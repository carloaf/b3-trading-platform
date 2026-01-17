"""
TESTE SIMPLES: Wave3 + ML usando MLWave3Integrator
Compara Wave3 pura vs Wave3+ML usando o integrator v2
"""

import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'ml'))

from ml_wave3_integration_v2 import MLWave3Integrator
import pandas as pd
import numpy as np
from dataclasses import dataclass
from datetime import datetime, timedelta

@dataclass
class SimpleBacktestResult:
    """Resultado simplificado"""
    symbol: str
    strategy: str  # 'wave3_pure' ou 'wave3_ml'
    period_days: int
    trades: int
    wins: int
    win_rate: float
    total_return: float
    sharpe: float
    signals_generated: int = 0
    signals_filtered: int = 0
    avg_confidence: float = 0.0


class SimpleWave3MLTest:
    """Teste simplificado Wave3+ML"""
    
    def __init__(self):
        self.db_config = {
            'host': 'timescaledb',
            'port': 5432,
            'database': 'b3trading',
            'user': 'trading_user',
            'password': 'trading_password'
        }
        
        # Carregar integrator com modelo
        self.integrator = MLWave3Integrator(self.db_config)
        model_path = '/app/models/ml_wave3_v2.pkl'
        
        if Path(model_path).exists():
            self.integrator.load_model(model_path)
            print(f"✅ ML model loaded successfully")
        else:
            print(f"❌ Model not found: {model_path}")
            sys.exit(1)
    
    async def fetch_data(self, symbol: str, start_date: datetime, market: str = 'b3'):
        """Busca dados históricos"""
        import asyncpg
        
        conn = await asyncpg.connect(**self.db_config)
        
        try:
            # Adicionar warm-up de 250 dias
            warmup_start = start_date - timedelta(days=500)
            
            if market == 'crypto':
                query = """
                    SELECT timestamp, open, high, low, close, volume, symbol
                    FROM crypto_ohlcv_1h
                    WHERE symbol = $1 AND timestamp >= $2
                    ORDER BY timestamp
                """
            else:
                query = """
                    SELECT timestamp, open, high, low, close, volume, symbol
                    FROM ohlcv_daily
                    WHERE symbol = $1 AND timestamp >= $2
                    ORDER BY timestamp
                """
            
            rows = await conn.fetch(query, symbol, warmup_start)
            
            if not rows:
                return pd.DataFrame()
            
            df = pd.DataFrame(rows, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'symbol'])
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.set_index('timestamp')
            df = df.sort_index()
            
            # Se crypto, agregar para diário
            if market == 'crypto':
                df = df.resample('1D').agg({
                    'open': 'first',
                    'high': 'max',
                    'low': 'min',
                    'close': 'last',
                    'volume': 'sum',
                    'symbol': 'first'
                }).dropna()
            
            return df
            
        finally:
            await conn.close()
    
    def generate_wave3_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """Gera sinais Wave3 PUROS (sem ML)"""
        df = df.copy()
        
        # EMAs
        df['ema_72'] = df['close'].ewm(span=72, adjust=False).mean()
        df['ema_17'] = df['close'].ewm(span=17, adjust=False).mean()
        
        # Trend
        df['uptrend'] = df['close'] > df['ema_72']
        
        # Zone (entre EMAs)
        df['in_zone'] = (
            (df['close'] >= df['ema_17'] * 0.99) &
            (df['close'] <= df['ema_72'] * 1.01)
        )
        
        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # MACD
        exp1 = df['close'].ewm(span=12, adjust=False).mean()
        exp2 = df['close'].ewm(span=26, adjust=False).mean()
        df['macd'] = exp1 - exp2
        df['signal'] = df['macd'].ewm(span=9, adjust=False).mean()
        df['macd_hist'] = df['macd'] - df['signal']
        
        # Wave3 signal: uptrend + in_zone + RSI médio + MACD positivo
        df['wave3_signal'] = (
            df['uptrend'] &
            df['in_zone'] &
            (df['rsi'] >= 40) &
            (df['rsi'] <= 60) &
            (df['macd_hist'] > 0)
        ).astype(int)
        
        return df
    
    async def get_ml_predictions(self, df: pd.DataFrame, symbol: str) -> pd.Series:
        """Usa MLWave3Integrator para gerar predições ML"""
        # Gerar features e predições
        df_with_ml = await self.integrator.get_trading_signals(
            df.copy(),
            [symbol],
            datetime.now() - timedelta(days=365),
            datetime.now()
        )
        
        # Retornar coluna de predição ML
        if 'ml_prediction' in df_with_ml.columns:
            return df_with_ml['ml_prediction']
        else:
            return pd.Series([0] * len(df), index=df.index)
    
    def simulate_trades(self, df: pd.DataFrame, signal_col: str) -> dict:
        """Simula trades com stops/alvos"""
        trades = []
        risk_pct = 0.06  # 6% stop
        reward_ratio = 3.0  # 3:1
        
        for idx, row in df[df[signal_col] == 1].iterrows():
            entry_price = row['close']
            stop_loss = entry_price * (1 - risk_pct)
            take_profit = entry_price * (1 + risk_pct * reward_ratio)
            
            # Buscar próximas 50 barras
            future_idx = df.index.get_loc(idx)
            future_data = df.iloc[future_idx+1:future_idx+51]
            
            if len(future_data) == 0:
                continue
            
            # Verificar stop ou target
            hit_stop = (future_data['low'] <= stop_loss).any()
            hit_target = (future_data['high'] >= take_profit).any()
            
            if hit_stop and hit_target:
                # Qual veio primeiro?
                stop_idx = future_data[future_data['low'] <= stop_loss].index[0]
                target_idx = future_data[future_data['high'] >= take_profit].index[0]
                
                if stop_idx < target_idx:
                    trades.append({'result': 'loss', 'return': -risk_pct})
                else:
                    trades.append({'result': 'win', 'return': risk_pct * reward_ratio})
            elif hit_stop:
                trades.append({'result': 'loss', 'return': -risk_pct})
            elif hit_target:
                trades.append({'result': 'win', 'return': risk_pct * reward_ratio})
            else:
                # Sem decisão - sair no close final
                final_price = future_data.iloc[-1]['close']
                ret = (final_price - entry_price) / entry_price
                trades.append({'result': 'neutral', 'return': ret})
        
        if not trades:
            return {
                'trades': 0,
                'wins': 0,
                'win_rate': 0.0,
                'total_return': 0.0,
                'sharpe': 0.0
            }
        
        wins = sum(1 for t in trades if t['result'] == 'win')
        returns = [t['return'] for t in trades]
        
        return {
            'trades': len(trades),
            'wins': wins,
            'win_rate': wins / len(trades) * 100,
            'total_return': sum(returns) * 100,
            'sharpe': np.mean(returns) / np.std(returns) if np.std(returns) > 0 else 0.0
        }
    
    async def test_symbol(self, symbol: str, start_date: datetime, market: str = 'b3') -> list:
        """Testa um símbolo com Wave3 pure e Wave3+ML"""
        print(f"\n{'─'*70}")
        print(f"📊 {symbol}")
        print(f"{'─'*70}")
        
        # Fetch data
        df = await self.fetch_data(symbol, start_date, market)
        
        if len(df) < 100:
            print(f"   ⚠️  Dados insuficientes: {len(df)}")
            return []
        
        print(f"   📥 {len(df)} dias carregados")
        
        # Gerar sinais Wave3 puros
        df = self.generate_wave3_signals(df)
        
        # Filtrar para período de teste (após warm-up)
        if df.index.tz is not None:
            test_start = pd.Timestamp(start_date).tz_localize('UTC')
        else:
            test_start = start_date
        
        df_test = df[df.index >= test_start].copy()
        
        if len(df_test) < 50:
            print(f"   ⚠️  Período de teste insuficiente: {len(df_test)}")
            return []
        
        print(f"   📅 {len(df_test)} dias no período de teste")
        
        total_wave3 = df_test['wave3_signal'].sum()
        print(f"   📈 Wave3 sinais gerados: {total_wave3}")
        
        results = []
        
        # ========== TESTE 1: Wave3 PURO ==========
        print(f"\n   🔹 Wave3 Puro:")
        metrics_pure = self.simulate_trades(df_test, 'wave3_signal')
        print(f"      Trades: {metrics_pure['trades']} | Win: {metrics_pure['win_rate']:.1f}% | Return: {metrics_pure['total_return']:+.2f}%")
        
        results.append(SimpleBacktestResult(
            symbol=symbol,
            strategy='wave3_pure',
            period_days=len(df_test),
            trades=metrics_pure['trades'],
            wins=metrics_pure['wins'],
            win_rate=metrics_pure['win_rate'],
            total_return=metrics_pure['total_return'],
            sharpe=metrics_pure['sharpe'],
            signals_generated=total_wave3,
            signals_filtered=0
        ))
        
        # ========== TESTE 2: Wave3 + ML ==========
        print(f"\n   🔹 Wave3 + ML:")
        
        try:
            # Obter predições ML usando integrator
            df_with_ml = await self.integrator.get_trading_signals(
                df_test.copy(),
                [symbol],
                start_date,
                start_date + timedelta(days=365)
            )
            
            if 'ml_prediction' not in df_with_ml.columns:
                print(f"      ❌ ML predictions not available")
                return results
            
            # Combinar: Wave3 AND ML
            df_with_ml['wave3_ml_signal'] = (
                (df_with_ml['wave3_signal'] == 1) &
                (df_with_ml['ml_prediction'] == 1)
            ).astype(int)
            
            total_ml = df_with_ml['wave3_ml_signal'].sum()
            filtered = total_wave3 - total_ml
            
            print(f"      ML sinais aceitos: {total_ml}")
            print(f"      Sinais filtrados: {filtered} ({filtered/total_wave3*100:.1f}%)" if total_wave3 > 0 else "      Sinais filtrados: 0")
            
            # Simular trades
            metrics_ml = self.simulate_trades(df_with_ml, 'wave3_ml_signal')
            print(f"      Trades: {metrics_ml['trades']} | Win: {metrics_ml['win_rate']:.1f}% | Return: {metrics_ml['total_return']:+.2f}%")
            
            # Calcular confiança média
            if 'ml_confidence' in df_with_ml.columns:
                ml_trades = df_with_ml[df_with_ml['wave3_ml_signal'] == 1]
                avg_conf = ml_trades['ml_confidence'].mean() if len(ml_trades) > 0 else 0.0
            else:
                avg_conf = 0.0
            
            results.append(SimpleBacktestResult(
                symbol=symbol,
                strategy='wave3_ml',
                period_days=len(df_test),
                trades=metrics_ml['trades'],
                wins=metrics_ml['wins'],
                win_rate=metrics_ml['win_rate'],
                total_return=metrics_ml['total_return'],
                sharpe=metrics_ml['sharpe'],
                signals_generated=total_wave3,
                signals_filtered=filtered,
                avg_confidence=avg_conf
            ))
            
        except Exception as e:
            print(f"      ❌ Erro ML: {str(e)}")
        
        return results


async def main():
    """Main test"""
    print("\n" + "█"*70)
    print("█  TESTE WAVE3 + ML (Simplified)")
    print("█"*70)
    
    tester = SimpleWave3MLTest()
    
    all_results = []
    
    # ========== TESTE 1: B3 STOCKS ==========
    print("\n\n" + "="*70)
    print("🔷 TESTE 1: B3 STOCKS")
    print("="*70)
    
    b3_symbols = ['PETR4', 'VALE3', 'ITUB4']
    b3_start = datetime(2025, 1, 2)
    
    for symbol in b3_symbols:
        results = await tester.test_symbol(symbol, b3_start, market='b3')
        all_results.extend(results)
    
    # ========== TESTE 2: CRYPTO ==========
    print("\n\n" + "="*70)
    print("🔷 TESTE 2: CRYPTO")
    print("="*70)
    
    crypto_symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT']
    crypto_start = datetime(2025, 1, 16)
    
    for symbol in crypto_symbols:
        results = await tester.test_symbol(symbol, crypto_start, market='crypto')
        all_results.extend(results)
    
    # ========== SUMÁRIO ==========
    print("\n\n" + "="*70)
    print("📊 SUMÁRIO GERAL")
    print("="*70)
    
    # Agrupar por estratégia
    for strategy in ['wave3_pure', 'wave3_ml']:
        strategy_results = [r for r in all_results if r.strategy == strategy]
        
        if not strategy_results:
            continue
        
        print(f"\n🔹 {strategy.upper().replace('_', ' ')}")
        print(f"{'─'*70}")
        print(f"{'Symbol':<12} {'Trades':>8} {'Win%':>8} {'Return%':>10} {'Sharpe':>8}")
        print(f"{'─'*70}")
        
        for r in strategy_results:
            print(f"{r.symbol:<12} {r.trades:>8} {r.win_rate:>7.1f}% {r.total_return:>9.2f}% {r.sharpe:>7.2f}")
        
        # Média
        avg_trades = np.mean([r.trades for r in strategy_results])
        avg_win = np.mean([r.win_rate for r in strategy_results])
        avg_return = np.mean([r.total_return for r in strategy_results])
        avg_sharpe = np.mean([r.sharpe for r in strategy_results if np.isfinite(r.sharpe)])
        
        print(f"{'─'*70}")
        print(f"{'MÉDIA':<12} {avg_trades:>8.1f} {avg_win:>7.1f}% {avg_return:>9.2f}% {avg_sharpe:>7.2f}")
    
    print("\n" + "="*70)


if __name__ == '__main__':
    asyncio.run(main())
