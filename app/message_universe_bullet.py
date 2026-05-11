"""POC2 Step 6 + Fix 라운드 — universe momentum signal 의 reason_text / fallback_text 빌더.

설계자 결정 (Step 6 §13 + Fix 라운드 2026-05-11):
- universe momentum top_candidate 의 메시지 반영은 draft_payload.factor_signals 안의
  scope="universe" signal 1건으로 표현한다 (draft_payload 키 추가 없음, BACKLOG 가드 준수).
- 본 모듈은 그 signal 의 reason_text / fallback_text 두 문자열을 만든다.
- 길이 / 형식 / 기준일 표기 정책은 §13 그대로:
  · 성공 / 부분 성공: reason_text = "pykrx 1개월 수익률 기준 {name}이 가장 높습니다(
       {value}%, 기준일 {basis_date}, 계산 가능 {scored}/{total}개).
       이 값은 매수 추천이 아닙니다."
  · 실패: fallback_text = "pykrx 가격 데이터 부족으로 1개월 점검값을 계산하지 못했습니다(
       기준일 {basis_date})."
- draft_message.py 의 _render_judgment_lines 는 factor_signals 의 scope="universe" signal
  을 picker 로 잡아 bullet 본문 ("- 외부 후보 점검: <reason_text or fallback_text>") 으로
  렌더링한다.

이 파일을 별도 모듈로 둔 이유:
- draft_message.py KS-10 근접 (>=600) 해소.
- 1개 책임 1개 파일 원칙.
"""

from __future__ import annotations

from typing import Any, Optional


def build_universe_signal_texts(
    refresh_status: Optional[str],
    top_candidate: Optional[dict[str, Any]],
    scored: int,
    total: int,
    basis_date: str,
) -> tuple[Optional[str], Optional[str], Optional[float]]:
    """factor signal 의 (reason_text, fallback_text, value) 3-tuple 반환.

    is_available 판정:
    - refresh_status in {"ok", "partial"} + top_candidate 존재 + score_value 추출 가능
      → reason_text 채움 + value 채움. fallback_text = None.
    - 그 외 (refresh_status="failed" / top_candidate 부재 / score_value 누락):
      → reason_text = None. fallback_text 채움. value = None.
    """
    if refresh_status in ("ok", "partial") and isinstance(top_candidate, dict):
        score_result = top_candidate.get("score_result")
        if isinstance(score_result, dict):
            score_value = score_result.get("score_value")
            name = (
                top_candidate.get("name")
                or top_candidate.get("ticker")
                or "(이름 미상)"
            )
            if (
                isinstance(score_value, (int, float))
                and isinstance(scored, int)
                and isinstance(total, int)
                and total > 0
            ):
                reason_text = (
                    f"pykrx 1개월 수익률 기준 {name}이 가장 높습니다"
                    f"({score_value}%, 기준일 {basis_date}, 계산 가능 "
                    f"{scored}/{total}개). 이 값은 매수 추천이 아닙니다."
                )
                return reason_text, None, float(score_value)

    fallback_text = (
        f"pykrx 가격 데이터 부족으로 1개월 점검값을 계산하지 못했습니다"
        f"(기준일 {basis_date})."
    )
    return None, fallback_text, None
