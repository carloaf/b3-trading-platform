"""
B3 Trading Platform - Trend Following Strategy
================================================
Estratégia de Seguimento de Tendência.

Usa EMA 9/21 + RSI + Volume para identificar e seguir tendências.

Sinais:
- BUY: EMA rápida cruza EMA lenta para cima + RSI não sobrecomprado + Volume alto
- SELL: EMA rápida cruza EMA lenta para baixo + RSI não sobrevendido + Volume alto
"""

from typing import Dict, List

import pandas as pd
import numpy as np

from .base_strategy import (
    BaseStrategy,
    calculate_atr,
    calculate_rsi,
    calculate_ema
)


class TrendFollowingStrategy(BaseStrategy):
    """
    Estratégia de Seguimento de Tendência.
    
    Identifica tendências usando cruzamento de EMAs confirmado
    por RSI e volume acima da média.
    """
    
    name = "trend_following"
    description = "Seguidor de tendência com EMA 9/21 + RSI + Volume"
    version = "2.0.0"
    
    def default_params(self) -> Dict:
        return {
            "ema_fast": 9,
            "ema_slow": 21,
            "rsi_period": 14,
            "rsi_oversold": 30,
            "rsi_overbought": 70,
            "volume_mult": 1.2,
            "atr_period": 14,
            "sl_atr_mult": 2.0,
            "tp_atr_mult": 3.0
        }
    
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        
        # EMAs
        df["ema_fast"] = calculate_ema(df["close"], self.params["ema_fast"])
        df["ema_slow"] = calculate_ema(df["close"], self.params["ema_slow"])
        
        # RSI
        df["rsi"] = calculate_rsi(df["close"], self.params["rsi_period"])
        
        # ATR
        df["atr"] = calculate_atr(df, self.params["atr_period"])
        
        # Volume SMA
        df["volume_sma"] = df["volume"].rolling(window=20).mean()
        df["volume_ratio"] = df["volume"] / df["volume_sma"]
        
        # Tendência
        df["trend"] = np.where(df["ema_fast"] > df["ema_slow"], 1, -1)
        
        return df
    
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["signal"] = "HOLD"
        df["signal_strength"] = 0.5
        df["signal_reason"] = ""
        
        # Condições de compra
        buy_condition = (
            (df["ema_fast"] > df["ema_slow"]) &
            (df["ema_fast"].shift(1) <= df["ema_slow"].shift(1)) &
            (df["rsi"] < self.params["rsi_overbought"]) &
            (df["volume_ratio"] > self.params["volume_mult"])
        )
        
        # Condições de venda
        sell_condition = (
            (df["ema_fast"] < df["ema_slow"]) &
            (df["ema_fast"].shift(1) >= df["ema_slow"].shift(1)) &
            (df["rsi"] > self.params["rsi_oversold"]) &
            (df["volume_ratio"] > self.params["volume_mult"])
        )
        
        df.loc[buy_condition, "signal"] = "BUY"
        df.loc[buy_condition, "signal_reason"] = "EMA crossover bullish + Volume alto"
        
        df.loc[sell_condition, "signal"] = "SELL"
        df.loc[sell_condition, "signal_reason"] = "EMA crossover bearish + Volume alto"
        
        # Força do sinal baseada em RSI
        df.loc[buy_condition, "signal_strength"] = 0.5 + (50 - df.loc[buy_condition, "rsi"]) / 100
        df.loc[sell_condition, "signal_strength"] = 0.5 + (df.loc[sell_condition, "rsi"] - 50) / 100
        
        # Stop Loss e Take Profit
        df["stop_loss"] = np.where(
            df["signal"] == "BUY",
            df["close"] - (df["atr"] * self.params["sl_atr_mult"]),
            np.where(
                df["signal"] == "SELL",
                df["close"] + (df["atr"] * self.params["sl_atr_mult"]),
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
            f"EMA{self.params['ema_fast']} cruza EMA{self.params['ema_slow']} para cima (BUY)",
            f"EMA{self.params['ema_fast']} cruza EMA{self.params['ema_slow']} para baixo (SELL)",
            f"RSI < {self.params['rsi_overbought']} para BUY",
            f"RSI > {self.params['rsi_oversold']} para SELL",
            f"Volume > {self.params['volume_mult']}x média"
        ]
    
    def get_exit_conditions(self) -> List[str]:
        return [
            f"Stop Loss: {self.params['sl_atr_mult']}x ATR",
            f"Take Profit: {self.params['tp_atr_mult']}x ATR",
            "Cruzamento oposto de EMAs"
        ]


def create_trend_following_strategy(params: Dict = None) -> TrendFollowingStrategy:
    """Factory function para criar instância da estratégia."""
    return TrendFollowingStrategy(params)
