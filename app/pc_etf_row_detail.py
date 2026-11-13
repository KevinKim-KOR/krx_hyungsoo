"""POC6-29 — 행 상세 수치(PC · 저장 자료 읽기 전용 · `GET /market/etf-detail?tickers=…`).

PLAN `docs/ai_plan/POC6/POC6_29_ETF_MARKET_DISCOVERY_REFOCUS_PLAN_V1.md` §2-7 · §3-3 · 판정 Q4-1.

「보유」 · 「섹터요약」 · 「후보리스트」(행 상세 · [표]) · 「보유와 후보 비교」가 같은 응답 모양 · 같은 값 · 같은
날짜를 쓴다. 새 산식 없이 기존 계산 규칙을 그대로 쓴다.

- 공통 끝일 = ETF 목록(etf_master) 종목의 저장 최신일(요약 `build_summary` 와 같은 질의).
- 일간 · 5 · 20구간 = 그 종목 마지막 유효 저장 행에서 1 · 5 · 20행 앞(`_window_return_pct` · 21행 읽기 =
  `read_recent_rows` — 「보유」 가격 흐름과 같은 행 조건).
- 1 · 3 · 6 · 12개월 = 공통 끝일 − 30 · 90 · 180 · 365일 이후 첫 저장 행 → 공통 끝일(`period_value`).
  069500 에 같은 규칙으로 정한 공통 기간과 시작 · 끝이 같을 때만 값(요약 `criteria` 와 같은 판정 · 같은 값).
- 끝일이 공통 끝일과 다른 종목(가격이 멈춘 ETF 등)은 값을 비우고 '기간 다름' + 실제 날짜.
- 20구간 KODEX 200 차이 = 이 종목 20구간 − 069500 20구간 — 실제 시작일 · 끝일이 **둘 다** 같을 때만.
- KODEX 200 동일 기간 1 · 3개월 = `same_period_kodex200.compare`(1 · 3개월 값이 ok 일 때만 · 요약과 같은 입력).
- 최근 고점 대비 = `compute_stored_drawdown`(20저장일 · 069500 창과 시작 · 끝 비교 = 요약과 같음).
- 시장가 · NAV · 괴리율 = `etf_nav_daily` 그 종목 최신 1행(`fetch_latest_nav` 와 같은 순서 · 날짜 하나) ·
  괴리 표시 = `classify_discount_flag`(3% · 5%). 개별 주식 = 해당 없음.

계산된 0 은 0.0(ok) 그대로 두고 자료 없음(missing) · 기간 다름(period_differs) · 해당 없음(not_applicable)은
다른 상태 값으로 둔다. 외부 호출 · 쓰기 0. DB 는 `mode=ro` 로만 연다.
"""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from app.etf_nav_fetcher import classify_discount_flag
from app.market_regime import KODEX200_TICKER
from app.market_topn_helpers import (
    ONE_MONTH_LOOKBACK_DAYS,
    SIX_MONTH_LOOKBACK_DAYS,
    THREE_MONTH_LOOKBACK_DAYS,
    TWELVE_MONTH_LOOKBACK_DAYS,
)
from app.pc_etf_compare_holdings import RecentRow, read_recent_rows
from app.pc_etf_compare_periods import (
    CRIT_MISSING,
    CRIT_OK,
    CRIT_PERIOD_DIFFERS,
    period_value,
    period_window,
    price_state,
)
from app.pc_etf_compare_summary import _ro
from app.pc_stored_drawdown import _read_window, compute_stored_drawdown
from app.same_period_kodex200 import STATUS_OK as SAME_OK
from app.same_period_kodex200 import close_by_date, valid_close
from app.same_period_kodex200 import compare as same_period_compare
from app.short_term_momentum import _window_return_pct

MAX_TICKERS = 30
ROW_WINDOWS = {"daily": 1, "w5": 5, "w20": 20}
MONTHS = {
    "m1": ONE_MONTH_LOOKBACK_DAYS,
    "m3": THREE_MONTH_LOOKBACK_DAYS,
    "m6": SIX_MONTH_LOOKBACK_DAYS,
    "m12": TWELVE_MONTH_LOOKBACK_DAYS,
}
NAV_USABLE = ("ok", "partial")  # 판단 근거 미리보기 `nav_line` 과 같은 규칙

R_NO_ROWS = "no_rows"
R_NO_START = "no_start_row"
R_SHORT = "insufficient_history"
R_END = "end_differs"
R_START = "start_differs"
R_KODEX = "kodex_window_unknown"

Window = tuple[dict[str, Any], Optional[float]]  # (응답 칸, 반올림 전 값 — ok 일 때만)


def _period(
    status: str,
    *,
    raw: Optional[float] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
    start_close: Optional[float] = None,
    end_close: Optional[float] = None,
    reason: Optional[str] = None,
) -> Window:
    ok = status == CRIT_OK
    return (
        {
            "status": status,
            "value": round(raw, 4) if ok and raw is not None else None,
            "start": start,
            "end": end,
            "start_close": start_close if ok else None,
            "end_close": end_close if ok else None,
            "reason": None if ok else reason,
        },
        raw if ok else None,
    )


def _row_window(series: Sequence[tuple[str, float]], n: int, end: str) -> Window:
    """그 종목 마지막 유효 행에서 n행 앞 → 마지막 행(`_window_return_pct` 와 같은 행)."""
    if not series:
        return _period(CRIT_MISSING, reason=R_NO_ROWS)
    last = series[-1][0]
    if len(series) < n + 1:
        return _period(CRIT_MISSING, end=last, reason=R_SHORT)
    (sd, sc), (ed, ec) = series[-(n + 1)], series[-1]
    if ed != end:
        return _period(CRIT_PERIOD_DIFFERS, start=sd, end=ed, reason=R_END)
    raw = _window_return_pct(list(series), n)
    if raw is None:  # 유효 종가만 읽어 생기지 않지만 0 으로 채우지 않는다
        return _period(CRIT_MISSING, start=sd, end=ed, reason=R_SHORT)
    return _period(CRIT_OK, raw=raw, start=sd, end=ed, start_close=sc, end_close=ec)


def _month_reason(valid: Sequence[tuple[str, float]], end: str, days: int) -> str:
    """`period_window` 가 None 인 까닭(같은 판정 순서)."""
    idx = [i for i, (d, _) in enumerate(valid) if d <= end]
    if len(idx) < 2:
        return R_SHORT
    target = (date.fromisoformat(end) - timedelta(days=days)).isoformat()
    first = next((i for i in idx if valid[i][0] >= target), None)
    return R_NO_START if first is None else R_SHORT


def _month(
    valid: Sequence[tuple[str, float]],
    last: Optional[str],
    end: str,
    days: int,
    common: Optional[tuple[str, str]],
) -> Window:
    """1 · 3 · 6 · 12개월 — 요약 `criterion_from_period` 와 같은 판정(기간 다름은 값을 비운다)."""
    if last is None:
        return _period(CRIT_MISSING, reason=R_NO_ROWS)
    if last != end:
        own = period_value(valid, last, days)
        return _period(
            CRIT_PERIOD_DIFFERS,
            start=own["start"] if own else None,
            end=last,
            reason=R_END,
        )
    v = period_value(valid, end, days)
    if v is None:
        return _period(CRIT_MISSING, end=last, reason=_month_reason(valid, end, days))
    if common is None:
        return _period(CRIT_MISSING, start=v["start"], end=v["end"], reason=R_KODEX)
    if (v["start"], v["end"]) != common:
        return _period(
            CRIT_PERIOD_DIFFERS, start=v["start"], end=v["end"], reason=R_START
        )
    return _period(
        CRIT_OK,
        raw=v["raw"],
        start=v["start"],
        end=v["end"],
        start_close=v["start_close"],
        end_close=v["end_close"],
    )


def _excess(mine: Window, kodex: Optional[Window]) -> dict[str, Any]:
    """20구간 KODEX 200 차이 — 이 종목 · 069500 의 실제 시작일 · 끝일이 둘 다 같을 때만."""
    (mp, mraw), (kp, kraw) = mine, (kodex or (None, None))
    out: dict[str, Any] = {
        "status": CRIT_MISSING,
        "value_pctp": None,
        "etf_return_pct": None,
        "kodex200_return_pct": None,
        "start": mp["start"],
        "end": mp["end"],
        "kodex200_start": kp["start"] if kp else None,
        "kodex200_end": kp["end"] if kp else None,
        "reason": None,
    }
    if mp["status"] == CRIT_MISSING:
        out["reason"] = mp["reason"]
    elif kp is None or kp["status"] == CRIT_MISSING:
        out["reason"] = R_KODEX
    elif mp["status"] == CRIT_PERIOD_DIFFERS or kp["status"] == CRIT_PERIOD_DIFFERS:
        out.update(status=CRIT_PERIOD_DIFFERS, reason=R_END)
    elif (mp["start"], mp["end"]) != (kp["start"], kp["end"]):
        out.update(
            status=CRIT_PERIOD_DIFFERS,
            reason=R_END if mp["end"] != kp["end"] else R_START,
        )
    elif mraw is not None and kraw is not None:
        out.update(
            status=CRIT_OK,
            value_pctp=round(mraw - kraw, 4),
            etf_return_pct=round(mraw, 4),
            kodex200_return_pct=round(kraw, 4),
        )
    return out


def _same(month: Window, kodex_close: Mapping[str, float]) -> dict[str, Any]:
    """KODEX 200 동일 기간 — 1 · 3개월 값이 ok 일 때만 `compare`.

    요약 `same_kodex_1m` 과 같은 입력(소수 4자리 1개월 값)을 넘긴다 — 표 · 행 상세가 같은 값이 되게.
    """
    p, _ = month
    out: dict[str, Any] = {
        "status": p["status"],
        "value": None,
        "etf_return_pct": None,
        "kodex200_return_pct": None,
        "start": p["start"],
        "end": p["end"],
        "reason": p["reason"],
    }
    if p["status"] != CRIT_OK:
        return out
    cmp = same_period_compare(p["value"], p["start"], p["end"], kodex_close)
    if cmp["status"] != SAME_OK:
        out.update(status=CRIT_MISSING, reason=cmp["reason"])
        return out
    out.update(
        value=cmp["diff_pctp"],
        etf_return_pct=cmp["candidate_return_pct"],
        kodex200_return_pct=cmp["kodex200_return_pct"],
    )
    return out


def _drawdown(
    con: sqlite3.Connection,
    ticker: str,
    last: Optional[str],
    kodex_window: Optional[tuple[Optional[str], Optional[str]]],
) -> dict[str, Any]:
    """최근 고점 대비 — 요약 `criteria.drawdown` 과 같은 판정(기간 다름도 값은 그 종목 창 그대로)."""
    rows = _read_window(con, ticker, last) if last else []
    dd = compute_stored_drawdown(rows, end_date=last).model_dump()
    if last is None:
        out = {"status": CRIT_MISSING, "value": None, "reason": R_NO_ROWS}
    elif dd["status"] != "ok":
        out = {"status": CRIT_MISSING, "value": None, "reason": dd.get("reason")}
    elif kodex_window is None:
        out = {"status": CRIT_MISSING, "value": None, "reason": R_KODEX}
    elif (dd.get("start_date"), dd.get("end_date")) != kodex_window:
        out = {
            "status": CRIT_PERIOD_DIFFERS,
            "value": dd["value_pct"],
            "reason": R_END if dd.get("end_date") != kodex_window[1] else R_START,
        }
    else:
        out = {"status": CRIT_OK, "value": dd["value_pct"], "reason": None}
    out.update(
        start=dd.get("start_date"),
        end=dd.get("end_date"),
        peak_date=dd.get("peak_date"),
        peak_close=dd.get("peak_close"),
        close=dd.get("close"),
    )
    return out


def _nav(
    con: sqlite3.Connection, ticker: str, is_etf: bool, has_table: bool
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "status": "missing" if is_etf else "not_applicable",
        "nav": None,
        "market_price": None,
        "discount_rate_pct": None,
        "flag": None,
        "asof": None,
        "row_status": None,
        "message": None,
    }
    if not is_etf or not has_table:
        return out
    row = con.execute(
        "SELECT asof, nav, market_price, discount_rate_pct, status, message "
        "FROM etf_nav_daily WHERE etf_ticker = ? "
        "ORDER BY asof DESC, created_at DESC LIMIT 1",
        (ticker,),
    ).fetchone()
    if row is None:
        return out
    asof, nav, market_price, rate, row_status, message = row
    out.update(asof=asof, row_status=row_status, message=message)
    if row_status in NAV_USABLE and rate is not None:
        out.update(
            status="ok",
            nav=nav,
            market_price=market_price,
            discount_rate_pct=rate,
            flag=classify_discount_flag(rate),
        )
    return out


def _valid_since(
    con: sqlite3.Connection, ticker: str, since: str
) -> list[tuple[str, float]]:
    return [
        (d, float(c))
        for d, c in con.execute(
            "SELECT date, close FROM etf_daily_price WHERE ticker = ? AND date >= ? "
            "ORDER BY date",
            (ticker, since),
        )
        if valid_close(c)
    ]


def _back(day: str, days: int) -> str:
    return (date.fromisoformat(day) - timedelta(days=days)).isoformat()


def _series(recent: Sequence[RecentRow]) -> list[tuple[str, float]]:
    return [(r[0], r[1]) for r in reversed(recent)]


class _Kodex:
    """069500 — 공통 기간(1 · 3 · 6 · 12개월) · 20구간 창 · 동일 기간 종가 · 고점 대비 창(한 번 읽기)."""

    def __init__(self, con: sqlite3.Connection, end: str) -> None:
        recent = read_recent_rows(con, KODEX200_TICKER)
        self.window20: Optional[Window] = (
            _row_window(_series(recent), 20, end) if recent else None
        )
        valid = [
            r
            for r in _valid_since(
                con, KODEX200_TICKER, _back(end, TWELVE_MONTH_LOOKBACK_DAYS)
            )
            if r[0] <= end
        ]
        self.close = close_by_date(valid)
        self.common: dict[str, Optional[tuple[str, str]]] = {}
        for key, days in MONTHS.items():
            w = period_window(valid, end, days)
            self.common[key] = (
                None
                if w is None or valid[w[1]][0] != end
                else (valid[w[0]][0], valid[w[1]][0])
            )
        last = valid[-1][0] if valid else None
        dd = compute_stored_drawdown(
            _read_window(con, KODEX200_TICKER, last) if last else [], end_date=last
        )
        self.dd_window = (dd.start_date, dd.end_date) if dd.status == "ok" else None


def _item(
    con: sqlite3.Connection,
    ticker: str,
    end: str,
    names: Mapping[str, Optional[str]],
    kodex: _Kodex,
    has_nav: bool,
) -> dict[str, Any]:
    recent = read_recent_rows(con, ticker)
    last = recent[0][0] if recent else None
    series = _series(recent)
    rows = {k: _row_window(series, n, end) for k, n in ROW_WINDOWS.items()}
    valid = (
        _valid_since(con, ticker, _back(min(end, last), TWELVE_MONTH_LOOKBACK_DAYS))
        if last
        else []
    )
    months = {
        k: _month(valid, last, end, days, kodex.common[k]) for k, days in MONTHS.items()
    }
    is_etf = ticker in names
    return {
        "ticker": ticker,
        "name": names.get(ticker),
        "is_etf": is_etf,
        "last_date": last,
        "end_price": price_state(last, recent[0][4]) if recent else None,
        **{k: w[0] for k, w in rows.items()},
        **{k: w[0] for k, w in months.items()},
        "excess20": _excess(rows["w20"], kodex.window20),
        "same_kodex": {
            "one_month": _same(months["m1"], kodex.close),
            "three_month": _same(months["m3"], kodex.close),
        },
        "drawdown": _drawdown(con, ticker, last, kodex.dd_window),
        "nav": _nav(con, ticker, is_etf, has_nav),
    }


def _empty(status: str, message: str) -> dict[str, Any]:
    return {
        "status": status,
        "message": message,
        "end_date": None,
        "kodex200": {"window20": None},
        "items": [],
    }


def build_etf_detail(db_path: Path, tickers: Sequence[str]) -> dict[str, Any]:
    """종목들(중복 없음 · 최대 30 — 호출자가 검사)의 상세 수치. 실패도 응답 안의 `status` 로 돌려준다."""
    if not db_path.exists():
        return _empty("missing", "시장 DB 파일이 없습니다.")
    try:
        con = _ro(db_path)
        try:
            end = con.execute(
                "SELECT MAX(p.date) FROM etf_daily_price p "
                "JOIN etf_master m ON m.ticker = p.ticker"
            ).fetchone()[0]
            if not end:
                return _empty("empty", "저장된 가격이 없습니다.")
            marks = ",".join("?" for _ in tickers)
            names = (
                dict(
                    con.execute(
                        f"SELECT ticker, name FROM etf_master WHERE ticker IN ({marks})",
                        tuple(tickers),
                    )
                )
                if tickers
                else {}
            )
            has_nav = (
                con.execute(
                    "SELECT 1 FROM sqlite_master WHERE type = 'table' "
                    "AND name = 'etf_nav_daily'"
                ).fetchone()
                is not None
            )
            kodex = _Kodex(con, end)
            items = [_item(con, t, end, names, kodex, has_nav) for t in tickers]
        finally:
            con.close()
    except (sqlite3.Error, ValueError) as e:
        return _empty("invalid", f"시장 DB 읽기 실패: {type(e).__name__}")
    return {
        "status": "ok",
        "message": None,
        "end_date": end,
        "kodex200": {"window20": kodex.window20[0] if kodex.window20 else None},
        "items": items,
    }
