"""
Wave3 ML Strategy - PASSO 12 v2
=================================

Integra Wave3 Daily Strategy com ML filtering:
- Usa Wave3 para gerar sinais base
- Filtra com ML classifier (Random Forest/XGBoost)
- Só opera quando ML confidence > threshold

Author: B3 Trading Platform
Date: 16 de Janeiro de 2026
"""

import asyncio
import pickle
from typing import Dict, Optional, List
from pathlib import Path
import pandas as pd
import numpy as np
from datetime import datetime

# Nota: assumindo que Wave3DailyStrategy já existe
# from .wave3_daily_strategy import Wave3DailyStrategy


class Wave3MLStrategy:
    """
    Wave3 Strategy + ML Filtering
    
    Workflow:
    1. Wave3 gera sinal baseado em EMAs + MACD + RSI
    2. ML analisa 114+ features e retorna probabilidade
    3. Só executa trade se:
       - Wave3 = BUY
       - ML prediction = 1 (profitable)
       - ML confidence > threshold (default 0.6)
    """
    
    def __init__(
        self,
        ml_model_path: str = '/app/models/ml_wave3_v2.pkl',
        confidence_threshold: float = 0.6,
        use_ml_filter: bool = True
    ):
        """
        Args:
            ml_model_path: Path para modelo pickle
            confidence_threshold: Threshold mínimo de confiança (0-1)
            use_ml_filter: Se False, opera como Wave3 puro
        """
        self.ml_model_path = ml_model_path
        self.confidence_threshold = confidence_threshold
        self.use_ml_filter = use_ml_filter
        
        # Carregar modelo ML
        self.ml_model = None
        self.feature_engineer = None
        self.model_metadata = {}
        
        if use_ml_filter:
            self._load_ml_model()
    
    def _load_ml_model(self):
        """Carrega modelo ML salvo"""
        try:
            with open(self.ml_model_path, 'rb') as f:
                data = pickle.load(f)
                self.ml_model = data['model']
                self.feature_engineer = data['feature_engineer']
                self.model_metadata = data['metadata']
            
            print(f"✅ ML Model loaded: {self.ml_model_path}")
            print(f"   Accuracy: {self.model_metadata['metrics']['accuracy']:.4f}")
            print(f"   ROC-AUC: {self.model_metadata['metrics']['roc_auc']:.4f}")
        
        except FileNotFoundError:
            print(f"⚠️  ML model not found: {self.ml_model_path}")
            print(f"   Run training first or set use_ml_filter=False")
            self.use_ml_filter = False
    
    def generate_wave3_signal(self, df: pd.DataFrame) -> Dict:
        """
        Gera sinal Wave3 puro (sem ML)
        
        Lógica Wave3:
        - Trend: EMA9 > EMA21 > EMA72
        - Momentum: MACD bullish + RSI 40-70
        - Confirmation: ADX > 20
        
        Args:
            df: DataFrame com OHLCV
        
        Returns:
            Dict com action, price, confidence
        """
        if len(df) < 250:
            return {'action': 'hold', 'reason': 'insufficient_data'}
        
        # Último candle
        last = df.iloc[-1]
        
        # Verificar EMAs
        ema9 = last.get('ema_9', None)
        ema21 = last.get('ema_21', None)
        ema72 = last.get('ema_72', None)
        
        if ema9 is None:
            # Calcular se não existir
            df['ema_9'] = df['close'].ewm(span=9, adjust=False).mean()
            df['ema_21'] = df['close'].ewm(span=21, adjust=False).mean()
            df['ema_72'] = df['close'].ewm(span=72, adjust=False).mean()
            last = df.iloc[-1]
            ema9 = last['ema_9']
            ema21 = last['ema_21']
            ema72 = last['ema_72']
        
        # Trend check
        trend_up = ema9 > ema21 > ema72
        
        # MACD
        macd = last.get('macd', None)
        macd_signal = last.get('macd_signal', None)
        macd_bullish = False
        
        if macd is not None and macd_signal is not None:
            macd_bullish = macd > macd_signal
        
        # RSI
        rsi = last.get('rsi_14', None)
        rsi_ok = False
        
        if rsi is not None:
            rsi_ok = 40 < rsi < 70
        
        # ADX
        adx = last.get('adx', None)
        adx_strong = False
        
        if adx is not None:
            adx_strong = adx > 20
        
        # Decisão Wave3
        conditions_met = 0
        conditions_met += 1 if trend_up else 0
        conditions_met += 1 if macd_bullish else 0
        conditions_met += 1 if rsi_ok else 0
        conditions_met += 1 if adx_strong else 0
        
        # Precisa de pelo menos 3/4 condições
        if conditions_met >= 3:
            return {
                'action': 'buy',
                'price': float(last['close']),
                'confidence': conditions_met / 4,
                'reason': f'wave3_conditions_{conditions_met}/4',
                'indicators': {
                    'ema9': float(ema9),
                    'ema21': float(ema21),
                    'ema72': float(ema72),
                    'rsi': float(rsi) if rsi is not None else None,
                    'macd': float(macd) if macd is not None else None,
                    'adx': float(adx) if adx is not None else None
                }
            }
        else:
            return {
                'action': 'hold',
                'reason': f'wave3_conditions_{conditions_met}/4_insufficient',
                'confidence': conditions_met / 4
            }
    
    def generate_ml_prediction(self, df: pd.DataFrame) -> Dict:
        """
        Gera predição ML
        
        Args:
            df: DataFrame com OHLCV
        
        Returns:
            Dict com prediction, probability, confidence
        """
        if not self.use_ml_filter or self.ml_model is None:
            return {
                'prediction': 1,
                'probability': 1.0,
                'confidence': 1.0,
                'reason': 'ml_disabled'
            }
        
        try:
            # Gerar features
            df_features = self.feature_engineer.generate_all_features(df.copy())
            
            if len(df_features) == 0:
                return {
                    'prediction': 0,
                    'probability': 0.0,
                    'confidence': 0.0,
                    'reason': 'insufficient_data_for_features'
                }
            
            # Última linha
            features = df_features[self.model_metadata['features']].iloc[-1:].values
            
            # Predição
            pred = self.ml_model.predict(features)[0]
            prob = self.ml_model.predict_proba(features)[0]
            confidence = float(prob[1])  # Prob de classe 1 (profitable)
            
            return {
                'prediction': int(pred),
                'probability': confidence,
                'confidence': confidence,
                'reason': 'ml_prediction'
            }
        
        except Exception as e:
            print(f"⚠️  ML prediction error: {e}")
            return {
                'prediction': 0,
                'probability': 0.0,
                'confidence': 0.0,
                'reason': f'ml_error_{str(e)}'
            }
    
    def generate_signal(self, df: pd.DataFrame) -> Dict:
        """
        Gera sinal combinado (Wave3 + ML)
        
        Logic:
        1. Wave3 deve sinalizar BUY
        2. ML deve prever profitable (1)
        3. ML confidence deve ser > threshold
        
        Args:
            df: DataFrame com OHLCV
        
        Returns:
            Dict com action, price, wave3_confidence, ml_confidence, combined_signal
        """
        # 1. Sinal Wave3
        wave3_signal = self.generate_wave3_signal(df)
        
        # Se Wave3 não sinaliza BUY, não precisa avaliar ML
        if wave3_signal['action'] != 'buy':
            return {
                'action': 'hold',
                'reason': 'wave3_no_signal',
                'wave3_signal': wave3_signal,
                'ml_signal': None,
                'timestamp': datetime.now().isoformat()
            }
        
        # 2. Se não usa ML filter, retorna Wave3 puro
        if not self.use_ml_filter:
            return {
                'action': 'buy',
                'price': wave3_signal['price'],
                'confidence': wave3_signal['confidence'],
                'reason': 'wave3_pure',
                'wave3_signal': wave3_signal,
                'ml_signal': {'reason': 'ml_disabled'},
                'timestamp': datetime.now().isoformat()
            }
        
        # 3. Predição ML
        ml_signal = self.generate_ml_prediction(df)
        
        # 4. Decisão combinada
        if ml_signal['prediction'] == 1 and ml_signal['confidence'] >= self.confidence_threshold:
            return {
                'action': 'buy',
                'price': wave3_signal['price'],
                'confidence': ml_signal['confidence'],
                'reason': 'wave3_ml_approved',
                'wave3_signal': wave3_signal,
                'ml_signal': ml_signal,
                'combined_confidence': (wave3_signal['confidence'] + ml_signal['confidence']) / 2,
                'timestamp': datetime.now().isoformat()
            }
        else:
            return {
                'action': 'hold',
                'reason': f'ml_filtered_out_conf_{ml_signal["confidence"]:.2f}',
                'wave3_signal': wave3_signal,
                'ml_signal': ml_signal,
                'timestamp': datetime.now().isoformat()
            }


class BacktestComparison:
    """Compara performance Wave3 puro vs Wave3+ML"""
    
    def __init__(self):
        self.results = {
            'wave3_pure': [],
            'wave3_ml_06': [],
            'wave3_ml_07': []
        }
    
    def run_backtest(
        self,
        symbol: str,
        df: pd.DataFrame,
        strategy: Wave3MLStrategy,
        initial_capital: float = 100000.0
    ) -> Dict:
        """
        Roda backtest para uma estratégia
        
        Args:
            symbol: Símbolo
            df: DataFrame com OHLCV
            strategy: Instância da estratégia
            initial_capital: Capital inicial
        
        Returns:
            Dict com métricas
        """
        capital = initial_capital
        position = None
        trades = []
        
        # Simular dia a dia
        for i in range(250, len(df)):
            df_slice = df.iloc[:i+1]
            
            signal = strategy.generate_signal(df_slice)
            
            # Se tem posição aberta
            if position is not None:
                # Sair após 5 dias ou se lucro > 2%
                days_held = i - position['entry_idx']
                current_price = df.iloc[i]['close']
                pnl_pct = (current_price - position['entry_price']) / position['entry_price']
                
                if days_held >= 5 or pnl_pct > 0.02:
                    # Fechar posição
                    pnl = (current_price - position['entry_price']) * position['shares']
                    capital += pnl
                    
                    trades.append({
                        'entry_date': position['entry_date'],
                        'exit_date': df.index[i],
                        'entry_price': position['entry_price'],
                        'exit_price': current_price,
                        'shares': position['shares'],
                        'pnl': pnl,
                        'pnl_pct': pnl_pct,
                        'days_held': days_held
                    })
                    
                    position = None
            
            # Se não tem posição e sinal é BUY
            if position is None and signal['action'] == 'buy':
                # Entrar
                entry_price = signal['price']
                shares = int(capital * 0.1 / entry_price)  # 10% do capital
                
                if shares > 0:
                    position = {
                        'entry_idx': i,
                        'entry_date': df.index[i],
                        'entry_price': entry_price,
                        'shares': shares,
                        'signal': signal
                    }
        
        # Fechar posição final se aberta
        if position is not None:
            current_price = df.iloc[-1]['close']
            pnl = (current_price - position['entry_price']) * position['shares']
            capital += pnl
            
            trades.append({
                'entry_date': position['entry_date'],
                'exit_date': df.index[-1],
                'entry_price': position['entry_price'],
                'exit_price': current_price,
                'shares': position['shares'],
                'pnl': pnl,
                'pnl_pct': (current_price - position['entry_price']) / position['entry_price'],
                'days_held': len(df) - position['entry_idx']
            })
        
        # Calcular métricas
        if trades:
            trades_df = pd.DataFrame(trades)
            total_return = (capital - initial_capital) / initial_capital
            win_rate = len(trades_df[trades_df['pnl'] > 0]) / len(trades_df)
            avg_pnl = trades_df['pnl'].mean()
            sharpe = trades_df['pnl_pct'].mean() / trades_df['pnl_pct'].std() if trades_df['pnl_pct'].std() > 0 else 0
        else:
            total_return = 0
            win_rate = 0
            avg_pnl = 0
            sharpe = 0
        
        return {
            'symbol': symbol,
            'initial_capital': initial_capital,
            'final_capital': capital,
            'total_return': total_return,
            'num_trades': len(trades),
            'win_rate': win_rate,
            'avg_pnl': avg_pnl,
            'sharpe_ratio': sharpe,
            'trades': trades
        }


# CLI para teste
if __name__ == '__main__':
    import asyncio
    
    print("Wave3 ML Strategy - Test Mode")
    print("=" * 70)
    
    # Criar estratégia
    strategy = Wave3MLStrategy(confidence_threshold=0.6, use_ml_filter=True)
    
    print("\n✅ Strategy initialized")
    print(f"   ML Filter: {'Enabled' if strategy.use_ml_filter else 'Disabled'}")
    print(f"   Confidence Threshold: {strategy.confidence_threshold}")
