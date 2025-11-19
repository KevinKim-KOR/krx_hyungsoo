/**
 * AI 프롬프트 생성 유틸리티
 * ChatGPT, Gemini 등에 질의할 수 있는 구조화된 프롬프트 생성
 */

import type { PortfolioOptimization, BacktestResult, MLModelInfo, LookbackAnalysis, LookbackResult } from '../types';

/**
 * 숫자를 한국 원화 형식으로 포맷
 */
function formatCurrency(value: number): string {
  return new Intl.NumberFormat('ko-KR').format(value);
}

/**
 * 포트폴리오 최적화 결과 프롬프트 생성
 */
export function generatePortfolioPrompt(data: PortfolioOptimization): string {
  const weightsText = Object.entries(data.weights)
    .sort(([, a], [, b]) => b - a)
    .map(([code, weight], i) => `${i + 1}. ${code}: ${(weight * 100).toFixed(1)}%`)
    .join('\n');

  let discreteText = '';
  if (data.discrete_allocation) {
    const allocationText = Object.entries(data.discrete_allocation.allocation)
      .map(([code, shares]) => `- ${code}: ${shares}주`)
      .join('\n');
    discreteText = `

## 이산 배분 (실제 매수)
${allocationText}
- 잔액: ₩${formatCurrency(data.discrete_allocation.leftover)}
- 총 투자액: ₩${formatCurrency(data.discrete_allocation.total_value)}`;
  }

  return `# 포트폴리오 최적화 결과 검토

## 분석 정보
- 분석 일시: ${data.timestamp}
- 최적화 방법: ${data.method === 'max_sharpe' ? 'Sharpe Ratio 최대화' : data.method}

## 최적화 결과
- 기대 수익률: ${(data.expected_return * 100).toFixed(1)}% (연율화)
- 변동성: ${(data.volatility * 100).toFixed(1)}% (연율화)
- Sharpe Ratio: ${data.sharpe_ratio.toFixed(2)}

## 종목별 비중
${weightsText}
${discreteText}

## 질문
다음 사항에 대해 분석해주세요:

1. **포트폴리오 구성 평가**
   - 이 포트폴리오 구성이 적절한가요?
   - 리스크 분산이 잘 되어 있나요?
   - 특정 종목 비중이 과도하지 않나요?

2. **성과 지표 해석**
   - Sharpe Ratio ${data.sharpe_ratio.toFixed(2)}는 좋은 수준인가요?
   - 기대 수익률 ${(data.expected_return * 100).toFixed(1)}%와 변동성 ${(data.volatility * 100).toFixed(1)}%의 균형은 적절한가요?

3. **개선 방안**
   - 더 나은 종목 조합이 있을까요?
   - 리밸런싱 주기는 어떻게 설정해야 하나요?
   - 시장 상황 변화 시 대응 전략은?

4. **리스크 관리**
   - 현재 시장 상황에서 이 전략의 주요 리스크는?
   - 손절 라인은 어떻게 설정해야 하나요?
   - 방어적 포지션 조정이 필요한가요?

5. **실전 투자**
   - 실제로 투자해도 될까요?
   - 투자 시 주의해야 할 점은?
   - 초기 투자 금액 대비 적절한 비중인가요?
`;
}

/**
 * 백테스트 결과 프롬프트 생성
 */
export function generateBacktestPrompt(data: BacktestResult): string {
  const cagr = data.cagr ?? 0;
  const sharpe = data.sharpe_ratio ?? 0;
  const mdd = data.max_drawdown ?? 0;
  const totalReturn = data.total_return ?? 0;
  const trades = data.total_trades ?? 0;

  return `# 백테스트 결과 검토

## 백테스트 정보
- 전략: ${data.strategy}
- 기간: ${data.start_date} ~ ${data.end_date}

## 성과 지표
- CAGR: ${cagr.toFixed(2)}%
- Sharpe Ratio: ${sharpe.toFixed(2)}
- Max Drawdown: ${mdd.toFixed(2)}%
- 총 수익률: ${totalReturn.toFixed(2)}%
- 총 거래 횟수: ${trades}회

## 질문
다음 사항에 대해 분석해주세요:

1. **백테스트 신뢰성**
   - 이 백테스트 결과가 신뢰할 만한가요?
   - 과최적화(overfitting) 징후가 있나요?
   - 실전 투자 시 예상 성과는?

2. **성과 평가**
   - CAGR ${cagr.toFixed(2)}%는 좋은 수준인가요?
   - Sharpe Ratio ${sharpe.toFixed(2)}는 어떻게 해석해야 하나요?
   - MDD ${mdd.toFixed(2)}%는 적절한 수준인가요?

3. **거래 분석**
   - 총 거래 횟수 ${trades}회가 과도하지 않나요?
   - 거래 비용을 고려하면 실제 수익률은?
   - 최적 거래 빈도는?

4. **리스크 관리**
   - 최대 손실 구간은 언제였나요?
   - 연속 손실 시 대응 방안은?
   - 리스크 조정 수익률을 개선할 방법은?

5. **전략 개선**
   - 이 전략의 강점과 약점은?
   - 개선할 수 있는 부분은?
   - 다른 전략과 비교하면?
`;
}

/**
 * ML 모델 학습 결과 프롬프트 생성
 */
export function generateMLPrompt(data: MLModelInfo): string {
  const featuresText = data.feature_importance
    .slice(0, 10)
    .map((f, i) => `${i + 1}. ${f.feature}: ${f.importance.toFixed(3)}`)
    .join('\n');

  const overfitting = data.train_score - data.test_score > 0.15;

  return `# ML 모델 학습 결과 검토

## 모델 정보
- 모델 타입: ${data.model_type}
- 학습 일시: ${data.timestamp}

## 성능 지표
- Train R²: ${data.train_score.toFixed(3)}
- Test R²: ${data.test_score.toFixed(3)}
- 특징 개수: ${data.n_features}개
${overfitting ? '\n⚠️ **과적합 경고**: Train과 Test 성능 차이가 큽니다!' : ''}

## Feature Importance (Top 10)
${featuresText}

## 질문
다음 사항에 대해 분석해주세요:

1. **모델 성능 평가**
   - Test R² ${data.test_score.toFixed(3)}는 좋은 성능인가요?
   - Train R² ${data.train_score.toFixed(3)}와 Test R² ${data.test_score.toFixed(3)}의 차이는 정상인가요?
   ${overfitting ? '- 과적합을 해결할 방법은?' : ''}

2. **Feature 분석**
   - 상위 Feature들이 의미하는 바는?
   - 예상과 다른 Feature가 있나요?
   - 추가하면 좋을 Feature는?

3. **모델 개선**
   - 성능을 개선할 수 있는 방법은?
   - 다른 모델 알고리즘을 시도해볼까요?
   - 하이퍼파라미터 튜닝이 필요한가요?

4. **실전 적용**
   - 이 모델을 실전 투자에 사용해도 될까요?
   - 모델 예측의 신뢰도는?
   - 모델 업데이트 주기는?

5. **리스크**
   - 모델 실패 시나리오는?
   - 시장 변화에 대한 적응력은?
   - 백테스트와 실전의 차이는?
`;
}

/**
 * 룩백 분석 결과 프롬프트 생성
 */
export function generateLookbackPrompt(data: LookbackAnalysis): string {
  const rebalancesText = data.results
    .map((r: LookbackResult, i: number) => `
### ${i + 1}차 (${r.rebalance_date})
- 수익률: ${(r.return * 100).toFixed(2)}%
- Sharpe: ${r.sharpe_ratio.toFixed(2)}
- 변동성: ${(r.volatility * 100).toFixed(2)}%
- 주요 종목: ${Object.entries(r.weights)
      .sort(([, a], [, b]) => (b as number) - (a as number))
      .slice(0, 3)
      .map(([code, weight]) => `${code} (${((weight as number) * 100).toFixed(0)}%)`)
      .join(', ')}`)
    .join('\n');

  const winRate = (data.summary.win_rate * 100).toFixed(1);
  const avgReturn = (data.summary.avg_return * 100).toFixed(2);

  return `# 룩백 분석 결과 검토

## 분석 정보
- 분석 일시: ${data.timestamp}
- 최적화 방법: ${data.method}

## 요약 통계
- 총 리밸런싱: ${data.summary.total_rebalances}회
- 평균 수익률: ${avgReturn}%
- 평균 Sharpe: ${data.summary.avg_sharpe.toFixed(2)}
- 승률: ${winRate}% (${Math.round(data.summary.total_rebalances * data.summary.win_rate)}승 ${Math.round(data.summary.total_rebalances * (1 - data.summary.win_rate))}패)

## 리밸런싱 상세
${rebalancesText}

## 질문
다음 사항에 대해 분석해주세요:

1. **전략 평가**
   - 리밸런싱 전략이 적절한가요?
   - 승률 ${winRate}%는 좋은 수준인가요?
   - 평균 수익률 ${avgReturn}%는 만족스러운가요?

2. **패턴 분석**
   - 리밸런싱 시점별 특징은?
   - 수익률이 높았던 시기의 공통점은?
   - 손실이 발생한 시기의 원인은?

3. **종목 선택**
   - 자주 선택되는 종목의 특징은?
   - 종목 비중 변화의 의미는?
   - 더 나은 종목 조합이 있을까요?

4. **최적화**
   - 리밸런싱 주기를 조정해야 하나요?
   - 최적화 방법을 변경하면 어떨까요?
   - 거래 비용을 고려하면 실제 수익률은?

5. **다음 액션**
   - 다음 리밸런싱 시점은 언제가 좋을까요?
   - 현재 시장 상황에서 주의할 점은?
   - 이 전략을 계속 사용해도 될까요?
`;
}

/**
 * 프롬프트에 추가 컨텍스트 추가
 */
export function addContext(prompt: string, context?: {
  marketCondition?: string;
  userProfile?: string;
  previousResults?: string;
}): string {
  let enhanced = prompt;

  if (context?.marketCondition) {
    enhanced += `\n\n## 현재 시장 상황 (참고)\n${context.marketCondition}`;
  }

  if (context?.userProfile) {
    enhanced += `\n\n## 투자자 프로필\n${context.userProfile}`;
  }

  if (context?.previousResults) {
    enhanced += `\n\n## 이전 결과와 비교\n${context.previousResults}`;
  }

  return enhanced;
}
