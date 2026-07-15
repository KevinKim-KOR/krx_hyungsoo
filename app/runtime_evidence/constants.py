"""Runtime Evidence 계약 상수 · 반환 dataclass · 유틸.

Cleanup / FIX r7 Round 2 에서 `app/runtime_evidence_composer.py` 로부터 분리.
외부 계약 (SRC_*, REASON_*, RuntimeEvidenceResult, _fmt_pct) 은 그대로 유지된다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

# ── source key 상수 (PUSH_KIND_DATA_SOURCES 와 동일 · §12 계약 유지) ──────────


SRC_MARKET_DISCOVERY = "market_discovery_snapshot"
SRC_HOLDINGS = "holdings_snapshot"
SRC_NAV_DISCOUNT = "nav_discount_snapshot"
SRC_KR_REALTIME = "kr_realtime_price_snapshot"
SRC_OVERNIGHT_US = "overnight_us_market_snapshot"
SRC_ML_BASELINE = "ml_baseline_v0"
SRC_NEWS = "news_snapshot"
SRC_UNIVERSE_MOMENTUM = "universe_momentum_snapshot"


# reason code — Telegram 본문 노출 금지 (diagnostics 전용).
REASON_EXTERNAL_FETCH_REQUIRED = "unavailable_external_fetch_required"
REASON_NOT_IMPLEMENTED = "unavailable_not_implemented"
REASON_SOURCE_MISSING_HOLDINGS = "holdings_source_missing"
REASON_MARKET_DB_MISSING = "market_db_missing_or_empty"
REASON_NO_CONTENTFUL_FACT = "no_contentful_fact"
REASON_NAV_UNAVAILABLE = "nav_row_unavailable"


@dataclass
class RuntimeEvidenceResult:
    """Composer 반환 계약 (지시문 §4.2)."""

    available_sources: dict[str, str] = field(default_factory=dict)
    extra_notes: list[str] = field(default_factory=list)
    diagnostics: dict[str, Any] = field(default_factory=dict)


def fmt_pct(value: Optional[float]) -> Optional[str]:
    if value is None:
        return None
    return f"{float(value):+.2f}%"


def fmt_pct_unsigned(value: Optional[float]) -> Optional[str]:
    if value is None:
        return None
    return f"{float(value):.2f}%"
