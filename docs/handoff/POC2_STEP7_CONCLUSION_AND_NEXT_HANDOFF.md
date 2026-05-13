# POC2-Step7 Conclusion & Next Handoff

## System Output 3-Push Realignment — 시리즈 종결

작성일: 2026-05-13
대상: 사용자 / 설계자 / 다음 세션 진입자
선행 읽기 순서:
1. docs/PROJECT_ORIGIN_INTENT.md — §3 시스템 출력 정의, §4 성공 기준
2. docs/KILL_SWITCHES.md — KS-5 / KS-10 / KS-11 가드
3. docs/ASSUMPTIONS.md — Q1 / Q4 (OPEN), L-3 (Q5 BACKLOG 이관)
4. docs/handoff/POC2_STEP7_SYSTEM_OUTPUT_3_PUSH_REALIGNMENT_DESIGN.md — Step7 마스터 설계서
5. docs/handoff/POC2_STEP7A_NEW_ETF_WATCH_CANDIDATE_MINIMAL_PUSH.md — PUSH 2
6. docs/handoff/POC2_STEP7B_HOLDINGS_STATUS_BRIEFING_MINIMAL_PUSH.md — PUSH 1
7. docs/handoff/POC2_STEP7C_FALLING_ETF_CAUTION_SIGNAL_MINIMAL_PUSH.md — PUSH 3
8. 본 문서

---

## 1. Step7 시리즈 종결 사실

```text
시리즈 종결: 2026-05-13
모든 STEP 검증자(Codex) 최종 판정: VERIFIED / VERIFIED_WITH_NOTES
3-PUSH 모두 최소 운영 가능 상태 도달.
```

### Step7 시리즈 commit chain (origin/main 기준)

| STEP | 성격 | Commit | 결과 |
|---|---|---|---|
| Step7 (설계) | 구조 재정렬 설계서 | 1c7881d9 | CONDITIONAL_PASS |
| Step7 / Step6 docs 정합성 | 직전 STEP 결과 동기화 | aa1253e1 / 9518f749 / 93025d18 | — |
| Step7A 구현 | PUSH 2 신규 ETF 관찰 후보 + starter seed | 3d9112d5 | VERIFIED_WITH_NOTES |
| Step7A NOTE 대응 | 포인터 stub 갱신 | d84bc7df | — |
| Step7B 구현 | PUSH 1 보유 종목 상태 브리핑 통합 | 531ffbf6 | (1차 REJECTED) |
| Step7B Fix | UI placeholder 제거 + 포인터 본문 revert | 5dcb207c | VERIFIED_WITH_NOTES |
| Step7C 구현 | PUSH 3 급락 ETF 주의 신호 | d7075bfd | VERIFIED_WITH_NOTES |
| Step7C NOTE 대응 | scope 타입 확장 + BACKLOG RESOLVED 표기 | 88ae8bf1 | — |

### 검증 흐름 요약

- **Step7 설계서**: CONDITIONAL_PASS → MINOR 1건 수용 (매수/매도 의견 드리프트 차단 문구).
- **Step7A**: 1차 VERIFIED_WITH_NOTES → NOTE 정정 → 최종 VERIFIED_WITH_NOTES.
- **Step7B**: 1차 REJECTED (UI placeholder 잔존 / 포인터 본문 변경) → Fix 라운드 →
  VERIFIED_WITH_NOTES.
- **Step7C**: 1차 VERIFIED_WITH_NOTES → NOTE 정정 → 본 commit 시점 최종 통과.

---

## 2. 3-PUSH 최종 구조

### message_text / Telegram 출력 구조 (최종 형태)

#### Case 1: 모든 PUSH 데이터 가용

```
[판단 사유]
- 보유 종목 상태 브리핑: 평가 계산 가능 보유분 중 {name}의 비중이 가장 큽니다. 현재 보유 종목 점검 기준으로 평가 가능한 보유 종목 중 {name}의 점검값이 가장 높습니다. 이 내용은 매수/매도 의견이 아닙니다.
- 신규 ETF 관찰 후보: pykrx 1개월 수익률 기준 {name}이 가장 높습니다({value}%, 기준일 {date}, 계산 가능 {scored}/{total}개). 이 값은 매수 추천이 아닙니다.
- 급락 ETF 주의 신호: pykrx 1개월 수익률 기준 {name}이 {value}%로 초기 급락 기준(-10.0%) 이하입니다(기준일 {date}). 이 값은 매수/매도 지시가 아닙니다.
```

#### Case 2: 급락 신호 없음 (대부분의 일상 운영)

```
[판단 사유]
- 보유 종목 상태 브리핑: ...
- 신규 ETF 관찰 후보: ...
```

급락 후보 없음 → bullet 자체 미생성. "신호 없음" 같은 매번 메시지를 Telegram 에 보내지
않음 (KS-5 알림 과다 방지).

#### Case 3: pykrx universe refresh 한 번도 안 한 신규 환경

```
[판단 사유]
- 보유 종목 상태 브리핑: ...
```

PUSH 2 / PUSH 3 모두 latest artifact 부재 → bullet 미생성. Step7A starter seed 가
첫 refresh 시 자동 생성되므로 1회 갱신 후 PUSH 2 동작.

### 공식 PUSH 명칭 (Step7 §2 — 중립형)

| 번호 | 명칭 | 데이터 소스 | 자리 |
|---|---|---|---|
| PUSH 1 | **보유 종목 상태 브리핑** | factor_signals scope=portfolio + momentum_result.summary.top_candidate (Step5B/Step3 결과 재배치) | [판단 사유] bullet 1 |
| PUSH 2 | **신규 ETF 관찰 후보** | factor_signals scope=universe (universe_momentum_latest.json.summary.top_candidate) | [판단 사유] bullet 2 |
| PUSH 3 | **급락 ETF 주의 신호** | factor_signals scope=universe_falling (universe_momentum_latest.json.summary.falling_candidate, 조건부) | [판단 사유] bullet 3 (조건부) |

---

## 3. 데이터 흐름 다이어그램 (Step7 시리즈 종결 시점)

```
사용자 UI
   ↓
[홀딩스 입력 / 시세 갱신 / GenerateDraft 버튼]
   ↓
GenerateDraft (POST /runs/generate-from-holdings)
   ↓
app/draft.py:_build_holdings_payload
   ↓
  1. build_factor_signals(enriched)  ← Step3 portfolio_concentration
  2. build_holdings_momentum_result(enriched)  ← Step5B holdings momentum
  3. _build_universe_factor_signal(asof)  ← Step6/Step7A — universe_momentum_latest.json 읽음
     · factor_signals 에 scope="universe" entry 추가
  4. _build_falling_etf_factor_signal(asof)  ← Step7C — 같은 artifact 읽음
     · falling_candidate 가 None 이면 factor_signal entry 자체 미추가
     · 있으면 factor_signals 에 scope="universe_falling" entry 추가
   ↓
draft_payload (정확히 6개 키 — title / asof / note / recommendations / factor_signals / momentum_result)
   ↓
app/draft_message.py:build_message_text
  → _render_judgment_lines
    · _holdings_status_briefing_bullet  ← Step7B (PUSH 1)
    · _external_universe_bullet         ← Step7A (PUSH 2)
    · _falling_etf_caution_bullet       ← Step7C (PUSH 3, 조건부)
   ↓
Run.message_text  ← Single source
   ↓
[Preview / Approve / OCI handoff / Telegram] 모두 동일 message_text 사용

[별도 흐름] universe momentum refresh
사용자 [신규 ETF 관찰 후보 갱신] 버튼
   ↓
POST /universe/momentum/refresh  ← Step6 + Step7A starter seed + Step7C falling
   ↓
app/universe_refresh.py:run_universe_refresh
   ↓
app/price_history_pykrx.py:fetch_one_month_basis  ← pykrx 단일 호출 모듈 (KS-9)
   ↓
build_universe_momentum_result_scored(..., falling_threshold_pct=-10.0)
   · summary.top_candidate (rank=1)
   · summary.falling_candidate (score <= -10.0, tie-breaker score ASC → ticker ASC → candidate_id ASC)
   ↓
universe_momentum_latest.json
   ↓
GenerateDraft 가 다음 호출 시 위 artifact 를 읽어 PUSH 2 / PUSH 3 반영
```

핵심 가드:
- **GenerateDraft 가 pykrx 직접 호출 0건** — latest artifact 만 읽음 (AC-20 from Step6).
- **draft_payload top-level 키 신설 0건** (Step7 시리즈 전반).
- **신규 endpoint 0건** (Step7 시리즈 전반).
- **새 데이터 계약 변경** = factor_signals scope 값 2건 확장 (universe / universe_falling).

---

## 4. KS-10 최종 상태

| 카테고리 | 최대 파일 | 라인 | 트리거 임계 | 근접 임계 | 상태 |
|---|---|---|---|---|---|
| 백엔드 핵심 모듈 | `app/draft_message.py` | 564 | >650 | ≥600 | **trigger 0 + near 0** ✓ |
| 프론트 컴포넌트 | `frontend/app/components/EnrichedHoldingsSection.tsx` | 515 | >900 | ≥850 | **trigger 0 + near 0** ✓ |
| 테스트 파일 | `tests/test_holdings_message_text.py` | 924 | >1500 | ≥1450 | **trigger 0 + near 0** ✓ |

Step7 시리즈 중 분리 라운드 (Step7B / Step7C 각 1회) — `message_holdings_briefing.py` /
`message_falling_etf_bullet.py` 신설 + 미사용 _factor_bullet / _momentum_bullet 제거로
KS-10 가드 충족 유지.

### 750라인 이상 파일

- `tests/test_holdings_message_text.py` (924) — Step5D-2 부터 잔존, Step7 시리즈 변경 없음.

### Step7 시리즈 신규 모듈 (전체 3건)

- `app/message_universe_bullet.py` (Step6 / Step7A) — PUSH 2 bullet 텍스트 빌더
- `app/message_holdings_briefing.py` (Step7B) — PUSH 1 통합 bullet 빌더
- `app/message_falling_etf_bullet.py` (Step7C) — PUSH 3 bullet 빌더 + picker

---

## 5. 테스트 누적

| STEP | 신규 테스트 | 누적 |
|---|---|---|
| Step5 baseline | — | 119 |
| Step6 | 16 | 135 |
| Step7A | 12 | 147 |
| Step7B | 12 | 159 |
| Step7C | 14 | 173 |

**173 passed in 1.84s** (Step7C 시점 측정).

---

## 6. 잔존 BACKLOG (Step7 시리즈 종결 시점)

### Step7 시리즈에서 신규 등록된 BACKLOG

| 항목 | 출처 | 복귀 조건 |
|---|---|---|
| manual seed 입력 UX 개선 (seed 편집 UI) | Step7A | 사용자 후보군 직접 수정 필요 보고 1회 / PUSH 2 두 번째 라운드 |
| 기본 ETF starter seed 확장 | Step7A | 신규 ETF 관찰 후보 2회 이상 운영 후 후보군 관리 병목 |
| 운영 빈도 문서 정합성 보정 | Step7 §9.7 | PUSH 1/2/3 중 첫 운영 STEP 진입 직전 |
| 보유 종목 상태 브리핑 상세 UI | Step7B | 사용자가 특정 보유 종목 상태 근거를 더 보고 싶다고 명시 |
| 보유 점검 산식 개선 | Step7B | 운영 후 점검값이 사용자 판단에 도움이 되지 않는다고 확인 |
| 급락 임계값 검증 | Step7C | 급락 신호 2회 이상 발생 또는 후보가 전혀 안 나옴 |
| 급락 기준 기간 비교 (1일/60일/120일) | Step7C | "이미 많이 빠진 뒤에야 신호가 나온다" 사용자 보고 |
| 급락 신호 UI 고도화 | Step7C | 사용자가 급락 후보 가격 흐름 UI 표시 명시 요청 |

### Step6 부터 누적된 후속 리스크

- **pykrx 단일 호출 timeout 부재** (Step6 MEDIUM) — Windows POSIX signal 부재 + thread 누수 위험으로 별도 작업. 실 운영 hang 발생 시 재검토.

### 자동 ETF universe 수집 / ML 등 장기 보류 항목

기존 BACKLOG 의 Layer A/B/C 항목 그대로 유지. ML 단계 진입은 단일 가격 기반 변수
운영 결과 부족 증거 + 백테스트 인프라 준비 후.

---

## 7. ASSUMPTIONS 상태 (Step7 시리즈 종결 시점)

| 질문 | 상태 | 비고 |
|---|---|---|
| **Q1** 여러 factor 부착 가능 구조 | OPEN | 새 factor 1개를 10줄 이내로 추가 가능한가 — POC 1단계 완료 시점 판정 |
| **Q4** 잘 올라가는 섹터/ETF 발굴 단위 | OPEN | Layer A 관리 — 발굴 단위 / 시간 측정 기간 모두 확정값 아님 |
| **L-3 (이전 Q5)** AI 토론 점수체계 검증 | BACKLOG 이관 | 복귀 트리거: 운영 시작 + PUSH 수신 + AI 투자세션 + 첫 매매 결정 1회 |
| **A-5 (이전 Q3)** 앞으로 못 나가는 패턴 | ANSWERED + 변형 패턴 발견 | KS-11 의사결정 24시간 룰로 차단. 분기 1회 PROJECT_ORIGIN_INTENT 재확인 권고 |

활성 OPEN 질문 2개 (Q1 / Q4) — 최대 3개 원칙 안.

---

## 8. Q5 첫 실전 데이터 수집 가이드 (운영 사이클 1회)

L-3 (이전 Q5) BACKLOG 복귀 트리거: **운영 시작 후 시스템 PUSH 수신 + AI 투자세션 +
첫 매매 결정 1회**.

### 운영 사이클 1회 정의 (Step7 시리즈 종결 시점)

```
EOD 분석 1회
  ↓
사용자가 시스템 PUSH 수신 (Telegram)
  · 보유 종목 상태 브리핑 1줄
  · 신규 ETF 관찰 후보 1줄 (universe seed 갱신 후)
  · 급락 ETF 주의 신호 1줄 (조건 만족 시)
  ↓
사용자가 AI 투자세션 진행 (별도 채널 — Step7 §5)
  ↓
사용자 매매 결정 또는 명시적 보류
  ↓
[L-3 BACKLOG 복귀 트리거 충족]
```

### 사용자 (= Q5 검증 대상 본인) 가 수집할 정보

1. **PUSH 가 의사결정에 실제로 도움 되는지**: PUSH 받은 후 행동 (매수/매도/보류) 으로
   연결되는 비율.
2. **변수 한계 인식**: 1개월 수익률 1개로 부족하다고 느끼는 신호가 어디서 나오는지.
3. **다음 변수 후보**: 한계 인식 시 추가하고 싶은 변수 카테고리 (다른 가격 변수 /
   거래량 / 섹터 / 외부 이벤트 등).
4. **AI 토론 사이클 작동 여부**: AI 투자세션이 실제 결정에 영향을 주는지, 단순히 말만
   늘리는지.

### 운영 기록 위치

- 사용자 본인 메모 / 노트.
- 또는 ASSUMPTIONS.md L-3 / Q4 항목에 분기 1회 직접 추가 기록.

---

## 9. 다음 단계 후보 (사용자 / 설계자 결정 영역)

### 후보 A — 운영 사이클 1회 시작 (가장 자연스러운 다음 흐름)

- 구현 STEP 없음. 사용자가 시스템 사용 시작 → PUSH 수신 → AI 투자세션 → 매매 결정.
- 1회 사이클 후 ASSUMPTIONS L-3 BACKLOG → 활성 질문 복귀 + Q5 첫 실전 데이터 수집.

### 후보 B — 운영 빈도 문서 정합성 보정

- PROJECT_ORIGIN_INTENT §7 "1일 3회 PC 분석" vs Step7 §7 "K6/EOD 저빈도" 표현 정합성.
- 문서만 변경, 코드 변경 0건. 운영 STEP 진입 전 권장.

### 후보 C — BACKLOG 잔존 후속 항목 진입

- Step7 시리즈에서 등록된 8건 + 누적 항목. 사용자 명시 트리거 발생 시 STEP 명명.

### 후보 D — 새 영역 (Step8 후보)

- 운영 사이클 1회 결과 후 데이터에 따라 결정.
- 단일 가격 변수 한계 신호 → Q4 Layer A 의 "시간 측정 기간" 검토 STEP.
- 또는 PROJECT_ORIGIN_INTENT §6 의 ML 엔진 검증 가능성 진입 검토.

---

## 10. 새 세션 진입자 체크리스트

다음 세션에서 본 프로젝트를 이어받을 때 반드시 수행:

1. **기반 문서 5개 + 본 문서 정독** (CLAUDE.md §1 절차):
   - `docs/PROJECT_ORIGIN_INTENT.md`
   - `docs/KILL_SWITCHES.md`
   - `docs/ASSUMPTIONS.md`
   - `CLAUDE.md`
   - `docs/handoff/POC2_STEP7_SYSTEM_OUTPUT_3_PUSH_REALIGNMENT_DESIGN.md` (마스터 설계)
   - 본 문서 (POC2_STEP7_CONCLUSION_AND_NEXT_HANDOFF.md)

2. **STATE_LATEST 읽기**:
   - `docs/handoff/STATE_LATEST.md` (SSOT) — 현재 단계 + Step7C VERIFIED 확인.
   - `docs/STATE_LATEST.md` (포인터 stub) — 단축 버전.

3. **BACKLOG 읽기**:
   - `docs/backlog/BACKLOG.md` — STEP7C 종료 후 신규 + STEP7B + STEP7A + STEP7
     설계서 저장 후 신규 항목 모두.

4. **코드 상태 확인**:
   - `git log --oneline -10` — Step7 시리즈 commit chain 확인.
   - `wc -l app/draft_message.py` — 564 라인 (KS-10 안전 영역).
   - 본 문서 §3 의 데이터 흐름 다이어그램 1번 정독.

5. **"기반 문서 확인 완료" 응답 후 작업 착수** (CLAUDE.md §1).

---

## 11. Step7 시리즈 자체 평가 (개발자 입장)

검증자가 잡지 못한 / 사용자가 알아야 할 한계:

- **자동 테스트는 모두 pykrx stub**: 실제 pykrx 호출은 사용자의 첫 운영 refresh 클릭이
  진짜 첫 검증 사이클. 본 세션 안에서는 Step6 의 운영 테스트 1회 (Telegram 수신 확인)
  를 사용자가 직접 했고 그것이 유일한 실 호출 검증.
- **3-PUSH UI 페이지 reload 동작**: UniverseRefreshPanel 의 상태 패널은 refresh 직후만
  채워짐 (POST 응답 → frontend state). 페이지 reload 시 비워지므로 사용자가 "어디 갔지?"
  라 느낄 수 있음. Step6 Fix 라운드의 안내 문구로 부분 mitigation, 완전한 해소 아님.
- **draft_message.py 의 단일 파일 누적**: Step6 부터 Step7C 까지 매 STEP 별로 bullet
  빌더가 추가될 때마다 KS-10 가드 발동 → 분리 라운드 → 안전 복귀 패턴이 3회 반복됨.
  향후 PUSH 추가가 또 있다면 별도 message 모듈 패키지 (`app/message/`) 로 묶는 방안
  사전 검토 가치 있음.
- **factor_signals scope 확장 일반화 위험**: Step7A 가 scope="universe" 추가 → Step7C
  가 scope="universe_falling" 추가. 패턴이 일반화되면 "scope 만 늘리면 된다" 는 부주의
  진입 가능. BACKLOG `factor_signals 외 메타 키 추가 금지` 항목의 가드 정신은 항목
  추가에도 동일하게 적용해야 한다는 점을 다음 STEP 진입 시 명시 권장.
- **세션 누적 컨텍스트**: 본 세션은 Step5C 부터 Step7C 까지 ~15 STEP 누적. 다음 STEP
  진입 시 새 세션 강력 권장 (의사결정 편향 누적 회피).

---

## 12. 검증 통과 commit 최종 목록 (origin/main 기준)

```
88ae8bf1 docs(poc2-step7c): address Codex NOTES — extend scope type + mark BACKLOG resolved
d7075bfd feat(poc2-step7c): falling ETF caution signal (PUSH 3) minimal push
5dcb207c fix(poc2-step7b): address Codex REJECTED — remove UI placeholder + revert pointer
531ffbf6 feat(poc2-step7b): unify holdings status briefing (PUSH 1) bullet
d84bc7df docs(poc2-step7a): mark VERIFIED_WITH_NOTES + record Step7 design in pointer
3d9112d5 feat(poc2-step7a): align label + starter seed for new ETF watch candidate
1c7881d9 docs(poc2-step7): save 3-Push Realignment Design (CONDITIONAL_PASS)
```

---

문서 끝. POC2-Step7 시리즈 종결. 다음 세션 진입자 또는 사용자의 운영 사이클 시작을
기다린다.
