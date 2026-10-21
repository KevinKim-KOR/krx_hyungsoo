"""POC6-02 — 맥북 단계 실행 · RTX 결과 취합(CLI 본문 · PLAN 판정 §3).

- run: snapshot(시장 DB · 보유 한 번 읽기 또는 기존 snapshot 파일) → MEDIAN · RIDGE · HGB 공식 실행 · 재현 확인 ·
  CPU 자원 측정 → 결과 폴더 + RTX PC 실행 묶음. smoke = 1구간 · 지표 없음(시간 · 형식 · 누수 · 표본 수만).
- merge: CPU 공식 결과 폴더 + gpu_result.json → study ID · 입력/recipe/묶음 digest · 실행 코드 해시 · 구간 · 행 ID
  완전 일치를 확인한 뒤 새 폴더에 쓴다. OK = `gpu_merged/`(네 방법 · 한 번만) · OK 아님 = `gpu_attempts/<시각>_<상태>/`
  (부분 완료 기록 · 뒤의 OK 취합을 막지 않음). 대조 실패 = MergeError(아무것도 쓰지 않음).
  취합 전 CPU 폴더를 잠긴 입력에서 다시 계산해 보고서 전체(구간별 시간 제외 · 실행 기록은 그대로)와
  묶음 표본이 같은지 확인한다(검증자 r2 — 칸별 대조 대신 전체 재계산). input_snapshot.json 계약 · digest ·
  recipe 해시 · 묶음 내용 digest · GPU 결과 칸 형식 · OK 의 재현 차 ≤ 허용값도 본다.
"""

from __future__ import annotations

import json
import math
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from app.d20_pooled import env, mlp
from app.d20_pooled import report as R
from app.d20_pooled import study as S
from app.d20_pooled.snapshot import (
    SnapshotError,
    build_snapshot,
    digest,
    load_snapshot,
)
from app.reentry_review import prices

_KST = timezone(timedelta(hours=9))
GPU_INPUT_SCHEMA = "poc6_02_gpu_input_v1"


class MergeError(Exception):
    """RTX 결과를 이 실험에 붙일 수 없음(다른 실험 · 손상 · 누락 · 중복)."""


def recipe_digest() -> str:
    return prices.canonical_hash(S.RECIPE)


def gpu_bundle_input(
    prep: dict[str, Any], *, study_id: str, input_digest: str, smoke: bool
) -> dict[str, Any]:
    body = {
        "schema": GPU_INPUT_SCHEMA,
        "study_id": study_id,
        "input_digest": input_digest,
        "recipe_digest": recipe_digest(),
        "mlp_spec": mlp.SPEC,
        "code_sha256": R.code_sha256(R.HERE),
        **S.gpu_input(prep, smoke=smoke),
    }
    return {**body, "bundle_digest": prices.canonical_hash(body)}


def run(*, snapshot_path: Optional[Path] = None, smoke: bool = False) -> Path:
    started = time.perf_counter()
    created = datetime.now(_KST)
    sid = f"{created.strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:8]}" + (
        "_smoke" if smoke else ""
    )
    if snapshot_path is not None:
        snap = load_snapshot(Path(snapshot_path))
    else:
        snap = build_snapshot()
    in_digest = digest(snap)
    cpu = S.run_cpu(snap, smoke=smoke)
    resources: dict[str, Any] = {}
    gin = None
    if cpu["status"] in (S.COMPLETED, "SMOKE"):
        X, y, w = S.pooled_xyw(cpu["prep"], S.block_sets(cpu["prep"], 0))
        resources["hgb_thread_probe"] = env.hgb_thread_probe(X, y, w, S.fit_hgb)
        gin = gpu_bundle_input(
            cpu["prep"], study_id=sid, input_digest=in_digest, smoke=smoke
        )
    resources["wall_seconds"] = time.perf_counter() - started
    resources["max_rss_mb"] = env.max_rss_mb()
    rep = R.build_report(
        study_id=sid,
        created_at=created.isoformat(timespec="seconds"),
        snap=snap,
        cpu=cpu,
        input_digest=in_digest,
        recipe_digest=recipe_digest(),
        environment=env.environment(),
        resources=resources,
        smoke=smoke,
    )
    return R.write_run(rep, snap, gin)


def _load(path: Path) -> dict[str, Any]:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise MergeError(
            f"파일을 읽을 수 없음: {Path(path).name} ({type(e).__name__})"
        ) from e


def _comparable(report: dict) -> dict:
    """구간별 학습 · 예측 시간만 뺀 사본(JSON 왕복) — 같은 입력이어도 실행마다 다르다.

    생성 시각 · 환경 · 자원은 다시 계산할 때 보고서 값을 그대로 넘기므로 비교에서 빼지 않아도 같다
    (다시 만들 수 없는 실행 기록 · 취합 보고서에 그대로 옮긴다).
    """
    body = json.loads(json.dumps(report, ensure_ascii=False))
    for blk in body.get("blocks") or []:
        if isinstance(blk, dict):
            blk.pop("seconds", None)
    return body


def _cpu_libs(environment: Any) -> Any:
    e = environment if isinstance(environment, dict) else {}
    libs = e.get("libraries") if isinstance(e.get("libraries"), dict) else {}
    return e.get("python"), {k: v for k, v in libs.items() if k != "torch"}


def _cpu_folder_problem(run_dir: Path, rep: dict, inp: dict) -> Optional[str]:
    """취합 전 CPU 결과 폴더 확인 — 디스크의 보고서를 믿지 않고 잠긴 입력에서 다시 계산해 같아야 한다.

    다시 계산 = 같은 input_snapshot · recipe 로 CPU 단계 전체(세 방법 재학습 · 재현 확인 1회는 생략). 시험 행(ID · 종목 ·
    날짜 · 정답 · 예측) · 점수 · 판정 · 진단 · 적격 · 경계 · 구간 · 한계 · recipe 가 구간별 시간만 빼고 완전히 같아야
    한다. 묶음 입력의 표본도 같은 입력에서 다시 만들어 같아야 한다. 칸을 하나씩 대조하지 않는다(검증자 r2).
    """
    try:
        snap = load_snapshot(run_dir / "input_snapshot.json")
    except SnapshotError as e:
        return f"input_snapshot.json: {e}"
    if digest(snap) != rep.get("input_digest"):
        return "input_snapshot.json 이 보고서의 입력 digest 와 다름"
    if prices.canonical_hash(rep.get("recipe")) != rep.get("recipe_digest"):
        return "report.json 의 recipe 가 recipe digest 와 다름"
    body = {k: v for k, v in inp.items() if k != "bundle_digest"}
    if prices.canonical_hash(body) != inp.get("bundle_digest"):
        return "gpu_input.json 내용이 bundle digest 와 다름"
    try:
        cpu = S.run_cpu(snap, repeat_check=False)
    except S.StudyError as e:
        return f"잠긴 입력에서 CPU 단계를 다시 계산할 수 없음: {e}"
    if cpu["status"] != S.COMPLETED:
        return f"잠긴 입력에서 다시 계산한 CPU 단계 상태 {cpu['status']}"
    again = R.build_report(
        study_id=rep.get("study_id"),
        created_at=rep.get("created_at"),
        snap=snap,
        cpu=cpu,
        input_digest=rep.get("input_digest"),
        recipe_digest=rep.get("recipe_digest"),
        environment=rep.get("environment"),
        resources=rep.get("resources"),
        smoke=False,
    )
    want, got = _comparable(again), _comparable(rep)
    if want != got:
        key = next(k for k in sorted(set(want) | set(got)) if want.get(k) != got.get(k))
        env_note = (
            " · CPU 계산 환경(Python · 라이브러리 판)도 실험 때와 다름"
            if _cpu_libs(rep.get("environment")) != _cpu_libs(env.environment())
            else ""
        )
        return (
            f"report.json 이 잠긴 입력에서 다시 계산한 결과와 다름(칸 {key}){env_note}"
        )
    redo = json.loads(json.dumps(S.gpu_input(cpu["prep"])))
    if redo != {k: inp.get(k) for k in redo}:
        return "gpu_input.json 표본이 잠긴 입력에서 다시 만든 값과 다름"
    return None


def _gpu_result_problem(res: dict) -> Optional[str]:
    for k in ("env", "resources"):
        if res.get(k) is not None and not isinstance(res[k], dict):
            return f"gpu_result.json {k} 형식 다름"
    if res.get("reason") is not None and not isinstance(res["reason"], str):
        return "gpu_result.json reason 형식 다름"
    if res.get("status") == "OK":
        diff = res.get("repeat_max_abs_diff")
        ok = isinstance(diff, (int, float)) and not isinstance(diff, bool)
        if not ok or not math.isfinite(diff) or diff > mlp.REPRO_TOL:
            return "OK 인데 같은 입력 두 학습의 예측 차이가 허용값 밖 · 없음"
    return None


def merge(run_dir: Path, gpu_result_path: Path) -> Path:
    run_dir = Path(run_dir)
    rep = _load(run_dir / "report.json")
    inp = _load(run_dir / "gpu_bundle" / "gpu_input.json")
    res = _load(gpu_result_path)
    if rep.get("stage") != "CPU" or rep.get("status") != S.COMPLETED:
        raise MergeError(
            "CPU 공식 결과 폴더가 아님(smoke · 자료 부족 · 확인 필요 결과에는 붙이지 않음)"
        )
    if res.get("schema") != "poc6_02_gpu_result_v1":
        raise MergeError("GPU 결과 파일 형식이 다름")
    if res.get("status") not in R.GPU_STATUSES:
        raise MergeError(f"알 수 없는 GPU 상태 {res.get('status')!r}")
    for key in ("study_id", "input_digest", "recipe_digest"):
        if not (rep.get(key) == inp.get(key) == res.get(key)):
            raise MergeError(f"{key} 불일치 — 다른 실험의 결과")
    if res.get("bundle_digest") != inp.get("bundle_digest"):
        raise MergeError("bundle_digest 불일치 — 다른 묶음의 결과")
    if rep["recipe_digest"] != recipe_digest():
        raise MergeError("지금 코드의 recipe 가 실험 때와 다름")
    problem = _cpu_folder_problem(run_dir, rep, inp) or _gpu_result_problem(res)
    if problem:
        raise MergeError(problem)
    if res.get("status") == "OK":
        local = R.code_sha256(run_dir / "gpu_bundle")
        if not (res.get("code_sha256") == inp.get("code_sha256") == local):
            raise MergeError("실행 코드(mlp.py · gpu_runner.py) 해시가 묶음과 다름")
        want = [b["test_ids"] for b in inp["blocks"]]
        got = [b.get("test_ids") for b in res.get("blocks") or []]
        if want != got:
            raise MergeError("구간 · 행 ID 가 묶음 입력과 다름(누락 · 중복 · 순서)")
    try:
        merged = R.merge_report(rep, res)
    except ValueError as e:
        raise MergeError(str(e)) from e
    merged["merged_at"] = datetime.now(_KST).isoformat(timespec="seconds")
    return R.write_merged(run_dir, merged)
