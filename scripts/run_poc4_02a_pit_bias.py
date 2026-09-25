"""POC4-02A — KRX PIT universe 생존편향 측정 러너 (PLAN §4 실행 규율 · §8 재개 · 설계자 판정 §12).

실행:
  python scripts/run_poc4_02a_pit_bias.py run --out-dir <새 폴더> [--limit-dates N]
  python scripts/run_poc4_02a_pit_bias.py run --out-dir <멈춘 실행 폴더> --resume
  python scripts/run_poc4_02a_pit_bias.py compare --first <DIR1> --second <DIR2>

산출물 (실행 폴더 안 · 모두 새로 만들기만 한다 — 덮어쓰기 없음):
  run_manifest.json  시작 때 한 번 — 인자 · 입력 지문 · 봉인 검증 · 코드 출처 · 환경 · recipe
  progress/<ARM>_<YYYY-MM-DD>.json  arm·신호일 단위 기록 (지문 포함 · 재개 때 재사용)
  result.json · run_manifest_final.json (끝날 때 — canonical hash · 날짜별 분할 기록)
  run_meta.json  시간·메모리 (비결정) · guard_failed.json  가드가 거부한 폴더 표식 (재개 금지)
  determinism_compare.json  compare 결과 (두 번째 폴더에)

규율: 봉인 DB 는 읽기 전용 URI 로만 · 실행 중 sqlite 연결은 봉인 DB 경로만 · 실행 전후 봉인 검증이
같아야 결과를 쓴다 · 라이브 5경로가 처음 시작(재개면 manifest 기록)과 끝에 같아야 결과를 쓴다 ·
실행 폴더는 legacy 결과 폴더·라이브 5경로 아래에 두지 않는다 · 외부 호출 0.
exit code: run 0 = 두 arm MEASURED · 3 = 막힌 arm 이 있음(결과는 쓴다 · 그 arm 지표 없음) ·
compare 0 = 결정성 확인 · 1 = hash 다름 · 2 = hash 같지만 재개한 실행이 끼어 있음(PLAN §8).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import resource
import sys
import time
from pathlib import Path
from typing import Optional

_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from app.krx_sealed_reader import (  # noqa: E402
    SEALED_VERSION,
    SealedSourceError,
    assert_same_source,
    load_panel,
    verify_sealed_source,
)
from app.ml_baseline_provenance import (  # noqa: E402
    code_provenance,
    environment,
    node_info,
)
from app.ml_baseline_snapshot import (  # noqa: E402
    SnapshotIntegrityError,
    file_sha256,
    guard_sqlite_paths,
    new_run_dir,
)
from app.ml_pit_bias_eval import build_context, evaluate_point  # noqa: E402
from app.ml_pit_bias_report import (  # noqa: E402
    CANONICAL_EXCLUDED,
    MEASURED,
    TRACK,
    build_result,
    recipe_block,
)
from app.ml_pit_universe import ARM_CONTROL, ARM_PIT, ARMS, arm_codes  # noqa: E402
from app.ml_score_validity_eval import (  # noqa: E402
    assert_evaluation_window,
    build_calendar,
)
from app.ml_score_validity_report import canonical_sha256, now_iso  # noqa: E402

MANIFEST_SCHEMA = "poc4_02a_run_manifest.v1"
FINAL_SCHEMA = "poc4_02a_run_manifest_final.v1"
PROGRESS_SCHEMA = "poc4_02a_progress.v1"
META_SCHEMA = "poc4_02a_run_meta.v1"
GUARD_SCHEMA = "poc4_02a_guard_failed.v1"
COMPARE_SCHEMA = "poc4_02a_determinism_compare.v1"
RUN_MANIFEST = "run_manifest.json"
RUN_MANIFEST_FINAL = "run_manifest_final.json"
RESULT = "result.json"
RUN_META = "run_meta.json"
GUARD_FAILED = "guard_failed.json"
COMPARE = "determinism_compare.json"
PROGRESS_DIR = "progress"
SEALED_DB_REL = Path("state/ml/research/krx_etf_universe.sqlite")
E2_MANIFEST_REL = Path(
    "state/ml/baselines/relative_upside_v1_snap_20260921/dataset_manifest.json"
)
LEGACY_ROOT_REL = Path("state/ml/validity")
# POC4-01 사고에서 전체 회귀가 실제로 쓴 라이브 경로 5곳 (tests/conftest.py 와 같은 목록).
LIVE_WATCH_FILES = (
    "state/market/market_data.sqlite",
    "state/market/nav_discount_refresh_latest.json",
    "logs/oci_market_data_batch.log",
    "logs/three_push_runtime_cron.log",
)
LIVE_WATCH_DIRS = ("state/runs",)
# A2 — manifest 날짜별 분할 기록에 split 블록과 함께 싣는 레코드 필드.
SPLIT_RECORD_KEYS = ("signal_date", "train_row_count", "test_row_count")
SPLIT_RECORD_KEYS += ("max_input_date", "max_target_end_date")


class RunnerError(RuntimeError):
    """실행 규율 위반 — 재개 지문 불일치 · 라이브 경로 변경 · 완료된 폴더 재개 등."""


def _logger() -> logging.Logger:
    lg = logging.getLogger("poc4_02a_pit_bias")
    if not lg.handlers:
        h = logging.StreamHandler()
        h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s: %(message)s"))
        lg.addHandler(h)
    lg.setLevel(logging.INFO)
    return lg


def _sha_json(obj) -> str:
    blob = json.dumps(obj, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def write_new(path: Path, payload: dict) -> str:
    """배타 생성(`x`) — 이미 있으면 `FileExistsError`. 쓴 텍스트를 돌려준다."""
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    with open(path, "x", encoding="utf-8") as fh:
        fh.write(text)
    return text


def live_fingerprint(root: Path) -> dict:
    """라이브 5경로 — 파일 4개 sha256(없으면 None) + `state/runs` 정렬 목록."""
    out: dict = {}
    for rel in LIVE_WATCH_FILES:
        path = root / rel
        out[rel] = file_sha256(path) if path.is_file() else None
    for rel in LIVE_WATCH_DIRS:
        path = root / rel
        out[rel] = sorted(os.listdir(path)) if path.is_dir() else None
    return out


def _peak_rss() -> dict:
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    unit = "bytes" if sys.platform == "darwin" else "kilobytes"
    return {"ru_maxrss": value, "unit": unit}


def _load_e2(path: Path) -> tuple[list[str], str]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    return list(manifest["evaluation_calendar"]["e2_dates"]), file_sha256(path)


def _points(dates: list[str], e2_dates: list[str], limit: Optional[int]) -> list:
    wanted = set(e2_dates)
    points = [
        p for p in build_calendar(dates, months_ahead=1) if p.signal_date in wanted
    ]
    if limit:
        points = points[-limit:]  # 스모크 — official=false
    else:
        assert_evaluation_window([p.signal_date for p in points], e2_dates)
    return points


def _code_fingerprint(code: dict) -> dict:
    """고정 모듈 + 실제 import 된 app/·scripts/ 모듈의 정규화 AST hash."""
    modules = {**code["frozen_modules"], **code["evaluator_modules"]}
    return {k: v["normalized_ast_sha256"] for k, v in sorted(modules.items())}


def input_fingerprint(source: dict, e2_sha: str, points: list, code, args) -> dict:
    return {
        "sealed_version": source["version_id"],
        "sealed_content_sha256": source["content_sha256"],
        "sealed_file_sha256": source["file_sha256"],
        "e2_manifest_sha256": e2_sha,
        "code_normalized_ast": _code_fingerprint(code),
        "config_sha256": _sha_json(recipe_block()),
        "evaluation_dates_sha256": _sha_json(
            [
                [p.signal_date, p.entry_date, p.next_signal_date, p.exit_date]
                for p in points
            ]
        ),
        "options": {"limit_dates": args.limit_dates},
    }


def _load_progress(path: Path, arm: str, date: str, fp_sha: str) -> dict:
    unit = json.loads(path.read_text(encoding="utf-8"))
    if (
        unit.get("schema_version") != PROGRESS_SCHEMA
        or unit.get("arm") != arm
        or unit.get("signal_date") != date
        or unit.get("fingerprint_sha256") != fp_sha
    ):
        raise RunnerError(
            f"progress 기록이 이번 입력 지문과 다르다 — 재개 불가: {path.name}"
        )
    return unit["record"]


# --- run ----------------------------------------------------------------------------


def _is_under(path: Path, root: Path) -> bool:
    """path 가 root 이거나 그 아래인지 — resolve 비교 + 있는 조상 samefile(대소문자·별칭 경로)."""
    path, root = path.resolve(), root.resolve()
    if path == root or path.is_relative_to(root):
        return True
    if not root.exists():
        return False
    return any(a.exists() and os.path.samefile(a, root) for a in (path, *path.parents))


def _check_out_dir(out_dir: Path, root: Path) -> None:
    """legacy 결과 폴더 · 감시 대상 라이브 5경로 아래에는 실행 폴더를 두지 않는다 (공통 규칙 3·10)."""
    if _is_under(out_dir, root / LEGACY_ROOT_REL):
        raise SnapshotIntegrityError("기존(legacy) 결과 폴더와 그 하위에는 쓰지 않는다")
    for rel in (*LIVE_WATCH_FILES, *LIVE_WATCH_DIRS):
        if _is_under(out_dir, root / rel):
            raise RunnerError(f"감시 대상 라이브 경로 아래에는 쓰지 않는다: {rel}")


def _open_run_dir(args, root: Path) -> Path:
    _check_out_dir(Path(args.out_dir), root)
    if not args.resume:
        out_dir = new_run_dir(Path(args.out_dir), forbidden_root=root / LEGACY_ROOT_REL)
        out_dir.mkdir(parents=True)
        return out_dir
    out_dir = Path(args.out_dir).resolve()
    if not (out_dir / RUN_MANIFEST).is_file():
        raise RunnerError(f"재개할 {RUN_MANIFEST} 가 없다: {out_dir}")
    if (out_dir / GUARD_FAILED).exists():
        raise RunnerError(
            f"실행 규율 가드가 결과를 거부한 폴더다 — 재개하지 않는다(새 폴더로 처음부터): "
            f"{out_dir / GUARD_FAILED}"
        )
    if (out_dir / RESULT).exists():
        raise RunnerError(
            f"이미 끝난 실행이다 — 최종 결과는 덮어쓰지 않는다: {out_dir}"
        )
    return out_dir


def _mark_guard_failed(out_dir: Path, guard: str, detail) -> None:
    """가드가 결과를 거부한 실행 폴더 표식(배타 생성) — `--resume` 이 이 폴더를 다시 열지 않는다."""
    payload = {"schema_version": GUARD_SCHEMA, "track": TRACK, "guard": guard}
    write_new(out_dir / GUARD_FAILED, {**payload, "detail": detail, "at": now_iso()})


def _run(args, root: Path) -> int:
    log = _logger()
    wall0 = time.perf_counter()
    started = now_iso()
    sealed = Path(args.sealed_db or root / SEALED_DB_REL).resolve()
    e2_path = Path(args.e2_manifest or root / E2_MANIFEST_REL).resolve()
    live_before = live_fingerprint(root)  # 실행 폴더를 만들기 전에 잰다
    out_dir = _open_run_dir(args, root)
    try:
        return _execute(
            args, root, out_dir, (sealed, e2_path), live_before, (started, wall0), log
        )
    finally:
        if not args.resume and out_dir.is_dir() and not any(out_dir.iterdir()):
            out_dir.rmdir()  # 아무것도 못 쓰고 끝난 새 실행은 빈 폴더를 남기지 않는다


def _execute(args, root, out_dir, inputs, live_before, clock, log) -> int:
    sealed, e2_path = inputs
    started, wall0 = clock
    code = code_provenance()
    with guard_sqlite_paths([sealed]):
        before = verify_sealed_source(sealed, version_id=SEALED_VERSION)
        log.info(
            "봉인 검증 ok — %s %s", before["version_id"], before["content_sha256"][:16]
        )
        panel = load_panel(sealed, version_id=SEALED_VERSION)
        e2_dates, e2_sha = _load_e2(e2_path)
        points = _points(panel.dates, e2_dates, args.limit_dates)
        codes = {arm: arm_codes(panel, arm) for arm in ARMS}
        fp = input_fingerprint(before, e2_sha, points, code, args)
        fp_sha = _sha_json(fp)
        if args.resume:
            manifest = json.loads((out_dir / RUN_MANIFEST).read_text(encoding="utf-8"))
            if manifest.get("fingerprint_sha256") != fp_sha:
                old = manifest.get("fingerprint", {})
                diff = sorted(k for k in set(old) | set(fp) if old.get(k) != fp.get(k))
                raise RunnerError(
                    f"입력 지문이 다르다 — 재개하지 않는다 (새 폴더로 처음부터): {diff}"
                )
            run_start_live = manifest.get("live_paths_before")
            if not isinstance(run_start_live, dict):
                raise RunnerError(f"{RUN_MANIFEST} 에 실행 시작 라이브 지문이 없다")
            log.info("재개 — 지문 일치 %s", fp_sha[:16])
        else:
            manifest = _manifest(args, sealed, e2_path, before, fp, fp_sha, points)
            manifest.update(_manifest_context(panel, codes, code, live_before, started))
            write_new(out_dir / RUN_MANIFEST, manifest)
            (out_dir / PROGRESS_DIR).mkdir()
            run_start_live = live_before
        ctx = build_context(panel)
        records, reused, computed = {arm: [] for arm in ARMS}, 0, 0
        for arm in ARMS:
            for i, point in enumerate(points, 1):
                t0 = time.perf_counter()
                path = out_dir / PROGRESS_DIR / f"{arm}_{point.signal_date}.json"
                if path.exists():
                    rec = _load_progress(path, arm, point.signal_date, fp_sha)
                    reused += 1
                else:
                    unit = {
                        "schema_version": PROGRESS_SCHEMA,
                        "arm": arm,
                        "signal_date": point.signal_date,
                        "fingerprint_sha256": fp_sha,
                        "record": evaluate_point(ctx, arm, codes[arm], point),
                    }
                    rec = json.loads(write_new(path, unit))["record"]
                    computed += 1
                records[arm].append(rec)
                log.info(
                    "[%s %d/%d] %s ic=%s n=%d cov=%s scored=%d (%.1fs)",
                    arm,
                    i,
                    len(points),
                    point.signal_date,
                    None if rec["ic_filter"] is None else round(rec["ic_filter"], 4),
                    rec["n_filter"],
                    None if rec["coverage"] is None else round(rec["coverage"], 3),
                    rec["scored_count"],
                    time.perf_counter() - t0,
                )
        try:
            after = verify_sealed_source(sealed, version_id=SEALED_VERSION)
            assert_same_source(before, after)
        except SealedSourceError as exc:
            _mark_guard_failed(out_dir, "SEALED_SOURCE_CHANGED", str(exc))
            raise
    bench = panel.benchmark()
    payload = build_result(
        official=args.limit_dates is None,
        source={"before": before, "after": after, "same": True},
        calendar=_calendar_block(panel, e2_dates, e2_sha, points, args.limit_dates),
        universe=_universe_block(panel, codes),
        records=records,
        benchmark_closes={
            d: c for d, c in zip(bench.dates, bench.chain) if c is not None
        },
    )
    payload["determinism"]["canonical_sha256"] = canonical_sha256(
        payload, exclude=CANONICAL_EXCLUDED
    )
    live_after = live_fingerprint(root)
    # 재개한 실행은 이번 세션 시작만이 아니라 처음 시작(manifest 기록)과도 비교한다.
    befores = (live_before, run_start_live)
    keys = sorted(set(live_after).union(*befores))
    changed = [k for k in keys if any(b.get(k) != live_after.get(k) for b in befores)]
    live = {
        "run_start": run_start_live,
        "session_before": live_before,
        "after": live_after,
        "changed": changed,
    }
    if changed:
        _mark_guard_failed(out_dir, "LIVE_PATHS_CHANGED", live)
        raise RunnerError(
            f"실행 중 라이브 경로가 바뀌었다 — 결과를 쓰지 않는다: {changed}"
        )
    write_new(out_dir / RESULT, payload)
    write_new(
        out_dir / RUN_MANIFEST_FINAL,
        _final_manifest(out_dir, args, fp_sha, payload, records, after, live),
    )
    statuses = {arm: payload["arms"][arm]["status"] for arm in ARMS}
    exit_code = 0 if all(s == MEASURED for s in statuses.values()) else 3
    write_new(
        out_dir / RUN_META,
        {
            "schema_version": META_SCHEMA,
            "track": TRACK,
            "status": statuses,
            "exit_code": exit_code,
            "final_manifest": RUN_MANIFEST_FINAL,
            "resumed": bool(args.resume),
            "progress_reused": reused,
            "progress_computed": computed,
            "started_at": started,
            "finished_at": now_iso(),
            "elapsed_seconds": round(time.perf_counter() - wall0, 2),
            "peak_rss": _peak_rss(),
            "node": node_info(),
        },
    )
    log.info(
        "완료 %s → %s (%.1fs)", statuses, out_dir / RESULT, time.perf_counter() - wall0
    )
    return exit_code


def _manifest(args, sealed, e2_path, before, fp, fp_sha, points) -> dict:
    return {
        "schema_version": MANIFEST_SCHEMA,
        "track": TRACK,
        "official": args.limit_dates is None,
        "arguments": {
            "out_dir": str(Path(args.out_dir).resolve()),
            "limit_dates": args.limit_dates,
            "sealed_db": str(sealed),
            "e2_manifest": str(e2_path),
        },
        "fingerprint": fp,
        "fingerprint_sha256": fp_sha,
        "sealed_source_before": before,
        "e2_manifest": {"path": str(e2_path), "sha256": fp["e2_manifest_sha256"]},
        "evaluation": {
            "count": len(points),
            "first": points[0].signal_date if points else None,
            "last": points[-1].signal_date if points else None,
            "dates": [p.signal_date for p in points],
        },
    }


def _manifest_context(panel, codes, code, live, started) -> dict:
    return {
        "panel": {
            "trading_days": len(panel.dates),
            "first_date": panel.dates[0],
            "last_date": panel.final_date,
            "codes": len(panel.series),
        },
        "universe_codes": {arm: len(codes[arm]) for arm in ARMS},
        "code": {**code, "code_committed": bool(code["git"].get("code_clean"))},
        "environment": environment(),
        "recipe": recipe_block(),
        "live_paths_before": live,
        "external_calls": 0,
        "final_manifest": RUN_MANIFEST_FINAL,
        "final_manifest_note": "시작 manifest 는 한 번만 쓴다 — 결과 canonical hash · 날짜별 분할"
        "·실제 학습 행 수·마지막 학습일 · 실행 후 봉인·라이브 5경로는 끝날 때 이 파일에 배타 생성",
        "started_at": started,
    }


def _split_entry(rec: dict) -> dict:
    """A2 — 신호일 하나의 분할 경계 · trainer 실제 학습 행 수 · 마지막 학습일 (모델 없음이면 None)."""
    base = {"trainer_train_row_count": None, "last_train_date": None, **rec["split"]}
    return {**base, **{k: rec[k] for k in SPLIT_RECORD_KEYS}}


def _final_manifest(out_dir, args, fp_sha, payload, records, after, live) -> dict:
    """run manifest 뒷부분 — 결과를 쓴 뒤 한 번 배타 생성 (PLAN §4 실행 규율 · 판정 A2)."""
    return {
        "schema_version": FINAL_SCHEMA,
        "track": TRACK,
        "official": payload["official"],
        "run_manifest_sha256": file_sha256(out_dir / RUN_MANIFEST),
        "fingerprint_sha256": fp_sha,
        "resumed": bool(args.resume),
        "result": {
            "file": RESULT,
            "canonical_sha256": payload["determinism"]["canonical_sha256"],
            "file_sha256": file_sha256(out_dir / RESULT),
        },
        "sealed_source_after": after,
        "live_paths": {**live, "unchanged": True},
        "split_by_date": {arm: [_split_entry(r) for r in records[arm]] for arm in ARMS},
    }


def _calendar_block(panel, e2_dates, e2_sha, points, limit) -> dict:
    return {
        "basis": "KRX v1 member 날짜(= 069500 유효일) · build_calendar(months_ahead=1) ∩ "
        "기준선 manifest e2_dates (A6)",
        "e2_manifest_sha256": e2_sha,
        "e2_dates_count": len(e2_dates),
        "e2_first": e2_dates[0] if e2_dates else None,
        "e2_last": e2_dates[-1] if e2_dates else None,
        "evaluated_count": len(points),
        "evaluated_first": points[0].signal_date if points else None,
        "evaluated_last": points[-1].signal_date if points else None,
        "limit_dates": limit,
        "trading_days": len(panel.dates),
        "first_trading_day": panel.dates[0],
        "last_trading_day": panel.final_date,
    }


def _universe_block(panel, codes) -> dict:
    return {
        ARM_PIT: {
            "codes": len(codes[ARM_PIT]),
            "definition": "t 에 v1 행이 있는 ETF (069500 제외)",
        },
        ARM_CONTROL: {
            "codes": len(codes[ARM_CONTROL]),
            "final_date": panel.final_date,
            "definition": "PIT 중 최종일에도 v1 행이 있는 ETF (069500 제외 · A5)",
        },
    }


# --- compare ------------------------------------------------------------------------


def _compare_side(folder: Path) -> dict:
    payload = json.loads((folder / RESULT).read_text(encoding="utf-8"))
    stored = payload.get("determinism", {}).get("canonical_sha256")
    recomputed = canonical_sha256(payload, exclude=CANONICAL_EXCLUDED)
    meta_path = folder / RUN_META
    meta = (
        json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.is_file() else {}
    )
    return {
        "dir": str(folder),
        "stored": stored,
        "recomputed": recomputed,
        "stored_matches": stored == recomputed,
        "official": payload.get("official"),
        "run_meta_present": meta_path.is_file(),
        "resumed": meta.get("resumed"),
        "progress_reused": meta.get("progress_reused"),
    }


def _compare(args) -> int:
    first, second = Path(args.first).resolve(), Path(args.second).resolve()
    sides = {"first": _compare_side(first), "second": _compare_side(second)}
    identical = (
        sides["first"]["stored_matches"]
        and sides["second"]["stored_matches"]
        and sides["first"]["recomputed"] == sides["second"]["recomputed"]
    )
    # PLAN §8 — 결정성 확인은 재개 없이 처음부터 두 번 돈(서로 다른) 두 실행으로만 한다.
    fresh = all(
        s["resumed"] is False and s["progress_reused"] == 0 for s in sides.values()
    )
    eligible = fresh and not os.path.samefile(first, second)
    confirmed = identical and eligible
    write_new(
        second / COMPARE,
        {
            "schema_version": COMPARE_SCHEMA,
            "track": TRACK,
            "excluded_fields": list(CANONICAL_EXCLUDED),
            **sides,
            "identical": identical,
            "both_official": all(s["official"] is True for s in sides.values()),
            "determinism_eligible": eligible,
            "determinism_eligibility_rule": "PLAN §8 — 서로 다른 두 폴더 · 둘 다 run_meta "
            "resumed=false · progress_reused=0 (재개 없이 처음부터)",
            "determinism_confirmed": confirmed,
        },
    )
    _logger().info("결정성 비교 identical=%s eligible=%s", identical, eligible)
    return 0 if confirmed else (2 if identical else 1)


def main(
    argv: Optional[list[str]] = None, *, project_root: Path = _PROJECT_ROOT
) -> int:
    parser = argparse.ArgumentParser(description="POC4-02A KRX PIT 생존편향 측정")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="측정 실행 (새 폴더 또는 --resume)")
    run.add_argument("--out-dir", required=True)
    run.add_argument("--resume", action="store_true", help="멈춘 실행 폴더 잇기")
    run.add_argument(
        "--limit-dates", type=int, default=None, help="스모크 — 마지막 N 개"
    )
    run.add_argument("--sealed-db", default=None, help=f"기본 {SEALED_DB_REL}")
    run.add_argument("--e2-manifest", default=None, help=f"기본 {E2_MANIFEST_REL}")
    cmp_ = sub.add_parser("compare", help="두 실행의 canonical hash 비교")
    cmp_.add_argument("--first", required=True)
    cmp_.add_argument("--second", required=True)
    args = parser.parse_args(argv)
    if args.command == "compare":
        return _compare(args)
    if args.limit_dates is not None and args.limit_dates < 1:
        parser.error("--limit-dates 는 1 이상")
    return _run(args, Path(project_root))


if __name__ == "__main__":
    raise SystemExit(main())
