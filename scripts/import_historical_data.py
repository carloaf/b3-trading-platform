#!/usr/bin/env python3
"""
Script de Importação Histórica - Dados23e24 + Dados26
=====================================================

Importa dados históricos ProfitChart em 2 fases:
1. Fase 1: 5 ativos prioritários (PETR4, VALE3, ITUB4, BBDC4, ABEV3)
2. Fase 2: 53 símbolos restantes

Pastas:
- /home/dellno/Área de trabalho/dadoshistoricos.csv/dados23e24 (2023-2025)
- /home/dellno/Área de trabalho/dadoshistoricos.csv/dados26 (janeiro 2026) [JÁ IMPORTADO]
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
logger.add(sys.stderr, level="INFO", format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>")

# Configuração do banco de dados (via rede Docker)
DB_CONFIG = {
    'host': 'b3-timescaledb',  # Nome do serviço Docker
    'port': 5432,              # Porta interna do container
    'database': 'b3trading_market',
    'user': 'b3trading_ts',
    'password': 'b3trading_ts_pass'
}

# Pastas de dados (ajustável via variável de ambiente)
PASTA_23E24 = Path("/data/dados23e24")
PASTA_26 = Path("/data/dados26")

# Símbolos prioritários
PRIORITY_SYMBOLS = ['PETR4', 'VALE3', 'ITUB4', 'BBDC4', 'ABEV3']

# Mapeamento de timeframes
TIMEFRAME_MAPPING = {
    '15min': 'ohlcv_15min',
    '60min': 'ohlcv_60min',
    'Diário': 'ohlcv_daily'
}


class HistoricalDataImporter:
    """Importador de dados históricos para TimescaleDB"""
    
    def __init__(self):
        self.pool = None
        self.stats = {
            'priority': {'files': 0, 'records': 0, 'errors': 0},
            'others': {'files': 0, 'records': 0, 'errors': 0}
        }
    
    async def connect(self):
        """Conecta ao TimescaleDB"""
        logger.info(f"Conectando ao TimescaleDB: {DB_CONFIG['host']}:{DB_CONFIG['port']}")
        self.pool = await asyncpg.create_pool(**DB_CONFIG, min_size=5, max_size=20)
        logger.success("✅ Conexão estabelecida!")
    
    async def close(self):
        """Fecha conexão"""
        if self.pool:
            await self.pool.close()
            logger.info("Conexão fechada")
    
    def parse_csv_line(self, line: list, is_daily: bool = False) -> dict:
        """
        Parse de linha CSV do ProfitChart
        
        Formato Intraday: symbol;date;time;open;high;low;close;volume_brl;volume_qty
        Formato Diário:   symbol;date;open;high;low;close;volume_brl;volume_qty (SEM time)
        """
        try:
            if is_daily:
                # Formato Diário: sem coluna de horário
                symbol = line[0].strip()
                date_str = line[1].strip()  # DD/MM/YYYY
                open_price = float(line[2].replace(',', '.'))
                high = float(line[3].replace(',', '.'))
                low = float(line[4].replace(',', '.'))
                close = float(line[5].replace(',', '.'))
                volume_brl = float(line[6].replace(',', '.'))
                volume = int(line[7].strip())
                
                # Parse data (sem horário)
                timestamp = datetime.strptime(date_str, '%d/%m/%Y')
            else:
                # Formato Intraday: com horário
                symbol = line[0].strip()
                date_str = line[1].strip()  # DD/MM/YYYY
                time_str = line[2].strip()  # HH:MM:SS
                open_price = float(line[3].replace(',', '.'))
                high = float(line[4].replace(',', '.'))
                low = float(line[5].replace(',', '.'))
                close = float(line[6].replace(',', '.'))
                volume_brl = float(line[7].replace(',', '.'))
                volume = int(line[8].strip())
                
                # Parse timestamp
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
            logger.error(f"Erro ao parsear linha: {line[:3]} - {e}")
            return None
    
    async def check_existing_data(self, symbol: str, start_date: datetime, end_date: datetime):
        """Verifica se já existem dados neste período"""
        async with self.pool.acquire() as conn:
            for table in TIMEFRAME_MAPPING.values():
                count = await conn.fetchval(
                    f"""
                    SELECT COUNT(*) FROM {table}
                    WHERE symbol = $1 AND time >= $2 AND time <= $3
                    """,
                    symbol, start_date, end_date
                )
                if count > 0:
                    logger.warning(f"  ⚠️ {symbol} já tem {count} registros em {table} ({start_date.date()} → {end_date.date()})")
                    return True
        return False
    
    async def delete_old_data(self, symbol: str, start_date: datetime, end_date: datetime):
        """Remove dados antigos antes de importar (evitar duplicatas)"""
        logger.info(f"  🗑️  Removendo dados existentes de {symbol} ({start_date.date()} → {end_date.date()})")
        
        async with self.pool.acquire() as conn:
            for table in TIMEFRAME_MAPPING.values():
                result = await conn.execute(
                    f"DELETE FROM {table} WHERE symbol = $1 AND time >= $2 AND time <= $3",
                    symbol, start_date, end_date
                )
                deleted = int(result.split()[-1])
                if deleted > 0:
                    logger.debug(f"    Deletados {deleted} registros de {table}")
    
    async def import_file(self, file_path: Path, phase: str):
        """Importa um arquivo CSV"""
        filename = file_path.name
        
        # Identificar timeframe
        timeframe = None
        for tf in ['15min', '60min', 'Diário']:
            if tf in filename:
                timeframe = tf
                break
        
        if not timeframe:
            logger.warning(f"  ⚠️ Timeframe não identificado: {filename}")
            return
        
        # Determinar se é arquivo diário (formato diferente)
        is_daily = (timeframe == 'Diário')
        
        table = TIMEFRAME_MAPPING[timeframe]
        symbol = filename.split('_')[0]
        
        logger.info(f"  📄 {filename} → {table}")
        
        records = []
        errors = 0
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f, delimiter=';')
                for line in reader:
                    # Diário tem 8 campos, Intraday tem 9
                    expected_fields = 8 if is_daily else 9
                    if len(line) < expected_fields:
                        continue
                    
                    parsed = self.parse_csv_line(line, is_daily=is_daily)
                    if parsed:
                        records.append(parsed)
                    else:
                        errors += 1
            
            if records:
                # Bulk insert usando COPY
                async with self.pool.acquire() as conn:
                    copy_data = [
                        (r['symbol'], r['time'], r['open'], r['high'], r['low'], r['close'], r['volume'])
                        for r in records
                    ]
                    
                    await conn.copy_records_to_table(
                        table,
                        records=copy_data,
                        columns=['symbol', 'time', 'open', 'high', 'low', 'close', 'volume']
                    )
                
                self.stats[phase]['files'] += 1
                self.stats[phase]['records'] += len(records)
                self.stats[phase]['errors'] += errors
                
                logger.success(f"     ✅ {len(records):,} registros importados")
            else:
                logger.warning(f"     ⚠️ Nenhum registro válido")
        
        except Exception as e:
            logger.error(f"     ❌ Erro: {e}")
            self.stats[phase]['errors'] += 1
    
    async def import_symbol(self, symbol: str, folder: Path, phase: str):
        """Importa todos os timeframes de um símbolo"""
        logger.info(f"\n{'='*70}")
        logger.info(f"📊 {symbol}")
        logger.info(f"{'='*70}")
        
        # Encontrar arquivos deste símbolo
        pattern = f"{symbol}_B_0_*.csv"
        files = sorted(folder.glob(pattern))
        
        if not files:
            logger.warning(f"  ⚠️ Nenhum arquivo encontrado para {symbol}")
            return
        
        logger.info(f"  Encontrados {len(files)} arquivos")
        
        # Verificar se já tem dados (apenas para dados23e24, dados26 já foi importado)
        if folder == PASTA_23E24:
            has_data = await self.check_existing_data(symbol, datetime(2023, 1, 1), datetime(2025, 12, 31))
            
            if has_data:
                response = input(f"\n  ⚠️ {symbol} já tem dados de 2023-2025. Remover e reimportar? (s/N): ")
                if response.lower() != 's':
                    logger.info(f"  ⏭️  Pulando {symbol}")
                    return
                
                # Remover dados antigos
                await self.delete_old_data(symbol, datetime(2023, 1, 1), datetime(2025, 12, 31))
        
        # Importar cada arquivo
        for file_path in files:
            await self.import_file(file_path, phase)
    
    async def import_priority_symbols(self):
        """Fase 1: Importa os 5 símbolos prioritários"""
        logger.info("\n" + "="*70)
        logger.info("🎯 FASE 1: ATIVOS PRIORITÁRIOS (5 símbolos)")
        logger.info("="*70)
        logger.info("Símbolos: " + ", ".join(PRIORITY_SYMBOLS))
        logger.info("Pasta: dados23e24 (2023-2025)")
        logger.info("="*70)
        
        for symbol in PRIORITY_SYMBOLS:
            await self.import_symbol(symbol, PASTA_23E24, 'priority')
    
    async def import_remaining_symbols(self):
        """Fase 2: Importa os símbolos restantes"""
        logger.info("\n" + "="*70)
        logger.info("📈 FASE 2: SÍMBOLOS RESTANTES (53 símbolos)")
        logger.info("="*70)
        
        # Listar todos os símbolos disponíveis
        all_files = sorted(PASTA_23E24.glob("*_B_0_*.csv"))
        all_symbols = sorted(set(f.name.split('_')[0] for f in all_files))
        
        # Excluir os prioritários
        remaining = [s for s in all_symbols if s not in PRIORITY_SYMBOLS]
        
        logger.info(f"Símbolos restantes: {len(remaining)}")
        logger.info("Pasta: dados23e24 (2023-2025)")
        logger.info("="*70)
        
        # Confirmar antes de importar
        response = input(f"\n⚠️ Deseja importar os {len(remaining)} símbolos restantes? (s/N): ")
        if response.lower() != 's':
            logger.info("❌ Importação da Fase 2 cancelada")
            return
        
        for symbol in remaining:
            await self.import_symbol(symbol, PASTA_23E24, 'others')
    
    async def validate_import(self, symbols: list):
        """Valida a importação mostrando estatísticas"""
        logger.info("\n" + "="*70)
        logger.info("✅ VALIDAÇÃO DA IMPORTAÇÃO")
        logger.info("="*70)
        
        async with self.pool.acquire() as conn:
            for symbol in symbols:
                logger.info(f"\n📊 {symbol}:")
                
                for timeframe, table in TIMEFRAME_MAPPING.items():
                    result = await conn.fetchrow(
                        f"""
                        SELECT 
                            COUNT(*) as total,
                            MIN(time) as primeiro,
                            MAX(time) as ultimo
                        FROM {table}
                        WHERE symbol = $1
                        """,
                        symbol
                    )
                    
                    if result['total'] > 0:
                        logger.info(
                            f"  {timeframe:10s}: {result['total']:>6,} candles | "
                            f"{result['primeiro'].date()} → {result['ultimo'].date()}"
                        )
                    else:
                        logger.warning(f"  {timeframe:10s}: ❌ SEM DADOS")
    
    def print_statistics(self):
        """Imprime estatísticas finais"""
        logger.info("\n" + "="*70)
        logger.info("📊 ESTATÍSTICAS FINAIS")
        logger.info("="*70)
        
        for phase, stats in self.stats.items():
            phase_name = "Prioritários" if phase == 'priority' else "Restantes"
            logger.info(f"\n{phase_name}:")
            logger.info(f"  Arquivos: {stats['files']}")
            logger.info(f"  Registros: {stats['records']:,}")
            logger.info(f"  Erros: {stats['errors']}")
        
        total_files = sum(s['files'] for s in self.stats.values())
        total_records = sum(s['records'] for s in self.stats.values())
        total_errors = sum(s['errors'] for s in self.stats.values())
        
        logger.info(f"\n{'TOTAL':10s}:")
        logger.info(f"  Arquivos: {total_files}")
        logger.info(f"  Registros: {total_records:,}")
        logger.info(f"  Erros: {total_errors}")
        logger.info("="*70)


async def main():
    """Função principal"""
    
    # Verificar se pastas existem
    if not PASTA_23E24.exists():
        logger.error(f"❌ Pasta não encontrada: {PASTA_23E24}")
        return
    
    logger.info("🚀 B3 Trading Platform - Importação Histórica")
    logger.info("="*70)
    logger.info(f"Pasta dados23e24: {PASTA_23E24}")
    logger.info(f"Pasta dados26: {PASTA_26} [JÁ IMPORTADO]")
    logger.info("="*70)
    
    importer = HistoricalDataImporter()
    
    try:
        # Conectar
        await importer.connect()
        
        # FASE 1: Prioritários
        await importer.import_priority_symbols()
        
        # Validar Fase 1
        await importer.validate_import(PRIORITY_SYMBOLS)
        
        # FASE 2: Restantes (opcional)
        logger.info("\n" + "="*70)
        response = input("\n🔄 Deseja continuar com a FASE 2 (53 símbolos restantes)? (s/N): ")
        if response.lower() == 's':
            await importer.import_remaining_symbols()
            
            # Validar Fase 2
            all_files = sorted(PASTA_23E24.glob("*_B_0_*.csv"))
            all_symbols = sorted(set(f.name.split('_')[0] for f in all_files))
            remaining = [s for s in all_symbols if s not in PRIORITY_SYMBOLS]
            await importer.validate_import(remaining)
        
        # Estatísticas finais
        importer.print_statistics()
        
        logger.success("\n🎉 Importação concluída com sucesso!")
    
    except Exception as e:
        logger.error(f"❌ Erro durante importação: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await importer.close()


if __name__ == '__main__':
    asyncio.run(main())
