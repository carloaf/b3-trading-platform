#!/usr/bin/env python3
"""
Script de Validação: Quantos sinais Wave3 em 6 meses?
=======================================================

Valida se o problema é:
- Falta de dados históricos
- Estratégia muito restritiva
- Bugs na geração de sinais

Autor: B3 Trading Platform
Data: 23 Janeiro 2026
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import asyncio
import asyncpg

sys.path.append('/app/src/strategies')
from wave3_enhanced import Wave3Enhanced


async def validate_data():
    """Valida dados e conta sinais potenciais"""
    
    print("="*100)
    print("VALIDAÇÃO: Wave3 Data & Signal Count (6 meses)")
    print("="*100)
    
    # Conectar DB
    print("\n🔗 Conectando ao TimescaleDB...")
    pool = await asyncpg.create_pool(
        host='b3-timescaledb',
        port=5432,
        user='b3trading_ts',
        password='b3trading_ts_pass',
        database='b3trading_market',
        min_size=1,
        max_size=3
    )
    print("✅ Conectado")
    
    # Símbolos para testar
    symbols = ['PETR4', 'VALE3', 'ITUB4', 'BBDC4', 'MGLU3']
    
    print(f"\n📊 Testando {len(symbols)} símbolos...")
    print("-"*100)
    
    total_signals = 0
    
    for symbol in symbols:
        print(f"\n🔄 {symbol}...")
        
        try:
            # Buscar dados dos últimos 12 meses (para ter contexto)
            async with pool.acquire() as conn:
                # Daily data
                rows_daily = await conn.fetch("""
                    SELECT time, open, high, low, close, volume
                    FROM ohlcv_daily
                    WHERE symbol = $1
                    AND time >= NOW() - INTERVAL '12 months'
                    ORDER BY time
                """, symbol)
                
                # 60min data
                rows_60min = await conn.fetch("""
                    SELECT time, open, high, low, close, volume
                    FROM ohlcv_60min
                    WHERE symbol = $1
                    AND time >= NOW() - INTERVAL '12 months'
                    ORDER BY time
                """, symbol)
            
            print(f"   📦 Dados: {len(rows_daily)} daily, {len(rows_60min)} 60min")
            
            if len(rows_daily) < 100:
                print(f"   ⚠️ Dados insuficientes para análise")
                continue
            
            # Converter para DataFrame
            df_daily = pd.DataFrame(rows_daily, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
            df_60min = pd.DataFrame(rows_60min, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
            
            # Converter Decimal para float
            for df in [df_daily, df_60min]:
                for col in ['open', 'high', 'low', 'close', 'volume']:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # Range de datas
            first_date = df_daily['time'].min()
            last_date = df_daily['time'].max()
            days_span = (last_date - first_date).days
            
            print(f"   📅 Range: {first_date.date()} → {last_date.date()} ({days_span} dias)")
            
            # Criar estratégia
            strategy = Wave3Enhanced(min_quality_score=65)
            
            # Contar sinais nos últimos 6 meses
            six_months_ago = last_date - timedelta(days=180)
            df_daily_6m = df_daily[df_daily['time'] >= six_months_ago].copy()
            
            signals_found = 0
            signal_dates = []
            signal_scores = []
            
            # Simular dia-a-dia
            for i in range(len(df_daily_6m)):
                current_date = df_daily_6m.iloc[i]['time']
                
                # Dados até data atual
                df_daily_slice = df_daily[df_daily['time'] <= current_date].copy()
                df_60min_slice = df_60min[df_60min['time'] <= current_date].copy()
                
                if len(df_daily_slice) < 100 or len(df_60min_slice) < 50:
                    continue
                
                # Tentar gerar sinal
                try:
                    signal = strategy.generate_signal(df_daily_slice, df_60min_slice, symbol)
                    
                    if signal and hasattr(signal, 'quality_score'):
                        signals_found += 1
                        signal_dates.append(current_date)
                        signal_scores.append(signal.quality_score)
                        
                        print(f"   ✅ Sinal #{signals_found} em {current_date.date()} | Score: {signal.quality_score}")
                        
                except Exception as e:
                    # Ignorar erros
                    pass
            
            print(f"\n   📊 Total Sinais (6 meses): {signals_found}")
            
            if signals_found > 0:
                avg_score = sum(signal_scores) / len(signal_scores)
                print(f"   📈 Score Médio: {avg_score:.1f}")
                print(f"   📅 Datas: {[d.date() for d in signal_dates[:5]]}{'...' if len(signal_dates) > 5 else ''}")
            
            total_signals += signals_found
            
        except Exception as e:
            print(f"   ❌ Erro: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    # Fechar pool
    await pool.close()
    
    # Resumo
    print("\n" + "="*100)
    print("📊 RESUMO DA VALIDAÇÃO")
    print("="*100)
    print(f"\nTotal de sinais gerados (6 meses): {total_signals}")
    print(f"Média por ativo: {total_signals/len(symbols):.1f} sinais")
    print(f"Frequência esperada: ~1-2 sinais/mês por ativo (André Moraes)")
    
    if total_signals < 10:
        print("\n⚠️ PROBLEMA IDENTIFICADO:")
        print("   - Sinais insuficientes para análise estatística")
        print("   - Possíveis causas:")
        print("     1. Quality score 65 muito restritivo")
        print("     2. Falta de dados históricos")
        print("     3. Mercado em range (sem tendência clara)")
        print("\n💡 RECOMENDAÇÕES:")
        print("   1. Reduzir quality_score para 55-60")
        print("   2. Testar com mais ativos (10-15)")
        print("   3. Estender período para 12 meses")
    elif total_signals < 30:
        print("\n⚠️ Amostra pequena, mas viável")
        print("   - Continuar com backtest 6 meses")
        print("   - Considerar adicionar mais ativos")
    else:
        print("\n✅ Amostra adequada para análise!")
        print("   - Prosseguir com backtest completo")


if __name__ == "__main__":
    asyncio.run(validate_data())
