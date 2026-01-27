#!/usr/bin/env python3
"""
Import ProfitChart Real Data to TimescaleDB
============================================

Importa dados REAIS do ProfitChart (15min, 60min) para o TimescaleDB,
substituindo os dados sintéticos anteriores.

Formato ProfitChart CSV:
PETR4;30/12/2025;17:00:00;30,93;30,96;30,82;30,82;175515252,00;5686700

Autor: B3 Trading Platform
Data: 23 Janeiro 2026
"""

import os
import pandas as pd
import asyncpg
import asyncio
from pathlib import Path
from datetime import datetime
import sys


async def import_profitchart_data():
    """Importa dados do ProfitChart para TimescaleDB"""
    
    print("="*100)
    print("IMPORTAÇÃO: ProfitChart Real Data → TimescaleDB")
    print("="*100)
    
    # Conectar ao banco
    print("\n🔗 Conectando ao TimescaleDB...")
    pool = await asyncpg.create_pool(
        host='b3-timescaledb',
        port=5432,
        user='b3trading_ts',
        password='b3trading_ts_pass',
        database='b3trading_market',
        min_size=1,
        max_size=10
    )
    print("✅ Conectado")
    
    # Pasta com dados
    data_dir = Path('/app/data')
    
    if not data_dir.exists():
        print(f"❌ Pasta {data_dir} não encontrada!")
        return
    
    # Listar arquivos 60min e 15min
    csv_files_60min = sorted(data_dir.glob('*_60min.csv'))
    csv_files_15min = sorted(data_dir.glob('*_15min.csv'))
    
    print(f"\n📦 Encontrados:")
    print(f"   - {len(csv_files_60min)} arquivos 60min")
    print(f"   - {len(csv_files_15min)} arquivos 15min")
    
    # Processar 60min primeiro
    print("\n" + "="*100)
    print("⏱️ IMPORTANDO DADOS 60 MINUTOS")
    print("="*100)
    
    total_records_60min = 0
    
    for idx, csv_file in enumerate(csv_files_60min, 1):
        symbol = csv_file.stem.split('_')[0]  # PETR4_B_0_60min → PETR4
        
        print(f"\n[{idx}/{len(csv_files_60min)}] 📊 {symbol}...")
        
        try:
            # Ler CSV (separador ; e decimal vírgula)
            df = pd.read_csv(
                csv_file,
                sep=';',
                header=None,
                names=['symbol', 'date', 'time', 'open', 'high', 'low', 'close', 'volume_financial', 'volume'],
                decimal=','
            )
            
            print(f"   📦 {len(df)} registros no CSV")
            
            # Combinar data + hora e adicionar timezone UTC
            df['datetime'] = pd.to_datetime(
                df['date'] + ' ' + df['time'],
                format='%d/%m/%Y %H:%M:%S'
            ).dt.tz_localize('UTC')
            
            # Converter tipos
            df['open'] = pd.to_numeric(df['open'], errors='coerce')
            df['high'] = pd.to_numeric(df['high'], errors='coerce')
            df['low'] = pd.to_numeric(df['low'], errors='coerce')
            df['close'] = pd.to_numeric(df['close'], errors='coerce')
            df['volume'] = pd.to_numeric(df['volume'], errors='coerce').fillna(0).astype(int)
            
            # Remover NaNs
            df = df.dropna(subset=['open', 'high', 'low', 'close'])
            
            if len(df) == 0:
                print(f"   ⚠️ Nenhum dado válido após limpeza")
                continue
            
            # Range de datas
            min_date = df['datetime'].min()
            max_date = df['datetime'].max()
            print(f"   📅 {min_date.date()} → {max_date.date()}")
            
            # Limpar dados antigos deste símbolo
            async with pool.acquire() as conn:
                deleted = await conn.execute("""
                    DELETE FROM ohlcv_60min
                    WHERE symbol = $1
                """, symbol)
                
                print(f"   🗑️ Removidos registros antigos: {deleted}")
                
                # Inserir novos dados
                records = [
                    (
                        row['symbol'],
                        row['datetime'],
                        float(row['open']),
                        float(row['high']),
                        float(row['low']),
                        float(row['close']),
                        int(row['volume'])
                    )
                    for _, row in df.iterrows()
                ]
                
                await conn.executemany("""
                    INSERT INTO ohlcv_60min (symbol, time, open, high, low, close, volume)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    ON CONFLICT (symbol, time) DO UPDATE
                    SET open = EXCLUDED.open,
                        high = EXCLUDED.high,
                        low = EXCLUDED.low,
                        close = EXCLUDED.close,
                        volume = EXCLUDED.volume
                """, records)
                
                print(f"   ✅ Inseridos {len(records)} registros")
                total_records_60min += len(records)
                
        except Exception as e:
            print(f"   ❌ Erro: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    # Processar 15min
    print("\n" + "="*100)
    print("⏱️ IMPORTANDO DADOS 15 MINUTOS")
    print("="*100)
    
    # Criar tabela 15min se não existir
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS ohlcv_15min (
                symbol TEXT NOT NULL,
                time TIMESTAMPTZ NOT NULL,
                open NUMERIC(20, 8) NOT NULL,
                high NUMERIC(20, 8) NOT NULL,
                low NUMERIC(20, 8) NOT NULL,
                close NUMERIC(20, 8) NOT NULL,
                volume BIGINT DEFAULT 0,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                PRIMARY KEY (symbol, time)
            );
        """)
        
        await conn.execute("""
            SELECT create_hypertable('ohlcv_15min', 'time', 
                if_not_exists => TRUE,
                migrate_data => TRUE
            );
        """)
        
        print("✅ Tabela ohlcv_15min preparada")
    
    total_records_15min = 0
    
    for idx, csv_file in enumerate(csv_files_15min, 1):
        symbol = csv_file.stem.split('_')[0]
        
        print(f"\n[{idx}/{len(csv_files_15min)}] 📊 {symbol}...")
        
        try:
            df = pd.read_csv(
                csv_file,
                sep=';',
                header=None,
                names=['symbol', 'date', 'time', 'open', 'high', 'low', 'close', 'volume_financial', 'volume'],
                decimal=','
            )
            
            print(f"   📦 {len(df)} registros no CSV")
            
            df['datetime'] = pd.to_datetime(
                df['date'] + ' ' + df['time'],
                format='%d/%m/%Y %H:%M:%S'
            ).dt.tz_localize('UTC')
            
            df['open'] = pd.to_numeric(df['open'], errors='coerce')
            df['high'] = pd.to_numeric(df['high'], errors='coerce')
            df['low'] = pd.to_numeric(df['low'], errors='coerce')
            df['close'] = pd.to_numeric(df['close'], errors='coerce')
            df['volume'] = pd.to_numeric(df['volume'], errors='coerce').fillna(0).astype(int)
            
            df = df.dropna(subset=['open', 'high', 'low', 'close'])
            
            if len(df) == 0:
                print(f"   ⚠️ Nenhum dado válido")
                continue
            
            min_date = df['datetime'].min()
            max_date = df['datetime'].max()
            print(f"   📅 {min_date.date()} → {max_date.date()}")
            
            async with pool.acquire() as conn:
                deleted = await conn.execute("""
                    DELETE FROM ohlcv_15min
                    WHERE symbol = $1
                """, symbol)
                
                print(f"   🗑️ Removidos: {deleted}")
                
                records = [
                    (
                        row['symbol'],
                        row['datetime'],
                        float(row['open']),
                        float(row['high']),
                        float(row['low']),
                        float(row['close']),
                        int(row['volume'])
                    )
                    for _, row in df.iterrows()
                ]
                
                await conn.executemany("""
                    INSERT INTO ohlcv_15min (symbol, time, open, high, low, close, volume)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    ON CONFLICT (symbol, time) DO UPDATE
                    SET open = EXCLUDED.open,
                        high = EXCLUDED.high,
                        low = EXCLUDED.low,
                        close = EXCLUDED.close,
                        volume = EXCLUDED.volume
                """, records)
                
                print(f"   ✅ Inseridos {len(records)} registros")
                total_records_15min += len(records)
                
        except Exception as e:
            print(f"   ❌ Erro: {e}")
            continue
    
    # Fechar pool
    await pool.close()
    
    # Resumo
    print("\n" + "="*100)
    print("📊 RESUMO DA IMPORTAÇÃO")
    print("="*100)
    print(f"\n✅ 60min: {total_records_60min:,} registros em {len(csv_files_60min)} ativos")
    print(f"✅ 15min: {total_records_15min:,} registros em {len(csv_files_15min)} ativos")
    print(f"\n🎯 Total: {total_records_60min + total_records_15min:,} registros importados")
    print("\n⚠️ IMPORTANTE: Dados sintéticos foram SUBSTITUÍDOS por dados REAIS do ProfitChart!")


if __name__ == "__main__":
    asyncio.run(import_profitchart_data())
