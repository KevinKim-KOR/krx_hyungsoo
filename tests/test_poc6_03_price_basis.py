"""POC6-03 — 가격 이력 기준 일관성 검증(격리 시험 · 실제 조회 0 · 라이브 DB 0).

조회기는 가짜(pandas DataFrame) · KRX 봉인 판은 합성 `SealedPanel` · 출력은 tmp 폴더.
"""

from __future__ import annotations

import json
import random
import sqlite3
from datetime import date, timedelta

import pandas as pd
import pytest
import requests

from app import krx_sealed_reader as krx
from app import market_data_fdr
from app.d20_pooled import study as S
from app.d20_pooled.snapshot import snapshot_problem
from app.price_basis_check import compare as C
from app.price_basis_check import fetch as F
from app.price_basis_check import report as R
from app.reentry_review import prices
from app.reentry_review.prices import FDR, NAVER

N = 560


def _weekdays(start: str, n: int) -> list[str]:
    d, out = date.fromisoformat(start), []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


DATES = _weekdays("2023-01-02", N)
T = DATES[-1]


def _walk(seed: int, n: int = N) -> list[float]:
    rnd, c, out = random.Random(seed), 10000.0, []
    for _ in range(n):
        c *= 1.0 + rnd.gauss(0.0002, 0.012)
        out.append(float(round(c)))
    return out


def _live_rows(closes, dates=DATES, source=FDR, fetched="2026-10-05T00:00:00Z"):
    out, prev = [], None
    for d, c in zip(dates, closes):
        out.append([d, c, source, fetched, None if prev is None else c / prev - 1.0])
        prev = c
    return out


def _snap(etfs: dict, dates=DATES) -> dict:
    t = dates[-1]
    firsts = [rows[0][0] for rows in etfs.values() if rows and rows[0][0] <= t]
    first = min(firsts) if firsts else t
    return {
        "schema": "poc6_02_snapshot_v1",
        "T": t,
        "holdings": {
            "status": "OK",
            "rows": len(etfs) + 1,
            "tickers": len(etfs) + 1,
            "etf": len(etfs),
            "non_etf": 1,
        },
        "axis": {
            "label": prices.AXIS_LABEL,
            "dates": [d for d in dates if d >= first],
            "modes": {
                str(y): prices.MODE_KOSPI for y in range(int(first[:4]), int(t[:4]) + 1)
            },
            "skipped_weekdays": [],
            "kospi_latest": t,
            "calendar_years": [],
            "problem": None,
        },
        "price_basis_label": prices.PRICE_BASIS_LABEL,
        "etfs": {k: {"name": f"ETF {k}", "rows": v} for k, v in etfs.items()},
    }


# ── 합성 KRX 봉인 판 ─────────────────────────────────────────────────────────


def _series(code: str, dates: list[str], closes: list, deltas: list) -> krx.CodeSeries:
    """무조정 종가 C · 부호 있는 전일 대비 Δ → load_panel 과 같은 CodeSeries(관계 검증 포함)."""
    s = krx.CodeSeries(code=code)
    for d, c, dl in zip(dates, closes, deltas):
        status = (
            krx.NO_VALID_CLOSE
            if c is None
            else (krx.NON_POSITIVE_CLOSE if c <= 0 else krx.CLOSE_OK)
        )
        fluc = None
        if c is not None and dl is not None and c - dl > 0:
            fluc = round(dl / (c - dl) * 100.0, 2)
        ret, ok = krx.check_relation(c if status == krx.CLOSE_OK else None, dl, fluc)
        s.dates.append(d)
        s.close.append(c)
        s.close_status.append(status)
        s.daily_return.append(ret)
        s.relation_ok.append(ok)
        s.volume.append(1.0)
        s.nav.append(None)
        s.name.append(code)
    krx._finish_series(s)
    return s


def _panel(series: dict, dates: list[str]) -> krx.SealedPanel:
    return krx.SealedPanel(
        version_id="test",
        dates=dates,
        series=series,
        relation_mismatch_rows=0,
        invalid_close_rows=0,
    )


def _krx_unadjusted(closes: list[float], events: dict[int, float]):
    """무조정 종가 · Δ — events[i] = 그날 기준가 = C[i-1] × factor(분배 등 · 사유 모름)."""
    deltas = [0.0]
    for i in range(1, len(closes)):
        base = closes[i - 1] * events[i] if i in events else closes[i - 1]
        base = float(round(base))
        deltas.append(closes[i] - base)
    return deltas


def _adjusted(closes: list[float], events: dict[int, float]) -> list[float]:
    """받은 날 기준 수정 종가 = 무조정 종가 × (그 날 뒤 사건 배율의 곱) · 원 반올림."""
    out = []
    for i, c in enumerate(closes):
        f = 1.0
        for j, k in events.items():
            if j > i:
                f *= k
        out.append(float(round(c * f)))
    return out


# ── 조회 · 사본 ──────────────────────────────────────────────────────────────


def _df(rows: list[list]) -> pd.DataFrame:
    idx = pd.to_datetime([r[0] for r in rows])
    close = pd.Series([r[1] for r in rows], index=idx, dtype=float)
    return pd.DataFrame({"Close": close, "Change": close.pct_change()})


@pytest.fixture
def no_live_writes(monkeypatch):
    def _boom(*a, **k):
        raise AssertionError("라이브 DB 쓰기 시도")

    monkeypatch.setattr(market_data_fdr, "upsert_daily_prices", _boom)
    monkeypatch.setattr(market_data_fdr, "log_refresh", _boom)


def test_fetch_batch_once_per_ticker_snapshot_range_no_retry(no_live_writes):
    starts = {"A1": 0, "B2": 7, "C3": 30, "D4": 3, "F6": 11}  # 종목마다 다른 첫 저장일
    rows = {
        t: _live_rows(_walk(i + 3, N - k), DATES[k:])
        for i, (t, k) in enumerate(starts.items())
    }
    rows["E5"] = []  # 저장 이력 없음 → 조회하지 않음
    snap = _snap(rows)
    calls = []

    class Weird:  # 변환 함수가 다룰 수 없는 응답
        columns = ["Close"]

        def __len__(self):
            return 1

        def iterrows(self):
            raise TypeError("이상한 응답")

    def fake(t, start, end):
        calls.append((t, start.isoformat(), end.isoformat()))
        if t == "B2":
            raise requests.exceptions.ReadTimeout("느림")
        if t == "C3":
            return pd.DataFrame()
        if t == "F6":
            return Weird()
        return _df(rows[t])

    batch = F.fetch_batch(snap, fetcher=fake)
    assert calls == [
        (t, DATES[starts[t]], T) for t in ("A1", "B2", "C3", "D4", "F6")
    ]  # 한 번씩 · 재시도 0 · 시작일 = 그 종목 첫 저장일
    st = {e["ticker"]: e for e in batch["log"]}
    assert st["A1"]["status"] == F.OK and st["A1"]["rows"] == N
    assert st["B2"]["status"] == F.FAILED and st["B2"]["timeout"] is True
    assert st["C3"]["status"] == F.NO_DATA and st["E5"]["status"] == F.NO_STORED
    assert st["F6"]["status"] == F.FAILED and st["F6"]["error"].startswith("convert:")
    assert (
        st["D4"]["status"] == F.OK
    )  # 변환 오류 종목 뒤로도 묶음이 계속(이미 받은 자료 보존)
    assert st["A1"]["returned_first"] == DATES[0] and st["A1"]["returned_last"] == T
    assert set(batch["rows"]) == {"A1", "D4"}
    assert batch["libraries"]["finance-datareader"]


def test_preflight_refuses_other_snapshot_too_many_and_repeat(tmp_path, monkeypatch):
    from app.d20_pooled.snapshot import digest

    rows = {"A1": _live_rows(_walk(3))}
    snap = _snap(rows)
    monkeypatch.setattr(F, "RESEARCH_ROOT", tmp_path / "poc6_03")
    good = digest(snap)
    F.preflight(snap, good)  # 통과
    with pytest.raises(F.FetchRefused, match="digest"):
        F.preflight(snap, "0" * 64)
    many = _snap({f"Z{k:02d}": _live_rows(_walk(k)) for k in range(27)})
    with pytest.raises(F.FetchRefused, match="27종"):
        F.preflight(many, digest(many))
    batch = F.fetch_batch(snap, fetcher=lambda t, s, e: _df(rows[t]))
    F.write_copy(snap, tmp_path / "snap.json", batch)
    with pytest.raises(F.FetchRefused, match="이미"):
        F.preflight(snap, good)  # 같은 snapshot 사본이 있으면 다시 조회하지 않음


def test_research_root_is_absolute_under_repo_state():
    import importlib

    fresh = importlib.reload(F)
    assert fresh.RESEARCH_ROOT.is_absolute()
    assert fresh.RESEARCH_ROOT.parts[-4:] == ("state", "ml", "research", "poc6_03")


def test_write_copy_is_atomic_and_failure_leaves_nothing(tmp_path, monkeypatch):
    rows = {"A1": _live_rows(_walk(3))}
    snap = _snap(rows)
    batch = F.fetch_batch(snap, fetcher=lambda t, s, e: _df(rows[t]))
    monkeypatch.setattr(F, "RESEARCH_ROOT", tmp_path / "poc6_03")
    folder = F.write_copy(snap, tmp_path / "snap.json", batch)
    assert sorted(p.name for p in folder.iterdir()) == ["copy.sqlite", "fetch.json"]
    copy = C.load_copy(folder)
    assert copy["meta"]["schema"] == F.SCHEMA and copy["meta"]["T"] == T
    assert [r.date for r in copy["rows"]["A1"]] == DATES
    assert all(r.source == FDR for r in copy["rows"]["A1"])
    blocker = tmp_path / "file"
    blocker.write_text("x")
    monkeypatch.setattr(F, "RESEARCH_ROOT", blocker / "poc6_03")
    with pytest.raises(F.CopySaveError):
        F.write_copy(snap, tmp_path / "snap.json", batch)
    # 임시 폴더를 만든 뒤(이름 바꾸기 단계) 실패해도 반쪽 폴더가 남지 않는다
    monkeypatch.setattr(F, "RESEARCH_ROOT", tmp_path / "late")

    def _rename_fails(a, b):
        raise OSError("rename")

    monkeypatch.setattr(F.os, "rename", _rename_fails)
    with pytest.raises(F.CopySaveError):
        F.write_copy(snap, tmp_path / "snap.json", batch)
    assert (tmp_path / "late").is_dir() and not list((tmp_path / "late").iterdir())


# ── 06 경계 · change ─────────────────────────────────────────────────────────


def test_breaks_use_06_link_break_and_change_ratio_count():
    closes = _walk(5, 60)
    live = [prices.PriceRow(*r) for r in _live_rows(closes, DATES[:60])]
    # 수집 묶음이 바뀐 자리: 뒤 묶음은 새 기준(0.99)인데 change 는 그 묶음 종가 기준
    mixed = live[:30] + [
        prices.PriceRow(
            r.date, round(r.close * 0.99), FDR, "2026-08-17T00:00:00Z", r.change
        )
        for r in live[30:]
    ]
    mixed[45] = prices.PriceRow(mixed[45].date, mixed[45].close, NAVER, None, None)
    got = C.breaks(mixed)
    assert [(b["date"], b["kind"]) for b in got][:1] == [
        (DATES[30], prices.BASIS_BREAK)
    ]
    assert any(b["kind"] == prices.SOURCE_RESWITCH for b in got)
    assert C.breaks(live) == []
    ratio = C.change_vs_close_ratio(live)
    assert ratio["checked"] == 59 and ratio["equal"] == 59


# ── KRX 대조 ────────────────────────────────────────────────────────────────


def _case(n=40, events=None, seed=11):
    dates = DATES[:n]
    closes = _walk(seed, n)
    events = events or {}
    deltas = _krx_unadjusted(closes, events)
    s = _series("X", dates, closes, deltas)
    copy = [
        prices.PriceRow(d, a, FDR, "2026-10-21T00:00:00Z", None)
        for d, a in zip(dates, _adjusted(closes, events))
    ]
    return dates, closes, deltas, s, copy


def test_krx_normal_up_down_days_match():
    dates, closes, _, s, copy = _case()
    out = C.krx_compare(dates, copy, s, dates)
    assert out["unit_ok"] and out["mismatch"] == 0 and out["not_comparable"] == {}
    assert out["match"] == len(dates) - 1
    ups = sum(1 for a, b in zip(closes, closes[1:]) if b > a)
    downs = sum(1 for a, b in zip(closes, closes[1:]) if b < a)
    assert ups and downs  # 상승일 · 하락일 모두 · 부호 있는 Δ


def test_krx_adjustment_candidate_matches_adjusted_copy_not_unadjusted():
    dates, closes, deltas, s, copy = _case(events={20: 0.99})
    out = C.krx_compare(dates, copy, s, dates)
    assert out["mismatch"] == 0
    cands = out["candidates_on_pairs"]
    assert [c["date"] for c in cands] == [dates[20]] and cands[0]["match"] is True
    assert cands[0]["reason"] == "조정 사유 미확인"
    assert cands[0]["factor"] == pytest.approx(round(closes[19] * 0.99) / closes[19])
    raw = [prices.PriceRow(d, c, FDR, "x", None) for d, c in zip(dates, closes)]
    out2 = C.krx_compare(dates, raw, s, dates)  # 조정 안 된 사본 = 그날 불일치
    assert [m["date"] for m in out2["mismatches"]] == [dates[20]]
    assert out2["mismatches"][0]["candidate"] is True


def test_krx_gaps_are_not_skipped_and_valid_zero_is_kept():
    dates = DATES[:40]
    closes = _walk(11, 40)
    closes[20] = closes[19]  # 보합(유효한 0)
    deltas = _krx_unadjusted(closes, {})
    assert deltas[20] == 0.0
    k_closes, k_deltas = list(closes), list(deltas)
    k_closes[10] = None  # KRX 종가 없음 → (9,10) · (10,11) 대조 불가
    k_deltas[15] = None  # Δ 없음 → (14,15) 관계 불성립
    s = _series("X", dates, k_closes, k_deltas)
    copy = [prices.PriceRow(d, c, FDR, "x", None) for d, c in zip(dates, closes)]
    out = C.krx_compare(dates, copy, s, dates)
    assert out["not_comparable"] == {C.KRX_CLOSE_INVALID: 2, C.KRX_RELATION_FAIL: 1}
    assert out["mismatch"] == 0 and out["match"] == len(dates) - 1 - 3


def test_krx_copy_missing_bad_close_and_zero_close():
    dates, _, _, s, copy = _case()
    copy2 = [r for r in copy if r.date != dates[5]]
    copy2[12] = prices.PriceRow(copy2[12].date, 0.0, FDR, "x", None)
    out = C.krx_compare(dates, copy2, s, dates)
    assert out["not_comparable"][C.COPY_ROW_MISSING] == 2
    assert out["not_comparable"][C.COPY_CLOSE_INVALID] == 2


@pytest.mark.parametrize(
    "bump,ok", [(0.0, True), (2.0, True), (2.02, False), (-2.0, True), (-2.02, False)]
)
def test_interval_boundary_inside_and_outside(bump, ok):
    """하루 값만 bump 원 올린다 — (A_t−1)/(A_prev+1) 하한이 1.01 을 넘는 2.01원 근처가 경계."""
    dates = DATES[:2]
    closes = [10000.0, 10100.0]
    s = _series("X", dates, closes, _krx_unadjusted(closes, {}))
    copy = [
        prices.PriceRow(dates[0], 10000.0, FDR, "x", None),
        prices.PriceRow(dates[1], 10100.0 + bump, FDR, "x", None),
    ]
    out = C.krx_compare(dates, copy, s, dates)
    assert (out["match"], out["mismatch"]) == ((1, 0) if ok else (0, 1))


def test_interval_undefined_out_of_range_unit_and_not_consecutive():
    dates = DATES[:6]
    closes = [10000.0, 10100.0, 10050.0, 10200.0, 10150.0, 10300.0]
    s = _series("X", dates, closes, _krx_unadjusted(closes, {}))
    tiny = [prices.PriceRow(d, 1.0, FDR, "x", None) for d in dates]
    big = [prices.PriceRow(d, c * 10, FDR, "x", None) for d, c in zip(dates, closes)]
    assert C.krx_compare(dates, big, s, dates)["not_comparable"] == {
        C.UNIT_UNCONFIRMED: 5
    }
    s_tiny = _series("X", dates, [1.0] * 6, [0.0] * 6)
    assert C.krx_compare(dates, tiny, s_tiny, dates)["not_comparable"] == {
        C.INTERVAL_UNDEFINED: 5
    }
    copy = [prices.PriceRow(d, c, FDR, "x", None) for d, c in zip(dates, closes)]
    out = C.krx_compare(dates, copy, s, dates[:4])  # KRX 판이 3번째 날짜에서 끝남
    assert out["not_comparable"] == {C.KRX_OUT_OF_RANGE: 2} and out["match"] == 3
    gap_axis = [
        dates[0],
        dates[2],
        dates[3],
        dates[4],
        dates[5],
    ]  # 축이 KRX 하루를 건너뜀
    out = C.krx_compare(gap_axis, copy, s, dates)
    assert out["not_comparable"] == {C.KRX_NOT_CONSECUTIVE: 1}
    none = C.krx_compare(dates, copy, None, dates)
    assert none["not_comparable"] == {C.KRX_NO_SERIES: 5} and none["match"] == 0


def test_krx_row_missing_and_nan_close_are_not_comparable():
    dates = DATES[:6]
    closes = [10000.0, 10100.0, 10050.0, 10200.0, 10150.0, 10300.0]
    deltas = _krx_unadjusted(closes, {})
    keep = [0, 1, 3, 4, 5]  # 2번째 날 그 종목 KRX 행 없음(봉인 판 날짜는 있음)
    s = _series(
        "X",
        [dates[i] for i in keep],
        [closes[i] for i in keep],
        [deltas[i] for i in keep],
    )
    copy = [prices.PriceRow(d, c, FDR, "x", None) for d, c in zip(dates, closes)]
    out = C.krx_compare(dates, copy, s, dates)
    assert out["not_comparable"] == {C.KRX_ROW_MISSING: 2} and out["match"] == 3
    s2 = _series("X", dates, closes, deltas)
    s2.close[3] = float("nan")  # 재사용 모듈이 NaN 을 OK 로 둘 수 있음(검토 LOW-3)
    out2 = C.krx_compare(dates, copy, s2, dates)
    assert (
        out2["not_comparable"].get(C.KRX_CLOSE_INVALID) == 2 and out2["mismatch"] == 0
    )


def test_small_two_won_adjustment_is_a_candidate():
    dates = DATES[:2]
    closes = [10000.0, 10100.0]
    s = _series("X", dates, closes, [0.0, 10100.0 - 9998.0])  # 기준가 9998 = 전일 −2원
    copy = [
        prices.PriceRow(dates[0], 9998.0, FDR, "x", None),
        prices.PriceRow(dates[1], 10100.0, FDR, "x", None),
    ]
    out = C.krx_compare(dates, copy, s, dates)
    (c,) = out["candidates_on_pairs"]
    assert c["factor"] == pytest.approx(9998.0 / 10000.0) and c["match"] is True


def test_mismatch_breakdown_by_candidate_size_and_year():
    ms = [
        {"date": "2014-04-11", "copy_k": 1.00005, "krx_k": 1.0, "candidate": False},
        {"date": "2014-05-02", "copy_k": 1.0003, "krx_k": 1.0, "candidate": False},
        {"date": "2025-04-29", "copy_k": 0.99, "krx_k": 1.0, "candidate": True},
    ]
    b = C.mismatch_breakdown(ms)
    assert b["candidate_days"] == 1 and b["normal_days"] == 2
    assert b["by_size_bp"] == {"≤1bp": 1, "≤5bp": 1, ">100bp": 1}
    assert b["by_year"] == {"2014": 2, "2025": 1}


def test_cumulative_uses_product_of_factors():
    dates, closes, deltas, s, copy = _case(n=60, events={15: 0.99, 40: 0.98})
    out = C.krx_compare(dates, copy, s, dates)
    ac = out["a_over_c"]
    assert ac["krx_candidate_product"] == pytest.approx(
        closes[14] / round(closes[14] * 0.99) * closes[39] / round(closes[39] * 0.98)
    )
    assert ac["observed_change"] == pytest.approx(ac["krx_candidate_product"], rel=2e-4)
    assert ac["unevaluated_krx_pairs_between"] == 0


# ── 수집 묶음별 차이 ───────────────────────────────────────────────────────────


def test_batch_diff_explains_with_krx_product_or_marks_unconfirmed():
    dates, closes, deltas, s, copy = _case(n=60, events={40: 0.98})
    cand = C.krx_candidates(s, dates)
    # 묶음 1: 사건(40) 전에 받은 행 = 그때 기준(사건 미반영) · 묶음 2: 사건 뒤에 받은 행 = 사본과 같은 기준
    older = _adjusted(closes, {})
    live = [
        prices.PriceRow(d, older[i], FDR, f"{dates[30]}T00:00:00Z", None)
        for i, d in enumerate(dates[:30])
    ] + [
        prices.PriceRow(d, copy[i].close, FDR, f"{dates[55]}T00:00:00Z", None)
        for i, d in enumerate(dates[:60])
        if i >= 30
    ]
    out = {b["batch"]: b for b in C.batch_diff(live, copy, cand, dates[-1])}
    b1, b2 = out[dates[30]], out[dates[55]]
    assert b1["expected_from_krx"] == pytest.approx(1 / cand["factors"][dates[40]])
    assert b1["status"].startswith("KRX 범위 안 후보 곱과 일치")
    assert b2["expected_from_krx"] == 1.0 and b2["status"].startswith("KRX 범위 안")
    bad = [
        prices.PriceRow(r.date, r.close * 1.05, FDR, r.fetched_at, None) for r in live
    ]
    out2 = {b["batch"]: b for b in C.batch_diff(bad, copy, cand, dates[-1])}
    assert out2[dates[30]]["status"].startswith("조정 사유 미확인")


# ── 적격 다시 세기 ─────────────────────────────────────────────────────────────


def _rows_obj(rows):
    return [prices.PriceRow(*r) for r in rows]


def test_recount_uses_02_rules_and_trims_axis_when_earliest_fails():
    live = {t: _live_rows(_walk(s)) for s, t in enumerate(("A1", "B2", "C3", "D4"), 3)}
    late = DATES[100:]
    live["E5"] = _live_rows(_walk(9, len(late)), late)
    snap = _snap(live)
    assert snapshot_problem(snap) is None
    copy = {t: _rows_obj(r) for t, r in live.items()}
    rec = C.recount(snap, copy)
    assert rec["official"] == rec["copy"] and rec["not_recounted"] == []
    # 가장 이른 종목들이 조회 실패 → 축 앞부분을 06 규칙대로 자르고 다시 셈
    only = {"E5": copy["E5"]}
    snap2 = C.recount_snapshot(snap, only)
    assert snap2["axis"]["dates"][0] == late[0] and snapshot_problem(snap2) is None
    assert snap2["holdings"]["etf"] == 1 and snap2["holdings"]["tickers"] == 2
    rec2 = C.recount(snap, only)
    assert rec2["not_recounted"] == ["A1", "B2", "C3", "D4"]
    assert rec2["copy"]["eligible"] == []  # 1종 = 자료 부족 규칙 그대로
    assert S.MIN_ETFS == 4


# ── 대조 실행 · 보고 · CLI ─────────────────────────────────────────────────────


@pytest.fixture
def world(tmp_path, monkeypatch, no_live_writes):
    """공식 snapshot 파일 · 가짜 조회 사본 · 합성 KRX 봉인 판(검증 결과 고정)."""
    tickers = ("A1", "B2", "C3", "D4")
    # 사건(400)은 두 수집 묶음 사이: 앞 묶음(350 전 행 · DATES[352] 수집) = 사건 전 기준 ·
    # 뒤 묶음(350 부터 · T 수집) = 사건 뒤 기준 → 350 에서 06 BASIS_BREAK
    events = {t: {400: 0.99} for t in tickers}
    unadj = {t: _walk(s) for s, t in enumerate(tickers, 3)}
    live = {}
    for t in tickers:
        older = _adjusted(unadj[t], {})
        rows = _live_rows(older[:350], DATES[:350], fetched=f"{DATES[352]}T00:00:00Z")
        newer = _adjusted(unadj[t], events[t])
        prev = newer[349]
        for d, c in zip(DATES[350:], newer[350:]):
            rows.append([d, c, FDR, f"{T}T00:00:00Z", c / prev - 1.0])
            prev = c
        live[t] = rows
    snap = _snap(live)
    snap_path = tmp_path / "input_snapshot.json"
    snap_path.write_text(json.dumps(snap), encoding="utf-8")
    copies = {t: _adjusted(unadj[t], events[t]) for t in tickers}
    series = {  # 실제 load_panel 처럼 종목 행은 봉인 판 날짜(500일) 안에만
        t: _series(
            t, DATES[:500], unadj[t][:500], _krx_unadjusted(unadj[t], events[t])[:500]
        )
        for t in tickers[:3]  # D4 = KRX 행 없음
    }
    panel = _panel(series, DATES[:500])  # 봉인 판이 T 보다 일찍 끝남
    src = {"version_id": "test", "first_date": DATES[0], "last_date": DATES[499]}
    monkeypatch.setattr(krx, "verify_sealed_source", lambda *a, **k: dict(src))
    monkeypatch.setattr(krx, "load_panel", lambda *a, **k: panel)
    monkeypatch.setattr(F, "RESEARCH_ROOT", tmp_path / "poc6_03")
    calls = []

    def fake(t, start, end):
        calls.append(t)
        rows = [[d, c] for d, c in zip(DATES, copies[t])]
        return _df(rows)

    return {
        "snap": snap,
        "snap_path": snap_path,
        "fetch": fake,
        "calls": calls,
        "src": src,
    }


def test_run_compare_end_to_end_and_rerun_without_refetch(world):
    batch = F.fetch_batch(world["snap"], fetcher=world["fetch"])
    folder = F.write_copy(world["snap"], world["snap_path"], batch)
    out = R.run_compare(folder)
    body = json.loads((out / "report.json").read_text(encoding="utf-8"))
    sm = body["summary"]
    assert sm["fetch"] == {"OK": 4} and sm["tickers_with_krx"] == 3
    assert (
        sm["live_breaks"] == 4 and sm["copy_breaks"] == 0
    )  # 기존 경계 관측 · 사본은 구조상 0
    assert sm["copy_change_equal"] == sm["copy_change_checked"]
    a1 = body["per_ticker"]["A1"]
    assert a1["krx"]["mismatch"] == 0 and a1["krx"]["not_comparable"] == {
        C.KRX_OUT_OF_RANGE: N - 500
    }
    assert [c["date"] for c in a1["krx"]["candidates_on_pairs"]] == [DATES[400]]
    batches = {b["batch"]: b for b in a1["batches"]}
    assert batches[DATES[352]]["expected_from_krx"] == pytest.approx(
        1 / a1["krx"]["candidates_on_pairs"][0]["factor"]
    )
    assert batches[DATES[352]]["status"].startswith("KRX 범위 안 후보 곱과 일치")
    assert (
        batches[T]["expected_from_krx"] is None
    )  # KRX 끝 뒤 수집 = KRX 근거 없음(검토 MED-1)
    assert batches[T]["status"].startswith("KRX 범위 밖 수집")
    assert "KRX 로 검증 안 됨" in batches[T]["status"]
    assert a1["live_breaks"][0]["date"] == DATES[350]
    assert body["per_ticker"]["D4"]["krx"]["not_comparable"].get(C.KRX_NO_SERIES)
    rec = body["recount"]
    assert rec["official"]["eligible"] == [] and len(rec["copy"]["eligible"]) == 4
    md = (out / "report.md").read_text(encoding="utf-8")
    assert "사본 경계 0 은 근거가 아님" in md and "## 한계" in md
    again = R.run_compare(folder)  # 대조만 다시 · 조회 0
    assert again != out and len(world["calls"]) == 4


def test_sealed_source_change_or_snapshot_change_is_check_required(world, monkeypatch):
    batch = F.fetch_batch(world["snap"], fetcher=world["fetch"])
    folder = F.write_copy(world["snap"], world["snap_path"], batch)
    seq = iter([dict(world["src"]), {**world["src"], "last_date": "x"}])
    monkeypatch.setattr(krx, "verify_sealed_source", lambda *a, **k: next(seq))
    with pytest.raises(C.CompareError, match="봉인"):
        R.run_compare(folder)
    assert not [p for p in folder.iterdir() if p.name.startswith("compare_")]
    snap = json.loads(world["snap_path"].read_text(encoding="utf-8"))
    snap["holdings"]["rows"] += 1
    world["snap_path"].write_text(json.dumps(snap), encoding="utf-8")
    monkeypatch.setattr(krx, "verify_sealed_source", lambda *a, **k: dict(world["src"]))
    with pytest.raises(C.CompareError, match="digest"):
        R.run_compare(folder)


def test_report_write_failure_leaves_no_folder(world, monkeypatch):
    batch = F.fetch_batch(world["snap"], fetcher=world["fetch"])
    folder = F.write_copy(world["snap"], world["snap_path"], batch)

    def _fail(*a, **k):
        raise OSError("disk")

    monkeypatch.setattr(R, "render_md", _fail)
    with pytest.raises(R.ReportSaveError):
        R.run_compare(folder)
    assert not [
        p for p in folder.iterdir() if p.name.startswith(("compare_", ".compare_"))
    ]


def test_cli_compare_and_bad_inputs(world, tmp_path, capsys):
    from scripts.run_price_basis_check import main

    batch = F.fetch_batch(world["snap"], fetcher=world["fetch"])
    folder = F.write_copy(world["snap"], world["snap_path"], batch)
    assert main(["compare", "--copy-dir", str(folder)]) == 0
    printed = capsys.readouterr().out
    assert "사본 경계 0 은 근거가 아님" in printed and "KRX 대조와 함께 읽기" in printed
    assert main(["compare", "--copy-dir", str(tmp_path / "없음")]) == 2
    bad = tmp_path / "bad.json"
    bad.write_text("{broken", encoding="utf-8")
    assert (
        main(["fetch", "--snapshot", str(bad), "--expect-digest", "x"]) == 2
    )  # 손상 snapshot = 조회 전에 거절
    # 같은 snapshot 사본이 이미 있음 = 조회 0 으로 거절(반복 수집 금지)
    from app.d20_pooled.snapshot import digest

    dg = digest(world["snap"])
    assert (
        main(["fetch", "--snapshot", str(world["snap_path"]), "--expect-digest", dg])
        == 2
    )
    assert len(world["calls"]) == 4  # 위 한 묶음뿐 · 대조 · 손상 입력은 조회하지 않음


def test_copy_schema_mismatch_is_check_required(world):
    batch = F.fetch_batch(world["snap"], fetcher=world["fetch"])
    folder = F.write_copy(world["snap"], world["snap_path"], batch)
    con = sqlite3.connect(folder / "copy.sqlite")
    con.execute("UPDATE meta SET value = '\"x\"' WHERE key = 'schema'")
    con.commit()
    con.close()
    with pytest.raises(C.CompareError, match="schema"):
        C.load_copy(folder)


def test_partial_fetch_failure_flows_to_report(world):
    real = world["fetch"]

    def flaky(t, start, end):
        if t == "B2":
            raise requests.exceptions.ConnectionError("끊김")
        return real(t, start, end)

    batch = F.fetch_batch(world["snap"], fetcher=flaky)
    folder = F.write_copy(world["snap"], world["snap_path"], batch)
    body = json.loads(
        (R.run_compare(folder) / "report.json").read_text(encoding="utf-8")
    )
    assert body["summary"]["fetch"] == {"FAILED": 1, "OK": 3}
    b2 = body["per_ticker"]["B2"]
    assert b2["copy_rows_to_T"] == 0 and b2["krx"]["pairs"] == 0
    assert body["recount"]["not_recounted"] == ["B2"]  # 실패 종목을 통과로 세지 않음
