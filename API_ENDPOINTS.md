# 📡 API Endpoints - B3 Trading Platform

## Execution Engine (Port 3008)

### 🏥 Health Check

```bash
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2026-01-13T23:31:11.494349",
  "services": {
    "postgres": "healthy",
    "timescaledb": "healthy",
    "redis": "healthy"
  }
}
```

---

### 📊 Estratégias

#### Listar todas as estratégias

```bash
GET /api/strategies
```

**Response:**
```json
[
  {
    "name": "trend_following",
    "description": "Estratégia de seguimento de tendência usando cruzamento de EMAs",
    "parameters": {
      "ema_fast": 9,
      "ema_slow": 21,
      "rsi_period": 14,
      "rsi_overbought": 70,
      "rsi_oversold": 30
    }
  },
  ...
]
```

#### Obter detalhes de uma estratégia

```bash
GET /api/strategies/{strategy_name}
```

---

### 🔄 Backtesting

#### Executar backtest

```bash
POST /api/backtest/run
Content-Type: application/json

{
  "symbol": "PETR4",
  "start_date": "2025-01-13",
  "end_date": "2026-01-12",
  "timeframe": "1d",
  "strategy": "trend_following",
  "initial_capital": 100000,
  "params": {}
}
```

**Response:**
```json
{
  "symbol": "PETR4",
  "strategy": "trend_following",
  "period": {
    "start": "2025-01-13",
    "end": "2026-01-12"
  },
  "metrics": {
    "total_return": 478.47,
    "sharpe_ratio": 2.797,
    "max_drawdown": 1212.65,
    "win_rate": 40.0,
    "total_trades": 5,
    "profit_factor": 1.462,
    "final_capital": 100478.47
  },
  "equity_curve": [...],
  "trades": [...]
}
```

#### Comparar múltiplas estratégias

```bash
POST /api/backtest/compare?symbol=PETR4&start_date=2025-01-13&end_date=2026-01-12&timeframe=1d&strategies=trend_following&strategies=mean_reversion&strategies=rsi_divergence&initial_capital=100000
```

**Response:**
```json
{
  "comparison": {
    "symbol": "PETR4",
    "timeframe": "1d",
    "period": {
      "start": "2025-01-13",
      "end": "2026-01-12"
    },
    "initial_capital": 100000.0,
    "strategies_tested": 3
  },
  "ranking": [
    {
      "strategy": "mean_reversion",
      "metrics": {
        "total_return": 478.47,
        "sharpe_ratio": 2.797,
        "max_drawdown": 1212.65,
        "win_rate": 40.0,
        "total_trades": 5,
        "profit_factor": 1.462,
        "final_capital": 100478.47
      },
      "trades": [...]
    },
    ...
  ],
  "best_strategy": "mean_reversion"
}
```

---

### 🎯 Sinais de Trading

#### Obter sinal para um ativo

```bash
GET /api/signals/PETR4?timeframe=1d&strategy=trend_following
```

#### Scan múltiplos ativos

```bash
GET /api/signals/scan?symbols=PETR4,VALE3,ITUB4&timeframe=1d&strategy=mean_reversion
```

---

### 🧠 Endpoint Adaptativo (NOVO - PASSO 8)

**Detecta automaticamente o regime de mercado e seleciona a estratégia ideal**

```bash
POST /api/adaptive-signal/PETR4?timeframe=1d&lookback=200
```

**Response:**
```json
{
  "symbol": "PETR4",
  "timeframe": "1d",
  "timestamp": "2026-01-13T23:39:00.404581",
  "market_regime": "volatile",
  "selected_strategy": "rsi_divergence",
  "recommended_strategies": [
    "rsi_divergence",
    "dynamic_position_sizing",
    "mean_reversion"
  ],
  "signal": {
    "action": "HOLD",
    "strength": 0.5,
    "price": 30.36,
    "stop_loss": 0.0,
    "take_profit": 0.0
  },
  "market_context": {
    "adx": 48.31,
    "atr": 2.67,
    "rsi": 39.94,
    "volume_avg": 32907465.0
  }
}
```

**Regimes de Mercado:**
- `trending_up`: ADX > 25 + EMA crescente + RSI > 50
- `trending_down`: ADX > 25 + EMA decrescente + RSI < 50
- `ranging`: ADX < 20
- `volatile`: ATR% > 3%

**Estratégias Recomendadas por Regime:**
- **Trending Up/Down:** `trend_following`, `breakout`, `macd_crossover`
- **Ranging:** `mean_reversion`, `rsi_divergence`
- **Volatile:** `rsi_divergence`, `dynamic_position_sizing`, `mean_reversion`

---

### � Walk-Forward Optimization (NOVO - PASSO 10)

**Otimização robusta de parâmetros com validação out-of-sample**

```bash
POST /api/optimize/walk-forward?symbol={symbol}&start_date={YYYY-MM-DD}&end_date={YYYY-MM-DD}&timeframe={timeframe}&strategy={strategy}&train_window_days={int}&test_window_days={int}&step_days={int}&optimization_metric={metric}&n_trials={int}&initial_capital={float}
```

**Parâmetros:**
- `symbol`: Símbolo do ativo (ex: PETR4)
- `start_date`: Data inicial (YYYY-MM-DD)
- `end_date`: Data final (YYYY-MM-DD)
- `timeframe`: Intervalo (1m, 5m, 15m, 1h, 1d)
- `strategy`: Estratégia a otimizar
- `train_window_days`: Tamanho da janela de treino em dias (padrão: 180)
- `test_window_days`: Tamanho da janela de teste em dias (padrão: 30)
- `step_days`: Passo para avançar janela (None = anchored, valor = rolling)
- `optimization_metric`: sharpe_ratio | total_return | profit_factor
- `n_trials`: Número de trials Optuna por janela (padrão: 50)
- `initial_capital`: Capital inicial

**Tipos de Walk-Forward:**
- **Anchored**: `step_days=None` - Janela de treino cresce, teste fixo
- **Rolling**: `step_days=30` - Ambas as janelas deslizam

**Response:**
```json
{
  "strategy": "mean_reversion",
  "configuration": {
    "train_window_days": 90,
    "test_window_days": 30,
    "step_days": 30,
    "optimization_metric": "sharpe_ratio",
    "n_trials": 10,
    "initial_capital": 100000.0
  },
  "aggregate_statistics": {
    "total_windows": 4,
    "avg_test_return": 125.45,
    "std_test_return": 78.32,
    "avg_test_sharpe": 1.85,
    "std_test_sharpe": 0.42,
    "total_test_trades": 12,
    "positive_windows": 3,
    "negative_windows": 1
  },
  "windows": [
    {
      "window_id": 1,
      "period": {
        "train": {
          "start": "2025-06-02T13:00:00+00:00",
          "end": "2025-08-31T13:00:00+00:00",
          "size": 64
        },
        "test": {
          "start": "2025-09-01T13:00:00+00:00",
          "end": "2025-10-01T13:00:00+00:00",
          "size": 23
        }
      },
      "best_params": {
        "bb_period": 24,
        "bb_std": 1.75,
        "rsi_period": 10,
        "rsi_oversold": 35,
        "rsi_overbought": 80
      },
      "train_metrics": {
        "total_return": 501.42,
        "sharpe_ratio": 60.14,
        "max_drawdown": 248.28,
        "win_rate": 100.0,
        "total_trades": 2,
        "profit_factor": 999.99
      },
      "test_metrics": {
        "total_return": 0,
        "sharpe_ratio": null,
        "max_drawdown": 0,
        "win_rate": 0,
        "total_trades": 0,
        "profit_factor": null
      },
      "optimization_trials": 10
    }
  ]
}
```

**Algoritmo de Otimização:**
- **Optuna TPE Sampler**: Tree-structured Parzen Estimator
- **Espaços de Busca Personalizados**: Cada estratégia tem seu próprio espaço de parâmetros
- **Penalizações**: Drawdown > 30%, trades = 0
- **Execução Assíncrona**: ThreadPoolExecutor para evitar conflito de event loops

---

### �📄 Paper Trading

#### Status do paper trading

```bash
GET /api/paper/status
```

#### Executar ordem

```bash
POST /api/paper/order
Content-Type: application/json

{
  "symbol": "PETR4",
  "side": "BUY",
  "quantity": 100,
  "order_type": "MARKET",
  "stop_loss": 29.0,
  "take_profit": 32.0
}
```

#### Listar posições abertas

```bash
GET /api/paper/positions
```

---

## 🔧 Exemplos de Uso

### Testar endpoint adaptativo

```bash
curl -X POST 'http://localhost:3008/api/adaptive-signal/PETR4?timeframe=1d&lookback=200' | python3 -m json.tool
```

### Comparar 3 estratégias

```bash
curl -X POST 'http://localhost:3008/api/backtest/compare?symbol=PETR4&start_date=2025-01-13&end_date=2026-01-12&timeframe=1d&strategies=trend_following&strategies=mean_reversion&strategies=rsi_divergence&initial_capital=100000' | python3 -m json.tool
```

### Listar estratégias

```bash
curl http://localhost:3008/api/strategies | python3 -m json.tool
```

### Executar backtest simples

```bash
curl -X POST http://localhost:3008/api/backtest/run \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "PETR4",
    "start_date": "2025-01-13",
    "end_date": "2026-01-12",
    "timeframe": "1d",
    "strategy": "mean_reversion",
    "initial_capital": 100000
  }' | python3 -m json.tool
```

### Walk-Forward Optimization

#### 📊 Exemplo 1: Rolling Walk-Forward (Janelas Deslizantes)

**Cenário:** Testar estratégia `mean_reversion` com janelas de 90 dias de treino e 30 dias de teste, avançando 30 dias por vez.

```bash
curl -X POST 'http://localhost:3008/api/optimize/walk-forward?\
symbol=PETR4&\
start_date=2025-06-01&\
end_date=2026-01-12&\
timeframe=1d&\
strategy=mean_reversion&\
train_window_days=90&\
test_window_days=30&\
step_days=30&\
optimization_metric=sharpe_ratio&\
n_trials=50&\
initial_capital=100000' | python3 -m json.tool
```

**Comportamento Rolling:**
```
Janela 1: Train [Jun-Aug] → Test [Set]
Janela 2: Train [Jul-Set] → Test [Out]
Janela 3: Train [Ago-Out] → Test [Nov]
Janela 4: Train [Set-Nov] → Test [Dez]
```

**Resultado Esperado:**
```json
{
  "strategy": "mean_reversion",
  "aggregate_statistics": {
    "total_windows": 4,
    "avg_test_sharpe": 1.45,
    "std_test_sharpe": 0.38,
    "avg_test_return": 234.56,
    "positive_windows": 3,
    "negative_windows": 1
  },
  "windows": [
    {
      "window_id": 1,
      "best_params": {
        "bb_period": 24,
        "bb_std": 1.75,
        "rsi_period": 10,
        "rsi_oversold": 35,
        "rsi_overbought": 80
      },
      "train_metrics": {"sharpe_ratio": 60.14, "total_trades": 2},
      "test_metrics": {"sharpe_ratio": 1.85, "total_trades": 3}
    }
  ]
}
```

#### 📈 Exemplo 2: Anchored Walk-Forward (Janela Crescente)

**Cenário:** Estratégia `rsi_divergence` com janela de treino crescente (anchored) e teste fixo de 30 dias.

```bash
curl -X POST 'http://localhost:3008/api/optimize/walk-forward?\
symbol=PETR4&\
start_date=2025-01-13&\
end_date=2026-01-12&\
timeframe=1d&\
strategy=rsi_divergence&\
train_window_days=180&\
test_window_days=30&\
optimization_metric=sharpe_ratio&\
n_trials=100&\
initial_capital=100000' | python3 -m json.tool
```

**Comportamento Anchored (step_days omitido = None):**
```
Janela 1: Train [Jan-Jun]        → Test [Jul]
Janela 2: Train [Jan-Jul]        → Test [Ago]
Janela 3: Train [Jan-Ago]        → Test [Set]
Janela 4: Train [Jan-Set]        → Test [Out]
```

**Vantagem:** Mais dados de treino a cada janela, simulando deployment incremental.

#### 🔬 Exemplo 3: Comparação de Estratégias com Walk-Forward

**Cenário:** Comparar `trend_following` vs `mean_reversion` usando walk-forward.

```bash
# 1. Walk-Forward para Trend Following
curl -X POST 'http://localhost:3008/api/optimize/walk-forward?\
symbol=VALE3&\
start_date=2025-03-01&\
end_date=2026-01-12&\
timeframe=1d&\
strategy=trend_following&\
train_window_days=120&\
test_window_days=30&\
step_days=30&\
optimization_metric=sharpe_ratio&\
n_trials=75&\
initial_capital=100000' > trend_wf.json

# 2. Walk-Forward para Mean Reversion
curl -X POST 'http://localhost:3008/api/optimize/walk-forward?\
symbol=VALE3&\
start_date=2025-03-01&\
end_date=2026-01-12&\
timeframe=1d&\
strategy=mean_reversion&\
train_window_days=120&\
test_window_days=30&\
step_days=30&\
optimization_metric=sharpe_ratio&\
n_trials=75&\
initial_capital=100000' > mean_wf.json

# 3. Comparar resultados
python3 << 'EOF'
import json

with open('trend_wf.json') as f1, open('mean_wf.json') as f2:
    trend = json.load(f1)
    mean = json.load(f2)
    
print("=" * 60)
print("COMPARAÇÃO WALK-FORWARD: TREND vs MEAN REVERSION")
print("=" * 60)
print(f"Trend Following:")
print(f"  Avg Test Sharpe: {trend['aggregate_statistics']['avg_test_sharpe']:.2f}")
print(f"  Positive Windows: {trend['aggregate_statistics']['positive_windows']}")
print(f"\nMean Reversion:")
print(f"  Avg Test Sharpe: {mean['aggregate_statistics']['avg_test_sharpe']:.2f}")
print(f"  Positive Windows: {mean['aggregate_statistics']['positive_windows']}")
EOF
```

#### ⚡ Exemplo 4: Walk-Forward Rápido (Desenvolvimento)

**Cenário:** Teste rápido com poucos trials para validar implementação.

```bash
curl -X POST 'http://localhost:3008/api/optimize/walk-forward?\
symbol=ITUB4&\
start_date=2025-09-01&\
end_date=2026-01-12&\
timeframe=1d&\
strategy=breakout&\
train_window_days=60&\
test_window_days=20&\
step_days=20&\
optimization_metric=total_return&\
n_trials=10&\
initial_capital=50000' | python3 -m json.tool
```

**Parâmetros Leves:**
- `n_trials=10` (apenas 10 otimizações por janela)
- `train_window_days=60` (janela menor)
- Execução: ~5-10 segundos

#### 🎯 Exemplo 5: Walk-Forward com Profit Factor

**Cenário:** Otimizar para `profit_factor` ao invés de Sharpe Ratio.

```bash
curl -X POST 'http://localhost:3008/api/optimize/walk-forward?\
symbol=PETR4&\
start_date=2025-04-01&\
end_date=2026-01-12&\
timeframe=1d&\
strategy=macd_crossover&\
train_window_days=90&\
test_window_days=30&\
step_days=30&\
optimization_metric=profit_factor&\
n_trials=60&\
initial_capital=100000' | python3 -m json.tool
```

**Métricas de Otimização Disponíveis:**
- `sharpe_ratio`: Retorno ajustado ao risco (padrão)
- `total_return`: Retorno absoluto em R$
- `profit_factor`: Razão ganhos/perdas

#### 📝 Exemplo 6: Script Python Completo

```python
#!/usr/bin/env python3
"""
Script de Walk-Forward Optimization Automatizado
"""
import requests
import json
from datetime import datetime

# Configuração
API_URL = "http://localhost:3008"
STRATEGIES = ["mean_reversion", "trend_following", "rsi_divergence"]
SYMBOL = "PETR4"
START_DATE = "2025-01-13"
END_DATE = "2026-01-12"

def run_walk_forward(strategy, step_days=30):
    """Executa walk-forward para uma estratégia."""
    params = {
        "symbol": SYMBOL,
        "start_date": START_DATE,
        "end_date": END_DATE,
        "timeframe": "1d",
        "strategy": strategy,
        "train_window_days": 120,
        "test_window_days": 30,
        "step_days": step_days,
        "optimization_metric": "sharpe_ratio",
        "n_trials": 50,
        "initial_capital": 100000
    }
    
    print(f"\n{'='*60}")
    print(f"🔄 Otimizando {strategy}...")
    print(f"{'='*60}")
    
    response = requests.post(
        f"{API_URL}/api/optimize/walk-forward",
        params=params,
        timeout=300
    )
    
    if response.status_code == 200:
        result = response.json()
        stats = result["aggregate_statistics"]
        
        print(f"✅ Concluído!")
        print(f"   Total Windows: {stats['total_windows']}")
        print(f"   Avg Test Sharpe: {stats['avg_test_sharpe']:.2f} ± {stats['std_test_sharpe']:.2f}")
        print(f"   Avg Test Return: R$ {stats['avg_test_return']:.2f}")
        print(f"   Win Rate: {stats['positive_windows']}/{stats['total_windows']}")
        
        return result
    else:
        print(f"❌ Erro: {response.status_code}")
        print(response.text)
        return None

def main():
    """Executa walk-forward para todas as estratégias."""
    results = {}
    
    for strategy in STRATEGIES:
        result = run_walk_forward(strategy)
        if result:
            results[strategy] = result
    
    # Ranking
    print(f"\n{'='*60}")
    print("🏆 RANKING FINAL")
    print(f"{'='*60}")
    
    ranking = sorted(
        results.items(),
        key=lambda x: x[1]["aggregate_statistics"]["avg_test_sharpe"],
        reverse=True
    )
    
    for i, (strategy, result) in enumerate(ranking, 1):
        stats = result["aggregate_statistics"]
        print(f"{i}. {strategy:20} → Sharpe: {stats['avg_test_sharpe']:.2f}")
    
    # Salvar resultados
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"walk_forward_results_{timestamp}.json"
    
    with open(filename, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n💾 Resultados salvos em: {filename}")

if __name__ == "__main__":
    main()
```

**Uso:**
```bash
chmod +x walk_forward_test.py
python3 walk_forward_test.py
```

---

---

## 🎯 Estratégias Disponíveis

| Nome | Descrição | Indicadores Principais |
|------|-----------|------------------------|
| `trend_following` | Seguimento de tendência | EMA 9/21, RSI, Volume |
| `mean_reversion` | Reversão à média | Bollinger Bands, RSI |
| `breakout` | Rompimentos de suporte/resistência | High/Low 20 períodos, Volume |
| `macd_crossover` | Cruzamento MACD | MACD, Signal Line, Histogram |
| `rsi_divergence` | Divergências RSI (4 padrões) | RSI, ADX, Volume, MACD |
| `dynamic_position_sizing` | Kelly Criterion adaptativo | EMA 20/50, RSI, ATR, Volatilidade |

---

## 📚 Documentação Adicional

- **Arquitetura OOP:** [services/execution-engine/src/strategies/](services/execution-engine/src/strategies/)
- **BaseStrategy:** Classe abstrata com helpers (ATR, RSI, EMA, SMA, BB, MACD, ADX)
- **StrategyManager:** Gerenciador central com detecção de regime
- **BacktestEngine:** Motor de backtesting com métricas completas

---

**Última atualização:** 13 de Janeiro de 2026
