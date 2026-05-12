"""POC2 Step 7C — 급락 ETF 주의 신호 (PUSH 3) bullet 빌더 분리.

분리 목적:
- draft_message.py KS-10 trigger 사전 회피 + 1개 책임 1개 파일 원칙.
- Step6 의 message_universe_bullet.py / Step7B 의 message_holdings_briefing.py 와 같은
  패턴.

설계자 결정 (Step 7C §3.5):
- universe_momentum_latest.json 의 summary.falling_candidate 가 있을 때만 bullet 생성.
- bullet 형식:
  "- 급락 ETF 주의 신호: pykrx 1개월 수익률 기준 {name}이 {score_value}%로 초기 급락
   기준({threshold}%) 이하입니다(기준일 {basis_date}). 이 값은 매수/매도 지시가 아닙니다."
- threshold_pct 는 호출자가 결정 (Step 7C 초기값 -10.0%, 확정값 아님).
- "매수/매도 지시가 아닙니다" 중립 안내 항상 포함.

본 모듈은 draft_payload 의 factor_signals scope="universe_falling" signal 에 들어갈
reason_text 1줄을 만든다. draft_message.py 의 _render_judgment_lines 가 호출.
"""

from __future__ import annotations

from typing import Any, Optional

FALLING_ETF_CAUTION_BULLET_LABEL = "급락 ETF 주의 신호"
FALLING_ETF_CAUTION_NEUTRAL_NOTE = "이 값은 매수/매도 지시가 아닙니다."
FALLING_ETF_CAUTION_FACTOR_SCOPE = "universe_falling"


def build_falling_etf_signal_text(
    name: str,
    score_value: float,
    threshold_pct: float,
    basis_date: str,
) -> str:
    """Step 7C 급락 ETF 주의 신호 reason_text (factor signal 의 본문) 생성.

    Step7C §3.5 정확한 문구:
      "pykrx 1개월 수익률 기준 {name}이 {score_value}%로 초기 급락 기준({threshold}%)
       이하입니다(기준일 {basis_date}). 이 값은 매수/매도 지시가 아닙니다."

    threshold_pct 는 확정값이 아니라 운영 검증 대상 — "초기 급락 기준" 이라는 표현으로
    명시. score_value / threshold_pct 모두 음수 (예: -12.5, -10.0).
    """
    return (
        f"pykrx 1개월 수익률 기준 {name}이 {score_value}%로 초기 급락 기준"
        f"({threshold_pct}%) 이하입니다(기준일 {basis_date}). "
        f"{FALLING_ETF_CAUTION_NEUTRAL_NOTE}"
    )


def extract_falling_etf_bullet(payload: dict[str, Any]) -> Optional[str]:
    """factor_signals 의 scope="universe_falling" signal → bullet 본문.

    falling_candidate 가 universe_momentum_latest.json 에 없으면 draft.py 가 signal
    자체를 추가하지 않으므로 본 함수는 None 반환 → [판단 사유] 에 bullet 미생성.
    (Step7C §3.4 — 급락 신호 없음 시 Telegram 에 "신호 없음" 문구 미발송, KS-5 가드.)
    """
    factor_signals = payload.get("factor_signals")
    if not isinstance(factor_signals, list):
        return None
    falling_sig: Optional[dict[str, Any]] = None
    for sig in factor_signals:
        if (
            isinstance(sig, dict)
            and sig.get("scope") == FALLING_ETF_CAUTION_FACTOR_SCOPE
        ):
            falling_sig = sig
            break
    if falling_sig is None:
        return None
    if not falling_sig.get("is_available"):
        return None
    factor_name = falling_sig.get("factor_name") or FALLING_ETF_CAUTION_BULLET_LABEL
    text = falling_sig.get("reason_text")
    if not isinstance(text, str) or not text.strip():
        return None
    return f"- {factor_name}: {text}"
