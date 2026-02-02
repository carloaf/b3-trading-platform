#!/usr/bin/env python3
"""
ProfitChart CSV File Monitor
=============================

Monitora arquivos CSV exportados pelo ProfitChart em tempo real.

Estratégia:
    1. ProfitChart exporta quotes para CSV (configurável 1-5s)
    2. Script monitora pasta de export com watchdog
    3. Detecta mudanças e atualiza WebSocket

Vantagens:
    - Não precisa pywin32 ou DDE
    - Funciona 100% em Linux
    - Latência aceitável (1-5 segundos)
    - Simples e robusto

Configuração no ProfitChart:
    Ferramentas > Opções > Avançado > Exportação Automática
    - Formato: CSV
    - Frequência: 1 segundo
    - Pasta: ~/profitchart_export/

Autor: B3 Trading Platform
Data: 30 Janeiro 2026
"""

import asyncio
import csv
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List
import logging

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ProfitChartCSVMonitor:
    """Monitora CSVs exportados pelo ProfitChart"""
    
    def __init__(self, 
                 export_folder: str = "~/profitchart_export",
                 symbols: List[str] = None,
                 poll_interval: float = 1.0):
        """
        Args:
            export_folder: Pasta onde ProfitChart exporta CSVs
            symbols: Lista de símbolos para monitorar
            poll_interval: Intervalo entre verificações (segundos)
        """
        self.export_folder = Path(export_folder).expanduser()
        self.symbols = symbols or ['PETR3', 'PETR4', 'VALE3', 'BBAS3', 'ITUB4']
        self.poll_interval = poll_interval
        self.last_modified = {}
        self.last_data = {}
        
        logger.info(f"📁 Monitorando pasta: {self.export_folder}")
        logger.info(f"📊 Símbolos: {', '.join(self.symbols)}")
        logger.info(f"⏱️  Intervalo: {poll_interval}s")
    
    def _get_csv_file(self, symbol: str) -> Path:
        """Retorna caminho do arquivo CSV do símbolo"""
        # ProfitChart geralmente usa formato: PETR4.csv ou quotes_PETR4.csv
        for pattern in [f"{symbol}.csv", f"quotes_{symbol}.csv", f"{symbol}_quote.csv"]:
            file_path = self.export_folder / pattern
            if file_path.exists():
                return file_path
        
        # Se não existe, retorna o padrão esperado
        return self.export_folder / f"{symbol}.csv"
    
    def _parse_csv_line(self, line: List[str], symbol: str) -> Dict:
        """
        Parse linha CSV do ProfitChart
        
        Formato esperado (9 campos):
        symbol;date;time;last;bid;ask;volume;variation;status
        
        Ou formato simplificado (4 campos):
        symbol;last;volume;timestamp
        """
        try:
            # Formato completo (9 campos)
            if len(line) >= 7:
                return {
                    'symbol': line[0] or symbol,
                    'date': line[1],
                    'time': line[2],
                    'last': float(line[3].replace(',', '.')),
                    'bid': float(line[4].replace(',', '.')) if line[4] else None,
                    'ask': float(line[5].replace(',', '.')) if line[5] else None,
                    'volume': int(float(line[6].replace(',', '.'))) if line[6] else 0,
                    'variation': float(line[7].replace(',', '.')) if len(line) > 7 and line[7] else 0,
                    'status': line[8] if len(line) > 8 else 'UNKNOWN'
                }
            
            # Formato simplificado (4 campos)
            elif len(line) >= 3:
                return {
                    'symbol': line[0] or symbol,
                    'last': float(line[1].replace(',', '.')),
                    'volume': int(float(line[2].replace(',', '.'))) if line[2] else 0,
                    'timestamp': line[3] if len(line) > 3 else datetime.now().isoformat()
                }
            
            else:
                logger.warning(f"⚠️  CSV inválido para {symbol}: {line}")
                return None
                
        except (ValueError, IndexError) as e:
            logger.error(f"❌ Erro ao parsear CSV {symbol}: {e}")
            return None
    
    def _read_latest_quote(self, symbol: str) -> Dict:
        """Lê última cotação do arquivo CSV"""
        csv_file = self._get_csv_file(symbol)
        
        if not csv_file.exists():
            logger.debug(f"📄 CSV não existe: {csv_file}")
            return None
        
        # Verificar se arquivo foi modificado
        modified_time = csv_file.stat().st_mtime
        if symbol in self.last_modified:
            if self.last_modified[symbol] == modified_time:
                # Arquivo não mudou, retornar cache
                return self.last_data.get(symbol)
        
        # Arquivo mudou ou primeira leitura
        try:
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.reader(f, delimiter=';')
                
                # Pular header se existir
                rows = list(reader)
                if not rows:
                    return None
                
                # Se primeira linha parece header, pular
                if 'symbol' in rows[0][0].lower() or 'last' in str(rows[0]).lower():
                    rows = rows[1:]
                
                if not rows:
                    return None
                
                # Última linha = última cotação
                last_line = rows[-1]
                quote = self._parse_csv_line(last_line, symbol)
                
                if quote:
                    self.last_modified[symbol] = modified_time
                    self.last_data[symbol] = quote
                    logger.debug(f"✅ {symbol}: R$ {quote.get('last', 0):.2f}")
                
                return quote
                
        except Exception as e:
            logger.error(f"❌ Erro ao ler {csv_file}: {e}")
            return None
    
    async def get_all_quotes(self) -> Dict[str, Dict]:
        """Obtém cotações de todos os símbolos"""
        quotes = {}
        
        for symbol in self.symbols:
            quote = self._read_latest_quote(symbol)
            if quote:
                quotes[symbol] = quote
        
        return quotes
    
    async def monitor_loop(self, callback=None):
        """
        Loop principal de monitoramento
        
        Args:
            callback: Função async para chamar quando dados mudarem
        """
        logger.info("🚀 Iniciando monitoramento...")
        
        while True:
            try:
                quotes = await self.get_all_quotes()
                
                if quotes and callback:
                    await callback(quotes)
                
                await asyncio.sleep(self.poll_interval)
                
            except KeyboardInterrupt:
                logger.info("⏸️  Monitoramento interrompido")
                break
            except Exception as e:
                logger.error(f"❌ Erro no loop: {e}")
                await asyncio.sleep(self.poll_interval)


def connect_csv_monitor(symbols: List[str]) -> Dict[str, Dict]:
    """
    Interface síncrona para compatibilidade com dde_wrapper.py
    
    Args:
        symbols: Lista de símbolos para monitorar
    
    Returns:
        Dict com cotações atuais
    """
    monitor = ProfitChartCSVMonitor(symbols=symbols)
    
    # Executar uma vez de forma síncrona
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        quotes = loop.run_until_complete(monitor.get_all_quotes())
        return quotes
    finally:
        loop.close()


async def main_test():
    """Teste standalone"""
    async def print_quotes(quotes):
        print(f"\n📊 {datetime.now().strftime('%H:%M:%S')}")
        for symbol, data in quotes.items():
            last = data.get('last', 0)
            var = data.get('variation', 0)
            print(f"  {symbol}: R$ {last:.2f} ({var:+.2f}%)")
    
    monitor = ProfitChartCSVMonitor(
        export_folder="~/profitchart_export",
        symbols=['PETR4', 'VALE3', 'ITUB4', 'BBAS3'],
        poll_interval=2.0
    )
    
    await monitor.monitor_loop(callback=print_quotes)


if __name__ == '__main__':
    try:
        asyncio.run(main_test())
    except KeyboardInterrupt:
        print("\n👋 Monitoramento encerrado")
