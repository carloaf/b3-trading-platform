# 📖 Guia Prático: Exportar Dados do ProfitChart

## 🎯 Objetivo
Exportar dados históricos do ProfitChart em formato CSV e importar para TimescaleDB.

---

## 📋 Pré-requisitos

✅ ProfitChart instalado via Wine  
✅ Dados históricos baixados no Profit  
✅ Container `b3-data-collector` rodando

---

## 🚀 Passo a Passo

### PASSO 1: Abrir ProfitChart

```bash
cd ~/.wine.backup_20260119_192254/drive_c/users/dellno/AppData/Roaming/Nelogica/Profit
wine profitchart.exe
```

**Aguarde:** O Profit pode demorar 30-60 segundos para abrir.

---

### PASSO 2: Criar Gráfico do Ativo

1. Na tela inicial, clique em **"Novo Gráfico"**
2. Digite o código do ativo (ex: **PETR4**)
3. Pressione **Enter**
4. O gráfico será exibido com as barras de preço

---

### PASSO 3: Configurar Período e Intervalo

**Para Dados Diários:**
- Clique no botão **"D"** (Diário) na barra superior
- Ajuste o período: **10 anos** (ou máximo disponível)

**Para Dados Intraday:**
- Clique em **"60 min"**, **"15 min"**, **"5 min"** ou **"1 min"**
- Ajuste o período: **3 meses** a **1 ano** (dependendo do intervalo)

---

### PASSO 4: Exportar para CSV

1. **Clique com botão direito** em qualquer lugar do gráfico
2. Selecione **"Exportar Dados"** (ou "Export Data")
3. Escolha formato: **CSV**
4. Selecione pasta de destino: `/tmp/profitpro_export/`
5. Nome do arquivo: `{SIMBOLO}_{INTERVALO}_{ANO_INICIAL}_{ANO_FINAL}.csv`
   - Exemplo: `PETR4_daily_2014_2024.csv`
   - Exemplo: `VALE3_60min_2023_2024.csv`
6. Clique em **"Salvar"**

**Formato CSV gerado:**
```csv
Data;Hora;Abertura;Máxima;Mínima;Fechamento;Volume
20/01/2026;00:00;30.50;30.80;30.40;30.75;1000000
21/01/2026;00:00;30.75;31.00;30.70;30.95;1200000
```

---

### PASSO 5: Importar para TimescaleDB

#### Importação Individual:

```bash
# Dados diários
docker exec b3-data-collector python /app/src/profitpro_integration.py import \
    /tmp/profitpro_export/PETR4_daily_2014_2024.csv \
    --table ohlcv_daily

# Dados 60 minutos
docker exec b3-data-collector python /app/src/profitpro_integration.py import \
    /tmp/profitpro_export/VALE3_60min_2023_2024.csv \
    --table ohlcv_60m

# Dados 15 minutos
docker exec b3-data-collector python /app/src/profitpro_integration.py import \
    /tmp/profitpro_export/ITUB4_15min_2024_2025.csv \
    --table ohlcv_15m
```

#### Importação em Lote:

```bash
# Importar todos os CSVs da pasta
docker exec b3-data-collector python /app/src/profitpro_integration.py import-batch \
    /tmp/profitpro_export \
    --pattern "*_daily_*.csv" \
    --table ohlcv_daily
```

---

### PASSO 6: Validar Dados Importados

```bash
# Conectar ao PostgreSQL
docker exec -it b3-timescaledb psql -U b3admin -d b3trading

# Verificar dados importados
SELECT 
    symbol,
    COUNT(*) as total_candles,
    MIN(time) as data_inicio,
    MAX(time) as data_fim
FROM ohlcv_daily
WHERE symbol IN ('PETR4', 'VALE3', 'ITUB4')
GROUP BY symbol
ORDER BY symbol;

# Verificar últimos 5 candles
SELECT time, symbol, open, high, low, close, volume
FROM ohlcv_daily
WHERE symbol = 'PETR4'
ORDER BY time DESC
LIMIT 5;
```

**Resultado esperado:**
```
 symbol | total_candles |  data_inicio       |    data_fim
--------+---------------+--------------------+--------------------
 ITUB4  |          2520 | 2014-01-02 00:00   | 2024-12-31 00:00
 PETR4  |          2520 | 2014-01-02 00:00   | 2024-12-31 00:00
 VALE3  |          2520 | 2014-01-02 00:00   | 2024-12-31 00:00
```

---

## 📊 Ativos Recomendados para Exportação

### Prioridade 1 (Top 10 Ibovespa):
```
PETR4  - Petrobras
VALE3  - Vale
ITUB4  - Itaú
BBDC4  - Bradesco
B3SA3  - B3
ABEV3  - Ambev
WEGE3  - Weg
RENT3  - Localiza
SUZB3  - Suzano
BBAS3  - Banco do Brasil
```

### Prioridade 2 (Top 20):
```
MGLU3  - Magazine Luiza
RADL3  - Raia Drogasil
EMBR3  - Embraer
CSNA3  - CSN
GGBR4  - Gerdau
USIM5  - Usiminas
SBSP3  - Sabesp
VIVT3  - Telefônica
BRFS3  - BRF
CIEL3  - Cielo
```

### Índices e Futuros:
```
IBOV   - Índice Ibovespa
DOLFUT - Dólar Futuro
INDFUT - Índice Futuro
WINM25 - Win (Mini Índice)
```

---

## ⏱️ Estimativa de Tempo

| Tarefa | Tempo por Ativo | Total (30 ativos) |
|--------|-----------------|-------------------|
| Exportar CSV (diário) | 2-3 minutos | 60-90 minutos |
| Importar para DB | 30 segundos | 15 minutos |
| Validação | 1 minuto | 30 minutos |
| **TOTAL** | **~4 minutos** | **~2 horas** |

**Otimização:** Exporte 5-10 ativos de uma vez, depois importe em batch.

---

## 🔧 Troubleshooting

### Problema: Profit não abre no Wine

**Solução:**
```bash
# Instalar dependências do Wine
sudo apt-get install wine-stable winetricks

# Configurar Wine
winetricks dotnet48 vcrun2019
```

### Problema: CSV com encoding errado

**Sintoma:** Caracteres especiais aparecem como `��`

**Solução:** Converter encoding ao importar:
```bash
# Converter de Windows-1252 para UTF-8
iconv -f WINDOWS-1252 -t UTF-8 arquivo_original.csv > arquivo_utf8.csv
```

### Problema: Erro "Table does not exist"

**Solução:** Criar hypertable manualmente:
```sql
-- Conectar ao PostgreSQL
docker exec -it b3-timescaledb psql -U b3admin -d b3trading

-- Criar tabela se não existir
CREATE TABLE IF NOT EXISTS ohlcv_60m (
    time TIMESTAMPTZ NOT NULL,
    symbol TEXT NOT NULL,
    open NUMERIC(10,2) NOT NULL,
    high NUMERIC(10,2) NOT NULL,
    low NUMERIC(10,2) NOT NULL,
    close NUMERIC(10,2) NOT NULL,
    volume BIGINT NOT NULL,
    CONSTRAINT ohlcv_60m_pkey PRIMARY KEY (time, symbol)
);

-- Converter para hypertable
SELECT create_hypertable('ohlcv_60m', 'time', if_not_exists => TRUE);

-- Criar índice
CREATE INDEX IF NOT EXISTS idx_ohlcv_60m_symbol_time 
ON ohlcv_60m(symbol, time DESC);
```

### Problema: Dados duplicados na importação

**Solução:** O script usa `ON CONFLICT DO NOTHING` automaticamente.

Verificar duplicatas:
```sql
SELECT symbol, time, COUNT(*) as duplicatas
FROM ohlcv_daily
GROUP BY symbol, time
HAVING COUNT(*) > 1;
```

---

## 📈 Próximos Passos

Após importar os dados:

1. **Testar backtesting com dados reais:**
   ```bash
   docker exec b3-data-collector python /app/src/backtest.py \
       --strategy Wave3 \
       --symbol PETR4 \
       --start-date 2023-01-01 \
       --end-date 2024-12-31 \
       --interval 60m
   ```

2. **Atualizar feature engineering para usar intraday:**
   - Adicionar features baseadas em 60min
   - Calcular volatilidade intraday
   - Detectar padrões de rompimento

3. **Retreinar modelos ML com dados intraday:**
   ```bash
   docker exec b3-data-collector python /app/src/train.py \
       --interval 60m \
       --lookback 90
   ```

---

## 🎯 Checklist de Sucesso

- [ ] ProfitChart abrindo corretamente
- [ ] 10 ativos exportados (diário)
- [ ] 10 ativos exportados (60min)
- [ ] Dados importados no TimescaleDB
- [ ] Validação de contagem e datas
- [ ] Backtest rodando com dados reais
- [ ] Comparação de resultados: diário vs 60min

---

*Última atualização: 20/01/2026 18:50*  
*Guia testado com ProfitChart via Wine no Ubuntu*
