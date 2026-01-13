"""
B3 Trading Platform - Backtest Engine
=====================================
Motor de backtesting para estratégias.
"""

from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
import pandas as pd
import numpy as np
from loguru import logger

from .strategies import StrategyManager, BaseStrategy


@dataclass
class Trade:
    """Representa um trade."""
    id: str
    symbol: str
    side: str  # BUY, SELL
    entry_time: datetime
    entry_price: float
    quantity: int
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None  # stop_loss, take_profit, signal, end_of_data
    
    pnl: float = 0.0
    return_pct: float = 0.0
    
    def close(self, exit_time: datetime, exit_price: float, reason: str):
        """Fecha o trade."""
        self.exit_time = exit_time
        self.exit_price = exit_price
        self.exit_reason = reason
        
        if self.side == "BUY":
            self.pnl = (exit_price - self.entry_price) * self.quantity
            self.return_pct = (exit_price - self.entry_price) / self.entry_price * 100
        else:  # SELL
            self.pnl = (self.entry_price - exit_price) * self.quantity
            self.return_pct = (self.entry_price - exit_price) / self.entry_price * 100
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "symbol": self.symbol,
            "side": self.side,
            "entry_time": self.entry_time.isoformat() if self.entry_time else None,
            "entry_price": self.entry_price,
            "quantity": self.quantity,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "exit_time": self.exit_time.isoformat() if self.exit_time else None,
            "exit_price": self.exit_price,
            "exit_reason": self.exit_reason,
            "pnl": round(self.pnl, 2),
            "return_pct": round(self.return_pct, 4)
        }


class BacktestEngine:
    """Motor de backtesting."""
    
    def __init__(
        self,
        strategy_name: str,
        initial_capital: float = 100000.0,
        params: Optional[Dict] = None,
        position_size: float = 0.1,  # 10% do capital por trade
        commission: float = 0.0,  # Comissão por trade (R$)
        slippage: float = 0.0001  # 0.01% slippage
    ):
        self.strategy_name = strategy_name
        self.initial_capital = initial_capital
        self.params = params
        self.position_size = position_size
        self.commission = commission
        self.slippage = slippage
        
        self.strategy_manager = StrategyManager()
        self.strategy = self.strategy_manager.get_strategy(strategy_name, params)
        
        # Estado
        self.capital = initial_capital
        self.trades: List[Trade] = []
        self.open_trade: Optional[Trade] = None
        self.equity_curve: List[Dict] = []
        self.trade_count = 0
    
    async def run(self, data: List[Dict]) -> Dict:
        """Executa o backtest."""
        logger.info(f"🔄 Iniciando backtest: {self.strategy_name}")
        
        # Converter para DataFrame
        df = pd.DataFrame(data)
        
        # Garantir tipos corretos
        for col in ["open", "high", "low", "close"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0).astype(int)
        
        # Calcular indicadores e sinais
        df = self.strategy.calculate_indicators(df)
        df = self.strategy.generate_signals(df)
        
        # Resetar estado
        self.capital = self.initial_capital
        self.trades = []
        self.open_trade = None
        self.equity_curve = []
        self.trade_count = 0
        
        # Simular trades
        for i in range(len(df)):
            row = df.iloc[i]
            current_time = row["time"] if "time" in row else datetime.now()
            current_price = row["close"]
            
            # Verificar posição aberta
            if self.open_trade:
                # Verificar Stop Loss
                if self.open_trade.stop_loss:
                    if self.open_trade.side == "BUY" and row["low"] <= self.open_trade.stop_loss:
                        self._close_trade(current_time, self.open_trade.stop_loss, "stop_loss")
                    elif self.open_trade.side == "SELL" and row["high"] >= self.open_trade.stop_loss:
                        self._close_trade(current_time, self.open_trade.stop_loss, "stop_loss")
                
                # Verificar Take Profit
                if self.open_trade and self.open_trade.take_profit:
                    if self.open_trade.side == "BUY" and row["high"] >= self.open_trade.take_profit:
                        self._close_trade(current_time, self.open_trade.take_profit, "take_profit")
                    elif self.open_trade.side == "SELL" and row["low"] <= self.open_trade.take_profit:
                        self._close_trade(current_time, self.open_trade.take_profit, "take_profit")
                
                # Verificar sinal de saída
                if self.open_trade:
                    if (self.open_trade.side == "BUY" and row["signal"] == "SELL") or \
                       (self.open_trade.side == "SELL" and row["signal"] == "BUY"):
                        self._close_trade(current_time, current_price, "signal")
            
            # Verificar entrada
            if not self.open_trade:
                if row["signal"] in ["BUY", "SELL"]:
                    self._open_trade(
                        current_time,
                        current_price,
                        row["signal"],
                        row.get("stop_loss"),
                        row.get("take_profit")
                    )
            
            # Calcular equity
            equity = self.capital
            if self.open_trade:
                if self.open_trade.side == "BUY":
                    equity += (current_price - self.open_trade.entry_price) * self.open_trade.quantity
                else:
                    equity += (self.open_trade.entry_price - current_price) * self.open_trade.quantity
            
            self.equity_curve.append({
                "time": current_time.isoformat() if hasattr(current_time, 'isoformat') else str(current_time),
                "equity": round(equity, 2),
                "drawdown": round((self.initial_capital - equity) / self.initial_capital * 100, 4) if equity < self.initial_capital else 0
            })
        
        # Fechar posição aberta no final
        if self.open_trade:
            final_price = df.iloc[-1]["close"]
            final_time = df.iloc[-1]["time"] if "time" in df.iloc[-1] else datetime.now()
            self._close_trade(final_time, final_price, "end_of_data")
        
        # Calcular métricas
        return self._calculate_metrics()
    
    def _open_trade(
        self,
        time: datetime,
        price: float,
        side: str,
        stop_loss: Optional[float],
        take_profit: Optional[float]
    ):
        """Abre um trade."""
        self.trade_count += 1
        
        # Calcular quantidade com base no position_size
        trade_value = self.capital * self.position_size
        
        # Aplicar slippage
        if side == "BUY":
            entry_price = price * (1 + self.slippage)
        else:
            entry_price = price * (1 - self.slippage)
        
        # Para Mini Índice, 1 contrato = 1 ponto = R$ 0.20
        # Simplificação: quantidade em "valor" do ativo
        quantity = int(trade_value / entry_price) if entry_price > 0 else 0
        
        if quantity <= 0:
            return
        
        self.open_trade = Trade(
            id=f"T{self.trade_count:04d}",
            symbol="BACKTEST",
            side=side,
            entry_time=time,
            entry_price=entry_price,
            quantity=quantity,
            stop_loss=stop_loss if pd.notna(stop_loss) else None,
            take_profit=take_profit if pd.notna(take_profit) else None
        )
        
        # Deduzir comissão
        self.capital -= self.commission
    
    def _close_trade(self, time: datetime, price: float, reason: str):
        """Fecha o trade aberto."""
        if not self.open_trade:
            return
        
        # Aplicar slippage na saída
        if self.open_trade.side == "BUY":
            exit_price = price * (1 - self.slippage)
        else:
            exit_price = price * (1 + self.slippage)
        
        self.open_trade.close(time, exit_price, reason)
        
        # Atualizar capital
        self.capital += self.open_trade.pnl - self.commission
        
        # Guardar trade
        self.trades.append(self.open_trade)
        self.open_trade = None
    
    def _calculate_metrics(self) -> Dict:
        """Calcula métricas do backtest."""
        if not self.trades:
            return {
                "initial_capital": self.initial_capital,
                "final_capital": self.capital,
                "total_return": 0,
                "total_return_pct": 0,
                "sharpe_ratio": None,
                "sortino_ratio": None,
                "max_drawdown": 0,
                "max_drawdown_pct": 0,
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate": 0,
                "profit_factor": None,
                "avg_win": 0,
                "avg_loss": 0,
                "trades": [],
                "equity_curve": self.equity_curve
            }
        
        # Trades
        pnls = [t.pnl for t in self.trades]
        returns = [t.return_pct for t in self.trades]
        
        winning = [t for t in self.trades if t.pnl > 0]
        losing = [t for t in self.trades if t.pnl < 0]
        
        # Métricas básicas
        total_return = self.capital - self.initial_capital
        total_return_pct = (self.capital - self.initial_capital) / self.initial_capital * 100
        
        win_rate = len(winning) / len(self.trades) * 100 if self.trades else 0
        
        avg_win = np.mean([t.pnl for t in winning]) if winning else 0
        avg_loss = abs(np.mean([t.pnl for t in losing])) if losing else 0
        
        # Profit Factor
        gross_profit = sum(t.pnl for t in winning)
        gross_loss = abs(sum(t.pnl for t in losing))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else (999.99 if gross_profit > 0 else None)
        
        # Sharpe Ratio (anualizado, assumindo ~252 trades por ano)
        if returns and np.std(returns) > 0:
            sharpe_ratio = np.mean(returns) / np.std(returns) * np.sqrt(252)
        else:
            sharpe_ratio = None
        
        # Sortino Ratio
        downside_returns = [r for r in returns if r < 0]
        if downside_returns and np.std(downside_returns) > 0:
            sortino_ratio = np.mean(returns) / np.std(downside_returns) * np.sqrt(252)
        else:
            sortino_ratio = None
        
        # Max Drawdown
        equity_values = [e["equity"] for e in self.equity_curve]
        peak = equity_values[0]
        max_dd = 0
        for equity in equity_values:
            if equity > peak:
                peak = equity
            dd = (peak - equity) / peak * 100
            if dd > max_dd:
                max_dd = dd
        
        max_dd_value = max_dd * self.initial_capital / 100
        
        return {
            "initial_capital": self.initial_capital,
            "final_capital": round(self.capital, 2),
            "total_return": round(total_return, 2),
            "total_return_pct": round(total_return_pct, 4),
            "sharpe_ratio": round(sharpe_ratio, 3) if sharpe_ratio else None,
            "sortino_ratio": round(sortino_ratio, 3) if sortino_ratio else None,
            "max_drawdown": round(max_dd_value, 2),
            "max_drawdown_pct": round(max_dd, 4),
            "total_trades": len(self.trades),
            "winning_trades": len(winning),
            "losing_trades": len(losing),
            "win_rate": round(win_rate, 2),
            "profit_factor": round(profit_factor, 3) if profit_factor else None,
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "trades": [t.to_dict() for t in self.trades],
            "equity_curve": self.equity_curve
        }
