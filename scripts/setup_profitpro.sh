#!/bin/bash
# ============================================
# ProfitPro Integration Helper
# ============================================
# Este script ajuda a localizar e configurar o ProfitPro

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║     PROFITPRO INTEGRATION - LOCALIZAÇÃO E SETUP              ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Procurar instalação do ProfitPro
echo "🔍 Procurando instalação do ProfitPro..."
echo ""

PROFITPRO_PATH=""

# Caminhos típicos do Wine
SEARCH_PATHS=(
    "$HOME/.wine/drive_c/Program Files/Nelogica/ProfitPro"
    "$HOME/.wine/drive_c/Program Files (x86)/Nelogica/ProfitPro"
    "$HOME/.wine/drive_c/Nelogica/ProfitPro"
    "/opt/wine/drive_c/Program Files/Nelogica/ProfitPro"
)

for path in "${SEARCH_PATHS[@]}"; do
    if [ -d "$path" ]; then
        echo "✅ Encontrado: $path"
        
        # Verificar se tem executável ou pasta de dados
        if [ -f "$path/ProfitPro.exe" ] || [ -d "$path/Dados" ]; then
            PROFITPRO_PATH="$path"
            echo "   ✓ Instalação válida"
            break
        fi
    fi
done

echo ""

if [ -z "$PROFITPRO_PATH" ]; then
    echo "❌ ProfitPro não encontrado automaticamente"
    echo ""
    echo "Por favor, informe o caminho manualmente:"
    read -p "Caminho do ProfitPro: " PROFITPRO_PATH
    
    if [ ! -d "$PROFITPRO_PATH" ]; then
        echo "❌ Diretório não existe: $PROFITPRO_PATH"
        exit 1
    fi
fi

echo "════════════════════════════════════════════════════════════════"
echo "📊 PROFITPRO ENCONTRADO"
echo "════════════════════════════════════════════════════════════════"
echo "Instalação: $PROFITPRO_PATH"
echo ""

# Verificar pasta de dados
DADOS_PATH="$PROFITPRO_PATH/Dados"

if [ -d "$DADOS_PATH" ]; then
    echo "✅ Pasta de dados: $DADOS_PATH"
    
    # Contar arquivos
    NUM_FILES=$(find "$DADOS_PATH" -type f 2>/dev/null | wc -l)
    echo "   Arquivos encontrados: $NUM_FILES"
    
    # Listar alguns arquivos
    echo ""
    echo "📂 Estrutura de dados:"
    ls -lh "$DADOS_PATH" | head -20
else
    echo "⚠️ Pasta de dados não encontrada"
    echo "   Esperado em: $DADOS_PATH"
fi

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "📝 PRÓXIMOS PASSOS"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "1. CRIAR DIRETÓRIO DE EXPORTAÇÃO:"
echo "   mkdir -p /tmp/profitpro_export"
echo ""
echo "2. ABRIR PROFITPRO:"
echo "   cd '$PROFITPRO_PATH'"
echo "   wine ProfitPro.exe"
echo ""
echo "3. EXPORTAR DADOS (dentro do ProfitPro):"
echo "   a) Criar gráfico do ativo desejado (ex: PETR4)"
echo "   b) Configurar periodicidade (60 min, 1 dia, etc.)"
echo "   c) Clique direito → 'Exportar Dados' → 'CSV'"
echo "   d) Salvar em: /tmp/profitpro_export/SIMBOLO_60min.csv"
echo ""
echo "4. VERIFICAR FORMATO DO CSV:"
echo "   head /tmp/profitpro_export/PETR4_60min.csv"
echo ""
echo "   Formato esperado:"
echo "   Data;Hora;Abertura;Máxima;Mínima;Fechamento;Volume"
echo "   20/01/2026;09:00;30.50;30.80;30.40;30.75;1000000"
echo ""
echo "5. IMPORTAR PARA TIMESCALEDB:"
echo "   docker exec b3-data-collector python /app/src/profitpro_integration.py import \\"
echo "       /tmp/profitpro_export/PETR4_60min.csv"
echo ""
echo "   OU importar lote:"
echo "   docker exec b3-data-collector python /app/src/profitpro_integration.py import-batch \\"
echo "       /tmp/profitpro_export --interval 60min"
echo ""
echo "════════════════════════════════════════════════════════════════"
echo ""

# Gerar arquivo de configuração
CONFIG_FILE="/tmp/profitpro_config.txt"
echo "PROFITPRO_PATH=$PROFITPRO_PATH" > "$CONFIG_FILE"
echo "DADOS_PATH=$DADOS_PATH" >> "$CONFIG_FILE"

echo "💾 Configuração salva em: $CONFIG_FILE"
echo ""

# Perguntar se quer abrir o ProfitPro agora
echo "════════════════════════════════════════════════════════════════"
read -p "Deseja abrir o ProfitPro agora? (s/n): " OPEN_NOW

if [ "$OPEN_NOW" == "s" ] || [ "$OPEN_NOW" == "S" ]; then
    echo ""
    echo "🚀 Abrindo ProfitPro..."
    cd "$PROFITPRO_PATH"
    wine ProfitPro.exe &
    
    echo ""
    echo "✅ ProfitPro aberto em background"
    echo "   Siga as instruções acima para exportar dados"
fi

echo ""
echo "════════════════════════════════════════════════════════════════"
