"""POC3-02D-OPS-04 항목 1 — 보유 코스피 개별주 KRX 공식 종가 채우기(KRX 단계의 곁 작업).

설계자 Q1 (a) · 사용자 승인 2건(2026-10-04 — 시장 DB 표 1개 · `sto/stk_bydd_trd`) · PLAN §2-1 2 · 3.

```text
언제      KRX 단계의 곁 작업(`krx_target_sync` 의 `side_task` · 08:10 배치의 KOSPI 재시도와
          같은 자리) — ETF 와 독립이다(ETF T-1 을 못 받은 날도 돈다). 08:10 배치는 시각표
          08:10 · 08:15 · 08:20 · 08:24 · 마감 08:27 공유 · 09:20 · 수동 실행은 1칸(1회).
          같은 시각이면 ETF 가 먼저다(곁 작업은 ETF 시도 사이 · ETF 단계 뒤에만 돈다). 창
          채우기는 자기 다음 칸 시각이 오면 멈추고 그 칸에서 잇는다(칸이 ETF 와 같아 ETF
          시도는 많아야 호출 1회만큼 늦다 · 마지막 칸 뒤는 마감까지)
목표일    T-1 이 저장돼 있지 않으면 칸마다 1회 부른다 — **ledger 밖**(ETF 목표일 시도와 같다 ·
          `krx_backfill` 머리말). 저장되면 더 부르지 않는다
창        T-1 로 끝나는 31거래일 창(21 + 앞 여유 10 · PLAN §2-1 3) 안에서 이 표에 행이 하나도
          없는 날 — 오래된 날부터 · 목표일 저장 여부와 무관하게 채운다
하루 한도  창 날짜는 KST 하루 1회 + 첫 호출이 일시 오류였던 날짜의 09:20 보강 1회(항목 5 와 같은
          규칙 · `krx_backfill.call_allowed`). ledger 는 따로(`krx_stock_backfill_ledger.json`)
          — ETF 채우기와 같은 날짜에서 서로 막지 않는다
멈춤      응답에 보유 행이 하나도 없으면(목표일 · 창 어느 날이든) 그 실행을 끝낸다(헛조회
          방지). 목표일이 저장되지 않은 채 끝나면 `no_held_kospi_stocks`(보유에 코스피 개별주가
          없다) · 목표일이 저장된 날이면 `incomplete`(창 앞쪽이 보유 종목의 상장 전 등). 조회
          예외면 그 칸을 끝내고 다음 칸에 남은 날을 잇는다(원천 장애 · 이번 실행에서 부른 날은
          다시 다루지 않는다 · 다른 실행에서는 ledger 가 건너뛴다)
실패      예외를 올리지 않는다 · 소비측이 그 종목 파생값만 닫는다
```

'행이 없는 날'은 날짜 단위다(그날 보유 개별주 행이 하나라도 있으면 저장된 날). 그래서 나중에
새로 보유한 개별주는 그 뒤 날짜부터 쌓인다(지난 창을 다시 받지 않는다 · 설계 범위 = 현재
보유 3종). 거래정지 종목 때문에 매일 창 전체를 다시 부르지 않게 하려는 선택이다.
"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Optional, Sequence

from app import trading_day_lag
from app.market_briefing import krx_backfill, krx_stock_store, krx_sync
from app.market_briefing import krx_target_checks as checks
from app.market_data_store import DEFAULT_DB_PATH

_KST = timezone(timedelta(hours=9))

LEDGER_NAME = "krx_stock_backfill_ledger.json"
# PLAN §2-1 3 '21 + 10' — 소비측(`holdings_price_basis`)이 읽는 30거래일(20거래일 축 +
# 읽기 여유 10)을 덮는다.
WINDOW_TRADING_DAYS = 31

R_NO_HELD_ROWS = "no_held_rows"
STOP_SLOTS_EXHAUSTED = "slots_exhausted"
STOP_PENDING = "pending"

STATUS_OK = "ok"
STATUS_INCOMPLETE = "incomplete"
STATUS_NO_HELD_KOSPI_STOCKS = "no_held_kospi_stocks"
STATUS_NO_HOLDINGS = "no_holdings"
STATUS_HOLDINGS_MISSING = "holdings_missing"
STATUS_HOLDINGS_UNREADABLE = "holdings_unreadable"
STATUS_SKIPPED_BEFORE_OPEN = "skipped_before_open"
STATUS_NO_TARGET_DATE = "target_date_unknown"


def ledger_path_for(db_path: Optional[Path]) -> Path:
    """시장 DB 와 같은 폴더(운영 = `state/market/krx_stock_backfill_ledger.json`)."""
    return Path(db_path or DEFAULT_DB_PATH).parent / LEDGER_NAME


def holdings_tickers() -> tuple[Optional[list[str]], Optional[str]]:
    """보유 ticker(중복 제거 · 정렬) 또는 `(None, 사유)`. 파일 없음 · 손상을 구분한다."""
    from app import holdings as _holdings

    if not _holdings.HOLDINGS_FILE.exists():
        return None, STATUS_HOLDINGS_MISSING
    try:
        items = _holdings.load()
    except Exception as e:  # noqa: BLE001 - 손상 · 키 누락 → 호출 0 + 기록
        return None, f"{STATUS_HOLDINGS_UNREADABLE}:{type(e).__name__}"
    tickers = sorted({(h.ticker or "").strip() for h in items} - {""})
    return (tickers, None) if tickers else (None, STATUS_NO_HOLDINGS)


def _as_kst(dt: datetime) -> datetime:
    return dt.replace(tzinfo=_KST) if dt.tzinfo is None else dt.astimezone(_KST)


def attempt_once(
    bas_dd: str,
    *,
    key: str,
    fetch: Callable[[str, str], list[dict[str, Any]]],
    tickers: Sequence[str],
    db_path: Optional[Path],
    at: datetime,
) -> dict[str, Any]:
    """한 날짜 1회 조회 → 보유 행 고르기 → 저장 → read-back. 시도 기록을 돌려준다.

    기록 필드는 ETF 시도(`krx_target_checks.attempt_once`)와 같은 이름을 쓴다(키 · 가격
    값은 남기지 않는다). 결과: `ok` · `not_published`(0행 · 가격 없는 휴장 응답) ·
    `basis_date_mismatch` · `no_held_rows` · `fetch_error` · `store_error` ·
    `readback_mismatch`.
    """
    entry: dict[str, Any] = {
        "at_kst": _as_kst(at).isoformat(timespec="seconds"),
        "target": bas_dd,
        "http": None,
        "rows": 0,
        "priced_rows": 0,
        "held_rows": 0,
        "result": None,
        "error_type": None,
    }
    try:
        rows = fetch(bas_dd, key) or []
    except Exception as e:  # noqa: BLE001 - 시도 실패로 기록
        entry.update(result=checks.R_FETCH_ERROR, error_type=type(e).__name__)
        entry["http"] = checks.http_status(e)
        entry["transient"] = checks.is_transient_fetch_error(e)
        return entry
    entry["http"] = 200
    entry["rows"] = len(rows)
    entry["priced_rows"] = sum(1 for r in rows if (r.get("TDD_CLSPRC") or "").strip())
    if not rows or not krx_sync.has_traded_prices(rows):
        entry["result"] = checks.R_NOT_PUBLISHED
        return entry
    other = sorted({(r.get("BAS_DD") or "").strip() for r in rows} - {bas_dd})
    if other:
        entry.update(result=checks.R_BASIS_MISMATCH, returned_basis_dates=other[:3])
        return entry
    held = krx_stock_store.held_rows(rows, bas_dd=bas_dd, tickers=tickers)
    entry["held_rows"] = len(held)
    if not held:
        entry["result"] = R_NO_HELD_ROWS
        return entry
    day = krx_stock_store.iso(bas_dd)
    try:
        krx_stock_store.upsert(held, db_path=db_path)
        back = krx_stock_store.closes_on_date(day, db_path=db_path)
        if any(back.get(r.ticker) != r.close for r in held):
            krx_stock_store.delete_date(day, db_path=db_path)
            entry["result"] = checks.R_READBACK
            return entry
    except sqlite3.Error as e:
        entry.update(result=checks.R_STORE_ERROR, error_type=type(e).__name__)
        return entry
    entry["result"] = checks.R_OK
    return entry


class HoldingsStockTask:
    """보유 코스피 개별주 곁 작업(`krx_target_sync` 의 `side_task` 계약 · 예외를 올리지 않는다).

    `slots` · `deadline` 은 KRX 단계 시각표(`krx_target_sync.attempt_plan`)를 그대로 받는다.
    `key` · `target_iso` 가 없거나 시각표가 비면 부르지 않고 상태만 남긴다. `fetch` 가
    없으면 호출 때 `krx_sync._default_stock_fetcher` 를 모듈 속성으로 부른다(테스트 가드가
    막을 수 있게 import 시점에 묶지 않는다). `tickers` 가 없으면 보유 파일을 읽는다.
    """

    def __init__(
        self,
        *,
        today: date,
        target_iso: Optional[str],
        key: Optional[str],
        mode: Optional[str],
        slots: Sequence[datetime],
        deadline: Optional[datetime],
        clock: Callable[[], datetime],
        db_path: Optional[Path] = None,
        calendar_dir: Optional[Path] = None,
        fetch: Optional[Callable[[str, str], list[dict[str, Any]]]] = None,
        ledger_path: Optional[Path] = None,
        reinforcement: bool = False,
        tickers: Optional[Sequence[str]] = None,
        logger: Any = None,
    ) -> None:
        self.today, self.target, self.key = today, target_iso, key
        self.slots = [_as_kst(s) for s in slots]
        self.deadline = deadline
        self._now, self._fetch, self._logger = clock, fetch, logger
        self.db_path, self.calendar_dir = db_path, calendar_dir
        self.ledger_path = ledger_path or ledger_path_for(db_path)
        self.reinforcement = reinforcement
        self.tickers: list[str] = []
        self.rec: dict[str, Any] = {
            "status": None,
            "mode": mode,
            "slots": [s.strftime("%H:%M:%S") for s in self.slots],
            "target": target_iso,
            "held_tickers": 0,
            "target_attempts": [],
            "missing_before": [],
            "called": [],
            "retried": [],
            "filled": [],
            "failed": [],
            "skipped_called_today": [],
            "stopped": None,
        }
        self._target_stored = False
        self._todo: list[str] = (
            []
        )  # 이번 실행에서 아직 다루지 않은 창 날짜(목표일 제외)
        self._end: Optional[str] = None  # 이번 실행을 끝낸 사유
        self._window_end: Optional[str] = None  # 창 채우기만 끝낸 사유(ledger)
        self._last_stop: Optional[str] = None  # 마지막 시각에서 멈춘 사유(원천 오류)
        self.pending: list[datetime] = []
        status = self._prepare(tickers)
        if status is not None:
            self.rec["status"] = status
        else:
            self.pending = list(self.slots)

    def _prepare(self, tickers: Optional[Sequence[str]]) -> Optional[str]:
        """부를 것이 없으면 상태를 돌려준다(호출 0)."""
        if self.target is None:
            return STATUS_NO_TARGET_DATE
        if not self.key:
            return krx_sync.STATUS_NO_API_KEY
        if not self.slots:
            return STATUS_SKIPPED_BEFORE_OPEN
        if tickers is None:
            tickers, why = holdings_tickers()
            if tickers is None:
                return why
        self.tickers = sorted(set(tickers))
        if not self.tickers:
            return STATUS_NO_HOLDINGS
        self.rec["held_tickers"] = len(self.tickers)
        try:
            days = trading_day_lag.trading_days_ending(
                self.target, WINDOW_TRADING_DAYS, calendar_dir=self.calendar_dir
            )
            stored = krx_stock_store.stored_dates(db_path=self.db_path)
        except (sqlite3.Error, OSError, ValueError) as e:
            self._end = f"store_error:{type(e).__name__}"
            return STATUS_INCOMPLETE
        self._target_stored = self.target in stored
        self._todo = [d for d in days if d != self.target and d not in stored]
        lead = [] if self._target_stored else [self.target]
        self.rec["missing_before"] = lead + self._todo
        return None if self.rec["missing_before"] else STATUS_OK

    # ── side_task 계약 (`krx_target_sync`) ──────────────────────────────────

    def next_slot(self) -> Optional[datetime]:
        return self.pending[0] if self.pending else None

    def run_due(self, now: datetime) -> None:
        """도래한 시각이 있으면 **한 번** 돈다(밀린 시각은 합친다).

        시각을 여기서 다시 읽는다 — 같은 칸의 앞 곁 작업(KOSPI)이 오래 걸렸으면 넘겨받은
        `now` 보다 늦다(마감 판정 · 시도 기록 시각).
        """
        now = max(_as_kst(now), _as_kst(self._now()))
        due = [s for s in self.pending if s <= now]
        if not due:
            return
        self.pending = [s for s in self.pending if s > now]
        if self.deadline is not None and now >= self.deadline:
            self._end = krx_backfill.STOP_DEADLINE  # 08:27 뒤 새 시도 없음
        else:
            try:
                self._step(now)
            except Exception as e:  # noqa: BLE001 - ETF · KOSPI 를 멈추지 않는다
                self._end = f"unexpected:{type(e).__name__}"
        if self._end is not None or (self._target_stored and not self._todo):
            self.pending = []
        if self._logger is not None:
            self._logger.info(
                "개별주 곁 작업: slot=%s target_stored=%s left=%s stopped=%s",
                due[-1].strftime("%H:%M:%S"),
                self._target_stored,
                len(self._todo),
                self._end or self._window_end or self._last_stop,
            )

    def _attempt(self, iso: str, at: datetime) -> dict[str, Any]:
        return attempt_once(
            iso.replace("-", ""),
            key=self.key or "",
            fetch=self._fetch or krx_sync._default_stock_fetcher,
            tickers=self.tickers,
            db_path=self.db_path,
            at=at,
        )

    def _step(self, at: datetime) -> None:
        """목표일(ledger 밖 · 시각표대로) → 창 안 빈 날(ledger 규칙)."""
        self._last_stop = None
        if not self._target_stored:
            entry = self._attempt(self.target, at)
            self.rec["target_attempts"].append(entry)
            if entry["result"] == checks.R_OK:
                self._target_stored = True
                self.rec["filled"].append(self.target)
            elif entry["result"] == R_NO_HELD_ROWS:
                self._end = R_NO_HELD_ROWS
                return
            elif entry["result"] == checks.R_FETCH_ERROR:
                # 원천 불통 — 창은 다음 시각에(불통 중에 부르면 ledger 가 오늘 부른 날로 남긴다).
                self._last_stop = krx_backfill.STOP_FETCH_ERROR
                return
        if self._todo:
            self._fill()

    def _fill(self) -> None:
        today_iso = self.today.isoformat()
        got = krx_backfill.read_ledger_today(self.ledger_path, today_iso)
        if got is None:
            self._window_end = krx_backfill.STOP_LEDGER_UNREADABLE
            self._todo = []
            return
        calls, retryable = got
        rec = self.rec
        while self._todo:
            d = self._todo[0]
            if not krx_backfill.call_allowed(
                d, calls, retryable, reinforcement=self.reinforcement
            ):
                rec["skipped_called_today"].append(self._todo.pop(0))
                continue
            at = _as_kst(self._now())
            if self.pending and at >= self.pending[0]:
                break  # 다음 칸(= ETF 시도 시각) — 남은 날은 그 칸에서 잇는다
            if self.deadline is not None and at >= self.deadline:
                self._end = krx_backfill.STOP_DEADLINE
                break
            prev = calls.get(d, 0)
            calls[d] = prev + 1
            retryable.discard(d)
            try:
                krx_backfill.write_ledger(self.ledger_path, today_iso, calls, retryable)
            except OSError as e:
                if prev:
                    calls[d] = prev
                    retryable.add(d)
                else:
                    calls.pop(d, None)
                self._window_end = f"ledger_error:{type(e).__name__}"
                self._todo = []
                break
            self._todo.pop(0)
            rec["called"].append(d)
            if prev:
                rec["retried"].append(d)
            entry = self._attempt(d, at)
            if entry["result"] == checks.R_OK:
                rec["filled"].append(d)
                continue
            transient = entry.get("transient") is True
            rec["failed"].append(
                {
                    "date": d,
                    "result": entry["result"],
                    "error_type": entry["error_type"],
                    "http": entry["http"],
                    "rows": entry["rows"],
                    "transient": transient,
                }
            )
            if transient and not self.reinforcement and not prev:
                retryable.add(d)
                try:
                    krx_backfill.write_ledger(
                        self.ledger_path, today_iso, calls, retryable
                    )
                except OSError as e:
                    retryable.discard(d)
                    rec["retryable_write_error"] = type(e).__name__
            if entry["result"] == R_NO_HELD_ROWS:
                self._end = R_NO_HELD_ROWS  # 보유 행 없음 — 이번 실행 끝(헛조회 방지)
                break
            if entry["result"] == checks.R_FETCH_ERROR:
                # 원천 오류 — 남은 날은 다음 칸에서(이번 실행에서 부른 날은 다시 다루지 않는다).
                self._last_stop = krx_backfill.STOP_FETCH_ERROR
                break
        rec["calls_today"] = {d: n for d, n in sorted(calls.items())}

    # ── 기록 ──────────────────────────────────────────────────────────────

    def summary(self) -> dict[str, Any]:
        rec = dict(self.rec)
        done = self._target_stored and not self._todo
        stopped = self._end or self._window_end
        if stopped is None and not done and self.rec["status"] is None:
            stopped = self._last_stop or (
                STOP_PENDING if self.pending else STOP_SLOTS_EXHAUSTED
            )
        rec["stopped"] = stopped
        if rec["status"] is None:
            if self._end == R_NO_HELD_ROWS and not self._target_stored:
                rec["status"] = STATUS_NO_HELD_KOSPI_STOCKS
            else:
                left = set(rec["missing_before"]) - set(rec["filled"])
                rec["status"] = STATUS_INCOMPLETE if left else STATUS_OK
        return rec

    def log_summary(self, why: str) -> None:
        """기록이 배치 상태에 실리지 않는 경로(ETF 단계 예외)에서 로그로 남긴다."""
        if self._logger is not None:
            s = self.summary()
            self._logger.info(
                "개별주 곁 작업(%s): status=%s stopped=%s called=%s filled=%s",
                why,
                s["status"],
                s["stopped"],
                len(s["called"]) + len(s["target_attempts"]),
                len(s["filled"]),
            )


__all__ = [
    "LEDGER_NAME",
    "R_NO_HELD_ROWS",
    "STOP_PENDING",
    "STOP_SLOTS_EXHAUSTED",
    "STATUS_HOLDINGS_MISSING",
    "STATUS_HOLDINGS_UNREADABLE",
    "STATUS_INCOMPLETE",
    "STATUS_NO_HELD_KOSPI_STOCKS",
    "STATUS_NO_HOLDINGS",
    "STATUS_NO_TARGET_DATE",
    "STATUS_OK",
    "STATUS_SKIPPED_BEFORE_OPEN",
    "WINDOW_TRADING_DAYS",
    "HoldingsStockTask",
    "attempt_once",
    "holdings_tickers",
    "ledger_path_for",
]
