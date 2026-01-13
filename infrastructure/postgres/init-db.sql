-- ============================================
-- B3 TRADING PLATFORM - POSTGRESQL INIT
-- ============================================
-- Banco principal para configurações e usuários

-- Extensões
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================
-- USUÁRIOS E AUTENTICAÇÃO
-- ============================================

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    name VARCHAR(100),
    is_active BOOLEAN DEFAULT true,
    is_admin BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS user_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(255) NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================
-- CONFIGURAÇÕES DE TRADING
-- ============================================

CREATE TABLE IF NOT EXISTS trading_configs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    
    -- Capital e Risco
    initial_capital DECIMAL(15, 2) DEFAULT 100000.00,
    max_risk_per_trade DECIMAL(5, 4) DEFAULT 0.02,  -- 2%
    max_daily_loss DECIMAL(5, 4) DEFAULT 0.05,       -- 5%
    max_positions INTEGER DEFAULT 5,
    
    -- Estratégia
    default_strategy VARCHAR(50) DEFAULT 'trend_following',
    default_timeframe VARCHAR(10) DEFAULT '5m',
    
    -- Símbolos permitidos
    allowed_symbols TEXT[] DEFAULT ARRAY['WINFUT', 'WDOFUT'],
    
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================
-- ESTRATÉGIAS
-- ============================================

CREATE TABLE IF NOT EXISTS strategies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    
    -- Parâmetros JSON
    default_params JSONB DEFAULT '{}',
    
    -- Performance histórica (atualizado por backtests)
    avg_return DECIMAL(8, 4),
    sharpe_ratio DECIMAL(6, 3),
    max_drawdown DECIMAL(6, 4),
    win_rate DECIMAL(5, 4),
    profit_factor DECIMAL(6, 3),
    total_trades INTEGER DEFAULT 0,
    
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Inserir estratégias padrão
INSERT INTO strategies (name, description, default_params) VALUES
('trend_following', 'Seguidor de tendência com EMA 9/21 + RSI', 
 '{"ema_fast": 9, "ema_slow": 21, "rsi_period": 14, "rsi_oversold": 30, "rsi_overbought": 70}'),
 
('mean_reversion', 'Reversão à média com Bollinger Bands', 
 '{"bb_period": 20, "bb_std": 2.0, "rsi_period": 14, "rsi_threshold": 25}'),
 
('breakout', 'Rompimento de suporte/resistência', 
 '{"lookback_period": 20, "volume_mult": 1.5, "atr_mult": 1.5}'),
 
('scalping', 'Scalping com análise de fluxo', 
 '{"tick_window": 100, "delta_threshold": 500, "time_limit_minutes": 5}'),

('macd_crossover', 'Cruzamento MACD com confirmação de volume',
 '{"macd_fast": 12, "macd_slow": 26, "macd_signal": 9, "volume_sma": 20}')

ON CONFLICT (name) DO NOTHING;

-- ============================================
-- SINAIS DE TRADING
-- ============================================

CREATE TABLE IF NOT EXISTS trading_signals (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    symbol VARCHAR(20) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    strategy VARCHAR(50) NOT NULL,
    
    signal_type VARCHAR(10) NOT NULL,  -- BUY, SELL, HOLD
    signal_strength DECIMAL(5, 4),      -- 0.0 a 1.0
    
    -- Preços sugeridos
    entry_price DECIMAL(15, 2),
    stop_loss DECIMAL(15, 2),
    take_profit DECIMAL(15, 2),
    
    -- Indicadores no momento do sinal
    indicators JSONB DEFAULT '{}',
    
    -- Status
    is_executed BOOLEAN DEFAULT false,
    executed_at TIMESTAMP WITH TIME ZONE,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_signals_symbol_time ON trading_signals(symbol, created_at DESC);
CREATE INDEX idx_signals_strategy ON trading_signals(strategy, created_at DESC);

-- ============================================
-- ORDENS (Paper e Live)
-- ============================================

CREATE TABLE IF NOT EXISTS orders (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id),
    signal_id UUID REFERENCES trading_signals(id),
    
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL,           -- BUY, SELL
    order_type VARCHAR(20) NOT NULL,     -- MARKET, LIMIT, STOP
    
    quantity INTEGER NOT NULL,
    price DECIMAL(15, 2),
    stop_price DECIMAL(15, 2),
    
    -- Status
    status VARCHAR(20) DEFAULT 'pending', -- pending, filled, partial, cancelled, rejected
    filled_quantity INTEGER DEFAULT 0,
    avg_fill_price DECIMAL(15, 2),
    
    -- Modo
    is_paper BOOLEAN DEFAULT true,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    filled_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_orders_user ON orders(user_id, created_at DESC);
CREATE INDEX idx_orders_status ON orders(status, created_at DESC);

-- ============================================
-- TRADES EXECUTADOS
-- ============================================

CREATE TABLE IF NOT EXISTS trades (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id),
    
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL,
    strategy VARCHAR(50),
    
    -- Entrada
    entry_price DECIMAL(15, 2) NOT NULL,
    entry_quantity INTEGER NOT NULL,
    entry_time TIMESTAMP WITH TIME ZONE NOT NULL,
    entry_order_id UUID REFERENCES orders(id),
    
    -- Saída (preenchido ao fechar)
    exit_price DECIMAL(15, 2),
    exit_quantity INTEGER,
    exit_time TIMESTAMP WITH TIME ZONE,
    exit_order_id UUID REFERENCES orders(id),
    exit_reason VARCHAR(50),  -- take_profit, stop_loss, manual, trailing_stop
    
    -- P&L
    gross_pnl DECIMAL(15, 2),
    commission DECIMAL(15, 2) DEFAULT 0,
    net_pnl DECIMAL(15, 2),
    return_pct DECIMAL(8, 4),
    
    -- Modo
    is_paper BOOLEAN DEFAULT true,
    
    -- Status
    status VARCHAR(20) DEFAULT 'open',  -- open, closed
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_trades_user ON trades(user_id, entry_time DESC);
CREATE INDEX idx_trades_symbol ON trades(symbol, entry_time DESC);
CREATE INDEX idx_trades_status ON trades(status, entry_time DESC);

-- ============================================
-- BACKTEST RESULTS
-- ============================================

CREATE TABLE IF NOT EXISTS backtest_results (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id),
    
    -- Configuração
    strategy VARCHAR(50) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    params JSONB DEFAULT '{}',
    
    -- Métricas
    initial_capital DECIMAL(15, 2),
    final_capital DECIMAL(15, 2),
    total_return DECIMAL(8, 4),
    annual_return DECIMAL(8, 4),
    sharpe_ratio DECIMAL(6, 3),
    sortino_ratio DECIMAL(6, 3),
    max_drawdown DECIMAL(6, 4),
    win_rate DECIMAL(5, 4),
    profit_factor DECIMAL(6, 3),
    total_trades INTEGER,
    winning_trades INTEGER,
    losing_trades INTEGER,
    avg_win DECIMAL(15, 2),
    avg_loss DECIMAL(15, 2),
    
    -- Detalhes (lista de trades)
    trades_detail JSONB DEFAULT '[]',
    equity_curve JSONB DEFAULT '[]',
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_backtest_strategy ON backtest_results(strategy, created_at DESC);
CREATE INDEX idx_backtest_symbol ON backtest_results(symbol, created_at DESC);

-- ============================================
-- ALERTAS
-- ============================================

CREATE TABLE IF NOT EXISTS alerts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id),
    
    symbol VARCHAR(20) NOT NULL,
    alert_type VARCHAR(50) NOT NULL,  -- price_above, price_below, indicator, signal
    
    condition JSONB NOT NULL,
    message TEXT,
    
    is_active BOOLEAN DEFAULT true,
    is_triggered BOOLEAN DEFAULT false,
    triggered_at TIMESTAMP WITH TIME ZONE,
    
    -- Notificação
    notify_telegram BOOLEAN DEFAULT false,
    notify_discord BOOLEAN DEFAULT false,
    notify_email BOOLEAN DEFAULT false,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================
-- WATCHLIST
-- ============================================

CREATE TABLE IF NOT EXISTS watchlists (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id),
    name VARCHAR(100) NOT NULL,
    symbols TEXT[] DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================
-- FUNÇÕES ÚTEIS
-- ============================================

-- Função para atualizar updated_at automaticamente
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers para updated_at
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_trading_configs_updated_at BEFORE UPDATE ON trading_configs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_strategies_updated_at BEFORE UPDATE ON strategies
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_orders_updated_at BEFORE UPDATE ON orders
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_trades_updated_at BEFORE UPDATE ON trades
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- USUÁRIO PADRÃO (para desenvolvimento)
-- ============================================

INSERT INTO users (email, password_hash, name, is_admin) 
VALUES (
    'admin@b3trading.local',
    crypt('admin123', gen_salt('bf')),
    'Administrador',
    true
) ON CONFLICT (email) DO NOTHING;

-- Config padrão para admin
INSERT INTO trading_configs (user_id, name, initial_capital, allowed_symbols)
SELECT id, 'Config Padrão', 100000.00, ARRAY['WINFUT', 'WDOFUT', 'PETR4', 'VALE3']
FROM users WHERE email = 'admin@b3trading.local'
ON CONFLICT DO NOTHING;

-- ============================================
-- GRANTS
-- ============================================

GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO b3trading_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO b3trading_user;

-- Log de inicialização
DO $$
BEGIN
    RAISE NOTICE '✅ B3 Trading Platform - PostgreSQL inicializado com sucesso!';
END $$;
