"""POC6-32 검증자 r1 정정 시험 — F1(한 응답 = 한 읽기) · F3(새 GET 이 파일 · 표를 만들거나 바꾸지 않음).

F1 계약: 한 주간 응답의 ③ R1 구성 요약 · R4 보유 겹침(노출) · 복사 글 · 넘기기 묶음(구성 · 겹침 · 자료 상태)은 고른 후보의
구성 · 원천일 확인 기록 · ETF 목록 · 보유 쪽 구성을 **한 읽기 트랜잭션**으로 읽은 사본에서만 나온다.
- 검증자 재현: 후보가 직접 보유한 주식 A 를 65% 편입 → 옛 코드가 두 번째로 읽던 자리(보유 파일 읽기)에서 같은 구성일
  저장본을 주식 B 65% 로 바꿈 → 응답 · 복사 글 · 저장 후 다시 연 기록이 모두 같은 짝(A 와 A 로 계산한 노출 · 또는 B 와 B).
- 읽는 동안 다른 연결의 저장은 끼어들지 못함(공유 잠금 유지) · 노출 계산은 기존 `load` 와 같은 결과(지문 포함).
- 읽기 트랜잭션이 끝난 **뒤**의 저장(트랜잭션 직후 · `read_candidate` 직후 · 구성 요약을 만들기 직전 · 트랜잭션 안에서
  막혀 기다리던 다른 스레드의 저장)은 그 응답에 들어가지 않음 — 응답 · 겹침 숫자 · 복사 글 · 넘기기 묶음 · 저장 후 다시 연
  기록 모두 저장 전 짝(주식 A · 100.00) · 다음 조회는 바뀐 짝(주식 B · 0.00 · 저장이 실제로 됐음).
F3 계약: 주간 GET 두 곳(마지막 기록 · 기록 해석)은 기록 DB 가 없으면 만들지 않고 · 있으면 바이트 · 수정 시각이 그대로 ·
옛 스키마도 마이그레이션 없이 읽음. 새 시장 GET(`/market/evidence` · 주간 · `/market/etf-official` ·
`/market/constituents/summary`)은 시장 DB 파일이 없으면 만들지 않음.
마지막 기록(판정 Q8 (a) '가장 최근 1건') = 주간 출처 기록 중 저장 시각이 가장 늦은 것 · 같은 시각이면 id 내림차순 ·
더 늦은 다른 출처 기록은 보지 않음(저장소 목록과 같은 순서).
임시 폴더 · 임시 DB · 합성 종목만 쓴다(라이브 DB · 실제 보유 없음).
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import api as api_module
from app import api_decision_sessions, api_etf_compare, decision_evidence_store
from app import api_weekly_review as W
from app import constituents_pair_exposure_io as IO
from app import decision_evidence_readonly as RO
from app import etf_constituents_store, etf_official_info, holdings, market_cache
from app import market_data_store as MDS
from app import market_evidence as ME
from app import weekly_candidate_reads as CR
from app import weekly_candidate_review as wcr
from app.etf_constituents_fetcher import NAVER_STOCK_SOURCE
from app.etf_constituents_status import LOG_OK
from app.etf_constituents_store import ConstituentRow, replace_constituents_snapshot
from app.holdings import Holding
from app.market_cache import MarketQuote
from app.market_data_store import EtfMasterRow, upsert_etf_master
from tests import test_poc6_32_market_evidence as MEX
from tests.test_poc6_31_pair_exposure import COND
from tests.test_poc6_32_weekly_review import FIX, SEL, _ans, _draft

A, B, OTHER, HETF = "005930", "000660", "035420", "H00001"
ASOF = "2026-11-13"
A65 = [(A, "주식A", 65.0), (OTHER, "기타", 35.0)]
B65 = [(B, "주식B", 65.0), (OTHER, "기타", 35.0)]


def rows(etf, items):
    return [
        ConstituentRow(
            etf_ticker=etf,
            asof=ASOF,
            source=NAVER_STOCK_SOURCE,
            rank=i + 1,
            constituent_ticker=code,
            constituent_name=name,
            weight_pct=w,
            constituent_key=code,
            constituent_isin=f"KR7{code}003",
            market_type="0",
        )
        for i, (code, name, w) in enumerate(items)
    ]


def save(db, items, etf=SEL):
    """원천일 확인 · 원천 전체(같은 구성일이면 저장본을 바꿈)."""
    replace_constituents_snapshot(
        rows(etf, items), log_status=LOG_OK, confirm=True, complete=True, db_path=db
    )


def seed(db, items=A65):
    upsert_etf_master(
        [
            EtfMasterRow(SEL, "고른 ETF", "1", 1.0, 1, 1.0),
            EtfMasterRow(HETF, "보유 ETF", "1", 1.0, 1, 1.0),
        ],
        source="TestSource",
        db_path=db,
    )
    save(db, items)


def held(*tickers):
    return [
        Holding(ticker=t, quantity=10, avg_buy_price=100.0, name=f"보유{t}")
        for t in tickers
    ]


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


@pytest.fixture
def env(monkeypatch, tmp_path):
    """모든 DB 경로 = 임시(아직 없음) · 목록 요약 = 11/16 고정 자료 · 보유 · 시세 = 합성."""
    mdb = tmp_path / "market" / "market.sqlite"
    ddb = tmp_path / "decision" / "decision.sqlite"
    for mod, name in (
        (etf_constituents_store, "DEFAULT_DB_PATH"),
        (MDS, "DEFAULT_DB_PATH"),
        (api_etf_compare, "MARKET_DB_PATH"),
    ):
        monkeypatch.setattr(mod, name, mdb)
    monkeypatch.setattr(decision_evidence_store, "DEFAULT_DB_PATH", ddb)
    monkeypatch.setattr(api_decision_sessions, "DEFAULT_DB_PATH", ddb)
    monkeypatch.setattr(etf_official_info, "META_DIR", tmp_path / "meta")
    monkeypatch.setattr(api_etf_compare, "_official", lambda: ({}, {"status": "ok"}))
    monkeypatch.setattr(
        api_etf_compare, "_dictionary", lambda: (None, {"status": "unavailable"})
    )
    monkeypatch.setattr(api_etf_compare, "_held_tickers", lambda: ([], "none"))
    monkeypatch.setattr(W, "build_summary", lambda **kw: FIX["summary"])
    monkeypatch.setattr(ME, "read_quick_quotes", lambda: MEX.quick())
    monkeypatch.setattr(holdings, "load", lambda: held(A))
    q = {t: MarketQuote(t, None, 100.0, "2026-11-13T15:40:00+09:00") for t in (A, HETF)}
    monkeypatch.setattr(market_cache, "get_all", lambda: q)
    return {
        "mdb": mdb,
        "ddb": ddb,
        "tmp": tmp_path,
        "client": TestClient(api_module.app),
    }


# ── F1 한 응답 = 한 읽기 ──────────────────────────────────────────────────────

# 고른 ETF 주요 주식 → (그 구성으로 계산한 노출 최댓값, 복사 글 범위) — 직접 보유 = 주식 A 만
PAIRS = {"주식A": ("100.00", "0.00% ~ 100.00%"), "주식B": ("0.00", "0.00% ~ 0.00%")}


def test_f1_snapshot_replaced_mid_request_never_mixes(env, monkeypatch):
    mdb, c = env["mdb"], env["client"]
    seed(mdb)
    monkeypatch.setattr(ME, "build_market_evidence", lambda **kw: None)
    swapped = []

    def hold_then_replace():
        # 옛 코드가 구성 요약을 읽은 뒤 노출 계산에서 다시 읽기 직전에 부르던 자리(보유 파일 읽기)
        if not swapped:
            save(mdb, B65)
            swapped.append(True)
        return held(A)

    monkeypatch.setattr(holdings, "load", hold_then_replace)
    r = c.get("/weekly/etf-check", params={"selected": SEL}).json()
    assert swapped == [True]
    top = r["selected_review"]["constituents"]["top_stocks"][0]
    assert top["name"] in PAIRS and top["weight_pct"] == 65.0
    mx, rng = PAIRS[top["name"]]
    other = ({"주식A", "주식B"} - {top["name"]}).pop()
    # 응답 안 — R1 과 R4(겹침) 가 같은 구성
    assert r["overlap"]["numbers"]["max"] == mx
    assert r["selected_review"]["overlap"]["numbers"]["max"] == mx
    # 복사 글 · 넘기기 묶음 — 같은 짝 · 다른 주식 이름 없음
    for text in (
        r["copy_text"],
        json.dumps(r["data_quality_snapshot"], ensure_ascii=False),
    ):
        assert f"{top['name']} 65.00%" in text and f"보유 노출 범위 {rng}" in text
        assert other not in text
    cs = r["constituent_snapshot"]["constituents"]
    assert cs["top_stocks"][0]["name"] == top["name"]
    # 저장 → 다시 열기 — 같은 짝 그대로
    saved = c.post("/decision/sessions", json=_draft(r))
    assert saved.status_code == 200
    rec = c.get(f"/decision/sessions/{saved.json()['id']}").json()["record"]
    got = rec["constituent_snapshot"]["constituents"]["top_stocks"][0]["name"]
    assert got == top["name"] and rec["overlap_snapshot"]["numbers"]["max"] == mx
    assert f"보유 노출 범위 {rng}" in rec["question_text"]
    assert other not in rec["question_text"]


def test_f1_candidate_reads_hold_one_read_transaction(env, monkeypatch):
    """ETF 목록을 읽은 뒤 · 구성을 읽기 전에 다른 연결이 저장하려 하면 막힌다(공유 잠금 유지 = 한 시점)."""
    mdb = env["mdb"]
    seed(mdb)
    save(mdb, [(A, "주식A", 50.0), (OTHER, "기타", 50.0)], etf=HETF)
    monkeypatch.setattr(holdings, "load", lambda: held(A, HETF))
    real = CR.holding_weights
    blocked = []

    def weights_then_try_write(enriched, etf_tickers):
        con = sqlite3.connect(str(mdb), timeout=0.05)
        try:
            con.execute(
                "UPDATE etf_constituents SET constituent_ticker = ?, "
                "constituent_name = '주식B' WHERE constituent_ticker = ?",
                (B, A),
            )
            con.commit()
            blocked.append(False)
        except sqlite3.OperationalError:
            blocked.append(True)
        finally:
            con.close()
        return real(enriched, etf_tickers)

    monkeypatch.setattr(CR, "holding_weights", weights_then_try_write)
    got = CR.read_candidate(SEL, db_path=mdb, condition=COND)
    assert blocked == [True]
    assert got["constituents"]["top_stocks"][0]["name"] == "주식A"
    assert got["constituents"]["state"] == "full" and got["exposure_error"] is False
    # 노출 계산 = 기존 `load` 와 같은 결과(지문 포함 · 보유 ETF 구성도 같은 읽기) — 계산 변경 없음
    monkeypatch.setattr(CR, "holding_weights", real)
    assert got["exposure"] == IO.load(SEL, None, COND, db_path=mdb)
    assert got["names"] == {SEL: "고른 ETF", HETF: "보유 ETF"}


def test_f1_read_failure_marks_both_unread_not_missing(env, monkeypatch):
    mdb = env["mdb"]
    seed(mdb)

    def boom(*a, **k):
        raise sqlite3.OperationalError("locked")

    real = CR.snapshots_in
    monkeypatch.setattr(CR, "snapshots_in", boom)
    got = CR.read_candidate(SEL, db_path=mdb, condition=COND)
    assert (got["constituents"]["state"], got["exposure"], got["exposure_error"]) == (
        "error",
        None,
        True,
    )
    assert got["names"] is None
    # 보유 시세만 못 읽음 = 노출만 '읽지 못함' · 구성은 그대로
    monkeypatch.setattr(CR, "snapshots_in", real)
    monkeypatch.setattr(market_cache, "get_all", boom)
    got = CR.read_candidate(SEL, db_path=mdb, condition=COND)
    assert got["constituents"]["state"] == "full" and got["exposure_error"] is True


# ── F1 회귀(r1 G2) — 읽기 트랜잭션 뒤의 저장은 그 응답에 들어가지 않음 ─────────────────
# 저장 시점: 트랜잭션 직후(`_read_db` 반환 직후 · 구성 요약 · 노출 계산 전) · `read_candidate` 반환 직후(API 가 공식
# 기준정보 · 시장 근거 · 조립 전) · ③ 구성 요약을 만들기 직전(`summary_of`) · 다른 스레드가 트랜잭션 안(ETF 목록 뒤 ·
# 구성 뒤)에서 저장을 시도 → 공유 잠금에 막혀 기다리다 트랜잭션이 끝나면 저장(구성 요약 · 노출 계산 전에 끝나게 기다림).
AFTER_TXN = ("after_read_db", "after_read_candidate", "before_summary")
IN_TXN = ("thread_after_master", "thread_after_snapshots")


def _hook_replace(monkeypatch, hook, mdb, log):
    """`hook` 자리에서 같은 구성일 저장본을 주식 A → 주식 B 로 바꾼다(한 번) · log = 저장 기록."""

    def replace():
        if not log.get("saved"):
            save(mdb, B65)
            log["saved"] = hook

    def after(obj, name):
        real = getattr(obj, name)

        def wrapped(*a, **k):
            out = real(*a, **k)
            replace()
            return out

        monkeypatch.setattr(obj, name, wrapped)

    if hook == "after_read_db":
        after(CR, "_read_db")
    elif hook == "after_read_candidate":
        after(CR, "read_candidate")
    elif hook == "before_summary":
        real = wcr.summary_of

        def summary_then(detail):
            replace()
            return real(detail)

        monkeypatch.setattr(wcr, "summary_of", summary_then)
    else:
        target = "master_in" if hook == "thread_after_master" else "snapshots_in"
        real_in, real_db = getattr(CR, target), CR._read_db
        errors: list[BaseException] = []

        def writer():
            try:
                replace()  # 다른 연결 · 기본 대기 5초 — 읽기 트랜잭션이 끝나야 저장된다
            except BaseException as e:  # pragma: no cover — 실패면 아래 단언이 알린다
                errors.append(e)

        def in_txn(*a, **k):
            out = real_in(*a, **k)
            if "thread" not in log:
                t = threading.Thread(target=writer)
                t.start()
                t.join(0.3)
                log["thread"], log["blocked"] = t, t.is_alive()
            return out

        def db_then_join(*a, **k):
            out = real_db(*a, **k)  # 연결이 닫힌 뒤 — 기다리던 저장이 이제 끝난다
            log["thread"].join(10)
            log["joined"] = not log["thread"].is_alive()
            log["errors"] = errors
            return out

        monkeypatch.setattr(CR, target, in_txn)
        monkeypatch.setattr(CR, "_read_db", db_then_join)


@pytest.mark.parametrize("hook", AFTER_TXN + IN_TXN)
def test_f1_write_after_read_transaction_never_reaches_response(env, monkeypatch, hook):
    mdb, c = env["mdb"], env["client"]
    seed(mdb)
    monkeypatch.setattr(ME, "build_market_evidence", lambda **kw: None)
    log: dict = {}
    _hook_replace(monkeypatch, hook, mdb, log)
    r = c.get("/weekly/etf-check", params={"selected": SEL}).json()
    assert log["saved"] == hook  # 그 자리에서 실제로 저장됨
    if hook in IN_TXN:
        # 트랜잭션 안에서는 막혔고(공유 잠금) · 트랜잭션이 끝난 뒤 · 응답을 만들기 전에 저장이 끝남
        assert log["blocked"] is True and log["joined"] is True
        assert log["errors"] == []
    mx, rng = PAIRS["주식A"]
    # ③ R1 구성 요약 · R4 겹침 숫자 = 저장 전 짝(주식 A · 100.00)
    top = r["selected_review"]["constituents"]["top_stocks"][0]
    assert (top["name"], top["weight_pct"]) == ("주식A", 65.0)
    assert r["overlap"]["numbers"]["max"] == mx == "100.00"
    assert r["selected_review"]["overlap"]["numbers"]["max"] == mx
    # 복사 글 · 넘기기 묶음(자료 상태 · 구성 · 겹침)
    dq = json.dumps(r["data_quality_snapshot"], ensure_ascii=False)
    for text in (r["copy_text"], dq):
        assert "주식A 65.00%" in text and f"보유 노출 범위 {rng}" in text
        assert "주식B" not in text
    cs = r["constituent_snapshot"]["constituents"]
    assert cs["top_stocks"][0]["name"] == "주식A"
    assert "주식B" not in json.dumps(r["constituent_snapshot"], ensure_ascii=False)
    # 저장 → 다시 열기 — 저장 전 짝 그대로
    saved = c.post("/decision/sessions", json=_draft(r))
    assert saved.status_code == 200
    rec = c.get(f"/decision/sessions/{saved.json()['id']}").json()["record"]
    assert rec["constituent_snapshot"]["constituents"]["top_stocks"][0]["name"] == (
        "주식A"
    )
    assert rec["overlap_snapshot"]["numbers"]["max"] == mx
    assert f"보유 노출 범위 {rng}" in rec["question_text"]
    for part in ("question_text", "data_quality_snapshot", "constituent_snapshot"):
        assert "주식B" not in json.dumps(rec[part], ensure_ascii=False)
    # 저장은 실제로 됐다 — 다음 조회는 바뀐 짝(주식 B · 0.00)
    r2 = c.get("/weekly/etf-check", params={"selected": SEL}).json()
    top2 = r2["selected_review"]["constituents"]["top_stocks"][0]
    assert (top2["name"], r2["overlap"]["numbers"]["max"]) == ("주식B", "0.00")


# ── F3 판단 기록 DB — 주간 GET 두 곳 ───────────────────────────────────────────


def test_f3_weekly_gets_do_not_create_record_db(env):
    ddb, mdb, c = env["ddb"], env["mdb"], env["client"]
    r = c.get("/weekly/etf-check", params={"selected": SEL}).json()
    assert r["last_record"]["status"] == "none"
    miss = c.get("/weekly/etf-check/records/unknown/review")
    assert (miss.status_code, miss.json()["detail"]) == (
        404,
        "기록을 찾을 수 없습니다.",
    )
    # 폴더 · 파일 모두 만들지 않음(기록 DB · 시장 DB 둘 다)
    assert not ddb.parent.exists() and not mdb.parent.exists()
    assert r["selected_review"]["constituents"]["state"] == "not_collected"
    assert r["market_evidence"]["status"] == "unavailable"


def _weekly_record(db: Path, question: str) -> str:
    return decision_evidence_store.insert_record(
        asof="2026-11-16",
        source_screen="today_weekly_review",
        filters={},
        candidate_snapshot=[{"ticker": SEL, "name": "고른"}],
        question_text=question,
        gpt_answer_text=_ans({SEL: ("추가 확인", "6", "이유")}),
        gemini_answer_text="",
        claude_answer_text="",
        user_memo="",
        user_verdict="unrecorded",
        next_checks=[],
        linked_market_refresh_id=None,
        db_path=db,
    )["id"]


def test_f3_weekly_gets_leave_existing_record_db_unchanged(env):
    ddb, c = env["ddb"], env["client"]
    q = c.get("/weekly/etf-check").json()["copy_text"]
    rid = _weekly_record(ddb, q)
    before = (sha(ddb), ddb.stat().st_mtime_ns, sorted(ddb.parent.iterdir()))
    assert c.get("/weekly/etf-check").json()["last_record"]["id"] == rid
    v = c.get(f"/weekly/etf-check/records/{rid}/review")
    assert v.status_code == 200 and v.json()["id"] == rid
    assert (sha(ddb), ddb.stat().st_mtime_ns, sorted(ddb.parent.iterdir())) == before


# ── 마지막 기록 = 주간 기록 중 가장 최근 1건(r1 G1 · 판정 Q8 (a)) ─────────────────


def _record_at(monkeypatch, db, rid, created, question, screen=W.wr.SOURCE_SCREEN):
    """저장 시각 · id 를 정해 기존 저장소로 저장(표 · 검사 그대로)."""
    monkeypatch.setattr(decision_evidence_store, "_kst_now_iso", lambda: created)
    monkeypatch.setattr(decision_evidence_store, "_generate_id", lambda: rid)
    weekly = screen == W.wr.SOURCE_SCREEN
    decision_evidence_store.insert_record(
        asof="2026-11-16",
        source_screen=screen,
        filters={},
        candidate_snapshot=[{"ticker": SEL, "name": "고른"}],
        question_text=question,
        gpt_answer_text=_ans({SEL: ("추가 확인", "6", "이유")}),
        gemini_answer_text="",
        claude_answer_text="",
        user_memo="",
        user_verdict="unrecorded" if weekly else "hold",
        next_checks=[],
        linked_market_refresh_id=None,
        db_path=db,
    )


def _at(day: int, hour: int = 9) -> str:
    return f"2026-11-{day:02d}T{hour:02d}:00:00.000000+0900"


def _latest(env) -> tuple[str, str]:
    rec = RO.latest_record(db_path=env["ddb"], source_screen=W.wr.SOURCE_SCREEN)
    view = env["client"].get("/weekly/etf-check").json()["last_record"]
    assert view["id"] == rec["id"] and view["saved_at"] == rec["created_at"]
    return rec["id"], rec["source_screen"]


def test_g1_latest_record_is_most_recent_weekly(env, monkeypatch):
    """저장 순서 · id 순서 · 오름차순 어느 것으로 골라도 답이 달라지게 둔다(가장 늦은 주간 기록은 저장 순서 · id 모두 가운데)."""
    ddb, c = env["ddb"], env["client"]
    q = c.get("/weekly/etf-check").json()["copy_text"]
    # 저장 순서: 주간 가운데 시각 → 주간 가장 늦은 시각 → 주간 가장 이른 시각 → 더 늦은 다른 출처
    _record_at(monkeypatch, ddb, "rec_1", _at(15), q)
    _record_at(monkeypatch, ddb, "rec_2", _at(16), q)
    _record_at(monkeypatch, ddb, "rec_3", _at(14), q)
    _record_at(monkeypatch, ddb, "rec_9", _at(17), q, screen="market_discovery")
    assert _latest(env) == ("rec_2", W.wr.SOURCE_SCREEN)
    # 저장소 목록(같은 출처 · created_at · id 내림차순)의 첫 줄과 같다
    first = decision_evidence_store.list_recent_records(
        db_path=ddb, source_screen=W.wr.SOURCE_SCREEN, limit=1
    )[0]
    assert first["id"] == "rec_2"
    # 더 늦은 주간 기록을 저장하면 그것이 마지막 기록(더 늦은 다른 출처 기록이 있어도)
    _record_at(monkeypatch, ddb, "rec_0", _at(18), q, screen="market_discovery")
    _record_at(monkeypatch, ddb, "rec_5", _at(17, 8), q)
    assert _latest(env) == ("rec_5", W.wr.SOURCE_SCREEN)


@pytest.mark.parametrize(
    "order", [("rec_a", "rec_z"), ("rec_z", "rec_a")], ids=["a 먼저", "z 먼저"]
)
def test_g1_latest_record_tie_on_created_at_takes_larger_id(env, monkeypatch, order):
    ddb, c = env["ddb"], env["client"]
    q = c.get("/weekly/etf-check").json()["copy_text"]
    _record_at(monkeypatch, ddb, "rec_m", _at(15), q)  # 더 이른 주간 기록
    for rid in order:
        _record_at(monkeypatch, ddb, rid, _at(16), q)
    # 같은 시각 · 더 큰 id 의 다른 출처 기록은 보지 않음
    _record_at(monkeypatch, ddb, "rec_zz", _at(16), q, screen="market_discovery")
    assert _latest(env) == ("rec_z", W.wr.SOURCE_SCREEN)


OLD_HEAD = (
    "id TEXT PRIMARY KEY, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, "
    "asof TEXT NOT NULL, source_screen TEXT NOT NULL, filters_json TEXT NOT NULL, "
    "candidate_snapshot_json TEXT NOT NULL, question_text TEXT NOT NULL, "
)
OLD_TAIL = (
    ", user_memo TEXT NOT NULL DEFAULT '', user_verdict TEXT NOT NULL, "
    "next_checks_json TEXT NOT NULL DEFAULT '[]', linked_market_refresh_id TEXT"
)


@pytest.mark.parametrize(
    "answers",
    [
        ("gpt_answer_text", "gemini_answer_text", "claude_answer_text"),  # 2026-05-21
        ("answer_text",),  # 2026-05-21 이전(단일 답 = GPT 로 읽음)
    ],
    ids=["세 답 칸 · 묶음 칸 없음", "단일 답 칸"],
)
def test_f3_old_schema_read_without_migration(env, answers):
    ddb, c = env["ddb"], env["client"]
    q = c.get("/weekly/etf-check").json()["copy_text"]
    ddb.parent.mkdir(parents=True)
    cols = ", ".join(f"{a} TEXT NOT NULL DEFAULT ''" for a in answers)
    with sqlite3.connect(str(ddb)) as con:
        con.execute(f"CREATE TABLE ai_session_records ({OLD_HEAD}{cols}{OLD_TAIL})")
        con.execute(
            f"INSERT INTO ai_session_records (id, created_at, updated_at, asof, "
            f"source_screen, filters_json, candidate_snapshot_json, question_text, "
            f"{answers[0]}, user_verdict) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "decision_old",
                "2026-11-16T09:00:00.000000+0900",
                "2026-11-16T09:00:00.000000+0900",
                "2026-11-16",
                "today_weekly_review",
                "{}",
                json.dumps([{"ticker": SEL, "name": "고른"}]),
                q,
                _ans({SEL: ("추가 확인", "6", "이유")}),
                "unrecorded",
            ),
        )

    def columns():
        with sqlite3.connect(f"file:{ddb}?mode=ro", uri=True) as con:
            return [r[1] for r in con.execute("PRAGMA table_info(ai_session_records)")]

    before = (columns(), sha(ddb), ddb.stat().st_mtime_ns)
    v = c.get("/weekly/etf-check/records/decision_old/review")
    assert v.status_code == 200
    body = v.json()
    assert (body["id"], body["verdict"], body["asof"]) == (
        "decision_old",
        "unrecorded",
        "2026-11-16",
    )
    assert body["compare"]["answers"]["gpt"] != {"status": "no_answer"}
    assert c.get("/weekly/etf-check").json()["last_record"]["id"] == "decision_old"
    # 마이그레이션(칸 추가 · 표 다시 만들기) 없음 — 칸 · 바이트 · 수정 시각 그대로
    assert (columns(), sha(ddb), ddb.stat().st_mtime_ns) == before


# ── F3 시장 DB — 새 시장 GET ──────────────────────────────────────────────────


def test_f3_market_gets_do_not_create_market_db(env):
    mdb, c = env["mdb"], env["client"]
    ev = c.get("/market/evidence").json()
    assert (ev["status"], ev["message"], ev["daily_text"]) == (
        "unavailable",
        ME.NO_DB,
        None,
    )
    assert ev["data_status"] == [ME.NO_DB]
    off = c.get("/market/etf-official", params={"tickers": "069500,102110"})
    assert off.status_code == 200 and off.json()["csv"]["ok"] is False
    cs = c.get("/market/constituents/summary", params={"ticker": SEL}).json()
    assert cs["status"] == "missing"
    assert not mdb.parent.exists() and not (env["tmp"] / "meta").exists()


def test_f3_weekly_with_real_summary_creates_nothing(env, monkeypatch):
    from app.pc_etf_compare_summary import build_summary

    monkeypatch.setattr(W, "build_summary", build_summary)
    r = env["client"].get("/weekly/etf-check", params={"selected": SEL}).json()
    assert r["status"] == "missing"
    assert not env["mdb"].parent.exists() and not env["ddb"].parent.exists()


def test_f3_market_evidence_existing_complete_db_bytes_unchanged(env, monkeypatch):
    mdb = env["mdb"]
    mdb.parent.mkdir(parents=True)
    MEX.make_db(mdb)
    MDS.init_db(mdb)  # 시장 표가 모두 있는 DB(운영과 같은 모양)
    # 이 프로세스에서 처음 여는 것처럼(기존 저장소의 표 확인이 다시 돈다)
    monkeypatch.setattr(MDS, "_INITIALIZED_DBS", set())
    before = (sha(mdb), mdb.stat().st_mtime_ns, sorted(mdb.parent.iterdir()))
    ev = env["client"].get("/market/evidence").json()
    assert ev["status"] in ("ok", "partial")
    assert (sha(mdb), mdb.stat().st_mtime_ns, sorted(mdb.parent.iterdir())) == before
