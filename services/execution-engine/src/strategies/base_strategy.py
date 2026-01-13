"""
B3 Trading Platform - Base Strategy
=====================================
Classe base abstrata para todas as estratégias de trading.

Define a interface comum que todas as estratégias devem implementar,
incluindo cálculo de indicadores, geração de sinais e gestão de risco.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple

import pandas as pd
import numpy as np
from loguru import logger


@dataclass
class Signal:
    """Representa um sinal de trading."""
    timestamp: datetime
    signal_type: str  # 'BUY', 'SELL', 'HOLD'
    price: float
    strength: float  # 0.0 to 1.0
    strategy_name: str
    indicators: Dict[str, float]
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    position_size: Optional[float] = None
    reason: str = ""
    
    def to_dict(self) -> Dict:
        """Converte para dicionário."""
        return {
            "timestamp": self.timestamp.isoformat() if isinstance(self.timestamp, datetime) else str(self.timestamp),
            "signal": self.signal_type,
            "price": self.price,
            "strength": self.strength,
            "strategy": self.strategy_name,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "position_size": self.position_size,
            "indicators": self.indicators,
            "reason": self.reason,
        }


class BaseStrategy(ABC):
    """
    Classe base abstrata para estratégias de trading.
    
    Todas as estratégias devem herdar desta classe e implementar
    os métodos abstratos: default_params, calculate_indicators e generate_signals.
    
    Attributes:
        name: Nome único da estratégia
        description: Descrição da estratégia
        version: Versão da implementação
        params: Parâmetros configuráveis
        
    Example:
        class MyStrategy(BaseStrategy):
            name = "my_strategy"
            description = "Minha estratégia customizada"
            
            def default_params(self) -> Dict:
                return {"period": 14}
            
            def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
                df["indicator"] = df["close"].rolling(self.params["period"]).mean()
                return df
            
            def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
                df["signal"] = "HOLD"
                df.loc[df["close"] > df["indicator"], "signal"] = "BUY"
                return df
    """
    
    name: str = "base"
    description: str = "Estratégia base abstrata"
    version: str = "1.0.0"
    
    def __init__(self, params: Optional[Dict] = None):
        """
        Inicializa a estratégia.
        
        Args:
            params: Parâmetros customizados (opcional).
                   Se None, usa default_params().
        """
        self.params = self.default_params()
        if params:
            self.params.update(params)
        
        self.signals: List[Signal] = []
        self.performance: Dict[str, Any] = {}
        
        logger.debug(f"Estratégia '{self.name}' inicializada com params: {self.params}")
    
    @abstractmethod
    def default_params(self) -> Dict:
        """
        Retorna os parâmetros padrão da estratégia.
        
        Returns:
            Dicionário com parâmetros e seus valores padrão.
        """
        pass
    
    @abstractmethod
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calcula os indicadores técnicos necessários.
        
        Args:
            df: DataFrame com colunas OHLCV (open, high, low, close, volume).
            
        Returns:
            DataFrame com indicadores adicionados.
        """
        pass
    
    @abstractmethod
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Gera sinais de compra/venda baseados nos indicadores.
        
        Args:
            df: DataFrame com dados OHLCV e indicadores calculados.
            
        Returns:
            DataFrame com coluna 'signal' adicionada.
            Valores: 'BUY', 'SELL', 'HOLD' (ou 1, -1, 0 para numérico)
        """
        pass
    
    def validate_data(self, df: pd.DataFrame) -> Tuple[bool, str]:
        """
        Valida se o DataFrame contém as colunas necessárias.
        
        Args:
            df: DataFrame para validar.
            
        Returns:
            Tupla (is_valid, message)
        """
        required_columns = ['open', 'high', 'low', 'close', 'volume']
        
        # Verificar colunas (case insensitive)
        df_cols_lower = [c.lower() for c in df.columns]
        
        for col in required_columns:
            if col not in df_cols_lower:
                return False, f"Coluna necessária '{col}' não encontrada"
        
        if df.empty:
            return False, "DataFrame está vazio"
        
        if len(df) < 50:
            return False, f"Dados insuficientes: {len(df)} linhas (mínimo: 50)"
        
        return True, "OK"
    
    def normalize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Normaliza nomes de colunas para lowercase.
        
        Args:
            df: DataFrame original.
            
        Returns:
            DataFrame com colunas normalizadas.
        """
        df = df.copy()
        df.columns = [c.lower() for c in df.columns]
        return df
    
    def run(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Executa a estratégia completa: validação → indicadores → sinais.
        
        Args:
            df: DataFrame com dados OHLCV.
            
        Returns:
            DataFrame com indicadores e sinais.
            
        Raises:
            ValueError: Se dados forem inválidos.
        """
        try:
            # Normalizar colunas
            df = self.normalize_columns(df)
            
            # Validar dados
            is_valid, message = self.validate_data(df)
            if not is_valid:
                raise ValueError(f"Dados inválidos: {message}")
            
            # Criar cópia para não modificar original
            df_strategy = df.copy()
            
            # Calcular indicadores
            logger.info(f"{self.name}: Calculando indicadores...")
            df_strategy = self.calculate_indicators(df_strategy)
            
            # Gerar sinais
            logger.info(f"{self.name}: Gerando sinais de trading...")
            df_strategy = self.generate_signals(df_strategy)
            
            # Limpar NaN (preencher para frente e para trás)
            df_strategy = df_strategy.bfill().ffill()
            
            logger.info(f"{self.name}: Estratégia executada com sucesso - {len(df_strategy)} candles")
            return df_strategy
            
        except Exception as e:
            logger.error(f"{self.name}: Erro ao executar estratégia - {e}")
            raise
    
    def get_current_signal(self, df: pd.DataFrame) -> Signal:
        """
        Retorna o sinal atual (último candle).
        
        Args:
            df: DataFrame com dados OHLCV.
            
        Returns:
            Objeto Signal com informações do sinal atual.
        """
        df = self.run(df)
        last = df.iloc[-1]
        
        # Extrair indicadores (excluindo colunas padrão)
        exclude_cols = ['time', 'timestamp', 'open', 'high', 'low', 'close', 'volume', 
                       'signal', 'signal_strength', 'stop_loss', 'take_profit', 'position_size']
        
        indicators = {}
        for k, v in last.items():
            if k not in exclude_cols:
                try:
                    if isinstance(v, (int, float, np.number)) and pd.notna(v) and np.isfinite(v):
                        indicators[k] = float(v)
                except (ValueError, TypeError):
                    pass
        
        # Determinar timestamp
        if 'time' in last:
            timestamp = last['time']
        elif 'timestamp' in last:
            timestamp = last['timestamp']
        else:
            timestamp = datetime.now()
        
        return Signal(
            timestamp=timestamp,
            signal_type=str(last.get('signal', 'HOLD')),
            price=float(last['close']),
            strength=float(last.get('signal_strength', 0.5)),
            strategy_name=self.name,
            stop_loss=float(last['stop_loss']) if pd.notna(last.get('stop_loss')) else None,
            take_profit=float(last['take_profit']) if pd.notna(last.get('take_profit')) else None,
            position_size=float(last['position_size']) if pd.notna(last.get('position_size')) else None,
            indicators=indicators,
            reason=str(last.get('signal_reason', ''))
        )
    
    def get_entry_conditions(self) -> List[str]:
        """
        Retorna as condições de entrada em formato legível.
        
        Returns:
            Lista de strings descrevendo condições de entrada.
        """
        return []
    
    def get_exit_conditions(self) -> List[str]:
        """
        Retorna as condições de saída em formato legível.
        
        Returns:
            Lista de strings descrevendo condições de saída.
        """
        return []
    
    def calculate_sharpe_ratio(self, df: pd.DataFrame, risk_free_rate: float = 0.0) -> float:
        """
        Calcula o Sharpe Ratio da estratégia.
        
        Args:
            df: DataFrame com coluna 'signal' e 'close'.
            risk_free_rate: Taxa livre de risco anual (default: 0).
            
        Returns:
            Sharpe Ratio anualizado.
        """
        if 'signal' not in df.columns:
            return 0.0
        
        df = df.copy()
        
        # Converter sinais string para numérico
        if df['signal'].dtype == object:
            signal_map = {'BUY': 1, 'SELL': -1, 'HOLD': 0}
            df['signal_num'] = df['signal'].map(signal_map).fillna(0)
        else:
            df['signal_num'] = df['signal']
        
        # Calcular retornos
        df['returns'] = df['close'].pct_change()
        df['strategy_returns'] = df['returns'] * df['signal_num'].shift(1)
        
        # Remover NaN
        strategy_returns = df['strategy_returns'].dropna()
        
        if len(strategy_returns) == 0 or strategy_returns.std() == 0:
            return 0.0
        
        # Calcular Sharpe (anualizado para 252 dias de trading)
        excess_returns = strategy_returns - risk_free_rate / 252
        sharpe = np.sqrt(252) * excess_returns.mean() / excess_returns.std()
        
        return float(sharpe) if np.isfinite(sharpe) else 0.0
    
    def calculate_max_drawdown(self, df: pd.DataFrame) -> float:
        """
        Calcula o Maximum Drawdown da estratégia.
        
        Args:
            df: DataFrame com coluna 'close' e 'signal'.
            
        Returns:
            Maximum Drawdown em percentual (0-1).
        """
        if 'signal' not in df.columns:
            return 0.0
        
        df = df.copy()
        
        # Converter sinais string para numérico
        if df['signal'].dtype == object:
            signal_map = {'BUY': 1, 'SELL': -1, 'HOLD': 0}
            df['signal_num'] = df['signal'].map(signal_map).fillna(0)
        else:
            df['signal_num'] = df['signal']
        
        # Calcular retornos acumulados
        df['returns'] = df['close'].pct_change()
        df['strategy_returns'] = df['returns'] * df['signal_num'].shift(1)
        df['cumulative'] = (1 + df['strategy_returns'].fillna(0)).cumprod()
        
        # Calcular drawdown
        df['peak'] = df['cumulative'].cummax()
        df['drawdown'] = (df['cumulative'] - df['peak']) / df['peak']
        
        max_dd = df['drawdown'].min()
        
        return abs(float(max_dd)) if np.isfinite(max_dd) else 0.0
    
    def get_info(self) -> Dict[str, Any]:
        """
        Retorna informações completas da estratégia.
        
        Returns:
            Dicionário com nome, descrição, parâmetros e condições.
        """
        return {
            'name': self.name,
            'description': self.description,
            'version': self.version,
            'parameters': self.params,
            'entry_conditions': self.get_entry_conditions(),
            'exit_conditions': self.get_exit_conditions(),
        }
    
    def __str__(self) -> str:
        return f"{self.name} v{self.version}"
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(name='{self.name}', params={self.params})>"


# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Calcula Average True Range (ATR).
    
    Args:
        df: DataFrame com colunas high, low, close.
        period: Período para média móvel.
        
    Returns:
        Série com valores ATR.
    """
    high_low = df['high'] - df['low']
    high_close = (df['high'] - df['close'].shift()).abs()
    low_close = (df['low'] - df['close'].shift()).abs()
    
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    atr = true_range.rolling(window=period).mean()
    
    return atr


def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """
    Calcula Relative Strength Index (RSI).
    
    Args:
        series: Série de preços (geralmente close).
        period: Período do RSI.
        
    Returns:
        Série com valores RSI (0-100).
    """
    delta = series.diff()
    gain = delta.where(delta > 0, 0).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    
    return rsi


def calculate_ema(series: pd.Series, period: int) -> pd.Series:
    """
    Calcula Exponential Moving Average (EMA).
    
    Args:
        series: Série de preços.
        period: Período da EMA.
        
    Returns:
        Série com valores EMA.
    """
    return series.ewm(span=period, adjust=False).mean()


def calculate_sma(series: pd.Series, period: int) -> pd.Series:
    """
    Calcula Simple Moving Average (SMA).
    
    Args:
        series: Série de preços.
        period: Período da SMA.
        
    Returns:
        Série com valores SMA.
    """
    return series.rolling(window=period).mean()


def calculate_bollinger_bands(series: pd.Series, period: int = 20, std_dev: float = 2.0) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """
    Calcula Bollinger Bands.
    
    Args:
        series: Série de preços.
        period: Período da média móvel.
        std_dev: Número de desvios padrão.
        
    Returns:
        Tupla (upper_band, middle_band, lower_band).
    """
    middle = series.rolling(window=period).mean()
    std = series.rolling(window=period).std()
    
    upper = middle + (std * std_dev)
    lower = middle - (std * std_dev)
    
    return upper, middle, lower


def calculate_macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """
    Calcula MACD (Moving Average Convergence Divergence).
    
    Args:
        series: Série de preços.
        fast: Período da EMA rápida.
        slow: Período da EMA lenta.
        signal: Período da linha de sinal.
        
    Returns:
        Tupla (macd_line, signal_line, histogram).
    """
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    
    return macd_line, signal_line, histogram


def calculate_adx(df: pd.DataFrame, period: int = 14) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """
    Calcula Average Directional Index (ADX).
    
    Args:
        df: DataFrame com colunas high, low, close.
        period: Período do ADX.
        
    Returns:
        Tupla (adx, di_plus, di_minus).
    """
    # True Range
    high_low = df['high'] - df['low']
    high_close = (df['high'] - df['close'].shift()).abs()
    low_close = (df['low'] - df['close'].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    
    # Directional Movement
    up_move = df['high'] - df['high'].shift()
    down_move = df['low'].shift() - df['low']
    
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)
    
    # Smoothed averages
    atr = tr.rolling(window=period).mean()
    plus_di = 100 * pd.Series(plus_dm).rolling(window=period).mean() / atr
    minus_di = 100 * pd.Series(minus_dm).rolling(window=period).mean() / atr
    
    # ADX
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    adx = dx.rolling(window=period).mean()
    
    return adx, plus_di, minus_di
