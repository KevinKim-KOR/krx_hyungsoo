import { useEffect, useState } from 'react'
import { Wallet, TrendingUp, TrendingDown, AlertTriangle } from 'lucide-react'

interface Holding {
  id: number
  code: string
  name: string
  quantity: number
  avg_price: number
  current_price: number
}

interface Regime {
  regime: string
  confidence: number
  date: string
  us_market_regime?: string
}

export default function Holdings() {
  const [holdings, setHoldings] = useState<Holding[]>([])
  const [regime, setRegime] = useState<Regime | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchData()
  }, [])

  const fetchData = async () => {
    try {
      setLoading(true)
      
      // Holdings 조회
      const holdingsRes = await fetch('http://localhost:8000/api/v1/holdings')
      if (!holdingsRes.ok) throw new Error('Holdings 조회 실패')
      const holdingsData = await holdingsRes.json()
      setHoldings(holdingsData)
      
      // Regime 조회
      const regimeRes = await fetch('http://localhost:8000/api/v1/regime/current')
      if (!regimeRes.ok) throw new Error('Regime 조회 실패')
      const regimeData = await regimeRes.json()
      setRegime(regimeData)
      
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : '데이터 로딩 실패')
    } finally {
      setLoading(false)
    }
  }

  // 총 평가액, 손익 계산
  const totalValue = holdings.reduce((sum, h) => sum + (h.current_price * h.quantity), 0)
  const totalCost = holdings.reduce((sum, h) => sum + (h.avg_price * h.quantity), 0)
  const totalProfit = totalValue - totalCost
  const totalProfitRate = totalCost > 0 ? (totalProfit / totalCost) * 100 : 0

  // 매도 신호 판단
  const getSellSignal = (holding: Holding) => {
    const profitRate = ((holding.current_price - holding.avg_price) / holding.avg_price) * 100
    
    if (regime?.regime === '하락장') {
      return { show: true, text: '하락장 전환', color: 'bg-red-100 text-red-800' }
    }
    if (regime?.regime === '중립장') {
      return { show: true, text: '중립장 - 일부 매도 권장', color: 'bg-yellow-100 text-yellow-800' }
    }
    if (profitRate < -10) {
      return { show: true, text: `손실 ${profitRate.toFixed(1)}%`, color: 'bg-orange-100 text-orange-800' }
    }
    return { show: false, text: '', color: '' }
  }

  const formatNumber = (num: number) => {
    return new Intl.NumberFormat('ko-KR').format(Math.round(num))
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-lg">로딩 중...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4">
        <p className="text-red-800">❌ {error}</p>
        <button 
          onClick={fetchData}
          className="mt-2 px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700"
        >
          다시 시도
        </button>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold flex items-center gap-2">
          <Wallet className="w-8 h-8" />
          보유 종목
        </h1>
        <button 
          onClick={fetchData}
          className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
        >
          새로고침
        </button>
      </div>

      {/* 현재 레짐 */}
      {regime && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <div className="flex items-center gap-2">
            <span className="text-2xl">
              {regime.regime === '상승장' ? '📈' : regime.regime === '하락장' ? '📉' : '➡️'}
            </span>
            <div>
              <span className="font-bold text-lg">{regime.regime}</span>
              <span className="ml-2 text-gray-600">
                (신뢰도: {(regime.confidence * 100).toFixed(1)}%)
              </span>
              {regime.us_market_regime && (
                <span className="ml-2 text-gray-600">
                  | 미국: {regime.us_market_regime}
                </span>
              )}
            </div>
          </div>
        </div>
      )}

      {/* 요약 카드 */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white rounded-lg shadow p-6">
          <div className="text-sm text-gray-600 mb-1">총 평가액</div>
          <div className="text-2xl font-bold">₩{formatNumber(totalValue)}</div>
        </div>
        
        <div className="bg-white rounded-lg shadow p-6">
          <div className="text-sm text-gray-600 mb-1">총 손익</div>
          <div className={`text-2xl font-bold flex items-center gap-1 ${
            totalProfit >= 0 ? 'text-green-600' : 'text-red-600'
          }`}>
            {totalProfit >= 0 ? <TrendingUp className="w-6 h-6" /> : <TrendingDown className="w-6 h-6" />}
            {totalProfit >= 0 ? '+' : ''}₩{formatNumber(totalProfit)}
          </div>
        </div>
        
        <div className="bg-white rounded-lg shadow p-6">
          <div className="text-sm text-gray-600 mb-1">수익률</div>
          <div className={`text-2xl font-bold ${
            totalProfitRate >= 0 ? 'text-green-600' : 'text-red-600'
          }`}>
            {totalProfitRate >= 0 ? '+' : ''}{totalProfitRate.toFixed(2)}%
          </div>
        </div>
      </div>

      {/* 보유 종목 테이블 */}
      <div className="bg-white rounded-lg shadow overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700">종목명</th>
                <th className="px-4 py-3 text-right text-sm font-semibold text-gray-700">수량</th>
                <th className="px-4 py-3 text-right text-sm font-semibold text-gray-700">평균가</th>
                <th className="px-4 py-3 text-right text-sm font-semibold text-gray-700">현재가</th>
                <th className="px-4 py-3 text-right text-sm font-semibold text-gray-700">평가액</th>
                <th className="px-4 py-3 text-right text-sm font-semibold text-gray-700">손익</th>
                <th className="px-4 py-3 text-right text-sm font-semibold text-gray-700">수익률</th>
                <th className="px-4 py-3 text-center text-sm font-semibold text-gray-700">신호</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {holdings.map((holding) => {
                const value = holding.current_price * holding.quantity
                const profit = (holding.current_price - holding.avg_price) * holding.quantity
                const profitRate = ((holding.current_price - holding.avg_price) / holding.avg_price) * 100
                const signal = getSellSignal(holding)
                
                return (
                  <tr key={holding.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3">
                      <div className="font-medium">{holding.name}</div>
                      <div className="text-sm text-gray-500">{holding.code}</div>
                    </td>
                    <td className="px-4 py-3 text-right">{formatNumber(holding.quantity)}</td>
                    <td className="px-4 py-3 text-right">₩{formatNumber(holding.avg_price)}</td>
                    <td className="px-4 py-3 text-right">₩{formatNumber(holding.current_price)}</td>
                    <td className="px-4 py-3 text-right font-medium">₩{formatNumber(value)}</td>
                    <td className={`px-4 py-3 text-right font-medium ${
                      profit >= 0 ? 'text-green-600' : 'text-red-600'
                    }`}>
                      {profit >= 0 ? '+' : ''}₩{formatNumber(profit)}
                    </td>
                    <td className={`px-4 py-3 text-right font-medium ${
                      profitRate >= 0 ? 'text-green-600' : 'text-red-600'
                    }`}>
                      {profitRate >= 0 ? '+' : ''}{profitRate.toFixed(2)}%
                    </td>
                    <td className="px-4 py-3 text-center">
                      {signal.show && (
                        <span className={`inline-flex items-center gap-1 px-2 py-1 rounded text-xs font-medium ${signal.color}`}>
                          <AlertTriangle className="w-3 h-3" />
                          {signal.text}
                        </span>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* 통계 및 안내 */}
      <div className="bg-gray-50 rounded-lg p-4">
        <div className="text-sm text-gray-600 mb-2">
          총 {holdings.length}개 종목 보유 중
        </div>
        <div className="text-sm text-blue-600 bg-blue-50 p-3 rounded border border-blue-200">
          💡 <strong>종목 관리 방법:</strong>
          <ul className="mt-2 ml-4 space-y-1">
            <li>• <strong>신규 매수:</strong> API 문서에서 POST /api/v1/holdings 사용</li>
            <li>• <strong>추가 매수:</strong> 같은 종목 코드로 POST 하면 자동으로 평균가 재계산</li>
            <li>• <strong>부분 매도:</strong> PUT /api/v1/holdings/{'{id}'} (action: "sell")</li>
            <li>• <strong>전체 매도:</strong> DELETE /api/v1/holdings/{'{id}'}</li>
          </ul>
          <div className="mt-2">
            <a 
              href="http://localhost:8000/api/docs" 
              target="_blank" 
              rel="noopener noreferrer"
              className="text-blue-700 underline hover:text-blue-900"
            >
              → API 문서 열기 (http://localhost:8000/api/docs)
            </a>
          </div>
        </div>
      </div>
    </div>
  )
}
