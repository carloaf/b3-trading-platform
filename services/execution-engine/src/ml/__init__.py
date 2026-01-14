"""
Machine Learning Module
B3 Trading Platform

Módulo de ML para Feature Engineering, Signal Classification, Anomaly Detection,
Hyperparameter Tuning e Performance Analytics.
"""

from .feature_engineer import FeatureEngineer
from .signal_classifier import SignalClassifier, MLSignalFilter
from .ml_enhanced_strategy import MLEnhancedStrategy
from .anomaly_detector import AnomalyDetector
from .hyperparameter_tuner import HyperparameterTuner
from .performance_analytics import PerformanceAnalytics

__all__ = [
    "FeatureEngineer",
    "SignalClassifier",
    "MLSignalFilter",
    "MLEnhancedStrategy",
    "AnomalyDetector",
    "HyperparameterTuner",
    "PerformanceAnalytics"
]
