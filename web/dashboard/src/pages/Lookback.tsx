import { AlertCircle, Play, RefreshCw, MessageSquare, Settings, History } from 'lucide-react';
import { useState, useMemo, useEffect } from 'react';
import { useApi } from '../hooks/useApi';
import { apiClient } from '../api/client';
import type { LookbackAnalysis } from '../types';
import { AIPromptModal } from '../components/AIPromptModal';
import { ParameterModal } from '../components/ParameterModal';
import { HistoryTable } from '../components/HistoryTable';
import { generateLookbackPrompt } from '../utils/promptGenerator';

export default function Lookback() {
  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);
  const [showPrompt, setShowPrompt] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [parameters, setParameters] = useState<any>(null);
  const [history, setHistory] = useState<any[]>([]);

  const { data: analysis, loading, error } = useApi<LookbackAnalysis>(
    () => apiClient.getLookbackAnalysis(),
    []
  );

  const prompt = useMemo(() => {
    if (!analysis) return '';
    return generateLookbackPrompt(analysis);
  }, [analysis]);

  useEffect(() => {
    loadParameters();
    loadHistory();
  }, []);

  const loadParameters = async () => {
    try {
      const params = await apiClient.getLookbackParameters();
      setParameters(params);
    } catch (err) {
      console.error('파라미터 로드 실패:', err);
    }
  };

  const loadHistory = async () => {
    try {
      const hist = await apiClient.getLookbackHistory();
      setHistory(hist);
    } catch (err) {
      console.error('히스토리 로드 실패:', err);
    }
  };

  const handleSaveParameters = async (params: any) => {
    try {
      await apiClient.updateLookbackParameters(params);
      setParameters(params);
      alert('파라미터가 저장되었습니다.');
    } catch (err: any) {
      alert(`저장 실패: ${err.message}`);
    }
  };

  const handleRefreshHistory = async () => {
    await loadHistory();
  };

  const handleSelectHistory = (item: any) => {
    setParameters(item.parameters);
  };

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
        <div>
          <h2 className="text-3xl font-bold">룩백 분석</h2>
          <p className="text-muted-foreground mt-1">과거 데이터 기반 성과 분석</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setShowSettings(true)}
            className="flex items-center gap-2 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50"
          >
            <Settings className="h-4 w-4" />
            파라미터 설정
          </button>
          <button
            onClick={handleRefreshHistory}
            className="flex items-center gap-2 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50"
          >
            <History className="h-4 w-4" />
            히스토리 새로고침
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
          <button
            onClick={() => setShowPrompt(true)}
            className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700"
          >
            <MessageSquare className="h-4 w-4" />
            💬 AI에게 질문하기
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

      {/* 히스토리 */}
      <div className="bg-card rounded-lg border p-6">
        <h3 className="text-xl font-bold mb-4">룩백 분석 히스토리</h3>
        <HistoryTable
          items={history}
          metricColumns={[
            { key: 'total_return', label: '총 수익률', format: (v) => `${v.toFixed(2)}%` },
            { key: 'sharpe_ratio', label: 'Sharpe', format: (v) => v.toFixed(2) },
            { key: 'max_drawdown', label: 'MDD', format: (v) => `${v.toFixed(2)}%` },
          ]}
          onSelect={handleSelectHistory}
        />
      </div>

      {/* 파라미터 설정 모달 */}
      {parameters && (
        <ParameterModal
          isOpen={showSettings}
          onClose={() => setShowSettings(false)}
          title="룩백 분석 파라미터 설정"
          fields={[
            { name: 'lookback_days', label: '룩백 기간 (일)', type: 'number', value: parameters.lookback_days, min: 30, max: 365 },
            { name: 'rebalance_frequency', label: '리밸런싱 주기 (일)', type: 'number', value: parameters.rebalance_frequency, min: 1, max: 90 },
            { name: 'min_weight', label: '최소 비중', type: 'number', value: parameters.min_weight, min: 0, max: 0.5, step: 0.01 },
            { name: 'max_weight', label: '최대 비중', type: 'number', value: parameters.max_weight, min: 0, max: 1, step: 0.01 },
            { name: 'risk_free_rate', label: '무위험 수익률', type: 'number', value: parameters.risk_free_rate, min: 0, max: 0.1, step: 0.001 },
          ]}
          history={history}
          historyMetricColumns={[
            { key: 'total_return', label: '총 수익률', format: (v) => `${v.toFixed(2)}%` },
            { key: 'sharpe_ratio', label: 'Sharpe', format: (v) => v.toFixed(2) },
            { key: 'max_drawdown', label: 'MDD', format: (v) => `${v.toFixed(2)}%` },
          ]}
          onSave={handleSaveParameters}
          onSelectHistory={handleSelectHistory}
        />
      )}

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
