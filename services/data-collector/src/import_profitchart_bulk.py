#!/usr/bin/env python3
"""
Script de Importação Bulk - ProfitChart Data
============================================

Importa dados do ProfitChart para TimescaleDB
- 60+ símbolos
- 3 timeframes: 15min, 60min, Diário
- Janeiro 2023 → 28 Janeiro 2026

Formato CSV ProfitChart:
PETR4;30/12/2024;17:00:00;32,83;32,97;32,80;32,80;215181183,90;6552300
Campos: symbol;date;time;open;high;low;close;volume_brl;volume_qty
"""

import asyncio
import asyncpg
import csv
from pathlib import Path
from datetime import datetime
import sys
from loguru import logger

# Configuração de logging
logger.remove()
logger.add(sys.stderr, level="INFO")

# Configuração do banco de dados
DB_CONFIG = {
    'host': 'b3-timescaledb',  # Nome do serviço Docker
    'port': 5432,  # Porta interna do container
    'database': 'b3trading_market',
    'user': 'b3trading_ts',
    'password': 'b3trading_ts_pass'
}

# Mapeamento de timeframes para tabelas
TIMEFRAME_MAPPING = {
    '15min': 'ohlcv_15min',
    '60min': 'ohlcv_60min',
    'Diário': 'ohlcv_daily'
}


class ProfitChartImporter:
    """Importador de dados ProfitChart para TimescaleDB"""
    
    def __init__(self, data_directory: str):
        self.data_directory = Path(data_directory)
        self.pool = None
        self.stats = {
            '15min': {'files': 0, 'records': 0, 'errors': 0},
            '60min': {'files': 0, 'records': 0, 'errors': 0},
            'Diário': {'files': 0, 'records': 0, 'errors': 0}
        }
    
    async def connect(self):
        """Conecta ao TimescaleDB"""
        logger.info(f"Conectando ao TimescaleDB: {DB_CONFIG['host']}:{DB_CONFIG['port']}")
        self.pool = await asyncpg.create_pool(**DB_CONFIG, min_size=5, max_size=20)
        logger.success("Conexão estabelecida!")
    
    async def close(self):
        """Fecha conexão"""
        if self.pool:
            await self.pool.close()
            logger.info("Conexão fechada")
    
    def parse_csv_line(self, line: list, timeframe: str) -> dict:
        """
        Parse de linha CSV do ProfitChart
        
        Formato: symbol;date;time;open;high;low;close;volume_brl;volume_qty
        Exemplo: PETR4;30/12/2024;17:00:00;32,83;32,97;32,80;32,80;215181183,90;6552300
        """
        try:
            symbol = line[0].strip()
            date_str = line[1].strip()  # DD/MM/YYYY
            time_str = line[2].strip()  # HH:MM:SS
            open_price = float(line[3].replace(',', '.'))
            high = float(line[4].replace(',', '.'))
            low = float(line[5].replace(',', '.'))
            close = float(line[6].replace(',', '.'))
            volume_brl = float(line[7].replace(',', '.'))
            volume = int(line[8].strip())
            
            # Parsear timestamp: DD/MM/YYYY HH:MM:SS
            timestamp_str = f"{date_str} {time_str}"
            timestamp = datetime.strptime(timestamp_str, '%d/%m/%Y %H:%M:%S')
            
            return {
                'symbol': symbol,
                'time': timestamp,
                'open': open_price,
                'high': high,
                'low': low,
                'close': close,
                'volume': volume,
                'volume_brl': volume_brl
            }
        except Exception as e:
            logger.error(f"Erro ao parsear linha: {line} - {e}")
            return None
    
    async def import_file(self, file_path: Path):
        """Importa um arquivo CSV para o TimescaleDB"""
        filename = file_path.name
        
        # Extrair timeframe do nome do arquivo
        # Formato: PETR4_B_0_60min.csv ou PETR4_B_0_Diário.csv
        timeframe = None
        for tf in ['15min', '60min', 'Diário']:
            if tf in filename:
                timeframe = tf
                break
        
        if not timeframe:
            logger.warning(f"Timeframe não identificado: {filename}")
            return
        
        table = TIMEFRAME_MAPPING[timeframe]
        symbol = filename.split('_')[0]
        
        logger.info(f"Importando {filename} → {table}")
        
        records = []
        errors = 0
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f, delimiter=';')
                for line in reader:
                    if len(line) < 9:
                        continue
                    
                    parsed = self.parse_csv_line(line, timeframe)
                    if parsed:
                        records.append(parsed)
                    else:
                        errors += 1
            
            # Bulk insert usando COPY
            if records:
                async with self.pool.acquire() as conn:
                    # Preparar dados para COPY
                    copy_data = []
                    for r in records:
                        copy_data.append((
                            r['symbol'],
                            r['time'],
                            r['open'],
                            r['high'],
                            r['low'],
                            r['close'],
                            r['volume']
                        ))
                    
                    # Executar COPY (mais rápido que INSERT)
                    await conn.copy_records_to_table(
                        table,
                        records=copy_data,
                        columns=['symbol', 'time', 'open', 'high', 'low', 'close', 'volume']
                    )
                
                self.stats[timeframe]['files'] += 1
                self.stats[timeframe]['records'] += len(records)
                self.stats[timeframe]['errors'] += errors
                
                logger.success(
                    f"✅ {filename}: {len(records)} registros importados "
                    f"({errors} erros)"
                )
            else:
                logger.warning(f"⚠️ {filename}: Nenhum registro válido encontrado")
        
        except Exception as e:
            logger.error(f"❌ Erro ao importar {filename}: {e}")
            self.stats[timeframe]['errors'] += 1
    
    async def delete_old_data(self, symbol: str, start_date: datetime):
        """Remove dados antigos antes de importar novos (evitar duplicatas)"""
        tables = ['ohlcv_15min', 'ohlcv_60min', 'ohlcv_daily']
        
        async with self.pool.acquire() as conn:
            for table in tables:
                result = await conn.execute(
                    f"DELETE FROM {table} WHERE symbol = $1 AND time >= $2",
                    symbol,
                    start_date
                )
                logger.debug(f"Deletados registros antigos de {symbol} em {table}: {result}")
    
    async def import_all(self, clean_before_import: bool = True):
        """Importa todos os arquivos CSV do diretório"""
        csv_files = sorted(self.data_directory.glob('*_B_0_*.csv'))
        
        logger.info(f"Encontrados {len(csv_files)} arquivos CSV")
        
        if clean_before_import:
            logger.warning("⚠️ Modo CLEAN ativado - dados existentes serão removidos")
            logger.info("Aguardando 3 segundos... (Ctrl+C para cancelar)")
            await asyncio.sleep(3)
        
        # Agrupar arquivos por símbolo (para limpeza)
        symbols = set()
        for f in csv_files:
            symbol = f.name.split('_')[0]
            symbols.add(symbol)
        
        # Limpar dados antigos (apenas de 2023 em diante)
        if clean_before_import:
            logger.info(f"Limpando dados de {len(symbols)} símbolos...")
            start_date = datetime(2023, 1, 1)
            for symbol in sorted(symbols):
                await self.delete_old_data(symbol, start_date)
            logger.success("Limpeza concluída!")
        
        # Importar arquivos
        logger.info("Iniciando importação...")
        for file_path in csv_files:
            await self.import_file(file_path)
        
        # Exibir estatísticas
        logger.info("\n" + "="*60)
        logger.info("ESTATÍSTICAS DE IMPORTAÇÃO")
        logger.info("="*60)
        
        total_files = 0
        total_records = 0
        total_errors = 0
        
        for tf, stats in self.stats.items():
            logger.info(
                f"{tf:10s} | {stats['files']:3d} arquivos | "
                f"{stats['records']:7d} registros | "
                f"{stats['errors']:4d} erros"
            )
            total_files += stats['files']
            total_records += stats['records']
            total_errors += stats['errors']
        
        logger.info("="*60)
        logger.info(
            f"{'TOTAL':10s} | {total_files:3d} arquivos | "
            f"{total_records:7d} registros | "
            f"{total_errors:4d} erros"
        )
        logger.info("="*60 + "\n")
    
    async def validate_import(self):
        """Valida a importação mostrando estatísticas do banco"""
        logger.info("\n" + "="*60)
        logger.info("VALIDAÇÃO DA IMPORTAÇÃO")
        logger.info("="*60)
        
        async with self.pool.acquire() as conn:
            for timeframe, table in TIMEFRAME_MAPPING.items():
                # Contar registros
                count = await conn.fetchval(f"SELECT COUNT(*) FROM {table}")
                
                # Verificar símbolos
                symbols = await conn.fetch(
                    f"""
                    SELECT 
                        symbol,
                        COUNT(*) as total,
                        MIN(time) as primeiro,
                        MAX(time) as ultimo
                    FROM {table}
                    GROUP BY symbol
                    ORDER BY symbol
                    LIMIT 5
                    """
                )
                
                logger.info(f"\n{table} ({timeframe}):")
                logger.info(f"  Total de registros: {count:,}")
                logger.info(f"  Top 5 símbolos:")
                
                for row in symbols:
                    logger.info(
                        f"    {row['symbol']:8s} | {row['total']:6,} registros | "
                        f"{row['primeiro'].date()} → {row['ultimo'].date()}"
                    )
        
        logger.info("\n" + "="*60 + "\n")


async def main():
    """Função principal"""
    # Diretório com os dados ProfitChart
    data_directory = "/tmp/profitchart_data_2026"
    
    # Verificar se diretório existe
    if not Path(data_directory).exists():
        logger.error(f"Diretório não encontrado: {data_directory}")
        return
    
    # Criar importador
    importer = ProfitChartImporter(data_directory)
    
    try:
        # Conectar ao banco
        await importer.connect()
        
        # Importar todos os arquivos
        # ATENÇÃO: clean_before_import=True remove dados de 2023 em diante!
        await importer.import_all(clean_before_import=True)
        
        # Validar importação
        await importer.validate_import()
        
        logger.success("🎉 Importação concluída com sucesso!")
    
    except Exception as e:
        logger.error(f"Erro durante importação: {e}")
        raise
    
    finally:
        await importer.close()


if __name__ == '__main__':
    asyncio.run(main())
