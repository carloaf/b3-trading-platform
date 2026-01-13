"""
B3 Trading Platform - Paper Trading Manager
============================================
Gerenciador de paper trading em tempo real.
"""

import uuid
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from loguru import logger


@dataclass
class PaperPosition:
    """Posição em paper trading."""
    id: str
    symbol: str
    side: str  # BUY, SELL
    quantity: int
    entry_price: float
    entry_time: datetime
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    
    def update_price(self, price: float):
        """Atualiza preço atual e P&L."""
        self.current_price = price
        if self.side == "BUY":
            self.unrealized_pnl = (price - self.entry_price) * self.quantity
        else:
            self.unrealized_pnl = (self.entry_price - price) * self.quantity
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "entry_price": self.entry_price,
            "entry_time": self.entry_time.isoformat(),
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "current_price": self.current_price,
            "unrealized_pnl": round(self.unrealized_pnl, 2)
        }


@dataclass
class PaperTrade:
    """Trade executado em paper trading."""
    id: str
    symbol: str
    side: str
    quantity: int
    entry_price: float
    entry_time: datetime
    exit_price: float
    exit_time: datetime
    exit_reason: str
    pnl: float
    return_pct: float
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "entry_price": self.entry_price,
            "entry_time": self.entry_time.isoformat(),
            "exit_price": self.exit_price,
            "exit_time": self.exit_time.isoformat(),
            "exit_reason": self.exit_reason,
            "pnl": round(self.pnl, 2),
            "return_pct": round(self.return_pct, 4)
        }


class PaperTradingManager:
    """Gerenciador de paper trading."""
    
    def __init__(self, initial_capital: float = 100000.0):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.positions: Dict[str, PaperPosition] = {}
        self.trade_history: List[PaperTrade] = []
        self.order_count = 0
        self.is_running = False
        self.start_time: Optional[datetime] = None
    
    def reset(self, initial_capital: float = None):
        """Reseta o paper trading."""
        if initial_capital:
            self.initial_capital = initial_capital
        self.capital = self.initial_capital
        self.positions = {}
        self.trade_history = []
        self.order_count = 0
        self.is_running = False
        self.start_time = None
        logger.info(f"📝 Paper trading resetado. Capital: R$ {self.capital:,.2f}")
    
    def start(self):
        """Inicia o paper trading."""
        self.is_running = True
        self.start_time = datetime.now()
        logger.info("▶️ Paper trading iniciado")
    
    def stop(self):
        """Para o paper trading."""
        self.is_running = False
        logger.info("⏹️ Paper trading parado")
    
    def get_status(self) -> Dict:
        """Retorna status atual."""
        # Calcular P&L total
        unrealized_pnl = sum(p.unrealized_pnl for p in self.positions.values())
        realized_pnl = sum(t.pnl for t in self.trade_history)
        total_pnl = realized_pnl + unrealized_pnl
        
        # Métricas de trades
        winning_trades = [t for t in self.trade_history if t.pnl > 0]
        losing_trades = [t for t in self.trade_history if t.pnl < 0]
        win_rate = len(winning_trades) / len(self.trade_history) * 100 if self.trade_history else 0
        
        return {
            "is_running": self.is_running,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "initial_capital": self.initial_capital,
            "current_capital": round(self.capital, 2),
            "unrealized_pnl": round(unrealized_pnl, 2),
            "realized_pnl": round(realized_pnl, 2),
            "total_pnl": round(total_pnl, 2),
            "return_pct": round(total_pnl / self.initial_capital * 100, 4),
            "open_positions": len(self.positions),
            "total_trades": len(self.trade_history),
            "winning_trades": len(winning_trades),
            "losing_trades": len(losing_trades),
            "win_rate": round(win_rate, 2)
        }
    
    def get_positions(self) -> Dict:
        """Retorna posições abertas."""
        return {
            "positions": [p.to_dict() for p in self.positions.values()],
            "count": len(self.positions)
        }
    
    def get_trade_history(self) -> Dict:
        """Retorna histórico de trades."""
        return {
            "trades": [t.to_dict() for t in self.trade_history],
            "count": len(self.trade_history)
        }
    
    async def execute_order(
        self,
        symbol: str,
        side: str,
        quantity: int,
        order_type: str = "MARKET",
        price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None
    ) -> Dict:
        """Executa uma ordem em paper trading."""
        
        self.order_count += 1
        order_id = f"PO{self.order_count:06d}"
        
        # Para MARKET orders, usar preço atual (simulado)
        # Em produção, isso viria de um feed de dados real
        if order_type == "MARKET":
            # Simular preço (em produção, buscar do feed)
            execution_price = price or 128000  # Placeholder
        else:
            execution_price = price
        
        if not execution_price:
            return {
                "success": False,
                "error": "Preço não fornecido para ordem LIMIT/STOP"
            }
        
        # Verificar se já existe posição no mesmo símbolo
        existing_position = None
        for pos in self.positions.values():
            if pos.symbol == symbol:
                existing_position = pos
                break
        
        # Se existe posição oposta, fechar primeiro
        if existing_position and existing_position.side != side:
            await self.close_position(existing_position.id, execution_price, "reversed")
            existing_position = None
        
        # Se existe posição do mesmo lado, aumentar
        if existing_position and existing_position.side == side:
            # Calcular novo preço médio
            total_quantity = existing_position.quantity + quantity
            new_avg_price = (
                (existing_position.entry_price * existing_position.quantity) +
                (execution_price * quantity)
            ) / total_quantity
            
            existing_position.quantity = total_quantity
            existing_position.entry_price = new_avg_price
            existing_position.update_price(execution_price)
            
            if stop_loss:
                existing_position.stop_loss = stop_loss
            if take_profit:
                existing_position.take_profit = take_profit
            
            logger.info(f"📈 Posição aumentada: {symbol} {side} +{quantity} @ {execution_price:.2f}")
            
            return {
                "success": True,
                "order_id": order_id,
                "action": "position_increased",
                "position": existing_position.to_dict()
            }
        
        # Criar nova posição
        position_id = str(uuid.uuid4())[:8]
        position = PaperPosition(
            id=position_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            entry_price=execution_price,
            entry_time=datetime.now(),
            stop_loss=stop_loss,
            take_profit=take_profit,
            current_price=execution_price
        )
        
        self.positions[position_id] = position
        
        logger.info(f"📝 Nova posição: {symbol} {side} {quantity} @ {execution_price:.2f}")
        
        return {
            "success": True,
            "order_id": order_id,
            "action": "position_opened",
            "position": position.to_dict()
        }
    
    async def close_position(
        self,
        position_id: str,
        exit_price: Optional[float] = None,
        reason: str = "manual"
    ) -> Dict:
        """Fecha uma posição."""
        
        if position_id not in self.positions:
            return {
                "success": False,
                "error": f"Posição não encontrada: {position_id}"
            }
        
        position = self.positions[position_id]
        
        # Usar preço atual se não fornecido
        if not exit_price:
            exit_price = position.current_price or position.entry_price
        
        # Calcular P&L
        if position.side == "BUY":
            pnl = (exit_price - position.entry_price) * position.quantity
            return_pct = (exit_price - position.entry_price) / position.entry_price * 100
        else:
            pnl = (position.entry_price - exit_price) * position.quantity
            return_pct = (position.entry_price - exit_price) / position.entry_price * 100
        
        # Criar registro de trade
        trade = PaperTrade(
            id=position.id,
            symbol=position.symbol,
            side=position.side,
            quantity=position.quantity,
            entry_price=position.entry_price,
            entry_time=position.entry_time,
            exit_price=exit_price,
            exit_time=datetime.now(),
            exit_reason=reason,
            pnl=pnl,
            return_pct=return_pct
        )
        
        self.trade_history.append(trade)
        
        # Atualizar capital
        self.capital += pnl
        
        # Remover posição
        del self.positions[position_id]
        
        logger.info(f"✅ Posição fechada: {position.symbol} {position.side} "
                   f"@ {exit_price:.2f} | P&L: R$ {pnl:,.2f} ({return_pct:+.2f}%)")
        
        return {
            "success": True,
            "trade": trade.to_dict(),
            "capital": round(self.capital, 2)
        }
    
    async def update_prices(self, prices: Dict[str, float]):
        """Atualiza preços das posições."""
        for position in self.positions.values():
            if position.symbol in prices:
                position.update_price(prices[position.symbol])
                
                # Verificar stop loss
                if position.stop_loss:
                    if (position.side == "BUY" and prices[position.symbol] <= position.stop_loss) or \
                       (position.side == "SELL" and prices[position.symbol] >= position.stop_loss):
                        await self.close_position(position.id, position.stop_loss, "stop_loss")
                        continue
                
                # Verificar take profit
                if position.take_profit:
                    if (position.side == "BUY" and prices[position.symbol] >= position.take_profit) or \
                       (position.side == "SELL" and prices[position.symbol] <= position.take_profit):
                        await self.close_position(position.id, position.take_profit, "take_profit")
