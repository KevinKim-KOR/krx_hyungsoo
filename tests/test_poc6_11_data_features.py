"""POC6-11 자료 · 자격 · 30열 · 정답 · 학습 표본 — 설계 §9 격리 확인(자료 쪽) · 판정 §5 · §6.

tmp_path 의 봉인 스키마 DB(`tests/_krx_fixture`)와 직접 만든 행렬만 쓴다. 봉인 DB · 라이브 DB 는 열지 않는다.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from app.weekly_selection import data as D
from app.weekly_selection import features as F
from tests._krx_fixture import build_sealed_db, krx_row, rows_by_date, trading_dates


def _iso(d: str) -> str:
    return f"{d[:4]}-{d[4:6]}-{d[6:]}"


def _series(
    code,
    days,
    closes,
    *,
    vols=None,
    name=None,
    opens=None,
    base_shift=None,
    at_low=False,
):
    """KRX 행. base_shift = {k: 기준가 차이} — 그날 대비를 바꿔 연결값이 종가와 달라지게(분배 흉내)."""
    out, prev = {}, None
    for k, (d, c) in enumerate(zip(days, closes)):
        v = vols[k] if vols is not None else 20000
        cmp = None
        if prev is not None and base_shift and k in base_shift:
            cmp = c - (prev - base_shift[k])
        row = krx_row(
            code, d, c, prev, volume=v, name=name or f"TEST {code}", cmpprev=cmp
        )
        o = opens[k] if opens is not None else c
        row.update(
            TDD_OPNPRC=f"{o:g}",
            TDD_HGPRC=f"{max(o, c) + 10:g}",
            TDD_LWPRC=f"{min(o, c) - (0 if at_low else 10):g}",
        )
        if v == 0 and opens is not None and o == 0:
            row.update(TDD_OPNPRC="0", TDD_HGPRC="0", TDD_LWPRC="0")
        out[d] = row
        prev = c
    return out


def _db(tmp_path, maps, name="krx.sqlite"):
    path = tmp_path / name
    sha = build_sealed_db(path, rows_by_date(*maps))
    return path, sha


def test_build_panel_synthetic_ohlc_and_exec(tmp_path):
    days = trading_dates(8)
    closes = [10000, 10100, 10200, 10300, 10400, 10500, 10600, 10700]
    opens = [10000, 10050, 10150, 10250, 10350, 10450, 0, 10650]
    vols = [20000, 20000, 20000, 20000, 20000, 20000, 0, 20000]
    a = _series("069500", days, closes, name="KODEX 200")
    b = _series("111111", days, closes, vols=vols, opens=opens, base_shift={3: 200})
    path, sha = _db(tmp_path, [a, b])
    p = D.build_panel(path, "krx_etf_universe_v1", sha)
    j = p.ci["111111"]
    # 4번째 날 기준가가 200 낮아 연결값이 종가보다 높아진다 → O* = O × I/C
    assert p.I[j, 5] != p.C[j, 5]
    assert p.O[j, 5] == pytest.approx(opens[5] * p.I[j, 5] / p.C[j, 5], rel=1e-15)
    assert p.H[j, 5] == pytest.approx(
        (max(opens[5], closes[5]) + 10) * p.I[j, 5] / p.C[j, 5], rel=1e-15
    )
    assert (
        p.exec_ok[j, 5] and not p.exec_ok[j, 6]
    )  # 무거래(거래량 0 · 시가 0) = 체결 불가
    assert p.raw_open[j, 6] == 0 and p.V[j, 6] == 0 and np.isfinite(p.I[j, 6])


def test_nonfinite_raw_value_is_check_required(tmp_path):
    days = trading_dates(4)
    a = _series("069500", days, [100, 101, 102, 103], name="KODEX 200")
    b = _series("111111", days, [100, 101, 102, 103])
    b[days[2]]["TDD_OPNPRC"] = "nan"
    path, sha = _db(tmp_path, [a, b])
    with pytest.raises(D.CheckRequired):
        D.build_panel(path, "krx_etf_universe_v1", sha)


def test_weekly_signals_drop_incomplete_last_week():
    axis = ["2020-01-06", "2020-01-07", "2020-01-10", "2020-01-13", "2020-01-14"]
    assert D.weekly_signals(axis) == [
        2
    ]  # 01-10(금) · 마지막 주(13 · 14)는 다음 날이 없어 신호 아님


def _eligibility_db(tmp_path):
    n = 160
    days = trading_dates(n)
    t = n - 1 - 3  # 신호 후보(뒤 3일은 미래)
    base = [10000] * n
    hi = 20000  # 10000 × 20000 = 2e8 ≥ 1e8
    maps = [_series("069500", days, base, name="KODEX 200")]
    maps.append(_series("100001", days, base, name="TEST OK"))
    maps.append(_series("100002", days, base, name="TEST 인버스"))
    # t = n − 4 에서 연속 125행(t−124 부터) · 126행(t−125 부터)
    maps.append(_series("100003", days[t - 124 :], base[: n - t + 124]))  # noqa: E203
    maps.append(_series("100004", days[t - 125 :], base[: n - t + 125]))  # noqa: E203
    # 유동성 창 t−19..t: t−20 하루만 크면 탈락 · t 하루만 크면 통과
    v5 = [1] * n
    v5[t - 20] = 20 * hi * 2
    maps.append(_series("100005", days, base, vols=v5))
    v6 = [1] * n
    v6[t] = 20 * hi * 2
    maps.append(_series("100006", days, base, vols=v6))
    # 정상 저장 0 포함: 19일 × 1.04e8 + 0 → 평균 0.988e8 < 1e8(0 을 건너뛰면 통과했을 값)
    v7 = [10400] * n
    v7[t - 3] = 0
    maps.append(_series("100007", days, base, vols=v7))
    v8 = [hi] * n
    v8[t] = 0
    maps.append(_series("100008", days, base, vols=v8))
    path, sha = _db(tmp_path, maps)
    return path, sha, t


def test_eligibility_reasons_and_window_boundaries(tmp_path):
    path, sha, t = _eligibility_db(tmp_path)
    p = D.build_panel(path, "krx_etf_universe_v1", sha)
    el = D.eligibility(p, [t])
    got = {p.codes[j] for j in el.members[t]}
    assert got == {"069500", "100001", "100004", "100006"}
    ex = {k: {p.codes[j] for j in v} for k, v in el.excluded[t].items()}
    assert ex == {
        "name": {"100002"},
        "run126": {"100003"},
        "liquidity": {"100005", "100007"},
        "vol0": {"100008"},
    }


def test_future_rows_do_not_change_past_eligibility(tmp_path):
    path, sha, t = _eligibility_db(tmp_path)
    p = D.build_panel(path, "krx_etf_universe_v1", sha)
    el = D.eligibility(p, [t])
    p.V[:, t + 1 :] = 0.0  # noqa: E203 — 미래 거래량 · 가격을 망가뜨려도
    p.I[:, t + 1 :] = 1.0  # noqa: E203
    p.C[:, t + 1 :] = 1.0  # noqa: E203
    assert D.eligibility(p, [t]).members == el.members


# ── 직접 만든 행렬(30열 · 정답) ────────────────────────────────────────────────────


def _panel(closes: dict, *, vols=None, opens=None, seg=None, n=None):
    codes = sorted(closes)
    n = n or len(next(iter(closes.values())))
    axis = [f"2020-{1 + k // 28:02d}-{1 + k % 28:02d}" for k in range(n)]
    I = np.array([closes[c] for c in codes], dtype=float)  # noqa: E741
    V = np.array(
        [vols[c] if vols and c in vols else [1000.0] * n for c in codes], dtype=float
    )
    O = np.array(  # noqa: E741
        [opens[c] if opens and c in opens else closes[c] for c in codes], dtype=float
    )
    H, L = np.maximum(O, I) * 1.01, np.minimum(O, I) * 0.99
    has = np.isfinite(I)
    sg = np.array(
        [seg[c] if seg and c in seg else [0] * n for c in codes], dtype=np.int32
    )
    return D.Panel(
        axis=axis,
        codes=codes,
        I=I,
        O=O,
        H=H,
        L=L,
        C=I.copy(),
        V=V,
        raw_open=O.copy(),
        raw_high=H.copy(),
        raw_low=L.copy(),
        seg=sg,
        has_row=has,
        exec_ok=has & (V > 0) & (O > 0),
    )


def test_feature_row_hand_calc():
    n = 130
    rng = np.random.default_rng(1)
    c = list(100 * np.cumprod(1 + rng.normal(0, 0.01, n)))
    v = list(rng.integers(100, 1000, n).astype(float))
    p = _panel({"069500": c, "111111": c}, vols={"111111": v})
    j, i = p.ci["111111"], 125
    vals, why = F.feature_row(p, j, i)
    got = dict(zip(F.COLUMNS, vals))
    I, V = np.array(c), np.array(v)  # noqa: E741
    for w in F.WINDOWS:
        assert got[f"RET_{w}"] == pytest.approx(I[i] / I[i - w] - 1, rel=1e-12)
        assert got[f"MA_GAP_{w}"] == pytest.approx(
            I[i] / I[i - w + 1 : i + 1].mean() - 1, rel=1e-12  # noqa: E203
        )
        rets = I[i - w + 1 : i + 1] / I[i - w : i] - 1  # noqa: E203
        assert got[f"RETURN_STD_{w}"] == pytest.approx(np.std(rets), rel=1e-12)
        assert got[f"CLOSE_PEAK_GAP_{w}"] == pytest.approx(
            I[i] / I[i - w + 1 : i + 1].max() - 1  # noqa: E203
        )
        # 거래량 배수 = 당일 / 직전 w 일 평균(당일 제외) · 변동계수 = 당일 포함 w 일
        assert got[f"VOLUME_RATIO_{w}"] == pytest.approx(
            V[i] / V[i - w : i].mean(), rel=1e-12  # noqa: E203
        )
        win = V[i - w + 1 : i + 1]  # noqa: E203
        assert got[f"VOLUME_CV_{w}"] == pytest.approx(
            np.std(win) / win.mean(), rel=1e-12
        )
    o, h, lo, prev = p.O[j, i], p.H[j, i], p.L[j, i], I[i - 1]
    assert got["OPEN_GAP"] == pytest.approx(o / prev - 1)
    assert got["CLOSE_POS"] == pytest.approx((I[i] - lo) / (h - lo))
    assert got["LOWER_SHADOW"] == pytest.approx((min(o, I[i]) - lo) / prev)
    assert why == {}
    assert len(vals) == 30 and F.COLUMNS[:6] == (
        "RET_5",
        "MA_GAP_5",
        "RETURN_STD_5",
        "CLOSE_PEAK_GAP_5",
        "VOLUME_RATIO_5",
        "VOLUME_CV_5",
    )


def test_feature_missing_reasons_and_damage():
    n = 130
    c = [100.0 + k for k in range(n)]
    v = [1000.0] * n
    for k in range(120, 125):
        v[k] = 0.0  # 직전 5일 거래량 0 → VOLUME_RATIO_5 분모 0
    p = _panel({"069500": c, "111111": c}, vols={"111111": v})
    j, i = p.ci["111111"], 125
    vals, why = F.feature_row(p, j, i)
    assert (
        why["VOLUME_RATIO_5"] == "DIV0"
        and vals[F.COLUMNS.index("VOLUME_RATIO_5")] is None
    )
    # 거래량 0 · 원시 시가 0 = 알려진 무거래 → 봉 6열 결측(NO_TRADE) · 가격 손상과 구분
    p.V[j, i], p.raw_open[j, i] = 0.0, 0.0
    vals, why = F.feature_row(p, j, i)
    assert all(why[k] == "NO_TRADE" for k in F.CANDLES)
    assert vals[F.COLUMNS.index("RET_5")] == pytest.approx(
        c[i] / c[i - 5] - 1
    )  # 0 이 아닌 값은 그대로
    # 거래가 있는 날 고저 관계 손상 → 결측으로 덮지 않고 CheckRequired
    p.V[j, i], p.raw_open[j, i] = 1000.0, 50.0
    p.raw_high[j, i] = p.raw_open[j, i] * 0.5
    with pytest.raises(D.CheckRequired):
        F.feature_row(p, j, i)
    # 고가만 종가 아래(저가 · 시가는 정상) → 고가 조건 하나로도 멈춤
    rc = p.C[j, i]
    p.raw_open[j, i], p.raw_low[j, i], p.raw_high[j, i] = rc, rc * 0.99, rc * 0.995
    with pytest.raises(D.CheckRequired):
        F.feature_row(p, j, i)
    # 저가만 시가 위(고가 정상) → 저가 조건 하나로도 멈춤
    p.raw_high[j, i], p.raw_low[j, i] = rc * 1.01, rc * 1.005
    with pytest.raises(D.CheckRequired):
        F.feature_row(p, j, i)
    # 고가 = 저가 → CLOSE_POS 분모 0
    p.raw_high[j, i] = p.raw_low[j, i] = p.raw_open[j, i] = p.C[j, i]
    vals, why = F.feature_row(p, j, i)
    assert why == {
        "VOLUME_RATIO_5": "DIV0",
        "CLOSE_POS": "DIV0",
    }  # 앞의 거래량 0 결측은 그대로


def test_label_definition_and_availability():
    n = 140
    b = [100.0 + 0.1 * k for k in range(n)]
    a = [50.0 + 0.3 * k for k in range(n)]
    p = _panel(
        {"069500": b, "111111": a},
        opens={"069500": [x - 0.05 for x in b], "111111": [x - 0.2 for x in a]},
    )
    j, bi, i = p.ci["111111"], p.ci["069500"], 10
    e, q = i + 2, i + 61
    z = F.label_z(p, j, i, bi)
    assert z == pytest.approx(
        math.log(a[q] / (a[e] - 0.2)) - math.log(b[q] / (b[e] - 0.05)), rel=1e-12
    )
    p.I[j, q + 1 :] = 1.0  # noqa: E203 — q 뒤 미래는 정답에 영향 없음
    assert F.label_z(p, j, i, bi) == z
    p2 = _panel({"069500": b, "111111": a})
    p2.seg[p2.ci["111111"], q] = 1  # 연결 구간이 바뀌면 정답 없음
    assert F.label_z(p2, p2.ci["111111"], i, bi) is None
    p3 = _panel({"069500": b, "111111": a})
    p3.raw_open[p3.ci["111111"], e] = (
        0.0  # 진입 시가 0 = 정답 미확인(0 으로 채우지 않음)
    )
    assert F.label_z(p3, p3.ci["111111"], i, bi) is None
    p4 = _panel({"069500": b, "111111": a[:q] + [math.nan] + a[q + 1 :]})  # noqa: E203
    assert F.label_z(p4, p4.ci["111111"], i, bi) is None
    assert F.label_z(p, j, n - 61, bi) is None  # q 가 축 밖


def test_rank_y_average_ties():
    y = F.rank_y({1: 0.5, 2: 0.1, 3: 0.5, 4: -1.0})
    assert y == {4: -0.5, 2: -0.5 + 1 / 3, 1: 0.5 - 1 / 6, 3: 0.5 - 1 / 6}


def _cal(n: int, first: str = "2010-01-01") -> list[str]:
    import datetime as dt

    d0 = dt.date.fromisoformat(first)
    return [(d0 + dt.timedelta(days=k)).isoformat() for k in range(n)]


def _table(sigs, per, y=None, usable=None):
    rows = [(i, j) for i in sigs for j in range(per)]
    return F.Table(
        sig=list(sigs),
        rows=rows,
        X=[[0.0] * 30] * len(rows),
        missing=[{}] * len(rows),
        z=[0.0] * len(rows),
        y=y or [0.0] * len(rows),
        usable=usable or {i: True for i in sigs},
        label_count={},
    )


def test_training_rows_maturity_usable_and_weights():
    axis = _cal(400)
    y = [0.0, 0.1, None] + [0.0] * 12  # 신호 100 의 세 번째 행 = 정답 없음
    t = _table(
        (100, 200, 290, 291, 292),
        3,
        y=y,
        usable={100: True, 200: True, 290: True, 291: False, 292: True},
    )
    ci = 357  # i + 61 ≤ ci − 5 → i ≤ 291
    got = F.training_rows(t, axis, ci)
    assert sorted({t.rows[r][0] for r in got}) == [
        100,
        200,
        290,
    ]  # 291 사용 불가 · 292 미성숙
    assert len(got) == 8 and all(t.y[r] is not None for r in got)
    w = F.weights(t, got)
    per: dict[int, float] = {}
    for r, x in zip(got, w):
        per[t.rows[r][0]] = per.get(t.rows[r][0], 0.0) + x
    assert np.mean(w) == pytest.approx(1.0)
    assert max(per.values()) == pytest.approx(min(per.values()))  # 날짜마다 합이 같다


def test_training_rows_five_year_window_and_maturity_boundary():
    axis = ["2015-01-02", "2015-01-05"] + _cal(100, "2016-01-01") + ["2020-01-02"]
    ci = len(axis) - 1  # cutoff 2020-01-02 → 5달력년 창 = (2015-01-02, 2020-01-02]
    t = _table((0, 1), 1)
    assert [t.rows[r][0] for r in F.training_rows(t, axis, ci)] == [1]
    axis2 = _cal(120)
    t2 = _table((40, 41), 1)
    ci2 = 40 + 61 + 5  # q(40) = 101 = ci − 5 → 성숙 · q(41) = 102 > ci − 5 → 제외
    assert [t2.rows[r][0] for r in F.training_rows(t2, axis2, ci2)] == [40]


def test_model_for_cutoff_le_signal():
    cuts = [{"id": "Q1", "cutoff_idx": 10}, {"id": "Q2", "cutoff_idx": 20}]
    assert F.model_for(9, cuts) is None
    assert F.model_for(10, cuts)["id"] == "Q1"  # cutoff = D 적용
    assert F.model_for(19, cuts)["id"] == "Q1"  # cutoff > D 인 Q2 는 쓰지 않음
    assert F.model_for(20, cuts)["id"] == "Q2"


def test_quarter_cutoffs_last_trading_day_before_quarter():
    axis = ["2017-12-27", "2017-12-28", "2018-01-02", "2018-03-30", "2018-04-02"]
    cuts = F.quarter_cutoffs(axis, (2018, 1), (2018, 2))
    assert [(c["id"], c["cutoff"]) for c in cuts] == [
        ("2018Q1", "2017-12-28"),
        ("2018Q2", "2018-03-30"),
    ]


def test_exec_needs_volume_even_with_published_open():
    p = _panel(
        {"069500": [100.0] * 5, "111111": [100.0] * 5},
        vols={"111111": [1000.0, 0.0, 1000.0, 0.0, 1.0]},
    )
    j = p.ci["111111"]
    assert [bool(x) for x in p.exec_ok[j]] == [True, False, True, False, True]


def test_build_panel_zero_volume_with_open_is_not_tradable(tmp_path):
    days = trading_dates(4)
    a = _series("069500", days, [100, 101, 102, 103], name="KODEX 200")
    b = _series(
        "111111", days, [100, 101, 102, 103], vols=[1000, 0, 1000, 1000]
    )  # 시가는 공표 · 거래량 0
    path, sha = _db(tmp_path, [a, b])
    p = D.build_panel(path, "krx_etf_universe_v1", sha)
    j = p.ci["111111"]
    assert p.raw_open[j, 1] > 0 and not p.exec_ok[j, 1] and p.exec_ok[j, 2]


def test_liquidity_window_needs_twenty_rows():
    n = 40
    c = [10000.0] * n
    p = _panel({"069500": c, "111111": c}, vols={"111111": [20000.0] * n})
    j = p.ci["111111"]
    liq = D.liquidity_mean(p)
    assert np.isnan(liq[j, 18]) and liq[j, 19] == pytest.approx(2e8)
    p.V[j, 10] = np.nan  # 창 안에 빈 날 → 건너뛰어 평균하지 않음
    liq = D.liquidity_mean(p)
    assert np.isnan(liq[j, 19]) and np.isnan(
        liq[j, 29]
    )  # 창 t−19..t 에 10 이 들어가는 동안
    assert liq[j, 30] == pytest.approx(2e8)  # 빈 날이 창을 벗어나면 다시 값


def test_zero_volume_with_published_prices_keeps_candles():
    n = 130
    c = [100.0 + k for k in range(n)]
    v = [1000.0] * n
    v[125] = 0.0  # 거래량 0 이지만 시가 · 고가 · 저가는 공표(알려진 무거래 표식 아님)
    p = _panel({"069500": c, "111111": c}, vols={"111111": v})
    vals, why = F.feature_row(p, p.ci["111111"], 125)
    assert not any(why.get(k) == "NO_TRADE" for k in F.CANDLES)
    assert vals[F.COLUMNS.index("OPEN_GAP")] is not None


def test_usable_date_needs_95_percent_labels():
    n = 70
    codes = [f"{100000 + k}" for k in range(40)]
    closes = {c: [100.0] * n for c in codes}
    closes["069500"] = [100.0] * n
    p = _panel(closes)
    i = 2  # e = 4 · q = 63
    members = {i: [p.ci[c] for c in codes]}
    count, usable = F.availability(p, members)
    assert count[i] == 40 and usable[i]
    p.has_row[p.ci[codes[0]], 63] = p.has_row[p.ci[codes[1]], 63] = False  # 38/40 = 95%
    count, usable = F.availability(p, members)
    assert count[i] == 38 and usable[i]
    p.has_row[p.ci[codes[2]], 63] = False  # 37/40 = 92.5%
    count, usable = F.availability(p, members)
    assert count[i] == 37 and not usable[i]


def test_close_at_low_with_chain_factor_is_not_damage(tmp_path):
    """연결값 ≠ 원시 종가인 종목이 저가(또는 고가)로 마감한 날 — 합성 L* 와 I 가 1ulp 어긋나도 정상(검토 r1)."""
    n = 140
    days = trading_dates(n)
    rng = np.random.default_rng(3)
    closes = [
        int(10000 + 5 * k + 5 * x) for k, x in enumerate(rng.integers(-40, 40, n))
    ]
    shift = {k: 37 for k in range(5, n, 7)}  # 기준가 차이 → 연결 배율이 날마다 쌓임
    a = _series("069500", days, closes, name="KODEX 200")
    b = _series("111111", days, closes, base_shift=shift, at_low=True)
    path, sha = _db(tmp_path, [a, b])
    p = D.build_panel(path, "krx_etf_universe_v1", sha)
    j = p.ci["111111"]
    off = sum(1 for i in range(125, n) if p.L[j, i] != p.I[j, i])
    assert off > 0  # 합성값끼리는 실제로 어긋나는 날이 있다
    for i in range(125, n):
        vals, _ = F.feature_row(p, j, i)
        assert (
            vals[F.COLUMNS.index("CLOSE_POS")] in (0.0, None)
            or vals[F.COLUMNS.index("CLOSE_POS")] == 0
        )
        assert vals[F.COLUMNS.index("LOWER_SHADOW")] == 0.0
