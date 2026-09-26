"""POC4-03 — RF 대 20일 모멘텀 최종 Kill Gate 러너 (PLAN §2 · 설계자 PLAN 판정 2026-09-25).

실행:
  python scripts/run_poc4_03_rf_kill_gate.py run --arm PIT --out-dir <새 폴더> [--limit-dates N]
  python scripts/run_poc4_03_rf_kill_gate.py run --arm PIT --out-dir <멈춘 폴더> --resume
  python scripts/run_poc4_03_rf_kill_gate.py compare --first <DIR1> --second <DIR2>
  python scripts/run_poc4_03_rf_kill_gate.py summarize --pit <DIR> --control <DIR> --out <새 파일>

순서(필수 보완 C): PIT run1 → PIT run2 → compare(최종 판정) → PIT 가 PASS 일 때만 CONTROL 2회 → summarize.

산출물(실행 폴더 · 새로 만들기만 한다): run_manifest.json · progress/<ARM>_<날짜>.json · result.json ·
run_manifest_final.json · run_meta.json(시간·메모리) · guard_failed.json(가드 거부 표식) ·
determinism_compare.json.

규율: 봉인 DB 는 읽기 전용 URI 로만 · 실행 중 sqlite 는 봉인 DB 만 · 봉인·라이브 5경로·02A 기준 산출물이 전후
같아야 결과를 쓴다 · 선형 기록이 02A 와 다르면 그 날짜에서 멈춘다 · perf_counter 4시간·RSS 10×10^9 바이트를
넘으면 멈춘다 · RF·모멘텀 날짜별 지표는 로그에 찍지 않는다 · 외부 호출 0.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sys
from pathlib import Path
from typing import Optional

_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from app import ml_rf_gate_models as rfm  # noqa: E402
from app import research_run_guard as guard  # noqa: E402
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
from app.ml_baseline_snapshot import file_sha256, guard_sqlite_paths  # noqa: E402
from app.ml_pit_bias_eval import build_context  # noqa: E402
from app.ml_pit_universe import ARM_CONTROL, ARM_PIT, arm_codes  # noqa: E402
from app.ml_research_split import SplitContractError  # noqa: E402
from app.ml_rf_gate_eval import MODELS, evaluate_point_models  # noqa: E402
from app.ml_rf_gate_verdict import (  # noqa: E402
    CANONICAL_EXCLUDED,
    RESULT_SCHEMA,
    TRACK,
    assert_frozen_recipe,
    build_payload,
    final_verdict,
    pit_control_summary,
    recipe,
    recipe_sha256,
)
from app.ml_score_validity_eval import (  # noqa: E402
    assert_evaluation_window,
    build_calendar,
)
from app.ml_score_validity_report import canonical_sha256  # noqa: E402

PROGRESS_SCHEMA = "poc4_03_progress.v1"
PROGRESS_DIR = "progress"
RUN_MANIFEST_FINAL = "run_manifest_final.json"
COMPARE = "determinism_compare.json"
SEALED_DB_REL = Path("state/ml/research/krx_etf_universe.sqlite")
E2_MANIFEST_REL = Path(
    "state/ml/baselines/relative_upside_v1_snap_20260921/dataset_manifest.json"
)
REFERENCE_DIR_REL = Path("state/ml/research/poc4_02a/run1")
# PLAN §1-2 — 02A 기준 산출물 hash (실행 전 대조 · 다르면 시작하지 않는다).
REFERENCE_EXPECT = {
    "result_json_sha256": (
        "edb1b0f65e55c18a2d3f5f441aa67bfea6b9ac054236d66508639b3b8e5dc57e"
    ),
    "run_manifest_final_sha256": (
        "4e5cd27c2b296540d6a33a3fc60760a285a64f932e60e64be8478f3f04608719"
    ),
    "progress_digest_sha256": (
        "d42913404c46878eb8a2229de22d3b641a971f50d156d35e661fa416cf68656e"
    ),
    "e2_manifest_sha256": (
        "6b9c893823c8252f148b1cbd237b757189419bec8470e15d06a2b454a0ea7dea"
    ),
}
FORCE_CPU_ENV = "ML_RELATIVE_UPSIDE_FORCE_CPU"
ARMS = (ARM_PIT, ARM_CONTROL)


class ReproductionError(guard.RunnerError):
    """선형 기록이 02A 기준 기록과 다르다 — INVALID_STOP(LINEAR_REPRODUCTION_FAILED)."""


def _logger() -> logging.Logger:
    lg = logging.getLogger("poc4_03_rf_kill_gate")
    if not lg.handlers:
        h = logging.StreamHandler()
        h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s: %(message)s"))
        lg.addHandler(h)
    lg.setLevel(logging.INFO)
    return lg


def _sha_json(obj) -> str:
    blob = json.dumps(obj, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def canon(obj) -> str:
    """선형 재현 대조용 canonical 텍스트 (PLAN §2-3)."""
    return json.dumps(
        obj, ensure_ascii=False, sort_keys=True, allow_nan=False, separators=(",", ":")
    )


def reference_digest(ref_dir: Path, e2_path: Path) -> dict:
    for need in (ref_dir / "result.json", ref_dir / RUN_MANIFEST_FINAL, e2_path):
        if not need.is_file():
            raise guard.RunnerError(f"02A 기준 산출물이 없다: {need}")
    files = sorted((ref_dir / PROGRESS_DIR).glob("*.json"))
    lines = "".join(f"{p.name}|{file_sha256(p)}\n" for p in files)
    return {
        "result_json_sha256": file_sha256(ref_dir / "result.json"),
        "run_manifest_final_sha256": file_sha256(ref_dir / RUN_MANIFEST_FINAL),
        "progress_digest_sha256": hashlib.sha256(lines.encode("utf-8")).hexdigest(),
        "e2_manifest_sha256": file_sha256(e2_path),
    }


def _points(dates: list[str], e2_dates: list[str], limit: Optional[int]) -> list:
    wanted = set(e2_dates)
    points = [
        p for p in build_calendar(dates, months_ahead=1) if p.signal_date in wanted
    ]
    if limit:
        return points[-limit:]  # 비공식 스모크
    assert_evaluation_window([p.signal_date for p in points], e2_dates)
    return points


def _linear_checker(ref_dir: Path, arm: str, t: str, sink: dict):
    def check(record: dict) -> None:
        path = ref_dir / PROGRESS_DIR / f"{arm}_{t}.json"
        if not path.is_file():
            raise ReproductionError(f"02A 기준 기록이 없다: {path.name}")
        ref = json.loads(path.read_text(encoding="utf-8"))["record"]
        text = canon(record)
        if text != canon(ref):
            raise ReproductionError(f"{arm} {t} 선형 기록이 02A 기준 기록과 다르다")
        sink["linear_canonical_sha256"] = hashlib.sha256(text.encode()).hexdigest()

    return check


# --- run ------------------------------------------------------------------------------


def _run(args, root: Path, reference_expect: dict, limits: tuple) -> int:
    log = _logger()
    if os.environ.get(FORCE_CPU_ENV, "").lower() == "true":
        raise guard.RunnerError(
            f"{FORCE_CPU_ENV} 가 켜져 있다 — 02A 선형 재현이 깨진다"
        )
    rfm.assert_frozen_config()
    assert_frozen_recipe()
    sealed = Path(args.sealed_db or root / SEALED_DB_REL).resolve()
    e2_path = Path(args.e2_manifest or root / E2_MANIFEST_REL).resolve()
    ref_dir = Path(args.reference_dir or root / REFERENCE_DIR_REL).resolve()
    forbidden = (ref_dir, e2_path.parent)
    guard.check_out_dir(Path(args.out_dir), root, forbidden)
    ref_digest = reference_digest(ref_dir, e2_path)
    if ref_digest != reference_expect:
        raise guard.RunnerError(f"02A 기준 산출물이 PLAN 값과 다르다: {ref_digest}")
    live_before = guard.live_fingerprint(root)
    started_utc = guard.utc_now()
    out_dir = guard.open_run_dir(
        Path(args.out_dir), root, resume=args.resume, extra=forbidden
    )
    rg = guard.ResourceGuard(*limits)
    try:
        return _execute(
            args,
            root,
            out_dir,
            (sealed, e2_path, ref_dir, ref_digest),
            live_before,
            started_utc,
            rg,
            log,
        )
    finally:
        if not args.resume and out_dir.is_dir() and not any(out_dir.iterdir()):
            out_dir.rmdir()


def _fingerprint(before, e2_digest, ref_digest, points, code, args) -> dict:
    import joblib

    modules = {**code["frozen_modules"], **code["evaluator_modules"]}
    env = environment()
    return {
        "arm": args.arm,
        "sealed_content_sha256": before["content_sha256"],
        "sealed_file_sha256": before["file_sha256"],
        "reference_02a": ref_digest,
        "e2_manifest_sha256": e2_digest,
        "code_normalized_ast": {
            k: v["normalized_ast_sha256"] for k, v in sorted(modules.items())
        },
        "rf_config_sha256": rfm.config_sha256(),
        "recipe_sha256": recipe_sha256(),
        "packages": {**env["packages"], "joblib": joblib.__version__},
        "evaluation_dates_sha256": _sha_json(
            [
                [p.signal_date, p.entry_date, p.next_signal_date, p.exit_date]
                for p in points
            ]
        ),
        "options": {"limit_dates": args.limit_dates},
    }


def _threads() -> dict:
    try:
        import threadpoolctl
        import torch

        pools = [
            {
                k: i.get(k)
                for k in ("user_api", "internal_api", "num_threads", "version")
            }
            for i in threadpoolctl.threadpool_info()
        ]
        return {"torch_threads": torch.get_num_threads(), "threadpools": pools}
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


def _manifest_env() -> dict:
    import joblib

    env = environment()
    env["packages"]["joblib"] = joblib.__version__
    env["threads"] = _threads()
    env["omp_env"] = {
        k: v for k, v in sorted(os.environ.items()) if k.startswith(("OMP_", "MKL_"))
    }
    return env


def _execute(args, root, out_dir, inputs, live_before, started_utc, rg, log) -> int:
    sealed, e2_path, ref_dir, ref_digest = inputs
    arm = args.arm
    code = code_provenance()
    manifest_path = out_dir / guard.RUN_MANIFEST
    with guard_sqlite_paths([sealed]):
        before = verify_sealed_source(sealed, version_id=SEALED_VERSION)
        panel = load_panel(sealed, version_id=SEALED_VERSION)
        e2_dates = json.loads(e2_path.read_text(encoding="utf-8"))
        e2_dates = list(e2_dates["evaluation_calendar"]["e2_dates"])
        points = _points(panel.dates, e2_dates, args.limit_dates)
        codes = arm_codes(panel, arm)
        fp = _fingerprint(
            before, ref_digest["e2_manifest_sha256"], ref_digest, points, code, args
        )
        fp_sha = _sha_json(fp)
        if args.resume:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest.get("fingerprint_sha256") != fp_sha:
                old = manifest.get("fingerprint", {})
                diff = sorted(k for k in set(old) | set(fp) if old.get(k) != fp.get(k))
                raise guard.RunnerError(f"입력 지문이 다르다 — 재개하지 않는다: {diff}")
            run_start_live = manifest["live_paths_before"]
            changed = guard.live_changes(live_before, run_start_live)
            if changed:
                guard.mark_guard_failed(out_dir, TRACK, "LIVE_PATHS_CHANGED", changed)
                raise guard.RunnerError(f"재개 전에 라이브 경로가 바뀌었다: {changed}")
        else:
            run_start_live = live_before
            guard.write_new(
                manifest_path,
                {
                    "schema_version": "poc4_03_run_manifest.v1",
                    "track": TRACK,
                    "arm": arm,
                    "official": args.limit_dates is None,
                    "fingerprint": fp,
                    "fingerprint_sha256": fp_sha,
                    "sealed_source_before": before,
                    "live_paths_before": live_before,
                    "code": code,
                    "environment": _manifest_env(),
                    "recipe": recipe(),
                    "evaluation_dates": [p.signal_date for p in points],
                    "started_utc": started_utc,
                    "precondition": "공식 실행 중 다른 무거운 작업 없음 · caffeinate -i",
                    "external_calls": 0,
                },
            )
            (out_dir / PROGRESS_DIR).mkdir()
        ctx = build_context(panel)
        units, reused, computed = [], 0, 0
        for i, point in enumerate(points, 1):
            t = point.signal_date
            try:
                rg.check()
            except guard.ResourceLimitError as exc:
                guard.mark_guard_failed(out_dir, TRACK, "RESOURCE_LIMIT", str(exc))
                raise
            path = out_dir / PROGRESS_DIR / f"{arm}_{t}.json"
            if path.exists():
                unit = json.loads(path.read_text(encoding="utf-8"))
                if (
                    unit.get("schema_version") != PROGRESS_SCHEMA
                    or unit.get("fingerprint_sha256") != fp_sha
                    or unit.get("arm") != arm
                    or unit.get("signal_date") != t
                    or set(unit.get("models", {})) != set(MODELS)
                ):
                    raise guard.RunnerError(
                        f"progress 기록이 이번 실행과 다르다: {path.name}"
                    )
                reused += 1
            else:
                sink: dict = {}
                try:
                    out = evaluate_point_models(
                        ctx,
                        arm,
                        codes,
                        point,
                        check_linear=_linear_checker(ref_dir, arm, t, sink),
                    )
                except ReproductionError as exc:
                    guard.mark_guard_failed(
                        out_dir, TRACK, "LINEAR_REPRODUCTION_FAILED", str(exc)
                    )
                    raise
                except (rfm.RfContractError, SplitContractError) as exc:
                    guard.mark_guard_failed(out_dir, TRACK, "MODEL_CONTRACT", str(exc))
                    raise
                unit = {
                    "schema_version": PROGRESS_SCHEMA,
                    "arm": arm,
                    "signal_date": t,
                    "fingerprint_sha256": fp_sha,
                    **sink,
                    **out,
                }
                unit = json.loads(guard.write_new(path, unit))
                computed += 1
            units.append(unit)
            log.info(
                "[%s %d/%d] %s 완료 · 누적 %.0fs · peak RSS %.2f GB · %s UTC",
                arm,
                i,
                len(points),
                t,
                rg.elapsed(),
                guard.peak_rss_bytes() / 1e9,
                guard.utc_now(),
            )
        try:
            after = verify_sealed_source(sealed, version_id=SEALED_VERSION)
            assert_same_source(before, after)
        except SealedSourceError as exc:
            guard.mark_guard_failed(out_dir, TRACK, "SEALED_SOURCE_CHANGED", str(exc))
            raise
    try:
        ref_after = reference_digest(ref_dir, e2_path)
    except guard.RunnerError as exc:
        ref_after = {"error": str(exc)}
    if ref_after != ref_digest:
        detail = {"before": ref_digest, "after": ref_after}
        guard.mark_guard_failed(out_dir, TRACK, "REFERENCE_CHANGED", detail)
        raise guard.RunnerError("실행 중 02A 기준 산출물이 바뀌었다")
    bench = panel.benchmark()
    closes = {d: c for d, c in zip(bench.dates, bench.chain) if c is not None}
    payload = build_payload(
        arm,
        args.limit_dates is None,
        [p.signal_date for p in points],
        units,
        closes,
        (before, after),
        ref_digest,
    )
    payload["determinism"]["canonical_sha256"] = canonical_sha256(
        payload, exclude=CANONICAL_EXCLUDED
    )
    live_after = guard.live_fingerprint(root)
    changed = guard.live_changes(live_after, live_before, run_start_live)
    if changed:
        guard.mark_guard_failed(out_dir, TRACK, "LIVE_PATHS_CHANGED", changed)
        raise guard.RunnerError(f"실행 중 라이브 경로가 바뀌었다: {changed}")
    try:
        final_state = (
            rg.check()
        )  # 결과를 쓰기 전 마지막 자원 검사 (마지막 날 · 집계 포함)
    except guard.ResourceLimitError as exc:
        guard.mark_guard_failed(out_dir, TRACK, "RESOURCE_LIMIT", str(exc))
        raise
    guard.write_new(out_dir / guard.RESULT, payload)
    guard.write_new(
        out_dir / RUN_MANIFEST_FINAL,
        {
            "schema_version": "poc4_03_run_manifest_final.v1",
            "track": TRACK,
            "arm": arm,
            "run_manifest_sha256": file_sha256(manifest_path),
            "result_file_sha256": file_sha256(out_dir / guard.RESULT),
            "canonical_sha256": payload["determinism"]["canonical_sha256"],
            "sealed_source_after": after,
            "live_paths": {
                "before": live_before,
                "after": live_after,
                "unchanged": True,
            },
        },
    )
    guard.write_new(
        out_dir / guard.RUN_META,
        {
            "schema_version": "poc4_03_run_meta.v1",
            "track": TRACK,
            "arm": arm,
            "resumed": bool(args.resume),
            "progress_reused": reused,
            "progress_computed": computed,
            "resource": final_state,
            "finished_utc": guard.utc_now(),
            "node": node_info(),
        },
    )
    cand = payload.get("verdict_candidate")
    log.info(
        "완료 %s → %s · 후보 %s", arm, out_dir / guard.RESULT, cand and cand["verdict"]
    )
    return 0


# --- compare · summarize ------------------------------------------------------------------


def _compare(args) -> int:
    first, second = Path(args.first).resolve(), Path(args.second).resolve()
    a = guard.compare_side(first, CANONICAL_EXCLUDED, RESULT_SCHEMA)
    b = guard.compare_side(second, CANONICAL_EXCLUDED, RESULT_SCHEMA)
    if a["arm"] != b["arm"]:
        raise guard.RunnerError(f"arm 이 다르다: {a['arm']} · {b['arm']}")
    det = guard.determinism(first, second, a, b)
    final, control_valid = None, None
    if a["arm"] == ARM_PIT:
        final = final_verdict(
            a["payload"].get("verdict_candidate"), det["determinism_confirmed"]
        )
    else:
        control_valid = bool(
            det["determinism_confirmed"]
            and not a["payload"].get("invalid_reasons")
            and not b["payload"].get("invalid_reasons")
        )
    guard.write_new(
        second / COMPARE,
        {
            "schema_version": "poc4_03_determinism_compare.v1",
            "track": TRACK,
            "arm": a["arm"],
            "excluded_fields": list(CANONICAL_EXCLUDED),
            "first": {k: v for k, v in a.items() if k != "payload"},
            "second": {k: v for k, v in b.items() if k != "payload"},
            **det,
            "final_verdict": final,
            "control_diagnostic_valid": control_valid,
            "control_invalid_reasons": (
                b["payload"].get("invalid_reasons") if a["arm"] == ARM_CONTROL else None
            ),
            "compared_utc": guard.utc_now(),
        },
    )
    _logger().info(
        "결정성 비교 %s identical=%s confirmed=%s 최종=%s",
        a["arm"],
        det["identical"],
        det["determinism_confirmed"],
        final and final["verdict"],
    )
    return 0 if det["determinism_confirmed"] else (2 if det["identical"] else 1)


def _summarize(args, root: Path) -> int:
    """PIT·CONTROL 각각 compare 를 마친 두 번째 폴더를 받는다 (determinism_compare.json 필요)."""
    guard.check_out_dir(Path(args.out), root)
    sides = {}
    for key, folder in (("pit", args.pit), ("control", args.control)):
        folder = Path(folder).resolve()
        cmp_path = folder / COMPARE
        if not cmp_path.is_file():
            raise guard.RunnerError(f"compare 를 마친 폴더가 아니다: {folder}")
        payload = guard.compare_side(folder, CANONICAL_EXCLUDED, RESULT_SCHEMA)[
            "payload"
        ]
        sides[key] = (payload, json.loads(cmp_path.read_text(encoding="utf-8")))
    (pit, pit_cmp), (ctl, ctl_cmp) = sides["pit"], sides["control"]
    summary = pit_control_summary(
        pit,
        ctl,
        pit_cmp.get("final_verdict") or {},
        bool(ctl_cmp.get("control_diagnostic_valid")),
    )
    guard.write_new(Path(args.out), summary)
    return 0


def main(
    argv: Optional[list[str]] = None,
    *,
    project_root: Path = _PROJECT_ROOT,
    reference_expect: Optional[dict] = None,
    limits: tuple = (guard.MAX_SECONDS, guard.MAX_RSS_BYTES),
) -> int:
    parser = argparse.ArgumentParser(description="POC4-03 RF 대 모멘텀 최종 Kill Gate")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="arm 하나 실행 (새 폴더 또는 --resume)")
    run.add_argument("--arm", required=True, choices=ARMS)
    run.add_argument("--out-dir", required=True)
    run.add_argument("--resume", action="store_true")
    run.add_argument("--limit-dates", type=int, default=None, help="비공식 스모크")
    run.add_argument("--sealed-db", default=None)
    run.add_argument("--e2-manifest", default=None)
    run.add_argument("--reference-dir", default=None)
    cmp_ = sub.add_parser("compare", help="같은 arm 두 실행의 결정성 · PIT 최종 판정")
    cmp_.add_argument("--first", required=True)
    cmp_.add_argument("--second", required=True)
    summ = sub.add_parser("summarize", help="PIT·CONTROL 진단 결합")
    summ.add_argument("--pit", required=True)
    summ.add_argument("--control", required=True)
    summ.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    if args.command == "compare":
        return _compare(args)
    if args.command == "summarize":
        return _summarize(args, Path(project_root))
    if args.limit_dates is not None and args.limit_dates < 1:
        parser.error("--limit-dates 는 1 이상")
    expect = REFERENCE_EXPECT if reference_expect is None else reference_expect
    return _run(args, Path(project_root), expect, limits)


if __name__ == "__main__":
    raise SystemExit(main())
