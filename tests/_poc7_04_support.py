"""POC7-04 시험 공용 — tmp 시세 DB · tmp 판단 근거 DB · 합성 기록 · 연구 서버 도우미(라이브 DB 안 엶)."""

from __future__ import annotations

import http.client
import json
import re
import socket
import sqlite3
from datetime import date, timedelta, timezone
from pathlib import Path
from typing import Any, Optional


from app.decision_evidence_store import AI_SESSION_RECORDS_DDL
from app.market_data_store import init_db
from app.weekly_decision import history as H
from app.weekly_decision import lines as L
from app.weekly_decision import server as SV

REPO = Path(__file__).resolve().parents[1]


KST = timezone(timedelta(hours=9))


FILTERS = {
    "exclude_inverse": True,
    "exclude_leveraged": True,
    "exclude_synthetic": True,
    "exclude_futures": True,
}


END = "2026-11-23"  # 월요일 — 11/23 주는 거래 중


ROWS = ["2026-10-30", "2026-11-06", "2026-11-13", "2026-11-20"]


def trading(d: str) -> bool:
    return date.fromisoformat(d).weekday() < 5


def _bdays(end: str, n: int) -> list[str]:
    d, out = date.fromisoformat(end), []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d -= timedelta(days=1)
    return list(reversed(out))


DAYS = _bdays(END, 90)


def _line(n: int, a: float, b: float) -> list[float]:
    return [round(a + (b - a) * i / (n - 1), 4) for i in range(n)]


def _put(
    db: Path, tk: str, closes: list[float], days: Optional[list[str]] = None
) -> None:
    if days is None:
        k = len(closes)
        days = DAYS[-k:]
    rows = [
        (
            tk,
            d,
            c,
            c,
            c,
            c,
            1000,
            0.0,
            "test",
            f"{d}T07:10:00+00:00",
        )  # 16:10 KST 마감 뒤
        for d, c in zip(days, closes)
    ]
    with sqlite3.connect(db) as con:
        con.executemany(
            "INSERT INTO etf_daily_price(ticker, date, open, high, low, close, volume, change,"
            " source, fetched_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            rows,
        )


NAMES = {
    "069500": "KODEX 200",
    "AAA001": "가 인도A",
    "AAA002": "나 인도B",
    "AAA003": "다 인도합성(합성)",
    "AAA004": "아 인도(H)",
    "DOM001": "라 국내A",
    "DOM002": "마 국내B",
    "LATE01": "바 늦은상장",
    "FLAT01": "사 평탄",
}


def _off(
    name: str,
    idx: str,
    market: str,
    *,
    rep: str = "실물(패시브)",
    fee: str = "0.190000",
):
    return {
        "기초지수명": idx,
        "추적배수": "일반",
        "복제방법": rep,
        "기초시장분류": market,
        "총보수": fee,
        "한글종목약명": name,
    }


OFFICIAL = {
    "AAA001": _off("가 인도A", "Nifty 50 Index", "해외"),
    "AAA002": _off("나 인도B", "Nifty 50 Index", "해외", fee="0.250000"),
    "AAA003": _off("다 인도합성(합성)", "Nifty 50 Index", "해외", rep="합성(패시브)"),
    "AAA004": _off("아 인도(H)", "Nifty 50 Index", "해외"),
    "DOM001": _off("라 국내A", "코스피 200", "국내"),
    "DOM002": _off("마 국내B", "코스피 200", "국내"),
    "DOM003": _off("자 국내C", "코스피 200", "국내"),  # 목록(시세 DB)에 없음
}


def make_market(tmp_path: Path) -> Path:
    """tmp 시세 DB(END 2026-11-23 · 후보 AAA001~004 · DOM001/002 · LATE01 · FLAT01 · 069500)."""
    db = tmp_path / "market_data.sqlite"
    init_db(db)
    with sqlite3.connect(db) as con:
        con.executemany(
            "INSERT INTO etf_master(ticker, name, category, price, volume, market_cap, source,"
            " last_seen_at) VALUES (?,?,NULL,NULL,NULL,NULL,'test','2026-11-10T00:00:00Z')",
            list(NAMES.items()),
        )
    _put(db, "069500", _line(90, 100.0, 95.0))
    _put(db, "AAA001", _line(90, 100.0, 130.0))
    _put(db, "AAA002", _line(90, 100.0, 131.0))
    _put(db, "AAA003", _line(90, 100.0, 140.0))
    _put(db, "AAA004", _line(90, 100.0, 120.0))
    _put(db, "DOM001", _line(90, 100.0, 110.0))
    _put(db, "DOM002", _line(90, 100.0, 90.0))
    _put(db, "LATE01", _line(15, 100.0, 105.0))
    _put(db, "FLAT01", [100.0] * 90)
    return db


def _ctx(db: Path, end: Optional[str] = None) -> H.Context:
    return H.load_context(
        db, end, filters=FILTERS, official=OFFICIAL, dictionary=None, is_trading=trading
    )


def _item(rank: int, tk: str, v: float, s: str, e: str) -> dict[str, Any]:
    return {
        "rank": rank,
        "ticker": tk,
        "name": NAMES.get(tk, tk),
        "one_month_return_pct": v,
        "tags": [],
        "same_period_kodex200": {
            "one_month": {"status": "ok", "start_date": s, "end_date": e}
        },
    }


def _true_item(ctx: H.Context, d: str, filters: Optional[dict] = None) -> dict:
    """그날 그 조건으로 다시 계산한 값 그대로의 저장 후보(맞춰 보기 = 같음 · V2 RESULT 판정 §2)."""
    seen = H.seen_at(ctx.restore(d, filters), "AAA001")
    one = seen["one_month"]
    return _item(
        seen["rank"], "AAA001", round(one["value"], 4), one["start"], one["end"]
    )


def _cite_line(item: dict[str, Any], asof: str) -> str:
    k1 = item["same_period_kodex200"]["one_month"]
    v = item["one_month_return_pct"]
    one = {"value": v, "start": k1["start_date"], "end": k1["end_date"]}
    return L.session_plain(asof, item["rank"], one)


def _decision(tmp_path: Path, rows: list[dict[str, Any]]) -> Path:
    db = tmp_path / "decision_evidence.sqlite"
    with sqlite3.connect(db) as con:
        con.executescript(AI_SESSION_RECORDS_DDL)
        for i, r in enumerate(rows):
            con.execute(
                "INSERT INTO ai_session_records(id, created_at, updated_at, asof, source_screen,"
                " filters_json, candidate_snapshot_json, question_text, user_memo, user_verdict,"
                " next_checks_json, gpt_answer_text) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    r.get("id", f"rec{i}"),
                    r.get("created", f"{r['asof']}T23:00:00+0900"),
                    r.get("created", f"{r['asof']}T23:00:00+0900"),
                    r["asof"],
                    r.get("source", "market_discovery"),
                    json.dumps(r.get("filters", FILTERS)),
                    (
                        json.dumps(r["items"])
                        if not isinstance(r["items"], str)
                        else r["items"]
                    ),
                    "q",
                    r.get("memo", ""),
                    r.get("verdict", "hold"),
                    json.dumps(r.get("nexts", []), ensure_ascii=False),
                    r.get("gpt", ""),
                ),
            )
    return db


def _sessions(tmp_path: Path, rows: list[dict[str, Any]]) -> dict[str, Any]:
    return H.read_sessions(_decision(tmp_path, rows))


NONE_SESSIONS = {"state": "ok", "records": [], "broken": 0}


def _rv(
    *, official=True, price="after_close", up=4, overseas=True, opposite=False, v=10.0
):
    peer = (
        {
            "state": "ok",
            "label": "Nifty 50",
            "overseas": overseas,
            "same": [
                {
                    "ticker": "P1",
                    "name": "피어",
                    "fee": "0.19",
                    "rank": 2,
                    "one_month": {
                        "value": -v if opposite else v,
                        "start": "2026-10-26",
                        "end": END,
                    },
                }
            ],
        }
        if official
        else {"state": "no_official"}
    )
    return {
        "peer": peer,
        "price_state": price,
        "up": up,
        "week_gap": None if up is not None else "no_price",
        "one_month": {"value": v, "start": "2026-10-26", "end": END},
    }


class FakeReader:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, ticker: str, cond: dict[str, Any]) -> dict[str, Any]:
        self.calls += 1
        return {
            "constituents": {
                "asof": "2026-11-16",
                "rows": [
                    {"name": "보유주식ABC", "weight_pct": 40.0},
                    {"name": "둘째", "weight_pct": 30.5},
                    {"name": "셋째", "weight_pct": "x"},
                ],
            },
            "exposure": {
                "status": "ok",
                "stocks": [
                    {
                        "name": "보유주식ABC",
                        "exposure": {"terms": [{"ticker": "H1"}], "direct": []},
                    },
                    {"name": "둘째", "exposure": {"terms": [], "direct": []}},
                ],
            },
            "exposure_error": False,
        }


def _records_for_copy() -> list[dict[str, Any]]:
    return [
        {
            "asof": "2026-11-16",
            "memo": "비밀메모XYZ",
            "nexts": ["다음확인QQQ"],
            "gpt": "답",
            "items": [_item(2, "AAA001", 9.5, "2026-10-19", "2026-11-16")],
        },
        {
            "asof": "2026-11-17",
            "source": "holdings_compare_preview",
            "items": [{"rank": None, "ticker": "AAA001", "same_period_kodex200": None}],
        },
        {
            "asof": "2026-11-03",
            "items": [_item(1, "DOM001", 3.0, "2026-10-03", "2026-11-03")],
        },
    ]


def _snap(ticker: str = "AAA001") -> dict[str, Any]:
    return {
        "ticker": ticker,
        "end": END,
        "copy": "c",
        "screen": {"sub": "s", "one": "o", "weeks": "w", "ask": "a"},
        "review": {"rank": 1},
    }


def _app(market: Path, tmp_path: Path, rows: Optional[list] = None) -> SV.App:
    root = tmp_path / "root"
    root.mkdir(exist_ok=True)
    return SV.App(
        db=market,
        decision_db=_decision(
            tmp_path, rows if rows is not None else _records_for_copy()
        ),
        root=root,
        end=None,
        filters=FILTERS,
        sources=lambda: (OFFICIAL, None),
        reader=FakeReader(),
        is_trading=trading,
    )


def _bid(html: str) -> str:
    return re.search(r'var BUILD = "([^"]+)"', html).group(1)


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _req(port: int, method: str, path: str, body: Optional[bytes] = None, headers=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=30)
    h = {"Host": f"127.0.0.1:{port}", **(headers or {})}
    conn.request(method, path, body=body, headers=h)
    r = conn.getresponse()
    data = r.read().decode("utf-8")
    conn.close()
    return r.status, data


def _bump(market: Path, ticker: str = "AAA001") -> None:
    """끝일 종가를 1 올림 — 시세 지문이 바뀌어 다음 화면의 근거 · 복사문이 달라진다."""
    with sqlite3.connect(market) as con:
        con.execute(
            "UPDATE etf_daily_price SET close = close + 1 WHERE ticker=? AND date=?",
            (ticker, END),
        )
