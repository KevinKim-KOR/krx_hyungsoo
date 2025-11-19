import { AlertCircle, Play, RefreshCw, MessageSquare } from 'lucide-react';
import { useState, useMemo } from 'react';
import { useApi } from '../hooks/useApi';
import { apiClient } from '../api/client';
import type { LookbackAnalysis } from '../types';
import { AIPromptModal } from '../components/AIPromptModal';
import { generateLookbackPrompt } from '../utils/promptGenerator';

export default function Lookback() {
  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);
  const [showPrompt, setShowPrompt] = useState(false);

  const { data: analysis, loading, error } = useApi<LookbackAnalysis>(
    () => apiClient.getLookbackAnalysis(),
    []
  );

  const prompt = useMemo(() => {
    if (!analysis) return '';
    return generateLookbackPrompt(analysis);
  }, [analysis]);

  const handleRunAnalysis = async () => {
    try {
      setRunning(true);
      setRunError(null);
      await apiClient.runLookbackAnalysis('portfolio_optimization', 120, 30);
      window.location.reload();
    } catch (err) {
      setRunError(err instanceof Error ? err.message : '룩백 분석 실행 실패');
    } finally {
      setRunning(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">룩백 분석 결과를 불러오는 중...</p>
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

  if (!analysis) {
    return (
      <div className="flex items-center justify-center h-96">
        <p className="text-gray-600">룩백 분석 결과가 없습니다</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-3xl font-bold">룩백 분석</h2>
        <div className="flex gap-2">
          <button
            onClick={() => setShowPrompt(true)}
            className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700"
          >
            <MessageSquare className="h-4 w-4" />
            💬 AI에게 질문하기
          </button>
          <button
            onClick={handleRunAnalysis}
            disabled={running}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed"
          >
            {running ? (
              <>
                <RefreshCw className="h-4 w-4 animate-spin" />
                분석 중...
              </>
            ) : (
              <>
                <Play className="h-4 w-4" />
                분석 실행
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
        <h3 className="text-xl font-bold mb-4">요약</h3>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="p-4 bg-secondary rounded">
            <p className="text-sm text-muted-foreground">리밸런싱 횟수</p>
            <p className="text-2xl font-bold mt-1">{analysis.summary.total_rebalances}회</p>
          </div>
          <div className="p-4 bg-secondary rounded">
            <p className="text-sm text-muted-foreground">평균 수익률</p>
            <p className="text-2xl font-bold mt-1">{(analysis.summary.avg_return * 100).toFixed(2)}%</p>
          </div>
          <div className="p-4 bg-secondary rounded">
            <p className="text-sm text-muted-foreground">평균 Sharpe</p>
            <p className="text-2xl font-bold mt-1">{analysis.summary.avg_sharpe.toFixed(2)}</p>
          </div>
          <div className="p-4 bg-secondary rounded">
            <p className="text-sm text-muted-foreground">승률</p>
            <p className="text-2xl font-bold mt-1">{(analysis.summary.win_rate * 100).toFixed(0)}%</p>
          </div>
        </div>
      </div>
      <div className="bg-card rounded-lg border p-6">
        <h3 className="text-xl font-bold mb-4">리밸런싱 결과</h3>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b">
                <th className="text-left p-3">날짜</th>
                <th className="text-right p-3">수익률</th>
                <th className="text-right p-3">Sharpe</th>
                <th className="text-right p-3">변동성</th>
              </tr>
            </thead>
            <tbody>
              {analysis.results.map((result, index) => (
                <tr key={index} className="border-b">
                  <td className="p-3">{result.rebalance_date}</td>
                  <td className={`text-right p-3 font-bold ${result.return >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                    {result.return >= 0 ? '+' : ''}{(result.return * 100).toFixed(2)}%
                  </td>
                  <td className="text-right p-3">{result.sharpe_ratio.toFixed(2)}</td>
                  <td className="text-right p-3">{(result.volatility * 100).toFixed(2)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* AI 프롬프트 모달 */}
      <AIPromptModal
        isOpen={showPrompt}
        onClose={() => setShowPrompt(false)}
        prompt={prompt}
        title="룩백 분석 결과 - AI 질문"
      />
    </div>
  )
}
