#!/usr/bin/env python3
"""
Backtest Wave3 v2.1 - OTIMIZADO
================================

Versão rápida: verifica sinais apenas 1x por dia (no fechamento diário)

Autor: B3 Trading Platform
Data: 28 Janeiro 2026
"""

import pandas as pd
import numpy as np
from datetime import datetime
import sys
import asyncio
import asyncpg

sys.path.append('/app/src/strategies')
from wave3_enhanced import Wave3Enhanced


async def backtest_symbol_fast(pool, strategy, symbol):
    """Backtest otimizado - 1 verificação por dia"""
    
    print(f"\n{'='*80}")
    print(f"🔄 {symbol}")
    print(f"{'='*80}")
    
    # Buscar dados
    async with pool.acquire() as conn:
        rows_daily = await conn.fetch("""
            SELECT time, open, high, low, close, volume
            FROM ohlcv_daily
            WHERE symbol = $1
            AND time >= '2023-01-01'
            ORDER BY time
        """, symbol)
        
        rows_60min = await conn.fetch("""
            SELECT time, open, high, low, close, volume
            FROM ohlcv_60min
            WHERE symbol = $1
            AND time >= '2023-01-01'
            ORDER BY time
        """, symbol)
    
    if len(rows_daily) < 100:
        print(f"⚠️ Dados insuficientes: {len(rows_daily)} daily")
        return None
    
    print(f"✅ {len(rows_daily)} daily, {len(rows_60min)} 60min")
    
    # DataFrames
    df_daily = pd.DataFrame(
        [(r['time'], float(r['open']), float(r['high']), 
          float(r['low']), float(r['close']), float(r['volume']))
         for r in rows_daily],
        columns=['time', 'open', 'high', 'low', 'close', 'volume']
    )
    
    df_60min = pd.DataFrame(
        [(r['time'], float(r['open']), float(r['high']), 
          float(r['low']), float(r['close']), float(r['volume']))
         for r in rows_60min],
        columns=['time', 'open', 'high', 'low', 'close', 'volume']
    )
    
    # Verificar sinal apenas 1x por dia
    signals = []
    trades = []
    
    for i in range(72, len(df_daily)):  # Warm-up 72 dias (EMA 72)
        daily_context = df_daily.iloc[:i+1].copy()
        current_date = daily_context.iloc[-1]['time']
        
        # 60min até esta data
        intraday_context = df_60min[df_60min['time'] <= current_date].copy()
        
        if len(intraday_context) < 20:
            continue
        
        try:
            signal = strategy.generate_signal(
                df_daily=daily_context,
                df_60min=intraday_context,
                symbol=symbol
            )
            
            if signal and hasattr(signal, 'signal_type'):
                entry_price = signal.entry_price
                stop_loss = signal.stop_loss
                target_3 = signal.target_3  # Alvo final 3:1
                
                # Simular trade
                future_daily = df_daily.iloc[i+1:i+31]  # Próximos 30 dias
                
                exit_price = None
                exit_date = None
                hit_stop = False
                
                for idx, day in future_daily.iterrows():
                    if signal.signal_type == 'BUY':
                        if day['low'] <= stop_loss:
                            exit_price = stop_loss
                            exit_date = day['time']
                            hit_stop = True
                            break
                        if day['high'] >= target_3:
                            exit_price = target_3
                            exit_date = day['time']
                            break
                    else:  # SELL
                        if day['high'] >= stop_loss:
                            exit_price = stop_loss
                            exit_date = day['time']
                            hit_stop = True
                            break
                        if day['low'] <= target_3:
                            exit_price = target_3
                            exit_date = day['time']
                            break
                
                # Se não bateu stop/target, fechar após 30 dias
                if exit_price is None and len(future_daily) > 0:
                    last_day = future_daily.iloc[-1]
                    exit_price = last_day['close']
                    exit_date = last_day['time']
                
                if exit_price:
                    if signal.signal_type == 'BUY':
                        return_pct = ((exit_price / entry_price) - 1) * 100
                    else:
                        return_pct = ((entry_price / exit_price) - 1) * 100
                    
                    trades.append({
                        'entry_date': current_date,
                        'exit_date': exit_date,
                        'direction': signal.signal_type,
                        'entry': entry_price,
                        'exit': exit_price,
                        'return': return_pct,
                        'hit_stop': hit_stop
                    })
                    
                    signals.append(signal)
        
        except Exception as e:
            continue
    
    # Estatísticas
    if not trades:
        print(f"⚠️ Nenhum trade")
        return None
    
    returns = [t['return'] for t in trades]
    winners = sum(1 for r in returns if r > 0)
    losers = sum(1 for r in returns if r < 0)
    win_rate = (winners / len(trades) * 100) if trades else 0
    
    avg_win = np.mean([r for r in returns if r > 0]) if winners > 0 else 0
    avg_loss = abs(np.mean([r for r in returns if r < 0])) if losers > 0 else 0
    
    total_return = sum(returns)
    sharpe = (np.mean(returns) / np.std(returns) * np.sqrt(252)) if np.std(returns) > 0 else 0
    
    print(f"\n📊 Trades: {len(trades)} | Win: {winners} ({win_rate:.1f}%)")
    print(f"💰 Return: {total_return:.2f}% | Sharpe: {sharpe:.2f}")
    print(f"📈 Avg Win: {avg_win:.2f}% | Avg Loss: {avg_loss:.2f}%")
    
    return {
        'symbol': symbol,
        'trades': len(trades),
        'winners': winners,
        'win_rate': win_rate,
        'total_return': total_return,
        'sharpe': sharpe,
        'avg_win': avg_win,
        'avg_loss': avg_loss,
        'trades_detail': trades
    }


async def main():
    """Main"""
    
    print("\n" + "="*80)
    print("BACKTEST WAVE3 v2.1 - OTIMIZADO (1x/dia)")
    print("="*80)
    print(f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print("="*80)
    
    # Conectar
    pool = await asyncpg.create_pool(
        host='b3-timescaledb',
        port=5432,
        user='b3trading_ts',
        password='b3trading_ts_pass',
        database='b3trading_market',
        min_size=1,
        max_size=5
    )
    
    # Estratégia
    strategy = Wave3Enhanced(min_quality_score=55)
    
    # Símbolos
    symbols = ['PETR4', 'VALE3', 'ITUB4', 'BBDC4', 'ABEV3']
    
    results = []
    
    for symbol in symbols:
        result = await backtest_symbol_fast(pool, strategy, symbol)
        if result:
            results.append(result)
    
    # Resumo
    print("\n" + "="*80)
    print("RESUMO CONSOLIDADO")
    print("="*80)
    
    if results:
        total_trades = sum(r['trades'] for r in results)
        total_winners = sum(r['winners'] for r in results)
        avg_win_rate = np.mean([r['win_rate'] for r in results])
        avg_return = np.mean([r['total_return'] for r in results])
        avg_sharpe = np.mean([r['sharpe'] for r in results])
        
        print(f"\nTotal Trades:     {total_trades}")
        print(f"Total Winners:    {total_winners} ({total_winners/total_trades*100:.1f}%)")
        print(f"Avg Win Rate:     {avg_win_rate:.1f}%")
        print(f"Avg Return:       {avg_return:.2f}%")
        print(f"Avg Sharpe:       {avg_sharpe:.2f}")
        
        print(f"\n{'Símbolo':<10} {'Trades':<10} {'Win%':<10} {'Return%':<12} {'Sharpe':<10}")
        print("-"*80)
        for r in results:
            print(f"{r['symbol']:<10} {r['trades']:<10} {r['win_rate']:<10.1f} {r['total_return']:<12.2f} {r['sharpe']:<10.2f}")
    
    print("\n" + "="*80)
    
    await pool.close()


if __name__ == '__main__':
    asyncio.run(main())
