#!/usr/bin/env python3
"""
Observatório Seriema — etapa 5: regime jurídico, fragmentos e certidões sem processo.

Três produtos:
  1. campo `regime` em cada ficha  (federal-4887 | federal-pre2003 | estadual | indefinido)
  2. campo `situacao_registro`     (ativo | fragmento | duplicata_provavel)
  3. base/certidoes_sem_processo.json — comunidades certificadas pela FCP que
     ainda não abriram processo em nenhuma esfera
"""
import json, math, os, re, unicodedata, hashlib
from collections import defaultdict
import pandas as pd

I    = os.environ.get('SERIEMA_INTERIM', 'interim')
BASE = os.environ.get('SERIEMA_BASE', 'base')

# ---------------------------------------------------------------- utilidades
def sem_acento(s):
    return unicodedata.normalize('NFKD', str(s)).encode('ascii', 'ignore').decode()

def norm(s):
    s = re.sub(r'[^A-Z0-9 ]', ' ', sem_acento(s).upper())
    return re.sub(r'\s+', ' ', s).strip()

def digitos(s):
    return re.sub(r'\D', '', str(s or ''))

def to_int(v):
    try:
        v = float(v)
        return None if math.isnan(v) else int(v)
    except Exception:
        return None

# ================================================================
# 1. REGIME JURÍDICO
# ================================================================
ORGAOS_ESTADUAIS = ('ITERPA', 'ITERMA', 'ITESP', 'INTERPI', 'CDA', 'CEMIG', 'ITERJ', 'INVTS')

def regime_de(x):
    """
    Decisão metodológica (auditoria de julho/2026):
    o que define o regime é o RITO percorrido, não apenas o rótulo de esfera.

    - Território que percorreu etapas do INCRA (RTID, portaria, decreto) ou
      recebeu título do INCRA é FEDERAL, ainda que um órgão estadual tenha
      participado da titulação final.
    - Titulações federais anteriores ao Decreto 4.887/2003, feitas pela
      Fundação Cultural Palmares, são federais de rito anterior.
    - O resto é estadual.
    """
    org  = (x.get('orgao_responsavel') or '').upper()
    esf  = (x.get('esfera') or '').upper()
    proc = digitos(re.split(r'[\n;]', str(x.get('processo_incra') or ''))[0])
    t    = x.get('tramite') or {}

    tem_estadual = any(s in org for s in ORGAOS_ESTADUAIS)
    tem_incra    = 'INCRA' in org or 'SPU' in org
    tem_fcp      = 'FCP' in org or 'PALMARES' in org
    # passou pelo rito federal?
    rito_federal = bool(t.get('rtid_edital_1') or t.get('portaria') or t.get('decreto'))

    if proc.startswith('01420') or (tem_fcp and not tem_incra and not rito_federal):
        return 'federal-pre2003'
    if len(proc) >= 15 and not proc.startswith('54'):
        return 'federal-pre2003'          # numeração antiga 21xxx (1996-98)
    if tem_estadual and (rito_federal or tem_incra):
        return 'federal-4887'             # compartilhado que percorreu o rito
    if tem_estadual or esf == 'ESTADUAL':
        return 'estadual'
    if proc.startswith('54') and len(proc) == 17:
        return 'federal-4887'
    if esf == 'FEDERAL':
        return 'federal-4887'
    return 'indefinido'

# ================================================================
# 2. FRAGMENTOS E DUPLICATAS
# ================================================================
def marcar_registros(fichas):
    """Fragmentos de polígono e duplicatas prováveis não somam ao total."""
    por_id = {x['id']: x for x in fichas}
    ativos = [x for x in fichas if x.get('processo_incra')]

    # --- fragmentos: registro sem processo, com prefixo/sufixo de recorte ---
    PADRAO_FRAG = re.compile(r'^TQ[ _]|_AREA\d|\bPARTE [AB]\b', re.I)
    for x in fichas:
        x.setdefault('situacao_registro', 'ativo')
        if x.get('processo_incra'):
            continue
        if not PADRAO_FRAG.search(x['nome']):
            continue
        cru = re.sub(r'(_AREA\d+|\bPARTE [AB]\b|/[A-Z]{2}$)', '', x['nome'], flags=re.I)
        cru = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', cru)      # EngenhoNovo -> Engenho Novo
        base_nome = norm(cru)
        base_nome = re.sub(r'^TQ ', '', base_nome).strip()
        area_frag = (x.get('geo') or {}).get('area_geom_ha') or x.get('area_ha') or 0
        melhor, motivo = None, None
        for y in ativos:
            if y['uf'] != x['uf']:
                continue
            mesmo_mun = any(norm(m) in [norm(n) for n in y['municipios']] for m in x['municipios'])
            if not mesmo_mun:
                continue
            ny = norm(y['nome'])
            nome_bate = base_nome and (base_nome in ny or ny in base_nome or ny.startswith(base_nome[:9]))
            ay = y.get('area_ha') or 0
            area_bate = ay and area_frag and abs(ay - area_frag) < max(2.0, ay * 0.05)
            if nome_bate and area_bate:
                melhor, motivo = y, 'nome e área coincidentes'; break
            if nome_bate and melhor is None:
                melhor, motivo = y, 'nome coincidente'
        if melhor:
            x['situacao_registro'] = 'fragmento'
            x['registro_principal'] = melhor['id']
            x['nota_registro'] = (f'Recorte cartográfico de {melhor["nome"]} ({melhor["id"]}); '
                                  f'não constitui território distinto — {motivo}.')

    # --- duplicatas prováveis: mesma UF, área idêntica, processos parecidos ---
    por_area = defaultdict(list)
    for x in fichas:
        if x['situacao_registro'] != 'ativo' or not x.get('area_ha'):
            continue
        por_area[(x['uf'], round(x['area_ha'], 4))].append(x)
    for (uf, area), grupo in por_area.items():
        if len(grupo) < 2:
            continue
        grupo.sort(key=lambda y: (y['fontes'] != ['INCRA/Acervo-Fundiário'], y['id']), reverse=True)
        principal = min(grupo, key=lambda y: (0 if 'INCRA/PDF-andamento' in y['fontes'] else 1, y['id']))
        for x in grupo:
            if x is principal:
                continue
            a, b = digitos(x.get('processo_incra')), digitos(principal.get('processo_incra'))
            difs = sum(1 for i in range(min(len(a), len(b))) if a[i] != b[i]) if len(a) == len(b) else 99
            x['situacao_registro'] = 'duplicata_provavel'
            x['registro_principal'] = principal['id']
            x['nota_registro'] = (
                f'Área idêntica à de {principal["nome"]} ({principal["id"]}) em {uf}: {area:,.4f} ha. '
                + (f'Números de processo divergem em {difs} dígito(s) — provável erro de digitação na origem. '
                   if difs <= 4 else '')
                + 'Aguarda conferência da CFU antes de fundir.')
    return fichas

# ================================================================
# 3. CERTIDÕES SEM PROCESSO
# ================================================================
def dispersar(chave, lat, lon, raio_km=2.6):
    """Deslocamento determinístico: o mesmo registro cai sempre no mesmo ponto."""
    h = hashlib.md5(str(chave).encode()).hexdigest()
    ang = int(h[:8], 16) / 0xFFFFFFFF * 2 * math.pi
    r   = math.sqrt(int(h[8:16], 16) / 0xFFFFFFFF) * raio_km
    dlat = (r / 111.0) * math.cos(ang)
    dlon = (r / (111.0 * max(math.cos(math.radians(lat)), 0.2))) * math.sin(ang)
    return round(lat + dlat, 6), round(lon + dlon, 6)

def certidoes_sem_processo():
    fcp = pd.read_parquet(f'{I}/fcp.parquet')
    ib  = pd.read_parquet(f'{I}/ibge.parquet')
    ib['lat'] = pd.to_numeric(ib.lat, errors='coerce')
    ib['lon'] = pd.to_numeric(ib.lon, errors='coerce')

    vazio = lambda s: s.isna() | s.astype(str).str.strip().isin(['', 'nan', 'None', '-'])
    sem = fcp[vazio(fcp.proc_incra)].copy()

    # localidades do Censo 2022 agrupadas pelo processo da Palmares
    loc = defaultdict(list)
    for _, r in ib[ib.fk != ''].iterrows():
        if pd.notna(r.lat):
            loc[r.fk].append({'nome': r.nm_cq, 'municipio': r.nm_munic,
                              'lat': round(float(r.lat), 6), 'lon': round(float(r.lon), 6)})
    # centroide municipal de recurso, em três níveis de preferência:
    #  1) malha oficial do IBGE, se estiver em entrada/ (arquivo BR_Municipios_*.zip)
    #  2) tabela de apoio versionada em pipeline/apoio/
    #  3) média das localidades quilombolas do município (Censo 2022)
    cent = ib.dropna(subset=['lat']).groupby('cd_munic')[['lat', 'lon']].mean().to_dict('index')
    cent_mun, cent_nome = {}, {}
    _malha = None
    for _cand in ('entrada/BR_Municipios_2025.zip', 'entrada/BR_Municipios_2024.zip'):
        if os.path.exists(_cand):
            _malha = _cand; break
    if _malha:
        try:
            import geopandas as gpd
            _g = gpd.read_file(f'zip://{_malha}').to_crs(4674)
            _p = _g.representative_point()          # sempre interno ao polígono
            for _i, _r in _g.iterrows():
                _cd = str(_r.get('CD_MUN') or _r.get('CD_GEOCMU') or '')
                cent_mun[_cd] = {'lat': round(_p.iloc[_i].y, 6), 'lon': round(_p.iloc[_i].x, 6)}
                cent_nome[(norm(_r.get('NM_MUN') or ''), str(_r.get('SIGLA_UF') or ''))] = cent_mun[_cd]
            print(f'  [centroides] malha oficial do IBGE: {len(cent_mun)} municípios ({_malha})')
        except Exception as e:
            print(f'  [centroides] falha ao ler a malha oficial ({e}); usando tabela de apoio')
            _malha = None
    if not _malha:
        _apoio = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              'apoio', 'municipios_centroides.csv')
        if os.path.exists(_apoio):
            _t = pd.read_csv(_apoio, dtype={'cd_mun': str})
            for _r in _t.itertuples():
                cent_mun[_r.cd_mun] = {'lat': _r.lat, 'lon': _r.lon}
                cent_nome[(norm(_r.nm_mun), _r.uf)] = cent_mun[_r.cd_mun]
            print(f'  [centroides] tabela de apoio: {len(cent_mun)} municípios')

    def centro_municipal(codigos, nome_mun, uf):
        for cd in codigos:
            for parte in re.split(r'[/;,]', str(cd)):
                p = re.sub(r'\D', '', parte)
                if p in cent_mun: return cent_mun[p]
                if p in cent:     return cent[p]
        for parte in re.split(r'\s+E\s+|/|,', norm(nome_mun)):
            k = (parte.strip(), uf)
            if k in cent_nome: return cent_nome[k]
        return None

    saida = []
    for i, (_, r) in enumerate(sem.iterrows(), 1):
        fk  = r.fk if r.fk else ''
        ls  = loc.get(fk, [])
        cds = [c.strip() for c in str(r.cd_ibge or '').split('|') if c.strip()]
        comunidades = [c.strip() for c in re.split(r'\s*\|\s*|\s*;\s*', str(r.comunidade or '')) if c.strip()]

        if ls:
            lat = round(sum(p['lat'] for p in ls) / len(ls), 6)
            lon = round(sum(p['lon'] for p in ls) / len(ls), 6)
            precisao, origem = 'censo', 'média das localidades do Censo 2022'
        else:
            base = centro_municipal(cds, r.municipio, str(r.uf or '').strip().upper())
            if base:
                lat, lon = dispersar(r.proc_fcp or i, base['lat'], base['lon'])
                precisao, origem = 'aproximada', 'posição aproximada no município (dispersão para leitura)'
            else:
                lat = lon = None
                precisao, origem = 'sem_coordenada', 'sem coordenada disponível'

        saida.append({
            'id': f'CRQ-{i:04d}',
            'comunidade': str(r.comunidade or '').strip(),
            'comunidades': comunidades,
            'n_comunidades': to_int(r.n_comunidades) or len(comunidades) or 1,
            'municipio': str(r.municipio or '').strip(),
            'cd_ibge': cds,
            'uf': str(r.uf or '').strip().upper(),
            'processo_fcp': str(r.proc_fcp or '').strip(),
            'portaria': str(r.portaria or '').strip() or None,
            'dou': r.dt_portaria_iso if isinstance(r.dt_portaria_iso, str) else None,
            'ano': to_int(r.ano_cert),
            'moradores': to_int(r.n_moradores),
            'urb_rural': str(r.urb_rural or '').strip() or None,
            'lat': lat, 'lon': lon, 'precisao': precisao, 'origem_ponto': origem,
            'localidades_censo': ls[:20],
            'n_localidades_censo': len(ls),
        })
    return saida

# ================================================================
# EXECUÇÃO
# ================================================================
if __name__ == '__main__':
    fichas = json.load(open(f'{BASE}/territorios_fichas.json', encoding='utf-8'))
    for x in fichas:
        x['regime'] = regime_de(x)
    fichas = marcar_registros(fichas)

    from collections import Counter
    print('=== REGIME ===')
    for k, v in Counter(x['regime'] for x in fichas).most_common():
        print(f'  {k:18s} {v}')
    print('\n=== SITUAÇÃO DO REGISTRO ===')
    for k, v in Counter(x['situacao_registro'] for x in fichas).most_common():
        print(f'  {k:20s} {v}')
    ativos = [x for x in fichas if x['situacao_registro'] == 'ativo']
    print(f'\nterritórios ativos: {len(ativos)} (de {len(fichas)} registros)')
    print('  federais :', sum(1 for x in ativos if x['regime'].startswith('federal')))
    print('  estaduais:', sum(1 for x in ativos if x['regime'] == 'estadual'))

    crq = certidoes_sem_processo()
    print(f'\n=== CERTIDÕES SEM PROCESSO: {len(crq)} ===')
    for k, v in Counter(c['precisao'] for c in crq).most_common():
        print(f'  {k:16s} {v}')
    print(f"  comunidades: {sum(c['n_comunidades'] or 0 for c in crq)}")
    print(f"  moradores  : {sum(c['moradores'] or 0 for c in crq):,}")

    json.dump(fichas, open(f'{BASE}/territorios_fichas.json', 'w', encoding='utf-8'),
              ensure_ascii=False, allow_nan=False)
    json.dump(crq, open(f'{BASE}/certidoes_sem_processo.json', 'w', encoding='utf-8'),
              ensure_ascii=False, allow_nan=False)

    # índice enxuto do mapa, agora com regime e situação
    idx = [{
        'id': x['id'], 'nome': x['nome'], 'uf': x['uf'], 'mun': '; '.join(x['municipios'][:3]),
        'fase': x['fase'], 'lat': x['geo']['lat'], 'lon': x['geo']['lon'],
        'pol': bool(x['geo'].get('tem_poligono')), 'area': x['area_ha'], 'fam': x['familias'],
        'prot': x['protocolo_consulta']['tem'], 'cert': x['certificacao']['n_certidoes'],
        'loc': x['ibge']['n_localidades'], 'esf': x['esfera'],
        'reg': x['regime'], 'sit': x['situacao_registro'],
    } for x in fichas if x['geo'].get('lat')]
    json.dump(idx, open(f'{BASE}/territorios_indice.json', 'w', encoding='utf-8'),
              ensure_ascii=False, allow_nan=False)

    r = json.load(open(f'{BASE}/resumo.json', encoding='utf-8'))
    r['por_regime']       = dict(Counter(x['regime'] for x in ativos).most_common())
    r['registros_totais'] = len(fichas)
    r['n_territorios']    = len(ativos)
    r['fragmentos']       = sum(1 for x in fichas if x['situacao_registro'] == 'fragmento')
    r['duplicatas']       = sum(1 for x in fichas if x['situacao_registro'] == 'duplicata_provavel')
    r['certidoes_sem_processo'] = {
        'n': len(crq),
        'comunidades': sum(c['n_comunidades'] or 0 for c in crq),
        'moradores': sum(c['moradores'] or 0 for c in crq),
        'por_uf': dict(Counter(c['uf'] for c in crq).most_common()),
        'por_precisao': dict(Counter(c['precisao'] for c in crq)),
        'por_ano': dict(sorted(Counter(c['ano'] for c in crq if c['ano']).items())),
    }
    r['por_fase_federal'] = dict(Counter(
        x['fase'] for x in ativos if x['regime'].startswith('federal')).most_common())
    r['por_fase_estadual'] = dict(Counter(
        x['fase'] for x in ativos if x['regime'] == 'estadual').most_common())
    json.dump(r, open(f'{BASE}/resumo.json', 'w', encoding='utf-8'),
              ensure_ascii=False, allow_nan=False, indent=1)
    print('\n>> base atualizada.')
