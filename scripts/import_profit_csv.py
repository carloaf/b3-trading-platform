#!/usr/bin/env python3
"""
Importação de Dados CSV do ProfitChart para TimescaleDB
========================================================

Importa arquivos CSV exportados do ProfitChart para o TimescaleDB.

Formato CSV esperado (sem header):
PETR4;30/12/2025;17:00:00;30,93;30,96;30,82;30,82;175515252,00;5686700
     ↓     ↓         ↓       ↓     ↓     ↓     ↓         ↓         ↓
  symbol date      time   open  high  low  close    volume1    volume2

Campos:
- Símbolo (ex: PETR4)
- Data (DD/MM/YYYY)
- Hora (HH:MM:SS)
- Abertura (vírgula como decimal)
- Máxima (vírgula como decimal)
- Mínima (vírgula como decimal)
- Fechamento (vírgula como decimal)
- Volume1 (vírgula como separador de milhar)
- Volume2 (desconhecido, ignorar)

Uso:
    python import_profit_csv.py import /path/to/data/*.csv
    python import_profit_csv.py import-all ./data
    python import_profit_csv.py validate PETR4
"""

import sys
import csv
import asyncio
import asyncpg
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
import re

# TimescaleDB config
DB_CONFIG = {
    'host': 'localhost',
    'port': 5433,
    'database': 'b3trading_market',
    'user': 'b3admin',
    'password': 'b3pass123'
}

# Mapeamento de intervalos para tabelas
INTERVAL_MAP = {
    '15min': 'ohlcv_15m',
    '60min': 'ohlcv_60m',
    '1h': 'ohlcv_60m',
}


class ProfitCSVImporter:
    """Importador de CSVs do ProfitChart"""
    
    def __init__(self, db_config: Dict = DB_CONFIG):
        self.db_config = db_config
        self.conn: Optional[asyncpg.Connection] = None
        self.stats = {
            'files_processed': 0,
            'files_success': 0,
            'files_failed': 0,
            'total_rows': 0,
            'rows_inserted': 0,
            'rows_skipped': 0,
        }
    
    async def connect(self):
        """Conecta ao TimescaleDB"""
        self.conn = await asyncpg.connect(**self.db_config)
        print(f"✅ Conectado ao TimescaleDB: {self.db_config['database']}")
    
    async def close(self):
        """Fecha conexão"""
        if self.conn:
            await self.conn.close()
    
    def parse_csv_row(self, row: List[str]) -> Optional[Dict]:
        """Parse uma linha do CSV do Profit"""
        try:
            # Formato: SYMBOL;DD/MM/YYYY;HH:MM:SS;OPEN;HIGH;LOW;CLOSE;VOLUME1;VOLUME2
            if len(row) < 8:
                return None
            
            symbol = row[0].strip()
            date_str = row[1].strip()  # DD/MM/YYYY
            time_str = row[2].strip()  # HH:MM:SS
            
            # Converter data (DD/MM/YYYY HH:MM:SS)
            datetime_str = f"{date_str} {time_str}"
            dt = datetime.strptime(datetime_str, "%d/%m/%Y %H:%M:%S")
            
            # Converter preços (substituir vírgula por ponto)
            open_val = float(row[3].replace(',', '.'))
            high_val = float(row[4].replace(',', '.'))
            low_val = float(row[5].replace(',', '.'))
            close_val = float(row[6].replace(',', '.'))
            
            # Volume (remover vírgulas de separação de milhar)
            volume_str = row[7].replace(',', '').replace('.00', '')
            volume = int(float(volume_str))
            
            # Validar OHLC
            if high_val < low_val:
                print(f"   ⚠️  High < Low inválido: {row}")
                return None
            
            if high_val < max(open_val, close_val):
                print(f"   ⚠️  High < Open/Close inválido: {row}")
                return None
            
            if low_val > min(open_val, close_val):
                print(f"   ⚠️  Low > Open/Close inválido: {row}")
                return None
            
            return {
                'time': dt,
                'symbol': symbol,
                'open': open_val,
                'high': high_val,
                'low': low_val,
                'close': close_val,
                'volume': volume
            }
        
        except Exception as e:
            print(f"   ⚠️  Erro ao parsear linha: {row} | Erro: {e}")
            return None
    
    def detect_interval(self, file_path: Path) -> str:
        """Detecta intervalo pelo nome do arquivo"""
        filename = file_path.name
        
        if '15min' in filename:
            return '15min'
        elif '60min' in filename or '1h' in filename:
            return '60min'
        else:
            # Default: 60min
            return '60min'
    
    async def ensure_table_exists(self, table_name: str):
        """Garante que a tabela existe"""
        await self.conn.execute(f'''
            CREATE TABLE IF NOT EXISTS {table_name} (
                time TIMESTAMPTZ NOT NULL,
                symbol TEXT NOT NULL,
                open NUMERIC(10,2) NOT NULL,
                high NUMERIC(10,2) NOT NULL,
                low NUMERIC(10,2) NOT NULL,
                close NUMERIC(10,2) NOT NULL,
                volume BIGINT NOT NULL,
                CONSTRAINT {table_name}_pkey PRIMARY KEY (time, symbol)
            );
        ''')
        
        # Converter para hypertable (ignora se já existe)
        try:
            await self.conn.execute(
                f"SELECT create_hypertable('{table_name}', 'time', if_not_exists => TRUE);"
            )
        except Exception:
            pass  # Já é hypertable
        
        # Criar índice
        await self.conn.execute(f'''
            CREATE INDEX IF NOT EXISTS idx_{table_name}_symbol_time 
            ON {table_name}(symbol, time DESC);
        ''')
    
    async def import_csv_file(self, file_path: Path) -> bool:
        """Importa um arquivo CSV"""
        print(f"\n📄 Processando: {file_path.name}")
        
        # Detectar intervalo e tabela
        interval = self.detect_interval(file_path)
        table_name = INTERVAL_MAP.get(interval, 'ohlcv_60m')
        
        print(f"   Intervalo: {interval} → Tabela: {table_name}")
        
        # Garantir que tabela existe
        await self.ensure_table_exists(table_name)
        
        # Ler CSV
        records = []
        with open(file_path, 'r', encoding='utf-8') as f:
            # CSV sem header, separador ;
            reader = csv.reader(f, delimiter=';')
            
            for row in reader:
                parsed = self.parse_csv_row(row)
                if parsed:
                    records.append(parsed)
                else:
                    self.stats['rows_skipped'] += 1
        
        self.stats['total_rows'] += len(records)
        
        if not records:
            print(f"   ⚠️  Nenhum registro válido encontrado")
            return False
        
        print(f"   📊 Registros parseados: {len(records)}")
        print(f"   📅 Período: {records[-1]['time'].date()} → {records[0]['time'].date()}")
        
        # Inserir em lote
        inserted = 0
        for record in records:
            try:
                await self.conn.execute(f'''
                    INSERT INTO {table_name} (time, symbol, open, high, low, close, volume)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    ON CONFLICT (time, symbol) DO NOTHING
                ''', record['time'], record['symbol'], record['open'], 
                     record['high'], record['low'], record['close'], record['volume'])
                inserted += 1
            except Exception as e:
                print(f"   ⚠️  Erro ao inserir {record['time']}: {e}")
                self.stats['rows_skipped'] += 1
        
        self.stats['rows_inserted'] += inserted
        print(f"   ✅ Inseridos: {inserted}/{len(records)} registros")
        
        return inserted > 0
    
    async def import_directory(self, directory: Path):
        """Importa todos os CSVs de um diretório"""
        print(f"\n{'='*80}")
        print(f"📦 IMPORTAÇÃO EM MASSA - DIRETÓRIO: {directory}")
        print(f"{'='*80}")
        
        # Buscar CSVs
        csv_files = list(directory.glob("*.csv"))
        
        if not csv_files:
            print(f"❌ Nenhum arquivo CSV encontrado em {directory}")
            return
        
        print(f"Arquivos encontrados: {len(csv_files)}")
        print(f"{'='*80}")
        
        for i, csv_file in enumerate(csv_files, 1):
            self.stats['files_processed'] += 1
            
            print(f"\n[{i}/{len(csv_files)}] {csv_file.name}")
            
            try:
                success = await self.import_csv_file(csv_file)
                if success:
                    self.stats['files_success'] += 1
                else:
                    self.stats['files_failed'] += 1
            except Exception as e:
                print(f"   ❌ Erro: {e}")
                self.stats['files_failed'] += 1
        
        self.print_summary()
    
    async def validate_import(self, symbol: str):
        """Valida importação de um símbolo"""
        print(f"\n{'='*80}")
        print(f"✅ VALIDAÇÃO - {symbol}")
        print(f"{'='*80}")
        
        for table in ['ohlcv_15m', 'ohlcv_60m']:
            count_query = f"SELECT COUNT(*) FROM {table} WHERE symbol = $1"
            count = await self.conn.fetchval(count_query, symbol)
            
            if count > 0:
                # Buscar período
                period_query = f'''
                    SELECT MIN(time) as first, MAX(time) as last
                    FROM {table}
                    WHERE symbol = $1
                '''
                period = await self.conn.fetchrow(period_query, symbol)
                
                # Buscar amostra
                sample_query = f'''
                    SELECT time, open, high, low, close, volume
                    FROM {table}
                    WHERE symbol = $1
                    ORDER BY time DESC
                    LIMIT 5
                '''
                samples = await self.conn.fetch(sample_query, symbol)
                
                print(f"\n📊 {table.upper()}:")
                print(f"   Total: {count:,} candles")
                print(f"   Período: {period['first'].date()} → {period['last'].date()}")
                print(f"\n   Últimos 5 candles:")
                print(f"   {'Data':<12} {'Open':>8} {'High':>8} {'Low':>8} {'Close':>8} {'Volume':>15}")
                print(f"   {'-'*70}")
                for sample in samples:
                    print(f"   {sample['time'].strftime('%Y-%m-%d')}  "
                          f"{sample['open']:>8.2f} {sample['high']:>8.2f} "
                          f"{sample['low']:>8.2f} {sample['close']:>8.2f} "
                          f"{sample['volume']:>15,}")
            else:
                print(f"\n📊 {table.upper()}: Sem dados")
    
    def print_summary(self):
        """Exibe resumo da importação"""
        print(f"\n{'='*80}")
        print(f"📊 RESUMO DA IMPORTAÇÃO")
        print(f"{'='*80}")
        print(f"Arquivos processados: {self.stats['files_processed']}")
        print(f"✅ Sucesso: {self.stats['files_success']}")
        print(f"❌ Falhas: {self.stats['files_failed']}")
        print(f"📦 Total de linhas: {self.stats['total_rows']:,}")
        print(f"✅ Linhas inseridas: {self.stats['rows_inserted']:,}")
        print(f"⚠️  Linhas ignoradas: {self.stats['rows_skipped']:,}")
        
        if self.stats['files_processed'] > 0:
            success_rate = (self.stats['files_success'] / self.stats['files_processed']) * 100
            print(f"Taxa de sucesso: {success_rate:.1f}%")
        
        print(f"{'='*80}")


async def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    command = sys.argv[1]
    
    importer = ProfitCSVImporter()
    await importer.connect()
    
    try:
        if command == "import":
            # Importar arquivos específicos
            if len(sys.argv) < 3:
                print("Uso: python import_profit_csv.py import /path/to/file.csv [file2.csv ...]")
                sys.exit(1)
            
            for file_path in sys.argv[2:]:
                await importer.import_csv_file(Path(file_path))
            
            importer.print_summary()
        
        elif command == "import-all":
            # Importar diretório
            if len(sys.argv) < 3:
                directory = Path("./data")
            else:
                directory = Path(sys.argv[2])
            
            await importer.import_directory(directory)
        
        elif command == "validate":
            # Validar importação
            if len(sys.argv) < 3:
                print("Uso: python import_profit_csv.py validate SYMBOL")
                sys.exit(1)
            
            symbol = sys.argv[2].upper()
            await importer.validate_import(symbol)
        
        else:
            print(f"❌ Comando desconhecido: {command}")
            print(__doc__)
            sys.exit(1)
    
    finally:
        await importer.close()


if __name__ == "__main__":
    asyncio.run(main())
