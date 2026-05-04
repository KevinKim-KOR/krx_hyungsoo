"""POC2 Step 3 — factor signal 모듈 패키지.

설계자 판단:
- 첫 factor 는 portfolio_concentration_v1 (사용자 표시명: "보유 비중 영향").
- 외부 API / 신규 의존성 없이 기존 holdings + market_cache 로 계산한다.
- BUY/SELL/리밸런싱/위험 등급 판단이 아니다.

draft_payload.factor_signals 5번째 키 추가는 Step3 목적상 예외 허용이며, 다른
draft_payload 메타 flag 추가나 top-level Run 필드 확장의 일반 허용은 아니다
(설계자 명시). 향후 factor 추가 시 이 모듈에 helper 1개를 추가하는 방식으로
재사용 가능하도록 한다.
"""

from app.factors.portfolio_concentration import (
    FACTOR_DISPLAY_NAME,
    FACTOR_ID,
    build_factor_signals,
)

__all__ = [
    "FACTOR_ID",
    "FACTOR_DISPLAY_NAME",
    "build_factor_signals",
]
