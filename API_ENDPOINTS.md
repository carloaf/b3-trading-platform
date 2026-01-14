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

```bash
# Otimização Rolling (janelas deslizantes)
curl -X POST 'http://localhost:3008/api/optimize/walk-forward?symbol=PETR4&start_date=2025-06-01&end_date=2026-01-12&timeframe=1d&strategy=mean_reversion&train_window_days=90&test_window_days=30&step_days=30&optimization_metric=sharpe_ratio&n_trials=50&initial_capital=100000' | python3 -m json.tool

# Otimização Anchored (janela de treino crescente)
curl -X POST 'http://localhost:3008/api/optimize/walk-forward?symbol=PETR4&start_date=2025-01-13&end_date=2026-01-12&timeframe=1d&strategy=rsi_divergence&train_window_days=180&test_window_days=30&optimization_metric=sharpe_ratio&n_trials=100' | python3 -m json.tool
```

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
