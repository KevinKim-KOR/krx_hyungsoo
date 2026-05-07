"""POC2 Step 5C — manual universe seed 파일 loader + asof 검증 + staleness 판정.

설계자 결정 (Step 5C 지시문 §5·§6·§7):
- 입력: state/universe/etf_universe_latest.json (수동 seed 파일).
- 외부 API 자동 수집 / 캐시 / DB 모두 미도입. 사용자가 수기로 작성하는 파일이다.
- 필수 top-level: asof / source / items.  필수 item: ticker / name. 선택 item:
  universe_group / sector_or_theme.
- asof 형식: YYYY-MM-DD. 누락 / 형식 오류 / 미래 날짜 / items 비배열 / items 빈
  배열은 모두 실패 처리 (UniverseSeedError). 오늘 날짜로 자동 보정 금지.
- staleness: UNIVERSE_SEED_MAX_AGE_DAYS = 30. 30일 초과 = stale (hard fail 아님,
  결과의 source_freshness="stale" 로 명시).

이 모듈은 외부 호출 / 디스크 쓰기를 일으키지 않는다. 읽기와 검증만.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

UNIVERSE_DIR = Path("state/universe")
UNIVERSE_SEED_FILE = UNIVERSE_DIR / "etf_universe_latest.json"

UNIVERSE_SEED_MAX_AGE_DAYS = 30

_ASOF_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class UniverseSeedError(ValueError):
    """universe seed 입력 검증 실패. 조용히 통과시키지 않는다."""


@dataclass
class UniverseSeedItem:
    ticker: str
    name: str
    universe_group: Optional[str] = None
    sector_or_theme: Optional[str] = None


@dataclass
class UniverseSeed:
    asof: str  # 'YYYY-MM-DD' (검증 통과한 값만)
    source: str
    items: list[UniverseSeedItem]
    source_freshness: str  # 'fresh' | 'stale'
    staleness_days: int  # 0 이상 정수


def _parse_asof(value: Any) -> date:
    """asof 검증 — 형식 / 미래 날짜 모두 차단."""
    if not isinstance(value, str) or not _ASOF_PATTERN.match(value):
        raise UniverseSeedError(
            f"asof 형식 오류 — YYYY-MM-DD 만 허용 (received: {value!r})"
        )
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as e:
        raise UniverseSeedError(f"asof 파싱 실패 (received: {value!r}): {e}")
    today = date.today()
    if parsed > today:
        raise UniverseSeedError(
            f"asof 가 미래 날짜입니다 (asof={value}, today={today.isoformat()})"
        )
    return parsed


def _coerce_item(raw: Any, idx: int) -> UniverseSeedItem:
    if not isinstance(raw, dict):
        raise UniverseSeedError(
            f"items[{idx}] 는 객체여야 합니다 (received: {type(raw).__name__})"
        )
    ticker = raw.get("ticker")
    if not isinstance(ticker, str) or not ticker.strip():
        raise UniverseSeedError(f"items[{idx}].ticker 가 비어있거나 문자열이 아닙니다.")
    name = raw.get("name")
    if not isinstance(name, str) or not name.strip():
        raise UniverseSeedError(f"items[{idx}].name 가 비어있거나 문자열이 아닙니다.")

    def _opt_str(key: str) -> Optional[str]:
        v = raw.get(key)
        if v is None:
            return None
        if not isinstance(v, str):
            raise UniverseSeedError(
                f"items[{idx}].{key} 는 문자열이거나 생략되어야 합니다."
            )
        s = v.strip()
        return s or None

    return UniverseSeedItem(
        ticker=ticker.strip(),
        name=name.strip(),
        universe_group=_opt_str("universe_group"),
        sector_or_theme=_opt_str("sector_or_theme"),
    )


def parse_universe_seed(raw: Any, today: Optional[date] = None) -> UniverseSeed:
    """raw dict 를 검증하고 UniverseSeed 로 변환. 실패 시 UniverseSeedError.

    today 인자는 테스트에서 staleness 판정 기준일을 고정하기 위함이며 미지정 시
    실제 오늘 날짜를 사용한다. asof 미래 날짜 검증은 _parse_asof 가 today 와
    무관하게 date.today() 기준으로 수행한다 (운영 정책 고정).
    """
    if not isinstance(raw, dict):
        raise UniverseSeedError("seed 페이로드는 객체여야 합니다.")

    if "asof" not in raw:
        raise UniverseSeedError("필수 필드 'asof' 가 누락됐습니다.")
    asof_date = _parse_asof(raw["asof"])

    source = raw.get("source")
    if not isinstance(source, str) or not source.strip():
        raise UniverseSeedError("필수 필드 'source' 가 비어있거나 문자열이 아닙니다.")

    items_raw = raw.get("items")
    if not isinstance(items_raw, list):
        raise UniverseSeedError("'items' 는 배열이어야 합니다.")
    if len(items_raw) == 0:
        raise UniverseSeedError("'items' 가 비어 있습니다.")

    items = [_coerce_item(it, i) for i, it in enumerate(items_raw)]

    base_today = today or date.today()
    delta_days = (base_today - asof_date).days
    if delta_days < 0:
        # 이중 안전 — _parse_asof 가 이미 미래 날짜를 차단했지만 today 인자가
        # asof 보다 과거면 음수가 나올 수 있다. 이 경우 staleness=0 으로 간주.
        delta_days = 0
    freshness = "stale" if delta_days > UNIVERSE_SEED_MAX_AGE_DAYS else "fresh"

    return UniverseSeed(
        asof=raw["asof"],
        source=source.strip(),
        items=items,
        source_freshness=freshness,
        staleness_days=delta_days,
    )


def load_universe_seed(
    path: Optional[Path] = None,
    today: Optional[date] = None,
) -> UniverseSeed:
    """state/universe/etf_universe_latest.json 을 읽고 검증.

    파일 부재 / JSON 파싱 실패도 UniverseSeedError 로 통일한다 — 호출자(API
    layer) 가 일관된 방식으로 422 등으로 변환할 수 있게.
    """
    target = path or UNIVERSE_SEED_FILE
    if not target.exists():
        raise UniverseSeedError(f"universe seed 파일이 없습니다: {target}")
    try:
        raw_text = target.read_text(encoding="utf-8")
    except OSError as e:
        raise UniverseSeedError(f"universe seed 파일 읽기 실패: {e}")
    try:
        raw = json.loads(raw_text)
    except json.JSONDecodeError as e:
        raise UniverseSeedError(f"universe seed JSON 파싱 실패: {e}")
    return parse_universe_seed(raw, today=today)
