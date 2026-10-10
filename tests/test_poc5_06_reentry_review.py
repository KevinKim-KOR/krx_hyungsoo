"""POC5-06 — 재진입 검토 API · 원장 연결 · 연구 산출물 · 부수효과(tmp 자료만).

설계 개정 2 §2 · §3 · §6 · §7 · §10-4 · §10-5 · §10-6. 보유 · 시세 DB · 캘린더 · 원장 사본 · 연구
산출물 폴더를 모두 tmp 로 돌린다(라이브 state 0).
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import sqlite3
import subprocess
import sys
import uuid
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import api as api_module
from app import holdings as holdings_module
from app import holdings_store as store
from app import market_data_store
from app.ledger_copy import store as copy_store
from app.market_benchmark_store import MARKET_BENCHMARK_DAILY_PRICE_DDL
from app.market_briefing import calendar as cal
from app.market_data_store import ETF_DAILY_PRICE_DDL, ETF_MASTER_DDL
from app.reentry_review import models as M
from app.reentry_review import review
from app.three_push_runtime import ledger_outcome, ledger_store

ETF, STOCK, OTHER = "069500", "005930", "102110"
REPO = Path(__file__).resolve().parents[1]


def _weekdays(start: str, n: int) -> list[str]:
    d, out = date.fromisoformat(start), []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


DATES = _weekdays("2023-01-02", 650)
TODAY = (date.fromisoformat(DATES[-1]) + timedelta(days=3)).isoformat()


def _closes(seed: int) -> list[float]:
    rnd, c, out = random.Random(seed), 10000.0, []
    for _ in DATES:
        c *= math.exp(rnd.gauss(0.0003, 0.012))
        out.append(round(c, 2))
    return out


def _market_db(path: Path, fetched_at: str = "2025-07-01T00:00:00Z") -> None:
    con = sqlite3.connect(path)
    con.execute(ETF_MASTER_DDL)
    con.execute(ETF_DAILY_PRICE_DDL)
    con.execute(MARKET_BENCHMARK_DAILY_PRICE_DDL)
    con.execute(
        "INSERT INTO etf_master (ticker, name, source, last_seen_at)"
        " VALUES (?, 'KODEX 200', 'FDR', 'x')",
        (ETF,),
    )
    for ticker, seed in ((ETF, 7), (STOCK, 9)):
        prev = None
        for d, c in zip(DATES, _closes(seed)):
            change = None if prev is None else c / prev - 1.0
            con.execute(
                "INSERT INTO etf_daily_price (ticker, date, close, change, source, fetched_at)"
                " VALUES (?, ?, ?, ?, 'FinanceDataReader', ?)",
                (ticker, d, c, change, fetched_at),
            )
            prev = c
    con.executemany(
        "INSERT INTO market_benchmark_daily_price"
        " VALUES ('KOSPI', 'KOSPI', ?, ?, 'NAVER_FDR', 'x')",
        [(d, 2500.0 + k) for k, d in enumerate(DATES)],
    )
    con.commit()
    con.close()


def _ledger(
    path: Path, items: list[tuple], outcomes=(), feedback=(), runs=None
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    for stmt in (*ledger_store.DDL, *ledger_outcome.DDL, *copy_store.PC_DDL):
        con.execute(stmt)
    for event_id, run_state in runs or [("ev1", "FINALIZED"), ("ev2", "FINALIZED")]:
        con.execute(
            "INSERT INTO evaluation_run (event_id, run_state, push_kind, contract_version,"
            " runtime_kst, runtime_date_kst, started_at, off_schedule, cohort, status)"
            " VALUES (?, ?, 'holdings_briefing', 'holdings_briefing.v1', ?, ?, 'x', 0,"
            " 'PRIMARY_LIVE', 'sent')",
            (event_id, run_state, f"{DATES[-2]}T09:15:00+09:00", DATES[-2]),
        )
        con.execute(
            "INSERT INTO delivery (event_id, delivery_status) VALUES (?, 'sent')",
            (event_id,),
        )
    con.executemany(
        "INSERT INTO signal_item (event_id, item_seq, subject_kind, subject_id, held, state,"
        " disposition, exposure, values_json, evaluable) VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?, 1)",
        items,
    )
    con.executemany(
        "INSERT INTO price_outcome (event_id, item_seq, series_id, horizon, price_basis,"
        " status, computed_at) VALUES (?, ?, ?, ?, 'KRX_ETF_UNADJUSTED', ?, 'x')",
        outcomes,
    )
    con.executemany(
        "INSERT INTO user_feedback (event_id, feedback_seq, helpfulness, action, memo,"
        " feedback_at) VALUES (?, ?, ?, NULL, ?, 'x')",
        feedback,
    )
    con.execute(
        "INSERT INTO ledger_sync_attempt (attempted_at, ok) VALUES ('2025-07-01T10:00:00+09:00', 1)"
    )
    con.commit()
    con.close()


LEDGER_ITEMS = [
    (
        "ev1",
        1,
        "ticker",
        ETF,
        "D5_8",
        "sent",
        "PRIMARY",
        json.dumps({"profit_loss_pct": -3.1}),
    ),
    ("ev1", 2, "ticker", OTHER, "D5_8", "not_selected", None, "{}"),
    (
        "ev2",
        1,
        "sector",
        "semis",
        "ENTRY_REVIEW",
        "sent",
        "PRIMARY",
        json.dumps({"ticker": ETF}),
    ),
    ("ev2", 2, "sector", "banks", "ENTRY_REVIEW", "suppressed", None, json.dumps({})),
    (
        "ev2",
        3,
        "index_group",
        "k200",
        "UP",
        "not_selected",
        None,
        json.dumps({"tickers": [OTHER, ETF]}),
    ),
]
LEDGER_OUTCOMES = [
    ("ev1", 1, f"krx_etf:{ETF}", 1, "MATURED"),
    ("ev1", 1, "benchmark:KOSPI", 1, "MATURED"),
    ("ev2", 3, f"krx_etf:{OTHER}", 1, "MATURED"),
    ("ev2", 3, f"krx_etf:{ETF}", 5, "PRICE_MISSING"),
]


@pytest.fixture
def env(tmp_path, monkeypatch):
    db = tmp_path / "market.sqlite"
    _market_db(db)
    caldir = tmp_path / "cal"
    caldir.mkdir()
    monkeypatch.setattr(market_data_store, "DEFAULT_DB_PATH", db)
    monkeypatch.setattr(cal, "CALENDAR_DIR", caldir)
    monkeypatch.setattr(review, "RESEARCH_ROOT", tmp_path / "research" / "poc5_06")
    monkeypatch.setattr(store, "today_kst", lambda: TODAY)
    f = holdings_module.HOLDINGS_FILE
    f.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {
            "ticker": ETF,
            "quantity": 10,
            "avg_buy_price": 10000,
            "name": "KODEX 200",
            "account_group": "ISA",
        },
        {
            "ticker": STOCK,
            "quantity": 3,
            "avg_buy_price": 70000,
            "name": "삼성전자",
            "account_group": "일반",
        },
    ]
    f.write_text(json.dumps({"holdings": rows}, ensure_ascii=False), encoding="utf-8")
    return {"db": db, "cal": caldir, "tmp": tmp_path}


@pytest.fixture
def client():
    return TestClient(api_module.app)


def _ids(client, ticker=ETF):
    hist = client.get("/holdings/trade-history").json()
    pos = next(p for p in hist["positions"] if p["ticker"] == ticker)
    return pos["position_id"], pos["cycles"][-1]["cycle_id"]


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


R = "/holdings/trade-history/reentry-review"


# ── GET 검토 창 ───────────────────────────────────────────────────────────────


def test_review_reads_only_and_shows_three_parts(env, client):
    _ledger(Path(copy_store.DEFAULT_DB_PATH), LEDGER_ITEMS, LEDGER_OUTCOMES)
    files = [holdings_module.HOLDINGS_FILE, env["db"], Path(copy_store.DEFAULT_DB_PATH)]
    before = [_sha(p) for p in files]
    pid, cid = _ids(client)
    r = client.get(R, params={"position_id": pid, "cycle_id": cid})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["selection"]["ticker"] == ETF and body["read_only"] is True
    mine = body["my_trades"]["summary"]
    assert (
        mine["purchase_date_unknown"] is True and mine["last_actual_sell_date"] is None
    )
    ps = body["stored_evidence"]["price_state"]
    assert ps["status"] == M.OK and ps["t"] == DATES[-1]
    assert set(ps["features"]) == {"chg5", "chg20", "chg60", "vol20", "from_high60"}
    assert ps["price_basis_label"].startswith("저장 종가(네이버 계열")
    assert ps["axis"]["label"].startswith("공식 휴장 목록이 아닌")
    assert ps["stale"] is False  # TODAY 직전 거래일 = 마지막 저장일
    assert body["stored_evidence"]["market_flow"]["read_only"] is True
    assert body["ml"]["available"] is True
    assert (
        body["read_basis"]["holdings_status"] == "V1"
        and body["read_basis"]["revision"] == 0
    )
    assert M.NOT_ADVICE in body["notes"]
    assert [_sha(p) for p in files] == before  # 보유 · 시세 · 원장 사본 불변
    assert not (env["tmp"] / "research").exists()  # 조회는 산출물을 만들지 않는다
    assert "하락 위험" not in json.dumps(body, ensure_ascii=False)
    notes = " ".join(body["notes"])  # 가격 의미는 '분배금 미반영'으로 바꾸지 않는다(§4)
    assert "배당" not in notes and "분배락 조정 흔적" in notes


def test_review_get_does_not_import_sklearn(env, tmp_path):
    script = tmp_path / "probe.py"
    script.write_text(
        "import sys, json\n"
        "from pathlib import Path\n"
        "from app import holdings as h, holdings_store as st, market_data_store as mds\n"
        "from app.market_briefing import calendar as cal\n"
        "from app.ledger_copy import store as cs\n"
        f"h.HOLDINGS_FILE = Path({str(holdings_module.HOLDINGS_FILE)!r})\n"
        f"mds.DEFAULT_DB_PATH = Path({str(env['db'])!r})\n"
        f"cal.CALENDAR_DIR = Path({str(env['cal'])!r})\n"
        f"cs.DEFAULT_DB_PATH = Path({str(tmp_path / 'no_ledger.sqlite')!r})\n"
        f"st.today_kst = lambda: {TODAY!r}\n"
        "from app import holdings_history_view as hv\n"
        "from app.reentry_review import review\n"
        "p = [x for x in hv.history()['positions'] if x['ticker'] == '069500'][0]\n"
        "out = review.build_review(p['position_id'], p['cycles'][-1]['cycle_id'])\n"
        "print(json.dumps({'status': out['stored_evidence']['price_state']['status'],"
        " 'sklearn': 'sklearn' in sys.modules}))\n",
        encoding="utf-8",
    )
    res = subprocess.run(
        [sys.executable, "-B", str(script)],
        cwd=REPO,
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(REPO), "PATH": "/usr/bin:/bin"},
    )
    assert res.returncode == 0, res.stderr
    out = json.loads(res.stdout.strip().splitlines()[-1])
    assert out == {"status": M.OK, "sklearn": False}


def test_review_for_stock_and_missing_selection(env, client):
    pid, cid = _ids(client, STOCK)
    body = client.get(R, params={"position_id": pid, "cycle_id": cid}).json()
    assert body["stored_evidence"]["price_state"]["status"] == M.NOT_ETF
    assert body["ml"]["available"] is False
    assert body["stored_evidence"]["ledger"]["status"] == M.NO_COPY
    assert not Path(copy_store.DEFAULT_DB_PATH).exists()  # 사본을 만들지 않는다
    r = client.get(R, params={"position_id": pid, "cycle_id": "nope"})
    assert r.status_code == 404 and "다시 여세요" in r.json()["detail"]


def test_v1_ids_kept_by_first_save_and_unknown_ids_get_404(env, client):
    pid, cid = _ids(client)
    put = client.put(
        "/holdings/trade-history",
        json={
            "record_id": str(uuid.uuid4()),
            "base_revision": 0,
            "action": "buy",
            "position_id": pid,
            "trade": {"trade_date": DATES[-1], "price": "10000", "quantity": "1"},
        },
    )
    assert put.status_code == 200, put.text
    after = client.get(R, params={"position_id": pid, "cycle_id": cid})
    assert after.status_code == 200
    basis = after.json()["read_basis"]
    assert basis["holdings_status"] == "V2" and basis["revision"] == 1
    # V1 → V2 로 바뀌어도 첫 저장은 같은 줄 ID 를 확정한다 — 문서에 없는 ID 는 404
    r = client.get(R, params={"position_id": "x" * 10, "cycle_id": cid})
    assert r.status_code == 404


def test_market_db_read_failure_is_500(env, client):
    pid, cid = _ids(client)
    env["db"].write_bytes(b"not a sqlite file" * 100)
    r = client.get(R, params={"position_id": pid, "cycle_id": cid})
    assert r.status_code == 500 and "시세 DB 조회 실패" in r.json()["detail"]


# ── 원장 연결(§10-4) ─────────────────────────────────────────────────────────


def test_ledger_links_three_kinds_and_only_own_outcomes(env, client):
    _ledger(
        Path(copy_store.DEFAULT_DB_PATH),
        LEDGER_ITEMS + [("ev3", 1, "ticker", ETF, "D5_8", "sent", "PRIMARY", "{}")],
        LEDGER_OUTCOMES,
        feedback=[("ev1", 1, "HELPFUL", "메모 원문"), ("ev1", 2, "NEUTRAL", None)],
        runs=[("ev1", "FINALIZED"), ("ev2", "FINALIZED"), ("ev3", "STARTED")],
    )
    pid, cid = _ids(client)
    ev = client.get(R, params={"position_id": pid, "cycle_id": cid}).json()
    led = ev["stored_evidence"]["ledger"]
    assert led["status"] == M.OK and led["synced_at"].startswith("2025-07-01")
    got = {(i["event_id"], i["item_seq"]): i for i in led["items"]}
    assert set(got) == {
        ("ev1", 1),
        ("ev2", 1),
        ("ev2", 3),
    }  # 비FINALIZED · 다른 종목 · 대표 없는 사업군 제외
    assert got[("ev1", 1)]["link_kind"] == M.LINK_SUBJECT
    assert got[("ev2", 1)]["link_kind"] == M.LINK_SECTOR_REPRESENTATIVE
    assert got[("ev2", 3)]["link_kind"] == M.LINK_INDEX_GROUP_MEMBER
    assert [o["series_id"] for o in got[("ev1", 1)]["outcomes"]] == [f"krx_etf:{ETF}"]
    assert [o["series_id"] for o in got[("ev2", 3)]["outcomes"]] == [f"krx_etf:{ETF}"]
    assert got[("ev1", 1)]["view"] == M.VIEW_DELIVERED
    assert got[("ev2", 3)]["view"] == M.VIEW_OBSERVED
    assert got[("ev2", 3)]["exposure"] == "NONE"
    fb = got[("ev1", 1)]["feedback"]
    assert (
        fb["scope"] == "EVENT"
        and fb["count"] == 2
        and fb["latest"]["feedback_seq"] == 2
    )
    text = json.dumps(ev, ensure_ascii=False)
    assert "profit_loss_pct" not in text and "values_json" not in text


def test_ledger_read_failure_is_reported_not_zero_rows(env, client):
    p = Path(copy_store.DEFAULT_DB_PATH)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"broken" * 200)
    pid, cid = _ids(client)
    body = client.get(R, params={"position_id": pid, "cycle_id": cid}).json()
    assert body["stored_evidence"]["ledger"]["status"] == M.READ_FAILED
    assert (
        body["stored_evidence"]["price_state"]["status"] == M.OK
    )  # 다른 근거는 그대로


@pytest.mark.parametrize(
    "damage",
    [
        "ledger_meta",
        "user_feedback",
        "ledger_sync_attempt",
        "delivery",
        "evaluation_run",
        "price_outcome_after_made",
    ],
)
def test_damaged_copy_is_not_read_as_empty(env, client, damage):
    """사본 손상(04 판정과 같은 규칙)을 '평가 없음' · '집계 중' · 동기화 시각 없음으로 바꾸지 않는다."""
    p = Path(copy_store.DEFAULT_DB_PATH)
    _ledger(
        p, LEDGER_ITEMS, LEDGER_OUTCOMES, feedback=[("ev1", 1, "HELPFUL", "메모 원문")]
    )
    con = sqlite3.connect(p)
    if damage == "price_outcome_after_made":
        con.execute(
            "INSERT INTO ledger_meta (key, value, recorded_at)"
            " VALUES ('schema_version.price_outcome', 'price_outcome.v1', 'x')"
        )
        con.execute("DROP TABLE price_outcome")
    else:
        con.execute(f"DROP TABLE {damage}")
    con.commit()
    con.close()
    pid, cid = _ids(client)
    body = client.get(R, params={"position_id": pid, "cycle_id": cid}).json()
    led = body["stored_evidence"]["ledger"]
    assert led["status"] == M.READ_FAILED and led["items"] == []
    assert led["status_text"].startswith("원장 사본 손상 — ") and led["problems"]
    # 다른 근거는 그대로 · ML 은 원장을 쓰지 않는다(계속 가능 · 원장 상태는 산출물에 남긴다)
    assert body["stored_evidence"]["price_state"]["status"] == M.OK
    ml = _ml(client, pid, cid)
    assert ml.status_code == 200 and ml.json()["status"] == M.OK
    folder = next((env["tmp"] / "research" / "poc5_06").iterdir())
    snap = json.loads((folder / "input_snapshot.json").read_text(encoding="utf-8"))
    assert snap["ledger_status"] == M.READ_FAILED and snap["ledger_ids"] == []
    assert snap["ledger_status_text"] == led["status_text"]


def test_unreadable_link_values_are_damage_not_zero_alerts(env, client):
    broken = '{"ticker": "%s"' % ETF  # 닫히지 않은 JSON
    bad = ("ev2", 4, "sector", "semis2", "ENTRY_REVIEW", "sent", None, broken)
    _ledger(Path(copy_store.DEFAULT_DB_PATH), LEDGER_ITEMS + [bad], LEDGER_OUTCOMES)
    pid, cid = _ids(client)
    led = client.get(R, params={"position_id": pid, "cycle_id": cid}).json()[
        "stored_evidence"
    ]["ledger"]
    assert led["status"] == M.READ_FAILED and led["items"] == []
    assert "values_json 해석 불가(ev2 · item 4)" in led["status_text"]


def test_copy_before_outcome_table_and_before_sync_is_normal(env, client):
    """결과 표를 만든 기록 없이 price_outcome 이 없음 = 성숙 전(정상) · 성공 동기화 기록 0 = 시각 없음(정상)."""
    p = Path(copy_store.DEFAULT_DB_PATH)
    _ledger(
        p, LEDGER_ITEMS, LEDGER_OUTCOMES, feedback=[("ev1", 1, "HELPFUL", "메모 원문")]
    )
    con = sqlite3.connect(p)
    con.execute("DROP TABLE price_outcome")
    con.execute("DELETE FROM ledger_sync_attempt")
    con.commit()
    con.close()
    pid, cid = _ids(client)
    led = client.get(R, params={"position_id": pid, "cycle_id": cid}).json()[
        "stored_evidence"
    ]["ledger"]
    assert led["status"] == M.OK and led["synced_at"] is None
    own = next(i for i in led["items"] if i["event_id"] == "ev1")
    assert own["outcomes"] == [] and own["pending_horizons"] == [1, 5, 20]
    assert own["feedback"]["count"] == 1  # 평가는 그대로


# ── POST ML · 산출물 ─────────────────────────────────────────────────────────


def _ml(client, pid, cid):
    return client.post(R + "/ml", json={"position_id": pid, "cycle_id": cid})


def test_ml_run_writes_artifacts_and_is_deterministic(env, client):
    _ledger(
        Path(copy_store.DEFAULT_DB_PATH),
        LEDGER_ITEMS,
        LEDGER_OUTCOMES,
        feedback=[("ev1", 1, "HELPFUL", "메모 원문")],
    )
    pid, cid = _ids(client)
    files = [holdings_module.HOLDINGS_FILE, env["db"], Path(copy_store.DEFAULT_DB_PATH)]
    before = [_sha(p) for p in files]
    a, b = _ml(client, pid, cid), _ml(client, pid, cid)
    assert a.status_code == 200, a.text
    ra, rb = a.json(), b.json()
    assert ra["status"] == M.OK and ra["target_name"] == M.TARGET_NAME
    assert ra["canonical_sha256"] == rb["canonical_sha256"]
    assert ra["result"] == rb["result"]
    assert ra["result"]["overall"]["verdict_text"] in M.VERDICT_TEXT.values()
    folders = sorted((env["tmp"] / "research" / "poc5_06").iterdir())
    assert len(folders) == 2 and {f.name for f in folders[0].iterdir()} == {
        "review.json",
        "input_snapshot.json",
    }
    rv = json.loads((folders[0] / "review.json").read_text(encoding="utf-8"))
    snap = json.loads((folders[0] / "input_snapshot.json").read_text(encoding="utf-8"))
    assert rv["recipe"]["model"].startswith("StandardScaler -> Ridge")
    assert rv["libraries"]["scikit-learn"] and rv["axis"]["label"].startswith(
        "공식 휴장"
    )
    assert len(snap["hash_input"]["prices"]) == len(DATES)
    assert snap["ledger_ids"][0]["feedback"] == {
        "event_id": "ev1",
        "feedback_seq": 1,
        "helpfulness": "HELPFUL",
    }
    assert "메모 원문" not in json.dumps(snap, ensure_ascii=False)
    # 입력 snapshot 에도 축 표기(§4)
    assert snap["axis_label"].startswith("공식 휴장 목록이 아닌")
    assert snap["price_basis_label"].startswith("저장 종가(네이버 계열")
    assert [_sha(p) for p in files] == before  # 보유 · 시세 DB · 원장 사본 불변
    assert not list((env["tmp"] / "research" / "poc5_06").glob(".*"))  # 임시 폴더 없음


def test_fetched_at_changes_hash_but_not_estimate(env, client):
    pid, cid = _ids(client)
    first = _ml(client, pid, cid).json()
    env["db"].unlink()
    _market_db(env["db"], fetched_at="2025-08-01T00:00:00Z")
    second = _ml(client, pid, cid).json()
    assert first["canonical_sha256"] != second["canonical_sha256"]
    assert first["result"] == second["result"]


def test_feedback_does_not_change_ml_output(env, client):
    p = Path(copy_store.DEFAULT_DB_PATH)
    _ledger(p, LEDGER_ITEMS, LEDGER_OUTCOMES)
    pid, cid = _ids(client)
    first = _ml(client, pid, cid).json()
    con = sqlite3.connect(p)
    con.execute(
        "INSERT INTO user_feedback VALUES ('ev1', 1, 'UNHELPFUL_CONFUSING', NULL, NULL, 'x')"
    )
    con.commit()
    con.close()
    second = _ml(client, pid, cid).json()
    assert first["result"] == second["result"]
    assert first["canonical_sha256"] == second["canonical_sha256"]


def test_ml_not_etf_bad_payload_and_missing_selection(env, client):
    pid, cid = _ids(client, STOCK)
    r = _ml(client, pid, cid)
    assert r.status_code == 200 and r.json()["status"] == M.NOT_ETF
    assert client.post(R + "/ml", json={"position_id": pid}).status_code == 422
    assert (
        client.post(
            R + "/ml", json={"position_id": pid, "cycle_id": "x" * 65}
        ).status_code
        == 422
    )
    assert _ml(client, pid, "nope").status_code == 404


def test_half_written_artifact_is_not_left_behind(env, client, monkeypatch):
    real = Path.write_text

    def fail_second(self, *a, **kw):
        if self.name == "input_snapshot.json":
            raise OSError("disk full")
        return real(self, *a, **kw)

    pid, cid = _ids(client)
    monkeypatch.setattr(Path, "write_text", fail_second)
    r = _ml(client, pid, cid)
    monkeypatch.setattr(Path, "write_text", real)
    assert r.status_code == 500 and "결과를 보이지 않습니다" in r.json()["detail"]
    root = env["tmp"] / "research" / "poc5_06"
    assert list(root.iterdir()) == []  # review.json 만 있는 폴더 · 임시 폴더 모두 없음


def test_artifact_save_failure_is_500_not_a_result(env, client, monkeypatch):
    blocker = env["tmp"] / "research_is_a_file"
    blocker.write_text("x", encoding="utf-8")
    monkeypatch.setattr(review, "RESEARCH_ROOT", blocker / "poc5_06")
    pid, cid = _ids(client)
    r = _ml(client, pid, cid)
    assert r.status_code == 500 and "결과를 보이지 않습니다" in r.json()["detail"]


# ── 상태 구분(§7 부족 · 장애 · §10-2 · §10-3) ─────────────────────────────────


def _get_ps(client, pid, cid):
    body = client.get(R, params={"position_id": pid, "cycle_id": cid}).json()
    return body, body["stored_evidence"]["price_state"]


def test_late_prices_are_marked_this_date_review(env, client, monkeypatch):
    later = (date.fromisoformat(DATES[-1]) + timedelta(days=7)).isoformat()
    monkeypatch.setattr(store, "today_kst", lambda: later)
    pid, cid = _ids(client)
    _, ps = _get_ps(client, pid, cid)
    assert ps["stale"] is True and ps["stale_note"] == M.STALE_NOTE
    assert ps["t"] == DATES[-1] < ps["expected_completed_date"]
    ml = _ml(client, pid, cid).json()  # 늦어도 그 저장일 기준 연구는 한다(§10-6)
    assert ml["status"] == M.OK and ml["stale"] is True
    assert ml["stale_note"] == M.STALE_NOTE and ml["t"] == DATES[-1]


def test_axis_uncertain_keeps_history_and_ledger(env, client):
    con = sqlite3.connect(env["db"])
    con.execute(
        "DELETE FROM market_benchmark_daily_price WHERE date >= ?", (DATES[-3],)
    )  # 파일 없는 해의 KOSPI 최신일 < t
    con.commit()
    con.close()
    pid, cid = _ids(client)
    body, ps = _get_ps(client, pid, cid)
    assert ps["status"] == M.AXIS_UNCERTAIN and ps["features"] is None
    assert body["my_trades"]["summary"]["status"] == "OPEN"  # 내 거래 · 원장은 그대로
    assert body["stored_evidence"]["ledger"]["status"] == M.NO_COPY
    ml = _ml(client, pid, cid).json()
    assert ml["status"] == M.AXIS_UNCERTAIN and "final" not in ml["result"]


def test_broken_t_window_is_price_basis_unconfirmed_through_api(env, client):
    con = sqlite3.connect(env["db"])
    con.execute(
        "UPDATE etf_daily_price SET change = change + 0.01 WHERE ticker = ? AND date = ?",
        (ETF, DATES[-10]),
    )
    con.execute(
        "DELETE FROM etf_daily_price WHERE ticker = ? AND date = ?", (ETF, DATES[-30])
    )
    con.commit()
    con.close()
    pid, cid = _ids(client)
    _, ps = _get_ps(client, pid, cid)
    assert ps["status"] == M.PRICE_BASIS_UNCONFIRMED and ps["features"] is None
    assert "저장 종가 없음" in ps["reason"] and "불일치" in ps["reason"]
    ml = _ml(client, pid, cid).json()
    assert ml["status"] == M.PRICE_BASIS_UNCONFIRMED and "final" not in ml["result"]
    assert ml["reason"] == ps["reason"]


def test_no_price_is_not_called_individual_stock(env, client):
    pid, cid = _ids(client)
    con = sqlite3.connect(env["db"])
    con.execute("DELETE FROM etf_daily_price WHERE ticker = ?", (ETF,))
    con.commit()
    _, ps = _get_ps(client, pid, cid)
    assert ps["status"] == M.NO_PRICE and "저장 종가 없음" in ps["reason"]
    con.execute("DROP TABLE etf_master")  # 확인 불가 ≠ 개별주
    con.commit()
    con.close()
    body, ps = _get_ps(client, pid, cid)
    assert ps["status"] == M.NO_PRICE and "확인 불가" in ps["reason"]
    assert body["ml"]["available"] is False
    assert _ml(client, pid, cid).json()["status"] == M.NO_PRICE


def test_closed_by_adjustment_keeps_real_sell_only(env, client):
    pid, cid = _ids(client)

    def cmd(rev, action, **kw):
        body = {
            "record_id": str(uuid.uuid4()),
            "base_revision": rev,
            "action": action,
            **kw,
        }
        res = client.put("/holdings/trade-history", json=body)
        assert res.status_code == 200, res.text
        return res.json()

    cmd(
        0,
        "sell",
        position_id=pid,
        trade={"trade_date": DATES[-5], "price": "11000", "quantity": "4"},
    )
    rows = [
        dict(h)
        for h in client.get("/holdings").json()["holdings"]
        if h["ticker"] != ETF
    ]
    put = client.put(
        "/holdings", json={"holdings": rows, "revision": 1}
    )  # 남은 6주 = 입력 정정 종료
    assert put.status_code == 200, put.text
    hist = client.get("/holdings/trade-history", params={"position_id": pid}).json()
    cyc = hist["positions"][0]["cycles"][-1]
    assert cyc["closed_by"] == "ADJUSTMENT"
    body = client.get(
        R, params={"position_id": pid, "cycle_id": cyc["cycle_id"]}
    ).json()
    mine = body["my_trades"]["summary"]
    assert (
        mine["closed_by_adjustment"] is True
        and mine["last_actual_sell_date"] == DATES[-5]
    )
    assert any("정정일은 매도일이 아니며" in n for n in body["my_trades"]["notes"])
