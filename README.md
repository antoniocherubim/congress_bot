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
  alembic/                 # Migrações de banco de dados
  main.py                  # Ponto de entrada para rodar o servidor
```

## Instalação

### Opção 1: Docker Compose (Recomendado para Produção)

1. Clone o repositório e configure as variáveis de ambiente:

Crie um arquivo `.env` na raiz do projeto:
```env
# OpenAI
OPENAI_API_KEY=sua-chave-aqui
OPENAI_MODEL=gpt-3o-mini

# Database (PostgreSQL)
DATABASE_URL=postgresql+psycopg://congress_bot:congress_bot_pass@postgres:5432/congress_bot
POSTGRES_USER=congress_bot
POSTGRES_PASSWORD=congress_bot_pass
POSTGRES_DB=congress_bot

# Redis
REDIS_URL=redis://redis:6379/0
SESSION_TTL_SECONDS=604800

# Environment
ENV=prod
BOT_API_KEY=uma-chave-secreta-aleatoria

# Email (SMTP)
SMTP_HOST=seu-smtp-host
SMTP_PORT=587
SMTP_USER=seu-usuario
SMTP_PASSWORD=sua-senha
SMTP_FROM=inscricao@biosummit.com.br
```

2. Execute as migrações do banco de dados:
```bash
docker-compose up -d postgres redis
# Aguardar alguns segundos para os serviços iniciarem
docker-compose run --rm api alembic upgrade head
```

3. Inicie todos os serviços:
```bash
docker-compose up -d
```

4. Verifique os logs:
```bash
docker-compose logs -f api
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

O projeto inclui um gateway WhatsApp em Node.js. Veja o arquivo [INTEGRATION.md](INTEGRATION.md) para instruções completas de integração.

Resumo:
1. Backend Python já está pronto para receber mensagens do gateway
2. Gateway WhatsApp está em `whatsapp-gateway/`
3. Configure a mesma `BOT_API_KEY` em ambos os serviços

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

### Erro ao conectar ao PostgreSQL
- Verifique se o PostgreSQL está rodando
- Confirme as credenciais em `DATABASE_URL`
- Verifique se o banco de dados foi criado

### Erro ao conectar ao Redis
- Verifique se o Redis está rodando
- Confirme a URL em `REDIS_URL`
- Se não configurar Redis, o sistema usa armazenamento em memória

### Migrações não aplicam
- Verifique se `DATABASE_URL` está correta
- Execute `alembic current` para ver a versão atual
- Execute `alembic history` para ver todas as migrações

## Próximos Passos

- [x] Persistência de sessões (Postgres/Redis) ✅
- [ ] Integração com ACE
- [x] Logging estruturado ✅
- [ ] Métricas e observabilidade
- [ ] Testes automatizados

