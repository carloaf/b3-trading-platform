#!/usr/bin/env python3
"""
Backtest Comparativo: Wave3 Original vs Enhanced
================================================

Compara performance entre:
1. Wave3 Multi-Timeframe (original)
2. Wave3 Enhanced (com otimizações)

Métricas comparadas:
- Retorno total
- Win rate
- Profit factor
- Sharpe ratio
- Max drawdown
- Número de trades
- Score médio de qualidade

Autor: B3 Trading Platform
Data: Janeiro 2026
"""

import sys
import asyncio
import asyncpg
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Tuple

sys.path.append('/app/src/strategies')

try:
    from wave3_enhanced import Wave3Enhanced, EnhancedWave3Signal
    from wave3_multi_timeframe import Wave3MultiTimeframe, Wave3Signal
except ImportError:
    print("⚠️  Erro ao importar estratégias")
    sys.exit(1)


DB_CONFIG = {
    'host': 'b3-timescaledb',
    'port': 5432,
    'database': 'b3trading_market',
    'user': 'b3trading_ts',
    'password': 'b3trading_ts_pass'
}


async def load_ohlcv_data(symbol: str, interval: str, start_date: str, end_date: str) -> pd.DataFrame:
    """Carrega dados OHLCV"""
    conn = await asyncpg.connect(**DB_CONFIG)
    
    table_name = f'ohlcv_{interval}'
    
    start_dt = datetime.strptime(start_date, '%Y-%m-%d') if isinstance(start_date, str) else start_date
    end_dt = datetime.strptime(end_date, '%Y-%m-%d') if isinstance(end_date, str) else end_date
    
    query = f'''
        SELECT time, open, high, low, close, volume
        FROM {table_name}
        WHERE symbol = $1
          AND time >= $2::timestamp
          AND time <= $3::timestamp
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


class EnhancedBacktester:
    """
    Backtester para Wave3 Enhanced com alvos parciais
    """
    
    def __init__(self, initial_capital: float = 100000.0):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.position = None
        self.trades = []
        self.partial_exits = []
        
    def open_position(self, signal: EnhancedWave3Signal):
        """Abre posição com alvos parciais"""
        
        # Calcula shares baseado em risco máximo 2%
        max_risk_capital = self.capital * 0.02
        shares = int(max_risk_capital / signal.risk) if signal.risk > 0 else 0
        
        # Limita ao capital disponível
        max_shares = int((self.capital * 0.95) / signal.entry_price)
        shares = min(shares, max_shares)
        
        if shares <= 0:
            return
        
        cost = shares * signal.entry_price
        
        self.position = {
            'signal': signal,
            'shares_total': shares,
            'shares_remaining': shares,
            'entry_price': signal.entry_price,
            'entry_time': signal.timestamp,
            'stop_loss': signal.stop_loss,
            'target_1': signal.target_1,
            'target_2': signal.target_2,
            'target_3': signal.target_3,
            'type': signal.signal_type,
            'cost': cost,
            'partial_exits': []
        }
        
        self.capital -= cost
        
    def check_partial_exits(self, current_price: float, current_time: datetime) -> List[Dict]:
        """Verifica e executa saídas parciais"""
        
        if self.position is None or self.position['shares_remaining'] == 0:
            return []
        
        exits = []
        pos = self.position
        
        # Define alvos pendentes
        targets = []
        if 'target_1_hit' not in pos:
            targets.append(('target_1', 0.5, pos['target_1']))
        if 'target_2_hit' not in pos:
            targets.append(('target_2', 0.3, pos['target_2']))
        if 'target_3_hit' not in pos:
            targets.append(('target_3', 0.2, pos['target_3']))
        
        for target_name, pct, target_price in targets:
            hit = False
            
            if pos['type'] == 'BUY':
                hit = current_price >= target_price
            else:
                hit = current_price <= target_price
            
            if hit:
                shares_to_exit = int(pos['shares_total'] * pct)
                
                if shares_to_exit > 0 and shares_to_exit <= pos['shares_remaining']:
                    proceeds = shares_to_exit * target_price
                    self.capital += proceeds
                    
                    profit = (target_price - pos['entry_price']) * shares_to_exit if pos['type'] == 'BUY' else (pos['entry_price'] - target_price) * shares_to_exit
                    
                    exit_info = {
                        'time': current_time,
                        'target': target_name,
                        'price': target_price,
                        'shares': shares_to_exit,
                        'profit': profit
                    }
                    
                    pos['shares_remaining'] -= shares_to_exit
                    pos[f'{target_name}_hit'] = True
                    pos['partial_exits'].append(exit_info)
                    exits.append(exit_info)
                    
                    self.partial_exits.append(exit_info)
        
        return exits
    
    def close_position(self, exit_price: float, exit_time: datetime, reason: str):
        """Fecha posição completamente"""
        
        if self.position is None:
            return
        
        shares = self.position['shares_remaining']
        
        if shares > 0:
            proceeds = shares * exit_price
            self.capital += proceeds
        
        # Calcula P&L total (incluindo parciais)
        total_profit = sum([e['profit'] for e in self.position['partial_exits']])
        
        if shares > 0:
            if self.position['type'] == 'BUY':
                total_profit += (exit_price - self.position['entry_price']) * shares
            else:
                total_profit += (self.position['entry_price'] - exit_price) * shares
        
        return_pct = (total_profit / self.position['cost']) * 100
        
        trade = {
            'symbol': self.position['signal'].symbol,
            'type': self.position['type'],
            'entry_time': self.position['entry_time'],
            'entry_price': self.position['entry_price'],
            'exit_time': exit_time,
            'exit_price': exit_price,
            'shares_total': self.position['shares_total'],
            'profit': total_profit,
            'return_pct': return_pct,
            'exit_reason': reason,
            'risk': self.position['signal'].risk,
            'partial_exits': self.position['partial_exits'].copy(),
            'quality_score': self.position['signal'].quality_score,
            'targets_hit': len(self.position['partial_exits'])
        }
        
        self.trades.append(trade)
        self.position = None
        
    def update_trailing_stop(self, strategy: Wave3Enhanced, df_60min: pd.DataFrame, current_price: float):
        """Atualiza trailing stop"""
        
        if self.position is None:
            return
        
        new_stop = strategy.calculate_trailing_stop(
            df_60min,
            self.position['type'],
            self.position['entry_price'],
            self.position['stop_loss'],
            current_price
        )
        
        self.position['stop_loss'] = new_stop


async def run_enhanced_backtest(symbol: str,
                                start_date: str,
                                end_date: str,
                                initial_capital: float = 100000.0):
    """Executa backtest Wave3 Enhanced"""
    
    print(f"\n{'='*100}")
    print(f"BACKTEST WAVE3 ENHANCED: {symbol}")
    print(f"{'='*100}\n")
    
    # Carrega dados
    df_daily = await load_ohlcv_data(symbol, 'daily', start_date, end_date)
    df_60min = await load_ohlcv_data(symbol, '60min', start_date, end_date)
    
    if df_daily.empty or df_60min.empty:
        print(f"❌ Dados insuficientes")
        return None
    
    print(f"📊 Daily: {len(df_daily)} candles | 60min: {len(df_60min)} candles")
    
    # Inicializa estratégia Enhanced com parâmetros OTIMIZADOS
    strategy = Wave3Enhanced(
        mma_long=72,
        mma_short=17,
        min_candles_daily=17,
        min_candles_60min=9,  # ✅ Mais flexível
        target_levels=[(0.5, 1.0), (0.3, 1.5), (0.2, 2.5)],  # 🔥 OTIMIZADO: alvos realistas
        activate_trailing_after_rr=0.75,  # 🔥 OTIMIZADO: trailing mais agressivo
        volume_multiplier=1.1,  # 🔥 OTIMIZADO: volume menos restritivo
        min_atr_percentile=30,  # ✅ Filtro ATR
        use_rsi_filter=True,  # ✅ Filtro RSI
        use_macd_filter=True,  # ✅ Filtro MACD
        use_adx_filter=True,  # ✅ Filtro ADX
        min_adx=20,
        min_quality_score=65  # 🔥 OTIMIZADO: aceita apenas sinais premium
    )
    
    backtester = EnhancedBacktester(initial_capital=initial_capital)
    
    print("🔄 Executando backtest...\n")
    
    # Simula trading
    for i in range(72, len(df_daily)):
        current_daily_date = df_daily.index[i]
        
        df_daily_hist = df_daily.iloc[:i+1]
        df_60min_hist = df_60min[df_60min.index <= current_daily_date]
        
        if len(df_60min_hist) < 50:
            continue
        
        if backtester.position is not None:
            current_price = df_60min_hist.iloc[-1]['close']
            current_time = df_60min_hist.index[-1]
            
            # Verifica saídas parciais
            partial_exits = backtester.check_partial_exits(current_price, current_time)
            
            for exit_info in partial_exits:
                print(f"   🎯 {exit_info['time'].strftime('%Y-%m-%d')}: "
                      f"Parcial {exit_info['target']} @ R$ {exit_info['price']:.2f} "
                      f"({exit_info['shares']} shares, P&L: R$ {exit_info['profit']:,.2f})")
            
            # Atualiza trailing stop
            backtester.update_trailing_stop(strategy, df_60min_hist, current_price)
            
            pos = backtester.position
            
            # Verifica stop loss
            if pos['type'] == 'BUY' and current_price <= pos['stop_loss']:
                backtester.close_position(pos['stop_loss'], current_time, 'STOP_LOSS')
                
            elif pos['type'] == 'SELL' and current_price >= pos['stop_loss']:
                backtester.close_position(pos['stop_loss'], current_time, 'STOP_LOSS')
        
        else:
            # Busca novo sinal
            signal = strategy.generate_signal(df_daily_hist, df_60min_hist, symbol)
            
            if signal:
                backtester.open_position(signal)
                
                # Indicadores de confirmação
                confirmations = []
                if signal.volume_confirmed: confirmations.append('VOL')
                if signal.atr_confirmed: confirmations.append('ATR')
                if signal.rsi_confirmed: confirmations.append('RSI')
                if signal.macd_confirmed: confirmations.append('MACD')
                if signal.adx_confirmed: confirmations.append('ADX')
                
                print(f"   🚀 {signal.timestamp.strftime('%Y-%m-%d')}: {signal.signal_type} @ R$ {signal.entry_price:.2f}")
                print(f"      Stop: R$ {signal.stop_loss:.2f} | T1: {signal.target_1:.2f} | T2: {signal.target_2:.2f} | T3: {signal.target_3:.2f}")
                print(f"      Score: {signal.quality_score:.0f}/100 | Confirmações: {', '.join(confirmations)}")
                print(f"      RSI: {signal.indicators['rsi']:.1f} | ADX: {signal.indicators['adx']:.1f} | Vol: {signal.indicators['volume_ratio']:.2f}x\n")
    
    # Fecha posição final
    if backtester.position:
        final_price = df_60min.iloc[-1]['close']
        final_time = df_60min.index[-1]
        backtester.close_position(final_price, final_time, 'END_OF_PERIOD')
    
    # Calcula métricas
    if not backtester.trades:
        print("❌ Nenhum trade executado")
        return None
    
    trades = backtester.trades
    winning_trades = [t for t in trades if t['profit'] > 0]
    losing_trades = [t for t in trades if t['profit'] <= 0]
    
    metrics = {
        'initial_capital': initial_capital,
        'final_capital': backtester.capital,
        'total_return_pct': (backtester.capital / initial_capital - 1) * 100,
        'num_trades': len(trades),
        'winning_trades': len(winning_trades),
        'losing_trades': len(losing_trades),
        'win_rate': len(winning_trades) / len(trades) * 100 if trades else 0,
        'avg_quality_score': np.mean([t['quality_score'] for t in trades]),
        'avg_targets_hit': np.mean([t['targets_hit'] for t in trades]),
        'total_partial_exits': len(backtester.partial_exits),
        'trades': trades
    }
    
    print(f"\n{'='*100}")
    print("RESULTADOS WAVE3 ENHANCED")
    print(f"{'='*100}\n")
    
    print(f"💰 PERFORMANCE")
    print(f"   Capital Final:          R$ {metrics['final_capital']:>15,.2f}")
    print(f"   Retorno Total:          {metrics['total_return_pct']:>15.2f}%")
    print(f"   Trades:                 {metrics['num_trades']:>15}")
    print(f"   Win Rate:               {metrics['win_rate']:>15.1f}%")
    print(f"   Quality Score Médio:    {metrics['avg_quality_score']:>15.1f}/100")
    print(f"   Alvos Parciais Médios:  {metrics['avg_targets_hit']:>15.1f}")
    print(f"   Total Saídas Parciais:  {metrics['total_partial_exits']:>15}\n")
    
    return metrics


async def compare_strategies(symbols: List[str], start_date: str, end_date: str):
    """Compara Original vs Enhanced"""
    
    print("\n" + "="*100)
    print("COMPARAÇÃO: WAVE3 ORIGINAL vs ENHANCED")
    print("="*100)
    
    for symbol in symbols:
        metrics_enhanced = await run_enhanced_backtest(symbol, start_date, end_date)
        
        if metrics_enhanced:
            print(f"\n✅ {symbol}: Retorno {metrics_enhanced['total_return_pct']:.2f}% | "
                  f"Win Rate {metrics_enhanced['win_rate']:.1f}% | "
                  f"Score {metrics_enhanced['avg_quality_score']:.0f}/100 | "
                  f"Alvos Parciais: {metrics_enhanced['total_partial_exits']}")


async def main():
    symbols = ['PETR4', 'VALE3', 'ITUB4']
    start_date = '2024-01-01'
    end_date = '2025-12-30'
    
    await compare_strategies(symbols, start_date, end_date)


if __name__ == '__main__':
    asyncio.run(main())
