import { useState, useEffect } from 'react'
import { Play, Square, RefreshCw, TrendingUp, Target, Clock, CheckCircle, AlertCircle } from 'lucide-react'
import { API_URLS } from '../config/api'

// API URL (백테스트/튜닝은 PC의 8001 포트 사용)
const API_BASE_URL = API_URLS.strategy

interface BacktestParams {
  start_date: string
  end_date: string
  ma_period: number
  rsi_period: number
  stop_loss: number
  initial_capital: number
}

interface BacktestResult {
  cagr: number
  sharpe_ratio: number
  max_drawdown: number
  total_return: number
  num_trades: number
  win_rate: number
}

interface TuningTrial {
  trial_number: number
  params: BacktestParams
  result: BacktestResult
  timestamp: string
}

interface TuningStatus {
  is_running: boolean
  current_trial: number
  total_trials: number
  best_sharpe: number
  best_params: BacktestParams | null
  trials: TuningTrial[]
}

export default function Strategy() {
  // 백테스트 상태
  const [backtestParams, setBacktestParams] = useState<BacktestParams>({
    start_date: '2024-01-01',
    end_date: new Date().toISOString().split('T')[0],
    ma_period: 60,
    rsi_period: 14,
    stop_loss: -8,
    initial_capital: 10000000,
  })
  const [backtestResult, setBacktestResult] = useState<BacktestResult | null>(null)
  const [backtestLoading, setBacktestLoading] = useState(false)
  const [backtestError, setBacktestError] = useState<string | null>(null)

  // 튜닝 상태
  const [tuningTrials, setTuningTrials] = useState(50)
  const [tuningStatus, setTuningStatus] = useState<TuningStatus>({
    is_running: false,
    current_trial: 0,
    total_trials: 0,
    best_sharpe: 0,
    best_params: null,
    trials: [],
  })

  // 히스토리
  const [history, setHistory] = useState<TuningTrial[]>([])

  // 백테스트 실행
  const runBacktest = async () => {
    setBacktestLoading(true)
    setBacktestError(null)
    
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/backtest/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(backtestParams),
      })
      
      if (!res.ok) throw new Error('백테스트 실행 실패')
      
      const data = await res.json()
      setBacktestResult(data)
      
      // 히스토리에 추가
      setHistory(prev => [{
        trial_number: prev.length + 1,
        params: backtestParams,
        result: data,
        timestamp: new Date().toISOString(),
      }, ...prev].slice(0, 20))
      
    } catch (err) {
      setBacktestError(err instanceof Error ? err.message : '백테스트 실패')
    } finally {
      setBacktestLoading(false)
    }
  }

  // 튜닝 시작
  const startTuning = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/tuning/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          trials: tuningTrials,
          start_date: backtestParams.start_date,
          end_date: backtestParams.end_date,
        }),
      })
      
      if (!res.ok) throw new Error('튜닝 시작 실패')
      
      setTuningStatus(prev => ({ ...prev, is_running: true, total_trials: tuningTrials }))
      
    } catch (err) {
      alert(err instanceof Error ? err.message : '튜닝 시작 실패')
    }
  }

  // 튜닝 중지
  const stopTuning = async () => {
    try {
      await fetch(`${API_BASE_URL}/api/v1/tuning/stop`, { method: 'POST' })
      setTuningStatus(prev => ({ ...prev, is_running: false }))
    } catch (err) {
      console.error('튜닝 중지 실패:', err)
    }
  }

  // 튜닝 상태 폴링
  useEffect(() => {
    if (!tuningStatus.is_running) return
    
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/api/v1/tuning/status`)
        if (res.ok) {
          const data = await res.json()
          setTuningStatus(data)
          
          // 튜닝 완료 시 히스토리에 추가
          if (!data.is_running && data.trials && data.trials.length > 0) {
            setHistory(prev => {
              const newItems = data.trials.map((t: TuningTrial) => ({
                ...t,
                timestamp: new Date().toISOString()
              }))
              return [...newItems, ...prev].slice(0, 50)
            })
            clearInterval(interval)
          }
        }
      } catch (err) {
        console.error('상태 조회 실패:', err)
      }
    }, 2000)
    
    return () => clearInterval(interval)
  }, [tuningStatus.is_running])

  // 최적 파라미터 적용
  const applyBestParams = () => {
    if (tuningStatus.best_params) {
      setBacktestParams(tuningStatus.best_params)
      alert('최적 파라미터가 적용되었습니다!')
    }
  }

  const formatPercent = (value: number) => `${value >= 0 ? '+' : ''}${(value * 100).toFixed(2)}%`

  return (
    <div className="space-y-6">
      <h2 className="text-3xl font-bold">전략 튜닝</h2>
      
      {/* 1. 빠른 백테스트 */}
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-xl font-bold mb-4 flex items-center gap-2">
          <TrendingUp className="w-5 h-5" />
          빠른 백테스트
        </h3>
        
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4 mb-4">
          <div>
            <label className="block text-sm text-gray-600 mb-1">시작일</label>
            <input
              type="date"
              value={backtestParams.start_date}
              onChange={e => setBacktestParams(p => ({ ...p, start_date: e.target.value }))}
              className="w-full border rounded px-3 py-2"
            />
          </div>
          <div>
            <label className="block text-sm text-gray-600 mb-1">종료일</label>
            <input
              type="date"
              value={backtestParams.end_date}
              onChange={e => setBacktestParams(p => ({ ...p, end_date: e.target.value }))}
              className="w-full border rounded px-3 py-2"
            />
          </div>
          <div>
            <label className="block text-sm text-gray-600 mb-1">MA 기간</label>
            <input
              type="number"
              value={backtestParams.ma_period}
              onChange={e => setBacktestParams(p => ({ ...p, ma_period: parseInt(e.target.value) }))}
              className="w-full border rounded px-3 py-2"
              min={10}
              max={200}
            />
          </div>
          <div>
            <label className="block text-sm text-gray-600 mb-1">RSI 기간</label>
            <input
              type="number"
              value={backtestParams.rsi_period}
              onChange={e => setBacktestParams(p => ({ ...p, rsi_period: parseInt(e.target.value) }))}
              className="w-full border rounded px-3 py-2"
              min={5}
              max={30}
            />
          </div>
          <div>
            <label className="block text-sm text-gray-600 mb-1">손절 (%)</label>
            <input
              type="number"
              value={backtestParams.stop_loss}
              onChange={e => setBacktestParams(p => ({ ...p, stop_loss: parseInt(e.target.value) }))}
              className="w-full border rounded px-3 py-2"
              min={-30}
              max={-1}
            />
          </div>
          <div className="flex items-end">
            <button
              onClick={runBacktest}
              disabled={backtestLoading}
              className="w-full bg-blue-600 text-white rounded px-4 py-2 flex items-center justify-center gap-2 hover:bg-blue-700 disabled:opacity-50"
            >
              {backtestLoading ? (
                <RefreshCw className="w-4 h-4 animate-spin" />
              ) : (
                <Play className="w-4 h-4" />
              )}
              실행
            </button>
          </div>
        </div>
        
        {backtestError && (
          <div className="bg-red-50 text-red-600 p-3 rounded mb-4 flex items-center gap-2">
            <AlertCircle className="w-4 h-4" />
            {backtestError}
          </div>
        )}
        
        {backtestResult && (
          <div className="grid grid-cols-2 md:grid-cols-6 gap-4 bg-gray-50 p-4 rounded">
            <div>
              <div className="text-sm text-gray-600">CAGR</div>
              <div className={`text-xl font-bold ${backtestResult.cagr >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                {formatPercent(backtestResult.cagr)}
              </div>
            </div>
            <div>
              <div className="text-sm text-gray-600">Sharpe Ratio</div>
              <div className="text-xl font-bold">{backtestResult.sharpe_ratio.toFixed(2)}</div>
            </div>
            <div>
              <div className="text-sm text-gray-600">MDD</div>
              <div className="text-xl font-bold text-red-600">{formatPercent(backtestResult.max_drawdown)}</div>
            </div>
            <div>
              <div className="text-sm text-gray-600">총 수익률</div>
              <div className={`text-xl font-bold ${backtestResult.total_return >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                {formatPercent(backtestResult.total_return)}
              </div>
            </div>
            <div>
              <div className="text-sm text-gray-600">거래 횟수</div>
              <div className="text-xl font-bold">{backtestResult.num_trades}</div>
            </div>
            <div>
              <div className="text-sm text-gray-600">승률</div>
              <div className="text-xl font-bold">{formatPercent(backtestResult.win_rate)}</div>
            </div>
          </div>
        )}
      </div>
      
      {/* 2. 자동 튜닝 */}
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-xl font-bold mb-4 flex items-center gap-2">
          <Target className="w-5 h-5" />
          자동 튜닝 (Optuna)
        </h3>
        
        <div className="flex items-center gap-4 mb-4">
          <div>
            <label className="block text-sm text-gray-600 mb-1">Trials</label>
            <input
              type="number"
              value={tuningTrials}
              onChange={e => setTuningTrials(parseInt(e.target.value))}
              className="w-32 border rounded px-3 py-2"
              min={10}
              max={500}
              disabled={tuningStatus.is_running}
            />
          </div>
          
          {!tuningStatus.is_running ? (
            <button
              onClick={startTuning}
              className="bg-green-600 text-white rounded px-6 py-2 flex items-center gap-2 hover:bg-green-700 mt-6"
            >
              <Play className="w-4 h-4" />
              튜닝 시작
            </button>
          ) : (
            <button
              onClick={stopTuning}
              className="bg-red-600 text-white rounded px-6 py-2 flex items-center gap-2 hover:bg-red-700 mt-6"
            >
              <Square className="w-4 h-4" />
              중지
            </button>
          )}
          
          {tuningStatus.best_params && (
            <button
              onClick={applyBestParams}
              className="bg-purple-600 text-white rounded px-6 py-2 flex items-center gap-2 hover:bg-purple-700 mt-6"
            >
              <CheckCircle className="w-4 h-4" />
              최적 파라미터 적용
            </button>
          )}
        </div>
        
        {tuningStatus.is_running && (
          <div className="mb-4">
            <div className="flex justify-between text-sm text-gray-600 mb-1">
              <span>진행률</span>
              <span>{tuningStatus.current_trial} / {tuningStatus.total_trials}</span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-3">
              <div
                className="bg-green-600 h-3 rounded-full transition-all"
                style={{ width: `${(tuningStatus.current_trial / tuningStatus.total_trials) * 100}%` }}
              />
            </div>
            {tuningStatus.best_sharpe > 0 && (
              <div className="mt-2 text-sm text-gray-600">
                현재 최적: Sharpe {tuningStatus.best_sharpe.toFixed(2)}
              </div>
            )}
          </div>
        )}
        
        {tuningStatus.trials.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-100">
                <tr>
                  <th className="px-3 py-2 text-left">#</th>
                  <th className="px-3 py-2 text-left">MA</th>
                  <th className="px-3 py-2 text-left">RSI</th>
                  <th className="px-3 py-2 text-left">손절</th>
                  <th className="px-3 py-2 text-left">Sharpe</th>
                  <th className="px-3 py-2 text-left">CAGR</th>
                  <th className="px-3 py-2 text-left">MDD</th>
                </tr>
              </thead>
              <tbody>
                {tuningStatus.trials.slice(0, 10).map((trial, idx) => (
                  <tr key={idx} className={idx === 0 ? 'bg-green-50' : ''}>
                    <td className="px-3 py-2">{trial.trial_number}</td>
                    <td className="px-3 py-2">{trial.params.ma_period}</td>
                    <td className="px-3 py-2">{trial.params.rsi_period}</td>
                    <td className="px-3 py-2">{trial.params.stop_loss}%</td>
                    <td className="px-3 py-2 font-bold">{trial.result.sharpe_ratio.toFixed(2)}</td>
                    <td className="px-3 py-2">{formatPercent(trial.result.cagr)}</td>
                    <td className="px-3 py-2 text-red-600">{formatPercent(trial.result.max_drawdown)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
      
      {/* 3. 히스토리 */}
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-xl font-bold mb-4 flex items-center gap-2">
          <Clock className="w-5 h-5" />
          백테스트 히스토리
        </h3>
        
        {history.length === 0 ? (
          <p className="text-gray-500">아직 백테스트 기록이 없습니다.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-100">
                <tr>
                  <th className="px-3 py-2 text-left">시간</th>
                  <th className="px-3 py-2 text-left">기간</th>
                  <th className="px-3 py-2 text-left">MA</th>
                  <th className="px-3 py-2 text-left">RSI</th>
                  <th className="px-3 py-2 text-left">손절</th>
                  <th className="px-3 py-2 text-left">Sharpe</th>
                  <th className="px-3 py-2 text-left">CAGR</th>
                  <th className="px-3 py-2 text-left">MDD</th>
                </tr>
              </thead>
              <tbody>
                {history.map((item, idx) => (
                  <tr key={idx} className="hover:bg-gray-50">
                    <td className="px-3 py-2 text-gray-500">
                      {new Date(item.timestamp).toLocaleTimeString()}
                    </td>
                    <td className="px-3 py-2">{item.params.start_date} ~ {item.params.end_date}</td>
                    <td className="px-3 py-2">{item.params.ma_period}</td>
                    <td className="px-3 py-2">{item.params.rsi_period}</td>
                    <td className="px-3 py-2">{item.params.stop_loss}%</td>
                    <td className="px-3 py-2 font-bold">{item.result.sharpe_ratio.toFixed(2)}</td>
                    <td className={`px-3 py-2 ${item.result.cagr >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                      {formatPercent(item.result.cagr)}
                    </td>
                    <td className="px-3 py-2 text-red-600">{formatPercent(item.result.max_drawdown)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
