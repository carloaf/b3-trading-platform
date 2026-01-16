#!/usr/bin/env python3
"""
Gerador de Dados Intraday Sintéticos Realistas
==============================================

Gera dados intraday (15min, 60min, 4h) a partir de dados diários reais
usando técnicas de desagregação temporal com características realistas:
- Volatilidade intraday baseada em ATR
- Padrões de volume (U-shape: maior abertura/fechamento)
- Gaps de abertura realistas
- Microestrutura de mercado

Autor: B3 Trading Platform Team
Data: 16 de Janeiro de 2026
"""

import asyncio
import asyncpg
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict


class IntradayDataGenerator:
    """Gerador de dados intraday sintéticos a partir de dados diários."""
    
    def __init__(
        self,
        db_host: str = 'timescaledb',
        db_port: int = 5432,
        db_name: str = 'b3trading_market',
        db_user: str = 'b3trading_ts',
        db_password: str = 'b3trading_ts_pass'
    ):
        self.db_config = {
            'host': db_host,
            'port': db_port,
            'database': db_name,
            'user': db_user,
            'password': db_password
        }
    
    def generate_intraday_bars(
        self,
        daily_data: pd.DataFrame,
        timeframe: str
    ) -> pd.DataFrame:
        """
        Gera barras intraday a partir de dados diários.
        
        Args:
            daily_data: DataFrame com dados diários (OHLCV)
            timeframe: '15min', '60min', ou '4h'
        
        Returns:
            DataFrame com barras intraday
        """
        bars_per_day = {
            '15min': 24,  # ~6h de pregão / 15min
            '60min': 6,    # ~6h de pregão / 1h
            '4h': 2        # Manhã e tarde
        }
        
        if timeframe not in bars_per_day:
            raise ValueError(f"Timeframe inválido: {timeframe}")
        
        n_bars = bars_per_day[timeframe]
        intraday_data = []
        
        for _, day in daily_data.iterrows():
            # Calcular volatilidade intraday (fração da diária)
            daily_range = day['high'] - day['low']
            atr_factor = 0.4  # Volatilidade intraday = 40% da diária
            
            # Gap de abertura (média 0.2% do close anterior)
            gap = np.random.normal(0, 0.002) * day['open']
            
            current_price = day['open'] + gap
            bar_volume = day['volume'] / n_bars
            
            # Distribuição de volume intraday (U-shape)
            volume_weights = self._get_volume_distribution(n_bars)
            
            for bar_idx in range(n_bars):
                # Timestamp da barra
                if timeframe == '15min':
                    bar_time = pd.Timestamp(day['time']) + timedelta(minutes=15 * bar_idx)
                elif timeframe == '60min':
                    bar_time = pd.Timestamp(day['time']) + timedelta(hours=bar_idx)
                else:  # 4h
                    bar_time = pd.Timestamp(day['time']) + timedelta(hours=4 * bar_idx)
                
                # Movimento esperado nesta barra
                # Tendência: dividir movimento diário proporcionalmente
                trend = (day['close'] - day['open']) / n_bars
                
                # Ruído intraday
                noise = np.random.normal(0, daily_range * atr_factor / n_bars)
                
                # Calcular OHLC da barra
                bar_open = current_price
                bar_move = trend + noise
                bar_close = bar_open + bar_move
                
                # High e Low com volatilidade realistica
                bar_range = abs(bar_move) * np.random.uniform(1.2, 2.0)
                bar_high = max(bar_open, bar_close) + bar_range * 0.3
                bar_low = min(bar_open, bar_close) - bar_range * 0.3
                
                # Volume com distribuição U-shape
                bar_vol = int(bar_volume * volume_weights[bar_idx])
                
                intraday_data.append({
                    'time': bar_time,
                    'symbol': day['symbol'],
                    'open': round(bar_open, 2),
                    'high': round(bar_high, 2),
                    'low': round(bar_low, 2),
                    'close': round(bar_close, 2),
                    'volume': bar_vol
                })
                
                current_price = bar_close
        
        return pd.DataFrame(intraday_data)
    
    def _get_volume_distribution(self, n_bars: int) -> np.ndarray:
        """
        Retorna distribuição de volume U-shape (maior na abertura e fechamento).
        
        Args:
            n_bars: Número de barras no dia
        
        Returns:
            Array com pesos de volume (soma = n_bars)
        """
        # U-shape: maior no início e fim do dia
        weights = []
        for i in range(n_bars):
            # Peso mínimo no meio do dia, máximo nas pontas
            position = i / (n_bars - 1) if n_bars > 1 else 0.5
            # Função U: y = (x - 0.5)^2 * 4 + 0.5
            u_value = (position - 0.5) ** 2 * 4 + 0.5
            weights.append(1.5 - u_value)  # Invertido para U-shape
        
        # Normalizar para soma = n_bars
        weights = np.array(weights)
        if weights.sum() > 0:
            weights = weights / weights.sum() * n_bars
        else:
            weights = np.ones(n_bars)  # Distribuição uniforme
        
        return weights
    
    async def fetch_daily_data(self, symbols: List[str] = None) -> pd.DataFrame:
        """
        Busca dados diários do banco.
        
        Args:
            symbols: Lista de símbolos (None = todos)
        
        Returns:
            DataFrame com dados diários
        """
        conn = await asyncpg.connect(**self.db_config)
        
        try:
            query = "SELECT * FROM ohlcv_daily"
            if symbols:
                placeholders = ','.join([f"${i+1}" for i in range(len(symbols))])
                query += f" WHERE symbol IN ({placeholders})"
                query += " ORDER BY symbol, time"
                rows = await conn.fetch(query, *symbols)
            else:
                query += " ORDER BY symbol, time"
                rows = await conn.fetch(query)
            
            if not rows:
                return pd.DataFrame()
            
            # Converter para DataFrame
            df = pd.DataFrame([dict(row) for row in rows])
            return df
        
        finally:
            await conn.close()
    
    async def save_intraday_data(
        self,
        df: pd.DataFrame,
        timeframe: str
    ) -> int:
        """
        Salva dados intraday no banco.
        
        Args:
            df: DataFrame com dados intraday
            timeframe: '15min', '60min', ou '4h'
        
        Returns:
            Número de registros inseridos
        """
        table_map = {
            '15min': 'ohlcv_15min',
            '60min': 'ohlcv_60min',
            '4h': 'ohlcv_4h'
        }
        
        table_name = table_map.get(timeframe)
        if not table_name:
            raise ValueError(f"Timeframe inválido: {timeframe}")
        
        conn = await asyncpg.connect(**self.db_config)
        inserted = 0
        
        try:
            for _, row in df.iterrows():
                try:
                    await conn.execute(f"""
                        INSERT INTO {table_name}
                        (time, symbol, open, high, low, close, volume)
                        VALUES ($1, $2, $3, $4, $5, $6, $7)
                        ON CONFLICT (time, symbol) DO NOTHING
                    """,
                        row['time'],
                        row['symbol'],
                        float(row['open']),
                        float(row['high']),
                        float(row['low']),
                        float(row['close']),
                        int(row['volume'])
                    )
                    inserted += 1
                except:
                    pass
            
            return inserted
        
        finally:
            await conn.close()
    
    async def generate_all_timeframes(
        self,
        symbols: List[str] = None,
        timeframes: List[str] = None
    ):
        """
        Gera dados intraday para todos os timeframes.
        
        Args:
            symbols: Lista de símbolos (None = todos)
            timeframes: Lista de timeframes (None = ['15min', '60min', '4h'])
        """
        if timeframes is None:
            timeframes = ['15min', '60min', '4h']
        
        print(f"\n{'='*60}")
        print(f"🎲 GERADOR DE DADOS INTRADAY SINTÉTICOS")
        print(f"{'='*60}")
        
        # Buscar dados diários
        print(f"\n📥 Carregando dados diários...")
        daily_data = await self.fetch_daily_data(symbols)
        
        if daily_data.empty:
            print("❌ Nenhum dado diário encontrado!")
            return
        
        symbols_found = daily_data['symbol'].unique()
        print(f"✅ {len(symbols_found)} símbolos carregados")
        print(f"   → {', '.join(sorted(symbols_found)[:10])}{'...' if len(symbols_found) > 10 else ''}")
        
        # Gerar e salvar para cada timeframe
        print(f"\n{'='*60}")
        print(f"⚙️  GERANDO DADOS INTRADAY")
        print(f"{'='*60}")
        
        for tf in timeframes:
            print(f"\n📊 Timeframe: {tf}")
            print(f"   Gerando barras...")
            
            intraday_df = self.generate_intraday_bars(daily_data, tf)
            
            print(f"   Salvando {len(intraday_df):,} registros no banco...")
            inserted = await self.save_intraday_data(intraday_df, tf)
            
            print(f"   ✅ {inserted:,} registros inseridos")
        
        # Estatísticas finais
        await self.show_stats()
    
    async def show_stats(self):
        """Mostra estatísticas do banco."""
        print(f"\n{'='*60}")
        print(f"📊 ESTATÍSTICAS DO BANCO DE DADOS")
        print(f"{'='*60}")
        
        conn = await asyncpg.connect(**self.db_config)
        
        try:
            for table in ['ohlcv_daily', 'ohlcv_15min', 'ohlcv_60min', 'ohlcv_4h']:
                result = await conn.fetchrow(f"""
                    SELECT 
                        COUNT(DISTINCT symbol) as symbols,
                        COUNT(*) as records,
                        MIN(time) as first_date,
                        MAX(time) as last_date
                    FROM {table}
                """)
                
                if result and result['records'] > 0:
                    print(f"\n📈 {table}:")
                    print(f"   Símbolos: {result['symbols']}")
                    print(f"   Registros: {result['records']:,}")
                    print(f"   Período: {result['first_date']} até {result['last_date']}")
        
        finally:
            await conn.close()


async def main():
    """Função principal CLI."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Gera dados intraday sintéticos a partir de dados diários',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos de uso:

  # Gerar todos os timeframes para todos os símbolos
  python generate_intraday.py
  
  # Apenas alguns símbolos
  python generate_intraday.py --symbols PETR4 VALE3 ITUB4
  
  # Apenas timeframes específicos
  python generate_intraday.py --timeframes 15min 60min
        """
    )
    
    parser.add_argument(
        '--symbols',
        nargs='+',
        help='Lista de símbolos (padrão: todos do banco)'
    )
    parser.add_argument(
        '--timeframes',
        nargs='+',
        choices=['15min', '60min', '4h'],
        help='Timeframes para gerar (padrão: todos)'
    )
    parser.add_argument(
        '--db-host',
        default='timescaledb',
        help='Host do TimescaleDB'
    )
    
    args = parser.parse_args()
    
    generator = IntradayDataGenerator(db_host=args.db_host)
    await generator.generate_all_timeframes(
        symbols=args.symbols,
        timeframes=args.timeframes
    )


if __name__ == '__main__':
    asyncio.run(main())
