"""POC5-11 — PC 시장 판정 날짜 = 실제 쓴 KODEX200 이력 마지막 날짜 (PLAN §2 · §6 · 설계자 판정 Q1 · §4).

격리 DB(tmp)만 쓴다. KODEX200(069500) 유효 행 끝 = D1, 다른 ETF 끝 = D2(> D1).
069500 의 D2 행은 종가가 없다(전체 최신일에는 들어가고 판정 이력에서는 빠지는 행).
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import api as api_module
from app import api_market_topn, market_data_store, market_refresh_service
from app.market_data_store import (
    EtfDailyPriceRow,
    EtfMasterRow,
    upsert_daily_prices,
    upsert_etf_master,
)
from app.market_topn import compute_topn

D1 = date(2026, 10, 13)
D2 = date(2026, 10, 14)


def _seed(db: Path, *, with_kodex: bool = True) -> None:
    upsert_etf_master(
        [
            EtfMasterRow("069500", "KODEX 200", "1", 130.0, 1000, 5000.0),
            EtfMasterRow("379800", "KODEX 미국S&P500", "1", 120.0, 1000, 5000.0),
        ],
        source="Test",
        db_path=db,
    )
    rows = []
    if with_kodex:
        for i in range(80):
            dt = (D1 - timedelta(days=79 - i)).isoformat()
            c = 100.0 + 0.3 * i
            rows.append(EtfDailyPriceRow("069500", dt, c, c, c, c, 0, 0))
        rows.append(
            EtfDailyPriceRow("069500", D2.isoformat(), None, None, None, None, 0, 0)
        )
    for i in range(100):
        dt = (D2 - timedelta(days=99 - i)).isoformat()
        c = 100.0 + 0.2 * i
        rows.append(EtfDailyPriceRow("379800", dt, c, c, c, c, 0, 0))
    upsert_daily_prices(rows, source="Test", db_path=db)


def _topn(db: Path, **kw) -> dict:
    return compute_topn(
        n=10,
        db_path=db,
        exclude_inverse=False,
        exclude_leveraged=False,
        exclude_synthetic=False,
        exclude_futures=False,
        **kw,
    )


def test_pc_flag_uses_kodex200_history_end_and_keeps_everything_else(
    tmp_path: Path,
) -> None:
    db = tmp_path / "m.sqlite"
    _seed(db)
    default = _topn(db)
    pc = _topn(db, market_asof_from_kodex200=True)
    # PC 판정 날짜 = 069500 유효 이력 마지막(D1) · 기본(OCI · 초안 · 다른 호출자)은 전체 최신일(D2) 그대로.
    assert pc["market_context"]["asof"] == D1.isoformat()
    assert default["market_context"]["asof"] == D2.isoformat()
    # 최상위 asof · 후보 기간 계산은 두 호출 모두 D2 그대로.
    assert pc["asof"] == default["asof"] == D2.isoformat()
    assert pc["candidates"] == default["candidates"]
    assert pc["candidates"]
    assert all(
        c.get("selected_basis_end_date") == D2.isoformat() for c in pc["candidates"]
    )
    # 국면 · 지속일 · 기준선 값은 날짜 말고는 같다.
    strip = lambda ctx: {k: v for k, v in ctx.items() if k != "asof"}  # noqa: E731
    assert strip(pc["market_context"]) == strip(default["market_context"])
    assert pc.get("regime_streak") == default.get("regime_streak")
    assert pc["market_context"]["asof_source"] == "KODEX200"


def test_pc_flag_without_kodex200_history_gives_none_not_other_date(
    tmp_path: Path,
) -> None:
    db = tmp_path / "m.sqlite"
    _seed(db, with_kodex=False)
    pc = _topn(db, market_asof_from_kodex200=True)
    assert (
        pc["market_context"]["asof"] is None
    )  # 전체 최신일 · 다른 종목 날짜로 대신하지 않음
    assert pc["asof"] == D2.isoformat()
    default = _topn(db)
    strip = lambda ctx: {k: v for k, v in ctx.items() if k != "asof"}  # noqa: E731
    assert strip(pc["market_context"]) == strip(default["market_context"])


@pytest.fixture
def api_client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TestClient:
    fake_db = tmp_path / "market_data.sqlite"
    monkeypatch.setattr(api_market_topn, "DEFAULT_DB_PATH", fake_db)
    monkeypatch.setattr(market_data_store, "DEFAULT_DB_PATH", fake_db)
    market_refresh_service.reset_state_for_testing(db_path=fake_db)
    return TestClient(api_module.app)


def test_pc_screen_api_reports_kodex200_date_and_same_row_as_other_kodex_dates(
    api_client: TestClient,
) -> None:
    _seed(api_market_topn.DEFAULT_DB_PATH)
    payload = api_client.get("/market/topn/latest").json()
    assert payload["asof"] == D2.isoformat()
    assert payload["market_context"]["asof"] == D1.isoformat()
    # 같은 '069500 유효 가격 최신 행' 조건을 쓰는 다른 두 날짜와 같다(행 조건 일치).
    assert payload["market_risk_reference"]["kodex200"]["as_of_date"] == D1.isoformat()
    assert payload["kodex200_stored_volume"]["asof_date"] == D1.isoformat()


def test_other_callers_keep_whole_table_date(tmp_path: Path) -> None:
    """compute_topn 의 다른 호출자(OCI 근거 · 초안 · 「확인 근거」 · ML)는 인자를 넘기지 않는다."""
    import subprocess

    out = (
        subprocess.run(
            [
                "git",
                "grep",
                "-n",
                "market_asof_from_kodex200=True",
                "--",
                "app",
                "scripts",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        .stdout.strip()
        .splitlines()
    )
    assert [line.split(":")[0] for line in out] == ["app/api_market_topn.py"]


def test_oci_evidence_sentence_keeps_whole_table_date(tmp_path: Path) -> None:
    """OCI 3-PUSH 근거 문장은 기본 호출 그대로(최상위 asof = 전체 최신일 D2) — 이번 정정 대상 아님(관찰)."""
    from app.runtime_evidence.market_discovery import compose_market_discovery

    db = tmp_path / "m.sqlite"
    _seed(db)
    _status, notes, _diag = compose_market_discovery(compute_topn, db)
    assert any(
        n.startswith(f"KODEX200 최근 수익률 ({D2.isoformat()} 기준)") for n in notes
    )
