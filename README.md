# Observatório Seriema

Painel de governança fundiária de territórios quilombolas, para apoio às atividades da **Coordenação de Governança Fundiária (CFU)** — SETEQ / MDA.

Site estático: mapa com os territórios, ficha completa por território, assistente de linguagem natural que consulta a base, e edição curada com registro público das alterações.

---

## Publicar

1. Suba todo o conteúdo desta pasta num repositório.
2. *Settings → Pages* → branch principal, pasta raiz (`/`).
3. Pronto. Não há build.

Para rodar localmente: `python3 -m http.server` na pasta e abra `http://localhost:8000`.
Abrir o `index.html` direto do disco **não funciona** — o navegador bloqueia a leitura dos JSON.

---

## As duas camadas de dados

Esta separação é o que impede que uma atualização de fonte apague o trabalho da equipe.

| Pasta | O que é | Quem escreve |
|---|---|---|
| `base/` | dados derivados de INCRA, IBGE, FCP e do acervo de protocolos | **só o pipeline**, nunca o painel |
| `curadoria/` | correções, confirmações de vínculo, protocolos e observações da CFU | **só o painel**, nunca o pipeline |

O painel funde as duas ao carregar, com a curadoria prevalecendo. A função de gravação conhece um único caminho de escrita: `curadoria/edicoes.json`.

### Arquivos de `base/`

- `territorios_indice.json` — versão leve (156 KB), é o que o mapa carrega
- `territorios_fichas.json` — base completa (1,1 MB)
- `resumo.json` — agregados pré-calculados
- `protocolos.json` — catálogo de protocolos de consulta prévia

---

## Metodologia

Este capítulo explica de onde vem cada informação, como as fontes foram cruzadas e quais decisões foram tomadas — inclusive as que ainda estão pendentes. Foi escrito para ser lido por alguém que chegue ao projeto sem contexto nenhum.

### O problema que a base resolve

Não existe, no Estado brasileiro, um cadastro único de territórios quilombolas. Existem quatro registros parciais, mantidos por instituições diferentes, com finalidades diferentes, que não conversam entre si:

- o **INCRA** mantém a tramitação dos processos de regularização e, separadamente, uma base cartográfica
- a **Fundação Cultural Palmares** mantém o cadastro de certificação das comunidades
- o **IBGE** mapeou, no Censo 2022, onde as comunidades efetivamente estão
- **órgãos estaduais de terra** titulam territórios por rito próprio, fora do fluxo federal

A mesma comunidade aparece nos quatro com nomes diferentes, grafias diferentes e nenhum identificador comum. O trabalho desta base é reconciliá-los sem inventar vínculos que não existem.

### As quatro fontes e o que cada uma aporta

| Fonte | Formato | Registros | O que só ela tem |
|---|---|---|---|
| **INCRA — Acervo Fundiário** | shapefile | 439 polígonos | geometria, área medida, esfera (federal/estadual), órgão responsável |
| **INCRA — Andamento dos processos** | PDF | 613 processos | a trilha administrativa completa, com datas de cada ato |
| **FCP — Comunidades certificadas** | planilha | 3.434 certidões | certificação, nº de moradores e **a ponte para o nº de processo do INCRA** |
| **IBGE — Localidades quilombolas 2022** | CSV | 8.441 localidades | coordenadas reais, e **três chaves de ligação por código** |

Uma quinta fonte, sem download, alimenta o campo de protocolos de consulta prévia: o **Observatório de Protocolos Comunitários (OPCPLI/CEPEDIS-UFGD)**, complementado por ISA e Terra de Direitos.

### O cruzamento é por código, não por nome

Esta é a decisão metodológica central. Casar registros por semelhança de nome produz erros silenciosos: existem territórios homônimos em municípios diferentes (Baú em Araçuaí e no Serro; Jatobá em Patu/RN e Cabrobó/PE) e o mesmo território escrito de cinco formas.

O cruzamento usa, em ordem de prioridade:

1. **Número de processo do INCRA**, normalizado a 17 dígitos — liga o shapefile, o PDF e a planilha da FCP
2. **Número de processo da Palmares** — presente tanto na planilha da FCP quanto no CSV do IBGE, liga a certificação às localidades do Censo
3. **Nome normalizado + UF** — só quando não há código, e sempre marcado como vínculo fraco

Cada ficha exibe o **selo de confiança** de cada vínculo:

- **Confirmado** — número de processo idêntico entre as fontes
- **Provável** — nome e UF idênticos após normalização (remoção de acentos, prefixos como "TQ", abreviações)
- **Não localizado** — não há correspondência

Resultado do cruzamento: 563 territórios com certificação confirmada por código, 616 com localidades do IBGE confirmadas por código, 301 com polígono confirmado. O painel nunca apresenta um vínculo provável como se fosse certo.

### Os três universos

Territórios quilombolas não seguem um único rito jurídico. Tratá-los como se seguissem é a principal fonte de confusão nas contagens públicas — e explica por que números divulgados variam de 54 a 200 conforme a fonte.

**1. Federal, rito do Decreto 4.887/2003** — o núcleo. São os 613 processos do quadro de andamento do INCRA. Percorrem uma sequência definida:

> **Certificação (FCP)** → **RTID** (identificação e delimitação, publicada em edital) → **Portaria de reconhecimento** (declara os limites) → **Decreto de desapropriação** (autoriza retirar imóveis privados de dentro) → **Título** (propriedade coletiva à associação da comunidade)

**2. Federal anterior a 2003** — cerca de 8 territórios titulados pela própria Fundação Cultural Palmares, quando a competência ainda era dela. Reconhecíveis pelo prefixo `01420` ou por formatos antigos de processo. Curiaú (AP) e Campinho (RJ) são exemplos. Não têm RTID nem portaria porque o rito era outro — não estão incompletos.

**3. Estadual** — cerca de 76 territórios titulados por ITERPA (PA), ITERMA (MA), ITESP (SP), INTERPI (PI) e CDA (BA). Rito próprio de cada estado, sem correspondência com as etapas federais. Entram na base pelo valor informativo, mas o painel não exibe trilha federal para eles.

O regime é inferido automaticamente pelo **formato do número de processo** somado ao campo de esfera e órgão responsável.

### A trilha e seus três estados

Cada etapa pode estar em uma de três situações — e confundi-las distorce a leitura:

- **Cumprida** — há data registrada
- **Pendente** — a etapa é exigida e ainda não ocorreu
- **Dispensada** — a etapa **não se aplica** àquele território

A dispensa é comum e documentada pelo próprio INCRA, que escreve "Não precisa" na coluna correspondente. Ocorre 34 vezes na coluna de decreto, 13 na de portaria e 10 no segundo edital de RTID. O caso típico: quando o território está integralmente em terra pública, não há imóvel privado a desapropriar, e o decreto é dispensável. Um território dispensado de decreto está **mais adiantado**, não menos.

Casos que fogem do padrão recebem nota explicativa breve na ficha: título parcial, concessão de direito real de uso (CCDRU), etapa dispensada, divergência entre fontes.

### Quando as fontes oficiais discordam

O shapefile e o PDF do INCRA às vezes classificam o mesmo processo de forma diferente. Para o universo federal, **prevalece o PDF**, por dois motivos verificados:

- é mais atual (edição de junho de 2026)
- distingue titulação **integral** de **parcial**, enquanto o campo do shapefile colapsa as duas

O caso que estabeleceu a regra: Invernada Paiol de Telha (PR) aparece como `TITULADO` no shapefile, mas o PDF registra "Parcial" — e a informação pública confirma que os títulos emitidos foram parciais.

Divergências remanescentes não são resolvidas em silêncio: aparecem sinalizadas na ficha, para decisão humana.

### Georreferenciamento

Dos 703 territórios, **673 têm coordenada**:

- **429** pelo centroide do polígono oficial do INCRA
- **244** pela média das localidades do Censo 2022 vinculadas ao território
- **30** sem coordenada — permanecem na base, ausentes do mapa

A origem do ponto é declarada em cada ficha. O painel exibe **pontos, não perímetros**, e a agregação nunca desce abaixo do que a fonte já publica.

### Achados da auditoria de julho de 2026

Uma vistoria completa da base identificou problemas pontuais, todos nominais e rastreáveis. Registrados aqui por honestidade metodológica e porque orientam a curadoria:

| Achado | Extensão | Natureza |
|---|---|---|
| Pares de registros duplicados | 5 pares | erro de dígito no nº de processo na origem |
| "Não precisa" tratado como etapa vazia | 34 casos | erro de processamento |
| Datas perdidas na extração do PDF | 1 processo, 3 datas | falha pontual de leitura de tabela |
| Processo possivelmente ausente do quadro federal | 1 caso | a confirmar junto ao INCRA |

As duplicatas merecem menção por serem instrutivas. Lagoa das Pedras (CE) aparece duas vezes com processos `...000663` e `...000664` — mesmo nome, mesma área ao quarto decimal, mesmo decreto. Estiva dos Mafras (MA) tem `54203` no shapefile e `54230` no PDF, uma transposição de dígitos. Mocambo (SE) tem prefixo de superintendência divergente. Área idêntica em UF igual é indício forte de duplicação, mas a fusão **não é automática**: cada par vai para conferência humana pela camada de curadoria.

A auditoria também estabeleceu um resultado positivo relevante: dos 91 territórios presentes apenas na base cartográfica, só **10 são federais**, e destes apenas 4 têm processo em formato moderno — sendo 3 duplicatas comprovadas. **O quadro federal de andamento é, portanto, uma fonte completa**, não uma amostra. É o que permite fechar o núcleo federal com confiança.

### O que a base não cobre

- Comunidades **apenas certificadas** pela FCP, sem processo aberto no INCRA, não aparecem como território. São milhares.
- **Povos e comunidades tradicionais não quilombolas** dependem de acordo de compartilhamento com o MPF e não integram esta versão.
- Ausência de protocolo de consulta significa **não localizado nas fontes públicas consultadas** — nunca "não existe".
- Territórios estaduais têm dados menos completos por limitação das fontes, não por opção.

---

## Atualizar os dados

> **Sobre os links abaixo:** foram verificados em **25 de julho de 2026**. Portais de governo mudam de endereço com alguma frequência. Se algum não abrir, procure pelo nome da instituição e do produto — os nomes dos arquivos são mais estáveis que as URLs. Cada item abaixo diz também *o que* procurar, não só onde.

### Resumo do procedimento

```bash
pip install geopandas pdfplumber openpyxl pyarrow

mkdir entrada                          # baixe os 4 arquivos aqui dentro
python3 pipeline/etl_01_fontes.py      # normaliza as fontes
python3 pipeline/etl_02_fusao.py       # cruza por nº de processo, monta as fichas
python3 pipeline/etl_03_protocolos.py  # cataloga e vincula os protocolos
python3 pipeline/etl_04_publicar.py    # grava base/
```

O primeiro script confere se está tudo em `entrada/` e, se faltar algo, diz exatamente o quê. Os nomes dos arquivos precisam bater — renomeie se o download vier com outro nome.

**`curadoria/` não é tocada por nenhum script.** É seguro reprocessar quantas vezes quiser.

### Os quatro arquivos de `entrada/`

---

#### 1. `A_reas_de_Quilombolas.shp` (+ `.dbf`, `.shx`, `.prj`)
**Polígonos dos territórios — INCRA, Acervo Fundiário**

Página de download: <https://certificacao.incra.gov.br/csv_shp/export_shp.py>

Na tela, escolha a **camada de quilombolas** e **deixe o estado em branco** para exportar o Brasil inteiro. Vem um `.zip` com quatro arquivos — descompacte todos os quatro em `entrada/`, não só o `.shp`.

Pode pedir autenticação **gov.br** (qualquer servidor tem). Tente primeiro sem login.

Se o endereço estiver fora do ar — acontece com alguma frequência:
- Alternativa quinzenal: <https://acervofundiario.incra.gov.br/i3geo/geodownload/geodados.php>
- Serviço por estado, para abrir no QGIS: `http://acervofundiario.incra.gov.br/i3geo/ogc.php?tema=quilombolas_XX` (troque `XX` pela UF)
- Portal geral: <https://acervofundiario.incra.gov.br/acervo/acv.php>

*O que este arquivo traz:* geometria, área, famílias, esfera (federal/estadual), órgão responsável e fase — inclusive dos territórios titulados por órgãos estaduais (ITERPA, ITERMA, ITESP, INTERPI, CDA), que **não aparecem** no PDF federal do item 2.

---

#### 2. `territoriosquilombolas.pdf`
**Andamento dos processos — INCRA**

Página: <https://www.gov.br/incra/pt-br/assuntos/governanca-fundiaria/quilombolas>

Procure na página o quadro **"Andamento dos processos"** ou **"Acompanhamento dos processos de regularização quilombola"**. É um PDF gerado a partir de planilha, com uma linha por processo. Baixe e salve com esse nome.

Vale pegar também, se estiver disponível, o quadro de **títulos expedidos** (`andamento_titulacao_quilombola_*.pdf`) para conferência manual — o pipeline não o usa.

*O que traz:* a trilha completa — 1º e 2º editais de RTID, retificações, portaria de reconhecimento, retificação da portaria, decreto e título, com datas. Cobre **exclusivamente processos federais** abertos na vigência do Decreto 4.887/2003.

---

#### 3. `TABELA_DE_CRQ_CERTIFICADAS.xlsx`
**Comunidades certificadas — Fundação Cultural Palmares**

Página: <https://www.gov.br/palmares/pt-br/departamentos/protecao-preservacao-e-articulacao/certificacao-quilombola>

A página aponta para uma **planilha do Google atualizada mensalmente**:
<https://docs.google.com/spreadsheets/d/1WBjixnnjJWrDXsA2WvElj65rrZ4nkNM-u5LclRV0lGs>

Abra e use **Arquivo → Fazer download → Microsoft Excel (.xlsx)**. A aba que importa chama-se `CERTIFICADAS`; a aba `DADOS` traz a data da última atualização, útil para registrar.

*Por que é a fonte mais valiosa:* traz as colunas **`Nº PROCESSO INCRA`** e **`ETAPA DO PROCESSO DE TITULAÇÃO`**. É essa ponte que permite cruzar certificação e regularização **por código**, e não por semelhança de nome.

---

#### 4. `BR_LQs_CD2022.csv`
**Localidades quilombolas 2022 — IBGE, Censo Demográfico**

Pasta: <https://geoftp.ibge.gov.br/organizacao_do_territorio/estrutura_territorial/localidades/localidades_quilombolas_2022/>

Dentro dela, baixe **apenas**:

- `Arquivos_vetoriais/csv/BR/` → o arquivo nacional (`BR_LQs_CD2022.csv`)
- `Arquivos_vetoriais/Dicionario_LQs.xlsx` — dicionário dos campos, para consulta humana

**Não precisa** de `kmz/`, `shp/`, `Apendices/` nem `Cartogramas/`: são o mesmo conteúdo em outro formato ou já contidos no CSV.

*O que traz:* 8.441 localidades com latitude e longitude, e três chaves de ligação — `IDCQ0001` (código nacional da comunidade), `CD_TQ` (território delimitado) e **`P_FCP`** (nº do processo na Palmares), que fecha o cruzamento com o item 3.

---

### 5. Protocolos de consulta prévia — *sem download*

Fonte principal: **Observatório de Protocolos Comunitários (OPCPLI/CEPEDIS-UFGD)**
<https://observatorio.direitosocioambiental.org/category/quilombolas/>

O catálogo está **escrito à mão** dentro de `pipeline/etl_03_protocolos.py`, na lista `P` — cada item é `(nome do território, UF, ano, título, endereço)`. Para atualizar, percorra as páginas da categoria e acrescente as entradas novas seguindo o formato das existentes. Em julho de 2026 eram 4 páginas, 39 protocolos.

Fontes complementares, se quiser ampliar:
- ISA, acervo de documentos: <https://acervo.socioambiental.org>
- Terra de Direitos, cadernos: <https://terradedireitos.org.br>

Também vale registrar protocolos direto pelo painel, via assistente — vão para `curadoria/` e sobrevivem a qualquer reprocessamento.

---

### Conferir se deu certo

O `etl_04` imprime o total ao final. Compare com o que a coordenação conhece antes de publicar. Na rodada de julho de 2026: **703 territórios, 673 com coordenada, 2.934.163 ha**.

Se algum número destoar muito, o suspeito mais provável é mudança de layout na fonte — sobretudo o PDF do item 2, cuja extração depende da posição das colunas.

---

## Assistente

O painel conversa com um serviço de linguagem pela interface padrão de mensagens (compatível com OpenAI). Para trocar de serviço, edite três campos em `config.js`:

```js
llm: { endpoint: '...', modelo: '...', usarProxy: false }
```

**O modelo não recebe a base inteira.** Ele pede consultas estruturadas; o código executa sobre o JSON local e devolve os registros; o modelo redige a resposta a partir deles. Toda afirmação factual é rastreável a um registro — e a instrução de sistema proíbe responder de memória.

Ferramentas disponíveis ao modelo: `consultar_base`, `resumo_agregado`, `buscar_web`, `propor_edicao`.

### Chaves

Nenhuma chave fica no código. Cada uma é digitada pela pessoa e guardada apenas no navegador dela (`localStorage`, com queda para memória quando o ambiente bloqueia). São três, independentes:

- **modelo** — pedida na primeira pergunta
- **busca na web** — pedida na primeira busca (opcional, configure o provedor em `config.js`)
- **GitHub** — pedida na primeira publicação

Se preferir não expor chave nenhuma, aponte `llm.endpoint` para um proxy que a guarde no servidor e ligue `usarProxy: true`.

---

## Edição por linguagem natural

O modelo **interpreta**, o código **grava**. Nunca o contrário.

1. Você descreve a correção em português
2. O modelo devolve uma alteração estruturada
3. A tela mostra antes → depois, com o motivo
4. Você confirma
5. O código aplica e, ao publicar, grava em `curadoria/edicoes.json`

Exclusão é **inativação com motivo**, não remoção: o registro sai da vista e permanece no arquivo. O histórico do Git vira a trilha de auditoria da coordenação — quem, quando, por quê.

Campos editáveis: nome, municípios, área, famílias, processo INCRA, observação, protocolo de consulta, confirmação de vínculo, inativação/reativação.

### Token do GitHub

Use um **fine-grained token** restrito a este repositório, com permissão de *Contents: read and write* e validade curta. A API rejeita a gravação se o arquivo mudou desde que a página foi carregada — nesse caso o painel avisa para recarregar, em vez de sobrescrever o trabalho de outra pessoa.

Para exigir revisão antes de valer, troque em `config.js`:

```js
github: { exigirRevisao: true }
```

O painel passa a abrir uma proposta de alteração em vez de gravar direto.

---

## Repositório público

Se o repositório for público — o caso previsto — **tudo que for digitado no painel fica visível na internet**, inclusive motivos e observações. Os dados de base já são públicos por origem, mas o campo livre de observação exige cuidado: anotação sobre conflito em curso, nome de liderança ameaçada ou tratativa não pública **não deve ir para lá**. Para isso, um segundo repositório privado.

---

## Limites conhecidos

- Recorte T1+T2: territórios com processo no INCRA **ou** com delimitação cartográfica. Comunidades apenas certificadas pela FCP, sem processo aberto, não aparecem como território.
- Territórios de esfera estadual constam quando têm polígono, mas o quadro federal de andamento não os cobre.
- Ausência de protocolo de consulta significa *não localizado nas fontes públicas consultadas* — nunca *não existe*.
- A camada de povos e comunidades tradicionais não quilombolas depende de acordo de compartilhamento com o MPF e não integra esta versão.
- Vínculos entre fontes vêm com selo: **confirmado** (nº de processo idêntico), **provável** (nome e UF idênticos após normalização), **não localizado**. Nada é inferido além disso.

---

## Estrutura

```
index.html                      estrutura
estilo.css                      estilo
config.js                       endpoints, repositório, flags
seriema.js                      dados, mapa, lista, ficha
assistente.js                   ferramentas, conversa, edição, publicação
base/                           dados derivados      ← só o pipeline escreve
curadoria/edicoes.json          camada da CFU        ← só o painel escreve
pipeline/etl_01_fontes.py       normaliza as 4 fontes
pipeline/etl_02_fusao.py        cruza e monta as fichas
pipeline/etl_03_protocolos.py   catálogo de protocolos
pipeline/etl_04_publicar.py     grava base/
entrada/                        arquivos-fonte baixados (não versionar)
interim/                        temporários do pipeline (não versionar)
```

Sugestão de `.gitignore`:

```
entrada/
interim/
```



Mapa com MapLibre GL sobre tiles do CARTO/OpenStreetMap. Sem framework, sem build, sem dependência de servidor.
