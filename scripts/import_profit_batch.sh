#!/bin/bash

# ============================================================================
# Script de Importação em Lote - Dados do ProfitChart
# ============================================================================
# Descrição: Importa múltiplos arquivos CSV exportados do ProfitChart para
#            as tabelas do TimescaleDB
# Uso: ./scripts/import_profit_batch.sh [PASTA_CSV] [INTERVALO]
# Exemplo: ./scripts/import_profit_batch.sh /tmp/profitpro_export daily
# ============================================================================

set -e

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configurações padrão
CSV_DIR="${1:-/tmp/profitpro_export}"
INTERVAL="${2:-daily}"
CONTAINER="b3-data-collector"
SCRIPT_PATH="/app/src/profitpro_integration.py"

# Mapeamento de intervalos para tabelas
declare -A INTERVAL_TO_TABLE=(
    ["daily"]="ohlcv_daily"
    ["60m"]="ohlcv_60m"
    ["60min"]="ohlcv_60m"
    ["15m"]="ohlcv_15m"
    ["15min"]="ohlcv_15m"
    ["5m"]="ohlcv_5m"
    ["5min"]="ohlcv_5m"
    ["1m"]="ohlcv_1m"
    ["1min"]="ohlcv_1m"
)

# Banner
echo -e "${BLUE}"
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║         Importação em Lote - ProfitChart → TimescaleDB         ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Validações
echo -e "${YELLOW}[1/5] Validando configurações...${NC}"

if [ ! -d "$CSV_DIR" ]; then
    echo -e "${RED}✗ Pasta não encontrada: $CSV_DIR${NC}"
    echo ""
    echo "Crie a pasta e coloque os CSVs exportados do ProfitChart:"
    echo "  mkdir -p /tmp/profitpro_export"
    exit 1
fi

if [ -z "${INTERVAL_TO_TABLE[$INTERVAL]}" ]; then
    echo -e "${RED}✗ Intervalo inválido: $INTERVAL${NC}"
    echo ""
    echo "Intervalos válidos:"
    echo "  - daily (ohlcv_daily)"
    echo "  - 60m, 60min (ohlcv_60m)"
    echo "  - 15m, 15min (ohlcv_15m)"
    echo "  - 5m, 5min (ohlcv_5m)"
    echo "  - 1m, 1min (ohlcv_1m)"
    exit 1
fi

TABLE="${INTERVAL_TO_TABLE[$INTERVAL]}"

# Verificar container
if ! docker ps | grep -q "$CONTAINER"; then
    echo -e "${RED}✗ Container '$CONTAINER' não está rodando${NC}"
    echo ""
    echo "Inicie o container:"
    echo "  docker compose up -d data-collector"
    exit 1
fi

echo -e "${GREEN}✓ Configurações válidas${NC}"
echo "  Pasta CSV: $CSV_DIR"
echo "  Intervalo: $INTERVAL"
echo "  Tabela: $TABLE"
echo "  Container: $CONTAINER"
echo ""

# Listar arquivos CSV
echo -e "${YELLOW}[2/5] Localizando arquivos CSV...${NC}"

# Padrões de busca por intervalo
case "$INTERVAL" in
    "daily")
        PATTERN="*_daily_*.csv"
        ;;
    "60m"|"60min")
        PATTERN="*_60m*.csv"
        ;;
    "15m"|"15min")
        PATTERN="*_15m*.csv"
        ;;
    "5m"|"5min")
        PATTERN="*_5m*.csv"
        ;;
    "1m"|"1min")
        PATTERN="*_1m*.csv"
        ;;
    *)
        PATTERN="*.csv"
        ;;
esac

# Encontrar arquivos
mapfile -t CSV_FILES < <(find "$CSV_DIR" -name "$PATTERN" -type f)

if [ ${#CSV_FILES[@]} -eq 0 ]; then
    echo -e "${RED}✗ Nenhum arquivo CSV encontrado${NC}"
    echo ""
    echo "Padrão de busca: $PATTERN"
    echo "Pasta: $CSV_DIR"
    echo ""
    echo "Certifique-se de ter exportado os CSVs do ProfitChart com o padrão:"
    echo "  SIMBOLO_${INTERVAL}_ANOINICIO_ANOFIM.csv"
    echo "  Exemplo: PETR4_daily_2014_2024.csv"
    exit 1
fi

echo -e "${GREEN}✓ Encontrados ${#CSV_FILES[@]} arquivos CSV${NC}"
echo ""

# Listar arquivos encontrados
echo "Arquivos a serem importados:"
for csv_file in "${CSV_FILES[@]}"; do
    filename=$(basename "$csv_file")
    filesize=$(du -h "$csv_file" | cut -f1)
    echo "  - $filename ($filesize)"
done
echo ""

# Confirmação
echo -e "${YELLOW}[3/5] Confirmar importação?${NC}"
read -p "Importar ${#CSV_FILES[@]} arquivos para $TABLE? (s/N): " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Ss]$ ]]; then
    echo -e "${RED}✗ Importação cancelada pelo usuário${NC}"
    exit 0
fi

# Importar arquivos
echo -e "${YELLOW}[4/5] Importando arquivos...${NC}"
echo ""

SUCCESS_COUNT=0
ERROR_COUNT=0
TOTAL_ROWS=0

for csv_file in "${CSV_FILES[@]}"; do
    filename=$(basename "$csv_file")
    echo -ne "${BLUE}Importando: $filename...${NC}"
    
    # Executar importação
    if docker exec "$CONTAINER" python "$SCRIPT_PATH" import \
        "$csv_file" --table "$TABLE" > /tmp/import_log.txt 2>&1; then
        
        # Extrair número de linhas importadas
        ROWS=$(grep -oP '\d+(?= rows inserted)' /tmp/import_log.txt || echo "0")
        TOTAL_ROWS=$((TOTAL_ROWS + ROWS))
        
        echo -e " ${GREEN}✓ OK ($ROWS linhas)${NC}"
        SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
    else
        echo -e " ${RED}✗ ERRO${NC}"
        echo "    Log: /tmp/import_log.txt"
        ERROR_COUNT=$((ERROR_COUNT + 1))
    fi
done

echo ""

# Resumo
echo -e "${YELLOW}[5/5] Resumo da importação${NC}"
echo ""
echo "┌──────────────────────────────────────────┐"
echo "│ Arquivos processados: ${#CSV_FILES[@]}               │"
echo "│ Sucessos: $SUCCESS_COUNT                           │"
echo "│ Erros: $ERROR_COUNT                              │"
echo "│ Total de linhas: $TOTAL_ROWS                 │"
echo "└──────────────────────────────────────────┘"
echo ""

# Validar dados no banco
echo -e "${YELLOW}Validando dados no TimescaleDB...${NC}"

VALIDATION_QUERY="
SELECT 
    symbol,
    COUNT(*) as total_candles,
    MIN(time) as data_inicio,
    MAX(time) as data_fim
FROM $TABLE
WHERE symbol IN (
    SELECT DISTINCT symbol FROM $TABLE ORDER BY symbol LIMIT 10
)
GROUP BY symbol
ORDER BY symbol;
"

docker exec -it b3-timescaledb psql -U b3admin -d b3trading -c "$VALIDATION_QUERY" || true

echo ""

# Status final
if [ $ERROR_COUNT -eq 0 ]; then
    echo -e "${GREEN}✓ Importação concluída com sucesso!${NC}"
    echo ""
    echo "Próximos passos:"
    echo "  1. Verificar dados importados:"
    echo "     docker exec -it b3-timescaledb psql -U b3admin -d b3trading"
    echo "     SELECT * FROM $TABLE WHERE symbol = 'PETR4' ORDER BY time DESC LIMIT 10;"
    echo ""
    echo "  2. Testar backtesting com dados reais:"
    echo "     docker exec b3-data-collector python /app/src/backtest.py \\"
    echo "         --strategy Wave3 --symbol PETR4 --interval $INTERVAL"
    exit 0
else
    echo -e "${RED}✗ Importação concluída com erros${NC}"
    echo ""
    echo "Verifique os logs em: /tmp/import_log.txt"
    exit 1
fi
