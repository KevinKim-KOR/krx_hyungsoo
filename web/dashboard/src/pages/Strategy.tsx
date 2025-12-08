import { useState, useEffect } from 'react'
import { Play, Square, RefreshCw, TrendingUp, Target, Clock, CheckCircle, AlertCircle, Database, BarChart3, HardDrive, Download } from 'lucide-react'
import { API_URLS } from '../config/api'
import { apiClient } from '../api/client'

// API URL (백테스트/튜닝은 PC의 8001 포트 사용)
const API_BASE_URL = API_URLS.strategy

interface CacheStatus {
  exists: boolean
  file_count: number
  last_date: string | null
  is_running: boolean
  progress: number
  total: number
  updated: number
  skipped: number
  failed: number
  errors: string[]
  message: string
}

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
  lookback_months?: number
  params: BacktestParams
  result: BacktestResult
  timestamp: string
}

interface LookbackResult {
  best_params: Record<string, number>
  best_value: number
  n_trials: number
}

interface TuningStatus {
  is_running: boolean
  current_trial: number
  total_trials: number
  best_sharpe: number
  best_params: BacktestParams | null
  trials: TuningTrial[]
  lookback_results?: Record<number, LookbackResult>
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
    lookback_results: {},
  })

  // 히스토리 (localStorage에서 복원)
  const [history, setHistory] = useState<TuningTrial[]>(() => {
    try {
      const saved = localStorage.getItem('backtest_history')
      return saved ? JSON.parse(saved) : []
    } catch {
      return []
    }
  })
  
  // 히스토리 변경 시 localStorage에 저장
  useEffect(() => {
    localStorage.setItem('backtest_history', JSON.stringify(history))
  }, [history])

  // DB 히스토리 상태
  const [dbHistory, setDbHistory] = useState<any[]>([])
  const [tuningSessions, setTuningSessions] = useState<any[]>([])
  const [statistics, setStatistics] = useState<any>(null)
  const [dbLoading, setDbLoading] = useState(false)
  const [activeTab, setActiveTab] = useState<'local' | 'db' | 'sessions' | 'stats'>('local')

  // 캐시 상태
  const [cacheStatus, setCacheStatus] = useState<CacheStatus>({
    exists: false,
    file_count: 0,
    last_date: null,
    is_running: false,
    progress: 0,
    total: 0,
    updated: 0,
    skipped: 0,
    failed: 0,
    errors: [],
    message: '',
  })

  // 캐시 상태 조회
  const loadCacheStatus = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/cache/status`)
      if (res.ok) {
        const data = await res.json()
        setCacheStatus(data)
      }
    } catch (err) {
      console.error('캐시 상태 조회 실패:', err)
    }
  }

  // 캐시 업데이트 시작
  const startCacheUpdate = async () => {
    try {
      // 즉시 UI 업데이트
      setCacheStatus(prev => ({ ...prev, is_running: true, progress: 0, total: 0, message: '업데이트 시작 중...' }))
      
      const res = await fetch(`${API_BASE_URL}/api/v1/cache/update`, { method: 'POST' })
      if (!res.ok) {
        setCacheStatus(prev => ({ ...prev, is_running: false, message: '시작 실패' }))
      }
    } catch (err) {
      console.error('캐시 업데이트 시작 실패:', err)
      setCacheStatus(prev => ({ ...prev, is_running: false, message: '연결 실패' }))
    }
  }

  // 캐시 상태 폴링 (항상 실행)
  useEffect(() => {
    loadCacheStatus()
    
    const interval = setInterval(() => {
      loadCacheStatus()
    }, 1500)

    return () => clearInterval(interval)
  }, [])

  // DB 히스토리 로드
  const loadDbHistory = async () => {
    setDbLoading(true)
    try {
      const [historyRes, sessionsRes, statsRes] = await Promise.all([
        apiClient.getBacktestHistoryFromDB(50),
        apiClient.getTuningSessions(10),
        apiClient.getHistoryStatistics(),
      ])
      setDbHistory(historyRes.history || [])
      setTuningSessions(sessionsRes.sessions || [])
      setStatistics(statsRes)
    } catch (err) {
      console.error('DB 히스토리 로드 실패:', err)
    } finally {
      setDbLoading(false)
    }
  }

  // 탭 변경 시 DB 데이터 로드
  useEffect(() => {
    if (activeTab !== 'local' && dbHistory.length === 0) {
      loadDbHistory()
    }
  }, [activeTab])

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

      {/* 0. 캐시 관리 */}
      <div className="bg-white rounded-lg shadow p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <HardDrive className="w-5 h-5 text-gray-600" />
            <div>
              <span className="font-medium">가격 데이터 캐시</span>
              <span className="text-sm text-gray-500 ml-2">
                {cacheStatus.file_count}개 ETF
                {cacheStatus.last_date && ` • 최신: ${cacheStatus.last_date}`}
              </span>
            </div>
          </div>
          
          <div className="flex items-center gap-4">
            {cacheStatus.is_running ? (
              <div className="flex items-center gap-3">
                <div className="w-32 bg-gray-200 rounded-full h-2">
                  <div 
                    className="bg-blue-500 h-2 rounded-full transition-all"
                    style={{ width: `${cacheStatus.total > 0 ? (cacheStatus.progress / cacheStatus.total) * 100 : 0}%` }}
                  />
                </div>
                <span className="text-sm text-gray-600">
                  {cacheStatus.progress}/{cacheStatus.total}
                </span>
                <span className="text-xs text-green-600">+{cacheStatus.updated}</span>
                <span className="text-xs text-gray-400">스킵 {cacheStatus.skipped}</span>
                {cacheStatus.failed > 0 && (
                  <span className="text-xs text-red-500">실패 {cacheStatus.failed}</span>
                )}
              </div>
            ) : (
              <div className="flex items-center gap-2">
                {cacheStatus.updated > 0 && (
                  <span className="text-sm text-green-600">✓ {cacheStatus.updated}개 업데이트</span>
                )}
                {cacheStatus.skipped > 0 && (
                  <span className="text-sm text-gray-500">• {cacheStatus.skipped}개 스킵</span>
                )}
                {cacheStatus.failed > 0 && (
                  <span className="text-sm text-red-500" title={cacheStatus.errors?.join('\n')}>
                    • {cacheStatus.failed}개 실패
                  </span>
                )}
                {!cacheStatus.updated && !cacheStatus.skipped && !cacheStatus.failed && cacheStatus.message && (
                  <span className="text-sm text-gray-500">{cacheStatus.message}</span>
                )}
              </div>
            )}
            
            <button
              onClick={startCacheUpdate}
              disabled={cacheStatus.is_running}
              className={`flex items-center gap-2 px-4 py-2 rounded text-sm ${
                cacheStatus.is_running
                  ? 'bg-gray-300 cursor-not-allowed'
                  : 'bg-blue-500 hover:bg-blue-600 text-white'
              }`}
            >
              <Download className="w-4 h-4" />
              {cacheStatus.is_running ? '업데이트 중...' : '캐시 업데이트'}
            </button>
          </div>
        </div>
        
        {/* 오류 상세 표시 */}
        {cacheStatus.errors && cacheStatus.errors.length > 0 && !cacheStatus.is_running && (
          <div className="mt-2 p-2 bg-red-50 rounded text-xs text-red-600">
            <strong>오류 상세:</strong>
            <ul className="mt-1 list-disc list-inside">
              {cacheStatus.errors.map((err, i) => (
                <li key={i}>{err}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
      
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
                  <th className="px-3 py-2 text-left">룩백</th>
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
                    <td className="px-3 py-2">{trial.lookback_months ? `${trial.lookback_months}개월` : '-'}</td>
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
        
        {/* 룩백 기간별 결과 */}
        {tuningStatus.lookback_results && Object.keys(tuningStatus.lookback_results).length > 0 && (
          <div className="mt-4 p-4 bg-blue-50 rounded">
            <h4 className="font-bold mb-2">📊 룩백 기간별 최적 결과</h4>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {Object.entries(tuningStatus.lookback_results).map(([months, result]) => (
                <div key={months} className="bg-white p-3 rounded shadow-sm">
                  <div className="text-sm text-gray-600 mb-1">{months}개월 룩백</div>
                  <div className="text-lg font-bold text-blue-600">
                    Sharpe: {result.best_value.toFixed(2)}
                  </div>
                  <div className="text-xs text-gray-500 mt-1">
                    MA: {result.best_params.ma_period}, RSI: {result.best_params.rsi_period}
                  </div>
                </div>
              ))}
            </div>
            <div className="mt-3 text-sm text-gray-600">
              💡 앙상블: 최근 기간(3개월)에 50%, 6개월에 30%, 12개월에 20% 가중치 적용
            </div>
          </div>
        )}
      </div>
      
      {/* 3. 히스토리 */}
      <div className="bg-white rounded-lg shadow p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-xl font-bold flex items-center gap-2">
            <Database className="w-5 h-5" />
            백테스트 히스토리
          </h3>
          <button
            onClick={loadDbHistory}
            disabled={dbLoading}
            className="flex items-center gap-1 px-3 py-1 text-sm bg-gray-100 rounded hover:bg-gray-200"
          >
            <RefreshCw className={`w-4 h-4 ${dbLoading ? 'animate-spin' : ''}`} />
            새로고침
          </button>
        </div>
        
        {/* 탭 */}
        <div className="flex gap-2 mb-4 border-b">
          <button
            onClick={() => setActiveTab('local')}
            className={`px-4 py-2 -mb-px ${activeTab === 'local' ? 'border-b-2 border-blue-500 text-blue-600 font-bold' : 'text-gray-500'}`}
          >
            <Clock className="w-4 h-4 inline mr-1" />
            현재 세션
          </button>
          <button
            onClick={() => setActiveTab('db')}
            className={`px-4 py-2 -mb-px ${activeTab === 'db' ? 'border-b-2 border-blue-500 text-blue-600 font-bold' : 'text-gray-500'}`}
          >
            <Database className="w-4 h-4 inline mr-1" />
            DB 히스토리
          </button>
          <button
            onClick={() => setActiveTab('sessions')}
            className={`px-4 py-2 -mb-px ${activeTab === 'sessions' ? 'border-b-2 border-blue-500 text-blue-600 font-bold' : 'text-gray-500'}`}
          >
            <Target className="w-4 h-4 inline mr-1" />
            튜닝 세션
          </button>
          <button
            onClick={() => setActiveTab('stats')}
            className={`px-4 py-2 -mb-px ${activeTab === 'stats' ? 'border-b-2 border-blue-500 text-blue-600 font-bold' : 'text-gray-500'}`}
          >
            <BarChart3 className="w-4 h-4 inline mr-1" />
            통계
          </button>
        </div>
        
        {/* 현재 세션 (localStorage) */}
        {activeTab === 'local' && (
          history.length === 0 ? (
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
          )
        )}
        
        {/* DB 히스토리 */}
        {activeTab === 'db' && (
          dbLoading ? (
            <div className="text-center py-8 text-gray-500">
              <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2" />
              로딩 중...
            </div>
          ) : dbHistory.length === 0 ? (
            <p className="text-gray-500">DB에 저장된 백테스트 기록이 없습니다.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-gray-100">
                  <tr>
                    <th className="px-3 py-2 text-left">ID</th>
                    <th className="px-3 py-2 text-left">유형</th>
                    <th className="px-3 py-2 text-left">기간</th>
                    <th className="px-3 py-2 text-left">MA</th>
                    <th className="px-3 py-2 text-left">RSI</th>
                    <th className="px-3 py-2 text-left">손절</th>
                    <th className="px-3 py-2 text-left">Sharpe</th>
                    <th className="px-3 py-2 text-left">CAGR</th>
                    <th className="px-3 py-2 text-left">MDD</th>
                    <th className="px-3 py-2 text-left">저장일</th>
                  </tr>
                </thead>
                <tbody>
                  {dbHistory.map((item, idx) => (
                    <tr key={idx} className="hover:bg-gray-50">
                      <td className="px-3 py-2 text-gray-500">{item.id}</td>
                      <td className="px-3 py-2">
                        <span className={`px-2 py-0.5 rounded text-xs ${item.run_type === 'tuning' ? 'bg-purple-100 text-purple-700' : 'bg-blue-100 text-blue-700'}`}>
                          {item.run_type === 'tuning' ? '튜닝' : '단일'}
                        </span>
                      </td>
                      <td className="px-3 py-2">{item.start_date} ~ {item.end_date}</td>
                      <td className="px-3 py-2">{item.ma_period}</td>
                      <td className="px-3 py-2">{item.rsi_period}</td>
                      <td className="px-3 py-2">{item.stop_loss}%</td>
                      <td className="px-3 py-2 font-bold">{item.sharpe_ratio?.toFixed(2) || '-'}</td>
                      <td className={`px-3 py-2 ${item.cagr >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                        {item.cagr?.toFixed(2) || '-'}%
                      </td>
                      <td className="px-3 py-2 text-red-600">{item.max_drawdown?.toFixed(2) || '-'}%</td>
                      <td className="px-3 py-2 text-gray-500 text-xs">
                        {new Date(item.created_at).toLocaleString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        )}
        
        {/* 튜닝 세션 */}
        {activeTab === 'sessions' && (
          dbLoading ? (
            <div className="text-center py-8 text-gray-500">
              <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2" />
              로딩 중...
            </div>
          ) : tuningSessions.length === 0 ? (
            <p className="text-gray-500">튜닝 세션 기록이 없습니다.</p>
          ) : (
            <div className="space-y-4">
              {tuningSessions.map((session, idx) => (
                <div key={idx} className="border rounded-lg p-4">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-sm bg-gray-100 px-2 py-1 rounded">{session.id}</span>
                      <span className={`px-2 py-0.5 rounded text-xs ${
                        session.status === 'completed' ? 'bg-green-100 text-green-700' :
                        session.status === 'running' ? 'bg-yellow-100 text-yellow-700' :
                        'bg-red-100 text-red-700'
                      }`}>
                        {session.status === 'completed' ? '완료' : session.status === 'running' ? '진행중' : '실패'}
                      </span>
                    </div>
                    <span className="text-sm text-gray-500">
                      {new Date(session.created_at).toLocaleString()}
                    </span>
                  </div>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                    <div>
                      <span className="text-gray-500">Trials:</span>
                      <span className="ml-2 font-bold">{session.completed_trials}/{session.total_trials}</span>
                    </div>
                    <div>
                      <span className="text-gray-500">Best Sharpe:</span>
                      <span className="ml-2 font-bold text-blue-600">{session.best_sharpe?.toFixed(2) || '-'}</span>
                    </div>
                    <div>
                      <span className="text-gray-500">룩백:</span>
                      <span className="ml-2">{session.lookback_months?.join(', ')}개월</span>
                    </div>
                    <div>
                      <span className="text-gray-500">지표:</span>
                      <span className="ml-2">{session.optimization_metric}</span>
                    </div>
                  </div>
                  {session.ensemble_params && Object.keys(session.ensemble_params).length > 0 && (
                    <div className="mt-3 p-2 bg-blue-50 rounded text-sm">
                      <span className="font-bold">앙상블 파라미터:</span>
                      <span className="ml-2">
                        MA: {session.ensemble_params.ma_period}, 
                        RSI: {session.ensemble_params.rsi_period}, 
                        손절: {session.ensemble_params.stop_loss}%
                      </span>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )
        )}
        
        {/* 통계 */}
        {activeTab === 'stats' && (
          dbLoading ? (
            <div className="text-center py-8 text-gray-500">
              <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2" />
              로딩 중...
            </div>
          ) : !statistics ? (
            <p className="text-gray-500">통계 데이터를 불러올 수 없습니다.</p>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* 백테스트 통계 */}
              <div className="border rounded-lg p-4">
                <h4 className="font-bold mb-3 flex items-center gap-2">
                  <TrendingUp className="w-4 h-4" />
                  백테스트 통계
                </h4>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-gray-500">총 백테스트 수</span>
                    <span className="font-bold">{statistics.backtest?.total || 0}회</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">평균 Sharpe</span>
                    <span className="font-bold">{statistics.backtest?.avg_sharpe?.toFixed(2) || '-'}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">최고 Sharpe</span>
                    <span className="font-bold text-blue-600">{statistics.backtest?.max_sharpe?.toFixed(2) || '-'}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">평균 CAGR</span>
                    <span className="font-bold">{statistics.backtest?.avg_cagr?.toFixed(2) || '-'}%</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">최고 CAGR</span>
                    <span className="font-bold text-green-600">{statistics.backtest?.max_cagr?.toFixed(2) || '-'}%</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">평균 MDD</span>
                    <span className="font-bold text-red-600">{statistics.backtest?.avg_mdd?.toFixed(2) || '-'}%</span>
                  </div>
                </div>
              </div>
              
              {/* 튜닝 통계 */}
              <div className="border rounded-lg p-4">
                <h4 className="font-bold mb-3 flex items-center gap-2">
                  <Target className="w-4 h-4" />
                  튜닝 통계
                </h4>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-gray-500">총 세션 수</span>
                    <span className="font-bold">{statistics.tuning?.total_sessions || 0}회</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">총 Trial 수</span>
                    <span className="font-bold">{statistics.tuning?.total_trials || 0}회</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">최고 Sharpe</span>
                    <span className="font-bold text-blue-600">{statistics.tuning?.best_sharpe?.toFixed(2) || '-'}</span>
                  </div>
                </div>
              </div>
            </div>
          )
        )}
      </div>
    </div>
  )
}
