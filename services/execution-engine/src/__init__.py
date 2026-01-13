"""
B3 Trading Platform - Execution Engine
=======================================
Motor de execução com estratégias avançadas.

Estratégias Disponíveis:
- trend_following
- mean_reversion
- breakout
- macd_crossover
- rsi_divergence (NOVO)
- dynamic_position_sizing (Kelly Criterion) (NOVO)
"""

from .main import app
from .strategies import (
    StrategyManager,
    BaseStrategy,
    TrendFollowingStrategy,
    MeanReversionStrategy,
    BreakoutStrategy,
    MACDCrossoverStrategy,
    RSIDivergenceStrategy,
    DynamicPositionSizingStrategy,
    get_recommended_strategy,
    detect_market_regime,
)
from .backtest import BacktestEngine
from .paper_trading import PaperTradingManager

__all__ = [
    # App
    "app",
    
    # Manager
    "StrategyManager",
    "BaseStrategy",
    
    # Estratégias
    "TrendFollowingStrategy",
    "MeanReversionStrategy",
    "BreakoutStrategy",
    "MACDCrossoverStrategy",
    "RSIDivergenceStrategy",
    "DynamicPositionSizingStrategy",
    
    # Funções auxiliares
    "get_recommended_strategy",
    "detect_market_regime",
    
    # Engines
    "BacktestEngine",
    "PaperTradingManager",
]
