/**
 * Fila BullMQ para processamento de mensagens do WhatsApp
 */
const { Queue } = require('bullmq');
const { getRedisConnection } = require('./redis');

const redis = getRedisConnection();

// Nome da fila
const QUEUE_NAME = 'whatsapp-messages';

  // Criar fila BullMQ
  const messageQueue = new Queue(QUEUE_NAME, {
    connection: redis,
    defaultJobOptions: {
      attempts: 5, // Mais tentativas para lidar com locks temporários
      backoff: {
        type: 'exponential',
        delay: 1000, // 1s, 2s, 4s, 8s, 16s
      },
    removeOnComplete: {
      age: 3600, // Manter jobs completos por 1 hora
      count: 1000, // Máximo 1000 jobs completos
    },
    removeOnFail: {
      age: 86400, // Manter jobs falhos por 24 horas
    },
  },
});

/**
 * Enfileira uma mensagem recebida do WhatsApp para processamento
 * @param {object} payload - Dados da mensagem
 * @param {string} payload.remoteJid - JID do remetente
 * @param {string} payload.messageId - ID único da mensagem
 * @param {object} payload.messageKey - Chave completa da mensagem (key do Baileys)
 * @param {object} payload.message - Objeto da mensagem (message do Baileys)
 * @param {string} payload.number - Número extraído do JID
 * @returns {Promise<object>} Job criado
 */
async function enqueueIncomingMessage(payload) {
  const { remoteJid, messageId } = payload;

  // Job ID baseado no messageId para garantir idempotência
  // BullMQ não permite ':' e outros caracteres especiais no jobId
  // Sanitizar o messageId removendo/re substituindo caracteres problemáticos
  let sanitizedMessageId = messageId || '';
  // Substituir todos os caracteres problemáticos por '-'
  sanitizedMessageId = sanitizedMessageId.replace(/[:@#\s]/g, '-');
  // Remover múltiplos hífens consecutivos
  sanitizedMessageId = sanitizedMessageId.replace(/-+/g, '-');
  // Remover hífens no início e fim
  sanitizedMessageId = sanitizedMessageId.replace(/^-+|-+$/g, '');
  
  // Se após sanitização ficar vazio, usar hash do messageId original
  if (!sanitizedMessageId) {
    const crypto = require('crypto');
    sanitizedMessageId = crypto.createHash('md5').update(messageId || '').digest('hex').substring(0, 16);
  }
  
  let jobId = `msg-${sanitizedMessageId}`;
  
  // Garantir que jobId não contém caracteres problemáticos (sanitização final)
  jobId = jobId.replace(/[:@#\s]/g, '-').replace(/-+/g, '-').replace(/^-+|-+$/g, '');
  
  // Debug: verificar se jobId ainda contém caracteres inválidos
  if (jobId.includes(':')) {
    console.error(`[Queue] ERRO: jobId ainda contém ':' após sanitização! jobId=${jobId}, messageId=${messageId}`);
    // Forçar remoção de ':' como fallback final
    jobId = jobId.replace(/:/g, '-');
    console.warn(`[Queue] Usando jobId sanitizado final: ${jobId}`);
  }
  
  const finalJobId = jobId;

  // Adicionar remoteJid ao payload para agrupamento
  const jobData = {
    ...payload,
    // Timestamp para rastreamento
    enqueuedAt: new Date().toISOString(),
  };

  try {
    // Calcular prioridade normalizada (BullMQ aceita 0-2097152)
    // Usar timestamp normalizado para manter ordem: mensagens mais recentes = prioridade maior
    // Pegar os últimos dígitos do timestamp e normalizar para o range permitido
    const timestamp = Date.now();
    // Usar módulo para garantir que fique dentro do range
    // Prioridade máxima do BullMQ é 2097152, então normalizamos para 0-2097151
    const normalizedPriority = Math.floor(timestamp % 2097152);
    
    const job = await messageQueue.add(
      'process-message',
      jobData,
      {
        jobId: finalJobId, // Usar messageId sanitizado como jobId para evitar duplicatas
        // Prioridade normalizada: mensagens mais recentes têm prioridade ligeiramente maior
        // Range: 0-2097151 (dentro do limite do BullMQ)
        priority: normalizedPriority,
      }
    );

    console.log(`[Queue] Mensagem enfileirada: messageId=${messageId}, remoteJid=${remoteJid}, jobId=${job.id}`);
    return job;
  } catch (error) {
    console.error(`[Queue] Erro ao enfileirar mensagem ${messageId}:`, error.message);
    throw error;
  }
}

module.exports = {
  messageQueue,
  enqueueIncomingMessage,
};

