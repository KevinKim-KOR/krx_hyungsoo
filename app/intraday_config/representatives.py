"""POC3-02D-OPS-03 — 활성 장중 설정의 대표 ETF 목록 · T-1 커버리지 판정(순수 함수).

설계자 RESULT STEP 2(2026-09-30) — 대표 ETF 커버리지는 **KRX 적재 성공 조건이 아니다.**
적재가 성공한 뒤 따로 판정하고, 그 결과는 장중 「신규 진입 검토」 한 구역에만 쓴다.

```text
ok                            활성 대표 전부 T-1 행이 있다
intraday_config_unavailable   활성 설정을 읽지 못했다(대표 목록을 모른다)
representative_missing        대표 일부가 T-1 행에 없다(상장폐지 등)
```

`ok` 가 아니면 `representatives_refresh_due = true` — 장중 설정(대표)을 새로 승인할
때라는 뜻이다. 공식 CSV 갱신 안내(정합성 JSON `refresh_due`)와는 **다른 필드**다.

두 곳이 같은 규칙을 쓴다 — 08:10 · 09:20 배치 기록(`krx_target_checks`)과 장중
판정(`sector_signal`). I/O 는 호출자가 한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Collection, Optional, Sequence

COVERAGE_OK = "ok"
COVERAGE_CONFIG_UNAVAILABLE = "intraday_config_unavailable"
COVERAGE_REPRESENTATIVE_MISSING = "representative_missing"


def representative_tickers(sectors: Any) -> Optional[list[str]]:
    """사업군 목록 → 대표 ticker(대체 제외 · 설정 순서). 모르면 `None`.

    사업군이 비었거나 대표 ticker 가 없는 사업군이 하나라도 있으면 활성 대표
    전체를 알 수 없다 — 추측으로 줄여 세지 않는다(스키마 검증은 둘 다 막는다).
    """
    if not isinstance(sectors, list) or not sectors:
        return None
    out: list[str] = []
    for s in sectors:
        t = ((s or {}).get("representative") or {}).get("ticker")
        if not isinstance(t, str) or not t.strip():
            return None
        out.append(t.strip())
    return out


@dataclass(frozen=True)
class RepresentativeCoverage:
    """활성 대표의 T-1 행 커버리지."""

    status: str
    expected: Optional[str] = None
    count: int = 0
    missing: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return self.status == COVERAGE_OK

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "expected_previous_trading_day": self.expected,
            "count": self.count,
            "missing": list(self.missing),
            "representatives_refresh_due": not self.ok,
        }


def evaluate_coverage(
    representatives: Optional[Sequence[str]],
    have_on_expected: Collection[str],
    *,
    expected: Optional[str],
) -> RepresentativeCoverage:
    """대표 목록과 T-1(`expected`)에 행이 있는 ticker 집합으로 판정한다.

    `expected` 가 없으면(기대 T-1 을 모른다) 어떤 대표도 T-1 행을 확인할 수 없다.
    """
    if not representatives:
        return RepresentativeCoverage(COVERAGE_CONFIG_UNAVAILABLE, expected)
    reps = sorted(set(representatives))
    have = set(have_on_expected) if expected else set()
    missing = tuple(t for t in reps if t not in have)
    return RepresentativeCoverage(
        COVERAGE_REPRESENTATIVE_MISSING if missing else COVERAGE_OK,
        expected,
        count=len(reps),
        missing=missing,
    )


__all__ = [
    "COVERAGE_CONFIG_UNAVAILABLE",
    "COVERAGE_OK",
    "COVERAGE_REPRESENTATIVE_MISSING",
    "RepresentativeCoverage",
    "evaluate_coverage",
    "representative_tickers",
]
