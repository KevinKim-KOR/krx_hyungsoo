"""POC3-02C-OPS-02 — 장중 점검 회차 집계 (설계자 §8 · §14-2).

15:40 보유 브리핑 말미의 **한 줄**을 만들기 위한 집계다.

```text
장중 점검 7회 · 알림 2건 · 중복 억제 3건 · 신호 없음 2건
```

## 왜 발송 상태와 별개 파일인가

`sector_signal_state` 는 **발송 판단용**이다. 그 안에서 `last_sent_at`·
`sent_today` 는 **전송 성공 뒤에만** 쓴다 — 미발송 신호가 발송 완료로 기록되면
안 되기 때문이다(설계 §9·§15-2). 관측 4종은 매 회차 쓴다.

회차 집계는 목적이 다르다. **보내지 않은 회차도 세야 한다** — "신호 없음 2건"
을 세려면 발송이 없었던 회차까지 기록해야 한다. 집계를 발송 상태 파일에 섞으면
발송 판단이 집계 때문에 흔들리므로 파일을 나눈다.

```text
sector_signal_state_latest.json   발송 판단 (last_sent_at·sent_today 는 성공 시에만)
intraday_checkup_tally_latest.json  매 회차 기록 (집계 전용 · 발송 판단에 쓰지 않는다)
```

집계 파일이 깨져도 **발송 판단은 영향받지 않는다.** 요약만 `확인 불가` 가 된다.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

SCHEMA_VERSION = "intraday_checkup_tally.v1"

OUTCOME_SENT = "sent"
OUTCOME_SUPPRESSED = "suppressed"
OUTCOME_NO_SIGNAL = "no_signal"
OUTCOME_FAILED = "failed"

VALID_OUTCOMES = (OUTCOME_SENT, OUTCOME_SUPPRESSED, OUTCOME_NO_SIGNAL, OUTCOME_FAILED)


@dataclass
class Tally:
    checks: int = 0
    sent: int = 0
    suppressed: int = 0
    no_signal: int = 0
    failed: int = 0
    unknown: bool = False


def load_tally(path: Path, *, today_kst: Optional[str] = None) -> Tally:
    """집계 읽기. 없거나 깨졌으면 `unknown=True`.

    **`0` 으로 위장하지 않는다**(설계 §8) — 집계 불가와 "0건" 은 다르다.
    """
    if not path.exists():
        return Tally(unknown=True)
    try:
        body = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return Tally(unknown=True)
    if not isinstance(body, dict) or body.get("schema_version") != SCHEMA_VERSION:
        return Tally(unknown=True)
    if today_kst and str(body.get("date_kst") or "")[:10] != str(today_kst)[:10]:
        # 다른 날 집계 — 오늘 요약에 쓰면 안 된다.
        return Tally(unknown=True)
    ticks = body.get("ticks")
    if not isinstance(ticks, list):
        return Tally(unknown=True)
    t = Tally(checks=len(ticks))
    for item in ticks:
        o = (item or {}).get("outcome") if isinstance(item, dict) else None
        if o == OUTCOME_SENT:
            t.sent += 1
        elif o == OUTCOME_SUPPRESSED:
            t.suppressed += 1
        elif o == OUTCOME_NO_SIGNAL:
            t.no_signal += 1
        elif o == OUTCOME_FAILED:
            t.failed += 1
    return t


def _write(path: Path, body: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".tally.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(body, f, ensure_ascii=False, indent=1)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _read_raw(path: Path, today_kst: str) -> dict[str, Any]:
    if path.exists():
        try:
            body = json.loads(path.read_text(encoding="utf-8"))
            if (
                isinstance(body, dict)
                and body.get("schema_version") == SCHEMA_VERSION
                and str(body.get("date_kst") or "")[:10] == str(today_kst)[:10]
                and isinstance(body.get("ticks"), list)
            ):
                return body
        except (OSError, ValueError):
            pass
    return {
        "schema_version": SCHEMA_VERSION,
        "date_kst": str(today_kst)[:10],
        "ticks": [],
    }


def record_tick(
    path: Path, *, today_kst: str, outcome: str, at_kst: Optional[str] = None
) -> None:
    """한 회차 기록. **보내지 않은 회차도 센다.**

    집계 실패가 발송을 막으면 안 되므로 호출자가 예외를 삼킨다.
    """
    if outcome not in VALID_OUTCOMES:
        outcome = OUTCOME_NO_SIGNAL
    body = _read_raw(path, today_kst)
    body["ticks"].append({"outcome": outcome, "at": at_kst})
    _write(path, body)


def mark_last_tick_sent(path: Path, *, today_kst: str) -> None:
    """마지막 회차를 `sent` 로 올린다. **전송 성공 뒤에만** 호출한다.

    조립 시점에는 전송 성공 여부를 모르므로 그때는 `suppressed`/`no_signal` 로
    적어 두고, 성공하면 여기서 정정한다.
    """
    body = _read_raw(path, today_kst)
    if body["ticks"]:
        body["ticks"][-1]["outcome"] = OUTCOME_SENT
        _write(path, body)


def render_summary_line(tally: Tally) -> str:
    """15:40 말미 한 줄. 집계 불가는 `확인 불가`."""
    from app.runtime_evidence.intraday_alert_render import render_checkup_summary

    return render_checkup_summary(
        checks=tally.checks,
        sent=tally.sent,
        suppressed=tally.suppressed,
        no_signal=tally.no_signal,
        failed=tally.failed,
        unknown=tally.unknown,
    )


__all__ = [
    "OUTCOME_FAILED",
    "OUTCOME_NO_SIGNAL",
    "OUTCOME_SENT",
    "OUTCOME_SUPPRESSED",
    "SCHEMA_VERSION",
    "VALID_OUTCOMES",
    "Tally",
    "load_tally",
    "mark_last_tick_sent",
    "record_tick",
    "render_summary_line",
]
