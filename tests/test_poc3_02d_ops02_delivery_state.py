"""POC3-02D-OPS-02 §3-2 — 장중 **전달 상태** 저장 계약 (설계자 Q1~Q3 확정 2026-09-28).

관측 상태(`state`)와 마지막 성공 전달 상태(`last_delivered_state`)를 나눈다.
억제 판정은 전달 상태와 비교한다. OPS-01 결과서 §8 의 두 결함을 실제 `run()`
경로로 고정한다.

```text
결함 1  구역 상한 잘림 · 전송 실패 · 부분 전송으로 전달되지 못한 새 상태가 관측
        저장으로 '이미 보낸 상태' 가 돼 다음 틱부터 억제됐다
결함 2  장중 조립 뒤 예외로 구 본문만 나갔는데 사업군 · 급등 신호가 발송 완료로
        기록됐다(`out.intraday` 대입 뒤 예외)
```

rig 는 OPS-01 파일 · flow-through 의 것을 import 해 그대로 쓴다(두 파일에는 테스트
추가 0). 실제 Telegram · Naver · OCI write 0건 — 전송기 · 시세 · 상태 경로 전부
대역 · tmp 경로(`_live_guard`).

run() 시나리오는 틱마다 다섯 가지를 **따로** 기록하고 단언한다(설계자 STEP 5).

```text
OBSERVATION_STATE               S 파일 state · continuous
DELIVERY_STATE                  S 파일 last_delivered_state · last_sent_at · sent_today
                                + 위험 상태 파일 worst_state(D*)
ACTUALLY_INCLUDED_SIGNALS       이번 틱 전송기에 넘어간 본문에 실린 신호
SUCCESSFULLY_DELIVERED_SIGNALS  전체 전송 성공이면 위와 같고, 아니면 없음
PENDING_FOR_NEXT_TICK           관측됐지만 전달 상태가 따라오지 못한 신호
```

단언 순서: 먼저 틱별 **동작**(status · 본문)을 보고, 그다음 저장 값을 본다 —
기준 코드(RED)에서 실패 원인이 동작 결함으로 드러나게 하기 위해서다.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional

import pytest

from tests import test_intraday_alert_flow_through as ft
from tests import test_poc3_02d_ops01_holdings_risk_flow as ops01
from tests.test_holdings_risk_alert_runner import _Sender

RISK_KIND = ft.RISK_KIND
TODAY = ft.TODAY

# 기존 rig fixture 재사용 — pytest 는 **모듈 속성 이름**으로 fixture 를 등록한다.
market_db = ft.market_db

ER, AC = "ENTRY_REVIEW", "AVOID_CHASE"
U57, U710, D57 = "U5_7", "U7_10", "D5_7"
NAMES = {
    "H00001": "보유하나",
    "H00002": "보유둘",
    "H00003": "보유셋",
    "H00004": "보유넷",
}
ONE = {"H00001": NAMES["H00001"]}


def _delivered_of(entry: Optional[dict]) -> Any:
    """설계자 Q1 구파일 호환 규칙(명세). 운영 helper 와 같은지는 단위 테스트가 본다."""
    if not isinstance(entry, dict):
        return None
    if "last_delivered_state" in entry:
        return entry["last_delivered_state"]
    return entry.get("state") if entry.get("last_sent_at") else None


# ── 틱 기록 도구 ────────────────────────────────────────────────────────────


@dataclass
class _Tick:
    label: str
    status: str
    reason: Optional[str]
    partial: bool
    intraday_error: Optional[str]
    header: Optional[str]
    observation: dict = field(default_factory=dict)
    delivery: dict = field(default_factory=dict)
    sent_today: Optional[int] = None
    risk_worst: dict = field(default_factory=dict)
    included: set = field(default_factory=set)
    delivered: set = field(default_factory=set)
    pending: set = field(default_factory=set)
    tally_ticks: int = 0
    record: dict = field(default_factory=dict)


class _ChunkSender:
    """실제 `telegram_send` 분할 로직 + **네트워크 없는** 청크 전송 대역.

    `fail_second=True` 면 한 본문의 둘째 청크부터 실패한다(실제형 부분 전송).
    """

    def __init__(self, monkeypatch):
        import app.three_push_runner_common as common

        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token-" + "z" * 24)
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "chat-test-id-zz")
        self.calls: list[str] = []
        self.chunks: list[str] = []
        self.fail_second = False
        self._n = 0
        self._common = common

        def _one(token, chat_id, text):
            self._n += 1
            self.chunks.append(text)
            if self.fail_second and self._n >= 2:
                return False, "mock chunk 실패"
            return True, None

        monkeypatch.setattr(common, "_telegram_send_one", _one)

    def __call__(self, text, *a, **kw):
        self.calls.append(text)
        self._n = 0
        return self._common.telegram_send(text)


class _Scenario:
    """틱 실행 + 다섯 분리 기록. `inject(fn)` 은 다음 틱 조립 결과에 한 번 적용."""

    def __init__(
        self, name, monkeypatch, tmp_path, market_db, *, holdings, sender=None
    ):
        import app.runtime_evidence.intraday_alert_flow as iflow
        from app.runtime_evidence import holdings_risk_flow as rflow

        self.name = name
        self.mp = monkeypatch
        self.sender = sender if sender is not None else _Sender()
        self.rig = ops01._rig(monkeypatch, tmp_path, market_db, sender=self.sender)
        ops01._set_holdings(monkeypatch, holdings)
        self.base = rflow._now_kst(None).replace(
            hour=9, minute=30, second=0, microsecond=0
        )
        self.labels: dict[str, str] = {}
        self.ticks: list[_Tick] = []
        self.calls: list[tuple[list, Any]] = []
        self._inject = None
        real = iflow.assemble_intraday_alert

        def _wrapped(**kw):
            res = real(**kw)
            self.calls.append((list(kw.get("held_drop") or []), res))
            if self._inject is not None:
                fn, self._inject = self._inject, None
                fn(res)
            return res

        monkeypatch.setattr(iflow, "assemble_intraday_alert", _wrapped)

    def inject(self, fn):
        self._inject = fn

    def quotes(self, held, sectors=None):
        stamp = ft._asof(TODAY)
        q = {t: ft._Q(10000.0, stamp, r) for t, r in held.items()}
        for i in range(10):
            t = f"T{i:05d}"
            q[t] = ft._Q(10000.0, stamp, (sectors or {}).get(t, 0.0))
        self.rig["quotes"] = q

    def state(self):
        p = self.rig["sector_state"]
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None

    def run(self, minutes, label, *, mode="send") -> _Tick:
        ft._tick_at(self.mp, self.base, minutes)
        self.labels[(self.base + timedelta(minutes=minutes)).isoformat()] = (
            f"t+{minutes}"
        )
        sent_before, calls_before = len(self.sender.calls), len(self.calls)
        rec = self.rig["runner"].run(RISK_KIND, mode)
        # 회차당 Telegram 최대 1건(설계 §6) — 한 run 이 본문을 두 번 넘기지 않는다.
        assert len(self.sender.calls) - sent_before <= 1
        body = self.sender.calls[-1] if len(self.sender.calls) > sent_before else None
        new = self.calls[calls_before:]
        held_drop, res = new[-1] if new else ([], None)
        st = self.state() or {}
        entries = st.get("entries") or {}
        risk = ops01._risk_entries(self.rig) or {}
        tick = _Tick(
            label=f"t+{minutes} {label}",
            status=rec.get("status"),
            reason=rec.get("reason"),
            partial=bool(rec.get("partial_delivery")),
            intraday_error=rec.get("intraday_error"),
            header=body.split("\n", 1)[0][:40] if body else None,
            sent_today=st.get("sent_today"),
            risk_worst={t: e.get("worst_state") for t, e in risk.items()},
            record=rec,
        )
        for t, e in entries.items():
            tick.observation[t] = (e.get("state"), e.get("continuous"))
            stamp = e.get("last_sent_at")
            tick.delivery[t] = (
                e.get("last_delivered_state"),
                self.labels.get(stamp, stamp) if stamp else None,
            )
        # 이번 틱 후보 = 관측된 사업군 · 급등 + 보낼 대상 보유 급락(new+worsened).
        cands = [(s.ticker, s.state, s.name) for s in (res.observed if res else [])]
        cands += [(i.ticker, i.state, i.name) for i in held_drop]
        if body:
            tick.included = {(t, s) for t, s, n in cands if n in body}
        if tick.status == "sent" and not tick.partial:
            tick.delivered = set(tick.included)
        for s in res.observed if res else []:
            if _delivered_of(entries.get(s.ticker)) != s.state:
                tick.pending.add((s.ticker, s.state))
        for i in held_drop:
            if risk.get(i.ticker, {}).get("worst_state") != i.state:
                tick.pending.add((i.ticker, i.state))
        tally = self.rig["tally"]
        if tally.exists():
            tick.tally_ticks = len(json.loads(tally.read_text("utf-8"))["ticks"])
        self.ticks.append(tick)
        return tick


def _boom_diag(res):
    """조립 뒤 `out.diagnostics.update(intraday.diagnostics)` 에서 터진다."""

    class _BoomDiag(dict):
        def keys(self):
            raise RuntimeError("OPS-02 주입: diagnostics.update 예외")

        def __iter__(self):
            raise RuntimeError("OPS-02 주입: diagnostics.update 예외")

    res.diagnostics = _BoomDiag(res.diagnostics)


def _boom_tally(res):
    """조립 뒤 회차 결과 분류(`intraday.sector.provider_down`)에서 터진다."""

    class _BoomSector:
        def __init__(self, inner):
            self._inner = inner

        def __getattr__(self, name):
            if name == "provider_down":
                raise RuntimeError("OPS-02 주입: 회차 결과 분류 예외")
            return getattr(self._inner, name)

    res.sector = _BoomSector(res.sector)


def _boom_records(res):
    """조립 뒤 관측 기록(`intraday_records`) 구성의 `set(...)` 에서 TypeError."""
    res.unevaluable = 5


_boom_diag.error = _boom_tally.error = "RuntimeError: OPS-02 주입"
_boom_records.error = "TypeError"
_INJECTIONS = [_boom_diag, _boom_records, _boom_tally]
_INJECTION_IDS = ["diagnostics", "records", "tally_classification"]


# ═══ run() 관통 — 결함 1 (잘림 · 전송 실패 · 부분 전송) ════════════════════


def test_run_section_cap_cut_changes_are_sent_next_tick(
    monkeypatch, tmp_path, market_db
):
    """구역 상한에 잘린 **상태 변화**(이미 전달된 신호)가 다음 틱에 나간다(계약 4).

    사업군 T00009: ENTRY_REVIEW(전달) → AVOID_CHASE(잘림). 보유 H00001: U5_7(전달)
    → U7_10(잘림 — 보유 급락 3종목이 「보유종목」 구역을 먼저 채운다).
    """
    sc = _Scenario("구역 상한 잘림", monkeypatch, tmp_path, market_db, holdings=NAMES)
    flat = {"H00002": -1.0, "H00003": -1.0, "H00004": -1.0}
    drops = {"H00002": -6.0, "H00003": -6.0, "H00004": -6.0}
    sc.quotes({"H00001": 5.5, **flat}, {"T00009": 2.0})
    t1 = sc.run(0, "X 전달")
    sc.quotes({"H00001": 8.0, **drops}, {f"T{i:05d}": 5.0 for i in range(10)})
    t2 = sc.run(60, "Y 잘림")
    sc.quotes({"H00001": 8.0, **drops}, {"T00009": 5.0})
    t3 = sc.run(120, "Y 지속")
    t4 = sc.run(180, "Y 지속(전달 뒤)")

    # 동작
    assert t1.status == "sent" and t1.included == {("H00001", U57), ("T00009", ER)}
    assert t2.status == "sent", t2.record
    assert ("T00009", AC) not in t2.included and ("H00001", U710) not in t2.included
    assert {("H00002", D57), ("H00003", D57), ("H00004", D57)} <= t2.included
    assert len([x for x in t2.included if x[0].startswith("T")]) == 3
    assert (t3.status, t3.reason) == ("sent", None), "잘린 상태 변화가 억제됐다"
    assert t3.included == {("T00009", AC), ("H00001", U710)}
    assert (t4.status, t4.reason) == ("skipped", "no_new_or_worsened")
    # 저장 값
    assert t2.observation["T00009"] == (AC, True)
    assert t2.observation["H00001"] == (U710, True)
    assert t2.delivery["T00009"] == (ER, "t+0"), "잘린 신호의 전달 상태가 전진했다"
    assert t2.delivery["H00001"] == (U57, "t+0")
    assert {("T00009", AC), ("H00001", U710)} <= t2.pending
    assert t2.delivered == t2.included and t2.sent_today == 2
    assert t3.delivery["T00009"] == (AC, "t+120")
    assert t3.delivery["H00001"] == (U710, "t+120")
    assert t3.delivered == t3.included and t3.pending == set()
    assert t3.sent_today == 3
    assert t4.delivery == t3.delivery and t4.sent_today == 3 and t4.pending == set()


@pytest.mark.parametrize("mode", ["telegram_send_error", "partial_delivery"])
def test_run_undelivered_change_is_sent_next_tick(
    monkeypatch, tmp_path, market_db, mode
):
    """전송 실패 · 부분 전송(대역 `sent=True, partial=True`) → 아무것도 전진하지
    않고 다음 틱에 다시 나간다(계약 5 · 6)."""
    sc = _Scenario(mode, monkeypatch, tmp_path, market_db, holdings=ONE)
    sc.quotes({"H00001": 5.5}, {"T00009": 2.0})
    t1 = sc.run(0, "X 전달")
    if mode == "telegram_send_error":
        sc.sender._sent = False
    else:
        sc.sender._partial = True
    sc.quotes({"H00001": 8.0}, {"T00009": 5.0})
    t2 = sc.run(60, f"Y {mode}")
    sc.sender._sent, sc.sender._partial = True, False
    t3 = sc.run(120, "Y 지속 · 전송 정상")
    t4 = sc.run(180, "Y 지속(전달 뒤)")

    ys = {("H00001", U710), ("T00009", AC)}
    assert t1.status == "sent"
    if mode == "telegram_send_error":
        assert (t2.status, t2.reason) == ("failed", "telegram_send_error")
    else:
        assert t2.status == "sent" and t2.partial is True
    assert t2.included == ys
    assert (t3.status, t3.reason) == ("sent", None), "전달 못 한 상태 변화가 억제됐다"
    assert t3.included == ys
    assert (t4.status, t4.reason) == ("skipped", "no_new_or_worsened")
    # 저장 값 — 실패 틱은 관측만 전진 · 전달 상태 · sent_today 불변
    assert t2.delivered == set() and t2.pending == ys
    assert t2.observation["T00009"] == (AC, True)
    assert (
        t2.delivery
        == t1.delivery
        == {
            "H00001": (U57, "t+0"),
            "T00009": (ER, "t+0"),
        }
    )
    assert t2.sent_today == 1
    assert t3.delivered == ys and t3.pending == set() and t3.sent_today == 2
    assert t3.delivery == {"H00001": (U710, "t+120"), "T00009": (AC, "t+120")}
    assert t4.delivery == t3.delivery and t4.sent_today == 2


def test_run_realistic_chunk_partial_delivery_is_resent(
    monkeypatch, tmp_path, market_db
):
    """실제형 부분 전송(분할 첫 청크 성공 · 둘째 실패) → 장중 신호 · D* 모두 미전달.

    `telegram_send` 는 `sent=False · partial=True` 를 돌려 러너가 failed 로 끝낸다.
    """
    sender = _ChunkSender(monkeypatch)
    names = {f"H0000{i}": f"긴이름{i}" + "가" * 1500 for i in (1, 2, 3)}
    sc = _Scenario(
        "실제형 부분 전송",
        monkeypatch,
        tmp_path,
        market_db,
        holdings=names,
        sender=sender,
    )
    sc.quotes({"H00001": 5.5, "H00002": -1.0, "H00003": -1.0}, {"T00009": 2.0})
    t1 = sc.run(0, "X 전달(1청크)")
    sender.fail_second = True
    y = {"H00001": 8.0, "H00002": -6.0, "H00003": -6.0}
    sc.quotes(y, {"T00009": 5.0})
    t2 = sc.run(60, "Y 둘째 청크 실패")
    sender.fail_second = False
    t3 = sc.run(120, "Y 지속 · 전송 정상")

    everything = {("H00001", U710), ("H00002", D57), ("H00003", D57), ("T00009", AC)}
    assert t1.status == "sent" and len(sender.calls[0]) < 4000
    assert (t2.status, t2.reason, t2.partial) == ("failed", "telegram_send_error", True)
    assert len(sender.calls[1]) > 4000 and t2.included == everything
    assert (t3.status, t3.reason) == ("sent", None), "부분 전송 신호가 억제됐다"
    assert t3.included == everything
    # 저장 값
    assert t2.delivered == set() and t2.pending == everything
    assert t2.delivery == {"H00001": (U57, "t+0"), "T00009": (ER, "t+0")}
    assert t2.risk_worst == {} and t2.sent_today == 1
    assert t3.delivered == everything and t3.pending == set()
    assert t3.delivery == {"H00001": (U710, "t+120"), "T00009": (AC, "t+120")}
    assert t3.risk_worst == {"H00002": D57, "H00003": D57}


def test_run_same_state_is_suppressed_after_successful_delivery(
    monkeypatch, tmp_path, market_db
):
    """성공 전달 뒤 같은 상태 지속 → 억제(정상) · 전달 상태 · sent_today 불변."""
    sc = _Scenario("성공 뒤 억제", monkeypatch, tmp_path, market_db, holdings=ONE)
    sc.quotes({"H00001": 8.0}, {"T00009": 5.0})
    t1 = sc.run(0, "Y 전달")
    t2 = sc.run(60, "Y 지속")
    t3 = sc.run(300, "Y 지속(cooldown 경과)")

    assert t1.status == "sent"
    assert t1.included == t1.delivered == {("H00001", U710), ("T00009", AC)}
    for t in (t2, t3):
        assert (t.status, t.reason) == ("skipped", "no_new_or_worsened")
        assert t.included == set() and t.pending == set()
        assert t.delivery == {"H00001": (U710, "t+0"), "T00009": (AC, "t+0")}
        assert t.sent_today == 1
        assert t.observation["T00009"] == (AC, True)


def test_run_q3_x_undelivered_y_then_x_is_suppressed_then_y_sent(
    monkeypatch, tmp_path, market_db
):
    """설계자 Q3 — 전달 X → 미전달 Y → 다시 X(지속) 억제 → 다시 Y 는 발송."""
    sc = _Scenario("Q3 X→Y→X→Y", monkeypatch, tmp_path, market_db, holdings=ONE)
    sc.quotes({"H00001": 5.5}, {"T00009": 2.0})
    t1 = sc.run(0, "X 전달")
    sc.sender._sent = False
    sc.quotes({"H00001": 8.0}, {"T00009": 5.0})
    t2 = sc.run(60, "Y 전송 실패")
    sc.sender._sent = True
    sc.quotes({"H00001": 5.5}, {"T00009": 2.0})
    t3 = sc.run(120, "다시 X")
    sc.quotes({"H00001": 8.0}, {"T00009": 5.0})
    t4 = sc.run(180, "다시 Y")

    assert t1.status == "sent" and t2.status == "failed"
    assert (t3.status, t3.reason) == (
        "skipped",
        "no_new_or_worsened",
    ), "마지막 전달 상태 X 와 같은데 다시 보냈다"
    assert (t4.status, t4.reason) == ("sent", None)
    assert t4.included == {("H00001", U710), ("T00009", AC)}
    # 저장 값
    assert t3.observation["T00009"] == (ER, True)
    assert t3.delivery == {"H00001": (U57, "t+0"), "T00009": (ER, "t+0")}
    assert t3.pending == set() and t3.sent_today == 1
    assert t4.delivery == {"H00001": (U710, "t+180"), "T00009": (AC, "t+180")}
    assert t4.sent_today == 2


# ═══ run() 관통 — 결함 2 (조립 뒤 예외 · 설계자 Q2) ═════════════════════════


@pytest.mark.parametrize("inject", _INJECTIONS, ids=_INJECTION_IDS)
def test_run_exception_after_assembly_marks_nothing_delivered(
    monkeypatch, tmp_path, market_db, inject
):
    """조립 뒤 예외 → 구 본문 발송 · 장중 관측 · 집계 · sent_today · 전달 상태 0.

    구 본문에 실린 D* 만 전송 성공 계약대로 저장된다. 다음 틱(주입 없음)에 통합
    본문이 사업군 · 급등 신호를 싣고 나간다(계약 7 · 설계자 Q2).
    """
    from app.runtime_evidence.sector_signal_state import save_sector_state

    holdings = {t: NAMES[t] for t in ("H00001", "H00002")}
    sc = _Scenario(inject.__name__, monkeypatch, tmp_path, market_db, holdings=holdings)
    save_sector_state(sc.rig["sector_state"], entries={}, today_kst=TODAY, sent_today=1)
    before = ft._hashes(sc.rig)
    sc.quotes({"H00001": -6.0, "H00002": 8.0}, {"T00009": 2.0})
    sc.inject(inject)
    t1 = sc.run(0, "조립 뒤 예외")
    after_1 = ft._hashes(sc.rig)
    t2 = sc.run(60, "주입 없음")

    # 동작
    assert t1.status == "sent" and t1.header.startswith("[보유 급락 알림]")
    assert t1.intraday_error.startswith(inject.error), t1.intraday_error
    assert t1.included == {("H00001", D57)}
    assert (t2.status, t2.reason) == ("sent", None), "한 번도 안 나간 신호가 억제됐다"
    assert t2.header.startswith("[장중 급등락]")
    assert t2.included == {("H00002", U710), ("T00009", ER)}
    # 저장 값 — 틱 1: S · 집계 파일 byte 불변 · D* 는 구 본문 기준 저장
    assert after_1 == before, "구 본문이 나갔는데 사업군 상태·집계를 썼다"
    assert "intraday_tally_outcome" not in t1.record
    assert "intraday_state_saved" not in t1.record
    assert t1.observation == {} and t1.delivery == {} and t1.sent_today == 1
    assert t1.delivered == {("H00001", D57)} and t1.risk_worst == {"H00001": D57}
    assert t1.pending == {("H00002", U710), ("T00009", ER)}
    assert t1.tally_ticks == 0
    # 틱 2: 이번에는 실제로 실린 것만 전달 · sent_today 전진 · 집계 1틱
    assert t2.delivered == t2.included and t2.pending == set()
    assert t2.delivery == {"H00002": (U710, "t+60"), "T00009": (ER, "t+60")}
    assert t2.sent_today == 2 and t2.tally_ticks == 1


@pytest.mark.parametrize("inject", _INJECTIONS, ids=_INJECTION_IDS)
@pytest.mark.parametrize(
    "sent, partial",
    [(False, False), (True, True)],
    ids=["telegram_failure", "partial_delivery"],
)
def test_run_exception_after_assembly_with_failed_send_saves_no_d_star(
    monkeypatch, tmp_path, market_db, inject, sent, partial
):
    """조립 뒤 예외 + 구 본문 전송 실패 · 부분 전송 → D* 도 저장하지 않는다(Q2).

    장중 관측 · 집계 파일도 byte 불변이다(실패 회차라도 조립 뒤 예외 회차는 쓰지 않는다).
    """
    holdings = {t: NAMES[t] for t in ("H00001", "H00002")}
    sc = _Scenario(
        "예외+실패",
        monkeypatch,
        tmp_path,
        market_db,
        holdings=holdings,
        sender=_Sender(sent=sent, partial=partial),
    )
    before = ft._hashes(sc.rig)
    sc.quotes({"H00001": -6.0, "H00002": 8.0}, {"T00009": 2.0})
    sc.inject(inject)
    t1 = sc.run(0, "조립 뒤 예외 + 전송 실패")
    assert t1.header.startswith("[보유 급락 알림]") and t1.included == {("H00001", D57)}
    assert t1.delivered == set()
    assert ops01._risk_entries(sc.rig) is None, "전송 실패인데 D* 를 저장했다"
    assert ft._hashes(sc.rig) == before, "조립 뒤 예외 회차가 관측·집계를 썼다"
    assert t1.pending == {("H00001", D57), ("H00002", U710), ("T00009", ER)}


# ═══ 단위 — 전달 필드 쓰기 · 보존 · 구파일 규칙 · 억제표 ═══════════════════


def _sig(ticker, state, pct=0.0):
    from app.runtime_evidence.sector_signal import SectorSignal

    return SectorSignal("S", ticker, f"n{ticker}", state, pct)


def _now():
    from app.runtime_evidence.sector_signal_state import KST

    return datetime(2026, 9, 28, 10, 30, tzinfo=KST)


def test_unit_last_delivered_state_written_only_for_sent():
    from app.runtime_evidence.sector_signal_state import (
        LoadedSectorState,
        merge_sector_entries,
    )

    t0 = (_now() - timedelta(minutes=60)).isoformat()
    prev = LoadedSectorState(
        entries={
            "T1": {"state": ER, "last_delivered_state": ER, "last_sent_at": t0},
            "T2": {"state": ER, "last_delivered_state": ER, "last_sent_at": t0},
        },
        fallback=False,
    )
    merged = merge_sector_entries(
        sent=[_sig("T1", AC)],
        previous=prev,
        now_kst=_now(),
        observed=[_sig("T1", AC), _sig("T2", AC), _sig("T3", AC)],
    )
    assert merged["T1"]["last_delivered_state"] == AC
    assert merged["T1"]["last_sent_at"] == _now().isoformat()
    # 관측만 된 T2(잘림) — 관측은 전진, 전달은 그대로
    assert merged["T2"]["state"] == AC and merged["T2"]["continuous"] is True
    assert merged["T2"]["last_delivered_state"] == ER
    assert merged["T2"]["last_sent_at"] == t0
    # 한 번도 안 나간 T3 — 전달 필드를 만들지 않는다
    assert "last_delivered_state" not in merged["T3"]
    assert "last_sent_at" not in merged["T3"]


def test_unit_observation_paths_preserve_delivered_state(tmp_path):
    """관측 저장 · 부재 표시 · 평가 불가 — 전달 상태를 바꾸지 않는다.

    구파일 entry(필드 없음 · `last_sent_at` 있음)는 `state` 를 덮기 전에 **추정값
    그대로** 필드로 옮긴다(설계자 Q1 '다음 정상 저장 때 필드를 추가').
    """
    from app.runtime_evidence.sector_signal_state import (
        load_sector_state,
        save_observation,
        save_sector_state,
    )

    t0 = (_now() - timedelta(minutes=60)).isoformat()
    delivered = {"last_delivered_state": ER, "last_sent_at": t0}
    p = tmp_path / "s.json"
    save_sector_state(
        p,
        entries={
            "OBS": {"state": ER, "continuous": True, **delivered},
            "GONE": {"state": ER, "continuous": True, **delivered},
            "BLIND": {"state": ER, "continuous": True, "sector_key": "S", **delivered},
            "LEGACY": {"state": ER, "continuous": True, "last_sent_at": t0},
            "NEVER": {"state": ER, "continuous": True},
        },
        today_kst=TODAY,
        sent_today=2,
    )
    blind_before = load_sector_state(p, today_kst=TODAY).entries["BLIND"]
    save_observation(
        p,
        observed=[_sig("OBS", AC), _sig("LEGACY", AC), _sig("NEVER", AC)],
        today_kst=TODAY,
        unevaluable={"BLIND"},
    )
    loaded = load_sector_state(p, today_kst=TODAY)
    e = loaded.entries
    assert loaded.sent_today == 2, "관측 저장이 sent_today 를 올렸다"
    assert e["OBS"]["state"] == AC and e["OBS"]["last_delivered_state"] == ER
    assert e["OBS"]["last_sent_at"] == t0
    assert e["GONE"]["continuous"] is False
    assert e["GONE"]["last_delivered_state"] == ER and e["GONE"]["last_sent_at"] == t0
    assert e["BLIND"] == blind_before, "평가 불가 entry 를 바꿨다"
    # 구파일 entry — 덮기 전 추정 전달 상태(ER)를 그대로 옮겼다. 관측 AC 가 전달
    # 상태로 읽히지 않는다(리뷰 실측 · 장중 배포 당일 전환 구간).
    assert e["LEGACY"]["last_delivered_state"] == ER
    assert e["LEGACY"]["state"] == AC and e["LEGACY"]["last_sent_at"] == t0
    assert "last_delivered_state" not in e["NEVER"]
    assert "last_sent_at" not in e["NEVER"]


def test_unit_legacy_entry_pinned_on_success_path_then_cut_change_is_sent():
    """구파일 전환 — 전송 성공 저장(merge)의 관측 루프도 덮기 전에 추정값을 옮긴다.

    리뷰 재현: 구파일 T2{ER · last_sent_at} 가 AC 로 관측되고 구역 상한에 잘린 채
    다른 신호가 전송 성공 → 예전에는 필드 없이 `state=AC` 로 덮여 다음 틱 AC 가
    '전달 상태' 로 억제됐다.
    """
    from app.runtime_evidence.sector_signal_state import (
        LoadedSectorState,
        compute_sector_changes,
        merge_sector_entries,
    )

    t0 = (_now() - timedelta(minutes=60)).isoformat()
    prev = LoadedSectorState(
        entries={"T2": {"state": ER, "continuous": True, "last_sent_at": t0}},
        fallback=False,
    )
    merged = merge_sector_entries(
        sent=[_sig("T1", AC)],
        previous=prev,
        now_kst=_now(),
        observed=[_sig("T1", AC), _sig("T2", AC)],
    )
    assert merged["T2"]["last_delivered_state"] == ER
    assert merged["T2"]["state"] == AC and merged["T2"]["last_sent_at"] == t0
    ch = compute_sector_changes(
        signals=[_sig("T2", AC)],
        previous=LoadedSectorState(entries=merged, fallback=False),
        now_kst=_now() + timedelta(minutes=10),
        cooldown_minutes=120,
    )
    assert [s.ticker for s in ch.send] == ["T2"], "잘린 상태 변화가 억제됐다"


@pytest.mark.parametrize(
    "continuous, delivered, observed, expected",
    [
        (False, ER, AC, False),  # 회복 뒤 미전달 Y — 회복 기록 유지(리뷰 지적)
        (False, ER, ER, True),  # 회복 뒤 전달 상태로 재진입 — 예전과 같다
        (True, ER, AC, True),  # 회복 없이 Y(Q3 경로) — 예전과 같다
        (False, None, AC, True),  # 전달 이력 없음 — 예전과 같다
        (None, None, AC, True),  # 새 entry — 예전과 같다
    ],
)
def test_unit_observation_keeps_recovery_until_delivered_state_returns(
    continuous, delivered, observed, expected
):
    """`continuous` — 회복 뒤 **전달 상태와 다른** 관측은 회복 기록을 지우지 않는다."""
    from app.runtime_evidence.sector_signal_state import (
        LoadedSectorState,
        merge_sector_entries,
    )

    row = {"state": delivered or ER}
    if continuous is not None:
        row["continuous"] = continuous
    if delivered is not None:
        row["last_delivered_state"] = delivered
        row["last_sent_at"] = (_now() - timedelta(minutes=60)).isoformat()
    merged = merge_sector_entries(
        sent=[],
        previous=LoadedSectorState(entries={"T1": row}, fallback=False),
        now_kst=_now(),
        observed=[_sig("T1", observed)],
    )
    assert merged["T1"]["state"] == observed
    assert merged["T1"]["continuous"] is expected


def test_run_recovery_then_undelivered_y_then_x_follows_cooldown_rule(
    monkeypatch, tmp_path, market_db
):
    """X 전달 → 회복 → 미전달 Y → X 재진입 = **회복 후 재진입**(설계 §5 cooldown 규칙).

    리뷰 지적: 미전달 Y 관측이 회복 기록을 지워, 돌아온 X 가 cooldown 이 지나도
    '지속 중' 으로 억제됐다. 전달 상태 기준으로 X 는 회복 뒤 재진입이다.
    """
    sc = _Scenario(
        "회복 → 미전달 Y → X", monkeypatch, tmp_path, market_db, holdings=ONE
    )
    sc.quotes({"H00001": 5.5}, {"T00009": 2.0})
    t1 = sc.run(0, "X 전달")
    sc.quotes({"H00001": 5.5}, {"T00009": 0.0})
    t2 = sc.run(60, "X 회복(임계 밖)")
    sc.sender._sent = False
    sc.quotes({"H00001": 5.5}, {"T00009": 5.0})
    t3 = sc.run(120, "Y 전송 실패")
    sc.sender._sent = True
    sc.quotes({"H00001": 5.5}, {"T00009": 2.0})
    t4 = sc.run(300, "X 재진입(cooldown 경과)")
    t5 = sc.run(360, "X 지속(전달 뒤)")

    assert t1.status == "sent" and t1.included == {("H00001", U57), ("T00009", ER)}
    assert (t2.status, t2.reason) == ("skipped", "no_new_or_worsened")
    assert t2.observation["T00009"] == (ER, False)
    assert t3.status == "failed" and t3.observation["T00009"] == (AC, False)
    assert t3.delivery["T00009"] == (ER, "t+0")
    assert (t4.status, t4.reason) == ("sent", None), "회복 뒤 재진입이 억제됐다"
    assert t4.included == {("T00009", ER)}
    assert t4.delivery["T00009"] == (ER, "t+300") and t4.sent_today == 2
    assert (t5.status, t5.reason) == ("skipped", "no_new_or_worsened")


def test_run_recovery_then_undelivered_y_then_x_within_cooldown_is_suppressed(
    monkeypatch, tmp_path, market_db
):
    """같은 모양에서 cooldown 이내 재진입은 억제 · 그 뒤 지속도 억제(설계 §5 그대로)."""
    sc = _Scenario("회복 → Y → X(이내)", monkeypatch, tmp_path, market_db, holdings=ONE)
    sc.quotes({"H00001": 5.5}, {"T00009": 2.0})
    t1 = sc.run(0, "X 전달")
    sc.quotes({"H00001": 5.5}, {"T00009": 0.0})
    sc.run(30, "X 회복")
    sc.sender._sent = False
    sc.quotes({"H00001": 5.5}, {"T00009": 5.0})
    t3 = sc.run(60, "Y 전송 실패")
    sc.sender._sent = True
    sc.quotes({"H00001": 5.5}, {"T00009": 2.0})
    t4 = sc.run(90, "X 재진입(cooldown 이내)")
    t5 = sc.run(300, "X 지속(cooldown 경과)")

    assert t1.status == "sent" and t3.status == "failed"
    for t in (t4, t5):
        assert (t.status, t.reason) == ("skipped", "no_new_or_worsened")
        assert t.delivery["T00009"] == (ER, "t+0") and t.sent_today == 1
    assert t4.observation["T00009"] == (ER, True)


def test_unit_mark_absent_entries_copies_delivered_fields():
    from app.runtime_evidence.sector_signal_state import (
        LoadedSectorState,
        mark_absent_entries,
    )

    row = {
        "state": ER,
        "continuous": True,
        "last_delivered_state": ER,
        "last_sent_at": "x",
    }
    prev = LoadedSectorState(entries={"A": dict(row), "B": dict(row)}, fallback=False)
    out = mark_absent_entries(observed=[], previous=prev, unevaluable={"B"})
    assert out["A"] == {**row, "continuous": False}
    assert out["B"] == row


@pytest.mark.parametrize(
    "entry, expected",
    [
        ({"state": AC, "last_delivered_state": ER, "last_sent_at": "t"}, ER),
        ({"state": AC, "last_sent_at": "2026-09-28T09:30:00+09:00"}, AC),
        ({"state": AC, "continuous": True}, None),
        ({"state": AC, "last_delivered_state": ER}, ER),
        (None, None),
        ("손상", None),
    ],
    ids=[
        "field_present",
        "legacy_with_last_sent_at",
        "legacy_never_sent",
        "field_present_without_last",
        "no_entry",
        "not_a_dict",
    ],
)
def test_unit_legacy_rules(entry, expected):
    """설계자 Q1 구파일 규칙 — 필드 있음 · 없음+last_sent_at · 없음(3 + 손상 3)."""
    from app.runtime_evidence.sector_signal_state import last_delivered_state

    assert last_delivered_state(entry) == expected
    assert _delivered_of(entry) == expected  # 테스트 명세와 운영 helper 가 같다


_T = {"old": -200, "recent": -10}

# (라벨, entry, 현재 신호 상태, 발송?) — entry 의 last 는 분(now 기준) · 문자열은 손상값
_TABLE = [
    ("prev 없음", None, AC, True),
    ("전달 이력 없음 · 지속", {"state": AC, "continuous": True}, AC, True),
    (
        "전달 X · 관측 Y · 현재 Y · 지속 (결함 1)",
        {"state": AC, "d": ER, "last": "old", "continuous": True},
        AC,
        True,
    ),
    (
        "전달 X · 관측 Y · 현재 X · 지속 (Q3)",
        {"state": AC, "d": ER, "last": "old", "continuous": True},
        ER,
        False,
    ),
    (
        "전달 X · 현재 X · 지속",
        {"state": ER, "d": ER, "last": "old", "continuous": True},
        ER,
        False,
    ),
    (
        "전달 X · 회복 · cooldown 경과",
        {"state": ER, "d": ER, "last": "old", "continuous": False},
        ER,
        True,
    ),
    (
        "전달 X · 회복 · cooldown 이내",
        {"state": ER, "d": ER, "last": "recent", "continuous": False},
        ER,
        False,
    ),
    (
        "전달 X · 현재 Y · cooldown 이내(상태 변화)",
        {"state": ER, "d": ER, "last": "recent", "continuous": False},
        AC,
        True,
    ),
    (
        "구파일 · 같은 상태 · 지속",
        {"state": ER, "last": "old", "continuous": True},
        ER,
        False,
    ),
    ("구파일 · 다른 상태", {"state": ER, "last": "old", "continuous": True}, AC, True),
    (
        "last 손상 · 필드 있음",
        {"state": ER, "d": ER, "last": "쓰레기", "continuous": True},
        ER,
        True,
    ),
    (
        "필드 손상값(비문자열)",
        {"state": ER, "d": 5, "last": "old", "continuous": True},
        ER,
        True,
    ),
]


@pytest.mark.parametrize(
    "label, spec, current, should_send", _TABLE, ids=[r[0] for r in _TABLE]
)
def test_unit_suppression_table(label, spec, current, should_send):
    """억제 판정 = 마지막 **전달** 상태 기준 · 회복 cooldown 규칙은 그대로."""
    from app.runtime_evidence.sector_signal_state import (
        LoadedSectorState,
        compute_sector_changes,
    )

    entries = {}
    if spec is not None:
        e = {"state": spec["state"], "continuous": spec["continuous"]}
        if "d" in spec:
            e["last_delivered_state"] = spec["d"]
        if "last" in spec:
            raw = spec["last"]
            e["last_sent_at"] = (
                (_now() + timedelta(minutes=_T[raw])).isoformat() if raw in _T else raw
            )
        entries["T1"] = e
    ch = compute_sector_changes(
        signals=[_sig("T1", current)],
        previous=LoadedSectorState(entries=entries, fallback=False),
        now_kst=_now(),
        cooldown_minutes=120,
    )
    assert bool(ch.send) is should_send, label
    assert bool(ch.suppressed) is (not should_send), label


def test_unit_schema_version_unchanged_and_round_trip(tmp_path):
    """필드를 더해도 `sector_signal_state.v1` — 올리면 sent_today 가 0 으로 읽힌다."""
    from app.runtime_evidence import sector_signal_state as sss

    assert sss.SCHEMA_VERSION == "sector_signal_state.v1"
    assert sss.DELIVERED_STATE_KEY == "last_delivered_state"
    p = tmp_path / "s.json"
    row = {"state": AC, "last_delivered_state": ER, "last_sent_at": _now().isoformat()}
    sss.save_sector_state(p, entries={"T1": row}, today_kst=TODAY, sent_today=3)
    body = json.loads(p.read_text(encoding="utf-8"))
    assert body["schema_version"] == "sector_signal_state.v1"
    loaded = sss.load_sector_state(p, today_kst=TODAY)
    assert loaded.comparable and loaded.sent_today == 3
    assert loaded.entries["T1"] == row


# ═══ 회귀 — 상한 · Gate · 정책 비활성 ══════════════════════════════════════


def test_regression_daily_cap_still_blocks_pending_change(
    monkeypatch, tmp_path, market_db
):
    """일일 상한 4 그대로 — 미전달 상태 변화도 상한을 넘지 못한다(계약 10)."""
    from app.runtime_evidence.sector_signal_state import save_sector_state

    sc = _Scenario("일일 상한", monkeypatch, tmp_path, market_db, holdings=ONE)
    save_sector_state(sc.rig["sector_state"], entries={}, today_kst=TODAY, sent_today=3)
    sc.quotes({"H00001": 5.5}, {"T00009": 2.0})
    t1 = sc.run(0, "4번째 발송")
    sc.quotes({"H00001": 8.0}, {"T00009": 5.0})
    t2 = sc.run(60, "상한 도달 · Y")
    assert t1.status == "sent" and t1.sent_today == 4
    assert t2.reason == "intraday_daily_cap_reached" and t2.included == set()
    assert len(sc.sender.calls) == 1
    assert t2.sent_today == 4
    assert t2.delivery == {"H00001": (U57, "t+0"), "T00009": (ER, "t+0")}
    assert t2.pending == {("H00001", U710), ("T00009", AC)}


def test_regression_section_cap_three_and_one_message_per_tick(
    monkeypatch, tmp_path, market_db
):
    """구역 상한 3 그대로 — 10개 중 본문 3개만 전달 필드 · 나머지 7개는 다음 틱 후보."""
    sc = _Scenario("구역 상한 3", monkeypatch, tmp_path, market_db, holdings=ONE)
    sc.quotes({"H00001": -1.0}, {f"T{i:05d}": 5.0 for i in range(10)})
    t1 = sc.run(0, "AVOID_CHASE 10")
    t2 = sc.run(60, "그대로")
    assert len(sc.sender.calls) == 2
    assert len(t1.included) == 3 and t1.delivered == t1.included
    stamped = {t for t, (d, _) in t1.delivery.items() if d == AC}
    assert stamped == {t for t, _ in t1.included}
    assert len(t1.pending) == 7
    assert len(t2.included) == 3 and not (t2.included & t1.included)
    assert len(t2.pending) == 4


def test_regression_gates_write_nothing_and_pending_survives(
    monkeypatch, tmp_path, market_db
):
    """dry-run · flag-off · duplicate 회차는 S · 집계 · 위험 파일 불변(D3).

    그 뒤 정상 틱에 미전달 상태 변화가 그대로 나간다.
    """
    sc = _Scenario("Gate", monkeypatch, tmp_path, market_db, holdings=ONE)
    risk = sc.rig["runner"].HOLDINGS_RISK_STATE_PATH

    def snap():
        return ft._hashes(sc.rig), risk.read_bytes() if risk.exists() else None

    sc.quotes({"H00001": 5.5}, {"T00009": 2.0})
    assert sc.run(0, "X 전달").status == "sent"
    before = snap()
    sc.quotes({"H00001": 8.0}, {"T00009": 5.0})
    assert sc.run(0, "dry-run", mode="dry-run").status == "dry_run_success"
    assert snap() == before, "dry-run 이 상태를 바꿨다"
    monkeypatch.setenv("PUSH_AUTOSEND_HOLDINGS_RISK_ALERT_ENABLED", "false")
    assert sc.run(0, "flag-off").reason == "push_kind_disabled"
    assert snap() == before, "flag-off 가 상태를 바꿨다"
    monkeypatch.setenv("PUSH_AUTOSEND_HOLDINGS_RISK_ALERT_ENABLED", "true")
    assert sc.run(0, "같은 분 재실행").reason == "duplicate_runtime"
    assert snap() == before, "duplicate 가 상태를 바꿨다"
    t = sc.run(60, "정상 틱")
    assert (t.status, t.included) == ("sent", {("H00001", U710), ("T00009", AC)})
    assert len(sc.sender.calls) == 2


def test_regression_policy_disabled_writes_no_sector_state(
    monkeypatch, tmp_path, market_db
):
    """정책 비활성 → 구 본문 · S 파일 · 집계 파일 생성 0."""
    sc = _Scenario("정책 비활성", monkeypatch, tmp_path, market_db, holdings=ONE)
    sc.rig["policy"] = ft._policy(enabled=False)
    sc.quotes({"H00001": -6.0}, {"T00009": 5.0})
    t = sc.run(0, "구 본문")
    assert t.status == "sent" and t.header.startswith("[보유 급락 알림]")
    assert ft._hashes(sc.rig) == (None, None)
    assert t.risk_worst == {"H00001": D57}
