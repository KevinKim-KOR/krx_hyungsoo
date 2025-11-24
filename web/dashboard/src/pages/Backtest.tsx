import { AlertCircle, MessageSquare, Play, Settings, History } from 'lucide-react';
import { useState, useMemo, useEffect } from 'react';
import { useApi } from '../hooks/useApi';
import { apiClient } from '../api/client';
import type { BacktestResult } from '../types';
import { AIPromptModal } from '../components/AIPromptModal';
import { ParameterModal } from '../components/ParameterModal';
import { HistoryTable } from '../components/HistoryTable';
import { generateBacktestPrompt } from '../utils/promptGenerator';

export default function Backtest() {
  const [showPrompt, setShowPrompt] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [running, setRunning] = useState(false);
  const [parameters, setParameters] = useState<any>(null);
  const [history, setHistory] = useState<any[]>([]);

  const { data: results, loading, error } = useApi<BacktestResult[]>(
    () => apiClient.getBacktestResults(),
    []
  );

  // 파라미터 및 히스토리 로드
  useEffect(() => {
    loadParameters();
    loadHistory();
  }, []);

  const loadParameters = async () => {
    try {
      const params = await apiClient.getCurrentParameters();
      setParameters(params);
    } catch (err) {
      console.error('파라미터 로드 실패:', err);
    }
  };

  const loadHistory = async () => {
    try {
      const hist = await apiClient.getBacktestHistory();
      setHistory(hist);
    } catch (err) {
      console.error('히스토리 로드 실패:', err);
    }
  };

  const handleRunBacktest = async () => {
    if (running) return;
    
    setRunning(true);
    
    try {
      const response = await apiClient.runBacktest();
      
      // 히스토리에 추가 (임시 - 실제로는 백테스트 완료 후)
      const newHistory = {
        id: Date.now().toString(),
        timestamp: new Date().toISOString(),
        parameters: parameters || {},
        metrics: { cagr: 0, sharpe: 0, mdd: 0 },
        status: 'running'
      };
      await apiClient.saveBacktestHistory(newHistory);
      
      alert('백테스트가 시작되었습니다. 완료까지 몇 분이 소요될 수 있습니다.');
      
      // 10초 후 페이지 새로고침
      setTimeout(() => {
        window.location.reload();
      }, 10000);
    } catch (err: any) {
      alert(`실행 실패: ${err.message}`);
      setRunning(false);
    }
  };

  const handleSaveParameters = async (params: any) => {
    try {
      await apiClient.updateParameters(params);
      setParameters(params);
      alert('파라미터가 저장되었습니다.');
    } catch (err: any) {
      alert(`저장 실패: ${err.message}`);
    }
  };

  const handleApplyPreset = async (presetName: string) => {
    try {
      const params = await apiClient.applyPreset(presetName);
      setParameters(params);
      alert(`${presetName} 프리셋이 적용되었습니다.`);
    } catch (err: any) {
      alert(`프리셋 적용 실패: ${err.message}`);
    }
  };

  const prompt = useMemo(() => {
    if (!results || results.length === 0) return '';
    // 첫 번째 결과 사용 (가장 최신)
    return generateBacktestPrompt(results[0]);
  }, [results]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">백테스트 결과를 불러오는 중...</p>
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

  if (!results || results.length === 0) {
    return (
      <div className="flex items-center justify-center h-96">
        <p className="text-gray-600">백테스트 결과가 없습니다</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-3xl font-bold">백테스트</h2>
          <p className="text-muted-foreground mt-1">전략 성능 분석</p>
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
            onClick={handleRunBacktest}
            disabled={running}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Play className="h-4 w-4" />
            {running ? '실행 중...' : '백테스트 실행'}
          </button>
          <button
            onClick={() => setShowHistory(!showHistory)}
            className="flex items-center gap-2 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50"
          >
            <History className="h-4 w-4" />
            히스토리
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
      
      <div className="bg-card rounded-lg border p-6">
        <h3 className="text-xl font-bold mb-4">백테스트 결과</h3>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b">
                <th className="text-left p-3">전략</th>
                <th className="text-right p-3">기간</th>
                <th className="text-right p-3">CAGR</th>
                <th className="text-right p-3">Sharpe</th>
                <th className="text-right p-3">MDD</th>
                <th className="text-right p-3">총 수익률</th>
              </tr>
            </thead>
            <tbody>
              {results.map((result, index) => (
                <tr key={index} className="border-b">
                  <td className="p-3 font-medium">{result.strategy}</td>
                  <td className="p-3 text-right text-sm text-muted-foreground">
                    {result.start_date} ~ {result.end_date}
                  </td>
                  <td className="p-3 text-right font-bold text-green-600">
                    {result.cagr.toFixed(2)}%
                  </td>
                  <td className="p-3 text-right">{result.sharpe_ratio.toFixed(2)}</td>
                  <td className="p-3 text-right text-red-600">
                    {result.max_drawdown.toFixed(2)}%
                  </td>
                  <td className="p-3 text-right font-bold">
                    {result.total_return >= 0 ? '+' : ''}{result.total_return.toFixed(2)}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* 상세 정보 */}
      {results[0] && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-card rounded-lg border p-6">
            <h4 className="text-sm font-medium text-muted-foreground">CAGR</h4>
            <p className="text-3xl font-bold mt-2 text-green-600">
              {results[0].cagr.toFixed(2)}%
            </p>
            <p className="text-sm text-muted-foreground mt-1">연평균 수익률</p>
          </div>
          <div className="bg-card rounded-lg border p-6">
            <h4 className="text-sm font-medium text-muted-foreground">Sharpe Ratio</h4>
            <p className="text-3xl font-bold mt-2">
              {results[0].sharpe_ratio.toFixed(2)}
            </p>
            <p className="text-sm text-muted-foreground mt-1">위험 대비 수익</p>
          </div>
          <div className="bg-card rounded-lg border p-6">
            <h4 className="text-sm font-medium text-muted-foreground">Max Drawdown</h4>
            <p className="text-3xl font-bold mt-2 text-red-600">
              {results[0].max_drawdown.toFixed(2)}%
            </p>
            <p className="text-sm text-muted-foreground mt-1">최대 손실</p>
          </div>
        </div>
      )}

      {/* 히스토리 */}
      {showHistory && (
        <div className="bg-card rounded-lg border p-6">
          <h3 className="text-xl font-bold mb-4">백테스트 히스토리</h3>
          <HistoryTable
            items={history}
            metricColumns={[
              { key: 'cagr', label: 'CAGR', format: (v) => `${v.toFixed(2)}%` },
              { key: 'sharpe', label: 'Sharpe', format: (v) => v.toFixed(2) },
              { key: 'mdd', label: 'MDD', format: (v) => `${v.toFixed(2)}%` },
            ]}
          />
        </div>
      )}

      {/* 파라미터 설정 모달 */}
      {parameters && (
        <ParameterModal
          isOpen={showSettings}
          onClose={() => setShowSettings(false)}
          title="백테스트 파라미터 설정"
          fields={[
            { name: 'top_n', label: 'Top N 종목', type: 'number', value: parameters.top_n, min: 1, max: 50 },
            { name: 'stop_loss', label: '손절 기준', type: 'number', value: parameters.stop_loss, min: -0.2, max: 0, step: 0.01 },
            { name: 'take_profit', label: '익절 기준', type: 'number', value: parameters.take_profit, min: 0, max: 1, step: 0.01 },
            { name: 'short_ma_period', label: '단기 MA', type: 'number', value: parameters.short_ma_period, min: 10, max: 100 },
            { name: 'long_ma_period', label: '장기 MA', type: 'number', value: parameters.long_ma_period, min: 100, max: 300 },
            { name: 'bull_threshold', label: '상승장 임계값', type: 'number', value: parameters.bull_threshold, min: 0, max: 0.1, step: 0.001 },
          ]}
          presets={[
            { name: 'conservative', label: '보수적', description: '안정적인 수익 추구' },
            { name: 'balanced', label: '균형', description: '수익과 리스크 균형' },
            { name: 'aggressive', label: '공격적', description: '높은 수익 추구' },
          ]}
          onSave={handleSaveParameters}
          onApplyPreset={handleApplyPreset}
        />
      )}

      {/* AI 프롬프트 모달 */}
      <AIPromptModal
        isOpen={showPrompt}
        onClose={() => setShowPrompt(false)}
        prompt={prompt}
        title="백테스트 결과 - AI 질문"
      />
    </div>
  )
}
