"""POC5-23 검증자 r1 · r2 · r3 정정 — 판단 근거 미리보기 숫자를 화면(브라우저 JS)과 같은 글로 만든다.

미리보기 글은 서버(파이썬)가 만들고 화면 칸은 브라우저가 만든다. 파이썬 `format`(round-half-even ·
고정 소수 여섯째)은 JS 와 경계값에서 다르다 — 검증자 r1: 저장 거래량 0.0000001 이 '0주' · r2: 1e22 에서
기본 Decimal 정밀도(28) 초과로 미리보기 전체 실패 · 음수 0 이 '-0.0'.
화면 helper 가 쓰는 네 가지 JS 규칙을 그대로 옮긴다(2026-10-18 node 실측 · 시험에 고정).

- `to_fixed` = `toFixed(n)`(%, %p · 흔들림 · 하락 구간 · 비중 · 중복률): 실제 이진값 · 같으면 0 에서
  먼 쪽 · 부호는 x < 0 일 때만(음수 0 → '0.0') · |x| ≥ 1e21 은 지수 표기.
- `intl_fixed` = `toLocaleString("ko-KR", 소수 n 고정)`(거래량 평균 · 배수): 가장 짧은 십진 표현 ·
  0 에서 먼 쪽 · 쉼표 · 음수 0 → '-0.00'.
- `fmt_exact` = `chartScale.fmtExact`(저장 거래량 · 줄이지 않음): 0 아닌 1 미만 = 유효숫자 6 ·
  그 밖 = 소수 6 이하 · 쉼표.
- `math_round_grouped` = `Math.round(v).toLocaleString("ko-KR")`(NAV · 시장가): floor(v + 0.5) ·
  (-0.5, 0] 은 '-0' · 결과 double 은 Intl 처럼 가장 짧은 십진 표현(1e23 → '100,000,…')(검증자 r3).

숫자 아님 · 무한대도 JS 글 그대로('NaN' · 'Infinity' / '∞'). 크기와 무관하게 정밀도가 모자라지 않도록
모든 계산은 넉넉한 정밀도의 전용 문맥으로 한다(double 최대 약 1.8e308 · 최소 5e-324).
"""

from __future__ import annotations

import math
from decimal import ROUND_FLOOR, ROUND_HALF_UP, Context, Decimal
from typing import Optional, Union

Number = Union[int, float]

# 정수부 309자리 + 소수부(최소 5e-324 → 1074자리 이진 정확값)까지 담는 정밀도.
_CTX = Context(prec=1500, rounding=ROUND_HALF_UP)
# JS toFixed 는 |x| ≥ 1e21 이면 지수 표기(Number::toString)로 돌려준다.
_TO_FIXED_LIMIT = 1e21


def _strip_frac(s: str, min_frac: int) -> str:
    if "." not in s:
        return s
    head, frac = s.split(".", 1)
    frac = frac.rstrip("0")
    if len(frac) < min_frac:
        frac = frac + "0" * (min_frac - len(frac))
    return f"{head}.{frac}" if frac else head


def _intl_special(v: float) -> Optional[str]:
    """Intl(toLocaleString) 의 숫자 아님 · 무한대 글."""
    if math.isnan(v):
        return "NaN"
    if math.isinf(v):
        return "∞" if v > 0 else "-∞"
    return None


def _quantize(d: Decimal, digits: int) -> Decimal:
    return d.quantize(Decimal(1).scaleb(-digits), rounding=ROUND_HALF_UP, context=_CTX)


def to_fixed(value: Number, digits: int) -> str:
    """JS `Number.prototype.toFixed(digits)` — 실제 이진값을 반올림(같으면 큰 쪽 · 부호는 x < 0 만)."""
    v = float(value)
    if math.isnan(v):
        return "NaN"
    if math.isinf(v):
        return "Infinity" if v > 0 else "-Infinity"
    if abs(v) >= _TO_FIXED_LIMIT:
        return repr(
            v
        )  # JS Number::toString 과 같은 가장 짧은 표현(예 '1e+21' · '1.5e+21')
    sign = "-" if v < 0 else ""  # 음수 0 은 x < 0 이 아니므로 부호 없음
    return sign + format(_quantize(Decimal(abs(v)), digits), "f")


def intl_fixed(value: Number, digits: int) -> str:
    """`toLocaleString("ko-KR", {minimumFractionDigits: digits, maximumFractionDigits: digits})`."""
    v = float(value)
    special = _intl_special(v)
    if special is not None:
        return special
    return format(_quantize(Decimal(repr(v)), digits), ",f")


def fmt_exact(value: Number) -> str:
    """`chartScale.fmtExact(v)` — 저장 거래량을 줄이지 않는다(0.0000001 은 0 이 아니다)."""
    v = float(value)
    special = _intl_special(v)
    if special is not None:
        return special
    d = Decimal(repr(v))
    if v != 0 and abs(v) < 1:
        exp = d.adjusted() - 5  # 유효숫자 6
        q = d.quantize(Decimal(1).scaleb(exp), rounding=ROUND_HALF_UP, context=_CTX)
        return format(q.normalize(context=_CTX), "f")
    return _strip_frac(format(_quantize(d, 6), ",f"), 0)


def js_math_round(value: Number) -> float:
    """JS `Math.round(v)` 의 결과 double — floor(v + 0.5)(정확한 이진값) · (-0.5, 0] 은 -0."""
    v = float(value)
    if math.isnan(v) or math.isinf(v):
        return v
    n = _CTX.add(Decimal(v), Decimal("0.5")).to_integral_value(
        rounding=ROUND_FLOOR, context=_CTX
    )
    if n == 0 and (v < 0 or math.copysign(1.0, v) < 0):
        return -0.0
    return float(n)  # |v| < 2^52 은 정확 · 그 이상은 v 가 이미 정수라 n == v


def math_round_grouped(value: Number) -> str:
    """`Math.round(v).toLocaleString("ko-KR")` — 반올림한 double 을 Intl 처럼(가장 짧은 십진 표현) 쓴다.

    검증자 r3 — 정확한 정수(파이썬 int)를 그대로 쓰면 1e23 이 '99,999,999,999,999,991,611,392' 가 된다
    (화면 '100,000,000,000,000,000,000,000').
    """
    return intl_fixed(js_math_round(value), 0)
