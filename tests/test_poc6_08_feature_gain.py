"""POC6-08 — 거래량 · 동일 기간 상대강도 ML 추가 효용 검증(설계 V1 · PLAN V1 §5 · §7 · 판정 2026-10-24).

작은 고정 자료(종목마다 다른 가격 · 거래량 경로 · tmp 폴더)만 쓴다. 라이브 DB · 실제 연구 폴더 · 06 산출물 읽기 0.
"""

from __future__ import annotations

import json
import math
import random
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from app.d20_pooled import study as S
from app.feature_gain import inputs as FI
from app.feature_gain import protocol as P
from app.feature_gain import report as R
from app.feature_gain import study as ST
from app.feature_gain import verify as VR
from app.ml_evidence import store as EV
from app.reentry_review import model as m06

N_DATES = 600
REPO = Path(__file__).resolve().parents[1]


def _weekdays(n: int, end: str = "2026-10-19") -> list[str]:
    out, d = [], date.fromisoformat(end)
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d -= timedelta(days=1)
    return list(reversed(out))


DATES = _weekdays(N_DATES)


def _rows(
    seed: int, start: int = 0, base: float = 100.0, vol0: int = 1000
) -> list[list]:
    rng = random.Random(seed)
    out, prev = [], None
    c = base
    for k, d in enumerate(DATES[start:]):
        c = round(c * (1 + rng.uniform(-0.03, 0.025)), 4)
        vol = vol0 + rng.randrange(0, 500) if k % 17 else 0  # 가끔 0
        ch = (c / prev - 1.0) if prev else 0.0
        out.append([d, c, c, c, c, vol, ch])
        prev = c
    return out


def _inputs(prices: dict[str, list], bench: list[list], review_out=()) -> FI.Inputs:
    return FI.Inputs(
        cohort=list(prices),
        review_out=tuple(review_out),
        prices={
            t: {"observed_at": "2026-10-23T01:19:20Z", "rows": r}
            for t, r in prices.items()
        },
        bench_rows=[
            (r[0], r[4], P.SOURCE, "2026-10-21T07:14:44Z", r[6]) for r in bench
        ],
        kospi_dates=list(DATES),
        calendar_dir=Path("."),
    )


def _ax() -> dict[str, Any]:
    return {
        "dates": list(DATES),
        "T": DATES[-1],
        "last24": DATES[-1],
        "limit": DATES[-1],
        "modes": None,
    }


def _world_prices() -> dict[str, list]:
    return {
        "0015K0": _rows(1, vol0=1000),
        "111111": _rows(2, base=50.0, vol0=50_000),
        "458030": _rows(3, base=10.0, vol0=7),  # 보조 범위 제외 대상(REVIEW_OUT)
        "333333": _rows(5, base=20.0, vol0=300),
        "444444": _rows(6, base=80.0, vol0=9_000),
        "555555": _rows(7, base=5.0, vol0=120),
        "666666": _rows(8, base=150.0, vol0=2_500),
        "222222": _rows(4, start=400),  # 이력 부족(부적격)
    }


def _world(prices=None, review_out=("458030",)) -> FI.Inputs:
    return _inputs(prices or _world_prices(), _rows(9, base=300.0), review_out)


@pytest.fixture
def world():
    return _world(), _ax()


# ── 산술 · 정의(설계 §3 · §9-1) ─────────────────────────────────────────────────


def test_v_excludes_base_day_includes_zero_and_avg_zero_is_missing(world) -> None:
    inp, ax = world
    series, bench = FI.build_series(inp, ax["dates"])
    ser = series["111111"]
    i = 300
    prev = [ser.volume[j] for j in range(i - 20, i)]
    v, why = FI.volume_ratio(ser, ax["dates"], i)
    assert why is None and v == ser.volume[i] / (math.fsum(prev) / 20)
    # 당일 0 · 직전 평균 양수 = 유효 0.
    ser.volume[i] = 0
    assert FI.volume_ratio(ser, ax["dates"], i) == (0.0, None)
    # 직전 20개가 모두 0 = 평균 0 → 결측(사유).
    for j in range(i - 20, i):
        ser.volume[j] = 0
    assert FI.volume_ratio(ser, ax["dates"], i) == (None, "avg_zero")
    # 축 날짜에 사본 행이 없음(None) → 결측(0 으로 바꾸지 않음 · 직전 20개 부족).
    ser.volume[i - 3] = None
    assert FI.volume_ratio(ser, ax["dates"], i) == (None, "avg_insufficient")
    ser.volume[i] = float("inf")
    assert FI.volume_ratio(ser, ax["dates"], i) == (None, "volume_missing")
    # 유한 값끼리 나눠도 넘치면(inf) 결측 · 사유(값으로 쓰지 않음).
    for j in range(i - 20, i):
        ser.volume[j] = 1e-300
    ser.volume[i] = 1e308
    assert FI.volume_ratio(ser, ax["dates"], i) == (None, "not_finite")


def test_r_same_dates_and_benchmark_problem_is_missing(world) -> None:
    inp, ax = world
    series, bench = FI.build_series(inp, ax["dates"])
    ser, i = series["0015K0"], 300
    c, b = ser.s.closes, bench.closes
    r, why = FI.relative_return(ser, bench, i)
    assert why is None and r == (c[i] / c[i - 20] - 1.0) - (b[i] / b[i - 20] - 1.0)
    assert r == pytest.approx(m06.features_at(c, i)[1] - (b[i] / b[i - 20] - 1.0))
    # 벤치마크 그 창의 날짜 하나가 빠지면(다른 기간 · 이웃 날짜로 대신 안 함) R 결측 · 기본 행은 그대로.
    rows = [r_ for r_ in inp.bench_rows if r_[0] != ax["dates"][i - 7]]
    inp2 = FI.Inputs(**{**inp.__dict__, "bench_rows": rows})
    s2, b2 = FI.build_series(inp2, ax["dates"])
    assert FI.relative_return(s2["0015K0"], b2, i) == (None, "bench_window")
    assert FI.base_ok(s2["0015K0"], i, len(ax["dates"]))
    # 종목 쪽 20축 창 문제 → 종목 사유(벤치마크가 멀쩡해도).
    rows = [x for x in inp.prices["0015K0"]["rows"] if x[0] != ax["dates"][i - 7]]
    inp3 = FI.Inputs(
        **{
            **inp.__dict__,
            "prices": {**inp.prices, "0015K0": {**inp.prices["0015K0"], "rows": rows}},
        }
    )
    s3, b3 = FI.build_series(inp3, ax["dates"])
    assert FI.relative_return(s3["0015K0"], b3, i) == (None, "ticker_window")


def test_each_ticker_uses_its_own_series_not_the_last_one(world) -> None:
    """판정 §4 — 임시 조사의 '마지막 종목 자료 반복' 결함(반복문 함수 늦은 바인딩)을 잡는다."""
    inp, ax = world
    pl = FI.plan(inp, ax)
    ex = FI.examples(inp, ax, pl)
    series, bench = FI.build_series(inp, ax["dates"])
    by = {(r["ticker"], r["i"]): r for r in ex["rows"]}
    for t in pl["eligible"]:
        i = 350
        r = by[(t, i)]
        assert r["p"] == m06.features_at(series[t].s.closes, i)
        assert r["v"] == FI.volume_ratio(series[t], ax["dates"], i)[0]
        assert r["r"] == FI.relative_return(series[t], bench, i)[0]
    vals = {t: by[(t, 350)]["v"] for t in pl["eligible"]}
    assert len(set(vals.values())) == len(vals)  # 종목마다 다른 거래량 경로 → 다른 V


def test_future_rows_do_not_change_past_features(world) -> None:
    inp, ax = world
    pl = FI.plan(inp, ax)
    before = {(r["ticker"], r["i"]): r for r in FI.examples(inp, ax, pl)["rows"]}
    rows = [list(x) for x in inp.prices["111111"]["rows"]]
    k = next(j for j, x in enumerate(rows) if x[0] == DATES[420])
    for j in range(k, len(rows)):  # 미래 가격 · 거래량만 바꿈(change 일관 유지)
        rows[j][4] *= 1.5
        rows[j][5] *= 3
    rows[k][6] = rows[k][4] / rows[k - 1][4] - 1.0
    inp.prices["111111"]["rows"] = rows
    after = {
        (r["ticker"], r["i"]): r for r in FI.examples(inp, ax, FI.plan(inp, ax))["rows"]
    }
    for i in (300, 399, 419):
        b, a = before[("111111", i)], after[("111111", i)]
        assert (b["p"], b["v"], b["r"]) == (a["p"], a["v"], a["r"])
    # 목표 창(411~430)만 미래 가격을 쓴다.
    assert before[("111111", 410)]["y"] != after[("111111", 410)]["y"]


# ── 구간 · 적격 · 같은 행 · 가중치(판정 §3-1) ────────────────────────────────────


def test_folds_boundary_and_eligibility(world) -> None:
    inp, ax = world
    pl = FI.plan(inp, ax)
    assert sorted(pl["eligible"]) == [
        "0015K0",
        "111111",
        "333333",
        "444444",
        "458030",
        "555555",
        "666666",
    ]
    assert len(pl["review"]) == 6  # 보조 범위 = 적격 7 - 제외 1(최소 5종 충족)
    assert pl["review"] == [t for t in pl["eligible"] if t != "458030"]
    assert not pl["per_ticker"]["222222"]["eligible"]  # 분모 유지 · 사유
    ex = FI.examples(inp, ax, pl)
    for k in range(P.FOLDS):
        train, test = ST.fold_sets(ex, k)
        s0 = ex["folds"][k][0]
        assert all(ax["dates"][r["i"] + 20] < ax["dates"][s0] for r in train)
        assert {r["i"] for r in test} <= set(ex["folds"][k])
        assert len(test) == pl["test_rows"]["G_ALL"][k]
        assert len(train) == pl["train_rows"][k]


def test_same_rows_hgb_weights_only_and_nan_not_zero(world) -> None:
    inp, ax = world
    pl = FI.plan(inp, ax)
    ex = FI.examples(inp, ax, pl)
    # V · R 결측 행 만들기 — 기본 행은 남고 HGB 입력은 NaN(0 대입 없음).
    target = next(r for r in ex["rows"] if r["ticker"] == "111111" and r["i"] == 200)
    target["v"], target["v_reason"] = None, "avg_zero"
    target["r"], target["r_reason"] = None, "bench_window"
    x = ST.x_of(target, "HGB_PVR")
    assert len(x) == 7 and x[:5] == [float(v) for v in target["p"]]
    assert all(math.isnan(v) for v in x[5:])
    assert ST.x_of(target, "RIDGE_P") == x[:5]
    # 열 순서 = P 5열 + V(PV) · R(PR) · V, R(PVR)
    row = {**target, "v": 1.5, "r": 0.25}
    assert ST.x_of(row, "HGB_PV")[5:] == [1.5]
    assert ST.x_of(row, "HGB_PR")[5:] == [0.25]
    assert ST.x_of(row, "HGB_PVR")[5:] == [1.5, 0.25]
    assert ST.x_of(row, "HGB_P") == x[:5] and ST.x_of(row, "MEDIAN_P") == x[:5]
    train, test = ST.fold_sets(ex, 0)
    assert target in train
    w = ST.date_weights(train)
    by_date: dict[str, float] = {}
    for r, wi in zip(train, w):
        by_date[r["date"]] = by_date.get(r["date"], 0.0) + wi
    assert all(abs(v - 1.0) < 1e-12 for v in by_date.values())  # 날짜마다 합 1
    res = ST.train_fold(train, test)
    assert {c for c, v in res.items() if v["status"] == "OK"} == set(P.CONFIGS)
    assert all(len(v["raw"]) == len(test) for v in res.values())
    # RIDGE · MEDIAN 은 종목별 학습 날짜 동일 비중(가중치 없음) — 저장 n = 그 종목 학습 행 수.
    ridge = json.loads(res["RIDGE_P"]["files"]["ridge.json"])["by_ticker"]
    for t, q in ridge.items():
        assert q["n"] == sum(1 for r in train if r["ticker"] == t)
        assert q["features"] == list(P.P_NAMES)


def test_restore_reproduces_raw_and_clipped(world) -> None:
    inp, ax = world
    ex = FI.examples(inp, ax, FI.plan(inp, ax))
    train, test = ST.fold_sets(ex, 1)
    res = ST.train_fold(train, test)
    rc = ST.restore_check(res, test)
    assert all(v["ok"] for v in rc.values())
    # Ridge 저장값(mean · scale · coef · intercept)만으로 원시 예측을 다시 만든다(판정 §3-3).
    again = ST.restore_predict("RIDGE_P", res["RIDGE_P"]["files"], test)
    assert (
        max(abs(a - b) for a, b in zip(again, res["RIDGE_P"]["raw"])) <= P.RESTORE_TOL
    )
    # 저장물이 바뀌면 복원 불일치로 잡힌다.
    p = json.loads(res["RIDGE_P"]["files"]["ridge.json"])
    t0 = next(iter(p["by_ticker"]))
    p["by_ticker"][t0]["intercept"] += 0.01
    res["RIDGE_P"]["files"]["ridge.json"] = json.dumps(p).encode()
    assert not ST.restore_check(res, test)["RIDGE_P"]["ok"]


def test_failed_or_nonfinite_config_is_failed_not_replaced(monkeypatch, world) -> None:
    inp, ax = world
    ex = FI.examples(inp, ax, FI.plan(inp, ax))
    train, test = ST.fold_sets(ex, 0)
    real = ST.FITTERS["HGB_PR"]

    def bad(rows):
        files, params, predict = real(rows)
        return files, params, lambda rows: [float("nan")] * len(rows)

    monkeypatch.setitem(ST.FITTERS, "HGB_PR", bad)
    monkeypatch.setitem(ST.FITTERS, "HGB_PV", lambda rows: 1 / 0)
    res = ST.train_fold(train, test)
    assert (res["HGB_PR"]["status"], res["HGB_PR"]["reason"]) == (
        "FAILED",
        "비유한 예측",
    )
    assert "raw" not in res["HGB_PR"] and res["HGB_PR"]["seconds"] >= 0
    assert (
        res["HGB_PV"]["status"] == "FAILED"
        and "ZeroDivisionError" in res["HGB_PV"]["reason"]
    )
    assert res["HGB_P"]["status"] == "OK"


# ── 판정(판정 §3-2) ──────────────────────────────────────────────────────────────


def _sc(overall, blocks):
    return {"overall": overall, "blocks": list(blocks)}


@pytest.mark.parametrize(
    "cand, base, status",
    [
        (
            _sc(0.90, [0.9, 0.9, 1.0]),
            _sc(1.0, [1.0, 1.0, 1.0]),
            "FEATURE_GAIN_SUPPORTED",
        ),
        (
            _sc(0.96, [0.9, 0.9, 1.0]),
            _sc(1.0, [1.0, 1.0, 1.0]),
            "FEATURE_GAIN_NOT_SHOWN",
        ),
        (
            _sc(0.90, [0.9, 1.0, 1.0]),
            _sc(1.0, [1.0, 1.0, 1.0]),
            "FEATURE_GAIN_NOT_SHOWN",
        ),
        (
            _sc(0.90, [0.5, 0.5, 1.06]),
            _sc(1.0, [1.0, 1.0, 1.0]),
            "FEATURE_GAIN_NOT_SHOWN",
        ),
        (_sc(0.0, [0.0, 0.0, 0.0]), _sc(0.0, [0.0, 0.0, 0.0]), "NO_BASELINE_HEADROOM"),
        # 한 구간 기준 0 · 후보 0 = 동률(우위 아님) — 나머지 두 구간 우위면 통과.
        (
            _sc(0.60, [0.0, 0.8, 0.9]),
            _sc(1.0, [0.0, 1.0, 1.0]),
            "FEATURE_GAIN_SUPPORTED",
        ),
        # 한 구간 기준 0 · 후보 양수 = 그 구간 악화(전체 기준 양수 · base_zero 로 바꾸지 않음).
        (
            _sc(0.60, [0.1, 0.8, 0.9]),
            _sc(1.0, [0.0, 1.0, 1.0]),
            "FEATURE_GAIN_NOT_SHOWN",
        ),
        # 한 구간 기준 0 · 후보 0 · 다른 한 구간만 우위 = 우위 1 → 미충족.
        (
            _sc(0.90, [0.0, 0.8, 1.0]),
            _sc(1.0, [0.0, 1.0, 1.0]),
            "FEATURE_GAIN_NOT_SHOWN",
        ),
    ],
)
def test_judge_a(cand, base, status) -> None:
    assert R.judge_a(cand, base)["status"] == status


def _tail(dates=25, tickers=4, u=1.0):
    return {"dates": dates, "tickers": tickers, "u_pp": u}


@pytest.mark.parametrize(
    "c, ridge, median, tc, tr, status",
    [
        (1.0, 2.0, 3.0, _tail(), _tail(u=1.0), "RESEARCH_CANDIDATE"),
        (1.0, 0.0, 3.0, _tail(), _tail(), "NO_BASELINE_HEADROOM"),
        (1.0, 2.0, 0.0, _tail(), _tail(), "NO_BASELINE_HEADROOM"),
        (1.0, 1.04, 3.0, _tail(), _tail(), "FEATURE_GAIN_ONLY"),  # RIDGE 5% 미만
        (
            1.0,
            2.0,
            1.0,
            _tail(),
            _tail(),
            "FEATURE_GAIN_ONLY",
        ),  # MEDIAN 과 같음(작지 않음)
        (1.0, 2.0, 3.0, _tail(dates=19), _tail(), "TAIL_DATA_SHORT"),
        (1.0, 2.0, 3.0, _tail(tickers=2), _tail(), "TAIL_DATA_SHORT"),
        (
            1.0,
            2.0,
            3.0,
            _tail(u=1.06),
            _tail(u=1.0),
            "FEATURE_GAIN_ONLY",
        ),  # U 5% 초과 악화
        (
            1.0,
            2.0,
            3.0,
            _tail(u=1.05),
            _tail(u=1.0),
            "RESEARCH_CANDIDATE",
        ),  # 경계(5% 이하)
        (1.0, 2.0, 3.0, _tail(u=0.0), _tail(u=0.0), "RESEARCH_CANDIDATE"),
        (
            1.0,
            2.0,
            3.0,
            _tail(u=0.1),
            _tail(u=0.0),
            "FEATURE_GAIN_ONLY",
        ),  # RIDGE U 0 → 후보도 0
    ],
)
def test_judge_b_order(c, ridge, median, tc, tr, status) -> None:
    got = R.judge_b(
        _sc(c, [c] * 3), _sc(ridge, [ridge] * 3), _sc(median, [median] * 3), tc, tr
    )
    assert got["status"] == status


def test_b_short_comparison_still_marks_tail_shortage() -> None:
    got = R.judge_b(
        _sc(1.0, [1] * 3), _sc(1.0, [1] * 3), _sc(3.0, [3] * 3), _tail(dates=3), _tail()
    )
    assert got["status"] == "FEATURE_GAIN_ONLY" and got["tail_enough"] is False


def test_tail_u_uses_only_deep_rows_by_date() -> None:
    rows = [
        {
            "date": "d1",
            "ticker": "A",
            "truth": -0.10,
            "preds": {"X": -0.05},
        },  # 과소 5%p
        {
            "date": "d1",
            "ticker": "B",
            "truth": -0.09,
            "preds": {"X": -0.12},
        },  # 과대 → 0
        {
            "date": "d2",
            "ticker": "A",
            "truth": -0.20,
            "preds": {"X": -0.10},
        },  # 과소 10%p
        {
            "date": "d3",
            "ticker": "C",
            "truth": -0.02,
            "preds": {"X": 0.0},
        },  # 큰 하락 아님
        {
            "date": "d1",
            "ticker": "D",
            "truth": -0.08,
            "preds": {"X": -0.08},
        },  # 경계 -8% 포함 · 과소 0 · 날짜마다 행 수가 달라 날짜 평균 ≠ 행 평균
    ]
    t = R.tail(rows, "X")
    assert (t["rows"], t["dates"], t["tickers"]) == (4, 2, 3)
    assert t["u_pp"] == pytest.approx(((5.0 + 0.0 + 0.0) / 3 + 10.0) / 2)
    assert t["u_pp"] != pytest.approx((5.0 + 0.0 + 10.0 + 0.0) / 4)
    assert t["max_under_pp"] == pytest.approx(10.0)


# ── 실행 흐름 · 잠금 · 1회 · verify(판정 §3-3) ──────────────────────────────────


@pytest.fixture
def flow(tmp_path, world):
    inp, ax = world
    load = lambda: (inp, ax, None)  # noqa: E731
    clock = iter(
        datetime(2026, 10, 24, 1, 0, s, tzinfo=timezone.utc) for s in range(59)
    ).__next__
    return tmp_path / "poc6_08", load, clock


def test_lock_run_verify_and_once(flow) -> None:
    root, load, clock = flow
    doc = ST.lock(root, REPO, load, clock, expected=None, base_commit="abc")
    assert doc["code"]["base_commit"] == "abc" and set(doc["code"]["sha256"]) == set(
        P.CODE_FILES
    )
    assert doc["corrects"] is None
    assert (
        doc["recipe"]["HGB"]["resolved"]["max_iter"] == 100
    )  # 설치 판 전체 설정(설계 §4)
    assert "validation_fraction" in doc["recipe"]["HGB"]["resolved"]
    assert all(len(v) == 64 for v in doc["code"]["sha256"].values())
    # lock 은 목표 · 예측 값을 담지 않는다(식별자 · 분모 · 가용만).
    assert '"y":' not in json.dumps(doc) and '"preds":' not in json.dumps(doc)
    with pytest.raises(P.Refused):
        ST.lock(root, REPO, load, clock, expected=None)
    res = ST.run(root, REPO, load, clock)
    assert res["meta"]["status"] == "OK" and res["meta"]["restore_ok"]
    rdir = res["run_dir"]
    for name in (
        "examples.json",
        "predictions.json",
        "restore.json",
        "report.json",
        "report.md",
        "run.json",
    ):
        assert (rdir / name).exists()
    meta = json.loads((rdir / "run.json").read_text())
    assert meta["failed_configs"] == [] and meta["status"] == "OK"
    for fold, files in meta["model_files"].items():  # 모델 파일 해시 기록(PLAN §7)
        for name, sha in files.items():
            assert EV.sha256_bytes((rdir / "models" / fold / name).read_bytes()) == sha
    assert set(meta["model_files"]["fold1"]) == {
        "median.json",
        "ridge.json",
        "hgb_p.joblib",
        "hgb_pv.joblib",
        "hgb_pr.joblib",
        "hgb_pvr.joblib",
    }
    assert all(set(t) == set(P.CONFIGS) for t in meta["timing_seconds"])
    ex = json.loads((rdir / "examples.json").read_text())
    assert ex["weights"] == ST.weights_record(ex)  # 가중치 근거 = 학습 날짜별 n_d
    md = (rdir / "report.md").read_text()
    assert "## 가용" in md and "## 종목별 MAE" in md
    rep = res["report"]
    assert set(rep["A"]["G_ALL"]) == set(P.CANDIDATES) and set(
        rep["scores"]["G_REVIEW"]
    ) == set(P.CONFIGS)
    assert (
        rep["scores"]["G_REVIEW"]["HGB_P"]["rows"]
        < rep["scores"]["G_ALL"]["HGB_P"]["rows"]
    )
    assert VR.verify(root, load)["status"] == "OK"
    with pytest.raises(P.Refused):
        ST.run(root, REPO, load, clock)
    again = ST.run(root, REPO, load, clock, correction_reason="정정 시험")
    assert (
        again["meta"]["corrects"] == [rdir.name]
        and again["meta"]["correction_reason"] == "정정 시험"
    )


def test_verify_catches_tampering(flow) -> None:
    root, load, clock = flow
    ST.lock(root, REPO, load, clock, expected=None)
    rdir = ST.run(root, REPO, load, clock)["run_dir"]
    preds = json.loads((rdir / "predictions.json").read_text())
    preds[0]["preds"]["HGB_PV"] = -0.5
    (rdir / "predictions.json").write_text(json.dumps(preds))
    v = VR.verify(root, load)
    assert v["status"] == "MISMATCH" and any(
        "clip" in p or "보고서" in p for p in v["problems"]
    )


def test_run_refuses_when_code_or_plan_differs(flow, monkeypatch) -> None:
    root, load, clock = flow
    ST.lock(root, REPO, load, clock, expected=None)
    real = P.code_hashes
    monkeypatch.setattr(
        P,
        "code_hashes",
        lambda repo: {**real(repo), "app/feature_gain/study.py": "0" * 64},
    )
    with pytest.raises(P.CheckRequired, match="코드"):
        ST.run(root, REPO, load, clock)
    monkeypatch.setattr(P, "code_hashes", real)
    real_env = P.env
    monkeypatch.setattr(P, "env", lambda: {**real_env(), "numpy": "0.0"})
    with pytest.raises(P.CheckRequired, match="라이브러리"):
        ST.run(root, REPO, load, clock)
    monkeypatch.setattr(P, "env", real_env)
    inp, ax, _ = load()
    inp.prices["111111"]["rows"][250][4] = -1.0  # 행 유효성이 바뀜 → 계획이 잠금과 다름
    with pytest.raises(P.CheckRequired, match="잠금과 다름"):
        ST.run(root, REPO, load, clock)
    assert not (next(root.iterdir()) / "runs").exists()  # 성과 산출물 0


def test_lock_stops_when_plan_table_differs(flow) -> None:
    root, load, clock = flow
    with pytest.raises(P.CheckRequired, match="PLAN 표와 다름"):
        ST.lock(root, REPO, load, clock, expected={"train_rows": [1, 2, 3]})
    assert not any(root.glob("*/protocol.json"))


def test_restore_mismatch_is_recorded(flow, monkeypatch) -> None:
    root, load, clock = flow
    ST.lock(root, REPO, load, clock, expected=None)
    real = ST.restore_predict
    monkeypatch.setattr(
        ST,
        "restore_predict",
        lambda cfg, files, test: [
            v + (1e-6 if cfg == "HGB_P" else 0) for v in real(cfg, files, test)
        ],
    )
    res = ST.run(root, REPO, load, clock)
    assert (
        res["meta"]["status"] == "RESTORE_MISMATCH"
        and res["report"]["restore_ok"] is False
    )
    # 같은 (어긋난) 복원으로 다시 계산하면 저장 원시 예측과 다름 → 불일치.
    v = VR.verify(root, load)
    assert v["status"] == "MISMATCH" and v["run_status"] == "RESTORE_MISMATCH"
    assert any("HGB_P" in x and "다시 계산" in x for x in v["problems"])
    monkeypatch.setattr(ST, "restore_predict", real)
    # 올바른 복원이면 산출물은 서로 맞지만, 실행 상태를 함께 돌려주고 CLI 는 0 으로 끝내지 않는다.
    v = VR.verify(root, load)
    assert v["status"] == "OK" and v["run_status"] == "RESTORE_MISMATCH"
    cli = _cli(monkeypatch, root, load)
    assert cli.main(["verify"]) == 2
    assert cli.main(["verify", "--run-id", res["run_dir"].name]) == 2
    assert cli.main(["verify", "--run-id", "없는_실행"]) == 2


def test_coverage_short_is_data_short(world) -> None:
    inp, ax = world
    pl = FI.plan(inp, ax)
    pl["coverage"]["HGB_PV"]["G_REVIEW"]["status"] = "DATA_SHORT"
    ex = FI.examples(inp, ax, pl)
    preds = []
    for k in range(P.FOLDS):
        train, test = ST.fold_sets(ex, k)
        res = ST.train_fold(train, test)
        preds += [
            {
                "fold": k,
                "ticker": r["ticker"],
                "date": r["date"],
                "truth": r["y"],
                "preds": {c: ST.clip(res[c]["raw"][j]) for c in P.CONFIGS},
            }
            for j, r in enumerate(test)
        ]
    meta = {"run_id": "x", "config_status": [{c: "OK" for c in P.CONFIGS}] * 3}
    rep = R.build({"lock_id": "l", "plan": pl}, meta, preds)
    assert rep["A"]["G_REVIEW"]["HGB_PV"] == {"status": "DATA_SHORT"}
    assert rep["A"]["G_ALL"]["HGB_PV"]["status"] != "DATA_SHORT"


# ── 입력 검증 · 06 무변경 경로 ─────────────────────────────────────────────────


def test_hash_mismatch_is_check_required(tmp_path) -> None:
    (tmp_path / P.COHORT_PATH).parent.mkdir(parents=True)
    (tmp_path / P.COHORT_PATH).write_text("{}")
    with pytest.raises(P.CheckRequired, match="cohort 해시"):
        FI.load(tmp_path, tmp_path / "ev", tmp_path / "cal")
    with pytest.raises(P.CheckRequired, match="읽기 실패"):
        FI.load(tmp_path / "없음", tmp_path / "ev", tmp_path / "cal")


def test_no_path_reads_06_trained_weights() -> None:
    for f in ("protocol.py", "inputs.py", "study.py", "report.py"):
        text = (REPO / "app/feature_gain" / f).read_text(encoding="utf-8")
        assert "poc6_06/models" not in text and "models/mv_" not in text
    assert S.HGB_PARAMS == P.recipe()["HGB"]["params"]


# ── 검토 1회 반영 — 미시험 분기(입력 · 축 · 구간 · 적격 · 가용 · A/B · verify · 정정 · 실패) ─────


def _fake_state() -> dict[str, Any]:
    tickers = list(P.REVIEW_OUT) + [f"9{k:05d}" for k in range(17)]
    kospi = json.dumps({"dates": ["2026-10-16", "2026-10-19"]}).encode()
    cal = b"date\n2026-10-19\n"
    k_sha, c_sha = EV.sha256_bytes(kospi), EV.sha256_bytes(cal)
    return {
        "tickers": tickers,
        "cohort": {
            # rank 역순 — load 가 rank 로 정렬하는지 본다.
            "selected": [{"ticker": t, "rank": 24 - k} for k, t in enumerate(tickers)],
            "aux_groups": {
                "bond_cash_mixed_5": list(P.REVIEW_OUT[:5]),
                "inverse_2": list(P.REVIEW_OUT[5:]),
            },
        },
        "prices": {
            "row_format": list(FI.ROW_FORMAT),
            "tickers": {
                t: {
                    "observed_at": "2026-10-23T01:19:20Z",
                    "rows": [["2026-10-19", 1, 1, 1, 10.0, 5, 0.0]],
                }
                for t in tickers
            },
        },
        "bench": [("069500", "2026-10-19", 300.0, P.SOURCE, "x", 0.0)],
        "bench_table": True,
        "runs": True,
        "k_sha": k_sha,
        "c_sha": c_sha,
        "objects": {k_sha: kospi, c_sha: cal},
        "manifest": {
            "sources": {
                "date_axis": {
                    "kospi_stored_dates": {"object": k_sha},
                    "calendar_files": [
                        {"name": "krx_trading_days_2026.csv", "sha256": c_sha}
                    ],
                }
            }
        },
    }


def _load_with(tmp_path, mp, change=None, after=None) -> FI.Inputs:
    import sqlite3
    from types import SimpleNamespace

    st = _fake_state()
    if change:
        change(st)
    paths = {
        "COHORT_SHA": tmp_path / P.COHORT_PATH,
        "PRICES_SHA": tmp_path / P.PRICES_PATH,
        "BENCH_SHA": tmp_path / P.BENCH_PATH,
    }
    for f in paths.values():
        f.parent.mkdir(parents=True, exist_ok=True)
    paths["COHORT_SHA"].write_text(json.dumps(st["cohort"]))
    paths["PRICES_SHA"].write_text(json.dumps(st["prices"]))
    con = sqlite3.connect(paths["BENCH_SHA"])
    if st["bench_table"]:
        con.execute(
            "CREATE TABLE prices (ticker TEXT, date TEXT, close REAL, source TEXT,"
            " fetched_at TEXT, change REAL)"
        )
        con.executemany("INSERT INTO prices VALUES (?,?,?,?,?,?)", st["bench"])
    con.commit()
    con.close()
    for const, f in paths.items():
        mp.setattr(P, const, EV.sha256_bytes(f.read_bytes()))
    mp.setattr(P, "AXIS_KOSPI_OBJECT", st["k_sha"])
    mp.setattr(P, "AXIS_CALENDAR_FILES", (("krx_trading_days_2026.csv", st["c_sha"]),))
    runs = [SimpleNamespace(run_id=P.AXIS_RUN, manifest=st["manifest"])]
    mp.setattr(EV, "list_runs", lambda root: (runs if st["runs"] else [], []))

    def read_object(root, sha):
        if sha not in st["objects"]:
            raise EV.EvidenceError("object 없음")
        return st["objects"][sha]

    mp.setattr(EV, "read_object", read_object)
    if after:
        after(mp)
    return FI.load(tmp_path, tmp_path / "ev", tmp_path / "cal")


def test_load_reads_all_fixed_inputs(tmp_path, monkeypatch) -> None:
    inp = _load_with(tmp_path, monkeypatch)
    st = _fake_state()
    assert inp.cohort == list(reversed(st["tickers"]))  # rank 순
    assert sorted(inp.review_out) == sorted(P.REVIEW_OUT)
    assert inp.kospi_dates == ["2026-10-16", "2026-10-19"]
    assert inp.bench_rows == [("2026-10-19", 300.0, P.SOURCE, "x", 0.0)]
    assert (tmp_path / "cal" / "krx_trading_days_2026.csv").read_bytes() == (
        b"date\n2026-10-19\n"
    )
    assert inp.refs["bench"]["ticker"] == P.BENCH


def _set(path: str, value):
    def change(st):
        node = st
        keys = path.split(".")
        for k in keys[:-1]:
            node = node[k]
        node[keys[-1]] = value

    return change


@pytest.mark.parametrize(
    "change, after, match",
    [
        (None, lambda mp: mp.setattr(P, "COHORT_SHA", "0" * 64), "cohort 해시"),
        (None, lambda mp: mp.setattr(P, "PRICES_SHA", "0" * 64), "가격 사본 해시"),
        (None, lambda mp: mp.setattr(P, "BENCH_SHA", "0" * 64), "069500 사본 해시"),
        (_set("runs", False), None, "축 묶음"),
        (None, lambda mp: mp.setattr(P, "AXIS_KOSPI_OBJECT", "f" * 64), "KOSPI"),
        (
            None,
            lambda mp: mp.setattr(P, "AXIS_CALENDAR_FILES", (("x.csv", "0" * 64),)),
            "거래일 파일",
        ),
        (_set("manifest.sources.date_axis", "x"), None, "AttributeError"),
        (lambda st: st["objects"].clear(), None, "05 object 손상"),
        (_set("cohort.aux_groups.inverse_2", ["271050"]), None, "보조 범위"),
        (lambda st: st["cohort"]["selected"].pop(), None, "cohort 명단"),
        (lambda st: st["cohort"]["selected"][0].pop("rank"), None, "KeyError"),
        (_set("prices.row_format", ["date", "close"]), None, "가격 사본 형식"),
        (lambda st: st["prices"]["tickers"].pop("458030"), None, "가격 사본 형식"),
        (_set("prices", []), None, "AttributeError"),
        (_set("bench_table", False), None, "OperationalError"),
        (_set("bench", []), None, "069500 행 없음"),
    ],
)
def test_load_problems_are_check_required(
    tmp_path, monkeypatch, change, after, match
) -> None:
    with pytest.raises(P.CheckRequired, match=match):
        _load_with(tmp_path, monkeypatch, change, after)


def test_axis_t_is_earliest_end_on_axis(tmp_path, monkeypatch) -> None:
    inp = _world()
    inp.calendar_dir = tmp_path  # 연도 파일 없음 → 평일 ∩ KOSPI 저장일
    inp.bench_rows = inp.bench_rows[:-2]  # 069500 끝 = DATES[-3]
    ax = FI.build_axis(inp)
    assert (ax["limit"], ax["T"], ax["dates"][-1]) == (DATES[-3], DATES[-3], DATES[-3])
    inp.bench_rows = _world().bench_rows
    monkeypatch.setattr(P, "CAP", "2026-10-18")  # 상한이 일요일 → 그 전 축 날짜(금)
    assert FI.build_axis(inp)["T"] == DATES[-2] == "2026-10-16"
    monkeypatch.setattr(P, "CAP", DATES[-6])  # 자료 상한이 가장 이름
    assert FI.build_axis(inp)["T"] == DATES[-6]


def test_fold_positions_exact() -> None:
    fp = FI.fold_positions(DATES)
    n = len(DATES)
    assert fp["T_index"] == n - 1 and fp["anchor_index"] == n - 21
    assert [f[0] for f in fp["folds"]] == [n - 21 - 188, n - 21 - 125, n - 21 - 62]
    assert fp["folds"][-1][-1] == fp["anchor_index"]
    assert all(len(f) == P.FOLD_LEN for f in fp["folds"])
    assert all(b[0] == a[-1] + 1 for a, b in zip(fp["folds"], fp["folds"][1:]))
    with pytest.raises(P.CheckRequired):
        FI.fold_positions(DATES[:280])


def test_base_row_needs_feature_and_target_windows(world) -> None:
    inp, ax = world
    n = len(DATES)
    rows = [r for r in inp.prices["111111"]["rows"] if r[0] != DATES[300]]
    inp.prices["111111"] = {**inp.prices["111111"], "rows": rows}
    s, _ = FI.build_series(inp, ax["dates"])
    assert not FI.base_ok(s["111111"], 280, n)  # 목표 창 끝(i+20) 종가 없음
    assert not FI.base_ok(s["111111"], 360, n)  # feature 창 시작(i-60) 종가 없음
    assert FI.base_ok(s["111111"], 279, n) and FI.base_ok(s["111111"], 361, n)
    assert FI.base_ok(s["0015K0"], n - 21, n) and not FI.base_ok(s["0015K0"], n - 20, n)
    assert not FI.base_ok(s["0015K0"], FI.LB - 1, n) and FI.base_ok(
        s["0015K0"], FI.LB, n
    )


def test_eligibility_needs_every_fold_and_reports_cause(world) -> None:
    prices = _world_prices()
    prices["777777"] = _rows(11, start=100)  # 1구간 학습 211 < 252 · 2 · 3구간은 충분
    f3 = FI.fold_positions(DATES)["folds"][2]
    gap = {DATES[j] for j in f3[10:40]}
    prices["888888"] = [
        r for r in _rows(12) if r[0] not in gap
    ]  # 3구간 시험 부족(중간 공백)
    pl = FI.plan(_world(prices), _ax())
    a, b = pl["per_ticker"]["777777"], pl["per_ticker"]["888888"]
    assert a["train"] == [211, 274, 337] and not a["eligible"]
    assert "1구간 학습 211<252" in a["reason"] and "상장 전" in a["reason"]
    assert b["train"][2] >= P.MIN_TRAIN and b["test"][2] < P.MIN_TEST
    assert not b["eligible"] and "3구간 시험" in b["reason"] and "중간" in b["reason"]
    assert "MISSING_PRICE" in b["excluded_by_cause"]
    # PLAN 표 대조가 중간 공백(상장 전 아닌 제외 원인)을 잡는다(판정 §4).
    diffs = FI.check_expected(pl, {"exclusion_causes": ["BEFORE_FIRST_ROW"]})
    assert len(diffs) == 1 and "exclusion_causes" in diffs[0]


def _v_missing(monkeypatch, cond) -> None:
    real = FI.volume_ratio
    monkeypatch.setattr(
        FI,
        "volume_ratio",
        lambda ser, dates, i: (
            (None, "avg_zero") if cond(ser.ticker, i) else real(ser, dates, i)
        ),
    )


def test_coverage_train_shortage_is_data_short(monkeypatch) -> None:
    _v_missing(
        monkeypatch, lambda t, i: i < 300
    )  # 학습 행 대부분 V 결측 · 시험 행은 온전
    pl = FI.plan(_world(), _ax())
    cov = pl["coverage"]
    for cand in ("HGB_PV", "HGB_PVR"):
        for scope in P.SCOPES:
            f1 = cov[cand][scope]["folds"][0]
            assert cov[cand][scope]["status"] == "DATA_SHORT" and not f1["pass"]
            assert f1["test"][0] == f1["test"][1]
            assert f1["train"][0] < P.COVERAGE * f1["train"][1]
    assert (
        cov["HGB_PR"]["G_ALL"]["status"] == cov["HGB_PR"]["G_REVIEW"]["status"] == "OK"
    )
    # 학습 분모 = G_ALL 공동 학습 행(두 범위 같음)
    for k in range(P.FOLDS):
        assert cov["HGB_PV"]["G_REVIEW"]["folds"][k]["train"][1] == pl["train_rows"][k]
    diffs = FI.check_expected(
        pl, {"coverage_missing": 0, "coverage_denominators_match": True}
    )
    assert len(diffs) == 1 and diffs[0].startswith("coverage_missing")


def test_coverage_test_boundary_80_and_min_five(monkeypatch) -> None:
    f3 = set(FI.fold_positions(DATES)["folds"][2])
    out = ("458030", "111111")  # 보조 범위 = 5종
    _v_missing(monkeypatch, lambda t, i: t == "333333" and i in f3)
    cov = FI.plan(_world(review_out=out), _ax())["coverage"]["HGB_PV"]
    assert cov["G_REVIEW"]["folds"][2]["test"] == [252, 315]  # 정확히 80% = 충족
    assert cov["G_REVIEW"]["status"] == "OK" and cov["G_REVIEW"]["eligible"] == 5
    first = min(f3)
    _v_missing(monkeypatch, lambda t, i: t == "444444" and i == first)
    cov = FI.plan(_world(review_out=out), _ax())["coverage"]["HGB_PV"]
    assert cov["G_REVIEW"]["folds"][2]["test"] == [251, 315]  # 80% 미만
    assert cov["G_REVIEW"]["status"] == "DATA_SHORT"
    assert cov["G_ALL"]["status"] == "OK"  # 377/441
    monkeypatch.undo()
    pl = FI.plan(_world(review_out=out + ("333333",)), _ax())  # 보조 범위 4종
    for cand in P.CANDIDATES:
        v = pl["coverage"][cand]["G_REVIEW"]
        assert v["eligible"] == 4 and all(f["pass"] for f in v["folds"])
        assert v["status"] == "DATA_SHORT"


def test_check_expected_covers_every_plan_table_key(world) -> None:
    inp, ax = world
    pl = FI.plan(inp, ax)
    diffs = FI.check_expected(pl, P.EXPECTED)
    assert not any("재계산 항목 없음" in d for d in diffs)
    assert FI.check_expected(pl, {"없는 칸": 1}) == ["없는 칸: 재계산 항목 없음"]
    same = {
        "excluded_fold1_train": {"222222": pl["per_ticker"]["222222"]["train"][0]},
        "eligible_test_dates": [63, 63, 63],
        "exclusion_causes": ["BEFORE_FIRST_ROW"],
        "coverage_missing": 0,
        "coverage_denominators_match": True,
    }
    assert FI.check_expected(pl, same) == []


ERR = {
    "MEDIAN_P": lambda t: 0.03,
    "RIDGE_P": lambda t: 0.02,
    "HGB_P": lambda t: 0.01,
    "HGB_PV": lambda t: 0.005,
    "HGB_PR": lambda t: 0.01,
    "HGB_PVR": lambda t: 0.10 if t == "458030" else 0.005,
}


def _synth(pl, err, status=None) -> dict[str, Any]:
    """합성 예측 행(예측 - 실제 = err · 양수 = 하락을 작게 추정) → build."""
    rows = []
    for k in range(P.FOLDS):
        for d in range(25):
            for t in pl["eligible"]:
                truth = -0.10
                rows.append(
                    {
                        "fold": k,
                        "ticker": t,
                        "date": f"2026-{k + 1:02d}-{d + 1:02d}",
                        "truth": truth,
                        "preds": {c: ST.clip(truth + f(t)) for c, f in err.items()},
                    }
                )
    st = status or [{c: "OK" for c in P.CONFIGS} for _ in range(P.FOLDS)]
    return R.build(
        {"lock_id": "l", "plan": pl}, {"run_id": "x", "config_status": st}, rows
    )


def test_build_a_b_states_and_scope_only_candidate(world) -> None:
    pl = FI.plan(*world)
    rep = _synth(pl, ERR)
    A, B = rep["A"], rep["B"]
    assert A["G_ALL"]["HGB_PV"]["status"] == "FEATURE_GAIN_SUPPORTED"
    assert B["G_ALL"]["HGB_PV"]["status"] == "RESEARCH_CANDIDATE"
    assert B["G_ALL"]["HGB_PV"]["use_candidate"] is True
    # A 미충족 = B 판단 안 함(설계 §6-3) — 수치 · 조건만 남기고 B 규칙 상태 · 사유 글은 없음.
    assert A["G_ALL"]["HGB_PR"]["status"] == "FEATURE_GAIN_NOT_SHOWN"
    b = B["G_ALL"]["HGB_PR"]
    assert b["status"] == "NOT_JUDGED" and "why" not in b and not b["use_candidate"]
    assert b["ridge_relative_improvement"] == pytest.approx(0.5)
    assert b["median_relative_improvement"] == pytest.approx(2 / 3)
    assert (
        b["ridge_improve_ok"] and b["beats_median"] and b["tail_enough"] and b["u_ok"]
    )
    # 보조 범위 한정 후보(전체는 미충족 · 주 결과를 바꾸지 않음)
    assert A["G_ALL"]["HGB_PVR"]["status"] == "FEATURE_GAIN_NOT_SHOWN"
    assert B["G_ALL"]["HGB_PVR"]["status"] == "NOT_JUDGED"
    assert A["G_REVIEW"]["HGB_PVR"]["status"] == "FEATURE_GAIN_SUPPORTED"
    assert B["G_REVIEW"]["HGB_PVR"]["use_candidate"] is True
    md = R.markdown(json.loads(json.dumps(rep)))
    assert "판단 안 함(A 미충족)" in md and "RESEARCH_CANDIDATE" in md


def test_build_baseline_zero_and_failures(world) -> None:
    pl = FI.plan(*world)
    rep = _synth(pl, {**ERR, "HGB_P": lambda t: 0.0})
    for cand in P.CANDIDATES:
        a = rep["A"]["G_ALL"][cand]
        assert (
            a["status"] == "NO_BASELINE_HEADROOM" and a["relative_improvement"] is None
        )
        assert rep["B"]["G_ALL"][cand]["status"] == "NOT_JUDGED"
    ok = [{c: "OK" for c in P.CONFIGS} for _ in range(P.FOLDS)]
    # HGB_P 한 구간 실패 → A FAILED(비교 기준 없음) · B 는 판단 안 함(수치는 남김)
    st = [dict(x) for x in ok]
    st[1]["HGB_P"] = "FAILED"
    rep = _synth(pl, ERR, st)
    a, b = rep["A"]["G_ALL"]["HGB_PV"], rep["B"]["G_ALL"]["HGB_PV"]
    assert a["status"] == "FAILED" and "HGB_P" in a["reason"]
    assert b["status"] == "NOT_JUDGED" and b["ridge_relative_improvement"] is not None
    assert "HGB_P" not in rep["scores"]["G_ALL"]
    # 기준선 실패 → B FAILED(A 는 그대로)
    st = [dict(x) for x in ok]
    st[0]["RIDGE_P"] = "FAILED"
    rep = _synth(pl, ERR, st)
    assert rep["A"]["G_ALL"]["HGB_PV"]["status"] == "FEATURE_GAIN_SUPPORTED"
    assert rep["B"]["G_ALL"]["HGB_PV"]["status"] == "FAILED"
    assert rep["B"]["G_ALL"]["HGB_PV"]["use_candidate"] is False
    # 후보 실패 → A · B FAILED(다른 구성 값으로 대체 없음)
    st = [dict(x) for x in ok]
    st[2]["HGB_PV"] = "FAILED"
    rep = _synth(pl, ERR, st)
    assert rep["A"]["G_ALL"]["HGB_PV"]["status"] == "FAILED"
    assert rep["B"]["G_ALL"]["HGB_PV"]["status"] == "FAILED"
    assert rep["A"]["G_ALL"]["HGB_PR"]["status"] == "FEATURE_GAIN_NOT_SHOWN"
    md = R.markdown(json.loads(json.dumps(rep)))
    assert "| HGB_PV | 실행 실패 |" in md


def test_clip_and_out_of_range_raw_is_clipped_in_run(flow, monkeypatch) -> None:
    assert (ST.clip(0.3), ST.clip(-1.5), ST.clip(-0.2)) == (0.0, -1.0, -0.2)
    root, load, clock = flow
    real = ST.FITTERS["MEDIAN_P"]

    def shifted(rows):  # 저장값 · 예측 모두 +1(원시 > 0 → 제한 예측 0)
        _, params, _ = real(rows)
        params = {t: {**v, "median": v["median"] + 1.0} for t, v in params.items()}
        data = P.dumps({"kind": "MEDIAN_P", "by_ticker": params})
        return (
            {"median.json": data},
            params,
            lambda rs: [params[r["ticker"]]["median"] for r in rs],
        )

    monkeypatch.setitem(ST.FITTERS, "MEDIAN_P", shifted)
    ST.lock(root, REPO, load, clock, expected=None)
    rdir = ST.run(root, REPO, load, clock)["run_dir"]
    preds = json.loads((rdir / "predictions.json").read_text())
    assert all(
        p["raw"]["MEDIAN_P"] > 0 and p["preds"]["MEDIAN_P"] == 0.0 for p in preds
    )
    assert VR.verify(root, load)["status"] == "OK"


def _tamper_json(name):
    def wrap(fn):
        def go(rdir, ldir):
            f = rdir / name
            d = json.loads(f.read_text())
            fn(d)
            f.write_text(json.dumps(d))

        return go

    return wrap


def _swap_first_two(preds):
    preds[0], preds[1] = preds[1], preds[0]


def _protocol_review_all(rdir, ldir):
    f = ldir / "protocol.json"
    d = json.loads(f.read_text())
    d["plan"]["review"] = list(d["plan"]["eligible"])
    f.write_text(json.dumps(d))


def _raw_shift(
    d,
):  # 유한한 원시 값 변조 + 제한 값도 맞춰 바꿈 → 저장 모델 재계산이 잡음
    d[0]["raw"]["HGB_PV"] += 0.001
    d[0]["preds"]["HGB_PV"] = ST.clip(d[0]["raw"]["HGB_PV"])


def _train_x(d):  # 학습 행 X 변조(예측 · 보고서에 안 드러남) → 잠긴 입력 재계산이 잡음
    s0 = d["folds"][0][0]
    next(r for r in d["rows"] if r["i"] + 20 < s0)["p"][0] += 0.01


def _empty_model_list_and_tamper(rdir, ldir):
    _tamper_json("run.json")(lambda d: d.update(model_files={}))(rdir, ldir)
    (rdir / "models/fold2/hgb_pv.joblib").write_bytes(b"x")


def _drop_model_file_and_entry(rdir, ldir):
    _tamper_json("run.json")(lambda d: d["model_files"]["fold3"].pop("ridge.json"))(
        rdir, ldir
    )
    (rdir / "models/fold3/ridge.json").unlink()


TAMPER = [
    (
        _tamper_json("examples.json")(lambda d: d["rows"][0].update(date="1999-01-01")),
        "행 식별자",
    ),
    (
        _tamper_json("examples.json")(
            lambda d: d["weights"]["train_n_by_date"][0].clear()
        ),
        "가중치",
    ),
    (_tamper_json("predictions.json")(_swap_first_two), "시험 행과 어긋남"),
    (
        _tamper_json("predictions.json")(lambda d: d[0]["preds"].pop("HGB_PV")),
        "예측 칸",
    ),
    (
        _tamper_json("predictions.json")(lambda d: d[0]["preds"].update(HGB_P=-0.999)),
        "clip",
    ),
    (_protocol_review_all, "G_REVIEW"),
    (
        _tamper_json("restore.json")(lambda d: d[0]["HGB_P"].update(ok=False)),
        "복원 결과",
    ),
    (lambda r, ldir: (r / "models/fold1/median.json").write_bytes(b"{}"), "모델 파일"),
    (_empty_model_list_and_tamper, "모델 파일 목록"),
    (_tamper_json("predictions.json")(_raw_shift), "저장 모델로 다시 계산"),
    (_tamper_json("examples.json")(_train_x), "잠긴 입력"),
    (
        _tamper_json("restore.json")(
            lambda d: d[0]["HGB_P"].update(max_abs_diff_raw=1.0)
        ),
        "'일치' 표시",
    ),
    (_drop_model_file_and_entry, "모델 파일 목록"),
    (lambda r, ldir: (r / "report.md").write_text("x"), "report.md"),
    (
        _tamper_json("report.json")(
            lambda d: d["A"]["G_ALL"]["HGB_PV"].update(status="X")
        ),
        "저장 보고서",
    ),
    (_tamper_json("run.json")(lambda d: d.update(lock_id="other")), "잠금"),
]


def test_verify_finds_each_tampering(flow, tmp_path) -> None:
    import shutil

    root, load, clock = flow
    ST.lock(root, REPO, load, clock, expected=None)
    ST.run(root, REPO, load, clock)
    assert VR.verify(root, load)["status"] == "OK"
    for n, (fn, msg) in enumerate(TAMPER):
        copy = tmp_path / f"t{n}"
        shutil.copytree(root, copy)
        ldir = next(copy.glob("*/protocol.json")).parent
        rdir = next((ldir / "runs").iterdir())
        fn(rdir, ldir)
        v = VR.verify(copy, load)
        assert v["status"] == "MISMATCH" and any(msg in p for p in v["problems"]), (
            n,
            v,
        )
    for name in ("run.json", "predictions.json", "restore.json"):
        copy = tmp_path / f"missing_{name}"
        shutil.copytree(root, copy)
        rdir = next(next(copy.glob("*/runs")).iterdir())
        (rdir / name).unlink()
        v = VR.verify(copy, load)
        assert v["status"] == "CHECK_REQUIRED" and name in v["problems"][0], v


# 비유한 수 — 읽을 때 거절(손상 · r1 F2). (파일, 정규식, 바꿀 값)
NONFINITE = [
    ("predictions.json", r'("raw":\{"HGB_P":)(-?[0-9.e+-]+)', "1e999"),
    ("predictions.json", r'("raw":\{"HGB_P":)(-?[0-9.e+-]+)', "NaN"),
    ("examples.json", r'("p":\[)(-?[0-9.e+-]+)', "-1e999"),
    ("restore.json", r'("max_abs_diff_raw": )(-?[0-9.e+-]+)', "Infinity"),
    ("run.json", r'("HGB_P": )(-?[0-9.e+-]+)', "Infinity"),
    ("report.json", r'("overall": )(-?[0-9.e+-]+)', "NaN"),
]


def test_verify_rejects_nonfinite_numbers_in_any_artifact(flow, tmp_path) -> None:
    import re
    import shutil

    root, load, clock = flow
    ST.lock(root, REPO, load, clock, expected=None)
    ST.run(root, REPO, load, clock)
    for n, (name, pat, value) in enumerate(NONFINITE):
        copy = tmp_path / f"nf{n}"
        shutil.copytree(root, copy)
        f = next(copy.glob("*/runs/*")) / name
        text, k = re.subn(pat, lambda m: m.group(1) + value, f.read_text(), count=1)
        assert k == 1, (name, pat)
        f.write_text(text)
        v = VR.verify(copy, load)
        assert v["status"] == "CHECK_REQUIRED" and "비유한" in v["problems"][0], (n, v)
    # 잠금 문서의 비유한 수도 손상(읽지 않음)
    copy = tmp_path / "nf_protocol"
    shutil.copytree(root, copy)
    f = next(copy.glob("*/protocol.json"))
    f.write_text(re.sub(r'("coverage": )([0-9.]+)', r"\1Infinity", f.read_text(), 1))
    assert VR.verify(copy, load)["status"] == "CHECK_REQUIRED"
    # 쓰기 쪽 — 비유한 수는 산출물에 쓰지 않는다.
    with pytest.raises(ValueError):
        P.dumps({"x": float("inf")})
    with pytest.raises(ValueError):
        P.dumps({"x": float("nan")}, compact=True)


def test_nonfinite_model_value_is_config_failure(world, monkeypatch) -> None:
    ex = FI.examples(*world, FI.plan(*world))
    train, test = ST.fold_sets(ex, 0)
    monkeypatch.setattr(m06, "median", lambda ys: float("inf"))
    res = ST.train_fold(train, test)
    assert (
        res["MEDIAN_P"]["status"] == "FAILED"
        and "ValueError" in res["MEDIAN_P"]["reason"]
    )
    assert res["HGB_P"]["status"] == "OK"


@pytest.mark.parametrize(
    "target, exc",
    [
        ("examples", RuntimeError),
        ("examples", KeyboardInterrupt),
        ("weights_record", ValueError),
    ],
)
def test_any_failure_after_run_id_is_recorded(flow, monkeypatch, target, exc) -> None:
    root, load, clock = flow
    ST.lock(root, REPO, load, clock, expected=None)

    def boom(*a, **k):
        raise exc("실행 식별자 뒤 실패")

    if target == "examples":
        monkeypatch.setattr(FI, "examples", boom)
    else:
        monkeypatch.setattr(ST, "weights_record", boom)
    with pytest.raises(exc):
        ST.run(root, REPO, load, clock)
    rdir = next(next(root.glob("*/runs")).iterdir())
    meta = json.loads((rdir / "run.json").read_text())
    assert meta["status"] == "FAILED" and exc.__name__ in meta["reason"]
    assert meta["run_id"] == rdir.name and not (rdir / "examples.json").exists()
    assert VR.verify(root, load)["status"] == "RUN_FAILED"
    monkeypatch.undo()
    with pytest.raises(P.Refused):  # 실패 실행이 남아 있어 사유 없이 다시 못 함
        ST.run(root, REPO, load, clock)
    res = ST.run(root, REPO, load, clock, correction_reason="실패 뒤 같은 코드 재실행")
    assert res["meta"]["corrects"] == [rdir.name] and res["meta"]["status"] == "OK"


def test_failure_record_write_failure_keeps_original_error(flow, monkeypatch) -> None:
    root, load, clock = flow
    ST.lock(root, REPO, load, clock, expected=None)

    def broken(path, data):
        raise OSError("disk full")

    monkeypatch.setattr(P, "write_once", broken)
    with pytest.raises(OSError, match="disk full") as ei:
        ST.run(root, REPO, load, clock)
    assert any("실패 기록" in n for n in getattr(ei.value, "__notes__", []))


def _cli(monkeypatch, root, load):
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "run_feature_gain_cli", REPO / "scripts" / "run_feature_gain.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod.P, "ROOT", root)  # 절대 경로 → REPO / ROOT = root
    monkeypatch.setattr(mod.ST, "real_loader", lambda repo, ev: load)  # 작은 고정 자료
    return mod


def test_busy_writes_nothing(flow) -> None:
    root, load, clock = flow
    with P.run_lock(root):
        with pytest.raises(P.Busy):
            ST.lock(root, REPO, load, clock, expected=None)
    assert not any(root.glob("*/protocol.json"))
    ST.lock(root, REPO, load, clock, expected=None)
    with P.run_lock(root):
        with pytest.raises(P.Busy):
            ST.run(root, REPO, load, clock)
    assert not any(root.glob("*/runs"))


def test_mid_run_crash_is_recorded_and_rerun_needs_reason(flow, monkeypatch) -> None:
    root, load, clock = flow
    ST.lock(root, REPO, load, clock, expected=None)
    real = R.build
    monkeypatch.setattr(R, "build", lambda *a: 1 / 0)
    with pytest.raises(ZeroDivisionError):
        ST.run(root, REPO, load, clock)
    rdir = next(next(root.glob("*/runs")).iterdir())
    meta = json.loads((rdir / "run.json").read_text())
    assert meta["status"] == "FAILED" and "ZeroDivisionError" in meta["reason"]
    assert (rdir / "predictions.json").exists() and (rdir / "examples.json").exists()
    assert not (rdir / "report.json").exists()  # 대체 결과 없음
    assert VR.verify(root, load)["status"] == "RUN_FAILED"
    monkeypatch.setattr(R, "build", real)
    with pytest.raises(P.Refused):
        ST.run(root, REPO, load, clock)
    res = ST.run(root, REPO, load, clock, correction_reason="중단 뒤 같은 코드 재실행")
    assert res["meta"]["corrects"] == [rdir.name] and res["meta"]["status"] == "OK"
    assert VR.verify(root, load)["status"] == "OK"


def test_examples_write_failure_is_recorded(flow, monkeypatch) -> None:
    root, load, clock = flow
    ST.lock(root, REPO, load, clock, expected=None)
    real = P.write_once

    def flaky(path, data):
        if path.name == "examples.json":
            raise OSError("disk full")
        return real(path, data)

    monkeypatch.setattr(P, "write_once", flaky)
    with pytest.raises(OSError):
        ST.run(root, REPO, load, clock)
    rdir = next(next(root.glob("*/runs")).iterdir())
    meta = json.loads((rdir / "run.json").read_text())
    assert meta["status"] == "FAILED" and "disk full" in meta["reason"]
    assert VR.verify(root, load)["status"] == "RUN_FAILED"


def test_config_failure_is_run_status(flow, monkeypatch) -> None:
    root, load, clock = flow
    monkeypatch.setitem(ST.FITTERS, "HGB_PR", lambda rows: 1 / 0)
    ST.lock(root, REPO, load, clock, expected=None)
    res = ST.run(root, REPO, load, clock)
    assert res["meta"]["status"] == "CONFIG_FAILED"
    assert res["meta"]["failed_configs"] == ["HGB_PR"] and res["meta"]["restore_ok"]
    assert res["report"]["A"]["G_ALL"]["HGB_PR"]["status"] == "FAILED"
    assert VR.verify(root, load)["status"] == "OK"


def test_correction_lock_keeps_prior_runs(flow, monkeypatch) -> None:
    root, load, clock = flow
    first = ST.lock(root, REPO, load, clock, expected=None)
    r1 = ST.run(root, REPO, load, clock)["run_dir"]
    with pytest.raises(P.Refused, match="정정 잠금 불필요"):
        ST.lock(root, REPO, load, clock, expected=None, correction_reason="같은 코드")
    real = P.code_hashes
    fixed = {**real(REPO), "app/feature_gain/report.py": "1" * 64}
    monkeypatch.setattr(P, "code_hashes", lambda repo: fixed)
    with pytest.raises(P.CheckRequired, match="코드"):
        ST.run(
            root,
            REPO,
            load,
            clock,
            correction_reason="코드가 다르면 run 사유로 못 넘김",
        )
    with pytest.raises(P.Refused):
        ST.lock(root, REPO, load, clock, expected=None)
    second = ST.lock(
        root, REPO, load, clock, expected=None, correction_reason="report.py 결함 정정"
    )
    c = second["corrects"]
    assert c["lock_id"] == first["lock_id"] and c["reason"] == "report.py 결함 정정"
    assert c["changed_code"] == ["app/feature_gain/report.py"] and c["plan_same"]
    assert c["prior_runs"] == [r1.name] and not c["env_changed"]
    assert P.active_lock(root)[1]["lock_id"] == second["lock_id"]
    r2 = ST.run(root, REPO, load, clock)  # 새 잠금 아래 첫 실행 — 사유 불필요
    assert r2["meta"]["lock_corrects"]["lock_id"] == first["lock_id"]
    assert VR.verify(root, load) == {
        "status": "OK",
        "run_id": r2["run_dir"].name,
        "run_status": "OK",
        "problems": [],
    }
    assert (
        VR.verify(root, load, run_id=r1.name)["status"] == "OK"
    )  # 이전 실행 보존 · 검증 가능
    # recipe(구성 · 설정 · 기준)를 바꾸는 정정 잠금은 멈춤
    monkeypatch.setattr(
        P, "code_hashes", lambda repo: {**fixed, "app/feature_gain/report.py": "2" * 64}
    )
    real_recipe = P.recipe
    monkeypatch.setattr(P, "recipe", lambda: {**real_recipe(), "configs": ["HGB_P"]})
    with pytest.raises(P.CheckRequired, match="recipe"):
        ST.lock(root, REPO, load, clock, expected=None, correction_reason="설정 변경")
    monkeypatch.setattr(P, "recipe", real_recipe)
    monkeypatch.setattr(
        P, "MIN_TRAIN", 100
    )  # 적격 상수도 recipe(split) — 정정으로 못 바꿈
    with pytest.raises(P.CheckRequired, match="recipe"):
        ST.lock(root, REPO, load, clock, expected=None, correction_reason="적격 완화")
    monkeypatch.setattr(P, "MIN_TRAIN", 252)
    with pytest.raises(P.CheckRequired, match="PLAN 표"):
        ST.lock(
            root,
            REPO,
            load,
            clock,
            expected={"T": DATES[-1]},
            correction_reason="표 바꿈",
        )
    # 사슬이 어긋나면(정정 관계 없는 잠금 둘) 지금 잠금을 정하지 않음
    stray = root / "zz_stray"
    stray.mkdir()
    (stray / "protocol.json").write_text(json.dumps({**first, "lock_id": "stray"}))
    with pytest.raises(P.CheckRequired, match="잠금 수"):
        P.active_lock(root)


def test_code_hashes_cover_reused_calculation_files() -> None:
    reused = {
        "app/reentry_review/prices.py",
        "app/reentry_review/model.py",
        "app/stored_volume_evidence.py",
        "app/d20_pooled/study.py",
        "app/trading_day_lag.py",
        "app/market_briefing/calendar.py",
        "app/ml_evidence/store.py",
    }
    assert reused <= set(P.CODE_FILES) and set(P.code_hashes(REPO)) == set(P.CODE_FILES)
