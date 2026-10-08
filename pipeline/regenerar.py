"""
Observatório Seriema — regeneração do índice e do resumo.

Chamado ao final das etapas 6 e 7 (e de qualquer etapa futura que acrescente
ou altere registros). Existe como módulo próprio porque o recálculo já foi
esquecido duas vezes: em julho/2026 o resumo saiu sem os campos de titulação,
e até outubro/2026 os contadores gerais (com_coordenada, com_poligono,
area_total_ha, por_orgao...) ficavam congelados no valor da etapa 4, antes de
as etapas 5 e 6 acrescentarem registros.

Todos os contadores são calculados sobre os registros ATIVOS (fora fragmentos
cartográficos e duplicatas prováveis). O bloco certidoes_sem_processo, gerado
pela etapa 5, é preservado como está.
"""
import json, datetime
from collections import Counter

FASES_TITULO = ('TITULADO', 'TITULO_PARCIAL')

def _indice(fichas):
    return [{'id': x['id'], 'nome': x['nome'], 'uf': x['uf'], 'mun': '; '.join(x['municipios'][:3]),
             'fase': x['fase'], 'lat': x['geo'].get('lat'), 'lon': x['geo'].get('lon'),
             'pol': bool(x['geo'].get('tem_poligono')), 'area': x['area_ha'], 'fam': x['familias'],
             'prot': x['protocolo_consulta']['tem'], 'cert': x['certificacao']['n_certidoes'],
             'loc': x['ibge']['n_localidades'], 'esf': x['esfera'], 'reg': x['regime'],
             'sit': x['situacao_registro'], 'div': len(x.get('divergencias') or [])} for x in fichas]

def regenerar(fichas, base, fonte_titulacao):
    json.dump(_indice(fichas), open(f'{base}/territorios_indice.json', 'w', encoding='utf-8'),
              ensure_ascii=False, allow_nan=False)

    A = [x for x in fichas if x['situacao_registro'] == 'ativo']
    r = json.load(open(f'{base}/resumo.json', encoding='utf-8'))
    r.update({
        'gerado_em': datetime.date.today().isoformat(),
        'registros_totais': len(fichas),
        'n_territorios': len(A),
        'fragmentos': sum(1 for x in fichas if x['situacao_registro'] == 'fragmento'),
        'duplicatas': sum(1 for x in fichas if x['situacao_registro'] == 'duplicata_provavel'),
        'por_uf':     dict(Counter(x['uf'] for x in A).most_common()),
        'por_fase':   dict(Counter(x['fase'] for x in A).most_common()),
        'por_esfera': dict(Counter(x['esfera'] for x in A).most_common()),
        'por_orgao':  dict(Counter(x['orgao_responsavel'] for x in A).most_common(12)),
        'por_regime': dict(Counter(x['regime'] for x in A).most_common()),
        'por_fase_federal':  dict(Counter(x['fase'] for x in A if x['regime'].startswith('federal')).most_common()),
        'por_fase_estadual': dict(Counter(x['fase'] for x in A if x['regime'] == 'estadual').most_common()),
        'com_poligono':         sum(1 for x in A if x['geo'].get('tem_poligono')),
        'com_coordenada':       sum(1 for x in A if x['geo'].get('lat') is not None),
        'com_certificacao_fcp': sum(1 for x in A if x['certificacao']['n_certidoes']),
        'com_localidades_ibge': sum(1 for x in A if x['ibge']['n_localidades']),
        'com_protocolo':        sum(1 for x in A if x['protocolo_consulta']['tem']),
        'area_total_ha':   round(sum(x['area_ha'] or 0 for x in A), 2),
        'familias_total':  sum(x['familias'] or 0 for x in A),
        'moradores_fcp_total':    sum(x['certificacao']['moradores_fcp'] or 0 for x in A),
        'localidades_ibge_total': sum(x['ibge']['n_localidades'] for x in A),
        'certidoes_total':        sum(x['certificacao']['n_certidoes'] for x in A),
        'vinculos': {k: dict(Counter(x['vinculos'][k] for x in A)) for k in ('poligono', 'fcp', 'ibge')},
        'divergencias': dict(Counter(d['tipo'] for x in A for d in (x.get('divergencias') or []))),
    })
    fed = [x for x in A if x['regime'].startswith('federal')]
    est = [x for x in A if x['regime'] == 'estadual']
    def area_tit(g): return round(sum((x.get('titulacao') or {}).get('area_titulada_ha') or 0 for x in g), 2)
    r['titulacao'] = {
        'fonte': fonte_titulacao,
        'federal':  {'territorios': sum(1 for x in fed if x['fase'] in FASES_TITULO), 'area_titulada_ha': area_tit(fed)},
        'estadual': {'territorios': sum(1 for x in est if x['fase'] in FASES_TITULO), 'area_titulada_ha': area_tit(est)},
        'itemizacao_pendente': sum(1 for x in A if (x.get('titulacao') or {}).get('itemizacao_pendente')),
    }
    com_iterpa = [x for x in A if x.get('iterpa')]
    if com_iterpa:
        r['iterpa'] = {
            'territorios': len(com_iterpa),
            'titulos': sum(len(x['iterpa']['registros']) for x in com_iterpa),
            'area_decretada_ha': round(sum(g['area_decreto_ha'] or 0 for x in com_iterpa
                                           for g in x['iterpa']['registros']), 4),
            'com_dados_cartoriais': sum(1 for x in com_iterpa
                                        if any(g['matricula'] for g in x['iterpa']['registros'])),
            'por_vinculo': dict(Counter(x['iterpa']['vinculo'] for x in com_iterpa)),
        }
    json.dump(r, open(f'{base}/resumo.json', 'w', encoding='utf-8'),
              ensure_ascii=False, allow_nan=False, indent=1)
    return r
