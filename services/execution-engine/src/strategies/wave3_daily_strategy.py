"""
Wave3 Daily Strategy - Versão Simplificada
B3 Trading Platform

Versão da estratégia Wave3 que funciona apenas com dados diários,
sem necessidade de dados intraday de 60min.

Adaptações:
- Setup identificado no próprio gráfico diário
- Pivôs de alta/baixa no daily
- Contexto e gatilho no mesmo timeframe
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from loguru import logger


class Wave3DailyStrategy:
    """
    Wave3 Strategy simplificada para operar apenas com dados diários.
    
    Mantém os princípios:
    - MME 72 + MME 17
    - Regra dos 17 candles
    - Zona de entrada (±1% entre MMEs)
    - Estrutura de topos/fundos ascendentes
    - Risk:Reward 1:3
    """
    
    def __init__(
        self,
        ema_long: int = 72,
        ema_short: int = 17,
        zone_tolerance: float = 0.01,
        min_candles_validation: int = 17,
        risk_percent: float = 0.06,
        reward_ratio: float = 3.0
    ):
        self.ema_long = ema_long
        self.ema_short = ema_short
        self.zone_tolerance = zone_tolerance
        self.min_candles_validation = min_candles_validation
        self.risk_percent = risk_percent
        self.reward_ratio = reward_ratio
        
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calcula indicadores no gráfico diário."""
        df = df.copy()
        
        # MMEs
        df['ema_long'] = df['close'].ewm(span=self.ema_long, adjust=False).mean()
        df['ema_short'] = df['close'].ewm(span=self.ema_short, adjust=False).mean()
        
        # Zona de entrada
        df['zone_upper'] = df[['ema_long', 'ema_short']].max(axis=1) * (1 + self.zone_tolerance)
        df['zone_lower'] = df[['ema_long', 'ema_short']].min(axis=1) * (1 - self.zone_tolerance)
        
        # Direção da tendência
        df['trend'] = np.where(df['close'] > df['ema_long'], 1, -1)
        
        # In zone
        df['in_zone'] = (
            (df['close'] >= df['zone_lower']) & 
            (df['close'] <= df['zone_upper'])
        )
        
        # Distância das MMEs
        df['dist_ema_long'] = (df['close'] - df['ema_long']) / df['ema_long']
        
        # ATR para stop loss
        df['atr'] = self._calculate_atr(df, 14)
        
        return df
    
    def _calculate_atr(self, df: pd.DataFrame, period: int) -> pd.Series:
        """Calcula ATR."""
        high_low = df['high'] - df['low']
        high_close = abs(df['high'] - df['close'].shift(1))
        low_close = abs(df['low'] - df['close'].shift(1))
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        return true_range.rolling(window=period).mean()
    
    def identify_swing_points(self, df: pd.DataFrame) -> pd.DataFrame:
        """Identifica swing points com regra dos 17 candles."""
        df = df.copy()
        window = self.min_candles_validation
        
        # Pivot Highs
        df['pivot_high'] = df['high'].rolling(window=window*2+1, center=True).apply(
            lambda x: x[window] if len(x) == window*2+1 and x[window] == x.max() else np.nan,
            raw=True
        )
        
        # Pivot Lows
        df['pivot_low'] = df['low'].rolling(window=window*2+1, center=True).apply(
            lambda x: x[window] if len(x) == window*2+1 and x[window] == x.min() else np.nan,
            raw=True
        )
        
        # Higher Highs / Higher Lows
        df['higher_high'] = False
        df['higher_low'] = False
        
        pivot_highs = df[df['pivot_high'].notna()]['pivot_high']
        pivot_lows = df[df['pivot_low'].notna()]['pivot_low']
        
        for i in range(1, len(pivot_highs)):
            if pivot_highs.iloc[i] > pivot_highs.iloc[i-1]:
                df.loc[pivot_highs.index[i], 'higher_high'] = True
        
        for i in range(1, len(pivot_lows)):
            if pivot_lows.iloc[i] > pivot_lows.iloc[i-1]:
                df.loc[pivot_lows.index[i], 'higher_low'] = True
        
        return df
    
    def generate_signals(self, df: pd.DataFrame) -> List[Dict]:
        """
        Gera sinais de compra baseados em:
        1. Preço na zona de entrada
        2. Tendência de alta (acima MME 72)
        3. Higher low confirmado
        4. Breakout do último pivot high
        """
        df = self.calculate_indicators(df)
        df = self.identify_swing_points(df)
        
        signals = []
        
        for i in range(self.ema_long + 50, len(df)):
            row = df.iloc[i]
            
            # Verificar condições
            if not row['in_zone']:
                continue
            
            if row['trend'] != 1:  # Apenas compras
                continue
            
            # Buscar higher low recente (últimos 30 dias)
            recent_df = df.iloc[max(0, i-30):i+1]
            has_higher_low = recent_df['higher_low'].any()
            
            if not has_higher_low:
                continue
            
            # Buscar último pivot low para stop
            pivot_lows = recent_df[recent_df['pivot_low'].notna()]
            if len(pivot_lows) == 0:
                continue
            
            last_pivot_low = pivot_lows.iloc[-1]['pivot_low']
            
            # Stop loss: 0.5% abaixo do último pivot low
            stop_loss = last_pivot_low * 0.995
            
            # Risk
            risk_distance = (row['close'] - stop_loss) / row['close']
            
            if risk_distance > 0.10:  # Risco máximo de 10%
                continue
            
            # Take profit: 3x o risco
            take_profit = row['close'] * (1 + risk_distance * self.reward_ratio)
            
            signal = {
                'date': row.name,
                'type': 'BUY',
                'entry_price': row['close'],
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'risk_pct': risk_distance * 100,
                'reward_pct': risk_distance * self.reward_ratio * 100,
                'ema_long': row['ema_long'],
                'ema_short': row['ema_short'],
                'in_zone': row['in_zone']
            }
            
            signals.append(signal)
        
        return signals
    
    def backtest(
        self,
        df: pd.DataFrame,
        initial_capital: float = 100000.0
    ) -> Dict:
        """
        Executa backtest da estratégia.
        
        Simula execução de trades com base nos sinais gerados,
        calculando resultado de cada trade até atingir SL ou TP.
        """
        signals = self.generate_signals(df)
        
        if len(signals) == 0:
            return {
                'total_trades': 0,
                'total_return': 0.0,
                'message': 'Nenhum sinal gerado no período'
            }
        
        capital = initial_capital
        trades = []
        
        for signal in signals:
            entry_date = signal['date']
            entry_price = signal['entry_price']
            stop_loss = signal['stop_loss']
            take_profit = signal['take_profit']
            
            # Position sizing baseado no risco
            risk_amount = capital * self.risk_percent
            shares = risk_amount / (entry_price - stop_loss)
            position_value = shares * entry_price
            
            # Simular resultado do trade
            # Pegar dados após a entrada
            entry_idx = df.index.get_loc(entry_date)
            future_df = df.iloc[entry_idx+1:min(entry_idx+60, len(df))]  # Próximos 60 dias
            
            if len(future_df) == 0:
                continue
            
            # Verificar se atingiu SL ou TP
            hit_sl = (future_df['low'] <= stop_loss).any()
            hit_tp = (future_df['high'] >= take_profit).any()
            
            # Determinar qual foi atingido primeiro
            if hit_sl and hit_tp:
                sl_date = future_df[future_df['low'] <= stop_loss].index[0]
                tp_date = future_df[future_df['high'] >= take_profit].index[0]
                
                if sl_date < tp_date:
                    result = 'LOSS'
                    exit_price = stop_loss
                    exit_date = sl_date
                else:
                    result = 'WIN'
                    exit_price = take_profit
                    exit_date = tp_date
            elif hit_sl:
                result = 'LOSS'
                exit_price = stop_loss
                exit_date = future_df[future_df['low'] <= stop_loss].index[0]
            elif hit_tp:
                result = 'WIN'
                exit_price = take_profit
                exit_date = future_df[future_df['high'] >= take_profit].index[0]
            else:
                # Não atingiu nenhum, sair no último preço
                result = 'NEUTRAL'
                exit_price = future_df.iloc[-1]['close']
                exit_date = future_df.index[-1]
            
            # Calcular P&L
            pnl = shares * (exit_price - entry_price)
            pnl_pct = (exit_price - entry_price) / entry_price * 100
            
            capital += pnl
            
            trade = {
                'entry_date': entry_date,
                'entry_price': entry_price,
                'exit_date': exit_date,
                'exit_price': exit_price,
                'shares': shares,
                'position_value': position_value,
                'pnl': pnl,
                'pnl_pct': pnl_pct,
                'result': result,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'days_held': (exit_date - entry_date).days
            }
            
            trades.append(trade)
        
        # Calcular métricas
        winning_trades = [t for t in trades if t['result'] == 'WIN']
        losing_trades = [t for t in trades if t['result'] == 'LOSS']
        
        total_trades = len(trades)
        win_count = len(winning_trades)
        loss_count = len(losing_trades)
        win_rate = win_count / total_trades if total_trades > 0 else 0
        
        avg_win = np.mean([t['pnl'] for t in winning_trades]) if winning_trades else 0
        avg_loss = np.mean([abs(t['pnl']) for t in losing_trades]) if losing_trades else 0
        profit_factor = abs(avg_win / avg_loss) if avg_loss != 0 else 0
        
        total_pnl = sum(t['pnl'] for t in trades)
        total_return = (capital - initial_capital) / initial_capital * 100
        
        return {
            'total_trades': total_trades,
            'winning_trades': win_count,
            'losing_trades': loss_count,
            'win_rate': round(win_rate * 100, 2),
            'total_pnl': round(total_pnl, 2),
            'total_return': round(total_return, 2),
            'profit_factor': round(profit_factor, 2),
            'avg_win': round(avg_win, 2),
            'avg_loss': round(avg_loss, 2),
            'initial_capital': initial_capital,
            'final_capital': round(capital, 2),
            'trades': trades
        }
