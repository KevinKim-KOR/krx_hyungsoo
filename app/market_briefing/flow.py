"""POC3-OPS-02B-2 — 조립 흐름 · fingerprint · 반복 억제 · 상태.

runner 가 **1회만** 호출하는 진입점이다. 러너에 본문 책임을 추가하지 않기 위해
조립·정합성·억제를 전부 여기서 끝낸다(설계 §7).

## 판정하지 않는다

이 모듈은 **조립만** 하고 `fail`·`skip` 을 **돌려주기만** 한다. 실제 결정은
러너가 **flag guard 뒤(§6-c)** 에서 한다. 앞에서 끊으면 `push_kind_disabled` 를
`non_trading_day` 가 가로챈다(OPS-01A 에서 실제로 겪었다).

## 외부 조회 0건

08:00 runner 는 KRX API 를 **다시 호출하지 않는다**(설계자 §M-2). 07:20 이 남긴
정합성 결과와 신규 무조정 가격 계열만 읽는다.

## fingerprint

```text
state_fingerprint = "{outlook_state}#{index_leadership_state}"
```

**근거 숫자를 넣지 않는다** — 매일 흔들려 억제가 무력화된다(OPS-02A 확정 원칙).
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Sequence

from app.market_briefing import evidence as ev
from app.market_briefing import krx_store, meta_gate, render
from app.market_briefing.calendar import CalendarVerdict, check_trading_day

SCHEMA_VERSION = "market_briefing_state.v1"
STATE_NAME = "market_briefing_state_latest.json"

REASON_NO_PUBLISHABLE = "no_publishable_content"
REASON_ALL_STALE = "all_data_stale"
REASON_NO_CHANGE = "no_change"


@dataclass
class BriefingOutcome:
    """러너가 §6-c 에서 쓰는 조립 결과."""

    message_text: str = ""
    fingerprint: str = ""
    previous_fingerprint: Optional[str] = None
    skip_reason: Optional[str] = None
    fail: Optional[tuple[str, str, str]] = None
    calendar: Optional[CalendarVerdict] = None
    diagnostics: dict[str, Any] = field(default_factory=dict)

    @property
    def should_send(self) -> bool:
        return (
            bool(self.message_text) and self.skip_reason is None and self.fail is None
        )


# ── 상태 저장 ───────────────────────────────────────────────────────────────


def load_state(path: Path) -> Optional[dict[str, Any]]:
    """직전 발송 상태. **일 단위 비교**이므로 거래일이 바뀌어도 유지한다."""
    if not path.exists():
        return None
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(d, dict) or d.get("schema_version") != SCHEMA_VERSION:
        return None
    return d


def save_state(
    path: Path, *, fingerprint: str, sent_date_kst: str, runtime_kst: Optional[str]
) -> None:
    """원자적 저장. **Telegram 전체 성공 뒤에만** 호출한다."""
    payload = {
        "schema_version": SCHEMA_VERSION,
        "state_fingerprint": fingerprint,
        "sent_date_kst": sent_date_kst,
        "updated_at_kst": runtime_kst,
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


# ── 조립 ────────────────────────────────────────────────────────────────────


def _index_block(
    consistency: Optional[meta_gate.ConsistencyResult],
    *,
    csv_rows: Sequence[dict[str, str]],
    db_path: Optional[Path],
) -> ev.IndexLeadership:
    """기초지수 블록. 정합성이 통과해야만 가격을 쓴다.

    설계자 §M-3 — 정합성 실패 상태에서는 **정상 수집된 가격도 후보 계산에 쓰지
    않는다.**
    """
    if consistency is None:
        return ev.IndexLeadership(
            status=meta_gate.STATUS_API_FETCH_FAILED,
            diagnostics={"reason": "no_0720_result"},
        )
    if not consistency.usable:
        return ev.IndexLeadership(
            status=consistency.status, diagnostics=consistency.to_dict()
        )

    window = krx_store.resolve_window(db_path=db_path)
    if window is None:
        return ev.IndexLeadership(
            status="stale",
            diagnostics={
                "reason": "insufficient_trading_days",
                "required": krx_store.REQUIRED_TRADING_DAYS,
                "stored": len(krx_store.stored_trading_days(db_path=db_path)),
            },
        )

    closes = krx_store.closes_on(list(window.dates), db_path=db_path)
    matched = meta_gate.matched_meta_rows(
        csv_rows, {t: n for t, n in _api_names_from(consistency, csv_rows).items()}
    )
    result = ev.compute_index_leadership(
        meta_rows=matched,
        closes=closes,
        latest=window.latest,
        d5=window.d5,
        d20=window.d20,
    )
    result.diagnostics.update(consistency.to_dict())
    if not result.candidates:
        result.status = render.STATUS_NO_CANDIDATE_NORMAL
    return result


def _api_names_from(
    consistency: meta_gate.ConsistencyResult, csv_rows: Sequence[dict[str, str]]
) -> dict[str, str]:
    """정합성이 `ok` 이면 CSV 이름이 곧 API 이름이다(완전일치가 확인됐다)."""
    excluded = set(consistency.api_only) | set(consistency.name_mismatch)
    return {
        (r.get("단축코드") or "").strip(): (r.get("기초지수명") or "").strip()
        for r in csv_rows
        if (r.get("단축코드") or "").strip()
        and (r.get("단축코드") or "").strip() not in excluded
    }


def assemble_market_briefing(
    *,
    today_kst: str,
    runtime_kst: Optional[str],
    state_path: Path,
    consistency_path: Path,
    official_csv_path: Path,
    sp500_return_pct: Optional[float],
    sp500_asof: Optional[str],
    sp500_fresh: bool,
    support: Sequence[ev.SupportIndex] = (),
    calendar_dir: Optional[Path] = None,
    db_path: Optional[Path] = None,
) -> BriefingOutcome:
    """러너 §3-e 전체. **판정하지 않고 조립만** 한다."""
    out = BriefingOutcome()

    # ① 거래일 Gate — 결과만 담고 결정은 러너 §6-c 가 한다.
    verdict = check_trading_day(today_kst, directory=calendar_dir)
    out.calendar = verdict
    out.diagnostics["calendar"] = verdict.to_dict()
    if not verdict.ok:
        out.skip_reason = verdict.reason
        return out

    # ② 07:20 결과 소비 — 외부 조회 0건.
    consistency = meta_gate.load_consistency(consistency_path)
    out.diagnostics["meta_consistency"] = (
        consistency.to_dict() if consistency else {"status": "missing"}
    )

    try:
        csv_rows = meta_gate.load_official_csv(official_csv_path)
    except (OSError, UnicodeDecodeError) as e:  # noqa: BLE001
        csv_rows = []
        out.diagnostics["official_csv_error"] = f"{type(e).__name__}"

    # ③ evidence
    outlook = ev.decide_outlook(
        sp500_return_pct=sp500_return_pct,
        sp500_asof=sp500_asof,
        sp500_fresh=sp500_fresh,
    )
    index = _index_block(consistency, csv_rows=csv_rows, db_path=db_path)
    out.diagnostics["outlook_state"] = outlook.state
    out.diagnostics["index_status"] = index.status
    out.diagnostics["index_candidates"] = [c.identifier for c in index.candidates]
    out.diagnostics["index_diagnostics"] = index.diagnostics

    if not outlook.usable and not index.candidates:
        out.skip_reason = (
            REASON_ALL_STALE
            if index.status in ("stale", meta_gate.STATUS_API_FETCH_FAILED)
            else REASON_NO_PUBLISHABLE
        )
        return out

    # ④ 본문
    out.message_text = render.render_market_briefing(
        outlook=outlook,
        index_status=index.status,
        candidates=index.candidates,
        support=support,
        us_asof=sp500_asof if sp500_fresh else None,
        kr_asof=index.price_asof,
    )
    if not out.message_text:
        out.skip_reason = REASON_NO_PUBLISHABLE
        return out

    # ⑤ fingerprint — **본문이 만들어진 뒤에만** 비교한다 (설계자 §6).
    out.fingerprint = f"{outlook.fingerprint_state}#{index.fingerprint_state}"
    prev = load_state(state_path)
    out.previous_fingerprint = (prev or {}).get("state_fingerprint")
    out.diagnostics["state_fingerprint"] = out.fingerprint
    out.diagnostics["previous_fingerprint"] = out.previous_fingerprint
    if out.previous_fingerprint == out.fingerprint:
        out.skip_reason = REASON_NO_CHANGE
    return out


__all__ = [
    "REASON_ALL_STALE",
    "REASON_NO_CHANGE",
    "REASON_NO_PUBLISHABLE",
    "SCHEMA_VERSION",
    "STATE_NAME",
    "BriefingOutcome",
    "assemble_market_briefing",
    "load_state",
    "save_state",
]
