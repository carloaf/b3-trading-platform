# 🚧 BRAPI Free Plan - Limitações e Soluções

## 📊 Resumo Executivo

Durante a implementação da **Option B** (coleta de dados históricos para Wave3 Strategy), identificamos limitações significativas do **BRAPI Free Plan** que impactam a coleta de dados históricos para backtesting.

---

## ⚠️ Limitações Identificadas

### 1. **Range Máximo: 3 Meses**
```
❌ Ranges permitidos: 1d, 5d, 1mo, 3mo
✅ Upgrade necessário para: 6mo, 1y, 2y, 5y, 10y, ytd, max
```

**Impacto:**
- Impossível coletar mais de 3 meses de histórico por requisição
- Tentativas de coleta incremental (3mo + 3mo + 3mo) **falham** pois a API sempre retorna os últimos 3 meses

**Teste Realizado:**
```python
# Tentativa de coleta incremental em chunks de 3 meses
for chunk in range(8):  # 8 x 3mo = 24mo
    data = brapi.get_historical(symbol, range='3mo')
    # Resultado: Sempre os mesmos últimos 3 meses!
```

### 2. **Interval 1h: Disponível Apenas para Alguns Ativos**
```
✅ Com dados 1h: ITUB4, MGLU3, PETR4, VALE3
❌ Sem dados 1h: WEGE3, BBDC4, ABEV3, RENT3, B3SA3, SUZB3
```

**Impacto:**
- Wave3 Strategy multi-timeframe (daily + hourly) **não pode ser testada** para 60% dos ativos
- Apenas 4 de 10 ativos têm dados suficientes

### 3. **Rate Limiting**
```
⏱️  Recomendado: 2-3 segundos entre requisições
🔴 Rate limit: ~200 requisições/dia (não documentado oficialmente)
```

### 4. **Sem Parâmetros de Data Start/End**
```
❌ Não suportado: start_date, end_date, from, to
✅ Único parâmetro: range (1d, 5d, 1mo, 3mo)
```

**Impacto:**
- Impossível especificar período histórico customizado
- Sempre retorna dados mais recentes dentro do range

---

## 📈 Dados Coletados com Sucesso

### Daily Data (ohlcv_1d)
| Símbolo | Barras | Período | Cobertura |
|---------|--------|---------|-----------|
| ITUB4   | 621    | 2024-01-16 → 2026-01-15 | ⭐ 2 anos |
| MGLU3   | 561    | 2024-01-16 → 2026-01-15 | ⭐ 2 anos |
| VALE3   | 559    | 2024-01-16 → 2026-01-14 | ⭐ 2 anos |
| PETR4   | 310    | 2025-01-13 → 2026-01-15 | 🔸 1 ano |
| Outros  | 118-120| 2025-10-17 → 2026-01-15 | ⚠️ 3 meses |

**Total:** 2,763 barras diárias

### Hourly Data (ohlcv_1h)
| Símbolo | Barras | Período | Cobertura |
|---------|--------|---------|-----------|
| ITUB4   | 944    | 2025-10-17 → 2026-01-14 | ✅ 3 meses |
| MGLU3   | 480    | 2025-10-17 → 2026-01-15 | ✅ 3 meses |
| PETR4   | 480    | 2025-10-17 → 2026-01-15 | ✅ 3 meses |
| VALE3   | 478    | 2025-10-17 → 2026-01-15 | ✅ 3 meses |

**Total:** 2,382 barras horárias

---

## 🌊 Ativos Prontos para Wave3 Multi-Timeframe

**4 ativos** com overlap de ~90 dias entre daily e hourly:

```
🌊 ITUB4: 621 daily + 944 hourly (overlap: 89 dias)
🌊 MGLU3: 561 daily + 480 hourly (overlap: 90 dias)
🌊 PETR4: 310 daily + 480 hourly (overlap: 90 dias)
🌊 VALE3: 559 daily + 478 hourly (overlap: 89 dias)
```

**Período de overlap:** 2025-10-17 a 2026-01-15 (~3 meses)

---

## ✅ Soluções Implementadas

### 1. **Wave3 Daily Strategy (Versão Simplificada)**
- ✅ Opera apenas em timeframe diário
- ✅ Funciona com dados disponíveis (3 meses a 2 anos)
- ✅ Mantém princípios Wave3 (MME 72/17, regra dos 17 candles)
- ✅ Testado com 10 ativos B3

**Endpoint:** `POST /api/backtest/wave3-daily`

### 2. **Wave3 Multi-Timeframe (Versão Completa)**
- ✅ Suporta daily + hourly
- ⚠️ Limitado a 4 ativos com dados 1h
- ⚠️ Overlap de apenas 3 meses
- ✅ Estratégia original de André Moraes

**Endpoint:** `POST /api/backtest/wave3`

### 3. **Ajustes no Código**
- ✅ Reduzido mínimo de 100 → 50 bars para incluir mais ativos
- ✅ Conversão Decimal → float para compatibilidade
- ✅ Queries otimizadas para `ohlcv_1d` e `ohlcv_1h`
- ✅ Rate limiting respeitado (2-3s entre requisições)

---

## 🚀 Recomendações

### Curto Prazo (Com BRAPI Free)
1. **Usar Wave3 Daily** para backtesting com 10 ativos
2. **Focar em ITUB4, MGLU3, VALE3** (2 anos de histórico)
3. **Teste multi-timeframe** apenas no período de overlap (3 meses)

### Médio Prazo (Upgrade)
1. **BRAPI Paid Plan:**
   - 💰 A partir de R$ 29,90/mês
   - ✅ Range até 10 anos
   - ✅ Interval 1h para todos os ativos
   - ✅ Maior rate limit

2. **Alpha Vantage:**
   - 💰 Free: 25 requests/dia, dados limitados
   - 💰 Paid: A partir de $49.99/mês

3. **Data Provider Profissional:**
   - 💰 Economatica, Bloomberg, Refinitiv
   - ✅ Dados históricos completos
   - ✅ Qualidade institucional

### Longo Prazo (Produção)
1. **Integração MetaTrader 5:**
   - ✅ Dados históricos ilimitados
   - ✅ Execução real de trades
   - ✅ Já planejado no roadmap

2. **Cache Local:**
   - ✅ Armazenar dados coletados no TimescaleDB
   - ✅ Atualizar incrementalmente
   - ✅ Reduzir dependência de APIs externas

---

## 📝 Scripts Criados

### `scripts/collect_brapi.py`
Script de coleta incremental para futura expansão:
```bash
python scripts/collect_brapi.py --symbol ITUB4 --range 2y --interval 1h
```

**Status:** 🚧 Em desenvolvimento (limitado por BRAPI free)

---

## 🎯 Conclusão

**BRAPI Free Plan é adequado para:**
- ✅ Desenvolvimento e testes iniciais
- ✅ Dados recentes (últimos 3 meses)
- ✅ Estratégias daily-only
- ✅ Proof of concept

**BRAPI Free Plan NÃO é adequado para:**
- ❌ Backtesting histórico extenso (> 3 meses)
- ❌ Estratégias multi-timeframe complexas
- ❌ Produção com múltiplos ativos
- ❌ Trading algorítmico em escala

**Decisão:** Continuar com **Wave3 Daily** usando dados disponíveis e planejar upgrade quando necessário para produção.

---

**Última Atualização:** 15 de janeiro de 2026
**Autor:** Stock-IndiceDev Assistant
**Status:** ✅ Option B Implementada com Limitações Documentadas
