#!/usr/bin/env python3
"""
Backtest Wave3 Strategy - Versões Otimizadas
=============================================

Testa 2 versões da estratégia Wave3:

1. CRYPTO VERSION: Ajustada para mercado 24/7, alta volatilidade
   - Regra: 10 candles (vs 17 original)
   - Stops: 8% (vs 6% original)
   - EMAs: 50/12 (vs 72/17 original)
   - Target: 2.5:1 (vs 3:1 original)
   - Símbolos: BTC, ETH, BNB, SOL, XRP

2. B3 STOCKS VERSION: Original para validação
   - Regra: 17 candles (original)
   - Stops: 6% (original)
   - EMAs: 72/17 (original)
   - Target: 3:1 (original)
   - Símbolos: ITUB4, VALE3, PETR4, MGLU3, BBDC4
"""

import asyncio
import asyncpg
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
import json


@dataclass
class BacktestResult:
    """Resultado do backtest"""
    symbol: str
    strategy: str
    version: str  # 'crypto_optimized' ou 'b3_original'
    timeframe_context: str
    timeframe_trigger: str
    
    # Métricas gerais
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    
    # Retornos
    total_return_pct: float
    avg_return_pct: float
    
    # Risk metrics
    sharpe_ratio: float
    max_drawdown_pct: float
    
    # Trade metrics
    best_trade_pct: float
    worst_trade_pct: float
    
    # Config usada
    ema_long: int
    ema_short: int
    min_candles: int
    risk_pct: float
    reward_ratio: float


class Wave3OptimizedBacktest:
    """
    Backtest Wave3 com versões otimizadas por tipo de ativo
    """
    
    def __init__(
        self,
        db_config: dict,
        version: str = 'crypto',  # 'crypto' ou 'b3'
    ):
        self.db_config = db_config
        self.version = version
        
        # Configurações por versão
        if version == 'crypto':
            self.ema_long = 50      # Mais rápida
            self.ema_short = 12     # Mais rápida
            self.min_candles = 10   # Mercado mais rápido
            self.risk_pct = 0.08    # Stop mais largo
            self.reward_ratio = 2.5 # Target mais realista
            self.zone_tolerance = 0.015  # 1.5% (mais largo)
        else:  # b3
            self.ema_long = 72      # Original
            self.ema_short = 17     # Original
            self.min_candles = 17   # Original
            self.risk_pct = 0.06    # Original
            self.reward_ratio = 3.0 # Original
            self.zone_tolerance = 0.01  # 1% (original)
    
    async def fetch_crypto_data(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime
    ) -> pd.DataFrame:
        """Busca dados crypto (horários)"""
        conn = await asyncpg.connect(**self.db_config)
        
        query = """
            SELECT 
                time as timestamp,
                open::float,
                high::float,
                low::float,
                close::float,
                volume::float
            FROM crypto_ohlcv_1h
            WHERE symbol = $1
                AND time >= $2
                AND time <= $3
            ORDER BY time ASC
        """
        
        rows = await conn.fetch(query, symbol, start_date, end_date)
        await conn.close()
        
        if not rows:
            return pd.DataFrame()
        
        df = pd.DataFrame([dict(row) for row in rows])
        df.set_index('timestamp', inplace=True)
        return df
    
    async def fetch_b3_data(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime
    ) -> pd.DataFrame:
        """Busca dados B3 (diários)"""
        conn = await asyncpg.connect(**self.db_config)
        
        query = """
            SELECT 
                time as timestamp,
                open::float,
                high::float,
                low::float,
                close::float,
                volume::float
            FROM ohlcv_daily
            WHERE symbol = $1
                AND time >= $2
                AND time <= $3
            ORDER BY time ASC
        """
        
        rows = await conn.fetch(query, symbol, start_date, end_date)
        await conn.close()
        
        if not rows:
            return pd.DataFrame()
        
        df = pd.DataFrame([dict(row) for row in rows])
        df.set_index('timestamp', inplace=True)
        return df
    
    def aggregate_to_daily(self, df_hourly: pd.DataFrame) -> pd.DataFrame:
        """Agrega dados horários para diário (crypto)"""
        if df_hourly.empty:
            return pd.DataFrame()
        
        df_daily = df_hourly.resample('D').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }).dropna()
        
        return df_daily
    
    def calculate_indicators(
        self,
        df_daily: pd.DataFrame,
        df_trigger: pd.DataFrame
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """
        Calcula indicadores Wave3
        """
        # Contexto Diário
        df_daily = df_daily.copy()
        df_daily['ema_long'] = df_daily['close'].ewm(span=self.ema_long, adjust=False).mean()
        df_daily['ema_short'] = df_daily['close'].ewm(span=self.ema_short, adjust=False).mean()
        
        # Zona de entrada
        df_daily['zone_upper'] = df_daily[['ema_long', 'ema_short']].max(axis=1) * (1 + self.zone_tolerance)
        df_daily['zone_lower'] = df_daily[['ema_long', 'ema_short']].min(axis=1) * (1 - self.zone_tolerance)
        df_daily['in_zone'] = (
            (df_daily['close'] >= df_daily['zone_lower']) &
            (df_daily['close'] <= df_daily['zone_upper'])
        )
        
        # Tendência
        df_daily['trend'] = np.where(df_daily['close'] > df_daily['ema_long'], 1, -1)
        
        # Gatilho: identificar pivôs
        df_trigger = df_trigger.copy()
        df_trigger['pivot_low'] = (
            (df_trigger['low'] < df_trigger['low'].shift(1)) &
            (df_trigger['low'] < df_trigger['low'].shift(-1))
        )
        df_trigger['pivot_high'] = (
            (df_trigger['high'] > df_trigger['high'].shift(1)) &
            (df_trigger['high'] > df_trigger['high'].shift(-1))
        )
        
        return df_daily, df_trigger
    
    def generate_signals(
        self,
        df_daily: pd.DataFrame,
        df_trigger: pd.DataFrame
    ) -> List[Dict]:
        """Gera sinais Wave3"""
        signals = []
        
        last_pivot_low_idx = None
        last_pivot_high_idx = None
        in_position = False
        entry_price = None
        stop_loss = None
        target = None
        
        # Merge contexto diário
        df_trigger['date'] = df_trigger.index.date
        df_daily['date'] = df_daily.index.date
        df_trigger = df_trigger.merge(
            df_daily[['date', 'trend', 'in_zone', 'ema_long']],
            on='date',
            how='left'
        )
        
        for i in range(self.min_candles, len(df_trigger)):
            row = df_trigger.iloc[i]
            timestamp = df_trigger.index[i]
            
            # Gerenciar posição aberta
            if in_position:
                # Stop loss
                if row['low'] <= stop_loss:
                    pnl_pct = (stop_loss - entry_price) / entry_price * 100
                    signals.append({
                        'timestamp': timestamp,
                        'action': 'SELL',
                        'price': stop_loss,
                        'reason': 'stop_loss',
                        'pnl_pct': pnl_pct
                    })
                    in_position = False
                    continue
                
                # Target
                if row['high'] >= target:
                    pnl_pct = (target - entry_price) / entry_price * 100
                    signals.append({
                        'timestamp': timestamp,
                        'action': 'SELL',
                        'price': target,
                        'reason': 'target',
                        'pnl_pct': pnl_pct
                    })
                    in_position = False
                    continue
                
                # Trailing stop
                if row['pivot_low']:
                    candles_since_last = i - last_pivot_low_idx if last_pivot_low_idx else 100
                    if candles_since_last >= self.min_candles:
                        new_stop = row['low'] * (1 - self.risk_pct * 0.3)  # 30% do risco
                        if new_stop > stop_loss:
                            stop_loss = new_stop
            
            # Verificar entrada
            if not in_position:
                # 1. Tendência de alta
                if row['trend'] != 1:
                    continue
                
                # 2. Preço na zona
                if not row['in_zone']:
                    continue
                
                # 3. Atualizar pivôs
                if row['pivot_low']:
                    if last_pivot_low_idx is None or (i - last_pivot_low_idx) >= self.min_candles:
                        last_pivot_low_idx = i
                
                if row['pivot_high']:
                    if last_pivot_high_idx is None or (i - last_pivot_high_idx) >= self.min_candles:
                        last_pivot_high_idx = i
                
                # 4. Onda 3: rompimento do topo
                if last_pivot_low_idx and last_pivot_high_idx:
                    if last_pivot_low_idx < last_pivot_high_idx < i:
                        pivot_low_price = df_trigger.iloc[last_pivot_low_idx]['low']
                        pivot_high_price = df_trigger.iloc[last_pivot_high_idx]['high']
                        
                        # Romper topo com fundo mais alto
                        if row['high'] > pivot_high_price:
                            # Verificar se fundo é mais alto
                            prev_low_idx = max(0, last_pivot_low_idx - self.min_candles)
                            if prev_low_idx < last_pivot_low_idx:
                                prev_low = df_trigger.iloc[prev_low_idx]['low']
                                
                                if pivot_low_price > prev_low:
                                    # COMPRA!
                                    entry_price = row['close']
                                    stop_loss = pivot_low_price * (1 - self.risk_pct * 0.3)
                                    risk = entry_price - stop_loss
                                    target = entry_price + (risk * self.reward_ratio)
                                    
                                    signals.append({
                                        'timestamp': timestamp,
                                        'action': 'BUY',
                                        'price': entry_price,
                                        'stop': stop_loss,
                                        'target': target,
                                        'risk_pct': (risk / entry_price) * 100,
                                        'reward_pct': ((target - entry_price) / entry_price) * 100
                                    })
                                    
                                    in_position = True
        
        return signals
    
    def calculate_metrics(self, signals: List[Dict]) -> Dict:
        """Calcula métricas de performance"""
        
        if not signals:
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0,
                'total_return_pct': 0,
                'avg_return_pct': 0,
                'sharpe_ratio': 0,
                'max_drawdown_pct': 0,
                'best_trade_pct': 0,
                'worst_trade_pct': 0
            }
        
        # Separar compras e vendas
        buys = [s for s in signals if s['action'] == 'BUY']
        sells = [s for s in signals if s['action'] == 'SELL']
        
        total_trades = min(len(buys), len(sells))
        
        if total_trades == 0:
            return {'total_trades': 0}
        
        # Calcular PnL
        trades_pnl = []
        winning = 0
        losing = 0
        
        for i in range(total_trades):
            pnl_pct = sells[i].get('pnl_pct', 0)
            trades_pnl.append(pnl_pct)
            
            if pnl_pct > 0:
                winning += 1
            else:
                losing += 1
        
        # Métricas
        win_rate = winning / total_trades if total_trades > 0 else 0
        avg_return = np.mean(trades_pnl)
        total_return = np.sum(trades_pnl)
        
        # Sharpe
        if len(trades_pnl) > 1 and np.std(trades_pnl) > 0:
            sharpe = np.mean(trades_pnl) / np.std(trades_pnl)
        else:
            sharpe = 0
        
        # Max Drawdown
        cumulative = np.cumsum(trades_pnl)
        running_max = np.maximum.accumulate(cumulative)
        drawdown = running_max - cumulative
        max_dd = np.max(drawdown) if len(drawdown) > 0 else 0
        
        return {
            'total_trades': total_trades,
            'winning_trades': winning,
            'losing_trades': losing,
            'win_rate': win_rate * 100,
            'total_return_pct': total_return,
            'avg_return_pct': avg_return,
            'sharpe_ratio': sharpe,
            'max_drawdown_pct': max_dd,
            'best_trade_pct': max(trades_pnl) if trades_pnl else 0,
            'worst_trade_pct': min(trades_pnl) if trades_pnl else 0
        }
    
    async def run_backtest(
        self,
        symbols: List[str],
        start_date: datetime,
        end_date: datetime
    ) -> List[BacktestResult]:
        """Executa backtest"""
        results = []
        
        version_name = "CRYPTO OPTIMIZED" if self.version == 'crypto' else "B3 ORIGINAL"
        
        print("\n" + "="*70)
        print(f"🔄 WAVE3 BACKTEST - {version_name}")
        print("="*70)
        print(f"📊 Símbolos: {', '.join(symbols)}")
        print(f"📅 Período: {start_date.date()} → {end_date.date()}")
        print(f"📈 Config: EMA {self.ema_long}/{self.ema_short} | "
              f"Regra {self.min_candles} candles | Risk {self.risk_pct*100:.0f}% | "
              f"R:R {self.reward_ratio}:1")
        print("="*70 + "\n")
        
        for symbol in symbols:
            print(f"{'─'*70}")
            print(f"📊 {symbol}")
            print(f"{'─'*70}")
            
            # Buscar dados
            if self.version == 'crypto':
                df_hourly = await self.fetch_crypto_data(symbol, start_date, end_date)
                if df_hourly.empty:
                    print(f"   ⚠️  Sem dados para {symbol}")
                    continue
                
                print(f"   📥 {len(df_hourly)} candles horários")
                df_daily = self.aggregate_to_daily(df_hourly)
                print(f"   📊 {len(df_daily)} dias agregados")
                df_trigger = df_hourly
                tf_context = '1d'
                tf_trigger = '1h'
            else:  # b3
                df_daily = await self.fetch_b3_data(symbol, start_date, end_date)
                if df_daily.empty:
                    print(f"   ⚠️  Sem dados para {symbol}")
                    continue
                
                print(f"   📥 {len(df_daily)} dias")
                df_trigger = df_daily  # Para B3, usar diário como gatilho também
                tf_context = '1d'
                tf_trigger = '1d'
            
            # Verificar dados suficientes
            if len(df_daily) < self.ema_long:
                print(f"   ⚠️  Dados insuficientes: {len(df_daily)} < {self.ema_long}")
                continue
            
            # Calcular indicadores
            df_daily, df_trigger = self.calculate_indicators(df_daily, df_trigger)
            
            # Gerar sinais
            signals = self.generate_signals(df_daily, df_trigger)
            print(f"   📊 {len(signals)} sinais gerados")
            
            # Calcular métricas
            metrics = self.calculate_metrics(signals)
            
            # Print resultados
            print(f"\n   📈 RESULTADOS {symbol}:")
            print(f"      Trades: {metrics['total_trades']}")
            print(f"      Win Rate: {metrics['win_rate']:.2f}%")
            print(f"      Retorno Total: {metrics['total_return_pct']:.2f}%")
            print(f"      Retorno Médio: {metrics['avg_return_pct']:.2f}%")
            print(f"      Sharpe: {metrics['sharpe_ratio']:.2f}")
            print(f"      Max DD: {metrics['max_drawdown_pct']:.2f}%")
            print(f"      Melhor: {metrics['best_trade_pct']:.2f}%")
            print(f"      Pior: {metrics['worst_trade_pct']:.2f}%\n")
            
            result = BacktestResult(
                symbol=symbol,
                strategy='wave3',
                version=f"{self.version}_optimized" if self.version == 'crypto' else 'b3_original',
                timeframe_context=tf_context,
                timeframe_trigger=tf_trigger,
                total_trades=metrics['total_trades'],
                winning_trades=metrics['winning_trades'],
                losing_trades=metrics['losing_trades'],
                win_rate=metrics['win_rate'],
                total_return_pct=metrics['total_return_pct'],
                avg_return_pct=metrics['avg_return_pct'],
                sharpe_ratio=metrics['sharpe_ratio'],
                max_drawdown_pct=metrics['max_drawdown_pct'],
                best_trade_pct=metrics['best_trade_pct'],
                worst_trade_pct=metrics['worst_trade_pct'],
                ema_long=self.ema_long,
                ema_short=self.ema_short,
                min_candles=self.min_candles,
                risk_pct=self.risk_pct,
                reward_ratio=self.reward_ratio
            )
            
            results.append(result)
        
        return results
    
    def print_summary(self, results: List[BacktestResult]):
        """Imprime sumário"""
        if not results:
            print("⚠️  Nenhum resultado disponível")
            return
        
        version_name = results[0].version.upper()
        
        print("\n" + "="*70)
        print(f"📊 SUMÁRIO - {version_name}")
        print("="*70)
        
        print(f"\n{'Symbol':<10} {'Trades':<8} {'Win%':<8} {'Return%':<10} {'Sharpe':<8} {'MaxDD%':<8}")
        print("─" * 70)
        
        for r in results:
            print(f"{r.symbol:<10} {r.total_trades:<8} {r.win_rate:<8.2f} "
                  f"{r.total_return_pct:<10.2f} {r.sharpe_ratio:<8.2f} {r.max_drawdown_pct:<8.2f}")
        
        # Médias
        if len(results) > 0:
            avg_trades = np.mean([r.total_trades for r in results])
            avg_win_rate = np.mean([r.win_rate for r in results])
            avg_return = np.mean([r.total_return_pct for r in results])
            avg_sharpe = np.mean([r.sharpe_ratio for r in results])
            
            print("─" * 70)
            print(f"{'MÉDIA':<10} {avg_trades:<8.1f} {avg_win_rate:<8.2f} "
                  f"{avg_return:<10.2f} {avg_sharpe:<8.2f}")
        
        print("\n💡 ANÁLISE:")
        
        if len(results) > 0:
            avg_win_rate = np.mean([r.win_rate for r in results])
            avg_sharpe = np.mean([r.sharpe_ratio for r in results])
            
            # Win Rate
            if 48 <= avg_win_rate <= 55:
                print("   ✅ Win Rate dentro do esperado (50-52%)")
            elif avg_win_rate < 48:
                print(f"   ⚠️  Win Rate abaixo ({avg_win_rate:.1f}%) - revisar stops/entries")
            else:
                print(f"   ⚠️  Win Rate muito alto ({avg_win_rate:.1f}%) - possível overfitting")
            
            # Sharpe
            if avg_sharpe > 1.0:
                print("   ✅ Sharpe > 1.0 - excelente relação risco/retorno")
            elif avg_sharpe > 0.5:
                print("   ⚠️  Sharpe moderado - pode melhorar")
            elif avg_sharpe > 0:
                print("   ⚠️  Sharpe positivo mas baixo")
            else:
                print("   ❌ Sharpe negativo - estratégia não compensando risco")
        
        print("="*70 + "\n")


async def main():
    """Executa ambos os backtests"""
    
    db_config = {
        'host': 'timescaledb',
        'port': 5432,
        'database': 'b3trading_market',
        'user': 'b3trading_ts',
        'password': 'b3trading_ts_pass'
    }
    
    all_results = []
    
    # ========== CRYPTO OPTIMIZED ==========
    print("\n\n" + "█"*70)
    print("█  TESTE 1: CRYPTO OPTIMIZED")
    print("█"*70)
    
    crypto_symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'XRPUSDT']
    crypto_start = datetime(2025, 1, 16)
    crypto_end = datetime(2025, 12, 23)
    
    backtest_crypto = Wave3OptimizedBacktest(db_config, version='crypto')
    crypto_results = await backtest_crypto.run_backtest(crypto_symbols, crypto_start, crypto_end)
    backtest_crypto.print_summary(crypto_results)
    
    all_results.extend(crypto_results)
    
    # ========== B3 ORIGINAL ==========
    print("\n\n" + "█"*70)
    print("█  TESTE 2: B3 STOCKS ORIGINAL")
    print("█"*70)
    
    b3_symbols = ['ITUB4', 'VALE3', 'PETR4', 'MGLU3', 'BBDC4']
    b3_start = datetime(2024, 1, 2)  # Usar 2024+2025 para ter mais dados
    b3_end = datetime(2025, 12, 30)
    
    backtest_b3 = Wave3OptimizedBacktest(db_config, version='b3')
    b3_results = await backtest_b3.run_backtest(b3_symbols, b3_start, b3_end)
    backtest_b3.print_summary(b3_results)
    
    all_results.extend(b3_results)
    
    # ========== COMPARAÇÃO FINAL ==========
    print("\n\n" + "█"*70)
    print("█  COMPARAÇÃO: CRYPTO vs B3")
    print("█"*70 + "\n")
    
    if crypto_results and b3_results:
        crypto_avg_win = np.mean([r.win_rate for r in crypto_results])
        crypto_avg_return = np.mean([r.total_return_pct for r in crypto_results])
        crypto_avg_sharpe = np.mean([r.sharpe_ratio for r in crypto_results])
        
        b3_avg_win = np.mean([r.win_rate for r in b3_results])
        b3_avg_return = np.mean([r.total_return_pct for r in b3_results])
        b3_avg_sharpe = np.mean([r.sharpe_ratio for r in b3_results])
        
        print(f"{'Métrica':<20} {'Crypto':<15} {'B3':<15} {'Diferença':<15}")
        print("─" * 70)
        print(f"{'Win Rate':<20} {crypto_avg_win:<15.2f} {b3_avg_win:<15.2f} "
              f"{crypto_avg_win - b3_avg_win:+.2f}")
        print(f"{'Return Total %':<20} {crypto_avg_return:<15.2f} {b3_avg_return:<15.2f} "
              f"{crypto_avg_return - b3_avg_return:+.2f}")
        print(f"{'Sharpe Ratio':<20} {crypto_avg_sharpe:<15.2f} {b3_avg_sharpe:<15.2f} "
              f"{crypto_avg_sharpe - b3_avg_sharpe:+.2f}")
        
        print("\n💡 CONCLUSÕES:")
        
        if b3_avg_win > crypto_avg_win:
            diff = b3_avg_win - crypto_avg_win
            print(f"   • B3 teve Win Rate {diff:.1f}pp maior que Crypto")
        else:
            diff = crypto_avg_win - b3_avg_win
            print(f"   • Crypto teve Win Rate {diff:.1f}pp maior que B3")
        
        if b3_avg_sharpe > crypto_avg_sharpe:
            print(f"   • B3 teve melhor Sharpe ({b3_avg_sharpe:.2f} vs {crypto_avg_sharpe:.2f})")
        else:
            print(f"   • Crypto teve melhor Sharpe ({crypto_avg_sharpe:.2f} vs {b3_avg_sharpe:.2f})")
        
        if abs(b3_avg_win - 50) < abs(crypto_avg_win - 50):
            print(f"   • B3 mais próximo do Win Rate esperado (50%)")
        else:
            print(f"   • Crypto mais próximo do Win Rate esperado (50%)")
    
    # Salvar resultados
    results_dict = [asdict(r) for r in all_results]
    output_file = '/app/models/wave3_optimized_backtest_results.json'
    
    with open(output_file, 'w') as f:
        json.dump(results_dict, f, indent=2, default=str)
    
    print(f"\n💾 Resultados salvos: {output_file}")
    print("="*70 + "\n")


if __name__ == '__main__':
    asyncio.run(main())
