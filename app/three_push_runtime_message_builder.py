"""OCI runtime 전용 단순 3-PUSH 메시지 빌더.

원칙 (지시문 §9):
  - runtime timestamp 포함
  - param_id 포함
  - push_kind 포함
  - data availability 포함
  - unavailable source 명시
  - 매매 지시 없음 명시
  - 추정 금지 (없는 데이터는 unavailable로 표시)
  - PC package message_text 재사용 금지
  - 신규 runtime probe 확장 금지 (OCI에서 외부 API 호출하지 않음)

이 빌더가 만드는 것:
  - text/plain Telegram body (sendMessage parse_mode=HTML 이지만 본문은 평문)
  - 모든 push_kind에서 동일한 구조: 헤더 → availability → 본문 안내 → 면책 푸터

이 빌더가 만들지 않는 것:
  - ETF 순위 / 매수/매도 후보 / 비중 조절 / threshold 판단
  - PC evidence 풍부도에 의존하는 본문
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Optional

from app.three_push_runtime_param import RuntimeParam

KST_OFFSET = timedelta(hours=9)


# push_kind별 기본 데이터 source 매핑 (현재 OCI에서 사용 불가 — unavailable 기본).
# 본 빌더는 외부 API 호출하지 않으므로 모든 source는 기본 unavailable.
PUSH_KIND_DATA_SOURCES = {
    "market_briefing": [
        "kr_realtime_price_snapshot",
        "overnight_us_market_snapshot",
        "market_discovery_snapshot",
        "ml_baseline_v0",
        "news_snapshot",
    ],
    "holdings_briefing": [
        "holdings_snapshot",
        "kr_realtime_price_snapshot",
        "nav_discount_snapshot",
        "ml_baseline_v0",
    ],
    "spike_or_falling_alert": [
        "universe_momentum_snapshot",
        "kr_realtime_price_snapshot",
    ],
}


PUSH_KIND_KOREAN = {
    "market_briefing": "시장 흐름 브리핑",
    "holdings_briefing": "보유 종목 관찰 브리핑",
    "spike_or_falling_alert": "급등락/상승 관찰 신호",
}


def kst_now_iso() -> str:
    """KST 기준 ISO-8601 표기."""
    now = datetime.now(timezone.utc).astimezone(timezone(KST_OFFSET))
    return now.strftime("%Y-%m-%dT%H:%M:%S+09:00")


def kst_today_date() -> str:
    """KST 기준 YYYY-MM-DD (duplicate guard runtime_window용)."""
    now = datetime.now(timezone.utc).astimezone(timezone(KST_OFFSET))
    return now.strftime("%Y-%m-%d")


def _build_availability_section(
    push_kind: str,
    available_sources: Optional[dict[str, str]] = None,
) -> tuple[list[str], list[str]]:
    """available_sources 는 {source_name: status} dict 또는 None.

    None이면 모든 source를 unavailable로 표시.
    status는 "available" 외에는 unavailable 취급.

    반환: (available 라인 목록, unavailable 라인 목록)
    """
    expected = PUSH_KIND_DATA_SOURCES.get(push_kind, [])
    statuses = available_sources or {}
    available_lines: list[str] = []
    unavailable_lines: list[str] = []
    for src in expected:
        st = statuses.get(src, "unavailable")
        if st == "available":
            available_lines.append(f"• {src}: available")
        else:
            unavailable_lines.append(f"• {src}: {st}")
    return available_lines, unavailable_lines


def build_runtime_message(
    *,
    push_kind: str,
    param: RuntimeParam,
    runtime_kst_iso: Optional[str] = None,
    available_sources: Optional[dict[str, str]] = None,
    extra_notes: Optional[list[str]] = None,
) -> str:
    """단일 push_kind에 대한 runtime 메시지 문자열을 만든다.

    인자:
      push_kind        : market_briefing / holdings_briefing / spike_or_falling_alert
      param            : 적용 중인 PARAM snapshot
      runtime_kst_iso  : 발송 시점 KST ISO-8601. 없으면 현재 KST.
      available_sources: {source_name: status}. 없으면 모든 source unavailable.
      extra_notes      : 본문에 추가할 안내 줄 목록 (선택).
    """
    if push_kind not in PUSH_KIND_KOREAN:
        raise ValueError(f"unknown push_kind: {push_kind!r}")

    ts = runtime_kst_iso or kst_now_iso()
    title = PUSH_KIND_KOREAN[push_kind]

    available_lines, unavailable_lines = _build_availability_section(
        push_kind, available_sources
    )

    lines: list[str] = []
    lines.append(f"[{title}]")
    lines.append(f"발송 시각(KST): {ts}")
    lines.append(f"param_id: {param.param_id}")
    lines.append(f"param_source: {param.param_source}")
    lines.append(f"push_kind: {push_kind}")
    lines.append("")
    lines.append("[데이터 가용성 (OCI runtime 기준)]")
    if available_lines:
        lines.extend(available_lines)
    else:
        lines.append("• 현재 가용 source 없음")
    if unavailable_lines:
        lines.append("")
        lines.append("[unavailable 또는 별도 확인 필요]")
        lines.extend(unavailable_lines)
    lines.append("")
    lines.append("[본문 안내]")
    lines.append(
        "본 알림은 사용자가 승인한 PARAM snapshot을 기준으로 OCI runtime에서 생성되었습니다."
    )
    lines.append(
        "표시되지 않은 source는 OCI runtime에서 직접 확인 불가하며, 추정값을 표시하지 않습니다."
    )
    if extra_notes:
        for note in extra_notes:
            lines.append(f"• {note}")
    lines.append("")
    lines.append("[면책]")
    lines.append(
        "본 메시지는 정보 제공 목적이며 매매 / 비중 조절 / 위험 판단을 지시하지 않습니다."
    )
    return "\n".join(lines)


def availability_summary(
    available_sources: Optional[dict[str, str]],
) -> dict[str, int]:
    """status 분포 요약. 모니터링/status JSON 에 포함하기 위한 용도."""
    if not available_sources:
        return {"available": 0, "unavailable_or_other": 0}
    available = sum(1 for v in available_sources.values() if v == "available")
    other = sum(1 for v in available_sources.values() if v != "available")
    return {"available": available, "unavailable_or_other": other}
