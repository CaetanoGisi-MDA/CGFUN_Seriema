/* ================================================================
   Observatório Seriema — assistente
   O modelo interpreta; quem consulta e quem grava é o código.
   Nenhuma afirmação factual vem da memória do modelo: só dos
   registros devolvidos pelas ferramentas.
   ================================================================ */
window.Assistente = (function () {
'use strict';

const CFG = window.SERIEMA_CONFIG;
let S = null;                       // injetado pelo núcleo
const $ = s => document.querySelector(s);
let historico = [];
let ocupado = false;

/* ---------------- chaves de sessão ---------------- */
const K_LLM = 'seriema.chave.llm';
const K_BUSCA = 'seriema.chave.busca';
const K_GH = 'seriema.chave.github';
const K_END = 'seriema.endpoint';
const K_MOD = 'seriema.modelo';

function endpointAtual() { return S.cofre.get(K_END) || CFG.llm.endpoint; }
function modeloAtual()   { return S.cofre.get(K_MOD) || CFG.llm.modelo; }

/* Configuração do serviço de linguagem: endpoint e modelo editáveis, para que
   cada pessoa use o serviço que preferir sem tocar no código. */
function dialogoServico() {
  return new Promise(resolve => {
    const v = document.createElement('div');
    v.className = 'veu';
    v.innerHTML = `<div class="dialogo">
      <h3>Serviço de linguagem</h3>
      <p>O painel conversa com qualquer serviço que use a interface padrão de mensagens
         (compatível com OpenAI). Endereço e modelo são editáveis — troque para usar outro provedor.</p>
      <label for="d-end">Endereço da API</label>
      <input id="d-end" type="text" spellcheck="false" value="${S.esc(endpointAtual())}">
      <label for="d-mod">Modelo</label>
      <input id="d-mod" type="text" spellcheck="false" value="${S.esc(modeloAtual())}">
      <label for="d-key">Chave</label>
      <input id="d-key" type="password" autocomplete="off" spellcheck="false"
             placeholder="${S.cofre.get(K_LLM) ? 'já guardada — deixe em branco para manter' : 'cole aqui'}">
      <div class="aviso">Nada disso vai para o repositório: fica só no seu navegador.
        ${S.cofre.persistente ? 'Será lembrado neste computador.'
          : '<b>Neste ambiente o armazenamento local está bloqueado</b>, então valerá só nesta sessão.'}</div>
      <div class="acoes">
        ${S.cofre.get(K_LLM) ? '<button class="bt vazado" data-esq>Esquecer chave</button>' : ''}
        <button class="bt vazado" data-x>Cancelar</button>
        <button class="bt" data-ok>Salvar</button>
      </div></div>`;
    document.body.appendChild(v);
    const fim = ok => { v.remove(); resolve(ok); };
    v.querySelector('#d-key').focus();
    v.querySelector('[data-x]').onclick = () => fim(false);
    const esq = v.querySelector('[data-esq]');
    if (esq) esq.onclick = () => { S.cofre.del(K_LLM); fim(false); };
    v.querySelector('[data-ok]').onclick = () => {
      const end = v.querySelector('#d-end').value.trim();
      const mod = v.querySelector('#d-mod').value.trim();
      const key = v.querySelector('#d-key').value.trim();
      if (end) S.cofre.set(K_END, end);
      if (mod) S.cofre.set(K_MOD, mod);
      if (key) S.cofre.set(K_LLM, key);
      if (!S.cofre.get(K_LLM)) { v.querySelector('#d-key').focus(); return; }
      fim(true);
    };
    v.onclick = e => { if (e.target === v) fim(false); };
  });
}

function temChave(k) { return !!S.cofre.get(k); }

function pedirChave(k, titulo, texto, ajuda) {
  return new Promise(resolve => {
    const v = document.createElement('div');
    v.className = 'veu';
    v.innerHTML = `<div class="dialogo">
      <h3>${titulo}</h3>
      <p>${texto}</p>
      <div class="aviso">A chave fica <b>apenas no seu navegador</b> — não vai para o repositório,
        não é enviada a lugar nenhum além do serviço que você escolheu.
        ${S.cofre.persistente
          ? 'Ela será lembrada neste computador até você clicar em esquecer.'
          : '<b>Neste ambiente o navegador bloqueia o armazenamento local</b>, então será preciso digitar de novo a cada sessão. No GitHub Pages isso não acontece.'}</div>
      <label for="dlg-chave">Chave</label>
      <input id="dlg-chave" type="password" autocomplete="off" spellcheck="false" placeholder="cole aqui">
      ${ajuda ? `<p style="margin-top:8px;font-size:11.5px">${ajuda}</p>` : ''}
      <div class="acoes">
        <button class="bt vazado" data-x>Cancelar</button>
        <button class="bt" data-ok>Guardar e continuar</button>
      </div></div>`;
    document.body.appendChild(v);
    const inp = v.querySelector('#dlg-chave');
    inp.focus();
    const fim = val => { v.remove(); resolve(val); };
    v.querySelector('[data-x]').onclick = () => fim(null);
    v.querySelector('[data-ok]').onclick = () => {
      const val = inp.value.trim();
      if (!val) return inp.focus();
      S.cofre.set(k, val); fim(val);
    };
    inp.onkeydown = e => { if (e.key === 'Enter') v.querySelector('[data-ok]').click(); };
    v.onclick = e => { if (e.target === v) fim(null); };
  });
}

/* ================================================================
   FERRAMENTAS — o que o modelo pode pedir
   ================================================================ */
const FERRAMENTAS = [
  {
    type: 'function',
    function: {
      name: 'consultar_base',
      description: 'Consulta a base de territórios quilombolas do Observatório. Use SEMPRE que a pergunta envolver territórios específicos, contagens ou listas. Devolve os registros reais.',
      parameters: {
        type: 'object',
        properties: {
          uf: { type: 'string', description: 'sigla da UF, ex: MA' },
          fase: { type: 'array', items: { type: 'string', enum: ['EM_ELABORACAO','RTID','PORTARIA','DECRETO','TITULO_PARCIAL','TITULADO','CCDRU','TITULO_ANULADO','SEM_INFO'] } },
          esfera: { type: 'string', enum: ['FEDERAL', 'ESTADUAL'] },
          tem_protocolo: { type: 'boolean', description: 'território com protocolo de consulta prévia localizado' },
          tem_poligono: { type: 'boolean' },
          area_min: { type: 'number' }, area_max: { type: 'number' },
          familias_min: { type: 'number' },
          texto: { type: 'string', description: 'busca por nome do território, município ou código Seriema' },
          ordenar_por: { type: 'string', enum: ['area', 'familias', 'nome'] },
          limite: { type: 'number', description: 'máximo de registros (padrão 25, teto 60)' },
          detalhe: { type: 'boolean', description: 'true traz a ficha completa (certidões, localidades, protocolos). Use só para poucos territórios.' },
        },
      },
    },
  },
  {
    type: 'function',
    function: {
      name: 'resumo_agregado',
      description: 'Totais e contagens agrupados. Use para perguntas de panorama ("quantos por estado", "área total por fase") em vez de listar tudo.',
      parameters: {
        type: 'object',
        properties: {
          agrupar_por: { type: 'string', enum: ['uf', 'fase', 'esfera'] },
          filtros: { type: 'object', description: 'mesmos campos de consultar_base' },
        },
        required: ['agrupar_por'],
      },
    },
  },
  {
    type: 'function',
    function: {
      name: 'buscar_web',
      description: 'Busca informação atual na internet. Use para notícias, atos publicados depois do corte da base, ou contexto que a base não tem.',
      parameters: { type: 'object', properties: { consulta: { type: 'string' } }, required: ['consulta'] },
    },
  },
  {
    type: 'function',
    function: {
      name: 'propor_edicao',
      description: 'Propõe uma alteração na camada de curadoria. NÃO grava: a proposta é mostrada à pessoa para conferência. Use quando pedirem para registrar, corrigir, complementar ou remover informação.',
      parameters: {
        type: 'object',
        properties: {
          id: { type: 'string', description: 'código Seriema do território, ex: SRM-0159' },
          acao: { type: 'string', enum: ['definir', 'protocolo', 'confirmar_vinculo', 'inativar', 'reativar'] },
          campo: { type: 'string', description: 'para definir: caminho do campo (nome, municipios, area_ha, familias, observacao). Para confirmar_vinculo: fcp | ibge | poligono.' },
          valor: { description: 'novo valor. Para acao=protocolo, objeto {titulo, url, ano, fonte}.' },
          motivo: { type: 'string', description: 'justificativa curta — fica registrada no histórico público' },
        },
        required: ['id', 'acao', 'motivo'],
      },
    },
  },
];

/* ---------------- execução das ferramentas ---------------- */
async function executar(nome, args) {
  if (nome === 'consultar_base') {
    const lim = Math.min(args.limite || 25, 60);
    const r = S.consultar(args);
    const corte = r.slice(0, lim);
    const registros = args.detalhe
      ? corte.map(i => enxugarFicha(S.E.porId.get(i.id)))
      : corte.map(i => ({ id: i.id, nome: i.nome, uf: i.uf, municipios: i.mun, fase: i.fase,
                          esfera: i.esf, area_ha: i.area, familias: i.fam,
                          tem_protocolo: i.prot, tem_poligono: i.pol,
                          certidoes_fcp: i.cert, localidades_ibge: i.loc }));
    return { total_encontrado: r.length, exibindo: corte.length, registros,
             aviso: r.length > corte.length ? `mostrando ${corte.length} de ${r.length}` : undefined };
  }
  if (nome === 'resumo_agregado') return S.agregar(args.agrupar_por, args.filtros || {});
  if (nome === 'buscar_web') return await buscarWeb(args.consulta);
  if (nome === 'propor_edicao') return prepararEdicao(args);
  return { erro: 'ferramenta desconhecida' };
}

function enxugarFicha(f) {
  if (!f) return null;
  return {
    id: f.id, nome: f.nome, uf: f.uf, municipios: f.municipios, fase: f.fase,
    processo_incra: f.processo_incra, esfera: f.esfera, orgao: f.orgao_responsavel,
    area_ha: f.area_ha, familias: f.familias, tramite: f.tramite,
    coordenada: f.geo && f.geo.lat ? [f.geo.lat, f.geo.lon] : null, origem_ponto: f.geo_origem,
    certificacao: { n_certidoes: f.certificacao.n_certidoes, ano_primeira: f.certificacao.ano_primeira,
                    moradores: f.certificacao.moradores_fcp },
    ibge: { territorio: f.ibge.nm_tq, localidades: f.ibge.n_localidades },
    protocolos: (f.protocolo_consulta.itens || []).map(p => ({ titulo: p.titulo, ano: p.ano, url: p.url, fonte: p.fonte })),
    vinculos: f.vinculos, fontes: f.fontes,
    inativo: f._inativo || undefined, editado: f._editado || undefined,
  };
}

async function buscarWeb(consulta) {
  if (!CFG.busca.ativa) return { erro: 'busca na web desativada na configuração' };
  let chave = S.cofre.get(K_BUSCA);
  if (!chave) {
    chave = await pedirChave(K_BUSCA, 'Chave do serviço de busca',
      'Para consultar a internet, o painel precisa de uma chave de um serviço de busca. É separada da chave do modelo.',
      'Serviços com camada gratuita: Tavily, Serper ou Brave Search. Configure qual em <span class="mono">config.js</span>.');
    if (!chave) return { erro: 'busca cancelada pela pessoa' };
  }
  try {
    let req;
    if (CFG.busca.provedor === 'tavily') {
      req = fetch(CFG.busca.endpoint, { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ api_key: chave, query: consulta, max_results: CFG.busca.maxResultados, search_depth: 'basic' }) });
    } else if (CFG.busca.provedor === 'serper') {
      req = fetch(CFG.busca.endpoint, { method: 'POST', headers: { 'X-API-KEY': chave, 'Content-Type': 'application/json' },
        body: JSON.stringify({ q: consulta, gl: 'br', hl: 'pt-br' }) });
    } else {
      req = fetch(CFG.busca.endpoint + '?q=' + encodeURIComponent(consulta),
        { headers: { 'X-Subscription-Token': chave, Accept: 'application/json' } });
    }
    const d = await (await req).json();
    const lista = d.results || d.organic || (d.web && d.web.results) || [];
    return { consulta, resultados: lista.slice(0, CFG.busca.maxResultados).map(r => ({
      titulo: r.title, url: r.url || r.link, trecho: (r.content || r.snippet || r.description || '').slice(0, 400) })) };
  } catch (e) {
    return { erro: 'não foi possível buscar: ' + e.message + '. Pode ser bloqueio de CORS do provedor — nesse caso use um proxy.' };
  }
}

/* ================================================================
   EDIÇÃO — proposta, conferência, confirmação
   ================================================================ */
const CAMPOS_LIVRES = { nome: 'Nome', municipios: 'Municípios', area_ha: 'Área (ha)',
  familias: 'Famílias', observacao: 'Observação', processo_incra: 'Processo INCRA' };

function prepararEdicao(a) {
  const f = S.E.porId.get(a.id);
  if (!f) return { erro: `território ${a.id} não existe na base. Use consultar_base para achar o código correto.` };
  if (a.acao === 'definir' && !CAMPOS_LIVRES[a.campo])
    return { erro: `campo "${a.campo}" não é editável. Editáveis: ${Object.keys(CAMPOS_LIVRES).join(', ')}.` };
  const antes = a.acao === 'definir' ? S.lerCampo(f, a.campo)
    : a.acao === 'confirmar_vinculo' ? (f.vinculos || {})[a.campo]
    : a.acao === 'inativar' ? 'ativo' : a.acao === 'reativar' ? 'inativo' : null;
  const prop = { ...a, nome_territorio: f.nome, uf: f.uf, antes,
                 em: new Date().toISOString().slice(0, 19).replace('T', ' ') };
  mostrarDiff(prop);
  return { estado: 'aguardando conferência da pessoa',
           instrucao: 'A proposta foi exibida na tela para confirmação. Diga em uma frase o que foi proposto e avise que só valerá após a pessoa confirmar. Não afirme que já foi salvo.' };
}

function mostrarDiff(p) {
  const rotAcao = { definir: 'alterar campo', protocolo: 'registrar protocolo de consulta',
    confirmar_vinculo: 'confirmar vínculo', inativar: 'inativar registro', reativar: 'reativar registro' }[p.acao];
  const depois = p.acao === 'protocolo' ? (p.valor && p.valor.titulo) || JSON.stringify(p.valor)
    : p.acao === 'confirmar_vinculo' ? 'confirmado pela CFU'
    : p.acao === 'inativar' ? 'inativo' : p.acao === 'reativar' ? 'ativo'
    : Array.isArray(p.valor) ? p.valor.join(', ') : String(p.valor);
  const el = document.createElement('div');
  el.className = 'diff';
  el.innerHTML = `<div class="cab">Conferir antes de valer · ${rotAcao}</div>
    <div class="corpo">
      <div class="linha"><span class="rot">Território</span><span>${S.esc(p.nome_territorio)} <span class="mono">(${p.id} · ${p.uf})</span></span></div>
      ${p.acao === 'definir' || p.acao === 'confirmar_vinculo'
        ? `<div class="linha"><span class="rot">Campo</span><span class="mono">${S.esc(p.campo)}</span></div>` : ''}
      <div class="linha"><span class="rot">Antes</span><span class="antes">${S.esc(p.antes == null ? '(vazio)' : (Array.isArray(p.antes) ? p.antes.join(', ') : p.antes))}</span></div>
      <div class="linha"><span class="rot">Depois</span><span class="depois">${S.esc(depois)}</span></div>
      <div class="linha"><span class="rot">Motivo</span><span>${S.esc(p.motivo)}</span></div>
      ${p.acao === 'protocolo' && p.valor && p.valor.url
        ? `<div class="linha"><span class="rot">Link</span><span class="mono" style="word-break:break-all">${S.esc(p.valor.url)}</span></div>` : ''}
    </div>
    <div class="acoes">
      <button class="bt p laranja" data-ok>Confirmar</button>
      <button class="bt p vazado" data-x>Descartar</button>
    </div>`;
  $('#ia-fluxo').appendChild(el);
  rolar();
  el.querySelector('[data-ok]').onclick = () => {
    aplicar(p);
    el.querySelector('.acoes').innerHTML =
      `<span style="font-size:11.5px;color:var(--f4);padding:2px 0">✓ confirmada — pendente de publicação</span>`;
    el.querySelector('.cab').textContent = 'Alteração confirmada';
    el.style.borderColor = 'var(--f4)';
    el.querySelector('.cab').style.background = 'var(--f4)';
  };
  el.querySelector('[data-x]').onclick = () => el.remove();
}

function aplicar(p) {
  const ed = { id: p.id, acao: p.acao, campo: p.campo, valor: p.valor, motivo: p.motivo,
               em: p.em, por: S.cofre.get('seriema.autor') || 'CFU' };
  S.E.curadoria.edicoes = S.E.curadoria.edicoes || [];
  S.E.curadoria.edicoes.push(ed);
  S.E.pendentes.push(ed);
  // reaplica a curadoria inteira sobre a base carregada
  const f = S.E.porId.get(p.id);
  if (p.acao === 'inativar') f._inativo = { motivo: p.motivo, em: p.em, por: ed.por };
  else if (p.acao === 'reativar') delete f._inativo;
  else if (p.acao === 'definir') {
    const c = p.campo.split('.'); let o = f;
    for (let i = 0; i < c.length - 1; i++) o = o[c[i]] = o[c[i]] || {};
    o[c[c.length - 1]] = p.valor;
    (f._editado = f._editado || []).push({ campo: p.campo, em: p.em, por: ed.por });
  } else if (p.acao === 'protocolo') {
    f.protocolo_consulta = f.protocolo_consulta || { tem: false, n: 0, itens: [] };
    f.protocolo_consulta.itens.push({ ...p.valor, vinculo: 'curadoria', fonte: (p.valor && p.valor.fonte) || 'curadoria CFU' });
    f.protocolo_consulta.tem = true; f.protocolo_consulta.n = f.protocolo_consulta.itens.length;
    (f._editado = f._editado || []).push({ campo: 'protocolo_consulta', em: p.em, por: ed.por });
  } else if (p.acao === 'confirmar_vinculo') {
    f.vinculos[p.campo] = 'confirmado_curadoria';
  }
  const i = S.E.indice.find(x => x.id === p.id);
  if (i) { i.nome = f.nome; i.prot = !!(f.protocolo_consulta && f.protocolo_consulta.tem); i.inativo = !!f._inativo; }
  S.render();
}

/* ---------------- publicação no GitHub ---------------- */
function b64(str) {
  const b = new TextEncoder().encode(str);
  let s = ''; for (let i = 0; i < b.length; i += 0x8000) s += String.fromCharCode.apply(null, b.subarray(i, i + 0x8000));
  return btoa(s);
}

async function publicar() {
  const G = CFG.github;
  if (!S.E.pendentes.length) return;
  if (G.dono === 'SEU-USUARIO') {
    return alerta('Configure o repositório', 'Edite <span class="mono">config.js</span> e preencha <span class="mono">github.dono</span> e <span class="mono">github.repo</span> antes de publicar.');
  }
  let tok = S.cofre.get(K_GH);
  if (!tok) {
    tok = await pedirChave(K_GH, 'Token do GitHub',
      'Para gravar as edições no repositório. Use um <b>fine-grained token</b> restrito a este repositório, com permissão de Conteúdo (leitura e escrita) e validade curta.',
      CFG.repositorioPublico ? '<b>Atenção:</b> o repositório é público. Tudo que você gravou — inclusive observações e motivos — ficará visível na internet.' : '');
    if (!tok) return;
  }
  const cab = { Authorization: 'Bearer ' + tok, Accept: 'application/vnd.github+json', 'Content-Type': 'application/json' };
  const api = `https://api.github.com/repos/${G.dono}/${G.repo}`;
  const msg = `curadoria: ${S.E.pendentes.length} edição(ões) via Observatório Seriema`;
  const conteudo = b64(JSON.stringify({ versao: 1, atualizado_em: new Date().toISOString(),
                                        edicoes: S.E.curadoria.edicoes }, null, 1));
  falar('sis', 'Publicando…');
  try {
    let branch = G.branch;
    if (G.exigirRevisao) {
      const ref = await (await fetch(`${api}/git/ref/heads/${G.branch}`, { headers: cab })).json();
      branch = 'curadoria-' + Date.now().toString(36);
      const cr = await fetch(`${api}/git/refs`, { method: 'POST', headers: cab,
        body: JSON.stringify({ ref: 'refs/heads/' + branch, sha: ref.object.sha }) });
      if (!cr.ok) throw new Error('não foi possível criar a proposta: ' + (await cr.text()).slice(0, 160));
    }
    let sha = null;
    const at = await fetch(`${api}/contents/${G.caminhoCuradoria}?ref=${branch}`, { headers: cab });
    if (at.ok) sha = (await at.json()).sha;
    const put = await fetch(`${api}/contents/${G.caminhoCuradoria}`, { method: 'PUT', headers: cab,
      body: JSON.stringify({ message: msg, content: conteudo, branch, ...(sha ? { sha } : {}) }) });
    if (put.status === 409) throw new Error('a base de curadoria mudou desde que você carregou a página. Recarregue e refaça a edição, para não sobrescrever o trabalho de outra pessoa.');
    if (!put.ok) throw new Error((await put.text()).slice(0, 200));
    let extra = '';
    if (G.exigirRevisao) {
      const pr = await fetch(`${api}/pulls`, { method: 'POST', headers: cab,
        body: JSON.stringify({ title: msg, head: branch, base: G.branch,
          body: S.E.pendentes.map(e => `- **${e.id}** · ${e.acao} ${e.campo || ''} — ${e.motivo}`).join('\n') }) });
      const d = await pr.json();
      extra = d.html_url ? ` Proposta aberta para revisão: ${d.html_url}` : '';
    }
    S.E.pendentes = [];
    S.atualizarPendentes();
    falar('sis', `Publicado.${extra}`);
  } catch (e) {
    falar('sis', 'Não foi possível publicar: ' + e.message);
  }
}

function alerta(t, p) {
  const v = document.createElement('div');
  v.className = 'veu';
  v.innerHTML = `<div class="dialogo"><h3>${t}</h3><p>${p}</p>
    <div class="acoes"><button class="bt" data-x>Entendi</button></div></div>`;
  document.body.appendChild(v);
  v.querySelector('[data-x]').onclick = () => v.remove();
  v.onclick = e => { if (e.target === v) v.remove(); };
}

/* ================================================================
   CONVERSA
   ================================================================ */
function sistema() {
  const r = S.E.resumo;
  return `Você é o assistente do Observatório Seriema, painel de apoio à Coordenação de Governança Fundiária (CFU/SETEQ/MDA) sobre territórios quilombolas no Brasil.

REGRA CENTRAL: toda afirmação factual sobre territórios deve vir dos registros devolvidos pelas ferramentas. Nunca cite número, data, área ou nome de memória. Se a ferramenta não devolveu, diga que não consta na base. Conhecimento geral seu pode entrar como contexto, mas marcado explicitamente como tal.

A base tem ${r.n_territorios} territórios com processo no INCRA ou delimitação cartográfica, dados de ${CFG.dados.dataCorte}. Ela NÃO cobre comunidades apenas certificadas pela FCP sem processo aberto, nem povos e comunidades tradicionais não quilombolas.

Fases: EM_ELABORACAO, RTID, PORTARIA, DECRETO, TITULO_PARCIAL, TITULADO, CCDRU, TITULO_ANULADO.
Vínculos entre fontes vêm com selo: "confirmado" (nº de processo idêntico), "provavel" (nome+UF), "nao_localizado". Quando o dado depender de vínculo provável, avise.

Para panoramas e totais use resumo_agregado; para listas e casos use consultar_base. Cite os códigos (SRM-XXXX) dos territórios que sustentam a resposta.

Para pedidos de correção, use propor_edicao: a alteração aparece na tela para conferência humana e só vale depois de confirmada. Nunca diga que salvou algo — diga que propôs.

Responda em português do Brasil, direto, sem enrolação. Use listas curtas quando ajudar.`;
}

function falar(tipo, texto, fontes) {
  const d = document.createElement('div');
  d.className = 'msg ' + tipo;
  d.textContent = texto;
  if (fontes && fontes.length) {
    const f = document.createElement('div');
    f.className = 'fontes-ia';
    f.innerHTML = '<b>Consultou:</b> ' + fontes.map(x => S.esc(x)).join(' · ');
    d.appendChild(f);
  }
  $('#ia-fluxo').appendChild(d); rolar(); return d;
}
function passo(txt) {
  const d = document.createElement('div');
  d.className = 'passo';
  d.innerHTML = `<span class="pulso"></span><span>${S.esc(txt)}</span>`;
  $('#ia-fluxo').appendChild(d); rolar(); return d;
}
function rolar() { const f = $('#ia-fluxo'); f.scrollTop = f.scrollHeight; }

async function chamar(mensagens) {
  const chave = S.cofre.get(K_LLM);
  const cab = { 'Content-Type': 'application/json' };
  if (!CFG.llm.usarProxy && chave) cab.Authorization = 'Bearer ' + chave;
  cab['HTTP-Referer'] = location.origin;
  cab['X-Title'] = 'Observatorio Seriema';
  const r = await fetch(endpointAtual(), { method: 'POST', headers: cab,
    body: JSON.stringify({ model: modeloAtual(), messages: mensagens, tools: FERRAMENTAS,
      tool_choice: 'auto', temperature: CFG.llm.temperatura, max_tokens: CFG.llm.maxTokens }) });
  if (!r.ok) {
    const t = await r.text();
    if (r.status === 401 || r.status === 403) { S.cofre.del(K_LLM); throw new Error('chave recusada pelo serviço. Ela foi esquecida; tente de novo.'); }
    throw new Error(`o serviço respondeu ${r.status}. ${t.slice(0, 180)}`);
  }
  return (await r.json()).choices[0].message;
}

async function enviar() {
  if (ocupado) return;
  const cx = $('#ia-txt'), texto = cx.value.trim();
  if (!texto) return;
  if (!CFG.llm.usarProxy && !temChave(K_LLM)) {
    const ok = await dialogoServico();
    if (!ok) return;
  }
  cx.value = ''; cx.style.height = 'auto';
  falar('p', texto);
  ocupado = true; $('#ia-enviar').disabled = true;

  if (!historico.length) historico.push({ role: 'system', content: sistema() });
  historico.push({ role: 'user', content: texto });

  const usadas = [];
  let p = passo('pensando…');
  try {
    for (let volta = 0; volta < 4; volta++) {
      const m = await chamar(historico);
      historico.push(m);
      if (m.tool_calls && m.tool_calls.length) {
        p.remove();
        for (const tc of m.tool_calls) {
          let args = {};
          try { args = JSON.parse(tc.function.arguments || '{}'); } catch (e) {}
          const rot = { consultar_base: 'consultando a base', resumo_agregado: 'somando os grupos',
                        buscar_web: 'buscando na internet', propor_edicao: 'preparando a alteração' }[tc.function.name] || tc.function.name;
          p = passo(rot + '…');
          const res = await executar(tc.function.name, args);
          usadas.push(tc.function.name === 'consultar_base'
            ? `base (${res.total_encontrado != null ? res.total_encontrado + ' registros' : '—'})`
            : tc.function.name === 'buscar_web' ? 'internet' : tc.function.name);
          historico.push({ role: 'tool', tool_call_id: tc.id, content: JSON.stringify(res).slice(0, 24000) });
          p.remove();
        }
        p = passo('redigindo…');
        continue;
      }
      p.remove();
      falar('a', (m.content || '').trim() || '(sem resposta)', [...new Set(usadas)]);
      break;
    }
  } catch (e) {
    p.remove();
    falar('sis', 'Não deu para consultar: ' + e.message);
  } finally {
    ocupado = false; $('#ia-enviar').disabled = false; rolar();
  }
}

/* ================================================================
   INÍCIO
   ================================================================ */
function iniciar(ctx) {
  S = ctx;
  const persist = S.cofre.persistente;
  $('#ia-fluxo').innerHTML =
    `<div class="msg sis">O assistente consulta a base carregada e, se você quiser, a internet.
       Ele não inventa números: o que afirmar vem dos registros.</div>`;
  falar('a', `Pergunte sobre os ${S.E.resumo.n_territorios} territórios — ou peça uma correção na base.

Exemplos:
· quais territórios titulados na Bahia têm protocolo de consulta?
· quantos processos por fase no Maranhão, e qual a área somada?
· liste os cinco maiores territórios sem polígono cartográfico
· no SRM-0159, registre o protocolo publicado em 2023 com o link tal`);
  if (!persist) falar('sis', 'Neste ambiente o navegador bloqueia o armazenamento local: a chave será pedida a cada sessão. No GitHub Pages ela é lembrada.');

  $('#ia-enviar').onclick = enviar;
  const barra = document.createElement('div');
  barra.style.cssText = 'display:flex;gap:6px;padding:6px 10px 0;justify-content:flex-end';
  barra.innerHTML = '<button class="bt p vazado" id="bt-config">Serviço e chave</button>';
  $('#ia-txt').closest('.ia-entrada').before(barra);
  $('#bt-config').onclick = dialogoServico;
  const cx = $('#ia-txt');
  cx.onkeydown = e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); enviar(); } };
  cx.oninput = () => { cx.style.height = 'auto'; cx.style.height = Math.min(cx.scrollHeight, 120) + 'px'; };
  $('#bt-publicar').onclick = publicar;
}

return { iniciar, publicar };
})();
