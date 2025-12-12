/**
 * Utilitários HTTP com timeout e retry
 * 
 * Usa fetch nativo do Node.js 18+ (sem dependência externa)
 */

// Node 18+ tem fetch nativo, mas vamos garantir compatibilidade
let fetchImpl;
if (typeof fetch !== 'undefined') {
  // Fetch nativo disponível (Node 18+)
  fetchImpl = fetch;
} else {
  // Fallback para node-fetch v2 (CommonJS)
  try {
    fetchImpl = require('node-fetch');
  } catch (e) {
    throw new Error('fetch não disponível. Use Node.js 18+ ou instale node-fetch@2');
  }
}

/**
 * Fetch com timeout usando AbortController
 * @param {string} url - URL para fazer a requisição
 * @param {object} opts - Opções do fetch (headers, body, method, etc.)
 * @param {number} timeoutMs - Timeout em milissegundos
 * @returns {Promise<Response>} Resposta do fetch
 */
async function fetchWithTimeout(url, opts = {}, timeoutMs = 20000) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetchImpl(url, {
      ...opts,
      signal: controller.signal,
    });
    clearTimeout(timeoutId);
    return response;
  } catch (error) {
    clearTimeout(timeoutId);
    if (error.name === 'AbortError' || error.message?.includes('aborted')) {
      throw new Error(`Request timeout após ${timeoutMs}ms: ${url}`);
    }
    throw error;
  }
}

module.exports = {
  fetchWithTimeout,
};

