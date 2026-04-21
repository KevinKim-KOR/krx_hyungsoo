"""계정 설정 메타데이터 로더."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from utils.logger import get_app_logger
from utils.settings_loader import (
    AccountSettingsError,
    get_account_order,
    get_account_precision,
    get_account_settings,
    get_slack_channel,
    list_available_accounts,
    load_common_settings,
)

_ICON_FALLBACKS: dict[str, str] = {
    "kor": "🇰🇷",
}

logger = get_app_logger()


def _normalize_code(value: Any, fallback: str) -> str:
    text = str(value or "").strip().lower()
    return text or fallback


def _load_account_configs_impl() -> list[dict[str, Any]]:
    """`zsettings/account`에 정의된 계정 정보를 정렬된 리스트로 반환합니다."""

    configs: list[dict[str, Any]] = []

    for account_id in list_available_accounts():
        try:
            settings = get_account_settings(account_id)
        except AccountSettingsError as exc:
            logger.warning("계정 설정 로딩 실패(%s): %s", account_id, exc)
            continue

        country_code = _normalize_code(settings.get("country_code"), account_id)
        base_name = settings.get("name") or account_id.upper()

        icon = settings.get("icon") or _ICON_FALLBACKS.get(country_code, "")
        is_default = bool(settings.get("default", False))
        order = float(get_account_order(account_id))

        # [User Request] '순서. 이름' 형식으로 변경 (비율 제거)
        name = f"{int(order)}. {base_name}"

        configs.append(
            {
                "account_id": account_id,
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


load_account_configs = _load_account_configs_impl


def pick_default_account(accounts: list[dict[str, Any]]) -> dict[str, Any]:
    """기본으로 선택할 계정 설정을 결정합니다."""

    if not accounts:
        raise ValueError("선택 가능한 계정이 없습니다.")

    for account in accounts:
        if account.get("is_default"):
            return account

    for account in accounts:
        if account.get("country_code") == "kor":
            return account

    return accounts[0]


def get_icon_fallback(country_code: str) -> str:
    return _ICON_FALLBACKS.get((country_code or "").strip().lower(), "")


def get_benchmark_tickers(account_settings: Mapping[str, Any]) -> list[str]:
    """계정 설정에서 벤치마크 티커 목록을 추출합니다."""

    single_bench = account_settings.get("benchmark")
    if isinstance(single_bench, Mapping):
        ticker = str(single_bench.get("ticker") or "").strip().upper()
        if ticker:
            return [ticker]

    entries = account_settings.get("benchmarks")
    if not isinstance(entries, list):
        return []

    tickers: list[str] = []
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, Mapping):
            continue
        ticker = str(entry.get("ticker") or "").strip().upper()
        if ticker and ticker not in seen:
            tickers.append(ticker)
            seen.add(ticker)
    return tickers


def build_account_meta(accounts: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    meta: dict[str, dict[str, str]] = {}
    for account in accounts:
        account_id = account["account_id"]
        meta[account_id] = {
            "label": account["name"],
            "icon": account.get("icon", ""),
            "country_code": account.get("country_code", account_id),
        }
    return meta


def iter_accounts() -> Iterable[str]:
    """계정 ID 이터레이터."""

    yield from list_available_accounts()


def get_common_file_settings() -> dict[str, Any]:
    """config.py의 공통 설정을 딕셔너리로 반환합니다."""

    try:
        return load_common_settings()
    except Exception as exc:
        logger.warning("공통 설정 로드 실패: %s", exc)
        return {}


__all__ = [
    "AccountSettingsError",
    "list_available_accounts",
    "iter_accounts",
    "load_account_configs",
    "pick_default_account",
    "build_account_meta",
    "get_icon_fallback",
    "get_benchmark_tickers",
    "get_account_settings",
    "get_account_precision",
    "get_slack_channel",
    "get_common_file_settings",
]
