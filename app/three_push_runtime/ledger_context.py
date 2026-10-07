"""POC5-01B — 러너 원장 문맥: 활성 판정 · STARTED · 종료 확정 · 미포착 예외 경계.

PLAN `docs/ai_plan/POC5/POC5-01B_OPERATIONAL_DECISION_EVENT_LEDGER_PLAN_V1.md`
§1-1 · §1-2 · §1-7 · §2-3 ~ §2-5.

```text
활성        DECISION_LEDGER_ENABLED=true(OCI .env · 기존 역할 표식 없음) AND mode=send AND 운영 3종
            — 아니면 no-op(파일 open · mkdir · chmod 0회). PC · dry-run · spike = 0행
진입        new_run_record 직후 begin() — event_id 발급 · meta 1회 기록 · STARTED INSERT
종료        _finish 안 finish_run 뒤 finalize() — item · delivery · FINALIZED 를 한 트랜잭션으로
예외        @boundary — run 밖으로 나가는 예외는 failed 확정을 시도한 뒤 같은 예외를 다시 올린다
            (종류 · 메시지 · exit code 동일 · traceback 에 경계 frame 1개 추가 — 원장이 켜진
            실행의 insert_status 예외는 wrap_insert_status frame 1개 더)
실패        원장 쓰기 실패는 PUSH 결과 · 예외 전파를 바꾸지 않는다. 기존 logger 에 event_id ·
            단계 · kind · 예외 종류만 남긴다(본문 · 비밀값 없음)
record      키를 더하지 않는다(DB · JSONL · stdout 불변) — 값은 이 문맥 객체에만 싣는다
```
"""

from __future__ import annotations

import functools
import hashlib
import os
import subprocess
import uuid
from contextvars import ContextVar
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from app.three_push_runner_common import PROJECT_ROOT, env_bool
from app.three_push_runtime import ledger_items as items_mod
from app.three_push_runtime import ledger_market as market_mod
from app.three_push_runtime import ledger_store as store

FLAG_ENV = "DECISION_LEDGER_ENABLED"
# kind 별 계약 버전(Q12 · 01B 첫 판). legacy 라벨(POC5-00 §1-3 OLD · NEW_V1/V2 · H0 ~ H2 · R1/R2)은
# 진단 전용이라 여기에 두지 않는다. 계약이 바뀌면 이 값을 올린다.
CONTRACT_VERSIONS = {
    "market_briefing": "market_briefing.v1",
    "holdings_briefing": "holdings_briefing.v1",
    "holdings_risk_alert": "holdings_risk_alert.v1",
}
# 예정 시각(Q-A · cron 과 같은 값 · cron 을 바꾸면 같이 고친다). 보유는 slot 표를 쓴다.
MARKET_TIMES = ("08:30",)
INTRADAY_TICKS = ("09:30", "10:30", "11:30", "12:30", "13:30", "14:30", "15:20")
# 한국 거래일 캘린더(호출 때 읽는다 · conftest 가 tmp 로 바꾼다).
CALENDAR_DIR = Path("state/market_meta")

_CURRENT: ContextVar[Optional["LedgerRun"]] = ContextVar(
    "decision_ledger_run", default=None
)


def is_active(push_kind: str, mode: str) -> bool:
    return mode == "send" and push_kind in CONTRACT_VERSIONS and env_bool(FLAG_ENV)


def schedule_for(
    push_kind: str, runtime_kst: str, slot_id: Optional[str]
) -> tuple[int, Optional[str]]:
    """`(off_schedule, 예정 시각)` — 평일 · 예정 HH:MM 이면 0. cron 이 1분 넘게 늦으면 1(한계)."""
    hhmm = (runtime_kst or "")[11:16]
    try:
        weekday = date.fromisoformat((runtime_kst or "")[:10]).weekday() < 5
    except ValueError:
        return 1, None
    if push_kind == "holdings_briefing":
        from app.runtime_evidence.holdings_selection_flow import SLOT_TIME_LABEL

        times: tuple[str, ...] = tuple(
            t for t in (SLOT_TIME_LABEL.get(slot_id or ""),) if t
        )
    elif push_kind == "market_briefing":
        times = MARKET_TIMES
    else:
        times = INTRADAY_TICKS
    matched = hhmm if hhmm in times else None
    return (0 if weekday and matched else 1), matched


def _git_head() -> Optional[str]:
    """배포 근거 커밋. 실패하면 None — 키를 비워 다음 실행에서 다시 시도한다(Q-F)."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    head = (out.stdout or "").strip()
    return head if out.returncode == 0 and len(head) == 40 else None


def _new_event_id() -> str:
    return f"ev_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}"


def _secret_in(text: str) -> bool:
    for key in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"):
        val = os.environ.get(key)
        if val and str(val) in text:
            return True
    return False


class LedgerRun:
    """한 실행의 원장 문맥. 비활성이면 모든 메서드가 아무것도 하지 않는다."""

    def __init__(self, *, active: bool, push_kind: str, mode: str, logger: Any) -> None:
        self.active = active
        self.push_kind, self.mode, self.logger = push_kind, mode, logger
        self.event_id: Optional[str] = None
        self.record: Optional[dict[str, Any]] = None
        self.asm: Any = None
        self.sent_text: Optional[str] = None
        self.run_id: Any = None
        self.done = False
        self.base: dict[str, Any] = {}

    # ── 단계 실패 기록 ─────────────────────────────────────────────────────────

    def _fail(self, stage: str, e: BaseException) -> None:
        self.active = False  # 그 실행의 원장 쓰기 중단(고아 행 방지 · 보정 1)
        if self.logger is not None:
            try:
                self.logger.warning(
                    "decision ledger %s 실패: event_id=%s kind=%s err=%s",
                    stage,
                    self.event_id,
                    self.push_kind,
                    type(e).__name__,
                )
            except Exception:  # noqa: BLE001
                pass

    # ── 진입 ────────────────────────────────────────────────────────────────

    def start(self, record: dict[str, Any], *, slot_id: Optional[str]) -> None:
        self.record = record
        if not self.active:
            return
        try:
            runtime_kst = record.get("runtime_kst") or ""
            off, expected = schedule_for(self.push_kind, runtime_kst, slot_id)
            self.event_id = _new_event_id()
            self.base = {
                "event_id": self.event_id,
                "push_kind": self.push_kind,
                "contract_version": CONTRACT_VERSIONS[self.push_kind],
                "slot_id": slot_id,
                "tick": (
                    runtime_kst[11:16]
                    if self.push_kind == "holdings_risk_alert"
                    else None
                ),
                "runtime_kst": runtime_kst,
                "runtime_date_kst": record.get("runtime_date_kst"),
                "mode": self.mode,
                "started_at": record.get("started_at"),
                "off_schedule": off,
                "schedule_expected": expected,
            }
            con = store.connect()
            try:
                self._meta_once(con, off)
                store.insert_started(con, self.base)
            finally:
                con.close()
        except Exception as e:  # noqa: BLE001 - 원장이 PUSH 를 막지 않는다
            self._fail("start", e)

    def _meta_once(self, con: Any, off: int) -> None:
        store.meta_put_once(con, "schema_version", store.SCHEMA_VERSION)
        store.meta_put_once(
            con, "first_active_at", self.base["started_at"] or store.now_utc()
        )
        version = CONTRACT_VERSIONS[self.push_kind]
        store.meta_put_once(
            con, f"contract_version.{self.push_kind}.{version}", version
        )
        if store.meta_get(con, "deploy_commit") is None:
            head = _git_head()
            if head:
                store.meta_put_once(con, "deploy_commit", head)
        day = self.base.get("runtime_date_kst")
        if not off and day and store.meta_get(con, "primary_start_date") is None:
            from app import trading_day_lag

            if trading_day_lag.is_trading_day(day, calendar_dir=CALENDAR_DIR):
                store.meta_put_once(con, "primary_start_date", day)

    # ── 실행 중 운반(속성만 · I/O · 계산 없음) ──────────────────────────────────

    def attach_assembly(self, asm: Any) -> None:
        self.asm = asm

    def attach_send(self, text: str) -> None:
        self.sent_text = text

    def wrap_insert_status(self, fn: Callable[[dict[str, Any]], Any]) -> Callable:
        if not self.active:
            return fn  # 비활성이면 감싸지 않는다(traceback frame 추가 0)

        def _wrapped(rec: dict[str, Any]) -> Any:
            rid = fn(rec)
            self.run_id = rid
            return rid

        return _wrapped

    # ── 종료 ────────────────────────────────────────────────────────────────

    def finalize(self, rec: dict[str, Any]) -> None:
        self._finalize(
            status=rec.get("status"),
            reason=rec.get("reason"),
            error=rec.get("error"),
            finished_at=rec.get("finished_at"),
        )

    def finalize_uncaught(self, e: BaseException) -> None:
        self._finalize(
            status="failed",
            reason="uncaught_exception",
            error=type(e).__name__,
            finished_at=store.now_utc(),
        )

    def _finalize(
        self, *, status: Any, reason: Any, error: Any, finished_at: Any
    ) -> None:
        if not self.active or self.done or self.event_id is None:
            return
        self.done = True
        rec = self.record or {}
        try:
            raw_items = self._items(rec)
            run = dict(self.base)
            run.update(
                status=status,
                reason=reason,
                error=error,
                finished_at=finished_at,
                run_id=self.run_id,
                param_id=rec.get("param_id"),
                slot_id=rec.get("slot_id") or self.base.get("slot_id"),
                input_basis_date=self._input_basis(rec),
                config_version_id=self._config_version(),
            )
            delivery = self._delivery(rec)
            con = store.connect()
            try:
                start = store.meta_get(con, "primary_start_date")
                day = run.get("runtime_date_kst") or ""
                run["cohort"] = (
                    "PRIMARY_LIVE" if start and day >= start else "LEGACY_DIAGNOSTIC"
                )

                def _rows(c: Any) -> list[dict[str, Any]]:
                    if self.push_kind == "market_briefing" and raw_items:
                        run["tags_json"] = _json(
                            market_mod.market_tags(
                                c,
                                rec,
                                raw_items,
                                runtime_date_kst=day,
                                calendar_dir=CALENDAR_DIR,
                            )
                        )
                    return items_mod.apply_transitions(
                        c, raw_items, push_kind=self.push_kind, runtime_date_kst=day
                    )

                store.finalize(con, self.event_id, run, _rows, delivery)
            finally:
                con.close()
        except Exception as e:  # noqa: BLE001 - STARTED 가 남으면 그것이 gap 이다
            self._fail("finalize", e)

    def _items(self, rec: dict[str, Any]) -> list[dict[str, Any]]:
        asm = self.asm
        if asm is None:
            return []  # 조립 전에 끝났다(preflight · 가격 조회 실패)
        if self.push_kind == "holdings_briefing":
            return items_mod.holdings_briefing_items(asm.holdings_outcome)
        if self.push_kind == "holdings_risk_alert":
            return items_mod.risk_items(
                asm.risk_assembly, intraday_isolated=bool(rec.get("intraday_error"))
            )
        return market_mod.market_items(asm.market_outcome, rec)

    def _input_basis(self, rec: dict[str, Any]) -> Optional[str]:
        if self.push_kind == "market_briefing":
            return rec.get("sp500_asof")
        if self.push_kind == "holdings_briefing":
            return rec.get("holdings_axis_last_trading_day")
        return rec.get("runtime_date_kst")

    def _config_version(self) -> Optional[str]:
        ra = getattr(self.asm, "risk_assembly", None) if self.asm is not None else None
        intraday = getattr(ra, "intraday_eval", None) if ra is not None else None
        value = getattr(intraday, "config_version_id", None) if intraday else None
        return str(value) if value is not None else None

    def _delivery(self, rec: dict[str, Any]) -> dict[str, Any]:
        attempted = bool(rec.get("telegram_attempted"))
        if not attempted:
            status = "skipped"
        elif rec.get("telegram_sent"):
            status = "sent"
        elif rec.get("partial_delivery"):
            status = "partial"
        else:
            status = "failed"
        text = self.sent_text if attempted else None
        out: dict[str, Any] = {
            "delivery_status": status,
            "telegram_sent": 1 if rec.get("telegram_sent") else 0,
            "planned_chunk_count": None,
            "body_text": None,
            "body_sha256": None,
            "body_withheld": 0,
        }
        if text is None:
            return out
        from app.three_push_runner_common import _split_message_for_telegram

        # 계획 chunk 수 — 같은 본문을 같은 순수 함수로 나눈 수다. 실제로 전달된 chunk 수는
        # 알 수 없다(telegram_send 가 돌려주지 않는다 · 설계자 보정 2).
        out["planned_chunk_count"] = len(_split_message_for_telegram(text))
        out["body_sha256"] = hashlib.sha256(text.encode("utf-8")).hexdigest()
        if _secret_in(text):
            out["body_withheld"] = 1  # 본문만 보류 · SHA 는 남긴다(Q9 · AC 8)
        else:
            out["body_text"] = text
        return out


def _json(value: Any) -> str:
    import json

    return json.dumps(value, ensure_ascii=False, default=str)


def begin(
    record: dict[str, Any],
    *,
    push_kind: str,
    mode: str,
    slot_id: Optional[str],
    logger: Any,
) -> LedgerRun:
    """실행 진입. 예외를 올리지 않는다."""
    try:
        run = LedgerRun(
            active=is_active(push_kind, mode),
            push_kind=push_kind,
            mode=mode,
            logger=logger,
        )
    except Exception:  # noqa: BLE001
        run = LedgerRun(active=False, push_kind=push_kind, mode=mode, logger=logger)
    _CURRENT.set(run)
    run.start(record, slot_id=slot_id)
    return run


def boundary(fn: Callable[..., Any]) -> Callable[..., Any]:
    """러너 `run` 의 최외곽 경계. 예외 종류 · 메시지 · 전파 · exit code 는 그대로다.

    traceback 에는 이 경계 frame 1개(`_wrapped`)가 더 찍힌다(원장 활성 여부와 무관). 원장이
    켜진 실행에서 `insert_status` 가 예외를 내면 `wrap_insert_status` frame 1개가 더 찍힌다.
    """

    @functools.wraps(fn)
    def _wrapped(*args: Any, **kwargs: Any) -> Any:
        token = _CURRENT.set(None)
        try:
            return fn(*args, **kwargs)
        except BaseException as e:
            run = _CURRENT.get()
            if run is not None:
                try:
                    run.finalize_uncaught(e)
                except Exception:  # noqa: BLE001
                    pass
            raise
        finally:
            _CURRENT.reset(token)

    return _wrapped


__all__ = [
    "CALENDAR_DIR",
    "CONTRACT_VERSIONS",
    "FLAG_ENV",
    "INTRADAY_TICKS",
    "MARKET_TIMES",
    "LedgerRun",
    "begin",
    "boundary",
    "is_active",
    "schedule_for",
]
