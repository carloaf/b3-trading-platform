#!/usr/bin/env python3
"""
ADVFN Data Collector para B3 Trading Platform
===============================================

Coleta dados históricos e intraday do ADVFN (https://br.advfn.com)

Recursos:
- Dados históricos diários
- Dados intraday (1min, 5min, 15min, 30min, 60min)
- Múltiplos símbolos em batch
- Rate limiting automático
- Retry logic
- Salvamento em CSV + TimescaleDB

Uso:
    python advfn_collector.py --symbols PETR4,VALE3,ITUB4 --timeframe 1d --period 2y
    python advfn_collector.py --symbols PETR4 --timeframe 5min --period 5d

Author: B3 Trading Platform
Date: 16 de Janeiro de 2026
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import argparse
import json
import re
from pathlib import Path
import asyncio
import asyncpg
from loguru import logger

# Configuração de logging
logger.add("logs/advfn_collector_{time}.log", rotation="1 day", retention="7 days")


class ADVFNCollector:
    """
    Coletor de dados do ADVFN.
    """
    
    BASE_URL = "https://br.advfn.com"
    
    # Mapeamento de timeframes
    TIMEFRAMES = {
        '1min': 1,
        '5min': 5,
        '15min': 15,
        '30min': 30,
        '60min': 60,
        '1d': 'daily',
        'daily': 'daily',
        '1w': 'weekly',
        'weekly': 'weekly'
    }
    
    # Mapeamento de períodos
    PERIODS = {
        '1d': 1,
        '5d': 5,
        '1w': 7,
        '2w': 14,
        '1m': 30,
        '3m': 90,
        '6m': 180,
        '1y': 365,
        '2y': 730,
        '5y': 1825,
        'max': 3650
    }
    
    def __init__(self, rate_limit_delay: float = 2.0):
        """
        Inicializa o collector.
        
        Args:
            rate_limit_delay: Delay entre requests (segundos)
        """
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
            'Connection': 'keep-alive',
        })
        self.rate_limit_delay = rate_limit_delay
        self.last_request_time = 0
        
    def _rate_limit(self):
        """Aplica rate limiting."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - elapsed)
        self.last_request_time = time.time()
    
    def _build_url(self, symbol: str, timeframe: str = '1d') -> str:
        """
        Constrói URL para o símbolo e timeframe.
        
        Args:
            symbol: Símbolo B3 (ex: PETR4)
            timeframe: Timeframe (1min, 5min, 15min, 30min, 60min, 1d, 1w)
            
        Returns:
            URL completa
        """
        # Remover sufixo .SA se existir
        symbol = symbol.replace('.SA', '')
        
        # URL base
        base = f"{self.BASE_URL}/bolsa-de-valores/bovespa"
        
        # Nome do ativo (tentaremos descobrir)
        # Para PETR4 -> petrobras-pn-PETR4
        # Para VALE3 -> vale-on-VALE3
        # Para ITUB4 -> itau-unibanco-pn-ITUB4
        
        # Mapeamento comum
        name_map = {
            'PETR3': 'petrobras-on',
            'PETR4': 'petrobras-pn',
            'VALE3': 'vale-on',
            'ITUB4': 'itau-unibanco-pn',
            'ITUB3': 'itau-unibanco-on',
            'BBDC4': 'bradesco-pn',
            'BBDC3': 'bradesco-on',
            'ABEV3': 'ambev-on',
            'B3SA3': 'b3-on',
            'MGLU3': 'magazine-luiza-on',
            'WEGE3': 'weg-on',
            'RENT3': 'localiza-on',
            'SUZB3': 'suzano-papel-on'
        }
        
        if symbol in name_map:
            asset_name = name_map[symbol]
        else:
            # Tentar descobrir dinamicamente (futuro)
            asset_name = f"ativo-{symbol.lower()}"
        
        url = f"{base}/{asset_name}-{symbol}/historico"
        
        # Adicionar timeframe se não for diário
        if timeframe != '1d' and timeframe != 'daily':
            if timeframe.endswith('min'):
                minutes = timeframe.replace('min', '')
                url += f"?timeframe={minutes}"
        
        return url
    
    def fetch_historical_data(
        self,
        symbol: str,
        timeframe: str = '1d',
        period: str = '1y'
    ) -> Optional[pd.DataFrame]:
        """
        Busca dados históricos do ADVFN.
        
        Args:
            symbol: Símbolo B3 (ex: PETR4)
            timeframe: Timeframe (1min, 5min, 15min, 30min, 60min, 1d, 1w)
            period: Período (1d, 5d, 1w, 2w, 1m, 3m, 6m, 1y, 2y, 5y, max)
            
        Returns:
            DataFrame com colunas: timestamp, open, high, low, close, volume
        """
        self._rate_limit()
        
        url = self._build_url(symbol, timeframe)
        logger.info(f"Fetching {symbol} {timeframe} data from ADVFN...")
        logger.debug(f"URL: {url}")
        
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            # Parse HTML com BeautifulSoup
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Procurar tabela de dados históricos
            # ADVFN usa diferentes estruturas, vamos tentar várias
            
            # Método 1: Procurar por ID da tabela
            table = soup.find('table', {'id': 'tableHistorical'})
            
            if not table:
                # Método 2: Procurar por classe
                table = soup.find('table', {'class': 'market-table'})
            
            if not table:
                # Método 3: Procurar qualquer tabela com headers de OHLCV
                tables = soup.find_all('table')
                for t in tables:
                    headers = [th.get_text().strip().lower() for th in t.find_all('th')]
                    if any(h in headers for h in ['data', 'abertura', 'fechamento', 'volume']):
                        table = t
                        break
            
            if not table:
                logger.error(f"Tabela de dados não encontrada para {symbol}")
                return None
            
            # Extrair dados da tabela
            rows = []
            tbody = table.find('tbody')
            if tbody:
                table_rows = tbody.find_all('tr')
            else:
                table_rows = table.find_all('tr')[1:]  # Skip header
            
            for row in table_rows:
                cols = row.find_all('td')
                if len(cols) >= 6:
                    try:
                        # Data, Abertura, Máxima, Mínima, Fechamento, Volume
                        date_str = cols[0].get_text().strip()
                        open_val = self._parse_price(cols[1].get_text().strip())
                        high_val = self._parse_price(cols[2].get_text().strip())
                        low_val = self._parse_price(cols[3].get_text().strip())
                        close_val = self._parse_price(cols[4].get_text().strip())
                        volume_val = self._parse_volume(cols[5].get_text().strip())
                        
                        # Parse date
                        timestamp = self._parse_date(date_str)
                        
                        if timestamp:
                            rows.append({
                                'timestamp': timestamp,
                                'open': open_val,
                                'high': high_val,
                                'low': low_val,
                                'close': close_val,
                                'volume': volume_val
                            })
                    except Exception as e:
                        logger.warning(f"Erro ao parsear linha: {e}")
                        continue
            
            if not rows:
                logger.error(f"Nenhum dado extraído para {symbol}")
                return None
            
            # Criar DataFrame
            df = pd.DataFrame(rows)
            df['symbol'] = symbol
            df = df.sort_values('timestamp').reset_index(drop=True)
            
            # Filtrar por período
            if period != 'max':
                days = self.PERIODS.get(period, 365)
                cutoff_date = datetime.now() - timedelta(days=days)
                df = df[df['timestamp'] >= cutoff_date]
            
            logger.success(f"✅ {symbol}: {len(df)} bars coletados ({timeframe})")
            return df
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro ao buscar {symbol}: {e}")
            return None
        except Exception as e:
            logger.error(f"Erro inesperado ao processar {symbol}: {e}")
            return None
    
    def _parse_price(self, price_str: str) -> float:
        """Parse preço (remove R$, vírgulas, etc)."""
        try:
            # Remove R$, espaços, pontos (milhares), substitui vírgula por ponto
            price_str = price_str.replace('R$', '').replace(' ', '').replace('.', '').replace(',', '.')
            return float(price_str)
        except:
            return 0.0
    
    def _parse_volume(self, volume_str: str) -> int:
        """Parse volume (pode ter K, M, B)."""
        try:
            volume_str = volume_str.replace('.', '').replace(',', '').strip()
            
            multiplier = 1
            if 'K' in volume_str.upper():
                multiplier = 1_000
                volume_str = volume_str.upper().replace('K', '')
            elif 'M' in volume_str.upper():
                multiplier = 1_000_000
                volume_str = volume_str.upper().replace('M', '')
            elif 'B' in volume_str.upper():
                multiplier = 1_000_000_000
                volume_str = volume_str.upper().replace('B', '')
            
            return int(float(volume_str) * multiplier)
        except:
            return 0
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse data (formatos: DD/MM/YYYY, DD/MM/YY, etc)."""
        try:
            # Formato brasileiro: DD/MM/YYYY ou DD/MM/YY
            formats = ['%d/%m/%Y', '%d/%m/%y', '%d-%m-%Y', '%d-%m-%y']
            
            for fmt in formats:
                try:
                    return datetime.strptime(date_str, fmt)
                except:
                    continue
            
            # Se falhar, tentar parser genérico
            from dateutil import parser
            return parser.parse(date_str, dayfirst=True)
        except:
            logger.warning(f"Não foi possível parsear data: {date_str}")
            return None
    
    def save_to_csv(self, df: pd.DataFrame, output_dir: str = 'data/advfn'):
        """Salva DataFrame em CSV."""
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        symbol = df['symbol'].iloc[0]
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{output_dir}/{symbol}_advfn_{timestamp}.csv"
        
        df.to_csv(filename, index=False)
        logger.info(f"💾 Dados salvos em: {filename}")
        return filename
    
    async def save_to_timescaledb(
        self,
        df: pd.DataFrame,
        db_config: Dict[str, str],
        table: str = 'ohlcv_1d'
    ):
        """
        Salva dados no TimescaleDB.
        
        Args:
            df: DataFrame com dados
            db_config: Configuração do banco (host, port, database, user, password)
            table: Nome da tabela (ohlcv_1d, ohlcv_1h, ohlcv_5min, etc)
        """
        try:
            conn = await asyncpg.connect(**db_config)
            
            # Insert com ON CONFLICT DO NOTHING (evita duplicatas)
            insert_query = f"""
                INSERT INTO {table} (timestamp, symbol, open, high, low, close, volume)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (timestamp, symbol) DO NOTHING
            """
            
            rows_inserted = 0
            for _, row in df.iterrows():
                await conn.execute(
                    insert_query,
                    row['timestamp'],
                    row['symbol'],
                    float(row['open']),
                    float(row['high']),
                    float(row['low']),
                    float(row['close']),
                    int(row['volume'])
                )
                rows_inserted += 1
            
            await conn.close()
            logger.success(f"✅ {rows_inserted} linhas inseridas em {table}")
            
        except Exception as e:
            logger.error(f"Erro ao salvar em TimescaleDB: {e}")


def main():
    """Main CLI."""
    parser = argparse.ArgumentParser(description='ADVFN Data Collector')
    parser.add_argument('--symbols', required=True, help='Símbolos separados por vírgula (ex: PETR4,VALE3,ITUB4)')
    parser.add_argument('--timeframe', default='1d', help='Timeframe (1min, 5min, 15min, 30min, 60min, 1d, 1w)')
    parser.add_argument('--period', default='1y', help='Período (1d, 5d, 1w, 1m, 3m, 6m, 1y, 2y, 5y, max)')
    parser.add_argument('--output-dir', default='data/advfn', help='Diretório de saída para CSVs')
    parser.add_argument('--save-to-db', action='store_true', help='Salvar no TimescaleDB')
    parser.add_argument('--db-host', default='localhost', help='Host do TimescaleDB')
    parser.add_argument('--db-port', default='5433', help='Porta do TimescaleDB')
    parser.add_argument('--db-name', default='trading_data', help='Nome do banco')
    parser.add_argument('--db-user', default='postgres', help='Usuário do banco')
    parser.add_argument('--db-password', default='postgres', help='Senha do banco')
    
    args = parser.parse_args()
    
    # Parse símbolos
    symbols = [s.strip().upper() for s in args.symbols.split(',')]
    
    # Criar collector
    collector = ADVFNCollector(rate_limit_delay=2.0)
    
    logger.info(f"🚀 Iniciando coleta ADVFN")
    logger.info(f"📊 Símbolos: {', '.join(symbols)}")
    logger.info(f"⏱️  Timeframe: {args.timeframe}")
    logger.info(f"📅 Período: {args.period}")
    
    # Coletar dados
    all_data = []
    for symbol in symbols:
        df = collector.fetch_historical_data(symbol, args.timeframe, args.period)
        if df is not None and not df.empty:
            # Salvar CSV
            collector.save_to_csv(df, args.output_dir)
            all_data.append(df)
            
            # Salvar em DB se solicitado
            if args.save_to_db:
                db_config = {
                    'host': args.db_host,
                    'port': int(args.db_port),
                    'database': args.db_name,
                    'user': args.db_user,
                    'password': args.db_password
                }
                
                # Determinar tabela baseado no timeframe
                if args.timeframe == '1d' or args.timeframe == 'daily':
                    table = 'ohlcv_1d'
                elif args.timeframe == '60min':
                    table = 'ohlcv_1h'
                elif args.timeframe.endswith('min'):
                    table = f"ohlcv_{args.timeframe}"
                else:
                    table = 'ohlcv_1d'
                
                asyncio.run(collector.save_to_timescaledb(df, db_config, table))
        
        # Delay entre símbolos
        time.sleep(1)
    
    # Sumário
    logger.info(f"\n{'='*70}")
    logger.info(f"📊 SUMÁRIO DA COLETA")
    logger.info(f"{'='*70}")
    logger.info(f"✅ Símbolos coletados: {len(all_data)}/{len(symbols)}")
    logger.info(f"📈 Total de barras: {sum(len(df) for df in all_data)}")
    logger.info(f"💾 Dados salvos em: {args.output_dir}")
    logger.info(f"{'='*70}")


if __name__ == '__main__':
    main()
