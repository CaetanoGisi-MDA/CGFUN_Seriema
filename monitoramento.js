/* ================================================================
   Observatório Seriema — módulo de Monitoramento prioritário
   Integra ao núcleo (seriema.js): usa E, cofre, funções compartilhadas.
   Dados: base/monitoramento_seed.json (semente) + curadoria/monitoramento.json
   (edições da CFU), fundidos na carga, curadoria prevalecendo.
   Gravação no GitHub via Assistente.publicarMonitoramento().
   ================================================================ */
window.Monitoramento = (function () {
'use strict';

let S = null;                 // contexto do núcleo (injetado em iniciar)
const $ = s => document.querySelector(s);

const FASES = { '': '— sem fase —', certidao: 'Certidão FCP', rtid: 'RTID',
                portaria: 'Portaria', decreto: 'Decreto', titulo: 'Título' };
// mapeia a fase curta do monitoramento para a fase canônica da base (trilha)
const FASE_PARA_BASE = { certidao: 'certidao', rtid: 'RTID', portaria: 'PORTARIA',
                         decreto: 'DECRETO', titulo: 'TITULADO' };

const M = {
  processos: [],            // fundido: seed + curadoria
  operacoes: [],            // curadoria a publicar (novos + edições)
  pendentes: 0,
  abertos: new Set(),
  contexto: null,           // processo em foco em algum diálogo
  filaVencidos: [],
  ordenar: 'urgencia',
  busca: '',
  grupoTerritorio: null,    // filtra a tabela por um território (vindo do mapa)
};

const hojeISO = () => new Date().toISOString().slice(0, 10);
const semAcento = s => String(s || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();

/* ---------------- tempo ---------------- */
function diasEntre(aISO, bISO) {
  return Math.round((new Date(bISO + 'T12:00:00') - new Date(aISO + 'T12:00:00')) / 86400000);
}
function fmtBR(iso) { if (!iso) return '—'; const [y, m, d] = iso.split('-'); return `${d}/${m}/${y}`; }
function tempoRelativo(iso) {
  if (!iso) return '—';
  const d = diasEntre(iso, hojeISO());
  if (d === 0) return 'hoje'; if (d === 1) return 'há 1 dia';
  if (d < 30) return `há ${d} dias`;
  const m = Math.round(d / 30); return m === 1 ? 'há 1 mês' : `há ${m} meses`;
}
function statusTimer(iso) {
  if (!iso) return { cls: 'semtimer', txt: 'sem verificação programada', dias: null };
  const dias = diasEntre(hojeISO(), iso);
  if (dias < 0) return { cls: 'venc', txt: `vencido há ${Math.abs(dias)} dia(s)`, dias };
  if (dias <= 7) return { cls: 'perto', txt: `em ${dias} dia(s)`, dias };
  return { cls: 'ok', txt: dias < 60 ? `em ${dias} dias` : `em ${Math.round(dias / 30)} meses`, dias };
}

/* ================================================================
   CARGA E FUSÃO (seed + curadoria)
   ================================================================ */
async function carregar() {
  const emb = window.SERIEMA_MON_EMBUTIDO;   // usado na prévia de arquivo único
  let seed, cur;
  if (emb) { seed = emb.seed; cur = emb.curadoria; }
  else {
    const pega = async f => { const r = await fetch(f, { cache: 'no-store' }); return r.ok ? r.json() : null; };
    seed = await pega(S.CFG.dados.base + 'monitoramento_seed.json') || { processos: [] };
    cur  = await pega(S.CFG.dados.curadoria.replace('edicoes.json', 'monitoramento.json'))
         || { operacoes: [] };
  }
  // clona a semente e aplica as operações de curadoria por cima
  M.processos = JSON.parse(JSON.stringify(seed.processos || []));
  S.E.curadoriaMon = cur;   // guarda para o publicar() acumular corretamente
  const porId = new Map(M.processos.map(p => [p.id, p]));
  (cur.operacoes || []).forEach(op => {
    if (op.acao === 'novo') {
      if (!porId.has(op.processo.id)) { M.processos.push(op.processo); porId.set(op.processo.id, op.processo); }
    } else if (op.acao === 'editar') {
      const p = porId.get(op.id); if (p) Object.assign(p, op.campos);
    } else if (op.acao === 'inserir_c') {
      const p = porId.get(op.id); if (p) { p.blocoC = p.blocoC || []; p.blocoC.unshift(op.item); }
    } else if (op.acao === 'excluir') {
      const p = porId.get(op.id); if (p) p._excluido = true;
    }
  });
  M.processos = M.processos.filter(p => !p._excluido);
}

/* registra uma operação de curadoria (fica pendente até publicar) */
function registrarOperacao(op) {
  op.em = new Date().toISOString();
  op.por = S.cofre.get('seriema.autor') || 'CFU';
  M.operacoes.push(op);
  M.pendentes = M.operacoes.length;
  if (S.marcarPendentesMonitoramento) S.marcarPendentesMonitoramento(M.pendentes);
}

/* ================================================================
   RENDERIZAÇÃO DA TABELA
   ================================================================ */
function ordenar(lista) {
  const arr = [...lista];
  const c = M.ordenar;
  if (c === 'nivel') { const o = { critico: 0, atencao: 1, rotina: 2 }; return arr.sort((a, b) => o[a.nivel] - o[b.nivel]); }
  if (c === 'atualizacao') return arr.sort((a, b) => (b.editadoEm || '').localeCompare(a.editadoEm || ''));
  if (c === 'nome') return arr.sort((a, b) => a.territorio.localeCompare(b.territorio, 'pt-BR'));
  if (c === 'manual') return arr.sort((a, b) => (a.ordem || 0) - (b.ordem || 0));
  // urgência (padrão): vencidos primeiro, depois por dias, sem-timer por último
  return arr.sort((a, b) => {
    const sa = statusTimer(a.timer), sb = statusTimer(b.timer);
    const pa = a.timer == null ? 9999 : (sa.dias < 0 ? sa.dias : sa.dias + 0.5);
    const pb = b.timer == null ? 9999 : (sb.dias < 0 ? sb.dias : sb.dias + 0.5);
    return pa - pb;
  });
}

function render() {
  const cont = $('#mon-corpo'); if (!cont) return;
  const termo = semAcento(M.busca);
  let lista = M.processos.filter(p =>
    !termo || semAcento(p.proc).includes(termo) || semAcento(p.territorio).includes(termo) || semAcento(p.loc).includes(termo));
  if (M.grupoTerritorio) lista = lista.filter(p => p.srm === M.grupoTerritorio || p.territorio === M.grupoTerritorio);
  lista = ordenar(lista);

  $('#mon-contagem').textContent =
    `${M.processos.length} processo(s) · ${new Set(M.processos.map(p => p.srm || p.territorio)).size} território(s)`;
  const cf = $('#mon-contfiltro');
  if (cf) cf.textContent = lista.length === M.processos.length ? '' : `${lista.length} de ${M.processos.length}`;

  if (!lista.length) {
    cont.innerHTML = `<tr><td colspan="6"><div class="vazio">Nenhum processo com esses filtros.</div></td></tr>`;
    return;
  }

  cont.innerHTML = '';
  lista.forEach(p => {
    const aberto = M.abertos.has(p.id);
    const st = statusTimer(p.timer);
    const reval = p.timer
      ? `<span class="mon-faltam ${st.cls}">${st.txt}</span><span class="mon-alvo">${fmtBR(p.timer)}</span>`
      : `<span class="mon-semtimer">sem verificação</span>`;
    const vTit = { confirmado: `vinculado a ${p.srm}`, sem: 'sem território na base', pendente: 'vínculo não verificado' }[p.vinculo] || '';

    const tr = document.createElement('tr');
    tr.className = 'mon-linha' + (aberto ? ' aberta' : '');
    tr.innerHTML = `
      <td><span class="mon-chip ${p.nivel}">${p.proc}<span class="mon-seta">▸</span></span></td>
      <td><div class="mon-terr">${S.esc(p.territorio)}</div><div class="mon-loc">${S.esc(p.loc)}</div></td>
      <td>${p.fase ? `<span class="mon-fase">${FASES[p.fase]}${p.fase === 'titulo' && p.tituloTipo === 'parcial' ? ' (parcial)' : ''}</span>` : `<span class="mon-fase vazia">sem fase</span>`}</td>
      <td class="mon-reval">${reval}<span class="mon-editado">editado ${tempoRelativo(p.editadoEm)}</span></td>
      <td><span class="mon-vinc" data-t="${p.vinculo}" title="${vTit}">●</span></td>`;
    tr.onclick = () => { M.abertos.has(p.id) ? M.abertos.delete(p.id) : M.abertos.add(p.id); render(); };
    cont.appendChild(tr);

    const trd = document.createElement('tr');
    trd.className = 'mon-detrow';
    trd.innerHTML = `<td colspan="6"><div class="mon-det${aberto ? ' on' : ''}" id="mon-det-${p.id}">${detalhe(p)}</div></td>`;
    cont.appendChild(trd);
  });
}

function detalhe(p) {
  const st = statusTimer(p.timer);
  const timerHTML = p.timer
    ? `<span class="mon-tvalor ${st.cls}">${st.txt}</span><span class="mon-tdata">alvo: ${fmtBR(p.timer)}</span>
       <button class="bt p vazado" style="margin-left:auto" data-mon="timer" data-id="${p.id}">Alterar data</button>`
    : `<span class="mon-semtimer">Nenhuma verificação programada.</span>
       <button class="bt p laranja" style="margin-left:auto" data-mon="timer" data-id="${p.id}">Definir verificação</button>`;

  const c = (p.blocoC && p.blocoC.length)
    ? p.blocoC.map(x => `<div class="mon-itemc"><div class="l1"><span class="tit">${S.esc(x.t)}</span><span class="dt">${S.esc(x.d || '')}</span></div><div class="txt">${S.esc(x.x)}</div></div>`).join('')
    : '<div class="nota" style="color:var(--tinta-3)">Nenhuma inserção ainda.</div>';

  const rotVinc = p.vinculo === 'confirmado' ? `Vinculado: ${p.srm}` : 'Vincular território';

  return `
    <div class="mon-dettopo">
      ${p.link ? `<a class="mon-sei" href="${S.esc(p.link)}" target="_blank" rel="noopener">${p.proc} — abrir no SEI ↗</a>`
               : `<span class="mono" style="font-size:12px;color:var(--tinta-2)">${p.proc}</span>`}
      <button class="bt p vazado" style="margin-left:auto" data-mon="vincular" data-id="${p.id}">${rotVinc}</button>
    </div>

    <div class="mon-timerbox"><span class="mon-trot">Próxima verificação</span>${timerHTML}</div>

    <div class="mon-resumo">
      <div class="mon-dataup">Resumo · editado ${tempoRelativo(p.editadoEm)}
        <button class="bt-editar" data-mon="resumo" data-id="${p.id}">editar</button></div>
      <div class="txt" id="mon-resumo-${p.id}">${S.esc(p.resumo || '(sem resumo)')}</div>
    </div>

    <div class="mon-blocos">
      <div class="mon-bloco">
        <h4>Bloco A — Identificação</h4>
        <dl class="kv">
          <dt>Ação judicial</dt><dd>${S.esc(p.acao || '—')}</dd>
          <dt>Processo(s) INCRA</dt><dd>${S.esc(p.incra || '—')}</dd>
          <dt>Código Seriema</dt><dd>${p.srm ? `<a href="#" data-mon="irterr" data-srm="${p.srm}">${p.srm}</a>` : '—'}</dd>
        </dl>
      </div>
      <div class="mon-bloco" id="mon-blocoB-${p.id}">
        <h4>Bloco B — Status <button class="bt-editar" data-mon="blocoB" data-id="${p.id}">editar</button></h4>
        <dl class="kv">
          <dt>Nível de atenção</dt><dd>
            <select data-mon="nivel" data-id="${p.id}" class="mon-selnivel">
              <option value="critico" ${p.nivel === 'critico' ? 'selected' : ''}>Crítico</option>
              <option value="atencao" ${p.nivel === 'atencao' ? 'selected' : ''}>Atenção</option>
              <option value="rotina" ${p.nivel === 'rotina' ? 'selected' : ''}>Rotina</option>
            </select></dd>
          <dt>Fase</dt><dd>
            <select data-mon="fase" data-id="${p.id}" class="mon-selfase">
              ${Object.entries(FASES).map(([k, v]) => `<option value="${k}" ${p.fase === k ? 'selected' : ''}>${v}</option>`).join('')}
            </select>${p.fase === 'titulo' ? `
            <select data-mon="titulotipo" data-id="${p.id}" class="mon-selfase" style="margin-left:4px">
              <option value="integral" ${p.tituloTipo !== 'parcial' ? 'selected' : ''}>integral</option>
              <option value="parcial" ${p.tituloTipo === 'parcial' ? 'selected' : ''}>parcial</option>
            </select>` : ''}</dd>
          <dt>Prazo judicial</dt><dd><span style="color:${p.prazoAtivo ? 'var(--critico)' : 'var(--tinta-2)'};font-weight:${p.prazoAtivo ? '700' : '400'}">${p.prazoAtivo ? 'Em curso' : 'Não há'}</span></dd>
          <dt>Conflito em curso</dt><dd>${S.esc(p.conflito || '—')}</dd>
          <dt>DEMCA</dt><dd>${S.esc(p.demca || '—')}</dd>
        </dl>
      </div>
    </div>

    <div class="mon-c">
      <h4>Bloco C — Inserções ad hoc</h4>
      ${c}
      <div id="mon-formc-${p.id}"></div>
      <button class="bt-add-c" data-mon="addc" data-id="${p.id}">+ Adicionar inserção</button>
    </div>`;
}

/* ================================================================
   EDIÇÃO — cada mudança passa por registrarEdicao (pergunta timer)
   ================================================================ */
function proc(id) { return M.processos.find(p => p.id === id); }

/* registra a edição no dado + curadoria, e se havia timer pergunta o que fazer */
function registrarEdicao(p, campos, aoTerminar) {
  Object.assign(p, campos);
  p.editadoEm = hojeISO();
  registrarOperacao({ acao: 'editar', id: p.id, campos: { ...campos, editadoEm: p.editadoEm } });

  if (p.timer) {
    M.contexto = p;
    M._aoTerminar = aoTerminar || render;
    const st = statusTimer(p.timer);
    $('#mon-te-texto').innerHTML = st.dias < 0
      ? `Este processo tinha verificação para <b>${fmtBR(p.timer)}</b> — já venceu. O que deseja?`
      : `Este processo já tem verificação para <b>${fmtBR(p.timer)}</b> (${st.txt}).`;
    const dt = $('#mon-te-data'); dt.value = p.timer; dt.style.display = 'none';
    document.querySelectorAll('input[name=mon-topc]').forEach(r => {
      r.checked = r.value === 'manter';
      r.onchange = () => dt.style.display = (r.value === 'nova' && r.checked) ? 'block' : 'none';
    });
    abrir('mon-veu-timer');
  } else { (aoTerminar || render)(); }
}

function confirmarTimerEdicao() {
  const opc = document.querySelector('input[name=mon-topc]:checked').value;
  if (opc === 'nova') {
    const nd = $('#mon-te-data').value;
    if (nd) { M.contexto.timer = nd; registrarOperacao({ acao: 'editar', id: M.contexto.id, campos: { timer: nd } }); }
  }
  fechar('mon-veu-timer');
  (M._aoTerminar || render)();
}

/* --- ações do Bloco B --- */
function mudarNivel(id, v) { registrarEdicao(proc(id), { nivel: v }, render); }

function mudarFase(id, v) {
  const p = proc(id);
  const antes = p.fase;
  // se o processo é vinculado e a fase avançou, oferece sincronizar a base
  registrarEdicao(p, { fase: v }, () => {
    render();
    if (p.vinculo === 'confirmado' && p.srm && v && v !== antes && FASE_PARA_BASE[v]) {
      abrirSincronizarFase(p, v);
    }
  });
}
function mudarTituloTipo(id, v) { registrarEdicao(proc(id), { tituloTipo: v }, render); }

function editarResumo(id) {
  const p = proc(id);
  const box = $(`#mon-resumo-${id}`);
  box.outerHTML = `<textarea class="mon-editresumo" id="mon-editres-${id}">${S.esc(p.resumo || '')}</textarea>
    <div class="mon-acoes-edit">
      <button class="bt p vazado" data-mon="cancel" data-id="${id}">Cancelar</button>
      <button class="bt p laranja" data-mon="salvaresumo" data-id="${id}">Salvar</button>
    </div>`;
}
function salvarResumo(id) {
  const p = proc(id);
  registrarEdicao(p, { resumo: $(`#mon-editres-${id}`).value }, render);
}

function editarBlocoB(id) {
  const p = proc(id);
  const dl = $(`#mon-blocoB-${id}`).querySelector('.kv');
  // troca o bloco inteiro de uma vez (nunca insere ao lado — evita duplicação)
  dl.outerHTML = `<dl class="kv" id="mon-editB-${id}">
    <dt>Conflito em curso</dt><dd><input id="mon-eb-conflito-${id}" value="${S.esc(p.conflito || '')}"></dd>
    <dt>DEMCA</dt><dd><input id="mon-eb-demca-${id}" value="${S.esc(p.demca || '')}"></dd>
    <dt>Prazo judicial</dt><dd><label style="font-weight:400;text-transform:none;letter-spacing:0;font-size:12px;display:flex;align-items:center;gap:6px">
      <input type="checkbox" id="mon-eb-prazo-${id}" ${p.prazoAtivo ? 'checked' : ''} style="width:auto"> há prazo judicial em curso</label></dd>
    <dt></dt><dd class="mon-acoes-edit">
      <button class="bt p vazado" data-mon="cancel" data-id="${id}">Cancelar</button>
      <button class="bt p laranja" data-mon="salvaB" data-id="${id}">Salvar</button></dd>
  </dl>`;
}
function salvarBlocoB(id) {
  const p = proc(id);
  registrarEdicao(p, {
    conflito: $(`#mon-eb-conflito-${id}`).value,
    demca: $(`#mon-eb-demca-${id}`).value,
    prazoAtivo: $(`#mon-eb-prazo-${id}`).checked,
  }, render);
}

/* --- Bloco C inline --- */
function abrirFormC(id) {
  $(`#mon-formc-${id}`).innerHTML = `<div class="mon-formadd">
    <input id="mon-ct-${id}" placeholder="Título curto">
    <textarea id="mon-cx-${id}" placeholder="Conteúdo da anotação…"></textarea>
    <div class="mon-acoes-edit">
      <button class="bt p vazado" data-mon="fecharc" data-id="${id}">Cancelar</button>
      <button class="bt p laranja" data-mon="salvac" data-id="${id}">Salvar inserção</button>
    </div></div>`;
}
function salvarItemC(id) {
  const t = $(`#mon-ct-${id}`).value.trim(), x = $(`#mon-cx-${id}`).value.trim();
  if (!t || !x) { alert('Título e conteúdo são obrigatórios.'); return; }
  const p = proc(id);
  const item = { t, d: fmtBR(hojeISO()), x };
  p.blocoC = p.blocoC || []; p.blocoC.unshift(item);
  p.editadoEm = hojeISO();
  registrarOperacao({ acao: 'inserir_c', id, item });
  registrarOperacao({ acao: 'editar', id, campos: { editadoEm: p.editadoEm } });
  // ainda pergunta o timer, como qualquer edição
  if (p.timer) registrarEdicao(p, {}, render); else render();
}

/* --- timer manual --- */
function abrirDefinirTimer(id) {
  M.contexto = proc(id);
  $('#mon-dt-texto').textContent = M.contexto.timer
    ? `Verificação atual: ${fmtBR(M.contexto.timer)}. Defina uma nova data.`
    : 'Defina a data da próxima verificação deste processo.';
  $('#mon-dt-data').value = M.contexto.timer || '';
  abrir('mon-veu-deftimer');
}
function confirmarDefinirTimer() {
  const nd = $('#mon-dt-data').value;
  M.contexto.timer = nd || null; M.contexto.editadoEm = hojeISO();
  registrarOperacao({ acao: 'editar', id: M.contexto.id, campos: { timer: M.contexto.timer, editadoEm: M.contexto.editadoEm } });
  fechar('mon-veu-deftimer'); render();
}

/* ================================================================
   VÍNCULO COM TERRITÓRIO
   ================================================================ */
function abrirVincular(id) {
  const p = proc(id); M.contexto = p;
  if (p.vinculo === 'confirmado') { irParaTerritorio(p.srm); return; }
  // busca candidatos na base por nome+UF
  const uf = (p.loc.split('/')[1] || '').trim();
  const nb = semAcento(p.territorio.split('+')[0].split('(')[0]);
  const cand = S.E.fichas.filter(f => f.uf === uf && semAcento(f.nome).includes(nb.slice(0, 8))).slice(0, 5);
  $('#mon-vinc-texto').innerHTML = `Buscando território para <b>${S.esc(p.territorio)}</b>, ${S.esc(p.loc)}…`;
  $('#mon-vinc-lista').innerHTML = cand.length
    ? cand.map(f => `<div class="mon-vinc-res"><b class="mono">${f.id}</b> — ${S.esc(f.nome)}, ${S.esc((f.municipios || []).join(', '))}
        <button class="bt p" data-mon="confvinc" data-id="${id}" data-srm="${f.id}">Vincular</button></div>`).join('')
    : `<div class="nota" style="color:var(--tinta-3)">Nenhum candidato encontrado por nome + UF.</div>`;
  abrir('mon-veu-vincular');
}
function confirmarVinculo(id, srm) {
  const p = proc(id);
  registrarEdicao(p, { vinculo: 'confirmado', srm }, () => { fechar('mon-veu-vincular'); render(); if (S.render) S.render(); });
}

function irParaTerritorio(srm) {
  const f = S.E.porId.get(srm);
  if (!f) return;
  S.irParaModulo('mapa');
  S.selecionar(srm, true);
}

/* ================================================================
   SINCRONIZAÇÃO DE FASE COM A BASE (grava em edicoes.json)
   ================================================================ */
function abrirSincronizarFase(p, faseNova) {
  M.contexto = p; M._faseNova = faseNova;
  const faseBase = FASE_PARA_BASE[faseNova];
  const f = S.E.porId.get(p.srm);
  $('#mon-sf-texto').innerHTML =
    `A fase do processo <b class="mono">${p.proc}</b> mudou para <b>${FASES[faseNova]}</b>.
     Deseja atualizar também a ficha do território <b>${S.esc(f ? f.nome : p.srm)}</b> na base?`;
  // campos condicionais: portaria/decreto/título pedem data (e nº opcional)
  const pedeData = ['portaria', 'decreto', 'titulo'].includes(faseNova);
  $('#mon-sf-campos').innerHTML = pedeData
    ? `<label>Data do ato (${FASES[faseNova]})</label>
       <input type="date" id="mon-sf-data">
       <label>Número do ato (opcional)</label>
       <input type="text" id="mon-sf-num" placeholder="ex.: Decreto nº 13.024">`
    : '<div class="nota">Esta fase não exige data de ato para a trilha.</div>';
  abrir('mon-veu-sincfase');
}
function confirmarSincronizarFase() {
  const p = M.contexto, faseNova = M._faseNova, faseBase = FASE_PARA_BASE[faseNova];
  const f = S.E.porId.get(p.srm);
  const dataEl = $('#mon-sf-data'), numEl = $('#mon-sf-num');
  const data = dataEl ? dataEl.value : null;
  const num = numEl ? numEl.value.trim() : '';
  if (dataEl && !data) { alert('A data do ato é obrigatória para atualizar a trilha do território.'); return; }

  // aplica na ficha em memória e registra edição de curadoria (edicoes.json via núcleo)
  if (f) {
    f.tramite = f.tramite || {};
    if (faseNova === 'portaria') f.tramite.portaria = data;
    else if (faseNova === 'decreto') f.tramite.decreto = data;
    else if (faseNova === 'titulo') f.tramite.titulacao = data;
    else if (faseNova === 'rtid') f.tramite.rtid_edital_1 = f.tramite.rtid_edital_1 || data;
    f.fase = faseBase;
    if (num) { f.tramite.titulo_txt = (faseNova === 'titulo') ? num : f.tramite.titulo_txt; }
    // usa o mecanismo de curadoria do núcleo, se disponível
    if (S.registrarEdicaoBase) {
      S.registrarEdicaoBase({
        id: p.srm, acao: 'definir', campo: 'fase', valor: faseBase,
        motivo: `sincronização via monitoramento (processo MDA ${p.proc}); ${FASES[faseNova]}${data ? ' em ' + fmtBR(data) : ''}${num ? ', ' + num : ''}`,
      });
      if (data) {
        const campoTramite = { portaria: 'tramite.portaria', decreto: 'tramite.decreto', titulo: 'tramite.titulacao', rtid: 'tramite.rtid_edital_1' }[faseNova];
        if (campoTramite) S.registrarEdicaoBase({ id: p.srm, acao: 'definir', campo: campoTramite, valor: data,
          motivo: `sincronização via monitoramento (processo MDA ${p.proc})` });
      }
    }
    if (S.render) S.render();
  }
  fechar('mon-veu-sincfase');
  falarOK(`Ficha de ${f ? f.nome : p.srm} atualizada para ${FASES[faseNova]}.`);
}

/* ================================================================
   TIMERS VENCIDOS — fila ao abrir o módulo
   ================================================================ */
function checarVencidos() {
  M.filaVencidos = M.processos.filter(p => p.timer && statusTimer(p.timer).dias < 0)
    .sort((a, b) => statusTimer(a.timer).dias - statusTimer(b.timer).dias);
  atualizarAlertaCabecalho();
  if (M.filaVencidos.length) proximoVencido();
}
function proximoVencido() {
  if (!M.filaVencidos.length) return;
  const p = M.filaVencidos[0]; M.contexto = p;
  const st = statusTimer(p.timer);
  $('#mon-venc-texto').innerHTML =
    `O processo <b class="mono">${p.proc}</b> (${S.esc(p.territorio)}) tinha verificação para <b>${fmtBR(p.timer)}</b> — venceu ${st.txt}.`;
  $('#mon-venc-data').value = '';
  $('#mon-venc-fila').textContent = M.filaVencidos.length > 1 ? `+${M.filaVencidos.length - 1} na fila` : '';
  abrir('mon-veu-vencido');
}
function confirmarVencido() {
  const nd = $('#mon-venc-data').value;
  M.contexto.timer = nd || null; M.contexto.editadoEm = hojeISO();
  registrarOperacao({ acao: 'editar', id: M.contexto.id, campos: { timer: M.contexto.timer, editadoEm: M.contexto.editadoEm } });
  M.filaVencidos.shift();
  fechar('mon-veu-vencido');
  atualizarAlertaCabecalho();
  if (M.filaVencidos.length) setTimeout(proximoVencido, 200); else render();
}
function adiarVencido() {
  M.filaVencidos.shift();
  fechar('mon-veu-vencido');
  if (M.filaVencidos.length) setTimeout(proximoVencido, 200);
}
function abrirProcessoVencido() {
  const id = M.contexto.id;
  fechar('mon-veu-vencido');
  M.ordenar = 'urgencia'; $('#mon-ordenar').value = 'urgencia';
  M.abertos.add(id); render();
  setTimeout(() => { const tr = [...document.querySelectorAll('.mon-linha')].find(t => t.querySelector('.mon-chip')?.textContent.includes(id)); }, 50);
}
function atualizarAlertaCabecalho() {
  const venc = M.processos.filter(p => p.timer && statusTimer(p.timer).dias < 0).length;
  const a = $('#nav-mon-alerta');
  if (a) a.style.display = venc ? 'inline-block' : 'none';
}

/* ================================================================
   NOVO PROCESSO
   ================================================================ */
function abrirNovo(prefill) {
  ['mon-f-proc', 'mon-f-link', 'mon-f-terr', 'mon-f-loc', 'mon-f-acao', 'mon-f-incra', 'mon-f-resumo', 'mon-f-timer'].forEach(id => { const el = $('#' + id); if (el) el.value = ''; });
  $('#mon-f-nivel').value = 'atencao'; $('#mon-f-fase').value = '';
  if (prefill) { $('#mon-f-terr').value = prefill.nome || ''; $('#mon-f-loc').value = prefill.loc || ''; if (prefill.srm) $('#mon-f-srm').value = prefill.srm; }
  $('#mon-f-srm').value = prefill && prefill.srm ? prefill.srm : '';
  abrir('mon-veu-novo');
}
function salvarNovo() {
  const pr = $('#mon-f-proc').value.trim(), terr = $('#mon-f-terr').value.trim();
  if (!pr || !terr) { alert('Nº do processo e território são obrigatórios.'); return; }
  const srm = $('#mon-f-srm').value.trim() || null;
  const novo = {
    id: 'MON-' + Date.now().toString(36).toUpperCase(),
    proc: pr, nivel: $('#mon-f-nivel').value,
    territorio: terr, loc: $('#mon-f-loc').value.trim() || '—',
    fase: $('#mon-f-fase').value,
    link: $('#mon-f-link').value.trim() || null,
    vinculo: srm ? 'confirmado' : 'sem', srm,
    timer: $('#mon-f-timer').value || null,
    editadoEm: hojeISO(), criadoEm: hojeISO(),
    resumo: $('#mon-f-resumo').value.trim() || '(sem resumo ainda)',
    acao: $('#mon-f-acao').value.trim() || '—',
    incra: $('#mon-f-incra').value.trim() || '—',
    prazoAtivo: false, conflito: 'Não verificado', demca: 'Não aplicável', blocoC: [],
  };
  M.processos.push(novo);
  registrarOperacao({ acao: 'novo', processo: novo });
  fechar('mon-veu-novo'); render();
  if (!srm) setTimeout(() => abrirVincular(novo.id), 250);
}

/* ================================================================
   DIÁLOGOS: abrir/fechar + delegação de cliques
   ================================================================ */
function abrir(id) { const v = $('#' + id); if (v) v.classList.add('on'); }
function fechar(id) { const v = $('#' + id); if (v) v.classList.remove('on'); }
function falarOK(msg) {
  const t = document.createElement('div'); t.className = 'mon-toast'; t.textContent = msg;
  document.body.appendChild(t); setTimeout(() => t.remove(), 3200);
}

/* delegação: todos os data-mon dentro da tabela e diálogos */
function ligarEventos() {
  $('#tela-mon').addEventListener('click', e => {
    const el = e.target.closest('[data-mon]'); if (!el) return;
    e.stopPropagation();
    const id = el.dataset.id, acao = el.dataset.mon;
    ({
      timer: () => abrirDefinirTimer(id),
      vincular: () => abrirVincular(id),
      resumo: () => editarResumo(id),
      salvaresumo: () => salvarResumo(id),
      blocoB: () => editarBlocoB(id),
      salvaB: () => salvarBlocoB(id),
      addc: () => abrirFormC(id),
      salvac: () => salvarItemC(id),
      fecharc: () => { $(`#mon-formc-${id}`).innerHTML = ''; },
      cancel: () => render(),
      confvinc: () => confirmarVinculo(id, el.dataset.srm),
      irterr: () => irParaTerritorio(el.dataset.srm),
    }[acao] || (() => {}))();
  });
  $('#tela-mon').addEventListener('change', e => {
    const el = e.target.closest('[data-mon]'); if (!el) return;
    const id = el.dataset.id;
    if (el.dataset.mon === 'nivel') mudarNivel(id, el.value);
    if (el.dataset.mon === 'fase') mudarFase(id, el.value);
    if (el.dataset.mon === 'titulotipo') mudarTituloTipo(id, el.value);
  });
}

/* ================================================================
   INÍCIO
   ================================================================ */
async function iniciar(ctx) {
  S = ctx;
  await carregar();
  ligarEventos();

  $('#mon-busca').oninput = e => { M.busca = e.target.value; render(); };
  $('#mon-ordenar').onchange = e => { M.ordenar = e.target.value; render(); };
  $('#mon-novo').onclick = () => abrirNovo();

  // botões dos diálogos
  $('#mon-te-confirmar').onclick = confirmarTimerEdicao;
  $('#mon-dt-confirmar').onclick = confirmarDefinirTimer;
  $('#mon-venc-confirmar').onclick = confirmarVencido;
  $('#mon-venc-adiar').onclick = adiarVencido;
  $('#mon-venc-abrir').onclick = abrirProcessoVencido;
  $('#mon-novo-salvar').onclick = salvarNovo;
  $('#mon-sf-confirmar').onclick = confirmarSincronizarFase;
  $('#mon-sf-cancelar').onclick = () => fechar('mon-veu-sincfase');
  document.querySelectorAll('[data-mon-fechar]').forEach(b => b.onclick = () => fechar(b.dataset.monFechar));
  document.querySelectorAll('.mon-veu:not(.critica)').forEach(v =>
    v.addEventListener('click', e => { if (e.target === v) v.classList.remove('on'); }));

  render();
  atualizarAlertaCabecalho();   // bolinha de vencidos no cabeçalho desde o início
}

/* chamado quando o módulo passa a ser exibido (fila de vencidos só aqui) */
function aoExibir() { checarVencidos(); render(); }

return { iniciar, aoExibir, render, abrirNovo, irParaTerritorio,
         get processos() { return M.processos; },
         get operacoes() { return M.operacoes; },
         limparPendentes() { M.operacoes = []; M.pendentes = 0; },
         filtrarPorTerritorio(chave) { M.grupoTerritorio = chave; render(); },
         limparFiltroTerritorio() { M.grupoTerritorio = null; render(); },
         processosDoTerritorio(srm) { return M.processos.filter(p => p.srm === srm); } };
})();
