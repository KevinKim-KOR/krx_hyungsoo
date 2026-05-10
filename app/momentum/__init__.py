"""POC2 Step 5B + 5C — Momentum Engine 패키지.

설계자 결정 (Step5A 계약 + Step5B/5C 가드):
- Momentum Engine 은 holdings mode 와 universe mode 가 공유하는 공통 엔진 자리.
- Step5B: holdings mode placeholder 산식 (pnl_rate) 1회 실행.
- Step5C: universe mode (manual seed → score 없는 momentum_result + latest artifact 저장).
- 추상 클래스 / registry / plugin 구조는 도입 금지 (premature abstraction 회피 — 설계자
  명시 가드). 두 mode 는 같은 ENGINE_ID / ENGINE_VERSION 을 공유할 뿐, 호출 진입점은
  분리.
- app/factors 의 책임(factor signal) 과 본 패키지의 책임(momentum 점검 결과 = momentum_result)
  은 의미가 다르므로 섞지 않는다.

저장 위치 정책:
- holdings mode: draft_payload.momentum_result (Step5B 한정 명시 승인된 6번째 키)
- universe mode: state/universe/universe_momentum_latest.json (Step5C — latest 1건 덮어쓰기)
- universe 결과는 draft_payload / Run top-level / message_text / Telegram 어디에도
  실리지 않는다 (Step5C 가드).

draft_payload 키 순번 (참고):
1) title
2) asof
3) note
4) recommendations
5) factor_signals (Step3)
6) momentum_result (Step5B — holdings mode 만)
"""

from app.momentum.holdings_mode import (
    ENGINE_ID,
    ENGINE_VERSION,
    build_holdings_momentum_result,
)
from app.momentum.universe_mode import (
    LATEST_ARTIFACT_FILE,
    build_universe_momentum_result,
    build_universe_momentum_result_scored,
    save_latest_artifact,
)

__all__ = [
    "ENGINE_ID",
    "ENGINE_VERSION",
    "build_holdings_momentum_result",
    "build_universe_momentum_result",
    "build_universe_momentum_result_scored",
    "save_latest_artifact",
    "LATEST_ARTIFACT_FILE",
]
