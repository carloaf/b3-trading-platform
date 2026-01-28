#!/bin/bash

# ============================================
# Test Paper Trading - Wave3 v2.1
# ============================================
#
# Script de teste rápido do paper trading
# com 1 símbolo (PETR4) em modo dry-run
#
# Uso:
#   bash scripts/test_paper_trading.sh
#
# ============================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "========================================"
echo "📊 TEST PAPER TRADING - Wave3 v2.1"
echo "========================================"
echo ""

# 1. Verificar containers
echo "1️⃣  Verificando containers..."
containers=("b3-postgres" "b3-timescaledb")

for container in "${containers[@]}"; do
    if [ "$(docker ps -q -f name=$container)" ]; then
        echo "  ✅ $container: running"
    else
        echo "  ❌ $container: NOT RUNNING"
        echo ""
        echo "💡 Inicie os containers com:"
        echo "   docker-compose up -d"
        exit 1
    fi
done

echo ""

# 2. Testar conexão PostgreSQL
echo "2️⃣  Testando PostgreSQL..."
if docker exec b3-postgres psql -U b3trading_user -d b3trading_db -c "\dt" > /dev/null 2>&1; then
    echo "  ✅ PostgreSQL: conectado"
else
    echo "  ❌ PostgreSQL: erro de conexão"
    exit 1
fi

echo ""

# 3. Verificar schema
echo "3️⃣  Verificando schema paper trading..."
TABLES=$(docker exec b3-postgres psql -U b3trading_user -d b3trading_db -t -c "
    SELECT COUNT(*) FROM information_schema.tables 
    WHERE table_name IN ('paper_positions', 'paper_trades', 'ml_training_data', 'paper_capital_history')
")

if [ "$TABLES" -eq 4 ]; then
    echo "  ✅ Schema: OK (4 tabelas encontradas)"
else
    echo "  ⚠️  Schema incompleto ($TABLES/4 tabelas)"
    echo ""
    echo "💡 Aplique o schema com:"
    echo "   docker exec -i b3-postgres psql -U b3trading_user -d b3trading_db < infrastructure/postgres/paper_trading_schema.sql"
    exit 1
fi

echo ""

# 4. Verificar dados TimescaleDB
echo "4️⃣  Verificando dados TimescaleDB..."
CANDLES=$(docker exec b3-timescaledb psql -U b3trading_ts -d b3trading_market -t -c "
    SELECT COUNT(*) FROM ohlcv_daily WHERE symbol = 'PETR4'
")

if [ "$CANDLES" -gt 100 ]; then
    echo "  ✅ Dados PETR4: $CANDLES candles"
else
    echo "  ❌ Dados insuficientes: $CANDLES candles (mínimo: 100)"
    exit 1
fi

echo ""

# 5. Limpar dados anteriores (opcional)
echo "5️⃣  Limpando dados anteriores..."
read -p "  Deseja limpar dados de paper trading anteriores? [y/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    docker exec b3-postgres psql -U b3trading_user -d b3trading_db -c "
        TRUNCATE TABLE paper_positions, paper_trades, ml_training_data, paper_capital_history RESTART IDENTITY CASCADE;
    " > /dev/null
    echo "  ✅ Dados limpos"
else
    echo "  ⏭️  Mantendo dados existentes"
fi

echo ""

# 6. Criar snapshot inicial
echo "6️⃣  Criando snapshot inicial de capital..."
docker exec b3-postgres psql -U b3trading_user -d b3trading_db -c "
    INSERT INTO paper_capital_history (capital, initial_capital, realized_pnl)
    VALUES (100000.00, 100000.00, 0.00);
" > /dev/null

echo "  ✅ Snapshot criado (R$ 100,000.00)"
echo ""

# 7. Modo de teste
echo "7️⃣  Escolha o modo de teste:"
echo ""
echo "  1) Teste rápido (1 símbolo - PETR4, scan 60s, 5 minutos total)"
echo "  2) Teste completo (5 símbolos, scan 300s, rodando em background)"
echo "  3) Cancelar"
echo ""

read -p "Escolha [1-3]: " -n 1 -r
echo

case $REPLY in
    1)
        echo ""
        echo "🧪 TESTE RÁPIDO - PETR4 apenas"
        echo "================================"
        echo ""
        echo "⏱️  Duração: 5 minutos (5 scans de 60s)"
        echo "📊 Símbolo: PETR4"
        echo "⚙️  Config: capital=100k, max_pos=1, quality≥55"
        echo ""
        
        # Criar script Python temporário
        cat > /tmp/test_paper_trading.py << 'EOF'
import asyncio
import sys
sys.path.append('/app/src')

from paper_trading_wave3 import Wave3PaperTrader
from loguru import logger

async def main():
    logger.info("🧪 Iniciando TESTE RÁPIDO (5 minutos)")
    
    trader = Wave3PaperTrader(
        initial_capital=100000.0,
        quality_score_threshold=55,
        max_positions=1,  # Apenas 1 posição no teste
        risk_per_trade=0.02
    )
    
    # Conectar
    await trader.connect_databases()
    
    # Rodar por 5 minutos
    trader.is_running = True
    
    for i in range(5):  # 5 scans
        logger.info(f"🔍 Scan {i+1}/5")
        await trader.scan_symbol('PETR4')
        await trader.update_positions()
        
        if i < 4:  # Não aguardar no último scan
            await asyncio.sleep(60)  # 1 minuto
    
    # Status final
    await trader.log_status()
    
    # Cleanup
    await trader.cleanup()
    
    logger.info("✅ Teste concluído!")

if __name__ == '__main__':
    asyncio.run(main())
EOF
        
        # Executar no container
        docker exec -it b3-execution-engine python /tmp/test_paper_trading.py
        
        rm /tmp/test_paper_trading.py
        ;;
    
    2)
        echo ""
        echo "🚀 TESTE COMPLETO - 5 símbolos"
        echo "================================"
        echo ""
        echo "📊 Símbolos: PETR4, VALE3, ITUB4, BBDC4, ABEV3"
        echo "⏱️  Scan interval: 300s (5 minutos)"
        echo "🕐 Horário pregão: 09:00-18:00 BRT"
        echo ""
        echo "🔄 O processo rodará em BACKGROUND"
        echo ""
        
        # Executar no container em background
        docker exec -d b3-execution-engine python /app/src/paper_trading_wave3.py
        
        echo "✅ Paper Trading iniciado!"
        echo ""
        echo "📝 Comandos úteis:"
        echo ""
        echo "  # Ver logs em tempo real"
        echo "  docker exec -it b3-execution-engine tail -f /app/logs/paper_trading_$(date +%Y-%m-%d).log"
        echo ""
        echo "  # Ver status no PostgreSQL"
        echo "  docker exec b3-postgres psql -U b3trading_user -d b3trading_db -c 'SELECT * FROM paper_trading_summary'"
        echo ""
        echo "  # Parar paper trading"
        echo "  docker exec b3-execution-engine pkill -f paper_trading_wave3.py"
        echo ""
        ;;
    
    *)
        echo ""
        echo "❌ Cancelado"
        exit 0
        ;;
esac

echo ""
echo "========================================"
echo "✅ Script finalizado"
echo "========================================"
