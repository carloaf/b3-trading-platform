# 📊 Wave3 Paper Trading - Guia de Uso

## ✨ Implementado!

A classe **Wave3PaperTrader** foi implementada com sucesso e está pronta para operação.

---

## 📦 O Que Foi Criado

### 1. **Classe Principal** (`paper_trading_wave3.py`)

**Localização:** `services/execution-engine/src/paper_trading_wave3.py`

**Tamanho:** ~750 linhas

**Funcionalidades:**
- ✅ Scan automático de múltiplos símbolos (5min intervals)
- ✅ Geração de sinais Wave3 v2.1 em tempo real
- ✅ Execução simulada de trades com gestão de risco (2% capital/trade)
- ✅ Position sizing baseado em Kelly Criterion
- ✅ Gerenciamento de posições (stop loss / take profit automáticos)
- ✅ Coleta de features ML (103 features por trade)
- ✅ Persistência PostgreSQL (posições + trades + ML dataset)
- ✅ Snapshots diários de capital às 18:00
- ✅ Logs estruturados e informativos
- ✅ Trading hours validation (09:00-18:00 BRT, Seg-Sex)

### 2. **Script de Teste** (`test_paper_trading.sh`)

**Localização:** `scripts/test_paper_trading.sh`

**Modos:**
- 🧪 **Teste Rápido:** 1 símbolo (PETR4), 5 scans de 60s = 5 minutos total
- 🚀 **Teste Completo:** 5 símbolos, scan 300s, rodando em background

---

## 🚀 Como Usar

### **Passo 1: Preparação**

Certifique-se que os containers estão rodando:

```bash
docker-compose up -d
```

Verifique a saúde:

```bash
docker ps | grep b3
```

Deve mostrar:
- `b3-postgres` (healthy)
- `b3-timescaledb` (healthy)
- `b3-execution-engine` (running)

---

### **Passo 2: Aplicar Schema** (se ainda não aplicado)

```bash
docker exec -i b3-postgres psql -U b3trading_user -d b3trading_db \
  < infrastructure/postgres/paper_trading_schema.sql
```

Deve retornar: `CREATE TABLE` (x4), `CREATE VIEW` (x5), `CREATE FUNCTION` (x3) = 23 statements

---

### **Passo 3: Teste Rápido** (Recomendado para primeira vez)

```bash
bash scripts/test_paper_trading.sh
```

Escolha **opção 1** (Teste Rápido):
- ⏱️ Duração: 5 minutos
- 📊 Símbolo: PETR4 apenas
- 🔍 5 scans de 60 segundos

**O que vai acontecer:**
1. ✅ Valida containers e schema
2. 🗑️ Opção para limpar dados anteriores
3. 📸 Cria snapshot inicial (R$ 100k)
4. 🔍 Escaneia PETR4 a cada 60s por 5 minutos
5. 📊 Mostra status final (posições, P&L, trades)

**Saída esperada:**

```
🔍 Scan 1/5
📉 PETR4: nenhum sinal (ou score < 55)

🔍 Scan 2/5
🟢 NOVA POSIÇÃO ABERTA
============================================================
📊 Símbolo: PETR4
💰 Entry: R$ 38.45
🛑 Stop: R$ 37.12 (-3.46%)
🎯 Target: R$ 42.30 (+10.01%)
⭐ Score: 67/100
📈 R:R: 1:2.89
🔢 Size: 1500 ações (R$ 57,675.00)
⚠️  Risco: R$ 2,000.00 (2.0% do capital)
============================================================

...

✅ Teste concluído!
```

---

### **Passo 4: Produção** (5 símbolos em background)

Após testar, rode em produção:

```bash
bash scripts/test_paper_trading.sh
```

Escolha **opção 2** (Teste Completo):
- 📊 Símbolos: PETR4, VALE3, ITUB4, BBDC4, ABEV3
- ⏱️ Scan: a cada 5 minutos
- 🕐 Horário: 09:00-18:00 (apenas pregão)
- 🔄 Rodando em background

**Comandos úteis após iniciar:**

```bash
# Ver logs em tempo real
docker exec -it b3-execution-engine tail -f /app/logs/paper_trading_$(date +%Y-%m-%d).log

# Ver status no PostgreSQL
docker exec b3-postgres psql -U b3trading_user -d b3trading_db -c '
  SELECT * FROM paper_trading_summary
'

# Ver posições abertas
docker exec b3-postgres psql -U b3trading_user -d b3trading_db -c '
  SELECT symbol, entry_price, stop_loss, take_profit, 
         unrealized_pnl, unrealized_pnl_pct, wave3_score
  FROM paper_positions
'

# Ver progresso ML
docker exec b3-postgres psql -U b3trading_user -d b3trading_db -c '
  SELECT * FROM ml_collection_progress
'

# Parar paper trading
docker exec b3-execution-engine pkill -f paper_trading_wave3.py
```

---

## 📊 Monitoramento

### **Views PostgreSQL**

O schema criou 5 views úteis:

#### 1. **paper_trading_summary** - Resumo geral

```sql
SELECT * FROM paper_trading_summary;
```

Retorna:
- `total_trades`: Total de trades fechados
- `winning_trades` / `losing_trades`: Wins vs Losses
- `win_rate`: Taxa de acerto (%)
- `avg_return_pct`: Retorno médio por trade (%)
- `total_pnl`: P&L total realizado
- `sharpe_ratio`: Sharpe ratio
- `max_drawdown`: Máximo drawdown (%)

#### 2. **paper_trading_by_symbol** - Por ativo

```sql
SELECT * FROM paper_trading_by_symbol ORDER BY total_pnl DESC;
```

Mostra performance de cada símbolo.

#### 3. **ml_collection_progress** - Progresso ML

```sql
SELECT * FROM ml_collection_progress;
```

Mostra:
- `samples_collected`: Trades coletados
- `ml_readiness`: Status (not_ready, beta_ready, production_ready)
- `trades_to_next_milestone`: Quantos trades faltam para próxima meta

**Milestones:**
- 25 trades: Análise exploratória
- 50 trades: ML v2.5 Beta
- 100 trades: ML Production Ready

#### 4. **paper_equity_curve** - Curva de capital

```sql
SELECT * FROM paper_equity_curve ORDER BY snapshot_date;
```

Gera gráfico de equity curve (para Grafana).

---

## 🔧 Configurações

### **Parâmetros do Wave3PaperTrader**

Localizados na função `main()` em `paper_trading_wave3.py`:

```python
trader = Wave3PaperTrader(
    initial_capital=100000.0,         # Capital inicial (R$)
    quality_score_threshold=55,       # Score mínimo (55-100)
    max_positions=5,                  # Max posições simultâneas
    risk_per_trade=0.02,              # 2% do capital por trade
    
    # PostgreSQL (posições, trades, ML)
    db_host='localhost',
    db_port=5432,
    db_user='b3trading_user',
    db_password='b3trading_pass',
    db_name='b3trading_db',
    
    # TimescaleDB (OHLCV data)
    timescale_host='localhost',
    timescale_port=5433,
    timescale_user='b3trading_ts',
    timescale_password='b3trading_ts_pass',
    timescale_db='b3trading_market'
)
```

### **Ajustar Quality Score Threshold**

Se **nenhum sinal** aparecer nos testes:

```python
quality_score_threshold=55  # Original (conservador)
quality_score_threshold=45  # Mais permissivo (mais sinais)
```

Se **muitos sinais ruins**:

```python
quality_score_threshold=65  # Mais rigoroso (apenas sinais excelentes)
```

---

## 🐛 Troubleshooting

### **Problema 1: "Dados insuficientes"**

**Sintoma:**
```
⚠️  PETR4: dados daily insuficientes (45 candles)
```

**Causa:** TimescaleDB sem dados suficientes.

**Solução:**
```bash
# Verificar dados
docker exec b3-timescaledb psql -U b3trading_ts -d b3trading_market -c "
  SELECT symbol, COUNT(*) as candles
  FROM ohlcv_daily
  GROUP BY symbol
  ORDER BY candles DESC
"

# Importar dados (se necessário)
# Ver: PAPER_TRADING_SETUP.md - Seção "Importação de Dados"
```

---

### **Problema 2: "Nenhum sinal gerado"**

**Sintoma:**
```
📉 PETR4: nenhum sinal
📉 VALE3: nenhum sinal
...
```

**Causa:** Nenhum setup Wave3 válido no momento.

**Soluções:**
1. **Aguardar:** Wave3 é seletivo, pode levar horas/dias para gerar sinal de qualidade
2. **Reduzir quality_threshold:** 55 → 45 (menos rigoroso)
3. **Verificar dados:** Candles diários devem estar atualizados

---

### **Problema 3: Container não conecta**

**Sintoma:**
```
❌ Erro ao conectar bancos de dados: connection refused
```

**Solução:**
```bash
# Restart containers
docker-compose restart

# Verificar logs
docker logs b3-postgres
docker logs b3-timescaledb
docker logs b3-execution-engine
```

---

## 📈 Timeline de Coleta ML

Conforme [PAPER_TRADING_SETUP.md](../PAPER_TRADING_SETUP.md):

| Milestone | Trades | Prazo | Status ML |
|-----------|--------|-------|-----------|
| 🎯 Fase 0 | 0-24 | Semanas 1-4 | `not_ready` |
| 🎯 Fase 1 | 25-49 | Semanas 5-8 | `beta_ready` (análise exploratória) |
| 🎯 Fase 2 | 50-99 | Semanas 9-12 | `beta_ready` (ML v2.5 treinável) |
| 🎯 Fase 3 | 100+ | Semana 13+ | `production_ready` (ML v2.5 ativável) |

**Meta:** 100 trades até **Abril de 2026**

---

## 📝 Logs

Logs são salvos em:

```
/app/logs/paper_trading_YYYY-MM-DD.log
```

**Dentro do container:**

```bash
docker exec -it b3-execution-engine tail -f /app/logs/paper_trading_$(date +%Y-%m-%d).log
```

**Copiar para host:**

```bash
docker cp b3-execution-engine:/app/logs/paper_trading_$(date +%Y-%m-%d).log ./logs/
```

---

## 🎯 Próximos Passos

Após validar o paper trading:

1. **Integração Telegram Bot** - Alertas em tempo real
2. **Dashboard Grafana** - Visualização de métricas
3. **Relatórios Diários** - Email/Telegram com resumo
4. **Backtest Comparativo** - Wave3 paper vs backtest histórico
5. **ML v2.5 Training** - Quando atingir 50-100 trades

Ver detalhes em: [PAPER_TRADING_SETUP.md](../PAPER_TRADING_SETUP.md) - Seção "Fase 2 e 3"

---

## ✅ Checklist de Validação

Antes de colocar em produção 24/7:

- [ ] ✅ Schema PostgreSQL aplicado (4 tabelas + 5 views + 3 functions)
- [ ] ✅ Dados TimescaleDB disponíveis (>100 candles por símbolo)
- [ ] ✅ Teste rápido executado com sucesso (PETR4, 5 min)
- [ ] ⏳ Teste completo executado (5 símbolos, 1 dia de operação)
- [ ] ⏳ Pelo menos 1 trade aberto e fechado com sucesso
- [ ] ⏳ Views PostgreSQL retornando dados corretos
- [ ] ⏳ Logs estruturados e sem erros críticos
- [ ] ⏳ Snapshots diários sendo criados às 18:00

---

## 🆘 Suporte

Em caso de problemas:

1. Verificar logs: `docker logs b3-execution-engine`
2. Verificar schema: `docker exec b3-postgres psql -U b3trading_user -d b3trading_db -c "\dt"`
3. Verificar dados: `docker exec b3-timescaledb psql -U b3trading_ts -d b3trading_market -c "SELECT COUNT(*) FROM ohlcv_daily"`
4. Consultar documentação completa: [PAPER_TRADING_SETUP.md](../PAPER_TRADING_SETUP.md)

---

**Autor:** B3 Trading Platform  
**Versão:** 1.0 Production  
**Data:** 27 de Janeiro de 2026  
**Status:** ✅ Implementado e Pronto para Testes
