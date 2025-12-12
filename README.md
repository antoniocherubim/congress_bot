# Event Bot - Chatbot para Congresso

MVP de um chatbot para congresso na área do agro, com arquitetura preparada para evoluir para sistema de matchmaking.

## Estrutura do Projeto

```
congress_bot/
  app/
    config.py              # Configurações centralizadas
    core/
      models.py            # Tipos básicos (Message, Role, ChatTurn)
      session_manager.py   # Gerenciamento de sessões (InMemory)
      engine.py            # ChatbotEngine (núcleo lógico)
    session/
      redis_session_manager.py  # Gerenciamento de sessões (Redis)
    infra/
      openai_client.py     # Cliente para a OpenAI
    api/
      http.py              # FastAPI app, rotas /chat, /whatsapp, /health
    storage/
      models.py            # Modelos SQLAlchemy (Participant)
      database.py          # Configuração do banco de dados
  whatsapp-gateway/        # Gateway WhatsApp (Node.js)
    index.js               # Gateway principal
    worker/                # Worker de processamento
    queue/                 # Fila BullMQ
  alembic/                 # Migrações de banco de dados
  docker-compose.yml       # Orquestração de todos os serviços
  main.py                  # Ponto de entrada para rodar o servidor
```

## Arquitetura Docker Compose

O projeto usa um único `docker-compose.yml` que gerencia todos os serviços:

| Serviço | Descrição | Porta | Dependências |
|---------|-----------|-------|--------------|
| `postgres` | Banco de dados PostgreSQL | 5432 | - |
| `redis` | Cache e filas (BullMQ) | 6379 | - |
| `api` | Backend Python (FastAPI) | 8000 | postgres, redis |
| `gateway` | Gateway WhatsApp (Node.js) | 3333 | redis, api |
| `worker` | Processador de mensagens | - | redis, api, gateway |

Todos os serviços estão na mesma rede Docker (`congress_bot_network`) e se comunicam pelos nomes dos serviços.

## Instalação

### Opção 1: Docker Compose Unificado (Recomendado para Produção)

O projeto usa um único `docker-compose.yml` que gerencia todos os serviços:
- **PostgreSQL**: Banco de dados
- **Redis**: Cache e filas
- **API**: Backend Python (FastAPI)
- **Gateway**: Gateway WhatsApp (Node.js)
- **Worker**: Processador de mensagens WhatsApp (Node.js)

#### 1. Clone o repositório e configure as variáveis de ambiente:

Crie um arquivo `.env` na raiz do projeto:
```env
# OpenAI
OPENAI_API_KEY=sua-chave-aqui
OPENAI_MODEL=gpt-3o-mini
OPENAI_TIMEOUT_MS=20000
OPENAI_MAX_RETRIES=3
OPENAI_RETRY_BASE_DELAY_MS=400

# Database (PostgreSQL)
DATABASE_URL=postgresql+psycopg://congress_bot:congress_bot_pass@postgres:5432/congress_bot
POSTGRES_USER=congress_bot
POSTGRES_PASSWORD=congress_bot_pass
POSTGRES_DB=congress_bot

# Redis
REDIS_URL=redis://redis:6379/0
SESSION_TTL_SECONDS=604800
SESSION_MAX_STORED_TURNS=30

# Environment
ENV=prod
BOT_API_KEY=uma-chave-secreta-aleatoria

# Email (SMTP)
SMTP_HOST=seu-smtp-host
SMTP_PORT=587
SMTP_USER=seu-usuario
SMTP_PASSWORD=sua-senha
SMTP_FROM=inscricao@biosummit.com.br

# Mock (opcional)
BIOSUMMIT_MOCK_EVENT_DATA=0

# Audio limits
MAX_AUDIO_BASE64_CHARS=12000000
MAX_AUDIO_BYTES=8388608
```

Crie também um arquivo `whatsapp-gateway/.env`:
```env
# Backend API
BOT_URL=http://api:8000
BOT_API_KEY=uma-chave-secreta-aleatoria  # Deve ser igual ao BOT_API_KEY do .env principal

# Redis (usado internamente pelo gateway)
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_DB=0

# Configurações da fila
QUEUE_CONCURRENCY=20
DEDUPE_TTL_SECONDS=21600
LOCK_TTL_SECONDS=60
HTTP_TIMEOUT_MS=20000

# Gateway
PORT=3333
```

#### 2. Inicie todos os serviços:

```bash
# Subir todos os serviços (as migrações são executadas automaticamente)
docker-compose up -d
```

**Nota**: As migrações do banco de dados são executadas automaticamente quando o serviço `api` inicia. Se precisar executar manualmente:

```bash
docker-compose run --rm api alembic upgrade head
```

#### 3. Verifique os logs:

```bash
# Ver logs de todos os serviços
docker-compose logs -f

# Ver logs específicos
docker-compose logs -f api          # Backend Python
docker-compose logs -f gateway      # Gateway WhatsApp (para ver QR code)
docker-compose logs -f worker       # Worker de processamento
```

#### 4. Conectar WhatsApp:

O gateway WhatsApp precisa ser conectado na primeira vez. Verifique os logs do gateway:

```bash
docker-compose logs -f gateway
```

Procure pelo QR code nos logs e escaneie com o WhatsApp. Após conectar, a sessão será salva em `whatsapp-gateway/auth_info/`.

#### 5. Verificar status dos serviços:

```bash
# Ver status de todos os containers
docker-compose ps

# Health check da API
curl http://localhost:8000/health
```

#### Comandos úteis:

```bash
# Parar todos os serviços
docker-compose down

# Parar e remover volumes (cuidado: remove dados)
docker-compose down -v

# Reconstruir imagens
docker-compose up -d --build

# Ver logs em tempo real
docker-compose logs -f

# Reiniciar um serviço específico
docker-compose restart api
docker-compose restart gateway
```

### Opção 2: Instalação Local

1. Instale as dependências:
```bash
pip install -r requirements.txt
```

2. Configure PostgreSQL e Redis localmente:
   - PostgreSQL: Instale e crie um banco de dados
   - Redis: Instale e inicie o servidor

3. Configure as variáveis de ambiente:

Crie um arquivo `.env` na raiz do projeto:
```env
# OpenAI
OPENAI_API_KEY=sua-chave-aqui
OPENAI_MODEL=gpt-3o-mini

# Database (PostgreSQL recomendado, SQLite para dev)
DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/congress_bot
# Para desenvolvimento local com SQLite:
# DATABASE_URL=sqlite:///./biosummit.db

# Redis (opcional, usa InMemory se não configurado)
REDIS_URL=redis://localhost:6379/0
SESSION_TTL_SECONDS=604800

# Environment
ENV=dev
BOT_API_KEY=uma-chave-secreta-aleatoria

# Email (SMTP)
SMTP_HOST=dev-log
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM=inscricao@biosummit.com.br
```

4. Execute as migrações do banco de dados:
```bash
alembic upgrade head
```

5. Execute a aplicação:
```bash
python main.py
```

O servidor estará disponível em `http://localhost:8000`

## Migrações de Banco de Dados

O projeto usa Alembic para gerenciar migrações do banco de dados.

### Criar nova migração:
```bash
alembic revision --autogenerate -m "descrição da migração"
```

### Aplicar migrações:
```bash
alembic upgrade head
```

### Reverter última migração:
```bash
alembic downgrade -1
```

### Ver histórico de migrações:
```bash
alembic history
```

## API

### GET /health

Endpoint de health check para monitoramento e Docker healthchecks.

**Response:**
```json
{
  "status": "healthy",
  "redis": "ok",
  "database": "ok"
}
```

### POST /chat

Endpoint principal para enviar mensagens ao chatbot (testes HTTP diretos).

**Request:**
```json
{
  "user_id": "user123",
  "message": "Qual é a programação do evento?"
}
```

**Response:**
```json
{
  "user_id": "user123",
  "reply": "A programação completa está disponível...",
  "turns": 1
}
```

### POST /whatsapp

Endpoint para integração com gateway WhatsApp.

**Request:**
```json
{
  "number": "5541999999999",
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

### POST /transcribe-audio

Endpoint para transcrever áudio usando OpenAI Whisper.

**Request:**
```json
{
  "audio_base64": "base64-encoded-audio-data"
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
  "text": "Texto transcrito do áudio"
}
```

## Integração WhatsApp

O projeto inclui um gateway WhatsApp em Node.js integrado ao docker-compose unificado.

### Estrutura

- **Gateway** (`whatsapp-gateway/`): Recebe mensagens do WhatsApp e enfileira para processamento
- **Worker** (`whatsapp-gateway/worker/`): Processa mensagens da fila com controle de concorrência e idempotência
- **Backend API**: Recebe requisições do worker e retorna respostas

### Configuração

1. Configure o `.env` do gateway (veja seção de instalação acima)
2. Certifique-se de que `BOT_API_KEY` é igual no `.env` principal e no `whatsapp-gateway/.env`
3. O `BOT_URL` no gateway deve apontar para `http://api:8000` (nome do serviço no docker-compose)

### Conectar WhatsApp

1. Inicie os serviços: `docker-compose up -d`
2. Verifique os logs do gateway: `docker-compose logs -f gateway`
3. Escaneie o QR code que aparece nos logs
4. Após conectar, a sessão será salva automaticamente

### Documentação Detalhada

Veja o arquivo [whatsapp-gateway/README.md](whatsapp-gateway/README.md) para documentação completa do gateway, incluindo:
- Arquitetura do sistema de filas
- Configurações avançadas
- Troubleshooting

## Documentação Interativa

Com o servidor rodando, acesse:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Configurações Avançadas

### Sessões Redis

O projeto suporta armazenamento de sessões em Redis para produção. Se `REDIS_URL` não estiver configurado, o sistema usa armazenamento em memória (apenas para desenvolvimento).

**Configuração:**
```env
REDIS_URL=redis://localhost:6379/0
SESSION_TTL_SECONDS=604800  # 7 dias
```

### Banco de Dados

**PostgreSQL (Recomendado para Produção):**
```env
DATABASE_URL=postgresql+psycopg://user:pass@host:5432/dbname
```

**SQLite (Apenas para Desenvolvimento):**
```env
DATABASE_URL=sqlite:///./biosummit.db
```

### Variáveis de Ambiente Completas

Veja o arquivo `ENV_VARIABLES.md` para documentação completa de todas as variáveis de ambiente disponíveis.

## Troubleshooting

### Erro ao iniciar containers

**Porta já em uso:**
```bash
# Verificar o que está usando a porta
sudo netstat -tulpn | grep 5432  # PostgreSQL
sudo netstat -tulpn | grep 6379  # Redis
sudo netstat -tulpn | grep 8000  # API
sudo netstat -tulpn | grep 3333  # Gateway

# Parar serviços conflitantes ou mudar portas no docker-compose.yml
```

**Container não inicia:**
```bash
# Ver logs do container
docker-compose logs nome_do_servico

# Verificar status
docker-compose ps
```

### Erro ao conectar ao PostgreSQL
- Verifique se o container `postgres` está rodando: `docker-compose ps`
- Confirme as credenciais em `DATABASE_URL` e variáveis de ambiente
- Verifique os logs: `docker-compose logs postgres`

### Erro ao conectar ao Redis
- Verifique se o container `redis` está rodando: `docker-compose ps`
- Confirme a URL em `REDIS_URL` (deve ser `redis://redis:6379/0` dentro do Docker)
- Verifique os logs: `docker-compose logs redis`

### Gateway não conecta ao WhatsApp
- Verifique os logs: `docker-compose logs -f gateway`
- Procure por erros de conexão ou QR code
- Verifique se o diretório `whatsapp-gateway/auth_info/` tem permissões corretas
- Se necessário, remova `auth_info/` e reconecte: `rm -rf whatsapp-gateway/auth_info/*`

### Worker não processa mensagens
- Verifique os logs: `docker-compose logs -f worker`
- Confirme que o Redis está acessível
- Verifique se `BOT_URL` está correto no `.env` do gateway

### Migrações não aplicam
- As migrações são executadas automaticamente ao iniciar o serviço `api`
- Se necessário, execute manualmente: `docker-compose run --rm api alembic upgrade head`
- Verifique se `DATABASE_URL` está correta
- Execute `docker-compose run --rm api alembic current` para ver a versão atual

## Próximos Passos

- [x] Persistência de sessões (Postgres/Redis) ✅
- [ ] Integração com ACE
- [x] Logging estruturado ✅
- [ ] Métricas e observabilidade
- [ ] Testes automatizados

