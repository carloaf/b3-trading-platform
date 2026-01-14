"""
Machine Learning Module
B3 Trading Platform

Módulo de ML para Feature Engineering, Signal Classification e Anomaly Detection.
"""

from .feature_engineer import FeatureEngineer
from .signal_classifier import SignalClassifier, MLSignalFilter
from .ml_enhanced_strategy import MLEnhancedStrategy
from .anomaly_detector import AnomalyDetector

__all__ = [
    "FeatureEngineer",
    "SignalClassifier",
    "MLSignalFilter",
    "MLEnhancedStrategy",
    "AnomalyDetector"
]
