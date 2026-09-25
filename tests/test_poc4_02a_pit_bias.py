"""POC4-02A — PIT universe · 제외 사유 · 날짜 분할 · 집계 테스트 (PLAN §3 · §4 · §5 · §6).

모두 tmp_path 의 KRX 스키마 고정 DB(`tests/_krx_fixture.py`)만 쓴다. 봉인 DB·라이브 DB 는 열지 않는다.
러너(새 폴더 · 재개 · 지문 · 라이브 경로 · 봉인 변경 · compare)는 `test_poc4_02a_pit_runner.py`.
"""

from __future__ import annotations

import dataclasses
import random

import pytest

from app import ml_pit_bias_eval as pit_eval
from app import ml_pit_bias_report as report
from app import ml_pit_universe as uni
from app.krx_sealed_reader import BENCHMARK_CODE, load_panel
from app.ml_baseline_snapshot import guard_sqlite_paths
from app.ml_research_split import SplitContractError
from app.ml_score_validity_eval import build_calendar, forward_excess
from tests._krx_fixture import (
    build_sealed_db,
    rows_by_date,
    series_rows,
    trading_dates,
)

DAYS = trading_dates(175)  # 2014-01-02 ~ 2014-09-03
ISO = [f"{d[:4]}-{d[4:6]}-{d[6:]}" for d in DAYS]
T, ENTRY, EXIT = "2014-06-30", "2014-07-01", "2014-08-01"
TI, EI, XI = ISO.index(T), ISO.index(ENTRY), ISO.index(EXIT)


def _walk(rng: random.Random, n: int) -> list[float]:
    out, price = [], 10000.0
    for _ in range(n):
        price = float(max(1000, round(price * (1 + rng.gauss(0.0, 0.015)))))
        out.append(price)
    return out


def make_code(
    code, lo=0, hi=None, *, seed, name=None, names=None, zero=(), carry_last=False
):
    """[lo, hi) 구간 상장 종목 행. `zero` 날짜는 거래량 0 · `carry_last` 는 마지막 행 = 직전 종가."""
    hi = len(DAYS) if hi is None else hi
    closes = _walk(random.Random(seed), hi - lo)
    if carry_last:
        closes[-1] = closes[-2]
    vols = [0 if ISO[k] in zero else 1000 for k in range(lo, hi)]
    return series_rows(
        code,
        DAYS[lo:hi],
        closes,
        volumes=vols,
        names=names,
        name=name or f"TEST {code}",
    )


def reasons_rows() -> dict:
    """PLAN §3 사유마다 종목 하나씩 — 신호일 T(2014-06-30) · 진입 07-01 · 청산 08-01."""
    maps = [make_code(BENCHMARK_CODE, seed=1, name="KODEX 200")]
    # A00000 — t 행 거래량 0 (feature 에는 쓰고 zero_volume_scored 로 센다)
    maps.append(make_code("A00000", seed=100, zero={T}))
    maps += [make_code(f"A{k:05d}", seed=100 + k) for k in range(1, 12)]
    maps.append(make_code("D00001", 0, TI + 10, seed=201))  # 보유 중 폐지
    maps.append(make_code("Z00001", 0, XI + 1, seed=202, zero={EXIT}, carry_last=True))
    maps.append(make_code("E00001", 0, TI + 1, seed=203))  # t 가 마지막 행
    maps.append(make_code("S00001", 0, TI - 3, seed=204))  # t 전에 폐지
    maps.append(make_code("L00001", 0, XI + 3, seed=205))  # 청산 뒤 폐지 → 평가 표본
    maps.append(make_code("V00001", seed=206, zero={ENTRY}))
    maps.append(make_code("W00001", TI - 10, seed=207))  # warm-up 부족
    maps.append(make_code("I00001", TI - 10, seed=208, name="TEST 인버스"))
    maps.append(make_code("N00001", TI + 5, seed=209))  # 미래 상장
    lev = ["TEST 레버리지"] * (TI + 1) + ["TEST PLAIN"] * (len(DAYS) - TI - 1)
    maps.append(make_code("R00001", seed=210, names=lev))  # t 이름 = 레버리지
    m, h = make_code("M00001", seed=211), make_code("H00001", seed=212)
    m[DAYS[TI - 5]]["FLUC_RT"] = "9.99"  # feature 창 관계 불일치
    h[DAYS[EI + 5]]["FLUC_RT"] = "9.99"  # 보유 구간 관계 불일치
    u, c, p = (
        make_code(x, seed=s)
        for x, s in (("U00001", 213), ("C00001", 214), ("P00001", 215))
    )
    u[DAYS[TI]]["ISU_NM"] = ""
    c[DAYS[TI]]["TDD_CLSPRC"] = ""
    p[DAYS[TI]]["TDD_CLSPRC"] = "0"
    maps += [m, h, u, c, p]
    return rows_by_date(*maps)


@pytest.fixture(scope="module")
def panel_ctx(tmp_path_factory):
    path = tmp_path_factory.mktemp("krx02a") / "krx.sqlite"
    build_sealed_db(path, reasons_rows())
    panel = load_panel(path)
    return panel, pit_eval.build_context(panel)


def _point(panel, date):
    return next(
        p for p in build_calendar(panel.dates, months_ahead=1) if p.signal_date == date
    )


@pytest.fixture(scope="module")
def records(panel_ctx):
    panel, ctx = panel_ctx
    point = _point(panel, T)
    return {
        arm: pit_eval.evaluate_point(ctx, arm, uni.arm_codes(panel, arm), point)
        for arm in uni.ARMS
    }


# --- universe ---------------------------------------------------------------------


def test_universe_future_listing_absent_delisted_present_control_final(panel_ctx):
    panel, _ctx = panel_ctx
    pit = uni.arm_codes(panel, uni.ARM_PIT)
    ctl = uni.arm_codes(panel, uni.ARM_CONTROL)
    assert BENCHMARK_CODE not in pit and BENCHMARK_CODE not in ctl
    assert set(ctl) == set(panel.present(panel.final_date)) - {BENCHMARK_CODE}
    assert {"D00001", "Z00001", "E00001", "S00001", "L00001"} <= set(pit) - set(ctl)
    at_t = uni.universe_at(panel, pit, T)
    assert "N00001" not in at_t and "S00001" not in at_t  # 미래 상장 · t 전 폐지
    assert {"D00001", "Z00001", "E00001"} <= set(at_t)  # 실재일에는 PIT 에 있다
    assert "N00001" not in uni.universe_at(panel, ctl, T)
    assert "N00001" in uni.universe_at(panel, ctl, panel.final_date)


def test_name_filter_uses_name_at_t(panel_ctx, records):
    panel, _ctx = panel_ctx
    s = panel.series["R00001"]
    assert uni.name_at(s, T) == "TEST 레버리지"
    assert not uni.passes_name_filter(uni.name_at(s, T))
    # 최종 이름으로 필터했다면 통과했을 종목이다
    assert uni.passes_name_filter(uni.name_at(s, panel.final_date))
    rec = records[uni.ARM_PIT]
    assert (
        "R00001"
        not in rec["top_decile_tickers"] + rec["sensitivity"]["top_decile_tickers"]
    )
    assert rec["n_all"] - rec["n_filter"] == 1  # R00001 은 필터 전 표본에만


# --- 제외 사유 ------------------------------------------------------------------------


def _expected(**kw):
    out = uni.empty_reasons()
    out.update(kw)
    return out


def test_every_reason_code_counted_once(records):
    common = dict(
        ZERO_VOLUME_ENTRY=1,
        BASEPRICE_RELATION_MISMATCH=2,  # M00001(feature 창) · H00001(보유 구간)
        HISTORICAL_FILTER_UNAVAILABLE=1,
        NO_VALID_CLOSE=1,
        NON_POSITIVE_CLOSE=1,
    )
    pit, ctl = records[uni.ARM_PIT], records[uni.ARM_CONTROL]
    pit_only = dict(NO_FORWARD_EXIT_PRICE=1, ZERO_VOLUME_EXIT=1, NO_ENTRY_PRICE=1)
    assert pit["reasons_prefilter"] == _expected(
        **common, **pit_only, INSUFFICIENT_WARMUP=2
    )
    assert pit["reasons_filtered"] == _expected(
        **common,
        **pit_only,
        INSUFFICIENT_WARMUP=1,  # I00001(인버스) 은 필터 뒤에서 빠진다
    )
    assert ctl["reasons_prefilter"] == _expected(
        **common, NOT_YET_LISTED=1, INSUFFICIENT_WARMUP=2
    )
    assert ctl["reasons_filtered"] == _expected(**common, INSUFFICIENT_WARMUP=1)


def test_counts_coverage_and_delisted(records):
    pit, ctl = records[uni.ARM_PIT], records[uni.ARM_CONTROL]
    # 점수: A×12 · L · R · U · V · H + (PIT) D · Z · E — M(창 불일치)·C·P·W·I 는 점수 없음
    assert (pit["scored_count"], ctl["scored_count"]) == (20, 16)
    assert (pit["delisted_scored"], ctl["delisted_scored"]) == (4, 0)
    assert (pit["zero_volume_scored"], ctl["zero_volume_scored"]) == (1, 1)
    assert (pit["n_filter"], ctl["n_filter"]) == (13, 12)
    assert (pit["delisted_in_eval"], ctl["delisted_in_eval"]) == (1, 0)
    # 분모: universe ∩ 필터 ∩ is_pit_eligible — W·I(warm-up)·R(필터)·N(미상장) 제외
    assert (pit["coverage_denominator"], ctl["coverage_denominator"]) == (22, 18)
    assert pit["coverage"] == pytest.approx(13 / 22)
    assert len(pit["_scores"]) == len(pit["_labels"]) == pit["n_filter"]


def test_no_stale_row_scoring(panel_ctx):
    panel, ctx = panel_ctx
    pit = uni.arm_codes(panel, uni.ARM_PIT)
    run = pit_eval.train_and_score(ctx, pit, T)
    assert set(run.display_scores) <= set(uni.universe_at(panel, pit, T))
    assert "S00001" not in run.display_scores and "E00001" in run.display_scores
    later = "2014-07-31"
    run2 = pit_eval.train_and_score(ctx, pit, later)
    assert set(run2.display_scores) <= panel.present(later)
    assert not {"D00001", "E00001", "S00001"} & set(run2.display_scores)


def test_last_carried_price_not_used_as_exit(panel_ctx, records):
    panel, ctx = panel_ctx
    point = _point(panel, T)
    bench = uni.benchmark_pair(ctx.bench, ctx.bench_facts, ENTRY, EXIT)
    z = panel.series["Z00001"]
    out = uni.classify_pair(
        z, ctx.facts["Z00001"], point, bench, has_model=True, scored=True
    )
    assert out.reason == uni.ZERO_VOLUME_EXIT and out.label is None
    k0, k1 = bench
    c0, c1 = z.chain[z.index[ENTRY]], z.chain[z.index[EXIT]]
    assert out.sensitivity_label == (c1 / c0 - 1.0) - (k1 / k0 - 1.0)
    v = uni.classify_pair(
        panel.series["V00001"],
        ctx.facts["V00001"],
        point,
        bench,
        has_model=True,
        scored=True,
    )
    assert v.reason == uni.ZERO_VOLUME_ENTRY and v.sensitivity_label is not None
    rec = records[uni.ARM_PIT]
    # Z00001 · V00001 만 민감도에 추가된다 (행이 없는 D00001·E00001 은 민감도에서도 빠진다)
    assert rec["sensitivity"]["n"] == rec["n_filter"] + 2


def test_benchmark_unavailable_and_non_trading_date(panel_ctx):
    panel, ctx = panel_ctx
    point = _point(panel, T)
    s, f = panel.series["A00001"], ctx.facts["A00001"]
    bench = uni.benchmark_pair(ctx.bench, ctx.bench_facts, ENTRY, EXIT)
    assert uni.benchmark_pair(ctx.bench, ctx.bench_facts, ENTRY, "2099-01-01") is None
    for pair, scored in ((None, True), (bench, False)):
        out = uni.classify_pair(s, f, point, pair, has_model=True, scored=scored)
        assert out.reason == uni.BENCHMARK_UNAVAILABLE and out.label is None
    weekend = dataclasses.replace(point, signal_date="2014-06-28")  # 토요일
    with pytest.raises(ValueError, match="거래일"):
        pit_eval.evaluate_point(ctx, uni.ARM_PIT, (), weekend)


@pytest.mark.parametrize("mode", ["row_missing", "close_invalid"])
def test_benchmark_missing_at_t_marks_whole_universe(tmp_path, mode):
    """069500 에 t 값이 없으면 학습·점수 없이 arm universe 전부 BENCHMARK_UNAVAILABLE → 막힌 arm."""
    rows = reasons_rows()
    day = DAYS[TI]
    if mode == "row_missing":
        rows[day] = [r for r in rows[day] if r["ISU_CD"] != BENCHMARK_CODE]
    else:
        next(r for r in rows[day] if r["ISU_CD"] == BENCHMARK_CODE)["TDD_CLSPRC"] = ""
    path = tmp_path / "krx.sqlite"
    build_sealed_db(path, rows)
    panel = load_panel(path)
    ctx = pit_eval.build_context(panel)
    assert ctx.bench is panel.series[BENCHMARK_CODE]  # 봉인 panel 의 069500 만 쓴다
    for arm in uni.ARMS:
        codes = uni.arm_codes(panel, arm)
        universe = uni.universe_at(panel, codes, T)
        rec = pit_eval.evaluate_point(ctx, arm, codes, _point(panel, T))
        assert rec["split"] == {
            "status": "NO_MODEL",
            "reason": uni.BENCHMARK_UNAVAILABLE,
        }
        assert rec["scored_count"] == rec["n_filter"] == rec["n_all"] == 0
        extra = {uni.NOT_YET_LISTED: len(codes) - len(universe)}
        assert rec["reasons_prefilter"] == _expected(
            BENCHMARK_UNAVAILABLE=len(universe),
            **(extra if arm == uni.ARM_CONTROL else {}),
        )
        passing = [
            c
            for c in universe
            if uni.passes_name_filter(uni.name_at(panel.series[c], T))
        ]
        assert rec["reasons_filtered"] == _expected(BENCHMARK_UNAVAILABLE=len(passing))
        assert rec["coverage_denominator"] > 0 and rec["coverage"] == 0.0
        assert report.build_arm_block([rec], {})["status"] != report.MEASURED


def test_label_equals_forward_excess_on_chain_maps(panel_ctx):
    panel, ctx = panel_ctx
    point = _point(panel, T)
    bench = uni.benchmark_pair(ctx.bench, ctx.bench_facts, ENTRY, EXIT)
    maps = {
        code: {d: c for d, c in zip(s.dates, s.chain) if c is not None}
        for code, s in panel.series.items()
    }
    checked = 0
    for code in ("A00000", "A00001", "A00005", "L00001", "R00001"):
        s = panel.series[code]
        reason, label = uni.label_outcome(
            s, ctx.facts[code], bench, point, require_volume=True
        )
        assert reason is None
        assert label == forward_excess(maps, code, ENTRY, EXIT)
        checked += 1
    assert checked == 5


# --- 분할 · trainer ---------------------------------------------------------------------


def test_fold_identical_for_both_arms_and_trainer_matches_boundary(records):
    sp, sc = records[uni.ARM_PIT]["split"], records[uni.ARM_CONTROL]["split"]
    for key in (
        "split_fingerprint",
        "validation_start",
        "validation_end",
        "train_first_date",
        "train_last_date",
        "purged_days",
        "validation_days",
    ):
        assert sp[key] == sc[key], key
    assert sp["train_rows"] > sc["train_rows"]  # 폐지 종목 이력이 PIT 학습에만 있다
    for split, rec in ((sp, records[uni.ARM_PIT]), (sc, records[uni.ARM_CONTROL])):
        assert split["status"] == "OK" and split["purged_days"] == 20
        assert split["trainer_train_row_count"] == split["train_rows"]
        assert split["trainer_test_row_count"] == split["validation_rows"]
        assert split["last_train_date"] == split["train_last_date"]
        assert split["last_train_date"] < split["validation_start"]
        assert split["trainer_test_date_range"][0] >= split["validation_start"]
        assert rec["max_target_end_date"] <= T and rec["max_input_date"] == T
        assert rec["train_row_count"] == split["train_rows"]


def test_trainer_boundary_mismatch_raises(panel_ctx, monkeypatch):
    panel, ctx = panel_ctx
    real = pit_eval.train_walk_forward

    def off_by_one(rows, **kw):
        model, tr = real(rows, **kw)
        return model, dataclasses.replace(tr, train_row_count=tr.train_row_count - 1)

    monkeypatch.setattr(pit_eval, "train_walk_forward", off_by_one)
    with pytest.raises(SplitContractError, match="trainer 경계"):
        pit_eval.train_and_score(ctx, uni.arm_codes(panel, uni.ARM_PIT), T)


def test_no_model_when_calendar_too_short(panel_ctx):
    panel, ctx = panel_ctx
    point = build_calendar(panel.dates, months_ahead=1)[0]  # 2014-01-31 — 달력 22일
    rec = pit_eval.evaluate_point(
        ctx, uni.ARM_PIT, uni.arm_codes(panel, uni.ARM_PIT), point
    )
    assert rec["split"]["status"] == "NO_MODEL" and rec["scored_count"] == 0
    assert rec["reasons_prefilter"][uni.NO_MODEL] > 0 and rec["n_filter"] == 0


def test_evaluation_opens_no_database(panel_ctx):
    """평가 중 sqlite 연결 0 — 현재 etf_master·운영 DB 를 읽지 않는다."""
    panel, ctx = panel_ctx
    with guard_sqlite_paths([]):
        rec = pit_eval.evaluate_point(
            ctx,
            uni.ARM_CONTROL,
            uni.arm_codes(panel, uni.ARM_CONTROL),
            _point(panel, T),
        )
    assert rec["n_filter"] == 12


# --- 집계 -----------------------------------------------------------------------------


def test_basket_series_follows_e2_turnover_rules():
    got = report.basket_series(
        [
            ("d1", 0.01, ["a", "b"]),
            ("d2", 0.02, ["a", "c"]),
            ("d3", None, []),
            ("d4", 0.03, ["x"]),
        ]
    )
    assert got["gross"] == [0.01, 0.02, 0.03]
    assert got["turnover"] == [0.5, 1.0]  # 첫 날은 직전 바스켓 없음 → 제외
    assert got["net"]["25"] == pytest.approx([0.01, 0.02 - 0.5 * 0.005, 0.03 - 0.005])
    assert got["net_by_date"]["d1"]["50"] == 0.01


def test_blocked_arm_keeps_counts_only(records):
    recs = [dict(records[uni.ARM_PIT])]  # coverage 13/22 < 0.70
    block = report.build_arm_block(recs, {})
    assert block["status"] == "BLOCKED_COVERAGE" and block["metrics"] is None
    assert block["counts"]["totals"]["scored"] == 20
    public = report.public_record(recs[0], measured=False)
    assert "ic_filter" not in public and "_scores" not in public
    assert public["reasons_prefilter"] == recs[0]["reasons_prefilter"]
    effect = report.survivorship_effect(
        {uni.ARM_PIT: block, uni.ARM_CONTROL: block},
        {uni.ARM_PIT: recs, uni.ARM_CONTROL: recs},
    )
    assert effect["status"] == "NOT_PRODUCED"


def test_strategy_price_basis_overwritten(records):
    rec = records[uni.ARM_PIT]
    closes = {"2014-07-01": 100.0, "2014-08-01": 101.0}
    main = report.strategy_block([rec], closes, sensitivity=False)
    sens = report.strategy_block([rec], closes, sensitivity=True)
    assert main["price_basis"] == sens["price_basis"] == "KRX_BASEPRICE_CHAIN"
    assert sens["label_basis"] == "OFFICIAL_REFERENCE_SENSITIVITY"
    assert main["status"] == sens["status"] == "OK"
