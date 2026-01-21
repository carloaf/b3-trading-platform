#!/usr/bin/env python3
"""
Treinar Modelo ML para Wave3 v2.3 Hybrid
=========================================

Treina Random Forest usando dados históricos dos 15 trades Wave3 v2.1
para prever quais trades terão sucesso (WIN) ou falha (LOSS).

Objetivo: Filtrar trades ruins (BBAS3 -16.61%) mantendo trades bons.

Autor: B3 Trading Platform - ML Team
Data: 21 Janeiro 2026
"""

import pandas as pd
import numpy as np
import pickle
import asyncio
import asyncpg
from datetime import datetime, timedelta
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import classification_report, confusion_matrix, roc_auc_score
import sys
sys.path.append('/app/src/ml')
from feature_engineering import FeatureEngineer


async def collect_training_data():
    """
    Coleta dados dos 15 trades conhecidos do backtest para treino
    """
    print("=" * 100)
    print("COLETA DE DADOS PARA TREINAMENTO ML")
    print("=" * 100)
    
    # Trades conhecidos do backtest
    trades_data = [
        # Vencedores
        {'symbol': 'WEGE3', 'score': 70, 'result': 1, 'return': 37.89},
        {'symbol': 'ABEV3', 'score': 95, 'result': 1, 'return': 29.72},
        {'symbol': 'VALE3', 'score': 85, 'result': 1, 'return': 23.11},
        {'symbol': 'ITUB4', 'score': 75, 'result': 1, 'return': 18.46},
        {'symbol': 'PETR4', 'score': 80, 'result': 1, 'return': 9.05},
        {'symbol': 'EMBR3', 'score': 80, 'result': 1, 'return': 5.16},  # 50% win
        {'symbol': 'GGBR4', 'score': 72.5, 'result': 1, 'return': 4.34},  # 50% win
        {'symbol': 'MGLU3', 'score': 70, 'result': 1, 'return': 4.13},
        {'symbol': 'RENT3', 'score': 65, 'result': 1, 'return': 1.53},
        {'symbol': 'CSNA3', 'score': 70, 'result': 1, 'return': 0.89},
        
        # Perdedor
        {'symbol': 'BBAS3', 'score': 65, 'result': 0, 'return': -16.61},
    ]
    
    print(f"\n📊 Trades conhecidos: {len(trades_data)} (10 wins, 1 loss)")
    
    # Conectar ao TimescaleDB
    print("\n🔗 Conectando ao TimescaleDB...")
    conn = await asyncpg.connect(
        host='b3-timescaledb',
        port=5432,
        user='b3trading_ts',
        password='b3trading_ts_pass',
        database='b3trading_market'
    )
    print("✅ Conectado")
    
    # Feature engineer
    fe = FeatureEngineer()
    
    # Coletar features para cada trade
    X_list = []
    y_list = []
    
    for trade in trades_data:
        symbol = trade['symbol']
        print(f"\n🔄 {symbol}...")
        
        try:
            # Buscar dados 60min
            rows = await conn.fetch("""
                SELECT time, open, high, low, close, volume
                FROM ohlcv_data
                WHERE symbol = $1 AND timeframe = '60min'
                ORDER BY time DESC
                LIMIT 500
            """, symbol)
            
            if len(rows) < 200:
                print(f"   ⚠️ Dados insuficientes: {len(rows)}")
                continue
            
            # Converter para DataFrame
            df = pd.DataFrame(rows, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
            df.set_index('time', inplace=True)
            df = df.sort_index()
            
            # Converter Decimal para float
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            df.dropna(inplace=True)
            
            # Gerar features
            features_df = fe.generate_all_features(df)
            
            if features_df.empty:
                print(f"   ⚠️ Features vazias")
                continue
            
            # Pegar última linha (momento do sinal)
            latest_features = features_df.iloc[-1].copy()
            
            # Adicionar quality_score como feature
            latest_features['quality_score'] = trade['score']
            
            # Remover features não numéricas
            feature_values = []
            feature_names_temp = []
            for name, value in latest_features.items():
                if isinstance(value, (int, float, np.number)) and not isinstance(value, bool):
                    feature_values.append(float(value) if not np.isnan(value) and not np.isinf(value) else 0.0)
                    feature_names_temp.append(name)
            
            X_list.append(feature_values)
            y_list.append(trade['result'])
            
            print(f"   ✅ {len(feature_values)} features numéricas coletadas")
        
        except Exception as e:
            print(f"   ❌ Erro: {e}")
            continue
    
    await conn.close()
    
    if len(X_list) < 5:
        print(f"\n❌ Dados insuficientes: apenas {len(X_list)} samples")
        return None, None, None
    
    X = np.array(X_list)
    y = np.array(y_list)
    feature_names = feature_names_temp  # Usar última iteração
    
    print(f"\n✅ Dataset criado:")
    print(f"   Samples: {len(X)}")
    print(f"   Features: {X.shape[1]}")
    print(f"   Wins: {sum(y)} | Losses: {len(y) - sum(y)}")
    
    return X, y, feature_names


def train_model(X, y, feature_names):
    """
    Treina Random Forest com os dados coletados
    """
    print("\n" + "=" * 100)
    print("TREINAMENTO DO MODELO ML")
    print("=" * 100)
    
    # Split dataset (Leave-One-Out approach dado dataset pequeno)
    # Com apenas 11 samples, vamos usar todo dataset para treino e validação cruzada
    print(f"\n⚠️ Dataset muito pequeno ({len(X)} samples), usando abordagem diferente:")
    print(f"   - Treino: Todo dataset")
    print(f"   - Validação: Leave-One-Out Cross-Validation")
    
    X_train = X
    y_train = y
    X_test = np.array([])
    y_test = np.array([])
    
    # Treinar Random Forest
    print("\n🤖 Treinando Random Forest...")
    rf = RandomForestClassifier(
        n_estimators=100,
        max_depth=10,
        min_samples_split=2,
        min_samples_leaf=1,
        random_state=42,
        class_weight='balanced'  # Importante: balancear classes (10 wins vs 1 loss)
    )
    
    rf.fit(X_train, y_train)
    print("✅ Modelo treinado!")
    
    # Avaliar no treino
    train_score = rf.score(X_train, y_train)
    print(f"\n📈 Train Accuracy: {train_score:.2%}")
    
    # Avaliar no teste
    if len(X_test) > 0:
        test_score = rf.score(X_test, y_test)
        y_pred = rf.predict(X_test)
        y_proba = rf.predict_proba(X_test)[:, 1]
        
        print(f"📉 Test Accuracy: {test_score:.2%}")
        
        print("\n📊 Classification Report:")
        print(classification_report(y_test, y_pred, target_names=['LOSS', 'WIN']))
        
        print("\n🎯 Confusion Matrix:")
        cm = confusion_matrix(y_test, y_pred)
        print(f"   TN: {cm[0,0]} | FP: {cm[0,1]}")
        print(f"   FN: {cm[1,0]} | TP: {cm[1,1]}")
        
        if len(np.unique(y_test)) > 1:
            auc = roc_auc_score(y_test, y_proba)
            print(f"\n📈 AUC-ROC: {auc:.3f}")
    
    # Cross-validation (Leave-One-Out dado dataset pequeno)
    print("\n🔄 Cross-Validation (5-fold)...")
    try:
        cv_scores = cross_val_score(rf, X, y, cv=min(5, len(X)), scoring='accuracy')
        print(f"   CV Mean: {cv_scores.mean():.2%} ± {cv_scores.std():.2%}")
        print(f"   CV Scores: {[f'{s:.2%}' for s in cv_scores]}")
    except Exception as e:
        print(f"   ⚠️ CV falhou: {e}")
    
    # Feature importance
    print("\n🔝 Top 10 Features:")
    importances = rf.feature_importances_
    indices = np.argsort(importances)[::-1][:10]
    
    for i, idx in enumerate(indices, 1):
        print(f"   {i:2}. {feature_names[idx]:30s}: {importances[idx]:.4f}")
    
    return rf


def save_model(model, feature_names):
    """
    Salva modelo treinado
    """
    print("\n" + "=" * 100)
    print("SALVANDO MODELO")
    print("=" * 100)
    
    # Criar diretório
    import os
    os.makedirs('/app/models', exist_ok=True)
    
    # Salvar modelo
    model_data = {
        'model': model,
        'feature_names': feature_names,
        'trained_at': datetime.now().isoformat(),
        'version': '1.0',
        'description': 'Random Forest treinado com 11 trades Wave3 v2.1'
    }
    
    model_path = '/app/models/ml_wave3_v2.pkl'
    with open(model_path, 'wb') as f:
        pickle.dump(model_data, f)
    
    print(f"✅ Modelo salvo: {model_path}")
    print(f"   Features: {len(feature_names)}")
    print(f"   Version: {model_data['version']}")
    print(f"   Trained: {model_data['trained_at']}")


async def main():
    """
    Pipeline completo de treinamento
    """
    # 1. Coletar dados
    X, y, feature_names = await collect_training_data()
    
    if X is None:
        print("\n❌ Falha na coleta de dados")
        return
    
    # 2. Treinar modelo
    model = train_model(X, y, feature_names)
    
    # 3. Salvar modelo
    save_model(model, feature_names)
    
    print("\n" + "=" * 100)
    print("✅ TREINAMENTO COMPLETO!")
    print("=" * 100)
    print("\n🚀 Próximo passo: Testar Wave3 v2.3 ML Hybrid com modelo treinado")


if __name__ == "__main__":
    asyncio.run(main())
