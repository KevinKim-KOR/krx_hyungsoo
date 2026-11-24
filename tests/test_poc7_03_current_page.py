"""POC7-03 이번 주 목록 · 주별 끝일 · 한 장 · 복사문 · AC1 대조 — tmp 시세 DB 만(라이브 DB 안 엶)."""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Optional

import pytest

from app.candidate_compare import crosscheck as CC
from app.candidate_compare import current as CU
from app.candidate_compare import page as PG
from app.candidate_compare import texts as TX
from app.market_data_store import init_db
from app.market_evidence_text import LATEST_CHECK
from app.pc_etf_compare_summary import build_summary

FILTERS = {
    "exclude_inverse": True,
    "exclude_leveraged": True,
    "exclude_synthetic": True,
    "exclude_futures": True,
}
END = "2026-11-20"  # 금요일
AFTER = "2026-11-20T07:10:00+00:00"  # 16:10 KST — 마감 뒤 저장
INTRA = "2026-11-20T03:00:00+00:00"  # 12:00 KST — 장중 저장


def _bdays(end: str, n: int) -> list[str]:
    d, out = date.fromisoformat(end), []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d -= timedelta(days=1)
    return list(reversed(out))


DAYS = _bdays(END, 80)


def _put(
    db: Path,
    tk: str,
    closes: list[float],
    days: Optional[list[str]] = None,
    last_fetched: str = AFTER,
) -> None:
    n = len(closes)
    days = days if days is not None else DAYS[-n:]
    rows = []
    for i, (d, c) in enumerate(zip(days, closes)):
        # 실제 자료처럼 그날 장 마감 뒤(16:10 KST) 저장 · 끝 행만 지정 시각
        fa = last_fetched if i == len(closes) - 1 else f"{d}T07:10:00+00:00"
        rows.append((tk, d, c, c, c, c, 1000, 0.0, "FinanceDataReader", fa))
    with sqlite3.connect(db) as con:
        con.executemany(
            "INSERT INTO etf_daily_price(ticker, date, open, high, low, close, volume, change,"
            " source, fetched_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            rows,
        )


def _master(db: Path, items: dict[str, str]) -> None:
    with sqlite3.connect(db) as con:
        con.executemany(
            "INSERT INTO etf_master(ticker, name, category, price, volume, market_cap, source,"
            " last_seen_at) VALUES (?,?,NULL,NULL,NULL,NULL,'test','2026-11-10T00:00:00Z')",
            list(items.items()),
        )


def _line(n: int, a: float, b: float) -> list[float]:
    return [round(a + (b - a) * i / (n - 1), 4) for i in range(n)]


@pytest.fixture
def market(tmp_path: Path) -> Path:
    db = tmp_path / "market_data.sqlite"
    init_db(db)
    _master(
        db,
        {
            "069500": "KODEX 200",
            "AAA001": "가 꾸준",
            "AAA002": "나 급등후조정",
            "AAA003": "다 완만",
            "AAA004": "라 인버스",
            "AAA005": "마 늦은상장",
            "AAA006": "바 가격없음",
            "AAA007": "사 하락",
            "AAA008": "아 주마감없음",
            "AAA009": "자 한주만오름",
        },
    )
    _put(db, "069500", _line(80, 100.0, 95.0))
    _put(db, "AAA001", _line(80, 100.0, 120.0))  # 매주 오름
    zig = _line(60, 100.0, 100.0) + [
        130.0,
        128,
        126,
        124,
        122,
        120,
        118,
        116,
        114,
        112,
        125,
        123,
        121,
        119,
        117,
        135,
        133,
        131,
        129,
        127,
    ]
    _put(db, "AAA002", zig)  # 1개월 큰 상승 · 주별로는 내림이 많음
    _put(db, "AAA003", _line(80, 100.0, 104.0))
    _put(db, "AAA004", _line(80, 100.0, 140.0))  # 인버스 → 제외
    _put(db, "AAA005", _line(10, 100.0, 110.0))  # 늦은 상장 → 시작일 다름
    _put(db, "AAA007", _line(80, 100.0, 90.0))
    late = [
        98,
        96,
        94,
        92,
        90,
        89,
        88,
        87,
        86,
        85,
        84,
        83,
        82,
        81,
        80,
        90,
        100,
        110,
        120,
        125,
    ]
    _put(
        db, "AAA009", _line(60, 100.0, 100.0) + late
    )  # 1개월 +25% · 네 주 중 한 주만 오름
    days8 = [d for d in DAYS if d != "2026-11-13"]  # 주 마감 하나 없음
    _put(db, "AAA008", _line(79, 100.0, 103.0), days=days8)
    return db


def _ops(db: Path) -> dict[str, Any]:
    return build_summary(
        db_path=db,
        basis="one_month",
        filters=FILTERS,
        official={},
        official_meta={},
        dictionary=None,
        dictionary_meta={},
        held_tickers=[],
        holdings_status="ok",
    )


def _weekday(d: str) -> bool:
    """시험용 거래일(연도 파일 없이 평일 + 5/1 · 12/31 휴장 — 프로젝트 기본 계약과 같은 함수)."""
    from app.market_briefing.calendar import is_fallback_trading_day

    return is_fallback_trading_day(date.fromisoformat(d))


def _research(db: Path, reader=None, end: Optional[str] = None) -> dict[str, Any]:
    return CU.build(
        CU.read_market(db, end),
        filters=FILTERS,
        official={},
        dictionary=None,
        reader=reader,
        is_trading=_weekday,
    )


def test_research_list_matches_operational_ranking(market: Path) -> None:
    ops, mine = _ops(market), _research(market)
    assert mine["status"] == "ok" and mine["end"] == ops["end_date"] == END
    assert [mine["windows"]["one_month"][0], mine["windows"]["one_month"][1]] == [
        ops["period"]["start"],
        ops["period"]["end"],
    ]
    for k in CC.COUNT_KEYS:
        assert mine["counts"][k] == ops["counts"][k], k
    assert [[r["rank"], r["ticker"]] for r in ops["top"]] == CC.research_top(mine)


def test_weekly_dates_rule() -> None:
    axis = _bdays("2026-11-23", 40)
    ok = {d: "after_close" for d in axis}
    fri = CU.weekly_dates(axis, "2026-11-20", ok, _weekday)
    assert fri["w0"] == "2026-11-20" and not fri["mid_week"] and fri["finished"]
    assert fri["dates"] == [
        "2026-10-23",
        "2026-10-30",
        "2026-11-06",
        "2026-11-13",
        "2026-11-20",
    ]
    mon = CU.weekly_dates(
        axis, "2026-11-23", ok, _weekday
    )  # 월요일 끝일 → 지난주 금요일
    assert mon["w0"] == "2026-11-20" and mon["mid_week"] is True and not mon["finished"]
    intra = CU.weekly_dates(
        axis, "2026-11-20", {**ok, "2026-11-20": "intraday"}, _weekday
    )
    assert (
        intra["w0"] == "2026-11-13" and intra["mid_week"] is True
    )  # 금요일 장중 → 한 주 앞
    # 검증자 r1 F3 ① — 월요일 자료에서 지난 금요일 KODEX 200 이 장중 저장이면 그 주도 쓰지 않음
    prev = CU.weekly_dates(
        axis, "2026-11-23", {**ok, "2026-11-20": "intraday"}, _weekday
    )
    assert (
        prev["w0"] == "2026-11-13"
        and prev["skipped"][-1]["why"] == "bench_not_after_close"
    )
    unk = CU.weekly_dates(axis, "2026-11-20", {**ok, "2026-11-20": "unknown"}, _weekday)
    assert unk["w0"] == "2026-11-13"  # 저장 시각 불명도 마감값 확보 아님


def test_weekly_dates_fixed_holiday_and_schedule_gap() -> None:
    # 검증자 r1 F3 ③ — 5/1(금) 고정 휴장 주: 4/30(목)이 그 주 일정상 마지막 거래일
    axis = [d for d in _bdays("2026-04-30", 40) if d != "2026-05-01"]
    ok = {d: "after_close" for d in axis}
    got = CU.weekly_dates(axis, "2026-04-30", ok, _weekday)
    assert got["w0"] == "2026-04-30" and got["finished"] and not got["mid_week"]
    # 연도 파일이 금요일을 휴장으로 알면(예: 12/25) 목요일이 그 주 마지막 거래일
    axis2 = [d for d in _bdays("2026-12-24", 40) if d != "2026-12-25"]
    ok2 = {d: "after_close" for d in axis2}
    cal = {"2026-12-25"}
    got2 = CU.weekly_dates(
        axis2, "2026-12-24", ok2, lambda d: _weekday(d) and d not in cal
    )
    assert got2["w0"] == "2026-12-24" and got2["finished"]
    # 일정상 거래일인 지난주 금요일 행이 축에 없으면 그 주는 마감값 미확보 → 한 주 앞
    axis3 = [d for d in _bdays("2026-11-23", 40) if d != "2026-11-20"]
    ok3 = {d: "after_close" for d in axis3}
    got3 = CU.weekly_dates(axis3, "2026-11-23", ok3, _weekday)
    assert got3["w0"] == "2026-11-13" and got3["skipped"][-1]["why"] == "schedule_gap"


def test_picks_and_missing_week_close(market: Path) -> None:
    mine = _research(market)
    by = {it["ticker"]: it for it in mine["items"]}
    assert (
        by["AAA008"]["up"] is None and by["AAA008"]["common_rank"] is None
    )  # 주 마감 없음 = 미확인
    assert by["AAA008"]["rank"] is not None  # 원래 1개월 순위는 보임
    assert mine["up_distribution"]["none"] == 1
    assert by["AAA001"]["up"] == 4
    assert mine["picks_a"] == ["AAA002", "AAA009", "AAA001"]  # 1개월 순서
    assert by["AAA009"]["up"] == 1 and by["AAA002"]["up"] == 3
    assert mine["picks_b"] == ["AAA001", "AAA003", "AAA002"]  # 오른 주 → 1개월 순서
    assert "AAA004" not in by  # 인버스 제외


def test_friday_intraday_close_is_not_a_week_close(tmp_path: Path) -> None:
    db = tmp_path / "m.sqlite"
    init_db(db)
    _master(db, {"069500": "KODEX 200", "AAA001": "가 꾸준", "AAA002": "나"})
    _put(db, "069500", _line(80, 100.0, 95.0))
    _put(
        db, "AAA001", _line(80, 100.0, 120.0), last_fetched=INTRA
    )  # 이 후보만 끝일 장중
    _put(db, "AAA002", _line(80, 100.0, 110.0))
    mine = _research(db)
    by = {it["ticker"]: it for it in mine["items"]}
    assert mine["weekly"]["w0"] == END
    assert by["AAA001"]["state"] == "intraday" and by["AAA001"]["up"] is None
    assert by["AAA001"]["week_gap"] == "intraday_close"
    assert by["AAA002"]["week_gap"] is None
    assert by["AAA002"]["up"] == 4


def test_previous_week_close_must_be_after_close(tmp_path: Path) -> None:
    """검증자 r1 F3 ② — 지난 주 마감값이 장중 · 저장 시각 불명이면 그 후보 오른 주는 미확인."""
    db = tmp_path / "m.sqlite"
    init_db(db)
    _master(db, {"069500": "KODEX 200", "AAA001": "가", "AAA002": "나", "AAA003": "다"})
    for tk, b in (
        ("069500", 95.0),
        ("AAA001", 120.0),
        ("AAA002", 110.0),
        ("AAA003", 105.0),
    ):
        _put(db, tk, _line(80, 100.0, b))
    with sqlite3.connect(db) as con:
        con.execute(
            "UPDATE etf_daily_price SET fetched_at = ? WHERE ticker = 'AAA001' AND date = ?",
            (
                "2026-11-13T03:00:00+00:00",
                "2026-11-13",
            ),  # 지난주 금요일 12:00 KST = 장중
        )
        con.execute(
            "UPDATE etf_daily_price SET fetched_at = ? WHERE ticker = 'AAA002' AND date = ?",
            (
                "2026-01-01T07:10:00+00:00",
                "2026-10-30",
            ),  # 가격 날짜보다 앞선 저장 시각 = 불명
        )
    mine = _research(db)
    by = {it["ticker"]: it for it in mine["items"]}
    assert by["AAA001"]["up"] is None and by["AAA001"]["week_gap"] == "intraday_close"
    assert by["AAA001"]["common_rank"] is None
    assert by["AAA002"]["up"] is None and by["AAA002"]["week_gap"] == "unknown_close"
    assert by["AAA003"]["up"] == 4 and by["AAA003"]["common_rank"] is not None
    page = PG.render(mine, generated_at="2026-11-21T09:00:00+09:00")
    assert "주 마감값이 장중 저장 — 오른 주 미확인" in page
    assert "주 마감값의 저장 시각 불명 — 오른 주 미확인" in page


def test_unknown_end_state_is_not_called_intraday(tmp_path: Path) -> None:
    """검증자 r1 F3 ④ — 끝일 저장 시각 불명을 복사문 · 화면 · 다음 확인에서 '장중'으로 쓰지 않음."""
    db = tmp_path / "m.sqlite"
    init_db(db)
    _master(db, {"069500": "KODEX 200", "AAA001": "가", "AAA002": "나", "AAA003": "다"})
    for tk, b in (
        ("069500", 95.0),
        ("AAA001", 120.0),
        ("AAA002", 110.0),
        ("AAA003", 105.0),
    ):
        _put(db, tk, _line(80, 100.0, b))
    with sqlite3.connect(db) as con:
        con.execute(
            "UPDATE etf_daily_price SET fetched_at = ? WHERE ticker = 'AAA003' AND date = ?",
            ("2026-01-01T07:10:00+00:00", END),  # 저장 시각 불명
        )
    mine = _research(db)
    by = {it["ticker"]: it for it in mine["items"]}
    assert by["AAA003"]["state"] == "unknown"
    line = TX._copy_item(by["AAA003"])
    assert "저장 시각 확인 불가" in line and "장중" not in line
    assert "저장 시각" in TX.next_check(by["AAA003"]) and "장중" not in TX.next_check(
        by["AAA003"]
    )
    assert not any("장중" in x for x in TX.scope_lines(by["AAA003"]))
    page = PG.render(mine, generated_at="2026-11-21T09:00:00+09:00")
    assert "끝일 가격 저장 시각 확인 불가" in page


def _market_like(db: Path) -> dict:
    return CU.read_market(db)


def test_fingerprint_sees_same_date_restore(market: Path) -> None:
    before = CU.fingerprint(_market_like(market))
    with sqlite3.connect(market) as con:
        con.execute(
            "UPDATE etf_daily_price SET fetched_at = ? WHERE ticker = 'AAA001' AND date = ?",
            ("2026-11-20T08:00:00+00:00", END),  # 끝일 그대로 · 같은 날짜 값 다시 저장
        )
    assert CU.fingerprint(_market_like(market)) != before


def _reader(ticker: str, cond: dict) -> dict:
    """구성 · 겹침 읽기 대역 — 보유 비중 숫자가 들어간 글(복사문에 나오면 안 됨)."""
    return {
        "constituents": {
            "state": "top_rows",
            "state_label": "상위 10행만 확인",
            "asof": "2026-11-16",
            "stored_rows": 10,
            "line": "구성 기준일 11/16 · 저장 10행 · 상위 10행만 확인",
        },
        "exposure": {
            "status": "ok",
            "candidate": {
                "ticker": ticker,
                "state": "top_rows",
                "asof": "2026-11-16",
                "stored_rows": 10,
            },
            "scope": None,
            "stocks": [],
        },
        "exposure_error": False,
    }


def test_copy_text_has_no_personal_holdings_and_starts_with_latest_check(
    market: Path, monkeypatch
) -> None:
    from app import weekly_review as WR

    def fake_overlap(sel, body, error=False):
        return {
            "state": "ok",
            "warn_lines": [
                "보유 평가액의 12.34%(보유 ETF 7개)에 해당하는 ETF 는 미확인"
            ],
            "lines": ["주요 주식별 보유 노출 범위 0.00% ~ 0.00%"],
            "date_line": "기준일 11/16",
            "numbers": {"full_confirmed": "87.66"},
        }

    monkeypatch.setattr(WR, "overlap_of", fake_overlap)
    mine = _research(market, reader=_reader)
    text = TX.copy_text(mine)
    assert text.startswith(LATEST_CHECK)
    for bad in ("12.34", "87.66", "보유 ETF 7개", "보유 평가액"):
        assert bad not in text
    assert "겹침 없음'이 아님" in text
    page = PG.render(mine, generated_at="2026-11-21T09:00:00+09:00")
    assert "12.34" in page  # 로컬 상세에는 보인다
    blob = page.split('id="cc-data">')[1].split("</script>")[0]
    data = json.loads(blob)  # JSON 의 '<\\/' 는 JSON.parse 가 '</' 로 읽는 정상 꼴
    assert data["selected"] == mine["picks_b"][0]
    assert all("12.34" not in data["head"] + t for t in data["tails"].values())
    assert all(f'id="d-{it["ticker"]}"' in page for it in mine["items"])
    assert data["head"] + data["tails"][data["selected"]] == TX.copy_text(
        mine, data["selected"]
    )


def test_copy_scope_line_follows_selected_candidate(market: Path, monkeypatch) -> None:
    """검토 M1 — 겹침 확인 범위 줄은 고른 후보의 것이어야 한다(1번 후보 것을 쓰면 안 됨)."""
    from app import weekly_review as WR

    def fake_overlap(sel, body, error=False):
        full = (
            "100.00" if sel["ticker"] == "AAA001" else "40.00"
        )  # 1번 후보만 보유 쪽 모두 확인
        return {
            "state": "ok",
            "warn_lines": [],
            "lines": [],
            "date_line": None,
            "numbers": {"full_confirmed": full},
        }

    monkeypatch.setattr(WR, "overlap_of", fake_overlap)
    mine = _research(market, reader=_reader)
    assert mine["picks_b"][0] == "AAA001"
    first = TX.copy_text(mine)
    assert (
        "[내 보유와 겹침 확인 범위 — 가 꾸준] 확보된 구성 범위에서 확인 · 내 보유 쪽 구성은 모두 확인됨"
        in first
    )
    other = TX.copy_text(mine, "AAA007")
    assert (
        "[고른 후보]" in other
        and "— 사 하락]" in other
        and "'겹침 없음'이 아님" in other
    )
    assert "모두 확인됨" not in other
    # 시세가 없어 분모 밖인 보유가 있으면 '모두 확인'이라고 쓰지 않는다(검토 m10)
    by = {it["ticker"]: it for it in mine["items"]}
    by["AAA001"]["detail"]["no_weight"] = 2
    assert "모두 확인됨" not in TX.copy_text(mine)
    page = PG.render(mine, generated_at="2026-11-21T09:00:00+09:00")
    blob = json.loads(page.split('id="cc-data">')[1].split("</script>")[0])
    assert blob["head"] + blob["tails"]["AAA007"] == TX.copy_text(mine, "AAA007")


def test_texts_lead_and_reasons(market: Path) -> None:
    mine = _research(market)
    by = {it["ticker"]: it for it in mine["items"]}
    lead = TX.lead(by["AAA007"], mine["kodex"])
    assert (
        "내렸습니다" in lead and "같은 기간 국내 시장 비교 기준인 KODEX 200은" in lead
    )
    why = TX.reasons(mine)
    assert why["picks"][0]["text"].startswith("지난 4주에 매주 올랐습니다.")
    assert "수익률 순위로 먼저 보던 후보는" in why["diff"]
    assert TX.next_check(by["AAA001"]).startswith("가 꾸준의 전체 구성")


def test_crosscheck_current_week_same_and_different(market: Path) -> None:
    ops = _ops(market)
    mine = _research(market)
    flows = [
        {"members": [{"rank": r["rank"], "ticker": r["ticker"]}]} for r in ops["top"]
    ]
    weekly = {
        "end_date": ops["end_date"],
        "condition": {
            "start": ops["period"]["start"],
            "end": ops["period"]["end"],
            "filters": FILTERS,
        },
        "flows": flows,
        "data_quality_snapshot": {
            "price_states": {
                "rows": {
                    it["ticker"]: {"state": it["state"]}
                    for it in mine["items"]
                    if it["rank"] <= 30
                },
                "kodex200": {"state": mine["bench_state"]},
            }
        },
    }
    ops = {**ops, "filters": FILTERS}

    def fetch(path: str) -> dict:
        return weekly if path.startswith("/weekly") else ops

    got = CC.current_week(fetch, lambda: mine)
    assert got["status"] == "SAME", got["same"]
    swapped = [dict(f, members=[dict(m) for m in f["members"]]) for f in flows]
    t0, t1 = swapped[0]["members"][0]["ticker"], swapped[1]["members"][0]["ticker"]
    swapped[0]["members"][0]["ticker"], swapped[1]["members"][0]["ticker"] = (
        t1,
        t0,
    )  # 1 · 2위 맞바꿈
    bad = {**weekly, "flows": swapped}
    got = CC.current_week(
        lambda p: bad if p.startswith("/weekly") else ops, lambda: mine
    )
    assert got["status"] == "DIFFERENT" and got["same"]["top30_weekly"] is False
    ops_bad = {
        **ops,
        "counts": {**ops["counts"], "no_price": ops["counts"]["no_price"] + 1},
    }
    got = CC.current_week(
        lambda p: weekly if p.startswith("/weekly") else ops_bad, lambda: mine
    )
    assert got["status"] == "DIFFERENT" and got["same"]["counts"] is False
    moved = {**weekly, "end_date": "2026-11-19"}
    got = CC.current_week(
        lambda p: moved if p.startswith("/weekly") else ops, lambda: mine
    )
    assert got["status"] == "DATA_CHANGED" and "end_date" in got["changed"]

    def flip(first: dict, second: dict, path: str):
        """처음 조회 = first · 다시 조회 = second(같은 끝일)."""
        seen: dict[str, int] = {}

        def f(p: str) -> dict:
            key = "w" if p.startswith("/weekly") else "s"
            seen[key] = seen.get(key, 0) + 1
            if key == path[0]:
                return first if seen[key] % 2 == 1 else second
            return weekly if key == "w" else ops

        return f

    # 검증자 r1 F4 — 끝일은 같지만 다시 조회한 주간 응답의 1 · 2위가 바뀜 → 같은 시점 아님
    got = CC.current_week(flip(weekly, bad, "w"), lambda: mine)
    assert got["status"] == "DATA_CHANGED" and got["changed"] == ["weekly"]
    got = CC.current_week(flip(ops, ops_bad, "s"), lambda: mine)
    assert got["status"] == "DATA_CHANGED" and got["changed"] == ["summary"]
    states = {
        **weekly,
        "data_quality_snapshot": {
            "price_states": {"rows": {}, "kodex200": {"state": "intraday"}}
        },
    }
    got = CC.current_week(flip(weekly, states, "w"), lambda: mine)
    assert got["status"] == "DATA_CHANGED"


def test_stored_response_compare(market: Path, tmp_path: Path) -> None:
    mine = _research(market)
    snap = [
        {
            "rank": it["rank"],
            "ticker": it["ticker"],
            "one_month_return_pct": it["one_month"]["value"],
        }
        for it in mine["items"]
    ]
    f = tmp_path / "response.json"
    f.write_text(
        json.dumps({"end_date": END, "candidate_snapshot": snap}), encoding="utf-8"
    )
    got = CC.stored_response(f, lambda e: _research(market, end=e))
    assert got["status"] == "SAME" and got["same_codes"]
    snap[0]["one_month_return_pct"] += 1.0
    f.write_text(
        json.dumps({"end_date": END, "candidate_snapshot": snap}), encoding="utf-8"
    )
    assert (
        CC.stored_response(f, lambda e: _research(market, end=e))["status"]
        == "DIFFERENT"
    )


def _cli():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "run_candidate_compare_t",
        Path(__file__).resolve().parents[1] / "scripts" / "run_candidate_compare.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_week_command_stops_when_same_date_data_restored(
    market: Path, tmp_path: Path, monkeypatch
) -> None:
    """검증자 r1 F4 같은 종류 — 한 장을 만드는 사이 끝일은 그대로 · 같은 날짜 값이 다시 저장되면 멈춤."""
    from datetime import datetime as _dt
    from datetime import timezone as _tz

    from app.candidate_compare.protocol import CheckRequired, Config

    mod = _cli()
    monkeypatch.setattr(mod, "MARKET_DB", market)
    monkeypatch.setattr(mod, "_sources", lambda: ({}, None))
    monkeypatch.setattr(CU, "default_is_trading", _weekday)
    touched: list[int] = []

    def factory(db):
        def read(ticker, cond):
            if os.environ.get("P703_TOUCH") and not touched:
                touched.append(1)
                with sqlite3.connect(market) as con:
                    con.execute(
                        "UPDATE etf_daily_price SET close = close + 1"
                        " WHERE ticker = 'AAA001' AND date = ?",
                        (END,),
                    )
            return {**_reader(ticker, cond), "exposure": None}

        return read

    monkeypatch.setattr(CU, "default_reader", factory)
    cfg = Config(root=tmp_path / "out", expected=None)
    now = _dt(2026, 11, 21, 0, 0, tzinfo=_tz.utc)
    ok = mod.cmd_week(cfg, now, None)
    assert Path(ok["dir"], "page.html").exists()
    monkeypatch.setenv("P703_TOUCH", "1")
    with pytest.raises(CheckRequired):
        mod.cmd_week(cfg, now, None)


# ── 반박 m2 · m3 · m4 · m5 ─────────────────────────────────────────────────────


def test_weekly_dates_checks_all_five_weeks_against_schedule() -> None:
    """반박 m3 — W0 뿐 아니라 W-4 ~ W-1 도 일정상 마지막 거래일 · 사이에 빠진 주 없음."""
    base = _bdays("2026-11-20", 40)
    ok = {d: "after_close" for d in base}
    # W-2(11/06 금) 행이 축에 없음 → 그 주 축 마지막 = 11/05(목) ≠ 일정 11/06
    axis = [d for d in base if d != "2026-11-06"]
    got = CU.weekly_dates(axis, "2026-11-20", ok, _weekday)
    assert got["dates"] is None and got["gap"] == {
        "why": "schedule_gap",
        "week_last": "2026-11-05",
        "scheduled": "2026-11-06",
    }
    # 한 주(11/09 ~ 11/13) 전체가 축에 없음 → 빠진 주
    axis2 = [d for d in base if not ("2026-11-09" <= d <= "2026-11-13")]
    got2 = CU.weekly_dates(axis2, "2026-11-20", ok, _weekday)
    assert got2["dates"] is None and got2["gap"]["why"] == "missing_week"
    assert got2["gap"]["scheduled"] == "2026-11-13"
    # 일정이 그 주 전체를 휴장으로 알면 빠진 주가 아님(축도 그 주를 건너뜀)
    hol = {d for d in base if "2026-11-09" <= d <= "2026-11-13"}
    got3 = CU.weekly_dates(
        axis2, "2026-11-20", ok, lambda d: _weekday(d) and d not in hol
    )
    assert got3["gap"] is None and got3["dates"] == [
        "2026-10-16",
        "2026-10-23",
        "2026-10-30",
        "2026-11-06",
        "2026-11-20",
    ]
    # 수요일 끝일 — 그 주는 아직 거래 중(일정상 마지막 11/20 > 끝일)이라 건너뜀 · 사유 = 거래 중(자료 빠짐 아님)
    wed = CU.weekly_dates(base, "2026-11-18", ok, _weekday)
    assert wed["w0"] == "2026-11-13" and wed["skipped"] == [
        {"week_last": "2026-11-18", "why": "week_unfinished"}
    ]
    assert "그 주 거래가 아직 끝나지 않음" in TX.week_note(wed, "2026-11-18")
    # 일정 밖 날짜(토요일) 행이 축에 끼어도 끝난 주(11/20)를 건너뛰지 않음 · 그 행은 따로 남김
    sat = CU.weekly_dates(
        base + ["2026-11-21"],
        "2026-11-21",
        {**ok, "2026-11-21": "after_close"},
        _weekday,
    )
    assert (
        sat["w0"] == "2026-11-20" and sat["mid_week"] is True and sat["skipped"] == []
    )
    assert sat["off_schedule"] == ["2026-11-21"] and sat["gap"] is None
    # 정상 = gap 없음
    assert CU.weekly_dates(base, "2026-11-20", ok, _weekday)["gap"] is None


def test_unavailable_weeks_mark_every_candidate(market: Path, monkeypatch) -> None:
    real = CU.weekly_dates

    def broken(*a, **k):
        out = real(*a, **k)
        return {
            **out,
            "dates": None,
            "w0": None,
            "mid_week": None,
            "gap": {"why": "missing_week", "scheduled": "2026-11-13"},
        }

    monkeypatch.setattr(CU, "weekly_dates", broken)
    mine = _research(market)
    assert mine["items"] and all(
        it["up"] is None and it["week_gap"] == "weekly_unavailable"
        for it in mine["items"]
    )
    note = TX.week_note(mine["weekly"], mine["end"])
    assert "네 주 날짜를 정하지 못했습니다" in note and "11/13가 있는 주" in note
    html = PG.render(mine, generated_at="2026-11-21T09:00:00+09:00", verdict=None)
    assert (
        "네 주 날짜를 정하지 못했습니다" in html
        and "주 마감 날짜를 정하지 못함" in html
    )


def test_mid_week_note_names_actual_week_end_and_skipped_reason() -> None:
    """반박 m5 — '지난주 마감'이라 뭉뚱그리지 않고 실제 네 주 끝일과 건너뛴 사유를 보인다."""
    axis = _bdays("2026-11-23", 40)
    ok = {d: "after_close" for d in axis}
    wk = CU.weekly_dates(axis, "2026-11-23", {**ok, "2026-11-20": "intraday"}, _weekday)
    note = TX.week_note(wk, "2026-11-23")
    assert "1개월 끝일(11/23)과 네 주 끝일(11/13)이 다릅니다" in note
    assert "11/20가 있는 주: 그날 KODEX 200 가격이 마감 뒤 저장이 아님" in note
    assert "지난주 마감" not in note
    fri = CU.weekly_dates(axis, "2026-11-20", ok, _weekday)
    assert TX.week_note(fri, "2026-11-20") is None


def test_unconfirmed_texts_do_not_say_no_price(market: Path) -> None:
    """반박 m4 — 장중 저장 · 저장 시각 불명도 있으므로 '가격 없음'으로 쓰지 않는다(전체 후보의 가격 없음 개수는 그대로)."""
    assert TX.chg(None) == "미확인"
    mine = _research(market)
    html = PG.render(mine, generated_at="2026-11-21T09:00:00+09:00", verdict=None)
    assert "주 마감 가격이 없어" not in html and "? 주 마감값 없음" not in html
    assert "주 마감값을 확인하지 못해" in html and "? 주 마감값 미확인" in html
    assert "주 마감값이 모두 확인된 후보" in html
    assert "주 마감 가격이 있는 후보 중" not in TX.copy_head(mine)


def test_cli_exit_code_two_on_mismatch_and_differences(
    tmp_path: Path, monkeypatch
) -> None:
    """반박 m2 — 검산 어긋남 · 대조 차이를 정상 종료(0)로 내지 않는다."""
    from datetime import datetime as _dt
    from datetime import timezone as _tz

    from app.candidate_compare.protocol import Config

    mod = _cli()
    monkeypatch.setattr(
        mod.VF, "verify", lambda cfg, now: {"status": "MISMATCH", "checks": ["x"]}
    )
    assert mod.main(["verify"]) == 2
    monkeypatch.setattr(
        mod.VF, "verify", lambda cfg, now: {"status": "VERIFIED_OK", "checks": []}
    )
    assert mod.main(["verify"]) == 0
    sealed = {
        "only_sealed": [],
        "only_pc": [],
        "top30_same": True,
        "up_differs": 0,
        "picks_same": {"same": True},
        "sealed_pop": 1,
        "pc_pop": 1,
        "rank_differs": 3,
        "max_1m_gap_pctp": 0.1,
    }
    monkeypatch.setattr(mod.CC, "current_week", lambda f, r: {"status": "SAME"})
    monkeypatch.setattr(mod.CC, "stored_response", lambda p, r: {"status": "SAME"})
    monkeypatch.setattr(mod.CC, "sealed_week", lambda c, s, r: dict(sealed))
    cfg = Config(root=tmp_path / "out", expected=None)
    now = _dt(2026, 11, 24, 0, 0, tzinfo=_tz.utc)
    assert mod.cmd_cross(cfg, now)["all_same"] is True  # 순위 차이는 가격판 설명용
    for bad in (
        {"up_differs": 1},
        {"top30_same": False},
        {"only_pc": ["X"]},
        {"picks_same": {"same": False}},
    ):
        monkeypatch.setattr(
            mod.CC, "sealed_week", lambda c, s, r, b=bad: {**sealed, **b}
        )
        assert mod.cmd_cross(cfg, now)["all_same"] is False, bad
    monkeypatch.setattr(mod.CC, "sealed_week", lambda c, s, r: dict(sealed))
    monkeypatch.setattr(mod.CC, "current_week", lambda f, r: {"status": "DATA_CHANGED"})
    assert mod.cmd_cross(cfg, now)["all_same"] is False
    monkeypatch.setattr(mod, "cmd_cross", lambda cfg, now: {"all_same": False})
    assert mod.main(["cross-check"]) == 2
    monkeypatch.setattr(mod, "cmd_cross", lambda cfg, now: {"all_same": True})
    assert mod.main(["cross-check"]) == 0


# ── 검증자 r2 F7 — 대조에 쓰는 칸 = 같은 시점 지문 칸 ─────────────────────────────


def _ac1(market: Path):
    ops = _ops(market)
    mine = _research(market)
    weekly = {
        "end_date": ops["end_date"],
        "condition": {
            "start": ops["period"]["start"],
            "end": ops["period"]["end"],
            "filters": dict(FILTERS),
        },
        "flows": [
            {"members": [{"rank": r["rank"], "ticker": r["ticker"]}]}
            for r in ops["top"]
        ],
        "data_quality_snapshot": {
            "price_states": {
                "rows": {
                    it["ticker"]: {"state": it["state"]}
                    for it in mine["items"]
                    if it["rank"] <= 30
                },
                "kodex200": {"state": mine["bench_state"]},
            }
        },
    }
    return weekly, {**ops, "filters": dict(FILTERS)}, mine


def _swap_top(rows):
    rows = [dict(r) for r in rows]
    rows[0]["ticker"], rows[1]["ticker"] = rows[1]["ticker"], rows[0]["ticker"]
    return rows


W_MUT = {
    "end_date": lambda w: {**w, "end_date": "2026-11-19"},
    "period": lambda w: {**w, "condition": {**w["condition"], "start": "2026-10-20"}},
    "filters": lambda w: {
        **w,
        "condition": {
            **w["condition"],
            "filters": {**w["condition"]["filters"], "exclude_futures": False},
        },
    },
    "top": lambda w: {
        **w,
        "flows": [
            {"members": [m]} for m in _swap_top([f["members"][0] for f in w["flows"]])
        ],
    },
    "states": lambda w: {
        **w,
        "data_quality_snapshot": {
            "price_states": {
                **w["data_quality_snapshot"]["price_states"],
                "rows": {
                    t: {"state": "intraday"}
                    for t in w["data_quality_snapshot"]["price_states"]["rows"]
                },
            }
        },
    },
    "kodex_state": lambda w: {
        **w,
        "data_quality_snapshot": {
            "price_states": {
                **w["data_quality_snapshot"]["price_states"],
                "kodex200": {"state": "intraday"},
            }
        },
    },
}
S_MUT = {
    "end_date": lambda s: {**s, "end_date": "2026-11-19"},
    "period": lambda s: {**s, "period": {**s["period"], "start": "2026-10-20"}},
    "filters": lambda s: {**s, "filters": {**s["filters"], "exclude_futures": False}},
    "top": lambda s: {**s, "top": _swap_top(s["top"])},
    "counts": lambda s: {
        **s,
        "counts": {**s["counts"], "no_price": s["counts"]["no_price"] + 1},
    },
    "state_counts": lambda s: {
        **s,
        "price_state": {**(s.get("price_state") or {}), "intraday_count": 99},
    },
    "kodex_state": lambda s: {
        **s,
        "regime": {**(s.get("regime") or {}), "price": {"state": "unknown"}},
    },
}


def _flip(first: dict, second: dict, which: str, other: dict):
    """처음 조회 = first · 다시 조회 = second(which 쪽만) · 다른 쪽은 늘 other."""
    seen = {"w": 0, "s": 0}

    def f(p: str) -> dict:
        key = "w" if p.startswith("/weekly") else "s"
        seen[key] += 1
        if key != which:
            return other
        return first if seen[key] % 2 == 1 else second

    return f


def test_every_compared_field_is_in_the_same_time_print(market: Path) -> None:
    """시험이 대조 칸 목록 전체를 덮는다 — 추출 함수에 칸이 늘면 이 시험이 먼저 깨진다."""
    weekly, ops, _mine = _ac1(market)
    assert set(W_MUT) == set(CC.weekly_fields(weekly))
    assert set(S_MUT) == set(CC.summary_fields(ops))


@pytest.mark.parametrize("field", sorted(W_MUT))
def test_weekly_field_change_between_reads_is_data_changed(market: Path, field) -> None:
    weekly, ops, mine = _ac1(market)
    assert (
        CC.current_week(
            lambda p: weekly if p.startswith("/weekly") else ops, lambda: mine
        )["status"]
        == "SAME"
    )
    second = W_MUT[field](weekly)
    assert CC.weekly_fields(second) != CC.weekly_fields(weekly)
    got = CC.current_week(_flip(weekly, second, "w", ops), lambda: mine)
    assert got["status"] == "DATA_CHANGED" and "weekly" in got["changed"], got


@pytest.mark.parametrize("field", sorted(S_MUT))
def test_summary_field_change_between_reads_is_data_changed(
    market: Path, field
) -> None:
    """검증자 r2 F7 — 「후보리스트」 제외 조건 등 대조 칸이 다시 조회에서 바뀌면 같은 시점이 아니다."""
    weekly, ops, mine = _ac1(market)
    second = S_MUT[field](ops)
    assert CC.summary_fields(second) != CC.summary_fields(ops)
    got = CC.current_week(_flip(ops, second, "s", weekly), lambda: mine)
    assert got["status"] == "DATA_CHANGED" and "summary" in got["changed"], got


def test_malformed_responses_do_not_raise(market: Path) -> None:
    """r2 F5 같은 종류 — 응답이 객체가 아니거나 칸 형이 틀려도 예외 없이 다름 · 바뀜으로 본다."""
    weekly, ops, mine = _ac1(market)
    for bad in (
        [],
        None,
        {"flows": "x", "condition": 3},
        {"top": [1, None], "counts": []},
    ):
        got = CC.current_week(
            lambda p, b=bad: b if p.startswith("/weekly") else ops, lambda: mine
        )
        assert got["status"] in ("DIFFERENT", "DATA_CHANGED")
        got = CC.current_week(
            lambda p, b=bad: weekly if p.startswith("/weekly") else b, lambda: mine
        )
        assert got["status"] in ("DIFFERENT", "DATA_CHANGED")


def test_cross_check_part_errors_are_recorded(tmp_path: Path, monkeypatch) -> None:
    from datetime import datetime as _dt
    from datetime import timezone as _tz

    from app.candidate_compare.protocol import Config

    mod = _cli()

    def boom(*a, **k):
        raise ValueError("깨진 응답")

    monkeypatch.setattr(mod.CC, "current_week", boom)
    monkeypatch.setattr(mod.CC, "stored_response", lambda p, r: {"status": "SAME"})
    monkeypatch.setattr(mod.CC, "sealed_week", lambda c, s, r: {"status": "ERROR"})
    cfg = Config(root=tmp_path / "out", expected=None)
    res = mod.cmd_cross(cfg, _dt(2026, 11, 24, 0, 0, tzinfo=_tz.utc))
    assert (
        res["current"] == "ERROR"
        and res["all_same"] is False
        and res["sealed_ok"] is False
    )
    body = json.loads(
        (tmp_path / "out" / "cross_check" / f"{res['id']}.json").read_text("utf-8")
    )
    assert body["current"]["error"].startswith("ValueError")


@pytest.mark.parametrize(
    "side, field", [("w", f) for f in sorted(W_MUT)] + [("s", f) for f in sorted(S_MUT)]
)
def test_every_compared_field_is_actually_compared(market: Path, side, field) -> None:
    """두 번 조회 모두 같게 한 곳만 다르면(같은 시점) 세 곳 대조가 다름을 낸다 — 대조 칸마다."""
    weekly, ops, mine = _ac1(market)
    if side == "w":
        w2 = W_MUT[field](weekly)
        got = CC.current_week(
            lambda p: w2 if p.startswith("/weekly") else ops, lambda: mine
        )
    else:
        s2 = S_MUT[field](ops)
        got = CC.current_week(
            lambda p: weekly if p.startswith("/weekly") else s2, lambda: mine
        )
    if field == "end_date":
        assert got["status"] == "DATA_CHANGED" and got["changed"] == ["end_date"]
    else:
        assert got["status"] == "DIFFERENT", (field, got["same"])


# ── r2 정정 전 반박 검토 5 · 6 — 형까지 · 행 집합 · 보관 응답 · 기록 쓰기 ─────────────


def _states_rows(w):
    return w["data_quality_snapshot"]["price_states"]["rows"]


@pytest.mark.parametrize(
    "case", ["one_row", "extra_unknown", "rank_bool", "rank_float", "filters_int"]
)
def test_partial_or_mistyped_responses_are_different(market: Path, case) -> None:
    weekly, ops, mine = _ac1(market)
    w, s = json.loads(json.dumps(weekly)), json.loads(json.dumps(ops))
    if case == "one_row":
        t = next(iter(_states_rows(w)))
        w["data_quality_snapshot"]["price_states"]["rows"] = {t: _states_rows(w)[t]}
    elif case == "extra_unknown":
        _states_rows(w)["ZZZ999"] = {}
    elif case == "rank_bool":
        w["flows"][0]["members"][0]["rank"] = True
    elif case == "rank_float":
        s["top"][1]["rank"] = float(s["top"][1]["rank"])
    else:
        s["filters"] = {k: int(v) for k, v in s["filters"].items()}
    got = CC.current_week(lambda p: w if p.startswith("/weekly") else s, lambda: mine)
    assert got["status"] == "DIFFERENT", (case, got["same"])


@pytest.mark.parametrize(
    "case", ["one_row", "empty", "nan", "dup", "rank_bool", "no_value"]
)
def test_stored_response_needs_whole_and_finite(
    market: Path, tmp_path: Path, case
) -> None:
    mine = _research(market)
    snap = [
        {
            "rank": it["rank"],
            "ticker": it["ticker"],
            "one_month_return_pct": it["one_month"]["value"],
        }
        for it in mine["items"]
        if it["rank"] <= 30
    ]
    if case == "one_row":
        snap = snap[:1]
    elif case == "empty":
        snap = []
    elif case == "nan":
        snap[0]["one_month_return_pct"] = float("nan")
    elif case == "dup":
        snap = snap + [dict(snap[0])]
    elif case == "rank_bool":
        snap[0]["rank"] = True if snap[0]["rank"] == 1 else snap[0]["rank"] * 1.0
    else:
        snap[0].pop("one_month_return_pct")
    f = tmp_path / "response.json"
    f.write_text(
        json.dumps({"end_date": END, "candidate_snapshot": snap}), encoding="utf-8"
    )
    assert (
        CC.stored_response(f, lambda e: _research(market, end=e))["status"]
        == "DIFFERENT"
    )


def test_cross_check_writes_record_with_nan_and_surrogates(
    tmp_path: Path, monkeypatch
) -> None:
    from datetime import datetime as _dt
    from datetime import timezone as _tz

    from app.candidate_compare.protocol import Config

    mod = _cli()
    monkeypatch.setattr(
        mod.CC, "current_week", lambda f, r: {"status": "DIFFERENT", "x": float("nan")}
    )
    monkeypatch.setattr(
        mod.CC, "stored_response", lambda p, r: {"status": "SAME", "t": "\ud800"}
    )
    monkeypatch.setattr(mod.CC, "sealed_week", lambda c, s, r: {"status": "ERROR"})
    cfg = Config(root=tmp_path / "out", expected=None)
    res = mod.cmd_cross(cfg, _dt(2026, 11, 24, 0, 0, tzinfo=_tz.utc))
    body = json.loads(
        (tmp_path / "out" / "cross_check" / f"{res['id']}.json").read_text("utf-8")
    )
    assert res["all_same"] is False and body["current"]["x"] == "nan"


@pytest.mark.parametrize(
    "case", ["ticker_list", "ticker_none", "no_end_date", "end_date_list"]
)
def test_stored_response_odd_keys_are_different(
    market: Path, tmp_path: Path, case
) -> None:
    """r3 F8 · F9 같은 종류 — 종목 칸이 글이 아니거나 끝일이 빠져도 예외 없이 다름."""
    mine = _research(market)
    snap = [
        {
            "rank": it["rank"],
            "ticker": it["ticker"],
            "one_month_return_pct": it["one_month"]["value"],
        }
        for it in mine["items"]
        if it["rank"] <= 30
    ]
    body = {"end_date": END, "candidate_snapshot": snap}
    if case == "ticker_list":
        snap[0]["ticker"] = [snap[0]["ticker"]]
    elif case == "ticker_none":
        snap[0]["ticker"] = None
    elif case == "no_end_date":
        body.pop("end_date")
    else:
        body["end_date"] = [END]
    f = tmp_path / "response.json"
    f.write_text(json.dumps(body), encoding="utf-8")
    assert (
        CC.stored_response(f, lambda e: _research(market, end=e))["status"]
        == "DIFFERENT"
    )
