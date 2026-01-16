SOLUÇÃO PARA DADOS DA B3 (Alternativas ao BRAPI gratuito)
1. Fontes alternativas gratuitas/mais acessíveis:
python
# Exemplo de coleta multi-fonte para B3
import yfinance as yf
import pandas as pd
import requests

class B3DataCollector:
    def __init__(self):
        self.sources = {
            'yfinance': self._get_yfinance_data,
            'investing': self._get_investing_data,
            'awtrix': self._get_awtrix_data
        }
    
    def get_historical_data(self, ticker, start_date, end_date, interval='1d'):
        """
        ticker: Código do ativo (ex: 'PETR4', 'VALE3')
        Adicionar '.SA' para yfinance
        """
        # Yahoo Finance (dados diários - anos de histórico)
        data = yf.download(f'{ticker}.SA', start=start_date, end=end_date)
        return data
    
    # Outras fontes alternativas:
    # 1. Investing.com (via web scraping - cuidado com termos de uso)
    # 2. API Alpha Vantage (chave gratuita, limite de requests)
    # 3. API AWTRiX (awtrix.com.br) - tem planos mais acessíveis
    # 4. Dados do BCB e CVM
2. Estratégia Híbrida de Coleta:
Dados diários longos: Yahoo Finance (10+ anos de histórico)

Dados intradiários:
Alpha Vantage (grátis: 5min, 15min, 30min, 60min)
Polygon.io (plano starter: $7/mês)
Finnhub (plano free: 60 requests/minuto)
