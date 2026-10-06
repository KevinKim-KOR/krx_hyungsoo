"""POC3-02D-OPS-03 설계자 RESULT STEP 2 · 6 — 대표 ETF 검증과 소비자 격리 · 09:20 채우기 한도.

```text
KRX 전체 적재     ① 기준일 ③ 행 수 95% ④ 관계식 · 중복 · 0행 ⑤ read-back 으로만 성공 판정
                  (② 대표 커버리지는 적재 뒤 따로 · status · missing · representatives_refresh_due)
08:30 기초지수     자기 계산에 필요한 종목의 커버리지만 본다(대표와 무관)
장중 신규 진입     활성 대표 전부 T-1 행이 있을 때만 · 아니면 구역 생략 · 회피 · 보유 그대로
CSV 갱신 안내      정합성 JSON `refresh_due` — 대표 결과로 바뀌지 않는다
빈 날 채우기       21거래일 창 안만 · 같은 날짜 KST 하루 1회(08:10 · 재시도 · 09:20 · 재실행 합산)
                  (일시 오류 날짜의 09:20 보강 1회는 POC3-02D-OPS-04 · test_poc3_02d_ops04_krx_backfill_retry)
```

합성 캘린더 · 임시 DB · 가짜 fetcher · 가짜 시계만 쓴다. **외부 조회 0건 · 라이브 DB ·
state · logs 미접근 · 실제 sleep 0.**
"""

from __future__ import annotations

import functools
import json
import os
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from app.intraday_config import schema
from app.intraday_config import store as config_store
from app.market_briefing import flow as briefing_flow
from app.market_briefing import krx_backfill, krx_store, krx_target_sync, meta_gate
from app.runtime_evidence import intraday_alert_flow as iflow
from app.runtime_evidence import sector_signal as ss
from app.runtime_evidence.sector_signal_state import load_sector_state, save_observation
from app.three_push_runtime import market_data_batch as mdb
from app.three_push_runtime.market_data_batch import RefreshResult
from tests import test_poc3_02d_ops03_krx_batch as kb

TODAY, T1 = kb.TODAY, kb.T1  # 2026-09-30 · 2026-09-29
TICKERS = kb.TICKERS  # T000 ~ T039 — 공식 CSV · KRX 응답 전종목
REPS_27 = TICKERS[:27]
ASOF = f"{TODAY.isoformat()}T10:30:00+09:00"
NOW = datetime(2026, 9, 30, 10, 30, tzinfo=kb.KST)
UNAVAILABLE = "intraday_config_unavailable"
MISSING = "representative_missing"


@pytest.fixture
def env(tmp_path):
    cal = kb._calendar(tmp_path)
    db = tmp_path / "m.sqlite"
    kb._seed(db, kb._window_before_t1(cal))  # 창 20일 · 종가 10000
    return {
        "tmp": tmp_path,
        "cal": cal,
        "db": db,
        "cpath": tmp_path / "consistency.json",
        "env": kb._env(tmp_path),
        "csv": kb._csv(tmp_path),
        "ledger": tmp_path / "ledger.json",
    }


def _t1_rows(bas_dd, tickers=TICKERS):
    # T-1 종가 11000 — 5일 · 20일 모두 +10%(08:30 기초지수 후보 · 장중 진입 검토 모양).
    return [kb._row(bas_dd, t, close=11000.0) for t in tickers]


def _sync(env, clock, fetcher, **kw):
    args = dict(
        today=TODAY,
        consistency_path=env["cpath"],
        official_csv_path=env["csv"],
        db_path=env["db"],
        env_path=env["env"],
        calendar_dir=env["cal"],
        fetcher=fetcher,
        clock=clock,
        sleep=clock.sleep,
        backfill_ledger_path=env["ledger"],
    )
    args.update(kw)
    return krx_target_sync.sync_krx_target(**args)


def _load_t1(env, **kw):
    clock = kb.Clock(8, 10, 20)
    f = kb.Fetcher(clock, lambda b, i: _t1_rows(b) if b == "20260929" else [])
    return _sync(env, clock, f, **kw), f


def _config_unreadable(monkeypatch):
    def _boom(**kw):
        raise RuntimeError("runtime db locked")

    monkeypatch.setattr(config_store, "get_active", _boom)


def _briefing(env):
    return briefing_flow.assemble_market_briefing(
        today_kst=TODAY.isoformat(),
        runtime_kst=f"{TODAY.isoformat()}T08:30:00+09:00",
        state_path=env["tmp"] / "briefing_state.json",
        consistency_path=env["cpath"],
        official_csv_path=env["csv"],
        sp500_return_pct=1.2,
        sp500_asof=T1,
        sp500_fresh=True,
        calendar_dir=env["cal"],
        db_path=env["db"],
    )


class Q:
    def __init__(self, ret, *, price=10000.0, asof=ASOF):
        self.current_price, self.day_return_pct, self.price_asof = price, ret, asof

    def has_day_return(self):
        return True


def _sectors(reps):
    return [
        {
            "sector_key": f"S{i}",
            "representative": {"ticker": t, "short_name": f"대표{i}"},
        }
        for i, t in enumerate(reps)
    ]


def _policy():
    p = dict(schema.INITIAL_POLICY_VALUES)
    p.update({"enabled": True, "policy_status": schema.POLICY_CONFIGURED})
    return p


def _intraday(monkeypatch, env, reps, *, entry, avoid="T000", state_path=None):
    """08:10 이 적재한 **같은 tmp DB** 를 장중 경로가 읽는다."""
    sectors = _sectors(reps) if reps is not None else []
    monkeypatch.setattr(iflow, "active_policy", lambda logger=None: _policy())
    monkeypatch.setattr(iflow, "_load_active_sectors", lambda logger=None: sectors)
    quotes = {t: Q(0.0) for t in TICKERS} | {entry: Q(2.0), avoid: Q(-2.5)}
    return iflow.assemble_intraday_alert(
        held_drop=[],
        holding_rows=[],
        market_quotes=quotes,
        today_kst=TODAY.isoformat(),
        now_kst=NOW,
        state_path=state_path or env["tmp"] / "sector_state.json",
        slot_label="10:30",
        quote_asof=f"{TODAY.isoformat()} 10:30",
        base_close_date=T1,
        db_path=env["db"],
        calendar_dir=env["cal"],
    )


# ── 적재 성공 판정에서 대표를 뺐다 · 대표는 따로 기록 ─────────────────────────


def test_config_unavailable_load_ok_briefing_ok_entry_omitted(env, monkeypatch):
    """활성 장중 설정을 못 읽는 날 — 적재 · 08:30 은 정상, 장중 진입 검토만 생략."""
    _config_unreadable(monkeypatch)
    out, f = _load_t1(env)

    assert out["status"] == "ok" and [a["result"] for a in out["attempts"]] == ["ok"]
    assert krx_store.row_count_on(T1, db_path=env["db"]) == len(TICKERS)
    rep = out["representatives"]
    assert rep["status"] == UNAVAILABLE and rep["source"] == "unavailable"
    assert rep["representatives_refresh_due"] is True
    assert out["representatives_refresh_due"] is True
    # 공식 CSV 갱신 안내(정합성 JSON)는 대표 결과와 무관하다.
    saved = meta_gate.load_consistency(env["cpath"])
    assert saved.status == meta_gate.STATUS_OK and saved.refresh_due is False
    assert out["refresh_due"] is False and saved.refresh_due_cycle_id is None
    assert "representative" not in env["cpath"].read_text(encoding="utf-8")

    brief = _briefing(env)
    assert brief.diagnostics["index_status"] == "ok", brief.diagnostics
    assert brief.diagnostics["index_candidates"] == ["KRX|코스피 200"]
    assert brief.diagnostics["refresh_notice"]["appended"] is False
    assert f"국내 {T1} 종가" in brief.message_text

    # 장중 — 정책은 읽혔는데 사업군(대표 목록)을 못 읽으면 진입 검토를 생략으로 센다.
    intra = _intraday(monkeypatch, env, None, entry="T026")
    assert intra.sector.entry_omitted is True
    assert intra.diagnostics["intraday_entry_omitted"] is True
    assert intra.diagnostics["intraday_entry_omitted_reason"] == UNAVAILABLE
    assert intra.diagnostics["intraday_representatives"]["status"] == UNAVAILABLE
    # 평가 불가 — 직전 사업군 관측을 회복으로 적지 않는다(D2).
    assert intra.sector.coverage_ok is False


def test_delisted_representative_load_ok_briefing_ok_entry_omitted(env):
    """대표 1종 상장폐지(T-1 응답에 없음) — 적재 · 08:30 정상 · 진입 검토만 생략 · 회피 유지."""
    reps = TICKERS[:26] + ["R_GONE"]
    out, _f = _load_t1(env, required_tickers=reps)

    assert out["status"] == "ok"
    assert out["attempts"][0]["result"] == "ok"
    assert "required_missing" not in json.dumps(out)
    rep = out["representatives"]
    assert (rep["status"], rep["missing"], rep["count"]) == (MISSING, ["R_GONE"], 27)
    assert rep["source"] == "argument" and out["representatives_refresh_due"] is True
    assert meta_gate.load_consistency(env["cpath"]).refresh_due is False

    brief = _briefing(env)
    assert brief.diagnostics["index_status"] == "ok"
    assert brief.diagnostics["index_candidates"] == ["KRX|코스피 200"]


def test_delisted_representative_intraday_omits_entry_keeps_avoid(env, monkeypatch):
    _load_t1(env, required_tickers=REPS_27)
    reps = TICKERS[:26] + ["R_GONE"]
    intra = _intraday(monkeypatch, env, reps, entry="T025")

    assert intra.sector.trend.usable is True  # 추세 기준일은 정상(T-1)
    assert intra.sector.entry_omitted is True
    assert not intra.sector.by_state(ss.STATE_ENTRY_REVIEW)
    assert [s.ticker for s in intra.sector.by_state(ss.STATE_AVOID_DROP)] == ["T000"]
    assert (
        "진입 회피" in intra.message_text and "신규 진입 검토" not in intra.message_text
    )
    assert "추세 기준" not in intra.message_text
    d = intra.diagnostics
    assert d["intraday_entry_omitted_reason"] == MISSING
    assert d["intraday_representatives"]["missing"] == ["R_GONE"]
    assert d["intraday_representatives"]["representatives_refresh_due"] is True
    reasons = {(e["ticker"], e["reason"]) for e in intra.sector.excluded}
    assert ("T025", ss.REASON_REPRESENTATIVE_MISSING) in reasons


def test_partial_representatives_missing_omits_entry_keeps_avoid(env, monkeypatch):
    """대표 4종이 T-1 행에 없다(27 중 23) — 사업군 커버리지는 통과해도 진입 검토는 생략."""
    _load_t1(env, required_tickers=REPS_27)
    reps = TICKERS[:23] + ["R1", "R2", "R3", "R4"]
    intra = _intraday(monkeypatch, env, reps, entry="T022")

    assert intra.sector.coverage_ok is True and intra.sector.entry_omitted is True
    assert intra.sector.representatives.missing == ("R1", "R2", "R3", "R4")
    assert not intra.sector.by_state(ss.STATE_ENTRY_REVIEW)
    assert intra.sector.by_state(ss.STATE_AVOID_DROP)


def test_delisted_representative_with_window_rows_still_omits_entry(env, monkeypatch):
    """실제 상장폐지 모양 — 폐지 전 창 행은 남고 T-1 행만 없다. 행이 있어도 기대 T-1
    날짜의 행이 없으면 대표 누락이다(행 존재가 아니라 T-1 날짜로 판정)."""
    clock = kb.Clock(8, 10, 20)
    listed = [t for t in TICKERS if t != "T026"]
    f = kb.Fetcher(clock, lambda b, i: _t1_rows(b, listed) if b == "20260929" else [])
    out = _sync(env, clock, f, required_tickers=REPS_27)
    assert out["status"] == "ok" and out["representatives"]["missing"] == ["T026"]
    assert krx_store.row_count_on(kb.T2, db_path=env["db"]) == len(TICKERS)

    intra = _intraday(monkeypatch, env, REPS_27, entry="T025")
    assert intra.sector.entry_omitted is True
    assert intra.diagnostics["intraday_entry_omitted_reason"] == MISSING
    assert intra.sector.representatives.missing == ("T026",)
    assert not intra.sector.by_state(ss.STATE_ENTRY_REVIEW)
    assert [s.ticker for s in intra.sector.by_state(ss.STATE_AVOID_DROP)] == ["T000"]


def test_all_27_representatives_present_entry_runs(env, monkeypatch):
    out, _f = _load_t1(env)  # 설정 없이도 적재는 성공한다(대표는 기록만)
    assert out["status"] == "ok"
    intra = _intraday(monkeypatch, env, REPS_27, entry="T026")

    assert intra.sector.representatives.ok and intra.sector.representatives.count == 27
    assert intra.sector.entry_omitted is False
    assert intra.diagnostics["intraday_entry_omitted_reason"] is None
    assert [s.ticker for s in intra.sector.by_state(ss.STATE_ENTRY_REVIEW)] == ["T026"]
    assert f"신규 진입 검토\n추세 기준 {T1} 종가" in intra.message_text


def test_all_present_config_representatives_recorded_ok(env, monkeypatch):
    payload = {
        "sector_representative_universe": {"sectors": _sectors(REPS_27)},
        "intraday_alert_policy": {"enabled": False},
    }
    monkeypatch.setattr(
        config_store,
        "get_active",
        lambda **kw: {"payload_json": json.dumps(payload)},
    )
    out, _f = _load_t1(env)
    rep = out["representatives"]
    assert (rep["status"], rep["source"], rep["count"]) == (
        "ok",
        "active_intraday_config",
        27,
    )
    assert rep["missing"] == [] and out["representatives_refresh_due"] is False


def test_representative_missing_keeps_previous_entry_observation(env, monkeypatch):
    """구역 생략 틱 — 직전 ENTRY_REVIEW 는 회복이 아니다(D2 · 평가 불가)."""
    from app.runtime_evidence.sector_signal_state import save_sector_state

    _load_t1(env, required_tickers=REPS_27)
    state = env["tmp"] / "sector_state.json"
    sent = (NOW - timedelta(minutes=60)).isoformat()
    save_sector_state(
        state,
        entries={
            "T025": {
                "state": ss.STATE_ENTRY_REVIEW,
                "last_delivered_state": ss.STATE_ENTRY_REVIEW,
                "last_sent_at": sent,
                "continuous": True,
                "sector_key": "S25",
            }
        },
        today_kst=TODAY.isoformat(),
        sent_today=1,
    )
    intra = _intraday(
        monkeypatch, env, TICKERS[:26] + ["R_GONE"], entry="T025", state_path=state
    )
    assert "T025" in intra.unevaluable
    save_observation(
        state,
        observed=intra.observed,
        today_kst=TODAY.isoformat(),
        unevaluable=intra.unevaluable,
    )
    entry = load_sector_state(state, today_kst=TODAY.isoformat()).entries["T025"]
    assert entry["continuous"] is True and entry["state"] == ss.STATE_ENTRY_REVIEW


def _assemble_without_policy_double(env):
    return iflow.assemble_intraday_alert(
        held_drop=[],
        holding_rows=[],
        market_quotes={t: Q(0.0) for t in TICKERS},
        today_kst=TODAY.isoformat(),
        now_kst=NOW,
        state_path=env["tmp"] / "sector_state.json",
        slot_label="10:30",
        db_path=env["db"],
        calendar_dir=env["cal"],
    )


def test_intraday_config_read_failure_is_recorded_apart_from_disabled(env, monkeypatch):
    """장중 설정 저장소를 읽지 못한 틱 — 발송 없음은 같고, 기록은 꺼짐과 구분한다."""
    _config_unreadable(monkeypatch)
    intra = _assemble_without_policy_double(env)
    assert intra.message_text == "" and intra.skip_reason == UNAVAILABLE
    d = intra.diagnostics
    assert d["intraday_policy_enabled"] is False
    assert d["intraday_config_error"] == "RuntimeError"
    assert d["intraday_entry_omitted"] is True
    assert d["intraday_entry_omitted_reason"] == UNAVAILABLE


@pytest.mark.parametrize(
    "active", [None, {"intraday_alert_policy": {"enabled": False}}]
)
def test_disabled_or_unset_policy_stays_policy_disabled(env, monkeypatch, active):
    row = None if active is None else {"payload_json": json.dumps(active)}
    monkeypatch.setattr(config_store, "get_active", lambda **kw: row)
    intra = _assemble_without_policy_double(env)
    assert intra.skip_reason == "policy_disabled"
    assert "intraday_config_error" not in intra.diagnostics
    assert "intraday_entry_omitted_reason" not in intra.diagnostics


def test_already_loaded_0920_run_records_representatives(env, monkeypatch):
    _load_t1(env, required_tickers=REPS_27)
    _config_unreadable(monkeypatch)
    clock = kb.Clock(9, 20, 0)
    f = kb.Fetcher(clock, lambda b, i: [])
    again = _sync(env, clock, f)
    assert again["mode"] == krx_target_sync.MODE_ALREADY_LOADED and f.calls == []
    assert again["representatives"]["status"] == UNAVAILABLE
    assert again["representatives_refresh_due"] is True


def test_target_not_obtained_does_not_evaluate_representatives(env):
    clock = kb.Clock(8, 40, 0)
    out = _sync(env, clock, kb.Fetcher(clock, lambda b, i: []), required_tickers=[])
    assert out["status"] == krx_target_sync.STATUS_TARGET_NOT_OBTAINED
    assert "representatives" not in out and "representatives_refresh_due" not in out


# ── 실제 run() 관통 — 러너 → 조립 → 집계 · 실행 기록 ────────────────────────


def test_run_config_unavailable_counts_entry_omitted(monkeypatch, tmp_path):
    from app.runtime_evidence import intraday_checkup_tally as tally_mod
    from tests import test_poc3_02d_ops03_intraday as it

    rig, ft = it._run_rig(monkeypatch, tmp_path, drop_last_day=False)
    rig["sectors"] = None  # 정책은 읽히고 사업군(대표 목록)은 없다
    rec = rig["runner"].run(ft.RISK_KIND, "send")
    assert rec["intraday_entry_omitted"] is True, rec
    assert rec["intraday_entry_omitted_reason"] == UNAVAILABLE
    ticks = json.loads(rig["tally"].read_text(encoding="utf-8"))["ticks"]
    assert ticks[-1]["entry_omitted"] is True
    line = tally_mod.render_summary_line(
        tally_mod.load_tally(rig["tally"], today_kst=ft.TODAY)
    )
    assert line.endswith("신규 진입 검토 생략 1회"), line


def test_run_delisted_representative_sends_avoid_and_counts_omission(
    monkeypatch, tmp_path
):
    from tests import test_poc3_02d_ops03_intraday as it

    rig, ft = it._run_rig(monkeypatch, tmp_path, drop_last_day=False)
    gone = {"sector_key": "S10", "representative": {"ticker": "R_GONE"}}
    rig["sectors"] = ft._sectors() + [gone]
    rec = rig["runner"].run(ft.RISK_KIND, "send")
    assert rec["status"] == "sent", rec
    body = rig["sent"].calls[-1]
    assert "진입 회피" in body and "대표8" in body  # 추격 주의는 그대로
    assert "신규 진입 검토" not in body and "추세 기준" not in body
    assert rec["intraday_entry_omitted_reason"] == MISSING
    assert rec["intraday_representatives"]["missing"] == ["R_GONE"]
    ticks = json.loads(rig["tally"].read_text(encoding="utf-8"))["ticks"]
    assert ticks[-1]["entry_omitted"] is True


# ── 설계자 RESULT STEP 6 — 빈 날 채우기 하루 1회 ledger ─────────────────────


def _calls_by_date(*fetchers):
    out: dict[str, int] = {}
    for f in fetchers:
        for _t, bas in f.calls:
            out[bas] = out.get(bas, 0) + 1
    return out


def test_same_window_date_not_called_twice_across_0810_retry_0920_rerun(env):
    for d in ("2026-09-18", "2026-09-21", "2026-09-22"):
        krx_store.delete_date(d, db_path=env["db"])

    # 08:10 — T-1 일시 장애 · 채우기는 09-18 을 부르다 원천 오류로 멈춘다.
    c1 = kb.Clock(8, 10, 20)

    def _first(b, i):
        if b == "20260929":
            return [] if i == 1 else _t1_rows(b)
        if b == "20260918":
            return RuntimeError("blip")
        return [] if b == "20260921" else kb._rows(b)  # 09-21 은 아직 공개 전

    f1 = kb.Fetcher(c1, _first)
    first = _sync(env, c1, f1, required_tickers=REPS_27)
    assert first["backfill"]["called"] == ["2026-09-18"]
    # 08:15 T-1 성공 뒤 재시도 — 오늘 아직 안 부른 날만(09-18 건너뜀).
    retry = first["backfill_retry"]
    assert retry["skipped_called_today"] == ["2026-09-18"]
    assert retry["called"] == ["2026-09-21", "2026-09-22"]
    assert retry["filled"] == ["2026-09-22"]

    # 09:20 --krx-only(이미 받음) · 10:05 수동 재실행 — 오늘 부른 날은 다시 안 부른다
    # (09-18 실패는 RuntimeError = 영구 실패 · 보강 표시 없는 호출이라 보강도 없다).
    fetchers = [f1]
    for hh, mm in ((9, 20), (10, 5)):
        c = kb.Clock(hh, mm, 0)
        f = kb.Fetcher(c, lambda b, i: kb._rows(b))
        # 09:20 은 운영처럼 보강 표시를 넘긴다(10:05 수동 run 은 넘기지 않는다).
        again = _sync(
            env,
            c,
            f,
            required_tickers=REPS_27,
            max_attempts=1,
            backfill_reinforcement=(hh, mm) == (9, 20),
        )
        assert again["mode"] == krx_target_sync.MODE_ALREADY_LOADED
        assert f.calls == []
        assert again["backfill"]["skipped_called_today"] == ["2026-09-18", "2026-09-21"]
        assert again["backfill"]["called"] == []
        fetchers.append(f)

    counts = _calls_by_date(*fetchers)
    assert counts == {
        "20260929": 2,  # 목표일 시각표 시도 — 채우기가 아니다(ledger 밖)
        "20260918": 1,
        "20260921": 1,
        "20260922": 1,
    }
    ledger = json.loads(env["ledger"].read_text(encoding="utf-8"))
    assert ledger == {
        "date_kst": TODAY.isoformat(),
        "calls": {"2026-09-18": 1, "2026-09-21": 1, "2026-09-22": 1},
    }


def test_new_kst_day_resets_ledger(env):
    krx_store.delete_date("2026-09-18", db_path=env["db"])
    env["ledger"].write_text(
        json.dumps({"date_kst": "2026-09-29", "calls": {"2026-09-18": 1}}), "utf-8"
    )
    out, f = _load_t1(env, required_tickers=REPS_27)
    assert [c[1] for c in f.calls] == ["20260929", "20260918"]
    assert out["backfill"]["called"] == ["2026-09-18"]
    assert out["backfill"]["calls_today"] == {"2026-09-18": 1}
    saved = json.loads(env["ledger"].read_text(encoding="utf-8"))
    assert saved["date_kst"] == TODAY.isoformat()


def test_fill_is_bounded_to_21_trading_day_window(env):
    """창(T-1 포함 21거래일) 밖의 빈 날은 부르지 않는다 — 전체 과거 채우기 금지."""
    from app import trading_day_lag

    window = trading_day_lag.trading_days_ending(T1, 21, calendar_dir=env["cal"])
    older = trading_day_lag.trading_days_ending(window[0], 3, calendar_dir=env["cal"])
    assert older[-1] == window[0] and older[0] < window[0]
    # 창 밖(창 첫날 이전) 날짜는 원래 저장돼 있지 않다 — 부르면 안 된다.
    assert krx_store.row_count_on(older[0], db_path=env["db"]) == 0
    krx_store.delete_date(window[3], db_path=env["db"])
    out, f = _load_t1(env, required_tickers=REPS_27)
    assert out["backfill"]["missing_before"] == [window[3]]
    assert [c[1] for c in f.calls] == ["20260929", window[3].replace("-", "")]


def test_unreadable_ledger_written_today_stops_fill(env):
    krx_store.delete_date("2026-09-18", db_path=env["db"])
    env["ledger"].write_text(
        "{broken", "utf-8"
    )  # 오늘 쓴 파일 — 오늘 무엇을 불렀는지 모른다
    now = datetime(2026, 9, 30, 8, 10, tzinfo=kb.KST).timestamp()
    os.utime(env["ledger"], (now, now))
    out, f = _load_t1(env, required_tickers=REPS_27)
    assert out["backfill"]["stopped"] == krx_backfill.STOP_LEDGER_UNREADABLE
    assert [c[1] for c in f.calls] == ["20260929"]  # 목표일만 · 채우기 0회


def test_unreadable_ledger_from_previous_day_starts_fresh(env):
    krx_store.delete_date("2026-09-18", db_path=env["db"])
    env["ledger"].write_text("{broken", "utf-8")
    old = datetime(2026, 9, 29, 12, 0, tzinfo=kb.KST).timestamp()
    os.utime(env["ledger"], (old, old))
    out, f = _load_t1(env, required_tickers=REPS_27)
    assert out["backfill"]["called"] == ["2026-09-18"]
    assert json.loads(env["ledger"].read_text("utf-8"))["date_kst"] == "2026-09-30"


def test_ledger_write_failure_makes_no_fill_call(env, monkeypatch):
    krx_store.delete_date("2026-09-18", db_path=env["db"])

    def _fail(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(krx_backfill, "_write_calls", _fail)
    out, f = _load_t1(env, required_tickers=REPS_27)
    assert out["backfill"]["stopped"] == "ledger_error:OSError"
    assert out["backfill"]["called"] == [] and [c[1] for c in f.calls] == ["20260929"]


def test_default_ledger_sits_next_to_krx_table(tmp_path):
    db = tmp_path / "market" / "market_data.sqlite"
    assert krx_backfill.ledger_path_for(db) == tmp_path / "market" / (
        "krx_backfill_ledger.json"
    )
    assert krx_backfill.ledger_path_for(None).as_posix() == (
        "state/market/krx_backfill_ledger.json"
    )


# ── 배치 상태 · 09:20 보강 기록 ───────────────────────────────────────────────


@pytest.fixture
def batch(monkeypatch, tmp_path):
    import scripts.run_oci_market_data_batch as batch

    monkeypatch.setattr(mdb, "MARKET_DATA_BATCH_STATE_PATH", tmp_path / "bs.json")
    monkeypatch.setattr(
        mdb, "KRX_REINFORCEMENT_STATE_PATH", tmp_path / "reinforce.json"
    )
    monkeypatch.setattr(batch, "_kst_today", lambda: TODAY)
    return batch


def _stub_price_stages(monkeypatch, batch, tmp_path):
    monkeypatch.setattr(batch, "collect_approved_tickers", lambda: ["069500"])
    monkeypatch.setattr(
        batch,
        "refresh_approved_prices",
        lambda tickers, *, end_date, **kw: RefreshResult(
            attempted=1, success=1, fail=0, price_data_as_of=T1
        ),
    )
    ok = {"status": "ok", "as_of_date": T1, "error": None}
    monkeypatch.setattr(
        "app.market_benchmark_batch.refresh_benchmarks",
        lambda **kw: {"kospi": ok, "vix": ok, "status": "ok", "failed": []},
    )
    monkeypatch.setattr(
        batch,
        "_build_universe_artifact",
        lambda *, price_data_as_of: ({"summary": {}}, f"{TODAY}T08:10:30", "ok"),
    )
    monkeypatch.setattr(
        "app.universe_bootstrap.artifact_validator.validate_artifact",
        lambda *a, **k: (True, None, {}),
    )
    monkeypatch.setattr(
        batch, "evaluate_freshness", lambda **kw: SimpleNamespace(ok=True, reason="")
    )
    monkeypatch.setattr(
        "app.momentum.universe_mode.save_latest_artifact",
        lambda result: tmp_path / "art.json",
    )


def test_batch_state_records_representatives_and_backfill(batch, monkeypatch, tmp_path):
    _stub_price_stages(monkeypatch, batch, tmp_path)
    rep = {
        "source": "unavailable",
        "status": UNAVAILABLE,
        "count": 0,
        "missing": [],
        "representatives_refresh_due": True,
    }
    backfill = {"called": ["2026-09-18"], "calls_today": {"2026-09-18": 1}}

    def _krx(**kw):
        return {
            "status": "ok",
            "mode": "scheduled",
            "target_date": T1,
            "basis_date": "20260929",
            "attempts": [{"result": "ok"}],
            "consistency_status": "ok",
            "refresh_due": False,
            "representatives": rep,
            "representatives_refresh_due": True,
            "backfill": backfill,
        }

    monkeypatch.setattr(krx_target_sync, "sync_krx_target", _krx)
    rec = batch.run(mode="run")
    assert rec["status"] == "success" and rec["krx_sync_status"] == "ok"
    saved = mdb.read_batch_state()
    assert saved["krx_representatives"] == rep
    assert saved["representatives_refresh_due"] is True
    assert saved["krx_backfill"] == {"backfill": backfill}
    # CSV 갱신 안내 판정은 따로 · 기존 키는 그대로(Spike 가 읽는다).
    assert rec["meta_refresh_due"] is False
    assert {"status", "refresh_date_kst", "price_data_as_of"} <= set(saved)


def test_reinforcement_record_carries_representatives_and_backfill(
    batch, monkeypatch, tmp_path
):
    env = {
        "cal": kb._calendar(tmp_path),
        "db": tmp_path / "m.sqlite",
        "env": kb._env(tmp_path),
    }
    kb._seed(env["db"], kb._window_before_t1(env["cal"]))
    krx_store.delete_date("2026-09-21", db_path=env["db"])
    calls: list[str] = []

    def _fetch(bas_dd, key):
        calls.append(bas_dd)
        return kb._rows(bas_dd)

    t = datetime(2026, 9, 30, 9, 20, tzinfo=kb.KST)
    real = krx_target_sync.sync_krx_target
    monkeypatch.setattr(
        krx_target_sync,
        "sync_krx_target",
        functools.partial(
            real,
            db_path=env["db"],
            env_path=env["env"],
            calendar_dir=env["cal"],
            fetcher=_fetch,
            clock=lambda: t,
            sleep=lambda s: pytest.fail("09:20 보강은 기다리지 않는다"),
        ),
    )
    _config_unreadable(monkeypatch)
    rec = batch.run_krx_only()
    assert rec["status"] == "ok" and calls == ["20260929", "20260921"]
    saved = mdb.read_krx_reinforcement_state()
    assert saved["krx_representatives"]["status"] == UNAVAILABLE
    assert saved["representatives_refresh_due"] is True
    bf = saved["krx_backfill"]["backfill"]
    assert bf["called"] == ["2026-09-21"] and bf["calls_today"] == {"2026-09-21": 1}
    assert bf["retried"] == []  # POC3-02D-OPS-04 — 보강 기록 키가 09:20 기록까지 간다
    ledger = krx_backfill.ledger_path_for(env["db"])
    assert json.loads(ledger.read_text("utf-8"))["calls"] == {"2026-09-21": 1}


def test_write_batch_state_old_callers_still_work(tmp_path):
    p = tmp_path / "bs.json"
    mdb.write_batch_state(
        status="success",
        price_data_as_of=T1,
        artifact_generated_at=None,
        refresh_date_kst=TODAY.isoformat(),
        refresh_completed_at="x",
        state_path=p,
    )
    saved = json.loads(p.read_text("utf-8"))
    assert saved["krx_representatives"] is None
    assert saved["representatives_refresh_due"] is None
    assert saved["krx_backfill"] is None


def test_load_success_does_not_depend_on_representatives_in_checks():
    """`check_response` 는 대표 목록을 받지 않는다(옛 ② 제거)."""
    import inspect

    from app.market_briefing import krx_target_checks

    params = inspect.signature(krx_target_checks.check_response).parameters
    assert "required" not in params
    assert set(params) == {"rows", "bas_dd", "db_path"}


def test_representative_read_failure_is_recorded_not_raised(tmp_path):
    """T-1 행을 못 읽어도 예외를 올리지 않는다 — 성공한 적재 결과를 뒤집지 않는다."""
    from app.market_briefing import krx_target_checks

    rep = krx_target_checks.evaluate_representatives(
        T1, db_path=tmp_path, required_tickers=REPS_27  # 폴더 — sqlite 가 못 연다
    )
    assert rep["status"] == krx_target_checks.COVERAGE_NOT_EVALUATED
    assert rep["error_type"] == "OperationalError"
    assert rep["representatives_refresh_due"] is None
