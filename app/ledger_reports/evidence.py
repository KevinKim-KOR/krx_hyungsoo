"""POC5-04 — 개발자가 제공하는 읽기 전용 근거 파일 해석(R0).

설계 개정 1 §2 · §3 · PLAN §1-2 · §1-3(판정 정정 반영). 이 모듈은 파일 내용만 읽는다(SSH · 쓰기 0).

```text
대조 근거   01B 대조 CLI 출력 그대로 + 개발자가 같은 SSH 명령에서 붙인 첫 줄 `captured_at=<ISO>`
            NOT_CHECKED 근거 없음 · 건수 줄 없음 · floor · captured_at 없음 · floor ≠ 원장 first_active_at
                        (시작 · 기간 정보를 확인할 수 없음 — 다른 원장의 근거로 판정하지 않는다)
            ERRORS      위를 통과하고 누락 · 미종료 · 원장에만 중 하나라도 > 0(status 와 무관 · 건수 · ID 보존)
            NOT_CHECKED 오류 0 인데 captured_at < 종료일 15:45 KST(기간이 종료일을 덮지 못함)
            OK          그 밖(종료일을 덮는 더 넓은 누적 구간 포함)
운영 근거   `key=value` 줄 — price_batch_price_date(YYYY-MM-DD) · price_batch_status ·
            price_batch_completed_at ·
            ops_error_count(개발자가 확인한 배치 · 원장 · PUSH 오류 건수 · 필수 · 0 이상 정수)
            (+ 그 밖의 줄은 메모 · 40줄 · 줄당 200자 · 비밀값 단어가 든 줄은 통째로 가리고 긴 토큰은 [가림])
            배치 확인 = 적재일 ≥ 종료일 ∧ 상태 success/ok ∧ PC 마지막 성공 동기화 > 배치 완료 시각
```
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any, Optional

from app.ledger_reports.dates import at_kst, parse_kst

RECONCILE_KINDS = ("ok", "missing_in_ledger", "started_gap", "ledger_only")
ERROR_KINDS = ("missing_in_ledger", "started_gap", "ledger_only")
COVER_HHMM = "15:45"  # 종료일 마지막 예정 실행(15:40) 뒤
BATCH_OK = ("success", "ok")
NOTE_LINES = 40
NOTE_WIDTH = 200

_SECRET_WORDS = re.compile(
    r"token|secret|password|passwd|api[_-]?key|chat[_-]?id|authorization|bearer", re.I
)
_LONG_TOKEN = re.compile(r"[A-Za-z0-9_\-:]{32,}")
OPS_KEYS = (
    "price_batch_price_date",
    "price_batch_status",
    "price_batch_completed_at",
    "ops_error_count",
    "captured_at",
)

_COUNTS = re.compile(
    r"^ok=(\d+) missing_in_ledger=(\d+) started_gap=(\d+) ledger_only=(\d+)$"
)


def _kv(line: str) -> tuple[str, str]:
    key, _, value = line.partition("=")
    return key.strip(), value.strip()


def parse_reconcile(
    text: Optional[str], *, first_active_at: Optional[str], end: str
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "state": "NOT_CHECKED",
        "reason": None,
        "captured_at": None,
        "floor": None,
        "status": None,
        "error_class": None,
        "counts": None,
        "ids": {},
        "period": None,
        "includes_after_end": None,
    }
    if text is None:
        out["reason"] = "대조 근거 없음"
        return out
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("captured_at="):
            out["captured_at"] = _kv(line)[1]
        elif line.startswith("status="):
            for part in line.split():
                k, v = _kv(part)
                if k == "status":
                    out["status"] = v
                elif k == "floor":
                    out["floor"] = v
                elif k == "error_class":
                    out["error_class"] = v
        elif _COUNTS.match(line):
            m = _COUNTS.match(line)
            assert m is not None
            out["counts"] = dict(zip(RECONCILE_KINDS, (int(g) for g in m.groups())))
        elif "_ids=" in line:
            k, v = _kv(line)
            out["ids"][k[: -len("_ids")]] = [x for x in v.split(",") if x]
    captured = parse_kst(out["captured_at"])
    floor = parse_kst(out["floor"])
    start = parse_kst(first_active_at)
    out["period"] = [out["floor"], out["captured_at"]]
    cover = at_kst(end, COVER_HHMM)
    if captured is not None:
        out["includes_after_end"] = captured > cover
    counts = out["counts"]
    if counts is None:
        out["reason"] = "분류 건수 줄을 읽을 수 없음"
    elif captured is None or floor is None:
        out["reason"] = "captured_at · floor 없음(시작 · 기간을 확인할 수 없음)"
    elif start is None or floor != start:
        out["reason"] = "floor 가 원장 first_active_at 과 다름(다른 원장 · 시작 불일치)"
    elif any(counts[k] > 0 for k in ERROR_KINDS):
        out["state"] = "ERRORS"  # status 와 무관 — 검출된 오류는 버리지 않는다
        out["reason"] = "대조가 누락 · 미종료 · 원장에만 있는 실행을 보고"
        if out["includes_after_end"]:
            out[
                "reason"
            ] += "(누적 근거 — 종료일 뒤 실행 포함 · 종료일 이전 정확한 건수 아님)"
    elif captured < cover:
        out["reason"] = (
            f"대조 시각이 종료일 {COVER_HHMM} 보다 이름(기간이 종료일을 덮지 못함)"
        )
    else:
        out["state"] = "OK"
    return out


def safe_note(line: str) -> str:
    """운영 메모 1줄 — 비밀값 단어가 들면 통째로 가리고 긴 토큰은 [가림]."""
    if _SECRET_WORDS.search(line):
        return "[가림 — 비밀값 단어가 든 줄]"
    return _LONG_TOKEN.sub("[가림]", line)[:NOTE_WIDTH]


def _iso_date(text: Optional[str]) -> Optional[str]:
    try:
        d = date.fromisoformat(text or "")
    except ValueError:
        return None
    return d.isoformat() if d.isoformat() == text else None


def parse_ops(
    text: Optional[str], *, end: str, last_sync_success: Optional[str]
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "provided": text is not None,
        "values": {},
        "notes": [],
        "batch_confirmed": False,
        "reason": None,
        "error_count": None,
        "error_count_reason": None,
    }
    if text is None:
        out["reason"] = "운영 근거(배치 완료) 없음"
        out["error_count_reason"] = "운영 근거 없음"
        return out
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        k, v = _kv(line)
        if "=" in line and k in OPS_KEYS:
            out["values"][k] = v
        elif len(out["notes"]) < NOTE_LINES:
            out["notes"].append(safe_note(line))
    vals = out["values"]
    raw_count = vals.get("ops_error_count")
    if raw_count is None:
        out["error_count_reason"] = "ops_error_count 없음"
    elif not raw_count.isdigit():
        out["error_count_reason"] = "ops_error_count 가 0 이상 정수가 아님"
    else:
        out["error_count"] = int(raw_count)
    loaded = _iso_date(vals.get("price_batch_price_date"))
    status = (vals.get("price_batch_status") or "").lower()
    done = parse_kst(vals.get("price_batch_completed_at"))
    synced = parse_kst(last_sync_success)
    if vals.get("price_batch_price_date") and loaded is None:
        out["reason"] = "price_batch_price_date 형식이 YYYY-MM-DD 가 아님"
    elif not loaded or loaded < end:
        out["reason"] = "종료일 종가를 적재한 배치 근거 없음"
    elif status not in BATCH_OK:
        out["reason"] = "배치 상태가 success/ok 가 아님"
    elif done is None:
        out["reason"] = "배치 완료 시각 없음"
    elif synced is None or synced <= done:
        out["reason"] = "PC 사본이 배치 완료 뒤에 동기화되지 않음"
    else:
        out["batch_confirmed"] = True
    return out
