#!/usr/bin/env python3
"""
Backtest Wave3 + ML com Walk-Forward 6/1 meses
================================================

TESTE 5: Retreino mais frequente para melhor adaptação ao mercado

Estratégia:
- Treino: 6 meses
- Teste: 1 mês
- Retreino a cada fold
- Comparar com baseline 18/6 meses

Período Total: Jul/2024 → Dez/2024 (6 meses)
- Fold 1: Train Jan-Jun/2024 → Test Jul/2024
- Fold 2: Train Fev-Jul/2024 → Test Ago/2024
- Fold 3: Train Mar-Ago/2024 → Test Set/2024
- Fold 4: Train Abr-Set/2024 → Test Out/2024
- Fold 5: Train Mai-Out/2024 → Test Nov/2024
- Fold 6: Train Jun-Nov/2024 → Test Dez/2024

Autor: B3 Trading Platform
Data: 29 Janeiro 2026
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Importar classe do backtest original
from backtest_wave3_gpu import Wave3GPUBacktest, BacktestGPUResults
import asyncpg
import pandas as pd
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
from typing import List
import numpy as np

async def main():
    """Walk-Forward com múltiplos folds de 3/1 meses"""
    
    print("\n" + "="*80)
    print("TESTE 5: WALK-FORWARD 6/1 MESES")
    print("="*80)
    print(f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print(f"Estratégia: Wave3 v2.1 + XGBoost GPU + Optuna")
    print(f"Walk-Forward: Train 6 meses → Test 1 mês (retreino a cada fold)")
    print(f"Total de Folds: 6")
    print("="*80)
    
    # Config DB
    db_config = {
        'host': 'b3-timescaledb',
        'port': 5432,
        'user': 'b3trading_ts',
        'password': 'b3trading_ts_pass',
        'database': 'b3trading_market'
    }
    
    # Conectar
    print("\n🔗 Conectando ao TimescaleDB...")
    try:
        pool = await asyncpg.create_pool(**db_config, min_size=1, max_size=5)
        print("✅ Conectado")
    except Exception as e:
        print(f"❌ Erro: {e}")
        return
    
    # Configuração do backtest
    backtest = Wave3GPUBacktest(
        db_config=db_config,
        use_gpu=True,
        use_optuna=True,
        n_trials=20,
        min_quality_score=55,
        use_smote=True,
        ml_threshold=0.6
    )
    
    # Símbolo a testar
    symbol = 'PETR4'
    
    # Definir folds (6 meses train / 1 mês test) - rolling window
    folds = [
        # Fold 1: Jan-Jun/2024 → Jul/2024
        {
            'train_start': date(2024, 1, 1),
            'train_end': date(2024, 6, 30),
            'test_start': date(2024, 7, 1),
            'test_end': date(2024, 7, 31)
        },
        # Fold 2: Fev-Jul/2024 → Ago/2024
        {
            'train_start': date(2024, 2, 1),
            'train_end': date(2024, 7, 31),
            'test_start': date(2024, 8, 1),
            'test_end': date(2024, 8, 31)
        },
        # Fold 3: Mar-Ago/2024 → Set/2024
        {
            'train_start': date(2024, 3, 1),
            'train_end': date(2024, 8, 31),
            'test_start': date(2024, 9, 1),
            'test_end': date(2024, 9, 30)
        },
        # Fold 4: Abr-Set/2024 → Out/2024
        {
            'train_start': date(2024, 4, 1),
            'train_end': date(2024, 9, 30),
            'test_start': date(2024, 10, 1),
            'test_end': date(2024, 10, 31)
        },
        # Fold 5: Mai-Out/2024 → Nov/2024
        {
            'train_start': date(2024, 5, 1),
            'train_end': date(2024, 10, 31),
            'test_start': date(2024, 11, 1),
            'test_end': date(2024, 11, 30)
        },
        # Fold 6: Jun-Nov/2024 → Dez/2024
        {
            'train_start': date(2024, 6, 1),
            'train_end': date(2024, 11, 30),
            'test_start': date(2024, 12, 1),
            'test_end': date(2024, 12, 31)
        }
    ]
    
    print(f"\n📊 Walk-Forward com {len(folds)} folds")
    print(f"   Símbolo: {symbol}")
    print(f"   Período total de teste: Jul-Dez 2024 (6 meses)")
    print()
    
    all_fold_results = []
    
    for idx, fold in enumerate(folds, 1):
        print(f"\n{'='*80}")
        print(f"FOLD {idx}/{len(folds)}")
        print(f"{'='*80}")
        print(f"Train: {fold['train_start']} → {fold['train_end']} (6 meses)")
        print(f"Test:  {fold['test_start']} → {fold['test_end']} (1 mês)")
        
        try:
            result = await backtest.backtest_symbol(
                pool, symbol,
                fold['train_start'], fold['train_end'],
                fold['test_start'], fold['test_end']
            )
            
            if result:
                all_fold_results.append({
                    'fold': idx,
                    'train_period': f"{fold['train_start']} → {fold['train_end']}",
                    'test_period': f"{fold['test_start']} → {fold['test_end']}",
                    'result': result
                })
                
                print(f"\n✅ Fold {idx} concluído:")
                print(f"   Trades: {result.total_trades}")
                print(f"   Win Rate: {result.win_rate:.1f}%")
                print(f"   Return: {result.total_return:.2f}%")
                print(f"   Sharpe: {result.sharpe_ratio:.2f}")
        
        except Exception as e:
            print(f"❌ Erro no Fold {idx}: {e}")
            import traceback
            traceback.print_exc()
    
    # Análise consolidada
    print("\n" + "="*80)
    print("ANÁLISE CONSOLIDADA - WALK-FORWARD 6/1 MESES")
    print("="*80)
    
    if not all_fold_results:
        print("⚠️ Nenhum resultado válido")
        await pool.close()
        return
    
    # Métricas por fold
    print("\n📊 Resultados por Fold:\n")
    print(f"{'Fold':<6} {'Período Teste':<20} {'Trades':<8} {'Win%':<8} {'Return%':<10} {'Sharpe':<8}")
    print("-"*80)
    
    for fold_data in all_fold_results:
        r = fold_data['result']
        test_period = fold_data['test_period'].split(' → ')[0][5:10]  # Apenas mês/ano
        print(f"{fold_data['fold']:<6} {test_period:<20} {r.total_trades:<8} {r.win_rate:<8.1f} {r.total_return:<10.2f} {r.sharpe_ratio:<8.2f}")
    
    # Estatísticas consolidadas
    total_trades = sum(f['result'].total_trades for f in all_fold_results)
    total_winners = sum(f['result'].winners for f in all_fold_results)
    avg_win_rate = np.mean([f['result'].win_rate for f in all_fold_results])
    std_win_rate = np.std([f['result'].win_rate for f in all_fold_results])
    avg_return = np.mean([f['result'].total_return for f in all_fold_results])
    std_return = np.std([f['result'].total_return for f in all_fold_results])
    avg_sharpe = np.mean([f['result'].sharpe_ratio for f in all_fold_results])
    std_sharpe = np.std([f['result'].sharpe_ratio for f in all_fold_results])
    avg_precision = np.mean([f['result'].ml_precision for f in all_fold_results])
    
    print(f"\n📈 Métricas Consolidadas:")
    print(f"   Total Trades:     {total_trades}")
    print(f"   Total Winners:    {total_winners} ({total_winners/total_trades*100:.1f}%)")
    print(f"   Avg Win Rate:     {avg_win_rate:.1f}% ± {std_win_rate:.1f}%")
    print(f"   Avg Return:       {avg_return:.2f}% ± {std_return:.2f}%")
    print(f"   Avg Sharpe:       {avg_sharpe:.2f} ± {std_sharpe:.2f}")
    print(f"   Avg ML Precision: {avg_precision:.1f}%")
    
    # Consistency Score (quanto menor o desvio padrão, mais consistente)
    consistency_win = 1 - (std_win_rate / avg_win_rate) if avg_win_rate > 0 else 0
    consistency_return = 1 - (std_return / abs(avg_return)) if avg_return != 0 else 0
    consistency_sharpe = 1 - (std_sharpe / abs(avg_sharpe)) if avg_sharpe != 0 else 0
    consistency_score = (consistency_win + consistency_return + consistency_sharpe) / 3
    
    print(f"\n🎯 Consistency Score: {consistency_score:.2f} (1.0 = perfeito)")
    print(f"   Win Rate Consistency:  {consistency_win:.2f}")
    print(f"   Return Consistency:    {consistency_return:.2f}")
    print(f"   Sharpe Consistency:    {consistency_sharpe:.2f}")
    
    # Comparação com baseline 18/6 meses
    print(f"\n📊 Comparação com Baseline (18/6 meses):")
    print(f"   Baseline Win Rate:     61.1%")
    print(f"   Walk-Forward 6/1:      {avg_win_rate:.1f}%")
    print(f"   Diferença:             {avg_win_rate - 61.1:+.1f}%")
    print()
    print(f"   Baseline Return:       +111.29%")
    print(f"   Walk-Forward 6/1:      {avg_return:.2f}%")
    print(f"   Diferença:             {avg_return - 111.29:+.2f}%")
    print()
    print(f"   Baseline Sharpe:       4.82")
    print(f"   Walk-Forward 6/1:      {avg_sharpe:.2f}")
    print(f"   Diferença:             {avg_sharpe - 4.82:+.2f}")
    
    # Análise de adaptação
    print(f"\n🔬 Análise de Adaptação ao Mercado:")
    first_half_folds = all_fold_results[:3]
    second_half_folds = all_fold_results[3:]
    
    if first_half_folds and second_half_folds:
        first_half_win = np.mean([f['result'].win_rate for f in first_half_folds])
        second_half_win = np.mean([f['result'].win_rate for f in second_half_folds])
        
        first_half_return = np.mean([f['result'].total_return for f in first_half_folds])
        second_half_return = np.mean([f['result'].total_return for f in second_half_folds])
        
        print(f"   Primeira metade (Folds 1-3):")
        print(f"      Win Rate: {first_half_win:.1f}%")
        print(f"      Return:   {first_half_return:.2f}%")
        print()
        print(f"   Segunda metade (Folds 4-6):")
        print(f"      Win Rate: {second_half_win:.1f}%")
        print(f"      Return:   {second_half_return:.2f}%")
        print()
        print(f"   Tendência:")
        if second_half_win > first_half_win:
            print(f"      ✅ Melhora ao longo do tempo (+{second_half_win - first_half_win:.1f}%)")
        else:
            print(f"      ⚠️ Piora ao longo do tempo ({second_half_win - first_half_win:.1f}%)")
    
    print("\n" + "="*80)
    print("✅ TESTE 5 - Walk-Forward 6/1 meses concluído!")
    print("="*80)
    
    await pool.close()


if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
