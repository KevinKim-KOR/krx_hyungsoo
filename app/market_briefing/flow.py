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

## POC3-02D-OPS-03 (설계자 PLAN 판정 2026-09-29)

- 시장 브리핑은 08:30 · 배치는 08:10(확정 계약 1 · 2). 위 '07:20' · '08:00' 은 옛 시각이다.
- 국내 최신성 = `actual_basis_date == expected_previous_trading_day`(확정 계약 6) —
  lag 숫자로 판정하지 않는다. 아니면 기초지수 구역만 빼고 설계자 확정 안내 1줄
  (`STATUS_PREV_DAY_MISSING`). T-2 값 · 날짜는 본문에 쓰지 않는다.
- 5일 · 20일은 거래일 **날짜**로 정한다(`krx_store.resolve_calendar_window` · 확정
  계약 5). 그 날짜가 저장돼 있지 않으면 구역 fail-closed(6 · 21일 전 값으로 밀지 않는다).
- 저장된 판정은 기대 T-1 과 그 날짜 창 d20 의 것일 때만 쓴다(08:10 목표일 수집과 같은 창).
- 뒤 PUSH 에 영향을 주는 배치 실패는 본문 끝 1줄 · 낼 내용이 없으면 그 1줄만 담은
  본문(확정 계약 13 · PLAN STEP 7-3). 하루 1회는 일 단위 registry 가 보장한다.
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
    # POC5-01B — 원장이 읽는 계산 결과(본문 · diagnostics 에는 넣지 않는다).
    outlook: Optional[ev.Outlook] = None
    index: Optional[ev.IndexLeadership] = None

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
# POC3-02D-OPS-03 — 기초지수 구역은 lag 로 판정하지 않는다(확정 계약 6). 두 이름은
# 호환(기존 테스트 · 도구)으로만 남긴다.
_weekday_axis_before = trading_day_lag.weekday_axis_before
_window_lag_trading_days = trading_day_lag.window_lag_trading_days
# 확정 계약 6 의 기대 기준일. 모듈 전역에서 찾으므로 역검증
# (`scripts/ops02b2/reverse_verify_guards.py` ②)이 갈아끼울 수 있다.
_expected_previous_trading_day = trading_day_lag.expected_previous_trading_day


def _verdict_stale(
    consistency: meta_gate.ConsistencyResult, window: krx_store.CalendarWindow
) -> Optional[dict[str, Any]]:
    """R2 Q27 — 저장된 판정이 오늘 창의 것이 아니면 진단 dict, 같으면 `None`.

    판정을 다시 계산하지 않는다. 오늘 창 = 기대 T-1 과 그 **거래일 날짜** d20
    (POC3-02D-OPS-03 — 08:10 목표일 수집이 판정에 남기는 창과 같다).
    """
    latest, d20 = window.latest, window.d20
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

    POC3-02D-OPS-03 — **국내 기준일 확인이 맨 앞이다**(확정 계약 6). 저장 계열의
    최신일(= 이 구역이 쓸 국내 기준일)이 기대 T-1 과 다르면 다른 관문을 보기 전에
    닫는다 — T-1 부재를 CSV 갱신 · 판정 실패로 잘못 안내하지 않는다.
    """
    expected = _expected_previous_trading_day(today_kst, calendar_dir=calendar_dir)
    stored = krx_store.stored_trading_days(db_path=db_path)
    actual = stored[-1] if stored else None
    if expected is None or actual != expected:
        # 지난 날짜는 진단에만 남긴다 — 본문 `기준` 줄에 쓰지 않는다(설계 §3.4).
        return ev.IndexLeadership(
            status=render.STATUS_PREV_DAY_MISSING,
            diagnostics={
                "reason": "basis_date_not_expected",
                "expected_previous_trading_day": expected,
                "actual_basis_date": actual,
            },
        )
    if consistency is None:
        return ev.IndexLeadership(
            status=meta_gate.STATUS_API_FETCH_FAILED,
            diagnostics={"reason": "no_0720_result"},
        )
    window = krx_store.resolve_calendar_window(
        expected, calendar_dir=calendar_dir, db_path=db_path
    )
    stale = _verdict_stale(consistency, window)
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

    # 확정 계약 5 — d5 · d20 은 거래일 **날짜**다. 창(21거래일) 안 빠진 날이 계산에
    # 쓰는 세 날짜에 걸리면 구역을 닫는다(6 · 21일 전 값으로 밀지 않는다). 옛
    # '21일 미만' · 'lag 초과' 관문은 위 T-1 확인과 이 확인이 함께 대신한다.
    prices = window.price_window()
    if prices is None or not window.usable:
        return ev.IndexLeadership(
            status="stale",
            diagnostics={"reason": "window_missing_days", **window.to_dict()},
        )

    closes = krx_store.closes_on(list(prices.dates), db_path=db_path)
    matched = meta_gate.matched_meta_rows(
        csv_rows, {t: n for t, n in _api_names_from(consistency, csv_rows).items()}
    )
    result = ev.compute_index_leadership(
        meta_rows=matched,
        closes=closes,
        latest=prices.latest,
        d5=prices.d5,
        d20=prices.d20,
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
    """R2 Q24 — 안내 대상 주기. 오늘 창의 판정이 `refresh_due` 일 때만.

    T-1 이 없는 날(`STATUS_PREV_DAY_MISSING`)의 판정도 오늘 창의 것이 아니다.
    """
    if consistency is None or index_status in (
        meta_gate.STATUS_META_GATE_STALE,
        render.STATUS_PREV_DAY_MISSING,
    ):
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
    batch_failure: Sequence[str] = (),
) -> BriefingOutcome:
    """러너 §3-e 전체. **판정하지 않고 조립만** 한다.

    공식 CSV — 운영은 `meta_dir` 을 넘겨 07:20 과 같은 resolver 로 고른다.
    `official_csv_path` 는 파일을 직접 지정하는 옛 호출(합성 fixture · 고정 경로
    도구)용이다. 둘 중 하나만 넘긴다.

    `batch_failure` — 러너가 배치 상태로 정한 고지 사유(PLAN STEP 7-3 · 비면 고지 없음).
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
    out.outlook, out.index = outlook, index

    # ④ 본문 — 낼 내용이 없으면 skip. 단 뒤 PUSH 에 영향을 주는 배치 실패가 있으면
    # 고지 1줄만 담은 본문을 만든다(PLAN STEP 7-3 · 그 밖의 안내는 붙이지 않는다).
    notice = {"reasons": list(batch_failure), "appended": False, "notice_only": False}
    out.diagnostics["batch_failure_notice"] = notice
    would_skip: Optional[str] = None
    if not outlook.usable and not index.candidates:
        would_skip = (
            REASON_ALL_STALE
            if index.status
            in (
                "stale",
                meta_gate.STATUS_API_FETCH_FAILED,
                meta_gate.STATUS_META_GATE_STALE,
                render.STATUS_PREV_DAY_MISSING,
            )
            else REASON_NO_PUBLISHABLE
        )
    else:
        out.message_text = render.render_market_briefing(
            outlook=outlook,
            index_status=index.status,
            candidates=index.candidates,
            support=support,
            us_asof=sp500_asof if sp500_fresh else None,
            kr_asof=index.price_asof,
        )
        if not out.message_text:
            would_skip = REASON_NO_PUBLISHABLE
    if would_skip is not None:
        if not batch_failure:
            out.skip_reason = would_skip
            return out
        out.diagnostics["would_skip_reason"] = would_skip
        out.message_text = render.render_notice_only()
        notice.update(appended=True, notice_only=True)

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

    # ⑥-a 배치 실패 고지 — fingerprint 가 정해진 뒤 끝에 붙인다(CSV 안내보다 앞).
    if batch_failure and not notice["notice_only"]:
        out.message_text = render.append_batch_notice(out.message_text)
        notice["appended"] = True

    # ⑥ CSV 갱신 안내 (R2 Q24) — **본문 · fingerprint 가 정해진 뒤** 끝에만 붙인다.
    # 여기까지 왔으면 어차피 나가는 발송이다. 안내만으로 발송을 만들지 않는다 —
    # 고지만 담은 본문에도 붙이지 않는다(다음 실제 본문에 붙는다).
    notified = (prev or {}).get(STATE_NOTICE_KEY)
    out.refresh_notice_cycle_id = notified
    cycle = _refresh_notice_cycle(consistency, index.status)
    if notice["notice_only"]:
        cycle = None
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
