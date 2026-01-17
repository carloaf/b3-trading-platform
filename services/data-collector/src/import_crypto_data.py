#!/usr/bin/env python3
"""
Import Crypto Data from aitrading-platform
==========================================

Importa dados de criptomoedas do aitrading-platform para o b3-trading-platform.

Dados: 10 principais criptomoedas, ~82.000 registros horários (2025)
Símbolos: BTCUSDT, ETHUSDT, BNBUSDT, SOLUSDT, ADAUSDT, DOTUSDT, 
          LINKUSDT, AVAXUSDT, UNIUSDT, SHIBUSDT

Author: B3 Trading Platform
Date: 16 de Janeiro de 2026
"""

import asyncio
import asyncpg
import csv
from datetime import datetime
from pathlib import Path


async def import_crypto_data(csv_file: Path, db_config: dict):
    """
    Importa dados de criptomoedas do CSV para o TimescaleDB
    
    Estrutura CSV:
    - symbol, timestamp, open, high, low, close, volume, price
    """
    
    print("=" * 80)
    print("📊 CRYPTO DATA IMPORTER")
    print("=" * 80)
    print(f"📁 File: {csv_file}")
    print(f"💾 Target DB: {db_config['host']}:{db_config['port']}/{db_config['database']}\n")
    
    # Conectar ao banco
    conn = await asyncpg.connect(**db_config)
    
    # Criar tabela crypto_ohlcv_1h se não existir
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS crypto_ohlcv_1h (
            symbol VARCHAR(20) NOT NULL,
            time TIMESTAMPTZ NOT NULL,
            open DECIMAL(20,8) NOT NULL,
            high DECIMAL(20,8) NOT NULL,
            low DECIMAL(20,8) NOT NULL,
            close DECIMAL(20,8) NOT NULL,
            volume BIGINT NOT NULL,
            price DECIMAL(20,8),
            UNIQUE(symbol, time)
        );
    """)
    
    # Criar hypertable se não existir
    try:
        await conn.execute("""
            SELECT create_hypertable(
                'crypto_ohlcv_1h', 
                'time',
                if_not_exists => TRUE
            );
        """)
        print("✅ Hypertable crypto_ohlcv_1h criada/verificada\n")
    except Exception as e:
        print(f"⚠️  Hypertable já existe ou erro: {e}\n")
    
    # Criar índices
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_crypto_ohlcv_1h_symbol_time 
        ON crypto_ohlcv_1h (symbol, time DESC);
    """)
    
    # Ler e inserir dados do CSV
    batch = []
    batch_size = 1000
    total_inserted = 0
    errors = 0
    symbols_count = {}
    
    print("📥 Importando dados...")
    
    with open(csv_file, 'r') as f:
        reader = csv.DictReader(f)
        
        for row_num, row in enumerate(reader, 1):
            try:
                symbol = row['symbol']
                timestamp = datetime.fromisoformat(row['timestamp'].replace('+00', '+00:00'))
                open_price = float(row['open'])
                high = float(row['high'])
                low = float(row['low'])
                close = float(row['close'])
                volume = int(float(row['volume']))
                price = float(row['price'])
                
                batch.append((
                    symbol, timestamp, open_price, high, low, close, volume, price
                ))
                
                # Contar por símbolo
                symbols_count[symbol] = symbols_count.get(symbol, 0) + 1
                
                # Inserir batch
                if len(batch) >= batch_size:
                    query = """
                        INSERT INTO crypto_ohlcv_1h 
                        (symbol, time, open, high, low, close, volume, price)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                        ON CONFLICT (symbol, time) DO UPDATE SET
                            open = EXCLUDED.open,
                            high = EXCLUDED.high,
                            low = EXCLUDED.low,
                            close = EXCLUDED.close,
                            volume = EXCLUDED.volume,
                            price = EXCLUDED.price
                    """
                    await conn.executemany(query, batch)
                    total_inserted += len(batch)
                    batch = []
                    
                    if row_num % 10000 == 0:
                        print(f"   📈 Processadas {row_num:,} linhas | Inseridas: {total_inserted:,}")
            
            except Exception as e:
                print(f"   ⚠️  Erro na linha {row_num}: {e}")
                errors += 1
        
        # Inserir batch restante
        if batch:
            query = """
                INSERT INTO crypto_ohlcv_1h 
                (symbol, time, open, high, low, close, volume, price)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT (symbol, time) DO UPDATE SET
                    open = EXCLUDED.open,
                    high = EXCLUDED.high,
                    low = EXCLUDED.low,
                    close = EXCLUDED.close,
                    volume = EXCLUDED.volume,
                    price = EXCLUDED.price
            """
            await conn.executemany(query, batch)
            total_inserted += len(batch)
    
    await conn.close()
    
    print(f"\n✅ Importação concluída!")
    print(f"   📊 Total de registros inseridos: {total_inserted:,}")
    print(f"   ❌ Erros: {errors:,}")
    print(f"\n📈 Registros por símbolo:")
    for symbol, count in sorted(symbols_count.items()):
        print(f"   {symbol:12s}: {count:,} registros")
    
    print("\n" + "=" * 80)


async def main():
    """Função principal"""
    
    # Configuração do banco b3-trading-platform
    db_config = {
        'host': 'timescaledb',
        'port': 5432,
        'database': 'b3trading_market',
        'user': 'b3trading_ts',
        'password': 'b3trading_ts_pass'
    }
    
    # Arquivo CSV - verificar ambos os nomes
    csv_file = Path('/tmp/crypto_data_all_export.csv')
    
    # Fallback para o arquivo antigo (10 símbolos)
    if not csv_file.exists():
        csv_file = Path('/tmp/crypto_data_export.csv')
    
    if not csv_file.exists():
        print(f"❌ Arquivo não encontrado")
        print("   Execute o export primeiro:")
        print("   docker exec aitrading-timescaledb psql ... > /tmp/crypto_data_all_export.csv")
        return
    
    await import_crypto_data(csv_file, db_config)


if __name__ == '__main__':
    asyncio.run(main())
