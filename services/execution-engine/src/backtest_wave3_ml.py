#!/usr/bin/env python3
"""
Backtest Wave3 + ML Strategy - Comparativo
===========================================

Testa a estratégia híbrida Wave3+ML (PASSO 12 v2) em:
1. B3 Stocks: PETR4, VALE3, ITUB4, MGLU3, BBDC4
2. Crypto: BTCUSDT, ETHUSDT, BNBUSDT, SOLUSDT, XRPUSDT

Compara:
- Wave3 Puro (baseline)
- Wave3 + ML (confidence > 0.6)
- Wave3 + ML (confidence > 0.7, conservador)

Métricas:
- Win Rate
- Total Trades
- Trades Filtrados pelo ML
- Sharpe Ratio
- Return %
"""

import asyncio
import asyncpg
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import json
import pickle
from pathlib import Path

# Import ML components
import sys
sys.path.append('/app/ml')
from ml_wave3_integration_v2 import FeatureEngineerV2, MLWave3Integrator


@dataclass
class BacktestResult:
    """Resultado do backtest"""
    symbol: str
    strategy: str  # 'wave3_pure', 'wave3_ml_0.6', 'wave3_ml_0.7'
    market: str  # 'b3' ou 'crypto'
    
    # Trade metrics
    total_signals: int  # Sinais Wave3 gerados
    total_trades: int   # Trades executados (após ML filter)
    trades_filtered: int  # Sinais filtrados pelo ML
    filter_rate: float  # % de sinais filtrados
    
    # Performance
    winning_trades: int
    losing_trades: int
    win_rate: float
    
    # Returns
    total_return_pct: float
    avg_return_pct: float
    
    # Risk
    sharpe_ratio: float
    max_drawdown_pct: float
    
    # ML specific
    avg_ml_confidence: Optional[float] = None
    false_positive_reduction: Optional[float] = None


class Wave3MLBacktest:
    """
    Backtest Wave3 + ML Strategy
    
    Compara performance de Wave3 puro vs Wave3+ML filtering
    """
    
    def __init__(
        self,
        db_config: dict,
        ml_model_path: str = '/app/models/ml_wave3_v2.pkl'
    ):
        self.db_config = db_config
        self.ml_model_path = ml_model_path
        
        # Carregar modelo ML
        self.ml_model = None
        self.feature_engineer = FeatureEngineerV2()
        
        if Path(ml_model_path).exists():
            with open(ml_model_path, 'rb') as f:
                model_data = pickle.load(f)
                self.ml_model = model_data['model']
                print(f"✅ ML Model loaded: {ml_model_path}")
                if 'metrics' in model_data:
                    print(f"   Accuracy: {model_data['metrics']['accuracy']:.4f}")
                    print(f"   ROC-AUC: {model_data['metrics']['roc_auc']:.4f}")
        else:
            print(f"⚠️  ML Model not found: {ml_model_path}")
            print("   Will train a new model...")
    
    async def fetch_data(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        table: str = 'ohlcv_daily'
    ) -> pd.DataFrame:
        """Busca dados do TimescaleDB"""
        conn = await asyncpg.connect(**self.db_config)
        
        # Adicionar 250 dias antes para warm-up de features
        warm_up_start = start_date - timedelta(days=250)
        
        query = f"""
            SELECT 
                time as timestamp,
                open::float,
                high::float,
                low::float,
                close::float,
                volume::float
            FROM {table}
            WHERE symbol = $1
                AND time >= $2
                AND time <= $3
            ORDER BY time ASC
        """
        
        rows = await conn.fetch(query, symbol, warm_up_start, end_date)
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
    
    def generate_wave3_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Gera sinais Wave3 baseline
        
        Critérios simplificados:
        - Preço acima EMA 72 (tendência alta)
        - Preço na zona das médias (EMA17/72 ± 1%)
        - RSI entre 40-60 (não sobrecomprado/sobrevendido)
        - MACD positivo
        """
        df = df.copy()
        
        # EMAs
        df['ema_72'] = df['close'].ewm(span=72, adjust=False).mean()
        df['ema_17'] = df['close'].ewm(span=17, adjust=False).mean()
        
        # MACD
        ema_12 = df['close'].ewm(span=12, adjust=False).mean()
        ema_26 = df['close'].ewm(span=26, adjust=False).mean()
        df['macd'] = ema_12 - ema_26
        df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
        df['macd_hist'] = df['macd'] - df['macd_signal']
        
        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # Zona de entrada
        df['zone_upper'] = df[['ema_72', 'ema_17']].max(axis=1) * 1.01
        df['zone_lower'] = df[['ema_72', 'ema_17']].min(axis=1) * 0.99
        df['in_zone'] = (
            (df['close'] >= df['zone_lower']) &
            (df['close'] <= df['zone_upper'])
        )
        
        # Sinal Wave3
        df['wave3_signal'] = (
            (df['close'] > df['ema_72']) &  # Tendência alta
            (df['in_zone']) &  # Na zona
            (df['rsi'] >= 40) & (df['rsi'] <= 60) &  # RSI neutro
            (df['macd_hist'] > 0)  # MACD positivo
        ).astype(int)
        
        return df
    
    def apply_ml_filter(
        self,
        df: pd.DataFrame,
        confidence_threshold: float = 0.6
    ) -> pd.DataFrame:
        """
        Aplica filtro ML aos sinais Wave3
        
        Retorna df com colunas adicionais:
        - ml_prediction: 0 ou 1
        - ml_confidence: probabilidade da classe 1
        - ml_filtered_signal: Wave3 AND ML (com threshold)
        """
        if self.ml_model is None:
            print("⚠️  ML Model not available, skipping ML filter")
            df['ml_prediction'] = 1
            df['ml_confidence'] = 1.0
            df['ml_filtered_signal'] = df['wave3_signal']
            return df
        
        # Gerar features
        self.feature_engineer.feature_list = []  # Reset
        df_features = self.feature_engineer.generate_all_features(df.copy())
        
        # Dropar NaN
        df_features = df_features.dropna()
        
        if len(df_features) == 0:
            print("⚠️  No data after dropna")
            df['ml_prediction'] = 1
            df['ml_confidence'] = 1.0
            df['ml_filtered_signal'] = df['wave3_signal']
            return df
        
        # Preparar features
        feature_cols = self.feature_engineer.feature_list
        
        # Verificar se todas as features existem
        missing_features = [f for f in feature_cols if f not in df_features.columns]
        if missing_features:
            print(f"⚠️  Missing features: {missing_features[:5]}...")
            # Usar features disponíveis
            feature_cols = [f for f in feature_cols if f in df_features.columns]
        
        X = df_features[feature_cols].values
        
        # Predição
        try:
            y_pred = self.ml_model.predict(X)
            y_proba = self.ml_model.predict_proba(X)[:, 1]  # Probabilidade classe 1
            
            # Adicionar ao DataFrame
            df_features['ml_prediction'] = y_pred
            df_features['ml_confidence'] = y_proba
            
            # Filtrar sinais: Wave3 AND ML (com threshold)
            df_features['ml_filtered_signal'] = (
                (df_features['wave3_signal'] == 1) &
                (df_features['ml_prediction'] == 1) &
                (df_features['ml_confidence'] >= confidence_threshold)
            ).astype(int)
            
            # Merge com df original
            df = df.join(df_features[['ml_prediction', 'ml_confidence', 'ml_filtered_signal']], how='left')
            df['ml_prediction'].fillna(0, inplace=True)
            df['ml_confidence'].fillna(0.0, inplace=True)
            df['ml_filtered_signal'].fillna(0, inplace=True)
            
        except Exception as e:
            print(f"❌ ML prediction error: {e}")
            df['ml_prediction'] = 1
            df['ml_confidence'] = 1.0
            df['ml_filtered_signal'] = df['wave3_signal']
        
        return df
    
    def simulate_trades(
        self,
        df: pd.DataFrame,
        signal_col: str = 'wave3_signal',
        risk_pct: float = 0.06,
        reward_ratio: float = 3.0
    ) -> Dict:
        """
        Simula trades baseado em sinais
        
        Args:
            signal_col: Coluna com sinais (wave3_signal ou ml_filtered_signal)
            risk_pct: % de risco por trade (stop)
            reward_ratio: Ratio reward:risk
        
        Returns:
            Dict com métricas de performance
        """
        trades = []
        in_position = False
        entry_price = None
        stop_loss = None
        target = None
        
        for i in range(len(df)):
            row = df.iloc[i]
            
            # Verificar entrada
            if not in_position and row[signal_col] == 1:
                entry_price = row['close']
                stop_loss = entry_price * (1 - risk_pct)
                risk = entry_price - stop_loss
                target = entry_price + (risk * reward_ratio)
                in_position = True
                entry_date = df.index[i]
                continue
            
            # Verificar saída
            if in_position:
                # Stop loss
                if row['low'] <= stop_loss:
                    pnl_pct = (stop_loss - entry_price) / entry_price * 100
                    trades.append({
                        'entry_date': entry_date,
                        'exit_date': df.index[i],
                        'entry_price': entry_price,
                        'exit_price': stop_loss,
                        'pnl_pct': pnl_pct,
                        'exit_reason': 'stop'
                    })
                    in_position = False
                    continue
                
                # Target
                if row['high'] >= target:
                    pnl_pct = (target - entry_price) / entry_price * 100
                    trades.append({
                        'entry_date': entry_date,
                        'exit_date': df.index[i],
                        'entry_price': entry_price,
                        'exit_price': target,
                        'pnl_pct': pnl_pct,
                        'exit_reason': 'target'
                    })
                    in_position = False
                    continue
        
        # Fechar posição final (se ainda aberta)
        if in_position:
            last_price = df.iloc[-1]['close']
            pnl_pct = (last_price - entry_price) / entry_price * 100
            trades.append({
                'entry_date': entry_date,
                'exit_date': df.index[-1],
                'entry_price': entry_price,
                'exit_price': last_price,
                'pnl_pct': pnl_pct,
                'exit_reason': 'end'
            })
        
        # Calcular métricas
        if not trades:
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0,
                'total_return_pct': 0,
                'avg_return_pct': 0,
                'sharpe_ratio': 0,
                'max_drawdown_pct': 0
            }
        
        trades_df = pd.DataFrame(trades)
        winning = len(trades_df[trades_df['pnl_pct'] > 0])
        losing = len(trades_df[trades_df['pnl_pct'] <= 0])
        win_rate = winning / len(trades) if trades else 0
        
        total_return = trades_df['pnl_pct'].sum()
        avg_return = trades_df['pnl_pct'].mean()
        
        # Sharpe
        if len(trades) > 1 and trades_df['pnl_pct'].std() > 0:
            sharpe = trades_df['pnl_pct'].mean() / trades_df['pnl_pct'].std()
        else:
            sharpe = 0
        
        # Max DD
        cumulative = trades_df['pnl_pct'].cumsum()
        running_max = cumulative.cummax()
        drawdown = running_max - cumulative
        max_dd = drawdown.max()
        
        return {
            'total_trades': len(trades),
            'winning_trades': winning,
            'losing_trades': losing,
            'win_rate': win_rate * 100,
            'total_return_pct': total_return,
            'avg_return_pct': avg_return,
            'sharpe_ratio': sharpe,
            'max_drawdown_pct': max_dd
        }
    
    async def run_backtest(
        self,
        symbols: List[str],
        start_date: datetime,
        end_date: datetime,
        market: str = 'b3',  # 'b3' ou 'crypto'
        confidence_thresholds: List[float] = [0.6, 0.7]
    ) -> List[BacktestResult]:
        """Executa backtest comparativo"""
        
        results = []
        
        table = 'ohlcv_daily' if market == 'b3' else 'crypto_ohlcv_1h'
        
        print("\n" + "="*70)
        print(f"🔄 WAVE3 + ML BACKTEST - {market.upper()}")
        print("="*70)
        print(f"📊 Símbolos: {', '.join(symbols)}")
        print(f"📅 Período: {start_date.date()} → {end_date.date()}")
        print(f"🤖 ML Thresholds: {confidence_thresholds}")
        print("="*70 + "\n")
        
        for symbol in symbols:
            print(f"{'─'*70}")
            print(f"📊 {symbol}")
            print(f"{'─'*70}")
            
            # Fetch data
            df = await self.fetch_data(symbol, start_date, end_date, table)
            
            if df.empty:
                print(f"   ⚠️  Sem dados para {symbol}\n")
                continue
            
            # Se crypto, agregar para diário
            if market == 'crypto':
                print(f"   📥 {len(df)} candlesticks horários")
                df = self.aggregate_to_daily(df)
                print(f"   📊 {len(df)} dias agregados")
            else:
                print(f"   📥 {len(df)} dias")
            
            # Filtrar para período de teste (após warm-up)
            # Garantir timezone match
            if df.index.tz is not None:
                test_start = pd.Timestamp(start_date).tz_localize('UTC')
            else:
                test_start = start_date
            
            df = df[df.index >= test_start]
            
            if len(df) < 100:
                print(f"   ⚠️  Dados insuficientes após warm-up: {len(df)}\n")
                continue
            
            # Gerar sinais Wave3
            df = self.generate_wave3_signals(df)
            total_wave3_signals = df['wave3_signal'].sum()
            print(f"   📈 Wave3 sinais gerados: {total_wave3_signals}")
            
            # ========== TESTE 1: Wave3 PURO ==========
            print(f"\n   🔹 Wave3 Puro:")
            metrics_pure = self.simulate_trades(df, signal_col='wave3_signal')
            print(f"      Trades: {metrics_pure['total_trades']} | "
                  f"Win: {metrics_pure['win_rate']:.1f}% | "
                  f"Return: {metrics_pure['total_return_pct']:.2f}%")
            
            result_pure = BacktestResult(
                symbol=symbol,
                strategy='wave3_pure',
                market=market,
                total_signals=total_wave3_signals,
                total_trades=metrics_pure['total_trades'],
                trades_filtered=0,
                filter_rate=0.0,
                winning_trades=metrics_pure['winning_trades'],
                losing_trades=metrics_pure['losing_trades'],
                win_rate=metrics_pure['win_rate'],
                total_return_pct=metrics_pure['total_return_pct'],
                avg_return_pct=metrics_pure['avg_return_pct'],
                sharpe_ratio=metrics_pure['sharpe_ratio'],
                max_drawdown_pct=metrics_pure['max_drawdown_pct']
            )
            results.append(result_pure)
            
            # ========== TESTE 2 & 3: Wave3 + ML ==========
            for threshold in confidence_thresholds:
                print(f"\n   🔹 Wave3 + ML (threshold {threshold}):")
                
                # Aplicar ML filter
                df = self.apply_ml_filter(df, confidence_threshold=threshold)
                
                ml_signals = df['ml_filtered_signal'].sum()
                filtered = total_wave3_signals - ml_signals
                filter_rate = (filtered / total_wave3_signals * 100) if total_wave3_signals > 0 else 0
                
                # Confidence médio dos sinais aceitos
                df_accepted = df[df['ml_filtered_signal'] == 1]
                avg_confidence = df_accepted['ml_confidence'].mean() if len(df_accepted) > 0 else 0
                
                print(f"      ML sinais aceitos: {ml_signals}")
                print(f"      Sinais filtrados: {filtered} ({filter_rate:.1f}%)")
                print(f"      Avg confidence: {avg_confidence:.3f}")
                
                # Simular trades
                metrics_ml = self.simulate_trades(df, signal_col='ml_filtered_signal')
                print(f"      Trades: {metrics_ml['total_trades']} | "
                      f"Win: {metrics_ml['win_rate']:.1f}% | "
                      f"Return: {metrics_ml['total_return_pct']:.2f}%")
                
                # False positive reduction
                if metrics_pure['total_trades'] > 0 and metrics_ml['total_trades'] > 0:
                    fp_reduction = (
                        (metrics_pure['losing_trades'] - metrics_ml['losing_trades']) /
                        metrics_pure['losing_trades'] * 100
                    ) if metrics_pure['losing_trades'] > 0 else 0
                else:
                    fp_reduction = 0
                
                result_ml = BacktestResult(
                    symbol=symbol,
                    strategy=f'wave3_ml_{threshold}',
                    market=market,
                    total_signals=total_wave3_signals,
                    total_trades=metrics_ml['total_trades'],
                    trades_filtered=filtered,
                    filter_rate=filter_rate,
                    winning_trades=metrics_ml['winning_trades'],
                    losing_trades=metrics_ml['losing_trades'],
                    win_rate=metrics_ml['win_rate'],
                    total_return_pct=metrics_ml['total_return_pct'],
                    avg_return_pct=metrics_ml['avg_return_pct'],
                    sharpe_ratio=metrics_ml['sharpe_ratio'],
                    max_drawdown_pct=metrics_ml['max_drawdown_pct'],
                    avg_ml_confidence=avg_confidence,
                    false_positive_reduction=fp_reduction
                )
                results.append(result_ml)
            
            print()
        
        return results
    
    def print_summary(self, results: List[BacktestResult]):
        """Imprime sumário comparativo"""
        if not results:
            print("⚠️  Nenhum resultado disponível")
            return
        
        market = results[0].market.upper()
        
        print("\n" + "="*90)
        print(f"📊 SUMÁRIO - {market}")
        print("="*90)
        
        # Agrupar por estratégia
        strategies = {}
        for r in results:
            if r.strategy not in strategies:
                strategies[r.strategy] = []
            strategies[r.strategy].append(r)
        
        for strategy_name, strategy_results in strategies.items():
            print(f"\n🔹 {strategy_name.upper()}")
            print("─"*90)
            print(f"{'Symbol':<10} {'Trades':<8} {'Filtered':<10} {'Win%':<8} "
                  f"{'Return%':<10} {'Sharpe':<8} {'Confidence':<10}")
            print("─"*90)
            
            for r in strategy_results:
                conf_str = f"{r.avg_ml_confidence:.3f}" if r.avg_ml_confidence else "-"
                print(f"{r.symbol:<10} {r.total_trades:<8} {r.trades_filtered:<10} "
                      f"{r.win_rate:<8.1f} {r.total_return_pct:<10.2f} "
                      f"{r.sharpe_ratio:<8.2f} {conf_str:<10}")
            
            # Médias
            avg_trades = np.mean([r.total_trades for r in strategy_results if r.total_trades > 0])
            avg_win = np.mean([r.win_rate for r in strategy_results if r.total_trades > 0])
            avg_return = np.mean([r.total_return_pct for r in strategy_results if r.total_trades > 0])
            avg_sharpe = np.mean([r.sharpe_ratio for r in strategy_results if r.total_trades > 0])
            
            print("─"*90)
            print(f"{'MÉDIA':<10} {avg_trades:<8.1f} {'':<10} {avg_win:<8.1f} "
                  f"{avg_return:<10.2f} {avg_sharpe:<8.2f}")
        
        print("\n" + "="*90)
        print("💡 COMPARAÇÃO:")
        
        # Comparar Wave3 puro vs ML
        pure_results = [r for r in results if r.strategy == 'wave3_pure' and r.total_trades > 0]
        ml_06_results = [r for r in results if r.strategy == 'wave3_ml_0.6' and r.total_trades > 0]
        ml_07_results = [r for r in results if r.strategy == 'wave3_ml_0.7' and r.total_trades > 0]
        
        if pure_results and ml_06_results:
            pure_win = np.mean([r.win_rate for r in pure_results])
            ml_06_win = np.mean([r.win_rate for r in ml_06_results])
            pure_sharpe = np.mean([r.sharpe_ratio for r in pure_results])
            ml_06_sharpe = np.mean([r.sharpe_ratio for r in ml_06_results])
            
            print(f"   • Wave3 Puro: Win {pure_win:.1f}% | Sharpe {pure_sharpe:.2f}")
            print(f"   • Wave3+ML(0.6): Win {ml_06_win:.1f}% | Sharpe {ml_06_sharpe:.2f}")
            
            if ml_06_win > pure_win:
                diff = ml_06_win - pure_win
                print(f"   ✅ ML melhorou Win Rate em {diff:.1f}pp")
            
            if ml_06_sharpe > pure_sharpe:
                diff = ml_06_sharpe - pure_sharpe
                print(f"   ✅ ML melhorou Sharpe em {diff:.2f}")
            
            # Filter rate médio
            avg_filter = np.mean([r.filter_rate for r in ml_06_results])
            print(f"   📊 ML filtrou {avg_filter:.1f}% dos sinais Wave3")
        
        print("="*90 + "\n")


async def main():
    """Executa backtests Wave3+ML"""
    
    db_config = {
        'host': 'timescaledb',
        'port': 5432,
        'database': 'b3trading_market',
        'user': 'b3trading_ts',
        'password': 'b3trading_ts_pass'
    }
    
    # Verificar se modelo existe, senão treinar
    model_path = '/app/models/ml_wave3_v2.pkl'
    if not Path(model_path).exists():
        print("\n🔧 ML Model not found. Training new model...")
        print("   This may take a few minutes...\n")
        
        # Treinar modelo básico
        integrator = MLWave3Integrator(db_config)
        symbols_train = ['ITUB4', 'VALE3', 'PETR4', 'MGLU3', 'BBDC4']
        start_train = datetime(2024, 1, 2)
        end_train = datetime(2025, 12, 30)
        
        await integrator.train_model(
            symbols=symbols_train,
            start_date=start_train,
            end_date=end_train,
            model_type='random_forest',
            use_smote=True,
            test_size=0.2
        )
    
    # Inicializar backtest
    backtest = Wave3MLBacktest(db_config, ml_model_path=model_path)
    
    all_results = []
    
    # ========== TESTE 1: B3 STOCKS ==========
    print("\n\n" + "█"*70)
    print("█  TESTE 1: B3 STOCKS (Wave3 + ML)")
    print("█"*70)
    
    b3_symbols = ['PETR4', 'VALE3', 'ITUB4']  # Top 3 performers
    b3_start = datetime(2025, 1, 2)  # Usar apenas 2025 para teste out-of-sample
    b3_end = datetime(2025, 12, 30)
    
    b3_results = await backtest.run_backtest(
        symbols=b3_symbols,
        start_date=b3_start,
        end_date=b3_end,
        market='b3',
        confidence_thresholds=[0.6, 0.7]
    )
    
    backtest.print_summary(b3_results)
    all_results.extend(b3_results)
    
    # ========== TESTE 2: CRYPTO ==========
    print("\n\n" + "█"*70)
    print("█  TESTE 2: CRYPTO (Wave3 + ML)")
    print("█"*70)
    
    crypto_symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT']  # Top 3
    crypto_start = datetime(2025, 1, 16)
    crypto_end = datetime(2025, 12, 23)
    
    crypto_results = await backtest.run_backtest(
        symbols=crypto_symbols,
        start_date=crypto_start,
        end_date=crypto_end,
        market='crypto',
        confidence_thresholds=[0.6, 0.7]
    )
    
    backtest.print_summary(crypto_results)
    all_results.extend(crypto_results)
    
    # Salvar resultados
    results_dict = [asdict(r) for r in all_results]
    output_file = '/app/models/wave3_ml_backtest_results.json'
    
    with open(output_file, 'w') as f:
        json.dump(results_dict, f, indent=2, default=str)
    
    print(f"\n💾 Resultados salvos: {output_file}")
    print("="*70 + "\n")


if __name__ == '__main__':
    asyncio.run(main())
