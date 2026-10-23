"""POC6-07 — 선택 ETF 종목 이동평균 · 표시값 기준 위치 · 검토 질문(설계 V1 · PLAN V1 · 판정 2026-10-23).

순수 판정(행 목록) · tmp DB 한 번 읽기 · 실제 endpoint(보유 · 후보) · 읽는 사이 자료 변경 재현.
라이브 DB · 보유 · 세션은 열지 않는다(tmp DB · conftest 격리 · `seeded` 고정 자료).
"""

from __future__ import annotations

import math
import sqlite3
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Optional

import pytest
from fastapi.testclient import TestClient

from app import api_market_topn, pc_selected_moving_average as M
from app.decision_draft_preview_service import _with_moving_average
from app.decision_preview_lines import AI_REQUEST, REVIEW_QUESTIONS, holding_flow_lines
from app.market_data_store import EtfDailyPriceRow, upsert_daily_prices
from app.preview_number_format import intl_fixed
from app.reentry_review.prices import PriceRow
from tests.test_pc_price_basis import api_client  # noqa: F401 — fixture
from tests.test_poc5_23_decision_preview_bundles import (  # noqa: F401 — fixture
    CAND,
    HELD_ETF,
    LIST_PARAMS,
    PREVIEW,
    STOCK,
    seeded,
)

FDR = "FinanceDataReader"
D = "2026-10-20"
NO_BASIS: dict[str, Any] = {"starts": {}, "returns": {}}


def _days(n: int, end: str = D) -> list[str]:
    out, d = [], date.fromisoformat(end)
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d -= timedelta(days=1)
    return list(reversed(out))


def _rows(closes: list[Any], end: str = D, source: str = FDR) -> list[PriceRow]:
    """오름차순 원본 행 · change = 실제 비율(연결 정상)."""
    out: list[PriceRow] = []
    prev = None
    for d, c in zip(_days(len(closes), end), closes):
        ok = isinstance(c, (int, float)) and c > 0 and math.isfinite(c)
        ch = (c / prev - 1.0) if (prev and ok) else 0.0
        out.append(PriceRow(d, c, source, "2026-10-20T13:55:00Z", ch))
        prev = c if ok else prev
    return out


def _replace(rows: list[PriceRow], i: int, **kw: Any) -> list[PriceRow]:
    r = rows[i]
    rows = list(rows)
    rows[i] = PriceRow(
        kw.get("date", r.date),
        kw.get("close", r.close),
        kw.get("source", r.source),
        kw.get("fetched_at", r.fetched_at),
        kw.get("change", r.change),
    )
    return rows


def _eval(rows: list[PriceRow], **kw: Any) -> M.MovingAverageEvidence:
    return M.evaluate(rows, rows[-1].date if rows else D, **{**NO_BASIS, **kw})


# ── 산술 · 표시 · 경계 ──────────────────────────────────────────────────────


def test_known_arithmetic_and_display() -> None:
    ev = _eval(_rows([float(i) for i in range(1, 61)]))
    assert ev.status == "ok"
    assert ev.ma20.value == sum(range(41, 61)) / 20 == 50.5
    assert ev.ma60.value == sum(range(1, 61)) / 60 == 30.5
    assert (ev.ma20.shown, ev.ma60.shown, ev.close_shown) == ("50.50", "30.50", "60.00")
    assert ev.relation == "종가 > MA20 > MA60"
    days = _days(60)
    assert (ev.ma20.start_date, ev.ma20.end_date) == (days[40], D)
    assert (ev.ma60.start_date, ev.ma60.end_date) == (days[0], D)
    assert M.moving_average_lines(ev.model_dump()) == [
        "종목 이동평균: MA20 50.50원 · MA60 30.50원",
        "표시값 기준 위치: 종가 > MA20 > MA60 (종가 60.00원)",
        f"이동평균 계산 구간: MA20 = 저장 종가 20개({days[40]} → {D}) · "
        f"MA60 = 저장 종가 60개({days[0]} → {D})",
    ]


def test_display_uses_existing_formatter_with_grouping() -> None:
    ev = _eval(_rows([1234567.891] * 60))
    assert ev.ma20.shown == intl_fixed(1234567.891, 2) == "1,234,567.89"
    assert ev.relation == "종가 = MA20 = MA60"


@pytest.mark.parametrize(
    "n_rows, ma20, ma60",
    [
        (19, "insufficient_history", "insufficient_history"),
        (20, "ok", "insufficient_history"),
        (59, "ok", "insufficient_history"),
        (60, "ok", "ok"),
    ],
)
def test_window_boundaries(n_rows: int, ma20: str, ma60: str) -> None:
    ev = _eval(_rows([100.0 + i for i in range(n_rows)]))
    assert (ev.ma20.status, ev.ma60.status) == (ma20, ma60)
    assert ev.ma20.row_count == min(n_rows, 20)
    assert ev.ma60.row_count == min(n_rows, 60)
    assert (ev.relation is None) == (ma60 != "ok")
    lines = M.moving_average_lines(ev.model_dump())
    if ma20 != "ok":
        assert lines[0] == (
            f"종목 이동평균: MA20 계산 불가(저장 종가 {n_rows}/20개) · "
            f"MA60 계산 불가(저장 종가 {n_rows}/60개)"
        )
        assert lines[2] == "이동평균 계산 구간: MA20 = 계산 안 함 · MA60 = 계산 안 함"
    elif ma60 != "ok":
        assert f"MA60 계산 불가(저장 종가 {n_rows}/60개)" in lines[0]
        assert lines[1].startswith("표시값 기준 위치: 확인 불가(MA60 없음) · 종가 ")
        assert lines[2].endswith("MA60 = 계산 안 함")


def test_display_tie_even_when_internal_values_differ() -> None:
    # 가장 오래된 1개만 10,000.006 → MA60 내부 10,000.0001 · 표시값은 셋 다 10,000.00.
    rows = _rows([10000.006] + [10000.0] * 59)
    ev = _eval(rows)
    assert ev.ma60.value != ev.close and ev.ma60.shown == ev.close_shown == "10,000.00"
    assert ev.relation == "종가 = MA20 = MA60"


@pytest.mark.parametrize(
    "shown, expected",
    [
        (("1.00", "2.00", "1.00"), "MA20 > 종가 = MA60"),
        (("2.00", "2.00", "1.00"), "종가 = MA20 > MA60"),
        (("1.00", "1.00", "2.00"), "MA60 > 종가 = MA20"),
        (("3.00", "1.00", "2.00"), "종가 > MA60 > MA20"),
        (("1,000.00", "999.99", "1,000.01"), "MA60 > 종가 > MA20"),
    ],
)
def test_relation_order_and_tie_names(
    shown: tuple[str, str, str], expected: str
) -> None:
    assert M.relation_text(*shown) == expected


# ── 창별 실패 · 판정 순서 ───────────────────────────────────────────────────


def test_old_part_damage_keeps_ma20() -> None:
    rows = _replace(_rows([100.0 + i for i in range(60)]), 10, close=0.0)
    ev = _eval(rows)
    assert (ev.ma20.status, ev.ma60.status) == ("ok", "invalid_price")
    assert ev.relation is None
    lines = M.moving_average_lines(ev.model_dump())
    assert lines[0].endswith("MA60 계산 불가(가격 확인 필요)")
    assert (
        lines[1] == f"표시값 기준 위치: 확인 불가(MA60 없음) · 종가 {ev.close_shown}원"
    )


@pytest.mark.parametrize(
    "break_at, ma20",
    [
        # 행 i 의 change = (i-1 → i) 연결 · MA20 창 = 행 40~59.
        (40, "ok"),  # MA20 창 첫 행으로 들어오는 연결(창 밖) — MA20 은 보지 않음
        (41, "basis_unconfirmed"),  # MA20 창 안 첫 연결
        (59, "basis_unconfirmed"),  # D 로 들어오는 연결
    ],
)
def test_link_break_is_checked_inside_each_window(break_at: int, ma20: str) -> None:
    rows = _replace(_rows([100.0 + i for i in range(60)]), break_at, change=0.05)
    ev = _eval(rows)
    assert ev.ma20.status == ma20
    assert ev.ma60.status == "basis_unconfirmed"
    assert M.moving_average_lines(ev.model_dump())[0].endswith(
        "MA60 계산 불가(가격 기준 확인 필요)"
    )


def test_link_before_ma60_window_is_not_checked() -> None:
    # 61번째 이전 행은 읽지 않는다 — 창 첫 행 change 가 이상해도(창 밖 연결) 계산한다.
    rows = _replace(_rows([100.0 + i for i in range(60)]), 0, change=0.5)
    assert _eval(rows).ma60.status == "ok"


def test_unreadable_change_is_basis_unconfirmed() -> None:
    rows = _replace(_rows([100.0 + i for i in range(60)]), 55, change="x")
    ev = _eval(rows)
    assert (ev.ma20.status, ev.ma60.status) == (
        "basis_unconfirmed",
        "basis_unconfirmed",
    )


@pytest.mark.parametrize(
    "bad",
    [
        {"close": -1.0},
        {"close": None},
        {"close": float("inf")},
        {"close": "100"},
        {"close": True},
        {"source": "KRX"},
    ],
)
def test_invalid_close_or_source_in_window(bad: dict[str, Any]) -> None:
    ev = _eval(_replace(_rows([100.0 + i for i in range(60)]), 50, **bad))
    assert (ev.ma20.status, ev.ma60.status) == ("invalid_price", "invalid_price")


@pytest.mark.parametrize("bad_date", ["20261001", "2026-10-1", "2026/10/01", "", None])
def test_unparseable_date_is_not_dropped(bad_date: Optional[str]) -> None:
    rows = _replace(_rows([100.0 + i for i in range(60)]), 5, date=bad_date)
    ev = _eval(rows)
    assert (ev.ma20.status, ev.ma60.status) == ("ok", "date_unconfirmed")
    assert ev.ma60.row_count == 60  # 거른 뒤 오래된 행으로 채우지 않음


def test_duplicate_date_is_not_dropped() -> None:
    rows = _rows([100.0 + i for i in range(60)])
    rows = _replace(rows, 30, date=rows[29].date)
    ev = _eval(rows)
    assert (ev.ma20.status, ev.ma60.status) == ("ok", "duplicate_date")


@pytest.mark.parametrize(
    "edits, n_rows, expected",
    [
        # 행 부족이 가장 먼저(다른 문제가 같이 있어도).
        ({5: {"close": 0.0, "date": "x"}}, 59, "insufficient_history"),
        # 날짜 형식 → 날짜 중복 → 종가 · 출처 → 연결.
        ({5: {"date": "x", "close": 0.0}}, 60, "date_unconfirmed"),
        ({6: {"date": "DUP", "close": 0.0}}, 60, "duplicate_date"),
        # 종가 문제와 떨어진 곳(30)의 연결 문제 — 이웃이면 연결 검사가 원래 건너뛰므로 떨어뜨린다.
        ({5: {"close": 0.0}, 30: {"change": 0.9}}, 60, "invalid_price"),
        ({6: {"change": 0.9}}, 60, "basis_unconfirmed"),
    ],
)
def test_window_check_order(
    edits: dict[int, dict[str, Any]], n_rows: int, expected: str
) -> None:
    rows = _rows([100.0 + i for i in range(n_rows)])
    for i, kw in edits.items():
        if kw.get("date") == "DUP":
            kw = {**kw, "date": rows[i - 1].date}
        rows = _replace(rows, i, **kw)
    assert M.compute_window(rows, 60).status == expected


# ── 관측 전체(D 행) ─────────────────────────────────────────────────────────


def test_d_row_missing_and_invalid() -> None:
    rows = _rows([100.0] * 60)
    assert M.evaluate(rows, "2026-10-21", **NO_BASIS).status == "d_row_missing"
    assert M.evaluate([], D, **NO_BASIS).status == "d_row_missing"
    for bad in ({"close": 0.0}, {"close": None}, {"source": "KRX"}):
        ev = M.evaluate(_replace(rows, 59, **bad), D, **NO_BASIS)
        assert ev.status == "d_close_invalid" and ev.ma20 is None
        assert M.moving_average_lines(ev.model_dump()) == [
            f"종목 이동평균: 확인 불가 — 가격 기준일({D}) 저장 종가 확인 필요",
            "표시값 기준 위치: 확인 불가",
        ]


# ── 같은 D 의 기존 가격 근거 대조(판정 §3-1) ─────────────────────────────────


def _flow_expect(rows: list[PriceRow]) -> dict[str, Any]:
    """기존 흐름 읽기(거른 행 · `_window_return_pct`)가 같은 행에서 냈을 값."""
    from app.short_term_momentum import _window_return_pct

    s = [(r.date, float(r.close)) for r in rows if M._kept(r.close)]
    return {
        "starts": {5: s[-6][0], 20: s[-21][0]},
        "returns": {n: _window_return_pct(s, n) for n in (5, 10, 20)},
    }


def test_holding_basis_matches_when_same_rows() -> None:
    rows = _rows([100.0 + 0.37 * i for i in range(60)])
    ev = M.evaluate(rows, D, **_flow_expect(rows))
    assert ev.status == "ok"
    assert ev.basis_checked == [
        "start_date_5d",
        "start_date_20d",
        "return_5d_pct",
        "return_10d_pct",
        "return_20d_pct",
    ]


@pytest.mark.parametrize("which", ["d_close", "d20_close", "start_date"])
def test_holding_basis_contradiction_is_unconfirmed(which: str) -> None:
    rows = _rows([100.0 + 0.37 * i for i in range(60)])
    expect = _flow_expect(rows)
    if which == "d_close":  # 같은 D 날짜 · 다른 종가(읽는 사이 정정)
        rows = _replace(rows, 59, close=rows[59].close + 0.01)
    elif which == "d20_close":
        rows = _replace(rows, 39, close=rows[39].close * 1.5, change=None)
    else:
        expect["starts"][20] = "2026-01-02"
    ev = M.evaluate(rows, D, **expect)
    assert ev.status == "basis_mismatch" and ev.ma20 is None
    assert M.moving_average_lines(ev.model_dump())[0] == (
        f"종목 이동평균: 확인 불가 — 같은 기준일({D})의 가격 근거가 앞서 읽은 값과 다릅니다"
        "(읽는 사이 저장 자료가 바뀌었을 수 있음)"
    )


@pytest.mark.parametrize(
    "at", [54, 50]
)  # 54 = D-5 번째 행(5저장일 변화율 NaN) · 50 = 그 밖
def test_inf_close_kept_like_flow_read_is_not_a_fake_contradiction(at: int) -> None:
    # SQL `close > 0` 은 무한대 종가 행을 남긴다 → 기존 흐름 값도 그 행으로 계산됐다. 같은 규칙이면 모순이 아니고,
    # 그 행은 창 판정(가격 확인 필요)으로만 드러난다.
    rows = _replace(_rows([100.0 + i for i in range(60)]), at, close=float("inf"))
    expect = _flow_expect(rows)
    if at == 54:
        assert math.isnan(expect["returns"][5])
    ev = M.evaluate(rows, D, **expect)
    assert ev.status == "ok"
    assert (ev.ma20.status, ev.ma60.status) == ("invalid_price", "invalid_price")


def test_absent_expectations_are_skipped_not_contradictions() -> None:
    # 앞선 근거에 값이 없던 항목(예: KODEX200 부족으로 변화율 없음)은 대조하지 않는다.
    rows = _rows([100.0 + i for i in range(60)])
    ev = M.evaluate(
        rows, D, starts={5: None, 20: None}, returns={5: None, 10: True, 20: "x"}
    )
    assert ev.status == "ok" and ev.basis_checked == []


def test_basis_fetched_at_alone_is_not_a_contradiction() -> None:
    rows = _rows([100.0 + i for i in range(60)])
    expect = _flow_expect(rows)
    rows = _replace(rows, 59, fetched_at="2026-10-23T01:00:00Z")
    preview = [(r.date, float(r.close), 1, r.source) for r in reversed(rows[-21:])]
    assert M.evaluate(rows, D, **expect, preview_desc=preview).status == "ok"


@pytest.mark.parametrize(
    "starts, returns",
    [({20: "2026-09-21"}, {}), ({}, {20: 1.0})],  # 시작일 · 변화율 각각
)
def test_basis_value_missing_from_complete_read_is_contradiction(
    starts: dict[int, Any], returns: dict[int, Any]
) -> None:
    # 앞선 읽기는 21행 이상(20저장일 값 있음) · 새 읽기는 D 이하 전부가 10행 → 모순.
    rows = _rows([100.0 + i for i in range(10)])
    ev = M.evaluate(rows, D, starts=starts, returns=returns)
    assert ev.status == "basis_mismatch"


def test_basis_out_of_60_rows_is_not_compared() -> None:
    # 60행 중 거른 행이 45개 → 21번째 유효 행이 60행 밖 · 대조하지 않고(모순 아님) 창은 각자 판정.
    closes: list[Any] = [None] * 45 + [100.0 + i for i in range(15)]
    rows = _rows(closes)
    ev = M.evaluate(rows, D, starts={20: "2026-01-02"}, returns={20: 1.0})
    assert ev.status == "ok" and ev.basis_checked == []
    assert (ev.ma20.status, ev.ma60.status) == ("invalid_price", "invalid_price")


def _preview_rows(rows: list[PriceRow], k: int = 21) -> list[tuple[Any, ...]]:
    kept = [r for r in rows if M._kept(r.close)]
    return [(r.date, float(r.close), 7, r.source) for r in reversed(kept[-k:])]


@pytest.mark.parametrize("change", ["close", "source", "inserted", "none"])
def test_candidate_preview_rows_must_match(change: str) -> None:
    rows = _rows([100.0 + i for i in range(60)])
    preview = _preview_rows(rows)
    if change == "close":
        rows = _replace(rows, 45, close=999.0, change=None)
    elif change == "source":
        rows = _replace(rows, 50, source="NAVER_FDR")
    elif change == "inserted":
        preview = preview[:5] + preview[6:]  # 앞선 읽기에 없던 행이 사이에 생김
    ev = M.evaluate(rows, D, **NO_BASIS, preview_desc=preview)
    if change == "none":
        assert ev.status == "ok" and ev.preview_rows_compared == 21
        assert ev.basis_checked == ["preview_rows"]
    else:
        assert ev.status == "basis_mismatch"


def test_candidate_rows_gone_from_complete_read_is_contradiction() -> None:
    # 앞선 읽기 12행 · 새 읽기는 D 이하 전부가 10행(읽는 사이 오래된 2행이 사라짐) → 모순.
    rows = _rows([100.0 + i for i in range(12)])
    preview = _preview_rows(rows, 12)
    ev = M.evaluate(rows[2:], D, **NO_BASIS, preview_desc=preview)
    assert ev.status == "basis_mismatch" and ev.preview_rows_compared == 10


def test_candidate_rows_beyond_60_are_not_compared() -> None:
    # 새 읽기 60행 중 거른 행 45개 → 유효 15행 뒤의 미리보기 행은 60행 밖(대조 안 함 · 모순 아님).
    full = _rows([100.0 + i for i in range(80)])
    preview = _preview_rows(full, 21)
    rows = full[20:]
    for k in range(45):
        rows = _replace(rows, k, close=None)
    kept = [r for r in rows if M._kept(r.close)]
    assert len(rows) == 60 and len(kept) == 15
    ev = M.evaluate(rows, D, **NO_BASIS, preview_desc=preview)
    assert ev.preview_rows_compared == 15
    assert ev.status == "ok"


# ── 검증자 r1 F1 — 숫자로 못 읽는 종가(창별 격리 · 예외 없음) ────────────────────


@pytest.mark.parametrize("bad", ["broken", b"broken"])
def test_unreadable_close_in_old_part_only_fails_ma60(bad: Any) -> None:
    # 기존 최근 읽기(21행) 밖 · MA60 창 앞쪽(오래된 여섯 번째 행)만 숫자로 못 읽는 값 → MA20 · 미리보기 유지.
    rows = _rows([100.0 + i for i in range(60)])
    expect = _flow_expect(rows)  # 앞선 읽기 값(그 행은 앞선 읽기 범위 밖)
    preview = _preview_rows(rows)
    broken = _replace(rows, 5, close=bad)
    for ev in (
        M.evaluate(broken, D, **expect),
        M.evaluate(broken, D, **NO_BASIS, preview_desc=preview),
    ):
        assert ev.status == "ok"
        assert (ev.ma20.status, ev.ma60.status) == ("ok", "invalid_price")
        assert M.moving_average_lines(ev.model_dump())[0].endswith(
            "MA60 계산 불가(가격 확인 필요)"
        )


@pytest.mark.parametrize(
    "at", [54, 49, 39]
)  # D-5 · D-10 · D-20 번째 행(앞선 읽기가 숫자로 읽은 행)
def test_unreadable_close_inside_compared_rows_is_change_between_reads(at: int) -> None:
    rows = _rows([100.0 + i for i in range(60)])
    expect = _flow_expect(rows)
    preview = _preview_rows(rows)
    broken = _replace(rows, at, close="broken")
    assert M.evaluate(broken, D, **expect).status == "basis_mismatch"
    assert M.evaluate(broken, D, **NO_BASIS, preview_desc=preview).status == (
        "basis_mismatch"
    )


def test_garbage_rows_never_raise() -> None:
    """같은 종류 전수 — 종가 · change · 날짜 · 출처 어디에 무엇이 와도 예외 없이 상태 · 사유로 끝난다."""
    import random

    rng = random.Random(607)
    garbage = [
        None,
        "broken",
        b"broken",
        b"\xff",
        "",
        "1e999",
        float("inf"),
        -1.0,
        0,
        0.0,
        True,
        1e308,
        5e-324,
        "100",
        b"123.0",
        "nan",
        float("nan"),
    ]
    for _ in range(1500):
        n = rng.choice([0, 1, 5, 19, 20, 21, 40, 59, 60])
        rows = _rows([100.0 + rng.random() * 50 for _ in range(n)]) if n else []
        expect = _flow_expect(rows) if n >= 21 else NO_BASIS
        preview = _preview_rows(rows) if n else []
        for _ in range(rng.randint(0, 6)):
            if not rows:
                break
            i = rng.randrange(len(rows))
            field = rng.choice(["close", "change", "date", "source"])
            value = rng.choice(
                garbage + (["2026-13-01", "20261020", None] if field == "date" else [])
            )
            rows = _replace(rows, i, **{field: value})
        d = rows[-1].date if rows and isinstance(rows[-1].date, str) else D
        ev = M.evaluate(rows, d, **expect, preview_desc=preview or None)
        assert ev.status in M.Status.__args__
        M.moving_average_lines(ev.model_dump())


# ── 대상 판별 · 진입 판정 순서(읽기 전) ─────────────────────────────────────


def test_etf_class_unknown_is_not_stock() -> None:
    assert M.etf_class("0015B0", set()) == "unknown"
    assert M.etf_class("0015B0", {"0015B0"}) == "etf"
    assert M.etf_class("005930", {"0015B0"}) == "stock"


@pytest.fixture
def no_read(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*a: Any, **k: Any) -> None:
        raise AssertionError("읽으면 안 되는 판정")

    monkeypatch.setattr(M, "_read_rows", boom)


@pytest.mark.parametrize(
    "kind, end, ref, expected",
    [
        ("stock", "2026-10-17", D, "not_etf"),  # 대상 밖이 가장 먼저
        ("unknown", "2026-10-17", D, "etf_unknown"),
        ("etf", None, D, "no_price"),
        ("etf", D, None, "reference_unavailable"),
        ("etf", "2026-10-17", D, "date_mismatch"),
        ("unknown", None, None, "etf_unknown"),
    ],
)
def test_holding_gate_order(no_read: None, kind: str, end, ref, expected: str) -> None:
    item = {"price_dates": {"end_date": end}}
    ev = M.for_holding("0015B0", item, reference_date=ref, kind=kind)
    assert ev.status == expected
    line = M.moving_average_lines(ev.model_dump())[0]
    assert line == "종목 이동평균: " + M.WHOLE_REASON[expected].format(d=end)


def test_candidate_gate(no_read: None) -> None:
    assert M.for_candidate("0229F0", {}, []).status == "no_price"
    ev = M.for_candidate("0229F0", {"end_date": "2026-10-17"}, [(D, 1.0, 1, FDR)])
    assert ev.status == "list_read_mismatch" and ev.d == D


def test_missing_result_is_not_silent() -> None:
    assert M.moving_average_lines(None) == [
        "종목 이동평균: 확인 불가 — 계산 결과가 없습니다",
        "표시값 기준 위치: 확인 불가",
    ]


# ── tmp DB 읽기 ─────────────────────────────────────────────────────────────


def _seed(db: Path, ticker: str, closes: list[float], end: str) -> None:
    days = _days(len(closes), end)
    prev = None
    rows = []
    for d, c in zip(days, closes):
        rows.append(
            EtfDailyPriceRow(
                ticker, d, c, c, c, c, 100, (c / prev - 1.0) if prev else 0.0
            )
        )
        prev = c
    upsert_daily_prices(rows, source=FDR, db_path=db)


def test_read_once_ro_excludes_rows_after_d_and_keeps_alnum_ticker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = tmp_path / "m.sqlite"
    _seed(db, "0015K0", [100.0 + i for i in range(63)], "2026-10-23")  # D 뒤 3행
    _seed(db, "015K00", [999.0] * 70, "2026-10-23")  # 다른 종목(섞이면 값이 달라짐)
    calls: list[tuple[str, list[str]]] = []
    real = sqlite3.connect

    def spy(database: str, *a: Any, **k: Any) -> sqlite3.Connection:
        con = real(database, *a, **k)
        stmts: list[str] = []
        con.set_trace_callback(stmts.append)
        calls.append((database, stmts))
        return con

    monkeypatch.setattr(M.sqlite3, "connect", spy)
    item = {"price_dates": {"end_date": D}}
    ev = M.for_holding("0015K0", item, reference_date=D, kind="etf", db_path=db)
    assert ev.status == "ok" and ev.d == D
    assert ev.close == 159.0  # D 행(63개 중 60번째) · 뒤 3행 제외
    assert ev.ma60.value == sum(100.0 + i for i in range(60)) / 60
    assert len(calls) == 1 and calls[0][0].endswith("?mode=ro")
    selects = [s for s in calls[0][1] if s.lstrip().upper().startswith("SELECT")]
    assert len(selects) == 1 and "LIMIT 60" in selects[0] and "'0015K0'" in selects[0]


def test_db_failure_is_not_turned_into_shortage(tmp_path: Path) -> None:
    item = {"price_dates": {"end_date": D}}
    with pytest.raises(sqlite3.Error):
        M.for_holding(
            "0015B0",
            item,
            reference_date=D,
            kind="etf",
            db_path=tmp_path / "none.sqlite",
        )


@pytest.mark.parametrize("big", [1e307, 1.7e308])
def test_huge_finite_closes_keep_the_preview(big: float) -> None:
    # 합이 double 범위를 넘어도 평균은 유한(검토 F1) — 미리보기 전체 실패 · '∞원' 없음.
    ev = _eval(_rows([big] * 60))
    assert ev.status == "ok" and ev.ma60.value == big and ev.ma20.value == big
    assert ev.relation == "종가 = MA20 = MA60"
    assert "∞" not in "".join(M.moving_average_lines(ev.model_dump()))
    mixed = _eval(_rows([1.0] * 30 + [big] * 30))
    assert math.isfinite(mixed.ma60.value) and mixed.ma20.value == big


@pytest.mark.parametrize("stored", ["Infinity", b"123.0"])
def test_text_or_blob_close_kept_like_sql_is_not_a_fake_contradiction(
    tmp_path: Path, stored: Any
) -> None:
    """SQLite 는 TEXT · BLOB 종가를 `close > 0` 에서 남긴다(검토 F2). 기존 흐름 읽기와 같은 규칙이면 모순이 아니다."""
    from app.market_data_store import fetch_recent_price_rows
    from app.short_term_momentum import _window_return_pct

    db = tmp_path / "m.sqlite"
    _seed(db, "0229F0", [100.0 + i for i in range(60)], D)
    day = _days(60)[39]  # 21번째 최신 행(D-20 · MA20 창 밖)
    con = sqlite3.connect(db)
    con.execute(
        "UPDATE etf_daily_price SET close = ? WHERE ticker = ? AND date = ?",
        (stored, "0229F0", day),
    )
    con.commit()
    assert con.execute(
        "SELECT typeof(close) FROM etf_daily_price WHERE date = ?", (day,)
    ).fetchone()[0] in ("text", "blob")
    con.close()
    flow = fetch_recent_price_rows("0229F0", limit=21, db_path=db)  # 기존 거른 읽기
    series = [(r[0], r[1]) for r in reversed(flow)]
    item = {
        "price_dates": {
            "end_date": D,
            "start_date_5d": series[-6][0],
            "start_date_20d": series[-21][0],
        },
        "short_term_momentum": {
            f"return_{n}d_pct": _window_return_pct(series, n) for n in (5, 10, 20)
        },
    }
    ev = M.for_holding("0229F0", item, reference_date=D, kind="etf", db_path=db)
    assert ev.status == "ok"
    assert ev.ma20.status == "ok" and ev.ma60.status == "invalid_price"
    preview = [(d, c, v, src) for d, c, v, src in flow]
    cand = M.for_candidate("0229F0", {}, preview, db_path=db)
    assert cand.status == "ok" and cand.preview_rows_compared == 21


# ── 원문 배치 ───────────────────────────────────────────────────────────────


def test_lines_go_right_after_returns_line_or_at_the_end() -> None:
    ma = {"status": "not_etf"}
    added = M.moving_average_lines(ma)
    flow = ["변화율 5저장일 …", "단기 KODEX200 차이 …", "끝 줄"]
    assert _with_moving_average(flow, ma) == [flow[0], *added, *flow[1:]]
    cand = [
        "1개월 +1.00% · 3개월 +2.00%",
        "단기 흐름: 값 없음 — 저장 종가가 부족합니다(21개 필요).",
    ]
    assert _with_moving_average(cand, ma) == [*cand, *added]
    mismatch = holding_flow_lines(
        {"price_dates": {"comparison": "date_mismatch", "end_date": "2026-10-17"}}, D
    )
    assert _with_moving_average(mismatch, ma) == [*mismatch, *added]


# ── 실제 endpoint(보유 · 후보 · tmp DB) ──────────────────────────────────────


def _sql_avg(db: Path, ticker: str, d: str, n: int) -> float:
    con = sqlite3.connect(db)
    try:
        return con.execute(
            "SELECT avg(close) FROM (SELECT close FROM etf_daily_price WHERE ticker = ? "
            "AND date <= ? ORDER BY date DESC LIMIT ?)",
            (ticker, d, n),
        ).fetchone()[0]
    finally:
        con.close()


def _flow_section(text: str) -> list[str]:
    sec = next(
        s for s in text.split("\n\n") if s.startswith("[가격 흐름 · PC 저장 종가]")
    )
    return [ln[2:] for ln in sec.split("\n")[1:]]


@pytest.mark.parametrize("kind, ticker", [("holding", HELD_ETF), ("candidate", CAND)])
def test_endpoint_text_equals_field_and_independent_sql(
    seeded: TestClient, kind: str, ticker: str  # noqa: F811
) -> None:
    q = LIST_PARAMS if kind == "candidate" else {}
    body = seeded.post(
        PREVIEW, json={"target_kind": kind, "ticker": ticker, **q}
    ).json()
    assert body["status"] == "ok"
    ma = body["moving_average"]
    d = body["evidence_as_of"]["target_as_of_date"]
    assert ma["status"] == "ok" and ma["d"] == d
    db = api_market_topn.DEFAULT_DB_PATH
    for n, key in ((20, "ma20"), (60, "ma60")):
        assert math.isclose(ma[key]["value"], _sql_avg(db, ticker, d, n), rel_tol=1e-12)
        assert ma[key]["shown"] == intl_fixed(ma[key]["value"], 2)
    # 원문 세 줄 = 응답 선택 필드로 만든 줄 · 변화율 줄 바로 다음.
    flow = _flow_section(body["preview_text"])
    i = next(k for k, ln in enumerate(flow) if ln.startswith("변화율 "))
    assert flow[i + 1 : i + 4] == M.moving_average_lines(ma)  # noqa: E203
    assert f"(종가 {ma['close_shown']}원)" in flow[i + 2]
    expected_checked = (
        ["start_date_5d", "start_date_20d"]
        if kind == "holding"
        else [
            "start_date_5d",
            "start_date_10d",
            "start_date_20d",
        ]
    )
    assert ma["basis_checked"][: len(expected_checked)] == expected_checked
    if kind == "candidate":
        assert ma["preview_rows_compared"] == 21
    # 끝 = [AI에게 요청] 그대로 + [검토 질문] 3줄(줄마다 하나).
    secs = body["preview_text"].split("\n\n")
    assert secs[-2] == "[AI에게 요청]\n" + "\n".join(f"- {x}" for x in AI_REQUEST)
    assert secs[-1] == "[검토 질문]\n" + "\n".join(f"- {x}" for x in REVIEW_QUESTIONS)
    assert len(secs) == 10


def test_endpoint_existing_holding_flow_lines_unchanged(
    seeded: TestClient,  # noqa: F811
) -> None:
    ev = seeded.get("/holdings/market-evidence/latest").json()
    item = next(h for h in ev["holdings"] if h["ticker"] == HELD_ETF)
    body = seeded.post(
        PREVIEW, json={"target_kind": "holding", "ticker": HELD_ETF}
    ).json()
    flow = _flow_section(body["preview_text"])
    added = M.moving_average_lines(body["moving_average"])
    assert [ln for ln in flow if ln not in added] == holding_flow_lines(
        item, ev["price_basis"]["reference_date"]
    )


def test_endpoint_stock_is_out_of_scope(seeded: TestClient) -> None:  # noqa: F811
    body = seeded.post(PREVIEW, json={"target_kind": "holding", "ticker": STOCK}).json()
    assert body["moving_average"]["status"] == "not_etf"
    assert (
        "종목 이동평균: 대상 아님(개별 종목 · 이 관측은 ETF만)" in body["preview_text"]
    )


@pytest.mark.parametrize("ticker", [HELD_ETF, STOCK])
def test_endpoint_empty_classification_is_unknown_not_stock(
    seeded: TestClient, ticker: str  # noqa: F811
) -> None:
    """RESULT 판정 §2 · §5-1(F3) — 분류 자료가 비면 대상 · 상태 줄 · 이동평균이 모두 '구분 확인 불가'(같은 뜻)."""
    before = seeded.post(
        PREVIEW, json={"target_kind": "holding", "ticker": ticker}
    ).json()
    con = sqlite3.connect(api_market_topn.DEFAULT_DB_PATH)
    con.execute("DELETE FROM etf_master")
    con.commit()
    con.close()
    body = seeded.post(
        PREVIEW, json={"target_kind": "holding", "ticker": ticker}
    ).json()
    assert body["status"] == "ok"
    text = body["preview_text"]
    secs = text.split("\n\n")
    head = secs[0].split("\n")[1]
    # 종목명 · ticker 보존 · 구분만 확인 불가.
    assert head == before["preview_text"].split("\n\n")[0].split("\n")[1].replace(
        "(ETF)" if ticker == HELD_ETF else "(개별 종목)", "(구분 확인 불가)"
    )
    assert f"({ticker}) · 보유 종목(구분 확인 불가)" in head
    status = next(x for x in secs if x.startswith("[중복 · 자료 상태]"))
    assert status == (
        "[중복 · 자료 상태]\n- 구성종목 겹침 · NAV 괴리율: 확인 불가(ETF 구분 자료를 확인하지 못했습니다)"
    )
    assert body["moving_average"]["status"] == "etf_unknown"
    assert (
        "- 종목 이동평균: 확인 불가 — ETF 구분 자료를 확인하지 못했습니다(개별 종목으로 보지 않음)"
        in text
    )
    # 개별주로 확정하는 문구 · 대체 숫자 없음.
    assert "보유 종목(개별 종목)" not in text and "대상 아님(개별 종목)" not in text
    assert "NAV 괴리율 " not in text and "구성종목 겹침:" not in text
    # 분류와 무관한 가격 근거(흐름 · 거래량 · 흔들림)는 그대로.
    for title in ("[가격 흐름 · PC 저장 종가]", "[거래량]", "[가격 흔들림]"):
        old = next(
            x for x in before["preview_text"].split("\n\n") if x.startswith(title)
        )
        new_sec = next(x for x in secs if x.startswith(title))
        keep = [
            ln
            for ln in old.split("\n")
            if not ln.startswith("- 종목 이동평균")
            and not ln.startswith("- 표시값 기준 위치")
            and not ln.startswith("- 이동평균 계산 구간")
        ]
        assert [ln for ln in new_sec.split("\n") if ln in keep] == keep
    assert secs[-1].startswith("[검토 질문]") and len(secs) == 10


def test_endpoint_classification_read_failure_keeps_error_contract(
    seeded: TestClient, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    """RESULT 판정 §2 · §5-2 — 분류 읽기 실패(DB 오류)는 '자료 없음 = 확인 불가'와 합치지 않고 기존 오류 계약."""
    from app import decision_preview_sources as S

    def broken(*a: Any, **k: Any) -> None:
        raise sqlite3.OperationalError("no such table: etf_master")

    monkeypatch.setattr(S, "list_etf_tickers", broken)
    body = seeded.post(
        PREVIEW, json={"target_kind": "holding", "ticker": HELD_ETF}
    ).json()
    assert body["status"] == "error" and body.get("preview_text") is None
    assert (
        body["message"] == "판단 근거 미리보기를 생성하지 못했습니다. 다시 시도하세요."
    )


def test_old_bundle_without_class_keeps_existing_labels(tmp_path: Path) -> None:
    """분류 필드가 없는 묶음(예전 형태)은 기존 is_etf 그대로 — 정상 ETF · 개별주 글 불변."""
    from app.decision_draft_preview_service import build_preview_text

    for is_etf, label, status in (
        (True, "보유 종목(ETF)", None),
        (
            False,
            "보유 종목(개별 종목)",
            "- 구성종목 겹침 · NAV 괴리율: 대상 아님(개별 종목)",
        ),
    ):
        ev = {
            "ticker": "0015K0",
            "name": "시험 종목",
            "market_weight_pct": 1.0,
            "pnl_rate_pct": -2.0,
            "bundle": {"item": {}, "is_etf": is_etf, "reference_date": None},
        }
        r = build_preview_text(
            target_kind="holding",
            ticker="0015K0",
            target_evidence=ev,
            db_path=tmp_path / "m.sqlite",
        )
        assert r.status == "ok" and label in r.preview_text
        assert "구분 확인 불가" not in r.preview_text
        if status:
            assert status in r.preview_text


@pytest.mark.parametrize("kind, ticker", [("holding", HELD_ETF), ("candidate", CAND)])
def test_endpoint_change_between_reads_is_unconfirmed(
    seeded: TestClient,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
    ticker: str,
) -> None:
    """앞선 읽기 뒤 · 이동평균 읽기 전에 같은 D 종가가 정정된 경우(읽는 사이 변경 재현)."""
    real = M._read_rows

    def changed(tk: str, d: str, db_path: Path) -> list[PriceRow]:
        con = sqlite3.connect(db_path)
        con.execute(
            "UPDATE etf_daily_price SET close = close + 1 WHERE ticker = ? AND date = ?",
            (tk, d),
        )
        con.commit()
        con.close()
        return real(tk, d, db_path)

    monkeypatch.setattr(M, "_read_rows", changed)
    q = LIST_PARAMS if kind == "candidate" else {}
    body = seeded.post(
        PREVIEW, json={"target_kind": kind, "ticker": ticker, **q}
    ).json()
    assert body["status"] == "ok"
    assert body["moving_average"]["status"] == "basis_mismatch"
    assert "가격 근거가 앞서 읽은 값과 다릅니다" in body["preview_text"]
    assert "MA20" not in body["preview_text"]


@pytest.mark.parametrize("kind, ticker", [("holding", HELD_ETF), ("candidate", CAND)])
def test_endpoint_unreadable_old_close_keeps_ma20_and_preview(
    seeded: TestClient,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
    ticker: str,
) -> None:
    """검증자 r1 재현 — 앞선 읽기 뒤 55번째 과거 행(MA60 창 · 기존 21행 밖)만 'broken' → MA60 사유 · 나머지 유지."""
    real = M._read_rows

    def broken(tk: str, d: str, db_path: Path) -> list[PriceRow]:
        con = sqlite3.connect(db_path)
        day = con.execute(
            "SELECT date FROM etf_daily_price WHERE ticker = ? AND date <= ? "
            "ORDER BY date DESC LIMIT 1 OFFSET 54",
            (tk, d),
        ).fetchone()[0]
        con.execute(
            "UPDATE etf_daily_price SET close = 'broken' WHERE ticker = ? AND date = ?",
            (tk, day),
        )
        con.commit()
        con.close()
        return real(tk, d, db_path)

    monkeypatch.setattr(M, "_read_rows", broken)
    q = LIST_PARAMS if kind == "candidate" else {}
    body = seeded.post(
        PREVIEW, json={"target_kind": kind, "ticker": ticker, **q}
    ).json()
    assert body["status"] == "ok"
    ma = body["moving_average"]
    assert ma["status"] == "ok"
    assert (ma["ma20"]["status"], ma["ma60"]["status"]) == ("ok", "invalid_price")
    assert "MA60 계산 불가(가격 확인 필요)" in body["preview_text"]
    assert body["preview_text"].split("\n\n")[-1].startswith("[검토 질문]")


def test_endpoint_db_read_failure_keeps_error_contract(
    seeded: TestClient, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    def broken(*a: Any, **k: Any) -> None:
        raise sqlite3.OperationalError("disk I/O error")

    monkeypatch.setattr(M, "_read_rows", broken)
    for kind, ticker, q in (
        ("holding", HELD_ETF, {}),
        ("candidate", CAND, LIST_PARAMS),
    ):
        body = seeded.post(
            PREVIEW, json={"target_kind": kind, "ticker": ticker, **q}
        ).json()
        assert body["status"] == "error" and body.get("moving_average") is None
        assert (
            body["message"]
            == "판단 근거 미리보기를 생성하지 못했습니다. 다시 시도하세요."
        )


def test_endpoint_same_ticker_two_accounts(seeded: TestClient) -> None:  # noqa: F811
    from app.api_decision_draft_preview import _aggregate_enriched_by_ticker

    before = seeded.post(
        PREVIEW, json={"target_kind": "holding", "ticker": HELD_ETF}
    ).json()
    payload = [
        {
            "ticker": HELD_ETF,
            "name": "보유 반도체 ETF",
            "quantity": 3,
            "avg_buy_price": 50,
        },
        {
            "ticker": HELD_ETF,
            "name": "보유 반도체 ETF",
            "quantity": 2,
            "avg_buy_price": 40,
            "account_group": "연금저축",
        },
        {"ticker": STOCK, "name": "삼성전자", "quantity": 1, "avg_buy_price": 60},
    ]
    rev = seeded.get("/holdings").json()["revision"]
    res = seeded.put("/holdings", json={"holdings": payload, "revision": rev})
    assert res.status_code == 200, res.text
    body = seeded.post(
        PREVIEW, json={"target_kind": "holding", "ticker": HELD_ETF}
    ).json()
    # 관측은 종목 하나 · 계좌 수와 무관하게 같다.
    assert body["moving_average"] == before["moving_average"]
    assert body["preview_text"].count("- 종목 이동평균:") == 1
    # 평가비중 · 손익 = 기존 종목 합산 그대로(이동평균이 바꾸지 않음).
    from app import market_cache
    from app.holdings import load as load_holdings
    from app.holdings_enrich import enrich_holdings

    hs = load_holdings()
    quotes = market_cache.get_all()
    agg = {
        a["ticker"]: a
        for a in _aggregate_enriched_by_ticker(
            enrich_holdings(
                hs, {h.ticker: quotes[h.ticker] for h in hs if h.ticker in quotes}
            )
        )
    }[HELD_ETF]
    from app.decision_preview_lines import fmt_pct

    assert (
        f"평가비중 {fmt_pct(agg['market_weight_pct'], plus_zero=True)} · "
        f"손익률 {fmt_pct(agg['pnl_rate_pct'], plus_zero=True)}"
    ) in body["preview_text"]
