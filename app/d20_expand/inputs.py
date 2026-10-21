"""POC6-04 — 입력 고정 · B/C snapshot(PLAN §1 · §3 · 판정 §6).

```text
manifest  입력 파일마다 전체 64자리 sha256 — 학습 전에 다시 계산해 같아야 함(다르면 InputError = CHECK_REQUIRED)
A         POC6-02 공식 CPU report.json(같은 해시 · 다시 실행 안 함)
B         공식 snapshot 의 원래 적격 4종 + POC6-03 사본 행(`price_basis_check.compare.recount_snapshot`)
C         공식 snapshot 의 26종 + 사본 행 → POC6-02 적격 규칙 그대로
```
B · C 는 새 snapshot 이므로 각자 digest 를 계산하고, 부모 입력 경로 · 해시는 따로 기록한다.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from app.d20_pooled import env
from app.d20_pooled import runner as R02
from app.d20_pooled.snapshot import SnapshotError, digest, load_snapshot
from app.price_basis_check import compare as C03

PROJECT_ROOT = Path(__file__).resolve().parents[2]
_P2 = "state/ml/research/poc6_02/20261021T104103_129a89b0"
_P3 = "state/ml/research/poc6_03/20261021T161446_3403e974"
_P3R = _P3 + "/compare_20261021T161507_3927699a"

# 실행용 manifest(판정 §6 · 2026-10-21 실측 전체 해시) — 다른 입력으로 자동 대체하지 않는다.
MANIFEST: dict[str, Any] = {
    "files": {
        "official_snapshot": {
            "path": f"{_P2}/input_snapshot.json",
            "sha256": "eccfce451d20e4f082c2f28b79a29a796a72f7b80979789665bc4b1d6eb1d57b",
        },
        "a_report": {
            "path": f"{_P2}/report.json",
            "sha256": "700c55a832834536941055a2e117cab4fb115d53f175f89baa9e79946c71312a",
        },
        "copy_fetch": {
            "path": f"{_P3}/fetch.json",
            "sha256": "709a2837aaa1cdbcb2cf25337b904da206787eb529c7496a06d0f55c537e6213",
        },
        "copy_db": {
            "path": f"{_P3}/copy.sqlite",
            "sha256": "276c29e74b0d100e97d9eaf33b59214ab896329d8e87004384a74503143bb088",
        },
        "basis_report": {
            "path": f"{_P3R}/report.json",
            "sha256": "a5ecf0137c3f2541ed31f5e9be90f2623514f17bd0328c849b827754e5dab772",
        },
        "basis_report_md": {
            "path": f"{_P3R}/report.md",
            "sha256": "4496059ccce94a2aa4cb426f62da8b9095722b54523c61bd31ddabb7ad7aef41",
        },
    },
    "expect": {"b_etfs": 4, "c_etfs": 12, "dates_per_block": 63},
    "monthly": [
        "161510",
        "441800",
    ],  # 보조 (a) 평가에서 뺄 월 분배 2종(조정 사유 미확인)
    "krx_end": "2026-09-21",  # 보조 (b) — 목표 창 마지막 날이 이 날 이하인 3구간 행
}


def cpu_libs(environment: Any) -> tuple:
    """같은 모델 비교에 필요한 계산 환경 — Python 판 · CPU 라이브러리 판(torch 제외 · POC6-02 merge 와 같은 기준)."""
    e = environment if isinstance(environment, dict) else {}
    libs = e.get("libraries") if isinstance(e.get("libraries"), dict) else {}
    return e.get("python"), tuple(
        sorted((k, v) for k, v in libs.items() if k != "torch")
    )


class InputError(Exception):
    """입력 고정 위반(해시 · 형식 · 다른 실험) — CHECK_REQUIRED · 학습 0."""


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def resolve(manifest: dict[str, Any], root: Path = PROJECT_ROOT) -> dict[str, Any]:
    """manifest 의 파일마다 전체 sha256 을 다시 계산해 같아야 한다."""
    out = {}
    for key, spec in manifest["files"].items():
        path = Path(spec["path"])
        path = path if path.is_absolute() else Path(root) / path
        if not path.is_file():
            raise InputError(f"{key} 파일 없음: {path}")
        got = sha256_file(path)
        if got != spec["sha256"]:
            raise InputError(f"{key} sha256 {got} ≠ manifest {spec['sha256']}")
        out[key] = {"path": str(path), "sha256": got, "bytes": path.stat().st_size}
    return out


def load_inputs(manifest: dict[str, Any], root: Path = PROJECT_ROOT) -> dict[str, Any]:
    files = resolve(manifest, root)
    try:
        official = load_snapshot(Path(files["official_snapshot"]["path"]))
        copy = C03.load_copy(Path(files["copy_db"]["path"]).parent)
    except (SnapshotError, C03.CompareError) as e:
        raise InputError(str(e)) from e
    # A 는 해시를 확인한 바이트 그대로 읽고 · 그 바이트를 고정 사본으로 쓴다(따로 다시 읽지 않음)
    a_bytes = Path(files["a_report"]["path"]).read_bytes()
    if hashlib.sha256(a_bytes).hexdigest() != files["a_report"]["sha256"]:
        raise InputError("A 보고서가 해시 확인 뒤 바뀜")
    try:
        a_report = json.loads(a_bytes.decode("utf-8"))
        basis = json.loads(
            Path(files["basis_report"]["path"]).read_text(encoding="utf-8")
        )
    except ValueError as e:
        raise InputError(f"보고서 JSON 읽기 실패: {e}") from e
    dg = digest(official)
    if copy["meta"].get("snapshot_digest") != dg:
        raise InputError(
            "POC6-03 사본이 공식 snapshot 으로 만든 것이 아님(digest 다름)"
        )
    if a_report.get("input_digest") != dg or a_report.get("stage") != "CPU":
        raise InputError("A 보고서가 공식 snapshot 의 CPU 결과가 아님")
    if a_report.get("recipe_digest") != R02.recipe_digest():
        raise InputError(
            "지금 POC6-02 recipe 가 A 실행 때와 다름(같은 설정 재사용 불가)"
        )
    now = env.environment()
    if cpu_libs(a_report.get("environment")) != cpu_libs(now):
        raise InputError(
            "CPU 계산 환경(Python · CPU 라이브러리 판)이 A 실행 때와 다름 — 같은 모델 비교 불가"
            f" (A {cpu_libs(a_report.get('environment'))} · 지금 {cpu_libs(now)})"
        )
    four = [e["ticker"] for e in a_report["eligibility"]["eligible"]]
    return {
        "files": files,
        "official": official,
        "official_digest": dg,
        "a_report": a_report,
        "a_report_bytes": a_bytes,
        "environment": now,
        "copy": copy,
        "basis": basis,
        "four": four,
    }


def build_snapshots(inp: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """B = 원래 적격 4종 + 사본 행 · C = 26종 + 사본 행(둘 다 POC6-03 recount_snapshot · snapshot 계약 통과)."""
    rows = inp["copy"]["rows"]
    try:
        b = C03.recount_snapshot(
            inp["official"], {t: rows[t] for t in inp["four"] if t in rows}
        )
        c = C03.recount_snapshot(inp["official"], rows)
    except C03.CompareError as e:
        raise InputError(str(e)) from e
    return b, c
