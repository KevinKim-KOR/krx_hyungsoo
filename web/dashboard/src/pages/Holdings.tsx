import { useEffect, useState } from 'react'
import { Wallet, TrendingUp, TrendingDown, AlertTriangle, Plus, Edit, Trash2, X } from 'lucide-react'

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

interface ModalData {
  type: 'add' | 'buy' | 'sell' | null
  holding?: Holding
}

export default function Holdings() {
  const [holdings, setHoldings] = useState<Holding[]>([])
  const [regime, setRegime] = useState<Regime | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [modal, setModal] = useState<ModalData>({ type: null })
  
  // 폼 상태
  const [formData, setFormData] = useState({
    code: '',
    name: '',
    quantity: 0,
    price: 0
  })

  useEffect(() => {
    fetchData()
  }, [])

  const fetchData = async () => {
    try {
      setLoading(true)
      
      const holdingsRes = await fetch('http://localhost:8000/api/v1/holdings')
      if (!holdingsRes.ok) throw new Error('Holdings 조회 실패')
      const holdingsData = await holdingsRes.json()
      setHoldings(holdingsData)
      
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

  // 신규 매수 또는 추가 매수
  const handleAdd = async () => {
    try {
      const res = await fetch('http://localhost:8000/api/v1/holdings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData)
      })
      if (!res.ok) throw new Error('추가 실패')
      await fetchData()
      closeModal()
      alert('종목이 추가되었습니다!')
    } catch (err) {
      alert(err instanceof Error ? err.message : '추가 실패')
    }
  }

  // 부분 매도
  const handleSell = async () => {
    if (!modal.holding) return
    try {
      const res = await fetch(`http://localhost:8000/api/v1/holdings/${modal.holding.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          quantity: formData.quantity,
          price: formData.price,
          action: 'sell'
        })
      })
      if (!res.ok) throw new Error('매도 실패')
      await fetchData()
      closeModal()
      alert('매도되었습니다!')
    } catch (err) {
      alert(err instanceof Error ? err.message : '매도 실패')
    }
  }

  // 전체 매도 (삭제)
  const handleDelete = async (id: number, name: string) => {
    if (!confirm(`${name} 종목을 전체 매도하시겠습니까?`)) return
    try {
      const res = await fetch(`http://localhost:8000/api/v1/holdings/${id}`, {
        method: 'DELETE'
      })
      if (!res.ok) throw new Error('삭제 실패')
      await fetchData()
      alert('전체 매도되었습니다!')
    } catch (err) {
      alert(err instanceof Error ? err.message : '삭제 실패')
    }
  }

  const openModal = (type: 'add' | 'buy' | 'sell', holding?: Holding) => {
    setModal({ type, holding })
    if (type === 'add') {
      setFormData({ code: '', name: '', quantity: 0, price: 0 })
    } else if (holding) {
      setFormData({
        code: holding.code,
        name: holding.name,
        quantity: 0,
        price: holding.current_price
      })
    }
  }

  const closeModal = () => {
    setModal({ type: null })
    setFormData({ code: '', name: '', quantity: 0, price: 0 })
  }

  const totalValue = holdings.reduce((sum, h) => sum + (h.current_price * h.quantity), 0)
  const totalCost = holdings.reduce((sum, h) => sum + (h.avg_price * h.quantity), 0)
  const totalProfit = totalValue - totalCost
  const totalProfitRate = totalCost > 0 ? (totalProfit / totalCost) * 100 : 0

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
        <div className="flex gap-2">
          <button 
            onClick={() => openModal('add')}
            className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 flex items-center gap-2"
          >
            <Plus className="w-4 h-4" />
            종목 추가
          </button>
          <button 
            onClick={fetchData}
            className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
          >
            새로고침
          </button>
        </div>
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
                <th className="px-4 py-3 text-center text-sm font-semibold text-gray-700">관리</th>
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
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-center gap-1">
                        <button
                          onClick={() => openModal('buy', holding)}
                          className="p-1 text-blue-600 hover:bg-blue-50 rounded"
                          title="추가 매수"
                        >
                          <Plus className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => openModal('sell', holding)}
                          className="p-1 text-orange-600 hover:bg-orange-50 rounded"
                          title="부분 매도"
                        >
                          <Edit className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => handleDelete(holding.id, holding.name)}
                          className="p-1 text-red-600 hover:bg-red-50 rounded"
                          title="전체 매도"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* 통계 */}
      <div className="bg-gray-50 rounded-lg p-4">
        <div className="text-sm text-gray-600">
          총 {holdings.length}개 종목 보유 중
        </div>
      </div>

      {/* 모달 */}
      {modal.type && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-md">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-bold">
                {modal.type === 'add' && '신규 매수'}
                {modal.type === 'buy' && `추가 매수 - ${modal.holding?.name}`}
                {modal.type === 'sell' && `부분 매도 - ${modal.holding?.name}`}
              </h2>
              <button onClick={closeModal} className="text-gray-500 hover:text-gray-700">
                <X className="w-6 h-6" />
              </button>
            </div>

            <div className="space-y-4">
              {modal.type === 'add' && (
                <>
                  <div>
                    <label className="block text-sm font-medium mb-1">종목 코드</label>
                    <input
                      type="text"
                      value={formData.code}
                      onChange={(e) => setFormData({...formData, code: e.target.value})}
                      className="w-full px-3 py-2 border rounded"
                      placeholder="예: 005930"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1">종목명</label>
                    <input
                      type="text"
                      value={formData.name}
                      onChange={(e) => setFormData({...formData, name: e.target.value})}
                      className="w-full px-3 py-2 border rounded"
                      placeholder="예: 삼성전자"
                    />
                  </div>
                </>
              )}

              <div>
                <label className="block text-sm font-medium mb-1">수량</label>
                <input
                  type="number"
                  value={formData.quantity}
                  onChange={(e) => setFormData({...formData, quantity: parseInt(e.target.value) || 0})}
                  className="w-full px-3 py-2 border rounded"
                  placeholder="0"
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-1">가격</label>
                <input
                  type="number"
                  value={formData.price}
                  onChange={(e) => setFormData({...formData, price: parseInt(e.target.value) || 0})}
                  className="w-full px-3 py-2 border rounded"
                  placeholder="0"
                />
              </div>

              {modal.type === 'buy' && modal.holding && (
                <div className="bg-blue-50 p-3 rounded text-sm">
                  <div>현재 보유: {formatNumber(modal.holding.quantity)}주</div>
                  <div>평균가: ₩{formatNumber(modal.holding.avg_price)}</div>
                  <div className="mt-2 font-medium">
                    추가 매수 후 평균가: ₩
                    {formatNumber(
                      ((modal.holding.avg_price * modal.holding.quantity) + (formData.price * formData.quantity)) /
                      (modal.holding.quantity + formData.quantity)
                    )}
                  </div>
                </div>
              )}

              {modal.type === 'sell' && modal.holding && (
                <div className="bg-orange-50 p-3 rounded text-sm">
                  <div>현재 보유: {formatNumber(modal.holding.quantity)}주</div>
                  <div>매도 후 잔량: {formatNumber(modal.holding.quantity - formData.quantity)}주</div>
                </div>
              )}

              <div className="flex gap-2 pt-4">
                <button
                  onClick={closeModal}
                  className="flex-1 px-4 py-2 border rounded hover:bg-gray-50"
                >
                  취소
                </button>
                <button
                  onClick={modal.type === 'sell' ? handleSell : handleAdd}
                  className={`flex-1 px-4 py-2 text-white rounded ${
                    modal.type === 'sell' 
                      ? 'bg-orange-600 hover:bg-orange-700' 
                      : 'bg-blue-600 hover:bg-blue-700'
                  }`}
                >
                  {modal.type === 'add' && '매수'}
                  {modal.type === 'buy' && '추가 매수'}
                  {modal.type === 'sell' && '매도'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
