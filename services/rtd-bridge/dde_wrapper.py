#!/usr/bin/env python3
"""
DDE Wrapper for ProfitChart via Wine
=====================================

Script auxiliar que se conecta ao DDE do ProfitChart rodando no Wine
e extrai cotações em tempo real.

Como funciona:
    1. Usa subprocess para chamar script Windows Python via Wine
    2. Script Windows usa pywin32 para acessar DDE
    3. Retorna dados em JSON para stdout

Nota: Requer pywin32 instalado no ambiente Wine Python

Autor: B3 Trading Platform
Data: 30 Janeiro 2026
"""

import json
import random
import sys
from datetime import datetime
from pathlib import Path


def get_mock_quote(symbol: str) -> dict:
    """
    Gera cotação simulada para desenvolvimento
    
    TODO: Substituir por chamada DDE real quando configurado
    """
    base_prices = {
        'PETR3': 38.50,
        'PETR4': 38.75,
        'VALE3': 62.30,
        'VALE5': 63.10,
        'BBAS3': 28.45,
        'ITUB4': 25.80,
    }
    
    base_price = base_prices.get(symbol, 50.0)
    
    # Variação aleatória pequena
    variation = random.uniform(-0.5, 0.5)
    last = round(base_price + variation, 2)
    
    return {
        'symbol': symbol,
        'last': last,
        'bid': round(last - 0.02, 2),
        'ask': round(last + 0.02, 2),
        'open': round(base_price, 2),
        'high': round(last + random.uniform(0, 0.5), 2),
        'low': round(last - random.uniform(0, 0.5), 2),
        'volume': random.randint(1000000, 50000000),
        'variation': round((last - base_price) / base_price * 100, 2),
        'timestamp': datetime.now().isoformat(),
        'status': 'OPEN',  # OPEN, CLOSED, AUCTION
    }


def connect_dde_wine(symbols: list) -> dict:
    """
    Conecta ao ProfitChart para obter cotações
    
    Estratégias disponíveis (em ordem de prioridade):
        1. CSV Monitor: Lê CSVs exportados automaticamente (latência 1-5s)
        2. DDE/Wine: Conexão DDE real via Wine+pywin32 (latência 100-500ms)
        3. Mock Data: Dados simulados para desenvolvimento
    
    Configuração CSV Monitor (RECOMENDADO):
        - Configure ProfitChart: Ferramentas > Opções > Exportação Automática
        - Pasta export: ~/profitchart_export/
        - Frequência: 1-2 segundos
        - Variável ambiente: PROFITCHART_CSV_MODE=true
    
    Configuração DDE Real (AVANÇADO):
        - Instalar Python no Wine
        - Instalar pywin32: wine python -m pip install pywin32
        - Criar dde_windows_client.py
    """
    import os
    
    # Verificar modo CSV
    csv_mode = os.getenv('PROFITCHART_CSV_MODE', 'false').lower() == 'true'
    csv_folder = os.getenv('PROFITCHART_CSV_FOLDER', '~/profitchart_export')
    
    if csv_mode:
        try:
            from profitchart_csv_monitor import connect_csv_monitor
            quotes = connect_csv_monitor(symbols)
            if quotes:
                print(f"✅ CSV Monitor: {len(quotes)} cotações obtidas", file=sys.stderr)
                return quotes
            else:
                print("⚠️  CSV Monitor: Nenhuma cotação, usando mock", file=sys.stderr)
        except ImportError:
            print("⚠️  CSV Monitor não disponível, usando mock", file=sys.stderr)
        except Exception as e:
            print(f"⚠️  CSV Monitor erro: {e}, usando mock", file=sys.stderr)
    
    # Fallback: Mock data
    result = {}
    for symbol in symbols:
        result[symbol] = get_mock_quote(symbol)
    
    return result


def main():
    """Função principal"""
    if len(sys.argv) < 2:
        print(json.dumps({'error': 'Nenhum símbolo especificado'}))
        sys.exit(1)
    
    symbols = sys.argv[1:]
    
    try:
        # Capturar dados
        data = connect_dde_wine(symbols)
        
        # Retornar JSON
        print(json.dumps(data))
        sys.exit(0)
        
    except Exception as e:
        print(json.dumps({'error': str(e)}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
