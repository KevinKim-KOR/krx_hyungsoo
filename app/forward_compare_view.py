"""POC6-14 — 06 전향 비교 기록의 PC 읽기 전용 조회(설계 V1 · PLAN 판정 2026-10-30).

```text
주 기록   06 `records.prediction_docs` · `primaries` 그대로(영수증 · 마감 · 재시도 연결 · 진단/부가 분리를 새로 판정하지 않음)
성숙      유효 목표(`records.targets`) → MATURED · 없으면 가장 늦은 회차 기록(`runs/*.json` maturity.open)의 상태
          · 둘 다 없으면 NOT_EVALUATED('이 기준일의 성숙 평가 상태 기록이 아직 없음' · 조회 응답에만)
보고      정상 보고 중 generated_at 최대 · 선택 D 대응 = 그 D 를 기록한 회차 id 의 reports/<run_id>.json
          (per_date 에 없다는 것만으로 미생성이라 하지 않음 · 06 은 예측 → 보고 → 회차 기록 순으로 쓴다)
단위      예측 · 실제 = 비율 → 여기 한 곳에서 ×100(`*_pct`) · 보고 MAE · 작게 추정한 정도 = 이미 %p(`*_pp` 그대로)
```

쓰기 · 잠금 · 실행 · 모델 열기 · 학습 · 성숙 처리 · 보고 생성 · SSH · 외부 조회 없음. 응답에 절대 경로 · raw 예측 ·
특징값 · 보유 · 계정을 넣지 않는다. 숫자는 표시 전에 유한성 · 허용 범위를 검사하고 어기면 숫자 대신 '확인 필요'.
"""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any, Optional

from app.forward_compare import cohort as C
from app.forward_compare import protocol as P
from app.forward_compare import records
from app.forward_compare import report as R06
from app.ml_evidence import store
from app import forward_compare_view_check as K

ROOT = Path(P.ROOT)
RESEARCH_LABEL = "연구용 · 운영 미채택"
REASON_MAX = 200
_PATH_RX = re.compile(r"(?:[A-Za-z]:\\|/)[^\s'\",)]+")
COUNT_KEYS = (
    "cohort",
    "forward_dates",
    "primary_records",
    "predicted_by_method",
    "matured",
    "pending_or_missing",
    "diagnostic_entries",
    "supplementary_entries",
    "unconfirmed_forward_records",
)


class ViewError(Exception):
    """조회 전체를 숫자 없이 멈추는 경우(status = READ_FAILED | CHECK_REQUIRED)."""

    def __init__(self, status: str, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


class DateNotFound(Exception):
    """선택한 D 에 유효 주 기록이 없다(404)."""


def _reason(text: Any) -> Optional[str]:
    """실패 사유 원문 — 절대 경로는 가리고 200자로 자른다."""
    if text is None:
        return None
    return _PATH_RX.sub("<경로>", str(text))[:REASON_MAX]


def _ratio_pct(v: Any) -> Optional[float]:
    """D20 비율(유한 · −1 ~ 0) → %. 어기면 None(숫자를 살리지 않음)."""
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    if not math.isfinite(v) or v < -1.0 or v > 0.0:
        return None
    return float(v) * 100.0


def _size_pp(v: Any) -> tuple[Optional[float], bool]:
    """보고의 %p 크기(유한 · 0 이상) 그대로. (값, 정상 여부) — null 은 정상(비교 행 0)."""
    if v is None:
        return None, True
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None, False
    if not math.isfinite(v) or v < 0.0:
        return None, False
    return float(v), True


def _span(values: list[str]) -> Optional[dict[str, str]]:
    vals = sorted(v for v in values if v)
    return {"min": vals[0], "max": vals[-1]} if vals else None


def _read(fn, *args):
    """06 읽기 함수 호출 — 형식 불일치는 CHECK_REQUIRED, 읽기 · 해석 실패는 READ_FAILED."""
    try:
        return fn(*args)
    except (store.EvidenceError, C.CohortError) as e:
        raise ViewError("CHECK_REQUIRED", _reason(e) or "형식 확인 필요") from e
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:
        raise ViewError("READ_FAILED", _reason(f"{type(e).__name__}: {e}")) from e


def _record_counts(docs: list[dict]) -> dict[str, int]:
    return {
        "unconfirmed_forward_records": len(records.unconfirmed(docs)),
        "diagnostic_entries": sum(
            len(d["entries"]) for d in docs if d["record_type"] == records.DIAGNOSTIC
        ),
        "supplementary_entries": sum(
            1 for d in docs for e in d["entries"] if e["role"] == "SUPPLEMENTARY"
        ),
    }


def _runs(root: Path) -> tuple[list[dict], list[str]]:
    """회차 기록(finished_at 순) · 읽지 못하거나 구조가 손상된 회차 이름(K.run_ok)."""
    ok, bad = [], []
    base = root / "runs"
    for f in sorted(base.glob("*.json")) if base.is_dir() else []:
        try:
            d = P.read_json(f)
            good = K.run_ok(d, f.stem)
        except (OSError, ValueError):
            good = False
        if good:
            ok.append(d)
        else:
            bad.append(f.stem)
    ok.sort(key=lambda r: store.parse_iso(r["finished_at"]))
    return ok, bad


def _maturity(key: tuple, tgts: dict, runs: list[dict], runs_bad: list[str]) -> dict:
    tg = tgts.get(key)
    if tg is not None:
        pct = _ratio_pct(tg.get("target"))
        if pct is None or not K.is_date(tg.get("target_end")):
            return {"state": "CHECK_REQUIRED", "reason": "저장된 목표 값 확인 필요"}
        return {
            "state": "MATURED",
            "actual_pct": pct,
            "target_end": tg.get("target_end"),
        }
    # 더 늦은 상태가 읽지 못한 회차에 있을 수 있다 — '성숙 확인 전'으로 숨기지 않음
    if runs_bad:
        return {"state": "CHECK_REQUIRED", "reason": "회차 기록 읽기 실패"}
    for r in reversed(runs):
        for o in (r.get("maturity") or {}).get("open") or []:
            if (o["ticker"], o["D"]) == key:  # 항목 모양 · 상태는 K.run_ok 가 확인
                return {
                    "state": o["status"],
                    "basis_run": r["id"],
                    "basis_at": r["finished_at"],
                }
    return {"state": "NOT_EVALUATED"}


def _methods(raw: dict) -> dict[str, dict]:
    out = {}
    for m in P.METHODS:
        v = raw.get(m)
        if not isinstance(v, dict):
            out[m] = {"status": "MISSING", "reason": "방법 기록 없음"}
            continue
        st = v.get("status")
        reason = v.get("reason")
        if st not in K.METHOD_STATES or not (reason is None or isinstance(reason, str)):
            out[m] = {"status": "CHECK_REQUIRED", "reason": "방법 기록 형식 확인 필요"}
            continue
        if st == "OK":
            pct = _ratio_pct(v.get("pred"))
            if pct is None:
                out[m] = {
                    "status": "CHECK_REQUIRED",
                    "reason": "저장된 예측 값 확인 필요",
                }
                continue
            item = {"status": "OK", "pred_pct": pct}
            if v.get("retried_at"):
                item["retried_at"] = v["retried_at"]
            out[m] = item
        else:
            out[m] = {"status": st, "reason": _reason(reason)}
    return out


def _report(root: Path, record_runs: list[str]) -> dict[str, Any]:
    base = root / "reports"
    good, bad = [], []
    for f in sorted(base.glob("*.json")) if base.is_dir() else []:
        try:
            d = P.read_json(f)
        except (OSError, ValueError):
            bad.append(f.stem)
            continue
        if K.report_ok(d, f.stem):  # 비교 세 항목 · 칸 · 방법 키 · 건수 · id(F1)
            good.append(d)
        else:
            bad.append(f.stem)
    sel_state = "INCLUDED"
    for rid in record_runs:
        if rid in bad:
            sel_state = "RUN_REPORT_UNREADABLE"
            break
        if not (base / f"{rid}.json").is_file():
            sel_state = "RUN_REPORT_MISSING"
    if not good:
        return {
            "state": "CHECK_REQUIRED" if bad else "NONE",
            "selected_D": sel_state,
            "unreadable": bad,
        }
    rep = max(good, key=lambda r: store.parse_iso(r["generated_at"]))
    comps, values_ok = {}, True
    for name in R06.COMPARISONS:
        x = rep["main"][name]
        mae = {}
        for m, v in x["mae_pp"].items():
            mae[m], fine = _size_pp(v)
            values_ok &= fine
        deep = x["deep_loss_le_8pct"]
        under = {}
        for m, v in deep["under_estimate_pp"].items():
            under[m], fine = _size_pp(v)
            values_ok &= fine
        comps[name] = {
            **{k: x[k] for k in ("rows", "dates", "tickers", "excluded_rows")},
            "mae_pp": mae,
            "deep": {"rows": deep["rows"], "under_estimate_pp": under},
        }
    per = rep["per_date"]
    predicted = sorted(per)
    matured = sorted(D for D, v in per.items() if v["matured"] > 0)
    return {
        "state": "OK" if values_ok else "CHECK_REQUIRED",
        "id": rep["id"],
        "generated_at": rep["generated_at"],
        "counts": {k: rep["counts"].get(k) for k in COUNT_KEYS},
        "predicted_dates": {
            "count": len(predicted),
            "first": predicted[0] if predicted else None,
            "last": predicted[-1] if predicted else None,
        },
        "matured_dates": {
            "count": len(matured),
            "first": matured[0] if matured else None,
            "last": matured[-1] if matured else None,
        },
        "comparisons": comps,
        "selected_D": sel_state,
        # 이름(UTC 접두)이 정상 보고보다 늦은데 읽지 못한 파일 — 후보 찾기용(생성 시각 인증 아님)
        "newer_unreadable": [b for b in bad if b > rep["id"]],
    }


def _base(status: str, message: Optional[str] = None, **extra: Any) -> dict[str, Any]:
    return {"status": status, "label": RESEARCH_LABEL, "message": message, **extra}


def build(root: Path = ROOT, d: Optional[str] = None) -> dict[str, Any]:
    """조회 응답 하나. 날짜 형식 · 존재는 호출 쪽(라우터)과 여기서 확인한다."""
    root = Path(root)
    if not root.is_dir() or not C.path(root).is_file():
        return _base("NO_RECORDS", "이 PC 에 06 연구 기록이 아직 없습니다")
    try:
        cohort = _read(C.load, root)
        names = K.cohort_names(cohort)
        if names is None:
            raise ViewError("CHECK_REQUIRED", "cohort 선정 목록 형식 다름")
        docs = _read(records.prediction_docs, root)
        tickers = set(cohort["tickers"])
        for doc in docs:
            if doc.get("cohort_id") != cohort.get("cohort_id"):
                raise ViewError(
                    "CHECK_REQUIRED", "예측 기록의 cohort 가 고정 표본과 다름"
                )
            problem = K.doc_problem(doc, tickers)
            if problem:
                raise ViewError("CHECK_REQUIRED", problem)
        prims = _read(records.primaries, root, docs)
        counts = _read(_record_counts, docs)
        if not prims:
            return _base("NO_RECORDS", "공개 확인된 연구 기록이 없습니다", other=counts)
        dates = sorted({D for (_, D) in prims}, reverse=True)
        sel = d or dates[0]
        if sel not in dates:
            raise DateNotFound(sel)
        tgts = _read(records.targets, root)
        runs, runs_bad = _runs(root)
        by_id = {doc["id"]: doc for doc in docs}
        rows = []
        for t in sorted(cohort["tickers"]):
            p = prims.get((t, sel))
            if p is None:
                why = None
                for doc in docs:
                    if doc["D"] != sel or doc["record_type"] != records.FORWARD:
                        continue
                    for n in doc["not_predicted"]:  # 모양은 K.doc_problem 이 확인
                        if n["ticker"] == t:
                            why = n["status"]
                rows.append(
                    {"ticker": t, "name": names.get(t), "primary": False, "why": why}
                )
                continue
            times = by_id[p["run_id"]]["times"]
            rows.append(
                {
                    "ticker": t,
                    "name": names.get(t),
                    "primary": True,
                    "methods": _methods(p["methods"]),
                    "actual": _maturity((t, sel), tgts, runs, runs_bad),
                    "detail": {
                        "run_id": p["run_id"],
                        "visible_by": p["visible_by"],
                        "write_started_at": p["write_started_at"],
                        "model_version": p["model_version"],
                        "input_cutoff": times["input_cutoff"],
                        "close_cutoff_at": times["close_cutoff_at"],
                        "input": {
                            k: p["input"]["source"].get(k)
                            for k in ("object", "observed_at", "available_at")
                        },
                    },
                }
            )
    except ViewError as e:
        return _base(e.status, e.message)
    except (KeyError, TypeError, AttributeError, ValueError) as e:
        return _base("READ_FAILED", _reason(f"{type(e).__name__}: {e}"))
    prim_rows = [r for r in rows if r["primary"]]
    record_runs = sorted({r["detail"]["run_id"] for r in prim_rows})
    mat = [r["actual"] for r in prim_rows if r["actual"].get("basis_run")]
    return _base(
        "OK",
        cohort={
            "id": cohort.get("cohort_id"),
            "size": len(cohort["tickers"]),
            "selected_at": cohort.get("selected_at"),
        },
        dates=[
            {"D": D, "primary_rows": sum(1 for (_, x) in prims if x == D)}
            for D in dates
        ],
        selected_D=sel,
        basis={
            "visible_by": _span([r["detail"]["visible_by"] for r in prim_rows]),
            "input_cutoff": _span([r["detail"]["input_cutoff"] for r in prim_rows]),
            "close_cutoff_at": _span(
                [r["detail"]["close_cutoff_at"] for r in prim_rows]
            ),
            "record_runs": record_runs,
            "model_versions": sorted({r["detail"]["model_version"] for r in prim_rows}),
            "maturity": (
                {
                    "runs": sorted({a["basis_run"] for a in mat}),
                    "at": _span([a["basis_at"] for a in mat]),
                }
                if mat
                else None
            ),
            "unreadable_runs": runs_bad,
        },
        rows=rows,
        report=_report(root, record_runs),
        other=counts,
    )
