"""POC4-01 — KRX universe 연구 DB 다운로더 (설계자 결정 2 Gate 2·4).

네트워크 없이 가짜 fetcher 로 checkpoint·중복·누락·재시도·backoff·한도·
no-overwrite 계약을 확인한다. 연구 DB 는 tmp_path 에만 만든다.
"""

from __future__ import annotations

import json

import pytest

import app.ml_research_krx_universe as krx
from app.market_data_store import DEFAULT_DB_PATH


def _payload(bas_dd: str, *, traded: bool = True, n: int = 3, bump: str = "") -> str:
    rows = [
        {
            "BAS_DD": bas_dd,
            "ISU_CD": f"{i:06d}",
            "ISU_NM": f"ETF{i}{bump}",
            "TDD_CLSPRC": "1000" if traded else "",
        }
        for i in range(n)
    ]
    return json.dumps({"OutBlock_1": rows}, ensure_ascii=False)


class FakeKrx:
    """날짜별 응답 스크립트. 호출 기록을 남긴다."""

    def __init__(self, script=None):
        self.script = script or {}
        self.calls: list[str] = []

    def __call__(self, bas_dd: str, key: str) -> krx.FetchResult:
        assert key == "k"
        self.calls.append(bas_dd)
        queue = self.script.get(bas_dd)
        item = queue.pop(0) if isinstance(queue, list) and queue else queue
        if isinstance(item, Exception):
            raise item
        if isinstance(item, int):
            return krx.FetchResult(item, "{}")
        return krx.FetchResult(200, item if item is not None else _payload(bas_dd))


@pytest.fixture
def con(tmp_path):
    c = krx.connect(tmp_path / "research.sqlite")
    yield c
    c.close()


def _run(con, fetch, *, batch="b1", max_calls=100, sleeps=None):
    return krx.run_batch(
        con,
        batch,
        key="k",
        fetch=fetch,
        max_calls=max_calls,
        pause_seconds=0.0,
        sleep=(sleeps.append if sleeps is not None else (lambda s: None)),
    )


def _plan(con, batch="b1"):
    return dict(
        con.execute(
            "SELECT bas_dd, state FROM krx_download_plan WHERE batch_id=?", (batch,)
        ).fetchall()
    )


def test_refuses_operating_market_db():
    with pytest.raises(krx.ResearchDbError, match="운영"):
        krx.connect(DEFAULT_DB_PATH)


def test_canary_is_capped_at_twenty_dates(con):
    dates = krx.weekdays("20240101", "20240205")
    assert len(dates) > 20
    with pytest.raises(krx.ResearchDbError, match="20"):
        krx.create_batch(
            con, batch_id="c", purpose="CANARY", dates=dates, dataset_version="v1"
        )


def test_weekdays_skip_weekends():
    assert krx.weekdays("20260918", "20260922") == ["20260918", "20260921", "20260922"]


def test_classifies_traded_holiday_and_empty_and_stores_raw_verbatim(con):
    fetch = FakeKrx(
        {
            "20260101": _payload("20260101", traded=False),
            "20260102": None,
            "20260103": json.dumps({"OutBlock_1": []}),
        }
    )
    krx.create_batch(
        con,
        batch_id="b1",
        purpose="CANARY",
        dates=["20260101", "20260102", "20260103"],
        dataset_version="v1",
    )
    out = _run(con, fetch)
    assert out["stopped"] is None
    assert _plan(con) == {
        "20260101": krx.NON_TRADING,
        "20260102": krx.TRADED,
        "20260103": krx.NO_ROWS,
    }
    members = con.execute("SELECT bas_dd FROM krx_dataset_member").fetchall()
    assert members == [("20260102",)], "거래일만 universe version 에 들어간다"
    payload = con.execute(
        "SELECT payload FROM krx_raw_response WHERE bas_dd='20260102'"
    ).fetchone()[0]
    assert payload == _payload("20260102"), "원응답 본문을 그대로 보관해야 한다"
    assert krx.verify_batch(con, "b1")["ok"] is True
    attempts = con.execute("SELECT COUNT(*) FROM krx_fetch_attempt").fetchone()[0]
    assert attempts == 3


def test_resume_continues_from_checkpoint_without_refetching(con):
    dates = ["20260105", "20260106", "20260107", "20260108"]
    krx.create_batch(
        con, batch_id="b1", purpose="FULL", dates=dates, dataset_version="v1"
    )
    fetch = FakeKrx()
    first = _run(con, fetch, max_calls=2)
    assert first["stopped"] == "CALL_LIMIT"
    assert first["status"]["remaining"] == 2
    second = _run(con, fetch, max_calls=10)
    assert second["stopped"] is None
    assert fetch.calls == dates, "끝난 날짜를 다시 부르면 안 된다"
    assert set(_plan(con).values()) == {krx.TRADED}
    # 같은 batch 를 다시 만들어도 계획은 바뀌지 않는다 (이어받기)
    assert (
        krx.create_batch(
            con, batch_id="b1", purpose="FULL", dates=dates[:1], dataset_version="v1"
        )
        == 4
    )


def test_server_error_is_retried_with_exponential_backoff(con):
    krx.create_batch(
        con, batch_id="b1", purpose="FULL", dates=["20260105"], dataset_version="v1"
    )
    fetch = FakeKrx({"20260105": [500, TimeoutError(), _payload("20260105")]})
    sleeps: list[float] = []
    out = _run(con, fetch, sleeps=sleeps)
    assert _plan(con) == {"20260105": krx.TRADED}
    assert len(fetch.calls) == 3
    assert [s for s in sleeps if s] == [2.0, 4.0], "backoff 는 2배씩 늘어야 한다"
    assert out["calls"] == 3


def test_http_429_stops_immediately_and_resume_retries_later(con):
    dates = ["20260105", "20260106"]
    krx.create_batch(
        con, batch_id="b1", purpose="FULL", dates=dates, dataset_version="v1"
    )
    fetch = FakeKrx({"20260105": [429, _payload("20260105")]})
    out = _run(con, fetch)
    assert out["stopped"] == "QUOTA_429"
    assert fetch.calls == ["20260105"], "429 는 재시도하지 않는다"
    assert _plan(con) == {"20260105": krx.FAILED, "20260106": krx.PENDING}
    again = _run(con, fetch)
    assert again["stopped"] is None
    assert set(_plan(con).values()) == {krx.TRADED}


def test_client_error_other_than_429_stops_the_run(con):
    krx.create_batch(
        con,
        batch_id="b1",
        purpose="FULL",
        dates=["20260105", "20260106"],
        dataset_version="v1",
    )
    fetch = FakeKrx({"20260105": 401})
    out = _run(con, fetch)
    assert out["stopped"] == "HTTP_401"
    assert fetch.calls == ["20260105"]


def test_consecutive_failures_trip_the_breaker(con):
    dates = ["20260105", "20260106", "20260107", "20260108"]
    krx.create_batch(
        con, batch_id="b1", purpose="FULL", dates=dates, dataset_version="v1"
    )
    fetch = FakeKrx({d: [503, 503, 503] for d in dates})
    out = _run(con, fetch)
    assert out["stopped"] == "CONSECUTIVE_FAILURES"
    assert _plan(con)["20260108"] == krx.PENDING
    assert krx.verify_batch(con, "b1")["ok"] is False


def test_daily_budget_counts_all_attempts(con, monkeypatch):
    dates = ["20260105", "20260106", "20260107", "20260108"]
    krx.create_batch(
        con, batch_id="b1", purpose="FULL", dates=dates, dataset_version="v1"
    )
    monkeypatch.setattr(krx, "MAX_CALLS_PER_KST_DAY", 3)
    out = _run(con, FakeKrx(), max_calls=100)
    assert out["calls"] == 3 and out["stopped"] == "CALL_LIMIT"
    assert krx.calls_today(con) == 3
    assert _run(con, FakeKrx(), max_calls=100)["calls"] == 0


def test_refetch_with_different_payload_is_conflict_not_overwrite(con):
    krx.create_batch(
        con, batch_id="b1", purpose="FULL", dates=["20260105"], dataset_version="v1"
    )
    _run(con, FakeKrx())
    kept = con.execute("SELECT response_id FROM krx_dataset_member").fetchone()[0]

    krx.create_batch(
        con, batch_id="b2", purpose="FULL", dates=["20260105"], dataset_version="v1"
    )
    _run(con, FakeKrx({"20260105": _payload("20260105", bump="*")}), batch="b2")
    assert con.execute("SELECT response_id FROM krx_dataset_member").fetchone()[0] == (
        kept
    ), "기존 version 의 값을 조용히 바꾸면 안 된다"
    conflict = con.execute("SELECT * FROM krx_refetch_conflict").fetchall()
    assert len(conflict) == 1
    assert con.execute("SELECT COUNT(*) FROM krx_raw_response").fetchone()[0] == 2

    # 같은 내용 재수집은 충돌이 아니다
    krx.create_batch(
        con, batch_id="b3", purpose="FULL", dates=["20260105"], dataset_version="v1"
    )
    _run(con, FakeKrx(), batch="b3")
    assert con.execute("SELECT COUNT(*) FROM krx_refetch_conflict").fetchone()[0] == 1

    # 달라진 결과는 별도 version 으로만 채택한다
    new_id = conflict[0][3]
    krx.derive_version(con, "v2", "v1", {"20260105": new_id})
    rows = dict(
        con.execute("SELECT version_id, response_id FROM krx_dataset_member").fetchall()
    )
    assert rows == {"v1": kept, "v2": new_id}


def test_sealed_version_cannot_receive_new_data(con):
    krx.create_batch(
        con, batch_id="b1", purpose="FULL", dates=["20260105"], dataset_version="v1"
    )
    _run(con, FakeKrx())
    sealed = krx.seal_version(con, "v1", "test")
    assert sealed["dates"] == 1 and sealed["content_sha256"]
    with pytest.raises(krx.ResearchDbError, match="봉인"):
        krx.create_batch(
            con, batch_id="b2", purpose="FULL", dates=["20260106"], dataset_version="v1"
        )
    with pytest.raises(krx.ResearchDbError, match="봉인"):
        _run(con, FakeKrx())


def test_verify_flags_duplicate_tickers_within_a_response(con):
    rows = [{"ISU_CD": "000001", "TDD_CLSPRC": "1"}] * 2
    krx.create_batch(
        con, batch_id="b1", purpose="FULL", dates=["20260105"], dataset_version="v1"
    )
    _run(con, FakeKrx({"20260105": json.dumps({"OutBlock_1": rows})}))
    report = krx.verify_batch(con, "b1")
    assert report["duplicate_isu_within_response"] == 1
    assert report["ok"] is False
