"""Momentum 전략에서 공통으로 사용하는 규칙/검증 헬퍼."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Mapping


@dataclass(frozen=True)
class StrategyRules:
    """Momentum 전략에서 공통으로 사용하는 핵심 파라미터."""

    # 기본 MA 기간 (이동평균 기간)
    DEFAULT_MA_PERIOD = 20
    # 기본 MA 타입 (이동평균 종류)
    DEFAULT_MA_TYPE = "SMA"

    ma_period: int
    portfolio_topn: int
    replace_threshold: float
    ma_type: str = "SMA"
    core_holdings: List[str] = field(default_factory=list)

    @classmethod
    def from_values(
        cls,
        *,
        ma_period: Any,
        portfolio_topn: Any,
        replace_threshold: Any,
        ma_type: Any = None,
        core_holdings: Any = None,
    ) -> "StrategyRules":
        try:
            ma_period_int = int(ma_period)
        except (TypeError, ValueError):
            raise ValueError("MA_PERIOD는 0보다 큰 정수여야 합니다.") from None
        if ma_period_int <= 0:
            raise ValueError("MA_PERIOD는 0보다 큰 정수여야 합니다.")

        try:
            portfolio_topn_int = int(portfolio_topn)
        except (TypeError, ValueError):
            raise ValueError("PORTFOLIO_TOPN은 0보다 큰 정수여야 합니다.") from None
        if portfolio_topn_int <= 0:
            raise ValueError("PORTFOLIO_TOPN은 0보다 큰 정수여야 합니다.")

        try:
            replace_threshold_float = float(replace_threshold)
        except (TypeError, ValueError):
            raise ValueError("REPLACE_SCORE_THRESHOLD는 숫자여야 합니다.") from None

        # MA 타입 검증
        ma_type_str = str(ma_type or cls.DEFAULT_MA_TYPE).upper()
        valid_ma_types = {"SMA", "EMA", "WMA", "DEMA", "TEMA", "HMA"}
        if ma_type_str not in valid_ma_types:
            raise ValueError(f"MA_TYPE은 {valid_ma_types} 중 하나여야 합니다. (입력값: {ma_type_str})")

        # 핵심 보유 종목 검증
        core_holdings_list: List[str] = []
        if core_holdings is not None:
            if isinstance(core_holdings, (list, tuple)):
                core_holdings_list = [str(ticker).strip().upper() for ticker in core_holdings if ticker]
            elif isinstance(core_holdings, str):
                # 쉼표로 구분된 문자열 지원
                core_holdings_list = [ticker.strip().upper() for ticker in core_holdings.split(",") if ticker.strip()]

        return cls(
            ma_period=ma_period_int,
            portfolio_topn=portfolio_topn_int,
            replace_threshold=replace_threshold_float,
            ma_type=ma_type_str,
            core_holdings=core_holdings_list,
        )

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> "StrategyRules":
        def _resolve(*keys: str) -> Any:
            sentinel = object()
            for key in keys:
                value = mapping.get(key, sentinel)
                if value is not sentinel:
                    return value
            return None

        return cls.from_values(
            ma_period=_resolve("MA_PERIOD", "ma_period"),
            portfolio_topn=_resolve("PORTFOLIO_TOPN", "portfolio_topn"),
            replace_threshold=_resolve("REPLACE_SCORE_THRESHOLD", "replace_threshold"),
            ma_type=_resolve("MA_TYPE", "ma_type"),
            core_holdings=_resolve("CORE_HOLDINGS", "core_holdings"),
        )

    def to_dict(self) -> dict[str, Any]:
        d = {
            "ma_period": self.ma_period,
            "portfolio_topn": self.portfolio_topn,
            "replace_threshold": self.replace_threshold,
            "ma_type": self.ma_type,
            "core_holdings": list(self.core_holdings),
        }
        return d


__all__ = [
    "StrategyRules",
]
