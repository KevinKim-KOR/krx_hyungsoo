import { AlertCircle, Plus, Trash2, Edit2, TrendingUp, TrendingDown, MessageSquare } from 'lucide-react';
import { useState, useMemo } from 'react';
import { useApi } from '../hooks/useApi';
import { apiClient } from '../api/client';
import type { Holding, RegimeInfo } from '../types';
import { AIPromptModal } from '../components/AIPromptModal';
import { generateHoldingsPrompt } from '../utils/promptGenerator';

export default function Holdings() {
  const [showAddModal, setShowAddModal] = useState(false);
  const [editingHolding, setEditingHolding] = useState<Holding | null>(null);
  const [showPrompt, setShowPrompt] = useState(false);
  
  const { data: holdings, loading: holdingsLoading, error: holdingsError, refetch } = useApi<Holding[]>(
    () => apiClient.getHoldings(),
    []
  );

  const { data: regime } = useApi<RegimeInfo>(
    () => apiClient.getCurrentRegime(),
    []
  );

  const prompt = useMemo(() => {
    if (!holdings || !regime) return '';
    return generateHoldingsPrompt(holdings, regime);
  }, [holdings, regime]);

  const totalValue = useMemo(() => {
    if (!holdings) return 0;
    return holdings.reduce((sum, h) => sum + (h.quantity * h.current_price), 0);
  }, [holdings]);

  const totalProfit = useMemo(() => {
    if (!holdings) return 0;
    return holdings.reduce((sum, h) => sum + ((h.current_price - h.avg_price) * h.quantity), 0);
  }, [holdings]);

  const totalProfitRate = useMemo(() => {
    if (!holdings || holdings.length === 0) return 0;
    const totalCost = holdings.reduce((sum, h) => sum + (h.avg_price * h.quantity), 0);
    return totalCost > 0 ? (totalProfit / totalCost) * 100 : 0;
  }, [holdings, totalProfit]);

  const handleDelete = async (id: number) => {
    if (!confirm('정말 삭제하시겠습니까?')) return;
    try {
      await apiClient.deleteHolding(id);
      refetch();
    } catch (err) {
      alert('삭제 실패: ' + (err instanceof Error ? err.message : '알 수 없는 오류'));
    }
  };

  const getSellSignal = (holding: Holding): { show: boolean; reason: string; color: string } => {
    if (!regime) return { show: false, reason: '', color: '' };

    // 하락장: 모든 종목 매도 권장
    if (regime.regime === '하락장') {
      return { show: true, reason: '하락장 전환', color: 'bg-red-100 text-red-800 border-red-300' };
    }

    // 중립장: 일부 매도 권장
    if (regime.regime === '중립장') {
      return { show: true, reason: '중립장 - 일부 매도 권장', color: 'bg-yellow-100 text-yellow-800 border-yellow-300' };
    }

    // 손실이 큰 경우
    const profitRate = ((holding.current_price - holding.avg_price) / holding.avg_price) * 100;
    if (profitRate < -10) {
      return { show: true, reason: `손실 ${profitRate.toFixed(1)}%`, color: 'bg-orange-100 text-orange-800 border-orange-300' };
    }

    return { show: false, reason: '', color: '' };
  };

  const formatCurrency = (value: number) => new Intl.NumberFormat('ko-KR').format(Math.round(value));
  const formatPercent = (value: number) => {
    const sign = value >= 0 ? '+' : '';
    return `${sign}${value.toFixed(2)}%`;
  };

  if (holdingsLoading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">보유 종목을 불러오는 중...</p>
        </div>
      </div>
    );
  }

  if (holdingsError) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center">
          <AlertCircle className="h-12 w-12 text-red-500 mx-auto mb-4" />
          <p className="text-red-600 mb-2">데이터를 불러오는데 실패했습니다</p>
          <p className="text-sm text-gray-500">{holdingsError}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* 헤더 */}
      <div className="flex justify-between items-center">
        <h2 className="text-3xl font-bold">보유 종목</h2>
        <div className="flex gap-2">
          <button
            onClick={() => setShowPrompt(true)}
            className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700"
          >
            <MessageSquare className="h-4 w-4" />
            💬 AI에게 질문하기
          </button>
          <button
            onClick={() => setShowAddModal(true)}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            <Plus className="h-4 w-4" />
            종목 추가
          </button>
        </div>
      </div>

      {/* 현재 레짐 */}
      {regime && (
        <div className="bg-card rounded-lg border p-6">
          <h3 className="text-lg font-bold mb-3">현재 시장 레짐</h3>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <span className="text-2xl">
                {regime.regime === '상승장' ? '📈' : regime.regime === '하락장' ? '📉' : '➡️'}
              </span>
              <span className="text-xl font-bold">{regime.regime}</span>
            </div>
            <div className="text-sm text-muted-foreground">
              신뢰도: {(regime.confidence * 100).toFixed(1)}%
            </div>
            {regime.us_market_regime && (
              <div className="text-sm text-muted-foreground">
                미국: {regime.us_market_regime}
              </div>
            )}
          </div>
        </div>
      )}

      {/* 요약 */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-card rounded-lg border p-6">
          <h4 className="text-sm font-medium text-muted-foreground">총 평가액</h4>
          <p className="text-2xl font-bold mt-2">₩{formatCurrency(totalValue)}</p>
        </div>
        <div className="bg-card rounded-lg border p-6">
          <h4 className="text-sm font-medium text-muted-foreground">총 손익</h4>
          <p className={`text-2xl font-bold mt-2 ${totalProfit >= 0 ? 'text-green-600' : 'text-red-600'}`}>
            {totalProfit >= 0 ? '+' : ''}₩{formatCurrency(totalProfit)}
          </p>
        </div>
        <div className="bg-card rounded-lg border p-6">
          <h4 className="text-sm font-medium text-muted-foreground">수익률</h4>
          <p className={`text-2xl font-bold mt-2 ${totalProfitRate >= 0 ? 'text-green-600' : 'text-red-600'}`}>
            {formatPercent(totalProfitRate)}
          </p>
        </div>
      </div>

      {/* 보유 종목 목록 */}
      {!holdings || holdings.length === 0 ? (
        <div className="bg-card rounded-lg border p-12 text-center">
          <p className="text-gray-500 mb-4">보유 종목이 없습니다</p>
          <button
            onClick={() => setShowAddModal(true)}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            첫 종목 추가하기
          </button>
        </div>
      ) : (
        <div className="bg-card rounded-lg border overflow-hidden">
          <table className="w-full">
            <thead className="bg-secondary">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  종목
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  수량
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  평균가
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  현재가
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  손익
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  수익률
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  평가액
                </th>
                <th className="px-6 py-3 text-center text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  신호
                </th>
                <th className="px-6 py-3 text-center text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  액션
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {holdings.map((holding) => {
                const profit = (holding.current_price - holding.avg_price) * holding.quantity;
                const profitRate = ((holding.current_price - holding.avg_price) / holding.avg_price) * 100;
                const value = holding.current_price * holding.quantity;
                const sellSignal = getSellSignal(holding);

                return (
                  <tr key={holding.id} className="hover:bg-secondary/50">
                    <td className="px-6 py-4">
                      <div>
                        <div className="font-medium">{holding.name}</div>
                        <div className="text-sm text-muted-foreground">{holding.code}</div>
                      </div>
                    </td>
                    <td className="px-6 py-4 text-right">{formatCurrency(holding.quantity)}</td>
                    <td className="px-6 py-4 text-right">₩{formatCurrency(holding.avg_price)}</td>
                    <td className="px-6 py-4 text-right">₩{formatCurrency(holding.current_price)}</td>
                    <td className={`px-6 py-4 text-right font-medium ${profit >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                      {profit >= 0 ? (
                        <div className="flex items-center justify-end gap-1">
                          <TrendingUp className="h-4 w-4" />
                          +₩{formatCurrency(profit)}
                        </div>
                      ) : (
                        <div className="flex items-center justify-end gap-1">
                          <TrendingDown className="h-4 w-4" />
                          ₩{formatCurrency(profit)}
                        </div>
                      )}
                    </td>
                    <td className={`px-6 py-4 text-right font-medium ${profitRate >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                      {formatPercent(profitRate)}
                    </td>
                    <td className="px-6 py-4 text-right font-medium">₩{formatCurrency(value)}</td>
                    <td className="px-6 py-4 text-center">
                      {sellSignal.show && (
                        <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium border ${sellSignal.color}`}>
                          {sellSignal.reason}
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-4 text-center">
                      <div className="flex items-center justify-center gap-2">
                        <button
                          onClick={() => setEditingHolding(holding)}
                          className="p-1 text-blue-600 hover:bg-blue-50 rounded"
                          title="수정"
                        >
                          <Edit2 className="h-4 w-4" />
                        </button>
                        <button
                          onClick={() => handleDelete(holding.id)}
                          className="p-1 text-red-600 hover:bg-red-50 rounded"
                          title="삭제"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* AI 프롬프트 모달 */}
      <AIPromptModal
        isOpen={showPrompt}
        onClose={() => setShowPrompt(false)}
        prompt={prompt}
        title="보유 종목 분석 - AI 질문"
      />

      {/* TODO: 종목 추가/수정 모달 */}
      {(showAddModal || editingHolding) && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-md w-full">
            <h3 className="text-xl font-bold mb-4">
              {editingHolding ? '종목 수정' : '종목 추가'}
            </h3>
            <p className="text-gray-500">구현 예정</p>
            <button
              onClick={() => {
                setShowAddModal(false);
                setEditingHolding(null);
              }}
              className="mt-4 px-4 py-2 bg-gray-200 rounded-lg hover:bg-gray-300"
            >
              닫기
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
