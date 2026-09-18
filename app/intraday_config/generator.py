"""POC3-02C-OPS-01 — PC 자동 산출 트리거 (설계자 §10-3(2)).

**별도 PC cron 을 만들지 않는다.**

| 시점 | 동작 |
|---|---|
| PC 백엔드 시작 | 미수행 작업 catch-up |
| 시장 데이터 갱신 성공 후 | 재계산 |
| 최초 1회 | 즉시 산출 |
| 이후 정기 | 최대 **20거래일에 한 번** |
| 현재 대표가 적격성을 잃음 | 주기와 무관하게 **즉시** 재평가 |
| PC 가 꺼져 있음 | OCI 는 기존 승인 버전 유지 (아무 일도 안 일어남) |

**자동 재평가는 하되 교체를 위한 강제 순환은 하지 않는다.** 결과가 같으면
`effective_config_hash` 가 같아 새 버전이 생기지 않는다(§10-3(1)).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from app.intraday_config import schema, selector, store

REEVAL_INTERVAL_TRADING_DAYS = 20

DEFAULT_CSV = Path("state/market_meta/krx_etf_basic_20260909.csv")
DEFAULT_DB = Path("state/market/market_data.sqlite")


def _stored_trading_days(db_path: Path) -> list[str]:
    from app.market_briefing import krx_store

    try:
        return krx_store.stored_trading_days(db_path=db_path)
    except Exception:  # noqa: BLE001
        return []


def _active_payload(db_path: Optional[Path]) -> tuple[Optional[dict], Optional[str]]:
    active = store.get_active(db_path=db_path)
    if not active:
        return None, None
    try:
        return json.loads(active["payload_json"]), active["config_version_id"]
    except (KeyError, TypeError, ValueError):
        return None, active.get("config_version_id")


def _representatives_still_eligible(
    payload: dict[str, Any], csv_path: Path
) -> tuple[bool, list[str]]:
    """현재 대표가 여전히 적격한가. 아니면 주기와 무관하게 재평가한다."""
    rows = {
        (r.get("단축코드") or "").strip(): r
        for r in selector.load_official_rows(csv_path)
    }
    bad: list[str] = []
    uni = payload.get("sector_representative_universe") or {}
    for s in uni.get("sectors") or []:
        t = str((s.get("representative") or {}).get("ticker") or "")
        row = rows.get(t)
        if row is None:
            bad.append(t)  # 상장폐지·코드변경
            continue
        ok, _ = selector.is_eligible(row)
        if not ok:
            bad.append(t)
    return (not bad), bad


def _trading_days_since(days: list[str], asof: Optional[str]) -> Optional[int]:
    if not days or not asof or asof not in days:
        return None
    return len(days) - 1 - days.index(asof)


def should_regenerate(
    *,
    csv_path: Path = DEFAULT_CSV,
    db_path: Path = DEFAULT_DB,
    state_db_path: Optional[Path] = None,
) -> tuple[bool, str]:
    """재계산이 필요한가. 반환 `(필요, 사유)`."""
    payload, _ = _active_payload(state_db_path)
    if payload is None:
        return True, "no_active_version"  # 최초 1회 즉시

    ok, bad = _representatives_still_eligible(payload, csv_path)
    if not ok:
        return True, f"representative_ineligible:{','.join(bad[:5])}"

    uni = payload.get("sector_representative_universe") or {}
    elapsed = _trading_days_since(_stored_trading_days(db_path), uni.get("data_asof"))
    if elapsed is None:
        return True, "asof_not_on_axis"
    if elapsed >= REEVAL_INTERVAL_TRADING_DAYS:
        return True, f"interval_elapsed:{elapsed}"
    return False, f"within_interval:{elapsed}"


def generate(
    *,
    csv_path: Path = DEFAULT_CSV,
    db_path: Path = DEFAULT_DB,
    state_db_path: Optional[Path] = None,
    force: bool = False,
) -> dict[str, Any]:
    """산출 → 후보 생성. **예외를 올리지 않는다** (백엔드 기동을 막으면 안 된다).

    같은 `effective_config_hash` 면 새 버전을 만들지 않는다(§10-3(1)).
    """
    try:
        if not force:
            need, why = should_regenerate(
                csv_path=csv_path, db_path=db_path, state_db_path=state_db_path
            )
            if not need:
                return {"status": "skipped", "reason": why}

        dictionary = selector.default_token_dictionary()
        sectors, excluded, asof = selector.build_sectors(
            csv_path=csv_path, db_path=db_path, dictionary=dictionary
        )
        if not sectors:
            return {"status": "failed", "reason": "no_sectors"}

        payload = schema.build_payload(
            rule_version=selector.RULE_VERSION,
            sectors=sectors,
            token_dictionary=dictionary,
            data_asof=asof,
            excluded=excluded,
        )
        eval_hash = selector.evaluation_input_hash(
            csv_path=csv_path,
            data_asof=asof,
            rule_version=selector.RULE_VERSION,
            dictionary_keys=list(dictionary),
        )
        vid, created = store.create_candidate(
            payload, evaluation_input_hash=eval_hash, db_path=state_db_path
        )
        return {
            "status": "created" if created else "unchanged",
            "config_version_id": vid,
            "sector_count": len(sectors),
            "excluded_count": len(excluded),
            "data_asof": asof,
        }
    except Exception as e:  # noqa: BLE001
        return {"status": "failed", "reason": f"{type(e).__name__}: {e}"[:300]}


__all__ = [
    "DEFAULT_CSV",
    "DEFAULT_DB",
    "REEVAL_INTERVAL_TRADING_DAYS",
    "generate",
    "should_regenerate",
]
