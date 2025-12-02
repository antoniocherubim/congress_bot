# Gateway WhatsApp - BioSummit 2026

Gateway em Node.js que conecta o WhatsApp ao backend Python usando @whiskeysockets/baileys.

## Instalação

1. Instale as dependências:
```bash
npm install
```

2. Configure as variáveis de ambiente:

Crie um arquivo `.env` no diretório `whatsapp-gateway/` com:

```
BOT_URL=http://localhost:8000
BOT_API_KEY=uma-chave-secreta-aleatoria
PORT=3000
```

**Importante**: A `BOT_API_KEY` deve ser a mesma configurada no backend Python.

## Execução

```bash
npm start
```

Ou em modo desenvolvimento (com auto-reload):
```bash
npm run dev
```

## Como Funciona

1. Ao iniciar, o gateway gera um QR Code no terminal
2. Escaneie o QR Code com o WhatsApp que será usado como bot
3. Todas as mensagens de texto recebidas são automaticamente:
   - Enviadas ao backend Python via POST `/whatsapp`
   - A resposta do bot é enviada de volta ao usuário no WhatsApp

## Endpoints

### POST /send-text
Envia uma mensagem manualmente (útil para testes).

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
  "number": "5541999380969"
}
```

### GET /health
Verifica o status do gateway e conexão com WhatsApp.

**Response:**
```json
{
  "status": "ok",
  "whatsapp_connected": true
}
```

## Estrutura de Arquivos

- `index.js` - Código principal do gateway
- `package.json` - Dependências e scripts
- `.env` - Variáveis de ambiente (não versionado)
- `auth_info/` - Dados de autenticação do Baileys (não versionado)

## Troubleshooting

### Erro 401 (Sessão Expirada)

Se você receber um erro `401 Unauthorized` ou `Connection Failure` com código 401, isso significa que a sessão do WhatsApp expirou ou foi invalidada.

**Como resolver:**

1. Pare o gateway (Ctrl+C)
2. Delete a pasta `auth_info`:
   ```bash
   # Linux/Mac:
   rm -rf whatsapp-gateway/auth_info
   
   # Windows:
   rmdir /s whatsapp-gateway\auth_info
   ```
3. Ou use o script auxiliar (Linux/Mac):
   ```bash
   chmod +x reset-auth.sh
   ./reset-auth.sh
   ```
4. Inicie o gateway novamente (`npm start`)
5. Escaneie o novo QR Code que aparecerá

### Outros Problemas

- **Gateway não conecta ao WhatsApp**: Verifique se escaneou o QR Code corretamente
- **Mensagens não são processadas**: Verifique os logs do gateway e do backend Python
- **Erro ao chamar backend**: Verifique se o backend está rodando em `http://localhost:8000`

## Notas

- O gateway só processa mensagens de texto de conversas individuais (não grupos)
- Mensagens enviadas pelo próprio bot são ignoradas
- O gateway reconecta automaticamente se a conexão cair (exceto erros 401)
- Conversas iniciadas por link direto (`@lid`) são suportadas

