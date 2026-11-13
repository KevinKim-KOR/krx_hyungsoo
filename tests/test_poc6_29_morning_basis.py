"""POC6-29 보완 2차 — 아침 요약 기준(`GET /market/morning-basis`) · 수급 5거래일(`GET /market/short-flows`).

PLAN §10-1 · §10-3 · §10-5 · S 판정 §1 · §3 · Q-S3 · Q-S4. 전부 tmp 시장 DB · tmp 보관소 · 고정 시각(라이브 DB 0).
기준 시각 = 2026-10-30(금) 09:30 KST → 아침 기준일 = 10/29(목 · 거래일 달력).
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import market_refresh_service as svc
from app import pc_morning_basis as mb
from app import pc_prevday_fill as pf
from app import pc_short_flows as sf
from app import supply_fx_oil_store as st
from app.api import app
from app.market_benchmark_store import KOSPI_SOURCE, upsert_benchmark_prices
from app.market_data_store import init_db
from app.market_regime import (
    compute_market_context,
    compute_regime_streak,
    kodex200_return_dates,
)
from app.supply_fx_oil_context import _trend
from tests.test_poc6_17_flow_import import _run

NOW = datetime(2026, 10, 30, 0, 30, tzinfo=timezone.utc)  # 10/30 09:30 KST
EXPECTED = "2026-10-29"
AFTER_CLOSE = "T07:00:00Z"  # 16:00 KST
INTRADAY = "T03:00:00Z"  # 12:00 KST


def _weekdays(start: str, end: str) -> list[str]:
    d, e, out = date.fromisoformat(start), date.fromisoformat(end), []
    while d <= e:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def _seed(
    tmp: Path,
    *,
    kodex_last: str = EXPECTED,
    kodex_first: str = "2026-06-01",
    expected_fetch: str = AFTER_CLOSE,
    today_row: bool = True,
    kospi_last: str = EXPECTED,
    flows_last: str = EXPECTED,
    vix_last: str = EXPECTED,
    fx_last: str = EXPECTED,
) -> Path:
    db = tmp / "market_data.sqlite"
    init_db(db)
    days = _weekdays(kodex_first, kodex_last)
    # 기준일 행의 저장 시각 — 'T..' 는 그 날짜에 붙이고, 날짜로 시작하면 그 값 그대로(날짜보다 앞선 시각 등)
    exp_at = (
        expected_fetch if expected_fetch[:2] == "20" else f"{EXPECTED}{expected_fetch}"
    )
    rows = [
        (
            "069500",
            d,
            None,
            None,
            None,
            100000.0 - i * 100,
            1000,
            None,
            "TEST",
            exp_at if d == EXPECTED else f"{d}{AFTER_CLOSE}",
        )
        for i, d in enumerate(days)
    ]
    if today_row:
        rows.append(
            (
                "069500",
                "2026-10-30",
                None,
                None,
                None,
                12345.0,
                1,
                None,
                "TEST",
                "2026-10-30T00:20:00Z",
            )
        )
    con = sqlite3.connect(db)
    con.executemany("INSERT INTO etf_daily_price VALUES (?,?,?,?,?,?,?,?,?,?)", rows)
    con.commit()
    con.close()
    for bid, last in (("KOSPI", kospi_last), ("VIX", vix_last)):
        upsert_benchmark_prices(
            benchmark_id=bid,
            benchmark_name=bid,
            rows=[(d, 5000.0) for d in _weekdays("2026-09-01", last)],
            source=KOSPI_SOURCE if bid == "KOSPI" else "TEST",
            db_path=db,
        )
    st.init_market_flow_tables(db)
    st.upsert_investor_flows(
        rows=[
            (d, inv, 100_000_000)
            for d in _weekdays("2026-09-01", flows_last)
            for inv in st.INVESTORS
        ],
        db_path=db,
    )
    con = sqlite3.connect(db)
    for sid in (st.USDKRW, st.WTI):
        u, p, b = st.MACRO_SERIES[sid]
        con.executemany(
            "INSERT INTO market_macro_daily VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (sid, d, 1000.0, u, p, b, "2026-10-30T00:10:00Z")
                for d in _weekdays("2026-09-01", fx_last)
            ],
        )
    con.commit()
    con.close()
    svc.reset_state_for_testing(db)
    return db


def _log(db: Path, run_id: str, source: str, ok: bool, err, at: str) -> None:
    con = sqlite3.connect(db)
    con.execute(
        "CREATE TABLE IF NOT EXISTS market_refresh_log (run_id TEXT, source TEXT, asof TEXT, "
        "attempted_count INTEGER, success_count INTEGER, fail_count INTEGER, "
        "runtime_seconds REAL, error_summary TEXT, created_at TEXT)"
    )
    con.execute(
        "INSERT INTO market_refresh_log (run_id, source, asof, attempted_count, success_count, "
        "fail_count, runtime_seconds, error_summary, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (run_id, source, "x", 1, 1 if ok else 0, 0 if ok else 1, 0.0, err, at),
    )
    con.commit()
    con.close()


def _build(db: Path, root: Path | None = None) -> dict:
    return mb.build_morning_basis(
        db_path=db, now=NOW, evidence_root=root or db.parent / "evidence"
    )


def _item(body: dict, key: str) -> dict:
    return next(i for i in body["items"] if i["key"] == key)


# ── 기준일 · 필수 3 · 아침 판정 ─────────────────────────────────────────────


def test_ready_when_required_meet_and_morning_regime_uses_expected_day(tmp_path):
    db = _seed(tmp_path)
    body = _build(db)
    assert body["status"] == "ok" and body["today"] == "2026-10-30"
    assert body["expected_date"] == EXPECTED
    assert body["ready"] is True and body["missing"] == []
    reg = body["morning_regime"]
    assert reg["status"] == "ok" and reg["basis_date"] == EXPECTED
    k = reg["context"]["kodex200"]
    # 오늘(10/30) 장중 행 12,345 가 아니라 기준일 10/29 마감 뒤 저장 행으로 계산
    last_close = 100000.0 - (len(_weekdays("2026-06-01", EXPECTED)) - 1) * 100
    assert k["close"] == last_close
    assert reg["context"]["regime_streak"]["streak_days"] >= 1
    kodex = _item(body, "kodex200")
    assert kodex["stored_date"] == "2026-10-30"  # 최신 행은 오늘
    assert kodex["basis_row"]["state"] == "after_close" and kodex["met"] is True


def test_latest_today_row_does_not_make_expected_day_ready(tmp_path):
    """S 판정 §3 — 최신 값이 오늘이라는 사실만으로 기준일 근거가 준비됐다고 표시하지 않는다."""
    db = _seed(tmp_path, expected_fetch=INTRADAY)
    body = _build(db)
    kodex = _item(body, "kodex200")
    assert kodex["met"] is False and kodex["basis_row"]["state"] == "intraday"
    assert body["ready"] is False and body["missing"] == ["kodex200"]
    assert "10/29 장중 저장값만 있음" in kodex["reason"]
    reg = body["morning_regime"]
    assert reg["status"] == "unconfirmed" and reg["context"] is None
    assert reg["reason"] == "KODEX 200 10/29 마감 가격 미확인"
    assert reg["basis_date"] == EXPECTED


# 검증자 F5 · F6 — 기준일 행의 저장 상태 × 판정 이력 조합(판정 순서: 행 없음 → 저장 상태 → 판정 계산).
@pytest.mark.parametrize(
    "fetch, first, met, ready, row_state, reason_has, regime_status, regime_reason",
    [
        ("T07:00:00Z", "2026-06-01", True, True, "after_close", None, "ok", None),
        (
            "T03:00:00Z",
            "2026-06-01",
            False,
            False,
            "intraday",
            "10/29 장중 저장값만 있음",
            "unconfirmed",
            "KODEX 200 10/29 마감 가격 미확인",
        ),
        (  # 시간대 없는 저장 시각(해석 불가) — '장중'으로 단정하지 않는다(F6)
            "T07:00:00",
            "2026-06-01",
            False,
            False,
            "unknown",
            "10/29 가격의 저장 시점 확인 불가",
            "unconfirmed",
            "KODEX 200 10/29 마감 가격 미확인",
        ),
        (  # 읽을 수 없는 저장 시각(F6)
            "Tbad",
            "2026-06-01",
            False,
            False,
            "unknown",
            "10/29 가격의 저장 시점 확인 불가",
            "unconfirmed",
            "KODEX 200 10/29 마감 가격 미확인",
        ),
        (  # 가격 날짜보다 앞선 저장 시각(F6)
            "2026-10-28T07:00:00Z",
            "2026-06-01",
            False,
            False,
            "unknown",
            "10/29 가격의 저장 시점 확인 불가",
            "unconfirmed",
            "KODEX 200 10/29 마감 가격 미확인",
        ),
        (  # 기준일 마감 가격은 있으나 판정 이력 부족(60거래일 + 1 미만) — 준비됨 아님(F5)
            "T07:00:00Z",
            "2026-09-01",
            False,
            False,
            "after_close",
            "10/29 마감 가격은 있으나 판정 근거 부족(저장 이력)",
            "unconfirmed",
            "KODEX 200 판정 근거 부족(저장 이력)",
        ),
    ],
)
def test_kodex_basis_row_state_and_history_decide_readiness(
    tmp_path,
    fetch,
    first,
    met,
    ready,
    row_state,
    reason_has,
    regime_status,
    regime_reason,
):
    db = _seed(tmp_path, expected_fetch=fetch, kodex_first=first)
    body = _build(db)
    kodex = _item(body, "kodex200")
    assert kodex["basis_row"]["state"] == row_state
    assert kodex["met"] is met
    assert body["ready"] is ready
    assert ("kodex200" in body["missing"]) is (not met)
    if reason_has is None:
        assert kodex["reason"] is None
    else:
        assert reason_has in kodex["reason"]
        assert kodex["reason"].startswith("KODEX 200 근거 미확인")
    if row_state != "intraday":
        assert "장중" not in (kodex["reason"] or "")
    reg = body["morning_regime"]
    assert reg["status"] == regime_status and reg["reason"] == regime_reason
    # 준비 상태 · 아침 판정이 같은 판단(준비됨이면 판정 있음 · 판정 없으면 준비됨 아님)
    assert body["ready"] is False or reg["status"] == "ok"


def test_kodex_read_once_and_all_three_come_from_that_read(tmp_path, monkeypatch):
    """검증자 F7 · F8 — KODEX 200 은 한 번만 읽고, 항목(기준일 행) · 아침 판정 · 당일 판정(+ 끝 행 저장 시점)이 모두 그
    결과에서 나온다(따로 읽은 저장본이 섞일 틈이 없음)."""
    db = _seed(tmp_path)
    real = mb._kodex_rows
    calls: list[int] = []

    def once(db_path):
        calls.append(1)
        return real(db_path)

    monkeypatch.setattr(mb, "_kodex_rows", once)
    body = _build(db)
    assert len(calls) == 1
    rows = real(db)
    k = _item(body, "kodex200")
    exp = next(r for r in rows if r[0] == EXPECTED)
    assert k["basis_row"]["close"] == exp[1]
    assert body["morning_regime"]["context"]["kodex200"]["close"] == exp[1]
    tr = body["today_regime"]
    assert tr["basis_row"]["date"] == rows[-1][0] == "2026-10-30"
    assert tr["context"]["kodex200"]["close"] == rows[-1][1] == tr["basis_row"]["close"]


def _same_as_market_regime(rows) -> dict:
    """시장 판정 응답과 같은 계산(같은 함수 · 같은 이력 · asof = 이력 끝일) — 비교 기준."""
    hist = [(d, c) for d, c, _at in rows]
    ctx = compute_market_context(asof=hist[-1][0], kodex200_history=hist)
    ctx["regime_streak"] = compute_regime_streak(hist)
    ctx["kodex200"].update(kodex200_return_dates(hist))
    return ctx


@pytest.mark.parametrize(
    "today_row, fetch, last, state, at_kst",
    [
        # 오늘(10/30) 09:20 장중 행이 끝 행
        (True, AFTER_CLOSE, "2026-10-30", "intraday", "2026-10-30T09:20:00+09:00"),
        # 끝 행 = 기준일 10/29 마감 뒤
        (False, AFTER_CLOSE, EXPECTED, "after_close", "2026-10-29T16:00:00+09:00"),
        # 끝 행 저장 시각 해석 불가 — 저장 시점 확인 필요(장중으로 단정 안 함)
        (False, "T07:00:00", EXPECTED, "unknown", None),
    ],
)
def test_today_regime_is_market_regime_with_its_own_end_row(
    tmp_path, today_row, fetch, last, state, at_kst
):
    db = _seed(tmp_path, today_row=today_row, expected_fetch=fetch)
    tr = _build(db)["today_regime"]
    assert tr["status"] == "ok" and tr["basis_date"] == last
    assert tr["basis_row"]["date"] == last
    assert tr["basis_row"]["state"] == state
    assert tr["basis_row"]["fetched_at_kst"] == at_kst
    want = _same_as_market_regime(mb._kodex_rows(db))
    got = tr["context"]
    for key in (
        "regime_code",
        "regime_label",
        "regime_score",
        "regime_reasons",
        "asof",
    ):
        assert got[key] == want[key]
    assert got["kodex200"] == want["kodex200"]
    assert got["regime_streak"] == want["regime_streak"]


@pytest.mark.parametrize(
    "first, rows_exist, reason",
    [
        ("2026-09-01", True, "KODEX 200 판정 근거 부족(저장 이력)"),
        (None, False, "KODEX 200 저장 가격 없음"),
    ],
)
def test_today_regime_unconfirmed(tmp_path, first, rows_exist, reason):
    db = _seed(tmp_path, kodex_first=first or "2026-06-01")
    if not rows_exist:
        con = sqlite3.connect(db)
        con.execute("DELETE FROM etf_daily_price WHERE ticker = '069500'")
        con.commit()
        con.close()
    tr = _build(db)["today_regime"]
    assert tr["status"] == "unconfirmed" and tr["context"] is None
    assert tr["reason"] == reason
    assert (tr["basis_row"] is not None) is rows_exist


def test_score_rule_is_the_existing_regime_constants(tmp_path):
    """설계자 V3 D1 — [?] 산식 설명이 읽는 경계값 = 기존 판정 상수 그대로(화면에 숫자를 따로 두지 않음) · 읽기 실패 응답에도."""
    from app import market_regime as mr

    want = {
        "return_20d_pct": mr.SCORE_THRESHOLD_20D_PCT,
        "return_60d_pct": mr.SCORE_THRESHOLD_60D_PCT,
        "bull_min": mr.REGIME_BULL_MIN_SCORE,
        "bear_max": mr.REGIME_BEAR_MAX_SCORE,
    }
    assert _build(_seed(tmp_path))["score_rule"] == want
    assert (
        mb.build_morning_basis(db_path=tmp_path / "no" / "x.sqlite", now=NOW)[
            "score_rule"
        ]
        == want
    )


def test_kodex_history_short_stays_unready_through_endpoint(tmp_path, monkeypatch):
    """F5 — 화면이 읽는 엔드포인트도 같은 판단(준비됨 아님 · 빠진 필수 = KODEX 200)."""
    db = _seed(tmp_path, kodex_first="2026-09-01")
    monkeypatch.setattr(mb, "DEFAULT_DB_PATH", db)
    real = mb.build_morning_basis
    monkeypatch.setattr(
        mb,
        "build_morning_basis",
        lambda **kw: real(**kw, now=NOW, evidence_root=tmp_path / "evidence"),
    )
    body = TestClient(app).get("/market/morning-basis").json()
    assert body["ready"] is False and body["missing"] == ["kodex200"]
    assert body["morning_regime"]["status"] == "unconfirmed"


@pytest.mark.parametrize("cooldown", [True, False])
def test_kodex_missing_row_shows_next_time_only_when_really_waiting(
    tmp_path, monkeypatch, cooldown
):
    db = _seed(tmp_path, kodex_last="2026-10-28", today_row=False)
    if cooldown:
        monkeypatch.setattr(
            svc._service,
            "last_success_at",
            datetime.now(timezone.utc) - timedelta(hours=1),
        )
    reason = _item(_build(db), "kodex200")["reason"]
    assert reason.startswith("KODEX 200 근거 미확인")
    assert ("ETF 전체 갱신 다음 " in reason) is cooldown
    assert reason.endswith("— [최신 자료 갱신]") is (not cooldown)


@pytest.mark.parametrize(
    "err, at, want",
    [
        (
            "api_key_missing",
            "2026-10-30T00:10:00Z",
            "설정 확인 필요(KRX 키 없음) · 09:10 확인",
        ),
        (
            "source_stale:as_of=2026-10-28,expected=2026-10-29,lag=1",
            "2026-10-29T22:50:00Z",
            "KRX 에 아직 기준일 자료가 없음 · 07:50 확인",
        ),
        ("fetch_failed:Timeout", "2026-10-30T00:10:00Z", "KRX 받기 실패 · 09:10 확인"),
        (
            "api_key_missing",
            "2026-10-29T06:00:00Z",
            mb.NOT_YET,
        ),  # 어제 시도 = 오늘은 아직
    ],
)
def test_kospi_reason_is_only_the_confirmed_last_attempt(tmp_path, err, at, want):
    db = _seed(tmp_path, kospi_last="2026-10-28")
    _log(db, "kospi-benchmark-x", KOSPI_SOURCE, False, err, at)
    it = _item(_build(db), "kospi")
    assert it["met"] is False and it["behind"] == 1
    assert it["reason"] == want
    assert it["last_attempt"]["via"] == "full"


def test_prevday_result_newer_than_full_log_wins(tmp_path):
    db = _seed(tmp_path, kospi_last="2026-10-28")
    _log(
        db,
        "kospi-benchmark-x",
        KOSPI_SOURCE,
        False,
        "api_key_missing",
        "2026-10-30T00:05:00Z",
    )
    pf.PREVDAY_FILE.parent.mkdir(parents=True, exist_ok=True)
    pf.PREVDAY_FILE.write_text(
        json.dumps(
            {
                "status": "done",
                "finished_at": "2026-10-30T09:20:00+09:00",
                "items": {
                    "kospi": {
                        "status": "unchanged",
                        "reason": "KRX 에 아직 기준일 자료가 없음",
                    }
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    it = _item(_build(db), "kospi")
    assert it["last_attempt"]["via"] == "prevday"
    assert it["reason"] == "KRX 에 아직 기준일 자료가 없음 · 09:20 확인"


def test_reason_keeps_confirmed_text_when_newer_attempt_has_none(tmp_path):
    """③ 이 반영은 했지만 기준일에 못 미친 기록(사유 없음)이 더 늦어도 같은 날 확인된 사유를 잃지 않는다."""
    db = _seed(tmp_path, flows_last="2026-10-28")
    _log(
        db,
        "market-flow-flowpull-prevday_x",
        st.FLOW_PULL_LOG_SOURCE,
        True,
        None,
        "2026-10-30T00:12:00Z",
    )
    _log(
        db,
        "market-flow-flowoci-prevday_x",
        st.FLOW_IMPORT_LOG_SOURCE,
        True,
        None,
        "2026-10-30T00:12:00Z",
    )
    pf.PREVDAY_FILE.parent.mkdir(parents=True, exist_ok=True)
    pf.PREVDAY_FILE.write_text(
        json.dumps(
            {
                "status": "done",
                "finished_at": "2026-10-30T09:13:00+09:00",
                "items": {"flows": {"status": "applied", "reason": None}},
            }
        ),
        encoding="utf-8",
    )
    it = _item(_build(db), "flows")
    assert it["last_attempt"]["via"] == "prevday"
    assert it["last_attempt"]["at"].endswith("09:13:00+09:00")
    # 더 늦은 ③ 기록에는 사유가 없다 → 같은 날 사유 있는 수급 연결 기록(09:12)을 쓴다('아직 받지 않음'으로 바뀌지 않음)
    assert it["reason"] != mb.NOT_YET
    assert it["reason"].endswith(" · 09:12 확인")
    assert "수급 10/28까지 사용 중" in it["reason"]


def test_flows_not_yet_names_copy_already_in_pc_store(tmp_path):
    db = _seed(tmp_path, flows_last="2026-10-28")
    root = tmp_path / "evidence"
    _run(
        root,
        datetime(2026, 10, 30, 0, 40, tzinfo=timezone.utc),
        ["2026-10-28", "2026-10-29"],
    )
    it = _item(_build(db, root), "flows")
    assert it["met"] is False
    assert it["reason"] == f"{mb.NOT_YET}(PC 보관소에 10/29까지 있음)"


def test_flows_reason_follows_today_flow_link(tmp_path):
    db = _seed(tmp_path, flows_last="2026-10-28")
    _log(
        db,
        "market-flow-flowpull-r",
        st.FLOW_PULL_LOG_SOURCE,
        False,
        "가져오기 실행 실패",
        "2026-10-30T00:12:00Z",
    )
    _log(
        db,
        "market-flow-flowoci-r",
        st.FLOW_IMPORT_LOG_SOURCE,
        True,
        None,
        "2026-10-30T00:12:00Z",
    )
    it = _item(_build(db), "flows")
    assert it["reason"].startswith("가져오기 실패(가져오기 실행 실패)")
    assert it["reason"].endswith(" · 09:12 확인")


def test_overseas_items_use_each_source_rule_and_are_not_required(tmp_path):
    db = _seed(tmp_path, vix_last="2026-10-27", fx_last="2026-10-28")
    body = _build(db)
    vix, fx, wti = (_item(body, k) for k in ("vix", "usdkrw", "wti"))
    assert not any(i["required"] for i in (vix, fx, wti))
    assert vix["state"] == "update_check" and vix["behind"] == 2 and vix["met"] is False
    assert fx["state"] == "late" and fx["behind"] == 1
    assert wti["state"] == "observed" and wti["expected_date"] is None
    assert body["ready"] is True  # 해외 늦음은 준비 상태를 막지 않는다
    assert fx["received_at"] == "2026-10-30T09:10:00+09:00"


def test_build_failure_is_invalid_not_ready(tmp_path, monkeypatch):
    db = _seed(tmp_path)

    def boom(_db):
        raise RuntimeError("x")

    monkeypatch.setattr(mb, "stored_dates", boom)
    body = _build(db)
    assert body["status"] == "invalid" and body["ready"] is False
    assert body["message"] == "아침 요약 기준을 읽지 못했습니다"


def test_endpoints_read_only_on_given_db(tmp_path, monkeypatch):
    db = _seed(tmp_path)
    before = db.read_bytes()
    monkeypatch.setattr(mb, "DEFAULT_DB_PATH", db)
    monkeypatch.setattr(sf, "DEFAULT_DB_PATH", db)
    monkeypatch.setattr(mb.evidence_store, "EVIDENCE_ROOT", tmp_path / "evidence")
    c = TestClient(app)
    body = c.get("/market/morning-basis").json()
    assert body["status"] == "ok" and body["expected_date"]
    flows = c.get("/market/short-flows").json()
    assert flows["status"] == "ok" and flows["end_date"] == EXPECTED
    assert db.read_bytes() == before


# ── 수급 5거래일(S 판정 §1) ─────────────────────────────────────────────────

TEN = _weekdays("2026-10-19", "2026-10-30")  # 10거래일(달력 · 이 기간 휴장 없음)


def _flow_db(tmp: Path, values: dict[str, dict[str, int]]) -> Path:
    db = tmp / "flows.sqlite"
    st.init_market_flow_tables(db)
    st.upsert_investor_flows(
        rows=[(d, inv, v) for inv, by in values.items() for d, v in by.items()],
        db_path=db,
    )
    return db


def test_short_flows_sums_last_five_and_compares_with_previous_five(tmp_path):
    fo = {d: (-100 if i >= 5 else -300) * 10**8 for i, d in enumerate(TEN)}
    ins = {d: 50 * 10**8 for d in TEN}
    ind = {d: (200 if i >= 5 else -200) * 10**8 for i, d in enumerate(TEN)}
    body = sf.build_short_flows(
        db_path=_flow_db(
            tmp_path, {"foreign": fo, "institution": ins, "individual": ind}
        )
    )
    assert body["end_date"] == "2026-10-30"
    by = {i["key"]: i for i in body["investors"]}
    assert [i["key"] for i in body["investors"]] == [
        "foreign",
        "institution",
        "individual",
    ]
    f = by["foreign"]
    assert f["last"] == {"date": "2026-10-30", "value": -100 * 10**8}
    assert f["recent5"] == {
        "sum": -500 * 10**8,
        "from": "2026-10-26",
        "to": "2026-10-30",
    }
    assert f["previous5"] == {
        "sum": -1500 * 10**8,
        "from": "2026-10-19",
        "to": "2026-10-23",
    }
    assert f["trend"] == "직전 5거래일보다 일평균 매도 감소" and f["note"] is None
    assert by["institution"]["trend"] == "직전 5거래일과 일평균 매수 같음"
    assert by["individual"]["trend"] == "순매도 → 순매수 전환"


def test_short_flows_missing_day_is_insufficient_not_skipped(tmp_path):
    fo = {d: -1 for d in TEN if d != "2026-10-27"}
    ins = {d: 1 for d in TEN if d != "2026-10-21"}
    body = sf.build_short_flows(
        db_path=_flow_db(tmp_path, {"foreign": fo, "institution": ins})
    )
    by = {i["key"]: i for i in body["investors"]}
    assert by["foreign"]["recent5"] is None and by["foreign"]["trend"] is None
    assert by["foreign"]["note"] == "5거래일 자료 부족"
    # 직전 5거래일만 빠지면 최근 합은 싣고 비교 문장만 없음
    assert (
        by["institution"]["recent5"]["sum"] == 5
        and by["institution"]["previous5"] is None
    )
    assert by["institution"]["trend"] is None and by["institution"]["note"] is None
    assert (
        by["individual"]["last"] is None
        and by["individual"]["note"] == "5거래일 자료 부족"
    )


def test_short_flows_empty_db(tmp_path):
    body = sf.build_short_flows(db_path=tmp_path / "none.sqlite")
    assert body == {
        "status": "empty",
        "message": "PC 수급 자료 없음",
        "end_date": None,
        "investors": [],
    }


def test_trend_default_keeps_the_twenty_day_wording():
    a, b = {"sum": -2, "avg": -1}, {"sum": -4, "avg": -2}
    assert _trend(a, b) == (
        "직전 20거래일보다 일평균 매도 감소",
        "일평균 매도 감소 (직전 20거래일 대비)",
    )
    assert _trend(a, b, 5)[0] == "직전 5거래일보다 일평균 매도 감소"


# ── 코스피 상세(kospi_detail · 설계자 지시 · 형수님 결정 2026-11-14 · POC6-29-1 결과서 §5) ───────────────
def _kospi_varied(db: Path, first: str, last: str) -> list[tuple[str, float]]:
    """KOSPI 공식 종가를 오르내리는 값으로 다시 쓴다(같은 날짜는 덮어씀) — 수익률이 0 이 아니게."""
    rows = [
        (d, 5000.0 + 13 * i + (i % 5) * 21 - (i % 7) * 17)
        for i, d in enumerate(_weekdays(first, last))
    ]
    upsert_benchmark_prices(
        benchmark_id="KOSPI",
        benchmark_name="KOSPI",
        rows=rows,
        source=KOSPI_SOURCE,
        db_path=db,
    )
    return rows


def _detail_at(db: Path, now: datetime) -> dict:
    return mb.build_morning_basis(
        db_path=db, now=now, evidence_root=db.parent / "evidence"
    )["kospi_detail"]


def test_kospi_detail_equals_market_regime_values_on_a_fresh_day(tmp_path):
    """정상일(KOSPI 기준일 = 기대 직전 거래일) — 20 · 60거래일 = 시장 판정 응답과 같은 값 · 1년 · 고점 대비 = 같은 함수 ·
    시작일은 저장 종가로 다시 계산해도 같은 수익률."""
    from app.market_regime import compute_kospi_position_metrics

    from app.market_data_store import fetch_price_history

    db = _seed(tmp_path)
    kospi = _kospi_varied(db, "2026-06-01", EXPECTED)
    det = _build(db)["kospi_detail"]
    # 비교 축 = 시장 판정 응답(`market_topn`)이 넘기는 그대로(`fetch_price_history`) — 상세가 읽는 축과 따로 읽음
    kodex = fetch_price_history("069500", db_path=db)
    ctx = compute_market_context(
        asof=kodex[-1][0],
        kodex200_history=kodex,
        kospi_history=kospi,
        kospi_today_kst="2026-10-30",
    )["kospi"]
    assert ctx["status"] == "ok"
    assert det["status"] == "ok" and det["as_of_date"] == EXPECTED
    assert det["r20"]["pct"] == ctx["return_20d_pct"]
    assert det["r60"]["pct"] == ctx["return_60d_pct"]
    pos = compute_kospi_position_metrics(kospi)
    assert det["return_1y_pct"] == pos["return_1y_pct"]
    assert det["high_52w_gap_pct"] == pos["high_52w_gap_pct"]
    close = dict(kospi)
    for key, n in (("r20", 20), ("r60", 60)):
        w = det[key]
        axis = [d for d, _c in kodex]
        assert w["end_date"] == EXPECTED
        assert axis.index(EXPECTED) - axis.index(w["start_date"]) == n
        assert w["pct"] == round(
            (close[EXPECTED] / close[w["start_date"]] - 1) * 100, 2
        )


@pytest.mark.parametrize(
    "now, kospi_last, expected",
    [
        # 토요일 10:00 KST — 기대 직전 거래일 10/30(금) · KRX 는 10/30 종가를 다음 영업일에 공개 → 저장 10/29
        (datetime(2026, 10, 31, 1, 0, tzinfo=timezone.utc), "2026-10-29", "2026-10-30"),
        # 평일 장 시작 전 07:00 KST — 기대 10/29 · 저장 10/28(10/29 종가는 08:00 공개)
        (datetime(2026, 10, 29, 22, 0, tzinfo=timezone.utc), "2026-10-28", EXPECTED),
    ],
)
def test_kospi_detail_readable_on_weekend_and_before_open(
    tmp_path, now, kospi_last, expected
):
    """시장 판정 응답은 기준일이 기대 직전 거래일이 아니면 값을 주지 않지만(엄격 규칙 그대로), 상세는 저장 끝 행 기준 값 ·
    실제 기간을 준다(저장값이 있으면 주말 · 장 시작 전에도 읽힘)."""
    db = _seed(tmp_path, kospi_last=kospi_last)
    kospi = _kospi_varied(db, "2026-06-01", kospi_last)
    body = mb.build_morning_basis(
        db_path=db, now=now, evidence_root=db.parent / "evidence"
    )
    assert body["expected_date"] == expected
    kodex = [(d, c) for d, c, _at in mb._kodex_rows(db)]
    ctx = compute_market_context(
        asof=kodex[-1][0],
        kodex200_history=kodex,
        kospi_history=kospi,
        kospi_today_kst=now.astimezone(timezone(timedelta(hours=9))).date().isoformat(),
    )["kospi"]
    assert ctx["status"] == "stale" and ctx.get("return_20d_pct") is None
    det = body["kospi_detail"]
    assert det["status"] == "ok" and det["as_of_date"] == kospi_last
    axis = [d for d, _c in kodex]
    close = dict(kospi)
    for key, n in (("r20", 20), ("r60", 60)):
        w = det[key]
        assert w["end_date"] == kospi_last
        assert axis.index(kospi_last) - axis.index(w["start_date"]) == n
        assert w["pct"] == round(
            (close[kospi_last] / close[w["start_date"]] - 1) * 100, 2
        )
    assert (
        det["return_1y_pct"] is None
    )  # 저장 이력이 1년 미만 — 대신 값 없음(0 으로 위장 안 함)


def test_kospi_detail_short_history_has_only_the_windows_it_can_compute(tmp_path):
    """KOSPI 저장이 09/01 부터라 60거래일 전 날짜에 값이 없으면 60거래일만 없음(더 오래된 값으로 대체하지 않음)."""
    det = _build(_seed(tmp_path))["kospi_detail"]
    assert det["status"] == "ok"
    assert det["r20"] is not None and det["r60"] is None


@pytest.mark.parametrize("case", ["no_rows", "no_table"])
def test_kospi_detail_without_kospi_keeps_the_response_ok(tmp_path, case):
    """KOSPI 를 아직 받지 않은 PC — 행이 없거나 표 자체가 없어도 응답 전체는 ok(항목 · 판정은 그대로) · 상세만 사유
    (독립 검토 2026-11-14 — 표가 없을 때 응답 전체가 '읽지 못함'이 되던 것을 같은 읽기 함수로 막음)."""
    db = _seed(tmp_path)
    con = sqlite3.connect(db)
    if case == "no_rows":
        con.execute(
            "DELETE FROM market_benchmark_daily_price WHERE benchmark_id = 'KOSPI'"
        )
    else:
        con.execute("DROP TABLE market_benchmark_daily_price")
    con.commit()
    con.close()
    body = _build(db)
    assert body["status"] == "ok" and body["today_regime"]["status"] == "ok"
    det = body["kospi_detail"]
    assert (
        det["status"] == "unavailable"
        and det["reason"] == "저장된 코스피 공식 종가 없음"
    )
    assert det["r20"] is None and det["r60"] is None and det["return_1y_pct"] is None


def test_kospi_detail_without_that_days_kodex_price_keeps_1y_and_explains(tmp_path):
    """그날 KODEX 200 저장 가격이 없으면(KOSPI 10/29 · KODEX 200 은 10/28 까지) 20 · 60거래일만 계산하지 않고 쉬운 말로
    사유 · 1년 · 고점 대비는 그대로(그 계산은 KODEX 200 날짜가 필요 없음 · 독립 검토 2026-11-14)."""
    from app.market_regime import compute_kospi_position_metrics

    db = _seed(tmp_path, kodex_last="2026-10-28", today_row=False)
    kospi = _kospi_varied(db, "2025-09-01", EXPECTED)
    det = _build(db)["kospi_detail"]
    assert det["status"] == "ok" and det["as_of_date"] == EXPECTED
    assert det["r20"] is None and det["r60"] is None
    assert (
        det["reason"]
        == "10/29 KODEX 200 저장 가격이 없어 20 · 60거래일은 계산하지 못했습니다"
    )
    pos = compute_kospi_position_metrics(kospi)
    assert det["return_1y_pct"] == pos["return_1y_pct"] is not None
    assert det["high_52w_gap_pct"] == pos["high_52w_gap_pct"] is not None


def test_kospi_detail_is_none_when_build_fails(tmp_path, monkeypatch):
    db = _seed(tmp_path)

    def boom(_db):
        raise RuntimeError("x")

    monkeypatch.setattr(mb, "_kospi_rows", boom)
    body = _build(db)
    assert body["status"] == "invalid" and body["kospi_detail"] is None
