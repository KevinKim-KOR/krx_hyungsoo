"""POC3-02C-OPS-02 — 사업군 신호 억제·cooldown (설계자 §5).

지속 중인 같은 신호를 반복 발송하지 않는다.

```text
발송     새 ticker 진입 · 상태 변경 · 단계 심화 · 회복 후 재진입 + cooldown 경과
미발송   같은 ticker 같은 상태 유지 · 수치만 변함 · cooldown 이내 재진입
```

보유 급락 경로의 억제(`holdings_risk_state`)와 **별도 파일·별도 상태**다. 설계
§9 — 사업군 경로 실패가 보유 경로를 막으면 안 되므로 상태도 섞지 않는다.

억제는 ticker 키 + 상태 비교로 한다 — 수치는 넣지 않는다. 수치만 달라지고
단계가 같으면 재발송하지 않기 위해서다. 숫자는 본문과 이력에는 남는다.
(`fingerprint`=`ticker#state` 는 파생 식별자일 뿐 저장 필드가 아니다 — 설계 §15-2.)

## 관측 상태와 전달 상태 (POC3-02D-OPS-02 · 설계자 Q1 2026-09-28 · §15-2 개정)

```text
state                 관측 — Gate 통과 회차마다 덮인다(회복·지속 판정용)
last_delivered_state  전달 — 전체 전송 성공 경로에서 본문에 실린 신호만 쓴다
last_sent_at          전달 시각 — 위와 같은 시점(기존)
sent_today            파일 수준 발송 수 — 위와 같은 시점(기존)
```

억제 비교는 **마지막 성공 전달 상태**와 한다. 예전에는 관측 `state` 와 비교해,
구역 상한에 잘리거나 전송 실패 · 부분 전송으로 전달되지 못한 새 상태가 다음
틱에 '이미 보낸 상태' 로 억제됐다(OPS-01 결과서 §8 결함 1).

구파일 호환(설계자 Q1): 필드가 있으면 그대로 · 없고 `last_sent_at` 이 있으면
기존 `state` 를 전달 상태로 추정 · 둘 다 없으면 None(전달 이력 없음).
읽기만으로 파일을 고치지 않는다 — 필드는 **다음 정상 저장**(관측 저장 · 전송 성공
저장) 때 생긴다. 그때 `state` 를 덮기 **전에** 추정값을 필드로 옮겨 적는다
(`_pin_legacy_delivered`). 옮기지 않고 덮으면 미전달 상태가 추정 규칙으로 '전달
상태' 가 된다(리뷰 실측 — 장중 배포 당일). 값은 추정 그대로라 전달 상태를
전진시키지 않는다.

`continuous` 는 억제 판정에서 **전달 상태가 이어지고 있나**로 쓴다. 회복(임계 밖)
뒤에 **전달 상태와 다른** 상태로 다시 관측된 것은 전달 상태의 지속이 아니다 —
회복 기록을 지우지 않는다(`_apply_observation`). 전달 상태와 같은 상태로 다시
관측되면 예전처럼 `True` 가 된다(회복 후 재진입 규칙 불변).
`schema_version` 은 그대로다(올리면 `schema_mismatch` 로 `sent_today` 가 0 으로
읽혀 일일 상한이 풀린다). fingerprint 저장이 아니다.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from app.runtime_evidence.sector_signal import SectorSignal

SCHEMA_VERSION = "sector_signal_state.v1"
KST = timezone(timedelta(hours=9))

# 마지막 성공 전달 상태 필드명(설계자 Q1 고정). 전송 성공 경로만 쓴다.
DELIVERED_STATE_KEY = "last_delivered_state"


@dataclass
class LoadedSectorState:
    """`entries: {ticker: {state, last_delivered_state, last_sent_at, ...}}`."""

    entries: dict[str, dict[str, Any]] = field(default_factory=dict)
    date_kst: Optional[str] = None
    sent_today: int = 0
    fallback: bool = True
    fallback_reason: Optional[str] = None

    @property
    def comparable(self) -> bool:
        return not self.fallback


@dataclass
class SectorChangeSet:
    send: list[SectorSignal] = field(default_factory=list)
    suppressed: list[tuple[str, str]] = field(default_factory=list)

    def has_send(self) -> bool:
        return bool(self.send)


def _parse_kst(value: Any) -> Optional[datetime]:
    if not isinstance(value, str) or not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=KST)


def last_delivered_state(entry: Any) -> Optional[Any]:
    """entry 의 마지막 성공 전달 상태(설계자 Q1 구파일 호환 규칙).

    ```text
    last_delivered_state 있음      → 그대로
    없음 + last_sent_at 있음       → 기존 state 를 전달 상태로 추정(구파일)
    없음 + last_sent_at 없음       → None (전달 이력 없음)
    ```

    값을 고치거나 파일에 쓰지 않는다 — 읽기 전용 해석이다.
    """
    if not isinstance(entry, dict):
        return None
    if DELIVERED_STATE_KEY in entry:
        return entry.get(DELIVERED_STATE_KEY)
    if entry.get("last_sent_at"):
        return entry.get("state")
    return None


def _pin_legacy_delivered(row: dict[str, Any]) -> None:
    """구파일 entry 의 추정 전달 상태를 `state` 를 덮기 전에 필드로 옮겨 적는다.

    설계자 Q1 '다음 정상 저장 때 필드를 추가'. 필드가 이미 있거나 전달 이력
    (`last_sent_at`)이 없으면 아무것도 하지 않는다 — 값을 새로 만들지 않는다.
    """
    if DELIVERED_STATE_KEY not in row and row.get("last_sent_at"):
        row[DELIVERED_STATE_KEY] = row.get("state")


def _apply_observation(row: dict[str, Any], sig: SectorSignal) -> None:
    """관측 4종(`state` · `continuous` · `sector_key` · `day_return_pct`)을 쓴다.

    `continuous` — 회복(`False`) 뒤 **전달 상태와 다른** 상태로 다시 관측되면
    `False` 를 유지한다. 전달되지 못한 Y 관측이 회복 기록을 지우면, 뒤이어 돌아온
    전달 상태 X 가 cooldown 이 지나도 '지속 중' 으로 억제됐다(리뷰 실측: X 전달 →
    회복 → 미전달 Y → X). 전달 상태와 같은 상태이거나 회복 기록이 없으면 `True`
    (예전과 같다).
    """
    _pin_legacy_delivered(row)
    delivered = last_delivered_state(row)
    recovered = row.get("continuous") is False
    row["state"] = sig.state
    row["continuous"] = not (
        recovered and delivered is not None and sig.state != delivered
    )
    row["sector_key"] = sig.sector_key
    row["day_return_pct"] = sig.day_return_pct


def load_sector_state(
    path: Path, *, today_kst: Optional[str] = None
) -> LoadedSectorState:
    """상태 읽기. **없거나 손상이면 비교 불가로 돌려준다** — 조용히 억제하지 않는다."""
    if not path.exists():
        return LoadedSectorState(fallback=True, fallback_reason="missing")
    try:
        body = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return LoadedSectorState(fallback=True, fallback_reason="unreadable")
    if not isinstance(body, dict) or body.get("schema_version") != SCHEMA_VERSION:
        return LoadedSectorState(fallback=True, fallback_reason="schema_mismatch")
    saved_date = body.get("date_kst")
    if today_kst and saved_date and str(saved_date)[:10] != str(today_kst)[:10]:
        # 새 거래일 — 어제 억제를 오늘로 끌고 오지 않는다.
        return LoadedSectorState(fallback=True, fallback_reason="date_reset")
    entries = body.get("entries")
    return LoadedSectorState(
        entries=entries if isinstance(entries, dict) else {},
        date_kst=str(saved_date) if saved_date else None,
        sent_today=int(body.get("sent_today") or 0),
        fallback=False,
    )


def compute_sector_changes(
    *,
    signals: list[SectorSignal],
    previous: LoadedSectorState,
    now_kst: datetime,
    cooldown_minutes: int,
) -> SectorChangeSet:
    """발송 대상 판정 (설계 §5).

    ```text
    발송     새 ticker 진입 · 상태 달라짐 · **회복 후 재진입 + cooldown 경과**
    미발송   같은 상태가 **계속 유지** · 수치만 변함 · cooldown 이내 재진입
    ```

    **지속 중인 신호는 시간이 지나도 재발송하지 않는다.** 예전에는 경과 시간만
    보고 120분 뒤 다시 보냈다 — 설계는 "임계 밖으로 **회복된 뒤** 다시 진입하고
    120분이 지남" 이라 두 조건이 모두 필요하다(검증자 지적).

    `continuous` 는 "마지막 전달 뒤 회복 없이 이어지고 있나" 다. 임계 밖으로
    나가면 `mark_absent_entries` 가 `False` 로 내린다. 회복 뒤 전달 상태와 **다른**
    상태로 관측돼도 `False` 로 남는다(`_apply_observation` · OPS-02 리뷰) — 미전달
    관측이 회복 기록을 지우지 않는다.

    **상태 비교 기준은 마지막 성공 전달 상태**(`last_delivered_state`)다 —
    관측 `state` 가 아니다(POC3-02D-OPS-02 · 설계자 Q1 · Q3).

    ```text
    전달 이력 없음(last_sent_at 없음·손상)      → 발송
    현재 상태 ≠ 마지막 전달 상태                → 발송 (cooldown 무관)
    현재 상태 = 마지막 전달 상태 + 지속 중      → 억제 (X → 미전달 Y → X 포함)
    현재 상태 = 마지막 전달 상태 + 회복 후 재진입 → cooldown 경과 시에만 발송
    ```

    비교 불가면 **전부 신규**로 본다 — 조용한 억제로 대체하지 않는다.
    """
    out = SectorChangeSet()
    if not previous.comparable:
        out.send = list(signals)
        return out

    for sig in signals:
        prev = previous.entries.get(sig.ticker)
        if not isinstance(prev, dict):
            out.send.append(sig)
            continue
        # **`last_sent_at` 을 먼저 본다.** 보낸 적이 없으면 억제할 근거가 없다.
        #
        # 관측 저장(`save_observation`)은 Telegram 결과와 무관하게 Gate 통과
        # 회차마다 `continuous=True` 를 남긴다 — 회복 판정에 필요해서다. 그런데
        # `continuous` 를 먼저 보면, **전송 실패·부분 전송된 신호가** 다음
        # 틱에서 "지속 중" 으로 억제된다(검증자 실측). 실제로는 한 번도 나간
        # 적이 없는데 영영 안 나가게 된다.
        last = _parse_kst(prev.get("last_sent_at"))
        if last is None:
            out.send.append(sig)
            continue
        if last_delivered_state(prev) != sig.state:
            # 마지막으로 **전달된** 상태와 다름 — cooldown 과 무관하게 보낸다.
            # 관측 `state` 와 비교하면, 잘림·전송 실패·부분 전송으로 전달되지
            # 못한 새 상태가 관측 저장으로 '이미 보낸 상태' 가 돼 억제됐다
            # (OPS-01 결과서 §8 결함 1). 관측은 이 판정의 근거가 아니다.
            out.send.append(sig)
            continue
        if prev.get("continuous"):
            # 보낸 적이 있고 **계속 유지 중** — 시간이 지나도 재발송하지 않는다.
            out.suppressed.append((sig.ticker, sig.state))
            continue
        # 회복 후 재진입 — 여기서만 cooldown 을 본다.
        elapsed = (now_kst - last).total_seconds() / 60.0
        if elapsed >= cooldown_minutes:
            out.send.append(sig)
        else:
            out.suppressed.append((sig.ticker, sig.state))
    return out


def mark_absent_entries(
    *,
    observed: list[SectorSignal],
    previous: LoadedSectorState,
    unevaluable: Optional[set[str]] = None,
) -> dict[str, dict[str, Any]]:
    """관측 결과를 **3상태**로 기록한다(설계 §15-2 · 설계자 D2 확정).

    ```text
    SIGNAL_PRESENT   조건 충족          → continuous=True   (호출자가 덮어쓴다)
    SIGNAL_ABSENT    정상 평가 후 미충족 → continuous=False
    UNEVALUABLE      평가 불가          → 기존 관측 상태 유지
    ```

    회복은 **정상적으로 평가할 수 있었고 조건이 충족되지 않았을 때만** 기록한다.
    provider 장애·커버리지 미달·사업군 예외·필수 데이터 누락으로 평가할 수 없는
    범위는 회복으로 치지 않는다 — `state`·`continuous`·`day_return_pct`·
    `last_sent_at`·`last_delivered_state` 를 그대로 둔다. **모르는 것을 회복으로
    기록하지 않는다.** 어느 경우든 전달 필드(`last_delivered_state`·
    `last_sent_at`)는 복사만 하고 바꾸지 않는다.

    기존 기록 자체는 어느 경우에도 **지우지 않는다** — 지우면 재진입이 신규로
    잡혀 cooldown 을 건너뛴다.
    """
    seen = {s.ticker for s in observed}
    keep = unevaluable or set()
    entries: dict[str, dict[str, Any]] = {}
    for ticker, row in (previous.entries or {}).items():
        if not isinstance(row, dict):
            continue
        entries[ticker] = dict(row)
        if ticker not in seen and ticker not in keep:
            entries[ticker]["continuous"] = False
    return entries


def merge_sector_entries(
    *,
    sent: list[SectorSignal],
    previous: LoadedSectorState,
    now_kst: datetime,
    observed: Optional[list[SectorSignal]] = None,
    unevaluable: Optional[set[str]] = None,
) -> dict[str, dict[str, Any]]:
    """전송 성공 경로의 entries. 관측된 것은 관측 4종을, **보낸 것만** 전달 필드
    (`last_sent_at` · `last_delivered_state`)를 갱신한다.

    `sent` = 본문에 실제로 실린 신호(`IntradayAssembly.sent_signals`)다 — 구역
    상한에 잘린 신호는 들어 있지 않다. 호출자(`runner_evidence`)는 전체 전송
    성공 뒤에만 부른다 — 전송 실패 · 부분 전송 · 조립 뒤 예외 회차는 여기에 오지
    않는다(OPS-02 계약 4~8).

    억제된 신호로 `last_sent_at` 을 밀면 cooldown 이 영원히 끝나지 않는다.
    선정에서 빠진 종목의 기존 기록은 유지한다 — 지우면 같은 날 재진입이 신규로
    잡혀 재발송된다.
    """
    entries = mark_absent_entries(
        observed=observed or [], previous=previous, unevaluable=unevaluable
    )
    stamp = now_kst.isoformat()
    # 이번 회차에 **관측된** 것은 관측 4종을 쓴다(`_apply_observation` — 보내지 않은
    # 억제 · 잘린 신호도 관측 사실은 같다). 구파일 entry 는 덮기 전에 추정 전달
    # 상태를 필드로 옮긴다(설계자 Q1).
    for sig in observed or []:
        _apply_observation(entries.setdefault(sig.ticker, {}), sig)
    for sig in sent:
        entries.setdefault(sig.ticker, {})
        entries[sig.ticker].update(
            {
                "state": sig.state,
                # 마지막 성공 전달 상태 — **여기서만** 쓴다(설계자 Q1).
                DELIVERED_STATE_KEY: sig.state,
                "last_sent_at": stamp,
                "continuous": True,
                "sector_key": sig.sector_key,
                "day_return_pct": sig.day_return_pct,
            }
        )
    return entries


def save_observation(
    path: Path,
    *,
    observed: list[SectorSignal],
    today_kst: str,
    unevaluable: Optional[set[str]] = None,
) -> None:
    """**매 회차** 관측 상태만 저장한다. 발송 상태는 건드리지 않는다.

    설계 §9 는 "Telegram 전송 성공 뒤에만 suppression state 저장" 인데, 그건
    **발송 사실**(`last_sent_at` · `sent_today`) 얘기다. 미발송 신호가 발송
    완료로 기록되면 안 되기 때문이다.

    반면 `continuous`(관측 지속 여부)는 **매 회차 갱신돼야** 한다 — 신호가
    사라진 회차를 기록하지 않으면 "회복 후 재진입" 을 영원히 구분하지 못하고,
    지속 신호가 계속 억제되거나 반대로 계속 재발송된다(검증자 실측).

    ```text
    여기서 쓰는 것      state · continuous · sector_key · day_return_pct
    여기서 안 쓰는 것   last_delivered_state · last_sent_at · sent_today
                        ← 전송 성공 시에만(기존 값은 그대로 복사)
    ```

    관측은 전달 상태를 전진시키지 않는다(OPS-02 계약 3). 구파일 entry 는
    `state` 를 덮기 전에 **추정 전달 상태를 그대로** 필드로 옮긴다(설계자 Q1
    '다음 정상 저장 때 필드를 추가' · 값을 바꾸지 않는다).

    `unevaluable` 에 든 ticker 는 **건드리지 않는다** — 평가 불가를 회복으로
    기록하면 지속 신호가 cooldown 뒤 재발송된다(설계자 D2).
    """
    previous = load_sector_state(path, today_kst=today_kst)
    entries = mark_absent_entries(
        observed=observed, previous=previous, unevaluable=unevaluable
    )
    for sig in observed:
        _apply_observation(entries.setdefault(sig.ticker, {}), sig)
    save_sector_state(
        path,
        entries=entries,
        today_kst=today_kst,
        # **올리지 않는다.** 발송 수는 전송 성공 경로에서만 센다.
        sent_today=(previous.sent_today if previous.comparable else 0),
    )


def save_sector_state(
    path: Path,
    *,
    entries: dict[str, dict[str, Any]],
    today_kst: str,
    sent_today: int,
) -> None:
    """원자적 저장 프리미티브. 호출자가 둘이다(설계 §15-2).

    - `save_observation()` — **매 회차**. 관측 4종을 쓰고 `sent_today` 는
      이전 값을 그대로 넘긴다(전진하지 않는다).
    - 러너의 전송 성공 경로 — `sent_today` 전진 · `last_sent_at` ·
      `last_delivered_state` 기록(`merge_sector_entries`).
    """
    body = {
        "schema_version": SCHEMA_VERSION,
        "date_kst": str(today_kst)[:10],
        "sent_today": int(sent_today),
        "entries": entries,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(
        prefix=".sector_state.", suffix=".tmp", dir=str(path.parent)
    )
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


__all__ = [
    "DELIVERED_STATE_KEY",
    "KST",
    "SCHEMA_VERSION",
    "LoadedSectorState",
    "SectorChangeSet",
    "compute_sector_changes",
    "last_delivered_state",
    "mark_absent_entries",
    "load_sector_state",
    "merge_sector_entries",
    "save_observation",
    "save_sector_state",
]
