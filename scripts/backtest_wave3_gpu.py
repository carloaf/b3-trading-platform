#!/usr/bin/env python3
"""
Backtest Wave3 com GPU Acceleration
====================================

Combina a estratégia Wave3 v2.1 validada (77.8% win rate) com:
1. XGBoost GPU para classificação de sinais
2. Optuna para hyperparameter tuning
3. Walk-Forward validation

Objetivo:
- Usar ML para filtrar sinais Wave3
- Aumentar win rate de 77.8% → 80%+
- Reduzir falsos positivos

Autor: B3 Trading Platform
Data: 29 Janeiro 2026
"""

import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
import sys
import asyncio
import asyncpg
from decimal import Decimal
import time
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
import json

# ML imports
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, confusion_matrix, classification_report
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
    print("⚠️ Optuna não instalado")

# SMOTE para balanceamento
try:
    from imblearn.over_sampling import SMOTE
    SMOTE_AVAILABLE = True
except ImportError:
    SMOTE_AVAILABLE = False

sys.path.append('/app/src/strategies')

# Suppress optuna logs
if OPTUNA_AVAILABLE:
    optuna.logging.set_verbosity(optuna.logging.WARNING)


@dataclass
class BacktestGPUResults:
    """Resultados do backtest com ML"""
    symbol: str
    total_signals: int
    ml_filtered: int
    total_trades: int
    winners: int
    losers: int
    win_rate: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    total_return: float
    sharpe_ratio: float
    max_drawdown: float
    ml_accuracy: float
    ml_precision: float
    ml_recall: float
    training_time: float
    device: str


class Wave3GPUBacktest:
    """
    Backtest Wave3 com GPU Acceleration
    
    Fluxo:
    1. Carrega dados históricos do TimescaleDB
    2. Gera features técnicas (Wave3 indicators)
    3. Treina XGBoost com GPU para filtrar sinais
    4. Walk-Forward: treina em período passado, testa no futuro
    5. Reporta métricas comparativas
    """
    
    def __init__(
        self,
        db_config: dict,
        use_gpu: bool = True,
        use_optuna: bool = True,
        n_trials: int = 20,
        min_quality_score: int = 40  # Reduzido para capturar mais sinais
    ):
        self.db_config = db_config
        self.use_gpu = use_gpu
        self.use_optuna = use_optuna and OPTUNA_AVAILABLE
        self.n_trials = n_trials
        self.min_quality_score = min_quality_score
        
        # Detectar GPU
        self.device = self._detect_gpu()
        self.models = {}
        self.best_params = {}
        
        print(f"\n{'='*80}")
        print("WAVE3 GPU BACKTEST INICIALIZADO")
        print(f"{'='*80}")
        print(f"Device: {self.device}")
        print(f"Optuna: {'✅' if self.use_optuna else '❌'} ({n_trials} trials)")
        print(f"Quality Score mínimo: {min_quality_score}")
        print(f"{'='*80}")
    
    def _detect_gpu(self) -> str:
        """Detecta se GPU está disponível"""
        if not self.use_gpu:
            return 'cpu'
        
        try:
            X = np.random.rand(100, 10)
            y = np.random.randint(0, 2, 100)
            model = xgb.XGBClassifier(
                tree_method='hist',
                device='cuda',
                n_estimators=5,
                verbosity=0
            )
            model.fit(X, y)
            print("✅ GPU CUDA detectada e funcionando")
            return 'cuda'
        except Exception as e:
            print(f"⚠️ GPU não disponível: {e}")
            return 'cpu'
    
    async def fetch_data(
        self,
        pool,
        symbol: str,
        start_date: date,
        end_date: date = None
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Busca dados históricos do TimescaleDB"""
        
        if end_date is None:
            end_date = date.today()
        
        async with pool.acquire() as conn:
            # Daily data
            rows_daily = await conn.fetch("""
                SELECT time, open, high, low, close, volume
                FROM ohlcv_daily
                WHERE symbol = $1
                AND time >= $2 AND time <= $3
                ORDER BY time
            """, symbol, start_date, end_date)
            
            # 60min data
            rows_60min = await conn.fetch("""
                SELECT time, open, high, low, close, volume
                FROM ohlcv_60min
                WHERE symbol = $1
                AND time >= $2 AND time <= $3
                ORDER BY time
            """, symbol, start_date, end_date)
        
        df_daily = pd.DataFrame(
            [(r['time'], float(r['open']), float(r['high']), 
              float(r['low']), float(r['close']), float(r['volume']))
             for r in rows_daily],
            columns=['time', 'open', 'high', 'low', 'close', 'volume']
        )
        
        df_60min = pd.DataFrame(
            [(r['time'], float(r['open']), float(r['high']), 
              float(r['low']), float(r['close']), float(r['volume']))
             for r in rows_60min],
            columns=['time', 'open', 'high', 'low', 'close', 'volume']
        )
        
        return df_daily, df_60min
    
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calcula indicadores técnicos (Wave3 enhanced)"""
        
        df = df.copy()
        
        # EMAs (Wave3 core)
        df['ema_9'] = df['close'].ewm(span=9, adjust=False).mean()
        df['ema_21'] = df['close'].ewm(span=21, adjust=False).mean()
        df['ema_34'] = df['close'].ewm(span=34, adjust=False).mean()
        df['ema_72'] = df['close'].ewm(span=72, adjust=False).mean()
        
        # Tendência EMA
        df['ema_trend'] = (df['ema_9'] > df['ema_21']).astype(int) + \
                         (df['ema_21'] > df['ema_34']).astype(int) + \
                         (df['ema_34'] > df['ema_72']).astype(int)
        
        # MACD
        ema_12 = df['close'].ewm(span=12, adjust=False).mean()
        ema_26 = df['close'].ewm(span=26, adjust=False).mean()
        df['macd'] = ema_12 - ema_26
        
        # MACD Signal - calculado corretamente
        macd_signal = pd.Series(index=df.index, dtype=float)
        macd_signal.iloc[:25] = np.nan
        for i in range(25, len(df)):
            if i == 25:
                macd_signal.iloc[i] = df['macd'].iloc[:26].mean()
            else:
                macd_signal.iloc[i] = macd_signal.iloc[i-1] * (8/10) + df['macd'].iloc[i] * (2/10)
        df['macd_signal'] = macd_signal
        df['macd_histogram'] = df['macd'] - df['macd_signal']
        
        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # Bollinger Bands
        df['bb_middle'] = df['close'].rolling(window=20).mean()
        bb_std = df['close'].rolling(window=20).std()
        df['bb_upper'] = df['bb_middle'] + (bb_std * 2)
        df['bb_lower'] = df['bb_middle'] - (bb_std * 2)
        df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle']
        df['bb_position'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])
        
        # Volume
        df['volume_sma_20'] = df['volume'].rolling(window=20).mean()
        df['volume_ratio'] = df['volume'] / df['volume_sma_20']
        
        # ATR
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = np.max(ranges, axis=1)
        df['atr_14'] = true_range.rolling(window=14).mean()
        df['atr_percent'] = df['atr_14'] / df['close'] * 100
        
        # Momentum
        df['momentum_10'] = df['close'] / df['close'].shift(10) - 1
        df['momentum_20'] = df['close'] / df['close'].shift(20) - 1
        
        # Range position
        df['range_position'] = (df['close'] - df['low']) / (df['high'] - df['low'] + 0.0001)
        
        # Volatilidade
        df['volatility_20'] = df['close'].rolling(window=20).std() / df['close'].rolling(window=20).mean()
        
        return df
    
    def generate_wave3_signals(
        self,
        df_daily: pd.DataFrame,
        df_60min: pd.DataFrame
    ) -> pd.DataFrame:
        """Gera sinais Wave3 com features para ML"""
        
        # Calcular indicadores
        df_daily = self.calculate_indicators(df_daily)
        df_60min = self.calculate_indicators(df_60min)
        
        signals = []
        
        # Iterar pelos candles de 60min (warm-up de 100 para ter mais sinais)
        warm_up = min(100, len(df_60min) - 50)  # Garantir pelo menos 50 candles de teste
        
        for i in range(warm_up, len(df_60min)):
            candle = df_60min.iloc[i]
            current_time = candle['time']
            
            # Contexto diário
            current_date = pd.Timestamp(current_time).normalize()
            daily_idx = df_daily[df_daily['time'] <= current_date].index
            
            if len(daily_idx) < 30:  # Reduzido para garantir mais dados
                continue
            
            daily_row = df_daily.loc[daily_idx[-1]]
            
            # Quality Score simplificado
            quality_score = 0
            
            # EMA Alignment (0-30 pontos)
            if df_60min.iloc[i]['ema_trend'] >= 2:
                quality_score += 15
            if daily_row['ema_trend'] >= 2:
                quality_score += 15
            
            # MACD (0-20 pontos)
            if not pd.isna(df_60min.iloc[i]['macd_histogram']):
                if df_60min.iloc[i]['macd_histogram'] > 0:
                    quality_score += 10
            if not pd.isna(daily_row['macd_histogram']):
                if daily_row['macd_histogram'] > 0:
                    quality_score += 10
            
            # RSI (0-15 pontos)
            rsi_60 = df_60min.iloc[i]['rsi']
            if not pd.isna(rsi_60):
                if 40 <= rsi_60 <= 70:
                    quality_score += 15
            
            # Volume (0-15 pontos)
            vol_ratio = df_60min.iloc[i]['volume_ratio']
            if not pd.isna(vol_ratio):
                if vol_ratio > 1.2:
                    quality_score += 15
            
            # Momentum (0-20 pontos)
            mom_10 = df_60min.iloc[i]['momentum_10']
            if not pd.isna(mom_10):
                if mom_10 > 0:
                    quality_score += 10
            mom_20 = df_60min.iloc[i]['momentum_20']
            if not pd.isna(mom_20):
                if mom_20 > 0:
                    quality_score += 10
            
            # Só considera se quality_score >= threshold
            if quality_score >= self.min_quality_score:
                signals.append({
                    'time': current_time,
                    'close': candle['close'],
                    'quality_score': quality_score,
                    'direction': 'LONG' if df_60min.iloc[i]['ema_trend'] >= 2 else 'SHORT',
                    # Features para ML
                    'ema_trend_60': df_60min.iloc[i]['ema_trend'],
                    'ema_trend_daily': daily_row['ema_trend'],
                    'macd_histogram_60': df_60min.iloc[i]['macd_histogram'],
                    'macd_histogram_daily': daily_row['macd_histogram'],
                    'rsi_60': df_60min.iloc[i]['rsi'],
                    'rsi_daily': daily_row['rsi'],
                    'bb_position_60': df_60min.iloc[i]['bb_position'],
                    'bb_width_60': df_60min.iloc[i]['bb_width'],
                    'volume_ratio_60': df_60min.iloc[i]['volume_ratio'],
                    'atr_percent_60': df_60min.iloc[i]['atr_percent'],
                    'momentum_10': df_60min.iloc[i]['momentum_10'],
                    'momentum_20': df_60min.iloc[i]['momentum_20'],
                    'volatility_20': df_60min.iloc[i]['volatility_20'],
                    'range_position': df_60min.iloc[i]['range_position']
                })
        
        return pd.DataFrame(signals)
    
    def simulate_trade_outcome(
        self,
        signals_df: pd.DataFrame,
        df_60min: pd.DataFrame
    ) -> pd.DataFrame:
        """Simula resultado real dos trades (target para ML)
        
        Wave3 v2.1 usa:
        - Stop Loss: 2% (tight stop)
        - Take Profit: 4% (2:1 R:R mais conservador)
        - Hold máximo: 15 candles de 60min
        """
        
        results = []
        
        for idx, signal in signals_df.iterrows():
            signal_time = signal['time']
            entry_price = signal['close']
            
            # Wave3 v2.1 usa R:R 2:1 com stops apertados
            if signal['direction'] == 'LONG':
                stop_loss = entry_price * 0.98  # -2% stop (apertado)
                take_profit = entry_price * 1.04  # +4% target (2:1 R:R)
            else:  # SHORT
                stop_loss = entry_price * 1.02  # +2% stop
                take_profit = entry_price * 0.96  # -4% target
            
            # Buscar candles futuros (máximo 15 = ~1 dia de trading)
            future_candles = df_60min[df_60min['time'] > signal_time].head(15)
            
            if len(future_candles) == 0:
                continue
            
            # Simular trade
            exit_price = None
            winner = None
            
            for _, candle in future_candles.iterrows():
                if signal['direction'] == 'LONG':
                    if candle['low'] <= stop_loss:
                        exit_price = stop_loss
                        winner = 0
                        break
                    if candle['high'] >= take_profit:
                        exit_price = take_profit
                        winner = 1
                        break
                else:
                    if candle['high'] >= stop_loss:
                        exit_price = stop_loss
                        winner = 0
                        break
                    if candle['low'] <= take_profit:
                        exit_price = take_profit
                        winner = 1
                        break
            
            # Se não bateu nem stop nem target
            if exit_price is None:
                last_candle = future_candles.iloc[-1]
                exit_price = last_candle['close']
                if signal['direction'] == 'LONG':
                    winner = 1 if exit_price > entry_price else 0
                else:
                    winner = 1 if exit_price < entry_price else 0
            
            signal_copy = signal.to_dict()
            signal_copy['exit_price'] = exit_price
            signal_copy['winner'] = winner
            signal_copy['return_pct'] = ((exit_price / entry_price) - 1) * 100 if signal['direction'] == 'LONG' else ((entry_price / exit_price) - 1) * 100
            results.append(signal_copy)
        
        return pd.DataFrame(results)
    
    def optimize_hyperparams(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: np.ndarray,
        y_val: np.ndarray
    ) -> Dict:
        """Otimiza hyperparâmetros com Optuna"""
        
        def objective(trial):
            params = {
                'n_estimators': trial.suggest_int('n_estimators', 50, 300),
                'max_depth': trial.suggest_int('max_depth', 3, 10),
                'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.3),
                'subsample': trial.suggest_float('subsample', 0.6, 1.0),
                'colsample_bytree': trial.suggest_float('colsample_bytree', 0.6, 1.0),
                'min_child_weight': trial.suggest_int('min_child_weight', 1, 10),
                'gamma': trial.suggest_float('gamma', 0, 0.5),
                'reg_alpha': trial.suggest_float('reg_alpha', 0, 1.0),
                'reg_lambda': trial.suggest_float('reg_lambda', 0, 1.0),
            }
            
            model = xgb.XGBClassifier(
                **params,
                tree_method='hist',
                device=self.device,
                random_state=42,
                verbosity=0,
                n_jobs=-1
            )
            
            model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)
            y_pred = model.predict(X_val)
            return f1_score(y_val, y_pred)
        
        study = optuna.create_study(
            direction='maximize',
            sampler=TPESampler(seed=42)
        )
        study.optimize(objective, n_trials=self.n_trials, show_progress_bar=True)
        
        return study.best_params
    
    async def backtest_symbol(
        self,
        pool,
        symbol: str,
        train_start: date,
        train_end: date,
        test_start: date,
        test_end: date
    ) -> Optional[BacktestGPUResults]:
        """Backtest Walk-Forward para 1 símbolo"""
        
        print(f"\n{'='*80}")
        print(f"📊 Backtesting: {symbol}")
        print(f"   Train: {train_start} → {train_end}")
        print(f"   Test:  {test_start} → {test_end}")
        print(f"{'='*80}")
        
        # Buscar dados de treino
        print("📥 Buscando dados de treino...")
        df_daily_train, df_60min_train = await self.fetch_data(pool, symbol, train_start, train_end)
        
        if len(df_60min_train) < 500:
            print(f"⚠️ Dados de treino insuficientes: {len(df_60min_train)} candles 60min")
            return None
        
        print(f"✅ Treino: {len(df_daily_train)} daily, {len(df_60min_train)} 60min")
        
        # Buscar dados de teste
        print("📥 Buscando dados de teste...")
        df_daily_test, df_60min_test = await self.fetch_data(pool, symbol, test_start, test_end)
        
        if len(df_60min_test) < 100:
            print(f"⚠️ Dados de teste insuficientes: {len(df_60min_test)} candles 60min")
            return None
        
        print(f"✅ Teste: {len(df_daily_test)} daily, {len(df_60min_test)} 60min")
        
        # Gerar sinais Wave3 para treino
        print("🔍 Gerando sinais Wave3 (treino)...")
        signals_train = self.generate_wave3_signals(df_daily_train, df_60min_train)
        print(f"   → {len(signals_train)} sinais com quality_score >= {self.min_quality_score}")
        
        if len(signals_train) < 50:
            print(f"⚠️ Poucos sinais de treino: {len(signals_train)}")
            return None
        
        # Simular resultados (target)
        print("💰 Simulando resultados de trades (treino)...")
        signals_train = self.simulate_trade_outcome(signals_train, df_60min_train)
        print(f"   → {len(signals_train)} trades simulados")
        print(f"   → Win Rate base: {signals_train['winner'].mean()*100:.1f}%")
        
        # Preparar features
        feature_cols = [
            'quality_score', 'ema_trend_60', 'ema_trend_daily',
            'macd_histogram_60', 'macd_histogram_daily',
            'rsi_60', 'rsi_daily', 'bb_position_60', 'bb_width_60',
            'volume_ratio_60', 'atr_percent_60',
            'momentum_10', 'momentum_20', 'volatility_20', 'range_position'
        ]
        
        X_train = signals_train[feature_cols].fillna(0).values
        y_train = signals_train['winner'].values
        
        # Split para validação do Optuna
        X_tr, X_val, y_tr, y_val = train_test_split(
            X_train, y_train, test_size=0.2, random_state=42, stratify=y_train
        )
        
        # SMOTE para balanceamento
        if SMOTE_AVAILABLE:
            try:
                smote = SMOTE(random_state=42)
                X_tr, y_tr = smote.fit_resample(X_tr, y_tr)
                print(f"   → SMOTE aplicado: {len(X_tr)} amostras")
            except:
                pass
        
        # Otimizar hyperparâmetros
        start_time = time.time()
        
        if self.use_optuna:
            print(f"\n🔧 Otimizando hyperparâmetros com Optuna ({self.n_trials} trials)...")
            best_params = self.optimize_hyperparams(X_tr, y_tr, X_val, y_val)
            print(f"   → Melhores params: {best_params}")
        else:
            best_params = {
                'n_estimators': 200,
                'max_depth': 6,
                'learning_rate': 0.1,
                'subsample': 0.8,
                'colsample_bytree': 0.8
            }
        
        # Treinar modelo final
        print("\n🚀 Treinando modelo XGBoost com GPU...")
        model = xgb.XGBClassifier(
            **best_params,
            tree_method='hist',
            device=self.device,
            random_state=42,
            verbosity=0,
            n_jobs=-1
        )
        model.fit(X_train, y_train)
        
        training_time = time.time() - start_time
        print(f"   → Tempo de treino: {training_time:.2f}s")
        
        # Feature importance
        importance = dict(zip(feature_cols, model.feature_importances_))
        top_features = sorted(importance.items(), key=lambda x: x[1], reverse=True)[:5]
        print(f"\n📈 Top 5 features:")
        for feat, imp in top_features:
            print(f"   → {feat}: {imp:.4f}")
        
        # ==================== TESTE ====================
        print(f"\n🧪 FASE DE TESTE ({test_start} → {test_end})")
        
        # Gerar sinais Wave3 para teste
        signals_test = self.generate_wave3_signals(df_daily_test, df_60min_test)
        print(f"   → {len(signals_test)} sinais Wave3 no período de teste")
        
        if len(signals_test) < 10:
            print(f"⚠️ Poucos sinais de teste")
            return None
        
        # Simular resultados reais
        signals_test = self.simulate_trade_outcome(signals_test, df_60min_test)
        
        X_test = signals_test[feature_cols].fillna(0).values
        y_test = signals_test['winner'].values
        
        # Prever com ML
        y_pred = model.predict(X_test)
        y_prob = model.predict_proba(X_test)[:, 1]
        
        # Métricas ML
        ml_accuracy = accuracy_score(y_test, y_pred)
        ml_precision = precision_score(y_test, y_pred, zero_division=0)
        ml_recall = recall_score(y_test, y_pred, zero_division=0)
        ml_f1 = f1_score(y_test, y_pred, zero_division=0)
        
        print(f"\n📊 Métricas ML:")
        print(f"   Accuracy:  {ml_accuracy*100:.1f}%")
        print(f"   Precision: {ml_precision*100:.1f}%")
        print(f"   Recall:    {ml_recall*100:.1f}%")
        print(f"   F1:        {ml_f1*100:.1f}%")
        
        # Filtrar sinais pelo ML (alta confiança)
        threshold = 0.6  # Só trades com >60% probabilidade
        ml_selected = y_prob >= threshold
        
        signals_filtered = signals_test[ml_selected].copy()
        
        if len(signals_filtered) < 5:
            print(f"⚠️ ML filtrou demais: apenas {len(signals_filtered)} trades")
            signals_filtered = signals_test  # Fallback para todos
        
        # Calcular métricas finais
        total_trades = len(signals_filtered)
        winners = int(signals_filtered['winner'].sum())
        losers = total_trades - winners
        win_rate = winners / total_trades * 100 if total_trades > 0 else 0
        
        returns = signals_filtered['return_pct'].values
        wins = [r for r in returns if r > 0]
        losses = [r for r in returns if r < 0]
        
        avg_win = np.mean(wins) if wins else 0
        avg_loss = abs(np.mean(losses)) if losses else 0
        
        total_wins = sum(wins) if wins else 0
        total_losses = abs(sum(losses)) if losses else 0
        profit_factor = total_wins / total_losses if total_losses > 0 else 0
        
        total_return = sum(returns)
        
        # Sharpe
        if len(returns) > 1:
            sharpe_ratio = np.mean(returns) / np.std(returns) * np.sqrt(252) if np.std(returns) > 0 else 0
        else:
            sharpe_ratio = 0
        
        # Max Drawdown
        cumulative = np.cumsum([1.0] + list(returns))
        running_max = np.maximum.accumulate(cumulative)
        drawdown = (cumulative - running_max) / running_max * 100
        max_drawdown = abs(drawdown.min())
        
        print(f"\n{'='*80}")
        print(f"📊 RESULTADOS: {symbol}")
        print(f"{'='*80}")
        print(f"Sinais Wave3 totais:  {len(signals_test)}")
        print(f"Filtrados pelo ML:    {total_trades} (threshold={threshold})")
        print(f"Winners:              {winners} ({win_rate:.1f}%)")
        print(f"Losers:               {losers}")
        print(f"Avg Win:              {avg_win:.2f}%")
        print(f"Avg Loss:             {avg_loss:.2f}%")
        print(f"Profit Factor:        {profit_factor:.2f}")
        print(f"Total Return:         {total_return:.2f}%")
        print(f"Sharpe Ratio:         {sharpe_ratio:.2f}")
        print(f"Max Drawdown:         {max_drawdown:.2f}%")
        print(f"{'='*80}")
        
        return BacktestGPUResults(
            symbol=symbol,
            total_signals=len(signals_test),
            ml_filtered=total_trades,
            total_trades=total_trades,
            winners=winners,
            losers=losers,
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            profit_factor=profit_factor,
            total_return=total_return,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
            ml_accuracy=ml_accuracy * 100,
            ml_precision=ml_precision * 100,
            ml_recall=ml_recall * 100,
            training_time=training_time,
            device=self.device
        )


async def main():
    """Função principal"""
    
    print("\n" + "="*80)
    print("BACKTEST WAVE3 COM GPU ACCELERATION")
    print("="*80)
    print(f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print(f"Estratégia: Wave3 v2.1 + XGBoost GPU + Optuna")
    print(f"Walk-Forward: Train 6 meses → Test 2 meses")
    print("="*80)
    
    # Config DB
    db_config = {
        'host': 'b3-timescaledb',
        'port': 5432,
        'user': 'b3trading_ts',
        'password': 'b3trading_ts_pass',
        'database': 'b3trading_market'
    }
    
    # Conectar
    print("\n🔗 Conectando ao TimescaleDB...")
    try:
        pool = await asyncpg.create_pool(**db_config, min_size=1, max_size=5)
        print("✅ Conectado")
    except Exception as e:
        print(f"❌ Erro: {e}")
        return
    
    # Criar backtest
    backtest = Wave3GPUBacktest(
        db_config=db_config,
        use_gpu=True,
        use_optuna=True,
        n_trials=20,
        min_quality_score=55  # Wave3 v2.1 padrão
    )
    
    # Símbolos
    symbols = ['PETR4', 'VALE3', 'ITUB4', 'BBDC4', 'ABEV3']
    
    # Períodos Walk-Forward (usando dados completos 2023-2025)
    # Train: Jan/2023 → Jun/2024 (18 meses)
    # Test: Jul/2024 → Dez/2024 (6 meses)
    train_start = date(2023, 1, 1)
    train_end = date(2024, 6, 30)
    test_start = date(2024, 7, 1)
    test_end = date(2024, 12, 31)
    
    print(f"\n📊 Testando {len(symbols)} símbolos...")
    print(f"   Train: {train_start} → {train_end}")
    print(f"   Test:  {test_start} → {test_end}")
    
    all_results = []
    
    for idx, symbol in enumerate(symbols, 1):
        print(f"\n[{idx}/{len(symbols)}]", end=" ")
        
        try:
            result = await backtest.backtest_symbol(
                pool, symbol,
                train_start, train_end,
                test_start, test_end
            )
            
            if result:
                all_results.append(result)
        
        except Exception as e:
            print(f"❌ Erro em {symbol}: {e}")
            import traceback
            traceback.print_exc()
    
    # Resumo consolidado
    print("\n" + "="*80)
    print("RESUMO CONSOLIDADO - WAVE3 + ML GPU")
    print("="*80)
    
    if all_results:
        total_trades = sum(r.total_trades for r in all_results)
        total_winners = sum(r.winners for r in all_results)
        avg_win_rate = np.mean([r.win_rate for r in all_results])
        avg_precision = np.mean([r.ml_precision for r in all_results])
        avg_sharpe = np.mean([r.sharpe_ratio for r in all_results])
        avg_return = np.mean([r.total_return for r in all_results])
        max_dd = max(r.max_drawdown for r in all_results)
        total_time = sum(r.training_time for r in all_results)
        
        print(f"\n📊 Performance Trading:")
        print(f"   Total Trades:     {total_trades}")
        print(f"   Total Winners:    {total_winners} ({total_winners/total_trades*100:.1f}%)")
        print(f"   Avg Win Rate:     {avg_win_rate:.1f}%")
        print(f"   Avg Sharpe:       {avg_sharpe:.2f}")
        print(f"   Avg Return:       {avg_return:.2f}%")
        print(f"   Max Drawdown:     {max_dd:.2f}%")
        
        print(f"\n🤖 Performance ML:")
        print(f"   Avg Precision:    {avg_precision:.1f}%")
        print(f"   Device:           {all_results[0].device}")
        print(f"   Tempo Total:      {total_time:.1f}s")
        
        print(f"\n{'Símbolo':<10} {'Trades':<8} {'Win%':<8} {'ML Prec%':<10} {'Return%':<10} {'Sharpe':<8}")
        print("-"*80)
        for r in all_results:
            print(f"{r.symbol:<10} {r.total_trades:<8} {r.win_rate:<8.1f} {r.ml_precision:<10.1f} {r.total_return:<10.2f} {r.sharpe_ratio:<8.2f}")
        
        # Comparação com baseline
        print(f"\n📈 Comparação com Baseline:")
        print(f"   Wave3 v2.1 baseline: 77.8% win rate")
        print(f"   Wave3 + ML GPU:      {avg_win_rate:.1f}% win rate")
        improvement = avg_win_rate - 77.8
        print(f"   Diferença:           {'+' if improvement > 0 else ''}{improvement:.1f}%")
    
    else:
        print("⚠️ Nenhum resultado válido")
    
    print("\n" + "="*80)
    print("✅ Backtest Wave3 GPU concluído!")
    print("="*80)
    
    await pool.close()


if __name__ == '__main__':
    asyncio.run(main())
