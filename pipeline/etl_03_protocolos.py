#!/usr/bin/env python3
"""Etapa 3 — catálogo de protocolos de consulta e vinculação às fichas."""
import json, re, unicodedata
from difflib import SequenceMatcher

B = 'https://observatorio.direitosocioambiental.org/'
FONTE_OBS = 'Observatório de Protocolos Comunitários (OPCPLI/CEPEDIS-UFGD)'

# (nome do território p/ casamento, UF, ano, título, slug)
P = [
 ("Córrego do Alexandre","ES",2025,"Protocolo de Consulta Prévia, Livre, Informada, de Consentimento e Veto da Comunidade Quilombola de Córrego do Alexandre, Sapê do Norte, Conceição da Barra","protocolo-de-consulta-previa-livre-informada-de-consentimento-e-veto-da-comunidade-quilombola-de-corrego-do-alexandre-sape-do-norte-conceicao-da-barra-espirito-santo-2025/"),
 ("Saco Barreiro","MG",2024,"Protocolo de Consulta livre, prévia e informada do Quilombo Saco Barreiro","protocolo-de-consulta-livre-previa-e-informada-do-quilombo-saco-barreiro-2024/"),
 ("Córrego Frio","ES",2024,"Protocolo de Consulta Livre, Prévia e Informada do Quilombo Córrego Frio","protocolo-de-consulta-livre-previa-e-informada-do-quilombo-corrego-frio-2024/"),
 ("Morro Alto","RS",2024,"Protocolo de Consulta Prévia, Livre, Informada e de boa-fé da Comunidade Quilombola de Morro Alto","protocolo-de-consulta-previa-livre-informada-e-de-boa-fe-da-comunidade-quilombola-de-morro-alto-2024/"),
 ("Vila Nova","RS",2025,"Protocolo de Consulta Prévia, Livre e Informada Quilombo Vila Nova (São José do Norte)","protocolo-de-consulta-previa-livre-e-informada-quilombo-vila-nova/"),
 ("Córrego da Angélica","ES",2025,"Protocolo de Consulta – Comunidade Quilombola Córrego da Angélica","protocolo-de-consulta-comunidade-quilombola-corrego-da-angelica/"),
 ("Córrego Narciso do Meio","ES",2025,"Protocolo de Consulta e Consentimento Livre e Informado da Comunidade Quilombola Córrego Narciso do Meio","protocolo-de-consulta-e-consentimento-livre-e-informado-da-comunidade-quilombola-corrego-narciso-do-meio-2025/"),
 ("Manzo Ngunzo Kaiango","MG",2025,"Protocolo de Consulta Prévia, Livre e Informada do Quilombo Manzo Ngunzo Kaiango, Senzala de Pai Benedito","protocolo-de-consulta-previa-livre-e-informada-do-quilombo-manzo-ngunzo-kaiango-senzala-de-pai-benedito-2025/"),
 ("Baú","MG",2025,"Protocolo de Consulta Prévia, Livre e Informada da Comunidade Quilombola Baú de Araçuaí/MG","protocolo-de-consulta-previa-livre-e-informada-da-comunidade-quilombola-bau-de-aracuai-mg/"),
 ("Rio Genipaúba","PA",2023,"Protocolo Comunitário-Autônomo da Comunidade Quilombola do Rio Genipaúba (Abaetetuba)","protocolo-comunitario-autonomo-de-consulta-e-consentimento-previo-livre-informado-adequado-de-boa-fe-e-de-veto-da-comunidade-quilombola-do-rio-genipauba-municipio-de-abaetetuba-estado-do-para-a/"),
 ("Rio Tauerá-Açu","PA",2024,"Protocolo Comunitário Autônomo do Território Quilombola do Rio Tauerá-Açu (Abaetetuba)","protocolo-comunitario-autonomo-do-territorio-quilombola-do-rio-tauera-acu-municipio-de-abaetetuba-estado-do-para-amazonia-brasileira-2024/"),
 ("Córrego Frio","ES",2024,"Protocolo de Consulta Livre Prévia e Informada do Quilombo Córrego Frio","protocolo-de-consulta-livre-previa-e-informada-do-quilombo-corrego-frio/"),
 ("Umburanas","BA",2024,"Protocolo de Consulta Prévia, Livre, Informada e de Boa-Fé do Território Quilombola das Umburanas","protocolo-de-consulta-previa-livre-informada-e-de-boa-fe-da-do-territorio-quilombola-das-umburanas/"),
 ("Brejão dos Negros","SE",2023,"Protocolo de Consulta Território Quilombola Brejão dos Negros","protocolo-de-consulta-territorio-quilombola-brejao-dos-negros-2023/"),
 ("Joaquim Maria","MA",2023,"Protocolo Quilombola de Consulta e Consentimento do Território de Joaquim Maria – Miranda do Norte","protocolo-quilombola-de-consulta-e-consentimento-previo-libre-e-informado-de-boa-fe-do-territorio-de-joaquim-maria-miranda-do-norte-2023/"),
 ("Pedrinhas","MA",2023,"Protocolo dos Territórios Quilombolas de Pedrinhas 1, Pedrinhas 2, Queluz, Capaúba, Teso Grande, Cumbi e Centro de Isidoro (Anajatuba)","protocolo-de-consulta-e-consentimento-previo-livre-e-informado-de-boa-fe-dos-territorios-quilombolas-de-pedrinhas-1-pedrinhas-2-queluz-capauba-teso-grande-cumbi-e-centro-de-isidoro-no-municipio/"),
 ("Subaé","BA",2023,"Protocolo de Consulta Prévia, Livre e Informada e de Consentimento do Território Quilombola Subaé","protocolo-de-consulta-previa-livre-e-informada-e-de-consentimento-do-territorio-quilombola-subae-2023/"),
 ("Oiteiro dos Nogueiras","MA",2022,"Protocolo de Consulta das Comunidades do Território Oiteiro dos Nogueiras e São José dos Matos","protocolo-de-consulta-das-comunidades-do-territorio-oiteiro-dos-nogueiras-e-sao-jose-dos-matos-2022/"),
 ("Graciosa","BA",2023,"Protocolo de Consulta da Comunidade Quilombola Graciosa","protocolo-de-consulta-da-comunidade-quilombola-graciosa-2023/"),
 ("São José de Icatu","MA",2023,"Protocolo de Consulta Comunidade Quilombola de São José de Icatu","protocolo-de-consulta-comunidade-quilombola-de-sao-jose-de-icatu-2023/"),
 ("Vão Grande","MT",2023,"Protocolo de Consulta Território Quilombola do Vão Grande","protocolo-de-consulta-territorio-quilombola-do-vao-grande-2023/"),
 ("Santa Tereza","PB",2023,"Protocolo de Consulta prévia, livre, esclarecida e de Boa Fé da Comunidade Quilombola de Santa Tereza","protocolo-de-consulta-previa-livre-esclarecida-e-de-boa-fe-da-comunidade-quilombola-de-santa-tereza-2023/"),
 ("Serra dos Rafaéis","PI",2023,"Protocolo de consulta livre, prévia e informada dos remanescentes de quilombo da Serra dos Rafaéis","protocolo-de-consulta-livre-previa-e-informada-dos-remanescentes-de-quilombo-da-serra-dos-rafaeis-2023/"),
 ("Sítio Conceição","PA",2022,"Protocolo de Consulta Prévia, Livre e Informada do Território Quilombola Sítio Conceição","protocolo-de-consulta-previa-livre-e-informada-do-territorio-quilombola-sitio-conceicao/"),
 ("Rio Itacuruçá Alto","PA",None,"Protocolo do Território Quilombola do Rio Itacuruçá Alto – Ilhas de Abaetetuba","protocolo-do-territorio-quilombola-do-rio-itacuruca-alto-ilhas-de-abaetetuba/"),
 ("Santa Rita","MA",2022,"Protocolo de Consulta Santa Rita","protocolo-de-consulta-santa-rita-2022/"),
 ("Pontinha","MG",None,"Protocolo de Consulta da Comunidade Quilombola da Pontinha","protocolo-de-consulta-da-comunidade-quilombola-da-pontinha/"),
 ("__PR_TODOS__","PR",2021,"Protocolo de Consulta às Comunidades Quilombolas do Paraná (coletivo estadual)","protocolo-de-consulta-as-comunidades-quilombolas-do-parana-2021/"),
 ("__VALE_RIBEIRA__","SP",2020,"Protocolo de Consulta Prévia dos Territórios Quilombolas do Vale do Ribeira – SP (coletivo regional)","protocolo-de-consulta-previa-dos-territorios-quilombolas-do-vale-do-ribeira-sp-2020/"),
 ("Brumadinho","MG",None,"Protocolo de Consulta Prévia, Livre e Informada das Comunidades Quilombolas de Brumadinho","protocolo-de-consulta-previa-livre-e-informada-das-comunidades-quilombolas-de-brumadinho/"),
 ("Passagem","PA",None,"Protocolo de Consulta Prévia dos Quilombos Passagem, Nazaré do Airi e Peafú (Monte Alegre)","protocolo-de-consulta-previa-dos-quilombos-passagem-nazare-do-airi-e-peafu-do-municipio-de-monte-alegre-pa/"),
 ("Jambuaçu","PA",None,"Protocolo de Consulta Prévia, Livre e informada dos Quilombolas de Jambuaçu/Moju-PA","protocolo-de-consulta-previa-livre-e-informada-dos-quilombolas-de-jambuacu-moju-pa/"),
 ("Laranjituba e África","PA",None,"Protocolo do Território Quilombola Laranjituba e África","protocolo-de-consulta-previa-livre-informada-e-de-consentimento-do-territorio-quilombola-laranjituba-e-africa/"),
 ("Gibrié de São Lourenço","PA",None,"Protocolo de Consulta – Comunidade Quilombola Gibrié de São Lourenço","protocolo-de-consulta-previa-livre-informada-e-de-consentimento-comunidade-quilombola-gibrie-de-sao-lourenco/"),
 ("Alcântara","MA",None,"Documento Base do Protocolo Comunitário de CCPLI das Comunidades Quilombolas do Território Étnico de Alcântara","protocolo-de-consulta-quilombola-de-alcantara/"),
 ("Bom Remédio","PA",None,"Protocolo de Consulta – Território Quilombola Bom Remédio","protocolo-de-consulta-territorio-quilombola-bom-remedio/"),
 ("Abacatal-Aurá","PA",None,"Protocolo de Consulta Quilombola – Abacatal/Aurá","protocolo-de-consulta-quilombola-abacatal-aura/"),
 ("Alto Trombetas II","PA",None,"Protocolo de Consulta Quilombola do Alto Trombetas II","protocolo-de-consulta-quilombola-do-alto-trombetas-ii/"),
 ("__SANTAREM__","PA",None,"Protocolo de Consulta Quilombola – Santarém/PA (coletivo municipal)","protocolo-de-consulta-quilombola-santarem-pa/"),
]

# fontes complementares
EXTRA = [
 ("Raiz","MG",2025,"Protocolo Comunitário Biocultural da Comunidade Quilombola e Apanhadora de Flores Sempre-Vivas Raiz",
  "https://terradedireitos.org.br/","Terra de Direitos"),
]

def strip_ac(s):
    return unicodedata.normalize('NFKD', s).encode('ascii','ignore').decode()
def norm(s):
    s = strip_ac(s).upper()
    s = re.sub(r'^(TQ|TERRITORIO QUILOMBOLA|COMUNIDADE QUILOMBOLA|QUILOMBO)[\s_]+','',s)
    s = re.sub(r'\bSTO\b','SANTO',s); s = re.sub(r'\bSTA\b','SANTA',s)
    s = re.sub(r'[^A-Z0-9]+',' ',s)
    return re.sub(r'\s+',' ',s).strip()

protos = []
for nome, uf, ano, titulo, slug in P:
    protos.append({'territorio_ref': nome, 'uf': uf, 'ano': ano, 'titulo': titulo,
                   'url': B + slug, 'fonte': FONTE_OBS, 'coletivo': nome.startswith('__')})
for nome, uf, ano, titulo, url, fonte in EXTRA:
    protos.append({'territorio_ref': nome, 'uf': uf, 'ano': ano, 'titulo': titulo,
                   'url': url, 'fonte': fonte, 'coletivo': False})

# ---------- vincular às fichas ----------
import os
I = os.environ.get('SERIEMA_INTERIM', 'interim')
fichas = json.load(open(f'{I}/fichas_pre.json'))
idx = {}
for f in fichas:
    idx.setdefault((norm(f['nome']), f['uf']), []).append(f)

VALE_RIBEIRA = {'ELDORADO','IPORANGA','BARRA DO TURVO','ITAOCA','ITAPEVA','JACUPIRANGA',
                'REGISTRO','CANANEIA','ELDORADO PAULISTA','ITAOCA'}
lig = falha = colet = 0
for p in protos:
    if p['coletivo']:
        alvos = []
        if p['territorio_ref'] == '__PR_TODOS__':
            alvos = [f for f in fichas if f['uf'] == 'PR']
        elif p['territorio_ref'] == '__VALE_RIBEIRA__':
            alvos = [f for f in fichas if f['uf'] == 'SP' and
                     any(strip_ac(m).upper() in VALE_RIBEIRA for m in f['municipios'])]
        elif p['territorio_ref'] == '__SANTAREM__':
            alvos = [f for f in fichas if f['uf'] == 'PA' and
                     any('SANTAREM' in strip_ac(m).upper() for m in f['municipios'])]
        for f in alvos:
            f.setdefault('_protos', []).append({**p, 'vinculo': 'coletivo'})
        colet += len(alvos); continue

    cands = idx.get((norm(p['territorio_ref']), p['uf']), [])
    if cands:
        cands[0].setdefault('_protos', []).append({**p, 'vinculo': 'confirmado'})
        lig += 1; continue
    # fuzzy dentro da UF
    best, score = None, 0
    alvo = norm(p['territorio_ref'])
    for f in fichas:
        if f['uf'] != p['uf']: continue
        s = SequenceMatcher(None, alvo, norm(f['nome'])).ratio()
        if s > score: best, score = f, s
    if best and score >= 0.82:
        best.setdefault('_protos', []).append({**p, 'vinculo': 'provavel', 'score': round(score,2)})
        lig += 1
    else:
        falha += 1

for f in fichas:
    ps = f.pop('_protos', [])
    f['protocolo_consulta'] = {
        'tem': bool(ps), 'n': len(ps),
        'itens': [{k: v for k, v in p.items() if k not in ('territorio_ref','coletivo')} for p in ps],
    } if ps else {'tem': False, 'n': 0, 'itens': []}

json.dump(protos, open(f'{I}/protocolos.json','w'), ensure_ascii=False, indent=1)
json.dump(fichas, open(f'{I}/fichas_com_protocolo.json','w'), ensure_ascii=False)
print(f'protocolos catalogados ......... {len(protos)}')
print(f'   vinculados a território ..... {lig}')
print(f'   coletivos (1 p/ vários) ..... {colet} vínculos')
print(f'   sem território correspondente {falha}  (comunidade certificada mas sem processo no INCRA)')
print(f'fichas com protocolo ........... {sum(1 for f in fichas if f["protocolo_consulta"]["tem"])}')
