#!/usr/bin/env python3
"""
Análise Completa de Cobertura de Dados
======================================

Analisa todos os dados no TimescaleDB e gera relatório de cobertura
por símbolo e timeframe, identificando gaps e períodos disponíveis.
"""

import asyncio
import asyncpg
from datetime import datetime, timedelta
from collections import defaultdict
import sys

# Configuração do banco
DB_CONFIG = {
    'host': 'b3-timescaledb',
    'port': 5432,
    'database': 'b3trading_market',
    'user': 'b3trading_ts',
    'password': 'b3trading_ts_pass'
}

TIMEFRAMES = {
    'ohlcv_15min': '15min',
    'ohlcv_60min': '60min',
    'ohlcv_daily': 'daily'
}


async def get_coverage_data():
    """Obtém dados de cobertura completos"""
    conn = await asyncpg.connect(**DB_CONFIG)
    
    coverage = {}
    
    for table, tf in TIMEFRAMES.items():
        query = f"""
        SELECT 
            symbol,
            COUNT(*) as total_records,
            MIN(time)::date as first_date,
            MAX(time)::date as last_date,
            COUNT(DISTINCT time::date) as total_days,
            (MAX(time)::date - MIN(time)::date) + 1 as days_range,
            ROUND(
                (COUNT(DISTINCT time::date)::numeric / 
                ((MAX(time)::date - MIN(time)::date) + 1)) * 100, 
                2
            ) as coverage_pct
        FROM {table}
        GROUP BY symbol
        ORDER BY symbol
        """
        
        rows = await conn.fetch(query)
        coverage[tf] = {row['symbol']: dict(row) for row in rows}
    
    await conn.close()
    return coverage


async def identify_gaps(symbol, table):
    """Identifica gaps de dados para um símbolo"""
    conn = await asyncpg.connect(**DB_CONFIG)
    
    query = f"""
    WITH RECURSIVE date_range AS (
        SELECT 
            MIN(time::date) as date,
            MAX(time::date) as max_date
        FROM {table}
        WHERE symbol = $1
        
        UNION ALL
        
        SELECT 
            date + INTERVAL '1 day',
            max_date
        FROM date_range
        WHERE date < max_date
    ),
    actual_dates AS (
        SELECT DISTINCT time::date as date
        FROM {table}
        WHERE symbol = $1
    )
    SELECT 
        dr.date::date as missing_date
    FROM date_range dr
    LEFT JOIN actual_dates ad ON dr.date = ad.date
    WHERE ad.date IS NULL
    AND EXTRACT(DOW FROM dr.date) BETWEEN 1 AND 5  -- Seg-Sex apenas
    ORDER BY dr.date
    LIMIT 50
    """
    
    gaps = await conn.fetch(query, symbol)
    await conn.close()
    
    return [row['missing_date'] for row in gaps]


async def print_summary():
    """Imprime resumo executivo"""
    print("\n" + "="*80)
    print("📊 ANÁLISE DE COBERTURA DE DADOS - TimescaleDB")
    print("="*80)
    print(f"Data/Hora: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print("="*80 + "\n")
    
    coverage = await get_coverage_data()
    
    # Total de registros
    total_records = sum(
        sum(data['total_records'] for data in coverage[tf].values())
        for tf in coverage
    )
    print(f"📈 **TOTAL DE REGISTROS:** {total_records:,}")
    
    # Por timeframe
    print("\n📅 **POR TIMEFRAME:**")
    for tf in ['15min', '60min', 'daily']:
        if tf in coverage:
            total = sum(data['total_records'] for data in coverage[tf].values())
            symbols = len(coverage[tf])
            print(f"  {tf:10s} | {symbols:3d} símbolos | {total:9,} registros")
    
    # Símbolos únicos
    all_symbols = set()
    for tf in coverage:
        all_symbols.update(coverage[tf].keys())
    
    print(f"\n🎯 **SÍMBOLOS ÚNICOS:** {len(all_symbols)}")
    
    # Análise por símbolo
    print("\n" + "="*80)
    print("📋 COBERTURA DETALHADA POR SÍMBOLO")
    print("="*80)
    
    # Header
    print(f"\n{'Símbolo':<8} | {'15min':<12} | {'60min':<12} | {'Daily':<12} | {'Status':<20}")
    print("-" * 80)
    
    for symbol in sorted(all_symbols):
        coverage_15 = coverage.get('15min', {}).get(symbol)
        coverage_60 = coverage.get('60min', {}).get(symbol)
        coverage_d = coverage.get('daily', {}).get(symbol)
        
        # Formatar datas
        def format_dates(cov):
            if cov:
                first = cov['first_date'].strftime('%d/%m/%y')
                last = cov['last_date'].strftime('%d/%m/%y')
                return f"{first}-{last}"
            return "-"
        
        dates_15 = format_dates(coverage_15)
        dates_60 = format_dates(coverage_60)
        dates_d = format_dates(coverage_d)
        
        # Status
        has_15 = "✓" if coverage_15 else " "
        has_60 = "✓" if coverage_60 else " "
        has_d = "✓" if coverage_d else " "
        
        if coverage_15 and coverage_60:
            status = "✅ COMPLETO"
        elif coverage_60:
            status = "⚠️ SEM 15min"
        elif coverage_15:
            status = "⚠️ SEM 60min"
        else:
            status = "❌ APENAS DAILY"
        
        print(f"{symbol:<8} | {has_15} {dates_15:<10} | {has_60} {dates_60:<10} | {has_d} {dates_d:<10} | {status}")
    
    # Análise de períodos
    print("\n" + "="*80)
    print("📆 PERÍODOS DISPONÍVEIS")
    print("="*80)
    
    # Encontrar menor e maior data
    all_dates = []
    for tf in coverage:
        for symbol_data in coverage[tf].values():
            all_dates.append(symbol_data['first_date'])
            all_dates.append(symbol_data['last_date'])
    
    if all_dates:
        min_date = min(all_dates)
        max_date = max(all_dates)
        total_days = (max_date - min_date).days + 1
        
        print(f"\n  Primeira data: {min_date.strftime('%d/%m/%Y')}")
        print(f"  Última data:   {max_date.strftime('%d/%m/%Y')}")
        print(f"  Período total: {total_days} dias ({total_days / 365:.1f} anos)")
        
        # Gap até hoje
        today = datetime.now().date()
        gap_days = (today - max_date).days
        
        if gap_days > 0:
            print(f"\n  ⚠️  GAP ATÉ HOJE: {gap_days} dias")
        else:
            print(f"\n  ✅ DADOS ATUALIZADOS (até hoje)")
    
    # Símbolos prioritários para paper trading
    print("\n" + "="*80)
    print("🎯 SÍMBOLOS PRIORITÁRIOS PAPER TRADING")
    print("="*80)
    
    priority_symbols = ['PETR4', 'VALE3', 'ITUB4', 'BBDC4', 'ABEV3']
    
    print(f"\n{'Símbolo':<8} | {'Total 60min':<12} | {'Período':<25} | {'Gap':<10} | {'Status':<15}")
    print("-" * 85)
    
    for symbol in priority_symbols:
        cov = coverage.get('60min', {}).get(symbol)
        if cov:
            first = cov['first_date'].strftime('%d/%m/%Y')
            last = cov['last_date'].strftime('%d/%m/%Y')
            total = cov['total_records']
            gap = (datetime.now().date() - cov['last_date']).days
            
            if gap == 0:
                status = "✅ ATUAL"
            elif gap <= 7:
                status = f"⚠️ {gap}d atrás"
            else:
                status = f"❌ {gap}d atrás"
            
            print(f"{symbol:<8} | {total:>10,}  | {first} - {last} | {gap:>3} dias | {status}")
        else:
            print(f"{symbol:<8} | {'SEM DADOS':>10}  | {'-':<25} | {'-':>8} | ❌ AUSENTE")
    
    print("\n" + "="*80 + "\n")


async def main():
    await print_summary()


if __name__ == '__main__':
    asyncio.run(main())
