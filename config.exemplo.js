/* ============================================================
   Observatório Seriema — configuração
   Coordenação de Governança Fundiária · SETEQ / MDA

   ARQUIVO DE EXEMPLO. Copie para `config.js` e ajuste.

   Ao ATUALIZAR o painel, substitua todos os arquivos EXCETO
   `config.js` — ele guarda o repositório, o serviço de linguagem
   e as preferências desta instalação, e é o único arquivo que o
   pipeline nunca deve sobrescrever.
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
    provedor: 'tavily',                       // 'tavily' | 'serper' | 'brave'
    endpoint: 'https://api.tavily.com/search',
    maxResultados: 5,
  },

  /* ---- repositório de curadoria ------------------------------------- */
  github: {
    dono: 'SEU-USUARIO',
    repo: 'NOME-DO-REPOSITORIO',
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
    // CARTO passou a exigir chave de API a partir de 28/08/2026. O formato
    // vetorial (não o raster/PNG antigo) é o que o próprio CARTO recomenda
    // — mais nítido e sem previsão de descontinuação, ao contrário do
    // raster. O MapLibre GL que já usamos consome isso nativamente.
    // Chave gratuita em: https://carto.com/basemaps/apikey (5 milhões de
    // requisições/mês, sem necessidade de conta).
    estilo: 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json',
    chave: '',  // obtenha em carto.com/basemaps/apikey
    atribuicao: '© OpenStreetMap contributors © CARTO',
  },

  /* ---- aviso de publicidade ------------------------------------------
     true faz o painel avisar, antes de publicar edições, que tudo o
     que for digitado ficará visível na internet.                      */
  repositorioPublico: true,
};
