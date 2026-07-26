/* ============================================================
   Observatório Seriema — configuração
   Coordenação de Governança Fundiária · SETEQ / MDA

   ESTE ARQUIVO É SEU. Ao atualizar o painel, substitua todos os
   outros arquivos, mas preserve este — ele guarda o repositório,
   o serviço de linguagem e as preferências desta instalação.
   ============================================================ */

window.SERIEMA_CONFIG = {

  /* ---- serviço de linguagem ----------------------------------------
     Interface compatível com OpenAI (/chat/completions).
     Endereço e modelo também são editáveis pela própria interface,
     no botão "Serviço e chave" da aba Assistente.
     A CHAVE NÃO FICA AQUI: é digitada pela pessoa e guardada apenas
     no navegador dela.                                              */
  llm: {
    endpoint: 'https://openrouter.ai/api/v1/chat/completions',
    modelo: 'deepseek/deepseek-v4-flash',
    // true apenas se você apontar o endpoint para um proxy que
    // guarde a chave no servidor.
    usarProxy: false,
    temperatura: 0.2,
    maxTokens: 1600,
  },

  /* ---- busca na web (opcional, independente do provedor do modelo) -- */
  busca: {
    ativa: true,
    provedor: 'firecrawl',
    endpoint: 'https://api.firecrawl.dev/v2/search',
    maxResultados: 5,
  },

  /* ---- repositório de curadoria ------------------------------------- */
  github: {
    dono: 'CaetanoGisi-MDA',
    repo: 'CGFUN_Seriema',
    branch: 'main',
    caminhoCuradoria: 'curadoria/edicoes.json',
    // false = grava direto no branch principal.
    // true  = abre proposta de alteração para revisão antes de valer.
    exigirRevisao: false,
  },

  /* ---- dados --------------------------------------------------------- */
  dados: {
    base: 'base/',
    arquivos: {
      indice: 'territorios_indice.json',
      fichas: 'territorios_fichas.json',
      resumo: 'resumo.json',
      protocolos: 'protocolos.json',
    },
    curadoria: 'curadoria/edicoes.json',
    dataCorte: 'julho de 2026',
  },

  /* ---- mapa ---------------------------------------------------------- */
  mapa: {
    centro: [-52.5, -13.5],
    zoom: 3.4,
    tiles: 'https://basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
    atribuicao: '© OpenStreetMap · © CARTO',
  },

  /* ---- aviso de publicidade ------------------------------------------
     true faz o painel avisar, antes de publicar edições, que tudo o
     que for digitado ficará visível na internet.                      */
  repositorioPublico: true,
};
