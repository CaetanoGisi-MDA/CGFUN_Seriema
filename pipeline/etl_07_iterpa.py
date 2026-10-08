#!/usr/bin/env python3
"""
Observatório Seriema — etapa 7: territórios titulados pelo ITERPA (Pará).

FONTE
  ITERPA — Instituto de Terras do Pará. Camada "quilombos estaduais"
  (banco ArcSDE gcg.sde.iterpa_quilombos_estaduais), exportada em shapefile,
  SIRGAS 2000 (EPSG:4674). Última edição registrada nos atributos
  (campo dataatual/datamodif): ver FONTE['atualizacao_fonte'], calculada.
  Obtida diretamente junto ao ITERPA pela Coordenação em outubro/2026 — não
  há endereço público de download; por isso o arquivo fica versionado em
  pipeline/apoio/iterpa/.

O QUE ESTA ETAPA FAZ
  1. Lê os polígonos e atributos do ITERPA (110 feições, um título cada).
  2. Casa cada feição com a base, nesta ordem de força:
       confirmado  — mesmo nº de processo ITERPA (o serial após a barra no
                     campo processo_incra da base) e nome compatível;
       provavel    — sem processo coincidente, mas nome compatível no mesmo
                     município do PA;
     Sem casamento → o território entra como registro novo.
  3. Enriquece a ficha casada com o bloco `iterpa` (portaria, matrícula,
     livro, folha, data do título, área do decreto, área líquida, famílias,
     nº do processo). Preenche coordenada/área geométrica SÓ quando a ficha
     não tem coordenada. Nunca sobrescreve área, fase ou famílias: diferenças
     ficam expostas como divergência.
  4. Detecta registros em dobro: quando uma feição ITERPA casa com um registro
     de polígono do INCRA (por processo) e também com um registro vindo só da
     tabela de títulos (por nome), e as áreas dos dois são idênticas, o
     segundo é marcado `duplicata_provavel` (fica preservado, mas sai das
     contagens) e a sua titulação passa ao registro principal, com nota.
  5. Regenera índice e resumo.

Uso:  python pipeline/etl_07_iterpa.py            (aplica)
      python pipeline/etl_07_iterpa.py --relatorio (só gera o relatório)
"""
import json, os, re, sys, csv, unicodedata
from collections import Counter, defaultdict

BASE  = os.environ.get('SERIEMA_BASE', 'base')
APOIO = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'apoio')
SHP   = os.path.join(APOIO, 'iterpa', 'quilomobos_estaduais.shp')

FONTE_NOME = 'ITERPA — camada de territórios quilombolas titulados pelo Estado do Pará'

# ---------------------------------------------------------------- normalização
def sem_acento(s):
    return unicodedata.normalize('NFKD', str(s)).encode('ascii', 'ignore').decode()

def norm(s):
    s = sem_acento(s or '').upper()
    s = re.sub(r'[^A-Z0-9 ]+', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()

VAZIAS = {'COMUNIDADE', 'COMUNIDADES', 'ASSOCIACAO', 'QUILOMBO', 'QUILOMBOS', 'QUILOMBOLA',
          'QUILOMBOLAS', 'REMANESCENTE', 'REMANESCENTES', 'REMANCESCENTES', 'DOS', 'DAS', 'DE',
          'DO', 'DA', 'E', 'TERRITORIO', 'MORADORES', 'AGRICULTORES', 'PESCADORES',
          'EXTRATIVISTAS', 'COMUNITARIA', 'AGRICOLA', 'LOCALIDADE', 'PARCELA', 'CRISTA',
          'DESENVOLVIMENTO', 'SUSTENTAVEL', 'ARTESANAIS', 'FORMADORES', 'NOSSA', 'SENHORA',
          'SANTA', 'SANTO', 'SAO', 'VILA', 'RIO', 'ILHA', 'IGARAPE', 'RAMAL', 'ALTO', 'BAIXO',
          'GRANDE', 'NOVO', 'NOVA', 'BOM', 'BOA', 'PA'}
# Palavras como SANTA/SAO/RIO são descartadas só para o "núcleo" do nome;
# o casamento por nome exige ao menos um token distintivo em comum.

def nucleo(s):
    return {t for t in norm(s).split() if len(t) > 2 and t not in VAZIAS and not t.isdigit()}

def serial(p):
    """Serial do processo ITERPA: '2006/304.677' -> '304677'; '295929' -> '295929'."""
    if not p: return None
    p = str(p)
    if re.match(r'^\d{5}\.\d{6}/\d{4}-\d{2}$', p):   # formato federal (INCRA/FCP)
        return None
    p = p.split('/')[-1]
    d = re.sub(r'\D', '', p).lstrip('0')
    return d or None

def municipios_iterpa(m):
    return {norm(x) for x in re.split(r'\s+E\s+|/|,', m or '') if x.strip()}

def mun_coincide(ms_iterpa, ms_base):
    b = {norm(x) for x in ms_base or []}
    # a base às vezes guarda "CAMETÁ E MOCAJUBA" como um só item
    b |= {norm(y) for x in ms_base or [] for y in re.split(r'\s+E\s+|/', sem_acento(x).upper())}
    return any(i[:8] == j[:8] for i in ms_iterpa for j in b if i and j)

def num_br(s):
    """'1.049,96' -> 1049.96 ; 'NADA CONSTA' -> None ; '15.146,01 m' -> 15146.01"""
    if s is None: return None
    s = str(s).strip()
    if not s or 'NADA' in s.upper(): return None
    s = re.sub(r'[^\d,.]', '', s)
    if ',' in s: s = s.replace('.', '').replace(',', '.')
    try: return float(s)
    except ValueError: return None

def txt(s):
    if s is None: return None
    s = str(s).replace('‬', '').strip()
    return None if not s or 'NADA CONSTA' in s.upper() or s.lower() in ('nan', 'none', 'nat') else s

def data_iso(v):
    if v is None: return None
    s = str(v)[:10]
    return s if re.match(r'^\d{4}-\d{2}-\d{2}$', s) else None

# ---------------------------------------------------------------- leitura
def carregar_iterpa():
    import geopandas as gpd
    g = gpd.read_file(SHP)
    if g.crs is None or g.crs.to_epsg() != 4674:
        g = g.to_crs(epsg=4674)
    gm = g.to_crs(epsg=5880)           # SIRGAS 2000 / Brazil Polyconic, para área
    regs = []
    for i, r in g.iterrows():
        pt = r.geometry.representative_point()   # sempre dentro do polígono
        regs.append({
            'fid': i,
            'territorio': txt(r['territorio']), 'comunidade': txt(r['comunidade']),
            'processo': txt(r['processo']), 'serial': serial(r['processo']),
            'ano_processo': txt(r['ano']),
            'municipio': txt(r['municipio']),
            'familias': int(num_br(r['familia'])) if num_br(r['familia']) else None,
            'area_decreto_ha': num_br(r['areadecret']),
            'area_liquida_ha': num_br(r['arealiquid']),
            'perimetro_decreto_m': num_br(r['perimdecre']),
            'portaria': txt(r['portaria']), 'matricula': txt(r['matricula']),
            'livro': txt(r['livro']),
            'folha': None if txt(r['folha']) in ('0', '00') else txt(r['folha']),   # '0' = não preenchido
            'data_titulo': data_iso(r['tituloexp']),
            'orgao_gestor': txt(r['orgaogest']), 'georreferenciamento': txt(r['georref']),
            'complemento': txt(r['complement']),
            'atualizado_em': data_iso(r['dataatual']) or data_iso(r['datamodif']),
            'area_geom_ha': round(gm.geometry.iloc[i].area / 10000, 4),
            'lat': round(pt.y, 6), 'lon': round(pt.x, 6),
        })
    return regs

# ---------------------------------------------------------------- vínculos manuais
# Casos em que nem processo, nem nome, nem município permitem o casamento
# automático, mas há prova numérica. Chave: serial do processo ITERPA.
# Alvo: (UF, nome normalizado do registro na base) — não o id SRM, que pode
# mudar se a ordem das fontes mudar.
VINCULOS_MANUAIS = {
    '123018': (('PA', 'PEAFU'),
               'No shapefile do ITERPA, o município (Porto de Moz) e a área decretada (4.879,081 ha) '
               'desta feição repetem os de Camutá do Rio Ipixuna. O polígono, porém, mede 1.522,67 ha '
               'e está em Monte Alegre — compatível com PEAFU na tabela de títulos do INCRA '
               '(Monte Alegre, 1.525,9261 ha). Vinculado por geometria; atributos do ITERPA a conferir.'),
    '73899':  (('PA', 'TQ EREPECURU'),
               'Título ITERPA de 160.459,4072 ha. Somado ao título do INCRA de 71.150,8867 ha, '
               'resulta em 231.610,2939 ha — a área do território Erepecuru na tabela de títulos do '
               'INCRA. Vinculado pela soma exata das áreas.'),
    '158126': (('PA', 'TROMBETAS'),
               'Título ITERPA de 57.024,6216 ha. Somado ao título do INCRA de 23.862,4725 ha, '
               'resulta em 80.887,0941 ha — a área do território Trombetas na tabela de títulos do '
               'INCRA. Vinculado pela soma exata das áreas.'),
}

TABELA_TITULOS = ['INCRA/DFQ-Títulos-expedidos']
FASES_TITULO = ('TITULADO', 'TITULO_PARCIAL', 'TITULO_ANULADO')

def area_eq(a, b, tol=0.01):
    return a is not None and b is not None and abs(a - b) <= tol

def area_prox(a, b, frac=0.25):
    return a is not None and b is not None and b > 0 and abs(a - b) / b <= frac

def variantes(f):
    """Nomes da ficha usados no casamento. O nome_na_fonte da titulação NÃO
    entra: quando o vínculo com a tabela de títulos é só 'provável', ele pode
    ser de outro território (foi o que ocorreu com Santa Luzia do Bom Prazer)."""
    ns = [f['nome']] + list((f.get('certificacao') or {}).get('comunidades') or [])
    return [nucleo(n) for n in ns if nucleo(n)]

def compat(r, f):
    """'igual' | 'contido' | None — compara o núcleo do nome ITERPA com cada nome da ficha."""
    nt, nc = nucleo(r['territorio']), nucleo(r['comunidade'])
    nivel = None
    for v in variantes(f):
        if v == nt or v == nc: return 'igual'
        if (nt and (nt <= v or v <= nt)) or (v <= nc): nivel = 'contido'
    return nivel

def so_tabela(f):
    return f.get('fontes') == TABELA_TITULOS

def casar(regs, fichas):
    pa = [f for f in fichas if f['uf'] == 'PA']
    por_serial = defaultdict(list)
    for f in pa:
        s = serial(f.get('processo_incra'))
        if s: por_serial[s].append(f)
    por_nome = {(f['uf'], norm(f['nome'])): f for f in pa}

    casos = []
    for r in regs:
        a, mr = r['area_decreto_ha'], municipios_iterpa(r['municipio'])
        c = {'reg': r, 'principal': None, 'vinculo': None, 'criterio': None, 'manual': None}
        def pega(f, v, crit): c.update(principal=f, vinculo=v, criterio=crit)
        ser = por_serial.get(r['serial'], [])
        # prefere registro com polígono/processo a registro vindo só da tabela
        ordem = lambda f: (so_tabela(f), f['situacao_registro'] != 'ativo',
                           {'igual': 0, 'contido': 1}.get(compat(r, f), 2))

        if r['serial'] in VINCULOS_MANUAIS and VINCULOS_MANUAIS[r['serial']][0] in por_nome:
            alvo, nota = VINCULOS_MANUAIS[r['serial']]
            pega(por_nome[alvo], 'provavel', 'vínculo manual documentado no pipeline')
            c['manual'] = nota
        elif (t := sorted([f for f in ser if area_eq(f['area_ha'], a)], key=ordem)):
            pega(t[0], 'confirmado', 'mesmo nº de processo ITERPA e mesma área decretada')
        elif (t := sorted([f for f in pa if area_eq(f['area_ha'], a)
                           and (compat(r, f) or mun_coincide(mr, f['municipios']))], key=ordem)):
            pega(t[0], 'provavel', 'mesma área (quatro casas decimais) e nome ou município compatível')
        elif (t := sorted([f for f in ser if compat(r, f)], key=ordem)):
            pega(t[0], 'confirmado', 'mesmo nº de processo ITERPA e nome compatível')
        elif len(ser) == 1 and mun_coincide(mr, ser[0]['municipios']):
            pega(ser[0], 'confirmado', 'mesmo nº de processo ITERPA e mesmo município')
        elif (t := sorted([f for f in pa if mun_coincide(mr, f['municipios'])
                           and (compat(r, f) == 'igual' or
                                (compat(r, f) == 'contido' and area_prox(a, f['area_ha'])))],
                          key=ordem)):
            pega(t[0], 'provavel', 'nome compatível no mesmo município (sem processo nem área coincidentes)')
        elif ser:
            pega(sorted(ser, key=ordem)[0], 'provavel', 'mesmo nº de processo ITERPA, mas nome e área não conferem')
        casos.append(c)
    return casos

# ---------------------------------------------------------------- aplicação
MINUSC = {'de', 'da', 'do', 'das', 'dos', 'e'}

def titulo_pt(s):
    ps = s.lower().split()
    cap = lambda p: '-'.join(x[:1].upper() + x[1:] for x in p.split('-'))
    return ' '.join(p if (i and p in MINUSC) else cap(p) for i, p in enumerate(ps))

def nome_territorio(r):
    """Nome legível para um território novo. Quando o campo 'territorio' do
    ITERPA traz só a sigla da associação (ARQAE, AQUIP...), o nome sai do
    campo 'comunidade'."""
    t = (r['territorio'] or '').strip()
    if ' ' not in t and len(t) <= 8:
        m = re.search(r'(?:QUILOMBOS?|QUILOMBOLAS?|COMUNIDADE)\s+(?:(?:DA|DE|DO|DAS|DOS)\s+)?'
                      r'(?:LOCALIDADE\s+DE\s+|COMUNIDADE\s+)?([^-]+?)\s*(?:-.*)?$', (r['comunidade'] or '').upper())
        t = m.group(1) if m else (r['comunidade'] or t)
    t = re.sub(r'\s*-\s*PARCELA\s*\d+\s*$', '', t, flags=re.I)
    t = re.sub(r'^(COMUNIDADES?|REMANESCENTES?)\s+(DE\s+QUILOMBO\s+)?((DE|DO|DA|DOS|DAS)\s+)?', '', t, flags=re.I)
    t = re.sub(r'^QUILOMBO\s+(DE|DO|DA)\s+', '', t, flags=re.I)
    return titulo_pt(t.strip())

def proc_iterpa(r):
    """Mesmo formato que a base já usa para processos do ITERPA: 'ano/número'."""
    p = r['processo'] or ''
    if '/' in p: return p
    ano = r['ano_processo'] or ''
    return f'{ano}/{p}' if re.match(r'^(19|20)\d\d$', ano) and p else (p or None)

def bloco_reg(r):
    data = r['data_titulo'] if r['data_titulo'] and r['data_titulo'] > '1901' else None
    return {k: r[k] for k in ('territorio', 'comunidade', 'processo', 'ano_processo', 'municipio',
                              'familias', 'area_decreto_ha', 'area_liquida_ha', 'perimetro_decreto_m',
                              'area_geom_ha', 'portaria', 'matricula', 'livro', 'folha',
                              'complemento', 'atualizado_em')} | {
        'data_titulo': data,
        'data_titulo_ausente': r['data_titulo'] is not None and data is None,
    }

def div(f, tipo, texto):
    f.setdefault('divergencias', []).append({'tipo': tipo, 'texto': texto})

def fmt(v, c=4):
    return f'{v:,.{c}f}'.replace(',', 'X').replace('.', ',').replace('X', '.')

def aplicar(casos, fichas, fonte):
    proximo = max(int(f['id'].split('-')[1]) for f in fichas) + 1
    stats = Counter()

    # 1) agrupa feições por ficha (um território pode ter vários títulos)
    grupos = defaultdict(list)
    novos = defaultdict(list)
    for c in casos:
        if c['principal'] is not None: grupos[c['principal']['id']].append(c)
        else: novos[c['reg']['serial'] or f"fid{c['reg']['fid']}"].append(c)
    por_id = {f['id']: f for f in fichas}

    # 2) territórios ausentes da base → registros novos
    for chave, cs in sorted(novos.items(), key=lambda kv: kv[1][0]['reg']['fid']):
        regs = [c['reg'] for c in cs]
        maior = max(regs, key=lambda r: r['area_geom_ha'] or 0)
        datas = [b['data_titulo'] for b in map(bloco_reg, regs) if b['data_titulo']]
        f = {
            'id': f'SRM-{proximo:04d}', 'nome': nome_territorio(maior), 'uf': 'PA',
            'municipios': [titulo_pt(m.strip()) for m in re.split(r'\s+E\s+|/', maior['municipio'] or '') if m.strip()],
            'processo_incra': proc_iterpa(maior), 'esfera': 'ESTADUAL', 'orgao_responsavel': 'ITERPA',
            'fase': 'TITULADO', 'fase_ordem': 7,
            'area_ha': round(sum(r['area_decreto_ha'] or 0 for r in regs), 4) or None,
            'familias': max((r['familias'] or 0 for r in regs), default=0) or None,
            'geo': {'lat': maior['lat'], 'lon': maior['lon'], 'tem_poligono': True,
                    'area_geom_ha': round(sum(r['area_geom_ha'] for r in regs), 4)},
            'geo_origem': 'centroide_poligono_iterpa',
            'tramite': {'rtid_edital_1': None, 'rtid_edital_2': None, 'portaria': None, 'decreto': None,
                        'titulo_txt': None, 'titulacao': max(datas) if datas else None, 'dispensas': {}},
            'certificacao': {'n_certidoes': 0, 'comunidades': [], 'moradores_fcp': None,
                             'ano_primeira': None, 'detalhe': []},
            'ibge': {'cd_tq': None, 'nm_tq': None, 'n_localidades': 0, 'localidades': []},
            'protocolo_consulta': {'tem': False, 'n': 0, 'itens': []},
            'vinculos': {'poligono': 'proprio', 'fcp': 'nao_localizado', 'ibge': 'nao_localizado'},
            'fontes': ['ITERPA/camada-quilombos-estaduais'],
            'regime': 'estadual', 'situacao_registro': 'ativo', 'divergencias': [],
            'nota_registro': ('Território titulado pelo ITERPA que não constava da base: não foi '
                              'localizado no quadro de andamento do INCRA, na base cartográfica do '
                              'INCRA nem na tabela de títulos expedidos. Certidão da FCP e localidades '
                              'do Censo ainda não vinculadas.'),
        }
        f['iterpa'] = {**fonte, 'vinculo': 'registro próprio', 'criterio': None,
                       'registros': [bloco_reg(r) for r in regs], 'preencheu': []}
        if len(regs) > 1:
            f['iterpa']['nota'] = f'O ITERPA registra {len(regs)} títulos (parcelas) para este território.'
        fichas.append(f); por_id[f['id']] = f
        for c in cs: c['principal'], c['novo'] = f, True
        proximo += 1; stats['novos'] += 1

    # 3) enriquece as fichas casadas
    for fid, cs in grupos.items():
        f = por_id[fid]
        regs = [c['reg'] for c in cs]
        vinc = 'confirmado' if all(c['vinculo'] == 'confirmado' for c in cs) else 'provavel'
        criterios = sorted({c['criterio'] for c in cs})
        f['iterpa'] = {**fonte, 'vinculo': vinc, 'criterio': '; '.join(criterios),
                       'registros': [bloco_reg(r) for r in regs], 'preencheu': []}
        for c in cs:
            if c['manual']: f['iterpa']['nota'] = c['manual']
        if len(regs) > 1:
            f['iterpa']['nota'] = (f['iterpa'].get('nota', '') + ' ' if f['iterpa'].get('nota') else '') + \
                                  f'O ITERPA registra {len(regs)} títulos para este território.'
        if 'ITERPA/camada-quilombos-estaduais' not in f['fontes']:
            f['fontes'] = f['fontes'] + ['ITERPA/camada-quilombos-estaduais']
        stats[f'casados_{vinc}'] += 1

        # registro marcado como duplicata pela etapa 5 mas que o ITERPA mostra ser
        # território próprio (mesmo processo E mesma área de um título ITERPA)
        if f['situacao_registro'] == 'duplicata_provavel' and any(
                c['vinculo'] == 'confirmado' and area_eq(f['area_ha'], c['reg']['area_decreto_ha']) for c in cs):
            antigo = f.get('nota_registro', '')
            f['situacao_registro'] = 'ativo'
            f.pop('registro_principal', None)
            f['nota_registro'] = ('Reativado pela etapa ITERPA. A etapa anterior o havia marcado como '
                                  'duplicata provável por ter área idêntica à de outro registro; o ITERPA, '
                                  'porém, registra para este processo um título próprio com exatamente esta '
                                  f'área. Nota anterior: {antigo}')
            stats['reativados'] += 1

        soma = round(sum(r['area_decreto_ha'] or 0 for r in regs), 4)
        geom = round(sum(r['area_geom_ha'] or 0 for r in regs), 4)
        maior = max(regs, key=lambda r: r['area_geom_ha'] or 0)

        # preenche só o que falta — nunca sobrescreve
        if f['area_ha'] is None and soma:
            f['area_ha'] = soma; f['iterpa']['preencheu'].append('area_ha')
        if f['familias'] is None and any(r['familias'] for r in regs):
            f['familias'] = max(r['familias'] or 0 for r in regs); f['iterpa']['preencheu'].append('familias')
        if f['geo'].get('lat') is None or (not f['geo'].get('tem_poligono') and vinc == 'confirmado'):
            if f['geo'].get('lat') is not None:
                f['iterpa']['coordenada_anterior'] = {'lat': f['geo']['lat'], 'lon': f['geo']['lon'],
                                                      'origem': f.get('geo_origem')}
            f['geo'].update(lat=maior['lat'], lon=maior['lon'], tem_poligono=True, area_geom_ha=geom)
            f['geo_origem'] = 'centroide_poligono_iterpa'
            if f['vinculos'].get('poligono') in (None, 'nao_localizado'):
                f['vinculos']['poligono'] = vinc
            f['iterpa']['preencheu'].append('coordenada')
            stats['coordenadas_preenchidas'] += 1
        if not f['tramite'].get('titulacao'):
            ds = [b['data_titulo'] for b in f['iterpa']['registros'] if b['data_titulo']]
            if ds: f['tramite']['titulacao'] = max(ds); f['iterpa']['preencheu'].append('data_titulo')

        # divergências — expostas, não resolvidas
        if f['area_ha'] is not None and soma and 'area_ha' not in f['iterpa']['preencheu'] \
                and abs(soma - f['area_ha']) > max(0.5, 0.005 * f['area_ha']):
            div(f, 'divergencia_iterpa',
                f'Área do território na base: {fmt(f["area_ha"])} ha. Área decretada pelo ITERPA '
                f'({len(regs)} título{"s" if len(regs) > 1 else ""}): {fmt(soma)} ha. Diferença menor '
                f'no ITERPA pode indicar que o Estado titulou só parte do território; maior, erro em '
                f'uma das fontes. Não corrigido automaticamente.')
            stats['div_area'] += 1
        for r in regs:
            if r['area_decreto_ha'] and r['area_geom_ha'] and \
                    abs(r['area_geom_ha'] - r['area_decreto_ha']) / r['area_decreto_ha'] > 0.2:
                div(f, 'divergencia_iterpa',
                    f'O polígono do ITERPA para "{r["territorio"]}" mede {fmt(r["area_geom_ha"], 2)} ha, '
                    f'mas a área decretada no mesmo registro é {fmt(r["area_decreto_ha"])} ha. '
                    f'O polígono pode estar incompleto ou a área decretada, errada.')
                stats['div_geometria'] += 1
        if f['fase'] not in FASES_TITULO:
            ds = [b['data_titulo'] for b in f['iterpa']['registros'] if b['data_titulo']]
            div(f, 'fase_divergente',
                f'O ITERPA registra título expedido{" em " + max(ds) if ds else ""}, mas a fase na base é '
                f'"{f["fase"]}". Vínculo {vinc} ({"; ".join(criterios)}). Fase não alterada.')
            stats['div_fase'] += 1
        if any(b['data_titulo_ausente'] for b in f['iterpa']['registros']):
            f['iterpa']['nota'] = (f['iterpa'].get('nota', '') + ' ').lstrip() + \
                'Em ao menos um registro do ITERPA a data do título está preenchida com 01/01/1900 (sem data).'

    # 4) titulação ligada à ficha errada pela etapa 6 (vínculo apenas provável):
    #    se a área do território na tabela do INCRA é idêntica à de um título
    #    ITERPA que pertence a OUTRA ficha, a titulação é transferida.
    area_para_ficha = {}
    for c in casos:
        if c['reg']['area_decreto_ha']:
            area_para_ficha[round(c['reg']['area_decreto_ha'], 2)] = c['principal']
    for f in list(fichas):
        t = f.get('titulacao')
        if not t or t.get('vinculo') != 'provavel' or f['uf'] != 'PA': continue
        destino = area_para_ficha.get(round(t['area_territorio_ha'] or -1, 2))
        if destino is None or destino is f or destino.get('titulacao'): continue
        destino['titulacao'] = {**t, 'vinculo': 'provavel',
                                'criterio_vinculo': (f'área do território na tabela ({fmt(t["area_territorio_ha"])} ha) '
                                                     f'idêntica à área decretada pelo ITERPA; antes estava ligada, '
                                                     f'por semelhança de nome, a {f["nome"]} ({f["id"]})')}
        del f['titulacao']
        div(f, 'divergencia_iterpa',
            f'A etapa de títulos havia ligado a esta ficha, por semelhança de nome, a linha "{t["nome_na_fonte"]}" '
            f'({t["municipio_na_fonte"]}) da tabela de títulos do INCRA. O ITERPA mostra que essa linha '
            f'corresponde a {destino["nome"]} ({destino["id"]}), e a titulação foi transferida para lá. '
            f'Se a fase desta ficha dependia daquela linha, ela precisa ser conferida.')
        stats['titulacao_transferida'] += 1

    # 5) duplicatas: registro vindo só da tabela de títulos com a mesma área de
    #    um registro principal casado com o ITERPA
    tabela = [f for f in fichas if so_tabela(f) and f['situacao_registro'] == 'ativo' and f['uf'] == 'PA']
    for fid, cs in grupos.items():
        p = por_id[fid]
        if so_tabela(p) or p['situacao_registro'] != 'ativo': continue
        for t in tabela:
            if t is p or t['situacao_registro'] != 'ativo' or t['id'] in grupos: continue
            # a área tem de bater com o registro principal E com um título do ITERPA:
            # só a área do polígono do INCRA não basta (ela própria pode estar errada)
            if not area_eq(t['area_ha'], p['area_ha']): continue
            if not any(area_eq(t['area_ha'], c['reg']['area_decreto_ha']) for c in cs): continue
            if not (any(compat(c['reg'], t) for c in cs) or mun_coincide(municipios_iterpa(cs[0]['reg']['municipio']), t['municipios'])):
                continue
            t['situacao_registro'] = 'duplicata_provavel'
            t['registro_principal'] = p['id']
            t['nota_registro'] = (f'Mesmo território que {p["nome"]} ({p["id"]}): área idêntica '
                                  f'({fmt(p["area_ha"])} ha), mesmo município, e ambos correspondem ao título '
                                  f'do ITERPA de processo {cs[0]["reg"]["processo"]}. Este registro foi criado '
                                  f'a partir da tabela de títulos do INCRA, que grafa o nome de outra forma. '
                                  f'Preservado, mas fora das contagens.')
            if not p.get('titulacao') and t.get('titulacao'):
                p['titulacao'] = {**t['titulacao'], 'vinculo': 'provavel',
                                  'criterio_vinculo': f'transferência do registro duplicado {t["id"]} (área idêntica, '
                                                      f'mesmo título ITERPA)',
                                  'nome_na_fonte': t['titulacao'].get('nome_na_fonte') or t['nome']}
                p['divergencias'] = [d for d in p['divergencias'] if d['tipo'] != 'titulado_ausente_da_tabela']
            stats['duplicatas_marcadas'] += 1
    # 6) fichas tituladas do PA que ficaram sem linha da tabela de títulos
    #    (por transferência acima ou porque a etapa 6 sobrescreveu a linha):
    #    religa a uma linha ainda livre com área idêntica e nome ou município compatível.
    tt = os.path.join(BASE, 'titulos_expedidos.json')
    if os.path.exists(tt):
        tabela_tt = json.load(open(tt, encoding='utf-8'))
        linhas = tabela_tt['registros']
        usadas = {(x.get('titulacao') or {}).get('num_fonte') for x in fichas}
        for f in fichas:
            if f['uf'] != 'PA' or f.get('titulacao') or f['situacao_registro'] != 'ativo' \
                    or f['fase'] not in FASES_TITULO or f['area_ha'] is None: continue
            for l in linhas:
                if l['uf'] != 'PA' or l['num_fonte'] in usadas: continue
                if not area_eq(l['area_territorio_ha'], f['area_ha']): continue
                pseudo = {'territorio': l['territorio'], 'comunidade': ''}
                if not (compat(pseudo, f) or mun_coincide(municipios_iterpa(norm(l['municipio'])), f['municipios'])):
                    continue
                f['titulacao'] = {
                    'fonte': tabela_tt['fonte']['nome'],
                    'atualizacao_fonte': tabela_tt['fonte'].get('atualizacao_fonte'),
                    'num_fonte': l['num_fonte'], 'area_territorio_ha': l['area_territorio_ha'],
                    'area_titulada_ha': l['area_titulada_ha'], 'pct_titulado': l['pct_titulado'],
                    'titulos': l['titulos'], 'n_titulos': len(l['titulos']),
                    'itemizacao_pendente': l['itemizacao_pendente'], 'vinculo': 'provavel',
                    'criterio_vinculo': 'área do território idêntica (quatro casas decimais) e nome ou município compatível',
                    'nome_na_fonte': l['territorio'], 'municipio_na_fonte': l['municipio']}
                f['divergencias'] = [d for d in f['divergencias'] if d['tipo'] != 'titulado_ausente_da_tabela']
                usadas.add(l['num_fonte']); stats['titulacao_religada'] += 1
                break
    # 6b) data do título: ITERPA x tabela do INCRA, só quando há um título de
    #     cada lado (com parcelas, a comparação não é segura)
    for f in fichas:
        it, t = f.get('iterpa'), f.get('titulacao')
        if not it or not t or len(it['registros']) != 1 or len(t.get('titulos') or []) != 1: continue
        di, dt = it['registros'][0]['data_titulo'], t['titulos'][0]['data']
        if di and dt and di != dt:
            div(f, 'divergencia_iterpa',
                f'Data do título: {di[8:10]}/{di[5:7]}/{di[:4]} no ITERPA; {dt[8:10]}/{dt[5:7]}/{dt[:4]} na tabela '
                f'de títulos do INCRA. Pode ser erro de transcrição em uma das fontes, ou um título '
                f'posterior (retificação ou novo título) registrado só no ITERPA. Não corrigido.')
            stats['div_data'] += 1

    # 7) ficha casada com o ITERPA e ainda sem titulação: registra a titulação
    #    pelo próprio órgão expedidor. O percentual titulado fica em branco —
    #    o ITERPA informa a área do título, não a área total do território.
    for f in fichas:
        it = f.get('iterpa')
        # só no regime estadual: em ficha de processo federal o título estadual é
        # sinal a conferir (fica no bloco ITERPA e como divergência), não titulação
        if not it or f.get('titulacao') or f['regime'] != 'estadual': continue
        tits = [{'orgao': 'ITERPA', 'area_ha': b['area_decreto_ha'], 'data': b['data_titulo'],
                 'parceria_incra': False, 'clausula_suspensiva': False, 'ccdru': False}
                for b in it['registros'] if b['area_decreto_ha']]
        if not tits: continue
        f['titulacao'] = {
            'fonte': it['fonte'], 'atualizacao_fonte': it['atualizacao_fonte'],
            'area_territorio_ha': f['area_ha'],
            'area_titulada_ha': round(sum(t['area_ha'] for t in tits), 4),
            'pct_titulado': None, 'titulos': tits, 'n_titulos': len(tits),
            'itemizacao_pendente': False,
            'vinculo': 'registro próprio' if it['vinculo'] == 'registro próprio' else it['vinculo'],
            'criterio_vinculo': None if it['vinculo'] == 'registro próprio' else
                                f'registro do ITERPA ({it["criterio"]})',
            'origem': 'ITERPA',
        }
        stats['titulacao_pelo_iterpa'] += 1
    return stats

# ---------------------------------------------------------------- relatório
def relatorio(casos, caminho):
    with open(caminho, 'w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh, delimiter=';')
        w.writerow(['fid', 'territorio_iterpa', 'comunidade_iterpa', 'processo', 'municipio',
                    'area_decreto_ha', 'area_poligono_ha', 'data_titulo', 'vinculo', 'criterio',
                    'id_base', 'nome_base', 'processo_base', 'area_base_ha'])
        for c in casos:
            r, f = c['reg'], c['principal']
            w.writerow([r['fid'], r['territorio'], r['comunidade'], r['processo'], r['municipio'],
                        r['area_decreto_ha'], r['area_geom_ha'], r['data_titulo'],
                        'novo' if c.get('novo') else c['vinculo'], c['manual'] or c['criterio'] or '',
                        f and f['id'], f and f['nome'], f and f.get('processo_incra'), f and f['area_ha']])

if __name__ == '__main__':
    fichas = json.load(open(f'{BASE}/territorios_fichas.json', encoding='utf-8'))
    if any(f.get('iterpa') for f in fichas) and '--relatorio' not in sys.argv:
        sys.exit('A base já passou pela etapa ITERPA. Rode o pipeline desde a etapa 1 '
                 '(a etapa 7 parte da saída da etapa 6), para não duplicar registros.')
    regs = carregar_iterpa()
    datas = sorted(r['atualizado_em'] for r in regs if r['atualizado_em'])
    fonte = {'fonte': FONTE_NOME, 'atualizacao_fonte': datas[-1] if datas else None,
             'arquivo': 'pipeline/apoio/iterpa/quilomobos_estaduais.shp'}
    casos = casar(regs, fichas)
    print('feições ITERPA ...................', len(regs))
    print('casamento ........................', dict(Counter(c['vinculo'] or 'novo' for c in casos)))
    if '--relatorio' in sys.argv:
        i = sys.argv.index('--relatorio')
        relatorio(casos, sys.argv[i + 1] if len(sys.argv) > i + 1 else 'iterpa_relatorio.csv'); sys.exit(0)

    stats = aplicar(casos, fichas, fonte)
    for k, v in sorted(stats.items()): print(f'  {k:.<32} {v}')

    json.dump(fichas, open(f'{BASE}/territorios_fichas.json', 'w', encoding='utf-8'),
              ensure_ascii=False, allow_nan=False)
    json.dump({'fonte': fonte, 'registros': [
                   {**bloco_reg(c['reg']), 'fid': c['reg']['fid'], 'lat': c['reg']['lat'], 'lon': c['reg']['lon'],
                    'id_base': c['principal']['id'], 'vinculo': 'novo' if c.get('novo') else c['vinculo'],
                    'criterio': c['manual'] or c['criterio']} for c in casos]},
              open(f'{BASE}/iterpa.json', 'w', encoding='utf-8'), ensure_ascii=False, allow_nan=False, indent=1)
    relatorio(casos, os.path.join(APOIO, 'iterpa', 'cruzamento_iterpa_x_base.csv'))
    print('>> base/iterpa.json e pipeline/apoio/iterpa/cruzamento_iterpa_x_base.csv gravados')

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from regenerar import regenerar
    from etl_06_titulos import FONTE as FT
    regenerar(fichas, BASE, FT['nome'] + '; no Pará, também ITERPA')
    print('>> índice e resumo regenerados')
