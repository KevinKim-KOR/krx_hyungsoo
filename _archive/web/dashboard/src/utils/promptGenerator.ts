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
 * 백테스트 결과 프롬프트 생성 (개선된 버전)
 */
export function generateBacktestPrompt(data: BacktestResult): string {
  const cagr = data.cagr ?? 0;
  const sharpe = data.sharpe_ratio ?? 0;
  const mdd = data.max_drawdown ?? 0;
  const calmar = data.calmar_ratio ?? 0;
  const volatility = data.volatility ?? 0;
  const totalReturn = data.total_return ?? 0;
  const trades = data.total_trades ?? 0;
  const sellTrades = data.sell_trades ?? 0;
  const tradeWinRate = data.trade_win_rate ?? 0;
  const avgWin = data.avg_win ?? 0;
  const avgLoss = data.avg_loss ?? 0;
  const totalCosts = data.total_costs ?? 0;
  const costRatio = data.cost_ratio ?? 0;
  const years = data.years ?? 0;

  // 손익비 계산
  const profitLossRatio = avgLoss !== 0 ? Math.abs(avgWin / avgLoss) : 0;

  return `# 백테스트 결과 검토

## 백테스트 정보
- 전략: ${data.strategy}
- 기간: ${data.start_date} ~ ${data.end_date} (${years.toFixed(2)}년)
- 총 수익률: ${totalReturn.toFixed(2)}%

## 핵심 성과 지표
| 지표 | 값 | 해석 |
|------|-----|------|
| CAGR | ${cagr.toFixed(2)}% | 연평균 복리 수익률 |
| Sharpe Ratio | ${sharpe.toFixed(2)} | 위험 대비 수익 (>1 양호, >2 우수) |
| MDD | ${mdd.toFixed(2)}% | 최대 낙폭 |
| Calmar Ratio | ${calmar.toFixed(2)} | CAGR/MDD (>1 양호) |
| 변동성 | ${volatility.toFixed(2)}% | 연율화 표준편차 |

## 거래 분석
| 항목 | 값 |
|------|-----|
| 총 거래 | ${trades}회 |
| 매도 거래 | ${sellTrades}회 |
| 거래 승률 | ${tradeWinRate.toFixed(1)}% |
| 평균 수익 | ₩${formatCurrency(avgWin)} |
| 평균 손실 | ₩${formatCurrency(Math.abs(avgLoss))} |
| 손익비 | ${profitLossRatio.toFixed(2)} |

## 비용 분석
- 총 거래비용: ₩${formatCurrency(totalCosts)}
- 비용 비율: ${costRatio.toFixed(2)}% (초기 자본 대비)

## 질문
다음 사항에 대해 분석해주세요:

### 1. 성과 평가
- CAGR ${cagr.toFixed(2)}%와 MDD ${mdd.toFixed(2)}%의 균형은 적절한가요?
- Sharpe ${sharpe.toFixed(2)}, Calmar ${calmar.toFixed(2)}는 좋은 수준인가요?
- 변동성 ${volatility.toFixed(2)}%는 감당할 만한 수준인가요?

### 2. 거래 효율성
- 거래 승률 ${tradeWinRate.toFixed(1)}%와 손익비 ${profitLossRatio.toFixed(2)}의 조합은 어떤가요?
- 거래 빈도가 적절한가요? (연간 ${(trades / years).toFixed(0)}회)
- 비용 ${costRatio.toFixed(2)}%가 수익에 미치는 영향은?

### 3. 리스크 관리
- MDD ${mdd.toFixed(2)}%를 줄이기 위한 방법은?
- 연속 손실 시 대응 전략은?
- 추가해야 할 방어 메커니즘이 있나요?

### 4. 개선 제안
- 이 전략의 강점과 약점은?
- 어떤 시장 상황에서 이 전략이 취약한가요?
- 추가로 고려해야 할 변수나 지표가 있나요?
`;
}

/**
 * 백테스트 결과 + Train/Val/Test 분할 결과 + 파라미터 정보 포함 프롬프트 생성
 */
export function generateBacktestPromptWithSplit(
  historyItem: any,
  splitResults: any,
  parameters: any
): string {
  const metrics = historyItem.metrics || historyItem;
  const params = historyItem.parameters || parameters || {};
  
  const cagr = metrics.cagr ?? 0;
  const sharpe = metrics.sharpe ?? metrics.sharpe_ratio ?? 0;
  const mdd = metrics.mdd ?? metrics.max_drawdown ?? 0;
  const totalReturn = metrics.total_return ?? 0;
  const trades = metrics.total_trades ?? metrics.num_trades ?? 0;

  // 파라미터 섹션 생성
  const paramEntries = Object.entries(params);
  const paramText = paramEntries.length > 0
    ? paramEntries.map(([key, value]) => `- ${key}: ${value}`).join('\n')
    : '- 파라미터 정보 없음';

  // Train/Val/Test 분할 결과 섹션 생성
  let splitText = '';
  if (splitResults && splitResults.train) {
    splitText = `
## Train / Validation / Test 분할 결과

### Train (학습 데이터)
- 기간: ${splitResults.periods?.train?.start || '-'} ~ ${splitResults.periods?.train?.end || '-'} (${splitResults.periods?.train?.days || '-'}일)
- CAGR: ${splitResults.train.cagr?.toFixed(2) || '-'}%
- Sharpe: ${splitResults.train.sharpe_ratio?.toFixed(2) || '-'}
- MDD: ${splitResults.train.max_drawdown?.toFixed(2) || '-'}%
- 거래: ${splitResults.train.num_trades || '-'}회
`;

    if (splitResults.val) {
      splitText += `
### Validation (검증 데이터)
- 기간: ${splitResults.periods?.val?.start || '-'} ~ ${splitResults.periods?.val?.end || '-'} (${splitResults.periods?.val?.days || '-'}일)
- CAGR: ${splitResults.val.cagr?.toFixed(2) || '-'}%
- Sharpe: ${splitResults.val.sharpe_ratio?.toFixed(2) || '-'}
- MDD: ${splitResults.val.max_drawdown?.toFixed(2) || '-'}%
- 거래: ${splitResults.val.num_trades || '-'}회
`;
    }

    splitText += `
### Test (테스트 데이터)
- 기간: ${splitResults.periods?.test?.start || '-'} ~ ${splitResults.periods?.test?.end || '-'} (${splitResults.periods?.test?.days || '-'}일)
- CAGR: ${splitResults.test.cagr?.toFixed(2) || '-'}%
- Sharpe: ${splitResults.test.sharpe_ratio?.toFixed(2) || '-'}
- MDD: ${splitResults.test.max_drawdown?.toFixed(2) || '-'}%
- 거래: ${splitResults.test.num_trades || '-'}회

### 과적합 판정
- 상태: ${splitResults.comparison?.status || '-'}
- 과적합 여부: ${splitResults.comparison?.is_overfit ? '예 (주의 필요)' : '아니오'}
- 신뢰도: ${splitResults.comparison?.validation_reliability || '-'}
${splitResults.comparison?.warnings?.length > 0 ? `- 경고: ${splitResults.comparison.warnings.join(', ')}` : ''}
`;
  }

  return `# 백테스트 결과 검토

## 실행 정보
- 실행 시간: ${historyItem.timestamp ? new Date(historyItem.timestamp).toLocaleString('ko-KR') : '-'}
- 상태: ${historyItem.status || 'success'}

## 사용된 파라미터
${paramText}

## 전체 성과 지표
- CAGR: ${cagr.toFixed(2)}%
- Sharpe Ratio: ${sharpe.toFixed(2)}
- Max Drawdown: ${mdd.toFixed(2)}%
- 총 수익률: ${totalReturn.toFixed(2)}%
- 총 거래 횟수: ${trades}회
${splitText}
## 질문
다음 사항에 대해 분석해주세요:

1. **과적합 분석**
   - Train/Val/Test 결과를 보면 과적합 징후가 있나요?
   - Train에서 Test로 갈수록 성과가 어떻게 변하나요?
   - 이 전략을 실전에 사용해도 될까요?

2. **파라미터 평가**
   - 현재 사용된 파라미터가 적절한가요?
   - 개선이 필요한 파라미터가 있나요?
   - 파라미터 민감도는 어떤가요?

3. **성과 평가**
   - CAGR ${cagr.toFixed(2)}%는 좋은 수준인가요?
   - Sharpe Ratio ${sharpe.toFixed(2)}는 어떻게 해석해야 하나요?
   - MDD ${mdd.toFixed(2)}%는 적절한 수준인가요?

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
 * 손실 구간 분석 프롬프트 생성
 */
export interface LossAnalysisData {
  loss_start_date: string;
  loss_end_date: string;
  loss_pct: number;
  kospi_change?: number;
  holdings?: string[];
  params?: Record<string, any>;
}

export function generateLossAnalysisPrompt(data: LossAnalysisData): string {
  const holdingsText = data.holdings?.length 
    ? data.holdings.map((h, i) => `${i + 1}. ${h}`).join('\n')
    : '- 정보 없음';

  const paramsText = data.params 
    ? Object.entries(data.params).map(([k, v]) => `- ${k}: ${v}`).join('\n')
    : '- 정보 없음';

  return `# 손실 구간 분석 요청

## 손실 발생 기간
- 시작: ${data.loss_start_date}
- 종료: ${data.loss_end_date}
- 손실률: ${data.loss_pct.toFixed(2)}%

## 해당 기간 시장 상황
- KOSPI 변동: ${data.kospi_change?.toFixed(2) ?? '정보 없음'}%

## 사용된 파라미터
${paramsText}

## 보유 종목
${holdingsText}

## 질문
다음 사항에 대해 분석해주세요:

### 1. 손실 원인 분석
- 이 손실의 주요 원인은 무엇으로 보이나요?
- 시장 전체 하락인가요, 아니면 전략 문제인가요?
- 특정 종목이 손실을 키웠나요?

### 2. 사전 감지 가능성
- 어떤 지표를 모니터링했다면 손실을 줄일 수 있었을까요?
- 손실 전 경고 신호가 있었나요?
- 조기 청산 타이밍은 언제였어야 하나요?

### 3. 방어 메커니즘 제안
- 새로운 방어 메커니즘으로 어떤 것을 제안하시나요?
- 손절 기준을 어떻게 조정해야 하나요?
- 포지션 비중 조절이 필요했나요?

### 4. 파라미터 조정
- 현재 파라미터 중 문제가 있는 것은?
- 어떤 파라미터를 추가하면 좋을까요?
- 시장 상황별로 다른 파라미터를 사용해야 하나요?
`;
}

/**
 * 새 변수 제안 요청 프롬프트 생성
 */
export interface VariableSuggestionData {
  current_variables: string[];
  problem_description: string;
  recent_performance?: {
    cagr: number;
    sharpe: number;
    mdd: number;
  };
}

export function generateVariableSuggestionPrompt(data: VariableSuggestionData): string {
  const currentVarsText = data.current_variables
    .map((v, i) => `${i + 1}. ${v}`)
    .join('\n');

  const perfText = data.recent_performance
    ? `- CAGR: ${data.recent_performance.cagr.toFixed(2)}%
- Sharpe: ${data.recent_performance.sharpe.toFixed(2)}
- MDD: ${data.recent_performance.mdd.toFixed(2)}%`
    : '- 정보 없음';

  return `# 새 변수 제안 요청

## 현재 사용 중인 변수
${currentVarsText}

## 최근 성과
${perfText}

## 발견된 문제점
${data.problem_description}

## 질문
다음 사항에 대해 제안해주세요:

### 1. 새 변수 제안
- 이 문제를 해결하기 위해 어떤 새 변수를 추가할 수 있을까요?
- 해당 변수의 계산 방법은?
- 적정 임계값은 어떻게 설정해야 하나요?

### 2. 변수 상호작용
- 기존 변수와 어떻게 조합해야 하나요?
- 변수 간 우선순위는?
- 충돌 시 어떻게 처리해야 하나요?

### 3. 구현 고려사항
- 이 변수를 계산하는 데 필요한 데이터는?
- 계산 복잡도는 어느 정도인가요?
- 실시간 적용이 가능한가요?

### 4. 검증 방법
- 변수 추가 효과를 어떻게 검증해야 하나요?
- 과적합 위험은 없나요?
- 백테스트 외에 추가 검증이 필요한가요?

### 5. 대안
- 변수 추가 대신 다른 접근법이 있나요?
- 기존 변수의 파라미터 조정으로 해결 가능한가요?
- 전략 자체를 변경해야 하나요?
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
