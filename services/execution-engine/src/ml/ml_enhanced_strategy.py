"""
ML-Enhanced Strategy
B3 Trading Platform

Estratégia que combina sinais de estratégia base com filtro ML.
Inclui sistema completo de backtesting comparativo com métricas profissionais.
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, List
from loguru import logger
from datetime import datetime

from .signal_classifier import SignalClassifier, MLSignalFilter
from .feature_engineer import FeatureEngineer


class MLEnhancedStrategy:
    """
    Estratégia melhorada com ML.
    
    Combina sinais de uma estratégia técnica base (ex: mean_reversion)
    com predições de um classificador ML treinado.
    """
    
    def __init__(
        self,
        base_strategy_name: str,
        base_strategy_params: Dict,
        classifier: SignalClassifier,
        feature_engineer: FeatureEngineer,
        confidence_threshold: float = 0.6,
        regime: Optional[str] = None
    ):
        """
        Inicializa estratégia ML-enhanced.
        
        Args:
            base_strategy_name: Nome da estratégia base (ex: 'mean_reversion')
            base_strategy_params: Parâmetros da estratégia base
            classifier: SignalClassifier treinado
            feature_engineer: FeatureEngineer para criar features
            confidence_threshold: Threshold de confiança ML
            regime: Regime de mercado (opcional)
        """
        self.base_strategy_name = base_strategy_name
        self.base_strategy_params = base_strategy_params
        self.classifier = classifier
        self.feature_engineer = feature_engineer
        self.regime = regime
        self.ml_filter = MLSignalFilter(classifier, confidence_threshold)
        
    def generate_base_signals(self, df: pd.DataFrame) -> pd.Series:
        """
        Gera sinais da estratégia base.
        
        Args:
            df: DataFrame com OHLCV
            
        Returns:
            Series com sinais numéricos (1=compra, -1=venda, 0=neutro)
        """
        # Importar estratégias dinamicamente
        from ..strategies.strategy_manager import StrategyManager
        
        strategy_manager = StrategyManager()
        strategy = strategy_manager.get_strategy(self.base_strategy_name, self.base_strategy_params)
        
        if strategy is None:
            raise ValueError(f"Estratégia base não encontrada: {self.base_strategy_name}")
        
        # Executar estratégia base
        df_result = strategy.run(df.copy())
        
        # Converter sinais de string para números
        signal_map = {'BUY': 1, 'SELL': -1, 'HOLD': 0}
        signals = df_result['signal'].map(signal_map).fillna(0)
        
        return signals
    
    def generate_signals(self, df: pd.DataFrame) -> Dict:
        """
        Gera sinais combinando estratégia base + ML.
        
        Args:
            df: DataFrame com OHLCV
            
        Returns:
            Dicionário com:
            - base_signals: sinais da estratégia base
            - ml_signals: sinais após filtro ML
            - ml_confidences: probabilidades do ML
            - features: features utilizadas
        """
        # 1. Criar features
        df_features = self.feature_engineer.create_all_features(df.copy(), regime=self.regime)
        df_features = self.feature_engineer.normalize_features(df_features)
        df_features = df_features.dropna()
        
        # 2. Gerar sinais base
        base_signals = self.generate_base_signals(df_features)
        
        # 3. Filtrar com ML
        feature_cols = [c for c in df_features.columns 
                       if c not in ['open', 'high', 'low', 'close', 'volume']]
        X = df_features[feature_cols]
        
        ml_signals, ml_confidences = self.ml_filter.filter_signals(base_signals, X)
        
        # 4. Estatísticas
        total_base_signals = (base_signals != 0).sum()
        total_ml_signals = (ml_signals != 0).sum()
        acceptance_rate = total_ml_signals / total_base_signals if total_base_signals > 0 else 0
        
        logger.info(f"Base signals: {total_base_signals}")
        logger.info(f"ML signals: {total_ml_signals}")
        logger.info(f"Acceptance rate: {acceptance_rate:.2%}")
        
        return {
            "base_signals": base_signals,
            "ml_signals": ml_signals,
            "ml_confidences": ml_confidences,
            "features": df_features,
            "statistics": {
                "total_base_signals": int(total_base_signals),
                "total_ml_signals": int(total_ml_signals),
                "acceptance_rate": float(acceptance_rate),
                "avg_confidence": float(ml_confidences[ml_signals != 0].mean()) if total_ml_signals > 0 else 0.0
            }
        }
    
    def backtest_comparison(
        self, 
        df: pd.DataFrame, 
        initial_capital: float = 100000,
        commission: float = 0.0025,
        slippage: float = 0.001
    ) -> Dict:
        """
        Compara performance da estratégia base vs ML-enhanced com métricas profissionais.
        
        Args:
            df: DataFrame com OHLCV
            initial_capital: Capital inicial
            commission: Taxa de corretagem (0.25% = 0.0025)
            slippage: Slippage estimado (0.1% = 0.001)
            
        Returns:
            Dicionário com métricas comparativas completas
        """
        # Gerar sinais
        result = self.generate_signals(df)
        df_signals = result['features'].copy()
        df_signals['base_signal'] = result['base_signals']
        df_signals['ml_signal'] = result['ml_signals']
        
        # Calcular métricas para ambas estratégias
        metrics_base = self._calculate_backtest_metrics(
            df_signals, 
            df_signals['base_signal'],
            initial_capital,
            commission,
            slippage,
            "Base Strategy"
        )
        
        metrics_ml = self._calculate_backtest_metrics(
            df_signals,
            df_signals['ml_signal'],
            initial_capital,
            commission,
            slippage,
            "ML Enhanced"
        )
        
        # Análise de sinais filtrados
        signal_analysis = self._analyze_filtered_signals(
            df_signals,
            result['base_signals'],
            result['ml_signals'],
            result['ml_confidences']
        )
        
        # Comparação e melhorias
        improvement = self._calculate_improvement(metrics_base, metrics_ml)
        
        return {
            "base_strategy": metrics_base,
            "ml_enhanced": metrics_ml,
            "improvement": improvement,
            "signal_analysis": signal_analysis,
            "summary": {
                "better_sharpe": metrics_ml['sharpe_ratio'] > metrics_base['sharpe_ratio'],
                "better_return": metrics_ml['total_return'] > metrics_base['total_return'],
                "fewer_trades": metrics_ml['total_trades'] < metrics_base['total_trades'],
                "better_win_rate": metrics_ml['win_rate'] > metrics_base['win_rate'],
                "recommendation": self._get_recommendation(metrics_base, metrics_ml)
            }
        }
    
    def _calculate_backtest_metrics(
        self,
        df: pd.DataFrame,
        signals: pd.Series,
        initial_capital: float,
        commission: float,
        slippage: float,
        strategy_name: str
    ) -> Dict:
        """
        Calcula métricas completas de backtesting.
        
        Returns:
            Dicionário com todas as métricas
        """
        # Inicializar
        capital = float(initial_capital)
        position = 0
        entry_price = 0.0
        trades = []
        equity_curve = []
        
        # Reset index para iterar corretamente e garantir float
        df_temp = df.reset_index(drop=True)
        signals_temp = signals.reset_index(drop=True)
        
        # Garantir que signals são numéricos
        signals_temp = signals_temp.astype(float)
        
        for i in range(len(df_temp)):
            signal = float(signals_temp.iloc[i])
            price = float(df_temp.loc[i, 'close'])
            
            # Registrar equity
            if position != 0:
                unrealized_pnl = position * (price - entry_price)
                equity_curve.append(capital + unrealized_pnl)
            else:
                equity_curve.append(capital)
            
            # Executar trade
            if signal == 1 and position <= 0:  # Compra
                if position < 0:  # Fechar short
                    pnl = -position * (entry_price - price)
                    cost = abs(position * price) * (commission + slippage)
                    capital += pnl - cost
                    trades.append({
                        'type': 'short',
                        'entry': entry_price,
                        'exit': price,
                        'pnl': pnl - cost,
                        'return': (entry_price - price) / entry_price
                    })
                
                # Abrir long
                shares = int((capital * 0.95) / (price * (1 + commission + slippage)))
                if shares > 0:
                    cost = shares * price * (commission + slippage)
                    capital -= cost
                    position = shares
                    entry_price = price
                    
            elif signal == -1 and position >= 0:  # Venda
                if position > 0:  # Fechar long
                    pnl = position * (price - entry_price)
                    cost = position * price * (commission + slippage)
                    capital += pnl - cost
                    trades.append({
                        'type': 'long',
                        'entry': entry_price,
                        'exit': price,
                        'pnl': pnl - cost,
                        'return': (price - entry_price) / entry_price
                    })
                
                # Abrir short
                shares = int((capital * 0.95) / (price * (1 + commission + slippage)))
                if shares > 0:
                    cost = shares * price * (commission + slippage)
                    capital -= cost
                    position = -shares
                    entry_price = price
        
        # Fechar posição final
        if position != 0:
            final_price = df_temp.loc[len(df_temp)-1, 'close']
            if position > 0:
                pnl = position * (final_price - entry_price)
                cost = position * final_price * (commission + slippage)
                capital += pnl - cost
                trades.append({
                    'type': 'long',
                    'entry': entry_price,
                    'exit': final_price,
                    'pnl': pnl - cost,
                    'return': (final_price - entry_price) / entry_price
                })
            else:
                pnl = -position * (entry_price - final_price)
                cost = abs(position * final_price) * (commission + slippage)
                capital += pnl - cost
                trades.append({
                    'type': 'short',
                    'entry': entry_price,
                    'exit': final_price,
                    'pnl': pnl - cost,
                    'return': (entry_price - final_price) / entry_price
                })
            position = 0
        
        # Calcular métricas
        if not trades:
            return {
                "strategy_name": strategy_name,
                "total_trades": 0,
                "total_return": 0.0,
                "sharpe_ratio": 0.0,
                "max_drawdown": 0.0,
                "win_rate": 0.0,
                "profit_factor": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
                "final_capital": initial_capital
            }
        
        returns = [t['return'] for t in trades]
        wins = [t['pnl'] for t in trades if t['pnl'] > 0]
        losses = [t['pnl'] for t in trades if t['pnl'] < 0]
        
        total_return = (capital - initial_capital) / initial_capital
        sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252) if np.std(returns) > 0 else 0
        
        # Drawdown
        equity_series = pd.Series(equity_curve)
        rolling_max = equity_series.expanding().max()
        drawdowns = (equity_series - rolling_max) / rolling_max
        max_drawdown = abs(drawdowns.min())
        
        # Win rate e Profit Factor
        win_rate = len(wins) / len(trades) if trades else 0
        total_wins = sum(wins) if wins else 0
        total_losses = abs(sum(losses)) if losses else 0
        profit_factor = total_wins / total_losses if total_losses > 0 else float('inf')
        
        return {
            "strategy_name": strategy_name,
            "total_trades": len(trades),
            "total_return": round(total_return * 100, 2),
            "sharpe_ratio": round(sharpe, 2),
            "max_drawdown": round(max_drawdown * 100, 2),
            "win_rate": round(win_rate * 100, 2),
            "profit_factor": round(profit_factor, 2),
            "avg_win": round(np.mean(wins), 2) if wins else 0.0,
            "avg_loss": round(np.mean(losses), 2) if losses else 0.0,
            "avg_trade": round(np.mean([t['pnl'] for t in trades]), 2),
            "final_capital": round(capital, 2),
            "equity_curve": [round(e, 2) for e in equity_curve],
            "trades": trades[:10]  # Primeiros 10 trades
        }
    
    def _analyze_filtered_signals(
        self,
        df: pd.DataFrame,
        base_signals: pd.Series,
        ml_signals: pd.Series,
        ml_confidences: pd.Series
    ) -> Dict:
        """
        Analisa sinais que foram filtrados pelo ML.
        """
        # Reset index para trabalhar com posições numéricas
        df_temp = df.reset_index(drop=True)
        base_signals_temp = base_signals.reset_index(drop=True)
        ml_signals_temp = ml_signals.reset_index(drop=True)
        ml_confidences_temp = ml_confidences.reset_index(drop=True)
        
        # Sinais filtrados (rejeitados pelo ML)
        filtered_mask = (base_signals_temp != 0) & (ml_signals_temp == 0)
        filtered_signals = base_signals_temp[filtered_mask]
        
        # Calcular retorno futuro dos sinais filtrados
        future_returns = []
        for idx in filtered_signals.index:
            if idx < len(df_temp) - 5:
                current_price = df_temp.loc[idx, 'close']
                future_price = df_temp.loc[idx + 5, 'close']  # 5 períodos à frente
                ret = (future_price - current_price) / current_price
                future_returns.append(ret * filtered_signals.loc[idx])  # Ajustar pelo sinal
        
        # Sinais aceitos
        accepted_mask = (ml_signals_temp != 0)
        accepted_signals = ml_signals_temp[accepted_mask]
        accepted_confidences = ml_confidences_temp[accepted_mask]
        
        return {
            "total_base_signals": int((base_signals_temp != 0).sum()),
            "total_ml_signals": int((ml_signals_temp != 0).sum()),
            "total_filtered": int(filtered_mask.sum()),
            "filter_rate": round(filtered_mask.sum() / (base_signals_temp != 0).sum() * 100, 2) if (base_signals_temp != 0).sum() > 0 else 0,
            "avg_confidence_accepted": round(accepted_confidences.mean(), 4) if len(accepted_confidences) > 0 else 0,
            "avg_return_filtered_signals": round(np.mean(future_returns) * 100, 2) if future_returns else 0,
            "filtered_signals_distribution": {
                "buy_filtered": int(((base_signals_temp == 1) & (ml_signals_temp == 0)).sum()),
                "sell_filtered": int(((base_signals_temp == -1) & (ml_signals_temp == 0)).sum())
            }
        }
    
    def _calculate_improvement(self, base: Dict, ml: Dict) -> Dict:
        """
        Calcula melhorias do ML sobre a estratégia base.
        """
        return {
            "sharpe_delta": round(ml['sharpe_ratio'] - base['sharpe_ratio'], 2),
            "return_delta": round(ml['total_return'] - base['total_return'], 2),
            "drawdown_reduction": round(base['max_drawdown'] - ml['max_drawdown'], 2),
            "win_rate_delta": round(ml['win_rate'] - base['win_rate'], 2),
            "profit_factor_delta": round(ml['profit_factor'] - base['profit_factor'], 2),
            "trades_reduction": base['total_trades'] - ml['total_trades'],
            "trades_reduction_pct": round((base['total_trades'] - ml['total_trades']) / base['total_trades'] * 100, 2) if base['total_trades'] > 0 else 0
        }
    
    def _get_recommendation(self, base: Dict, ml: Dict) -> str:
        """
        Gera recomendação baseada na comparação.
        """
        ml_score = 0
        
        # Critérios de pontuação
        if ml['sharpe_ratio'] > base['sharpe_ratio']:
            ml_score += 3
        if ml['total_return'] > base['total_return']:
            ml_score += 2
        if ml['max_drawdown'] < base['max_drawdown']:
            ml_score += 2
        if ml['win_rate'] > base['win_rate']:
            ml_score += 1
        if ml['profit_factor'] > base['profit_factor']:
            ml_score += 1
        
        if ml_score >= 7:
            return "STRONGLY_RECOMMENDED - ML melhora significativamente a estratégia"
        elif ml_score >= 5:
            return "RECOMMENDED - ML oferece melhorias consistentes"
        elif ml_score >= 3:
            return "NEUTRAL - ML tem algumas vantagens mas não é conclusivo"
        else:
            return "NOT_RECOMMENDED - Estratégia base performa melhor"
