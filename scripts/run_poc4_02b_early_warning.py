"""POC4-02B — 위험 구간 조기감지 기준선 러너 (PLAN §3 · §9 · §11 · 설계 §21).

실행:
  python scripts/run_poc4_02b_early_warning.py run --out-dir <새 폴더>
  python scripts/run_poc4_02b_early_warning.py run --out-dir <중단된 폴더> --resume
  python scripts/run_poc4_02b_early_warning.py compare <실행1 폴더> <실행2 폴더>
  (--skip-legacy-reproduction 은 스모크 전용 → official=false)

단계: reproduce → axes → signals → events → null → report. 단계 결과는 실행 폴더 `progress/<단계>.json` 에
입력 지문과 함께 한 번씩만 쓴다(덮어쓰기 0 · 임시 파일에 다 쓴 뒤 `os.link` 로 원자 게시 — 끊겨도 반쪽 기록 0).
`--resume` 은 지문이 모두 같을 때만 남은 단계를 잇는다.

보호 — 새 폴더(`new_run_dir` · state/ml/validity 금지) · 봉인 source 실행 전후 검증(`assert_same_source` 가
결과 파일보다 먼저) · 라이브 5경로: 첫 시작 지문을 manifest 에 두고 재개 시작·실행 끝마다 그 값과 대조(다르면
report 기록·결과를 쓰지 않고 `guard_failed.json` 을 남긴다 → 그 폴더는 재개 거부) · sqlite 연결은 봉인 DB 와
재현 사본만. 결과 canonical 에 시각 값 0 — 시간·메모리는 `run_meta.json` 에만.

하지 않는 것 — 라이브 DB 직접 연결 · 보고서/feature 표 쓰기 · 네트워크 · OCI · PUSH.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import resource
import sys
import time
import uuid
from pathlib import Path
from typing import Callable, Optional

_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from app import krx_sealed_reader as reader  # noqa: E402
from app import ml_ew_events as ew_events  # noqa: E402
from app import ml_ew_market_axes as ew_axes  # noqa: E402
from app import ml_ew_report as ew_report  # noqa: E402
from app import ml_ew_reproduce as ew_repro  # noqa: E402
from app import ml_ew_signals as ew_signals  # noqa: E402
from app.ml_baseline_provenance import (  # noqa: E402
    code_provenance,
    environment,
    evaluator_hashes,
)
from app.ml_baseline_snapshot import guard_sqlite_paths, new_run_dir  # noqa: E402
from app.ml_score_validity_report import canonical_sha256, now_iso  # noqa: E402

PROJECT_ROOT = _PROJECT_ROOT
FORBIDDEN_ROOT = PROJECT_ROOT / "state" / "ml" / "validity"
MANIFEST_SCHEMA = "poc4_02b_run_manifest.v1"
PROGRESS_SCHEMA = "poc4_02b_progress.v1"
COMPARE_SCHEMA = "poc4_02b_determinism_compare.v1"
RESULT_FILENAME = "poc4_02b_early_warning_result.json"
MANIFEST_FILENAME = "run_manifest.json"
META_FILENAME = "run_meta.json"
COMPARE_FILENAME = "determinism_compare.json"
GUARD_FAILED_FILENAME = "guard_failed.json"
NOT_OFFICIAL_FINAL = (
    "NOT_OFFICIAL_SMOKE"  # 공식 실행이 아닌 비교 — 판정 값을 붙이지 않는다
)
PROGRESS_DIR = "progress"
STAGES = ("reproduce", "axes", "signals", "events", "null", "report")
LIVE_WATCH_FILES = (
    "state/market/market_data.sqlite",
    "state/market/nav_discount_refresh_latest.json",
    "logs/oci_market_data_batch.log",
    "logs/three_push_runtime_cron.log",
)
LIVE_WATCH_DIRS = ("state/runs",)


class RunError(RuntimeError):
    """실행 계약 위반 — 재개 지문 불일치 · 라이브 경로 변경 · 보호 실패 폴더 · 기존 결과 · 기록 손상."""


# --- 파일 · 지문 ----------------------------------------------------------------------------


def _sha256_file(path: Path) -> Optional[str]:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_json(obj) -> str:
    blob = json.dumps(obj, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _dumps(obj, indent: Optional[int] = 2) -> str:
    return json.dumps(
        obj, ensure_ascii=False, indent=indent, sort_keys=True, default=str
    )


def write_text_x(path: Path, text: str) -> None:
    """임시 파일(같은 폴더 · 배타 생성)에 다 쓰고 fsync 한 뒤 `os.link` 로 게시한다.
    최종 경로가 이미 있으면 `FileExistsError` (덮어쓰기 0) · 쓰는 도중 끊기면 최종 경로에는 아무것도 없다."""
    tmp = path.parent / f".{path.name}.{uuid.uuid4().hex}.tmp"
    try:
        with open(tmp, "x", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.link(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def write_json_x(path: Path, obj, indent: Optional[int] = 2) -> str:
    """JSON 을 원자·배타로 쓴다 (`write_text_x`). 쓴 텍스트를 돌려준다."""
    text = _dumps(obj, indent)
    write_text_x(path, text)
    return text


def load_json(path: Path) -> dict:
    """기록을 읽는다 — 읽을 수 없거나 객체가 아니면 파일 이름을 적은 `RunError` (자동 복구 0)."""
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RunError(f"기록을 읽을 수 없다(손상 · 손으로 확인): {path.name} — {exc}")
    if not isinstance(obj, dict):
        raise RunError(f"기록이 JSON 객체가 아니다: {path.name}")
    return obj


def live_fingerprint(live_root: Path) -> dict:
    """라이브 5경로 — 파일 4개 sha256(없으면 None) · state/runs 정렬 목록(없으면 None)."""
    out: dict = {rel: _sha256_file(live_root / rel) for rel in LIVE_WATCH_FILES}
    for rel in LIVE_WATCH_DIRS:
        path = live_root / rel
        out[rel] = sorted(os.listdir(path)) if path.is_dir() else None
    return out


def _member_dates(sealed_db: Path) -> list[str]:
    con = reader.open_readonly(sealed_db)
    try:
        return [
            r[0]
            for r in con.execute(
                "SELECT bas_dd FROM krx_dataset_member WHERE version_id = ? ORDER BY bas_dd",
                (reader.SEALED_VERSION,),
            )
        ]
    finally:
        con.close()


def config_constants() -> dict:
    """결과에 영향을 주는 설정 상수 전부 (재개 지문의 설정 hash 입력)."""
    return {
        "axes": ew_axes.config(),
        "signals": ew_signals.config(),
        "events": ew_events.config(),
        "report": {
            "core": list(ew_report.CORE),
            "excluded_year": ew_report.EXCLUDED_YEAR,
            "schema": ew_report.SCHEMA,
        },
    }


def input_fingerprint(
    sealed_db: Path, source: dict, legacy_inputs, options: dict
) -> dict:
    """재개 지문 — 봉인 content·파일 hash · 모듈 정규화 AST · 설정 상수 · 평가일 목록 ·
    결과에 영향 주는 인자 · (재현을 하면) 라이브 DB·저장 보고서 sha256."""
    modules = {k: v["normalized_ast_sha256"] for k, v in evaluator_hashes().items()}
    components = {
        "sealed_content_sha256": source["content_sha256"],
        "sealed_file_sha256": source["file_sha256"],
        "module_normalized_ast_sha256": modules,
        "config_sha256": _sha256_json(config_constants()),
        "evaluation_dates_sha256": _sha256_json(_member_dates(sealed_db)),
        "legacy_inputs": legacy_inputs,
        "options": options,
    }
    return {"components": components, "sha256": _sha256_json(components)}


# --- 단계 -----------------------------------------------------------------------------------


def _read_stage(path: Path, name: str, fp: str) -> dict:
    record = load_json(path)
    if (
        record.get("schema") != PROGRESS_SCHEMA
        or record.get("stage") != name
        or record.get("fingerprint_sha256") != fp
        or "data" not in record
    ):
        raise RunError(f"진행 기록이 이 실행의 입력 지문과 다르다: {path.name}")
    return record["data"]


def _stage_text(name: str, fp: str, data: dict) -> str:
    record = {
        "schema": PROGRESS_SCHEMA,
        "stage": name,
        "fingerprint_sha256": fp,
        "data": data,
    }
    return _dumps(record, indent=None)


def run_stage(run_dir: Path, name: str, fp: str, compute: Callable[[], dict]) -> dict:
    """완료된 단계는 기록을 검증해 다시 쓰고, 없으면 계산해 한 번 쓴다. 반환은 항상 JSON 왕복 값."""
    path = run_dir / PROGRESS_DIR / f"{name}.json"
    if path.exists():
        return _read_stage(path, name, fp)
    text = _stage_text(name, fp, compute())
    write_text_x(path, text)
    return json.loads(text)["data"]


def mark_guard_failed(run_dir: Path, reason: str, detail: dict) -> None:
    """보호 검사 실패 표시 — 이 폴더는 더 이상 재개하지 않는다(이미 있으면 그대로 둔다)."""
    try:
        write_json_x(
            run_dir / GUARD_FAILED_FILENAME,
            {"reason": reason, "detail": detail, "recorded_at": now_iso()},
        )
    except FileExistsError:
        pass


def check_live(run_dir: Path, at_start: dict, now: dict, when: str) -> None:
    """라이브 5경로가 첫 시작 지문과 같아야 한다 — 다르면 실패 표시를 남기고 중단(결과 0)."""
    if now == at_start:
        return
    changed = sorted(k for k in at_start if at_start[k] != now.get(k))
    mark_guard_failed(
        run_dir,
        "LIVE_PATHS_CHANGED",
        {"when": when, "changed": changed, "at_start": at_start, "now": now},
    )
    raise RunError(f"실행 중 라이브 경로가 바뀌었다 — 결과를 쓰지 않는다: {changed}")


def _verify(sealed_db: Path) -> dict:
    return reader.verify_sealed_source(sealed_db)


def _prepare(args: argparse.Namespace) -> tuple[Path, bool]:
    out = Path(args.out_dir)
    if args.resume:
        run_dir = out.resolve()
        if not (run_dir / MANIFEST_FILENAME).is_file():
            raise RunError(
                f"--resume: 실행 폴더에 {MANIFEST_FILENAME} 가 없다: {run_dir}"
            )
        if (run_dir / GUARD_FAILED_FILENAME).exists():
            raise RunError(
                f"보호 검사에 실패한 실행 폴더다 — 재개하지 않는다: {run_dir}"
            )
        if (run_dir / RESULT_FILENAME).exists():
            raise RunError(f"이미 완료된 실행이다(결과 파일 있음): {run_dir}")
        return run_dir, True
    run_dir = new_run_dir(out, forbidden_root=FORBIDDEN_ROOT)
    run_dir.mkdir(parents=True)
    (run_dir / PROGRESS_DIR).mkdir()
    return run_dir, False


def _open_run(ctx: dict, before: dict, live_now: dict) -> tuple[dict, dict]:
    """(입력 지문, 첫 시작 라이브 지문) — 새 실행이면 manifest 를 배타 생성(라이브 지문 포함),
    재개면 manifest 의 첫 시작 라이브 지문과 지금을 먼저 대조(다르면 실패 표시) → 입력 지문 대조(다르면 중단)."""
    args = ctx["args"]
    legacy_inputs = None
    if not args.skip_legacy_reproduction:
        legacy_inputs = {
            "live_db_sha256": _sha256_file(ctx["live_db"]),
            "report_sha256": _sha256_file(ctx["report_path"]),
        }
    options = {
        "skip_legacy_reproduction": bool(args.skip_legacy_reproduction),
        "official": ctx["official"],
    }
    fp = input_fingerprint(ctx["sealed_db"], before, legacy_inputs, options)
    manifest_path = ctx["run_dir"] / MANIFEST_FILENAME
    if ctx["resumed"]:
        manifest = load_json(manifest_path)
        live_start = manifest.get("live_paths_at_start")
        if not isinstance(live_start, dict):
            raise RunError(
                f"--resume: {MANIFEST_FILENAME} 에 첫 시작 라이브 지문이 없다"
            )
        check_live(ctx["run_dir"], live_start, live_now, "resume_start")
        stored = manifest.get("fingerprint") or {}
        if stored.get("sha256") != fp["sha256"]:
            old = stored.get("components", {})
            diff = sorted(k for k, v in fp["components"].items() if old.get(k) != v)
            raise RunError(f"--resume: 입력 지문이 다르다 — 중단 {diff}")
        return fp, live_start
    code = code_provenance()
    write_json_x(
        manifest_path,
        {
            "schema": MANIFEST_SCHEMA,
            "track": ew_report.TRACK,
            "args": {k: str(v) for k, v in sorted(vars(args).items())},
            "fingerprint": fp,
            "live_paths_at_start": live_now,
            "sealed_source_before": before,
            "code": code,
            "code_committed": bool(code["git"].get("code_clean")),
            "code_committed_note": "app/·scripts/ 미커밋 변경이 있으면 false (code.git)",
            "environment": environment(),
            "started_at": ctx["started"],
        },
    )
    return fp, live_now


def _run_stages(ctx: dict, key: str) -> dict:
    """reproduce → axes → signals → events → null (단계마다 progress 에 한 번)."""
    args, run_dir, sealed_db = ctx["args"], ctx["run_dir"], ctx["sealed_db"]

    def reproduce() -> dict:
        if args.skip_legacy_reproduction:
            return ew_repro.skipped_record()
        return ew_repro.reproduce_legacy(
            ctx["live_db"], ctx["report_path"], ctx["copy"]
        )

    out = {"legacy": run_stage(run_dir, "reproduce", key, reproduce)}
    out["axes"] = run_stage(
        run_dir,
        "axes",
        key,
        lambda: ew_axes.build_market_axes(reader.load_panel(sealed_db)),
    )
    out["signals"] = run_stage(
        run_dir, "signals", key, lambda: ew_signals.build_signals(out["axes"])
    )
    out["ev_stage"] = run_stage(
        run_dir,
        "events",
        key,
        lambda: ew_events.build_event_stage(out["axes"], out["signals"]),
    )
    out["null"] = run_stage(
        run_dir,
        "null",
        key,
        lambda: ew_report.build_null_stage(
            out["axes"], out["signals"], out["ev_stage"]
        ),
    )
    return out


def run(args: argparse.Namespace) -> dict:
    t0 = time.perf_counter()
    started = now_iso()
    live_root = Path(args.live_root).resolve()
    sealed_db = Path(args.sealed_db).resolve()
    live_before = live_fingerprint(live_root)
    run_dir, resumed = _prepare(args)
    ctx = {
        "args": args,
        "started": started,
        "run_dir": run_dir,
        "resumed": resumed,
        "sealed_db": sealed_db,
        "copy": run_dir / ew_repro.COPY_NAME,
        "live_db": live_root / ew_repro.LIVE_DB_REL,
        "report_path": live_root / ew_repro.REPORT_REL,
        "official": bool(
            not args.skip_legacy_reproduction
            and sealed_db == reader.DEFAULT_SEALED_DB.resolve()
            and live_root == PROJECT_ROOT.resolve()
        ),
    }
    with guard_sqlite_paths([sealed_db, ctx["copy"]]):
        before = _verify(sealed_db)
        fp, live_start = _open_run(ctx, before, live_before)
        key = fp["sha256"]
        stages = _run_stages(ctx, key)
        after = _verify(sealed_db)
        try:
            reader.assert_same_source(before, after)
        except reader.SealedSourceError as exc:
            detail = {"before": before, "after": after, "error": str(exc)}
            mark_guard_failed(run_dir, "SEALED_SOURCE_CHANGED", detail)
            raise
    source = {
        "before": before,
        "after": after,
        "same": True,
        "version_id": before["version_id"],
    }
    # report 는 메모리에서 만들고, 라이브 5경로 대조를 통과한 뒤에만 progress 에 쓴다(실패 시 결과 기록 0).
    report_path = run_dir / PROGRESS_DIR / "report.json"
    report_text = None
    if report_path.exists():
        result = _read_stage(report_path, "report", key)
    else:
        built = ew_report.build_result(
            **stages, source=source, official=ctx["official"]
        )
        report_text = _stage_text("report", key, built)
        result = json.loads(report_text)["data"]
    live_after = live_fingerprint(live_root)
    check_live(run_dir, live_start, live_after, "run_end")
    if report_text is not None:
        write_text_x(report_path, report_text)
    if canonical_sha256(result) != result["determinism"]["canonical_sha256"]:
        raise RunError("결과 canonical sha256 재계산 불일치")
    write_json_x(run_dir / RESULT_FILENAME, result)
    write_json_x(
        run_dir / META_FILENAME,
        {
            "resumed": resumed,
            "started_at": started,
            "finished_at": now_iso(),
            "elapsed_seconds": round(time.perf_counter() - t0, 3),
            "peak_rss_raw": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "peak_rss_unit": "bytes" if sys.platform == "darwin" else "kilobytes",
            "live_paths_at_start": live_start,
            "live_paths_before": live_before,
            "live_paths_after": live_after,
            "result_canonical_sha256": result["determinism"]["canonical_sha256"],
        },
    )
    return result


# --- 두 실행 비교 (조건 11) ------------------------------------------------------------------


def compare(run1: Path, run2: Path) -> dict:
    run1, run2 = Path(run1).resolve(), Path(run2).resolve()
    if run1 == run2:
        raise RunError("같은 실행 폴더끼리는 비교하지 않는다")
    runs = []
    for d in (run1, run2):
        meta_path, result_path = d / META_FILENAME, d / RESULT_FILENAME
        if not result_path.is_file() or not meta_path.is_file():
            raise RunError(f"완료되지 않은 실행: {d}")
        if (d / GUARD_FAILED_FILENAME).exists():
            raise RunError(f"보호 검사에 실패한 실행 폴더다: {d}")
        meta = load_json(meta_path)
        if meta.get("resumed") is not False:
            raise RunError(f"결정성은 재개 없이 처음부터 돈 실행으로만 비교한다: {d}")
        result = load_json(result_path)
        recomputed = canonical_sha256(result)
        if recomputed != result["determinism"]["canonical_sha256"]:
            raise RunError(f"저장된 canonical 과 재계산이 다르다: {d}")
        runs.append((d, result, recomputed))
    identical = runs[0][2] == runs[1][2]
    run_verdict = runs[1][1]["verdict"]
    # 판정은 공식 실행(운영 표 재현 감사 포함) 둘끼리만 — 스모크(official=false)에는 판정 값을 붙이지 않는다.
    official_both = all(r.get("official") is True for _, r, _ in runs)
    final = (
        ew_report.final_verdict(run_verdict, identical)
        if official_both
        else NOT_OFFICIAL_FINAL
    )
    record = {
        "schema": COMPARE_SCHEMA,
        "track": ew_report.TRACK,
        "runs": [
            {
                "dir": str(d),
                "canonical_sha256": c,
                "verdict": r["verdict"],
                "official": r["official"],
            }
            for d, r, c in runs
        ],
        "criterion_11": {
            "basis": "two from-scratch runs canonical identical",
            "value": identical,
        },
        "run_verdict": run_verdict,
        "official_both": official_both,
        "final_verdict": final,
        "note": ew_report.TRACK_B_NOTE,
        "compared_at": now_iso(),
    }
    write_json_x(run2 / COMPARE_FILENAME, record)
    return record


# --- CLI ------------------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    r = sub.add_parser("run", help="실행 (새 폴더 또는 --resume)")
    r.add_argument("--out-dir", required=True)
    r.add_argument("--resume", action="store_true")
    r.add_argument("--skip-legacy-reproduction", action="store_true")
    r.add_argument("--sealed-db", default=str(reader.DEFAULT_SEALED_DB))
    r.add_argument("--live-root", default=str(PROJECT_ROOT))
    c = sub.add_parser("compare", help="두 실행 canonical 비교 (조건 11)")
    c.add_argument("run1")
    c.add_argument("run2")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "compare":
        record = compare(Path(args.run1), Path(args.run2))
        print(json.dumps(record, ensure_ascii=False, indent=2))
        return 0
    result = run(args)
    print(
        json.dumps(
            {
                "verdict": result["verdict"],
                "official": result["official"],
                "canonical_sha256": result["determinism"]["canonical_sha256"],
                "events": result["events"]["by_status"],
                "legacy_reproduction": result["legacy_reproduction"]["status"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
