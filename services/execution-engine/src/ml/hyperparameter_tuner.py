"""
Hyperparameter Tuner para ML Models
B3 Trading Platform

Otimização de hiperparâmetros usando Optuna para modelos ML.
"""

import optuna
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from sklearn.model_selection import cross_val_score, TimeSeriesSplit
from sklearn.ensemble import RandomForestClassifier
from xgboost import XGBClassifier
from loguru import logger


class HyperparameterTuner:
    """
    Otimizador de hiperparâmetros para modelos ML usando Optuna.
    """
    
    def __init__(
        self,
        model_type: str = "random_forest",
        n_trials: int = 50,
        cv_splits: int = 5,
        random_state: int = 42
    ):
        """
        Inicializa otimizador.
        
        Args:
            model_type: Tipo do modelo ('random_forest' ou 'xgboost')
            n_trials: Número de trials do Optuna
            cv_splits: Número de splits para cross-validation
            random_state: Seed aleatória
        """
        self.model_type = model_type
        self.n_trials = n_trials
        self.cv_splits = cv_splits
        self.random_state = random_state
        self.study = None
        self.best_params = None
        self.best_score = None
        
    def _objective_random_forest(
        self,
        trial: optuna.Trial,
        X: pd.DataFrame,
        y: pd.Series
    ) -> float:
        """
        Função objetivo para Random Forest.
        """
        params = {
            'n_estimators': trial.suggest_int('n_estimators', 50, 500),
            'max_depth': trial.suggest_int('max_depth', 3, 20),
            'min_samples_split': trial.suggest_int('min_samples_split', 2, 20),
            'min_samples_leaf': trial.suggest_int('min_samples_leaf', 1, 10),
            'max_features': trial.suggest_categorical('max_features', ['sqrt', 'log2', None]),
            'class_weight': trial.suggest_categorical('class_weight', ['balanced', 'balanced_subsample', None]),
            'random_state': self.random_state
        }
        
        model = RandomForestClassifier(**params)
        
        # Time Series Cross-Validation
        tscv = TimeSeriesSplit(n_splits=self.cv_splits)
        scores = cross_val_score(model, X, y, cv=tscv, scoring='f1_weighted', n_jobs=-1)
        
        return scores.mean()
    
    def _objective_xgboost(
        self,
        trial: optuna.Trial,
        X: pd.DataFrame,
        y: pd.Series
    ) -> float:
        """
        Função objetivo para XGBoost.
        """
        params = {
            'n_estimators': trial.suggest_int('n_estimators', 50, 500),
            'max_depth': trial.suggest_int('max_depth', 3, 15),
            'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.3, log=True),
            'subsample': trial.suggest_float('subsample', 0.5, 1.0),
            'colsample_bytree': trial.suggest_float('colsample_bytree', 0.5, 1.0),
            'gamma': trial.suggest_float('gamma', 0, 5),
            'reg_alpha': trial.suggest_float('reg_alpha', 0, 5),
            'reg_lambda': trial.suggest_float('reg_lambda', 0, 5),
            'min_child_weight': trial.suggest_int('min_child_weight', 1, 10),
            'random_state': self.random_state,
            'use_label_encoder': False,
            'eval_metric': 'logloss'
        }
        
        model = XGBClassifier(**params)
        
        # Time Series Cross-Validation
        tscv = TimeSeriesSplit(n_splits=self.cv_splits)
        scores = cross_val_score(model, X, y, cv=tscv, scoring='f1_weighted', n_jobs=-1)
        
        return scores.mean()
    
    def optimize(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        direction: str = "maximize"
    ) -> Dict:
        """
        Executa otimização de hiperparâmetros.
        
        Args:
            X: Features
            y: Labels
            direction: Direção da otimização ('maximize' ou 'minimize')
            
        Returns:
            Dicionário com melhores parâmetros e métricas
        """
        logger.info(f"Iniciando otimização de hiperparâmetros para {self.model_type}")
        logger.info(f"Trials: {self.n_trials}, CV Splits: {self.cv_splits}")
        logger.info(f"Samples: {len(X)}, Features: {len(X.columns)}")
        
        # Criar study
        self.study = optuna.create_study(
            direction=direction,
            sampler=optuna.samplers.TPESampler(seed=self.random_state)
        )
        
        # Selecionar função objetivo
        if self.model_type == "random_forest":
            objective = lambda trial: self._objective_random_forest(trial, X, y)
        elif self.model_type == "xgboost":
            objective = lambda trial: self._objective_xgboost(trial, X, y)
        else:
            raise ValueError(f"Modelo não suportado: {self.model_type}")
        
        # Executar otimização
        self.study.optimize(
            objective,
            n_trials=self.n_trials,
            show_progress_bar=False
        )
        
        # Salvar resultados
        self.best_params = self.study.best_params
        self.best_score = self.study.best_value
        
        logger.info(f"Otimização concluída!")
        logger.info(f"Melhor score: {self.best_score:.4f}")
        logger.info(f"Melhores parâmetros: {self.best_params}")
        
        return {
            "best_params": self.best_params,
            "best_score": round(self.best_score, 4),
            "n_trials": self.n_trials,
            "best_trial": self.study.best_trial.number,
            "optimization_history": [
                {
                    "trial": t.number,
                    "value": round(t.value, 4) if t.value is not None else None,
                    "params": t.params
                }
                for t in self.study.trials[-10:]  # Últimos 10 trials
            ]
        }
    
    def get_best_model(self) -> object:
        """
        Retorna modelo com melhores hiperparâmetros.
        
        Returns:
            Modelo sklearn/xgboost configurado
        """
        if self.best_params is None:
            raise ValueError("Execute optimize() primeiro")
        
        if self.model_type == "random_forest":
            return RandomForestClassifier(**self.best_params)
        elif self.model_type == "xgboost":
            return XGBClassifier(**self.best_params)
        else:
            raise ValueError(f"Modelo não suportado: {self.model_type}")
    
    def get_param_importance(self, top_n: int = 10) -> Dict[str, float]:
        """
        Retorna importância de cada hiperparâmetro.
        
        Args:
            top_n: Número de parâmetros mais importantes
            
        Returns:
            Dicionário com importâncias
        """
        if self.study is None:
            raise ValueError("Execute optimize() primeiro")
        
        importances = optuna.importance.get_param_importances(self.study)
        
        # Top N
        top_importances = dict(sorted(
            importances.items(),
            key=lambda x: x[1],
            reverse=True
        )[:top_n])
        
        return {k: round(v, 4) for k, v in top_importances.items()}
