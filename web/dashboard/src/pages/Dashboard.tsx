import { AlertCircle } from 'lucide-react';
import { useApi } from '../hooks/useApi';
import { apiClient } from '../api/client';
import type { DashboardSummary, RecentAnalysis } from '../types';

export default function Dashboard() {
  // API 호출
  const { data: summary, loading: summaryLoading, error: summaryError } = useApi<DashboardSummary>(
    () => apiClient.getDashboardSummary(),
    []
  );

  const { data: recentAnalyses, loading: analysesLoading, error: analysesError } = useApi<RecentAnalysis[]>(
    () => apiClient.getRecentAnalyses(),
    []
  );

  // 로딩 상태
  if (summaryLoading || analysesLoading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">데이터를 불러오는 중...</p>
        </div>
      </div>
    );
  }

  // 에러 상태
  if (summaryError || analysesError) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center">
          <AlertCircle className="h-12 w-12 text-red-500 mx-auto mb-4" />
          <p className="text-red-600 mb-2">데이터를 불러오는데 실패했습니다</p>
          <p className="text-sm text-gray-500">{summaryError || analysesError}</p>
          <p className="text-sm text-gray-500 mt-2">FastAPI 서버가 실행 중인지 확인하세요 (포트 8000)</p>
        </div>
      </div>
    );
  }

  // 데이터가 없는 경우
  if (!summary) {
    return (
      <div className="flex items-center justify-center h-96">
        <p className="text-gray-600">데이터가 없습니다</p>
      </div>
    );
  }

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('ko-KR').format(value);
  };

  const formatPercent = (value: number) => {
    return `${value > 0 ? '+' : ''}${value.toFixed(2)}%`;
  };

  return (
    <div className="space-y-6">
      <h2 className="text-3xl font-bold">대시보드</h2>
      
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* 총 포트폴리오 가치 */}
        <div className="p-6 bg-card rounded-lg border">
          <h3 className="text-sm font-medium text-muted-foreground">총 포트폴리오 가치</h3>
          <p className="text-2xl font-bold mt-2">₩{formatCurrency(summary.portfolio_value)}</p>
          <p className={`text-sm mt-1 ${summary.portfolio_change >= 0 ? 'text-green-600' : 'text-red-600'}`}>
            {formatPercent(summary.portfolio_change)}
          </p>
        </div>

        {/* Sharpe Ratio */}
        <div className="p-6 bg-card rounded-lg border">
          <h3 className="text-sm font-medium text-muted-foreground">Sharpe Ratio</h3>
          <p className="text-2xl font-bold mt-2">{summary.sharpe_ratio.toFixed(2)}</p>
          <p className="text-sm text-muted-foreground mt-1">최적화 결과</p>
        </div>

        {/* 변동성 */}
        <div className="p-6 bg-card rounded-lg border">
          <h3 className="text-sm font-medium text-muted-foreground">변동성</h3>
          <p className="text-2xl font-bold mt-2">{(summary.volatility * 100).toFixed(1)}%</p>
          <p className="text-sm text-muted-foreground mt-1">연율화</p>
        </div>

        {/* 기대 수익률 */}
        <div className="p-6 bg-card rounded-lg border">
          <h3 className="text-sm font-medium text-muted-foreground">기대 수익률</h3>
          <p className="text-2xl font-bold mt-2">{(summary.expected_return * 100).toFixed(1)}%</p>
          <p className="text-sm text-muted-foreground mt-1">연율화</p>
        </div>
      </div>

      {/* 최근 분석 결과 */}
      <div className="bg-card rounded-lg border p-6">
        <h3 className="text-xl font-bold mb-4">최근 분석 결과</h3>
        {recentAnalyses && recentAnalyses.length > 0 ? (
          <div className="space-y-4">
            {recentAnalyses.map((analysis, index) => (
              <div key={index} className="flex items-center justify-between p-4 bg-secondary rounded-lg">
                <div>
                  <p className="font-medium">{analysis.title}</p>
                  <p className="text-sm text-muted-foreground">{analysis.timestamp}</p>
                  <p className="text-sm text-gray-600 mt-1">{analysis.summary}</p>
                </div>
                <span className="px-3 py-1 bg-green-100 text-green-800 rounded-full text-sm">완료</span>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-gray-500">최근 분석 결과가 없습니다</p>
        )}
      </div>
    </div>
  );
}
