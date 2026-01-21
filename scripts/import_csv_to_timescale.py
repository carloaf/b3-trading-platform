#!/usr/bin/env python3
"""
Importar dados CSV 60min para TimescaleDB
==========================================

Importa arquivos CSV do ProfitChart para o TimescaleDB

Autor: B3 Trading Platform
Data: 21 Janeiro 2026
"""

import asyncio
import asyncpg
import pandas as pd
import os
from datetime import datetime
from glob import glob


async def import_csv_to_timescale():
    """
    Importa dados CSV 60min para TimescaleDB
    """
    print("=" * 100)
    print("IMPORTAR DADOS CSV 60min → TimescaleDB")
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
    
    # Buscar arquivos CSV
    csv_files = sorted(glob('/app/data/*_60min.csv'))
    print(f"\n📂 Encontrados {len(csv_files)} arquivos CSV")
    
    total_imported = 0
    
    for csv_file in csv_files:
        # Extrair símbolo do nome do arquivo
        filename = os.path.basename(csv_file)
        symbol = filename.split('_')[0]
        
        print(f"\n🔄 {symbol}...")
        
        try:
            # Ler CSV
            df = pd.read_csv(csv_file, sep=';', header=None,
                           names=['ticker', 'date', 'time', 'open', 'high', 'low', 'close', 'volume', 'trades'])
            
            # Parse datetime
            df['timestamp'] = pd.to_datetime(df['date'] + ' ' + df['time'], format='%d/%m/%Y %H:%M:%S')
            # Timezone aware (America/Sao_Paulo)
            df['timestamp'] = df['timestamp'].dt.tz_localize('America/Sao_Paulo')
            
            # Converter vírgula para ponto nos preços
            for col in ['open', 'high', 'low', 'close', 'volume']:
                if df[col].dtype == 'object':
                    df[col] = df[col].str.replace(',', '.').astype(float)
            
            # Preparar dados para inserção
            records = []
            for _, row in df.iterrows():
                records.append((
                    symbol,
                    '60min',
                    row['timestamp'],
                    float(row['open']),
                    float(row['high']),
                    float(row['low']),
                    float(row['close']),
                    float(row['volume'])
                ))
            
            # Inserir no banco (batch)
            await conn.executemany(
                """
                INSERT INTO ohlcv_data (symbol, timeframe, time, open, high, low, close, volume)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT (symbol, timeframe, time) DO NOTHING
                """,
                records
            )
            
            total_imported += len(records)
            print(f"   ✅ {len(records)} candles importados")
        
        except Exception as e:
            print(f"   ❌ Erro: {e}")
            continue
    
    # Fechar conexão
    await conn.close()
    
    print(f"\n✅ Importação completa: {total_imported:,} candles")
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
    
    await conn.close()


if __name__ == "__main__":
    asyncio.run(import_csv_to_timescale())
