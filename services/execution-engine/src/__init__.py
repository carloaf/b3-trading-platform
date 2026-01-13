"""
B3 Trading Platform - Execution Engine
"""

from .main import app
from .strategies import StrategyManager, BaseStrategy
from .backtest import BacktestEngine
from .paper_trading import PaperTradingManager

__all__ = [
    "app",
    "StrategyManager",
    "BaseStrategy", 
    "BacktestEngine",
    "PaperTradingManager"
]
