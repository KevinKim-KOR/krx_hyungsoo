"""POC3-OPS-02B-2 — API↔CSV 정합성 판정과 07:20 결과 소비 경계.

설계자 최종 확정 (PLAN §M-2·§M-3):

- **07:20 배치가 받은 KRX 전종목 응답 하나**를 가격 적재와 정합성 판정에
  **함께** 쓴다.
- **08:00 runner 는 같은 API 를 다시 호출하지 않는다.** 이 모듈의 `load_*` 는
  07:20 이 남긴 결과를 **읽기만** 한다.

정합성 판정은 **순수 함수**다(`evaluate_consistency`). 외부 I/O 는 07:20 쪽
`build_consistency` 진입점에만 있다.

**fail-closed 우선순위** — API-only / 지수명 불일치가 **1건이라도** 있으면
`coverage` 와 무관하게 `CSV_REFRESH_REQUIRED` 다. "불일치 종목만 빼고 나머지로
만드는" fallback 은 허용하지 않는다(설계 §5.2).
"""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Sequence

# 설계자 §M-3 — 분모는 두 원천 중 **큰 쪽**이다. 한 방향 coverage 만 보면
# API 부분 응답(행 수 급감)을 잡지 못한다.
MIN_JOIN_COVERAGE = 0.95

STATUS_OK = "ok"
STATUS_CSV_REFRESH_REQUIRED = "CSV_REFRESH_REQUIRED"
STATUS_COVERAGE_BELOW_THRESHOLD = "coverage_below_threshold"
STATUS_API_FETCH_FAILED = "api_fetch_failed"

# 07:20 이 남기고 08:00 이 읽는 파일.
CONSISTENCY_STATE_NAME = "market_briefing_meta_consistency_latest.json"


@dataclass
class ConsistencyResult:
    """API↔CSV 대조 결과. 수치를 손으로 옮기지 않도록 전부 담는다."""

    status: str
    api_ticker_count: int = 0
    csv_ticker_count: int = 0
    exact_match_count: int = 0
    api_only: list[str] = field(default_factory=list)
    csv_only: list[str] = field(default_factory=list)
    name_mismatch: list[str] = field(default_factory=list)
    join_coverage: float = 0.0
    api_basis_date: Optional[str] = None
    csv_asof_date: Optional[str] = None
    csv_sha256: Optional[str] = None
    csv_rows: Optional[int] = None
    error: Optional[str] = None
    evaluated_at: Optional[str] = None

    @property
    def usable(self) -> bool:
        """기초지수 블록을 산출해도 되는가."""
        return self.status == STATUS_OK

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "api_ticker_count": self.api_ticker_count,
            "csv_ticker_count": self.csv_ticker_count,
            "exact_match_count": self.exact_match_count,
            "api_only_count": len(self.api_only),
            "api_only": self.api_only[:20],
            "csv_only_count": len(self.csv_only),
            "csv_only": self.csv_only[:20],
            "name_mismatch_count": len(self.name_mismatch),
            "name_mismatch": self.name_mismatch[:20],
            "join_coverage": round(self.join_coverage, 6),
            "api_basis_date": self.api_basis_date,
            "csv_asof_date": self.csv_asof_date,
            "csv_sha256": self.csv_sha256,
            "csv_rows": self.csv_rows,
            "error": self.error,
            "evaluated_at": self.evaluated_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ConsistencyResult":
        return cls(
            status=d.get("status") or STATUS_API_FETCH_FAILED,
            api_ticker_count=d.get("api_ticker_count") or 0,
            csv_ticker_count=d.get("csv_ticker_count") or 0,
            exact_match_count=d.get("exact_match_count") or 0,
            api_only=list(d.get("api_only") or []),
            csv_only=list(d.get("csv_only") or []),
            name_mismatch=list(d.get("name_mismatch") or []),
            join_coverage=float(d.get("join_coverage") or 0.0),
            api_basis_date=d.get("api_basis_date"),
            csv_asof_date=d.get("csv_asof_date"),
            csv_sha256=d.get("csv_sha256"),
            csv_rows=d.get("csv_rows"),
            error=d.get("error"),
            evaluated_at=d.get("evaluated_at"),
        )


def evaluate_consistency(
    *,
    api_index_names: dict[str, str],
    csv_rows: Sequence[dict[str, str]],
    api_basis_date: Optional[str] = None,
    csv_meta: Optional[dict[str, Any]] = None,
) -> ConsistencyResult:
    """**순수 함수.** API ticker→기초지수명 과 공식 CSV 를 대조한다.

    `api_index_names` 가 비어 있으면 **조회 실패**다 — CSV 불일치로 위장하지
    않는다(설계 §5.2).
    """
    meta = csv_meta or {}
    base = {
        "api_basis_date": api_basis_date,
        "csv_asof_date": meta.get("asof_date"),
        "csv_sha256": meta.get("sha256"),
        "csv_rows": meta.get("rows"),
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
    }
    if not api_index_names:
        return ConsistencyResult(
            status=STATUS_API_FETCH_FAILED, error="empty_api_response", **base
        )

    csv_names = {
        (r.get("단축코드") or "").strip(): (r.get("기초지수명") or "").strip()
        for r in csv_rows
        if (r.get("단축코드") or "").strip()
    }
    api_set, csv_set = set(api_index_names), set(csv_names)
    api_only = sorted(api_set - csv_set)
    csv_only = sorted(csv_set - api_set)
    both = api_set & csv_set
    mismatch = sorted(t for t in both if api_index_names[t] != csv_names[t])
    exact = len(both) - len(mismatch)
    denom = max(len(api_set), len(csv_set)) or 1
    coverage = exact / denom

    result = ConsistencyResult(
        status=STATUS_OK,
        api_ticker_count=len(api_set),
        csv_ticker_count=len(csv_set),
        exact_match_count=exact,
        api_only=api_only,
        csv_only=csv_only,
        name_mismatch=mismatch,
        join_coverage=coverage,
        **base,
    )

    # 설계자 §M-3 — API-only 또는 지수명 불일치가 1건이라도 있으면
    # **coverage 와 무관하게** CSV 교체 필요다. 부분 사용 fallback 금지.
    if api_only or mismatch:
        result.status = STATUS_CSV_REFRESH_REQUIRED
        return result
    if coverage < MIN_JOIN_COVERAGE:
        result.status = STATUS_COVERAGE_BELOW_THRESHOLD
        return result
    return result


def matched_meta_rows(
    csv_rows: Sequence[dict[str, str]], api_index_names: dict[str, str]
) -> list[dict[str, str]]:
    """정합성을 통과한 종목만. 이름을 고쳐 맞추지 않는다."""
    return [
        r
        for r in csv_rows
        if (r.get("단축코드") or "").strip() in api_index_names
        and api_index_names[(r.get("단축코드") or "").strip()]
        == (r.get("기초지수명") or "").strip()
    ]


# ── 공식 CSV 로더 ───────────────────────────────────────────────────────────


def load_official_csv(path: Path) -> list[dict[str, str]]:
    """공식 KRX ETF 기본정보. **cp949** 이고 편집본을 쓰지 않는다."""
    raw = path.read_bytes().decode("cp949")
    return list(csv.DictReader(io.StringIO(raw)))


# ── 07:20 결과 저장 / 08:00 소비 ────────────────────────────────────────────


def save_consistency(result: ConsistencyResult, path: Path) -> None:
    """07:20 이 판정 결과를 남긴다. 원자적으로 쓴다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(result.to_dict(), ensure_ascii=False, indent=1), encoding="utf-8"
    )
    tmp.replace(path)


def load_consistency(path: Path) -> Optional[ConsistencyResult]:
    """08:00 runner 가 읽는다. **외부 조회 0건.**

    파일이 없거나 깨졌으면 `None` — 호출자가 fail-closed 한다.
    """
    if not path.exists():
        return None
    try:
        return ConsistencyResult.from_dict(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return None


__all__ = [
    "CONSISTENCY_STATE_NAME",
    "MIN_JOIN_COVERAGE",
    "STATUS_API_FETCH_FAILED",
    "STATUS_COVERAGE_BELOW_THRESHOLD",
    "STATUS_CSV_REFRESH_REQUIRED",
    "STATUS_OK",
    "ConsistencyResult",
    "evaluate_consistency",
    "load_consistency",
    "load_official_csv",
    "matched_meta_rows",
    "save_consistency",
]
