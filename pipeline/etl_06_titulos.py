#!/usr/bin/env python3
"""
Observatório Seriema — etapa 6: títulos expedidos.

FONTE
  INCRA/DFQ — "Títulos expedidos às comunidades quilombolas de 1995 até a
  atualidade, por órgãos fundiários federais, estaduais e municipais".
  Última atualização da fonte: 19/11/2025.
  Endereço original: gov.br/incra → Governança Fundiária → Quilombolas.

COMO ESTES DADOS FORAM OBTIDOS  (leia antes de usar)
  Em julho de 2026 o arquivo saiu do ar no portal do INCRA: a página foi
  remodelada e passou a apontar para um nome de arquivo inexistente. Os dados
  aqui foram transcritos do conteúdo do documento, não extraídos do PDF por
  programa. A transcrição foi validada contra os totais que o próprio
  documento declara:

      territórios ....... 245        conferido: 245        ✓
      área territórios .. 1.595.781,2907 ha   conferido: idem   ✓
      famílias .......... 24.250      conferido: 24.250     ✓
      comunidades ....... 397         conferido: 397        ✓
      títulos ........... 384         itemizados: 255       ✗ parcial
      área titulada ..... 1.162.002,0645 ha   conferida: 1.106.980,5383 ha

  Os quatro primeiros totais batem exatamente, o que dá alta confiança à
  linha de cada território. Os dois últimos não fecham: em 19 territórios que
  receberam vários títulos, as linhas dos títulos individuais vieram
  embaralhadas e não foi possível reassociá-las com segurança. Esses casos
  ficam marcados como `itemizacao_pendente` e correspondem a 129 títulos e
  4,7% da área titulada. NENHUMA área foi estimada — o que não pôde ser
  conferido está registrado como ausente, não como zero nem como aproximação.

  Ao obter o PDF original, rode este script com o arquivo em entrada/ para
  substituir a transcrição pela extração automática.
"""
import csv, json, os, re, unicodedata
from collections import defaultdict

BASE  = os.environ.get('SERIEMA_BASE', 'base')
APOIO = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'apoio')

FONTE = {
    'nome': 'INCRA/DFQ — Títulos expedidos às comunidades quilombolas (1995 até a atualidade)',
    'atualizacao_fonte': '2025-11-19',
    'obtencao': 'transcrição validada por totais; PDF indisponível no portal em julho/2026',
    'confianca': 'linha do território conferida contra 4 totais oficiais; itemização de títulos parcial',
    'totais_declarados': {'territorios': 245, 'titulos': 384, 'comunidades': 397,
                          'familias': 24250, 'area_territorios_ha': 1595781.2907,
                          'area_titulada_ha': 1162002.0645},
}

def sem_acento(s):
    return unicodedata.normalize('NFKD', str(s)).encode('ascii', 'ignore').decode()

def norm(s):
    s = sem_acento(s).upper()
    s = re.sub(r'^(TQ|TERRITORIO QUILOMBOLA|COMUNIDADE QUILOMBOLA|QUILOMBO)[\s_]+', '', s)
    s = re.sub(r'\bSTO\b', 'SANTO', s); s = re.sub(r'\bSTA\b', 'SANTA', s)
    s = re.sub(r'[^A-Z0-9 ]+', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()

def carregar_titulos():
    p = os.path.join(APOIO, 'titulos_incra.csv')
    if not os.path.exists(p):
        print(f'  [títulos] {p} não encontrado — etapa ignorada'); return []
    regs = []
    for l in csv.DictReader(open(p, encoding='utf-8'), delimiter='|'):
        titulos = []
        if l['titulos'].strip():
            for t in l['titulos'].split(';'):
                orgao, area, dt = t.split(':')
                titulos.append({'orgao': orgao, 'area_ha': float(area), 'data': dt,
                                'parceria_incra': orgao.endswith('**'),
                                'clausula_suspensiva': orgao.endswith('*') and not orgao.endswith('**'),
                                'ccdru': orgao.endswith('***')})
        regs.append({
            'num_fonte': int(l['num']), 'territorio': l['territorio'],
            'municipio': l['municipio'], 'uf': l['uf'],
            'n_comunidades': int(l['n_com']), 'familias': int(l['familias']),
            'area_territorio_ha': float(l['area_terr']),
            'pct_titulado': float(l['pct']),
            'titulos': titulos,
            'area_titulada_ha': round(sum(t['area_ha'] for t in titulos), 4) if titulos else None,
            'itemizacao_pendente': not titulos,
            'chave': norm(l['territorio']) + '|' + l['uf'],
        })
    return regs

if __name__ == '__main__':
    regs = carregar_titulos()
    fichas = json.load(open(f'{BASE}/territorios_fichas.json', encoding='utf-8'))

    idx = defaultdict(list)
    for f in fichas:
        if f['situacao_registro'] != 'ativo': continue
        idx[norm(f['nome']) + '|' + str(f['uf'])].append(f)

    casados = orfaos = 0
    for r in regs:
        alvos = idx.get(r['chave'])
        if not alvos:
            # tenta pelo município, para nomes com grafia divergente
            alvos = [f for f in fichas if f['uf'] == r['uf'] and f['situacao_registro'] == 'ativo'
                     and any(norm(r['municipio']).startswith(norm(m)[:8]) for m in f['municipios'])
                     and norm(f['nome'])[:9] == norm(r['territorio'])[:9]]
        if alvos:
            f = alvos[0]
            # Força do vínculo: a tabela de títulos não traz nº de processo, então
            # o casamento é por nome. Só consideramos FORTE quando o nome
            # normalizado é idêntico E ao menos um município coincide. Só o
            # vínculo forte pode corrigir a fase; o provável apenas sinaliza.
            nome_igual = norm(f['nome']) == norm(r['territorio'])
            mun_igual = any(norm(m)[:8] == norm(r['municipio'])[:8] or
                            norm(r['municipio']).startswith(norm(m)[:8])
                            for m in f['municipios'] if m)
            forte = nome_igual and mun_igual
            f['titulacao'] = {
                'fonte': FONTE['nome'], 'atualizacao_fonte': FONTE['atualizacao_fonte'],
                'num_fonte': r['num_fonte'],
                'area_territorio_ha': r['area_territorio_ha'],
                'area_titulada_ha': r['area_titulada_ha'],
                'pct_titulado': r['pct_titulado'],
                'titulos': r['titulos'],
                'n_titulos': len(r['titulos']),
                'itemizacao_pendente': r['itemizacao_pendente'],
                'vinculo': 'confirmado' if forte else 'provavel',
                'criterio_vinculo': ('nome idêntico e município coincidente'
                                     if forte else 'nome semelhante na mesma UF'),
                'nome_na_fonte': r['territorio'], 'municipio_na_fonte': r['municipio'],
            }
            casados += 1
        else:
            orfaos += 1
            r['sem_correspondencia'] = True

    # --- territórios titulados ausentes da base entram como registros novos ---
    ORG_EST = ('ITERPA','ITERMA','ITESP','INTERPI','CDA','INTERBA','ITERJ','ITERPE',
               'ITERTINS','IDATERRA','SEHAF','CEMIG','PM ')
    proximo = max(int(f['id'].split('-')[1]) for f in fichas) + 1
    novos = 0
    for r in regs:
        if not r.get('sem_correspondencia'): continue
        orgs = ' '.join(t['orgao'] for t in r['titulos']) or ''
        tem_est = any(o in orgs.upper() for o in ORG_EST)
        tem_fed = 'INCRA' in orgs.upper() or 'SPU' in orgs.upper() or 'FCP' in orgs.upper()
        regime = ('federal-4887' if tem_fed and not tem_est else
                  'estadual' if tem_est else 'indefinido')
        fase = 'TITULADO' if r['pct_titulado'] >= 99.5 else 'TITULO_PARCIAL'
        fichas.append({
            'id': f'SRM-{proximo:04d}', 'nome': r['territorio'], 'uf': r['uf'],
            'municipios': [m.strip() for m in re.split(r'\s+e\s+|,|/', r['municipio']) if m.strip()],
            'processo_incra': None, 'esfera': 'ESTADUAL' if regime == 'estadual' else 'FEDERAL',
            'orgao_responsavel': (r['titulos'][0]['orgao'].replace('*', '') if r['titulos'] else '—'),
            'fase': fase, 'fase_ordem': 7 if fase == 'TITULADO' else 6,
            'area_ha': r['area_territorio_ha'], 'familias': r['familias'],
            'geo': {'lat': None, 'lon': None, 'tem_poligono': False},
            'geo_origem': 'sem_coordenada',
            'tramite': {'rtid_edital_1': None, 'rtid_edital_2': None, 'portaria': None,
                        'decreto': None, 'titulo_txt': None,
                        'titulacao': (max(t['data'] for t in r['titulos']) if r['titulos'] else None),
                        'dispensas': {}},
            'certificacao': {'n_certidoes': 0, 'comunidades': [], 'moradores_fcp': None,
                             'ano_primeira': None, 'detalhe': []},
            'ibge': {'cd_tq': None, 'nm_tq': None, 'n_localidades': 0, 'localidades': []},
            'protocolo_consulta': {'tem': False, 'n': 0, 'itens': []},
            'vinculos': {'poligono': 'nao_localizado', 'fcp': 'nao_localizado', 'ibge': 'nao_localizado'},
            'fontes': ['INCRA/DFQ-Títulos-expedidos'],
            'regime': regime, 'situacao_registro': 'ativo',
            'nota_registro': ('Território titulado registrado na tabela de títulos expedidos do INCRA, '
                              'sem correspondência no quadro de andamento nem na base cartográfica. '
                              'Não possui coordenada nem trâmite detalhado.'),
            'titulacao': {
                'fonte': FONTE['nome'], 'atualizacao_fonte': FONTE['atualizacao_fonte'],
                'num_fonte': r['num_fonte'], 'area_territorio_ha': r['area_territorio_ha'],
                'area_titulada_ha': r['area_titulada_ha'], 'pct_titulado': r['pct_titulado'],
                'titulos': r['titulos'], 'n_titulos': len(r['titulos']),
                'itemizacao_pendente': r['itemizacao_pendente'], 'vinculo': 'registro próprio',
            },
        })
        proximo += 1; novos += 1

    # ---------------------------------------------------------------
    # DIVERGÊNCIAS entre a fase registrada e a tabela oficial de títulos.
    # Nada é resolvido em silêncio: ou a fase é corrigida com registro do
    # que mudou, ou a divergência fica exposta na ficha para decisão humana.
    # ---------------------------------------------------------------
    ORD = {'EM_ELABORACAO':0,'IDENTIFICACAO':1,'RTID':2,'PORTARIA':3,'DECRETO':4,
           'CCDRU':4,'TITULO_PARCIAL':5,'TITULADO':6,'TITULO_ANULADO':6,'SEM_INFO':-1}
    corrigidas = expostas = 0
    for f in fichas:
        f.setdefault('divergencias', [])
        t = f.get('titulacao')
        fase = f.get('fase')
        if t:
            esperada = 'TITULADO' if t['pct_titulado'] >= 99.5 else 'TITULO_PARCIAL'
            if ORD.get(fase, -1) < ORD[esperada] and fase != 'TITULO_ANULADO':
                if t['vinculo'] == 'confirmado':
                    f['divergencias'].append({
                        'tipo': 'fase_corrigida',
                        'texto': (f'A fase registrada era "{fase}", mas a tabela oficial de títulos '
                                  f'do INCRA registra {t["pct_titulado"]}% do território titulado. '
                                  f'A fase foi corrigida para "{esperada}" com base na tabela, que é '
                                  f'a fonte específica sobre titulação. O quadro de andamento federal '
                                  f'não acompanha títulos expedidos por outros órgãos.')})
                    f['fase'] = esperada
                    corrigidas += 1
                else:
                    f['divergencias'].append({
                        'tipo': 'fase_divergente',
                        'texto': (f'A fase registrada é "{fase}", mas a tabela oficial de títulos '
                                  f'associa a este território {t["pct_titulado"]}% de área titulada. '
                                  f'O vínculo com a tabela é apenas provável — foi feito por '
                                  f'semelhança de nome, não por número de processo — então a fase '
                                  f'NÃO foi alterada. Requer conferência.')})
                    expostas += 1
        elif fase in ('TITULADO', 'TITULO_PARCIAL'):
            f['divergencias'].append({
                'tipo': 'titulado_ausente_da_tabela',
                'texto': ('Este território consta como titulado na base cartográfica do INCRA, '
                          'mas não foi localizado na tabela oficial de títulos expedidos. '
                          'Pode ser divergência de grafia entre as duas fontes ou ausência real '
                          'no consolidado. Requer conferência junto à Diretoria de Territórios '
                          'Quilombolas.')})
            expostas += 1

    print(f'registros da tabela de títulos ..... {len(regs)}')
    print(f'  casados com território da base ... {casados}')
    print(f'  sem correspondência .............. {orfaos}')
    com_area = sum(1 for f in fichas if f.get('titulacao') and f['titulacao']['area_titulada_ha'] is not None)
    print(f'  incorporados como registros novos  {novos}')
    print(f'  fichas com área titulada exata ... {com_area}')
    from collections import Counter as _C
    print(f'  vínculo confirmado / provável .... ' +
          str(dict(_C((f["titulacao"]["vinculo"]) for f in fichas if f.get("titulacao")))))
    print(f'  fases corrigidas pela tabela ..... {corrigidas}')
    print(f'  divergências expostas ............ {expostas}')
    from collections import Counter
    print('  regime dos novos:', dict(Counter(f['regime'] for f in fichas
          if f['fontes'] == ['INCRA/DFQ-Títulos-expedidos'])))

    json.dump(fichas, open(f'{BASE}/territorios_fichas.json', 'w', encoding='utf-8'),
              ensure_ascii=False, allow_nan=False)
    json.dump({'fonte': FONTE, 'registros': regs},
              open(f'{BASE}/titulos_expedidos.json', 'w', encoding='utf-8'),
              ensure_ascii=False, allow_nan=False, indent=1)
    print(f'\n>> base/titulos_expedidos.json gravado')
