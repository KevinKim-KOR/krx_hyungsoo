"""POC6-27 — 시장 흐름 자료별 최신성(`freshness` · 국내 T-1 대비 · WTI 관측일만).

계약 출처: POC6-27 PLAN V1 쟁점 2 · 설계자 PLAN 판정 §3 Q4 · §4(11/9 기대일 11/6 · 수급 · 원/달러 11/5 = 1거래일
늦음 · 국내 휴장 중 더 최근 원/달러 = 최신 · 평일 대체 기준 표시 · 날짜 깨짐 · 기대일 모름 = 기준 확인 필요 ·
WTI 에 VIX 마감 · 1평일 규칙 적용 안 함). 달력은 tmp 폴더(라이브 state 를 읽지 않음).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.market_freshness_rows import build_freshness, freshness_from_series
from app.supply_fx_oil_context import build_market_flow_context


def _calendar(tmp_path: Path, *, year: int = 2026, holidays=()) -> Path:
    d = tmp_path / "cal"
    d.mkdir(exist_ok=True)
    day, rows = date(year, 1, 1), ["date,source"]
    while day.year == year:
        iso = day.isoformat()
        if day.weekday() < 5 and iso not in holidays:
            rows.append(f"{iso},TEST")
        day += timedelta(days=1)
    (d / f"krx_trading_days_{year}.csv").write_text("\n".join(rows), encoding="utf-8")
    return d


def _items(fr):
    return {i["key"]: i for i in fr["items"]}


def test_case_1109_flows_one_day_late_usdkrw_fresh(tmp_path):
    cal = _calendar(tmp_path)
    fr = build_freshness(
        today_kst="2026-11-09",
        last_dates={"flows": "2026-11-05", "usdkrw": "2026-11-06", "wti": "2026-11-06"},
        calendar_dir=cal,
    )
    assert (fr["today_kst"], fr["expected_kr"], fr["expected_kr_basis"]) == (
        "2026-11-09",
        "2026-11-06",
        "calendar",
    )
    it = _items(fr)
    assert it["flows"] == {
        "key": "flows",
        "label": "외국인 수급",
        "last_date": "2026-11-05",
        "expected": "2026-11-06",
        "basis": "kr_t1",
        "state": "late",
        "behind": 1,
        "reason": "국내 직전 거래일 2026-11-06 대비 1거래일 늦음",
    }
    assert (it["usdkrw"]["state"], it["usdkrw"]["behind"], it["usdkrw"]["label"]) == (
        "fresh",
        None,
        "원/달러",
    )


def test_same_case_both_late_matches_1109_screen(tmp_path):
    fr = build_freshness(
        today_kst="2026-11-09",
        last_dates={"flows": "2026-11-05", "usdkrw": "2026-11-05", "wti": "2026-11-06"},
        calendar_dir=_calendar(tmp_path),
    )
    it = _items(fr)
    assert [it[k]["state"] for k in ("flows", "usdkrw")] == ["late", "late"]
    assert [it[k]["behind"] for k in ("flows", "usdkrw")] == [1, 1]


def test_holiday_skipped_in_expected_and_behind(tmp_path):
    # 11/6(금)을 국내 휴장으로 둔 달력 → 11/9 의 기대일 = 11/5
    cal = _calendar(tmp_path, holidays={"2026-11-06"})
    fr = build_freshness(
        today_kst="2026-11-09",
        last_dates={"flows": "2026-11-03", "usdkrw": "2026-11-06", "wti": None},
        calendar_dir=cal,
    )
    assert fr["expected_kr"] == "2026-11-05"
    it = _items(fr)
    # 11/4 · 11/5 두 거래일 늦음
    assert (it["flows"]["state"], it["flows"]["behind"]) == ("late", 2)
    # 국내 휴장 중 더 최근 원/달러(런던 날짜 11/6) = 최신
    assert it["usdkrw"]["state"] == "fresh"


def test_weekday_fallback_basis_when_year_not_covered(tmp_path):
    cal = _calendar(tmp_path, year=2026)  # 2027 파일 없음
    fr = build_freshness(
        today_kst="2027-03-10",
        last_dates={"flows": "2027-03-08", "usdkrw": "2027-03-09", "wti": None},
        calendar_dir=cal,
    )
    assert (fr["expected_kr"], fr["expected_kr_basis"]) == (
        "2027-03-09",
        "weekday_fallback",
    )
    it = _items(fr)
    assert (it["flows"]["state"], it["flows"]["behind"]) == ("late", 1)
    assert it["usdkrw"]["state"] == "fresh"


def test_no_calendar_dir_at_all_is_weekday_fallback(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    fr = build_freshness(
        today_kst="2026-11-09",
        last_dates={"flows": "2026-11-06", "usdkrw": None, "wti": None},
        calendar_dir=empty,
    )
    assert (fr["expected_kr"], fr["expected_kr_basis"]) == (
        "2026-11-06",
        "weekday_fallback",
    )
    assert _items(fr)["flows"]["state"] == "fresh"


@pytest.mark.parametrize(
    "last, reason",
    [
        (None, "자료 없음"),
        ("", "자료 없음"),
        ("20261105", "날짜 확인 불가"),
        ("2026-11-05junk", "날짜 확인 불가"),
        # 검증자 r1 F2 — 모양은 맞지만 달력에 없는 날짜(화면 쪽 결함과 같은 값 · 서버는 실제 날짜로 읽음)
        ("2026-13-01", "날짜 확인 불가"),
        ("2026-02-30", "날짜 확인 불가"),
    ],
)
def test_missing_or_broken_date_is_check(tmp_path, last, reason):
    fr = build_freshness(
        today_kst="2026-11-09",
        last_dates={"flows": last, "usdkrw": last, "wti": last},
        calendar_dir=_calendar(tmp_path),
    )
    it = _items(fr)
    for k in ("flows", "usdkrw"):
        assert (it[k]["state"], it[k]["reason"], it[k]["behind"]) == (
            "check",
            reason,
            None,
        )


def test_expected_unknown_is_check(tmp_path):
    fr = build_freshness(
        today_kst="not-a-date",
        last_dates={"flows": "2026-11-05", "usdkrw": "2026-11-05", "wti": "2026-11-05"},
        calendar_dir=_calendar(tmp_path),
    )
    assert fr["expected_kr"] is None and fr["expected_kr_basis"] is None
    it = _items(fr)
    assert it["flows"]["state"] == "check"
    assert it["flows"]["reason"] == "기대 기준일 확인 불가"


@pytest.mark.parametrize("wti", [None, "2020-01-02", "2026-11-06", "garbage"])
def test_wti_is_never_judged(tmp_path, wti):
    fr = build_freshness(
        today_kst="2026-11-09",
        last_dates={"flows": "2026-11-06", "usdkrw": "2026-11-06", "wti": wti},
        calendar_dir=_calendar(tmp_path),
    )
    assert _items(fr)["wti"] == {
        "key": "wti",
        "label": "WTI",
        "last_date": wti,
        "expected": None,
        "basis": "observed_only",
        "state": "observed",
        "behind": None,
        "reason": None,
    }


def test_from_series_uses_kst_date_and_last_points(tmp_path):
    # 11/8 23:30 UTC = 11/9 08:30 KST → 기대 11/6
    now = datetime(2026, 11, 8, 23, 30, tzinfo=timezone.utc)
    fr = freshness_from_series(
        now,
        "2026-11-05",
        [("2026-11-04", 1.0), ("2026-11-05", 2.0)],
        [],
        _calendar(tmp_path),
    )
    assert fr["today_kst"] == "2026-11-09" and fr["expected_kr"] == "2026-11-06"
    it = _items(fr)
    assert it["usdkrw"]["last_date"] == "2026-11-05" and it["wti"]["last_date"] is None


def test_context_carries_freshness_on_every_path(tmp_path):
    cal = _calendar(tmp_path)
    now = datetime(2026, 11, 9, 1, 0, tzinfo=timezone.utc)
    empty_db = tmp_path / "none.sqlite"
    out = build_market_flow_context(db_path=empty_db, now=now, calendar_dir=cal)
    assert out["D"] is None and not empty_db.exists()  # 이른 반환 경로 · 파일 안 만듦
    assert out["freshness"]["expected_kr"] == "2026-11-06"
    assert [i["state"] for i in out["freshness"]["items"]] == [
        "check",
        "check",
        "observed",
    ]
    from tests.test_poc6_27_flow_fields import _seed_case

    db = tmp_path / "m.sqlite"
    _seed_case(db)
    full = build_market_flow_context(db_path=db, now=now, calendar_dir=cal)
    it = _items(full["freshness"])
    # status[] 의 E 와 같은 값을 쓴다
    status = {s["key"]: s["E"] for s in full["status"]}
    assert it["flows"]["last_date"] == status["flows"] == "2026-11-05"
    assert it["usdkrw"]["last_date"] == status["usdkrw"]
    assert it["wti"]["last_date"] == status["wti"]
    assert (it["flows"]["state"], it["flows"]["behind"]) == ("late", 1)
