#!/usr/bin/env python3
"""
Expansão de Dados de Mercado - 40+ Ativos Multi-Timeframe
==========================================================

Coleta dados históricos e intraday de 40+ ativos B3 usando:
1. COTAHIST (B3 oficial) - dados diários completos
2. yfinance - dados intraday (15min, 60min, 4h)

Autor: B3 Trading Platform Team
Data: 16 de Janeiro de 2026
"""

import os
import sys
from datetime import datetime, timedelta
from typing import List, Dict, Set
import pandas as pd
import asyncio
import asyncpg
import yfinance as yf
from pathlib import Path

# Lista expandida de 40+ ativos mais líquidos da B3
TOP_40_SYMBOLS = [
    # Bancos
    'ITUB4', 'BBDC4', 'BBAS3', 'SANB11', 'ITUB3', 'BBDC3',
    
    # Energia
    'PETR4', 'PETR3', 'PRIO3', 'RRRP3', 'CSAN3',
    
    # Mineração/Siderurgia
    'VALE3', 'VALE5', 'CSNA3', 'GGBR4', 'USIM5',
    
    # Varejo
    'MGLU3', 'AMER3', 'LREN3', 'PCAR3', 'VIIA3', 'ARZZ3',
    
    # Consumo
    'ABEV3', 'JBSS3', 'BEEF3', 'SMTO3',
    
    # Utilities
    'ELET3', 'ELET6', 'CPLE6', 'CMIG4', 'TAEE11',
    
    # Financeiro/Bolsa
    'B3SA3', 'BBSE3',
    
    # Industrial
    'WEGE3', 'RAIL3', 'EMBR3', 'AZUL4',
    
    # Telecom
    'VIVT3', 'TIMS3',
    
    # Imobiliário
    'MULT3',
    
    # Saúde
    'RDOR3', 'HAPV3',
    
    # Logística
    'RENT3', 'RADL3',
    
    # Tecnologia
    'TOTS3',
    
    # Papel/Celulose
    'SUZB3', 'KLBN11'
]

# Mapeamento de timeframes
TIMEFRAMES = {
    '15min': {'yf_interval': '15m', 'period': '60d', 'table': 'ohlcv_15min'},
    '60min': {'yf_interval': '1h', 'period': '730d', 'table': 'ohlcv_60min'},  # 2 anos
    '4h': {'yf_interval': '1h', 'period': '730d', 'table': 'ohlcv_4h'},  # Resample de 1h
    '1d': {'yf_interval': '1d', 'period': 'max', 'table': 'ohlcv_daily'}
}


class MarketDataExpander:
    """Expansor de dados de mercado multi-timeframe."""
    
    def __init__(
        self,
        db_host: str = 'timescaledb',
        db_port: int = 5432,
        db_name: str = 'b3trading_market',
        db_user: str = 'b3trading_ts',
        db_password: str = 'b3trading_ts_pass'
    ):
        self.db_config = {
            'host': db_host,
            'port': db_port,
            'database': db_name,
            'user': db_user,
            'password': db_password
        }
        self.stats = {
            'symbols_processed': 0,
            'symbols_failed': 0,
            'total_records': 0,
            'timeframes_created': set()
        }
    
    async def setup_database(self):
        """Cria tabelas para todos os timeframes."""
        print("\n🗄️  Configurando estrutura do banco de dados...")
        
        conn = await asyncpg.connect(**self.db_config)
        
        try:
            # Criar tabelas para cada timeframe
            for tf_name, tf_config in TIMEFRAMES.items():
                table_name = tf_config['table']
                
                await conn.execute(f"""
                    CREATE TABLE IF NOT EXISTS {table_name} (
                        time TIMESTAMPTZ NOT NULL,
                        symbol VARCHAR(20) NOT NULL,
                        open DOUBLE PRECISION,
                        high DOUBLE PRECISION,
                        low DOUBLE PRECISION,
                        close DOUBLE PRECISION,
                        volume BIGINT,
                        PRIMARY KEY (time, symbol)
                    );
                """)
                
                # Criar hypertable se não existir
                try:
                    await conn.execute(f"""
                        SELECT create_hypertable('{table_name}', 'time', 
                            if_not_exists => TRUE,
                            chunk_time_interval => INTERVAL '1 month'
                        );
                    """)
                    print(f"   ✅ Hypertable {table_name} criada/verificada")
                    self.stats['timeframes_created'].add(tf_name)
                except:
                    print(f"   ⚠️  {table_name} já existe como hypertable")
                
                # Criar índices
                await conn.execute(f"""
                    CREATE INDEX IF NOT EXISTS idx_{table_name}_symbol_time 
                    ON {table_name} (symbol, time DESC);
                """)
            
            print(f"✅ Estrutura criada para {len(TIMEFRAMES)} timeframes")
        
        finally:
            await conn.close()
    
    def fetch_yfinance_data(
        self,
        symbol: str,
        interval: str,
        period: str
    ) -> pd.DataFrame:
        """
        Busca dados do yfinance.
        
        Args:
            symbol: Símbolo (ex: PETR4.SA)
            interval: Intervalo (15m, 1h, 1d)
            period: Período (60d, 730d, max)
        
        Returns:
            DataFrame com OHLCV
        """
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period, interval=interval)
            
            if df.empty:
                return pd.DataFrame()
            
            # Padronizar colunas
            df = df.reset_index()
            df.columns = df.columns.str.lower()
            
            # Renomear coluna de data
            date_col = 'date' if 'date' in df.columns else 'datetime'
            df = df.rename(columns={date_col: 'time'})
            
            # Selecionar colunas necessárias
            df = df[['time', 'open', 'high', 'low', 'close', 'volume']]
            
            # Adicionar símbolo
            df['symbol'] = symbol.replace('.SA', '')
            
            return df
        
        except Exception as e:
            print(f"   ❌ Erro ao buscar {symbol}: {e}")
            return pd.DataFrame()
    
    def resample_to_4h(self, df: pd.DataFrame) -> pd.DataFrame:
        """Reamostrar dados de 1h para 4h."""
        if df.empty:
            return df
        
        df = df.set_index('time')
        
        # Resample para 4h
        df_4h = df.resample('4H').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum',
            'symbol': 'first'
        }).dropna()
        
        return df_4h.reset_index()
    
    async def save_to_database(
        self,
        df: pd.DataFrame,
        table_name: str,
        symbol: str
    ) -> int:
        """
        Salva DataFrame no banco de dados.
        
        Returns:
            Número de registros inseridos
        """
        if df.empty:
            return 0
        
        conn = await asyncpg.connect(**self.db_config)
        inserted = 0
        
        try:
            for _, row in df.iterrows():
                try:
                    await conn.execute(f"""
                        INSERT INTO {table_name}
                        (time, symbol, open, high, low, close, volume)
                        VALUES ($1, $2, $3, $4, $5, $6, $7)
                        ON CONFLICT (time, symbol) DO NOTHING
                    """,
                        row['time'],
                        symbol,
                        float(row['open']),
                        float(row['high']),
                        float(row['low']),
                        float(row['close']),
                        int(row['volume'])
                    )
                    inserted += 1
                except Exception as e:
                    pass  # Ignorar duplicados
            
            return inserted
        
        finally:
            await conn.close()
    
    async def process_symbol(
        self,
        symbol: str,
        timeframes: List[str] = None
    ):
        """
        Processa um símbolo para todos os timeframes.
        
        Args:
            symbol: Código do ativo (ex: PETR4)
            timeframes: Lista de timeframes a processar (None = todos)
        """
        if timeframes is None:
            timeframes = list(TIMEFRAMES.keys())
        
        yf_symbol = f"{symbol}.SA"
        print(f"\n📊 Processando {symbol}...")
        
        try:
            for tf_name in timeframes:
                if tf_name not in TIMEFRAMES:
                    continue
                
                tf_config = TIMEFRAMES[tf_name]
                
                print(f"   🔄 {tf_name}: baixando {tf_config['period']}...")
                
                # Buscar dados
                df = self.fetch_yfinance_data(
                    yf_symbol,
                    tf_config['yf_interval'],
                    tf_config['period']
                )
                
                if df.empty:
                    print(f"      ⚠️  Sem dados disponíveis")
                    continue
                
                # Se for 4h, reamostrar de 1h
                if tf_name == '4h':
                    df = self.resample_to_4h(df)
                
                # Salvar no banco
                inserted = await self.save_to_database(
                    df,
                    tf_config['table'],
                    symbol
                )
                
                print(f"      ✅ {inserted} registros inseridos em {tf_config['table']}")
                self.stats['total_records'] += inserted
            
            self.stats['symbols_processed'] += 1
        
        except Exception as e:
            print(f"   ❌ Erro ao processar {symbol}: {e}")
            self.stats['symbols_failed'] += 1
    
    async def expand_market_data(
        self,
        symbols: List[str] = None,
        timeframes: List[str] = None
    ):
        """
        Expande dados de mercado para múltiplos símbolos e timeframes.
        
        Args:
            symbols: Lista de símbolos (None = TOP_40_SYMBOLS)
            timeframes: Lista de timeframes (None = todos)
        """
        if symbols is None:
            symbols = TOP_40_SYMBOLS
        
        print(f"\n{'='*60}")
        print(f"🚀 EXPANSÃO DE DADOS DE MERCADO")
        print(f"{'='*60}")
        print(f"📌 Símbolos: {len(symbols)}")
        print(f"📌 Timeframes: {', '.join(timeframes or TIMEFRAMES.keys())}")
        
        # Setup inicial
        await self.setup_database()
        
        # Processar símbolos
        print(f"\n{'='*60}")
        print(f"📥 COLETANDO DADOS")
        print(f"{'='*60}")
        
        for i, symbol in enumerate(symbols, 1):
            print(f"\n[{i}/{len(symbols)}]", end=" ")
            await self.process_symbol(symbol, timeframes)
        
        # Mostrar estatísticas finais
        print(f"\n{'='*60}")
        print(f"📊 ESTATÍSTICAS FINAIS")
        print(f"{'='*60}")
        print(f"✅ Símbolos processados: {self.stats['symbols_processed']}")
        print(f"❌ Símbolos com erro: {self.stats['symbols_failed']}")
        print(f"💾 Total de registros: {self.stats['total_records']:,}")
        print(f"📈 Timeframes criados: {', '.join(sorted(self.stats['timeframes_created']))}")
        
        # Validar dados no banco
        await self.show_database_stats()
    
    async def show_database_stats(self):
        """Mostra estatísticas do banco de dados."""
        print(f"\n{'='*60}")
        print(f"🗄️  VALIDAÇÃO DO BANCO DE DADOS")
        print(f"{'='*60}")
        
        conn = await asyncpg.connect(**self.db_config)
        
        try:
            for tf_name, tf_config in TIMEFRAMES.items():
                table_name = tf_config['table']
                
                result = await conn.fetchrow(f"""
                    SELECT 
                        COUNT(DISTINCT symbol) as symbols,
                        COUNT(*) as records,
                        MIN(time) as first_date,
                        MAX(time) as last_date
                    FROM {table_name}
                """)
                
                if result and result['records'] > 0:
                    print(f"\n📊 {tf_name.upper()} ({table_name}):")
                    print(f"   Símbolos: {result['symbols']}")
                    print(f"   Registros: {result['records']:,}")
                    print(f"   Período: {result['first_date']} até {result['last_date']}")
        
        finally:
            await conn.close()


async def main():
    """Função principal CLI."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Expande dados de mercado para 40+ ativos multi-timeframe',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos de uso:

  # Expandir todos os 40 ativos para todos os timeframes
  python expand_market_data.py
  
  # Apenas timeframes específicos
  python expand_market_data.py --timeframes 15min 60min 1d
  
  # Apenas alguns símbolos
  python expand_market_data.py --symbols PETR4 VALE3 ITUB4
  
  # Combinação
  python expand_market_data.py --symbols PETR4 VALE3 --timeframes 15min 60min
        """
    )
    
    parser.add_argument(
        '--symbols',
        nargs='+',
        help='Lista de símbolos para processar (padrão: TOP_40_SYMBOLS)'
    )
    parser.add_argument(
        '--timeframes',
        nargs='+',
        choices=['15min', '60min', '4h', '1d'],
        help='Timeframes para coletar (padrão: todos)'
    )
    parser.add_argument(
        '--db-host',
        default='timescaledb',
        help='Host do TimescaleDB'
    )
    
    args = parser.parse_args()
    
    # Criar expansor
    expander = MarketDataExpander(db_host=args.db_host)
    
    # Executar expansão
    await expander.expand_market_data(
        symbols=args.symbols,
        timeframes=args.timeframes
    )


if __name__ == '__main__':
    asyncio.run(main())
