#!/usr/bin/env python3
"""
Backtest Comparativo: Wave3 v2.1 vs Wave3 v2.3+ML
==================================================

Testa ambas estratégias em 10+ ativos B3 com dados 60min e daily

Objetivo: Provar que ML filter melhora win rate

Autor: B3 Trading Platform
Data: 21 Janeiro 2026
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os
import asyncio
import asyncpg

# Add paths
sys.path.append('/app/src/strategies')
sys.path.append('/app/src/ml')

from wave3_enhanced import Wave3Enhanced
from wave3_ml_hybrid import Wave3MLHybrid


class ComparativeBacktester:
    """
    Backtester comparativo para Wave3 v2.1 vs v2.3+ML
    Usa dados do TimescaleDB
    """
    
    def __init__(self, initial_capital: float = 100000.0):
        self.initial_capital = initial_capital
        self.db_pool = None
        
    async def connect_db(self):
        """Conecta ao TimescaleDB"""
        if not self.db_pool:
            self.db_pool = await asyncpg.create_pool(
                host='b3-timescaledb',
                port=5432,
                user='b3trading_ts',
                password='b3trading_ts_pass',
                database='b3trading_market',
                min_size=1,
                max_size=5
            )
        return self.db_pool
    
    async def close_db(self):
        """Fecha conexão com banco"""
        if self.db_pool:
            await self.db_pool.close()
    
    async def load_data_from_db(self, symbol: str, timeframe: str) -> pd.DataFrame:
        """
        Carrega dados do TimescaleDB
        
        Args:
            symbol: Símbolo (ex: PETR4)
            timeframe: '60min' ou 'daily' (1d)
        """
        pool = await self.connect_db()
        
        # Query baseada no timeframe
        query = """
            SELECT time, open, high, low, close, volume
            FROM ohlcv_data
            WHERE symbol = $1 AND timeframe = $2
            ORDER BY time ASC
        """
        
        async with pool.acquire() as conn:
            rows = await conn.fetch(query, symbol, timeframe)
        
        if not rows:
            return pd.DataFrame()
        
        # Converter para DataFrame
        df = pd.DataFrame(rows, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
        df.set_index('time', inplace=True)
        
        # Converter strings para float (se necessário)
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Remover NaN
        df.dropna(inplace=True)
        
        return df
    
    def run_backtest(self, strategy, df_daily, df_60min, symbol):
        """
        Executa backtest para uma estratégia
        
        Returns:
            Dict com métricas
        """
        capital = self.initial_capital
        position = None
        trades = []
        
        # Iterar por cada candle 60min
        for i in range(200, len(df_60min)):  # Warm-up 200 candles
            current_time = df_60min.index[i]
            current_price = df_60min.iloc[i]['close']
            
            # Daily até este momento
            df_daily_slice = df_daily[df_daily.index <= current_time]
            df_60min_slice = df_60min.iloc[:i+1]
            
            if len(df_daily_slice) < 100:
                continue
            
            # Se não tem posição, buscar sinal
            if position is None:
                try:
                    signal = strategy.generate_signal(df_daily_slice, df_60min_slice, symbol)
                except Exception as e:
                    # Skip em caso de erro na geração do sinal
                    continue
                
                if signal and hasattr(signal, 'quality_score'):
                    # Abrir posição
                    max_risk_capital = capital * 0.02
                    shares = int(max_risk_capital / signal.risk) if signal.risk > 0 else 0
                    
                    if shares > 0:
                        position = {
                            'signal': signal,
                            'entry_time': current_time,
                            'entry_price': current_price,
                            'shares': shares,
                            'stop_loss': signal.stop_loss,
                            'targets': [signal.target_1, signal.target_2, signal.target_3],
                            'remaining_shares': shares,
                            'partial_exits': []
                        }
            
            # Se tem posição, verificar saídas
            else:
                signal = position['signal']
                
                # Check stop loss
                if signal.signal_type == 'BUY':
                    if current_price <= position['stop_loss']:
                        # Stop loss
                        pnl = (current_price - position['entry_price']) * position['remaining_shares']
                        capital += pnl
                        
                        trades.append({
                            'symbol': symbol,
                            'entry': position['entry_time'],
                            'exit': current_time,
                            'type': signal.signal_type,
                            'entry_price': position['entry_price'],
                            'exit_price': current_price,
                            'pnl': pnl,
                            'return_pct': (current_price / position['entry_price'] - 1) * 100,
                            'exit_reason': 'STOP_LOSS',
                            'quality_score': signal.quality_score,
                            'ml_confidence': getattr(signal, 'ml_confidence', 0),
                            'hybrid_score': getattr(signal, 'hybrid_score', signal.quality_score)
                        })
                        
                        position = None
                        continue
                    
                    # Check targets
                    for idx, target_price in enumerate(position['targets']):
                        if current_price >= target_price and position['remaining_shares'] > 0:
                            # Alvo parcial
                            if idx == 0:  # T1: 50%
                                exit_shares = int(position['shares'] * 0.5)
                            elif idx == 1:  # T2: 30%
                                exit_shares = int(position['shares'] * 0.3)
                            else:  # T3: 20%
                                exit_shares = position['remaining_shares']
                            
                            if exit_shares > 0:
                                pnl = (current_price - position['entry_price']) * exit_shares
                                capital += pnl
                                position['remaining_shares'] -= exit_shares
                                position['partial_exits'].append({
                                    'target': f'T{idx+1}',
                                    'price': current_price,
                                    'shares': exit_shares,
                                    'pnl': pnl
                                })
                            
                            if position['remaining_shares'] <= 0:
                                # Posição fechada completamente
                                total_pnl = sum([pe['pnl'] for pe in position['partial_exits']])
                                
                                trades.append({
                                    'symbol': symbol,
                                    'entry': position['entry_time'],
                                    'exit': current_time,
                                    'type': signal.signal_type,
                                    'entry_price': position['entry_price'],
                                    'exit_price': current_price,
                                    'pnl': total_pnl,
                                    'return_pct': (total_pnl / (position['entry_price'] * position['shares'])) * 100,
                                    'exit_reason': f"TARGET_T{idx+1}",
                                    'quality_score': signal.quality_score,
                                    'ml_confidence': getattr(signal, 'ml_confidence', 0),
                                    'hybrid_score': getattr(signal, 'hybrid_score', signal.quality_score),
                                    'partial_exits': len(position['partial_exits'])
                                })
                                
                                position = None
        
        # Fechar posição aberta no fim
        if position:
            final_price = df_60min.iloc[-1]['close']
            pnl = (final_price - position['entry_price']) * position['remaining_shares']
            capital += pnl
            
            trades.append({
                'symbol': symbol,
                'entry': position['entry_time'],
                'exit': df_60min.index[-1],
                'type': position['signal'].signal_type,
                'entry_price': position['entry_price'],
                'exit_price': final_price,
                'pnl': pnl,
                'return_pct': (final_price / position['entry_price'] - 1) * 100,
                'exit_reason': 'END_OF_PERIOD',
                'quality_score': position['signal'].quality_score,
                'ml_confidence': getattr(position['signal'], 'ml_confidence', 0),
                'hybrid_score': getattr(position['signal'], 'hybrid_score', position['signal'].quality_score),
                'partial_exits': len(position['partial_exits'])
            })
        
        # Calcular métricas
        if len(trades) == 0:
            return {
                'symbol': symbol,
                'trades': 0,
                'win_rate': 0,
                'total_return': 0,
                'avg_quality_score': 0,
                'avg_ml_confidence': 0,
                'avg_hybrid_score': 0
            }
        
        df_trades = pd.DataFrame(trades)
        wins = len(df_trades[df_trades['pnl'] > 0])
        
        return {
            'symbol': symbol,
            'trades': len(df_trades),
            'wins': wins,
            'losses': len(df_trades) - wins,
            'win_rate': (wins / len(df_trades)) * 100,
            'total_return': ((capital - self.initial_capital) / self.initial_capital) * 100,
            'avg_pnl': df_trades['pnl'].mean(),
            'avg_quality_score': df_trades['quality_score'].mean(),
            'avg_ml_confidence': df_trades['ml_confidence'].mean(),
            'avg_hybrid_score': df_trades['hybrid_score'].mean(),
            'partial_exits': df_trades['partial_exits'].sum()
        }


def main():
    """
    Executa backtest comparativo em 10+ ativos
    """
    # Run async main
    asyncio.run(async_main())


async def async_main():
    """
    Função assíncrona principal
    """
    print("=" * 100)
    print("BACKTEST COMPARATIVO: Wave3 v2.1 vs Wave3 v2.3+ML")
    print("=" * 100)
    
    # Símbolos para testar (10+)
    symbols = [
        'PETR4', 'VALE3', 'ITUB4', 'BBDC4', 'ABEV3',
        'BBAS3', 'WEGE3', 'RENT3', 'MGLU3', 'B3SA3',
        'GGBR4', 'CSNA3', 'EMBR3', 'RADL3', 'SBSP3'
    ]
    
    # Criar estratégias
    print("\n🔧 Criando estratégias...")
    
    wave3_v21 = Wave3Enhanced(
        min_quality_score=65,
        volume_multiplier=1.1,
        target_levels=[(0.5, 1.0), (0.3, 1.5), (0.2, 2.5)]
    )
    
    wave3_v23_ml = Wave3MLHybrid(
        ml_threshold=0.60,
        min_quality_score=65,
        volume_multiplier=1.1,
        target_levels=[(0.5, 1.0), (0.3, 1.5), (0.2, 2.5)]
    )
    
    print(f"✅ Wave3 v2.1 (baseline): Score ≥65")
    print(f"✅ Wave3 v2.3+ML: Score ≥65 + ML confidence ≥0.60")
    
    # Backtester
    backtester = ComparativeBacktester(initial_capital=100000)
    
    # Conectar ao banco
    print("\n🔗 Conectando ao TimescaleDB...")
    try:
        await backtester.connect_db()
        print("✅ Conectado ao TimescaleDB")
    except Exception as e:
        print(f"❌ Erro ao conectar: {e}")
        return
    
    # Resultados
    results_v21 = []
    results_v23 = []
    
    # Testar cada símbolo
    print(f"\n📊 Testando {len(symbols)} símbolos...")
    print("-" * 100)
    
    for symbol in symbols:
        print(f"\n🔄 {symbol}...")
        
        try:
            # Carregar dados do banco
            df_60min = await backtester.load_data_from_db(symbol, '60min')
            df_daily = await backtester.load_data_from_db(symbol, '1d')
            
            if len(df_60min) < 500 or len(df_daily) < 100:
                print(f"   ⚠️ Dados insuficientes: {len(df_daily)} daily, {len(df_60min)} 60min")
                continue
            
            print(f"   ✅ Dados: {len(df_daily)} daily, {len(df_60min)} 60min")
            
            # Backtest v2.1
            print("   🔄 v2.1 (baseline)...")
            result_v21 = backtester.run_backtest(wave3_v21, df_daily, df_60min, symbol)
            results_v21.append(result_v21)
            print(f"      Trades: {result_v21['trades']} | Win Rate: {result_v21['win_rate']:.1f}% | Retorno: {result_v21['total_return']:.2f}%")
            
            # Backtest v2.3+ML
            print("   🔄 v2.3+ML...")
            result_v23 = backtester.run_backtest(wave3_v23_ml, df_daily, df_60min, symbol)
            results_v23.append(result_v23)
            print(f"      Trades: {result_v23['trades']} | Win Rate: {result_v23['win_rate']:.1f}% | Retorno: {result_v23['total_return']:.2f}%")
            print(f"      ML Confidence: {result_v23['avg_ml_confidence']:.2f} | Hybrid Score: {result_v23['avg_hybrid_score']:.1f}")
        
        except Exception as e:
            print(f"   ❌ Erro: {e}")
            continue
    
    # Fechar conexão
    await backtester.close_db()
    
    # Consolidar resultados
    print("\n" + "=" * 100)
    print("RESULTADOS CONSOLIDADOS")
    print("=" * 100)
    
    if len(results_v21) == 0:
        print("❌ Nenhum resultado gerado")
        return
    
    df_v21 = pd.DataFrame(results_v21)
    df_v23 = pd.DataFrame(results_v23)
    
    print("\n📊 Wave3 v2.1 (Baseline)")
    print(f"   Trades Total: {df_v21['trades'].sum()}")
    print(f"   Win Rate Médio: {df_v21['win_rate'].mean():.1f}%")
    print(f"   Retorno Médio: {df_v21['total_return'].mean():.2f}%")
    print(f"   Quality Score Médio: {df_v21['avg_quality_score'].mean():.1f}")
    
    print("\n📊 Wave3 v2.3+ML")
    print(f"   Trades Total: {df_v23['trades'].sum()}")
    print(f"   Win Rate Médio: {df_v23['win_rate'].mean():.1f}%")
    print(f"   Retorno Médio: {df_v23['total_return'].mean():.2f}%")
    print(f"   Quality Score Médio: {df_v23['avg_quality_score'].mean():.1f}")
    print(f"   ML Confidence Médio: {df_v23['avg_ml_confidence'].mean():.2f}")
    print(f"   Hybrid Score Médio: {df_v23['avg_hybrid_score'].mean():.1f}")
    
    # Comparação
    print("\n📈 COMPARAÇÃO (v2.3 vs v2.1)")
    trades_diff = df_v23['trades'].sum() - df_v21['trades'].sum()
    wr_diff = df_v23['win_rate'].mean() - df_v21['win_rate'].mean()
    ret_diff = df_v23['total_return'].mean() - df_v21['total_return'].mean()
    
    print(f"   Trades: {trades_diff:+d} ({trades_diff / df_v21['trades'].sum() * 100:+.1f}%)")
    print(f"   Win Rate: {wr_diff:+.1f}pp")
    print(f"   Retorno: {ret_diff:+.2f}pp")
    
    # Top performers
    print("\n⭐ TOP 5 PERFORMERS (v2.3+ML)")
    top5 = df_v23.nlargest(5, 'total_return')[['symbol', 'trades', 'win_rate', 'total_return', 'avg_ml_confidence']]
    print(top5.to_string(index=False))
    
    print("\n✅ Backtest completo!")
    
    # Stats ML
    ml_stats = wave3_v23_ml.get_stats()
    print(f"\n📊 ML Filter Statistics:")
    print(f"   Wave3 Signals: {ml_stats['wave3_signals']}")
    print(f"   ML Filtered: {ml_stats['ml_filtered']} ({ml_stats.get('ml_filter_rate', 0):.1f}%)")
    print(f"   ML Approved: {ml_stats['ml_approved']} ({ml_stats.get('ml_approval_rate', 0):.1f}%)")


if __name__ == "__main__":
    main()
