"""POC3-OPS-02B-2 — API↔CSV 정합성 판정과 07:20 결과 소비 경계.

설계자 최종 확정 (PLAN §M-2·§M-3):

- **07:20 배치가 받은 KRX 전종목 응답 하나**를 가격 적재와 정합성 판정에
  **함께** 쓴다.
- **08:00 runner 는 같은 API 를 다시 호출하지 않는다.** 이 모듈의 `load_*` 는
  07:20 이 남긴 결과를 **읽기만** 한다.

정합성 판정은 **순수 함수**다(`evaluate_consistency`). 외부 I/O 는 07:20 쪽
`build_consistency` 진입점에만 있다.

**fail-closed 우선순위** — 지수명 불일치 또는 **d20 종가가 있는** API-only 가
**1건이라도** 있으면 `coverage` 와 무관하게 `CSV_REFRESH_REQUIRED` 다. "불일치
종목만 빼고 나머지로 만드는" fallback 은 허용하지 않는다(설계 §5.2).

**pending gate** — 설계자 판정 `POC3-02D-OPS-01` Q1 (c)(2026-09-26)로 §5.2 의
"API-only 1건이라도 차단" 을 개정했다. 07:20 이 저장된 KRX 무조정 계열에서
**d20 종가가 없다**고 확인한 API-only(신규 상장 ETF)는 차단하지 않고
`api_only_pending`(ticker · 첫 적재일)으로 기록한다. 이런 ETF 는 CSV 에 행이
있어도 `compute_index_leadership` 의 `n` 에 들어가지 못해 후보 수치 영향이 0이다.
coverage 규칙(분자·분모)은 그대로다. d20 정보를 넘기지 않은 호출은 옛 계약대로
모든 API-only 가 차단 사유다.

**`refresh_due`** — 설계자 R2 Q23 (2026-09-27). 가장 먼저 적재된 pending 이 21번째
저장 거래일을 얻기까지 5거래일 이하이거나 이미 `CSV_REFRESH_REQUIRED` 이면 참이다.
참이 이어지는 동안 같은 주기 id 를 쓴다(Q24 — 주기마다 안내 1회).

**판정 창** — R2 Q27. 07:20 은 판정에 쓴 창(`evaluated_*`)을 남기고, 08:00 은 그
창이 오늘 창과 같을 때만 저장된 판정을 쓴다. 아니면 `META_GATE_STALE` 로 기초지수
구역만 닫는다 — `CSV_REFRESH_REQUIRED` 로 표시하지 않는다.
"""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from app.market_briefing.krx_store import REQUIRED_TRADING_DAYS

# 설계자 §M-3 — 분모는 두 원천 중 **큰 쪽**이다. 한 방향 coverage 만 보면
# API 부분 응답(행 수 급감)을 잡지 못한다.
MIN_JOIN_COVERAGE = 0.95

STATUS_OK = "ok"
STATUS_CSV_REFRESH_REQUIRED = "CSV_REFRESH_REQUIRED"
STATUS_COVERAGE_BELOW_THRESHOLD = "coverage_below_threshold"
STATUS_API_FETCH_FAILED = "api_fetch_failed"
# R2 Q27 — 저장된 판정이 오늘 창의 것이 아니다(08:00 진단 전용).
STATUS_META_GATE_STALE = "META_GATE_STALE"

# R2 Q23 (a) N=5 — 가장 이른 pending 이 d20 종가를 얻기까지 남은 거래일 상한.
REFRESH_DUE_MAX_REMAINING_DAYS = 5
REFRESH_REASON_CSV = "csv_refresh_required"
REFRESH_REASON_PENDING = "pending_within_5_trading_days"
# 07:20 이 판정하지 못한 날(조회 실패 등) — 직전 값을 이어받는다.
REFRESH_REASON_NOT_EVALUATED = "not_evaluated"

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
    # POC3-02D-OPS-01 Q1 (c) — `api_only` 중 d20 종가가 없어 차단하지 않은 것.
    # `[{"ticker": ..., "first_loaded": "YYYY-MM-DD"}]`. `api_only` 는 증거용
    # 전체 목록 그대로다(차단 대상 = `api_only` − pending).
    api_only_pending: list[dict[str, Any]] = field(default_factory=list)
    # POC3-02D-OPS-01 C1 — resolver 가 고른 파일명 · 거부한 후보(이름 · SHA · 사유).
    csv_name: Optional[str] = None
    csv_rejected: list[dict[str, Any]] = field(default_factory=list)
    # R2 Q27 — 판정에 쓴 창. 08:00 이 오늘 창과 비교한다.
    evaluated_api_basis_date: Optional[str] = None
    evaluated_window_d20_date: Optional[str] = None
    evaluated_at_kst: Optional[str] = None
    # R2 Q23 · Q24
    refresh_due: bool = False
    refresh_due_reason: Optional[str] = None
    refresh_due_cycle_id: Optional[str] = None

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
            "api_only_pending_count": len(self.api_only_pending),
            # 자르지 않는다 — 가장 먼저 적재된 pending(곧 d20 이 생겨 차단으로
            # 넘어갈 종목)이 08:00 진단에서 빠지면 안 된다. 신규 상장은 약 20
            # 거래일 동안의 것뿐이라 길지 않다(POC3-02D-OPS-01 C1).
            "api_only_pending": list(self.api_only_pending),
            "csv_only_count": len(self.csv_only),
            "csv_only": self.csv_only[:20],
            "name_mismatch_count": len(self.name_mismatch),
            "name_mismatch": self.name_mismatch[:20],
            "join_coverage": round(self.join_coverage, 6),
            "api_basis_date": self.api_basis_date,
            "csv_asof_date": self.csv_asof_date,
            "csv_sha256": self.csv_sha256,
            "csv_rows": self.csv_rows,
            "csv_name": self.csv_name,
            "csv_rejected": list(self.csv_rejected),
            "error": self.error,
            "evaluated_at": self.evaluated_at,
            "evaluated_api_basis_date": self.evaluated_api_basis_date,
            "evaluated_window_d20_date": self.evaluated_window_d20_date,
            "evaluated_at_kst": self.evaluated_at_kst,
            "refresh_due": self.refresh_due,
            "refresh_due_reason": self.refresh_due_reason,
            "refresh_due_cycle_id": self.refresh_due_cycle_id,
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
            # 필드가 없던 옛 07:20 JSON 은 pending 0 으로 읽는다.
            api_only_pending=[
                dict(x) for x in d.get("api_only_pending") or [] if isinstance(x, dict)
            ],
            # 아래는 POC3-02D-OPS-01 C1 필드 — 없던 옛 JSON 은 기본값으로 읽는다.
            csv_name=d.get("csv_name"),
            csv_rejected=[
                dict(x) for x in d.get("csv_rejected") or [] if isinstance(x, dict)
            ],
            evaluated_api_basis_date=d.get("evaluated_api_basis_date"),
            evaluated_window_d20_date=d.get("evaluated_window_d20_date"),
            evaluated_at_kst=d.get("evaluated_at_kst"),
            refresh_due=d.get("refresh_due") is True,
            refresh_due_reason=d.get("refresh_due_reason"),
            refresh_due_cycle_id=d.get("refresh_due_cycle_id"),
        )


def evaluate_consistency(
    *,
    api_index_names: dict[str, str],
    csv_rows: Sequence[dict[str, str]],
    api_basis_date: Optional[str] = None,
    csv_meta: Optional[dict[str, Any]] = None,
    no_d20_first_loaded: Optional[Mapping[str, Optional[str]]] = None,
    stored_day_counts: Optional[Mapping[str, int]] = None,
) -> ConsistencyResult:
    """**순수 함수.** API ticker→기초지수명 과 공식 CSV 를 대조한다.

    `api_index_names` 가 비어 있으면 **조회 실패**다 — CSV 불일치로 위장하지
    않는다(설계 §5.2).

    `no_d20_first_loaded` — 07:20 이 적재 직후 확인한 **d20 종가가 없는 API
    ticker → 첫 적재일**(POC3-02D-OPS-01 Q1 (c)). 그중 API-only 인 것은 pending
    으로 기록하고 차단하지 않는다. `None` 이면 옛 계약 — 모든 API-only 가 차단
    사유다. 이 함수는 넘겨받은 값만 본다(I/O 없음).

    `stored_day_counts` — ticker → 저장 거래일 수(R2 Q23). 주면 pending 마다
    `stored_trading_day_count` · `remaining_trading_days = max(0, 21 - 수)` 를 담는다.
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

    # POC3-02D-OPS-01 Q1 (c) — d20 종가가 없는 API-only 는 pending 이다.
    no_d20 = no_d20_first_loaded
    # 첫 적재일 오름차순(없으면 뒤) → ticker 순. 맨 앞이 가장 먼저 d20 을 얻는다.
    pending = (
        sorted(
            (
                {"ticker": t, "first_loaded": no_d20.get(t)}
                for t in api_only
                if t in no_d20
            ),
            key=lambda p: (p["first_loaded"] or "9999-12-31", p["ticker"]),
        )
        if no_d20 is not None
        else []
    )
    if stored_day_counts is not None:
        for p in pending:
            n = int(stored_day_counts.get(p["ticker"]) or 0)
            p["stored_trading_day_count"] = n
            p["remaining_trading_days"] = max(0, REQUIRED_TRADING_DAYS - n)
    pending_set = {p["ticker"] for p in pending}
    blocking = [t for t in api_only if t not in pending_set]

    result = ConsistencyResult(
        status=STATUS_OK,
        api_ticker_count=len(api_set),
        csv_ticker_count=len(csv_set),
        exact_match_count=exact,
        api_only=api_only,
        csv_only=csv_only,
        name_mismatch=mismatch,
        join_coverage=coverage,
        api_only_pending=pending,
        **base,
    )

    # 설계자 §M-3 (POC3-02D-OPS-01 Q1 로 개정) — d20 종가가 있는 API-only 또는
    # 지수명 불일치가 1건이라도 있으면 **coverage 와 무관하게** CSV 교체 필요다.
    # 부분 사용 fallback 금지. pending 은 차단하지 않지만 coverage 분모에는
    # 그대로 들어간다(규칙 불변).
    if blocking or mismatch:
        result.status = STATUS_CSV_REFRESH_REQUIRED
        return result
    if coverage < MIN_JOIN_COVERAGE:
        result.status = STATUS_COVERAGE_BELOW_THRESHOLD
        return result
    return result


def apply_refresh_due(
    result: ConsistencyResult, *, previous: Optional[ConsistencyResult]
) -> None:
    """R2 Q23 · Q24 — `refresh_due` 와 주기 id 를 정한다. I/O 없음(result 를 갱신).

    - 가장 이른 pending(첫 적재일 순 맨 앞)의 남은 거래일이 5 이하이거나,
      status 가 `CSV_REFRESH_REQUIRED` 이면 참.
    - 주기 id: 직전 판정도 참이었으면 그 id 를 잇고, 새로 참이 되면 이번 판정의
      API 기준일로 새 id. 거짓이면 `None`.
    """
    reasons = []
    if result.status == STATUS_CSV_REFRESH_REQUIRED:
        reasons.append(REFRESH_REASON_CSV)
    earliest = result.api_only_pending[0] if result.api_only_pending else None
    remaining = (earliest or {}).get("remaining_trading_days")
    if isinstance(remaining, int) and remaining <= REFRESH_DUE_MAX_REMAINING_DAYS:
        reasons.append(REFRESH_REASON_PENDING)
    result.refresh_due = bool(reasons)
    result.refresh_due_reason = ",".join(reasons) or None
    if not result.refresh_due:
        result.refresh_due_cycle_id = None
    elif (
        previous is not None and previous.refresh_due and previous.refresh_due_cycle_id
    ):
        result.refresh_due_cycle_id = previous.refresh_due_cycle_id
    else:
        result.refresh_due_cycle_id = (
            result.evaluated_api_basis_date
            or result.api_basis_date
            or result.evaluated_at
        )


def carry_refresh_due(
    result: ConsistencyResult, *, previous: Optional[ConsistencyResult]
) -> None:
    """07:20 이 판정하지 못한 날 — 직전 `refresh_due` · 주기를 그대로 잇는다.

    판정 못 한 날을 거짓으로 적으면 주기가 끊겨 다음 판정에서 같은 갱신 요청을
    다시 알린다. 08:00 은 이 JSON 을 `META_GATE_STALE` 로 보고 안내에 쓰지 않는다.
    """
    due = bool(previous is not None and previous.refresh_due)
    result.refresh_due = due
    result.refresh_due_reason = REFRESH_REASON_NOT_EVALUATED
    result.refresh_due_cycle_id = previous.refresh_due_cycle_id if due else None


def _iso_day(value: Optional[str]) -> Optional[str]:
    """`20260917` · `2026-09-17` → `2026-09-17`. 다른 형식은 그대로(불일치로 남는다)."""
    v = (value or "").strip()
    if len(v) == 8 and v.isdigit():
        return f"{v[:4]}-{v[4:6]}-{v[6:]}"
    return v or None


def verdict_stale_reason(
    result: ConsistencyResult, *, latest: Optional[str], d20: Optional[str]
) -> Optional[str]:
    """R2 Q27 — 저장된 판정이 **오늘 창**(`latest` · `d20`)의 것인가.

    `None` 이면 같은 창이다. 아니면 사유 — 호출자가 기초지수 구역만 fail-closed
    한다. 판정을 다시 계산하지 않는다.
    """
    if not result.evaluated_at_kst or not result.evaluated_api_basis_date:
        return "evaluated_window_missing"
    if _iso_day(result.evaluated_api_basis_date) != _iso_day(latest):
        return "api_basis_date_mismatch"
    if _iso_day(result.evaluated_window_d20_date) != _iso_day(d20):
        return "window_d20_mismatch"
    return None


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
    "STATUS_META_GATE_STALE",
    "STATUS_OK",
    "REFRESH_DUE_MAX_REMAINING_DAYS",
    "REFRESH_REASON_CSV",
    "REFRESH_REASON_NOT_EVALUATED",
    "REFRESH_REASON_PENDING",
    "ConsistencyResult",
    "apply_refresh_due",
    "carry_refresh_due",
    "evaluate_consistency",
    "load_consistency",
    "load_official_csv",
    "matched_meta_rows",
    "save_consistency",
    "verdict_stale_reason",
]
