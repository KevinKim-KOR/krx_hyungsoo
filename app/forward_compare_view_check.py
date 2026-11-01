"""POC6-14 — 조회가 읽는 06 저장 구조 검사(검증자 r1 F1 · 손상을 정상 '미평가 · 비교 없음'으로 받지 않음).

06 이 실제로 쓰는 모양(`cohort.select` · `forward._run` · `mature.evaluate` · `report.build`)만 정상으로 본다.
조회가 소비하는 칸만 검사하고, 값의 진위 · 생성 이력은 인증하지 않는다(설계 §7 · 판정 §7).

```text
회차 기록  maturity 칸 없음 = 정상(06 은 입력 없는 날 성숙 평가 전에 끝난다) · 있으면 open 목록의 항목마다 종목 · D · 06 상태
보고       비교 세 항목 전부 · 칸(행 · 날짜 · 종목 · 빠진 행) · 방법 키 = 그 비교의 방법 · 비교 행 0 ⇔ MAE 전부 null
           · 큰 하락 행 0 ⇔ 작게 추정한 정도 전부 null · 건수 · 날짜별 값 · id = 파일 이름
예측 기록  D · 시각 · 모델 판 · 기록 종류 · 항목(종목 ⊂ 고정 표본 · 역할 · 방법 · 입력 출처) · 예측 안 함 목록
```
"""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

from app.forward_compare import protocol as P
from app.forward_compare import report as R06
from app.ml_evidence import store

# 06 mature.STATES 중 목표 파일 없이 회차 기록에만 남는 상태(MATURED 제외 · 06 문구 그대로)
OPEN_STATES = (
    "PENDING_NOT_DUE",
    "PENDING_CALENDAR",
    "DUE_DATA_MISSING",
    "DATA_CHECK_REQUIRED",
)
# 06 models.Loaded / predict 가 쓰는 방법 상태
METHOD_STATES = ("OK", "FAILED", "ENV_MISMATCH", "NOT_RUN_ENV", "DATA_SHORT")
RECORD_TYPES = ("FORWARD_RESEARCH", "DIAGNOSTIC")
ROLES = ("PRIMARY", "RETRY", "SUPPLEMENTARY", "DIAGNOSTIC")
COUNT_INT_KEYS = (
    "cohort",
    "forward_dates",
    "primary_records",
    "matured",
    "pending_or_missing",
    "diagnostic_entries",
    "supplementary_entries",
)
# 06 첫 커밋(666fc5c0 · 2026-10-23 13:53) 전 작업 판이 쓴 첫 보고(2026-10-23 10:20 KST)에는 없는 칸
# — 없으면 허용(화면 '미확인' · 0 으로 채우지 않음) · 있으면 0 이상 정수
OPTIONAL_COUNT_KEYS = ("unconfirmed_forward_records",)


def nonneg_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and v >= 0


def is_date(v: Any) -> bool:
    try:
        return isinstance(v, str) and date.fromisoformat(v).isoformat() == v
    except ValueError:
        return False


def is_iso(v: Any) -> bool:
    try:
        store.parse_iso(v)
        return True
    except (ValueError, TypeError, AttributeError):
        return False


def _num_or_none(v: Any) -> bool:
    return v is None or (isinstance(v, (int, float)) and not isinstance(v, bool))


def cohort_names(cohort: dict) -> Optional[dict]:
    """종목 → 선정 당시 이름(글자 또는 None). 목록 모양이 틀리거나 고정 표본 종목이 빠지면 None."""
    sel = cohort.get("selected")
    if not isinstance(sel, list):
        return None
    names = {}
    for s in sel:
        if not isinstance(s, dict) or not isinstance(s.get("ticker"), str):
            return None
        if not (s.get("name") is None or isinstance(s.get("name"), str)):
            return None
        names[s["ticker"]] = s.get("name")
    return names if set(cohort["tickers"]) <= set(names) else None


def _source_ok(entry: dict) -> bool:
    inp = entry.get("input")
    src = inp.get("source") if isinstance(inp, dict) else None
    return (
        isinstance(src, dict)
        and isinstance(src.get("object"), str)
        and bool(src["object"])
        and is_iso(src.get("available_at"))
        and (src.get("observed_at") is None or is_iso(src.get("observed_at")))
    )


def doc_problem(doc: dict, tickers: set) -> Optional[str]:
    """예측 기록 하나의 구조 문제(없으면 None)."""
    if not is_date(doc.get("D")):
        return "예측 기록 기준일 형식 다름"
    times = doc.get("times")
    if not isinstance(times, dict) or not all(
        is_iso(times.get(k))
        for k in ("published_at", "input_cutoff", "close_cutoff_at")
    ):
        return "예측 기록 시각 형식 다름"
    model = doc.get("model")
    if not isinstance(model, dict) or not isinstance(model.get("model_version"), str):
        return "예측 기록 모델 판 형식 다름"
    if not model["model_version"] or doc.get("record_type") not in RECORD_TYPES:
        return "예측 기록 모델 판 · 기록 종류 형식 다름"
    entries = doc.get("entries")
    if not isinstance(entries, list):
        return "예측 기록 항목 형식 다름"
    for e in entries:
        if (
            not isinstance(e, dict)
            or e.get("ticker") not in tickers
            or e.get("role") not in ROLES
            or not isinstance(e.get("methods"), dict)
        ):
            return "예측 기록 항목 형식 다름(종목 · 역할 · 방법)"
        if not _source_ok(e):
            return "예측 기록 입력 출처 형식 다름"
    missing = doc.get("not_predicted")
    if not isinstance(missing, list) or not all(
        isinstance(n, dict)
        and n.get("ticker") in tickers
        and isinstance(n.get("status"), str)
        for n in missing
    ):
        return "예측 기록의 예측 안 함 목록 형식 다름"
    return None


def run_ok(d: Any, stem: str) -> bool:
    if not (
        isinstance(d, dict)
        and d.get("schema") == P.SCHEMAS["run"]
        and d.get("protocol_id") == P.PROTOCOL_ID
        and d.get("id") == stem
        and is_iso(d.get("finished_at"))
    ):
        return False
    if "maturity" not in d:
        return True
    m = d["maturity"]
    if not isinstance(m, dict) or not isinstance(m.get("open"), list):
        return False
    return all(
        isinstance(o, dict)
        and isinstance(o.get("ticker"), str)
        and is_date(o.get("D"))
        and o.get("status") in OPEN_STATES
        for o in m["open"]
    )


def _method_map_ok(v: Any, methods: tuple) -> bool:
    return (
        isinstance(v, dict)
        and set(v) == set(methods)
        and all(_num_or_none(x) for x in v.values())
    )


def _comparison_ok(x: Any, methods: tuple) -> bool:
    if not isinstance(x, dict) or not all(
        nonneg_int(x.get(k)) for k in ("rows", "dates", "tickers", "excluded_rows")
    ):
        return False
    deep = x.get("deep_loss_le_8pct")
    if not (
        _method_map_ok(x.get("mae_pp"), methods)
        and isinstance(deep, dict)
        and nonneg_int(deep.get("rows"))
        and _method_map_ok(deep.get("mae_pp"), methods)
        and _method_map_ok(deep.get("under_estimate_pp"), methods)
    ):
        return False
    # 06 report.compare 는 비교 대상 방법이 모두 있는 공통 행만 쓴다 — 행이 있으면 모든 방법에 값,
    # 행이 없으면 모든 방법이 null(일부 null = 구조 손상 · 검증자 r2 F3). 큰 하락 공통 행도 같다.
    if deep["rows"] > x["rows"]:
        return False
    if not _filled(x["rows"], x["mae_pp"]):
        return False
    if (x["rows"] > 0) != (x["dates"] > 0) or (x["rows"] > 0) != (x["tickers"] > 0):
        return False
    return _filled(deep["rows"], deep["mae_pp"]) and _filled(
        deep["rows"], deep["under_estimate_pp"]
    )


def _filled(rows: int, values: dict) -> bool:
    """행 > 0 ⇔ 모든 방법 값 있음 · 행 = 0 ⇔ 모든 방법 null(일부만 null 은 손상)."""
    if rows > 0:
        return all(v is not None for v in values.values())
    return all(v is None for v in values.values())


def report_ok(d: Any, stem: str) -> bool:
    if not (
        isinstance(d, dict)
        and d.get("schema") == P.SCHEMAS["report"]
        and d.get("protocol_id") == P.PROTOCOL_ID
        and d.get("id") == stem
        and is_iso(d.get("generated_at"))
    ):
        return False
    per, counts, main = d.get("per_date"), d.get("counts"), d.get("main")
    if not (
        isinstance(per, dict) and isinstance(counts, dict) and isinstance(main, dict)
    ):
        return False
    if not all(
        is_date(k)
        and isinstance(v, dict)
        and nonneg_int(v.get("input_ok_primary"))
        and nonneg_int(v.get("matured"))
        for k, v in per.items()
    ):
        return False
    by = counts.get("predicted_by_method")
    if not (
        all(nonneg_int(counts.get(k)) for k in COUNT_INT_KEYS)
        and all(k not in counts or nonneg_int(counts[k]) for k in OPTIONAL_COUNT_KEYS)
        and isinstance(by, dict)
        and set(by) == set(P.METHODS)
        and all(nonneg_int(v) for v in by.values())
    ):
        return False
    return all(_comparison_ok(main.get(n), ms) for n, ms in R06.COMPARISONS.items())
