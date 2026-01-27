#!/bin/bash
# ============================================
# Paper Trading Startup Script - Wave3 v2.1
# ============================================
# Inicia paper trading com verificações de segurança
# Data: 27 de Janeiro de 2026

set -e

echo "🚀 Iniciando Paper Trading - Wave3 v2.1"
echo "========================================"

# Cores para output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# ============================================
# 1. VERIFICAR CONTAINERS
# ============================================
echo ""
echo "📊 Verificando containers..."

if ! docker ps | grep -q "b3-timescaledb.*Up"; then
    echo -e "${RED}❌ TimescaleDB não está rodando!${NC}"
    echo "Execute: docker compose up -d timescaledb"
    exit 1
fi

if ! docker ps | grep -q "b3-postgres.*Up"; then
    echo -e "${RED}❌ PostgreSQL não está rodando!${NC}"
    echo "Execute: docker compose up -d postgres"
    exit 1
fi

if ! docker ps | grep -q "b3-execution-engine.*Up"; then
    echo -e "${RED}❌ Execution Engine não está rodando!${NC}"
    echo "Execute: docker compose up -d execution-engine"
    exit 1
fi

echo -e "${GREEN}✅ Containers OK${NC}"

# ============================================
# 2. VERIFICAR SCHEMA PAPER TRADING
# ============================================
echo ""
echo "📝 Verificando schema paper trading..."

TABLE_COUNT=$(docker exec b3-postgres psql -U b3trading_user -d b3trading_db -tAc \
    "SELECT COUNT(*) FROM information_schema.tables WHERE table_name LIKE 'paper_%'")

if [ "$TABLE_COUNT" -lt 3 ]; then
    echo -e "${YELLOW}⚠️  Schema incompleto. Criando...${NC}"
    docker exec -i b3-postgres psql -U b3trading_user -d b3trading_db < infrastructure/postgres/paper_trading_schema.sql
    echo -e "${GREEN}✅ Schema criado${NC}"
else
    echo -e "${GREEN}✅ Schema OK ($TABLE_COUNT tabelas)${NC}"
fi

# ============================================
# 3. VERIFICAR DADOS TIMESCALEDB
# ============================================
echo ""
echo "📊 Verificando dados TimescaleDB..."

DATA_COUNT=$(docker exec b3-timescaledb psql -U b3trading_ts -d b3trading_market -tAc \
    "SELECT COUNT(*) FROM ohlcv_60min WHERE symbol IN ('PETR4', 'VALE3', 'ITUB4')")

if [ "$DATA_COUNT" -lt 1000 ]; then
    echo -e "${RED}❌ Dados insuficientes no TimescaleDB!${NC}"
    echo "Execute: docker exec -it b3-data-collector python /app/src/import_profitchart_data.py"
    exit 1
fi

echo -e "${GREEN}✅ Dados OK ($DATA_COUNT registros)${NC}"

# ============================================
# 4. LIMPAR POSIÇÕES/TRADES ANTERIORES (OPCIONAL)
# ============================================
echo ""
read -p "🗑️  Limpar dados anteriores de paper trading? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Limpando paper_positions, paper_trades, ml_training_data..."
    docker exec b3-postgres psql -U b3trading_user -d b3trading_db -c "TRUNCATE TABLE paper_positions CASCADE"
    docker exec b3-postgres psql -U b3trading_user -d b3trading_db -c "TRUNCATE TABLE paper_trades CASCADE"
    docker exec b3-postgres psql -U b3trading_user -d b3trading_db -c "TRUNCATE TABLE ml_training_data CASCADE"
    docker exec b3-postgres psql -U b3trading_user -d b3trading_db -c "TRUNCATE TABLE paper_capital_history CASCADE"
    echo -e "${GREEN}✅ Dados limpos${NC}"
fi

# ============================================
# 5. SNAPSHOT INICIAL DE CAPITAL
# ============================================
echo ""
echo "💰 Criando snapshot inicial de capital..."
docker exec b3-postgres psql -U b3trading_user -d b3trading_db -c "SELECT take_capital_snapshot()"
echo -e "${GREEN}✅ Snapshot criado${NC}"

# ============================================
# 6. CONFIGURAÇÃO DO PAPER TRADER
# ============================================
echo ""
echo "⚙️  Configurações do Paper Trader:"
echo "  - Capital inicial: R$ 100.000,00"
echo "  - Quality score mínimo: 55"
echo "  - Máximo de posições: 5"
echo "  - Risco por trade: 2%"
echo "  - Símbolos: PETR4, VALE3, ITUB4, BBDC4, ABEV3"
echo "  - Intervalo de scan: 5 minutos (300s)"
echo ""

# ============================================
# 7. VERIFICAR SE JÁ ESTÁ RODANDO
# ============================================
if docker exec b3-execution-engine pgrep -f "paper_trading_wave3" > /dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  Paper trader já está rodando!${NC}"
    echo ""
    read -p "Deseja reiniciar? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Parando processo anterior..."
        docker exec b3-execution-engine pkill -f "paper_trading_wave3" || true
        sleep 2
    else
        echo "Abortando..."
        exit 0
    fi
fi

# ============================================
# 8. INICIAR PAPER TRADER
# ============================================
echo ""
echo "▶️  Iniciando Paper Trader..."

# Criar arquivo Python de execução dentro do container
docker exec b3-execution-engine bash -c 'cat > /tmp/start_paper_trader.py << '\''EOF'\''
import asyncio
import sys
sys.path.append("/app/src")

from paper_trading_wave3 import Wave3PaperTrader

async def main():
    trader = Wave3PaperTrader(
        initial_capital=100000.0,
        quality_score_threshold=55,
        max_positions=5,
        risk_per_trade=0.02
    )
    
    symbols = ["PETR4", "VALE3", "ITUB4", "BBDC4", "ABEV3"]
    
    await trader.start(symbols, scan_interval=300)

if __name__ == "__main__":
    asyncio.run(main())
EOF'

# Iniciar em background
docker exec -d b3-execution-engine python3 /tmp/start_paper_trader.py

# Aguardar 3 segundos para verificar se iniciou
sleep 3

if docker exec b3-execution-engine pgrep -f "paper_trading_wave3" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Paper Trading ATIVO!${NC}"
else
    echo -e "${RED}❌ Falha ao iniciar Paper Trader${NC}"
    echo "Verifique os logs: docker logs b3-execution-engine"
    exit 1
fi

# ============================================
# 9. INFORMAÇÕES ÚTEIS
# ============================================
echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║       PAPER TRADING ATIVO - Wave3 v2.1                    ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "📊 MONITORAMENTO:"
echo "   Logs em tempo real:"
echo "   $ docker logs -f b3-execution-engine | grep -E 'POSIÇÃO|TRADE|STOP|TARGET|STATUS'"
echo ""
echo "   Status atual:"
echo "   $ docker exec b3-postgres psql -U b3trading_user -d b3trading_db -c 'SELECT * FROM paper_trading_summary'"
echo ""
echo "   Posições abertas:"
echo "   $ docker exec b3-postgres psql -U b3trading_user -d b3trading_db -c 'SELECT * FROM paper_positions'"
echo ""
echo "   Progresso ML:"
echo "   $ docker exec b3-postgres psql -U b3trading_user -d b3trading_db -c 'SELECT * FROM ml_collection_progress'"
echo ""
echo "📈 DASHBOARD:"
echo "   Grafana: http://localhost:3001"
echo "   (Criar dashboard com queries acima)"
echo ""
echo "🛑 PARA PARAR:"
echo "   $ docker exec b3-execution-engine pkill -f paper_trading_wave3"
echo ""
echo "📅 PRÓXIMOS PASSOS:"
echo "   1. Monitorar primeiros sinais (pode levar até 1 dia)"
echo "   2. Ajustar quality_score se necessário"
echo "   3. Coletar 25-50 trades (1-2 meses)"
echo "   4. Treinar ML v2.5 beta"
echo ""
echo -e "${GREEN}Sucesso! Paper trading está coletando dados...${NC}"
