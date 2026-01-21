#!/usr/bin/env python3
"""
Importar dados CSV DAILY para TimescaleDB
==========================================

Importa arquivos CSV daily do ProfitChart para o TimescaleDB

Autor: B3 Trading Platform
Data: 21 Janeiro 2026
"""

import asyncio
import asyncpg
import pandas as pd
import os
from datetime import datetime
from glob import glob


async def import_daily_csv_to_timescale():
    """
    Importa dados CSV daily (1d) para TimescaleDB
    """
    print("=" * 100)
    print("IMPORTAR DADOS CSV DAILY (1d) → TimescaleDB")
    print("=" * 100)
    
    # Conectar ao banco
    print("\n🔗 Conectando ao TimescaleDB...")
    conn = await asyncpg.connect(
        host='b3-timescaledb',
        port=5432,
        user='b3trading_ts',
        password='b3trading_ts_pass',
        database='b3trading_market'
    )
    print("✅ Conectado")
    
    # Buscar arquivos CSV daily (15min para gerar daily)
    csv_files_15min = sorted(glob('/app/data/*_15min.csv'))
    print(f"\n📂 Encontrados {len(csv_files_15min)} arquivos CSV 15min (para converter em daily)")
    
    total_imported = 0
    
    for csv_file in csv_files_15min:
        # Extrair símbolo do nome do arquivo
        filename = os.path.basename(csv_file)
        symbol = filename.split('_')[0]
        
        print(f"\n🔄 {symbol}...")
        
        try:
            # Ler CSV 15min
            df = pd.read_csv(csv_file, sep=';', header=None,
                           names=['ticker', 'date', 'time', 'open', 'high', 'low', 'close', 'volume', 'trades'])
            
            # Parse datetime
            df['timestamp'] = pd.to_datetime(df['date'] + ' ' + df['time'], format='%d/%m/%Y %H:%M:%S')
            
            # Converter vírgula para ponto nos preços
            for col in ['open', 'high', 'low', 'close', 'volume']:
                if df[col].dtype == 'object':
                    df[col] = df[col].str.replace(',', '.').astype(float)
            
            # Criar índice temporal
            df.set_index('timestamp', inplace=True)
            
            # Resample para daily
            df_daily = df.resample('1D').agg({
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum'
            }).dropna()
            
            # Timezone aware (America/Sao_Paulo)
            df_daily.index = df_daily.index.tz_localize('America/Sao_Paulo')
            
            # Preparar dados para inserção
            records = []
            for timestamp, row in df_daily.iterrows():
                records.append((
                    symbol,
                    '1d',
                    timestamp,
                    float(row['open']),
                    float(row['high']),
                    float(row['low']),
                    float(row['close']),
                    float(row['volume'])
                ))
            
            if len(records) == 0:
                print(f"   ⚠️ Nenhum dado daily gerado")
                continue
            
            # Inserir no banco (batch)
            await conn.executemany(
                """
                INSERT INTO ohlcv_data (symbol, timeframe, time, open, high, low, close, volume)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT (symbol, timeframe, time) DO UPDATE SET
                    open = EXCLUDED.open,
                    high = EXCLUDED.high,
                    low = EXCLUDED.low,
                    close = EXCLUDED.close,
                    volume = EXCLUDED.volume
                """,
                records
            )
            
            total_imported += len(records)
            print(f"   ✅ {len(records)} candles daily importados")
        
        except Exception as e:
            print(f"   ❌ Erro: {e}")
            continue
    
    # Fechar conexão
    await conn.close()
    
    print(f"\n✅ Importação completa: {total_imported:,} candles daily")
    print("\n📊 Verificando dados...")
    
    # Reconectar para verificar
    conn = await asyncpg.connect(
        host='b3-timescaledb',
        port=5432,
        user='b3trading_ts',
        password='b3trading_ts_pass',
        database='b3trading_market'
    )
    
    result = await conn.fetch("""
        SELECT timeframe, COUNT(*) as registros, COUNT(DISTINCT symbol) as simbolos
        FROM ohlcv_data
        GROUP BY timeframe
        ORDER BY timeframe
    """)
    
    print("\n📈 Dados no banco:")
    for row in result:
        print(f"   {row['timeframe']:>6s}: {row['registros']:>6,} candles, {row['simbolos']:>2} símbolos")
    
    # Verificar símbolos com dados daily e 60min
    result2 = await conn.fetch("""
        SELECT symbol, 
               COUNT(CASE WHEN timeframe = '1d' THEN 1 END) as daily,
               COUNT(CASE WHEN timeframe = '60min' THEN 1 END) as min60
        FROM ohlcv_data
        GROUP BY symbol
        ORDER BY symbol
    """)
    
    print("\n📊 Símbolos com ambos timeframes (1d + 60min):")
    both_tf = 0
    for row in result2:
        if row['daily'] > 100 and row['min60'] > 500:
            print(f"   {row['symbol']:>6s}: {row['daily']:>4} daily, {row['min60']:>5} 60min ✅")
            both_tf += 1
    
    print(f"\n✅ {both_tf} símbolos prontos para backtest!")
    
    await conn.close()


if __name__ == "__main__":
    asyncio.run(import_daily_csv_to_timescale())
