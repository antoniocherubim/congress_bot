FROM node:20-alpine

WORKDIR /app

# Copiar arquivos de dependências
COPY package*.json ./

# Instalar dependências
RUN npm ci --only=production

# Copiar código
COPY . .

# Criar diretórios necessários
RUN mkdir -p auth_info logs

# Expor porta (se necessário)
EXPOSE 3333

# Comando padrão (pode ser sobrescrito no docker-compose)
CMD ["npm", "run", "start:gateway"]

