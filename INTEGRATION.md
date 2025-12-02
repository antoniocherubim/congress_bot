# Guia de Integração - Gateway WhatsApp + Backend Python

Este documento descreve como configurar e executar o sistema integrado de chatbot do BioSummit 2026.

## Visão Geral

O sistema consiste em dois componentes principais:

1. **Backend Python (FastAPI)**: Processa mensagens usando ChatbotEngine e OpenAI
2. **Gateway WhatsApp (Node.js)**: Conecta ao WhatsApp via Baileys e envia mensagens para o backend

## Arquitetura

```
WhatsApp User → Gateway Node.js → Backend Python (FastAPI) → OpenAI
                (Baileys)          (ChatbotEngine)
                     ↑                      ↓
                     └──────── resposta ────┘
```

## Configuração

### 1. Backend Python

#### Variáveis de Ambiente

Crie um arquivo `.env` na raiz do projeto Python:

```env
# OpenAI
OPENAI_API_KEY=sua-chave-openai-aqui
OPENAI_MODEL=gpt-4o-mini

# Banco de Dados
DATABASE_URL=sqlite:///./biosummit.db

# Email (para fluxo de inscrição)
SMTP_HOST=dev-log
SMTP_PORT=587
SMTP_USER=seu-usuario-smtp
SMTP_PASSWORD=sua-senha-smtp
SMTP_FROM=inscricao@biosummit.com.br

# Autenticação entre Node e Python (IMPORTANTE: deve ser igual ao gateway)
BOT_API_KEY=uma-chave-secreta-aleatoria
```

#### Executar Backend

```bash
# Ativar ambiente virtual
source venv/bin/activate  # Linux/Mac
# ou
.\venv\Scripts\activate  # Windows

# Instalar dependências (se necessário)
pip install -r requirements.txt

# Executar servidor
python main.py
```

O backend estará disponível em `http://localhost:8000`

### 2. Gateway WhatsApp

#### Instalação

```bash
cd whatsapp-gateway
npm install
```

#### Variáveis de Ambiente

Crie um arquivo `.env` no diretório `whatsapp-gateway/`:

```env
# URL do backend Python
BOT_URL=http://localhost:8000

# Chave de autenticação (DEVE SER A MESMA do backend Python)
BOT_API_KEY=uma-chave-secreta-aleatoria

# Porta do gateway
PORT=3000
```

**⚠️ IMPORTANTE**: A `BOT_API_KEY` deve ser **exatamente a mesma** no backend Python e no gateway Node.js.

#### Executar Gateway

```bash
cd whatsapp-gateway
npm start
```

Ou em modo desenvolvimento:
```bash
npm run dev
```

## Fluxo de Funcionamento

### 1. Inicialização

1. Inicie o backend Python primeiro (`python main.py`)
2. Inicie o gateway WhatsApp (`npm start` no diretório `whatsapp-gateway/`)
3. Escaneie o QR Code exibido no terminal do gateway com o WhatsApp que será usado como bot

### 2. Processamento de Mensagens

Quando um usuário envia uma mensagem no WhatsApp:

1. **Gateway recebe** a mensagem via Baileys
2. **Gateway valida**:
   - Ignora mensagens próprias
   - Ignora grupos/broadcasts (só conversas individuais)
   - Extrai número e texto da mensagem
3. **Gateway envia** POST para `http://localhost:8000/whatsapp` com:
   ```json
   {
     "number": "5541999380969",
     "text": "Olá, quero me inscrever"
   }
   ```
4. **Backend Python**:
   - Valida autenticação via header `X-API-KEY`
   - Processa mensagem usando `ChatbotEngine.handle_message()`
   - Retorna resposta:
     ```json
     {
       "reply": "Olá! Vamos fazer sua inscrição..."
     }
     ```
5. **Gateway recebe** a resposta e envia de volta ao usuário no WhatsApp

## Endpoints

### Backend Python

#### POST /chat
Endpoint original para testes HTTP diretos.

**Request:**
```json
{
  "user_id": "user123",
  "message": "Qual é a programação?"
}
```

#### POST /whatsapp
Endpoint para integração com gateway WhatsApp.

**Request:**
```json
{
  "number": "5541999380969",
  "text": "Olá!"
}
```

**Headers:**
```
X-API-KEY: uma-chave-secreta-aleatoria
Content-Type: application/json
```

**Response:**
```json
{
  "reply": "Olá! Como posso ajudar?"
}
```

### Gateway WhatsApp

#### POST /send-text
Envia mensagem manualmente (útil para testes).

#### GET /health
Verifica status do gateway e conexão WhatsApp.

## Testes

### Testar Backend Python

```bash
# Usando curl
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test123", "message": "Olá!"}'
```

### Testar Integração Completa

1. Envie uma mensagem de texto para o número do WhatsApp conectado
2. Verifique os logs do gateway e do backend
3. Confirme que a resposta foi recebida no WhatsApp

### Testar Gateway Manualmente

```bash
# Enviar mensagem via gateway
curl -X POST http://localhost:3000/send-text \
  -H "Content-Type: application/json" \
  -d '{"number": "5541999380969", "text": "Teste"}'
```

## Troubleshooting

### Gateway não conecta ao WhatsApp
- Verifique se escaneou o QR Code corretamente
- Verifique a pasta `auth_info/` (pode estar corrompida, delete e escaneie novamente)

### Gateway não recebe resposta do backend
- Verifique se o backend está rodando em `http://localhost:8000`
- Verifique os logs do gateway para erros HTTP
- Verifique se `BOT_API_KEY` é igual em ambos os serviços
- Teste o endpoint `/whatsapp` diretamente com curl

### Erro 401 (Unauthorized)
- Certifique-se de que `BOT_API_KEY` é igual no backend e no gateway
- Verifique se o header `X-API-KEY` está sendo enviado

### Mensagens não são processadas
- Verifique os logs do backend Python
- Verifique se a mensagem não está vindo de grupo/broadcast
- Verifique se a mensagem tem texto (não é mídia)

## Segurança

- **Nunca** commite arquivos `.env` no Git
- Use chaves `BOT_API_KEY` fortes e aleatórias
- Em produção, use variáveis de ambiente do sistema ou secrets manager
- Configure firewall para limitar acesso ao backend Python

## Próximos Passos

- [ ] Adicionar suporte a mídias (imagens, áudios)
- [ ] Adicionar retry logic no gateway
- [ ] Adicionar rate limiting
- [ ] Adicionar suporte a grupos
- [ ] Implementar webhook para status de mensagens
