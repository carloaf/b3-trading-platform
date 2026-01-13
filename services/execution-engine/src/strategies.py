"""
B3 Trading Platform - Strategy Manager
=======================================
Gerenciador de estratégias de trading.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Optional, Any

import pandas as pd
import numpy as np
from loguru import logger

# Importar biblioteca de indicadores técnicos
try:
    import pandas_ta as ta
except ImportError:
    import ta


class BaseStrategy(ABC):
    """Classe base para todas as estratégias."""
    
    name: str = "base"
    description: str = "Estratégia base"
    
    def __init__(self, params: Optional[Dict] = None):
        self.params = params or self.default_params()
    
    @abstractmethod
    def default_params(self) -> Dict:
        """Parâmetros padrão da estratégia."""
        pass
    
    @abstractmethod
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calcula indicadores técnicos."""
        pass
    
    @abstractmethod
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """Gera sinais de trading."""
        pass
    
    def get_current_signal(self, df: pd.DataFrame) -> Dict:
        """Retorna sinal atual (último candle)."""
        df = self.calculate_indicators(df)
        df = self.generate_signals(df)
        
        last = df.iloc[-1]
        
        return {
            "signal": last.get("signal", "HOLD"),
            "strength": float(last.get("signal_strength", 0.5)),
            "strategy": self.name,
            "entry_price": float(last["close"]),
            "stop_loss": float(last.get("stop_loss")) if pd.notna(last.get("stop_loss")) else None,
            "take_profit": float(last.get("take_profit")) if pd.notna(last.get("take_profit")) else None,
            "timestamp": last["time"] if "time" in last else datetime.now(),
            "indicators": {
                k: float(v) if isinstance(v, (int, float, np.number)) and pd.notna(v) else None
                for k, v in last.items()
                if k not in ["time", "open", "high", "low", "close", "volume", "signal", "signal_strength", "stop_loss", "take_profit"]
            }
        }


class TrendFollowingStrategy(BaseStrategy):
    """
    Estratégia de seguimento de tendência.
    Usa EMA 9/21 + RSI + Volume para identificar tendências.
    """
    
    name = "trend_following"
    description = "Seguidor de tendência com EMA 9/21 + RSI + Volume"
    
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
        df["ema_fast"] = df["close"].ewm(span=self.params["ema_fast"], adjust=False).mean()
        df["ema_slow"] = df["close"].ewm(span=self.params["ema_slow"], adjust=False).mean()
        
        # RSI
        delta = df["close"].diff()
        gain = delta.where(delta > 0, 0).rolling(window=self.params["rsi_period"]).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.params["rsi_period"]).mean()
        rs = gain / loss
        df["rsi"] = 100 - (100 / (1 + rs))
        
        # ATR
        high_low = df["high"] - df["low"]
        high_close = (df["high"] - df["close"].shift()).abs()
        low_close = (df["low"] - df["close"].shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df["atr"] = tr.rolling(window=self.params["atr_period"]).mean()
        
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
        
        # Condições de compra
        buy_condition = (
            (df["ema_fast"] > df["ema_slow"]) &  # Tendência de alta
            (df["ema_fast"].shift(1) <= df["ema_slow"].shift(1)) &  # Cruzamento
            (df["rsi"] < self.params["rsi_overbought"]) &  # RSI não sobrecomprado
            (df["volume_ratio"] > self.params["volume_mult"])  # Volume acima da média
        )
        
        # Condições de venda
        sell_condition = (
            (df["ema_fast"] < df["ema_slow"]) &  # Tendência de baixa
            (df["ema_fast"].shift(1) >= df["ema_slow"].shift(1)) &  # Cruzamento
            (df["rsi"] > self.params["rsi_oversold"]) &  # RSI não sobrevendido
            (df["volume_ratio"] > self.params["volume_mult"])  # Volume acima da média
        )
        
        df.loc[buy_condition, "signal"] = "BUY"
        df.loc[sell_condition, "signal"] = "SELL"
        
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


class MeanReversionStrategy(BaseStrategy):
    """
    Estratégia de reversão à média.
    Usa Bollinger Bands + RSI para identificar extremos.
    """
    
    name = "mean_reversion"
    description = "Reversão à média com Bollinger Bands + RSI"
    
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
        df["bb_middle"] = df["close"].rolling(window=self.params["bb_period"]).mean()
        bb_std = df["close"].rolling(window=self.params["bb_period"]).std()
        df["bb_upper"] = df["bb_middle"] + (bb_std * self.params["bb_std"])
        df["bb_lower"] = df["bb_middle"] - (bb_std * self.params["bb_std"])
        df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / df["bb_middle"]
        df["bb_pct"] = (df["close"] - df["bb_lower"]) / (df["bb_upper"] - df["bb_lower"])
        
        # RSI
        delta = df["close"].diff()
        gain = delta.where(delta > 0, 0).rolling(window=self.params["rsi_period"]).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.params["rsi_period"]).mean()
        rs = gain / loss
        df["rsi"] = 100 - (100 / (1 + rs))
        
        # ATR
        high_low = df["high"] - df["low"]
        high_close = (df["high"] - df["close"].shift()).abs()
        low_close = (df["low"] - df["close"].shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df["atr"] = tr.rolling(window=self.params["atr_period"]).mean()
        
        return df
    
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["signal"] = "HOLD"
        df["signal_strength"] = 0.5
        
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
        df.loc[sell_condition, "signal"] = "SELL"
        
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
            df["bb_middle"],  # Alvo: média
            np.where(
                df["signal"] == "SELL",
                df["bb_middle"],
                np.nan
            )
        )
        
        return df


class BreakoutStrategy(BaseStrategy):
    """
    Estratégia de rompimento.
    Identifica rompimentos de suporte/resistência com volume.
    """
    
    name = "breakout"
    description = "Rompimento de suporte/resistência com volume"
    
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
        high_low = df["high"] - df["low"]
        high_close = (df["high"] - df["close"].shift()).abs()
        low_close = (df["low"] - df["close"].shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df["atr"] = tr.rolling(window=self.params["atr_period"]).mean()
        
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
        df.loc[breakout_down, "signal"] = "SELL"
        
        # Força baseada no volume
        df.loc[breakout_up | breakout_down, "signal_strength"] = (
            0.5 + df.loc[breakout_up | breakout_down, "volume_ratio"].clip(1, 3) / 6
        )
        
        # Stop Loss e Take Profit
        df["stop_loss"] = np.where(
            df["signal"] == "BUY",
            df["resistance"].shift(1) - (df["atr"] * 0.5),  # Abaixo da resistência rompida
            np.where(
                df["signal"] == "SELL",
                df["support"].shift(1) + (df["atr"] * 0.5),  # Acima do suporte rompido
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


class MACDCrossoverStrategy(BaseStrategy):
    """
    Estratégia de cruzamento MACD.
    Usa MACD + Volume para confirmar sinais.
    """
    
    name = "macd_crossover"
    description = "Cruzamento MACD com confirmação de volume"
    
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
        ema_fast = df["close"].ewm(span=self.params["macd_fast"], adjust=False).mean()
        ema_slow = df["close"].ewm(span=self.params["macd_slow"], adjust=False).mean()
        df["macd_line"] = ema_fast - ema_slow
        df["macd_signal"] = df["macd_line"].ewm(span=self.params["macd_signal"], adjust=False).mean()
        df["macd_histogram"] = df["macd_line"] - df["macd_signal"]
        
        # ATR
        high_low = df["high"] - df["low"]
        high_close = (df["high"] - df["close"].shift()).abs()
        low_close = (df["low"] - df["close"].shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df["atr"] = tr.rolling(window=self.params["atr_period"]).mean()
        
        # Volume
        df["volume_sma"] = df["volume"].rolling(window=self.params["volume_sma"]).mean()
        df["volume_ratio"] = df["volume"] / df["volume_sma"]
        
        return df
    
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["signal"] = "HOLD"
        df["signal_strength"] = 0.5
        
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
        df.loc[sell_condition, "signal"] = "SELL"
        
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


# ============================================
# STRATEGY MANAGER
# ============================================

class StrategyManager:
    """Gerenciador de estratégias."""
    
    STRATEGIES = {
        "trend_following": TrendFollowingStrategy,
        "mean_reversion": MeanReversionStrategy,
        "breakout": BreakoutStrategy,
        "macd_crossover": MACDCrossoverStrategy,
    }
    
    def __init__(self):
        self._cache = {}
    
    def get_strategy(self, name: str, params: Optional[Dict] = None) -> BaseStrategy:
        """Retorna instância da estratégia."""
        if name not in self.STRATEGIES:
            raise ValueError(f"Estratégia não encontrada: {name}. Disponíveis: {list(self.STRATEGIES.keys())}")
        
        return self.STRATEGIES[name](params)
    
    def list_strategies(self) -> List[Dict]:
        """Lista todas as estratégias."""
        return [
            {
                "name": cls.name,
                "description": cls.description,
                "default_params": cls(None).default_params()
            }
            for cls in self.STRATEGIES.values()
        ]
    
    async def generate_signal(self, strategy_name: str, data: List[Dict], params: Optional[Dict] = None) -> Dict:
        """Gera sinal para dados fornecidos."""
        df = pd.DataFrame(data)
        
        # Garantir tipos corretos
        for col in ["open", "high", "low", "close"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0).astype(int)
        
        strategy = self.get_strategy(strategy_name, params)
        return strategy.get_current_signal(df)
