#!/usr/bin/env python3
"""
Backtest Wave3 6 Meses - Quality Score 55
==========================================

Configuração otimizada para dados disponíveis:
- Quality Score: 55 (menos restritivo)
- Período: 6 meses (últimos 180 dias)
- Ativos: 10 mais líquidos da B3

Autor: B3 Trading Platform
Data: 23 Janeiro 2026
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import asyncio
import asyncpg

sys.path.append('/app/src/strategies')
from wave3_enhanced import Wave3Enhanced
from wave3_ml_hybrid import Wave3MLHybrid


async def backtest_6months():
    """Backtest 6 meses com quality_score=55"""
    
    print("="*100)
    print("BACKTEST 6 MESES: Wave3 v2.1 vs v2.3+ML")
    print("Config: Quality Score = 55 | Período = 180 dias | 10 ativos")
    print("="*100)
    
    # Criar estratégias com score MENOR (55)
    print("\n🔧 Criando estratégias...")
    strategy_v21 = Wave3Enhanced(min_quality_score=55)
    strategy_v23 = Wave3MLHybrid(ml_threshold=0.60, min_quality_score=55)
    print("✅ Wave3 v2.1 (score≥55) | v2.3 ML (score≥55, ML≥60%)")
    
    # Conectar DB
    print("\n🔗 Conectando ao TimescaleDB...")
    pool = await asyncpg.create_pool(
        host='b3-timescaledb',
        port=5432,
        user='b3trading_ts',
        password='b3trading_ts_pass',
        database='b3trading_market',
        min_size=1,
        max_size=5
    )
    print("✅ Conectado")
    
    # 10 ativos mais líquidos
    symbols = [
        'PETR4', 'VALE3', 'ITUB4', 'BBDC4', 'MGLU3',
        'ABEV3', 'WEGE3', 'RENT3', 'GGBR4', 'SUZB3'
    ]
    
    results_v21 = []
    results_v23 = []
    
    print(f"\n📊 Testando {len(symbols)} símbolos (6 meses)...")
    print("-"*100)
    
    for idx, symbol in enumerate(symbols, 1):
        print(f"\n[{idx}/{len(symbols)}] 🔄 {symbol}...")
        
        try:
            # Buscar dados dos últimos 12 meses (contexto)
            async with pool.acquire() as conn:
                # Daily data
                rows_daily = await conn.fetch("""
                    SELECT time, open, high, low, close, volume
                    FROM ohlcv_daily
                    WHERE symbol = $1
                    AND time >= NOW() - INTERVAL '12 months'
                    ORDER BY time
                """, symbol)
                
                # 60min data
                rows_60min = await conn.fetch("""
                    SELECT time, open, high, low, close, volume
                    FROM ohlcv_60min
                    WHERE symbol = $1
                    AND time >= NOW() - INTERVAL '12 months'
                    ORDER BY time
                """, symbol)
            
            if len(rows_daily) < 100 or len(rows_60min) < 100:
                print(f"   ⚠️ Dados insuficientes: {len(rows_daily)} daily, {len(rows_60min)} 60min")
                continue
            
            print(f"   ✅ Dados: {len(rows_daily)} daily, {len(rows_60min)} 60min")
            
            # Converter para DataFrame
            df_daily = pd.DataFrame(rows_daily, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
            df_60min = pd.DataFrame(rows_60min, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
            
            # Converter Decimal para float
            for df in [df_daily, df_60min]:
                for col in ['open', 'high', 'low', 'close', 'volume']:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # Backtest ambas estratégias
            result_v21 = await backtest_strategy(strategy_v21, df_daily, df_60min, symbol, "v2.1", pool)
            result_v23 = await backtest_strategy(strategy_v23, df_daily, df_60min, symbol, "v2.3+ML", pool)
            
            if result_v21:
                results_v21.append(result_v21)
            if result_v23:
                results_v23.append(result_v23)
                
        except Exception as e:
            print(f"   ❌ Erro: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    # Fechar pool
    await pool.close()
    
    # Exibir resultados consolidados
    print("\n" + "="*100)
    print("📊 RESULTADOS CONSOLIDADOS (6 MESES)")
    print("="*100)
    
    print_summary("Wave3 v2.1 (Score≥55)", results_v21)
    print_summary("Wave3 v2.3+ML (Score≥55, ML≥60%)", results_v23)
    
    # Comparação
    if results_v21 and results_v23:
        print("\n" + "="*100)
        print("🏆 COMPARAÇÃO DIRETA")
        print("="*100)
        
        wr_v21 = sum(r['win_rate'] for r in results_v21) / len(results_v21) if results_v21 else 0
        wr_v23 = sum(r['win_rate'] for r in results_v23) / len(results_v23) if results_v23 else 0
        
        ret_v21 = sum(r['avg_return'] for r in results_v21) / len(results_v21) if results_v21 else 0
        ret_v23 = sum(r['avg_return'] for r in results_v23) / len(results_v23) if results_v23 else 0
        
        print(f"\n📈 Win Rate:")
        print(f"   v2.1: {wr_v21:.1f}%")
        print(f"   v2.3: {wr_v23:.1f}% ({'🟢 +' if wr_v23 > wr_v21 else '🔴 '}{wr_v23-wr_v21:.1f}%)")
        
        print(f"\n💰 Retorno Médio:")
        print(f"   v2.1: {ret_v21:.2f}%")
        print(f"   v2.3: {ret_v23:.2f}% ({'🟢 +' if ret_v23 > ret_v21 else '🔴 '}{ret_v23-ret_v21:.2f}%)")
        
        trades_v21 = sum(r['trades'] for r in results_v21)
        trades_v23 = sum(r['trades'] for r in results_v23)
        
        print(f"\n📊 Total Trades:")
        print(f"   v2.1: {trades_v21}")
        print(f"   v2.3: {trades_v23} ({trades_v23-trades_v21:+d} trades)")
        
        if trades_v21 > 0 and trades_v23 < trades_v21:
            filter_rate = (1 - trades_v23/trades_v21) * 100
            print(f"   ML Filter Rate: {filter_rate:.1f}% ({trades_v21-trades_v23} rejeitados)")
        
        # Decisão
        print("\n" + "="*100)
        print("🎯 DECISÃO")
        print("="*100)
        
        if trades_v21 < 15:
            print("\n⚠️ AMOSTRA INSUFICIENTE (<15 trades)")
            print("   - Reduzir quality_score para 50")
            print("   - Adicionar mais ativos (15-20)")
            print("   - Estender para 12 meses")
        elif wr_v23 > wr_v21 + 5:
            print("\n✅ ML MELHORA SIGNIFICATIVAMENTE!")
            print("   - ML aumentou win rate em +{:.1f}%".format(wr_v23-wr_v21))
            print("   - Continuar desenvolvimento v2.3")
        elif wr_v23 > wr_v21:
            print("\n✅ ML tem leve vantagem")
            print("   - Testar thresholds diferentes (0.70, 0.80)")
            print("   - Otimizar features")
        else:
            print("\n❌ ML não está agregando valor")
            print("   - Focar em Wave3 v2.1 pura")
            print("   - Revisar features do modelo")


async def backtest_strategy(strategy, df_daily, df_60min, symbol, strategy_name, pool):
    """
    Executa backtest nos últimos 6 meses
    """
    print(f"      🔄 {strategy_name}...", end=" ")
    
    try:
        trades = []
        position = None
        
        # Últimos 6 meses = últimos 180 dias
        last_date = df_daily['time'].max()
        six_months_ago = last_date - timedelta(days=180)
        
        df_daily_6m = df_daily[df_daily['time'] >= six_months_ago].copy()
        
        for i in range(len(df_daily_6m)):
            current_date = df_daily_6m.iloc[i]['time']
            
            # Dados até data atual (incluindo contexto anterior)
            df_daily_slice = df_daily[df_daily['time'] <= current_date].copy()
            df_60min_slice = df_60min[df_60min['time'] <= current_date].copy()
            
            if len(df_daily_slice) < 100 or len(df_60min_slice) < 50:
                continue
            
            # Sem posição: buscar sinal de entrada
            if position is None:
                try:
                    signal = strategy.generate_signal(df_daily_slice, df_60min_slice, symbol)
                except Exception:
                    continue
                
                if signal and hasattr(signal, 'quality_score'):
                    # Abrir posição
                    take_profit = signal.target_3 if hasattr(signal, 'target_3') else signal.entry_price * 1.18
                    
                    position = {
                        'symbol': symbol,
                        'entry_date': current_date,
                        'entry_price': float(df_daily_slice.iloc[-1]['close']),
                        'stop_loss': float(signal.stop_loss),
                        'take_profit': float(take_profit),
                        'score': signal.quality_score if hasattr(signal, 'quality_score') else 0,
                        'ml_confidence': signal.ml_confidence if hasattr(signal, 'ml_confidence') else 0.5,
                        'hybrid_score': signal.hybrid_score if hasattr(signal, 'hybrid_score') else 0
                    }
            
            # Com posição: verificar saída
            else:
                current_price = float(df_daily_slice.iloc[-1]['close'])
                
                # Stop loss ou take profit
                if current_price <= position['stop_loss'] or current_price >= position['take_profit']:
                    exit_date = current_date
                    exit_price = current_price
                    
                    # Calcular retorno
                    ret = ((exit_price - position['entry_price']) / position['entry_price']) * 100
                    
                    trade = {
                        'symbol': symbol,
                        'entry_date': position['entry_date'],
                        'exit_date': exit_date,
                        'entry_price': position['entry_price'],
                        'exit_price': exit_price,
                        'return_pct': ret,
                        'result': 'WIN' if ret > 0 else 'LOSS',
                        'score': position['score'],
                        'ml_confidence': position['ml_confidence'],
                        'hybrid_score': position['hybrid_score']
                    }
                    
                    trades.append(trade)
                    position = None
        
        # Calcular métricas
        if len(trades) == 0:
            print(f"0 trades")
            return None
        
        wins = [t for t in trades if t['result'] == 'WIN']
        win_rate = (len(wins) / len(trades)) * 100
        avg_return = sum(t['return_pct'] for t in trades) / len(trades)
        
        print(f"{len(trades)} trades | {win_rate:.0f}% win | {avg_return:+.2f}%")
        
        return {
            'symbol': symbol,
            'strategy': strategy_name,
            'trades': len(trades),
            'wins': len(wins),
            'losses': len(trades) - len(wins),
            'win_rate': win_rate,
            'avg_return': avg_return,
            'trades_data': trades
        }
        
    except Exception as e:
        print(f"❌ {e}")
        return None


def print_summary(strategy_name, results):
    """Exibe resumo consolidado de uma estratégia"""
    if not results:
        print(f"\n⚠️ {strategy_name}: Sem resultados")
        return
    
    print(f"\n{'='*50}")
    print(f"📊 {strategy_name}")
    print(f"{'='*50}")
    
    total_trades = sum(r['trades'] for r in results)
    total_wins = sum(r['wins'] for r in results)
    
    if total_trades > 0:
        overall_wr = (total_wins / total_trades) * 100
        overall_ret = sum(r['avg_return'] * r['trades'] for r in results) / total_trades
        
        print(f"Ativos testados: {len(results)}")
        print(f"Total Trades: {total_trades}")
        print(f"Wins: {total_wins} ({overall_wr:.1f}%)")
        print(f"Losses: {total_trades - total_wins} ({100-overall_wr:.1f}%)")
        print(f"Retorno Médio: {overall_ret:+.2f}%")
        
        # Melhor e pior
        best = max(results, key=lambda x: x['avg_return'])
        worst = min(results, key=lambda x: x['avg_return'])
        
        print(f"\n🏆 Melhor: {best['symbol']} ({best['avg_return']:+.2f}%, {best['win_rate']:.0f}% win, {best['trades']} trades)")
        print(f"⚠️ Pior: {worst['symbol']} ({worst['avg_return']:+.2f}%, {worst['win_rate']:.0f}% win, {worst['trades']} trades)")


if __name__ == "__main__":
    asyncio.run(backtest_6months())
