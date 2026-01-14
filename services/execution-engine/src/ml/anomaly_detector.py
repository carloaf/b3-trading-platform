"""
Anomaly Detection para Trading
B3 Trading Platform

Detecta anomalias em dados de mercado usando Isolation Forest.
Anomalias podem indicar:
- Movimentos de preço incomuns (oportunidades ou riscos)
- Mudanças abruptas de volume
- Padrões técnicos raros
- Possíveis erros de dados
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import joblib
from pathlib import Path
from loguru import logger


class AnomalyDetector:
    """
    Detector de anomalias em dados de mercado usando Isolation Forest.
    
    Isolation Forest é eficaz para detectar outliers em dados multidimensionais
    sem necessidade de labels (aprendizado não supervisionado).
    
    Anomalias detectadas podem indicar:
    - Oportunidades de trading (reversões, breakouts)
    - Eventos de risco (crashes, manipulação)
    - Erros de dados
    """
    
    def __init__(
        self,
        contamination: float = 0.1,
        n_estimators: int = 100,
        max_samples: str = "auto",
        random_state: int = 42
    ):
        """
        Inicializa o detector de anomalias.
        
        Args:
            contamination: Proporção esperada de anomalias (0.0-0.5)
                          0.1 = espera 10% de anomalias
            n_estimators: Número de árvores no ensemble
            max_samples: Número de amostras por árvore ("auto" ou int)
            random_state: Seed para reprodutibilidade
        """
        self.contamination = contamination
        self.n_estimators = n_estimators
        self.max_samples = max_samples
        self.random_state = random_state
        
        self.model = IsolationForest(
            contamination=contamination,
            n_estimators=n_estimators,
            max_samples=max_samples,
            random_state=random_state,
            n_jobs=-1
        )
        
        self.scaler = StandardScaler()
        self.feature_names: List[str] = []
        self.is_fitted: bool = False
        
    def fit(self, X: pd.DataFrame) -> Dict:
        """
        Treina o detector com dados históricos.
        
        Args:
            X: Features para treinar
            
        Returns:
            Dicionário com estatísticas de treinamento
        """
        logger.info(f"Treinando Isolation Forest com {len(X)} amostras")
        
        # Armazenar nomes das features
        self.feature_names = X.columns.tolist()
        
        # Normalizar features
        X_scaled = self.scaler.fit_transform(X)
        
        # Treinar modelo
        self.model.fit(X_scaled)
        self.is_fitted = True
        
        # Predizer anomalias no conjunto de treino
        predictions = self.model.predict(X_scaled)
        scores = self.model.score_samples(X_scaled)
        
        # -1 = anomalia, 1 = normal
        n_anomalies = (predictions == -1).sum()
        anomaly_rate = n_anomalies / len(X)
        
        stats = {
            "n_samples": len(X),
            "n_features": len(self.feature_names),
            "n_anomalies_detected": int(n_anomalies),
            "anomaly_rate": float(anomaly_rate),
            "contamination_param": self.contamination,
            "avg_anomaly_score": float(scores[predictions == -1].mean()) if n_anomalies > 0 else 0.0,
            "avg_normal_score": float(scores[predictions == 1].mean())
        }
        
        logger.info(f"Anomalias detectadas: {n_anomalies} ({anomaly_rate:.2%})")
        
        return stats
    
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """
        Prediz se amostras são anomalias.
        
        Args:
            X: Features
            
        Returns:
            Array com -1 (anomalia) ou 1 (normal)
        """
        if not self.is_fitted:
            raise ValueError("Modelo não treinado. Execute fit() primeiro.")
        
        # Garantir mesma ordem de features
        X_ordered = X[self.feature_names]
        X_scaled = self.scaler.transform(X_ordered)
        
        return self.model.predict(X_scaled)
    
    def score_samples(self, X: pd.DataFrame) -> np.ndarray:
        """
        Calcula anomaly scores (quanto mais negativo, mais anômalo).
        
        Args:
            X: Features
            
        Returns:
            Array com scores de anomalia
        """
        if not self.is_fitted:
            raise ValueError("Modelo não treinado.")
        
        X_ordered = X[self.feature_names]
        X_scaled = self.scaler.transform(X_ordered)
        
        return self.model.score_samples(X_scaled)
    
    def detect_anomalies(
        self,
        X: pd.DataFrame,
        df_ohlcv: Optional[pd.DataFrame] = None
    ) -> Dict:
        """
        Detecta anomalias e retorna análise detalhada.
        
        Args:
            X: Features para análise
            df_ohlcv: DataFrame opcional com OHLCV para contexto
            
        Returns:
            Dicionário com anomalias detectadas e estatísticas
        """
        predictions = self.predict(X)
        scores = self.score_samples(X)
        
        # Identificar índices de anomalias
        anomaly_mask = predictions == -1
        anomaly_indices = X.index[anomaly_mask]
        
        # Estatísticas
        n_anomalies = anomaly_mask.sum()
        anomaly_rate = n_anomalies / len(X)
        
        # Detalhes das anomalias
        anomalies_details = []
        if n_anomalies > 0:
            for idx in anomaly_indices[-100:]:  # Últimas 100 anomalias
                anomaly_info = {
                    "timestamp": idx.isoformat() if hasattr(idx, 'isoformat') else str(idx),
                    "anomaly_score": float(scores[X.index == idx][0])
                }
                
                # Adicionar contexto OHLCV se disponível
                if df_ohlcv is not None and idx in df_ohlcv.index:
                    ohlcv = df_ohlcv.loc[idx]
                    anomaly_info.update({
                        "close": float(ohlcv['close']),
                        "volume": float(ohlcv['volume']),
                        "price_change_pct": float(ohlcv['close'].pct_change()) if hasattr(ohlcv['close'], 'pct_change') else 0
                    })
                
                # Features mais anormais
                feature_values = X.loc[idx]
                feature_deviations = {}
                for feat in self.feature_names[:10]:  # Top 10 features
                    if feat in feature_values.index:
                        feature_deviations[feat] = float(feature_values[feat])
                
                anomaly_info["top_features"] = feature_deviations
                anomalies_details.append(anomaly_info)
        
        return {
            "total_samples": len(X),
            "n_anomalies": int(n_anomalies),
            "anomaly_rate": float(anomaly_rate),
            "avg_anomaly_score": float(scores[anomaly_mask].mean()) if n_anomalies > 0 else 0.0,
            "min_anomaly_score": float(scores[anomaly_mask].min()) if n_anomalies > 0 else 0.0,
            "anomalies": anomalies_details
        }
    
    def get_anomaly_timestamps(self, X: pd.DataFrame) -> List[pd.Timestamp]:
        """
        Retorna timestamps das anomalias detectadas.
        
        Args:
            X: Features com index como timestamp
            
        Returns:
            Lista de timestamps onde anomalias foram detectadas
        """
        predictions = self.predict(X)
        anomaly_mask = predictions == -1
        return X.index[anomaly_mask].tolist()
    
    def analyze_anomaly_patterns(
        self,
        X: pd.DataFrame,
        df_ohlcv: pd.DataFrame
    ) -> Dict:
        """
        Analisa padrões nas anomalias detectadas.
        
        Args:
            X: Features
            df_ohlcv: DataFrame com OHLCV
            
        Returns:
            Dicionário com análise de padrões
        """
        predictions = self.predict(X)
        scores = self.score_samples(X)
        anomaly_mask = predictions == -1
        
        if anomaly_mask.sum() == 0:
            return {"message": "Nenhuma anomalia detectada"}
        
        # Anomalias com contexto de preço
        anomaly_indices = X.index[anomaly_mask]
        anomaly_prices = df_ohlcv.loc[anomaly_indices, 'close']
        anomaly_volumes = df_ohlcv.loc[anomaly_indices, 'volume']
        
        # Retornos após anomalias
        future_returns = []
        for idx in anomaly_indices:
            try:
                current_price = df_ohlcv.loc[idx, 'close']
                # Retorno em 1, 3, 5 dias
                returns = {}
                for days in [1, 3, 5]:
                    future_idx = df_ohlcv.index.get_loc(idx) + days
                    if future_idx < len(df_ohlcv):
                        future_price = df_ohlcv.iloc[future_idx]['close']
                        returns[f"return_{days}d"] = float((future_price - current_price) / current_price)
                
                if returns:
                    future_returns.append(returns)
            except:
                continue
        
        # Estatísticas de retornos
        avg_returns = {}
        if future_returns:
            for key in future_returns[0].keys():
                values = [r[key] for r in future_returns if key in r]
                if values:
                    avg_returns[key] = {
                        "mean": float(np.mean(values)),
                        "median": float(np.median(values)),
                        "std": float(np.std(values))
                    }
        
        # Classificar anomalias por tipo
        anomaly_types = {
            "extreme_price": 0,
            "extreme_volume": 0,
            "high_volatility": 0
        }
        
        # Detectar tipos (simplificado)
        price_threshold = df_ohlcv['close'].std() * 2
        volume_threshold = df_ohlcv['volume'].quantile(0.95)
        
        for idx in anomaly_indices:
            price_change = abs(df_ohlcv.loc[idx, 'close'] - df_ohlcv['close'].shift(1).loc[idx])
            volume = df_ohlcv.loc[idx, 'volume']
            
            if price_change > price_threshold:
                anomaly_types["extreme_price"] += 1
            if volume > volume_threshold:
                anomaly_types["extreme_volume"] += 1
        
        return {
            "n_anomalies": int(anomaly_mask.sum()),
            "anomaly_types": anomaly_types,
            "price_statistics": {
                "mean": float(anomaly_prices.mean()),
                "std": float(anomaly_prices.std()),
                "min": float(anomaly_prices.min()),
                "max": float(anomaly_prices.max())
            },
            "volume_statistics": {
                "mean": float(anomaly_volumes.mean()),
                "median": float(anomaly_volumes.median())
            },
            "future_returns": avg_returns
        }
    
    def save_model(self, filepath: str):
        """
        Salva modelo treinado em disco.
        
        Args:
            filepath: Caminho do arquivo
        """
        if not self.is_fitted:
            raise ValueError("Modelo não treinado")
        
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        
        model_data = {
            'model': self.model,
            'scaler': self.scaler,
            'feature_names': self.feature_names,
            'contamination': self.contamination,
            'is_fitted': self.is_fitted
        }
        
        joblib.dump(model_data, filepath)
        logger.info(f"Modelo de anomalia salvo em {filepath}")
    
    def load_model(self, filepath: str):
        """
        Carrega modelo treinado do disco.
        
        Args:
            filepath: Caminho do arquivo
        """
        model_data = joblib.load(filepath)
        
        self.model = model_data['model']
        self.scaler = model_data['scaler']
        self.feature_names = model_data['feature_names']
        self.contamination = model_data['contamination']
        self.is_fitted = model_data['is_fitted']
        
        logger.info(f"Modelo de anomalia carregado de {filepath}")
