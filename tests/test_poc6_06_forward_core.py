"""POC6-06 — 표본 · 입력 판 선택 · 성숙 목표 · 05 허용 형식 · 비교 보고 시험(학습 없음).

tmp 폴더의 가짜 05 보관소(거래일 파일 = 평일 전부 · KOSPI 저장일 = 같은 날)와 결정적 가짜 가격만 쓴다.
라이브 DB · state · 외부 조회 · SSH 0. 계약 출처: 설계 V1 §2 · §6 ~ §10 · PLAN 판정(2026-10-22) §2 ~ §6.
"""

from __future__ import annotations

import json
import math
import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.forward_compare import cohort, inputs, records, report
from app.forward_compare import protocol as P
from app.ml_evidence import daily_naver, store, transfer
from app.ml_evidence import forward_artifacts as FA
from app.reentry_review import model as m06
from app.three_push_runtime import ledger_outcome

UTC = timezone.utc
TICKERS = P.EXPECTED_COHORT
FIRST = date(2025, 1, 1)


# ── 공용 세계: 가짜 가격 · 가짜 05 묶음 ───────────────────────────────────────


def weekdays(lo: date, hi: date) -> list[date]:
    out, d = [], lo
    while d <= hi:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def price(ticker: str, d: date) -> float:
    k = sum(ord(c) for c in ticker)
    n = (d - FIRST).days
    wave = 0.15 * math.sin(n / (9 + k % 5)) + 0.06 * math.sin(n / (3 + k % 3))
    return round(10000.0 * (1.0 + wave + 0.0004 * n * ((k % 3) - 1)), 2)


def series(ticker: str, lo: date, hi: date) -> list[list]:
    """[date, o, h, l, close, vol, change] — change = 같은 응답 종가 변화(FDR 과 같은 방식)."""
    out, prev = [], price(ticker, lo - timedelta(days=1 if lo.weekday() else 3))
    for d in weekdays(lo, hi):
        c = price(ticker, d)
        out.append([d.isoformat(), c, c, c, c, 1000, c / prev - 1.0])
        prev = c
    return out


def drop(rows: list[list], day: str) -> list[list]:
    """응답에 그 날이 없던 것처럼 — 다음 행 change 를 같은 응답 직전 종가로 다시 계산(FDR 방식)."""
    out = [list(r) for r in rows if r[0] != day]
    for i in range(1, len(out)):
        if out[i - 1][0] < day < out[i][0]:
            out[i][6] = out[i][4] / out[i - 1][4] - 1.0
    return out


def calendar_csv(year: int, skip: tuple = ()) -> bytes:
    days = [d.isoformat() for d in weekdays(date(year, 1, 1), date(year, 12, 31))]
    return ("date\n" + "\n".join(d for d in days if d not in skip) + "\n").encode()


def put_lines(root: Path, lines: list[dict]) -> dict:
    w = store.GzJsonlWriter(root)
    for x in lines:
        w.write(x)
    return w.finish()


def obj(root: Path, data: bytes, role: str, fmt: str = "json") -> dict:
    got = store.put_bytes(root, data)
    return {"sha256": got["sha256"], "bytes": got["bytes"], "role": role, "format": fmt}


def daily(
    ev: Path,
    target_day: str,
    published: datetime,
    copied: datetime,
    *,
    tickers=TICKERS,
    status="OK",
    edit=None,
    reuse=None,
    cal_skip=(),
    receipt=True,
    line_status="OK",
) -> dict:
    """가짜 05 일일 묶음 하나(창 = 기준일까지 120일 · 거래일 파일 · KOSPI 저장일 object)."""
    t = date.fromisoformat(target_day)
    lines = []
    for tk in tickers:
        rows = series(tk, t - timedelta(days=120), t)
        if edit is not None:
            rows = edit(tk, rows)
        lines.append(
            {
                "ticker": tk,
                "status": line_status,
                "observed_at": store.iso(published),
                "rows": rows,
            }
        )
    objs = []
    win = []
    if lines:
        info = put_lines(ev, lines)
        objs.append(
            {
                "sha256": info["sha256"],
                "bytes": info["bytes"],
                "role": "naver_windows",
                "format": "jsonl.gz",
                "lines": info["lines"],
            }
        )
        win.append(info["sha256"])
    for o in (reuse or {}).get("objects", []):
        if o["role"] == "naver_windows":
            objs.append(
                dict(o, role="naver_windows_target_day", reused_from=reuse["run_id"])
            )
            win.insert(0, o["sha256"])
    kospi = [d.isoformat() for d in weekdays(FIRST, t)]
    k_obj = obj(
        ev,
        json.dumps({"dates": kospi, "source": "test"}).encode(),
        "kospi_stored_dates",
    )
    cal_files = []
    for year in (2025, 2026):
        c = obj(ev, calendar_csv(year, cal_skip), "calendar_csv", "csv")
        objs.append(c)
        cal_files.append(
            {
                "name": f"krx_trading_days_{year}.csv",
                "sha256": c["sha256"],
                "bytes": c["bytes"],
            }
        )
    objs.append(k_obj)
    m = {
        "schema": store.SCHEMA,
        "run_id": store.new_run_id(published),
        "kind": "DAILY_COLLECTION",
        "site": "OCI",
        "status": status,
        "sources": {
            "date_axis": {
                "kospi_stored_dates": {"object": k_obj["sha256"], "count": len(kospi)},
                "calendar_files": cal_files,
            },
            "naver_etf_windows": {
                "target_day": target_day,
                "objects_for_target_day": win,
            },
        },
        "objects": sorted(
            {o["sha256"]: o for o in objs}.values(), key=lambda o: o["sha256"]
        ),
    }
    rec = (
        (lambda: {"site": "PC", "copied_at_pc": store.iso(copied)}) if receipt else None
    )
    return store.publish_run(ev, m, clock=lambda: published, receipt=rec)[1]


def z(y, mo, d, h=0, mi=0, s=0, us=0) -> datetime:
    return datetime(y, mo, d, h, mi, s, us, tzinfo=UTC)


def d20(ticker: str, D: str) -> float:
    days = [
        d
        for d in weekdays(
            date.fromisoformat(D), date.fromisoformat(D) + timedelta(days=40)
        )
    ]
    c = [price(ticker, d) for d in days[:21]]
    return min(0.0, min(c[h] / c[0] - 1.0 for h in range(1, 21)))


# ── 표본 ──────────────────────────────────────────────────────────────────


def _cohort_world(tmp_path, monkeypatch, extra_days=None):
    ev = tmp_path / "ev"
    names = list(TICKERS)
    higher = [f"9{i:05d}" for i in range(400)]
    higher = [
        t for t in higher if P.cohort_rank_key(t) > P.cohort_rank_key(TICKERS[-1])
    ][:30]
    lower = next(
        t
        for t in (f"8{i:05d}" for i in range(5000))
        if P.cohort_rank_key(t) < P.cohort_rank_key(TICKERS[0])
    )
    rows = [
        {"ticker": t, "name": f"N{t}", "category": "1"}
        for t in sorted(names + higher + [lower])
    ]
    lst = obj(
        ev,
        json.dumps({"rows": rows, "observed_at": "x", "source": "t"}).encode(),
        "etf_list_response",
    )
    m = {
        "schema": store.SCHEMA,
        "run_id": "20261022T103723Z_aaaaaaaa",
        "kind": "DAILY_COLLECTION",
        "site": "OCI",
        "status": "PARTIAL",
        "objects": [lst],
        "sources": {
            "etf_list": {
                "effective": {
                    "object": lst["sha256"],
                    "list_hash": daily_naver.list_hash(rows),
                    "list_date": "2026-10-22",
                }
            }
        },
    }
    store.publish_run(
        ev,
        m,
        clock=lambda: z(2026, 10, 22, 10, 37),
        receipt=lambda: {"copied_at_pc": "x"},
    )
    monkeypatch.setattr(cohort, "LIST_RUN", m["run_id"])
    monkeypatch.setattr(cohort, "LIST_OBJECT", lst["sha256"])
    monkeypatch.setattr(cohort, "LIST_HASH", daily_naver.list_hash(rows))
    db = tmp_path / "market.sqlite"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE etf_daily_price (ticker TEXT, date TEXT, close REAL)")
    con.execute("CREATE TABLE holdings (ticker TEXT)")  # 보유 표가 있어도 읽지 않는다
    days = [d.isoformat() for d in weekdays(date(2024, 1, 1), date(2026, 10, 23))]
    want = {t: 400 for t in names + higher} | {lower: 364} | (extra_days or {})
    for t, n in want.items():
        lo = len(days) - n - 2  # 마지막 2일은 기준일 뒤(세지 않음)
        keep = days[lo:]
        con.executemany(
            "INSERT INTO etf_daily_price VALUES (?, ?, 1.0)", [(t, d) for d in keep]
        )
    con.executemany(
        "INSERT INTO etf_daily_price VALUES (?, ?, 0)", [(lower, d) for d in days[:10]]
    )
    con.commit()
    con.close()
    return ev, db, lower


def test_cohort_is_fixed_by_hash_rule_and_ignores_holdings(tmp_path, monkeypatch):
    ev, db, lower = _cohort_world(tmp_path, monkeypatch)
    root = tmp_path / "r"
    status, body = cohort.select(root, ev, db, z(2026, 10, 22, 13))
    assert status == "OK" and tuple(body["tickers"]) == TICKERS
    # 364일(유효 종가) = 후보 아님 · 0 종가는 세지 않음
    assert lower not in body["candidates"]
    assert "0015K0" in body["tickers"] and body["aux_groups"]["inverse_2"] == [
        "271050",
        "282000",
    ]
    assert len(body["aux_groups"]["rest_17"]) == 17
    con = sqlite3.connect(db)
    con.execute("INSERT INTO holdings VALUES ('364960')")
    con.execute("DELETE FROM etf_daily_price WHERE ticker = '364960'")
    con.commit()
    con.close()
    again, body2 = cohort.select(root, ev, db, z(2026, 11, 1))
    # 고정 뒤 라이브 DB 로 다시 순위를 매기지 않음
    assert again == "ALREADY" and body2 == body
    assert cohort.load(root)["tickers"] == list(TICKERS)


def test_cohort_mismatch_stops_without_writing(tmp_path, monkeypatch):
    low = next(
        t
        for t in (f"8{i:05d}" for i in range(5000))
        if P.cohort_rank_key(t) < P.cohort_rank_key(TICKERS[0])
    )
    ev, db, lower = _cohort_world(tmp_path, monkeypatch, extra_days={low: 400})
    assert lower == low
    with pytest.raises(cohort.CohortError):
        cohort.select(tmp_path / "r", ev, db, z(2026, 10, 22, 13))
    assert not cohort.path(tmp_path / "r").exists()


# ── 입력 판 선택(판정 §2 Q2 (a)) ─────────────────────────────────────────────


D = "2026-10-22"
CUT = z(2026, 10, 23, 1)


def test_input_is_earliest_valid_original_publication_and_skips_ineligible(tmp_path):
    ev = tmp_path / "ev"
    # 늦게 공개된 정상 묶음(나중 판)
    late = daily(ev, D, z(2026, 10, 23, 0, 50), z(2026, 10, 23, 0, 55))
    # 더 이른 공개지만 FAILED · cutoff 뒤 PC 수신 · cutoff 뒤 공개 · receipt 없음 = 모두 제외
    daily(ev, D, z(2026, 10, 23, 0, 10), z(2026, 10, 23, 0, 12), status="FAILED")
    daily(ev, D, z(2026, 10, 23, 0, 11), z(2026, 10, 23, 2))
    daily(ev, D, z(2026, 10, 23, 2), z(2026, 10, 23, 2, 5))
    daily(ev, D, z(2026, 10, 23, 0, 13), z(2026, 10, 23, 0, 14), receipt=False)

    # 가장 이른 정상 PARTIAL 묶음 — 364960 창에 축 날짜 결측(검사 실패) → 그 종목은 다음 판
    def hole(tk, rows):
        return drop(rows, "2026-10-20") if tk == "364960" else rows

    early = daily(
        ev,
        D,
        z(2026, 10, 23, 0, 20),
        z(2026, 10, 23, 0, 21),
        status="PARTIAL",
        edit=hole,
    )
    e = inputs.Evidence(ev, CUT)
    try:
        assert [r.run_id for r in e.runs] == [early["run_id"], late["run_id"]]
        reasons = {x["run_id"]: x["reason"] for x in e.excluded if "run_id" in x}
        assert sorted(reasons.values()) == sorted(
            [
                "상태 FAILED",
                "PC 수신이 cutoff 뒤",
                "OCI 공개가 cutoff 뒤",
                "PC 수신 시각 없음 · 형식 아님",
            ]
        )
        a = e.select_input("122090", D)
        assert a["status"] == "OK" and a["source"]["run_id"] == early["run_id"]
        assert a["source"]["available_at"] == early["published_at"]
        b = e.select_input("364960", D)
        assert b["source"]["run_id"] == late["run_id"]
        assert b["tried"][0]["reason"] == "WINDOW" and b["tried"][0]["detail"] == [
            "MISSING_PRICE"
        ]
        c = e.select_input("0015K0", D)  # 영숫자 식별자 그대로
        closes = [r[1] for r in c["window"]]
        assert c["features"] == m06.features_at(closes, len(closes) - 1)
        assert c["window"][-1][0] == D and len(c["window"]) == 61
    finally:
        e.close()


def test_reused_object_keeps_original_publication_and_damage_falls_through(tmp_path):
    ev = tmp_path / "ev"
    first = daily(
        ev, D, z(2026, 10, 23, 0, 20), z(2026, 10, 23, 0, 21), tickers=TICKERS[:3]
    )
    second = daily(
        ev,
        D,
        z(2026, 10, 23, 0, 40),
        z(2026, 10, 23, 0, 41),
        tickers=TICKERS[3:],
        reuse=first,
    )
    e = inputs.Evidence(ev, CUT)
    try:
        got = e.select_input(TICKERS[0], D)
        assert (
            got["source"]["run_id"] == first["run_id"]
        )  # 참조한 묶음이 아니라 원래 공개 판
        assert e.select_input(TICKERS[5], D)["source"]["run_id"] == second["run_id"]
        assert e.select_input("999999", D)["status"] == "INPUT_MISSING"
    finally:
        e.close()
    win = next(o["sha256"] for o in first["objects"] if o["role"] == "naver_windows")
    p = store.object_path(ev, win)
    p.write_bytes(p.read_bytes()[:-3] + b"xyz")
    e = inputs.Evidence(ev, CUT)
    try:
        got = e.select_input(TICKERS[0], D)
        assert (
            got["status"] == "INPUT_CHECK_REQUIRED"
            and got["tried"][0]["reason"] == "OBJECT_DAMAGED"
        )
    finally:
        e.close()


def test_input_window_basis_break_and_bad_close_are_rejected(tmp_path):
    ev = tmp_path / "ev"

    def broken(tk, rows):
        rows = [list(r) for r in rows]
        if tk == TICKERS[0]:
            rows[-3][6] += 0.01  # change ≠ 종가 변화 = 가격 기준 변화
        if tk == TICKERS[1]:
            rows[-2][4] = 0.0
        return rows

    daily(ev, D, z(2026, 10, 23, 0, 20), z(2026, 10, 23, 0, 21), edit=broken)
    e = inputs.Evidence(ev, CUT)
    try:
        assert e.select_input(TICKERS[0], D)["tried"][0]["detail"] == ["BASIS_BREAK"]
        assert e.select_input(TICKERS[1], D)["tried"][0]["detail"] == ["BAD_CLOSE"]
        assert e.select_input(TICKERS[2], D)["status"] == "OK"
    finally:
        e.close()


# ── 성숙 목표(설계 §8) ───────────────────────────────────────────────────────


D20_END = "2026-11-19"  # D(10-22) 다음 20번째 평일


def _mature_world(tmp_path, edit=None, end=D20_END):
    ev = tmp_path / "ev"
    daily(ev, D, z(2026, 10, 23, 0, 20), z(2026, 10, 23, 0, 21))
    daily(ev, end, z(2026, 11, 20, 0, 40), z(2026, 11, 20, 0, 41), edit=edit)
    return ev


def test_target_states_and_known_d20(tmp_path):
    ev = tmp_path / "ev"
    daily(ev, D, z(2026, 10, 23, 0, 20), z(2026, 10, 23, 0, 21))
    e = inputs.Evidence(ev, z(2026, 11, 1))
    try:
        assert e.select_target(TICKERS[0], D)["status"] == "PENDING_NOT_DUE"
    finally:
        e.close()
    ev2 = _mature_world(tmp_path / "b")
    e = inputs.Evidence(ev2, z(2026, 11, 20, 1))
    try:
        got = e.select_target("0015K0", D)
        assert got["status"] == "MATURED" and got["target_end"] == D20_END
        assert len(got["closes"]) == 21 and got["closes"][0][0] == D
        assert got["target"] == pytest.approx(d20("0015K0", D), abs=1e-12)
    finally:
        e.close()


def test_nineteen_days_after_D_is_not_due(tmp_path):
    ev = _mature_world(tmp_path, end="2026-11-18")  # D 다음 19거래일까지만 지남
    e = inputs.Evidence(ev, z(2026, 11, 20, 1))
    try:
        got = e.select_target(TICKERS[0], D)
        assert got["status"] == "PENDING_NOT_DUE" and got["axis_after_D"] == 19
    finally:
        e.close()


def test_bootstrap_examples_end_strictly_before_D(tmp_path):
    from app.forward_compare import bootstrap
    from app.reentry_review import prices as px

    D_ = "2026-03-02"
    cal = tmp_path / "cal"
    cal.mkdir()
    for year in (2025, 2026):
        (cal / f"krx_trading_days_{year}.csv").write_bytes(calendar_csv(year))
    rows = series("122090", FIRST, date(2026, 3, 10))  # D 와 그 뒤 종가까지 받은 판
    at = "2026-03-11T00:00:00.000000Z"
    prices = {"tickers": {"122090": {"observed_at": at, "rows": rows}}}
    meta = {"id": "x", "prices_sha256": "y", "finished_at": at}
    kospi = [d.isoformat() for d in weekdays(FIRST, date(2026, 3, 10))]
    axis = px.research_axis(D_, FIRST.isoformat(), kospi, calendar_dir=cal)
    ex = bootstrap.build_examples(prices, meta, axis, D_)
    n = len(axis["dates"])
    assert axis["dates"][-1] == D_ and len(ex["rows"]) == n - m06.LB - m06.H - 1
    assert (
        max(r[5] for r in ex["rows"]) == axis["dates"][-2]
    )  # 목표 끝 < D(= D 는 제외)
    assert ex["per_ticker"]["122090"]["examples"] == len(ex["rows"])
    assert ex["per_ticker"]["0015K0"]["reason"] == "초기 자료 미확보"


def test_due_but_missing_or_bad_is_not_zero(tmp_path):
    def edit(tk, rows):
        rows = drop(rows, "2026-11-05") if tk == TICKERS[0] else [list(r) for r in rows]
        if tk == TICKERS[1]:
            for r in rows:
                if r[0] == "2026-11-06":
                    r[4] = -1.0
        return rows

    ev = _mature_world(tmp_path, edit=edit)
    e = inputs.Evidence(ev, z(2026, 11, 20, 1))
    try:
        assert e.select_target(TICKERS[0], D)["status"] == "DUE_DATA_MISSING"
        assert e.select_target(TICKERS[1], D)["status"] == "DATA_CHECK_REQUIRED"
        assert e.select_target(TICKERS[2], D)["status"] == "MATURED"
    finally:
        e.close()


def test_target_uses_window_content_not_status_label(tmp_path):
    ev = tmp_path / "ev"
    daily(ev, D, z(2026, 10, 23, 0, 20), z(2026, 10, 23, 0, 21))
    daily(
        ev,
        D20_END,
        z(2026, 11, 20, 0, 40),
        z(2026, 11, 20, 0, 41),
        line_status="NO_NEW_ROW",
    )
    e = inputs.Evidence(ev, z(2026, 11, 20, 1))
    try:
        assert e.select_target(TICKERS[0], D)["status"] == "MATURED"
    finally:
        e.close()


def test_target_reads_only_windows_that_can_hold_D(tmp_path, monkeypatch):
    def gone(tk, rows):
        return [] if tk == TICKERS[0] else rows

    ev = _mature_world(tmp_path, edit=gone)
    far = daily(ev, "2027-03-01", z(2027, 3, 2, 0, 40), z(2027, 3, 2, 0, 41))
    far_obj = next(o["sha256"] for o in far["objects"] if o["role"] == "naver_windows")
    e = inputs.Evidence(ev, z(2027, 3, 2, 1), tickers={TICKERS[0]})
    read = []
    real = inputs.Evidence.lines
    monkeypatch.setattr(
        inputs.Evidence, "lines", lambda self, sha: read.append(sha) or real(self, sha)
    )
    try:
        got = e.select_target(TICKERS[0], D)
        assert (
            got["status"] == "DUE_DATA_MISSING" and far_obj not in read
        )  # D+120일 밖 묶음은 읽지 않음
        assert set(e._lines[read[0]]) <= {TICKERS[0]}  # 고른 종목 줄만 기억
    finally:
        e.close()


def test_calendar_uncertain_is_pending_calendar(tmp_path):
    ev = tmp_path / "ev"
    daily(ev, D, z(2026, 10, 23, 0, 20), z(2026, 10, 23, 0, 21))
    daily(
        ev, D20_END, z(2026, 11, 20, 0, 40), z(2026, 11, 20, 0, 41), cal_skip=(D20_END,)
    )
    e = inputs.Evidence(ev, z(2026, 11, 20, 1))
    try:
        assert e.select_target(TICKERS[0], D)["status"] == "PENDING_CALENDAR"
        cal = e.calendar_dir(e.latest())
        assert (
            inputs.next_trading_day("2026-10-23", cal) == "2026-10-26"
        )  # 금요일 D → 월요일
    finally:
        e.close()


def test_close_cutoff_is_existing_constant():
    assert P.CLOSE_CUTOFF == ledger_outcome.CLOSE_CUTOFF == "15:30"


# ── 05 허용 형식(판정 §6) ────────────────────────────────────────────────────


R = FA.ROOT_REL


@pytest.mark.parametrize(
    "rel,kind",
    [
        (f"{R}/cohort_v1/cohort.json", "cohort"),
        (f"{R}/targets/2026-10-22/0015K0.json", "target"),
        (f"{R}/models/mv_0123456789abcdef/hgb.joblib", "model_hgb"),
        (f"{R}/predictions/2026-10-22/20261023T010000Z_0123abcd.json", "prediction"),
        (
            f"{R}/predictions/2026-10-22/20261023T010000Z_0123abcd.receipt.json",
            "prediction_receipt",
        ),
        (f"{R}/predictions/2026-10-22/20261023T010000Z_0123abcd.receipt.json.x", None),
        (f"{R}/../poc6_06/cohort_v1/cohort.json", None),
        (f"/{R}/cohort_v1/cohort.json", None),
        (f"{R}_evil/cohort_v1/cohort.json", None),
        (f"{R}/cohort_v1/../cohort_v1/cohort.json", None),
        (f"{R}\\cohort_v1\\cohort.json", None),
        (f"{R}/predictions/2026-02-30/20261023T010000Z_0123abcd.json", None),
        (f"{R}/runs/20261399T010000Z_0123abcd.json", None),
        (f"{R}/models/mv_0123456789abcdef/other.pkl", None),
        (f"{R}/targets/2026-10-22/0015k0.json", None),
    ],
)
def test_artifact_paths_are_normalized_not_prefix_matched(rel, kind):
    assert FA.classify(rel)[0] == kind


def _artifact_manifest(files: dict[str, bytes], ev: Path, kind_override=None) -> dict:
    rows, objs = [], {}
    for rel, data in files.items():
        o = store.put_bytes(ev, data)
        k = FA.classify(rel)[0]
        rows.append(
            {
                "rel_path": rel,
                "type": kind_override or k,
                "sha256": o["sha256"],
                "bytes": o["bytes"],
            }
        )
        objs[o["sha256"]] = {
            "sha256": o["sha256"],
            "bytes": o["bytes"],
            "role": "x",
            "format": "raw",
        }
    return {
        "schema": store.SCHEMA,
        "run_id": "20261023T020000Z_0123abcd",
        "kind": FA.KIND,
        "protocol_id": FA.PROTOCOL_ID,
        "site": "PC",
        "status": "OK",
        "published_at": "2026-10-23T02:00:00.000000Z",
        "files": rows,
        "objects": list(objs.values()),
    }


def _training(mv: str, refs: dict) -> bytes:
    return P.dumps(P.doc("training", model_version=mv, file_sha256=refs))


def test_artifact_checks_schema_reference_and_hash(tmp_path):
    ev = tmp_path / "ev"
    mv = "mv_0123456789abcdef"
    hgb = b"\x80binary"
    good = {
        f"{R}/models/{mv}/hgb.joblib": hgb,
        f"{R}/models/{mv}/training.json": _training(
            mv, {"hgb.joblib": store.sha256_bytes(hgb)}
        ),
        f"{R}/cohort_v1/cohort.json": P.dumps(P.doc("cohort", tickers=[])),
    }

    def read(s):
        return store.read_object(ev, s) if store.object_ok(ev, s) else None

    assert FA.problems(_artifact_manifest(good, ev), read) == []
    bad_ref = dict(good)
    bad_ref[f"{R}/models/{mv}/training.json"] = _training(mv, {"hgb.joblib": "0" * 64})
    assert "참조" in " ".join(FA.problems(_artifact_manifest(bad_ref, ev), read))
    no_train = {k: v for k, v in good.items() if not k.endswith("training.json")}
    assert FA.problems(_artifact_manifest(no_train, ev), read)
    bad_schema = dict(good)
    bad_schema[f"{R}/cohort_v1/cohort.json"] = json.dumps(
        {"schema": "x", "protocol_id": FA.PROTOCOL_ID}
    ).encode()
    assert FA.problems(_artifact_manifest(bad_schema, ev), read)
    wrong_path_value = {
        f"{R}/targets/2026-10-22/0015K0.json": P.dumps(
            P.doc("target", ticker="364960", D=D)
        )
    }
    assert FA.problems(_artifact_manifest(wrong_path_value, ev), read)
    assert FA.problems(_artifact_manifest(good, ev, kind_override="cohort"), read)
    rid = "20261023T010000Z_0123abcd"
    pred = P.dumps(P.doc("prediction", id=rid, D=D))

    def receipt(sha, rid_=rid):
        return P.dumps(P.doc("prediction_receipt", id=rid_, D=D, prediction_sha256=sha))

    base = f"{R}/predictions/{D}/{rid}"
    ok_rec = {
        f"{base}.json": pred,
        f"{base}.receipt.json": receipt(store.sha256_bytes(pred)),
    }
    assert FA.problems(_artifact_manifest(ok_rec, ev), read) == []
    lost = {f"{base}.receipt.json": receipt("1" * 64)}  # 가리키는 예측 파일 없음
    assert "영수증" in " ".join(FA.problems(_artifact_manifest(lost, ev), read))
    broken = {f"{base}.receipt.json": b"{not json"}
    assert "해석 불가" in " ".join(FA.problems(_artifact_manifest(broken, ev), read))
    run_like = P.dumps(P.doc("run", id=rid, D=D))  # 같은 id · D 인 다른 종류 파일
    store.put_bytes(ev, run_like)
    not_pred = {f"{base}.receipt.json": receipt(store.sha256_bytes(run_like))}
    assert "예측 기록이 아님" in " ".join(
        FA.problems(_artifact_manifest(not_pred, ev), read)
    )
    other = P.dumps(P.doc("prediction", id="20261023T020000Z_0123abcd", D=D))
    store.put_bytes(ev, other)
    wrong = {f"{base}.receipt.json": receipt(store.sha256_bytes(other))}
    assert "예측 기록이 아님" in " ".join(
        FA.problems(_artifact_manifest(wrong, ev), read)
    )


def test_accept_upload_publishes_forward_artifacts_only_when_checks_pass(tmp_path):
    from tests.test_poc6_05_evidence_store import FakeRemote

    pc, oci = tmp_path / "pc", tmp_path / "oci"
    files = {
        f"{R}/cohort_v1/cohort.json": P.dumps(P.doc("cohort", tickers=list(TICKERS)))
    }
    m = _artifact_manifest(files, pc)
    store.publish_run(pc, m, clock=lambda: z(2026, 10, 23, 2))
    rep = transfer.upload_research(
        root=pc, remote=FakeRemote(oci), run_id=m["run_id"], now=z(2026, 10, 23, 3)
    )
    assert rep["status"] == "OK" and [r.run_id for r in store.list_runs(oci)[0]] == [
        m["run_id"]
    ]
    # 같은 kind 라도 허용 밖 경로가 섞이면 OCI 가 공개하지 않는다
    pc2, oci2 = tmp_path / "pc2", tmp_path / "oci2"
    m2 = _artifact_manifest(files, pc2)
    m2["files"].append(
        dict(m2["files"][0], rel_path="state/ml/research/poc6_02/x.json")
    )
    store.publish_run(pc2, m2, clock=lambda: z(2026, 10, 23, 2))
    rep2 = transfer.upload_research(
        root=pc2, remote=FakeRemote(oci2), run_id=m2["run_id"], now=z(2026, 10, 23, 3)
    )
    assert rep2["status"] == "CHECK_REQUIRED" and store.list_runs(oci2)[0] == []


def test_research_registration_contract_is_unchanged():
    m = {"kind": FA.KIND, "experiments": [], "files": []}
    assert transfer._research_problems(m) == ["연구 등록 묶음 아님"]
    assert transfer.UPLOAD_KINDS == ("RESEARCH_REGISTRATION", FA.KIND)


# ── 비교 보고(설계 §9) ───────────────────────────────────────────────────────


def _pred_doc(
    root,
    rid,
    D_,
    published,
    cutoff,
    entries,
    record_type="FORWARD_RESEARCH",
    mv="mv_a",
    confirm=timedelta(seconds=1),
):
    """예측 기록 + (confirm 이 None 이 아니면) 놓인 뒤 공개 확인 영수증(published + confirm)."""
    doc = P.doc(
        "prediction",
        id=rid,
        D=D_,
        record_type=record_type,
        times={
            "published_at": store.iso(published),
            "close_cutoff_at": store.iso(cutoff),
        },
        model={"model_version": mv},
        entries=entries,
    )
    path = root / "predictions" / D_ / f"{rid}.json"
    P.write_once(path, P.dumps(doc))
    if confirm is not None:
        records.write_receipt(root, path, published + confirm, "TEST")
    return path


def _entry(t, preds, role="PRIMARY", obj_="o1", **kw):
    methods = {
        m: ({"status": "OK", "pred": v} if v is not None else {"status": "FAILED"})
        for m, v in preds.items()
    }
    return {
        "ticker": t,
        "role": role,
        "input": {"source": {"object": obj_}, "features": [0] * 5, "base_close": 1.0},
        "methods": methods,
        **kw,
    }


def _target(root, t, D_, value):
    P.write_once(
        records.target_path(root, t, D_),
        P.dumps(
            P.doc(
                "target", ticker=t, D=D_, target=value, target_end="x", computed_at="x"
            )
        ),
    )


def test_report_same_rows_date_balanced_and_null(tmp_path):
    root = tmp_path / "r"
    coh = {"tickers": list(TICKERS)}
    assert (
        report.build(root, coh)["main"]["ALL_FOUR"]["mae_pp"]["HGB"] is None
    )  # 행 없음 = null
    c1, c2 = z(2026, 10, 23, 6, 30), z(2026, 10, 26, 6, 30)
    four = {"MEDIAN": -0.02, "RIDGE": -0.03, "HGB": -0.05, "MLP_CPU": None}
    _pred_doc(
        root,
        "20261023T010000Z_00000001",
        "2026-10-22",
        z(2026, 10, 23, 1),
        c1,
        [_entry("364960", four), _entry("458030", dict(four, MLP_CPU=-0.01))],
    )
    _pred_doc(
        root,
        "20261026T010000Z_00000002",
        "2026-10-23",
        z(2026, 10, 26, 1),
        c2,
        [
            _entry("364960", dict(four, MLP_CPU=-0.04)),
            _entry("271050", dict(four, MLP_CPU=-0.04)),
            _entry("282000", dict(four, MLP_CPU=-0.04)),
        ],
    )
    # 진단 · 마감 뒤 공개 · 부가 기록은 세지 않는다
    _pred_doc(
        root,
        "20261023T080000Z_00000003",
        "2026-10-22",
        z(2026, 10, 23, 8),
        c1,
        [_entry("122090", four)],
        record_type="DIAGNOSTIC",
    )
    _pred_doc(
        root,
        "20261023T063000Z_00000004",
        "2026-10-22",
        c1,
        c1,
        [_entry("122090", four)],
    )
    for t, D_, v in [
        ("364960", "2026-10-22", -0.10),
        ("458030", "2026-10-22", 0.0),
        ("364960", "2026-10-23", -0.04),
        ("271050", "2026-10-23", -0.02),
        ("282000", "2026-10-23", -0.06),
        ("122090", "2026-10-22", -0.5),
    ]:
        _target(root, t, D_, v)
    rep = report.build(root, coh)
    h = rep["main"]["HGB_vs_MEDIAN_RIDGE"]
    assert h["rows"] == 5 and h["dates"] == 2
    # 10-22: |−5+10|=5 · |−5−0|=5 → 5 · 10-23: 1 · 3 · 1 → 5/3 · 날짜 평균
    assert h["mae_pp"]["HGB"] == pytest.approx((5 + 5 / 3) / 2)
    m = rep["main"]["MLP_CPU_vs_MEDIAN_RIDGE"]
    assert (
        m["rows"] == 4 and m["excluded_rows"] == 1
    )  # 364960@10-22 MLP 실패 = 그 비교에서만 빠짐
    assert rep["main"]["ALL_FOUR"]["rows"] == 4
    assert h["deep_loss_le_8pct"]["rows"] == 1
    assert h["deep_loss_le_8pct"]["under_estimate_pp"]["HGB"] == pytest.approx(5.0)
    assert (
        rep["counts"]["diagnostic_entries"] == 1
        and rep["counts"]["primary_records"] == 5
    )
    assert rep["aux_groups"]["inverse_2"]["HGB_vs_MEDIAN_RIDGE"]["rows"] == 2
    assert rep["aux_groups"]["bond_cash_mixed_5"]["missing_tickers"] == [
        "114100",
        "130730",
        "447620",
        "488720",
    ]
    # 최초 실제 예측일 = 첫 주 기록 공개일(KST 10-23) — 가격 기준일 D(10-22)가 아니다(검증자 r1 F3)
    assert rep["first_forward_D"] == "2026-10-22"
    assert rep["first_forward_published_kst"] == "2026-10-23"
    assert rep["first_interpretation_date"] == "2027-01-23"
    assert rep["counts"]["unconfirmed_forward_records"] == 1  # 마감 시각에 확인된 기록


def test_retry_links_only_same_input_and_model_before_cutoff(tmp_path):
    root = tmp_path / "r"
    c1 = z(2026, 10, 23, 6, 30)
    first = {"MEDIAN": -0.02, "RIDGE": -0.03, "HGB": None, "MLP_CPU": -0.01}
    p1 = "20261023T010000Z_00000001"
    _pred_doc(
        root,
        p1,
        D,
        z(2026, 10, 23, 1),
        c1,
        [_entry(t, first) for t in ("364960", "381180")],
    )

    def retry(rid, at, t, preds, **kw):
        e = _entry(t, preds, role="RETRY", retry_of=p1, obj_=kw.pop("obj_", "o1"))
        _pred_doc(root, rid, D, at, c1, [e], **kw)

    # 364960: 다른 모델 판 · 다른 입력 · 마감 뒤 재시도는 연결하지 않음
    retry(
        "20261023T013000Z_00000002",
        z(2026, 10, 23, 1, 30),
        "364960",
        {"HGB": -0.6},
        mv="mv_b",
    )
    retry(
        "20261023T014000Z_00000003",
        z(2026, 10, 23, 1, 40),
        "364960",
        {"HGB": -0.7},
        obj_="o2",
    )
    retry("20261023T070000Z_00000004", z(2026, 10, 23, 7), "364960", {"HGB": -0.8})
    # 381180: 같은 입력 · 같은 판 · 마감 전 = 실패 방법만 연결(정상 방법은 바꾸지 않음)
    retry(
        "20261023T020000Z_00000005",
        z(2026, 10, 23, 2),
        "381180",
        {"HGB": -0.04, "MLP_CPU": -0.9},
    )
    prims = records.primaries(root)
    assert prims[("364960", D)]["methods"]["HGB"]["status"] == "FAILED"
    b = prims[("381180", D)]
    assert (
        b["methods"]["HGB"]["pred"] == -0.04
        and b["methods"]["MLP_CPU"]["pred"] == -0.01
    )
    assert b["retries"] == [{"run_id": "20261023T020000Z_00000005", "method": "HGB"}]
    assert (
        b["methods"]["HGB"]["retried_at"] == "2026-10-23T02:00:01.000000Z"
    )  # 재시도 기록의 공개 확인


def test_forward_counts_only_with_matching_receipt_before_cutoff(tmp_path):
    root = tmp_path / "r"
    c1 = z(2026, 10, 23, 6, 30)
    four = {"MEDIAN": -0.02, "RIDGE": -0.03, "HGB": -0.05, "MLP_CPU": -0.04}
    _pred_doc(
        root,
        "20261023T010000Z_00000001",
        D,
        z(2026, 10, 23, 1),
        c1,
        [_entry("364960", four)],
        confirm=None,
    )  # 영수증 없음
    late = _pred_doc(
        root,
        "20261023T020000Z_00000002",
        D,
        z(2026, 10, 23, 2),
        c1,
        [_entry("381180", four)],
        confirm=timedelta(hours=5),
    )  # 확인 = 07:00
    ok = _pred_doc(
        root,
        "20261023T030000Z_00000003",
        D,
        z(2026, 10, 23, 3),
        c1,
        [_entry("445690", four)],
    )
    assert set(records.primaries(root)) == {("445690", D)}
    assert {d["id"] for d in records.unconfirmed(records.prediction_docs(root))} == {
        "20261023T010000Z_00000001",
        "20261023T020000Z_00000002",
    }
    assert late.exists()
    ok.write_bytes(ok.read_bytes().replace(b"-0.05", b"-0.09"))  # 영수증 뒤에 바뀐 파일
    assert records.primaries(root) == {}


@pytest.mark.parametrize(
    "case",
    ["at_cutoff", "before_published", "not_json", "not_object", "time_text"],
)
def test_bad_or_boundary_receipts_are_not_forward_and_do_not_crash(tmp_path, case):
    root = tmp_path / "r"
    c1 = z(2026, 10, 23, 6, 30)
    four = {"MEDIAN": -0.02, "RIDGE": -0.03, "HGB": -0.05, "MLP_CPU": -0.04}
    pub = c1 - timedelta(seconds=1) if case == "at_cutoff" else z(2026, 10, 23, 1)
    conf = {
        "at_cutoff": timedelta(seconds=1),
        "before_published": -timedelta(seconds=1),
    }
    path = _pred_doc(
        root,
        "20261023T010000Z_00000001",
        D,
        pub,
        c1,
        [_entry("364960", four)],
        confirm=conf.get(case),
    )
    rp = records.receipt_path(path)
    if case == "not_json":
        rp.write_text("{broken")
    elif case == "not_object":
        rp.write_text("[1, 2]")
    elif case == "time_text":
        r = P.read_json(rp) if rp.exists() else None
        rp.write_text(json.dumps(dict(r or {}, confirmed_at="2026-10-23 01:00:01")))
    docs = records.prediction_docs(root)  # 깨진 영수증이 있어도 읽기는 멈추지 않는다
    assert records.primaries(root, docs) == {} and len(records.unconfirmed(docs)) == 1


def test_first_interpretation_date_uses_kst_publication_day(tmp_path):
    root = tmp_path / "r"
    four = {"MEDIAN": -0.02, "RIDGE": -0.03, "HGB": -0.05, "MLP_CPU": -0.04}
    # 2026-10-22T16:00Z = 10-23 01:00 KST(UTC 날짜로는 10-22)
    _pred_doc(
        root,
        "20261022T160000Z_00000001",
        "2026-10-22",
        z(2026, 10, 22, 16),
        z(2026, 10, 23, 6, 30),
        [_entry("364960", four)],
    )
    rep = report.build(root, {"tickers": list(TICKERS)})
    assert rep["first_forward_published_kst"] == "2026-10-23"
    assert rep["first_interpretation_date"] == "2027-01-23"


def test_first_publication_day_is_the_confirmed_day_across_midnight(tmp_path):
    root = tmp_path / "r"
    four = {"MEDIAN": -0.02, "RIDGE": -0.03, "HGB": -0.05, "MLP_CPU": -0.04}
    # 쓰기 시작 = 토 23:59:59 KST · 놓인 뒤 확인 = 일 00:00:01 KST(검증자 r2 F3 재현과 같은 경계)
    _pred_doc(
        root,
        "20261024T145959Z_00000001",
        "2026-10-23",
        z(2026, 10, 24, 14, 59, 59),
        z(2026, 10, 26, 6, 30),
        [_entry("364960", four)],
        confirm=timedelta(seconds=2),
    )
    rep = report.build(root, {"tickers": list(TICKERS)})
    assert rep["first_forward_published_kst"] == "2026-10-25"
    assert rep["first_interpretation_date"] == "2027-01-25"


def test_logged_examples_need_target_before_D_and_availability(tmp_path):
    from app.forward_compare import training

    root = tmp_path / "r"
    e = _entry("364960", {"MEDIAN": -0.02})
    e2 = _entry("381180", {"MEDIAN": -0.02})
    _pred_doc(
        root,
        "20261023T010000Z_00000001",
        D,
        z(2026, 10, 23, 1),
        z(2026, 10, 23, 6, 30),
        [e, e2],
    )
    for t, at in (
        ("364960", "2026-11-25T00:00:00.000000Z"),
        ("381180", "2026-11-20T01:00:00.000000Z"),
    ):
        body = P.doc(
            "target",
            ticker=t,
            D=D,
            target=-0.03,
            target_end="2026-11-19",
            computed_at=at,
        )
        P.write_once(records.target_path(root, t, D), P.dumps(body))
    rows, skipped = training.logged_examples(
        root, "2026-11-23", z(2026, 11, 24), ["364960", "381180"]
    )
    assert [r["ticker"] for r in rows] == ["381180"] and skipped[
        "available_after_start"
    ] == 1
    assert (
        rows[0]["available_at"] == "2026-11-20T01:00:00.000000Z"
        and rows[0]["origin"] == "LOGGED_FORWARD"
    )
    rows, skipped = training.logged_examples(
        root, "2026-11-19", z(2026, 11, 24), ["364960", "381180"]
    )
    assert rows == [] and skipped["target_end_not_before_D"] == 2
    rows, skipped = training.logged_examples(
        root, "2026-11-23", z(2026, 11, 24), ["364960"]
    )
    assert skipped["not_trainable"] == 1
