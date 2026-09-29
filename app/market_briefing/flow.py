"""POC3-OPS-02B-2 — 조립 흐름 · fingerprint 기록 · 상태.

runner 가 **1회만** 호출하는 진입점이다. 러너에 본문 책임을 추가하지 않기 위해
조립·정합성·skip 사유를 전부 여기서 끝낸다(설계 §7). fingerprint 는 발송을 막지
않는다 — 2026-09-18 `02C-OPS-01` 배포부터 `content_unchanged` 기록만 한다(⑤).

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

**근거 숫자를 넣지 않는다** — 매일 흔들려 `content_unchanged` 비교가 뜻을 잃는다
(OPS-02A 확정 원칙 · 2026-09-18 운영분까지는 `no_change` 억제의 기준이었다).

## POC3-02D-OPS-01 C1

- 공식 CSV 는 07:20 과 **같은 resolver**(`official_csv`)로 고른다(Q2).
- 저장된 07:20 판정은 **오늘 창**의 것일 때만 쓴다. 아니면 기초지수 구역만
  `META_GATE_STALE` 로 닫는다(R2 Q27).
- `refresh_due` 인 주기에는 **어차피 나가는 본문** 끝에 CSV 갱신 안내 1줄을 붙인다.
  주기마다 한 번이며, 발송이 전부 성공한 뒤에만 상태에 소진을 남긴다(R2 Q24).
  fingerprint · 발송 여부는 바꾸지 않는다.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Sequence

from app import trading_day_lag
from app.market_briefing import evidence as ev
from app.market_briefing import krx_store, meta_gate, official_csv, render
from app.market_benchmark_freshness import MAX_STALE_TRADING_DAYS
from app.market_briefing.calendar import CalendarVerdict, check_trading_day

SCHEMA_VERSION = "market_briefing_state.v1"
STATE_NAME = "market_briefing_state_latest.json"
# R2 Q24 — 안내를 이미 보낸 `refresh_due` 주기. 없던 옛 상태 파일은 "보낸 적 없음".
STATE_NOTICE_KEY = "refresh_notice_cycle_id"

REASON_NO_PUBLISHABLE = "no_publishable_content"
REASON_ALL_STALE = "all_data_stale"
# 정기 PUSH 에서는 더 이상 발송을 막지 않는다(POC3-02B-OPS-03). 진단·이력
# 호환을 위해 상수는 남긴다.
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
    # 발송이 전부 성공하면 상태에 남길 "안내한 주기" (R2 Q24). 오늘 안내를 붙였으면
    # 그 주기, 아니면 직전 상태의 값을 그대로 잇는다.
    refresh_notice_cycle_id: Optional[str] = None

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
    path: Path,
    *,
    fingerprint: str,
    sent_date_kst: str,
    runtime_kst: Optional[str],
    refresh_notice_cycle_id: Optional[str] = None,
) -> None:
    """원자적 저장. **Telegram 전체 성공 뒤에만** 호출한다."""
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "state_fingerprint": fingerprint,
        "sent_date_kst": sent_date_kst,
        "updated_at_kst": runtime_kst,
    }
    if refresh_notice_cycle_id is not None:
        payload[STATE_NOTICE_KEY] = refresh_notice_cycle_id
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


# 거래일-lag 축은 공용 모듈로 옮겼다(POC3-02D-OPS-01 C7 · 설계자 Q17) — KOSPI
# 적재 감지(`refresh_kospi_benchmark`)가 **같은 축**을 쓴다. 옛 이름은 그대로
# 묶어 둔다: `_index_block` 이 이 모듈 전역에서 찾으므로 역검증 스크립트
# (`scripts/ops02b2/reverse_verify_guards.py` ②)의 monkeypatch 가 그대로 통한다.
_weekday_axis_before = trading_day_lag.weekday_axis_before
_window_lag_trading_days = trading_day_lag.window_lag_trading_days


def _verdict_stale(
    consistency: meta_gate.ConsistencyResult, *, db_path: Optional[Path]
) -> Optional[dict[str, Any]]:
    """R2 Q27 — 저장된 판정이 오늘 창의 것이 아니면 진단 dict, 같으면 `None`.

    판정을 다시 계산하지 않는다. 오늘 창 = 저장 계열의 최신일 · d20
    (`krx_store.resolve_window` · 21일 미만이면 d20 없음).
    """
    window = krx_store.resolve_window(db_path=db_path)
    if window is not None:
        latest, d20 = window.latest, window.d20
    else:
        days = krx_store.stored_trading_days(db_path=db_path)
        latest, d20 = (days[-1] if days else None), None
    reason = meta_gate.verdict_stale_reason(consistency, latest=latest, d20=d20)
    if reason is None:
        return None
    return {
        "reason": reason,
        "evaluated_api_basis_date": consistency.evaluated_api_basis_date,
        "evaluated_window_d20_date": consistency.evaluated_window_d20_date,
        "evaluated_at_kst": consistency.evaluated_at_kst,
        "current_latest": latest,
        "current_d20": d20,
    }


def _index_block(
    consistency: Optional[meta_gate.ConsistencyResult],
    *,
    csv_rows: Sequence[dict[str, str]],
    db_path: Optional[Path],
    today_kst: str,
    calendar_dir: Optional[Path] = None,
    csv_unavailable: Optional[str] = None,
) -> ev.IndexLeadership:
    """기초지수 블록. 정합성이 통과해야만 가격을 쓴다.

    설계자 §M-3 — 정합성 실패 상태에서는 **정상 수집된 가격도 후보 계산에 쓰지
    않는다.**

    `csv_unavailable` — 08:00 resolver 가 유효 파일을 하나도 못 찾았을 때의 오류.
    CSV 행 없이 후보를 계산하면 "정상 0개" 로 조용히 사라지므로 닫는다(R2 Q25).
    """
    if consistency is None:
        return ev.IndexLeadership(
            status=meta_gate.STATUS_API_FETCH_FAILED,
            diagnostics={"reason": "no_0720_result"},
        )
    stale = _verdict_stale(consistency, db_path=db_path)
    if stale is not None:
        # `CSV_REFRESH_REQUIRED` 로 표시하지 않는다 — 불필요한 CSV 요청을 막는다.
        return ev.IndexLeadership(
            status=meta_gate.STATUS_META_GATE_STALE, diagnostics=stale
        )
    if csv_unavailable is not None:
        return ev.IndexLeadership(
            status=meta_gate.STATUS_CSV_REFRESH_REQUIRED,
            diagnostics={
                "reason": "official_csv_unavailable",
                "error": csv_unavailable,
            },
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

    # 최신성 Gate — 21일이 모였다는 것과 **그 21일이 최근이라는 것**은 다르다.
    # 이 검사가 없으면 적재가 멈춘 뒤에도 18일 지난 종가로 "오늘 볼 기초지수" 를
    # 만들어 보낸다(사용자 지적 2026-09-13 · 실측 재현). benchmark 와 같은 계약
    # (`MAX_STALE_TRADING_DAYS`)을 재사용한다 — 새 임계를 만들지 않는다.
    lag = _window_lag_trading_days(
        window.latest, today_kst=today_kst, calendar_dir=calendar_dir
    )
    if lag is None or lag > MAX_STALE_TRADING_DAYS:
        # `price_asof` 를 담지 않는다 — 쓰지 않은 기준일을 본문 `기준` 줄에
        # 적으면 "기준일이 다른 값을 하나의 기준일로 표시" 금지(설계 §3.4)를
        # 위반한다. 지난 날짜는 진단에만 남긴다.
        return ev.IndexLeadership(
            status="stale",
            diagnostics={
                "reason": "window_not_fresh" if lag is not None else "lag_unknown",
                "latest_stored": window.latest,
                "lag_trading_days": lag,
                "max_stale_trading_days": MAX_STALE_TRADING_DAYS,
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


def _refresh_notice_cycle(
    consistency: Optional[meta_gate.ConsistencyResult], index_status: str
) -> Optional[str]:
    """R2 Q24 — 안내 대상 주기. 오늘 창의 판정이 `refresh_due` 일 때만."""
    if consistency is None or index_status == meta_gate.STATUS_META_GATE_STALE:
        return None
    if not consistency.refresh_due:
        return None
    return consistency.refresh_due_cycle_id or None


def assemble_market_briefing(
    *,
    today_kst: str,
    runtime_kst: Optional[str],
    state_path: Path,
    consistency_path: Path,
    sp500_return_pct: Optional[float],
    sp500_asof: Optional[str],
    sp500_fresh: bool,
    official_csv_path: Optional[Path] = None,
    meta_dir: Optional[Path] = None,
    support: Sequence[ev.SupportIndex] = (),
    calendar_dir: Optional[Path] = None,
    db_path: Optional[Path] = None,
    logger: Any = None,
) -> BriefingOutcome:
    """러너 §3-e 전체. **판정하지 않고 조립만** 한다.

    공식 CSV — 운영은 `meta_dir` 을 넘겨 07:20 과 같은 resolver 로 고른다.
    `official_csv_path` 는 파일을 직접 지정하는 옛 호출(합성 fixture · 고정 경로
    도구)용이다. 둘 중 하나만 넘긴다.
    """
    if (meta_dir is None) == (official_csv_path is None):
        raise TypeError("meta_dir 과 official_csv_path 중 하나만 넘긴다")
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

    csv_unavailable: Optional[str] = None
    if meta_dir is not None:
        selection = official_csv.resolve_official_csv(meta_dir, logger=logger)
        out.diagnostics["official_csv"] = selection.to_dict()
        csv_rows = selection.records
        csv_unavailable = selection.error
    else:
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
    index = _index_block(
        consistency,
        csv_rows=csv_rows,
        db_path=db_path,
        today_kst=today_kst,
        calendar_dir=calendar_dir,
        csv_unavailable=csv_unavailable,
    )
    out.diagnostics["outlook_state"] = outlook.state
    out.diagnostics["index_status"] = index.status
    out.diagnostics["index_candidates"] = [c.identifier for c in index.candidates]
    out.diagnostics["index_diagnostics"] = index.diagnostics

    if not outlook.usable and not index.candidates:
        out.skip_reason = (
            REASON_ALL_STALE
            if index.status
            in (
                "stale",
                meta_gate.STATUS_API_FETCH_FAILED,
                meta_gate.STATUS_META_GATE_STALE,
            )
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
    # 같은 상태여도 **거래일마다 보낸다** (설계자 2026-09-16 · POC3-02B-OPS-03).
    #
    # 이전 계약은 fingerprint 가 같으면 `no_change` 로 막았다. 그런데 08:00 은
    # "오늘 장이 어떻게 흘러갈지" 를 주는 **정기** 브리핑이다. 5거래일 연속
    # 하락이면 그 주에 한 번만 오는 문제가 실측됐다(09-07~09-11 DOWN 연속).
    # 하락이 이어지는 것 자체가 알아야 할 정보다.
    #
    # fingerprint 는 없애지 않는다 — 메시지 비교·운영 기록에 쓴다. 같은 날짜
    # 재실행 차단은 `registry_key(push_kind, param_id, runtime_date_kst)` 가
    # 이미 한다.
    out.diagnostics["content_unchanged"] = out.previous_fingerprint == out.fingerprint

    # ⑥ CSV 갱신 안내 (R2 Q24) — **본문 · fingerprint 가 정해진 뒤** 끝에만 붙인다.
    # 여기까지 왔으면 어차피 나가는 발송이다. 안내만으로 발송을 만들지 않는다.
    notified = (prev or {}).get(STATE_NOTICE_KEY)
    out.refresh_notice_cycle_id = notified
    cycle = _refresh_notice_cycle(consistency, index.status)
    appended = cycle is not None and cycle != notified
    if appended:
        out.message_text = render.append_refresh_notice(out.message_text)
        out.refresh_notice_cycle_id = cycle
    out.diagnostics["refresh_notice"] = {
        "cycle_id": cycle,
        "already_notified": notified,
        "appended": appended,
    }
    return out


__all__ = [
    "REASON_ALL_STALE",
    "REASON_NO_CHANGE",
    "REASON_NO_PUBLISHABLE",
    "SCHEMA_VERSION",
    "STATE_NAME",
    "STATE_NOTICE_KEY",
    "BriefingOutcome",
    "assemble_market_briefing",
    "load_state",
    "save_state",
]
