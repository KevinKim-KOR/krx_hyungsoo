"""POC2 3-PUSH — source key → 사용자 표시 라벨 매핑.

PUSH 사용자 표현 정리 STEP (2026-06-20):
- Telegram 본문/UI 에 내부 식별자(snake_case source key) 노출 금지 (지시문 §4.1).
- 모든 사용자 노출 위치는 본 모듈의 user_label_for() 를 거친다.
- 매핑은 지시문 §4.2 표 그대로.
"""

from __future__ import annotations

SOURCE_USER_LABELS: dict[str, str] = {
    "kr_realtime_price_snapshot": "국내 ETF 시세",
    "overnight_us_market_snapshot": "밤사이 미국 시장",
    "market_discovery_snapshot": "ETF 후보 흐름",
    "holdings_snapshot": "보유 종목 평가",
    "nav_discount_snapshot": "NAV·괴리율",
    "universe_momentum_snapshot": "급등락 관찰",
    "ml_baseline_v0": "위험 참고 데이터",
    "news_snapshot": "주요 뉴스",
}


def user_label_for(source_key: str) -> str:
    """내부 source key → 사용자 표시 라벨.

    매핑에 없으면 원본 key 를 그대로 반환하지 않고 안전한 fallback("기타 데이터") 을
    반환한다 — 내부 snake_case 가 사용자 노출되는 것을 차단 (AC-1).
    """
    label = SOURCE_USER_LABELS.get(source_key)
    if label:
        return label
    return "기타 데이터"


def user_labels_for(source_keys: list[str]) -> list[str]:
    """source key 목록 → 사용자 표시 라벨 목록 (중복 제거, 입력 순서 유지)."""
    seen: set[str] = set()
    result: list[str] = []
    for key in source_keys:
        label = user_label_for(key)
        if label in seen:
            continue
        seen.add(label)
        result.append(label)
    return result
