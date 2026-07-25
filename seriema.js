/* ================================================================
   Observatório Seriema — núcleo
   dados (base + curadoria) · mapa · lista · ficha
   ================================================================ */
window.Seriema = (function () {
'use strict';

const CFG = window.SERIEMA_CONFIG;

/* ---------------- cofre: persiste no GitHub Pages, degrada no preview -------- */
const cofre = (function () {
  const mem = {};
  let ok = false;
  try { localStorage.setItem('__seriema', '1'); localStorage.removeItem('__seriema'); ok = true; } catch (e) { ok = false; }
  return {
    persistente: ok,
    get: k => ok ? localStorage.getItem(k) : (k in mem ? mem[k] : null),
    set: (k, v) => { ok ? localStorage.setItem(k, v) : (mem[k] = v); },
    del: k => { ok ? localStorage.removeItem(k) : delete mem[k]; },
  };
})();

/* ---------------- estado ---------------- */
const E = {
  fichas: [], indice: [], resumo: {}, protocolos: [],
  curadoria: { versao: 1, edicoes: [] },
  porId: new Map(),
  filtros: { fases: new Set(), protocolo: false, poligono: false, estadual: false, uf: '', texto: '' },
  selecionado: null, mapa: null, aba: 'lista',
  pendentes: [],           // edições confirmadas ainda não publicadas
  shaCuradoria: null,
};

const FASES = [
  ['TITULADO',       'Titulado',        'var(--f5)'],
  ['TITULO_PARCIAL', 'Título parcial',  'var(--f4)'],
  ['DECRETO',        'Decreto',         'var(--f3)'],
  ['PORTARIA',       'Portaria',        'var(--f2)'],
  ['RTID',           'RTID',            'var(--f1)'],
  ['EM_ELABORACAO',  'Em elaboração',   'var(--f0)'],
  ['CCDRU',          'CCDRU',           'var(--fx)'],
  ['TITULO_ANULADO', 'Título anulado',  'var(--fx)'],
  ['SEM_INFO',       'Sem informação',  'var(--linha-forte)'],
];
const COR_FASE = Object.fromEntries(FASES.map(f => [f[0], f[2]]));
const NOME_FASE = Object.fromEntries(FASES.map(f => [f[0], f[1]]));
const COR_HEX = {
  TITULADO:'#1B4F58', TITULO_PARCIAL:'#2F7370', DECRETO:'#56917F', PORTARIA:'#86A98A',
  RTID:'#AFC0A2', EM_ELABORACAO:'#CBCCC0', CCDRU:'#7E8AA0', TITULO_ANULADO:'#9A6A62', SEM_INFO:'#B9BBB2',
};

/* ---------------- utilidades ---------------- */
const $ = s => document.querySelector(s);
const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c =>
  ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' }[c]));
const num = (v, d = 0) => v == null ? '—' :
  Number(v).toLocaleString('pt-BR', { minimumFractionDigits: d, maximumFractionDigits: d });
const data = s => {
  if (!s) return null;
  const [a, m, d] = String(s).split('-');
  return (a && m && d) ? `${d}/${m}/${a}` : s;
};
const semAcento = s => String(s || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toUpperCase();

/* ================================================================
   1. DADOS
   ================================================================ */
async function carregar() {
  const emb = window.SERIEMA_DADOS_EMBUTIDOS;
  if (emb) {
    E.indice = emb.indice; E.fichas = emb.fichas; E.resumo = emb.resumo; E.protocolos = emb.protocolos;
  } else {
    const b = CFG.dados.base, a = CFG.dados.arquivos;
    const pega = async f => (await fetch(b + f, { cache: 'no-store' })).json();
    [E.indice, E.fichas, E.resumo, E.protocolos] =
      await Promise.all([pega(a.indice), pega(a.fichas), pega(a.resumo), pega(a.protocolos)]);
    try {
      const r = await fetch(CFG.dados.curadoria, { cache: 'no-store' });
      if (r.ok) E.curadoria = await r.json();
    } catch (e) { /* curadoria ainda não existe */ }
  }
  E.fichas.forEach(f => E.porId.set(f.id, f));
  aplicarCuradoria();
}

/* A curadoria é uma CAMADA sobre a base. A base nunca é alterada aqui:
   ela é regenerada pelo pipeline. Isto é o que impede que uma
   atualização de fonte apague o trabalho da equipe. */
function aplicarCuradoria() {
  (E.curadoria.edicoes || []).forEach(ed => {
    const f = E.porId.get(ed.id);
    if (!f) return;
    f._editado = f._editado || [];
    if (ed.acao === 'inativar') {
      f._inativo = { motivo: ed.motivo, em: ed.em, por: ed.por };
    } else if (ed.acao === 'reativar') {
      delete f._inativo;
    } else if (ed.acao === 'definir') {
      escreverCampo(f, ed.campo, ed.valor);
      f._editado.push({ campo: ed.campo, em: ed.em, por: ed.por, motivo: ed.motivo });
    } else if (ed.acao === 'protocolo') {
      f.protocolo_consulta = f.protocolo_consulta || { tem: false, n: 0, itens: [] };
      f.protocolo_consulta.itens.push({ ...ed.valor, vinculo: 'curadoria', fonte: ed.valor.fonte || 'curadoria CFU' });
      f.protocolo_consulta.tem = true;
      f.protocolo_consulta.n = f.protocolo_consulta.itens.length;
      f._editado.push({ campo: 'protocolo_consulta', em: ed.em, por: ed.por });
    } else if (ed.acao === 'confirmar_vinculo') {
      f.vinculos[ed.campo] = 'confirmado_curadoria';
      f._editado.push({ campo: 'vinculos.' + ed.campo, em: ed.em, por: ed.por });
    }
  });
  // reflete no índice
  const ind = new Map(E.indice.map(i => [i.id, i]));
  E.fichas.forEach(f => {
    const i = ind.get(f.id); if (!i) return;
    i.nome = f.nome; i.fase = f.fase; i.prot = !!(f.protocolo_consulta && f.protocolo_consulta.tem);
    i.inativo = !!f._inativo;
  });
}

function escreverCampo(obj, caminho, valor) {
  const p = caminho.split('.');
  let o = obj;
  for (let i = 0; i < p.length - 1; i++) { if (o[p[i]] == null) o[p[i]] = {}; o = o[p[i]]; }
  o[p[p.length - 1]] = valor;
}
function lerCampo(obj, caminho) {
  return caminho.split('.').reduce((o, k) => (o == null ? undefined : o[k]), obj);
}

/* ---- consulta estruturada: é isto que o assistente executa ---- */
function consultar(q = {}) {
  let r = E.indice.filter(i => !i.inativo || q.incluir_inativos);
  if (q.uf) r = r.filter(i => i.uf === String(q.uf).toUpperCase());
  if (q.fase && q.fase.length) { const s = new Set(q.fase.map(x => String(x).toUpperCase())); r = r.filter(i => s.has(i.fase)); }
  if (q.esfera) r = r.filter(i => semAcento(i.esf).startsWith(semAcento(q.esfera).slice(0, 3)));
  if (q.tem_protocolo === true) r = r.filter(i => i.prot);
  if (q.tem_protocolo === false) r = r.filter(i => !i.prot);
  if (q.tem_poligono === true) r = r.filter(i => i.pol);
  if (q.tem_poligono === false) r = r.filter(i => !i.pol);
  if (q.area_min != null) r = r.filter(i => (i.area || 0) >= q.area_min);
  if (q.area_max != null) r = r.filter(i => (i.area || 0) <= q.area_max);
  if (q.familias_min != null) r = r.filter(i => (i.fam || 0) >= q.familias_min);
  if (q.texto) {
    const t = semAcento(q.texto);
    r = r.filter(i => semAcento(i.nome).includes(t) || semAcento(i.mun).includes(t) || (i.id === q.texto));
  }
  if (q.ordenar_por === 'area') r = [...r].sort((a, b) => (b.area || 0) - (a.area || 0));
  else if (q.ordenar_por === 'familias') r = [...r].sort((a, b) => (b.fam || 0) - (a.fam || 0));
  else r = [...r].sort((a, b) => (a.uf + a.nome).localeCompare(b.uf + b.nome, 'pt-BR'));
  return r;
}

/* ---- agregação: responde perguntas de total sem varrer as fichas ---- */
function agregar(agruparPor = 'uf', q = {}) {
  const r = consultar(q), mapa = {};
  const chave = i => ({ uf: i.uf, fase: i.fase, esfera: i.esf || 'SEM_INFO' }[agruparPor] || i.uf);
  r.forEach(i => {
    const k = chave(i);
    mapa[k] = mapa[k] || { n: 0, area_ha: 0, familias: 0, com_protocolo: 0 };
    mapa[k].n++; mapa[k].area_ha += i.area || 0; mapa[k].familias += i.fam || 0;
    if (i.prot) mapa[k].com_protocolo++;
  });
  Object.values(mapa).forEach(v => v.area_ha = Math.round(v.area_ha));
  return { agrupado_por: agruparPor, total: r.length, grupos: mapa };
}

/* ---- deep-links por território ---- */
function linksDe(f) {
  const n = encodeURIComponent(f.nome);
  const AMZ = ['AC','AP','AM','MA','MT','PA','RO','RR','TO'];
  const L = [
    ['INCRA · PGT', 'https://pro-pgt-incra.estaleiro.serpro.gov.br/pgt/home', 'portal'],
    ['INCRA · Acervo Fundiário', 'https://acervofundiario.incra.gov.br/acervo/acv.php', 'portal'],
    ['FCP · certificadas', 'https://www.gov.br/palmares/pt-br/departamentos/protecao-preservacao-e-articulacao/certificacao-quilombola', 'portal'],
    ['CPISP · Observatório', `https://cpisp.org.br/?s=${n}`, 'busca'],
    ['Terra de Direitos', `https://terradedireitos.org.br/?s=${n}`, 'busca'],
    ['Protocolos · OPCPLI', `https://observatorio.direitosocioambiental.org/?s=${n}`, 'busca'],
    ['Fiocruz · Mapa de Conflitos', 'https://mapadeconflitos.ensp.fiocruz.br', 'portal'],
    ['MPF · Territórios Tradicionais', 'https://territoriostradicionais.mpf.mp.br', 'portal'],
    ['MapBiomas Alerta', 'https://alerta.mapbiomas.org', 'portal'],
  ];
  if (AMZ.includes(f.uf)) L.push(['ISA/CONAQ · Amazônia Quilombola', 'https://amazoniaquilombola.org.br/', 'portal']);
  if (f.geo && f.geo.lat) L.push(['Ver satélite', `https://www.google.com/maps/@${f.geo.lat},${f.geo.lon},13z/data=!3m1!1e3`, 'busca']);
  return L;
}

/* ================================================================
   2. TRILHA — o glifo que resume o rito administrativo
   ================================================================ */
function trilhaHTML(f, grande) {
  const t = f.tramite || {};
  const passos = [
    ['RTID', t.rtid_edital_1],
    ['Portaria', t.portaria],
    ['Decreto', t.decreto],
    ['Título', t.titulacao || (t.titulo_txt ? '·' : null)],
  ];
  const parcial = f.fase === 'TITULO_PARCIAL';
  const segs = passos.map(([, d], i) => {
    const on = !!d;
    let cls = 'seg';
    if (on) cls += (i === 3 ? (parcial ? ' seg parcial' : ' tit') : ' on');
    return `<div class="${cls}" title="${passos[i][0]}${d && d !== '·' ? ': ' + data(d) : (on ? '' : ': —')}"></div>`;
  }).join('');
  if (!grande) return `<div class="trilha">${segs}</div>`;
  return `<div class="trilha g">${segs}</div>
    <div class="trilha-legenda">${passos.map(p => `<span>${p[0]}</span>`).join('')}</div>
    <div class="trilha-datas">${passos.map(p => `<span>${p[1] && p[1] !== '·' ? data(p[1]) : '—'}</span>`).join('')}</div>`;
}

/* ================================================================
   3. MAPA
   ================================================================ */
function geojson(lista) {
  return {
    type: 'FeatureCollection',
    features: lista.filter(i => i.lat != null).map(i => ({
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [i.lon, i.lat] },
      properties: { id: i.id, nome: i.nome, uf: i.uf, fase: i.fase, cor: COR_HEX[i.fase] || COR_HEX.SEM_INFO, pol: i.pol ? 1 : 0 },
    })),
  };
}

function montarMapa() {
  const m = new maplibregl.Map({
    container: 'mapa',
    style: {
      version: 8,
      sources: { base: { type: 'raster', tiles: [CFG.mapa.tiles], tileSize: 256, attribution: CFG.mapa.atribuicao } },
      layers: [{ id: 'base', type: 'raster', source: 'base' }],
    },
    center: CFG.mapa.centro, zoom: CFG.mapa.zoom, maxZoom: 15, attributionControl: { compact: true },
  });
  E.mapa = m;
  m.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'bottom-right');
  m.addControl(new maplibregl.ScaleControl({ maxWidth: 90, unit: 'metric' }), 'bottom-left');

  m.on('load', () => {
    m.addSource('terr', { type: 'geojson', data: geojson(E.indice), cluster: true, clusterRadius: 38, clusterMaxZoom: 7 });

    m.addLayer({ id: 'clusters', type: 'circle', source: 'terr', filter: ['has', 'point_count'],
      paint: {
        'circle-color': '#17262C',
        'circle-radius': ['step', ['get', 'point_count'], 13, 10, 18, 40, 24],
        'circle-stroke-width': 2, 'circle-stroke-color': 'rgba(245,245,241,.85)',
      } });
    m.addLayer({ id: 'clusters-n', type: 'symbol', source: 'terr', filter: ['has', 'point_count'],
      layout: { 'text-field': ['get', 'point_count_abbreviated'], 'text-size': 11.5,
                'text-font': ['Open Sans Bold', 'Arial Unicode MS Bold'] },
      paint: { 'text-color': '#F5F5F1' } });
    m.addLayer({ id: 'pontos', type: 'circle', source: 'terr', filter: ['!', ['has', 'point_count']],
      paint: {
        'circle-color': ['get', 'cor'],
        'circle-radius': ['interpolate', ['linear'], ['zoom'], 4, 4.2, 8, 6.5, 12, 10],
        'circle-stroke-width': ['case', ['==', ['get', 'pol'], 1], 1.6, 0.9],
        'circle-stroke-color': ['case', ['==', ['get', 'pol'], 1], '#17262C', 'rgba(23,38,44,.4)'],
      } });
    m.addLayer({ id: 'selecionado', type: 'circle', source: 'terr',
      filter: ['==', ['get', 'id'], ''],
      paint: { 'circle-radius': 13, 'circle-color': 'rgba(200,83,31,.22)', 'circle-stroke-width': 2.2, 'circle-stroke-color': '#C8531F' } });

    m.on('click', 'pontos', e => selecionar(e.features[0].properties.id, false));
    m.on('click', 'clusters', e => {
      const id = e.features[0].properties.cluster_id;
      m.getSource('terr').getClusterExpansionZoom(id).then(z =>
        m.easeTo({ center: e.features[0].geometry.coordinates, zoom: z })).catch(() => {});
    });
    ['pontos', 'clusters'].forEach(l => {
      m.on('mouseenter', l, () => m.getCanvas().style.cursor = 'pointer');
      m.on('mouseleave', l, () => m.getCanvas().style.cursor = '');
    });
    atualizarMapa();
  });
}

function atualizarMapa() {
  if (!E.mapa || !E.mapa.getSource('terr')) return;
  E.mapa.getSource('terr').setData(geojson(filtrados()));
  E.mapa.setFilter('selecionado', ['==', ['get', 'id'], E.selecionado || '']);
}

/* ================================================================
   4. FILTROS E LISTA
   ================================================================ */
function filtrados() {
  const F = E.filtros;
  return consultar({
    uf: F.uf || undefined,
    fase: F.fases.size ? [...F.fases] : undefined,
    tem_protocolo: F.protocolo ? true : undefined,
    tem_poligono: F.poligono ? true : undefined,
    esfera: F.estadual ? 'ESTADUAL' : undefined,
    texto: F.texto || undefined,
  });
}

function montarChips() {
  const cont = {};
  E.indice.forEach(i => cont[i.fase] = (cont[i.fase] || 0) + 1);
  $('#chips-fase').innerHTML = FASES.filter(f => cont[f[0]]).map(([k, rot, cor]) =>
    `<button class="chip" data-fase="${k}" aria-pressed="false">
       <span class="pt" style="background:${cor}"></span>${rot} <span class="n">${cont[k]}</span></button>`).join('');
  $('#chips-fase').onclick = e => {
    const b = e.target.closest('[data-fase]'); if (!b) return;
    const k = b.dataset.fase;
    E.filtros.fases.has(k) ? E.filtros.fases.delete(k) : E.filtros.fases.add(k);
    b.setAttribute('aria-pressed', E.filtros.fases.has(k));
    render();
  };
  $('#n-prot').textContent = E.indice.filter(i => i.prot).length;
  $('#n-pol').textContent = E.indice.filter(i => i.pol).length;
  $('#n-est').textContent = E.indice.filter(i => semAcento(i.esf).startsWith('EST')).length;
  $('#chips-extra').onclick = e => {
    const b = e.target.closest('[data-filtro]'); if (!b) return;
    const k = b.dataset.filtro;
    E.filtros[k] = !E.filtros[k];
    b.setAttribute('aria-pressed', E.filtros[k]);
    render();
  };
  const ufs = [...new Set(E.indice.map(i => i.uf))].sort();
  $('#filtro-uf').innerHTML = '<option value="">UF</option>' + ufs.map(u => `<option>${u}</option>`).join('');
}

function renderLista() {
  const r = filtrados(), alvo = $('#painel-lista');
  if (E.selecionado) return renderFicha(E.porId.get(E.selecionado));
  if (!r.length) { alvo.innerHTML = `<div class="vazio">Nenhum território com esses filtros.<br>Desmarque alguma camada.</div>`; return; }
  const topo = `<div style="padding:7px 12px;font-size:11px;color:var(--tinta-2);border-bottom:1px solid var(--linha)">
      <b class="mono">${r.length}</b> de ${E.indice.length} territórios</div>`;
  alvo.innerHTML = topo + r.slice(0, 400).map(i => {
    const f = E.porId.get(i.id);
    return `<button class="item" data-id="${i.id}" ${E.selecionado === i.id ? 'aria-current="true"' : ''}>
      <div class="l1"><span class="nome">${esc(i.nome)}</span><span class="uf">${i.uf}</span></div>
      <div class="l2">
        <span class="mun">${esc(i.mun || '—')}</span>
        <span class="marcas">
          ${i.prot ? '<span class="marca-mini m-prot">PROT</span>' : ''}
          ${i.pol ? '<span class="marca-mini m-pol">POL</span>' : ''}
          ${semAcento(i.esf).startsWith('EST') ? '<span class="marca-mini m-est">EST</span>' : ''}
        </span>
      </div>
      <div class="l2" style="margin-top:5px">
        ${trilhaHTML(f)}
        <span class="mono" style="color:var(--tinta-2);margin-left:auto">${i.area ? num(i.area) + ' ha' : ''}</span>
      </div>
    </button>`;
  }).join('') + (r.length > 400 ? `<div class="vazio">…e mais ${r.length - 400}. Refine a busca.</div>` : '');
  alvo.onclick = e => { const b = e.target.closest('[data-id]'); if (b) selecionar(b.dataset.id, true); };
}

/* ================================================================
   5. FICHA COMPLETA
   ================================================================ */
function renderFicha(f) {
  if (!f) return;
  const c = f.certificacao || {}, ib = f.ibge || {}, pc = f.protocolo_consulta || { itens: [] };
  const selo = v => v === 'confirmado' || v === 'confirmado_curadoria' ? 's-conf' : v === 'provavel' ? 's-prov' : 's-nao';
  const rot = v => ({ confirmado: 'confirmado por código', confirmado_curadoria: 'confirmado pela CFU',
                      provavel: 'provável (por nome)', proprio: 'registro próprio', nao_localizado: 'não localizado' }[v] || v);

  $('#painel-lista').innerHTML = `<div class="ficha">
    <button class="voltar" id="bt-voltar">← todos os territórios</button>
    ${f._inativo ? `<div class="aviso"><b>Registro inativado.</b> ${esc(f._inativo.motivo || '')}
        <br><span class="mono" style="font-size:10px">${esc(f._inativo.em || '')}</span></div>` : ''}
    <h2>${esc(f.nome)}</h2>
    <div class="local">${esc((f.municipios || []).join(', '))} · ${f.uf}</div>
    <span class="selo-fase" style="background:${COR_FASE[f.fase] || 'var(--tinta-2)'}">${NOME_FASE[f.fase] || f.fase}</span>

    <div class="bloco">
      <h3>Trilha do processo</h3>
      ${trilhaHTML(f, true)}
      ${f.tramite && f.tramite.titulo_txt ? `<div class="nota mt6">Título: ${esc(f.tramite.titulo_txt)}</div>` : ''}
      ${f.tramite && f.tramite.retificacao_portaria ? `<div class="nota mt6">Retificação da portaria: ${data(f.tramite.retificacao_portaria)}</div>` : ''}
    </div>

    <div class="bloco">
      <h3>Identificação e área</h3>
      <dl class="kv">
        <dt>Código Seriema</dt><dd>${f.id}</dd>
        <dt>Processo INCRA</dt><dd>${esc(f.processo_incra || '—')}</dd>
        <dt>Esfera</dt><dd>${esc(f.esfera || '—')}</dd>
        <dt>Órgão</dt><dd>${esc(f.orgao_responsavel || '—')}</dd>
        <dt>Área (edital)</dt><dd>${f.area_ha ? num(f.area_ha, 2) + ' ha' : '—'}</dd>
        ${f.geo && f.geo.area_geom_ha ? `<dt>Área (polígono)</dt><dd>${num(f.geo.area_geom_ha, 2)} ha</dd>` : ''}
        <dt>Famílias</dt><dd>${f.familias != null ? num(f.familias) : '—'}</dd>
        <dt>Coordenada</dt><dd>${f.geo && f.geo.lat ? `${f.geo.lat}, ${f.geo.lon}` : '—'}</dd>
        <dt>Origem do ponto</dt><dd style="font-size:10.5px">${
          ({ centroide_poligono_incra: 'centroide do polígono INCRA',
             media_localidades_ibge: 'média das localidades IBGE',
             sem_coordenada: 'sem coordenada' }[f.geo_origem] || '—')}</dd>
      </dl>
    </div>

    <div class="bloco">
      <h3>Protocolo de consulta prévia</h3>
      ${pc.tem ? `<div class="pilha">${pc.itens.map(p => `
        <div class="cartao">
          <div class="t">${esc(p.titulo)}</div>
          <div class="m">${p.ano ? p.ano + ' · ' : ''}${esc(p.fonte || '')}${p.vinculo === 'coletivo' ? ' · protocolo coletivo' : ''}</div>
          <div class="mt6"><a href="${esc(p.url)}" target="_blank" rel="noopener">abrir documento ↗</a></div>
        </div>`).join('')}</div>`
       : `<div class="nota">Nenhum protocolo localizado nas fontes públicas consultadas.
            Isto não significa que não exista — significa que não foi encontrado.
            Se a coordenação tiver notícia de um, use o assistente para registrá-lo.</div>`}
    </div>

    <div class="bloco">
      <h3>Certificação — Fundação Cultural Palmares</h3>
      ${c.n_certidoes ? `<dl class="kv">
          <dt>Certidões</dt><dd>${c.n_certidoes}</dd>
          <dt>1ª certificação</dt><dd>${c.ano_primeira || '—'}</dd>
          <dt>Moradores</dt><dd>${c.moradores_fcp != null ? num(c.moradores_fcp) : '—'}</dd>
        </dl>
        <div class="pilha mt10">${(c.detalhe || []).slice(0, 6).map(d => `
          <div class="cartao"><div class="t" style="font-size:11.5px">${esc(String(d.comunidade).slice(0, 180))}${String(d.comunidade).length > 180 ? '…' : ''}</div>
          <div class="m">${esc(d.municipio || '')} · portaria ${esc(d.portaria || '—')} · DOU ${data(d.dou) || '—'}</div></div>`).join('')}
          ${(c.detalhe || []).length > 6 ? `<div class="nota">…e mais ${c.detalhe.length - 6} certidões.</div>` : ''}</div>`
        : `<div class="nota">Sem certidão vinculada a este processo.</div>`}
    </div>

    <div class="bloco">
      <h3>Presença no Censo 2022 — IBGE</h3>
      ${ib.n_localidades ? `<dl class="kv">
          <dt>Território IBGE</dt><dd>${esc(ib.nm_tq || '—')}${ib.cd_tq ? ' (cód. ' + ib.cd_tq + ')' : ''}</dd>
          <dt>Localidades</dt><dd>${ib.n_localidades}</dd>
        </dl>
        <div class="nota mt6">${(ib.localidades || []).slice(0, 14).map(l => esc(l.nome)).join(' · ')}${
          (ib.localidades || []).length > 14 ? ` … +${ib.localidades.length - 14}` : ''}</div>`
        : `<div class="nota">Nenhuma localidade do Censo 2022 vinculada.</div>`}
    </div>

    <div class="bloco">
      <h3>Confiança dos vínculos</h3>
      <div class="selos">
        <span class="selo ${selo(f.vinculos.poligono)}">polígono: ${rot(f.vinculos.poligono)}</span>
        <span class="selo ${selo(f.vinculos.fcp)}">FCP: ${rot(f.vinculos.fcp)}</span>
        <span class="selo ${selo(f.vinculos.ibge)}">IBGE: ${rot(f.vinculos.ibge)}</span>
      </div>
      <div class="nota mt6">Fontes deste registro: ${esc((f.fontes || []).join(' · '))}.
        ${f._editado && f._editado.length ? `<br><b>Editado pela CFU:</b> ${f._editado.map(e => esc(e.campo)).join(', ')}.` : ''}</div>
    </div>

    <div class="bloco">
      <h3>Consultar nas fontes</h3>
      <div class="links">${linksDe(f).map(([r, u, t]) =>
        `<a href="${esc(u)}" target="_blank" rel="noopener">${esc(r)} <span class="ext">${t === 'busca' ? '⌕' : '↗'}</span></a>`).join('')}</div>
      <div class="nota mt6">⌕ abre já filtrado por este território · ↗ abre o portal</div>
    </div>

    <div class="bloco">
      <h3>Corrigir ou complementar</h3>
      <div class="nota">Descreva a correção em linguagem natural no assistente — ela será mostrada
        para conferência antes de valer.</div>
      <button class="bt vazado p mt10" id="bt-editar">Abrir assistente com este território</button>
    </div>
  </div>`;

  $('#bt-voltar').onclick = () => { E.selecionado = null; render(); };
  $('#bt-editar').onclick = () => {
    trocarAba('ia');
    $('#ia-txt').value = `No território ${f.nome} (${f.uf}, ${f.id}), `;
    $('#ia-txt').focus();
  };
}

function selecionar(id, doPainel) {
  E.selecionado = id;
  const f = E.porId.get(id);
  if (f && f.geo && f.geo.lat && E.mapa) {
    if (doPainel) E.mapa.easeTo({ center: [f.geo.lon, f.geo.lat], zoom: Math.max(E.mapa.getZoom(), 8.5), duration: 700 });
    E.mapa.setFilter('selecionado', ['==', ['get', 'id'], id]);
  }
  trocarAba('lista');
  renderFicha(f);
}

/* ================================================================
   6. ABAS, SOBRE, RENDER
   ================================================================ */
function trocarAba(a) {
  E.aba = a;
  document.querySelectorAll('.aba').forEach(b => b.setAttribute('aria-selected', b.dataset.aba === a));
  $('#painel-lista').classList.toggle('oculto', a !== 'lista');
  $('#painel-ia').classList.toggle('oculto', a !== 'ia');
  $('#painel-sobre').classList.toggle('oculto', a !== 'sobre');
  $('#buscabar').classList.toggle('oculto', a !== 'lista');
}

function renderSobre() {
  const r = E.resumo, v = r.vinculos || {};
  const G = [
    ['A · Governo federal', [
      ['INCRA — Acervo Fundiário (polígonos)', 'https://acervofundiario.incra.gov.br/acervo/acv.php'],
      ['INCRA — andamento dos processos', 'https://www.gov.br/incra/pt-br/assuntos/governanca-fundiaria/quilombolas'],
      ['FCP — comunidades certificadas', 'https://www.gov.br/palmares/pt-br/departamentos/protecao-preservacao-e-articulacao/certificacao-quilombola'],
      ['IBGE — localidades quilombolas 2022', 'https://geoftp.ibge.gov.br/organizacao_do_territorio/estrutura_territorial/localidades/localidades_quilombolas_2022/'],
    ]],
    ['B · Controle e justiça', [
      ['MPF — Plataforma de Territórios Tradicionais', 'https://territoriostradicionais.mpf.mp.br'],
      ['MPF — 6ª Câmara', 'https://www.mpf.mp.br/atuacao/ccr6'],
      ['DPU — comunidades tradicionais', 'https://www.dpu.def.br/comunidades-tradicionais-quilombolas'],
      ['Fiocruz — Mapa de Conflitos', 'https://mapadeconflitos.ensp.fiocruz.br'],
    ]],
    ['C · Sociedade civil e técnica', [
      ['Observatório de Protocolos (OPCPLI/CEPEDIS)', 'https://observatorio.direitosocioambiental.org/'],
      ['CPISP — Observatório Terras Quilombolas', 'https://cpisp.org.br'],
      ['CPT — Conflitos no Campo', 'https://cptnacional.org.br/acervo/conflitos-no-campo/caderno-de-conflitos/'],
      ['ISA/CONAQ — Amazônia Quilombola', 'https://amazoniaquilombola.org.br/'],
      ['CONAQ', 'https://conaq.org.br'],
      ['MapBiomas Alerta', 'https://alerta.mapbiomas.org'],
      ['Terra de Direitos', 'https://terradedireitos.org.br'],
    ]],
  ];
  $('#painel-sobre').innerHTML = `<div class="ficha">
    <h2 style="font-size:16px">Como esta base foi construída</h2>
    <div class="nota mt6">Quatro fontes públicas cruzadas por número de processo, não por semelhança
      de nome. Cada ficha carrega o selo de confiança de cada vínculo.</div>

    <div class="bloco"><h3>Números</h3>
      <dl class="kv">
        <dt>Territórios</dt><dd>${num(r.n_territorios)}</dd>
        <dt>Com coordenada</dt><dd>${num(r.com_coordenada)} (${num(r.com_poligono)} com polígono)</dd>
        <dt>Área somada</dt><dd>${num(r.area_total_ha)} ha</dd>
        <dt>Famílias</dt><dd>${num(r.familias_total)}</dd>
        <dt>Certidões FCP</dt><dd>${num(r.certidoes_total)}</dd>
        <dt>Localidades IBGE</dt><dd>${num(r.localidades_ibge_total)}</dd>
        <dt>Com protocolo</dt><dd>${num(r.com_protocolo)}</dd>
      </dl></div>

    <div class="bloco"><h3>Confiança dos vínculos</h3>
      <dl class="kv">
        <dt>FCP</dt><dd>${(v.fcp && v.fcp.confirmado) || 0} confirmados · ${(v.fcp && v.fcp.provavel) || 0} prováveis</dd>
        <dt>IBGE</dt><dd>${(v.ibge && v.ibge.confirmado) || 0} confirmados · ${(v.ibge && v.ibge.provavel) || 0} prováveis</dd>
        <dt>Polígono</dt><dd>${(v.poligono && v.poligono.confirmado) || 0} confirmados · ${(v.poligono && v.poligono.provavel) || 0} prováveis</dd>
      </dl>
      <div class="nota mt6"><b>Confirmado</b> = número de processo idêntico entre as fontes.
        <b>Provável</b> = nome e UF idênticos após normalização. Nunca inferimos além disso.</div></div>

    ${G.map(([t, l]) => `<div class="bloco"><h3>${t}</h3><div class="links">${
      l.map(([r2, u]) => `<a href="${u}" target="_blank" rel="noopener">${r2} <span class="ext">↗</span></a>`).join('')}</div></div>`).join('')}

    <div class="bloco"><h3>Limites conhecidos</h3>
      <div class="nota">
        · O recorte é T1+T2: territórios com processo no INCRA ou com delimitação cartográfica.
          Comunidades apenas certificadas pela FCP, sem processo aberto, não aparecem como território.<br>
        · Territórios de esfera estadual constam quando têm polígono, mas o quadro de andamento
          federal não os cobre.<br>
        · Ausência de protocolo de consulta significa <i>não localizado nas fontes públicas</i>.<br>
        · A camada de povos e comunidades tradicionais não quilombolas depende de acordo com o MPF
          e ainda não integra esta versão.
      </div></div>

    <div class="bloco"><h3>Atualização</h3>
      <div class="nota">Dados de ${esc(CFG.dados.dataCorte)}. Para atualizar, rode os scripts
        <span class="mono">etl_01</span> → <span class="mono">etl_02</span> → <span class="mono">etl_03</span>
        com os arquivos-fonte novos e substitua a pasta <span class="mono">base/</span>.
        A pasta <span class="mono">curadoria/</span> não é tocada pelo pipeline.</div></div>
  </div>`;
}

function render() {
  atualizarMapa();
  if (E.aba === 'lista') renderLista();
  atualizarPendentes();
}

function atualizarPendentes() {
  const p = $('#pendentes');
  p.classList.toggle('oculto', !E.pendentes.length);
  $('#pend-n').textContent = E.pendentes.length;
}

/* ================================================================
   7. INICIALIZAÇÃO
   ================================================================ */
async function iniciar() {
  try {
    await carregar();
  } catch (e) {
    document.getElementById('painel-lista').innerHTML =
      `<div class="vazio"><b>Não foi possível carregar a base.</b><br><br>
       Se você abriu o arquivo direto do disco, o navegador bloqueia a leitura dos JSON.
       Publique no GitHub Pages ou rode <span class="mono">python3 -m http.server</span> na pasta do projeto.
       <br><br><span class="mono" style="font-size:10px">${esc(e.message)}</span></div>`;
    return;
  }
  const r = E.resumo;
  $('#c-terr').textContent = num(r.n_territorios);
  $('#c-tit').textContent = num((r.por_fase && (r.por_fase.TITULADO || 0)) + (r.por_fase && (r.por_fase.TITULO_PARCIAL || 0)));
  $('#c-area').textContent = (r.area_total_ha / 1e6).toFixed(2).replace('.', ',') + ' mi';
  $('#c-corte').textContent = 'dados de ' + CFG.dados.dataCorte;

  montarChips(); montarMapa(); renderSobre(); render();

  document.querySelectorAll('.aba').forEach(b => b.onclick = () => trocarAba(b.dataset.aba));
  let t;
  $('#busca').oninput = e => { clearTimeout(t); t = setTimeout(() => { E.filtros.texto = e.target.value.trim(); E.selecionado = null; render(); }, 180); };
  $('#filtro-uf').onchange = e => { E.filtros.uf = e.target.value; E.selecionado = null; render(); };
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && E.selecionado) { E.selecionado = null; render(); }
    if (e.key === '/' && document.activeElement.tagName !== 'INPUT' && document.activeElement.tagName !== 'TEXTAREA') {
      e.preventDefault(); trocarAba('lista'); $('#busca').focus();
    }
  });
  if (window.Assistente) window.Assistente.iniciar({ E, cofre, consultar, agregar, lerCampo, esc, num, data, render, selecionar, atualizarPendentes });
}

return { iniciar, E, cofre, consultar, agregar, render, selecionar, trocarAba, esc, num, data, lerCampo, trilhaHTML, NOME_FASE };
})();
