#!/bin/bash

# Script para limpar a autenticação do WhatsApp e forçar novo login

echo "🗑️  Removendo pasta auth_info..."
rm -rf ./auth_info
echo "✅ Pasta auth_info removida com sucesso!"
echo ""
echo "Agora você pode reiniciar o gateway e escanear um novo QR Code."

