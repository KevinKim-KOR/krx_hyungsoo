"""POC6-02 — 입력 snapshot(설계 개정 2 §3 · PLAN §1 · §2).

```text
읽기    보유 문서 한 번(ticker 만) · 시장 DB 한 mode=ro 읽기 트랜잭션(06 과 같은 open_ro) → 닫은 뒤 계산
담음    보유 ETF ticker · 이름 · 저장 행(date · close · source · fetched_at · change) · 공통 기준일 T ·
        06 연구 축(dates · modes · 건너뛴 평일 · KOSPI 최신일 · 연도 파일) · 축 문제 · 보유 건수(ETF · 개별주)
안 담음 수량 · 평단 · 계좌 · 메모 · 평가 · 비밀값 · 개별주 ticker(건수만)
T       KOSPI 저장 최신일(close > 0) 하나 — 모든 ETF 공통(06 은 ETF 마지막 저장일 · 설계 §3)
```

입력을 확정할 수 없으면(보유 문서 손상 · 보유 파일 없음 · 시세 DB 없음 · etf_master · 가격 표 없음 ·
KOSPI 저장일 없음 · `--snapshot` 파일 손상 · 형식 다름) `SnapshotError` = CHECK_REQUIRED 이다. 정상 '자료 부족'
(DATA_SHORT)과 섞지 않는다 — 보유 파일이 있는데 ETF 가 없으면(EMPTY · 개별주만) 그때만 자료 부족이다.
형식 검사는 모양만이 아니라 실제 해석이다(`snapshot_problem` · 검증자 r1 정정): 날짜 해석 · 엄격한 오름차순(중복 · 역순 없음) ·
수 · 글자 칸 · 보유 건수 일치 · 연구 축 내부 일치(연도별 방식 · 건너뛴 평일 · 축 문제 다시 판정). 만들 때 · 파일에서 읽을 때 ·
계산 시작(`study.prepare`) 세 곳이 같은 검사를 쓴다.
"""

from __future__ import annotations

import json
import math
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

from app import holdings as holdings_module
from app import holdings_edit
from app import holdings_store as store
from app.market_briefing import calendar as cal
from app.reentry_review import prices
from app.three_push_runtime import ledger_outcome_prices as lop

SCHEMA = "poc6_02_snapshot_v1"


class SnapshotError(Exception):
    """입력을 확정할 수 없음 — CHECK_REQUIRED(정상 부족과 구분)."""


def _holding_tickers() -> tuple[str, int, list[str]]:
    """현재 보유 = 화면 GET /holdings 와 같은 함수(V1 · V2 · 파일 없음 모두) — ticker 만 쓴다."""
    try:
        cur = holdings_edit.current_holdings()
    except (store.DocumentCorrupt, holdings_module.HoldingsValidationError) as e:
        raise SnapshotError(f"보유 문서 손상: {e}") from e
    if cur["status"] == "NO_FILE":
        raise SnapshotError(
            "보유 파일 없음 — 실행 위치 · 보유 경로 확인(빈 모집단으로 넘기지 않음)"
        )
    rows = cur["holdings"]
    tickers = sorted({str(h.get("ticker")) for h in rows if h.get("ticker")})
    return cur["status"], len(rows), tickers


def _has_table(con: sqlite3.Connection, name: str) -> bool:
    return (
        con.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)
        ).fetchone()
        is not None
    )


def _names(con: sqlite3.Connection, tickers: list[str]) -> dict[str, Optional[str]]:
    out: dict[str, Optional[str]] = {}
    for t in tickers:
        row = con.execute(
            f"SELECT name FROM {prices.MASTER_TABLE} WHERE ticker = ?", (t,)
        ).fetchone()
        out[t] = row[0] if row else None
    return out


def build_snapshot(market_db: Optional[Path] = None) -> dict[str, Any]:
    status, n_rows, tickers = _holding_tickers()
    try:
        con = lop.open_ro(market_db)
    except FileNotFoundError as e:
        raise SnapshotError("시세 DB 파일 없음") from e
    try:
        con.execute("BEGIN")
        if not _has_table(con, prices.PRICE_TABLE):
            raise SnapshotError("ETF 가격 표(etf_daily_price) 없음 — 시세 DB 확인")
        kind = {t: prices.is_etf(con, t) for t in tickers}
        if any(v is None for v in kind.values()):
            raise SnapshotError("ETF 목록(etf_master) 없음 — ETF 여부 확인 불가")
        etfs = [t for t in tickers if kind[t]]
        rows = {t: prices.read_rows(con, t) for t in etfs}
        names = _names(con, etfs)
        kospi = prices.read_kospi_dates(con)
        con.execute("ROLLBACK")
    except sqlite3.Error as e:
        raise SnapshotError(f"시세 DB 읽기 실패: {type(e).__name__}") from e
    finally:
        con.close()
    if not kospi:
        raise SnapshotError("KOSPI 저장일 없음 — 공통 기준일 T 를 정할 수 없음")
    T = kospi[-1]
    starts = [r[0].date for r in rows.values() if r and r[0].date <= T]
    first = min(starts) if starts else T
    axis = prices.research_axis(T, first, kospi, calendar_dir=cal.CALENDAR_DIR)
    snap = {
        "schema": SCHEMA,
        "T": T,
        "holdings": {
            "status": status,
            "rows": n_rows,
            "tickers": len(tickers),
            "etf": len(etfs),
            "non_etf": sum(1 for t in tickers if kind[t] is False),
        },
        "axis": {
            "label": prices.AXIS_LABEL,
            "dates": axis["dates"],
            "modes": axis["modes"],
            "skipped_weekdays": axis["skipped_weekdays"],
            "kospi_latest": axis["kospi_latest"],
            "calendar_years": axis["calendar_years"],
            "problem": prices.axis_problem(T, axis),
        },
        "price_basis_label": prices.PRICE_BASIS_LABEL,
        "etfs": {
            t: {"name": names[t], "rows": [list(r.as_json().values()) for r in rows[t]]}
            for t in etfs
        },
    }
    problem = snapshot_problem(snap)
    if problem:  # DB 에서 온 값도 같은 계약(해석 불가 날짜 · 수 아닌 종가 등)
        raise SnapshotError(f"시세 DB 값이 snapshot 계약과 다름: {problem}")
    return snap


_TOP_KEYS = {"schema", "T", "holdings", "axis", "price_basis_label", "etfs"}
_HOLDINGS_KEYS = {"status", "rows", "tickers", "etf", "non_etf"}
_AXIS_KEYS = {
    "label",
    "dates",
    "modes",
    "skipped_weekdays",
    "kospi_latest",
    "calendar_years",
    "problem",
}


def _day(v: Any) -> Optional[date]:
    """정규 ISO 날짜(YYYY-MM-DD)만 — 실제로 해석하고 같은 글자로 되돌아와야 한다."""
    if not isinstance(v, str):
        return None
    try:
        d = date.fromisoformat(v)
    except ValueError:
        return None
    return d if d.isoformat() == v else None


def _days(vs: Any, what: str) -> tuple[Optional[list[date]], Optional[str]]:
    """날짜 목록 — 모두 해석 가능 · 엄격히 오름차순(중복 · 역순 없음)."""
    if not isinstance(vs, list):
        return None, f"{what} 가 목록이 아님"
    out = []
    for k, v in enumerate(vs):
        d = _day(v)
        if d is None:
            return None, f"{what}[{k}] 날짜 해석 불가 {v!r}"
        if out and d <= out[-1]:
            return None, f"{what}[{k}] 중복 · 역순 {v!r}"
        out.append(d)
    return out, None


def _count(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and v >= 0


def _num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _instant(v: Any) -> bool:
    if not isinstance(v, str):
        return False
    try:
        datetime.fromisoformat(v)
    except ValueError:
        return False
    return True


def _row_problem(t: str, k: int, r: Any) -> Optional[str]:
    if not isinstance(r, list) or len(r) != 5:
        return f"{t} 저장 행 {k} 형식 다름"
    _, close, source, fetched_at, change = r
    if close is not None and not _num(close):
        return f"{t} 저장 행 {k} 종가가 수가 아님"
    if source is not None and not isinstance(source, str):
        return f"{t} 저장 행 {k} 출처가 글자가 아님"
    if fetched_at is not None and not _instant(fetched_at):
        return f"{t} 저장 행 {k} 수집 시각 해석 불가"
    if change is not None and not (_num(change) and math.isfinite(change)):
        return f"{t} 저장 행 {k} change 가 유한한 수가 아님"
    return None


def _holdings_problem(h: Any, n_etfs: int) -> Optional[str]:
    if not isinstance(h, dict) or set(h) != _HOLDINGS_KEYS:
        return "holdings 칸이 다름"
    if not isinstance(h["status"], str):
        return "holdings.status 가 글자가 아님"
    if not all(_count(h[k]) for k in ("rows", "tickers", "etf", "non_etf")):
        return "holdings 건수가 0 이상 정수가 아님"
    if h["etf"] != n_etfs or h["tickers"] != h["etf"] + h["non_etf"]:
        return "holdings 건수가 etfs 와 맞지 않음"
    if h["rows"] < h["tickers"]:
        return "holdings 행 수가 ticker 수보다 적음"
    return None


def _axis_problem(a: Any, T: str, t_day: date, first: date) -> Optional[str]:
    """연구 축 내부 일치 — 06 `research_axis` 가 만드는 모양과 같아야 한다(다시 만들 수 없는 KOSPI 저장일만 빼고)."""
    if not isinstance(a, dict) or set(a) != _AXIS_KEYS:
        return "axis 칸이 다름"
    if a["label"] != prices.AXIS_LABEL:
        return "axis.label 이 06 연구 축과 다름"
    dates, why = _days(a["dates"], "axis.dates")
    if why:
        return why
    if dates and (dates[0] < first or dates[-1] > t_day):
        return "axis.dates 가 [첫 저장일, T] 밖"
    if any(d.weekday() >= 5 for d in dates):
        return "axis.dates 에 주말"
    years = a["calendar_years"]
    if not isinstance(years, list) or not all(
        isinstance(y, int) and not isinstance(y, bool) for y in years
    ):
        return "axis.calendar_years 가 연도 목록이 아님"
    if years != sorted(set(years)):
        return "axis.calendar_years 중복 · 역순"
    modes = a["modes"]
    want = {str(y) for y in range(first.year, t_day.year + 1)}
    if not isinstance(modes, dict) or set(modes) != want:
        return "axis.modes 연도가 [첫 저장일, T] 와 다름"
    for y, m in modes.items():
        if m != (prices.MODE_FILE if int(y) in years else prices.MODE_KOSPI):
            return f"axis.modes[{y}] 가 연도 파일 유무와 다름"
    latest = a["kospi_latest"]
    if latest is not None and _day(latest) is None:
        return "axis.kospi_latest 날짜 해석 불가"
    skipped, why = _days(a["skipped_weekdays"], "axis.skipped_weekdays")
    if why:
        return why
    axis_set = set(dates)
    for d in skipped:
        if (
            d.weekday() >= 5
            or not first <= d < t_day
            or d in axis_set
            or modes[str(d.year)] != prices.MODE_KOSPI
        ):
            return f"axis.skipped_weekdays {d.isoformat()} 가 축과 맞지 않음"
    if a["problem"] is not None and not isinstance(a["problem"], str):
        return "axis.problem 이 글자가 아님"
    if a["problem"] != prices.axis_problem(T, a):
        return "axis.problem 이 축에서 다시 판정한 값과 다름"
    return None


def snapshot_problem(snap: Any) -> Optional[str]:
    """snapshot 계약 검사 — 모양뿐 아니라 날짜 해석 · 정렬 · 중복 · 건수 · 축 내부 일치. 문제 없으면 None.

    만들 때(`build_snapshot`) · 파일에서 읽을 때(`load_snapshot`) · 계산 시작(`study.prepare`) 세 곳이 같이 쓴다.
    값의 품질(비정상 종가 · 허용 밖 출처 · 경계)은 여기서 거르지 않는다 — 06 판정이 표본 제외 사유로 센다.
    """
    if not isinstance(snap, dict):
        return "JSON 객체가 아님"
    if snap.get("schema") != SCHEMA:
        return f"schema {snap.get('schema')!r} ≠ {SCHEMA}"
    if set(snap) != _TOP_KEYS:
        return "최상위 칸이 다름"
    T = snap["T"]
    t_day = _day(T)
    if t_day is None:
        return f"기준일 T 해석 불가 {T!r}"
    if snap["price_basis_label"] != prices.PRICE_BASIS_LABEL:
        return "가격 의미 라벨이 06 과 다름"
    e = snap["etfs"]
    if not isinstance(e, dict):
        return "etfs 가 객체가 아님"
    firsts = []
    for t, entry in e.items():
        if not (isinstance(t, str) and t.isascii() and t.isalnum()):
            return f"ticker {t!r} 형식 다름"
        if not isinstance(entry, dict) or set(entry) != {"name", "rows"}:
            return f"{t} 칸이 다름"
        if entry["name"] is not None and not isinstance(entry["name"], str):
            return f"{t} 이름이 글자가 아님"
        rows = entry["rows"]
        if not isinstance(rows, list):
            return f"{t} 저장 행이 목록이 아님"
        for k, r in enumerate(rows):
            why = _row_problem(t, k, r)
            if why:
                return why
        days, why = _days([r[0] for r in rows], f"{t} 저장 행 날짜")
        if why:
            return why
        if days and days[0] <= t_day:
            firsts.append(days[0])
    why = _holdings_problem(snap["holdings"], len(e))
    if why:
        return why
    return _axis_problem(snap["axis"], T, t_day, min(firsts) if firsts else t_day)


def load_snapshot(path: Path) -> dict[str, Any]:
    """`--snapshot` 파일 — 읽기 실패 · 형식 다름 = SnapshotError(CHECK_REQUIRED · 계산 오류로 보이지 않음)."""
    try:
        snap = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise SnapshotError(f"snapshot 파일을 읽을 수 없음: {type(e).__name__}") from e
    problem = snapshot_problem(snap)
    if problem:
        raise SnapshotError(f"snapshot 형식 다름: {problem}")
    return snap


def rows_of(entry: dict[str, Any]) -> list[prices.PriceRow]:
    """snapshot 행 → 06 PriceRow(date · close · source · fetched_at · change 순서)."""
    return [prices.PriceRow(*r) for r in entry["rows"]]


def digest(snapshot: dict[str, Any]) -> str:
    return prices.canonical_hash(snapshot)
