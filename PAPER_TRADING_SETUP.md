# 📊 Paper Trading Setup - Wave3 v2.1
## Plano Executivo de Implementação

> **Objetivo:** Validar estratégia Wave3 v2.1 em ambiente simulado com dados reais B3  
> **Período:** 3-6 meses de coleta de dados  
> **Meta:** 50-100 trades para retreino ML v2.5  
> **Data Início:** 27 de Janeiro de 2026

---

## 🎯 Visão Geral

### O que é Paper Trading?
Simulação de trading em tempo real com:
- ✅ Preços reais (ProfitChart ou tempo real)
- ✅ Execução simulada (sem risco de capital)
- ✅ Coleta de dados para ML futuro
- ✅ Validação de estratégia antes de capital real

### Por que Fazer?
1. **Validar Win Rate:** Confirmar 77.8% do backtest em produção
2. **Coletar Dataset ML:** 103 features × 50-100 trades
3. **Ajustar Parâmetros:** Quality score, thresholds, filtros
4. **Detectar Problemas:** Slippage, latência, bugs

---

## 📋 Arquitetura do Sistema

```
┌─────────────────────────────────────────────────────────────────┐
│                    PAPER TRADING ARCHITECTURE                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐  │
│  │ Data Source  │─────▶│  Wave3 v2.1  │─────▶│   Execution  │  │
│  │              │      │   Strategy   │      │    Engine    │  │
│  │ ProfitChart/ │      │              │      │              │  │
│  │ Real-Time API│      │ Signal Gen   │      │ Paper Trade  │  │
│  └──────────────┘      └──────────────┘      └──────────────┘  │
│         │                      │                      │          │
│         │                      │                      ▼          │
│         │                      │              ┌──────────────┐  │
│         │                      │              │  PostgreSQL  │  │
│         │                      │              │              │  │
│         │                      │              │ • Positions  │  │
│         │                      │              │ • Trades     │  │
│         │                      │              │ • ML Data    │  │
│         │                      │              └──────────────┘  │
│         │                      │                      │          │
│         │                      ▼                      ▼          │
│         │              ┌──────────────┐      ┌──────────────┐  │
│         └─────────────▶│ TimescaleDB  │      │   Grafana    │  │
│                        │              │      │              │  │
│                        │ OHLC 60min   │      │ • Dashboard  │  │
│                        │ OHLC Daily   │      │ • Alerts     │  │
│                        └──────────────┘      └──────────────┘  │
│                                                      │          │
│                                              ┌──────────────┐  │
│                                              │   Telegram   │  │
│                                              │     Bot      │  │
│                                              │              │  │
│                                              │ • Signals    │  │
│                                              │ • Trades     │  │
│                                              │ • Daily P&L  │  │
│                                              └──────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🚀 FASE 1: Infraestrutura Base (Semana 1)

### 1.1 Database Schema - PostgreSQL

**Objetivo:** Armazenar posições, trades e dados ML

```sql
-- 📊 Schema: paper_trading

-- Tabela de posições abertas
CREATE TABLE paper_positions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    position_id VARCHAR(20) UNIQUE NOT NULL,
    symbol VARCHAR(10) NOT NULL,
    side VARCHAR(4) CHECK (side IN ('BUY', 'SELL')),
    quantity INTEGER NOT NULL,
    entry_price NUMERIC(10,2) NOT NULL,
    entry_time TIMESTAMP NOT NULL DEFAULT NOW(),
    stop_loss NUMERIC(10,2),
    take_profit NUMERIC(10,2),
    current_price NUMERIC(10,2),
    unrealized_pnl NUMERIC(12,2),
    wave3_score INTEGER,
    signal_data JSONB,  -- Todos os dados do sinal Wave3
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Tabela de trades fechados
CREATE TABLE paper_trades (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trade_id VARCHAR(20) UNIQUE NOT NULL,
    symbol VARCHAR(10) NOT NULL,
    side VARCHAR(4) CHECK (side IN ('BUY', 'SELL')),
    quantity INTEGER NOT NULL,
    
    -- Entry
    entry_price NUMERIC(10,2) NOT NULL,
    entry_time TIMESTAMP NOT NULL,
    entry_signal JSONB,  -- Sinal original Wave3
    
    -- Exit
    exit_price NUMERIC(10,2) NOT NULL,
    exit_time TIMESTAMP NOT NULL,
    exit_reason VARCHAR(20) CHECK (exit_reason IN (
        'take_profit', 'stop_loss', 'manual', 'timeout', 
        'reversal', 'regime_change'
    )),
    
    -- P&L
    pnl NUMERIC(12,2) NOT NULL,
    return_pct NUMERIC(8,4) NOT NULL,
    
    -- Métricas
    holding_days INTEGER,
    wave3_score INTEGER,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT NOW()
);

-- Tabela de dados ML (para retreino futuro)
CREATE TABLE ml_training_data (
    id SERIAL PRIMARY KEY,
    trade_id VARCHAR(20) REFERENCES paper_trades(trade_id),
    
    -- Contexto do trade
    symbol VARCHAR(10) NOT NULL,
    trade_date DATE NOT NULL,
    result VARCHAR(4) CHECK (result IN ('WIN', 'LOSS', 'BE')),
    return_pct NUMERIC(8,4),
    
    -- Wave3 metadata
    wave3_score INTEGER NOT NULL,
    signal_type VARCHAR(10),
    
    -- 103 ML Features (JSON compactado)
    features JSONB NOT NULL,
    
    -- Contexto de mercado
    market_regime VARCHAR(20),  -- trending_up, ranging, volatile
    volatility_percentile INTEGER,  -- 0-100
    
    -- Audit
    collected_at TIMESTAMP DEFAULT NOW(),
    
    CONSTRAINT unique_ml_trade UNIQUE(trade_id)
);

-- Índices para performance
CREATE INDEX idx_positions_symbol ON paper_positions(symbol);
CREATE INDEX idx_positions_entry_time ON paper_positions(entry_time DESC);
CREATE INDEX idx_trades_symbol ON paper_trades(symbol);
CREATE INDEX idx_trades_entry_time ON paper_trades(entry_time DESC);
CREATE INDEX idx_trades_exit_time ON paper_trades(exit_time DESC);
CREATE INDEX idx_trades_result ON paper_trades(exit_reason);
CREATE INDEX idx_ml_symbol ON ml_training_data(symbol);
CREATE INDEX idx_ml_date ON ml_training_data(trade_date DESC);
CREATE INDEX idx_ml_result ON ml_training_data(result);

-- View: Resumo de performance
CREATE VIEW paper_trading_summary AS
SELECT
    COUNT(*) as total_trades,
    SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as winning_trades,
    SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as losing_trades,
    ROUND(SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END)::NUMERIC / 
          COUNT(*)::NUMERIC * 100, 2) as win_rate,
    ROUND(SUM(pnl), 2) as total_pnl,
    ROUND(AVG(return_pct), 4) as avg_return_pct,
    ROUND(MAX(return_pct), 4) as max_return_pct,
    ROUND(MIN(return_pct), 4) as max_drawdown_pct,
    ROUND(AVG(holding_days), 1) as avg_holding_days
FROM paper_trades;

-- View: Performance por símbolo
CREATE VIEW paper_trading_by_symbol AS
SELECT
    symbol,
    COUNT(*) as trades,
    SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as wins,
    ROUND(SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END)::NUMERIC / 
          COUNT(*)::NUMERIC * 100, 2) as win_rate,
    ROUND(SUM(pnl), 2) as total_pnl,
    ROUND(AVG(return_pct), 4) as avg_return,
    ROUND(MAX(return_pct), 4) as best_trade,
    ROUND(MIN(return_pct), 4) as worst_trade
FROM paper_trades
GROUP BY symbol
ORDER BY total_pnl DESC;

-- View: Coleta ML progress
CREATE VIEW ml_collection_progress AS
SELECT
    COUNT(*) as samples_collected,
    SUM(CASE WHEN result = 'WIN' THEN 1 ELSE 0 END) as wins,
    SUM(CASE WHEN result = 'LOSS' THEN 1 ELSE 0 END) as losses,
    ROUND(SUM(CASE WHEN result = 'WIN' THEN 1 ELSE 0 END)::NUMERIC / 
          COUNT(*)::NUMERIC * 100, 2) as balance_pct,
    MIN(trade_date) as first_trade,
    MAX(trade_date) as last_trade,
    COUNT(DISTINCT symbol) as unique_symbols,
    CASE
        WHEN COUNT(*) < 25 THEN 'collecting_initial'
        WHEN COUNT(*) < 50 THEN 'ready_for_beta'
        WHEN COUNT(*) < 100 THEN 'ready_for_production'
        ELSE 'ready_for_advanced_ml'
    END as ml_readiness
FROM ml_training_data;
```

**Executar:**
```bash
# Criar schema
docker exec -i b3-postgres psql -U b3trading_user -d b3trading < infrastructure/postgres/paper_trading_schema.sql
```

---

### 1.2 Configuração Wave3 Strategy

**Arquivo:** `services/execution-engine/src/paper_trading_wave3.py`

```python
#!/usr/bin/env python3
"""
Paper Trading Manager - Wave3 v2.1 Integration
==============================================

Features:
- Geração de sinais Wave3 em tempo real
- Execução simulada de trades
- Coleta automática de dados ML
- Monitoring de performance
- Alertas Telegram

Author: B3 Trading Platform
Date: Janeiro 2026
"""

import asyncio
import asyncpg
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from loguru import logger

from strategies.wave3_enhanced import Wave3Enhanced
from ml.feature_engineering_v2 import FeatureEngineerV2


class Wave3PaperTrader:
    """Gerenciador de paper trading com Wave3 v2.1"""
    
    def __init__(
        self,
        initial_capital: float = 100000.0,
        quality_score_threshold: int = 55,
        max_positions: int = 5,
        risk_per_trade: float = 0.02,  # 2% do capital por trade
    ):
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.quality_threshold = quality_score_threshold
        self.max_positions = max_positions
        self.risk_per_trade = risk_per_trade
        
        # Estratégia
        self.wave3 = Wave3Enhanced()
        self.feature_engineer = FeatureEngineerV2()
        
        # Estado
        self.positions: Dict[str, Dict] = {}
        self.is_running = False
        self.start_time: Optional[datetime] = None
        
        # Database
        self.db_pool = None
        
        logger.info(f"🚀 Wave3 Paper Trader inicializado | Capital: R$ {initial_capital:,.2f}")
    
    async def connect_database(self):
        """Conecta ao PostgreSQL"""
        self.db_pool = await asyncpg.create_pool(
            host='localhost',
            port=5432,
            user='b3trading_user',
            password='b3trading_password',
            database='b3trading',
            min_size=2,
            max_size=10
        )
        logger.info("✅ Conectado ao PostgreSQL")
    
    async def start(self, symbols: List[str], scan_interval: int = 300):
        """
        Inicia paper trading
        
        Args:
            symbols: Lista de ativos para monitorar (ex: ['PETR4', 'VALE3'])
            scan_interval: Intervalo de scan em segundos (padrão: 5 min)
        """
        if not self.db_pool:
            await self.connect_database()
        
        self.is_running = True
        self.start_time = datetime.now()
        
        logger.info(f"▶️ Paper Trading INICIADO | Ativos: {symbols}")
        
        while self.is_running:
            try:
                # 1. Buscar dados mais recentes
                for symbol in symbols:
                    await self.scan_symbol(symbol)
                
                # 2. Atualizar preços das posições abertas
                await self.update_positions()
                
                # 3. Log de status a cada hora
                if datetime.now().minute == 0:
                    await self.log_status()
                
                # 4. Aguardar próximo scan
                await asyncio.sleep(scan_interval)
                
            except Exception as e:
                logger.error(f"❌ Erro no loop principal: {e}")
                await asyncio.sleep(60)  # Retry após 1 minuto
    
    async def scan_symbol(self, symbol: str):
        """Escaneia um símbolo e gera sinais Wave3"""
        
        try:
            # 1. Buscar dados do TimescaleDB
            df_daily = await self.fetch_ohlcv(symbol, 'daily', days=365)
            df_60min = await self.fetch_ohlcv(symbol, '60min', days=180)
            
            if df_daily is None or df_60min is None:
                logger.warning(f"⚠️ Dados insuficientes para {symbol}")
                return
            
            # 2. Gerar sinal Wave3
            signal = self.wave3.generate_signal(df_daily, df_60min)
            
            if signal is None:
                return  # Nenhum sinal
            
            # 3. Verificar quality score
            if signal.quality_score < self.quality_threshold:
                logger.debug(f"❌ {symbol} rejected | Score: {signal.quality_score} < {self.quality_threshold}")
                return
            
            # 4. Verificar se já existe posição aberta
            if symbol in self.positions:
                logger.debug(f"⏭️ {symbol} já possui posição aberta")
                return
            
            # 5. Verificar limite de posições
            if len(self.positions) >= self.max_positions:
                logger.warning(f"⏸️ Limite de {self.max_positions} posições atingido")
                return
            
            # 6. Executar ordem
            await self.execute_signal(symbol, signal, df_daily, df_60min)
            
        except Exception as e:
            logger.error(f"❌ Erro ao escanear {symbol}: {e}")
    
    async def execute_signal(
        self,
        symbol: str,
        signal,
        df_daily: pd.DataFrame,
        df_60min: pd.DataFrame
    ):
        """Executa um sinal Wave3"""
        
        # 1. Calcular tamanho da posição (Kelly)
        risk_amount = self.current_capital * self.risk_per_trade
        stop_distance = signal.entry_price - signal.stop_loss
        position_size = int(risk_amount / stop_distance)
        
        # 2. Gerar features ML (para coleta)
        features = self.feature_engineer.generate_all_features(df_daily)
        
        # 3. Criar registro na tabela paper_positions
        position_data = {
            'position_id': f"POS-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
            'symbol': symbol,
            'side': 'BUY',  # Wave3 é sempre compra
            'quantity': position_size,
            'entry_price': signal.entry_price,
            'entry_time': datetime.now(),
            'stop_loss': signal.stop_loss,
            'take_profit': signal.target_3,  # Alvo final
            'wave3_score': signal.quality_score,
            'signal_data': {
                'type': signal.signal_type,
                'entry': signal.entry_price,
                'stop': signal.stop_loss,
                'targets': [signal.target_1, signal.target_2, signal.target_3],
                'indicators': signal.indicators,
                'context': signal.context_daily
            }
        }
        
        async with self.db_pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO paper_positions (
                    position_id, symbol, side, quantity, entry_price,
                    entry_time, stop_loss, take_profit, wave3_score, signal_data
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            ''', 
                position_data['position_id'],
                position_data['symbol'],
                position_data['side'],
                position_data['quantity'],
                position_data['entry_price'],
                position_data['entry_time'],
                position_data['stop_loss'],
                position_data['take_profit'],
                position_data['wave3_score'],
                position_data['signal_data']
            )
        
        # 4. Adicionar ao tracking local
        self.positions[symbol] = {
            **position_data,
            'features': features.to_dict()  # Guardar para ML futuro
        }
        
        # 5. Log e alerta
        logger.info(
            f"🟢 NOVA POSIÇÃO | {symbol} | "
            f"Entry: R$ {signal.entry_price:.2f} | "
            f"Stop: R$ {signal.stop_loss:.2f} | "
            f"Target: R$ {signal.target_3:.2f} | "
            f"Score: {signal.quality_score} | "
            f"Size: {position_size} ações"
        )
        
        # TODO: Enviar alerta Telegram
        # await self.send_telegram_alert(f"🟢 Nova posição: {symbol}")
    
    async def update_positions(self):
        """Atualiza preços das posições abertas e verifica stops/targets"""
        
        for symbol, position in list(self.positions.items()):
            try:
                # 1. Buscar preço atual
                current_price = await self.get_current_price(symbol)
                
                if current_price is None:
                    continue
                
                # 2. Atualizar P&L
                entry = position['entry_price']
                qty = position['quantity']
                pnl = (current_price - entry) * qty
                return_pct = (current_price - entry) / entry * 100
                
                # 3. Verificar stop loss
                if current_price <= position['stop_loss']:
                    await self.close_position(
                        symbol, 
                        position['stop_loss'], 
                        'stop_loss'
                    )
                    logger.warning(f"🔴 STOP LOSS | {symbol} | Loss: {return_pct:.2f}%")
                    continue
                
                # 4. Verificar take profit
                if current_price >= position['take_profit']:
                    await self.close_position(
                        symbol,
                        position['take_profit'],
                        'take_profit'
                    )
                    logger.info(f"🟢 TAKE PROFIT | {symbol} | Gain: +{return_pct:.2f}%")
                    continue
                
                # 5. Atualizar no PostgreSQL
                async with self.db_pool.acquire() as conn:
                    await conn.execute('''
                        UPDATE paper_positions
                        SET current_price = $1,
                            unrealized_pnl = $2,
                            updated_at = NOW()
                        WHERE position_id = $3
                    ''', current_price, pnl, position['position_id'])
                
            except Exception as e:
                logger.error(f"❌ Erro ao atualizar {symbol}: {e}")
    
    async def close_position(
        self,
        symbol: str,
        exit_price: float,
        exit_reason: str
    ):
        """Fecha uma posição e salva nos trades"""
        
        if symbol not in self.positions:
            return
        
        position = self.positions[symbol]
        
        # 1. Calcular P&L final
        entry = position['entry_price']
        qty = position['quantity']
        pnl = (exit_price - entry) * qty
        return_pct = (exit_price - entry) / entry * 100
        
        # 2. Atualizar capital
        self.current_capital += pnl
        
        # 3. Calcular holding period
        entry_time = position['entry_time']
        exit_time = datetime.now()
        holding_days = (exit_time - entry_time).days
        
        # 4. Determinar resultado (WIN/LOSS)
        result = 'WIN' if pnl > 0 else ('LOSS' if pnl < 0 else 'BE')
        
        # 5. Salvar no paper_trades
        async with self.db_pool.acquire() as conn:
            trade_id = await conn.fetchval('''
                INSERT INTO paper_trades (
                    trade_id, symbol, side, quantity,
                    entry_price, entry_time, entry_signal,
                    exit_price, exit_time, exit_reason,
                    pnl, return_pct, holding_days, wave3_score
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                RETURNING trade_id
            ''',
                f"TRD-{exit_time.strftime('%Y%m%d-%H%M%S')}",
                symbol,
                'BUY',
                qty,
                entry,
                entry_time,
                position['signal_data'],
                exit_price,
                exit_time,
                exit_reason,
                pnl,
                return_pct,
                holding_days,
                position['wave3_score']
            )
            
            # 6. Salvar features ML
            await conn.execute('''
                INSERT INTO ml_training_data (
                    trade_id, symbol, trade_date, result, return_pct,
                    wave3_score, signal_type, features
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            ''',
                trade_id,
                symbol,
                entry_time.date(),
                result,
                return_pct,
                position['wave3_score'],
                position['signal_data']['type'],
                position['features']
            )
            
            # 7. Remover do paper_positions
            await conn.execute('''
                DELETE FROM paper_positions
                WHERE position_id = $1
            ''', position['position_id'])
        
        # 8. Remover do tracking local
        del self.positions[symbol]
        
        # 9. Log final
        emoji = '🟢' if pnl > 0 else '🔴'
        logger.info(
            f"{emoji} TRADE FECHADO | {symbol} | "
            f"Exit: R$ {exit_price:.2f} | "
            f"P&L: R$ {pnl:,.2f} ({return_pct:+.2f}%) | "
            f"Holding: {holding_days} dias | "
            f"Reason: {exit_reason}"
        )
        
        # TODO: Enviar alerta Telegram
    
    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        days: int
    ) -> Optional[pd.DataFrame]:
        """Busca dados OHLCV do TimescaleDB"""
        
        table = 'ohlcv_daily' if timeframe == 'daily' else 'ohlcv_60min'
        
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(f'''
                SELECT time, open, high, low, close, volume
                FROM {table}
                WHERE symbol = $1
                  AND time >= NOW() - INTERVAL '{days} days'
                ORDER BY time ASC
            ''', symbol)
        
        if not rows:
            return None
        
        df = pd.DataFrame(rows, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
        df.set_index('time', inplace=True)
        
        return df
    
    async def get_current_price(self, symbol: str) -> Optional[float]:
        """Busca preço mais recente (close do último candle)"""
        
        async with self.db_pool.acquire() as conn:
            price = await conn.fetchval('''
                SELECT close
                FROM ohlcv_60min
                WHERE symbol = $1
                ORDER BY time DESC
                LIMIT 1
            ''', symbol)
        
        return float(price) if price else None
    
    async def log_status(self):
        """Log de status a cada hora"""
        
        # Calcular métricas
        unrealized_pnl = sum(
            (await self.get_current_price(sym) - pos['entry_price']) * pos['quantity']
            for sym, pos in self.positions.items()
        )
        
        total_pnl = self.current_capital - self.initial_capital
        return_pct = total_pnl / self.initial_capital * 100
        
        logger.info(
            f"📊 STATUS | "
            f"Capital: R$ {self.current_capital:,.2f} | "
            f"P&L: R$ {total_pnl:,.2f} ({return_pct:+.2f}%) | "
            f"Posições: {len(self.positions)}"
        )
    
    async def stop(self):
        """Para o paper trading"""
        self.is_running = False
        logger.info("⏹️ Paper Trading PARADO")
        
        if self.db_pool:
            await self.db_pool.close()


# ========================================
# MAIN - Exemplo de Uso
# ========================================

async def main():
    """Exemplo de execução"""
    
    # 1. Criar trader
    trader = Wave3PaperTrader(
        initial_capital=100000.0,
        quality_score_threshold=55,
        max_positions=5,
        risk_per_trade=0.02
    )
    
    # 2. Definir ativos (usar os validados)
    symbols = ['PETR4', 'VALE3', 'ITUB4', 'BBDC4', 'ABEV3']
    
    # 3. Iniciar (scaneia a cada 5 minutos)
    await trader.start(symbols, scan_interval=300)


if __name__ == '__main__':
    asyncio.run(main())
```

---

### 1.3 Script de Inicialização

**Arquivo:** `scripts/start_paper_trading.sh`

```bash
#!/bin/bash
# Paper Trading Startup Script
# ============================

set -e

echo "🚀 Iniciando Paper Trading - Wave3 v2.1"
echo "========================================"

# 1. Verificar se containers estão rodando
echo "📊 Verificando containers..."
docker compose ps | grep -q "timescaledb.*Up" || {
    echo "❌ TimescaleDB não está rodando!"
    exit 1
}

docker compose ps | grep -q "postgres.*Up" || {
    echo "❌ PostgreSQL não está rodando!"
    exit 1
}

echo "✅ Containers OK"

# 2. Criar schema se não existir
echo "📝 Criando schema paper trading..."
docker exec -i b3-postgres psql -U b3trading_user -d b3trading <<SQL
CREATE TABLE IF NOT EXISTS paper_positions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    position_id VARCHAR(20) UNIQUE NOT NULL,
    symbol VARCHAR(10) NOT NULL,
    side VARCHAR(4) CHECK (side IN ('BUY', 'SELL')),
    quantity INTEGER NOT NULL,
    entry_price NUMERIC(10,2) NOT NULL,
    entry_time TIMESTAMP NOT NULL DEFAULT NOW(),
    stop_loss NUMERIC(10,2),
    take_profit NUMERIC(10,2),
    current_price NUMERIC(10,2),
    unrealized_pnl NUMERIC(12,2),
    wave3_score INTEGER,
    signal_data JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS paper_trades (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trade_id VARCHAR(20) UNIQUE NOT NULL,
    symbol VARCHAR(10) NOT NULL,
    side VARCHAR(4),
    quantity INTEGER NOT NULL,
    entry_price NUMERIC(10,2) NOT NULL,
    entry_time TIMESTAMP NOT NULL,
    entry_signal JSONB,
    exit_price NUMERIC(10,2) NOT NULL,
    exit_time TIMESTAMP NOT NULL,
    exit_reason VARCHAR(20),
    pnl NUMERIC(12,2) NOT NULL,
    return_pct NUMERIC(8,4) NOT NULL,
    holding_days INTEGER,
    wave3_score INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ml_training_data (
    id SERIAL PRIMARY KEY,
    trade_id VARCHAR(20) REFERENCES paper_trades(trade_id),
    symbol VARCHAR(10) NOT NULL,
    trade_date DATE NOT NULL,
    result VARCHAR(4),
    return_pct NUMERIC(8,4),
    wave3_score INTEGER NOT NULL,
    signal_type VARCHAR(10),
    features JSONB NOT NULL,
    collected_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT unique_ml_trade UNIQUE(trade_id)
);
SQL

echo "✅ Schema criado"

# 3. Iniciar paper trader
echo "▶️ Iniciando Paper Trader..."
docker exec -d b3-execution-engine python3 /app/src/paper_trading_wave3.py

echo ""
echo "✅ Paper Trading ATIVO!"
echo ""
echo "📊 Monitorar:"
echo "   docker logs -f b3-execution-engine | grep -E 'NOVA POSIÇÃO|TRADE FECHADO|STATUS'"
echo ""
echo "📈 Dashboard:"
echo "   http://localhost:3001 (Grafana)"
echo ""
echo "🛑 Para parar:"
echo "   docker exec b3-execution-engine pkill -f paper_trading_wave3"
```

---

## 📊 FASE 2: Monitoramento e Alertas (Semana 2)

### 2.1 Telegram Bot Integration

**Arquivo:** `services/execution-engine/src/telegram_notifier.py`

```python
#!/usr/bin/env python3
"""
Telegram Notifier - Alertas de Paper Trading
============================================
"""

import asyncio
import aiohttp
from typing import Dict, Optional
from loguru import logger


class TelegramNotifier:
    """Cliente Telegram para alertas"""
    
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.api_url = f"https://api.telegram.org/bot{bot_token}"
    
    async def send_message(self, text: str, parse_mode: str = "Markdown"):
        """Envia mensagem"""
        
        url = f"{self.api_url}/sendMessage"
        
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": parse_mode
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as response:
                    if response.status == 200:
                        logger.debug(f"✅ Telegram: mensagem enviada")
                        return True
                    else:
                        error = await response.text()
                        logger.error(f"❌ Telegram error: {error}")
                        return False
        
        except Exception as e:
            logger.error(f"❌ Erro ao enviar Telegram: {e}")
            return False
    
    async def alert_new_position(self, symbol: str, signal: Dict):
        """Alerta de nova posição"""
        
        text = f"""
🟢 *NOVA POSIÇÃO - Wave3 v2.1*

📊 *Ativo:* {symbol}
💰 *Entry:* R$ {signal['entry_price']:.2f}
🛑 *Stop Loss:* R$ {signal['stop_loss']:.2f}
🎯 *Target:* R$ {signal['take_profit']:.2f}
⭐ *Score:* {signal['wave3_score']}/100

📈 *Risco/Retorno:* 1:{signal.get('reward_risk', 3):.1f}
🕐 *Horário:* {signal['entry_time']}
"""
        
        await self.send_message(text)
    
    async def alert_closed_position(
        self,
        symbol: str,
        pnl: float,
        return_pct: float,
        reason: str
    ):
        """Alerta de posição fechada"""
        
        emoji = '🟢' if pnl > 0 else ('🔴' if pnl < 0 else '⚪')
        result = 'WIN' if pnl > 0 else ('LOSS' if pnl < 0 else 'BREAK EVEN')
        
        text = f"""
{emoji} *TRADE FECHADO - {result}*

📊 *Ativo:* {symbol}
💵 *P&L:* R$ {pnl:,.2f} ({return_pct:+.2f}%)
🚪 *Saída:* {reason.replace('_', ' ').title()}

{'🎉 Excelente resultado!' if return_pct > 5 else ''}
"""
        
        await self.send_message(text)
    
    async def alert_daily_summary(self, stats: Dict):
        """Resumo diário"""
        
        text = f"""
📊 *RESUMO DIÁRIO - Paper Trading*

💰 *Capital:* R$ {stats['capital']:,.2f}
📈 *Retorno:* {stats['return_pct']:+.2f}%
📊 *P&L Total:* R$ {stats['total_pnl']:,.2f}

🎯 *Trades:* {stats['total_trades']}
✅ *Wins:* {stats['wins']} ({stats['win_rate']:.1f}%)
❌ *Losses:* {stats['losses']}
🔄 *Posições Abertas:* {stats['open_positions']}

🏆 *Melhor Trade:* {stats.get('best_trade', 'N/A')}
⚠️ *Pior Trade:* {stats.get('worst_trade', 'N/A')}
"""
        
        await self.send_message(text)


# Configurar via .env
# TELEGRAM_BOT_TOKEN=your_token_here
# TELEGRAM_CHAT_ID=your_chat_id_here
```

**Setup Telegram:**
1. Falar com [@BotFather](https://t.me/BotFather) no Telegram
2. Criar bot: `/newbot`
3. Copiar token
4. Obter chat_id: Enviar mensagem para o bot e visitar:
   `https://api.telegram.org/bot<TOKEN>/getUpdates`

**Adicionar ao `.env`:**
```bash
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=123456789
```

---

### 2.2 Grafana Dashboard

**Arquivo:** `infrastructure/grafana/provisioning/dashboards/paper_trading.json`

(Criar dashboard JSON com painéis para equity curve, win rate, trades, etc.)

**Métricas Importantes:**
- Equity Curve (capital ao longo do tempo)
- Win Rate rolling (últimos 10/20 trades)
- Drawdown máximo
- Sharpe Ratio semanal
- Trades por dia/semana
- Distribuição de retornos
- Heatmap de performance por símbolo

---

## 🔄 FASE 3: Workflow Operacional (Semanas 3-4)

### 3.1 Rotina Diária

**Horário de Operação:**
- **09:00 BRT:** Sistema inicia (pré-abertura)
- **09:30-10:00:** Primeiro scan (após abertura)
- **10:00-17:00:** Scans a cada 5-15 minutos
- **17:30:** Último scan (antes do fechamento)
- **18:00:** Relatório diário automático

**Checklist Diário:**
```bash
# 1. Manhã (09:00)
# Verificar se sistema está rodando
docker ps | grep execution-engine

# Ver últimas posições
docker exec b3-postgres psql -U b3trading_user -d b3trading \
  -c "SELECT * FROM paper_positions ORDER BY entry_time DESC LIMIT 5"

# 2. Durante o Dia
# Monitorar logs em tempo real
docker logs -f b3-execution-engine | grep -E "POSIÇÃO|TRADE|STOP|TARGET"

# 3. Fim do Dia (18:00)
# Gerar relatório
docker exec b3-execution-engine python3 /app/scripts/daily_report.py

# Backup do dia
docker exec b3-postgres pg_dump -U b3trading_user b3trading > \
  /backups/paper_trading_$(date +%Y%m%d).sql
```

---

### 3.2 Script de Relatório Diário

**Arquivo:** `scripts/daily_report.py`

```python
#!/usr/bin/env python3
"""
Relatório Diário - Paper Trading
================================
"""

import asyncio
import asyncpg
from datetime import datetime, timedelta
from loguru import logger


async def generate_daily_report():
    """Gera relatório diário"""
    
    conn = await asyncpg.connect(
        host='localhost',
        port=5432,
        user='b3trading_user',
        password='b3trading_password',
        database='b3trading'
    )
    
    # 1. Trades do dia
    today_trades = await conn.fetch('''
        SELECT * FROM paper_trades
        WHERE exit_time >= CURRENT_DATE
        ORDER BY exit_time DESC
    ''')
    
    # 2. Posições abertas
    open_positions = await conn.fetch('''
        SELECT * FROM paper_positions
        ORDER BY entry_time DESC
    ''')
    
    # 3. Performance acumulada
    stats = await conn.fetchrow('''
        SELECT * FROM paper_trading_summary
    ''')
    
    # 4. ML collection progress
    ml_progress = await conn.fetchrow('''
        SELECT * FROM ml_collection_progress
    ''')
    
    # 5. Gerar relatório
    report = f"""
╔════════════════════════════════════════════════════════════╗
║       RELATÓRIO DIÁRIO - PAPER TRADING Wave3 v2.1         ║
║                {datetime.now().strftime('%d/%m/%Y %H:%M')}                           ║
╚════════════════════════════════════════════════════════════╝

📊 PERFORMANCE ACUMULADA
├─ Total Trades: {stats['total_trades']}
├─ Win Rate: {stats['win_rate']:.1f}% ({stats['winning_trades']}W / {stats['losing_trades']}L)
├─ P&L Total: R$ {stats['total_pnl']:,.2f}
├─ Retorno Médio: {stats['avg_return_pct']:.2f}%
├─ Melhor Trade: +{stats['max_return_pct']:.2f}%
└─ Pior Trade: {stats['max_drawdown_pct']:.2f}%

🔄 TRADES HOJE
├─ Executados: {len(today_trades)}
└─ {', '.join([f"{t['symbol']} ({t['return_pct']:+.2f}%)" for t in today_trades]) or 'Nenhum'}

📈 POSIÇÕES ABERTAS
├─ Total: {len(open_positions)}
└─ {', '.join([p['symbol'] for p in open_positions]) or 'Nenhuma'}

🤖 COLETA ML
├─ Samples: {ml_progress['samples_collected']} / 50 (meta mínima)
├─ Balanceamento: {ml_progress['wins']}W / {ml_progress['losses']}L ({ml_progress['balance_pct']:.1f}%)
├─ Símbolos Únicos: {ml_progress['unique_symbols']}
└─ Status: {ml_progress['ml_readiness'].replace('_', ' ').title()}

📅 PRÓXIMOS PASSOS
"""
    
    if ml_progress['samples_collected'] < 25:
        report += f"├─ Faltam {25 - ml_progress['samples_collected']} trades para ML Beta\n"
    elif ml_progress['samples_collected'] < 50:
        report += f"├─ Faltam {50 - ml_progress['samples_collected']} trades para ML Production\n"
        report += "├─ ✅ Pronto para treinar ML v2.5 Beta!\n"
    else:
        report += "├─ ✅ Dataset completo! Treinar ML v2.5 Production\n"
    
    report += "└─ Continuar paper trading...\n"
    
    print(report)
    
    # Salvar em arquivo
    with open(f'/app/logs/daily_report_{datetime.now().strftime("%Y%m%d")}.txt', 'w') as f:
        f.write(report)
    
    await conn.close()
    
    return report


if __name__ == '__main__':
    asyncio.run(generate_daily_report())
```

---

## 📅 CRONOGRAMA DE 3 MESES

### MÊS 1 (Fevereiro 2026)

**Semana 1 (27 Jan - 2 Fev):**
- [x] Criar schemas PostgreSQL
- [x] Implementar Wave3PaperTrader
- [x] Configurar Telegram Bot
- [ ] Setup Grafana Dashboard
- [ ] Primeiro teste com 1 ativo (PETR4)

**Semana 2-4:**
- [ ] Monitorar 5 ativos validados
- [ ] Coletar primeiros 10-15 trades
- [ ] Ajustar quality_score se necessário
- [ ] Validar win rate (esperado: 70%+)

**Meta do Mês:** 15-20 trades coletados

---

### MÊS 2 (Março 2026)

**Objetivos:**
- [ ] Atingir 25-30 trades
- [ ] Analisar distribuição (wins/losses)
- [ ] Treinar ML v2.5 BETA (preliminar)
- [ ] Comparar backtest ML vs Wave3 pura
- [ ] Exportar CSV para análise offline

**Meta do Mês:** 35-40 trades acumulados

---

### MÊS 3 (Abril 2026)

**Objetivos:**
- [ ] Atingir 50+ trades (meta mínima)
- [ ] Treinar ML v2.5 PRODUCTION
- [ ] Walk-Forward validation (4 folds)
- [ ] Decisão: ML é viável? (accuracy > 75%?)
- [ ] Se SIM: Paper trading com ML
- [ ] Se NÃO: Continuar Wave3 pura + coletar mais

**Meta do Mês:** 50-60 trades | ML v2.5 testado

---

## ✅ CHECKLIST DE VALIDAÇÃO

Antes de passar para capital real (no futuro):

### Performance
- [ ] Win Rate ≥ 70% (mínimo 50 trades)
- [ ] Sharpe Ratio ≥ 1.5
- [ ] Max Drawdown < 10%
- [ ] Payoff Ratio ≥ 2:1
- [ ] Consistency entre meses (±10%)

### Dados ML
- [ ] 50+ trades coletados
- [ ] Balanceamento 30-70% wins
- [ ] 5+ símbolos diferentes
- [ ] Features validadas (103 ou top 20)
- [ ] Sem missing data

### Sistema
- [ ] Zero bugs críticos
- [ ] Logs completos (audit trail)
- [ ] Alertas funcionando
- [ ] Backup automático ativo
- [ ] Dashboard atualizado

### Compliance
- [ ] Documentação completa
- [ ] Regras de entrada/saída claras
- [ ] Risk management validado
- [ ] Histórico exportável (IR)

---

## 🚨 Red Flags - Quando PARAR

### Parar Imediatamente Se:
- ❌ Win rate < 50% por 2 semanas consecutivas
- ❌ Drawdown > 15%
- ❌ 5+ trades perdedores seguidos
- ❌ Bug crítico (trades não fecham, stops ignorados)

### Pausar e Revisar Se:
- ⚠️ Win rate < 60% por 1 mês
- ⚠️ Sharpe < 1.0
- ⚠️ Quality score rejeitando tudo (0 sinais/semana)
- ⚠️ Quality score aceitando tudo (20+ sinais/semana)

---

## 📞 PRÓXIMOS PASSOS IMEDIATOS

### ESTA SEMANA (27 Jan - 2 Fev):

1. **Segunda (27 Jan):**
   - Criar schema PostgreSQL
   - Testar conexão TimescaleDB → Paper Trader

2. **Terça (28 Jan):**
   - Implementar `Wave3PaperTrader` class
   - Testar com 1 ativo (PETR4) em modo dry-run

3. **Quarta (29 Jan):**
   - Setup Telegram Bot
   - Enviar primeiro alerta de teste

4. **Quinta (30 Jan):**
   - Configurar Grafana dashboard
   - Ativar paper trading REAL (5 ativos)

5. **Sexta (31 Jan):**
   - Monitorar primeiro dia completo
   - Ajustar thresholds se necessário

---

## 📊 RESUMO EXECUTIVO

| Item | Status | Prazo | Responsável |
|------|--------|-------|-------------|
| **FASE 1: Infraestrutura** | 🟡 Em Progresso | Semana 1 | Dev Team |
| PostgreSQL Schema | ⏳ Pendente | 27 Jan | Database |
| Wave3PaperTrader Class | ⏳ Pendente | 28 Jan | Backend |
| Telegram Integration | ⏳ Pendente | 29 Jan | Backend |
| Grafana Dashboard | ⏳ Pendente | 30 Jan | DevOps |
| **FASE 2: Validação** | ⏳ Aguardando | Semana 2-4 | Trader |
| Primeiro Trade Real | ⏳ Pendente | Fev | Sistema |
| 25 Trades Coletados | ⏳ Pendente | Fim Fev | Sistema |
| **FASE 3: ML Dataset** | ⏳ Aguardando | Mês 2-3 | Data Science |
| 50 Trades Mínimos | ⏳ Pendente | Abr | Sistema |
| ML v2.5 Beta | ⏳ Pendente | Mar | ML Team |
| ML v2.5 Production | ⏳ Pendente | Abr | ML Team |

---

*Documento vivo - Atualizar conforme implementação*  
*Última atualização: 26 de Janeiro de 2026*  
*Próxima revisão: 2 de Fevereiro de 2026*
