"""서비스 패키지의 공개 진입점을 지연 로딩한다."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORT_MAP = {
    "clear_price_service_cache": "services.price_service",
    "get_exchange_rate_series": "services.price_service",
    "get_exchange_rates": "services.price_service",
    "get_realtime_cache_meta": "services.price_service",
    "get_realtime_snapshot": "services.price_service",
    "get_kor_etf_master": "services.reference_data_service",
    "get_listing_date": "services.reference_data_service",
    "get_stock_reference_info": "services.reference_data_service",
    "get_stock_cache_meta": "services.stock_cache_service",
    "get_stock_cache_meta_map": "services.stock_cache_service",
    "refresh_stock_cache": "services.stock_cache_service",
    "refresh_stock_holdings_cache": "services.stock_cache_service",
    "refresh_stock_meta_cache": "services.stock_cache_service",
}

__all__ = list(_EXPORT_MAP.keys())


def __getattr__(name: str) -> Any:
    """필요한 서비스 함수만 지연 로딩한다."""
    module_name = _EXPORT_MAP.get(name)
    if module_name is None:
        raise AttributeError(f"module 'services' has no attribute '{name}'")
    module = import_module(module_name)
    return getattr(module, name)
