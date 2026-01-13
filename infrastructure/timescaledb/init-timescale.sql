-- ============================================
-- B3 TRADING PLATFORM - TIMESCALEDB INIT
-- ============================================
-- Banco de séries temporais para dados de mercado

-- Extensão TimescaleDB
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- ============================================
-- DADOS OHLCV (Candles)
-- ============================================

CREATE TABLE IF NOT EXISTS ohlcv_data (
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    
    open DECIMAL(15, 2) NOT NULL,
    high DECIMAL(15, 2) NOT NULL,
    low DECIMAL(15, 2) NOT NULL,
    close DECIMAL(15, 2) NOT NULL,
    volume BIGINT NOT NULL,
    
    -- Campos extras
    trades_count INTEGER,
    vwap DECIMAL(15, 2),
    
    PRIMARY KEY (time, symbol, timeframe)
);

-- Converter para Hypertable
SELECT create_hypertable('ohlcv_data', 'time', 
    chunk_time_interval => INTERVAL '1 week',
    if_not_exists => TRUE
);

-- Índices
CREATE INDEX IF NOT EXISTS idx_ohlcv_symbol_time ON ohlcv_data(symbol, time DESC);
CREATE INDEX IF NOT EXISTS idx_ohlcv_timeframe ON ohlcv_data(timeframe, time DESC);

-- ============================================
-- TICKS (Dados de alta frequência)
-- ============================================

CREATE TABLE IF NOT EXISTS tick_data (
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    
    price DECIMAL(15, 2) NOT NULL,
    volume INTEGER NOT NULL,
    side VARCHAR(4),  -- BUY, SELL
    
    -- Agressor
    aggressor VARCHAR(4),  -- BID, ASK
    
    PRIMARY KEY (time, symbol)
);

-- Converter para Hypertable (chunks menores para ticks)
SELECT create_hypertable('tick_data', 'time',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

CREATE INDEX IF NOT EXISTS idx_tick_symbol ON tick_data(symbol, time DESC);

-- ============================================
-- BOOK DE OFERTAS (Snapshot)
-- ============================================

CREATE TABLE IF NOT EXISTS order_book (
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    
    -- Melhor bid/ask
    bid_price DECIMAL(15, 2),
    bid_size INTEGER,
    ask_price DECIMAL(15, 2),
    ask_size INTEGER,
    
    -- Spread
    spread DECIMAL(10, 2),
    spread_pct DECIMAL(8, 4),
    
    -- Profundidade (top 5 níveis serializado)
    depth_json JSONB,
    
    PRIMARY KEY (time, symbol)
);

SELECT create_hypertable('order_book', 'time',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

-- ============================================
-- INDICADORES TÉCNICOS PRÉ-CALCULADOS
-- ============================================

CREATE TABLE IF NOT EXISTS technical_indicators (
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    
    -- Médias Móveis
    ema_9 DECIMAL(15, 2),
    ema_21 DECIMAL(15, 2),
    ema_50 DECIMAL(15, 2),
    ema_200 DECIMAL(15, 2),
    sma_20 DECIMAL(15, 2),
    
    -- RSI
    rsi_14 DECIMAL(6, 2),
    
    -- MACD
    macd_line DECIMAL(15, 4),
    macd_signal DECIMAL(15, 4),
    macd_histogram DECIMAL(15, 4),
    
    -- Bollinger Bands
    bb_upper DECIMAL(15, 2),
    bb_middle DECIMAL(15, 2),
    bb_lower DECIMAL(15, 2),
    bb_width DECIMAL(8, 4),
    
    -- ATR (Volatilidade)
    atr_14 DECIMAL(15, 2),
    
    -- Volume
    volume_sma_20 DECIMAL(20, 2),
    volume_ratio DECIMAL(8, 4),
    
    -- ADX (Força da tendência)
    adx_14 DECIMAL(6, 2),
    di_plus DECIMAL(6, 2),
    di_minus DECIMAL(6, 2),
    
    -- Stochastic
    stoch_k DECIMAL(6, 2),
    stoch_d DECIMAL(6, 2),
    
    PRIMARY KEY (time, symbol, timeframe)
);

SELECT create_hypertable('technical_indicators', 'time',
    chunk_time_interval => INTERVAL '1 week',
    if_not_exists => TRUE
);

CREATE INDEX IF NOT EXISTS idx_indicators_symbol ON technical_indicators(symbol, timeframe, time DESC);

-- ============================================
-- CONTINUOUS AGGREGATES (Views materializadas)
-- ============================================

-- Agregação horária automática a partir de 1m
CREATE MATERIALIZED VIEW IF NOT EXISTS ohlcv_1h
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', time) AS time,
    symbol,
    '1h' AS timeframe,
    first(open, time) AS open,
    max(high) AS high,
    min(low) AS low,
    last(close, time) AS close,
    sum(volume) AS volume,
    count(*) AS candles_count
FROM ohlcv_data
WHERE timeframe = '1m'
GROUP BY time_bucket('1 hour', time), symbol;

-- Agregação diária
CREATE MATERIALIZED VIEW IF NOT EXISTS ohlcv_1d
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 day', time) AS time,
    symbol,
    '1d' AS timeframe,
    first(open, time) AS open,
    max(high) AS high,
    min(low) AS low,
    last(close, time) AS close,
    sum(volume) AS volume,
    count(*) AS candles_count
FROM ohlcv_data
WHERE timeframe = '1m'
GROUP BY time_bucket('1 day', time), symbol;

-- Políticas de refresh
SELECT add_continuous_aggregate_policy('ohlcv_1h',
    start_offset => INTERVAL '3 hours',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour',
    if_not_exists => TRUE
);

SELECT add_continuous_aggregate_policy('ohlcv_1d',
    start_offset => INTERVAL '3 days',
    end_offset => INTERVAL '1 day',
    schedule_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

-- ============================================
-- POLÍTICAS DE RETENÇÃO
-- ============================================

-- Ticks: manter apenas 7 dias (muito volume)
SELECT add_retention_policy('tick_data', INTERVAL '7 days', if_not_exists => TRUE);

-- Order book: 7 dias
SELECT add_retention_policy('order_book', INTERVAL '7 days', if_not_exists => TRUE);

-- OHLCV 1m: 30 dias
-- OHLCV outros: 2 anos (configurar manualmente se necessário)

-- Indicadores: 1 ano
SELECT add_retention_policy('technical_indicators', INTERVAL '1 year', if_not_exists => TRUE);

-- ============================================
-- COMPRESSÃO (economia de espaço)
-- ============================================

-- Habilitar compressão para OHLCV após 7 dias
ALTER TABLE ohlcv_data SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'symbol,timeframe'
);

SELECT add_compression_policy('ohlcv_data', INTERVAL '7 days', if_not_exists => TRUE);

-- Compressão para indicadores após 30 dias
ALTER TABLE technical_indicators SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'symbol,timeframe'
);

SELECT add_compression_policy('technical_indicators', INTERVAL '30 days', if_not_exists => TRUE);

-- ============================================
-- FUNÇÕES ÚTEIS
-- ============================================

-- Função para obter último preço
CREATE OR REPLACE FUNCTION get_last_price(p_symbol VARCHAR)
RETURNS TABLE(symbol VARCHAR, price DECIMAL, time TIMESTAMPTZ) AS $$
BEGIN
    RETURN QUERY
    SELECT o.symbol, o.close, o.time
    FROM ohlcv_data o
    WHERE o.symbol = p_symbol
    ORDER BY o.time DESC
    LIMIT 1;
END;
$$ LANGUAGE plpgsql;

-- Função para calcular retorno
CREATE OR REPLACE FUNCTION calculate_return(
    p_symbol VARCHAR,
    p_timeframe VARCHAR,
    p_periods INTEGER
)
RETURNS DECIMAL AS $$
DECLARE
    v_first_close DECIMAL;
    v_last_close DECIMAL;
BEGIN
    SELECT close INTO v_first_close
    FROM ohlcv_data
    WHERE symbol = p_symbol AND timeframe = p_timeframe
    ORDER BY time ASC
    LIMIT 1 OFFSET p_periods - 1;
    
    SELECT close INTO v_last_close
    FROM ohlcv_data
    WHERE symbol = p_symbol AND timeframe = p_timeframe
    ORDER BY time DESC
    LIMIT 1;
    
    IF v_first_close IS NULL OR v_first_close = 0 THEN
        RETURN NULL;
    END IF;
    
    RETURN ((v_last_close - v_first_close) / v_first_close) * 100;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- DADOS INICIAIS (para teste)
-- ============================================

-- Inserir alguns dados de exemplo para WINFUT
INSERT INTO ohlcv_data (time, symbol, timeframe, open, high, low, close, volume)
SELECT 
    generate_series(
        NOW() - INTERVAL '7 days',
        NOW(),
        INTERVAL '5 minutes'
    ) AS time,
    'WINFUT' AS symbol,
    '5m' AS timeframe,
    128000 + (random() * 1000)::INTEGER AS open,
    128500 + (random() * 1000)::INTEGER AS high,
    127500 + (random() * 1000)::INTEGER AS low,
    128000 + (random() * 1000)::INTEGER AS close,
    (random() * 10000)::INTEGER AS volume
ON CONFLICT DO NOTHING;

-- ============================================
-- GRANTS
-- ============================================

GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO b3trading_ts;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO b3trading_ts;

-- Log de inicialização
DO $$
BEGIN
    RAISE NOTICE '✅ B3 Trading Platform - TimescaleDB inicializado com sucesso!';
END $$;
