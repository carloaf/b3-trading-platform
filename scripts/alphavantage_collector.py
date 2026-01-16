#!/usr/bin/env python3
"""
Alpha Vantage Data Collector for B3 Stocks
==========================================

Free Tier Limits:
- 5 API calls per minute
- 25 API calls per day
- Daily: 20+ years full history
- Intraday: 1-2 months (outputsize=full)

Usage:
    python alphavantage_collector.py --symbols ITUB4,VALE3 --api-key YOUR_KEY

Get free API key: https://www.alphavantage.co/support/#api-key
"""

import asyncio
import asyncpg
import httpx
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import argparse
import sys
import time
import os

class AlphaVantageCollector:
    """Alpha Vantage data collector with rate limiting"""
    
    def __init__(self, api_key: str, db_config: dict):
        self.api_key = api_key
        self.db_config = db_config
        self.base_url = "https://www.alphavantage.co/query"
        self.rate_limit_delay = 12  # 5 req/min = 12 seconds between calls
        self.daily_limit = 25
        self.calls_made = 0
        self.last_call_time = None
        
        # B3 to US symbol mapping (Alpha Vantage uses different symbols)
        self.symbol_mapping = {
            'ITUB4': 'ITUB4.SAO',  # Itaú Unibanco
            'VALE3': 'VALE3.SAO',  # Vale
            'PETR4': 'PETR4.SAO',  # Petrobras
            'MGLU3': 'MGLU3.SAO',  # Magazine Luiza
            'BBDC4': 'BBDC4.SAO',  # Bradesco
            'ABEV3': 'ABEV3.SAO',  # Ambev
            'WEGE3': 'WEGE3.SAO',  # WEG
            'RENT3': 'RENT3.SAO',  # Localiza
            'SUZB3': 'SUZB3.SAO',  # Suzano
            'B3SA3': 'B3SA3.SAO',  # B3
        }
    
    async def _wait_for_rate_limit(self):
        """Enforce rate limiting between API calls"""
        if self.last_call_time:
            elapsed = time.time() - self.last_call_time
            if elapsed < self.rate_limit_delay:
                wait_time = self.rate_limit_delay - elapsed
                print(f"  ⏳ Rate limit: waiting {wait_time:.1f}s...")
                await asyncio.sleep(wait_time)
        
        self.last_call_time = time.time()
        self.calls_made += 1
        
        if self.calls_made >= self.daily_limit:
            print(f"\n⚠️  Daily limit reached ({self.daily_limit} calls)")
            print("   Resume tomorrow or upgrade to premium plan")
            return False
        
        return True
    
    def _get_alpha_symbol(self, b3_symbol: str) -> str:
        """Convert B3 symbol to Alpha Vantage format"""
        return self.symbol_mapping.get(b3_symbol, f"{b3_symbol}.SAO")
    
    async def collect_daily(self, symbol: str, outputsize: str = 'compact') -> Optional[pd.DataFrame]:
        """
        Collect daily data from Alpha Vantage
        
        Args:
            symbol: B3 symbol (e.g., 'ITUB4')
            outputsize: 'compact' (100 days) or 'full' (20+ years)
        
        Note: Free tier may have issues with 'full' for some symbols.
              'compact' works reliably and provides 100 recent bars.
        """
        alpha_symbol = self._get_alpha_symbol(symbol)
        
        print(f"\n📊 Daily Data - {symbol}")
        print(f"   Alpha Vantage Symbol: {alpha_symbol}")
        print(f"   Output Size: {outputsize}")
        
        if not await self._wait_for_rate_limit():
            return None
        
        params = {
            'function': 'TIME_SERIES_DAILY',
            'symbol': alpha_symbol,
            'outputsize': outputsize,
            'apikey': self.api_key,
            'datatype': 'json'
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                print(f"   📡 Fetching... (call {self.calls_made}/{self.daily_limit})")
                response = await client.get(self.base_url, params=params)
                response.raise_for_status()
                data = response.json()
            
            # Check for API errors
            if 'Error Message' in data:
                print(f"   ❌ API Error: {data['Error Message']}")
                return None
            
            if 'Note' in data:
                print(f"   ⚠️  API Note: {data['Note']}")
                return None
            
            if 'Time Series (Daily)' not in data:
                print(f"   ❌ No daily data returned")
                print(f"   Response keys: {list(data.keys())}")
                return None
            
            # Parse time series data
            time_series = data['Time Series (Daily)']
            
            rows = []
            for date_str, values in time_series.items():
                rows.append({
                    'timestamp': datetime.strptime(date_str, '%Y-%m-%d'),
                    'open': float(values['1. open']),
                    'high': float(values['2. high']),
                    'low': float(values['3. low']),
                    'close': float(values['4. close']),
                    'volume': int(values['5. volume'])
                })
            
            df = pd.DataFrame(rows)
            df = df.sort_values('timestamp').reset_index(drop=True)
            
            print(f"   ✅ Downloaded {len(df)} bars")
            print(f"      Range: {df['timestamp'].min().date()} → {df['timestamp'].max().date()}")
            
            return df
            
        except httpx.HTTPError as e:
            print(f"   ❌ HTTP Error: {e}")
            return None
        except Exception as e:
            print(f"   ❌ Error: {e}")
            return None
    
    async def collect_intraday(self, symbol: str, interval: str = '60min', outputsize: str = 'compact') -> Optional[pd.DataFrame]:
        """
        Collect intraday data from Alpha Vantage
        
        Args:
            symbol: B3 symbol (e.g., 'ITUB4')
            interval: '1min', '5min', '15min', '30min', '60min'
            outputsize: 'compact' (100 bars) or 'full' (1-2 months)
        
        Note: Free tier may have issues with 'full' for some symbols.
              'compact' works reliably and provides 100 recent bars.
        """
        alpha_symbol = self._get_alpha_symbol(symbol)
        
        print(f"\n⏰ Intraday Data - {symbol}")
        print(f"   Alpha Vantage Symbol: {alpha_symbol}")
        print(f"   Interval: {interval}")
        print(f"   Output Size: {outputsize}")
        
        if not await self._wait_for_rate_limit():
            return None
        
        params = {
            'function': 'TIME_SERIES_INTRADAY',
            'symbol': alpha_symbol,
            'interval': interval,
            'outputsize': outputsize,
            'apikey': self.api_key,
            'datatype': 'json'
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                print(f"   📡 Fetching... (call {self.calls_made}/{self.daily_limit})")
                response = await client.get(self.base_url, params=params)
                response.raise_for_status()
                data = response.json()
            
            # Check for API errors
            if 'Error Message' in data:
                print(f"   ❌ API Error: {data['Error Message']}")
                return None
            
            if 'Note' in data:
                print(f"   ⚠️  API Note: {data['Note']}")
                return None
            
            time_series_key = f'Time Series ({interval})'
            if time_series_key not in data:
                print(f"   ❌ No intraday data returned")
                print(f"   Response keys: {list(data.keys())}")
                return None
            
            # Parse time series data
            time_series = data[time_series_key]
            
            rows = []
            for datetime_str, values in time_series.items():
                rows.append({
                    'timestamp': datetime.strptime(datetime_str, '%Y-%m-%d %H:%M:%S'),
                    'open': float(values['1. open']),
                    'high': float(values['2. high']),
                    'low': float(values['3. low']),
                    'close': float(values['4. close']),
                    'volume': int(values['5. volume'])
                })
            
            df = pd.DataFrame(rows)
            df = df.sort_values('timestamp').reset_index(drop=True)
            
            print(f"   ✅ Downloaded {len(df)} bars")
            if len(df) > 0:
                print(f"      Range: {df['timestamp'].min()} → {df['timestamp'].max()}")
            
            return df
            
        except httpx.HTTPError as e:
            print(f"   ❌ HTTP Error: {e}")
            return None
        except Exception as e:
            print(f"   ❌ Error: {e}")
            return None
    
    async def save_to_db(self, df: pd.DataFrame, symbol: str, timeframe: str):
        """Save data to TimescaleDB"""
        if df is None or len(df) == 0:
            return
        
        table = 'ohlcv_1d' if timeframe == '1d' else 'ohlcv_1h'
        
        try:
            conn = await asyncpg.connect(**self.db_config)
            
            # Insert data
            inserted = 0
            for _, row in df.iterrows():
                try:
                    await conn.execute(f"""
                        INSERT INTO {table} (timestamp, symbol, open, high, low, close, volume)
                        VALUES ($1, $2, $3, $4, $5, $6, $7)
                        ON CONFLICT (timestamp, symbol) DO UPDATE
                        SET open = EXCLUDED.open,
                            high = EXCLUDED.high,
                            low = EXCLUDED.low,
                            close = EXCLUDED.close,
                            volume = EXCLUDED.volume
                    """, row['timestamp'], symbol, 
                        float(row['open']), float(row['high']), 
                        float(row['low']), float(row['close']), 
                        int(row['volume']))
                    inserted += 1
                except Exception as e:
                    pass  # Skip duplicates
            
            await conn.close()
            print(f"   💾 Saved {inserted} bars to {table}")
            
        except Exception as e:
            print(f"   ❌ Database error: {e}")
    
    async def collect_symbol(self, symbol: str, include_intraday: bool = True):
        """Collect both daily and intraday data for a symbol"""
        print(f"\n{'='*70}")
        print(f"📈 COLLECTING: {symbol}")
        print(f"{'='*70}")
        
        # Collect daily data (100 days with compact)
        df_daily = await self.collect_daily(symbol, outputsize='compact')
        if df_daily is not None:
            await self.save_to_db(df_daily, symbol, '1d')
        
        # Collect intraday data (100 bars with compact)
        if include_intraday and self.calls_made < self.daily_limit:
            df_hourly = await self.collect_intraday(symbol, interval='60min', outputsize='compact')
            if df_hourly is not None:
                await self.save_to_db(df_hourly, symbol, '1h')


async def main():
    parser = argparse.ArgumentParser(
        description='Alpha Vantage Data Collector for B3 Stocks',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single symbol (daily + hourly)
  python alphavantage_collector.py --symbols ITUB4 --api-key YOUR_KEY
  
  # Multiple symbols
  python alphavantage_collector.py --symbols ITUB4,VALE3,PETR4 --api-key YOUR_KEY
  
  # Daily only (to save API calls)
  python alphavantage_collector.py --symbols ITUB4 --api-key YOUR_KEY --daily-only

Get free API key: https://www.alphavantage.co/support/#api-key
Free tier: 5 calls/minute, 25 calls/day
        """
    )
    
    parser.add_argument('--symbols', required=True, help='Comma-separated B3 symbols (e.g., ITUB4,VALE3)')
    parser.add_argument('--api-key', required=True, help='Alpha Vantage API key')
    parser.add_argument('--daily-only', action='store_true', help='Collect daily data only (skip intraday)')
    parser.add_argument('--db-host', default='localhost', help='Database host')
    parser.add_argument('--db-port', default=5433, type=int, help='Database port')
    parser.add_argument('--db-name', default='trading_timescale', help='Database name')
    parser.add_argument('--db-user', default='trading_user', help='Database user')
    parser.add_argument('--db-password', default='trading_pass', help='Database password')
    
    args = parser.parse_args()
    
    # Parse symbols
    symbols = [s.strip().upper() for s in args.symbols.split(',')]
    
    # Database config
    db_config = {
        'host': args.db_host,
        'port': args.db_port,
        'database': args.db_name,
        'user': args.db_user,
        'password': args.db_password
    }
    
    # Initialize collector
    collector = AlphaVantageCollector(args.api_key, db_config)
    
    print("🌎 ALPHA VANTAGE DATA COLLECTOR")
    print("="*70)
    print(f"📊 Symbols: {', '.join(symbols)}")
    print(f"🔑 API Key: {args.api_key[:8]}...{args.api_key[-4:]}")
    print(f"📈 Mode: {'Daily only' if args.daily_only else 'Daily + Hourly'}")
    print(f"⚠️  Limits: 5 calls/min, 25 calls/day")
    print(f"📊 Estimated calls: {len(symbols) * (1 if args.daily_only else 2)}")
    print("="*70)
    
    # Check if we can collect all symbols
    estimated_calls = len(symbols) * (1 if args.daily_only else 2)
    if estimated_calls > 25:
        print(f"\n⚠️  WARNING: Need {estimated_calls} calls but limit is 25/day")
        print(f"   Will collect partial data. Run again tomorrow for remaining symbols.")
        input("\nPress Enter to continue or Ctrl+C to cancel...")
    
    # Collect data
    start_time = time.time()
    
    for i, symbol in enumerate(symbols, 1):
        if collector.calls_made >= collector.daily_limit:
            print(f"\n⚠️  Daily limit reached. Stopping.")
            break
        
        print(f"\n[{i}/{len(symbols)}]")
        await collector.collect_symbol(symbol, include_intraday=not args.daily_only)
    
    elapsed = time.time() - start_time
    
    print(f"\n{'='*70}")
    print(f"✅ COLLECTION COMPLETE")
    print(f"{'='*70}")
    print(f"   API Calls Used: {collector.calls_made}/{collector.daily_limit}")
    print(f"   Remaining Today: {collector.daily_limit - collector.calls_made}")
    print(f"   Time Elapsed: {elapsed/60:.1f} minutes")
    print(f"{'='*70}")


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(1)
