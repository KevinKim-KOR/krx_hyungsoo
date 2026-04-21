"""RANK(Moving Average Position Score) 전략 서브패키지."""

from __future__ import annotations

from .scoring import calculate_maps_score

__all__ = [
    "calculate_maps_score",
]
