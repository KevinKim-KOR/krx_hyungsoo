"""종목풀(ticker_type) 설정 메타데이터 로더."""

from __future__ import annotations

from typing import Any

from utils.logger import get_app_logger
from utils.settings_loader import (
    AccountSettingsError,
    get_ticker_type_settings,
    list_available_ticker_types,
)

logger = get_app_logger()


def _normalize_code(value: Any, fallback: str) -> str:
    text = str(value or "").strip().lower()
    return text or fallback


def load_ticker_type_configs() -> list[dict[str, Any]]:
    """`ztickers`에 정의된 종목풀 정보를 정렬된 리스트로 반환합니다."""

    from utils.settings_loader import parse_ticker_dir_name, get_ticker_dir

    configs: list[dict[str, Any]] = []

    for t_id in list_available_ticker_types():
        try:
            settings = get_ticker_type_settings(t_id)
        except AccountSettingsError as exc:
            logger.warning("종목풀 설정 로딩 실패(%s): %s", t_id, exc)
            continue

        country_code = _normalize_code(settings.get("country_code"), "")
        base_name = settings.get("name") or t_id.upper()

        icon = str(settings.get("icon") or "").strip()
        if not icon:
            raise AccountSettingsError(f"종목풀 '{t_id}' 설정에 icon이 필요합니다.")
        is_default = bool(settings.get("default", False))
        
        path = get_ticker_dir(t_id)
        order, _ = parse_ticker_dir_name(path.name)
        
        name = f"{int(order)}. {base_name}"

        configs.append(
            {
                "ticker_type": t_id,
                "country_code": country_code,
                "name": name,
                "icon": icon,
                "is_default": is_default,
                "order": order,
                "settings": settings,
            }
        )

    configs.sort(key=lambda acc: (acc["order"], acc["name"]))
    return configs


def pick_default_ticker_type(types: list[dict[str, Any]]) -> dict[str, Any]:
    """기본으로 선택할 종목풀을 결정합니다."""

    if not types:
        raise ValueError("선택 가능한 종목풀이 없습니다.")

    for t in types:
        if t.get("is_default"):
            return t

    for t in types:
        if t.get("country_code") == "kor":
            return t

    return types[0]
