#!/usr/bin/env python3
"""
Teste comparativo da estratégia Wave3 com dados de 60min vs daily
Usa dados reais importados do ProfitChart
"""

import asyncio
import asyncpg
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

# Configuração do banco
DB_CONFIG = {
    'host': 'b3-timescaledb',
    'port': 5432,
    'database': 'b3trading_market',
    'user': 'b3trading_ts',
    'password': 'b3trading_ts_pass'
}

class SimpleWave3:
    """Implementação simplificada da estratégia Wave3"""
    
    def __init__(self, 
                 sma_period=20,
                 sma_trend_period=50,
                 rsi_period=14,
                 rsi_overbought=70,
                 rsi_oversold=30):
        self.sma_period = sma_period
        self.sma_trend_period = sma_trend_period
        self.rsi_period = rsi_period
        self.rsi_overbought = rsi_overbought
        self.rsi_oversold = rsi_oversold
    
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calcula indicadores técnicos"""
        # SMA
        df['sma'] = df['close'].rolling(window=self.sma_period).mean()
        df['sma_trend'] = df['close'].rolling(window=self.sma_trend_period).mean()
        
        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=self.rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.rsi_period).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # ATR para stop loss
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        df['atr'] = ranges.max(axis=1).rolling(14).mean()
        
        return df
    
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """Gera sinais de compra/venda"""
        df = self.calculate_indicators(df)
        
        # Sinal de compra
        df['buy_signal'] = (
            (df['close'] > df['sma']) &
            (df['sma'] > df['sma_trend']) &
            (df['rsi'] < self.rsi_overbought) &
            (df['rsi'] > self.rsi_oversold)
        )
        
        # Sinal de venda
        df['sell_signal'] = (
            (df['close'] < df['sma']) |
            (df['rsi'] > self.rsi_overbought)
        )
        
        return df


async def load_data(symbol: str, interval: str, start_date: str, end_date: str) -> pd.DataFrame:
    """Carrega dados do TimescaleDB"""
    
    table = f'ohlcv_{interval}'
    
    conn = await asyncpg.connect(**DB_CONFIG)
    
    # Converte strings para datetime
    start_dt = datetime.strptime(start_date, '%Y-%m-%d')
    end_dt = datetime.strptime(end_date, '%Y-%m-%d')
    
    query = f'''
        SELECT time, open, high, low, close, volume
        FROM {table}
        WHERE symbol = $1
          AND time >= $2
          AND time <= $3
        ORDER BY time ASC
    '''
    
    rows = await conn.fetch(query, symbol, start_dt, end_dt)
    await conn.close()
    
    if not rows:
        return pd.DataFrame()
    
    df = pd.DataFrame(rows, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
    df['time'] = pd.to_datetime(df['time'])
    df.set_index('time', inplace=True)
    
    return df


def backtest_strategy(df: pd.DataFrame, initial_capital=100000.0) -> Dict:
    """Executa backtest da estratégia"""
    
    strategy = SimpleWave3()
    df = strategy.generate_signals(df)
    
    # Simula trades
    capital = initial_capital
    position = 0
    shares = 0
    entry_price = 0
    trades = []
    equity_curve = [initial_capital]
    
    for i in range(len(df)):
        row = df.iloc[i]
        
        # Compra
        if position == 0 and row['buy_signal']:
            shares = int(capital * 0.95 / row['close'])  # 95% do capital
            if shares > 0:
                entry_price = row['close']
                capital -= shares * entry_price
                position = 1
                trades.append({
                    'type': 'BUY',
                    'time': row.name,
                    'price': entry_price,
                    'shares': shares
                })
        
        # Venda
        elif position == 1 and row['sell_signal']:
            exit_price = row['close']
            capital += shares * exit_price
            profit = (exit_price - entry_price) * shares
            trades.append({
                'type': 'SELL',
                'time': row.name,
                'price': exit_price,
                'shares': shares,
                'profit': profit,
                'return_pct': (exit_price / entry_price - 1) * 100
            })
            position = 0
            shares = 0
        
        # Atualiza equity
        if position == 1:
            equity = capital + (shares * row['close'])
        else:
            equity = capital
        equity_curve.append(equity)
    
    # Fecha posição final se necessário
    if position == 1:
        exit_price = df.iloc[-1]['close']
        capital += shares * exit_price
        profit = (exit_price - entry_price) * shares
        trades.append({
            'type': 'SELL',
            'time': df.index[-1],
            'price': exit_price,
            'shares': shares,
            'profit': profit,
            'return_pct': (exit_price / entry_price - 1) * 100
        })
    
    final_capital = capital
    total_return = (final_capital / initial_capital - 1) * 100
    
    # Calcula métricas
    profitable_trades = [t for t in trades if t.get('profit', 0) > 0]
    losing_trades = [t for t in trades if t.get('profit', 0) < 0]
    
    num_trades = len([t for t in trades if t['type'] == 'SELL'])
    win_rate = len(profitable_trades) / num_trades * 100 if num_trades > 0 else 0
    
    avg_win = np.mean([t['profit'] for t in profitable_trades]) if profitable_trades else 0
    avg_loss = np.mean([abs(t['profit']) for t in losing_trades]) if losing_trades else 0
    
    # Sharpe Ratio
    returns = pd.Series(equity_curve).pct_change().dropna()
    sharpe = returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0
    
    # Max Drawdown
    equity_series = pd.Series(equity_curve)
    running_max = equity_series.expanding().max()
    drawdown = (equity_series - running_max) / running_max
    max_drawdown = drawdown.min() * 100
    
    return {
        'initial_capital': initial_capital,
        'final_capital': final_capital,
        'total_return_pct': total_return,
        'num_trades': num_trades,
        'profitable_trades': len(profitable_trades),
        'losing_trades': len(losing_trades),
        'win_rate': win_rate,
        'avg_win': avg_win,
        'avg_loss': avg_loss,
        'profit_factor': abs(avg_win / avg_loss) if avg_loss != 0 else 0,
        'sharpe_ratio': sharpe,
        'max_drawdown_pct': max_drawdown,
        'trades': trades
    }


async def compare_intervals(symbol: str, start_date: str, end_date: str):
    """Compara desempenho entre 60min e daily"""
    
    print("=" * 100)
    print(f"COMPARAÇÃO WAVE3: {symbol}")
    print("=" * 100)
    print(f"Período: {start_date} → {end_date}")
    print()
    
    # Testa 60min
    print("📊 Carregando dados 60min...")
    df_60min = await load_data(symbol, '60min', start_date, end_date)
    
    if df_60min.empty:
        print(f"❌ Sem dados 60min para {symbol}")
        return
    
    print(f"   ✅ {len(df_60min)} candles carregados")
    
    # Testa daily
    print("📊 Carregando dados daily...")
    df_daily = await load_data(symbol, 'daily', start_date, end_date)
    
    if df_daily.empty:
        print(f"❌ Sem dados daily para {symbol}")
        return
    
    print(f"   ✅ {len(df_daily)} candles carregados")
    print()
    
    # Backtest 60min
    print("🔄 Executando backtest 60min...")
    results_60min = backtest_strategy(df_60min)
    
    # Backtest daily
    print("🔄 Executando backtest daily...")
    results_daily = backtest_strategy(df_daily)
    
    # Exibe comparação
    print()
    print("=" * 100)
    print("RESULTADOS COMPARATIVOS")
    print("=" * 100)
    print()
    
    print(f"{'Métrica':<25} {'60min':>20} {'Daily':>20} {'Diferença':>20}")
    print("-" * 100)
    
    metrics = [
        ('Capital Inicial', 'initial_capital', 'R$ {:,.2f}'),
        ('Capital Final', 'final_capital', 'R$ {:,.2f}'),
        ('Retorno Total', 'total_return_pct', '{:+.2f}%'),
        ('Número de Trades', 'num_trades', '{:.0f}'),
        ('Trades Lucrativos', 'profitable_trades', '{:.0f}'),
        ('Trades Perdedores', 'losing_trades', '{:.0f}'),
        ('Win Rate', 'win_rate', '{:.2f}%'),
        ('Lucro Médio', 'avg_win', 'R$ {:,.2f}'),
        ('Perda Média', 'avg_loss', 'R$ {:,.2f}'),
        ('Profit Factor', 'profit_factor', '{:.2f}'),
        ('Sharpe Ratio', 'sharpe_ratio', '{:.2f}'),
        ('Max Drawdown', 'max_drawdown_pct', '{:.2f}%'),
    ]
    
    for label, key, fmt in metrics:
        val_60min = results_60min[key]
        val_daily = results_daily[key]
        
        if isinstance(val_60min, (int, float)) and isinstance(val_daily, (int, float)):
            diff = val_60min - val_daily
            if '%' in fmt:
                diff_str = f"{diff:+.2f}pp"
            else:
                diff_str = fmt.format(diff)
        else:
            diff_str = "-"
        
        print(f"{label:<25} {fmt.format(val_60min):>20} {fmt.format(val_daily):>20} {diff_str:>20}")
    
    print()
    print("=" * 100)
    
    # Últimos 5 trades de cada
    print()
    print("ÚLTIMOS 5 TRADES - 60MIN")
    print("-" * 100)
    for trade in results_60min['trades'][-10:]:
        if trade['type'] == 'SELL':
            print(f"  {trade['time']}: SELL @ R$ {trade['price']:.2f} | "
                  f"Lucro: R$ {trade['profit']:,.2f} | Retorno: {trade['return_pct']:+.2f}%")
    
    print()
    print("ÚLTIMOS 5 TRADES - DAILY")
    print("-" * 100)
    for trade in results_daily['trades'][-10:]:
        if trade['type'] == 'SELL':
            print(f"  {trade['time']}: SELL @ R$ {trade['price']:.2f} | "
                  f"Lucro: R$ {trade['profit']:,.2f} | Retorno: {trade['return_pct']:+.2f}%")
    
    print()


async def main():
    """Main"""
    
    symbols = ['PETR4', 'VALE3', 'ITUB4']
    start_date = '2024-01-01'
    end_date = '2025-12-30'
    
    for symbol in symbols:
        await compare_intervals(symbol, start_date, end_date)
        print("\n\n")


if __name__ == '__main__':
    asyncio.run(main())
