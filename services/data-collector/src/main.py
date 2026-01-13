"""
B3 Trading Platform - Data Collector
=====================================
Serviço de coleta de dados de mercado.
"""

import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Optional, List

import asyncpg
import redis.asyncio as redis
import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from loguru import logger


# ============================================
# CONFIGURATION
# ============================================

class Settings:
    # TimescaleDB
    TIMESCALE_HOST = os.getenv("TIMESCALE_HOST", "localhost")
    TIMESCALE_PORT = int(os.getenv("TIMESCALE_PORT", 5432))
    TIMESCALE_DB = os.getenv("TIMESCALE_DB", "b3trading_market")
    TIMESCALE_USER = os.getenv("TIMESCALE_USER", "b3trading_ts")
    TIMESCALE_PASSWORD = os.getenv("TIMESCALE_PASSWORD", "b3trading_ts_pass")
    
    # Redis
    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
    
    # BRAPI
    BRAPI_TOKEN = os.getenv("BRAPI_TOKEN", "")
    BRAPI_URL = "https://brapi.dev/api"
    
    # MetaTrader 5
    MT5_LOGIN = os.getenv("MT5_LOGIN", "")
    MT5_PASSWORD = os.getenv("MT5_PASSWORD", "")
    MT5_SERVER = os.getenv("MT5_SERVER", "")

settings = Settings()


# ============================================
# DATABASE
# ============================================

ts_pool: Optional[asyncpg.Pool] = None
redis_client: Optional[redis.Redis] = None


async def init_db():
    global ts_pool, redis_client
    
    logger.info("🔌 Conectando aos bancos de dados...")
    
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
    
    redis_client = redis.Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        decode_responses=True
    )
    await redis_client.ping()
    logger.info("✅ Redis conectado")


async def close_db():
    global ts_pool, redis_client
    if ts_pool:
        await ts_pool.close()
    if redis_client:
        await redis_client.close()


# ============================================
# FASTAPI APP
# ============================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    logger.info("🚀 Data Collector iniciado!")
    yield
    await close_db()


app = FastAPI(
    title="B3 Trading Platform - Data Collector",
    description="Serviço de coleta de dados de mercado B3",
    version="1.0.0",
    lifespan=lifespan
)

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

class OHLCVData(BaseModel):
    time: datetime
    symbol: str
    timeframe: str
    open: float
    high: float
    low: float
    close: float
    volume: int


class DownloadRequest(BaseModel):
    symbols: List[str]
    timeframes: List[str] = ["5m", "15m", "1h", "1d"]
    days: int = 30


# ============================================
# BRAPI CLIENT
# ============================================

class BRAPIClient:
    """Cliente para API BRAPI (ações brasileiras)."""
    
    def __init__(self, token: str):
        self.token = token
        self.base_url = "https://brapi.dev/api"
    
    async def get_quote(self, symbol: str) -> dict:
        """Obtém cotação atual."""
        async with httpx.AsyncClient() as client:
            url = f"{self.base_url}/quote/{symbol}"
            params = {"token": self.token} if self.token else {}
            
            response = await client.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            if "results" in data and len(data["results"]) > 0:
                return data["results"][0]
            return {}
    
    async def get_historical(
        self,
        symbol: str,
        range: str = "1mo",  # 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max
        interval: str = "1d"  # 1d, 1wk, 1mo
    ) -> List[dict]:
        """Obtém dados históricos."""
        async with httpx.AsyncClient() as client:
            url = f"{self.base_url}/quote/{symbol}"
            params = {
                "range": range,
                "interval": interval,
                "fundamental": "false"
            }
            if self.token:
                params["token"] = self.token
            
            response = await client.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            if "results" in data and len(data["results"]) > 0:
                result = data["results"][0]
                if "historicalDataPrice" in result:
                    return result["historicalDataPrice"]
            return []


brapi = BRAPIClient(settings.BRAPI_TOKEN)


# ============================================
# ENDPOINTS
# ============================================

@app.get("/health")
async def health_check():
    """Health check."""
    services = {"timescaledb": "unknown", "redis": "unknown"}
    
    try:
        async with ts_pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
            services["timescaledb"] = "healthy"
    except Exception as e:
        services["timescaledb"] = f"unhealthy: {str(e)}"
    
    try:
        await redis_client.ping()
        services["redis"] = "healthy"
    except Exception as e:
        services["redis"] = f"unhealthy: {str(e)}"
    
    all_healthy = all(s == "healthy" for s in services.values())
    
    return {
        "status": "healthy" if all_healthy else "degraded",
        "timestamp": datetime.now(),
        "services": services
    }


@app.get("/api/quote/{symbol}")
async def get_quote(symbol: str):
    """Obtém cotação atual de um símbolo."""
    try:
        quote = await brapi.get_quote(symbol)
        
        if quote:
            # Salvar no cache Redis
            await redis_client.hset(
                f"quote:{symbol}",
                mapping={
                    "price": str(quote.get("regularMarketPrice", 0)),
                    "change": str(quote.get("regularMarketChange", 0)),
                    "change_pct": str(quote.get("regularMarketChangePercent", 0)),
                    "volume": str(quote.get("regularMarketVolume", 0)),
                    "updated_at": datetime.now().isoformat()
                }
            )
            await redis_client.expire(f"quote:{symbol}", 60)  # Cache por 1 minuto
        
        return quote
    except Exception as e:
        logger.error(f"Erro ao obter cotação de {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/historical/{symbol}")
async def get_historical(
    symbol: str,
    range: str = Query(default="1mo", description="Período: 1d, 5d, 1mo, 3mo, 6mo, 1y"),
    interval: str = Query(default="1d", description="Intervalo: 1d, 1wk, 1mo")
):
    """Obtém dados históricos de um símbolo."""
    try:
        data = await brapi.get_historical(symbol, range, interval)
        
        # Salvar no TimescaleDB
        if data:
            async with ts_pool.acquire() as conn:
                for candle in data:
                    await conn.execute("""
                        INSERT INTO ohlcv_data (time, symbol, timeframe, open, high, low, close, volume)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                        ON CONFLICT (time, symbol, timeframe) DO UPDATE SET
                            open = EXCLUDED.open,
                            high = EXCLUDED.high,
                            low = EXCLUDED.low,
                            close = EXCLUDED.close,
                            volume = EXCLUDED.volume
                    """,
                        datetime.fromtimestamp(candle.get("date", 0)),
                        symbol,
                        interval,
                        candle.get("open", 0),
                        candle.get("high", 0),
                        candle.get("low", 0),
                        candle.get("close", 0),
                        int(candle.get("volume", 0))
                    )
        
        return {
            "symbol": symbol,
            "range": range,
            "interval": interval,
            "count": len(data),
            "data": data
        }
    except Exception as e:
        logger.error(f"Erro ao obter histórico de {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/download")
async def download_data(request: DownloadRequest):
    """Baixa dados históricos para múltiplos símbolos."""
    results = []
    
    for symbol in request.symbols:
        try:
            # Mapear dias para range
            if request.days <= 5:
                range_param = "5d"
            elif request.days <= 30:
                range_param = "1mo"
            elif request.days <= 90:
                range_param = "3mo"
            elif request.days <= 180:
                range_param = "6mo"
            elif request.days <= 365:
                range_param = "1y"
            else:
                range_param = "2y"
            
            for timeframe in request.timeframes:
                # BRAPI só suporta 1d, 1wk, 1mo
                if timeframe in ["1d", "1wk", "1mo"]:
                    data = await brapi.get_historical(symbol, range_param, timeframe)
                    
                    results.append({
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "candles": len(data),
                        "status": "success"
                    })
                else:
                    results.append({
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "candles": 0,
                        "status": "skipped (BRAPI só suporta 1d, 1wk, 1mo)"
                    })
                    
        except Exception as e:
            results.append({
                "symbol": symbol,
                "timeframe": "all",
                "candles": 0,
                "status": f"error: {str(e)}"
            })
    
    return {
        "timestamp": datetime.now(),
        "results": results
    }


@app.get("/api/symbols")
async def list_symbols():
    """Lista símbolos disponíveis no banco."""
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
        "symbols": [dict(row) for row in rows],
        "count": len(rows)
    }


@app.get("/api/data/{symbol}")
async def get_data(
    symbol: str,
    timeframe: str = Query(default="1d"),
    limit: int = Query(default=500, le=2000)
):
    """Retorna dados OHLCV do banco."""
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


# ============================================
# SÍMBOLOS B3
# ============================================

B3_SYMBOLS = {
    "futures": ["WINFUT", "WDOFUT"],  # Mini Índice, Mini Dólar
    "stocks": [
        "PETR4", "VALE3", "ITUB4", "BBDC4", "ABEV3",
        "B3SA3", "WEGE3", "RENT3", "SUZB3", "JBSS3"
    ],
    "etfs": ["BOVA11", "IVVB11", "SMAL11", "HASH11", "XFIX11"]
}


@app.get("/api/b3/symbols")
async def list_b3_symbols():
    """Lista símbolos B3 configurados."""
    return B3_SYMBOLS


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3002)
