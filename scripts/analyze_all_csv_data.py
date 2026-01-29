#!/usr/bin/env python3
"""
Análise Completa de Dados CSV ProfitChart
==========================================

Analisa TODOS os arquivos CSV disponíveis nas pastas:
- dados23e24 (2023-2024-2025)
- dados26 (janeiro 2026)

Para cada símbolo e timeframe, extrai:
- Quantidade de candles
- Período (primeira e última data)
- Tamanho do arquivo
"""

import os
import csv
from datetime import datetime
from collections import defaultdict
import sys

# Caminhos das pastas
PASTA_23E24 = "/home/dellno/Área de trabalho/dadoshistoricos.csv/dados23e24"
PASTA_26 = "/home/dellno/Área de trabalho/dadoshistoricos.csv/dados26"

def parse_profitchart_date(date_str, time_str=""):
    """Parse data no formato ProfitChart (DD/MM/YYYY)."""
    try:
        if time_str:
            dt_str = f"{date_str} {time_str}"
            return datetime.strptime(dt_str, "%d/%m/%Y %H:%M:%S")
        else:
            return datetime.strptime(date_str, "%d/%m/%Y")
    except:
        return None

def analyze_csv_file(filepath):
    """Analisa um arquivo CSV e retorna estatísticas."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        if len(lines) == 0:
            return None
        
        # Primeira linha
        first_line = lines[0].strip().split(';')
        first_date = first_line[1] if len(first_line) > 1 else None
        first_time = first_line[2] if len(first_line) > 2 else ""
        
        # Última linha
        last_line = lines[-1].strip().split(';')
        last_date = last_line[1] if len(last_line) > 1 else None
        last_time = last_line[2] if len(last_line) > 2 else ""
        
        # Parse dates
        first_dt = parse_profitchart_date(first_date, first_time)
        last_dt = parse_profitchart_date(last_date, last_time)
        
        # Tamanho do arquivo
        file_size = os.path.getsize(filepath)
        
        return {
            'candles': len(lines),
            'first_date': first_dt,
            'last_date': last_dt,
            'file_size': file_size,
            'first_date_str': first_date,
            'last_date_str': last_date
        }
    except Exception as e:
        print(f"Erro ao analisar {filepath}: {e}", file=sys.stderr)
        return None

def scan_folder(folder_path, folder_name):
    """Escaneia uma pasta e retorna dicionário com análises."""
    results = defaultdict(lambda: defaultdict(dict))
    
    if not os.path.exists(folder_path):
        print(f"⚠️  Pasta não encontrada: {folder_path}")
        return results
    
    files = [f for f in os.listdir(folder_path) if f.endswith('.csv') and '_B_0_' in f]
    
    print(f"\n🔍 Analisando pasta {folder_name}...")
    print(f"   Encontrados: {len(files)} arquivos CSV")
    
    for filename in sorted(files):
        filepath = os.path.join(folder_path, filename)
        
        # Parse filename: PETR4_B_0_60min.csv
        parts = filename.replace('.csv', '').split('_B_0_')
        if len(parts) != 2:
            continue
        
        symbol = parts[0]
        timeframe = parts[1]
        
        stats = analyze_csv_file(filepath)
        if stats:
            results[symbol][timeframe] = stats
    
    return results

def format_size(size_bytes):
    """Formata tamanho de arquivo."""
    if size_bytes < 1024:
        return f"{size_bytes}B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes/1024:.1f}KB"
    else:
        return f"{size_bytes/(1024*1024):.1f}MB"

def print_summary(data_23e24, data_26):
    """Imprime resumo consolidado."""
    
    # Todos os símbolos únicos
    all_symbols = sorted(set(list(data_23e24.keys()) + list(data_26.keys())))
    
    print("\n" + "="*100)
    print("📊 RESUMO COMPLETO DE DADOS CSV - B3 TRADING PLATFORM")
    print("="*100)
    
    print(f"\n📁 PASTA dados23e24: {len(data_23e24)} símbolos")
    print(f"📁 PASTA dados26: {len(data_26)} símbolos")
    print(f"📈 TOTAL ÚNICO: {len(all_symbols)} símbolos\n")
    
    # Tabela detalhada
    print("="*100)
    print(f"{'SÍMBOLO':<10} | {'PASTA':<8} | {'15min':<12} | {'60min':<12} | {'Daily':<12}")
    print("-"*100)
    
    for symbol in all_symbols:
        # dados23e24
        if symbol in data_23e24:
            tf_15 = data_23e24[symbol].get('15min', {})
            tf_60 = data_23e24[symbol].get('60min', {})
            tf_daily = data_23e24[symbol].get('Diário', {})
            
            print(f"{symbol:<10} | 23e24    | ", end="")
            print(f"{tf_15.get('candles', 0):>5} candles | ", end="")
            print(f"{tf_60.get('candles', 0):>5} candles | ", end="")
            print(f"{tf_daily.get('candles', 0):>5} candles")
        
        # dados26
        if symbol in data_26:
            tf_15 = data_26[symbol].get('15min', {})
            tf_60 = data_26[symbol].get('60min', {})
            tf_daily = data_26[symbol].get('Diário', {})
            
            print(f"{symbol:<10} | 26       | ", end="")
            print(f"{tf_15.get('candles', 0):>5} candles | ", end="")
            print(f"{tf_60.get('candles', 0):>5} candles | ", end="")
            print(f"{tf_daily.get('candles', 0):>5} candles")
        
        # Linha separadora entre símbolos
        if symbol in data_23e24 and symbol in data_26:
            print("-"*100)
    
    print("="*100)

def print_detailed_report(data_23e24, data_26, priority_symbols):
    """Imprime relatório detalhado dos ativos prioritários."""
    
    print("\n" + "="*100)
    print("🎯 ATIVOS PRIORITÁRIOS - ANÁLISE DETALHADA")
    print("="*100)
    
    for symbol in priority_symbols:
        print(f"\n{'='*100}")
        print(f"📊 {symbol}")
        print(f"{'='*100}")
        
        # dados23e24
        if symbol in data_23e24:
            print(f"\n📁 PASTA: dados23e24 (2023-2024-2025)")
            print("-"*100)
            
            for tf in ['15min', '60min', 'Diário']:
                if tf in data_23e24[symbol]:
                    stats = data_23e24[symbol][tf]
                    print(f"  {tf:<10}: {stats['candles']:>6} candles | ", end="")
                    print(f"{stats['last_date_str']} → {stats['first_date_str']} | ", end="")
                    print(f"{format_size(stats['file_size'])}")
                else:
                    print(f"  {tf:<10}: ❌ NÃO DISPONÍVEL")
        
        # dados26
        if symbol in data_26:
            print(f"\n📁 PASTA: dados26 (janeiro 2026)")
            print("-"*100)
            
            for tf in ['15min', '60min', 'Diário']:
                if tf in data_26[symbol]:
                    stats = data_26[symbol][tf]
                    print(f"  {tf:<10}: {stats['candles']:>6} candles | ", end="")
                    print(f"{stats['last_date_str']} → {stats['first_date_str']} | ", end="")
                    print(f"{format_size(stats['file_size'])}")
                else:
                    print(f"  {tf:<10}: ❌ NÃO DISPONÍVEL")
        
        # Total combinado
        print(f"\n📊 TOTAL COMBINADO (23e24 + 26):")
        print("-"*100)
        
        for tf in ['15min', '60min', 'Diário']:
            total_23e24 = data_23e24.get(symbol, {}).get(tf, {}).get('candles', 0)
            total_26 = data_26.get(symbol, {}).get(tf, {}).get('candles', 0)
            total = total_23e24 + total_26
            
            if total > 0:
                print(f"  {tf:<10}: {total:>6} candles total", end="")
                if total_23e24 > 0 and total_26 > 0:
                    print(f" ({total_23e24} + {total_26})")
                else:
                    print()
            else:
                print(f"  {tf:<10}: ❌ NÃO DISPONÍVEL")

def print_statistics(data_23e24, data_26):
    """Imprime estatísticas gerais."""
    
    print("\n" + "="*100)
    print("📈 ESTATÍSTICAS GERAIS")
    print("="*100)
    
    # Contar timeframes disponíveis
    tf_count_23e24 = defaultdict(int)
    tf_count_26 = defaultdict(int)
    
    for symbol, timeframes in data_23e24.items():
        for tf in timeframes.keys():
            tf_count_23e24[tf] += 1
    
    for symbol, timeframes in data_26.items():
        for tf in timeframes.keys():
            tf_count_26[tf] += 1
    
    print(f"\n📁 dados23e24:")
    for tf, count in sorted(tf_count_23e24.items()):
        print(f"   {tf:<10}: {count:>3} símbolos")
    
    print(f"\n📁 dados26:")
    for tf, count in sorted(tf_count_26.items()):
        print(f"   {tf:<10}: {count:>3} símbolos")
    
    # Símbolos em ambas as pastas
    symbols_both = set(data_23e24.keys()) & set(data_26.keys())
    symbols_only_23e24 = set(data_23e24.keys()) - set(data_26.keys())
    symbols_only_26 = set(data_26.keys()) - set(data_23e24.keys())
    
    print(f"\n📊 DISTRIBUIÇÃO:")
    print(f"   Em ambas as pastas:     {len(symbols_both):>3} símbolos")
    print(f"   Apenas em dados23e24:   {len(symbols_only_23e24):>3} símbolos")
    print(f"   Apenas em dados26:      {len(symbols_only_26):>3} símbolos")
    
    if symbols_only_23e24:
        print(f"\n   Símbolos APENAS em dados23e24:")
        for s in sorted(symbols_only_23e24):
            print(f"      • {s}")
    
    if symbols_only_26:
        print(f"\n   Símbolos APENAS em dados26:")
        for s in sorted(symbols_only_26):
            print(f"      • {s}")

def main():
    """Função principal."""
    
    print("🚀 B3 Trading Platform - Análise Completa de Dados CSV")
    print("="*100)
    
    # Escanear pastas
    data_23e24 = scan_folder(PASTA_23E24, "dados23e24")
    data_26 = scan_folder(PASTA_26, "dados26")
    
    # Símbolos prioritários
    priority_symbols = ['PETR4', 'VALE3', 'ITUB4', 'BBDC4', 'ABEV3']
    
    # Imprimir relatórios
    print_summary(data_23e24, data_26)
    print_detailed_report(data_23e24, data_26, priority_symbols)
    print_statistics(data_23e24, data_26)
    
    print("\n" + "="*100)
    print("✅ ANÁLISE COMPLETA")
    print("="*100)
    print("\nPróximo passo: Importar dados para TimescaleDB")
    print("Comando sugerido:")
    print("  docker exec b3-data-collector python3 /app/src/import_profitchart_bulk.py")
    print()

if __name__ == "__main__":
    main()
