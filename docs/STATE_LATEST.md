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
- POC2-Step5D-2 Cleanup — Step5D 1차 후 남은 KS-10 트리거 2건 해소.
  · test_holdings_draft_flow.py 1,982→244라인 (3개 신규 도메인 파일로 분리)
  · RunPanel.tsx 905→606라인 (EvidenceDetails.tsx 추출)
  · pytest 119 passed 유지. KS-10 모든 트리거 해소.
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
