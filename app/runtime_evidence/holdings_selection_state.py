"""POC3-OPS-01A — 보유 브리핑 반복 억제 상태 (저장 · fingerprint · 변화 판정).

OPEN 은 당일 최초 전체 상태를 보내고, MIDDAY·CLOSE 는 **변화분만** 보낸다.
동일 종목·동일 이유·동일 구간은 반복하지 않는다.

설계자 확정 (PLAN §4 · V1.3):
- 비교 identity = `ticker | sorted(reason:state)` — **reason별로** 비교한다.
  `max_severity` 하나만 저장하면 primary 가 이미 최상위일 때 secondary 의
  구간 이동이 삼켜진다.
- **발송 성공 후에만 상태를 확정한다.** 원자 교체는 파일 파손만 막는다.
  미발송 신호가 발송 완료로 기록되는 것을 금지한다.
- 상태를 비교할 수 없으면 **조용히 억제하지 않고** 전체 현재 상태를 보낸다.

이 모듈은 Telegram 을 호출하지 않는다. 저장 시점은 호출자가 정한다.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from app.runtime_evidence.holdings_selection import SelectedTicker

SCHEMA_VERSION = "holdings_selection_state.v1"
KST = timezone(timedelta(hours=9))

# fallback 사유 — 조용한 억제 금지 (PLAN §4.5).
FALLBACK_MISSING = "missing"
FALLBACK_CORRUPT = "corrupt"
FALLBACK_SCHEMA = "schema_mismatch"
FALLBACK_DATE = "date_mismatch"

# 변화 종류.
CHANGE_NEW = "new"
CHANGE_STATE_MOVED = "state_moved"
CHANGE_RESOLVED = "resolved"


def kst_today() -> str:
    return datetime.now(timezone.utc).astimezone(KST).strftime("%Y-%m-%d")


def kst_now_iso() -> str:
    return (
        datetime.now(timezone.utc).astimezone(KST).strftime("%Y-%m-%dT%H:%M:%S+09:00")
    )


@dataclass
class LoadedState:
    """이전 상태. `fallback` 이 있으면 비교하지 않고 전체를 보낸다."""

    entries: dict[str, dict[str, Any]] = field(default_factory=dict)
    kst_date: Optional[str] = None
    last_slot: Optional[str] = None
    fallback: Optional[str] = None

    @property
    def comparable(self) -> bool:
        return self.fallback is None


@dataclass
class ChangeSet:
    """변화 판정 결과."""

    new: list[SelectedTicker] = field(default_factory=list)
    moved: list[tuple[SelectedTicker, dict[str, Any]]] = field(default_factory=list)
    resolved: list[str] = field(default_factory=list)
    full_send: bool = False
    fallback: Optional[str] = None

    @property
    def has_change(self) -> bool:
        return bool(self.full_send or self.new or self.moved or self.resolved)


def load_state(path: Path, *, today_kst: Optional[str] = None) -> LoadedState:
    """이전 상태 로드. 비교 불가 사유는 **삼키지 않고 fallback 으로 남긴다**."""
    today = today_kst or kst_today()
    if not path.exists():
        return LoadedState(fallback=FALLBACK_MISSING)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — 파손 사유를 구분하지 않는다.
        return LoadedState(fallback=FALLBACK_CORRUPT)
    if not isinstance(raw, dict):
        return LoadedState(fallback=FALLBACK_CORRUPT)
    if raw.get("schema_version") != SCHEMA_VERSION:
        return LoadedState(fallback=FALLBACK_SCHEMA)
    if raw.get("kst_date") != today:
        return LoadedState(kst_date=raw.get("kst_date"), fallback=FALLBACK_DATE)
    entries = raw.get("entries")
    if not isinstance(entries, dict):
        return LoadedState(fallback=FALLBACK_CORRUPT)
    return LoadedState(
        entries=entries, kst_date=raw.get("kst_date"), last_slot=raw.get("last_slot")
    )


def _entry_states(entry: dict[str, Any]) -> dict[str, str]:
    reasons = entry.get("reasons")
    if not isinstance(reasons, dict):
        return {}
    out: dict[str, str] = {}
    for reason, payload in reasons.items():
        if isinstance(payload, dict) and isinstance(payload.get("state"), str):
            out[reason] = payload["state"]
    return out


def compute_changes(
    *,
    selected: list[SelectedTicker],
    previous: LoadedState,
    is_first_slot: bool,
) -> ChangeSet:
    """변화 판정.

    `is_first_slot=True` (OPEN) 또는 이전 상태 비교 불가면 **전체 현재 상태**를
    보낸다. 비교 실패를 `변화 없음` 으로 대체하지 않는다 (PLAN §4.5).
    """
    if is_first_slot or not previous.comparable:
        return ChangeSet(full_send=True, fallback=previous.fallback)

    changes = ChangeSet()
    prev_entries = previous.entries
    for item in selected:
        prev = prev_entries.get(item.ticker)
        if prev is None:
            changes.new.append(item)
            continue
        before = _entry_states(prev)
        after = {r: v["state"] for r, v in item.reasons.items()}
        if before != after:
            # reason 추가·제거·구간 이동 전부 여기서 잡힌다.
            changes.moved.append((item, before))

    current_tickers = {i.ticker for i in selected}
    for ticker in prev_entries:
        if ticker not in current_tickers:
            changes.resolved.append(ticker)
    changes.resolved.sort()
    return changes


def build_entries(selected: list[SelectedTicker]) -> dict[str, dict[str, Any]]:
    """저장용 entries. 보조 정보(고점 대비)는 저장하지 않는다."""
    return {
        item.ticker: {
            "reasons": {
                reason: {"state": payload["state"], "value": payload.get("value")}
                for reason, payload in item.reasons.items()
            }
        }
        for item in selected
    }


def save_state(
    path: Path,
    *,
    selected: list[SelectedTicker],
    slot_id: Optional[str],
    today_kst: Optional[str] = None,
    created_at_kst: Optional[str] = None,
) -> None:
    """상태 원자 교체.

    **호출 시점 계약 (PLAN §4.6)**: 이 함수는 **Telegram 전체 발송 성공 이후에만**
    호출한다. 부분·전체 실패 시 호출하지 않아 이전 상태가 유지되고, 다음 슬롯에서
    같은 변화를 다시 시도한다. 미발송 신호가 발송 완료로 기록되면 안 된다.
    """
    now = kst_now_iso()
    payload = {
        "schema_version": SCHEMA_VERSION,
        "kst_date": today_kst or kst_today(),
        "created_at_kst": created_at_kst or now,
        "updated_at_kst": now,
        "last_slot": slot_id,
        "entries": build_entries(selected),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)
