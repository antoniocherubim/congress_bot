/**
 * Gateway WhatsApp - BioSummit 2026
 * 
 * Responsabilidades:
 * - Conectar ao WhatsApp via Baileys
 * - Receber mensagens e enfileirar para processamento
 * - Endpoint /send-text para envio manual
 * - Endpoint /health para verificação
 * 
 * O processamento real das mensagens é feito pelo worker (worker/messageWorker.js)
 */
require('dotenv').config();
const express = require('express');
const {
  default: makeWASocket,
  useMultiFileAuthState,
  fetchLatestBaileysVersion,
  DisconnectReason,
} = require('@whiskeysockets/baileys');
const qrcode = require('qrcode-terminal');
const P = require('pino');
const fs = require('fs');
const path = require('path');
const { enqueueIncomingMessage } = require('./queue/messageQueue');
const { getRedisConnection } = require('./queue/redis');

const app = express();
// Aumentar limite para suportar áudio base64
app.use(express.json({ limit: '20mb' }));

const PORT = process.env.PORT || 3333;
const BOT_API_KEY = process.env.BOT_API_KEY;

let sockGlobal = null;

// Configuração de logging para arquivo
const logDir = path.join(__dirname, '..', 'logs');
if (!fs.existsSync(logDir)) {
  fs.mkdirSync(logDir, { recursive: true });
}

const logFile = path.join(logDir, 'gateway.log');

// Salvar métodos originais do console antes de substituir
const originalLog = console.log.bind(console);
const originalError = console.error.bind(console);
const originalWarn = console.warn.bind(console);
const originalInfo = console.info.bind(console);

// Função helper para logging que escreve no console e no arquivo
function logToFile(level, ...args) {
  const timestamp = new Date().toISOString();
  
  // Formatar mensagem para arquivo
  const messageParts = args.map(arg => {
    if (typeof arg === 'object') {
      try {
        return JSON.stringify(arg, null, 2);
      } catch {
        return String(arg);
      }
    }
    return String(arg);
  });
  const logMessage = `[${timestamp}] [${level.toUpperCase()}] ${messageParts.join(' ')}\n`;
  
  // Escrever no console usando método original (evita loop infinito)
  const consoleMethod = {
    'log': originalLog,
    'error': originalError,
    'warn': originalWarn,
    'info': originalInfo
  }[level] || originalLog;
  
  consoleMethod(`[${timestamp}] [${level.toUpperCase()}]`, ...args);
  
  // Escrever no arquivo (append)
  try {
    fs.appendFileSync(logFile, logMessage, 'utf8');
  } catch (error) {
    // Se falhar ao escrever no arquivo, usar método original para evitar loop
    originalError(`[ERRO] Falha ao escrever no arquivo de log: ${error.message}`);
  }
}

// Substituir console.log, console.error, console.warn, console.info
console.log = (...args) => {
  logToFile('log', ...args);
};

console.error = (...args) => {
  logToFile('error', ...args);
};

console.warn = (...args) => {
  logToFile('warn', ...args);
};

console.info = (...args) => {
  logToFile('info', ...args);
};

// Log inicial
console.log(`Logging configurado. Arquivo de log: ${logFile}`);
console.log(`Gateway iniciado em ${new Date().toISOString()}`);

// Contador de tentativas de reconexão
let reconnectAttempts = 0;
const MAX_RECONNECT_ATTEMPTS = 10;

async function startBaileys() {
  const { state, saveCreds } = await useMultiFileAuthState('./auth_info');
  const { version, isLatest } = await fetchLatestBaileysVersion();
  
  const sock = makeWASocket({
    version,
    logger: P({ level: 'silent' }),
    auth: state,
    browser: ['BioSummit Bot', 'Chrome', '1.0.0'],
    // Opções para garantir sincronização e salvamento de mensagens
    syncFullHistory: false, // Não sincronizar histórico completo (mais rápido)
    markOnlineOnConnect: true, // Marcar como online ao conectar
    generateHighQualityLinkPreview: false, // Desabilitar preview de links (mais rápido)
    // Função para recuperar mensagens quando necessário
    getMessage: async (key) => {
      // Retornar undefined para mensagens não encontradas
      return undefined;
    },
    // Timeout de conexão aumentado
    connectTimeoutMs: 60000, // 60 segundos
    defaultQueryTimeoutMs: 60000, // 60 segundos
  });

  sock.ev.on('connection.update', (update) => {
    const { connection, lastDisconnect, qr } = update;
    
    if (qr) {
      console.log('QR Code gerado, escaneie com o WhatsApp:');
      qrcode.generate(qr, { small: true });
      reconnectAttempts = 0; // Reset contador ao gerar QR
    }

    if (connection === 'close') {
      const statusCode = lastDisconnect?.error?.output?.statusCode;
      const isLoggedOut = statusCode === DisconnectReason.loggedOut;
      const isUnauthorized = statusCode === 401;
      const isTimeout = statusCode === 408;
      
      console.log('Conexão fechada');
      console.log(`Código de erro: ${statusCode}`);
      
      if (isUnauthorized || isLoggedOut) {
        console.error('');
        console.error('⚠️  ERRO: Sessão expirada ou invalidada (401/Logged Out)');
        console.error('');
        console.error('Para resolver:');
        console.error('1. Pare o gateway');
        console.error('2. Delete a pasta auth_info:');
        console.error('   rm -rf whatsapp-gateway/auth_info');
        console.error('3. Inicie o gateway novamente e escaneie o QR Code');
        console.error('');
        reconnectAttempts = 0;
        process.exit(1);
      } else if (isTimeout) {
        reconnectAttempts++;
        
        if (reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
          console.error('');
          console.error(`⚠️  ERRO: Muitas tentativas de reconexão (${reconnectAttempts})`);
          console.error('O WhatsApp pode estar bloqueando a conexão ou há problema de rede.');
          console.error('');
          console.error('Soluções:');
          console.error('1. Verifique sua conexão com a internet');
          console.error('2. Aguarde alguns minutos e reinicie o gateway');
          console.error('3. Se persistir, delete auth_info e reconecte:');
          console.error('   rm -rf whatsapp-gateway/auth_info');
          console.error('');
          reconnectAttempts = 0;
          // Não sair, apenas aguardar mais tempo antes de tentar novamente
          setTimeout(() => {
            reconnectAttempts = 0; // Reset após espera longa
            startBaileys();
          }, 60000); // Aguardar 1 minuto
        } else {
          // Backoff exponencial: 3s, 6s, 12s, 24s, 48s, max 60s
          const delay = Math.min(3000 * Math.pow(2, reconnectAttempts - 1), 60000);
          console.log(`Reconectando automaticamente em ${delay/1000}s (tentativa ${reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})...`);
          setTimeout(() => {
            startBaileys();
          }, delay);
        }
      } else {
        // Outros erros: reconexão com backoff
        reconnectAttempts++;
        const delay = Math.min(3000 * Math.pow(2, Math.min(reconnectAttempts - 1, 4)), 30000);
        console.log(`Reconectando automaticamente em ${delay/1000}s (tentativa ${reconnectAttempts})...`);
        setTimeout(() => {
          startBaileys();
        }, delay);
      }
    } else if (connection === 'open') {
      console.log('✅ Conectado ao WhatsApp com sucesso!');
      reconnectAttempts = 0; // Reset contador ao conectar com sucesso
      sockGlobal = sock; // Salvar referência global
    }
  });

  sock.ev.on('creds.update', saveCreds);

  // Handlers adicionais para verificar sincronização (opcional, apenas para debug)
  sock.ev.on('messages.update', async (updates) => {
    // Log apenas se necessário (evitar spam)
    if (process.env.DEBUG_MESSAGES === 'true') {
      for (const update of updates) {
        if (update.update) {
          console.log('[DEBUG] Status da mensagem atualizado:', {
            id: update.key?.id,
            status: update.update?.status,
            fromMe: update.key?.fromMe,
            remoteJid: update.key?.remoteJid
          });
        }
      }
    }
  });

  // Handler para mensagens recebidas - APENAS ENFILEIRAR
  sock.ev.on('messages.upsert', async (m) => {
    // Processar apenas mensagens novas (tipo 'notify')
    if (m.type === 'append') {
      if (process.env.DEBUG_MESSAGES === 'true') {
        console.log('[DEBUG] Mensagens antigas sincronizadas:', m.messages?.length || 0);
      }
      return;
    }
    
    if (m.type !== 'notify') {
      return;
    }

    const messages = m.messages || [];
    
    if (messages.length > 0) {
      console.log(`[Gateway] ${messages.length} mensagem(ns) recebida(s), enfileirando...`);
    }
    
    // Processar cada mensagem: apenas filtrar e enfileirar
    for (const msg of messages) {
      try {
        const messageKey = msg.key;
        const messageRemoteJid = messageKey?.remoteJid;
        const messageFromMe = messageKey?.fromMe;
        const messageId = messageKey?.id;

        // Ignorar mensagens enviadas por você mesmo
        if (messageFromMe) {
          continue;
        }

        // Filtrar apenas conversas individuais
        if (!messageRemoteJid) {
          continue;
        }
        
        // Ignorar grupos e broadcasts
        if (messageRemoteJid.endsWith('@g.us') || messageRemoteJid.endsWith('@broadcast')) {
          continue;
        }

        // Extrair número do JID
        const number = messageRemoteJid.split('@')[0];

        // Preparar payload mínimo para enfileirar
        const payload = {
          remoteJid: messageRemoteJid,
          messageId: messageId,
          messageKey: messageKey,
          message: msg.message, // Objeto completo da mensagem
          number: number,
        };

        // Enfileirar mensagem para processamento pelo worker
        await enqueueIncomingMessage(payload);
        
        console.log(`[Gateway] Mensagem enfileirada: messageId=${messageId}, remoteJid=${messageRemoteJid}`);
      } catch (error) {
        console.error(`[Gateway] Erro ao enfileirar mensagem:`, error.message);
        // Não interrompe o loop, continua com próxima mensagem
      }
    }
  });

  sockGlobal = sock;
}

// Endpoint para envio manual de mensagens
app.post('/send-text', async (req, res) => {
  try {
    // Verificar autenticação se BOT_API_KEY estiver configurada
    if (BOT_API_KEY && BOT_API_KEY.trim()) {
      const providedKey = req.headers['x-api-key'];
      if (!providedKey || providedKey !== BOT_API_KEY) {
        return res.status(401).json({
          error: 'Não autorizado. X-API-KEY inválida ou ausente.',
        });
      }
    }

    const { number, text } = req.body;

    if (!number || !text) {
      return res.status(400).json({
        error: 'Campos "number" e "text" são obrigatórios',
      });
    }

    if (!sockGlobal) {
      return res.status(503).json({
        error: 'WhatsApp não está conectado',
      });
    }

    // Buscar último remoteJid conhecido no Redis, ou usar fallback
    const redis = getRedisConnection();
    let jid = await redis.get(`jid:number:${number}`);
    
    if (!jid) {
      // Fallback para @s.whatsapp.net se não encontrar no Redis
      jid = `${number}@s.whatsapp.net`;
      console.log(`[Send-Text] JID não encontrado no Redis para ${number}, usando fallback: ${jid}`);
    } else {
      console.log(`[Send-Text] Usando JID do Redis para ${number}: ${jid}`);
    }

    await sockGlobal.sendMessage(jid, { text });

    res.json({
      success: true,
      message: 'Mensagem enviada com sucesso',
      number,
      jid: jid,
    });
  } catch (error) {
    console.error('[Erro no /send-text]', error);
    res.status(500).json({
      error: 'Erro ao enviar mensagem',
      message: error.message,
    });
  }
});

// Endpoint de health check
app.get('/health', (req, res) => {
  res.json({
    status: 'ok',
    whatsapp_connected: sockGlobal !== null,
    timestamp: new Date().toISOString(),
  });
});

// Iniciar Baileys e depois o servidor HTTP
startBaileys()
  .then(() => {
    app.listen(PORT, () => {
      console.log(`HTTP server ON em http://localhost:${PORT}`);
      console.log(`Gateway pronto para receber mensagens (processamento via worker)`);
      if (BOT_API_KEY && BOT_API_KEY.trim()) {
        console.log(`[INFO] Autenticação habilitada: BOT_API_KEY configurada`);
      } else {
        console.log(`[INFO] Modo desenvolvimento: BOT_API_KEY não configurada (autenticação desabilitada)`);
      }
    });
  })
  .catch((error) => {
    console.error('Erro ao iniciar gateway:', error);
    process.exit(1);
  });

// Graceful shutdown
process.on('SIGTERM', async () => {
  console.log('[Gateway] SIGTERM recebido, encerrando...');
  process.exit(0);
});

process.on('SIGINT', async () => {
  console.log('[Gateway] SIGINT recebido, encerrando...');
  process.exit(0);
});
