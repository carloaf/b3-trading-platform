#!/usr/bin/env python3
"""
Walk-Forward ML com GPU Acceleration
====================================

Versão otimizada do Walk-Forward que utiliza GPU (XGBoost) para:
1. Treinamento acelerado (~2x mais rápido)
2. Hyperparameter tuning com Optuna
3. Dataset completo de 798k registros

Requisitos:
- NVIDIA Container Toolkit configurado
- XGBoost com suporte CUDA

Author: B3 Trading Platform
Date: 29 de Janeiro de 2026
"""

import asyncio
import asyncpg
import pandas as pd
import numpy as np
from typing import List, Dict, Tuple, Optional
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pickle
import json
import time
import os
import sys
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor

# ML imports
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, confusion_matrix
)
from sklearn.model_selection import train_test_split
import xgboost as xgb

# Optuna para hyperparameter tuning
try:
    import optuna
    from optuna.samplers import TPESampler
    OPTUNA_AVAILABLE = True
except ImportError:
    OPTUNA_AVAILABLE = False
    print("⚠️ Optuna não instalado - hyperparameter tuning desabilitado")

# SMOTE para balanceamento
try:
    from imblearn.over_sampling import SMOTE
    SMOTE_AVAILABLE = True
except ImportError:
    SMOTE_AVAILABLE = False
    print("⚠️ imbalanced-learn não instalado - SMOTE desabilitado")

from loguru import logger

# Configuração de logging
logger.remove()
logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}")


@dataclass
class FoldMetrics:
    """Métricas de um fold específico"""
    fold_id: int
    train_start: str
    train_end: str
    test_start: str
    test_end: str
    train_samples: int
    test_samples: int
    train_time: float
    device: str
    accuracy: float
    precision: float
    recall: float
    f1_score: float
    roc_auc: float
    feature_importance: Dict[str, float]


@dataclass
class WalkForwardGPUResults:
    """Resultados consolidados do Walk-Forward com GPU"""
    folds: List[FoldMetrics]
    avg_accuracy: float
    avg_roc_auc: float
    std_accuracy: float
    std_roc_auc: float
    consistency_score: float
    total_train_time: float
    speedup_vs_cpu: float
    best_params: Dict
    top_features: List[Tuple[str, float]]


class GPUWalkForward:
    """
    Walk-Forward Optimization com GPU Acceleration
    
    Features:
    - XGBoost com CUDA para treinamento acelerado
    - Optuna para hyperparameter tuning
    - SMOTE para balanceamento de classes
    - Feature engineering otimizado
    """
    
    def __init__(
        self,
        db_config: dict,
        folds: int = 4,
        train_months: int = 6,
        test_months: int = 2,
        use_gpu: bool = True,
        use_optuna: bool = True,
        n_trials: int = 20
    ):
        """
        Args:
            db_config: Configuração do banco TimescaleDB
            folds: Número de folds (padrão: 4)
            train_months: Meses para treino (padrão: 6)
            test_months: Meses para teste (padrão: 2)
            use_gpu: Usar GPU para treinamento
            use_optuna: Usar Optuna para hyperparameter tuning
            n_trials: Número de trials do Optuna
        """
        self.db_config = db_config
        self.folds = folds
        self.train_months = train_months
        self.test_months = test_months
        self.use_gpu = use_gpu
        self.use_optuna = use_optuna and OPTUNA_AVAILABLE
        self.n_trials = n_trials
        
        # Detectar GPU
        self.device = self._detect_gpu()
        self.models = {}
        self.fold_results = []
        self.best_params = {}
        
        logger.info(f"🎮 GPUWalkForward inicializado")
        logger.info(f"   Device: {self.device}")
        logger.info(f"   Folds: {folds} | Train: {train_months}mo | Test: {test_months}mo")
        logger.info(f"   Optuna: {'✅' if self.use_optuna else '❌'} ({n_trials} trials)")
    
    def _detect_gpu(self) -> str:
        """Detecta se GPU está disponível"""
        if not self.use_gpu:
            return 'cpu'
        
        try:
            import xgboost as xgb
            # Teste rápido
            X = np.random.rand(100, 10)
            y = np.random.randint(0, 2, 100)
            model = xgb.XGBClassifier(
                tree_method='hist',
                device='cuda',
                n_estimators=5,
                verbosity=0
            )
            model.fit(X, y)
            logger.success("✅ GPU CUDA detectada e funcionando")
            return 'cuda'
        except Exception as e:
            logger.warning(f"⚠️ GPU não disponível: {e}")
            return 'cpu'
    
    def _split_timeline(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict]:
        """Divide timeline em folds temporais"""
        folds_data = []
        
        current_date = start_date
        
        for fold_id in range(self.folds):
            train_start = current_date
            train_end = current_date + timedelta(days=30 * self.train_months)
            test_start = train_end
            test_end = test_start + timedelta(days=30 * self.test_months)
            
            if test_end > end_date:
                logger.warning(f"   Fold {fold_id + 1} excede data final, parando...")
                break
            
            folds_data.append({
                'fold_id': fold_id + 1,
                'train_start': train_start,
                'train_end': train_end,
                'test_start': test_start,
                'test_end': test_end
            })
            
            # Rolling window
            current_date += timedelta(days=30 * self.test_months)
        
        return folds_data
    
    async def _load_all_data(
        self,
        symbols: List[str],
        table: str = 'ohlcv_15min'
    ) -> pd.DataFrame:
        """Carrega todos os dados de uma vez para eficiência"""
        
        conn = await asyncpg.connect(**self.db_config)
        
        try:
            # Query otimizada para múltiplos símbolos
            placeholders = ', '.join([f"${i+1}" for i in range(len(symbols))])
            query = f"""
                SELECT symbol, time, open, high, low, close, volume
                FROM {table}
                WHERE symbol IN ({placeholders})
                ORDER BY symbol, time
            """
            
            logger.info(f"📥 Carregando dados de {table}...")
            rows = await conn.fetch(query, *symbols)
            
            df = pd.DataFrame([dict(r) for r in rows])
            logger.info(f"✅ Carregados {len(df):,} registros de {len(symbols)} símbolos")
            
            return df
            
        finally:
            await conn.close()
    
    def _calculate_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calcula features técnicas otimizadas"""
        
        logger.info(f"   Processando {df['symbol'].nunique()} símbolos...")
        
        features_list = []
        
        for symbol in df['symbol'].unique():
            symbol_df = df[df['symbol'] == symbol].copy()
            symbol_df = symbol_df.sort_values('time').reset_index(drop=True)
            
            close = symbol_df['close'].astype(float).values
            high = symbol_df['high'].astype(float).values
            low = symbol_df['low'].astype(float).values
            volume = symbol_df['volume'].astype(float).values
            
            n = len(close)
            
            if n < 250:
                logger.debug(f"   ⚠️ {symbol}: apenas {n} registros (< 250)")
                continue
            
            logger.info(f"   📊 {symbol}: {n:,} registros")
            
            # EMAs (vetorizadas com numpy)
            def ema(arr, period):
                result = np.full(n, np.nan)
                if period >= n:
                    return result
                alpha = 2 / (period + 1)
                result[period-1] = np.mean(arr[:period])
                for i in range(period, n):
                    result[i] = alpha * arr[i] + (1 - alpha) * result[i-1]
                return result
            
            ema_9 = ema(close, 9)
            ema_21 = ema(close, 21)
            ema_50 = ema(close, 50)
            ema_200 = ema(close, 200)
            
            # RSI
            def rsi(arr, period=14):
                result = np.full(n, np.nan)
                deltas = np.diff(arr)
                for i in range(period, n):
                    gains = deltas[i-period:i]
                    ups = np.sum(gains[gains > 0]) / period
                    downs = -np.sum(gains[gains < 0]) / period
                    if downs == 0:
                        result[i] = 100
                    elif ups == 0:
                        result[i] = 0
                    else:
                        result[i] = 100 - (100 / (1 + ups / downs))
                return result
            
            rsi_14 = rsi(close, 14)
            rsi_7 = rsi(close, 7)
            
            # ATR
            def atr(high, low, close, period=14):
                result = np.full(n, np.nan)
                tr = np.zeros(n)
                tr[0] = high[0] - low[0]
                for i in range(1, n):
                    tr[i] = max(high[i] - low[i], 
                               abs(high[i] - close[i-1]),
                               abs(low[i] - close[i-1]))
                for i in range(period, n):
                    result[i] = np.mean(tr[i-period:i])
                return result
            
            atr_14 = atr(high, low, close, 14)
            atr_7 = atr(high, low, close, 7)
            
            # MACD
            ema_12 = ema(close, 12)
            ema_26 = ema(close, 26)
            macd = ema_12 - ema_26
            
            # MACD Signal - precisa tratar NaN no início
            macd_signal = np.full(n, np.nan)
            # Primeiro valor válido do MACD é em index 25 (ema_26 precisa de 26 candles)
            start_idx = 25
            if start_idx + 9 < n:
                # Calcular EMA do MACD a partir do primeiro valor válido
                alpha = 2 / (9 + 1)
                macd_signal[start_idx + 8] = np.nanmean(macd[start_idx:start_idx + 9])
                for i in range(start_idx + 9, n):
                    if not np.isnan(macd[i]) and not np.isnan(macd_signal[i-1]):
                        macd_signal[i] = alpha * macd[i] + (1 - alpha) * macd_signal[i-1]
            
            macd_hist = macd - macd_signal
            
            # Bollinger Bands
            bb_middle = np.full(n, np.nan)
            bb_upper = np.full(n, np.nan)
            bb_lower = np.full(n, np.nan)
            for i in range(20, n):
                bb_middle[i] = np.mean(close[i-20:i])
                std = np.std(close[i-20:i])
                bb_upper[i] = bb_middle[i] + 2 * std
                bb_lower[i] = bb_middle[i] - 2 * std
            
            bb_width = np.where(bb_middle > 0, (bb_upper - bb_lower) / bb_middle, np.nan)
            bb_position = np.where((bb_upper - bb_lower) > 0, 
                                  (close - bb_lower) / (bb_upper - bb_lower), 
                                  np.nan)
            
            # Volume features
            vol_sma_20 = np.full(n, np.nan)
            for i in range(20, n):
                vol_sma_20[i] = np.mean(volume[i-20:i])
            vol_ratio = np.where(vol_sma_20 > 0, volume / vol_sma_20, np.nan)
            
            # Returns e Volatility
            returns = np.zeros(n)
            returns[1:] = (close[1:] - close[:-1]) / close[:-1]
            
            volatility_10 = np.full(n, np.nan)
            volatility_20 = np.full(n, np.nan)
            for i in range(10, n):
                volatility_10[i] = np.std(returns[i-10:i])
            for i in range(20, n):
                volatility_20[i] = np.std(returns[i-20:i])
            
            # ADX (simplificado)
            def adx(high, low, close, period=14):
                result = np.full(n, np.nan)
                tr = np.zeros(n)
                plus_dm = np.zeros(n)
                minus_dm = np.zeros(n)
                
                for i in range(1, n):
                    tr[i] = max(high[i] - low[i], 
                               abs(high[i] - close[i-1]),
                               abs(low[i] - close[i-1]))
                    
                    up_move = high[i] - high[i-1]
                    down_move = low[i-1] - low[i]
                    
                    plus_dm[i] = up_move if (up_move > down_move and up_move > 0) else 0
                    minus_dm[i] = down_move if (down_move > up_move and down_move > 0) else 0
                
                for i in range(period * 2, n):
                    atr_sum = np.sum(tr[i-period:i])
                    plus_di = 100 * np.sum(plus_dm[i-period:i]) / (atr_sum + 1e-10)
                    minus_di = 100 * np.sum(minus_dm[i-period:i]) / (atr_sum + 1e-10)
                    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)
                    result[i] = dx
                
                return result
            
            adx_14 = adx(high, low, close, 14)
            
            # Target: retorno futuro > 0
            target = np.zeros(n)
            for i in range(n - 5):
                target[i] = 1 if close[i + 5] > close[i] else 0
            
            # DataFrame de features
            symbol_features = pd.DataFrame({
                'symbol': symbol,
                'time': symbol_df['time'].values,
                'close': close,
                # EMAs
                'ema_9': ema_9,
                'ema_21': ema_21,
                'ema_50': ema_50,
                'ema_200': ema_200,
                'ema_ratio_9_21': np.where(ema_21 != 0, ema_9 / ema_21, np.nan),
                'ema_ratio_21_50': np.where(ema_50 != 0, ema_21 / ema_50, np.nan),
                'ema_dist_200': np.where(ema_200 != 0, (close - ema_200) / ema_200, np.nan),
                # Momentum
                'rsi_14': rsi_14,
                'rsi_7': rsi_7,
                'macd': macd,
                'macd_signal': macd_signal,
                'macd_hist': macd_hist,
                # Volatility
                'atr_14': atr_14,
                'atr_7': atr_7,
                'atr_pct': np.where(close != 0, atr_14 / close, np.nan),
                'volatility_10': volatility_10,
                'volatility_20': volatility_20,
                # Bollinger
                'bb_width': bb_width,
                'bb_position': bb_position,
                # Volume
                'vol_ratio': vol_ratio,
                # Trend
                'adx_14': adx_14,
                'returns': returns,
                # Target
                'target': target
            })
            
            # Remover NaN por símbolo ANTES de adicionar à lista
            before = len(symbol_features)
            symbol_features = symbol_features.dropna()
            
            # Remover últimos 5 (target inválido)
            if len(symbol_features) > 5:
                symbol_features = symbol_features.iloc[:-5]
            
            logger.info(f"      ✅ {symbol}: {len(symbol_features):,} válidos (de {before:,})")
            
            if len(symbol_features) > 0:
                features_list.append(symbol_features)
        
        if not features_list:
            logger.error("   features_list está vazio!")
            return pd.DataFrame()
        
        logger.info(f"   Concatenando {len(features_list)} DataFrames...")
        all_features = pd.concat(features_list, ignore_index=True)
        logger.info(f"   ✅ Total: {len(all_features):,} registros")
        
        return all_features
    
    def _get_feature_columns(self, df: pd.DataFrame) -> List[str]:
        """Retorna lista de colunas de features"""
        exclude = ['symbol', 'time', 'close', 'target']
        return [c for c in df.columns if c not in exclude]
    
    def _optuna_objective(self, trial, X_train, y_train, X_val, y_val):
        """Função objetivo para Optuna"""
        
        params = {
            'tree_method': 'hist',
            'device': self.device,
            'objective': 'binary:logistic',
            'eval_metric': 'auc',
            'verbosity': 0,
            'random_state': 42,
            # Hyperparameters to tune
            'n_estimators': trial.suggest_int('n_estimators', 50, 200),
            'max_depth': trial.suggest_int('max_depth', 3, 10),
            'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.3, log=True),
            'min_child_weight': trial.suggest_int('min_child_weight', 1, 10),
            'subsample': trial.suggest_float('subsample', 0.6, 1.0),
            'colsample_bytree': trial.suggest_float('colsample_bytree', 0.6, 1.0),
            'gamma': trial.suggest_float('gamma', 0, 5),
            'reg_alpha': trial.suggest_float('reg_alpha', 1e-8, 10.0, log=True),
            'reg_lambda': trial.suggest_float('reg_lambda', 1e-8, 10.0, log=True),
        }
        
        model = xgb.XGBClassifier(**params)
        model.fit(X_train, y_train)
        
        y_pred_prob = model.predict_proba(X_val)[:, 1]
        auc = roc_auc_score(y_val, y_pred_prob)
        
        return auc
    
    def _tune_hyperparameters(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray
    ) -> Dict:
        """Otimiza hyperparameters com Optuna"""
        
        if not self.use_optuna:
            return {
                'n_estimators': 100,
                'max_depth': 6,
                'learning_rate': 0.1,
                'min_child_weight': 1,
                'subsample': 0.8,
                'colsample_bytree': 0.8,
                'gamma': 0,
                'reg_alpha': 1e-5,
                'reg_lambda': 1e-5,
            }
        
        logger.info("🔍 Otimizando hyperparameters com Optuna...")
        
        # Split para validação
        X_tr, X_val, y_tr, y_val = train_test_split(
            X_train, y_train, test_size=0.2, random_state=42
        )
        
        # Optuna study
        study = optuna.create_study(
            direction='maximize',
            sampler=TPESampler(seed=42)
        )
        
        study.optimize(
            lambda trial: self._optuna_objective(trial, X_tr, y_tr, X_val, y_val),
            n_trials=self.n_trials,
            show_progress_bar=True,
            n_jobs=1  # GPU não suporta paralelo
        )
        
        logger.info(f"   Best AUC: {study.best_value:.4f}")
        logger.info(f"   Best params: {study.best_params}")
        
        return study.best_params
    
    def _train_fold(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_test: np.ndarray,
        y_test: np.ndarray,
        fold_id: int,
        feature_names: List[str]
    ) -> Tuple[FoldMetrics, xgb.XGBClassifier]:
        """Treina um fold e retorna métricas"""
        
        logger.info(f"\n{'='*60}")
        logger.info(f"📊 FOLD {fold_id}")
        logger.info(f"   Train: {len(X_train):,} samples | Test: {len(X_test):,} samples")
        
        # Balanceamento com SMOTE (se disponível)
        if SMOTE_AVAILABLE and len(np.unique(y_train)) > 1:
            try:
                smote = SMOTE(random_state=42)
                X_train_bal, y_train_bal = smote.fit_resample(X_train, y_train)
                logger.info(f"   SMOTE: {len(X_train)} → {len(X_train_bal)} samples")
            except Exception as e:
                logger.warning(f"   SMOTE falhou: {e}")
                X_train_bal, y_train_bal = X_train, y_train
        else:
            X_train_bal, y_train_bal = X_train, y_train
        
        # Hyperparameter tuning no primeiro fold
        if fold_id == 1 and self.use_optuna:
            self.best_params = self._tune_hyperparameters(X_train_bal, y_train_bal)
        
        # Parâmetros do modelo
        params = {
            'tree_method': 'hist',
            'device': self.device,
            'objective': 'binary:logistic',
            'eval_metric': 'auc',
            'verbosity': 0,
            'random_state': 42,
            **self.best_params
        }
        
        # Treinar
        logger.info(f"   🚀 Treinando com {self.device.upper()}...")
        start_time = time.time()
        
        model = xgb.XGBClassifier(**params)
        model.fit(X_train_bal, y_train_bal)
        
        train_time = time.time() - start_time
        logger.info(f"   ⏱️  Tempo: {train_time:.2f}s")
        
        # Avaliar
        y_pred = model.predict(X_test)
        y_prob = model.predict_proba(X_test)[:, 1]
        
        acc = accuracy_score(y_test, y_pred)
        prec = precision_score(y_test, y_pred, zero_division=0)
        rec = recall_score(y_test, y_pred, zero_division=0)
        f1 = f1_score(y_test, y_pred, zero_division=0)
        
        try:
            auc = roc_auc_score(y_test, y_prob)
        except:
            auc = 0.5
        
        logger.info(f"   📈 Accuracy: {acc*100:.2f}% | ROC-AUC: {auc:.4f}")
        logger.info(f"   📈 Precision: {prec*100:.2f}% | Recall: {rec*100:.2f}%")
        
        # Feature importance
        importance = dict(zip(feature_names, model.feature_importances_))
        top_features = sorted(importance.items(), key=lambda x: x[1], reverse=True)[:5]
        logger.info(f"   🔝 Top features: {[f[0] for f in top_features]}")
        
        metrics = FoldMetrics(
            fold_id=fold_id,
            train_start="",
            train_end="",
            test_start="",
            test_end="",
            train_samples=len(X_train_bal),
            test_samples=len(X_test),
            train_time=train_time,
            device=self.device,
            accuracy=acc,
            precision=prec,
            recall=rec,
            f1_score=f1,
            roc_auc=auc,
            feature_importance=importance
        )
        
        return metrics, model
    
    async def run(
        self,
        symbols: List[str],
        table: str = 'ohlcv_15min'
    ) -> WalkForwardGPUResults:
        """
        Executa Walk-Forward completo com GPU
        
        Args:
            symbols: Lista de símbolos
            table: Tabela do TimescaleDB
        
        Returns:
            Resultados consolidados
        """
        
        logger.info("=" * 60)
        logger.info("🚀 Walk-Forward ML com GPU")
        logger.info(f"   Símbolos: {symbols}")
        logger.info(f"   Tabela: {table}")
        logger.info("=" * 60)
        
        # 1. Carregar dados
        df = await self._load_all_data(symbols, table)
        
        if df.empty:
            logger.error("❌ Nenhum dado carregado!")
            return None
        
        # 2. Calcular features
        logger.info("\n🔧 Calculando features...")
        features_df = self._calculate_features(df)
        
        if features_df.empty:
            logger.error("❌ Nenhuma feature calculada!")
            return None
        
        logger.info(f"✅ {len(features_df):,} registros com features")
        
        # 3. Preparar dados
        feature_cols = self._get_feature_columns(features_df)
        X = features_df[feature_cols].values
        y = features_df['target'].values
        
        logger.info(f"\n📊 Dataset: {X.shape[0]:,} amostras × {X.shape[1]} features")
        logger.info(f"   Target balance: {y.mean()*100:.1f}% positivos")
        
        # 4. Split temporal para folds
        # Usar índices para simular folds temporais
        n_samples = len(X)
        fold_size = n_samples // (self.folds + 1)
        
        fold_metrics = []
        total_train_time = 0
        cpu_train_time = 0  # Para calcular speedup
        
        # 5. Executar folds
        for fold_id in range(1, self.folds + 1):
            train_start = 0
            train_end = fold_size * fold_id
            test_start = train_end
            test_end = min(test_start + fold_size, n_samples)
            
            X_train = X[train_start:train_end]
            y_train = y[train_start:train_end]
            X_test = X[test_start:test_end]
            y_test = y[test_start:test_end]
            
            if len(X_test) == 0:
                continue
            
            metrics, model = self._train_fold(
                X_train, y_train, X_test, y_test,
                fold_id, feature_cols
            )
            
            fold_metrics.append(metrics)
            total_train_time += metrics.train_time
            self.models[fold_id] = model
        
        # 6. Benchmark CPU para speedup
        logger.info("\n⏱️ Calculando speedup vs CPU...")
        start_cpu = time.time()
        
        cpu_params = {
            'tree_method': 'hist',
            'device': 'cpu',
            'n_estimators': self.best_params.get('n_estimators', 100),
            'max_depth': self.best_params.get('max_depth', 6),
            'verbosity': 0
        }
        cpu_model = xgb.XGBClassifier(**cpu_params)
        cpu_model.fit(X[:fold_size], y[:fold_size])
        
        cpu_train_time = time.time() - start_cpu
        
        # Speedup por fold
        avg_gpu_time = total_train_time / len(fold_metrics)
        speedup = cpu_train_time / avg_gpu_time if avg_gpu_time > 0 else 1.0
        
        # 7. Consolidar resultados
        accuracies = [m.accuracy for m in fold_metrics]
        aucs = [m.roc_auc for m in fold_metrics]
        
        avg_accuracy = np.mean(accuracies)
        avg_auc = np.mean(aucs)
        std_accuracy = np.std(accuracies)
        std_auc = np.std(aucs)
        consistency = 1 - (std_accuracy / avg_accuracy) if avg_accuracy > 0 else 0
        
        # Top features agregadas
        all_importance = {}
        for m in fold_metrics:
            for feat, imp in m.feature_importance.items():
                all_importance[feat] = all_importance.get(feat, 0) + imp
        
        top_features = sorted(all_importance.items(), key=lambda x: x[1], reverse=True)[:10]
        
        results = WalkForwardGPUResults(
            folds=fold_metrics,
            avg_accuracy=avg_accuracy,
            avg_roc_auc=avg_auc,
            std_accuracy=std_accuracy,
            std_roc_auc=std_auc,
            consistency_score=consistency,
            total_train_time=total_train_time,
            speedup_vs_cpu=speedup,
            best_params=self.best_params,
            top_features=top_features
        )
        
        # 8. Resumo final
        logger.info("\n" + "=" * 60)
        logger.info("📊 RESULTADOS FINAIS")
        logger.info("=" * 60)
        logger.info(f"   Folds: {len(fold_metrics)}")
        logger.info(f"   Accuracy: {avg_accuracy*100:.2f}% ± {std_accuracy*100:.2f}%")
        logger.info(f"   ROC-AUC: {avg_auc:.4f} ± {std_auc:.4f}")
        logger.info(f"   Consistency: {consistency:.4f}")
        logger.info(f"   Total train time: {total_train_time:.2f}s")
        logger.info(f"   🚀 Speedup GPU: {speedup:.2f}x vs CPU")
        logger.info("\n📊 Top 10 Features:")
        for i, (feat, imp) in enumerate(top_features):
            logger.info(f"   {i+1}. {feat}: {imp/len(fold_metrics)*100:.2f}%")
        
        # Salvar modelo final
        model_path = Path('/app/models/walk_forward_gpu_latest.pkl')
        model_path.parent.mkdir(exist_ok=True)
        with open(model_path, 'wb') as f:
            pickle.dump({
                'models': self.models,
                'best_params': self.best_params,
                'feature_columns': feature_cols,
                'results': asdict(results)
            }, f)
        logger.info(f"\n💾 Modelo salvo em: {model_path}")
        
        return results


async def main():
    """Executa Walk-Forward GPU"""
    
    # Configuração do banco
    db_config = {
        'host': os.getenv('TIMESCALE_HOST', 'timescaledb'),
        'port': int(os.getenv('TIMESCALE_PORT', 5432)),
        'database': os.getenv('TIMESCALE_DB', 'b3trading_market'),
        'user': os.getenv('TIMESCALE_USER', 'b3trading_ts'),
        'password': os.getenv('TIMESCALE_PASSWORD', 'b3trading_ts_pass')
    }
    
    # Símbolos com mais dados em 15min (>15k registros)
    symbols = [
        'CSNA3', 'VALE3', 'MGLU3', 'GGBR4', 'USIM5',
        'SUZB3', 'EMBR3', 'TAEE11', 'WEGE3', 'KLBN11',
        'HAPV3', 'PRIO3', 'SANB11', 'PETR3', 'SBSP3'
    ]
    
    # Criar e executar Walk-Forward
    wf = GPUWalkForward(
        db_config=db_config,
        folds=4,
        train_months=6,
        test_months=2,
        use_gpu=True,
        use_optuna=True,
        n_trials=20
    )
    
    results = await wf.run(symbols, table='ohlcv_15min')
    
    return results


if __name__ == "__main__":
    asyncio.run(main())
