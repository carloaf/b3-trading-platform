"""
B3 API Integration - Ticker Discovery & COTAHIST Integration
============================================================

Integra com API B3 de dados históricos para descobrir ativos disponíveis:
https://cvscarlos.github.io/b3-api-dados-historicos/

Endpoints:
- GET /api/v1/tickers-cash-market.json - Lista todos os ativos disponíveis

Após descobrir os ativos, usa COTAHIST para baixar dados históricos reais.

Autor: Stock-IndiceDev Assistant
Data: 19/01/2026
"""

import asyncio
import asyncpg
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from loguru import logger
import pandas as pd
import time

# Configurações
B3_API_BASE = "https://cvscarlos.github.io/b3-api-dados-historicos/api/v1"
DB_CONFIG = {
    'host': 'timescaledb',
    'port': 5432,
    'database': 'b3trading_market',
    'user': 'b3trading_ts',
    'password': 'b3trading_ts_pass'
}


class B3APIIntegration:
    """
    Integração com API B3 para descobrir ativos disponíveis
    
    IMPORTANTE: Esta API fornece apenas a LISTA de ativos disponíveis,
    não os dados históricos. Para baixar dados históricos, use:
    - scripts/cotahist_parser.py (dados oficiais B3)
    - BRAPI (API alternativa com dados em tempo real)
    """
    
    def __init__(self):
        self.base_url = B3_API_BASE
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'B3TradingPlatform/1.0',
            'Accept': 'application/json'
        })
    
    def get_available_tickers(self) -> Dict[str, Dict]:
        """
        Baixa lista de todos os ativos disponíveis na API B3
        
        Returns:
            Dict com ticker -> {codNeg, nomeCurto, especPapel, dataMin, dataMax}
            
        Exemplo:
            {
                "PETR4": {
                    "codNeg": "PETR4",
                    "nomeCurto": "PETROBRAS",
                    "especPapel": "PN N2",
                    "dataMax": 20260116,  # YYYYMMDD
                    "dataMin": 20100104
                }
            }
        """
        url = f"{self.base_url}/tickers-cash-market.json"
        logger.info(f"📥 Baixando lista de ativos: {url}")
        
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            tickers = data.get('data', {})
            logger.success(f"✅ {len(tickers)} ativos disponíveis")
            
            return tickers
        
        except requests.RequestException as e:
            logger.error(f"❌ Erro ao baixar lista de ativos: {e}")
            return {}
    
    def export_to_csv(self, output_file: str = 'b3_tickers_list.csv'):
        """
        Exporta lista de ativos para CSV
        
        Args:
            output_file: Nome do arquivo de saída
        """
        tickers = self.get_available_tickers()
        
        if not tickers:
            logger.error("❌ Nenhum ativo para exportar")
            return
        
        # Converter para DataFrame
        records = []
        for ticker, info in tickers.items():
            records.append({
                'ticker': ticker,
                'nome': info['nomeCurto'],
                'especificacao': info['especPapel'],
                'data_min': info['dataMin'],
                'data_max': info['dataMax']
            })
        
        df = pd.DataFrame(records)
        df = df.sort_values('ticker')
        
        df.to_csv(output_file, index=False, encoding='utf-8')
        logger.success(f"✅ Lista exportada: {output_file}")
        logger.info(f"   Total: {len(df)} ativos")
    
    def get_bluechips(self) -> List[str]:
        """
        Retorna lista de blue chips brasileiras (ações mais líquidas)
        
        Returns:
            Lista de tickers
        """
        bluechips = [
            'PETR4',  # Petrobras PN
            'VALE3',  # Vale ON
            'ITUB4',  # Itaú PN
            'BBDC4',  # Bradesco PN
            'ABEV3',  # Ambev ON
            'B3SA3',  # B3 ON
            'WEGE3',  # WEG ON
            'RENT3',  # Localiza ON
            'SUZB3',  # Suzano ON
            'RAIL3',  # Rumo ON
            'BBAS3',  # Banco do Brasil ON
            'JBSS3',  # JBS ON
            'MGLU3',  # Magazine Luiza ON
            'VIVT3',  # Telefonica Brasil ON
            'ELET3',  # Eletrobras ON
            'CSNA3',  # CSN ON
            'USIM5',  # Usiminas PNA
            'GGBR4',  # Gerdau PN
            'EMBR3',  # Embraer ON
            'RADL3',  # Raia Drogasil ON
        ]
        
        logger.info(f"📊 {len(bluechips)} blue chips brasileiras")
        return bluechips
    
    def get_ibov_components(self) -> List[str]:
        """
        Retorna componentes aproximados do Ibovespa (ativos mais relevantes)
        
        Returns:
            Lista de tickers
        """
        # Top 50 componentes aproximados do Ibovespa
        # (baseado em peso histórico e liquidez)
        ibov = [
            # Top 10 (maior peso)
            'PETR4', 'VALE3', 'ITUB4', 'BBDC4', 'ABEV3',
            'B3SA3', 'WEGE3', 'RENT3', 'SUZB3', 'RAIL3',
            
            # Top 20
            'BBAS3', 'JBSS3', 'MGLU3', 'VIVT3', 'ELET3',
            'CSNA3', 'USIM5', 'GGBR4', 'EMBR3', 'RADL3',
            
            # Top 30
            'HAPV3', 'RDOR3', 'KLBN11', 'EQTL3', 'CPLE6',
            'ENBR3', 'ENGI11', 'SBSP3', 'CMIG4', 'TAEE11',
            
            # Top 40
            'CSAN3', 'UGPA3', 'LREN3', 'BRDT3', 'YDUQ3',
            'CCRO3', 'BPAC11', 'TOTS3', 'PRIO3', 'BEEF3',
            
            # Top 50
            'CYRE3', 'MRFG3', 'GOLL4', 'AZUL4', 'LWSA3',
            'VBBR3', 'SANB11', 'ITSA4', 'CRFB3', 'COGN3'
        ]
        
        logger.info(f"📈 {len(ibov)} componentes Ibovespa")
        return ibov
    
    def filter_top_liquidity(self, tickers: Dict[str, Dict], top_n: int = 100) -> List[str]:
        """
        Filtra ativos com maior histórico disponível (proxy de liquidez)
        
        Args:
            tickers: Dict de ativos retornado por get_available_tickers()
            top_n: Número de ativos a retornar
        
        Returns:
            Lista de tickers ordenados por tamanho de histórico
        """
        # Calcular tamanho do histórico (dataMax - dataMin)
        ticker_ranges = []
        for ticker, info in tickers.items():
            try:
                data_min = datetime.strptime(str(info['dataMin']), '%Y%m%d')
                data_max = datetime.strptime(str(info['dataMax']), '%Y%m%d')
                days = (data_max - data_min).days
                ticker_ranges.append((ticker, days, info['nomeCurto']))
            except:
                continue
        
        # Ordenar por tamanho de histórico
        ticker_ranges.sort(key=lambda x: x[1], reverse=True)
        
        logger.info(f"🏆 Top {top_n} ativos por histórico:")
        for i, (ticker, days, nome) in enumerate(ticker_ranges[:top_n], 1):
            logger.info(f"   {i:3}. {ticker:8} | {nome:20} | {days:5} dias")
        
        return [ticker for ticker, _, _ in ticker_ranges[:top_n]]
    
    def filter_by_names(self, tickers: Dict[str, Dict], names: List[str]) -> List[str]:
        """
        Filtra ativos por lista de nomes conhecidos
        
        Args:
            tickers: Dict de ativos
            names: Lista de nomes para buscar (ex: ['PETROBRAS', 'VALE', 'ITAU'])
        
        Returns:
            Lista de tickers encontrados
        """
        found = []
        for ticker, info in tickers.items():
            nome_curto = info['nomeCurto'].upper()
            for name in names:
                if name.upper() in nome_curto:
                    found.append(ticker)
                    logger.info(f"   ✓ {ticker:8} | {info['nomeCurto']:20}")
        
        return found


def analyze_tickers():
    """Analisa ativos disponíveis e gera relatório"""
    api = B3APIIntegration()
    
    logger.info("=" * 80)
    logger.info("ANÁLISE DE ATIVOS B3 DISPONÍVEIS")
    logger.info("=" * 80)
    
    # 1. Baixar lista completa
    tickers = api.get_available_tickers()
    
    if not tickers:
        logger.error("❌ Falha ao baixar lista de ativos")
        return
    
    logger.info(f"\n📊 Total de ativos: {len(tickers)}")
    
    # 2. Filtrar por tipo
    tipos = {}
    for ticker, info in tickers.items():
        tipo = info.get('especPapel', 'OUTROS')
        if tipo not in tipos:
            tipos[tipo] = []
        tipos[tipo].append(ticker)
    
    logger.info(f"\n📋 Tipos de ativos:")
    for tipo, lista in sorted(tipos.items(), key=lambda x: len(x[1]), reverse=True)[:20]:
        logger.info(f"   {tipo:20} | {len(lista):5} ativos")
    
    # 3. Verificar blue chips
    logger.info(f"\n🔵 Blue Chips Brasileiras:")
    bluechips = api.get_bluechips()
    for ticker in bluechips[:10]:
        if ticker in tickers:
            info = tickers[ticker]
            logger.info(f"   ✓ {ticker:8} | {info['nomeCurto']:20} | {info['dataMin']} -> {info['dataMax']}")
        else:
            logger.warning(f"   ✗ {ticker:8} | NÃO ENCONTRADO")
    
    # 4. Top por histórico
    logger.info(f"\n🏆 Top 20 por tamanho de histórico:")
    top = api.filter_top_liquidity(tickers, top_n=20)
    
    # 5. Exportar CSV
    logger.info(f"\n💾 Exportando para CSV...")
    api.export_to_csv('b3_tickers_list.csv')
    
    logger.info("=" * 80)
    logger.info("✅ Análise completa!")
    logger.info("=" * 80)


def recommend_tickers_for_download():
    """
    Recomenda quais ativos baixar baseado em:
    - Liquidez (tamanho do histórico)
    - Relevância (Ibovespa, blue chips)
    - Qualidade dos dados (data_min < 2015)
    """
    api = B3APIIntegration()
    tickers_info = api.get_available_tickers()
    
    if not tickers_info:
        logger.error("❌ Falha ao baixar lista de ativos")
        return
    
    logger.info("=" * 80)
    logger.info("RECOMENDAÇÕES DE DOWNLOAD")
    logger.info("=" * 80)
    
    # 1. Ibovespa (prioridade máxima)
    ibov = api.get_ibov_components()
    ibov_available = [t for t in ibov if t in tickers_info]
    logger.info(f"\n🥇 PRIORIDADE 1: Componentes Ibovespa")
    logger.info(f"   {len(ibov_available)}/{len(ibov)} disponíveis")
    logger.info(f"   Comando: python b3_api_integration.py check-ibov")
    
    # 2. Blue chips não no Ibovespa
    bluechips = api.get_bluechips()
    bluechips_extra = [t for t in bluechips if t not in ibov and t in tickers_info]
    if bluechips_extra:
        logger.info(f"\n🥈 PRIORIDADE 2: Blue Chips adicionais")
        logger.info(f"   {len(bluechips_extra)} ativos")
        for ticker in bluechips_extra[:10]:
            info = tickers_info[ticker]
            logger.info(f"   • {ticker:8} | {info['nomeCurto']}")
    
    # 3. Ativos com histórico longo (>10 anos)
    cutoff_date = 20140101  # 2014
    long_history = []
    for ticker, info in tickers_info.items():
        if info['dataMin'] < cutoff_date:
            long_history.append((ticker, info))
    
    logger.info(f"\n🥉 PRIORIDADE 3: Histórico longo (>10 anos)")
    logger.info(f"   {len(long_history)} ativos disponíveis")
    logger.info(f"   (Use filter_top_liquidity para selecionar)")
    
    # Resumo
    logger.info("=" * 80)
    logger.info("💡 RECOMENDAÇÃO FINAL:")
    logger.info("=" * 80)
    logger.info("1. Baixe IBOVESPA primeiro (50 ativos, alta qualidade)")
    logger.info("2. Adicione blue chips extras conforme necessário")
    logger.info("3. Para backtesting histórico: filtrar por data_min < 2014")
    logger.info("=" * 80)


def check_ibovespa_availability():
    """Verifica quais componentes Ibovespa estão disponíveis"""
    api = B3APIIntegration()
    tickers_info = api.get_available_tickers()
    
    if not tickers_info:
        logger.error("❌ Falha ao baixar lista de ativos")
        return
    
    ibov = api.get_ibov_components()
    
    logger.info("=" * 80)
    logger.info("DISPONIBILIDADE COMPONENTES IBOVESPA")
    logger.info("=" * 80)
    
    available = []
    missing = []
    
    for ticker in ibov:
        if ticker in tickers_info:
            info = tickers_info[ticker]
            available.append(ticker)
            logger.info(f"✓ {ticker:8} | {info['nomeCurto']:20} | {info['dataMin']} -> {info['dataMax']}")
        else:
            missing.append(ticker)
            logger.warning(f"✗ {ticker:8} | NÃO DISPONÍVEL")
    
    logger.info("=" * 80)
    logger.info(f"✅ Disponíveis: {len(available)}/{len(ibov)} ({100*len(available)/len(ibov):.1f}%)")
    logger.info(f"❌ Indisponíveis: {len(missing)}")
    
    if available:
        logger.info("\n💾 Para baixar estes ativos, use:")
        logger.info(f"   python import_cotahist.py --symbols {' '.join(available[:5])} ...")
    
    logger.info("=" * 80)


if __name__ == '__main__':
    import sys
    
    # Exemplo de uso:
    # python b3_api_integration.py analyze
    # python b3_api_integration.py recommend
    # python b3_api_integration.py check-ibov
    # python b3_api_integration.py export-csv
    
    if len(sys.argv) < 2:
        print("""
B3 API Integration - Ticker Discovery Tool
==========================================

Uso:
  python b3_api_integration.py analyze         - Analisa todos os ativos disponíveis
  python b3_api_integration.py recommend       - Recomenda ativos para download
  python b3_api_integration.py check-ibov      - Verifica disponibilidade Ibovespa
  python b3_api_integration.py export-csv      - Exporta lista completa para CSV

IMPORTANTE:
  Esta API fornece apenas a LISTA de ativos disponíveis.
  Para baixar dados históricos, use:
  
  1. scripts/cotahist_parser.py (dados oficiais B3)
  2. BRAPI API (dados em tempo real)
  
Exemplo workflow completo:
  1. python b3_api_integration.py check-ibov
     → Verifica quais componentes Ibovespa estão disponíveis
  
  2. python import_cotahist.py --year 2024 --symbols PETR4 VALE3 ITUB4
     → Baixa dados históricos via COTAHIST
  
  3. python main.py
     → Executa estratégias de trading
        """)
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == 'analyze':
        analyze_tickers()
    
    elif command == 'recommend':
        recommend_tickers_for_download()
    
    elif command == 'check-ibov':
        check_ibovespa_availability()
    
    elif command == 'export-csv':
        api = B3APIIntegration()
        api.export_to_csv('b3_tickers_list.csv')
    
    else:
        print(f"❌ Comando desconhecido: {command}")
        print("Use: analyze, recommend, check-ibov, ou export-csv")
        sys.exit(1)
