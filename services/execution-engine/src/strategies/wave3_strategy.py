"""
Wave3 Strategy - André Moraes Trend Following
B3 Trading Platform

Estratégia de seguimento de tendência multi-timeframe:
- Contexto: Gráfico Diário (MME 72 + MME 17)
- Gatilho: Gráfico 60min (Onda 3 de Elliott)
- Regra dos 17 Candles: Validação de topos/fundos
- Risk:Reward: 1:3 (6% risco → 18% alvo)
- Win Rate Esperado: 50-52%
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from loguru import logger


class Wave3Strategy:
    """
    Implementação da estratégia Wave3 de André Moraes.
    
    Sistema de trend following com contexto diário e execução em 60min,
    utilizando médias móveis, regra dos 17 candles e identificação da Onda 3.
    """
    
    def __init__(
        self,
        ema_long: int = 72,
        ema_short: int = 17,
        zone_tolerance: float = 0.01,  # 1% acima/abaixo da zona
        min_candles_validation: int = 17,  # Regra dos 17 candles
        risk_percent: float = 0.06,  # 6% de risco
        reward_ratio: float = 3.0,  # 3:1 reward
        trailing_stop: bool = True
    ):
        """
        Inicializa Wave3 Strategy.
        
        Args:
            ema_long: Períodos da MME longa (contexto de tendência)
            ema_short: Períodos da MME curta (zona de entrada)
            zone_tolerance: Tolerância da zona de entrada (%)
            min_candles_validation: Mínimo de candles entre topos/fundos
            risk_percent: % de risco por operação
            reward_ratio: Ratio de reward:risk
            trailing_stop: Se deve usar trailing stop
        """
        self.ema_long = ema_long
        self.ema_short = ema_short
        self.zone_tolerance = zone_tolerance
        self.min_candles_validation = min_candles_validation
        self.risk_percent = risk_percent
        self.reward_ratio = reward_ratio
        self.trailing_stop = trailing_stop
        
        # Estado da estratégia
        self.daily_context: Optional[Dict] = None
        self.last_pivot_low: Optional[Dict] = None
        self.last_pivot_high: Optional[Dict] = None
        
    def calculate_indicators(
        self,
        df_daily: pd.DataFrame,
        df_60min: Optional[pd.DataFrame] = None
    ) -> Tuple[pd.DataFrame, Optional[pd.DataFrame]]:
        """
        Calcula indicadores para ambos os timeframes.
        
        Args:
            df_daily: DataFrame com dados diários
            df_60min: DataFrame com dados de 60min (opcional)
            
        Returns:
            Tuple com DataFrames processados (daily, 60min)
        """
        # Indicadores no gráfico diário
        df_daily = df_daily.copy()
        df_daily['ema_long'] = df_daily['close'].ewm(span=self.ema_long, adjust=False).mean()
        df_daily['ema_short'] = df_daily['close'].ewm(span=self.ema_short, adjust=False).mean()
        
        # Zona de entrada (espaço entre MMEs)
        df_daily['zone_upper'] = df_daily[['ema_long', 'ema_short']].max(axis=1) * (1 + self.zone_tolerance)
        df_daily['zone_lower'] = df_daily[['ema_long', 'ema_short']].min(axis=1) * (1 - self.zone_tolerance)
        
        # Direção da tendência
        df_daily['trend_direction'] = np.where(df_daily['close'] > df_daily['ema_long'], 1, -1)
        
        # Topos e fundos ascendentes/descendentes
        df_daily = self._identify_swing_points(df_daily)
        
        # Distância das médias (para evitar preços esticados)
        df_daily['dist_ema_long'] = (df_daily['close'] - df_daily['ema_long']) / df_daily['ema_long']
        df_daily['dist_ema_short'] = (df_daily['close'] - df_daily['ema_short']) / df_daily['ema_short']
        
        # Se há dados de 60min, processar
        if df_60min is not None:
            df_60min = df_60min.copy()
            df_60min['ema_9'] = df_60min['close'].ewm(span=9, adjust=False).mean()
            df_60min['ema_21'] = df_60min['close'].ewm(span=21, adjust=False).mean()
            
            # Identificar pivôs de alta/baixa em 60min
            df_60min = self._identify_swing_points(df_60min, suffix='_60min')
            
        return df_daily, df_60min
    
    def _identify_swing_points(
        self,
        df: pd.DataFrame,
        suffix: str = ''
    ) -> pd.DataFrame:
        """
        Identifica topos e fundos (swing points) respeitando a regra dos 17 candles.
        
        Args:
            df: DataFrame com OHLC
            suffix: Sufixo para colunas (ex: '_60min')
            
        Returns:
            DataFrame com swing points identificados
        """
        df = df.copy()
        
        # Identificar máximas e mínimas locais (janela de 17 candles)
        window = self.min_candles_validation
        
        # Pivot Highs (topos)
        df[f'pivot_high{suffix}'] = df['high'].rolling(window=window*2+1, center=True).apply(
            lambda x: x[window] if x[window] == x.max() else np.nan, raw=True
        )
        
        # Pivot Lows (fundos)
        df[f'pivot_low{suffix}'] = df['low'].rolling(window=window*2+1, center=True).apply(
            lambda x: x[window] if x[window] == x.min() else np.nan, raw=True
        )
        
        # Validar distância mínima de 17 candles entre pivôs
        df[f'valid_pivot_high{suffix}'] = False
        df[f'valid_pivot_low{suffix}'] = False
        
        last_high_idx = -999
        last_low_idx = -999
        
        for i in range(len(df)):
            if not pd.isna(df.iloc[i][f'pivot_high{suffix}']):
                if i - last_high_idx >= self.min_candles_validation:
                    df.iloc[i, df.columns.get_loc(f'valid_pivot_high{suffix}')] = True
                    last_high_idx = i
            
            if not pd.isna(df.iloc[i][f'pivot_low{suffix}']):
                if i - last_low_idx >= self.min_candles_validation:
                    df.iloc[i, df.columns.get_loc(f'valid_pivot_low{suffix}')] = True
                    last_low_idx = i
        
        # Identificar topos/fundos ascendentes/descendentes
        df = self._identify_trend_structure(df, suffix)
        
        return df
    
    def _identify_trend_structure(
        self,
        df: pd.DataFrame,
        suffix: str = ''
    ) -> pd.DataFrame:
        """
        Identifica estrutura de tendência (higher highs, higher lows, etc).
        
        Args:
            df: DataFrame com pivot points
            suffix: Sufixo das colunas
            
        Returns:
            DataFrame com estrutura de tendência
        """
        df = df.copy()
        
        # Extrair apenas pivôs válidos
        pivot_highs = df[df[f'valid_pivot_high{suffix}'] == True][f'pivot_high{suffix}']
        pivot_lows = df[df[f'valid_pivot_low{suffix}'] == True][f'pivot_low{suffix}']
        
        # Higher Highs / Lower Highs
        df[f'higher_high{suffix}'] = False
        df[f'lower_high{suffix}'] = False
        
        if len(pivot_highs) >= 2:
            for i in range(1, len(pivot_highs)):
                idx = pivot_highs.index[i]
                prev_high = pivot_highs.iloc[i-1]
                curr_high = pivot_highs.iloc[i]
                
                if curr_high > prev_high:
                    df.loc[idx, f'higher_high{suffix}'] = True
                else:
                    df.loc[idx, f'lower_high{suffix}'] = True
        
        # Higher Lows / Lower Lows
        df[f'higher_low{suffix}'] = False
        df[f'lower_low{suffix}'] = False
        
        if len(pivot_lows) >= 2:
            for i in range(1, len(pivot_lows)):
                idx = pivot_lows.index[i]
                prev_low = pivot_lows.iloc[i-1]
                curr_low = pivot_lows.iloc[i]
                
                if curr_low > prev_low:
                    df.loc[idx, f'higher_low{suffix}'] = True
                else:
                    df.loc[idx, f'lower_low{suffix}'] = True
        
        # Tendência geral baseada em estrutura
        df[f'uptrend_structure{suffix}'] = df[f'higher_high{suffix}'] & df[f'higher_low{suffix}']
        df[f'downtrend_structure{suffix}'] = df[f'lower_high{suffix}'] & df[f'lower_low{suffix}']
        
        return df
    
    def check_daily_context(self, df_daily: pd.DataFrame) -> Dict:
        """
        Verifica contexto do gráfico diário.
        
        Args:
            df_daily: DataFrame diário com indicadores
            
        Returns:
            Dict com análise do contexto diário
        """
        last_row = df_daily.iloc[-1]
        
        # Direção da tendência principal
        trend_direction = 'bullish' if last_row['trend_direction'] == 1 else 'bearish'
        
        # Verificar se preço está na zona de entrada
        in_zone = (
            last_row['close'] >= last_row['zone_lower'] and
            last_row['close'] <= last_row['zone_upper']
        )
        
        # Verificar estrutura de topos e fundos
        uptrend_structure = df_daily['uptrend_structure'].iloc[-5:].any()  # Últimos 5 dias
        downtrend_structure = df_daily['downtrend_structure'].iloc[-5:].any()
        
        # Verificar se preço está esticado
        price_stretched = abs(last_row['dist_ema_long']) > 0.05  # Mais de 5% de distância
        
        context = {
            'trend_direction': trend_direction,
            'in_entry_zone': in_zone,
            'uptrend_structure': uptrend_structure,
            'downtrend_structure': downtrend_structure,
            'price_stretched': price_stretched,
            'ema_long': last_row['ema_long'],
            'ema_short': last_row['ema_short'],
            'close': last_row['close'],
            'zone_upper': last_row['zone_upper'],
            'zone_lower': last_row['zone_lower'],
            'ready_for_entry': (
                in_zone and 
                not price_stretched and
                (
                    (trend_direction == 'bullish' and uptrend_structure) or
                    (trend_direction == 'bearish' and downtrend_structure)
                )
            )
        }
        
        self.daily_context = context
        return context
    
    def identify_wave3_setup(
        self,
        df_60min: pd.DataFrame,
        daily_context: Dict
    ) -> Optional[Dict]:
        """
        Identifica setup de Onda 3 no gráfico de 60 minutos.
        
        Onda 3 = Pivô de alta confirmado após correção:
        1. Fundo mais alto que o anterior
        2. Rompimento do topo intermediário
        3. Distância mínima de 17 candles respeitada
        
        Args:
            df_60min: DataFrame 60min com indicadores
            daily_context: Contexto do gráfico diário
            
        Returns:
            Dict com setup identificado ou None
        """
        if not daily_context['ready_for_entry']:
            return None
        
        # Verificar apenas últimos 50 candles para performance
        df_recent = df_60min.iloc[-50:].copy()
        
        # Buscar pivôs de baixa válidos recentes
        pivot_lows = df_recent[df_recent['valid_pivot_low_60min'] == True]
        
        if len(pivot_lows) < 2:
            return None
        
        # Pegar os 2 últimos fundos
        last_low = pivot_lows.iloc[-1]
        prev_low = pivot_lows.iloc[-2]
        
        # Verificar se é Higher Low (fundo mais alto)
        if last_low['pivot_low_60min'] <= prev_low['pivot_low_60min']:
            return None
        
        # Buscar topo intermediário entre os dois fundos
        between_lows = df_recent[
            (df_recent.index > prev_low.name) &
            (df_recent.index < last_low.name)
        ]
        
        if len(between_lows) == 0:
            return None
        
        intermediate_high = between_lows['high'].max()
        
        # Verificar se rompeu o topo intermediário (Onda 3)
        last_row = df_recent.iloc[-1]
        breakout = last_row['close'] > intermediate_high
        
        if not breakout:
            return None
        
        # Calcular stop loss (abaixo do último fundo)
        stop_loss = last_low['pivot_low_60min'] * 0.995  # 0.5% abaixo do fundo
        
        # Calcular distância de risco
        risk_distance = (last_row['close'] - stop_loss) / last_row['close']
        
        # Calcular take profit (3x o risco)
        take_profit = last_row['close'] * (1 + risk_distance * self.reward_ratio)
        
        setup = {
            'signal': 'BUY' if daily_context['trend_direction'] == 'bullish' else 'SELL',
            'entry_price': last_row['close'],
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'risk_pct': risk_distance,
            'reward_pct': risk_distance * self.reward_ratio,
            'reward_risk_ratio': self.reward_ratio,
            'last_low': last_low['pivot_low_60min'],
            'prev_low': prev_low['pivot_low_60min'],
            'intermediate_high': intermediate_high,
            'timestamp': last_row.name,
            'setup_type': 'wave3_breakout'
        }
        
        return setup
    
    def generate_signals(
        self,
        df_daily: pd.DataFrame,
        df_60min: pd.DataFrame
    ) -> List[Dict]:
        """
        Gera sinais de trading baseados na estratégia Wave3.
        
        Args:
            df_daily: DataFrame com dados diários
            df_60min: DataFrame com dados de 60min
            
        Returns:
            Lista de sinais gerados
        """
        # Calcular indicadores
        df_daily, df_60min = self.calculate_indicators(df_daily, df_60min)
        
        # Verificar contexto diário
        daily_context = self.check_daily_context(df_daily)
        
        logger.info(f"📊 Contexto Diário: {daily_context['trend_direction']} | "
                   f"Zona: {daily_context['in_entry_zone']} | "
                   f"Pronto: {daily_context['ready_for_entry']}")
        
        # Se contexto não está pronto, não gerar sinais
        if not daily_context['ready_for_entry']:
            return []
        
        # Identificar setup de Onda 3 no 60min
        wave3_setup = self.identify_wave3_setup(df_60min, daily_context)
        
        if wave3_setup is None:
            return []
        
        logger.success(f"✅ Wave3 Setup identificado: {wave3_setup['signal']} @ {wave3_setup['entry_price']:.2f}")
        
        return [wave3_setup]
    
    def backtest(
        self,
        df_daily: pd.DataFrame,
        df_60min: pd.DataFrame,
        initial_capital: float = 100000.0
    ) -> Dict:
        """
        Executa backtest da estratégia Wave3.
        
        Args:
            df_daily: DataFrame com dados diários
            df_60min: DataFrame com dados de 60min
            initial_capital: Capital inicial
            
        Returns:
            Dict com resultados do backtest
        """
        # Calcular indicadores
        df_daily, df_60min = self.calculate_indicators(df_daily, df_60min)
        
        # Simular trades
        trades = []
        capital = initial_capital
        positions = []
        
        # Iterar por cada dia para verificar contexto
        for i in range(self.ema_long, len(df_daily)):
            daily_slice = df_daily.iloc[:i+1]
            daily_context = self.check_daily_context(daily_slice)
            
            if not daily_context['ready_for_entry']:
                continue
            
            # Buscar sinais no 60min correspondente ao período diário
            current_date = daily_slice.index[-1]
            
            # Filtrar 60min do dia atual e dias anteriores
            df_60min_filtered = df_60min[df_60min.index <= current_date]
            
            if len(df_60min_filtered) < 50:
                continue
            
            # Identificar Wave3 setup
            wave3_setup = self.identify_wave3_setup(df_60min_filtered.iloc[-50:], daily_context)
            
            if wave3_setup is not None:
                # Simular trade
                position_size = capital * self.risk_percent / wave3_setup['risk_pct']
                
                trade = {
                    'entry_date': wave3_setup['timestamp'],
                    'entry_price': wave3_setup['entry_price'],
                    'stop_loss': wave3_setup['stop_loss'],
                    'take_profit': wave3_setup['take_profit'],
                    'position_size': position_size,
                    'signal': wave3_setup['signal']
                }
                
                # Simular resultado (simplificado)
                # Em produção, iterar pelos candles seguintes até SL ou TP
                trades.append(trade)
        
        # Calcular métricas
        total_trades = len(trades)
        
        metrics = {
            'total_trades': total_trades,
            'initial_capital': initial_capital,
            'final_capital': capital,
            'total_return': (capital - initial_capital) / initial_capital,
            'trades': trades
        }
        
        return metrics
