# Gateway WhatsApp - BioSummit 2026 (Produção)

Gateway em Node.js que conecta o WhatsApp ao backend Python usando @whiskeysockets/baileys, com processamento assíncrono via Redis e BullMQ.

## Arquitetura

O sistema é composto por três componentes principais:

1. **Gateway** (`index.js`): Recebe mensagens do WhatsApp e enfileira para processamento
2. **Worker** (`worker/messageWorker.js`): Processa mensagens da fila com controle de concorrência e idempotência
3. **Redis**: Backend para fila (BullMQ) e cache de locks/deduplicação

### Características

- ✅ **Ordenação por conversa**: Garante que mensagens de uma mesma conversa sejam processadas em ordem
- ✅ **Idempotência**: Evita processar a mesma mensagem duas vezes (deduplicação por messageId)
- ✅ **Controle de concorrência**: 20 jobs globais, mas apenas 1 por conversa simultaneamente
- ✅ **Timeouts**: Todas as chamadas HTTP têm timeout configurável
- ✅ **Retry automático**: BullMQ retenta jobs falhos com backoff exponencial
- ✅ **Suporte a @lid**: /send-text funciona com contatos iniciados por link

## Pré-requisitos

- Node.js 20+ (para fetch nativo)
- Redis 6+
- Backend Python rodando

## Instalação e Execução

### Opção 1: Docker Compose Unificado (Recomendado)

O gateway está integrado ao `docker-compose.yml` principal do projeto. Veja o [README.md](../README.md) principal para instruções completas.

**Resumo:**
1. Configure o `.env` na raiz do projeto
2. Configure o `whatsapp-gateway/.env` (veja variáveis abaixo)
3. Execute: `docker-compose up -d`
4. Verifique logs: `docker-compose logs -f gateway`

### Opção 2: Execução Local (Desenvolvimento)

1. Instale as dependências:
```bash
npm install
```

2. Configure as variáveis de ambiente:

Copie `.env.example` para `.env` e ajuste:

```bash
cp .env.example .env
```

Edite o `.env` com suas configurações (veja seção "Variáveis de Ambiente" abaixo).

3. Execute:

#### Desenvolvimento (tudo em um processo):
```bash
npm start
```

**Nota**: Em desenvolvimento, o gateway processa mensagens diretamente. Para produção, use gateway + worker separados.

#### Produção (Gateway + Worker separados):

**Terminal 1 - Gateway:**
```bash
npm run start:gateway
```

**Terminal 2 - Worker:**
```bash
npm run start:worker
```

## Variáveis de Ambiente

| Variável | Descrição | Padrão | Docker Compose |
|----------|-----------|--------|----------------|
| `BOT_URL` | URL do backend Python | `http://localhost:8000` | `http://api:8000` |
| `BOT_API_KEY` | Chave de autenticação (deve ser igual no backend) | - | Obrigatório |
| `PORT` | Porta do gateway HTTP | `3333` | 3333 (interno) |
| `REDIS_HOST` | Host do Redis | `localhost` | `redis` |
| `REDIS_PORT` | Porta do Redis | `6379` | `6379` |
| `REDIS_PASSWORD` | Senha do Redis (opcional) | - | - |
| `REDIS_DB` | Database do Redis | `0` | `0` |
| `QUEUE_CONCURRENCY` | Número máximo de jobs processados simultaneamente | `20` | `20` |
| `DEDUPE_TTL_SECONDS` | TTL para deduplicação (6h padrão) | `21600` | `21600` |
| `LOCK_TTL_SECONDS` | TTL do lock por conversa | `60` | `60` |
| `HTTP_TIMEOUT_MS` | Timeout para chamadas HTTP | `20000` | `20000` |
| `DEBUG_MESSAGES` | Log detalhado de mensagens (true/false) | `false` | `false` |

**Nota para Docker Compose**: No ambiente Docker, use `BOT_URL=http://api:8000` e `REDIS_HOST=redis` (nomes dos serviços no docker-compose).

## Como Funciona

### Fluxo de Mensagem

1. **Gateway recebe mensagem** do WhatsApp via Baileys
2. **Filtros aplicados**: Ignora mensagens próprias, grupos, broadcasts
3. **Enfileiramento**: Mensagem é adicionada à fila BullMQ com `messageId` como jobId (idempotência)
4. **Worker processa**:
   - Verifica deduplicação (Redis SET NX)
   - Adquire lock da conversa (1 por remoteJid)
   - Extrai texto (suporta texto, áudio, imagem com caption)
   - Chama backend Python com timeout
   - Envia resposta via Baileys
   - Libera lock

### Garantias

- **Ordenação**: Lock por conversa garante processamento sequencial
- **Idempotência**: messageId como jobId + Redis SET NX evita duplicatas
- **Resiliência**: Jobs falhos são retentados automaticamente (3 tentativas, backoff exponencial)
- **Sem perda**: Se backend estiver offline, jobs ficam na fila e são processados quando voltar

## Endpoints

### POST /send-text

Envia mensagem manualmente. Suporta contatos @lid (busca último JID conhecido no Redis).

**Headers:**
```
X-API-KEY: sua-chave-secreta (se BOT_API_KEY estiver configurada)
```

**Request:**
```json
{
  "number": "5541999380969",
  "text": "Olá!"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Mensagem enviada com sucesso",
  "number": "5541999380969",
  "jid": "5541999380969@s.whatsapp.net"
}
```

### GET /health

Verifica status do gateway.

**Response:**
```json
{
  "status": "ok",
  "whatsapp_connected": true,
  "timestamp": "2026-01-15T10:30:00.000Z"
}
```

## Docker Compose

Exemplo de `docker-compose.yml`:

```yaml
version: '3.8'

services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data
    command: redis-server --appendonly yes

  gateway:
    build: .
    command: npm run start:gateway
    env_file:
      - .env
    volumes:
      - ./auth_info:/app/auth_info
      - ../logs:/app/logs
    depends_on:
      - redis
    restart: unless-stopped

  worker:
    build: .
    command: npm run start:worker
    env_file:
      - .env
    volumes:
      - ./auth_info:/app/auth_info
      - ../logs:/app/logs
    depends_on:
      - redis
      - gateway
    restart: unless-stopped

volumes:
  redis-data:
```

## Estrutura de Arquivos

```
whatsapp-gateway/
├── index.js                 # Gateway (recebe mensagens, enfileira)
├── worker/
│   └── messageWorker.js    # Worker (processa mensagens da fila)
├── queue/
│   ├── redis.js            # Configuração Redis
│   └── messageQueue.js     # Fila BullMQ
├── utils/
│   └── http.js             # Utilitários HTTP com timeout
├── package.json
├── .env                     # Variáveis de ambiente (não versionado)
└── auth_info/              # Autenticação Baileys (não versionado)
```

## Troubleshooting

### Erro 401 (Sessão Expirada)

1. Pare gateway e worker
2. Delete `auth_info/`
3. Reinicie e escaneie novo QR Code

### Mensagens não são processadas

- Verifique se Redis está rodando: `redis-cli ping`
- Verifique se worker está rodando: `npm run start:worker`
- Verifique logs em `../logs/gateway.log` e `../logs/app.log`

### Jobs ficam travados

- Verifique locks no Redis: `redis-cli KEYS "lock:jid:*"`
- Se necessário, delete locks manualmente: `redis-cli DEL lock:jid:SEU_JID`

### Backend offline

- Jobs ficam na fila e são processados quando backend voltar
- BullMQ retenta automaticamente (3 tentativas com backoff)

## Notas

- O gateway só processa mensagens de conversas individuais (não grupos)
- Mensagens enviadas pelo próprio bot são ignoradas
- O gateway reconecta automaticamente se a conexão cair (exceto erros 401)
- Conversas iniciadas por link direto (`@lid`) são suportadas e mapeadas no Redis
