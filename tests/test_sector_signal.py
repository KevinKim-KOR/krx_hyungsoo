"""POC3-02C-OPS-02 — 사업군 대표 판정 계약 (설계자 §4-2 · §9).

실제 Naver·KRX·Telegram 호출 0건. 모든 입력은 대역이다.
"""

from __future__ import annotations

import sqlite3

import pytest

from app.intraday_config import schema
from app.runtime_evidence import sector_signal as ss

TODAY = "2026-09-16"
ASOF = "2026-09-16T10:30:00+09:00"
POLICY = dict(schema.INITIAL_POLICY_VALUES)


class Q:
    def __init__(self, ret, *, price=10000.0, asof=ASOF):
        self.current_price, self.day_return_pct, self.price_asof = price, ret, asof

    def has_day_return(self):
        v = self.day_return_pct
        return isinstance(v, (int, float)) and not isinstance(v, bool)


def _sector(key, ticker, name="대표ETF", alt=None):
    s = {"sector_key": key, "representative": {"ticker": ticker, "short_name": name}}
    if alt:
        s["alternate"] = {"ticker": alt[0], "short_name": alt[1]}
    return s


def _hist(*closes):
    return [(f"2026-08-{i + 1:02d}", c) for i, c in enumerate(closes)]


def _rising(n=25, start=100.0, step=1.0):
    return _hist(*[start + step * i for i in range(n)])


# ── §4-2 판정 표 ────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "pct,top,bottom,expected",
    [
        (4.0, False, False, ss.STATE_AVOID_CHASE),
        (5.5, False, False, ss.STATE_AVOID_CHASE),
        (3.99, True, False, ss.STATE_ENTRY_REVIEW),
        (1.5, True, False, ss.STATE_ENTRY_REVIEW),
        (1.49, True, False, None),
        (1.5, False, False, None),  # 상위 20% 아님
        (-1.5, False, True, ss.STATE_AVOID_DROP),
        (-2.4, False, True, ss.STATE_AVOID_DROP),
        (-1.49, False, True, None),
        (-2.4, False, False, None),  # 하위 20% 아님
        (0.0, True, True, None),
    ],
)
def test_classification_table(pct, top, bottom, expected):
    """설계 §4-2 표 그대로. 경계값 포함."""
    got = ss.classify_sector(
        day_return_pct=pct,
        return_5d_pct=1.0,
        return_20d_pct=1.0,
        is_top_riser=top,
        is_bottom_faller=bottom,
        policy=POLICY,
    )
    assert got == expected


@pytest.mark.parametrize("r5,r20", [(None, 1.0), (1.0, None), (-0.1, 1.0), (1.0, -0.1)])
def test_entry_requires_both_windows_positive(r5, r20):
    """5일·20일이 **둘 다 양수**여야 진입 검토다."""
    assert (
        ss.classify_sector(
            day_return_pct=2.0,
            return_5d_pct=r5,
            return_20d_pct=r20,
            is_top_riser=True,
            is_bottom_faller=False,
            policy=POLICY,
        )
        is None
    )


def test_chase_wins_over_entry():
    """추격 주의가 진입 검토보다 **앞선다** — 임계가 PARAM 으로 바뀌어도."""
    loose = dict(POLICY, sector_entry_min_pct=1.0, sector_chase_pct=2.0)
    assert (
        ss.classify_sector(
            day_return_pct=3.0,
            return_5d_pct=5.0,
            return_20d_pct=5.0,
            is_top_riser=True,
            is_bottom_faller=False,
            policy=loose,
        )
        == ss.STATE_AVOID_CHASE
    )


# ── 창 수익률 ───────────────────────────────────────────────────────────────


def test_window_return_needs_n_plus_one_closes():
    """`N일 수익률` 은 종가 N+1 개가 있어야 한다."""
    assert ss.window_return_pct(_hist(100.0, 101.0, 102.0), 5) is None
    assert ss.window_return_pct(_rising(6), 5) is not None


def test_window_return_does_not_substitute_older_close():
    """모자라면 **더 오래된 종가로 대체하지 않는다** — None 이다."""
    assert ss.window_return_pct(_rising(20), ss.LOOKBACK_20D) is None
    assert ss.window_return_pct(_rising(21), ss.LOOKBACK_20D) is not None


def test_window_return_value():
    assert ss.window_return_pct(_hist(100.0, 0, 0, 0, 0, 110.0), 5) == 10.0


# ── 순위 ────────────────────────────────────────────────────────────────────


def test_top_cut_keeps_at_least_one():
    assert ss._top_cut(27, 20.0) == 5
    assert ss._top_cut(3, 20.0) == 1  # 내림하면 0 — 최소 1 보장
    assert ss._top_cut(0, 20.0) == 0


def test_rank_is_computed_among_evaluable_only():
    """조회 실패한 사업군을 분모에 넣으면 상위 20% 가 실제보다 좁아진다."""
    sectors = [_sector(f"S{i}", f"T{i:05d}") for i in range(10)]
    quotes = {f"T{i:05d}": Q(2.0 - i * 0.1) for i in range(5)}  # 5개만 조회 성공
    out = ss.select_sector_signals(
        sectors=sectors,
        market_quotes=quotes,
        history={f"T{i:05d}": _rising() for i in range(10)},
        today_kst=TODAY,
        policy=POLICY,
    )
    assert out.evaluated_count == 5
    assert all(s.candidate_count == 5 for s in out.signals)


# ── §9 실패 격리 ────────────────────────────────────────────────────────────


def test_missing_quote_excludes_only_that_sector():
    """조회 실패는 **그 사업군만** 제외한다.

    커버리지 Gate 에 걸리지 않도록 10개 중 1개만 실패시킨다(90% ≥ 80%).
    """
    sectors = [_sector(f"S{i}", f"T{i:05d}") for i in range(10)]
    quotes = {f"T{i:05d}": Q(2.0 - i * 0.1) for i in range(1, 10)}  # T00000 만 실패
    out = ss.select_sector_signals(
        sectors=sectors,
        market_quotes=quotes,
        history={f"T{i:05d}": _rising() for i in range(10)},
        today_kst=TODAY,
        policy=POLICY,
    )
    assert out.evaluated_count == 9
    assert out.coverage_ok is True
    assert [e["reason"] for e in out.excluded] == [ss.REASON_NO_QUOTE]


def test_alternate_is_tried_once_when_primary_fails():
    """대표 실패 시 **대체 1개만**. 재귀 대체 금지(설계자 §13-4)."""
    sectors = [_sector("A", "T00001", alt=("T99999", "대체ETF"))]
    out = ss.select_sector_signals(
        sectors=sectors,
        market_quotes={"T99999": Q(2.0)},
        history={"T99999": _rising()},
        today_kst=TODAY,
        policy=POLICY,
    )
    assert out.evaluated_count == 1
    assert out.signals and out.signals[0].used_alternate is True
    assert out.signals[0].ticker == "T99999"


def test_primary_success_never_queries_alternate():
    sectors = [_sector("A", "T00001", alt=("T99999", "대체ETF"))]
    out = ss.select_sector_signals(
        sectors=sectors,
        market_quotes={"T00001": Q(2.0), "T99999": Q(9.0)},
        history={"T00001": _rising(), "T99999": _rising()},
        today_kst=TODAY,
        policy=POLICY,
    )
    assert out.signals[0].ticker == "T00001"
    assert out.signals[0].used_alternate is False


def test_short_history_excludes_only_entry_candidate():
    """이력 부족은 **그 사업군만** 제외하고 사유를 남긴다.

    `T00001` 이 상위 20% 여야 진입 검토 분기에 닿는다 — 거기서만 5일·20일이
    필요하다. 순위 밖이면 애초에 후보가 아니라 이력도 안 본다.
    """
    sectors = [_sector("A", "T00001"), _sector("B", "T00002")]
    out = ss.select_sector_signals(
        sectors=sectors,
        market_quotes={"T00001": Q(2.5), "T00002": Q(2.0)},
        history={"T00001": _rising(3), "T00002": _rising()},
        today_kst=TODAY,
        policy=POLICY,
    )
    assert [e["reason"] for e in out.excluded] == [ss.REASON_SHORT_HISTORY]
    assert [s.ticker for s in out.signals] == []


def test_sector_outside_rank_never_needs_window_history():
    """순위 밖 사업군은 이력이 없어도 조용히 지나간다 — 제외 사유도 안 남는다."""
    sectors = [_sector("A", "T00001"), _sector("B", "T00002")]
    out = ss.select_sector_signals(
        sectors=sectors,
        market_quotes={"T00001": Q(2.5), "T00002": Q(2.0)},
        history={"T00001": _rising(), "T00002": _rising(3)},
        today_kst=TODAY,
        policy=POLICY,
    )
    assert out.excluded == []
    assert [s.ticker for s in out.signals] == ["T00001"]


def test_held_ticker_is_not_an_entry_candidate():
    """보유 중이면 신규 진입 후보가 아니다 — 보유 구역에만 실린다(§4-2)."""
    sectors = [_sector("A", "T00001")]
    out = ss.select_sector_signals(
        sectors=sectors,
        market_quotes={"T00001": Q(2.0)},
        history={"T00001": _rising()},
        today_kst=TODAY,
        policy=POLICY,
        held_tickers={"T00001"},
    )
    assert out.signals == []
    assert [e["reason"] for e in out.excluded] == [ss.REASON_HELD]


def test_stale_quote_is_excluded():
    """최신성 게이트는 사업군에서도 그대로."""
    sectors = [_sector("A", "T00001")]
    out = ss.select_sector_signals(
        sectors=sectors,
        market_quotes={"T00001": Q(2.0, asof="2026-09-04T15:40:00+09:00")},
        history={"T00001": _rising()},
        today_kst=TODAY,
        policy=POLICY,
    )
    assert out.signals == []


def test_missing_table_returns_empty_history_not_raise(tmp_path):
    """무조정 테이블이 없어도 **올리지 않는다** — 보유 경로를 막으면 안 된다."""
    db = tmp_path / "empty.sqlite"
    sqlite3.connect(db).close()
    out = ss.load_unadjusted_history(["T00001"], db_path=db)
    assert out == {"T00001": []}


def test_empty_ticker_list_is_safe(tmp_path):
    db = tmp_path / "empty.sqlite"
    sqlite3.connect(db).close()
    assert ss.load_unadjusted_history([], db_path=db) == {}


# ── fingerprint ─────────────────────────────────────────────────────────────


def test_fingerprint_excludes_numbers():
    """`fingerprint` 는 `ticker#state` 파생값이라 수치가 달라도 같다. 재발송 억제
    자체는 상태 파일의 `state` 비교로 한다(설계 §5·§15-2)."""
    a = ss.SectorSignal("반도체", "T1", "n", ss.STATE_AVOID_DROP, -2.4)
    b = ss.SectorSignal("반도체", "T1", "n", ss.STATE_AVOID_DROP, -3.9)
    assert a.fingerprint() == b.fingerprint()


def test_fingerprint_changes_with_state():
    a = ss.SectorSignal("반도체", "T1", "n", ss.STATE_AVOID_DROP, -2.4)
    b = ss.SectorSignal("반도체", "T1", "n", ss.STATE_AVOID_CHASE, 4.4)
    assert a.fingerprint() != b.fingerprint()


# ── §14-4 상대순위 최소 커버리지 Gate ───────────────────────────────────────


def test_low_coverage_drops_whole_sector_section():
    """**27개 중 3개만 조회돼도 그중 하나가 상위 20% 가 되면 안 된다.**

    실패 격리가 아니라 왜곡이다(설계자 §14-4).
    """
    sectors = [_sector(f"S{i}", f"T{i:05d}") for i in range(27)]
    quotes = {f"T{i:05d}": Q(3.0 - i) for i in range(3)}  # 3/27 = 11.1%
    out = ss.select_sector_signals(
        sectors=sectors,
        market_quotes=quotes,
        history={f"T{i:05d}": _rising() for i in range(27)},
        today_kst=TODAY,
        policy=POLICY,
    )
    assert out.signals == []
    assert out.coverage_ok is False
    assert out.coverage_pct is not None and out.coverage_pct < 80.0
    assert any(e["reason"] == ss.REASON_LOW_COVERAGE for e in out.excluded)


def test_coverage_at_threshold_is_allowed():
    """정확히 80% 는 통과한다 — 하한 포함."""
    sectors = [_sector(f"S{i}", f"T{i:05d}") for i in range(10)]
    quotes = {f"T{i:05d}": Q(2.5 - i * 0.1) for i in range(8)}  # 8/10 = 80%
    out = ss.select_sector_signals(
        sectors=sectors,
        market_quotes=quotes,
        history={f"T{i:05d}": _rising() for i in range(10)},
        today_kst=TODAY,
        policy=POLICY,
    )
    assert out.coverage_ok is True
    assert out.coverage_pct == 80.0


def test_coverage_just_below_threshold_is_blocked():
    sectors = [_sector(f"S{i}", f"T{i:05d}") for i in range(10)]
    quotes = {f"T{i:05d}": Q(2.5 - i * 0.1) for i in range(7)}  # 7/10 = 70%
    out = ss.select_sector_signals(
        sectors=sectors,
        market_quotes=quotes,
        history={f"T{i:05d}": _rising() for i in range(10)},
        today_kst=TODAY,
        policy=POLICY,
    )
    assert out.coverage_ok is False and out.signals == []


def test_coverage_threshold_comes_from_policy_not_code():
    """코드 상수가 아니라 PARAM 이다(설계자 §14-4)."""
    loose = dict(POLICY, sector_min_coverage_pct=10.0)
    sectors = [_sector(f"S{i}", f"T{i:05d}") for i in range(10)]
    quotes = {f"T{i:05d}": Q(2.5 - i * 0.1) for i in range(2)}  # 20%
    out = ss.select_sector_signals(
        sectors=sectors,
        market_quotes=quotes,
        history={f"T{i:05d}": _rising() for i in range(10)},
        today_kst=TODAY,
        policy=loose,
    )
    assert out.coverage_ok is True


def test_zero_evaluable_is_low_coverage_not_crash():
    sectors = [_sector("A", "T00001")]
    out = ss.select_sector_signals(
        sectors=sectors, market_quotes={}, history={}, today_kst=TODAY, policy=POLICY
    )
    assert out.signals == [] and out.coverage_ok is False


# ── §14-5 provider 장애 시 대체 연쇄 금지 ───────────────────────────────────
#
# **조회 횟수를 실제로 센다.** "대체를 안 쓴다" 를 결과로만 보면, 안 쓰는지
# 못 찾는지 구분되지 않는다.


class CountingQuotes(dict):
    """`market_quotes.get` 호출을 ticker 별로 센다."""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.looked_up: list[str] = []

    def get(self, key, default=None):
        self.looked_up.append(key)
        return super().get(key, default)


def _with_alts(n):
    return [_sector(f"S{i}", f"T{i:05d}", alt=(f"A{i:05d}", "대체")) for i in range(n)]


def test_single_ticker_failure_allows_one_alternate_lookup():
    """한 건 누락이면 **그 사업군만** 대체 1회 허용(§14-5)."""
    sectors = _with_alts(10)
    q = CountingQuotes({f"T{i:05d}": Q(2.0 - i * 0.1) for i in range(1, 10)})
    q["A00000"] = Q(2.5)  # 0번만 대체로 산다
    out = ss.select_sector_signals(
        sectors=sectors,
        market_quotes=q,
        history={f"T{i:05d}": _rising() for i in range(10)}
        | {f"A{i:05d}": _rising() for i in range(10)},
        today_kst=TODAY,
        policy=POLICY,
    )
    assert out.provider_down is False
    alt_lookups = [t for t in q.looked_up if t.startswith("A")]
    assert alt_lookups == ["A00000"], alt_lookups
    assert any(s.used_alternate for s in out.signals)


def test_provider_failure_makes_zero_alternate_lookups():
    """**provider 장애면 대체를 한 건도 조회하지 않는다.**

    primary 27개가 죽은 뒤 fallback 22개를 더 때리면 장애를 키운다.
    """
    sectors = _with_alts(27)
    q = CountingQuotes()  # primary 전부 실패
    for i in range(27):
        q[f"A{i:05d}"] = Q(2.0)  # 대체는 살아 있지만 건드리면 안 된다
    out = ss.select_sector_signals(
        sectors=sectors,
        market_quotes=q,
        history={f"A{i:05d}": _rising() for i in range(27)},
        today_kst=TODAY,
        policy=POLICY,
    )
    assert out.provider_down is True
    alt_lookups = [t for t in q.looked_up if t.startswith("A")]
    assert alt_lookups == [], f"provider 장애인데 대체를 {len(alt_lookups)}건 조회했다"
    assert out.signals == []
    assert any(e["reason"] == ss.REASON_PROVIDER_DOWN for e in out.excluded)


def test_alternate_is_never_recursed():
    """대체가 실패해도 **그 다음** 후보를 찾지 않는다 — 1단계뿐."""
    sectors = _with_alts(10)
    q = CountingQuotes({f"T{i:05d}": Q(2.0 - i * 0.1) for i in range(1, 10)})
    # A00000 도 없다 — 재귀 대체가 있으면 더 조회할 것이다
    out = ss.select_sector_signals(
        sectors=sectors,
        market_quotes=q,
        history={f"T{i:05d}": _rising() for i in range(10)},
        today_kst=TODAY,
        policy=POLICY,
    )
    assert q.looked_up.count("A00000") == 1
    assert out.evaluated_count == 9


def test_half_failure_is_not_provider_down():
    """절반만 실패하면 ticker 단위 장애로 본다 — 대체를 쓴다."""
    sectors = _with_alts(10)
    q = CountingQuotes({f"T{i:05d}": Q(2.0 - i * 0.1) for i in range(6)})
    for i in range(6, 10):
        q[f"A{i:05d}"] = Q(1.5)
    out = ss.select_sector_signals(
        sectors=sectors,
        market_quotes=q,
        history={f"T{i:05d}": _rising() for i in range(10)}
        | {f"A{i:05d}": _rising() for i in range(10)},
        today_kst=TODAY,
        policy=POLICY,
    )
    assert out.provider_down is False
    assert [t for t in q.looked_up if t.startswith("A")]
