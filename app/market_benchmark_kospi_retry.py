"""POC3-02D-OPS-03 설계자 RESULT STEP 3 — 08:10 배치의 KOSPI 재시도.

08:10 벤치마크 단계의 KOSPI 결과가 기대 T-1 이 아니면 KRX 단계와 **같은 시각표**
(08:10 · 08:15 · 08:20 · 08:24 · 마감 08:27)로 다시 조회한다.

| 벤치마크 단계 시작(KST) | 재시도 |
|---|---|
| 08:00 전 | 없음 — KRX 단계와 같은 건너뜀 규칙 |
| 08:00 ~ 08:27 | 시작 뒤 60초 넘게 남은 시각만 · T-1 을 저장하면 곧바로 끝 |
| 08:27 뒤 | 없음 — 벤치마크 단계 1회만 |

- **ETF 적재와 독립이다.** 시각은 KRX 단계(`krx_target_sync.sync_krx_target` 의
  `side_task`)가 돌린다 — ETF 시도 사이와 ETF 판정 · 정합성 JSON 을 쓴 뒤에만 부른다.
  같은 시각이면 ETF 가 먼저다. ETF 가 성공해도 남은 KOSPI 시각은 계속 돈다.
- 재시도는 첫 시도 전 저장 최신일을 이번 실행이 이미 확인했을 때만 그 날짜를 빼고
  (`recheck_latest=False`) 그 뒤 빠진 날만 T-1 까지 부른다. 첫 시도가 그 날짜에서
  예외로 멈췄거나 증거 · 저장 · read-back 이 실패했으면 다시 포함한다(`True`) —
  확정 계약 9 ③ 의 09-17 같은 정정이 영영 빠지지 않게(설계자 RESULT STEP 3).
- 키가 없거나 기대 T-1 을 못 정하면 재시도하지 않는다(다시 불러도 결과가 같다).
- 08:27 까지 T-1 이 없으면 저장 기준일이 그대로 남는다. 최신성은 같은 함수
  (`kospi_freshness`)가 판정해 기준일 지연(`source_stale`)이 된다. Telegram 경고는
  없다(`runner_market_briefing.batch_failure_reasons` 는 KOSPI 를 보지 않는다).
- 09:20 `--krx-only` 는 이 객체를 만들지 않는다(KOSPI 호출 0).
- 시도마다 시각 · 부른 날짜별 결과 · 예외 종류를 `kospi_attempts` 에 남긴다(키 ·
  가격 값 없음). 이 모듈은 예외를 올리지 않는다.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Callable, Optional

from app.market_briefing import krx_target_sync as kts

# 다시 불러도 결과가 같은 실패 — 재시도하지 않는다.
NOT_RETRIABLE_ERRORS = ("api_key_missing", "expected_date_unknown")

# 받은 값이 저장까지 가지 못한 실패(`refresh_kospi_benchmark` 무결성 오류).
INTEGRITY_ERRORS = ("evidence_write_failed", "store:", "readback_mismatch")

KIND_FIRST = "benchmark_stage"
KIND_RETRY = "retry"

STOP_T1_STORED = "t1_stored"
STOP_NOT_RETRIABLE = "not_retriable"
STOP_DEADLINE = "deadline"
STOP_SLOTS_EXHAUSTED = "slots_exhausted"
STOP_NO_RETRY_WINDOW = "no_retry_window"
STOP_PENDING = "pending"

# 합친 결과에서 시도별로 더하는 기록(설계자 판정 '호출량과 응답 근거').
_SUM_KEYS = ("calls", "replaced", "written", "rows_written")
_CONCAT_KEYS = ("attempts", "corrections")


def now_kst() -> datetime:
    """KRX 단계와 같은 시계(`krx_target_sync._now_kst` · 호출 시점에 읽는다)."""
    return kts._as_kst(kts._now_kst())


def retry_slots(first_at: datetime) -> tuple[str, list[datetime]]:
    """벤치마크 단계 시작 시각 → `(mode, 재시도 시각들)`. 순수 함수.

    mode 는 KRX 시각표(`attempt_plan`)와 같은 말을 쓴다 — `skipped_before_open` ·
    `single_attempt` 이면 재시도가 없다.
    """
    first_at = kts._as_kst(first_at)
    mode, plan = kts.attempt_plan(first_at)
    if mode != kts.MODE_SCHEDULED:
        return mode, []
    return mode, [s for s in plan if s - first_at >= kts.MIN_SLOT_GAP]


def _t1_stored(res: dict) -> bool:
    """T-1 이 저장됐나. 무결성 오류(read-back 등)라도 기준일이 T-1 이면 다시 부르지 않는다."""
    if res.get("status") == "ok":
        return True
    as_of = res.get("as_of_date")
    return bool(as_of) and as_of == res.get("expected_as_of_date")


def _error_type(res: dict) -> Optional[str]:
    for a in res.get("attempts") or []:
        if isinstance(a, dict) and a.get("error_type"):
            return a["error_type"]
    return None


def _entry(
    res: dict,
    kind: str,
    at: datetime,
    *,
    slot: Optional[datetime] = None,
    error_type: Optional[str] = None,
) -> dict[str, Any]:
    """시도 1회 기록. 날짜별 결과 · 예외 종류만 — 키 · 가격 값은 담지 않는다."""
    calls = [
        {k: a[k] for k in ("date", "rows", "result", "error_type") if k in a}
        for a in res.get("attempts") or []
        if isinstance(a, dict)
    ]
    return {
        "kind": kind,
        "slot": slot.strftime("%H:%M") if slot is not None else None,
        "at_kst": at.isoformat(timespec="seconds"),
        "calls": calls,
        "result": "ok" if res.get("status") == "ok" else "failed",
        "as_of": res.get("as_of_date"),
        "error": res.get("error"),
        "error_type": error_type or _error_type(res),
    }


def latest_confirmed(results: list[dict]) -> bool:
    """첫 시도 전 저장 최신일을 이번 실행이 공식 자료원으로 확인해 저장까지 마쳤나.

    확인 = 그 날짜 시도 결과가 `ok` 이고 그 시도에 무결성 오류가 없다. 첫 결과에
    적재 전 기록(`before`)이 없으면(벤치마크 단계 예외 등) 확인하지 않은 것으로 본다.
    """
    before = (results[0] if results else {}).get("before")
    if not isinstance(before, dict):
        return False
    latest = before.get("as_of")
    if not latest:
        return True  # 빈 표 — 다시 확인할 저장 최신일이 없다
    for r in results:
        if str(r.get("error") or "").startswith(INTEGRITY_ERRORS):
            continue
        for a in r.get("attempts") or []:
            if isinstance(a, dict) and (a.get("date"), a.get("result")) == (
                latest,
                "ok",
            ):
                return True
    return False


def _default_attempt(end_date: date, recheck_latest: bool) -> dict:
    # 호출 시점에 읽는다 — 배치와 같은 적재 함수(`refresh_kospi`)를 쓴다.
    from app import market_benchmark_batch

    return market_benchmark_batch.refresh_kospi(
        end_date=end_date, recheck_latest=recheck_latest
    )


class KospiRetry:
    """벤치마크 단계 결과 1건에서 시작하는 KOSPI 재시도(KRX 단계의 `side_task`)."""

    def __init__(
        self,
        first: Optional[dict],
        *,
        first_at: datetime,
        end_date: date,
        attempt: Optional[Callable[[date, bool], dict]] = None,
        logger: Any = None,
    ) -> None:
        first_at = kts._as_kst(first_at)
        self.end_date = end_date
        self._attempt = attempt or _default_attempt
        self._logger = logger
        self.results: list[dict] = [dict(first or {})]
        self.attempts: list[dict] = [_entry(self.results[0], KIND_FIRST, first_at)]
        self.mode, self.slots = retry_slots(first_at)
        self.deadline = kts._at(first_at.date(), kts.STAGE_DEADLINE)
        self._deadline_hit = False
        self.pending: list[datetime] = [] if self._finished() else list(self.slots)

    def _finished(self) -> bool:
        last = self.results[-1]
        return _t1_stored(last) or (last.get("error") or "") in NOT_RETRIABLE_ERRORS

    # ── side_task 계약 (`krx_target_sync`) ──────────────────────────────────

    def next_slot(self) -> Optional[datetime]:
        return self.pending[0] if self.pending else None

    def run_due(self, now: datetime) -> None:
        """도래한 시각이 있으면 **한 번** 조회한다(밀린 시각은 합친다). 예외를 올리지 않는다."""
        now = kts._as_kst(now)
        due = [s for s in self.pending if s <= now]
        if not due:
            return
        self.pending = [s for s in self.pending if s > now]
        if now >= self.deadline:
            # 08:27 뒤 새 시도 없음(KRX 단계와 같은 마감).
            self.pending, self._deadline_hit = [], True
            return
        prev = self.results[-1]
        recheck = not latest_confirmed(self.results)
        try:
            res = dict(self._attempt(self.end_date, recheck) or {})
            err_type = None
        except Exception as e:  # noqa: BLE001 - KOSPI 재시도는 KRX 단계를 멈추지 않는다
            res = {
                "status": "failed",
                "as_of_date": prev.get("as_of_date"),
                "expected_as_of_date": prev.get("expected_as_of_date"),
                "error": f"kospi_retry:{type(e).__name__}",
            }
            err_type = type(e).__name__
        self.results.append(res)
        entry = _entry(res, KIND_RETRY, now, slot=due[-1], error_type=err_type)
        self.attempts.append(entry)
        if self._finished():
            self.pending = []
        if self._logger is not None:
            self._logger.info(
                "KOSPI 재시도: slot=%s result=%s as_of=%s calls=%s err=%s",
                entry["slot"],
                entry["result"],
                entry["as_of"],
                [c.get("date") for c in entry["calls"]],
                entry["error"],
            )

    # ── 기록 ──────────────────────────────────────────────────────────────

    def summary(self) -> dict[str, Any]:
        if _t1_stored(self.results[-1]):
            stopped = STOP_T1_STORED
        elif self._finished():
            stopped = STOP_NOT_RETRIABLE
        elif self._deadline_hit:
            stopped = STOP_DEADLINE
        elif self.pending:
            stopped = STOP_PENDING
        elif not self.slots:
            stopped = STOP_NO_RETRY_WINDOW
        else:
            stopped = STOP_SLOTS_EXHAUSTED
        return {
            "mode": self.mode,
            "slots": [s.strftime("%H:%M") for s in self.slots],
            "retries": len(self.results) - 1,
            "stopped": stopped,
        }

    def merged_result(self) -> dict[str, Any]:
        """이번 실행 KOSPI 결과 하나. 상태 · 기준일 · 오류는 마지막 시도.

        호출 수 · 날짜별 시도 · 정정 · 행 수는 모든 시도를 합친다. 적재 전 건수는 첫
        시도, 증거 경로는 마지막으로 남긴 것(`benchmark_refresh.kospi` 기존 필드 뜻 유지).
        """
        first, last = self.results[0], self.results[-1]
        if len(self.results) == 1:
            return first
        merged = dict(last)
        for k in _SUM_KEYS:
            if any(k in r for r in self.results):
                merged[k] = sum(int(r.get(k) or 0) for r in self.results)
        for k in _CONCAT_KEYS:
            if any(k in r for r in self.results):
                merged[k] = [x for r in self.results for x in (r.get(k) or [])]
        if "before" in first:
            merged["before"] = first["before"]
        paths = [r["evidence_path"] for r in self.results if r.get("evidence_path")]
        if paths or "evidence_path" in merged:
            merged["evidence_path"] = paths[-1] if paths else None
        return merged

    def apply(self, record: dict) -> None:
        """배치 기록에 반영한다. 재시도가 있었으면 KOSPI 결과 · 전체 benchmark 상태를 다시 센다."""
        record["kospi_attempts"] = [dict(a) for a in self.attempts]
        record["kospi_retry"] = self.summary()
        bench = record.get("benchmark_refresh")
        if len(self.results) < 2 or not isinstance(bench, dict):
            return
        from app.market_benchmark_batch import overall_status

        merged = self.merged_result()
        bench["kospi"] = merged
        others = [n for n in (bench.get("failed") or []) if n != "kospi"]
        failed = (["kospi"] if merged.get("status") != "ok" else []) + others
        bench["failed"] = failed
        if any(str(n).startswith("unexpected:") for n in others):
            # 벤치마크 단계 전체가 예외로 끝났다 — VIX · 미국 결과가 없다. KOSPI 재시도가
            # 성공해도 '일부 실패'로 세지 않고 단계 실패를 그대로 둔다.
            bench["status"] = "failed"
        else:
            bench["status"] = overall_status(
                len(failed), 2 + len(bench.get("us_indices") or {})
            )
        record["benchmark_status"] = bench["status"]
        record["kospi_as_of"] = merged.get("as_of_date")
        record.setdefault("stage_status", {})["benchmark"] = bench["status"]


__all__ = [
    "KIND_FIRST",
    "KIND_RETRY",
    "KospiRetry",
    "INTEGRITY_ERRORS",
    "NOT_RETRIABLE_ERRORS",
    "STOP_DEADLINE",
    "STOP_NOT_RETRIABLE",
    "STOP_NO_RETRY_WINDOW",
    "STOP_PENDING",
    "STOP_SLOTS_EXHAUSTED",
    "STOP_T1_STORED",
    "latest_confirmed",
    "now_kst",
    "retry_slots",
]
