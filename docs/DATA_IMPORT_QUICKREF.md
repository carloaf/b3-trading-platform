# 📋 Quick Reference - Importação de Dados

**Última Atualização:** 28/01/2026

---

## ⚡ Comando Rápido de Importação

```bash
docker run --rm -it \
  -v "/home/dellno/Área de trabalho/dadoshistoricos.csv:/data" \
  -v /home/dellno/worksapace/b3-trading-platform/scripts:/scripts \
  --network b3-trading-platform_b3-network \
  python:3.11-slim bash -c "pip install -q asyncpg loguru && python3 /scripts/import_historical_data.py"
```

---

## 📊 Formatos CSV

### Intraday (15min, 60min) - 9 COLUNAS

```csv
symbol;date;time;open;high;low;close;volume_brl;volume_qty
PETR4;30/12/2024;17:00:00;32,83;32,97;32,80;32,80;215181183,90;6552300
```

### Diário - 8 COLUNAS (SEM time)

```csv
symbol;date;open;high;low;close;volume_brl;volume_qty
PETR4;30/12/2024;32,43;32,97;32,42;32,80;733138158,20;22355600
```

---

## 🗂️ Localização dos Arquivos

```
/home/dellno/Área de trabalho/dadoshistoricos.csv/
├── dados23e24/  (157 arquivos, 58 símbolos, 2023-2025)
└── dados26/     (72 arquivos, 24 símbolos, jan/2026)
```

---

## 🗄️ Banco de Dados

**TimescaleDB:** `b3trading_market` (porta 5433)

**Tabelas:**
- `ohlcv_15min` - 338.847 registros
- `ohlcv_60min` - 407.470 registros
- `ohlcv_daily` - 28.942 registros

**Total:** 775.259 registros (28/01/2026)

---

## ✅ Validação Rápida

```sql
-- Total por tabela
SELECT 'ohlcv_15min' as tabela, COUNT(*) FROM ohlcv_15min
UNION ALL
SELECT 'ohlcv_60min', COUNT(*) FROM ohlcv_60min
UNION ALL
SELECT 'ohlcv_daily', COUNT(*) FROM ohlcv_daily;

-- Prioritários (diário)
SELECT symbol, COUNT(*) as candles, MIN(time), MAX(time)
FROM ohlcv_daily
WHERE symbol IN ('PETR4', 'VALE3', 'ITUB4', 'BBDC4', 'ABEV3')
GROUP BY symbol;
```

---

## 🐛 Troubleshooting

| Erro | Solução |
|------|---------|
| "Pasta não encontrada" | Verificar path e volume mount `-v` |
| "Connection refused" | `docker compose up -d b3-timescaledb` |
| "Nenhum registro válido" | Verificar formato CSV (8 vs 9 colunas) |
| "ModuleNotFoundError" | Garantir `pip install asyncpg loguru` |

---

## 📞 Documentação Completa

Ver: [docs/DATA_IMPORT_GUIDE.md](DATA_IMPORT_GUIDE.md)
