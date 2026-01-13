"""
B3 Trading Platform - Strategy Manager
========================================
Gerenciador centralizado de todas as estratégias disponíveis.

Funcionalidades:
- Registro e instanciação de estratégias
- Listagem de estratégias com descrições
- Comparação de performance entre estratégias
- Recomendação de estratégias por condição de mercado
"""

from typing import Dict, Any, List, Type, Optional

import pandas as pd
from loguru import logger

from .base_strategy import BaseStrategy
from .trend_following import TrendFollowingStrategy
from .mean_reversion import MeanReversionStrategy
from .breakout import BreakoutStrategy
from .macd_crossover import MACDCrossoverStrategy
from .rsi_divergence import RSIDivergenceStrategy
from .dynamic_position_sizing import DynamicPositionSizingStrategy


class StrategyManager:
    """
    Gerenciador central de todas as estratégias disponíveis.
    
    Exemplo de uso:
        manager = StrategyManager()
        
        # Listar estratégias
        strategies = manager.list_strategies()
        
        # Obter uma estratégia
        strategy = manager.get_strategy('rsi_divergence', {'rsi_period': 14})
        
        # Executar estratégia
        df_result = strategy.run(df)
        
        # Comparar estratégias
        comparison = manager.compare_strategies(['trend_following', 'rsi_divergence'], df)
    """
    
    # Registro de todas as estratégias disponíveis
    STRATEGIES: Dict[str, Type[BaseStrategy]] = {
        'trend_following': TrendFollowingStrategy,
        'mean_reversion': MeanReversionStrategy,
        'breakout': BreakoutStrategy,
        'macd_crossover': MACDCrossoverStrategy,
        'rsi_divergence': RSIDivergenceStrategy,
        'dynamic_position_sizing': DynamicPositionSizingStrategy,
    }
    
    # Descrições das estratégias para documentação
    STRATEGY_DESCRIPTIONS: Dict[str, str] = {
        'trend_following': """
            Estratégia de seguimento de tendência usando EMAs, volume e RSI.
            Melhor para: Mercados em tendência forte
            Timeframe recomendado: 1h, 4h, diário
            Risk/Reward: Médio/Alto
        """,
        'mean_reversion': """
            Estratégia de reversão à média usando Bollinger Bands.
            Melhor para: Mercados laterais, alta volatilidade
            Timeframe recomendado: 15m, 1h
            Risk/Reward: Alto/Médio
        """,
        'breakout': """
            Estratégia de rompimento de faixas de consolidação.
            Melhor para: Início de tendências, após consolidações
            Timeframe recomendado: 1h, 4h
            Risk/Reward: Médio/Alto
        """,
        'macd_crossover': """
            Combinação de MACD e volume para sinais confirmados.
            Melhor para: Qualquer mercado, uso geral
            Timeframe recomendado: 1h, 4h
            Risk/Reward: Médio/Médio
        """,
        'rsi_divergence': """
            Detecta divergências entre preço e RSI (4 padrões).
            Melhor para: Reversões, mercados voláteis
            Timeframe recomendado: 1h, 4h
            Risk/Reward: Alto/Alto
        """,
        'dynamic_position_sizing': """
            Gestão de risco com tamanho de posição dinâmico (Kelly Criterion).
            Melhor para: Proteção de capital, gestão de risco
            Timeframe recomendado: Qualquer
            Risk/Reward: Baixo/Médio (foco em preservação)
        """
    }
    
    def __init__(self):
        """Inicializa o gerenciador de estratégias."""
        self._cache: Dict[str, BaseStrategy] = {}
        logger.info(f"StrategyManager inicializado com {len(self.STRATEGIES)} estratégias")
    
    @classmethod
    def get_strategy(cls, strategy_name: str, params: Optional[Dict[str, Any]] = None) -> BaseStrategy:
        """
        Cria instância de uma estratégia pelo nome.
        
        Args:
            strategy_name: Nome da estratégia (case insensitive).
            params: Parâmetros customizados (opcional).
            
        Returns:
            Instância da estratégia.
            
        Raises:
            ValueError: Se estratégia não existe.
        """
        strategy_key = strategy_name.lower().replace(' ', '_').replace('-', '_')
        
        if strategy_key not in cls.STRATEGIES:
            available = ', '.join(cls.STRATEGIES.keys())
            raise ValueError(
                f"Estratégia '{strategy_name}' não encontrada. "
                f"Disponíveis: {available}"
            )
        
        strategy_class = cls.STRATEGIES[strategy_key]
        return strategy_class(params)
    
    @classmethod
    def list_strategies(cls) -> List[Dict[str, Any]]:
        """
        Lista todas as estratégias disponíveis com suas descrições.
        
        Returns:
            Lista de dicionários com info das estratégias.
        """
        strategies_info = []
        
        for key, strategy_class in cls.STRATEGIES.items():
            # Criar instância temporária para obter informações
            temp_instance = strategy_class()
            
            strategies_info.append({
                'id': key,
                'name': temp_instance.name,
                'description': temp_instance.description,
                'version': temp_instance.version,
                'class': strategy_class.__name__,
                'default_parameters': temp_instance.params,
                'entry_conditions': temp_instance.get_entry_conditions(),
                'exit_conditions': temp_instance.get_exit_conditions(),
                'long_description': cls.STRATEGY_DESCRIPTIONS.get(key, '').strip()
            })
        
        return strategies_info
    
    @classmethod
    def get_strategy_class(cls, strategy_name: str) -> Type[BaseStrategy]:
        """
        Retorna a classe da estratégia (não instancia).
        
        Args:
            strategy_name: Nome da estratégia.
            
        Returns:
            Classe da estratégia.
        """
        strategy_key = strategy_name.lower().replace(' ', '_').replace('-', '_')
        
        if strategy_key not in cls.STRATEGIES:
            available = ', '.join(cls.STRATEGIES.keys())
            raise ValueError(f"Estratégia '{strategy_name}' não encontrada. Disponíveis: {available}")
        
        return cls.STRATEGIES[strategy_key]
    
    @classmethod
    def get_strategy_description(cls, strategy_name: str) -> Dict[str, Any]:
        """
        Obtém descrição detalhada de uma estratégia específica.
        
        Args:
            strategy_name: Nome da estratégia.
            
        Returns:
            Dicionário com descrição detalhada.
        """
        strategy = cls.get_strategy(strategy_name)
        strategy_key = strategy_name.lower().replace(' ', '_').replace('-', '_')
        
        return {
            'name': strategy.name,
            'description': strategy.description,
            'version': strategy.version,
            'parameters': strategy.params,
            'entry_conditions': strategy.get_entry_conditions(),
            'exit_conditions': strategy.get_exit_conditions(),
            'long_description': cls.STRATEGY_DESCRIPTIONS.get(strategy_key, '').strip()
        }
    
    @classmethod
    def compare_strategies(
        cls, 
        strategies: List[str], 
        df: pd.DataFrame, 
        initial_capital: float = 10000
    ) -> Dict[str, Any]:
        """
        Compara performance de múltiplas estratégias.
        
        Args:
            strategies: Lista de nomes de estratégias.
            df: DataFrame com dados OHLCV.
            initial_capital: Capital inicial para simulação.
            
        Returns:
            Comparação de performances.
        """
        results = {}
        
        for strategy_name in strategies:
            try:
                strategy = cls.get_strategy(strategy_name)
                df_result = strategy.run(df.copy())
                
                # Calcular métricas
                sharpe = strategy.calculate_sharpe_ratio(df_result)
                max_dd = strategy.calculate_max_drawdown(df_result)
                
                # Contar sinais
                signals_df = df_result[df_result['signal'] != 'HOLD'] if df_result['signal'].dtype == object else df_result[df_result['signal'] != 0]
                total_trades = len(signals_df)
                
                # Calcular retorno total
                df_result['returns'] = df_result['close'].pct_change()
                
                if df_result['signal'].dtype == object:
                    signal_map = {'BUY': 1, 'SELL': -1, 'HOLD': 0}
                    df_result['signal_num'] = df_result['signal'].map(signal_map).fillna(0)
                else:
                    df_result['signal_num'] = df_result['signal']
                
                df_result['strategy_returns'] = df_result['returns'] * df_result['signal_num'].shift(1)
                total_return = (1 + df_result['strategy_returns'].fillna(0)).prod() - 1
                
                results[strategy_name] = {
                    'sharpe_ratio': round(float(sharpe), 2),
                    'max_drawdown': round(float(max_dd * 100), 2),  # em percentual
                    'total_return': round(float(total_return * 100), 2),  # em percentual
                    'total_trades': int(total_trades),
                    'status': 'success'
                }
                
            except Exception as e:
                logger.error(f"Erro ao comparar estratégia {strategy_name}: {e}")
                results[strategy_name] = {
                    'status': 'error',
                    'error': str(e)
                }
        
        # Ranking
        successful = {k: v for k, v in results.items() if v.get('status') == 'success'}
        if successful:
            best_sharpe = max(successful.items(), key=lambda x: x[1].get('sharpe_ratio', -999))
            best_return = max(successful.items(), key=lambda x: x[1].get('total_return', -999))
            lowest_dd = min(successful.items(), key=lambda x: x[1].get('max_drawdown', 999))
            
            results['_ranking'] = {
                'best_sharpe': best_sharpe[0],
                'best_return': best_return[0],
                'lowest_drawdown': lowest_dd[0]
            }
        
        return results
    
    async def generate_signal(
        self, 
        strategy_name: str, 
        data: List[Dict], 
        params: Optional[Dict] = None
    ) -> Dict:
        """
        Gera sinal para dados fornecidos (compatibilidade com versão anterior).
        
        Args:
            strategy_name: Nome da estratégia.
            data: Lista de dicionários com dados OHLCV.
            params: Parâmetros customizados.
            
        Returns:
            Dicionário com informações do sinal.
        """
        df = pd.DataFrame(data)
        
        # Garantir tipos corretos
        for col in ["open", "high", "low", "close"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        
        if "volume" in df.columns:
            df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0).astype(int)
        
        strategy = self.get_strategy(strategy_name, params)
        signal = strategy.get_current_signal(df)
        
        return signal.to_dict()


def get_recommended_strategy(market_condition: str) -> List[str]:
    """
    Recomenda estratégias baseado nas condições de mercado.
    
    Args:
        market_condition: Condição atual do mercado.
            - 'trending_up': Tendência de alta
            - 'trending_down': Tendência de baixa
            - 'ranging': Mercado lateral
            - 'volatile': Alta volatilidade
            
    Returns:
        Lista de estratégias recomendadas.
        
    Example:
        >>> strategies = get_recommended_strategy('volatile')
        >>> print(strategies)
        ['rsi_divergence', 'dynamic_position_sizing', 'mean_reversion']
    """
    recommendations = {
        'trending_up': ['trend_following', 'breakout', 'macd_crossover'],
        'trending_down': ['mean_reversion', 'dynamic_position_sizing', 'rsi_divergence'],
        'ranging': ['mean_reversion', 'rsi_divergence', 'breakout'],
        'volatile': ['rsi_divergence', 'dynamic_position_sizing', 'mean_reversion']
    }
    
    return recommendations.get(market_condition.lower(), ['macd_crossover', 'trend_following'])


def detect_market_regime(df: pd.DataFrame) -> str:
    """
    Detecta o regime de mercado atual (PASSO 8 do plano).
    
    Usa ADX e volatilidade para classificar:
    - trending_up: ADX > 25 e preço acima da SMA50
    - trending_down: ADX > 25 e preço abaixo da SMA50
    - ranging: ADX < 20
    - volatile: ATR% > 3%
    
    Args:
        df: DataFrame com dados OHLCV.
        
    Returns:
        Regime de mercado: 'trending_up', 'trending_down', 'ranging', 'volatile'
    """
    if len(df) < 50:
        return 'unknown'
    
    df = df.copy()
    
    # Calcular indicadores
    from .base_strategy import calculate_adx, calculate_atr, calculate_sma
    
    df['adx'], _, _ = calculate_adx(df, 14)
    df['atr'] = calculate_atr(df, 14)
    df['sma50'] = calculate_sma(df['close'], 50)
    df['atr_pct'] = (df['atr'] / df['close']) * 100
    
    # Últimos valores
    last = df.iloc[-1]
    
    adx = last['adx'] if pd.notna(last['adx']) else 0
    atr_pct = last['atr_pct'] if pd.notna(last['atr_pct']) else 0
    close = last['close']
    sma50 = last['sma50'] if pd.notna(last['sma50']) else close
    
    # Classificar regime
    if atr_pct > 3.0:
        return 'volatile'
    elif adx > 25:
        if close > sma50:
            return 'trending_up'
        else:
            return 'trending_down'
    else:
        return 'ranging'
