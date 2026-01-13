"""
B3 Trading Platform - Strategies Module
=========================================
Módulo de estratégias de trading com arquitetura OOP.

Estratégias Disponíveis:
- TrendFollowingStrategy: Seguidor de tendência (EMA + RSI + Volume)
- MeanReversionStrategy: Reversão à média (Bollinger Bands + RSI)
- BreakoutStrategy: Rompimento de suporte/resistência
- MACDCrossoverStrategy: Cruzamento MACD
- RSIDivergenceStrategy: Divergência RSI (4 padrões)
- DynamicPositionSizingStrategy: Kelly Criterion + ATR

Uso:
    from strategies import StrategyManager
    
    manager = StrategyManager()
    strategy = manager.get_strategy('rsi_divergence')
    df_result = strategy.run(df)
"""

from .base_strategy import BaseStrategy, Signal
from .trend_following import TrendFollowingStrategy
from .mean_reversion import MeanReversionStrategy
from .breakout import BreakoutStrategy
from .macd_crossover import MACDCrossoverStrategy
from .rsi_divergence import RSIDivergenceStrategy
from .dynamic_position_sizing import DynamicPositionSizingStrategy
from .strategy_manager import StrategyManager, get_recommended_strategy, detect_market_regime

__all__ = [
    # Base
    'BaseStrategy',
    'Signal',
    
    # Estratégias
    'TrendFollowingStrategy',
    'MeanReversionStrategy',
    'BreakoutStrategy',
    'MACDCrossoverStrategy',
    'RSIDivergenceStrategy',
    'DynamicPositionSizingStrategy',
    
    # Manager
    'StrategyManager',
    'get_recommended_strategy',
    'detect_market_regime',
]

__version__ = '2.0.0'
