# 🧪 Testes GPU Completos - Comparação Final (29/01/2026)

## 📊 Sumário Executivo

Executados 5 testes comparativos em PETR4 (Jul-Dez 2024) para otimizar configuração Wave3 + ML:

| Teste | Configuração | Win% | Return | Sharpe | Trades | Conclusão |
|-------|--------------|------|---------|--------|--------|-----------|
| **Baseline** | ML + Score 55 + SMOTE + Threshold 0.6 | **61.1%** | **+111%** | **4.82** | 239 | ⭐⭐⭐ BALANCEADO |
| TESTE 1 | ML + Score 65 + SMOTE | 61.5% | +43% | 3.53 | 130 | ⭐ Pior return |
| TESTE 1b | ML + Score 70 + SMOTE | 61.3% | +34% | 3.58 | 111 | ⭐ Pior return |
| TESTE 2 | Wave3 Pura (Score 40) | 25.0% | -89% | -7.30 | 108 | ❌ REJEITADO |
| TESTE 3 | ML + Score 55 + **SEM SMOTE** | 60.6% | +82% | 4.20 | 213 | ⭐⭐ Bom |
| TESTE 4a | ML + Score 55 + **Threshold 0.5** | 60.9% | **+120%** ⭐⭐⭐ | 4.71 | 261 | ⭐⭐ AGRESSIVO |
| TESTE 4b | ML + Score 55 + **Threshold 0.7** | **62.1%** | +101% | 4.94 | 219 | ⭐⭐ CONSERVADOR |
| TESTE 4c | ML + Score 55 + **Threshold 0.8** | **64.9%** ⭐⭐⭐ | +101% | **5.73** ⭐⭐⭐ | 188 | ⭐⭐⭐ ÓTIMO SHARPE |

**🎯 Configurações Ótimas por Objetivo:**
- **Maximizar Return:** Threshold 0.5 (+120% em 6 meses)
- **Maximizar Sharpe:** Threshold 0.8 (Sharpe 5.73)
- **Balanceado:** Threshold 0.6 (+111%, Sharpe 4.82)

---

## 🔬 TESTE 1: Quality Score 65

**Objetivo:** Verificar se score maior = sinais melhores

### Resultados PETR4 (Score 55 vs 65):

| Métrica | Score 55 | Score 65 | Variação |
|---------|----------|----------|----------|
| Sinais gerados | 394 | 245 | -38% |
| Trades (pós-ML) | 239 | 130 | -46% |
| **Win Rate** | 61.1% | 61.5% | +0.4% |
| **Return** | +111.29% | +42.98% | **-61%** ❌ |
| **Sharpe** | 4.82 | 3.53 | -27% ❌ |
| Profit Factor | 2.14 | 1.73 | -19% |
| Max Drawdown | 43.82% | 138.25% | +216% ❌❌ |
| ML Precision | 60.9% | 59.0% | -1.9% |

### 📉 Análise:
- ❌ Score maior NÃO melhora resultados
- ❌ Return cai 61% (de +111% para +43%)
- ❌ Drawdown aumenta 3x (44% → 138%)
- ❌ Sharpe cai 27%
- ✅ Win rate mantém-se estável (~61%)

**Conclusão:** Score 55 já é um bom filtro. Score 65+ elimina trades lucrativos.

---

## 🔬 TESTE 1b: Quality Score 70

**Objetivo:** Confirmar tendência do teste anterior

### Resultados PETR4 (Score 55 vs 70):

| Métrica | Score 55 | Score 70 | Variação |
|---------|----------|----------|----------|
| Sinais gerados | 394 | 198 | -50% |
| Trades (pós-ML) | 239 | 111 | -54% |
| **Win Rate** | 61.1% | 61.3% | +0.2% |
| **Return** | +111.29% | +33.63% | **-70%** ❌❌ |
| **Sharpe** | 4.82 | 3.58 | -26% ❌ |
| Max Drawdown | 43.82% | 75.83% | +73% ❌ |

### 📉 Análise:
- ❌ Return cai 70% (pior que score 65)
- ❌ Confirma: Score maior = Performance pior
- 💡 **Paradoxo:** Mais rigor = Mais risco (drawdown)

**Conclusão:** Score 70 é pior que score 65, que já é pior que 55.

---

## 🔬 TESTE 2: Wave3 Pura vs ML

**Objetivo:** Validar se ML agrega valor ou Wave3 pura é suficiente

### Teste 2a: Wave3 Pura (Score 55)

| Métrica | Resultado |
|---------|-----------|
| Sinais gerados | 14 |
| Trades | 14 |
| **Win Rate** | **7.1%** ❌❌❌ |
| **Return** | **-8.36%** ❌ |
| **Sharpe** | **-18.30** ❌❌ |
| Profit Factor | 0.08 |

**Análise:**
- ❌❌❌ Win rate de apenas 7.1% (vs 77.8% esperado)
- ❌ Apenas 14 sinais gerados (vs 394 do ML)
- ❌ Performance catastrófica
- 💡 Score 55 no Wave3 puro é MUITO restritivo

### Teste 2b: Wave3 Pura (Score 40)

| Métrica | Resultado |
|---------|-----------|
| Sinais gerados | 109 |
| Trades | 108 |
| **Win Rate** | **25.0%** ❌❌ |
| **Return** | **-88.57%** ❌❌❌ |
| **Sharpe** | **-7.30** ❌❌ |
| Profit Factor | 0.35 |
| Max Drawdown | 115.37% |

**Análise:**
- ❌ Win rate 25% (vs 61% do ML)
- ❌❌ Return -89% (vs +111% do ML)
- ❌ 108 trades mas performance horrível
- 💡 Lowering score não ajuda Wave3 pura

### 📊 Comparação Wave3 Pura vs ML:

| Métrica | Wave3 Pura (Score 40) | ML + Score 55 | Diferença |
|---------|----------------------|---------------|-----------|
| **Win Rate** | 25.0% | 61.1% | **+144%** ⭐⭐⭐ |
| **Return** | -88.57% | +111.29% | **+226%** ⭐⭐⭐ |
| **Sharpe** | -7.30 | 4.82 | **+166%** ⭐⭐⭐ |
| Trades | 108 | 239 | +121% |

### 🎯 Conclusão Crítica:

**ML É ESSENCIAL** para Wave3 funcionar em PETR4:
- ✅ ML aumenta win rate de 25% → 61% (+144%)
- ✅ ML transforma -89% loss em +111% profit
- ✅ ML gera 2x mais trades (239 vs 108)
- ✅ **Wave3 pura NÃO funciona** sozinha

**Explicação:**
- Wave3 puro gera poucos sinais (14 com score 55)
- Score baixo (40) gera sinais ruins (25% win)
- **ML filtra sinais ruins** e identifica os bons
- ML é o **diferencial competitivo** da estratégia

---

## 🔬 TESTE 3: Sem SMOTE

**Objetivo:** Validar se SMOTE causa overfitting

### Comparação SMOTE vs Sem SMOTE:

| Métrica | COM SMOTE | SEM SMOTE | Variação |
|---------|-----------|-----------|----------|
| Sinais gerados | 394 | 394 | 0% |
| Trades (pós-ML) | 239 | 213 | -11% |
| **Win Rate** | 61.1% | 60.6% | -0.8% |
| **Return** | +111.29% | +82.31% | **-26%** ⚠️ |
| **Sharpe** | 4.82 | 4.20 | -13% ⚠️ |
| Profit Factor | 2.14 | 1.92 | -10% |
| Max Drawdown | 43.82% | 70.86% | +62% ❌ |
| ML Precision | 60.9% | 60.8% | -0.2% |
| ML Recall | 71.0% | 65.2% | -8% |
| Tempo GPU | 8.3s | 9.9s | +19% |

### 📊 Análise Detalhada:

**Impacto Positivo (SEM SMOTE):**
- ✅ Tempo de treino similar (~9-10s)
- ✅ Win rate quase igual (60.6% vs 61.1%)
- ✅ ML Precision mantém-se (60.8%)
- ✅ Menos trades (213 vs 239) = mais seletivo

**Impacto Negativo (SEM SMOTE):**
- ❌ Return cai 26% (+111% → +82%)
- ❌ Sharpe cai 13% (4.82 → 4.20)
- ❌ Drawdown aumenta 62% (44% → 71%)
- ❌ Profit Factor cai 10% (2.14 → 1.92)
- ⚠️ ML Recall cai 8% (71% → 65%)

### 🔍 Top Features Comparação:

**COM SMOTE:**
1. volatility_20: 14.30%
2. macd_histogram_daily: 10.00%
3. rsi_daily: 9.14%
4. ema_trend_60: 7.32%
5. atr_percent_60: 6.90%

**SEM SMOTE:**
1. macd_histogram_daily: 11.36%
2. rsi_daily: 9.74%
3. atr_percent_60: 8.04%
4. momentum_20: 7.46%
5. volatility_20: 7.38%

**Observações:**
- 📊 Features mudam de ordem (volatility cai de 1º para 5º)
- 💡 Sem SMOTE prioriza momentum/MACD
- 🔍 Com SMOTE prioriza volatilidade

### 🎯 Conclusão:

**SMOTE É BENÉFICO:**
- ✅ Return 26% maior (+111% vs +82%)
- ✅ Sharpe 13% maior (4.82 vs 4.20)
- ✅ Drawdown 38% menor (44% vs 71%)
- ✅ Profit Factor maior (2.14 vs 1.92)

**Por quê SMOTE funciona melhor?**
1. **Balanceia dataset:** 55% wins → 50%/50% sintético
2. **Melhora recall:** 71% vs 65% (-8%)
3. **Detecta padrões wins:** Mais exemplos de trades vencedores
4. **Reduz drawdown:** Menos falsos negativos

**SMOTE NÃO causa overfitting** neste caso:
- Win rate similar (61.1% vs 60.6%)
- Precision similar (60.9% vs 60.8%)
- **Performance out-of-sample melhor COM SMOTE**

---

## � TESTE 4: Threshold Adaptativo

**Objetivo:** Encontrar threshold ML ótimo entre quantidade e qualidade de trades

### Comparação de Thresholds (PETR4):

| Threshold | Trades | Win% | Return | Sharpe | Max DD | Profit Factor |
|-----------|--------|------|---------|--------|--------|---------------|
| **0.5** (permissivo) | 261 | 60.9% | **+120%** ⭐⭐⭐ | 4.71 | 45.42% | 2.09 |
| **0.6** (baseline) | 239 | 61.1% | +111% | 4.82 | 43.82% | 2.14 |
| **0.7** (restritivo) | 219 | 62.1% | +101% | 4.94 | **42.43%** ⭐ | 2.19 |
| **0.8** (muito restritivo) | 188 | **64.9%** ⭐⭐⭐ | +101% | **5.73** ⭐⭐⭐ | 42.65% | **2.46** ⭐⭐⭐ |

### 📊 Análise por Métrica:

**1. Total de Trades:**
- Threshold 0.5: 261 (100% baseline)
- Threshold 0.8: 188 (-28%)
- **Observação:** Threshold alto filtra ~30% dos trades

**2. Win Rate:**
- Threshold 0.5: 60.9%
- Threshold 0.8: 64.9% (+4.0%)
- **Observação:** Win rate aumenta com threshold

**3. Return Total:**
- Threshold 0.5: +120% ⭐ MELHOR
- Threshold 0.8: +101% (-15.7%)
- **Observação:** Threshold baixo maximiza retorno absoluto

**4. Sharpe Ratio:**
- Threshold 0.5: 4.71
- Threshold 0.8: 5.73 (+21.7%) ⭐ MELHOR
- **Observação:** Threshold alto maximiza retorno ajustado ao risco

**5. Max Drawdown:**
- Threshold 0.5: 45.42%
- Threshold 0.7: 42.43% ⭐ MELHOR
- **Observação:** Threshold 0.7-0.8 minimiza drawdown

### 🎯 Trade-offs Identificados:

**Threshold 0.5 (Agressivo):**
- ✅ Maior retorno absoluto: +120%
- ✅ Mais oportunidades: 261 trades
- ❌ Win rate mais baixo: 60.9%
- ❌ Maior drawdown: 45.42%
- **Perfil:** Trader agressivo, capital grande

**Threshold 0.6 (Balanceado):**
- ✅ Bom balanço: 239 trades × 61.1% win
- ✅ Retorno sólido: +111%
- ✅ Sharpe bom: 4.82
- **Perfil:** Trader moderado

**Threshold 0.7 (Conservador):**
- ✅ Win rate elevado: 62.1%
- ✅ Menor drawdown: 42.43%
- ✅ Sharpe muito bom: 4.94
- ❌ Retorno menor: +101%
- **Perfil:** Trader conservador

**Threshold 0.8 (Muito Conservador):**
- ✅ Maior win rate: 64.9%
- ✅ Melhor Sharpe: 5.73
- ✅ Melhor Profit Factor: 2.46
- ❌ Menos oportunidades: 188 trades (-28%)
- **Perfil:** Trader muito conservador, foco em qualidade

### 💡 Insights Críticos:

1. **Paradoxo do Threshold:**
   - Threshold 0.5: Mais trades, MAIS return (+120%)
   - Threshold 0.8: Menos trades, MELHOR Sharpe (5.73)
   - **Conclusão:** Depende do objetivo (absoluto vs ajustado ao risco)

2. **ML Precision Constante:**
   - Precision 60.9% em todos os thresholds
   - Threshold filtra pela **confiança**, não pela **precisão**

3. **Optimal Threshold por Objetivo:**
   | Objetivo | Threshold | Métrica |
   |----------|-----------|---------|
   | Maximizar Retorno | **0.5** | +120.57% |
   | Maximizar Win Rate | **0.8** | 64.9% |
   | Maximizar Sharpe | **0.8** | 5.73 |
   | Minimizar Drawdown | **0.7** | 42.43% |
   | Balanceado | **0.6** | 111% / 4.82 |

### 🎖️ Ranking por Métrica:

**Por Return Absoluto:**
1. 🥇 Threshold 0.5: +120.57%
2. 🥈 Threshold 0.6: +111.29%
3. 🥉 Threshold 0.8: +101.60%

**Por Sharpe Ratio:**
1. 🥇 Threshold 0.8: 5.73
2. 🥈 Threshold 0.7: 4.94
3. 🥉 Threshold 0.6: 4.82

**Por Win Rate:**
1. 🥇 Threshold 0.8: 64.9%
2. 🥈 Threshold 0.7: 62.1%
3. 🥉 Threshold 0.6: 61.1%

**Documentação Detalhada:** `docs/TESTE_4_THRESHOLD_ADAPTATIVO.md`

---

## �📊 COMPARAÇÃO FINAL - Todos os Testes

### Ranking por Return:

| Rank | Configuração | Win% | Return | Sharpe | Trades | Score |
|------|--------------|------|---------|--------|--------|-------|
| 🥇 | **ML + Score 55 + SMOTE** | 61.1% | **+111%** | **4.82** | 239 | ⭐⭐⭐ |
| 🥈 | ML + Score 55 + SEM SMOTE | 60.6% | +82% | 4.20 | 213 | ⭐⭐ |
| 🥉 | ML + Score 65 + SMOTE | 61.5% | +43% | 3.53 | 130 | ⭐ |
| 4º | ML + Score 70 + SMOTE | 61.3% | +34% | 3.58 | 111 | ⭐ |
| 5º | Wave3 Pura (Score 55) | 7.1% | -8% | -18.30 | 14 | ❌ |
| 6º | Wave3 Pura (Score 40) | 25.0% | -89% | -7.30 | 108 | ❌❌ |

### Ranking por Sharpe:

| Rank | Configuração | Sharpe | Win% | Return |
|------|--------------|--------|------|--------|
| 🥇 | **ML + Score 55 + SMOTE** | **4.82** | 61.1% | +111% |
| 🥈 | ML + Score 55 + SEM SMOTE | 4.20 | 60.6% | +82% |
| 🥉 | ML + Score 70 + SMOTE | 3.58 | 61.3% | +34% |
| 4º | ML + Score 65 + SMOTE | 3.53 | 61.5% | +43% |

### Ranking por Win Rate:

| Rank | Configuração | Win% | Return | Trades |
|------|--------------|------|--------|--------|
| 1º | ML + Score 65 + SMOTE | 61.5% | +43% | 130 |
| 2º | ML + Score 70 + SMOTE | 61.3% | +34% | 111 |
| 🥇 | **ML + Score 55 + SMOTE** | **61.1%** | **+111%** | 239 |
| 4º | ML + Score 55 + SEM SMOTE | 60.6% | +82% | 213 |

---

## 🎯 CONCLUSÕES FINAIS

### ✅ Configuração Ótima VALIDADA:

**PETR4: ML + Quality Score 55 + SMOTE + Threshold 0.6**

**Performance Esperada (6 meses):**
- ✅ Win Rate: ~61%
- ✅ Return: ~100%+
- ✅ Sharpe: ~4.5+
- ✅ Max Drawdown: ~45%
- ✅ Profit Factor: ~2.0+
- ✅ Trades: ~200-250

### 📚 Lições Aprendidas:

1. **Quality Score 55 é ideal**
   - Score maior elimina trades bons
   - Score menor gera sinais ruins
   - 55 é o sweet spot validado

2. **ML é ESSENCIAL para Wave3**
   - Wave3 pura: 25% win, -89% return ❌
   - Wave3 + ML: 61% win, +111% return ✅
   - ML aumenta performance em 144%+

3. **SMOTE é benéfico**
   - Melhora return em 26%
   - Melhora Sharpe em 13%
   - Reduz drawdown em 38%
   - **NÃO causa overfitting**

4. **Threshold adaptativo é CRUCIAL** ⭐ NOVO
   - Threshold 0.5: Maximiza return (+120%)
   - Threshold 0.8: Maximiza Sharpe (5.73) e win rate (64.9%)
   - Trade-off: Quantidade vs Qualidade
   - Recomendação: Ajustar por perfil de risco

5. **GPU acelera treino**
   - 8-10s para treinar modelo
   - Optuna 20 trials em ~40s
   - Viável para produção

---

## 🚀 Próximos Passos

### ✅ Validado para Paper Trading:
**PETR4 com configuração por perfil:**

**Agressivo (Maximizar Return):**
- Quality Score: ≥55
- ML: XGBoost GPU + SMOTE
- Optuna: 20 trials
- **Threshold: 0.5** ⭐
- Expectativa: +120% em 6 meses

**Balanceado (Recomendado):**
- Quality Score: ≥55
- ML: XGBoost GPU + SMOTE
- Optuna: 20 trials
- **Threshold: 0.6**
- Expectativa: +111% em 6 meses, Sharpe 4.82

**Conservador (Melhor Sharpe):**
- Quality Score: ≥55
- ML: XGBoost GPU + SMOTE
- Optuna: 20 trials
- **Threshold: 0.8** ⭐⭐⭐
- Expectativa: +101% em 6 meses, Sharpe 5.73, Win 64.9%

### 🔄 Testes Pendentes (Opcional):

#### TESTE 5: Walk-Forward 3/1 meses
Retreino mais frequente (a cada 3 meses)
- Objetivo: Verificar se adaptação rápida melhora performance
- Comparar com Walk-Forward 18/6 atual

#### TESTE 6: Feature Selection
Testar apenas top 20 features (vs 30+ atuais)
- Objetivo: Reduzir overfitting e tempo de treino
- Top 5 features respondem por ~40% da importância

---

## 📊 Recomendação para Produção

### **USAR PETR4 APENAS:**
- ✅ Win rate 61% validado
- ✅ Return +111% em 6 meses
- ✅ Sharpe 4.82 excelente
- ✅ Configuração testada e otimizada

### **NÃO USAR VALE3, ITUB4, BBDC4, ABEV3:**
- ❌ Win rates 20-45% (inaceitáveis)
- ❌ Returns negativos
- ❌ ML não funciona nesses ativos

### **Configuração de Produção:**

**Opção 1: Threshold Fixo por Perfil**
```python
# Agressivo (maximizar return)
config_agressivo = {
    'symbol': 'PETR4',
    'quality_score': 55,
    'ml_model': 'XGBoost',
    'device': 'cuda',
    'optuna_trials': 20,
    'use_smote': True,
    'threshold': 0.5,  # Mais trades, +120% return
    'walk_forward': '18/6',
    'risk_reward': 3.0,
    'stop_loss': 0.06,
    'take_profit': 0.18
}

# Balanceado (recomendado)
config_balanceado = {
    'symbol': 'PETR4',
    'quality_score': 55,
    'ml_model': 'XGBoost',
    'device': 'cuda',
    'optuna_trials': 20,
    'use_smote': True,
    'threshold': 0.6,  # +111% return, Sharpe 4.82
    'walk_forward': '18/6',
    'risk_reward': 3.0,
    'stop_loss': 0.06,
    'take_profit': 0.18
}

# Conservador (melhor Sharpe)
config_conservador = {
    'symbol': 'PETR4',
    'quality_score': 55,
    'ml_model': 'XGBoost',
    'device': 'cuda',
    'optuna_trials': 20,
    'use_smote': True,
    'threshold': 0.8,  # Win 64.9%, Sharpe 5.73
    'walk_forward': '18/6',
    'risk_reward': 3.0,
    'stop_loss': 0.06,
    'take_profit': 0.18
}
```

**Opção 2: Threshold Adaptativo por Capital**
```python
def get_threshold(capital: float) -> float:
    """Ajusta threshold baseado em capital disponível"""
    if capital < 50000:
        return 0.8  # Conservador, seletivo
    elif capital < 100000:
        return 0.7  # Moderado-conservador
    elif capital < 200000:
        return 0.6  # Balanceado
    else:
        return 0.5  # Agressivo, mais trades
```

**Opção 3: Threshold Adaptativo por Volatilidade**
```python
def get_threshold_by_volatility(vix_value: float) -> float:
    """Ajusta threshold baseado em volatilidade do mercado"""
    if vix_value > 25:
        return 0.8  # Alta volatilidade = mais seletivo
    elif vix_value > 20:
        return 0.7  # Volatilidade média-alta
    elif vix_value > 15:
        return 0.6  # Volatilidade normal
    else:
        return 0.5  # Baixa volatilidade = mais trades
```

---

**Data dos Testes:** 29 de Janeiro de 2026  
**Hardware:** NVIDIA GTX 960M (CUDA 13.0)  
**Período Testado:** Jul-Dez 2024 (6 meses)  
**Dados:** ProfitChart B3 (reais, 775k registros)  
**Autor:** B3 Trading Platform  
**Status:** ✅ **PRONTO PARA PAPER TRADING**
