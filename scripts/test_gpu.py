#!/usr/bin/env python3
"""
Teste de GPU para o projeto B3 Trading Platform
Verifica disponibilidade de CUDA e testa XGBoost com GPU
"""
import sys
import time

def test_xgboost_gpu():
    """Testa XGBoost com GPU vs CPU"""
    import xgboost as xgb
    import numpy as np
    
    print(f"XGBoost version: {xgb.__version__}")
    
    # Dados de teste MAIORES para benchmark realista
    np.random.seed(42)
    n_samples = 50000  # 50k amostras
    n_features = 100   # 100 features
    X = np.random.rand(n_samples, n_features)
    y = np.random.randint(0, 2, n_samples)
    print(f"Dataset: {n_samples:,} amostras × {n_features} features")
    
    # Teste GPU
    print("\n=== Testando GPU ===")
    try:
        start = time.time()
        model_gpu = xgb.XGBClassifier(
            tree_method="hist",
            device="cuda",
            n_estimators=50,
            max_depth=6
        )
        model_gpu.fit(X, y)
        gpu_time = time.time() - start
        print(f"✅ GPU XGBoost: {gpu_time:.2f}s")
    except Exception as e:
        print(f"❌ GPU erro: {e}")
        gpu_time = None
    
    # Teste CPU
    print("\n=== Testando CPU ===")
    start = time.time()
    model_cpu = xgb.XGBClassifier(
        tree_method="hist",
        device="cpu",
        n_estimators=50,
        max_depth=6
    )
    model_cpu.fit(X, y)
    cpu_time = time.time() - start
    print(f"✅ CPU XGBoost: {cpu_time:.2f}s")
    
    # Comparação
    if gpu_time:
        speedup = cpu_time / gpu_time
        print(f"\n🚀 Speedup GPU: {speedup:.1f}x")
    
    return gpu_time is not None


def test_cuda_available():
    """Verifica se CUDA está disponível"""
    print("\n=== Verificando CUDA ===")
    try:
        import torch
        cuda = torch.cuda.is_available()
        if cuda:
            print(f"✅ PyTorch CUDA: {torch.cuda.get_device_name(0)}")
            print(f"   Memória: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")
        else:
            print("⚠️ PyTorch CUDA não disponível")
        return cuda
    except ImportError:
        print("⚠️ PyTorch não instalado")
        return False


if __name__ == "__main__":
    print("=" * 50)
    print("B3 Trading Platform - Teste de GPU")
    print("=" * 50)
    
    # Teste XGBoost
    xgb_ok = test_xgboost_gpu()
    
    # Teste PyTorch (opcional)
    test_cuda_available()
    
    print("\n" + "=" * 50)
    if xgb_ok:
        print("✅ GPU pronta para uso com XGBoost!")
    else:
        print("⚠️ GPU não disponível - usando CPU")
    print("=" * 50)
