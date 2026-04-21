# KRX Alertor Modular — Phase 2 Hand-off & Master Plan

작성 시점: 2026-04-16
목적: 다음 세션에서 흐름이 끊기지 않도록, 현재 프로젝트 상태·판정·다음 단계 계획·세션 시작 지시문을 한 문서에 고정한다.

---

## 1. 현재 프로젝트 위치 요약

현재 프로젝트는 **Phase 1 = 현재 엔진 자체 검증/반증 사이클**을 완료했다.

Phase 1에서 닫은 축:
- P206: timing / regime 검증
- P207: allocation 검증
- P208: holding structure 검증
- P209A/B/C: selection/filter Track A 검증
- P210A/A-2/B/C: selection/filter Track B 검증 및 closeout

핵심 결론:
- Main Run은 여전히 승격 기준 미달이다.
- Research Candidate는 수익률은 상대적으로 낫지만 MDD 벽을 넘지 못했다.
- Track B(ML)는 활성화·재설계까지 했으나 MDD를 개선하지 못해 closeout 되었다.
- 따라서 지금은 **기존 엔진 미세조정 단계가 아니라, Phase 2 진입 단계**다.

---

## 2. 최신 canonical 기준선 (세션 시작 시 최우선 확인)

### Main Run
- Identifier: `g2_pos2_raew`
- CAGR: `11.83%`
- MDD: `14.10%`
- Sharpe: `1.1522`
- Verdict: `REJECT`

### Research Candidate
- Identifier: `B1_pos3_raew_pre_entry_guard`
- CAGR: `16.3198%`
- MDD: `13.0048%`
- Sharpe: `1.5456`
- Verdict: `REJECT`

### Track B Latest (best failed candidate)
- Identifier: `B2_research_L1_softgate`
- Label Profile: `L1_severe_crash20`
- Action Policy: `soft_gate_top1_skip`
- Min Train Samples: `100`
- Label Positive Ratio: `45.76%`
- Predicted Dates: `6`
- Soft Gate Hits: `5`
- CAGR: `14.7438%`
- MDD: `13.0048%`
- Sharpe: `1.4826`
- Verdict: `REJECT`

### Track B Closeout
- `track_b_status = CLOSED_REJECTED`
- `track_b_closeout_verdict = Activated but did not improve MDD`
- `track_b_limit_reason = MDD not improved across activated variants`
- `do_not_promote = [B1_research_L0_softgate, B2_research_L1_softgate, B3_research_L2_rerank]`

---

## 3. Phase 1 종료 의미

Track B를 닫는다는 것은 아래를 의미한다.

1. 현재 Track B 설계축은 **작동은 했지만 승격 불가**로 공식 종료한다.
2. 같은 축의 미세조정(동일 feature / 동일 LR / threshold 장난 / softgate/rerank 반복)은 중단한다.
3. `CURRENT_TRACK_B_LATEST`는 승격 후보가 아니라 **best failed candidate**로 유지한다.
4. 현재 엔진 검증은 충분히 진행되었고, 다음은 **새로운 입력 소스(friend project)와 운영 UX**를 중심으로 한 Phase 2다.

---

## 4. Phase 2 목표

Phase 2의 목표는 세 가지다.

1. **친구 프로젝트의 장점 추출**
   - 전략 규칙
   - 운영 판단 방식
   - UI/운영 흐름

2. **직장인형 Human + AI Decision Loop 설계**
   - 형수님은 전업투자자가 아니므로, 상시 관측형이 아닌 저빈도 운영형 구조가 필요하다.
   - AI는 단순 분류기가 아니라, 비교·설명·회고를 돕는 판단 파트너가 되어야 한다.

3. **운영형 UX 재설계**
   - 현재 UI는 연구/검증에는 유효하지만 운영 대시보드로는 지저분하다.
   - 운영용 1페이지 / 연구용 상세화면 분리가 필요하다.

---

## 5. Phase 2 권장 순서

### P211-STEP11A-FRIEND-SOURCE-RULE-EXTRACTION-V1
성격: **analysis-only**
목표:
- 친구 프로젝트에서 실제 이식 가치가 있는 규칙/구조/UX 후보만 추출한다.
- 전체 소스 완독이 아니라, 우선순위 높은 파일만 선택 완독한다.

우선 완독 대상:
- `core/strategy/scoring.py`
- `core/strategy/metrics.py`
- `core/strategy/weight_allocator.py`
- `utils/rankings.py`
- `utils/backtest_service.py`
- `utils/data_loader.py`
- `utils/cache_utils.py`

산출물:
- 후보별 4축 평가표
  - 타당성
  - 기대 효과
  - 이식 비용
  - 영향 범위
- 분류 태그
  - 즉시 이식 후보
  - 연구 보류 후보
  - UI 참고 후보
  - 이식 금지

### P211-STEP11B-OPERATOR-UX-REDESIGN-V1
성격: 설계 우선, 필요 시 이후 구현
목표:
- 운영용 1페이지와 연구용 상세화면을 분리한다.
- friend project의 좋은 화면 구조를 참고하되, 현재 canonical/handoff 구조를 깨지 않는다.

### P212-STEP12A-HUMAN-AI-DECISION-LOOP-V1
목표:
- AI를 “예측기”가 아니라 “설명·비교·회고 도우미”로 포함한 운영 루프 설계
- 입력: current strategy state, compare, 시장 상태, 후보/제외 후보, 필요 시 뉴스/이벤트 태그
- 출력: 이번 판단 근거, 리스크 신호, 과거 실패 패턴 유사성, 최종 인간 승인 포인트

### P212-STEP12B-SHADOW-LIVE-OPS-REHEARSAL-V1
목표:
- 실제 매매 없이도 운영 흐름을 실전처럼 굴려보는 shadow/live-lite 리허설
- 운영 가능한 UI/보고/판단 체계인지 검증

### 이후
- 더 큰 ML / GPU 활용 / 더 넓은 유니버스 / 더 복잡한 모델은
  **Phase 2가 정리된 뒤** 검토한다.

---

## 6. 친구 프로젝트에서 우선 가져올 후보

우선순위 높은 전략 로직 후보:
1. 7종 MA (특히 ALMA / HMA)
2. 0 중심 부호 보존 백분위 점수
3. MA_RULES 기반 다중 규칙 조합
4. 데이터 충분성 단계적 완화
5. min/max 가드레일 반복 정규화 비중 할당
6. 최근 월간 수익률 curve feature

UI/운영 참고 후보:
1. 3단 헤더 구조
2. 순위 화면의 집중도 높은 정보 배치
3. 종목 상세의 drill-down 구조
4. 계좌/종목풀 분리 개념

이식 금지(현 단계):
- MongoDB 자체 호스팅
- Google OAuth
- Next.js 프론트 전체 전환
- 실시간 외부 API 의존 강화
- 알림/인프라 전체 이식

---

## 7. 다음 세션 기본 첨부 묶음

다음 세션에서는 아래 파일만 기본 첨부한다.

### required
- `reports/handoff/latest/handoff_manifest.json`
- `reports/handoff/latest/current_strategy_state.json`
- `reports/handoff/latest/experiment_registry.json`
- `reports/handoff/latest/dynamic_evidence_latest.md`
- `freiends_project/MOMENTUM_ETF_ANALYSIS.md`

### optional
- `reports/handoff/latest/decision_ledger.json`
- `reports/handoff/latest/chapter_focus_compare.json`

원칙:
- 캡처는 기본 첨부 아님
- JSON 우선, MD 보조
- UI 충돌/렌더링 문제 있을 때만 캡처 추가

---

## 8. 다음 세션 시작 프롬프트 (복붙용)

```text
[PROJECT BOOT — KRX Alertor Modular / Phase 2]

지금부터는 Phase 1(현재 엔진 검증/반증 사이클) 종료 이후의 Phase 2를 진행한다.
Phase 1에서는 timing / allocation / holding structure / selection Track A / selection Track B를 모두 검증했고, 최신 canonical 기준으로 다음 상태가 고정되어 있다.

- Main Run: g2_pos2_raew = 11.83 / 14.10 / 1.1522 / REJECT
- Research Candidate: B1_pos3_raew_pre_entry_guard = 16.3198 / 13.0048 / 1.5456 / REJECT
- Track B Latest: B2_research_L1_softgate = 14.7438 / 13.0048 / 1.4826 / REJECT
- Track B Status: CLOSED_REJECTED
- Phase 1 complete → Phase 2 진입

이번 세션의 목표는
1) 친구 프로젝트(momenum-etf-main)에서 이식 가능한 규칙/UX/운영 흐름을 추출하고
2) 직장인형 Human + AI decision loop 설계의 입력을 만들며
3) 이후 운영형 UI 재설계로 이어질 수 있는 분석 결과를 만드는 것이다.

절대 규칙:
- 지금은 구현이 아니라 analysis-only 챕터다.
- 전체 소스 전수 완독이 아니라, 우선순위 높은 파일만 선택 완독한다.
- 친구 프로젝트를 통째로 이식하지 않는다. rule extraction / UI reference / do-not-import 로 분리한다.
- 기존 canonical/handoff 구조를 깨지 않는다.
- Main Run / Compare Run / analysis-only 를 반드시 구분한다.
- stale 가능성이 있으면 먼저 경고한다.

이번 세션 시작점:
- P211-STEP11A-FRIEND-SOURCE-RULE-EXTRACTION-V1
- 우선 완독 대상:
  - core/strategy/scoring.py
  - core/strategy/metrics.py
  - core/strategy/weight_allocator.py
  - utils/rankings.py
  - utils/backtest_service.py
  - utils/data_loader.py
  - utils/cache_utils.py

출력 요구:
- 항상 첫 줄은 “다음에 눌러야 할 UI 버튼 3개 + 기대 결과” 형식
- 이번 세션은 UI 액션이 실제로 없으면 “없음 / 이번 단계는 설계·판정·문서화 / UI 변화 없음”으로 시작
- 소스 수정 없이 판단이면 “순차 확인사항 + 예상결과” 체크리스트
- 소스 수정 필요 시에만 “[수정 지시문] + [최종 보고 JSON]”

첨부 파일은 handoff_manifest.json, current_strategy_state.json, experiment_registry.json, dynamic_evidence_latest.md, MOMENTUM_ETF_ANALYSIS.md 를 기준으로 읽어라.

이번 세션의 1차 목표는 친구 프로젝트에서 실제 이식 가치가 있는 후보를 4축 평가표(타당성 / 기대 효과 / 이식 비용 / 영향 범위)로 정리하는 것이다.
```

---

## 9. 다음 세션에서 절대 잃으면 안 되는 흐름

1. 지금 엔진은 **검증을 충분히 거친 상태**다
2. Track B는 **닫혔다**
3. 이제는 “같은 축 미세조정”이 아니라 **새로운 입력원(friend source) 추출 단계**다
4. 형수님은 전업이 아니라 직장인이므로, 운영형 구조는 **저빈도·설명가능·AI 보조형**으로 가야 한다
5. 목표는 “AI가 대신 투자”가 아니라 **AI와 함께 더 잘 판단하는 시스템**이다
6. 언젠가는 실운영도 맛봐야 하므로, 완전 자동보다 **shadow/live-lite**가 중간 단계로 필요하다

---

## 10. 세션 이동 후 첫 질문의 방향

새 세션에서는 아래 둘 중 하나로 바로 시작하면 된다.

### 추천 시작
- “P211-STEP11A-FRIEND-SOURCE-RULE-EXTRACTION-V1 지시문을 작성하라”

### 또는 먼저 판단
- “친구 프로젝트에서 우선 완독할 7개 파일을 기준으로 4축 평가표 초안을 작성하라”

---

## 11. 마지막 정리

이 handoff 문서는 **흐름 유지용 앵커**다.
다음 세션의 GPT는 이 문서를 읽고,
- 우리가 어디까지 왔는지
- 무엇을 닫았는지
- 왜 지금 친구 프로젝트 분석으로 넘어가는지
- 그 다음에 어떤 순서로 설계할지
를 바로 이어서 이해해야 한다.
