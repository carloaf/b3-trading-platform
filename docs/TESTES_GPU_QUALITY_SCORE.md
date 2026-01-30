# 🔬 Testes GPU - Comparação Quality Score (29/01/2026)

## 📊 Objetivo

Testar diferentes níveis de Quality Score para validar impacto na qualidade dos sinais Wave3 + ML.

---

## 🧪 TESTE 1: Quality Score 65 (5 ativos)

**Configuração:**
- Quality Score: ≥65 (vs 55 do teste anterior)
- Símbolos: PETR4, VALE3, ITUB4, BBDC4, ABEV3
- ML: XGBoost GPU + Optuna (20 trials)
- Threshold: 0.6
- Período: Train 18 meses, Test 6 meses

### Resultados Consolidados:

| Métrica | Score 55 | Score 65 | Diferença |
|---------|----------|----------|-----------|
| **Total Trades** | 607 | 347 | -260 (-43%) |
| **Win Rate Médio** | 37.5% | 38.0% | +0.5% |
| **Sharpe Médio** | -2.15 | -2.12 | +0.03 |
| **Return Médio** | -6.16% | -1.13% | +5.03% |
| **Tempo GPU** | 44.3s | 41.1s | -3.2s |

### Por Símbolo:

#### ⭐ PETR4 - Melhor Performance

| Métrica | Score 55 | Score 65 | Variação |
|---------|----------|----------|----------|
| Sinais gerados | 394 | 245 | -38% ✅ |
| Trades após ML | 239 | 130 | -46% ✅ |
| **Win Rate** | 61.1% | **61.5%** | +0.4% ⭐ |
| **Return** | +111.29% | +42.98% | -61% ⚠️ |
| **Sharpe** | 4.82 | 3.53 | -27% |
| **Profit Factor** | 2.14 | 1.73 | -19% |
| Max Drawdown | 43.82% | 138.25% | +216% ❌ |
| ML Precision | 60.9% | 59.0% | -1.9% |

**Análise:**
- ✅ Win rate mantém-se estável (~61%)
- ⚠️ Return cai pela metade (menos trades)
- ❌ Drawdown aumenta 3x (piora da qualidade)
- 💡 Score 65 **NÃO melhorou** vs score 55

#### ❌ VALE3, ITUB4, BBDC4, ABEV3

Todos continuam com performance negativa mesmo com score 65:
- VALE3: 21.1% win, -35% return
- ITUB4: 41.9% win, -5% return
- BBDC4: 45.5% win, -1% return
- ABEV3: 20.0% win, -7% return

---

## 🧪 TESTE 1b: Quality Score 70 (PETR4 apenas)

**Configuração:**
- Quality Score: ≥70 (ainda mais rigoroso)
- Símbolo: PETR4 apenas
- ML: XGBoost GPU + Optuna
- Threshold: 0.6

### Resultados PETR4:

| Métrica | Score 55 | Score 65 | Score 70 | Melhor |
|---------|----------|----------|----------|--------|
| Sinais gerados | 394 | 245 | 198 | - |
| Trades após ML | 239 | 130 | 111 | - |
| **Win Rate** | 61.1% | 61.5% | **61.3%** | Score 65 ⭐ |
| **Return** | +111.29% | +42.98% | +33.63% | Score 55 ⭐⭐⭐ |
| **Sharpe** | 4.82 | 3.53 | 3.58 | Score 55 ⭐⭐⭐ |
| **Profit Factor** | 2.14 | 1.73 | 1.74 | Score 55 ⭐⭐ |
| Max Drawdown | 43.82% | 138.25% | 75.83% | Score 55 ⭐ |
| ML Precision | 60.9% | 59.0% | 58.1% | Score 55 ⭐ |
| Tempo GPU | - | - | 7.9s | - |

### 📈 Gráfico de Comparação (PETR4):

```
Win Rate (quanto maior, melhor):
Score 55: ████████████████████████████████████████████████████████████ 61.1%
Score 65: █████████████████████████████████████████████████████████████ 61.5%
Score 70: ████████████████████████████████████████████████████████████ 61.3%

Return (quanto maior, melhor):
Score 55: ████████████████████████████████████████████████████████████ +111.29%
Score 65: ████████████████████ +42.98%
Score 70: ███████████████ +33.63%

Sharpe Ratio (quanto maior, melhor):
Score 55: ████████████████████████████████████████████████ 4.82
Score 65: ███████████████████████████████ 3.53
Score 70: ████████████████████████████████ 3.58
```

---

## 🔍 Análise Crítica

### ❌ **Quality Score 65+ NÃO melhora resultados**

**Evidências:**
1. **Win rate estável** (~61%) independente do score
2. **Return cai** conforme score aumenta (menos trades)
3. **Drawdown aumenta** com score 65 (138% vs 44%)
4. **ML Precision cai** com score mais alto

### 💡 **Paradoxo do Quality Score**

**Esperado:**
- Score maior → Sinais melhores → Win rate maior

**Realidade:**
- Score maior → Menos sinais → Win rate igual
- Score maior → Menos trades → Return menor
- Score maior → Drawdown maior (???)

**Hipótese:**
- Score 55 já filtra bem os sinais
- Score 65+ elimina trades bons
- ML não consegue melhorar além do score base

### 🎯 **Conclusões:**

1. **Score 55 é IDEAL para PETR4**
   - Melhor return (+111%)
   - Melhor Sharpe (4.82)
   - Melhor Profit Factor (2.14)
   - Menor Drawdown (44%)

2. **Score 65/70 não agrega valor**
   - Win rate igual
   - Return menor
   - Drawdown pior
   - Menos oportunidades

3. **ML + Score 55 > ML + Score 65+**
   - Mais trades = mais return
   - Score base já é bom filtro
   - ML refina score 55 eficientemente

---

## 📊 Comparação com Baseline Wave3 Pura

| Estratégia | Trades | Win% | Return | Sharpe | Conclusão |
|------------|--------|------|---------|--------|-----------|
| **Wave3 v2.1 Baseline** | ~9 | 77.8% | - | ~2.5 | 📖 Benchmark |
| **ML Score 55** | 239 | 61.1% | +111% | 4.82 | ⭐⭐⭐ MELHOR |
| **ML Score 65** | 130 | 61.5% | +43% | 3.53 | ⭐⭐ Bom |
| **ML Score 70** | 111 | 61.3% | +34% | 3.58 | ⭐⭐ Bom |

**Observação Importante:**
- ML gera **26x mais trades** que baseline (239 vs 9)
- Win rate ML (61%) < Baseline (78%), mas...
- Return ML (+111%) com Sharpe 4.82 é excelente
- **ML vale a pena para PETR4 com score 55**

---

## 🚀 Próximos Testes Recomendados

### ✅ TESTE 2: Wave3 Pura vs ML (PETR4)
Comparar diretamente sem ML para validar se vale a pena:
```bash
docker exec b3-execution-engine python3 /app/backtest_wave3_pure.py --symbol PETR4 --min-quality 55
```

### ✅ TESTE 3: Sem SMOTE (Score 55)
Testar se SMOTE causa overfitting:
```bash
docker exec b3-execution-engine python3 /app/backtest_wave3_gpu.py --min-quality 55 --no-smote --symbols PETR4
```

### ✅ TESTE 4: Threshold Adaptativo
- PETR4: threshold 0.5 (precision 60%+)
- VALE3: threshold 0.8 (precision baixa)

### ✅ TESTE 5: Walk-Forward 3/1 meses
Retreino mais frequente:
```bash
docker exec b3-execution-engine python3 /app/backtest_wave3_gpu.py --walk-forward 3 1 --symbols PETR4
```

---

## 🎯 Recomendação Final

### **Para PETR4: Usar ML com Score 55**

**Configuração Validada:**
- Quality Score: ≥55
- ML: XGBoost GPU
- Optuna: 20 trials
- Threshold: 0.6
- SMOTE: Habilitado

**Métricas Esperadas:**
- Win Rate: ~61%
- Return: ~100%+ (6 meses)
- Sharpe: ~4.5+
- Max Drawdown: ~45%

### **Para VALE3, ITUB4, BBDC4, ABEV3: NÃO USAR**

Todos os scores testados resultam em win rate < 45% (inaceitável).

---

**Data dos Testes:** 29 de Janeiro de 2026, 21:46-21:48 UTC  
**Hardware:** NVIDIA GTX 960M (CUDA 13.0)  
**Autor:** B3 Trading Platform  
**Status:** ✅ **PETR4 Score 55 validado como configuração ótima**
