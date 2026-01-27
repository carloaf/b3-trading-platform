#!/usr/bin/env python3
"""
Backtest Multi-Ativos: Wave3 v2.1 vs v2.3+ML
=============================================

Testa múltiplos ativos com dados REAIS do ProfitChart
Gera relatório consolidado para decisão ML

Autor: B3 Trading Platform
Data: 23 Janeiro 2026
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import asyncio
import asyncpg
from typing import List, Dict, Optional

sys.path.append('/app/src/strategies')
sys.path.append('/app/src/ml')

from wave3_enhanced import Wave3Enhanced
from wave3_ml_hybrid import Wave3MLHybrid


async def test_multi_assets(
    symbols: List[str],
    months: int = 6,
    quality_score: int = 55
):
    """
    Testa múltiplos ativos com Wave3 pura e ML
    
    Args:
        symbols: Lista de símbolos a testar
        months: Período de teste em meses
        quality_score: Score mínimo para sinais
    """
    
    print("="*100)
    print(f"BACKTEST MULTI-ATIVOS: Wave3 v2.1 vs v2.3+ML")
    print(f"Ativos: {len(symbols)} | Período: {months} meses | Score≥{quality_score}")
    print("="*100)
    
    # Criar estratégias
    print("\n🔧 Criando estratégias...")
    strategy_v21 = Wave3Enhanced(min_quality_score=quality_score)
    strategy_v23 = Wave3MLHybrid(ml_threshold=0.60, min_quality_score=quality_score)
    print("✅ Wave3 v2.1 (pura) | v2.3 ML (ML≥60%)")
    
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
    
    results = []
    
    print(f"\n📊 Testando {len(symbols)} símbolos...")
    print("-"*100)
    
    for idx, symbol in enumerate(symbols, 1):
        print(f"\n[{idx}/{len(symbols)}] 🔄 {symbol}...")
        
        try:
            # Buscar dados
            async with pool.acquire() as conn:
                # Daily data (últimos 12 meses para contexto)
                rows_daily = await conn.fetch("""
                    SELECT time, open, high, low, close, volume
                    FROM ohlcv_daily
                    WHERE symbol = $1
                    ORDER BY time DESC
                    LIMIT 300
                """, symbol)
                
                # 60min data (todos)
                rows_60min = await conn.fetch("""
                    SELECT time, open, high, low, close, volume
                    FROM ohlcv_60min
                    WHERE symbol = $1
                    ORDER BY time
                """, symbol)
            
            if len(rows_daily) < 100 or len(rows_60min) < 1000:
                print(f"   ⚠️ Dados insuficientes: {len(rows_daily)} daily, {len(rows_60min)} 60min")
                continue
            
            print(f"   ✅ Dados: {len(rows_daily)} daily, {len(rows_60min)} 60min")
            
            # Converter para DataFrame
            df_daily = pd.DataFrame(rows_daily, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
            df_60min = pd.DataFrame(rows_60min, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
            
            # Reverter daily (mais antigo primeiro)
            df_daily = df_daily.iloc[::-1].reset_index(drop=True)
            
            # Converter Decimal para float
            for df in [df_daily, df_60min]:
                for col in ['open', 'high', 'low', 'close', 'volume']:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # Backtest ambas estratégias
            result_v21 = await backtest_strategy(
                strategy_v21, df_daily, df_60min, symbol, "v2.1", months
            )
            
            result_v23 = await backtest_strategy(
                strategy_v23, df_daily, df_60min, symbol, "v2.3+ML", months
            )
            
            if result_v21 or result_v23:
                results.append({
                    'symbol': symbol,
                    'v21': result_v21,
                    'v23': result_v23
                })
                
        except Exception as e:
            print(f"   ❌ Erro: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    # Fechar pool
    await pool.close()
    
    # Exibir resultados consolidados
    print("\n" + "="*100)
    print("📊 RESULTADOS CONSOLIDADOS")
    print("="*100)
    
    print_consolidated_results(results, months)
    
    # Salvar relatório
    save_report(results, months, quality_score)


async def backtest_strategy(
    strategy,
    df_daily: pd.DataFrame,
    df_60min: pd.DataFrame,
    symbol: str,
    strategy_name: str,
    months: int
) -> Optional[Dict]:
    """Executa backtest de uma estratégia"""
    
    try:
        trades = []
        position = None
        
        # Período de teste
        last_date = df_daily['time'].max()
        start_date = last_date - timedelta(days=months*30)
        
        df_daily_test = df_daily[df_daily['time'] >= start_date].copy()
        
        for i in range(len(df_daily_test)):
            current_date = df_daily_test.iloc[i]['time']
            
            # Dados até data atual
            df_daily_slice = df_daily[df_daily['time'] <= current_date].copy()
            df_60min_slice = df_60min[df_60min['time'] <= current_date].copy()
            
            if len(df_daily_slice) < 100 or len(df_60min_slice) < 50:
                continue
            
            # Sem posição: buscar entrada
            if position is None:
                try:
                    signal = strategy.generate_signal(df_daily_slice, df_60min_slice, symbol)
                    
                    if signal and hasattr(signal, 'quality_score'):
                        entry_price = float(df_daily_slice.iloc[-1]['close'])
                        take_profit = signal.target_3 if hasattr(signal, 'target_3') else entry_price * 1.18
                        
                        position = {
                            'entry_date': current_date,
                            'entry_price': entry_price,
                            'stop_loss': float(signal.stop_loss),
                            'take_profit': float(take_profit),
                            'score': signal.quality_score,
                            'ml_confidence': getattr(signal, 'ml_confidence', 0.5),
                            'hybrid_score': getattr(signal, 'hybrid_score', 0)
                        }
                        
                except Exception:
                    pass
            
            # Com posição: verificar saída
            else:
                current_price = float(df_daily_slice.iloc[-1]['close'])
                
                if current_price <= position['stop_loss'] or current_price >= position['take_profit']:
                    ret = ((current_price - position['entry_price']) / position['entry_price']) * 100
                    
                    trade = {
                        'entry_date': position['entry_date'],
                        'exit_date': current_date,
                        'entry_price': position['entry_price'],
                        'exit_price': current_price,
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
            print(f"      {strategy_name}: 0 trades")
            return None
        
        wins = [t for t in trades if t['result'] == 'WIN']
        win_rate = (len(wins) / len(trades)) * 100
        avg_return = sum(t['return_pct'] for t in trades) / len(trades)
        total_return = sum(t['return_pct'] for t in trades)
        
        print(f"      {strategy_name}: {len(trades)} trades | {win_rate:.0f}% win | {avg_return:+.2f}% avg")
        
        return {
            'trades': len(trades),
            'wins': len(wins),
            'losses': len(trades) - len(wins),
            'win_rate': win_rate,
            'avg_return': avg_return,
            'total_return': total_return,
            'trades_data': trades
        }
        
    except Exception as e:
        print(f"      ❌ {strategy_name}: {e}")
        return None


def print_consolidated_results(results: List[Dict], months: int):
    """Exibe resumo consolidado"""
    
    if not results:
        print("\n⚠️ Nenhum resultado disponível")
        return
    
    # Separar v2.1 e v2.3
    v21_results = [r for r in results if r['v21'] is not None]
    v23_results = [r for r in results if r['v23'] is not None]
    
    print(f"\n{'='*50}")
    print(f"📊 Wave3 v2.1 (Pura) - {months} meses")
    print(f"{'='*50}")
    
    if v21_results:
        total_trades_v21 = sum(r['v21']['trades'] for r in v21_results)
        total_wins_v21 = sum(r['v21']['wins'] for r in v21_results)
        
        if total_trades_v21 > 0:
            overall_wr_v21 = (total_wins_v21 / total_trades_v21) * 100
            overall_ret_v21 = sum(r['v21']['avg_return'] * r['v21']['trades'] for r in v21_results) / total_trades_v21
            
            print(f"Ativos testados: {len(v21_results)}")
            print(f"Total Trades: {total_trades_v21}")
            print(f"Win Rate: {overall_wr_v21:.1f}%")
            print(f"Retorno Médio: {overall_ret_v21:+.2f}%")
            
            # Top 3
            top3_v21 = sorted(v21_results, key=lambda x: x['v21']['avg_return'], reverse=True)[:3]
            print(f"\n🏆 Top 3:")
            for i, r in enumerate(top3_v21, 1):
                print(f"   {i}. {r['symbol']}: {r['v21']['avg_return']:+.2f}% ({r['v21']['win_rate']:.0f}% win, {r['v21']['trades']} trades)")
    
    print(f"\n{'='*50}")
    print(f"📊 Wave3 v2.3+ML (ML≥60%) - {months} meses")
    print(f"{'='*50}")
    
    if v23_results:
        total_trades_v23 = sum(r['v23']['trades'] for r in v23_results)
        total_wins_v23 = sum(r['v23']['wins'] for r in v23_results)
        
        if total_trades_v23 > 0:
            overall_wr_v23 = (total_wins_v23 / total_trades_v23) * 100
            overall_ret_v23 = sum(r['v23']['avg_return'] * r['v23']['trades'] for r in v23_results) / total_trades_v23
            
            print(f"Ativos testados: {len(v23_results)}")
            print(f"Total Trades: {total_trades_v23}")
            print(f"Win Rate: {overall_wr_v23:.1f}%")
            print(f"Retorno Médio: {overall_ret_v23:+.2f}%")
            
            # ML Filter effectiveness
            if total_trades_v21 > 0:
                filter_rate = (1 - total_trades_v23/total_trades_v21) * 100 if total_trades_v23 < total_trades_v21 else 0
                print(f"ML Filter Rate: {filter_rate:.1f}% ({total_trades_v21-total_trades_v23} trades rejeitados)")
            
            # Top 3
            top3_v23 = sorted(v23_results, key=lambda x: x['v23']['avg_return'], reverse=True)[:3]
            print(f"\n🏆 Top 3:")
            for i, r in enumerate(top3_v23, 1):
                print(f"   {i}. {r['symbol']}: {r['v23']['avg_return']:+.2f}% ({r['v23']['win_rate']:.0f}% win, {r['v23']['trades']} trades)")
    
    # Comparação
    if v21_results and v23_results and total_trades_v21 > 0 and total_trades_v23 > 0:
        print(f"\n{'='*50}")
        print("🏆 COMPARAÇÃO DIRETA")
        print(f"{'='*50}")
        
        improvement = overall_wr_v23 - overall_wr_v21
        ret_improvement = overall_ret_v23 - overall_ret_v21
        
        print(f"\nWin Rate: {overall_wr_v21:.1f}% → {overall_wr_v23:.1f}% ({improvement:+.1f}%)")
        print(f"Retorno: {overall_ret_v21:+.2f}% → {overall_ret_v23:+.2f}% ({ret_improvement:+.2f}%)")
        
        if improvement > 5:
            print("\n✅ ML MELHOROU SIGNIFICATIVAMENTE (+5% win rate)")
        elif improvement > 0:
            print("\n⚠️ ML teve leve melhora (testar mais dados)")
        else:
            print("\n❌ ML não agregou valor (revisar modelo)")


def save_report(results: List[Dict], months: int, quality_score: int):
    """Salva relatório em CSV"""
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"/app/reports/backtest_multi_assets_{timestamp}.csv"
    
    rows = []
    for r in results:
        row = {'symbol': r['symbol']}
        
        if r['v21']:
            row.update({
                'v21_trades': r['v21']['trades'],
                'v21_win_rate': r['v21']['win_rate'],
                'v21_avg_return': r['v21']['avg_return'],
                'v21_total_return': r['v21']['total_return']
            })
        
        if r['v23']:
            row.update({
                'v23_trades': r['v23']['trades'],
                'v23_win_rate': r['v23']['win_rate'],
                'v23_avg_return': r['v23']['avg_return'],
                'v23_total_return': r['v23']['total_return']
            })
        
        rows.append(row)
    
    df = pd.DataFrame(rows)
    
    try:
        df.to_csv(filename, index=False)
        print(f"\n💾 Relatório salvo: {filename}")
    except Exception as e:
        print(f"\n⚠️ Erro ao salvar relatório: {e}")


if __name__ == "__main__":
    # Símbolos para testar (prioridade por liquidez)
    SYMBOLS_PRIORITY_1 = ['PETR4', 'VALE3', 'ITUB4', 'BBDC4', 'MGLU3']
    SYMBOLS_PRIORITY_2 = ['ABEV3', 'WEGE3', 'RENT3', 'GGBR4', 'SUZB3']
    SYMBOLS_PRIORITY_3 = ['B3SA3', 'BBAS3', 'TOTS3', 'CIEL3', 'RAIL3']
    
    # Configuração do teste
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == 'quick':
            symbols = SYMBOLS_PRIORITY_1
            months = 6
        elif sys.argv[1] == 'full':
            symbols = SYMBOLS_PRIORITY_1 + SYMBOLS_PRIORITY_2
            months = 6
        elif sys.argv[1] == 'extended':
            symbols = SYMBOLS_PRIORITY_1 + SYMBOLS_PRIORITY_2 + SYMBOLS_PRIORITY_3
            months = 12
        else:
            symbols = SYMBOLS_PRIORITY_1
            months = 6
    else:
        symbols = SYMBOLS_PRIORITY_1
        months = 6
    
    asyncio.run(test_multi_assets(symbols, months=months, quality_score=55))
