"""POC6-05 — OCI 일일 수집 `collect-daily`(cron 09:40 · 매일 · 독립 프로세스 · 판정 2026-10-22).

한 번 실행 = 완료 묶음(manifest) 하나. 증거 보관소에 쓰기만 한다(덮어쓰기 없음).

| 자료 | 받는 방식 | OCI DB |
|---|---|---|
| ETF 목록 · 네이버 수신 창 | 새 완료 거래일 · 같은 기준일 미확보분이 있을 때(`daily_naver`) | 쓰지 않음 |
| KRX ETF · 보유 개별주 · 지수 | 재조회 0 · 최근 21거래일 delta(`daily_tables`) | 읽기만 |
| 수집 기록 · KOSPI 정정 증거 | 파일 바이트 그대로(`daily_tables`) | — |
| 날짜 축 | 달력 CSV · KOSPI 저장일 목록 실제 내용 | — |
| 원/달러 · WTI · 코스피 수급 | POC6-01 함수 + capture(`daily_flow`) | 두 시장 흐름 표만 |

시각: `observed_at` = 실제 수신 · `published_at`(= available_at) = 묶음 최초 공개.
학습 · 추론 · 성과 계산 없음.
"""

from __future__ import annotations

import importlib.metadata
import json
import logging
import sqlite3
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from app.market_briefing.calendar import CALENDAR_DIR, CALENDAR_GLOB
from app.ml_evidence import daily_flow, daily_tables
from app.ml_evidence import daily_naver as nv
from app.ml_evidence import store
from app.trading_day_lag import expected_previous_trading_day

logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))
PROJECT_ROOT = Path(__file__).resolve().parents[2]
MARKET_DB = Path("state/market/market_data.sqlite")
NETWORK_NOTE = "기존 HTTP 경계에서 수신 바이트를 셀 수 없음(공급자가 전체 이력을 준 뒤 자름) — 미측정"
OK, PARTIAL, FAILED, SKIPPED = "OK", "PARTIAL", "FAILED", "SKIPPED_NO_NEW"


def git_head() -> Optional[str]:
    """이 수집 프로그램의 실행 commit(과거 연구의 실행 commit 으로 쓰지 않는다)."""
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


@dataclass
class Deps:
    now: Callable[[], datetime] = store.utc_now
    clock: Callable[[], float] = time.monotonic
    sleep: Callable[[float], None] = time.sleep
    list_fetcher: Optional[Callable] = None
    price_fetcher: Optional[Callable] = None
    request_timeout: Optional[Callable] = None
    fx_http_get: Optional[Callable] = None
    kiwoom_client: Optional[Any] = None
    git_head: Callable[[], Optional[str]] = git_head

    def resolved(self) -> "Deps":
        from app import market_data_fdr as fdr_mod
        from app.three_push_runtime.market_data_batch import fdr_request_timeout

        self.list_fetcher = self.list_fetcher or fdr_mod._default_universe_fetcher
        self.price_fetcher = self.price_fetcher or fdr_mod._default_price_fetcher
        self.request_timeout = self.request_timeout or fdr_request_timeout
        return self


def _libraries() -> dict:
    out = {"python": sys.version.split()[0]}
    for pkg in ("finance-datareader", "pandas", "requests", "urllib3"):
        try:
            out[pkg] = importlib.metadata.version(pkg)
        except importlib.metadata.PackageNotFoundError:
            out[pkg] = None
    return out


ACQUISITION = (
    "etf_list",
    "naver_etf_windows",
    "krx_etf_close",
    "krx_stock_close",
    "benchmarks",
    "fx_wti",
    "investor_flow",
)
BOOKKEEPING = ("date_axis", "batch_records")


def combine(statuses: list[str]) -> str:
    """자료원 상태 → 묶음 상태. 유효 자료가 있는 부분 실패 = PARTIAL · 전부 실패 = FAILED."""
    active = [s for s in statuses if s != SKIPPED]
    if not active:
        return SKIPPED
    if all(s == FAILED for s in active):
        return FAILED
    if all(s == OK for s in active):
        return OK
    return PARTIAL


def bundle_status(sources: dict) -> str:
    """확보 자료원으로 판정하고, 날짜 축 · 수집 기록이 실패 · 부분이면 OK 를 PARTIAL 로 낮춘다(판정 §6-2)."""
    status = combine([sources[k]["status"] for k in ACQUISITION if k in sources])
    side = [sources[k]["status"] for k in BOOKKEEPING if k in sources]
    if status == OK and any(x in (FAILED, PARTIAL) for x in side):
        return PARTIAL
    return status


class Collector:
    def __init__(self, root, db_path, calendar_dir, deps, site, limit_tickers) -> None:
        self.root, self.db_path, self.calendar_dir = root, db_path, calendar_dir
        self.deps, self.site, self.limit = deps, site, limit_tickers
        self.objects: dict[str, dict] = {}
        self.new_bytes = 0
        self.prev: Optional[store.RunRef] = None
        self.prev_objects: dict[str, dict] = {}
        self._usable: dict[str, bool] = {}
        self.repaired: list[str] = []

    def add(self, info: Optional[dict], role: str, fmt: str) -> Optional[str]:
        if info is None:
            return None
        sha = info["sha256"]
        if sha in self.objects:
            return sha
        if info.get("created"):
            self.new_bytes += info["bytes"]
        if info.get("repaired"):
            self.repaired.append(sha)
        entry = {"sha256": sha, "bytes": info["bytes"], "role": role, "format": fmt}
        if "lines" in info:
            entry["lines"] = info["lines"]
        self.objects[sha] = entry
        return sha

    def usable(self, sha: Optional[str]) -> bool:
        """이전 묶음의 object 가 실제로 있고 크기 · 해시가 맞는가(손상 참조를 잇지 않는다)."""
        if not sha:
            return False
        if sha not in self._usable:
            old = self.prev_objects.get(sha)
            path = store.object_path(self.root, sha)
            self._usable[sha] = bool(
                old
                and path.exists()
                and path.stat().st_size == old["bytes"]
                and store.sha256_file(path) == sha
            )
        return self._usable[sha]

    def reuse(self, sha: str, role: str) -> None:
        """이전 묶음의 object 를 이 묶음 참조 목록에 넣는다(export · 복구 · 가져오기가 함께 가져가게)."""
        if sha in self.objects:
            return
        if not self.usable(sha):
            raise store.EvidenceError(f"이전 판 object 없음 · 손상: {sha[:16]}")
        old = self.prev_objects[sha]
        entry = {k: old[k] for k in ("sha256", "bytes", "format", "lines") if k in old}
        entry["role"] = role
        entry["reused_from"] = old.get("reused_from") or self.prev.run_id
        self.objects[sha] = entry

    def prev_source(self, name: str) -> dict:
        if self.prev is None:
            return {}
        return self.prev.manifest.get("sources", {}).get(name) or {}

    def run(self) -> tuple[str, dict]:
        d = self.deps
        started, t0 = d.now(), d.clock()
        today = started.astimezone(KST).date()
        runs, _ = store.list_runs(self.root)
        daily = [r for r in runs if r.manifest["kind"] == "DAILY_COLLECTION"]
        good = [r for r in daily if r.manifest["status"] != FAILED]
        self.prev = good[-1] if good else None  # FAILED 묶음의 판은 잇지 않는다
        if self.prev:
            self.prev_objects = {o["sha256"]: o for o in self.prev.manifest["objects"]}
        skipped_failed = [
            r.run_id for r in daily if self.prev is None or r.run_id > self.prev.run_id
        ]
        sources: dict[str, dict] = {}
        integrity = None
        try:
            snap = daily_tables.read_db_snapshot(self.db_path)
            sources["date_axis"] = self._axis(snap, today)
            target = sources["date_axis"]["latest_completed_trading_day"]
            sources.update(self._domestic(target, today, snap))
            for name in ("krx_etf_close", "krx_stock_close", "benchmarks"):
                prev_map = self.prev_source(name).get("map", {})
                sources[name] = daily_tables.delta(
                    name, snap, prev_map, self.root, self.add, self.reuse, self.usable
                )
                daily_tables.note_behind(sources[name], target)
            sources["batch_records"] = daily_tables.batch_records(self.root, self.add)
            sources.update(
                daily_flow.run_market_flow(
                    root=self.root,
                    db_path=self.db_path,
                    deps=d,
                    kospi=snap["kospi"],
                    today=today,
                    target=target,
                    add=self.add,
                )
            )
            if snap["problems"]:
                sources["date_axis"]["db_problems"] = snap["problems"]
        except (store.EvidenceError, OSError, sqlite3.Error) as e:
            logger.exception("collect-daily 보관 · 읽기 실패")
            integrity = f"{type(e).__name__}: {str(e)[:200]}"
        status = FAILED if integrity else bundle_status(sources)
        manifest = {
            "schema": store.SCHEMA,
            "run_id": store.new_run_id(started),
            "kind": "DAILY_COLLECTION",
            "site": self.site,
            "status": status,
            "code_commit": d.git_head(),
            "code_commit_kind": "collector_run_commit",
            "started_at": store.iso(started),
            "finished_at": store.iso(d.now()),
            "today_kst": today.isoformat(),
            "previous_run": self.prev.run_id if self.prev else None,
            "skipped_failed_runs": skipped_failed,
            "test_limit_tickers": self.limit,
            "integrity_error": integrity,
            "repaired_objects": self.repaired,
            "sources": sources,
            "objects": [self.objects[k] for k in sorted(self.objects)],
            "resources": {
                "elapsed_s": round(d.clock() - t0, 3),
                "max_rss": store.max_rss(),
                "network_received_bytes": None,
                "network_received_bytes_note": NETWORK_NOTE,
                "evidence_new_bytes": self.new_bytes,
            },
            "libraries": _libraries(),
            "limits": [
                "연구 증거 보관 · 학습 · 추론 · 성과 계산 없음",
                "네이버 수신 창 · KRX 무조정 · 지수 표 값은 서로 대체하지 않음",
                "D20 정답 · 예측 · 오차를 만들지 않음",
            ],
        }
        _, published = store.publish_run(self.root, manifest, clock=d.now)
        return status, published

    def _axis(self, snap: dict, today: date) -> dict:
        cal = []
        if self.calendar_dir.exists():
            for p in sorted(self.calendar_dir.glob(CALENDAR_GLOB)):
                info = store.put_file(self.root, p)
                self.add(info, "calendar_csv", "csv")
                cal.append(
                    {"name": p.name, "sha256": info["sha256"], "bytes": info["bytes"]}
                )
        kd = snap["kospi"]
        payload = {"source": "market_benchmark_daily_price KOSPI 저장일", "dates": kd}
        kobj = self.add(
            store.put_bytes(self.root, store.canonical(payload)),
            "kospi_stored_dates",
            "json",
        )
        target = expected_previous_trading_day(
            today.isoformat(), calendar_dir=self.calendar_dir
        )
        if target and kd:
            status = OK
        else:
            status = PARTIAL if (target or kd) else FAILED
        return {
            "status": status,
            "today_kst": today.isoformat(),
            "latest_completed_trading_day": target,
            "calendar_files": cal,
            "calendar_missing": not cal,
            "fallback_policy": "연도 파일이 없는 해 = 평일 기본(5/1 · 12/31 제외 · 2026-09-11 사용자 확정)",
            "kospi_stored_dates": {
                "object": kobj,
                "count": len(kd),
                "latest": kd[-1] if kd else None,
            },
        }

    def _list_tickers(self, eff: Optional[dict]) -> list[str]:
        if not eff:
            return []
        data = json.loads(store.read_object(self.root, eff["object"]).decode("utf-8"))
        return [r["ticker"] for r in data["rows"]]

    def _domestic(self, target: Optional[str], today: date, snap: dict) -> dict:
        prev_list = self.prev_source("etf_list")
        prev_win = self.prev_source("naver_etf_windows")
        if target is None:
            reason = {"status": FAILED, "reason": "기준 거래일 판정 불가"}
            return {"etf_list": dict(reason), "naver_etf_windows": dict(reason)}
        prev_eff = prev_list.get("effective")
        bad_prev = []
        if prev_eff and not self.usable(prev_eff["object"]):
            bad_prev.append(prev_eff["object"])
            prev_eff = None  # 손상된 직전 목록은 쓰지 않는다
        same_day = prev_win.get("target_day") == target
        prior = list(prev_win.get("objects_for_target_day", [])) if same_day else []
        if any(not self.usable(sha) for sha in prior):
            bad_prev += [sha for sha in prior if not self.usable(sha)]
            same_day, prior = False, []  # 손상된 앞 판이 있으면 그날 전체를 다시 받는다
        for sha in prior:
            self.reuse(sha, "naver_windows_target_day")
        list_ok = same_day and prev_list.get("status") in (OK, SKIPPED) and prev_eff
        if list_ok and not prev_win.get("missing"):
            self.reuse(prev_eff["object"], "etf_list_effective")
            return {
                "etf_list": {
                    "status": SKIPPED,
                    "reason": "같은 기준 거래일 목록 확보됨",
                    "effective": prev_eff,
                },
                "naver_etf_windows": {
                    "status": SKIPPED,
                    "reason": "새 완료 거래일 없음 · 미확보 없음",
                    "target_day": target,
                    "missing": [],
                    "have_total": prev_win.get("have_total", 0),
                    "objects_for_target_day": prior,
                    "semantics": nv.PRICE_SEMANTICS,
                },
            }
        if list_ok:
            lst = {
                "status": SKIPPED,
                "reason": "같은 기준일 목록 재사용",
                "effective": prev_eff,
            }
        else:
            lst = self._fetch_list(prev_eff, snap)
        if bad_prev:
            lst["previous_bad_objects"] = sorted(set(bad_prev))
        eff = lst.get("effective")
        if eff and eff["object"] not in self.objects:
            self.reuse(eff["object"], "etf_list_effective")
        if not eff:
            return {
                "etf_list": lst,
                "naver_etf_windows": {
                    "status": FAILED,
                    "reason": "대상 목록 없음",
                    "target_day": target,
                    "missing": [],
                },
            }
        tickers = self._list_tickers(eff)
        if same_day:
            known = set(self._list_tickers(prev_eff))
            targets = sorted(set(prev_win.get("missing", [])) | (set(tickers) - known))
            have_before = prev_win.get("have_total", 0)
        else:
            targets, have_before = tickers, 0
        win = self._windows(targets, target, today, prior, have_before)
        return {"etf_list": lst, "naver_etf_windows": win}

    def _krx_compare(self, tickers: set[str], snap: dict) -> Optional[dict]:
        groups = snap["groups"].get("krx_etf_close") or {}
        if not groups:
            return None
        day = max(groups)
        krx = {r[0] for r in groups[day]}
        return {
            "krx_date": day,
            "list_not_in_krx": len(tickers - krx),
            "krx_not_in_list": len(krx - tickers),
            "examples": {
                "list_not_in_krx": sorted(tickers - krx)[:20],
                "krx_not_in_list": sorted(krx - tickers)[:20],
            },
        }

    def _fetch_list(self, prev_eff: Optional[dict], snap: dict) -> dict:
        response, error = None, None
        try:
            with self.deps.request_timeout():  # 기존 요청 상한(20초) — FDR 목록 경로는 자체 상한 없음
                response = nv.normalize_listing(self.deps.list_fetcher())
        except Exception as e:  # noqa: BLE001 — 목록 실패는 직전 목록(stale)로
            error = type(e).__name__
        at = self.deps.now()
        observed = store.iso(at)
        prev_count = prev_eff.get("count") if prev_eff else None
        reason = nv.judge_list(response, error, prev_count)
        resp_obj = None
        if response:
            payload = {
                "source": nv.LIST_SOURCE,
                "observed_at": observed,
                "rows": response,
            }
            info = store.put_bytes(self.root, store.canonical(payload))
            resp_obj = self.add(info, "etf_list_response", "json")
        prev_t = set(self._list_tickers(prev_eff))
        now_t = {r["ticker"] for r in response or []}
        base = {
            "observed_at": observed,
            "response_object": resp_obj,
            "response_count": len(response or []),
            "source": nv.LIST_SOURCE,
            "added": sorted(now_t - prev_t) if prev_eff and response else [],
            "removed": sorted(prev_t - now_t) if prev_eff and response else [],
        }
        if reason is None:
            eff = {
                "object": resp_obj,
                "list_date": at.astimezone(KST).date().isoformat(),
                "list_hash": nv.list_hash(response),
                "count": len(response),
                "stale": False,
            }
            return base | {
                "status": OK,
                "effective": eff,
                "krx_compare": self._krx_compare(now_t, snap),
            }
        if prev_eff is None:
            return base | {"status": FAILED, "reason": reason, "effective": None}
        stale = dict(prev_eff, stale=True)
        stale.setdefault("from_run", self.prev.run_id)
        return base | {
            "status": PARTIAL,
            "reason": reason + " → 직전 목록(stale) 사용",
            "effective": stale,
            "krx_compare": self._krx_compare(prev_t, snap),
        }

    def _windows(self, targets, target, today, prior, have_before) -> dict:
        d = self.deps
        writer = store.GzJsonlWriter(self.root)
        try:
            out = nv.fetch_windows(
                targets,
                writer=writer,
                target_day=target,
                today_kst=today,
                fetcher=d.price_fetcher,
                request_timeout=d.request_timeout,
                now=d.now,
                clock=d.clock,
                sleep=d.sleep,
                attempt_limit=self.limit,
            )
        except BaseException:
            writer.abort()
            raise
        sha = self.add(writer.finish(), "naver_windows", "jsonl.gz")
        have = have_before + out["received"]
        status = OK if not out["missing"] else (PARTIAL if have else FAILED)
        lim = nv.Limits()
        return out | {
            "status": status,
            "target_day": target,
            "object": sha,
            "have_total": have,
            "objects_for_target_day": prior + ([sha] if sha else []),
            "retry_of_same_day": bool(prior),
            "semantics": nv.PRICE_SEMANTICS,
            "limits": {
                "gap_s": lim.gap_s,
                "budget_s": lim.budget_s,
                "timeout_streak": lim.timeout_streak,
                "fail_streak": lim.fail_streak,
                "http_block_stop": [403, 429],
            },
        }


def collect_daily(
    *,
    root: Optional[Path] = None,
    db_path: Optional[Path] = None,
    calendar_dir: Optional[Path] = None,
    deps: Optional[Deps] = None,
    site: str = "OCI",
    limit_tickers: Optional[int] = None,
) -> tuple[str, dict]:
    """일일 수집 1회. 다른 수집이 실행 중이면 ('BUSY', {...}) — 아무것도 쓰지 않는다."""
    root = root or store.EVIDENCE_ROOT
    with store.file_lock(root / ".collect.lock") as ok:
        if not ok:
            return "BUSY", {"status": "BUSY", "reason": "다른 collect-daily 가 실행 중"}
        return Collector(
            root,
            db_path or MARKET_DB,
            calendar_dir or CALENDAR_DIR,
            (deps or Deps()).resolved(),
            site,
            limit_tickers,
        ).run()
