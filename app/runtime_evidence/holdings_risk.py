"""POC3-OPS-02A — 보유 위험 즉시 알림 (`DAY_DROP`) 판정.

설계자 확정 (PLAN V1.2 §4.1):

    DAY_DROP = runtime 현재가 / 직전 거래일 종가 - 1

**분모는 직전 거래일 종가**다. 당일 시가가 아니다 — 시가를 분모로 쓰면 **갭
하락을 놓친다**. 분자는 OPS-01A 와 같은 runtime 현재가(Naver)이고 유효성 규칙도
같다(`price_asof` 가 실행일).

**구간은 사실형이다.** 투자 성과 기준이 아니라 보유종목의 당일 하락 구간이며
판단어(관찰/주의/경고)를 쓰지 않는다.

보조 정보 2종(고점 대비 · 매입 대비)은 **본문 표시 전용**이며 trigger · state ·
fingerprint 에 **넣지 않는다**. 넣으면 값이 미세하게 흔들릴 때마다 매 실행
재발송된다.

**시가 대비는 표시하지 않는다** (PLAN V1.3 §4.2-b) — 기존 Naver `basic` 응답에
시가 필드가 없고(재귀 탐색 매칭 0건), 당일 시가를 담은 다른 원천도 없다
(일별 가격은 마감 후 적재). 별도 endpoint 호출·장중 DB 적재는 범위 밖이다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from app.runtime_evidence.holdings_selection import (
    DISPLAY_DECIMALS,
    LOOKBACK_TRADING_DAYS,
    _is_same_day,
    normalize_pct,
    reference_trading_day,
)

REASON_DAY_DROP = "DAY_DROP"
REASON_DATA_UNAVAILABLE = "DATA_UNAVAILABLE_OR_STALE"

STATE_D5_7 = "D5_7"
STATE_D7_10 = "D7_10"
STATE_D10_PLUS = "D10_PLUS"
STATE_ACTIVE = "ACTIVE"

# 설계자 확정 경계 (PLAN V1.2 §4.1):
#   정확히 -5%  -> D5_7
#   정확히 -7%  -> D7_10
#   정확히 -10% -> D10_PLUS
# 즉 상한 배타 · 하한 포함. OPS-01A `classify_decline` 과 같은 패턴이다.
_RISK_BANDS = (
    (STATE_D10_PLUS, None, -10.0),
    (STATE_D7_10, -10.0, -7.0),
    (STATE_D5_7, -7.0, -5.0),
)

# ── POC3-02C-OPS-02 급등 3단계 (설계자 §13-1 · 2026-09-20) ──────────────────
#
# 급락 경계의 **절댓값을 양수 방향으로 대칭 적용**한다. 다만 부등호 방향이
# 뒤집힌다 — 급락은 `상한 배타 · 하한 포함`(정확히 -5% → D5_7)이고, 급등은
# `하한 포함 · 상한 배타`(정확히 +5% → U5_7)다. 0 에서 멀어질수록 심각해지는
# 성질을 양쪽에서 같게 유지하려면 이렇게 돼야 한다.
#
# **급락 경계는 한 글자도 바꾸지 않는다** — 기존 계약이다.
STATE_U5_7 = "U5_7"
STATE_U7_10 = "U7_10"
STATE_U10_PLUS = "U10_PLUS"

_SURGE_BANDS = (
    (STATE_U10_PLUS, 10.0, None),
    (STATE_U7_10, 7.0, 10.0),
    (STATE_U5_7, 5.0, 7.0),
)

SURGE_STATE_LABEL = {
    STATE_U5_7: "전일 대비 상승 5~7%",
    STATE_U7_10: "전일 대비 상승 7~10%",
    STATE_U10_PLUS: "전일 대비 상승 10% 이상",
}

SURGE_STATE_SHORT = {
    STATE_U5_7: "5~7%",
    STATE_U7_10: "7~10%",
    STATE_U10_PLUS: "10% 이상",
}

# 급등도 심각도 1·2·3 (설계자 §13-1). 급락과 **별도 축**이다 — 한 종목이
# 동시에 양쪽일 수 없으므로 값이 겹쳐도 섞이지 않는다.
_SURGE_SEVERITY = {STATE_U5_7: 1, STATE_U7_10: 2, STATE_U10_PLUS: 3}

# 표시 순서 — 큰 상승이 위로.
SURGE_GROUP_ORDER = (STATE_U10_PLUS, STATE_U7_10, STATE_U5_7)


def surge_severity(state: Optional[str]) -> int:
    """급등 구간 심각도. 미상은 0."""
    return _SURGE_SEVERITY.get(state or "", 0)


def classify_day_surge(pct: Optional[float]) -> Optional[str]:
    """당일 상승률(%) → 급등 구간. 해당 없으면 None.

    `classify_day_drop` 과 **대칭**이다. 경계값은 하한 포함·상한 배타 —
    정확히 `+5%` 는 `U5_7`, 정확히 `+7%` 는 `U7_10`, 정확히 `+10%` 는 `U10_PLUS`.
    """
    if pct is None:
        return None
    for state, lower_inclusive, upper_exclusive in _SURGE_BANDS:
        if upper_exclusive is None:
            if pct >= lower_inclusive:
                return state
        elif lower_inclusive <= pct < upper_exclusive:
            return state
    return None


RISK_STATE_LABEL = {
    STATE_D5_7: "전일 대비 하락 5~7%",
    STATE_D7_10: "전일 대비 하락 7~10%",
    STATE_D10_PLUS: "전일 대비 하락 10% 이상",
}

# 구간 전이 표기용 짧은 라벨. 그룹 헤더에 이미 전체 라벨이 있으므로 줄 끝
# `(이전 → 현재)` 에까지 전체 문장을 반복하면 줄이 두 배로 길어진다.
RISK_STATE_SHORT = {
    STATE_D5_7: "5~7%",
    STATE_D7_10: "7~10%",
    STATE_D10_PLUS: "10% 이상",
}

# 악화 판정용 순서. 값이 클수록 나쁘다.
_SEVERITY = {STATE_D5_7: 1, STATE_D7_10: 2, STATE_D10_PLUS: 3}

# 표시 순서 — 나쁜 구간이 위로.
GROUP_ORDER = (STATE_D10_PLUS, STATE_D7_10, STATE_D5_7)

# 보조 정보 `고점 대비` 창.
DRAWDOWN_WINDOW = LOOKBACK_TRADING_DAYS


def severity(state: Optional[str]) -> int:
    """구간 심각도. 미상은 0."""
    return _SEVERITY.get(state or "", 0)


def classify_day_drop(pct: Optional[float]) -> Optional[str]:
    """당일 하락률(%) → 구간. 해당 없으면 None.

    `pct` 는 **이미 정규화된 값**이어야 한다 — 판정·저장·표시가 같은 값을 써야
    경계에서 어긋나지 않는다(OPS-01A 에서 겪은 문제).
    """
    if pct is None:
        return None
    for state, lower_exclusive, upper_inclusive in _RISK_BANDS:
        if lower_exclusive is None:
            if pct <= upper_inclusive:
                return state
        elif lower_exclusive < pct <= upper_inclusive:
            return state
    return None


@dataclass
class RiskTicker:
    """위험 알림 1건. 다계좌는 ticker 기준으로 합쳐 **한 번만** 표시한다."""

    ticker: str
    name: str
    account_count: int
    state: str
    # trigger 값.
    day_drop_pct: Optional[float] = None
    # 보조 정보 — state·fingerprint 에 넣지 않는다. 시가 대비는 §4.2-b 로 제외.
    drawdown_pct: Optional[float] = None
    profit_loss_pct: Optional[float] = None
    extra: dict[str, Any] = field(default_factory=dict)

    def fingerprint(self) -> str:
        """`ticker#DAY_DROP#state`.

        보조 2종은 제외한다. 근거 값(−5.1 → −5.3)도 제외한다 — 구간이 바뀔 때만
        의미가 있다.
        """
        return f"{self.ticker}#{REASON_DAY_DROP}#{self.state}"


def previous_trading_day(
    axis_dates: list[str], today_kst: Optional[str]
) -> Optional[str]:
    """실행일 **직전 거래일**. 축이 비었거나 이전 거래일이 없으면 None.

    OPS-01A 의 `reference_trading_day(..., lookback=1)` 과 같은 계약이다 —
    실행일 당일은 후보가 아니다.
    """
    return reference_trading_day(axis_dates, today_kst, 1)


def _drawdown_pct(
    history: list[tuple[str, float]], window_days: list[str], current: Optional[float]
) -> Optional[float]:
    """보조 — 구간 고점 대비. OPS-01A 와 같은 정의(현재가 / 기간 고점 − 1).

    구간이 불완전하면 **이 값만** 생략한다. 빠진 날이 있는 채로 고점을 잡으면
    하락이 얕게 보고된다.
    """
    if not window_days or not current or current <= 0:
        return None
    by_date = {d[:10]: c for d, c in history if c and c > 0}
    closes = [by_date.get(d) for d in window_days]
    if any(c is None for c in closes):
        return None
    peak = max(c for c in closes if c is not None)
    if not peak or peak <= 0:
        return None
    return normalize_pct((current / peak - 1.0) * 100.0)


def _ratio_pct(current: Optional[float], base: Optional[float]) -> Optional[float]:
    if not current or current <= 0 or not base or base <= 0:
        return None
    return normalize_pct((current / base - 1.0) * 100.0)


def select_risk_holdings(
    *,
    holdings: list[dict[str, Any]],
    price_history: dict[str, list[tuple[str, float]]],
    market_quotes: dict[str, Any],
    today_kst: Optional[str] = None,
    axis_dates: Optional[list[str]] = None,
    avg_buy_prices: Optional[dict[str, float]] = None,
) -> tuple[list[RiskTicker], list[str]]:
    """위험 구간에 든 보유종목만 반환.

    반환: `(선정 목록, 데이터 확인 대상 ticker 목록)`.

    **직전 거래일 종가가 정확히 없으면 더 오래된 값으로 대체하지 않는다**
    (PLAN §4.7). 그 종목은 선정에서 빼고 `데이터 확인 대상` 으로 돌려준다.
    """
    axis = axis_dates or []
    buy_prices = avg_buy_prices or {}
    # `previous_trading_day` 는 여기서 더 이상 분모에 쓰지 않는다 — 등락률이
    # Naver 응답에서 온다. 함수 자체는 호출자(`holdings_risk_flow`)가 표시용
    # 기준일로 쓰므로 남겨 둔다.

    today = (today_kst or "")[:10]
    before_today = [d for d in axis if d[:10] < today] if today else []
    aux_window = before_today[-DRAWDOWN_WINDOW:] if before_today else []

    by_ticker: dict[str, dict[str, Any]] = {}
    for h in holdings:
        t = h.get("ticker")
        if not t:
            continue
        entry = by_ticker.setdefault(t, {"name": h.get("name") or t, "accounts": 0})
        entry["accounts"] += 1
        if h.get("name"):
            entry["name"] = h["name"]

    selected: list[RiskTicker] = []
    unavailable: list[str] = []
    for ticker, meta in by_ticker.items():
        history = price_history.get(ticker) or []
        quote = market_quotes.get(ticker)
        current = getattr(quote, "current_price", None) if quote else None

        # POC3-02C-OPS-02 (설계자 §13-2) — 분모를 조정계열 종가에서
        # **Naver 무조정 D-1 등락률**로 교체했다. 예전에는
        # `current(무조정) / close_on(etf_daily_price, prev_day)(조정)` 이라
        # 두 계열이 섞여 있었다. 임계·상태·심각도 계약은 그대로다.
        day_drop = usable_day_return(quote, today_kst)
        if day_drop is None:
            unavailable.append(ticker)
            continue

        state = classify_day_drop(day_drop)
        if state is None:
            continue  # 위험 구간 아님 — 표시하지 않는다.

        item = RiskTicker(
            ticker=ticker,
            name=meta["name"],
            account_count=meta["accounts"],
            state=state,
            day_drop_pct=day_drop,
        )
        # 보조 2종 — 표시 전용.
        item.drawdown_pct = _drawdown_pct(history, aux_window, current)
        item.profit_loss_pct = _ratio_pct(current, buy_prices.get(ticker))
        selected.append(item)

    return sort_risk(selected), sorted(unavailable)


def usable_day_return(quote: Any, today_kst: Optional[str]) -> Optional[float]:
    """판정에 쓸 수 있는 **무조정 D-1 대비 등락률(%)**. 못 쓰면 `None`.

    설계자 §13-2 — `fluctuationsRatio` 를 **그대로** 쓴다. 현재가로 역산하지
    않고, 조정계열 `etf_daily_price` 로 fallback 하지 않는다.

    **기존 가격 최신성 검사는 그대로 유지한다** — 실행일 시세가 아니면 등락률이
    있어도 쓰지 않는다. 어제 값으로 오늘을 판정하면 안 된다.

    `0.0` 은 **유효한 보합**이다. 여기서 걸러지면 하락·보합이 통째로 사라진다.
    """
    if quote is None:
        return None
    current = getattr(quote, "current_price", None)
    asof = getattr(quote, "price_asof", None)
    # 최신성 게이트 — 기존 계약 그대로.
    if not current or current <= 0 or not _is_same_day(asof, today_kst):
        return None
    getter = getattr(quote, "has_day_return", None)
    if callable(getter):
        if not getter():
            return None
        return normalize_pct(float(quote.day_return_pct))
    # dataclass 가 아닌 대역 객체도 받는다 — 값만 보고 판단한다.
    raw = getattr(quote, "day_return_pct", None)
    if raw is None or isinstance(raw, bool):
        return None
    try:
        n = float(raw)
    except (TypeError, ValueError):
        return None
    if n != n or abs(n) > 100.0:
        return None
    return normalize_pct(n)


def select_surge_holdings(
    *,
    holdings: list[dict[str, Any]],
    market_quotes: dict[str, Any],
    today_kst: Optional[str],
) -> list[RiskTicker]:
    """보유 **급등** 선정 (설계자 §13-1). 급락과 **별도 축**이다.

    한 종목이 동시에 급락·급등일 수 없으므로 두 목록이 겹치지 않는다.

    `unavailable` 을 따로 돌려주지 않는다 — 같은 quote 를 급락 경로가 이미 보고
    결손을 보고했다. 여기서 또 세면 같은 종목이 두 번 실린다.
    """
    by_ticker: dict[str, dict[str, Any]] = {}
    for h in holdings:
        t = h.get("ticker")
        if not t:
            continue
        entry = by_ticker.setdefault(t, {"name": h.get("name") or t, "accounts": 0})
        entry["accounts"] += 1
        if h.get("name"):
            entry["name"] = h["name"]

    out: list[RiskTicker] = []
    for ticker, meta in by_ticker.items():
        pct = usable_day_return(market_quotes.get(ticker), today_kst)
        if pct is None:
            continue
        state = classify_day_surge(pct)
        if state is None:
            continue
        item = RiskTicker(
            ticker=ticker,
            name=meta["name"],
            account_count=meta["accounts"],
            state=state,
            day_drop_pct=pct,  # 부호 포함 — 급등이면 양수다
        )
        out.append(item)
    return sort_surge(out)


def sort_surge(items: list[RiskTicker]) -> list[RiskTicker]:
    """구간(큰 상승 먼저) → 상승 큰 순 → ticker."""
    order = {s: i for i, s in enumerate(SURGE_GROUP_ORDER)}
    return sorted(
        items,
        key=lambda i: (
            order.get(i.state, len(order)),
            -(i.day_drop_pct if i.day_drop_pct is not None else 0.0),
            i.ticker,
        ),
    )


def sort_risk(items: list[RiskTicker]) -> list[RiskTicker]:
    """구간(나쁜 순) → 하락 큰 순 → ticker."""
    order = {s: i for i, s in enumerate(GROUP_ORDER)}
    return sorted(
        items,
        key=lambda i: (
            order.get(i.state, len(order)),
            i.day_drop_pct if i.day_drop_pct is not None else 0.0,
            i.ticker,
        ),
    )


def group_label(state: str) -> str:
    return RISK_STATE_LABEL.get(state, state)


def short_label(state: str) -> str:
    """전이 표기용. 그룹 헤더의 전체 라벨과 중복되지 않게 구간만."""
    return RISK_STATE_SHORT.get(state, state)


__all__ = [
    "DISPLAY_DECIMALS",
    "GROUP_ORDER",
    "REASON_DATA_UNAVAILABLE",
    "REASON_DAY_DROP",
    "RISK_STATE_LABEL",
    "RISK_STATE_SHORT",
    "RiskTicker",
    "STATE_D10_PLUS",
    "STATE_D5_7",
    "STATE_D7_10",
    "classify_day_drop",
    "group_label",
    "previous_trading_day",
    "select_surge_holdings",
    "sort_surge",
    "select_risk_holdings",
    "severity",
    "short_label",
    "sort_risk",
]
