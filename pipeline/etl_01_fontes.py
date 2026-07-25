#!/usr/bin/env python3
"""
Observatório Seriema — Etapa 1 de ingestão
Normaliza as quatro fontes e grava tabelas intermediárias em /home/claude/seriema/interim
"""
import re, json, unicodedata, warnings
import pandas as pd, geopandas as gpd
warnings.filterwarnings('ignore')

import os, sys
# Todos os arquivos-fonte ficam em ./entrada (veja o README para o que baixar e onde).
UP  = os.environ.get('SERIEMA_ENTRADA', 'entrada')
OUT = os.environ.get('SERIEMA_INTERIM', 'interim')
os.makedirs(OUT, exist_ok=True)

NECESSARIOS = {
    'A_reas_de_Quilombolas.shp':      'polígonos dos territórios (INCRA — Acervo Fundiário)',
    'territoriosquilombolas.pdf':     'andamento dos processos (INCRA — governança fundiária)',
    'TABELA_DE_CRQ_CERTIFICADAS.xlsx':'comunidades certificadas (Fundação Cultural Palmares)',
    'BR_LQs_CD2022.csv':              'localidades quilombolas 2022 (IBGE)',
}
faltam = [f'  - {n}  →  {d}' for n, d in NECESSARIOS.items() if not os.path.exists(os.path.join(UP, n))]
if faltam:
    print(f'Faltam arquivos em ./{UP}/ :', *faltam, sep='\n')
    print('\nO README explica onde baixar cada um. Nomes precisam bater exatamente.')
    sys.exit(1)

# ---------- utilidades ----------
def strip_ac(s):
    if not isinstance(s, str): return ''
    return unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode()

def norm_nome(s):
    """Normaliza nome de território para casamento."""
    s = strip_ac(s).upper()
    s = re.sub(r'^(TQ|TERRITORIO QUILOMBOLA|COMUNIDADE QUILOMBOLA|QUILOMBO)[\s_]+', '', s)
    s = s.replace('&', ' E ')
    s = re.sub(r'\bSTO\b', 'SANTO', s); s = re.sub(r'\bSTA\b', 'SANTA', s)
    s = re.sub(r'\bS\.\s*', 'SAO ', s)
    s = re.sub(r'\bN\.?\s*S\.?\b', 'NOSSA SENHORA', s)
    s = re.sub(r'\b3\b', 'TRES', s); s = re.sub(r'\b2\b', 'DOIS', s)
    s = re.sub(r'[^A-Z0-9]+', ' ', s)
    # remove parênteses/detalhamentos já eliminados; corta em barra
    return re.sub(r'\s+', ' ', s).strip()

def proc_digits(s):
    """Só os dígitos do nº de processo. Formato canônico tem 17 dígitos."""
    d = re.sub(r'\D', '', str(s) if s is not None else '')
    return d

def proc_key(s):
    d = proc_digits(s)
    return d if len(d) == 17 else ''

def proc_key_loose(s):
    """Chave tolerante: prefixo(5)+corpo(6) — pega erros de dígito no ano/verificador."""
    d = proc_digits(s)
    return d[:11] if len(d) >= 11 else ''

def to_float(x):
    if x is None: return None
    s = str(x).strip()
    if not s or s in ('-', 'nan'): return None
    s = s.replace('.', '').replace(' ', '').replace(',', '.')
    try: return float(s)
    except: return None

def to_int(x):
    v = to_float(x)
    return int(v) if v is not None else None

DATE_RE = re.compile(r'(\d{1,2})[/\.](\d{1,2})[/\.](\d{2,4})')
def to_date(x):
    """Devolve ISO ou None. Tolera lixo ('-', '28/01/205', '20/092018')."""
    if x is None: return None
    s = str(x).strip()
    if not s or s in ('-', 'nan', 'NaT'): return None
    if 'Não precisa' in s or 'Nao precisa' in s: return None
    m = DATE_RE.search(s.replace('/', '/'))
    if not m:
        m2 = re.search(r'(\d{2})(\d{2})(\d{4})', re.sub(r'\D', '', s))
        if not m2: return None
        d, mo, y = m2.groups()
    else:
        d, mo, y = m.groups()
    try:
        d, mo, y = int(d), int(mo), int(y)
    except: return None
    if y < 100: y += 2000
    if y < 1900 or y > 2100: return None      # descarta '205', '222'
    if not (1 <= mo <= 12) or not (1 <= d <= 31): return None
    return f'{y:04d}-{mo:02d}-{d:02d}'

FASE_MAP = {
    'RTID': 'RTID', 'RTID PUBLICADO': 'RTID', 'ABERTURA RTID': 'RTID',
    'IDENTIFICACAO': 'IDENTIFICACAO', 'INCRA': None,
    'PORTARIA': 'PORTARIA', 'PORTARIA NO DOU': 'PORTARIA',
    'DECRETO': 'DECRETO', 'DECRETO NO DOU': 'DECRETO',
    'TITULADO': 'TITULADO', 'TITULO PARCIAL': 'TITULO_PARCIAL',
    'TITULACAO PARCIAL': 'TITULO_PARCIAL', 'TITULO ANULADO': 'TITULO_ANULADO',
    'CCDRU': 'CCDRU', 'CDRU': 'CCDRU',
}
def norm_fase(x):
    if x is None: return None
    k = re.sub(r'\s+', ' ', strip_ac(str(x)).upper().strip())
    if k in ('', 'NAN', 'NONE', 'NAT', 'NULL'): return None
    return FASE_MAP.get(k, k)

# =========================================================
# 1. INCRA — polígonos
# =========================================================
g = gpd.read_file(f'{UP}/A_reas_de_Quilombolas.shp')
g['geometry'] = g.geometry.buffer(0)                       # corrige a inválida
gm = g.to_crs(5880)
g['area_geom_ha'] = (gm.area / 10000).round(4)
cen = g.geometry.centroid
g['lat'] = cen.y.round(6); g['lon'] = cen.x.round(6)

poly = pd.DataFrame({
    'nome_incra':  g.nm_comunid.str.strip(),
    'nome_norm':   g.nm_comunid.map(norm_nome),
    'municipio':   g.nm_municip.fillna('').str.strip(),
    'uf':          g.cd_uf.str.strip().str.upper(),
    'proc':        g.nr_process,
    'pk':          g.nr_process.map(proc_key),
    'pk_loose':    g.nr_process.map(proc_key_loose),
    'sr':          g.cd_sr.str.strip(),
    'esfera':      g.esfera.map(lambda x: strip_ac(str(x)).upper().replace('FEDEERAL','FEDERAL') if pd.notna(x) else None),
    'responsavel': g.responsave.str.strip(),
    'fase_shp':    g.fase.map(norm_fase),
    'area_ha_shp': g.nr_area_ha,
    'area_geom_ha':g.area_geom_ha,
    'familias_shp':g.nr_familia.map(to_int),
    'dt_titulacao_shp': g.dt_titulac.map(to_date),
    'dt_decreto_shp':   g.dt_decreto.map(to_date),
    'lat': g.lat, 'lon': g.lon,
})
poly['geometry'] = g.geometry
poly = gpd.GeoDataFrame(poly, geometry='geometry', crs=g.crs)
print(f'[1] polígonos INCRA .............. {len(poly):>5}  ({poly.pk.ne("").sum()} com nº de processo válido)')

# =========================================================
# 2. INCRA — PDF de andamento dos processos
# =========================================================
import pdfplumber
raw = []
with pdfplumber.open(f'{UP}/territoriosquilombolas.pdf') as pdf:
    for pg in pdf.pages:
        for tb in (pg.extract_tables() or []):
            raw.extend([[(c or '').strip() for c in r] for r in tb])

COLS = ['sr_col','seq','proc','comunidade','municipio','area','familias',
        'rtid1','rtid2','ret1','ret2','portaria','ret_portaria','decreto','titulo']
recs = []
for r in raw:
    if len(r) < 15: continue
    if not re.match(r'^\d{1,3}$', r[1] or ''): continue
    d = dict(zip(COLS, r[:15]))
    recs.append(d)
pdf_df = pd.DataFrame(recs)

# UF a partir do prefixo do processo, calibrado pelos polígonos
pref = poly[poly.pk.ne('')].assign(p=lambda d: d.pk.str[:5])
pref_map = (pref.groupby('p').uf.agg(lambda s: s.value_counts().index[0])).to_dict()
EXTRA = {'54700':'GO','54105':'PA','54501':'PA','54113':'PA','54141':'PE',
         '54570':'SE','54000':None,'54360':'AL','54270':'AM','54350':'AP',
         '54160':'BA','54130':'CE','54150':'GO','54340':'ES','54230':'MA',
         '54170':'MG','54290':'MS','54240':'MT','54100':'PA','54320':'PB',
         '54140':'PE','54380':'PI','54200':'PR','54180':'RJ','54330':'RN',
         '54300':'RO','54220':'RS','54210':'SC','54370':'SE','54190':'SP','54400':'TO'}
for k, v in EXTRA.items(): pref_map.setdefault(k, v)

pdf_df['pk']       = pdf_df.proc.map(proc_key)
pdf_df['pk_loose'] = pdf_df.proc.map(proc_key_loose)
pdf_df['uf']       = pdf_df.pk_loose.str[:5].map(pref_map)
pdf_df['nome_norm']= pdf_df.comunidade.map(norm_nome)
pdf_df['area_ha']  = pdf_df.area.map(to_float)
pdf_df['familias'] = pdf_df.familias.map(to_int)
for c in ['rtid1','rtid2','ret1','ret2','portaria','ret_portaria','decreto']:
    pdf_df[c+'_dt'] = pdf_df[c].map(to_date)

def has(v):
    return v is not None and not (isinstance(v, float) and pd.isna(v)) and str(v).strip() not in ('', 'nan', 'None')

def fase_pdf(r):
    t = str(r.titulo).strip()
    if has(r.titulo):
        if 'parcial' in strip_ac(t).lower(): return 'TITULO_PARCIAL'
        if 'anulado' in strip_ac(t).lower(): return 'TITULO_ANULADO'
        return 'TITULADO'
    if has(r.decreto_dt): return 'DECRETO'
    if has(r.portaria_dt): return 'PORTARIA'
    if has(r.rtid1_dt): return 'RTID'
    return 'EM_ELABORACAO'
pdf_df['fase_pdf'] = pdf_df.apply(fase_pdf, axis=1)
pdf_df['titulo_txt'] = pdf_df.titulo.str.strip()
pdf_df['em_elaboracao'] = pdf_df.apply(
    lambda r: any('Elabora' in str(r[c]) for c in ['rtid1','rtid2','area','portaria']), axis=1)
print(f'[2] processos no PDF ............. {len(pdf_df):>5}  ({pdf_df.pk.ne("").sum()} com nº válido, '
      f'{pdf_df.uf.notna().sum()} com UF resolvida)')

# =========================================================
# 3. FCP — certidões
# =========================================================
fcp = pd.read_excel(f'{UP}/TABELA_DE_CRQ_CERTIFICADAS.xlsx', 'CERTIFICADAS', header=0)
fcp.columns = ['regiao','uf','municipio','cd_ibge','comunidade','proc_fcp','dt_abertura',
               'livro','registro','folha','portaria','dt_portaria','retificacao',
               'proc_incra','etapa','n_comunidades','n_moradores','urb_rural',
               'ano_cert','porta','cont']
fcp['uf'] = fcp.uf.astype(str).str.strip().str.upper()
fcp['comunidade'] = fcp.comunidade.astype(str).str.strip()
fcp['nome_norm']  = fcp.comunidade.map(norm_nome)
fcp['pk']         = fcp.proc_incra.map(proc_key)
fcp['pk_loose']   = fcp.proc_incra.map(proc_key_loose)
fcp['fk']         = fcp.proc_fcp.map(lambda s: proc_digits(s) if len(proc_digits(s)) >= 15 else '')
fcp['n_moradores']= fcp.n_moradores.map(to_int)
fcp['dt_portaria_iso'] = fcp.dt_portaria.map(lambda x: to_date(x) if not isinstance(x, pd.Timestamp) else x.date().isoformat())
print(f'[3] certidões FCP ................ {len(fcp):>5}  ({fcp.pk.ne("").sum()} c/ nº INCRA canônico, '
      f'{fcp.pk_loose.ne("").sum()} c/ chave tolerante)')

# =========================================================
# 4. IBGE — localidades quilombolas
# =========================================================
ib = pd.read_csv(f'{UP}/BR_LQs_CD2022.csv', sep=';', encoding='utf-8-sig', dtype=str)
ib.columns = ['cd_uf','nm_uf','uf','cd_munic','nm_munic','idcq','ocorrencia','cd_lq',
              'prefixo','nm_cq','cd_aglom','nm_aglom','cd_tq','nm_tq','p_fcp','lat','lon']
ib['fk'] = ib.p_fcp.map(lambda s: proc_digits(s) if len(proc_digits(s)) >= 15 else '')
ib['lat'] = pd.to_numeric(ib.lat, errors='coerce')
ib['lon'] = pd.to_numeric(ib.lon, errors='coerce')
ib['nome_norm_tq'] = ib.nm_tq.map(norm_nome)
print(f'[4] localidades IBGE ............. {len(ib):>5}  ({ib.cd_tq.notna().sum()} ligadas a TQ delimitado, '
      f'{ib.fk.ne("").sum()} com processo FCP)')

# ---------- grava intermediários ----------
poly.to_file(f'{OUT}/poly.gpkg', driver='GPKG')
for c in pdf_df.columns:
    if pdf_df[c].dtype == object: pdf_df[c] = pdf_df[c].astype(str)
pdf_df.to_parquet(f'{OUT}/pdf.parquet')
for c in fcp.columns:
    if fcp[c].dtype == object: fcp[c] = fcp[c].astype(str)
fcp.to_parquet(f'{OUT}/fcp.parquet')
ib.to_parquet(f'{OUT}/ibge.parquet')
print(f'\n>> intermediários gravados em {OUT}')
