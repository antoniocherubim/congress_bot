# Variáveis de Ambiente

Este arquivo documenta todas as variáveis de ambiente necessárias para o projeto.

## Configurações da API OpenAI
- `OPENAI_API_KEY` (obrigatório): Chave da API OpenAI
- `OPENAI_MODEL` (opcional, padrão: `gpt-3o-mini`): Modelo a ser usado

## Configurações do banco de dados
- `DATABASE_URL` (opcional, padrão: `sqlite:///./biosummit.db`): URL de conexão do banco de dados
  - Para PostgreSQL: `postgresql://user:password@localhost:5432/biosummit`

## Configurações de email (SMTP)
- `SMTP_HOST` (opcional, padrão: `dev-log`): Host do servidor SMTP
- `SMTP_PORT` (opcional, padrão: `587`): Porta do servidor SMTP
- `SMTP_USER` (opcional): Usuário SMTP
- `SMTP_PASSWORD` (opcional): Senha SMTP
- `SMTP_FROM` (opcional, padrão: `inscricao@biosummit.com.br`): Email remetente

## Ambiente e Segurança
- `ENV` (opcional, padrão: `dev`): Ambiente de execução (`dev` ou `prod`)
  - Em produção (`ENV=prod`), `BOT_API_KEY` é obrigatória
- `BOT_API_KEY` (obrigatório em produção): Chave de API para proteger endpoints `/whatsapp` e `/transcribe-audio`
  - Em desenvolvimento (`ENV=dev`), pode estar vazia (com warning)
  - Em produção (`ENV=prod`), deve estar definida ou a aplicação não inicia

## Mock de dados do evento
- `BIOSUMMIT_MOCK_EVENT_DATA` (opcional, padrão: `0`): Habilita dados simulados do evento
  - Valores aceitos: `0`, `1`, `true`, `false`, `yes`, `no`, `y`, `n`

## Limites de sessão
- `SESSION_MAX_STORED_TURNS` (opcional, padrão: `30`): Número máximo de turnos armazenados em memória
  - O histórico completo é podado automaticamente para evitar vazamento de memória
  - Este é o limite de armazenamento, não o limite usado no prompt (controlado por `max_history_turns`)

## Configurações de timeout e retry para OpenAI
- `OPENAI_TIMEOUT_MS` (opcional, padrão: `20000`): Timeout em milissegundos para chamadas OpenAI
- `OPENAI_MAX_RETRIES` (opcional, padrão: `3`): Número máximo de tentativas em caso de erro transitório
- `OPENAI_RETRY_BASE_DELAY_MS` (opcional, padrão: `400`): Delay base em milissegundos para retry (backoff exponencial)

## Limites de payload para /transcribe-audio
- `MAX_AUDIO_BASE64_CHARS` (opcional, padrão: `12000000`): Tamanho máximo do base64 em caracteres
- `MAX_AUDIO_BYTES` (opcional, padrão: `8388608`): Tamanho máximo do áudio após decodificar em bytes (8MB)

## Redis (Sessões)
- `REDIS_URL` (opcional): URL de conexão Redis (ex: `redis://localhost:6379/0`)
  - Se não configurado, o sistema usa armazenamento em memória (apenas para desenvolvimento)
  - Em produção, é altamente recomendado usar Redis
- `SESSION_TTL_SECONDS` (opcional, padrão: `604800`): TTL de sessão em segundos (7 dias padrão)

## Exemplo de arquivo .env

```env
# Configurações da API OpenAI
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-3o-mini

# Configurações do banco de dados
DATABASE_URL=sqlite:///./biosummit.db

# Configurações de email (SMTP)
SMTP_HOST=dev-log
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM=inscricao@biosummit.com.br

# Ambiente (dev ou prod)
ENV=dev

# Chave de API para proteger endpoints
BOT_API_KEY=

# Mock de dados do evento
BIOSUMMIT_MOCK_EVENT_DATA=0

# Limite de turnos armazenados
SESSION_MAX_STORED_TURNS=30

# Configurações de timeout e retry
OPENAI_TIMEOUT_MS=20000
OPENAI_MAX_RETRIES=3
OPENAI_RETRY_BASE_DELAY_MS=400

# Limites de payload
MAX_AUDIO_BASE64_CHARS=12000000
MAX_AUDIO_BYTES=8388608
```

