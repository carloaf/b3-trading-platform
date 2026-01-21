#!/usr/bin/env python3
"""
Estratégia Wave3 Multi-Timeframe
================================

Estratégia de seguimento de tendência baseada na metodologia André Moraes:
- Análise de contexto no gráfico DIÁRIO (MMA 72 e 17)
- Gatilho de entrada no gráfico de 60 MINUTOS (Onda 3)
- Regra dos 17 candles para validação de topos/fundos
- Trailing stop com alvo 3:1

Autor: B3 Trading Platform
Data: Janeiro 2026
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class Wave3Signal:
    """Representa um sinal da estratégia Wave3"""
    timestamp: datetime
    symbol: str
    signal_type: str  # 'BUY' ou 'SELL'
    entry_price: float
    stop_loss: float
    target_price: float
    risk: float
    reward: float
    context_daily: Dict
    wave3_confirmed: bool
    candles_since_pivot: int


class Wave3MultiTimeframe:
    """
    Estratégia Wave3 - Multi-Timeframe
    
    ETAPA 1: Contexto Diário
    - MMA 72: Tendência de longo prazo
    - MMA 17: Tendência de curto prazo
    - Preço acima MMA72 → busca compras
    - Preço abaixo MMA72 → busca vendas
    - Aguarda retorno à região das médias (±1%)
    
    ETAPA 2: Gatilho 60min
    - Identifica Onda 3 (Elliot Wave)
    - Fundo mais alto + rompimento do topo intermediário
    - Confirmação de reversão da correção
    
    ETAPA 3: Regra dos 17 Candles
    - Distância mínima de 17 candles entre extremos
    - Evita sinais falsos em oscilações curtas
    
    ETAPA 4: Gestão de Risco
    - Stop: abaixo do fundo da Onda 3
    - Alvo: 3x o risco (3:1)
    - Trailing stop: move para cada novo fundo confirmado
    - Win rate esperado: 50-52%
    """
    
    def __init__(self,
                 mma_long: int = 72,
                 mma_short: int = 17,
                 min_candles_pivot: int = 17,
                 risk_reward_ratio: float = 3.0,
                 mean_zone_tolerance: float = 0.01):
        """
        Inicializa a estratégia Wave3
        
        Args:
            mma_long: Período da média móvel longa (contexto)
            mma_short: Período da média móvel curta (contexto)
            min_candles_pivot: Mínimo de candles entre pivôs (regra dos 17)
            risk_reward_ratio: Relação risco/retorno alvo
            mean_zone_tolerance: Tolerância para zona das médias (±%)
        """
        self.mma_long = mma_long
        self.mma_short = mma_short
        self.min_candles_pivot = min_candles_pivot
        self.risk_reward_ratio = risk_reward_ratio
        self.mean_zone_tolerance = mean_zone_tolerance
        
        # Estado interno
        self.pivots_high = []  # Lista de pivôs de alta
        self.pivots_low = []   # Lista de pivôs de baixa
        self.last_signal = None
        
    def calculate_daily_context(self, df_daily: pd.DataFrame) -> pd.DataFrame:
        """
        ETAPA 1: Calcula contexto do gráfico diário
        
        Args:
            df_daily: DataFrame com dados diários (OHLCV)
            
        Returns:
            DataFrame com indicadores calculados
        """
        df = df_daily.copy()
        
        # Médias Móveis
        df['mma_72'] = df['close'].rolling(window=self.mma_long).mean()
        df['mma_17'] = df['close'].rolling(window=self.mma_short).mean()
        
        # Identifica tendência
        df['trend'] = np.where(df['close'] > df['mma_72'], 'BULLISH', 'BEARISH')
        
        # Distância do preço em relação às médias
        df['distance_to_mma72'] = (df['close'] - df['mma_72']) / df['mma_72']
        df['distance_to_mma17'] = (df['close'] - df['mma_17']) / df['mma_17']
        
        # Define zona das médias (entre MMA17 e MMA72)
        df['mean_zone_upper'] = df[['mma_17', 'mma_72']].max(axis=1) * (1 + self.mean_zone_tolerance)
        df['mean_zone_lower'] = df[['mma_17', 'mma_72']].min(axis=1) * (1 - self.mean_zone_tolerance)
        
        # Verifica se preço está na zona das médias
        df['in_mean_zone'] = (
            (df['close'] >= df['mean_zone_lower']) &
            (df['close'] <= df['mean_zone_upper'])
        )
        
        # Identifica topos e fundos ascendentes/descendentes
        df['higher_high'] = (df['high'] > df['high'].shift(1)) & (df['high'].shift(1) > df['high'].shift(2))
        df['higher_low'] = (df['low'] > df['low'].shift(1)) & (df['low'].shift(1) > df['low'].shift(2))
        df['lower_high'] = (df['high'] < df['high'].shift(1)) & (df['high'].shift(1) < df['high'].shift(2))
        df['lower_low'] = (df['low'] < df['low'].shift(1)) & (df['low'].shift(1) < df['low'].shift(2))
        
        # Contexto favorável para compra/venda
        df['buy_context'] = (
            (df['trend'] == 'BULLISH') &
            (df['higher_high'] | df['higher_low']) &
            df['in_mean_zone']
        )
        
        df['sell_context'] = (
            (df['trend'] == 'BEARISH') &
            (df['lower_high'] | df['lower_low']) &
            df['in_mean_zone']
        )
        
        return df
    
    def identify_pivots_60min(self, df_60min: pd.DataFrame) -> Tuple[List, List]:
        """
        Identifica pivôs de alta e baixa no gráfico 60min
        Aplica a regra dos 17 candles
        
        Args:
            df_60min: DataFrame com dados de 60 minutos
            
        Returns:
            Tuple com (pivôs de alta, pivôs de baixa)
        """
        pivots_high = []
        pivots_low = []
        
        for i in range(self.min_candles_pivot, len(df_60min) - self.min_candles_pivot):
            # Pivô de alta (topo local)
            is_pivot_high = True
            for j in range(1, self.min_candles_pivot + 1):
                if (df_60min.iloc[i]['high'] <= df_60min.iloc[i-j]['high'] or
                    df_60min.iloc[i]['high'] <= df_60min.iloc[i+j]['high']):
                    is_pivot_high = False
                    break
            
            if is_pivot_high:
                pivots_high.append({
                    'index': i,
                    'timestamp': df_60min.index[i],
                    'price': df_60min.iloc[i]['high']
                })
            
            # Pivô de baixa (fundo local)
            is_pivot_low = True
            for j in range(1, self.min_candles_pivot + 1):
                if (df_60min.iloc[i]['low'] >= df_60min.iloc[i-j]['low'] or
                    df_60min.iloc[i]['low'] >= df_60min.iloc[i+j]['low']):
                    is_pivot_low = False
                    break
            
            if is_pivot_low:
                pivots_low.append({
                    'index': i,
                    'timestamp': df_60min.index[i],
                    'price': df_60min.iloc[i]['low']
                })
        
        return pivots_high, pivots_low
    
    def detect_wave3_pattern(self, 
                            df_60min: pd.DataFrame,
                            trend_direction: str) -> Optional[Dict]:
        """
        ETAPA 2: Detecta padrão de Onda 3 no gráfico 60min
        
        Onda 3 (compra):
        1. Fundo anterior (Onda 1)
        2. Topo intermediário (Onda 2)
        3. Fundo mais alto que Onda 1 (início Onda 3)
        4. Rompimento do topo da Onda 2 (confirmação Onda 3)
        
        Args:
            df_60min: DataFrame com dados de 60 minutos
            trend_direction: 'BULLISH' ou 'BEARISH'
            
        Returns:
            Dict com dados da Onda 3 ou None
        """
        pivots_high, pivots_low = self.identify_pivots_60min(df_60min)
        
        if trend_direction == 'BULLISH':
            # Busca padrão de compra (Onda 3 de alta)
            if len(pivots_low) >= 2 and len(pivots_high) >= 1:
                # Últimos 2 fundos e último topo
                wave1_low = pivots_low[-2]  # Fundo da Onda 1
                wave2_high = pivots_high[-1]  # Topo da Onda 2
                wave3_low = pivots_low[-1]  # Fundo da Onda 3
                
                # Validações:
                # 1. Fundo da Onda 3 é mais alto que Onda 1 (higher low)
                if wave3_low['price'] <= wave1_low['price']:
                    return None
                
                # 2. Topo da Onda 2 está entre os fundos
                if not (wave1_low['index'] < wave2_high['index'] < wave3_low['index']):
                    return None
                
                # 3. Verifica se houve rompimento do topo da Onda 2
                current_price = df_60min.iloc[-1]['close']
                breakout = current_price > wave2_high['price']
                
                if breakout:
                    return {
                        'type': 'BUY',
                        'wave1_low': wave1_low,
                        'wave2_high': wave2_high,
                        'wave3_low': wave3_low,
                        'entry_price': current_price,
                        'stop_loss': wave3_low['price'],
                        'risk': current_price - wave3_low['price'],
                        'confirmed': True,
                        'candles_since_pivot': len(df_60min) - wave3_low['index'] - 1
                    }
        
        elif trend_direction == 'BEARISH':
            # Busca padrão de venda (Onda 3 de baixa)
            if len(pivots_high) >= 2 and len(pivots_low) >= 1:
                wave1_high = pivots_high[-2]  # Topo da Onda 1
                wave2_low = pivots_low[-1]  # Fundo da Onda 2
                wave3_high = pivots_high[-1]  # Topo da Onda 3
                
                # Validações
                if wave3_high['price'] >= wave1_high['price']:
                    return None
                
                if not (wave1_high['index'] < wave2_low['index'] < wave3_high['index']):
                    return None
                
                current_price = df_60min.iloc[-1]['close']
                breakout = current_price < wave2_low['price']
                
                if breakout:
                    return {
                        'type': 'SELL',
                        'wave1_high': wave1_high,
                        'wave2_low': wave2_low,
                        'wave3_high': wave3_high,
                        'entry_price': current_price,
                        'stop_loss': wave3_high['price'],
                        'risk': wave3_high['price'] - current_price,
                        'confirmed': True,
                        'candles_since_pivot': len(df_60min) - wave3_high['index'] - 1
                    }
        
        return None
    
    def generate_signal(self,
                       df_daily: pd.DataFrame,
                       df_60min: pd.DataFrame,
                       symbol: str) -> Optional[Wave3Signal]:
        """
        Gera sinal de trading combinando análise daily + 60min
        
        Args:
            df_daily: Dados diários
            df_60min: Dados de 60 minutos
            symbol: Símbolo do ativo
            
        Returns:
            Wave3Signal ou None
        """
        # ETAPA 1: Analisa contexto diário
        df_daily_analyzed = self.calculate_daily_context(df_daily)
        
        if len(df_daily_analyzed) < self.mma_long:
            return None
        
        latest_daily = df_daily_analyzed.iloc[-1]
        
        # Verifica se há contexto favorável
        if not (latest_daily['buy_context'] or latest_daily['sell_context']):
            return None
        
        trend_direction = latest_daily['trend']
        
        # ETAPA 2: Busca Onda 3 no gráfico 60min
        wave3_pattern = self.detect_wave3_pattern(df_60min, trend_direction)
        
        if wave3_pattern is None or not wave3_pattern['confirmed']:
            return None
        
        # ETAPA 3: Calcula níveis de entrada, stop e alvo
        entry_price = wave3_pattern['entry_price']
        stop_loss = wave3_pattern['stop_loss']
        risk = wave3_pattern['risk']
        
        # Alvo 3:1
        if wave3_pattern['type'] == 'BUY':
            target_price = entry_price + (risk * self.risk_reward_ratio)
        else:
            target_price = entry_price - (risk * self.risk_reward_ratio)
        
        reward = abs(target_price - entry_price)
        
        # Cria sinal
        signal = Wave3Signal(
            timestamp=df_60min.index[-1],
            symbol=symbol,
            signal_type=wave3_pattern['type'],
            entry_price=entry_price,
            stop_loss=stop_loss,
            target_price=target_price,
            risk=risk,
            reward=reward,
            context_daily={
                'trend': trend_direction,
                'mma_72': latest_daily['mma_72'],
                'mma_17': latest_daily['mma_17'],
                'in_mean_zone': latest_daily['in_mean_zone'],
                'distance_to_mma72': latest_daily['distance_to_mma72']
            },
            wave3_confirmed=True,
            candles_since_pivot=wave3_pattern['candles_since_pivot']
        )
        
        self.last_signal = signal
        return signal
    
    def update_trailing_stop(self,
                            df_60min: pd.DataFrame,
                            position_type: str,
                            current_stop: float) -> float:
        """
        ETAPA 4: Atualiza trailing stop baseado em novos fundos confirmados
        
        Args:
            df_60min: Dados de 60 minutos
            position_type: 'BUY' ou 'SELL'
            current_stop: Stop loss atual
            
        Returns:
            Novo stop loss
        """
        pivots_high, pivots_low = self.identify_pivots_60min(df_60min)
        
        if position_type == 'BUY':
            # Move stop para o último fundo confirmado
            if pivots_low:
                last_pivot_low = pivots_low[-1]['price']
                # Só move o stop para cima
                if last_pivot_low > current_stop:
                    return last_pivot_low
        
        elif position_type == 'SELL':
            # Move stop para o último topo confirmado
            if pivots_high:
                last_pivot_high = pivots_high[-1]['price']
                # Só move o stop para baixo
                if last_pivot_high < current_stop:
                    return last_pivot_high
        
        return current_stop
    
    def check_exit_conditions(self,
                             current_price: float,
                             position: Dict) -> Tuple[bool, str]:
        """
        Verifica condições de saída
        
        Args:
            current_price: Preço atual
            position: Dados da posição aberta
            
        Returns:
            Tuple (should_exit: bool, reason: str)
        """
        if position['type'] == 'BUY':
            # Hit target
            if current_price >= position['target']:
                return True, 'TARGET_HIT'
            
            # Hit stop loss
            if current_price <= position['stop_loss']:
                return True, 'STOP_LOSS'
        
        elif position['type'] == 'SELL':
            if current_price <= position['target']:
                return True, 'TARGET_HIT'
            
            if current_price >= position['stop_loss']:
                return True, 'STOP_LOSS'
        
        return False, ''
    
    def get_strategy_stats(self) -> Dict:
        """
        Retorna estatísticas da estratégia
        
        Returns:
            Dict com estatísticas
        """
        return {
            'name': 'Wave3 Multi-Timeframe',
            'timeframes': ['daily', '60min'],
            'parameters': {
                'mma_long': self.mma_long,
                'mma_short': self.mma_short,
                'min_candles_pivot': self.min_candles_pivot,
                'risk_reward_ratio': self.risk_reward_ratio,
                'mean_zone_tolerance': self.mean_zone_tolerance
            },
            'expected_win_rate': '50-52%',
            'expected_profit_factor': '3.0',
            'methodology': 'André Moraes - Trend Following'
        }


def example_usage():
    """Exemplo de uso da estratégia"""
    
    # Inicializa estratégia
    strategy = Wave3MultiTimeframe(
        mma_long=72,
        mma_short=17,
        min_candles_pivot=17,
        risk_reward_ratio=3.0,
        mean_zone_tolerance=0.01
    )
    
    # Exemplo com DataFrames (substituir por dados reais)
    import pandas as pd
    
    # Simula dados diários
    df_daily = pd.DataFrame({
        'close': np.random.randn(100).cumsum() + 100,
        'open': np.random.randn(100).cumsum() + 100,
        'high': np.random.randn(100).cumsum() + 102,
        'low': np.random.randn(100).cumsum() + 98,
        'volume': np.random.randint(1000, 10000, 100)
    })
    df_daily.index = pd.date_range('2024-01-01', periods=100, freq='D')
    
    # Simula dados 60min
    df_60min = pd.DataFrame({
        'close': np.random.randn(500).cumsum() + 100,
        'open': np.random.randn(500).cumsum() + 100,
        'high': np.random.randn(500).cumsum() + 102,
        'low': np.random.randn(500).cumsum() + 98,
        'volume': np.random.randint(100, 1000, 500)
    })
    df_60min.index = pd.date_range('2024-01-01', periods=500, freq='60min')
    
    # Gera sinal
    signal = strategy.generate_signal(df_daily, df_60min, 'PETR4')
    
    if signal:
        print(f"\n🎯 SINAL GERADO: {signal.signal_type}")
        print(f"   Símbolo: {signal.symbol}")
        print(f"   Entrada: R$ {signal.entry_price:.2f}")
        print(f"   Stop: R$ {signal.stop_loss:.2f}")
        print(f"   Alvo: R$ {signal.target_price:.2f}")
        print(f"   Risco: R$ {signal.risk:.2f}")
        print(f"   Retorno esperado: R$ {signal.reward:.2f}")
        print(f"   R/R: 1:{signal.reward/signal.risk:.1f}")
        print(f"\n   Contexto Daily:")
        print(f"   - Tendência: {signal.context_daily['trend']}")
        print(f"   - MMA72: R$ {signal.context_daily['mma_72']:.2f}")
        print(f"   - MMA17: R$ {signal.context_daily['mma_17']:.2f}")
        print(f"   - Na zona: {signal.context_daily['in_mean_zone']}")
    else:
        print("❌ Nenhum sinal gerado")
    
    # Estatísticas
    stats = strategy.get_strategy_stats()
    print(f"\n📊 Estatísticas da Estratégia:")
    for key, value in stats.items():
        print(f"   {key}: {value}")


if __name__ == '__main__':
    example_usage()
