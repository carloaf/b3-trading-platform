#!/usr/bin/env python3
"""
Import COTAHIST 2024 Data to TimescaleDB
========================================

Script para importar dados do arquivo COTAHIST_A2024.TXT para o TimescaleDB.

Formato COTAHIST (posições fixas):
- Posições 03-12: Data (AAAAMMDD)
- Posições 13-24: Código BDI + Código de negociação (símbolo)
- Posições 57-68: Preço de abertura (2 casas decimais)
- Posições 69-80: Preço máximo (2 casas decimais)
- Posições 81-92: Preço mínimo (2 casas decimais)
- Posições 109-121: Preço de fechamento (2 casas decimais)
- Posições 153-170: Volume total (quantidade)

Author: B3 Trading Platform
Date: 16 de Janeiro de 2026
"""

import asyncio
import asyncpg
from datetime import datetime
from pathlib import Path
from typing import List, Tuple
import sys


class CotahistImporter:
    """Importador de dados COTAHIST para TimescaleDB"""
    
    # Símbolos de interesse (mesmos do PASSO 8)
    TARGET_SYMBOLS = {
        'ITUB4', 'VALE3', 'PETR4', 'BBDC4', 'ABEV3',
        'MGLU3', 'WEGE3', 'RENT3', 'ELET3', 'SUZB3',
        'BBAS3', 'JBSS3', 'RAIL3', 'GGBR4', 'RADL3',
        'VIVT3', 'CSAN3', 'HAPV3', 'LREN3', 'EMBR3',
        'AZUL4', 'CPLE6', 'EGIE3', 'ENEV3', 'EQTL3',
        'CYRE3', 'MRFG3', 'BEEF3', 'CRFB3', 'PCAR3',
        'KLBN11', 'GOAU4', 'USIM5', 'BRFS3', 'TOTS3',
        'VBBR3', 'PETZ3', 'YDUQ3', 'SBSP3', 'CMIN3',
        'PRIO3', 'NTCO3', 'RRRP3'
    }
    
    def __init__(self, db_config: dict):
        self.db_config = db_config
        self.stats = {
            'total_lines': 0,
            'valid_lines': 0,
            'inserted': 0,
            'errors': 0,
            'by_symbol': {}
        }
    
    def parse_line(self, line: str) -> Tuple[str, datetime, float, float, float, float, float]:
        """
        Parse uma linha do COTAHIST
        
        Returns:
            (symbol, date, open, high, low, close, volume)
        """
        if len(line) < 245:
            return None
        
        # Tipo de registro (01 = dados)
        tipo_registro = line[0:2]
        if tipo_registro != '01':
            return None
        
        # Data (posições 2-10)
        data_str = line[2:10]
        try:
            data = datetime.strptime(data_str, '%Y%m%d')
        except ValueError:
            return None
        
        # Símbolo (posições 12-24, remove espaços)
        symbol = line[12:24].strip()
        
        # Filtrar apenas símbolos de interesse
        if symbol not in self.TARGET_SYMBOLS:
            return None
        
        # Tipo de mercado (010 = mercado à vista)
        tipo_mercado = line[24:27]
        if tipo_mercado != '010':
            return None
        
        try:
            # Preços (dividir por 100 para obter valor real)
            open_price = float(line[56:69]) / 100.0
            high_price = float(line[69:82]) / 100.0
            low_price = float(line[82:95]) / 100.0
            close_price = float(line[108:121]) / 100.0
            
            # Volume (quantidade de negócios)
            volume = float(line[152:170])
            
            # Validações básicas
            if high_price < low_price:
                return None
            if high_price < close_price or low_price > close_price:
                return None
            if any(p <= 0 for p in [open_price, high_price, low_price, close_price]):
                return None
            
            return (symbol, data, open_price, high_price, low_price, close_price, volume)
        
        except (ValueError, IndexError):
            return None
    
    async def import_file(self, file_path: Path, batch_size: int = 5000):
        """Importa arquivo COTAHIST para o banco"""
        
        print(f"\n📁 Abrindo arquivo: {file_path}")
        print(f"📊 Símbolos-alvo: {len(self.TARGET_SYMBOLS)} ativos")
        print(f"💾 Batch size: {batch_size}\n")
        
        conn = await asyncpg.connect(**self.db_config)
        
        try:
            batch = []
            
            with open(file_path, 'r', encoding='latin-1') as f:
                for line_num, line in enumerate(f, 1):
                    self.stats['total_lines'] = line_num
                    
                    parsed = self.parse_line(line)
                    
                    if parsed:
                        self.stats['valid_lines'] += 1
                        batch.append(parsed)
                        
                        # Atualizar stats por símbolo
                        symbol = parsed[0]
                        self.stats['by_symbol'][symbol] = self.stats['by_symbol'].get(symbol, 0) + 1
                    
                    # Inserir batch quando atingir o tamanho
                    if len(batch) >= batch_size:
                        inserted = await self._insert_batch(conn, batch)
                        self.stats['inserted'] += inserted
                        batch = []
                        
                        # Progress report
                        if line_num % 100000 == 0:
                            print(f"   📈 Processadas {line_num:,} linhas | "
                                  f"Válidas: {self.stats['valid_lines']:,} | "
                                  f"Inseridas: {self.stats['inserted']:,}")
            
            # Inserir batch restante
            if batch:
                inserted = await self._insert_batch(conn, batch)
                self.stats['inserted'] += inserted
            
            print(f"\n✅ Importação concluída!")
            print(f"   📊 Total de linhas: {self.stats['total_lines']:,}")
            print(f"   ✅ Linhas válidas: {self.stats['valid_lines']:,}")
            print(f"   💾 Registros inseridos: {self.stats['inserted']:,}")
            print(f"   ❌ Erros: {self.stats['errors']:,}")
            print(f"\n📈 Registros por símbolo:")
            
            # Top 10 símbolos
            top_symbols = sorted(self.stats['by_symbol'].items(), key=lambda x: x[1], reverse=True)[:10]
            for symbol, count in top_symbols:
                print(f"   {symbol}: {count:,} registros")
        
        finally:
            await conn.close()
    
    async def _insert_batch(self, conn: asyncpg.Connection, batch: List[Tuple]) -> int:
        """Insere um batch de dados no banco"""
        
        query = """
            INSERT INTO ohlcv_daily (symbol, time, open, high, low, close, volume)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (symbol, time) DO UPDATE SET
                open = EXCLUDED.open,
                high = EXCLUDED.high,
                low = EXCLUDED.low,
                close = EXCLUDED.close,
                volume = EXCLUDED.volume
        """
        
        try:
            await conn.executemany(query, batch)
            return len(batch)
        except Exception as e:
            print(f"   ⚠️  Erro ao inserir batch: {e}")
            self.stats['errors'] += len(batch)
            return 0


async def main():
    """Função principal"""
    
    # Configuração do banco (container)
    db_config = {
        'host': 'timescaledb',
        'port': 5432,
        'database': 'b3trading_market',
        'user': 'b3trading_ts',
        'password': 'b3trading_ts_pass'
    }
    
    # Caminho do arquivo (dentro do container será /data)
    file_path = Path('/data/COTAHIST_A2024.TXT')
    
    if not file_path.exists():
        print(f"❌ Arquivo não encontrado: {file_path}")
        print(f"   Certifique-se de montar o volume corretamente:")
        print(f"   docker run -v /path/to/COTAHIST_A2024.TXT:/data/COTAHIST_A2024.TXT ...")
        sys.exit(1)
    
    print("=" * 70)
    print("📊 COTAHIST 2024 IMPORTER")
    print("=" * 70)
    
    importer = CotahistImporter(db_config)
    await importer.import_file(file_path, batch_size=5000)
    
    print("\n" + "=" * 70)
    print("✅ Importação finalizada!")
    print("=" * 70)


if __name__ == '__main__':
    asyncio.run(main())
