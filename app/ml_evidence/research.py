"""POC6-05 — 기존 연구 증거 등록(PC · 판정 Q3 (a) · 원본 바이트 그대로 · 재실행 0).

대상 = POC6-02 · 03 · 04 공식 22파일(내용 중복 1 = 같은 object). 원본 파일은 읽기만 하고 등록 전후 해시가 같은지 본다.
- 봉인 KRX 판(1.86GB · OCI 미전송 계약)은 올리지 않고 경로 · 해시 · 바이트만 참조한다.
- POC5-06 · 08 은 이번 등록 제외(PC 원본 보존 · 폐기 · 보관 완료 아님).
- 과거 연구의 실행 당시 commit 은 미상이다. '코드가 처음 들어간 commit' · '결과서 재현 근거' · GPU `code_sha256` 을
  근거 종류별로 따로 적는다(HEAD · 최초 포함 commit 을 실행 commit 으로 대입하지 않는다).
- 기록 종류 = RETROSPECTIVE_TEST(등록 시각만 오늘로 바꿔 미래 예측 실적으로 세지 않는다).
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from app.ml_evidence import store

P02 = "state/ml/research/poc6_02/20261021T104103_129a89b0"
P03 = "state/ml/research/poc6_03/20261021T161446_3403e974"
P04 = "state/ml/research/poc6_04/20261021T200645_c24b88ce"
_C03 = "compare_20261021T161507_3927699a"

# (상대 경로, 바이트, sha256) — PLAN 부록 A(2026-10-22 실측) 와 같다.
FILES = {
    "POC6-02:20261021T104103_129a89b0": (
        P02,
        [
            (
                "report.json",
                265284,
                "700c55a832834536941055a2e117cab4fb115d53f175f89baa9e79946c71312a",
            ),
            (
                "report.md",
                9171,
                "d8b298288f443fcd936167ebb34848621cfbbb3c5b34c10eaf3923cf6add492a",
            ),
            (
                "input_snapshot.json",
                2779173,
                "eccfce451d20e4f082c2f28b79a29a796a72f7b80979789665bc4b1d6eb1d57b",
            ),
            (
                "gpu_bundle.zip",
                733466,
                "5843829d9c53f97008495caeedad8913dd5fedce5b4164301ba6a008921cdd07",
            ),
            (
                "gpu_bundle/gpu_input.json",
                2369207,
                "21a8c52734718e156edf87ba454181a1ef6f9e33622c6034a12966075587ddda",
            ),
            (
                "gpu_bundle/gpu_runner.py",
                13243,
                "139099338e43b4de8854285eb2b3d05a00acd119891aa62689a05ca957538102",
            ),
            (
                "gpu_bundle/mlp.py",
                6803,
                "930095c04533aae01add24d3219095d1c3fe6e9c0cd9384e5800859a207593a2",
            ),
            (
                "gpu_bundle/run_gpu.bat",
                131,
                "4ee204e61cb70a77101778d65dbb6d6f21d5fd3f1d02809094c5ed81ddedbf48",
            ),
            (
                "gpu_bundle/README_KO.txt",
                1135,
                "b5ee9589baf99ae27ad301b2c26ada54f38a396567b5cb94601db02c318a9c37",
            ),
            (
                "gpu_result.json",
                42880,
                "d5dac74d483dc754094defe2b2ce0eef6db7137d983703f8e6821fa1b17a2b6a",
            ),
            (
                "gpu_merged/report_with_gpu.json",
                302890,
                "85b67c587828ca39297addff273482be09174c25043ddc60f8c7a1435f7f4bfe",
            ),
            (
                "gpu_merged/report_with_gpu.md",
                10467,
                "84dd6bc8cde17d5c74c01b4b816ecd563618380377417d4c7b1167bb7ba07e3e",
            ),
        ],
    ),
    "POC6-03:20261021T161446_3403e974": (
        P03,
        [
            (
                "copy.sqlite",
                3051520,
                "276c29e74b0d100e97d9eaf33b59214ab896329d8e87004384a74503143bb088",
            ),
            (
                "fetch.json",
                10576,
                "709a2837aaa1cdbcb2cf25337b904da206787eb529c7496a06d0f55c537e6213",
            ),
            (
                f"{_C03}/report.json",
                778392,
                "a5ecf0137c3f2541ed31f5e9be90f2623514f17bd0328c849b827754e5dab772",
            ),
            (
                f"{_C03}/report.md",
                70284,
                "4496059ccce94a2aa4cb426f62da8b9095722b54523c61bd31ddabb7ad7aef41",
            ),
        ],
    ),
    "POC6-04:20261021T200645_c24b88ce": (
        P04,
        [
            (
                "manifest.json",
                2110,
                "a2953b3bcc176142f59c10fa035ae8c37193d74abfd665164459d416f20afae7",
            ),
            (
                "a_report_frozen.json",
                265284,
                "700c55a832834536941055a2e117cab4fb115d53f175f89baa9e79946c71312a",
            ),
            (
                "b_snapshot.json",
                671175,
                "0cdb21c490d94818fd1de9afe080c02cc4bffc8cb8de78cee2cf490325ef8d64",
            ),
            (
                "c_snapshot.json",
                3272043,
                "40074f11956fc105d7fac9e04a1296fb5a655be45f3dcf5cccdab6d35d7aa457",
            ),
            (
                "report.json",
                24458,
                "70c575a2f4315d37fdac076764512442762d27515a4d02beb46e377e6d92bd1c",
            ),
            (
                "report.md",
                7843,
                "54392f3242b00d1901387cca469e326635af19f28089950bdf21015d0fb62b0b",
            ),
        ],
    ),
}
ALLOWED_EXPERIMENTS = frozenset(FILES)
_DOCS = "docs/ai_result/POC6/"
_DES = "docs/ai_design/POC6/"
STATIC = {
    "POC6-02:20261021T104103_129a89b0": {
        "step": "POC6-02",
        "result_doc": _DOCS + "POC6-02_ETF_D20_ML_IMPROVEMENT_RESULT.md",
        "decisions": [
            _DES + "POC6-02_ETF_D20_ML_IMPROVEMENT_PLAN_DECISION_2026-10-21.md",
            _DES + "POC6-02_ETF_D20_ML_IMPROVEMENT_RESULT_DECISION_2026-10-21.md",
        ],
        "code_evidence": [
            {
                "kind": "first_commit_containing_code",
                "commit": "6a6fa39e",
                "paths": ["app/d20_pooled/", "scripts/run_d20_pooled_research.py"],
            },
            {
                "kind": "result_doc_recompute",
                "ref": "POC6-02 RESULT §6-11(정정 코드 재계산 = 공식 결과와 같음)",
            },
            {
                "kind": "gpu_code_sha256",
                "ref": "gpu_bundle/gpu_input.json code_sha256(mlp.py · gpu_runner.py)",
            },
        ],
        "predictions": [
            {
                "file": "report.json",
                "json_path": "rows_by_block[][].preds",
                "methods": ["MEDIAN", "RIDGE_EXISTING", "POOLED_HGB"],
            },
            {
                "file": "gpu_result.json",
                "json_path": "blocks[].test_ids · blocks[].pred",
                "methods": ["POOLED_GPU_MLP"],
            },
            {
                "file": "gpu_merged/report_with_gpu.json",
                "json_path": "rows_by_block[][].preds",
                "methods": ["네 방법"],
            },
        ],
        "truth": [{"file": "report.json", "json_path": "rows_by_block[][].truth"}],
        "limits": [
            "원본 안 경로는 이 맥북 기준 · 다른 경로 복원본으로 기존 CLI 무수정 재실행은 증명하지 않음"
        ],
    },
    "POC6-03:20261021T161446_3403e974": {
        "step": "POC6-03",
        "result_doc": _DOCS + "POC6-03_PRICE_HISTORY_BASIS_CONSISTENCY_RESULT.md",
        "decisions": [
            _DES
            + "POC6-03_PRICE_HISTORY_BASIS_CONSISTENCY_PLAN_DECISION_2026-10-21.md",
            _DES
            + "POC6-03_PRICE_HISTORY_BASIS_CONSISTENCY_RESULT_DECISION_2026-10-21.md",
        ],
        "code_evidence": [
            {
                "kind": "first_commit_containing_code",
                "commit": "6a6fa39e",
                "paths": ["app/price_basis_check/", "scripts/run_price_basis_check.py"],
            },
        ],
        "predictions": "not_applicable(성과 계산 없는 자료 검증 단계)",
        "truth": "not_applicable",
        "limits": [
            "대조 보고서는 KRX 원가격 행이 아니라 계산 배율 · 집계(본인 서버 보관 = 모든 원천 자료 복제 허용 근거 아님)",
            "meta.snapshot_path 등 원본 안 절대경로 = 이 맥북 기준",
        ],
    },
    "POC6-04:20261021T200645_c24b88ce": {
        "step": "POC6-04",
        "result_doc": _DOCS + "POC6-04_D20_EXPANDED_SAMPLE_REPRODUCTION_RESULT.md",
        "decisions": [
            _DES
            + "POC6-04_D20_EXPANDED_SAMPLE_REPRODUCTION_PLAN_DECISION_2026-10-21.md",
            _DES
            + "POC6-04_D20_EXPANDED_SAMPLE_REPRODUCTION_RESULT_DECISION_2026-10-21.md",
        ],
        "code_evidence": [
            {
                "kind": "first_commit_containing_code",
                "commit": "fea10c38",
                "paths": ["app/d20_expand/", "scripts/run_d20_expanded_check.py"],
            },
        ],
        "predictions": "not_saved(점수 · 판정만 저장 · 행 단위 예측 · 정답 미저장)",
        "truth": "not_saved",
        "limits": ["manifest.json 의 입력 경로 = 이 맥북 절대경로"],
    },
}
COMMON = {
    "run_commit": None,
    "run_commit_note": "실행 당시 commit 미상(커밋 전 작업 트리에서 실행)",
    "trained_artifact": "not_saved",
    "record_type": "RETROSPECTIVE_TEST",
    "closing_commit": "fea10c38",
}
EXCLUDED = [
    {
        "what": "state/ml/research/poc5_06",
        "reason": "평단 · 수량 · 실현손익 칸 포함 — 이번 OCI 등록 제외(PC 원본 보존)",
    },
    {
        "what": "state/ml/research/poc5_08",
        "reason": "보유 표시 · 사용자 평가 포함 — 이번 OCI 등록 제외(PC 원본 보존)",
    },
]
# 미래 예측 기록 형식(이번에 생산 작업 없음 · 판정 §5 설계 §5)
FORWARD_RECORD_FIELDS = {
    "record_type": "FORWARD_RESEARCH",
    "model_id": "모델 식별자",
    "model_version": "설정 · 코드 판",
    "recipe_digest": "목표 · feature · 모델 설정 해시",
    "input_runs": "입력으로 쓴 증거 묶음 run_id 목록",
    "decision_time": "기준 시각(UTC) — 이 시각 이하에 공개된 판만 입력",
    "generated_at": "예측 실제 생성 시각(UTC)",
    "train_data_end": "학습 자료 마지막 관측일",
    "train_data_available_by": "학습 자료 확보 · 공개 기준 시각(UTC)",
    "target_def": "목표 정의(예: D20 = 다음 20거래일 최저 종가 변화)",
    "universe_ref": "대상 목록 object · 선정 시각",
    "predictions": "[{ticker, value}]",
}


def allowed_files() -> set[tuple[str, str, str]]:
    """허용 연구 파일 (실험, 원래 상대 경로, sha256). OCI 업로드 받기의 허용 목록."""
    return {
        (eid, f"{folder}/{rel}", sha)
        for eid, (folder, entries) in FILES.items()
        for rel, _size, sha in entries
    }


def _count(value: Any) -> Optional[int]:
    """fetch.json 의 targets = 개수(정수 · 실제 POC6-03) 또는 목록."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return len(value) if isinstance(value, list) else None


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _links(eid: str, folder: Path) -> dict:
    """원본 파일에서 연결 정보를 읽기만 한다(모델 모듈을 불러오지 않는다)."""
    if eid.startswith("POC6-02"):
        rep = _load(folder / "report.json")
        merged = _load(folder / "gpu_merged/report_with_gpu.json")
        etfs = rep["eligibility"]["etfs"]
        return {
            "input_digest": rep.get("input_digest"),
            "recipe_digest": rep.get("recipe_digest"),
            "targets": {
                "eligible": sorted(t for t, v in etfs.items() if v.get("eligible")),
                "excluded": sorted(t for t, v in etfs.items() if not v.get("eligible")),
                "all": len(etfs),
            },
            "target_def": rep["recipe"].get("target"),
            "features": rep["recipe"].get("feature_names"),
            "environment": {
                "cpu": rep.get("environment"),
                "gpu": _load(folder / "gpu_result.json").get("env"),
            },
            "verdicts": merged.get("candidates"),
            "gpu_code_sha256": _load(folder / "gpu_bundle/gpu_input.json").get(
                "code_sha256"
            ),
        }
    if eid.startswith("POC6-03"):
        rep = _load(folder / f"{_C03}/report.json")
        src = rep.get("krx_source", {})
        return {
            "targets": {"all": _count(_load(folder / "fetch.json").get("targets"))},
            "dependencies": [
                {
                    "kind": "sealed_krx_db",
                    "path": "state/ml/research/krx_etf_universe.sqlite",
                    "bytes": src.get("file_size"),
                    "file_sha256": src.get("file_sha256"),
                    "content_sha256": src.get("content_sha256"),
                    "uploaded": False,
                    "reason": "OCI 미전송 계약 — 참조만",
                }
            ],
        }
    rep = _load(folder / "report.json")
    man = _load(folder / "manifest.json")
    return {
        "recipe_digest": man.get("recipe_digest"),
        "targets": {"B": rep.get("four"), "C": rep.get("c_etfs")},
        "environment": rep.get("environment"),
        "verdicts": {"C12": (rep.get("c12") or {}).get("verdict", {}).get("label")},
    }


def _existing(root: Path, shas: set[str]) -> Optional[store.RunRef]:
    runs, _ = store.list_runs(root)
    for r in runs:
        if r.manifest["kind"] == "RESEARCH_REGISTRATION":
            got = {
                f["sha256"]
                for f in r.manifest.get("files", [])
                if f["status"] == "REGISTERED"
            }
            if got == shas:
                return r
    return None


def register_research(
    *, root: Path, repo_root: Path, now: datetime, git_head: Optional[str]
) -> tuple[str, dict]:
    """공식 파일을 objects 에 넣고 RESEARCH_REGISTRATION 묶음 하나를 공개한다(같은 내용이 이미 있으면 그것)."""
    files, objects, experiments = [], {}, []
    for eid, (folder, entries) in FILES.items():
        base = repo_root / folder
        for rel, size, sha in entries:
            p = base / rel
            row = {
                "experiment_id": eid,
                "rel_path": f"{folder}/{rel}",
                "expected_sha256": sha,
                "bytes": size,
            }
            try:
                before = store.sha256_file(p)
                if before != sha or p.stat().st_size != size:
                    raise store.EvidenceError("받은 파일 해시 · 크기가 기대와 다름")
                store.put_file(root, p, expect_sha=sha)
                if store.sha256_file(p) != before:
                    raise store.EvidenceError("등록 중 원본이 바뀜")
            except (OSError, store.EvidenceError) as e:
                files.append(
                    row
                    | {
                        "status": "CHECK_REQUIRED",
                        "reason": f"{type(e).__name__}: {e}"[:200],
                    }
                )
                continue
            files.append(row | {"status": "REGISTERED", "sha256": sha})
            objects.setdefault(
                sha,
                {
                    "sha256": sha,
                    "bytes": size,
                    "role": "research_file",
                    "format": "raw",
                },
            )
        if all(f["status"] == "REGISTERED" for f in files if f["experiment_id"] == eid):
            try:
                links = _links(eid, base)
            except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:
                links = {"error": f"연결 정보 읽기 실패: {type(e).__name__}: {e}"[:200]}
        else:
            links = {"note": "확인 필요 파일이 있어 연결 정보를 읽지 않음"}
        experiments.append(
            {"experiment_id": eid} | STATIC[eid] | COMMON | {"links": links}
        )
    registered = {f["sha256"] for f in files if f["status"] == "REGISTERED"}
    found = _existing(root, registered)
    if found is not None:
        return "ALREADY_REGISTERED", found.manifest
    bad = [f for f in files if f["status"] != "REGISTERED"]
    bad += [e for e in experiments if "error" in e["links"]]
    manifest = {
        "schema": store.SCHEMA,
        "run_id": store.new_run_id(now),
        "kind": "RESEARCH_REGISTRATION",
        "site": "PC",
        "status": "OK" if not bad else ("PARTIAL" if registered else "FAILED"),
        "code_commit": git_head,
        "code_commit_kind": "registration_program_commit(과거 연구 실행 commit 아님)",
        "imported_at": store.iso(now),
        "record_type": "RETROSPECTIVE_TEST",
        "experiments": experiments,
        "files": files,
        "excluded": EXCLUDED,
        "forward_record_fields": FORWARD_RECORD_FIELDS,
        "objects": [objects[k] for k in sorted(objects)],
    }
    _, published = store.publish_run(root, manifest, clock=lambda: now)
    return published["status"], published
