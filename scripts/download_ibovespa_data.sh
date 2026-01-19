#!/bin/bash

################################################################################
# Script: Download Ibovespa Historical Data
# Descrição: Baixa dados históricos dos 50 componentes do Ibovespa
# Autor: Stock-IndiceDev Assistant
# Data: 19/01/2026
################################################################################

set -e  # Exit on error

echo "================================================================================"
echo "DOWNLOAD IBOVESPA HISTORICAL DATA"
echo "================================================================================"
echo ""

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# PASSO 1: Verificar disponibilidade
echo -e "${BLUE}PASSO 1: Verificando disponibilidade dos componentes Ibovespa...${NC}"
docker exec -it b3-data-collector python /app/src/b3_api_integration.py check-ibov

echo ""
read -p "Deseja continuar com o download? (y/n): " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${RED}Download cancelado pelo usuário${NC}"
    exit 0
fi

# PASSO 2: Exportar lista para CSV (opcional)
echo ""
echo -e "${BLUE}PASSO 2: Exportando lista de ativos para CSV...${NC}"
docker exec -it b3-data-collector python /app/src/b3_api_integration.py export-csv
echo -e "${GREEN}✓ Lista exportada para b3_tickers_list.csv${NC}"

# PASSO 3: Baixar dados COTAHIST
echo ""
echo -e "${BLUE}PASSO 3: Baixando dados históricos via COTAHIST...${NC}"
echo ""
echo -e "${YELLOW}Escolha o ano:${NC}"
echo "  1) 2024 (mais recente)"
echo "  2) 2023"
echo "  3) 2022"
echo "  4) Todos (2022-2024)"
read -p "Opção (1-4): " year_option

case $year_option in
    1)
        YEARS="2024"
        ;;
    2)
        YEARS="2023"
        ;;
    3)
        YEARS="2022"
        ;;
    4)
        YEARS="2022 2023 2024"
        ;;
    *)
        echo -e "${RED}Opção inválida${NC}"
        exit 1
        ;;
esac

# Lista dos 50 componentes Ibovespa
IBOVESPA_TICKERS=(
    PETR4 VALE3 ITUB4 BBDC4 ABEV3
    B3SA3 WEGE3 RENT3 SUZB3 RAIL3
    BBAS3 JBSS3 MGLU3 VIVT3 ELET3
    CSNA3 USIM5 GGBR4 EMBR3 RADL3
    HAPV3 RDOR3 KLBN11 EQTL3 CPLE6
    ENBR3 ENGI11 SBSP3 CMIG4 TAEE11
    CSAN3 UGPA3 LREN3 BRDT3 YDUQ3
    CCRO3 BPAC11 TOTS3 PRIO3 BEEF3
    CYRE3 MRFG3 GOLL4 AZUL4 LWSA3
    VBBR3 SANB11 ITSA4 CRFB3 COGN3
)

echo ""
echo -e "${YELLOW}Ativos a serem baixados: ${#IBOVESPA_TICKERS[@]}${NC}"
echo -e "${YELLOW}Anos: $YEARS${NC}"
echo ""

for year in $YEARS; do
    echo -e "${BLUE}Baixando dados de $year...${NC}"
    
    # Baixar COTAHIST do ano
    docker exec -it b3-data-collector python /app/src/import_cotahist.py \
        --year $year \
        --symbols "${IBOVESPA_TICKERS[@]}"
    
    echo -e "${GREEN}✓ Dados de $year importados${NC}"
    echo ""
done

# PASSO 4: Verificar dados no banco
echo ""
echo -e "${BLUE}PASSO 4: Verificando dados importados...${NC}"
docker exec -it b3-timescaledb psql -U b3trading_ts -d b3trading_market -c "
    SELECT 
        COUNT(DISTINCT symbol) as total_ativos,
        COUNT(*) as total_registros,
        MIN(time::date) as data_min,
        MAX(time::date) as data_max
    FROM ohlcv_daily;
"

echo ""
echo -e "${BLUE}Top 10 ativos por número de registros:${NC}"
docker exec -it b3-timescaledb psql -U b3trading_ts -d b3trading_market -c "
    SELECT 
        symbol,
        COUNT(*) as registros,
        MIN(time::date) as data_min,
        MAX(time::date) as data_max
    FROM ohlcv_daily
    GROUP BY symbol
    ORDER BY registros DESC
    LIMIT 10;
"

# PASSO 5: Executar backtests (opcional)
echo ""
echo -e "${YELLOW}Deseja executar backtests agora? (y/n)${NC}"
read -p ": " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo -e "${BLUE}Executando Wave3 backtest em PETR4, VALE3, ITUB4...${NC}"
    docker exec -it b3-execution-engine python /app/src/backtest.py \
        --strategy wave3 \
        --symbols PETR4 VALE3 ITUB4 \
        --start-date 2023-01-01 \
        --end-date 2024-12-31
    
    echo -e "${GREEN}✓ Backtest completo${NC}"
fi

# Finalização
echo ""
echo "================================================================================"
echo -e "${GREEN}✅ DOWNLOAD COMPLETO!${NC}"
echo "================================================================================"
echo ""
echo "📊 Próximos passos:"
echo "  1. Visualizar dados no Grafana: http://localhost:3001"
echo "  2. Executar backtests: make backtest"
echo "  3. Testar API ML: curl http://localhost:3000/api/ml/health"
echo "  4. Paper trading: curl http://localhost:3000/api/paper/status"
echo ""
echo "📁 Documentação:"
echo "  - B3 API: docs/B3_API_INTEGRATION.md"
echo "  - INSTRUCOES: INSTRUCOES.md"
echo ""
