"""POC6-07 — 선택 ETF 의 종목 이동평균(MA20 · MA60) · 표시값 기준 위치(PC 판단 근거 미리보기 전용 · 읽기 전용).

설계 `docs/ai_design/POC6/POC6-07_SELECTED_ETF_ENTRY_AND_HOLDING_EVIDENCE_DESIGN_V1.md` §3 · §4 ·
PLAN V1 §2 · 판정 `..._PLAN_DECISION_2026-10-23.md` §2 · §3 · §4.

```text
대상     미리보기가 고른 종목 하나. 보유 = etf_master 분류(빈 분류 = 확인 불가 · 개별 종목으로 보지 않음) ·
         후보 = 기존 미리보기대로 ETF(시장 ETF 목록의 후보)
D        미리보기 가격 흐름의 종목 기준일. 보유 = price_dates.end_date(PC 비교 기준일과 같아야 함 ·
         기존 흐름 · 흔들림 규칙) · 후보 = 미리보기 읽기의 끝 날짜(목록 응답 날짜와 다르면 맞추지 않음)
읽기     D 가 정해지면 mode=ro 로 `date <= D` 원본 최근 60행 1회(거르지 않음)
관측 전체 D 행 없음 · D 종가 무효 · 같은 D 의 기존 가격 근거와 모순 → 확인 불가(평균 없음)
창       MA20 = 끝 20행 · MA60 = 끝 60행 · 각각 행 부족 → 날짜 형식 → 날짜 중복 → 종가 · 출처 →
         창 안 연결(POC5-06 link_break) 순서로 검사 · 통과하면 D 종가 포함 단순평균 · 더 오래된 행으로
         채우지 않음 · 창 첫 행 이전 연결은 보지 않음
표시     숫자 = intl_fixed(v, 2)(화면 toLocaleString) · 위치 = 세 표시값을 큰 순으로(같으면 '=' ·
         이름 순서 종가 · MA20 · MA60) · 세 값이 모두 있을 때만
```

같은 D 의 기존 가격 근거 대조(판정 §3-1 · 새 조회 없음 · 이미 읽은 값만):
- 보유 — 보유 근거 응답의 `price_dates`(5 · 20저장일 시작일) · `short_term_momentum`(5 · 10 · 20저장일
  변화율). 같은 읽기의 저장 종가에서 나온 값이라, 새 60행에서 같은 규칙(`close IS NOT NULL AND close > 0`
  행 · `_window_return_pct`)으로 다시 구해 같은지 본다(재계산 대조 · 원시 종가 직접 비교 아님 — 검사 사이 행 ·
  변화율이 그대로인 같은 배율 변경은 못 잡을 수 있음 · RESULT 판정 §3).
- 후보 — 미리보기 읽기의 최근 행(날짜 · 종가 · 출처 · 최대 21) 전부 + 목록 응답의 5 · 10 · 20 시작일 ·
  변화율. 수신 시각(fetched_at)은 비교하지 않는다. NAV 시장가 · 평단과도 비교하지 않는다.
- 60행 밖으로 밀린 비교 대상(60행 안에 거른 행이 40개 이상)은 대조하지 않는다(대조 범위는 basis_checked).

실제 DB 열기 · 읽기 오류는 잡지 않는다 — 기존 미리보기 오류 계약(짧은 실패 응답)을 따른다.
"""

from __future__ import annotations

import math
import sqlite3
from datetime import date
from decimal import Context, Decimal
from pathlib import Path
from typing import Any, Literal, Optional

from pydantic import BaseModel

from app.market_data_store import DEFAULT_DB_PATH
from app.preview_number_format import intl_fixed
from app.reentry_review.prices import (
    ALLOWED_SOURCES,
    PriceRow,
    link_break,
    valid_close,
)
from app.short_term_momentum import _window_return_pct

WINDOWS = (20, 60)
READ_ROWS = max(WINDOWS)  # 60
FLOW_WINDOWS = (5, 10, 20)

# 평균은 저장 double 의 정확한 십진 합 ÷ n 을 한 번만 반올림(아주 큰 유한 종가도 합이 넘치지 않음 · 검토 F1).
_MEAN_CTX = Context(prec=1500)

Status = Literal[
    "ok",
    "not_etf",
    "etf_unknown",
    "no_price",
    "reference_unavailable",
    "date_mismatch",
    "list_read_mismatch",
    "d_row_missing",
    "d_close_invalid",
    "basis_mismatch",
]
WindowStatus = Literal[
    "ok",
    "insufficient_history",
    "date_unconfirmed",
    "duplicate_date",
    "invalid_price",
    "basis_unconfirmed",
]

WINDOW_REASON = {
    "date_unconfirmed": "날짜 확인 필요",
    "duplicate_date": "날짜 중복",
    "invalid_price": "가격 확인 필요",
    "basis_unconfirmed": "가격 기준 확인 필요",
}
# 분류 자료가 비었을 때의 사유 — 이동평균 · [대상] · 상태 줄이 같은 뜻으로 쓴다(RESULT 판정 §2 F3).
ETF_UNKNOWN_REASON = "ETF 구분 자료를 확인하지 못했습니다"
WHOLE_REASON = {
    "not_etf": "대상 아님(개별 종목 · 이 관측은 ETF만)",
    "etf_unknown": f"확인 불가 — {ETF_UNKNOWN_REASON}(개별 종목으로 보지 않음)",
    "no_price": "계산하지 않음 — 이 종목의 저장 종가가 없습니다",
    "reference_unavailable": "계산하지 않음 — PC 비교 기준일(KODEX200)을 확인할 수 없습니다",
    "date_mismatch": "계산하지 않음 — 위 기준일 불일치(이 종목 마지막 저장일 ≠ PC 비교 기준일)",
    "list_read_mismatch": "확인 불가 — 목록 응답과 미리보기 읽기의 가격 기준일이 다릅니다",
    "d_row_missing": "확인 불가 — 가격 기준일({d}) 저장 종가를 다시 읽지 못했습니다",
    "d_close_invalid": "확인 불가 — 가격 기준일({d}) 저장 종가 확인 필요",
    "basis_mismatch": (
        "확인 불가 — 같은 기준일({d})의 가격 근거가 앞서 읽은 값과 다릅니다"
        "(읽는 사이 저장 자료가 바뀌었을 수 있음)"
    ),
}
NO_RESULT = "확인 불가 — 계산 결과가 없습니다"
POSITION_UNCONFIRMED = "표시값 기준 위치: 확인 불가"


class MovingAverageWindow(BaseModel):
    status: WindowStatus
    window_size: int  # 20 · 60
    row_count: int  # 이 창에 쓴(쓰려던) 원본 행 수 — 부족이면 확보한 수
    value: Optional[float] = None  # 내부 평균(반올림 안 함)
    shown: Optional[str] = None  # 화면 · 원문 표시값(intl_fixed 2)
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class MovingAverageEvidence(BaseModel):
    status: Status
    d: Optional[str] = None
    close: Optional[float] = None
    close_shown: Optional[str] = None
    ma20: Optional[MovingAverageWindow] = None
    ma60: Optional[MovingAverageWindow] = None
    relation: Optional[str] = None  # 예 'MA20 > MA60 > 종가' · 세 값이 모두 있을 때만
    basis_checked: list[str] = []  # 대조한 기존 가격 근거(판정 §3-1)
    preview_rows_compared: Optional[int] = None  # 후보 — 대조한 미리보기 읽기 행 수


# ─── 순수 판정 ──────────────────────────────────────────────────────────────


def _iso_day(value: Any) -> bool:
    """'YYYY-MM-DD' 그대로 다시 쓸 수 있는 날짜만(실제 파싱 · '20261020' · '2026-10-2' 는 아님)."""
    if not isinstance(value, str):
        return False
    try:
        return date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


def _link_unconfirmed(prev: PriceRow, row: PriceRow) -> bool:
    # 흔들림(pc_price_volatility)과 같은 처리 — 숫자로 못 읽는 change 도 연결 확인 불가.
    try:
        return link_break(prev, row) is not None
    except (TypeError, ValueError):
        return True


def compute_window(rows_asc: list[PriceRow], n: int) -> MovingAverageWindow:
    """D 로 끝나는 원본 행(오름차순)의 끝 n 행 한 창."""
    if len(rows_asc) < n:
        return MovingAverageWindow(
            status="insufficient_history", window_size=n, row_count=len(rows_asc)
        )
    w = rows_asc[-n:]
    status: WindowStatus = "ok"
    if not all(_iso_day(r.date) for r in w):
        status = "date_unconfirmed"
    elif any(w[i - 1].date >= w[i].date for i in range(1, n)):
        status = "duplicate_date"
    elif any(not valid_close(r.close) or r.source not in ALLOWED_SOURCES for r in w):
        status = "invalid_price"
    elif any(_link_unconfirmed(w[i - 1], w[i]) for i in range(1, n)):
        status = "basis_unconfirmed"
    if status != "ok":
        return MovingAverageWindow(status=status, window_size=n, row_count=n)
    total = Decimal(0)
    for r in w:
        total = _MEAN_CTX.add(total, Decimal(float(r.close)))
    value = float(_MEAN_CTX.divide(total, n))
    return MovingAverageWindow(
        status="ok",
        window_size=n,
        row_count=n,
        value=value,
        shown=intl_fixed(value, 2),
        start_date=w[0].date,
        end_date=w[-1].date,
    )


def relation_text(close_shown: str, ma20_shown: str, ma60_shown: str) -> str:
    """세 표시값을 큰 순으로 · 같은 표시값은 '=' · 같은 값 안 이름 순서 종가 · MA20 · MA60."""
    items = [
        ("종가", Decimal(close_shown.replace(",", ""))),
        ("MA20", Decimal(ma20_shown.replace(",", ""))),
        ("MA60", Decimal(ma60_shown.replace(",", ""))),
    ]
    ordered = sorted(items, key=lambda x: -x[1])  # 안정 정렬 → 같은 값은 위 순서 그대로
    out = ordered[0][0]
    for (_, prev), (name, value) in zip(ordered, ordered[1:]):
        out += (" = " if value == prev else " > ") + name
    return out


def _kept(close: Any) -> bool:
    """기존 흐름 읽기(`close IS NOT NULL AND close > 0`)가 남기는 행과 같은 판정.

    SQLite 는 TEXT · BLOB 를 늘 숫자보다 크게 비교한다 → 그 행도 남긴다(검토 F2).
    """
    if close is None:
        return False
    if isinstance(close, (str, bytes)):
        return True
    return close > 0


def _number(close: Any) -> Optional[float]:
    """기존 읽기의 float() 값 · 숫자로 못 읽으면 None(검증자 r1 F1 — 예외로 관측 전체를 멈추지 않는다).

    기존 흐름 읽기는 최근 21행만 float() 한다. 그 밖의 행이거나 읽는 사이 바뀐 행이면 여기서 처음 만난다 —
    대조 범위 안이면 '근거 다름', 밖이면 그 창의 '가격 확인 필요'로만 드러난다.
    """
    try:
        return float(close)
    except (TypeError, ValueError):
        return None


def _same(a: Any, b: Any) -> bool:
    if isinstance(a, float) and isinstance(b, float) and math.isnan(a):
        return math.isnan(b)
    return a == b


def _flow_basis(
    kept: list[tuple[str, Optional[float], Any]],
    complete: bool,
    starts: dict[int, Any],
    returns: dict[int, Any],
) -> tuple[bool, list[str]]:
    """(모순 없음, 대조한 항목). 기대값이 없는 항목은 건너뛴다(그 값이 없던 근거)."""
    checked: list[str] = []
    series = [(d, c) for d, c, _ in kept]
    for n, expected in starts.items():
        if expected is None:
            continue
        got = series[-(n + 1)][0] if len(series) > n else None
        if got is None and not complete:
            continue  # 60행 밖 — 대조 불가
        checked.append(f"start_date_{n}d")
        if got != expected:
            return False, checked
    for n, expected in returns.items():
        if isinstance(expected, bool) or not isinstance(expected, (int, float)):
            continue
        if len(series) > n and None in (series[-(n + 1)][1], series[-1][1]):
            # 앞선 읽기는 그 행을 숫자로 읽었다 → 지금 숫자가 아니면 읽는 사이 바뀐 것.
            checked.append(f"return_{n}d_pct")
            return False, checked
        got = _window_return_pct(series, n) if len(series) > n else None
        if got is None and not complete:
            continue
        checked.append(f"return_{n}d_pct")
        if got is None or not _same(got, float(expected)):
            return False, checked
    return True, checked


def _rows_basis(
    kept: list[tuple[str, Optional[float], Any]],
    complete: bool,
    preview_desc: list[Any],
) -> tuple[bool, int]:
    """후보 — 미리보기 읽기 행(최신순 date · close · volume · source)이 새 읽기와 같은지(수신 시각 제외)."""
    compared = 0
    for i, row in enumerate(preview_desc):
        if i >= len(kept):
            return (not complete), compared
        d, c, src = kept[-(i + 1)]
        compared += 1
        if d != row[0] or c is None or not _same(c, float(row[1])) or src != row[3]:
            return False, compared
    return True, compared


def evaluate(
    rows_asc: list[PriceRow],
    d: str,
    *,
    starts: dict[int, Any],
    returns: dict[int, Any],
    preview_desc: Optional[list[Any]] = None,
) -> MovingAverageEvidence:
    """읽은 원본 행(D 이하 · 오름차순 · 최대 60) → 관측 전체 검사 → 기존 근거 대조 → 창별 평균."""
    if not rows_asc or rows_asc[-1].date != d:
        return MovingAverageEvidence(status="d_row_missing", d=d)
    last = rows_asc[-1]
    if not valid_close(last.close) or last.source not in ALLOWED_SOURCES:
        return MovingAverageEvidence(status="d_close_invalid", d=d)
    complete = len(rows_asc) < READ_ROWS  # D 이하 행을 모두 읽었음
    kept = [(r.date, _number(r.close), r.source) for r in rows_asc if _kept(r.close)]
    ok, checked = _flow_basis(kept, complete, starts, returns)
    compared: Optional[int] = None
    if ok and preview_desc is not None:
        ok, compared = _rows_basis(kept, complete, preview_desc)
        checked.append("preview_rows")
    if not ok:
        return MovingAverageEvidence(
            status="basis_mismatch",
            d=d,
            basis_checked=checked,
            preview_rows_compared=compared,
        )
    ma20, ma60 = compute_window(rows_asc, 20), compute_window(rows_asc, 60)
    close = float(last.close)
    close_shown = intl_fixed(close, 2)
    relation = (
        relation_text(close_shown, ma20.shown, ma60.shown)
        if ma20.shown is not None and ma60.shown is not None
        else None
    )
    return MovingAverageEvidence(
        status="ok",
        d=d,
        close=close,
        close_shown=close_shown,
        ma20=ma20,
        ma60=ma60,
        relation=relation,
        basis_checked=checked,
        preview_rows_compared=compared,
    )


# ─── 읽기 · 진입 ────────────────────────────────────────────────────────────


def _read_rows(ticker: str, d: str, db_path: Path) -> list[PriceRow]:
    """D 이하 원본 최근 60행(오름차순) — 비정상 행을 거르지 않는다 · 오류는 호출자 계약대로 올린다."""
    con = sqlite3.connect(
        f"{Path(db_path).resolve().as_uri()}?mode=ro", uri=True, timeout=5.0
    )
    try:
        cur = con.execute(
            "SELECT date, close, source, fetched_at, change FROM etf_daily_price "
            "WHERE ticker = ? AND date <= ? ORDER BY date DESC LIMIT ?",
            (ticker, d, READ_ROWS),
        )
        return [PriceRow(*r) for r in reversed(cur.fetchall())]
    finally:
        con.close()


def etf_class(ticker: str, etf_tickers: set[str]) -> str:
    """보유 종목 구분 — 분류 자료가 비었으면 확인 불가(개별 종목으로 단정하지 않음 · 판정 §3-3)."""
    if not etf_tickers:
        return "unknown"
    return "etf" if ticker in etf_tickers else "stock"


def for_holding(
    ticker: str,
    item: dict[str, Any],
    *,
    reference_date: Optional[str],
    kind: str,
    db_path: Path = DEFAULT_DB_PATH,
) -> MovingAverageEvidence:
    """보유 종목 — 보유 근거 응답(PC 기준일 정정 사본)의 그 종목 · 판정 순서는 흔들림과 같다."""
    if kind == "stock":
        return MovingAverageEvidence(status="not_etf")
    if kind != "etf":
        return MovingAverageEvidence(status="etf_unknown")
    pd_ = item.get("price_dates") or {}
    end = pd_.get("end_date")
    if end is None:
        return MovingAverageEvidence(status="no_price")
    if reference_date is None:
        return MovingAverageEvidence(status="reference_unavailable", d=end)
    if end != reference_date:
        return MovingAverageEvidence(status="date_mismatch", d=end)
    stm = item.get("short_term_momentum") or {}
    return evaluate(
        _read_rows(ticker, end, db_path),
        end,
        starts={5: pd_.get("start_date_5d"), 20: pd_.get("start_date_20d")},
        returns={n: stm.get(f"return_{n}d_pct") for n in FLOW_WINDOWS},
    )


def for_candidate(
    ticker: str,
    stm: Optional[dict[str, Any]],
    preview_desc: list[Any],
    *,
    db_path: Path = DEFAULT_DB_PATH,
) -> MovingAverageEvidence:
    """후보 — 자기 D(미리보기 읽기 끝 날짜) · 목록 응답 날짜와 다르면 맞추지 않는다(판정 §3-1)."""
    stm = stm or {}
    end = preview_desc[0][0] if preview_desc else None
    if end is None:
        return MovingAverageEvidence(status="no_price")
    listed = stm.get("end_date")
    if listed is not None and listed != end:
        return MovingAverageEvidence(status="list_read_mismatch", d=end)
    sd = stm.get("start_dates") or {}
    return evaluate(
        _read_rows(ticker, end, db_path),
        end,
        starts={5: sd.get("five_d"), 10: sd.get("ten_d"), 20: sd.get("twenty_d")},
        returns={n: stm.get(f"return_{n}d_pct") for n in FLOW_WINDOWS},
        preview_desc=preview_desc,
    )


# ─── 원문 줄 ────────────────────────────────────────────────────────────────


def _cell(w: Optional[dict[str, Any]], label: str) -> str:
    if not w:
        return f"{label} 확인 불가"
    if w.get("status") == "ok":
        return f"{label} {w['shown']}원"
    if w.get("status") == "insufficient_history":
        return f"{label} 계산 불가(저장 종가 {w['row_count']}/{w['window_size']}개)"
    return f"{label} 계산 불가({WINDOW_REASON.get(w.get('status') or '', '확인 불가')})"


def _span(w: Optional[dict[str, Any]], label: str) -> str:
    if w and w.get("status") == "ok":
        return (
            f"{label} = 저장 종가 {w['row_count']}개"
            f"({w['start_date']} → {w['end_date']})"
        )
    return f"{label} = 계산 안 함"


def moving_average_lines(ma: Optional[dict[str, Any]]) -> list[str]:
    """가격 흐름 묶음에 넣을 줄(사용자 확인 목업 · 판정 Q1 · Q2 (a))."""
    if not ma:
        return [f"종목 이동평균: {NO_RESULT}", POSITION_UNCONFIRMED]
    status = ma.get("status")
    if status != "ok":
        reason = WHOLE_REASON.get(status or "", NO_RESULT).format(
            d=ma.get("d") or "확인 불가"
        )
        return [f"종목 이동평균: {reason}", POSITION_UNCONFIRMED]
    m20, m60 = ma.get("ma20"), ma.get("ma60")
    head = f"종목 이동평균: {_cell(m20, 'MA20')} · {_cell(m60, 'MA60')}"
    if ma.get("relation"):
        pos = f"표시값 기준 위치: {ma['relation']} (종가 {ma['close_shown']}원)"
    else:
        missing = " · ".join(
            label
            for label, w in (("MA20", m20), ("MA60", m60))
            if not w or w.get("status") != "ok"
        )
        pos = (
            f"표시값 기준 위치: 확인 불가({missing} 없음) · 종가 {ma['close_shown']}원"
        )
    span = f"이동평균 계산 구간: {_span(m20, 'MA20')} · {_span(m60, 'MA60')}"
    return [head, pos, span]
