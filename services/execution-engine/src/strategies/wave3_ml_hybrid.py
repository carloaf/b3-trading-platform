#!/usr/bin/env python3
"""
Wave3 ML Hybrid Strategy - v2.3
================================

Combina Wave3 Enhanced v2.1 com Machine Learning Filter

Arquitetura:
1. Wave3 gera sinal (score ≥65)
2. ML prediz probabilidade de sucesso usando 114 features
3. Aceita trade SE wave3_score ≥65 AND ml_confidence ≥0.60

Objetivo: Win rate 40% → 55-60%

Autor: B3 Trading Platform - Data Science Team
Data: 21 Janeiro 2026
Versão: 2.3 Hybrid
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional
from dataclasses import dataclass
import pickle
import os
import sys

# Importar Wave3 Enhanced v2.1
sys.path.append('/app/src/strategies')
from wave3_enhanced import Wave3Enhanced, EnhancedWave3Signal

# Importar FeatureEngineer
sys.path.append('/app/src/ml')
from feature_engineering import FeatureEngineer


@dataclass
class Wave3MLSignal(EnhancedWave3Signal):
    """
    Estende EnhancedWave3Signal com informações de ML
    """
    ml_confidence: float = 0.0
    ml_prediction: str = "UNKNOWN"
    ml_features_count: int = 0
    hybrid_score: float = 0.0  # Combina wave3 + ML


class Wave3MLHybrid:
    """
    Estratégia Híbrida: Wave3 Enhanced + ML Filter
    
    Workflow:
    1. Wave3 gera sinal base (quality score ≥65)
    2. ML engine calcula confidence (0-1)
    3. Filtro: aceita SE ml_confidence ≥ threshold
    4. Retorna sinal enriquecido com ML info
    
    Parâmetros:
        ml_model_path: Caminho para modelo .pkl
        ml_threshold: Confidence mínima (default: 0.60)
        wave3_params: Dict de parâmetros Wave3
    """
    
    def __init__(self,
                 ml_model_path: str = '/app/models/ml_wave3_v2.pkl',
                 ml_threshold: float = 0.60,
                 **wave3_params):
        """
        Inicializa Wave3MLHybrid
        
        Args:
            ml_model_path: Caminho para modelo ML treinado
            ml_threshold: Confidence mínima para aceitar trade (0-1)
            **wave3_params: Parâmetros para Wave3Enhanced
        """
        
        # Inicializar Wave3 Enhanced v2.1 (baseline)
        self.wave3 = Wave3Enhanced(**wave3_params)
        
        # ML configuration
        self.ml_threshold = ml_threshold
        self.ml_model_path = ml_model_path
        self.ml_model = None
        self.feature_engineer = FeatureEngineer()
        
        # Carregar modelo ML se existir
        self._load_ml_model()
        
        # Estatísticas
        self.stats = {
            'wave3_signals': 0,
            'ml_filtered': 0,
            'ml_approved': 0,
            'no_ml_model': 0
        }
    
    def _load_ml_model(self):
        """Carrega modelo ML do disco"""
        if os.path.exists(self.ml_model_path):
            try:
                with open(self.ml_model_path, 'rb') as f:
                    self.ml_model = pickle.load(f)
                print(f"✅ ML Model loaded: {self.ml_model_path}")
            except Exception as e:
                print(f"⚠️ Erro ao carregar modelo ML: {e}")
                self.ml_model = None
        else:
            print(f"⚠️ ML Model não encontrado: {self.ml_model_path}")
            print("   Estratégia funcionará como Wave3 pura")
    
    def _engineer_ml_features(self, df_60min: pd.DataFrame, df_daily: pd.DataFrame) -> Optional[np.ndarray]:
        """
        Gera features ML para predição
        
        Args:
            df_60min: DataFrame com dados 60min
            df_daily: DataFrame com dados daily
            
        Returns:
            Array com features ou None se erro
        """
        try:
            # Usar dados 60min como base (mais granular)
            df_features = self.feature_engineer.engineer_features(df_60min.copy())
            
            if df_features is None or len(df_features) == 0:
                return None
            
            # Pegar última linha (momento atual)
            latest = df_features.iloc[-1:]
            
            # Remover colunas não-feature
            feature_cols = [col for col in latest.columns 
                          if col not in ['time', 'symbol', 'target', 'target_binary']]
            
            features = latest[feature_cols].values
            
            # Tratar NaN/Inf
            features = np.nan_to_num(features, nan=0.0, posinf=1e10, neginf=-1e10)
            
            return features
            
        except Exception as e:
            print(f"⚠️ Erro ao gerar features ML: {e}")
            return None
    
    def _predict_ml_confidence(self, features: np.ndarray) -> tuple:
        """
        Prediz probabilidade de sucesso usando ML
        
        Args:
            features: Array de features
            
        Returns:
            (confidence, prediction) onde:
                confidence: probabilidade 0-1
                prediction: 'BUY', 'SELL', 'HOLD'
        """
        if self.ml_model is None:
            return 0.5, "HOLD"  # Neutro se não tem modelo
        
        try:
            # Predict proba: [prob_negativo, prob_positivo]
            proba = self.ml_model.predict_proba(features)[0]
            
            # Confidence = probabilidade da classe positiva
            confidence = float(proba[1])
            
            # Predição categórica
            if confidence >= 0.65:
                prediction = "BUY"
            elif confidence <= 0.35:
                prediction = "SELL"
            else:
                prediction = "HOLD"
            
            return confidence, prediction
            
        except Exception as e:
            print(f"⚠️ Erro na predição ML: {e}")
            return 0.5, "HOLD"
    
    def generate_signal(self, 
                       df_daily: pd.DataFrame,
                       df_60min: pd.DataFrame,
                       symbol: str) -> Optional[Wave3MLSignal]:
        """
        Gera sinal Wave3 + ML Filter
        
        Workflow:
        1. Wave3 gera sinal base
        2. ML calcula confidence
        3. Filtro: aceita SE confidence ≥ threshold
        
        Args:
            df_daily: DataFrame com dados diários
            df_60min: DataFrame com dados 60min
            symbol: Símbolo do ativo
            
        Returns:
            Wave3MLSignal ou None se rejeitado
        """
        
        # 1. Wave3 gera sinal base
        wave3_signal = self.wave3.generate_signal(df_daily, df_60min, symbol)
        
        if wave3_signal is None:
            return None  # Wave3 não gerou sinal
        
        self.stats['wave3_signals'] += 1
        
        # 2. Se não tem modelo ML, retorna Wave3 puro
        if self.ml_model is None:
            self.stats['no_ml_model'] += 1
            # Converter para Wave3MLSignal sem ML info
            return Wave3MLSignal(
                **wave3_signal.__dict__,
                ml_confidence=0.5,
                ml_prediction="NO_MODEL",
                ml_features_count=0,
                hybrid_score=wave3_signal.quality_score
            )
        
        # 3. Gerar features ML
        features = self._engineer_ml_features(df_60min, df_daily)
        
        if features is None:
            self.stats['no_ml_model'] += 1
            return Wave3MLSignal(
                **wave3_signal.__dict__,
                ml_confidence=0.5,
                ml_prediction="NO_FEATURES",
                ml_features_count=0,
                hybrid_score=wave3_signal.quality_score
            )
        
        # 4. ML prediz confidence
        ml_confidence, ml_prediction = self._predict_ml_confidence(features)
        
        # 5. Filtro ML: rejeita se confidence < threshold
        if ml_confidence < self.ml_threshold:
            self.stats['ml_filtered'] += 1
            return None  # ❌ REJEITADO por ML
        
        # 6. ✅ APROVADO: Wave3 + ML
        self.stats['ml_approved'] += 1
        
        # Calcular hybrid score (combina wave3 + ML)
        hybrid_score = (wave3_signal.quality_score * 0.6) + (ml_confidence * 100 * 0.4)
        
        # Criar sinal enriquecido
        return Wave3MLSignal(
            **wave3_signal.__dict__,
            ml_confidence=ml_confidence,
            ml_prediction=ml_prediction,
            ml_features_count=features.shape[1],
            hybrid_score=hybrid_score
        )
    
    def get_stats(self) -> Dict:
        """Retorna estatísticas de filtragem ML"""
        total = self.stats['wave3_signals']
        if total == 0:
            return self.stats
        
        return {
            **self.stats,
            'ml_filter_rate': self.stats['ml_filtered'] / total * 100,
            'ml_approval_rate': self.stats['ml_approved'] / total * 100
        }
    
    def reset_stats(self):
        """Reseta estatísticas"""
        self.stats = {
            'wave3_signals': 0,
            'ml_filtered': 0,
            'ml_approved': 0,
            'no_ml_model': 0
        }


if __name__ == "__main__":
    """
    Teste básico da estratégia
    """
    print("🧪 Testando Wave3MLHybrid...")
    
    # Criar estratégia
    strategy = Wave3MLHybrid(
        ml_threshold=0.60,
        min_quality_score=65,  # Wave3 params
        volume_multiplier=1.1,
        target_levels=[(0.5, 1.0), (0.3, 1.5), (0.2, 2.5)]
    )
    
    print(f"\n📊 Configuração:")
    print(f"   Wave3 Score: ≥65")
    print(f"   ML Threshold: ≥0.60")
    print(f"   ML Model: {strategy.ml_model is not None}")
    print(f"\n✅ Strategy ready!")
