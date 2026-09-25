"""POC4-02B 봉인 KRX → 시장일 축 13개 · universe 변형 PIT/FS/ALL (PLAN §6 · 확정 B4·B10 · 구현 정의 6).

tmp_path 의 KRX 스키마 고정 DB 만 쓴다(`tests/_krx_fixture.py`). 봉인 DB·라이브 DB 는 열지 않는다.
"""

from __future__ import annotations

import statistics

import pytest

from app import krx_sealed_reader as reader
from app import ml_ew_market_axes as mx
from app.ml_feature_builder import _build_market_risk_row_kodex_only
from app.ml_feature_primitives import build_series
from tests._krx_fixture import build_sealed_db, krx_row, trading_dates

N = 30
K_CLOSES = [
    100.0, 101.0, 102.0, 101.5, 100.5, 99.0, 99.5, 100.2, 101.1, 100.0,
    98.8, 98.0, 97.5, 99.0, 100.5, 101.0, 102.2, 101.9, 103.0, 102.4,
    101.0, 100.1, 99.2, 100.8, 101.6, 102.9, 102.0, 101.3, 100.9, 102.5,
]  # fmt: skip
K_VOLUMES = [1000 + 37 * ((i * 7) % 11) for i in range(N)]


def _code_rows(code, days, closes, names, navs=None, volume=1000):
    out, prev = {}, None
    for i, (d, c, name) in enumerate(zip(days, closes, names)):
        nav = navs[i] if navs else c
        out[d] = krx_row(code, d, c, prev, volume=volume, nav=nav, name=name)
        prev = c
    return out


def _panel(tmp_path):
    days = trading_dates(N)
    wave = [50.0 + ((i * 3) % 7) - 3 for i in range(N)]
    specs = [
        ("069500", days, K_CLOSES, ["KODEX 200"] * N, None),
        ("111111", days, wave, ["TEST 일반"] * N, [round(c * 1.01, 2) for c in wave]),
        ("222222", days, wave, ["TEST 인버스"] * N, None),
        ("333333", days, wave, ["TEST 코스닥 2배"] * N, None),
        ("444444", days[:20], wave[:20], ["TEST 폐지"] * 20, None),
        ("555555", days, wave, ["TEST 합성"] * 15 + ["TEST 일반2"] * 15, None),
        ("666666", days[10:], wave[10:], ["TEST 신규"] * 20, None),
    ]
    by_date: dict[str, list[dict]] = {}
    for code, ds, cl, nm, nav in specs:
        rows = _code_rows(code, ds, cl, nm, nav)
        if code == "069500":
            for d, v in zip(ds, K_VOLUMES):
                rows[d]["ACC_TRDVOL"] = str(v)
        for d, row in rows.items():
            by_date.setdefault(d, []).append(row)
    path = tmp_path / "krx.sqlite"
    build_sealed_db(path, by_date)
    return reader.load_panel(path), wave


def test_kodex_axes_match_legacy_builder_functions(tmp_path):
    panel, _ = _panel(tmp_path)
    axes = mx.build_market_axes(panel)
    chain = axes["chain"]
    assert chain == pytest.approx(K_CLOSES)  # 분배 없는 계열 = 종가
    series = build_series("069500", list(zip(panel.dates, chain, K_VOLUMES)))
    legacy_keys = (
        "kodex200_return_5d",
        "kodex200_return_20d",
        "volatility_20d_market_proxy",
        "drawdown_20d_market_proxy",
        "distance_from_20d_high",
    )
    for k, d in enumerate(panel.dates):
        row = _build_market_risk_row_kodex_only(d, series, k, {})
        for key in legacy_keys:
            assert axes["kodex"][key][k] == getattr(row, key), (key, k)
    assert axes["kodex"]["volatility_20d_market_proxy"][19] is None
    assert axes["kodex"]["volatility_20d_market_proxy"][20] is not None
    assert axes["kodex"]["drawdown_20d_market_proxy"][19] is not None


def test_kodex_down_day_weakness_and_expansion(tmp_path):
    panel, _ = _panel(tmp_path)
    kx = mx.build_market_axes(panel)["kodex"]
    for k in range(N):
        change = (K_CLOSES[k] / K_CLOSES[k - 1] - 1) * 100 if k else None
        if k >= 19 and change < 0:
            window = K_VOLUMES[k - 19 : k + 1]  # noqa: E203
            vr = K_VOLUMES[k] / statistics.fmean(window)
            assert kx["down_day_volume_ratio"][k] == pytest.approx(vr)
            assert kx["large_negative_day_proxy"][k] == pytest.approx(abs(change) * vr)
        else:
            assert kx["down_day_volume_ratio"][k] is None
            assert kx["large_negative_day_proxy"][k] is None
    assert kx["short_term_weakness_proxy"][:3] == [None, None, None]
    # 10·11·12 가 연속 하락 → 3일 일간 % 합 (음수) · 13 은 상승 → 0.0
    three = sum((K_CLOSES[i] / K_CLOSES[i - 1] - 1) * 100 for i in (10, 11, 12))
    assert kx["short_term_weakness_proxy"][12] == pytest.approx(three) and three < 0
    assert kx["short_term_weakness_proxy"][13] == 0.0
    r5 = [(K_CLOSES[i] / K_CLOSES[i - 1] - 1) * 100 for i in range(21, 26)]
    r20 = [(K_CLOSES[i] / K_CLOSES[i - 1] - 1) * 100 for i in range(6, 26)]
    assert kx["volatility_expansion_20d"][25] == pytest.approx(
        statistics.stdev(r5) / statistics.stdev(r20)
    )


def test_universe_variants_filter_by_day_name_and_final_date(tmp_path):
    panel, _ = _panel(tmp_path)
    axes = mx.build_market_axes(panel)
    size = {v: axes["universe_size"][v]["universe"] for v in mx.VARIANTS}
    assert [size[v][0] for v in mx.VARIANTS] == [0, 0, 0]  # 첫날 = 앞 행 없음
    # day 5: ALL 6 (069500·111111·222222·333333·444444·555555) · PIT 3 (합성·인버스·2배 제외)
    #        FS 2 (444444 는 최종일에 없음)
    assert (size["ALL"][5], size["PIT"][5], size["FS"][5]) == (6, 3, 2)
    # day 10: 666666 첫 행 → 건너뜀 · day 12: 포함
    assert (size["ALL"][10], size["ALL"][12]) == (6, 7)
    assert (size["PIT"][12], size["FS"][12]) == (4, 3)
    # day 16: 555555 이름이 바뀌어 PIT·FS 에 들어온다 (그날 이름 기준)
    assert (size["PIT"][16], size["FS"][16]) == (5, 4)
    # day 25: 444444 폐지 뒤 → PIT = FS
    assert (size["ALL"][25], size["PIT"][25], size["FS"][25]) == (6, 4, 4)
    for axis in mx.UNIVERSE_AXES:
        assert axes["universe"]["PIT"][axis][-1] == axes["universe"]["FS"][axis][-1]
    assert all(
        axes["universe"][v]["etf_universe_down_ratio"][0] is None for v in mx.VARIANTS
    )


def test_universe_breadth_median_and_nav(tmp_path):
    panel, wave = _panel(tmp_path)
    u = mx.build_market_axes(panel)["universe"]["PIT"]
    k = 5  # PIT = 069500 · 111111 · 444444
    wave_daily = (wave[k] / wave[k - 1] - 1) * 100
    daily = [(K_CLOSES[k] / K_CLOSES[k - 1] - 1) * 100, wave_daily, wave_daily]
    up = sum(d > 0 for d in daily) / 3
    down = sum(d < 0 for d in daily) / 3
    assert u["etf_universe_down_ratio"][k] == pytest.approx(down)
    assert u["breadth_deterioration_proxy"][k] == pytest.approx(down - up)
    five = [(K_CLOSES[k] / K_CLOSES[0] - 1) * 100] + [(wave[k] / wave[0] - 1) * 100] * 2
    assert u["etf_universe_median_return_5d"][k] == pytest.approx(
        statistics.median(five)
    )
    assert u["etf_universe_median_return_5d"][4] is None
    nav = round(wave[k] * 1.01, 2)
    expect = statistics.fmean([0.0, abs((wave[k] - nav) / nav * 100), 0.0])
    assert u["nav_discount_abs_avg"][k] == pytest.approx(expect)


def test_axes_for_and_pit_minus_fs(tmp_path):
    panel, _ = _panel(tmp_path)
    axes = mx.build_market_axes(panel)
    pit = mx.axes_for(axes, "PIT")
    assert list(pit) == list(mx.LEGACY_AXES) and len(pit) == 13
    assert pit["distance_from_20d_high"] == pit["drawdown_20d_market_proxy"]
    diff = mx.pit_minus_fs(axes)
    assert set(diff) == set(mx.UNIVERSE_AXES)
    assert diff["etf_universe_down_ratio"]["days_compared"] == N - 1


def test_benchmark_must_cover_every_date(tmp_path):
    days = trading_dates(5)
    by_date: dict[str, list[dict]] = {d: [] for d in days}
    prev = None
    for d, c in zip(days[1:], [100, 101, 102, 103]):
        by_date[d].append(krx_row("069500", d, c, prev, name="KODEX 200"))
        prev = c
    by_date[days[0]].append(krx_row("111111", days[0], 10, None, name="TEST"))
    path = tmp_path / "krx.sqlite"
    build_sealed_db(path, by_date)
    with pytest.raises(mx.AxesError, match="모든 거래일"):
        mx.build_market_axes(reader.load_panel(path))


def test_benchmark_chain_break_is_error(tmp_path):
    days = trading_dates(4)
    rows = {}
    prev = None
    for d, c in zip(days, [100, 101, 102, 103]):
        rows[d] = [krx_row("069500", d, c, prev, name="KODEX 200")]
        prev = c
    rows[days[2]][0]["FLUC_RT"] = "9.99"  # 관계 불일치 → 구간 끊김
    path = tmp_path / "krx.sqlite"
    build_sealed_db(path, rows)
    with pytest.raises(mx.AxesError, match="끊겼다"):
        mx.build_market_axes(reader.load_panel(path))
