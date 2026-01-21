"""
Profit/ProfitChart Binary Parser - Nelogica Data Extraction
===========================================================

Parser para ler arquivos binários do Profit/ProfitChart (Nelogica)
e converter para formato compatível com TimescaleDB.

Formatos suportados:
- .day (dados diários)
- .min (dados intraday - 1min, 5min, etc.)
- .trd (tick-by-tick)

Baseado em engenharia reversa do formato binário da Nelogica.

Autor: Stock-IndiceDev Assistant
Data: 20/01/2026
"""

import struct
import asyncio
import asyncpg
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Optional, Tuple
import pandas as pd
from loguru import logger

# Configurações
DB_CONFIG = {
    'host': 'timescaledb',
    'port': 5432,
    'database': 'b3trading_market',
    'user': 'b3trading_ts',
    'password': 'b3trading_ts_pass'
}

# Caminho padrão do Profit
PROFIT_BASE_PATH = Path.home() / ".wine.backup_20260119_192254/drive_c/users/dellno/AppData/Roaming/Nelogica/Profit"
PROFIT_DATABASE_PATH = PROFIT_BASE_PATH / "database/assets"


class ProfitBinaryParser:
    """
    Parser para arquivos binários do Profit/ProfitChart
    
    Formato binário (engenharia reversa):
    - Header com informações do ativo
    - Registros OHLC sequenciais
    - Cada registro: 32-40 bytes (dependendo do formato)
    """
    
    def __init__(self, profit_path: Optional[Path] = None):
        self.profit_path = profit_path or PROFIT_DATABASE_PATH
        
        if self.profit_path.exists():
            logger.success(f"✅ Profit database encontrado: {self.profit_path}")
        else:
            logger.warning(f"⚠️ Profit database não encontrado: {self.profit_path}")
    
    def list_available_symbols(self) -> List[str]:
        """Lista símbolos disponíveis no Profit"""
        if not self.profit_path.exists():
            return []
        
        symbols = []
        for asset_dir in self.profit_path.iterdir():
            if asset_dir.is_dir():
                # Extrair símbolo (formato: PETR4_B_0)
                symbol = asset_dir.name.split('_')[0]
                symbols.append(symbol)
        
        return sorted(set(symbols))
    
    def find_asset_files(
        self,
        symbol: str,
        interval: str = 'daily'
    ) -> List[Path]:
        """
        Encontra arquivos de um ativo específico
        
        Args:
            symbol: Ticker (ex: PETR4)
            interval: daily, 1min, 5min, tick
        
        Returns:
            Lista de arquivos encontrados
        """
        # Padrões de busca
        patterns = {
            'daily': f"{symbol}_B_0/*_2_1_1_1_0_*.day",
            '1min': f"{symbol}_B_0/*_1_1_1_1_0_*.min",
            '5min': f"{symbol}_B_0/*_1_5_1_1_0_*.min",
            'tick': f"{symbol}_B_0/*_0_1_1_1_0_*.trd"
        }
        
        pattern = patterns.get(interval, patterns['daily'])
        files = list(self.profit_path.glob(pattern))
        
        logger.info(f"📁 {len(files)} arquivos encontrados para {symbol} ({interval})")
        return sorted(files)
    
    def parse_daily_file(self, file_path: Path) -> Optional[pd.DataFrame]:
        """
        Parse arquivo .day (dados diários)
        
        Formato estimado (32 bytes por registro):
        - 4 bytes: Data (int - dias desde época)
        - 4 bytes: Open (float)
        - 4 bytes: High (float)
        - 4 bytes: Low (float)
        - 4 bytes: Close (float)
        - 8 bytes: Volume (long)
        - 4 bytes: Extra/padding
        """
        try:
            with open(file_path, 'rb') as f:
                data = f.read()
            
            # Pular header (primeiros 40-100 bytes geralmente são header)
            header_size = 40
            data = data[header_size:]
            
            # Tamanho do registro (tentativa: 32 bytes)
            record_size = 32
            num_records = len(data) // record_size
            
            records = []
            for i in range(num_records):
                offset = i * record_size
                record_data = data[offset:offset + record_size]
                
                if len(record_data) < record_size:
                    break
                
                try:
                    # Tentar desempacotar (little-endian)
                    # Formato: int, 4 floats, long
                    date_int, open_val, high_val, low_val, close_val, volume = struct.unpack(
                        '<iffff Q', record_data[:28]
                    )
                    
                    # Converter date_int para datetime
                    # Nelogica usa época diferente (possivelmente 1980 ou 1990)
                    base_date = datetime(1980, 1, 1)
                    date = base_date + timedelta(days=date_int)
                    
                    # Validar dados (preços devem ser positivos)
                    if open_val > 0 and close_val > 0:
                        records.append({
                            'time': date,
                            'open': open_val,
                            'high': high_val,
                            'low': low_val,
                            'close': close_val,
                            'volume': volume
                        })
                
                except struct.error:
                    continue
            
            if not records:
                logger.warning(f"⚠️ Nenhum registro válido em {file_path.name}")
                return None
            
            df = pd.DataFrame(records)
            
            # Extrair símbolo do nome do arquivo
            symbol = file_path.parent.name.split('_')[0]
            df['symbol'] = symbol
            
            logger.success(f"✅ {len(df)} registros parseados de {file_path.name}")
            logger.debug(f"   Range: {df['time'].min()} → {df['time'].max()}")
            
            return df
        
        except Exception as e:
            logger.error(f"❌ Erro ao parsear {file_path.name}: {e}")
            return None
    
    def parse_all_daily_files(self, symbol: str) -> Optional[pd.DataFrame]:
        """Parse todos os arquivos diários de um símbolo"""
        files = self.find_asset_files(symbol, 'daily')
        
        if not files:
            logger.warning(f"⚠️ Nenhum arquivo diário para {symbol}")
            return None
        
        all_data = []
        for file_path in files:
            df = self.parse_daily_file(file_path)
            if df is not None:
                all_data.append(df)
        
        if not all_data:
            return None
        
        # Concatenar e ordenar
        df_final = pd.concat(all_data, ignore_index=True)
        df_final = df_final.sort_values('time')
        df_final = df_final.drop_duplicates(subset=['time'])
        
        logger.success(f"✅ Total: {len(df_final)} dias de {symbol}")
        logger.info(f"   Período: {df_final['time'].min().date()} → {df_final['time'].max().date()}")
        
        return df_final
    
    async def import_to_timescaledb(
        self,
        df: pd.DataFrame,
        table: str = 'ohlcv_daily'
    ):
        """Importa DataFrame para TimescaleDB"""
        if df is None or df.empty:
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
            
            await conn.executemany(query, records)
            logger.success(f"✅ {len(records)} registros importados para {table}")
        
        finally:
            await conn.close()


async def import_symbol(symbol: str, interval: str = 'daily'):
    """Importa um símbolo específico"""
    parser = ProfitBinaryParser()
    
    if interval == 'daily':
        df = parser.parse_all_daily_files(symbol)
        if df is not None:
            await parser.import_to_timescaledb(df, 'ohlcv_daily')
    else:
        logger.warning(f"⚠️ Intervalo {interval} ainda não implementado")


async def import_batch(symbols: List[str], interval: str = 'daily'):
    """Importa múltiplos símbolos"""
    parser = ProfitBinaryParser()
    
    logger.info("=" * 80)
    logger.info(f"IMPORTAÇÃO EM LOTE - Profit → TimescaleDB")
    logger.info("=" * 80)
    logger.info(f"Símbolos: {len(symbols)}")
    logger.info(f"Intervalo: {interval}")
    logger.info("=" * 80)
    
    success = 0
    failed = 0
    
    for i, symbol in enumerate(symbols, 1):
        logger.info(f"[{i}/{len(symbols)}] Importando {symbol}...")
        try:
            await import_symbol(symbol, interval)
            success += 1
        except Exception as e:
            logger.error(f"❌ Erro: {e}")
            failed += 1
    
    logger.info("=" * 80)
    logger.success(f"✅ Importação completa!")
    logger.info(f"   Sucesso: {success}/{len(symbols)}")
    logger.info(f"   Falhas: {failed}/{len(symbols)}")
    logger.info("=" * 80)


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("""
Profit Binary Parser - Extração de Dados Nelogica
==================================================

Uso:

  1. LISTAR SÍMBOLOS DISPONÍVEIS
     python profit_parser.py list

  2. IMPORTAR UM SÍMBOLO
     python profit_parser.py import PETR4

  3. IMPORTAR MÚLTIPLOS SÍMBOLOS
     python profit_parser.py import PETR4 VALE3 ITUB4 BBDC4

  4. IMPORTAR IBOVESPA (50 componentes)
     python profit_parser.py import-ibov

  5. IMPORTAR TODOS OS DISPONÍVEIS
     python profit_parser.py import-all

Intervalos suportados (futuros):
  daily (padrão), 1min, 5min, tick

IMPORTANTE:
  - Os arquivos .day/.min/.trd são binários proprietários da Nelogica
  - Este parser usa engenharia reversa do formato
  - Se o formato mudar, pode precisar ajustes
        """)
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == 'list':
        parser = ProfitBinaryParser()
        symbols = parser.list_available_symbols()
        
        print(f"\n📊 {len(symbols)} símbolos disponíveis no Profit:\n")
        for i, symbol in enumerate(symbols, 1):
            files = parser.find_asset_files(symbol, 'daily')
            years = len(files)
            print(f"  {i:3d}. {symbol:10s} ({years:2d} anos)")
        
        print(f"\nTotal: {len(symbols)} símbolos")
    
    elif command == 'import':
        symbols = sys.argv[2:]
        if not symbols:
            print("❌ Especifique pelo menos um símbolo")
            sys.exit(1)
        
        asyncio.run(import_batch(symbols))
    
    elif command == 'import-ibov':
        ibovespa = [
            'PETR4', 'VALE3', 'ITUB4', 'BBDC4', 'ABEV3',
            'B3SA3', 'WEGE3', 'RENT3', 'SUZB3', 'RAIL3',
            'BBAS3', 'JBSS3', 'MGLU3', 'VIVT3', 'ELET3',
            'CSNA3', 'USIM5', 'GGBR4', 'EMBR3', 'RADL3'
        ]
        asyncio.run(import_batch(ibovespa))
    
    elif command == 'import-all':
        parser = ProfitBinaryParser()
        symbols = parser.list_available_symbols()
        
        print(f"⚠️ Importar {len(symbols)} símbolos?")
        resp = input("Confirmar (s/n): ")
        
        if resp.lower() == 's':
            asyncio.run(import_batch(symbols))
    
    else:
        print(f"❌ Comando desconhecido: {command}")
        sys.exit(1)
