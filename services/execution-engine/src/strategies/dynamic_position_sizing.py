"""
B3 Trading Platform - Dynamic Position Sizing Strategy
========================================================
Estratégia de Dimensionamento Dinâmico de Posição com Kelly Criterion

Esta estratégia implementa:

1. **Kelly Criterion Modificado**:
   - Fórmula: f* = (bp - q) / b
   - Onde: b = ganho médio/perda média, p = win rate, q = 1-p
   - Usa 50% do Kelly (Half Kelly) para ser mais conservador

2. **Position Sizing baseado em ATR**:
   - Ajusta tamanho baseado na volatilidade atual
   - Maior volatilidade = menor posição
   - Menor volatilidade = maior posição

3. **Gestão de Risco**:
   - Risco máximo por trade configurável (default: 2%)
   - Position size máximo (default: 25% do capital)
   - Stop Loss e Take Profit dinâmicos baseados em ATR

DISCLAIMER: Esta estratégia é para fins educacionais.
Gestão de risco adequada é fundamental para preservação de capital.
"""

from typing import Dict, List, Any, Optional

import pandas as pd
import numpy as np
from loguru import logger

from .base_strategy import (
    BaseStrategy,
    calculate_atr,
    calculate_rsi,
    calculate_ema,
    calculate_bollinger_bands
)


class DynamicPositionSizingStrategy(BaseStrategy):
    """
    Estratégia de Dimensionamento Dinâmico de Posição.
    
    Usa Kelly Criterion e ATR para calcular o tamanho ideal de posição
    baseado em volatilidade e performance histórica.
    
    Features:
    - Kelly Criterion para sizing ótimo
    - Ajuste por volatilidade (ATR)
    - Limites de risco configuráveis
    - Sinais baseados em EMA crossover + RSI
    """
    
    name = "dynamic_position_sizing"
    description = "Position Sizing dinâmico com Kelly Criterion + ATR"
    version = "2.0.0"
    
    def default_params(self) -> Dict:
        return {
            # Gestão de risco
            'risk_per_trade': 0.02,  # 2% de risco por trade
            'max_position_size': 0.25,  # Máximo 25% do capital por posição
            'kelly_fraction': 0.5,  # Usar 50% do Kelly (Half Kelly)
            
            # ATR
            'atr_period': 14,
            'atr_multiplier': 2.0,
            
            # EMAs para sinais
            'ema_fast': 20,
            'ema_slow': 50,
            
            # RSI
            'rsi_period': 14,
            'rsi_lower': 40,
            'rsi_upper': 70,
            
            # Stop/Take Profit
            'sl_atr_mult': 2.0,
            'tp_atr_mult': 3.0,
        }
    
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calcula ATR, EMAs, RSI e Bollinger Bands para análise de volatilidade.
        """
        df = df.copy()
        
        # ATR para medir volatilidade
        df['atr'] = calculate_atr(df, self.params['atr_period'])
        
        # ATR percentual (volatilidade normalizada)
        df['atr_pct'] = (df['atr'] / df['close']) * 100
        
        # Bollinger Bands Width (outra medida de volatilidade)
        bb_upper, bb_middle, bb_lower = calculate_bollinger_bands(df['close'])
        df['bb_upper'] = bb_upper
        df['bb_middle'] = bb_middle
        df['bb_lower'] = bb_lower
        df['bb_width'] = (bb_upper - bb_lower) / bb_middle
        
        # EMAs para tendência
        df['ema_fast'] = calculate_ema(df['close'], self.params['ema_fast'])
        df['ema_slow'] = calculate_ema(df['close'], self.params['ema_slow'])
        
        # RSI para timing
        df['rsi'] = calculate_rsi(df['close'], self.params['rsi_period'])
        
        # Tendência
        df['trend'] = np.where(df['ema_fast'] > df['ema_slow'], 1, -1)
        
        return df
    
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Gera sinais E calcula tamanho da posição dinamicamente.
        """
        df = df.copy()
        
        df['signal'] = 'HOLD'
        df['signal_strength'] = 0.5
        df['position_size'] = 0.0
        df['stop_loss'] = np.nan
        df['take_profit'] = np.nan
        df['signal_reason'] = ''
        
        # Sinais básicos de entrada (EMA crossover + RSI)
        buy_condition = (
            (df['ema_fast'] > df['ema_slow']) &
            (df['ema_fast'].shift(1) <= df['ema_slow'].shift(1)) &  # Cruzamento
            (df['rsi'] > self.params['rsi_lower']) & 
            (df['rsi'] < self.params['rsi_upper'])
        )
        
        sell_condition = (
            (df['ema_fast'] < df['ema_slow']) &
            (df['ema_fast'].shift(1) >= df['ema_slow'].shift(1)) &  # Cruzamento
            (df['rsi'] > 100 - self.params['rsi_upper'])
        )
        
        df.loc[buy_condition, 'signal'] = 'BUY'
        df.loc[buy_condition, 'signal_reason'] = 'EMA crossover bullish + RSI em range'
        
        df.loc[sell_condition, 'signal'] = 'SELL'
        df.loc[sell_condition, 'signal_reason'] = 'EMA crossover bearish + RSI elevado'
        
        # Calcular tamanho de posição dinâmico para cada candle
        df['position_size'] = self._calculate_position_sizes(df)
        
        # Calcular força do sinal baseada em múltiplos fatores
        df['signal_strength'] = self._calculate_signal_strength(df)
        
        # Stop-loss e Take-profit baseados em ATR
        for idx in df.index:
            if df.loc[idx, 'signal'] == 'BUY':
                atr = df.loc[idx, 'atr'] if pd.notna(df.loc[idx, 'atr']) else 0
                df.loc[idx, 'stop_loss'] = df.loc[idx, 'close'] - (self.params['sl_atr_mult'] * atr)
                df.loc[idx, 'take_profit'] = df.loc[idx, 'close'] + (self.params['tp_atr_mult'] * atr)
            elif df.loc[idx, 'signal'] == 'SELL':
                atr = df.loc[idx, 'atr'] if pd.notna(df.loc[idx, 'atr']) else 0
                df.loc[idx, 'stop_loss'] = df.loc[idx, 'close'] + (self.params['sl_atr_mult'] * atr)
                df.loc[idx, 'take_profit'] = df.loc[idx, 'close'] - (self.params['tp_atr_mult'] * atr)
        
        return df
    
    def _calculate_position_sizes(self, df: pd.DataFrame) -> pd.Series:
        """
        Calcula tamanho de posição usando Kelly Criterion simplificado.
        
        Fórmula: Position Size = (Risk per Trade) / (ATR * Multiplier / Price)
        
        Ajustes:
        - Volatilidade alta → posição menor
        - Volatilidade baixa → posição maior
        - Limitar ao máximo permitido
        """
        risk_per_trade = self.params['risk_per_trade']
        atr_multiplier = self.params['atr_multiplier']
        max_position = self.params['max_position_size']
        
        # Calcular risco por unidade (em percentual do preço)
        # risk_per_unit = quanto o preço pode mover contra nós (ATR * mult) / preço atual
        risk_per_unit = (df['atr'] * atr_multiplier) / df['close']
        
        # Evitar divisão por zero
        risk_per_unit = risk_per_unit.replace(0, np.nan).fillna(0.01)
        
        # Tamanho da posição = risco desejado / risco por unidade
        position_size = risk_per_trade / risk_per_unit
        
        # Limitar ao máximo permitido
        position_size = np.minimum(position_size, max_position)
        
        # Ajustar pela volatilidade (reduzir posição em alta volatilidade)
        # atr_pct médio histórico ~ 2%, se maior que isso, reduzir
        volatility_adjustment = 1 / (1 + df['atr_pct'] / 5)
        position_size = position_size * volatility_adjustment
        
        # Garantir que está entre 0 e max_position
        position_size = np.clip(position_size, 0, max_position)
        
        return position_size
    
    def _calculate_signal_strength(self, df: pd.DataFrame) -> pd.Series:
        """
        Calcula a força do sinal baseada em múltiplos fatores.
        """
        strength = pd.Series(0.5, index=df.index)
        
        # Aumentar força se RSI está em zona favorável
        rsi_strength = pd.Series(0.0, index=df.index)
        
        # Para BUY: RSI baixo é melhor
        buy_mask = df['signal'] == 'BUY'
        rsi_strength.loc[buy_mask] = (50 - df.loc[buy_mask, 'rsi'].clip(0, 50)) / 50 * 0.3
        
        # Para SELL: RSI alto é melhor
        sell_mask = df['signal'] == 'SELL'
        rsi_strength.loc[sell_mask] = (df.loc[sell_mask, 'rsi'].clip(50, 100) - 50) / 50 * 0.3
        
        # Força da tendência (distância entre EMAs)
        ema_diff = (df['ema_fast'] - df['ema_slow']).abs() / df['close']
        trend_strength = (ema_diff * 10).clip(0, 0.2)
        
        strength = 0.5 + rsi_strength + trend_strength
        
        return strength.clip(0.0, 1.0)
    
    @staticmethod
    def calculate_kelly_criterion(
        win_rate: float,
        avg_win: float,
        avg_loss: float,
        kelly_fraction: float = 0.5
    ) -> float:
        """
        Calcula Kelly Criterion para tamanho ótimo de posição.
        
        Args:
            win_rate: Taxa de acerto (0 a 1).
            avg_win: Ganho médio por trade vencedor.
            avg_loss: Perda média por trade perdedor (valor positivo).
            kelly_fraction: Fração do Kelly a usar (0.5 = Half Kelly).
            
        Returns:
            Fração do capital a arriscar (0 a 1).
            
        Example:
            >>> kelly = DynamicPositionSizingStrategy.calculate_kelly_criterion(
            ...     win_rate=0.55,
            ...     avg_win=100,
            ...     avg_loss=80,
            ...     kelly_fraction=0.5
            ... )
            >>> print(f"Kelly: {kelly:.2%}")
        """
        if avg_loss == 0 or win_rate <= 0 or win_rate >= 1:
            return 0.0
        
        # Kelly Criterion: f* = (bp - q) / b
        # onde: b = avg_win/avg_loss, p = win_rate, q = 1-p
        b = avg_win / abs(avg_loss)
        p = win_rate
        q = 1 - p
        
        kelly_pct = (b * p - q) / b
        
        # Aplicar fração do Kelly (mais conservador)
        kelly_pct = kelly_pct * kelly_fraction
        
        # Limitar entre 0 e 25%
        kelly_pct = np.clip(kelly_pct, 0, 0.25)
        
        logger.info(
            f"Kelly Criterion: {kelly_pct:.2%} "
            f"(Win Rate: {win_rate:.2%}, Avg Win: {avg_win:.2f}, Avg Loss: {avg_loss:.2f})"
        )
        
        return float(kelly_pct)
    
    @staticmethod
    def calculate_optimal_position_size(
        account_balance: float,
        entry_price: float,
        stop_loss_price: float,
        risk_per_trade: float = 0.02,
        max_position_pct: float = 0.25
    ) -> Dict[str, float]:
        """
        Calcula o tamanho ótimo de posição baseado no risco.
        
        Args:
            account_balance: Saldo total da conta.
            entry_price: Preço de entrada.
            stop_loss_price: Preço do stop loss.
            risk_per_trade: Percentual de risco por trade (default: 2%).
            max_position_pct: Tamanho máximo da posição (default: 25%).
            
        Returns:
            Dicionário com informações de sizing.
            
        Example:
            >>> sizing = DynamicPositionSizingStrategy.calculate_optimal_position_size(
            ...     account_balance=10000,
            ...     entry_price=100,
            ...     stop_loss_price=95,
            ...     risk_per_trade=0.02
            ... )
            >>> print(f"Quantidade: {sizing['quantity']:.2f}")
        """
        # Calcular distância até o stop loss
        stop_distance = abs(entry_price - stop_loss_price)
        stop_distance_pct = stop_distance / entry_price
        
        if stop_distance == 0:
            return {
                'quantity': 0,
                'position_value': 0,
                'risk_amount': 0,
                'position_pct': 0,
                'error': 'Stop loss igual ao preço de entrada'
            }
        
        # Valor em risco
        risk_amount = account_balance * risk_per_trade
        
        # Quantidade baseada no risco
        quantity = risk_amount / stop_distance
        
        # Valor da posição
        position_value = quantity * entry_price
        
        # Verificar limite máximo
        max_position_value = account_balance * max_position_pct
        
        if position_value > max_position_value:
            position_value = max_position_value
            quantity = position_value / entry_price
            risk_amount = quantity * stop_distance
        
        position_pct = position_value / account_balance
        
        return {
            'quantity': float(quantity),
            'position_value': float(position_value),
            'risk_amount': float(risk_amount),
            'risk_pct': float(risk_amount / account_balance),
            'position_pct': float(position_pct),
            'stop_distance': float(stop_distance),
            'stop_distance_pct': float(stop_distance_pct),
        }
    
    def analyze_risk(self, df: pd.DataFrame, account_balance: float = 10000.0) -> Dict[str, Any]:
        """
        Analisa o risco atual da estratégia.
        
        Args:
            df: DataFrame com dados e sinais.
            account_balance: Saldo da conta.
            
        Returns:
            Análise de risco detalhada.
        """
        if df.empty or 'position_size' not in df.columns:
            return {"error": "Dados insuficientes"}
        
        last_row = df.iloc[-1]
        
        position_value = account_balance * last_row['position_size']
        risk_amount = position_value * self.params['risk_per_trade']
        
        # Calcular risk/reward ratio
        sl = last_row.get('stop_loss', np.nan)
        tp = last_row.get('take_profit', np.nan)
        close = last_row['close']
        
        if pd.notna(sl) and pd.notna(tp) and (close - sl) != 0:
            risk_reward = abs(tp - close) / abs(close - sl)
        else:
            risk_reward = 0
        
        return {
            "current_price": float(last_row['close']),
            "atr": float(last_row['atr']) if pd.notna(last_row['atr']) else 0,
            "atr_pct": float(last_row['atr_pct']) if pd.notna(last_row['atr_pct']) else 0,
            "recommended_position_size_pct": float(last_row['position_size'] * 100),
            "position_value": float(position_value),
            "risk_per_trade": float(risk_amount),
            "stop_loss": float(sl) if pd.notna(sl) else None,
            "take_profit": float(tp) if pd.notna(tp) else None,
            "risk_reward_ratio": float(risk_reward),
            "account_balance": float(account_balance),
            "volatility_level": self._get_volatility_level(last_row),
        }
    
    def _get_volatility_level(self, row: pd.Series) -> str:
        """Classifica o nível de volatilidade."""
        atr_pct = row.get('atr_pct', 0)
        if pd.isna(atr_pct):
            return 'unknown'
        
        if atr_pct < 1.0:
            return 'low'
        elif atr_pct < 2.5:
            return 'medium'
        elif atr_pct < 4.0:
            return 'high'
        else:
            return 'extreme'
    
    def get_entry_conditions(self) -> List[str]:
        return [
            f"EMA{self.params['ema_fast']} > EMA{self.params['ema_slow']} (tendência de alta)",
            f"RSI entre {self.params['rsi_lower']}-{self.params['rsi_upper']}",
            "Tamanho de posição ajustado por volatilidade (ATR)",
            f"Risco máximo: {self.params['risk_per_trade']*100}% por trade"
        ]
    
    def get_exit_conditions(self) -> List[str]:
        return [
            f"EMA{self.params['ema_fast']} < EMA{self.params['ema_slow']}",
            f"RSI > {100 - self.params['rsi_upper']}",
            f"Stop-loss: {self.params['sl_atr_mult']}x ATR",
            f"Take-profit: {self.params['tp_atr_mult']}x ATR"
        ]


def create_dynamic_position_sizing_strategy(params: Dict[str, Any] = None) -> DynamicPositionSizingStrategy:
    """Factory function para criar instância da estratégia."""
    return DynamicPositionSizingStrategy(params)
