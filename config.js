/* ============================================================
   Observatório Seriema — configuração
   Edite este arquivo para trocar de provedor de modelo, ajustar
   o repositório de curadoria ou ativar revisão por proposta.
   ============================================================ */

window.SERIEMA_CONFIG = {

  /* ---- modelo de linguagem ------------------------------------------
     Interface compatível com OpenAI (/chat/completions).
     Troque estes três campos para usar outro provedor.
     A chave NÃO fica aqui: é digitada pela pessoa e guardada
     apenas no navegador dela.                                        */
  llm: {
    endpoint: 'https://api.deepseek.com/chat/completions',
    modelo: 'deepseek/deepseek-v4-flash',
    // Se você montar um proxy institucional que guarda a chave no servidor,
    // aponte o endpoint para ele e ligue a linha abaixo.
    usarProxy: false,
    temperatura: 0.2,
    maxTokens: 1600,
  },

  /* ---- busca na web (opcional, independente do provedor) ----------- */
  busca: {
    ativa: true,
    provedor: 'tavily',                       // 'tavily' | 'serper' | 'brave'
    endpoint: 'https://api.tavily.com/search',
    maxResultados: 5,
  },

  /* ---- repositório de curadoria ------------------------------------ */
  github: {
    dono: 'CaetanoGisi-MDA',
    repo: 'CGFUN_Seriema',
    branch: 'main',
    caminhoCuradoria: 'curadoria/edicoes.json',
    // false = grava direto no branch. true = abre proposta de alteração
    // para revisão antes de valer. Troque quando a equipe crescer.
    exigirRevisao: false,
  },

  /* ---- dados -------------------------------------------------------- */
  dados: {
    base: 'base/',
    arquivos: {
      indice: 'territorios_indice.json',
      fichas: 'territorios_fichas.json',
      resumo: 'resumo.json',
      protocolos: 'protocolos.json',
    },
    curadoria: 'curadoria/edicoes.json',
    dataCorte: '25 de julho de 2026',
  },

  /* ---- mapa --------------------------------------------------------- */
  mapa: {
    centro: [-52.5, -13.5],
    zoom: 3.4,
    tiles: 'https://basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
    atribuicao: '© OpenStreetMap · © CARTO',
  },

  /* ---- aviso de publicidade ---------------------------------------- */
  repositorioPublico: true,
};
