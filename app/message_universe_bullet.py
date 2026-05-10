"""POC2 Step 6 — draft_message.py 의 '외부 후보 점검' bullet 빌더 분리.

설계자 결정 (Step 6 §13):
- [판단 사유] 섹션의 3번째 bullet 본문을 만드는 책임만 본 모듈에 둔다.
- 헤더 / 순서 / 다른 bullet 통합은 draft_message 의 _render_judgment_lines 가 담당.
- pykrx 호출 / artifact 읽기 / 점수 계산은 전혀 하지 않는다 — payload 의 캐시된
  external_universe_check dict 에서만 정보를 가져온다.

이 파일을 별도 모듈로 둔 이유:
- draft_message.py KS-10 근접 (>=600) 해소.
- 1개 책임 1개 파일 원칙 (Step5D Cleanup 이후 강화).
"""

from __future__ import annotations

from typing import Any, Optional

# Step 6 — 외부 후보 점검 bullet 라벨. [판단 사유] 섹션 안 3번째 bullet.
EXTERNAL_UNIVERSE_BULLET_LABEL = "외부 후보 점검"


def basis_date_for_universe(universe: dict[str, Any]) -> str:
    """Step 6 §13 — 기준일 결정.

    1순위: top_candidate.price_history_basis.latest_date
    2순위: universe_momentum_latest.json.asof  (== universe['asof'])
    3순위: '기준일 확인 불가'
    """
    top = universe.get("top_candidate")
    if isinstance(top, dict):
        phb = top.get("price_history_basis")
        if isinstance(phb, dict):
            ld = phb.get("latest_date")
            if isinstance(ld, str) and ld.strip():
                return ld
    asof = universe.get("asof")
    if isinstance(asof, str) and asof.strip():
        return asof
    return "기준일 확인 불가"


def external_universe_bullet(payload: dict[str, Any]) -> Optional[str]:
    """draft_payload.external_universe_check 1줄 → bullet 본문. 없으면 None.

    포맷 (성공 / 부분 성공):
      "외부 후보 점검: pykrx 1개월 수익률 기준 {name}이 가장 높습니다(
       {score_value}%, 기준일 {basis_date}, 계산 가능 {scored}/{total}개).
       이 값은 매수 추천이 아닙니다."

    포맷 (실패):
      "외부 후보 점검: pykrx 가격 데이터 부족으로 1개월 점검값을 계산하지 못했습니다
       (기준일 {basis_date})."

    pre-refresh (artifact 부재) 시 GenerateDraft 가 external_universe_check 키 자체를
    추가하지 않으므로 본 함수는 None 반환.
    """
    universe = payload.get("external_universe_check")
    if not isinstance(universe, dict):
        return None
    refresh_status = universe.get("refresh_status")
    if refresh_status not in ("ok", "partial", "failed"):
        return None
    basis_date = basis_date_for_universe(universe)

    if refresh_status == "failed":
        return (
            f"- {EXTERNAL_UNIVERSE_BULLET_LABEL}: pykrx 가격 데이터 부족으로 "
            f"1개월 점검값을 계산하지 못했습니다(기준일 {basis_date})."
        )

    top = universe.get("top_candidate")
    if not isinstance(top, dict):
        return None
    score = top.get("score_result")
    if not isinstance(score, dict):
        return None
    score_value = score.get("score_value")
    name = top.get("name") or top.get("ticker") or "(이름 미상)"
    scored = universe.get("scored_count")
    total = universe.get("total_count")
    if not isinstance(scored, int) or not isinstance(total, int) or total <= 0:
        return None
    if score_value is None:
        return None

    return (
        f"- {EXTERNAL_UNIVERSE_BULLET_LABEL}: pykrx 1개월 수익률 기준 {name}이 "
        f"가장 높습니다({score_value}%, 기준일 {basis_date}, 계산 가능 "
        f"{scored}/{total}개). 이 값은 매수 추천이 아닙니다."
    )
