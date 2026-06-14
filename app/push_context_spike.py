"""POC2 Cleanup — push_context spike_view + 관련 line helper 분리 (2026-06-14).

3-PUSH Message Text Runtime Evidence 반영 STEP 의 KS-10 trigger 해소를 위해
`app/push_context.py` 의 spike 책임을 본 모듈로 분리. 산식 / 문구 / 데이터 계약
변경 0건.

본 모듈은 다음 공개 helper 를 제공한다:

- `build_spike_view` — PUSH-3 spike_view dict.
- `spike_view_lines` — PUSH-3 message builder 용 풍부 1줄/item.
"""

from __future__ import annotations

from typing import Any, Optional

from app.push_context_format import (
    _candidate_name,
    _candidate_return_pct,
    _candidate_ticker,
    _fmt_pct,
    _topn_candidates,
)
from app.push_context_holdings import _holdings_overlap_tickers


def _universe_momentum_items(um: dict[str, Any]) -> list[dict[str, Any]]:
    """universe_momentum_snapshot 의 summary.top_candidate / falling_candidate 를
    추출해 score / 방향 / reason 을 갖는 dict 리스트로 정규화."""
    out: list[dict[str, Any]] = []
    summary = um.get("summary") if isinstance(um, dict) else None
    if not isinstance(summary, dict):
        return []
    for key, direction in (("top_candidate", "up"), ("falling_candidate", "down")):
        cand = summary.get(key)
        if not isinstance(cand, dict):
            continue
        score = (cand.get("score_result") or {}).get("score_value")
        if not isinstance(score, (int, float)):
            continue
        phb = cand.get("price_history_basis") or {}
        basis_date = phb.get("latest_date") if isinstance(phb, dict) else None
        out.append(
            {
                "ticker": cand.get("ticker") or "",
                "name": cand.get("name") or "",
                "score_value": float(score),
                "direction": direction,
                "basis_date": basis_date,
                "evidence_refs": [
                    f"pc_evidence_snapshot.universe_momentum_snapshot.summary.{key}"
                ],
            }
        )
    return out


def build_spike_view(
    *,
    pc_evidence: dict[str, Any],
    runtime_snapshot: dict[str, Any],
) -> dict[str, Any]:
    """PUSH-3 spike_view — universe_momentum.top_candidate + falling_candidate +
    market_discovery candidates 중 절대 수익률 큰 항목들의 관찰 묶음.

    items 가 1건도 없으면 빈 dict 반환.

    각 item 에 수익률 근거 / 방향 / data_quality / holdings overlap 여부를 채움.
    """
    um = pc_evidence.get("universe_momentum_snapshot") or {}
    items: list[dict[str, Any]] = _universe_momentum_items(um)

    # Market Discovery candidates 중 절대 수익률이 큰 항목도 함께 노출.
    md = pc_evidence.get("market_discovery_snapshot") or {}
    md_candidates = _topn_candidates(md)
    md_enriched: list[tuple[dict[str, Any], float]] = []
    for c in md_candidates:
        p = _candidate_return_pct(c)
        if p is None:
            continue
        md_enriched.append((c, p))
    md_enriched.sort(key=lambda x: abs(x[1]), reverse=True)

    holdings_tickers = _holdings_overlap_tickers(pc_evidence)
    seen_tickers: set[str] = {it["ticker"] for it in items if it.get("ticker")}

    for c, p in md_enriched[:5]:
        t = _candidate_ticker(c)
        if not t or t in seen_tickers:
            continue
        seen_tickers.add(t)
        returns = c.get("returns") if isinstance(c.get("returns"), dict) else {}
        return_1d = (
            (returns.get("daily") or {}).get("return_pct")
            if isinstance(returns, dict)
            else None
        )
        return_5d = None  # 별도 입력 없음.
        return_20d = (
            (returns.get("one_month") or {}).get("return_pct")
            if isinstance(returns, dict)
            else None
        )
        dq = c.get("data_quality_flag")
        dq_flags = [dq] if isinstance(dq, str) and dq.strip() else []
        direction = "up" if p >= 0 else "down"
        items.append(
            {
                "ticker": t,
                "name": _candidate_name(c),
                "direction": direction,
                "return_1d_pct": (
                    float(return_1d) if isinstance(return_1d, (int, float)) else None
                ),
                "return_5d_pct": (
                    float(return_5d) if isinstance(return_5d, (int, float)) else None
                ),
                "return_20d_pct": (
                    float(return_20d) * 100.0
                    if isinstance(return_20d, (int, float)) and abs(return_20d) < 1.5
                    else (
                        float(return_20d)
                        if isinstance(return_20d, (int, float))
                        else None
                    )
                ),
                "selected_return_pct": p,
                "data_quality_flags": dq_flags,
                "holdings_overlap": t in holdings_tickers,
                "evidence_refs": [
                    f"pc_evidence_snapshot.market_discovery_snapshot.candidates[{t}]"
                ],
            }
        )

    # universe_momentum item 에도 holdings_overlap / data_quality_flags 채워넣기.
    for it in items:
        t = it.get("ticker")
        if isinstance(t, str):
            it.setdefault("holdings_overlap", t in holdings_tickers)
        it.setdefault("data_quality_flags", [])

    if not items:
        return {}
    return {
        "push_kind": "spike_or_falling_alert",
        "universe_scope": "ETF",
        "ranking_basis": "absolute_return_desc",
        "items": items,
        "limitations": [
            "개별 주식 전체 universe는 포함하지 않음",
        ],
    }


def spike_view_lines(push_context: Optional[dict[str, Any]]) -> list[str]:
    """PUSH-3 message builder 용 — push_context.spike_view.items 1건씩 사람이
    읽는 관찰 문장으로 변환. score 단독 표시 금지.

    각 line 에는 가능한 경우 수익률 근거 / 방향 / data_quality / holdings overlap
    중 최소 2개 이상이 포함된다.
    """
    if not isinstance(push_context, dict):
        return []
    sv = push_context.get("spike_view")
    if not isinstance(sv, dict):
        return []
    items = sv.get("items") or []
    if not isinstance(items, list) or not items:
        return []
    out: list[str] = ["[universe momentum 관찰 (push_context 기반)]"]
    for it in items[:6]:
        if not isinstance(it, dict):
            continue
        name = it.get("name") or it.get("ticker") or "-"
        direction = it.get("direction") or "-"
        return_terms: list[str] = []
        for label, key in (
            ("1d", "return_1d_pct"),
            ("5d", "return_5d_pct"),
            ("20d", "return_20d_pct"),
        ):
            v = it.get(key)
            if isinstance(v, (int, float)):
                return_terms.append(f"{label} {_fmt_pct(v)}")
        score_val = it.get("score_value")
        if isinstance(score_val, (int, float)) and not return_terms:
            return_terms.append(f"momentum score {score_val:+.2f}")
        dq_flags = it.get("data_quality_flags") or []
        dq_text = (
            f"data_quality flag: {', '.join(dq_flags)}"
            if isinstance(dq_flags, list) and dq_flags
            else "data_quality 이상 없음"
        )
        overlap = it.get("holdings_overlap")
        overlap_text = (
            "보유 종목과 겹침 (별도 확인 필요)"
            if overlap is True
            else "보유 종목과 겹치지 않음"
        )
        if not return_terms:
            # 수익률도 없고 score 도 없으면 단독 표시 회피.
            continue
        line_parts = [
            ", ".join(return_terms),
            f"방향 {direction}",
            dq_text,
            overlap_text,
        ]
        out.append(f"  • {name}: " + " · ".join(line_parts))
    if len(out) == 1:
        return []
    return out
