"""POC3-OPS-02A — 위험 알림 상태·변화 판정 (`worst_state` 기반).

설계자 확정 (PLAN V1.2 §4.3) — **신규·악화만 발송**한다.

| 상황 | 발송 |
|---|---|
| 처음 `D5_7` 이상 진입 | 발송 |
| `D5_7` → `D7_10` → `D10_PLUS` | 재발송 |
| 한 번에 더 나쁜 구간으로 진입 | 해당 구간으로 발송 |
| 같은 구간 유지 | 억제 |
| 완화·해소 | **미발송** |
| 완화 후 같은 날 기존 구간 재진입 | **미발송** |
| 같은 날 도달한 **최악 구간보다 더 악화**된 경우에만 | 추가 발송 |
| 다음 거래일 시작 | **상태 초기화** |
| 나중 실행에서 새 종목이 처음 진입 | 그 종목은 신규로 발송 |

**OPS-01A 와 다른 점 3가지**

1. 완화·해소를 알리지 않는다 (01A 는 구간 이동을 양방향 발송)
2. **완화 후 같은 날 재진입도 억제**한다 — 그래서 "현재 구간" 이 아니라
   **그날 도달한 최악 구간(`worst_state`)** 을 기록해야 한다
3. **거래일 경계에서 상태를 버린다** (01A 는 슬롯 기반 누적)

`worst_state` 는 **완화해도 낮추지 않는다.** 낮추면 같은 날 재진입이 신규로
잡혀 재발송된다.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from app.runtime_evidence.holdings_risk import RiskTicker, severity

SCHEMA_VERSION = "holdings_risk_state.v1"


@dataclass
class LoadedRiskState:
    """이전 상태. `fallback` 이 있으면 비교하지 않고 **전부 신규**로 본다."""

    # ticker -> {"worst_state": str}
    entries: dict[str, dict[str, Any]] = field(default_factory=dict)
    kst_date: Optional[str] = None
    fallback: Optional[str] = None

    @property
    def comparable(self) -> bool:
        return self.fallback is None


@dataclass
class RiskChangeSet:
    """이번 실행에서 **발송할** 항목."""

    new: list[RiskTicker] = field(default_factory=list)
    worsened: list[tuple[RiskTicker, str]] = field(
        default_factory=list
    )  # (item, 이전 worst)
    suppressed: list[str] = field(default_factory=list)  # ticker
    fallback: Optional[str] = None

    @property
    def has_send(self) -> bool:
        return bool(self.new or self.worsened)

    @property
    def send_count(self) -> int:
        return len(self.new) + len(self.worsened)


def load_risk_state(path: Path, *, today_kst: Optional[str] = None) -> LoadedRiskState:
    """상태 로드. **거래일이 다르면 버린다**(초기화).

    fallback 종류:
      - `missing`         파일 없음
      - `corrupt`         JSON 파싱 실패
      - `schema_mismatch` schema_version 불일치
      - `date_reset`      **저장된 날짜 != 실행일** → 새 거래일이므로 초기화

    `date_reset` 은 오류가 아니라 **정상 동작**이다. 다만 `comparable=False` 로
    두어 그날 첫 실행이 전부 신규가 되게 한다.
    """
    if not path.exists():
        return LoadedRiskState(fallback="missing")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return LoadedRiskState(fallback="corrupt")
    if not isinstance(raw, dict) or raw.get("schema_version") != SCHEMA_VERSION:
        return LoadedRiskState(fallback="schema_mismatch")

    stored_date = raw.get("kst_date")
    entries = raw.get("entries")
    if not isinstance(entries, dict):
        entries = {}
    if today_kst and stored_date != today_kst:
        # 새 거래일 — 전일 상태를 이월하지 않는다.
        return LoadedRiskState(kst_date=stored_date, fallback="date_reset")
    return LoadedRiskState(entries=entries, kst_date=stored_date, fallback=None)


def _worst_of(entry: Any) -> Optional[str]:
    if isinstance(entry, dict):
        w = entry.get("worst_state")
        if isinstance(w, str) and w:
            return w
    return None


def compute_risk_changes(
    *, selected: list[RiskTicker], previous: LoadedRiskState
) -> RiskChangeSet:
    """발송 대상 판정. **신규·악화만** 담는다.

    비교 불가(`fallback`)면 선정된 것을 **전부 신규**로 본다 — 조용한 억제로
    대체하지 않는다. 새 거래일(`date_reset`)이 여기에 해당한다.
    """
    changes = RiskChangeSet(fallback=previous.fallback)
    if not previous.comparable:
        changes.new = list(selected)
        return changes

    for item in selected:
        prev_worst = _worst_of(previous.entries.get(item.ticker))
        if prev_worst is None:
            changes.new.append(item)
        elif severity(item.state) > severity(prev_worst):
            changes.worsened.append((item, prev_worst))
        else:
            # 같은 구간 유지 · 완화 후 재진입 — 둘 다 억제.
            changes.suppressed.append(item.ticker)
    return changes


def merge_worst(
    *, selected: list[RiskTicker], previous: LoadedRiskState
) -> dict[str, dict[str, Any]]:
    """저장할 entries. **기존 worst 를 낮추지 않는다.**

    선정에서 빠진 종목(완화·해소)의 기존 기록도 **유지**한다 — 지워버리면 같은
    날 재진입이 신규로 잡혀 재발송된다.
    """
    out: dict[str, dict[str, Any]] = {}
    if previous.comparable:
        for t, e in previous.entries.items():
            w = _worst_of(e)
            if w:
                out[t] = {"worst_state": w}
    for item in selected:
        cur = _worst_of(out.get(item.ticker))
        if cur is None or severity(item.state) > severity(cur):
            out[item.ticker] = {"worst_state": item.state}
    return out


def save_risk_state(
    path: Path,
    *,
    entries: dict[str, dict[str, Any]],
    today_kst: str,
    runtime_kst: Optional[str] = None,
) -> None:
    """원자적 저장(`.tmp` → `os.replace`).

    **러너가 Telegram 전체 발송 성공을 확인한 뒤에만** 호출한다. 미발송 신호가
    발송 완료로 기록되면 그 악화는 영영 사라진다(OPS-01A 와 같은 계약).
    """
    payload = {
        "schema_version": SCHEMA_VERSION,
        "kst_date": today_kst,
        "updated_at_kst": runtime_kst,
        "entries": entries,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=1)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
