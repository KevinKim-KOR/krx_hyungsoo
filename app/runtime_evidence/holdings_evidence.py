"""Holdings evidence 판정 + 사용자용 문장 생성 (지시문 §5.2 · §5.5~§5.8).

Cleanup / FIX r7 Round 2 에서 `app/runtime_evidence_composer.py` 로부터 분리.
설계자 확정본 유지:
- matched_topn_candidate → Holdings evidence.
- not_in_current_topn (정상 TOP-N 조회 결과) → Holdings evidence.
- returns / excess_return / short_term_momentum / constituents_overlap 실제 수치 → evidence.
- TOP-N 조회 실패 (per-holding topn_match.status 모두 unavailable) → holdings_snapshot=unavailable.
"""

from __future__ import annotations

from typing import Any, Optional

from app.runtime_evidence.constants import fmt_pct


def signal_topn_reader_failed(evidence_payload: dict[str, Any]) -> bool:
    """TOP-N reader 실패 판정 (per-holding topn_match.status 신호).

    설계자 확정본 (FIX r5): builder 는 topn_status != "ok" 여도 입력 asof 를
    반환 dict 의 market_asof 로 보존할 수 있으므로 market_asof 존재만으로는
    fail-open. per-holding topn_match.status ∈ {matched_topn_candidate,
    not_in_current_topn} 신호가 하나도 없으면 TOP-N reader 실패.

    holdings 자체가 비어 있으면 이 판정이 아니라 downstream no_contentful_fact
    로 흘려보낸다 (여기서는 False 반환).
    """
    holdings_out_list = evidence_payload.get("holdings") or []
    if not holdings_out_list:
        return False
    ok_signal_count = sum(
        1
        for h in holdings_out_list
        if (h.get("topn_match") or {}).get("status")
        in ("matched_topn_candidate", "not_in_current_topn")
    )
    return ok_signal_count == 0


def _build_holding_line_parts(
    h_out: dict[str, Any],
) -> tuple[list[str], bool]:
    """개별 holding evidence 문장 조각 리스트 + evidence 존재 여부."""
    line_parts: list[str] = []
    has_evidence_item = False

    returns_payload = h_out.get("returns") or {}
    if returns_payload.get("status") in ("ok", "partial"):
        r1m = fmt_pct(returns_payload.get("one_month_return_pct"))
        r3m = fmt_pct(returns_payload.get("three_month_return_pct"))
        frag = []
        if r1m:
            frag.append(f"1개월 {r1m}")
        if r3m:
            frag.append(f"3개월 {r3m}")
        if frag:
            line_parts.append(" / ".join(frag))
            has_evidence_item = True

    excess_payload = h_out.get("excess_return") or {}
    if excess_payload.get("status") in ("ok", "partial"):
        exc_1m = fmt_pct(excess_payload.get("vs_kodex200_1m_pctp"))
        exc_3m = fmt_pct(excess_payload.get("vs_kodex200_3m_pctp"))
        frag2 = []
        if exc_1m:
            frag2.append(f"1개월 초과 {exc_1m}")
        if exc_3m:
            frag2.append(f"3개월 초과 {exc_3m}")
        if frag2:
            line_parts.append("KODEX200 대비 " + " / ".join(frag2))
            has_evidence_item = True

    topn_match = h_out.get("topn_match") or {}
    match_status = topn_match.get("status")
    if match_status == "matched_topn_candidate":
        rank = topn_match.get("rank")
        if rank is not None:
            line_parts.append(f"Market Discovery TOP{rank}")
            has_evidence_item = True
    elif match_status == "not_in_current_topn":
        # 설계자 확정본 Q3: 정상 조회 결과 TOP-N 에 없음도 evidence.
        line_parts.append("현재 Market Discovery TOP-N 미포함")
        has_evidence_item = True

    # 단기 흐름 (builder 계약: STATUS_OK "ok" / STATUS_PARTIAL "partial",
    # 필드 return_20d_pct).
    stm = h_out.get("short_term_momentum") or {}
    if stm.get("status") in ("ok", "partial"):
        stm_20d = fmt_pct(stm.get("return_20d_pct"))
        if stm_20d:
            line_parts.append(f"최근 20거래일 {stm_20d}")
            has_evidence_item = True

    # 구성종목 overlap (builder 계약: status=CONSTITUENTS_OK("ok") ·
    # 필드 overlap_with_market_core = list[dict]).
    constituents = h_out.get("constituents_overlap") or {}
    if constituents.get("status") == "ok":
        overlap_items = constituents.get("overlap_with_market_core") or []
        overlap_names = [
            (it.get("name") or it.get("ticker"))
            for it in overlap_items
            if isinstance(it, dict) and (it.get("name") or it.get("ticker"))
        ]
        if overlap_names:
            preview = ", ".join(overlap_names[: min(3, len(overlap_names))])
            line_parts.append(f"구성종목 반복 핵심: {preview}")
            has_evidence_item = True

    return line_parts, has_evidence_item


def build_holdings_facts(
    evidence_payload: dict[str, Any],
    market_asof: Optional[str],
) -> tuple[list[str], dict[str, int]]:
    """Holdings evidence 문장 리스트 + 카운터.

    반환:
      notes: 사용자용 문장 리스트.
      counters: {
        "holdings_evidence_item_count": ...,
        "holdings_selection_result_count": ...,
        "holdings_contentful_fact_count": ...,
      }
    """
    notes: list[str] = []
    evidence_item_count = 0
    selection_count = 0
    fact_count = 0

    for h_out in evidence_payload.get("holdings") or []:
        name = h_out.get("name") or h_out.get("ticker")
        line_parts, has_evidence_item = _build_holding_line_parts(h_out)
        if has_evidence_item:
            evidence_item_count += 1
        if line_parts and name and has_evidence_item and market_asof:
            line_text = f"{name} ({market_asof} 기준): " + " · ".join(line_parts) + "."
            notes.append(line_text)
            fact_count += 1
            selection_count += 1

    return notes, {
        "holdings_evidence_item_count": evidence_item_count,
        "holdings_selection_result_count": selection_count,
        "holdings_contentful_fact_count": fact_count,
    }
