"""ETF constituents API (POST refresh + GET analysis) 통합 테스트
(POC2 — 2026-05-27)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import api as api_module
from app import api_etf_constituents  # noqa: F401
from app.etf_constituents_store import (
    ConstituentRow,
    upsert_constituents,
)


@pytest.fixture
def api_client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TestClient:
    fake_db = tmp_path / "market_data.sqlite"
    # store / service 모두 DEFAULT_DB_PATH 를 모듈 attr 로 참조하므로 둘 다 patch.
    from app import etf_constituents_store as store
    from app import etf_constituents_service as service
    from app import etf_constituents_analysis as analysis

    monkeypatch.setattr(store, "DEFAULT_DB_PATH", fake_db)
    monkeypatch.setattr(service, "DEFAULT_DB_PATH", fake_db)
    monkeypatch.setattr(analysis, "DEFAULT_DB_PATH", fake_db)
    # service 의 default_fetcher 는 pykrx 호출 — 통합 테스트에서는 stub fetcher 주입.

    return TestClient(api_module.app)


def _seed_two_etfs_in_db(db: Path):
    # 2026-05-31 — service 의 cache check 가 NAVER_STOCK_SOURCE 매칭으로 교체
    # (Naver Stock ETFComponent 1차 채택). 시드 source 도 동일하게.
    from app.etf_constituents_fetcher import NAVER_STOCK_SOURCE as PYKRX_SOURCE

    upsert_constituents(
        [
            ConstituentRow(
                "139260", "2026-05-26", PYKRX_SOURCE, 1, "005930", "삼성전자", 25.0
            ),
            ConstituentRow(
                "139260",
                "2026-05-26",
                PYKRX_SOURCE,
                2,
                "000660",
                "SK하이닉스",
                20.0,
            ),
        ],
        db_path=db,
    )
    upsert_constituents(
        [
            ConstituentRow(
                "363580", "2026-05-26", PYKRX_SOURCE, 1, "005930", "삼성전자", 30.0
            ),
            ConstituentRow(
                "363580", "2026-05-26", PYKRX_SOURCE, 2, "035420", "NAVER", 12.0
            ),
        ],
        db_path=db,
    )


def test_post_refresh_rejects_more_than_10_tickers(api_client):
    res = api_client.post(
        "/market/constituents/refresh",
        json={
            "asof": "2026-05-26",
            "tickers": [f"00{i:04d}" for i in range(11)],
        },
    )
    body = res.json()
    assert res.status_code == 200
    assert body["status"] == "rejected"
    assert body["reason"] == "too_many_tickers"


def test_post_refresh_cache_only_when_data_exists(
    api_client, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    # 캐시 데이터 미리 시드.
    from app import etf_constituents_store as store

    _seed_two_etfs_in_db(store.DEFAULT_DB_PATH)

    # fetcher 가 호출되면 fail (캐시 우선 검증).
    def boom(ticker, asof, top_k):  # noqa: ARG001
        raise AssertionError("cache hit 인데 fetcher 가 호출됨")

    from app import etf_constituents_service as service

    monkeypatch.setattr(service, "default_fetcher", lambda: boom)

    res = api_client.post(
        "/market/constituents/refresh",
        json={
            "asof": "2026-05-26",
            "tickers": ["139260", "363580"],
        },
    )
    body = res.json()
    assert body["status"] == "ok"
    assert body["cached_count"] == 2
    assert body["fetched_count"] == 0


def test_get_analysis_returns_concentration_and_overlap(api_client):
    from app import etf_constituents_store as store

    _seed_two_etfs_in_db(store.DEFAULT_DB_PATH)

    res = api_client.get(
        "/market/constituents/analysis?tickers=139260,363580&asof=2026-05-26"
    )
    body = res.json()
    assert res.status_code == 200
    assert body["status"] == "ok"
    assert body["coverage"]["available_count"] == 2

    by_ticker = {c["etf_ticker"]: c for c in body["constituents"]}
    assert by_ticker["139260"]["status"] == "ok"
    assert by_ticker["139260"]["concentration"]["top1_weight_pct"] == 25.0
    assert by_ticker["139260"]["concentration"]["top3_weight_pct"] == 45.0

    assert len(body["overlap_matrix"]) == 1
    pair = body["overlap_matrix"][0]
    assert pair["common_count_top10"] == 1
    assert pair["weighted_overlap_pct"] == 25.0
    # repeated_core: 삼성전자가 2 ETF 에서 등장.
    assert len(body["repeated_core_holdings"]) == 1
    assert body["repeated_core_holdings"][0]["ticker"] == "005930"
    assert body["repeated_core_holdings"][0]["appears_in_etf_count"] == 2


def test_get_analysis_rejects_too_many_tickers(api_client):
    # POC6-31(판정 Q7) — DB 만 읽는 분석은 넘겨받는 후보 목록 상한(30)까지 받는다.
    csv = ",".join(f"00{i:04d}" for i in range(31))
    res = api_client.get(f"/market/constituents/analysis?tickers={csv}&asof=2026-05-26")
    assert res.status_code == 422
    csv11 = ",".join(f"00{i:04d}" for i in range(11))
    ok = api_client.get(
        f"/market/constituents/analysis?tickers={csv11}&asof=2026-05-26"
    )
    assert ok.status_code == 200 and ok.json()["coverage"]["requested_count"] == 11


def test_get_analysis_marks_unavailable_for_missing_ticker(api_client):
    res = api_client.get(
        "/market/constituents/analysis?tickers=UNKNOWN&asof=2026-05-26"
    )
    body = res.json()
    assert body["status"] == "ok"
    assert body["coverage"]["unavailable_count"] == 1
    assert body["constituents"][0]["status"] == "unavailable"


def test_get_analysis_asof_optional_uses_latest_when_missing(api_client):
    """asof 미지정 — POC6-31(판정 Q7) 부터 ETF마다 자기 마지막 구성일로 읽는다(예전: 가장 늦은 날짜 하나로
    모두 읽어 더 오래된 ETF 를 unavailable 로 처리). 맨 위 asof 는 가장 늦은 날짜(호환)."""
    from app import etf_constituents_store as store
    from app.etf_constituents_fetcher import NAVER_STOCK_SOURCE as SRC

    # 두 ETF 를 서로 다른 asof 로 시드.
    upsert_constituents(
        [ConstituentRow("139260", "2026-05-25", SRC, 1, "005930", "삼성전자", 25.0)],
        db_path=store.DEFAULT_DB_PATH,
    )
    upsert_constituents(
        [ConstituentRow("363580", "2026-05-26", SRC, 1, "035420", "NAVER", 12.0)],
        db_path=store.DEFAULT_DB_PATH,
    )
    res = api_client.get("/market/constituents/analysis?tickers=139260,363580")
    body = res.json()
    assert res.status_code == 200
    assert body["asof"] == "2026-05-26"
    by_ticker = {c["etf_ticker"]: c for c in body["constituents"]}
    assert (
        by_ticker["363580"]["status"] == "ok"
        and by_ticker["363580"]["asof"] == "2026-05-26"
    )
    assert (
        by_ticker["139260"]["status"] == "ok"
        and by_ticker["139260"]["asof"] == "2026-05-25"
    )
    assert (
        by_ticker["139260"]["asof_confirmed"] is False
    )  # 원천 기준일 확인 표시 없는 저장분
    pair = body["overlap_matrix"][0]
    assert (pair["left_asof"], pair["right_asof"], pair["same_date"]) == (
        "2026-05-25",
        "2026-05-26",
        False,
    )


def test_get_analysis_asof_optional_falls_back_to_today_when_no_data(api_client):
    """ticker 가 DB 에 1건도 없으면 today 로 fallback (모두 unavailable)."""
    res = api_client.get("/market/constituents/analysis?tickers=NEVER1,NEVER2")
    body = res.json()
    assert res.status_code == 200
    # today 의 ISO date — 형식만 확인.
    assert len(body["asof"]) == 10
    assert body["asof"][4] == "-" and body["asof"][7] == "-"
    assert body["coverage"]["available_count"] == 0
    assert body["coverage"]["unavailable_count"] == 2


def test_refresh_cache_first_matches_naver_source(
    api_client, monkeypatch: pytest.MonkeyPatch
):
    """2026-05-31 — cache key 가 ticker+asof+source 일치 매칭. 본 STEP 부터
    expected_source 가 NAVER_STOCK_SOURCE 라, 다른 source 의 캐시는 hit 안 됨.
    """
    from app import etf_constituents_store as store

    # 다른 source 로 시드 (예: "src" — naver 와 다름).
    upsert_constituents(
        [ConstituentRow("139260", "2026-05-26", "src", 1, "005930", "삼성전자", 25.0)],
        db_path=store.DEFAULT_DB_PATH,
    )

    called: list[str] = []

    def stub_fetcher(ticker, asof, top_k):  # noqa: ARG001
        from app.etf_constituents_fetcher import (
            FetchedConstituent,
            FetchResult,
            NAVER_STOCK_SOURCE,
        )

        called.append(ticker)
        return FetchResult(
            status="ok",
            source=NAVER_STOCK_SOURCE,
            constituents=[
                FetchedConstituent(
                    rank=1,
                    constituent_ticker="005930",
                    constituent_name="삼성전자",
                    weight_pct=25.0,
                )
            ],
        )

    from app import etf_constituents_service as service

    monkeypatch.setattr(service, "default_fetcher", lambda: stub_fetcher)

    res = api_client.post(
        "/market/constituents/refresh",
        json={"asof": "2026-05-26", "tickers": ["139260"]},
    )
    body = res.json()
    # 기존 캐시는 다른 source 라 hit 안 됨 → fetcher 호출됨.
    assert called == ["139260"]
    assert body["fetched_count"] == 1
    assert body["cached_count"] == 0


def _seed_confirmed(db: Path, tk: str, asof: str, *, confirmed: bool = True):
    from app.etf_constituents_fetcher import NAVER_STOCK_SOURCE as SRC
    from app.etf_constituents_status import confirmation_message
    from app.etf_constituents_store import log_constituent_refresh

    rows = [ConstituentRow(tk, asof, SRC, 1, "005930", "삼성전자", 20.0)]
    upsert_constituents(rows, db_path=db)
    log_constituent_refresh(
        etf_ticker=tk,
        asof=asof,
        status="ok",
        source=SRC,
        message=confirmation_message(rows) if confirmed else None,
        db_path=db,
    )


def test_analysis_pairs_scope_29_same_date_plus_1_missing_is_406(api_client):
    """POC6-31 지적 backend#0 · frontend#0(HIGH) — 판정 §4 M2: 30개 중 29개만 같은 날짜 자료 → 같은 구성일 쌍 406.

    자료 없는 ETF가 낀 쌍은 같은 날짜 쌍이 아니다(가장 늦은 날짜를 물려받지 않음).
    """
    from app import etf_constituents_store as store

    tickers = [f"E{i:02d}" for i in range(30)]
    for t in tickers[:29]:
        _seed_confirmed(store.DEFAULT_DB_PATH, t, "2026-11-13")
    body = api_client.get(
        f"/market/constituents/analysis?tickers={','.join(tickers)}"
    ).json()
    scopes = [p["pair_scope"] for p in body["overlap_matrix"]]
    assert len(scopes) == 435
    assert scopes.count("same_date") == 406 and scopes.count("no_data") == 29
    missing = [
        p
        for p in body["overlap_matrix"]
        if "E29" in (p["left_ticker"], p["right_ticker"])
    ]
    assert all(p["same_date"] is None for p in missing)
    assert all(
        (p["right_asof"] if p["right_ticker"] == "E29" else p["left_asof"]) is None
        for p in missing
    )
    assert sum(1 for p in body["overlap_matrix"] if p["same_date"] is True) == 406


def test_analysis_pairs_scope_unconfirmed_and_different_date(api_client):
    """지적 backend#6 — 원천 기준일이 확인되지 않은 쪽이 있으면 같은 날짜여도 같은 구성일 쌍이 아니다(참고)."""
    from app import etf_constituents_store as store

    db = store.DEFAULT_DB_PATH
    _seed_confirmed(db, "A", "2026-11-13")
    _seed_confirmed(db, "B", "2026-11-13")
    _seed_confirmed(db, "C", "2026-11-13", confirmed=False)  # 예전 저장분 흉내
    _seed_confirmed(db, "D", "2026-11-12")
    body = api_client.get("/market/constituents/analysis?tickers=A,B,C,D").json()
    by = {(p["left_ticker"], p["right_ticker"]): p for p in body["overlap_matrix"]}
    assert (
        by[("A", "B")]["pair_scope"] == "same_date"
        and by[("A", "B")]["same_date"] is True
    )
    assert (
        by[("A", "C")]["pair_scope"] == "unconfirmed"
        and by[("A", "C")]["same_date"] is False
    )
    assert by[("A", "D")]["pair_scope"] == "different_date"
    assert (by[("A", "D")]["left_asof"], by[("A", "D")]["right_asof"]) == (
        "2026-11-13",
        "2026-11-12",
    )
    assert by[("C", "D")]["pair_scope"] == "unconfirmed"


@pytest.mark.parametrize("explicit", [False, True])
def test_f2_unconfirmed_same_date_pair_is_not_same_date_with_or_without_asof(
    api_client, explicit
):
    """검증자 r1 F2 — 원천일 확인 표시가 없는 같은 날짜 예전 ETF 2개는 날짜를 지정해도 · 비워도 '원천 기준일 미확인'."""
    from app import etf_constituents_store as store

    db = store.DEFAULT_DB_PATH
    _seed_confirmed(db, "A", "2026-10-02", confirmed=False)
    _seed_confirmed(db, "B", "2026-10-02", confirmed=False)
    q = "&asof=2026-10-02" if explicit else ""
    body = api_client.get(f"/market/constituents/analysis?tickers=A,B{q}").json()
    p = body["overlap_matrix"][0]
    assert p["pair_scope"] == "unconfirmed" and p["same_date"] is False
    assert (p["left_asof"], p["right_asof"]) == ("2026-10-02", "2026-10-02")
    assert [c["asof_confirmed"] for c in body["constituents"]] == [False, False]


def test_f2_explicit_asof_same_date_only_when_confirmed_at_that_date(api_client):
    """날짜 지정 — 원천일이 확인된 구성이 바로 그 날짜인 쪽만 확인(다른 날짜에 확인된 ETF는 미확인)."""
    from app import etf_constituents_store as store

    db = store.DEFAULT_DB_PATH
    _seed_confirmed(db, "A", "2026-11-13")
    _seed_confirmed(db, "B", "2026-11-13")
    _seed_confirmed(db, "C", "2026-11-13", confirmed=False)
    _seed_confirmed(db, "C", "2026-11-12")  # C 의 확인된 구성은 11/12
    body = api_client.get(
        "/market/constituents/analysis?tickers=A,B,C&asof=2026-11-13"
    ).json()
    by = {
        (p["left_ticker"], p["right_ticker"]): p["pair_scope"]
        for p in body["overlap_matrix"]
    }
    assert by == {
        ("A", "B"): "same_date",
        ("A", "C"): "unconfirmed",
        ("B", "C"): "unconfirmed",
    }


def test_f2_compute_analysis_without_confirmation_is_never_same_date(tmp_path):
    """검증자 r1 B-1 — 확인 정보를 받지 못한 분석(날짜만 준 호출)은 같은 구성일로 분류하지 않는다(기본 = 미확인)."""
    from app.etf_constituents_analysis import compute_analysis

    db = tmp_path / "m.sqlite"
    _seed_confirmed(db, "A", "2026-11-13")
    _seed_confirmed(db, "B", "2026-11-13")
    out = compute_analysis(tickers=["A", "B"], asof="2026-11-13", db_path=db)
    p = out["overlap_matrix"][0]
    assert p["pair_scope"] == "unconfirmed" and p["same_date"] is False
    assert (p["left_asof"], p["right_asof"]) == ("2026-11-13", "2026-11-13")


# ---------- 검증자 r2 정정(F5 · F6 · 2026-11-16) ----------


def _manual_overwrite(db: Path, tk: str, asof: str, name: str = "덮어쓴 주식"):
    """기존 수동 수집(POST /market/constituents/refresh 경로) — 원천일 없는 응답을 요청일로 저장."""
    from app.etf_constituents_fetcher import (
        NAVER_STOCK_SOURCE as SRC,
        FetchedConstituent,
        FetchResult,
    )
    from app.etf_constituents_service import refresh_constituents

    def no_date(ticker, a, top_k):  # noqa: ARG001
        return FetchResult(
            status="ok",
            source=SRC,
            constituents=[
                FetchedConstituent(
                    rank=1,
                    constituent_ticker="999999",
                    constituent_name=name,
                    weight_pct=50.0,
                )
            ],
        )

    refresh_constituents(
        asof=asof,
        tickers=[tk],
        force=True,
        fetcher=no_date,
        db_path=db,
        sleep_fn=lambda s: None,
    )


@pytest.fixture()
def fast_lock_timeout(monkeypatch):
    """진짜 잠금 시험용 — 모든 sqlite 연결의 잠김 대기를 0.2초로(기본 5초 · 잠금 의미는 그대로)."""
    import sqlite3

    real = sqlite3.connect

    def connect(*a, **kw):
        kw.setdefault("timeout", 0.2)
        return real(*a, **kw)

    monkeypatch.setattr(sqlite3, "connect", connect)


def _save(db, tk, weights, date="2026-11-12"):
    """정상 저장 경로(구성 통째 바꾸기 + 확인 지문 기록 · 한 트랜잭션) — 새 수집 작업이 쓰는 그 함수."""
    from app.etf_constituents_fetcher import NAVER_STOCK_SOURCE as SRC
    from app.etf_constituents_store import replace_constituents_snapshot

    rows = [
        ConstituentRow(tk, date, SRC, i + 1, f"00593{i}", f"주식{i}", w)
        for i, w in enumerate(weights)
    ]
    return replace_constituents_snapshot(
        rows, log_status="ok", confirm=True, db_path=db
    )


def _hook_after_marks(monkeypatch, action):
    """분석 읽기 트랜잭션 안에서 확인 지문을 읽은 바로 뒤 `action` 실행(쓰기 시도) — 결과(예외 포함)를 남긴다.

    `hook["on"] = False` 로 끈다(시험 준비의 임시 DB 경로는 건드리지 않음).
    """
    from app import etf_constituents_status as ST

    real = ST._confirm_marks
    hook: dict = {"on": True, "seen": []}

    def marks_then(con, tks):
        out = real(con, tks)
        if hook["on"]:
            try:
                hook["seen"].append(action())
            except Exception as e:  # noqa: BLE001 — 잠김 등 쓰기 실패도 그대로 기록
                hook["seen"].append(e)
        return out

    monkeypatch.setattr(ST, "_confirm_marks", marks_then)
    return hook


def test_f5_overwrite_between_confirmation_and_row_read_is_unconfirmed(
    api_client, monkeypatch, fast_lock_timeout
):
    """검증자 r2 F5 (a) · r3 F8 — 분석은 날짜 · 확인 지문 · 행을 한 읽기 트랜잭션에서 읽는다. 지문을 읽은 직후의 기존 수동
    덮어쓰기는 그 읽기가 끝날 때까지 들어오지 못하고(잠김), 분석은 한 시점의 행 · 확인으로 일관된다."""
    from app import etf_constituents_store as store

    db = store.DEFAULT_DB_PATH
    _seed_confirmed(db, "A", "2026-11-13")
    _seed_confirmed(db, "B", "2026-11-13")
    hook = _hook_after_marks(
        monkeypatch, lambda: _manual_overwrite(db, "A", "2026-11-13")
    )
    body = api_client.get("/market/constituents/analysis?tickers=A,B").json()
    assert hook["seen"] and "locked" in str(hook["seen"][0])  # 읽는 동안 쓰기 못 들어옴
    by = {c["etf_ticker"]: c for c in body["constituents"]}
    assert by["A"]["top_holdings"][0]["name"] == "삼성전자"
    assert by["A"]["asof_confirmed"] is True and by["B"]["asof_confirmed"] is True
    assert body["overlap_matrix"][0]["pair_scope"] == "same_date"
    # 읽기가 끝난 뒤 덮어쓰면 다음 분석은 덮어쓴 행 = 미확인
    hook["on"] = False
    _manual_overwrite(db, "A", "2026-11-13")
    body2 = api_client.get("/market/constituents/analysis?tickers=A,B").json()
    by2 = {c["etf_ticker"]: c for c in body2["constituents"]}
    assert by2["A"]["top_holdings"][0]["name"] == "덮어쓴 주식"
    assert by2["A"]["asof_confirmed"] is False
    assert body2["overlap_matrix"][0]["pair_scope"] == "unconfirmed"


def test_f8_legit_recollection_during_analysis_read_stays_consistent(
    api_client, monkeypatch, fast_lock_timeout
):
    """검증자 r3 F8 — 11/12 확인 자료 두 ETF · 날짜 지정 분석 중(지문을 읽은 직후) A 를 42% 로 정상 저장 경로 교체 →
    그 분석은 한 시점(교체 전)의 행 · 확인으로 같은 구성일. 읽기가 끝난 뒤 교체하면 새 행 · 새 확인으로 같은 구성일."""
    from app import etf_constituents_store as store

    db = store.DEFAULT_DB_PATH
    _save(db, "A", [40.0, 10.0])
    _save(db, "B", [40.0, 10.0])
    hook = _hook_after_marks(monkeypatch, lambda: _save(db, "A", [42.0, 10.0]))
    q = "/market/constituents/analysis?tickers=A,B&asof=2026-11-12"
    body = api_client.get(q).json()
    assert hook["seen"] and "locked" in str(hook["seen"][0])  # 읽는 동안 저장 못 함
    by = {c["etf_ticker"]: c for c in body["constituents"]}
    assert by["A"]["top_holdings"][0]["weight_pct"] == 40.0
    assert [by[t]["asof_confirmed"] for t in "AB"] == [True, True]
    assert body["overlap_matrix"][0]["pair_scope"] == "same_date"
    hook["on"] = False
    _save(db, "A", [42.0, 10.0])
    body2 = api_client.get(q).json()
    by2 = {c["etf_ticker"]: c for c in body2["constituents"]}
    assert by2["A"]["top_holdings"][0]["weight_pct"] == 42.0
    assert [by2[t]["asof_confirmed"] for t in "AB"] == [True, True]
    assert body2["overlap_matrix"][0]["pair_scope"] == "same_date"


def test_f8_analysis_uses_rows_read_with_confirmation_not_a_later_read(
    api_client, monkeypatch
):
    """검증자 r3 F8 — 분석은 한 읽기 트랜잭션에서 받은 행 그대로 계산한다(그 뒤 따로 다시 읽지 않음). 읽기가 끝난 직후
    덮어써도 그 분석은 읽은 시점의 행 · 확인으로 일관된다(덮어쓴 행을 확인 자료로 섞지 않음)."""
    from app import api_etf_constituents as M
    from app import etf_constituents_store as store

    db = store.DEFAULT_DB_PATH
    _seed_confirmed(db, "A", "2026-11-13")
    _seed_confirmed(db, "B", "2026-11-13")
    real = M.read_analysis_rows

    def read_then_overwrite(tickers, *, asof, db_path):
        out = real(tickers, asof=asof, db_path=db_path)
        _manual_overwrite(db_path, "A", "2026-11-13")  # 읽기가 끝난 바로 뒤
        return out

    monkeypatch.setattr(M, "read_analysis_rows", read_then_overwrite)
    body = api_client.get("/market/constituents/analysis?tickers=A,B").json()
    by = {c["etf_ticker"]: c for c in body["constituents"]}
    assert by["A"]["top_holdings"][0]["name"] == "삼성전자"
    assert by["A"]["asof_confirmed"] is True
    assert body["overlap_matrix"][0]["pair_scope"] == "same_date"


def test_f5_cross_family_uses_only_rows_read_with_confirmation(api_client, monkeypatch):
    """F5 (a) 공통 주식 경로 — 확인 판정과 같은 읽기의 행만 쓴다(그 뒤 덮어쓴 행이 확인 자료로 섞이지 않음)."""
    from app import constituents_cross_family as X
    from app import etf_constituents_store as store

    db = store.DEFAULT_DB_PATH
    _seed_confirmed(db, "A", "2026-11-13")
    real = X.read_snapshots

    def snaps_then_overwrite(tickers, *, db_path):
        out = real(tickers, db_path=db_path)
        _manual_overwrite(db_path, "A", "2026-11-13")
        return out

    monkeypatch.setattr(X, "read_snapshots", snaps_then_overwrite)
    got = X.read_confirmed_rows(["A"], db_path=db)
    assert [r["name"] for r in got["A"]["rows"]] == ["삼성전자"]  # 확인한 그 행
    # 다시 읽으면 덮어쓴 구성은 미확인(확인된 구성 없음)
    monkeypatch.setattr(X, "read_snapshots", real)
    assert X.read_confirmed_rows(["A"], db_path=db) == {}


def test_f5_earlier_timestamp_written_later_is_still_unconfirmed(
    api_client, monkeypatch
):
    """검증자 r2 F5 (b) — 기존 저장 경로가 시각을 먼저 정한 뒤 늦게 쓰면(행 시각 < 확인 기록 시각) 시각 비교로는
    확인으로 남았다. 내용 지문 대조라 다른 내용은 미확인."""
    from app import etf_constituents_store as store
    from app.etf_constituents_status import EXISTING, NOT_CHECKED, read_status

    db = store.DEFAULT_DB_PATH
    _seed_confirmed(db, "A", "2026-11-13")
    with monkeypatch.context() as m:  # 이 덮어쓰기만 더 이른 시각(시험 준비의 임시 DB 경로는 그대로)
        m.setattr(store, "_utcnow_iso", lambda: "2000-01-01T00:00:00.000000Z")
        _manual_overwrite(db, "A", "2026-11-13")
    st = read_status(["A"], target_date="2026-11-13", db_path=db)["A"]
    assert st["result"] == NOT_CHECKED and st["result"] != EXISTING
    body = api_client.get("/market/constituents/analysis?tickers=A").json()
    assert body["constituents"][0]["asof_confirmed"] is False


def test_f6_explicit_past_date_confirmed_after_newer_snapshot(api_client):
    """검증자 r2 F6 — 11/12 · 11/13 모두 원천일 확인 → 11/12 를 지정해도 그 날짜의 확인 기록으로 같은 구성일."""
    from app import etf_constituents_store as store

    db = store.DEFAULT_DB_PATH
    for t in ("A", "B"):
        _seed_confirmed(db, t, "2026-11-12")
        _seed_confirmed(db, t, "2026-11-13")
    for d in ("2026-11-12", "2026-11-13"):
        body = api_client.get(
            f"/market/constituents/analysis?tickers=A,B&asof={d}"
        ).json()
        p = body["overlap_matrix"][0]
        assert p["pair_scope"] == "same_date" and (p["left_asof"], p["right_asof"]) == (
            d,
            d,
        )
        assert [c["asof_confirmed"] for c in body["constituents"]] == [True, True]


# ---------- 검증자 r4 정정(F9 · 2026-11-16) ----------


def _old_source(db: Path, tk: str, asof: str):
    """예전 출처(pykrx)로만 저장된 구성(원천일 확인 기록 없음)."""
    upsert_constituents(
        [ConstituentRow(tk, asof, "pykrx", 1, "005930", "삼성전자", 30.0)], db_path=db
    )


@pytest.mark.parametrize("explicit", [False, True])
def test_f9_old_source_only_etf_is_shown_and_unconfirmed(api_client, explicit):
    """검증자 r4 F9 — 같은 11/12 에 네이버 확인 자료 A · 예전 pykrx 자료만 있는 B → 날짜를 비워도 · 지정해도 2/2 표시 ·
    B 는 원천 기준일 미확인 · 쌍은 '자료 없음'이 아니라 '원천 기준일 미확인'."""
    from app import etf_constituents_store as store

    db = store.DEFAULT_DB_PATH
    _save(db, "A", [40.0, 10.0])
    _old_source(db, "B", "2026-11-12")
    q = "&asof=2026-11-12" if explicit else ""
    body = api_client.get(f"/market/constituents/analysis?tickers=A,B{q}").json()
    assert body["coverage"]["available_count"] == 2
    by = {c["etf_ticker"]: c for c in body["constituents"]}
    assert by["B"]["status"] == "ok" and by["B"]["asof"] == "2026-11-12"
    assert by["A"]["asof_confirmed"] is True and by["B"]["asof_confirmed"] is False
    p = body["overlap_matrix"][0]
    assert p["pair_scope"] == "unconfirmed" and (p["left_asof"], p["right_asof"]) == (
        "2026-11-12",
        "2026-11-12",
    )


def test_f9_old_source_at_its_own_date_and_list_without_naver(api_client):
    """날짜를 비우면 ETF마다 실제 날짜 — 예전 출처만 있는 ETF는 그 ETF 의 마지막 구성일로(빠지지 않음) ·
    목록 전체에 네이버 자료가 없어도 표시(모두 미확인)."""
    from app import etf_constituents_store as store

    db = store.DEFAULT_DB_PATH
    _save(db, "A", [40.0, 10.0])
    _old_source(db, "B", "2026-11-10")
    _old_source(db, "B", "2026-11-05")
    body = api_client.get("/market/constituents/analysis?tickers=A,B").json()
    by = {c["etf_ticker"]: c for c in body["constituents"]}
    assert by["B"]["asof"] == "2026-11-10" and by["B"]["asof_confirmed"] is False
    assert body["overlap_matrix"][0]["pair_scope"] == "unconfirmed"
    _old_source(db, "C", "2026-11-09")
    only_old = api_client.get("/market/constituents/analysis?tickers=B,C").json()
    assert only_old["coverage"]["available_count"] == 2
    assert [c["asof_confirmed"] for c in only_old["constituents"]] == [False, False]
    assert only_old["asof"] == "2026-11-10"
