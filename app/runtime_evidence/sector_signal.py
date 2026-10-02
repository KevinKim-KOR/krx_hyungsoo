"""POC3-02C-OPS-02 — 사업군 대표 ETF 장중 판정 (설계자 §4-2).

승인된 `INTRADAY_ALERT_CONFIG` 의 27개 사업군 대표 ETF 를 보고 **신규 진입
검토 / 진입 회피** 후보를 고른다.

```text
진입 검토        당일 +1.5% 이상 +4.0% 미만 · 5일>0 · 20일>0 · 상승률 상위 20%
진입 회피－급락   당일 -1.5% 이하 · 하락률 하위 20%
진입 회피－추격   당일 +4.0% 이상
```

**매수·매도 예측이 아니라 초기 운영용 단순 규칙**이다(설계 §4-2). 수치는 코드
상수가 아니라 승인 PARAM 에서 온다 — 이후 백테스트·ML 로 교체할 수 있어야 한다.

## 가격 기준

당일 등락률은 **보유 경로와 같은 출처**를 쓴다 — Naver 무조정 D-1 대비 등락률
(`usable_day_return`). 조정계열 `etf_daily_price` 를 쓰지 않는다(설계자 §13-2).

5일·20일 수익률은 **무조정 일별 종가**(`krx_etf_daily_price_unadjusted`)에서
계산한다. 조정계열은 OCI 에서 하루 41종목만 갱신돼 대표 27개 중 4개만 커버한다
(PLAN §1-2 실측).

## 추세 기준일 (POC3-02D-OPS-03 · 확정 계약 5 · 8)

5일 · 20일은 **기대 T-1**(`trading_day_lag.expected_previous_trading_day`)과 그
거래일 **날짜**(d5 · d20)의 종가로 계산한다. 저장 행 위치로 세지 않는다.

```text
표 최신 저장일 ≠ 기대 T-1          → 「신규 진입 검토」 구역 전체 생략(ENTRY 0건)
d5 · d20 날짜가 이력 전체에 없음     → 구역 전체 생략(캘린더 없는 해의 빈 평일 포함)
활성 대표 중 T-1 종가 없는 종목 있음 → 구역 전체 생략(설계자 RESULT STEP 2 · 대표 100%)
활성 대표 목록을 모름               → 구역 전체 생략(설정을 읽지 못함)
대체 종목에 T-1 종가 없음           → 그 사업군만 ENTRY 제외
그 종목에 d5 · d20 날짜 종가 없음   → 그 사업군만 ENTRY 제외(21일 전 값으로 밀지 않는다)
```

대표 커버리지는 08:10 · 09:20 배치 기록과 같은 규칙(`intraday_config.representatives`)이다.

「진입 회피」(AVOID_*)는 당일 등락률만 쓰므로 그대로 판정한다.

## 하지 않는 것

- 전체 ETF 장중 조회 (설계 §2 금지)
- OCI 가 새 사업군·대표를 선정 (설계 §2 금지)
- 이력이 모자란 사업군을 추정값으로 메우기 — **그 사업군만 제외**하고 사유를 남긴다
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Collection, Optional

from app import trading_day_lag
from app.intraday_config.representatives import (
    COVERAGE_CONFIG_UNAVAILABLE,
    COVERAGE_REPRESENTATIVE_MISSING,
    RepresentativeCoverage,
    evaluate_coverage,
    representative_tickers,
)
from app.runtime_evidence.holdings_risk import usable_day_return
from app.runtime_evidence.holdings_selection import normalize_pct

# 판정 상태 — 보유 급등락(`D*`/`U*`) 과 **다른 축**이다. 섞지 않는다.
STATE_ENTRY_REVIEW = "ENTRY_REVIEW"
STATE_AVOID_DROP = "AVOID_DROP"
STATE_AVOID_CHASE = "AVOID_CHASE"

STATE_LABEL = {
    STATE_ENTRY_REVIEW: "신규 진입 검토",
    STATE_AVOID_DROP: "장중 급락",
    STATE_AVOID_CHASE: "단기 급등 · 추격 주의",
}

# 제외 사유 — 조용히 버리지 않는다.
REASON_NO_QUOTE = "no_quote"
REASON_NO_DAY_RETURN = "no_day_return"
REASON_SHORT_HISTORY = "short_history"
REASON_HELD = "held"
REASON_LOW_COVERAGE = "low_coverage"
REASON_PROVIDER_DOWN = "provider_down"
# POC3-02D-OPS-03 — 추세 기준일 미확인으로 **진입 검토만** 평가하지 못했다.
REASON_TREND_NOT_T1 = "trend_not_t1"  # 표 최신일 ≠ 기대 T-1 · 창 빈 날 (구역 생략)
REASON_TICKER_NOT_T1 = "ticker_not_t1"  # 그 종목에 T-1 종가 없음
# 설계자 RESULT STEP 2 — 대표 커버리지 미달로 「신규 진입 검토」 구역 생략.
REASON_CONFIG_UNAVAILABLE = COVERAGE_CONFIG_UNAVAILABLE
REASON_REPRESENTATIVE_MISSING = COVERAGE_REPRESENTATIVE_MISSING

# 설계자 §14-5 — primary 가 **이 비율 이상** 실패하면 provider 단위 장애로 보고
# 대체 조회를 한 건도 하지 않는다. ticker 한 건의 누락·오염과 구분하기 위한
# 선이다. provider 가 죽었는데 fallback 22개를 더 때리면 장애를 키운다.
PROVIDER_DOWN_FAILURE_RATIO = 0.5

# 표본이 이보다 적으면 **비율로 장애를 판정하지 않는다.** 사업군 1개짜리
# 구성에서 그 하나가 실패하면 100% 실패가 되는데, 그건 provider 장애가 아니라
# 그냥 ticker 한 건의 실패다 — 대체를 막을 이유가 없다.
PROVIDER_DOWN_MIN_SECTORS = 5

# 5일·20일 수익률의 **거래일 수**. 기대 T-1 에서 거래일 N 개 전 **날짜**의 종가가
# 분모다(POC3-02D-OPS-03 확정 계약 5 · 저장 행 위치로 세지 않는다).
LOOKBACK_5D = 5
LOOKBACK_20D = 20


@dataclass
class SectorSignal:
    """사업군 1건."""

    sector_key: str
    ticker: str
    name: str
    state: str
    day_return_pct: float
    return_5d_pct: Optional[float] = None
    return_20d_pct: Optional[float] = None
    rank: Optional[int] = None
    candidate_count: Optional[int] = None
    used_alternate: bool = False
    # 5일 · 20일의 기준일(= 기대 T-1). 추세를 확인하지 못했으면 `None`.
    trend_basis_date: Optional[str] = None

    def fingerprint(self) -> str:
        """`ticker#state`. **숫자는 넣지 않는다**(설계 §5).

        수치만 조금 달라지고 단계가 같으면 재발송하지 않기 위해서다.
        """
        return f"{self.ticker}#{self.state}"


@dataclass
class SectorOutcome:
    signals: list[SectorSignal] = field(default_factory=list)
    excluded: list[dict[str, Any]] = field(default_factory=list)
    evaluated_count: int = 0
    sector_count: int = 0
    coverage_pct: Optional[float] = None
    coverage_ok: bool = True
    provider_down: bool = False
    # POC3-02D-OPS-03 — 추세 기준일 판정과 「신규 진입 검토」 구역 생략 여부 · 사유.
    trend: Optional["TrendBasis"] = None
    entry_omitted: bool = False
    entry_omitted_reason: Optional[str] = None
    # 설계자 RESULT STEP 2 — 활성 대표의 T-1 종가 커버리지.
    representatives: Optional[RepresentativeCoverage] = None

    def by_state(self, state: str) -> list[SectorSignal]:
        return [s for s in self.signals if s.state == state]


@dataclass(frozen=True)
class TrendBasis:
    """5일 · 20일 추세 기준(확정 계약 5 · 8).

    `usable` 은 표 최신 저장일이 기대 T-1 과 **정확히 같고** d5 · d20 날짜가
    정해졌을 때만 참이다. lag 숫자로 판정하지 않는다(확정 계약 6).

    `missing_days` — 대표 · 대체 종목 이력에 **하나도** 없는 d5 · d20 날짜(연도 파일이
    없는 해는 저장 자료가 없는 평일을 휴장으로 건너뛰어 날짜를 정한다 · 한국 거래일
    계약 2026-09-11). 있으면 `usable=False` — 08:30 기초지수 창(`krx_store.CalendarWindow`)과 같은
    규칙으로 구역을 닫고 생략으로 센다(확정 계약 5 · 13).
    """

    expected: Optional[str]
    table_latest: Optional[str]
    d5: Optional[str] = None
    d20: Optional[str] = None
    missing_days: tuple[str, ...] = ()

    @property
    def usable(self) -> bool:
        return (
            self.expected is not None
            and self.table_latest == self.expected
            and self.d5 is not None
            and self.d20 is not None
            and not self.missing_days
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "expected_previous_trading_day": self.expected,
            "table_latest": self.table_latest,
            "d5": self.d5,
            "d20": self.d20,
            "missing_days": list(self.missing_days),
            "usable": self.usable,
        }


def load_unadjusted_history(
    tickers: list[str], *, db_path: Path
) -> dict[str, list[tuple[str, float]]]:
    """무조정 일별 종가 `{ticker: [(date, close)]}` 오름차순.

    읽기 전용으로 연다. 이 경로는 **절대 쓰지 않는다.**
    """
    out: dict[str, list[tuple[str, float]]] = {t: [] for t in tickers}
    if not tickers:
        return out
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        marks = ",".join("?" * len(tickers))
        rows = con.execute(
            "SELECT ticker, date, close FROM krx_etf_daily_price_unadjusted "
            f"WHERE ticker IN ({marks}) AND close > 0 ORDER BY ticker, date ASC",
            tickers,
        ).fetchall()
    except sqlite3.Error:
        # 테이블 부재·손상 — 사업군 경로만 비운다. 보유 경로를 막지 않는다.
        return out
    finally:
        con.close()
    for ticker, date, close in rows:
        out.setdefault(ticker, []).append((str(date), float(close)))
    return out


def latest_unadjusted_date(*, db_path: Path) -> Optional[str]:
    """무조정 표에서 종가가 있는 최신 저장일. 읽기 전용 · 실패하면 `None`.

    `None` 이면 추세 기준일을 확인하지 못한 것이다 — 진입 검토를 닫는다.
    """
    try:
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except sqlite3.Error:
        return None
    try:
        # 날짜 내림차순 1행 — (date, ticker) 기본키 색인을 거꾸로 읽는다(매 틱 호출).
        row = con.execute(
            "SELECT date FROM krx_etf_daily_price_unadjusted WHERE close > 0 "
            "ORDER BY date DESC LIMIT 1"
        ).fetchone()
    except sqlite3.Error:
        return None
    finally:
        con.close()
    return str(row[0])[:10] if row and row[0] else None


def resolve_trend_basis(
    today_kst: Optional[str],
    *,
    table_latest: Optional[str],
    calendar_dir: Optional[Path] = None,
    stored_days: Optional[Collection[str]] = None,
) -> TrendBasis:
    """기대 T-1 과 그 거래일 날짜 d5 · d20 (확정 계약 5 · 6).

    표 최신일이 기대 T-1 이 아니면 d5 · d20 을 정하지 않는다 — 그날은 진입
    검토를 계산하지 않는다(T-2 로 대신하지 않는다).

    `stored_days` — 대표 · 대체 종목 이력에 있는 날짜. 넘기면 창(21거래일)의 빈
    날을 본다(`TrendBasis.missing_days`). 없으면 보지 않는다(순수 호출 · 테스트).
    """
    expected = (
        trading_day_lag.expected_previous_trading_day(
            str(today_kst)[:10], calendar_dir=calendar_dir
        )
        if today_kst
        else None
    )
    if expected is None or table_latest != expected:
        return TrendBasis(expected=expected, table_latest=table_latest)
    dates = trading_day_lag.trading_window_dates(
        expected,
        calendar_dir=calendar_dir,
        lookbacks=(LOOKBACK_5D, LOOKBACK_20D),
        stored=stored_days,
    )
    if not dates:
        return TrendBasis(expected=expected, table_latest=table_latest)
    d5, d20 = dates[1], dates[2]
    missing: tuple[str, ...] = ()
    if stored_days is not None:
        missing = tuple(sorted({d for d in (d5, d20) if d not in stored_days}))
    return TrendBasis(
        expected=expected,
        table_latest=table_latest,
        d5=d5,
        d20=d20,
        missing_days=missing,
    )


def trend_returns(
    history: list[tuple[str, float]], trend: TrendBasis
) -> tuple[Optional[float], Optional[float], Optional[str]]:
    """`(5일 %, 20일 %, 빠진 사유)` — **거래일 날짜**의 종가만 쓴다(확정 계약 5).

    저장 행 위치로 세면 하루가 빠질 때 6 · 21일 전 값이 5 · 20일로 보고된다.
    그 날짜 종가가 없으면 그 수익률은 `None` 이다(더 오래된 값으로 대체하지
    않는다 — `close_on` 과 같은 원칙).
    """
    if not trend.usable:
        return None, None, REASON_TREND_NOT_T1
    by_date = {str(d)[:10]: c for d, c in history if c and c > 0}
    last = by_date.get(str(trend.expected))
    if last is None:
        return None, None, REASON_TICKER_NOT_T1
    base5, base20 = by_date.get(str(trend.d5)), by_date.get(str(trend.d20))
    r5 = normalize_pct((last / base5 - 1.0) * 100.0) if base5 else None
    r20 = normalize_pct((last / base20 - 1.0) * 100.0) if base20 else None
    if r5 is None or r20 is None:
        return r5, r20, REASON_SHORT_HISTORY
    return r5, r20, None


def _top_cut(n: int, top_pct: float) -> int:
    """상위 `top_pct`% 에 드는 **개수**. 최소 1개는 보장한다.

    27개의 20% 는 5.4 → 5개다. 내림하되 0 이 되지 않게 한다.
    """
    if n <= 0:
        return 0
    return max(1, int(n * top_pct / 100.0))


def is_entry_band(
    *, day_return_pct: float, is_top_riser: bool, policy: dict[str, Any]
) -> bool:
    """**창 수익률을 빼고** 진입 검토 모양인가(당일 등락률 + 순위만).

    `classify_sector` 는 5일·20일까지 봐서 이력이 모자라면 그냥 `None` 을 낸다.
    그러면 "진입 후보가 될 뻔했는데 이력이 없어 빠졌다" 를 구분할 수 없다 —
    감사 기록이 사라진다. 그 구분을 여기서 한다.
    """
    entry_min = float(policy["sector_entry_min_pct"])
    chase = float(policy["sector_chase_pct"])
    return is_top_riser and entry_min <= day_return_pct < chase


def classify_sector(
    *,
    day_return_pct: float,
    return_5d_pct: Optional[float],
    return_20d_pct: Optional[float],
    is_top_riser: bool,
    is_bottom_faller: bool,
    policy: dict[str, Any],
) -> Optional[str]:
    """설계 §4-2 표 그대로. 해당 없으면 `None`.

    판정 순서가 중요하다 — **추격 주의가 진입 검토보다 앞선다.** `+4.0%` 이상은
    진입 검토 상한 밖이므로 겹치지 않지만, 임계가 PARAM 으로 바뀔 수 있어
    순서로도 못박는다.
    """
    chase = float(policy["sector_chase_pct"])
    entry_min = float(policy["sector_entry_min_pct"])
    avoid_drop = float(policy["sector_avoid_drop_pct"])

    if day_return_pct >= chase:
        return STATE_AVOID_CHASE
    if day_return_pct <= avoid_drop and is_bottom_faller:
        return STATE_AVOID_DROP
    if (
        entry_min <= day_return_pct < chase
        and is_top_riser
        and return_5d_pct is not None
        and return_5d_pct > 0
        and return_20d_pct is not None
        and return_20d_pct > 0
    ):
        return STATE_ENTRY_REVIEW
    return None


def select_sector_signals(
    *,
    sectors: list[dict[str, Any]],
    market_quotes: dict[str, Any],
    history: dict[str, list[tuple[str, float]]],
    today_kst: Optional[str],
    policy: dict[str, Any],
    held_tickers: Optional[set[str]] = None,
    trend: Optional[TrendBasis] = None,
) -> SectorOutcome:
    """사업군 후보 선정.

    `held_tickers` 에 든 대표는 **신규 진입 후보에서 뺀다**(설계 §4-2) — 보유
    구역에만 나온다. 제외 사유는 남긴다.

    `trend` — 추세 기준(POC3-02D-OPS-03). 없거나 `usable` 이 아니면 **진입 검토를
    하나도 내지 않는다**(확정 계약 8 · fail-closed). 회피 판정은 그대로다.

    대표 커버리지(설계자 RESULT STEP 2) — 활성 대표 전부가 `history` 에 기대 T-1
    종가를 가져야 진입 검토를 낸다. 아니면 구역 전체를 생략한다(회피는 그대로).
    """
    out = SectorOutcome()
    held = held_tickers or set()
    basis = trend if trend is not None else TrendBasis(None, None)
    out.trend = basis
    t1 = basis.expected
    with_t1 = {
        t
        for t, rows in history.items()
        for d, c in rows
        if c and c > 0 and str(d)[:10] == t1
    }
    reps = evaluate_coverage(representative_tickers(sectors), with_t1, expected=t1)
    out.representatives = reps
    # 구역 생략 사유 — 추세 기준일 미확인이 먼저다(그날은 대표 전부 T-1 이 없다).
    entry_block = (
        REASON_TREND_NOT_T1 if not basis.usable else (None if reps.ok else reps.status)
    )
    out.entry_omitted = bool(sectors) and entry_block is not None
    out.entry_omitted_reason = entry_block if out.entry_omitted else None

    # 0차 — primary 결과부터 본다. **provider 단위 장애를 먼저 판정**한다.
    #
    # 설계자 §14-5 — ticker 한 건의 누락·오염이면 그 사업군만 대체 1회를
    # 허용하지만, provider 가 통째로 죽었으면 대체를 **한 건도** 하지 않는다.
    # primary 27개가 전부 실패한 뒤 fallback 22개를 더 때리면 장애를 키운다.
    primary_ok = 0
    for s in sectors:
        t = str(((s or {}).get("representative") or {}).get("ticker") or "")
        if usable_day_return(market_quotes.get(t), today_kst) is not None:
            primary_ok += 1
    provider_down = len(sectors) >= PROVIDER_DOWN_MIN_SECTORS and (
        primary_ok / len(sectors) < (1.0 - PROVIDER_DOWN_FAILURE_RATIO)
    )
    out.provider_down = provider_down
    if provider_down:
        out.excluded.append(
            {
                "sector_key": None,
                "ticker": None,
                "reason": REASON_PROVIDER_DOWN,
                "primary_ok": primary_ok,
                "total": len(sectors),
            }
        )

    # 1차 — 당일 등락률이 쓸 수 있는 사업군만 모은다.
    usable: list[tuple[dict[str, Any], str, str, float, bool]] = []
    for s in sectors:
        key = str(s.get("sector_key") or "")
        rep = s.get("representative") or {}
        alt = s.get("alternate") or {}
        picked, used_alt = rep, False
        ret = usable_day_return(
            market_quotes.get(str(rep.get("ticker") or "")), today_kst
        )
        if ret is None and alt.get("ticker") and not provider_down:
            # 대표 실패 시에만 대체 **1개**. 재귀 대체 금지(설계자 §13-4).
            # provider 장애면 여기 오지 않는다(§14-5).
            alt_ret = usable_day_return(
                market_quotes.get(str(alt.get("ticker") or "")), today_kst
            )
            if alt_ret is not None:
                picked, used_alt, ret = alt, True, alt_ret
        ticker = str(picked.get("ticker") or "")
        if ret is None:
            out.excluded.append(
                {
                    "sector_key": key,
                    "ticker": ticker,
                    "reason": (
                        REASON_NO_QUOTE
                        if market_quotes.get(ticker) is None
                        else REASON_NO_DAY_RETURN
                    ),
                }
            )
            continue
        usable.append((s, key, ticker, ret, used_alt))

    out.evaluated_count = len(usable)
    out.sector_count = len(sectors)
    out.coverage_pct = (
        normalize_pct(len(usable) / len(sectors) * 100.0) if sectors else None
    )
    if not usable:
        out.coverage_ok = False
        return out

    # 설계자 §14-4 — 상대순위 최소 커버리지 Gate.
    #
    # 상대순위(상위/하위 20%)는 **전체 사업군을 봐야** 의미가 있다. 조회 성공분
    # 안에서만 매기면 27개 중 3개만 살아남아도 그중 하나가 "상위 20%" 가 된다.
    # 그건 실패 격리가 아니라 **왜곡**이다.
    #
    # 미달하면 사업군 구역을 통째로 생략한다. 보유 급등락 경로는 계속 간다.
    min_cov = float(policy["sector_min_coverage_pct"])
    if out.coverage_pct is not None and out.coverage_pct < min_cov:
        out.coverage_ok = False
        out.excluded.append(
            {
                "sector_key": None,
                "ticker": None,
                "reason": REASON_LOW_COVERAGE,
                "coverage_pct": out.coverage_pct,
                "required_pct": min_cov,
                "evaluated": len(usable),
                "total": len(sectors),
            }
        )
        return out

    # 2차 — 순위. **평가 가능한 사업군 안에서** 매긴다. 조회 실패한 사업군을
    # 분모에 넣으면 상위 20% 가 실제보다 좁아진다.
    ordered_desc = sorted(usable, key=lambda x: (-x[3], x[2]))
    ordered_asc = sorted(usable, key=lambda x: (x[3], x[2]))
    cut = _top_cut(len(usable), float(policy["sector_rank_top_pct"]))
    top_risers = {t[2] for t in ordered_desc[:cut]}
    bottom_fallers = {t[2] for t in ordered_asc[:cut]}
    rank_of = {t[2]: i + 1 for i, t in enumerate(ordered_desc)}

    for s, key, ticker, ret, used_alt in usable:
        # 확정 계약 5 — 기대 T-1 · d5 · d20 **날짜**의 종가. 없으면 `None`.
        r5, r20, missing = trend_returns(history.get(ticker) or [], basis)
        # 구역 생략이면 진입 판정에만 추세를 넘기지 않는다(회피 판정은 그대로).
        e5, e20 = (None, None) if entry_block else (r5, r20)
        is_top = ticker in top_risers
        state = classify_sector(
            day_return_pct=ret,
            return_5d_pct=e5,
            return_20d_pct=e20,
            is_top_riser=is_top,
            is_bottom_faller=ticker in bottom_fallers,
            policy=policy,
        )
        if state is None:
            # 진입 후보가 될 뻔했는데 **추세를 계산하지 못해** 빠진 경우를 구분해
            # 남긴다 — 표 최신일 ≠ T-1 · 대표 커버리지 미달 · 종목 T-1 없음 ·
            # d5/d20 날짜 없음. 추정값으로 메우지 않는다.
            if is_entry_band(
                day_return_pct=ret, is_top_riser=is_top, policy=policy
            ) and (e5 is None or e20 is None):
                out.excluded.append(
                    {
                        "sector_key": key,
                        "ticker": ticker,
                        "reason": entry_block or missing or REASON_SHORT_HISTORY,
                    }
                )
            continue
        if ticker in held:
            # 보유 중이면 신규 진입 후보가 아니다 — 보유 구역에만 실린다.
            out.excluded.append(
                {"sector_key": key, "ticker": ticker, "reason": REASON_HELD}
            )
            continue
        rep_name = str((s.get("representative") or {}).get("short_name") or "")
        alt_name = str((s.get("alternate") or {}).get("short_name") or "")
        out.signals.append(
            SectorSignal(
                sector_key=key,
                ticker=ticker,
                name=(alt_name if used_alt else rep_name) or ticker,
                state=state,
                day_return_pct=ret,
                return_5d_pct=r5,
                return_20d_pct=r20,
                rank=rank_of.get(ticker),
                candidate_count=len(usable),
                used_alternate=used_alt,
                trend_basis_date=basis.expected if basis.usable else None,
            )
        )
    return out


__all__ = [
    "LOOKBACK_20D",
    "LOOKBACK_5D",
    "REASON_CONFIG_UNAVAILABLE",
    "REASON_HELD",
    "REASON_LOW_COVERAGE",
    "PROVIDER_DOWN_FAILURE_RATIO",
    "PROVIDER_DOWN_MIN_SECTORS",
    "REASON_PROVIDER_DOWN",
    "REASON_REPRESENTATIVE_MISSING",
    "REASON_NO_DAY_RETURN",
    "REASON_NO_QUOTE",
    "REASON_SHORT_HISTORY",
    "REASON_TICKER_NOT_T1",
    "REASON_TREND_NOT_T1",
    "STATE_AVOID_CHASE",
    "STATE_AVOID_DROP",
    "STATE_ENTRY_REVIEW",
    "STATE_LABEL",
    "SectorOutcome",
    "SectorSignal",
    "TrendBasis",
    "classify_sector",
    "is_entry_band",
    "latest_unadjusted_date",
    "load_unadjusted_history",
    "resolve_trend_basis",
    "select_sector_signals",
    "trend_returns",
]
