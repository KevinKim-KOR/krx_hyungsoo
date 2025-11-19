import { AlertCircle, Play, RefreshCw, MessageSquare } from 'lucide-react';
import { useState, useMemo } from 'react';
import { useApi } from '../hooks/useApi';
import { apiClient } from '../api/client';
import type { PortfolioOptimization } from '../types';
import { AIPromptModal } from '../components/AIPromptModal';
import { generatePortfolioPrompt } from '../utils/promptGenerator';

export default function Portfolio() {
  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);
  const [showPrompt, setShowPrompt] = useState(false);
  
  const { data: optimization, loading, error } = useApi<PortfolioOptimization>(
    () => apiClient.getPortfolioOptimization(),
    []
  );

  const handleRunOptimization = async () => {
    try {
      setRunning(true);
      setRunError(null);
      await apiClient.runPortfolioOptimization('max_sharpe', 10000000);
      // 성공 시 페이지 새로고침
      window.location.reload();
    } catch (err) {
      setRunError(err instanceof Error ? err.message : '최적화 실행 실패');
    } finally {
      setRunning(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">포트폴리오 최적화 결과를 불러오는 중...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center">
          <AlertCircle className="h-12 w-12 text-red-500 mx-auto mb-4" />
          <p className="text-red-600 mb-2">데이터를 불러오는데 실패했습니다</p>
          <p className="text-sm text-gray-500">{error}</p>
        </div>
      </div>
    );
  }

  if (!optimization) {
    return (
      <div className="flex items-center justify-center h-96">
        <p className="text-gray-600">포트폴리오 최적화 결과가 없습니다</p>
      </div>
    );
  }

  const formatPercent = (value: number) => `${(value * 100).toFixed(1)}%`;
  const formatCurrency = (value: number) => new Intl.NumberFormat('ko-KR').format(value);

  const prompt = useMemo(() => {
    return generatePortfolioPrompt(optimization);
  }, [optimization]);

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-3xl font-bold">포트폴리오 최적화</h2>
        <div className="flex gap-2">
          <button
            onClick={() => setShowPrompt(true)}
            className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700"
          >
            <MessageSquare className="h-4 w-4" />
            💬 AI에게 질문하기
          </button>
          <button
            onClick={handleRunOptimization}
            disabled={running}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed"
          >
            {running ? (
              <>
                <RefreshCw className="h-4 w-4 animate-spin" />
                실행 중...
              </>
            ) : (
              <>
                <Play className="h-4 w-4" />
                최적화 실행
              </>
            )}
          </button>
        </div>
      </div>

      {runError && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <p className="text-red-600">{runError}</p>
        </div>
      )}

      <div className="bg-card rounded-lg border p-6">
        <h3 className="text-xl font-bold mb-4">최적 비중 (Sharpe Ratio 최대화)</h3>
        <div className="space-y-2">
          {Object.entries(optimization.weights).map(([code, weight]) => (
            <div key={code} className="flex justify-between items-center p-3 bg-secondary rounded">
              <span className="font-medium">{code}</span>
              <span className="text-lg font-bold">{formatPercent(weight)}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-card rounded-lg border p-6">
          <h4 className="text-sm font-medium text-muted-foreground">기대 수익률</h4>
          <p className="text-2xl font-bold mt-2">{formatPercent(optimization.expected_return)}</p>
        </div>
        <div className="bg-card rounded-lg border p-6">
          <h4 className="text-sm font-medium text-muted-foreground">변동성</h4>
          <p className="text-2xl font-bold mt-2">{formatPercent(optimization.volatility)}</p>
        </div>
        <div className="bg-card rounded-lg border p-6">
          <h4 className="text-sm font-medium text-muted-foreground">Sharpe Ratio</h4>
          <p className="text-2xl font-bold mt-2">{optimization.sharpe_ratio.toFixed(2)}</p>
        </div>
      </div>

      {optimization.discrete_allocation && (
        <div className="bg-card rounded-lg border p-6">
          <h3 className="text-xl font-bold mb-4">이산 배분</h3>
          <div className="space-y-2">
            {Object.entries(optimization.discrete_allocation.allocation).map(([code, shares]) => (
              <div key={code} className="flex justify-between items-center p-3 bg-secondary rounded">
                <span>{code}</span>
                <span className="font-bold">{shares}주</span>
              </div>
            ))}
            <div className="flex justify-between items-center p-3 bg-primary/10 rounded mt-4">
              <span className="font-medium">잔액</span>
              <span className="font-bold">₩{formatCurrency(optimization.discrete_allocation.leftover)}</span>
            </div>
          </div>
        </div>
      )}

      {/* AI 프롬프트 모달 */}
      <AIPromptModal
        isOpen={showPrompt}
        onClose={() => setShowPrompt(false)}
        prompt={prompt}
        title="포트폴리오 최적화 결과 - AI 질문"
      />
    </div>
  );
}
