"""POC5-08 — 사후평가 실행 · 모집단 · 가격 상태 · 산출물 · 조회 · API(tmp 사본 · tmp 캘린더 · 고정 시계).

설계 §3 · §4 · §7 · §8 · §9 · PLAN §2 · §3 · 판정 §3-B(price_asof_date).
라이브 원장 · 보유 · 시세 · 연구 폴더 0 — 사본은 conftest 가 tmp 로 돌린 경로에 만든다.
"""

from __future__ import annotations

import ast
import hashlib
import json
import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app import api as api_module
from app.alert_retro import population, report
from app.ledger_copy import store as pc_store
from app.ledger_reports import dates
from app.three_push_runtime import ledger_context as lc
from app.three_push_runtime import ledger_outcome as lo
from app.three_push_runtime import ledger_store as ls

KST = timezone(timedelta(hours=9))
UTC = timezone.utc
HOLIDAYS = ("2026-10-05", "2026-10-09")
D = "2026-10-12"  # 월 · 사건일


def _at(text):
    return datetime.fromisoformat(text).replace(tzinfo=KST)


@pytest.fixture
def base(tmp_path, monkeypatch):
    caldir = Path(lc.CALENDAR_DIR)
    caldir.mkdir(parents=True, exist_ok=True)
    days, x = [], date(2026, 1, 1)
    while x.year == 2026:
        if x.weekday() < 5 and x.isoformat() not in HOLIDAYS:
            days.append(x.isoformat())
        x += timedelta(days=1)
    (caldir / "krx_trading_days_2026.csv").write_text(
        "date,source\n" + "\n".join(f"{v},TEST" for v in days) + "\n", encoding="utf-8"
    )
    root = tmp_path / "research" / "poc5_08"
    monkeypatch.setattr(report, "RESEARCH_ROOT", root)
    clock = {"now": _at("2026-10-20T10:00:00")}
    monkeypatch.setattr(report, "_now", lambda: clock["now"])
    return SimpleNamespace(
        root=root,
        clock=clock,
        path=Path(pc_store.DEFAULT_DB_PATH),
        cal=dates.calendar(),
    )


@pytest.fixture
def env(base):
    con = ls.connect(base.path)
    for stmt in lo.DDL:
        con.execute(stmt)
    con.commit()
    pc_store.connect(base.path).close()
    base.con = con
    yield base
    con.close()


def _item(kind="ticker", sid="005930", *, disp="sent", exposure="PRIMARY", **kw):
    return {
        "subject_kind": kind,
        "subject_id": sid,
        "held": kw.get("held", 1),
        "state": kw.get("state", "D5_8"),
        "prev_state": None,
        "disposition": disp,
        "event_type": kw.get("event_type"),
        "exposure": exposure,
        "values_json": json.dumps(kw.get("values", {})),
        "t0_price": 100.0,
        "t0_price_asof": "x",
        "evaluable": kw.get("evaluable", 1),
    }


def _run(con, eid, day, kind, hhmm, items, *, delivery="sent", cohort="PRIMARY_LIVE"):
    ts = f"{day}T{hhmm}:01+09:00"
    off = 1 if cohort == "OFF" else 0
    ls.insert_started(
        con,
        {
            "event_id": eid,
            "push_kind": kind,
            "runtime_kst": ts,
            "runtime_date_kst": day,
            "started_at": ts,
            "off_schedule": off,
            "schedule_expected": None if off else hhmm,
        },
    )
    ls.finalize(
        con,
        eid,
        {
            "status": "sent",
            "cohort": "PRIMARY_LIVE" if off else cohort,
            "contract_version": f"{kind}.v1",
        },
        lambda _c: [dict(i) for i in items],
        {
            "delivery_status": delivery,
            "telegram_sent": 1,
            "body_text": "b",
            "body_sha256": "h",
        },
    )


def _outcome(con, eid, seq, series, h, status="MATURED", **kw):
    ret = kw.get("ret")
    con.execute(
        "INSERT INTO price_outcome (event_id, item_seq, series_id, horizon, t0_price,"
        " eval_date, eval_price, return_raw, max_up_raw, max_down_raw, path_points,"
        " price_basis, status, computed_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            eid,
            seq,
            series,
            h,
            100.0,
            kw.get("eval_date"),
            None if ret is None else 100.0 * (1 + ret),
            ret,
            kw.get("up"),
            kw.get("down"),
            kw.get("path", h if status == "MATURED" else None),
            kw.get("basis", "KRX_ETF_UNADJUSTED|ETF"),
            status,
            kw.get("computed", "2026-10-20T00:00:00+00:00"),
        ),
    )
    con.commit()


def _sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _folders(root):
    return sorted(p.name for p in Path(root).iterdir()) if Path(root).exists() else []


def _slots(rep_items, eid, seq):
    return next(i for i in rep_items if (i["event_id"], i["item_seq"]) == (eid, seq))[
        "slots"
    ]


# ── 사본 없음 · 손상 ─────────────────────────────────────────────────────────


def test_no_copy_is_status_without_artifact(base):
    got = report.run()
    assert got["status"] == "NO_COPY" and got["end_date"] == "2026-10-19"
    assert _folders(base.root) == []
    assert report.latest()["status"] == "NO_RESULT"


def _drop_feedback(con):
    con.execute("DROP TABLE user_feedback")


def _meta_without_outcome(con):
    ls.meta_put_once(con, lo.META_KEY, lo.SCHEMA_VERSION)
    con.execute("DROP TABLE price_outcome")


def _orphan_outcome(con):
    _outcome(con, "ev_missing", 1, "krx_etf:069500", 1, ret=0.01, eval_date=D)


def _duplicate_key(con):
    con.execute("ALTER TABLE price_outcome RENAME TO po_old")
    con.execute(
        "CREATE TABLE price_outcome AS SELECT * FROM po_old WHERE 0"
    )  # 같은 칸 · 기본 키 없음(손상 사본)
    for _ in range(2):
        _outcome(con, "ev1", 1, "krx_etf:069500", 1, ret=0.01, eval_date=D)


def _orphan_item(con):
    con.execute(
        "INSERT INTO signal_item (event_id, item_seq, subject_kind, subject_id,"
        " disposition) VALUES ('ev_gone', 1, 'ticker', 'X', 'sent')"
    )


def _bad_values(con):
    con.execute("UPDATE signal_item SET values_json = '{bad' WHERE event_id = 'ev1'")


def _no_pk_copy(con, table):
    """같은 칸 · 기본 키 없는 표로 바꾸고 모든 행을 한 번 더 넣는다(손상 사본)."""
    con.execute(f"ALTER TABLE {table} RENAME TO {table}_old")
    con.execute(f"CREATE TABLE {table} AS SELECT * FROM {table}_old")
    con.execute(f"INSERT INTO {table} SELECT * FROM {table}_old")


def _dup_run(con):
    _no_pk_copy(con, "evaluation_run")


def _dup_item(con):
    _no_pk_copy(con, "signal_item")


def _null_run_date(con):
    con.execute(
        "UPDATE evaluation_run SET runtime_date_kst = NULL WHERE event_id = 'ev1'"
    )


def _set_run(column, value):
    def damage(con):
        con.execute(
            f"UPDATE evaluation_run SET {column} = ? WHERE event_id = 'ev1'", (value,)
        )

    return damage


def _legacy_bad_date(con):
    _run(con, "ev_legacy", D, "holdings_briefing", "09:15", [_item()], cohort="LEGACY")
    con.execute(
        "UPDATE evaluation_run SET runtime_date_kst = 'x' WHERE event_id = 'ev_legacy'"
    )


def _bad_row(**over):
    """결과 행 1개를 원시 SQL 로 넣는다(칸 하나만 형식이 틀림)."""

    def damage(con):
        row = dict(
            horizon=1,
            status="MATURED",
            return_raw=0.01,
            eval_date=D,
            path_points=1,
            computed_at="2026-10-13T00:00:00+00:00",
        )
        row.update(over)
        con.execute(
            "INSERT INTO price_outcome (event_id, item_seq, series_id, horizon, status,"
            " return_raw, eval_date, path_points, computed_at)"
            " VALUES ('ev1', 1, 'krx_etf:005930', ?, ?, ?, ?, ?, ?)",
            tuple(row[k] for k in row),
        )

    return damage


@pytest.mark.parametrize(
    "damage, word",
    [
        (_drop_feedback, "user_feedback"),
        (_meta_without_outcome, "price_outcome"),
        (_orphan_outcome, "없는 항목"),
        (_duplicate_key, "중복 키"),
        (_orphan_item, "실행 기록 없는 항목"),
        (_bad_values, "values_json"),
        (_dup_run, "실행 event_id"),
        (_dup_item, "항목 (event_id, item_seq)"),
        (_null_run_date, "실행 날짜"),
        (_set_run("schedule_expected", "invalid-time"), "예정 시각"),
        (_set_run("schedule_expected", "25:00"), "예정 시각"),
        (_set_run("schedule_expected", None), "예정 시각"),
        (_set_run("runtime_kst", "invalid-time"), "실행 시각"),
        (_set_run("runtime_kst", "2026-10-12T09:15:01"), "실행 시각"),  # 시간대 없음
        (
            _set_run("runtime_kst", "2026-10-13T09:15:01+09:00"),
            "실행 시각",
        ),  # 날짜 다름
        (_legacy_bad_date, "실행 날짜"),  # 대상 아닌 실행도 날짜는 검사
        (_bad_row(computed_at="invalid-time"), "계산 시각"),
        (_bad_row(computed_at="2026-10-13T00:00:00"), "계산 시각"),  # 시간대 없음
        (_bad_row(horizon=7), "가격 결과 행"),
        (_bad_row(status="WEIRD"), "가격 결과 행"),
        (_bad_row(return_raw="abc"), "가격 결과 행"),
        (_bad_row(path_points="x"), "가격 결과 행"),
        (_bad_row(eval_date="2026/10/12"), "가격 결과 행"),
    ],
)
def test_damaged_copy_is_check_required_without_artifact(env, damage, word):
    _run(env.con, "ev1", D, "holdings_briefing", "09:15", [_item()])
    damage(env.con)
    env.con.commit()
    got = report.run()
    assert got["status"] == "CHECK_REQUIRED"
    assert any(word in p for p in got["problems"]), got["problems"]
    assert _folders(env.root) == []


def test_normal_copy_is_ok(env):
    _run(env.con, "ev1", D, "holdings_briefing", "09:15", [_item()])
    _bad_row()(env.con)  # 기준 행(형식 정상) — 손상 시험의 바탕이 정상인지
    env.con.commit()
    assert report.run()["status"] == "OK"


def test_utc_offset_times_are_read_as_times_not_rejected(env):
    """시간대만 다른 같은 시각(UTC 표기)은 정상 — KST 날짜로 실행 날짜와 맞춘다."""
    _run(env.con, "ev1", D, "holdings_briefing", "09:15", [_item()])
    _set_run("runtime_kst", "2026-10-12T00:15:01+00:00")(env.con)
    env.con.commit()
    got = report.run()
    assert got["status"] == "OK"


# ── 모집단 · 분모 · 전달 · 제외 ──────────────────────────────────────────────


def test_population_denominators_delivery_and_exclusions(env):
    c = env.con
    _run(
        c,
        "ev1",
        D,
        "holdings_briefing",
        "09:15",
        [
            _item(sid="A", exposure="PRIMARY"),
            _item(sid="B", disp="not_selected", exposure=None),
            _item(sid="C", disp="suppressed", exposure="SECONDARY"),
        ],
    )
    _run(
        c,
        "ev2",
        D,
        "holdings_risk_alert",
        "09:30",
        [
            _item("sector", "S1", values={"ticker": "111111"}),
            _item("sector", "S2", disp="cut_by_section_cap", values={"ticker": "2"}),
        ],
        delivery="partial",
    )
    _run(
        c,
        "ev3",
        D,
        "market_briefing",
        "08:30",
        [
            _item("market", "SP500", exposure=None),
            _item("index_group", "G", values={"tickers": ["1", "2"]}),
            _item("market", "NASDAQ"),
        ],
        delivery="failed",
    )
    _run(c, "ev4", D, "holdings_briefing", "09:15", [_item()], cohort="LEGACY")
    _run(c, "ev5", D, "holdings_briefing", "09:15", [_item()], cohort="OFF")
    _run(c, "ev6", D, "holdings_briefing", "09:15", [_item(evaluable=0)])
    _run(c, "ev7", "2026-10-21", "holdings_briefing", "09:15", [_item()])
    env.clock["now"] = _at("2026-10-22T10:00:00")
    pc_store.add_feedback("ev1", helpfulness="HELPFUL", path=env.path)
    got = report.run("2026-10-20")
    s = got["summary"]
    assert s["denominators"] == {
        "events": 3,
        "items": 7,
        "price_observations": 8,
        "price_slots": 24,
        "signal_dates": 1,
        "series_recorded": 0,
    }
    assert s["delivery"] == {
        "dispositions": {
            "cut_by_section_cap": 1,
            "not_selected": 1,
            "sent": 4,
            "suppressed": 1,
        },
        "delivered_items": 1,  # ev1 A 만(ev2 = partial · ev3 = failed)
        "partial_items": 1,
        "exposure": {"NONE": 2, "PRIMARY": 4, "SECONDARY": 1},
    }
    assert got["exclusions"] == {
        "after_end": 1,
        "cohort_not_primary_live": 1,
        "evaluable_0": 1,
        "market_not_sp500": 1,
        "off_schedule": 1,
    }
    assert got["feedback_summary"] == {
        "events_with_feedback": 1,
        "events_without_feedback": 2,
    }
    assert got["ml"]["not_eligible"] == {"NOT_MATURED": 5, "OUT_OF_SCOPE": 3}


# ── 가격 상태 ────────────────────────────────────────────────────────────────


def test_price_statuses_sign_partial_path_and_no_zero_fill(env):
    c = env.con
    items = [_item(sid=f"T{i}") for i in range(1, 7)]
    _run(c, "ev1", D, "holdings_briefing", "09:15", items)
    s = "krx_etf:T"
    _outcome(c, "ev1", 1, s + "1", 1, ret=0.01, eval_date=D)
    _outcome(c, "ev1", 1, s + "1", 5, ret=-0.02, eval_date="2026-10-16", down=-0.03)
    _outcome(c, "ev1", 2, s + "2", 5, ret=0.0, eval_date="2026-10-16")
    _outcome(c, "ev1", 3, s + "3", 5, "PRICE_MISSING", eval_date="2026-10-16", path=3)
    for h in (1, 5, 20):
        _outcome(c, "ev1", 4, s + "4", h, "T0_MISSING")
        _outcome(c, "ev1", 6, "unsupported:T6", h, "UNSUPPORTED_PRICE_SOURCE")
    _outcome(c, "ev1", 5, "krx_stock:T5", 5, "UNTRACKED_AFTER_EXIT", path=2)
    report.run()
    rep = json.loads(next(Path(env.root).glob("*/report.json")).read_text("utf-8"))
    one = _slots(rep["items"], "ev1", 1)
    assert [(x["horizon"], x["status"]) for x in one] == [
        (1, "MATURED"),
        (5, "MATURED"),
        (20, "PENDING_NOT_DUE"),
    ]
    assert one[1]["sign"] == "DOWN" and one[1]["sign_text"].endswith("하락")
    assert one[0]["sign"] is None  # 부호 문구는 +5 만
    assert _slots(rep["items"], "ev1", 2)[1]["sign_text"].endswith("변화 없음")
    miss = _slots(rep["items"], "ev1", 3)[1]
    assert miss["status_text"] == "가격 자료 없음" and miss["partial_path"] is True
    assert miss["return_raw"] is None and miss["sign"] is None  # 0% 로 바꾸지 않음
    assert {x["status"] for x in _slots(rep["items"], "ev1", 4)} == {"T0_MISSING"}
    assert _slots(rep["items"], "ev1", 5)[1]["status_text"] == "매도 뒤 추적 중단"
    assert _slots(rep["items"], "ev1", 6)[1]["status_text"] == "지원 계열 없음"
    assert rep["summary"]["status_by_horizon"]["5"] == {
        "MATURED": 2,
        "PRICE_MISSING": 1,
        "T0_MISSING": 1,
        "UNSUPPORTED_PRICE_SOURCE": 1,
        "UNTRACKED_AFTER_EXIT": 1,
    }
    ml = {
        x["item_seq"]: _slots(rep["items"], "ev1", x["item_seq"])[1]["ml"]
        for x in rep["items"]
    }
    assert ml[3]["reason"] == "NO_LABEL" and ml[6]["reason"] == "NO_LABEL"
    # 종료일 10-19 → 마지막 구간 10-06 ~ 10-12 의 시험 행이지만 학습 자료 없음
    assert ml[1]["reason"] == "DATA_SHORT" and ml[1]["block"] == 3


@pytest.mark.parametrize(
    "now, asof",
    [
        ("2026-10-13T15:29:59", "2026-10-12"),
        ("2026-10-13T15:30:00", "2026-10-13"),
        ("2026-10-09T17:00:00", "2026-10-08"),  # 휴장일 저녁
        ("2026-10-11T12:00:00", "2026-10-08"),  # 일요일
    ],
)
def test_price_asof_date_follows_calendar_and_close(base, now, asof):
    assert report.price_asof_date(base.cal, _at(now)) == asof


def test_pending_uses_fixed_price_asof_not_signal_end_date(env):
    """판정 §3-B — 과거 종료일을 지정하고 평가일이 지난 뒤 실행해도 결측 슬롯은 price_asof_date 기준."""
    c = env.con
    _run(c, "ev1", D, "holdings_briefing", "09:15", [_item(sid="A"), _item(sid="B")])
    _outcome(c, "ev1", 2, "krx_etf:B", 5, ret=0.03, eval_date="2026-10-16")
    env.clock["now"] = _at("2026-11-20T10:00:00")
    late = report.run(D)
    assert (late["end_date"], late["price_asof_date"]) == (D, "2026-11-19")
    rep = json.loads((env.root / late["run_id"] / "report.json").read_text("utf-8"))
    a = _slots(rep["items"], "ev1", 1)
    assert [x["status"] for x in a] == ["PENDING_DUE"] * 3  # 종료일 기준이면 미도래
    assert [x["expected_eval_date"] for x in a] == [D, "2026-10-16", "2026-11-06"]
    b = _slots(rep["items"], "ev1", 2)
    assert b[1]["status"] == "MATURED"  # 종료일 뒤 평가일 결과도 저장된 그대로
    env.clock["now"] = _at("2026-10-13T15:00:00")
    early = report.run(D)
    rep = json.loads((env.root / early["run_id"] / "report.json").read_text("utf-8"))
    assert early["price_asof_date"] == D
    assert [x["status"] for x in _slots(rep["items"], "ev1", 1)] == [
        "PENDING_DUE",
        "PENDING_NOT_DUE",
        "PENDING_NOT_DUE",
    ]


# ── ML 자료(합성) ────────────────────────────────────────────────────────────


def _ml_days(env, start, end):
    """매 거래일 장중 사업군 2개 · +5 MATURED · 결과는 평가일 다음 거래일 08:10 계산."""
    for i, d in enumerate(dates.trading_days(env.cal, start, end)):
        eid = f"ev_{d}"
        items = []
        for j, tk in enumerate(("111111", "222222")):
            r20 = ((i * 7 + j * 3) % 11 - 5) / 100.0
            items.append(
                _item(
                    "sector",
                    f"S{j}",
                    disp="not_selected" if j else "sent",
                    values={
                        "ticker": tk,
                        "return_20d_pct": r20 * 100,
                        "day_return_pct": None if i % 4 == 0 else j * 0.5,
                        "profit_loss_pct": 77.77,  # 개인값 — 쓰지도 복사하지도 않는다
                    },
                )
            )
        _run(env.con, eid, d, "holdings_risk_alert", "09:30", items)
        ev = env.cal.days_from(d, 5)[-1]
        at = _at(f"{env.cal.next_after(ev)}T08:10:00").astimezone(UTC).isoformat()
        for j, tk in enumerate(("111111", "222222")):
            r20 = ((i * 7 + j * 3) % 11 - 5) / 100.0
            _outcome(
                env.con,
                eid,
                j + 1,
                f"krx_etf:{tk}",
                5,
                ret=0.5 * r20 + (0.002 if (i + j) % 2 else -0.002),
                eval_date=ev,
                basis="KRX_ETF_UNADJUSTED",
                computed=at,
            )


def test_ml_values_only_on_test_rows_and_full_comparison(env):
    _ml_days(env, "2026-06-01", "2026-10-13")
    _run(
        env.con,
        "ev_mkt",
        "2026-10-13",
        "market_briefing",
        "08:30",
        [_item("market", "SP500")],
    )
    env.clock["now"] = _at("2026-10-21T10:00:00")
    got = report.run()
    assert got["end_date"] == "2026-10-20" and got["ml"]["status"] == "COMPARED"
    ov = got["ml"]["overall"]
    assert ov["verdict_text"] == "개선" and ov["model_mae_pp"] < ov["baseline_mae_pp"]
    blocks = got["ml"]["blocks"]
    assert [b["days"][0] for b in blocks] == ["2026-09-21", "2026-09-28", "2026-10-06"]
    rep = json.loads((env.root / got["run_id"] / "report.json").read_text("utf-8"))
    in_test = {d for b in blocks for d in b["days"]}
    for it in rep["items"]:
        ml = it["slots"][1]["ml"]
        if it["push_kind"] == "market_briefing":
            assert ml["reason"] == "OUT_OF_SCOPE"
        elif it["signal_date"] in in_test:
            assert ml["status"] == "ESTIMATED" and ml["reason"] is None
            exact = abs(ml["actual_raw"] - ml["estimate_raw"]) * 100
            assert abs(ml["abs_error_pp"] - exact) <= 0.005 + 1e-9
        else:
            assert ml["status"] == "NONE" and ml["reason_text"] == "시험 구간 밖"
    assert got["ml"]["eligible_rows"] == 2 * len(
        dates.trading_days(env.cal, "2026-06-01", "2026-10-13")
    )


def test_feedback_changes_digest_and_display_not_samples_or_model(env):
    _ml_days(env, "2026-06-01", "2026-10-13")
    env.clock["now"] = _at("2026-10-21T10:00:00")
    a = report.run()
    first = report.latest("ev_2026-10-13")
    assert first["input_changed"] is False and first["event"]["feedback"] is None
    pc_store.add_feedback(
        "ev_2026-10-13",
        helpfulness="UNHELPFUL_CONFUSING",
        action="SELL_OR_REDUCE",
        memo="비밀메모-08",
        path=env.path,
    )
    changed = report.latest()
    assert changed["input_changed"] is True
    assert changed["input_check"] == "입력이 변경됨 · 재실행 필요"
    env.clock["now"] = _at("2026-10-21T10:05:00")
    b = report.run()
    assert a["input_digest"] != b["input_digest"]
    assert a["ml"] == b["ml"] and a["summary"] == b["summary"]
    ra = json.loads((env.root / a["run_id"] / "report.json").read_text("utf-8"))
    rb = json.loads((env.root / b["run_id"] / "report.json").read_text("utf-8"))
    assert ra["items"] == rb["items"]
    ev = report.latest("ev_2026-10-13")["event"]
    assert ev["feedback"]["helpfulness"] == "UNHELPFUL_CONFUSING"
    assert set(ev["feedback"]) == {"feedback_seq", "helpfulness", "feedback_at"}
    for f in (env.root / b["run_id"]).iterdir():
        text = f.read_text("utf-8")
        assert "비밀메모-08" not in text and "SELL_OR_REDUCE" not in text
        assert "profit_loss" not in text and "77.77" not in text
    # 기존 평가를 바꿔도(새 평가 = event 최신 1건) 표본 · 모델은 같고 digest 만 바뀐다
    pc_store.add_feedback("ev_2026-10-13", helpfulness="HELPFUL", path=env.path)
    assert report.latest()["input_changed"] is True
    env.clock["now"] = _at("2026-10-21T10:10:00")
    c = report.run()
    assert c["input_digest"] not in (a["input_digest"], b["input_digest"])
    assert c["ml"] == a["ml"] and c["summary"] == a["summary"]
    assert report.latest("ev_2026-10-13")["event"]["feedback"]["feedback_seq"] == 2


# ── 산출물 · 최신 조회 ───────────────────────────────────────────────────────


def test_artifacts_latest_selection_and_unreadable(env):
    _run(env.con, "ev1", D, "holdings_briefing", "09:15", [_item()])
    a = report.run()
    env.clock["now"] = _at("2026-10-20T10:00:01")
    b = report.run()
    assert _folders(env.root) == sorted([a["run_id"], b["run_id"]])
    assert set(p.name for p in (env.root / b["run_id"]).iterdir()) == {
        "report.json",
        "input_snapshot.json",
    }
    snap = json.loads((env.root / b["run_id"] / "input_snapshot.json").read_text())
    assert snap["input_digest"] == b["input_digest"] and snap["price_asof_date"]
    (env.root / ".99999999T999999999999_ffffffff.partial").mkdir()
    (env.root / "99999999T999999999999_eeeeeeee").mkdir()  # 반쪽 폴더(파일 없음)
    assert report.latest()["run_id"] == b["run_id"]
    good = (env.root / b["run_id"] / "report.json").read_text("utf-8")
    missing_end = json.loads(good)
    del missing_end["end_date"]
    for broken in ("{", "[]", "null", json.dumps(missing_end)):
        (env.root / b["run_id"] / "report.json").write_text(broken, encoding="utf-8")
        got = report.latest()
        assert got["status"] == "ARTIFACT_UNREADABLE" and got["run_id"] == b["run_id"]


def test_latest_keeps_result_when_copy_is_damaged_later(env):
    _run(env.con, "ev1", D, "holdings_briefing", "09:15", [_item()])
    ok = report.run()
    _null_run_date(env.con)
    env.con.commit()
    got = report.latest("ev1")
    assert got["status"] == "OK" and got["run_id"] == ok["run_id"]
    assert got["input_changed"] is None and got["input_check"].startswith(
        "사본 확인 필요"
    )
    assert len(got["event"]["items"]) == 1


def test_alert_after_end_date_does_not_mark_input_changed(env):
    _run(env.con, "ev1", D, "holdings_briefing", "09:15", [_item()])
    env.clock["now"] = _at("2026-10-14T10:00:00")
    report.run(D)
    _run(env.con, "ev2", "2026-10-13", "holdings_briefing", "09:15", [_item()])
    assert report.latest()["input_changed"] is False  # 신호 기간 끝 뒤 알림
    _run(env.con, "ev3", D, "holdings_briefing", "15:40", [_item()])
    assert report.latest()["input_changed"] is True  # 기간 안 알림


def test_latest_get_does_not_load_scikit_learn(tmp_path):
    """조회(GET)는 학습 라이브러리를 읽지 않는다 — 새 프로세스 · tmp 작업 폴더(라이브 0)."""
    import subprocess
    import sys

    code = (
        "import sys; from app.alert_retro import report; "
        "from app import api_decision_ledger; "
        "r = report.latest(); print(r['status'], 'sklearn' in sys.modules)"
    )
    root = Path(__file__).resolve().parents[1]
    out = subprocess.run(
        [sys.executable, "-c", code],
        cwd=tmp_path,
        env={"PYTHONPATH": str(root), "PATH": "/usr/bin:/bin"},
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert out.returncode == 0, out.stderr
    assert out.stdout.split()[-2:] == ["NO_RESULT", "False"]


def test_save_failure_keeps_previous_and_leaves_no_partial(env, monkeypatch):
    _run(env.con, "ev1", D, "holdings_briefing", "09:15", [_item()])
    ok = report.run()

    def _fail(*_a, **_k):
        raise OSError("disk")

    monkeypatch.setattr(report, "os", SimpleNamespace(rename=_fail))  # 이 모듈만
    env.clock["now"] = _at("2026-10-20T11:00:00")
    with pytest.raises(report.ArtifactSaveError):
        report.run()
    assert _folders(env.root) == [ok["run_id"]]
    assert report.latest()["run_id"] == ok["run_id"]
    client = TestClient(api_module.app)
    res = client.post("/decision-ledger/retrospective-evaluation", json={})
    assert res.status_code == 500 and "결과를 보이지 않습니다" in res.json()["detail"]


def test_latest_input_check_uses_report_dates_not_clock(env):
    _run(env.con, "ev1", D, "holdings_briefing", "09:15", [_item()])
    env.clock["now"] = _at("2026-10-13T10:00:00")
    report.run()
    env.clock["now"] = _at("2026-12-01T10:00:00")  # 시간만 지남 → 변경 아님
    assert report.latest()["input_changed"] is False
    _outcome(env.con, "ev1", 1, "krx_etf:005930", 1, ret=0.01, eval_date=D)
    assert report.latest()["input_changed"] is True


def test_latest_event_filter_returns_that_alert_only(env):
    _run(env.con, "ev1", D, "holdings_briefing", "09:15", [_item(), _item(sid="B")])
    _run(env.con, "ev2", D, "holdings_risk_alert", "09:30", [_item()])
    report.run()
    got = report.latest("ev1")
    assert [i["item_seq"] for i in got["event"]["items"]] == [1, 2]
    assert "items" not in got and "feedback" not in got
    assert report.latest("ev_none")["event"]["items"] == []


# ── API ──────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "body",
    [
        {"end_date": "2026/10/12"},
        {"end_date": "2026-10-20"},  # 오늘
        {"end_date": "2026-10-09"},  # 휴장일
        {"end_date": "2026-10-12", "extra": 1},
    ],
)
def test_api_rejects_bad_input(env, body):
    res = TestClient(api_module.app).post(
        "/decision-ledger/retrospective-evaluation", json=body
    )
    assert res.status_code == 422
    assert _folders(env.root) == []


def test_api_post_and_latest(env):
    _run(env.con, "ev1", D, "holdings_briefing", "09:15", [_item()])
    client = TestClient(api_module.app)
    assert (
        client.get("/decision-ledger/retrospective-evaluation/latest").json()["status"]
        == "NO_RESULT"
    )
    res = client.post("/decision-ledger/retrospective-evaluation", json={})
    assert res.status_code == 200 and res.json()["status"] == "OK"
    assert "items" not in res.json()
    got = client.get(
        "/decision-ledger/retrospective-evaluation/latest", params={"event_id": "ev1"}
    ).json()
    assert got["run_id"] == res.json()["run_id"] and len(got["event"]["items"]) == 1


# ── 보존 · 경계 ──────────────────────────────────────────────────────────────


def test_copy_is_read_only_during_run_and_latest(env):
    _ml_days(env, "2026-09-01", "2026-10-13")
    env.con.close()
    before = _sha(env.path)
    report.run()
    report.latest("ev_2026-10-13")
    assert _sha(env.path) == before
    env.con = sqlite3.connect(str(env.path))


def test_new_modules_have_no_network_ssh_or_telegram():
    root = Path(__file__).resolve().parents[1] / "app" / "alert_retro"
    banned = ("requests", "httpx", "urllib", "telegram", "aiohttp", "socket")
    banned += ("subprocess", "paramiko", "ledger_copy.sync")
    for f in sorted(root.glob("*.py")):
        tree = ast.parse(f.read_text(encoding="utf-8"))
        mods = [
            *(
                a.name
                for n in ast.walk(tree)
                if isinstance(n, ast.Import)
                for a in n.names
            ),
            *(n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)),
        ]
        assert not [m for m in mods if any(b in m for b in banned)], f


def test_population_status_texts_cover_all_outcome_statuses():
    for s in (lo.MATURED, lo.T0_MISSING, lo.PRICE_MISSING, lo.UNTRACKED_AFTER_EXIT):
        assert s in population.STATUS_TEXT
    assert lo.UNSUPPORTED in population.STATUS_TEXT


def test_after_close_event_counts_from_next_trading_day(env):
    _run(env.con, "ev1", "2026-10-08", "holdings_briefing", "15:40", [_item()])
    env.clock["now"] = _at("2026-10-13T16:00:00")
    got = report.run("2026-10-08")
    rep = json.loads((env.root / got["run_id"] / "report.json").read_text("utf-8"))
    slots = _slots(rep["items"], "ev1", 1)
    # 15:40 사건 = 다음 거래일 종가부터(10-09 휴장 · 주말) · 가격 관측 기준일 10-13
    assert [x["expected_eval_date"] for x in slots][:2] == ["2026-10-12", "2026-10-16"]
    assert [x["status"] for x in slots][:2] == ["PENDING_DUE", "PENDING_NOT_DUE"]
