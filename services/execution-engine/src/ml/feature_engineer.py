"""
Feature Engineer para Machine Learning
B3 Trading Platform

Classe responsável por gerar features técnicas e fundamentalistas
para treinamento de modelos de ML.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from sklearn.preprocessing import RobustScaler
from sklearn.feature_selection import SelectKBest, mutual_info_classif


class FeatureEngineer:
    """
    Classe para engenharia de features para ML em trading.
    
    Cria features técnicas (momentum, volatilidade, tendência, volume)
    e features de regime de mercado para alimentar modelos de classificação.
    """
    
    def __init__(self, n_features: int = 20):
        """
        Inicializa o Feature Engineer.
        
        Args:
            n_features: Número de melhores features a selecionar (SelectKBest)
        """
        self.n_features = n_features
        self.scaler = RobustScaler()
        self.feature_selector: Optional[SelectKBest] = None
        self.selected_features: List[str] = []
        
    def create_all_features(
        self,
        df: pd.DataFrame,
        regime: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Cria todas as features técnicas e de regime.
        
        Args:
            df: DataFrame com OHLCV
            regime: Regime de mercado atual ('trending', 'ranging', 'volatile')
            
        Returns:
            DataFrame com todas as features
        """
        df = df.copy()
        
        # Features de Momentum
        df = self._add_momentum_features(df)
        
        # Features de Volatilidade
        df = self._add_volatility_features(df)
        
        # Features de Tendência
        df = self._add_trend_features(df)
        
        # Features de Volume
        df = self._add_volume_features(df)
        
        # Features de Padrões
        df = self._add_pattern_features(df)
        
        # Features de Regime
        if regime:
            df = self._add_regime_features(df, regime)
        
        return df
    
    def _add_momentum_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Adiciona features de momentum."""
        # RSI em múltiplos períodos
        for period in [7, 14, 21]:
            df[f'rsi_{period}'] = self._calculate_rsi(df['close'], period)
        
        # ROC (Rate of Change)
        for period in [5, 10, 20]:
            df[f'roc_{period}'] = df['close'].pct_change(period) * 100
        
        # Stochastic Oscillator
        df['stoch_k'] = self._calculate_stochastic(df, 14)
        df['stoch_d'] = df['stoch_k'].rolling(window=3).mean()
        
        # Williams %R
        df['williams_r'] = self._calculate_williams_r(df, 14)
        
        # Momentum absoluto
        df['momentum'] = df['close'] - df['close'].shift(10)
        
        return df
    
    def _add_volatility_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Adiciona features de volatilidade."""
        # ATR (Average True Range)
        df['atr_14'] = self._calculate_atr(df, 14)
        df['atr_20'] = self._calculate_atr(df, 20)
        
        # Bollinger Bands
        for period in [20, 30]:
            df[f'bb_width_{period}'] = self._calculate_bb_width(df['close'], period)
            df[f'bb_position_{period}'] = self._calculate_bb_position(df['close'], period)
        
        # Volatilidade histórica
        df['volatility_10'] = df['close'].pct_change().rolling(window=10).std() * np.sqrt(252)
        df['volatility_20'] = df['close'].pct_change().rolling(window=20).std() * np.sqrt(252)
        
        # Parkinson's Historical Volatility
        df['parkinson_vol'] = self._calculate_parkinson_volatility(df, 20)
        
        return df
    
    def _add_trend_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Adiciona features de tendência."""
        # EMAs
        for period in [9, 21, 50, 200]:
            df[f'ema_{period}'] = df['close'].ewm(span=period, adjust=False).mean()
        
        # Distância do preço às EMAs (normalizada)
        for period in [21, 50]:
            df[f'dist_ema_{period}'] = (df['close'] - df[f'ema_{period}']) / df[f'ema_{period}'] * 100
        
        # MACD
        ema_12 = df['close'].ewm(span=12, adjust=False).mean()
        ema_26 = df['close'].ewm(span=26, adjust=False).mean()
        df['macd'] = ema_12 - ema_26
        df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
        df['macd_hist'] = df['macd'] - df['macd_signal']
        
        # ADX (Average Directional Index)
        df = self._add_adx(df, 14)
        
        # Aroon Indicator
        df['aroon_up'], df['aroon_down'] = self._calculate_aroon(df, 25)
        df['aroon_osc'] = df['aroon_up'] - df['aroon_down']
        
        # Linear Regression Slope
        df['lr_slope_20'] = self._calculate_linear_regression_slope(df['close'], 20)
        
        return df
    
    def _add_volume_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Adiciona features de volume."""
        # Volume SMA
        df['volume_sma_20'] = df['volume'].rolling(window=20).mean()
        df['volume_ratio'] = df['volume'] / df['volume_sma_20']
        
        # OBV (On-Balance Volume)
        df['obv'] = self._calculate_obv(df)
        df['obv_ema'] = df['obv'].ewm(span=20, adjust=False).mean()
        
        # VWAP (Volume Weighted Average Price)
        df['vwap'] = self._calculate_vwap(df)
        df['dist_vwap'] = (df['close'] - df['vwap']) / df['vwap'] * 100
        
        # MFI (Money Flow Index)
        df['mfi'] = self._calculate_mfi(df, 14)
        
        # Volume Price Trend
        df['vpt'] = self._calculate_vpt(df)
        
        return df
    
    def _add_pattern_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Adiciona features baseadas em padrões."""
        # Candlestick patterns
        df['body_size'] = abs(df['close'] - df['open']) / df['open'] * 100
        df['upper_shadow'] = (df['high'] - df[['close', 'open']].max(axis=1)) / df['open'] * 100
        df['lower_shadow'] = (df[['close', 'open']].min(axis=1) - df['low']) / df['open'] * 100
        
        # Doji detection
        df['is_doji'] = (df['body_size'] < 0.1).astype(int)
        
        # Hammer detection
        df['is_hammer'] = ((df['lower_shadow'] > 2 * df['body_size']) & 
                           (df['upper_shadow'] < df['body_size'])).astype(int)
        
        # Engulfing pattern (simplified)
        df['bullish_engulfing'] = ((df['close'] > df['open']) & 
                                   (df['close'].shift(1) < df['open'].shift(1)) &
                                   (df['close'] > df['open'].shift(1)) &
                                   (df['open'] < df['close'].shift(1))).astype(int)
        
        # Higher highs, lower lows
        df['higher_high'] = (df['high'] > df['high'].shift(1)).astype(int)
        df['lower_low'] = (df['low'] < df['low'].shift(1)).astype(int)
        
        # Price position in day's range
        df['price_position'] = (df['close'] - df['low']) / (df['high'] - df['low'] + 1e-10)
        
        return df
    
    def _add_regime_features(self, df: pd.DataFrame, regime: str) -> pd.DataFrame:
        """
        Adiciona features one-hot encoded de regime de mercado.
        
        Args:
            df: DataFrame
            regime: 'trending', 'ranging', ou 'volatile'
        """
        df['regime_trending'] = int(regime == 'trending')
        df['regime_ranging'] = int(regime == 'ranging')
        df['regime_volatile'] = int(regime == 'volatile')
        
        return df
    
    def _add_adx(self, df: pd.DataFrame, period: int) -> pd.DataFrame:
        """Calcula ADX (Average Directional Index)."""
        high = df['high']
        low = df['low']
        close = df['close']
        
        # True Range
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        
        # Directional Movement
        up_move = high - high.shift(1)
        down_move = low.shift(1) - low
        
        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)
        
        plus_di = 100 * pd.Series(plus_dm).rolling(window=period).mean() / atr
        minus_di = 100 * pd.Series(minus_dm).rolling(window=period).mean() / atr
        
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)
        df['adx'] = dx.rolling(window=period).mean()
        df['plus_di'] = plus_di
        df['minus_di'] = minus_di
        
        return df
    
    # Métodos auxiliares de cálculo
    def _calculate_rsi(self, series: pd.Series, period: int) -> pd.Series:
        """Calcula RSI."""
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / (loss + 1e-10)
        return 100 - (100 / (1 + rs))
    
    def _calculate_stochastic(self, df: pd.DataFrame, period: int) -> pd.Series:
        """Calcula Stochastic Oscillator %K."""
        low_min = df['low'].rolling(window=period).min()
        high_max = df['high'].rolling(window=period).max()
        return 100 * (df['close'] - low_min) / (high_max - low_min + 1e-10)
    
    def _calculate_williams_r(self, df: pd.DataFrame, period: int) -> pd.Series:
        """Calcula Williams %R."""
        high_max = df['high'].rolling(window=period).max()
        low_min = df['low'].rolling(window=period).min()
        return -100 * (high_max - df['close']) / (high_max - low_min + 1e-10)
    
    def _calculate_atr(self, df: pd.DataFrame, period: int) -> pd.Series:
        """Calcula ATR."""
        high_low = df['high'] - df['low']
        high_close = abs(df['high'] - df['close'].shift(1))
        low_close = abs(df['low'] - df['close'].shift(1))
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        return tr.rolling(window=period).mean()
    
    def _calculate_bb_width(self, series: pd.Series, period: int) -> pd.Series:
        """Calcula largura das Bollinger Bands."""
        sma = series.rolling(window=period).mean()
        std = series.rolling(window=period).std()
        return (4 * std) / sma * 100
    
    def _calculate_bb_position(self, series: pd.Series, period: int) -> pd.Series:
        """Calcula posição do preço nas Bollinger Bands."""
        sma = series.rolling(window=period).mean()
        std = series.rolling(window=period).std()
        upper = sma + (2 * std)
        lower = sma - (2 * std)
        return (series - lower) / (upper - lower + 1e-10)
    
    def _calculate_parkinson_volatility(self, df: pd.DataFrame, period: int) -> pd.Series:
        """Calcula volatilidade de Parkinson."""
        hl_ratio = np.log(df['high'] / df['low'])
        return np.sqrt((1 / (4 * np.log(2))) * hl_ratio ** 2).rolling(window=period).mean()
    
    def _calculate_aroon(self, df: pd.DataFrame, period: int) -> Tuple[pd.Series, pd.Series]:
        """Calcula Aroon Up e Aroon Down."""
        aroon_up = df['high'].rolling(window=period).apply(
            lambda x: float(period - x.argmax()) / period * 100, raw=False
        )
        aroon_down = df['low'].rolling(window=period).apply(
            lambda x: float(period - x.argmin()) / period * 100, raw=False
        )
        return aroon_up, aroon_down
    
    def _calculate_linear_regression_slope(self, series: pd.Series, period: int) -> pd.Series:
        """Calcula inclinação da regressão linear."""
        def slope(y):
            if len(y) < 2:
                return 0
            x = np.arange(len(y))
            return np.polyfit(x, y, 1)[0]
        
        return series.rolling(window=period).apply(slope, raw=False)
    
    def _calculate_obv(self, df: pd.DataFrame) -> pd.Series:
        """Calcula On-Balance Volume."""
        obv = (np.sign(df['close'].diff()) * df['volume']).fillna(0).cumsum()
        return obv
    
    def _calculate_vwap(self, df: pd.DataFrame) -> pd.Series:
        """Calcula VWAP."""
        typical_price = (df['high'] + df['low'] + df['close']) / 3
        return (typical_price * df['volume']).cumsum() / df['volume'].cumsum()
    
    def _calculate_mfi(self, df: pd.DataFrame, period: int) -> pd.Series:
        """Calcula Money Flow Index."""
        typical_price = (df['high'] + df['low'] + df['close']) / 3
        money_flow = typical_price * df['volume']
        
        positive_flow = money_flow.where(typical_price > typical_price.shift(1), 0)
        negative_flow = money_flow.where(typical_price < typical_price.shift(1), 0)
        
        positive_mf = positive_flow.rolling(window=period).sum()
        negative_mf = negative_flow.rolling(window=period).sum()
        
        mfi = 100 - (100 / (1 + positive_mf / (negative_mf + 1e-10)))
        return mfi
    
    def _calculate_vpt(self, df: pd.DataFrame) -> pd.Series:
        """Calcula Volume Price Trend."""
        vpt = (df['volume'] * df['close'].pct_change()).cumsum()
        return vpt
    
    def normalize_features(
        self,
        df: pd.DataFrame,
        feature_columns: Optional[List[str]] = None,
        fit: bool = True
    ) -> pd.DataFrame:
        """
        Normaliza features usando RobustScaler.
        
        Args:
            df: DataFrame com features
            feature_columns: Colunas a normalizar (None = todas numéricas)
            fit: Se True, ajusta o scaler aos dados
            
        Returns:
            DataFrame com features normalizadas
        """
        df = df.copy()
        
        if feature_columns is None:
            feature_columns = df.select_dtypes(include=[np.number]).columns.tolist()
            # Excluir colunas OHLCV originais
            feature_columns = [c for c in feature_columns 
                             if c not in ['open', 'high', 'low', 'close', 'volume']]
        
        # Substituir inf/-inf por NaN e depois preencher com 0
        df[feature_columns] = df[feature_columns].replace([np.inf, -np.inf], np.nan).fillna(0)
        
        if fit:
            df[feature_columns] = self.scaler.fit_transform(df[feature_columns])
        else:
            df[feature_columns] = self.scaler.transform(df[feature_columns])
        
        return df
    
    def select_best_features(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        n_features: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Seleciona as melhores features usando mutual information.
        
        Args:
            X: Features
            y: Target (labels)
            n_features: Número de features a selecionar (None = usar self.n_features)
            
        Returns:
            DataFrame com features selecionadas
        """
        if n_features is None:
            n_features = self.n_features
        
        self.feature_selector = SelectKBest(score_func=mutual_info_classif, k=n_features)
        X_selected = self.feature_selector.fit_transform(X, y)
        
        # Obter nomes das features selecionadas
        mask = self.feature_selector.get_support()
        self.selected_features = X.columns[mask].tolist()
        
        return pd.DataFrame(X_selected, columns=self.selected_features, index=X.index)
    
    def get_feature_importance(self) -> Optional[Dict[str, float]]:
        """
        Retorna importância das features selecionadas.
        
        Returns:
            Dicionário com scores de importância
        """
        if self.feature_selector is None:
            return None
        
        scores = self.feature_selector.scores_
        mask = self.feature_selector.get_support()
        
        importance = {}
        for i, feature in enumerate(self.selected_features):
            original_idx = np.where(mask)[0][i]
            importance[feature] = float(scores[original_idx])
        
        return dict(sorted(importance.items(), key=lambda x: x[1], reverse=True))
