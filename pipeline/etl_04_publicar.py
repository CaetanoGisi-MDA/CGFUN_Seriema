#!/usr/bin/env python3
"""
Observatório Seriema — etapa 4: publicação da base.
Gera os quatro arquivos que o painel lê. Não toca em curadoria/.
"""
import json, math, os, collections, datetime

I    = os.environ.get('SERIEMA_INTERIM', 'interim')
BASE = os.environ.get('SERIEMA_BASE', 'base')
os.makedirs(BASE, exist_ok=True)

def txt(v, padrao='SEM_INFO'):
    """NaN é verdadeiro em Python: `v or padrao` não basta. Este é o cuidado
    que evita a classe de erro mais comum deste pipeline."""
    if v is None: return padrao
    if isinstance(v, float) and math.isnan(v): return padrao
    s = str(v).strip()
    return padrao if s.lower() in ('', 'nan', 'none', 'nat', 'null') else s

def limpar(o):
    """JSON não aceita NaN/Infinity — nem em valor, nem em chave."""
    if isinstance(o, dict):  return {txt(k, 'SEM_INFO'): limpar(v) for k, v in o.items()}
    if isinstance(o, list):  return [limpar(v) for v in o]
    if isinstance(o, float) and (math.isnan(o) or math.isinf(o)): return None
    if isinstance(o, str) and o.strip() in ('nan', 'NaN', 'None', 'NaT'): return None
    return o

f = json.load(open(f'{I}/fichas_com_protocolo.json', encoding='utf-8'))

def n(v):
    try:
        v = float(v)
        return None if math.isnan(v) else v
    except Exception:
        return None

for x in f:
    x.pop('_k', None)
    x['area_ha'] = n(x.get('area_ha'))
    fam = n(x.get('familias'))
    x['familias'] = int(fam) if fam is not None else None
    for k, v in list(x.get('geo', {}).items()):
        if isinstance(v, float) and math.isnan(v): x['geo'][k] = None
    x['fase']   = txt(x.get('fase'))
    x['esfera'] = txt(x.get('esfera'))
    x['orgao_responsavel'] = txt(x.get('orgao_responsavel'), '—')

resumo = {
    'gerado_em': datetime.date.today().isoformat(),
    'n_territorios': len(f),
    'por_uf':     dict(collections.Counter(x['uf'] for x in f).most_common()),
    'por_fase':   dict(collections.Counter(txt(x.get('fase')) for x in f).most_common()),
    'por_esfera': dict(collections.Counter(txt(x.get('esfera')) for x in f).most_common()),
    'por_orgao':  dict(collections.Counter(txt(x.get('orgao_responsavel')) for x in f).most_common(12)),
    'com_poligono':         sum(1 for x in f if x['geo'].get('tem_poligono')),
    'com_coordenada':       sum(1 for x in f if x['geo'].get('lat')),
    'com_certificacao_fcp': sum(1 for x in f if x['certificacao']['n_certidoes']),
    'com_localidades_ibge': sum(1 for x in f if x['ibge']['n_localidades']),
    'com_protocolo':        sum(1 for x in f if x['protocolo_consulta']['tem']),
    'area_total_ha':   round(sum(x['area_ha'] or 0 for x in f), 2),
    'familias_total':  sum(x['familias'] or 0 for x in f),
    'moradores_fcp_total':    sum(x['certificacao']['moradores_fcp'] or 0 for x in f),
    'localidades_ibge_total': sum(x['ibge']['n_localidades'] for x in f),
    'certidoes_total':        sum(x['certificacao']['n_certidoes'] for x in f),
    'vinculos': {k: dict(collections.Counter(x['vinculos'][k] for x in f))
                 for k in ('poligono', 'fcp', 'ibge')},
}

indice = [{
    'id': x['id'], 'nome': x['nome'], 'uf': x['uf'], 'mun': '; '.join(x['municipios'][:3]),
    'fase': x['fase'], 'lat': x['geo']['lat'], 'lon': x['geo']['lon'],
    'pol': bool(x['geo'].get('tem_poligono')), 'area': x['area_ha'], 'fam': x['familias'],
    'prot': x['protocolo_consulta']['tem'], 'cert': x['certificacao']['n_certidoes'],
    'loc': x['ibge']['n_localidades'], 'esf': txt(x.get('esfera')),
} for x in f if x['geo'].get('lat')]

saidas = {
    'territorios_fichas.json': (limpar(f), None),
    'territorios_indice.json': (limpar(indice), None),
    'resumo.json':             (limpar(resumo), 1),
    'protocolos.json':         (limpar(json.load(open(f'{I}/protocolos.json', encoding='utf-8'))), 1),
}
for nome, (dado, ident) in saidas.items():
    p = f'{BASE}/{nome}'
    json.dump(dado, open(p, 'w', encoding='utf-8'), ensure_ascii=False, allow_nan=False, indent=ident)
    json.loads(open(p, encoding='utf-8').read())        # valida
    print(f'  {nome:26s} {os.path.getsize(p)/1024:8.1f} KB')

print(f"\nbase publicada em ./{BASE}/ — {resumo['n_territorios']} territórios, "
      f"{resumo['com_coordenada']} com coordenada, {resumo['area_total_ha']:,.0f} ha")
print('A pasta curadoria/ não foi tocada.')
