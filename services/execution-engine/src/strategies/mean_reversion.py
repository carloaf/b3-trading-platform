"""
B3 Trading Platform - Mean Reversion Strategy
===============================================
Estratégia de Reversão à Média.

Usa Bollinger Bands + RSI para identificar extremos e reversões.

Sinais:
- BUY: Preço abaixo da banda inferior + RSI sobrevendido
- SELL: Preço acima da banda superior + RSI sobrecomprado
"""

from typing import Dict, List

import pandas as pd
import numpy as np

from .base_strategy import (
    BaseStrategy,
    calculate_atr,
    calculate_rsi,
    calculate_bollinger_bands
)


class MeanReversionStrategy(BaseStrategy):
    """
    Estratégia de Reversão à Média.
    
    Identifica condições de sobrevenda/sobrecompra usando
    Bollinger Bands e RSI, esperando reversão ao preço médio.
    """
    
    name = "mean_reversion"
    description = "Reversão à média com Bollinger Bands + RSI"
    version = "2.0.0"
    
    def default_params(self) -> Dict:
        return {
            "bb_period": 20,
            "bb_std": 2.0,
            "rsi_period": 14,
            "rsi_oversold": 25,
            "rsi_overbought": 75,
            "atr_period": 14,
            "sl_atr_mult": 1.5,
            "tp_atr_mult": 2.0
        }
    
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        
        # Bollinger Bands
        df["bb_upper"], df["bb_middle"], df["bb_lower"] = calculate_bollinger_bands(
            df["close"], 
            period=self.params["bb_period"],
            std_dev=self.params["bb_std"]
        )
        df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / df["bb_middle"]
        df["bb_pct"] = (df["close"] - df["bb_lower"]) / (df["bb_upper"] - df["bb_lower"])
        
        # RSI
        df["rsi"] = calculate_rsi(df["close"], self.params["rsi_period"])
        
        # ATR
        df["atr"] = calculate_atr(df, self.params["atr_period"])
        
        return df
    
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["signal"] = "HOLD"
        df["signal_strength"] = 0.5
        df["signal_reason"] = ""
        
        # Compra: preço abaixo da banda inferior + RSI sobrevendido
        buy_condition = (
            (df["close"] < df["bb_lower"]) &
            (df["rsi"] < self.params["rsi_oversold"])
        )
        
        # Venda: preço acima da banda superior + RSI sobrecomprado
        sell_condition = (
            (df["close"] > df["bb_upper"]) &
            (df["rsi"] > self.params["rsi_overbought"])
        )
        
        df.loc[buy_condition, "signal"] = "BUY"
        df.loc[buy_condition, "signal_reason"] = "Preço abaixo BB inferior + RSI sobrevendido"
        
        df.loc[sell_condition, "signal"] = "SELL"
        df.loc[sell_condition, "signal_reason"] = "Preço acima BB superior + RSI sobrecomprado"
        
        # Força baseada na distância das bandas
        df.loc[buy_condition, "signal_strength"] = 0.5 + (1 - df.loc[buy_condition, "bb_pct"].clip(0, 1)) * 0.5
        df.loc[sell_condition, "signal_strength"] = 0.5 + df.loc[sell_condition, "bb_pct"].clip(0, 1) * 0.5
        
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
            df["bb_middle"],  # Alvo: média (middle band)
            np.where(
                df["signal"] == "SELL",
                df["bb_middle"],
                np.nan
            )
        )
        
        return df
    
    def get_entry_conditions(self) -> List[str]:
        return [
            f"Preço < Bollinger Band inferior (BUY)",
            f"Preço > Bollinger Band superior (SELL)",
            f"RSI < {self.params['rsi_oversold']} para BUY",
            f"RSI > {self.params['rsi_overbought']} para SELL",
            f"Bollinger Bands: {self.params['bb_period']} períodos, {self.params['bb_std']} desvios"
        ]
    
    def get_exit_conditions(self) -> List[str]:
        return [
            f"Stop Loss: {self.params['sl_atr_mult']}x ATR",
            "Take Profit: Retorno à média (Middle Band)",
            "RSI normaliza para zona neutra"
        ]


def create_mean_reversion_strategy(params: Dict = None) -> MeanReversionStrategy:
    """Factory function para criar instância da estratégia."""
    return MeanReversionStrategy(params)
