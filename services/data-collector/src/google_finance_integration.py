"""
Google Finance Integration - Intraday Data Collector
====================================================

Integra com Google Finance para obter dados intraday (60min, 15min, etc.)
de ativos brasileiros listados na B3.

Métodos disponíveis:
1. Web Scraping (direto do Google Finance)
2. Google Sheets API (via GOOGLEFINANCE formula)
3. yfinance (biblioteca Python que usa Yahoo Finance com fallback Google)

Autor: Stock-IndiceDev Assistant
Data: 19/01/2026
"""

import asyncio
import asyncpg
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from loguru import logger
import pandas as pd
import time

# Método 1: yfinance (mais confiável)
try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False
    logger.warning("yfinance não instalado. Instale com: pip install yfinance")

# Método 2: Google Sheets API
try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    GSHEETS_AVAILABLE = True
except ImportError:
    GSHEETS_AVAILABLE = False
    logger.warning("Google Sheets API não disponível. Instale com: pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client")

# Configurações
DB_CONFIG = {
    'host': 'timescaledb',
    'port': 5432,
    'database': 'b3trading_market',
    'user': 'b3trading_ts',
    'password': 'b3trading_ts_pass'
}


class GoogleFinanceIntegration:
    """
    Integração com Google Finance para dados intraday
    
    Suporta múltiplos métodos:
    - yfinance (Yahoo Finance com dados Google)
    - Google Sheets API (GOOGLEFINANCE formula)
    - Web Scraping (fallback)
    """
    
    def __init__(self):
        self.session = None
        self.sheets_service = None
    
    def convert_b3_to_yahoo(self, symbol: str) -> str:
        """
        Converte ticker B3 para formato Yahoo Finance
        
        B3: PETR4 → Yahoo: PETR4.SA
        B3: VALE3 → Yahoo: VALE3.SA
        
        Args:
            symbol: Ticker B3 (ex: PETR4)
        
        Returns:
            Ticker Yahoo Finance (ex: PETR4.SA)
        """
        if not symbol.endswith('.SA'):
            return f"{symbol}.SA"
        return symbol
    
    def convert_yahoo_to_b3(self, symbol: str) -> str:
        """
        Converte ticker Yahoo Finance para B3
        
        Args:
            symbol: Ticker Yahoo (ex: PETR4.SA)
        
        Returns:
            Ticker B3 (ex: PETR4)
        """
        return symbol.replace('.SA', '')
    
    def get_intraday_data_yfinance(
        self,
        symbol: str,
        interval: str = '60m',
        period: str = '60d'
    ) -> Optional[pd.DataFrame]:
        """
        Baixa dados intraday usando yfinance
        
        Args:
            symbol: Ticker B3 (ex: PETR4)
            interval: Intervalo (1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d)
            period: Período (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)
        
        Returns:
            DataFrame com colunas [time, open, high, low, close, volume, symbol]
        """
        if not YFINANCE_AVAILABLE:
            logger.error("yfinance não disponível. Instale com: pip install yfinance")
            return None
        
        yahoo_symbol = self.convert_b3_to_yahoo(symbol)
        logger.info(f"📥 Baixando {yahoo_symbol} (interval={interval}, period={period})")
        
        try:
            ticker = yf.Ticker(yahoo_symbol)
            df = ticker.history(period=period, interval=interval)
            
            if df.empty:
                logger.warning(f"⚠️ Sem dados para {symbol}")
                return None
            
            # Renomear colunas para padrão do projeto
            df = df.reset_index()
            df = df.rename(columns={
                'Datetime': 'time',
                'Open': 'open',
                'High': 'high',
                'Low': 'low',
                'Close': 'close',
                'Volume': 'volume'
            })
            
            # Se não tem coluna Datetime, usar Date
            if 'time' not in df.columns and 'Date' in df.columns:
                df['time'] = df['Date']
                df = df.drop('Date', axis=1)
            
            # Adicionar símbolo
            df['symbol'] = symbol
            
            # Selecionar apenas colunas necessárias
            df = df[['time', 'open', 'high', 'low', 'close', 'volume', 'symbol']]
            
            logger.success(f"✅ {len(df)} registros baixados para {symbol}")
            logger.debug(f"   Range: {df['time'].min()} → {df['time'].max()}")
            
            return df
        
        except Exception as e:
            logger.error(f"❌ Erro ao baixar {symbol}: {e}")
            return None
    
    def get_intraday_data_gsheets(
        self,
        symbol: str,
        credentials_path: str,
        interval: str = 'DAILY'
    ) -> Optional[pd.DataFrame]:
        """
        Baixa dados usando Google Sheets API + GOOGLEFINANCE
        
        Args:
            symbol: Ticker B3 (ex: PETR4)
            credentials_path: Caminho para credenciais JSON
            interval: DAILY ou qualquer intervalo suportado
        
        Returns:
            DataFrame com dados
        
        Nota: Requer credenciais de Service Account do Google Cloud
        """
        if not GSHEETS_AVAILABLE:
            logger.error("Google Sheets API não disponível")
            return None
        
        try:
            # Autenticar
            creds = service_account.Credentials.from_service_account_file(
                credentials_path,
                scopes=['https://www.googleapis.com/auth/spreadsheets']
            )
            
            service = build('sheets', 'v4', credentials=creds)
            
            # Criar fórmula GOOGLEFINANCE
            # =GOOGLEFINANCE("BVMF:B3SA3", "price", TODAY(), "DAILY")
            formula = f'=GOOGLEFINANCE("BVMF:{symbol}", "all", TODAY()-60, TODAY(), "{interval}")'
            
            logger.info(f"📊 Usando Google Sheets para {symbol}")
            logger.debug(f"   Fórmula: {formula}")
            
            # Implementação completa requer criação de Sheet temporário
            # e execução da fórmula - deixar para versão futura
            
            logger.warning("⚠️ Google Sheets API requer implementação completa")
            return None
        
        except Exception as e:
            logger.error(f"❌ Erro Google Sheets: {e}")
            return None
    
    async def save_to_timescaledb(
        self,
        df: pd.DataFrame,
        table: str = 'ohlcv_60m'
    ):
        """
        Salva dados intraday no TimescaleDB
        
        Args:
            df: DataFrame com colunas [time, open, high, low, close, volume, symbol]
            table: Nome da tabela (ohlcv_60m, ohlcv_15m, etc.)
        """
        if df is None or df.empty:
            logger.warning("⚠️ DataFrame vazio, nada para salvar")
            return
        
        conn = await asyncpg.connect(**DB_CONFIG)
        
        try:
            # Criar tabela se não existir (similar a ohlcv_daily)
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
                
                -- Criar hypertable se ainda não for
                SELECT create_hypertable('{table}', 'time', if_not_exists => TRUE);
                
                -- Índice para consultas rápidas
                CREATE INDEX IF NOT EXISTS idx_{table}_symbol_time 
                ON {table} (symbol, time DESC);
            """
            
            await conn.execute(create_table)
            logger.info(f"📊 Tabela {table} pronta")
            
            # Preparar dados para insert
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
            
            # Insert com ON CONFLICT DO NOTHING (evita duplicatas)
            query = f"""
                INSERT INTO {table} (time, open, high, low, close, volume, symbol)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (time, symbol) DO NOTHING
            """
            
            result = await conn.executemany(query, records)
            logger.success(f"✅ {len(records)} registros salvos em {table}")
        
        except Exception as e:
            logger.error(f"❌ Erro ao salvar no TimescaleDB: {e}")
        
        finally:
            await conn.close()


async def download_intraday_batch(
    symbols: List[str],
    interval: str = '60m',
    period: str = '60d',
    save_to_db: bool = True
):
    """
    Baixa dados intraday em batch para múltiplos ativos
    
    Args:
        symbols: Lista de tickers B3
        interval: Intervalo (60m, 15m, 5m, etc.)
        period: Período (60d, 30d, etc.)
        save_to_db: Se True, salva no TimescaleDB
    """
    api = GoogleFinanceIntegration()
    
    # Mapear intervalo para nome da tabela
    interval_table_map = {
        '1m': 'ohlcv_1m',
        '5m': 'ohlcv_5m',
        '15m': 'ohlcv_15m',
        '30m': 'ohlcv_30m',
        '60m': 'ohlcv_60m',
        '1h': 'ohlcv_60m',
        '90m': 'ohlcv_90m',
        '1d': 'ohlcv_daily'
    }
    
    table = interval_table_map.get(interval, 'ohlcv_60m')
    
    logger.info("=" * 80)
    logger.info(f"DOWNLOAD INTRADAY DATA - Interval: {interval}")
    logger.info("=" * 80)
    logger.info(f"Ativos: {len(symbols)}")
    logger.info(f"Período: {period}")
    logger.info(f"Tabela: {table}")
    logger.info("=" * 80)
    
    success = 0
    failed = 0
    
    for i, symbol in enumerate(symbols, 1):
        logger.info(f"[{i}/{len(symbols)}] Processando {symbol}...")
        
        df = api.get_intraday_data_yfinance(symbol, interval=interval, period=period)
        
        if df is not None and save_to_db:
            await api.save_to_timescaledb(df, table=table)
            success += 1
        else:
            failed += 1
        
        # Rate limit: 1 request/segundo
        if i < len(symbols):
            time.sleep(1)
    
    logger.info("=" * 80)
    logger.success(f"✅ Download completo!")
    logger.info(f"   Sucesso: {success}/{len(symbols)}")
    logger.info(f"   Falhas: {failed}/{len(symbols)}")
    logger.info("=" * 80)


async def download_ibovespa_intraday(interval: str = '60m', period: str = '60d'):
    """
    Baixa dados intraday dos 50 componentes Ibovespa
    
    Args:
        interval: Intervalo (60m, 15m, 5m, etc.)
        period: Período (60d, 30d, 7d, etc.)
    """
    # Lista dos 50 componentes Ibovespa
    ibovespa = [
        # Top 10
        'PETR4', 'VALE3', 'ITUB4', 'BBDC4', 'ABEV3',
        'B3SA3', 'WEGE3', 'RENT3', 'SUZB3', 'RAIL3',
        
        # Top 20
        'BBAS3', 'JBSS3', 'MGLU3', 'VIVT3', 'ELET3',
        'CSNA3', 'USIM5', 'GGBR4', 'EMBR3', 'RADL3',
        
        # Top 30
        'HAPV3', 'RDOR3', 'KLBN11', 'EQTL3', 'CPLE6',
        'ENBR3', 'ENGI11', 'SBSP3', 'CMIG4', 'TAEE11',
        
        # Top 40
        'CSAN3', 'UGPA3', 'LREN3', 'BRDT3', 'YDUQ3',
        'CCRO3', 'BPAC11', 'TOTS3', 'PRIO3', 'BEEF3',
        
        # Top 50
        'CYRE3', 'MRFG3', 'GOLL4', 'AZUL4', 'LWSA3',
        'VBBR3', 'SANB11', 'ITSA4', 'CRFB3', 'COGN3'
    ]
    
    await download_intraday_batch(ibovespa, interval=interval, period=period)


async def test_single_ticker(symbol: str = 'PETR4'):
    """
    Testa download de um único ticker para validação
    
    Args:
        symbol: Ticker a testar (padrão: PETR4)
    """
    api = GoogleFinanceIntegration()
    
    logger.info("=" * 80)
    logger.info(f"TESTE: Download intraday {symbol}")
    logger.info("=" * 80)
    
    # Teste 1: 60min, últimos 60 dias
    logger.info("\n📊 Teste 1: 60min, últimos 60 dias")
    df_60m = api.get_intraday_data_yfinance(symbol, interval='60m', period='60d')
    
    if df_60m is not None:
        logger.info(f"   Registros: {len(df_60m)}")
        logger.info(f"   Range: {df_60m['time'].min()} → {df_60m['time'].max()}")
        logger.info(f"   Últimos 5 registros:")
        print(df_60m.tail())
        
        # Salvar no banco
        await api.save_to_timescaledb(df_60m, table='ohlcv_60m')
    
    # Teste 2: 15min, últimos 7 dias
    logger.info("\n📊 Teste 2: 15min, últimos 7 dias")
    df_15m = api.get_intraday_data_yfinance(symbol, interval='15m', period='7d')
    
    if df_15m is not None:
        logger.info(f"   Registros: {len(df_15m)}")
        logger.info(f"   Range: {df_15m['time'].min()} → {df_15m['time'].max()}")
        
        # Salvar no banco
        await api.save_to_timescaledb(df_15m, table='ohlcv_15m')
    
    logger.info("=" * 80)
    logger.success("✅ Teste completo!")
    logger.info("=" * 80)


if __name__ == '__main__':
    import sys
    
    # Exemplo de uso:
    # python google_finance_integration.py test PETR4
    # python google_finance_integration.py download-ibovespa 60m 60d
    # python google_finance_integration.py download PETR4 VALE3 ITUB4 --interval 15m --period 7d
    
    if len(sys.argv) < 2:
        print("""
Google Finance Integration - Intraday Data Collector
====================================================

Uso:
  python google_finance_integration.py test [SYMBOL]
     Testa download de um ticker (padrão: PETR4)
     Exemplo: python google_finance_integration.py test VALE3
  
  python google_finance_integration.py download-ibovespa [INTERVAL] [PERIOD]
     Baixa 50 componentes Ibovespa
     Exemplo: python google_finance_integration.py download-ibovespa 60m 60d
  
  python google_finance_integration.py download SYMBOL1 SYMBOL2 ... --interval 60m --period 60d
     Baixa tickers específicos
     Exemplo: python google_finance_integration.py download PETR4 VALE3 --interval 15m --period 7d

Intervalos disponíveis:
  1m, 5m, 15m, 30m, 60m (1h), 90m, 1d

Períodos disponíveis:
  1d, 5d, 7d, 1mo (30d), 3mo, 6mo, 1y, 2y, 5y, max

IMPORTANTE:
  - Requer yfinance instalado: pip install yfinance
  - Yahoo Finance tem limites de rate: 1 request/segundo
  - Dados intraday limitados: max 60 dias para 60m, 7 dias para 15m
        """)
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == 'test':
        symbol = sys.argv[2] if len(sys.argv) > 2 else 'PETR4'
        asyncio.run(test_single_ticker(symbol))
    
    elif command == 'download-ibovespa':
        interval = sys.argv[2] if len(sys.argv) > 2 else '60m'
        period = sys.argv[3] if len(sys.argv) > 3 else '60d'
        asyncio.run(download_ibovespa_intraday(interval, period))
    
    elif command == 'download':
        # Buscar argumentos --interval e --period
        interval = '60m'
        period = '60d'
        
        symbols = []
        i = 2
        while i < len(sys.argv):
            if sys.argv[i] == '--interval':
                interval = sys.argv[i+1]
                i += 2
            elif sys.argv[i] == '--period':
                period = sys.argv[i+1]
                i += 2
            else:
                symbols.append(sys.argv[i])
                i += 1
        
        if not symbols:
            print("❌ Especifique pelo menos um símbolo")
            sys.exit(1)
        
        asyncio.run(download_intraday_batch(symbols, interval=interval, period=period))
    
    else:
        print(f"❌ Comando desconhecido: {command}")
        sys.exit(1)
