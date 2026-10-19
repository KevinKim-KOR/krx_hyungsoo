"""POC5-24 — 「보유와 비교」 판단 근거 미리보기 → AI 세션 기록(선택 근거 모드) 규칙.

선택 근거 모드 기록 = `source_screen == SELECTED_PREVIEW_SOURCE_SCREEN` 이고 저장 후보가 1건이며
그 후보에 `selected_preview`(처음 넘긴 미리보기 원문 · 대상 종류 · 생성 시각 · 근거 날짜)가 있는 기록.
저장 위치는 기존 `candidate_snapshot_json` 안 선택 필드(새 표 · 열 없음). 일반 후보가 우연히 1건인
옛 기록은 선택 근거 모드가 아니다.

쓰기 규칙(저장소 `insert_record` 한 곳에서 검사):
- `selected_preview` 는 선택 근거 화면 값에서만 · 그 화면 값이면 후보 1건 + `selected_preview` 필수.
- 원문 · 생성 시각 비어 있으면 안 됨 · 대상 종류 = holding / candidate.
- 기록 기준일(`asof`) = 가격 기준일(`evidence_as_of.target_as_of_date`) · 없으면 생성 시각의 KST 날짜.
  가격 기준일 칸을 생성일로 채우지 않는다(없으면 없음 그대로).
- 시장 문맥 · 구성종목 · 중복 · 단기 · 자료 품질 · ML 근거 스냅샷은 받지 않는다(다른 자료로 바꿔 넣지 않음).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

SELECTED_PREVIEW_SOURCE_SCREEN = "holdings_compare_preview"
SELECTED_PREVIEW_TARGET_KINDS = ("holding", "candidate")

_KST = timezone(timedelta(hours=9))


def is_selected_preview_record(
    source_screen: object, candidate_snapshot: object
) -> bool:
    """읽기 판정 — 화면 값 · 후보 1건 · selected_preview 객체가 모두 맞을 때만."""
    return (
        source_screen == SELECTED_PREVIEW_SOURCE_SCREEN
        and isinstance(candidate_snapshot, list)
        and len(candidate_snapshot) == 1
        and isinstance(candidate_snapshot[0], dict)
        and isinstance(candidate_snapshot[0].get("selected_preview"), dict)
    )


def selected_target_label(
    source_screen: object, candidate_snapshot: object
) -> Optional[str]:
    """목록 표시용 '이름(티커)' — 선택 근거 모드 기록만 · 그 밖은 None."""
    if not is_selected_preview_record(source_screen, candidate_snapshot):
        return None
    c = candidate_snapshot[0]  # type: ignore[index]
    name = c.get("name") if isinstance(c.get("name"), str) else ""
    ticker = c.get("ticker") if isinstance(c.get("ticker"), str) else ""
    name, ticker = name.strip(), ticker.strip()
    if name and ticker:
        return f"{name}({ticker})"
    return name or ticker or None


def kst_date_of(generated_at: str) -> Optional[str]:
    """생성 시각(ISO-8601)의 KST 날짜 'YYYY-MM-DD' · 시간대 없는 값은 KST 로 본다 · 해석 못 하면 None."""
    try:
        dt = datetime.fromisoformat(generated_at.strip())
    except (AttributeError, TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_KST)
    return dt.astimezone(_KST).date().isoformat()


def selected_preview_error(
    *, asof: str, source_screen: str, candidate_snapshot: list, other_snapshots: dict
) -> Optional[str]:
    """쓰기 검사 — 규칙 위반이면 사유 문장 · 아니면 None. 선택 근거와 무관한 기록은 그대로 통과."""
    has_sp = any(
        isinstance(c, dict) and c.get("selected_preview") is not None
        for c in candidate_snapshot
    )
    if source_screen != SELECTED_PREVIEW_SOURCE_SCREEN:
        if has_sp:
            return (
                "selected_preview is only allowed when source_screen is "
                f"{SELECTED_PREVIEW_SOURCE_SCREEN!r}."
            )
        return None
    if len(candidate_snapshot) != 1 or not is_selected_preview_record(
        source_screen, candidate_snapshot
    ):
        return (
            f"source_screen {SELECTED_PREVIEW_SOURCE_SCREEN!r} requires exactly one "
            "candidate with selected_preview."
        )
    sp = candidate_snapshot[0]["selected_preview"]
    if sp.get("target_kind") not in SELECTED_PREVIEW_TARGET_KINDS:
        return f"selected_preview.target_kind must be one of {SELECTED_PREVIEW_TARGET_KINDS}."
    text = sp.get("preview_text")
    if not isinstance(text, str) or not text.strip():
        return "selected_preview.preview_text is required."
    generated_at = sp.get("generated_at")
    gen_date = kst_date_of(generated_at) if isinstance(generated_at, str) else None
    if gen_date is None:
        return "selected_preview.generated_at must be an ISO-8601 timestamp."
    as_of = (
        sp.get("evidence_as_of") if isinstance(sp.get("evidence_as_of"), dict) else {}
    )
    price_date = as_of.get("target_as_of_date")
    expected = price_date if isinstance(price_date, str) and price_date else gen_date
    if asof != expected:
        return (
            f"asof must be {expected!r} (price as-of date, or the KST date of "
            "generated_at when the price date is unknown)."
        )
    filled = sorted(k for k, v in other_snapshots.items() if v)
    if filled:
        return f"selected preview record does not take other snapshots: {filled}."
    return None
