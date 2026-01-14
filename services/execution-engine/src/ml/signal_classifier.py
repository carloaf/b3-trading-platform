"""
Signal Classifier para Machine Learning
B3 Trading Platform

Classifica sinais de trading usando Random Forest ou XGBoost.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Literal
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score
import xgboost as xgb
import joblib
from pathlib import Path
from loguru import logger


class SignalClassifier:
    """
    Classificador de sinais de trading usando ML.
    
    Prediz se um sinal de compra/venda será lucrativo baseado em features técnicas.
    Suporta Random Forest e XGBoost.
    """
    
    def __init__(
        self,
        model_type: Literal["random_forest", "xgboost"] = "random_forest",
        n_estimators: int = 200,
        max_depth: Optional[int] = None,
        random_state: int = 42
    ):
        """
        Inicializa o classificador.
        
        Args:
            model_type: Tipo de modelo ('random_forest' ou 'xgboost')
            n_estimators: Número de árvores
            max_depth: Profundidade máxima das árvores
            random_state: Seed para reprodutibilidade
        """
        self.model_type = model_type
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.random_state = random_state
        self.model = None
        self.feature_names: List[str] = []
        self.feature_importance: Optional[Dict[str, float]] = None
        self.training_metrics: Dict = {}
        
    def create_model(self) -> object:
        """Cria instância do modelo baseado no tipo."""
        if self.model_type == "random_forest":
            return RandomForestClassifier(
                n_estimators=self.n_estimators,
                max_depth=self.max_depth,
                random_state=self.random_state,
                n_jobs=-1,
                class_weight='balanced',  # Lidar com desbalanceamento
                min_samples_split=10,
                min_samples_leaf=5
            )
        elif self.model_type == "xgboost":
            return xgb.XGBClassifier(
                n_estimators=self.n_estimators,
                max_depth=self.max_depth if self.max_depth else 6,
                random_state=self.random_state,
                n_jobs=-1,
                learning_rate=0.1,
                subsample=0.8,
                colsample_bytree=0.8,
                scale_pos_weight=1  # Ajustar conforme desbalanceamento
            )
        else:
            raise ValueError(f"model_type inválido: {self.model_type}")
    
    def create_labels(
        self,
        df: pd.DataFrame,
        lookahead_bars: int = 5,
        profit_threshold: float = 0.01
    ) -> pd.Series:
        """
        Cria labels para treinamento supervisionado.
        
        Label = 1 (positivo) se o preço subir > profit_threshold nos próximos lookahead_bars
        Label = 0 (negativo) caso contrário
        
        Args:
            df: DataFrame com coluna 'close'
            lookahead_bars: Quantos candles olhar para frente
            profit_threshold: Retorno mínimo para considerar positivo (ex: 0.01 = 1%)
            
        Returns:
            Series com labels (0 ou 1)
        """
        future_returns = df['close'].shift(-lookahead_bars) / df['close'] - 1
        labels = (future_returns > profit_threshold).astype(int)
        
        # Últimas barras não têm label (dados futuros não disponíveis)
        labels.iloc[-lookahead_bars:] = np.nan
        
        return labels
    
    def train(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        test_size: float = 0.2,
        cross_validation: bool = True
    ) -> Dict:
        """
        Treina o modelo.
        
        Args:
            X: Features
            y: Labels (0 ou 1)
            test_size: Proporção do conjunto de teste
            cross_validation: Se True, executa validação cruzada
            
        Returns:
            Dicionário com métricas de treinamento
        """
        # Remover NaN
        valid_idx = ~y.isna()
        X_clean = X[valid_idx]
        y_clean = y[valid_idx]
        
        logger.info(f"Treinando {self.model_type} com {len(X_clean)} amostras")
        logger.info(f"Distribuição de classes: {y_clean.value_counts().to_dict()}")
        
        # Split train/test
        X_train, X_test, y_train, y_test = train_test_split(
            X_clean, y_clean,
            test_size=test_size,
            random_state=self.random_state,
            stratify=y_clean
        )
        
        # Criar e treinar modelo
        self.model = self.create_model()
        self.feature_names = X_train.columns.tolist()
        
        self.model.fit(X_train, y_train)
        
        # Predições
        y_train_pred = self.model.predict(X_train)
        y_test_pred = self.model.predict(X_test)
        
        # Métricas
        train_accuracy = accuracy_score(y_train, y_train_pred)
        test_accuracy = accuracy_score(y_test, y_test_pred)
        
        logger.info(f"Train accuracy: {train_accuracy:.4f}")
        logger.info(f"Test accuracy: {test_accuracy:.4f}")
        
        # Validação cruzada
        cv_scores = []
        if cross_validation:
            cv_scores = cross_val_score(
                self.model, X_clean, y_clean,
                cv=5, scoring='accuracy', n_jobs=-1
            )
            logger.info(f"CV accuracy: {cv_scores.mean():.4f} (+/- {cv_scores.std():.4f})")
        
        # Feature importance
        self._calculate_feature_importance()
        
        # Confusion matrix
        conf_matrix = confusion_matrix(y_test, y_test_pred)
        
        # Classification report
        class_report = classification_report(
            y_test, y_test_pred,
            output_dict=True,
            zero_division=0
        )
        
        # Armazenar métricas
        self.training_metrics = {
            "model_type": self.model_type,
            "n_samples": len(X_clean),
            "n_features": len(self.feature_names),
            "train_accuracy": float(train_accuracy),
            "test_accuracy": float(test_accuracy),
            "cv_mean_accuracy": float(cv_scores.mean()) if cross_validation else None,
            "cv_std_accuracy": float(cv_scores.std()) if cross_validation else None,
            "confusion_matrix": conf_matrix.tolist(),
            "classification_report": class_report,
            "class_distribution": y_clean.value_counts().to_dict()
        }
        
        return self.training_metrics
    
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """
        Prediz labels para novas features.
        
        Args:
            X: Features
            
        Returns:
            Array com predições (0 ou 1)
        """
        if self.model is None:
            raise ValueError("Modelo não treinado. Execute train() primeiro.")
        
        # Garantir que features estão na mesma ordem
        X_ordered = X[self.feature_names]
        
        return self.model.predict(X_ordered)
    
    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """
        Prediz probabilidades de cada classe.
        
        Args:
            X: Features
            
        Returns:
            Array com probabilidades [prob_class_0, prob_class_1]
        """
        if self.model is None:
            raise ValueError("Modelo não treinado. Execute train() primeiro.")
        
        X_ordered = X[self.feature_names]
        return self.model.predict_proba(X_ordered)
    
    def _calculate_feature_importance(self):
        """Calcula importância das features."""
        if self.model is None:
            return
        
        if hasattr(self.model, 'feature_importances_'):
            importances = self.model.feature_importances_
            self.feature_importance = dict(zip(self.feature_names, importances))
            self.feature_importance = dict(
                sorted(self.feature_importance.items(), key=lambda x: x[1], reverse=True)
            )
    
    def get_feature_importance(self, top_n: int = 20) -> Dict[str, float]:
        """
        Retorna as N features mais importantes.
        
        Args:
            top_n: Número de features a retornar
            
        Returns:
            Dicionário com features e suas importâncias
        """
        if self.feature_importance is None:
            return {}
        
        return dict(list(self.feature_importance.items())[:top_n])
    
    def save_model(self, filepath: str):
        """
        Salva modelo treinado em disco.
        
        Args:
            filepath: Caminho do arquivo (ex: 'models/classifier.pkl')
        """
        if self.model is None:
            raise ValueError("Nenhum modelo para salvar")
        
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        
        model_data = {
            'model': self.model,
            'model_type': self.model_type,
            'feature_names': self.feature_names,
            'feature_importance': self.feature_importance,
            'training_metrics': self.training_metrics
        }
        
        joblib.dump(model_data, filepath)
        logger.info(f"Modelo salvo em {filepath}")
    
    def load_model(self, filepath: str):
        """
        Carrega modelo treinado do disco.
        
        Args:
            filepath: Caminho do arquivo
        """
        model_data = joblib.load(filepath)
        
        self.model = model_data['model']
        self.model_type = model_data['model_type']
        self.feature_names = model_data['feature_names']
        self.feature_importance = model_data.get('feature_importance')
        self.training_metrics = model_data.get('training_metrics', {})
        
        logger.info(f"Modelo carregado de {filepath}")
    
    def evaluate(self, X: pd.DataFrame, y: pd.Series) -> Dict:
        """
        Avalia modelo em um conjunto de dados.
        
        Args:
            X: Features
            y: Labels verdadeiros
            
        Returns:
            Dicionário com métricas
        """
        if self.model is None:
            raise ValueError("Modelo não treinado")
        
        y_pred = self.predict(X)
        y_proba = self.predict_proba(X)[:, 1]
        
        accuracy = accuracy_score(y, y_pred)
        conf_matrix = confusion_matrix(y, y_pred)
        class_report = classification_report(y, y_pred, output_dict=True, zero_division=0)
        
        return {
            "accuracy": float(accuracy),
            "confusion_matrix": conf_matrix.tolist(),
            "classification_report": class_report,
            "sample_predictions": {
                "predictions": y_pred[:10].tolist(),
                "probabilities": y_proba[:10].tolist(),
                "true_labels": y.iloc[:10].tolist()
            }
        }


class MLSignalFilter:
    """
    Filtro de sinais usando ML.
    
    Combina sinais de uma estratégia base com predições ML
    para melhorar a qualidade dos sinais.
    """
    
    def __init__(
        self,
        classifier: SignalClassifier,
        confidence_threshold: float = 0.6
    ):
        """
        Inicializa o filtro.
        
        Args:
            classifier: SignalClassifier treinado
            confidence_threshold: Probabilidade mínima para aceitar sinal (0.0-1.0)
        """
        self.classifier = classifier
        self.confidence_threshold = confidence_threshold
    
    def filter_signal(
        self,
        base_signal: int,
        features: pd.DataFrame
    ) -> Tuple[int, float]:
        """
        Filtra um sinal usando ML.
        
        Args:
            base_signal: Sinal da estratégia base (1=compra, -1=venda, 0=neutro)
            features: Features do momento atual
            
        Returns:
            Tupla (sinal_filtrado, confiança)
            - sinal_filtrado: sinal após filtro ML
            - confiança: probabilidade do modelo
        """
        if base_signal == 0:
            return 0, 0.0
        
        # Predizer probabilidade
        proba = self.classifier.predict_proba(features)[0, 1]
        
        # Se confiança é alta, manter sinal
        if proba >= self.confidence_threshold:
            return base_signal, float(proba)
        
        # Caso contrário, rejeitar sinal
        return 0, float(proba)
    
    def filter_signals(
        self,
        base_signals: pd.Series,
        features: pd.DataFrame
    ) -> Tuple[pd.Series, pd.Series]:
        """
        Filtra múltiplos sinais.
        
        Args:
            base_signals: Série com sinais da estratégia base
            features: DataFrame com features
            
        Returns:
            Tupla (sinais_filtrados, probabilidades)
        """
        filtered_signals = []
        confidences = []
        
        for i, signal in enumerate(base_signals):
            if signal == 0:
                filtered_signals.append(0)
                confidences.append(0.0)
            else:
                filtered, conf = self.filter_signal(signal, features.iloc[i:i+1])
                filtered_signals.append(filtered)
                confidences.append(conf)
        
        return pd.Series(filtered_signals, index=base_signals.index), pd.Series(confidences, index=base_signals.index)
