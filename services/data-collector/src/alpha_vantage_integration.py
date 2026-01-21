"""
Alpha Vantage Integration - Dados Intraday Reais para B3
=========================================================

Alternativa ao Yahoo Finance (que está bloqueado).
Alpha Vantage oferece 500 requests/dia no plano grátis.

API Key: Obter em https://www.alphavantage.co/support/#api-key

Autor: Stock-IndiceDev Assistant
Data: 19/01/2026
"""

import asyncio
import asyncpg
import requests
import pandas as pd
from datetime import datetime
from typing import Optional, List
from loguru import logger
import time
import os

# Configurações
DB_CONFIG = {
    'host': 'timescaledb',
    'port': 5432,
    'database': 'b3trading_market',
    'user': 'b3trading_ts',
    'password': 'b3trading_ts_pass'
}

ALPHA_VANTAGE_BASE_URL = 'https://www.alphavantage.co/query'


class AlphaVantageIntegration:
    """
    Integração com Alpha Vantage API para dados intraday B3
    
    Plano Grátis: 500 requests/dia, 5 requests/minuto
    """
    
    def __init__(self, api_key: str = None):
        """
        Args:
            api_key: Alpha Vantage API key (obter em alphavantage.co)
        """
        self.api_key = api_key or os.getenv('ALPHA_VANTAGE_API_KEY')
        
        if not self.api_key:
            logger.warning("⚠️ ALPHA_VANTAGE_API_KEY não configurado")
            logger.info("   Obtenha em: https://www.alphavantage.co/support/#api-key")
            logger.info("   Configure: export ALPHA_VANTAGE_API_KEY='sua_key'")
        
        self.session = requests.Session()
    
    def convert_b3_to_alpha_vantage(self, symbol: str) -> str:
        """
        Converte ticker B3 para formato Alpha Vantage
        
        B3: PETR4 → Alpha Vantage: BVMF:PETR4 ou PETR4.SAO
        
        Args:
            symbol: Ticker B3
        
        Returns:
            Ticker Alpha Vantage
        """
        # Tentar ambos formatos (BVMF: é mais confiável)
        return f"BVMF:{symbol}"
    
    def get_intraday_data(
        self,
        symbol: str,
        interval: str = '60min',
        outputsize: str = 'compact'
    ) -> Optional[pd.DataFrame]:
        """
        Baixa dados intraday da Alpha Vantage
        
        Args:
            symbol: Ticker B3 (ex: PETR4)
            interval: 1min, 5min, 15min, 30min, 60min
            outputsize: compact (últimos 100 pontos) ou full (mês completo)
        
        Returns:
            DataFrame com [time, open, high, low, close, volume, symbol]
        """
        if not self.api_key:
            logger.error("❌ API key não configurada")
            return None
        
        av_symbol = self.convert_b3_to_alpha_vantage(symbol)
        
        params = {
            'function': 'TIME_SERIES_INTRADAY',
            'symbol': av_symbol,
            'interval': interval,
            'outputsize': outputsize,
            'apikey': self.api_key
        }
        
        logger.info(f"📥 Baixando {av_symbol} (interval={interval}, size={outputsize})")
        
        try:
            response = self.session.get(ALPHA_VANTAGE_BASE_URL, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            # Verificar erros
            if 'Error Message' in data:
                logger.error(f"❌ Alpha Vantage error: {data['Error Message']}")
                return None
            
            if 'Note' in data:
                logger.warning(f"⚠️ Rate limit: {data['Note']}")
                return None
            
            if 'Information' in data:
                logger.warning(f"⚠️ {data['Information']}")
                return None
            
            # Parsear dados
            time_series_key = f'Time Series ({interval})'
            
            if time_series_key not in data:
                logger.error(f"❌ Chave {time_series_key} não encontrada. Keys: {list(data.keys())}")
                return None
            
            time_series = data[time_series_key]
            
            if not time_series:
                logger.warning(f"⚠️ Sem dados para {symbol}")
                return None
            
            # Converter para DataFrame
            records = []
            for timestamp, values in time_series.items():
                records.append({
                    'time': pd.to_datetime(timestamp),
                    'open': float(values['1. open']),
                    'high': float(values['2. high']),
                    'low': float(values['3. low']),
                    'close': float(values['4. close']),
                    'volume': int(values['5. volume']),
                    'symbol': symbol
                })
            
            df = pd.DataFrame(records)
            df = df.sort_values('time')
            
            logger.success(f"✅ {len(df)} registros baixados para {symbol}")
            logger.debug(f"   Range: {df['time'].min()} → {df['time'].max()}")
            
            return df
        
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Erro HTTP: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Erro ao processar {symbol}: {e}")
            return None
    
    async def save_to_timescaledb(self, df: pd.DataFrame, table: str = 'ohlcv_60m'):
        """
        Salva dados intraday no TimescaleDB
        
        Args:
            df: DataFrame com dados
            table: Nome da tabela (ohlcv_1m, ohlcv_15m, ohlcv_60m, etc.)
        """
        if df is None or df.empty:
            logger.warning("⚠️ DataFrame vazio")
            return
        
        conn = await asyncpg.connect(**DB_CONFIG)
        
        try:
            # Criar tabela
            create_table = f"""
                CREATE TABLE IF NOT EXISTS {table} (
                    time TIMESTAMPTZ NOT NULL,
                    open DOUBLE PRECISION,
                    high DOUBLE PRECISION,
                    low DOUBLE PRECISION,
                    close DOUBLE PRECISION,
                    volume BIGINT,
                    symbol VARCHAR(20) NOT NULL,
                    UNIQUE(time, symbol)
                );
                
                SELECT create_hypertable('{table}', 'time', if_not_exists => TRUE);
                CREATE INDEX IF NOT EXISTS idx_{table}_symbol_time ON {table} (symbol, time DESC);
            """
            
            await conn.execute(create_table)
            logger.info(f"📊 Tabela {table} pronta")
            
            # Inserir dados
            records = []
            for _, row in df.iterrows():
                records.append((
                    row['time'],
                    float(row['open']),
                    float(row['high']),
                    float(row['low']),
                    float(row['close']),
                    int(row['volume']),
                    row['symbol']
                ))
            
            query = f"""
                INSERT INTO {table} (time, open, high, low, close, volume, symbol)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (time, symbol) DO NOTHING
            """
            
            result = await conn.executemany(query, records)
            logger.success(f"✅ {len(records)} registros salvos em {table}")
        
        except Exception as e:
            logger.error(f"❌ Erro ao salvar: {e}")
        
        finally:
            await conn.close()


async def download_batch(
    symbols: List[str],
    interval: str = '60min',
    api_key: str = None,
    save_to_db: bool = True
):
    """
    Download em batch com rate limiting
    
    Args:
        symbols: Lista de tickers B3
        interval: 1min, 5min, 15min, 30min, 60min
        api_key: Alpha Vantage API key
        save_to_db: Salvar no TimescaleDB
    """
    api = AlphaVantageIntegration(api_key)
    
    interval_table_map = {
        '1min': 'ohlcv_1m',
        '5min': 'ohlcv_5m',
        '15min': 'ohlcv_15m',
        '30min': 'ohlcv_30m',
        '60min': 'ohlcv_60m'
    }
    
    table = interval_table_map.get(interval, 'ohlcv_60m')
    
    logger.info("=" * 80)
    logger.info(f"ALPHA VANTAGE DOWNLOAD - Interval: {interval}")
    logger.info("=" * 80)
    logger.info(f"Ativos: {len(symbols)}")
    logger.info(f"Tabela: {table}")
    logger.info(f"Rate limit: 5 requests/minuto (free tier)")
    logger.info("=" * 80)
    
    success = 0
    failed = 0
    
    for i, symbol in enumerate(symbols, 1):
        logger.info(f"[{i}/{len(symbols)}] Processando {symbol}...")
        
        df = api.get_intraday_data(symbol, interval=interval)
        
        if df is not None:
            if save_to_db:
                await api.save_to_timescaledb(df, table=table)
            success += 1
        else:
            failed += 1
        
        # Rate limit: 5 requests/minuto = 12 segundos entre requests
        if i < len(symbols):
            logger.info("   ⏳ Aguardando 12s (rate limit)...")
            time.sleep(12)
    
    logger.info("=" * 80)
    logger.success(f"✅ Download completo!")
    logger.info(f"   Sucesso: {success}/{len(symbols)}")
    logger.info(f"   Falhas: {failed}/{len(symbols)}")
    logger.info("=" * 80)


async def test_single_ticker(symbol: str = 'PETR4', api_key: str = None):
    """Testa download de um único ticker"""
    api = AlphaVantageIntegration(api_key)
    
    logger.info("=" * 80)
    logger.info(f"TESTE: Alpha Vantage - {symbol}")
    logger.info("=" * 80)
    
    # Teste 1: 60min
    logger.info("\n📊 Teste 1: 60min")
    df_60m = api.get_intraday_data(symbol, interval='60min', outputsize='compact')
    
    if df_60m is not None:
        logger.info(f"   Registros: {len(df_60m)}")
        logger.info(f"   Range: {df_60m['time'].min()} → {df_60m['time'].max()}")
        logger.info(f"\n   Últimos 5 registros:")
        print(df_60m.tail())
        
        await api.save_to_timescaledb(df_60m, table='ohlcv_60m')
    
    logger.info("\n" + "=" * 80)
    logger.success("✅ Teste completo!")
    logger.info("=" * 80)


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("""
Alpha Vantage Integration - Dados Intraday B3
==============================================

⚠️ IMPORTANTE: Requer API key (grátis): https://www.alphavantage.co/support/#api-key
   Configure: export ALPHA_VANTAGE_API_KEY='sua_key'

Plano Grátis:
  - 500 requests/dia
  - 5 requests/minuto
  - Dados intraday: últimos 100 pontos (compact) ou mês completo (full)

Uso:
  python alpha_vantage_integration.py test [SYMBOL] [API_KEY]
     Testa download de um ticker
     Exemplo: python alpha_vantage_integration.py test PETR4 YOUR_API_KEY
  
  python alpha_vantage_integration.py download SYMBOL1 SYMBOL2 ... --interval 60min --key YOUR_API_KEY
     Baixa tickers específicos
     Exemplo: python alpha_vantage_integration.py download PETR4 VALE3 --interval 15min --key YOUR_KEY

Intervalos disponíveis:
  1min, 5min, 15min, 30min, 60min

Output size:
  compact: últimos 100 pontos (mais recentes)
  full: mês completo (~1000 pontos)

IMPORTANTE:
  - Rate limit: 12 segundos entre requests (5 req/min)
  - Para baixar 50 ativos: ~10 minutos
  - Dados em UTC (converter para BRT se necessário)
        """)
        sys.exit(1)
    
    command = sys.argv[1]
    
    # Buscar API key dos argumentos ou variável de ambiente
    api_key_arg = None
    for i, arg in enumerate(sys.argv):
        if arg == '--key' and i + 1 < len(sys.argv):
            api_key_arg = sys.argv[i + 1]
            break
    
    if command == 'test':
        symbol = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith('--') else 'PETR4'
        api_key = sys.argv[3] if len(sys.argv) > 3 and not sys.argv[3].startswith('--') else api_key_arg
        asyncio.run(test_single_ticker(symbol, api_key))
    
    elif command == 'download':
        symbols = []
        interval = '60min'
        
        i = 2
        while i < len(sys.argv):
            if sys.argv[i] == '--interval':
                interval = sys.argv[i + 1]
                i += 2
            elif sys.argv[i] == '--key':
                api_key_arg = sys.argv[i + 1]
                i += 2
            else:
                symbols.append(sys.argv[i])
                i += 1
        
        if not symbols:
            print("❌ Especifique pelo menos um símbolo")
            sys.exit(1)
        
        asyncio.run(download_batch(symbols, interval=interval, api_key=api_key_arg))
    
    else:
        print(f"❌ Comando desconhecido: {command}")
        sys.exit(1)
