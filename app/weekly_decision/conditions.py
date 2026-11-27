"""POC7-04 — 저장된 조회 조건 칸 판정 한 곳(검증 F18 · F20 · 반박 검토 D1 · history 600줄 근접에서 나눔).

저장 기록(「AI 투자 세션」) · 내 판단 기록의 제외 조건 칸은 이 모듈로만 읽고 판정한다.
- 참 · 거짓 값(JSON 불리언)만 참 · 거짓으로 본다. 문자열 'false' · 숫자 · 객체 · null · NaN = 형식 오류.
- 같은 칸이 서로 다른 값으로 두 번 이상 저장되면 마지막 값으로 덮지 않고 '값 충돌'로 둔다.
- 원값은 들고 다니지 않는다 — 표시(MISSING · INVALID · CONFLICT)만 들어 새 저장 스냅숏이 끊기지 않게.
"""

from __future__ import annotations

import json
from typing import Any, Iterable, Mapping

MISSING, INVALID, CONFLICT = "missing", "invalid", "conflict"
# 읽는 동안만 쓰는 표시 — 같은 칸에 서로 다른 값(stored_filters · 형 검사가 걸러 냄)
_CLASH = object()


def _same(a: Any, b: Any) -> bool:
    return type(a) is type(b) and a == b


def _pairs(items: Iterable[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in items:
        if k not in out:
            out[k] = v
        elif out[k] is not _CLASH and not _same(out[k], v):
            out[k] = _CLASH
    return out


def loads(text: str) -> Any:
    """저장 기록 JSON 읽기 — 같은 칸이 서로 다른 값으로 두 번 이상 있으면 그 칸 = 충돌(검증 F20).

    충돌 표시는 조건 칸에서는 CONFLICT 가 되고, 후보 칸(순위 · 값 · 날짜 · 코드)에서는 형 검사에 걸려
    '값 없음'이 된다(인용 안 함)."""
    return json.loads(text, object_pairs_hook=_pairs)


def _unique(items: Iterable[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in items:
        if k in out:
            raise ValueError(f"같은 칸이 두 번 저장됨: {k}")
        out[k] = v
    return out


def loads_unique(text: str) -> Any:
    """내 판단 기록 파일 읽기 — 이 도구가 쓴 파일에는 같은 칸이 두 번 나오지 않는다(나오면 못 읽은 파일)."""
    return json.loads(text, object_pairs_hook=_unique)


def has_clash(obj: Any) -> bool:
    """읽은 값 안 어디든 같은 칸 충돌이 있나(후보 칸 — 있으면 그 기록 전체를 못 읽은 기록으로 · 반박 검토 D5)."""
    stack = [obj]
    while stack:
        v = stack.pop()
        if v is _CLASH:
            return True
        if isinstance(v, dict):
            stack.extend(v.values())
        elif isinstance(v, list):
            stack.extend(v)
    return False


def text_ok(obj: Any) -> bool:
    """읽은 값 안의 글(칸 이름 포함)이 모두 UTF-8 로 쓸 수 있나 — JSON 의 짝 없는 대리 문자(\\udXXX)는
    읽히지만 화면 · 저장 글을 만들 때 실패한다(검증 F22 · 그 기록 · 그 파일만 못 읽음)."""
    stack = [obj]
    while stack:
        v = stack.pop()
        if isinstance(v, str):
            try:
                v.encode("utf-8")
            except UnicodeEncodeError:
                return False
        elif isinstance(v, dict):
            stack.extend(v.keys())
            stack.extend(v.values())
        elif isinstance(v, list):
            stack.extend(v)
    return True


def stored_filters(raw: Mapping[str, Any]) -> dict[str, Any]:
    """저장된 제외 조건 — 불리언은 그대로 · 충돌 = CONFLICT · 그 밖 값 = INVALID(반박 검토 D1 · D2)."""
    return {
        str(k): (v if isinstance(v, bool) else CONFLICT if v is _CLASH else INVALID)
        for k, v in raw.items()
    }


def filter_value(filters: Mapping[str, Any], key: str) -> Any:
    """제외 조건 한 칸 = True · False(JSON 불리언만) · MISSING · INVALID · CONFLICT.

    참 · 거짓으로 바꾸지 않는다(검증 F18 — 확인 안 된 조건을 같다고 보지 않음 · 빠진 칸을 '제외 안 함'으로
    가정하지 않음)."""
    if key not in filters:
        return MISSING
    v = filters[key]
    if isinstance(v, bool):
        return v
    return CONFLICT if v is CONFLICT or v is _CLASH else INVALID


def filter_gaps(
    filters: Mapping[str, Any], keys: Iterable[str]
) -> dict[str, list[str]]:
    """지금 조건 칸(keys) 기준으로 확인할 수 없는 칸 — 빠짐 · 형식 오류 · 값 충돌 · 지금 조건에 없는 칸."""
    got = {k: filter_value(filters, k) for k in keys}
    return {
        "missing": [k for k, v in got.items() if v is MISSING],
        "invalid": [k for k, v in got.items() if v is INVALID],
        "conflict": [k for k, v in got.items() if v is CONFLICT],
        "extra": sorted(str(k) for k in filters if k not in got),
    }
