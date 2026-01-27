#!/usr/bin/env python3
"""
Backtest RÁPIDO: Wave3 v2.1 vs Wave3 v2.3+ML
=============================================

Testa 3 ativos apenas para validação rápida

Autor: B3 Trading Platform
Data: 21 Janeiro 2026
"""

import pandas as pd
import numpy as np
from datetime import datetime
import sys
import asyncio
import asyncpg

sys.path.append('/app/src/strategies')
sys.path.append('/app/src/ml')

from wave3_enhanced import Wave3Enhanced
from wave3_ml_hybrid import Wave3MLHybrid


async def quick_backtest():
    """Backtest rápido em 3 ativos"""
    
    print("="*100)
    print("BACKTEST RÁPIDO: Wave3 v2.1 vs v2.3+ML (3 ativos)")
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
    
    # 3 ativos apenas
    symbols = ['PETR4', 'VALE3', 'ITUB4']
    
    results_v21 = []
    results_v23 = []
    
    print(f"\n📊 Testando {len(symbols)} símbolos...")
    print("-"*100)
    
    for symbol in symbols:
        print(f"\n🔄 {symbol}...")
        
        try:
            # Buscar dados
            async with pool.acquire() as conn:
                # Daily data
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
                print(f"   ⚠️ Dados insuficientes: {len(rows_daily)} daily, {len(rows_60min)} 60min")
                continue
            
            print(f"   ✅ Dados: {len(rows_daily)} daily, {len(rows_60min)} 60min")
            
            # Converter para DataFrame
            df_daily = pd.DataFrame(rows_daily, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
            df_60min = pd.DataFrame(rows_60min, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
            
            # Converter Decimal para float
            for df in [df_daily, df_60min]:
                for col in ['open', 'high', 'low', 'close', 'volume']:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # Backtest ambas estratégias
            result_v21 = await backtest_strategy(strategy_v21, df_daily, df_60min, symbol, "v2.1")
            result_v23 = await backtest_strategy(strategy_v23, df_daily, df_60min, symbol, "v2.3+ML")
            
            if result_v21:
                results_v21.append(result_v21)
            if result_v23:
                results_v23.append(result_v23)
                
        except Exception as e:
            print(f"   ❌ Erro: {e}")
            continue
    
    # Fechar pool
    await pool.close()
    
    # Exibir resultados consolidados
    print("\n" + "="*100)
    print("📊 RESULTADOS CONSOLIDADOS")
    print("="*100)
    
    print_summary("Wave3 v2.1 (Baseline)", results_v21)
    print_summary("Wave3 v2.3+ML Hybrid", results_v23)
    
    # Comparação
    if results_v21 and results_v23:
        print("\n" + "="*100)
        print("🏆 COMPARAÇÃO DIRETA")
        print("="*100)
        
        wr_v21 = sum(r['win_rate'] for r in results_v21) / len(results_v21) if results_v21 else 0
        wr_v23 = sum(r['win_rate'] for r in results_v23) / len(results_v23) if results_v23 else 0
        
        ret_v21 = sum(r['avg_return'] for r in results_v21) / len(results_v21) if results_v21 else 0
        ret_v23 = sum(r['avg_return'] for r in results_v23) / len(results_v23) if results_v23 else 0
        
        print(f"\n📈 Win Rate:")
        print(f"   v2.1: {wr_v21:.1f}%")
        print(f"   v2.3: {wr_v23:.1f}% ({'🟢 +' if wr_v23 > wr_v21 else '🔴 '}{wr_v23-wr_v21:.1f}%)")
        
        print(f"\n💰 Retorno Médio:")
        print(f"   v2.1: {ret_v21:.2f}%")
        print(f"   v2.3: {ret_v23:.2f}% ({'🟢 +' if ret_v23 > ret_v21 else '🔴 '}{ret_v23-ret_v21:.2f}%)")
        
        trades_v21 = sum(r['trades'] for r in results_v21)
        trades_v23 = sum(r['trades'] for r in results_v23)
        
        print(f"\n📊 Total Trades:")
        print(f"   v2.1: {trades_v21}")
        print(f"   v2.3: {trades_v23} ({trades_v23-trades_v21:+d} trades)")
        
        if trades_v21 > 0:
            filter_rate = (1 - trades_v23/trades_v21) * 100 if trades_v23 < trades_v21 else 0
            print(f"   ML Filter Rate: {filter_rate:.1f}% ({trades_v21-trades_v23} rejeitados)")


async def backtest_strategy(strategy, df_daily, df_60min, symbol, strategy_name):
    """
    Executa backtest simplificado de uma estratégia
    """
    print(f"   🔄 {strategy_name}...")
    
    try:
        trades = []
        position = None
        
        # Simular dia-a-dia (últimos 200 dias)
        start_idx = max(0, len(df_daily) - 200)
        
        for i in range(start_idx, len(df_daily)):
            current_date = df_daily.iloc[i]['time']
            
            # Slice até data atual
            df_daily_slice = df_daily.iloc[:i+1].copy()
            
            # 60min até data atual
            df_60min_slice = df_60min[df_60min['time'] <= current_date].copy()
            
            if len(df_60min_slice) < 50:
                continue
            
            # Sem posição: buscar sinal de entrada
            if position is None:
                try:
                    signal = strategy.generate_signal(df_daily_slice, df_60min_slice, symbol)
                except Exception as e:
                    # Se erro na geração, skip
                    continue
                
                if signal and hasattr(signal, 'quality_score'):
                    # Abrir posição
                    # EnhancedWave3Signal tem target_3 (alvo final 3:1), não take_profit
                    take_profit = signal.target_3 if hasattr(signal, 'target_3') else signal.entry_price * 1.18
                    
                    position = {
                        'symbol': symbol,
                        'entry_date': current_date,
                        'entry_price': float(df_daily_slice.iloc[-1]['close']),
                        'stop_loss': float(signal.stop_loss),
                        'take_profit': float(take_profit),
                        'score': signal.quality_score if hasattr(signal, 'quality_score') else 0,
                        'ml_confidence': signal.ml_confidence if hasattr(signal, 'ml_confidence') else 0.5,
                        'hybrid_score': signal.hybrid_score if hasattr(signal, 'hybrid_score') else 0
                    }
            
            # Com posição: verificar saída
            else:
                current_price = float(df_daily_slice.iloc[-1]['close'])
                
                # Stop loss ou take profit
                if current_price <= position['stop_loss'] or current_price >= position['take_profit']:
                    exit_date = current_date
                    exit_price = current_price
                    
                    # Calcular retorno
                    ret = ((exit_price - position['entry_price']) / position['entry_price']) * 100
                    
                    trade = {
                        'symbol': symbol,
                        'entry_date': position['entry_date'],
                        'exit_date': exit_date,
                        'entry_price': position['entry_price'],
                        'exit_price': exit_price,
                        'return_pct': ret,
                        'result': 'WIN' if ret > 0 else 'LOSS',
                        'score': position['score'],
                        'ml_confidence': position['ml_confidence'],
                        'hybrid_score': position['hybrid_score']
                    }
                    
                    trades.append(trade)
                    position = None  # Fechar posição
        
        # Calcular métricas
        if len(trades) == 0:
            print(f"      Trades: 0 | ⚠️ Nenhum trade gerado")
            return None
        
        wins = [t for t in trades if t['result'] == 'WIN']
        win_rate = (len(wins) / len(trades)) * 100
        avg_return = sum(t['return_pct'] for t in trades) / len(trades)
        
        print(f"      Trades: {len(trades)} | Win Rate: {win_rate:.1f}% | Retorno: {avg_return:+.2f}%")
        
        # ML info se disponível
        if trades[0].get('ml_confidence', 0) > 0:
            avg_ml_conf = sum(t['ml_confidence'] for t in trades) / len(trades)
            avg_hybrid = sum(t['hybrid_score'] for t in trades) / len(trades)
            print(f"      ML Confidence: {avg_ml_conf:.2f} | Hybrid Score: {avg_hybrid:.1f}")
        
        return {
            'symbol': symbol,
            'strategy': strategy_name,
            'trades': len(trades),
            'wins': len(wins),
            'losses': len(trades) - len(wins),
            'win_rate': win_rate,
            'avg_return': avg_return,
            'trades_data': trades
        }
        
    except Exception as e:
        print(f"      ❌ Erro no backtest: {e}")
        import traceback
        traceback.print_exc()
        return None


def print_summary(strategy_name, results):
    """Exibe resumo consolidado de uma estratégia"""
    if not results:
        print(f"\n⚠️ {strategy_name}: Sem resultados")
        return
    
    print(f"\n{'='*50}")
    print(f"📊 {strategy_name}")
    print(f"{'='*50}")
    
    total_trades = sum(r['trades'] for r in results)
    total_wins = sum(r['wins'] for r in results)
    
    if total_trades > 0:
        overall_wr = (total_wins / total_trades) * 100
        overall_ret = sum(r['avg_return'] * r['trades'] for r in results) / total_trades
        
        print(f"Ativos testados: {len(results)}")
        print(f"Total Trades: {total_trades}")
        print(f"Wins: {total_wins} ({overall_wr:.1f}%)")
        print(f"Losses: {total_trades - total_wins} ({100-overall_wr:.1f}%)")
        print(f"Retorno Médio: {overall_ret:+.2f}%")
        
        # Melhor e pior
        best = max(results, key=lambda x: x['avg_return'])
        worst = min(results, key=lambda x: x['avg_return'])
        
        print(f"\n🏆 Melhor: {best['symbol']} ({best['avg_return']:+.2f}%, {best['win_rate']:.0f}% win)")
        print(f"⚠️ Pior: {worst['symbol']} ({worst['avg_return']:+.2f}%, {worst['win_rate']:.0f}% win)")


if __name__ == "__main__":
    asyncio.run(quick_backtest())
