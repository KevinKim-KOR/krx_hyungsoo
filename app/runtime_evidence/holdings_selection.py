"""POC3-OPS-01A — 보유 브리핑 선정기 (선정 이유 · 구간 · 그룹).

기존 `holdings_evidence.build_holdings_facts` 는 보유 32건을 **전량 나열**했다
(종목당 2줄 · 8,690자 · chunk 3개). 이 모듈은 **선정 이유가 있는 종목만** 골라
같은 구간끼리 묶는다.

설계자 확정 (PLAN V1.3):
- 선정 reason 2개 — `RECENT_DECLINE` · `DATA_UNAVAILABLE_OR_STALE`
- 보조 정보 1개 — `RECENT_LOW_OR_DRAWDOWN` (선정 근거 아님 · fingerprint 미생성)
- 제외 — `MARKET_RELATIVE_WEAKNESS`(자산군 차이) · 저점 접근 · `INTRADAY_DROP` ·
  `LOSS_WORSENING`

`RECENT_DECLINE` 계산 (PLAN §1.4 — 장중에 변해야 한다):

    20일 수익률 = OCI 실행 시점 현재가 / 20거래일 전 종가 - 1

  **세 지표 모두 같은 runtime 현재가를 분자로 쓴다** (설계자 확정 2026-09-06):

      매입 대비 손익률 = 현재가 / 수량가중평균 매입가 - 1
      20거래일 수익률  = 현재가 / 20거래일 전 종가     - 1
      고점 대비 수익률 = 현재가 / 기간 고점            - 1

  분자는 OCI runtime quote(Naver), 분모만 지표마다 다르다.
  종가끼리 비교하면 OPEN·MIDDAY·CLOSE 가 같은 값이라 장중 변화가 생기지 않는다.

구간은 **사실형 명칭**이다 (PLAN §5.1). `관찰·주의·경고` 를 쓰지 않는다 —
60거래일 실측에서 최상위 구간이 67% 를 차지해 심각도를 설명하지 못했다.

이 모듈이 하지 않는 것:
- 외부 API 호출 (현재가는 호출자가 넘긴다).
- 상태 저장 · 변화 판정 (→ `holdings_selection_state.py`).
- 매수/매도/비중 판단.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

# ── reason ──────────────────────────────────────────────────────────────────
REASON_RECENT_DECLINE = "RECENT_DECLINE"
REASON_DATA_UNAVAILABLE = "DATA_UNAVAILABLE_OR_STALE"

SELECTION_REASONS = (REASON_RECENT_DECLINE, REASON_DATA_UNAVAILABLE)

# ── 구간 (PLAN §5.1 · 상한 배타 · 하한 포함) ────────────────────────────────
STATE_D5_8 = "D5_8"
STATE_D8_10 = "D8_10"
STATE_D10_PLUS = "D10_PLUS"
STATE_ACTIVE = "ACTIVE"

# (state, 하한 초과, 상한 이하) — r <= 상한 이고 r > 하한.
_DECLINE_BANDS = (
    (STATE_D10_PLUS, None, -10.0),
    (STATE_D8_10, -10.0, -8.0),
    (STATE_D5_8, -8.0, -5.0),
)

DECLINE_STATE_LABEL = {
    STATE_D10_PLUS: "20거래일 하락 10% 이상",
    STATE_D8_10: "20거래일 하락 8~10%",
    STATE_D5_8: "20거래일 하락 5~8%",
}
DATA_UNAVAILABLE_LABEL = "데이터 확인 필요"

# 그룹 표시 순서 (PLAN §5.3).
GROUP_ORDER = (
    (REASON_RECENT_DECLINE, STATE_D10_PLUS),
    (REASON_RECENT_DECLINE, STATE_D8_10),
    (REASON_RECENT_DECLINE, STATE_D5_8),
    (REASON_DATA_UNAVAILABLE, STATE_ACTIVE),
)

# 보조 정보 표시 임계 — 이 값 이하일 때만 `[고점 대비 x%]` 를 붙인다.
DRAWDOWN_NOTE_MAX_PCT = -8.0

LOOKBACK_TRADING_DAYS = 20

# KRX 거래일 축 기준 ticker. 기존 walk-forward 가 쓰는 것과 같은 축을 쓴다
# (`app/market_flow_dataset.BENCHMARK_KODEX200_TICKER`). 신규 휴장일 캘린더를
# 만들지 않고 이미 있는 거래일 시퀀스를 그대로 재사용한다.
TRADING_DAY_AXIS_TICKER = "069500"

DISPLAY_DECIMALS = 1


def normalize_pct(value: float) -> float:
    """판정·표시 공통 정규화. 이 값 하나만 두 곳에서 쓴다."""
    return round(value, DISPLAY_DECIMALS)


def classify_decline(return_pct: Optional[float]) -> Optional[str]:
    """20거래일 수익률(%) → 구간 코드. 선정 구간 밖이면 None.

    경계는 **상한 배타 · 하한 포함** 이다 (PLAN §2.1):
      -8.0 은 `D8_10` (D5_8 의 `-8% < r` 을 만족하지 않는다).
      -10.0 은 `D10_PLUS`.
    """
    if return_pct is None:
        return None
    for state, low_exclusive, high_inclusive in _DECLINE_BANDS:
        if return_pct > high_inclusive:
            continue
        if low_exclusive is None or return_pct > low_exclusive:
            return state
    return None


@dataclass
class SelectedTicker:
    """선정된 종목 1건. 계좌는 합쳐 1행이다."""

    ticker: str
    name: str
    account_count: int
    # reason -> {"state": str, "value": Optional[float]}
    reasons: dict[str, dict[str, Any]] = field(default_factory=dict)
    # 보조 정보 — 상태 저장·변화 판정에 쓰지 않는다.
    drawdown_20d_pct: Optional[float] = None
    # 매입가 대비 손익률(%). 사용자 요청 2026-09-06 — "팔지 홀딩할지" 판단에
    # 20일 하락률만으로는 부족하다(20일 -6.7% 인데 매입 +89.2% 인 종목이 있다).
    # **보조 정보다.** fingerprint 에 넣지 않는다 — 넣으면 값이 미세하게 흔들릴
    # 때마다 매 슬롯 재발송된다.
    profit_loss_pct: Optional[float] = None

    @property
    def primary_reason(self) -> str:
        """PLAN §5.2 — 데이터 문제가 있으면 항상 그것이 primary.

        값이 틀렸을 가능성을 먼저 알려야 나머지 숫자를 믿을지 판단할 수 있다.
        `RECENT_DECLINE` 안에서는 구간으로 서열을 만들지 않는다.
        """
        if REASON_DATA_UNAVAILABLE in self.reasons:
            return REASON_DATA_UNAVAILABLE
        return REASON_RECENT_DECLINE

    @property
    def primary_state(self) -> str:
        return self.reasons[self.primary_reason]["state"]

    def fingerprint(self) -> str:
        """PLAN §4.2 — `ticker | sorted(reason:state)`.

        근거 값은 identity 에서 제외한다. 넣으면 -10.41 -> -10.43 에도 매 슬롯
        발송된다. 값 변화는 **구간이 바뀔 때만** 의미를 갖는다.
        """
        pairs = sorted(f"{r}:{v['state']}" for r, v in self.reasons.items())
        return "|".join([self.ticker, *pairs])


def reference_trading_day(
    axis_dates: list[str], today_kst: Optional[str], lookback: int
) -> Optional[str]:
    """실행일보다 **앞선 `lookback` 번째 거래일** (설계자 확정 2026-09-05).

    `axis_dates` 는 KRX 거래일 축(오름차순). 실행일 이전만 남기고 뒤에서
    `lookback` 번째를 고른다. 거래일이 모자라면 None.

    달력일 임계(`MAX_PRICE_STALE_DAYS`)는 **폐기됐다.** "며칠 전인가" 가 아니라
    "정확한 기준일 데이터가 있는가" 로 판정한다.
    """
    if not axis_dates or not today_kst or lookback <= 0:
        return None
    today = today_kst[:10]
    before = [d for d in axis_dates if d[:10] < today]
    if len(before) < lookback:
        return None
    return before[-lookback]


def close_on(history: list[tuple[str, float]], day: Optional[str]) -> Optional[float]:
    """`day` **그 날짜의** 종가. 없으면 None.

    더 오래된 종가로 대체하지 않는다 — 대체하면 20거래일이 아닌 구간의
    수익률을 20거래일이라고 보고하게 된다.
    """
    if not day:
        return None
    for d, c in reversed(history):
        if d[:10] == day:
            return c if c and c > 0 else None
        if d[:10] < day:
            break
    return None


def _is_same_day(day: Optional[str], today_kst: Optional[str]) -> bool:
    """`day` 가 실행일과 같은 날인가. 파싱 불가·미래·과거 모두 False (fail-closed).

    분자(runtime 현재가)의 유효성 판정에 쓴다. 과거 시각의 quote 는 장중 값이
    아니므로 그 종목만 `DATA_UNAVAILABLE_OR_STALE` 로 뺀다 (설계자 확정 표).
    """
    if not day or not today_kst:
        return False
    return day[:10] == today_kst[:10]


def _profit_loss_pct(
    current: Optional[float], avg_buy: Optional[float]
) -> Optional[float]:
    """매입가 대비 손익률(%) = `현재가 / 수량가중평균 매입가 - 1`.

    **현재가가 분자다.** 20거래일 수익률·고점 대비와 같은 값을 쓰고 분모만 다르다.
    둘 중 하나라도 없거나 0 이하면 None.

    매입가가 없다고 해서 **선정을 버리지 않는다** — 손익 표시만 생략한다.
    """
    if not current or current <= 0 or not avg_buy or avg_buy <= 0:
        return None
    return normalize_pct((current / avg_buy - 1.0) * 100.0)


def _drawdown_pct_over_window(
    history: list[tuple[str, float]],
    window_days: list[str],
    current: Optional[float],
) -> Optional[float]:
    """`window_days` 구간 고점 대비 하락률(%) = `현재가 / 기간 고점 - 1`.

    **분자는 runtime 현재가다.** 20거래일 수익률·매입 대비와 **같은 값**을 쓰고
    분모(기간 고점)만 다르다.

    2026-09-06 정정 (검증자 r11): 분자로 구간 마지막 **종가**(`closes[-1]`)를
    썼다. 그래서 현재가 80 · 구간 종가 전부 100 이면 계약상 `-20%` 인데 `0%` 가
    나왔다. 장중에 빠진 만큼이 고점 대비에 반영되지 않아, 판단용 수치가 실제보다
    얕은 하락으로 보고됐다.

    구간 데이터가 불완전하면 **보조값만 생략**한다(설계자 확정). 빠진 날이 있는
    채로 고점을 잡으면 하락이 얕게 나온다. 보조값이 없다고 해서 계산 가능한
    `RECENT_DECLINE` 까지 버리지는 않는다.
    """
    if not window_days or not current or current <= 0:
        return None
    by_date = {d[:10]: c for d, c in history if c and c > 0}
    closes = [by_date.get(d) for d in window_days]
    if any(c is None for c in closes):
        return None  # 구간 불완전 — 보조값만 생략
    peak = max(c for c in closes if c is not None)
    if not peak or peak <= 0:
        return None
    return normalize_pct((current / peak - 1.0) * 100.0)


def select_holdings(
    *,
    holdings: list[dict[str, Any]],
    price_history: dict[str, list[tuple[str, float]]],
    market_quotes: dict[str, Any],
    today_kst: Optional[str] = None,
    axis_dates: Optional[list[str]] = None,
    avg_buy_prices: Optional[dict[str, float]] = None,
) -> list[SelectedTicker]:
    """선정 결과. 이유가 없는 종목은 **결과에 넣지 않는다**.

    인자:
      holdings       : [{"ticker","name","account_group",...}] — 계좌별 행.
                       같은 ticker 가 여러 계좌에 있으면 **1건으로 합친다**.
      price_history  : {ticker: [(date, close), ...]} date ASC. 분모 원천.
      market_quotes  : {ticker: MarketQuote} — `current_price` · `price_asof`.
      axis_dates     : KRX 거래일 축(오름차순). 기준일 계산 원천.
      avg_buy_prices : {ticker: 수량 가중평균 매입가}. 없으면 손익률을 생략한다
                       (선정 자체는 그대로 한다).

    **분모 계약 (설계자 확정 2026-09-05)**

        기준일 = 거래일 축에서 실행일보다 앞선 20번째 거래일
        분모   = 그 ticker 의 **기준일 종가** (정확히 그 날짜)
        분자   = 실행 시점의 유효한 runtime 현재가 (price_asof 가 실행일)

    기준일 종가가 없으면 `DATA_UNAVAILABLE_OR_STALE`. 더 오래된 종가로
    대체하지 않는다. 달력일 임계는 쓰지 않는다.

    반환 순서는 `GROUP_ORDER` → 근거 값 악화순 → ticker (PLAN §5.3).
    """
    buy_prices = avg_buy_prices or {}
    axis = axis_dates or []
    base_day = reference_trading_day(axis, today_kst, LOOKBACK_TRADING_DAYS)
    # 보조값 구간: 기준일 다음 거래일 ~ 실행일 직전 거래일 (20 거래일).
    today = (today_kst or "")[:10]
    before_today = [d for d in axis if d[:10] < today] if today else []
    aux_window = before_today[-LOOKBACK_TRADING_DAYS:] if before_today else []
    by_ticker: dict[str, dict[str, Any]] = {}
    for h in holdings:
        t = h.get("ticker")
        if not t:
            continue
        entry = by_ticker.setdefault(t, {"name": h.get("name") or t, "accounts": 0})
        entry["accounts"] += 1
        if h.get("name"):
            entry["name"] = h["name"]

    selected: list[SelectedTicker] = []
    for ticker, meta in by_ticker.items():
        item = SelectedTicker(
            ticker=ticker, name=meta["name"], account_count=meta["accounts"]
        )
        history = price_history.get(ticker) or []
        quote = market_quotes.get(ticker)
        current = getattr(quote, "current_price", None) if quote else None
        base = close_on(history, base_day)

        # 설계자 확정 2026-09-05 —
        #   분모: 기준일 **그 날짜** 종가가 있어야 한다. 없으면 데이터 문제다.
        #   분자: quote 의 price_asof 가 **실행일**이어야 한다. 과거 시각 quote 는
        #         장중 값이 아니므로 그 종목만 뺀다.
        # 달력일 임계로 배제하지 않고, 오래된 종가로 대체하지도 않는다.
        quote_asof = getattr(quote, "price_asof", None) if quote else None
        numerator_ok = (
            bool(current) and current > 0 and _is_same_day(quote_asof, today_kst)
        )
        if not numerator_ok or not base or base <= 0:
            item.reasons[REASON_DATA_UNAVAILABLE] = {
                "state": STATE_ACTIVE,
                "value": None,
            }
            selected.append(item)
            continue

        # 매입가 대비 손익률. **분자는 20일 수익률·고점 대비와 같은 현재가**이고
        # 분모만 매입가로 다르다. 세 슬롯 모두 실행 시점 시세 기준이며 OPEN 만
        # 종가로 바꾸지 않는다 (사용자 확정 2026-09-06).
        item.profit_loss_pct = _profit_loss_pct(current, buy_prices.get(ticker))

        # 판정·저장·표시 모두 **같은 정규화 값**을 쓴다 (경계 불일치 방지).
        return_pct = normalize_pct((current / base - 1.0) * 100.0)
        state = classify_decline(return_pct)
        if state is None:
            continue  # 선정 이유 없음 — 표시하지 않는다.
        item.reasons[REASON_RECENT_DECLINE] = {
            "state": state,
            "value": return_pct,
        }
        item.drawdown_20d_pct = _drawdown_pct_over_window(history, aux_window, current)
        selected.append(item)

    return sort_selected(selected)


def sort_selected(items: list[SelectedTicker]) -> list[SelectedTicker]:
    """그룹 순서 → 근거 값 악화순 → ticker."""
    order = {key: i for i, key in enumerate(GROUP_ORDER)}

    def key(it: SelectedTicker):
        group = order.get((it.primary_reason, it.primary_state), len(order))
        value = it.reasons[it.primary_reason].get("value")
        return (group, value if value is not None else 0.0, it.ticker)

    return sorted(items, key=key)


def group_label(reason: str, state: str) -> str:
    if reason == REASON_DATA_UNAVAILABLE:
        return DATA_UNAVAILABLE_LABEL
    return DECLINE_STATE_LABEL.get(state, state)
