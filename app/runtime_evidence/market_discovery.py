"""market_discovery_snapshot source composer (지시문 §5.1).

Cleanup / FIX r7 Round 2 에서 `app/runtime_evidence_composer.py` 로부터 분리.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from app.runtime_evidence.constants import (
    REASON_MARKET_DB_MISSING,
    REASON_NO_CONTENTFUL_FACT,
    fmt_pct,
)


def compose_market_discovery(
    topn_fn: Callable[..., dict],
    market_db_path: Path,
) -> tuple[str, list[str], dict[str, Any]]:
    """returns (status, extra_notes lines, diag dict).

    available 조건 (지시문 §5.1):
      - reader 실행 성공 (status == "ok").
      - 실제 asof 존재.
      - 실제 benchmark 또는 후보 수치 존재.
      - 사용자용 evidence 문장 최소 1개 생성 가능.
    """
    payload = topn_fn(db_path=market_db_path)
    status = payload.get("status")
    asof = payload.get("asof")
    diag: dict[str, Any] = {
        "status": None,
        "asof": asof,
        "reader_status": status,
        "candidates_count": 0,
        "contentful_fact_count": 0,
    }
    if status != "ok" or not asof:
        diag["status"] = "unavailable"
        diag["reason"] = REASON_MARKET_DB_MISSING
        return "unavailable", [], diag

    notes: list[str] = []
    fact_count = 0
    market_context = payload.get("market_context") or {}

    # KODEX200 벤치마크.
    kodex = market_context.get("kodex200") or {}
    if kodex.get("status") == "ok":
        pct1m = fmt_pct(kodex.get("return_1m_pct"))
        pct3m = fmt_pct(kodex.get("return_3m_pct"))
        if pct1m or pct3m:
            parts = []
            if pct1m:
                parts.append(f"1개월 {pct1m}")
            if pct3m:
                parts.append(f"3개월 {pct3m}")
            notes.append(
                f"KODEX200 최근 수익률 ({asof} 기준): " + " / ".join(parts) + "."
            )
            fact_count += 1

    # KOSPI 벤치마크.
    kospi = market_context.get("kospi") or {}
    if kospi.get("status") == "ok":
        pct1m = fmt_pct(kospi.get("return_1m_pct"))
        pct3m = fmt_pct(kospi.get("return_3m_pct"))
        if pct1m or pct3m:
            parts = []
            if pct1m:
                parts.append(f"1개월 {pct1m}")
            if pct3m:
                parts.append(f"3개월 {pct3m}")
            notes.append(f"KOSPI 최근 수익률 ({asof} 기준): " + " / ".join(parts) + ".")
            fact_count += 1

    # Market Discovery TOP 후보 — 실제 as-of 가 있을 때만 preview fact 로 인정.
    candidates = payload.get("candidates") or []
    diag["candidates_count"] = len(candidates)
    if candidates:
        top_preview = candidates[: min(3, len(candidates))]
        preview_pairs: list[str] = []
        for c in top_preview:
            name = c.get("name") or c.get("ticker")
            ret_pct = fmt_pct(c.get("selected_return_pct"))
            if name and ret_pct:
                preview_pairs.append(f"{name} {ret_pct}")
        if preview_pairs:
            notes.append(
                f"Market Discovery 후보 {len(candidates)}종 상위 ({asof} 기준): "
                + ", ".join(preview_pairs)
                + "."
            )
            fact_count += 1

    if fact_count == 0:
        diag["status"] = "unavailable"
        diag["reason"] = REASON_NO_CONTENTFUL_FACT
        return "unavailable", [], diag

    diag["status"] = "available"
    diag["contentful_fact_count"] = fact_count
    return "available", notes, diag
