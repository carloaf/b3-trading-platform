"""
B3 Trading Platform - Walk-Forward Optimizer
=============================================
Otimização Walk-Forward para validação robusta de estratégias.

PASSO 10: Implementação de Walk-Forward Optimization
"""

from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import pandas as pd
import numpy as np
from loguru import logger

try:
    import optuna
    OPTUNA_AVAILABLE = True
except ImportError:
    OPTUNA_AVAILABLE = False
    logger.warning("⚠️  Optuna não instalado. Use: pip install optuna")

from .strategies import StrategyManager
from .backtest import BacktestEngine


@dataclass
class WalkForwardWindow:
    """Representa uma janela de walk-forward."""
    window_id: int
    train_start: datetime
    train_end: datetime
    test_start: datetime
    test_end: datetime
    train_size: int
    test_size: int
    
    # Resultados
    best_params: Optional[Dict] = None
    train_metrics: Optional[Dict] = None
    test_metrics: Optional[Dict] = None
    optimization_trials: int = 0
    
    def to_dict(self) -> Dict:
        """Converte para dicionário."""
        return {
            "window_id": self.window_id,
            "period": {
                "train": {
                    "start": self.train_start.isoformat() if self.train_start else None,
                    "end": self.train_end.isoformat() if self.train_end else None,
                    "size": self.train_size
                },
                "test": {
                    "start": self.test_start.isoformat() if self.test_start else None,
                    "end": self.test_end.isoformat() if self.test_end else None,
                    "size": self.test_size
                }
            },
            "best_params": self.best_params,
            "train_metrics": self.train_metrics,
            "test_metrics": self.test_metrics,
            "optimization_trials": self.optimization_trials
        }


class WalkForwardOptimizer:
    """
    Otimizador Walk-Forward.
    
    Divide dados históricos em múltiplas janelas de treino/teste,
    otimiza parâmetros em cada janela de treino e valida em teste.
    
    Parâmetros:
    -----------
    strategy_name : str
        Nome da estratégia a otimizar
    train_window_days : int
        Tamanho da janela de treino em dias
    test_window_days : int
        Tamanho da janela de teste em dias
    step_days : int
        Passo para avançar a janela (anchored se None)
    optimization_metric : str
        Métrica para otimizar: 'sharpe_ratio', 'total_return', 'profit_factor'
    n_trials : int
        Número de trials do Optuna por janela
    initial_capital : float
        Capital inicial para backtests
    """
    
    def __init__(
        self,
        strategy_name: str,
        train_window_days: int = 180,
        test_window_days: int = 30,
        step_days: Optional[int] = 30,
        optimization_metric: str = "sharpe_ratio",
        n_trials: int = 50,
        initial_capital: float = 100000.0
    ):
        self.strategy_name = strategy_name
        self.train_window_days = train_window_days
        self.test_window_days = test_window_days
        self.step_days = step_days or test_window_days  # Default: rolling
        self.optimization_metric = optimization_metric
        self.n_trials = n_trials
        self.initial_capital = initial_capital
        
        self.strategy_manager = StrategyManager()
        self.windows: List[WalkForwardWindow] = []
        
        if not OPTUNA_AVAILABLE:
            raise ImportError("Optuna é obrigatório. Instale: pip install optuna")
    
    def create_windows(self, df: pd.DataFrame) -> List[WalkForwardWindow]:
        """
        Cria janelas de walk-forward.
        
        Anchored Walk-Forward: janela de treino cresce, teste fixo
        Rolling Walk-Forward: ambas as janelas deslizam com step_days
        """
        if 'time' not in df.columns:
            raise ValueError("DataFrame deve ter coluna 'time'")
        
        df = df.sort_values('time').reset_index(drop=True)
        windows = []
        
        start_date = df['time'].iloc[0]
        end_date = df['time'].iloc[-1]
        
        train_start = start_date
        window_id = 1
        
        while True:
            # Definir período de treino
            train_end = train_start + timedelta(days=self.train_window_days)
            
            # Definir período de teste
            test_start = train_end + timedelta(days=1)
            test_end = test_start + timedelta(days=self.test_window_days)
            
            # Verificar se há dados suficientes
            if test_end > end_date:
                break
            
            # Filtrar dados
            train_df = df[(df['time'] >= train_start) & (df['time'] <= train_end)]
            test_df = df[(df['time'] >= test_start) & (df['time'] <= test_end)]
            
            if len(train_df) < 30 or len(test_df) < 5:
                logger.warning(f"⚠️  Janela {window_id} com poucos dados: train={len(train_df)}, test={len(test_df)}")
                break
            
            window = WalkForwardWindow(
                window_id=window_id,
                train_start=train_start,
                train_end=train_end,
                test_start=test_start,
                test_end=test_end,
                train_size=len(train_df),
                test_size=len(test_df)
            )
            windows.append(window)
            
            logger.info(f"📊 Janela {window_id}: Train {len(train_df)} candles, Test {len(test_df)} candles")
            
            # Avançar janela
            if self.step_days == self.train_window_days + self.test_window_days:
                # Anchored: próximo treino começa do início
                train_start = start_date
            else:
                # Rolling: avançar step_days
                train_start = train_start + timedelta(days=self.step_days)
            
            window_id += 1
            
            # Limite de segurança
            if window_id > 50:
                logger.warning("⚠️  Limite de 50 janelas atingido")
                break
        
        self.windows = windows
        logger.info(f"✅ Criadas {len(windows)} janelas de walk-forward")
        return windows
    
    def _get_param_space(self) -> Dict:
        """
        Define espaço de busca de parâmetros por estratégia.
        """
        spaces = {
            "trend_following": {
                "ema_fast": (5, 20),
                "ema_slow": (15, 50),
                "rsi_period": (10, 20),
                "rsi_overbought": (65, 80),
                "rsi_oversold": (20, 35)
            },
            "mean_reversion": {
                "bb_period": (15, 30),
                "bb_std": (1.5, 3.0),
                "rsi_period": (10, 20),
                "rsi_oversold": (20, 35),
                "rsi_overbought": (65, 80)
            },
            "breakout": {
                "lookback_period": (15, 30),
                "volume_multiplier": (1.2, 2.5)
            },
            "macd_crossover": {
                "macd_fast": (8, 15),
                "macd_slow": (20, 30),
                "macd_signal": (7, 12),
                "volume_multiplier": (1.0, 2.0)
            },
            "rsi_divergence": {
                "rsi_period": (10, 20),
                "lookback_periods": (15, 30),
                "min_adx": (15, 30),
                "volume_multiplier": (1.0, 2.0),
                "min_signal_strength": (0.3, 0.7)
            },
            "dynamic_position_sizing": {
                "ema_fast": (15, 30),
                "ema_slow": (40, 60),
                "rsi_period": (10, 20),
                "risk_per_trade": (0.01, 0.03),
                "max_position_size": (0.15, 0.35)
            }
        }
        
        return spaces.get(self.strategy_name, {})
    
    def _create_objective(self, train_data: List[Dict]) -> callable:
        """Cria função objetivo para Optuna."""
        
        param_space = self._get_param_space()
        
        if not param_space:
            raise ValueError(f"Estratégia '{self.strategy_name}' não tem espaço de parâmetros definido")
        
        def objective(trial: optuna.Trial) -> float:
            """Função objetivo do Optuna."""
            # Sugerir parâmetros
            params = {}
            for param_name, (low, high) in param_space.items():
                if isinstance(low, int):
                    params[param_name] = trial.suggest_int(param_name, low, high)
                else:
                    params[param_name] = trial.suggest_float(param_name, low, high)
            
            try:
                # Executar backtest
                backtest = BacktestEngine(
                    strategy_name=self.strategy_name,
                    initial_capital=self.initial_capital,
                    params=params
                )
                
                # Executar de forma síncrona - criar novo loop para thread
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    result = loop.run_until_complete(backtest.run(train_data))
                finally:
                    loop.close()
                
                # Retornar métrica de otimização
                metric_value = result.get(self.optimization_metric, 0.0)
                
                # Penalizar se não houver trades
                if result.get('total_trades', 0) == 0:
                    return -1000.0
                
                # Penalizar drawdown excessivo
                max_dd = result.get('max_drawdown', 0)
                if max_dd > 0.3 * self.initial_capital:  # > 30% drawdown
                    metric_value *= 0.5
                
                return float(metric_value)
                
            except Exception as e:
                logger.error(f"❌ Erro no trial: {e}")
                return -1000.0
        
        return objective
    
    async def optimize_window(
        self,
        window: WalkForwardWindow,
        train_df: pd.DataFrame,
        test_df: pd.DataFrame
    ) -> WalkForwardWindow:
        """
        Otimiza parâmetros em uma janela específica.
        """
        logger.info(f"🔧 Otimizando janela {window.window_id}...")
        
        # Converter para lista de dicts
        train_data = train_df.to_dict('records')
        test_data = test_df.to_dict('records')
        
        # Executar Optuna em executor separado para evitar conflito de event loop
        import asyncio
        import concurrent.futures
        
        def run_optuna_sync():
            """Executa Optuna de forma síncrona."""
            # Criar estudo Optuna
            study = optuna.create_study(
                direction="maximize",
                sampler=optuna.samplers.TPESampler(seed=42),
                study_name=f"window_{window.window_id}"
            )
            
            # Otimizar
            objective = self._create_objective(train_data)
            study.optimize(
                objective,
                n_trials=self.n_trials,
                show_progress_bar=False,
                n_jobs=1
            )
            
            return study.best_params, study.best_value, len(study.trials)
        
        # Executar em thread pool
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as executor:
            best_params, best_value, n_trials = await loop.run_in_executor(
                executor, run_optuna_sync
            )
        
        window.best_params = best_params
        window.optimization_trials = n_trials
        
        logger.info(f"✅ Melhores parâmetros: {best_params}")
        logger.info(f"📈 Melhor {self.optimization_metric}: {best_value:.4f}")
        
        # Avaliar em treino
        train_backtest = BacktestEngine(
            strategy_name=self.strategy_name,
            initial_capital=self.initial_capital,
            params=best_params
        )
        train_result = await train_backtest.run(train_data)
        window.train_metrics = {
            "total_return": train_result['total_return'],
            "sharpe_ratio": train_result['sharpe_ratio'],
            "max_drawdown": train_result['max_drawdown'],
            "win_rate": train_result['win_rate'],
            "total_trades": train_result['total_trades'],
            "profit_factor": train_result['profit_factor']
        }
        
        # Avaliar em teste (out-of-sample)
        test_backtest = BacktestEngine(
            strategy_name=self.strategy_name,
            initial_capital=self.initial_capital,
            params=best_params
        )
        test_result = await test_backtest.run(test_data)
        window.test_metrics = {
            "total_return": test_result['total_return'],
            "sharpe_ratio": test_result['sharpe_ratio'],
            "max_drawdown": test_result['max_drawdown'],
            "win_rate": test_result['win_rate'],
            "total_trades": test_result['total_trades'],
            "profit_factor": test_result['profit_factor']
        }
        
        train_sharpe = train_result.get('sharpe_ratio', 0.0) or 0.0
        test_sharpe = test_result.get('sharpe_ratio', 0.0) or 0.0
        logger.info(f"📊 Train Sharpe: {train_sharpe:.2f} | Test Sharpe: {test_sharpe:.2f}")
        
        return window
    
    async def run(self, df: pd.DataFrame) -> Dict:
        """
        Executa walk-forward optimization completo.
        """
        logger.info(f"🚀 Iniciando Walk-Forward Optimization: {self.strategy_name}")
        logger.info(f"📅 Train: {self.train_window_days} dias | Test: {self.test_window_days} dias | Step: {self.step_days} dias")
        
        # Criar janelas
        windows = self.create_windows(df)
        
        if not windows:
            raise ValueError("Nenhuma janela criada. Dados insuficientes.")
        
        # Otimizar cada janela
        for window in windows:
            # Filtrar dados
            train_df = df[(df['time'] >= window.train_start) & (df['time'] <= window.train_end)]
            test_df = df[(df['time'] >= window.test_start) & (df['time'] <= window.test_end)]
            
            # Otimizar
            await self.optimize_window(window, train_df, test_df)
        
        # Calcular estatísticas agregadas
        test_returns = [w.test_metrics['total_return'] for w in windows if w.test_metrics and w.test_metrics.get('total_return') is not None]
        test_sharpes = [w.test_metrics['sharpe_ratio'] for w in windows if w.test_metrics and w.test_metrics.get('sharpe_ratio') is not None]
        test_trades = [w.test_metrics['total_trades'] for w in windows if w.test_metrics and w.test_metrics.get('total_trades') is not None]
        
        aggregate_stats = {
            "total_windows": len(windows),
            "avg_test_return": float(np.mean(test_returns)) if test_returns else 0.0,
            "std_test_return": float(np.std(test_returns)) if test_returns else 0.0,
            "avg_test_sharpe": float(np.mean(test_sharpes)) if test_sharpes else 0.0,
            "std_test_sharpe": float(np.std(test_sharpes)) if test_sharpes else 0.0,
            "total_test_trades": int(sum(test_trades)) if test_trades else 0,
            "positive_windows": sum(1 for r in test_returns if r > 0),
            "negative_windows": sum(1 for r in test_returns if r < 0)
        }
        
        logger.info(f"✅ Walk-Forward completo!")
        logger.info(f"📈 Avg Test Sharpe: {aggregate_stats['avg_test_sharpe']:.2f} ± {aggregate_stats['std_test_sharpe']:.2f}")
        logger.info(f"💰 Avg Test Return: R$ {aggregate_stats['avg_test_return']:.2f}")
        logger.info(f"📊 Janelas positivas: {aggregate_stats['positive_windows']}/{len(windows)}")
        
        return {
            "strategy": self.strategy_name,
            "configuration": {
                "train_window_days": self.train_window_days,
                "test_window_days": self.test_window_days,
                "step_days": self.step_days,
                "optimization_metric": self.optimization_metric,
                "n_trials": self.n_trials,
                "initial_capital": self.initial_capital
            },
            "aggregate_statistics": aggregate_stats,
            "windows": [w.to_dict() for w in windows]
        }
