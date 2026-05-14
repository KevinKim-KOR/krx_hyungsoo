# STATE_LATEST.md (포인터)

본 프로젝트의 STATE_LATEST 단일 SSOT 위치는 다음과 같다.

→ [docs/handoff/STATE_LATEST.md](handoff/STATE_LATEST.md)

이 파일(`docs/STATE_LATEST.md`) 은 지시문이 `docs/STATE_LATEST.md` 경로로 들어와도
실제 SSOT 와 일치하도록 유지하기 위한 포인터다. **최근 갱신 기록 / 직전 상태 /
세부 내용은 본 파일에 작성하지 않는다 — 모두 위 SSOT(`docs/handoff/STATE_LATEST.md`)
에만 작성한다.**

배경:
- POC1 시점부터 종결 문서·핸드오프·STATE 스냅샷은 모두 `docs/handoff/` 하위에 모아왔다.
- POC2-Step3 설계자 지시문은 `docs/STATE_LATEST.md` 표기를 사용했고, 검증자(Codex)
  REJECTED 1라운드에서 경로 불일치가 지적되었다.
- SSOT 자체를 옮기면 기존 4건 이상의 종결 문서 / 핸드오프 / 다음 세션 진입 절차가
  모두 깨진다 — 위험 비대칭.
- 따라서 `docs/STATE_LATEST.md` 를 본 포인터 stub 으로 두고, 실제 갱신은
  `docs/handoff/STATE_LATEST.md` 에서만 한다.

규칙 (B 방향 전환 정합성 보정 — 2026-05-14):
- 본 파일에 "최근 갱신" / "직전 상태" / "Step N 요약" 등 어떤 이력 블록도 추가하지
  않는다. 이력과 현재 상태는 모두 SSOT 한 곳에서만 관리한다.
- 본 포인터 stub 의 본문 변경은 포인터 경로 정합성 보정 또는 본 규칙 갱신에 한한다.
