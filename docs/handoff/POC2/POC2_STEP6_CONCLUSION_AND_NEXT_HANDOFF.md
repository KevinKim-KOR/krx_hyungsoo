# POC2-Step6 Conclusion & Next Handoff

작성일: 2026-05-11
대상: 다음 세션의 모든 역할자 (사용자 / 설계자 / 개발자 / 검증자)
선행 읽기: `docs/PROJECT_ORIGIN_INTENT.md` / `docs/KILL_SWITCHES.md` /
          `docs/ASSUMPTIONS.md` / `CLAUDE.md` / 본 문서.

---

## 1. Step6 종결 사실

```text
STEP: POC2-Step6 Universe Momentum Formula Minimal Scoring
종결 시점: 2026-05-11
검증자(Codex) 최종 판정: VERIFIED_WITH_NOTES
잔존 NOTES: pykrx 단일 호출 timeout MEDIUM (수정 불필요 — BACKLOG 후속) /
            배포 dependency 설치 주의 (정보 전달 NOTE)
```

**Commit chain** (origin/main 기준):
```
6810e697 feat(poc2-step6): minimal universe momentum scoring (pykrx 1m return)
2a225473 fix(poc2-step6): remove new API + new draft_payload key per Codex REJECTED
8bd76072 chore(poc2-step6): address Codex VERIFIED_WITH_NOTES — type + docstring touch-ups
```

**검증 흐름** (사용자 요청 시 참고):
- 1라운드 REJECTED → Fix 라운드 (2a225473) → VERIFIED_WITH_NOTES → NOTES 대응 (8bd76072) → 최종 통과.

**KS-10 임계 (최종 실측)**:
- 백엔드 max: 569 (`app/draft_message.py`) — trigger 650 미달, near ≥600 미달.
- 프론트 max: 515 (`frontend/app/components/EnrichedHoldingsSection.tsx`) — trigger 900 미달, near ≥850 미달.
- 테스트 max: 924 (`tests/test_holdings_message_text.py`) — trigger 1500 미달, near ≥1450 미달.
- **모든 트리거 + 근접 0건 유지**.

**테스트**: pytest 119 → 135 passed (Step6 회귀 16개 추가).

---

## 2. Step6 가 한 일 / 안 한 일 (한 줄 정리)

### 한 일
- pykrx 기반 **1개월 기간 수익률** (`one_month_return_pct = (latest/base - 1) × 100`) 1개를 universe 후보군에 적용.
- pykrx 호출은 단일 모듈 `app/price_history_pykrx.py` 만 사용 (KS-9 가드).
- bounded sync refresh: 20 items / 0.5s per-ticker delay / 30s budget. seed >20 hard fail. candidate 단위 실패 격리.
- `state/universe/universe_momentum_latest.json` 확장: refresh_status (ok/partial/failed) + data_source + score_basis + lookback/fetch_window + top_candidate (rank=1).
- GenerateDraft 가 universe latest artifact 를 읽어 `factor_signals` 안의 scope="universe" signal 1건으로 병합 (draft_payload 키 신설 0건 — BACKLOG `factor_signals 외 메타 키 추가 금지` 가드 준수).
- `[판단 사유]` 3번째 bullet ("외부 후보 점검") 추가. 헤더 1번 유지.
- UI: `UniverseRefreshPanel` 신설 — refresh 버튼 + 상태 패널. POST 응답을 frontend state 로 보관 (페이지 reload 시 비워짐).
- ASSUMPTIONS Q5 첫 실전 검증 기록 (단일 가격 기반 변수 채택 + 운영 사이클 결과로 변수 확장 여부 판단).

### 안 한 일 (의도적 미도입)
- 복합 점수체계 / MA / RSI / 고점 / 보너스 점수.
- Top N 정책 / BUY·SELL / 리밸런싱 / 후보 전체 UI 또는 Telegram 노출.
- pykrx 외 데이터 소스 / 자동 universe 수집 / 가격 히스토리 캐시 / DB / history 저장 / ML 학습 데이터.
- 신규 GET endpoint / 신규 draft_payload top-level 키 (Fix 라운드에서 제거 — BACKLOG 가드 준수).
- 자동 재시도 / scheduler / cron / background worker / 비동기 refresh.

---

## 3. universe 결과 데이터 흐름 요약 (다음 세션이 코드 읽기 전 빠른 이해용)

```
[사용자 명시 클릭]
   ↓
POST /universe/momentum/refresh                  ← app/api_universe.py (POST 1개)
   ↓
load_universe_seed()                             ← app/universe_seed.py
   → validate_seed_for_refresh(seed)             ← app/universe_refresh.py (20 items 가드)
   → run_universe_refresh(seed)                  ← per-ticker delay + 30s budget
     → fetch_one_month_basis(ticker, asof)       ← app/price_history_pykrx.py (단일 호출 모듈)
     → compute_one_month_return_pct(basis)
   → build_universe_momentum_result_scored()     ← app/momentum/universe_mode.py
   → save_latest_artifact(...)                   ← state/universe/universe_momentum_latest.json
   ↓
POST 응답 (summary + top_candidate + summary_reason_text)
   ↓
[frontend state 에 저장 — 페이지 reload 시 비워짐]

[별도 흐름] GenerateDraft (POST /runs/generate-from-holdings)
   ↓
_build_holdings_payload()                        ← app/draft.py
   → _build_universe_factor_signal(asof_iso)     ← universe latest artifact 읽기 (pykrx 미호출)
     → build_universe_signal_texts(...)          ← app/message_universe_bullet.py
   → factor_signals 리스트에 scope="universe" signal 1건 추가
   ↓
build_message_text()                             ← app/draft_message.py
   → _render_judgment_lines()
     → _factor_bullet()      → "- 보유 비중 영향: ..."
     → _momentum_bullet()    → "- 모멘텀 점검: ..."
     → _external_universe_bullet()  → "- 외부 후보 점검: ..."  (factor_signals scope="universe")
   ↓
Run.message_text (single source — preview / OCI handoff / Telegram 동일)
```

**draft_payload 키 (Step6 종결 시점)**: 1) title 2) asof 3) note 4) recommendations 5) factor_signals 6) momentum_result — **6개 정확**. universe 결과는 factor_signals 안 1 entry. 키 신설 0건.

---

## 4. Q5 첫 실전 검증 데이터 수집 가이드

ASSUMPTIONS.md Q5 의 첫 실전 데이터 수집 사이클이 본 Step6 종결 후 시작된다.

### 사용자 (= Q5 검증 대상 본인) 가 수집할 정보
1. **변수 채택의 직관 정합성**: pykrx 1개월 수익률 1개로 본 universe top 1건의 "추천 정도" 가 사용자 본인 판단과 얼마나 일치하는지.
2. **변수 한계 인식 시점**: 운영 중 "이 변수 1개로는 부족하다" 는 신호가 어디서 나오는지 (어떤 후보를 놓치거나 잘못 평가했는지).
3. **다음 변수 후보**: 한계 인식 시 추가하고 싶은 변수가 어떤 카테고리인지 (다른 가격 변수 / 거래량 / 섹터 / 외부 이벤트 등).

### 운영 기록 권장 위치
- 본 프로젝트 외부의 사용자 본인 메모 / 노트.
- 또는 ASSUMPTIONS.md Q5 항목에 분기 1회 직접 추가 기록.

### Q5 재검토 트리거 (ASSUMPTIONS.md 명시)
- 모멘텀 엔진 최소 운영 사이클 1회 완료.
- 위 (1)~(3) 데이터가 의미 있게 수집된 시점.

### 운영 사이클 1회 정의 (Step6 시점 작업 정의)
- 최소: 사용자가 universe seed 작성 1회 + refresh 1회 + 결과 해석 1회.
- 권장: 동일 seed 로 다른 asof 에 refresh 를 여러 번 수행해 결과 안정성도 관찰.

---

## 5. BACKLOG 잔존 후속 항목 (Step6 시점에 등록됨)

`docs/backlog/BACKLOG.md` 의 **STEP 6 향후 검토** 섹션에 5건:

1. **비동기 universe refresh** — 동기 sync API 한계 (응답 시간 30초). 재검토 트리거: 사용자 명시 피드백 발생 시.
2. **pykrx 가격 히스토리 캐시** — 반복 호출 부담. 재검토 트리거: 분당 N회 이상 호출 패턴 확인 시.
3. **universe 결과 history 저장** — 날짜별 누적 / Q5 변수 변경 이력 비교. 재검토 트리거: Q5 변수 추가 진입 시.
4. **ML dataset 저장 구조** — 변수 3개 이상 안정 운영 + 사용자 ML 진입 의지 명시 시.
5. **pykrx 외 fallback 데이터 소스** — pykrx 장애 운영 영향 명시 발생 시.

추가 (본 핸드오프 시점에 신규):
6. **pykrx 단일 호출 timeout 안전 처리** — 검증자(Codex) Step6 MEDIUM 지적. 30초 budget 은 *호출 전후* 체크라 단일 호출 hang 시 즉시 중단 불가. Windows POSIX signal 부재 + thread 누수 위험으로 별도 작업. 재검토 트리거: 실 운영 중 pykrx hang 발생 시.

---

## 6. 다음 STEP 후보 (사용자/설계자 결정 영역)

본 핸드오프는 개발자 입장에서 본 후보 나열일 뿐 — 우선순위는 사용자/설계자가 결정.

### 후보 A — universe momentum 변수 추가 (Q5 자연 확장)
- Step6 사이클 1회 결과 후 사용자가 "이 변수 1개로 부족" 판단 시.
- 신규 변수 1개를 같은 factor_signals scope="universe" 형태로 추가하거나, 별도 scope 신설.
- 복합 점수체계 진입 여부는 별도 의사결정 — Step6 §18 의 "복합 점수체계 금지" 가드 명시 해제 필요.

### 후보 B — 기존 BACKLOG 후속 처리
- 위 §5 의 6건 중 하나가 실 운영에서 트리거되면 진입.

### 후보 C — Cleanup STEP (KS-10 가드 예방 정비)
- 현재 트리거 0 + 근접 0 이라 즉시 필요 없음. 다만 단일 파일 누적 신호 (test_holdings_message_text.py 924) 가 다음 STEP 작업으로 1500 트리거에 근접하면 진입.

### 후보 D — 외부 후보 점검 영역 UX 보강
- 페이지 reload 시 상태 패널이 비워지는 사용성 trade-off 가 사용자에게 불편을 주면 별도 STEP.
- 단, 이 경우에도 신규 GET endpoint 도입은 명시 승인 필요 (BACKLOG 가드 정신 — 가능하면 frontend state persistence / localStorage 등 다른 방식).

---

## 7. 새 세션 진입자 체크리스트

다음 세션에서 본 프로젝트를 이어받을 때 반드시 수행:

1. CLAUDE.md §1 의 기반 문서 5개 순서대로 읽기:
   - `docs/PROJECT_ORIGIN_INTENT.md` — 성공 기준 3개 / 절대 하지 않을 것
   - `docs/KILL_SWITCHES.md` — KS-1~10 + 이식 금지
   - `docs/ASSUMPTIONS.md` — Q1 / Q4 / Q5 (OPEN 3건)
   - `CLAUDE.md` — 개발자 / 검증자 / 설계자 역할 분담 + 7섹션 보고서 형식
   - 본 문서 (POC2_STEP6_CONCLUSION_AND_NEXT_HANDOFF.md)

2. STATE_LATEST 읽기:
   - `docs/STATE_LATEST.md` (canonical, 2026-06-07 정리 이후) — 현재 상태 / history 요약 / index.
   - `docs/handoff/STATE_LATEST_ARCHIVE.md` — Step6 종결 + 검증 이력 + KS-10 임계 실측 (시간순 누적 본문 보존).

3. BACKLOG 읽기:
   - `docs/backlog/BACKLOG.md` 의 **STEP 6 향후 검토** 섹션 5건 + 본 문서 §5 의 신규 항목 1건.

4. 코드 진입 전 최소 확인:
   - `git log --oneline -10` — 최근 commit 흐름 (Step6 3건이 origin/main 에 있어야 함).
   - 본 핸드오프 §3 의 데이터 흐름 다이어그램 1번 정독.

5. "기반 문서 확인 완료" 응답 후 작업 착수 (CLAUDE.md §1 절차).

---

## 8. 본 세션 종료 시점의 자체 평가 (개발자 입장)

검증자가 잡지 못한 / 사용자가 알아야 할 한계:

- **pykrx 호출 안정성 미검증**: 본 세션의 모든 테스트는 `tests/conftest.py` 의 stub fetcher 로 대체. 실제 pykrx 호출은 사용자의 첫 운영 refresh 클릭이 첫 검증 사이클.
- **UI 페이지 reload 사용성**: Fix 라운드에서 GET endpoint 제거하면서 UniverseRefreshPanel 의 상태 패널은 refresh 직후만 채워진다. 사용자가 페이지 reload 후 "어디 갔지?" 라 느낄 가능성 — 안내 문구로 부분 mitigate 했으나 완전한 해소는 아님.
- **factor_signals scope 확장 (universe) 의 일반화 위험**: Step6 Fix 라운드에서 universe scope 를 추가한 것은 사용자(설계자) 명시 지시에 따른 결정. 향후 다른 새 입력 (예: 외부 이벤트) 이 추가될 때 "scope 만 늘리면 된다" 는 일반 허용으로 해석되지 않도록 BACKLOG 가드 명시.
- **세션 누적 컨텍스트 권고**: 본 세션은 Step5C ~ Step5D ~ Step5D-2 (1차 + Final) ~ Step6 (1차 + Fix + NOTES 대응) 까지 누적. 다음 STEP 진입은 새 세션에서 기반 문서 5개 재읽기 권장 (의사결정 편향 누적 회피).

---

문서 끝. 다음 세션 진입자께서 본 핸드오프를 읽고 위 §7 체크리스트를 따라 주시기 바랍니다.
