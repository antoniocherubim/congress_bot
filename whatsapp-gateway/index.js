require('dotenv').config();
const express = require('express');
const {
  default: makeWASocket,
  useMultiFileAuthState,
  fetchLatestBaileysVersion,
  DisconnectReason,
  downloadMediaMessage,
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
      const statusCode = lastDisconnect?.error?.output?.statusCode;
      const isLoggedOut = statusCode === DisconnectReason.loggedOut;
      const isUnauthorized = statusCode === 401;
      
      console.log('Conexão fechada');
      console.log(`Código de erro: ${statusCode}`);
      
      if (isUnauthorized || isLoggedOut) {
        console.error('');
        console.error('⚠️  ERRO: Sessão expirada ou invalidada (401/Logged Out)');
        console.error('');
        console.error('Para resolver:');
        console.error('1. Pare o gateway (Ctrl+C)');
        console.error('2. Delete a pasta auth_info:');
        console.error('   rm -rf whatsapp-gateway/auth_info');
        console.error('   (ou no Windows: rmdir /s whatsapp-gateway\\auth_info)');
        console.error('3. Inicie o gateway novamente e escaneie o QR Code');
        console.error('');
        process.exit(1);
      } else {
        console.log('Reconectando automaticamente...');
        setTimeout(() => {
          startBaileys();
        }, 3000);
      }
    } else if (connection === 'open') {
      console.log('✅ Conectado ao WhatsApp com sucesso!');
    }
  });

  sock.ev.on('creds.update', saveCreds);

  // Handler para mensagens recebidas
  sock.ev.on('messages.upsert', async (m) => {
    // IMPORTANTE: Processar apenas mensagens novas (tipo 'notify')
    // Ignorar sincronizações de mensagens antigas (tipo 'append')
    if (m.type !== 'notify') {
      return;
    }

    console.log('[DEBUG] messages.upsert acionado, tipo:', m.type);
    const messages = m.messages || [];
    console.log(`[DEBUG] Total de mensagens recebidas: ${messages.length}`);
    
    for (const msg of messages) {
      console.log('[DEBUG] Processando mensagem:', {
        fromMe: msg.key?.fromMe,
        remoteJid: msg.key?.remoteJid,
        hasMessage: !!msg.message,
        messageType: msg.message ? Object.keys(msg.message)[0] : 'none'
      });

      // Ignorar mensagens enviadas por você mesmo
      if (msg.key?.fromMe) {
        console.log('[DEBUG] Mensagem ignorada: enviada pelo próprio bot');
        continue;
      }

      // Filtrar apenas conversas individuais (ignorar grupos e broadcasts)
      const remoteJid = msg.key?.remoteJid;
      if (!remoteJid) {
        console.log('[DEBUG] Mensagem ignorada: remoteJid vazio');
        continue;
      }
      
      // Ignorar grupos (@g.us) e broadcasts (@broadcast)
      if (remoteJid.endsWith('@g.us')) {
        console.log(`[DEBUG] Mensagem ignorada: é um grupo (JID: ${remoteJid})`);
        continue;
      }
      
      if (remoteJid.endsWith('@broadcast')) {
        console.log(`[DEBUG] Mensagem ignorada: é um broadcast (JID: ${remoteJid})`);
        continue;
      }
      
      // Aceitar conversas individuais (podem ter diferentes sufixos: @s.whatsapp.net, @lid, etc.)
      // Qualquer JID que não seja grupo ou broadcast é considerado conversa individual

      // Extrair número do JID (funciona com @s.whatsapp.net, @lid, etc.)
      // Exemplos:
      // "5541999380969@s.whatsapp.net" -> "5541999380969"
      // "177077240250390@lid" -> "177077240250390"
      const number = remoteJid.split('@')[0];

      // Extrair texto da mensagem ou processar áudio
      let text = '';
      
      // Verificar se é mensagem de texto
      if (msg.message?.conversation) {
        text = msg.message.conversation;
      } else if (msg.message?.extendedTextMessage?.text) {
        text = msg.message.extendedTextMessage.text;
      }
      // Verificar se é mensagem de áudio
      else if (msg.message?.audioMessage) {
        try {
          console.log(`[Áudio recebido] De: ${number}, processando...`);
          
          // Baixar o áudio do WhatsApp
          const mediaBuffer = await downloadMediaMessage(
            msg,
            'buffer',
            {},
            { 
              logger: P({ level: 'silent' }),
              reuploadRequest: sock.updateMediaMessage
            }
          );
          
          // Garantir que seja um Buffer
          const buffer = Buffer.isBuffer(mediaBuffer) 
            ? mediaBuffer 
            : Buffer.from(mediaBuffer);
          
          // Converter para base64
          const audioBase64 = buffer.toString('base64');
          
          // Enviar para o backend Python para transcrever
          const headers = {
            'Content-Type': 'application/json',
          };
          
          const apiKey = process.env.BOT_API_KEY;
          if (apiKey && apiKey.trim()) {
            headers['X-API-KEY'] = apiKey;
          }
          
          const transcribeResponse = await fetch(`${BOT_URL}/transcribe-audio`, {
            method: 'POST',
            headers: headers,
            body: JSON.stringify({
              audio_base64: audioBase64,
            }),
          });
          
          if (!transcribeResponse.ok) {
            console.error(`[Erro ao transcrever áudio] Status: ${transcribeResponse.status}`);
            // Enviar mensagem de erro ao usuário
            await sock.sendMessage(remoteJid, { 
              text: 'Desculpe, não consegui processar o áudio. Por favor, tente enviar uma mensagem de texto.' 
            });
            continue;
          }
          
          const transcribeData = await transcribeResponse.json();
          text = transcribeData.text || '';
          
          if (!text || !text.trim()) {
            console.warn(`[Aviso] Transcrição vazia do áudio para número: ${number}`);
            await sock.sendMessage(remoteJid, { 
              text: 'Não consegui entender o áudio. Por favor, tente novamente ou envie uma mensagem de texto.' 
            });
            continue;
          }
          
          console.log(`[Áudio transcrito] De: ${number}, Texto: ${text.substring(0, 50)}...`);
        } catch (error) {
          console.error(`[Erro ao processar áudio] De: ${number}, Erro: ${error.message}`);
          await sock.sendMessage(remoteJid, { 
            text: 'Desculpe, ocorreu um erro ao processar seu áudio. Por favor, tente enviar uma mensagem de texto.' 
          });
          continue;
        }
      }

      // Ignorar se não houver texto (nem texto direto, nem áudio transcrito)
      if (!text || !text.trim()) {
        console.log('[DEBUG] Mensagem ignorada: sem texto (pode ser outro tipo de mídia)');
        continue;
      }

      console.log(`[Mensagem recebida] De: ${number}, Texto: ${text.substring(0, 50)}...`);

      try {
        // Preparar headers
        const headers = {
          'Content-Type': 'application/json',
        };
        
        // Adicionar API key apenas se configurada
        const apiKey = process.env.BOT_API_KEY;
        if (apiKey && apiKey.trim()) {
          headers['X-API-KEY'] = apiKey;
        }
        
        // Enviar para o backend Python
        const response = await fetch(`${BOT_URL}${BOT_WHATSAPP_ENDPOINT}`, {
          method: 'POST',
          headers: headers,
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
          // CORREÇÃO: usar sock diretamente (já está no escopo) ao invés de sockGlobal
          await sock.sendMessage(remoteJid, { text: reply });
          console.log(`[Resposta enviada] Para: ${number}, Resposta: ${reply.substring(0, 50)}...`);
        } else {
          console.warn(`[Aviso] Resposta vazia do backend para número: ${number}`);
        }
      } catch (error) {
        console.error(`[Erro ao processar mensagem] De: ${number}, Erro: ${error.message}`);
        console.error(`[DEBUG] Stack:`, error.stack);
      }
    }
    
    console.log(`[DEBUG] Loop de processamento concluído. Mensagens processadas.`);
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
      const apiKey = process.env.BOT_API_KEY;
      if (apiKey && apiKey.trim()) {
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

