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
  // BullMQ não permite ':' no jobId, então usamos '-' como separador
  const jobId = `msg-${messageId}`;

  // Adicionar remoteJid ao payload para agrupamento
  const jobData = {
    ...payload,
    // Timestamp para rastreamento
    enqueuedAt: new Date().toISOString(),
  };

  try {
    const job = await messageQueue.add(
      'process-message',
      jobData,
      {
        jobId, // Usar messageId como jobId para evitar duplicatas
        // Prioridade: mensagens mais recentes têm prioridade ligeiramente maior
        priority: Date.now(),
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

