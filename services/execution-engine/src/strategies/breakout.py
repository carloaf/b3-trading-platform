"""
B3 Trading Platform - Breakout Strategy
=========================================
Estratégia de Rompimento.

Identifica rompimentos de suporte/resistência com confirmação de volume.

Sinais:
- BUY: Preço rompe resistência + Volume alto
- SELL: Preço rompe suporte + Volume alto
"""

from typing import Dict, List

import pandas as pd
import numpy as np

from .base_strategy import BaseStrategy, calculate_atr


class BreakoutStrategy(BaseStrategy):
    """
    Estratégia de Rompimento de Suporte/Resistência.
    
    Detecta rompimentos de níveis de preço significativos
    com confirmação de volume acima da média.
    """
    
    name = "breakout"
    description = "Rompimento de suporte/resistência com volume"
    version = "2.0.0"
    
    def default_params(self) -> Dict:
        return {
            "lookback_period": 20,
            "volume_mult": 1.5,
            "atr_period": 14,
            "atr_mult": 0.5,  # Margem para confirmar rompimento
            "sl_atr_mult": 2.0,
            "tp_atr_mult": 4.0
        }
    
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        
        # Suporte e Resistência
        df["resistance"] = df["high"].rolling(window=self.params["lookback_period"]).max()
        df["support"] = df["low"].rolling(window=self.params["lookback_period"]).min()
        
        # ATR
        df["atr"] = calculate_atr(df, self.params["atr_period"])
        
        # Volume
        df["volume_sma"] = df["volume"].rolling(window=20).mean()
        df["volume_ratio"] = df["volume"] / df["volume_sma"]
        
        # Distância do suporte/resistência
        df["dist_resistance"] = (df["resistance"] - df["close"]) / df["atr"]
        df["dist_support"] = (df["close"] - df["support"]) / df["atr"]
        
        return df
    
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["signal"] = "HOLD"
        df["signal_strength"] = 0.5
        df["signal_reason"] = ""
        
        margin = df["atr"] * self.params["atr_mult"]
        
        # Rompimento de alta
        breakout_up = (
            (df["close"] > df["resistance"].shift(1) + margin) &
            (df["close"].shift(1) <= df["resistance"].shift(1)) &
            (df["volume_ratio"] > self.params["volume_mult"])
        )
        
        # Rompimento de baixa
        breakout_down = (
            (df["close"] < df["support"].shift(1) - margin) &
            (df["close"].shift(1) >= df["support"].shift(1)) &
            (df["volume_ratio"] > self.params["volume_mult"])
        )
        
        df.loc[breakout_up, "signal"] = "BUY"
        df.loc[breakout_up, "signal_reason"] = "Rompimento de resistência + Volume alto"
        
        df.loc[breakout_down, "signal"] = "SELL"
        df.loc[breakout_down, "signal_reason"] = "Rompimento de suporte + Volume alto"
        
        # Força baseada no volume
        df.loc[breakout_up | breakout_down, "signal_strength"] = (
            0.5 + df.loc[breakout_up | breakout_down, "volume_ratio"].clip(1, 3) / 6
        )
        
        # Stop Loss e Take Profit
        df["stop_loss"] = np.where(
            df["signal"] == "BUY",
            df["resistance"].shift(1) - (df["atr"] * 0.5),
            np.where(
                df["signal"] == "SELL",
                df["support"].shift(1) + (df["atr"] * 0.5),
                np.nan
            )
        )
        
        df["take_profit"] = np.where(
            df["signal"] == "BUY",
            df["close"] + (df["atr"] * self.params["tp_atr_mult"]),
            np.where(
                df["signal"] == "SELL",
                df["close"] - (df["atr"] * self.params["tp_atr_mult"]),
                np.nan
            )
        )
        
        return df
    
    def get_entry_conditions(self) -> List[str]:
        return [
            f"Preço rompe resistência de {self.params['lookback_period']} períodos (BUY)",
            f"Preço rompe suporte de {self.params['lookback_period']} períodos (SELL)",
            f"Volume > {self.params['volume_mult']}x média",
            f"Margem de confirmação: {self.params['atr_mult']}x ATR"
        ]
    
    def get_exit_conditions(self) -> List[str]:
        return [
            "Stop Loss: Abaixo da resistência rompida (BUY) / Acima do suporte rompido (SELL)",
            f"Take Profit: {self.params['tp_atr_mult']}x ATR",
            "Retorno ao nível rompido (falso rompimento)"
        ]


def create_breakout_strategy(params: Dict = None) -> BreakoutStrategy:
    """Factory function para criar instância da estratégia."""
    return BreakoutStrategy(params)
