import { AlertCircle, Play, RefreshCw } from 'lucide-react';
import { useState } from 'react';
import { useApi } from '../hooks/useApi';
import { apiClient } from '../api/client';
import type { MLModelInfo } from '../types';

export default function MLModel() {
  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);

  const { data: modelInfo, loading, error } = useApi<MLModelInfo>(
    () => apiClient.getMLModelInfo(),
    []
  );

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
        <h2 className="text-3xl font-bold">ML 모델</h2>
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
    </div>
  )
}
