"""
B3 Trading Platform - MACD Crossover Strategy
===============================================
Estratégia de Cruzamento MACD.

Usa MACD + Volume para confirmar sinais de reversão de tendência.

Sinais:
- BUY: MACD cruza linha de sinal para cima + histograma positivo + Volume alto
- SELL: MACD cruza linha de sinal para baixo + histograma negativo + Volume alto
"""

from typing import Dict, List

import pandas as pd
import numpy as np

from .base_strategy import BaseStrategy, calculate_atr, calculate_macd


class MACDCrossoverStrategy(BaseStrategy):
    """
    Estratégia de Cruzamento MACD.
    
    Detecta cruzamentos da linha MACD com a linha de sinal,
    confirmados por volume acima da média.
    """
    
    name = "macd_crossover"
    description = "Cruzamento MACD com confirmação de volume"
    version = "2.0.0"
    
    def default_params(self) -> Dict:
        return {
            "macd_fast": 12,
            "macd_slow": 26,
            "macd_signal": 9,
            "volume_sma": 20,
            "volume_mult": 1.2,
            "atr_period": 14,
            "sl_atr_mult": 2.0,
            "tp_atr_mult": 3.0
        }
    
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        
        # MACD
        df["macd_line"], df["macd_signal"], df["macd_histogram"] = calculate_macd(
            df["close"],
            fast=self.params["macd_fast"],
            slow=self.params["macd_slow"],
            signal=self.params["macd_signal"]
        )
        
        # ATR
        df["atr"] = calculate_atr(df, self.params["atr_period"])
        
        # Volume
        df["volume_sma"] = df["volume"].rolling(window=self.params["volume_sma"]).mean()
        df["volume_ratio"] = df["volume"] / df["volume_sma"]
        
        return df
    
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["signal"] = "HOLD"
        df["signal_strength"] = 0.5
        df["signal_reason"] = ""
        
        # Cruzamento para cima
        buy_condition = (
            (df["macd_line"] > df["macd_signal"]) &
            (df["macd_line"].shift(1) <= df["macd_signal"].shift(1)) &
            (df["macd_histogram"] > 0) &
            (df["volume_ratio"] > self.params["volume_mult"])
        )
        
        # Cruzamento para baixo
        sell_condition = (
            (df["macd_line"] < df["macd_signal"]) &
            (df["macd_line"].shift(1) >= df["macd_signal"].shift(1)) &
            (df["macd_histogram"] < 0) &
            (df["volume_ratio"] > self.params["volume_mult"])
        )
        
        df.loc[buy_condition, "signal"] = "BUY"
        df.loc[buy_condition, "signal_reason"] = "MACD crossover bullish + Volume alto"
        
        df.loc[sell_condition, "signal"] = "SELL"
        df.loc[sell_condition, "signal_reason"] = "MACD crossover bearish + Volume alto"
        
        # Força baseada no histograma
        df.loc[buy_condition, "signal_strength"] = 0.6 + abs(df.loc[buy_condition, "macd_histogram"]).clip(0, 100) / 250
        df.loc[sell_condition, "signal_strength"] = 0.6 + abs(df.loc[sell_condition, "macd_histogram"]).clip(0, 100) / 250
        
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
            f"MACD ({self.params['macd_fast']}/{self.params['macd_slow']}/{self.params['macd_signal']}) cruza linha de sinal para cima (BUY)",
            f"MACD cruza linha de sinal para baixo (SELL)",
            "Histograma MACD confirma direção",
            f"Volume > {self.params['volume_mult']}x média"
        ]
    
    def get_exit_conditions(self) -> List[str]:
        return [
            f"Stop Loss: {self.params['sl_atr_mult']}x ATR",
            f"Take Profit: {self.params['tp_atr_mult']}x ATR",
            "Cruzamento oposto do MACD"
        ]


def create_macd_crossover_strategy(params: Dict = None) -> MACDCrossoverStrategy:
    """Factory function para criar instância da estratégia."""
    return MACDCrossoverStrategy(params)
