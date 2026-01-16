"""
Feature Engineering Module for ML Trading Signals
==================================================

Generates technical indicators and features for machine learning models.
Designed to enhance trading signal quality through pattern recognition.

Author: B3 Trading Platform
Date: 15 de Janeiro de 2026
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional


class FeatureEngineer:
    """
    Feature engineering for trading signals
    
    Generates comprehensive technical features including:
    - Trend indicators (EMAs, MACD, ADX)
    - Momentum indicators (RSI, Stochastic, ROC)
    - Volatility indicators (ATR, Bollinger Bands)
    - Volume indicators
    - Pattern recognition features
    - Market regime features
    """
    
    def __init__(self):
        self.feature_names = []
    
    def generate_all_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generate all technical features for ML model
        
        Args:
            df: DataFrame with columns ['open', 'high', 'low', 'close', 'volume']
        
        Returns:
            DataFrame with all features added
        """
        df = df.copy()
        
        # 1. Trend Features
        df = self._add_trend_features(df)
        
        # 2. Momentum Features
        df = self._add_momentum_features(df)
        
        # 3. Volatility Features
        df = self._add_volatility_features(df)
        
        # 4. Volume Features
        df = self._add_volume_features(df)
        
        # 5. Pattern Features
        df = self._add_pattern_features(df)
        
        # 6. Market Regime Features
        df = self._add_regime_features(df)
        
        # 7. Price Action Features
        df = self._add_price_action_features(df)
        
        # 8. Statistical Features
        df = self._add_statistical_features(df)
        
        return df
    
    def _add_trend_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add trend-based features"""
        
        # EMAs (multiple periods)
        for period in [9, 17, 21, 50, 72, 200]:
            df[f'ema_{period}'] = df['close'].ewm(span=period, adjust=False).mean()
            df[f'close_vs_ema_{period}'] = (df['close'] - df[f'ema_{period}']) / df[f'ema_{period}']
        
        # EMA crossovers
        df['ema9_vs_ema21'] = (df['ema_9'] > df['ema_21']).astype(int)
        df['ema9_vs_ema50'] = (df['ema_9'] > df['ema_50']).astype(int)
        df['ema21_vs_ema50'] = (df['ema_21'] > df['ema_50']).astype(int)
        df['ema50_vs_ema200'] = (df['ema_50'] > df['ema_200']).astype(int)
        
        # MACD (12, 26, 9)
        ema_12 = df['close'].ewm(span=12, adjust=False).mean()
        ema_26 = df['close'].ewm(span=26, adjust=False).mean()
        df['macd'] = ema_12 - ema_26
        df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
        df['macd_hist'] = df['macd'] - df['macd_signal']
        df['macd_bullish'] = (df['macd'] > df['macd_signal']).astype(int)
        
        # ADX (14-period - simplified version)
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        df['tr'] = np.maximum(high_low, np.maximum(high_close, low_close))
        df['atr_14'] = df['tr'].rolling(14).mean()
        
        df['dmp'] = np.where((df['high'] - df['high'].shift()) > (df['low'].shift() - df['low']),
                            np.maximum(df['high'] - df['high'].shift(), 0), 0)
        df['dmn'] = np.where((df['low'].shift() - df['low']) > (df['high'] - df['high'].shift()),
                            np.maximum(df['low'].shift() - df['low'], 0), 0)
        
        dmp_14 = df['dmp'].rolling(14).mean()
        dmn_14 = df['dmn'].rolling(14).mean()
        dx = 100 * np.abs(dmp_14 - dmn_14) / (dmp_14 + dmn_14 + 1e-10)
        df['adx'] = dx.rolling(14).mean()
        df['adx_strong_trend'] = (df['adx'] > 25).astype(int)
        
        return df
    
    def _add_momentum_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add momentum-based features"""
        
        # RSI (multiple periods)
        for period in [7, 14, 21]:
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / (loss + 1e-10)
            df[f'rsi_{period}'] = 100 - (100 / (1 + rs))
            df[f'rsi_{period}_oversold'] = (df[f'rsi_{period}'] < 30).astype(int)
            df[f'rsi_{period}_overbought'] = (df[f'rsi_{period}'] > 70).astype(int)
        
        # Stochastic
        low_14 = df['low'].rolling(14).min()
        high_14 = df['high'].rolling(14).max()
        df['stoch_k'] = 100 * (df['close'] - low_14) / (high_14 - low_14 + 1e-10)
        df['stoch_d'] = df['stoch_k'].rolling(3).mean()
        df['stoch_oversold'] = (df['stoch_k'] < 20).astype(int)
        df['stoch_overbought'] = (df['stoch_k'] > 80).astype(int)
        
        # ROC (Rate of Change)
        for period in [5, 10, 20]:
            df[f'roc_{period}'] = df['close'].pct_change(period) * 100
        
        # CCI (Commodity Channel Index)
        tp = (df['high'] + df['low'] + df['close']) / 3
        tp_sma = tp.rolling(20).mean()
        mad = (tp - tp_sma).abs().rolling(20).mean()
        df['cci'] = (tp - tp_sma) / (0.015 * mad + 1e-10)
        
        # Williams %R
        high_14 = df['high'].rolling(14).max()
        low_14 = df['low'].rolling(14).min()
        df['willr'] = -100 * (high_14 - df['close']) / (high_14 - low_14 + 1e-10)
        
        return df
    
    def _add_volatility_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add volatility-based features"""
        
        # Use ATR already calculated in trend features
        for period in [7, 14, 21]:
            df[f'atr_{period}'] = df['tr'].rolling(period).mean()
            df[f'atr_{period}_pct'] = df[f'atr_{period}'] / df['close']
        
        # Bollinger Bands
        df['bb_middle'] = df['close'].rolling(20).mean()
        bb_std = df['close'].rolling(20).std()
        df['bb_upper'] = df['bb_middle'] + (bb_std * 2)
        df['bb_lower'] = df['bb_middle'] - (bb_std * 2)
        df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / (df['bb_middle'] + 1e-10)
        df['bb_position'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'] + 1e-10)
        df['bb_squeeze'] = (df['bb_width'] < df['bb_width'].rolling(20).mean() * 0.7).astype(int)
        
        # Keltner Channels (simplified using ATR)
        ema_20 = df['close'].ewm(span=20, adjust=False).mean()
        df['kc_middle'] = ema_20
        df['kc_upper'] = ema_20 + (df['atr_14'] * 2)
        df['kc_lower'] = ema_20 - (df['atr_14'] * 2)
        
        # Historical Volatility
        df['hist_vol_10'] = df['close'].pct_change().rolling(10).std() * np.sqrt(252)
        df['hist_vol_20'] = df['close'].pct_change().rolling(20).std() * np.sqrt(252)
        
        return df
    
    def _add_volume_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add volume-based features"""
        
        # Volume SMA
        df['volume_sma_20'] = df['volume'].rolling(20).mean()
        df['volume_ratio'] = df['volume'] / (df['volume_sma_20'] + 1e-10)
        df['volume_spike'] = (df['volume_ratio'] > 1.5).astype(int)
        
        # OBV (On Balance Volume)
        df['obv'] = (np.sign(df['close'].diff()) * df['volume']).fillna(0).cumsum()
        df['obv_sma'] = df['obv'].rolling(20).mean()
        df['obv_bullish'] = (df['obv'] > df['obv_sma']).astype(int)
        
        # Volume Price Trend
        df['vpt'] = (df['volume'] * df['close'].pct_change()).fillna(0).cumsum()
        
        # Force Index
        df['force_index'] = (df['close'] - df['close'].shift(1)) * df['volume']
        df['force_index_13'] = df['force_index'].ewm(span=13, adjust=False).mean()
        
        # Ease of Movement
        distance = ((df['high'] + df['low']) / 2).diff()
        box_ratio = (df['volume'] / 1e6) / (df['high'] - df['low'] + 1e-10)
        df['eom'] = distance / (box_ratio + 1e-10)
        
        return df
    
    def _add_pattern_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add candlestick pattern features"""
        
        # Candle body and wicks
        df['candle_body'] = abs(df['close'] - df['open'])
        df['upper_wick'] = df['high'] - df[['open', 'close']].max(axis=1)
        df['lower_wick'] = df[['open', 'close']].min(axis=1) - df['low']
        df['body_ratio'] = df['candle_body'] / (df['high'] - df['low'] + 1e-10)
        
        # Candle patterns
        df['bullish_candle'] = df['close'] > df['open']
        df['bearish_candle'] = df['close'] < df['open']
        df['doji'] = df['body_ratio'] < 0.1
        
        # Hammer pattern
        df['hammer'] = (
            (df['lower_wick'] > df['candle_body'] * 2) &
            (df['upper_wick'] < df['candle_body'] * 0.3) &
            (df['close'] > df['open'])
        )
        
        # Shooting star pattern
        df['shooting_star'] = (
            (df['upper_wick'] > df['candle_body'] * 2) &
            (df['lower_wick'] < df['candle_body'] * 0.3) &
            (df['close'] < df['open'])
        )
        
        # Engulfing patterns
        df['bullish_engulfing'] = (
            (df['close'] > df['open']) &
            (df['close'].shift(1) < df['open'].shift(1)) &
            (df['open'] < df['close'].shift(1)) &
            (df['close'] > df['open'].shift(1))
        )
        
        df['bearish_engulfing'] = (
            (df['close'] < df['open']) &
            (df['close'].shift(1) > df['open'].shift(1)) &
            (df['open'] > df['close'].shift(1)) &
            (df['close'] < df['open'].shift(1))
        )
        
        return df
    
    def _add_regime_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add market regime features"""
        
        # Trend regime (based on EMAs)
        df['price_above_ema200'] = df['close'] > df['ema_200']
        df['ema50_above_ema200'] = df['ema_50'] > df['ema_200']
        
        df['regime_trend'] = 'neutral'
        df.loc[df['price_above_ema200'] & df['ema50_above_ema200'], 'regime_trend'] = 'uptrend'
        df.loc[~df['price_above_ema200'] & ~df['ema50_above_ema200'], 'regime_trend'] = 'downtrend'
        
        # Volatility regime
        df['volatility_regime'] = 'normal'
        df.loc[df['atr_14_pct'] > df['atr_14_pct'].rolling(50).quantile(0.75), 'volatility_regime'] = 'high'
        df.loc[df['atr_14_pct'] < df['atr_14_pct'].rolling(50).quantile(0.25), 'volatility_regime'] = 'low'
        
        # Volume regime
        df['volume_regime'] = 'normal'
        df.loc[df['volume_ratio'] > 1.5, 'volume_regime'] = 'high'
        df.loc[df['volume_ratio'] < 0.7, 'volume_regime'] = 'low'
        
        return df
    
    def _add_price_action_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add price action features"""
        
        # Higher highs and higher lows
        df['higher_high'] = (df['high'] > df['high'].shift(1)) & (df['high'].shift(1) > df['high'].shift(2))
        df['higher_low'] = (df['low'] > df['low'].shift(1)) & (df['low'].shift(1) > df['low'].shift(2))
        df['lower_high'] = (df['high'] < df['high'].shift(1)) & (df['high'].shift(1) < df['high'].shift(2))
        df['lower_low'] = (df['low'] < df['low'].shift(1)) & (df['low'].shift(1) < df['low'].shift(2))
        
        # Support and resistance (simplified)
        df['resistance_20'] = df['high'].rolling(20).max()
        df['support_20'] = df['low'].rolling(20).min()
        df['near_resistance'] = (df['high'] / df['resistance_20']) > 0.98
        df['near_support'] = (df['low'] / df['support_20']) < 1.02
        
        # Gap detection
        df['gap_up'] = df['low'] > df['high'].shift(1)
        df['gap_down'] = df['high'] < df['low'].shift(1)
        
        # Consecutive candles
        df['consec_bullish'] = (df['close'] > df['open']).rolling(3).sum()
        df['consec_bearish'] = (df['close'] < df['open']).rolling(3).sum()
        
        return df
    
    def _add_statistical_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add statistical features"""
        
        # Returns
        df['return_1d'] = df['close'].pct_change(1)
        df['return_5d'] = df['close'].pct_change(5)
        df['return_10d'] = df['close'].pct_change(10)
        df['return_20d'] = df['close'].pct_change(20)
        
        # Rolling statistics
        for window in [5, 10, 20]:
            df[f'mean_{window}d'] = df['close'].rolling(window).mean()
            df[f'std_{window}d'] = df['close'].rolling(window).std()
            df[f'skew_{window}d'] = df['close'].rolling(window).skew()
            df[f'kurt_{window}d'] = df['close'].rolling(window).kurt()
        
        # Z-score
        df['zscore_20'] = (df['close'] - df['mean_20d']) / (df['std_20d'] + 1e-10)
        
        # Distance from high/low
        df['dist_from_52w_high'] = (df['high'].rolling(252).max() - df['close']) / df['close']
        df['dist_from_52w_low'] = (df['close'] - df['low'].rolling(252).min()) / df['close']
        
        return df
    
    def get_feature_importance_groups(self) -> Dict[str, List[str]]:
        """
        Return feature groups for importance analysis
        
        Returns:
            Dictionary with feature categories and their column names
        """
        return {
            'trend': ['ema_', 'macd', 'adx', 'psar'],
            'momentum': ['rsi_', 'stoch_', 'roc_', 'cci', 'willr', 'mfi'],
            'volatility': ['atr_', 'bb_', 'kc_', 'hist_vol'],
            'volume': ['volume_', 'obv', 'vpt', 'force_index', 'eom'],
            'pattern': ['candle_', 'hammer', 'shooting_star', 'engulfing'],
            'regime': ['regime_', 'price_above', 'ema50_above'],
            'price_action': ['higher_', 'lower_', 'near_', 'gap_', 'consec_'],
            'statistical': ['return_', 'mean_', 'std_', 'zscore', 'dist_from']
        }
    
    def select_features(self, df: pd.DataFrame, top_n: int = 50) -> List[str]:
        """
        Select top N most important features
        
        Args:
            df: DataFrame with all features
            top_n: Number of features to select
        
        Returns:
            List of selected feature names
        """
        # Remove non-numeric columns
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        
        # Remove target and identifier columns
        exclude = ['open', 'high', 'low', 'close', 'volume', 'timestamp', 'symbol']
        feature_cols = [col for col in numeric_cols if col not in exclude]
        
        # Return top_n features (in practice, should use feature importance from trained model)
        return feature_cols[:top_n] if len(feature_cols) > top_n else feature_cols


def create_target_variable(df: pd.DataFrame, forward_periods: int = 5, 
                          profit_threshold: float = 0.02) -> pd.DataFrame:
    """
    Create target variable for ML classification
    
    Args:
        df: DataFrame with OHLCV data
        forward_periods: Look-forward period for calculating returns
        profit_threshold: Minimum return to classify as profitable trade
    
    Returns:
        DataFrame with target variable added
    """
    df = df.copy()
    
    # Calculate forward returns
    df['forward_return'] = df['close'].shift(-forward_periods) / df['close'] - 1
    
    # Create binary target (1 = profitable, 0 = not profitable)
    df['target'] = (df['forward_return'] > profit_threshold).astype(int)
    
    # Remove last rows where we don't have forward returns
    df = df[:-forward_periods]
    
    return df
