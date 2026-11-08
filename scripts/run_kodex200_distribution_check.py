"""POC6-26 — KODEX200(069500) 2025 1주 보유 기준선 검산(무조정 A · 분배금 현금 B · 기존 연결 C).

설계 `docs/ai_design/POC6/POC6_26_KODEX200_DISTRIBUTION_BENCHMARK_RECONCILIATION_DESIGN_V1.md`
· 판정 V1.1 · 재개 판정 V1.2(우선) · PLAN `docs/ai_plan/POC6/POC6_26_..._PLAN_V1.md`.

```text
입력   <run_dir>/official_rows.json — 개발자가 공식 [분배금현황 다운로드] 파일에서 옮긴 여섯 행 · 출처 · 해시 · 팩트시트 대조
       봉인 판 krx_etf_universe_v1(읽기 전용 · 전후 검증 같음)
장부   1주 · D0 무조정 종가에 매입(편도 20bp) · D1 종가 평가 · 분배금 = 세전 원화 현금 보유(이자 · 추가 매입 0)
       권리 = T+2 결제일 < 지급기준일 · 지급 = 실지급일 ≤ D1(같으면 경계 확인 · 미확인 · 기말 넘김 = 자료 미충족)
검산   A · B 공통 원가 E 상쇄 → 기말 금액 차이 == 원본 행을 다시 읽어 독립 합산한 현금(원 단위 정확) → 그 뒤 수익률
출력   <run_dir>/{run.json, report.json, report.md}(git 제외 로컬) — run_dir 마다 한 번(report 가 있으면 거절)
```

외부 호출 0 · 봉인 판 · reader · 기존 연구 코드 변경 0.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date, datetime, timezone
from decimal import Decimal, getcontext
from pathlib import Path
from typing import Any, Optional, Sequence

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from app import krx_sealed_reader as K  # noqa: E402

getcontext().prec = 40

CODE = "069500"
FID = "2ETF01"
YEAR = 2025
D0_FIXED = "2025-01-02"  # PLAN §1-1 · 봉인 달력의 2025 첫 거래일
D1_FIXED = "2025-12-30"  # PLAN §1-1 · 봉인 달력의 2025 마지막 거래일
SETTLEMENT_LAG = 2  # KRX ETF 결제 T+2(판정 V1.1 A-2) · 봉인 거래일 축으로 센다
COST = Decimal("1.002")  # 편도 20bp
SCHEMA = "poc6_26_official_rows_v1"
SPLIT_RATIO_BOUNDS = (0.5, 2.0)  # 상장좌수 하루 변화가 이 밖이면 단위 변경 의심

INCLUDED = "INCLUDED"
NOT_ENTITLED_BEFORE = "NOT_ENTITLED_BEFORE_SETTLEMENT"
AFTER_PERIOD = "AFTER_PERIOD"
BOUNDARY_CHECK = "BOUNDARY_CHECK"
PAY_UNKNOWN = "DATA_INSUFFICIENT_PAY_UNKNOWN"
PAY_AFTER_D1 = "DATA_INSUFFICIENT_PAY_AFTER_D1"

RECONCILED = "SAMPLE_RECONCILED"
INSUFFICIENT = "DATA_INSUFFICIENT"


class InputError(ValueError):
    """official_rows.json 형식 · 범위 위반(계산하지 않음)."""


# ── 입력 ────────────────────────────────────────────────────────────────────


def _iso_day(value: Any, label: str, *, allow_none: bool = False) -> Optional[str]:
    if value is None and allow_none:
        return None
    if not isinstance(value, str) or len(value) != 10:
        raise InputError(f"{label} 형식 오류(YYYY-MM-DD): {value!r}")
    try:
        if date.fromisoformat(value).isoformat() != value:
            raise ValueError
    except ValueError:
        raise InputError(f"{label} 형식 오류(YYYY-MM-DD): {value!r}") from None
    return value


def _won(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise InputError(f"{label} 는 0 이상 원 단위 정수여야 한다: {value!r}")
    return value


def _hex64(value: Any, label: str) -> str:
    if not (
        isinstance(value, str)
        and len(value) == 64
        and all(c in "0123456789abcdef" for c in value)
    ):
        raise InputError(f"{label} 는 SHA-256 16진수 64자여야 한다")
    return value


def load_official(path: Path) -> dict[str, Any]:
    """official_rows.json — 형식 · 필수 칸 · 여섯 행 범위 · 팩트시트 대조 결과를 확인한다."""
    try:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise InputError(
            f"official_rows.json 을 읽지 못했다: {type(e).__name__}"
        ) from e
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
        raise InputError("official_rows.json schema 가 다르다")
    prod = doc.get("product") or {}
    if prod.get("code") != CODE or prod.get("fid") != FID:
        raise InputError(f"종목 식별이 다르다: {prod!r}")
    src = doc.get("source") or {}
    for key in (
        "page_url",
        "download_url",
        "downloaded_at",
        "file_type",
        "read_method",
    ):
        if not isinstance(src.get(key), str) or not src[key]:
            raise InputError(f"source.{key} 가 없다")
    _hex64(src.get("file_sha256"), "source.file_sha256")
    if src.get("http_status") is not None and not isinstance(src["http_status"], int):
        raise InputError("source.http_status 는 정수 또는 null")
    raw_rows = doc.get("rows")
    if not isinstance(raw_rows, list) or not raw_rows:
        raise InputError("rows 가 없다")
    rows = []
    for i, r in enumerate(raw_rows):
        if not isinstance(r, dict):
            raise InputError(f"rows[{i}] 형식 오류")
        rows.append(
            {
                "basic_date": _iso_day(r.get("basic_date"), f"rows[{i}].basic_date"),
                "pay_date": _iso_day(
                    r.get("pay_date"), f"rows[{i}].pay_date", allow_none=True
                ),
                "amount_krw": _won(r.get("amount_krw"), f"rows[{i}].amount_krw"),
            }
        )
    days = [r["basic_date"] for r in rows]
    if days != sorted(days) or len(set(days)) != len(days):
        raise InputError("rows 는 지급기준일 오름차순 · 중복 없음이어야 한다")
    in_year = [d for d in days if d.startswith(f"{YEAR}-")]
    before = [d for d in days if d < f"{YEAR}-01-01"]
    after = [d for d in days if d > f"{YEAR}-12-31"]
    cov = doc.get("coverage") or {}
    if cov.get("file_year_rows") != len(in_year):
        raise InputError(
            f"{YEAR} 지급 전체가 rows 에 없다: 파일 {cov.get('file_year_rows')!r} · rows {len(in_year)}"
        )
    if len(before) != 1 or len(after) != 1:
        raise InputError("양끝 인접 회차는 앞 · 뒤 각 1행이어야 한다")
    fs = doc.get("factsheet") or {}
    for key in ("url", "fetched_at"):
        if not isinstance(fs.get(key), str) or not fs[key]:
            raise InputError(f"factsheet.{key} 가 없다")
    _hex64(fs.get("file_sha256"), "factsheet.file_sha256")
    if not isinstance(fs.get("page"), int) or isinstance(fs.get("page"), bool):
        raise InputError("factsheet.page 는 쪽 번호(정수)")
    if not isinstance(fs.get("match"), bool):
        raise InputError("factsheet.match 는 true / false")
    return {"doc": doc, "rows": rows}


# ── 권리 · 장부 ─────────────────────────────────────────────────────────────


def settlement_date(calendar: Sequence[str], d0: str, lag: int = SETTLEMENT_LAG) -> str:
    """봉인 거래일 축에서 d0 다음 lag 번째 거래일."""
    i = list(calendar).index(d0)
    if i + lag >= len(calendar):
        raise InputError("결제일이 봉인 달력 밖이다")
    return calendar[i + lag]


def classify(row: dict, settle: str, d1: str) -> str:
    basic, pay = row["basic_date"], row["pay_date"]
    if basic < settle:
        return NOT_ENTITLED_BEFORE
    if basic == settle:
        return BOUNDARY_CHECK
    if basic > d1:
        return AFTER_PERIOD
    if pay is None:
        return PAY_UNKNOWN
    if pay > d1:
        return PAY_AFTER_D1
    return INCLUDED


def recount_cash(official_path: Path, settle: str, d1: str) -> int:
    """검산용 — 원본 파일을 다시 읽어 `classify` 를 쓰지 않고 날짜 비교만으로 현금을 다시 더한다."""
    doc = json.loads(Path(official_path).read_text(encoding="utf-8"))
    total = 0
    for r in doc["rows"]:
        if settle < r["basic_date"] <= d1 and r["pay_date"] is not None:
            if r["pay_date"] <= d1:
                total += int(r["amount_krw"])
    return total


def ledger(
    close0: Decimal,
    close1: Decimal,
    chain0: float,
    chain1: float,
    cash: int,
    recount: int,
) -> dict[str, Any]:
    """A · B · C · 차이 · 원 단위 정확 검산(공통 원가 E 상쇄)."""
    e = close0 * COST
    end_a = close1
    end_b = close1 + Decimal(cash)
    amount_gap = end_b - end_a  # E 를 상쇄한 기말 금액 차이
    exact = amount_gap == Decimal(recount) and Decimal(cash) == Decimal(recount)
    a = end_a / e - 1
    b = end_b / e - 1
    c = Decimal(repr(chain1 / chain0)) / COST - 1
    return {
        "start_cost_e": str(e),
        "end_value_a": str(end_a),
        "end_value_b": str(end_b),
        "cash_krw": cash,
        "recount_cash_krw": recount,
        "amount_gap_krw": str(amount_gap),
        "exact_check": exact,
        "b_minus_a_vs_cash_over_e": str((b - a) - Decimal(recount) / e),
        "A": str(a),
        "B": str(b),
        "C": str(c),
        "B_minus_A_pp": str((b - a) * 100),
        "C_minus_A_pp": str((c - a) * 100),
        "B_minus_C_pp": str((b - c) * 100),
    }


# ── 봉인 판 ─────────────────────────────────────────────────────────────────


def _price(text: Any) -> Optional[Decimal]:
    v = K._num(text)
    if v is None:
        return None
    d = Decimal(str(text).replace(",", "").strip())
    return d if d == d.to_integral_value() else None


def read_raw_069500(db_path: Path, first: str, last: str) -> list[dict[str, Any]]:
    """같은 봉인 판의 069500 원시 행(무조정 종가 · 대비 · 상장좌수) — 단위 대조용 · 읽기 전용."""
    con = K.open_readonly(db_path)
    try:
        rows = con.execute(
            "SELECT m.bas_dd, d.row_json FROM krx_dataset_member m JOIN krx_etf_daily_raw d "
            "ON d.response_id = m.response_id WHERE m.version_id = ? AND d.isu_cd = ? "
            "AND m.bas_dd BETWEEN ? AND ? ORDER BY m.bas_dd",
            (K.SEALED_VERSION, CODE, first.replace("-", ""), last.replace("-", "")),
        ).fetchall()
    finally:
        con.close()
    out = []
    for bas_dd, row_json in rows:
        r = json.loads(row_json)
        out.append(
            {
                "date": K._iso(bas_dd),
                "code": r.get("ISU_CD"),
                "close": _price(r.get("TDD_CLSPRC")),
                "cmpprev": _price(r.get("CMPPREVDD_PRC")),
                "list_shrs": K._num(r.get("LIST_SHRS")),
            }
        )
    return out


def unit_checks(
    raw: list[dict], rows: list[dict], calendar: Sequence[str]
) -> dict[str, Any]:
    """기준가 차이 후보일(전일 종가 ≠ 종가 − 대비)과 설명 여부 · 상장좌수 하루 변화 범위."""
    gaps = []
    for prev, cur in zip(raw, raw[1:]):
        if None in (prev["close"], cur["close"], cur["cmpprev"]):
            gaps.append({"date": cur["date"], "explained": False, "reason": "값 없음"})
            continue
        if cur["close"] - cur["cmpprev"] != prev["close"]:
            gaps.append({"date": cur["date"]})
    pos = {d: i for i, d in enumerate(calendar)}
    basics = {r["basic_date"] for r in rows}
    for g in gaps:
        if "explained" in g:
            continue
        i = pos.get(g["date"])
        nxt = calendar[i + 1] if i is not None and i + 1 < len(calendar) else None
        g["next_trading_day"] = nxt
        g["explained"] = nxt in basics  # T+2 → 분배락 후보 = 지급기준일 한 거래일 앞
    ratios = [
        cur["list_shrs"] / prev["list_shrs"]
        for prev, cur in zip(raw, raw[1:])
        if prev["list_shrs"] and cur["list_shrs"]
    ]
    lo, hi = SPLIT_RATIO_BOUNDS
    suspicious = [x for x in ratios if not lo <= x <= hi]
    return {
        "base_price_gap_days": gaps,
        "unexplained_gap_days": [g["date"] for g in gaps if not g["explained"]],
        "list_shrs_daily_ratio_min": min(ratios) if ratios else None,
        "list_shrs_daily_ratio_max": max(ratios) if ratios else None,
        "list_shrs_split_suspicious_days": len(suspicious),
        "codes": sorted({r["code"] for r in raw}),
    }


# ── 실행 ────────────────────────────────────────────────────────────────────


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def run(run_dir: Path, db_path: Path = K.DEFAULT_SEALED_DB) -> dict[str, Any]:
    run_dir = Path(run_dir)
    official_path = run_dir / "official_rows.json"
    if (run_dir / "report.json").exists():
        raise SystemExit(f"이미 계산한 run_dir 이다(한 번만): {run_dir}")
    started = _now()
    reasons: list[str] = []
    try:
        inp = load_official(official_path)
    except InputError as e:
        # 자료 조건 미충족 — 봉인 판을 읽지 않고 사유만 남긴다(설계 §5).
        report = {
            "status": INSUFFICIENT,
            "reasons": [f"입력: {e}"],
            "scope": f"{CODE} · {YEAR} · 1주 표본 검산",
        }
        _write(run_dir, report, started)
        return report
    before = K.verify_sealed_source(db_path)
    panel = K.load_panel(db_path)
    calendar = [d for d in panel.dates if d.startswith(f"{YEAR}-")]
    d0, d1 = calendar[0], calendar[-1]
    if (d0, d1) != (D0_FIXED, D1_FIXED):
        reasons.append(f"D0 · D1 이 PLAN 고정값과 다르다: {d0} · {d1}")
    s = panel.benchmark()
    i0, i1 = s.index[d0], s.index[d1]
    same_segment = len({s.segment[i] for i in range(i0, i1 + 1)}) == 1
    if not same_segment:
        reasons.append("D0 ~ D1 연결 구간이 끊겼다")
    if s.close_status[i0] != K.CLOSE_OK or s.close_status[i1] != K.CLOSE_OK:
        reasons.append("D0 · D1 무조정 종가가 유효하지 않다")
    raw = read_raw_069500(db_path, panel.dates[panel.dates.index(d0) - 1], d1)
    K.assert_same_source(
        before, K.verify_sealed_source(db_path)
    )  # 읽기 전후 같은 봉인 판
    by_date = {r["date"]: r for r in raw}
    close0, close1 = by_date[d0]["close"], by_date[d1]["close"]
    if (
        close0 is None
        or close1 is None
        or float(close0) != s.close[i0]
        or float(close1) != s.close[i1]
    ):
        reasons.append("원시 종가와 reader 종가가 다르다")
    settle = settlement_date(panel.dates, d0)
    units = unit_checks(raw, inp["rows"], panel.dates)
    if units["unexplained_gap_days"]:
        reasons.append(f"설명되지 않는 기준가 차이일: {units['unexplained_gap_days']}")
    if units["list_shrs_split_suspicious_days"]:
        reasons.append("상장좌수 하루 변화가 단위 변경 의심 범위다")
    if units["codes"] != [CODE]:
        reasons.append(f"종목 코드가 섞였다: {units['codes']}")
    fs = inp["doc"]["factsheet"]
    if fs["match"] is not True:
        reasons.append("팩트시트 대조 불일치")
    classified = [{**r, "status": classify(r, settle, d1)} for r in inp["rows"]]
    blocked = [
        c
        for c in classified
        if c["status"] in (BOUNDARY_CHECK, PAY_UNKNOWN, PAY_AFTER_D1)
    ]
    if blocked:
        reasons.append(f"권리 · 지급 경계 미충족 {len(blocked)}건")
    cash = sum(c["amount_krw"] for c in classified if c["status"] == INCLUDED)
    recount = recount_cash(official_path, settle, d1)
    book = None
    if not reasons:
        book = ledger(close0, close1, s.chain[i0], s.chain[i1], cash, recount)
        if not book["exact_check"]:
            reasons.append("원 단위 정확 검산 불일치")
    status = INSUFFICIENT if reasons else RECONCILED
    report = {
        "status": status,
        "reasons": reasons,
        "scope": f"{CODE} · {YEAR} · 1주 표본 검산",
        "d0": d0,
        "d1": d1,
        "settlement_date": settle,
        "rows": classified,
        "included_rows": sum(c["status"] == INCLUDED for c in classified),
        "unit_checks": units,
        "prices": {
            "close_d0": str(close0),
            "close_d1": str(close1),
            "chain_d0": s.chain[i0],
            "chain_d1": s.chain[i1],
            "same_segment": same_segment,
        },
        "ledger": book,
        "definitions": {
            "A": "D1 무조정 종가 ÷ E − 1",
            "B": "(D1 무조정 종가 + 수령 세전 현금) ÷ E − 1 · 현금 보유(재투자 · 이자 0)",
            "C": "(D1 연결 종가 ÷ D0 연결 종가) ÷ 1.002 − 1 · 연결 = KRX_BASEPRICE_CHAIN",
            "E": "D0 무조정 종가 × 1.002",
        },
        "sealed_source": before,
        "official_rows_sha256": _sha256(official_path),
    }
    _write(run_dir, report, started)
    return report


def _write(run_dir: Path, report: dict[str, Any], started: str) -> None:
    (run_dir / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (run_dir / "report.md").write_text(render_md(report), encoding="utf-8")
    meta = {
        "started_at": started,
        "finished_at": _now(),
        "status": report["status"],
        "run_dir": str(run_dir),
    }
    (run_dir / "run.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _pp(text: Optional[str]) -> str:
    return "—" if text is None else f"{Decimal(text):+.4f}%p"


def _pct(text: Optional[str]) -> str:
    return "—" if text is None else f"{Decimal(text) * 100:+.4f}%"


def render_md(rep: dict[str, Any]) -> str:
    lines = [
        f"# POC6-26 검산 보고 — {rep['scope']}",
        "",
        f"- 상태: **{rep['status']}**"
        + (f" · 사유: {' / '.join(rep['reasons'])}" if rep["reasons"] else ""),
    ]
    if "rows" not in rep:  # 입력 미충족 — 계산 전 멈춤
        return "\n".join(lines) + "\n"
    lines += [
        f"- D0 {rep['d0']} · D1 {rep['d1']} · T+2 결제일 {rep['settlement_date']} · "
        f"포함 회차 {rep['included_rows']}",
        "",
        "| 지급기준일 | 실지급일 | 세전 좌당(원) | 분류 |",
        "|---|---|---|---|",
    ]
    for r in rep["rows"]:
        lines.append(
            f"| {r['basic_date']} | {r['pay_date'] or '미확인'} | {r['amount_krw']} | {r['status']} |"
        )
    lines += [
        "",
        f"- 기준가 차이 후보일: {[g['date'] for g in rep['unit_checks']['base_price_gap_days']]}",
    ]
    book = rep["ledger"]
    if book:
        lines += [
            "",
            "| 항목 | 값 |",
            "|---|---|",
            f"| 시작 원가 E | {book['start_cost_e']} |",
            f"| 기말 평가 A(D1 종가) | {book['end_value_a']} |",
            f"| 기말 평가 B(D1 종가 + 현금) | {book['end_value_b']} |",
            f"| 수령 현금 · 독립 재합산 | {book['cash_krw']} · {book['recount_cash_krw']} |",
            f"| 원 단위 정확 검산 | {book['exact_check']} |",
            f"| A · B · C | {_pct(book['A'])} · {_pct(book['B'])} · {_pct(book['C'])} |",
            f"| B−A · C−A · B−C | {_pp(book['B_minus_A_pp'])} · "
            f"{_pp(book['C_minus_A_pp'])} · {_pp(book['B_minus_C_pp'])} |",
        ]
    lines += [
        "",
        "정의: " + " · ".join(f"{k} = {v}" for k, v in rep["definitions"].items()),
    ]
    return "\n".join(lines) + "\n"


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="POC6-26 KODEX200 2025 1주 검산(한 번)")
    ap.add_argument("--run-dir", required=True, type=Path)
    args = ap.parse_args(argv)
    rep = run(args.run_dir)
    print(
        json.dumps(
            {"status": rep["status"], "reasons": rep["reasons"]}, ensure_ascii=False
        )
    )
    return 0 if rep["status"] == RECONCILED else 2


if __name__ == "__main__":
    raise SystemExit(main())
