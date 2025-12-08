# AI 분석 연동 계획

**작성일**: 2025-12-08  
**목적**: ChatGPT/Gemini를 활용한 백테스트 결과 분석 및 전략 개선

---

## 1. 개요

### 1.1 목표
- 백테스트 결과를 AI에게 공유하여 객관적 의견 수렴
- 손실 발생 시 원인 분석 및 새로운 변수 도출
- 도출된 변수를 파라미터로 추가하여 전략 개선
- 지속적인 피드백 루프 구축

### 1.2 철학
> "백테스트로 돈을 벌 수 있다면 모두가 부자가 되었을 것이다.  
> 하지만 AI의 객관적 분석과 지속적인 개선을 통해 최선의 결과에 가까워질 수 있다."

---

## 2. 워크플로우

```
┌─────────────────────────────────────────────────────────────────┐
│                        전략 개선 사이클                           │
└─────────────────────────────────────────────────────────────────┘

    ┌──────────┐     ┌──────────┐     ┌──────────┐
    │  백테스트  │ ──▶ │  결과 분석 │ ──▶ │  AI 상담  │
    │   실행    │     │  리포트   │     │ (GPT/Gem)│
    └──────────┘     └──────────┘     └──────────┘
          ▲                                 │
          │                                 ▼
    ┌──────────┐     ┌──────────┐     ┌──────────┐
    │  파라미터 │ ◀── │  변수 추출 │ ◀── │  원인 분석 │
    │   추가   │     │  & 정의   │     │  & 제안   │
    └──────────┘     └──────────┘     └──────────┘
```

---

## 3. AI 분석 프롬프트 템플릿

### 3.1 백테스트 결과 분석 요청

```markdown
## 백테스트 결과 분석 요청

### 기간
- 시작: {start_date}
- 종료: {end_date}
- 기간: {years}년

### 성과 지표
- CAGR: {cagr}%
- Sharpe Ratio: {sharpe_ratio}
- MDD: {max_drawdown}%
- Calmar Ratio: {calmar_ratio}
- 거래 승률: {trade_win_rate}%
- 총 거래 수: {total_trades}회

### 파라미터
- MA 기간: {ma_period}
- RSI 기간: {rsi_period}
- 손절 비율: {stop_loss}%
- 리밸런싱 임계값: {rebalance_threshold}%

### 비용
- 총 수수료: {total_commission}원
- 총 세금: {total_tax}원
- 총 슬리피지: {total_slippage}원
- 비용 비율: {cost_ratio}%

### 질문
1. 이 결과에서 개선할 수 있는 부분은 무엇인가요?
2. MDD를 줄이기 위해 어떤 변수를 추가할 수 있을까요?
3. 시장 상황별로 다른 전략을 적용하는 것이 좋을까요?
```

### 3.2 손실 원인 분석 요청

```markdown
## 손실 구간 분석 요청

### 손실 발생 기간
- 시작: {loss_start_date}
- 종료: {loss_end_date}
- 손실률: {loss_pct}%

### 해당 기간 시장 상황
- KOSPI 변동: {kospi_change}%
- 거래량 변화: {volume_change}%
- 변동성 (VIX): {vix_level}

### 보유 종목
{holding_list}

### 질문
1. 이 손실의 주요 원인은 무엇으로 보이나요?
2. 어떤 지표를 모니터링했다면 손실을 줄일 수 있었을까요?
3. 새로운 방어 메커니즘으로 어떤 것을 제안하시나요?
```

### 3.3 새 변수 제안 요청

```markdown
## 새 변수 제안 요청

### 현재 사용 중인 변수
- 이동평균 (MA): 추세 판단
- RSI: 과매수/과매도
- 손절 비율: 리스크 관리
- 레짐 감지: 시장 상태 판단

### 발견된 문제점
{problem_description}

### 질문
1. 이 문제를 해결하기 위해 어떤 새 변수를 추가할 수 있을까요?
2. 해당 변수의 계산 방법과 적정 임계값은?
3. 기존 변수와의 상호작용은 어떻게 설계해야 할까요?
```

---

## 4. 데이터 내보내기 형식

### 4.1 JSON 형식 (API 연동용)

```json
{
  "backtest_result": {
    "period": {"start": "2024-01-01", "end": "2024-12-31"},
    "metrics": {
      "cagr": 15.5,
      "sharpe_ratio": 1.2,
      "max_drawdown": 12.3,
      "calmar_ratio": 1.26,
      "trade_win_rate": 55.2,
      "total_trades": 150
    },
    "params": {
      "ma_period": 20,
      "rsi_period": 14,
      "stop_loss": 5,
      "rebalance_threshold": 1
    },
    "costs": {
      "commission": 150000,
      "tax": 0,
      "slippage": 100000
    }
  },
  "market_context": {
    "kospi_return": 8.5,
    "avg_volatility": 15.2,
    "regime_distribution": {
      "bullish": 45,
      "neutral": 35,
      "bearish": 20
    }
  }
}
```

### 4.2 마크다운 형식 (수동 복사용)

UI에서 "AI 분석용 복사" 버튼 클릭 시 클립보드에 복사되는 형식

---

## 5. 구현 계획

### Phase 1: 데이터 내보내기 (1주)
- [ ] 백테스트 결과 JSON 내보내기 API
- [ ] UI에 "AI 분석용 복사" 버튼 추가
- [ ] 마크다운 템플릿 자동 생성

### Phase 2: 분석 기록 관리 (1주)
- [ ] AI 분석 결과 저장 기능
- [ ] 분석 히스토리 조회
- [ ] 분석 결과와 백테스트 연결

### Phase 3: 변수 관리 시스템 (2주)
- [ ] 새 변수 정의 인터페이스
- [ ] 변수 계산 로직 플러그인 시스템
- [ ] 변수 효과 A/B 테스트 기능

### Phase 4: 자동화 (선택)
- [ ] OpenAI API 연동 (자동 분석)
- [ ] 분석 결과 기반 파라미터 자동 조정 제안
- [ ] 주간 자동 리포트 생성

---

## 6. 변수 추가 프로세스

### 6.1 변수 정의서 템플릿

```yaml
variable:
  name: "market_breadth"
  description: "시장 폭 지표 - 상승 종목 비율"
  category: "market_condition"
  
calculation:
  formula: "advancing_stocks / total_stocks * 100"
  data_required:
    - "daily_stock_changes"
  lookback_period: 1  # days
  
parameters:
  threshold_bullish: 60  # % 이상이면 강세
  threshold_bearish: 40  # % 이하면 약세
  
integration:
  affects: ["position_size", "entry_signal"]
  priority: 2  # 1=highest
  
backtest_validation:
  min_improvement_sharpe: 0.1
  max_increase_mdd: 2  # %
```

### 6.2 변수 추가 워크플로우

1. **문제 식별**: AI 분석에서 문제점 도출
2. **변수 제안**: AI가 새 변수 제안
3. **정의서 작성**: 위 템플릿으로 변수 정의
4. **구현**: 계산 로직 코드 작성
5. **백테스트**: 변수 추가 전/후 비교
6. **검증**: Sharpe 개선, MDD 악화 없음 확인
7. **적용**: 프로덕션 반영

---

## 7. 성공 지표

### 7.1 정량적 지표
- Sharpe Ratio 개선: 목표 +0.2 이상
- MDD 감소: 목표 -3% 이상
- 거래 승률 개선: 목표 +5% 이상

### 7.2 정성적 지표
- AI 분석 활용 빈도: 주 1회 이상
- 새 변수 추가: 월 1개 이상
- 분석 기록 축적: 분기당 10건 이상

---

## 8. 주의사항

### 8.1 과적합 방지
- 새 변수 추가 시 반드시 Out-of-Sample 테스트
- 변수 개수 제한 (최대 10개)
- 정기적인 변수 유효성 검토

### 8.2 AI 의존성 관리
- AI 제안은 참고용, 최종 결정은 사용자
- 모든 변경사항 기록 및 추적
- 롤백 가능한 구조 유지

### 8.3 시장 변화 대응
- 분기별 전략 리뷰
- 시장 레짐 변화 시 재분석
- 장기 성과 추적 (1년 이상)

---

## 9. 참고 자료

### 9.1 추천 AI 프롬프트 기법
- Chain of Thought: 단계별 분석 요청
- Few-shot: 예시와 함께 질문
- Role-playing: "퀀트 애널리스트로서..."

### 9.2 관련 문서
- `docs/analysis/BACKTEST_ENGINE_CODE_REVIEW.md`
- `docs/plans/BACKTEST_IMPROVEMENT_PLAN.md`
- `docs/WEEK3_HYBRID_STRATEGY.md`

---

## 10. 체크리스트

- [ ] Phase 1 완료
- [ ] Phase 2 완료
- [ ] Phase 3 완료
- [ ] 첫 AI 분석 수행
- [ ] 첫 변수 추가 완료
- [ ] 1개월 성과 리뷰
