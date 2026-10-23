"""POC6-06 — 저장한 예측 · 목표 기록 읽기(주 기록 · 공개 확인 영수증 · 재시도 연결 · 진단 분리).

주 기록 = (protocol · cohort · ticker · D) 의 최초 FORWARD_RESEARCH 항목(role PRIMARY · 공개 순 첫째) 중
**공개 확인 영수증**이 있는 것만이다. 영수증 = 예측 파일이 놓인 뒤 찍은 시각(= 공개 시각의 상한) · 파일 해시.
영수증 시각 < D 다음 거래일 15:30(close_cutoff_at) · 해시 일치일 때만 전향 기록으로 센다(검증자 r1 F1).
재시도(role RETRY)는 그 주 기록과 같은 입력 object · 같은 모델 판 · 영수증이 마감 전인 것만,
주 기록에서 실행 실패(FAILED)한 방법에만 연결한다. 진단(DIAGNOSTIC) · 부가(SUPPLEMENTARY)는 성과 · 학습에 쓰지 않는다.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from app.forward_compare import protocol as P
from app.ml_evidence import store

FORWARD, DIAGNOSTIC = "FORWARD_RESEARCH", "DIAGNOSTIC"
RECEIPT_SUFFIX = ".receipt.json"


def receipt_path(doc_path: Path) -> Path:
    return doc_path.with_name(doc_path.name[: -len(".json")] + RECEIPT_SUFFIX)


def prediction_docs(root: Path) -> list[dict[str, Any]]:
    """예측 기록(영수증 파일 제외) · 각 기록에 `_receipt`(검사 통과 영수증 또는 None)를 붙인다."""
    base = root / "predictions"
    docs = []
    for f in sorted(base.glob("*/*.json")) if base.is_dir() else []:
        if f.name.endswith(RECEIPT_SUFFIX):
            continue
        data = f.read_bytes()
        d = P.read_json(f)
        if (
            d.get("schema") != P.SCHEMAS["prediction"]
            or d.get("protocol_id") != P.PROTOCOL_ID
        ):
            raise store.EvidenceError(f"예측 기록 schema 다름: {f.name}")
        d["_path"] = f
        d["_receipt"] = _receipt(f, d, store.sha256_bytes(data))
        docs.append(d)
    docs.sort(key=lambda d: (store.parse_iso(d["times"]["published_at"]), d["id"]))
    return docs


def _receipt(f: Path, d: dict, sha: str) -> Optional[dict]:
    """영수증이 있고 · 형식 · 해시 · id · D 가 맞고 · 확인 시각이 실제 해석되고 공개 시작 이후면 그 영수증.

    깨진 · 객체가 아닌 영수증은 None(읽기 전체를 멈추지 않는다 · 그 기록은 전향 기록이 아님).
    """
    rp = receipt_path(f)
    if not rp.is_file():
        return None
    try:
        r = P.read_json(rp)
        confirmed = store.parse_iso(r.get("confirmed_at"))
        started = store.parse_iso(d["times"]["published_at"])
    except (OSError, ValueError, AttributeError, TypeError, KeyError):
        return None
    ok = (
        r.get("schema") == P.SCHEMAS["prediction_receipt"]
        and r.get("protocol_id") == P.PROTOCOL_ID
        and r.get("prediction_sha256") == sha
        and r.get("id") == d["id"]
        and r.get("D") == d["D"]
        and confirmed >= started  # 확인은 공개 시작 뒤일 수밖에 없다(하한)
    )
    return r if ok else None


def write_receipt(root: Path, doc_path: Path, confirmed_at: datetime, how: str) -> dict:
    """예측 파일이 이미 놓여 있음을 확인한 시각을 남긴다(파일을 놓은 뒤에만 부른다)."""
    d = P.read_json(doc_path)
    body = P.doc(
        "prediction_receipt",
        id=d["id"],
        D=d["D"],
        prediction=P.rel_in(root, doc_path),
        prediction_sha256=store.sha256_file(doc_path),
        confirmed_at=store.iso(confirmed_at),
        close_cutoff_at=d["times"]["close_cutoff_at"],
        how=how,
        meaning=(
            "이 시각에 예측 파일이 이미 공개돼 있었음(공개 시각의 상한)"
            " · 확인 시각 < 마감 일 때만 전향 기록 · 마감 뒤 확인도 남겨 다시 확인되지 않게 한다"
        ),
    )
    P.write_once(receipt_path(doc_path), P.dumps(body))
    return body


def latest_recorded(root: Path) -> Optional[datetime]:
    """연구 폴더에 남은 가장 늦은 기록 시각(실행 종료 · 예측 공개 · 공개 확인) — 시계 역행 가드용."""
    found: list[datetime] = []
    for pattern, keys in (
        ("runs/*.json", ("finished_at",)),
        ("predictions/*/*.json", ("confirmed_at", "times.published_at")),
    ):
        for f in root.glob(pattern):
            try:
                doc = P.read_json(f)
            except (OSError, ValueError):
                continue
            for key in keys:
                v = doc
                for part in key.split("."):
                    v = v.get(part) if isinstance(v, dict) else None
                try:
                    found.append(store.parse_iso(v))
                except ValueError:
                    continue
    return max(found, default=None)


def _valid_forward(d: dict) -> bool:
    r = d.get("_receipt")
    return (
        d["record_type"] == FORWARD
        and r is not None
        and store.parse_iso(r["confirmed_at"])
        < store.parse_iso(d["times"]["close_cutoff_at"])
    )


def unconfirmed(docs: list[dict]) -> list[dict]:
    """전향 후보인데 마감 전 공개 확인이 없는 기록(성과 · 학습 제외 · 보고에 수만 표시)."""
    return [d for d in docs if d["record_type"] == FORWARD and not _valid_forward(d)]


def primaries(
    root: Path, docs: list[dict] | None = None
) -> dict[tuple, dict[str, Any]]:
    """(ticker, D) → 주 기록(+ 연결된 재시도 결과)."""
    docs = prediction_docs(root) if docs is None else docs
    out: dict[tuple, dict] = {}
    for d in docs:
        if not _valid_forward(d):
            continue
        for e in d["entries"]:
            key = (e["ticker"], d["D"])
            if e["role"] == "PRIMARY" and key not in out:
                out[key] = {
                    "run_id": d["id"],
                    "D": d["D"],
                    # 쓰기 시작(하한) · 실제 공개 확인(영수증 · 상한) — 공개일 · 가용 시각은 visible_by
                    "write_started_at": d["times"]["published_at"],
                    "visible_by": d["_receipt"]["confirmed_at"],
                    "model_version": d["model"]["model_version"],
                    "input": e["input"],
                    "methods": {m: dict(v) for m, v in e["methods"].items()},
                    "retries": [],
                }
    for d in docs:
        if not _valid_forward(d):
            continue
        for e in d["entries"]:
            prim = out.get((e["ticker"], d["D"]))
            if (
                e["role"] != "RETRY"
                or prim is None
                or e.get("retry_of") != prim["run_id"]
            ):
                continue
            if (
                d["model"]["model_version"] != prim["model_version"]
                or e["input"]["source"]["object"] != prim["input"]["source"]["object"]
            ):
                continue
            for m, v in e["methods"].items():
                if (
                    prim["methods"].get(m, {}).get("status") == "FAILED"
                    and v.get("status") == "OK"
                ):
                    # 재시도 기록의 공개 확인 시각
                    retried = d["_receipt"]["confirmed_at"]
                    prim["methods"][m] = dict(v, retried_at=retried)
                    prim["retries"].append({"run_id": d["id"], "method": m})
    return out


def target_path(root: Path, ticker: str, D: str) -> Path:
    return root / "targets" / D / f"{ticker}.json"


def targets(root: Path) -> dict[tuple, dict[str, Any]]:
    base = root / "targets"
    out = {}
    for f in sorted(base.glob("*/*.json")) if base.is_dir() else []:
        d = P.read_json(f)
        if (
            d.get("schema") != P.SCHEMAS["target"]
            or d.get("protocol_id") != P.PROTOCOL_ID
        ):
            raise store.EvidenceError(f"목표 기록 schema 다름: {f.name}")
        out[(d["ticker"], d["D"])] = d
    return out
