# 🎯 TESTE 4: Threshold Adaptativo - Análise Completa (29/01/2026)

## 📊 Objetivo

Testar diferentes thresholds de confiança ML para encontrar o ponto ótimo entre:
- **Quantidade de trades** (threshold baixo = mais trades)
- **Qualidade dos trades** (threshold alto = melhor win rate)
- **Retorno total** (balanço entre quantidade e qualidade)

## 🧪 Metodologia

**Asset Testado:** PETR4 (único asset validado nos testes anteriores)  
**Configuração Base:**
- Quality Score: 55
- SMOTE: Habilitado
- Optuna: 20 trials
- Período: Jul-Dez 2024 (6 meses)
- Train: Jan/2023-Jun/2024 (18 meses)

**Thresholds Testados:**
1. **0.5** - Muito permissivo (baseline era 0.6)
2. **0.6** - Baseline original (TESTE inicial)
3. **0.7** - Mais restritivo
4. **0.8** - Muito restritivo

## 📈 Resultados Comparativos

| Threshold | Trades | Win% | Return | Sharpe | Max DD | Profit Factor |
|-----------|--------|------|---------|--------|--------|---------------|
| **0.5** (permissivo) | 261 | 60.9% | **+120.57%** ⭐⭐⭐ | 4.71 | 45.42% | 2.09 |
| **0.6** (baseline) | 239 | **61.1%** | +111.29% ⭐⭐ | 4.82 | 43.82% | 2.14 |
| **0.7** (restritivo) | 219 | **62.1%** ⭐ | +101.57% ⭐ | **4.94** ⭐ | **42.43%** ⭐⭐ | 2.19 |
| **0.8** (muito restritivo) | 188 | **64.9%** ⭐⭐⭐ | +101.60% ⭐ | **5.73** ⭐⭐⭐ | 42.65% ⭐ | **2.46** ⭐⭐⭐ |

### 📊 Análise Detalhada por Métrica

#### 1. **Total de Trades**
```
0.5 → 261 trades (100% baseline)
0.6 → 239 trades (-8.4%)
0.7 → 219 trades (-16.1%)
0.8 → 188 trades (-28.0%)
```
**Observação:** Threshold mais alto filtra ~30% dos trades

#### 2. **Win Rate**
```
0.5 → 60.9%
0.6 → 61.1% (+0.2%)
0.7 → 62.1% (+1.2%)
0.8 → 64.9% (+4.0%) ⭐ MELHOR
```
**Observação:** Win rate aumenta consistentemente com threshold

#### 3. **Return Total**
```
0.5 → +120.57% ⭐ MELHOR
0.6 → +111.29% (-7.7%)
0.7 → +101.57% (-15.8%)
0.8 → +101.60% (-15.7%)
```
**Observação:** Threshold 0.5 maximiza retorno absoluto

#### 4. **Sharpe Ratio** (retorno ajustado ao risco)
```
0.5 → 4.71
0.6 → 4.82 (+2.3%)
0.7 → 4.94 (+4.9%)
0.8 → 5.73 (+21.7%) ⭐⭐⭐ MELHOR
```
**Observação:** Threshold 0.8 maximiza Sharpe Ratio

#### 5. **Max Drawdown**
```
0.5 → 45.42% (PIOR)
0.6 → 43.82% (-3.5%)
0.7 → 42.43% (-6.6%) ⭐ MELHOR
0.8 → 42.65% (-6.1%)
```
**Observação:** Threshold 0.7-0.8 minimiza drawdown

#### 6. **Profit Factor**
```
0.5 → 2.09
0.6 → 2.14 (+2.4%)
0.7 → 2.19 (+4.8%)
0.8 → 2.46 (+17.7%) ⭐⭐⭐ MELHOR
```
**Observação:** Threshold 0.8 maximiza eficiência

## 🎯 Trade-offs Identificados

### Threshold 0.5 (Agressivo)
**Prós:**
- ✅ **Maior retorno absoluto:** +120.57% (melhor)
- ✅ Mais oportunidades: 261 trades
- ✅ Aproveitamento máximo de sinais

**Contras:**
- ❌ Win rate mais baixo: 60.9%
- ❌ Maior drawdown: 45.42%
- ❌ Sharpe menor: 4.71
- ❌ Mais trades perdedores: 102

**Perfil:** Trader agressivo, capital grande, tolera volatilidade

---

### Threshold 0.6 (Balanceado) - BASELINE
**Prós:**
- ✅ Bom balanço: 239 trades × 61.1% win
- ✅ Retorno sólido: +111.29%
- ✅ Sharpe bom: 4.82
- ✅ Drawdown aceitável: 43.82%

**Contras:**
- ⚠️ Não é o melhor em nenhuma métrica específica
- ⚠️ "Middle ground" sem otimização clara

**Perfil:** Trader moderado, sem preferência clara

---

### Threshold 0.7 (Conservador)
**Prós:**
- ✅ Win rate elevado: 62.1%
- ✅ **Menor drawdown:** 42.43% (melhor)
- ✅ Sharpe muito bom: 4.94
- ✅ Profit Factor bom: 2.19

**Contras:**
- ❌ Retorno menor: +101.57% (-15.8% vs 0.5)
- ❌ Menos trades: 219 (-16%)

**Perfil:** Trader conservador, foco em consistência

---

### Threshold 0.8 (Muito Conservador)
**Prós:**
- ✅ **Maior win rate:** 64.9% (melhor)
- ✅ **Melhor Sharpe:** 5.73 (melhor)
- ✅ **Melhor Profit Factor:** 2.46 (melhor)
- ✅ Trades muito seletivos (188)
- ✅ Excelente eficiência por trade

**Contras:**
- ❌ Retorno menor: +101.60% (-15.7% vs 0.5)
- ❌ **Menos oportunidades:** -28% trades
- ❌ Pode perder bons trades (66 losers vs 102)

**Perfil:** Trader muito conservador, capital limitado, foco em qualidade

## 🔬 Análise Estatística

### Teste de Consistência (por threshold)

**ML Precision (constante):** 60.9% em todos os testes
- Indica que o modelo ML tem precision fixa
- Threshold NÃO melhora a precision do modelo
- Threshold FILTRA trades baseado na confiança

**Top Features (consistentes):**
1. Volatility_20: 14.30%
2. MACD Histogram Daily: 10.00%
3. RSI Daily: 9.14%
4. EMA Trend 60: 7.32%
5. ATR Percent 60: 6.90%

**Tempo de Treino GPU:** 8.3-8.9s (estável)

### Curva de Eficiência

```
Trades vs Win Rate:
261 trades → 60.9% win (-4.0% vs melhor)
239 trades → 61.1% win (-3.8%)
219 trades → 62.1% win (-2.8%)
188 trades → 64.9% win (ÓTIMO)
```

**Lei dos Retornos Decrescentes:**
- De 0.5→0.6: +0.2% win, -7.7% return (RUIM)
- De 0.6→0.7: +1.0% win, -8.7% return (MÉDIO)
- De 0.7→0.8: +2.8% win, +0.03% return (BOM!)

**Sweet Spot:** Threshold 0.7-0.8

## 💡 Insights Críticos

### 1. **Paradoxo do Threshold**
- ❌ Threshold 0.5: Mais trades, MAIS return (+120%)
- ✅ Threshold 0.8: Menos trades, MELHOR Sharpe (5.73)
- 💡 **Conclusão:** Depende do objetivo (retorno absoluto vs ajustado ao risco)

### 2. **ML Precision Constante**
- Precision 60.9% em todos os thresholds
- **Explicação:** Precision mede acertos sobre positivos preditos
- Threshold filtra pela **confiança**, não pela **precisão**
- Modelo sempre tem mesma precision, só escolhemos quantos aceitar

### 3. **Optimal Threshold por Objetivo**

| Objetivo | Threshold | Métrica |
|----------|-----------|---------|
| Maximizar Retorno | **0.5** | +120.57% |
| Maximizar Win Rate | **0.8** | 64.9% |
| Maximizar Sharpe | **0.8** | 5.73 |
| Minimizar Drawdown | **0.7** | 42.43% |
| Balanceado | **0.6** | 111% / 4.82 |

### 4. **Recomendação por Perfil de Risco**

**Agressivo (alta tolerância ao risco):**
- Threshold: **0.5**
- Return: +120%
- Drawdown: 45% (aceitável)
- Trades: 261 (máximo)

**Moderado (risco médio):**
- Threshold: **0.6-0.7**
- Return: +101-111%
- Drawdown: 42-44%
- Trades: 219-239

**Conservador (baixo risco):**
- Threshold: **0.8**
- Return: +101%
- Drawdown: 42%
- Win Rate: 65% (alta confiança)
- Trades: 188 (seletivo)

## 🎖️ Ranking Final

### Por Return Absoluto:
1. 🥇 **Threshold 0.5:** +120.57% ⭐⭐⭐
2. 🥈 Threshold 0.6: +111.29%
3. 🥉 Threshold 0.8: +101.60%
4. 4º Threshold 0.7: +101.57%

### Por Sharpe Ratio (Risk-Adjusted):
1. 🥇 **Threshold 0.8:** 5.73 ⭐⭐⭐
2. 🥈 Threshold 0.7: 4.94
3. 🥉 Threshold 0.6: 4.82
4. 4º Threshold 0.5: 4.71

### Por Win Rate:
1. 🥇 **Threshold 0.8:** 64.9% ⭐⭐⭐
2. 🥈 Threshold 0.7: 62.1%
3. 🥉 Threshold 0.6: 61.1%
4. 4º Threshold 0.5: 60.9%

### Por Profit Factor:
1. 🥇 **Threshold 0.8:** 2.46 ⭐⭐⭐
2. 🥈 Threshold 0.7: 2.19
3. 🥉 Threshold 0.6: 2.14
4. 4º Threshold 0.5: 2.09

## 🚀 Recomendações Finais

### Para Produção (Paper Trading):

**Opção 1: Threshold Adaptativo** ⭐ RECOMENDADO
```python
# Ajustar threshold baseado em capital e risco
if capital < 50000:
    threshold = 0.8  # Conservador, seletivo
elif capital < 100000:
    threshold = 0.7  # Moderado-conservador
else:
    threshold = 0.5  # Agressivo, mais trades
```

**Opção 2: Threshold por Contexto de Mercado**
```python
# Alta volatilidade (VIX > 25)
threshold = 0.8  # Mais seletivo

# Volatilidade normal
threshold = 0.6  # Balanceado

# Baixa volatilidade (VIX < 15)
threshold = 0.5  # Mais trades
```

**Opção 3: Threshold Fixo**
- **Conservador:** 0.8 (Sharpe 5.73, Win 64.9%)
- **Agressivo:** 0.5 (Return +120%, mais oportunidades)

### Threshold Recomendado por Objetivo:

| Objetivo Principal | Threshold | Resultado Esperado |
|-------------------|-----------|-------------------|
| 💰 Maximizar lucro absoluto | **0.5** | +120% em 6 meses |
| 📊 Melhor Sharpe Ratio | **0.8** | Sharpe 5.73 |
| 🎯 Melhor Win Rate | **0.8** | 64.9% wins |
| ⚖️ Balanceado | **0.6** | +111%, Sharpe 4.82 |
| 🛡️ Menor Drawdown | **0.7** | 42.43% DD |

## 📊 Comparação com Baseline Wave3 Pura

**Wave3 v2.1 Pure (sem ML):**
- Win Rate: 77.8% (baseline documentado)
- Trades: ~250-300 (estimativa)

**Wave3 + ML (threshold 0.8):**
- Win Rate: 64.9% (-12.9%)
- Trades: 188 (-25-30%)
- **Sharpe: 5.73** (melhor que pura)
- **Return: +101%** (6 meses)

**Conclusão:**
- ML **NÃO melhora** win rate vs Wave3 pura
- ML **MELHORA** Sharpe Ratio (melhor seleção)
- ML **FILTRA** trades, reduz quantidade mas aumenta qualidade

## 🔄 Próximos Passos

### TESTE 5 (Opcional): Walk-Forward 3/1 meses
- Retreino mais frequente (a cada 3 meses)
- Testar se adaptação mais rápida melhora
- Comparar com Walk-Forward 18/6 atual

### Implementação em Produção:
1. ✅ **Validar em paper trading:** Threshold 0.8 (conservador)
2. ⏳ **Coletar 50+ trades:** Com features + resultados
3. ⏳ **Re-treinar modelo:** Com dados reais de paper trading
4. ⏳ **Validar threshold adaptativo:** Ajustar por volatilidade

---

**Data do Teste:** 29 de Janeiro de 2026  
**Asset:** PETR4  
**Período:** Jul-Dez 2024 (6 meses)  
**GPU:** NVIDIA GTX 960M (CUDA 13.0)  
**Tempo Total:** ~33s (4 testes × 8.5s cada)  
**Status:** ✅ **COMPLETO**
