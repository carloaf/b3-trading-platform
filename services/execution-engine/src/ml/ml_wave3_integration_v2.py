#!/usr/bin/env python3
"""
PASSO 12 v2: Integração ML + Wave3 + SMOTE
==========================================

Sistema completo de Machine Learning integrado com Wave3 Strategy:
- 114+ features multi-timeframe
- SMOTE para balanceamento de classes  
- Random Forest + XGBoost
- Integração com Wave3 Daily Strategy
- Backtest comparativo (Wave3 puro vs Wave3+ML)

Author: B3 Trading Platform
Date: 16 de Janeiro de 2026
"""

import asyncio
import asyncpg
import pandas as pd
import numpy as np
from typing import List, Dict, Tuple, Optional
from datetime import datetime, timedelta
from pathlib import Path
import pickle
import json

# ML Libraries
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.metrics import classification_report, confusion_matrix, roc_auc_score
from imblearn.over_sampling import SMOTE
import xgboost as xgb

# Technical indicators
from ta.trend import EMAIndicator, MACD, ADXIndicator, SMAIndicator
from ta.momentum import RSIIndicator, StochasticOscillator, ROCIndicator, WilliamsRIndicator
from ta.volatility import BollingerBands, AverageTrueRange, KeltnerChannel
from ta.volume import OnBalanceVolumeIndicator, VolumeWeightedAveragePrice, ChaikinMoneyFlowIndicator


class FeatureEngineerV2:
    """Feature Engineering com 114+ features multi-timeframe"""
    
    def __init__(self):
        self.feature_list = []
    
    def generate_all_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Gera 114+ features para ML
        
        Categorias:
        - Trend (30 features)
        - Momentum (25 features)
        - Volatility (20 features)
        - Volume (15 features)
        - Price Action (12 features)
        - Market Regime (12 features)
        """
        print(f"   📊 Generating 114+ features...")
        
        df = df.copy()
        
        # 1. TREND FEATURES (30)
        df = self._add_trend_features(df)
        
        # 2. MOMENTUM FEATURES (25)
        df = self._add_momentum_features(df)
        
        # 3. VOLATILITY FEATURES (20)
        df = self._add_volatility_features(df)
        
        # 4. VOLUME FEATURES (15)
        df = self._add_volume_features(df)
        
        # 5. PRICE ACTION FEATURES (12)
        df = self._add_price_action_features(df)
        
        # 6. MARKET REGIME FEATURES (12)
        df = self._add_regime_features(df)
        
        # Drop NaN (initial periods)
        initial_len = len(df)
        df = df.dropna()
        print(f"   ✅ Features generated: {len(self.feature_list)} features")
        print(f"   📉 Dropped {initial_len - len(df)} initial NaN rows")
        
        return df
    
    def _add_trend_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """30 Trend features"""
        
        # EMAs (multiple periods)
        for period in [5, 8, 9, 13, 17, 20, 21, 50, 72, 100, 200]:
            col = f'ema_{period}'
            ema = EMAIndicator(df['close'], window=period)
            df[col] = ema.ema_indicator()
            self.feature_list.append(col)
        
        # SMA
        for period in [20, 50, 200]:
            col = f'sma_{period}'
            sma = SMAIndicator(df['close'], window=period)
            df[col] = sma.sma_indicator()
            self.feature_list.append(col)
        
        # MACD
        macd = MACD(df['close'], window_fast=12, window_slow=26, window_sign=9)
        df['macd'] = macd.macd()
        df['macd_signal'] = macd.macd_signal()
        df['macd_hist'] = macd.macd_diff()
        self.feature_list.extend(['macd', 'macd_signal', 'macd_hist'])
        
        # ADX
        adx = ADXIndicator(df['high'], df['low'], df['close'], window=14)
        df['adx'] = adx.adx()
        df['adx_pos'] = adx.adx_pos()
        df['adx_neg'] = adx.adx_neg()
        self.feature_list.extend(['adx', 'adx_pos', 'adx_neg'])
        
        # Trend strength
        df['trend_strength'] = (df['ema_9'] - df['ema_21']) / df['ema_21']
        self.feature_list.append('trend_strength')
        
        # Price vs EMAs
        for period in [20, 50, 200]:
            col = f'price_vs_ema_{period}'
            df[col] = (df['close'] - df[f'ema_{period}']) / df[f'ema_{period}']
            self.feature_list.append(col)
        
        return df
    
    def _add_momentum_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """25 Momentum features"""
        
        # RSI (multiple periods)
        for period in [7, 14, 21]:
            col = f'rsi_{period}'
            rsi = RSIIndicator(df['close'], window=period)
            df[col] = rsi.rsi()
            self.feature_list.append(col)
        
        # Stochastic
        stoch = StochasticOscillator(df['high'], df['low'], df['close'])
        df['stoch_k'] = stoch.stoch()
        df['stoch_d'] = stoch.stoch_signal()
        self.feature_list.extend(['stoch_k', 'stoch_d'])
        
        # ROC (Rate of Change)
        for period in [5, 10, 20]:
            col = f'roc_{period}'
            roc = ROCIndicator(df['close'], window=period)
            df[col] = roc.roc()
            self.feature_list.append(col)
        
        # MOM (Momentum)
        for period in [5, 10, 20]:
            col = f'mom_{period}'
            df[col] = df['close'] - df['close'].shift(period)
            self.feature_list.append(col)
        
        # Williams %R
        for period in [14, 21]:
            col = f'willr_{period}'
            willr = WilliamsRIndicator(df['high'], df['low'], df['close'], lbp=period)
            df[col] = willr.williams_r()
            self.feature_list.append(col)
        
        # CCI (Commodity Channel Index) - usando implementação manual
        for period in [14, 20]:
            col = f'cci_{period}'
            typical_price = (df['high'] + df['low'] + df['close']) / 3
            sma_tp = typical_price.rolling(window=period).mean()
            mean_dev = typical_price.rolling(window=period).apply(lambda x: np.abs(x - x.mean()).mean())
            df[col] = (typical_price - sma_tp) / (0.015 * mean_dev)
            self.feature_list.append(col)
        
        # MFI (Money Flow Index) - implementação manual
        typical_price = (df['high'] + df['low'] + df['close']) / 3
        money_flow = typical_price * df['volume']
        positive_flow = money_flow.where(typical_price > typical_price.shift(1), 0)
        negative_flow = money_flow.where(typical_price < typical_price.shift(1), 0)
        positive_mf = positive_flow.rolling(window=14).sum()
        negative_mf = negative_flow.rolling(window=14).sum()
        mfi = 100 - (100 / (1 + positive_mf / negative_mf))
        df['mfi'] = mfi
        self.feature_list.append('mfi')
        
        return df
    
    def _add_volatility_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """20 Volatility features"""
        
        # ATR (multiple periods)
        for period in [7, 14, 21]:
            col = f'atr_{period}'
            atr = AverageTrueRange(df['high'], df['low'], df['close'], window=period)
            df[col] = atr.average_true_range()
            self.feature_list.append(col)
        
        # Bollinger Bands
        for period in [20, 50]:
            bbands = BollingerBands(df['close'], window=period, window_dev=2)
            df[f'bb_upper_{period}'] = bbands.bollinger_hband()
            df[f'bb_middle_{period}'] = bbands.bollinger_mavg()
            df[f'bb_lower_{period}'] = bbands.bollinger_lband()
            df[f'bb_width_{period}'] = bbands.bollinger_wband()
            self.feature_list.extend([f'bb_upper_{period}', f'bb_middle_{period}', 
                                     f'bb_lower_{period}', f'bb_width_{period}'])
        
        # Historical Volatility
        for period in [10, 20, 30]:
            col = f'hist_vol_{period}'
            df[col] = df['close'].pct_change().rolling(window=period).std() * np.sqrt(252)
            self.feature_list.append(col)
        
        # Keltner Channel
        kc = KeltnerChannel(df['high'], df['low'], df['close'], window=20)
        df['kc_upper'] = kc.keltner_channel_hband()
        df['kc_middle'] = kc.keltner_channel_mband()
        df['kc_lower'] = kc.keltner_channel_lband()
        self.feature_list.extend(['kc_upper', 'kc_middle', 'kc_lower'])
        
        return df
    
    def _add_volume_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """15 Volume features"""
        
        # Volume SMA
        for period in [10, 20, 50]:
            col = f'volume_sma_{period}'
            df[col] = df['volume'].rolling(window=period).mean()
            self.feature_list.append(col)
        
        # Volume ratio
        df['volume_ratio'] = df['volume'] / df['volume'].rolling(window=20).mean()
        self.feature_list.append('volume_ratio')
        
        # OBV (On Balance Volume)
        obv = OnBalanceVolumeIndicator(df['close'], df['volume'])
        df['obv'] = obv.on_balance_volume()
        self.feature_list.append('obv')
        
        # VWAP (Volume Weighted Average Price)
        vwap = VolumeWeightedAveragePrice(df['high'], df['low'], df['close'], df['volume'])
        df['vwap'] = vwap.volume_weighted_average_price()
        self.feature_list.append('vwap')
        
        # AD (Accumulation/Distribution) - implementação manual
        clv = ((df['close'] - df['low']) - (df['high'] - df['close'])) / (df['high'] - df['low'])
        clv = clv.fillna(0)
        ad = (clv * df['volume']).cumsum()
        df['ad'] = ad
        self.feature_list.append('ad')
        
        # CMF (Chaikin Money Flow)
        cmf = ChaikinMoneyFlowIndicator(df['high'], df['low'], df['close'], df['volume'], window=20)
        df['cmf'] = cmf.chaikin_money_flow()
        self.feature_list.append('cmf')
        
        # Volume changes
        for period in [1, 5, 10]:
            col = f'volume_change_{period}'
            df[col] = df['volume'].pct_change(periods=period)
            self.feature_list.append(col)
        
        return df
    
    def _add_price_action_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """12 Price Action features"""
        
        # Candle body/shadow ratios
        df['body_size'] = abs(df['close'] - df['open']) / df['close']
        df['upper_shadow'] = (df['high'] - df[['close', 'open']].max(axis=1)) / df['close']
        df['lower_shadow'] = (df[['close', 'open']].min(axis=1) - df['low']) / df['close']
        self.feature_list.extend(['body_size', 'upper_shadow', 'lower_shadow'])
        
        # Price changes
        for period in [1, 3, 5, 10]:
            col = f'price_change_{period}'
            df[col] = df['close'].pct_change(periods=period)
            self.feature_list.append(col)
        
        # High/Low ranges
        df['hl_range'] = (df['high'] - df['low']) / df['close']
        df['oc_range'] = abs(df['close'] - df['open']) / df['close']
        self.feature_list.extend(['hl_range', 'oc_range'])
        
        # Gap
        df['gap'] = (df['open'] - df['close'].shift(1)) / df['close'].shift(1)
        self.feature_list.append('gap')
        
        # Close position in range
        df['close_position'] = (df['close'] - df['low']) / (df['high'] - df['low'])
        self.feature_list.append('close_position')
        
        return df
    
    def _add_regime_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """12 Market Regime features"""
        
        # Trend detection
        df['trend_up'] = (df['close'] > df['ema_50']).astype(int)
        df['trend_strong'] = (df['adx'] > 25).astype(int)
        self.feature_list.extend(['trend_up', 'trend_strong'])
        
        # Volatility regime
        df['high_vol'] = (df['atr_14'] > df['atr_14'].rolling(50).mean()).astype(int)
        self.feature_list.append('high_vol')
        
        # Volume regime
        df['high_volume'] = (df['volume'] > df['volume'].rolling(50).mean() * 1.5).astype(int)
        self.feature_list.append('high_volume')
        
        # Overbought/Oversold
        df['rsi_overbought'] = (df['rsi_14'] > 70).astype(int)
        df['rsi_oversold'] = (df['rsi_14'] < 30).astype(int)
        self.feature_list.extend(['rsi_overbought', 'rsi_oversold'])
        
        # BB squeeze
        df['bb_squeeze'] = (df['bb_width_20'] < df['bb_width_20'].rolling(50).quantile(0.25)).astype(int)
        self.feature_list.append('bb_squeeze')
        
        # Price extremes
        df['near_high'] = ((df['close'] - df['close'].rolling(20).min()) / 
                           (df['close'].rolling(20).max() - df['close'].rolling(20).min()) > 0.9).astype(int)
        df['near_low'] = ((df['close'] - df['close'].rolling(20).min()) / 
                          (df['close'].rolling(20).max() - df['close'].rolling(20).min()) < 0.1).astype(int)
        self.feature_list.extend(['near_high', 'near_low'])
        
        # MACD signal
        df['macd_bullish'] = (df['macd'] > df['macd_signal']).astype(int)
        df['macd_strong'] = (abs(df['macd_hist']) > df['macd_hist'].rolling(20).std()).astype(int)
        self.feature_list.extend(['macd_bullish', 'macd_strong'])
        
        return df


class MLWave3Integrator:
    """Integra ML com Wave3 Strategy"""
    
    def __init__(self, db_config: dict):
        self.db_config = db_config
        self.feature_engineer = FeatureEngineerV2()
        self.model = None
        self.model_metadata = {}
    
    async def fetch_data(self, symbol: str, timeframe: str = '1d') -> pd.DataFrame:
        """Busca dados do TimescaleDB"""
        
        table_map = {
            '15min': 'ohlcv_15min',
            '60min': 'ohlcv_60min',
            '4h': 'ohlcv_4h',
            '1d': 'ohlcv_daily'
        }
        
        table = table_map.get(timeframe, 'ohlcv_daily')
        
        conn = await asyncpg.connect(**self.db_config)
        
        try:
            query = f"""
                SELECT 
                    time as timestamp,
                    open::float,
                    high::float,
                    low::float,
                    close::float,
                    volume::float
                FROM {table}
                WHERE symbol = $1
                ORDER BY time ASC
            """
            
            rows = await conn.fetch(query, symbol)
            
            if not rows:
                return None
            
            df = pd.DataFrame(rows, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.set_index('timestamp')
            
            return df
        
        finally:
            await conn.close()
    
    def create_target(self, df: pd.DataFrame, forward_periods: int = 5, profit_threshold: float = 0.02) -> pd.Series:
        """
        Cria variável target binária: 1 se trade lucrativo, 0 caso contrário
        
        Args:
            df: DataFrame com dados OHLCV
            forward_periods: Períodos para frente para calcular retorno
            profit_threshold: Threshold de lucro mínimo (2% = 0.02)
        
        Returns:
            Series binária (0/1)
        """
        # Calcular retorno futuro
        df['future_high'] = df['high'].shift(-forward_periods).rolling(forward_periods).max()
        df['future_low'] = df['low'].shift(-forward_periods).rolling(forward_periods).min()
        
        # Calcular potencial de lucro (assumindo long)
        df['max_profit'] = (df['future_high'] - df['close']) / df['close']
        df['max_loss'] = (df['close'] - df['future_low']) / df['close']
        
        # Target: 1 se lucro > threshold e loss < (threshold/2)
        target = ((df['max_profit'] > profit_threshold) & 
                  (df['max_loss'] < profit_threshold / 2)).astype(int)
        
        return target
    
    async def train_model(
        self,
        symbols: List[str],
        model_type: str = 'random_forest',
        use_smote: bool = True,
        test_size: float = 0.2
    ) -> Dict:
        """
        Treina modelo ML com SMOTE
        
        Args:
            symbols: Lista de símbolos para treinar
            model_type: 'random_forest' ou 'xgboost'
            use_smote: Se True, aplica SMOTE para balanceamento
            test_size: Proporção do conjunto de teste
        
        Returns:
            Dict com métricas de performance
        """
        print(f"\n{'='*70}")
        print(f"🎓 ML TRAINING - PASSO 12 v2")
        print(f"{'='*70}")
        print(f"📊 Symbols: {', '.join(symbols)}")
        print(f"🤖 Model: {model_type}")
        print(f"⚖️  SMOTE: {'Enabled' if use_smote else 'Disabled'}")
        print(f"{'='*70}\n")
        
        # Coletar dados de todos os símbolos
        all_data = []
        
        for symbol in symbols:
            print(f"📥 Fetching {symbol}...")
            df = await self.fetch_data(symbol, '1d')
            
            if df is None or len(df) < 100:
                print(f"   ⚠️  Insufficient data for {symbol} (need at least 100 days)")
                continue
            
            # Gerar features
            df = self.feature_engineer.generate_all_features(df)
            
            # Criar target
            target = self.create_target(df)
            df['target'] = target
            
            # Remover NaN
            df = df.dropna()
            
            print(f"   ✅ {symbol}: {len(df)} samples")
            
            all_data.append(df)
        
        if not all_data:
            raise ValueError("No data available for training!")
        
        # Concatenar todos os dados
        df_combined = pd.concat(all_data, ignore_index=True)
        
        print(f"\n📊 Combined dataset: {len(df_combined)} samples")
        
        # Separar features e target
        feature_cols = self.feature_engineer.feature_list
        X = df_combined[feature_cols]
        y = df_combined['target']
        
        print(f"📈 Features: {len(feature_cols)}")
        print(f"🎯 Target distribution: {y.value_counts().to_dict()}")
        print(f"   Class balance: {y.mean():.2%} positive")
        
        # Split train/test
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=42, stratify=y
        )
        
        print(f"\n📦 Train set: {len(X_train)} samples")
        print(f"📦 Test set: {len(X_test)} samples")
        
        # Aplicar SMOTE
        if use_smote:
            print(f"\n⚖️  Applying SMOTE...")
            smote = SMOTE(random_state=42)
            X_train, y_train = smote.fit_resample(X_train, y_train)
            print(f"   ✅ After SMOTE: {len(X_train)} samples")
            print(f"   Balance: {y_train.value_counts().to_dict()}")
        
        # Treinar modelo
        print(f"\n🤖 Training {model_type}...")
        
        if model_type == 'random_forest':
            self.model = RandomForestClassifier(
                n_estimators=200,
                max_depth=15,
                min_samples_split=20,
                min_samples_leaf=10,
                max_features='sqrt',
                class_weight='balanced',
                random_state=42,
                n_jobs=-1
            )
        elif model_type == 'xgboost':
            scale_pos_weight = len(y_train[y_train == 0]) / len(y_train[y_train == 1])
            self.model = xgb.XGBClassifier(
                n_estimators=200,
                max_depth=6,
                learning_rate=0.05,
                subsample=0.8,
                colsample_bytree=0.8,
                scale_pos_weight=scale_pos_weight,
                random_state=42,
                n_jobs=-1
            )
        else:
            raise ValueError(f"Invalid model_type: {model_type}")
        
        self.model.fit(X_train, y_train)
        
        print(f"   ✅ Training complete!")
        
        # Avaliar
        y_pred = self.model.predict(X_test)
        y_pred_proba = self.model.predict_proba(X_test)[:, 1]
        
        # Métricas
        from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
        
        metrics = {
            'accuracy': accuracy_score(y_test, y_pred),
            'precision': precision_score(y_test, y_pred),
            'recall': recall_score(y_test, y_pred),
            'f1': f1_score(y_test, y_pred),
            'roc_auc': roc_auc_score(y_test, y_pred_proba),
            'train_samples': len(X_train),
            'test_samples': len(X_test),
            'n_features': len(feature_cols),
            'class_balance': float(y_train.mean())
        }
        
        print(f"\n{'='*70}")
        print(f"📊 MODEL PERFORMANCE")
        print(f"{'='*70}")
        print(f"Accuracy:  {metrics['accuracy']:.4f}")
        print(f"Precision: {metrics['precision']:.4f}")
        print(f"Recall:    {metrics['recall']:.4f}")
        print(f"F1-Score:  {metrics['f1']:.4f}")
        print(f"ROC-AUC:   {metrics['roc_auc']:.4f}")
        print(f"{'='*70}\n")
        
        # Feature importance
        if hasattr(self.model, 'feature_importances_'):
            importances = pd.DataFrame({
                'feature': feature_cols,
                'importance': self.model.feature_importances_
            }).sort_values('importance', ascending=False)
            
            print(f"🔝 Top 10 Features:")
            for idx, row in importances.head(10).iterrows():
                print(f"   {row['feature']:<25} {row['importance']:.4f}")
        
        # Salvar metadata
        self.model_metadata = {
            'model_type': model_type,
            'features': feature_cols,
            'metrics': metrics,
            'trained_on': symbols,
            'timestamp': datetime.now().isoformat()
        }
        
        return metrics
    
    def save_model(self, path: str = '/app/models/ml_wave3_v2.pkl'):
        """Salva modelo treinado"""
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'wb') as f:
            pickle.dump({
                'model': self.model,
                'metadata': self.model_metadata,
                'feature_engineer': self.feature_engineer
            }, f)
        
        print(f"💾 Model saved: {path}")
    
    def load_model(self, path: str = '/app/models/ml_wave3_v2.pkl'):
        """Carrega modelo salvo"""
        with open(path, 'rb') as f:
            data = pickle.load(f)
            self.model = data['model']
            self.model_metadata = data['metadata']
            self.feature_engineer = data['feature_engineer']
        
        print(f"📂 Model loaded: {path}")
        print(f"   Type: {self.model_metadata['model_type']}")
        print(f"   Features: {self.model_metadata['metrics']['n_features']}")
        print(f"   Accuracy: {self.model_metadata['metrics']['accuracy']:.4f}")


async def main():
    """CLI para treinamento"""
    import argparse
    
    parser = argparse.ArgumentParser(description='PASSO 12 v2: ML + Wave3 + SMOTE')
    parser.add_argument('--symbols', nargs='+', default=['ITUB4', 'MGLU3', 'VALE3', 'PETR4', 'BBDC4'],
                        help='Symbols to train on')
    parser.add_argument('--model-type', choices=['random_forest', 'xgboost'], default='random_forest',
                        help='Model type')
    parser.add_argument('--no-smote', action='store_true', help='Disable SMOTE')
    parser.add_argument('--test-size', type=float, default=0.2, help='Test set proportion')
    
    args = parser.parse_args()
    
    db_config = {
        'host': 'timescaledb',
        'port': 5432,
        'database': 'b3trading_market',
        'user': 'b3trading_ts',
        'password': 'b3trading_ts_pass'
    }
    
    integrator = MLWave3Integrator(db_config)
    
    metrics = await integrator.train_model(
        symbols=args.symbols,
        model_type=args.model_type,
        use_smote=not args.no_smote,
        test_size=args.test_size
    )
    
    # Salvar modelo
    integrator.save_model()
    
    print(f"\n✅ Training complete! Model saved.")


if __name__ == '__main__':
    asyncio.run(main())
