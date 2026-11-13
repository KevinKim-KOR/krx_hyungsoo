"""POC6-29 보완 2차 — 투자자 수급 5거래일 합(「시장 근거와 다른 변화 보기」 근거 표의 단기 흐름 · S 판정 §1).

- `GET /market/short-flows` = 저장된 일별 원자료(`market_investor_flow_daily` · KOSPI)만 읽는다(외부 조회 0 · 쓰기 0).
- 끝일 = 수급 표의 마지막 거래일. 5거래일 = 거래일 달력에서 끝일을 포함한 5일(`trading_days_ending` · 달력 없는 해는
  평일 기본) · 직전 5거래일 = 그 앞 5일. 합 = 기존 `supply_fx_oil_calc.window`(하루라도 빠지면 계산하지 않음 →
  '5거래일 자료 부족') · 비교 문장 = 기존 외국인 20거래일 규칙(`supply_fx_oil_context._trend`)을 기간 수만 5로.
- 주체 = 외국인 · 기관계 · 개인(화면 근거 표의 세 줄). 마지막 값 = 끝일의 그 주체 순매수(원 · 없으면 None).
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter

from app.market_data_store import DEFAULT_DB_PATH
from app.supply_fx_oil_calc import window
from app.supply_fx_oil_context import _trend
from app.supply_fx_oil_store import read_investor_flows
from app.trading_day_lag import trading_days_ending

logger = logging.getLogger(__name__)
router = APIRouter(tags=["market"])

SHORT_N = 5
SHOWN = (("foreign", "외국인"), ("institution", "기관계"), ("individual", "개인"))
SHORT_MISSING_TEXT = "5거래일 자료 부족"


def _sum(w: Optional[dict]) -> Optional[dict[str, Any]]:
    if not w:
        return None
    return {"sum": int(w["sum"]), "from": w["from"], "to": w["to"]}


def build_short_flows(
    *, db_path: Path = DEFAULT_DB_PATH, calendar_dir: Optional[Path] = None
) -> dict[str, Any]:
    """주체별 끝일 값 · 최근 5거래일 합 · 직전 5거래일 합 · 비교 문장."""
    try:
        raw, _at = read_investor_flows(db_path=db_path)
    except sqlite3.Error:
        logger.exception("short flows: read failed")
        return {
            "status": "invalid",
            "message": "PC 수급 자료를 읽지 못했습니다",
            "end_date": None,
            "investors": [],
        }
    dates = [d for k, _ in SHOWN for d, _ in raw.get(k, [])]
    if not dates:
        return {
            "status": "empty",
            "message": "PC 수급 자료 없음",
            "end_date": None,
            "investors": [],
        }
    end = max(dates)
    cal = trading_days_ending(end, SHORT_N * 2, calendar_dir=calendar_dir)
    cal_ok = len(cal) == SHORT_N * 2 and cal[-1] == end
    investors = []
    for key, label in SHOWN:
        points = raw.get(key, [])
        rows = dict(points)
        recent = window(points, cal, end, 0, SHORT_N) if cal_ok else None
        previous = window(points, cal, end, SHORT_N, SHORT_N) if cal_ok else None
        trend = _trend(recent, previous, SHORT_N)[0] if recent and previous else None
        investors.append(
            {
                "key": key,
                "label": label,
                "last": (
                    {"date": end, "value": int(rows[end])} if end in rows else None
                ),
                "recent5": _sum(recent),
                "previous5": _sum(previous),
                "trend": trend,
                "note": None if recent else SHORT_MISSING_TEXT,
            }
        )
    return {
        "status": "ok",
        "message": None,
        "end_date": end,
        "investors": investors,
    }


@router.get("/market/short-flows")
def get_short_flows() -> dict[str, Any]:
    return build_short_flows(db_path=DEFAULT_DB_PATH)  # 모듈 속성(시험이 바꿔 끼움)
