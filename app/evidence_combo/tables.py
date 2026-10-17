"""POC5-20 — 같은 공통 표본의 가격 구간 표 · 네 조합 표(설계 §4 · PLAN §2).

```text
행    가격 구간 4개(10% 이상 · 8~10% · 5~8% 하락 · 구간 미해당)
칸    전체 + 네 조합(거래량 평균 초과 / 이하 × 흔들림 커짐 / 커지지 않음)
값    종목×기준일 수 · 서로 다른 종목 수 · 기준일 수 · 두 결과(끝점 · 최저 종가 변화 %)의 중앙값 · 25 / 75 분위
      (`ml_score_validity_metrics.percentile` · 선형보간) · 날짜별 중앙값의 중앙값(보조값)
빈 칸 n = 0 → 표본 없음(0% 아님)
```

성공률 · 유의확률 · 점수 · 위험 등급 · 최적 기준은 만들지 않는다(설계 §4).
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable, Optional, Sequence

from app.evidence_combo.observations import BAND_NONE, Record
from app.ml_score_validity_metrics import percentile
from app.runtime_evidence.holdings_selection import (
    STATE_D5_8,
    STATE_D8_10,
    STATE_D10_PLUS,
)

BANDS: tuple[tuple[str, str], ...] = (
    (STATE_D10_PLUS, "10% 이상 하락"),
    (STATE_D8_10, "8~10% 하락"),
    (STATE_D5_8, "5~8% 하락"),
    (BAND_NONE, "구간 미해당"),
)
COMBOS: tuple[tuple[str, str, bool, bool], ...] = (
    ("vol_above__vola_up", "거래량 평균 초과 · 흔들림 커짐", True, True),
    ("vol_above__vola_not_up", "거래량 평균 초과 · 흔들림 커지지 않음", True, False),
    ("vol_below__vola_up", "거래량 평균 이하 · 흔들림 커짐", False, True),
    ("vol_below__vola_not_up", "거래량 평균 이하 · 흔들림 커지지 않음", False, False),
)
OUTCOMES: tuple[tuple[str, str], ...] = (
    ("end_change_pct", "끝점 변화"),
    ("min_change_pct", "기간 중 최저 종가 변화"),
)


def _median(values: Sequence[float]) -> Optional[float]:
    return percentile(values, 50.0)


def _outcome_stats(records: Sequence[Record], key: str) -> dict[str, Optional[float]]:
    values = [getattr(r, key) for r in records]
    by_date: dict[str, list[float]] = defaultdict(list)
    for r in records:
        by_date[r.date].append(getattr(r, key))
    date_medians = [
        m for m in (_median(v) for _, v in sorted(by_date.items())) if m is not None
    ]
    return {
        "median": _median(values),
        "p25": percentile(values, 25.0),
        "p75": percentile(values, 75.0),
        "date_median_of_medians": _median(date_medians),
    }


def cell(records: Sequence[Record]) -> dict[str, Any]:
    """한 칸의 통계. 표본이 없으면 n = 0 · empty = True(값 없음 · 0% 아님)."""
    if not records:
        return {"n": 0, "tickers": 0, "dates": 0, "empty": True}
    out: dict[str, Any] = {
        "n": len(records),
        "tickers": len({r.ticker for r in records}),
        "dates": len({r.date for r in records}),
        "empty": False,
    }
    for key, _ in OUTCOMES:
        out[key] = _outcome_stats(records, key)
    return out


def band_table(records: Iterable[Record]) -> list[dict[str, Any]]:
    """가격 구간마다 전체 칸 + 네 조합 칸 — 모두 같은 공통 표본(records)에서."""
    recs = list(records)
    rows = []
    for band, label in BANDS:
        in_band = [r for r in recs if r.band == band]
        combos = {
            code: cell(
                [
                    r
                    for r in in_band
                    if r.volume_above is v_above and r.volatility_up is p_up
                ]
            )
            for code, _, v_above, p_up in COMBOS
        }
        rows.append(
            {"band": band, "label": label, "all": cell(in_band), "combos": combos}
        )
    return rows


def split_halves(base_dates: Sequence[str]) -> tuple[list[str], list[str]]:
    """입력 범위 거래일을 순서대로 반으로(홀수면 앞 기간이 하루 길다 · 설계 §4)."""
    days = sorted(base_dates)
    k = (len(days) + 1) // 2
    return days[:k], days[k:]
