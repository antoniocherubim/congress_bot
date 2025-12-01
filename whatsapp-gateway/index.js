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
const fetch = require('node-fetch');

const app = express();
app.use(express.json());

const BOT_URL = process.env.BOT_URL || 'http://localhost:8000';
const BOT_WHATSAPP_ENDPOINT = '/whatsapp';
const PORT = process.env.PORT || 3333;

let sockGlobal = null;

async function startBaileys() {
  const { state, saveCreds } = await useMultiFileAuthState('./auth_info');
  const { version, isLatest } = await fetchLatestBaileysVersion();
  
  const sock = makeWASocket({
    version,
    logger: P({ level: 'silent' }),
    printQRInTerminal: true,
    auth: state,
    browser: ['BioSummit Bot', 'Chrome', '1.0.0'],
  });

  sock.ev.on('connection.update', (update) => {
    const { connection, lastDisconnect, qr } = update;
    
    if (qr) {
      console.log('QR Code gerado, escaneie com o WhatsApp:');
      qrcode.generate(qr, { small: true });
    }

    if (connection === 'close') {
      const shouldReconnect = (lastDisconnect?.error?.output?.statusCode !== DisconnectReason.loggedOut);
      
      console.log('Conexão fechada', lastDisconnect?.error);
      
      if (shouldReconnect) {
        console.log('Reconectando...');
        startBaileys();
      }
    } else if (connection === 'open') {
      console.log('✅ Conectado ao WhatsApp com sucesso!');
    }
  });

  sock.ev.on('creds.update', saveCreds);

  // Handler para mensagens recebidas
  sock.ev.on('messages.upsert', async (m) => {
    const messages = m.messages || [];
    
    for (const msg of messages) {
      // Ignorar mensagens enviadas por você mesmo
      if (msg.key.fromMe) {
        continue;
      }

      // Ignorar mensagens de grupos e broadcast (só aceitar JIDs que terminam com @s.whatsapp.net)
      const remoteJid = msg.key.remoteJid;
      if (!remoteJid || !remoteJid.endsWith('@s.whatsapp.net')) {
        continue;
      }

      // Extrair número do JID (ex: "5541999380969@s.whatsapp.net" -> "5541999380969")
      const number = remoteJid.split('@')[0];

      // Extrair texto da mensagem
      let text = '';
      if (msg.message?.conversation) {
        text = msg.message.conversation;
      } else if (msg.message?.extendedTextMessage?.text) {
        text = msg.message.extendedTextMessage.text;
      }

      // Ignorar se não houver texto
      if (!text || !text.trim()) {
        continue;
      }

      console.log(`[Mensagem recebida] De: ${number}, Texto: ${text.substring(0, 50)}...`);

      try {
        // Enviar para o backend Python
        const response = await fetch(`${BOT_URL}${BOT_WHATSAPP_ENDPOINT}`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-API-KEY': process.env.BOT_API_KEY || '',
          },
          body: JSON.stringify({
            number: number,
            text: text,
          }),
        });

        if (!response.ok) {
          const errorText = await response.text();
          console.error(
            `[Erro ao chamar backend] Status: ${response.status}, ` +
            `Response: ${errorText}`
          );
          continue;
        }

        const data = await response.json();
        const reply = data.reply || '';

        if (reply && reply.trim()) {
          // Enviar resposta de volta ao usuário
          await sockGlobal.sendMessage(remoteJid, { text: reply });
          console.log(`[Resposta enviada] Para: ${number}, Resposta: ${reply.substring(0, 50)}...`);
        } else {
          console.warn(`[Aviso] Resposta vazia do backend para número: ${number}`);
        }
      } catch (error) {
        console.error(`[Erro ao processar mensagem] De: ${number}, Erro: ${error.message}`);
      }
    }
  });

  sockGlobal = sock;
}

// Endpoint para envio manual de mensagens (mantido para testes)
app.post('/send-text', async (req, res) => {
  try {
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

    const jid = `${number}@s.whatsapp.net`;
    await sockGlobal.sendMessage(jid, { text });

    res.json({
      success: true,
      message: 'Mensagem enviada com sucesso',
      number,
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
  });
});

// Iniciar Baileys e depois o servidor HTTP
startBaileys()
  .then(() => {
    app.listen(PORT, () => {
      console.log(`HTTP server ON em http://localhost:${PORT}`);
      console.log(`Backend Python configurado em: ${BOT_URL}`);
    });
  })
  .catch((error) => {
    console.error('Erro ao iniciar gateway:', error);
    process.exit(1);
  });

