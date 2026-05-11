"""POC2 Step 5B + 5C + 6 — Momentum Engine 패키지.

설계자 결정 (Step5A 계약 + Step5B/5C/6 가드):
- Momentum Engine 은 holdings mode 와 universe mode 가 공유하는 공통 엔진 자리.
- Step5B: holdings mode placeholder 산식 (pnl_rate) 1회 실행.
- Step5C: universe mode (manual seed → score 없는 momentum_result + latest artifact 저장).
- Step6: universe mode 에 pykrx 1개월 기간 수익률 1개 적용 (one_month_return_pct).
  bounded sync refresh (20 items / 0.5s delay / 30s budget). pykrx 호출은
  app/price_history_pykrx.py 1개 모듈만 사용 — 본 패키지는 호출하지 않는다.
- 추상 클래스 / registry / plugin 구조는 도입 금지 (premature abstraction 회피 — 설계자
  명시 가드). 두 mode 는 같은 ENGINE_ID / ENGINE_VERSION 을 공유할 뿐, 호출 진입점은
  분리.
- app/factors 의 책임(factor signal) 과 본 패키지의 책임(momentum 점검 결과 = momentum_result)
  은 의미가 다르나, Step6 시점 universe momentum top_candidate 의 메시지 반영은
  draft_payload.factor_signals 안에 scope="universe" signal 1건으로 표현한다
  (draft_payload 키 추가 없음 — 사용자(설계자) 결정, BACKLOG 가드 준수).

저장 위치 정책:
- holdings mode: draft_payload.momentum_result (Step5B 한정 명시 승인된 6번째 키)
- universe mode 산출 본문: state/universe/universe_momentum_latest.json
  (Step5C — latest 1건 덮어쓰기. Step6 — refresh_status / data_source / score_basis /
   top_candidate / price_history_basis 확장)
- universe mode 결과의 메시지 반영: draft_payload.factor_signals 안의 scope="universe"
  signal 1건 (Step6 — 사용자 결정, draft_payload 7번째 키 신설 금지 가드 준수).
  factor signal 의 reason_text / fallback_text 가 [판단 사유] 의 "외부 후보 점검"
  bullet 본문이 된다.
- universe 후보 전체 / 후보 candidates 배열 / 점수 상세는 draft_payload / Run top-level /
  message_text / Telegram 어디에도 노출하지 않는다 (Step6 §11 / §13 / §18 / AC-28).

draft_payload 키 순번 (Step6 시점 그대로 유지 — 키 추가 없음):
1) title
2) asof
3) note
4) recommendations
5) factor_signals (Step3 — portfolio / holding_row + Step6 universe scope 추가)
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
