#!/usr/bin/env python3
"""
Backtest Wave3 Strategy com Criptomoedas
=========================================

Testa a estratégia Wave3 (André Moraes) com dados de criptomoedas:
- Contexto: 1d (dados diários agregados)
- Gatilho: 1h (dados horários)
- Símbolos: BTC, ETH, BNB, SOL
- Período: 2025

Compara performance com ações B3 para validar adaptabilidade.
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
    timeframe_context: str  # 1d, 4h
    timeframe_trigger: str  # 1h, 15min
    
    # Métricas gerais
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    
    # Retornos
    total_return: float
    total_return_pct: float
    avg_return: float
    avg_return_pct: float
    
    # Risk metrics
    sharpe_ratio: float
    max_drawdown: float
    max_drawdown_pct: float
    
    # Trade metrics
    avg_holding_time_hours: float
    best_trade_pct: float
    worst_trade_pct: float
    
    # Estratégia específica
    avg_confidence: Optional[float] = None
    trades_filtered: Optional[int] = None


class Wave3CryptoBacktest:
    """
    Backtest da estratégia Wave3 para criptomoedas.
    
    Adaptações para crypto:
    - Mercado 24/7: não há gaps de fim de semana
    - Volatilidade maior: ajuste de stop/target
    - Regra dos 17 candles: pode precisar ajuste (mercado mais rápido)
    """
    
    def __init__(
        self,
        db_config: dict,
        ema_long: int = 72,
        ema_short: int = 17,
        min_candles: int = 17,
        risk_pct: float = 0.06,
        reward_ratio: float = 3.0
    ):
        self.db_config = db_config
        self.ema_long = ema_long
        self.ema_short = ema_short
        self.min_candles = min_candles
        self.risk_pct = risk_pct
        self.reward_ratio = reward_ratio
        
    async def fetch_hourly_data(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime
    ) -> pd.DataFrame:
        """Busca dados horários da crypto"""
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
        
        print(f"   📥 {symbol}: {len(df)} candlesticks horários")
        return df
    
    def aggregate_to_daily(self, df_hourly: pd.DataFrame) -> pd.DataFrame:
        """Agrega dados horários para diário"""
        if df_hourly.empty:
            return pd.DataFrame()
        
        df_daily = df_hourly.resample('D').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }).dropna()
        
        print(f"   📊 Agregado para diário: {len(df_daily)} dias")
        return df_daily
    
    def calculate_wave3_indicators(
        self,
        df_daily: pd.DataFrame,
        df_hourly: pd.DataFrame
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """
        Calcula indicadores Wave3:
        - Diário: EMA 72, EMA 17, zona de entrada
        - Horário: pivôs, ondas, stops
        """
        # Contexto Diário
        df_daily = df_daily.copy()
        df_daily['ema_long'] = df_daily['close'].ewm(span=self.ema_long, adjust=False).mean()
        df_daily['ema_short'] = df_daily['close'].ewm(span=self.ema_short, adjust=False).mean()
        
        # Zona de entrada (entre médias ±1%)
        df_daily['zone_upper'] = df_daily[['ema_long', 'ema_short']].max(axis=1) * 1.01
        df_daily['zone_lower'] = df_daily[['ema_long', 'ema_short']].min(axis=1) * 0.99
        df_daily['in_zone'] = (
            (df_daily['close'] >= df_daily['zone_lower']) &
            (df_daily['close'] <= df_daily['zone_upper'])
        )
        
        # Tendência
        df_daily['trend'] = np.where(df_daily['close'] > df_daily['ema_long'], 1, -1)
        
        # Horário: identificar pivôs
        df_hourly = df_hourly.copy()
        df_hourly['pivot_low'] = (
            (df_hourly['low'] < df_hourly['low'].shift(1)) &
            (df_hourly['low'] < df_hourly['low'].shift(-1))
        )
        df_hourly['pivot_high'] = (
            (df_hourly['high'] > df_hourly['high'].shift(1)) &
            (df_hourly['high'] > df_hourly['high'].shift(-1))
        )
        
        return df_daily, df_hourly
    
    def generate_signals(
        self,
        df_daily: pd.DataFrame,
        df_hourly: pd.DataFrame
    ) -> List[Dict]:
        """
        Gera sinais de compra/venda seguindo a lógica Wave3:
        
        1. Contexto diário: preço em zona de entrada + tendência de alta
        2. Gatilho 60min: pivô de alta confirmado (onda 3)
        3. Regra dos 17 candles: distância mínima entre pivôs
        """
        signals = []
        
        last_pivot_low_idx = None
        last_pivot_high_idx = None
        in_position = False
        entry_price = None
        stop_loss = None
        target = None
        
        # Merge contexto diário no horário
        df_hourly['date'] = df_hourly.index.date
        df_daily['date'] = df_daily.index.date
        df_hourly = df_hourly.merge(
            df_daily[['date', 'trend', 'in_zone', 'ema_long']],
            on='date',
            how='left'
        )
        
        for i in range(self.min_candles, len(df_hourly)):
            row = df_hourly.iloc[i]
            timestamp = df_hourly.index[i]
            
            # Verificar saída (se em posição)
            if in_position:
                # Stop loss
                if row['low'] <= stop_loss:
                    signals.append({
                        'timestamp': timestamp,
                        'action': 'SELL',
                        'price': stop_loss,
                        'reason': 'stop_loss',
                        'pnl_pct': (stop_loss - entry_price) / entry_price * 100
                    })
                    in_position = False
                    continue
                
                # Target
                if row['high'] >= target:
                    signals.append({
                        'timestamp': timestamp,
                        'action': 'SELL',
                        'price': target,
                        'reason': 'target',
                        'pnl_pct': (target - entry_price) / entry_price * 100
                    })
                    in_position = False
                    continue
                
                # Trailing stop: novo fundo confirmado
                if row['pivot_low']:
                    candles_since_last = i - last_pivot_low_idx if last_pivot_low_idx else 100
                    if candles_since_last >= self.min_candles:
                        new_stop = row['low'] * 0.98
                        if new_stop > stop_loss:
                            stop_loss = new_stop
                            print(f"      🔧 Trailing stop: {stop_loss:.2f}")
            
            # Verificar entrada (se não em posição)
            if not in_position:
                # Condições:
                # 1. Tendência de alta no diário
                if row['trend'] != 1:
                    continue
                
                # 2. Preço na zona de entrada
                if not row['in_zone']:
                    continue
                
                # 3. Pivô de baixa confirmado (fundo)
                if row['pivot_low']:
                    if last_pivot_low_idx and (i - last_pivot_low_idx) >= self.min_candles:
                        # Pivô válido pela regra dos 17 candles
                        last_pivot_low_idx = i
                    else:
                        last_pivot_low_idx = i
                        continue
                
                # 4. Rompimento do topo intermediário (Onda 3)
                if last_pivot_low_idx and last_pivot_high_idx:
                    pivot_low_price = df_hourly.iloc[last_pivot_low_idx]['low']
                    pivot_high_price = df_hourly.iloc[last_pivot_high_idx]['high']
                    
                    # Onda 3: preço rompe o topo anterior
                    if row['high'] > pivot_high_price:
                        # Confirmar que o novo fundo é mais alto
                        if pivot_low_price > df_hourly.iloc[last_pivot_low_idx - self.min_candles]['low']:
                            # COMPRA!
                            entry_price = row['close']
                            stop_loss = pivot_low_price * 0.98  # 2% abaixo do fundo
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
                            print(f"   🚀 BUY: {entry_price:.2f} | Stop: {stop_loss:.2f} | Target: {target:.2f}")
                
                # Atualizar último topo
                if row['pivot_high']:
                    if last_pivot_high_idx and (i - last_pivot_high_idx) >= self.min_candles:
                        last_pivot_high_idx = i
                    else:
                        last_pivot_high_idx = i
        
        return signals
    
    def calculate_metrics(
        self,
        signals: List[Dict],
        initial_capital: float = 100000.0
    ) -> Dict:
        """Calcula métricas de performance"""
        
        if not signals:
            return {
                'total_trades': 0,
                'win_rate': 0,
                'total_return_pct': 0,
                'sharpe_ratio': 0,
                'max_drawdown_pct': 0
            }
        
        # Separar compras e vendas
        buys = [s for s in signals if s['action'] == 'BUY']
        sells = [s for s in signals if s['action'] == 'SELL']
        
        total_trades = min(len(buys), len(sells))
        
        if total_trades == 0:
            return {'total_trades': 0}
        
        # Calcular PnL de cada trade
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
        
        # Sharpe Ratio (simplificado)
        if len(trades_pnl) > 1:
            sharpe = np.mean(trades_pnl) / np.std(trades_pnl) if np.std(trades_pnl) > 0 else 0
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
        """
        Executa backtest para múltiplos símbolos
        """
        results = []
        
        print("\n" + "="*70)
        print("🔄 WAVE3 CRYPTO BACKTEST")
        print("="*70)
        print(f"📊 Símbolos: {', '.join(symbols)}")
        print(f"📅 Período: {start_date.date()} → {end_date.date()}")
        print(f"📈 Estratégia: Wave3 (EMA {self.ema_long}/{self.ema_short})")
        print(f"⚙️  Regra: {self.min_candles} candles | Risk: {self.risk_pct*100:.0f}% | R:R {self.reward_ratio}:1")
        print("="*70 + "\n")
        
        for symbol in symbols:
            print(f"\n{'─'*70}")
            print(f"📊 {symbol}")
            print(f"{'─'*70}")
            
            # Fetch data
            df_hourly = await self.fetch_hourly_data(symbol, start_date, end_date)
            
            if df_hourly.empty:
                print(f"   ⚠️  Sem dados para {symbol}")
                continue
            
            # Aggregate to daily
            df_daily = self.aggregate_to_daily(df_hourly)
            
            if len(df_daily) < self.ema_long:
                print(f"   ⚠️  Dados insuficientes: {len(df_daily)} dias < {self.ema_long}")
                continue
            
            # Calculate indicators
            df_daily, df_hourly = self.calculate_wave3_indicators(df_daily, df_hourly)
            
            # Generate signals
            signals = self.generate_signals(df_daily, df_hourly)
            print(f"   📊 Sinais gerados: {len(signals)}")
            
            # Calculate metrics
            metrics = self.calculate_metrics(signals)
            
            # Print results
            print(f"\n   📈 RESULTADOS {symbol}:")
            print(f"      Trades: {metrics.get('total_trades', 0)}")
            print(f"      Win Rate: {metrics.get('win_rate', 0):.2f}%")
            print(f"      Retorno Total: {metrics.get('total_return_pct', 0):.2f}%")
            print(f"      Retorno Médio: {metrics.get('avg_return_pct', 0):.2f}%")
            print(f"      Sharpe: {metrics.get('sharpe_ratio', 0):.2f}")
            print(f"      Max DD: {metrics.get('max_drawdown_pct', 0):.2f}%")
            print(f"      Melhor: {metrics.get('best_trade_pct', 0):.2f}%")
            print(f"      Pior: {metrics.get('worst_trade_pct', 0):.2f}%")
            
            result = BacktestResult(
                symbol=symbol,
                strategy='wave3',
                timeframe_context='1d',
                timeframe_trigger='1h',
                total_trades=metrics.get('total_trades', 0),
                winning_trades=metrics.get('winning_trades', 0),
                losing_trades=metrics.get('losing_trades', 0),
                win_rate=metrics.get('win_rate', 0),
                total_return=0,
                total_return_pct=metrics.get('total_return_pct', 0),
                avg_return=0,
                avg_return_pct=metrics.get('avg_return_pct', 0),
                sharpe_ratio=metrics.get('sharpe_ratio', 0),
                max_drawdown=0,
                max_drawdown_pct=metrics.get('max_drawdown_pct', 0),
                avg_holding_time_hours=0,
                best_trade_pct=metrics.get('best_trade_pct', 0),
                worst_trade_pct=metrics.get('worst_trade_pct', 0)
            )
            
            results.append(result)
        
        return results
    
    def print_summary(self, results: List[BacktestResult]):
        """Imprime sumário consolidado"""
        print("\n" + "="*70)
        print("📊 SUMÁRIO CONSOLIDADO - WAVE3 CRYPTO")
        print("="*70)
        
        if not results:
            print("⚠️  Nenhum resultado disponível")
            return
        
        # Tabela de resultados
        print(f"\n{'Symbol':<10} {'Trades':<8} {'Win%':<8} {'Return%':<10} {'Sharpe':<8} {'MaxDD%':<8}")
        print("─" * 70)
        
        for r in results:
            print(f"{r.symbol:<10} {r.total_trades:<8} {r.win_rate:<8.2f} "
                  f"{r.total_return_pct:<10.2f} {r.sharpe_ratio:<8.2f} {r.max_drawdown_pct:<8.2f}")
        
        # Médias
        avg_trades = np.mean([r.total_trades for r in results])
        avg_win_rate = np.mean([r.win_rate for r in results])
        avg_return = np.mean([r.total_return_pct for r in results])
        avg_sharpe = np.mean([r.sharpe_ratio for r in results])
        
        print("─" * 70)
        print(f"{'MÉDIA':<10} {avg_trades:<8.1f} {avg_win_rate:<8.2f} "
              f"{avg_return:<10.2f} {avg_sharpe:<8.2f}")
        
        print("\n💡 ANÁLISE:")
        if avg_win_rate >= 45 and avg_win_rate <= 55:
            print("   ✅ Win Rate dentro do esperado (50-52%)")
        elif avg_win_rate < 45:
            print("   ⚠️  Win Rate abaixo do esperado - revisar stops")
        else:
            print("   ⚠️  Win Rate muito alto - possível overfitting")
        
        if avg_sharpe > 1.0:
            print("   ✅ Sharpe > 1.0 - boa relação risco/retorno")
        elif avg_sharpe > 0.5:
            print("   ⚠️  Sharpe moderado - pode melhorar")
        else:
            print("   ❌ Sharpe baixo - estratégia não compensando risco")
        
        print("="*70 + "\n")


async def main():
    """Executa backtest Wave3 com criptomoedas"""
    
    db_config = {
        'host': 'timescaledb',
        'port': 5432,
        'database': 'b3trading_market',
        'user': 'b3trading_ts',
        'password': 'b3trading_ts_pass'
    }
    
    # Símbolos principais
    symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT']
    
    # Período: full data disponível
    start_date = datetime(2025, 1, 16)
    end_date = datetime(2025, 12, 23)
    
    # Inicializar backtest
    backtest = Wave3CryptoBacktest(
        db_config=db_config,
        ema_long=72,
        ema_short=17,
        min_candles=17,
        risk_pct=0.06,
        reward_ratio=3.0
    )
    
    # Executar
    results = await backtest.run_backtest(symbols, start_date, end_date)
    
    # Sumário
    backtest.print_summary(results)
    
    # Salvar resultados
    results_dict = [asdict(r) for r in results]
    output_file = '/app/models/wave3_crypto_backtest_results.json'
    
    with open(output_file, 'w') as f:
        json.dump(results_dict, f, indent=2)
    
    print(f"💾 Resultados salvos: {output_file}")


if __name__ == '__main__':
    asyncio.run(main())
