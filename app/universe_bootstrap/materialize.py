"""Manual seed materialization (지시문 §12).

사용자 승인 목록만 seed 로 저장. 승인되지 않은 종목 추가 · 승인된 종목 제거 ·
ticker 대체 · 종목명 임의 변경 · 승인 순서 변경 · 20개 초과 자동 보충 금지.

seed schema 변경 X. proposal_source · 순위 · 제안 사유를 seed 에 저장 X.

검증자 REJECTED r2 재정정 (B-1 fallback 위반 해소):
- 기존 정상 seed 를 먼저 덮어쓰지 않는다.
- **canonical validation 을 먼저 실행** 후, 통과할 때만 atomic replace.
- 실패 시 기존 seed 는 손대지 않는다 (fallback 삭제 금지).
- 기존 정상 seed 가 있으면 원본을 백업(사본) 없이도 무조건 보존.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Optional

from app.universe_bootstrap.proposal import TOTAL_MAX

DEFAULT_SEED_PATH = Path("state/universe/etf_universe_latest.json")


@dataclass
class ApprovedItem:
    ticker: str
    name: str
    universe_group: Optional[str] = None
    sector_or_theme: Optional[str] = None


class UniverseApprovalError(ValueError):
    """사용자 승인 목록이 계약을 위반한 경우."""


def _basic_shape_check(items: list[ApprovedItem]) -> None:
    if not items:
        raise UniverseApprovalError("승인 목록이 비어있습니다.")
    if len(items) > TOTAL_MAX:
        raise UniverseApprovalError(
            f"승인 목록이 {TOTAL_MAX}개를 초과했습니다 (received: {len(items)}). "
            "임의로 자르지 말고 재확인 필요."
        )
    seen: set[str] = set()
    for i, it in enumerate(items):
        if not isinstance(it.ticker, str) or not it.ticker.strip():
            raise UniverseApprovalError(
                f"승인 항목 [{i}] 의 ticker 가 비어있거나 문자열이 아닙니다."
            )
        if not isinstance(it.name, str) or not it.name.strip():
            raise UniverseApprovalError(
                f"승인 항목 [{i}] ({it.ticker}) 의 name 이 비어있거나 문자열이 아닙니다."
            )
        if it.ticker in seen:
            raise UniverseApprovalError(f"승인 항목 [{i}] ticker 중복: {it.ticker}")
        seen.add(it.ticker)


def _validate_seed_payload_via_parser(seed_payload: dict[str, Any]) -> None:
    """seed payload 를 canonical parse_universe_seed 로 검증 (파일 write 전).

    검증자 REJECTED r2 재정정: 기존 seed 를 건드리기 전에 in-memory 로 검증.
    실패 시 UniverseApprovalError 로 승격 · 기존 파일은 손대지 않는다.
    """
    from app.universe_seed import UniverseSeedError, parse_universe_seed

    try:
        parse_universe_seed(seed_payload)
    except (UniverseSeedError, ValueError) as e:
        raise UniverseApprovalError(
            f"승인 목록이 canonical seed validation 실패: {type(e).__name__}: {e}"
        ) from e


def materialize_seed(
    approved_items: list[ApprovedItem],
    *,
    asof: Optional[str] = None,
    seed_path: Optional[Path] = None,
) -> Path:
    """사용자 승인 목록 → manual seed JSON (source=manual) 원자적 저장.

    Args:
        approved_items: 사용자가 최종 승인한 후보 (승인 순서 유지).
        asof: seed 생성일 (기본 = 오늘 UTC 날짜, ISO YYYY-MM-DD).
              반드시 canonical parser (`parse_universe_seed`) 를 통과하는 형식이어야 함.
        seed_path: 저장 경로 (기본 = DEFAULT_SEED_PATH). 테스트는 tmp path.

    Returns:
        저장된 seed 파일 경로.

    Raises:
        UniverseApprovalError: 승인 목록 계약 위반 또는 canonical validation 실패.
                              이 경우 기존 seed 파일은 변경되지 않는다 (B-1 대응).
    """
    _basic_shape_check(approved_items)

    target = Path(seed_path) if seed_path is not None else DEFAULT_SEED_PATH
    asof_value = asof or date.today().isoformat()

    items_payload: list[dict[str, Any]] = []
    for it in approved_items:
        entry: dict[str, Any] = {
            "ticker": it.ticker,
            "name": it.name,
        }
        if it.universe_group is not None:
            entry["universe_group"] = it.universe_group
        if it.sector_or_theme is not None:
            entry["sector_or_theme"] = it.sector_or_theme
        items_payload.append(entry)

    seed_payload = {
        "asof": asof_value,
        "source": "manual",
        "items": items_payload,
    }

    # 검증자 REJECTED r2 재정정 (B-1): 기존 seed 를 덮어쓰기 전에 in-memory validation.
    # 실패 시 target 파일은 손대지 않는다.
    _validate_seed_payload_via_parser(seed_payload)

    # canonical validation 통과 시에만 atomic replace.
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(
        json.dumps(seed_payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    os.replace(tmp, target)
    return target
