# Paper Trading Wave3 v2.1 - Guia de Setup

## 📊 Situação dos Dados (28/01/2026)

### Dados Disponíveis no TimescaleDB

**Total de registros:** 475.923 candles
- 15min: 338.847 candles (47 símbolos)
- 60min: 135.791 candles (58 símbolos)
- Daily: 1.285 candles (5 símbolos apenas)

### Ativos Prioritários (Paper Trading)

**Cobertura 100% atualizada até 28/01/2026:**

| Símbolo | 15min | 60min | Daily | Período | Status |
|---------|-------|-------|-------|---------|--------|
| PETR4   | 610   | 156   | ❌ 0  | 02/01-28/01/2026 | ✅ Pronto (60min) |
| VALE3   | 610   | 156   | ❌ 0  | 02/01-28/01/2026 | ✅ Pronto (60min) |
| ITUB4   | 610   | 156   | ❌ 0  | 02/01-28/01/2026 | ✅ Pronto (60min) |
| BBDC4   | 610   | 156   | ❌ 0  | 02/01-28/01/2026 | ✅ Pronto (60min) |
| ABEV3   | 609   | 155   | ❌ 0  | 02/01-28/01/2026 | ✅ Pronto (60min) |

**⚠️ Observação Importante:**
- Dados daily existem apenas para 5 símbolos específicos (JBSS3, MRFG3, NTCO3, CRFB3, RRRP3)
- Ativos prioritários têm ~4.000 candles históricos de 60min (suficiente!)
- Wave3 será adaptada para usar dados 60min como proxy de daily

---

## 🚀 Estratégia Wave3 - Adaptação para 60min

### Versão Original (Requer Daily + 60min)
```
Contexto Daily: MME 72 + MME 17
Gatilho 60min: Onda 3 de Elliott
Regra: 17 candles acima MME 17
```

### Versão Adaptada (Apenas 60min)
```
Contexto 60min: MME 288 (72 dias × 4 candles/dia = 288 períodos)
Contexto 60min: MME 68 (17 dias × 4 candles/dia = 68 períodos)
Gatilho 60min: Mesma lógica de Onda 3
Regra: 68 candles acima MME 68 (equivalente a 17 dias)
```

**Justificativa:**
- 1 dia = ~4 candles de 60min (4 horas de pregão)
- MME 72 daily ≈ MME 288 em 60min
- MME 17 daily ≈ MME 68 em 60min
- Mantém mesma filosofia: tendência longa + gatilho médio prazo

---

## 🛠️ Implementação

### Arquivos Criados

1. **`services/execution-engine/src/paper_trading_wave3.py`** (815 linhas)
   - Gerenciador completo de paper trading
   - Integração com Wave3Enhanced
   - Coleta automática de features ML (103 features)
   - Persistência PostgreSQL
   - Status: ✅ IMPLEMENTADO

2. **`scripts/run_paper_trading_wave3.py`** (274 linhas)
   - Runner CLI com modo teste e produção
   - Monitoramento em tempo real
   - Relatórios de performance
   - Status: ✅ IMPLEMENTADO

### Arquivos a Modificar

1. **`services/execution-engine/src/strategies/wave3_enhanced.py`**
   - [ ] Adicionar modo `intraday_only=True`
   - [ ] Substituir queries daily por agregação 60min
   - [ ] Ajustar parâmetros (72→288, 17→68)

---

## 📋 Checklist de Implementação

### Fase 1: Adaptação da Estratégia (ESTA SESSÃO)
- [x] Diagnosticar falta de dados daily
- [ ] Modificar Wave3Enhanced para modo intraday
- [ ] Testar com PETR4 (156 candles de jan/2026)
- [ ] Validar sinais gerados vs backtest histórico

### Fase 2: Teste em Produção (PRÓXIMA SEMANA)
- [ ] Executar paper trading por 7 dias (modo teste)
- [ ] Coletar 5-10 sinais gerados
- [ ] Comparar win rate vs backtest (77.8% esperado)
- [ ] Ajustar threshold de score se necessário

### Fase 3: Escala para 5 Ativos (APÓS VALIDAÇÃO)
- [ ] Expandir para VALE3, ITUB4, BBDC4, ABEV3
- [ ] Monitorar max 5 posições simultâneas
- [ ] Coletar features ML de todos os sinais
- [ ] Setup Grafana dashboard

### Fase 4: Coleta de Dados ML (3-6 MESES)
- [ ] Atingir 25 trades (milestone 1)
- [ ] Atingir 50 trades (milestone 2 - treinar ML beta)
- [ ] Atingir 100 trades (milestone 3 - treinar ML production)

---

## 🔧 Comandos Úteis

### Verificar Dados Disponíveis
```bash
# Cobertura dos 5 ativos prioritários
docker exec b3-timescaledb psql -U b3trading_ts -d b3trading_market -c "
SELECT symbol, COUNT(*) as candles_60min 
FROM ohlcv_60min 
WHERE symbol IN ('PETR4', 'VALE3', 'ITUB4', 'BBDC4', 'ABEV3')
GROUP BY symbol 
ORDER BY symbol;
"
```

### Executar Paper Trading

**Modo Teste (10 ciclos de 30s):**
```bash
docker exec b3-execution-engine python3 /app/scripts/run_paper_trading_wave3.py \
    --test \
    --symbols PETR4
```

**Modo Produção (1 ativo, scan 1h):**
```bash
docker exec b3-execution-engine python3 /app/scripts/run_paper_trading_wave3.py \
    --symbols PETR4 \
    --interval 3600 \
    --min-score 55
```

**Modo Produção (5 ativos, scan 1h):**
```bash
docker exec b3-execution-engine python3 /app/scripts/run_paper_trading_wave3.py \
    --symbols PETR4 VALE3 ITUB4 BBDC4 ABEV3 \
    --interval 3600 \
    --min-score 55 \
    --max-positions 5
```

### Monitorar Trades no Database

```bash
# Ver trades fechados (últimos 10)
docker exec b3-timescaledb psql -U b3trading_user -d b3trading_db -c "
SELECT id, symbol, entry_time, exit_time, pnl_pct, result, wave3_score
FROM paper_trades_wave3
ORDER BY exit_time DESC
LIMIT 10;
"

# Estatísticas acumuladas
docker exec b3-timescaledb psql -U b3trading_user -d b3trading_db -c "
SELECT 
    COUNT(*) as total_trades,
    AVG(pnl_pct) as avg_return_pct,
    SUM(CASE WHEN result = 'WIN' THEN 1 ELSE 0 END) as wins,
    SUM(CASE WHEN result = 'LOSS' THEN 1 ELSE 0 END) as losses,
    ROUND(SUM(CASE WHEN result = 'WIN' THEN 1 ELSE 0 END)::numeric / COUNT(*) * 100, 2) as win_rate
FROM paper_trades_wave3;
"
```

---

## 📊 Métricas de Sucesso

### Mínimo Aceitável (Baseline)
- Win Rate ≥ 60%
- Retorno médio por trade ≥ 2%
- Sharpe Ratio ≥ 1.0
- Max Drawdown < 15%

### Target (Backtest Wave3 v2.1)
- Win Rate: 77.8%
- Retorno médio: 6.42%
- Sharpe Ratio: 2.5+
- Max Drawdown < 10%

### Excelente (Superar Backtest)
- Win Rate ≥ 80%
- Retorno médio ≥ 8%
- Sharpe Ratio ≥ 3.0
- Max Drawdown < 5%

---

## ⚠️ Problemas Conhecidos e Soluções

### ❌ Problema 1: Wave3 requer dados daily
**Causa:** Ativos prioritários não têm dados daily importados  
**Solução:** Adaptar Wave3 para usar agregação 60min (288/68 períodos)  
**Status:** 🔄 EM ANDAMENTO

### ❌ Problema 2: Container não encontra scripts
**Causa:** Arquivos criados fora do container Docker  
**Solução:** `docker cp` para copiar scripts  
**Status:** ✅ RESOLVIDO

### ❌ Problema 3: Parâmetros `scan_interval_seconds` incorreto
**Causa:** API do paper_trading_wave3.py usa `scan_interval`  
**Solução:** Corrigir runner para usar nome correto  
**Status:** ✅ RESOLVIDO

---

## 🎯 Próximos Passos

1. **AGORA:** Modificar `wave3_enhanced.py` para modo intraday
2. **HOJE:** Testar com PETR4 em modo teste
3. **AMANHÃ:** Executar 24h em produção com 1 ativo
4. **ESTA SEMANA:** Escalar para 5 ativos se resultados ok
5. **PRÓXIMOS 3 MESES:** Coletar 50+ trades para ML v2.5

---

## 📚 Referências

- Backtest Wave3 v2.1: `INSTRUCOES.md` linhas 74-80
- Paper Trading Manager: `services/execution-engine/src/paper_trading_wave3.py`
- Runner CLI: `scripts/run_paper_trading_wave3.py`
- Dados ProfitChart: `/home/dellno/Área de trabalho/dadoshistoricos.csv/dados26/`

---

*Última atualização: 28 de Janeiro de 2026*  
*Status: 🔄 EM DESENVOLVIMENTO*  
*Responsável: Stock-IndiceDev Assistant*
