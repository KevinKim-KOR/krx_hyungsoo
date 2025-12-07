import { useState, useEffect } from 'react'
import { AlertCircle, TrendingUp, TrendingDown, Wallet, Target, AlertTriangle, RefreshCw } from 'lucide-react'
import { API_URLS } from '../config/api'

interface Holding {
  id: number
  code: string
  name: string
  quantity: number
  avg_price: number
  current_price: number
}

interface Recommendation {
  code: string
  name: string
  signal: string
  reason: string
  current_weight: number
  target_weight: number
  return_pct: number
}

interface DailyRecommendation {
  date: string
  regime: string
  regime_confidence: number
  total_value: number
  total_cost: number
  total_return_pct: number
  recommendations: Recommendation[]
  summary: {
    action_required: number
    stoploss_count: number
    sell_count: number
    buy_count: number
  }
}

export default function Dashboard() {
  const [holdings, setHoldings] = useState<Holding[]>([])
  const [recommendation, setRecommendation] = useState<DailyRecommendation | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchData = async () => {
    try {
      setLoading(true)
      
      // 보유종목 조회 (Cloud API)
      const holdingsRes = await fetch(`${API_URLS.holdings}/api/v1/holdings`)
      if (holdingsRes.ok) {
        const data = await holdingsRes.json()
        setHoldings(data)
      }
      
      // 오늘의 추천 조회 (Local API)
      try {
        const recRes = await fetch(`${API_URLS.dashboard}/api/v1/recommendations/today`)
        if (recRes.ok) {
          const data = await recRes.json()
          setRecommendation(data)
        }
      } catch {
        // 추천 데이터 없어도 OK
      }
      
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : '데이터 로딩 실패')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
  }, [])

  // 포트폴리오 계산
  const totalCost = holdings.reduce((sum, h) => sum + h.avg_price * h.quantity, 0)
  const totalValue = holdings.reduce((sum, h) => sum + h.current_price * h.quantity, 0)
  const totalProfit = totalValue - totalCost
  const totalProfitRate = totalCost > 0 ? (totalProfit / totalCost) * 100 : 0

  const formatNumber = (num: number) => new Intl.NumberFormat('ko-KR').format(Math.round(num))
  const formatPercent = (num: number) => `${num >= 0 ? '+' : ''}${num.toFixed(2)}%`

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center">
          <RefreshCw className="w-12 h-12 text-blue-600 mx-auto mb-4 animate-spin" />
          <p className="text-gray-600">데이터를 불러오는 중...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center">
          <AlertCircle className="h-12 w-12 text-red-500 mx-auto mb-4" />
          <p className="text-red-600 mb-2">{error}</p>
          <button onClick={fetchData} className="text-blue-600 hover:underline">다시 시도</button>
        </div>
      </div>
    )
  }

  // 액션 필요한 종목
  const actionItems = recommendation?.recommendations.filter(r => r.signal !== 'HOLD') || []
  const stopLossItems = actionItems.filter(r => r.signal === 'STOPLOSS')
  const sellItems = actionItems.filter(r => r.signal === 'SELL')
  const buyItems = actionItems.filter(r => r.signal === 'BUY')

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-3xl font-bold">대시보드</h2>
        <button onClick={fetchData} className="text-gray-500 hover:text-gray-700">
          <RefreshCw className="w-5 h-5" />
        </button>
      </div>
      
      {/* 포트폴리오 요약 */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <div className="bg-white rounded-lg shadow p-6">
          <div className="text-sm text-gray-600 mb-1">총 매입액</div>
          <div className="text-2xl font-bold">₩{formatNumber(totalCost)}</div>
        </div>
        
        <div className="bg-white rounded-lg shadow p-6">
          <div className="text-sm text-gray-600 mb-1">총 평가액</div>
          <div className="text-2xl font-bold">₩{formatNumber(totalValue)}</div>
        </div>
        
        <div className="bg-white rounded-lg shadow p-6">
          <div className="text-sm text-gray-600 mb-1">평가손익</div>
          <div className={`text-2xl font-bold flex items-center gap-1 ${totalProfit >= 0 ? 'text-green-600' : 'text-red-600'}`}>
            {totalProfit >= 0 ? <TrendingUp className="w-5 h-5" /> : <TrendingDown className="w-5 h-5" />}
            {formatPercent(totalProfitRate)}
          </div>
        </div>
        
        <div className="bg-white rounded-lg shadow p-6">
          <div className="text-sm text-gray-600 mb-1">보유 종목</div>
          <div className="text-2xl font-bold flex items-center gap-1">
            <Wallet className="w-5 h-5 text-gray-400" />
            {holdings.length}개
          </div>
        </div>
        
        <div className="bg-white rounded-lg shadow p-6">
          <div className="text-sm text-gray-600 mb-1">시장 레짐</div>
          <div className="text-2xl font-bold flex items-center gap-1">
            {recommendation?.regime === 'bull' && <span className="text-green-600">🟢 상승장</span>}
            {recommendation?.regime === 'bear' && <span className="text-red-600">🔴 하락장</span>}
            {recommendation?.regime === 'neutral' && <span className="text-yellow-600">🟡 횡보장</span>}
            {!recommendation?.regime && <span className="text-gray-400">-</span>}
          </div>
        </div>
      </div>

      {/* 오늘의 추천 */}
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-xl font-bold mb-4 flex items-center gap-2">
          <Target className="w-5 h-5" />
          오늘의 추천
          {recommendation && (
            <span className="text-sm font-normal text-gray-500">({recommendation.date})</span>
          )}
        </h3>
        
        {actionItems.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            <p>✅ 오늘은 특별한 액션이 필요하지 않습니다.</p>
          </div>
        ) : (
          <div className="space-y-4">
            {/* 손절 필요 */}
            {stopLossItems.length > 0 && (
              <div className="bg-red-50 rounded-lg p-4">
                <h4 className="font-bold text-red-700 flex items-center gap-2 mb-2">
                  <AlertTriangle className="w-4 h-4" />
                  손절 필요 ({stopLossItems.length}건)
                </h4>
                <div className="space-y-2">
                  {stopLossItems.map((item, idx) => (
                    <div key={idx} className="flex justify-between items-center text-sm">
                      <span className="font-medium">{item.name}</span>
                      <span className="text-red-600">{formatPercent(item.return_pct)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            
            {/* 매도 검토 */}
            {sellItems.length > 0 && (
              <div className="bg-orange-50 rounded-lg p-4">
                <h4 className="font-bold text-orange-700 mb-2">📤 매도 검토 ({sellItems.length}건)</h4>
                <div className="space-y-2">
                  {sellItems.map((item, idx) => (
                    <div key={idx} className="flex justify-between items-center text-sm">
                      <span className="font-medium">{item.name}</span>
                      <span className="text-gray-600">{item.reason}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            
            {/* 매수 검토 */}
            {buyItems.length > 0 && (
              <div className="bg-green-50 rounded-lg p-4">
                <h4 className="font-bold text-green-700 mb-2">📥 매수 검토 ({buyItems.length}건)</h4>
                <div className="space-y-2">
                  {buyItems.map((item, idx) => (
                    <div key={idx} className="flex justify-between items-center text-sm">
                      <span className="font-medium">{item.name}</span>
                      <span className="text-gray-600">목표 {item.target_weight}%</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* 수익률 Top 5 / Bottom 5 */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Top 5 */}
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-bold mb-4 text-green-600">🔴 수익 Top 5</h3>
          <div className="space-y-3">
            {[...holdings]
              .sort((a, b) => {
                const rateA = ((a.current_price - a.avg_price) / a.avg_price) * 100
                const rateB = ((b.current_price - b.avg_price) / b.avg_price) * 100
                return rateB - rateA
              })
              .slice(0, 5)
              .map((h, idx) => {
                const rate = ((h.current_price - h.avg_price) / h.avg_price) * 100
                return (
                  <div key={idx} className="flex justify-between items-center">
                    <span className="text-sm">{h.name}</span>
                    <span className={`font-bold ${rate >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                      {formatPercent(rate)}
                    </span>
                  </div>
                )
              })}
          </div>
        </div>
        
        {/* Bottom 5 */}
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-bold mb-4 text-red-600">🔵 손실 Top 5</h3>
          <div className="space-y-3">
            {[...holdings]
              .sort((a, b) => {
                const rateA = ((a.current_price - a.avg_price) / a.avg_price) * 100
                const rateB = ((b.current_price - b.avg_price) / b.avg_price) * 100
                return rateA - rateB
              })
              .slice(0, 5)
              .map((h, idx) => {
                const rate = ((h.current_price - h.avg_price) / h.avg_price) * 100
                return (
                  <div key={idx} className="flex justify-between items-center">
                    <span className="text-sm">{h.name}</span>
                    <span className={`font-bold ${rate >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                      {formatPercent(rate)}
                    </span>
                  </div>
                )
              })}
          </div>
        </div>
      </div>
    </div>
  )
}
