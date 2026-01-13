"""
B3 Trading Platform - Execution Engine
======================================
API principal para backtesting, paper trading e execução.
"""

import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Optional, List

import asyncpg
import redis.asyncio as redis
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from loguru import logger

from .strategies import StrategyManager, get_recommended_strategy, detect_market_regime
from .backtest import BacktestEngine
from .paper_trading import PaperTradingManager


# ============================================
# CONFIGURATION
# ============================================

class Settings:
    # PostgreSQL
    POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", 5432))
    POSTGRES_DB = os.getenv("POSTGRES_DB", "b3trading_db")
    POSTGRES_USER = os.getenv("POSTGRES_USER", "b3trading_user")
    POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "b3trading_pass")
    
    # TimescaleDB
    TIMESCALE_HOST = os.getenv("TIMESCALE_HOST", "localhost")
    TIMESCALE_PORT = int(os.getenv("TIMESCALE_PORT", 5432))
    TIMESCALE_DB = os.getenv("TIMESCALE_DB", "b3trading_market")
    TIMESCALE_USER = os.getenv("TIMESCALE_USER", "b3trading_ts")
    TIMESCALE_PASSWORD = os.getenv("TIMESCALE_PASSWORD", "b3trading_ts_pass")
    
    # Redis
    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
    
    # Trading
    INITIAL_CAPITAL = float(os.getenv("INITIAL_CAPITAL", 100000))
    ENABLE_PAPER_TRADING = os.getenv("ENABLE_PAPER_TRADING", "true").lower() == "true"

settings = Settings()


# ============================================
# DATABASE CONNECTIONS
# ============================================

db_pool: Optional[asyncpg.Pool] = None
ts_pool: Optional[asyncpg.Pool] = None
redis_client: Optional[redis.Redis] = None


async def init_db():
    """Inicializa conexões com bancos de dados."""
    global db_pool, ts_pool, redis_client
    
    logger.info("🔌 Conectando aos bancos de dados...")
    
    # PostgreSQL
    db_pool = await asyncpg.create_pool(
        host=settings.POSTGRES_HOST,
        port=settings.POSTGRES_PORT,
        database=settings.POSTGRES_DB,
        user=settings.POSTGRES_USER,
        password=settings.POSTGRES_PASSWORD,
        min_size=2,
        max_size=10
    )
    logger.info("✅ PostgreSQL conectado")
    
    # TimescaleDB
    ts_pool = await asyncpg.create_pool(
        host=settings.TIMESCALE_HOST,
        port=settings.TIMESCALE_PORT,
        database=settings.TIMESCALE_DB,
        user=settings.TIMESCALE_USER,
        password=settings.TIMESCALE_PASSWORD,
        min_size=2,
        max_size=10
    )
    logger.info("✅ TimescaleDB conectado")
    
    # Redis
    redis_client = redis.Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        decode_responses=True
    )
    await redis_client.ping()
    logger.info("✅ Redis conectado")


async def close_db():
    """Fecha conexões."""
    global db_pool, ts_pool, redis_client
    
    if db_pool:
        await db_pool.close()
    if ts_pool:
        await ts_pool.close()
    if redis_client:
        await redis_client.close()
    
    logger.info("🔌 Conexões fechadas")


# ============================================
# FASTAPI APP
# ============================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle do app."""
    await init_db()
    logger.info("🚀 B3 Trading Platform - Execution Engine iniciado!")
    yield
    await close_db()
    logger.info("👋 Execution Engine encerrado")


app = FastAPI(
    title="B3 Trading Platform - Execution Engine",
    description="API para backtesting, paper trading e execução de estratégias",
    version="1.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================
# MODELS
# ============================================

class HealthResponse(BaseModel):
    status: str
    timestamp: datetime
    services: dict


class BacktestRequest(BaseModel):
    strategy: str = Field(..., description="Nome da estratégia")
    symbol: str = Field(default="WINFUT", description="Símbolo (WINFUT, WDOFUT, PETR4)")
    timeframe: str = Field(default="5m", description="Timeframe (1m, 5m, 15m, 1h, 1d)")
    start_date: str = Field(..., description="Data inicial (YYYY-MM-DD)")
    end_date: str = Field(..., description="Data final (YYYY-MM-DD)")
    initial_capital: float = Field(default=100000, description="Capital inicial (R$)")
    params: Optional[dict] = Field(default=None, description="Parâmetros da estratégia")


class BacktestResponse(BaseModel):
    success: bool
    strategy: str
    symbol: str
    timeframe: str
    period: str
    
    # Métricas principais
    initial_capital: float
    final_capital: float
    total_return: float
    total_return_pct: float
    
    # Performance
    sharpe_ratio: Optional[float]
    sortino_ratio: Optional[float]
    max_drawdown: float
    max_drawdown_pct: float
    
    # Trades
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    profit_factor: Optional[float]
    avg_win: float
    avg_loss: float
    
    # Detalhes
    trades: Optional[List[dict]] = None
    equity_curve: Optional[List[dict]] = None


class SignalResponse(BaseModel):
    symbol: str
    timeframe: str
    signal: str  # BUY, SELL, HOLD
    strength: float
    strategy: str
    entry_price: Optional[float]
    stop_loss: Optional[float]
    take_profit: Optional[float]
    timestamp: datetime
    indicators: dict


class PaperTradeRequest(BaseModel):
    symbol: str
    side: str  # BUY, SELL
    quantity: int
    order_type: str = "MARKET"  # MARKET, LIMIT, STOP
    price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None


# ============================================
# ENDPOINTS
# ============================================

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Verifica saúde dos serviços."""
    services = {
        "postgres": "unknown",
        "timescaledb": "unknown",
        "redis": "unknown"
    }
    
    # Check PostgreSQL
    try:
        async with db_pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
            services["postgres"] = "healthy"
    except Exception as e:
        services["postgres"] = f"unhealthy: {str(e)}"
    
    # Check TimescaleDB
    try:
        async with ts_pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
            services["timescaledb"] = "healthy"
    except Exception as e:
        services["timescaledb"] = f"unhealthy: {str(e)}"
    
    # Check Redis
    try:
        await redis_client.ping()
        services["redis"] = "healthy"
    except Exception as e:
        services["redis"] = f"unhealthy: {str(e)}"
    
    all_healthy = all(s == "healthy" for s in services.values())
    
    return HealthResponse(
        status="healthy" if all_healthy else "degraded",
        timestamp=datetime.now(),
        services=services
    )


@app.get("/api/strategies")
async def list_strategies():
    """Lista estratégias disponíveis."""
    # Primeiro, listar estratégias do código (local)
    manager = StrategyManager()
    local_strategies = manager.list_strategies()
    
    # Buscar estatísticas do banco de dados
    db_stats = {}
    try:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT name, sharpe_ratio, max_drawdown, win_rate, total_trades
                FROM strategies
                WHERE is_active = true
            """)
            for row in rows:
                db_stats[row['name']] = dict(row)
    except Exception as e:
        logger.warning(f"Erro ao buscar stats do banco: {e}")
    
    # Combinar informações
    strategies = []
    for strat in local_strategies:
        stats = db_stats.get(strat['id'], {})
        strat['db_stats'] = stats
        strategies.append(strat)
    
    return {
        "strategies": strategies,
        "total": len(strategies)
    }


@app.get("/api/strategies/{strategy_name}")
async def get_strategy_info(strategy_name: str):
    """Retorna informações detalhadas de uma estratégia."""
    try:
        info = StrategyManager.get_strategy_description(strategy_name)
        return info
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/market/regime")
async def get_market_regime(
    symbol: str = Query(default="WINFUT"),
    timeframe: str = Query(default="15m")
):
    """Detecta o regime de mercado atual (PASSO 8)."""
    import pandas as pd
    
    # Buscar últimos dados
    async with ts_pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT time, open, high, low, close, volume
            FROM ohlcv_data
            WHERE symbol = $1 AND timeframe = $2
            ORDER BY time DESC
            LIMIT 100
        """, symbol, timeframe)
    
    if len(rows) < 50:
        raise HTTPException(
            status_code=400,
            detail=f"Dados insuficientes para {symbol}"
        )
    
    # Converter para DataFrame
    data = [dict(row) for row in reversed(rows)]
    df = pd.DataFrame(data)
    
    # Detectar regime
    regime = detect_market_regime(df)
    recommended = get_recommended_strategy(regime)
    
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "regime": regime,
        "recommended_strategies": recommended,
        "timestamp": datetime.now()
    }


@app.post("/api/backtest/run", response_model=BacktestResponse)
async def run_backtest(request: BacktestRequest):
    """Executa backtest de uma estratégia."""
    logger.info(f"📊 Backtest: {request.strategy} em {request.symbol} ({request.start_date} a {request.end_date})")
    
    # Buscar dados OHLCV
    async with ts_pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT time, open, high, low, close, volume
            FROM ohlcv_data
            WHERE symbol = $1 
              AND timeframe = $2
              AND time >= $3
              AND time <= $4
            ORDER BY time ASC
        """, request.symbol, request.timeframe, 
            datetime.strptime(request.start_date, "%Y-%m-%d"),
            datetime.strptime(request.end_date, "%Y-%m-%d") + timedelta(days=1))
    
    if len(rows) < 100:
        raise HTTPException(
            status_code=400,
            detail=f"Dados insuficientes: {len(rows)} candles. Mínimo: 100"
        )
    
    # Converter para lista de dicts
    data = [dict(row) for row in rows]
    
    # Executar backtest
    engine = BacktestEngine(
        strategy_name=request.strategy,
        initial_capital=request.initial_capital,
        params=request.params
    )
    
    result = await engine.run(data)
    
    # Salvar resultado no banco (com tratamento de valores None e limites)
    # win_rate: DECIMAL(5,4) max = 0.9999, mas pode vir como 100.0 (porcentagem)
    win_rate = result["win_rate"]
    if win_rate > 1:  # Se veio como porcentagem, converter
        win_rate = win_rate / 100.0
    win_rate = min(0.9999, max(0, win_rate))
    
    # max_drawdown: DECIMAL(6,4) max = 99.9999
    max_drawdown = result["max_drawdown_pct"]
    if max_drawdown is not None:
        max_drawdown = min(99.9999, max(-99.9999, max_drawdown / 100.0 if max_drawdown > 1 else max_drawdown))
    
    # total_return: DECIMAL(8,4) max = 9999.9999
    total_return = result["total_return_pct"]
    if total_return is not None:
        total_return = min(9999.9999, max(-9999.9999, total_return / 100.0 if abs(total_return) > 100 else total_return))
    
    profit_factor = result.get("profit_factor")
    if profit_factor is not None:
        profit_factor = min(999.99, max(-999.99, profit_factor))
    
    sharpe_ratio = result.get("sharpe_ratio")
    if sharpe_ratio is not None:
        sharpe_ratio = min(99.99, max(-99.99, sharpe_ratio))
    
    async with db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO backtest_results 
            (strategy, symbol, timeframe, start_date, end_date, params,
             initial_capital, final_capital, total_return, sharpe_ratio,
             max_drawdown, win_rate, profit_factor, total_trades,
             winning_trades, losing_trades, avg_win, avg_loss)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18)
        """, 
            request.strategy, request.symbol, request.timeframe,
            datetime.strptime(request.start_date, "%Y-%m-%d").date(),
            datetime.strptime(request.end_date, "%Y-%m-%d").date(),
            str(request.params or {}),
            request.initial_capital, result["final_capital"],
            total_return, sharpe_ratio,
            max_drawdown, win_rate,
            profit_factor, result["total_trades"],
            result["winning_trades"], result["losing_trades"],
            result["avg_win"], result["avg_loss"]
        )
    
    logger.info(f"✅ Backtest concluído: {result['total_return_pct']:.2f}% return, "
                f"{result['total_trades']} trades, {result['win_rate']:.1f}% win rate")
    
    return BacktestResponse(
        success=True,
        strategy=request.strategy,
        symbol=request.symbol,
        timeframe=request.timeframe,
        period=f"{request.start_date} a {request.end_date}",
        **result
    )


@app.get("/api/signals/{symbol}", response_model=SignalResponse)
async def get_signal(
    symbol: str,
    timeframe: str = Query(default="5m"),
    strategy: str = Query(default="trend_following")
):
    """Obtém sinal atual para um símbolo."""
    
    # Buscar últimos candles
    async with ts_pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT time, open, high, low, close, volume
            FROM ohlcv_data
            WHERE symbol = $1 AND timeframe = $2
            ORDER BY time DESC
            LIMIT 200
        """, symbol, timeframe)
    
    if len(rows) < 50:
        raise HTTPException(
            status_code=400,
            detail=f"Dados insuficientes para {symbol}"
        )
    
    # Reverter ordem (mais antigo primeiro)
    data = [dict(row) for row in reversed(rows)]
    
    # Gerar sinal
    manager = StrategyManager()
    signal = await manager.generate_signal(strategy, data)
    
    return SignalResponse(
        symbol=symbol,
        timeframe=timeframe,
        **signal
    )


@app.get("/api/signals/scan")
async def scan_signals(
    symbols: str = Query(default="WINFUT,WDOFUT"),
    timeframe: str = Query(default="5m"),
    strategy: str = Query(default="trend_following")
):
    """Escaneia múltiplos símbolos por sinais."""
    symbol_list = [s.strip() for s in symbols.split(",")]
    results = []
    
    for symbol in symbol_list:
        try:
            signal = await get_signal(symbol, timeframe, strategy)
            results.append(signal.model_dump())
        except Exception as e:
            results.append({
                "symbol": symbol,
                "error": str(e)
            })
    
    return {
        "scan_time": datetime.now(),
        "timeframe": timeframe,
        "strategy": strategy,
        "results": results
    }


@app.post("/api/adaptive-signal/{symbol}")
async def adaptive_signal(
    symbol: str,
    timeframe: str = Query("1d", description="Timeframe (1m, 5m, 15m, 1h, 1d)"),
    lookback: int = Query(200, description="Número de candles para análise")
):
    """
    Endpoint adaptativo que detecta regime de mercado e seleciona a estratégia ideal.
    
    PASSO 8 - Execução adaptativa baseada em regime de mercado.
    """
    try:
        # Buscar dados históricos
        async with ts_pool.acquire() as conn:
            query = """
                SELECT time, open, high, low, close, volume
                FROM ohlcv_data
                WHERE symbol = $1 AND timeframe = $2
                ORDER BY time DESC
                LIMIT $3
            """
            rows = await conn.fetch(query, symbol, timeframe, lookback)
        
        if not rows:
            raise HTTPException(
                status_code=404,
                detail=f"Nenhum dado encontrado para {symbol} no timeframe {timeframe}"
            )
        
        # Converter para DataFrame
        import pandas as pd
        df = pd.DataFrame([dict(r) for r in rows])
        
        # Converter Decimal para float
        for col in ['open', 'high', 'low', 'close', 'volume']:
            if col in df.columns:
                df[col] = df[col].astype(float)
        
        df = df.sort_values('time').reset_index(drop=True)
        
        # Detectar regime de mercado
        regime = detect_market_regime(df)
        logger.info(f"📊 Regime detectado para {symbol}: {regime}")
        
        # Obter estratégias recomendadas
        recommended = get_recommended_strategy(regime)
        strategy_name = recommended[0]  # Pega a primeira recomendada
        
        # Instanciar e executar estratégia
        strategy_manager = StrategyManager()
        strategy = strategy_manager.get_strategy(strategy_name)
        result_df = strategy.run(df)
        
        # Pegar último sinal
        last_idx = len(result_df) - 1
        current_signal = result_df.loc[last_idx]
        
        # Helper para converter valores float para JSON-safe
        import math
        def safe_float(value, default=0.0):
            """Converte para float seguro para JSON (sem NaN/Inf)."""
            try:
                val = float(value)
                if math.isnan(val) or math.isinf(val):
                    return default
                return val
            except (ValueError, TypeError):
                return default
        
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "timestamp": datetime.now(),
            "market_regime": regime,
            "selected_strategy": strategy_name,
            "recommended_strategies": recommended,
            "signal": {
                "action": current_signal.get('signal', 'hold'),
                "strength": safe_float(current_signal.get('signal_strength', 0.0)),
                "price": safe_float(current_signal['close']),
                "stop_loss": safe_float(current_signal.get('stop_loss', 0.0)),
                "take_profit": safe_float(current_signal.get('take_profit', 0.0))
            },
            "market_context": {
                "adx": safe_float(result_df['adx'].iloc[-1]) if 'adx' in result_df.columns else None,
                "atr": safe_float(result_df['atr'].iloc[-1]) if 'atr' in result_df.columns else None,
                "rsi": safe_float(result_df['rsi'].iloc[-1]) if 'rsi' in result_df.columns else None,
                "volume_avg": safe_float(result_df['volume'].tail(20).mean())
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Erro em adaptive_signal: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/backtest/compare")
async def compare_strategies(
    symbol: str = Query(..., description="Símbolo do ativo"),
    start_date: str = Query(..., description="Data inicial (YYYY-MM-DD)"),
    end_date: str = Query(..., description="Data final (YYYY-MM-DD)"),
    timeframe: str = Query("1d", description="Timeframe"),
    strategies: List[str] = Query(..., description="Lista de estratégias para comparar"),
    initial_capital: float = Query(100000, description="Capital inicial")
):
    """
    Compara múltiplas estratégias executando backtests paralelos.
    
    Retorna comparação detalhada de performance entre estratégias.
    """
    try:
        # Validar estratégias
        strategy_manager = StrategyManager()
        available = [s['name'] for s in strategy_manager.list_strategies()]
        
        invalid = [s for s in strategies if s not in available]
        if invalid:
            raise HTTPException(
                status_code=400,
                detail=f"Estratégias inválidas: {invalid}. Disponíveis: {available}"
            )
        
        # Buscar dados históricos
        async with ts_pool.acquire() as conn:
            query = """
                SELECT time, open, high, low, close, volume
                FROM ohlcv_data
                WHERE symbol = $1 
                AND timeframe = $2
                AND time BETWEEN $3 AND $4
                ORDER BY time ASC
            """
            rows = await conn.fetch(
                query, 
                symbol, 
                timeframe,
                datetime.fromisoformat(start_date),
                datetime.fromisoformat(end_date)
            )
        
        if not rows:
            raise HTTPException(
                status_code=404,
                detail=f"Nenhum dado encontrado para {symbol} no período especificado"
            )
        
        import pandas as pd
        df = pd.DataFrame([dict(r) for r in rows])
        
        # Converter Decimal para float
        for col in ['open', 'high', 'low', 'close', 'volume']:
            if col in df.columns:
                df[col] = df[col].astype(float)
        
        # Executar backtests para cada estratégia
        results = []
        
        for strategy_name in strategies:
            logger.info(f"🔄 Executando backtest para {strategy_name}...")
            
            # Criar engine específico para cada estratégia
            backtest_engine = BacktestEngine(
                strategy_name=strategy_name,
                initial_capital=initial_capital
            )
            
            # Executar backtest com dados históricos
            backtest_result = await backtest_engine.run([dict(r) for r in rows])
            
            results.append({
                "strategy": strategy_name,
                "metrics": {
                    "total_return": backtest_result['total_return'],
                    "sharpe_ratio": backtest_result['sharpe_ratio'],
                    "max_drawdown": backtest_result['max_drawdown'],
                    "win_rate": backtest_result['win_rate'],
                    "total_trades": backtest_result['total_trades'],
                    "profit_factor": backtest_result['profit_factor'],
                    "final_capital": backtest_result['final_capital']
                },
                "trades": backtest_result['trades']
            })
        
        # Ranquear estratégias por Sharpe Ratio
        results_sorted = sorted(
            results, 
            key=lambda x: x['metrics']['sharpe_ratio'], 
            reverse=True
        )
        
        return {
            "comparison": {
                "symbol": symbol,
                "timeframe": timeframe,
                "period": {
                    "start": start_date,
                    "end": end_date
                },
                "initial_capital": initial_capital,
                "strategies_tested": len(strategies)
            },
            "ranking": results_sorted,
            "best_strategy": results_sorted[0]['strategy'] if results_sorted else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erro em compare_strategies: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# PAPER TRADING ENDPOINTS
# ============================================

paper_manager = PaperTradingManager(settings.INITIAL_CAPITAL)


@app.get("/api/paper/status")
async def paper_status():
    """Status do paper trading."""
    return paper_manager.get_status()


@app.post("/api/paper/order")
async def paper_order(request: PaperTradeRequest):
    """Executa ordem em paper trading."""
    if not settings.ENABLE_PAPER_TRADING:
        raise HTTPException(status_code=400, detail="Paper trading desabilitado")
    
    result = await paper_manager.execute_order(
        symbol=request.symbol,
        side=request.side,
        quantity=request.quantity,
        order_type=request.order_type,
        price=request.price,
        stop_loss=request.stop_loss,
        take_profit=request.take_profit
    )
    
    return result


@app.get("/api/paper/positions")
async def paper_positions():
    """Lista posições abertas em paper trading."""
    return paper_manager.get_positions()


@app.get("/api/paper/history")
async def paper_history():
    """Histórico de trades em paper trading."""
    return paper_manager.get_trade_history()


@app.post("/api/paper/close/{position_id}")
async def paper_close_position(position_id: str):
    """Fecha posição específica."""
    result = await paper_manager.close_position(position_id)
    return result


@app.post("/api/paper/reset")
async def paper_reset():
    """Reseta paper trading."""
    paper_manager.reset(settings.INITIAL_CAPITAL)
    return {"message": "Paper trading resetado", "capital": settings.INITIAL_CAPITAL}


# ============================================
# MARKET DATA ENDPOINTS
# ============================================

@app.get("/api/data/{symbol}/ohlcv")
async def get_ohlcv(
    symbol: str,
    timeframe: str = Query(default="5m"),
    limit: int = Query(default=500, le=2000)
):
    """Retorna dados OHLCV."""
    async with ts_pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT time, open, high, low, close, volume
            FROM ohlcv_data
            WHERE symbol = $1 AND timeframe = $2
            ORDER BY time DESC
            LIMIT $3
        """, symbol, timeframe, limit)
    
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "count": len(rows),
        "data": [dict(row) for row in reversed(rows)]
    }


@app.get("/api/data/{symbol}/indicators")
async def get_indicators(
    symbol: str,
    timeframe: str = Query(default="5m"),
    limit: int = Query(default=100, le=500)
):
    """Retorna indicadores técnicos."""
    async with ts_pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT *
            FROM technical_indicators
            WHERE symbol = $1 AND timeframe = $2
            ORDER BY time DESC
            LIMIT $3
        """, symbol, timeframe, limit)
    
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "count": len(rows),
        "data": [dict(row) for row in reversed(rows)]
    }


@app.get("/api/data/symbols")
async def list_symbols():
    """Lista símbolos disponíveis."""
    async with ts_pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT DISTINCT symbol, 
                   MIN(time) as first_date,
                   MAX(time) as last_date,
                   COUNT(*) as candles
            FROM ohlcv_data
            GROUP BY symbol
            ORDER BY symbol
        """)
    
    return {
        "symbols": [dict(row) for row in rows]
    }


# ============================================
# STARTUP MESSAGE
# ============================================

@app.on_event("startup")
async def startup_message():
    """Mensagem de inicialização."""
    logger.info("""
    ╔══════════════════════════════════════════════════════════════╗
    ║       🇧🇷 B3 TRADING PLATFORM - EXECUTION ENGINE              ║
    ╠══════════════════════════════════════════════════════════════╣
    ║  API:          http://localhost:3008                         ║
    ║  Docs:         http://localhost:3008/docs                    ║
    ║  Paper Trade:  {'ENABLED' if settings.ENABLE_PAPER_TRADING else 'DISABLED':10}                          ║
    ║  Capital:      R$ {settings.INITIAL_CAPITAL:,.2f}                        ║
    ╚══════════════════════════════════════════════════════════════╝
    """)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3008)
