# Event Bot - Chatbot para Congresso

MVP de um chatbot para congresso na área do agro, com arquitetura preparada para evoluir para sistema de matchmaking.

## Estrutura do Projeto

```
event_bot/
  app/
    config.py              # Configurações centralizadas
    core/
      models.py            # Tipos básicos (Message, Role, ChatTurn)
      session_manager.py   # Gerenciamento de sessões (em memória)
      engine.py            # ChatbotEngine (núcleo lógico)
    infra/
      openai_client.py     # Cliente para a OpenAI
    api/
      http.py              # FastAPI app, rota /chat
  main.py                  # Ponto de entrada para rodar o servidor
```

## Instalação

1. Instale as dependências:
```bash
pip install -r requirements.txt
```

2. Configure as variáveis de ambiente:

Crie um arquivo `.env` na raiz do projeto (não versionado) com:
```
OPENAI_API_KEY=sua-chave-aqui
OPENAI_MODEL=gpt-4o-mini  # opcional, padrão é gpt-3o-mini
BOT_API_KEY=uma-chave-secreta-aleatoria  # para autenticação com gateway WhatsApp
DATABASE_URL=sqlite:///./biosummit.db
SMTP_HOST=dev-log
SMTP_PORT=587
SMTP_USER=seu-usuario-smtp
SMTP_PASSWORD=sua-senha-smtp
SMTP_FROM=inscricao@biosummit.com.br
```

O sistema carrega automaticamente as variáveis do arquivo `.env`. 
Alternativamente, você pode definir as variáveis diretamente no ambiente do sistema:
```bash
# Linux/Mac
export OPENAI_API_KEY="sua-chave-aqui"

# Windows PowerShell
$env:OPENAI_API_KEY="sua-chave-aqui"
```

## Execução

```bash
python main.py
```

O servidor estará disponível em `http://localhost:8000`

## API

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

## Próximos Passos

- [ ] Persistência de sessões (Postgres/Redis)
- [ ] Integração com ACE
- [ ] Logging estruturado
- [ ] Métricas e observabilidade
- [ ] Testes automatizados

