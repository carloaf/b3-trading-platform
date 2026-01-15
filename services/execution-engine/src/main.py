"""
B3 Trading Platform - Execution Engine
======================================
API principal para backtesting, paper trading e execução.
"""

import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Optional, List, Dict

import asyncpg
import redis.asyncio as redis
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from loguru import logger

from .strategies import StrategyManager, get_recommended_strategy, detect_market_regime
from .backtest import BacktestEngine
from .paper_trading import PaperTradingManager
from .walk_forward_optimizer import WalkForwardOptimizer
from .ml.feature_engineer import FeatureEngineer
from .ml.signal_classifier import SignalClassifier
from .ml.ml_enhanced_strategy import MLEnhancedStrategy
from .ml.anomaly_detector import AnomalyDetector
from .ml.hyperparameter_tuner import HyperparameterTuner
from .ml.ml_paper_trader import MLPaperTrader


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


@app.post("/api/optimize/walk-forward")
async def walk_forward_optimization(
    symbol: str = Query(..., description="Símbolo do ativo"),
    start_date: str = Query(..., description="Data inicial (YYYY-MM-DD)"),
    end_date: str = Query(..., description="Data final (YYYY-MM-DD)"),
    timeframe: str = Query("1d", description="Timeframe"),
    strategy: str = Query(..., description="Estratégia a otimizar"),
    train_window_days: int = Query(180, description="Tamanho da janela de treino em dias"),
    test_window_days: int = Query(30, description="Tamanho da janela de teste em dias"),
    step_days: Optional[int] = Query(None, description="Passo para avançar janela (None = anchored)"),
    optimization_metric: str = Query("sharpe_ratio", description="Métrica para otimizar"),
    n_trials: int = Query(50, description="Número de trials Optuna por janela"),
    initial_capital: float = Query(100000, description="Capital inicial")
):
    """
    Walk-Forward Optimization - PASSO 10
    
    Divide dados históricos em janelas de treino/teste, otimiza parâmetros
    em cada janela de treino e valida em dados out-of-sample.
    
    Tipos de Walk-Forward:
    - Anchored (step_days=None): janela de treino cresce, teste fixo
    - Rolling (step_days especificado): ambas as janelas deslizam
    
    Parâmetros:
    -----------
    symbol : str
        Símbolo do ativo (ex: PETR4)
    start_date : str
        Data inicial no formato YYYY-MM-DD
    end_date : str
        Data final no formato YYYY-MM-DD
    timeframe : str
        Intervalo de tempo (1m, 5m, 15m, 1h, 1d)
    strategy : str
        Nome da estratégia a otimizar
    train_window_days : int
        Tamanho da janela de treino em dias (padrão: 180)
    test_window_days : int
        Tamanho da janela de teste em dias (padrão: 30)
    step_days : Optional[int]
        Passo para avançar a janela. None = anchored, valor = rolling
    optimization_metric : str
        Métrica para otimizar: sharpe_ratio, total_return, profit_factor
    n_trials : int
        Número de trials do Optuna por janela (padrão: 50)
    initial_capital : float
        Capital inicial para backtests
    
    Retorna:
    --------
    {
        "strategy": "mean_reversion",
        "configuration": {...},
        "aggregate_statistics": {
            "total_windows": 5,
            "avg_test_sharpe": 1.85,
            "std_test_sharpe": 0.42,
            "positive_windows": 4,
            ...
        },
        "windows": [
            {
                "window_id": 1,
                "period": {...},
                "best_params": {...},
                "train_metrics": {...},
                "test_metrics": {...}
            },
            ...
        ]
    }
    """
    try:
        # Validar estratégia
        strategy_manager = StrategyManager()
        available = [s['name'] for s in strategy_manager.list_strategies()]
        
        if strategy not in available:
            raise HTTPException(
                status_code=400,
                detail=f"Estratégia '{strategy}' inválida. Disponíveis: {available}"
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
        
        # Verificar quantidade mínima de dados
        min_required = train_window_days + test_window_days
        if len(df) < min_required:
            raise HTTPException(
                status_code=400,
                detail=f"Dados insuficientes. Necessário: {min_required} candles, Disponível: {len(df)}"
            )
        
        logger.info(f"🚀 Iniciando Walk-Forward: {strategy} em {symbol}")
        logger.info(f"📊 Total de dados: {len(df)} candles")
        
        # Criar otimizador
        optimizer = WalkForwardOptimizer(
            strategy_name=strategy,
            train_window_days=train_window_days,
            test_window_days=test_window_days,
            step_days=step_days,
            optimization_metric=optimization_metric,
            n_trials=n_trials,
            initial_capital=initial_capital
        )
        
        # Executar otimização
        result = await optimizer.run(df)
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erro em walk_forward_optimization: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# PAPER TRADING ENDPOINTS
# ============================================

paper_manager = PaperTradingManager(settings.INITIAL_CAPITAL)
ml_paper_trader: Optional[MLPaperTrader] = None


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
# ML FEATURE ENGINEERING ENDPOINTS
# ============================================

class FeatureRequest(BaseModel):
    """Request para criação de features."""
    symbol: str = Field(..., description="Símbolo do ativo")
    start_date: str = Field(..., description="Data inicial (YYYY-MM-DD)")
    end_date: str = Field(..., description="Data final (YYYY-MM-DD)")
    timeframe: str = Field(default="1d", description="Timeframe")
    regime: Optional[str] = Field(None, description="Regime: trending, ranging, volatile")
    normalize: bool = Field(default=True, description="Normalizar features")
    n_features: int = Field(default=20, description="Número de features a selecionar")


@app.post("/api/ml/features")
async def create_features(request: FeatureRequest):
    """
    Cria features de ML a partir de dados OHLCV.
    
    **Parâmetros:**
    - `symbol`: Código do ativo (ex: PETR4, VALE3)
    - `start_date`: Data inicial no formato YYYY-MM-DD
    - `end_date`: Data final no formato YYYY-MM-DD
    - `timeframe`: Período dos candles (1d, 1h, etc)
    - `regime`: Regime de mercado (opcional: trending, ranging, volatile)
    - `normalize`: Se True, normaliza features com RobustScaler
    - `n_features`: Número de melhores features a retornar
    
    **Retorna:**
    - DataFrame com features técnicas calculadas
    - Lista de features disponíveis
    - Estatísticas descritivas
    
    **Exemplo:**
    ```bash
    curl -X POST 'http://localhost:3008/api/ml/features' \\
      -H 'Content-Type: application/json' \\
      -d '{
        "symbol": "PETR4",
        "start_date": "2025-06-01",
        "end_date": "2026-01-12",
        "regime": "trending",
        "normalize": true
      }'
    ```
    """
    try:
        # Converter datas
        from datetime import datetime
        start_dt = datetime.strptime(request.start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(request.end_date, "%Y-%m-%d")
        
        # Buscar dados históricos
        query = """
        SELECT time, open, high, low, close, volume
        FROM ohlcv_data
        WHERE symbol = $1 
          AND timeframe = $2
          AND time BETWEEN $3 AND $4
        ORDER BY time ASC
        """
        
        rows = await ts_pool.fetch(
            query,
            request.symbol,
            request.timeframe,
            start_dt,
            end_dt
        )
        
        if not rows:
            raise HTTPException(
                status_code=404,
                detail=f"Nenhum dado encontrado para {request.symbol} no período especificado"
            )
        
        # Converter para DataFrame
        import pandas as pd
        df = pd.DataFrame(rows, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
        df['time'] = pd.to_datetime(df['time'])
        df.set_index('time', inplace=True)
        
        # Converter Decimal para float
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = df[col].astype(float)
        
        # Criar features
        feature_engineer = FeatureEngineer(n_features=request.n_features)
        df_features = feature_engineer.create_all_features(df, regime=request.regime)
        
        # Normalizar se solicitado
        if request.normalize:
            df_features = feature_engineer.normalize_features(df_features)
        
        # Remover NaN
        df_features = df_features.dropna()
        
        # Estatísticas
        feature_columns = [c for c in df_features.columns 
                          if c not in ['open', 'high', 'low', 'close', 'volume']]
        
        stats = {
            "total_rows": len(df_features),
            "total_features": len(feature_columns),
            "date_range": {
                "start": df_features.index[0].isoformat(),
                "end": df_features.index[-1].isoformat()
            },
            "feature_categories": {
                "momentum": len([f for f in feature_columns if any(x in f for x in ['rsi', 'roc', 'stoch', 'williams', 'momentum'])]),
                "volatility": len([f for f in feature_columns if any(x in f for x in ['atr', 'bb', 'volatility', 'parkinson'])]),
                "trend": len([f for f in feature_columns if any(x in f for x in ['ema', 'macd', 'adx', 'aroon', 'lr_slope'])]),
                "volume": len([f for f in feature_columns if any(x in f for x in ['volume', 'obv', 'vwap', 'mfi', 'vpt'])]),
                "pattern": len([f for f in feature_columns if any(x in f for x in ['body', 'shadow', 'doji', 'hammer', 'engulfing'])]),
                "regime": len([f for f in feature_columns if 'regime' in f])
            }
        }
        
        # Retornar amostra das últimas 100 linhas
        sample_size = min(100, len(df_features))
        df_sample = df_features.tail(sample_size)
        
        return {
            "status": "success",
            "symbol": request.symbol,
            "timeframe": request.timeframe,
            "regime": request.regime,
            "normalized": request.normalize,
            "statistics": stats,
            "feature_names": feature_columns,
            "sample_data": df_sample.reset_index().to_dict(orient='records')
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao criar features: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao criar features: {str(e)}")


# ============================================
# ML CLASSIFIER TRAINING ENDPOINT
# ============================================

class TrainClassifierRequest(BaseModel):
    """Request para treinar classificador ML."""
    symbol: str = Field(..., description="Símbolo do ativo")
    start_date: str = Field(..., description="Data inicial (YYYY-MM-DD)")
    end_date: str = Field(..., description="Data final (YYYY-MM-DD)")
    timeframe: str = Field(default="1d", description="Timeframe")
    model_type: str = Field(default="random_forest", description="random_forest ou xgboost")
    n_estimators: int = Field(default=200, description="Número de árvores")
    lookahead_bars: int = Field(default=5, description="Quantos candles olhar para frente")
    profit_threshold: float = Field(default=0.01, description="Retorno mínimo para label positivo")
    regime: Optional[str] = Field(None, description="Regime de mercado")
    test_size: float = Field(default=0.2, description="Proporção do conjunto de teste")
    model_name: Optional[str] = Field(None, description="Nome para salvar modelo")


@app.post("/api/ml/train")
async def train_classifier(request: TrainClassifierRequest):
    """
    Treina um classificador ML para sinais de trading.
    
    **Workflow:**
    1. Busca dados históricos do símbolo
    2. Cria features técnicas (momentum, volatilidade, etc)
    3. Cria labels baseado em retornos futuros
    4. Treina Random Forest ou XGBoost
    5. Retorna métricas de treinamento
    
    **Exemplo:**
    ```bash
    curl -X POST 'http://localhost:3008/api/ml/train' \\
      -H 'Content-Type: application/json' \\
      -d '{
        "symbol": "PETR4",
        "start_date": "2025-01-01",
        "end_date": "2026-01-12",
        "model_type": "random_forest",
        "n_estimators": 200,
        "lookahead_bars": 5,
        "profit_threshold": 0.01,
        "model_name": "petr4_rf_model"
      }'
    ```
    """
    try:
        # Buscar dados
        start_dt = datetime.strptime(request.start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(request.end_date, "%Y-%m-%d")
        
        query = """
        SELECT time, open, high, low, close, volume
        FROM ohlcv_data
        WHERE symbol = $1 AND timeframe = $2
          AND time BETWEEN $3 AND $4
        ORDER BY time ASC
        """
        
        rows = await ts_pool.fetch(query, request.symbol, request.timeframe, start_dt, end_dt)
        
        if not rows:
            raise HTTPException(status_code=404, detail=f"Dados não encontrados para {request.symbol}")
        
        # DataFrame
        import pandas as pd
        df = pd.DataFrame(rows, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
        df['time'] = pd.to_datetime(df['time'])
        df.set_index('time', inplace=True)
        
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = df[col].astype(float)
        
        # Criar features
        feature_engineer = FeatureEngineer()
        df_features = feature_engineer.create_all_features(df, regime=request.regime)
        df_features = feature_engineer.normalize_features(df_features)
        
        # Criar labels
        classifier = SignalClassifier(
            model_type=request.model_type,
            n_estimators=request.n_estimators
        )
        
        labels = classifier.create_labels(
            df_features,
            lookahead_bars=request.lookahead_bars,
            profit_threshold=request.profit_threshold
        )
        
        # Features para treino
        feature_cols = [c for c in df_features.columns 
                       if c not in ['open', 'high', 'low', 'close', 'volume']]
        X = df_features[feature_cols]
        
        # Treinar
        metrics = classifier.train(X, labels, test_size=request.test_size, cross_validation=True)
        
        # Salvar modelo se nome fornecido
        if request.model_name:
            model_path = f"/app/models/{request.model_name}.pkl"
            classifier.save_model(model_path)
            metrics['model_path'] = model_path
        
        # Feature importance
        feature_importance = classifier.get_feature_importance(top_n=20)
        
        return {
            "status": "success",
            "symbol": request.symbol,
            "model_type": request.model_type,
            "metrics": metrics,
            "top_features": feature_importance,
            "parameters": {
                "lookahead_bars": request.lookahead_bars,
                "profit_threshold": request.profit_threshold,
                "n_estimators": request.n_estimators
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao treinar classificador: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao treinar: {str(e)}")


# ============================================
# ML PREDICTION ENDPOINT
# ============================================

class PredictSignalsRequest(BaseModel):
    """Request para predizer sinais com ML."""
    symbol: str = Field(..., description="Símbolo do ativo")
    start_date: str = Field(..., description="Data inicial")
    end_date: str = Field(..., description="Data final")
    timeframe: str = Field(default="1d", description="Timeframe")
    model_name: str = Field(..., description="Nome do modelo treinado")
    base_strategy: str = Field(default="mean_reversion", description="Estratégia base")
    strategy_params: Dict = Field(default={}, description="Parâmetros da estratégia")
    confidence_threshold: float = Field(default=0.6, description="Threshold de confiança ML")
    regime: Optional[str] = Field(None, description="Regime de mercado")


@app.post("/api/ml/predict")
async def predict_signals(request: PredictSignalsRequest):
    """
    Gera sinais de trading usando ML-Enhanced Strategy.
    
    **Workflow:**
    1. Carrega modelo ML treinado
    2. Busca dados históricos
    3. Gera sinais da estratégia base
    4. Filtra sinais com ML (aceita apenas alta confiança)
    5. Retorna sinais filtrados + estatísticas
    
    **Exemplo:**
    ```bash
    curl -X POST 'http://localhost:3008/api/ml/predict' \\
      -H 'Content-Type: application/json' \\
      -d '{
        "symbol": "PETR4",
        "start_date": "2025-11-01",
        "end_date": "2026-01-12",
        "model_name": "petr4_rf_model",
        "base_strategy": "mean_reversion",
        "confidence_threshold": 0.7
      }'
    ```
    """
    try:
        # Carregar modelo
        model_path = f"/app/models/{request.model_name}.pkl"
        classifier = SignalClassifier()
        classifier.load_model(model_path)
        
        # Buscar dados
        start_dt = datetime.strptime(request.start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(request.end_date, "%Y-%m-%d")
        
        query = """
        SELECT time, open, high, low, close, volume
        FROM ohlcv_data
        WHERE symbol = $1 AND timeframe = $2
          AND time BETWEEN $3 AND $4
        ORDER BY time ASC
        """
        
        rows = await ts_pool.fetch(query, request.symbol, request.timeframe, start_dt, end_dt)
        
        if not rows:
            raise HTTPException(status_code=404, detail=f"Dados não encontrados")
        
        # DataFrame
        import pandas as pd
        df = pd.DataFrame(rows, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
        df['time'] = pd.to_datetime(df['time'])
        df.set_index('time', inplace=True)
        
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = df[col].astype(float)
        
        # ML-Enhanced Strategy
        feature_engineer = FeatureEngineer()
        
        # Parâmetros padrão se não fornecidos
        if not request.strategy_params:
            if request.base_strategy == "mean_reversion":
                request.strategy_params = {"bb_period": 20, "bb_std": 2.0}
            elif request.base_strategy == "trend_following":
                request.strategy_params = {"fast_ema": 12, "slow_ema": 26}
        
        ml_strategy = MLEnhancedStrategy(
            base_strategy_name=request.base_strategy,
            base_strategy_params=request.strategy_params,
            classifier=classifier,
            feature_engineer=feature_engineer,
            confidence_threshold=request.confidence_threshold,
            regime=request.regime
        )
        
        # Gerar sinais
        result = ml_strategy.generate_signals(df)
        
        # Preparar resposta com amostra dos últimos 50 sinais
        signals_df = pd.DataFrame({
            'time': result['features'].index,
            'close': result['features']['close'],
            'base_signal': result['base_signals'],
            'ml_signal': result['ml_signals'],
            'ml_confidence': result['ml_confidences']
        }).tail(50)
        
        return {
            "status": "success",
            "symbol": request.symbol,
            "model_name": request.model_name,
            "base_strategy": request.base_strategy,
            "statistics": result['statistics'],
            "signals_sample": signals_df.to_dict(orient='records')
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao predizer sinais: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao predizer: {str(e)}")


# ============================================
# ANOMALY DETECTION ENDPOINT
# ============================================

class AnomalyDetectionRequest(BaseModel):
    """Request para detecção de anomalias."""
    symbol: str = Field(..., description="Símbolo do ativo")
    start_date: str = Field(..., description="Data inicial")
    end_date: str = Field(..., description="Data final")
    timeframe: str = Field(default="1d", description="Timeframe")
    contamination: float = Field(default=0.1, description="Proporção esperada de anomalias (0.0-0.5)")
    n_estimators: int = Field(default=100, description="Número de árvores")
    regime: Optional[str] = Field(None, description="Regime de mercado")
    analyze_patterns: bool = Field(default=True, description="Analisar padrões nas anomalias")


@app.post("/api/ml/anomalies")
async def detect_anomalies(request: AnomalyDetectionRequest):
    """
    Detecta anomalias em dados de mercado usando Isolation Forest.
    
    **Anomalias indicam:**
    - Movimentos de preço incomuns (oportunidades)
    - Mudanças abruptas de volume
    - Padrões técnicos raros
    - Possíveis eventos de risco
    
    **Workflow:**
    1. Busca dados históricos
    2. Cria features técnicas (momentum, volatilidade, etc)
    3. Treina Isolation Forest
    4. Detecta anomalias
    5. Analisa padrões e retornos futuros
    
    **Exemplo:**
    ```bash
    curl -X POST 'http://localhost:3008/api/ml/anomalies' \\
      -H 'Content-Type: application/json' \\
      -d '{
        "symbol": "PETR4",
        "start_date": "2025-01-01",
        "end_date": "2026-01-12",
        "contamination": 0.1,
        "analyze_patterns": true
      }'
    ```
    """
    try:
        # Buscar dados
        start_dt = datetime.strptime(request.start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(request.end_date, "%Y-%m-%d")
        
        query = """
        SELECT time, open, high, low, close, volume
        FROM ohlcv_data
        WHERE symbol = $1 AND timeframe = $2
          AND time BETWEEN $3 AND $4
        ORDER BY time ASC
        """
        
        rows = await ts_pool.fetch(query, request.symbol, request.timeframe, start_dt, end_dt)
        
        if not rows:
            raise HTTPException(status_code=404, detail=f"Dados não encontrados")
        
        # DataFrame
        import pandas as pd
        df = pd.DataFrame(rows, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
        df['time'] = pd.to_datetime(df['time'])
        df.set_index('time', inplace=True)
        
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = df[col].astype(float)
        
        # Criar features
        feature_engineer = FeatureEngineer()
        df_features = feature_engineer.create_all_features(df.copy(), regime=request.regime)
        df_features = feature_engineer.normalize_features(df_features)
        df_features = df_features.dropna()
        
        if len(df_features) < 50:
            raise HTTPException(
                status_code=400,
                detail=f"Dados insuficientes após criar features: {len(df_features)} linhas"
            )
        
        # Features para análise
        feature_cols = [c for c in df_features.columns 
                       if c not in ['open', 'high', 'low', 'close', 'volume']]
        X = df_features[feature_cols]
        
        # Treinar detector
        detector = AnomalyDetector(
            contamination=request.contamination,
            n_estimators=request.n_estimators
        )
        
        training_stats = detector.fit(X)
        
        # Detectar anomalias
        anomalies_result = detector.detect_anomalies(X, df_features[['close', 'volume']])
        
        # Análise de padrões (opcional)
        patterns_analysis = None
        if request.analyze_patterns and anomalies_result['n_anomalies'] > 0:
            patterns_analysis = detector.analyze_anomaly_patterns(X, df_features)
        
        # Preparar resposta
        response = {
            "status": "success",
            "symbol": request.symbol,
            "period": {
                "start": request.start_date,
                "end": request.end_date
            },
            "training_stats": training_stats,
            "detection_results": anomalies_result,
        }
        
        if patterns_analysis:
            response["pattern_analysis"] = patterns_analysis
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao detectar anomalias: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao detectar anomalias: {str(e)}")


# ============================================
# ML - BACKTESTING COMPARATIVO
# ============================================

class BacktestCompareRequest(BaseModel):
    """Request para comparação de backtesting."""
    symbol: str = Field(..., description="Símbolo do ativo (ex: PETR4)")
    start_date: str = Field(..., description="Data inicial (YYYY-MM-DD)")
    end_date: str = Field(..., description="Data final (YYYY-MM-DD)")
    timeframe: str = Field(default="1d", description="Timeframe dos dados")
    
    # Estratégia base
    base_strategy: str = Field(..., description="Nome da estratégia base (ex: mean_reversion)")
    strategy_params: Dict = Field(default_factory=dict, description="Parâmetros da estratégia")
    
    # ML Classifier
    model_path: str = Field(..., description="Caminho do modelo ML treinado (ex: models/petr4_rf.pkl)")
    confidence_threshold: float = Field(default=0.6, ge=0, le=1, description="Threshold de confiança ML")
    
    # Backtest params
    initial_capital: float = Field(default=100000, description="Capital inicial")
    commission: float = Field(default=0.0025, description="Taxa de corretagem (0.25%)")
    slippage: float = Field(default=0.001, description="Slippage estimado (0.1%)")
    
    regime: Optional[str] = Field(None, description="Regime de mercado")


@app.post("/api/ml/compare", tags=["ML"], summary="🆚 Comparar Estratégia Base vs ML-Enhanced")
async def compare_strategies(request: BacktestCompareRequest):
    """
    Compara performance de estratégia base vs ML-enhanced com métricas profissionais.
    
    Retorna análise detalhada incluindo:
    - Métricas de performance (Sharpe, retorno, drawdown, win rate, profit factor)
    - Equity curves comparativas
    - Análise de sinais filtrados pelo ML
    - Recomendação sobre uso do filtro ML
    - Trades executados
    
    Exemplo:
    ```bash
    curl -X POST 'http://localhost:3008/api/ml/compare' \\
      -H 'Content-Type: application/json' \\
      -d '{
        "symbol": "PETR4",
        "start_date": "2025-01-01",
        "end_date": "2026-01-12",
        "base_strategy": "mean_reversion",
        "strategy_params": {"rsi_period": 14, "rsi_oversold": 30, "rsi_overbought": 70},
        "model_path": "models/petr4_rf.pkl",
        "confidence_threshold": 0.65,
        "initial_capital": 100000,
        "commission": 0.0025,
        "slippage": 0.001
      }'
    ```
    """
    try:
        # 1. Buscar dados
        start_dt = datetime.strptime(request.start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(request.end_date, "%Y-%m-%d")
        
        query = """
        SELECT time, open, high, low, close, volume
        FROM ohlcv_data
        WHERE symbol = $1 AND timeframe = $2
          AND time BETWEEN $3 AND $4
        ORDER BY time ASC
        """
        
        rows = await ts_pool.fetch(query, request.symbol, request.timeframe, start_dt, end_dt)
        
        if not rows:
            raise HTTPException(status_code=404, detail=f"Dados não encontrados")
        
        # DataFrame
        import pandas as pd
        df = pd.DataFrame(rows, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
        df['time'] = pd.to_datetime(df['time'])
        df.set_index('time', inplace=True)
        
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = df[col].astype(float)
        
        # 2. Carregar modelo ML
        import joblib
        import os
        
        model_full_path = os.path.join('/app', request.model_path)
        
        if not os.path.exists(model_full_path):
            raise HTTPException(
                status_code=404,
                detail=f"Modelo não encontrado: {model_full_path}"
            )
        
        # Carregar modelo (é um dict com 'model', 'model_type', etc)
        model_data = joblib.load(model_full_path)
        
        # Criar SignalClassifier e carregar modelo
        classifier = SignalClassifier(model_type=model_data['model_type'])
        classifier.model = model_data['model']
        classifier.feature_names = model_data.get('feature_names')
        classifier.feature_importance = model_data.get('feature_importance')
        classifier.training_metrics = model_data.get('training_metrics')
        
        logger.info(f"Modelo carregado: {model_full_path} ({model_data['model_type']})")
        
        # 3. Criar feature engineer
        feature_engineer = FeatureEngineer()
        
        # 4. Criar estratégia ML-enhanced
        from .ml.ml_enhanced_strategy import MLEnhancedStrategy
        
        ml_strategy = MLEnhancedStrategy(
            base_strategy_name=request.base_strategy,
            base_strategy_params=request.strategy_params,
            classifier=classifier,
            feature_engineer=feature_engineer,
            confidence_threshold=request.confidence_threshold,
            regime=request.regime
        )
        
        # 5. Executar comparação
        comparison_result = ml_strategy.backtest_comparison(
            df=df,
            initial_capital=request.initial_capital,
            commission=request.commission,
            slippage=request.slippage
        )
        
        # 6. Preparar resposta
        response = {
            "status": "success",
            "symbol": request.symbol,
            "period": {
                "start": request.start_date,
                "end": request.end_date,
                "days": len(df)
            },
            "config": {
                "base_strategy": request.base_strategy,
                "strategy_params": request.strategy_params,
                "model": request.model_path,
                "confidence_threshold": request.confidence_threshold,
                "initial_capital": request.initial_capital,
                "commission": request.commission,
                "slippage": request.slippage
            },
            "results": comparison_result
        }
        
        # Log resumo
        logger.info(f"✅ Comparação concluída: {request.symbol}")
        logger.info(f"   Base Strategy: {comparison_result['base_strategy']['total_return']}% retorno")
        logger.info(f"   ML Enhanced:   {comparison_result['ml_enhanced']['total_return']}% retorno")
        logger.info(f"   Improvement:   {comparison_result['improvement']['return_delta']}%")
        logger.info(f"   Recommendation: {comparison_result['summary']['recommendation']}")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro na comparação de estratégias: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro na comparação: {str(e)}")


# ============================================
# ML - HYPERPARAMETER OPTIMIZATION
# ============================================

class HyperparameterOptimizationRequest(BaseModel):
    """Request para otimização de hiperparâmetros."""
    symbol: str = Field(..., description="Símbolo do ativo")
    start_date: str = Field(..., description="Data inicial (YYYY-MM-DD)")
    end_date: str = Field(..., description="Data final (YYYY-MM-DD)")
    timeframe: str = Field(default="1d", description="Timeframe")
    model_type: str = Field(..., description="Tipo do modelo (random_forest ou xgboost)")
    n_trials: int = Field(default=50, ge=10, le=200, description="Número de trials")
    lookahead_bars: int = Field(default=5, ge=1, le=20, description="Barras para lookahead")
    profit_threshold: float = Field(default=0.02, ge=0.001, le=0.1, description="Threshold de lucro")
    regime: Optional[str] = Field(None, description="Regime de mercado")


@app.post("/api/ml/optimize", tags=["ML"], summary="⚙️ Otimizar Hiperparâmetros ML")
async def optimize_hyperparameters(request: HyperparameterOptimizationRequest):
    """
    Otimiza hiperparâmetros do modelo ML usando Optuna.
    
    Retorna:
    - Melhores parâmetros encontrados
    - Score do melhor modelo
    - Histórico de otimização
    - Importância dos hiperparâmetros
    
    Exemplo:
    ```bash
    curl -X POST 'http://localhost:3008/api/ml/optimize' \\
      -H 'Content-Type: application/json' \\
      -d '{
        "symbol": "PETR4",
        "start_date": "2024-01-01",
        "end_date": "2026-01-12",
        "model_type": "random_forest",
        "n_trials": 30,
        "lookahead_bars": 5,
        "profit_threshold": 0.02
      }'
    ```
    """
    try:
        # 1. Buscar dados
        start_dt = datetime.strptime(request.start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(request.end_date, "%Y-%m-%d")
        
        query = """
        SELECT time, open, high, low, close, volume
        FROM ohlcv_data
        WHERE symbol = $1 AND timeframe = $2
          AND time BETWEEN $3 AND $4
        ORDER BY time ASC
        """
        
        rows = await ts_pool.fetch(query, request.symbol, request.timeframe, start_dt, end_dt)
        
        if not rows:
            raise HTTPException(status_code=404, detail="Dados não encontrados")
        
        # DataFrame
        import pandas as pd
        df = pd.DataFrame(rows, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
        df['time'] = pd.to_datetime(df['time'])
        df.set_index('time', inplace=True)
        
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = df[col].astype(float)
        
        # 2. Feature Engineering
        feature_engineer = FeatureEngineer()
        df_features = feature_engineer.create_all_features(df.copy(), regime=request.regime)
        df_features = feature_engineer.normalize_features(df_features)
        df_features = df_features.dropna()
        
        if len(df_features) < 100:
            raise HTTPException(
                status_code=400,
                detail=f"Dados insuficientes: {len(df_features)} linhas (mínimo: 100)"
            )
        
        # 3. Criar labels
        classifier = SignalClassifier(model_type=request.model_type)
        labels = classifier.create_labels(
            df_features,
            lookahead_bars=request.lookahead_bars,
            profit_threshold=request.profit_threshold
        )
        
        # Features - remover NaN
        feature_cols = [c for c in df_features.columns 
                       if c not in ['open', 'high', 'low', 'close', 'volume']]
        X = df_features[feature_cols].loc[labels.index]
        y = labels
        
        # Remover NaN
        valid_mask = ~(X.isna().any(axis=1) | y.isna())
        X = X[valid_mask]
        y = y[valid_mask]
        
        if len(X) < 100:
            raise HTTPException(
                status_code=400,
                detail=f"Dados insuficientes após limpeza: {len(X)} linhas (mínimo: 100)"
            )
        
        logger.info(f"Otimização: {len(X)} samples, {len(X.columns)} features")
        
        # 4. Executar otimização
        from .ml.hyperparameter_tuner import HyperparameterTuner
        
        tuner = HyperparameterTuner(
            model_type=request.model_type,
            n_trials=request.n_trials,
            cv_splits=5
        )
        
        optimization_result = tuner.optimize(X, y, direction="maximize")
        
        # 5. Importância dos hiperparâmetros
        param_importance = tuner.get_param_importance(top_n=10)
        
        # 6. Preparar resposta
        response = {
            "status": "success",
            "symbol": request.symbol,
            "period": {
                "start": request.start_date,
                "end": request.end_date,
                "days": len(df)
            },
            "optimization": {
                **optimization_result,
                "param_importance": param_importance
            },
            "data_info": {
                "n_samples": len(X),
                "n_features": len(X.columns),
                "class_distribution": {
                    "0": int((y == 0).sum()),
                    "1": int((y == 1).sum())
                }
            }
        }
        
        logger.info(f"✅ Otimização concluída: {request.model_type}")
        logger.info(f"   Best Score: {optimization_result['best_score']}")
        logger.info(f"   Best Trial: {optimization_result['best_trial']}/{request.n_trials}")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro na otimização: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro na otimização: {str(e)}")


# ============================================
# ML PAPER TRADING ENDPOINTS
# ============================================

class MLPaperTraderRequest(BaseModel):
    """Request para iniciar ML Paper Trader."""
    symbol: str = Field(..., description="Símbolo do ativo (ex: PETR4)")
    timeframe: str = Field(default="5m", description="Timeframe ('1m', '5m', '15m', '1h', '1d')")
    model_path: str = Field(..., description="Caminho do modelo ML (ex: models/petr4_rf.pkl)")
    strategy: str = Field(default="mean_reversion", description="Estratégia base")
    strategy_params: Dict = Field(default_factory=dict, description="Parâmetros da estratégia")
    confidence_threshold: float = Field(default=0.65, ge=0, le=1, description="Threshold ML")
    max_position_pct: float = Field(default=0.2, ge=0.01, le=1, description="% máxima por posição")
    check_interval: int = Field(default=60, ge=10, le=3600, description="Intervalo de verificação (s)")
    enable_anomaly_filter: bool = Field(default=True, description="Ativar filtro de anomalias")


@app.post("/api/ml/paper/start", tags=["ML Paper Trading"], summary="🤖 Iniciar ML Paper Trader")
async def start_ml_paper_trader(request: MLPaperTraderRequest):
    """
    Inicia paper trading automatizado com Machine Learning.
    
    O sistema irá:
    1. Monitorar preços no intervalo definido
    2. Gerar sinais com estratégia base
    3. Filtrar sinais com ML (apenas alta confiança)
    4. Detectar anomalias no mercado
    5. Executar trades automaticamente
    6. Gerenciar stop loss e take profit
    
    Exemplo:
    ```bash
    curl -X POST 'http://localhost:3008/api/ml/paper/start' \\
      -H 'Content-Type: application/json' \\
      -d '{
        "symbol": "PETR4",
        "timeframe": "5m",
        "model_path": "models/petr4_rf.pkl",
        "confidence_threshold": 0.70,
        "max_position_pct": 0.2,
        "check_interval": 60
      }'
    ```
    """
    global ml_paper_trader
    
    try:
        if ml_paper_trader and ml_paper_trader.is_running:
            raise HTTPException(
                status_code=400,
                detail="ML Paper Trader já está rodando. Pare primeiro com /api/ml/paper/stop"
            )
        
        # Criar ML Paper Trader
        # Se model_path já começa com /app/, não adicionar novamente
        model_path = request.model_path if request.model_path.startswith('/app/') else f"/app/{request.model_path}"
        
        ml_paper_trader = MLPaperTrader(
            paper_manager=paper_manager,
            model_path=model_path,
            strategy_name=request.strategy,
            strategy_params=request.strategy_params,
            confidence_threshold=request.confidence_threshold,
            max_position_size_pct=request.max_position_pct,
            check_interval=request.check_interval,
            enable_anomaly_filter=request.enable_anomaly_filter
        )
        
        # Carregar modelo
        if not ml_paper_trader.load_model():
            raise HTTPException(status_code=404, detail="Erro ao carregar modelo ML")
        
        # Iniciar paper manager se não estiver rodando
        if not paper_manager.is_running:
            paper_manager.start()
        
        ml_paper_trader.is_running = True
        
        logger.info(f"🤖 ML Paper Trader iniciado: {request.symbol} ({request.timeframe})")
        
        return {
            "status": "success",
            "message": "ML Paper Trader iniciado",
            "config": {
                "symbol": request.symbol,
                "timeframe": request.timeframe,
                "model_path": request.model_path,
                "strategy": request.strategy,
                "confidence_threshold": request.confidence_threshold,
                "check_interval": request.check_interval
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao iniciar ML Paper Trader: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ml/paper/stop", tags=["ML Paper Trading"], summary="⏹️ Parar ML Paper Trader")
async def stop_ml_paper_trader():
    """
    Para o ML Paper Trader.
    
    Exemplo:
    ```bash
    curl -X POST 'http://localhost:3008/api/ml/paper/stop'
    ```
    """
    global ml_paper_trader
    
    if not ml_paper_trader:
        raise HTTPException(status_code=400, detail="ML Paper Trader não foi iniciado")
    
    if not ml_paper_trader.is_running:
        raise HTTPException(status_code=400, detail="ML Paper Trader não está rodando")
    
    ml_paper_trader.is_running = False
    
    logger.info("⏹️ ML Paper Trader parado")
    
    return {
        "status": "success",
        "message": "ML Paper Trader parado",
        "stats": ml_paper_trader.get_stats()
    }


@app.get("/api/ml/paper/status", tags=["ML Paper Trading"], summary="📊 Status ML Paper Trader")
async def ml_paper_trader_status():
    """
    Retorna status do ML Paper Trader.
    
    Inclui:
    - Estado (rodando/parado)
    - Estatísticas de sinais (gerados/aceitos/rejeitados)
    - Taxa de aceitação
    - Anomalias detectadas
    - Performance do paper trading
    - Últimas decisões
    
    Exemplo:
    ```bash
    curl 'http://localhost:3008/api/ml/paper/status'
    ```
    """
    if not ml_paper_trader:
        return {
            "status": "not_initialized",
            "message": "ML Paper Trader não foi iniciado"
        }
    
    return ml_paper_trader.get_stats()


@app.post("/api/ml/paper/check", tags=["ML Paper Trading"], summary="🔍 Verificar Sinal Manualmente")
async def check_ml_signal_manual(
    symbol: str = Query(..., description="Símbolo"),
    timeframe: str = Query(default="5m", description="Timeframe")
):
    """
    Verifica manualmente se há sinal ML no momento.
    
    Útil para testar sem executar trades.
    
    Exemplo:
    ```bash
    curl 'http://localhost:3008/api/ml/paper/check?symbol=PETR4&timeframe=5m'
    ```
    """
    if not ml_paper_trader:
        raise HTTPException(status_code=400, detail="ML Paper Trader não inicializado")
    
    try:
        # Buscar dados recentes
        df = await ml_paper_trader.fetch_recent_data(symbol, timeframe, 200, ts_pool)
        
        if df is None or len(df) < 50:
            raise HTTPException(status_code=404, detail="Dados insuficientes")
        
        current_price = float(df['close'].iloc[-1])
        
        # Verificar anomalias
        anomaly_check = await ml_paper_trader.check_anomalies(df)
        
        # Gerar sinal
        signal_data = await ml_paper_trader.generate_ml_signal(df, current_price)
        
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "current_price": current_price,
            "timestamp": datetime.now().isoformat(),
            "anomaly_check": anomaly_check,
            "signal": signal_data if signal_data else None,
            "recommendation": "EXECUTE" if (signal_data and anomaly_check.get('is_safe')) else "WAIT"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao verificar sinal: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


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
