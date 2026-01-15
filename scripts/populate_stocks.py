#!/usr/bin/env python3
"""
Script para popular TimescaleDB com dados históricos via yfinance
"""

import asyncio
import asyncpg
import yfinance as yf
from datetime import datetime
from loguru import logger


B3_STOCKS = [
    'VALE3.SA', 'ITUB4.SA', 'WEGE3.SA', 'BBDC4.SA', 
    'MGLU3.SA', 'B3SA3.SA', 'RENT3.SA', 'ABEV3.SA',
    'PETR3.SA', 'ELET3.SA', 'SUZB3.SA', 'EMBR3.SA'
]


async def populate_stocks():
    """Coleta e insere dados de ações B3."""
    
    # Conectar ao TimescaleDB
    conn = await asyncpg.connect(
        host='b3-timescaledb',
        port=5432,
        database='b3trading_market',
        user='b3trading_ts',
        password='b3trading_ts_pass'
    )
    
    logger.info(f"📊 Coletando {len(B3_STOCKS)} ativos...")
    
    for ticker in B3_STOCKS:
        try:
            symbol = ticker.replace('.SA', '')
            logger.info(f"⏳ Baixando {symbol}...")
            
            # Baixar dados históricos
            stock = yf.Ticker(ticker)
            df = stock.history(start='2023-01-01', end='2026-01-15', interval='1d')
            
            if df.empty:
                logger.warning(f"⚠️ {symbol}: Sem dados")
                continue
            
            # Inserir no banco
            inserted = 0
            for index, row in df.iterrows():
                try:
                    await conn.execute("""
                        INSERT INTO ohlcv_data (time, symbol, timeframe, open, high, low, close, volume)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                        ON CONFLICT (time, symbol, timeframe) DO NOTHING
                    """, 
                        index.to_pydatetime(),
                        symbol,
                        '1d',
                        float(row['Open']),
                        float(row['High']),
                        float(row['Low']),
                        float(row['Close']),
                        int(row['Volume'])
                    )
                    inserted += 1
                except Exception as e:
                    logger.error(f"Erro ao inserir linha: {e}")
                    continue
            
            logger.success(f"✅ {symbol}: {inserted} barras inseridas")
            
        except Exception as e:
            logger.error(f"❌ Erro em {ticker}: {e}")
            continue
    
    await conn.close()
    logger.success("🎉 Coleta finalizada!")


if __name__ == '__main__':
    asyncio.run(populate_stocks())
