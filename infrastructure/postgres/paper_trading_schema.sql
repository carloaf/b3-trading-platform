-- ============================================
-- PAPER TRADING SCHEMA - Wave3 v2.1
-- ============================================
-- Schema dedicado para paper trading e coleta de dados ML
-- Data: 27 de Janeiro de 2026

-- ============================================
-- POSIÇÕES ABERTAS (PAPER TRADING)
-- ============================================

CREATE TABLE IF NOT EXISTS paper_positions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    position_id VARCHAR(20) UNIQUE NOT NULL,
    
    -- Ativo
    symbol VARCHAR(10) NOT NULL,
    side VARCHAR(4) CHECK (side IN ('BUY', 'SELL')),
    quantity INTEGER NOT NULL,
    
    -- Preços
    entry_price NUMERIC(10,2) NOT NULL,
    entry_time TIMESTAMP NOT NULL DEFAULT NOW(),
    current_price NUMERIC(10,2),
    
    -- Gestão de risco
    stop_loss NUMERIC(10,2),
    take_profit NUMERIC(10,2),
    
    -- P&L não realizado
    unrealized_pnl NUMERIC(12,2),
    unrealized_pnl_pct NUMERIC(8,4),
    
    -- Wave3 metadata
    wave3_score INTEGER,
    quality_score INTEGER,
    signal_data JSONB,  -- Dados completos do sinal Wave3
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Índices para performance
CREATE INDEX IF NOT EXISTS idx_paper_positions_symbol ON paper_positions(symbol);
CREATE INDEX IF NOT EXISTS idx_paper_positions_entry_time ON paper_positions(entry_time DESC);
CREATE INDEX IF NOT EXISTS idx_paper_positions_active ON paper_positions(entry_time DESC) WHERE current_price IS NOT NULL;

-- ============================================
-- TRADES FECHADOS (PAPER TRADING)
-- ============================================

CREATE TABLE IF NOT EXISTS paper_trades (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    trade_id VARCHAR(20) UNIQUE NOT NULL,
    
    -- Ativo
    symbol VARCHAR(10) NOT NULL,
    side VARCHAR(4) CHECK (side IN ('BUY', 'SELL')),
    quantity INTEGER NOT NULL,
    
    -- Entrada
    entry_price NUMERIC(10,2) NOT NULL,
    entry_time TIMESTAMP NOT NULL,
    entry_signal JSONB,  -- Sinal original Wave3
    
    -- Saída
    exit_price NUMERIC(10,2) NOT NULL,
    exit_time TIMESTAMP NOT NULL,
    exit_reason VARCHAR(20) CHECK (exit_reason IN (
        'take_profit', 'stop_loss', 'manual', 'timeout', 
        'reversal', 'regime_change', 'trailing_stop'
    )),
    
    -- P&L
    pnl NUMERIC(12,2) NOT NULL,
    pnl_pct NUMERIC(8,4) NOT NULL,
    return_pct NUMERIC(8,4) NOT NULL,
    
    -- Métricas
    holding_days INTEGER,
    holding_hours INTEGER,
    max_favorable_excursion NUMERIC(8,4),  -- MFE: máximo lucro durante trade
    max_adverse_excursion NUMERIC(8,4),    -- MAE: máxima perda durante trade
    
    -- Wave3 metadata
    wave3_score INTEGER,
    quality_score INTEGER,
    signal_type VARCHAR(20),
    
    -- Resultado
    result VARCHAR(4) CHECK (result IN ('WIN', 'LOSS', 'BE')),
    
    -- Metadata
    created_at TIMESTAMP DEFAULT NOW()
);

-- Índices
CREATE INDEX IF NOT EXISTS idx_paper_trades_symbol ON paper_trades(symbol);
CREATE INDEX IF NOT EXISTS idx_paper_trades_entry_time ON paper_trades(entry_time DESC);
CREATE INDEX IF NOT EXISTS idx_paper_trades_exit_time ON paper_trades(exit_time DESC);
CREATE INDEX IF NOT EXISTS idx_paper_trades_result ON paper_trades(result);
CREATE INDEX IF NOT EXISTS idx_paper_trades_exit_reason ON paper_trades(exit_reason);

-- ============================================
-- DADOS ML - TRAINING DATASET
-- ============================================

CREATE TABLE IF NOT EXISTS ml_training_data (
    id SERIAL PRIMARY KEY,
    trade_id VARCHAR(20) REFERENCES paper_trades(trade_id),
    
    -- Contexto do trade
    symbol VARCHAR(10) NOT NULL,
    trade_date DATE NOT NULL,
    result VARCHAR(4) CHECK (result IN ('WIN', 'LOSS', 'BE')),
    return_pct NUMERIC(8,4),
    
    -- Wave3 metadata
    wave3_score INTEGER NOT NULL,
    quality_score INTEGER,
    signal_type VARCHAR(10),
    
    -- 103 ML Features (JSON compactado)
    features JSONB NOT NULL,
    
    -- Contexto de mercado
    market_regime VARCHAR(20),  -- trending_up, trending_down, ranging, volatile
    volatility_percentile INTEGER,  -- 0-100
    trend_strength NUMERIC(5,4),  -- ADX normalizado
    
    -- Métricas do trade
    holding_days INTEGER,
    max_favorable_excursion NUMERIC(8,4),
    max_adverse_excursion NUMERIC(8,4),
    
    -- Audit
    collected_at TIMESTAMP DEFAULT NOW(),
    
    CONSTRAINT unique_ml_trade UNIQUE(trade_id)
);

-- Índices
CREATE INDEX IF NOT EXISTS idx_ml_symbol ON ml_training_data(symbol);
CREATE INDEX IF NOT EXISTS idx_ml_date ON ml_training_data(trade_date DESC);
CREATE INDEX IF NOT EXISTS idx_ml_result ON ml_training_data(result);
CREATE INDEX IF NOT EXISTS idx_ml_regime ON ml_training_data(market_regime);

-- ============================================
-- CAPITAL TRACKING (PAPER TRADING)
-- ============================================

CREATE TABLE IF NOT EXISTS paper_capital_history (
    id SERIAL PRIMARY KEY,
    
    -- Capital
    timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    capital NUMERIC(15,2) NOT NULL,
    initial_capital NUMERIC(15,2) NOT NULL,
    
    -- P&L
    realized_pnl NUMERIC(15,2) DEFAULT 0,
    unrealized_pnl NUMERIC(15,2) DEFAULT 0,
    total_pnl NUMERIC(15,2) DEFAULT 0,
    return_pct NUMERIC(8,4) DEFAULT 0,
    
    -- Posições
    open_positions INTEGER DEFAULT 0,
    
    -- Trades
    total_trades INTEGER DEFAULT 0,
    winning_trades INTEGER DEFAULT 0,
    losing_trades INTEGER DEFAULT 0,
    win_rate NUMERIC(5,4) DEFAULT 0,
    
    -- Métricas
    sharpe_ratio NUMERIC(6,3),
    max_drawdown_pct NUMERIC(6,4),
    profit_factor NUMERIC(6,3)
);

CREATE INDEX IF NOT EXISTS idx_capital_timestamp ON paper_capital_history(timestamp DESC);

-- ============================================
-- VIEWS DE PERFORMANCE
-- ============================================

-- View: Resumo de performance
CREATE OR REPLACE VIEW paper_trading_summary AS
SELECT
    COUNT(*) as total_trades,
    SUM(CASE WHEN result = 'WIN' THEN 1 ELSE 0 END) as winning_trades,
    SUM(CASE WHEN result = 'LOSS' THEN 1 ELSE 0 END) as losing_trades,
    ROUND(SUM(CASE WHEN result = 'WIN' THEN 1 ELSE 0 END)::NUMERIC / 
          NULLIF(COUNT(*), 0) * 100, 2) as win_rate,
    ROUND(SUM(pnl), 2) as total_pnl,
    ROUND(AVG(return_pct), 4) as avg_return_pct,
    ROUND(MAX(return_pct), 4) as max_return_pct,
    ROUND(MIN(return_pct), 4) as max_drawdown_pct,
    ROUND(AVG(holding_days), 1) as avg_holding_days,
    ROUND(AVG(holding_hours), 1) as avg_holding_hours,
    
    -- Separação WIN/LOSS
    ROUND(AVG(CASE WHEN result = 'WIN' THEN return_pct END), 4) as avg_win,
    ROUND(AVG(CASE WHEN result = 'LOSS' THEN return_pct END), 4) as avg_loss,
    
    -- Profit Factor
    ROUND(
        ABS(SUM(CASE WHEN pnl > 0 THEN pnl ELSE 0 END)) / 
        NULLIF(ABS(SUM(CASE WHEN pnl < 0 THEN pnl ELSE 0 END)), 0),
        2
    ) as profit_factor,
    
    -- MFE/MAE médio
    ROUND(AVG(max_favorable_excursion), 4) as avg_mfe,
    ROUND(AVG(max_adverse_excursion), 4) as avg_mae
    
FROM paper_trades;

-- View: Performance por símbolo
CREATE OR REPLACE VIEW paper_trading_by_symbol AS
SELECT
    symbol,
    COUNT(*) as trades,
    SUM(CASE WHEN result = 'WIN' THEN 1 ELSE 0 END) as wins,
    ROUND(SUM(CASE WHEN result = 'WIN' THEN 1 ELSE 0 END)::NUMERIC / 
          NULLIF(COUNT(*), 0) * 100, 2) as win_rate,
    ROUND(SUM(pnl), 2) as total_pnl,
    ROUND(AVG(return_pct), 4) as avg_return,
    ROUND(MAX(return_pct), 4) as best_trade,
    ROUND(MIN(return_pct), 4) as worst_trade,
    ROUND(AVG(holding_days), 1) as avg_holding_days
FROM paper_trades
GROUP BY symbol
ORDER BY total_pnl DESC;

-- View: Performance por exit_reason
CREATE OR REPLACE VIEW paper_trading_by_exit_reason AS
SELECT
    exit_reason,
    COUNT(*) as trades,
    ROUND(AVG(return_pct), 4) as avg_return,
    ROUND(SUM(pnl), 2) as total_pnl,
    SUM(CASE WHEN result = 'WIN' THEN 1 ELSE 0 END) as wins,
    SUM(CASE WHEN result = 'LOSS' THEN 1 ELSE 0 END) as losses
FROM paper_trades
GROUP BY exit_reason
ORDER BY trades DESC;

-- View: Progresso coleta ML
CREATE OR REPLACE VIEW ml_collection_progress AS
SELECT
    COUNT(*) as samples_collected,
    SUM(CASE WHEN result = 'WIN' THEN 1 ELSE 0 END) as wins,
    SUM(CASE WHEN result = 'LOSS' THEN 1 ELSE 0 END) as losses,
    ROUND(SUM(CASE WHEN result = 'WIN' THEN 1 ELSE 0 END)::NUMERIC / 
          NULLIF(COUNT(*), 0) * 100, 2) as balance_pct,
    MIN(trade_date) as first_trade,
    MAX(trade_date) as last_trade,
    COUNT(DISTINCT symbol) as unique_symbols,
    CASE
        WHEN COUNT(*) < 25 THEN 'collecting_initial'
        WHEN COUNT(*) < 50 THEN 'ready_for_beta'
        WHEN COUNT(*) < 100 THEN 'ready_for_production'
        ELSE 'ready_for_advanced_ml'
    END as ml_readiness,
    
    -- Próxima meta
    CASE
        WHEN COUNT(*) < 25 THEN 25 - COUNT(*)
        WHEN COUNT(*) < 50 THEN 50 - COUNT(*)
        WHEN COUNT(*) < 100 THEN 100 - COUNT(*)
        ELSE 0
    END as trades_to_next_milestone
    
FROM ml_training_data;

-- View: Performance por quality_score
CREATE OR REPLACE VIEW paper_trading_by_quality_score AS
SELECT
    CASE
        WHEN quality_score >= 80 THEN '80-100'
        WHEN quality_score >= 70 THEN '70-79'
        WHEN quality_score >= 60 THEN '60-69'
        WHEN quality_score >= 55 THEN '55-59'
        ELSE '<55'
    END as score_range,
    COUNT(*) as trades,
    ROUND(AVG(return_pct), 4) as avg_return,
    SUM(CASE WHEN result = 'WIN' THEN 1 ELSE 0 END) as wins,
    ROUND(SUM(CASE WHEN result = 'WIN' THEN 1 ELSE 0 END)::NUMERIC / 
          NULLIF(COUNT(*), 0) * 100, 2) as win_rate
FROM paper_trades
WHERE quality_score IS NOT NULL
GROUP BY score_range
ORDER BY score_range DESC;

-- View: Equity Curve (simulado)
CREATE OR REPLACE VIEW paper_equity_curve AS
SELECT
    trade_id,
    symbol,
    exit_time as timestamp,
    pnl,
    SUM(pnl) OVER (ORDER BY exit_time) as cumulative_pnl,
    100 + (SUM(pnl) OVER (ORDER BY exit_time) / 100000.0 * 100) as equity_pct
FROM paper_trades
ORDER BY exit_time;

-- ============================================
-- FUNÇÕES AUXILIARES
-- ============================================

-- Função: Calcular Sharpe Ratio
CREATE OR REPLACE FUNCTION calculate_sharpe_ratio(risk_free_rate NUMERIC DEFAULT 0.05)
RETURNS NUMERIC AS $$
DECLARE
    avg_return NUMERIC;
    stddev_return NUMERIC;
    sharpe NUMERIC;
BEGIN
    SELECT AVG(return_pct), STDDEV(return_pct)
    INTO avg_return, stddev_return
    FROM paper_trades;
    
    IF stddev_return IS NULL OR stddev_return = 0 THEN
        RETURN NULL;
    END IF;
    
    sharpe := (avg_return - risk_free_rate) / stddev_return;
    RETURN ROUND(sharpe, 3);
END;
$$ LANGUAGE plpgsql;

-- Função: Calcular Max Drawdown
CREATE OR REPLACE FUNCTION calculate_max_drawdown()
RETURNS NUMERIC AS $$
DECLARE
    max_dd NUMERIC := 0;
    peak NUMERIC := 0;
    current_equity NUMERIC;
    dd NUMERIC;
BEGIN
    FOR current_equity IN 
        SELECT cumulative_pnl FROM paper_equity_curve ORDER BY timestamp
    LOOP
        IF current_equity > peak THEN
            peak := current_equity;
        END IF;
        
        IF peak > 0 THEN
            dd := (peak - current_equity) / peak * 100;
            IF dd > max_dd THEN
                max_dd := dd;
            END IF;
        END IF;
    END LOOP;
    
    RETURN ROUND(max_dd, 4);
END;
$$ LANGUAGE plpgsql;

-- Função: Snapshot diário de capital
CREATE OR REPLACE FUNCTION take_capital_snapshot()
RETURNS VOID AS $$
DECLARE
    current_capital NUMERIC;
    unrealized NUMERIC;
    realized NUMERIC;
    open_pos INTEGER;
    total_t INTEGER;
    wins INTEGER;
    losses INTEGER;
BEGIN
    -- Calcular unrealized P&L
    SELECT COALESCE(SUM(unrealized_pnl), 0) INTO unrealized
    FROM paper_positions;
    
    -- Calcular realized P&L
    SELECT COALESCE(SUM(pnl), 0) INTO realized
    FROM paper_trades;
    
    -- Contar posições
    SELECT COUNT(*) INTO open_pos
    FROM paper_positions;
    
    -- Contar trades
    SELECT COUNT(*) INTO total_t
    FROM paper_trades;
    
    SELECT 
        COALESCE(SUM(CASE WHEN result = 'WIN' THEN 1 ELSE 0 END), 0),
        COALESCE(SUM(CASE WHEN result = 'LOSS' THEN 1 ELSE 0 END), 0)
    INTO wins, losses
    FROM paper_trades;
    
    -- Capital atual
    current_capital := 100000.0 + realized;
    
    -- Inserir snapshot
    INSERT INTO paper_capital_history (
        capital, initial_capital, realized_pnl, unrealized_pnl, total_pnl,
        return_pct, open_positions, total_trades, winning_trades, losing_trades,
        win_rate, sharpe_ratio, max_drawdown_pct
    ) VALUES (
        current_capital,
        100000.0,
        realized,
        unrealized,
        realized + unrealized,
        (realized + unrealized) / 100000.0 * 100,
        open_pos,
        total_t,
        wins,
        losses,
        CASE WHEN total_t > 0 THEN wins::NUMERIC / total_t ELSE 0 END,
        calculate_sharpe_ratio(),
        calculate_max_drawdown()
    );
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- TRIGGER: Auto-update updated_at
-- ============================================

CREATE OR REPLACE FUNCTION update_paper_position_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_paper_positions
BEFORE UPDATE ON paper_positions
FOR EACH ROW
EXECUTE FUNCTION update_paper_position_timestamp();

-- ============================================
-- GRANTS
-- ============================================

GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO b3trading_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO b3trading_user;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO b3trading_user;

-- ============================================
-- LOG DE INICIALIZAÇÃO
-- ============================================

DO $$
BEGIN
    RAISE NOTICE '✅ Paper Trading Schema criado com sucesso!';
    RAISE NOTICE '📊 Tabelas: paper_positions, paper_trades, ml_training_data, paper_capital_history';
    RAISE NOTICE '📈 Views: paper_trading_summary, paper_trading_by_symbol, ml_collection_progress';
    RAISE NOTICE '🔧 Funções: calculate_sharpe_ratio(), calculate_max_drawdown(), take_capital_snapshot()';
END $$;
