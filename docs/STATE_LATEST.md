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
- POC2-Step4 설계서 신규 + ASSUMPTIONS Q3→A-5 이동 + Q5 OPEN 신규 등록 반영.
- 직전 설계 문서:
  [docs/handoff/POC2_STEP4_MOMENTUM_ENGINE_DIRECTION_AND_Q4_BOUNDARY_DESIGN.md](handoff/POC2_STEP4_MOMENTUM_ENGINE_DIRECTION_AND_Q4_BOUNDARY_DESIGN.md).
- 직전 종결 문서:
  [docs/handoff/POC2_STEP3_CONCLUSION_AND_NEXT_HANDOFF.md](handoff/POC2_STEP3_CONCLUSION_AND_NEXT_HANDOFF.md).
