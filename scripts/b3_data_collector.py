#!/usr/bin/env python3
"""
B3 Data Collector - Multi-Source Strategy
==========================================
Coleta dados históricos de múltiplas fontes para ações B3:
- Yahoo Finance: Daily data (anos de histórico, gratuito)
- Alpha Vantage: Intraday data (free tier com limites)
- BRAPI: Fallback para dados recentes (3mo)

Uso:
    python scripts/b3_data_collector.py --symbol ITUB4 --years 2
    python scripts/b3_data_collector.py --symbols ITUB4,VALE3,MGLU3 --timeframes 1d,1h
"""

import asyncio
import asyncpg
import yfinance as yf
import argparse
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import pandas as pd
import time


class B3DataCollector:
    """Multi-source data collector for Brazilian stocks"""
    
    def __init__(self, db_url: str):
        self.db_url = db_url
        self.alpha_vantage_key = os.getenv('ALPHA_VANTAGE_KEY', '')
        self.brapi_token = os.getenv('BRAPI_TOKEN', '')
        
    async def connect_db(self):
        """Connect to TimescaleDB"""
        return await asyncpg.connect(self.db_url)
    
    def _clean_yfinance_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Clean and validate Yahoo Finance data
        Fixes timezone issues and invalid values
        """
        if df.empty:
            return df
        
        # Remove timezone info if present
        if hasattr(df.index, 'tz') and df.index.tz is not None:
            df.index = df.index.tz_localize(None)
        
        # Drop rows with all NaN values
        df = df.dropna(how='all')
        
        # Forward fill missing values (max 5 periods)
        df = df.fillna(method='ffill', limit=5)
        
        # Drop remaining NaN rows
        df = df.dropna()
        
        # Ensure positive prices
        price_cols = ['Open', 'High', 'Low', 'Close']
        for col in price_cols:
            if col in df.columns:
                df = df[df[col] > 0]
        
        # Validate OHLC relationships
        if all(col in df.columns for col in price_cols):
            df = df[
                (df['High'] >= df['Low']) &
                (df['High'] >= df['Open']) &
                (df['High'] >= df['Close']) &
                (df['Low'] <= df['Open']) &
                (df['Low'] <= df['Close'])
            ]
        
        return df
    
    async def collect_daily_yahoo(
        self,
        symbol: str,
        years: int = 2,
        verbose: bool = True
    ) -> int:
        """
        Collect daily data from Yahoo Finance
        Returns number of bars inserted
        """
        conn = await self.connect_db()
        
        # Yahoo Finance requires .SA suffix for B3 stocks
        yf_symbol = f'{symbol}.SA'
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365 * years)
        
        if verbose:
            print(f'\n📊 Yahoo Finance - {symbol}')
            print('-' * 60)
            print(f'  Symbol: {yf_symbol}')
            print(f'  Period: {start_date.date()} → {end_date.date()}')
        
        try:
            # Download data
            if verbose:
                print(f'  📡 Downloading...')
            
            ticker = yf.Ticker(yf_symbol)
            df = ticker.history(start=start_date, end=end_date, interval='1d')
            
            if df.empty:
                if verbose:
                    print(f'  ❌ No data returned')
                await conn.close()
                return 0
            
            # Clean data
            df = self._clean_yfinance_data(df)
            
            if df.empty:
                if verbose:
                    print(f'  ❌ All data invalid after cleaning')
                await conn.close()
                return 0
            
            if verbose:
                print(f'  ✅ Downloaded {len(df)} bars')
                print(f'  📅 Range: {df.index[0].date()} → {df.index[-1].date()}')
            
            # Insert into database
            inserted = 0
            for timestamp, row in df.iterrows():
                try:
                    await conn.execute('''
                        INSERT INTO ohlcv_1d (time, symbol, open, high, low, close, volume)
                        VALUES ($1, $2, $3, $4, $5, $6, $7)
                        ON CONFLICT DO NOTHING
                    ''', timestamp.to_pydatetime(), symbol, 
                         float(row['Open']), float(row['High']), 
                         float(row['Low']), float(row['Close']), 
                         int(row['Volume']))
                    inserted += 1
                except Exception as e:
                    if verbose:
                        print(f'  ⚠️  Error inserting bar {timestamp}: {e}')
            
            if verbose:
                print(f'  💾 Inserted: {inserted} bars')
            
            await conn.close()
            return inserted
            
        except Exception as e:
            if verbose:
                print(f'  ❌ Error: {e}')
            await conn.close()
            return 0
    
    async def collect_intraday_yahoo(
        self,
        symbol: str,
        days: int = 60,
        interval: str = '1h',
        verbose: bool = True
    ) -> int:
        """
        Collect intraday data from Yahoo Finance
        Yahoo provides up to 60 days of hourly data
        """
        conn = await self.connect_db()
        
        yf_symbol = f'{symbol}.SA'
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        if verbose:
            print(f'\n⏰ Yahoo Finance Intraday - {symbol}')
            print('-' * 60)
            print(f'  Symbol: {yf_symbol}')
            print(f'  Interval: {interval}')
            print(f'  Period: {start_date.date()} → {end_date.date()}')
        
        try:
            if verbose:
                print(f'  📡 Downloading...')
            
            ticker = yf.Ticker(yf_symbol)
            df = ticker.history(start=start_date, end=end_date, interval=interval)
            
            if df.empty:
                if verbose:
                    print(f'  ❌ No data returned')
                await conn.close()
                return 0
            
            df = self._clean_yfinance_data(df)
            
            if df.empty:
                if verbose:
                    print(f'  ❌ All data invalid after cleaning')
                await conn.close()
                return 0
            
            if verbose:
                print(f'  ✅ Downloaded {len(df)} bars')
                print(f'  📅 Range: {df.index[0]} → {df.index[-1]}')
            
            # Map interval to table
            table_map = {'1h': 'ohlcv_1h', '60m': 'ohlcv_1h'}
            table = table_map.get(interval, 'ohlcv_1h')
            
            inserted = 0
            for timestamp, row in df.iterrows():
                try:
                    await conn.execute(f'''
                        INSERT INTO {table} (time, symbol, open, high, low, close, volume)
                        VALUES ($1, $2, $3, $4, $5, $6, $7)
                        ON CONFLICT DO NOTHING
                    ''', timestamp.to_pydatetime(), symbol,
                         float(row['Open']), float(row['High']),
                         float(row['Low']), float(row['Close']),
                         int(row['Volume']))
                    inserted += 1
                except Exception as e:
                    if verbose:
                        print(f'  ⚠️  Error inserting bar {timestamp}: {e}')
            
            if verbose:
                print(f'  💾 Inserted: {inserted} bars into {table}')
            
            await conn.close()
            return inserted
            
        except Exception as e:
            if verbose:
                print(f'  ❌ Error: {e}')
            await conn.close()
            return 0
    
    async def collect_symbol_all_timeframes(
        self,
        symbol: str,
        years: int = 2,
        verbose: bool = True
    ) -> Dict[str, int]:
        """
        Collect all timeframes for a symbol
        Returns dict with counts per timeframe
        """
        results = {}
        
        # Daily data (2 years)
        daily_count = await self.collect_daily_yahoo(symbol, years, verbose)
        results['1d'] = daily_count
        
        # Small delay between requests
        await asyncio.sleep(1)
        
        # Hourly data (60 days max for Yahoo)
        hourly_count = await self.collect_intraday_yahoo(symbol, 60, '1h', verbose)
        results['1h'] = hourly_count
        
        return results


async def main():
    parser = argparse.ArgumentParser(
        description='B3 Data Collector - Multi-Source Strategy'
    )
    parser.add_argument(
        '--symbols',
        type=str,
        required=True,
        help='Símbolos separados por vírgula (ex: ITUB4,VALE3,MGLU3)'
    )
    parser.add_argument(
        '--years',
        type=int,
        default=2,
        help='Anos de histórico para dados diários (padrão: 2)'
    )
    parser.add_argument(
        '--db-url',
        type=str,
        default='postgresql://b3trading_ts:b3trading_ts_pass@b3-timescaledb:5432/b3trading_market',
        help='URL de conexão do banco de dados'
    )
    
    args = parser.parse_args()
    
    symbols = [s.strip().upper() for s in args.symbols.split(',')]
    
    collector = B3DataCollector(db_url=args.db_url)
    
    print(f'\n{"=" * 80}')
    print(f'🇧🇷 B3 DATA COLLECTOR - Multi-Source Strategy')
    print(f'{"=" * 80}')
    print(f'📊 Símbolos: {", ".join(symbols)}')
    print(f'📅 Período: {args.years} anos (daily) + 60 dias (hourly)')
    print(f'🔄 Fonte: Yahoo Finance (.SA suffix)')
    print(f'{"=" * 80}\n')
    
    all_results = {}
    
    for idx, symbol in enumerate(symbols, 1):
        print(f'\n[{idx}/{len(symbols)}] 📈 {symbol}')
        print('=' * 80)
        
        result = await collector.collect_symbol_all_timeframes(
            symbol=symbol,
            years=args.years,
            verbose=True
        )
        
        all_results[symbol] = result
        
        # Rate limiting between symbols
        if idx < len(symbols):
            print(f'\n⏳ Rate limit: aguardando 2s...')
            await asyncio.sleep(2)
    
    print(f'\n{"=" * 80}')
    print(f'📈 RESUMO FINAL')
    print(f'{"=" * 80}')
    
    total_daily = 0
    total_hourly = 0
    
    for symbol, result in all_results.items():
        daily = result.get('1d', 0)
        hourly = result.get('1h', 0)
        total_daily += daily
        total_hourly += hourly
        
        print(f'\n{symbol}:')
        print(f'  📅 Daily:  {daily} barras')
        print(f'  ⏰ Hourly: {hourly} barras')
    
    print(f'\n{"=" * 80}')
    print(f'TOTAL:')
    print(f'  📅 Daily:  {total_daily} barras')
    print(f'  ⏰ Hourly: {total_hourly} barras')
    print(f'  📊 Total:  {total_daily + total_hourly} barras')
    print(f'{"=" * 80}\n')


if __name__ == '__main__':
    asyncio.run(main())
