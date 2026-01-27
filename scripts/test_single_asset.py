#!/usr/bin/env python3
"""
Teste Rápido: 1 Ativo com Dados REAIS
======================================

Valida se dados do ProfitChart estão corretos no banco

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


async def test_single_asset():
    """Testa PETR4 com dados reais"""
    
    print("="*80)
    print("TESTE RÁPIDO: PETR4 com Dados REAIS do ProfitChart")
    print("="*80)
    
    # Conectar DB
    print("\n🔗 Conectando ao TimescaleDB...")
    pool = await asyncpg.create_pool(
        host='b3-timescaledb',
        port=5432,
        user='b3trading_ts',
        password='b3trading_ts_pass',
        database='b3trading_market',
        min_size=1,
        max_size=2
    )
    print("✅ Conectado")
    
    symbol = 'PETR4'
    
    print(f"\n📊 Buscando dados de {symbol}...")
    
    try:
        async with pool.acquire() as conn:
            # Daily data
            rows_daily = await conn.fetch("""
                SELECT time, open, high, low, close, volume
                FROM ohlcv_daily
                WHERE symbol = $1
                ORDER BY time DESC
                LIMIT 300
            """, symbol)
            
            # 60min data (TODOS os dados disponíveis)
            rows_60min = await conn.fetch("""
                SELECT time, open, high, low, close, volume
                FROM ohlcv_60min
                WHERE symbol = $1
                ORDER BY time
            """, symbol)
        
        print(f"\n✅ Dados carregados:")
        print(f"   Daily: {len(rows_daily)} registros")
        print(f"   60min: {len(rows_60min)} registros")
        
        if len(rows_daily) > 0:
            first_daily = rows_daily[-1]['time']
            last_daily = rows_daily[0]['time']
            print(f"   Daily range: {first_daily.date()} → {last_daily.date()}")
        
        if len(rows_60min) > 0:
            first_60min = rows_60min[0]['time']
            last_60min = rows_60min[-1]['time']
            print(f"   60min range: {first_60min} → {last_60min}")
        
        if len(rows_daily) < 100:
            print("\n❌ Dados insuficientes (< 100 dias)")
            await pool.close()
            return
        
        # Converter para DataFrame
        df_daily = pd.DataFrame(rows_daily, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
        df_60min = pd.DataFrame(rows_60min, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
        
        # Reverter ordem (mais antigo primeiro)
        df_daily = df_daily.iloc[::-1].reset_index(drop=True)
        
        # Converter Decimal para float
        for df in [df_daily, df_60min]:
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        print(f"\n📈 Últimos 5 dias (Daily):")
        print(df_daily[['time', 'close', 'volume']].tail())
        
        print(f"\n📈 Últimas 5 horas (60min):")
        print(df_60min[['time', 'close', 'volume']].tail())
        
        # Criar estratégia
        print("\n🔧 Testando estratégia Wave3...")
        strategy = Wave3Enhanced(min_quality_score=55)
        
        # Testar últimos 6 MESES
        trades = []
        position = None
        
        last_date = df_daily['time'].max()
        start_date = last_date - timedelta(days=180)
        
        df_daily_6m = df_daily[df_daily['time'] >= start_date].copy()
        
        print(f"\n🔄 Simulando {len(df_daily_6m)} dias (6 meses)...")
        
        for i in range(len(df_daily_6m)):
            current_date = df_daily_6m.iloc[i]['time']
            
            # Dados até data atual
            df_daily_slice = df_daily[df_daily['time'] <= current_date].copy()
            df_60min_slice = df_60min[df_60min['time'] <= current_date].copy()
            
            if len(df_daily_slice) < 100 or len(df_60min_slice) < 20:
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
                            'score': signal.quality_score
                        }
                        
                        print(f"\n✅ SINAL em {current_date.date()}")
                        print(f"   Entry: R$ {entry_price:.2f}")
                        print(f"   Stop: R$ {position['stop_loss']:.2f}")
                        print(f"   Target: R$ {position['take_profit']:.2f}")
                        print(f"   Score: {signal.quality_score}")
                        
                except Exception as e:
                    pass
            
            # Com posição: verificar saída
            else:
                current_price = float(df_daily_slice.iloc[-1]['close'])
                
                if current_price <= position['stop_loss'] or current_price >= position['take_profit']:
                    ret = ((current_price - position['entry_price']) / position['entry_price']) * 100
                    result = 'WIN' if ret > 0 else 'LOSS'
                    
                    trade = {
                        'entry_date': position['entry_date'],
                        'exit_date': current_date,
                        'entry_price': position['entry_price'],
                        'exit_price': current_price,
                        'return_pct': ret,
                        'result': result,
                        'score': position['score']
                    }
                    
                    trades.append(trade)
                    
                    print(f"\n🏁 SAÍDA em {current_date.date()}")
                    print(f"   Exit: R$ {current_price:.2f}")
                    print(f"   Retorno: {ret:+.2f}%")
                    print(f"   Resultado: {result}")
                    
                    position = None
        
        # Resumo
        print("\n" + "="*80)
        print("📊 RESUMO - 6 MESES")
        print("="*80)
        
        if len(trades) == 0:
            print("⚠️ Nenhum trade gerado")
        else:
            wins = [t for t in trades if t['result'] == 'WIN']
            win_rate = (len(wins) / len(trades)) * 100
            avg_return = sum(t['return_pct'] for t in trades) / len(trades)
            
            print(f"Total Trades: {len(trades)}")
            print(f"Wins: {len(wins)} ({win_rate:.1f}%)")
            print(f"Losses: {len(trades) - len(wins)} ({100-win_rate:.1f}%)")
            print(f"Retorno Médio: {avg_return:+.2f}%")
            
            print(f"\n📋 Detalhes:")
            for i, t in enumerate(trades, 1):
                print(f"   Trade {i}: {t['entry_date'].date()} → {t['exit_date'].date()} | {t['return_pct']:+.2f}% | {t['result']}")
    
    except Exception as e:
        print(f"\n❌ Erro: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await pool.close()
        print("\n✅ Conexão fechada")


if __name__ == "__main__":
    asyncio.run(test_single_asset())
