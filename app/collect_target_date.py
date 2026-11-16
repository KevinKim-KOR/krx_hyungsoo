"""구성종목 수집 목표일(POC6-31 PLAN 판정 §1 첫째 · Q2 (b)).

- 거래일이고 한국 시각 15:30 이후면 그날, 그 전이나 휴장일이면 직전 거래일.
- 거래일 계산은 운영 달력(`trading_day_lag` — 연도 캘린더 파일 · 없으면 평일 fallback)을 그대로 쓴다.
- 15:30 은 「섹터요약」 가격 시점 판정과 같은 정규장 마감 상수(`pc_etf_compare_periods.SESSION_CLOSE`)다.

목표일은 '이 날짜 이상 구성이면 다시 부르지 않는다'는 수집 기준일 뿐이다. 실제 구성일은 원천이 준 날짜다.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

from app.pc_etf_compare_periods import KST, SESSION_CLOSE
from app.trading_day_lag import expected_previous_trading_day, is_trading_day


def collect_target_date(
    now: datetime, *, calendar_dir: Optional[Path] = None
) -> Optional[str]:
    """`now`(시간대 있는 시각)의 수집 목표일 `YYYY-MM-DD`. 달력으로 거래일을 못 찾으면 `None`."""
    local = now.astimezone(KST)
    today = local.date().isoformat()
    if (
        is_trading_day(today, calendar_dir=calendar_dir)
        and (local.hour, local.minute) >= SESSION_CLOSE
    ):
        return today
    return expected_previous_trading_day(today, calendar_dir=calendar_dir)
