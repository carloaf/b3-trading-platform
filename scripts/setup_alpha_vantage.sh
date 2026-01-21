#!/bin/bash
# ============================================
# Alpha Vantage Setup - Obter API Key Grátis
# ============================================

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║       ALPHA VANTAGE - CONFIGURAÇÃO API KEY                   ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "📋 PASSOS PARA OBTER SUA API KEY (GRÁTIS):"
echo ""
echo "1. Acesse: https://www.alphavantage.co/support/#api-key"
echo "2. Preencha o formulário (nome, email, organização)"
echo "3. Copie a API key que aparecerá na tela"
echo "4. Cole abaixo quando solicitado"
echo ""
echo "🎁 Plano Grátis Inclui:"
echo "   - 500 requests/dia"
echo "   - 5 requests/minuto"
echo "   - Dados intraday (1min, 5min, 15min, 30min, 60min)"
echo "   - Cobertura: B3, NYSE, NASDAQ, etc."
echo ""
echo "════════════════════════════════════════════════════════════════"
echo ""

# Verificar se já tem API key configurada
if [ ! -z "$ALPHA_VANTAGE_API_KEY" ]; then
    echo "✅ API key já configurada: ${ALPHA_VANTAGE_API_KEY:0:8}..."
    echo ""
    read -p "Deseja reconfigurar? (s/n): " reconfig
    if [ "$reconfig" != "s" ]; then
        echo "✅ Mantendo configuração atual"
        exit 0
    fi
fi

# Solicitar API key
echo ""
read -p "Cole sua API key aqui: " api_key

if [ -z "$api_key" ]; then
    echo "❌ API key não pode estar vazia"
    exit 1
fi

# Validar formato (letras e números, 16+ caracteres)
if [[ ! "$api_key" =~ ^[A-Z0-9]{10,}$ ]]; then
    echo "⚠️ Formato de API key inválido. Deve conter apenas letras maiúsculas e números."
    echo "   Você copiou corretamente?"
    read -p "Continuar mesmo assim? (s/n): " continue
    if [ "$continue" != "s" ]; then
        exit 1
    fi
fi

# Salvar em .env
ENV_FILE="/home/dellno/worksapace/b3-trading-platform/.env"

if [ -f "$ENV_FILE" ]; then
    # Adicionar ou atualizar
    if grep -q "ALPHA_VANTAGE_API_KEY" "$ENV_FILE"; then
        # Atualizar existente
        sed -i "s/ALPHA_VANTAGE_API_KEY=.*/ALPHA_VANTAGE_API_KEY=$api_key/" "$ENV_FILE"
        echo "✅ API key atualizada em .env"
    else
        # Adicionar nova
        echo "" >> "$ENV_FILE"
        echo "# Alpha Vantage API" >> "$ENV_FILE"
        echo "ALPHA_VANTAGE_API_KEY=$api_key" >> "$ENV_FILE"
        echo "✅ API key adicionada em .env"
    fi
else
    # Criar .env
    cat > "$ENV_FILE" << EOF
# Alpha Vantage API
ALPHA_VANTAGE_API_KEY=$api_key
EOF
    echo "✅ Arquivo .env criado com API key"
fi

# Exportar para sessão atual
export ALPHA_VANTAGE_API_KEY="$api_key"

# Testar API key
echo ""
echo "🧪 Testando API key..."
echo ""

docker exec b3-data-collector python /app/src/alpha_vantage_integration.py test PETR4 "$api_key"

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "✅ Configuração completa!"
echo ""
echo "📝 PRÓXIMOS PASSOS:"
echo ""
echo "1. Testar com um ticker:"
echo "   docker exec b3-data-collector python /app/src/alpha_vantage_integration.py test VALE3 $api_key"
echo ""
echo "2. Baixar múltiplos ativos (60min):"
echo "   docker exec b3-data-collector python /app/src/alpha_vantage_integration.py download PETR4 VALE3 ITUB4 --interval 60min --key $api_key"
echo ""
echo "3. Baixar Ibovespa top 10 (cuidado: 10 ativos × 12s = 2 minutos):"
echo "   docker exec b3-data-collector python /app/src/alpha_vantage_integration.py download PETR4 VALE3 ITUB4 BBDC4 ABEV3 B3SA3 WEGE3 RENT3 SUZB3 RAIL3 --interval 60min --key $api_key"
echo ""
echo "⚠️ LEMBRE-SE:"
echo "   - Rate limit: 5 requests/minuto (12 segundos entre ativos)"
echo "   - Limite diário: 500 requests"
echo "   - Para baixar 50 ativos Ibovespa: ~10 minutos"
echo ""
echo "════════════════════════════════════════════════════════════════"
