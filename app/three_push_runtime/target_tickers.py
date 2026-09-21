"""Runtime price refresh 대상 ticker 수집 helper (Low-Frequency Push v1 A+).

Fail-Closed: 파일 없음/파싱 오류/공용 validator 계약 위반은 raise. 호출자
(Runner) 가 즉시 failed 종료한다.

빈 리스트 반환 케이스:
- refresh 불필요 push_kind (예: market_briefing).
- spike_or_falling_alert 이면서 artifact.candidates == [] (validator 통과 ·
  no-signal 정상 시나리오).

POC3-02C-OPS-02 — `holdings_risk_alert` 만 **보유 ∪ 승인된 사업군 대표**를 본다.
전체 ETF 장중 조회는 금지다(설계 §2). 사업군 조회 실패는 보유 경로를 막지
않는다(설계 §9) — 아래 helper 들이 전부 흡수한다.
"""

from __future__ import annotations

import json
from typing import Any, Optional


def _active_sectors() -> list[dict[str, Any]]:
    """활성 승인 버전의 사업군 목록. **실패하거나 비활성이면 빈 목록.**

    `intraday_alert_policy.enabled` 가 `false` 면 **대표를 한 건도 돌려주지
    않는다.** 본문만 숨기고 27종목을 조회하면 비활성화가 아니다
    (설계자 §14-3). 합집합 53종목 조회는 `enabled=true` 일 때만 허용한다.

    config 부재·비활성·손상을 전부 여기서 흡수한다. 사업군 경로 실패가 보유
    급락 경로를 막으면 안 된다(설계 §9).
    """
    try:
        from app.intraday_config import store

        active = store.get_active()
        if not active:
            return []
        payload = json.loads(active["payload_json"])
        policy = payload.get("intraday_alert_policy") or {}
        if not policy.get("enabled"):
            return []
        uni = payload.get("sector_representative_universe") or {}
        sectors = uni.get("sectors")
        return sectors if isinstance(sectors, list) else []
    except Exception:  # noqa: BLE001 - 보유 경로를 절대 막지 않는다
        return []


def sector_representative_tickers() -> list[str]:
    """대표 ETF ticker 목록. 대체는 넣지 않는다.

    대체는 대표가 **ticker 단위로 실패했을 때만** 한 번 조회한다
    (설계자 §13-4 재귀 대체 금지).
    """
    out: list[str] = []
    for s in _active_sectors():
        t = ((s or {}).get("representative") or {}).get("ticker")
        if isinstance(t, str) and t:
            out.append(t)
    return out


def alternate_ticker_for(ticker: str) -> Optional[str]:
    """대표 `ticker` 의 대체 ETF. 없으면 `None`. **1단계만** 찾는다."""
    for s in _active_sectors():
        rep = ((s or {}).get("representative") or {}).get("ticker")
        if rep == ticker:
            alt = ((s or {}).get("alternate") or {}).get("ticker")
            return alt if isinstance(alt, str) and alt else None
    return None


def union_with_sector_reps(held: list[str]) -> list[str]:
    """보유 ∪ 대표. **같은 ticker 는 한 번만**(설계 §2).

    보유 원장은 다계좌라 같은 ticker 가 여러 행으로 온다(실측 32행 / 고유 29).
    `holdings_briefing` 은 기존대로 행 수를 그대로 넘기지만, 장중 경로는 설계
    §2 가 중복 조회를 명시적으로 금지하므로 여기서 제거한다.

    완전성 판정은 `attempted`(행 수) 가 아니라 `target_tickers`/`success_tickers`
    **집합**으로 하므로(설계자 확정 2026-09-05) 중복 제거가 그 계약을 깨지 않는다.
    """
    out: list[str] = []
    seen: set[str] = set()
    for t in list(held) + sector_representative_tickers():
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    return out


def collect_target_tickers(push_kind: str) -> list[str]:
    """`holdings_risk_alert` 는 보유 원장 + 승인된 사업군 대표를 본다.

    `holdings_briefing` 은 **보유만** 본다 — 브리핑에 사업군을 넣지 않는다.
    기존 spike 의 universe 후보를 쓰지 않는다 (OPS-01C `REJECT`).
    """
    if push_kind in ("holdings_briefing", "holdings_risk_alert"):
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
        held = [h.ticker for h in hs if isinstance(h.ticker, str)]
        if push_kind == "holdings_risk_alert":
            return union_with_sector_reps(held)
        return held
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
