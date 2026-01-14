"""
ML-Enhanced Strategy
B3 Trading Platform

Estratégia que combina sinais de estratégia base com filtro ML.
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional
from loguru import logger

from .signal_classifier import SignalClassifier, MLSignalFilter
from .feature_engineer import FeatureEngineer


class MLEnhancedStrategy:
    """
    Estratégia melhorada com ML.
    
    Combina sinais de uma estratégia técnica base (ex: mean_reversion)
    com predições de um classificador ML treinado.
    """
    
    def __init__(
        self,
        base_strategy_name: str,
        base_strategy_params: Dict,
        classifier: SignalClassifier,
        feature_engineer: FeatureEngineer,
        confidence_threshold: float = 0.6,
        regime: Optional[str] = None
    ):
        """
        Inicializa estratégia ML-enhanced.
        
        Args:
            base_strategy_name: Nome da estratégia base (ex: 'mean_reversion')
            base_strategy_params: Parâmetros da estratégia base
            classifier: SignalClassifier treinado
            feature_engineer: FeatureEngineer para criar features
            confidence_threshold: Threshold de confiança ML
            regime: Regime de mercado (opcional)
        """
        self.base_strategy_name = base_strategy_name
        self.base_strategy_params = base_strategy_params
        self.classifier = classifier
        self.feature_engineer = feature_engineer
        self.regime = regime
        self.ml_filter = MLSignalFilter(classifier, confidence_threshold)
        
    def generate_base_signals(self, df: pd.DataFrame) -> pd.Series:
        """
        Gera sinais da estratégia base.
        
        Args:
            df: DataFrame com OHLCV
            
        Returns:
            Series com sinais (1=compra, -1=venda, 0=neutro)
        """
        # Importar estratégias dinamicamente
        from ..strategies.strategy_manager import StrategyManager
        
        strategy_manager = StrategyManager()
        strategy = strategy_manager.get_strategy(self.base_strategy_name, self.base_strategy_params)
        
        if strategy is None:
            raise ValueError(f"Estratégia base não encontrada: {self.base_strategy_name}")
        
        # Executar estratégia base
        df_result = strategy.run(df.copy())
        signals = df_result['signal']
        
        return signals
    
    def generate_signals(self, df: pd.DataFrame) -> Dict:
        """
        Gera sinais combinando estratégia base + ML.
        
        Args:
            df: DataFrame com OHLCV
            
        Returns:
            Dicionário com:
            - base_signals: sinais da estratégia base
            - ml_signals: sinais após filtro ML
            - ml_confidences: probabilidades do ML
            - features: features utilizadas
        """
        # 1. Criar features
        df_features = self.feature_engineer.create_all_features(df.copy(), regime=self.regime)
        df_features = self.feature_engineer.normalize_features(df_features)
        df_features = df_features.dropna()
        
        # 2. Gerar sinais base
        base_signals = self.generate_base_signals(df_features)
        
        # 3. Filtrar com ML
        feature_cols = [c for c in df_features.columns 
                       if c not in ['open', 'high', 'low', 'close', 'volume']]
        X = df_features[feature_cols]
        
        ml_signals, ml_confidences = self.ml_filter.filter_signals(base_signals, X)
        
        # 4. Estatísticas
        total_base_signals = (base_signals != 0).sum()
        total_ml_signals = (ml_signals != 0).sum()
        acceptance_rate = total_ml_signals / total_base_signals if total_base_signals > 0 else 0
        
        logger.info(f"Base signals: {total_base_signals}")
        logger.info(f"ML signals: {total_ml_signals}")
        logger.info(f"Acceptance rate: {acceptance_rate:.2%}")
        
        return {
            "base_signals": base_signals,
            "ml_signals": ml_signals,
            "ml_confidences": ml_confidences,
            "features": df_features,
            "statistics": {
                "total_base_signals": int(total_base_signals),
                "total_ml_signals": int(total_ml_signals),
                "acceptance_rate": float(acceptance_rate),
                "avg_confidence": float(ml_confidences[ml_signals != 0].mean()) if total_ml_signals > 0 else 0.0
            }
        }
    
    def backtest_comparison(self, df: pd.DataFrame, initial_capital: float = 100000) -> Dict:
        """
        Compara performance da estratégia base vs ML-enhanced.
        
        Args:
            df: DataFrame com OHLCV
            initial_capital: Capital inicial
            
        Returns:
            Dicionário com métricas comparativas
        """
        from ..backtest import BacktestEngine
        
        # Gerar sinais
        result = self.generate_signals(df)
        df_signals = result['features'].copy()
        df_signals['base_signal'] = result['base_signals']
        df_signals['ml_signal'] = result['ml_signals']
        
        # Backtest estratégia base
        bt_base = BacktestEngine(initial_capital=initial_capital)
        metrics_base = bt_base.run(df_signals, df_signals['base_signal'])
        
        # Backtest estratégia ML
        bt_ml = BacktestEngine(initial_capital=initial_capital)
        metrics_ml = bt_ml.run(df_signals, df_signals['ml_signal'])
        
        # Comparação
        improvement = {
            "sharpe_ratio": (metrics_ml['sharpe_ratio'] - metrics_base['sharpe_ratio']) 
                           if metrics_base['sharpe_ratio'] else 0,
            "total_return": metrics_ml['total_return'] - metrics_base['total_return'],
            "win_rate": metrics_ml['win_rate'] - metrics_base['win_rate'],
            "total_trades": metrics_ml['total_trades'] - metrics_base['total_trades']
        }
        
        return {
            "base_strategy": metrics_base,
            "ml_enhanced": metrics_ml,
            "improvement": improvement,
            "signal_statistics": result['statistics']
        }
