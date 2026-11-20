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
뒤에 다시 관측된 것 중 아래 두 경우는 전달 상태의 지속이 아니다 — 회복 기록
(`False`)을 지우지 않는다(`_apply_observation`).

```text
회복 뒤 · 전달 상태와 다른 상태                        → False 유지 (OPS-02 리뷰)
회복 뒤 · 전달 상태와 같은 상태 · 이번 회차 발송 후보  → False 유지 (POC6-35 K2)
회복 뒤 · 전달 상태와 같은 상태 · 후보 아님(대기 억제) → True (K3 · 회복 후 재진입)
```

'이번 회차 발송 후보' 는 사업군 · 보유 급등 `compute_sector_changes` 의 `send` 합집합
(`send_candidates`)이다. 본문에 실려 전체 전송이 성공한 후보는 전송 성공 저장이
`True` 로 덮는다. 구역 상한 · 전송 실패 · 부분 전송 · 발송 전 차단 · 일일 상한으로
전달되지 못한 재진입은 회복 기록이 남아 다음 회차에 **그 회차의 정책 대기**로 다시
판정된다(설계자 PLAN 판정 Q1 · Q5 2026-11-19). 관측을 쓰는 두 저장(전송 성공 저장의
`merge_sector_entries` · 매 회차 `save_observation`)이 같은 집합을 받는다.

전송 성공 뒤 첫 저장(러너)이 실패하면 뒤의 `save_observation(sent=…)` 이 같은 병합을
대신 한다(보완 1 · 같은 회차 시각이 이미 행에 있으면 `sent_today` 를 다시 세지 않는다 ·
그 병합까지 실패하면 관측만 쓴다). `schema_version` 은 그대로다(올리면
`schema_mismatch` 로 `sent_today` 가 0 으로 읽혀 일일 상한이 풀린다). fingerprint 저장이
아니다.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Collection, Optional

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


# 이번 회차 발송 후보 `(ticker, state)` — 관측 저장의 회복 유지 판정용(POC6-35 A1).
Candidates = Collection[tuple[str, str]]


def send_candidates(
    *change_sets: Optional[SectorChangeSet],
) -> frozenset[tuple[str, str]]:
    """이번 회차 **발송 후보** — `compute_sector_changes` 결과들의 `send` 합집합.

    호출자는 사업군(`changes`)과 보유 급등(`surge_changes`)을 **둘 다** 넘긴다(같은
    상태 파일 · 같은 판정 · 설계자 Q2). 후보는 판정을 통과한 것이다 — 구역 상한 ·
    일일 상한 · 전송 결과와 무관하다. 억제(`suppressed`)는 후보가 아니다.
    """
    return frozenset(
        (s.ticker, s.state)
        for cs in change_sets
        if cs is not None
        for s in (cs.send or [])
    )


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


def _apply_observation(
    row: dict[str, Any],
    sig: SectorSignal,
    candidates: Optional[Candidates] = None,
) -> None:
    """관측 4종(`state` · `continuous` · `sector_key` · `day_return_pct`)을 쓴다.

    `continuous` — 회복(`False`) 뒤 다시 관측된 것이 아래 둘 중 하나면 `False` 를
    유지한다. 나머지(회복 기록 없음 · 전달 이력 없음 · 후보 아닌 같은 상태)는 `True`.

    - **전달 상태와 다른** 상태: 전달되지 못한 Y 관측이 회복 기록을 지우면, 뒤이어
      돌아온 전달 상태 X 가 cooldown 이 지나도 '지속 중' 으로 억제됐다(리뷰 실측: X
      전달 → 회복 → 미전달 Y → X).
    - **전달 상태와 같은 상태 + 이번 회차 발송 후보**(`candidates` 에 `(ticker,
      state)` 가 있음 · POC6-35 K2): 대기를 채운 재진입이 잘림 · 전송 실패 등으로
      전달되지 못했다. `True` 로 덮으면 다음 회차부터 '지속 중' 으로 억제됐다. 전달
      성공이면 호출자(`merge_sector_entries` 의 sent 루프)가 `True` 로 덮는다.

    대기 때문에 억제된 같은 상태 재진입은 후보가 아니므로 `True` 다(K3 — 그 뒤 지속도
    억제 · POC6-34 RESULT 판정).
    """
    _pin_legacy_delivered(row)
    delivered = last_delivered_state(row)
    recovered = row.get("continuous") is False
    row["state"] = sig.state
    is_candidate = (sig.ticker, sig.state) in (candidates or ())
    row["continuous"] = not (
        recovered and delivered is not None and (sig.state != delivered or is_candidate)
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


def load_merge_base(
    path: Path, *, today_kst: str, snapshot: Optional[LoadedSectorState] = None
) -> tuple[LoadedSectorState, Optional[str]]:
    """쓰기 직전에 다시 읽은 상태 — 병합 · 관측 저장의 기준(POC6-35 검증자 r1 F1).

    다시 읽기가 **읽기 실패**(`unreadable`)인데 이번 회차가 이미 아는 상태(`snapshot` =
    조립 때 읽은 상태 또는 첫 저장이 방금 쓴 상태 · 오늘 날짜 · 비교 가능)가 있으면 그
    상태를 기준으로 쓴다. 읽기 실패를 '발송 이력 없음' 으로 보고 빈 상태 위에 쓰면 앞선
    전달 기록과 `sent_today` 가 지워져 다음 회차가 같은 신호를 다시 보내고 일일 상한을
    넘긴다.

    ```text
    다시 읽기 정상 · 없음 · 날짜 바뀜 · 형식 다름   읽은 그대로(예전 규칙)     진단 없음
    읽기 실패 + 이번 회차가 아는 상태 있음        그 상태                   'snapshot'
    읽기 실패 + 아는 상태 없음(조립 때도 손상)     비교 불가(예전처럼 새로 씀) 'unreadable'
    ```

    반환 = `(기준 상태, 진단)`. 마지막 줄은 손상 파일을 새로 써서 복구하는 기존 동작이다.
    """
    loaded = load_sector_state(path, today_kst=today_kst)
    if loaded.fallback_reason != "unreadable":
        return loaded, None
    # 날짜 비교는 `load_sector_state` 와 같은 규칙(둘 다 있을 때만 · 앞 10자리).
    day = snapshot.date_kst if snapshot is not None else None
    usable = (
        snapshot is not None
        and snapshot.comparable
        and (not day or not today_kst or str(day)[:10] == str(today_kst)[:10])
    )
    return (snapshot, "snapshot") if usable else (loaded, "unreadable")


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
    상태로 관측돼도(OPS-02 리뷰), 같은 상태로 관측됐는데 그 회차 **발송 후보**였고
    전달되지 못했어도(POC6-35 K2) `False` 로 남는다(`_apply_observation`) — 미전달
    관측이 회복 기록을 지우지 않는다. 그래서 잘린 재진입은 다음 회차에 아래 마지막
    줄(회복 후 재진입)로 **그 회차의 `cooldown_minutes`** 와 다시 비교된다. 그때 대기를
    못 채우면 억제되고 후보가 아니므로 `True` 가 된다(K3 지속 억제 · 설계자 Q5).

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
    candidates: Optional[Candidates] = None,
) -> dict[str, dict[str, Any]]:
    """전송 성공 경로의 entries. 관측된 것은 관측 4종을, **보낸 것만** 전달 필드
    (`last_sent_at` · `last_delivered_state`)를 갱신한다.

    `sent` = 본문에 실제로 실린 신호(`IntradayAssembly.sent_signals`)다 — 구역
    상한에 잘린 신호는 들어 있지 않다. 호출자는 전체 전송 성공을 확인한 뒤에만 부른다
    — 러너 첫 저장(`runner_evidence`)과, 그것이 끝나지 않았을 때의 대신 저장
    (`save_observation(sent=…)` · POC6-35 보완 1). 전송 실패 · 부분 전송 · 조립 뒤
    예외 회차는 여기에 오지 않는다(OPS-02 계약 4~8).

    `candidates` = 이번 회차 발송 후보(`send_candidates`). 후보였는데 `sent` 에 없는
    회복 뒤 같은 상태 재진입은 회복 기록(`continuous=False`)을 유지한다(POC6-35 K2 ·
    `_apply_observation`). 기본값(없음)은 예전 동작이다.

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
        _apply_observation(entries.setdefault(sig.ticker, {}), sig, candidates)
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
    candidates: Optional[Candidates] = None,
    sent: Optional[list[SectorSignal]] = None,
    now_kst: Optional[datetime] = None,
    snapshot: Optional[LoadedSectorState] = None,
) -> tuple[str, Optional[str], Optional[str]]:
    """**매 회차** 관측 상태를 저장한다. 발송 상태는 `sent` 를 받았을 때만 쓴다.

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
    예외(POC6-35)       `sent` 를 받은 대신 저장(아래 보완 1)은 이 셋도 쓴다 —
                        전송 성공 저장과 같은 병합(`merge_sector_entries` · +1)
    ```

    관측은 전달 상태를 전진시키지 않는다(OPS-02 계약 3). 구파일 entry 는
    `state` 를 덮기 전에 **추정 전달 상태를 그대로** 필드로 옮긴다(설계자 Q1
    '다음 정상 저장 때 필드를 추가' · 값을 바꾸지 않는다).

    `unevaluable` 에 든 ticker 는 **건드리지 않는다** — 평가 불가를 회복으로
    기록하면 지속 신호가 cooldown 뒤 재발송된다(설계자 D2). 잘린 재진입의 다음
    회차가 평가 불가여도 그 행(회복 기록)이 그대로 남는다(설계자 Q5).

    `candidates` = 이번 회차 발송 후보(`send_candidates`). 전송 성공 저장과 **같은
    집합**이다 — 후보였는데 전달되지 못한 회복 뒤 같은 상태 재진입은 회복 기록을
    유지한다(POC6-35 K2 · `_apply_observation`).

    **성공 전달 대신 저장(POC6-35 보완 1).** `sent` 를 넘기면(빈 목록 포함) 전체 전송
    성공인데 러너 첫 저장이 끝나지 않은 회차다(판정은 호출자 `apply_intraday_records`).
    첫 저장과 같은 병합(`merge_sector_entries` · `sent_today` +1)을 여기서 한다.
    `sent` 행 중 하나라도 `last_sent_at` 이 이미 이번 회차 시각(`now_kst`)이면 첫 저장이
    실제로는 써진 것이므로 `sent_today` 를 다시 올리지 않는다(같은 회차 한 번만 반영).
    빈 `sent`(보유 급락만 실린 통합 본문)는 그 표식이 없어 호출자 판정에만 기댄다.

    대신 저장(병합 · 쓰기)이 예외를 내면 **관측만 쓰는 저장을 한 번 더** 한다(독립 검토
    B-1 — 병합이 늘 실패하는 입력이어도 이번 회차 관측 · 회복 기록은 남긴다). 그때
    `sent_today` 는 올리지 않는다. 그것까지 실패해야, 즉 아무것도 쓰지 못했을 때만
    예외를 낸다.

    **기준 상태(검증자 r1 F1).** 세 저장(대신 저장 · 그 재시도 · 관측만)은 모두
    `load_merge_base` 로 다시 읽은 상태 위에 쓴다. 다시 읽기가 읽기 실패이면
    `snapshot`(pending 의 이번 회차 상태 — 조립 때 읽은 상태, 첫 저장이 썼으면 그 상태)을
    기준으로 쓴다. 대신 저장이 그 상태에 병합하면 `sent_today` 는 이번 회차 전 값 + 1 이다
    (첫 저장이 실제로 썼어도 같은 값).

    반환 = `(쓴 것, 대신 저장 예외 형 이름, 기준 진단)` — 쓴 것은 `"sent"`(대신 저장 병합)
    또는 `"observation"`(관측만). 예외 형 이름은 대신 저장이 실패해 관측만 쓴 경우에만
    있다. 기준 진단은 다시 읽기가 읽기 실패일 때만 있다(`'snapshot'` · `'unreadable'`).
    """
    if sent is not None and now_kst is None:
        raise ValueError("sent 를 넘기면 now_kst(이번 회차 시각)도 넘겨야 한다")
    previous, base = load_merge_base(path, today_kst=today_kst, snapshot=snapshot)
    # 관측만 쓰는 회차는 **올리지 않는다.** 발송 수는 전송 성공 경로에서만 센다.
    sent_today = previous.sent_today if previous.comparable else 0
    fallback_error: Optional[str] = None
    if sent is not None:
        try:
            stamp = now_kst.isoformat()
            rows = previous.entries or {}
            already = any(
                isinstance(rows.get(s.ticker), dict)
                and rows[s.ticker].get("last_sent_at") == stamp
                for s in sent
            )
            entries = merge_sector_entries(
                sent=list(sent),
                previous=previous,
                now_kst=now_kst,
                observed=observed,
                unevaluable=unevaluable,
                candidates=candidates,
            )
            save_sector_state(
                path,
                entries=entries,
                today_kst=today_kst,
                sent_today=sent_today + (0 if already else 1),
            )
            return "sent", None, base
        except Exception as e:  # noqa: BLE001 - 관측은 남긴다(B-1)
            fallback_error = type(e).__name__
    entries = mark_absent_entries(
        observed=observed, previous=previous, unevaluable=unevaluable
    )
    for sig in observed:
        _apply_observation(entries.setdefault(sig.ticker, {}), sig, candidates)
    save_sector_state(path, entries=entries, today_kst=today_kst, sent_today=sent_today)
    return "observation", fallback_error, base


def save_sector_state(
    path: Path,
    *,
    entries: dict[str, dict[str, Any]],
    today_kst: str,
    sent_today: int,
) -> None:
    """원자적 저장 프리미티브. 호출자가 둘이다(설계 §15-2).

    - `save_observation()` — **매 회차**. 관측 4종을 쓰고 `sent_today` 는
      이전 값을 그대로 넘긴다(전진하지 않는다). 단 전체 전송 성공인데 러너 첫 저장이
      끝나지 않은 회차(`sent` 를 받음)는 아래와 같은 병합을 대신 한다(POC6-35 보완 1).
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
    "load_merge_base",
    "load_sector_state",
    "merge_sector_entries",
    "save_observation",
    "save_sector_state",
    "send_candidates",
]
