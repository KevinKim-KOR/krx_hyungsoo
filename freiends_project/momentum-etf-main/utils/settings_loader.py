"""계정별 설정을 파일에서 로드하기 위한 헬퍼 모듈."""

from __future__ import annotations

import json
import re
from functools import cache, lru_cache
from pathlib import Path
from typing import Any

from utils.logger import get_app_logger


class AccountSettingsError(RuntimeError):
    """계정 설정 로딩 중 발생하는 예외."""


SETTINGS_ROOT = Path(__file__).resolve().parents[1] / "zaccounts"
TICKERS_ROOT = Path(__file__).resolve().parents[1] / "ztickers"
ACCOUNT_SETTINGS_DIR = SETTINGS_ROOT  # Backward compatibility alias
COMMON_SETTINGS_PATH = SETTINGS_ROOT / "common.py"
SCHEDULE_CONFIG_PATH = SETTINGS_ROOT / "schedule_config.json"
logger = get_app_logger()
ACCOUNT_DIR_PATTERN = re.compile(r"^(?P<order>\d+)_(?P<account>[a-z0-9_]+)$")
TICKER_DIR_PATTERN = re.compile(r"^(?P<order>\d+)_(?P<ticker_type>[a-z0-9_]+)$")


def parse_account_dir_name(dir_name: str) -> tuple[int, str]:
    """`<order>_<account>` 형식의 디렉토리명에서 순번과 계정 코드를 추출합니다."""

    normalized = (dir_name or "").strip().lower()
    match = ACCOUNT_DIR_PATTERN.fullmatch(normalized)
    if not match:
        raise AccountSettingsError(f"계정 디렉토리명은 '<order>_<account>' 형식이어야 합니다: {dir_name}")
    return int(match.group("order")), match.group("account")


def _iter_account_dirs() -> list[tuple[str, Path]]:
    account_dirs: dict[str, Path] = {}
    if not SETTINGS_ROOT.exists():
        return []

    for item in SETTINGS_ROOT.iterdir():
        if not item.is_dir() or item.name.startswith(".") or item.name.startswith("_"):
            continue

        config_path = item / "config.json"
        if not config_path.exists():
            continue

        config_data = _load_json(config_path)
        _, account_id = parse_account_dir_name(item.name)
        configured = str(config_data.get("account") or "").strip().lower()
        if configured and configured != account_id:
            pass  # 기존 검사 완화 (이름 불일치 허용)
        account_dirs[account_id] = item

    return sorted(account_dirs.items(), key=lambda pair: parse_account_dir_name(pair[1].name))


def parse_ticker_dir_name(dir_name: str) -> tuple[int, str]:
    """`<order>_<ticker_type>` 형식의 디렉토리명에서 순번과 타입 코드를 추출합니다."""
    normalized = (dir_name or "").strip().lower()
    match = TICKER_DIR_PATTERN.fullmatch(normalized)
    if not match:
        raise AccountSettingsError(f"종목타입 디렉토리명은 '<order>_<type>' 형식이어야 합니다: {dir_name}")
    return int(match.group("order")), match.group("ticker_type")


def _iter_ticker_dirs() -> list[tuple[str, Path]]:
    ticker_dirs: dict[str, Path] = {}
    if not TICKERS_ROOT.exists():
        return []

    for item in TICKERS_ROOT.iterdir():
        if not item.is_dir() or item.name.startswith(".") or item.name.startswith("_"):
            continue

        config_path = item / "config.json"
        if not config_path.exists():
            continue

        _, type_id = parse_ticker_dir_name(item.name)
        ticker_dirs[type_id] = item

    return sorted(ticker_dirs.items(), key=lambda pair: parse_ticker_dir_name(pair[1].name))

def list_available_ticker_types() -> list[str]:
    """ztickers 하위의 유효한 종목타입 목록을 반환합니다."""
    return [t_id for t_id, _ in _iter_ticker_dirs()]


def list_available_accounts() -> list[str]:
    """
    zaccounts 디렉토리 하위의 유효한 계정(디렉토리 내 config.json 존재) 목록을 반환합니다.
    """
    return [account_id for account_id, _ in _iter_account_dirs()]


def _load_json(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:  # noqa: PERF203
        raise AccountSettingsError(f"설정 파일을 찾을 수 없습니다: {path}") from exc
    except OSError as exc:  # noqa: PERF203
        raise AccountSettingsError(f"설정 파일을 읽을 수 없습니다: {path}") from exc

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:  # noqa: PERF203
        raise AccountSettingsError(f"설정 파일이 올바른 JSON 형식이 아닙니다: {path}") from exc

    if not isinstance(data, dict):
        raise AccountSettingsError(f"설정 파일의 루트는 객체(JSON object)여야 합니다: {path}")
    return data


@cache
def get_account_dir(account_id: str) -> Path:
    """논리 계정 ID에 대응하는 실제 zaccounts 디렉토리를 반환합니다."""

    account = (account_id or "").strip().lower()
    if not account:
        raise AccountSettingsError("계정 식별자를 지정해야 합니다.")

    account_dirs = dict(_iter_account_dirs())
    path = account_dirs.get(account)
    if path is None:
        raise AccountSettingsError(f"계정 '{account}'에 해당하는 설정 디렉토리를 찾을 수 없습니다.")
    return path


def get_account_order(account_id: str) -> int:
    """논리 계정 ID에 대응하는 디렉토리명의 순번을 반환합니다."""

    return parse_account_dir_name(get_account_dir(account_id).name)[0]


@cache
def get_account_settings(account_id: str) -> dict[str, Any]:
    """`zaccounts/{account}/config.json` 파일을 로드합니다."""

    account = (account_id or "").strip().lower()
    if not account:
        raise AccountSettingsError("계정 식별자를 지정해야 합니다.")

    path = get_account_dir(account) / "config.json"
    logger.debug("계정 설정 로드: %s", path)

    settings = _load_json(path)
    settings["account"] = account

    if not settings.get("country_code"):
        settings["country_code"] = "kor"

    return settings

@cache
def get_ticker_dir(ticker_type: str) -> Path:
    t_id = (ticker_type or "").strip().lower()
    dirs = dict(_iter_ticker_dirs())
    path = dirs.get(t_id)
    if path is None:
        raise AccountSettingsError(f"종목타입 '{t_id}'에 해당하는 설정 디렉토리를 찾을 수 없습니다.")
    return path

@cache
def get_ticker_type_settings(ticker_type: str) -> dict[str, Any]:
    """`ztickers/{order}_{type}/config.json` 파일을 로드합니다."""
    t_id = (ticker_type or "").strip().lower()
    if not t_id:
        raise AccountSettingsError("종목타입을 지정해야 합니다.")

    path = get_ticker_dir(t_id) / "config.json"
    settings = _load_json(path)
    settings["ticker_type"] = t_id

    country_code = str(settings.get("country_code") or "").strip().lower()
    if country_code not in {"kor", "au", "us"}:
        raise AccountSettingsError(f"'{path}' 설정 파일의 country_code는 kor, au 또는 us만 허용합니다: {country_code}")
    settings["country_code"] = country_code

    return settings


def get_account_precision(account_id: str) -> dict[str, Any]:
    """표시/계산 정밀도 설정을 반환합니다."""

    settings = get_account_settings(account_id)
    country_code = (settings.get("country_code") or account_id).strip().lower()
    if country_code == "au":
        return {
            "currency": "AUD",
            "qty_precision": 0,
            "price_precision": 2,
        }

    if country_code == "us":
        return {
            "currency": "USD",
            "qty_precision": 0,
            "price_precision": 2,
        }

    if country_code != "kor":
        raise AccountSettingsError(f"지원하지 않는 국가 코드입니다: {country_code}")

    return {
        "currency": "KRW",
        "qty_precision": 0,
        "price_precision": 0,
    }


def get_slack_channel() -> str | None:
    """공통 슬랙 채널 ID를 반환합니다. config.SLACK_CHANNEL을 사용합니다."""

    try:
        import config

        channel = getattr(config, "SLACK_CHANNEL", None)
        if isinstance(channel, str) and channel.strip():
            return channel.strip()
    except Exception:
        pass

    return None


@lru_cache(maxsize=1)
def load_common_settings() -> dict[str, Any]:
    """config.py 모듈에서 공통 설정을 추출해 딕셔너리로 반환합니다."""

    try:
        import importlib

        config_module = importlib.import_module("config")
    except ModuleNotFoundError as exc:
        raise AccountSettingsError("공통 설정 모듈(config.py)을 찾을 수 없습니다.") from exc
    except Exception as exc:
        raise AccountSettingsError(f"공통 설정을 로드하지 못했습니다: {exc}") from exc

    data = {key: getattr(config_module, key) for key in dir(config_module) if key.isupper() and not key.startswith("_")}
    return data


def get_country_precision(country: str) -> dict[str, Any]:  # pragma: no cover
    country_code = (country or "").strip().lower()
    if country_code == "au":
        return {
            "currency": "AUD",
            "qty_precision": 0,
            "price_precision": 2,
        }
    if country_code == "us":
        return {
            "currency": "USD",
            "qty_precision": 0,
            "price_precision": 2,
        }
    if country_code == "kor":
        return {
            "currency": "KRW",
            "qty_precision": 0,
            "price_precision": 0,
        }
    raise AccountSettingsError(f"지원하지 않는 국가 코드입니다: {country}")


def get_country_slack_channel(country: str) -> str | None:  # pragma: no cover
    return get_slack_channel()
