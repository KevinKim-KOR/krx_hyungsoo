# -*- coding: utf-8 -*-
from typing import Optional

def corrected_valuation(recorded_value: float, holdings_value: float) -> float:
    """
    개발룰:
      - recorded_value <= 0 이거나 holdings_value > recorded_value 이면 holdings_value로 보정
      - 그 외에는 recorded_value 유지(0이 아닌 값을 낮추지 않음)
    """
    if recorded_value <= 0:
        return float(holdings_value)
    if holdings_value > recorded_value:
        return float(holdings_value)
    return float(recorded_value)
