#!/usr/bin/env python3
"""
Backtest Wave3 PURA (SEM ML)
============================

Testa Wave3 v2.1 SEM filtro ML para comparar com versão ML+GPU.

Objetivo:
- Validar se ML agrega valor à estratégia Wave3
- Baseline: Wave3 pura com quality_score >= 55

Autor: B3 Trading Platform
Data: 29 Janeiro 2026
"""

import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
import sys
import asyncio
import asyncpg
from decimal import Decimal
import argparse

sys.path.append('/app/src/strategies')


def calculate_wave3_score(df_daily: pd.DataFrame, df_60min: pd.DataFrame, 
                          current_idx: int, symbol: str) -> tuple:
    """
    Calcula quality score Wave3 simplificado
    
    Retorna: (score, direction, entry_price)
    """
    
    if current_idx < 72:  # Precisa EMA 72
        return (0, None, None)
    
    # Contexto diário
    daily_close = df_daily.iloc[:current_idx+1]['close'].values
    
    # EMAs diárias
    ema_72 = pd.Series(daily_close).ewm(span=72, adjust=False).mean().iloc[-1]
    ema_17 = pd.Series(daily_close).ewm(span=17, adjust=False).mean().iloc[-1]
    
    # Preço atual
    current_price = df_60min.iloc[current_idx]['close']
    
    # Regra Wave3: Preço acima EMA 72 E EMA 17 > EMA 72
    if current_price > ema_72 and ema_17 > ema_72:
        direction = 'LONG'
    elif current_price < ema_72 and ema_17 < ema_72:
        direction = 'SHORT'
    else:
        return (0, None, None)
    
    # Score simplificado (0-100)
    # Baseado em distância das EMAs e momentum
    ema_distance = abs(ema_17 - ema_72) / ema_72 * 100
    price_momentum = (current_price - daily_close[-2]) / daily_close[-2] * 100
    
    # Volatilidade (últimos 20 dias)
    volatility = pd.Series(daily_close[-20:]).std() / pd.Series(daily_close[-20:]).mean() * 100
    
    # Score = distância EMAs (0-40) + momentum (0-30) + volatilidade (0-30)
    score = min(100, int(
        min(40, ema_distance * 10) +
        min(30, abs(price_momentum) * 10) +
        min(30, volatility * 2)
    ))
    
    return (score, direction, current_price)


def simulate_trades(signals, df_60min):
    """Simula execução de trades com risk:reward 3:1"""
    
    trades = []
    
    for signal in signals:
        signal_time = signal['timestamp']
        entry_price = signal['entry_price']
        direction = signal['direction']
        
        # Stop loss e take profit
        if direction == 'LONG':
            stop_loss = entry_price * 0.94  # -6%
            take_profit = entry_price * 1.18  # +18%
        else:
            stop_loss = entry_price * 1.06
            take_profit = entry_price * 0.82
        
        # Buscar candles futuros
        future_candles = df_60min[df_60min['time'] > signal_time].head(30)
        
        if len(future_candles) == 0:
            continue
        
        # Simular trade
        exit_price = None
        exit_time = None
        hit_stop = False
        
        for _, candle in future_candles.iterrows():
            if direction == 'LONG':
                if candle['low'] <= stop_loss:
                    exit_price = stop_loss
                    exit_time = candle['time']
                    hit_stop = True
                    break
                elif candle['high'] >= take_profit:
                    exit_price = take_profit
                    exit_time = candle['time']
                    break
            else:  # SHORT
                if candle['high'] >= stop_loss:
                    exit_price = stop_loss
                    exit_time = candle['time']
                    hit_stop = True
                    break
                elif candle['low'] <= take_profit:
                    exit_price = take_profit
                    exit_time = candle['time']
                    break
        
        if exit_price is None:
            exit_price = future_candles.iloc[-1]['close']
            exit_time = future_candles.iloc[-1]['time']
        
        # Calcular retorno
        if direction == 'LONG':
            return_pct = (exit_price - entry_price) / entry_price * 100
        else:
            return_pct = (entry_price - exit_price) / entry_price * 100
        
        trades.append({
            'entry_time': signal_time,
            'exit_time': exit_time,
            'entry_price': entry_price,
            'exit_price': exit_price,
            'return_pct': return_pct,
            'direction': direction,
            'hit_stop': hit_stop,
            'quality_score': signal['quality_score']
        })
    
    return trades


class BacktestResults:
    """Métricas de backtest"""
    
    def __init__(self, symbol, trades, signals_count):
        self.symbol = symbol
        self.trades = trades
        self.signals_count = signals_count
        self.calculate_metrics()
    
    def calculate_metrics(self):
        if not self.trades:
            self.total_trades = 0
            self.winners = 0
            self.losers = 0
            self.win_rate = 0.0
            self.avg_win = 0.0
            self.avg_loss = 0.0
            self.profit_factor = 0.0
            self.total_return = 0.0
            self.sharpe_ratio = 0.0
            self.max_drawdown = 0.0
            return
        
        self.total_trades = len(self.trades)
        returns = [t['return_pct'] for t in self.trades]
        
        self.winners = sum(1 for r in returns if r > 0)
        self.losers = sum(1 for r in returns if r < 0)
        self.win_rate = (self.winners / self.total_trades * 100) if self.total_trades > 0 else 0
        
        wins = [r for r in returns if r > 0]
        losses = [r for r in returns if r < 0]
        
        self.avg_win = np.mean(wins) if wins else 0.0
        self.avg_loss = abs(np.mean(losses)) if losses else 0.0
        
        total_wins = sum(wins) if wins else 0.0
        total_losses = abs(sum(losses)) if losses else 0.0
        self.profit_factor = (total_wins / total_losses) if total_losses > 0 else 0.0
        
        self.total_return = sum(returns)
        
        # Sharpe Ratio
        if returns:
            mean_return = np.mean(returns)
            std_return = np.std(returns)
            self.sharpe_ratio = (mean_return / std_return * np.sqrt(252)) if std_return > 0 else 0.0
        else:
            self.sharpe_ratio = 0.0
        
        # Max Drawdown
        cumulative = np.cumsum(returns)
        running_max = np.maximum.accumulate(cumulative)
        drawdown = running_max - cumulative
        self.max_drawdown = np.max(drawdown) if len(drawdown) > 0 else 0.0
    
    def __str__(self):
        return f"""
================================================================================
📊 RESULTADOS: {self.symbol}
================================================================================
Sinais Wave3 gerados:  {self.signals_count}
Trades executados:     {self.total_trades}
Winners:               {self.winners} ({self.win_rate:.1f}%)
Losers:                {self.losers}
Avg Win:               {self.avg_win:.2f}%
Avg Loss:              {self.avg_loss:.2f}%
Profit Factor:         {self.profit_factor:.2f}
Total Return:          {self.total_return:.2f}%
Sharpe Ratio:          {self.sharpe_ratio:.2f}
Max Drawdown:          {self.max_drawdown:.2f}%
================================================================================
"""


async def backtest_symbol(pool, symbol: str, start_date: date, end_date: date, min_quality: int):
    """Backtest Wave3 pura para um símbolo"""
    
    print(f"\n{'='*80}")
    print(f"📊 Backtesting Wave3 PURA: {symbol}")
    print(f"   Período: {start_date} → {end_date}")
    print(f"   Quality Score: >={min_quality}")
    print('='*80)
    
    # Buscar dados
    async with pool.acquire() as conn:
        rows_daily = await conn.fetch("""
            SELECT time, open, high, low, close, volume
            FROM ohlcv_daily
            WHERE symbol = $1 AND time >= $2 AND time <= $3
            ORDER BY time
        """, symbol, start_date, end_date)
        
        rows_60min = await conn.fetch("""
            SELECT time, open, high, low, close, volume
            FROM ohlcv_60min
            WHERE symbol = $1 AND time >= $2 AND time <= $3
            ORDER BY time
        """, symbol, start_date, end_date)
    
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
    
    print(f"✅ Dados: {len(df_daily)} daily, {len(df_60min)} 60min")
    
    # Gerar sinais Wave3
    print("🔍 Gerando sinais Wave3 (sem ML)...")
    signals = []
    
    for i in range(200, len(df_60min)):
        current_time = df_60min.iloc[i]['time']
        current_date = pd.Timestamp(current_time).normalize()
        
        # Contexto diário até esta data
        daily_context = df_daily[df_daily['time'] <= current_date]
        
        if len(daily_context) < 72:
            continue
        
        score, direction, entry_price = calculate_wave3_score(
            daily_context, df_60min, i, symbol
        )
        
        if score >= min_quality and direction is not None:
            signals.append({
                'timestamp': current_time,
                'quality_score': score,
                'direction': direction,
                'entry_price': entry_price,
                'symbol': symbol
            })
    
    print(f"   → {len(signals)} sinais com quality_score >= {min_quality}")
    
    if len(signals) == 0:
        print("⚠️ Nenhum sinal gerado")
        return None
    
    # Simular trades
    print("💰 Simulando trades...")
    trades = simulate_trades(signals, df_60min)
    print(f"   → {len(trades)} trades executados")
    
    # Calcular métricas
    results = BacktestResults(symbol, trades, len(signals))
    
    return results


async def main():
    """Função principal"""
    
    parser = argparse.ArgumentParser(description='Backtest Wave3 PURA (sem ML)')
    parser.add_argument('--min-quality', type=int, default=55,
                       help='Quality score mínimo (default: 55)')
    parser.add_argument('--symbols', nargs='+', default=['PETR4'],
                       help='Símbolos a testar')
    parser.add_argument('--start', type=str, default='2024-07-01',
                       help='Data início (YYYY-MM-DD)')
    parser.add_argument('--end', type=str, default='2024-12-31',
                       help='Data fim (YYYY-MM-DD)')
    args = parser.parse_args()
    
    start_date = date.fromisoformat(args.start)
    end_date = date.fromisoformat(args.end)
    
    print("\n" + "="*80)
    print("BACKTEST WAVE3 PURA (SEM ML)")
    print("="*80)
    print(f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print(f"Estratégia: Wave3 v2.1 (quality_score >= {args.min_quality})")
    print(f"Período: {start_date} → {end_date}")
    print(f"Símbolos: {', '.join(args.symbols)}")
    print("="*80)
    
    # Conectar DB
    print("\n🔗 Conectando ao TimescaleDB...")
    try:
        pool = await asyncpg.create_pool(
            host='b3-timescaledb',
            port=5432,
            user='b3trading_ts',
            password='b3trading_ts_pass',
            database='b3trading_market',
            min_size=1,
            max_size=5
        )
        print("✅ Conectado")
    except Exception as e:
        print(f"❌ Erro: {e}")
        return
    
    # Backtest para cada símbolo
    all_results = []
    
    for idx, symbol in enumerate(args.symbols, 1):
        print(f"\n[{idx}/{len(args.symbols)}]", end=" ")
        
        try:
            results = await backtest_symbol(
                pool, symbol, start_date, end_date, args.min_quality
            )
            
            if results:
                all_results.append(results)
                print(results)
        
        except Exception as e:
            print(f"❌ Erro em {symbol}: {e}")
            import traceback
            traceback.print_exc()
    
    # Resumo consolidado
    if all_results:
        print("\n" + "="*80)
        print("RESUMO CONSOLIDADO - WAVE3 PURA")
        print("="*80)
        
        total_signals = sum(r.signals_count for r in all_results)
        total_trades = sum(r.total_trades for r in all_results)
        total_winners = sum(r.winners for r in all_results)
        avg_win_rate = np.mean([r.win_rate for r in all_results])
        avg_sharpe = np.mean([r.sharpe_ratio for r in all_results])
        avg_return = np.mean([r.total_return for r in all_results])
        
        print(f"\n📊 Performance:")
        print(f"   Total Sinais:     {total_signals}")
        print(f"   Total Trades:     {total_trades}")
        print(f"   Total Winners:    {total_winners} ({total_winners/total_trades*100:.1f}%)")
        print(f"   Avg Win Rate:     {avg_win_rate:.1f}%")
        print(f"   Avg Sharpe:       {avg_sharpe:.2f}")
        print(f"   Avg Return:       {avg_return:.2f}%")
        
        print(f"\n{'Símbolo':<10} {'Sinais':<8} {'Trades':<8} {'Win%':<8} {'Return%':<10} {'Sharpe':<8}")
        print("-"*80)
        for r in all_results:
            print(f"{r.symbol:<10} {r.signals_count:<8} {r.total_trades:<8} {r.win_rate:<8.1f} {r.total_return:<10.2f} {r.sharpe_ratio:<8.2f}")
    
    else:
        print("⚠️ Nenhum resultado válido")
    
    print("\n" + "="*80)
    print("✅ Backtest Wave3 PURA concluído!")
    print("="*80)
    
    await pool.close()


if __name__ == '__main__':
    asyncio.run(main())
