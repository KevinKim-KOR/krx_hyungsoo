import { useState, useEffect } from 'react'
import { Play, Square, RefreshCw, Target, Clock, Database, BarChart3, HardDrive, Download, Bot, TrendingUp, Settings, ToggleLeft, ToggleRight, Rocket, CheckCircle } from 'lucide-react'
import { API_URLS } from '../config/api'
import { apiClient } from '../api/client'
import { AIPromptModal } from '../components/AIPromptModal'

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
  volatility?: number
  calmar_ratio?: number
  // 엔진 정합성 검증용
  sell_trades?: number
  total_costs?: number
  total_realized_pnl?: number
}

interface SplitMetrics {
  cagr: number
  sharpe_ratio: number
  max_drawdown: number
  num_trades: number
}

interface EngineHealth {
  is_valid: boolean
  warnings: string[]
}

interface TuningTrial {
  trial_number: number
  lookback_months?: number
  params: BacktestParams
  result: BacktestResult
  // Train/Val/Test 분할 성과
  train?: SplitMetrics
  val?: SplitMetrics
  test?: SplitMetrics
  // 엔진 헬스체크
  engine_health?: EngineHealth
  warnings?: string[]
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

interface TuningVariable {
  enabled: boolean
  range: [number, number]
  default: number
  step: number
  description: string
  category: string
}

interface TuningVariablesResponse {
  all_variables: Record<string, TuningVariable>
  enabled_variables: string[]
  enabled_count: number
  total_count: number
}

export default function Strategy() {
  // 튜닝용 기본 파라미터
  const [backtestParams] = useState<BacktestParams>({
    start_date: '2024-01-01',
    end_date: new Date().toISOString().split('T')[0],
    ma_period: 60,
    rsi_period: 14,
    stop_loss: -8,
    initial_capital: 10000000,
  })

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

  // AI 분석 모달 상태 (기존 프롬프트 생성용)
  const [aiModalOpen, setAiModalOpen] = useState(false)
  const [aiPrompt, setAiPrompt] = useState('')
  

  // DB 히스토리 상태
  const [dbHistory, setDbHistory] = useState<any[]>([])
  const [tuningSessions, setTuningSessions] = useState<any[]>([])
  const [statistics, setStatistics] = useState<any>(null)
  const [dbLoading, setDbLoading] = useState(false)
  const [activeTab, setActiveTab] = useState<'local' | 'db' | 'sessions' | 'stats'>('local')

  // 튜닝 변수 상태
  const [tuningVariables, setTuningVariables] = useState<Record<string, TuningVariable>>({})
  const [variablesExpanded, setVariablesExpanded] = useState(false)
  const [variableUpdating, setVariableUpdating] = useState<string | null>(null)

  // 튜닝 변수 로드
  const loadTuningVariables = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/tuning-variables`)
      if (res.ok) {
        const data: TuningVariablesResponse = await res.json()
        setTuningVariables(data.all_variables)
      }
    } catch (err) {
      console.error('튜닝 변수 로드 실패:', err)
    }
  }

  // 튜닝 변수 토글
  const toggleVariable = async (name: string, enabled: boolean) => {
    setVariableUpdating(name)
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/tuning-variables/${name}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled }),
      })
      if (res.ok) {
        setTuningVariables(prev => ({
          ...prev,
          [name]: { ...prev[name], enabled }
        }))
      }
    } catch (err) {
      console.error('변수 업데이트 실패:', err)
    } finally {
      setVariableUpdating(null)
    }
  }

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
    
    // 튜닝 변수 로드
    loadTuningVariables()
    
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

  // 튜닝 시작
  const startTuning = async () => {
    // 프론트엔드 검증
    if (tuningTrials < 10 || tuningTrials > 1000) {
      alert('Trials는 10~1000 범위여야 합니다.')
      return
    }
    
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
      
      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}))
        const detail = errorData.detail || '튜닝 시작 실패'
        throw new Error(detail)
      }
      
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

  // AI 분석 프롬프트 템플릿 생성 (공통)
  const buildPromptFromPayload = (payload: object) => {
    return `당신은 한국 ETF 모멘텀/레짐 전략을 다루는 퀀트 전문가입니다.

아래 JSON은 모멘텀 ETF 전략 튜닝 결과 중
"선택된 1개 Trial"의 정보입니다.

이 데이터를 분석해서, 아래 7개 섹션으로 된 한국어 리포트를 작성해 주세요.
각 섹션은 Markdown 제목(## 1. …)으로 구분해 주세요.

1) 최적 파라미터 요약
   - 룩백, MA, RSI, 손절 비율
   - Train/Val/Test Sharpe, CAGR, MDD 간단 요약

2) 성과 안정성 평가
   - Train → Val → Test Sharpe 흐름 분석
   - 어느 구간에서 성과가 튀는지, 일관성이 있는지 평가
   - Validation 구간 Sharpe/CAGR가 비정상적으로 크거나 작으면,
     기간이 짧아서 생긴 이상치인지도 함께 언급

3) 과적합 여부 판단
   - 단순히 '과적합/아님'이 아니라,
     어떤 지표 패턴 때문에 그렇게 판단하는지 근거 설명

4) 전략적 해석
   - MA/RSI/손절 조합이 어떤 시장 상황에서 잘 맞는지
   - 이 파라미터가 만들어내는 전략 성격(공격/방어, 단기/중기) 설명

5) 리스크 요인 분석
   - Validation 구간 부진, 특정 구간 민감도, 파라미터 민감도 등
   - 어떤 시장 환경에서 이 세팅이 깨질 수 있는지

6) 개선 제안
   - MA/RSI/손절/룩백을 어떻게 조정해볼 수 있을지 방향 제시
   - 추가로 검증해야 할 실험(예: Walk-Forward, 다른 룩백, TP/SL 조합 등)

7) 최종 결론
   - 이 Trial을 실거래 / 모의거래 / 추가검증 중 어디에 쓸지 권고
   - 한 줄 요약으로 정리

아래는 분석할 JSON 데이터입니다. 그대로 참고해서 위 7개 섹션을 채워 주세요.

\`\`\`json
${JSON.stringify(payload, null, 2)}
\`\`\``
  }

  // AI 분석 프롬프트 생성 (튜닝 Trial용)
  const generateAnalysisPrompt = (trial: TuningTrial) => {
    const payload = {
      lookback: trial.lookback_months ? `${trial.lookback_months}M` : '3M',
      trial_id: trial.trial_number,
      strategy: 'Momentum ETF',
      params: {
        ma_period: trial.params.ma_period,
        rsi_period: trial.params.rsi_period,
        stop_loss: trial.params.stop_loss,
      },
      metrics: {
        train: trial.train ? {
          sharpe: trial.train.sharpe_ratio,
          cagr: trial.train.cagr,
          mdd: -trial.train.max_drawdown,
        } : { sharpe: 0, cagr: 0, mdd: 0 },
        val: trial.val ? {
          sharpe: trial.val.sharpe_ratio,
          cagr: trial.val.cagr,
          mdd: -trial.val.max_drawdown,
        } : { sharpe: 0, cagr: 0, mdd: 0 },
        test: trial.test ? {
          sharpe: trial.test.sharpe_ratio,
          cagr: trial.test.cagr,
          mdd: -trial.test.max_drawdown,
        } : {
          sharpe: trial.result.sharpe_ratio,
          cagr: trial.result.cagr,
          mdd: -trial.result.max_drawdown,
        },
      },
      engine_health: trial.engine_health ?? { is_valid: true, warnings: [] },
    }
    return buildPromptFromPayload(payload)
  }

  // AI 분석 프롬프트 모달 열기
  const requestAiAnalysis = (trialIdx: number) => {
    const trial = tuningStatus.trials[trialIdx]
    if (!trial) return
    
    // 엔진 정합성 검증
    const volatilityZero = trial.result.volatility === 0
    const sellTradesZero = trial.result.num_trades > 0 && (trial.result.sell_trades ?? 0) === 0
    const costsZero = trial.result.num_trades > 0 && (trial.result.total_costs ?? 0) === 0
    const engineHealthInvalid = trial.engine_health && !trial.engine_health.is_valid
    const isInvalid = engineHealthInvalid || volatilityZero || sellTradesZero || costsZero
    
    if (isInvalid) {
      alert('엔진 비정상 Trial은 분석할 수 없습니다.')
      return
    }
    
    const prompt = generateAnalysisPrompt(trial)
    setAiPrompt(prompt)
    setAiModalOpen(true)
  }

  // DB 히스토리 항목에서 AI 분석 프롬프트 생성
  const requestAiAnalysisFromHistory = (item: any) => {
    // 페이로드 구성 (DB 히스토리 항목 기반)
    const payload = {
      lookback: '3M',  // DB에서 룩백 정보가 없으면 기본값
      trial_id: item.id,
      strategy: 'Momentum ETF',
      params: {
        ma_period: item.ma_period,
        rsi_period: item.rsi_period,
        stop_loss: item.stop_loss,
      },
      metrics: {
        train: item.train_metrics ? (typeof item.train_metrics === 'string' ? JSON.parse(item.train_metrics) : item.train_metrics) : { sharpe: 0, cagr: 0, mdd: 0 },
        val: item.val_metrics ? (typeof item.val_metrics === 'string' ? JSON.parse(item.val_metrics) : item.val_metrics) : { sharpe: 0, cagr: 0, mdd: 0 },
        test: item.test_metrics ? (typeof item.test_metrics === 'string' ? JSON.parse(item.test_metrics) : item.test_metrics) : {
          sharpe: item.sharpe_ratio ?? 0,
          cagr: item.cagr ?? 0,
          mdd: -(item.max_drawdown ?? 0),
        },
      },
      engine_health: item.engine_health 
        ? (typeof item.engine_health === 'string' ? JSON.parse(item.engine_health) : item.engine_health)
        : { is_valid: true, warnings: [] },
    }
    
    setAiPrompt(buildPromptFromPayload(payload))
    setAiModalOpen(true)
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

  // 최적 파라미터 저장
  const [saving, setSaving] = useState(false)
  const [promoting, setPromoting] = useState(false)
  const [promoteSuccess, setPromoteSuccess] = useState(false)
  
  const saveOptimalParams = async () => {
    if (!tuningStatus.best_params || tuningStatus.trials.length === 0) return
    
    setSaving(true)
    try {
      const bestTrial = tuningStatus.trials[0]
      const res = await fetch(`${API_BASE_URL}/api/v1/optimal-params/save`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          params: tuningStatus.best_params,
          result: bestTrial.result,
          source: 'tuning',
          notes: `Sharpe: ${bestTrial.result.sharpe_ratio.toFixed(2)}, CAGR: ${bestTrial.result.cagr.toFixed(2)}%`
        }),
      })
      
      if (res.ok) {
        alert('✅ 최적 파라미터가 저장되었습니다!')
      } else {
        throw new Error('저장 실패')
      }
    } catch (err) {
      alert('❌ 저장 실패: ' + (err instanceof Error ? err.message : '알 수 없는 오류'))
    } finally {
      setSaving(false)
    }
  }

  // 실전 파라미터로 승격 (Live)
  const promoteToLive = async () => {
    if (!tuningStatus.best_params || tuningStatus.trials.length === 0) return
    
    // 확인 모달
    const confirmed = window.confirm(
      '이 파라미터를 실전 운영용으로 적용하시겠습니까?\n\n' +
      '• 기존 Live 파라미터는 히스토리로 이동됩니다.\n' +
      '• 일일 추천 알림에 이 파라미터가 사용됩니다.'
    )
    if (!confirmed) return
    
    setPromoting(true)
    setPromoteSuccess(false)
    try {
      const bestTrial = tuningStatus.trials[0]
      const lookback = bestTrial.lookback_months ? `${bestTrial.lookback_months}M` : '3M'
      
      const res = await fetch(`${API_BASE_URL}/api/v1/optimal-params/promote-to-live`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          params: tuningStatus.best_params,
          result: bestTrial.result,
          trial_id: bestTrial.trial_number,
          lookback: lookback,
          notes: `Sharpe: ${bestTrial.result.sharpe_ratio.toFixed(2)}, CAGR: ${bestTrial.result.cagr.toFixed(2)}% - UI에서 승격`
        }),
      })
      
      if (res.ok) {
        setPromoteSuccess(true)
        alert('✅ Live 파라미터로 승격되었습니다!\n\n이제 일일 추천 알림에 이 파라미터가 사용됩니다.')
        // 3초 후 성공 상태 초기화
        setTimeout(() => setPromoteSuccess(false), 3000)
      } else {
        const errorData = await res.json().catch(() => ({}))
        throw new Error(errorData.detail || 'Live 승격 실패')
      }
    } catch (err) {
      alert('❌ Live 승격 실패: ' + (err instanceof Error ? err.message : '알 수 없는 오류'))
    } finally {
      setPromoting(false)
    }
  }

  // 백엔드에서 이미 % 단위로 반환하므로 100 곱하지 않음
  const formatPercent = (value: number) => `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`
  // MDD는 양수로 반환되므로 음수로 표시
  const formatMDD = (value: number) => `-${Math.abs(value).toFixed(2)}%`

  // Live 파라미터 수동 설정 상태
  const [liveParams, setLiveParams] = useState({
    lookback: '3M',
    ma_period: 60,
    rsi_period: 14,
    stop_loss: -10,
    max_positions: 10,
    notes: ''
  })
  const [liveParamsExpanded, setLiveParamsExpanded] = useState(false)
  const [settingLive, setSettingLive] = useState(false)
  const [currentLive, setCurrentLive] = useState<any>(null)

  // 현재 Live 파라미터 로드
  useEffect(() => {
    const fetchLive = async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/api/v1/optimal-params/live`)
        if (res.ok) {
          const data = await res.json()
          setCurrentLive(data.live)
          if (data.live?.params) {
            setLiveParams({
              lookback: data.live.params.lookback || '3M',
              ma_period: data.live.params.ma_period || 60,
              rsi_period: data.live.params.rsi_period || 14,
              stop_loss: data.live.params.stop_loss || -10,
              max_positions: data.live.params.max_positions || 10,
              notes: ''
            })
          }
        }
      } catch (err) {
        console.error('Live 파라미터 로드 실패:', err)
      }
    }
    fetchLive()
  }, [])

  // Live 파라미터 수동 설정
  const setLiveManually = async () => {
    const confirmed = window.confirm(
      'Live 파라미터를 수동으로 설정하시겠습니까?\n\n' +
      '• 기존 Live 파라미터는 히스토리로 이동됩니다.\n' +
      '• 일일 추천 알림에 이 파라미터가 사용됩니다.'
    )
    if (!confirmed) return

    setSettingLive(true)
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/optimal-params/set-live`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(liveParams)
      })

      if (res.ok) {
        const data = await res.json()
        setCurrentLive(data.live)
        alert('✅ Live 파라미터가 설정되었습니다!')
      } else {
        const errorData = await res.json().catch(() => ({}))
        throw new Error(errorData.detail || '설정 실패')
      }
    } catch (err) {
      alert('❌ 설정 실패: ' + (err instanceof Error ? err.message : '알 수 없는 오류'))
    } finally {
      setSettingLive(false)
    }
  }

  return (
    <div className="space-y-6">
      <h2 className="text-3xl font-bold">전략 튜닝</h2>

      {/* 0. Live 파라미터 설정 */}
      <div className="bg-white rounded-lg shadow p-4">
        <div 
          className="flex items-center justify-between cursor-pointer"
          onClick={() => setLiveParamsExpanded(!liveParamsExpanded)}
        >
          <div className="flex items-center gap-4">
            <Rocket className="w-5 h-5 text-orange-600" />
            <div>
              <span className="font-medium">Live 파라미터</span>
              {currentLive?.params && (
                <span className="text-sm text-gray-500 ml-2">
                  {currentLive.params.lookback} / MA{currentLive.params.ma_period} / RSI{currentLive.params.rsi_period} / 손절{currentLive.params.stop_loss}%
                </span>
              )}
              {currentLive?.promoted_at && (
                <span className="text-xs text-gray-400 ml-2">
                  ({new Date(currentLive.promoted_at).toLocaleDateString()})
                </span>
              )}
            </div>
          </div>
          <span className="text-lg text-gray-500">{liveParamsExpanded ? '▲' : '▼'}</span>
        </div>

        {liveParamsExpanded && (
          <div className="mt-4 border-t pt-4">
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-4">
              <div>
                <label className="block text-sm text-gray-600 mb-1">Lookback</label>
                <select
                  value={liveParams.lookback}
                  onChange={e => setLiveParams({...liveParams, lookback: e.target.value})}
                  className="w-full border rounded px-3 py-2"
                >
                  <option value="1M">1M</option>
                  <option value="3M">3M</option>
                  <option value="6M">6M</option>
                  <option value="12M">12M</option>
                </select>
              </div>
              <div>
                <label className="block text-sm text-gray-600 mb-1">MA Period</label>
                <input
                  type="number"
                  value={liveParams.ma_period}
                  onChange={e => setLiveParams({...liveParams, ma_period: parseInt(e.target.value)})}
                  className="w-full border rounded px-3 py-2"
                  min={5}
                  max={200}
                />
              </div>
              <div>
                <label className="block text-sm text-gray-600 mb-1">RSI Period</label>
                <input
                  type="number"
                  value={liveParams.rsi_period}
                  onChange={e => setLiveParams({...liveParams, rsi_period: parseInt(e.target.value)})}
                  className="w-full border rounded px-3 py-2"
                  min={5}
                  max={30}
                />
              </div>
              <div>
                <label className="block text-sm text-gray-600 mb-1">손절 (%)</label>
                <input
                  type="number"
                  value={liveParams.stop_loss}
                  onChange={e => setLiveParams({...liveParams, stop_loss: parseFloat(e.target.value)})}
                  className="w-full border rounded px-3 py-2"
                  min={-30}
                  max={0}
                  step={1}
                />
              </div>
              <div>
                <label className="block text-sm text-gray-600 mb-1">최대 포지션</label>
                <input
                  type="number"
                  value={liveParams.max_positions}
                  onChange={e => setLiveParams({...liveParams, max_positions: parseInt(e.target.value)})}
                  className="w-full border rounded px-3 py-2"
                  min={1}
                  max={20}
                />
              </div>
            </div>
            <div className="mb-4">
              <label className="block text-sm text-gray-600 mb-1">메모 (선택)</label>
              <input
                type="text"
                value={liveParams.notes}
                onChange={e => setLiveParams({...liveParams, notes: e.target.value})}
                className="w-full border rounded px-3 py-2"
                placeholder="예: 보수적 설정으로 변경"
              />
            </div>
            <button
              onClick={setLiveManually}
              disabled={settingLive}
              className="bg-orange-600 text-white rounded px-6 py-2 flex items-center gap-2 hover:bg-orange-700 disabled:opacity-50"
            >
              {settingLive ? (
                <RefreshCw className="w-4 h-4 animate-spin" />
              ) : (
                <Rocket className="w-4 h-4" />
              )}
              Live 파라미터 설정
            </button>
          </div>
        )}
      </div>

      {/* 1. 캐시 관리 */}
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
      
      {/* 튜닝 변수 설정 */}
      <div className="bg-white rounded-lg shadow p-6">
        <div 
          className="flex items-center justify-between cursor-pointer"
          onClick={() => setVariablesExpanded(!variablesExpanded)}
        >
          <h3 className="text-xl font-bold flex items-center gap-2">
            <Settings className="w-5 h-5" />
            튜닝 변수 설정
          </h3>
          <div className="flex items-center gap-2 text-sm text-gray-500">
            <span>{Object.values(tuningVariables).filter(v => v.enabled).length}개 활성화</span>
            <span className="text-lg">{variablesExpanded ? '▲' : '▼'}</span>
          </div>
        </div>
        
        {variablesExpanded && (
          <div className="mt-4 space-y-3">
            {Object.entries(tuningVariables).map(([name, config]) => (
              <div 
                key={name}
                className={`flex items-center justify-between p-3 rounded border ${
                  config.enabled ? 'bg-green-50 border-green-200' : 'bg-gray-50 border-gray-200'
                }`}
              >
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{name}</span>
                    <span className={`text-xs px-2 py-0.5 rounded ${
                      config.category === 'trend' ? 'bg-blue-100 text-blue-700' :
                      config.category === 'momentum' ? 'bg-purple-100 text-purple-700' :
                      config.category === 'risk' ? 'bg-red-100 text-red-700' :
                      config.category === 'market' ? 'bg-yellow-100 text-yellow-700' :
                      'bg-gray-100 text-gray-700'
                    }`}>
                      {config.category}
                    </span>
                  </div>
                  <div className="text-sm text-gray-500 mt-1">
                    {config.description} • 범위: [{config.range[0]}, {config.range[1]}] step={config.step}
                  </div>
                </div>
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    toggleVariable(name, !config.enabled)
                  }}
                  disabled={variableUpdating === name}
                  className="ml-4"
                >
                  {variableUpdating === name ? (
                    <RefreshCw className="w-6 h-6 text-gray-400 animate-spin" />
                  ) : config.enabled ? (
                    <ToggleRight className="w-8 h-8 text-green-600" />
                  ) : (
                    <ToggleLeft className="w-8 h-8 text-gray-400" />
                  )}
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
      
      {/* 자동 튜닝 */}
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
            <>
              <button
                onClick={saveOptimalParams}
                disabled={saving}
                className="bg-purple-600 text-white rounded px-6 py-2 flex items-center gap-2 hover:bg-purple-700 mt-6 disabled:opacity-50"
              >
                {saving ? (
                  <RefreshCw className="w-4 h-4 animate-spin" />
                ) : (
                  <Download className="w-4 h-4" />
                )}
                최적 파라미터 저장
              </button>
              
              {/* 최적 결과 AI 분석 버튼 - 첫 번째 Trial(최적) 분석 */}
              {tuningStatus.trials.length > 0 && (
                <button
                  onClick={() => requestAiAnalysis(0)}
                  className="rounded px-6 py-2 flex items-center gap-2 mt-6 bg-indigo-600 text-white hover:bg-indigo-700"
                >
                  <Bot className="w-4 h-4" />
                  최적 결과 AI 분석
                </button>
              )}
              
              {/* 실전 파라미터로 적용 버튼 */}
              <button
                onClick={promoteToLive}
                disabled={promoting}
                className={`rounded px-6 py-2 flex items-center gap-2 mt-6 disabled:opacity-50 ${
                  promoteSuccess 
                    ? 'bg-green-600 text-white' 
                    : 'bg-orange-600 text-white hover:bg-orange-700'
                }`}
              >
                {promoting ? (
                  <RefreshCw className="w-4 h-4 animate-spin" />
                ) : promoteSuccess ? (
                  <CheckCircle className="w-4 h-4" />
                ) : (
                  <Rocket className="w-4 h-4" />
                )}
                {promoteSuccess ? 'Live 적용 완료!' : '실전 파라미터로 적용'}
              </button>
            </>
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
                  <th className="px-3 py-2 text-left">Train</th>
                  <th className="px-3 py-2 text-left">Val</th>
                  <th className="px-3 py-2 text-left">Test</th>
                  <th className="px-3 py-2 text-left">MDD</th>
                  <th className="px-3 py-2 text-left">상태</th>
                  <th className="px-3 py-2 text-left">분석</th>
                </tr>
              </thead>
              <tbody>
                {tuningStatus.trials.slice(0, 10).map((trial, idx) => {
                  // 과적합 판단: Train Sharpe > Test Sharpe * 1.3
                  const trainSharpe = trial.train?.sharpe_ratio ?? trial.result.sharpe_ratio
                  const testSharpe = trial.test?.sharpe_ratio ?? trial.result.sharpe_ratio
                  const isOverfit = trainSharpe > 0 && testSharpe > 0 && trainSharpe > testSharpe * 1.3
                  const hasWarnings = trial.warnings && trial.warnings.length > 0
                  
                  // 엔진 정합성 검증 (engine_health 또는 result에서 직접 확인)
                  const volatilityZero = trial.result.volatility === 0
                  const sellTradesZero = trial.result.num_trades > 0 && (trial.result.sell_trades ?? 0) === 0
                  const costsZero = trial.result.num_trades > 0 && (trial.result.total_costs ?? 0) === 0
                  const engineHealthInvalid = trial.engine_health && !trial.engine_health.is_valid
                  const isInvalid = engineHealthInvalid || volatilityZero || sellTradesZero || costsZero
                  
                  // 무효 사유 생성
                  const invalidReasons: string[] = []
                  if (volatilityZero) invalidReasons.push('변동성=0')
                  if (sellTradesZero) invalidReasons.push('매도=0')
                  if (costsZero) invalidReasons.push('비용=0')
                  if (trial.engine_health?.warnings) invalidReasons.push(...trial.engine_health.warnings)
                  
                  // 행 색상 결정
                  let rowClass = ''
                  if (idx === 0 && !isInvalid) rowClass = 'bg-green-50'
                  if (isOverfit && !isInvalid) rowClass = 'bg-yellow-50'
                  if (isInvalid) rowClass = 'bg-red-50'
                  
                  return (
                    <tr key={idx} className={rowClass}>
                      <td className="px-3 py-2">{trial.trial_number}</td>
                      <td className="px-3 py-2">{trial.lookback_months ? `${trial.lookback_months}개월` : '-'}</td>
                      <td className="px-3 py-2">{trial.params.ma_period}</td>
                      <td className="px-3 py-2">{trial.params.rsi_period}</td>
                      <td className="px-3 py-2">{trial.params.stop_loss}%</td>
                      <td className="px-3 py-2 text-blue-600">
                        {trial.train?.sharpe_ratio?.toFixed(2) ?? '-'}
                      </td>
                      <td className="px-3 py-2 text-purple-600">
                        {trial.val?.sharpe_ratio?.toFixed(2) ?? '-'}
                      </td>
                      <td className="px-3 py-2 font-bold text-green-600">
                        {trial.test?.sharpe_ratio?.toFixed(2) ?? trial.result.sharpe_ratio.toFixed(2)}
                      </td>
                      <td className="px-3 py-2 text-red-600">{formatMDD(trial.result.max_drawdown)}</td>
                      <td className="px-3 py-2">
                        {isInvalid && (
                          <span className="px-2 py-0.5 bg-red-100 text-red-700 rounded text-xs" title={invalidReasons.join(', ')}>
                            ❌ 무효({invalidReasons.length > 0 ? invalidReasons[0] : '엔진오류'})
                          </span>
                        )}
                        {isOverfit && !isInvalid && (
                          <span className="px-2 py-0.5 bg-yellow-100 text-yellow-700 rounded text-xs" title="Train > Test * 1.3">
                            ⚠️ 과적합
                          </span>
                        )}
                        {!isOverfit && !isInvalid && hasWarnings && (
                          <span className="px-2 py-0.5 bg-orange-100 text-orange-700 rounded text-xs" title={trial.warnings?.join(', ')}>
                            ⚠️ 경고
                          </span>
                        )}
                        {!isOverfit && !isInvalid && !hasWarnings && (
                          <span className="px-2 py-0.5 bg-green-100 text-green-700 rounded text-xs">
                            ✅ 정상
                          </span>
                        )}
                      </td>
                      <td className="px-3 py-2">
                        <button
                          onClick={() => requestAiAnalysis(idx)}
                          disabled={isInvalid}
                          className={`px-2 py-1 text-xs rounded flex items-center gap-1 ${
                            isInvalid 
                              ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                              : 'bg-purple-500 text-white hover:bg-purple-600'
                          }`}
                          title={isInvalid ? '무효 Trial은 분석 불가' : 'AI 분석 프롬프트 생성'}
                        >
                          <Bot className="w-3 h-3" />
                          AI
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
            <div className="mt-2 text-xs text-gray-500">
              * Train/Val/Test: 70/15/15 비율 분할 | 과적합 기준: Train Sharpe &gt; Test Sharpe × 1.3
            </div>
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
                      <td className="px-3 py-2 text-red-600">{formatMDD(item.result.max_drawdown)}</td>
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
                    <th className="px-3 py-2 text-left">분석</th>
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
                      <td className="px-3 py-2 text-red-600">{item.max_drawdown ? formatMDD(item.max_drawdown) : '-'}</td>
                      <td className="px-3 py-2 text-gray-500 text-xs">
                        {new Date(item.created_at).toLocaleString()}
                      </td>
                      <td className="px-3 py-2">
                        <button
                          onClick={() => requestAiAnalysisFromHistory(item)}
                          className="px-2 py-1 text-xs rounded flex items-center gap-1 bg-purple-500 text-white hover:bg-purple-600"
                          title="AI 분석 프롬프트 생성"
                        >
                          <Bot className="w-3 h-3" />
                          AI
                        </button>
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
                    <div className="mt-3 p-2 bg-blue-50 rounded text-sm flex items-center justify-between">
                      <div>
                        <span className="font-bold">앙상블 파라미터:</span>
                        <span className="ml-2">
                          MA: {session.ensemble_params.ma_period}, 
                          RSI: {session.ensemble_params.rsi_period}, 
                          손절: {session.ensemble_params.stop_loss}%
                        </span>
                      </div>
                      <button
                        onClick={() => requestAiAnalysisFromHistory({
                          id: session.id,
                          ma_period: session.ensemble_params.ma_period,
                          rsi_period: session.ensemble_params.rsi_period,
                          stop_loss: session.ensemble_params.stop_loss,
                          sharpe_ratio: session.best_sharpe,
                          cagr: 0,
                          max_drawdown: 0,
                        })}
                        className="px-3 py-1 text-xs rounded flex items-center gap-1 bg-purple-500 text-white hover:bg-purple-600"
                      >
                        <Bot className="w-3 h-3" />
                        AI 분석
                      </button>
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

      {/* AI 분석 모달 */}
      <AIPromptModal
        isOpen={aiModalOpen}
        onClose={() => setAiModalOpen(false)}
        prompt={aiPrompt}
        title="백테스트 결과 AI 분석"
      />
    </div>
  )
}
