#!/bin/bash
# Script para limpar tudo e subir containers do zero

set -e

echo "🧹 Limpando containers, volumes e imagens..."

# Parar e remover todos os containers
echo "1️⃣ Parando e removendo containers..."
sudo docker-compose down -v --remove-orphans

# Remover imagens do projeto (opcional, mas garante rebuild completo)
echo "2️⃣ Removendo imagens antigas do projeto..."
sudo docker images | grep -E "(congress_bot|biosummit|whatsapp-gateway)" | awk '{print $3}' | xargs -r sudo docker rmi -f || true

# Limpar cache de build do Docker (opcional)
echo "3️⃣ Limpando cache de build..."
sudo docker builder prune -f

# Remover volumes órfãos (cuidado: isso remove dados!)
echo "4️⃣ Removendo volumes órfãos..."
sudo docker volume prune -f

echo ""
echo "✅ Limpeza concluída!"
echo ""
echo "🔨 Reconstruindo e subindo containers (sem cache)..."
echo ""

# Reconstruir sem cache e subir
sudo docker-compose build --no-cache
sudo docker-compose up -d

echo ""
echo "✅ Containers subindo!"
echo ""
echo "📊 Verificando status..."
sudo docker-compose ps

echo ""
echo "📝 Para ver os logs:"
echo "   sudo docker-compose logs -f gateway"
echo "   sudo docker-compose logs -f worker"
echo "   sudo docker-compose logs -f api"

