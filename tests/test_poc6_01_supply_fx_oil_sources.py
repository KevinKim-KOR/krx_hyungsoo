"""POC6-01 — 수집 쪽(Yahoo 일봉 어댑터 · 키움 ka10051 · 시장 DB 표 2개 · 갱신 단계 · 갱신 작업 연결).

모든 시험은 tmp DB · 가짜 전송만 쓴다(conftest 가 실제 Yahoo · 키움 호출과 라이브 DB 쓰기를 막는다).
계약 출처: POC5-28 설계 개정 3 · PLAN §9 · PLAN 판정 §4 · §7 · POC6-01 판정.
"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from app import market_refresh_service
from app import supply_fx_oil_refresh as rf
from app import supply_fx_oil_store as st
from app.kiwoom_investor_flow import (
    KiwoomAuthError,
    KiwoomClient,
    KiwoomFlowError,
    parse_eok,
)
from app.market_benchmark_store import upsert_benchmark_prices
from app.market_data_store import log_refresh
from app.market_topn_helpers import _latest_refresh_payload
from app.yahoo_daily_series import YahooSeriesError, fetch_completed_daily
from tests.test_market_vix_retry import _full, svc  # noqa: F401


def _ts(iso: str) -> int:
    return int(datetime.fromisoformat(iso).timestamp())


class _Resp:
    def __init__(self, body, status=200):
        self._b, self.status_code = body, status

    def json(self):
        if isinstance(self._b, Exception):
            raise self._b
        return self._b

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def _chart(tz, stamps, closes, today_start_iso):
    return {
        "chart": {
            "result": [
                {
                    "meta": {
                        "exchangeTimezoneName": tz,
                        "currentTradingPeriod": {
                            "regular": {"start": _ts(today_start_iso)}
                        },
                    },
                    "timestamp": [_ts(s) for s in stamps],
                    "indicators": {"quote": [{"close": closes}]},
                }
            ]
        }
    }


NOW = datetime(2026, 10, 20, 8, 0, tzinfo=timezone.utc)


# ── Yahoo 일봉 어댑터 ────────────────────────────────────────────────────────


def test_yahoo_dates_follow_provider_timezone_across_dst():
    """런던 자정 봉: 겨울 00:00Z = 그날 · 여름 23:00Z(전날) = 다음 날(일괄 +1 · 요일 맞추기 없음)."""
    body = _chart(
        "Europe/London",
        [
            "2026-01-12T00:00:00+00:00",
            "2026-01-16T00:00:00+00:00",
            "2026-07-12T23:00:00+00:00",
            "2026-07-16T23:00:00+00:00",
        ],
        [1455.2, 1468.8, 1498.5, 1478.8],
        "2026-10-19T23:00:00+00:00",
    )
    calls = []
    rows = fetch_completed_daily(
        "KRW=X",
        date(2026, 1, 1),
        now_utc=NOW,
        http_get=lambda url, **kw: calls.append((url, kw)) or _Resp(body),
    )
    assert rows == [
        ("2026-01-12", 1455.2),
        ("2026-01-16", 1468.8),
        ("2026-07-13", 1498.5),
        ("2026-07-17", 1478.8),
    ]
    assert calls[0][0].endswith("/KRW=X") and calls[0][1]["timeout"] == 20
    assert calls[0][1]["params"]["interval"] == "1d"


def test_yahoo_new_york_dates_and_negative_price_kept():
    body = _chart(
        "America/New_York",
        ["2020-04-20T04:00:00+00:00", "2026-01-12T05:00:00+00:00"],
        [-37.63, 59.5],
        "2026-10-20T04:00:00+00:00",
    )
    rows = fetch_completed_daily(
        "CL=F", date(2020, 1, 1), now_utc=NOW, http_get=lambda *a, **k: _Resp(body)
    )
    assert rows == [("2020-04-20", -37.63), ("2026-01-12", 59.5)]


def test_yahoo_excludes_in_progress_live_and_empty_rows():
    """공급자 '오늘 구간' 날짜 이상 · 현지 자정이 아닌 현재가 줄 · 종가 없는 줄은 저장하지 않는다."""
    body = _chart(
        "Europe/London",
        [
            "2026-10-15T23:00:00+00:00",  # 10/16 완료
            "2026-10-14T10:00:00+00:00",  # 지난 평일이어도 자정 아닌 줄은 일봉이 아님
            "2026-10-17T23:00:00+00:00",  # 10/18(일) 자정 봉 = 주말 날짜 = 완료 일봉 아님
            "2026-10-18T23:00:00+00:00",  # 10/19 완료
            "2026-10-19T23:00:00+00:00",  # 10/20 = 오늘 구간(진행 중)
            "2026-10-20T08:04:58+00:00",  # 현재가 줄(자정 아님)
        ],
        [1340.9, 9999.0, 8888.0, 1333.4, 1332.8, 1325.6],
        "2026-10-19T23:00:00+00:00",
    )
    rows = fetch_completed_daily(
        "KRW=X", date(2026, 10, 1), now_utc=NOW, http_get=lambda *a, **k: _Resp(body)
    )
    assert rows == [("2026-10-16", 1340.9), ("2026-10-19", 1333.4)]
    body["chart"]["result"][0]["indicators"]["quote"][0]["close"][3] = None
    rows = fetch_completed_daily(
        "KRW=X", date(2026, 10, 1), now_utc=NOW, http_get=lambda *a, **k: _Resp(body)
    )
    assert rows == [("2026-10-16", 1340.9)]  # 빈 종가 = 0 이 아니라 없음


@pytest.mark.parametrize(
    "mutate",
    [
        lambda b: b["chart"]["result"][0]["meta"].pop("exchangeTimezoneName"),
        lambda b: b["chart"]["result"][0]["meta"].pop("currentTradingPeriod"),
        lambda b: b["chart"]["result"][0]["meta"].update(
            exchangeTimezoneName="Nowhere/City"
        ),
        lambda b: b["chart"]["result"][0]["indicators"]["quote"][0]["close"].append(
            1.0
        ),
    ],
)
def test_yahoo_unknown_date_meaning_is_failure(mutate):
    body = _chart(
        "Europe/London",
        ["2026-10-15T23:00:00+00:00"],
        [1340.9],
        "2026-10-19T23:00:00+00:00",
    )
    mutate(body)
    with pytest.raises(YahooSeriesError):
        fetch_completed_daily(
            "KRW=X",
            date(2026, 10, 1),
            now_utc=NOW,
            http_get=lambda *a, **k: _Resp(body),
        )


def test_yahoo_duplicate_date_and_nan_are_failures():
    dup = _chart(
        "Europe/London",
        ["2026-10-15T23:00:00+00:00", "2026-10-15T23:00:00+00:00"],
        [1.0, 2.0],
        "2026-10-19T23:00:00+00:00",
    )
    with pytest.raises(YahooSeriesError):
        fetch_completed_daily(
            "KRW=X", date(2026, 10, 1), now_utc=NOW, http_get=lambda *a, **k: _Resp(dup)
        )
    nan = _chart(
        "Europe/London",
        ["2026-10-15T23:00:00+00:00"],
        [float("nan")],
        "2026-10-19T23:00:00+00:00",
    )
    with pytest.raises(YahooSeriesError):
        fetch_completed_daily(
            "KRW=X", date(2026, 10, 1), now_utc=NOW, http_get=lambda *a, **k: _Resp(nan)
        )


# ── 키움 ka10051 ─────────────────────────────────────────────────────────────

ROW = {
    "inds_cd": "001",
    "inds_nm": "종합(KOSPI)",
    "cur_prc": "+566805",
    "ind_netprps": "-5103",
    "frgnr_netprps": "+3214",
    "orgn_netprps": "-6402",
    "etc_corp_netprps": "+8302",
    "native_trmt_frgnr_netprps": "-9",
    "natn_netprps": "+0",
    "sc_netprps": "-9543",
    "insrnc_netprps": "+555",
    "invtrt_netprps": "+1886",
    "bank_netprps": "+82",
    "jnsinkm_netprps": "+63",
    "endw_netprps": "-1677",
    "samo_fund_netprps": "+2232",
}


class FakeKiwoom:
    """토큰 · ka10051 요청을 기록하는 가짜 전송."""

    def __init__(self, rows=None, token_body=None, sect=None):
        self.calls = []
        self.token_body = token_body or {
            "return_code": 0,
            "return_msg": "ok",
            "token": "TOK",
            "token_type": "Bearer",
            "expires_dt": "20261021202443",
        }
        self.sect = sect or (
            lambda body: {
                "return_code": 0,
                "inds_netprps": [
                    dict(ROW, inds_cd="002", inds_nm="대형주"),
                    rows or ROW,
                ],
            }
        )

    def __call__(self, url, json=None, headers=None, timeout=None):
        self.calls.append((url, json, headers, timeout))
        if url.endswith("/oauth2/token"):
            return _Resp(self.token_body)
        out = self.sect(json)
        return out if isinstance(out, _Resp) else _Resp(out)


def _client(fake, now=datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)):
    return KiwoomClient(
        "APPKEY-SECRET-1", "APPSECRET-SECRET-2", http_post=fake, now=lambda: now
    )


def test_kiwoom_kospi_row_parsed_to_won_and_request_contract():
    fake = FakeKiwoom()
    nets, idx = _client(fake).kospi_net_by_investor("2026-10-16")
    assert (
        nets["foreign"] == 3214 * 100_000_000
        and nets["individual"] == -5103 * 100_000_000
    )
    assert nets["institution"] == -6402 * 100_000_000 and nets["nation"] == 0
    assert set(nets) == set(st.INVESTORS) and idx == 5668.05
    token_call, sect_call = fake.calls
    assert token_call[1] == {
        "grant_type": "client_credentials",
        "appkey": "APPKEY-SECRET-1",
        "secretkey": "APPSECRET-SECRET-2",
    }
    assert sect_call[0].endswith("/api/dostk/sect")
    assert sect_call[1] == {
        "mrkt_tp": "0",
        "amt_qty_tp": "0",
        "base_dt": "20261016",
        "stex_tp": "1",
    }
    assert (
        sect_call[2]["api-id"] == "ka10051"
        and sect_call[2]["authorization"] == "Bearer TOK"
    )
    assert sect_call[3] == 15


def test_kiwoom_token_reused_until_close_to_expiry():
    fake = FakeKiwoom()
    c = _client(fake)
    c.kospi_net_by_investor("2026-10-16")
    c.kospi_net_by_investor("2026-10-15")
    assert [u for u, *_ in fake.calls].count("https://api.kiwoom.com/oauth2/token") == 1
    late = _client(
        fake, now=datetime(2026, 10, 21, 11, 21, tzinfo=timezone.utc)
    )  # 만료 4분 전(KST 20:21)
    late._token, late._expires = c._token, c._expires
    late.kospi_net_by_investor("2026-10-14")
    assert [u for u, *_ in fake.calls].count("https://api.kiwoom.com/oauth2/token") == 2


@pytest.mark.parametrize(
    "raw, want",
    [
        ("+8475", 8475 * 10**8),
        ("-0", 0),
        ("+0", 0),
        ("12", 12 * 10**8),
        (" -3 ", -3 * 10**8),
    ],
)
def test_parse_eok_values(raw, want):
    assert parse_eok(raw) == want


@pytest.mark.parametrize("raw", ["", None, "1.5", "abc", "+", "--3", 5])
def test_parse_eok_rejects_blank_and_non_numbers(raw):
    with pytest.raises(KiwoomFlowError):
        parse_eok(raw)


def test_kiwoom_failures_never_leak_keys():
    bad_token = FakeKiwoom(token_body={"return_code": 8010, "return_msg": "IP 다름"})
    with pytest.raises(KiwoomAuthError) as e:
        _client(bad_token).kospi_net_by_investor("2026-10-16")
    assert "SECRET" not in str(e.value) and "8010" in str(e.value)
    no_row = FakeKiwoom(
        sect=lambda body: {"return_code": 0, "inds_netprps": [dict(ROW, inds_cd="002")]}
    )
    with pytest.raises(KiwoomFlowError, match="001"):
        _client(no_row).kospi_net_by_investor("2026-10-16")
    err = FakeKiwoom(
        sect=lambda body: {
            "return_code": 1700,
            "return_msg": "허용된 API 요청 개수를 초과",
        }
    )
    with pytest.raises(KiwoomFlowError, match="1700"):
        _client(err).kospi_net_by_investor("2026-10-16")
    blank = FakeKiwoom(rows=dict(ROW, frgnr_netprps=""))
    with pytest.raises(KiwoomFlowError):
        _client(blank).kospi_net_by_investor("2026-10-16")


# ── 저장(시장 DB 표 2개) ───────────────────────────────────────────────────────


def _db(tmp_path: Path) -> Path:
    return tmp_path / "market_data.sqlite"


def test_macro_upsert_fixed_series_meta_and_correction(tmp_path):
    db = _db(tmp_path)
    unit, provider, basis = st.MACRO_SERIES[st.WTI]
    st.upsert_macro_daily(
        series_id=st.WTI,
        rows=[("2026-10-16", 101.41), ("2020-04-20", -37.63)],
        unit=unit,
        provider=provider,
        basis=basis,
        db_path=db,
    )
    st.upsert_macro_daily(
        series_id=st.WTI,
        rows=[("2026-10-16", 101.5)],
        unit=unit,
        provider=provider,
        basis=basis,
        db_path=db,
    )
    rows, at = st.read_macro_series(st.WTI, db_path=db)
    assert (
        rows == [("2020-04-20", -37.63), ("2026-10-16", 101.5)] and at
    )  # 정정 반영 · 음수 그대로
    with pytest.raises(ValueError):  # 다른 단위가 같은 계열 키로 = 실패
        st.upsert_macro_daily(
            series_id=st.WTI,
            rows=[("2026-10-17", 1.0)],
            unit="KRW/USD",
            provider=provider,
            basis=basis,
            db_path=db,
        )
    with pytest.raises(ValueError):
        st.upsert_macro_daily(
            series_id=st.WTI,
            rows=[("2026-10-17", float("inf"))],
            unit=unit,
            provider=provider,
            basis=basis,
            db_path=db,
        )
    assert (
        st.read_macro_series(st.WTI, db_path=db)[0] == rows
    )  # 실패한 저장은 아무것도 바꾸지 않음


def test_flow_upsert_null_totals_and_validation(tmp_path):
    db = _db(tmp_path)
    st.upsert_investor_flows(
        rows=[("2026-10-16", "foreign", 3214 * 10**8), ("2026-10-16", "individual", 0)],
        db_path=db,
    )
    st.upsert_investor_flows(rows=[("2026-10-16", "foreign", 3215 * 10**8)], db_path=db)
    flows, at = st.read_investor_flows(db_path=db)
    assert (
        flows
        == {
            "foreign": [("2026-10-16", 3215 * 10**8)],
            "individual": [("2026-10-16", 0)],
        }
        and at
    )
    con = sqlite3.connect(db)
    assert con.execute(
        "SELECT buy_value, sell_value, source FROM market_investor_flow_daily LIMIT 1"
    ).fetchone() == (None, None, st.FLOW_SOURCE)
    for bad in (
        [("2026-10-16", "retail", 1)],
        [("2026-10-16", "foreign", 1.5)],
        [("10/16", "foreign", 1)],
    ):
        with pytest.raises(ValueError):
            st.upsert_investor_flows(rows=bad, db_path=db)


def test_reads_open_read_only_connections(tmp_path, monkeypatch):
    """읽기(GET · 미리보기 · 갱신 전 확인)는 늘 `mode=ro` 로 연다(설계 · PLAN 읽기 계약)."""
    db = _db(tmp_path)
    st.init_market_flow_tables(db_path=db)
    seen = []
    real = sqlite3.connect

    def spy(*a, **k):
        seen.append((str(a[0]), k.get("uri")))
        return real(*a, **k)

    monkeypatch.setattr(st.sqlite3, "connect", spy)
    st.read_macro_series(st.USDKRW, db_path=db)
    st.read_investor_flows(db_path=db)
    st.read_benchmark_series("KOSPI", db_path=db)
    assert len(seen) == 3
    assert all(path.endswith("?mode=ro") and uri for path, uri in seen)


def test_reads_do_not_create_tables_or_files(tmp_path):
    db = _db(tmp_path)
    assert st.read_macro_series(st.USDKRW, db_path=db) == ([], None)
    assert not db.exists()
    sqlite3.connect(db).close()
    assert (
        st.read_investor_flows(db_path=db) == ({}, None)
        and st.read_benchmark_series("KOSPI", db_path=db) == []
    )
    con = sqlite3.connect(db)
    assert con.execute("SELECT count(*) FROM sqlite_master").fetchone()[0] == 0


# ── 갱신 단계 ────────────────────────────────────────────────────────────────


def _kospi(db, dates_closes):
    upsert_benchmark_prices(
        benchmark_id="KOSPI",
        benchmark_name="코스피",
        rows=dates_closes,
        source="TEST",
        db_path=db,
    )


def test_collection_start_uses_60_trading_days_before_new_year():
    days = [f"2025-{m:02d}-{d:02d}" for m in (9, 10, 11, 12) for d in range(1, 29)]
    assert rf.collection_start(days, date(2026, 10, 20)) == date.fromisoformat(
        days[-60]
    )
    assert rf.collection_start(days[-10:], date(2026, 10, 20)) == date(
        2025, 9, 23
    )  # 모자라면 1/1 의 100일 전


def test_fx_wti_first_then_overlap_90_days_and_isolated_failure(tmp_path):
    db = _db(tmp_path)
    seen = []

    def get(url, params=None, **kw):
        seen.append((url.rsplit("/", 1)[1], params["period1"]))
        if url.endswith("CL=F") and len(seen) > 2:
            raise RuntimeError("down")
        tz = "Europe/London" if url.endswith("KRW=X") else "America/New_York"
        stamp = (
            "2026-10-15T23:00:00+00:00"
            if tz == "Europe/London"
            else "2026-10-16T04:00:00+00:00"
        )
        return _Resp(_chart(tz, [stamp], [100.0], "2026-10-19T23:00:00+00:00"))

    start = date(2025, 9, 23)
    assert rf.refresh_fx_wti(db_path=db, now_utc=NOW, start=start, http_get=get) == []
    assert [s for s, _ in seen] == ["KRW=X", "CL=F"]
    assert all(
        p == _ts("2025-09-23T00:00:00+00:00") for _, p in seen
    )  # 처음 = 시작일부터
    assert rf.refresh_fx_wti(db_path=db, now_utc=NOW, start=start, http_get=get) == [
        "WTI"
    ]
    assert seen[2][1] == _ts("2026-07-22T00:00:00+00:00")  # 이후 = 최근 90일 겹쳐 받기
    assert st.read_macro_series(st.WTI, db_path=db)[0] == [
        ("2026-10-16", 100.0)
    ]  # 실패해도 기존 값 그대로


class FakeClient:
    def __init__(self, closes, fail=None, auth_fail_at=None):
        self.closes, self.fail, self.auth_fail_at, self.asked = (
            closes,
            fail or set(),
            auth_fail_at,
            [],
        )

    def kospi_net_by_investor(self, d):
        self.asked.append(d)
        if self.auth_fail_at == d:
            raise KiwoomAuthError("토큰 발급 실패(HTTP 200 · 코드 8010)")
        if d in self.fail:
            raise KiwoomFlowError(f"{d} 조회 실패")
        return {
            inv: (-100 if inv == "foreign" else 10) * 10**8 for inv in st.INVESTORS
        }, self.closes[d]


def _days(n, start="2026-08-03"):
    d, out = date.fromisoformat(start), []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d = date.fromordinal(d.toordinal() + 1)
    return out


def test_flows_first_collection_skips_today_and_checks_index(tmp_path):
    db = _db(tmp_path)
    days = _days(30) + ["2026-10-20"]
    closes = {d: 3000.0 + i for i, d in enumerate(days)}
    _kospi(db, list(closes.items()))
    client = FakeClient(
        dict(closes, **{days[5]: closes[days[5]] + 1})
    )  # 그날만 지수값이 다름
    sleeps = []
    msg = rf.refresh_investor_flows(
        db_path=db,
        now_utc=datetime(2026, 10, 20, 11, 0, tzinfo=timezone.utc),
        start=date(2026, 8, 1),
        client=client,
        sleep=sleeps.append,
    )
    assert (
        "2026-10-20" not in client.asked and client.asked == days[:-1][::-1]
    )  # 오늘 제외 · 처음 = 전부 · 최신 날짜부터
    assert msg == "투자자 수급(29/30일)" and len(sleeps) == 29
    stored = {d for d, _ in st.read_investor_flows(db_path=db)[0]["foreign"]}
    assert days[5] not in stored and len(stored) == 29  # 지수값 다른 날 = 저장 안 함


def test_flows_later_runs_fetch_missing_plus_last_20(tmp_path):
    db = _db(tmp_path)
    days = _days(45)
    closes = {d: 3000.0 for d in days}
    _kospi(db, list(closes.items()))
    st.upsert_investor_flows(
        rows=[(d, "foreign", 1) for d in days if d != days[3]], db_path=db
    )
    client = FakeClient(closes)
    msg = rf.refresh_investor_flows(
        db_path=db,
        now_utc=datetime(2026, 12, 1, tzinfo=timezone.utc),
        start=date(2026, 8, 1),
        client=client,
        sleep=lambda s: None,
    )
    assert msg is None and client.asked == sorted({days[3], *days[-20:]}, reverse=True)


def test_flows_auth_failure_stops_and_keeps_collected(tmp_path):
    db = _db(tmp_path)
    days = _days(10)
    closes = {d: 3000.0 for d in days}
    _kospi(db, list(closes.items()))
    client = FakeClient(closes, auth_fail_at=days[4])
    msg = rf.refresh_investor_flows(
        db_path=db,
        now_utc=datetime(2026, 12, 1, tzinfo=timezone.utc),
        start=date(2026, 8, 1),
        client=client,
        sleep=lambda s: None,
    )
    assert (
        msg == "투자자 수급(키움 인증 실패 — 등록 IP · 앱키 확인)"
        and client.asked == days[4:][::-1]
    )
    assert (
        len(st.read_investor_flows(db_path=db)[0]["foreign"]) == 5
    )  # 멈추기 전 받은 날 저장


def test_flows_three_consecutive_failures_stop(tmp_path):
    db = _db(tmp_path)
    days = _days(10)
    closes = {d: 3000.0 for d in days}
    _kospi(db, list(closes.items()))
    client = FakeClient(closes, fail=set(days[2:6]))
    msg = rf.refresh_investor_flows(
        db_path=db,
        now_utc=datetime(2026, 12, 1, tzinfo=timezone.utc),
        start=date(2026, 8, 1),
        client=client,
        sleep=lambda s: None,
    )
    assert client.asked == days[3:][::-1] and msg == "투자자 수급(4/10일)"


def test_flows_old_failing_dates_never_block_new_dates(tmp_path):
    """오래된 날짜가 계속 실패해도 새 날짜는 매 갱신 받는다(최신 날짜부터 · 검토 MED-1 재현)."""
    db = _db(tmp_path)
    days = _days(60)
    closes = {d: 3000.0 for d in days}
    _kospi(db, list(closes.items()))
    bad = set(days[3:6])
    for _ in range(3):
        rf.refresh_investor_flows(
            db_path=db,
            now_utc=datetime(2026, 12, 1, tzinfo=timezone.utc),
            start=date(2026, 8, 1),
            client=FakeClient(closes, fail=bad),
            sleep=lambda s: None,
        )
    stored = [d for d, _ in st.read_investor_flows(db_path=db)[0]["foreign"]]
    assert stored[-1] == days[-1] and set(days[6:]) <= set(stored)


def test_flows_time_budget_stops_and_reports(tmp_path):
    db = _db(tmp_path)
    days = _days(10)
    closes = {d: 3000.0 for d in days}
    _kospi(db, list(closes.items()))
    ticks = iter([0.0, 0.0, 10.0, rf.FLOW_TIME_BUDGET_S + 1])
    client = FakeClient(closes)
    msg = rf.refresh_investor_flows(
        db_path=db,
        now_utc=datetime(2026, 12, 1, tzinfo=timezone.utc),
        start=date(2026, 8, 1),
        client=client,
        sleep=lambda s: None,
        clock=lambda: next(ticks),
    )
    assert client.asked == [days[-1], days[-2]]
    assert msg == f"투자자 수급(시간 제한 {rf.FLOW_TIME_BUDGET_S}초 · 2/10일)"
    assert len(st.read_investor_flows(db_path=db)[0]["foreign"]) == 2


def test_flows_non_consecutive_failures_do_not_stop(tmp_path):
    db = _db(tmp_path)
    days = _days(10)
    closes = {d: 3000.0 for d in days}
    _kospi(db, list(closes.items()))
    client = FakeClient(closes, fail={days[1], days[3], days[5]})
    msg = rf.refresh_investor_flows(
        db_path=db,
        now_utc=datetime(2026, 12, 1, tzinfo=timezone.utc),
        start=date(2026, 8, 1),
        client=client,
        sleep=lambda s: None,
    )
    assert client.asked == days[::-1] and msg == "투자자 수급(7/10일)"


def test_fx_old_gap_beyond_overlap_is_refetched(tmp_path):
    """마지막 저장일이 90일보다 오래됐으면 그 다음 날부터 다시 받는다(구멍을 남기지 않음 · 검토 MED-3)."""
    db = _db(tmp_path)
    for sid in (st.USDKRW, st.WTI):
        u, p, b = st.MACRO_SERIES[sid]
        st.upsert_macro_daily(
            series_id=sid,
            rows=[("2026-05-01", 1.0)],
            unit=u,
            provider=p,
            basis=b,
            db_path=db,
        )
    seen = []

    def get(url, params=None, **kw):
        seen.append(params["period1"])
        return _Resp(_chart("Europe/London", [], [], "2026-10-19T23:00:00+00:00"))

    rf.refresh_fx_wti(db_path=db, now_utc=NOW, start=date(2025, 9, 23), http_get=get)
    assert seen == [_ts("2026-05-02T00:00:00+00:00")] * 2


def test_fx_failure_of_first_series_does_not_skip_wti(tmp_path):
    db = _db(tmp_path)

    def get(url, params=None, **kw):
        if url.endswith("KRW=X"):
            raise RuntimeError("down")
        return _Resp(
            _chart(
                "America/New_York",
                ["2026-10-16T04:00:00+00:00"],
                [87.5],
                "2026-10-19T23:00:00+00:00",
            )
        )

    assert rf.refresh_fx_wti(
        db_path=db, now_utc=NOW, start=date(2026, 10, 1), http_get=get
    ) == ["원/달러"]
    assert st.read_macro_series(st.WTI, db_path=db)[0] == [("2026-10-16", 87.5)]


def test_flows_without_credentials_is_a_message_not_a_crash(tmp_path, monkeypatch):
    monkeypatch.delenv("KIWOOM_APP_KEY", raising=False)
    monkeypatch.delenv("KIWOOM_APP_SECRET", raising=False)
    assert (
        rf.refresh_investor_flows(
            db_path=_db(tmp_path), now_utc=NOW, start=date(2026, 1, 1)
        )
        == "투자자 수급(키움 인증 정보 없음)"
    )


def test_step_logs_new_sources_and_latest_refresh_stays_kospi(tmp_path, monkeypatch):
    db = _db(tmp_path)
    _kospi(db, [(d, 3000.0) for d in _days(3)])
    log_refresh(
        run_id="kospi-benchmark-r1",
        source="KRX_OPEN_API/idx_kospi_dd_trd",
        asof="2026-10-16",
        attempted=1,
        success=1,
        fail=0,
        runtime_seconds=0.0,
        db_path=db,
    )
    monkeypatch.setattr(rf, "refresh_fx_wti", lambda **k: ["WTI"])
    monkeypatch.setattr(rf, "refresh_investor_flows", lambda **k: None)
    msg = rf.refresh_market_flow(
        db_path=db, now_utc=NOW, refresh_id="r1", asof="2026-10-16"
    )
    assert msg == "시장 흐름 자료 일부를 갱신하지 못했습니다(WTI)"
    rows = (
        sqlite3.connect(db)
        .execute(
            "SELECT source, success_count, fail_count, error_summary "
            "FROM market_refresh_log ORDER BY rowid"
        )
        .fetchall()
    )
    assert rows[1:] == [
        (st.FX_WTI_LOG_SOURCE, 0, 1, "WTI"),
        (st.FLOW_LOG_SOURCE, 1, 0, None),
    ]
    assert (
        _latest_refresh_payload(db)["refresh_id"] == "kospi-benchmark-r1"
    )  # 마지막 전체 갱신 = KOSPI 행 그대로


def test_step_exception_is_isolated_per_substep(tmp_path, monkeypatch):
    db = _db(tmp_path)

    def boom(**k):
        raise RuntimeError("x")

    monkeypatch.setattr(rf, "refresh_fx_wti", boom)
    monkeypatch.setattr(rf, "refresh_investor_flows", lambda **k: None)
    assert (
        rf.refresh_market_flow(
            db_path=db, now_utc=NOW, refresh_id="r2", asof="2026-10-16"
        )
        == "시장 흐름 자료 일부를 갱신하지 못했습니다(원/달러 · WTI(오류))"
    )


# ── 갱신 작업 연결 ────────────────────────────────────────────────────────────


def test_refresh_job_appends_flow_message_and_vix_only_flag_respects_it(
    request, monkeypatch
):
    rig = request.getfixturevalue(
        "svc"
    )  # 갱신 작업 고정 장치(VIX 다시 받기 시험) 재사용
    seen = {}
    monkeypatch.setattr(
        market_refresh_service,
        "sync_vix_retry_after_full_refresh",
        lambda db, **kw: seen.update(kw),
    )
    rig["vix"] = "시장 불안 지표(VIX)를 갱신하지 못했습니다"
    monkeypatch.setattr(
        market_refresh_service,
        "refresh_market_flow",
        lambda **kw: "시장 흐름 자료 일부를 갱신하지 못했습니다(WTI)",
    )
    _full(rig)
    state = market_refresh_service._service.state
    assert state.error_summary.endswith(
        "시장 불안 지표(VIX)를 갱신하지 못했습니다 · 시장 흐름 자료 일부를 갱신하지 못했습니다(WTI)"
    )
    assert (
        state.status == "completed" and seen["vix_only_failure"] is False
    )  # 시장 흐름도 실패 = 'VIX 만 실패' 아님
    monkeypatch.setattr(
        market_refresh_service, "refresh_market_flow", lambda **kw: None
    )
    market_refresh_service.reset_state_for_testing(db_path=rig["db"])
    _full(rig)
    assert seen["vix_only_failure"] is True


def test_refresh_job_survives_flow_step_exception(request, monkeypatch):
    rig = request.getfixturevalue("svc")

    def boom(**kw):
        raise RuntimeError("x")

    monkeypatch.setattr(market_refresh_service, "refresh_market_flow", boom)
    _full(rig)
    state = market_refresh_service._service.state
    assert (
        state.status == "completed"
        and state.error_summary == rf.MARKET_FLOW_STEP_FAILED_TEXT
    )
