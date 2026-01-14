# 🚀 Próximos Passos: Machine Learning e Alertas

> **Status:** Planejamento  
> **Data:** 13 de Janeiro de 2026  
> **Pré-requisitos:** PASSO 10 concluído ✅

---

## 📊 Estado Atual do Projeto

### ✅ Implementado (PASSOS 1-10)

| Componente | Status | Descrição |
|------------|--------|-----------|
| Infraestrutura Docker | ✅ | 8 containers (postgres, timescaledb, redis, grafana, etc) |
| Data Collector | ✅ | Coleta via BRAPI + MetaTrader 5 |
| Execution Engine | ✅ | FastAPI com 6 estratégias OOP |
| Estratégias Base | ✅ | trend_following, mean_reversion, breakout, macd_crossover |
| Estratégias Avançadas | ✅ | rsi_divergence (4 padrões), dynamic_position_sizing (Kelly) |
| Backtest Engine | ✅ | Motor completo com métricas (Sharpe, drawdown, profit factor) |
| Strategy Manager | ✅ | Detecção de regime + seleção automática |
| Endpoint Adaptativo | ✅ | `/api/adaptive-signal` - regime-based strategy selection |
| Endpoint Comparação | ✅ | `/api/backtest/compare` - múltiplas estratégias |
| Walk-Forward Optimizer | ✅ | Optuna TPE + Rolling/Anchored validation |
| Paper Trading | ✅ | Simulação em tempo real |
| Frontend | ✅ | React dashboard |
| Grafana | ✅ | Monitoramento visual |

---

## 🧠 FASE 4: Machine Learning (PASSOS 11-13)

### PASSO 11: Feature Engineering 🔧

**Objetivo:** Criar features técnicas avançadas para ML.

#### 11.1. Features Técnicas Clássicas
```python
# services/execution-engine/src/ml/feature_engineering.py

class FeatureEngineer:
    """
    Cria features para machine learning.
    """
    
    def create_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Cria todas as features."""
        
        # 1. Momentum Features
        df['momentum_5'] = df['close'].pct_change(5)
        df['momentum_10'] = df['close'].pct_change(10)
        df['momentum_20'] = df['close'].pct_change(20)
        
        # 2. Volatility Features
        df['volatility_5'] = df['close'].rolling(5).std()
        df['volatility_20'] = df['close'].rolling(20).std()
        df['atr_ratio'] = calculate_atr(df, 14) / df['close']
        
        # 3. Trend Features
        df['ema_diff'] = calculate_ema(df, 9) - calculate_ema(df, 21)
        df['ema_diff_slope'] = df['ema_diff'].diff()
        df['adx'] = calculate_adx(df, 14)
        
        # 4. Volume Features
        df['volume_ratio'] = df['volume'] / df['volume'].rolling(20).mean()
        df['volume_trend'] = df['volume'].rolling(5).mean() / df['volume'].rolling(20).mean()
        
        # 5. Pattern Features
        df['doji'] = self._detect_doji(df)
        df['hammer'] = self._detect_hammer(df)
        df['engulfing'] = self._detect_engulfing(df)
        
        # 6. Price Position Features
        df['price_vs_ma20'] = (df['close'] - df['close'].rolling(20).mean()) / df['close']
        df['distance_to_high'] = (df['high'].rolling(20).max() - df['close']) / df['close']
        df['distance_to_low'] = (df['close'] - df['low'].rolling(20).min()) / df['close']
        
        return df
    
    def create_target(self, df: pd.DataFrame, lookahead: int = 5) -> pd.DataFrame:
        """Cria target para classificação."""
        
        # Forward return
        df['forward_return'] = df['close'].shift(-lookahead) / df['close'] - 1
        
        # Classificação: BUY(1), SELL(-1), HOLD(0)
        df['target'] = 0
        df.loc[df['forward_return'] > 0.02, 'target'] = 1   # BUY se > 2%
        df.loc[df['forward_return'] < -0.02, 'target'] = -1 # SELL se < -2%
        
        return df
```

#### 11.2. Features de Regime
```python
def create_regime_features(df: pd.DataFrame) -> pd.DataFrame:
    """Features baseadas em regime de mercado."""
    
    # Detectar regime
    regime = detect_market_regime(df)
    
    # One-hot encoding
    df['regime_trending_up'] = (regime == 'trending_up').astype(int)
    df['regime_trending_down'] = (regime == 'trending_down').astype(int)
    df['regime_ranging'] = (regime == 'ranging').astype(int)
    df['regime_volatile'] = (regime == 'volatile').astype(int)
    
    return df
```

#### 11.3. Feature Selection
```python
from sklearn.feature_selection import SelectKBest, mutual_info_classif

def select_features(X, y, k=20):
    """Seleciona top K features."""
    
    selector = SelectKBest(mutual_info_classif, k=k)
    X_selected = selector.fit_transform(X, y)
    
    # Features selecionadas
    selected_features = X.columns[selector.get_support()].tolist()
    
    return X_selected, selected_features
```

#### 11.4. Normalização
```python
from sklearn.preprocessing import RobustScaler

def normalize_features(X_train, X_test):
    """Normaliza features usando RobustScaler."""
    
    scaler = RobustScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    return X_train_scaled, X_test_scaled, scaler
```

**Arquivos a criar:**
- `services/execution-engine/src/ml/__init__.py`
- `services/execution-engine/src/ml/feature_engineering.py`
- `services/execution-engine/src/ml/utils.py`

**Endpoint:**
```bash
POST /api/ml/features
{
  "symbol": "PETR4",
  "start_date": "2025-01-13",
  "end_date": "2026-01-12",
  "feature_groups": ["momentum", "volatility", "trend", "volume"]
}
```

---

### PASSO 12: Modelo de Classificação de Sinais 🎯

**Objetivo:** Filtrar sinais usando Random Forest / XGBoost.

#### 12.1. Modelo Random Forest
```python
# services/execution-engine/src/ml/signal_classifier.py

from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import TimeSeriesSplit
import joblib

class SignalClassifier:
    """
    Classificador de sinais usando Random Forest.
    """
    
    def __init__(self, n_estimators: int = 200):
        self.model = RandomForestClassifier(
            n_estimators=n_estimators,
            max_depth=10,
            min_samples_split=100,
            min_samples_leaf=50,
            random_state=42,
            n_jobs=-1
        )
        self.scaler = None
        self.feature_names = None
    
    def train(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        cv_splits: int = 5
    ):
        """Treina modelo com cross-validation."""
        
        # Time Series Cross-Validation
        tscv = TimeSeriesSplit(n_splits=cv_splits)
        
        scores = []
        for train_idx, val_idx in tscv.split(X):
            X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
            y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]
            
            # Normalizar
            scaler = RobustScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_val_scaled = scaler.transform(X_val)
            
            # Treinar
            self.model.fit(X_train_scaled, y_train)
            
            # Avaliar
            score = self.model.score(X_val_scaled, y_val)
            scores.append(score)
        
        # Treinar no dataset completo
        self.scaler = RobustScaler()
        X_scaled = self.scaler.fit_transform(X)
        self.model.fit(X_scaled, y)
        
        self.feature_names = X.columns.tolist()
        
        return {
            "cv_scores": scores,
            "mean_accuracy": np.mean(scores),
            "std_accuracy": np.std(scores)
        }
    
    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Prediz probabilidades."""
        X_scaled = self.scaler.transform(X)
        return self.model.predict_proba(X_scaled)
    
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Prediz classe."""
        X_scaled = self.scaler.transform(X)
        return self.model.predict(X_scaled)
    
    def get_feature_importance(self) -> pd.DataFrame:
        """Retorna importância das features."""
        importance = pd.DataFrame({
            'feature': self.feature_names,
            'importance': self.model.feature_importances_
        }).sort_values('importance', ascending=False)
        
        return importance
    
    def save(self, path: str):
        """Salva modelo."""
        joblib.dump({
            'model': self.model,
            'scaler': self.scaler,
            'feature_names': self.feature_names
        }, path)
    
    @classmethod
    def load(cls, path: str):
        """Carrega modelo."""
        data = joblib.load(path)
        instance = cls()
        instance.model = data['model']
        instance.scaler = data['scaler']
        instance.feature_names = data['feature_names']
        return instance
```

#### 12.2. XGBoost Classifier
```python
import xgboost as xgb

class XGBoostSignalClassifier:
    """
    Classificador usando XGBoost (mais rápido).
    """
    
    def __init__(self):
        self.model = xgb.XGBClassifier(
            n_estimators=200,
            max_depth=6,
            learning_rate=0.1,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            n_jobs=-1
        )
```

#### 12.3. Integração com Estratégias
```python
# services/execution-engine/src/strategies/ml_enhanced_strategy.py

class MLEnhancedStrategy(BaseStrategy):
    """
    Estratégia com filtro ML.
    """
    
    def __init__(self, base_strategy: str, ml_model_path: str):
        super().__init__("ml_enhanced_" + base_strategy)
        
        # Carregar estratégia base
        strategy_manager = StrategyManager()
        self.base_strategy = strategy_manager.get_strategy(base_strategy)
        
        # Carregar modelo ML
        self.ml_classifier = SignalClassifier.load(ml_model_path)
        
        # Feature engineer
        self.feature_engineer = FeatureEngineer()
    
    def run(self, df: pd.DataFrame) -> pd.DataFrame:
        """Executa estratégia com filtro ML."""
        
        # Gerar sinais da estratégia base
        df = self.base_strategy.run(df)
        
        # Criar features
        df = self.feature_engineer.create_features(df)
        
        # Predizer com ML
        features = self.feature_engineer.get_feature_columns()
        X = df[features].fillna(0)
        
        ml_predictions = self.ml_classifier.predict(X)
        ml_probas = self.ml_classifier.predict_proba(X)
        
        # Filtrar sinais
        df['ml_signal'] = ml_predictions
        df['ml_confidence'] = ml_probas.max(axis=1)
        
        # Aplicar filtro: só aceitar sinais se ML concorda E confiança > 0.6
        df['signal_filtered'] = df['signal']
        mask_disagree = (df['signal'] != df['ml_signal']) | (df['ml_confidence'] < 0.6)
        df.loc[mask_disagree, 'signal_filtered'] = 'HOLD'
        
        # Substituir sinal original
        df['signal'] = df['signal_filtered']
        
        return df
```

**Endpoint de Treinamento:**
```bash
POST /api/ml/train
{
  "symbol": "PETR4",
  "start_date": "2024-01-01",
  "end_date": "2025-12-31",
  "model_type": "random_forest",
  "feature_groups": ["all"],
  "cv_splits": 5
}
```

**Endpoint de Predição:**
```bash
POST /api/ml/predict
{
  "symbol": "PETR4",
  "model_path": "models/rf_classifier_20260113.pkl",
  "data": {...}
}
```

---

### PASSO 13: Detecção de Anomalias 🚨

**Objetivo:** Detectar condições anormais de mercado.

#### 13.1. Isolation Forest
```python
# services/execution-engine/src/ml/anomaly_detector.py

from sklearn.ensemble import IsolationForest

class AnomalyDetector:
    """
    Detecta anomalias usando Isolation Forest.
    """
    
    def __init__(self, contamination: float = 0.1):
        self.model = IsolationForest(
            contamination=contamination,
            random_state=42,
            n_jobs=-1
        )
        self.scaler = RobustScaler()
    
    def fit(self, df: pd.DataFrame):
        """Treina detector."""
        
        # Features para detecção
        features = [
            'volatility_20',
            'volume_ratio',
            'momentum_10',
            'atr_ratio',
            'distance_to_high',
            'distance_to_low'
        ]
        
        X = df[features].fillna(0)
        X_scaled = self.scaler.fit_transform(X)
        
        self.model.fit(X_scaled)
    
    def predict(self, df: pd.DataFrame) -> np.ndarray:
        """Detecta anomalias."""
        X = df[features].fillna(0)
        X_scaled = self.scaler.transform(X)
        
        # -1 = anomalia, 1 = normal
        predictions = self.model.predict(X_scaled)
        
        # Anomaly score (menor = mais anômalo)
        scores = self.model.score_samples(X_scaled)
        
        return predictions, scores
```

#### 13.2. Alertas de Anomalia
```python
def check_anomalies(df: pd.DataFrame) -> Dict:
    """Verifica e alerta sobre anomalias."""
    
    detector = AnomalyDetector()
    detector.fit(df.iloc[:-50])  # Treinar em histórico
    
    # Detectar em últimos 10 candles
    recent = df.tail(10)
    predictions, scores = detector.predict(recent)
    
    anomalies = []
    for i, (pred, score) in enumerate(zip(predictions, scores)):
        if pred == -1:
            anomalies.append({
                "timestamp": recent.iloc[i]['time'],
                "score": float(score),
                "severity": "high" if score < -0.5 else "medium"
            })
    
    return {
        "has_anomalies": len(anomalies) > 0,
        "count": len(anomalies),
        "anomalies": anomalies
    }
```

**Endpoint:**
```bash
GET /api/ml/anomalies/{symbol}?timeframe=1d&lookback=100
```

---

## 📢 FASE 5: Alertas e Notificações (PASSOS 14-15)

### PASSO 14: Integração Telegram Bot 📱

**Objetivo:** Notificações em tempo real via Telegram.

#### 14.1. Setup Bot
```python
# services/execution-engine/src/notifications/telegram_bot.py

import asyncio
from telegram import Bot
from telegram.error import TelegramError

class TelegramNotifier:
    """
    Envia notificações via Telegram.
    """
    
    def __init__(self, bot_token: str, chat_id: str):
        self.bot = Bot(token=bot_token)
        self.chat_id = chat_id
    
    async def send_signal_alert(self, signal: Dict):
        """Envia alerta de sinal."""
        
        message = f"""
🎯 **NOVO SINAL DE TRADING**

📊 Ativo: {signal['symbol']}
📈 Ação: {signal['action']}
💪 Força: {signal['strength']:.2f}
💰 Preço: R$ {signal['price']:.2f}
🛑 Stop Loss: R$ {signal['stop_loss']:.2f}
🎯 Take Profit: R$ {signal['take_profit']:.2f}

📅 {signal['timestamp']}
        """
        
        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode='Markdown'
            )
        except TelegramError as e:
            logger.error(f"Erro ao enviar Telegram: {e}")
    
    async def send_anomaly_alert(self, anomaly: Dict):
        """Alerta de anomalia."""
        
        severity_emoji = "🔴" if anomaly['severity'] == 'high' else "🟡"
        
        message = f"""
{severity_emoji} **ANOMALIA DETECTADA**

⚠️ Condição anormal de mercado
📊 Score: {anomaly['score']:.3f}
📅 {anomaly['timestamp']}

⚡ Recomendação: Reduzir exposição
        """
        
        await self.bot.send_message(
            chat_id=self.chat_id,
            text=message,
            parse_mode='Markdown'
        )
    
    async def send_daily_summary(self, summary: Dict):
        """Resumo diário."""
        
        message = f"""
📊 **RESUMO DIÁRIO**

💰 P&L: R$ {summary['pnl']:.2f}
📈 Return: {summary['return_pct']:.2f}%
🎯 Trades: {summary['trades']}
✅ Win Rate: {summary['win_rate']:.1f}%

📅 {summary['date']}
        """
        
        await self.bot.send_message(
            chat_id=self.chat_id,
            text=message,
            parse_mode='Markdown'
        )
```

#### 14.2. Comandos do Bot
```python
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram import Update

class TradingBot:
    """Bot Telegram interativo."""
    
    def __init__(self, token: str):
        self.app = Application.builder().token(token).build()
        
        # Registrar comandos
        self.app.add_handler(CommandHandler("start", self.cmd_start))
        self.app.add_handler(CommandHandler("status", self.cmd_status))
        self.app.add_handler(CommandHandler("signals", self.cmd_signals))
        self.app.add_handler(CommandHandler("positions", self.cmd_positions))
        self.app.add_handler(CommandHandler("stop", self.cmd_stop))
    
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /start"""
        await update.message.reply_text(
            "🤖 B3 Trading Bot iniciado!\n\n"
            "Comandos disponíveis:\n"
            "/status - Status do sistema\n"
            "/signals - Últimos sinais\n"
            "/positions - Posições abertas\n"
            "/stop - Parar alertas"
        )
    
    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Status do sistema."""
        # Buscar status da API
        response = requests.get("http://execution-engine:3008/health")
        status = response.json()
        
        await update.message.reply_text(
            f"✅ Sistema: {status['status']}\n"
            f"📅 {status['timestamp']}"
        )
    
    async def cmd_signals(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Últimos sinais."""
        # Buscar sinais
        response = requests.get(
            "http://execution-engine:3008/api/signals/scan",
            params={"symbols": "PETR4,VALE3,ITUB4"}
        )
        signals = response.json()
        
        message = "📊 **SINAIS ATIVOS**\n\n"
        for sig in signals['results']:
            if sig['signal']['action'] != 'HOLD':
                message += f"{sig['symbol']}: {sig['signal']['action']} ({sig['signal']['strength']:.2f})\n"
        
        await update.message.reply_text(message)
    
    def run(self):
        """Inicia bot."""
        self.app.run_polling()
```

**Configuração:**
1. Criar bot no @BotFather
2. Obter token
3. Adicionar ao `.env`:
```bash
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=123456789
```

**Endpoint:**
```bash
POST /api/notifications/telegram/send
{
  "type": "signal",
  "data": {...}
}
```

---

### PASSO 15: Integração Discord Webhook 💬

**Objetivo:** Notificações em canal Discord.

#### 15.1. Discord Notifier
```python
# services/execution-engine/src/notifications/discord_notifier.py

import aiohttp
from typing import Dict, List

class DiscordNotifier:
    """
    Envia notificações via Discord Webhook.
    """
    
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
    
    async def send_embed(
        self,
        title: str,
        description: str,
        color: int = 0x00ff00,
        fields: List[Dict] = None
    ):
        """Envia embed formatado."""
        
        embed = {
            "title": title,
            "description": description,
            "color": color,
            "timestamp": datetime.now().isoformat()
        }
        
        if fields:
            embed["fields"] = fields
        
        payload = {"embeds": [embed]}
        
        async with aiohttp.ClientSession() as session:
            async with session.post(self.webhook_url, json=payload) as response:
                if response.status != 204:
                    logger.error(f"Discord webhook error: {response.status}")
    
    async def send_signal_alert(self, signal: Dict):
        """Alerta de sinal."""
        
        color = 0x00ff00 if signal['action'] == 'BUY' else 0xff0000
        
        fields = [
            {"name": "📊 Ativo", "value": signal['symbol'], "inline": True},
            {"name": "📈 Ação", "value": signal['action'], "inline": True},
            {"name": "💪 Força", "value": f"{signal['strength']:.2f}", "inline": True},
            {"name": "💰 Preço", "value": f"R$ {signal['price']:.2f}", "inline": True},
            {"name": "🛑 Stop Loss", "value": f"R$ {signal['stop_loss']:.2f}", "inline": True},
            {"name": "🎯 Take Profit", "value": f"R$ {signal['take_profit']:.2f}", "inline": True}
        ]
        
        await self.send_embed(
            title="🎯 Novo Sinal de Trading",
            description=f"Estratégia detectou oportunidade em {signal['symbol']}",
            color=color,
            fields=fields
        )
```

**Configuração:**
1. Criar webhook no Discord (Configurações do Canal → Integrações → Webhooks)
2. Adicionar ao `.env`:
```bash
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
```

---

## 📋 Resumo dos Próximos Passos

### FASE 4: Machine Learning
- [ ] **PASSO 11:** Feature Engineering (momentum, volatility, trend, volume, patterns)
- [ ] **PASSO 12:** Modelo Random Forest / XGBoost para filtrar sinais
- [ ] **PASSO 13:** Isolation Forest para detecção de anomalias

### FASE 5: Alertas
- [ ] **PASSO 14:** Bot Telegram com comandos interativos
- [ ] **PASSO 15:** Webhooks Discord com embeds formatados

### FASE 6: Produção (PASSOS 16-18)
- [ ] **PASSO 16:** Alertas Grafana (drawdown, serviços degradados)
- [ ] **PASSO 17:** Otimização de performance (cache, compressão)
- [ ] **PASSO 18:** Documentação final (Swagger, deployment, runbook)

---

## 🔧 Dependências Adicionais

```txt
# Machine Learning
scikit-learn==1.4.0
xgboost==2.0.3
joblib==1.3.2
imbalanced-learn==0.12.0

# Telegram
python-telegram-bot==20.7

# Discord
aiohttp==3.9.1
discord-webhook==1.3.0
```

---

**Última atualização:** 13 de Janeiro de 2026
