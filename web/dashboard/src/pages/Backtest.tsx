import { AlertCircle, MessageSquare, Play, Settings, History, TrendingUp, TrendingDown, Activity } from 'lucide-react';
import { useState, useMemo, useEffect } from 'react';
import { useApi } from '../hooks/useApi';
import { apiClient } from '../api/client';
import type { BacktestResult } from '../types';
import { AIPromptModal } from '../components/AIPromptModal';
import { ParameterModal } from '../components/ParameterModal';
import { HistoryTable } from '../components/HistoryTable';
import { ComparisonChart } from '../components/ComparisonChart';
import { generateBacktestPromptWithSplit } from '../utils/promptGenerator';

// 분할 결과 타입
interface SplitMetrics {
  total_return_pct: number;
  cagr: number;
  sharpe_ratio: number;
  max_drawdown: number;
  num_trades: number;
  total_costs: number;
  cost_ratio: number;
}

interface SplitPeriod {
  start: string;
  end: string;
  days: number;
}

interface SplitResults {
  strategy_params?: {
    ma_period?: number;
    rsi_period?: number;
    rsi_overbought?: number;
    maps_buy_threshold?: number;
    maps_sell_threshold?: number;
  };
  backtest_config?: {
    initial_capital?: number;
    max_positions?: number;
    commission_rate?: number;
    slippage_rate?: number;
    instrument_type?: string;
    enable_defense?: boolean;
  };
  periods: {
    train: SplitPeriod;
    val?: SplitPeriod;
    test: SplitPeriod;
  };
  train: SplitMetrics;
  val?: SplitMetrics;
  test: SplitMetrics;
  comparison: {
    status: string;
    is_overfit: boolean;
    validation_reliability?: string;
    degradation_pattern?: string;
    warnings: string[];
  };
}

export default function Backtest() {
  const [showPrompt, setShowPrompt] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [running, setRunning] = useState(false);
  const [parameters, setParameters] = useState<any>(null);
  const [history, setHistory] = useState<any[]>([]);
  const [showComparison, setShowComparison] = useState(false);
  const [comparisonItems, setComparisonItems] = useState<any[]>([]);
  const [splitResults, setSplitResults] = useState<SplitResults | null>(null);
  const [selectedHistoryItem, setSelectedHistoryItem] = useState<any>(null);

  const { data: results, loading, error } = useApi<BacktestResult[]>(
    () => apiClient.getBacktestResults(),
    []
  );

  // 파라미터 및 히스토리 자동 로드
  useEffect(() => {
    loadParameters();
    loadHistory();
    loadSplitResults();
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

  const loadSplitResults = async () => {
    try {
      const data = await apiClient.getSplitResults();
      setSplitResults(data);
    } catch (err) {
      console.error('분할 결과 로드 실패:', err);
    }
  };

  const handleRunBacktest = async () => {
    if (running) return;
    
    setRunning(true);
    
    // 현재 히스토리 개수 저장
    const currentHistoryCount = history.length;
    
    try {
      // 파라미터에서 날짜 가져오기
      const startDate = parameters?.start_date;
      const endDate = parameters?.end_date;
      await apiClient.runBacktest(startDate, endDate);
      
      alert('백테스트가 시작되었습니다. 완료까지 1-2분이 소요됩니다.\n완료 후 자동으로 결과가 갱신됩니다.');
      
      // 5초마다 히스토리 폴링 (최대 3분)
      let attempts = 0;
      const maxAttempts = 36; // 3분
      const pollInterval = setInterval(async () => {
        attempts++;
        try {
          // 히스토리가 증가했는지 확인 (스크립트에서 저장)
          const newHistory = await apiClient.getBacktestHistory();
          if (newHistory.length > currentHistoryCount && newHistory[0]?.status === 'success') {
            clearInterval(pollInterval);
            setHistory(newHistory);
            
            // 분할 결과도 갱신
            const newResults = await apiClient.getSplitResults();
            setSplitResults(newResults);
            
            setRunning(false);
            alert('✅ 백테스트가 완료되었습니다!');
          }
        } catch {
          // 아직 완료되지 않음
        }
        
        if (attempts >= maxAttempts) {
          clearInterval(pollInterval);
          setRunning(false);
          alert('백테스트가 아직 진행 중입니다. 잠시 후 새로고침해주세요.');
        }
      }, 5000);
      
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
      // 프리셋 적용 시 모달 닫지 않음
    } catch (err: any) {
      alert(`프리셋 적용 실패: ${err.message}`);
    }
  };

  const handleRefreshHistory = async () => {
    await loadHistory();
  };

  const handleSelectHistory = (item: any) => {
    // 히스토리 항목 선택 시 파라미터 적용 및 선택 상태 저장
    setParameters(item.parameters);
    setSelectedHistoryItem(item);
  };

  const handleCompare = (items: any[]) => {
    setComparisonItems(items);
    setShowComparison(true);
  };

  // 선택된 히스토리 또는 최신 결과 기반 프롬프트 생성
  const prompt = useMemo(() => {
    // 선택된 히스토리 항목이 있으면 해당 항목 기반 프롬프트 생성
    if (selectedHistoryItem) {
      return generateBacktestPromptWithSplit(
        selectedHistoryItem,
        splitResults,
        parameters
      );
    }
    // 없으면 최신 결과 사용
    if (!results || results.length === 0) return '';
    return generateBacktestPromptWithSplit(
      { metrics: results[0], parameters },
      splitResults,
      parameters
    );
  }, [results, selectedHistoryItem, splitResults, parameters]);

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
            onClick={handleRefreshHistory}
            className="flex items-center gap-2 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50"
          >
            <History className="h-4 w-4" />
            히스토리 새로고침
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
            onClick={() => setShowPrompt(true)}
            className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700"
          >
            <MessageSquare className="h-4 w-4" />
            💬 AI에게 질문하기
            {selectedHistoryItem && (
              <span className="text-xs bg-green-500 px-1.5 py-0.5 rounded">
                선택됨
              </span>
            )}
          </button>
        </div>
      </div>
      
      <div className="bg-card rounded-lg border p-6">
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-xl font-bold">백테스트 결과</h3>
          {selectedHistoryItem && (
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">
                선택됨: {new Date(selectedHistoryItem.timestamp).toLocaleString('ko-KR')}
              </span>
              <button
                onClick={() => setSelectedHistoryItem(null)}
                className="text-xs px-2 py-1 bg-gray-200 rounded hover:bg-gray-300"
              >
                선택 해제
              </button>
            </div>
          )}
        </div>
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
              {/* 선택된 히스토리 항목이 있으면 해당 항목 표시, 없으면 최신 결과 표시 */}
              {selectedHistoryItem ? (
                <tr className="border-b bg-blue-50">
                  <td className="p-3 font-medium">하이브리드 레짐 전략</td>
                  <td className="p-3 text-right text-sm text-muted-foreground">
                    {selectedHistoryItem.parameters?.start_date || '-'} ~ {selectedHistoryItem.parameters?.end_date || '-'}
                  </td>
                  <td className="p-3 text-right font-bold text-green-600">
                    {(selectedHistoryItem.metrics?.cagr ?? 0).toFixed(2)}%
                  </td>
                  <td className="p-3 text-right">{(selectedHistoryItem.metrics?.sharpe ?? 0).toFixed(2)}</td>
                  <td className="p-3 text-right text-red-600">
                    {(selectedHistoryItem.metrics?.mdd ?? 0).toFixed(2)}%
                  </td>
                  <td className="p-3 text-right font-bold">
                    {(selectedHistoryItem.metrics?.total_return ?? 0) >= 0 ? '+' : ''}{(selectedHistoryItem.metrics?.total_return ?? 0).toFixed(2)}%
                  </td>
                </tr>
              ) : (
                results.map((result, index) => (
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
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Train/Val/Test 분할 결과 */}
      {splitResults && (
        <div className="space-y-4">
          <h3 className="text-xl font-bold">Train / Validation / Test 분할 결과</h3>
          
          {/* 사용된 파라미터 카드 - 선택된 히스토리 또는 splitResults 기반 */}
          {(() => {
            // 선택된 히스토리 항목의 파라미터 또는 splitResults의 파라미터 사용
            const displayParams = selectedHistoryItem?.parameters || splitResults.strategy_params || {};
            const configParams = splitResults.backtest_config || {};
            
            return (displayParams || configParams) && (
              <div className="bg-card rounded-lg border p-4">
                <h4 className="text-sm font-bold text-muted-foreground mb-3 flex items-center gap-2">
                  <Settings className="h-4 w-4" />
                  사용된 파라미터
                  {selectedHistoryItem && (
                    <span className="text-xs bg-blue-100 text-blue-800 px-2 py-0.5 rounded ml-2">
                      선택된 히스토리
                    </span>
                  )}
                </h4>
                <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4 text-sm">
                  <div>
                    <span className="text-muted-foreground">MA 기간</span>
                    <p className="font-bold">{displayParams.ma_period || '-'}</p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">RSI 기간</span>
                    <p className="font-bold">{displayParams.rsi_period || '-'}</p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">RSI 과매수</span>
                    <p className="font-bold">{displayParams.rsi_overbought || '-'}</p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">매수 임계값</span>
                    <p className="font-bold">{displayParams.maps_buy_threshold ?? '-'}</p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">매도 임계값</span>
                    <p className="font-bold">{displayParams.maps_sell_threshold ?? '-'}</p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">초기 자본</span>
                    <p className="font-bold">{(displayParams.initial_capital || configParams.initial_capital || 0).toLocaleString()}원</p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">최대 포지션</span>
                    <p className="font-bold">{displayParams.top_n || configParams.max_positions || '-'}개</p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">상품 유형</span>
                    <p className="font-bold">{configParams.instrument_type || 'etf'}</p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">방어 시스템</span>
                    <p className="font-bold">{configParams.enable_defense ? '활성화' : '활성화'}</p>
                  </div>
                </div>
              </div>
            );
          })()}
          
          {/* 판정 상태 */}
          <div className={`p-4 rounded-lg border ${splitResults.comparison.is_overfit ? 'bg-red-50 border-red-200' : 'bg-green-50 border-green-200'}`}>
            <div className="flex items-center gap-2">
              {splitResults.comparison.is_overfit ? (
                <TrendingDown className="h-5 w-5 text-red-600" />
              ) : (
                <TrendingUp className="h-5 w-5 text-green-600" />
              )}
              <span className={`font-bold ${splitResults.comparison.is_overfit ? 'text-red-600' : 'text-green-600'}`}>
                {splitResults.comparison.status}
              </span>
              {splitResults.comparison.validation_reliability && (
                <span className="text-sm text-muted-foreground ml-2">
                  (신뢰도: {splitResults.comparison.validation_reliability})
                </span>
              )}
            </div>
            {splitResults.comparison.warnings && splitResults.comparison.warnings.length > 0 && (
              <div className="mt-2 text-sm text-amber-600">
                {splitResults.comparison.warnings.map((w, i) => (
                  <div key={i}>⚠️ {w}</div>
                ))}
              </div>
            )}
          </div>
          
          {/* 3개 카드 */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Train 카드 */}
            <div className="bg-card rounded-lg border-2 border-blue-200 p-6">
              <div className="flex items-center gap-2 mb-4">
                <Activity className="h-5 w-5 text-blue-600" />
                <h4 className="text-lg font-bold text-blue-600">Train (70%)</h4>
              </div>
              <p className="text-xs text-muted-foreground mb-3">
                {splitResults.periods.train.start} ~ {splitResults.periods.train.end}
                <span className="ml-1">({splitResults.periods.train.days}일)</span>
              </p>
              <div className="space-y-2">
                <div className="flex justify-between">
                  <span className="text-sm text-muted-foreground">CAGR</span>
                  <span className="font-bold text-green-600">{splitResults.train.cagr.toFixed(2)}%</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm text-muted-foreground">Sharpe</span>
                  <span className="font-bold">{splitResults.train.sharpe_ratio.toFixed(2)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm text-muted-foreground">MDD</span>
                  <span className="font-bold text-red-600">{splitResults.train.max_drawdown.toFixed(2)}%</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm text-muted-foreground">거래</span>
                  <span className="font-medium">{splitResults.train.num_trades}회</span>
                </div>
              </div>
            </div>
            
            {/* Validation 카드 (있는 경우) */}
            {splitResults.val && splitResults.periods.val && (
              <div className="bg-card rounded-lg border-2 border-amber-200 p-6">
                <div className="flex items-center gap-2 mb-4">
                  <Activity className="h-5 w-5 text-amber-600" />
                  <h4 className="text-lg font-bold text-amber-600">Validation (15%)</h4>
                </div>
                <p className="text-xs text-muted-foreground mb-3">
                  {splitResults.periods.val.start} ~ {splitResults.periods.val.end}
                  <span className="ml-1">({splitResults.periods.val.days}일)</span>
                </p>
                <div className="space-y-2">
                  <div className="flex justify-between">
                    <span className="text-sm text-muted-foreground">CAGR</span>
                    <span className="font-bold text-green-600">{splitResults.val.cagr.toFixed(2)}%</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-sm text-muted-foreground">Sharpe</span>
                    <span className="font-bold">{splitResults.val.sharpe_ratio.toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-sm text-muted-foreground">MDD</span>
                    <span className="font-bold text-red-600">{splitResults.val.max_drawdown.toFixed(2)}%</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-sm text-muted-foreground">거래</span>
                    <span className="font-medium">{splitResults.val.num_trades}회</span>
                  </div>
                </div>
              </div>
            )}
            
            {/* Test 카드 */}
            <div className="bg-card rounded-lg border-2 border-green-200 p-6">
              <div className="flex items-center gap-2 mb-4">
                <Activity className="h-5 w-5 text-green-600" />
                <h4 className="text-lg font-bold text-green-600">Test ({splitResults.val ? '15%' : '30%'})</h4>
              </div>
              <p className="text-xs text-muted-foreground mb-3">
                {splitResults.periods.test.start} ~ {splitResults.periods.test.end}
                <span className="ml-1">({splitResults.periods.test.days}일)</span>
              </p>
              <div className="space-y-2">
                <div className="flex justify-between">
                  <span className="text-sm text-muted-foreground">CAGR</span>
                  <span className="font-bold text-green-600">{splitResults.test.cagr.toFixed(2)}%</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm text-muted-foreground">Sharpe</span>
                  <span className="font-bold">{splitResults.test.sharpe_ratio.toFixed(2)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm text-muted-foreground">MDD</span>
                  <span className="font-bold text-red-600">{splitResults.test.max_drawdown.toFixed(2)}%</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm text-muted-foreground">거래</span>
                  <span className="font-medium">{splitResults.test.num_trades}회</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 기존 상세 정보 (분할 결과 없을 때) */}
      {!splitResults && results[0] && (
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

      {/* 히스토리 - 항상 표시 */}
      <div className="bg-card rounded-lg border p-6">
        <h3 className="text-xl font-bold mb-4">백테스트 히스토리</h3>
        <HistoryTable
          items={history}
          metricColumns={[
            { key: 'cagr', label: 'CAGR', format: (v) => `${v.toFixed(2)}%` },
            { key: 'sharpe', label: 'Sharpe', format: (v) => v.toFixed(2) },
            { key: 'mdd', label: 'MDD', format: (v) => `${v.toFixed(2)}%` },
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
          title="백테스트 파라미터 설정"
          fields={[
            { name: 'start_date', label: '시작일', type: 'date', value: parameters.start_date || '2022-01-01' },
            { name: 'end_date', label: '종료일', type: 'date', value: parameters.end_date || new Date().toISOString().split('T')[0] },
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
          history={history}
          historyMetricColumns={[
            { key: 'cagr', label: 'CAGR', format: (v) => `${v.toFixed(2)}%` },
            { key: 'sharpe', label: 'Sharpe', format: (v) => v.toFixed(2) },
            { key: 'mdd', label: 'MDD', format: (v) => `${v.toFixed(2)}%` },
          ]}
          onSave={handleSaveParameters}
          onApplyPreset={handleApplyPreset}
          onSelectHistory={handleSelectHistory}
        />
      )}

      {/* 비교 차트 */}
      <ComparisonChart
        isOpen={showComparison}
        onClose={() => setShowComparison(false)}
        items={comparisonItems}
        metricColumns={[
          { key: 'cagr', label: 'CAGR', format: (v) => `${v.toFixed(2)}%` },
          { key: 'sharpe', label: 'Sharpe', format: (v) => v.toFixed(2) },
          { key: 'mdd', label: 'MDD', format: (v) => `${v.toFixed(2)}%` },
        ]}
        title="백테스트 결과 비교"
      />

      {/* AI 프롬프트 모달 */}
      <AIPromptModal
        isOpen={showPrompt}
        onClose={() => setShowPrompt(false)}
        prompt={prompt}
        title={selectedHistoryItem 
          ? `백테스트 결과 - AI 질문 (${new Date(selectedHistoryItem.timestamp).toLocaleDateString('ko-KR')} 실행)`
          : "백테스트 결과 - AI 질문 (최신)"
        }
      />
    </div>
  );
}
