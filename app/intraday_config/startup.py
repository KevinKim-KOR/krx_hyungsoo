"""POC3-02C-OPS-01 — 장중 설정 기동 catch-up (설계자 §10-3(2)).

**별도 PC cron 을 만들지 않는다.** PC 백엔드가 뜰 때 미수행 산출을 1회 따라잡고,
시장 데이터 갱신 성공 후에는 `market_refresh_service` 가 직접 재산출한다.

`api.py` 에 인라인하지 않은 이유는 KS-10 이다 — 그 파일은 근접(≥600줄)이라
새 책임을 더 받으면 임계를 넘는다.

여기서 만드는 것은 **미승인 후보뿐**이다. 승인과 OCI 전달은 사용자 동작이며
이 경로에서 절대 일어나지 않는다.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def catch_up() -> dict[str, Any]:
    """기동 시 1회. **예외를 절대 올리지 않는다** — 백엔드 기동을 막으면 안 된다.

    최초 1회는 즉시 산출되고, 이후에는 `should_regenerate()` 가 20거래일 주기와
    대표 적격성을 보고 판단하므로 기동할 때마다 새 버전이 쌓이지 않는다.
    """
    try:
        from app.intraday_config import generator

        out = generator.generate()
        logger.info(
            "장중 설정 기동 catch-up: status=%s version=%s",
            out.get("status"),
            out.get("config_version_id"),
        )
        return out
    except Exception as e:  # noqa: BLE001 - 기동을 절대 막지 않는다
        logger.warning("장중 설정 catch-up 중 예외(무시): %s", e)
        return {"status": "failed", "reason": f"{type(e).__name__}: {e}"[:300]}


__all__ = ["catch_up"]
