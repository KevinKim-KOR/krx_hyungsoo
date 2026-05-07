"""POC2 Step 5B — Momentum Engine 패키지 (holdings mode 만 구현).

설계자 결정 (Step5A 계약 + Step5B 진입 가드):
- Momentum Engine 은 holdings mode 와 universe mode 가 공유하는 공통 엔진 자리.
- 본 Step5B 는 holdings mode 만 placeholder 산식으로 1회 실행.
- universe mode 빈 stub / 공통 추상 클래스 / registry / plugin 구조는 모두 도입 금지
  (설계자 명시 가드).
- app/factors 의 책임(factor signal) 과 본 패키지의 책임(momentum 점검 결과 = momentum_result)
  은 의미가 다르므로 섞지 않는다.

draft_payload.momentum_result 6번째 키 추가는 Step5B 한정 명시 승인이며, 다른 키 확장의
일반 허용으로 해석하지 말 것 (Step3 의 factor_signals 5번째 키 명시 승인 정신과 동일).

draft_payload 키 순번 (참고):
1) title
2) asof
3) note
4) recommendations
5) factor_signals (Step3)
6) momentum_result (Step5B)
"""

from app.momentum.holdings_mode import (
    ENGINE_ID,
    ENGINE_VERSION,
    build_holdings_momentum_result,
)

__all__ = [
    "ENGINE_ID",
    "ENGINE_VERSION",
    "build_holdings_momentum_result",
]
