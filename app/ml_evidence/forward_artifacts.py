"""POC6-06 산출물의 05 보관 허용 형식(PLAN 판정 2026-10-22 §6 — 정규화 상대 경로 · schema · 참조 · hash).

PC 등록(`app/forward_compare/archive.py`)과 OCI 받기(`transfer.accept_upload`)가 같은 규칙을 쓴다.
표준 라이브러리 · `store` 만 불러온다(OCI 에 torch · sklearn 이 없어도 읽힘). 모델 파일은 bytes 로만 다룬다
(load · import 0) — 같은 묶음의 training.json 이 그 파일 이름 · 해시를 참조해야만 받는다.
"""

from __future__ import annotations

import json
import posixpath
import re
from datetime import date
from typing import Any, Callable, Optional

from app.ml_evidence import store

KIND = "FORWARD_RESEARCH_ARTIFACTS"
PROTOCOL_ID = "poc6-06-v1"
ROOT_REL = "state/ml/research/poc6_06"
_ID = r"(?P<id>\d{8}T\d{6}Z_[0-9a-f]{8})"
_DAY = r"(?P<day>\d{4}-\d{2}-\d{2})"
_MV = r"(?P<mv>mv_[0-9a-f]{16})"
_TICKER = r"(?P<ticker>[0-9A-Z]{6})"

# 자료 유형 → (상대 경로 규칙, JSON schema · None = bytes 만 · training.json 참조 필수)
TYPES: dict[str, tuple[str, Optional[str]]] = {
    "cohort": (r"cohort_v1/cohort\.json", "poc6_06_cohort_v1"),
    "bootstrap_prices": (
        rf"bootstrap/{_ID}/prices\.json",
        "poc6_06_bootstrap_prices_v1",
    ),
    "bootstrap_fetch": (rf"bootstrap/{_ID}/fetch\.json", "poc6_06_bootstrap_fetch_v1"),
    "examples": (rf"examples/{_ID}\.json", "poc6_06_examples_v1"),
    "training": (rf"models/{_MV}/training\.json", "poc6_06_training_v1"),
    "model_median": (rf"models/{_MV}/median\.json", "poc6_06_median_v1"),
    "model_ridge": (rf"models/{_MV}/ridge\.json", "poc6_06_ridge_v1"),
    "model_mlp_norm": (rf"models/{_MV}/mlp_norm\.json", "poc6_06_mlp_norm_v1"),
    "model_hgb": (rf"models/{_MV}/hgb\.joblib", None),
    "model_mlp_state": (rf"models/{_MV}/mlp_state\.pt", None),
    "prediction": (rf"predictions/{_DAY}/{_ID}\.json", "poc6_06_prediction_v1"),
    # 공개 확인 영수증 — 예측 파일이 이 시각까지 공개돼 있었음(공개 시각의 상한 · F1)
    "prediction_receipt": (
        rf"predictions/{_DAY}/{_ID}\.receipt\.json",
        "poc6_06_prediction_receipt_v1",
    ),
    "target": (rf"targets/{_DAY}/{_TICKER}\.json", "poc6_06_target_v1"),
    "report": (rf"reports/{_ID}\.json", "poc6_06_report_v1"),
    "run": (rf"runs/{_ID}\.json", "poc6_06_run_v1"),
}
SCHEMAS = {k: v[1] for k, v in TYPES.items() if v[1] is not None}
_RX = {k: re.compile(v[0]) for k, v in TYPES.items()}


def classify(rel_path: Any) -> tuple[Optional[str], Optional[dict]]:
    """정규화한 상대 경로 → (유형, 경로 안 값). 허용 밖이면 (None, None). 접두어 문자열만으로 보지 않는다."""
    if not isinstance(rel_path, str) or "\\" in rel_path or rel_path.startswith("/"):
        return None, None
    if posixpath.normpath(rel_path) != rel_path or ".." in rel_path.split("/"):
        return None, None
    prefix = ROOT_REL + "/"
    if not rel_path.startswith(prefix):
        return None, None
    tail = rel_path.removeprefix(prefix)
    for kind, rx in _RX.items():
        m = rx.fullmatch(tail)
        if m is None:
            continue
        parts = m.groupdict()
        if "id" in parts and not store.run_id_ok(parts["id"]):
            return None, None
        if "day" in parts:
            try:
                date.fromisoformat(parts["day"])
            except ValueError:
                return None, None
        return kind, parts
    return None, None


def json_problem(kind: str, parts: dict, data: bytes) -> Optional[str]:
    """JSON 산출물의 실제 해석 · schema · protocol · 경로 값 일치."""
    try:
        doc = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return "JSON 해석 불가"
    if not isinstance(doc, dict):
        return "JSON 객체 아님"
    if doc.get("schema") != SCHEMAS[kind] or doc.get("protocol_id") != PROTOCOL_ID:
        return "schema · protocol_id 다름"
    expect = {"id": "id", "day": "D", "ticker": "ticker", "mv": "model_version"}
    for key, field in expect.items():
        if key == "mv" and kind != "training":
            continue  # 모델 JSON 은 같은 묶음 training.json 의 해시 참조로 연결을 본다
        if key in parts and doc.get(field) != parts[key]:
            return f"경로 값과 본문 {field} 다름"
    return None


def problems(m: dict, read: Callable[[str], Optional[bytes]]) -> list[str]:
    """FORWARD_RESEARCH_ARTIFACTS 묶음 검사. read(sha) = 해시가 맞는 bytes 또는 None."""
    if m.get("kind") != KIND or m.get("protocol_id") != PROTOCOL_ID:
        return ["POC6-06 산출물 묶음 아님"]
    files = m.get("files")
    if (
        not isinstance(files, list)
        or not files
        or not all(isinstance(f, dict) for f in files)
    ):
        return ["files 형식 아님 · 비어 있음"]
    out: list[str] = []
    paths: set[str] = set()
    shas: dict[str, int] = {}
    typed: list[tuple[str, dict, dict]] = []
    for f in files:
        kind, parts = classify(f.get("rel_path"))
        sha, size = f.get("sha256"), f.get("bytes")
        if kind is None or f.get("type") != kind:
            out.append(f"허용 밖 경로 · 유형: {str(f.get('rel_path'))[:80]}")
            continue
        if not (isinstance(sha, str) and store.HEX64.match(sha)) or not isinstance(
            size, int
        ):
            out.append(f"해시 · 크기 형식 아님: {f['rel_path'][-60:]}")
            continue
        if f["rel_path"] in paths:
            out.append(f"같은 경로 두 번: {f['rel_path'][-60:]}")
        paths.add(f["rel_path"])
        shas[sha] = size
        typed.append((kind, parts, f))
    if out:
        return out
    objs = {o["sha256"]: o.get("bytes") for o in m.get("objects", [])}
    if objs != shas:
        return ["object 목록이 파일 목록과 다름"]
    trainings: dict[str, dict] = {}
    for kind, parts, f in typed:
        data = read(f["sha256"])
        if data is None or len(data) != f["bytes"]:
            out.append(f"object 없음 · 손상 · 크기 다름: {f['rel_path'][-60:]}")
            continue
        if SCHEMAS.get(kind) is None:
            continue
        bad = json_problem(kind, parts, data)
        if bad:
            out.append(f"{bad}: {f['rel_path'][-60:]}")
        elif kind == "training":
            trainings[parts["mv"]] = json.loads(data.decode("utf-8"))
    for kind, parts, f in typed:
        if kind == "prediction_receipt":
            out += _receipt_problems(parts, f, read)
            continue
        if not kind.startswith("model_"):
            continue
        name = f["rel_path"].rsplit("/", 1)[1]
        ref = (trainings.get(parts["mv"]) or {}).get("file_sha256", {})
        if ref.get(name) != f["sha256"]:
            out.append(
                f"같은 묶음의 training.json 참조 없음 · 해시 다름: {f['rel_path'][-60:]}"
            )
    return out


def _json_dict(data: Optional[bytes]) -> Optional[dict]:
    """bytes → JSON 객체(아니면 None · 예외를 올리지 않는다)."""
    if data is None:
        return None
    try:
        doc = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None
    return doc if isinstance(doc, dict) else None


def _receipt_problems(parts: dict, f: dict, read: Callable) -> list[str]:
    """영수증이 가리키는 파일(해시)이 이 묶음이나 보관소에 있는 같은 id · D 의 예측 기록인가."""
    rec = _json_dict(read(f["sha256"]))
    if rec is None:
        return [f"영수증 해석 불가: {f['rel_path'][-60:]}"]
    sha = rec.get("prediction_sha256")
    ok_sha = isinstance(sha, str) and store.HEX64.match(sha) is not None
    pred = _json_dict(read(sha)) if ok_sha else None
    if pred is None:
        return [f"영수증이 가리키는 예측 파일 없음 · 해석 불가: {f['rel_path'][-60:]}"]
    if (
        pred.get("schema") != SCHEMAS["prediction"]
        or pred.get("protocol_id") != PROTOCOL_ID
        or pred.get("id") != parts["id"]
        or pred.get("D") != parts["day"]
    ):
        return [
            f"영수증이 가리키는 파일이 같은 id · D 의 예측 기록이 아님: {f['rel_path'][-60:]}"
        ]
    return []
