#!/usr/bin/env python3
"""
B3 COTAHIST Parser - Extração de Dados Históricos Oficiais
============================================================

Parser para arquivos COTAHIST da B3 (formato texto de largura fixa).

Formato COTAHIST (B3):
- Tipo 00: Header (registro de identificação)
- Tipo 01: Cotação (dados de negociação)
- Tipo 99: Trailer (total de registros)

Layout do Registro Tipo 01 (245 caracteres):
- Posição 001-002: Tipo de registro (01)
- Posição 003-010: Data do pregão (AAAAMMDD)
- Posição 011-012: CODBDI (código BDI)
- Posição 013-024: Código de negociação (ticker)
- Posição 025-027: Tipo de mercado
- Posição 028-039: Nome resumido da empresa
- Posição 040-049: Especificação do papel
- Posição 050-052: Prazo em dias
- Posição 053-064: Moeda de referência
- Posição 057-069: Preço de abertura (13 dígitos, últimos 2 são decimais)
- Posição 070-082: Preço máximo
- Posição 083-095: Preço mínimo
- Posição 096-108: Preço médio
- Posição 109-121: Preço de fechamento
- Posição 122-134: Melhor oferta de compra
- Posição 135-147: Melhor oferta de venda
- Posição 148-152: Número de negócios
- Posição 153-170: Quantidade de títulos negociados
- Posição 171-188: Volume total de negócios (18 dígitos, últimos 2 são decimais)
- Posição 189-201: Preço de exercício (opções)
- Posição 202-202: Indicador de correção
- Posição 203-215: Preço de exercício em moeda
- Posição 216-230: Código ISIN
- Posição 231-242: Número de distribuição

Autor: B3 Trading Platform Team
Data: 16 de Janeiro de 2026
"""

import os
import sys
from datetime import datetime
from typing import List, Dict, Optional, Set
from pathlib import Path
import pandas as pd
import asyncio
import asyncpg


class COTAHISTParser:
    """Parser para arquivos COTAHIST da B3."""
    
    # Tipos de mercado de interesse (ações à vista)
    MARKET_TYPES = {'010'}  # Mercado à vista
    
    # Códigos BDI de interesse (02 = lote padrão)
    BDI_CODES = {'02'}
    
    # Símbolos de interesse (principais ações B3) - EXPANDIDO PARA 40+
    DEFAULT_SYMBOLS = {
        # Bancos (6)
        'ITUB4', 'BBDC4', 'BBAS3', 'SANB11', 'ITUB3', 'BBDC3',
        
        # Energia (5)
        'PETR4', 'PETR3', 'PRIO3', 'RRRP3', 'CSAN3',
        
        # Mineração/Siderurgia (5)
        'VALE3', 'CSNA3', 'GGBR4', 'USIM5', 'GOAU4',
        
        # Varejo (6)
        'MGLU3', 'AMER3', 'LREN3', 'PCAR3', 'VIIA3', 'ARZZ3',
        
        # Consumo (4)
        'ABEV3', 'JBSS3', 'BEEF3', 'SMTO3',
        
        # Utilities (5)
        'ELET3', 'ELET6', 'CPLE6', 'CMIG4', 'TAEE11',
        
        # Financeiro/Bolsa (2)
        'B3SA3', 'BBSE3',
        
        # Industrial (4)
        'WEGE3', 'RAIL3', 'EMBR3', 'AZUL4',
        
        # Telecom (2)
        'VIVT3', 'TIMS3',
        
        # Imobiliário (1)
        'MULT3',
        
        # Saúde (2)
        'RDOR3', 'HAPV3',
        
        # Logística (2)
        'RENT3', 'RADL3',
        
        # Tecnologia (1)
        'TOTS3',
        
        # Papel/Celulose (2)
        'SUZB3', 'KLBN11'
    }
    
    def __init__(self, filepath: str):
        """
        Inicializa o parser.
        
        Args:
            filepath: Caminho para o arquivo COTAHIST (ex: COTAHIST_A2025.TXT)
        """
        self.filepath = Path(filepath)
        if not self.filepath.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {filepath}")
        
        self.records = []
        self.stats = {
            'total_lines': 0,
            'header_lines': 0,
            'data_lines': 0,
            'trailer_lines': 0,
            'parsed_records': 0,
            'skipped_records': 0,
            'symbols_found': set()
        }
    
    def parse(self, symbols: Optional[Set[str]] = None) -> List[Dict]:
        """
        Faz parsing do arquivo COTAHIST.
        
        Args:
            symbols: Conjunto de símbolos para filtrar (None = todos os símbolos padrão)
        
        Returns:
            Lista de dicionários com dados OHLCV
        """
        if symbols is None:
            symbols = self.DEFAULT_SYMBOLS
        
        print(f"\n📊 Parsing COTAHIST: {self.filepath.name}")
        print(f"🎯 Filtrando símbolos: {', '.join(sorted(symbols))}")
        
        with open(self.filepath, 'r', encoding='latin-1') as f:
            for line in f:
                self.stats['total_lines'] += 1
                
                # Identificar tipo de registro
                tipo_registro = line[0:2]
                
                if tipo_registro == '00':
                    # Header
                    self.stats['header_lines'] += 1
                    self._parse_header(line)
                
                elif tipo_registro == '01':
                    # Dados de cotação
                    self.stats['data_lines'] += 1
                    record = self._parse_data_line(line, symbols)
                    if record:
                        self.records.append(record)
                        self.stats['parsed_records'] += 1
                        self.stats['symbols_found'].add(record['symbol'])
                    else:
                        self.stats['skipped_records'] += 1
                
                elif tipo_registro == '99':
                    # Trailer
                    self.stats['trailer_lines'] += 1
                    self._parse_trailer(line)
        
        print(f"\n✅ Parsing concluído!")
        print(f"   Total de linhas: {self.stats['total_lines']}")
        print(f"   Registros processados: {self.stats['parsed_records']}")
        print(f"   Registros ignorados: {self.stats['skipped_records']}")
        print(f"   Símbolos encontrados: {len(self.stats['symbols_found'])}")
        print(f"   → {', '.join(sorted(self.stats['symbols_found']))}")
        
        return self.records
    
    def _parse_header(self, line: str):
        """Parse do registro de header (tipo 00)."""
        # Formato: 00COTAHIST.2025BOVESPA 20251230
        try:
            arquivo = line[2:17].strip()  # COTAHIST.2025
            origem = line[17:25].strip()  # BOVESPA
            data_geracao = line[25:33].strip()  # 20251230
            print(f"📄 Header: {arquivo} - Origem={origem}, Data={data_geracao}")
        except:
            print(f"📄 Header: {line[:40].strip()}")
    
    def _parse_trailer(self, line: str):
        """Parse do registro de trailer (tipo 99)."""
        # Formato: 99COTAHIST.2025BOVESPA 2025123000003174698
        try:
            arquivo = line[2:17].strip()  # COTAHIST.2025
            origem = line[17:25].strip()  # BOVESPA
            data = line[25:33].strip()  # 20251230
            total_registros = int(line[33:44])  # 00003174698
            print(f"📄 Trailer: Total de registros = {total_registros:,}")
        except Exception as e:
            print(f"📄 Trailer: {line[:50].strip()}")
    
    def _parse_data_line(self, line: str, symbols: Set[str]) -> Optional[Dict]:
        """
        Parse de uma linha de dados (tipo 01).
        
        Args:
            line: Linha do arquivo (245 caracteres)
            symbols: Símbolos para filtrar
        
        Returns:
            Dicionário com dados OHLCV ou None se não atender aos filtros
        """
        # Extrair campos usando posições fixas
        try:
            data_pregao = line[2:10]  # AAAAMMDD
            codbdi = line[10:12].strip()
            codneg = line[12:24].strip()  # Ticker
            tpmerc = line[24:27].strip()
            nomres = line[27:39].strip()
            
            # Preços (13 dígitos, últimos 2 são decimais, dividir por 100)
            preabe = int(line[56:69]) / 100.0  # Abertura
            premax = int(line[69:82]) / 100.0  # Máximo
            premin = int(line[82:95]) / 100.0  # Mínimo
            premed = int(line[95:108]) / 100.0  # Médio
            preult = int(line[108:121]) / 100.0  # Último (fechamento)
            
            # Volume e negócios
            totneg = int(line[147:152])  # Número de negócios
            quatot = int(line[152:170])  # Quantidade de títulos
            voltot = int(line[170:188]) / 100.0  # Volume total
            
            # Filtros
            # 1. Apenas mercado à vista (010)
            if tpmerc not in self.MARKET_TYPES:
                return None
            
            # 2. Apenas lote padrão (BDI = 02)
            if codbdi not in self.BDI_CODES:
                return None
            
            # 3. Apenas símbolos de interesse
            if codneg not in symbols:
                return None
            
            # 4. Ignorar registros sem negociação
            if totneg == 0 or voltot == 0:
                return None
            
            # Converter data de AAAAMMDD para datetime
            date = datetime.strptime(data_pregao, '%Y%m%d')
            
            return {
                'date': date,
                'symbol': codneg,
                'name': nomres,
                'open': preabe,
                'high': premax,
                'low': premin,
                'close': preult,
                'volume': int(quatot),
                'trades': totneg,
                'turnover': voltot,  # Volume financeiro
                'avg_price': premed
            }
        
        except (ValueError, IndexError) as e:
            # Linha malformada, ignorar
            return None
    
    def to_dataframe(self) -> pd.DataFrame:
        """
        Converte os registros parseados para DataFrame.
        
        Returns:
            DataFrame com colunas: date, symbol, open, high, low, close, volume
        """
        if not self.records:
            print("⚠️  Nenhum registro foi parseado. Execute parse() primeiro.")
            return pd.DataFrame()
        
        df = pd.DataFrame(self.records)
        
        # Ordenar por símbolo e data
        df = df.sort_values(['symbol', 'date']).reset_index(drop=True)
        
        print(f"\n📊 DataFrame criado:")
        print(f"   Shape: {df.shape}")
        print(f"   Período: {df['date'].min()} até {df['date'].max()}")
        print(f"   Símbolos: {df['symbol'].nunique()}")
        
        return df
    
    def save_to_csv(self, output_dir: str = 'data/cotahist'):
        """
        Salva os dados em arquivos CSV (um por símbolo).
        
        Args:
            output_dir: Diretório de saída para os CSVs
        """
        if not self.records:
            print("⚠️  Nenhum registro para salvar.")
            return
        
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        df = self.to_dataframe()
        
        # Salvar um CSV por símbolo
        for symbol in df['symbol'].unique():
            df_symbol = df[df['symbol'] == symbol]
            
            csv_file = output_path / f"{symbol}_2025.csv"
            df_symbol.to_csv(csv_file, index=False)
            print(f"💾 {symbol}: {len(df_symbol)} registros → {csv_file}")
        
        # Salvar CSV consolidado
        csv_all = output_path / "cotahist_2025_all.csv"
        df.to_csv(csv_all, index=False)
        print(f"\n💾 Consolidado: {len(df)} registros → {csv_all}")
    
    async def save_to_timescaledb(
        self,
        db_host: str = 'localhost',
        db_port: int = 5432,
        db_name: str = 'trading_db',
        db_user: str = 'trading_user',
        db_password: str = 'trading_pass'
    ):
        """
        Salva os dados no TimescaleDB.
        
        Args:
            db_host: Host do banco de dados
            db_port: Porta do banco de dados
            db_name: Nome do banco de dados
            db_user: Usuário do banco
            db_password: Senha do banco
        """
        if not self.records:
            print("⚠️  Nenhum registro para salvar.")
            return
        
        print(f"\n🗄️  Conectando ao TimescaleDB ({db_host}:{db_port})...")
        
        try:
            conn = await asyncpg.connect(
                host=db_host,
                port=db_port,
                database=db_name,
                user=db_user,
                password=db_password
            )
            
            print(f"✅ Conectado ao banco de dados: {db_name}")
            
            # Criar tabela se não existir
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS ohlcv_daily (
                    time TIMESTAMPTZ NOT NULL,
                    symbol VARCHAR(20) NOT NULL,
                    open DOUBLE PRECISION,
                    high DOUBLE PRECISION,
                    low DOUBLE PRECISION,
                    close DOUBLE PRECISION,
                    volume BIGINT,
                    trades INTEGER,
                    turnover DOUBLE PRECISION,
                    avg_price DOUBLE PRECISION,
                    PRIMARY KEY (time, symbol)
                );
                
                SELECT create_hypertable('ohlcv_daily', 'time', 
                    if_not_exists => TRUE, 
                    chunk_time_interval => INTERVAL '1 month'
                );
            """)
            
            print("✅ Tabela ohlcv_daily verificada/criada")
            
            # Inserir dados em batch
            inserted = 0
            skipped = 0
            
            for record in self.records:
                try:
                    await conn.execute("""
                        INSERT INTO ohlcv_daily 
                        (time, symbol, open, high, low, close, volume, trades, turnover, avg_price)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                        ON CONFLICT (time, symbol) DO NOTHING
                    """,
                        record['date'],
                        record['symbol'],
                        record['open'],
                        record['high'],
                        record['low'],
                        record['close'],
                        record['volume'],
                        record['trades'],
                        record['turnover'],
                        record['avg_price']
                    )
                    inserted += 1
                except Exception as e:
                    skipped += 1
            
            print(f"\n✅ Inserção concluída:")
            print(f"   Registros inseridos: {inserted}")
            print(f"   Registros ignorados (duplicados): {skipped}")
            
            await conn.close()
        
        except Exception as e:
            print(f"❌ Erro ao conectar/inserir no banco: {e}")
            raise


def main():
    """Função principal CLI."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Parser para arquivos COTAHIST da B3',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos de uso:

  # Parse básico (símbolos padrão)
  python cotahist_parser.py COTAHIST_A2025.TXT
  
  # Parse com símbolos específicos
  python cotahist_parser.py COTAHIST_A2025.TXT --symbols PETR4 VALE3 ITUB4
  
  # Salvar em CSV
  python cotahist_parser.py COTAHIST_A2025.TXT --csv --output-dir data/cotahist
  
  # Salvar no TimescaleDB
  python cotahist_parser.py COTAHIST_A2025.TXT --db --db-host timescaledb
  
  # Salvar em ambos
  python cotahist_parser.py COTAHIST_A2025.TXT --csv --db
        """
    )
    
    parser.add_argument('filepath', help='Caminho para o arquivo COTAHIST (ex: COTAHIST_A2025.TXT)')
    parser.add_argument('--symbols', nargs='+', help='Lista de símbolos para filtrar (ex: PETR4 VALE3)')
    parser.add_argument('--csv', action='store_true', help='Salvar dados em CSV')
    parser.add_argument('--output-dir', default='data/cotahist', help='Diretório para salvar CSVs')
    parser.add_argument('--db', action='store_true', help='Salvar dados no TimescaleDB')
    parser.add_argument('--db-host', default='localhost', help='Host do TimescaleDB')
    parser.add_argument('--db-port', type=int, default=5432, help='Porta do TimescaleDB')
    parser.add_argument('--db-name', default='trading_db', help='Nome do banco de dados')
    parser.add_argument('--db-user', default='trading_user', help='Usuário do banco')
    parser.add_argument('--db-password', default='trading_pass', help='Senha do banco')
    
    args = parser.parse_args()
    
    # Parse do arquivo
    cotahist = COTAHISTParser(args.filepath)
    
    symbols = set(args.symbols) if args.symbols else None
    cotahist.parse(symbols)
    
    # Salvar em CSV
    if args.csv:
        cotahist.save_to_csv(args.output_dir)
    
    # Salvar no TimescaleDB
    if args.db:
        asyncio.run(cotahist.save_to_timescaledb(
            db_host=args.db_host,
            db_port=args.db_port,
            db_name=args.db_name,
            db_user=args.db_user,
            db_password=args.db_password
        ))
    
    # Mostrar preview dos dados
    if cotahist.records:
        df = cotahist.to_dataframe()
        print("\n📊 Preview dos dados (primeiras 10 linhas):")
        print(df.head(10).to_string())
        
        print("\n📊 Estatísticas por símbolo:")
        stats = df.groupby('symbol').agg({
            'date': ['min', 'max', 'count'],
            'volume': 'sum',
            'turnover': 'sum'
        }).round(2)
        print(stats)


if __name__ == '__main__':
    main()
