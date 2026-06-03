"""POC2 — Holdings × Market Discovery Evidence 판단 사유 bullet helper (2026-06-03).

지시문 §5.10 — GenerateDraft 의 [판단 사유] 섹션에 "보유 vs 시장 evidence" 1줄을
추가하기 위한 텍스트 빌더. draft_message 가 본 helper 를 호출해 bullet 1줄을
조립한다.

금지 표현 (지시문 §5.10):
- 매수 / 매도 / 교체 / 진입 / 비중 확대·축소 / 탈락 / 대표 ETF.
본 helper 는 일치 수 / 미일치 수 / unavailable 수 + (가능 시) 첫 후보의 단기 흐름
1건만 표시한다.
"""

from __future__ import annotations

from typing import Any, Optional

JUDGMENT_LABEL = "보유 vs 시장"


def _format_count_section(summary: dict[str, Any]) -> Optional[str]:
    total = int(summary.get("total_holdings_count") or 0)
    if total == 0:
        return None
    matched = int(summary.get("matched_topn_count") or 0)
    not_in = int(summary.get("not_in_current_topn_count") or 0)
    unavail = int(summary.get("evidence_unavailable_count") or 0)
    parts = [f"일치 {matched}건"]
    if not_in > 0:
        parts.append(f"TOP N 외 {not_in}건")
    if unavail > 0:
        parts.append(f"시장 비교 미가용 {unavail}건")
    return "보유 {0}건 중 ".format(total) + " / ".join(parts)


def _format_short_term_excerpt(holdings: list[dict[str, Any]]) -> Optional[str]:
    """matched_topn_candidate 중 첫 번째의 단기 흐름 1건 (있을 때만)."""
    for h in holdings:
        topn_match = h.get("topn_match") or {}
        if topn_match.get("status") != "matched_topn_candidate":
            continue
        stm = h.get("short_term_momentum") or {}
        if stm.get("status") != "ok":
            continue
        excess_20d = stm.get("excess_vs_kodex200_20d_pctp")
        if not isinstance(excess_20d, (int, float)):
            continue
        name = h.get("name") or h.get("ticker") or ""
        return f"{name} 20거래일 KODEX200 대비 {excess_20d:+.2f}%p"
    return None


def build_holdings_market_evidence_bullet(snapshot: Any) -> Optional[str]:
    """snapshot dict → draft_message bullet 1줄. 매수/매도 판단 표현 X.

    snapshot 이 dict 가 아니거나 holdings 가 비어있으면 None (bullet 미추가).
    """
    if not isinstance(snapshot, dict):
        return None
    holdings = snapshot.get("holdings")
    if not isinstance(holdings, list) or not holdings:
        return None
    summary = snapshot.get("summary") or {}

    count_part = _format_count_section(summary)
    if count_part is None:
        return None

    stm_part = _format_short_term_excerpt(holdings)
    body = count_part if stm_part is None else f"{count_part}; {stm_part}"
    return f"- {JUDGMENT_LABEL}: {body}"


def render_holdings_market_evidence_bullet(payload: Any) -> Optional[str]:
    """draft_payload.factor_signals 중 scope="holdings_market_evidence" signal 을
    찾아 [판단 사유] 섹션에 넣을 bullet 1줄을 반환.

    draft_message._render_judgment_lines 가 호출. payload 가 dict 가 아니거나
    signal 이 없으면 None (bullet 미추가). 매수/매도 표현 X.
    """
    if not isinstance(payload, dict):
        return None
    factor_signals = payload.get("factor_signals")
    if not isinstance(factor_signals, list):
        return None
    for sig in factor_signals:
        if not isinstance(sig, dict):
            continue
        if sig.get("scope") != "holdings_market_evidence":
            continue
        if not sig.get("is_available"):
            continue
        text = sig.get("reason_text")
        if not isinstance(text, str) or not text.strip():
            continue
        label = sig.get("factor_name") or JUDGMENT_LABEL
        return f"- {label}: {text}"
    return None


def build_holdings_market_evidence_factor_signal(
    snapshot: Any,
    *,
    asof_iso: str,
) -> Optional[dict[str, Any]]:
    """draft_payload.factor_signals 에 추가할 signal 1건.

    scope="holdings_market_evidence" — 기존 universe / falling 패턴과 동일.
    snapshot 이 비정상이거나 bullet 본문이 비어있으면 None (signal 미추가).
    """
    bullet = build_holdings_market_evidence_bullet(snapshot)
    if bullet is None:
        return None
    # bullet 본문 ("- 라벨: 본문") 에서 본문만 추출 — factor_signals 의 reason_text 규약 정합.
    sep = ": "
    if sep in bullet:
        reason_text = bullet.split(sep, 1)[1]
    else:
        reason_text = bullet
    summary = snapshot.get("summary") or {}
    return {
        "factor_id": "holdings_market_evidence",
        "factor_name": JUDGMENT_LABEL,
        "scope": "holdings_market_evidence",
        "is_available": True,
        "value": None,
        "unit": "",
        "reason_text": reason_text,
        "fallback_text": None,
        "input_basis": {
            "total_holdings": int(summary.get("total_holdings_count") or 0),
            "matched_topn": int(summary.get("matched_topn_count") or 0),
            "not_in_current_topn": int(summary.get("not_in_current_topn_count") or 0),
            "constituents_available": int(
                summary.get("constituents_available_count") or 0
            ),
            "market_asof": snapshot.get("market_asof"),
        },
        "computed_at": asof_iso,
    }
