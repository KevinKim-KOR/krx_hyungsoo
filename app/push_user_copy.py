"""POC2 3-PUSH — 사용자 중심 PUSH 본문 보조 빌더.

PUSH 사용자 표현 정리 STEP (2026-06-20):
- 지시문 §4.3 — 전체 unavailable 메시지 축약 (운영 로그처럼 source key 나열 X).
- 지시문 §4.4 — 일부 available 메시지 구조 (지금 확인된 흐름 / 해석 참고 신호 /
  별도 확인 필요 / 짧은 주의 문장).
- 본 모듈은 message builder 가 호출하는 보조 helper. 매수/매도/교체/비중 조절
  지시 문구 0건.
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Optional

from app.push_user_labels import user_labels_for

# 사용자 표시용 KST 변환을 위한 고정 offset (외부 의존성 추가 금지 — stdlib only).
_KST = timezone(timedelta(hours=9))

# push_kind 별 사용자 표시 제목 / 보조 라벨.
PUSH_KIND_HEADERS: dict[str, str] = {
    "market_briefing": "[시장 흐름 브리핑]",
    "holdings_briefing": "[보유 종목 관찰 브리핑]",
    "spike_or_falling_alert": "[급등락·상승 관찰 신호]",
}

# push_kind 별 전체 unavailable 시 안내 문장 (지시문 §4.3 예시 그대로).
_ALL_UNAVAILABLE_LEAD: dict[str, str] = {
    "market_briefing": (
        "오늘은 자동 확인 가능한 시장 데이터가 부족해\n시장 해석을 보류합니다."
    ),
    "holdings_briefing": (
        "현재 OCI에서 보유 종목 평가에 필요한 자동 확인 데이터가 부족합니다."
    ),
    "spike_or_falling_alert": (
        "현재 OCI에서 급등락 관찰에 필요한 자동 확인 데이터가 부족합니다."
    ),
}

# push_kind 별 짧은 주의 문장 (지시문 §4.3 예시 그대로 — 매매 지시 아님 명시).
NEUTRAL_NOTES: dict[str, str] = {
    "market_briefing": (
        "이 알림은 시장 확인용 정보이며 직접적인 매매 지시는 아닙니다."
    ),
    "holdings_briefing": (
        "이 알림은 보유 현황 확인용 정보이며 매도·교체·비중 조절을 지시하지 않습니다."
    ),
    "spike_or_falling_alert": (
        "이 알림은 시장 관찰용 정보이며 직접적인 매매 지시는 아닙니다."
    ),
}


def format_asof_for_user(asof_iso: Optional[str]) -> str:
    """ISO 시각 → 사용자 친화 한국어 표시 (예: '6월 20일 14:14').

    파싱 실패 시 "방금 전" 으로 안전 fallback. asof_iso 가 None/빈문자열이면
    "방금 전" — 운영용 raw 시각을 사용자에게 노출하지 않는다.
    """
    if not asof_iso:
        return "방금 전"
    try:
        # ISO 8601 형식 + 끝 'Z' 도 수용.
        s = asof_iso.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        dt_kst = dt.astimezone(_KST)
        return f"{dt_kst.month}월 {dt_kst.day}일 {dt_kst.strftime('%H:%M')}"
    except (ValueError, TypeError):
        return "방금 전"


def build_all_unavailable_message(
    *,
    push_kind: str,
    asof_iso: Optional[str],
    unavailable_source_keys: list[str],
) -> str:
    """모든 source 가 unavailable 일 때 사용자에게 보낼 짧은 메시지 (지시문 §4.3).

    예 (market_briefing):
        [시장 흐름 브리핑]

        기준 시각: 6월 20일 14:14

        오늘은 자동 확인 가능한 시장 데이터가 부족해
        시장 해석을 보류합니다.

        별도 확인 필요
        • 국내 ETF 시세
        • 밤사이 미국 시장

        이 알림은 시장 확인용 정보이며 직접적인 매매 지시는 아닙니다.

    source key 는 사용자 라벨로 변환 (raw snake_case 노출 0건).
    """
    header = PUSH_KIND_HEADERS.get(push_kind, "[알림]")
    lead = _ALL_UNAVAILABLE_LEAD.get(
        push_kind,
        "현재 자동 확인 가능한 데이터가 부족합니다.",
    )
    note = NEUTRAL_NOTES.get(
        push_kind,
        "이 알림은 정보 확인용이며 직접적인 매매 지시는 아닙니다.",
    )
    asof_human = format_asof_for_user(asof_iso)

    parts: list[str] = [header, "", f"기준 시각: {asof_human}", "", lead, ""]
    labels = user_labels_for(unavailable_source_keys)
    if labels:
        parts.append("별도 확인 필요")
        for label in labels:
            parts.append(f"• {label}")
        parts.append("")
    parts.append(note)
    return "\n".join(parts).rstrip()


def collect_unavailable_source_keys(
    *,
    push_kind: str,
    pc_evidence: dict,
    runtime_snapshot: dict,
) -> list[str]:
    """push_kind 에 필요한 source 중 unavailable/missing 인 것의 key 목록.

    매핑 기준:
      - kr_realtime_price_snapshot / overnight_us_market_snapshot 은
        runtime_snapshot 의 status 가 ok/partial 이 아니면 unavailable.
      - market_discovery_snapshot / holdings_snapshot / universe_momentum_snapshot
        / nav_discount_snapshot / ml_baseline_snapshot 은 pc_evidence 의 dict 가
        비어있으면 unavailable.
      - news_snapshot 은 pc_evidence 안에 키가 있으면 그 status 를 본다.

    push_kind 별로 사용자에게 의미 있는 source 만 추출:
      market_briefing: kr_realtime / overnight_us / market_discovery / news (news 는 있을 때만)
      holdings_briefing: holdings / kr_realtime / nav_discount / ml_baseline
      spike_or_falling_alert: universe_momentum / kr_realtime
    """

    def _is_unavail_runtime(key: str) -> bool:
        snap = runtime_snapshot.get(key)
        if not isinstance(snap, dict):
            return True
        st = snap.get("status")
        return st not in ("ok", "partial")

    def _is_unavail_evidence(key: str) -> bool:
        ev = pc_evidence.get(key)
        if not isinstance(ev, dict) or not ev:
            return True
        st = ev.get("status")
        if st is not None:
            return st in ("unavailable", "failed", "error", None)
        # status 없이 dict 만 있으면 내용 존재 = available 로 간주.
        return False

    def _check(key: str, source: str) -> bool:
        if source == "runtime":
            return _is_unavail_runtime(key)
        return _is_unavail_evidence(key)

    PUSH_REQUIREMENTS: dict[str, list[tuple[str, str]]] = {
        "market_briefing": [
            ("overnight_us_market_snapshot", "runtime"),
            ("kr_realtime_price_snapshot", "runtime"),
            ("market_discovery_snapshot", "evidence"),
            ("ml_baseline_v0", "evidence"),
        ],
        "holdings_briefing": [
            ("holdings_snapshot", "evidence"),
            ("kr_realtime_price_snapshot", "runtime"),
            ("nav_discount_snapshot", "evidence"),
            ("ml_baseline_v0", "evidence"),
        ],
        "spike_or_falling_alert": [
            ("universe_momentum_snapshot", "evidence"),
            ("kr_realtime_price_snapshot", "runtime"),
        ],
    }
    # pc_evidence 의 ml 키 이름 정렬 — 일부 코드에선 ml_baseline_snapshot 사용.
    ml_synonyms = ("ml_baseline_v0", "ml_baseline_snapshot")

    result: list[str] = []
    for key, source in PUSH_REQUIREMENTS.get(push_kind, []):
        if key in ml_synonyms:
            # 두 key 중 하나라도 있으면 available 로 간주.
            present = False
            for cand in ml_synonyms:
                ev = pc_evidence.get(cand)
                if isinstance(ev, dict) and ev:
                    st = ev.get("status")
                    if st not in ("unavailable", "failed", "error"):
                        present = True
                        break
            if not present:
                result.append("ml_baseline_v0")
            continue
        if _check(key, source):
            result.append(key)
    return result


def render_unavailable_block(unavailable_source_keys: list[str]) -> list[str]:
    """일부 available 메시지의 "별도 확인 필요" 블록 (지시문 §4.4 step 3).

    빈 목록이면 빈 리스트 반환 — 호출자가 블록 자체를 생략.
    """
    labels = user_labels_for(unavailable_source_keys)
    if not labels:
        return []
    lines: list[str] = ["별도 확인 필요"]
    for label in labels:
        lines.append(f"• {label}")
    return lines
