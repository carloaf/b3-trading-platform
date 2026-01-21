# 📊 Próximas Ações - Otimização Intraday 60min

> **Data:** 20 de Janeiro de 2026  
> **Contexto:** Após importação de 268K candles do ProfitChart  
> **Status:** 🔴 ESTRATÉGIA WAVE3 NÃO FUNCIONA EM 60MIN COM PARÂMETROS ATUAIS

---

## 🎯 OBJETIVO

Otimizar a estratégia Wave3 para operar com dados de 60min, corrigindo os problemas identificados nos testes comparativos.

---

## 📉 PROBLEMAS IDENTIFICADOS

### Resultados dos Testes (2024-2025)

| Ação | 60min Retorno | Daily Retorno | Win Rate 60min | Win Rate Daily | Trades 60min | Trades Daily |
|------|---------------|---------------|----------------|----------------|--------------|--------------|
| **PETR4** | **-99.97%** 💀 | -12.15% | 18.10% | 33.33% | **232** | 12 |
| **VALE3** | +0.39% ⚠️ | -0.59% | 40.19% | 50.00% | **321** | 20 |
| **ITUB4** | **-99.97%** 💀 | -2.86% | 27.04% | 42.86% | **159** | 21 |

### Análise dos Problemas

#### 1. **Overtrading Severo** 🔴 CRÍTICO
- **60min:** 159-321 trades/ano
- **Daily:** 12-21 trades/ano
- **Diferença:** 10x mais trades
- **Impacto:** Custos operacionais, slippage, exaustão de capital

**Causa Raiz:**
- Parâmetros de SMA/RSI muito sensíveis para 60min
- Falta de filtro de volatilidade mínima
- Ausência de cooldown entre trades

#### 2. **Win Rate Muito Baixo** 🔴 CRÍTICO
- **60min:** 18-40% (abaixo do mínimo viável)
- **Daily:** 33-50% (aceitável)
- **Meta:** 50-52% (André Moraes)

**Causa Raiz:**
- Noise do mercado intraday não filtrado
- Sinais falsos em consolidações laterais
- Falta de confirmação multi-timeframe

#### 3. **Drawdown Catastrófico** 🔴 CRÍTICO
- **PETR4/ITUB4:** -99.97% (perda total)
- **Causa:** Sequência de perdas sem stop loss adequado
- **Risk Management:** Inexistente para 60min

#### 4. **Lucro Médio Baixo vs Perda Média Alta** 🔴 CRÍTICO
- **PETR4:** Lucro R$ 1.209 | Perda R$ 798 (1.5:1) ✅
- **VALE3:** Lucro R$ 760 | Perda R$ 517 (1.5:1) ✅
- **ITUB4:** Lucro R$ 574 | Perda R$ 1.123 (0.5:1) ❌

**Problema:** Profit Factor < 1.0 em ITUB4

---

## 🔧 PLANO DE AÇÃO

### **FASE 1: Ajustes de Parâmetros** ⏱️ 2-3 horas

#### 1.1 Aumentar Períodos de Indicadores
```python
# ATUAL (otimizado para daily)
SMA_PERIOD = 20
SMA_TREND_PERIOD = 50
RSI_PERIOD = 14

# PROPOSTO (para 60min)
SMA_PERIOD = 40        # 40 horas = ~5 dias
SMA_TREND_PERIOD = 100 # 100 horas = ~12.5 dias
RSI_PERIOD = 21        # 21 horas = ~2.5 dias
```

**Lógica:**
- 60min tem 8 candles/dia (pregão 10h-18h)
- SMA 20 daily ≈ SMA 160 hourly
- Mas noise é maior, então usar períodos intermediários

#### 1.2 Filtros de Entrada Mais Rigorosos
```python
# Adicionar condições extras
buy_signal = (
    close > sma AND
    sma > sma_trend AND                    # ✅ Atual
    rsi > 40 AND rsi < 60 AND              # ✅ Atual (ajustado)
    volume > avg_volume * 1.5 AND          # 🆕 NOVO - Volume mínimo
    atr > atr_ma * 0.8 AND                 # 🆕 NOVO - Volatilidade mínima
    (high - low) / close > 0.005           # 🆕 NOVO - Range mínimo 0.5%
)
```

#### 1.3 Cooldown Entre Trades
```python
# Evitar overtrading
MIN_CANDLES_BETWEEN_TRADES = 8  # 8 horas mínimo
last_trade_time = None

if buy_signal and (last_trade_time is None or 
                   current_time - last_trade_time > MIN_CANDLES_BETWEEN_TRADES):
    # Executar trade
    last_trade_time = current_time
```

---

### **FASE 2: Walk-Forward Optimization** ⏱️ 4-6 horas

#### 2.1 Grid Search de Parâmetros
```python
param_grid = {
    'sma_period': [30, 40, 50, 60],
    'sma_trend_period': [80, 100, 120],
    'rsi_period': [14, 21, 28],
    'rsi_oversold': [30, 35, 40],
    'rsi_overbought': [60, 65, 70],
    'volume_mult': [1.2, 1.5, 2.0],
    'atr_mult_sl': [1.5, 2.0, 2.5],
    'atr_mult_tp': [2.0, 3.0, 4.0]
}
```

**Método:**
- Training: 70% dos dados (Jan/2024 - Set/2025)
- Validation: 15% (Out/2025 - Nov/2025)
- Testing: 15% (Dez/2025)

**Métricas de Otimização:**
1. **Sharpe Ratio** (peso 40%)
2. **Win Rate** (peso 30%)
3. **Profit Factor** (peso 20%)
4. **Max Drawdown** (peso 10%)

#### 2.2 Análise de Overfitting
```python
# Validação cruzada temporal
num_folds = 5
fold_results = []

for fold in range(num_folds):
    train_start = fold * (len(data) // num_folds)
    train_end = train_start + (len(data) * 0.7 // num_folds)
    
    # Treinar e validar
    ...
```

---

### **FASE 3: Regime Detection** ⏱️ 6-8 horas

#### 3.1 Identificar Regimes de Mercado
```python
def detect_market_regime(df):
    """
    Classifica regime atual:
    - TRENDING_UP: ADX > 25 e +DI > -DI
    - TRENDING_DOWN: ADX > 25 e -DI > +DI
    - RANGING: ADX < 25
    - HIGH_VOLATILITY: ATR > ATR_MA * 1.5
    - LOW_VOLATILITY: ATR < ATR_MA * 0.7
    """
    adx = calculate_adx(df, period=14)
    atr = calculate_atr(df, period=14)
    
    if adx > 25:
        return "TRENDING"
    else:
        return "RANGING"
```

#### 3.2 Parâmetros Adaptativos
```python
if regime == "TRENDING":
    # Parâmetros agressivos
    sma_period = 30
    atr_mult_sl = 2.0
    
elif regime == "RANGING":
    # Parâmetros conservadores
    sma_period = 50
    atr_mult_sl = 1.5
    # Desabilitar trades em ranging?
    TRADE_ENABLED = False
```

---

### **FASE 4: Machine Learning Enhancement** ⏱️ 8-12 horas

#### 4.1 Feature Engineering Intraday
```python
# Features temporais
features = [
    'hour_of_day',           # 10-18
    'time_to_close',         # Minutos até fechamento
    'is_first_hour',         # Primeira hora pregão
    'is_last_hour',          # Última hora pregão
]

# Features de microestrutura
features += [
    'bid_ask_spread',        # Spread estimado
    'volume_imbalance',      # Compra vs venda
    'price_impact',          # Movimento por volume
]

# Features de regime
features += [
    'adx',
    'atr_percentile',        # ATR relativo a 20 períodos
    'volume_percentile',
]
```

#### 4.2 Modelo XGBoost para Filtragem
```python
from xgboost import XGBClassifier

# Treinar modelo para prever "bom trade"
X_train = df[features]
y_train = df['profitable_trade']  # 1 se lucro > 1%, 0 caso contrário

model = XGBClassifier(
    max_depth=5,
    n_estimators=100,
    learning_rate=0.1
)

model.fit(X_train, y_train)

# Usar no live trading
signal_probability = model.predict_proba(current_features)
if signal_probability[1] > 0.65:  # 65% confiança
    # Executar trade
```

---

### **FASE 5: Risk Management Avançado** ⏱️ 3-4 horas

#### 5.1 Position Sizing Dinâmico
```python
def calculate_position_size(capital, atr, win_rate, risk_pct=0.01):
    """
    Kelly Criterion adaptado para intraday
    """
    # Kelly fraction
    kelly = (win_rate - (1 - win_rate)) / 1.5  # R:R 1.5:1
    kelly_adjusted = kelly * 0.25  # 25% do Kelly (conservador)
    
    # Risk-based
    risk_amount = capital * risk_pct
    shares = risk_amount / (atr * 2.0)
    
    # Combinar ambos
    final_shares = min(shares, capital * kelly_adjusted / current_price)
    
    return int(final_shares)
```

#### 5.2 Trailing Stop Adaptativo
```python
def update_trailing_stop(entry_price, current_price, atr, regime):
    """
    Stop loss que se ajusta ao regime
    """
    if regime == "TRENDING":
        # Stop mais largo
        initial_sl = entry_price - (atr * 2.5)
        
        # Trailing após 1.5 ATR de lucro
        if current_price > entry_price + (atr * 1.5):
            trailing_sl = current_price - (atr * 1.5)
            return max(trailing_sl, initial_sl)
    
    elif regime == "RANGING":
        # Stop mais apertado
        initial_sl = entry_price - (atr * 1.5)
        
        # Trailing após 1 ATR de lucro
        if current_price > entry_price + atr:
            trailing_sl = current_price - atr
            return max(trailing_sl, initial_sl)
    
    return initial_sl
```

---

## 📊 MÉTRICAS DE SUCESSO

### Metas Mínimas (60min)

| Métrica | Meta | Atual | Status |
|---------|------|-------|--------|
| **Win Rate** | ≥ 45% | 18-40% | ❌ |
| **Profit Factor** | ≥ 1.5 | 0.5-1.5 | ⚠️ |
| **Sharpe Ratio** | ≥ 1.0 | -2.1 a +0.02 | ❌ |
| **Max Drawdown** | ≤ 20% | -99.97% | ❌ |
| **Trades/Ano** | 50-100 | 159-321 | ❌ |
| **Avg Win** | ≥ R$ 1.000 | R$ 574-1.209 | ⚠️ |
| **Avg Loss** | ≤ R$ 800 | R$ 517-1.123 | ⚠️ |

### Metas Otimistas (após otimização)

| Métrica | Meta | 
|---------|------|
| **Win Rate** | 50-55% |
| **Profit Factor** | 2.0-2.5 |
| **Sharpe Ratio** | 1.5-2.0 |
| **Max Drawdown** | 10-15% |
| **Trades/Ano** | 60-80 |
| **Retorno Anual** | 15-25% |

---

## 🛠️ IMPLEMENTAÇÃO PRÁTICA

### Passo 1: Ajustes Rápidos (HOJE)
```bash
# 1. Criar branch de desenvolvimento
cd /home/dellno/worksapace/b3-trading-platform
git checkout -b feature/wave3-60min-optimization

# 2. Modificar estratégia
vim services/execution-engine/src/strategies/wave3_intraday_strategy.py

# 3. Testar com novos parâmetros
docker exec b3-data-collector python3 /tmp/test_wave3_60min_v2.py

# 4. Comparar resultados
```

### Passo 2: Walk-Forward (AMANHÃ)
```bash
# 1. Implementar otimizador específico
vim services/execution-engine/src/walk_forward_60min.py

# 2. Executar grid search
docker exec b3-execution-engine python /app/src/walk_forward_60min.py \
    --symbols PETR4 VALE3 ITUB4 \
    --interval 60min \
    --train-period 18 \
    --validation-period 3 \
    --test-period 3

# 3. Salvar melhores parâmetros
# Resultado esperado: params_60min_optimized.json
```

### Passo 3: Regime Detection (SEMANA QUE VEM)
```bash
# 1. Implementar detector de regime
vim services/execution-engine/src/regime_detector.py

# 2. Integrar com estratégia
vim services/execution-engine/src/strategies/wave3_adaptive_strategy.py

# 3. Backtesting com regime switching
docker exec b3-execution-engine python /app/src/backtest_adaptive.py
```

---

## 📚 REFERÊNCIAS

### Artigos Sobre Intraday Trading
- **Larry Williams** - "The Intraday Trading Rules" (1997)
- **Linda Raschke** - "Street Smarts: High Probability Short-Term Trading Strategies" (1996)
- **Kevin Haggerty** - "Mastering Short-Term Trading" (2000)

### Papers Acadêmicos
- **Chande & Kroll** - "The New Technical Trader" (1994) - ADX e regime detection
- **Kaufman** - "Trading Systems and Methods" (2013) - Adaptive parameters
- **Prado** - "Advances in Financial Machine Learning" (2018) - Feature engineering

### Estratégias de Referência
- **André Moraes** - Wave 3 Multi-Timeframe (contexto daily, gatilho 60min)
- **Alexander Elder** - Triple Screen Trading System
- **John Carter** - "Mastering the Trade" - Intraday filters

---

## 🎯 PRÓXIMOS PASSOS IMEDIATOS

### 1. **HOJE (20/01/2026)** - Ajustes Rápidos
- [ ] Criar `wave3_intraday_strategy.py` com parâmetros ajustados
- [ ] Implementar filtros de volume e ATR
- [ ] Adicionar cooldown entre trades
- [ ] Re-testar PETR4, VALE3, ITUB4
- [ ] Documentar resultados

### 2. **AMANHÃ (21/01/2026)** - Walk-Forward
- [ ] Implementar `walk_forward_60min.py`
- [ ] Executar grid search (30 combinações × 3 símbolos = 90 testes)
- [ ] Validar em out-of-sample
- [ ] Salvar melhores parâmetros

### 3. **ESTA SEMANA** - Regime Detection
- [ ] Implementar `regime_detector.py` (ADX + ATR)
- [ ] Criar `wave3_adaptive_strategy.py`
- [ ] Testar regime switching
- [ ] Comparar vs parâmetros fixos

### 4. **PRÓXIMA SEMANA** - Machine Learning
- [ ] Feature engineering intraday
- [ ] Treinar XGBoost classifier
- [ ] Integrar com estratégia
- [ ] Backtesting final

---

## ⚠️ AVISOS IMPORTANTES

### 1. **Não Deploy em Produção Ainda**
- Estratégia 60min está com performance negativa
- Precisa de otimização completa antes de paper trading
- Risco de perda total confirmado nos testes

### 2. **Dados São Bons, Estratégia Não**
- ✅ 268K candles importados corretamente
- ✅ Dados validados (OHLC, volume, timestamps)
- ❌ Parâmetros inadequados para 60min
- ❌ Falta risk management específico

### 3. **Expectativas Realistas**
- Intraday é mais difícil que daily (noise, custos, slippage)
- Win rate 60min sempre será menor que daily
- Meta: 45-50% win rate com profit factor > 1.5
- Não esperar retornos astronômicos

---

## 📞 SUPORTE

Dúvidas sobre implementação:
1. Consultar [INSTRUCOES.md](../INSTRUCOES.md)
2. Ver exemplos em `services/execution-engine/src/strategies/`
3. Revisar `docs/PROFITPRO_INTEGRATION.md`

---

**Última Atualização:** 20 de Janeiro de 2026  
**Autor:** Stock-IndiceDev Assistant  
**Status:** 🔴 AÇÃO IMEDIATA NECESSÁRIA
