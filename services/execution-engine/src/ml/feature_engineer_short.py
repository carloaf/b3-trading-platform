#!/usr/bin/env python3
"""
Feature Engineer - Short Windows Version
========================================

Versão modificada do FeatureEngineerV2 para Walk-Forward Optimization
com datasets limitados (250 dias).

MODIFICAÇÕES:
- Remove EMA/SMA 200, 100, 72 (muito longos)
- Usa apenas janelas ≤50 dias
- Mantém 70+ features com warm-up máximo de 50 dias

Author: B3 Trading Platform
Date: 16 de Janeiro de 2026
"""

import pandas as pd
from ta.trend import EMAIndicator, SMAIndicator, MACD, ADXIndicator
from ta.momentum import RSIIndicator, StochasticOscillator, ROCIndicator
from ta.volatility import BollingerBands, AverageTrueRange
from ta.volume import OnBalanceVolumeIndicator, MFIIndicator


class FeatureEngineerShort:
    """
    Feature Engineering com janelas curtas (max 50 dias)
    Para Walk-Forward com datasets limitados
    """
    
    def __init__(self):
        self.feature_list = []
    
    def generate_all_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Gera 70+ features para ML (janelas ≤50 dias)
        
        Categorias:
        - Trend (20 features) - max window 50
        - Momentum (20 features) - max window 21
        - Volatility (15 features) - max window 20
        - Volume (10 features) - max window 20
        - Price Action (10 features) - max window 20
        """
        print(f"   📊 Generating 70+ features (short windows)...")
        
        df = df.copy()
        
        # 1. TREND FEATURES (20) - max window 50
        df = self._add_trend_features(df)
        
        # 2. MOMENTUM FEATURES (20) - max window 21
        df = self._add_momentum_features(df)
        
        # 3. VOLATILITY FEATURES (15) - max window 20
        df = self._add_volatility_features(df)
        
        # 4. VOLUME FEATURES (10) - max window 20
        df = self._add_volume_features(df)
        
        # 5. PRICE ACTION FEATURES (10) - max window 20
        df = self._add_price_action_features(df)
        
        # Drop NaN (initial periods - máximo 50 dias)
        initial_len = len(df)
        df = df.dropna()
        print(f"   ✅ Features generated: {len(self.feature_list)} features")
        print(f"   📉 Dropped {initial_len - len(df)} initial NaN rows")
        
        return df
    
    def _add_trend_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """20 Trend features (max window 50)"""
        
        # EMAs (períodos curtos/médios apenas)
        for period in [5, 8, 9, 13, 17, 20, 21, 50]:
            col = f'ema_{period}'
            ema = EMAIndicator(df['close'], window=period)
            df[col] = ema.ema_indicator()
            self.feature_list.append(col)
        
        # SMA
        for period in [20, 50]:
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
        for period in [20, 50]:
            col = f'price_vs_ema_{period}'
            df[col] = (df['close'] - df[f'ema_{period}']) / df[f'ema_{period}']
            self.feature_list.append(col)
        
        return df
    
    def _add_momentum_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """20 Momentum features (max window 21)"""
        
        # RSI (múltiplos períodos)
        for period in [7, 14, 21]:
            col = f'rsi_{period}'
            rsi = RSIIndicator(df['close'], window=period)
            df[col] = rsi.rsi()
            self.feature_list.append(col)
        
        # Stochastic
        stoch = StochasticOscillator(df['high'], df['low'], df['close'], window=14, smooth_window=3)
        df['stoch_k'] = stoch.stoch()
        df['stoch_d'] = stoch.stoch_signal()
        self.feature_list.extend(['stoch_k', 'stoch_d'])
        
        # ROC (Rate of Change)
        for period in [5, 10, 20]:
            col = f'roc_{period}'
            roc = ROCIndicator(df['close'], window=period)
            df[col] = roc.roc()
            self.feature_list.append(col)
        
        # Price momentum
        for period in [3, 5, 10, 20]:
            col = f'momentum_{period}'
            df[col] = df['close'].pct_change(periods=period)
            self.feature_list.append(col)
        
        # Acceleration
        for period in [5, 10]:
            col = f'acceleration_{period}'
            df[col] = df['close'].diff(period).diff()
            self.feature_list.append(col)
        
        # High-Low momentum
        df['hl_momentum'] = (df['high'] - df['low']) / df['low']
        self.feature_list.append('hl_momentum')
        
        # Close position in range
        df['close_position'] = (df['close'] - df['low']) / (df['high'] - df['low'] + 1e-10)
        self.feature_list.append('close_position')
        
        return df
    
    def _add_volatility_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """15 Volatility features (max window 20)"""
        
        # Bollinger Bands
        for window in [10, 20]:
            bb = BollingerBands(df['close'], window=window, window_dev=2)
            df[f'bb_upper_{window}'] = bb.bollinger_hband()
            df[f'bb_lower_{window}'] = bb.bollinger_lband()
            df[f'bb_width_{window}'] = bb.bollinger_wband()
            df[f'bb_pct_{window}'] = bb.bollinger_pband()
            self.feature_list.extend([
                f'bb_upper_{window}', f'bb_lower_{window}',
                f'bb_width_{window}', f'bb_pct_{window}'
            ])
        
        # ATR
        atr = AverageTrueRange(df['high'], df['low'], df['close'], window=14)
        df['atr'] = atr.average_true_range()
        df['atr_pct'] = df['atr'] / df['close']
        self.feature_list.extend(['atr', 'atr_pct'])
        
        # Historical Volatility
        for period in [10, 20]:
            col = f'volatility_{period}'
            df[col] = df['close'].pct_change().rolling(period).std()
            self.feature_list.append(col)
        
        # High-Low range
        df['hl_range'] = (df['high'] - df['low']) / df['close']
        df['hl_range_ma'] = df['hl_range'].rolling(10).mean()
        self.feature_list.extend(['hl_range', 'hl_range_ma'])
        
        return df
    
    def _add_volume_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """10 Volume features (max window 20)"""
        
        # Volume change
        df['volume_change'] = df['volume'].pct_change()
        df['volume_ma_ratio'] = df['volume'] / df['volume'].rolling(20).mean()
        self.feature_list.extend(['volume_change', 'volume_ma_ratio'])
        
        # OBV
        obv = OnBalanceVolumeIndicator(df['close'], df['volume'])
        df['obv'] = obv.on_balance_volume()
        df['obv_ma'] = df['obv'].rolling(10).mean()
        self.feature_list.extend(['obv', 'obv_ma'])
        
        # MFI
        mfi = MFIIndicator(df['high'], df['low'], df['close'], df['volume'], window=14)
        df['mfi'] = mfi.money_flow_index()
        self.feature_list.append('mfi')
        
        # Price-Volume correlation
        df['pv_corr'] = df['close'].rolling(20).corr(df['volume'])
        self.feature_list.append('pv_corr')
        
        # Volume Weighted Average Price (VWAP approximation)
        df['vwap'] = (df['volume'] * (df['high'] + df['low'] + df['close']) / 3).rolling(20).sum() / df['volume'].rolling(20).sum()
        df['price_vs_vwap'] = (df['close'] - df['vwap']) / df['vwap']
        self.feature_list.extend(['vwap', 'price_vs_vwap'])
        
        return df
    
    def _add_price_action_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """10 Price Action features (max window 20)"""
        
        # Candle body/shadow ratios
        df['body_size'] = abs(df['close'] - df['open']) / df['close']
        df['upper_shadow'] = (df['high'] - df[['open', 'close']].max(axis=1)) / df['close']
        df['lower_shadow'] = (df[['open', 'close']].min(axis=1) - df['low']) / df['close']
        self.feature_list.extend(['body_size', 'upper_shadow', 'lower_shadow'])
        
        # Distance from High/Low
        df['dist_from_high_20'] = (df['high'].rolling(20).max() - df['close']) / df['close']
        df['dist_from_low_20'] = (df['close'] - df['low'].rolling(20).min()) / df['close']
        self.feature_list.extend(['dist_from_high_20', 'dist_from_low_20'])
        
        # Price patterns
        df['higher_high'] = ((df['high'] > df['high'].shift(1)) & (df['high'].shift(1) > df['high'].shift(2))).astype(int)
        df['lower_low'] = ((df['low'] < df['low'].shift(1)) & (df['low'].shift(1) < df['low'].shift(2))).astype(int)
        self.feature_list.extend(['higher_high', 'lower_low'])
        
        # Gap detection
        df['gap_up'] = (df['low'] > df['high'].shift(1)).astype(int)
        df['gap_down'] = (df['high'] < df['low'].shift(1)).astype(int)
        self.feature_list.extend(['gap_up', 'gap_down'])
        
        return df
