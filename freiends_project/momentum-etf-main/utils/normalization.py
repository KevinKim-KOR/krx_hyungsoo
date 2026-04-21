"""서비스 공통 정규화 유틸리티."""

from __future__ import annotations

import datetime as _dt
from typing import Any


import math

def normalize_number(value: Any) -> float:
    """숫자로 변환한다. 실패 시 0.0을 반환한다."""
    try:
        val = float(value or 0)
        if math.isnan(val):
            return 0.0
        return val
    except (TypeError, ValueError):
        return 0.0


def normalize_nullable_number(value: Any) -> float | None:
    """숫자로 변환한다. 빈 값이면 None을 반환한다."""
    if value in (None, "", "-"):
        return None
    try:
        val = float(str(value).replace(",", ""))
        if math.isnan(val):
            return None
        return val
    except (TypeError, ValueError):
        return None


def normalize_text(value: Any, fallback: str = "") -> str:
    """문자열로 변환하고 양쪽 공백을 제거한다."""
    text = str(value or "").strip()
    return text or fallback


def to_iso_string(value: Any) -> str | None:
    """datetime/date를 ISO 문자열로 변환한다. None이면 None을 반환한다."""
    if value is None:
        return None
    if isinstance(value, _dt.datetime):
        if value.tzinfo is None:
            # Mongo에서 읽힌 naive datetime은 UTC로 간주해 offset을 명시한다.
            value = value.replace(tzinfo=_dt.timezone.utc)
        return value.isoformat()
    if isinstance(value, _dt.date):
        return value.isoformat()
    return str(value)
