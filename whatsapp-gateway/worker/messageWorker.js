/**
 * Worker BullMQ para processar mensagens do WhatsApp
 * 
 * Responsabilidades:
 * - Deduplicação por messageId
 * - Extração de texto (texto, áudio, imagem, etc.)
 * - Chamada ao backend Python com timeout
 * - Envio de resposta via endpoint do gateway (/send-text)
 * - Controle de concorrência (1 por conversa)
 */
require('dotenv').config();
const { Worker } = require('bullmq');
const {
  default: makeWASocket,
  useMultiFileAuthState,
  fetchLatestBaileysVersion,
  downloadMediaMessage,
} = require('@whiskeysockets/baileys');
const P = require('pino');
const { getRedisConnection } = require('../queue/redis');
const { fetchWithTimeout } = require('../utils/http');

const redis = getRedisConnection();
const BOT_URL = process.env.BOT_URL || 'http://localhost:8000';
const GATEWAY_URL = process.env.GATEWAY_URL || 'http://gateway:3333';
const BOT_WHATSAPP_ENDPOINT = '/whatsapp';
const GATEWAY_SEND_ENDPOINT = '/send-text';
const QUEUE_CONCURRENCY = parseInt(process.env.QUEUE_CONCURRENCY || '20', 10);
const DEDUPE_TTL_SECONDS = parseInt(process.env.DEDUPE_TTL_SECONDS || '21600', 10); // 6 horas
const LOCK_TTL_SECONDS = parseInt(process.env.LOCK_TTL_SECONDS || '60', 10);
const HTTP_TIMEOUT_MS = parseInt(process.env.HTTP_TIMEOUT_MS || '20000', 10);

// Socket Baileys temporário apenas para download de mídia (áudio)
let sockForMedia = null;

/**
 * Inicializa socket Baileys temporário apenas para download de mídia
 * (não usado para enviar mensagens, apenas para downloadMediaMessage)
 */
async function initBaileysSocketForMedia() {
  if (sockForMedia) {
    return sockForMedia;
  }

  try {
    const { state } = await useMultiFileAuthState('./auth_info');
    const { version } = await fetchLatestBaileysVersion();

    const sock = makeWASocket({
      version,
      logger: P({ level: 'silent' }),
      auth: state,
      browser: ['BioSummit Bot Worker', 'Chrome', '1.0.0'],
      syncFullHistory: false,
      markOnlineOnConnect: false, // Não marcar online, apenas para download
      generateHighQualityLinkPreview: false,
      getMessage: async () => undefined,
    });

    sockForMedia = sock;
    console.log('[Worker] Socket Baileys para mídia inicializado');
    return sock;
  } catch (error) {
    console.error('[Worker] Erro ao inicializar Baileys para mídia:', error.message);
    throw error;
  }
}

/**
 * Verifica se messageId já foi processado (deduplicação)
 * @param {string} messageId - ID da mensagem
 * @returns {Promise<boolean>} true se já foi processado
 */
async function isMessageProcessed(messageId) {
  const key = `dedupe:msg:${messageId}`;
  const result = await redis.set(key, '1', 'EX', DEDUPE_TTL_SECONDS, 'NX');
  return result === null; // null significa que a chave já existia
}

/**
 * Tenta adquirir lock para processar mensagem de uma conversa
 * @param {string} remoteJid - JID da conversa
 * @returns {Promise<boolean>} true se conseguiu o lock
 */
async function acquireConversationLock(remoteJid) {
  const lockKey = `lock:jid:${remoteJid}`;
  const lockValue = `${Date.now()}`;
  const result = await redis.set(lockKey, lockValue, 'EX', LOCK_TTL_SECONDS, 'NX');
  return result !== null; // não-null significa que conseguiu o lock
}

/**
 * Renova o lock durante processamento
 * @param {string} remoteJid - JID da conversa
 */
async function renewConversationLock(remoteJid) {
  const lockKey = `lock:jid:${remoteJid}`;
  await redis.expire(lockKey, LOCK_TTL_SECONDS);
}

/**
 * Libera o lock da conversa
 * @param {string} remoteJid - JID da conversa
 */
async function releaseConversationLock(remoteJid) {
  const lockKey = `lock:jid:${remoteJid}`;
  await redis.del(lockKey);
}

/**
 * Extrai texto da mensagem (suporta texto, extendedText, caption, áudio)
 * @param {object} message - Objeto da mensagem do Baileys
 * @param {object} messageKey - Chave da mensagem
 * @returns {Promise<string>} Texto extraído ou vazio
 */
async function extractText(message, messageKey) {
  // Texto simples
  if (message?.conversation) {
    return message.conversation;
  }

  // Texto estendido
  if (message?.extendedTextMessage?.text) {
    return message.extendedTextMessage.text;
  }

  // Caption de imagem/documento
  if (message?.imageMessage?.caption) {
    return message.imageMessage.caption;
  }
  if (message?.documentMessage?.caption) {
    return message.documentMessage.caption;
  }

  // Áudio - precisa transcrever
  if (message?.audioMessage) {
    try {
      console.log(`[Worker] Transcrevendo áudio: messageId=${messageKey.id}`);
      
      // Inicializar socket apenas para download de mídia
      if (!sockForMedia) {
        await initBaileysSocketForMedia();
      }
      
      const mediaBuffer = await downloadMediaMessage(
        { key: messageKey, message },
        'buffer',
        {},
        {
          logger: P({ level: 'silent' }),
          reuploadRequest: sockForMedia.updateMediaMessage,
        }
      );

      const buffer = Buffer.isBuffer(mediaBuffer) ? mediaBuffer : Buffer.from(mediaBuffer);
      const audioBase64 = buffer.toString('base64');

      // Chamar endpoint de transcrição com timeout
      const headers = {
        'Content-Type': 'application/json',
      };

      const apiKey = process.env.BOT_API_KEY;
      if (apiKey && apiKey.trim()) {
        headers['X-API-KEY'] = apiKey;
      }

      const response = await fetchWithTimeout(
        `${BOT_URL}/transcribe-audio`,
        {
          method: 'POST',
          headers,
          body: JSON.stringify({ audio_base64: audioBase64 }),
        },
        HTTP_TIMEOUT_MS
      );

      if (!response.ok) {
        console.error(`[Worker] Erro ao transcrever áudio: Status ${response.status}`);
        return '';
      }

      const data = await response.json();
      return data.text || '';
    } catch (error) {
      console.error(`[Worker] Erro ao processar áudio: ${error.message}`);
      return '';
    }
  }

  return '';
}

/**
 * Salva mapeamento number -> remoteJid no Redis
 * @param {string} number - Número do telefone
 * @param {string} remoteJid - JID completo
 */
async function saveNumberToJidMapping(number, remoteJid) {
  const key = `jid:number:${number}`;
  await redis.set(key, remoteJid, 'EX', 86400 * 7); // 7 dias
}

/**
 * Busca último remoteJid conhecido para um número
 * @param {string} number - Número do telefone
 * @returns {Promise<string|null>} JID ou null
 */
async function getJidForNumber(number) {
  const key = `jid:number:${number}`;
  return await redis.get(key);
}

// Socket será inicializado sob demanda apenas para download de mídia

// Criar worker
const worker = new Worker(
  'whatsapp-messages',
  async (job) => {
    const { remoteJid, messageId, messageKey, message, number } = job.data;

    console.log(`[Worker] Processando job: messageId=${messageId}, remoteJid=${remoteJid}`);

    // 1. Deduplicação
    if (await isMessageProcessed(messageId)) {
      console.log(`[Worker] Mensagem ${messageId} já foi processada (duplicata ignorada)`);
      return { status: 'duplicate', messageId };
    }

    // 2. Adquirir lock da conversa
    const hasLock = await acquireConversationLock(remoteJid);
    if (!hasLock) {
      console.log(`[Worker] Lock não disponível para ${remoteJid}, job será retentado`);
      // Lançar erro para BullMQ fazer retry (com backoff exponencial)
      // O job será reprocessado após delay, quando o lock pode estar disponível
      const error = new Error('LOCK_NOT_AVAILABLE');
      error.name = 'LockNotAvailable';
      throw error;
    }

    try {
      // Renovar lock periodicamente durante processamento
      const lockRenewalInterval = setInterval(() => {
        renewConversationLock(remoteJid).catch(() => {
          // Ignorar erros de renovação
        });
      }, (LOCK_TTL_SECONDS * 1000) / 2); // Renovar na metade do TTL

      // 3. Salvar mapeamento number -> remoteJid
      await saveNumberToJidMapping(number, remoteJid);

      // 4. Extrair texto (socket será inicializado automaticamente se precisar de mídia)
      const text = await extractText(message, messageKey);

      if (!text || !text.trim()) {
        console.log(`[Worker] Mensagem ${messageId} sem texto processável`);
        clearInterval(lockRenewalInterval);
        await releaseConversationLock(remoteJid);
        return { status: 'no_text', messageId };
      }

      // 7. Chamar backend Python
      const headers = {
        'Content-Type': 'application/json',
      };

      const apiKey = process.env.BOT_API_KEY;
      if (apiKey && apiKey.trim()) {
        headers['X-API-KEY'] = apiKey;
      }

      const response = await fetchWithTimeout(
        `${BOT_URL}${BOT_WHATSAPP_ENDPOINT}`,
        {
          method: 'POST',
          headers,
          body: JSON.stringify({
            number: number,
            text: text,
          }),
        },
        HTTP_TIMEOUT_MS
      );

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Backend retornou ${response.status}: ${errorText}`);
      }

      const data = await response.json();
      const reply = data.reply || '';

      // 8. Enviar resposta via endpoint do gateway
      if (reply && reply.trim()) {
        const sendHeaders = {
          'Content-Type': 'application/json',
        };

        const apiKey = process.env.BOT_API_KEY;
        if (apiKey && apiKey.trim()) {
          sendHeaders['X-API-KEY'] = apiKey;
        }

        const sendResponse = await fetchWithTimeout(
          `${GATEWAY_URL}${GATEWAY_SEND_ENDPOINT}`,
          {
            method: 'POST',
            headers: sendHeaders,
            body: JSON.stringify({
              number: number,
              text: reply,
            }),
          },
          HTTP_TIMEOUT_MS
        );

        if (!sendResponse.ok) {
          const errorText = await sendResponse.text();
          throw new Error(`Gateway retornou ${sendResponse.status} ao enviar mensagem: ${errorText}`);
        }

        console.log(`[Worker] Resposta enviada via gateway: messageId=${messageId}, remoteJid=${remoteJid}`);
      } else {
        console.warn(`[Worker] Resposta vazia do backend para messageId=${messageId}`);
      }

      clearInterval(lockRenewalInterval);
      await releaseConversationLock(remoteJid);

      return { status: 'success', messageId, replyLength: reply.length };
    } catch (error) {
      // Liberar lock em caso de erro
      try {
        await releaseConversationLock(remoteJid);
      } catch (releaseError) {
        // Ignorar erro ao liberar lock
      }
      
      console.error(`[Worker] Erro ao processar mensagem ${messageId}:`, error.message);
      
      // Se for erro de lock, não contar como tentativa (será retentado)
      if (error.name === 'LockNotAvailable' || error.message === 'LOCK_NOT_AVAILABLE') {
        // Não fazer nada, BullMQ vai fazer retry automaticamente
      }
      
      throw error; // BullMQ vai fazer retry
    }
  },
  {
    connection: redis,
    concurrency: QUEUE_CONCURRENCY,
    limiter: {
      max: QUEUE_CONCURRENCY,
      duration: 1000,
    },
  }
);

worker.on('completed', (job) => {
  console.log(`[Worker] Job ${job.id} completado`);
});

worker.on('failed', (job, error) => {
  console.error(`[Worker] Job ${job?.id} falhou:`, error.message);
});

worker.on('error', (error) => {
  console.error('[Worker] Erro no worker:', error);
});

console.log(`[Worker] Worker iniciado com concorrência ${QUEUE_CONCURRENCY}`);
console.log(`[Worker] Aguardando jobs...`);

// Graceful shutdown
process.on('SIGTERM', async () => {
  console.log('[Worker] SIGTERM recebido, encerrando...');
  await worker.close();
  await redis.quit();
  process.exit(0);
});

process.on('SIGINT', async () => {
  console.log('[Worker] SIGINT recebido, encerrando...');
  await worker.close();
  await redis.quit();
  process.exit(0);
});

