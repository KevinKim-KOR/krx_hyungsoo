"""POC3-02D-OPS-03 — S&P500 기대 완료 세션(NYSE) · 거래일 달력 준비 상태.

설계자 PLAN 판정(2026-09-29) 확정 계약 11 · 설계자 판정 STEP 9 · 검증 시나리오 8(미국
휴장일). 휴장 CSV 는 저장소 파일(`state/market_meta/nyse_holidays_YYYY.csv`)을 **읽기만**
하고, 나머지는 `tmp_path` 다. 외부 조회 0건 · 라이브 DB · state 쓰기 없음.
"""

from __future__ import annotations

import csv
import shutil
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from app import us_trading_calendar as uc
from app.market_benchmark_store import upsert_benchmark_prices
from app.three_push_runtime import runner_market_briefing as mb

KST = timezone(timedelta(hours=9))
REPO_META = Path(__file__).resolve().parents[1] / "state" / "market_meta"

# NYSE 공식 표(https://www.nyse.com/markets/hours-calendars · 2026-09-29 17:05Z 조회)를
# 손으로 옮긴 기대값 — 저장소 CSV 가 이 표와 같아야 한다.
OFFICIAL_HOLIDAYS = {
    2026: [
        "2026-01-01",
        "2026-01-19",
        "2026-02-16",
        "2026-04-03",
        "2026-05-25",
        "2026-06-19",
        "2026-07-03",
        "2026-09-07",
        "2026-11-26",
        "2026-12-25",
    ],
    2027: [
        "2027-01-01",
        "2027-01-18",
        "2027-02-15",
        "2027-03-26",
        "2027-05-31",
        "2027-06-18",
        "2027-07-05",
        "2027-09-06",
        "2027-11-25",
        "2027-12-24",
    ],
}
OFFICIAL_EARLY = {2026: ["2026-11-27", "2026-12-24"], 2027: ["2027-11-26"]}


def _kst(text: str) -> datetime:
    return datetime.fromisoformat(text).replace(tzinfo=KST)


@pytest.fixture
def cal_dir(tmp_path: Path) -> Path:
    """저장소 휴장 CSV 사본(2026 · 2027)만 둔 폴더."""
    d = tmp_path / "meta"
    d.mkdir()
    for y in (2026, 2027):
        shutil.copy(REPO_META / f"nyse_holidays_{y}.csv", d)
    return d


# ── 저장소 CSV — 출처 · 내용 (확정 계약 11) ──────────────────────────────────


@pytest.mark.parametrize("year", [2026, 2027])
def test_repo_csv_matches_official_notice_and_records_provenance(year):
    path = REPO_META / f"nyse_holidays_{year}.csv"
    text = path.read_text(encoding="utf-8")
    head = [ln for ln in text.splitlines() if ln.startswith("#")]
    joined = "\n".join(head)
    assert "source_url: https://www.nyse.com/markets/hours-calendars" in joined
    assert "retrieved_at_utc: 2026-09-29T17:05:34Z" in joined
    assert "page_sha256: " in joined and "table_sha256: " in joined
    rows = list(
        csv.DictReader([ln for ln in text.splitlines() if not ln.startswith("#")])
    )
    got_h = sorted(r["date"] for r in rows if r["kind"] == uc.KIND_HOLIDAY)
    got_e = sorted(r["date"] for r in rows if r["kind"] == uc.KIND_EARLY_CLOSE)
    assert got_h == OFFICIAL_HOLIDAYS[year]
    assert got_e == OFFICIAL_EARLY[year]
    assert all(r["close_et"] == "13:00" for r in rows if r["kind"] == "early_close")
    parsed = uc.parse_year_file(path)
    assert parsed is not None and parsed.year == year


def test_loader_ignores_corrupt_file_and_falls_back_to_weekday(tmp_path):
    (tmp_path / "nyse_holidays_2026.csv").write_text(
        "date,kind,name,close_et\n2026-01-01,holiday,x,\n20260119,holiday,y,\n",
        encoding="utf-8",
    )
    (tmp_path / "nyse_holidays_2027.csv").write_text(
        "date,kind,name,close_et\n2026-07-03,holiday,wrong year,\n", encoding="utf-8"
    )
    cal = uc.load_nyse_calendar(tmp_path)
    assert not cal.covers(2026) and not cal.covers(2027)
    # 평일 fallback — 휴장일(07-03)도 세션으로 본다(보수적).
    assert cal.is_session(date(2026, 7, 3))


# ── 기대 완료 세션 (시나리오 8 · 서머타임 경계) ─────────────────────────────────


@pytest.mark.parametrize(
    "kst,expected",
    [
        ("2026-09-30T08:30:00", "2026-09-29"),  # 평일 · 서머타임(19:30 ET 전날)
        ("2026-09-28T08:30:00", "2026-09-25"),  # 월요일 → 금요일
        ("2026-09-08T08:30:00", "2026-09-04"),  # 09-07 Labor Day 휴장
        ("2026-11-27T08:30:00", "2026-11-25"),  # 11-26 Thanksgiving 휴장
        ("2026-12-28T08:30:00", "2026-12-24"),  # 12-25 휴장 · 12-24 조기 폐장
        ("2027-01-19T08:30:00", "2027-01-15"),  # 2027 파일 · 01-18 MLK 휴장
        ("2027-07-06T08:30:00", "2027-07-02"),  # 07-05 (07-04 대체) 휴장
    ],
)
def test_expected_session_weekday_monday_and_holidays(cal_dir, kst, expected):
    assert uc.expected_completed_session(_kst(kst), calendar_dir=cal_dir) == expected


@pytest.mark.parametrize(
    "kst,expected",
    [
        # 서머타임 끝(2026-11-01) 뒤 월요일: 11-03 05:30 KST = 11-02 15:30 EST (장중).
        ("2026-11-03T05:30:00", "2026-10-30"),
        ("2026-11-03T06:00:00", "2026-11-02"),  # = 16:00 EST 마감 시각
        # 서머타임 중: 10-27 05:30 KST = 10-26 16:30 EDT (마감 뒤).
        ("2026-10-27T05:30:00", "2026-10-26"),
        ("2026-10-27T04:59:00", "2026-10-23"),  # = 15:59 EDT (장중)
        # 서머타임 시작(2026-03-08) 뒤 월요일: 03-10 05:00 KST = 03-09 16:00 EDT.
        ("2026-03-10T05:00:00", "2026-03-09"),
        ("2026-03-10T04:59:00", "2026-03-06"),
        # 조기 폐장 13:00 ET — 11-28 03:00 KST = 11-27 13:00 EST.
        ("2026-11-28T03:00:00", "2026-11-27"),
        ("2026-11-28T02:59:00", "2026-11-25"),
    ],
)
def test_expected_session_dst_est_and_early_close_boundaries(cal_dir, kst, expected):
    assert uc.expected_completed_session(_kst(kst), calendar_dir=cal_dir) == expected


def test_missing_year_uses_weekday_fallback_conservatively(cal_dir):
    """2028 파일 없음 — 01-17(MLK) 도 세션으로 본다 → 금요일 값은 정상이 아니다."""
    now = _kst("2028-01-18T08:30:00")
    assert uc.expected_completed_session(now, calendar_dir=cal_dir) == "2028-01-17"
    chk = uc.session_check("2028-01-14", "2028-01-13", now=now, calendar_dir=cal_dir)
    assert chk["fresh"] is False
    assert chk["decided_by"] == uc.DECIDED_BY_WEEKDAY


def test_naive_now_is_read_as_kst(cal_dir):
    """KST 04:30 = 뉴욕 09-29 15:30(마감 전) → 09-28. UTC 로 읽으면 뉴욕 09-30 00:30 → 09-29.

    08:30 은 두 해석이 같은 답(09-29)이라 구분하지 못했다(리뷰 L3 ⑥).
    """
    naive = datetime(2026, 9, 30, 4, 30)
    assert uc.expected_completed_session(naive, calendar_dir=cal_dir) == "2026-09-28"
    as_utc = naive.replace(tzinfo=timezone.utc)
    assert uc.expected_completed_session(as_utc, calendar_dir=cal_dir) == "2026-09-29"


def test_timezone_data_missing_is_not_fresh(cal_dir, monkeypatch):
    monkeypatch.setattr(uc, "_ny_zone", lambda: None)
    chk = uc.session_check(
        "2026-09-29",
        "2026-09-28",
        now=_kst("2026-09-30T08:30:00"),
        calendar_dir=cal_dir,
    )
    assert chk["fresh"] is False and chk["reason"] == "expected_session_unknown"


@pytest.mark.parametrize(
    "last,prev,fresh,reason",
    [
        ("2026-09-29", "2026-09-28", True, "ok"),
        ("2026-09-28", "2026-09-25", False, "last_session_not_expected"),  # 하루 늦음
        ("2026-09-29", "2026-09-25", False, "previous_session_mismatch"),  # 가운데 빠짐
        (None, None, False, "last_session_not_expected"),
    ],
)
def test_session_check_last_and_previous(cal_dir, last, prev, fresh, reason):
    chk = uc.session_check(
        last, prev, now=_kst("2026-09-30T08:30:00"), calendar_dir=cal_dir
    )
    assert (chk["fresh"], chk["reason"]) == (fresh, reason)
    assert chk["expected_session"] == "2026-09-29"


# ── 러너 S&P500 입력 (tmp 벤치마크 DB) ─────────────────────────────────────────


def _us500(db: Path, rows: list[tuple[str, float]]) -> None:
    upsert_benchmark_prices(
        benchmark_id=mb.SP500_BENCHMARK,
        benchmark_name="S&P500",
        rows=rows,
        source="test",
        db_path=db,
    )


def test_sp500_input_fresh_only_on_expected_session(tmp_path, cal_dir):
    db = tmp_path / "bm.sqlite"
    _us500(db, [("2026-09-03", 100.0), ("2026-09-04", 101.0)])
    diag: dict = {}
    # 09-08 08:30 KST — 09-07 Labor Day → 기대 = 09-04 → 정상.
    ret, asof, fresh = mb._sp500_input(
        "2026-09-08",
        now=_kst("2026-09-08T08:30:00"),
        calendar_dir=cal_dir,
        db_path=db,
        diag=diag,
    )
    assert (asof, fresh) == ("2026-09-04", True) and ret == pytest.approx(1.0)
    assert (
        diag["expected_session"] == "2026-09-04" and diag["decided_by"] == "nyse_file"
    )
    # 같은 저장 값 · 다음 날 09-09 08:30 — 기대 = 09-08 → 전망 없음(옛 `last < today` 는 통과).
    _, _, fresh2 = mb._sp500_input(
        "2026-09-09", now=_kst("2026-09-09T08:30:00"), calendar_dir=cal_dir, db_path=db
    )
    assert fresh2 is False


def test_runner_records_expected_session_and_asof(tmp_path, cal_dir, monkeypatch):
    """확정 계약 11 — 실행 기록에 `sp500_asof` · 기대 세션을 남긴다(러너 경로)."""
    import app.market_benchmark_store as bms
    from app.market_briefing import calendar as kcal

    # 국내 거래일 판정도 저장소 달력을 읽지 않게(평일 fallback).
    monkeypatch.setattr(kcal, "CALENDAR_DIR", cal_dir)
    monkeypatch.setattr(
        bms,
        "fetch_benchmark_history",
        lambda _bid, **_k: [("2026-09-28", 100.0), ("2026-09-29", 99.0)],
    )
    monkeypatch.setattr(mb, "_batch_failure", lambda *_a, **_k: [])
    record: dict = {}
    out = mb.assemble(
        record,
        push_kind=mb.PUSH_KIND,
        today_kst="2026-09-30",
        runtime_kst="2026-09-30T08:30:02+09:00",
        state_dir=tmp_path,
        meta_dir=cal_dir,
        db_path=tmp_path / "krx.sqlite",
    )
    assert record["sp500_asof"] == "2026-09-29"
    assert record["sp500_expected_session"] == "2026-09-29"
    assert record["sp500_fresh"] is True
    assert record["sp500_session_check"]["reason"] == "ok"
    assert record["outlook_state"] == "DOWN" and out.should_send


# ── 거래일 달력 준비 상태 (확정 계약 11) ──────────────────────────────────────


def _names(*pairs: tuple[str, int]) -> list[str]:
    return [uc.calendar_file_name(m, y) for m, y in pairs]


ALL_2026_2027 = _names(("KRX", 2026), ("NYSE", 2026), ("KRX", 2027), ("NYSE", 2027))
NO_KRX_2027 = _names(("KRX", 2026), ("NYSE", 2026), ("NYSE", 2027))


@pytest.mark.parametrize(
    "today,names,state,missing_next",
    [
        (date(2026, 10, 31), NO_KRX_2027, uc.READY_OK, ["KRX"]),
        (date(2026, 11, 1), NO_KRX_2027, uc.READY_DUE, ["KRX"]),
        (date(2026, 11, 30), NO_KRX_2027, uc.READY_DUE, ["KRX"]),
        (date(2026, 12, 1), NO_KRX_2027, uc.READY_WARN, ["KRX"]),
        (date(2026, 12, 1), ALL_2026_2027, uc.READY_OK, []),
    ],
)
def test_readiness_november_check_and_december_warning(
    today, names, state, missing_next
):
    r = uc.calendar_readiness_for_names(today, names)
    assert (r["state"], r["missing_next"]) == (state, missing_next)


def test_readiness_current_year_missing_warns_any_month():
    r = uc.calendar_readiness_for_names(
        date(2027, 3, 2), ALL_2026_2027[:2] + NO_KRX_2027
    )
    assert r["state"] == uc.READY_WARN and r["missing_current"] == ["KRX"]


def test_readiness_from_directory_reads_content(tmp_path, cal_dir):
    """배치는 파일을 읽는다 — 손상 파일은 없는 것과 같다."""
    shutil.copy(REPO_META / "krx_trading_days_2026.csv", cal_dir)
    r = uc.calendar_readiness_for_dir(date(2026, 12, 1), cal_dir)
    assert r["basis"] == "file_content"
    assert (r["state"], r["missing_current"], r["missing_next"]) == (
        uc.READY_WARN,
        [],
        ["KRX"],
    )
    (cal_dir / "krx_trading_days_2027.csv").write_text("date\n2027-01-04\n", "utf-8")
    (cal_dir / "nyse_holidays_2027.csv").write_text("broken\n", encoding="utf-8")
    r2 = uc.calendar_readiness_for_dir(date(2026, 12, 1), cal_dir)
    assert r2["missing_next"] == ["NYSE"]


def test_batch_state_records_calendar_readiness(batch, tmp_path):  # noqa: F811
    """08:10 배치 JSON 에 준비 상태가 남는다(MARKET_META_DIR 는 conftest 격리 폴더)."""
    import json

    from app.three_push_runtime import market_data_batch as mdb

    shutil.copy(REPO_META / "nyse_holidays_2026.csv", batch.MARKET_META_DIR)
    rec = batch.run(mode="run")
    saved = json.loads(mdb.MARKET_DATA_BATCH_STATE_PATH.read_text("utf-8"))
    assert rec["calendar_readiness"] == saved["calendar_readiness"]
    assert saved["calendar_readiness"]["checked_date"] == "2026-09-30"
    assert saved["calendar_readiness"]["missing_current"] == ["KRX"]
    assert saved["calendar_readiness"]["state"] == uc.READY_WARN


# ── PC 「OCI 운영·적용」 ① 상태 표 행 ────────────────────────────────────────


def _snap(monkeypatch, out: str, today: date):
    from app import oci_startup_status as oss

    monkeypatch.setattr(oss, "require_env", lambda _k: "oci-krx")
    monkeypatch.setattr(oss, "_ssh_read", lambda cmd: (True, out))
    monkeypatch.setattr(oss, "_today_kst", lambda: today)
    return oss.refresh_snapshot()


CRON = "holdings_briefing\nholdings_risk_alert\nmarket_briefing\n"


@pytest.mark.parametrize(
    "today,status,detail",
    [
        (
            date(2026, 9, 30),
            "SUCCESS",
            "2027년 파일 없음: 한국 — 11월 30일까지 준비",
        ),
        (
            date(2026, 11, 2),
            "SUCCESS",
            "2027년 파일 없음: 한국 — 11월 30일까지 준비 필요",
        ),
        (date(2026, 12, 1), "STALE", "2027년 파일 없음: 한국 — 준비 필요"),
    ],
)
def test_oci_status_calendar_row(monkeypatch, today, status, detail):
    listing = "\n".join(["krx_etf_basic_20260927.csv", *NO_KRX_2027])
    snap = _snap(monkeypatch, f"{CRON}###\n1\n1 1\n###\n{listing}", today)
    row = [j for j in snap.jobs if j.job == "trading_calendar"][0]
    assert (row.status, row.detail) == (status, detail)
    assert snap.overall == "OPERATING", "달력 행이 전체 운영 판정을 바꾸면 안 된다"


def test_oci_status_calendar_row_all_present_and_old_output(monkeypatch):
    snap = _snap(
        monkeypatch,
        f"{CRON}###\n1\n1 1\n###\n" + "\n".join(ALL_2026_2027),
        date(2026, 12, 1),
    )
    row = [j for j in snap.jobs if j.job == "trading_calendar"][0]
    assert (row.status, row.detail) == ("SUCCESS", "한국·미국 2026년·2027년 파일 있음")
    # 넷째 블록이 없는 옛 응답 — 모르는 것을 '없음' 으로 보이지 않는다(행 없음).
    old = _snap(monkeypatch, f"{CRON}###\n1\n1 1", date(2026, 12, 1))
    assert [j.job for j in old.jobs if j.job == "trading_calendar"] == []


def test_oci_status_current_year_missing(monkeypatch):
    snap = _snap(monkeypatch, f"{CRON}###\n1\n1 1\n###\n", date(2026, 9, 30))
    row = [j for j in snap.jobs if j.job == "trading_calendar"][0]
    assert row.status == "STALE"
    assert row.detail.startswith(
        "2026년 파일 없음: 한국·미국 — 평일 기준으로 대신 판정 중"
    )


from tests.test_poc3_02d_ops03_krx_batch_stages import batch  # noqa: E402,F401
