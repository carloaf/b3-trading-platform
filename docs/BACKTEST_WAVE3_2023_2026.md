# 📊 Resultados Backtest Wave3 v2.1 - Dados Reais 2023-2026

**Data:** 28 de Janeiro de 2026  
**Estratégia:** Wave3 Enhanced v2.1  
**Período:** Janeiro/2023 → Dezembro/2024 (2 anos)  
**Fonte:** ProfitChart CSV (775.259 registros reais B3)

---

## 🎯 Configuração do Backtest

**Parâmetros:**
- Quality Score: ≥ 55
- Verificação: 1x por dia (no fechamento diário)
- Risk:Reward: 3:1 (18% target, 6% stop)
- Máximo por trade: 30 dias
- Timeframes: Daily (contexto) + 60min (gatilho)

**Símbolos Testados:**
- PETR4 (Petrobras)
- VALE3 (Vale)
- ITUB4 (Itaú)
- BBDC4 (Bradesco)
- ABEV3 (Ambev)

---

## 📈 Resultados Consolidados

### Performance Geral (5 Ativos)

| Métrica | Valor |
|---------|-------|
| **Total de Trades** | 24 |
| **Winners** | 8 (33.3%) ⚠️ |
| **Losers** | 16 (66.7%) |
| **Avg Win Rate** | 26.3% |
| **Total Return** | +18.63% (2 anos) |
| **Avg Return/Ativo** | +3.73% |
| **Avg Sharpe Ratio** | -21.39 ⚠️ |

---

## 📊 Performance por Ativo

### ⭐ PETR4 (Melhor Performer)
```
Trades:        5
Winners:       3 (60.0%) ✅
Total Return:  +25.68%
Sharpe Ratio:  11.29 ⭐⭐⭐
Avg Win:       +10.92%
Avg Loss:      -3.55%
```
**Conclusão:** Único ativo com performance positiva consistente.

---

### ⚠️ VALE3 (Pior Performer)
```
Trades:        2
Winners:       0 (0.0%) ❌
Total Return:  -6.34%
Sharpe Ratio:  -43.42 ❌
Avg Win:       0.00%
Avg Loss:      -3.17%
```
**Conclusão:** Todos os sinais resultaram em losses.

---

### 🟡 ITUB4 (Moderado)
```
Trades:        7
Winners:       3 (42.9%)
Total Return:  +10.42%
Sharpe Ratio:  4.37
Avg Win:       +7.60%
Avg Loss:      -3.10%
```
**Conclusão:** Performance moderada, win rate abaixo do esperado.

---

### ❌ BBDC4 (Negativo)
```
Trades:        3
Winners:       0 (0.0%) ❌
Total Return:  -8.76%
Sharpe Ratio:  -76.94 ❌
Avg Win:       0.00%
Avg Loss:      -2.92%
```
**Conclusão:** Nenhum sinal vencedor.

---

### ⚠️ ABEV3 (Negativo)
```
Trades:        7
Winners:       2 (28.6%)
Total Return:  -2.37%
Sharpe Ratio:  -2.23
Avg Win:       +3.46%
Avg Loss:      -1.86%
```
**Conclusão:** Mais losers que winners.

---

## 🔍 Análise Crítica

### ❌ Problemas Identificados

1. **Win Rate Muito Baixo**
   - Esperado: 77.8% (baseline v2.1)
   - Obtido: 33.3% (24 trades)
   - Diferença: -44.5 pontos percentuais ⚠️

2. **Poucos Trades**
   - 24 trades em 2 anos = 1 trade/mês
   - Estratégia muito conservadora (score ≥55)

3. **Performance Inconsistente**
   - Apenas PETR4 teve Sharpe > 1
   - 3 de 5 ativos com return negativo

4. **Sharpe Ratio Negativo**
   - Avg: -21.39 (muito ruim)
   - Indica alta volatilidade de retornos

### ⚠️ Possíveis Causas

1. **Quality Score 55 Inadequado**
   - Score muito baixo pode gerar sinais ruins
   - Testar: 60, 65, 70

2. **Verificação Diária vs Intraday**
   - Backtest original usava 60min (mais granular)
   - Teste atual: 1x/dia (menos preciso)
   - **Loss de timing**: Entrada/saída no close do dia

3. **Dados Insuficientes para Warm-up**
   - Strategy precisa 72 dias (EMA 72)
   - 60min pode ter lacunas

4. **Regime de Mercado**
   - 2023-2024 pode ter sido período difícil
   - Tendências laterais ou reversões constantes

---

## 🎯 Próximos Passos

### 1. ✅ Testar Quality Scores Maiores
```bash
# Testar score 60, 65, 70
python3 /scripts/backtest_wave3_fast.py --quality-score 65
```

**Expectativa:**
- Score 65: ~10-15 trades, win rate 50-60%
- Score 70: ~5-8 trades, win rate 70-80%

---

### 2. ✅ Backtest Intraday (60min)
```python
# Criar backtest_wave3_intraday.py
# Verificar sinais a cada candle 60min (não diário)
# Expectativa: Mais trades, timing melhor
```

---

### 3. ✅ Walk-Forward Optimization
```python
# Otimizar parâmetros:
# - Quality score
# - EMA 72/17 vs outros períodos
# - Risk:Reward ratio
# - Timeframe combinações
```

---

### 4. ⏳ Análise de Regime de Mercado
```sql
-- Verificar características do mercado 2023-2024
SELECT 
    EXTRACT(YEAR FROM time) as year,
    EXTRACT(MONTH FROM time) as month,
    COUNT(*) as days,
    AVG(close) as avg_close,
    STDDEV(close) as volatility
FROM ohlcv_daily
WHERE symbol = 'PETR4'
AND time BETWEEN '2023-01-01' AND '2024-12-31'
GROUP BY year, month
ORDER BY year, month;
```

---

### 5. ⏳ Comparar com Outras Estratégias
- **RSI Divergence:** Pode ser melhor em mercado lateral
- **MACD Crossover:** Mais simples, mais trades
- **Mean Reversion:** Para períodos range-bound

---

## 📝 Recomendações

### ✅ Ações Imediatas

1. **NÃO usar Wave3 v2.1 em produção ainda**
   - Win rate 33% é inaceitável (< 50%)
   - Sharpe negativo indica alto risco

2. **Focar em PETR4 para testes**
   - Único ativo com Sharpe > 1
   - 60% win rate (5 trades)
   - Usar como benchmark

3. **Aumentar Quality Score para 65-70**
   - Reduzir trades ruins
   - Melhorar win rate
   - Aceitar menos trades (qualidade > quantidade)

4. **Implementar backtest intraday**
   - Timing mais preciso
   - Aproveitar volatilidade 60min

---

### ⏳ Médio Prazo

1. **Coletar mais dados** (até Jun/2026)
   - Aumentar sample size
   - Validar em diferentes regimes

2. **Paper Trading com Score 70**
   - Testar em mercado real
   - Monitorar 20-30 sinais

3. **Adicionar filtros ML** (quando tiver 50+ trades)
   - Rejeitar 10-20% piores sinais
   - Melhorar win rate para 60-70%

---

## 📚 Arquivos Relacionados

- **Script:** `scripts/backtest_wave3_fast.py`
- **Estratégia:** `services/execution-engine/src/strategies/wave3_enhanced.py`
- **Dados:** TimescaleDB `ohlcv_daily`, `ohlcv_60min`
- **Documentação:** `INSTRUCOES.md` (PASSO A)

---

## 🔄 Histórico de Testes

| Data | Versão | Score | Trades | Win% | Return | Sharpe | Observações |
|------|--------|-------|--------|------|--------|--------|-------------|
| 28/01/2026 | v2.1 | 55 | 24 | 33.3% | +18.63% | -21.39 | Win rate muito baixo |
| - | - | 60 | - | - | - | - | Próximo teste |
| - | - | 65 | - | - | - | - | Próximo teste |
| - | - | 70 | - | - | - | - | Próximo teste |

---

**Status:** ⚠️ **NÃO VALIDADA para produção**  
**Próxima Ação:** Testar quality_score 65 e 70  
**Meta:** Win rate > 60%, Sharpe > 1.5, Max DD < 15%
