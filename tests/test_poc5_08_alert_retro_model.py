"""POC5-08 — +5 고정 Ridge 시간 분리 검증 단위 시험(합성 관측 · tmp 캘린더 · 라이브 0).

설계 §5 · §6 · PLAN §2-2 · §2-6 · §3(모델 비교 · 시간 누출).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from fractions import Fraction

import pytest

from app.alert_retro import features as F
from app.alert_retro import model
from app.ledger_reports import dates

KST = timezone(timedelta(hours=9))
UTC = timezone.utc


@pytest.fixture
def cal(tmp_path):
    d = tmp_path / "market_meta"
    d.mkdir()
    days, x = [], date(2026, 1, 1)
    while x.year == 2026:
        if x.weekday() < 5 and x.isoformat() not in ("2026-10-09", "2026-10-05"):
            days.append(x.isoformat())
        x += timedelta(days=1)
    (d / "krx_trading_days_2026.csv").write_text(
        "date,source\n" + "\n".join(f"{v},TEST" for v in days) + "\n", encoding="utf-8"
    )
    return dates.calendar(d)


def _obs(day, series, y, *, seq=1, ret20=None, day_ret=None, cat=None, cal=None):
    """09:15 사건 · +5 평가일 = 사건일 포함 5번째 거래일 · computed_at = 다음 거래일 08:10 KST."""
    ev = cal.days_from(day, 5)[-1]
    nxt = cal.next_after(ev)
    cats = {n: "NONE" for n in F.CATEGORICAL}
    cats.update(cat or {})
    return {
        "event_id": f"ev_{day}_{series}_{seq}",
        "item_seq": seq,
        "slot": 1,
        "series_id": series,
        "signal_date": day,
        "runtime": datetime.fromisoformat(f"{day}T09:15:00+09:00"),
        "eval_date": ev,
        "computed": datetime.fromisoformat(f"{nxt}T08:10:00+09:00").astimezone(UTC),
        "y": y,
        "num": {"return_20d": ret20, "day_return": day_ret},
        "cat": cats,
        "group": "holdings_risk_alert/sector",
    }


def _signal(cal, start, end, *, noise=0.0):
    """매 거래일 series 2개 · y = 0.5 × 20일 변화 (+ 작은 흔들림)."""
    out = []
    for i, d in enumerate(dates.trading_days(cal, start, end)):
        for j, s in enumerate(("krx_etf:A", "krx_etf:B")):
            r20 = ((i * 7 + j * 3) % 11 - 5) / 100.0
            out.append(
                _obs(
                    d,
                    s,
                    0.5 * r20 + (noise if (i + j) % 2 else -noise),
                    ret20=r20,
                    cat={"push_kind": "holdings_risk_alert", "subject_kind": "sector"},
                    cal=cal,
                )
            )
    return out


# ── 가중치 · 가중 중앙값 ─────────────────────────────────────────────────────


def test_weights_balance_dates_and_series_repeats():
    rows = [
        {"signal_date": "d1", "series_id": "A"},
        {"signal_date": "d1", "series_id": "A"},
        {"signal_date": "d1", "series_id": "A"},
        {"signal_date": "d1", "series_id": "B"},
        {"signal_date": "d2", "series_id": "A"},
    ]
    w = model.weights(rows)
    assert w == [Fraction(1, 6)] * 3 + [Fraction(1, 2), Fraction(1, 1)]
    assert sum(w[:4]) == 1 and w[4] == 1  # 날짜 합 1


def test_weighted_median_first_value_reaching_half():
    assert model.weighted_median([3.0, 1.0, 2.0], [Fraction(1, 4)] * 2 + [1]) == 2.0
    # 누적 정확히 절반에 닿는 첫 값(분수라 부동소수 오차 없음)
    assert model.weighted_median([1.0, 2.0], [Fraction(1, 2), Fraction(1, 2)]) == 1.0
    assert (
        model.weighted_median(
            [5.0, 1.0, 2.0], [Fraction(1, 3), Fraction(1, 3), Fraction(1, 3)]
        )
        == 2.0
    )


# ── 전처리(학습 구간만 fit) ──────────────────────────────────────────────────


def _row(ret20, day_ret, state="A"):
    cats = {n: "NONE" for n in F.CATEGORICAL}
    cats["state"] = state
    return {"num": {"return_20d": ret20, "day_return": day_ret}, "cat": cats}


def test_prep_missing_indicator_impute_constant_and_unseen():
    train = [_row(0.1, None), _row(0.3, None), _row(None, None, "B")]
    w = [Fraction(1, 2), Fraction(1, 2), Fraction(1, 1)]
    prep = model.Prep(train, w)
    assert prep.fill["return_20d"] == 0.1  # 유효값 가중 중앙값
    assert prep.fill["day_return"] == 0.0  # 유효값 없음 → 0
    assert prep.std["day_return"] is None  # 값이 모두 같다 → 0 열
    x, unseen = prep.transform([_row(None, 0.5, "Z")])
    cols = prep.columns()
    assert x[0, cols.index("return_20d_missing")] == 1.0
    assert x[0, cols.index("day_return")] == 0.0
    assert x[0, cols.index("day_return_missing")] == 0.0
    assert [x[0, cols.index(f"state={v}")] for v in ("A", "B")] == [0.0, 0.0]
    assert unseen == {"state": 1}
    # 학습 행: 대입값으로 표준화 · 가중 평균 0
    xt, _ = prep.transform(train)
    col = cols.index("return_20d")
    wsum = sum(float(v) for v in w)
    assert abs(sum(float(wi) * xt[i, col] for i, wi in enumerate(w)) / wsum) < 1e-12


def test_prep_is_unchanged_by_test_rows():
    train = [_row(0.1, 0.02), _row(-0.2, 0.01), _row(0.05, None)]
    w = [Fraction(1, 3)] * 3
    a = model.Prep(train, w)
    b = model.Prep(train, w)
    a.transform([_row(9.0, 9.0, "NEW")])  # 시험 값이 변환을 바꾸지 않는다
    assert (a.fill, a.mean, a.std, a.vocab) == (b.fill, b.mean, b.std, b.vocab)


# ── 구간 ─────────────────────────────────────────────────────────────────────


def test_window_anchor_is_five_trading_days_before_end(cal):
    blocks = model.window(cal, "2026-10-13")
    # 5거래일 전 = 10-12 · 10-08 · 10-07 · 10-06 · 10-02(10-05 · 10-09 휴장) → anchor = 10-02
    assert blocks[-1][-1] == "2026-10-02"
    assert [len(b) for b in blocks] == [5, 5, 5]
    flat = [d for b in blocks for d in b]
    assert flat == dates.trading_days(cal, flat[0], flat[-1])


# ── 검증 ─────────────────────────────────────────────────────────────────────


def test_full_three_block_comparison_and_mae_consistency(cal):
    obs = _signal(cal, "2026-07-01", "2026-10-13", noise=0.002)
    got = model.evaluate(obs, cal, "2026-10-20")
    assert got["status"] == "COMPARED"
    assert all(b["status"] == "VALID" for b in got["blocks"])
    ov = got["overall"]
    assert ov["model_mae"] < ov["baseline_mae"] and ov["verdict"] == "IMPROVED"
    assert ov["verdict_text"] == "개선"
    for b in got["blocks"]:
        assert b["train_dates"] >= model.MIN_TRAIN_DATES
        test = [o for o in obs if o["signal_date"] in b["days"]]
        assert b["test_rows"] == len(test) and b["test_dates"] == 5
        # 항목별 오차와 가중치로 날짜 MAE 를 다시 계산하면 구간 값과 같다
        w = model.weights(test)
        per = {}
        for o, wi in zip(test, w):
            r = got["rows"][(o["event_id"], o["item_seq"], o["slot"])]
            assert r["block"] == b["index"]
            per[o["signal_date"]] = per.get(o["signal_date"], 0.0) + float(wi) * abs(
                o["y"] - r["estimate_raw"]
            )
        assert abs(sum(per.values()) / len(per) - b["model_mae"]) < 1e-12
        # 단순 기준 = 학습 표본 가중 중앙값
        train = [
            o
            for o in obs
            if o["signal_date"] < b["start"]
            and o["computed"] < datetime.fromisoformat(b["test_start"])
        ]
        assert b["baseline_value"] == model.weighted_median(
            [o["y"] for o in train], model.weights(train)
        )
    errs = [e[0] for b in got["blocks"] for e in b["date_errors"].values()]
    assert abs(sum(errs) / len(errs) - ov["model_mae"]) < 1e-12


def test_same_input_is_deterministic(cal):
    obs = _signal(cal, "2026-07-01", "2026-10-13", noise=0.003)
    a = model.evaluate(obs, cal, "2026-10-20")
    b = model.evaluate(list(obs), cal, "2026-10-20")
    assert a == b


def test_partial_window_is_block_diagnosis_only(cal):
    # 첫 구간 앞 신호일 23일 중 결과가 시험 시작 전에 계산된 날 = 19일 → 1구간 DATA_SHORT
    window = model.window(cal, "2026-10-20")
    start = cal._walk_back(window[0][0], 23)[-1]
    obs = _signal(cal, start, "2026-10-13")
    got = model.evaluate(obs, cal, "2026-10-20")
    assert got["status"] == "DATA_SHORT" and got["overall"] is None
    first = got["blocks"][0]
    assert first["status"] == "DATA_SHORT" and first["reason"] == "학습 신호일 19 < 20"
    assert [b["status"] for b in got["blocks"][1:]] == ["VALID", "VALID"]
    some = next(o for o in obs if o["signal_date"] == window[0][0])
    assert got["rows"][(some["event_id"], 1, 1)] == {"status": "DATA_SHORT", "block": 1}


def test_no_test_rows_is_data_short(cal):
    obs = _signal(cal, "2026-07-01", "2026-09-01")
    got = model.evaluate(obs, cal, "2026-10-20")
    assert [b["reason"] for b in got["blocks"]] == ["시험 행 없음"] * 3


def test_late_computed_label_and_close_time_are_excluded_from_training(cal):
    obs = _signal(cal, "2026-07-01", "2026-10-13", noise=0.002)
    base = model.evaluate(obs, cal, "2026-10-20")
    b1 = base["blocks"][0]
    test_start = datetime.fromisoformat(b1["test_start"])
    # 1구간 시작 전 신호지만 결과가 시험 시작 뒤에 계산된 과거 라벨(크게 다른 값)
    late = _obs(cal._walk_back(b1["start"], 30)[-1], "krx_etf:C", 5.0, cal=cal)
    late["computed"] = test_start + timedelta(seconds=1)
    # 평가일 종가(15:30)가 시험 시작보다 늦은 행
    close_late = _obs(cal._walk_back(b1["start"], 1)[0], "krx_etf:D", -5.0, cal=cal)
    close_late["computed"] = test_start - timedelta(days=30)
    assert model.at_kst(close_late["eval_date"], "15:30") > test_start
    got = model.evaluate([*obs, late, close_late], cal, "2026-10-20")
    g1 = got["blocks"][0]
    assert g1["train_rows"] == b1["train_rows"]
    assert g1["train_excluded_by_time"] == b1["train_excluded_by_time"] + 2
    assert g1["model_mae"] == b1["model_mae"] and g1["baseline_value"] == (
        b1["baseline_value"]
    )


def test_test_start_is_earliest_runtime_and_uses_timezones(cal):
    obs = _signal(cal, "2026-07-01", "2026-10-13")
    b1 = model.evaluate(obs, cal, "2026-10-20")["blocks"][0]
    assert b1["test_start"] == f"{b1['start']}T09:15:00+09:00"
    # computed_at 이 UTC 표기라도 시각으로 비교된다(시험 시작 1초 전 = 학습 포함)
    edge = _obs(cal._walk_back(b1["start"], 40)[-1], "krx_etf:E", 0.0, cal=cal)
    edge["computed"] = datetime.fromisoformat(b1["test_start"]).astimezone(
        UTC
    ) - timedelta(seconds=1)
    got = model.evaluate([*obs, edge], cal, "2026-10-20")["blocks"][0]
    assert got["train_rows"] == b1["train_rows"] + 1


def test_prediction_floor_minus_one_without_clipping_labels(cal):
    obs = _signal(cal, "2026-07-01", "2026-10-13")
    for o in obs:  # 20일 변화가 크게 음수면 추정이 -1 아래로 내려가는 자료
        o["y"] = 30.0 * o["num"]["return_20d"]
    window = model.window(cal, "2026-10-20")
    for o in obs:
        if o["signal_date"] in window[2]:
            o["num"]["return_20d"] = -1.0
            o["y"] = -0.95
    got = model.evaluate(obs, cal, "2026-10-20")
    rows = [r for r in got["rows"].values() if r["block"] == 3]
    assert rows and all(r["estimate_raw"] == -1.0 for r in rows)
    assert all(r["actual_raw"] == -0.95 for r in rows)


def test_unseen_category_is_counted(cal):
    obs = _signal(cal, "2026-07-01", "2026-10-13")
    window = model.window(cal, "2026-10-20")
    for o in obs:
        if o["signal_date"] in window[1]:
            o["cat"]["state"] = "NEW_STATE"
    got = model.evaluate(obs, cal, "2026-10-20")
    assert got["blocks"][1]["unseen_categories"] == {"state": 10}
    assert got["blocks"][0]["unseen_categories"] == {}


def test_pp_is_two_decimal_percent_points():
    assert model.pp(0.5) == 50.0 and model.pp(-0.0123) == -1.23
    assert model.pp(0.012345) == 1.23


def test_verdict_uses_displayed_two_decimals_not_raw():
    assert model.verdict_of(0.024001, 0.024004) == "NO_DIFFERENCE"  # 둘 다 2.40%p
    assert model.verdict_of(0.0239, 0.0241) == "IMPROVED"
    assert model.verdict_of(0.0262, 0.0261) == "WORSE"


def test_test_rows_need_plus5_eval_date_on_or_before_end(cal):
    obs = _signal(cal, "2026-07-01", "2026-10-13")
    base = model.evaluate(obs, cal, "2026-10-20")
    window = model.window(cal, "2026-10-20")
    late = _obs(window[2][-1], "krx_etf:Z", 0.4, cal=cal)
    late["eval_date"] = "2026-10-21"  # 종료일 뒤 평가일 — 시험 행 아님
    got = model.evaluate([*obs, late], cal, "2026-10-20")
    assert got["blocks"][2]["test_rows"] == base["blocks"][2]["test_rows"]
    assert (late["event_id"], 1, 1) not in got["rows"]
    assert got["overall"] == base["overall"]


# ── ML 대상 범위(features) ───────────────────────────────────────────────────


def _item(basis="KRX_ETF_UNADJUSTED|ETF", contract="holdings_risk_alert.v1", **kw):
    slot = {
        "horizon": 5,
        "status": "MATURED",
        "return_raw": 0.01,
        "eval_date": "2026-10-16",
        "price_basis": basis,
        "series_id": "krx_etf:1",
        "computed_at": "2026-10-19T00:00:00+00:00",
    }
    item = {
        "event_id": "E",
        "item_seq": 1,
        "signal_date": "2026-10-12",
        "runtime_kst": "2026-10-12T09:30:01+09:00",
        "push_kind": "holdings_risk_alert",
        "subject_kind": "ticker",
        "contract_version": contract,
        "numeric": {"return_20d": None, "day_return": 0.01},
        "held": 1,
        "state": None,
        "event_type": None,
        "exposure": None,
        "slots": [slot],
    }
    item.update(kw)
    return item


@pytest.mark.parametrize(
    "basis, reason",
    [
        ("KRX_ETF_UNADJUSTED|ETF", None),
        ("KRX_STOCK_UNADJUSTED|STOCK", None),
        ("KRX_ETF_UNADJUSTED", None),  # 사업군 대표 ETF(접미 없음)
        ("KRX_ETF_UNADJUSTED_V2|ETF", "UNSUPPORTED_PRICE_BASIS"),  # 앞부분만 같음
        ("KRX_KOSPI_INDEX", "UNSUPPORTED_PRICE_BASIS"),
        (None, "UNSUPPORTED_PRICE_BASIS"),
    ],
)
def test_price_basis_base_must_match_exactly(basis, reason):
    obs, reasons = F.observations([_item(basis=basis)])
    assert (len(obs), list(reasons.values())) == (
        (1, []) if reason is None else (0, [reason])
    )


def test_unsupported_contract_version_is_not_ml_target():
    obs, reasons = F.observations([_item(contract="holdings_risk_alert.v2")])
    assert obs == [] and list(reasons.values()) == ["UNSUPPORTED_CONTRACT"]


def test_numeric_transform_is_fit_on_training_rows_only(cal):
    """시험 행의 숫자 · 범주가 크게 바뀌어도 그 구간의 대입값 · 평균 · 표준편차 · 사전 · 기준은 같다."""
    obs = _signal(cal, "2026-07-01", "2026-10-13")
    window = model.window(cal, "2026-10-20")
    base = model.evaluate(obs, cal, "2026-10-20")["blocks"][0]
    for o in obs:
        if o["signal_date"] in window[0]:
            o["num"] = {"return_20d": 50.0, "day_return": None}
            o["cat"]["state"] = "FUTURE_ONLY"
    got = model.evaluate(obs, cal, "2026-10-20")["blocks"][0]
    assert got["numeric_fit"] == base["numeric_fit"]
    assert got["vocab_sizes"] == base["vocab_sizes"]
    assert got["baseline_value"] == base["baseline_value"]
    assert got["model_mae"] != base["model_mae"]  # 시험 입력은 실제로 바뀌었다
