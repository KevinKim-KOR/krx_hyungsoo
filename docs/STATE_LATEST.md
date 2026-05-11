# STATE_LATEST.md (포인터)

본 프로젝트의 STATE_LATEST 단일 SSOT 위치는 다음과 같다.

→ [docs/handoff/STATE_LATEST.md](handoff/STATE_LATEST.md)

이 파일(`docs/STATE_LATEST.md`) 은 지시문이 `docs/STATE_LATEST.md` 경로로 들어와도
실제 SSOT 와 일치하도록 유지하기 위한 포인터다. 새 갱신 내용은 위 SSOT 경로에 작성하고
이 파일은 그대로 둔다.

배경:
- POC1 시점부터 종결 문서·핸드오프·STATE 스냅샷은 모두 `docs/handoff/` 하위에 모아왔다.
- POC2-Step3 설계자 지시문은 `docs/STATE_LATEST.md` 표기를 사용했고, 검증자(Codex)
  REJECTED 1라운드에서 경로 불일치가 지적되었다.
- SSOT 자체를 옮기면 기존 4건 이상의 종결 문서 / 핸드오프 / 다음 세션 진입 절차가
  모두 깨진다 — 위험 비대칭.
- 따라서 `docs/STATE_LATEST.md` 를 본 포인터 stub 으로 두고, 실제 갱신은
  `docs/handoff/STATE_LATEST.md` 에서만 한다.

최근 갱신:
- POC2-Step6 Fix 라운드 (2026-05-11) — 검증자(Codex) 1차 REJECTED 대응.
  · __init__.py docstring 을 Step6 현재 구조로 정정 (universe 결과는 factor_signals
    안의 scope="universe" signal 로 표현 명시).
  · GET /universe/momentum/latest endpoint 제거 (신규 API 추가 금지 가드 준수).
    POST refresh 응답에 summary_reason_text / top_candidate 필드를 추가하여 UI 가
    상태 패널 표시 가능.
  · draft_payload.external_universe_check 키 제거 (BACKLOG `factor_signals 외 메타 키
    추가 금지` 가드 준수). universe 결과는 기존 factor_signals 안의 scope="universe"
    signal 1건으로 표현 — 사용자(설계자) 결정.
  · UI: UniverseRefreshPanel 의 mount 시 GET 호출 제거 → POST 응답을 frontend state
    로 보관. 페이지 reload 시 state 비워짐 (사용성 trade-off 수용).
  · pytest 119 → 135 passed (Step6 회귀 16개). black / flake8 / Next.js build PASS.
  · KS-10 임계: 백엔드 max 569 / 프론트 max 515 / 테스트 max 924 — 트리거 0 + 근접 0.
  · draft_payload 키 신설 0건 (Step6 Fix 후) — 기존 6개 키만 존재.
- POC2-Step6 (2026-05-11) — Universe Momentum Formula Minimal Scoring.
  · 점검값: pykrx 기반 1개월 기간 수익률 (one_month_return_pct).
  · pykrx 호출은 app/price_history_pykrx.py 1개 모듈만. bounded sync refresh
    (20 items / 0.5s delay / 30s budget) + candidate 단위 실패 격리.
  · POST /universe/momentum/refresh → ok / partial / failed 상태 + top_candidate
    저장 (latest 1건 덮어쓰기). DB / history / 가격 캐시 모두 미도입.
  · GET /universe/momentum/latest → UI 상태 패널용 최신 artifact 조회.
  · GenerateDraft 가 latest artifact 의 top_candidate 를 draft_payload.external_universe_check
    로 병합. pykrx 직접 호출 0건 (AC-20).
  · [판단 사유] 3번째 bullet 추가 — 보유 비중 영향 / 모멘텀 점검 / 외부 후보 점검.
    헤더 1번 유지. universe 후보 전체 목록 미노출.
  · UniverseRefreshPanel 추가 (HoldingsClient 아래 별도 영역).
  · 검증: pytest 136 passed (Step6 회귀 17개 추가) / black / flake8 / Next.js build PASS.
  · KS-10 임계: 백엔드 max 536 / 프론트 max 515 / 테스트 max 924 — 트리거 0 + 근접 0 유지.
  · ASSUMPTIONS Q5 첫 실전 검증 기록 추가 (OPEN 유지).
- POC2-Step5D-2 Final Round (2026-05-10) — 모든 KS-10 트리거 + 근접(50라인 이내) 0건 동시 달성.
  · HoldingsClient.tsx 906→394라인 (트리거 3 해소). EnrichedHoldingsSection.tsx 신규 (515라인) 로 시세평가 compact UI 책임 분리.
  · draft_message.py 600→525라인 (트리거 4 근접 해소). message_helpers.py 신규 (124라인) 로 leaf format / 항목 식별 helpers 분리. 공개 API 동일 import 경로 유지.
  · RunPanel.tsx 606→444라인. holdings_view.ts 신규 (186라인) 로 RunPanel ↔ EvidenceDetails 양방향 import 해소 (단일 lib 출처).
  · 검증: pytest 119 passed (1.16s) / black / flake8 / TypeScript build / Next.js lint 모두 PASS.
  · message_text / UI / Telegram payload / [판단 사유] 헤더 1번 + 2 bullets 모두 동일 (본문 이동만, 로직 변경 0).
  · KS-10 임계 (실측): 백엔드 max 557 (api.py) / 프론트 max 515 (EnrichedHoldingsSection) / 테스트 max 924 — 트리거 0 + 근접 0.
  · commit: e9bd502e.
- POC2-Step5D-2 Cleanup (1차) — Step5D 1차 후 §1.2 명시 KS-10 트리거 2건 해소.
  · test_holdings_draft_flow.py 1,982→244라인 (3개 신규 도메인 파일로 분리)
  · RunPanel.tsx 905→606라인 (EvidenceDetails.tsx 추출)
  · pytest 119 passed 유지.
- POC2-Step5D Cleanup (1차) — 단일 파일 책임 누적 재발 신호 대응.
  · 백엔드 테스트 파일 분리 (test_poc1_loop.py 3,452→298라인 + conftest.py/_helpers.py + 4개 신규 파일)
  · 프론트 RunPanel.tsx 책임 분리 (JudgmentReasonSection.tsx + MomentumCandidatesSection.tsx)
  · KILL_SWITCHES KS-10 (단일 파일 라인 수 / 책임 누적 임계 초과) 가드 추가
- 직전 구현: POC2-Step5C — universe mode minimal candidate source.
  manual seed → score 없는 universe momentum_result → state/universe/universe_momentum_latest.json
  (latest 1건 덮어쓰기). 실행 트리거: POST /universe/momentum/refresh 수동 backend API 1곳.
  draft_payload / message_text / UI / Telegram 영향 없음. asof 필수 + 미래 차단 + 30일 staleness.
- 직전 구현: POC2-Step5B (holdings mode placeholder, pnl_rate, draft_payload.momentum_result).
- 직전 설계 문서:
  [docs/handoff/POC2_STEP5A_MOMENTUM_ENGINE_BOUNDARY_AND_MINIMAL_CONTRACT.md](handoff/POC2_STEP5A_MOMENTUM_ENGINE_BOUNDARY_AND_MINIMAL_CONTRACT.md).
- 직전직전 설계 문서:
  [docs/handoff/POC2_STEP4_MOMENTUM_ENGINE_DIRECTION_AND_Q4_BOUNDARY_DESIGN.md](handoff/POC2_STEP4_MOMENTUM_ENGINE_DIRECTION_AND_Q4_BOUNDARY_DESIGN.md).
- 직전 종결 문서:
  [docs/handoff/POC2_STEP3_CONCLUSION_AND_NEXT_HANDOFF.md](handoff/POC2_STEP3_CONCLUSION_AND_NEXT_HANDOFF.md).
