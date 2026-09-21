"""POC3-02C-OPS-02 — 당일 등락률 가격 기준 계약 (설계자 §13-2).

판정 입력이 "무조정 현재가 ÷ 조정 종가" 에서 **Naver 무조정 D-1 등락률**로
바뀌었다. 계약이 **두 layer** 에 걸쳐 있어 양쪽을 다 고정한다.

```text
layer 1  coerce_day_return / MarketQuote.has_day_return   값 정규화
layer 2  usable_day_return                                최신성 + 판정 가용성
```

선정 테스트(`test_holdings_risk_alert.py`)만으로는 layer 1 이 비어 있었다 —
`0.0` 을 누락으로 바꿔도 통과했다. 실측으로 확인하고 이 파일을 만들었다.

실제 Naver·KRX 호출은 하지 않는다.
"""

from __future__ import annotations

import math

import pytest

from app.market_cache import MarketQuote, coerce_day_return
from app.runtime_evidence.holdings_risk import usable_day_return

ASOF = "2026-09-07T10:30:00+09:00"
TODAY = "2026-09-07"


# ── layer 1 · 값 정규화 ──────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "raw,expected", [(0, 0.0), (0.0, 0.0), ("0", 0.0), ("0.0", 0.0)]
)
def test_zero_is_a_valid_flat_not_missing(raw, expected):
    """**`0.0` 은 유효한 보합이다.**

    `_coerce_price` 는 `n <= 0` 을 버리는데 그 규칙을 등락률에 쓰면 보합뿐 아니라
    **하락이 통째로** 사라진다. 별도 함수인 이유다.
    """
    assert coerce_day_return(raw) == expected
    assert MarketQuote("t", "n", 100.0, ASOF, day_return_pct=expected).has_day_return()


@pytest.mark.parametrize("raw", [-3.2, "-3.2", -10.0, "2.83", 2.83])
def test_negative_and_positive_survive(raw):
    assert coerce_day_return(raw) == float(raw)


@pytest.mark.parametrize("raw", [None, "", "x", "--", [], {}, object()])
def test_missing_or_non_numeric_is_none(raw):
    assert coerce_day_return(raw) is None


@pytest.mark.parametrize("raw", [True, False])
def test_bool_is_rejected(raw):
    """`bool` 은 `int` 하위형이라 `float(True) == 1.0` 이 된다 — 막는다."""
    assert coerce_day_return(raw) is None


@pytest.mark.parametrize("raw", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_is_rejected(raw):
    assert coerce_day_return(raw) is None


@pytest.mark.parametrize("raw", [100.01, -100.01, 1e6])
def test_out_of_range_is_rejected(raw):
    """±100% 초과는 오염으로 본다."""
    assert coerce_day_return(raw) is None


def test_hundred_percent_is_still_accepted():
    """경계 자체는 살린다 — 상한가/하한가 극단이 실제로 있을 수 있다."""
    assert coerce_day_return(100.0) == 100.0
    assert coerce_day_return(-100.0) == -100.0


def test_nan_never_passes_has_day_return():
    q = MarketQuote("t", "n", 100.0, ASOF, day_return_pct=math.nan)
    assert not q.has_day_return()


def test_legacy_cache_without_field_is_none():
    """옛 캐시 파일에는 이 키가 없다 — 그 ticker 만 다음 조회까지 빠진다."""
    assert coerce_day_return({}.get("day_return_pct")) is None
    assert MarketQuote("t", "n", 100.0, ASOF).day_return_pct is None


# ── layer 2 · 최신성 + 판정 가용성 ──────────────────────────────────────────


def test_usable_requires_todays_quote():
    """**기존 가격 최신성 검사 유지** — 어제 값으로 오늘을 판정하지 않는다."""
    stale = MarketQuote(
        "t", "n", 100.0, "2026-09-04T15:40:00+09:00", day_return_pct=-8.0
    )
    assert usable_day_return(stale, TODAY) is None


def test_usable_requires_positive_current_price():
    for bad in (None, 0.0, -1.0):
        q = MarketQuote("t", "n", bad, ASOF, day_return_pct=-8.0)
        assert usable_day_return(q, TODAY) is None


def test_usable_returns_zero_for_flat():
    q = MarketQuote("t", "n", 100.0, ASOF, day_return_pct=0.0)
    assert usable_day_return(q, TODAY) == 0.0


def test_usable_is_none_when_field_missing():
    q = MarketQuote("t", "n", 100.0, ASOF)
    assert usable_day_return(q, TODAY) is None


def test_usable_handles_none_quote():
    assert usable_day_return(None, TODAY) is None


def test_usable_normalizes_like_display():
    """판정·표시가 같은 값을 써야 경계에서 어긋나지 않는다."""
    q = MarketQuote("t", "n", 100.0, ASOF, day_return_pct=-5.004)
    assert usable_day_return(q, TODAY) == -5.0


def test_usable_accepts_plain_object_without_helper():
    """dataclass 가 아닌 대역 객체도 값만 보고 판단한다."""

    class Bare:
        current_price = 100.0
        price_asof = ASOF
        day_return_pct = -8.0

    assert usable_day_return(Bare(), TODAY) == -8.0


def test_usable_rejects_polluted_value_on_plain_object():
    class Bare:
        current_price = 100.0
        price_asof = ASOF
        day_return_pct = 12345.0

    assert usable_day_return(Bare(), TODAY) is None


# ── 어댑터가 올바른 필드를 읽는가 ───────────────────────────────────────────


def test_adapter_reads_fluctuations_ratio_not_compare_amount():
    """`compareToPreviousClosePrice` 는 **부호가 없다.**

    방향 코드로 부호를 복원하면 실측에서 틀렸다(`466920`: 역산 +1.17% vs
    실제 −1.14%). 어댑터가 `fluctuationsRatio` 를 읽는지 소스로 고정한다.
    """
    src = __import__("pathlib").Path("app/market_naver.py").read_text(encoding="utf-8")
    assert 'data.get("fluctuationsRatio")' in src
    code = [
        ln for ln in src.splitlines() if ln.strip() and not ln.strip().startswith("#")
    ]
    joined = "\n".join(code)
    assert "compareToPreviousClosePrice" not in joined, "부호 없는 값을 쓰고 있다"


def test_selection_does_not_import_adjusted_close_helper():
    """조정계열 `close_on` fallback 이 판정 경로에 남아 있으면 안 된다."""
    src = (
        __import__("pathlib")
        .Path("app/runtime_evidence/holdings_risk.py")
        .read_text(encoding="utf-8")
    )
    code = [
        ln for ln in src.splitlines() if ln.strip() and not ln.strip().startswith("#")
    ]
    assert not [ln for ln in code if "close_on(" in ln], "조정 종가 fallback 잔존"
