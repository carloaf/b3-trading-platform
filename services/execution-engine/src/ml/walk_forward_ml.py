#!/usr/bin/env python3
"""
PASSO 13: Walk-Forward Optimization para ML
===========================================

Walk-Forward com retreino periódico do modelo ML:
- Divisão em folds temporais (train/test windows)
- Retreino do modelo a cada fold
- Validação out-of-sample
- Métricas acumuladas por fold
- Comparação: ML estático vs ML walk-forward

Objetivo: Evitar overfitting e criar modelo adaptativo ao tempo

Author: B3 Trading Platform
Date: 16 de Janeiro de 2026
"""

import asyncio
import asyncpg
import pandas as pd
import numpy as np
from typing import List, Dict, Tuple, Optional
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pickle
import json
from dataclasses import dataclass, asdict

# ML imports
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, confusion_matrix
)
from imblearn.over_sampling import SMOTE
import xgboost as xgb

# Import from existing ML module
import sys
sys.path.append('/app/ml')
from ml_wave3_integration_v2 import FeatureEngineerV2, MLWave3Integrator


@dataclass
class FoldMetrics:
    """Métricas de um fold específico"""
    fold_id: int
    train_start: str
    train_end: str
    test_start: str
    test_end: str
    train_samples: int
    test_samples: int
    accuracy: float
    precision: float
    recall: float
    f1_score: float
    roc_auc: float
    trades: int
    win_rate: float
    sharpe_ratio: float
    max_drawdown: float
    total_return: float


@dataclass
class WalkForwardResults:
    """Resultados consolidados do Walk-Forward"""
    folds: List[FoldMetrics]
    avg_accuracy: float
    avg_roc_auc: float
    avg_win_rate: float
    avg_sharpe: float
    std_accuracy: float
    std_roc_auc: float
    consistency_score: float  # 1 - CV de accuracy
    total_trades: int
    overall_return: float


class MLWalkForward:
    """
    Walk-Forward Optimization para ML
    
    Divide dados em janelas temporais e retreina modelo periodicamente
    """
    
    def __init__(
        self,
        db_config: dict,
        folds: int = 4,
        train_months: int = 3,
        test_months: int = 1,
        table_name: str = 'ohlcv_daily'
    ):
        """
        Args:
            db_config: Configuração do banco TimescaleDB
            folds: Número de folds (padrão: 4)
            train_months: Meses para treino (padrão: 3)
            test_months: Meses para teste (padrão: 1)
            table_name: Nome da tabela (ohlcv_daily ou crypto_ohlcv_1h)
        """
        self.db_config = db_config
        self.folds = folds
        self.train_months = train_months
        self.test_months = test_months
        self.table_name = table_name
        self.feature_engineer = FeatureEngineerV2()
        self.models = {}  # Store model per fold
        self.fold_results = []
    
    def _split_timeline(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict[str, datetime]]:
        """
        Divide timeline em folds temporais
        
        Args:
            start_date: Data inicial
            end_date: Data final
        
        Returns:
            Lista de dicionários com {train_start, train_end, test_start, test_end}
        """
        folds_data = []
        fold_duration = timedelta(days=30 * (self.train_months + self.test_months))
        
        current_date = start_date
        
        for fold_id in range(self.folds):
            train_start = current_date
            train_end = current_date + timedelta(days=30 * self.train_months)
            test_start = train_end
            test_end = test_start + timedelta(days=30 * self.test_months)
            
            if test_end > end_date:
                break
            
            folds_data.append({
                'fold_id': fold_id + 1,
                'train_start': train_start,
                'train_end': train_end,
                'test_start': test_start,
                'test_end': test_end
            })
            
            # Rolling window: move forward by test_months
            current_date += timedelta(days=30 * self.test_months)
        
        return folds_data
    
    async def _fetch_data_window(
        self,
        symbols: List[str],
        start_date: datetime,
        end_date: datetime
    ) -> pd.DataFrame:
        """
        Busca dados para uma janela temporal específica
        
        IMPORTANTE: Para calcular features com janelas longas (EMA/SMA 200),
        buscamos dados desde 250 dias ANTES do start_date para "warm up" dos indicadores.
        Com dados de 2024+2025, temos 501 dias totais, permitindo warm-up adequado.
        """
        
        conn = await asyncpg.connect(**self.db_config)
        
        all_data = []
        
        # Warm-up: buscar dados desde 250 dias antes para calcular indicadores longos
        warm_up_days = 250
        warm_up_start = start_date - timedelta(days=warm_up_days)
        
        try:
            for symbol in symbols:
                # Ajusta query baseado no nome da tabela
                query = f"""
                    SELECT 
                        time as timestamp,
                        open::float,
                        high::float,
                        low::float,
                        close::float,
                        volume::float
                    FROM {self.table_name}
                    WHERE symbol = $1
                        AND time >= $2
                        AND time <= $3
                    ORDER BY time ASC
                """
                
                # Busca dados com warm-up (desde 2024 se necessário)
                rows = await conn.fetch(query, symbol, warm_up_start, end_date)
                
                if not rows:
                    continue
                
                df = pd.DataFrame(
                    rows,
                    columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
                )
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df = df.set_index('timestamp')
                df['symbol'] = symbol
                
                print(f"   📥 {symbol}: Fetched {len(df)} rows (with {warm_up_days}d warm-up)")
                
                # Generate features (reset feature_list first)
                self.feature_engineer.feature_list = []
                df = self.feature_engineer.generate_all_features(df)
                print(f"   🔧 {symbol}: After features & dropna: {len(df)} rows")
                
                # Filtra apenas o período desejado (descarta warm-up)
                start_date_tz = start_date.replace(tzinfo=timezone.utc) if start_date.tzinfo is None else start_date
                end_date_tz = end_date.replace(tzinfo=timezone.utc) if end_date.tzinfo is None else end_date
                df = df[(df.index >= start_date_tz) & (df.index <= end_date_tz)]
                print(f"   ✂️  {symbol}: Filtered to target period: {len(df)} rows")
                
                # Create target
                df = self._create_target(df)
                
                # Remove NaN (from target creation)
                df_before = len(df)
                df = df.dropna()
                print(f"   🧹 {symbol}: After target dropna: {len(df)} rows (removed {df_before - len(df)})")
                
                if len(df) > 0:
                    all_data.append(df)
                else:
                    print(f"   ⚠️  {symbol}: Skipped - 0 rows after processing")
        
        finally:
            await conn.close()
        
        if not all_data:
            return None
        
        result = pd.concat(all_data, ignore_index=True)
        print(f"   ✅ Combined: {len(result)} total rows from {len(all_data)} symbols")
        
        return result
    
    def _create_target(
        self,
        df: pd.DataFrame,
        forward_periods: int = 5,
        profit_threshold: float = 0.02
    ) -> pd.DataFrame:
        """Cria variável target binária"""
        
        # Calcular retorno futuro
        df['future_high'] = df['high'].shift(-forward_periods).rolling(forward_periods).max()
        df['future_low'] = df['low'].shift(-forward_periods).rolling(forward_periods).min()
        
        # Calcular potencial de lucro
        df['max_profit'] = (df['future_high'] - df['close']) / df['close']
        df['max_loss'] = (df['close'] - df['future_low']) / df['close']
        
        # Target: 1 se lucro > threshold e loss < threshold/2
        df['target'] = (
            (df['max_profit'] > profit_threshold) & 
            (df['max_loss'] < profit_threshold / 2)
        ).astype(int)
        
        # Remove colunas auxiliares
        df = df.drop(['future_high', 'future_low', 'max_profit', 'max_loss'], axis=1)
        
        return df
    
    def _calculate_trading_metrics(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        initial_capital: float = 100000
    ) -> Dict[str, float]:
        """Calcula métricas de trading simuladas"""
        
        # Simular trades
        capital = initial_capital
        equity_curve = [capital]
        trades = []
        
        for i in range(len(y_pred)):
            if y_pred[i] == 1:  # Sinal de compra
                # Simular resultado do trade
                if y_true[i] == 1:  # Win
                    profit = 0.02  # 2% profit
                else:  # Loss
                    profit = -0.01  # 1% loss (stop)
                
                capital *= (1 + profit)
                equity_curve.append(capital)
                trades.append({'win': y_true[i] == 1, 'return': profit})
        
        # Calcular métricas
        if len(trades) == 0:
            return {
                'trades': 0,
                'win_rate': 0.0,
                'sharpe_ratio': 0.0,
                'max_drawdown': 0.0,
                'total_return': 0.0
            }
        
        wins = sum(1 for t in trades if t['win'])
        win_rate = wins / len(trades)
        
        # Sharpe Ratio
        returns = [t['return'] for t in trades]
        if len(returns) > 1 and np.std(returns) > 0:
            sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252)
        else:
            sharpe = 0.0
        
        # Max Drawdown
        peak = equity_curve[0]
        max_dd = 0.0
        for value in equity_curve:
            if value > peak:
                peak = value
            dd = (peak - value) / peak
            if dd > max_dd:
                max_dd = dd
        
        # Total Return
        total_return = (capital - initial_capital) / initial_capital
        
        return {
            'trades': len(trades),
            'win_rate': win_rate,
            'sharpe_ratio': sharpe,
            'max_drawdown': max_dd,
            'total_return': total_return
        }
    
    async def run_walk_forward(
        self,
        symbols: List[str],
        start_date: datetime,
        end_date: datetime,
        model_type: str = 'random_forest',
        use_smote: bool = True
    ) -> WalkForwardResults:
        """
        Executa Walk-Forward Optimization
        
        Args:
            symbols: Lista de símbolos
            start_date: Data inicial
            end_date: Data final
            model_type: 'random_forest' ou 'xgboost'
            use_smote: Se True, aplica SMOTE
        
        Returns:
            WalkForwardResults com métricas consolidadas
        """
        print(f"\n{'='*70}")
        print(f"🔄 WALK-FORWARD OPTIMIZATION - PASSO 13")
        print(f"{'='*70}")
        print(f"📊 Symbols: {', '.join(symbols)}")
        print(f"📅 Period: {start_date.date()} → {end_date.date()}")
        print(f"🤖 Model: {model_type}")
        print(f"⚖️  SMOTE: {'Enabled' if use_smote else 'Disabled'}")
        print(f"📁 Folds: {self.folds} (Train: {self.train_months}mo, Test: {self.test_months}mo)")
        print(f"{'='*70}\n")
        
        # Split timeline
        folds_data = self._split_timeline(start_date, end_date)
        
        if len(folds_data) == 0:
            raise ValueError("Insufficient data for walk-forward optimization")
        
        print(f"✅ Created {len(folds_data)} folds\n")
        
        # Process each fold
        for fold_info in folds_data:
            fold_id = fold_info['fold_id']
            
            print(f"{'─'*70}")
            print(f"📊 FOLD {fold_id}/{len(folds_data)}")
            print(f"{'─'*70}")
            print(f"  Train: {fold_info['train_start'].date()} → {fold_info['train_end'].date()}")
            print(f"  Test:  {fold_info['test_start'].date()} → {fold_info['test_end'].date()}")
            
            # Fetch training data
            print(f"\n  📥 Fetching training data...")
            df_train = await self._fetch_data_window(
                symbols,
                fold_info['train_start'],
                fold_info['train_end']
            )
            
            if df_train is None or len(df_train) < 30:
                print(f"  ⚠️  Insufficient training data ({len(df_train) if df_train is not None else 0} samples), skipping fold {fold_id}")
                continue
            
            # Fetch test data
            print(f"  📥 Fetching test data...")
            df_test = await self._fetch_data_window(
                symbols,
                fold_info['test_start'],
                fold_info['test_end']
            )
            
            if df_test is None or len(df_test) < 5:
                print(f"  ⚠️  Insufficient test data ({len(df_test) if df_test is not None else 0} samples), skipping fold {fold_id}")
                continue
            
            print(f"  ✅ Train samples: {len(df_train)}")
            print(f"  ✅ Test samples: {len(df_test)}")
            
            # Separate features and target
            feature_cols = self.feature_engineer.feature_list
            
            X_train = df_train[feature_cols]
            y_train = df_train['target']
            X_test = df_test[feature_cols]
            y_test = df_test['target']
            
            print(f"\n  🎯 Train target balance: {y_train.mean():.2%} positive")
            
            # Apply SMOTE
            if use_smote and len(np.unique(y_train)) > 1:
                print(f"  ⚖️  Applying SMOTE...")
                smote = SMOTE(random_state=42)
                X_train, y_train = smote.fit_resample(X_train, y_train)
                print(f"     After SMOTE: {len(X_train)} samples")
            
            # Train model
            print(f"\n  🤖 Training {model_type}...")
            
            if model_type == 'random_forest':
                model = RandomForestClassifier(
                    n_estimators=200,
                    max_depth=15,
                    min_samples_split=20,
                    min_samples_leaf=10,
                    max_features='sqrt',
                    class_weight='balanced',
                    random_state=42,
                    n_jobs=-1
                )
            elif model_type == 'xgboost':
                scale_pos_weight = len(y_train[y_train == 0]) / len(y_train[y_train == 1])
                model = xgb.XGBClassifier(
                    n_estimators=200,
                    max_depth=6,
                    learning_rate=0.05,
                    subsample=0.8,
                    colsample_bytree=0.8,
                    scale_pos_weight=scale_pos_weight,
                    random_state=42,
                    n_jobs=-1
                )
            
            model.fit(X_train, y_train)
            
            # Predict on test set
            y_pred = model.predict(X_test)
            y_pred_proba = model.predict_proba(X_test)[:, 1]
            
            # Calculate metrics
            metrics = {
                'accuracy': accuracy_score(y_test, y_pred),
                'precision': precision_score(y_test, y_pred, zero_division=0),
                'recall': recall_score(y_test, y_pred, zero_division=0),
                'f1': f1_score(y_test, y_pred, zero_division=0),
                'roc_auc': roc_auc_score(y_test, y_pred_proba) if len(np.unique(y_test)) > 1 else 0.0
            }
            
            # Calculate trading metrics
            trading_metrics = self._calculate_trading_metrics(
                y_test.values,
                y_pred
            )
            
            # Store fold metrics
            fold_metrics = FoldMetrics(
                fold_id=fold_id,
                train_start=fold_info['train_start'].strftime('%Y-%m-%d'),
                train_end=fold_info['train_end'].strftime('%Y-%m-%d'),
                test_start=fold_info['test_start'].strftime('%Y-%m-%d'),
                test_end=fold_info['test_end'].strftime('%Y-%m-%d'),
                train_samples=len(df_train),
                test_samples=len(df_test),
                accuracy=metrics['accuracy'],
                precision=metrics['precision'],
                recall=metrics['recall'],
                f1_score=metrics['f1'],
                roc_auc=metrics['roc_auc'],
                trades=trading_metrics['trades'],
                win_rate=trading_metrics['win_rate'],
                sharpe_ratio=trading_metrics['sharpe_ratio'],
                max_drawdown=trading_metrics['max_drawdown'],
                total_return=trading_metrics['total_return']
            )
            
            self.fold_results.append(fold_metrics)
            self.models[fold_id] = model
            
            # Print fold results
            print(f"\n  📊 FOLD {fold_id} RESULTS:")
            print(f"     Accuracy:  {metrics['accuracy']:.4f}")
            print(f"     Precision: {metrics['precision']:.4f}")
            print(f"     Recall:    {metrics['recall']:.4f}")
            print(f"     F1-Score:  {metrics['f1']:.4f}")
            print(f"     ROC-AUC:   {metrics['roc_auc']:.4f}")
            print(f"\n  💰 TRADING METRICS:")
            print(f"     Trades:     {trading_metrics['trades']}")
            print(f"     Win Rate:   {trading_metrics['win_rate']:.2%}")
            print(f"     Sharpe:     {trading_metrics['sharpe_ratio']:.2f}")
            print(f"     Max DD:     {trading_metrics['max_drawdown']:.2%}")
            print(f"     Return:     {trading_metrics['total_return']:.2%}")
            print()
        
        # Consolidate results
        results = self._consolidate_results()
        
        # Print summary
        self._print_summary(results)
        
        return results
    
    def _consolidate_results(self) -> WalkForwardResults:
        """Consolida resultados de todos os folds"""
        
        if not self.fold_results:
            raise ValueError("No fold results available")
        
        accuracies = [f.accuracy for f in self.fold_results]
        roc_aucs = [f.roc_auc for f in self.fold_results]
        win_rates = [f.win_rate for f in self.fold_results]
        sharpes = [f.sharpe_ratio for f in self.fold_results]
        
        # Consistency score: 1 - CV (coeficiente de variação)
        cv_accuracy = np.std(accuracies) / np.mean(accuracies) if np.mean(accuracies) > 0 else 1
        consistency_score = max(0, 1 - cv_accuracy)
        
        return WalkForwardResults(
            folds=self.fold_results,
            avg_accuracy=np.mean(accuracies),
            avg_roc_auc=np.mean(roc_aucs),
            avg_win_rate=np.mean(win_rates),
            avg_sharpe=np.mean(sharpes),
            std_accuracy=np.std(accuracies),
            std_roc_auc=np.std(roc_aucs),
            consistency_score=consistency_score,
            total_trades=sum(f.trades for f in self.fold_results),
            overall_return=sum(f.total_return for f in self.fold_results)
        )
    
    def _print_summary(self, results: WalkForwardResults):
        """Imprime resumo dos resultados"""
        
        print(f"\n{'='*70}")
        print(f"📊 WALK-FORWARD SUMMARY")
        print(f"{'='*70}")
        print(f"\n🎯 ML METRICS (Average across {len(results.folds)} folds):")
        print(f"   Accuracy:     {results.avg_accuracy:.4f} ± {results.std_accuracy:.4f}")
        print(f"   ROC-AUC:      {results.avg_roc_auc:.4f} ± {results.std_roc_auc:.4f}")
        print(f"   Consistency:  {results.consistency_score:.4f} (1.0 = perfect)")
        
        print(f"\n💰 TRADING METRICS:")
        print(f"   Avg Win Rate: {results.avg_win_rate:.2%}")
        print(f"   Avg Sharpe:   {results.avg_sharpe:.2f}")
        print(f"   Total Trades: {results.total_trades}")
        print(f"   Overall Return: {results.overall_return:.2%}")
        
        print(f"\n📈 PERFORMANCE BY FOLD:")
        print(f"   {'Fold':<6} {'Accuracy':<10} {'ROC-AUC':<10} {'Win Rate':<10} {'Sharpe':<8} {'Return':<10}")
        print(f"   {'-'*64}")
        for fold in results.folds:
            print(f"   {fold.fold_id:<6} {fold.accuracy:<10.4f} {fold.roc_auc:<10.4f} "
                  f"{fold.win_rate:<10.2%} {fold.sharpe_ratio:<8.2f} {fold.total_return:<10.2%}")
        
        print(f"\n{'='*70}")
        
        # Interpretação
        print(f"\n💡 INTERPRETATION:")
        if results.avg_accuracy > 0.75:
            print(f"   ✅ Excellent accuracy across folds!")
        elif results.avg_accuracy > 0.65:
            print(f"   ✅ Good accuracy, model is reliable")
        else:
            print(f"   ⚠️  Low accuracy, consider feature engineering")
        
        if results.consistency_score > 0.9:
            print(f"   ✅ High consistency - model is stable over time")
        elif results.consistency_score > 0.8:
            print(f"   ✅ Good consistency")
        else:
            print(f"   ⚠️  Low consistency - performance varies significantly")
        
        if results.avg_sharpe > 1.5:
            print(f"   ✅ Excellent Sharpe Ratio - strong risk-adjusted returns")
        elif results.avg_sharpe > 1.0:
            print(f"   ✅ Good Sharpe Ratio")
        else:
            print(f"   ⚠️  Low Sharpe Ratio - returns not compensating risk")
        
        print(f"\n{'='*70}\n")
    
    def save_results(self, path: str = '/app/models/walk_forward_results.json'):
        """Salva resultados em JSON"""
        
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        
        results = self._consolidate_results()
        
        results_dict = {
            'folds': [asdict(f) for f in results.folds],
            'summary': {
                'avg_accuracy': results.avg_accuracy,
                'avg_roc_auc': results.avg_roc_auc,
                'avg_win_rate': results.avg_win_rate,
                'avg_sharpe': results.avg_sharpe,
                'std_accuracy': results.std_accuracy,
                'std_roc_auc': results.std_roc_auc,
                'consistency_score': results.consistency_score,
                'total_trades': results.total_trades,
                'overall_return': results.overall_return
            },
            'config': {
                'folds': self.folds,
                'train_months': self.train_months,
                'test_months': self.test_months
            },
            'timestamp': datetime.now().isoformat()
        }
        
        with open(path, 'w') as f:
            json.dump(results_dict, f, indent=2)
        
        print(f"💾 Results saved: {path}")


async def main():
    """CLI para Walk-Forward Optimization"""
    import argparse
    
    parser = argparse.ArgumentParser(description='PASSO 13: Walk-Forward Optimization para ML')
    parser.add_argument('--symbols', nargs='+', default=['ITUB4', 'MGLU3', 'VALE3', 'PETR4'],
                        help='Symbols for walk-forward')
    parser.add_argument('--folds', type=int, default=4, help='Number of folds')
    parser.add_argument('--train-months', type=int, default=3, help='Training window in months')
    parser.add_argument('--test-months', type=int, default=1, help='Test window in months')
    parser.add_argument('--model-type', choices=['random_forest', 'xgboost'], 
                        default='random_forest', help='Model type')
    parser.add_argument('--no-smote', action='store_true', help='Disable SMOTE')
    parser.add_argument('--start-date', type=str, default='2025-01-01', 
                        help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str, default='2025-12-30',
                        help='End date (YYYY-MM-DD)')
    parser.add_argument('--table', choices=['ohlcv_daily', 'crypto_ohlcv_1h'],
                        default='ohlcv_daily', help='Data table (daily stocks or hourly crypto)')
    
    args = parser.parse_args()
    
    db_config = {
        'host': 'timescaledb',
        'port': 5432,
        'database': 'b3trading_market',
        'user': 'b3trading_ts',
        'password': 'b3trading_ts_pass'
    }
    
    optimizer = MLWalkForward(
        db_config=db_config,
        folds=args.folds,
        train_months=args.train_months,
        test_months=args.test_months,
        table_name=args.table
    )
    
    start_date = datetime.strptime(args.start_date, '%Y-%m-%d')
    end_date = datetime.strptime(args.end_date, '%Y-%m-%d')
    
    results = await optimizer.run_walk_forward(
        symbols=args.symbols,
        start_date=start_date,
        end_date=end_date,
        model_type=args.model_type,
        use_smote=not args.no_smote
    )
    
    # Save results
    optimizer.save_results()
    
    print(f"\n✅ Walk-Forward Optimization complete!")


if __name__ == '__main__':
    asyncio.run(main())
