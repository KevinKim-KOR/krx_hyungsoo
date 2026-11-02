"""POC6-17 — PC 시장 갱신의 수급 단계: OCI 수급 보관 사본(POC6-05) → PC `market_investor_flow_daily`(KOSPI).

키움을 직접 부르지 않는다(맥북 접속 IP 에 매이지 않게 · 설계 §2 · §3). 순서:

1. 가져오기 = 기존 05 `pull` CLI 를 자식 프로세스로(150초 상한 · 넘으면 그 프로세스 그룹 전체 정리 —
   `app/forward_auto/runner.run_child` 재사용 · 판정 §2-4). pull 안의 비대기 잠금이 06 과의 겹침을 막는다.
2. 반영 = 이 PC 보관소의 **공개 완료 묶음 목록을 시작 때 고정**하고, 아직 반영하지 않은 일일 수집 묶음을 run_id
   순으로 하나씩 검사 → 한 트랜잭션(행 반영 + `market_investor_flow_import` 기록 1행). 가져오기가 실패해도
   검증된 기존 사본은 반영한다(판정 §3 · 이 단계에만 · 06 의 pull 실패 처리는 그대로).

행 우선순위는 시간대가 명확한 관측 시각(`observed_at` · OCI 확보 시각)으로 정한다(판정 §4-1 · §4-3):
더 늦은 관측이면 값이 같아도 출처 · 관측 시각을 올리고(값 정정과 건수 구분), 더 이른 관측은 값과 관계없이
기존 값을 둔다. 같은 시각의 다른 값 · 시각을 알 수 없는 기존 행의 다른 값은 충돌(그 묶음 rollback · 멈춤).
수급 수집이 실패한(object 없는) 묶음은 반영 대상이 아니라 수집 상태 근거로만 기록한다(판정 §4-2).
범위 밖 행 삭제 · 보간 · 0 채우기 · 단위 재환산(object 는 이미 정수 원)은 없다.
"""

from __future__ import annotations

import json
import logging
import math
import sqlite3
import sys
import time
from contextlib import closing
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Optional

from app.market_data_store import log_refresh
from app.ml_evidence import store
from app.supply_fx_oil_store import (
    FLOW_IMPORT_LOG_SOURCE,
    FLOW_MARKET,
    FLOW_OCI_SOURCE,
    FLOW_PULL_LOG_SOURCE,
    INVESTORS,
    init_market_flow_tables,
    read_benchmark_series,
)

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[1]
PULL_TIMEOUT_S = 150  # 기존 수급 단계 상한 180초 안 · 화면 대기 8분 안(PLAN §3)
PULL_GRACE_S = 5
CLOSE_TOLERANCE = 0.005  # 지수 소수 둘째 자리(POC6-01 규칙 그대로)
INT64_LIMIT = 2**63  # SQLite 정수 칸 범위(넘으면 저장 단계 예외 — 검사 단계에서 거절)
# 가져오기가 실패해도 검증된 PC 사본을 반영하는 경우(판정 §3 · 망 · SSH · 시간 초과 · 경합 · 전송 확인 필요).
# 'failed'(가져오기 실행 자체의 알 수 없는 실패)는 반영하지 않고 기존 PC 수급을 둔다.
APPLY_AFTER_PULL = ("ok", "busy", "timeout", "unreachable", "check")
FLOW_KIND = "DAILY_COLLECTION"

IMPORT_DDL = """
CREATE TABLE IF NOT EXISTS market_investor_flow_import (
    evidence_run_id  TEXT PRIMARY KEY,
    manifest_sha256  TEXT NOT NULL,
    published_at     TEXT NOT NULL,
    flow_status      TEXT NOT NULL,
    result           TEXT NOT NULL,
    first_date       TEXT,
    last_date        TEXT,
    dates            INTEGER NOT NULL,
    new_rows         INTEGER NOT NULL,
    corrected_rows   INTEGER NOT NULL,
    refreshed_rows   INTEGER NOT NULL,
    same_rows        INTEGER NOT NULL,
    kept_newer_rows  INTEGER NOT NULL,
    max_observed_at  TEXT,
    applied_at       TEXT NOT NULL,
    refresh_id       TEXT NOT NULL
);
""".strip()
APPLIED = "APPLIED"
EXCLUDED = (
    "EXCLUDED_NO_FLOW"  # 수급 수집 실패 · 미시도 묶음(반영 대상 아님 · 상태 근거로만)
)

PULL_TEXT = {
    "busy": "다른 가져오기 진행 중",
    "timeout": f"가져오기 시간 제한({PULL_TIMEOUT_S}초)",
    "unreachable": "OCI 연결 실패",
    "check": "가져오기 확인 필요(일부 실패 · 손상 · 충돌)",
    "failed": "가져오기 실행 실패",
}


@dataclass
class PullOutcome:
    state: str  # ok | busy | timeout | unreachable | check | failed
    reason: Optional[str] = None  # 짧은 한국어(원시 출력 · 경로 · 접속 정보 없음)


@dataclass
class ApplyResult:
    applied: list[str] = field(default_factory=list)  # 수급을 반영한 묶음
    excluded: list[str] = field(
        default_factory=list
    )  # 수급 없는 묶음(상태 근거로만 기록)
    failed_run: Optional[str] = None
    fail_reason: Optional[str] = None
    counts: dict[str, int] = field(
        default_factory=lambda: dict.fromkeys(
            ("new", "corrected", "refreshed", "same", "kept_newer"), 0
        )
    )


class _RunProblem(Exception):
    """이 묶음은 반영하지 않고 멈춘다(짧은 한국어 사유)."""


def run_pull(
    *, root: Path, timeout_s: float = PULL_TIMEOUT_S, child: Optional[Callable] = None
) -> PullOutcome:
    """기존 05 `pull` CLI 를 자식으로 실행(상한 초과 = 그 그룹 전체 정리 · 잠금은 프로세스와 함께 풀림)."""
    if child is None:
        from app.forward_auto.runner import run_child as child
    argv = [
        sys.executable,
        "scripts/run_ml_evidence.py",
        "--root",
        str(Path(root).resolve()),
        "pull",
    ]
    try:
        c = child(argv, cwd=REPO_ROOT, timeout_s=timeout_s, grace_s=PULL_GRACE_S)
    except Exception:  # noqa: BLE001 — 실행 자체 실패도 수급 단계 안에서 격리
        logger.exception("flow import: pull child failed")
        return PullOutcome("failed", PULL_TEXT["failed"])
    if c.timed_out:
        return PullOutcome("timeout", PULL_TEXT["timeout"])
    res = c.result or {}
    status = res.get("status")
    if status in ("OK", "REPAIRED"):
        return PullOutcome("ok")
    if status == "BUSY":
        return PullOutcome("busy", PULL_TEXT["busy"])
    if status == "CHECK_REQUIRED" and "목록 조회 실패" in str(res.get("error") or ""):
        return PullOutcome("unreachable", PULL_TEXT["unreachable"])
    if status == "CHECK_REQUIRED":
        return PullOutcome("check", PULL_TEXT["check"])
    if status == "FAILED" and str(res.get("error") or "").startswith("TimeoutExpired"):
        return PullOutcome(
            "unreachable", PULL_TEXT["unreachable"]
        )  # SSH 목록 조회 시간 초과
    return PullOutcome("failed", PULL_TEXT["failed"])


def _row_time(text: object) -> Optional[datetime]:
    """기존 행 `collected_at` → UTC 시각. 보관본 형식(마이크로초 Z) · PC 저장 형식(초 Z)만 · 아니면 None(추정 안 함)."""
    try:
        return store.parse_iso(text)
    except ValueError:
        pass
    try:
        return datetime.strptime(str(text), "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        return None


def _flow_section(m: dict) -> Optional[dict]:
    if m.get("kind") != FLOW_KIND:
        return None
    f = (m.get("sources") or {}).get("investor_flow")
    return f if isinstance(f, dict) else None


def _load_rows(
    root: Path, run: store.RunRef, f: dict, kospi: dict[str, float]
) -> list[tuple[str, datetime, str, dict[str, int]]]:
    """묶음의 수급 object 전부 검사(참조 · 크기 · hash · 형식 · 지수값). 하나라도 틀리면 _RunProblem."""
    objs, received = f.get("objects"), f.get("received")
    if (
        not isinstance(objs, list)
        or not isinstance(received, list)
        or len(objs) != len(received)
    ):
        raise _RunProblem("보관본 확인 필요(수급 목록 형식)")
    sizes = {o["sha256"]: o["bytes"] for o in run.manifest["objects"]}
    rows, seen = [], set()
    for sha, want in zip(objs, received):
        if sha not in sizes:
            raise _RunProblem("보관본 확인 필요(참조 object 없음)")
        try:
            data = store.read_object(root, sha)
        except (OSError, store.EvidenceError):
            raise _RunProblem("보관본 손상(수급 object)") from None
        if len(data) != sizes[sha]:
            raise _RunProblem("보관본 손상(크기 다름)")
        try:
            j = json.loads(data.decode("utf-8"))
            d = j["date"]
            date.fromisoformat(d)
            nets = j["nets"]
            index_close = j["index_close"]
            obs_text = j["observed_at"]
        except (UnicodeDecodeError, ValueError, KeyError, TypeError):
            raise _RunProblem("보관본 확인 필요(수급 형식)") from None
        if d != want or d in seen or len(d) != 10:
            raise _RunProblem("보관본 확인 필요(날짜가 목록과 다름)")
        seen.add(d)
        try:
            obs = store.parse_iso(
                obs_text
            )  # 시간대(UTC Z) 미상이면 로컬로 추정하지 않음
        except ValueError:
            raise _RunProblem("보관본 확인 필요(관측 시각 형식)") from None
        if (
            isinstance(index_close, bool)
            or not isinstance(index_close, (int, float))
            or not math.isfinite(index_close)
            or index_close <= 0
        ):
            raise _RunProblem("보관본 확인 필요(지수값)")
        if not isinstance(nets, dict) or set(nets) != set(INVESTORS):
            raise _RunProblem("보관본 확인 필요(투자자 분류)")
        if any(isinstance(v, bool) or not isinstance(v, int) for v in nets.values()):
            raise _RunProblem("보관본 확인 필요(순매수가 정수 원이 아님)")
        if any(abs(v) >= INT64_LIMIT for v in nets.values()):
            raise _RunProblem("보관본 확인 필요(순매수 범위)")
        if d in kospi and abs(index_close - kospi[d]) > CLOSE_TOLERANCE:
            raise _RunProblem(f"보관본 지수값이 PC 코스피와 다름({d})")
        rows.append((d, obs, obs_text, nets))
    return rows


def _apply_run(
    con: sqlite3.Connection,
    run: store.RunRef,
    f: dict,
    rows: list,
    *,
    applied_at: str,
    refresh_id: str,
    counts: dict[str, int],
) -> None:
    """한 트랜잭션: 행마다 관측 시각 비교 → 반영 · 반영 기록 1행. 충돌 · 예외면 rollback 후 _RunProblem."""
    c = dict.fromkeys(counts, 0)
    try:
        con.execute("BEGIN IMMEDIATE")
    except sqlite3.Error:
        logger.exception("flow import: begin failed (%s)", run.run_id)
        raise _RunProblem("PC 표 반영 실패") from None
    try:
        for d, obs, obs_text, nets in rows:
            cur = {
                inv: (net, at)
                for inv, net, at in con.execute(
                    "SELECT investor, net_value, collected_at FROM market_investor_flow_daily "
                    "WHERE market = ? AND trade_date = ?",
                    (FLOW_MARKET, d),
                )
            }
            for inv in INVESTORS:
                net = nets[inv]
                old = cur.get(inv)
                if old is None:
                    con.execute(
                        "INSERT INTO market_investor_flow_daily (market, trade_date, investor, "
                        "buy_value, sell_value, net_value, source, collected_at) "
                        "VALUES (?, ?, ?, NULL, NULL, ?, ?, ?)",
                        (FLOW_MARKET, d, inv, net, FLOW_OCI_SOURCE, obs_text),
                    )
                    c["new"] += 1
                    continue
                old_net, old_at = old
                old_t = _row_time(old_at)
                if old_t is None or old_t == obs:
                    if old_net != net:
                        raise _RunProblem(
                            f"수급 값 충돌({d} · 같은 관측 시각 또는 기존 시각 불명)"
                        )
                    c["same"] += 1
                elif obs > old_t:
                    con.execute(
                        "UPDATE market_investor_flow_daily SET net_value = ?, source = ?, "
                        "collected_at = ? WHERE market = ? AND trade_date = ? AND investor = ?",
                        (net, FLOW_OCI_SOURCE, obs_text, FLOW_MARKET, d, inv),
                    )
                    c["corrected" if old_net != net else "refreshed"] += 1
                elif old_net != net:
                    c["kept_newer"] += 1  # 더 이른 관측의 다른 값 — 최신 값을 덮지 않음
                else:
                    c["same"] += 1
        dates = [r[0] for r in rows]
        con.execute(
            "INSERT INTO market_investor_flow_import VALUES "
            "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                run.run_id,
                run.manifest_sha256,
                run.manifest["published_at"],
                str(f.get("status")),
                APPLIED,
                min(dates),
                max(dates),
                len(dates),
                c["new"],
                c["corrected"],
                c["refreshed"],
                c["same"],
                c["kept_newer"],
                store.iso(max(r[1] for r in rows)),
                applied_at,
                refresh_id,
            ),
        )
        con.execute("COMMIT")
    except _RunProblem:
        con.execute("ROLLBACK")
        raise
    except sqlite3.Error:
        con.execute("ROLLBACK")
        logger.exception("flow import: db apply failed (%s)", run.run_id)
        raise _RunProblem("PC 표 반영 실패") from None
    except (
        Exception
    ):  # noqa: BLE001 — 예상 밖 오류도 되돌리고 그 묶음에서 멈춤(다시 눌러 해결된다고 보지 않음)
        con.execute("ROLLBACK")
        logger.exception("flow import: unexpected apply error (%s)", run.run_id)
        raise _RunProblem("PC 표 반영 확인 필요(예상 밖 오류)") from None
    for k, v in c.items():
        counts[k] += v


def _record_excluded(
    con: sqlite3.Connection,
    run: store.RunRef,
    f: dict,
    *,
    applied_at: str,
    refresh_id: str,
) -> None:
    con.execute(
        "INSERT INTO market_investor_flow_import VALUES "
        "(?, ?, ?, ?, ?, NULL, NULL, 0, 0, 0, 0, 0, 0, NULL, ?, ?)",
        (
            run.run_id,
            run.manifest_sha256,
            run.manifest["published_at"],
            str(f.get("status")),
            EXCLUDED,
            applied_at,
            refresh_id,
        ),
    )


def apply_evidence_flows(
    *,
    root: Path,
    db_path: Path,
    refresh_id: str,
    clock: Callable[[], datetime] = store.utc_now,
) -> ApplyResult:
    """공개 완료 묶음(시작 때 고정)의 미반영 수급을 run_id 순으로 반영. 첫 실패에서 멈추고 앞 범위만 성공."""
    out = ApplyResult()
    runs, problems = store.list_runs(root)
    broken = {p.split(":", 1)[0] for p in problems}
    by_id = {r.run_id: r for r in runs}
    kospi = dict(read_benchmark_series("KOSPI", db_path=db_path))
    init_market_flow_tables(db_path)
    with closing(sqlite3.connect(str(db_path), isolation_level=None)) as con:
        con.execute(IMPORT_DDL)
        done = dict(
            con.execute(
                "SELECT evidence_run_id, manifest_sha256 FROM market_investor_flow_import"
            ).fetchall()
        )
        for name in sorted(set(by_id) | broken):
            run = by_id.get(name)
            try:
                if run is None:
                    if name in done:
                        continue  # 이미 반영한 묶음의 과거 사본 재검증은 조건이 아님(판정 §4-2)
                    raise _RunProblem("보관본 확인 필요(묶음 목록을 읽을 수 없음)")
                f = _flow_section(run.manifest)
                if f is None:
                    continue  # 연구 묶음 · 수급 구역 없는 묶음
                if name in done:
                    if done[name] != run.manifest_sha256:
                        raise _RunProblem("보관본 확인 필요(같은 묶음 다른 내용)")
                    continue
                at = store.iso(clock())
                status = f.get("status")
                if status == "FAILED" and not f.get("objects"):
                    try:
                        _record_excluded(
                            con, run, f, applied_at=at, refresh_id=refresh_id
                        )
                    except sqlite3.Error:
                        logger.exception("flow import: exclude record failed")
                        raise _RunProblem("PC 표 반영 실패") from None
                    out.excluded.append(name)
                    continue
                if status not in ("OK", "PARTIAL"):
                    raise _RunProblem("보관본 확인 필요(수급 상태)")
                if not f.get("objects"):
                    raise _RunProblem("보관본 확인 필요(수급 object 없음)")
                rows = _load_rows(root, run, f, kospi)
                _apply_run(
                    con,
                    run,
                    f,
                    rows,
                    applied_at=at,
                    refresh_id=refresh_id,
                    counts=out.counts,
                )
                out.applied.append(name)
            except _RunProblem as e:
                out.failed_run, out.fail_reason = name, str(e)
                break
            except (
                Exception
            ):  # noqa: BLE001 — 예상 밖 오류도 앞서 끝난 범위를 지우지 않고 그 묶음에서 멈춤
                logger.exception("flow import: unexpected error (%s)", name)
                out.failed_run = name
                out.fail_reason = "보관본 확인 필요(예상 밖 오류)"
                break
    return out


def refresh_flows_from_oci(
    *,
    db_path: Path,
    refresh_id: str,
    asof: str,
    root: Path = store.EVIDENCE_ROOT,
    pull: Optional[Callable[[], PullOutcome]] = None,
    clock: Callable[[], datetime] = store.utc_now,
) -> list[str]:
    """PC 시장 갱신의 수급 단계. 가져오기 · 반영 기록을 따로 1행씩 남기고, 완료 문구용 문제 목록을 돌려준다."""
    t0 = time.perf_counter()
    po = (pull or (lambda: run_pull(root=root)))()
    pulled = po.state == "ok"
    _log(
        db_path,
        refresh_id,
        "flowpull",
        FLOW_PULL_LOG_SOURCE,
        asof,
        pulled,
        1 if pulled else 0,
        time.perf_counter() - t0,
        po.reason,
    )
    t1 = time.perf_counter()
    if po.state not in APPLY_AFTER_PULL:
        res = (
            ApplyResult()
        )  # 반영하지 않음 = 기존 PC 수급 유지(가져오기 기록이 사유를 남김)
    else:
        try:
            res = apply_evidence_flows(
                root=root, db_path=db_path, refresh_id=refresh_id, clock=clock
            )
        except (
            Exception
        ):  # noqa: BLE001 — 반영 시작 전 예외(목록 · 표 준비)도 갱신 전체를 멈추지 않는다
            logger.exception("flow import: apply failed")
            res = ApplyResult(failed_run="-", fail_reason="PC 표 반영 실패")
    _log(
        db_path,
        refresh_id,
        "flowoci",
        FLOW_IMPORT_LOG_SOURCE,
        asof,
        res.failed_run is None,
        len(res.applied),
        time.perf_counter() - t1,
        res.fail_reason,
        attempted=len(res.applied) + (1 if res.failed_run else 0),
    )
    problems = []
    if not pulled:
        problems.append(f"투자자 수급({po.reason})")
    if res.failed_run is not None:
        problems.append(f"투자자 수급({res.fail_reason})")
    return problems


def _log(
    db_path: Path,
    refresh_id: str,
    label: str,
    source: str,
    asof: str,
    ok: bool,
    success: int,
    runtime: float,
    reason: Optional[str],
    *,
    attempted: int = 1,
) -> None:
    try:
        log_refresh(
            run_id=f"market-flow-{label}-{refresh_id}",
            source=source,
            asof=asof,
            attempted=attempted,
            success=success,
            fail=0 if ok else 1,
            runtime_seconds=round(runtime, 3),
            error_summary=(reason or None) if not ok else None,
            db_path=db_path,
        )
    except Exception:  # noqa: BLE001 — 기록 실패도 갱신을 멈추지 않는다
        logger.exception("flow import log failed")


def main(argv: Optional[list[str]] = None) -> int:
    """단독 확인(PLAN 판정 §5 (나)) — 버튼과 같은 수급 단계 함수만(가져오기 + 반영 · 다른 공급자 호출 0).

    `python -m app.oci_flow_import` (기본 = PC 시장 DB · PC 보관소). 결과는 갱신 기록 2행 + RESULT 한 줄.
    """
    import argparse

    from app.market_data_store import DEFAULT_DB_PATH

    p = argparse.ArgumentParser(
        description="POC6-17 OCI 수급 보관본 → PC 수급 표(단독 확인)"
    )
    p.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    p.add_argument("--root", type=Path, default=store.EVIDENCE_ROOT)
    args = p.parse_args(argv)
    now = store.utc_now()
    rid = f"manual-{now:%Y%m%dT%H%M%SZ}"
    kst_day = now.astimezone(timezone(timedelta(hours=9))).date().isoformat()
    problems = refresh_flows_from_oci(
        db_path=args.db, refresh_id=rid, asof=kst_day, root=args.root
    )
    print(
        "RESULT "
        + json.dumps({"refresh_id": rid, "problems": problems}, ensure_ascii=False)
    )
    return 0 if not problems else 2


if __name__ == "__main__":
    sys.exit(main())
