"""POC5-05 개정 2 — '시장 흐름 보기' 읽기 전용 조회(설계 §8 · §11-1 Q-B 판정 · PLAN §1-5 · §2-7).

사용자가 History 의 보유 기간에서 '시장 흐름 보기' 를 누를 때만 부른다(History 조회 · 종목
선택은 부르지 않는다 · 이 조회가 없거나 실패해도 개인 거래 · History 손익 조회는 무관).

```text
읽기     PC 시세 DB 를 `file:...?mode=ro` 로만 연다(ledger_outcome_prices.open_ro) — CREATE ·
         INSERT · 외부 조회 0 · 연결 때 CREATE TABLE 을 실행하는 기존 조회 함수는 쓰지 않는다
계열     ETF  = etf_daily_price(ticker · date · close · source) — 종목 구분은 etf_master 존재 여부
         시장 = market_benchmark_daily_price · benchmark_id='KOSPI'
         개별주 = 자료 없음(PC 개별주 일별 종가 미수집 · etf_daily_price 에 행이 있어도 쓰지 않음)
         KRX 무조정 표는 읽지 않는다(모듈 계약 'UI · ML 로 확장하지 않는다')
기준일    거래일이 거래일이면 그날, 아니면 운영 캘린더의 다음 거래일(Calendar.days_from(day, 1)) ·
         판정 근거(연도 파일 / 평일 기본)를 함께 담는다 — 가격표 행으로 휴장을 추론하지 않는다
값       이벤트별 '기준일 → 마지막 저장일' · 종료된 실제 매수 기간의 '첫 매수 기준일 → 마지막 매도
         기준일' · 같은 두 날짜의 KOSPI(양 끝이 모두 있을 때만) — 인접일 · 다른 계열로 메우지 않는다
출처     ETF = FinanceDataReader · NAVER_FDR 끼리만 비교(다르면 source_differs) · 그 밖 = 비교 불가
         KOSPI = NAVER_FDR · FinanceDataReader/KS11 · KRX_OPEN_API/idx_kospi_dd_trd 끼리 비교
```

변화율 = Decimal(정밀도 40) 십진 문자열(화면 반올림은 UI 몫). '마지막 저장일' 은 오늘 시세가
아니다. 결과는 정형 값 · 정형 문장만 담는다(자유 생성 코멘트 · 모델 판단 없음).
"""

from __future__ import annotations

import math
import sqlite3
from decimal import Decimal, localcontext
from pathlib import Path
from typing import Any, Optional

from app.market_benchmark_store import KOSPI_ID
from app.market_briefing.calendar import (
    SOURCE_SNAPSHOT,
    SOURCE_WEEKDAY_FALLBACK,
    check_trading_day,
    parse_date,
)
from app.three_push_runtime import ledger_outcome_prices as lop

SCHEMA = "holdings_market_flow_v1"

STATUS_OK = "OK"
STATUS_NO_DATA = "NO_DATA"
STATUS_NOT_COMPARABLE = "NOT_COMPARABLE"

KIND_ETF = "ETF"
KIND_STOCK = "STOCK"
KIND_UNKNOWN = "UNKNOWN"

SERIES_TICKER = "ETF"
SERIES_MARKET = "KOSPI"

ETF_TABLE = "etf_daily_price"
MASTER_TABLE = "etf_master"
MARKET_TABLE = "market_benchmark_daily_price"

# 비교 가능한 출처(설계 §11-1 Q-B · PLAN §2-7 — PC 실측 출처 기준). 이 밖의 출처가 한쪽
# 끝에 있으면 가격 기준(조정 ↔ 무조정 등)을 확인할 수 없어 비교 불가다.
ETF_SOURCES = frozenset({"FinanceDataReader", "NAVER_FDR"})
KOSPI_SOURCES = frozenset(
    {"NAVER_FDR", "FinanceDataReader/KS11", "KRX_OPEN_API/idx_kospi_dd_trd"}
)

_SERIES = {
    SERIES_TICKER: {
        "table": ETF_TABLE,
        "series_name": "ETF 저장 종가",
        "comparable_sources": sorted(ETF_SOURCES),
    },
    SERIES_MARKET: {
        "table": MARKET_TABLE,
        "benchmark_id": KOSPI_ID,
        "series_name": "KOSPI 저장 종가",
        "comparable_sources": sorted(KOSPI_SOURCES),
    },
}

_ANCHORS = ("BASELINE", "REGISTER")  # 매수일 미상으로 시작한 기간
_OPENERS = (*_ANCHORS, "BUY")
_CYCLE_STATUS = ("OPEN", "CLOSED")
_EVENT_KINDS = ("BUY", "SELL")

_RULE_LABEL = {SOURCE_SNAPSHOT: "연도 파일", SOURCE_WEEKDAY_FALLBACK: "평일 기본"}

# 항목 상태 사유(정형 문구 · 한국어 짧게).
REASONS = {
    "NO_DB": "자료 없음(PC 시세 DB 없음)",
    "NO_TABLE": "자료 없음(가격 표 없음)",
    "ASSET_UNKNOWN": "자료 없음(종목 구분 확인 불가)",
    "STOCK_NOT_COLLECTED": "자료 없음(PC 개별주 일별 종가 미수집)",
    "BASIS_UNDETERMINED": "자료 없음(기준일 판정 불가)",
    "NO_ROWS": "자료 없음(저장 종가 없음)",
    "LATEST_BEFORE_BASIS": "변화율 없음(마지막 저장일이 기준일보다 이름)",
    "BASIS_ROW_MISSING": "자료 없음(기준일 종가 없음 · 인접일 대체 안 함)",
    "END_ROW_MISSING": "자료 없음(끝 날짜 종가 없음 · 인접일 대체 안 함)",
    "NO_WINDOW": "자료 없음(종목 비교 구간 없음)",
    "WINDOW_INVALID": "자료 없음(구간 끝이 시작보다 이름)",
    "SOURCE_UNVERIFIED": "비교 불가(가격 기준 확인 안 됨)",
}

# 보유 기간 항목을 계산하지 않는 사유.
PERIOD_REASONS = {
    "PURCHASE_DATE_UNKNOWN": "매수일 미상 — 매수 전후 변화 계산 안 함",
    "CYCLE_OPEN": "보유 중 — 보유 기간 변화는 전량매도 뒤 계산",
    "NO_BUY": "매수 기록 없음 — 보유 기간 변화 계산 안 함",
    "NO_SELL": "매도 기록 없음 — 보유 기간 변화 계산 안 함",
}

NOTES = (
    "저장 종가 비교값 — 체결단가로 계산한 개인 손익과 다르다.",
    "마지막 저장일은 PC 시세 DB 에 저장된 마지막 날짜이며 오늘 시세가 아니다.",
    "기준일 종가가 없으면 인접일 · 다른 계열로 메우지 않는다.",
    "정형 값만 제공 — 자유 생성 코멘트 · 모델 판단 없음.",
)


class MarketFlowReadError(Exception):
    """DB 파일은 있는데 읽지 못함(sqlite 오류 · 손상) — '자료 없음' 과 구분해 '조회 실패' 로 알린다.

    파일 없음 · 표 없음 · 행 없음은 이 예외가 아니라 항목별 '자료 없음' 이다.
    """


# ── 입력 확인 ─────────────────────────────────────────────────────────────────


def _validated(ticker: Any, cycle: Any) -> tuple[str, list[dict[str, str]]]:
    """호출부(이력 계산 결과)가 넘긴 기간의 형식만 본다 — 틀리면 ValueError."""
    if not isinstance(ticker, str) or not ticker.strip():
        raise ValueError("ticker")
    if not isinstance(cycle, dict):
        raise ValueError("cycle")
    if not isinstance(cycle.get("cycle_id"), str):
        raise ValueError("cycle_id")
    if cycle.get("opened_by") not in _OPENERS:
        raise ValueError("opened_by")
    if cycle.get("status") not in _CYCLE_STATUS:
        raise ValueError("status")
    events = cycle.get("events")
    if not isinstance(events, list):
        raise ValueError("events")
    out: list[dict[str, str]] = []
    for ev in events:
        if (
            not isinstance(ev, dict)
            or not isinstance(ev.get("record_id"), str)
            or ev.get("kind") not in _EVENT_KINDS
            or parse_date(str(ev.get("trade_date") or "")) is None
        ):
            raise ValueError("events")
        out.append({k: ev[k] for k in ("record_id", "kind", "trade_date")})
    return ticker.strip(), out


# ── 기준일(운영 캘린더 · 가격표를 보지 않는다) ─────────────────────────────────


class _BasisDays:
    """거래일 → 기준일. 캘린더 판정은 기존 `Calendar` · `check_trading_day` 를 그대로 쓴다."""

    def __init__(self, calendar_dir: Optional[Path]) -> None:
        self._dir = calendar_dir
        self._cal = lop.Calendar(calendar_dir)
        self._decided: dict[str, str] = {}

    def _decided_by(self, day: str) -> str:
        if day not in self._decided:
            self._decided[day] = check_trading_day(day, directory=self._dir).decided_by
        return self._decided[day]

    def of(self, trade_date: str) -> dict[str, Any]:
        got = self._cal.days_from(trade_date, 1)
        basis = got[0] if got else None
        trade_rule = self._decided_by(trade_date)
        basis_rule = self._decided_by(basis) if basis else None
        moved = basis is not None and basis != trade_date
        if basis is None:
            note = "기준일 판정 불가"
        elif moved:
            note = (
                f"비거래일({_RULE_LABEL.get(trade_rule, trade_rule)}) → "
                f"다음 거래일({_RULE_LABEL.get(basis_rule, basis_rule)})"
            )
        else:
            note = f"거래일 그대로({_RULE_LABEL.get(trade_rule, trade_rule)})"
        return {
            "trade_date": trade_date,
            "trade_date_is_trading_day": self._cal.is_trading(trade_date),
            "trade_date_decided_by": trade_rule,
            "basis_date": basis,
            "basis_date_decided_by": basis_rule,
            "moved_to_next_trading_day": moved,
            "basis_note": note,
        }


# ── 시세 DB 읽기(mode=ro · 같은 질의는 한 번만) ──────────────────────────────


def _point(row: Optional[tuple[Any, ...]]) -> Optional[dict[str, Any]]:
    if row is None:
        return None
    try:
        close = float(row[1])
    except (TypeError, ValueError) as exc:
        raise MarketFlowReadError("close_unreadable") from exc
    if not math.isfinite(close):
        raise MarketFlowReadError("close_unreadable")
    return {"date": str(row[0]), "close": close, "source": row[2]}


class _Reader:
    def __init__(self, con: Optional[sqlite3.Connection]) -> None:
        self.con = con
        self._tables: dict[str, bool] = {}
        self._rows: dict[tuple[str, str], Optional[dict[str, Any]]] = {}
        self._latest: dict[str, Optional[dict[str, Any]]] = {}

    @property
    def db_present(self) -> bool:
        return self.con is not None

    def has_table(self, name: str) -> bool:
        if self.con is None:
            return False
        if name not in self._tables:
            row = self.con.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                (name,),
            ).fetchone()
            self._tables[name] = row is not None
        return self._tables[name]

    def asset_kind(self, ticker: str) -> str:
        """etf_master 에 있으면 ETF · 없으면 개별주 · 표가 없으면 확인 불가."""
        if self.con is None or not self.has_table(MASTER_TABLE):
            return KIND_UNKNOWN
        row = self.con.execute(
            f"SELECT 1 FROM {MASTER_TABLE} WHERE ticker = ? LIMIT 1", (ticker,)
        ).fetchone()
        return KIND_ETF if row else KIND_STOCK

    def _where(self, series: str, ticker: str) -> tuple[str, str, tuple[Any, ...]]:
        if series == SERIES_MARKET:
            return (
                MARKET_TABLE,
                "benchmark_id = ? AND close IS NOT NULL AND close > 0",
                (KOSPI_ID,),
            )
        return ETF_TABLE, "ticker = ? AND close IS NOT NULL AND close > 0", (ticker,)

    def close_on(self, series: str, ticker: str, day: str) -> Optional[dict[str, Any]]:
        """정확히 그 날짜의 저장 종가 — 인접일로 메우지 않는다."""
        key = (series, day)
        if key not in self._rows:
            table, cond, args = self._where(series, ticker)
            row = self.con.execute(  # type: ignore[union-attr]
                f"SELECT date, close, source FROM {table} WHERE {cond} AND date = ?"
                " LIMIT 1",
                (*args, day),
            ).fetchone()
            self._rows[key] = _point(row)
        return self._rows[key]

    def latest(self, series: str, ticker: str) -> Optional[dict[str, Any]]:
        """그 계열의 그 종목 마지막 저장일(close>0) 행."""
        if series not in self._latest:
            table, cond, args = self._where(series, ticker)
            row = self.con.execute(  # type: ignore[union-attr]
                f"SELECT date, close, source FROM {table} WHERE {cond}"
                " ORDER BY date DESC LIMIT 1",
                args,
            ).fetchone()
            self._latest[series] = _point(row)
        return self._latest[series]


# ── 항목 ─────────────────────────────────────────────────────────────────────


def _change_pct(start_close: float, end_close: float) -> str:
    """(끝 − 시작) / 시작 × 100 — 반올림 없이 십진 문자열."""
    with localcontext() as ctx:
        ctx.prec = 40
        a = Decimal(str(start_close))
        b = Decimal(str(end_close))
        return format(((b - a) / a * 100).normalize(), "f")


def _series_desc(series: str) -> dict[str, Any]:
    """결과에 담는 계열 설명(표 이름 · 계열 이름 · 비교 가능 출처) — 호출마다 새 사본."""
    desc = dict(_SERIES[series])
    desc["comparable_sources"] = list(desc["comparable_sources"])
    return desc


def _item(
    series: str,
    *,
    status: str,
    code: Optional[str],
    start_date: Optional[str],
    end_date: Optional[str],
    start: Optional[dict[str, Any]] = None,
    end: Optional[dict[str, Any]] = None,
    change_pct: Optional[str] = None,
) -> dict[str, Any]:
    desc = _SERIES[series]
    return {
        "series": series,
        "series_name": desc["series_name"],
        "table": desc["table"],
        "status": status,
        "reason_code": code,
        "reason": REASONS[code] if code else None,
        "start_date": start_date,
        "end_date": end_date,
        "start": start,
        "end": end,
        "change_pct": change_pct,
        "source_differs": bool(start and end and start["source"] != end["source"]),
    }


def _no(
    series: str,
    code: str,
    start_date: Optional[str],
    end_date: Optional[str],
    **points: Optional[dict[str, Any]],
) -> dict[str, Any]:
    return _item(
        series,
        status=STATUS_NO_DATA,
        code=code,
        start_date=start_date,
        end_date=end_date,
        **points,
    )


def _window(
    reader: _Reader, series: str, ticker: str, start_date: str, end_date: str
) -> dict[str, Any]:
    """정해진 두 날짜의 저장 종가 비교 — 양 끝 행이 모두 있을 때만 값."""
    if end_date < start_date:
        return _no(series, "WINDOW_INVALID", start_date, end_date)
    start = reader.close_on(series, ticker, start_date)
    end = reader.close_on(series, ticker, end_date)
    if start is None:
        return _no(series, "BASIS_ROW_MISSING", start_date, end_date, end=end)
    if end is None:
        return _no(series, "END_ROW_MISSING", start_date, end_date, start=start)
    # 한쪽 끝이라도 비교 가능 출처 밖이면 가격 기준을 확인할 수 없다 → 비교 불가(값 없음).
    allowed = ETF_SOURCES if series == SERIES_TICKER else KOSPI_SOURCES
    ok = start["source"] in allowed and end["source"] in allowed
    return _item(
        series,
        status=STATUS_OK if ok else STATUS_NOT_COMPARABLE,
        code=None if ok else "SOURCE_UNVERIFIED",
        start_date=start_date,
        end_date=end_date,
        start=start,
        end=end,
        change_pct=_change_pct(start["close"], end["close"]) if ok else None,
    )


def _pair(
    reader: _Reader,
    series: str,
    ticker: str,
    gate: Optional[str],
    start_date: Optional[str],
    end_date: Optional[str],
    missing: str,
) -> dict[str, Any]:
    """막힘(gate) → 구간 없음(missing) → 두 날짜 비교 순서로 항목 하나를 만든다."""
    if gate:
        return _no(series, gate, start_date, end_date)
    if start_date is None or end_date is None:
        return _no(series, missing, start_date, end_date)
    return _window(reader, series, ticker, start_date, end_date)


def _ticker_gate(reader: _Reader, asset_kind: str) -> Optional[str]:
    if not reader.db_present:
        return "NO_DB"
    if asset_kind == KIND_UNKNOWN:
        return "ASSET_UNKNOWN"
    if asset_kind == KIND_STOCK:
        return "STOCK_NOT_COLLECTED"
    if not reader.has_table(ETF_TABLE):
        return "NO_TABLE"
    return None


def _market_gate(reader: _Reader) -> Optional[str]:
    if not reader.db_present:
        return "NO_DB"
    if not reader.has_table(MARKET_TABLE):
        return "NO_TABLE"
    return None


def _event(
    reader: _Reader,
    days: _BasisDays,
    ev: dict[str, str],
    ticker: str,
    asset_kind: str,
) -> dict[str, Any]:
    """BUY · SELL 하나 — 기준일 종가 → 그 종목 마지막 저장일 종가 · 같은 두 날짜 KOSPI."""
    basis = days.of(ev["trade_date"])
    b = basis["basis_date"]
    gate = _ticker_gate(reader, asset_kind)
    latest = reader.latest(SERIES_TICKER, ticker) if gate is None else None
    latest_date = latest["date"] if latest else None
    if gate:
        tick = _no(SERIES_TICKER, gate, b, None)
    elif b is None:
        tick = _no(SERIES_TICKER, "BASIS_UNDETERMINED", None, latest_date, end=latest)
    elif latest is None:
        tick = _no(SERIES_TICKER, "NO_ROWS", b, None)
    elif latest["date"] < b:
        tick = _no(SERIES_TICKER, "LATEST_BEFORE_BASIS", b, latest_date, end=latest)
    else:
        tick = _window(reader, SERIES_TICKER, ticker, b, latest["date"])

    # KOSPI 는 종목과 **같은 두 날짜**(기준일 · 종목 마지막 저장일)만 본다.
    end_date = latest_date if (b and latest_date and latest_date >= b) else None
    market = _pair(
        reader, SERIES_MARKET, ticker, _market_gate(reader), b, end_date, "NO_WINDOW"
    )

    label = "매수 기준일" if ev["kind"] == "BUY" else "매도 기준일"
    return {
        "record_id": ev["record_id"],
        "kind": ev["kind"],
        "trade_date": ev["trade_date"],
        "basis": basis,
        "window_label": f"{label} → 마지막 저장일",
        "latest_stored_date": latest_date,
        "ticker": tick,
        "market": market,
    }


def _holding_period(
    reader: _Reader,
    days: _BasisDays,
    *,
    opened_by: str,
    status: str,
    events: list[dict[str, str]],
    ticker: str,
    asset_kind: str,
) -> dict[str, Any]:
    """실제 매수로 시작해 종료된 기간만 — 첫 BUY 기준일 → 마지막 SELL 기준일."""
    out: dict[str, Any] = dict.fromkeys(
        ("reason_code", "reason", "start_record_id", "end_record_id")
        + ("start_basis", "end_basis", "ticker", "market")
    )
    out.update(computed=False, window_label="첫 매수 기준일 → 마지막 매도 기준일")
    buys = [e for e in events if e["kind"] == "BUY"]
    sells = [e for e in events if e["kind"] == "SELL"]
    if opened_by in _ANCHORS:
        code: Optional[str] = "PURCHASE_DATE_UNKNOWN"
    elif status != "CLOSED":
        code = "CYCLE_OPEN"
    elif not buys:
        code = "NO_BUY"
    elif not sells:
        code = "NO_SELL"
    else:
        code = None
    if code:
        out.update(reason_code=code, reason=PERIOD_REASONS[code])
        return out

    first, last = buys[0], sells[-1]  # 이벤트는 계산 순서(거래일 · seq)대로 온다
    start_basis, end_basis = days.of(first["trade_date"]), days.of(last["trade_date"])
    s, e = start_basis["basis_date"], end_basis["basis_date"]
    gates = {
        SERIES_TICKER: _ticker_gate(reader, asset_kind),
        SERIES_MARKET: _market_gate(reader),
    }
    tick, market = (
        _pair(reader, sr, ticker, gates[sr], s, e, "BASIS_UNDETERMINED")
        for sr in (SERIES_TICKER, SERIES_MARKET)
    )
    out.update(
        computed=True,
        start_record_id=first["record_id"],
        end_record_id=last["record_id"],
        start_basis=start_basis,
        end_basis=end_basis,
        ticker=tick,
        market=market,
    )
    return out


# ── 공개 함수 ─────────────────────────────────────────────────────────────────


def build_market_flow(
    *,
    ticker: str,
    cycle: dict,
    db_path: Optional[Path] = None,
    calendar_dir: Optional[Path] = None,
    connection: Optional[sqlite3.Connection] = None,
) -> dict:
    """선택한 보유 기간 하나의 시장 흐름(저장 종가 · 정형 값). 쓰기 · 외부 조회 0.

    `cycle` = {cycle_id, opened_by: BASELINE|REGISTER|BUY, status: OPEN|CLOSED,
    events: [{record_id, kind: BUY|SELL, trade_date}] — 계산 순서 · 유효 거래만}.
    DB 파일 없음 · 표 없음 · 행 없음 = 항목별 NO_DATA. DB 파일은 있는데 읽기 오류 =
    `MarketFlowReadError`. 형식이 틀린 입력 = `ValueError`. `connection` = 호출부가 연 읽기 전용
    연결(POC5-06 이 같은 읽기로 가격도 읽을 때 · 닫지 않는다).
    """
    ticker, events = _validated(ticker, cycle)
    opened_by, status = cycle["opened_by"], cycle["status"]
    days = _BasisDays(calendar_dir)
    path = Path(db_path) if db_path is not None else lop.market_db_path()
    con: Optional[sqlite3.Connection] = connection
    try:
        try:
            con = con if connection is not None else lop.open_ro(path)
        except FileNotFoundError:
            con = None  # 파일 없음 = 자료 없음(만들지 않는다)
        reader = _Reader(con)
        asset_kind = reader.asset_kind(ticker)
        gate = _ticker_gate(reader, asset_kind)
        latest = None if gate else reader.latest(SERIES_TICKER, ticker)
        flows = [_event(reader, days, ev, ticker, asset_kind) for ev in events]
        period = _holding_period(
            reader,
            days,
            opened_by=opened_by,
            status=status,
            events=events,
            ticker=ticker,
            asset_kind=asset_kind,
        )
    except sqlite3.Error as exc:
        raise MarketFlowReadError(
            f"market_db_read_failed:{type(exc).__name__}"
        ) from exc
    finally:
        if con is not None and connection is None:
            con.close()

    unknown = opened_by in _ANCHORS
    return {
        "schema": SCHEMA,
        "read_only": True,
        "ticker": ticker,
        "cycle_id": cycle["cycle_id"],
        "opened_by": opened_by,
        "cycle_status": status,
        "purchase_date_unknown": unknown,
        "purchase_date_note": (
            PERIOD_REASONS["PURCHASE_DATE_UNKNOWN"] if unknown else None
        ),
        "db_present": reader.db_present,
        "asset_kind": asset_kind,
        "series": {
            "ticker": _series_desc(SERIES_TICKER),
            "market": _series_desc(SERIES_MARKET),
        },
        "latest_stored_date": latest["date"] if latest else None,
        "latest_stored_close": latest["close"] if latest else None,
        "latest_stored_source": latest["source"] if latest else None,
        "events": flows,
        "holding_period": period,
        "notes": list(NOTES),
        "free_commentary": None,
    }


__all__ = [
    "ETF_SOURCES",
    "KOSPI_SOURCES",
    "MarketFlowReadError",
    "STATUS_NOT_COMPARABLE",
    "STATUS_NO_DATA",
    "STATUS_OK",
    "build_market_flow",
]
