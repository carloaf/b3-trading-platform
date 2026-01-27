#!/usr/bin/env python3
"""
Teste: Wave3 Negative Filter vs Wave3 Pure
===========================================

Compara:
- v2.1: Wave3 pura
- v2.4: Wave3 + ML Negative Filter (rejeita se confidence < 30%)

Autor: B3 Trading Platform
Data: 26 Janeiro 2026
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import asyncio
import asyncpg

sys.path.append('/app/src/strategies')
from wave3_enhanced import Wave3Enhanced
from wave3_ml_negative_filter import Wave3MLNegativeFilter


async def test_negative_filter():
    """Testa filtro negativo em 5 ativos"""
    
    print("="*80)
    print("TESTE: Wave3 v2.1 vs v2.4 Negative Filter")
    print("="*80)
    
    # Criar estratégias
    print("\n🔧 Criando estratégias...")
    strategy_v21 = Wave3Enhanced(min_quality_score=55)
    strategy_v24 = Wave3MLNegativeFilter(
        ml_reject_threshold=0.30,  # Rejeita SE < 30%
        min_quality_score=55
    )
    print("✅ v2.1: Wave3 pura (score≥55)")
    print("✅ v2.4: Wave3 + ML Negative Filter (rejeita < 30% confidence)")
    
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
    
    # 5 ativos
    symbols = ['PETR4', 'VALE3', 'ITUB4', 'BBDC4', 'ABEV3']
    
    results_v21 = []
    results_v24 = []
    
    print(f"\n📊 Testando {len(symbols)} símbolos (6 meses)...")
    print("-"*80)
    
    for idx, symbol in enumerate(symbols, 1):
        print(f"\n[{idx}/{len(symbols)}] 🔄 {symbol}...")
        
        try:
            # Buscar dados
            async with pool.acquire() as conn:
                rows_daily = await conn.fetch("""
                    SELECT time, open, high, low, close, volume
                    FROM ohlcv_daily
                    WHERE symbol = $1
                    ORDER BY time DESC
                    LIMIT 300
                """, symbol)
                
                rows_60min = await conn.fetch("""
                    SELECT time, open, high, low, close, volume
                    FROM ohlcv_60min
                    WHERE symbol = $1
                    ORDER BY time
                """, symbol)
            
            if len(rows_daily) < 100 or len(rows_60min) < 100:
                print(f"   ⚠️ Dados insuficientes")
                continue
            
            print(f"   ✅ Dados: {len(rows_daily)} daily, {len(rows_60min)} 60min")
            
            # Converter para DataFrame
            df_daily = pd.DataFrame(rows_daily, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
            df_60min = pd.DataFrame(rows_60min, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
            
            # Reverter ordem daily
            df_daily = df_daily.iloc[::-1].reset_index(drop=True)
            
            # Converter Decimal para float
            for df in [df_daily, df_60min]:
                for col in ['open', 'high', 'low', 'close', 'volume']:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # Backtest ambas estratégias
            result_v21 = await backtest_strategy(strategy_v21, df_daily, df_60min, symbol, "v2.1")
            result_v24 = await backtest_strategy(strategy_v24, df_daily, df_60min, symbol, "v2.4-NegFilter")
            
            if result_v21:
                results_v21.append(result_v21)
            if result_v24:
                results_v24.append(result_v24)
                
        except Exception as e:
            print(f"   ❌ Erro: {e}")
            continue
    
    await pool.close()
    
    # Resultados
    print("\n" + "="*80)
    print("📊 RESULTADOS CONSOLIDADOS")
    print("="*80)
    
    print_summary("v2.1: Wave3 Pura", results_v21)
    print_summary("v2.4: Wave3 + ML Negative Filter", results_v24)
    
    # Comparação
    if results_v21 and results_v24:
        print("\n" + "="*80)
        print("🔬 ANÁLISE DO FILTRO NEGATIVO")
        print("="*80)
        
        trades_v21 = sum(r['trades'] for r in results_v21)
        trades_v24 = sum(r['trades'] for r in results_v24)
        
        wins_v21 = sum(r['wins'] for r in results_v21)
        wins_v24 = sum(r['wins'] for r in results_v24)
        
        wr_v21 = (wins_v21 / trades_v21 * 100) if trades_v21 > 0 else 0
        wr_v24 = (wins_v24 / trades_v24 * 100) if trades_v24 > 0 else 0
        
        ret_v21 = sum(r['avg_return'] * r['trades'] for r in results_v21) / trades_v21 if trades_v21 > 0 else 0
        ret_v24 = sum(r['avg_return'] * r['trades'] for r in results_v24) / trades_v24 if trades_v24 > 0 else 0
        
        print(f"\n📉 Trades Filtrados:")
        print(f"   v2.1: {trades_v21} trades")
        print(f"   v2.4: {trades_v24} trades")
        filtered = trades_v21 - trades_v24
        filter_rate = (filtered / trades_v21 * 100) if trades_v21 > 0 else 0
        print(f"   🔴 Rejeitados: {filtered} ({filter_rate:.1f}%)")
        
        print(f"\n📈 Win Rate:")
        print(f"   v2.1: {wr_v21:.1f}%")
        print(f"   v2.4: {wr_v24:.1f}% ({'🟢 +' if wr_v24 > wr_v21 else '🔴 '}{wr_v24-wr_v21:.1f}%)")
        
        print(f"\n💰 Retorno Médio:")
        print(f"   v2.1: {ret_v21:+.2f}%")
        print(f"   v2.4: {ret_v24:+.2f}% ({'🟢 +' if ret_v24 > ret_v21 else '🔴 '}{ret_v24-ret_v21:.2f}%)")
        
        print(f"\n🎯 CONCLUSÃO:")
        if filter_rate < 5:
            print(f"   ⚠️ Filtro rejeitou apenas {filter_rate:.1f}% - threshold muito baixo")
            print(f"   💡 Sugestão: aumentar threshold para 0.40-0.50")
        elif filter_rate > 30:
            print(f"   ⚠️ Filtro rejeitou {filter_rate:.1f}% - threshold muito alto")
            print(f"   💡 Sugestão: reduzir threshold para 0.20-0.25")
        else:
            if wr_v24 > wr_v21 + 5:
                print(f"   ✅ SUCESSO! Filtro melhorou win rate em +{wr_v24-wr_v21:.1f}%")
                print(f"   🎉 ML Negative Filter está funcionando!")
            elif wr_v24 > wr_v21:
                print(f"   ✅ Leve melhora no win rate (+{wr_v24-wr_v21:.1f}%)")
                print(f"   💡 Considerar ajuste de threshold para melhor resultado")
            else:
                print(f"   ❌ Filtro não melhorou performance")
                print(f"   💡 Revisar features ou abandonar ML")


async def backtest_strategy(strategy, df_daily, df_60min, symbol, strategy_name):
    """Executa backtest nos últimos 6 meses"""
    try:
        trades = []
        position = None
        
        # Últimos 6 meses
        last_date = df_daily['time'].max()
        start_date = last_date - timedelta(days=180)
        df_daily_6m = df_daily[df_daily['time'] >= start_date].copy()
        
        for i in range(len(df_daily_6m)):
            current_date = df_daily_6m.iloc[i]['time']
            
            df_daily_slice = df_daily[df_daily['time'] <= current_date].copy()
            df_60min_slice = df_60min[df_60min['time'] <= current_date].copy()
            
            if len(df_daily_slice) < 100 or len(df_60min_slice) < 50:
                continue
            
            # Sem posição: buscar entrada
            if position is None:
                try:
                    signal = strategy.generate_signal(df_daily_slice, df_60min_slice, symbol)
                except Exception:
                    continue
                
                if signal and hasattr(signal, 'quality_score'):
                    take_profit = signal.target_3 if hasattr(signal, 'target_3') else signal.entry_price * 1.18
                    
                    position = {
                        'entry_date': current_date,
                        'entry_price': float(df_daily_slice.iloc[-1]['close']),
                        'stop_loss': float(signal.stop_loss),
                        'take_profit': float(take_profit),
                        'score': signal.quality_score,
                        'ml_confidence': signal.ml_confidence if hasattr(signal, 'ml_confidence') else 0.5
                    }
            
            # Com posição: verificar saída
            else:
                current_price = float(df_daily_slice.iloc[-1]['close'])
                
                if current_price <= position['stop_loss'] or current_price >= position['take_profit']:
                    ret = ((current_price - position['entry_price']) / position['entry_price']) * 100
                    
                    trade = {
                        'entry_date': position['entry_date'],
                        'exit_date': current_date,
                        'return_pct': ret,
                        'result': 'WIN' if ret > 0 else 'LOSS',
                        'ml_confidence': position['ml_confidence']
                    }
                    
                    trades.append(trade)
                    position = None
        
        if len(trades) == 0:
            print(f"      {strategy_name}: 0 trades")
            return None
        
        wins = [t for t in trades if t['result'] == 'WIN']
        win_rate = (len(wins) / len(trades)) * 100
        avg_return = sum(t['return_pct'] for t in trades) / len(trades)
        avg_ml_conf = sum(t['ml_confidence'] for t in trades) / len(trades)
        
        print(f"      {strategy_name}: {len(trades)} trades | {win_rate:.0f}% win | {avg_return:+.2f}% avg | ML {avg_ml_conf:.0%}")
        
        return {
            'symbol': symbol,
            'strategy': strategy_name,
            'trades': len(trades),
            'wins': len(wins),
            'losses': len(trades) - len(wins),
            'win_rate': win_rate,
            'avg_return': avg_return
        }
        
    except Exception as e:
        print(f"      {strategy_name}: ❌ {e}")
        return None


def print_summary(strategy_name, results):
    """Exibe resumo consolidado"""
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
        
        print(f"Ativos: {len(results)}")
        print(f"Trades: {total_trades}")
        print(f"Win Rate: {overall_wr:.1f}%")
        print(f"Retorno Médio: {overall_ret:+.2f}%")


if __name__ == "__main__":
    asyncio.run(test_negative_filter())
