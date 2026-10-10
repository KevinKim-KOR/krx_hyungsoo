"""POC5-06 — 가격 경계 · 연구 축 · D20 연구 모델(순수 계산 · tmp 자료).

설계 개정 2 §4 · §5 · §7 · §10-2 · §10-3 · §10-6. 시세 DB 는 쓰지 않고 행 목록으로 시험한다.
"""

from __future__ import annotations

import math
import random
import statistics
from datetime import date, timedelta

import pytest

from app.reentry_review import model
from app.reentry_review import models as M
from app.reentry_review import prices
from app.reentry_review.prices import FDR, NAVER, AxisSeries, PriceRow


def _weekdays(start: str, n: int) -> list[str]:
    d, out = date.fromisoformat(start), []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def _walk(n: int, seed: int = 7) -> list[float]:
    rnd, c, out = random.Random(seed), 10000.0, []
    for _ in range(n):
        c *= math.exp(rnd.gauss(0.0003, 0.012))
        out.append(round(c, 2))
    return out


def _rows(dates, closes, source=FDR) -> list[PriceRow]:
    out, prev = [], None
    for d, c in zip(dates, closes):
        change = None if prev is None else c / prev - 1.0
        out.append(PriceRow(d, c, source, "2026-10-05T00:00:00Z", change))
        prev = c
    return out


def _series(n=650, seed=7):
    dates = _weekdays("2023-01-02", n)
    return dates, AxisSeries(dates, _rows(dates, _walk(n, seed)))


# ── 목표 · feature ───────────────────────────────────────────────────────────


def test_d20_target_known_paths():
    c = [100.0] + [101, 99, 98.5, 102] + [103.0] * 16
    assert model.target_at(c, 0) == pytest.approx(-0.015)
    rising = [100.0 + k for k in range(21)]
    assert model.target_at(rising, 0) == 0.0  # 전 구간이 기준일보다 높으면 0
    c[20] = 90.0  # 20번째 날까지 본다
    assert model.target_at(c, 0) == pytest.approx(-0.10)


def test_features_known_series():
    c = [100.0 * 1.01**k for k in range(61)]
    f = model.features_at(c, 60)
    assert f[0] == pytest.approx(1.01**5 - 1)
    assert f[1] == pytest.approx(1.01**20 - 1)
    assert f[2] == pytest.approx(1.01**60 - 1)
    assert f[3] == pytest.approx(
        0.0, abs=1e-12
    )  # 일정한 로그수익률 → 모집단 표준편차 0
    assert f[4] == pytest.approx(0.0)  # 최근 60일 최고가 = 현재
    falling = [200.0 - k for k in range(61)]
    assert model.features_at(falling, 60)[4] == pytest.approx(140 / 199 - 1)


# ── 연구 축(§10-2) ───────────────────────────────────────────────────────────


def test_research_axis_file_year_and_kospi_corrected_year(tmp_path):
    caldir = tmp_path / "meta"
    caldir.mkdir()
    file_days = _weekdays("2025-01-02", 40)
    (caldir / "krx_trading_days_2025.csv").write_text(
        "date,source\n" + "".join(f"{d},TEST\n" for d in file_days), encoding="utf-8"
    )
    y2024 = _weekdays("2024-11-01", 30)
    holiday = y2024[10]  # 파일 없는 해 · KOSPI 저장 없음 → 축에서 건너뜀
    kospi = [d for d in y2024 if d != holiday] + [
        d for d in file_days if d != file_days[5]
    ]
    axis = prices.research_axis(file_days[-1], y2024[0], kospi, calendar_dir=caldir)
    assert holiday not in axis["dates"] and holiday in axis["skipped_weekdays"]
    assert file_days[5] in axis["dates"]  # 파일 있는 해는 KOSPI 누락이어도 파일 축
    assert axis["modes"] == {"2024": prices.MODE_KOSPI, "2025": prices.MODE_FILE}
    assert axis["label"] == prices.AXIS_LABEL
    assert prices.axis_problem(file_days[-1], axis) is None


def test_axis_uncertain_when_kospi_latest_is_earlier_than_t(tmp_path):
    days = _weekdays("2024-03-04", 80)
    kospi = days[:-3]  # 파일 없는 해 · KOSPI 저장이 t 보다 이르다
    axis = prices.research_axis(days[-1], days[0], kospi, calendar_dir=tmp_path)
    assert "KOSPI" in prices.axis_problem(days[-1], axis)
    full = prices.research_axis(days[-1], days[0], days, calendar_dir=tmp_path)
    assert prices.axis_problem(days[-1], full) is None
    assert prices.axis_problem("2024-03-09", full)  # 토요일 = 축에 없음


# ── 가격 경계(§10-3) ─────────────────────────────────────────────────────────


def test_detected_basis_boundaries_and_continuous_label_switch():
    dates = _weekdays("2024-01-01", 12)
    closes = [100.0 + k for k in range(12)]
    rows = _rows(dates, closes, NAVER)
    rows = [PriceRow(r.date, r.close, NAVER, r.fetched_at, None) for r in rows]
    # 2 → FDR(연속 change): 경계 아님
    rows[2] = PriceRow(dates[2], closes[2], FDR, "f", closes[2] / closes[1] - 1)
    # 4 → FDR · 0.5e-6 차이: 경계 아님 / 5 → 2e-6 차이: BASIS_BREAK
    rows[3] = PriceRow(dates[3], closes[3], FDR, "f", closes[3] / closes[2] - 1)
    rows[4] = PriceRow(
        dates[4], closes[4], FDR, "f", closes[4] / closes[3] - 1 + 0.5e-6
    )
    rows[5] = PriceRow(dates[5], closes[5], FDR, "f", closes[5] / closes[4] - 1 + 2e-6)
    rows[6] = PriceRow(dates[6], closes[6], FDR, "f", None)  # 첫 행 아님 · change 누락
    rows[7] = PriceRow(dates[7], closes[7], NAVER, "f", None)  # FDR → NAVER 재전환
    rows[8] = PriceRow(dates[8], closes[8], "YAHOO_FDR", "f", None)  # 허용 밖 출처
    rows[9] = PriceRow(dates[9], 0.0, NAVER, "f", None)  # 유한한 양수 아님
    s = AxisSeries(dates, rows)
    assert s.breaks == {
        5: prices.BASIS_BREAK,
        6: prices.CHANGE_MISSING,
        7: prices.SOURCE_RESWITCH,
    }
    assert (
        s.invalid[8] == prices.SOURCE_NOT_ALLOWED and s.invalid[9] == prices.BAD_CLOSE
    )
    assert s.window_ok(0, 4)  # 라벨 전환 · 허용 오차 안 차이는 이어서 쓴다
    assert not s.window_ok(4, 5) and s.window_reason(4, 5) == prices.BASIS_BREAK
    assert s.window_ok(5, 5)  # 경계는 날짜 '사이' — 그 날 하나는 쓸 수 있다
    assert s.window_reason(0, 11) == prices.SOURCE_NOT_ALLOWED  # 우선순위 순서
    first_fdr = AxisSeries(
        dates[:2],
        [
            PriceRow(dates[0], 1.0, FDR, "f", None),
            PriceRow(dates[1], 1.01, FDR, "f", 0.01),
        ],
    )
    assert first_fdr.breaks == {}  # 첫 가격 행의 change 누락은 경계가 아니다


def test_tolerance_is_absolute_ratio_not_percent():
    assert prices.CHANGE_TOLERANCE == 1e-6  # 0.0001%p — 퍼센트 단위와 섞지 않는다
    dates = _weekdays("2024-01-01", 3)
    rows = [
        PriceRow(dates[0], 100.0, FDR, "f", None),
        PriceRow(dates[1], 101.0, FDR, "f", 0.0100009),  # 0.9e-6 차이
        PriceRow(dates[2], 102.01, FDR, "f", 0.01 * 1.0002),  # 2e-6 차이
    ]
    assert AxisSeries(dates, rows).breaks == {2: prices.BASIS_BREAK}


# ── 검증 · 누수 · 기준(§5-2 · §10-6) ─────────────────────────────────────────


def test_evaluate_ok_validation_contract():
    dates, s = _series()
    r = model.evaluate(s, dates[-1])
    assert r["status"] == M.OK and r["reason"] is None
    T = len(dates) - 1
    assert [b["axis_dates"] for b in r["blocks"]] == [63, 63, 63]
    assert r["blocks"][-1]["last_date"] == dates[T - 20]  # 검증 끝 = t 의 20일 전
    for b in r["blocks"]:
        assert b["train_n"] >= model.MIN_TRAIN and b["valid_n"] == 63
        assert b["train_last_eval_end"] < b["first_date"]  # 정답 종료일 < 구간 시작
    assert r["overall"]["n"] == 189
    weighted = sum(b["mae_model_pp"] * b["valid_n"] for b in r["blocks"]) / 189
    assert r["overall"]["mae_model_pp"] == pytest.approx(weighted)  # 전체 = 표본별 평균
    assert r["final"]["train_last"] == dates[T - 20]  # t 까지 성숙한 표본만
    assert -100.0 <= r["final"]["estimate_pct"] <= 0.0


def test_baseline_is_training_median_and_same_dates(monkeypatch):
    dates, s = _series()
    T = len(dates) - 1
    r = model.evaluate(s, dates[-1])
    first = T - 20 - 189 + 1
    valid = [i for i in range(60, T - 19) if s.window_ok(i - 60, i + 20)]
    ys = {i: model.target_at(s.closes, i) for i in valid}
    for b in range(3):
        start = first + b * 63
        train = [ys[i] for i in valid if i + 20 < start]
        assert r["blocks"][b]["baseline_median_pct"] == pytest.approx(
            statistics.median(train) * 100
        )
        val = [ys[i] for i in range(start, start + 63)]
        base_mae = sum(abs(statistics.median(train) - y) for y in val) * 100 / 63
        assert r["blocks"][b]["mae_baseline_pp"] == pytest.approx(base_mae)


def test_no_future_leakage_into_training_or_scaler(monkeypatch):
    dates, s = _series()
    seen: list = []
    real = model.fit_predict

    def spy(tx, ty, test_x):
        seen.append((tuple(map(tuple, tx)), tuple(ty)))  # 학습 입력 · 정답 전부
        return real(tx, ty, test_x)

    monkeypatch.setattr(model, "fit_predict", spy)
    model.evaluate(s, dates[-1])
    first_run = list(seen)
    assert len(first_run) == 4  # 세 구간 + 최종
    # 구간 b 시작 뒤의 가격만 바꾼다 → 구간 1..b 의 학습 입력 · 정답은 그대로(세 구간 모두)
    T = len(dates) - 1
    start1 = T - 20 - 189 + 1
    for b in range(3):
        start = start1 + b * 63
        moved = [c if k < start else c * 1.5 for k, c in enumerate(s.closes)]
        rows = _rows(dates, moved)  # change 도 바꾼 종가로 계산(경계 없음)
        seen.clear()
        model.evaluate(AxisSeries(dates, rows), dates[-1])
        assert seen[: b + 1] == first_run[: b + 1]
        # 최종 fit 은 뒤 가격을 쓴다(시험이 실제로 가격을 바꿨다)
        assert seen[3] != first_run[3]

    from sklearn.preprocessing import StandardScaler

    fitted: list[int] = []
    orig_fit = StandardScaler.fit

    def fit_spy(self, X, y=None, sample_weight=None):
        fitted.append(len(X))
        return orig_fit(self, X, y, sample_weight)

    monkeypatch.setattr(StandardScaler, "fit", fit_spy)
    r = model.evaluate(s, dates[-1])
    assert fitted == [b["train_n"] for b in r["blocks"]] + [r["final"]["train_n"]]


def test_overall_mae_pools_unequal_blocks_on_same_dates():
    """구간마다 유효 검증 날짜 수가 달라도 전체 = 표본별 평균 · 모델과 기준은 같은 날짜(§10-6)."""
    dates = _weekdays("2023-01-02", 650)
    rows = _rows(dates, _walk(650))
    T = len(dates) - 1
    first = T - 20 - 189 + 1
    k = first + 63 + 30  # 구간 2 안의 경계 하나 → 구간 2 · 3 의 일부 날짜 제외
    r = rows[k]
    rows[k] = PriceRow(r.date, r.close, FDR, r.fetched_at, r.change + 0.01)
    s = AxisSeries(dates, rows)
    out = model.evaluate(s, dates[-1])
    assert out["status"] == M.OK
    ns = [b["valid_n"] for b in out["blocks"]]
    assert len(set(ns)) > 1 and sum(ns) == out["overall"]["n"]
    valid = [i for i in range(60, T - 19) if s.window_ok(i - 60, i + 20)]
    ys = {i: model.target_at(s.closes, i) for i in valid}
    errs_m: list[float] = []
    errs_b: list[float] = []
    for b in range(3):
        start = first + b * 63
        val = [i for i in range(start, start + 63) if i in ys]
        train = [i for i in valid if i + 20 < start]
        assert out["blocks"][b]["valid_n"] == len(val)
        med = statistics.median([ys[i] for i in train])
        pred = model.fit_predict(
            [model.features_at(s.closes, i) for i in train],
            [ys[i] for i in train],
            [model.features_at(s.closes, i) for i in val],
        )
        errs_m += [abs(p - ys[i]) * 100 for p, i in zip(pred, val)]
        errs_b += [abs(med - ys[i]) * 100 for i in val]
    ov = out["overall"]
    assert ov["mae_model_pp"] == pytest.approx(sum(errs_m) / len(errs_m))
    assert ov["mae_baseline_pp"] == pytest.approx(sum(errs_b) / len(errs_b))
    mean_of_means = sum(b["mae_model_pp"] for b in out["blocks"]) / 3
    # 이 자료에서 두 방식(표본별 평균 · 구간 평균의 평균)이 갈린다
    assert abs(ov["mae_model_pp"] - mean_of_means) > 1e-6


def test_predictions_are_clipped_to_minus_one_and_zero():
    tx = [[float(i)] for i in range(30)]
    ty = [-0.01 * i for i in range(30)]
    low, high, mid = model.fit_predict(tx, ty, [[500.0], [-500.0], [10.0]])
    assert (low, high) == (-1.0, 0.0)
    assert -1.0 < mid < 0.0


def test_short_history_is_data_short_without_estimate():
    dates, s = _series(n=400)
    r = model.evaluate(s, dates[-1])
    assert r["status"] == M.DATA_SHORT
    assert "final" not in r and "overall" not in r
    assert any(b["status"] == M.DATA_SHORT for b in r["blocks"])
    assert r["features_at_t"] is not None  # 최근 가격 상태는 계산된다


def test_broken_t_feature_window_is_price_basis_unconfirmed():
    dates = _weekdays("2023-01-02", 650)
    rows = _rows(dates, _walk(650))
    k = len(rows) - 10
    r = rows[k]
    rows[k] = PriceRow(r.date, r.close, FDR, r.fetched_at, r.change + 0.01)
    out = model.evaluate(AxisSeries(dates, rows), dates[-1])
    assert out["status"] == M.PRICE_BASIS_UNCONFIRMED
    assert out["features_at_t"] is None and "final" not in out
    assert out["samples"]["excluded_by_reason"].get(prices.BASIS_BREAK)


def test_axis_gap_in_t_window_is_price_basis_unconfirmed_with_all_reasons():
    """기준일 feature 창의 축 공백도 경계(§4 · §10-3) — 자료 부족으로 숨기지 않고 사유를 모두 적는다."""
    dates = _weekdays("2023-01-02", 650)
    rows = _rows(dates, _walk(650))
    k = len(rows) - 10
    r = rows[k]
    rows[k] = PriceRow(r.date, r.close, FDR, r.fetched_at, r.change + 0.01)
    del rows[len(rows) - 30]  # 축 날짜 하나의 저장 종가 없음
    out = model.evaluate(AxisSeries(dates, rows), dates[-1])
    assert out["status"] == M.PRICE_BASIS_UNCONFIRMED and out["features_at_t"] is None
    assert prices.REASON_TEXT[prices.MISSING_PRICE] in out["reason"]
    assert prices.REASON_TEXT[prices.BASIS_BREAK] in out["reason"]
    assert "MISSING_PRICE" not in out["reason"]  # 화면 문구에 내부 코드 없음


def test_axis_shorter_than_feature_window_is_data_short():
    dates, s = _series(n=50)
    out = model.evaluate(s, dates[-1])
    assert out["status"] == M.DATA_SHORT and "61일 미만" in out["reason"]
    assert out["features_at_t"] is None and "final" not in out


def test_verdict_uses_two_decimal_pp():
    assert model.verdict(4.30, 4.33) == M.IMPROVED
    assert model.verdict(4.331, 4.334) == M.NO_DIFFERENCE
    assert model.verdict(4.371, 4.329) == M.WORSE


def test_same_snapshot_same_result():
    dates, s = _series()
    assert model.evaluate(s, dates[-1]) == model.evaluate(s, dates[-1])
