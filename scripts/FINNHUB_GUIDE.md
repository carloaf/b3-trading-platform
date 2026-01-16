# 📊 Finnhub Data Collector - Guia Rápido

## 🚀 Como Testar

### 1. Obter API Key (GRÁTIS)

Acesse: **https://finnhub.io/register**

- ✅ Cadastro rápido (email + senha)
- ✅ Confirmação por email (imediato)
- ✅ Key visível em: https://finnhub.io/dashboard

### 2. Testar com sua key

```bash
# Teste rápido com ITUB4
docker exec b3-execution-engine python3 /tmp/finnhub_collector.py \
  --symbols ITUB4 \
  --api-key d5kolfhr01qt47mei93gd5kolfhr01qt47mei940 \
  --db-host timescaledb \
  --db-port 5432 \
  --db-name b3trading_market \
  --db-user b3trading_ts \
  --db-password b3trading_ts_pass \
  --daily-only
```

### 3. Coletar múltiplos ativos

```bash
# Todos os 10 ativos (daily + hourly)
docker exec b3-execution-engine python3 /tmp/finnhub_collector.py \
  --symbols ITUB4,VALE3,PETR4,MGLU3,BBDC4,ABEV3,WEGE3,RENT3,SUZB3,B3SA3 \
  --api-key SUA_KEY_AQUI \
  --db-host timescaledb \
  --db-port 5432 \
  --db-name b3trading_market \
  --db-user b3trading_ts \
  --db-password b3trading_ts_pass
```

## ⚡ Vantagens Finnhub Free Tier

| Característica | Alpha Vantage Free | Finnhub Free |
|----------------|-------------------|--------------|
| **Rate Limit** | 5 calls/min | 60 calls/min |
| **Daily Limit** | 25 calls/day | Sem limite dia |
| **Daily Data** | 100 bars | 730 days (2 anos) |
| **Intraday Data** | Premium only | 1 ano free |
| **Resoluções** | Diário apenas | 1,5,15,30,60min + D,W,M |

## 📊 Formatos B3 Testados

O script testa automaticamente:
- `ITUB4.SA` (Yahoo Finance style)
- `ITUB4.SAO` (Alternative)
- `SA:ITUB4` (Exchange prefix)
- `BVMF:ITUB4` (BVMF exchange)

## 🎯 Expectativa

**Se funcionar:**
- ✅ 2 anos de daily data
- ✅ 1 ano de hourly data  
- ✅ 60 req/min (muito rápido)
- ✅ Sem limite diário

**Total estimado para 10 ativos:**
- ~30 API calls (test formats + daily + hourly)
- Tempo: ~1-2 minutos
- **Muito melhor que Alpha Vantage!**

---

## ❌ RESULTADO DO TESTE

**Data:** 15 de Janeiro de 2026  
**Conclusão:** **Finnhub NÃO suporta ações B3**

Formatos testados:
- ❌ `ITUB4.SA` - No data
- ❌ `ITUB4.SAO` - No data  
- ❌ `SA:ITUB4` - No data
- ❌ `BVMF:ITUB4` - No data

**Finnhub cobre:**
- ✅ US stocks (NYSE, NASDAQ)
- ✅ Crypto
- ✅ Forex
- ❌ **Brazil/B3** - Not supported

---

**Status:** B3 não disponível - Fonte descartada  
**Criado:** 15 de Janeiro de 2026
