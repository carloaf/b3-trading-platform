#!/usr/bin/env python3
"""
Profit Binary Parser V2 - Baseado em Análise Hexdump Real
===========================================================

Formato descoberto:
- Registros de 128 bytes (0x80)
- Offset 0x00-0x07: Marcador/Delimitador (double ~45.xxx = 0xXX 1e e6 40)
- Offset 0x08-0x0F: Zeros (padding)
- Offset 0x10-0x17: Open (double)
- Offset 0x18-0x1F: High (double)
- Offset 0x20-0x27: Low (double)
- Offset 0x28-0x2F: Close (double)
- Offset 0x30-0x37: ? (double, pode ser ajuste/indicador)
- Offset 0x38-0x3F: Volume (uint64)
- Offset 0x40-0x7F: Metadados/padding (64 bytes)

Uso:
    python profit_parser_v2.py parse PETR4 2024
    python profit_parser_v2.py import-60min
    python profit_parser_v2.py import-all
"""

import struct
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import asyncio
import asyncpg

# Configuração
PROFIT_PATH = Path.home() / ".wine.backup_20260119_192254/drive_c/users/dellno/AppData/Roaming/Nelogica/Profit"
DATABASE_PATH = PROFIT_PATH / "database/assets"

# TimescaleDB config
DB_CONFIG = {
    'host': 'localhost',
    'port': 5433,
    'database': 'b3trading_market',
    'user': 'b3admin',
    'password': 'b3pass123'
}

class ProfitParserV2:
    """Parser binário baseado em estrutura real descoberta"""
    
    RECORD_SIZE = 128  # 0x80 bytes por registro
    
    def __init__(self, file_path: Path):
        self.file_path = file_path
        with open(file_path, 'rb') as f:
            self.data = f.read()
        
        # Extrair símbolo do nome do arquivo
        # Ex: PETR4_B_0_2_1_1_1_0_2024.day -> PETR4
        self.symbol = file_path.parent.name.split('_')[0]
        
        # Extrair ano
        # Ex: PETR4_B_0_2_1_1_1_0_2024.day -> 2024
        match = file_path.name.split('_')
        self.year = int(match[-1].replace('.day', '').replace('.min', ''))
    
    def parse_records(self) -> List[Dict]:
        """Parse todos os registros do arquivo"""
        records = []
        num_records = len(self.data) // self.RECORD_SIZE
        
        print(f"📊 Parsing {self.file_path.name}")
        print(f"   Tamanho: {len(self.data):,} bytes")
        print(f"   Registros: {num_records}")
        
        # Data base (1º dia do ano do arquivo)
        current_date = datetime(self.year, 1, 1)
        day_counter = 0
        
        for i in range(num_records):
            offset = i * self.RECORD_SIZE
            record_bytes = self.data[offset:offset + self.RECORD_SIZE]
            
            if len(record_bytes) < self.RECORD_SIZE:
                break
            
            try:
                # Marcador (double) - offset 0x00
                marker = struct.unpack('<d', record_bytes[0:8])[0]
                
                # Verificar se é um marcador válido (~45.xxx típico)
                if not (40 < marker < 50):
                    continue
                
                # OHLC (doubles) - offsets 0x10, 0x18, 0x20, 0x28
                open_val = struct.unpack('<d', record_bytes[0x10:0x18])[0]
                high_val = struct.unpack('<d', record_bytes[0x18:0x20])[0]
                low_val = struct.unpack('<d', record_bytes[0x20:0x28])[0]
                close_val = struct.unpack('<d', record_bytes[0x28:0x30])[0]
                
                # Valor desconhecido (pode ser ajuste, dividendos, etc.)
                unknown = struct.unpack('<d', record_bytes[0x30:0x38])[0]
                
                # Volume (uint64) - offset 0x38
                volume = struct.unpack('<Q', record_bytes[0x38:0x40])[0]
                
                # Validar preços
                prices = [open_val, high_val, low_val, close_val]
                if not all(10 < p < 200 for p in prices):
                    continue
                
                # Validar High >= Low
                if high_val < low_val:
                    continue
                
                # Validar High >= Open/Close
                if high_val < max(open_val, close_val):
                    continue
                
                # Validar Low <= Open/Close
                if low_val > min(open_val, close_val):
                    continue
                
                # Validar volume (não pode ser absurdo)
                if volume > 1_000_000_000_000:  # 1 trilhão de ações é absurdo
                    # Pode ser encoding errado, tentar uint32
                    volume_32 = struct.unpack('<I', record_bytes[0x38:0x3C])[0]
                    if 1000 < volume_32 < 1_000_000_000:
                        volume = volume_32
                
                # Incrementar data (supondo dias úteis sequenciais)
                # TODO: Pular fins de semana e feriados
                records.append({
                    'date': current_date + timedelta(days=day_counter),
                    'open': round(open_val, 2),
                    'high': round(high_val, 2),
                    'low': round(low_val, 2),
                    'close': round(close_val, 2),
                    'volume': volume,
                    'unknown': round(unknown, 2) if unknown > 0 else None
                })
                
                day_counter += 1
                
            except Exception as e:
                # print(f"   ⚠️  Erro no registro {i}: {e}")
                continue
        
        print(f"   ✅ Parseados: {len(records)} registros válidos")
        
        if records:
            print(f"   📅 Período: {records[0]['date'].date()} → {records[-1]['date'].date()}")
            print(f"   💰 Primeiro: O={records[0]['open']:.2f} H={records[0]['high']:.2f} L={records[0]['low']:.2f} C={records[0]['close']:.2f} V={records[0]['volume']:,}")
            print(f"   💰 Último:   O={records[-1]['open']:.2f} H={records[-1]['high']:.2f} L={records[-1]['low']:.2f} C={records[-1]['close']:.2f} V={records[-1]['volume']:,}")
        
        return records
    
    async def import_to_timescaledb(self, records: List[Dict], table: str = 'ohlcv_daily'):
        """Importa registros para TimescaleDB"""
        if not records:
            print("   ⚠️  Nenhum registro para importar")
            return
        
        print(f"\n📤 Importando para TimescaleDB...")
        print(f"   Tabela: {table}")
        print(f"   Símbolo: {self.symbol}")
        print(f"   Registros: {len(records)}")
        
        conn = await asyncpg.connect(**DB_CONFIG)
        
        try:
            # Criar tabela se não existir
            await conn.execute(f'''
                CREATE TABLE IF NOT EXISTS {table} (
                    time TIMESTAMPTZ NOT NULL,
                    symbol TEXT NOT NULL,
                    open NUMERIC(10,2) NOT NULL,
                    high NUMERIC(10,2) NOT NULL,
                    low NUMERIC(10,2) NOT NULL,
                    close NUMERIC(10,2) NOT NULL,
                    volume BIGINT NOT NULL,
                    CONSTRAINT {table}_pkey PRIMARY KEY (time, symbol)
                );
            ''')
            
            # Converter para hypertable (ignora se já existe)
            try:
                await conn.execute(f"SELECT create_hypertable('{table}', 'time', if_not_exists => TRUE);")
            except:
                pass  # Já é hypertable
            
            # Inserir registros
            inserted = 0
            for record in records:
                try:
                    await conn.execute(f'''
                        INSERT INTO {table} (time, symbol, open, high, low, close, volume)
                        VALUES ($1, $2, $3, $4, $5, $6, $7)
                        ON CONFLICT (time, symbol) DO NOTHING
                    ''', record['date'], self.symbol, record['open'], record['high'], 
                         record['low'], record['close'], record['volume'])
                    inserted += 1
                except Exception as e:
                    print(f"   ⚠️  Erro ao inserir {record['date']}: {e}")
            
            print(f"   ✅ Importados: {inserted}/{len(records)} registros")
        
        finally:
            await conn.close()


async def parse_and_import(symbol: str, year: int, interval: str = 'daily'):
    """Parse e importa um símbolo específico"""
    # Mapear interval para padrão de arquivo
    patterns = {
        'daily': f"*_2_1_1_1_0_{year}.day",
        '60min': f"*_1_60_1_1_0_{year}.min",
        '15min': f"*_1_15_1_1_0_{year}.min",
        '5min': f"*_1_5_1_1_0_{year}.min",
        '1min': f"*_1_1_1_1_0_{year}.min",
    }
    
    # Mapear interval para tabela
    tables = {
        'daily': 'ohlcv_daily',
        '60min': 'ohlcv_60m',
        '15min': 'ohlcv_15m',
        '5min': 'ohlcv_5m',
        '1min': 'ohlcv_1m',
    }
    
    pattern = patterns.get(interval, patterns['daily'])
    table = tables.get(interval, 'ohlcv_daily')
    
    # Buscar arquivo
    symbol_dir = DATABASE_PATH / f"{symbol}_B_0"
    if not symbol_dir.exists():
        print(f"❌ Diretório não encontrado: {symbol_dir}")
        return
    
    files = list(symbol_dir.glob(pattern))
    
    if not files:
        print(f"❌ Arquivo não encontrado: {symbol_dir}/{pattern}")
        return
    
    file_path = files[0]
    
    # Parse
    parser = ProfitParserV2(file_path)
    records = parser.parse_records()
    
    # Import
    if records:
        await parser.import_to_timescaledb(records, table)


async def import_all_60min():
    """Importa todos os símbolos disponíveis (60min)"""
    print(f"\n{'='*80}")
    print(f"📦 IMPORTAÇÃO MASSIVA - 60 MINUTOS")
    print(f"{'='*80}\n")
    
    # Listar todos os símbolos
    symbols = []
    for symbol_dir in DATABASE_PATH.iterdir():
        if not symbol_dir.is_dir():
            continue
        
        symbol = symbol_dir.name.split('_')[0]
        
        # Buscar arquivos 60min
        files = list(symbol_dir.glob("*_1_60_1_1_0_*.min"))
        
        if files:
            for file_path in files:
                year = int(file_path.name.split('_')[-1].replace('.min', ''))
                symbols.append((symbol, year))
    
    print(f"Encontrados: {len(symbols)} arquivos 60min")
    print(f"{'='*80}\n")
    
    success = 0
    failed = 0
    
    for i, (symbol, year) in enumerate(symbols, 1):
        print(f"\n[{i}/{len(symbols)}] {symbol} {year}...")
        
        try:
            await parse_and_import(symbol, year, '60min')
            success += 1
        except Exception as e:
            print(f"   ❌ Erro: {e}")
            failed += 1
    
    print(f"\n{'='*80}")
    print(f"📊 RESUMO")
    print(f"{'='*80}")
    print(f"✅ Sucesso: {success}")
    print(f"❌ Falhas: {failed}")
    print(f"Taxa: {success/(success+failed)*100:.1f}%")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "parse":
        # Parse específico
        if len(sys.argv) < 4:
            print("Uso: python profit_parser_v2.py parse PETR4 2024 [interval]")
            sys.exit(1)
        
        symbol = sys.argv[2]
        year = int(sys.argv[3])
        interval = sys.argv[4] if len(sys.argv) > 4 else 'daily'
        
        asyncio.run(parse_and_import(symbol, year, interval))
    
    elif command == "import-60min":
        asyncio.run(import_all_60min())
    
    elif command == "import-all":
        # TODO: Implementar import de todos os intervalos
        print("⏳ Em desenvolvimento...")
    
    else:
        print(f"❌ Comando desconhecido: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
