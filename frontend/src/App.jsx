import { useState, useEffect } from 'react'
import { 
  TrendingUp, TrendingDown, Activity, DollarSign, 
  BarChart2, Settings, Play, Square, RefreshCw,
  ChevronRight, AlertCircle, CheckCircle
} from 'lucide-react'

// API base URL
const API_URL = '/api'

// Helper para fetch
async function apiFetch(endpoint, options = {}) {
  const response = await fetch(`${API_URL}${endpoint}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers
    }
  })
  return response.json()
}

// Componente de Card de Métrica
function MetricCard({ title, value, change, icon: Icon, positive }) {
  return (
    <div className="card">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-gray-400 text-sm">{title}</p>
          <p className="text-2xl font-bold mt-1">{value}</p>
          {change !== undefined && (
            <p className={`text-sm mt-1 ${positive ? 'status-positive' : 'status-negative'}`}>
              {positive ? '+' : ''}{change}%
            </p>
          )}
        </div>
        <div className={`p-3 rounded-lg ${positive ? 'bg-green-900/50' : 'bg-gray-700'}`}>
          <Icon className={`w-6 h-6 ${positive ? 'text-green-400' : 'text-gray-400'}`} />
        </div>
      </div>
    </div>
  )
}

// Componente de Status do Sistema
function SystemStatus({ status }) {
  const getStatusColor = (s) => {
    if (s === 'healthy') return 'text-green-400'
    if (s === 'degraded') return 'text-yellow-400'
    return 'text-red-400'
  }
  
  return (
    <div className="card">
      <h3 className="text-lg font-semibold mb-3">Status do Sistema</h3>
      <div className="space-y-2">
        {status && Object.entries(status.services || {}).map(([service, state]) => (
          <div key={service} className="flex items-center justify-between">
            <span className="text-gray-400 capitalize">{service.replace(/([A-Z])/g, ' $1')}</span>
            <span className={`flex items-center gap-1 ${getStatusColor(state)}`}>
              {state === 'healthy' ? <CheckCircle className="w-4 h-4" /> : <AlertCircle className="w-4 h-4" />}
              {state}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

// Componente de Backtest Form
function BacktestForm({ onSubmit, loading }) {
  const [form, setForm] = useState({
    strategy: 'trend_following',
    symbol: 'PETR4',
    timeframe: '1d',
    start_date: '2024-01-01',
    end_date: '2024-12-31',
    initial_capital: 100000
  })
  
  const handleSubmit = (e) => {
    e.preventDefault()
    onSubmit(form)
  }
  
  return (
    <div className="card">
      <h3 className="text-lg font-semibold mb-4">Executar Backtest</h3>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm text-gray-400 mb-1">Estratégia</label>
            <select 
              className="input w-full"
              value={form.strategy}
              onChange={(e) => setForm({...form, strategy: e.target.value})}
            >
              <option value="trend_following">Trend Following</option>
              <option value="mean_reversion">Mean Reversion</option>
              <option value="breakout">Breakout</option>
              <option value="macd_crossover">MACD Crossover</option>
            </select>
          </div>
          
          <div>
            <label className="block text-sm text-gray-400 mb-1">Símbolo</label>
            <select 
              className="input w-full"
              value={form.symbol}
              onChange={(e) => setForm({...form, symbol: e.target.value})}
            >
              <option value="WINFUT">Mini Índice (WINFUT)</option>
              <option value="WDOFUT">Mini Dólar (WDOFUT)</option>
              <option value="PETR4">Petrobras (PETR4)</option>
              <option value="VALE3">Vale (VALE3)</option>
              <option value="ITUB4">Itaú (ITUB4)</option>
              <option value="BOVA11">ETF Ibovespa (BOVA11)</option>
            </select>
          </div>
          
          <div>
            <label className="block text-sm text-gray-400 mb-1">Data Inicial</label>
            <input 
              type="date" 
              className="input w-full"
              value={form.start_date}
              onChange={(e) => setForm({...form, start_date: e.target.value})}
            />
          </div>
          
          <div>
            <label className="block text-sm text-gray-400 mb-1">Data Final</label>
            <input 
              type="date" 
              className="input w-full"
              value={form.end_date}
              onChange={(e) => setForm({...form, end_date: e.target.value})}
            />
          </div>
          
          <div>
            <label className="block text-sm text-gray-400 mb-1">Capital Inicial (R$)</label>
            <input 
              type="number" 
              className="input w-full"
              value={form.initial_capital}
              onChange={(e) => setForm({...form, initial_capital: Number(e.target.value)})}
            />
          </div>
          
          <div>
            <label className="block text-sm text-gray-400 mb-1">Timeframe</label>
            <select 
              className="input w-full"
              value={form.timeframe}
              onChange={(e) => setForm({...form, timeframe: e.target.value})}
            >
              <option value="1d">Diário (1d)</option>
              <option value="1wk">Semanal (1wk)</option>
            </select>
          </div>
        </div>
        
        <button 
          type="submit" 
          className="btn btn-primary w-full flex items-center justify-center gap-2"
          disabled={loading}
        >
          {loading ? (
            <RefreshCw className="w-4 h-4 animate-spin" />
          ) : (
            <Play className="w-4 h-4" />
          )}
          {loading ? 'Executando...' : 'Executar Backtest'}
        </button>
      </form>
    </div>
  )
}

// Componente de Resultado do Backtest
function BacktestResult({ result }) {
  if (!result) return null
  
  const isPositive = result.total_return_pct > 0
  
  return (
    <div className="card">
      <h3 className="text-lg font-semibold mb-4">Resultado do Backtest</h3>
      
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <div className="text-center p-3 bg-gray-700/50 rounded-lg">
          <p className="text-gray-400 text-sm">Retorno Total</p>
          <p className={`text-xl font-bold ${isPositive ? 'status-positive' : 'status-negative'}`}>
            {isPositive ? '+' : ''}{result.total_return_pct?.toFixed(2)}%
          </p>
        </div>
        
        <div className="text-center p-3 bg-gray-700/50 rounded-lg">
          <p className="text-gray-400 text-sm">Win Rate</p>
          <p className="text-xl font-bold text-white">{result.win_rate?.toFixed(1)}%</p>
        </div>
        
        <div className="text-center p-3 bg-gray-700/50 rounded-lg">
          <p className="text-gray-400 text-sm">Max Drawdown</p>
          <p className="text-xl font-bold text-red-400">-{result.max_drawdown_pct?.toFixed(2)}%</p>
        </div>
        
        <div className="text-center p-3 bg-gray-700/50 rounded-lg">
          <p className="text-gray-400 text-sm">Total Trades</p>
          <p className="text-xl font-bold text-white">{result.total_trades}</p>
        </div>
      </div>
      
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-sm">
        <div>
          <span className="text-gray-400">Capital Inicial:</span>
          <span className="ml-2">R$ {result.initial_capital?.toLocaleString('pt-BR')}</span>
        </div>
        <div>
          <span className="text-gray-400">Capital Final:</span>
          <span className="ml-2">R$ {result.final_capital?.toLocaleString('pt-BR')}</span>
        </div>
        <div>
          <span className="text-gray-400">Sharpe Ratio:</span>
          <span className="ml-2">{result.sharpe_ratio?.toFixed(2) || 'N/A'}</span>
        </div>
        <div>
          <span className="text-gray-400">Profit Factor:</span>
          <span className="ml-2">{result.profit_factor?.toFixed(2) || 'N/A'}</span>
        </div>
        <div>
          <span className="text-gray-400">Trades Vencedores:</span>
          <span className="ml-2 text-green-400">{result.winning_trades}</span>
        </div>
        <div>
          <span className="text-gray-400">Trades Perdedores:</span>
          <span className="ml-2 text-red-400">{result.losing_trades}</span>
        </div>
      </div>
    </div>
  )
}

// Componente de Paper Trading Status
function PaperTradingStatus({ status, onStart, onStop, onReset }) {
  if (!status) return null
  
  return (
    <div className="card">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold">Paper Trading</h3>
        <div className="flex items-center gap-2">
          {status.is_running ? (
            <span className="flex items-center gap-1 text-green-400">
              <span className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></span>
              Ativo
            </span>
          ) : (
            <span className="text-gray-400">Inativo</span>
          )}
        </div>
      </div>
      
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
        <div>
          <p className="text-gray-400 text-sm">Capital</p>
          <p className="text-lg font-bold">R$ {status.current_capital?.toLocaleString('pt-BR')}</p>
        </div>
        <div>
          <p className="text-gray-400 text-sm">P&L Total</p>
          <p className={`text-lg font-bold ${status.total_pnl >= 0 ? 'status-positive' : 'status-negative'}`}>
            R$ {status.total_pnl?.toLocaleString('pt-BR')}
          </p>
        </div>
        <div>
          <p className="text-gray-400 text-sm">Retorno</p>
          <p className={`text-lg font-bold ${status.return_pct >= 0 ? 'status-positive' : 'status-negative'}`}>
            {status.return_pct?.toFixed(2)}%
          </p>
        </div>
        <div>
          <p className="text-gray-400 text-sm">Win Rate</p>
          <p className="text-lg font-bold">{status.win_rate?.toFixed(1)}%</p>
        </div>
      </div>
      
      <div className="flex gap-2">
        {!status.is_running ? (
          <button onClick={onStart} className="btn btn-primary flex items-center gap-2">
            <Play className="w-4 h-4" /> Iniciar
          </button>
        ) : (
          <button onClick={onStop} className="btn btn-danger flex items-center gap-2">
            <Square className="w-4 h-4" /> Parar
          </button>
        )}
        <button onClick={onReset} className="btn btn-secondary flex items-center gap-2">
          <RefreshCw className="w-4 h-4" /> Resetar
        </button>
      </div>
    </div>
  )
}

// App Principal
function App() {
  const [systemStatus, setSystemStatus] = useState(null)
  const [backtestResult, setBacktestResult] = useState(null)
  const [backtestLoading, setBacktestLoading] = useState(false)
  const [paperStatus, setPaperStatus] = useState(null)
  const [activeTab, setActiveTab] = useState('dashboard')
  
  // Carregar status inicial
  useEffect(() => {
    loadSystemStatus()
    loadPaperStatus()
    
    // Atualizar a cada 30 segundos
    const interval = setInterval(() => {
      loadSystemStatus()
      loadPaperStatus()
    }, 30000)
    
    return () => clearInterval(interval)
  }, [])
  
  const loadSystemStatus = async () => {
    try {
      const data = await apiFetch('/health'.replace('/api', ''))
      setSystemStatus(data)
    } catch (err) {
      console.error('Error loading status:', err)
    }
  }
  
  const loadPaperStatus = async () => {
    try {
      const data = await apiFetch('/paper/status')
      setPaperStatus(data)
    } catch (err) {
      console.error('Error loading paper status:', err)
    }
  }
  
  const runBacktest = async (params) => {
    setBacktestLoading(true)
    setBacktestResult(null)
    try {
      const data = await apiFetch('/backtest/run', {
        method: 'POST',
        body: JSON.stringify(params)
      })
      setBacktestResult(data)
    } catch (err) {
      console.error('Error running backtest:', err)
      alert('Erro ao executar backtest. Verifique se o serviço está disponível.')
    } finally {
      setBacktestLoading(false)
    }
  }
  
  const handlePaperReset = async () => {
    try {
      await apiFetch('/paper/reset', { method: 'POST' })
      loadPaperStatus()
    } catch (err) {
      console.error('Error resetting paper:', err)
    }
  }
  
  return (
    <div className="min-h-screen bg-gray-900">
      {/* Header */}
      <header className="bg-gray-800 border-b border-gray-700 px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-green-600 rounded-lg flex items-center justify-center">
              <TrendingUp className="w-6 h-6 text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold">B3 Trading Platform</h1>
              <p className="text-sm text-gray-400">Mini Índice & Ações</p>
            </div>
          </div>
          
          <nav className="flex items-center gap-4">
            {['dashboard', 'backtest', 'paper', 'signals'].map(tab => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`px-4 py-2 rounded-lg capitalize transition-colors ${
                  activeTab === tab 
                    ? 'bg-green-600 text-white' 
                    : 'text-gray-400 hover:text-white'
                }`}
              >
                {tab}
              </button>
            ))}
          </nav>
        </div>
      </header>
      
      {/* Main Content */}
      <main className="p-6">
        {activeTab === 'dashboard' && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <MetricCard 
                title="Capital Total" 
                value={`R$ ${paperStatus?.current_capital?.toLocaleString('pt-BR') || '100.000'}`}
                change={paperStatus?.return_pct?.toFixed(2)}
                positive={paperStatus?.return_pct >= 0}
                icon={DollarSign}
              />
              <MetricCard 
                title="Total Trades" 
                value={paperStatus?.total_trades || 0}
                icon={Activity}
                positive={true}
              />
              <MetricCard 
                title="Win Rate" 
                value={`${paperStatus?.win_rate?.toFixed(1) || 0}%`}
                icon={BarChart2}
                positive={paperStatus?.win_rate > 50}
              />
              <MetricCard 
                title="P&L Hoje" 
                value={`R$ ${paperStatus?.realized_pnl?.toLocaleString('pt-BR') || '0'}`}
                change={paperStatus?.return_pct?.toFixed(2)}
                positive={paperStatus?.realized_pnl >= 0}
                icon={TrendingUp}
              />
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <SystemStatus status={systemStatus} />
              <PaperTradingStatus 
                status={paperStatus}
                onStart={() => {}}
                onStop={() => {}}
                onReset={handlePaperReset}
              />
            </div>
          </div>
        )}
        
        {activeTab === 'backtest' && (
          <div className="space-y-6">
            <BacktestForm onSubmit={runBacktest} loading={backtestLoading} />
            <BacktestResult result={backtestResult} />
          </div>
        )}
        
        {activeTab === 'paper' && (
          <div className="space-y-6">
            <PaperTradingStatus 
              status={paperStatus}
              onStart={() => {}}
              onStop={() => {}}
              onReset={handlePaperReset}
            />
            
            <div className="card">
              <h3 className="text-lg font-semibold mb-4">Posições Abertas</h3>
              <p className="text-gray-400">Nenhuma posição aberta</p>
            </div>
            
            <div className="card">
              <h3 className="text-lg font-semibold mb-4">Histórico de Trades</h3>
              <p className="text-gray-400">Nenhum trade executado</p>
            </div>
          </div>
        )}
        
        {activeTab === 'signals' && (
          <div className="card">
            <h3 className="text-lg font-semibold mb-4">Sinais em Tempo Real</h3>
            <p className="text-gray-400">Configure os símbolos para monitorar sinais de trading.</p>
          </div>
        )}
      </main>
      
      {/* Footer */}
      <footer className="border-t border-gray-700 px-6 py-4 text-center text-gray-500 text-sm">
        B3 Trading Platform © 2026 - Desenvolvido para o mercado brasileiro 🇧🇷
      </footer>
    </div>
  )
}

export default App
