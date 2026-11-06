"""POC6-24 보유 판단의 자금 기준(검토에 포함할 현금 C · 이번 검토의 추가 투입 한도 A · 확인일).

저장 · 검증 · 계산 · 미리보기 글.

설계 `docs/ai_design/POC6/POC6_24_HOLDINGS_CAPITAL_CONTEXT_AND_AI_EVIDENCE_DESIGN_V1.md` · PLAN 판정 ·
전체 통합설계 V1.1 `..._PLAN_DECISION_2026-11-06.md`(우선) · PLAN `docs/ai_plan/POC6/..._PLAN_V1.md`.

```text
저장   holdings.HOLDINGS_DIR / capital_context.json(호출 때 해석)
       — holdings_latest.json(「보유 OCI 반영」 대상)과 별도 문서
       {schema_version 1, cash_krw, limit_krw, confirmed_on, saved_at}
       · 같은 폴더 임시 파일 · fsync · os.replace · 별도 잠금
읽기   파일 없음 · 세 칸 null = NOT_ENTERED / 값 있음 = ENTERED
       / 손상 = CapitalCorrupt(미입력 · 0원으로 바꾸지 않고 덮어쓰지 않음)
검증   금액 = JSON 정수(불 · 소수 · 문자열 거부) · 0 ≤ 금액 ≤ 2^53 − 1 · 한도는 현금이 있을 때만 · 한도 ≤ 현금
       · 현금이 있으면 확인일(YYYY-MM-DD · 오늘 KST 이하) · 둘 다 비면 확인일도 비움
계산   V = 평가금액 있는 행의 합 · 완전 = 모든 행에 평가금액 · T = 완전 · 현금 입력이면 V + C(0원도 알려진 합계)
       · 보유/현금 구성 · '입력 현금 포함' 비중 = T > 0 일 때만 · 한도는 합계에 더하지 않음
       · 가격 기준일 = 평가 행 날짜 최소 ~ 최대 · 같은 기준일 = 모든 평가 행 날짜가 확인일과 같을 때만
```

기존 시장 비중 · 매입 비중 · 손익의 정의는 바꾸지 않는다. OCI · Telegram/PUSH · PARAM 으로 보내지 않는다.
"""

from __future__ import annotations

import json
import math
import os
import tempfile
import threading
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from app import holdings as holdings_module

FILE_NAME = "capital_context.json"
SCHEMA_VERSION = 1
MAX_KRW = 2**53 - 1  # 화면(JavaScript) 숫자가 정확히 나타내는 최대 정수
_KST = timezone(timedelta(hours=9))
_LOCK = threading.Lock()
_KEYS = ("cash_krw", "limit_krw", "confirmed_on")


class CapitalInputError(ValueError):
    """저장할 수 없는 입력(사유는 화면에 그대로 보여 줄 한국어)."""


class CapitalCorrupt(Exception):
    """저장 파일을 읽을 수 없음 — 미입력 · 0원으로 바꾸지 않는다."""


def path() -> Path:
    # 호출 때 해석 — conftest 가 holdings.HOLDINGS_DIR 을 tmp 로 바꿔 끼운다.
    return holdings_module.HOLDINGS_DIR / FILE_NAME


def today_kst() -> date:
    return datetime.now(_KST).date()


# ── 검증 ─────────────────────────────────────────────────────────────────────


def _amount(value: Any, label: str) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise CapitalInputError(f"{label}은 원 단위 정수로 입력하세요.")
    if value < 0:
        raise CapitalInputError(f"{label}은 0원 이상이어야 합니다.")
    if value > MAX_KRW:
        raise CapitalInputError(f"{label}이 너무 큽니다.")
    return value


def _day(value: Any, today: date) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        raise CapitalInputError("확인일 형식이 올바르지 않습니다(YYYY-MM-DD).")
    try:
        d = date.fromisoformat(value)
    except ValueError:
        raise CapitalInputError(
            "확인일 형식이 올바르지 않습니다(YYYY-MM-DD)."
        ) from None
    if len(value) != 10 or d.isoformat() != value:
        raise CapitalInputError("확인일 형식이 올바르지 않습니다(YYYY-MM-DD).")
    if d > today:
        raise CapitalInputError("확인일은 오늘 이후로 정할 수 없습니다.")
    return value


def validate(cash: Any, limit: Any, confirmed_on: Any, today: date) -> tuple:
    """(현금 · 한도 · 확인일) — 어기면 CapitalInputError(저장 안 함)."""
    c = _amount(cash, "검토에 포함할 현금")
    a = _amount(limit, "추가 투입 한도")
    d = _day(confirmed_on, today)
    if a is not None and c is None:
        raise CapitalInputError(
            "추가 투입 한도를 넣으려면 검토에 포함할 현금도 넣으세요."
        )
    if a is not None and a > c:
        raise CapitalInputError(
            "추가 투입 한도가 검토에 포함할 현금보다 클 수 없습니다."
        )
    if c is not None and d is None:
        raise CapitalInputError("현금을 넣으면 확인일도 함께 넣으세요.")
    if c is None and d is not None:
        raise CapitalInputError("현금이 비어 있으면 확인일도 비워 두세요.")
    return c, a, d


# ── 저장 · 읽기 ──────────────────────────────────────────────────────────────


def _state(doc: Optional[dict]) -> dict[str, Any]:
    if doc is None or all(doc.get(k) is None for k in _KEYS):
        return {
            "status": "NOT_ENTERED",
            "cash_krw": None,
            "limit_krw": None,
            "confirmed_on": None,
            "saved_at": None if doc is None else doc.get("saved_at"),
        }
    return {
        "status": "ENTERED",
        **{k: doc[k] for k in _KEYS},
        "saved_at": doc.get("saved_at"),
    }


def _read_doc() -> Optional[dict]:
    p = path()
    if not p.exists():
        return None
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError) as e:  # 깊은 중첩 손상도 읽기 실패
        raise CapitalCorrupt(
            f"자금 기준 파일을 읽지 못했습니다: {type(e).__name__}"
        ) from e
    if (
        not isinstance(doc, dict)
        or type(doc.get("schema_version")) is not int  # true · 1.0 은 형식 버전 아님
        or doc.get("schema_version") != SCHEMA_VERSION
        or not set(_KEYS) <= set(doc)
        or not isinstance(doc.get("saved_at"), (str, type(None)))
    ):
        raise CapitalCorrupt("자금 기준 파일 형식이 올바르지 않습니다.")
    try:  # 저장 뒤 날짜가 지나도 '미래' 가 되지 않으므로 오늘로 검사해도 된다
        validate(doc["cash_krw"], doc["limit_krw"], doc["confirmed_on"], today_kst())
    except CapitalInputError as e:
        raise CapitalCorrupt(f"자금 기준 파일 값이 올바르지 않습니다: {e}") from e
    return doc


def read() -> dict[str, Any]:
    """저장값(손상 = CapitalCorrupt)."""
    return _state(_read_doc())


def load_status() -> dict[str, Any]:
    """화면 · 미리보기용 — 읽기 실패는 READ_FAILED(0원 · 미입력으로 바꾸지 않음)."""
    try:
        return read()
    except CapitalCorrupt:
        return {
            "status": "READ_FAILED",
            "cash_krw": None,
            "limit_krw": None,
            "confirmed_on": None,
            "saved_at": None,
        }


def _atomic_write(doc: dict[str, Any]) -> None:
    p = path()
    p.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(doc, indent=2, ensure_ascii=False).encode("utf-8")
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), prefix=".capital-", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(body)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, p)
    except BaseException:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise


def save(
    cash: Any, limit: Any, confirmed_on: Any, now: Optional[datetime] = None
) -> dict:
    """한 묶음 저장 · 비우기(세 칸 None). 입력 오류 = CapitalInputError · 손상 파일 = CapitalCorrupt(덮어쓰지 않음)."""
    at = (now or datetime.now(_KST)).astimezone(_KST)
    with _LOCK:
        _read_doc()  # 손상이면 여기서 멈춘다
        c, a, d = validate(cash, limit, confirmed_on, at.date())
        doc = {
            "schema_version": SCHEMA_VERSION,
            "cash_krw": c,
            "limit_krw": a,
            "confirmed_on": d,
            "saved_at": at.isoformat(timespec="seconds"),
        }
        _atomic_write(doc)
        return _state(doc)


# ── 계산 ─────────────────────────────────────────────────────────────────────


def _pct(part: float, whole: float) -> float:
    return round(part / whole * 100.0, 2)


def _date_of(asof: Any) -> Optional[str]:
    if not isinstance(asof, str) or len(asof) < 10:
        return None
    try:
        return date.fromisoformat(asof[:10]).isoformat()
    except ValueError:
        return None


def view(rows: list, cap: dict[str, Any]) -> dict[str, Any]:
    """rows = 보유 행(`eval_amount` · `price_asof` 속성) · cap = load_status() 결과."""
    evals = [r.eval_amount for r in rows]
    priced = [r for r in rows if r.eval_amount is not None]
    v = round(sum(e for e in evals if e is not None), 2)
    complete = len(priced) == len(rows)
    days = [_date_of(r.price_asof) for r in priced]
    known = sorted(d for d in days if d is not None)
    if not rows:
        price_date = {"state": "NO_HOLDINGS", "min": None, "max": None}
    elif not priced:
        price_date = {"state": "NONE_PRICED", "min": None, "max": None}
    elif len(known) < len(days):
        price_date = {"state": "UNKNOWN", "min": None, "max": None}
    else:
        price_date = {"state": "KNOWN", "min": known[0], "max": known[-1]}
    cash = cap.get("cash_krw")
    total = None
    reason = None
    if cap.get("status") == "READ_FAILED":
        reason = "READ_FAILED"
    elif cash is None:
        reason = "NO_CASH"
    elif not complete:
        reason = "PARTIAL"
    else:
        total = round(v + cash, 2)
    shares_ok = total is not None and total > 0
    confirmed = cap.get("confirmed_on")
    same_day = None
    if total is not None and rows and price_date["state"] == "KNOWN":
        same_day = all(d == confirmed for d in days)
    return {
        **cap,
        "holdings_value": v,
        "holdings_rows": len(rows),
        "priced_rows": len(priced),
        "complete": complete,
        "price_date": price_date,
        "total_krw": total,
        "total_reason": reason,
        "holdings_share_pct": _pct(v, total) if shares_ok else None,
        "cash_share_pct": _pct(cash, total) if shares_ok else None,
        "same_day": same_day,
    }


def with_cash_pct(eval_amount: Optional[float], cv: dict[str, Any]) -> Optional[float]:
    """행 · 종목 합산 평가금액의 '입력 현금 포함' 비중(T > 0 일 때만)."""
    total = cv.get("total_krw")
    if eval_amount is None or total is None or not total > 0:
        return None
    return _pct(eval_amount, total)


# ── 미리보기 글(판정 Q1: 새 금액 = V · C · A · T 만) ──────────────────────────────


def won(value: Optional[float]) -> str:
    if value is None or not math.isfinite(value):
        return "확인 불가"
    text = f"{value:,.2f}".rstrip("0").rstrip(".")
    return f"{text}원"


def _pct_text(value: Optional[float]) -> str:
    return "계산 안 함" if value is None else f"{value:.2f}%"


UNBUILT_LINE = "보유 · 자금 기준을 만들지 못했습니다 — 현금 · 한도 · 비중 확인 불가(0원으로 보지 않음)."

_REASON = {
    "NO_CASH": "현금 미입력",
    "PARTIAL": "보유 일부 시세 미확인",
    "READ_FAILED": "자금 기준 읽기 실패",
}


def _price_date_text(pd: dict[str, Any]) -> str:
    st = pd["state"]
    if st == "NO_HOLDINGS":
        return "가격 기준일 대상 없음"
    if st == "NONE_PRICED":
        return "가격 기준일 확인 불가(시세 확인된 보유 없음)"
    if st == "UNKNOWN":
        return "가격 기준일 확인 불가"
    if pd["min"] == pd["max"]:
        return f"가격 기준일 {pd['min']}"
    return f"가격 기준일 {pd['min']} ~ {pd['max']}"


def preview_lines(
    cv: Optional[dict[str, Any]], target: Optional[dict[str, Any]]
) -> list[str]:
    """[보유 · 자금 기준] 묶음 줄. target = {kind · held · weight_in · weight_with_cash · unknown}."""
    if cv is None:
        return [
            "보유 · 자금 기준 확인 불가 — 보유 자료를 읽지 못했습니다(0원으로 보지 않음)."
        ]
    scope = (
        "보유 없음"
        if cv["holdings_rows"] == 0
        else (
            f"{cv['priced_rows']}/{cv['holdings_rows']}종목 전체"
            if cv["complete"]
            else f"부분 합계 {cv['priced_rows']}/{cv['holdings_rows']}종목"
        )
    )
    # 시세가 하나도 없으면 합 0 을 '0원'으로 적지 않는다.
    value = (
        "확인 불가"
        if cv["price_date"]["state"] == "NONE_PRICED"
        else won(cv["holdings_value"])
    )
    lines = [
        f"보유 평가액 {value} · {scope} · "
        f"{_price_date_text(cv['price_date'])} · 현금 제외 · 모든 계좌 합산"
    ]
    status = cv.get("status")
    if status == "READ_FAILED":
        lines.append(
            "자금 기준 읽기 실패 — 현금 · 한도 확인 불가(0원 · 무제한으로 보지 않음) · 합계 · 현금 포함 비중 계산 안 함"
        )
    elif status == "NOT_ENTERED":
        lines.append(
            "검토에 포함할 현금 미입력(0원 아님) · 추가 투입 한도 미입력 — 합계 · 현금 포함 비중 계산 안 함"
        )
    else:
        limit = cv.get("limit_krw")
        limit_text = (
            "미정(현금 전액을 한도로 보지 않음)" if limit is None else won(limit)
        )
        lines.append(
            f"검토에 포함할 현금 {won(cv['cash_krw'])} · 이번 검토의 추가 투입 한도 {limit_text} · "
            f"확인일 {cv['confirmed_on']} · 직접 입력한 확인일 기준 값 · 거래/입출금 후 자동 반영되지 않음"
        )
    total = cv.get("total_krw")
    if total is not None:
        mix = (
            f"보유 {_pct_text(cv['holdings_share_pct'])} · 현금 {_pct_text(cv['cash_share_pct'])}"
            if cv["holdings_share_pct"] is not None
            else "보유 · 현금 구성 계산 불가(합계 0원)"
        )
        same = cv.get("same_day")
        when = {
            True: " · 가격 기준일과 현금 확인일이 같은 합계",
            False: " · 가격 기준일과 현금 확인일이 다른 참고 합계",
        }.get(same, "")
        if same is None and cv["price_date"]["state"] == "UNKNOWN":
            when = " · 가격 기준일 확인 불가 — 같은 기준일 합계로 보지 않음"
        lines.append(
            f"보유 + 입력 현금 합계 {won(total)}(이 보유 목록과 입력 현금의 평가 합계 · 투자 총예산 · 전체 재산 아님 · "
            f"한도는 더하지 않음) · {mix}{when}"
        )
    elif status == "ENTERED":
        lines.append(
            f"보유 + 입력 현금 합계 계산 안 함({_REASON.get(cv['total_reason'], '확인 불가')})"
        )
    lines.append(_target_line(target, _weight_date_note(cv)))
    return lines


def _weight_date_note(cv: dict[str, Any]) -> str:
    """'입력 현금 포함' 비중에 붙일 기준일 표시(합계 줄과 같은 규칙 · 설계 B-3 '참고 합계/비중')."""
    if cv.get("total_krw") is None:
        return ""
    if cv.get("same_day") is False:
        return "(기준일이 다른 참고 비중)"
    if cv["price_date"]["state"] == "UNKNOWN":
        return "(가격 기준일 확인 불가 — 같은 기준일 비중으로 보지 않음)"
    return ""


def _target_line(target: Optional[dict[str, Any]], note: str = "") -> str:
    if target is None:
        return "이 종목 비중: 보유 여부 확인 불가"
    base = "현금 제외 · 부분 평가액 기준" if target.get("partial") else "현금 제외"
    weights = (
        f"보유 내 {_pct_text(target.get('weight_in'))}({base}) · "
        f"입력 현금 포함 {_pct_text(target.get('weight_with_cash'))}"
        + (note if target.get("weight_with_cash") is not None else "")
    )
    if target.get("unknown"):
        weights = (
            "보유 내 미확인 · 입력 현금 포함 미확인(같은 종목 일부 계좌 행 시세 미확인)"
        )
    if target.get("kind") == "candidate":
        if not target.get("held"):
            return "이 종목: 후보 · 현재 보유 아님 — 보유 비중 없음"
        return f"이 종목: 후보 · 현재 보유 중 — 같은 종목 모든 계좌 합산: {weights}"
    if not target.get("held"):
        return "이 종목: 현재 등록 보유에 없음 — 보유 비중 없음"
    return f"이 종목 비중(같은 종목 모든 계좌 합산): {weights}"
