"""Runtime price refresh 대상 ticker 수집 helper (Low-Frequency Push v1 A+).

Fail-Closed: 파일 없음/파싱 오류/공용 validator 계약 위반은 raise. 호출자
(Runner) 가 즉시 failed 종료한다.

빈 리스트 반환 케이스:
- refresh 불필요 push_kind (예: market_briefing).
- spike_or_falling_alert 이면서 artifact.candidates == [] (validator 통과 ·
  no-signal 정상 시나리오).
"""

from __future__ import annotations


def collect_target_tickers(push_kind: str) -> list[str]:
    if push_kind == "holdings_briefing":
        from app import holdings as _holdings_mod

        # A+ 재정정: holdings.load() 는 파일 부재 시 [] 반환. 이 경우 attempted=0
        # 이 되어 가격 실패 guard 를 우회하므로 명시적으로 raise 한다. Fail-Closed.
        if not _holdings_mod.HOLDINGS_FILE.exists():
            raise RuntimeError(
                f"holdings source missing: {_holdings_mod.HOLDINGS_FILE}"
            )
        hs = _holdings_mod.load()
        if not hs:
            raise RuntimeError("holdings source is empty")
        return [h.ticker for h in hs if isinstance(h.ticker, str)]
    if push_kind == "spike_or_falling_alert":
        from app.draft_three_push import _load_universe_artifact_for_spike
        from app.universe_bootstrap.artifact_validator import validate_artifact

        art = _load_universe_artifact_for_spike()
        # A+ 재정정 (검증자 라운드 6 지적 · 인접 계약 정합):
        # Universe artifact 판정은 Publication/Runtime composer 가 공유하는 단일
        # 계약 validator (validate_artifact) 를 재사용한다. target_tickers 자체
        # 축약 검증을 재구현하면 공용 validator 와 판정이 갈라진다 (미채점 후보
        # ticker 미검사 · 채점 후보 score_value 미검사 등). semantic-invalid 는
        # 즉시 raise → Runner 가 failed 종료 (Fail-Closed).
        valid, reason, _meta = validate_artifact(art)
        if not valid:
            raise RuntimeError(f"universe artifact invalid: {reason}")
        # validate_artifact 통과 후에는 candidates 가 list 이고 각 원소가
        # {ticker(str), score_result{is_scored(bool), (scored 시) score_value 유한}}
        # 계약을 만족함이 보장된다. scored 후보의 ticker 만 수집.
        out: list[str] = []
        for c in art.get("candidates") or []:
            sr = c.get("score_result") or {}
            if sr.get("is_scored") is True:
                out.append(c["ticker"])
        # out 은 두 경우에 빈 list 일 수 있다:
        #   - candidates == [] (validator 는 빈 리스트를 valid 로 통과) → no-signal
        #     정상 시나리오.
        # candidates 가 비어있지 않은데 scored 0건인 경우는 validator 가 이미
        # artifact_status_scored_inconsistency 로 차단하므로 여기 도달하지 않는다.
        return out
    return []
