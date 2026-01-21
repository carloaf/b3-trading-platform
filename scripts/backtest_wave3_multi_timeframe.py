#!/usr/bin/env python3
"""
Backtest da Estratégia Wave3 Multi-Timeframe
============================================

Testa a estratégia Wave3 com dados reais do ProfitChart
- Análise de contexto: DAILY
- Gatilho de entrada: 60MIN
- Trailing stop adaptativo
- Alvo 3:1

Autor: B3 Trading Platform
Data: Janeiro 2026
"""

import sys
import asyncio
import asyncpg
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List

# Adiciona path para importar a estratégia
sys.path.append('/app/src/strategies')

try:
    from wave3_multi_timeframe import Wave3MultiTimeframe, Wave3Signal
except ImportError:
    print("⚠️  Usando implementação local")
    # Fallback: usar implementação inline se necessário


# Configuração do banco
DB_CONFIG = {
    'host': 'b3-timescaledb',
    'port': 5432,
    'database': 'b3trading_market',
    'user': 'b3trading_ts',
    'password': 'b3trading_ts_pass'
}


async def load_ohlcv_data(symbol: str, 
                         interval: str,
                         start_date: str,
                         end_date: str) -> pd.DataFrame:
    """
    Carrega dados OHLCV do TimescaleDB
    
    Args:
        symbol: Símbolo do ativo
        interval: Intervalo ('daily', '60min', '15min')
        start_date: Data inicial
        end_date: Data final
        
    Returns:
        DataFrame com dados OHLCV
    """
    conn = await asyncpg.connect(**DB_CONFIG)
    
    table_name = f'ohlcv_{interval}'
    
    query = f'''
        SELECT time, open, high, low, close, volume
        FROM {table_name}
        WHERE symbol = $1
          AND time >= $2::timestamp
          AND time <= $3::timestamp
        ORDER BY time ASC
    '''
    
    # Converte strings para datetime
    start_dt = datetime.strptime(start_date, '%Y-%m-%d') if isinstance(start_date, str) else start_date
    end_dt = datetime.strptime(end_date, '%Y-%m-%d') if isinstance(end_date, str) else end_date
    
    rows = await conn.fetch(query, symbol, start_dt, end_dt)
    await conn.close()
    
    if not rows:
        return pd.DataFrame()
    
    df = pd.DataFrame(rows, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
    df['time'] = pd.to_datetime(df['time'])
    df.set_index('time', inplace=True)
    
    return df


class Wave3Backtester:
    """
    Backtester para estratégia Wave3 Multi-Timeframe
    """
    
    def __init__(self, 
                 initial_capital: float = 100000.0,
                 position_size_pct: float = 0.95):
        """
        Inicializa backtester
        
        Args:
            initial_capital: Capital inicial
            position_size_pct: % do capital por trade
        """
        self.initial_capital = initial_capital
        self.position_size_pct = position_size_pct
        
        self.capital = initial_capital
        self.position = None
        self.trades = []
        self.equity_curve = []
        
    def open_position(self, signal: Wave3Signal):
        """Abre posição baseada no sinal"""
        
        # Calcula tamanho da posição
        risk_per_share = signal.risk
        max_shares = int((self.capital * self.position_size_pct) / signal.entry_price)
        
        # Calcula shares baseado no risco
        # Risco máximo: 2% do capital
        max_risk_capital = self.capital * 0.02
        shares_by_risk = int(max_risk_capital / risk_per_share) if risk_per_share > 0 else max_shares
        
        shares = min(max_shares, shares_by_risk)
        
        if shares <= 0:
            return
        
        cost = shares * signal.entry_price
        
        self.position = {
            'signal': signal,
            'shares': shares,
            'entry_price': signal.entry_price,
            'entry_time': signal.timestamp,
            'stop_loss': signal.stop_loss,
            'target': signal.target_price,
            'type': signal.signal_type,
            'cost': cost
        }
        
        self.capital -= cost
        
    def close_position(self, exit_price: float, exit_time: datetime, reason: str):
        """Fecha posição"""
        
        if self.position is None:
            return
        
        shares = self.position['shares']
        proceeds = shares * exit_price
        
        self.capital += proceeds
        
        # Calcula lucro
        if self.position['type'] == 'BUY':
            profit = (exit_price - self.position['entry_price']) * shares
            return_pct = (exit_price / self.position['entry_price'] - 1) * 100
        else:
            profit = (self.position['entry_price'] - exit_price) * shares
            return_pct = (self.position['entry_price'] / exit_price - 1) * 100
        
        # Registra trade
        trade = {
            'symbol': self.position['signal'].symbol,
            'type': self.position['type'],
            'entry_time': self.position['entry_time'],
            'entry_price': self.position['entry_price'],
            'exit_time': exit_time,
            'exit_price': exit_price,
            'shares': shares,
            'profit': profit,
            'return_pct': return_pct,
            'exit_reason': reason,
            'risk': self.position['signal'].risk,
            'reward': self.position['signal'].reward,
            'target_hit': reason == 'TARGET_HIT'
        }
        
        self.trades.append(trade)
        self.position = None
        
    def update_trailing_stop(self, strategy: Wave3MultiTimeframe, df_60min: pd.DataFrame):
        """Atualiza trailing stop"""
        
        if self.position is None:
            return
        
        new_stop = strategy.update_trailing_stop(
            df_60min,
            self.position['type'],
            self.position['stop_loss']
        )
        
        if new_stop != self.position['stop_loss']:
            self.position['stop_loss'] = new_stop
            
    def calculate_metrics(self) -> Dict:
        """Calcula métricas de performance"""
        
        if not self.trades:
            return {
                'error': 'No trades executed'
            }
        
        # Separa trades lucrativos e perdedores
        winning_trades = [t for t in self.trades if t['profit'] > 0]
        losing_trades = [t for t in self.trades if t['profit'] <= 0]
        
        num_trades = len(self.trades)
        num_winning = len(winning_trades)
        num_losing = len(losing_trades)
        
        win_rate = (num_winning / num_trades * 100) if num_trades > 0 else 0
        
        # Lucros e perdas médias
        avg_win = np.mean([t['profit'] for t in winning_trades]) if winning_trades else 0
        avg_loss = np.mean([abs(t['profit']) for t in losing_trades]) if losing_trades else 0
        
        # Retornos médios
        avg_win_pct = np.mean([t['return_pct'] for t in winning_trades]) if winning_trades else 0
        avg_loss_pct = np.mean([abs(t['return_pct']) for t in losing_trades]) if losing_trades else 0
        
        # Total P&L
        total_profit = sum([t['profit'] for t in self.trades])
        
        # Returns
        final_capital = self.capital
        total_return_pct = (final_capital / self.initial_capital - 1) * 100
        
        # Profit Factor
        total_wins = sum([t['profit'] for t in winning_trades])
        total_losses = abs(sum([t['profit'] for t in losing_trades]))
        profit_factor = (total_wins / total_losses) if total_losses > 0 else 0
        
        # Expectancy
        expectancy = (win_rate/100 * avg_win) - ((1-win_rate/100) * avg_loss)
        
        # Sharpe Ratio (simplificado)
        returns = [t['return_pct'] for t in self.trades]
        sharpe = (np.mean(returns) / np.std(returns) * np.sqrt(252)) if np.std(returns) > 0 else 0
        
        # Max Drawdown
        equity_values = [self.initial_capital]
        capital_temp = self.initial_capital
        
        for trade in self.trades:
            capital_temp += trade['profit']
            equity_values.append(capital_temp)
        
        equity_series = pd.Series(equity_values)
        running_max = equity_series.expanding().max()
        drawdown = (equity_series - running_max) / running_max
        max_drawdown = drawdown.min() * 100
        
        # Trades que atingiram o alvo
        target_hits = len([t for t in self.trades if t['target_hit']])
        target_hit_rate = (target_hits / num_trades * 100) if num_trades > 0 else 0
        
        return {
            'initial_capital': self.initial_capital,
            'final_capital': final_capital,
            'total_return_pct': total_return_pct,
            'total_profit': total_profit,
            'num_trades': num_trades,
            'winning_trades': num_winning,
            'losing_trades': num_losing,
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'avg_win_pct': avg_win_pct,
            'avg_loss_pct': avg_loss_pct,
            'profit_factor': profit_factor,
            'expectancy': expectancy,
            'sharpe_ratio': sharpe,
            'max_drawdown_pct': max_drawdown,
            'target_hits': target_hits,
            'target_hit_rate': target_hit_rate
        }


async def run_backtest(symbol: str, 
                      start_date: str,
                      end_date: str,
                      initial_capital: float = 100000.0):
    """
    Executa backtest para um símbolo
    
    Args:
        symbol: Símbolo do ativo
        start_date: Data inicial
        end_date: Data final
        initial_capital: Capital inicial
    """
    
    print(f"\n{'='*100}")
    print(f"BACKTEST WAVE3 MULTI-TIMEFRAME: {symbol}")
    print(f"{'='*100}")
    print(f"Período: {start_date} → {end_date}")
    print(f"Capital Inicial: R$ {initial_capital:,.2f}\n")
    
    # Carrega dados
    print("📊 Carregando dados...")
    df_daily = await load_ohlcv_data(symbol, 'daily', start_date, end_date)
    df_60min = await load_ohlcv_data(symbol, '60min', start_date, end_date)
    
    if df_daily.empty or df_60min.empty:
        print(f"❌ Dados insuficientes para {symbol}")
        return None
    
    print(f"   ✅ Daily: {len(df_daily)} candles")
    print(f"   ✅ 60min: {len(df_60min)} candles\n")
    
    # Inicializa estratégia e backtester
    strategy = Wave3MultiTimeframe(
        mma_long=72,
        mma_short=17,
        min_candles_pivot=17,
        risk_reward_ratio=3.0,
        mean_zone_tolerance=0.01
    )
    
    backtester = Wave3Backtester(initial_capital=initial_capital)
    
    # Simula trading
    print("🔄 Executando backtest...")
    
    # Itera pelos dados diários
    for i in range(72, len(df_daily)):  # Precisa de 72 períodos para MMA
        current_daily_date = df_daily.index[i]
        
        # Pega dados históricos até a data atual
        df_daily_hist = df_daily.iloc[:i+1]
        
        # Pega dados 60min até a mesma data
        df_60min_hist = df_60min[df_60min.index <= current_daily_date]
        
        if len(df_60min_hist) < 50:  # Mínimo de dados 60min
            continue
        
        # Verifica se há posição aberta
        if backtester.position is not None:
            # Atualiza trailing stop
            backtester.update_trailing_stop(strategy, df_60min_hist)
            
            # Verifica saída
            current_price = df_60min_hist.iloc[-1]['close']
            current_time = df_60min_hist.index[-1]
            
            pos = backtester.position
            
            # Check stop loss
            if pos['type'] == 'BUY' and current_price <= pos['stop_loss']:
                backtester.close_position(pos['stop_loss'], current_time, 'STOP_LOSS')
                
            elif pos['type'] == 'SELL' and current_price >= pos['stop_loss']:
                backtester.close_position(pos['stop_loss'], current_time, 'STOP_LOSS')
                
            # Check target
            elif pos['type'] == 'BUY' and current_price >= pos['target']:
                backtester.close_position(pos['target'], current_time, 'TARGET_HIT')
                
            elif pos['type'] == 'SELL' and current_price <= pos['target']:
                backtester.close_position(pos['target'], current_time, 'TARGET_HIT')
        
        else:
            # Busca novo sinal
            signal = strategy.generate_signal(df_daily_hist, df_60min_hist, symbol)
            
            if signal:
                backtester.open_position(signal)
                print(f"   🎯 {signal.timestamp.strftime('%Y-%m-%d')}: {signal.signal_type} @ R$ {signal.entry_price:.2f} "
                      f"(Stop: {signal.stop_loss:.2f} | Alvo: {signal.target_price:.2f})")
    
    # Fecha posição final se aberta
    if backtester.position:
        final_price = df_60min.iloc[-1]['close']
        final_time = df_60min.index[-1]
        backtester.close_position(final_price, final_time, 'END_OF_PERIOD')
    
    # Calcula métricas
    metrics = backtester.calculate_metrics()
    
    if 'error' in metrics:
        print(f"\n❌ {metrics['error']}")
        return None
    
    # Exibe resultados
    print(f"\n{'='*100}")
    print("RESULTADOS DO BACKTEST")
    print(f"{'='*100}\n")
    
    print(f"💰 PERFORMANCE FINANCEIRA")
    print(f"   Capital Inicial:        R$ {metrics['initial_capital']:>15,.2f}")
    print(f"   Capital Final:          R$ {metrics['final_capital']:>15,.2f}")
    print(f"   Lucro Total:            R$ {metrics['total_profit']:>15,.2f}")
    print(f"   Retorno Total:          {metrics['total_return_pct']:>15.2f}%")
    print(f"   Max Drawdown:           {metrics['max_drawdown_pct']:>15.2f}%\n")
    
    print(f"📊 ESTATÍSTICAS DE TRADES")
    print(f"   Total de Trades:        {metrics['num_trades']:>15}")
    print(f"   Trades Lucrativos:      {metrics['winning_trades']:>15} ({metrics['win_rate']:.1f}%)")
    print(f"   Trades Perdedores:      {metrics['losing_trades']:>15}")
    print(f"   Alvos Atingidos:        {metrics['target_hits']:>15} ({metrics['target_hit_rate']:.1f}%)\n")
    
    print(f"💡 MÉTRICAS DE QUALIDADE")
    print(f"   Lucro Médio:            R$ {metrics['avg_win']:>15,.2f} ({metrics['avg_win_pct']:+.2f}%)")
    print(f"   Perda Média:            R$ {metrics['avg_loss']:>15,.2f} ({metrics['avg_loss_pct']:.2f}%)")
    print(f"   Profit Factor:          {metrics['profit_factor']:>15.2f}")
    print(f"   Expectancy:             R$ {metrics['expectancy']:>15,.2f}")
    print(f"   Sharpe Ratio:           {metrics['sharpe_ratio']:>15.2f}\n")
    
    # Últimos trades
    if backtester.trades:
        print(f"📝 ÚLTIMOS 10 TRADES")
        print(f"{'-'*100}")
        
        for trade in backtester.trades[-10:]:
            profit_emoji = "✅" if trade['profit'] > 0 else "❌"
            target_emoji = "🎯" if trade['target_hit'] else "🛑"
            
            print(f"   {profit_emoji} {target_emoji} {trade['entry_time'].strftime('%Y-%m-%d')} → "
                  f"{trade['exit_time'].strftime('%Y-%m-%d')}: "
                  f"{trade['type']:4s} | "
                  f"R$ {trade['entry_price']:6.2f} → R$ {trade['exit_price']:6.2f} | "
                  f"P&L: R$ {trade['profit']:>10,.2f} ({trade['return_pct']:+6.2f}%) | "
                  f"{trade['exit_reason']}")
    
    return metrics


async def compare_symbols(symbols: List[str],
                         start_date: str,
                         end_date: str):
    """
    Compara performance entre múltiplos símbolos
    """
    
    results = {}
    
    for symbol in symbols:
        metrics = await run_backtest(symbol, start_date, end_date)
        if metrics:
            results[symbol] = metrics
    
    # Resumo comparativo
    if results:
        print(f"\n\n{'='*100}")
        print("COMPARAÇÃO ENTRE SÍMBOLOS")
        print(f"{'='*100}\n")
        
        print(f"{'Símbolo':<10} {'Retorno':>12} {'Trades':>10} {'Win Rate':>12} {'Profit Factor':>15} {'Sharpe':>10} {'Max DD':>12}")
        print(f"{'-'*100}")
        
        for symbol, metrics in results.items():
            print(f"{symbol:<10} {metrics['total_return_pct']:>11.2f}% {metrics['num_trades']:>10} "
                  f"{metrics['win_rate']:>11.1f}% {metrics['profit_factor']:>15.2f} "
                  f"{metrics['sharpe_ratio']:>10.2f} {metrics['max_drawdown_pct']:>11.2f}%")


async def main():
    """Main"""
    
    symbols = ['PETR4', 'VALE3', 'ITUB4']
    start_date = '2024-01-01'
    end_date = '2025-12-30'
    
    await compare_symbols(symbols, start_date, end_date)


if __name__ == '__main__':
    asyncio.run(main())
