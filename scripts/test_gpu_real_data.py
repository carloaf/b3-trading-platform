#!/usr/bin/env python3
"""
Teste de GPU com dados REAIS do TimescaleDB
Compara performance CPU vs GPU para treinamento ML Wave3

Dados: 775.259 registros (58 símbolos × 3 anos)
- ohlcv_15min: ~338.847 registros
- ohlcv_60min: ~230.000 registros
- ohlcv_daily: ~28.942 registros
"""
import os
import sys
import time
import asyncio
import numpy as np
import pandas as pd
from loguru import logger

# Configuração de logging
logger.remove()
logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}")


async def load_data_from_timescale():
    """Carrega dados reais do TimescaleDB"""
    import asyncpg
    
    logger.info("Conectando ao TimescaleDB...")
    
    conn = await asyncpg.connect(
        host=os.getenv('TIMESCALE_HOST', 'timescaledb'),
        port=int(os.getenv('TIMESCALE_PORT', 5432)),
        database=os.getenv('TIMESCALE_DB', 'b3trading_market'),
        user=os.getenv('TIMESCALE_USER', 'b3trading_ts'),
        password=os.getenv('TIMESCALE_PASSWORD', 'b3trading_ts_pass')
    )
    
    # Verificar total de registros
    stats = await conn.fetch("""
        SELECT 'ohlcv_15min' as tabela, COUNT(*) as total FROM ohlcv_15min
        UNION ALL
        SELECT 'ohlcv_60min', COUNT(*) FROM ohlcv_60min
        UNION ALL
        SELECT 'ohlcv_daily', COUNT(*) FROM ohlcv_daily
    """)
    
    logger.info("📊 Estatísticas do TimescaleDB:")
    total_records = 0
    for row in stats:
        logger.info(f"   {row['tabela']}: {row['total']:,} registros")
        total_records += row['total']
    logger.info(f"   TOTAL: {total_records:,} registros")
    
    # Carregar dados de 15min para TODOS os símbolos (dataset grande para GPU)
    logger.info("\n📥 Carregando dados 15min (TODOS os símbolos para benchmark GPU)...")
    
    rows = await conn.fetch("""
        SELECT symbol, time, open, high, low, close, volume
        FROM ohlcv_15min
        WHERE symbol IN (
            'PETR4', 'VALE3', 'ITUB4', 'BBDC4', 'ABEV3',
            'WEGE3', 'GGBR4', 'CSNA3', 'BBAS3', 'B3SA3',
            'RENT3', 'RADL3', 'SUZB3', 'USIM5', 'EMBR3',
            'MGLU3', 'SBSP3', 'BPAC11', 'PRIO3', 'CSAN3'
        )
        ORDER BY symbol, time
    """)
    
    await conn.close()
    
    # Converter para DataFrame
    df = pd.DataFrame([dict(r) for r in rows])
    logger.info(f"✅ Carregados {len(df):,} registros de 60min")
    
    return df


def calculate_features(df: pd.DataFrame) -> pd.DataFrame:
    """Calcula features técnicas para ML (simplificado)"""
    logger.info("🔧 Calculando features técnicas...")
    
    features_list = []
    
    for symbol in df['symbol'].unique():
        symbol_df = df[df['symbol'] == symbol].copy()
        symbol_df = symbol_df.sort_values('time').reset_index(drop=True)
        
        # Preços
        close = symbol_df['close'].astype(float).values
        high = symbol_df['high'].astype(float).values
        low = symbol_df['low'].astype(float).values
        volume = symbol_df['volume'].astype(float).values
        
        n = len(close)
        logger.info(f"   {symbol}: {n} registros")
        
        if n < 250:
            logger.warning(f"   ⚠️ {symbol} ignorado (< 250 registros)")
            continue
        
        # EMAs
        def ema(arr, period):
            result = np.full(n, np.nan)
            if period >= n:
                return result
            alpha = 2 / (period + 1)
            result[period-1] = np.mean(arr[:period])
            for i in range(period, n):
                result[i] = alpha * arr[i] + (1 - alpha) * result[i-1]
            return result
        
        ema_9 = ema(close, 9)
        ema_21 = ema(close, 21)
        ema_50 = ema(close, 50)
        ema_200 = ema(close, 200)
        
        # RSI
        def rsi(arr, period=14):
            result = np.full(n, np.nan)
            deltas = np.diff(arr)
            for i in range(period, n):
                gains = deltas[i-period:i]
                ups = np.sum(gains[gains > 0]) / period
                downs = -np.sum(gains[gains < 0]) / period
                if downs == 0:
                    result[i] = 100
                elif ups == 0:
                    result[i] = 0
                else:
                    result[i] = 100 - (100 / (1 + ups / downs))
            return result
        
        rsi_14 = rsi(close, 14)
        
        # ATR
        def atr(high, low, close, period=14):
            result = np.full(n, np.nan)
            tr = np.zeros(n)
            tr[0] = high[0] - low[0]
            for i in range(1, n):
                tr[i] = max(high[i] - low[i], 
                           abs(high[i] - close[i-1]),
                           abs(low[i] - close[i-1]))
            for i in range(period, n):
                result[i] = np.mean(tr[i-period:i])
            return result
        
        atr_14 = atr(high, low, close, 14)
        
        # MACD
        ema_12 = ema(close, 12)
        ema_26 = ema(close, 26)
        macd = ema_12 - ema_26
        
        # Bollinger Bands
        bb_middle = np.full(n, np.nan)
        bb_upper = np.full(n, np.nan)
        bb_lower = np.full(n, np.nan)
        for i in range(20, n):
            bb_middle[i] = np.mean(close[i-20:i])
            std = np.std(close[i-20:i])
            bb_upper[i] = bb_middle[i] + 2 * std
            bb_lower[i] = bb_middle[i] - 2 * std
        
        bb_width = np.where(bb_middle > 0, (bb_upper - bb_lower) / bb_middle, np.nan)
        bb_position = np.where((bb_upper - bb_lower) > 0, 
                              (close - bb_lower) / (bb_upper - bb_lower), 
                              np.nan)
        
        # Volume features
        vol_sma_20 = np.full(n, np.nan)
        for i in range(20, n):
            vol_sma_20[i] = np.mean(volume[i-20:i])
        vol_ratio = np.where(vol_sma_20 > 0, volume / vol_sma_20, np.nan)
        
        # Returns
        returns = np.zeros(n)
        returns[1:] = (close[1:] - close[:-1]) / close[:-1]
        
        # Volatilidade
        volatility_20 = np.full(n, np.nan)
        for i in range(20, n):
            volatility_20[i] = np.std(returns[i-20:i])
        
        # Target: retorno futuro > 0 (classificação binária)
        target = np.zeros(n)
        for i in range(n - 5):
            target[i] = 1 if close[i + 5] > close[i] else 0
        
        # Criar DataFrame de features
        symbol_features = pd.DataFrame({
            'symbol': symbol,
            'time': symbol_df['time'].values,
            'close': close,
            'ema_9': ema_9,
            'ema_21': ema_21,
            'ema_50': ema_50,
            'ema_200': ema_200,
            'ema_ratio_9_21': np.where(ema_21 != 0, ema_9 / ema_21, np.nan),
            'ema_ratio_21_50': np.where(ema_50 != 0, ema_21 / ema_50, np.nan),
            'ema_dist_200': np.where(ema_200 != 0, (close - ema_200) / ema_200, np.nan),
            'rsi_14': rsi_14,
            'atr_14': atr_14,
            'atr_pct': np.where(close != 0, atr_14 / close, np.nan),
            'macd': macd,
            'bb_width': bb_width,
            'bb_position': bb_position,
            'vol_ratio': vol_ratio,
            'volatility_20': volatility_20,
            'returns': returns,
            'target': target
        })
        
        features_list.append(symbol_features)
    
    if not features_list:
        logger.error("❌ Nenhum dado processado!")
        return pd.DataFrame()
    
    all_features = pd.concat(features_list, ignore_index=True)
    
    # Remover NaNs (warm-up period de 200 candles)
    initial_count = len(all_features)
    all_features = all_features.dropna()
    final_count = len(all_features)
    
    # Remover últimos 5 registros de cada símbolo (target inválido)
    all_features = all_features.groupby('symbol').apply(
        lambda x: x.iloc[:-5] if len(x) > 5 else x
    ).reset_index(drop=True)
    
    logger.info(f"✅ {len(all_features):,} registros válidos ({len(all_features.columns)-3} features)")
    logger.info(f"   Removidos: {initial_count - final_count:,} registros (warm-up)")
    
    return all_features


def train_xgboost_benchmark(X, y, device='cpu'):
    """Treina XGBoost e retorna tempo"""
    import xgboost as xgb
    
    params = {
        'tree_method': 'hist',
        'device': device,
        'n_estimators': 100,
        'max_depth': 6,
        'learning_rate': 0.1,
        'objective': 'binary:logistic',
        'eval_metric': 'auc',
        'verbosity': 0,
        'random_state': 42
    }
    
    model = xgb.XGBClassifier(**params)
    
    start = time.time()
    model.fit(X, y)
    elapsed = time.time() - start
    
    # Avaliar
    from sklearn.metrics import accuracy_score, roc_auc_score
    y_pred = model.predict(X)
    y_prob = model.predict_proba(X)[:, 1]
    
    acc = accuracy_score(y, y_pred)
    auc = roc_auc_score(y, y_prob)
    
    return elapsed, acc, auc, model


async def main():
    """Executa benchmark completo"""
    print("=" * 60)
    print("🚀 B3 Trading Platform - Benchmark GPU vs CPU")
    print("   Dados REAIS do TimescaleDB (775.259 registros)")
    print("=" * 60)
    
    # 1. Carregar dados
    df = await load_data_from_timescale()
    
    # 2. Calcular features
    features_df = calculate_features(df)
    
    # 3. Preparar X, y
    feature_cols = [c for c in features_df.columns if c not in ['symbol', 'time', 'close', 'target']]
    X = features_df[feature_cols].values
    y = features_df['target'].values
    
    logger.info(f"\n📊 Dataset final: {X.shape[0]:,} amostras × {X.shape[1]} features")
    logger.info(f"   Target balance: {y.mean()*100:.1f}% positivos")
    
    # 4. Benchmark CPU
    print("\n" + "=" * 60)
    logger.info("🖥️  Treinando com CPU...")
    cpu_time, cpu_acc, cpu_auc, _ = train_xgboost_benchmark(X, y, device='cpu')
    logger.info(f"   ⏱️  Tempo: {cpu_time:.2f}s")
    logger.info(f"   📈 Accuracy: {cpu_acc*100:.2f}%")
    logger.info(f"   📈 ROC-AUC: {cpu_auc:.4f}")
    
    # 5. Benchmark GPU
    print("\n" + "=" * 60)
    logger.info("🎮 Treinando com GPU (GTX 960M)...")
    try:
        gpu_time, gpu_acc, gpu_auc, model = train_xgboost_benchmark(X, y, device='cuda')
        logger.info(f"   ⏱️  Tempo: {gpu_time:.2f}s")
        logger.info(f"   📈 Accuracy: {gpu_acc*100:.2f}%")
        logger.info(f"   📈 ROC-AUC: {gpu_auc:.4f}")
        
        # Speedup
        speedup = cpu_time / gpu_time
        print("\n" + "=" * 60)
        if speedup > 1:
            logger.success(f"🚀 GPU é {speedup:.2f}x mais RÁPIDA que CPU!")
        else:
            logger.warning(f"⚠️ CPU é {1/speedup:.2f}x mais rápida (dataset pequeno para GPU)")
        
    except Exception as e:
        logger.error(f"❌ Erro GPU: {e}")
        logger.warning("   Usando apenas CPU...")
    
    # 6. Feature Importance
    print("\n" + "=" * 60)
    logger.info("📊 Top 10 Features Mais Importantes:")
    try:
        importance = model.feature_importances_
        indices = np.argsort(importance)[::-1][:10]
        for i, idx in enumerate(indices):
            logger.info(f"   {i+1}. {feature_cols[idx]}: {importance[idx]*100:.2f}%")
    except:
        pass
    
    print("\n" + "=" * 60)
    logger.success("✅ Benchmark concluído!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
