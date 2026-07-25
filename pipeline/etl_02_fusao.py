#!/usr/bin/env python3
"""
Observatório Seriema — Etapa 2: fusão das fontes num registro único de território.

Hierarquia de vínculo (registrada em cada ficha):
  confirmado   nº de processo canônico batendo entre fontes
  provavel     chave tolerante (prefixo do processo) ou nome+UF idênticos normalizados
  nao_localizado
"""
import re, json, warnings, unicodedata
from collections import defaultdict
import pandas as pd, geopandas as gpd
warnings.filterwarnings('ignore')

import os
I = os.environ.get('SERIEMA_INTERIM', 'interim')
poly = gpd.read_file(f'{I}/poly.gpkg')
pdfd = pd.read_parquet(f'{I}/pdf.parquet')
fcp  = pd.read_parquet(f'{I}/fcp.parquet')
ib   = pd.read_parquet(f'{I}/ibge.parquet')
for df in (pdfd, fcp):
    df.replace({'nan': None, 'None': None, '': None}, inplace=True)

def nn(x):  # normaliza p/ chave nome+uf
    return x if isinstance(x, str) and x else None

# =====================================================================
# 1. UNIVERSO DE TERRITÓRIOS  =  processos do PDF  ∪  polígonos
# =====================================================================
terr = {}          # chave interna -> dict
def key_of(pk, pk_loose, nome_norm, uf):
    if pk: return 'P:' + pk
    if pk_loose and nome_norm: return 'L:' + pk_loose
    return 'N:' + (nome_norm or '') + '|' + (uf or '')

# --- 1a. PDF (trilha processual federal, 613) ---
for _, r in pdfd.iterrows():
    k = key_of(r.pk, r.pk_loose, r.nome_norm, r.uf)
    terr[k] = {
        'nome': (r.comunidade or '').strip(),
        'nome_norm': r.nome_norm, 'uf': r.uf,
        'municipios': [m.strip() for m in re.split(r'\s+e\s+|,|/', str(r.municipio or '')) if m.strip()],
        'municipio_txt': (r.municipio or '').strip(),
        'proc_incra': (r.proc or '').strip(), 'pk': r.pk, 'pk_loose': r.pk_loose,
        'esfera': 'FEDERAL', 'responsavel': 'INCRA',
        'fase': r.fase_pdf,
        'area_ha': r.area_ha, 'familias': r.familias,
        'tramite': {
            'rtid_edital_1': r.rtid1_dt, 'rtid_edital_2': r.rtid2_dt,
            'portaria': r.portaria_dt, 'retificacao_portaria': r.ret_portaria_dt,
            'decreto': r.decreto_dt,
            'titulo_txt': nn(r.titulo_txt),
        },
        'fontes': ['INCRA/PDF-andamento'],
        '_pdf': True, '_poly': False,
    }

# --- 1b. polígonos (439; inclui esfera estadual, ausente do PDF) ---
idx_pk    = {v['pk']: k for k, v in terr.items() if v['pk']}
idx_loose = defaultdict(list)
idx_nome  = defaultdict(list)
for k, v in terr.items():
    if v['pk_loose']: idx_loose[v['pk_loose']].append(k)
    if v['nome_norm']: idx_nome[(v['nome_norm'], v['uf'])].append(k)

geoms = {}
for _, r in poly.iterrows():
    k = None; via = None
    if r.pk and r.pk in idx_pk:
        k, via = idx_pk[r.pk], 'confirmado'
    elif r.pk_loose and idx_loose.get(r.pk_loose):
        k, via = idx_loose[r.pk_loose][0], 'provavel'
    elif idx_nome.get((r.nome_norm, r.uf)):
        k, via = idx_nome[(r.nome_norm, r.uf)][0], 'provavel'
    if k is None:                                    # território só no shapefile
        k = key_of(r.pk, r.pk_loose, r.nome_norm, r.uf)
        if k in terr: k = k + '#shp'
        terr[k] = {
            'nome': r.nome_incra, 'nome_norm': r.nome_norm, 'uf': r.uf,
            'municipios': [m.strip() for m in re.split(r'\s+e\s+|,|/', str(r.municipio or '')) if m.strip()],
            'municipio_txt': r.municipio,
            'proc_incra': (r.proc or ''), 'pk': r.pk or '', 'pk_loose': r.pk_loose or '',
            'esfera': r.esfera, 'responsavel': r.responsavel,
            'fase': r.fase_shp, 'area_ha': r.area_ha_shp, 'familias': r.familias_shp,
            'tramite': {'rtid_edital_1': None, 'rtid_edital_2': None, 'portaria': None,
                        'decreto': r.dt_decreto_shp, 'titulo_txt': None},
            'fontes': [], '_pdf': False, '_poly': True,
        }
        via = 'proprio'
    t = terr[k]
    t['_poly'] = True
    t['fontes'].append('INCRA/Acervo-Fundiário')
    t['vinculo_poligono'] = via
    t['geo'] = {'lat': float(r.lat), 'lon': float(r.lon),
                'area_geom_ha': float(r.area_geom_ha) if pd.notna(r.area_geom_ha) else None,
                'tem_poligono': True}
    if t.get('area_ha') is None and pd.notna(r.area_ha_shp): t['area_ha'] = float(r.area_ha_shp)
    if t.get('familias') is None and pd.notna(r.familias_shp): t['familias'] = int(r.familias_shp)
    if not t.get('esfera') or t['esfera'] == 'FEDERAL':
        if r.esfera and r.esfera != 'FEDERAL': t['esfera'] = r.esfera
    if r.responsavel and r.responsavel != 'INCRA': t['responsavel'] = r.responsavel
    if t['tramite'].get('decreto') is None: t['tramite']['decreto'] = r.dt_decreto_shp
    if r.dt_titulacao_shp: t['tramite']['titulacao'] = r.dt_titulacao_shp
    if not t.get('fase'): t['fase'] = r.fase_shp
    geoms[k] = r.geometry

print(f'universo de territórios ......... {len(terr)}')
print(f'   com polígono ................. {sum(1 for v in terr.values() if v["_poly"])}')
print(f'   só trilha processual ......... {sum(1 for v in terr.values() if not v["_poly"])}')

# =====================================================================
# 2. FCP — certificação, por processo INCRA
# =====================================================================
idx_pk    = {v['pk']: k for k, v in terr.items() if v['pk']}
idx_loose = defaultdict(list); idx_nome = defaultdict(list)
for k, v in terr.items():
    if v['pk_loose']: idx_loose[v['pk_loose']].append(k)
    if v['nome_norm']: idx_nome[(v['nome_norm'], v['uf'])].append(k)

cert = defaultdict(lambda: {'certidoes': [], 'via': None})
fk_to_terr = {}                       # processo FCP -> chave do território
for _, r in fcp.iterrows():
    k = None; via = None
    if r.pk and r.pk in idx_pk:
        k, via = idx_pk[r.pk], 'confirmado'
    elif r.pk_loose and idx_loose.get(r.pk_loose):
        k, via = idx_loose[r.pk_loose][0], 'provavel'
    elif idx_nome.get((r.nome_norm, r.uf)):
        k, via = idx_nome[(r.nome_norm, r.uf)][0], 'provavel'
    if k is None: continue
    c = cert[k]
    c['certidoes'].append({
        'comunidade': r.comunidade, 'municipio': r.municipio,
        'cd_ibge': r.cd_ibge, 'proc_fcp': r.proc_fcp,
        'portaria': r.portaria, 'dou': r.dt_portaria_iso,
        'ano': int(r.ano_cert) if pd.notna(r.ano_cert) else None,
        'moradores': int(r.n_moradores) if pd.notna(r.n_moradores) else None,
        'urb_rural': r.urb_rural, 'etapa_fcp': r.etapa,
    })
    if via == 'confirmado' or c['via'] is None: c['via'] = via
    if r.fk: fk_to_terr[r.fk] = k

conf = sum(1 for v in cert.values() if v['via'] == 'confirmado')
print(f'territórios com certificação FCP  {len(cert)}  ({conf} confirmados por código, {len(cert)-conf} prováveis)')

# =====================================================================
# 3. IBGE — localidades  (duas rotas)
#    A) localidade --proc FCP--> certidão --proc INCRA--> território  (código)
#    B) nome do TQ delimitado == nome do território (+UF)             (nome)
# =====================================================================
idx_tqnome = defaultdict(list)
for k, v in terr.items():
    if v['nome_norm']: idx_tqnome[(v['nome_norm'], v['uf'])].append(k)

loc = defaultdict(lambda: {'localidades': [], 'via': set(), 'cd_tq': set(), 'nm_tq': set()})
for _, r in ib.iterrows():
    k = None; via = None
    if r.fk and r.fk in fk_to_terr:
        k, via = fk_to_terr[r.fk], 'confirmado'
    elif pd.notna(r.nome_norm_tq) and idx_tqnome.get((r.nome_norm_tq, r.uf)):
        k, via = idx_tqnome[(r.nome_norm_tq, r.uf)][0], 'provavel'
    if k is None: continue
    d = loc[k]
    d['localidades'].append({
        'nome': r.nm_cq, 'municipio': r.nm_munic, 'cd_munic': r.cd_munic,
        'lat': None if pd.isna(r.lat) else round(float(r.lat), 6),
        'lon': None if pd.isna(r.lon) else round(float(r.lon), 6),
        'aglomerado': r.nm_aglom, 'idcq': r.idcq,
    })
    d['via'].add(via)
    if pd.notna(r.cd_tq): d['cd_tq'].add(str(r.cd_tq)); d['nm_tq'].add(r.nm_tq)

print(f'territórios com localidades IBGE  {len(loc)}  '
      f'({sum(1 for v in loc.values() if "confirmado" in v["via"])} com rota por código)')

# =====================================================================
# 4. MONTA AS FICHAS
# =====================================================================
FASE_ORD = {'EM_ELABORACAO':0,'IDENTIFICACAO':1,'RTID':2,'PORTARIA':3,'DECRETO':4,
            'CCDRU':5,'TITULO_PARCIAL':6,'TITULADO':7,'TITULO_ANULADO':8}
fichas = []
for i, (k, v) in enumerate(sorted(terr.items(), key=lambda x: (str(x[1]['uf'] or 'ZZ'), str(x[1]['nome'] or ''))), 1):
    c = cert.get(k); l = loc.get(k)
    moradores = sum(x['moradores'] or 0 for x in c['certidoes']) if c else 0
    anos = [x['ano'] for x in c['certidoes'] if x['ano']] if c else []
    f = {
        'id': f'SRM-{i:04d}',
        'nome': v['nome'], 'uf': v['uf'],
        'municipios': v['municipios'] or ([v['municipio_txt']] if v['municipio_txt'] else []),
        'processo_incra': v['proc_incra'] or None,
        'esfera': v['esfera'], 'orgao_responsavel': v['responsavel'],
        'fase': v['fase'], 'fase_ordem': FASE_ORD.get(v['fase'], -1),
        'area_ha': v['area_ha'], 'familias': v['familias'],
        'geo': v.get('geo', {'lat': None, 'lon': None, 'tem_poligono': False}),
        'tramite': v['tramite'],
        'certificacao': {
            'n_certidoes': len(c['certidoes']) if c else 0,
            'comunidades': [x['comunidade'] for x in c['certidoes']] if c else [],
            'moradores_fcp': moradores or None,
            'ano_primeira': min(anos) if anos else None,
            'detalhe': c['certidoes'] if c else [],
        },
        'ibge': {
            'cd_tq': sorted(l['cd_tq'])[0] if l and l['cd_tq'] else None,
            'nm_tq': sorted(l['nm_tq'])[0] if l and l['nm_tq'] else None,
            'n_localidades': len(l['localidades']) if l else 0,
            'localidades': l['localidades'] if l else [],
        },
        'protocolo_consulta': None,
        'vinculos': {
            'poligono': v.get('vinculo_poligono', 'proprio' if v['_poly'] else 'nao_localizado'),
            'fcp': c['via'] if c else 'nao_localizado',
            'ibge': ('confirmado' if l and 'confirmado' in l['via']
                     else 'provavel' if l else 'nao_localizado'),
        },
        'fontes': sorted(set(v['fontes'])),
        '_k': k,
    }
    fichas.append(f)

# ---- ponto no mapa: centroide do polígono, senão média das localidades IBGE ----
sem_ponto = 0
for f in fichas:
    if f['geo'].get('lat') is None:
        pts = [(x['lat'], x['lon']) for x in f['ibge']['localidades'] if x['lat']]
        if pts:
            f['geo'] = {'lat': round(sum(p[0] for p in pts)/len(pts), 6),
                        'lon': round(sum(p[1] for p in pts)/len(pts), 6),
                        'area_geom_ha': None, 'tem_poligono': False}
            f['geo_origem'] = 'media_localidades_ibge'
        else:
            sem_ponto += 1
            f['geo_origem'] = 'sem_coordenada'
    else:
        f['geo_origem'] = 'centroide_poligono_incra'

print(f'\nfichas geradas .................. {len(fichas)}')
print(f'   com coordenada ............... {len(fichas)-sem_ponto}  '
      f'({sum(1 for f in fichas if f["geo_origem"]=="centroide_poligono_incra")} por polígono, '
      f'{sum(1 for f in fichas if f["geo_origem"]=="media_localidades_ibge")} por localidades IBGE)')
print(f'   sem coordenada ............... {sem_ponto}')

json.dump(fichas, open(f'{I}/fichas_pre.json','w'), ensure_ascii=False)
gpd.GeoDataFrame({'k': list(geoms.keys())}, geometry=list(geoms.values()), crs=poly.crs)\
   .to_file(f'{I}/geoms.gpkg', driver='GPKG')
print(f'\n>> fichas preliminares em {I}/fichas_pre.json')
