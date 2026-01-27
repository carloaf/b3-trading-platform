#!/usr/bin/env python3
"""
Backtest ULTRA-RÁPIDO: Wave3 v2.1 vs Wave3 v2.3+ML
===================================================

Versão otimizada:
- Apenas últimos 30 dias
- 1 ativo por vez
- Features geradas uma vez

Autor: B3 Trading Platform
Data: 21 Janeiro 2026
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import asyncio
import asyncpg

sys.path.append('/app/src/strategies')
sys.path.append('/app/src/ml')

from wave3_enhanced import Wave3Enhanced
from wave3_ml_hybrid import Wave3MLHybrid


async def ultra_quick_backtest():
    """Backtest ultra-rápido em 1 ativo"""
    
    print("="*100)
    print("BACKTEST ULTRA-RÁPIDO: Wave3 v2.1 vs v2.3+ML")
    print("="*100)
    
    # Criar estratégias
    print("\n🔧 Criando estratégias...")
    strategy_v21 = Wave3Enhanced(min_quality_score=65)
    strategy_v23 = Wave3MLHybrid(ml_threshold=0.60, min_quality_score=65)
    print("✅ Estratégias criadas")
    
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
    
    # Testar 1 ativo apenas
    symbol = 'PETR4'
    
    print(f"\n📊 Testando {symbol}...")
    print("-"*100)
    
    try:
        # Buscar dados
        async with pool.acquire() as conn:
            # Daily data (últimos 12 meses para EMAs)
            rows_daily = await conn.fetch("""
                SELECT time, open, high, low, close, volume
                FROM ohlcv_daily
                WHERE symbol = $1
                ORDER BY time
            """, symbol)
            
            # 60min data
            rows_60min = await conn.fetch("""
                SELECT time, open, high, low, close, volume
                FROM ohlcv_60min
                WHERE symbol = $1
                ORDER BY time
            """, symbol)
        
        if len(rows_daily) < 100 or len(rows_60min) < 100:
            print(f"⚠️ Dados insuficientes: {len(rows_daily)} daily, {len(rows_60min)} 60min")
            return
        
        print(f"✅ Dados carregados: {len(rows_daily)} daily, {len(rows_60min)} 60min")
        
        # Converter para DataFrame
        df_daily = pd.DataFrame(rows_daily, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
        df_60min = pd.DataFrame(rows_60min, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
        
        # Converter Decimal para float
        for df in [df_daily, df_60min]:
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        print(f"\n🧪 Testando v2.1 (Wave3 pura)...")
        result_v21 = await simple_backtest(strategy_v21, df_daily, df_60min, symbol, "v2.1")
        
        print(f"\n🤖 Testando v2.3+ML (Wave3 + ML Filter)...")
        result_v23 = await simple_backtest(strategy_v23, df_daily, df_60min, symbol, "v2.3+ML")
        
        # Comparar
        print("\n" + "="*100)
        print("🏆 COMPARAÇÃO FINAL")
        print("="*100)
        
        if result_v21 and result_v23:
            print(f"\n{symbol}:")
            print(f"  v2.1: {result_v21['trades']} trades | {result_v21['win_rate']:.1f}% win | {result_v21['avg_return']:+.2f}% retorno")
            print(f"  v2.3: {result_v23['trades']} trades | {result_v23['win_rate']:.1f}% win | {result_v23['avg_return']:+.2f}% retorno")
            
            if result_v23['trades'] < result_v21['trades']:
                filtered = result_v21['trades'] - result_v23['trades']
                print(f"\n  🔍 ML Filter: {filtered} trades rejeitados ({filtered/result_v21['trades']*100:.1f}%)")
            
            if result_v23['win_rate'] > result_v21['win_rate']:
                print(f"  ✅ ML melhorou win rate em {result_v23['win_rate']-result_v21['win_rate']:+.1f}%")
            else:
                print(f"  ⚠️ ML reduziu win rate em {result_v21['win_rate']-result_v23['win_rate']:.1f}%")
    
    except Exception as e:
        print(f"❌ Erro: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await pool.close()


async def simple_backtest(strategy, df_daily, df_60min, symbol, strategy_name):
    """
    Backtest simplificado - gera sinal UMA VEZ ao final
    """
    
    try:
        # Pegar últimos 30 dias apenas
        cutoff_date = df_daily.iloc[-1]['time'] - timedelta(days=30)
        
        df_daily_recent = df_daily[df_daily['time'] >= cutoff_date].copy()
        df_60min_recent = df_60min[df_60min['time'] >= cutoff_date].copy()
        
        print(f"   📅 Período: últimos 30 dias")
        print(f"   📊 Dados: {len(df_daily_recent)} daily, {len(df_60min_recent)} 60min")
        
        trades = []
        position = None
        
        # Simular dia-a-dia
        for i in range(len(df_daily_recent)):
            if i % 5 == 0:  # Progress a cada 5 dias
                print(f"   ⏳ Dia {i+1}/{len(df_daily_recent)}...", end='\r')
            
            current_date = df_daily_recent.iloc[i]['time']
            
            # Slice até data atual (incluindo histórico completo para EMAs)
            df_daily_slice = df_daily[df_daily['time'] <= current_date].copy()
            df_60min_slice = df_60min[df_60min['time'] <= current_date].copy()
            
            if len(df_60min_slice) < 50:
                continue
            
            # Sem posição: buscar sinal
            if position is None:
                try:
                    signal = strategy.generate_signal(df_daily_slice, df_60min_slice, symbol)
                except Exception as e:
                    continue
                
                if signal and hasattr(signal, 'quality_score'):
                    # Abrir posição
                    take_profit = signal.target_3 if hasattr(signal, 'target_3') else signal.entry_price * 1.18
                    
                    position = {
                        'entry_date': current_date,
                        'entry_price': float(df_daily_slice.iloc[-1]['close']),
                        'stop_loss': float(signal.stop_loss),
                        'take_profit': float(take_profit),
                        'score': signal.quality_score if hasattr(signal, 'quality_score') else 0,
                        'ml_confidence': signal.ml_confidence if hasattr(signal, 'ml_confidence') else 0.5
                    }
                    print(f"\n   🟢 ENTRADA: {current_date.strftime('%Y-%m-%d')} @ R$ {position['entry_price']:.2f}")
                    if hasattr(signal, 'ml_confidence'):
                        print(f"      ML Confidence: {signal.ml_confidence:.2%} | Score: {signal.quality_score}")
            
            # Com posição: verificar saída
            else:
                current_price = float(df_daily_slice.iloc[-1]['close'])
                
                # Stop ou Take Profit
                if current_price <= position['stop_loss'] or current_price >= position['take_profit']:
                    ret = ((current_price - position['entry_price']) / position['entry_price']) * 100
                    
                    result = 'WIN' if ret > 0 else 'LOSS'
                    emoji = '✅' if ret > 0 else '❌'
                    
                    print(f"   {emoji} SAÍDA: {current_date.strftime('%Y-%m-%d')} @ R$ {current_price:.2f} | {result} {ret:+.2f}%")
                    
                    trades.append({
                        'entry_date': position['entry_date'],
                        'exit_date': current_date,
                        'entry_price': position['entry_price'],
                        'exit_price': current_price,
                        'return_pct': ret,
                        'result': result
                    })
                    
                    position = None
        
        print()  # Nova linha após progress
        
        # Calcular métricas
        if len(trades) == 0:
            print(f"   ⚠️ Nenhum trade gerado")
            return None
        
        wins = [t for t in trades if t['result'] == 'WIN']
        win_rate = (len(wins) / len(trades)) * 100
        avg_return = sum(t['return_pct'] for t in trades) / len(trades)
        
        print(f"\n   📊 RESUMO:")
        print(f"      Trades: {len(trades)}")
        print(f"      Wins: {len(wins)} ({win_rate:.1f}%)")
        print(f"      Losses: {len(trades)-len(wins)} ({100-win_rate:.1f}%)")
        print(f"      Retorno Médio: {avg_return:+.2f}%")
        
        return {
            'symbol': symbol,
            'strategy': strategy_name,
            'trades': len(trades),
            'wins': len(wins),
            'win_rate': win_rate,
            'avg_return': avg_return
        }
        
    except Exception as e:
        print(f"\n   ❌ Erro: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    asyncio.run(ultra_quick_backtest())
