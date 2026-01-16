#!/usr/bin/env python3
"""
ML Training and Testing Script
================================

Trains ML models on historical data and evaluates performance.
Integrates feature engineering with Wave3 Daily strategy.

Usage:
    python train_ml_model.py --symbols ITUB4,MGLU3,VALE3 --model-type random_forest

Author: B3 Trading Platform
Date: 15 de Janeiro de 2026
"""

import asyncio
import asyncpg
import pandas as pd
import numpy as np
from typing import List, Dict, Tuple
from datetime import datetime, timedelta
import argparse
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

# Import directly to avoid __init__.py issues
from feature_engineering import FeatureEngineer, create_target_variable
from signal_classifier import SignalClassifier


async def fetch_historical_data(db_config: dict, symbol: str, days_back: int = 730) -> pd.DataFrame:
    """Fetch historical data from TimescaleDB"""
    
    conn = await asyncpg.connect(**db_config)
    
    try:
        # Query daily data
        query = """
            SELECT 
                time as timestamp,
                symbol,
                open::float,
                high::float,
                low::float,
                close::float,
                volume::float
            FROM ohlcv_1d
            WHERE symbol = $1
            ORDER BY time ASC
        """
        
        rows = await conn.fetch(query, symbol)
        
        if not rows:
            print(f"   ⚠️  No data found for {symbol}")
            return None
        
        df = pd.DataFrame(rows, columns=['timestamp', 'symbol', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.set_index('timestamp')
        
        print(f"   ✅ {symbol}: {len(df)} bars ({df.index.min().date()} → {df.index.max().date()})")
        
        return df
        
    finally:
        await conn.close()


async def train_ml_model(
    symbols: List[str],
    db_config: dict,
    model_type: str = 'random_forest',
    profit_threshold: float = 0.02,
    forward_periods: int = 5,
    test_size: float = 0.2
):
    """
    Train ML model on historical data
    
    Args:
        symbols: List of symbols to train on
        db_config: Database configuration
        model_type: 'random_forest' or 'xgboost'
        profit_threshold: Minimum profit to label as successful trade
        forward_periods: Look-forward period for calculating returns
        test_size: Proportion of test set
    """
    
    print("="*70)
    print("🎓 ML MODEL TRAINING - B3 Trading Platform")
    print("="*70)
    print(f"📊 Symbols: {', '.join(symbols)}")
    print(f"🤖 Model: {model_type}")
    print(f"🎯 Profit threshold: {profit_threshold*100}%")
    print(f"📅 Forward periods: {forward_periods}")
    print("="*70)
    
    # Initialize feature engineer
    fe = FeatureEngineer()
    
    # Collect data for all symbols
    all_data = []
    
    print(f"\n📥 Fetching historical data...")
    for symbol in symbols:
        df = await fetch_historical_data(db_config, symbol)
        if df is not None and len(df) > 200:  # Minimum bars for features
            all_data.append(df)
    
    if not all_data:
        print("❌ No data available for training")
        return None
    
    # Combine all symbols
    combined_df = pd.concat(all_data)
    print(f"\n📊 Combined dataset: {len(combined_df)} total bars")
    
    # Generate features
    print(f"\n🔬 Generating technical features...")
    df_with_features = fe.generate_all_features(combined_df)
    
    # Create target variable
    print(f"\n🎯 Creating target variable...")
    df_with_target = create_target_variable(
        df_with_features,
        forward_periods=forward_periods,
        profit_threshold=profit_threshold
    )
    
    # Remove NaN rows
    df_clean = df_with_target.dropna()
    
    print(f"\n📊 Dataset after cleaning:")
    print(f"   Total samples: {len(df_clean)}")
    print(f"   Profitable trades: {df_clean['target'].sum()} ({df_clean['target'].mean()*100:.1f}%)")
    print(f"   Non-profitable: {len(df_clean) - df_clean['target'].sum()} ({(1-df_clean['target'].mean())*100:.1f}%)")
    
    if len(df_clean) < 100:
        print("❌ Insufficient data for training (need at least 100 samples)")
        return None
    
    # Initialize classifier
    print(f"\n🤖 Initializing {model_type} classifier...")
    
    if model_type == 'random_forest':
        classifier = SignalClassifier(
            model_type='random_forest',
            n_estimators=200,
            max_depth=10,
            random_state=42
        )
    elif model_type == 'xgboost':
        classifier = SignalClassifier(
            model_type='xgboost',
            n_estimators=200,
            max_depth=6,
            random_state=42
        )
    else:
        print(f"❌ Unknown model type: {model_type}")
        return None
    
    # Prepare features
    exclude_cols = ['open', 'high', 'low', 'close', 'volume', 'symbol',
                   'target', 'forward_return', 'regime_trend', 
                   'volatility_regime', 'volume_regime']
    
    feature_cols = [col for col in df_clean.columns 
                   if col not in exclude_cols and df_clean[col].dtype in [np.float64, np.int64, bool]]
    
    # Convert boolean to int
    for col in feature_cols:
        if df_clean[col].dtype == bool:
            df_clean[col] = df_clean[col].astype(int)
    
    X = df_clean[feature_cols]
    y = df_clean['target']
    
    # Split data (time series: no shuffle)
    split_idx = int(len(X) * (1 - test_size))
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]
    
    print(f"\n📊 Train/Test split:")
    print(f"   Training: {len(X_train)} samples")
    print(f"   Test: {len(X_test)} samples")
    print(f"   Features: {len(feature_cols)}")
    
    # Train model (don't split again since we already split manually)
    print(f"\n🎓 Training model...")
    train_metrics = classifier.train(X_train, y_train, test_size=0.2, cross_validation=True)
    
    # Evaluate on test set
    print(f"\n📊 Evaluating on test set...")
    y_test_pred = classifier.predict(X_test)
    y_test_proba = classifier.predict_proba(X_test)
    
    from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score
    
    test_accuracy = accuracy_score(y_test, y_test_pred)
    test_precision = precision_score(y_test, y_test_pred, zero_division=0)
    test_recall = recall_score(y_test, y_test_pred, zero_division=0)
    test_f1 = f1_score(y_test, y_test_pred, zero_division=0)
    test_roc_auc = roc_auc_score(y_test, y_test_proba[:, 1]) if y_test_proba.shape[1] == 2 else 0.0
    
    print(f"\n✅ Test Results:")
    print(f"   Accuracy: {test_accuracy:.4f}")
    print(f"   Precision: {test_precision:.4f}")
    print(f"   Recall: {test_recall:.4f}")
    print(f"   F1 Score: {test_f1:.4f}")
    print(f"   ROC-AUC: {test_roc_auc:.4f}")
    
    # Feature importance
    print(f"\n🎯 Top 20 Most Important Features:")
    importance_dict = classifier.get_feature_importance(top_n=20)
    for i, (feat, imp) in enumerate(importance_dict.items(), 1):
        print(f"   {i:2d}. {feat:30s} {imp:.4f}")
    
    # Save model
    model_dir = '/tmp/ml_models'
    Path(model_dir).mkdir(parents=True, exist_ok=True)
    
    print(f"\n💾 Saving model...")
    model_name = f"rf_model_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pkl"
    model_path = Path(model_dir) / model_name
    classifier.save_model(str(model_path))
    print(f"   Saved to: {model_path}")
    
    # Summary
    print(f"\n{'='*70}")
    print(f"🎉 TRAINING COMPLETE")
    print(f"{'='*70}")
    print(f"   Model: {model_type}")
    print(f"   Test Accuracy: {test_accuracy:.4f}")
    print(f"   Test Precision: {test_precision:.4f}")
    print(f"   Test Recall: {test_recall:.4f}")
    print(f"   Test F1: {test_f1:.4f}")
    print(f"   Test ROC-AUC: {test_roc_auc:.4f}")
    print(f"   Model saved: {model_path}")
    print(f"{'='*70}")
    
    return {
        'classifier': classifier,
        'test_accuracy': test_accuracy,
        'test_precision': test_precision,
        'test_recall': test_recall,
        'test_f1': test_f1,
        'test_roc_auc': test_roc_auc,
        'model_path': str(model_path),
        'feature_cols': feature_cols
    }

async def test_ml_predictions(
    symbol: str,
    db_config: dict,
    model_path: str
):
    """
    Test ML model predictions on recent data
    
    Args:
        symbol: Symbol to test
        db_config: Database configuration
        model_path: Path to saved model
    """
    
    print(f"\n{'='*70}")
    print(f"🧪 TESTING ML PREDICTIONS - {symbol}")
    print(f"{'='*70}")
    
    # Load model
    print(f"📂 Loading model...")
    classifier = SignalClassifier()
    classifier.load_model(model_path)
    print(f"   ✅ Model loaded: {classifier.model_type}")
    
    # Fetch recent data
    print(f"\n📥 Fetching recent data for {symbol}...")
    df = await fetch_historical_data(db_config, symbol, days_back=180)
    
    if df is None or len(df) < 100:
        print(f"❌ Insufficient data for {symbol}")
        return
    
    # Generate features
    print(f"🔬 Generating features...")
    fe = FeatureEngineer()
    df_with_features = fe.generate_all_features(df)
    df_clean = df_with_features.dropna()
    
    # Prepare features
    X = df_clean[classifier.feature_names].values
    
    # Convert boolean to int
    for i, col in enumerate(classifier.feature_names):
        if df_clean[col].dtype == bool:
            X[:, i] = df_clean[col].astype(int).values
    
    # Predict
    print(f"🤖 Making predictions...")
    predictions = classifier.predict(X)
    probabilities = classifier.predict_proba(X)[:, 1]
    
    # Add to dataframe
    df_clean['ml_signal'] = predictions
    df_clean['ml_probability'] = probabilities
    df_clean['ml_confidence'] = np.abs(probabilities - 0.5) * 2
    
    # Filter high-confidence signals
    high_conf_signals = df_clean[
        (df_clean['ml_signal'] == 1) & 
        (df_clean['ml_confidence'] > 0.6)
    ]
    
    print(f"\n📊 Prediction Results:")
    print(f"   Total bars analyzed: {len(df_clean)}")
    print(f"   Positive signals (ML=1): {predictions.sum()}")
    print(f"   High confidence signals (>0.6): {len(high_conf_signals)}")
    print(f"   Average probability: {probabilities.mean():.3f}")
    
    if len(high_conf_signals) > 0:
        print(f"\n🎯 High Confidence Trading Signals:")
        print(high_conf_signals[['close', 'ml_probability', 'ml_confidence']].tail(10).to_string())
    
    print(f"{'='*70}")


async def main():
    parser = argparse.ArgumentParser(
        description='Train ML model for trading signal classification'
    )
    
    parser.add_argument('--symbols', required=True, 
                       help='Comma-separated symbols (e.g., ITUB4,MGLU3,VALE3)')
    parser.add_argument('--model-type', default='random_forest',
                       choices=['random_forest', 'xgboost'],
                       help='ML model type')
    parser.add_argument('--profit-threshold', type=float, default=0.02,
                       help='Minimum profit threshold (default: 0.02 = 2%%)')
    parser.add_argument('--forward-periods', type=int, default=5,
                       help='Look-forward periods (default: 5)')
    parser.add_argument('--test-size', type=float, default=0.2,
                       help='Test set proportion (default: 0.2)')
    parser.add_argument('--db-host', default='timescaledb')
    parser.add_argument('--db-port', type=int, default=5432)
    parser.add_argument('--db-name', default='b3trading_market')
    parser.add_argument('--db-user', default='b3trading_ts')
    parser.add_argument('--db-password', default='b3trading_ts_pass')
    
    args = parser.parse_args()
    
    # Parse symbols
    symbols = [s.strip().upper() for s in args.symbols.split(',')]
    
    # Database config
    db_config = {
        'host': args.db_host,
        'port': args.db_port,
        'database': args.db_name,
        'user': args.db_user,
        'password': args.db_password
    }
    
    # Train model
    result = await train_ml_model(
        symbols=symbols,
        db_config=db_config,
        model_type=args.model_type,
        profit_threshold=args.profit_threshold,
        forward_periods=args.forward_periods,
        test_size=args.test_size
    )
    
    if result is None:
        print("❌ Training failed")
        return
    
    # Test predictions on first symbol
    if len(symbols) > 0:
        await test_ml_predictions(
            symbol=symbols[0],
            db_config=db_config,
            model_path=result['model_path']
        )


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
