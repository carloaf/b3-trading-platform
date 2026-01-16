#!/usr/bin/env python3
"""
Finnhub Data Collector for B3 Stocks
=====================================

Free Tier Limits:
- 60 API calls per minute
- Stock candles with multiple resolutions (1, 5, 15, 30, 60, D, W, M)
- Real-time and historical data

Usage:
    python finnhub_collector.py --symbols ITUB4,VALE3 --api-key YOUR_KEY

Get free API key: https://finnhub.io/register
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

class FinnhubCollector:
    """Finnhub data collector with rate limiting"""
    
    def __init__(self, api_key: str, db_config: dict):
        self.api_key = api_key
        self.db_config = db_config
        self.base_url = "https://finnhub.io/api/v1"
        self.rate_limit_delay = 1  # 60 req/min = 1 second between calls
        self.calls_made = 0
        self.last_call_time = None
        
        # B3 symbol mapping (Finnhub may use different formats)
        # Testing different formats: ITUB4.SA, ITUB4.SAO, SA:ITUB4
        self.symbol_formats = [
            lambda s: f"{s}.SA",      # Yahoo Finance style
            lambda s: f"{s}.SAO",     # Alternative
            lambda s: f"SA:{s}",      # Exchange prefix
            lambda s: f"BVMF:{s}",    # BVMF exchange
        ]
    
    async def _wait_for_rate_limit(self):
        """Enforce rate limiting between API calls"""
        if self.last_call_time:
            elapsed = time.time() - self.last_call_time
            if elapsed < self.rate_limit_delay:
                wait_time = self.rate_limit_delay - elapsed
                await asyncio.sleep(wait_time)
        
        self.last_call_time = time.time()
        self.calls_made += 1
    
    async def _test_symbol_format(self, b3_symbol: str) -> Optional[str]:
        """Test different symbol formats to find the correct one"""
        print(f"\n🔍 Testing symbol formats for {b3_symbol}")
        
        # Try to get current quote to validate symbol
        for format_func in self.symbol_formats:
            test_symbol = format_func(b3_symbol)
            
            try:
                await self._wait_for_rate_limit()
                
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(
                        f"{self.base_url}/quote",
                        params={'symbol': test_symbol, 'token': self.api_key}
                    )
                    data = response.json()
                
                # Check if we got valid data
                if data and 'c' in data and data['c'] > 0:
                    print(f"   ✅ Found: {test_symbol} (price: {data['c']})")
                    return test_symbol
                else:
                    print(f"   ❌ {test_symbol}: No data")
                    
            except Exception as e:
                print(f"   ❌ {test_symbol}: {e}")
        
        print(f"   ⚠️  No valid format found for {b3_symbol}")
        return None
    
    async def collect_candles(self, symbol: str, resolution: str, days_back: int) -> Optional[pd.DataFrame]:
        """
        Collect candle data from Finnhub
        
        Args:
            symbol: Finnhub symbol (e.g., 'ITUB4.SA')
            resolution: '1', '5', '15', '30', '60', 'D', 'W', 'M'
            days_back: Number of days of historical data
        """
        # Calculate timestamps
        end_time = int(datetime.now().timestamp())
        start_time = int((datetime.now() - timedelta(days=days_back)).timestamp())
        
        resolution_name = {
            '1': '1min', '5': '5min', '15': '15min',
            '30': '30min', '60': '60min', 'D': 'Daily',
            'W': 'Weekly', 'M': 'Monthly'
        }.get(resolution, resolution)
        
        print(f"\n📊 {resolution_name} Candles - {symbol}")
        print(f"   Period: {datetime.fromtimestamp(start_time).date()} → {datetime.fromtimestamp(end_time).date()}")
        
        await self._wait_for_rate_limit()
        
        params = {
            'symbol': symbol,
            'resolution': resolution,
            'from': start_time,
            'to': end_time,
            'token': self.api_key
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                print(f"   📡 Fetching... (call {self.calls_made})")
                response = await client.get(f"{self.base_url}/stock/candle", params=params)
                response.raise_for_status()
                data = response.json()
            
            # Check for errors
            if 's' not in data or data['s'] != 'ok':
                error_msg = data.get('s', 'unknown error')
                print(f"   ❌ API Error: {error_msg}")
                return None
            
            # Check if we have data
            if 'c' not in data or not data['c']:
                print(f"   ❌ No candle data returned")
                return None
            
            # Parse candles
            rows = []
            for i in range(len(data['t'])):
                rows.append({
                    'timestamp': datetime.fromtimestamp(data['t'][i]),
                    'open': float(data['o'][i]),
                    'high': float(data['h'][i]),
                    'low': float(data['l'][i]),
                    'close': float(data['c'][i]),
                    'volume': int(data['v'][i])
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
    
    async def save_to_db(self, df: pd.DataFrame, b3_symbol: str, timeframe: str):
        """Save data to TimescaleDB"""
        if df is None or len(df) == 0:
            return
        
        table = 'ohlcv_1d' if timeframe == 'D' else 'ohlcv_1h'
        
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
                    """, row['timestamp'], b3_symbol,
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
    
    async def collect_symbol(self, b3_symbol: str, include_intraday: bool = True):
        """Collect both daily and intraday data for a symbol"""
        print(f"\n{'='*70}")
        print(f"📈 COLLECTING: {b3_symbol}")
        print(f"{'='*70}")
        
        # Find correct symbol format
        finnhub_symbol = await self._test_symbol_format(b3_symbol)
        
        if not finnhub_symbol:
            print(f"   ⚠️  Symbol {b3_symbol} not available on Finnhub")
            return
        
        # Collect daily data (last 730 days = 2 years)
        df_daily = await self.collect_candles(finnhub_symbol, 'D', 730)
        if df_daily is not None:
            await self.save_to_db(df_daily, b3_symbol, 'D')
        
        # Collect intraday data (last 90 days)
        if include_intraday:
            df_hourly = await self.collect_candles(finnhub_symbol, '60', 90)
            if df_hourly is not None:
                await self.save_to_db(df_hourly, b3_symbol, '60')


async def main():
    parser = argparse.ArgumentParser(
        description='Finnhub Data Collector for B3 Stocks',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single symbol (daily + hourly)
  python finnhub_collector.py --symbols ITUB4 --api-key YOUR_KEY
  
  # Multiple symbols
  python finnhub_collector.py --symbols ITUB4,VALE3,PETR4 --api-key YOUR_KEY
  
  # Daily only
  python finnhub_collector.py --symbols ITUB4 --api-key YOUR_KEY --daily-only

Get free API key: https://finnhub.io/register
Free tier: 60 calls/minute
        """
    )
    
    parser.add_argument('--symbols', required=True, help='Comma-separated B3 symbols (e.g., ITUB4,VALE3)')
    parser.add_argument('--api-key', required=True, help='Finnhub API key')
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
    collector = FinnhubCollector(args.api_key, db_config)
    
    print("📊 FINNHUB DATA COLLECTOR")
    print("="*70)
    print(f"📈 Symbols: {', '.join(symbols)}")
    print(f"🔑 API Key: {args.api_key[:8]}...{args.api_key[-4:]}")
    print(f"📊 Mode: {'Daily only' if args.daily_only else 'Daily + Hourly'}")
    print(f"⚡ Rate Limit: 60 calls/minute")
    print("="*70)
    
    # Collect data
    start_time = time.time()
    
    for i, symbol in enumerate(symbols, 1):
        print(f"\n[{i}/{len(symbols)}]")
        await collector.collect_symbol(symbol, include_intraday=not args.daily_only)
    
    elapsed = time.time() - start_time
    
    print(f"\n{'='*70}")
    print(f"✅ COLLECTION COMPLETE")
    print(f"{'='*70}")
    print(f"   API Calls Used: {collector.calls_made}")
    print(f"   Time Elapsed: {elapsed/60:.1f} minutes")
    print(f"{'='*70}")


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(1)
