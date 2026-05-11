"""POC2 Step 7B — 보유 종목 상태 브리핑 (PUSH 1) bullet 빌더 분리.

분리 목적:
- draft_message.py KS-10 trigger 해소 (673 → ~570).
- 1개 책임 1개 파일 원칙 (Step5D Cleanup 이후 강화).

설계자 결정 (Step 7B §3.1):
- 기존 portfolio scope factor signal (보유 비중 영향) 의 reason_text 첫 문장 +
  holdings momentum top_candidate.reason_text 첫 문장을 1줄 bullet 로 통합.
- 사용자 노출 placeholder 표현 ("placeholder 기준으로") 은 "현재 보유 종목 점검
  기준으로" 로 정정.
- 매수/매도 의견 아님 중립 안내 항상 부착.

본 모듈은 draft_payload dict 를 입력받아 bullet 본문 1줄을 반환할 뿐, 다른 책임은
없다. draft_message.py 의 _render_judgment_lines 가 본 함수를 호출한다.
"""

from __future__ import annotations

from typing import Any, Optional

HOLDINGS_STATUS_BRIEFING_LABEL = "보유 종목 상태 브리핑"
HOLDINGS_STATUS_BRIEFING_NEUTRAL_NOTE = "이 내용은 매수/매도 의견이 아닙니다."

# Step 7B §3.2 — holdings momentum reason_text 안의 "placeholder 기준으로" 사용자
# 노출 표현을 중립 표현으로 정정.
_PLACEHOLDER_USER_FACING_PATTERN = "placeholder 기준으로"
_PLACEHOLDER_USER_FACING_REPLACEMENT = "현재 보유 종목 점검 기준으로"


def first_sentence(text: str) -> str:
    """문장의 첫 마침표(. ) 또는 끝의 마침표까지를 첫 문장으로 반환.

    형식 가정:
    - "AAA. BBB." → "AAA."
    - "AAA. " → "AAA."
    - "AAA"  → "AAA"
    """
    stripped = text.strip()
    idx = stripped.find(". ")
    if idx >= 0:
        return stripped[: idx + 1]
    return stripped


def build_holdings_status_briefing_bullet(payload: dict[str, Any]) -> Optional[str]:
    """보유 종목 상태 브리핑 (PUSH 1) bullet 통합 빌더.

    데이터 소스 2개를 1줄로 통합:
    1. factor_signals 의 scope="portfolio" signal 의 reason_text 첫 문장.
    2. momentum_result.summary.top_candidate.reason_text 첫 문장
       (placeholder 사용자 노출 표현 정정).

    문구 구조:
      "- 보유 종목 상태 브리핑: {portfolio 첫 문장} {momentum 첫 문장} 이 내용은
       매수/매도 의견이 아닙니다."

    두 데이터 모두 없으면 None 반환 (bullet 미생성). 하나만 있어도 가능한 부분만
    포함 + 중립 안내 1문장 항상 끝에 부착.
    """
    parts: list[str] = []

    # 1) portfolio scope signal — reason_text 또는 fallback_text 의 첫 문장.
    factor_signals = payload.get("factor_signals")
    if isinstance(factor_signals, list):
        for sig in factor_signals:
            if not isinstance(sig, dict):
                continue
            if sig.get("scope") != "portfolio":
                continue
            text = (
                sig.get("reason_text")
                if sig.get("is_available")
                else sig.get("fallback_text")
            )
            if isinstance(text, str) and text.strip():
                first = first_sentence(text)
                if first:
                    parts.append(first)
            break

    # 2) holdings momentum top_candidate.reason_text 첫 문장 (placeholder 표현 정정).
    momentum = payload.get("momentum_result")
    if isinstance(momentum, dict):
        summary = momentum.get("summary")
        if isinstance(summary, dict):
            top = summary.get("top_candidate")
            text: Optional[str] = None
            if isinstance(top, dict):
                t = top.get("reason_text")
                if isinstance(t, str) and t.strip():
                    text = t
            if text is None:
                sr = summary.get("summary_reason_text")
                if isinstance(sr, str) and sr.strip():
                    text = sr
            if text is not None:
                first = first_sentence(text)
                if first:
                    first = first.replace(
                        _PLACEHOLDER_USER_FACING_PATTERN,
                        _PLACEHOLDER_USER_FACING_REPLACEMENT,
                    )
                    parts.append(first)

    if not parts:
        return None

    body = " ".join(parts) + " " + HOLDINGS_STATUS_BRIEFING_NEUTRAL_NOTE
    return f"- {HOLDINGS_STATUS_BRIEFING_LABEL}: {body}"
