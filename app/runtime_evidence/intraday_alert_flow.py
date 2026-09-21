"""POC3-02C-OPS-02 — 장중 급등락 조립 (설계자 §6·§9).

보유 급락·급등·사업군을 한 메시지로 합친다. **실패 격리가 이 모듈의 존재
이유**다.

```text
보유 경로    먼저. 끝까지 간다.
사업군 경로  try/except 로 감싼다. 실패하면 그 구역만 빠진다.
```

설계 §9 — "신규 사업군 경로 실패가 기존 보유 급락 경로를 막으면 안 됨".
config 누락·비활성·손상·DB 부재·이력 부족을 전부 여기서 흡수한다.

## 상한 (§6)

```text
회차당 Telegram = 최대 1건   (이 모듈은 본문 1개만 만든다)
일일 조건형     = 최대 4건   (상태 파일의 sent_today 로 센다)
구역별          = 최대 3종목
```

일일 상한에 걸리면 **본문을 만들지 않는다.** 잘린 신호는 이력에 남긴다.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from app.runtime_evidence.holdings_risk import (
    select_surge_holdings,
    usable_day_return,
)
from app.runtime_evidence.intraday_alert_render import (
    SectionPlan,
    build_section_plan,
    render_intraday_alert,
)
from app.runtime_evidence.sector_signal import (
    REASON_HELD,
    REASON_NO_DAY_RETURN,
    REASON_NO_QUOTE,
    SectorOutcome,
    SectorSignal,
    load_unadjusted_history,
    select_sector_signals,
)
from app.runtime_evidence.sector_signal_state import (
    SectorChangeSet,
    compute_sector_changes,
    load_sector_state,
)

DEFAULT_MARKET_DB = Path("state/market/market_data.sqlite")

# 보유 급등 신호의 `sector_key`. 상태 파일에서 사업군 entry 와 보유 entry 를
# 가르는 유일한 표식이라 상수로 못박는다(설계자 D2 — 범위 분리).
HELD_SECTOR_KEY = "보유"

REASON_DAILY_CAP = "daily_cap_reached"
REASON_NO_SIGNAL = "no_signal"


@dataclass
class IntradayAssembly:
    message_text: str = ""
    plan: Optional[SectionPlan] = None
    sector: SectorOutcome = field(default_factory=SectorOutcome)
    changes: Optional[SectorChangeSet] = None
    # 보유 급등도 억제 대상이다 — 같은 급등이 유지되는데 매 틱 보내면 안 된다.
    surge_changes: Optional[SectorChangeSet] = None
    # 상태 저장 대상 = 사업군 + 급등. 두 목록의 저장 시점이 다르다 —
    # `observed` 는 **매 회차** 관측 저장(`save_observation`), `sent_signals` 는
    # **전송 성공 뒤에만** 발송 상태 저장(`save_sector_state`) 에 쓰인다.
    observed: list[Any] = field(default_factory=list)
    sent_signals: list[Any] = field(default_factory=list)
    # 평가 **불가** 범위 (설계자 D2). 여기 든 ticker 는 관측 저장에서 건드리지
    # 않는다 — 평가 못 한 것을 "회복" 으로 기록하면 지속 신호가 cooldown 뒤
    # 재발송된다. `observed` 에 없는 것 중 이 집합에 **없는** 것만 회복이다.
    unevaluable: set[str] = field(default_factory=set)
    skip_reason: Optional[str] = None
    # 일일 조건형 상한 도달 — **보유 급락 본문까지 막는다**(설계 §6).
    # `holdings_risk_alert` 자체가 조건형 PUSH 이므로 "이후 조건형 억제" 는
    # 이 종류 전체를 뜻한다.
    daily_cap_reached: bool = False
    sector_error: Optional[str] = None
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def will_send(self) -> bool:
        return bool(self.message_text)


def _as_signal(item: Any) -> SectorSignal:
    """보유 급등 항목을 억제 판정용 `SectorSignal` 로 감싼다.

    상태 파일 entries 는 ticker 키 + `state` 필드다. 급등(`U*`)과 사업군 상태
    (`AVOID_*`·`ENTRY_REVIEW`)는 값이 겹치지 않아 한 파일을 공유해도 섞이지
    않는다. 급락(`D*`)은 이 파일이 아니라 `holdings_risk_state` 가 억제한다.
    `fingerprint`(`ticker#state`)는 저장 필드가 아닌 파생 식별자다(설계 §15-2).
    """
    pct = getattr(item, "day_drop_pct", None)
    if pct is None:
        pct = getattr(item, "day_return_pct", None)
    return SectorSignal(
        sector_key=HELD_SECTOR_KEY,
        ticker=getattr(item, "ticker", ""),
        name=getattr(item, "name", "") or getattr(item, "ticker", ""),
        state=getattr(item, "state", ""),
        day_return_pct=float(pct or 0.0),
    )


def _load_active_sectors(logger: Any = None) -> list[dict[str, Any]]:
    """승인·활성 사업군. **실패하면 빈 목록** — 보유 경로를 막지 않는다."""
    try:
        from app.intraday_config import store

        active = store.get_active()
        if not active:
            return []
        payload = json.loads(active["payload_json"])
        uni = payload.get("sector_representative_universe") or {}
        sectors = uni.get("sectors")
        return sectors if isinstance(sectors, list) else []
    except Exception as e:  # noqa: BLE001
        if logger is not None:
            logger.warning("사업군 설정 읽기 실패(무시): %s", e)
        return []


def active_policy(logger: Any = None) -> Optional[dict[str, Any]]:
    """활성 버전의 판정 PARAM. **`enabled=false` 면 `None`**(설계 §10).

    검증 완료 전에는 켜지지 않는다. 여기서 임의 기본값으로 대체하지 않는다 —
    승인받지 않은 수치로 발송하는 셈이 된다.
    """
    try:
        from app.intraday_config import store

        active = store.get_active()
        if not active:
            return None
        payload = json.loads(active["payload_json"])
        policy = payload.get("intraday_alert_policy") or {}
        if not policy.get("enabled"):
            return None
        return policy
    except Exception as e:  # noqa: BLE001
        if logger is not None:
            logger.warning("장중 정책 읽기 실패(무시): %s", e)
        return None


def fetch_alternate_quotes(
    sectors: list[dict[str, Any]],
    market_quotes: dict[str, Any],
    today_kst: Optional[str],
    *,
    fetch_many: Any = None,
    logger: Any = None,
) -> dict[str, Any]:
    """대표가 실패한 사업군의 **대체 ETF 만** 한 번 조회한다(설계 §2 · §14-5).

    정기 조회 대상(`collect_target_tickers`)에는 대체가 들어 있지 않다 —
    넣으면 정상일 때도 22종목을 매 틱 더 때린다. 실패한 것만 여기서 따로 부른다.

    **provider 단위 장애면 한 건도 부르지 않는다.** primary 가 과반 실패했는데
    fallback 을 또 때리면 장애를 키운다.

    반환은 **추가된 quote 만** 담은 dict 다. 실패해도 예외를 올리지 않는다.
    """
    from app.runtime_evidence.sector_signal import (
        PROVIDER_DOWN_FAILURE_RATIO,
        PROVIDER_DOWN_MIN_SECTORS,
    )

    need: list[str] = []
    primary_ok = 0
    for s in sectors:
        rep = ((s or {}).get("representative") or {}).get("ticker")
        alt = ((s or {}).get("alternate") or {}).get("ticker")
        if usable_day_return(market_quotes.get(str(rep or "")), today_kst) is not None:
            primary_ok += 1
        elif isinstance(alt, str) and alt and alt not in market_quotes:
            need.append(alt)
    if not need:
        return {}
    if len(sectors) >= PROVIDER_DOWN_MIN_SECTORS and (
        primary_ok / len(sectors) < (1.0 - PROVIDER_DOWN_FAILURE_RATIO)
    ):
        if logger is not None:
            logger.info("provider 장애 판정 — 대체 %d종목 조회 생략", len(need))
        return {}
    try:
        if fetch_many is None:
            from app import market_naver

            fetch_many = market_naver.fetch_many
        out: dict[str, Any] = {}
        for r in fetch_many(sorted(set(need))) or []:
            q = getattr(r, "quote", None)
            t = getattr(r, "ticker", None)
            if q is not None and t:
                out[t] = q
        return out
    except Exception as e:  # noqa: BLE001 - 보유 경로를 막지 않는다
        if logger is not None:
            logger.warning("대체 ETF 조회 실패(격리): %s", e)
        return {}


def build_sector_outcome(
    *,
    market_quotes: dict[str, Any],
    today_kst: Optional[str],
    policy: dict[str, Any],
    held_tickers: set[str],
    db_path: Path = DEFAULT_MARKET_DB,
    fetch_many: Any = None,
    logger: Any = None,
) -> tuple[SectorOutcome, Optional[str]]:
    """사업군 후보. **절대 예외를 올리지 않는다** — `(결과, 오류문자열)`."""
    try:
        sectors = _load_active_sectors(logger)
        if not sectors:
            return SectorOutcome(), None
        # 대표 실패분의 대체를 **여기서 한 번** 채운다. 없으면 평가 함수가
        # 대체를 볼 방법이 없다(검증자 지적).
        extra = fetch_alternate_quotes(
            sectors, market_quotes, today_kst, fetch_many=fetch_many, logger=logger
        )
        if extra:
            market_quotes = {**market_quotes, **extra}
        tickers = []
        for s in sectors:
            for who in ("representative", "alternate"):
                t = ((s or {}).get(who) or {}).get("ticker")
                if isinstance(t, str) and t:
                    tickers.append(t)
        history = load_unadjusted_history(sorted(set(tickers)), db_path=db_path)
        return (
            select_sector_signals(
                sectors=sectors,
                market_quotes=market_quotes,
                history=history,
                today_kst=today_kst,
                policy=policy,
                held_tickers=held_tickers,
            ),
            None,
        )
    except Exception as e:  # noqa: BLE001 - 보유 경로를 막지 않는다
        if logger is not None:
            logger.warning("사업군 경로 실패(격리): %s", e)
        return SectorOutcome(), f"{type(e).__name__}: {str(e)[:200]}"


# 사업군 경로가 "평가했으나 조건 미충족" 이 아니라 **평가 자체를 못 한** 사유.
# `short_history` 는 제외한다 — 당일 등락률은 쓸 수 있었고 진입 분기만
# 미정이므로, 급락·추격 조건은 정상 평가된 것이다.
UNEVALUABLE_REASONS = frozenset({REASON_NO_QUOTE, REASON_NO_DAY_RETURN, REASON_HELD})


def _unevaluable_tickers(
    *,
    sector: SectorOutcome,
    sector_error: Optional[str],
    previous: Any,
    holding_rows: list[dict[str, Any]],
    market_quotes: dict[str, Any],
    today_kst: Optional[str],
) -> set[str]:
    """이번 회차에 **평가할 수 없었던** ticker (설계자 D2).

    범위를 분리한다 — 사업군이 통째로 무너져도 정상 평가된 보유는 갱신한다.

    ```text
    사업군 전체 장애·커버리지 미달 → 이전 사업군 entries 전체 보존
    특정 사업군만 평가 불가        → 그 **사업군**(sector_key) 의 entry 보존
    보유 ticker 등락률 없음        → 그 보유 entry 만 보존
    ```

    사업군 보존은 ticker 가 아니라 **`sector_key` 단위**다. 직전 회차가 대체
    ETF 로 저장됐다면 이번 회차의 대표 ticker 와 다르므로, ticker 로만 잡으면
    그 entry 가 회복으로 기록된다(검증자 실측 `ALT000 True → False`).
    """
    keep: set[str] = set()
    rows = [
        (str(tk), row)
        for tk, row in (getattr(previous, "entries", None) or {}).items()
        if isinstance(row, dict)
    ]
    sector_down = bool(sector_error) or sector.provider_down or not sector.coverage_ok
    if sector_down:
        # 이전 기록 중 **사업군** 것만 — 보유(`sector_key="보유"`)는 건드리지 않는다.
        keep.update(tk for tk, row in rows if row.get("sector_key") != HELD_SECTOR_KEY)
    down_keys = {
        str(ex.get("sector_key"))
        for ex in sector.excluded or []
        if ex.get("reason") in UNEVALUABLE_REASONS and ex.get("sector_key")
    }
    for ex in sector.excluded or []:
        if ex.get("reason") in UNEVALUABLE_REASONS and ex.get("ticker"):
            keep.add(str(ex["ticker"]))
    if down_keys:
        keep.update(tk for tk, row in rows if str(row.get("sector_key")) in down_keys)
    for row in holding_rows or []:
        ticker = str(row.get("ticker") or "")
        if ticker and usable_day_return(market_quotes.get(ticker), today_kst) is None:
            keep.add(ticker)
    return keep


def assemble_intraday_alert(
    *,
    held_drop: list[Any],
    holding_rows: list[dict[str, Any]],
    market_quotes: dict[str, Any],
    today_kst: Optional[str],
    now_kst: datetime,
    state_path: Path,
    slot_label: str,
    quote_asof: Optional[str] = None,
    base_close_date: Optional[str] = None,
    db_path: Path = DEFAULT_MARKET_DB,
    logger: Any = None,
) -> IntradayAssembly:
    """한 회차 조립. `held_drop` 은 **이미 선정된** 보유 급락 목록이다.

    보유 급락을 여기서 다시 계산하지 않는다 — 기존 경로가 억제·상태까지 이미
    처리했다. 그 결과를 받아 합치기만 한다.
    """
    out = IntradayAssembly()

    policy = active_policy(logger)
    if policy is None:
        # 검증 전에는 여기서 끝난다. 보유 급락은 기존 경로가 이미 보냈다.
        out.skip_reason = "policy_disabled"
        out.diagnostics["intraday_policy_enabled"] = False
        return out
    out.diagnostics["intraday_policy_enabled"] = True

    held_tickers = {r["ticker"] for r in holding_rows if r.get("ticker")}

    # 보유 급등 — 실패해도 급락을 막지 않는다.
    try:
        held_surge = select_surge_holdings(
            holdings=holding_rows,
            market_quotes=market_quotes or {},
            today_kst=today_kst,
        )
    except Exception as e:  # noqa: BLE001
        if logger is not None:
            logger.warning("보유 급등 선정 실패(격리): %s", e)
        held_surge = []

    sector, sector_error = build_sector_outcome(
        market_quotes=market_quotes or {},
        today_kst=today_kst,
        policy=policy,
        held_tickers=held_tickers,
        db_path=db_path,
        logger=logger,
    )
    out.sector, out.sector_error = sector, sector_error

    previous = load_sector_state(state_path, today_kst=today_kst)
    out.unevaluable = _unevaluable_tickers(
        sector=sector,
        sector_error=sector_error,
        previous=previous,
        holding_rows=holding_rows,
        market_quotes=market_quotes or {},
        today_kst=today_kst,
    )
    cooldown = int(policy["cooldown_minutes"])
    changes = compute_sector_changes(
        signals=sector.signals,
        previous=previous,
        now_kst=now_kst,
        cooldown_minutes=cooldown,
    )
    out.changes = changes

    # 보유 급등도 **같은 억제 규칙**을 탄다(검증자 지적). 급락은 기존
    # `holdings_risk_state` 가 이미 억제하므로 여기서 또 보지 않는다.
    surge_signals = [_as_signal(i) for i in held_surge]
    surge_changes = compute_sector_changes(
        signals=surge_signals,
        previous=previous,
        now_kst=now_kst,
        cooldown_minutes=cooldown,
    )
    out.surge_changes = surge_changes
    sent_surge_tickers = {s.ticker for s in surge_changes.send}
    held_surge = [i for i in held_surge if i.ticker in sent_surge_tickers]

    # 관측 목록 — 조립 단계에서 **매 회차** 저장된다(`save_observation`).
    # 발송 목록(`sent_signals`)은 구역 상한을 적용한 **뒤에** 확정한다 — 아래.
    out.observed = list(sector.signals) + surge_signals

    # 일일 상한 — 걸리면 본문을 만들지 않는다(§6).
    max_day = int(policy["max_sends_per_day"])
    if previous.comparable and previous.sent_today >= max_day:
        out.skip_reason = REASON_DAILY_CAP
        out.daily_cap_reached = True
        out.diagnostics["intraday_sent_today"] = previous.sent_today
        out.diagnostics["intraday_daily_cap_reached"] = True
        return out

    plan = build_section_plan(
        held_drop=list(held_drop),
        held_surge=held_surge,
        sector_signals=changes.send,
        max_items_per_section=int(policy["max_items_per_section"]),
    )
    out.plan = plan
    if plan.is_empty():
        out.skip_reason = REASON_NO_SIGNAL
        return out

    # 발송 목록 = **본문에 실제로 실리는 것**만. 구역 상한에 잘려 `plan.dropped`
    # 로 간 신호에 `last_sent_at` 을 찍으면 다음 틱에 "지속 중" 으로 억제돼
    # 지속되는 동안 한 번도 나가지 못한다(설계 §15-2 4항 — 발송 성공은 해당
    # 신호의 `last_sent_at` 갱신으로 판정한다). 잘린 신호는 §6 대로
    # `dropped` 이력에만 남긴다.
    carried_sector = {
        (s.ticker, s.state) for s in plan.avoid_drop + plan.avoid_chase + plan.entry
    }
    carried_surge = {getattr(i, "ticker", None) for i in plan.held_surge}
    out.sent_signals = [
        s for s in changes.send if (s.ticker, s.state) in carried_sector
    ] + [s for s in surge_changes.send if s.ticker in carried_surge]

    out.message_text = render_intraday_alert(
        plan,
        slot_label=slot_label,
        quote_asof=quote_asof,
        base_close_date=base_close_date,
    )
    out.diagnostics.update(
        {
            "intraday_held_drop_count": len(plan.held_drop),
            "intraday_held_surge_count": len(plan.held_surge),
            "intraday_sector_signal_count": len(sector.signals),
            "intraday_sector_sent_count": len(changes.send),
            "intraday_sector_suppressed_count": len(changes.suppressed),
            "intraday_sector_excluded_count": len(sector.excluded),
            "intraday_sector_evaluated_count": sector.evaluated_count,
            "intraday_dropped_by_cap": len(plan.dropped),
            "intraday_sector_error": sector_error,
        }
    )
    return out


__all__ = [
    "DEFAULT_MARKET_DB",
    "REASON_DAILY_CAP",
    "REASON_NO_SIGNAL",
    "IntradayAssembly",
    "active_policy",
    "assemble_intraday_alert",
    "build_sector_outcome",
]
