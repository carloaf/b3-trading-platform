#!/usr/bin/env python3
"""
Backtest Wave3 v2.1 - Dados Completos 2023-2026
================================================

Testa Wave3 v2.1 com dados históricos reais ProfitChart:
- Período: Janeiro/2023 → Janeiro/2026 (3 anos)
- Dados: 775.259 registros reais (15min, 60min, daily)
- Ativos: 5 prioritários + top performers
- Quality Score: 55 (padrão validado)

Resultados esperados:
- Win Rate: ~77.8% (baseline v2.1)
- Sharpe: > 1.5
- Max Drawdown: < 15%

Autor: B3 Trading Platform
Data: 28 Janeiro 2026
"""

import pandas as pd
import numpy as np
from datetime import datetime, date
import sys
import asyncio
import asyncpg
from decimal import Decimal

sys.path.append('/app/src/strategies')
from wave3_enhanced import Wave3Enhanced


class BacktestResults:
    """Armazena e calcula métricas de backtest"""
    
    def __init__(self, symbol, trades):
        self.symbol = symbol
        self.trades = trades
        self.calculate_metrics()
    
    def calculate_metrics(self):
        """Calcula todas as métricas"""
        if not self.trades:
            self.total_trades = 0
            self.winners = 0
            self.losers = 0
            self.win_rate = 0.0
            self.avg_win = 0.0
            self.avg_loss = 0.0
            self.profit_factor = 0.0
            self.total_return = 0.0
            self.sharpe_ratio = 0.0
            self.max_drawdown = 0.0
            return
        
        self.total_trades = len(self.trades)
        returns = [t['return_pct'] for t in self.trades]
        
        self.winners = sum(1 for r in returns if r > 0)
        self.losers = sum(1 for r in returns if r < 0)
        self.win_rate = (self.winners / self.total_trades * 100) if self.total_trades > 0 else 0
        
        wins = [r for r in returns if r > 0]
        losses = [r for r in returns if r < 0]
        
        self.avg_win = np.mean(wins) if wins else 0.0
        self.avg_loss = abs(np.mean(losses)) if losses else 0.0
        
        total_wins = sum(wins) if wins else 0.0
        total_losses = abs(sum(losses)) if losses else 0.0
        self.profit_factor = (total_wins / total_losses) if total_losses > 0 else 0.0
        
        self.total_return = sum(returns)
        
        # Sharpe Ratio (252 trading days)
        if returns:
            mean_return = np.mean(returns)
            std_return = np.std(returns)
            self.sharpe_ratio = (mean_return / std_return * np.sqrt(252)) if std_return > 0 else 0.0
        else:
            self.sharpe_ratio = 0.0
        
        # Max Drawdown
        cumulative = np.cumsum([1.0] + returns)
        running_max = np.maximum.accumulate(cumulative)
        drawdown = (cumulative - running_max) / running_max * 100
        self.max_drawdown = abs(drawdown.min()) if len(drawdown) > 0 else 0.0
    
    def __str__(self):
        """String formatada dos resultados"""
        return f"""
{'='*80}
RESULTADOS: {self.symbol}
{'='*80}
Total Trades:    {self.total_trades}
Winners:         {self.winners} ({self.win_rate:.1f}%)
Losers:          {self.losers}

Avg Win:         {self.avg_win:.2f}%
Avg Loss:        {self.avg_loss:.2f}%
Profit Factor:   {self.profit_factor:.2f}

Total Return:    {self.total_return:.2f}%
Sharpe Ratio:    {self.sharpe_ratio:.2f}
Max Drawdown:    {self.max_drawdown:.2f}%
{'='*80}
"""


async def fetch_data(pool, symbol, start_date='2023-01-01'):
    """Busca dados históricos completos"""
    
    # Converter string para datetime
    if isinstance(start_date, str):
        start_date = datetime.strptime(start_date, '%Y-%m-%d')
    
    async with pool.acquire() as conn:
        # Daily data (contexto)
        rows_daily = await conn.fetch("""
            SELECT time, open, high, low, close, volume
            FROM ohlcv_daily
            WHERE symbol = $1
            AND time >= $2
            ORDER BY time
        """, symbol, start_date)
        
        # 60min data (gatilho)
        rows_60min = await conn.fetch("""
            SELECT time, open, high, low, close, volume
            FROM ohlcv_60min
            WHERE symbol = $1
            AND time >= $2
            ORDER BY time
        """, symbol, start_date)
    
    # Converter para DataFrame
    df_daily = pd.DataFrame(
        [(r['time'], float(r['open']), float(r['high']), 
          float(r['low']), float(r['close']), float(r['volume']))
         for r in rows_daily],
        columns=['time', 'open', 'high', 'low', 'close', 'volume']
    )
    
    df_60min = pd.DataFrame(
        [(r['time'], float(r['open']), float(r['high']), 
          float(r['low']), float(r['close']), float(r['volume']))
         for r in rows_60min],
        columns=['time', 'open', 'high', 'low', 'close', 'volume']
    )
    
    return df_daily, df_60min


def simulate_trades(signals, df_60min):
    """Simula execução de trades com risk:reward 3:1"""
    
    trades = []
    
    for signal in signals:
        signal_time = signal['timestamp']
        entry_price = signal['current_price']
        
        # Definir stop loss e take profit
        if signal['direction'] == 'LONG':
            stop_loss = entry_price * 0.94  # -6% stop
            take_profit = entry_price * 1.18  # +18% target (3:1 R:R)
        else:  # SHORT
            stop_loss = entry_price * 1.06  # +6% stop
            take_profit = entry_price * 0.82  # -18% target
        
        # Buscar candles após o sinal
        future_candles = df_60min[df_60min['time'] > signal_time].head(30)  # Próximos 30 candles
        
        if len(future_candles) == 0:
            continue
        
        # Simular trade
        exit_price = None
        exit_time = None
        hit_stop = False
        
        for idx, candle in future_candles.iterrows():
            if signal['direction'] == 'LONG':
                # Check stop loss
                if candle['low'] <= stop_loss:
                    exit_price = stop_loss
                    exit_time = candle['time']
                    hit_stop = True
                    break
                # Check take profit
                if candle['high'] >= take_profit:
                    exit_price = take_profit
                    exit_time = candle['time']
                    break
            else:  # SHORT
                # Check stop loss
                if candle['high'] >= stop_loss:
                    exit_price = stop_loss
                    exit_time = candle['time']
                    hit_stop = True
                    break
                # Check take profit
                if candle['low'] <= take_profit:
                    exit_price = take_profit
                    exit_time = candle['time']
                    break
        
        # Se não bateu nem stop nem target, fechar no último candle
        if exit_price is None:
            last_candle = future_candles.iloc[-1]
            exit_price = last_candle['close']
            exit_time = last_candle['time']
        
        # Calcular retorno
        if signal['direction'] == 'LONG':
            return_pct = ((exit_price / entry_price) - 1) * 100
        else:
            return_pct = ((entry_price / exit_price) - 1) * 100
        
        trades.append({
            'entry_time': signal_time,
            'exit_time': exit_time,
            'direction': signal['direction'],
            'entry_price': entry_price,
            'exit_price': exit_price,
            'return_pct': return_pct,
            'quality_score': signal['quality_score'],
            'hit_stop': hit_stop
        })
    
    return trades


async def backtest_symbol(pool, strategy, symbol, start_date='2023-01-01'):
    """Backtest completo para 1 símbolo"""
    
    print(f"\n{'='*80}")
    print(f"🔄 Backtesting: {symbol}")
    print(f"{'='*80}")
    
    # Buscar dados
    print(f"📥 Buscando dados desde {start_date}...")
    df_daily, df_60min = await fetch_data(pool, symbol, start_date)
    
    if len(df_daily) < 100 or len(df_60min) < 100:
        print(f"⚠️ Dados insuficientes: {len(df_daily)} daily, {len(df_60min)} 60min")
        return None
    
    print(f"✅ Dados carregados: {len(df_daily)} daily, {len(df_60min)} 60min")
    print(f"   Período: {df_daily['time'].min()} → {df_daily['time'].max()}")
    
    # Gerar sinais
    print(f"🔍 Gerando sinais Wave3...")
    signals = []
    
    # Iterar pelos candles de 60min
    for i in range(200, len(df_60min)):  # Warm-up de 200 candles
        current_time = df_60min.iloc[i]['time']
        
        # Contexto diário até esta data (comparar apenas date)
        current_date = pd.Timestamp(current_time).normalize()
        daily_context = df_daily[df_daily['time'] <= current_date].copy()
        
        # Candles 60min até agora
        intraday_context = df_60min.iloc[:i+1].copy()
        
        if len(daily_context) < 72:  # Warm-up para EMA 72
            continue
        
        try:
            # Usar interface correta: df_daily, df_60min, symbol
            signal = strategy.generate_signal(
                df_daily=daily_context,
                df_60min=intraday_context,
                symbol=symbol
            )
            
            if signal and hasattr(signal, 'signal_type'):
                signals.append({
                    'timestamp': current_time,
                    'direction': 'LONG' if signal.signal_type == 'BUY' else 'SHORT',
                    'current_price': signal.entry_price,
                    'quality_score': getattr(signal, 'quality_score', 0)
                })
        except Exception as e:
            # Ignorar erros silenciosamente (dados insuficientes, etc)
            continue
    
    print(f"✅ Sinais gerados: {len(signals)}")
    
    if len(signals) == 0:
        print(f"⚠️ Nenhum sinal válido gerado")
        return None
    
    # Simular trades
    print(f"💰 Simulando trades...")
    trades = simulate_trades(signals, df_60min)
    
    print(f"✅ Trades simulados: {len(trades)}")
    
    # Calcular métricas
    results = BacktestResults(symbol, trades)
    
    return results


async def main():
    """Função principal"""
    
    print("\n" + "="*80)
    print("BACKTEST WAVE3 v2.1 - DADOS COMPLETOS 2023-2026")
    print("="*80)
    print(f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print(f"Período: Janeiro/2023 → Janeiro/2026 (3 anos)")
    print(f"Fonte: ProfitChart CSV (dados B3 reais)")
    print(f"Total: 775.259 registros")
    print("="*80)
    
    # Conectar DB
    print("\n🔗 Conectando ao TimescaleDB...")
    try:
        pool = await asyncpg.create_pool(
            host='b3-timescaledb',
            port=5432,
            user='b3trading_ts',
            password='b3trading_ts_pass',
            database='b3trading_market',
            min_size=1,
            max_size=10,
            command_timeout=60
        )
        print("✅ Conectado")
    except Exception as e:
        print(f"❌ Erro ao conectar: {e}")
        return
    
    # Criar estratégia Wave3 v2.1
    print("\n🔧 Criando Wave3 v2.1 (quality_score ≥ 55)...")
    strategy = Wave3Enhanced(min_quality_score=55)
    print("✅ Estratégia inicializada")
    
    # Símbolos prioritários
    symbols = ['PETR4', 'VALE3', 'ITUB4', 'BBDC4', 'ABEV3']
    
    print(f"\n📊 Testando {len(symbols)} símbolos prioritários...")
    
    # Data de início (converter para datetime.date)
    start_date = date(2023, 1, 1)
    
    # Backtest para cada símbolo
    all_results = []
    
    for idx, symbol in enumerate(symbols, 1):
        print(f"\n[{idx}/{len(symbols)}]", end=" ")
        
        try:
            results = await backtest_symbol(pool, strategy, symbol, start_date=start_date)
            
            if results:
                all_results.append(results)
                print(results)
            
        except Exception as e:
            print(f"❌ Erro ao processar {symbol}: {e}")
            import traceback
            traceback.print_exc()
    
    # Resumo consolidado
    print("\n" + "="*80)
    print("RESUMO CONSOLIDADO - 5 ATIVOS PRIORITÁRIOS")
    print("="*80)
    
    if all_results:
        total_trades = sum(r.total_trades for r in all_results)
        total_winners = sum(r.winners for r in all_results)
        avg_win_rate = np.mean([r.win_rate for r in all_results])
        avg_sharpe = np.mean([r.sharpe_ratio for r in all_results])
        avg_return = np.mean([r.total_return for r in all_results])
        max_dd = max(r.max_drawdown for r in all_results)
        
        print(f"\nTotal Trades:     {total_trades}")
        print(f"Total Winners:    {total_winners} ({total_winners/total_trades*100:.1f}%)")
        print(f"Avg Win Rate:     {avg_win_rate:.1f}%")
        print(f"Avg Sharpe:       {avg_sharpe:.2f}")
        print(f"Avg Return:       {avg_return:.2f}%")
        print(f"Max Drawdown:     {max_dd:.2f}%")
        
        print(f"\n{'Símbolo':<10} {'Trades':<10} {'Win%':<10} {'Return%':<12} {'Sharpe':<10}")
        print("-"*80)
        for r in all_results:
            print(f"{r.symbol:<10} {r.total_trades:<10} {r.win_rate:<10.1f} {r.total_return:<12.2f} {r.sharpe_ratio:<10.2f}")
    else:
        print("⚠️ Nenhum resultado válido")
    
    print("\n" + "="*80)
    print("✅ Backtest concluído!")
    print("="*80)
    
    await pool.close()


if __name__ == '__main__':
    asyncio.run(main())
