"""
B3 Trading Platform - RSI Divergence Strategy
===============================================
Estratégia de Divergência RSI - Detecção de 4 Padrões de Divergência

Esta estratégia detecta padrões de divergência entre preço e RSI:

1. **Divergência de Alta (Bullish)**: 
   - Preço faz mínimas mais baixas (lower lows)
   - RSI faz mínimas mais altas (higher lows)
   - Sinal: COMPRA - possível reversão de alta

2. **Divergência de Baixa (Bearish)**:
   - Preço faz máximas mais altas (higher highs)
   - RSI faz máximas mais baixas (lower highs)
   - Sinal: VENDA - possível reversão de baixa

3. **Divergência Oculta de Alta (Hidden Bullish)**:
   - Preço faz mínimas mais altas
   - RSI faz mínimas mais baixas
   - Sinal: COMPRA - continuação de tendência de alta

4. **Divergência Oculta de Baixa (Hidden Bearish)**:
   - Preço faz máximas mais baixas
   - RSI faz máximas mais altas
   - Sinal: VENDA - continuação de tendência de baixa

DISCLAIMER: Esta estratégia é para fins educacionais.
Resultados passados não garantem resultados futuros.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Any

import pandas as pd
import numpy as np
from loguru import logger

from .base_strategy import (
    BaseStrategy, 
    calculate_atr, 
    calculate_rsi, 
    calculate_ema,
    calculate_sma,
    calculate_macd,
    calculate_adx
)


@dataclass
class DivergencePattern:
    """Representa um padrão de divergência detectado."""
    pattern_type: str  # 'bullish', 'bearish', 'hidden_bullish', 'hidden_bearish'
    signal: str  # 'BUY' ou 'SELL'
    strength: float  # 0.0 a 1.0
    price_point1: float
    price_point2: float
    rsi_point1: float
    rsi_point2: float
    index: int
    description: str


class RSIDivergenceStrategy(BaseStrategy):
    """
    Estratégia de Detecção de Divergências RSI.
    
    Detecta divergências regulares e ocultas entre preço e RSI,
    gerando sinais de reversão ou continuação de tendência.
    
    Filtros aplicados:
    - ADX > threshold (tendência forte)
    - Volume > média (confirmação)
    - RSI não em zona neutra
    - Sem sinais consecutivos próximos
    
    Gestão de Risco:
    - Stop Loss: 2x ATR
    - Take Profit: 4x ATR
    """
    
    name = "rsi_divergence"
    description = "Divergência RSI com 4 padrões (bullish, bearish, hidden)"
    version = "2.0.0"
    
    def default_params(self) -> Dict:
        return {
            # Parâmetros RSI
            'rsi_period': 14,
            'rsi_overbought': 70,
            'rsi_oversold': 30,
            
            # Parâmetros de detecção de picos/vales
            'lookback_periods': 20,
            'min_peak_distance': 5,
            'divergence_threshold': 0.02,  # 2% de diferença mínima
            
            # Filtros de tendência
            'ma_trend_period': 50,
            'min_adx': 20,
            
            # Confirmação de volume
            'volume_confirmation': True,
            'volume_multiplier': 1.2,
            
            # Gestão de risco
            'atr_period': 14,
            'sl_atr_mult': 2.0,
            'tp_atr_mult': 4.0,
            
            # Qualidade mínima do sinal
            'min_signal_strength': 0.5
        }
    
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calcula RSI, ATR, ADX, MACD e médias móveis.
        """
        df = df.copy()
        
        # RSI
        df['rsi'] = calculate_rsi(df['close'], self.params['rsi_period'])
        
        # ATR para gestão de risco
        df['atr'] = calculate_atr(df, self.params['atr_period'])
        
        # ADX para filtro de tendência
        df['adx'], df['di_plus'], df['di_minus'] = calculate_adx(df, self.params['min_adx'])
        
        # Médias móveis para contexto
        df['sma_trend'] = calculate_sma(df['close'], self.params['ma_trend_period'])
        df['ema_fast'] = calculate_ema(df['close'], 12)
        df['ema_slow'] = calculate_ema(df['close'], 26)
        
        # MACD para confirmação
        df['macd'], df['macd_signal'], df['macd_hist'] = calculate_macd(df['close'])
        
        # Médias de volume
        df['volume_sma'] = df['volume'].rolling(window=20).mean()
        df['volume_ratio'] = df['volume'] / df['volume_sma']
        
        # Detectar picos e vales
        df = self._detect_peaks_and_valleys(df)
        
        return df
    
    def _detect_peaks_and_valleys(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Detecta picos e vales no preço e no RSI.
        """
        lookback = self.params['lookback_periods']
        
        df['price_peak'] = False
        df['price_valley'] = False
        df['rsi_peak'] = False
        df['rsi_valley'] = False
        
        for i in range(lookback, len(df) - lookback):
            # Picos de preço (máximas locais)
            window_high = df['high'].iloc[i-lookback:i+lookback+1]
            if df['high'].iloc[i] == window_high.max():
                df.iloc[i, df.columns.get_loc('price_peak')] = True
            
            # Vales de preço (mínimas locais)
            window_low = df['low'].iloc[i-lookback:i+lookback+1]
            if df['low'].iloc[i] == window_low.min():
                df.iloc[i, df.columns.get_loc('price_valley')] = True
            
            # Picos de RSI
            if pd.notna(df['rsi'].iloc[i]):
                window_rsi = df['rsi'].iloc[i-lookback:i+lookback+1]
                if df['rsi'].iloc[i] == window_rsi.max() and df['rsi'].iloc[i] > 50:
                    df.iloc[i, df.columns.get_loc('rsi_peak')] = True
                
                # Vales de RSI
                if df['rsi'].iloc[i] == window_rsi.min() and df['rsi'].iloc[i] < 50:
                    df.iloc[i, df.columns.get_loc('rsi_valley')] = True
        
        return df
    
    def _find_divergence(self, df: pd.DataFrame, idx: int) -> Optional[DivergencePattern]:
        """
        Procura por divergências no ponto atual.
        
        Args:
            df: DataFrame com indicadores.
            idx: Índice atual.
            
        Returns:
            DivergencePattern se encontrado, None caso contrário.
        """
        if idx < self.params['lookback_periods'] * 2:
            return None
        
        lookback = self.params['lookback_periods']
        threshold = self.params['divergence_threshold']
        
        # Buscar últimos picos/vales
        price_data = df.iloc[idx-lookback*2:idx+1]
        
        current_price = df['close'].iloc[idx]
        
        # ====================
        # 1. DIVERGÊNCIA DE ALTA (Bullish Divergence)
        # ====================
        price_valleys = price_data[price_data['price_valley']].tail(2)
        rsi_valleys = price_data[price_data['rsi_valley']].tail(2)
        
        if len(price_valleys) >= 2 and len(rsi_valleys) >= 2:
            # Preço faz lower lows
            price_ll = price_valleys['low'].iloc[-1] < price_valleys['low'].iloc[-2] * (1 - threshold)
            # RSI faz higher lows
            rsi_hl = rsi_valleys['rsi'].iloc[-1] > rsi_valleys['rsi'].iloc[-2] * (1 + threshold/10)
            
            if price_ll and rsi_hl:
                strength = self._calculate_divergence_strength(
                    price_valleys['low'].iloc[-2], price_valleys['low'].iloc[-1],
                    rsi_valleys['rsi'].iloc[-2], rsi_valleys['rsi'].iloc[-1],
                    'bullish', df, idx
                )
                
                if strength >= self.params['min_signal_strength']:
                    return DivergencePattern(
                        pattern_type='bullish_divergence',
                        signal='BUY',
                        strength=strength,
                        price_point1=float(price_valleys['low'].iloc[-2]),
                        price_point2=float(price_valleys['low'].iloc[-1]),
                        rsi_point1=float(rsi_valleys['rsi'].iloc[-2]),
                        rsi_point2=float(rsi_valleys['rsi'].iloc[-1]),
                        index=idx,
                        description='Divergência de Alta: Preço ↓ RSI ↑'
                    )
        
        # ====================
        # 2. DIVERGÊNCIA DE BAIXA (Bearish Divergence)
        # ====================
        price_peaks = price_data[price_data['price_peak']].tail(2)
        rsi_peaks = price_data[price_data['rsi_peak']].tail(2)
        
        if len(price_peaks) >= 2 and len(rsi_peaks) >= 2:
            # Preço faz higher highs
            price_hh = price_peaks['high'].iloc[-1] > price_peaks['high'].iloc[-2] * (1 + threshold)
            # RSI faz lower highs
            rsi_lh = rsi_peaks['rsi'].iloc[-1] < rsi_peaks['rsi'].iloc[-2] * (1 - threshold/10)
            
            if price_hh and rsi_lh:
                strength = self._calculate_divergence_strength(
                    price_peaks['high'].iloc[-2], price_peaks['high'].iloc[-1],
                    rsi_peaks['rsi'].iloc[-2], rsi_peaks['rsi'].iloc[-1],
                    'bearish', df, idx
                )
                
                if strength >= self.params['min_signal_strength']:
                    return DivergencePattern(
                        pattern_type='bearish_divergence',
                        signal='SELL',
                        strength=strength,
                        price_point1=float(price_peaks['high'].iloc[-2]),
                        price_point2=float(price_peaks['high'].iloc[-1]),
                        rsi_point1=float(rsi_peaks['rsi'].iloc[-2]),
                        rsi_point2=float(rsi_peaks['rsi'].iloc[-1]),
                        index=idx,
                        description='Divergência de Baixa: Preço ↑ RSI ↓'
                    )
        
        # ====================
        # 3. DIVERGÊNCIA OCULTA DE ALTA (Hidden Bullish)
        # ====================
        if len(price_valleys) >= 2 and len(rsi_valleys) >= 2:
            # Preço faz higher lows
            price_hl = price_valleys['low'].iloc[-1] > price_valleys['low'].iloc[-2] * (1 + threshold)
            # RSI faz lower lows
            rsi_ll = rsi_valleys['rsi'].iloc[-1] < rsi_valleys['rsi'].iloc[-2] * (1 - threshold/10)
            
            # Confirmar tendência de alta
            trend_bullish = current_price > df['sma_trend'].iloc[idx] if pd.notna(df['sma_trend'].iloc[idx]) else False
            
            if price_hl and rsi_ll and trend_bullish:
                strength = self._calculate_divergence_strength(
                    price_valleys['low'].iloc[-2], price_valleys['low'].iloc[-1],
                    rsi_valleys['rsi'].iloc[-2], rsi_valleys['rsi'].iloc[-1],
                    'hidden_bullish', df, idx
                ) * 0.9  # Hidden divergences têm menos peso
                
                if strength >= self.params['min_signal_strength']:
                    return DivergencePattern(
                        pattern_type='hidden_bullish',
                        signal='BUY',
                        strength=strength,
                        price_point1=float(price_valleys['low'].iloc[-2]),
                        price_point2=float(price_valleys['low'].iloc[-1]),
                        rsi_point1=float(rsi_valleys['rsi'].iloc[-2]),
                        rsi_point2=float(rsi_valleys['rsi'].iloc[-1]),
                        index=idx,
                        description='Divergência Oculta de Alta: Continuação bullish'
                    )
        
        # ====================
        # 4. DIVERGÊNCIA OCULTA DE BAIXA (Hidden Bearish)
        # ====================
        if len(price_peaks) >= 2 and len(rsi_peaks) >= 2:
            # Preço faz lower highs
            price_lh = price_peaks['high'].iloc[-1] < price_peaks['high'].iloc[-2] * (1 - threshold)
            # RSI faz higher highs
            rsi_hh = rsi_peaks['rsi'].iloc[-1] > rsi_peaks['rsi'].iloc[-2] * (1 + threshold/10)
            
            # Confirmar tendência de baixa
            trend_bearish = current_price < df['sma_trend'].iloc[idx] if pd.notna(df['sma_trend'].iloc[idx]) else False
            
            if price_lh and rsi_hh and trend_bearish:
                strength = self._calculate_divergence_strength(
                    price_peaks['high'].iloc[-2], price_peaks['high'].iloc[-1],
                    rsi_peaks['rsi'].iloc[-2], rsi_peaks['rsi'].iloc[-1],
                    'hidden_bearish', df, idx
                ) * 0.9
                
                if strength >= self.params['min_signal_strength']:
                    return DivergencePattern(
                        pattern_type='hidden_bearish',
                        signal='SELL',
                        strength=strength,
                        price_point1=float(price_peaks['high'].iloc[-2]),
                        price_point2=float(price_peaks['high'].iloc[-1]),
                        rsi_point1=float(rsi_peaks['rsi'].iloc[-2]),
                        rsi_point2=float(rsi_peaks['rsi'].iloc[-1]),
                        index=idx,
                        description='Divergência Oculta de Baixa: Continuação bearish'
                    )
        
        return None
    
    def _calculate_divergence_strength(
        self,
        price1: float, price2: float,
        rsi1: float, rsi2: float,
        div_type: str,
        df: pd.DataFrame,
        idx: int
    ) -> float:
        """
        Calcula a força da divergência baseada em múltiplos fatores.
        
        Componentes do score:
        - Magnitude da divergência de preço (25%)
        - Magnitude da divergência de RSI (25%)
        - Confirmação de volume (20%)
        - RSI em zona extrema (15%)
        - Confirmação MACD (15%)
        
        Returns:
            Score entre 0.0 e 1.0.
        """
        scores = []
        
        # 1. Magnitude da divergência de preço (25%)
        price_change = abs(price2 - price1) / price1 if price1 > 0 else 0
        price_score = min(price_change * 10, 1.0)
        scores.append(('price_magnitude', price_score, 0.25))
        
        # 2. Magnitude da divergência de RSI (25%)
        rsi_change = abs(rsi2 - rsi1) / 100
        rsi_score = min(rsi_change * 5, 1.0)
        scores.append(('rsi_magnitude', rsi_score, 0.25))
        
        # 3. Confirmação de volume (20%)
        vol_ratio = df['volume_ratio'].iloc[idx] if pd.notna(df['volume_ratio'].iloc[idx]) else 1.0
        if self.params['volume_confirmation']:
            volume_score = min(vol_ratio / self.params['volume_multiplier'], 1.0)
        else:
            volume_score = 0.5
        scores.append(('volume', volume_score, 0.20))
        
        # 4. RSI em zona extrema (15%)
        current_rsi = df['rsi'].iloc[idx] if pd.notna(df['rsi'].iloc[idx]) else 50
        if div_type in ['bullish', 'hidden_bullish']:
            rsi_zone_score = max(0, (self.params['rsi_oversold'] - current_rsi + 20) / 40)
        else:
            rsi_zone_score = max(0, (current_rsi - self.params['rsi_overbought'] + 20) / 40)
        rsi_zone_score = min(rsi_zone_score, 1.0)
        scores.append(('rsi_zone', rsi_zone_score, 0.15))
        
        # 5. Confirmação MACD (15%)
        macd_hist = df['macd_hist'].iloc[idx] if pd.notna(df['macd_hist'].iloc[idx]) else 0
        macd_hist_prev = df['macd_hist'].iloc[idx-1] if idx > 0 and pd.notna(df['macd_hist'].iloc[idx-1]) else macd_hist
        
        if div_type in ['bullish', 'hidden_bullish']:
            macd_score = 1.0 if macd_hist > macd_hist_prev else 0.3
        else:
            macd_score = 1.0 if macd_hist < macd_hist_prev else 0.3
        scores.append(('macd', macd_score, 0.15))
        
        # Calcular score ponderado final
        final_score = sum(score * weight for name, score, weight in scores)
        
        return min(max(final_score, 0.0), 1.0)
    
    def _apply_filters(self, df: pd.DataFrame, idx: int, divergence: DivergencePattern) -> bool:
        """
        Aplica filtros adicionais para validar o sinal.
        
        Returns:
            True se o sinal passou em todos os filtros.
        """
        # 1. Filtro de tendência ADX
        adx_value = df['adx'].iloc[idx] if pd.notna(df['adx'].iloc[idx]) else 0
        if adx_value < self.params['min_adx']:
            logger.debug(f"Sinal filtrado: ADX muito baixo ({adx_value:.2f})")
            return False
        
        # 2. Filtro de volume (se habilitado)
        if self.params['volume_confirmation']:
            vol_ratio = df['volume_ratio'].iloc[idx] if pd.notna(df['volume_ratio'].iloc[idx]) else 0
            if vol_ratio < self.params['volume_multiplier']:
                # Permitir sinais com volume normal para divergências fortes
                if divergence.strength < 0.7:
                    logger.debug("Sinal filtrado: Volume insuficiente")
                    return False
        
        # 3. Evitar sinais consecutivos muito próximos
        if idx >= 5:
            recent_signals = df['signal'].iloc[idx-5:idx]
            if (recent_signals != 'HOLD').any():
                logger.debug("Sinal filtrado: Sinal recente muito próximo")
                return False
        
        # 4. Verificar RSI não está em zona neutra demais
        rsi = df['rsi'].iloc[idx] if pd.notna(df['rsi'].iloc[idx]) else 50
        if 45 < rsi < 55 and divergence.strength < 0.8:
            logger.debug(f"Sinal filtrado: RSI em zona neutra ({rsi:.2f})")
            return False
        
        return True
    
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Gera sinais de compra/venda baseados em divergências RSI.
        """
        df = df.copy()
        
        df['signal'] = 'HOLD'
        df['signal_type'] = ''
        df['signal_strength'] = 0.5
        df['signal_reason'] = ''
        df['stop_loss'] = np.nan
        df['take_profit'] = np.nan
        
        # Processar cada candle procurando divergências
        for i in range(self.params['lookback_periods'] * 2, len(df)):
            divergence = self._find_divergence(df, i)
            
            if divergence is not None:
                # Aplicar filtros adicionais
                if not self._apply_filters(df, i, divergence):
                    continue
                
                # Registrar sinal
                df.iloc[i, df.columns.get_loc('signal')] = divergence.signal
                df.iloc[i, df.columns.get_loc('signal_type')] = divergence.pattern_type
                df.iloc[i, df.columns.get_loc('signal_strength')] = divergence.strength
                df.iloc[i, df.columns.get_loc('signal_reason')] = divergence.description
                
                # Calcular Stop Loss e Take Profit
                atr = df['atr'].iloc[i] if pd.notna(df['atr'].iloc[i]) else 0
                entry_price = df['close'].iloc[i]
                
                if divergence.signal == 'BUY':
                    df.iloc[i, df.columns.get_loc('stop_loss')] = entry_price - (atr * self.params['sl_atr_mult'])
                    df.iloc[i, df.columns.get_loc('take_profit')] = entry_price + (atr * self.params['tp_atr_mult'])
                else:  # SELL
                    df.iloc[i, df.columns.get_loc('stop_loss')] = entry_price + (atr * self.params['sl_atr_mult'])
                    df.iloc[i, df.columns.get_loc('take_profit')] = entry_price - (atr * self.params['tp_atr_mult'])
        
        return df
    
    def get_entry_conditions(self) -> List[str]:
        return [
            "Divergência de Alta: Preço faz mínimas mais baixas, RSI faz mínimas mais altas",
            "Divergência de Baixa: Preço faz máximas mais altas, RSI faz máximas mais baixas",
            "Divergência Oculta de Alta: Preço faz mínimas mais altas, RSI faz mínimas mais baixas (tendência de alta)",
            "Divergência Oculta de Baixa: Preço faz máximas mais baixas, RSI faz máximas mais altas (tendência de baixa)",
            f"ADX > {self.params['min_adx']} (tendência forte)",
            f"Volume > {self.params['volume_multiplier']}x média (confirmação)"
        ]
    
    def get_exit_conditions(self) -> List[str]:
        return [
            f"Stop Loss: {self.params['sl_atr_mult']}x ATR",
            f"Take Profit: {self.params['tp_atr_mult']}x ATR",
            "Divergência oposta detectada",
            "RSI atinge zona extrema oposta"
        ]
    
    def get_pattern_statistics(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Retorna estatísticas dos padrões detectados.
        """
        signals_df = df[df['signal'] != 'HOLD']
        
        if len(signals_df) == 0:
            return {'total_patterns': 0}
        
        stats = {
            'total_patterns': len(signals_df),
            'buy_signals': len(signals_df[signals_df['signal'] == 'BUY']),
            'sell_signals': len(signals_df[signals_df['signal'] == 'SELL']),
            'avg_strength': float(signals_df['signal_strength'].mean()),
            'pattern_distribution': {}
        }
        
        for pattern_type in signals_df['signal_type'].unique():
            if pattern_type:
                count = len(signals_df[signals_df['signal_type'] == pattern_type])
                stats['pattern_distribution'][pattern_type] = {
                    'count': count,
                    'percentage': (count / len(signals_df)) * 100,
                    'avg_strength': float(signals_df[signals_df['signal_type'] == pattern_type]['signal_strength'].mean())
                }
        
        return stats


def create_rsi_divergence_strategy(params: Dict[str, Any] = None) -> RSIDivergenceStrategy:
    """Factory function para criar instância da estratégia."""
    return RSIDivergenceStrategy(params)
