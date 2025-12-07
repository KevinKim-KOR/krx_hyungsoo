import { useState, useEffect } from 'react'
import { AlertCircle, RefreshCw, PieChart, TrendingUp } from 'lucide-react'
import { API_URLS } from '../config/api'

interface Holding {
  code: string
  name: string
  quantity: number
  avg_price: number
  current_price: number
}

interface OptimalWeight {
  code: string
  name: string
  target_weight: number
  current_weight: number
  diff: number
}

export default function Portfolio() {
  const [holdings, setHoldings] = useState<Holding[]>([])
  const [optimalWeights, setOptimalWeights] = useState<OptimalWeight[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchData = async () => {
    try {
      setLoading(true)
      
      // 보유종목 조회
      const holdingsRes = await fetch(`${API_URLS.holdings}/api/v1/holdings`)
      if (!holdingsRes.ok) throw new Error('보유종목 조회 실패')
      const holdingsData = await holdingsRes.json()
      setHoldings(holdingsData)
      
      // 총 평가액 계산
      const totalValue = holdingsData.reduce((sum: number, h: Holding) => 
        sum + h.current_price * h.quantity, 0)
      
      // 현재 비중 계산
      const weights: OptimalWeight[] = holdingsData.map((h: Holding) => {
        const value = h.current_price * h.quantity
        const currentWeight = totalValue > 0 ? (value / totalValue) * 100 : 0
        return {
          code: h.code,
          name: h.name,
          target_weight: 0, // TODO: 최적 비중 로드
          current_weight: currentWeight,
          diff: 0
        }
      })
      
      setOptimalWeights(weights.sort((a, b) => b.current_weight - a.current_weight))
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

  const totalValue = holdings.reduce((sum, h) => sum + h.current_price * h.quantity, 0)
  const totalCost = holdings.reduce((sum, h) => sum + h.avg_price * h.quantity, 0)
  const totalReturn = totalCost > 0 ? ((totalValue - totalCost) / totalCost) * 100 : 0

  const formatNumber = (num: number) => new Intl.NumberFormat('ko-KR').format(Math.round(num))
  const formatPercent = (num: number) => `${num >= 0 ? '+' : ''}${num.toFixed(2)}%`

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center">
          <RefreshCw className="w-12 h-12 text-blue-600 mx-auto mb-4 animate-spin" />
          <p className="text-gray-600">포트폴리오 데이터를 불러오는 중...</p>
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

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-3xl font-bold">포트폴리오</h2>
        <button onClick={fetchData} className="text-gray-500 hover:text-gray-700">
          <RefreshCw className="w-5 h-5" />
        </button>
      </div>

      {/* 요약 */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white rounded-lg shadow p-6">
          <div className="text-sm text-gray-600 mb-1">총 평가액</div>
          <div className="text-2xl font-bold">₩{formatNumber(totalValue)}</div>
        </div>
        <div className="bg-white rounded-lg shadow p-6">
          <div className="text-sm text-gray-600 mb-1">총 매입액</div>
          <div className="text-2xl font-bold">₩{formatNumber(totalCost)}</div>
        </div>
        <div className="bg-white rounded-lg shadow p-6">
          <div className="text-sm text-gray-600 mb-1">평가손익</div>
          <div className={`text-2xl font-bold ${totalReturn >= 0 ? 'text-green-600' : 'text-red-600'}`}>
            {formatPercent(totalReturn)}
          </div>
        </div>
        <div className="bg-white rounded-lg shadow p-6">
          <div className="text-sm text-gray-600 mb-1">보유 종목</div>
          <div className="text-2xl font-bold">{holdings.length}개</div>
        </div>
      </div>

      {/* 비중 분포 */}
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-xl font-bold mb-4 flex items-center gap-2">
          <PieChart className="w-5 h-5" />
          종목별 비중
        </h3>
        
        <div className="space-y-3">
          {optimalWeights.slice(0, 15).map((item, idx) => (
            <div key={idx} className="flex items-center gap-4">
              <div className="w-32 truncate text-sm font-medium">{item.name}</div>
              <div className="flex-1">
                <div className="w-full bg-gray-200 rounded-full h-4">
                  <div
                    className="bg-blue-600 h-4 rounded-full"
                    style={{ width: `${Math.min(item.current_weight, 100)}%` }}
                  />
                </div>
              </div>
              <div className="w-16 text-right text-sm font-bold">
                {item.current_weight.toFixed(1)}%
              </div>
            </div>
          ))}
          
          {optimalWeights.length > 15 && (
            <div className="text-sm text-gray-500 text-center">
              외 {optimalWeights.length - 15}개 종목
            </div>
          )}
        </div>
      </div>

      {/* 리밸런싱 제안 */}
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-xl font-bold mb-4 flex items-center gap-2">
          <TrendingUp className="w-5 h-5" />
          리밸런싱 제안
        </h3>
        
        <div className="text-center py-8 text-gray-500">
          <p>전략 튜닝에서 최적화를 실행하면</p>
          <p>리밸런싱 제안이 표시됩니다.</p>
        </div>
      </div>
    </div>
  )
}
