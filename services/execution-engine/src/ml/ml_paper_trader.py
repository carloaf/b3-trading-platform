"""
ML Paper Trader
B3 Trading Platform

Paper trading automatizado com Machine Learning.
Monitora mercado, gera sinais ML-filtered e executa trades automaticamente.
"""

import asyncio
import joblib
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from loguru import logger

from ..paper_trading import PaperTradingManager
from .feature_engineer import FeatureEngineer
from .signal_classifier import SignalClassifier
from .anomaly_detector import AnomalyDetector


class MLPaperTrader:
    """
    Paper Trader automatizado com ML.
    
    Workflow:
    1. Monitora preços em intervalo definido
    2. Calcula features técnicas
    3. Detecta anomalias
    4. Gera sinais com estratégia base
    5. Filtra sinais com ML
    6. Executa trades automaticamente
    7. Gerencia stop loss / take profit
    """
    
    def __init__(
        self,
        paper_manager: PaperTradingManager,
        model_path: str,
        strategy_name: str = "mean_reversion",
        strategy_params: Dict = None,
        confidence_threshold: float = 0.65,
        max_position_size_pct: float = 0.2,  # 20% do capital
        check_interval: int = 60,  # segundos
        enable_anomaly_filter: bool = True,
        anomaly_threshold: float = 0.1  # 10% anomalies = cautela
    ):
        """
        Inicializa ML Paper Trader.
        
        Args:
            paper_manager: Gerenciador de paper trading
            model_path: Caminho do modelo ML treinado
            strategy_name: Nome da estratégia base
            strategy_params: Parâmetros da estratégia
            confidence_threshold: Threshold mínimo de confiança ML
            max_position_size_pct: % máxima do capital por posição
            check_interval: Intervalo de verificação em segundos
            enable_anomaly_filter: Se deve usar filtro de anomalias
            anomaly_threshold: % de anomalias que indica mercado instável
        """
        self.paper_manager = paper_manager
        self.model_path = model_path
        self.strategy_name = strategy_name
        self.strategy_params = strategy_params or {}
        self.confidence_threshold = confidence_threshold
        self.max_position_size_pct = max_position_size_pct
        self.check_interval = check_interval
        self.enable_anomaly_filter = enable_anomaly_filter
        self.anomaly_threshold = anomaly_threshold
        
        # Componentes ML
        self.classifier: Optional[SignalClassifier] = None
        self.feature_engineer = FeatureEngineer()
        self.anomaly_detector: Optional[AnomalyDetector] = None
        
        # Estado
        self.is_running = False
        self.last_check: Optional[datetime] = None
        self.signals_generated = 0
        self.signals_accepted = 0
        self.signals_rejected = 0
        self.anomalies_detected = 0
        
        # Histórico de decisões
        self.decision_history: List[Dict] = []
        
    def load_model(self) -> bool:
        """
        Carrega modelo ML.
        
        Returns:
            True se sucesso
        """
        try:
            model_data = joblib.load(self.model_path)
            
            self.classifier = SignalClassifier(model_type=model_data.get('model_type', 'random_forest'))
            self.classifier.model = model_data['model']
            self.classifier.feature_names = model_data.get('feature_names')
            self.classifier.feature_importance = model_data.get('feature_importance')
            self.classifier.training_metrics = model_data.get('training_metrics')
            
            logger.info(f"✅ Modelo carregado: {self.model_path}")
            logger.info(f"   Tipo: {model_data.get('model_type')}")
            logger.info(f"   Features: {len(model_data.get('feature_names', []))}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao carregar modelo: {str(e)}")
            return False
    
    async def fetch_recent_data(
        self,
        symbol: str,
        timeframe: str,
        bars: int,
        ts_pool
    ) -> Optional[pd.DataFrame]:
        """
        Busca dados recentes do banco.
        
        Args:
            symbol: Símbolo do ativo
            timeframe: Timeframe (ex: '1m', '5m', '1d')
            bars: Número de barras
            ts_pool: Pool de conexão TimescaleDB
            
        Returns:
            DataFrame com OHLCV ou None
        """
        try:
            # Calcular data de início
            now = datetime.now()
            
            # Estimar duração baseado no timeframe
            if timeframe == '1m':
                start_time = now - timedelta(minutes=bars + 10)
            elif timeframe == '5m':
                start_time = now - timedelta(minutes=(bars + 10) * 5)
            elif timeframe == '15m':
                start_time = now - timedelta(minutes=(bars + 10) * 15)
            elif timeframe == '1h':
                start_time = now - timedelta(hours=bars + 10)
            else:  # 1d
                start_time = now - timedelta(days=bars + 10)
            
            query = """
            SELECT time, open, high, low, close, volume
            FROM ohlcv_data
            WHERE symbol = $1 AND timeframe = $2
              AND time >= $3
            ORDER BY time DESC
            LIMIT $4
            """
            
            rows = await ts_pool.fetch(query, symbol, timeframe, start_time, bars)
            
            if not rows or len(rows) < 50:
                logger.warning(f"Dados insuficientes: {len(rows) if rows else 0} barras")
                return None
            
            # Converter para DataFrame
            df = pd.DataFrame(rows, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
            df['time'] = pd.to_datetime(df['time'])
            df = df.sort_values('time').reset_index(drop=True)
            
            # Converter para float
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = df[col].astype(float)
            
            return df
            
        except Exception as e:
            logger.error(f"Erro ao buscar dados: {str(e)}")
            return None
    
    async def check_anomalies(self, df: pd.DataFrame) -> Dict:
        """
        Verifica anomalias no mercado.
        
        Returns:
            Dict com análise de anomalias
        """
        if not self.enable_anomaly_filter:
            return {"enabled": False, "is_safe": True}
        
        try:
            # Criar features
            df_features = self.feature_engineer.create_all_features(df.copy())
            df_features = self.feature_engineer.normalize_features(df_features)
            df_features = df_features.dropna()
            
            if len(df_features) < 30:
                return {"enabled": True, "is_safe": False, "reason": "dados_insuficientes"}
            
            # Treinar detector
            feature_cols = [c for c in df_features.columns 
                          if c not in ['open', 'high', 'low', 'close', 'volume']]
            X = df_features[feature_cols]
            
            if self.anomaly_detector is None:
                self.anomaly_detector = AnomalyDetector(contamination=self.anomaly_threshold)
                self.anomaly_detector.fit(X)
            
            # Detectar anomalias
            result = self.anomaly_detector.detect_anomalies(X, df_features[['close', 'volume']])
            
            anomaly_rate = result['anomaly_rate'] / 100.0
            is_safe = anomaly_rate < self.anomaly_threshold
            
            if not is_safe:
                self.anomalies_detected += 1
                logger.warning(f"⚠️ Mercado instável detectado! Anomaly rate: {anomaly_rate:.2%}")
            
            return {
                "enabled": True,
                "is_safe": is_safe,
                "anomaly_rate": anomaly_rate,
                "n_anomalies": result['n_anomalies'],
                "total_samples": result['total_samples']
            }
            
        except Exception as e:
            logger.error(f"Erro ao detectar anomalias: {str(e)}")
            return {"enabled": True, "is_safe": False, "reason": str(e)}
    
    async def generate_ml_signal(
        self,
        df: pd.DataFrame,
        current_price: float
    ) -> Optional[Dict]:
        """
        Gera sinal filtrado por ML.
        
        Returns:
            Dict com sinal e confiança ou None
        """
        try:
            # Importar estratégia
            from ..strategies.strategy_manager import StrategyManager
            
            # Criar features
            df_features = self.feature_engineer.create_all_features(df.copy())
            df_features = self.feature_engineer.normalize_features(df_features)
            df_features = df_features.dropna()
            
            if len(df_features) < 50:
                return None
            
            # Gerar sinal base
            strategy_manager = StrategyManager()
            strategy = strategy_manager.get_strategy(self.strategy_name, self.strategy_params)
            
            if strategy is None:
                logger.error(f"Estratégia não encontrada: {self.strategy_name}")
                return None
            
            df_signals = strategy.run(df_features.copy())
            
            # Pegar último sinal
            last_signal = df_signals['signal'].iloc[-1]
            
            # Converter BUY/SELL/HOLD para numérico
            signal_map = {'BUY': 1, 'SELL': -1, 'HOLD': 0}
            base_signal = signal_map.get(last_signal, 0)
            
            self.signals_generated += 1
            
            if base_signal == 0:
                return None
            
            # Filtrar com ML
            feature_cols = [c for c in df_features.columns 
                          if c not in ['open', 'high', 'low', 'close', 'volume']]
            X_last = df_features[feature_cols].iloc[[-1]]
            
            # Predição
            probas = self.classifier.predict_proba(X_last)[0]
            confidence = probas[1] if base_signal == 1 else probas[0]
            
            # Verificar threshold
            if confidence < self.confidence_threshold:
                self.signals_rejected += 1
                logger.info(f"❌ Sinal rejeitado: {last_signal} (confidence: {confidence:.2%})")
                return None
            
            self.signals_accepted += 1
            
            logger.info(f"✅ Sinal aceito: {last_signal} (confidence: {confidence:.2%})")
            
            return {
                "signal": last_signal,
                "numeric_signal": base_signal,
                "confidence": confidence,
                "current_price": current_price,
                "timestamp": datetime.now()
            }
            
        except Exception as e:
            logger.error(f"Erro ao gerar sinal ML: {str(e)}")
            return None
    
    async def execute_signal(
        self,
        symbol: str,
        signal_data: Dict,
        anomaly_check: Dict
    ) -> bool:
        """
        Executa sinal (abre ou fecha posição).
        
        Returns:
            True se executou
        """
        try:
            signal = signal_data['signal']
            price = signal_data['current_price']
            confidence = signal_data['confidence']
            
            # Verificar se mercado está seguro
            if not anomaly_check.get('is_safe', False):
                logger.warning("🚫 Trade cancelado: mercado instável")
                self._log_decision({
                    "timestamp": datetime.now(),
                    "symbol": symbol,
                    "signal": signal,
                    "confidence": confidence,
                    "executed": False,
                    "reason": "anomaly_detected",
                    "anomaly_rate": anomaly_check.get('anomaly_rate')
                })
                return False
            
            # Verificar se já tem posição
            existing_position = self.paper_manager.positions.get(symbol)
            
            if existing_position:
                # Fechar posição se sinal contrário
                if (existing_position.side == "BUY" and signal == "SELL") or \
                   (existing_position.side == "SELL" and signal == "BUY"):
                    
                    result = self.paper_manager.close_position(
                        symbol=symbol,
                        current_price=price,
                        reason=f"ml_signal_reversal (confidence: {confidence:.2%})"
                    )
                    
                    if result['status'] == 'success':
                        logger.info(f"💰 Posição fechada: {symbol} @ R$ {price:.2f}")
                        logger.info(f"   P&L: R$ {result['trade']['pnl']:.2f} ({result['trade']['return_pct']:.2%})")
                        
                        self._log_decision({
                            "timestamp": datetime.now(),
                            "symbol": symbol,
                            "action": "close",
                            "signal": signal,
                            "price": price,
                            "confidence": confidence,
                            "executed": True,
                            "pnl": result['trade']['pnl']
                        })
                        return True
                else:
                    logger.info(f"ℹ️ Já tem posição {existing_position.side} em {symbol}")
                    return False
            else:
                # Abrir nova posição
                # Calcular tamanho da posição
                max_position_value = self.paper_manager.capital * self.max_position_size_pct
                quantity = int(max_position_value / price)
                
                if quantity == 0:
                    logger.warning("Capital insuficiente para abrir posição")
                    return False
                
                # Stop loss e take profit baseados em ATR (se disponível)
                # Por enquanto, usar % fixo
                sl_pct = 0.02  # 2%
                tp_pct = 0.04  # 4%
                
                if signal == "BUY":
                    stop_loss = price * (1 - sl_pct)
                    take_profit = price * (1 + tp_pct)
                elif signal == "SELL":
                    stop_loss = price * (1 + sl_pct)
                    take_profit = price * (1 - tp_pct)
                else:
                    return False
                
                result = self.paper_manager.open_position(
                    symbol=symbol,
                    side=signal,
                    quantity=quantity,
                    entry_price=price,
                    stop_loss=stop_loss,
                    take_profit=take_profit
                )
                
                if result['status'] == 'success':
                    logger.info(f"📈 Posição aberta: {signal} {quantity}x {symbol} @ R$ {price:.2f}")
                    logger.info(f"   SL: R$ {stop_loss:.2f} | TP: R$ {take_profit:.2f}")
                    logger.info(f"   Confidence: {confidence:.2%}")
                    
                    self._log_decision({
                        "timestamp": datetime.now(),
                        "symbol": symbol,
                        "action": "open",
                        "signal": signal,
                        "quantity": quantity,
                        "price": price,
                        "confidence": confidence,
                        "stop_loss": stop_loss,
                        "take_profit": take_profit,
                        "executed": True
                    })
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Erro ao executar sinal: {str(e)}")
            return False
    
    def _log_decision(self, decision: Dict):
        """Registra decisão no histórico."""
        self.decision_history.append(decision)
        
        # Manter apenas últimas 100 decisões
        if len(self.decision_history) > 100:
            self.decision_history = self.decision_history[-100:]
    
    def get_stats(self) -> Dict:
        """Retorna estatísticas do trader."""
        acceptance_rate = (self.signals_accepted / self.signals_generated * 100) if self.signals_generated > 0 else 0
        
        return {
            "is_running": self.is_running,
            "last_check": self.last_check.isoformat() if self.last_check else None,
            "model_path": self.model_path,
            "strategy": f"{self.strategy_name}",
            "confidence_threshold": self.confidence_threshold,
            "signals_generated": self.signals_generated,
            "signals_accepted": self.signals_accepted,
            "signals_rejected": self.signals_rejected,
            "acceptance_rate": round(acceptance_rate, 2),
            "anomalies_detected": self.anomalies_detected,
            "recent_decisions": self.decision_history[-10:],  # Últimas 10
            **self.paper_manager.get_status()
        }
