#!/usr/bin/env python3
"""
Wave3 ML Negative Filter Strategy - v2.4
=========================================

LÓGICA INVERTIDA: Usa ML para REJEITAR trades ruins

Arquitetura:
1. Wave3 gera sinal (score ≥55)
2. ML prediz probabilidade de sucesso
3. REJEITA trade SE ml_confidence < 0.30 (filtro negativo)
4. ACEITA todos os outros (confiança neutra/alta)

Filosofia: "Não sabemos quais são os melhores, mas sabemos quais são os piores"

Objetivo: Filtrar 10-20% dos piores trades (losses)

Autor: B3 Trading Platform - Data Science Team
Data: 26 Janeiro 2026
Versão: 2.4 Negative Filter
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
class Wave3MLNegativeSignal(EnhancedWave3Signal):
    """
    Estende EnhancedWave3Signal com informações de ML (filtro negativo)
    """
    ml_confidence: float = 0.5
    ml_prediction: str = "NEUTRAL"
    ml_features_count: int = 0
    ml_reject_reason: str = ""  # Se rejeitado, por quê?
    hybrid_score: float = 0.0


class Wave3MLNegativeFilter:
    """
    Estratégia com Filtro Negativo ML
    
    LÓGICA INVERTIDA:
    - Aceita trades por padrão
    - REJEITA apenas se ML tem BAIXA confiança (< 30%)
    - Filosofia: "eliminar os piores, não escolher os melhores"
    
    Workflow:
    1. Wave3 gera sinal base (quality score ≥55)
    2. ML engine calcula confidence (0-1)
    3. Filtro NEGATIVO: rejeita SE ml_confidence < reject_threshold
    4. Retorna sinal se passou pelo filtro
    
    Parâmetros:
        ml_reject_threshold: Confidence abaixo da qual REJEITA (default: 0.30)
        wave3_params: Dict de parâmetros Wave3
    """
    
    def __init__(self,
                 ml_model_path: str = '/app/models/ml_wave3_v2.pkl',
                 ml_reject_threshold: float = 0.30,
                 **wave3_params):
        """
        Inicializa Wave3MLNegativeFilter
        
        Args:
            ml_model_path: Caminho para modelo ML treinado
            ml_reject_threshold: Confidence ABAIXO da qual REJEITA (0-1)
                                0.30 = rejeita apenas 30% mais baixos
                                0.20 = rejeita apenas 20% mais baixos
            **wave3_params: Parâmetros para Wave3Enhanced
        """
        
        # Inicializar Wave3 Enhanced v2.1 (baseline)
        self.wave3 = Wave3Enhanced(**wave3_params)
        
        # ML configuration (LÓGICA INVERTIDA)
        self.ml_reject_threshold = ml_reject_threshold
        self.ml_model_path = ml_model_path
        self.ml_model = None
        self.ml_feature_names = []
        self.feature_engineer = FeatureEngineer()
        
        # Carregar modelo ML
        self._load_ml_model()
        
        # Estatísticas
        self.stats = {
            'wave3_signals': 0,
            'ml_rejected': 0,  # Trades rejeitados por ML
            'ml_accepted': 0,  # Trades aceitos
            'no_ml_model': 0   # Trades sem modelo ML
        }
    
    def _load_ml_model(self):
        """Carrega modelo ML do disco"""
        if os.path.exists(self.ml_model_path):
            try:
                with open(self.ml_model_path, 'rb') as f:
                    model_data = pickle.load(f)
                
                if isinstance(model_data, dict):
                    self.ml_model = model_data['model']
                    self.ml_feature_names = model_data.get('feature_names', [])
                    print(f"✅ ML Negative Filter loaded: {self.ml_model_path}")
                    print(f"   Version: {model_data.get('version', 'unknown')}")
                    print(f"   Features: {len(self.ml_feature_names)}")
                    print(f"   🔴 REJECT Threshold: < {self.ml_reject_threshold:.0%}")
                else:
                    self.ml_model = model_data
                    self.ml_feature_names = []
                    
            except Exception as e:
                print(f"⚠️ Erro ao carregar modelo ML: {e}")
                self.ml_model = None
        else:
            print(f"⚠️ Modelo ML não encontrado: {self.ml_model_path}")
            self.ml_model = None
    
    def _engineer_ml_features(self, df_daily: pd.DataFrame) -> Optional[np.ndarray]:
        """
        Gera features ML a partir dos dados
        
        Args:
            df_daily: DataFrame com OHLCV diário
            
        Returns:
            Array 2D com features ou None se falhar
        """
        if self.ml_model is None:
            return None
        
        try:
            # Gerar todas as features
            df_features = self.feature_engineer.generate_all_features(df_daily.copy())
            
            if df_features is None or len(df_features) == 0:
                return None
            
            # Pegar última linha (mais recente)
            features_row = df_features.iloc[-1:]
            
            # Se temos feature_names do modelo, usar apenas essas
            if len(self.ml_feature_names) > 0:
                # Selecionar apenas numeric features que estão no modelo
                numeric_features = features_row.select_dtypes(include=[np.number])
                
                # Alinhar com features do modelo
                available_features = [f for f in self.ml_feature_names if f in numeric_features.columns]
                
                if len(available_features) != len(self.ml_feature_names):
                    # Features faltando, tentar preencher com zeros
                    missing = set(self.ml_feature_names) - set(numeric_features.columns)
                    for feat in missing:
                        numeric_features[feat] = 0.0
                
                # Reordenar colunas na ordem esperada
                features_row = numeric_features[self.ml_feature_names]
            else:
                # Sem feature_names, usar todas as numeric
                features_row = features_row.select_dtypes(include=[np.number])
            
            # Converter para numpy array 2D
            features_array = features_row.values
            
            # Validar shape
            if len(self.ml_feature_names) > 0 and features_array.shape[1] != len(self.ml_feature_names):
                print(f"⚠️ Feature mismatch: esperado {len(self.ml_feature_names)}, obtido {features_array.shape[1]}")
                return None
            
            return features_array
            
        except Exception as e:
            print(f"⚠️ Erro ao gerar features ML: {e}")
            return None
    
    def _predict_ml_confidence(self, features: np.ndarray) -> tuple:
        """
        Prediz probabilidade de sucesso usando ML
        
        Args:
            features: Array de features
            
        Returns:
            (confidence, prediction, reject_reason)
        """
        if self.ml_model is None:
            return 0.5, "NEUTRAL", ""
        
        try:
            # Predict proba: [prob_loss, prob_win]
            proba = self.ml_model.predict_proba(features)[0]
            
            # Confidence = probabilidade de WIN (classe positiva)
            confidence = float(proba[1])
            
            # Determinar predição e razão de rejeição
            if confidence < self.ml_reject_threshold:
                prediction = "REJECT"
                reject_reason = f"ML confidence {confidence:.1%} < {self.ml_reject_threshold:.0%}"
            elif confidence >= 0.70:
                prediction = "HIGH_CONFIDENCE"
                reject_reason = ""
            else:
                prediction = "NEUTRAL"
                reject_reason = ""
            
            return confidence, prediction, reject_reason
            
        except Exception as e:
            print(f"⚠️ Erro na predição ML: {e}")
            return 0.5, "NEUTRAL", ""
    
    def generate_signal(self, 
                       df_daily: pd.DataFrame,
                       df_60min: pd.DataFrame,
                       symbol: str) -> Optional[Wave3MLNegativeSignal]:
        """
        Gera sinal Wave3 + ML Negative Filter
        
        LÓGICA INVERTIDA:
        1. Wave3 gera sinal base
        2. ML calcula confidence
        3. REJEITA SE confidence < reject_threshold
        4. ACEITA todos os outros
        
        Args:
            df_daily: DataFrame com dados diários
            df_60min: DataFrame com dados 60min
            symbol: Símbolo do ativo
            
        Returns:
            Wave3MLNegativeSignal ou None se rejeitado
        """
        
        # 1. Wave3 gera sinal base
        wave3_signal = self.wave3.generate_signal(df_daily, df_60min, symbol)
        
        if wave3_signal is None:
            return None  # Wave3 não gerou sinal
        
        self.stats['wave3_signals'] += 1
        
        # 2. Se não tem modelo ML, retorna Wave3 puro (aceita por padrão)
        if self.ml_model is None:
            self.stats['no_ml_model'] += 1
            return Wave3MLNegativeSignal(
                **wave3_signal.__dict__,
                ml_confidence=0.5,
                ml_prediction="NEUTRAL",
                ml_features_count=0,
                ml_reject_reason="",
                hybrid_score=wave3_signal.quality_score
            )
        
        # 3. Gerar features ML
        features = self._engineer_ml_features(df_daily)
        
        if features is None:
            # Sem features, aceita por padrão (não pode avaliar)
            self.stats['ml_accepted'] += 1
            return Wave3MLNegativeSignal(
                **wave3_signal.__dict__,
                ml_confidence=0.5,
                ml_prediction="NEUTRAL",
                ml_features_count=0,
                ml_reject_reason="",
                hybrid_score=wave3_signal.quality_score
            )
        
        # 4. ML prediz confidence
        ml_confidence, ml_prediction, reject_reason = self._predict_ml_confidence(features)
        
        # 5. FILTRO NEGATIVO: Rejeita SE confidence < threshold
        if ml_confidence < self.ml_reject_threshold:
            self.stats['ml_rejected'] += 1
            return None  # 🔴 REJEITADO por baixa confiança
        
        # 6. ACEITO! Retorna sinal enriquecido
        self.stats['ml_accepted'] += 1
        
        # Hybrid score: média ponderada Wave3 + ML
        hybrid_score = (wave3_signal.quality_score * 0.6) + (ml_confidence * 100 * 0.4)
        
        return Wave3MLNegativeSignal(
            **wave3_signal.__dict__,
            ml_confidence=ml_confidence,
            ml_prediction=ml_prediction,
            ml_features_count=features.shape[1],
            ml_reject_reason=reject_reason,
            hybrid_score=hybrid_score
        )
    
    def get_stats(self) -> Dict:
        """Retorna estatísticas de uso"""
        total = self.stats['wave3_signals']
        
        if total > 0:
            reject_rate = (self.stats['ml_rejected'] / total) * 100
            accept_rate = (self.stats['ml_accepted'] / total) * 100
        else:
            reject_rate = 0
            accept_rate = 0
        
        return {
            **self.stats,
            'reject_rate_pct': reject_rate,
            'accept_rate_pct': accept_rate
        }
