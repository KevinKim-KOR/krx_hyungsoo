"""OCI runtime 전용 단순 3-PUSH 메시지 빌더.

PUSH 사용자 표현 정리 STEP (2026-06-20, 지시문 §4):
- raw 기술 식별자 (param_id / param_source / push_kind / snake_case source key)
  본문 노출 금지.
- 사용자 표시 라벨로만 노출 (app.push_user_labels).
- 전체 unavailable 시 사용자 중심 축약 메시지 (app.push_user_copy).
- 매매 지시 0건. 추정 금지.

PARAM Handoff 원칙 (지시문 §9):
  - PC package message_text 재사용 금지 — PARAM 만 가지고 OCI 에서 생성.
  - 신규 runtime probe 확장 금지 (OCI 에서 외부 API 호출하지 않음).
  - 모든 source 는 기본 unavailable.

이 빌더가 만드는 것:
  - 사용자 중심 Telegram body — 헤더 + 기준 시각 + 안내 + 별도 확인 필요 + 면책.

이 빌더가 만들지 않는 것:
  - ETF 순위 / 매수/매도 후보 / 비중 조절 / threshold 판단.
  - raw 식별자 노출 (param_id / push_kind / snake_case source key 등).
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
    "spike_or_falling_alert": "급등락·상승 관찰 신호",
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
    """단일 push_kind 에 대한 runtime 메시지 문자열을 만든다.

    PUSH 사용자 표현 정리 STEP (2026-06-20, 지시문 §4):
      - raw 기술 식별자 (param_id / param_source / push_kind / snake_case source key)
        본문 노출 금지. param 은 duplicate guard / status 기록 / 로그용으로만
        사용되며 본문에는 들어가지 않는다.
      - 사용자 표시 라벨만 노출 (app.push_user_labels).
      - 모든 source 가 unavailable 인 경우 (현재 PARAM runtime 의 기본 상태):
        사용자 중심 축약 메시지 (build_all_unavailable_message). 운영 진단
        로그처럼 source 목록을 길게 나열하지 않는다 (지시문 §4.3).
      - 일부 source 가 available 인 경우: 헤더 + (available 요약) +
        "별도 확인 필요" 사용자 라벨 블록 + 면책 (지시문 §4.4).

    인자:
      push_kind        : market_briefing / holdings_briefing / spike_or_falling_alert
      param            : 적용 중인 PARAM snapshot (본문 노출 X — 호출자가 status 기록용)
      runtime_kst_iso  : 발송 시점 KST ISO-8601. 없으면 현재 KST.
      available_sources: {source_name: status}. 없으면 모든 source unavailable.
      extra_notes      : 본문에 추가할 안내 줄 목록 (선택, 사용자 친화 문장만).
    """
    if push_kind not in PUSH_KIND_KOREAN:
        raise ValueError(f"unknown push_kind: {push_kind!r}")

    # PARAM 은 발송 정책 / 로그 / duplicate guard 에만 사용. 본문 노출 X.
    _ = param  # 사용자 본문에는 param_id / param_source 를 절대 포함하지 않는다.

    ts = runtime_kst_iso or kst_now_iso()

    expected = PUSH_KIND_DATA_SOURCES.get(push_kind, [])
    statuses = available_sources or {}
    available_keys: list[str] = []
    unavailable_keys: list[str] = []
    for src in expected:
        st = statuses.get(src, "unavailable")
        if st == "available":
            available_keys.append(src)
        else:
            unavailable_keys.append(src)

    # 전체 unavailable — 사용자 중심 축약 메시지 (지시문 §4.3).
    if not available_keys:
        from app.push_user_copy import build_all_unavailable_message

        text = build_all_unavailable_message(
            push_kind=push_kind,
            asof_iso=ts,
            unavailable_source_keys=unavailable_keys,
        )
        if extra_notes:
            # extra_notes 는 사용자 친화 문장만 허용 (호출자 책임).
            text = text + "\n\n" + "\n".join(f"• {n}" for n in extra_notes)
        return text

    # 일부 available — 헤더 + available 요약 + 별도 확인 필요 + 면책 (§4.4).
    from app.push_user_copy import (
        NEUTRAL_NOTES,
        PUSH_KIND_HEADERS,
        format_asof_for_user,
        render_unavailable_block,
    )
    from app.push_user_labels import user_labels_for

    header = PUSH_KIND_HEADERS.get(push_kind, f"[{PUSH_KIND_KOREAN[push_kind]}]")
    note = NEUTRAL_NOTES.get(
        push_kind, "이 알림은 정보 확인용이며 직접적인 매매 지시는 아닙니다."
    )

    lines: list[str] = [header, "", f"기준 시각: {format_asof_for_user(ts)}", ""]
    # available 요약 — 사용자 라벨 + 짧은 안내.
    lines.append("지금 확인된 항목")
    for label in user_labels_for(available_keys):
        lines.append(f"• {label}")
    lines.append("")

    unavail_block = render_unavailable_block(unavailable_keys)
    if unavail_block:
        lines.extend(unavail_block)
        lines.append("")

    if extra_notes:
        for n in extra_notes:
            lines.append(f"• {n}")
        lines.append("")

    lines.append(note)
    return "\n".join(lines).rstrip()


def availability_summary(
    available_sources: Optional[dict[str, str]],
) -> dict[str, int]:
    """status 분포 요약. 모니터링/status JSON 에 포함하기 위한 용도."""
    if not available_sources:
        return {"available": 0, "unavailable_or_other": 0}
    available = sum(1 for v in available_sources.values() if v == "available")
    other = sum(1 for v in available_sources.values() if v != "available")
    return {"available": available, "unavailable_or_other": other}
