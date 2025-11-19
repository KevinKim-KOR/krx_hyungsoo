# AI 프롬프트 생성 기능

**작성일**: 2025-11-19  
**목적**: 분석 결과를 ChatGPT/Gemini에 질의할 수 있는 프롬프트 자동 생성

---

## 📋 개요

각 분석 결과 페이지에 "AI에게 질문하기" 버튼을 추가하여, 결과를 ChatGPT나 Gemini에 복사하여 질의할 수 있는 구조화된 프롬프트를 생성합니다.

---

## 🎯 기능 설계

### 1. 프롬프트 생성 버튼

**위치**: 각 분석 결과 페이지 상단
- Portfolio 페이지
- Backtest 페이지
- MLModel 페이지
- Lookback 페이지

**버튼 디자인**:
```
[💬 AI에게 질문하기]
```

**동작**:
1. 버튼 클릭
2. 모달 창 열림
3. 프롬프트 자동 생성
4. 클립보드 복사 버튼
5. ChatGPT/Gemini 링크

---

### 2. 프롬프트 구조

#### 기본 템플릿
```
# 투자 분석 결과 검토 요청

## 분석 유형
{분석 유형}

## 분석 일시
{타임스탬프}

## 주요 지표
{핵심 지표 요약}

## 상세 결과
{상세 데이터}

## 질문
다음 사항에 대해 분석해주세요:
1. 이 결과가 의미하는 바는 무엇인가요?
2. 개선할 수 있는 부분이 있나요?
3. 리스크 요인은 무엇인가요?
4. 다음 액션 아이템을 추천해주세요.
```

---

### 3. 페이지별 프롬프트

#### Portfolio (포트폴리오 최적화)

```markdown
# 포트폴리오 최적화 결과 검토

## 분석 정보
- 분석 일시: 2025-11-19 23:15:30
- 최적화 방법: Sharpe Ratio 최대화
- 초기 자본: ₩10,000,000

## 최적화 결과
- 기대 수익률: 29.9% (연율화)
- 변동성: 18.1% (연율화)
- Sharpe Ratio: 1.49

## 종목별 비중
1. 069500 (KODEX 200): 40.0%
2. 091160 (KODEX 반도체): 20.0%
3. 133690 (KOSEF 국고채): 40.0%

## 이산 배분 (실제 매수)
- 069500: 120주 (₩4,200,000)
- 091160: 63주 (₩1,890,000)
- 133690: 33주 (₩3,300,000)
- 잔액: ₩21,441

## 질문
1. 이 포트폴리오 구성이 적절한가요?
2. 국고채 비중 40%가 과도하지 않나요?
3. 더 나은 종목 조합이 있을까요?
4. 리밸런싱 주기는 어떻게 설정해야 하나요?
5. 현재 시장 상황에서 이 전략의 리스크는?
```

---

#### Backtest (백테스트)

```markdown
# 백테스트 결과 검토

## 백테스트 정보
- 기간: 2022-01-01 ~ 2025-11-19
- 전략: 하이브리드 레짐 전략
- 초기 자본: ₩10,000,000

## 성과 지표
- CAGR: 27.05%
- Sharpe Ratio: 1.51
- Max Drawdown: -19.92%
- 총 수익률: 96.80%
- 거래 횟수: 1,406회

## 레짐 통계
- 상승장: 232일 (48.2%)
- 중립장: 135일 (28.1%)
- 하락장: 114일 (23.7%)
- 레짐 변경: 5회

## 월별 수익률
- 2022: +15.2%
- 2023: +8.7%
- 2024: +32.1%
- 2025 (YTD): +12.3%

## 질문
1. 이 백테스트 결과가 신뢰할 만한가요?
2. MDD -19.92%는 적절한 수준인가요?
3. 레짐 변경이 5회밖에 안 된 것이 정상인가요?
4. 거래 횟수 1,406회가 과도하지 않나요?
5. 실전 투자 시 주의할 점은?
```

---

#### MLModel (머신러닝)

```markdown
# ML 모델 학습 결과 검토

## 모델 정보
- 모델 타입: XGBoost
- 태스크: Regression
- 학습 일시: 2025-11-19 22:30:15

## 성능 지표
- Train R²: 0.85
- Test R²: 0.72
- Train RMSE: 0.023
- Test RMSE: 0.031

## Feature Importance (Top 10)
1. volume_ratio: 0.185
2. price_momentum_20: 0.142
3. rsi_14: 0.128
4. macd_signal: 0.095
5. bollinger_position: 0.087
6. atr_ratio: 0.076
7. obv_trend: 0.065
8. stoch_k: 0.058
9. cci_20: 0.047
10. williams_r: 0.042

## 학습 파라미터
- n_estimators: 100
- max_depth: 6
- learning_rate: 0.1
- subsample: 0.8

## 질문
1. Test R² 0.72는 좋은 성능인가요?
2. 과적합 징후가 있나요? (Train 0.85 vs Test 0.72)
3. Feature Importance가 의미하는 바는?
4. 모델을 개선할 수 있는 방법은?
5. 실전 투자에 사용해도 될까요?
```

---

#### Lookback (룩백 분석)

```markdown
# 룩백 분석 결과 검토

## 분석 정보
- 분석 기간: 120일
- 리밸런싱 주기: 30일
- 최적화 방법: Sharpe Ratio 최대화

## 요약 통계
- 총 리밸런싱: 4회
- 평균 수익률: +8.5%
- 평균 Sharpe: 1.32
- 승률: 75.0% (3승 1패)

## 리밸런싱 상세

### 1차 (2025-08-20)
- 수익률: +12.3%
- Sharpe: 1.45
- 주요 종목: KODEX 200 (45%), 반도체 (30%)

### 2차 (2025-09-20)
- 수익률: +6.8%
- Sharpe: 1.28
- 주요 종목: KODEX 200 (40%), 국고채 (35%)

### 3차 (2025-10-20)
- 수익률: +9.2%
- Sharpe: 1.38
- 주요 종목: 반도체 (50%), KODEX 200 (30%)

### 4차 (2025-11-19)
- 수익률: +5.7%
- Sharpe: 1.18
- 주요 종목: 국고채 (60%), KODEX 200 (25%)

## 질문
1. 리밸런싱 주기 30일이 적절한가요?
2. 승률 75%는 좋은 수준인가요?
3. 4차 리밸런싱에서 국고채 비중이 급증한 이유는?
4. 다음 리밸런싱 시점을 어떻게 결정해야 하나요?
5. 이 전략의 장단점은?
```

---

## 🛠️ 구현 방법

### 1. React 컴포넌트

**파일**: `web/dashboard/src/components/AIPromptModal.tsx`

```typescript
interface AIPromptModalProps {
  isOpen: boolean;
  onClose: () => void;
  prompt: string;
  title: string;
}

export function AIPromptModal({ isOpen, onClose, prompt, title }: AIPromptModalProps) {
  const [copied, setCopied] = useState(false);
  
  const handleCopy = () => {
    navigator.clipboard.writeText(prompt);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  
  const openChatGPT = () => {
    window.open('https://chat.openai.com/', '_blank');
  };
  
  const openGemini = () => {
    window.open('https://gemini.google.com/', '_blank');
  };
  
  return (
    <Modal isOpen={isOpen} onClose={onClose}>
      <h2>{title}</h2>
      
      <div className="prompt-preview">
        <pre>{prompt}</pre>
      </div>
      
      <div className="actions">
        <button onClick={handleCopy}>
          {copied ? '✅ 복사됨!' : '📋 클립보드에 복사'}
        </button>
        <button onClick={openChatGPT}>
          🤖 ChatGPT에서 열기
        </button>
        <button onClick={openGemini}>
          ✨ Gemini에서 열기
        </button>
      </div>
    </Modal>
  );
}
```

---

### 2. 프롬프트 생성 함수

**파일**: `web/dashboard/src/utils/promptGenerator.ts`

```typescript
export function generatePortfolioPrompt(data: PortfolioOptimization): string {
  return `# 포트폴리오 최적화 결과 검토

## 분석 정보
- 분석 일시: ${data.timestamp}
- 최적화 방법: ${data.method}
- 초기 자본: ₩${formatNumber(data.initial_capital)}

## 최적화 결과
- 기대 수익률: ${(data.expected_return * 100).toFixed(1)}% (연율화)
- 변동성: ${(data.volatility * 100).toFixed(1)}% (연율화)
- Sharpe Ratio: ${data.sharpe_ratio.toFixed(2)}

## 종목별 비중
${Object.entries(data.weights)
  .map(([code, weight], i) => `${i + 1}. ${code}: ${(weight * 100).toFixed(1)}%`)
  .join('\n')}

${data.discrete_allocation ? `
## 이산 배분 (실제 매수)
${Object.entries(data.discrete_allocation.allocation)
  .map(([code, shares]) => `- ${code}: ${shares}주`)
  .join('\n')}
- 잔액: ₩${formatNumber(data.discrete_allocation.leftover)}
` : ''}

## 질문
1. 이 포트폴리오 구성이 적절한가요?
2. 리스크 분산이 잘 되어 있나요?
3. 더 나은 종목 조합이 있을까요?
4. 리밸런싱 주기는 어떻게 설정해야 하나요?
5. 현재 시장 상황에서 이 전략의 리스크는?
`;
}

export function generateBacktestPrompt(data: BacktestResult): string {
  // 백테스트 프롬프트 생성
}

export function generateMLPrompt(data: MLModelInfo): string {
  // ML 프롬프트 생성
}

export function generateLookbackPrompt(data: LookbackAnalysis): string {
  // 룩백 프롬프트 생성
}
```

---

### 3. 페이지에 버튼 추가

**예시**: `Portfolio.tsx`

```typescript
export default function Portfolio() {
  const [showPrompt, setShowPrompt] = useState(false);
  const { data } = useApi<PortfolioOptimization>(...);
  
  const prompt = useMemo(() => {
    if (!data) return '';
    return generatePortfolioPrompt(data);
  }, [data]);
  
  return (
    <div>
      <div className="header">
        <h2>포트폴리오 최적화</h2>
        <button onClick={() => setShowPrompt(true)}>
          💬 AI에게 질문하기
        </button>
      </div>
      
      {/* 기존 내용 */}
      
      <AIPromptModal
        isOpen={showPrompt}
        onClose={() => setShowPrompt(false)}
        prompt={prompt}
        title="포트폴리오 최적화 결과 - AI 질문"
      />
    </div>
  );
}
```

---

## 📊 프롬프트 품질 개선

### 1. 컨텍스트 추가

**시장 상황**:
```markdown
## 현재 시장 상황 (참고)
- KOSPI: 2,450 (-1.2%)
- KOSDAQ: 850 (+0.5%)
- 달러/원: 1,320 (+0.3%)
- 금리: 3.5%
```

**사용자 프로필**:
```markdown
## 투자자 프로필
- 투자 성향: 중립적
- 투자 기간: 중장기 (1~3년)
- 리스크 허용도: 중간
- 목표 수익률: 연 20%
```

---

### 2. 비교 데이터

**이전 결과와 비교**:
```markdown
## 이전 결과와 비교
- 이전 Sharpe: 1.35 → 현재: 1.49 (+10.4%)
- 이전 변동성: 20.1% → 현재: 18.1% (-10.0%)
- 이전 수익률: 25.3% → 현재: 29.9% (+18.2%)

개선된 점:
- Sharpe Ratio 향상
- 변동성 감소
- 수익률 증가
```

---

### 3. 추천 질문 템플릿

**초보자용**:
```markdown
## 추천 질문 (초보자)
1. 이 결과를 어떻게 해석해야 하나요?
2. Sharpe Ratio 1.49가 좋은 건가요?
3. 변동성 18.1%는 높은 편인가요?
4. 실제로 투자해도 될까요?
5. 주의해야 할 점은 무엇인가요?
```

**중급자용**:
```markdown
## 추천 질문 (중급자)
1. 포트폴리오 구성의 논리적 근거는?
2. 리스크 조정 수익률을 개선할 방법은?
3. 시장 레짐 변화 시 대응 전략은?
4. 최적 리밸런싱 주기는?
5. 대안 전략과 비교하면?
```

**고급자용**:
```markdown
## 추천 질문 (고급자)
1. 포트폴리오 최적화 알고리즘의 한계는?
2. 블랙-리터만 모델 적용 가능성은?
3. 꼬리 위험(tail risk) 관리 방안은?
4. 거래 비용 및 슬리피지 고려 시 실제 성과는?
5. 다른 최적화 기법(CVaR, 로버스트 최적화) 비교는?
```

---

## 🎯 추가 기능

### 1. 프롬프트 템플릿 관리

**사용자 정의 템플릿**:
- 기본 템플릿
- 상세 분석 템플릿
- 간단 요약 템플릿
- 커스텀 템플릿

### 2. AI 응답 저장

**히스토리 관리**:
- 질문 내용
- AI 응답 (수동 입력)
- 액션 아이템
- 후속 조치

### 3. 자동 질문 생성

**이상 징후 감지**:
```markdown
⚠️ 자동 감지된 주의사항:
1. Sharpe Ratio가 이전 대비 20% 하락했습니다.
2. 특정 종목 비중이 50%를 초과합니다.
3. 변동성이 급증했습니다.

AI에게 다음을 질문하는 것을 권장합니다:
- 이러한 변화의 원인은 무엇인가요?
- 포트폴리오를 조정해야 하나요?
```

---

## 📝 구현 우선순위

### Phase 1: 기본 기능 (2~3시간)
1. ✅ AIPromptModal 컴포넌트
2. ✅ 프롬프트 생성 함수
3. ✅ 클립보드 복사
4. ✅ 외부 링크

### Phase 2: 프롬프트 개선 (1~2시간)
5. ⏳ 컨텍스트 추가
6. ⏳ 비교 데이터
7. ⏳ 추천 질문

### Phase 3: 고급 기능 (3~4시간)
8. ⏳ 템플릿 관리
9. ⏳ 히스토리 저장
10. ⏳ 자동 질문 생성

---

## 🚀 사용 예시

### 1. 포트폴리오 최적화 후

1. Portfolio 페이지 접속
2. "💬 AI에게 질문하기" 버튼 클릭
3. 프롬프트 확인
4. "📋 클립보드에 복사" 클릭
5. ChatGPT 또는 Gemini에 붙여넣기
6. AI 응답 확인
7. 인사이트 적용

### 2. 백테스트 결과 검토

1. Backtest 페이지에서 결과 확인
2. "💬 AI에게 질문하기" 클릭
3. 프롬프트에 추가 질문 작성
4. AI에게 질의
5. 전략 개선 아이디어 획득

---

## 📚 참고

### ChatGPT 활용 팁
- GPT-4 사용 권장 (더 정확한 분석)
- 구체적인 질문 추가
- 여러 번 대화하며 깊이 파고들기

### Gemini 활용 팁
- 최신 시장 데이터 반영
- 다양한 관점 제시
- 이미지/차트 분석 가능

---

**작성**: Cascade AI Assistant  
**최종 수정**: 2025-11-19  
**다음 작업**: AIPromptModal 컴포넌트 구현
