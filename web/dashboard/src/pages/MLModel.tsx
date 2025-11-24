import { AlertCircle, Play, RefreshCw, MessageSquare, Settings, History } from 'lucide-react';
import { useState, useMemo, useEffect } from 'react';
import { useApi } from '../hooks/useApi';
import { apiClient } from '../api/client';
import { type MLModelInfo } from '../types';
import { AIPromptModal } from '../components/AIPromptModal';
import { ParameterModal } from '../components/ParameterModal';
import { HistoryTable } from '../components/HistoryTable';
import { ComparisonChart } from '../components/ComparisonChart';
import { generateMLPrompt } from '../utils/promptGenerator';

export default function MLModel() {
  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);
  const [showPrompt, setShowPrompt] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [parameters, setParameters] = useState<any>(null);
  const [history, setHistory] = useState<any[]>([]);
  const [showComparison, setShowComparison] = useState(false);
  const [comparisonItems, setComparisonItems] = useState<any[]>([]);

  const { data: modelInfo, loading, error } = useApi<MLModelInfo>(
    () => apiClient.getMLModelInfo(),
    []
  );

  const prompt = useMemo(() => {
    if (!modelInfo) return '';
    return generateMLPrompt(modelInfo);
  }, [modelInfo]);

  useEffect(() => {
    loadParameters();
    loadHistory();
  }, []);

  const loadParameters = async () => {
    try {
      const params = await apiClient.getMLParameters();
      setParameters(params);
    } catch (err) {
      console.error('파라미터 로드 실패:', err);
    }
  };

  const loadHistory = async () => {
    try {
      const hist = await apiClient.getMLHistory();
      setHistory(hist);
    } catch (err) {
      console.error('히스토리 로드 실패:', err);
    }
  };

  const handleSaveParameters = async (params: any) => {
    try {
      await apiClient.updateMLParameters(params);
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

  const handleCompare = (items: any[]) => {
    setComparisonItems(items);
    setShowComparison(true);
  };

  const handleTrainModel = async () => {
    try {
      setRunning(true);
      setRunError(null);
      await apiClient.trainMLModel('xgboost', 'regression');
      window.location.reload();
    } catch (err) {
      setRunError(err instanceof Error ? err.message : 'ML 모델 학습 실패');
    } finally {
      setRunning(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">ML 모델 정보를 불러오는 중...</p>
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

  if (!modelInfo) {
    return (
      <div className="flex items-center justify-center h-96">
        <p className="text-gray-600">ML 모델 정보가 없습니다</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-3xl font-bold">ML 모델</h2>
          <p className="text-muted-foreground mt-1">머신러닝 모델 학습 및 성능 분석</p>
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
            onClick={handleTrainModel}
            disabled={running}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed"
          >
            {running ? (
              <>
                <RefreshCw className="h-4 w-4 animate-spin" />
                학습 중...
              </>
            ) : (
              <>
                <Play className="h-4 w-4" />
                모델 학습
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
        <h3 className="text-xl font-bold mb-4">학습 결과</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="p-4 bg-secondary rounded">
            <p className="text-sm text-muted-foreground">Train R²</p>
            <p className="text-2xl font-bold mt-1">{modelInfo.train_score.toFixed(4)}</p>
          </div>
          <div className="p-4 bg-secondary rounded">
            <p className="text-sm text-muted-foreground">Test R²</p>
            <p className="text-2xl font-bold mt-1">{modelInfo.test_score.toFixed(4)}</p>
          </div>
          <div className="p-4 bg-secondary rounded">
            <p className="text-sm text-muted-foreground">특징 개수</p>
            <p className="text-2xl font-bold mt-1">{modelInfo.n_features}</p>
          </div>
        </div>

        {modelInfo.test_score < 0 && (
          <div className="mt-4 p-4 bg-yellow-50 border border-yellow-200 rounded">
            <p className="text-yellow-800">⚠️ 과적합 신호: Test R²가 음수입니다</p>
          </div>
        )}
      </div>

      <div className="bg-card rounded-lg border p-6">
        <h3 className="text-xl font-bold mb-4">Top Feature Importance</h3>
        <div className="space-y-2">
          {modelInfo.feature_importance.map((feature, index) => (
            <div key={index} className="flex items-center gap-4">
              <span className="text-sm font-medium w-32">{feature.feature}</span>
              <div className="flex-1 bg-secondary rounded-full h-6">
                <div
                  className="bg-blue-600 h-6 rounded-full flex items-center justify-end pr-2"
                  style={{ width: `${feature.importance * 1000}%` }}
                >
                  <span className="text-xs text-white">{feature.importance.toFixed(4)}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 히스토리 */}
      <div className="bg-card rounded-lg border p-6">
        <h3 className="text-xl font-bold mb-4">ML 모델 히스토리</h3>
        <HistoryTable
          items={history}
          metricColumns={[
            { key: 'train_score', label: 'Train R²', format: (v) => v.toFixed(4) },
            { key: 'test_score', label: 'Test R²', format: (v) => v.toFixed(4) },
          ]}
          onSelect={handleSelectHistory}
          onCompare={handleCompare}
        />
      </div>

      {/* 파라미터 설정 모달 */}
      {parameters && (
        <ParameterModal
          isOpen={showSettings}
          onClose={() => setShowSettings(false)}
          title="ML 모델 파라미터 설정"
          fields={[
            { name: 'n_estimators', label: '트리 개수', type: 'number', value: parameters.n_estimators, min: 10, max: 500 },
            { name: 'max_depth', label: '최대 깊이', type: 'number', value: parameters.max_depth, min: 1, max: 20 },
            { name: 'learning_rate', label: '학습률', type: 'number', value: parameters.learning_rate, min: 0.001, max: 1, step: 0.001 },
            { name: 'min_child_weight', label: '최소 자식 가중치', type: 'number', value: parameters.min_child_weight, min: 1, max: 10 },
            { name: 'subsample', label: '서브샘플 비율', type: 'number', value: parameters.subsample, min: 0.1, max: 1, step: 0.1 },
            { name: 'colsample_bytree', label: '특징 샘플링', type: 'number', value: parameters.colsample_bytree, min: 0.1, max: 1, step: 0.1 },
          ]}
          history={history}
          historyMetricColumns={[
            { key: 'train_score', label: 'Train R²', format: (v) => v.toFixed(4) },
            { key: 'test_score', label: 'Test R²', format: (v) => v.toFixed(4) },
          ]}
          onSave={handleSaveParameters}
          onSelectHistory={handleSelectHistory}
        />
      )}

      {/* 비교 차트 */}
      <ComparisonChart
        isOpen={showComparison}
        onClose={() => setShowComparison(false)}
        items={comparisonItems}
        metricColumns={[
          { key: 'train_score', label: 'Train R²', format: (v) => v.toFixed(4) },
          { key: 'test_score', label: 'Test R²', format: (v) => v.toFixed(4) },
        ]}
        title="ML 모델 성능 비교"
      />

      {/* AI 프롬프트 모달 */}
      <AIPromptModal
        isOpen={showPrompt}
        onClose={() => setShowPrompt(false)}
        prompt={prompt}
        title="ML 모델 학습 결과 - AI 질문"
      />
    </div>
  )
}
