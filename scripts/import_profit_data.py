#!/usr/bin/env python3
"""
Importador de dados CSV exportados do ProfitChart para TimescaleDB
Formato esperado: SYMBOL;DD/MM/YYYY;HH:MM:SS;OPEN,HIGH,LOW,CLOSE;VOLUME1,VOLUME2
"""

import asyncio
import asyncpg
import csv
from pathlib import Path
from datetime import datetime
import sys

async def import_csv_to_timescale(csv_path: Path, conn: asyncpg.Connection):
    """Importa um arquivo CSV para o TimescaleDB"""
    
    # Extrai símbolo e intervalo do nome do arquivo
    # Exemplo: PETR4_B_0_60min.csv -> PETR4, 60min
    filename_parts = csv_path.stem.split('_')
    symbol = filename_parts[0]
    
    # Determina a tabela baseado no nome do arquivo
    if '15min' in csv_path.name:
        table_name = 'ohlcv_15min'
        interval = '15min'
    elif '60min' in csv_path.name:
        table_name = 'ohlcv_60min'
        interval = '60min'
    else:
        raise ValueError(f"Intervalo não identificado no arquivo: {csv_path.name}")
    
    records = []
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f, delimiter=';')
        
        for row_num, row in enumerate(reader, 1):
            try:
                # Parse da linha
                # PETR4;30/12/2025;17:00:00;30,93;30,96;30,82;30,82;175515252,00;5686700
                if len(row) < 8:
                    continue
                
                # Converte data/hora
                date_str = row[1]  # DD/MM/YYYY
                time_str = row[2]  # HH:MM:SS
                dt = datetime.strptime(f"{date_str} {time_str}", "%d/%m/%Y %H:%M:%S")
                
                # Converte preços (virgula para ponto)
                open_val = float(row[3].replace(',', '.'))
                high_val = float(row[4].replace(',', '.'))
                low_val = float(row[5].replace(',', '.'))
                close_val = float(row[6].replace(',', '.'))
                
                # Converte volume
                volume_str = row[7].replace(',', '').replace('.00', '')
                volume = int(float(volume_str)) if volume_str else 0
                
                # Valida OHLC
                if not (low_val <= open_val <= high_val and 
                       low_val <= close_val <= high_val):
                    print(f"⚠️  Linha {row_num}: OHLC inválido - L:{low_val} O:{open_val} H:{high_val} C:{close_val}")
                    continue
                
                records.append((dt, symbol, open_val, high_val, low_val, close_val, volume))
                
            except Exception as e:
                print(f"⚠️  Linha {row_num}: Erro ao processar - {e}")
                continue
    
    if not records:
        return 0
    
    # Bulk insert usando ON CONFLICT para evitar duplicatas
    insert_query = f'''
        INSERT INTO {table_name} (time, symbol, open, high, low, close, volume)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        ON CONFLICT (time, symbol) DO NOTHING
    '''
    
    inserted = await conn.executemany(insert_query, records)
    
    return len(records)


async def main():
    # Configuração do banco
    DB_CONFIG = {
        'host': 'b3-timescaledb',
        'port': 5432,
        'database': 'b3trading_market',
        'user': 'b3trading_ts',
        'password': 'b3trading_ts_pass'
    }
    
    print("=" * 80)
    print("IMPORTADOR DE DADOS DO PROFITCHART PARA TIMESCALEDB")
    print("=" * 80)
    print()
    
    # Conecta ao TimescaleDB
    try:
        print("📡 Conectando ao TimescaleDB...")
        conn = await asyncpg.connect(**DB_CONFIG)
        print("✅ Conectado!\n")
    except Exception as e:
        print(f"❌ Erro ao conectar: {e}")
        return 1
    
    # Busca arquivos CSV
    csv_dir = Path('/tmp')
    csv_files = sorted(csv_dir.glob('*.csv'))
    
    if not csv_files:
        print(f"❌ Nenhum arquivo CSV encontrado em {csv_dir}")
        await conn.close()
        return 1
    
    print(f"📦 Encontrados {len(csv_files)} arquivos CSV\n")
    
    # Importa cada arquivo
    total_records = 0
    total_files = len(csv_files)
    
    for idx, csv_file in enumerate(csv_files, 1):
        try:
            print(f"[{idx:2d}/{total_files}] {csv_file.name:35s} ", end='', flush=True)
            
            record_count = await import_csv_to_timescale(csv_file, conn)
            total_records += record_count
            
            print(f"✅ {record_count:>6,} registros")
            
        except Exception as e:
            print(f"❌ ERRO: {e}")
            continue
    
    print()
    print("=" * 80)
    print(f"📊 IMPORTAÇÃO CONCLUÍDA")
    print("=" * 80)
    print(f"Total de registros importados: {total_records:,}")
    print()
    
    # Exibe estatísticas por tabela e símbolo
    for table in ['ohlcv_15min', 'ohlcv_60min']:
        try:
            result = await conn.fetch(f'''
                SELECT 
                    symbol,
                    COUNT(*) as count,
                    MIN(time) as first_date,
                    MAX(time) as last_date
                FROM {table}
                GROUP BY symbol
                ORDER BY symbol
            ''')
            
            if result:
                print(f"📊 {table.upper()}")
                print("-" * 80)
                for row in result:
                    print(f"  {row['symbol']:8s}: {row['count']:>7,} candles  "
                          f"({row['first_date'].strftime('%d/%m/%Y')} → "
                          f"{row['last_date'].strftime('%d/%m/%Y')})")
                print()
        except Exception as e:
            print(f"⚠️  Erro ao buscar estatísticas de {table}: {e}\n")
    
    await conn.close()
    return 0


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
