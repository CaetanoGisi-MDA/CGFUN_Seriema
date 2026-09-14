# COMO_ATUALIZAR_A_BASE.md
## Observatório Seriema — passo a passo de atualização trimestral

> Leia a seção **"Por que isso é seguro"** antes da primeira vez. Nas rodadas seguintes, vá direto ao passo a passo.

---

## Por que isso é seguro

Tudo o que você corrigir pelo assistente do painel — protocolos registrados, vínculos confirmados, territórios inativados — vive em um único arquivo: `curadoria/edicoes.json`.

**Nenhum dos scripts abaixo toca nesse arquivo.** Eles só leem os arquivos-fonte novos e regravam a pasta `base/`. Quando o painel carrega, ele funde as duas camadas, com a curadoria sempre por cima. Você pode rodar esta atualização quantas vezes quiser, sem risco de perder o que já foi corrigido manualmente.

---

## Visão geral das três etapas

1. **Buscar** — baixar os arquivos-fonte atualizados
2. **Processar** — rodar os seis scripts do pipeline, na ordem
3. **Conferir e publicar** — checar os números e subir para o GitHub

---

## Etapa 1 — Buscar as fontes atualizadas

Baixe os quatro arquivos abaixo e coloque todos dentro da pasta `entrada/`, **mantendo os nomes exatos** indicados — o pipeline procura por esses nomes.

### 1. Polígonos dos territórios — INCRA, Acervo Fundiário

🔗 **https://certificacao.incra.gov.br/csv_shp/export_shp.py**

Na tela, escolha a camada de **Quilombolas** e deixe o campo de estado **em branco** para exportar o Brasil inteiro. Vem um `.zip` com quatro arquivos — descompacte todos.

Salvar como: `A_reas_de_Quilombolas.shp` (+ `.dbf`, `.shx`, `.prj`, mesmo nome)

*Se o link estiver fora do ar:* alternativa quinzenal em
🔗 https://acervofundiario.incra.gov.br/i3geo/geodownload/geodados.php

---

### 2. Andamento dos processos — INCRA

🔗 **https://www.gov.br/incra/pt-br/assuntos/governanca-fundiaria/quilombolas**

Procure na página o quadro **"Acompanhamento dos processos de regularização quilombola"** (PDF).

Salvar como: `territoriosquilombolas.pdf`

*Nota:* o INCRA já trocou o endereço direto deste arquivo uma vez durante o projeto. Se o link antigo não abrir, procure pelo nome do documento dentro da página em vez de tentar um endereço direto salvo.

---

### 3. Comunidades certificadas — Fundação Cultural Palmares

🔗 **https://www.gov.br/palmares/pt-br/departamentos/protecao-preservacao-e-articulacao/certificacao-quilombola**

A página aponta para uma planilha do Google, atualizada mensalmente:

🔗 **https://docs.google.com/spreadsheets/d/1WBjixnnjJWrDXsA2WvElj65rrZ4nkNM-u5LclRV0lGs**

Abra e use **Arquivo → Fazer download → Microsoft Excel (.xlsx)**.

Salvar como: `TABELA_DE_CRQ_CERTIFICADAS.xlsx`

---

### 4. Localidades quilombolas — IBGE, Censo 2022

🔗 **https://geoftp.ibge.gov.br/organizacao_do_territorio/estrutura_territorial/localidades/localidades_quilombolas_2022/**

Dentro da pasta, baixe apenas:

- `Arquivos_vetoriais/csv/BR/` → o arquivo nacional
- `Arquivos_vetoriais/Dicionario_LQs.xlsx` (opcional, só para consulta)

Salvar como: `BR_LQs_CD2022.csv`

*Não precisa* de `kmz/`, `shp/`, `Apendices/` nem `Cartogramas/` — são o mesmo conteúdo em outro formato.

---

### 5. Títulos expedidos — INCRA/DFQ (opcional, se voltar ao ar)

Este arquivo estava fora do portal do INCRA no momento em que a base foi construída, e por isso os dados de titulação vêm de uma **transcrição validada por totais**, não do PDF direto. Se o documento for republicado, procure na mesma página do item 2 por **"Títulos expedidos às comunidades quilombolas"** ou **"Titulação de Territórios Quilombolas"**.

Salvar como: `Titulos_expedidos.pdf`

Se este arquivo estiver presente em `entrada/`, o pipeline usa ele automaticamente no lugar da transcrição.

---

### 6. Protocolos de consulta prévia — sem download, é trabalho manual

🔗 **https://observatorio.direitosocioambiental.org/category/quilombolas/**

Não há arquivo para baixar. Percorra as páginas da categoria e veja se há protocolos novos desde a última atualização. Se houver, abra:

```
pipeline/etl_03_protocolos.py
```

E acrescente cada protocolo novo na lista `P`, seguindo exatamente o formato das linhas existentes: nome do território, UF, ano, título do documento, endereço.

---

### 7. Malha municipal oficial do IBGE (opcional, melhora a precisão)

Só necessário se você quiser substituir a tabela de apoio (compilação de terceiros) pela malha oficial, usada para posicionar certidões sem coordenada do Censo.

🔗 **https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/malhas_municipais/municipio_2024/Brasil/**

Baixe `BR_Municipios_2024.zip` (≈199 MB). Salve em `entrada/` — o pipeline detecta e usa automaticamente, sem precisar de nenhum ajuste no código. Este arquivo **nunca** deve ir para o GitHub; a pasta `entrada/` está no `.gitignore`.

---

## Etapa 2 — Processar

Com os arquivos em `entrada/`, abra o terminal na pasta `pipeline/` e rode, **nesta ordem**:

```bash
pip install geopandas pdfplumber openpyxl pyarrow

python3 etl_01_fontes.py      # normaliza as quatro fontes
python3 etl_02_fusao.py       # cruza por número de processo, monta as fichas
python3 etl_03_protocolos.py  # cataloga e vincula os protocolos
python3 etl_04_publicar.py    # grava os arquivos finais em base/
python3 etl_05_regime.py      # separa federal / estadual / pré-2003, marca fragmentos e duplicatas
python3 etl_06_titulos.py     # integra a tabela de títulos expedidos, expõe divergências
```

Cada script imprime um resumo do que fez — quantos registros, quantos casaram por código, quantos por nome. Não é preciso decorar; basta rodar em sequência e observar se algum termina com erro.

---

## Etapa 3 — Conferir e publicar

Antes de subir para o GitHub, dois pontos merecem atenção:

**O total de territórios ativos mudou de forma coerente?** Se caiu ou disparou de repente, alguma fonte provavelmente mudou de formato e a extração falhou silenciosamente em algum trecho. Compare com a última rodada.

**Apareceram divergências novas?** O `etl_06` expõe, nas próprias fichas, casos em que as fontes discordam entre si sobre a fase de um território. Vale abrir algumas para checar se fazem sentido.

Estando tudo certo:

1. Suba o **conteúdo** da pasta `base/` para o repositório no GitHub, substituindo os arquivos existentes (o GitHub troca sozinho os de mesmo nome)
2. **Não toque em `curadoria/`** — nunca faz parte deste processo
3. Espere um ou dois minutos e recarregue o painel com **Ctrl+Shift+R**

---

## Referência rápida — links para copiar

| # | Fonte | Link |
|---|---|---|
| 1 | Polígonos INCRA | https://certificacao.incra.gov.br/csv_shp/export_shp.py |
| 2 | Andamento dos processos | https://www.gov.br/incra/pt-br/assuntos/governanca-fundiaria/quilombolas |
| 3 | Planilha FCP | https://docs.google.com/spreadsheets/d/1WBjixnnjJWrDXsA2WvElj65rrZ4nkNM-u5LclRV0lGs |
| 4 | Localidades IBGE | https://geoftp.ibge.gov.br/organizacao_do_territorio/estrutura_territorial/localidades/localidades_quilombolas_2022/ |
| 5 | Títulos expedidos (se voltar) | mesma página do item 2 |
| 6 | Protocolos de consulta | https://observatorio.direitosocioambiental.org/category/quilombolas/ |
| 7 | Malha municipal oficial | https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/malhas_municipais/municipio_2024/Brasil/ |

---

## Se algo der errado

O sintoma mais comum é um script terminar com erro por causa de **mudança de formato** em alguma fonte — colunas renomeadas, layout diferente no PDF. Nesse caso, o erro do Python geralmente aponta a linha exata; guarde a mensagem e leve para o Claude resolver, com o arquivo-fonte novo em mãos.

O segundo mais comum é o **link ter mudado de endereço** — já aconteceu com o item 1 e o item 2 durante a construção desta base. Nesse caso, procure pelo nome do documento na página institucional em vez de confiar num endereço direto salvo.
