"""
Performance Analytics
B3 Trading Platform

Métricas avançadas de performance para backtesting.
Inclui: Sortino Ratio, Calmar Ratio, MAE, MFE, Ulcer Index, etc.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional
from loguru import logger


class PerformanceAnalytics:
    """
    Calcula métricas avançadas de performance para estratégias de trading.
    """
    
    @staticmethod
    def calculate_all_metrics(
        equity_curve: List[float],
        trades: List[Dict],
        returns: List[float],
        initial_capital: float,
        risk_free_rate: float = 0.0
    ) -> Dict:
        """
        Calcula todas as métricas de performance.
        
        Args:
            equity_curve: Lista com evolução do capital
            trades: Lista de trades executados
            returns: Lista de retornos diários
            initial_capital: Capital inicial
            risk_free_rate: Taxa livre de risco (anualizada)
            
        Returns:
            Dicionário com todas as métricas
        """
        if not trades:
            return PerformanceAnalytics._empty_metrics()
        
        # Métricas básicas
        total_return = (equity_curve[-1] - initial_capital) / initial_capital
        
        # Métricas de risco
        sharpe = PerformanceAnalytics.sharpe_ratio(returns, risk_free_rate)
        sortino = PerformanceAnalytics.sortino_ratio(returns, risk_free_rate)
        calmar = PerformanceAnalytics.calmar_ratio(returns, equity_curve)
        
        # Drawdown
        max_dd, max_dd_duration = PerformanceAnalytics.max_drawdown(equity_curve)
        ulcer = PerformanceAnalytics.ulcer_index(equity_curve)
        
        # Trades
        win_rate = PerformanceAnalytics.win_rate(trades)
        profit_factor = PerformanceAnalytics.profit_factor(trades)
        avg_win, avg_loss = PerformanceAnalytics.avg_win_loss(trades)
        
        # MAE/MFE
        mae, mfe = PerformanceAnalytics.mae_mfe_analysis(trades)
        
        # Expectativa
        expectancy = PerformanceAnalytics.expectancy(trades)
        
        # Recovery Factor
        recovery = total_return / max_dd if max_dd > 0 else float('inf')
        
        return {
            "total_return": round(total_return * 100, 2),
            "sharpe_ratio": round(sharpe, 2),
            "sortino_ratio": round(sortino, 2),
            "calmar_ratio": round(calmar, 2),
            "max_drawdown": round(max_dd * 100, 2),
            "max_drawdown_duration_days": int(max_dd_duration),
            "ulcer_index": round(ulcer, 2),
            "win_rate": round(win_rate * 100, 2),
            "profit_factor": round(profit_factor, 2),
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "expectancy": round(expectancy, 2),
            "recovery_factor": round(recovery, 2),
            "total_trades": len(trades),
            "winning_trades": sum(1 for t in trades if t['pnl'] > 0),
            "losing_trades": sum(1 for t in trades if t['pnl'] < 0),
            "mae": round(mae, 4),
            "mfe": round(mfe, 4),
            "final_capital": round(equity_curve[-1], 2)
        }
    
    @staticmethod
    def sharpe_ratio(returns: List[float], risk_free_rate: float = 0.0) -> float:
        """
        Calcula Sharpe Ratio anualizado.
        """
        if not returns or len(returns) < 2:
            return 0.0
        
        returns_array = np.array(returns)
        excess_returns = returns_array - (risk_free_rate / 252)
        
        if np.std(excess_returns) == 0:
            return 0.0
        
        return np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(252)
    
    @staticmethod
    def sortino_ratio(returns: List[float], risk_free_rate: float = 0.0) -> float:
        """
        Calcula Sortino Ratio (considera apenas volatilidade negativa).
        """
        if not returns or len(returns) < 2:
            return 0.0
        
        returns_array = np.array(returns)
        excess_returns = returns_array - (risk_free_rate / 252)
        
        # Downside deviation (apenas retornos negativos)
        downside_returns = excess_returns[excess_returns < 0]
        
        if len(downside_returns) == 0:
            return float('inf')
        
        downside_std = np.std(downside_returns)
        
        if downside_std == 0:
            return 0.0
        
        return np.mean(excess_returns) / downside_std * np.sqrt(252)
    
    @staticmethod
    def calmar_ratio(returns: List[float], equity_curve: List[float]) -> float:
        """
        Calcula Calmar Ratio (retorno anual / max drawdown).
        """
        if not returns or not equity_curve:
            return 0.0
        
        annual_return = np.mean(returns) * 252
        max_dd, _ = PerformanceAnalytics.max_drawdown(equity_curve)
        
        if max_dd == 0:
            return float('inf')
        
        return annual_return / max_dd
    
    @staticmethod
    def max_drawdown(equity_curve: List[float]) -> tuple:
        """
        Calcula drawdown máximo e sua duração.
        
        Returns:
            (max_drawdown, duration_in_periods)
        """
        if not equity_curve:
            return 0.0, 0
        
        equity_series = pd.Series(equity_curve)
        rolling_max = equity_series.expanding().max()
        drawdowns = (equity_series - rolling_max) / rolling_max
        
        max_dd = abs(drawdowns.min())
        
        # Duração do drawdown
        in_drawdown = drawdowns < 0
        drawdown_periods = []
        current_duration = 0
        
        for is_dd in in_drawdown:
            if is_dd:
                current_duration += 1
            else:
                if current_duration > 0:
                    drawdown_periods.append(current_duration)
                current_duration = 0
        
        if current_duration > 0:
            drawdown_periods.append(current_duration)
        
        max_duration = max(drawdown_periods) if drawdown_periods else 0
        
        return max_dd, max_duration
    
    @staticmethod
    def ulcer_index(equity_curve: List[float]) -> float:
        """
        Calcula Ulcer Index (medida de drawdown).
        """
        if not equity_curve:
            return 0.0
        
        equity_series = pd.Series(equity_curve)
        rolling_max = equity_series.expanding().max()
        drawdowns = (equity_series - rolling_max) / rolling_max * 100
        
        # Ulcer Index = sqrt(mean(drawdown^2))
        ulcer = np.sqrt(np.mean(drawdowns ** 2))
        
        return ulcer
    
    @staticmethod
    def win_rate(trades: List[Dict]) -> float:
        """
        Calcula taxa de acerto (win rate).
        """
        if not trades:
            return 0.0
        
        winning_trades = sum(1 for t in trades if t['pnl'] > 0)
        return winning_trades / len(trades)
    
    @staticmethod
    def profit_factor(trades: List[Dict]) -> float:
        """
        Calcula Profit Factor (lucro total / perda total).
        """
        if not trades:
            return 0.0
        
        total_wins = sum(t['pnl'] for t in trades if t['pnl'] > 0)
        total_losses = abs(sum(t['pnl'] for t in trades if t['pnl'] < 0))
        
        if total_losses == 0:
            return float('inf') if total_wins > 0 else 0.0
        
        return total_wins / total_losses
    
    @staticmethod
    def avg_win_loss(trades: List[Dict]) -> tuple:
        """
        Calcula média de ganho e perda.
        
        Returns:
            (avg_win, avg_loss)
        """
        if not trades:
            return 0.0, 0.0
        
        wins = [t['pnl'] for t in trades if t['pnl'] > 0]
        losses = [t['pnl'] for t in trades if t['pnl'] < 0]
        
        avg_win = np.mean(wins) if wins else 0.0
        avg_loss = np.mean(losses) if losses else 0.0
        
        return avg_win, avg_loss
    
    @staticmethod
    def expectancy(trades: List[Dict]) -> float:
        """
        Calcula expectância matemática por trade.
        """
        if not trades:
            return 0.0
        
        total_pnl = sum(t['pnl'] for t in trades)
        return total_pnl / len(trades)
    
    @staticmethod
    def mae_mfe_analysis(trades: List[Dict]) -> tuple:
        """
        Análise de Maximum Adverse Excursion e Maximum Favorable Excursion.
        
        Returns:
            (avg_mae, avg_mfe)
        """
        if not trades:
            return 0.0, 0.0
        
        # MAE: quanto o trade chegou a perder antes de fechar
        # MFE: quanto o trade chegou a ganhar antes de fechar
        # (Simplificado - usa apenas PnL final)
        
        maes = []
        mfes = []
        
        for trade in trades:
            pnl = trade['pnl']
            ret = trade.get('return', 0)
            
            if pnl > 0:
                # Trade vencedor: MAE estimado em 0, MFE = pnl
                maes.append(0)
                mfes.append(abs(ret))
            else:
                # Trade perdedor: MAE = |pnl|, MFE estimado em 0
                maes.append(abs(ret))
                mfes.append(0)
        
        avg_mae = np.mean(maes) if maes else 0.0
        avg_mfe = np.mean(mfes) if mfes else 0.0
        
        return avg_mae, avg_mfe
    
    @staticmethod
    def _empty_metrics() -> Dict:
        """Retorna métricas vazias."""
        return {
            "total_return": 0.0,
            "sharpe_ratio": 0.0,
            "sortino_ratio": 0.0,
            "calmar_ratio": 0.0,
            "max_drawdown": 0.0,
            "max_drawdown_duration_days": 0,
            "ulcer_index": 0.0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "avg_win": 0.0,
            "avg_loss": 0.0,
            "expectancy": 0.0,
            "recovery_factor": 0.0,
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "mae": 0.0,
            "mfe": 0.0,
            "final_capital": 0.0
        }
