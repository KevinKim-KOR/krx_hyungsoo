"""개인정보 · raw identifier 노출 **탐지 알고리즘** (지시문 §7).

Cleanup / FIX r7 Round 3 에서 `privacy.py` 로부터 분리. 정책 상수는
`privacy_policy.py` 에서 read-only 로 참조.

계약:
- detector 반환은 항상 실제 boolean (int 0/1 · None · 문자열 금지).
- notes 가 비어 있으면 False.
- 정책 상수를 alter 하지 않는다.
"""

from __future__ import annotations

import re as _re
from typing import TYPE_CHECKING

from app.runtime_evidence.privacy_policy import (
    ACCOUNT_GROUP_DEFAULT_LABEL,
    PRIVACY_CONTEXT_TOKENS,
    PRIVACY_CONTEXT_WINDOW,
    PRIVACY_NUMERIC_MIN_LEN,
    RAW_IDENT_TOKENS,
)

if TYPE_CHECKING:
    from app.holdings import Holding


def has_numeric_word(text: str, value: str) -> bool:
    """숫자 value 가 개인정보 문맥에 노출됐는지 검사.

    검증자 확정 계약:
    1. value 가 non-digit 경계로 감싸진 단어여야 한다 (date/percent 오탐 회피).
    2. value 매칭 위치의 좌·우 PRIVACY_CONTEXT_WINDOW 자 내에
       PRIVACY_CONTEXT_TOKENS 하나가 있어야 실제 leak 로 인정.
    이 조합은 "TOP10", "20거래일", "STAR50" 같은 정상 문맥은 통과하고,
    실제 개인정보 필드가 template 에 우회 노출되는 시나리오는 차단한다.
    """
    if not value or not value.isdigit():
        return False
    pattern = _re.compile(r"(?<!\d)" + _re.escape(value) + r"(?!\d)")
    for m in pattern.finditer(text):
        start = max(0, m.start() - PRIVACY_CONTEXT_WINDOW)
        window = text[start : m.end() + PRIVACY_CONTEXT_WINDOW]  # noqa: E203
        if any(tok in window for tok in PRIVACY_CONTEXT_TOKENS):
            return True
    return False


def has_string_word(text: str, value: str) -> bool:
    """비숫자 문자열 값 (account_group 등) 검사 — 단순 substring."""
    return bool(value) and value in text


def _to_int_str(v) -> str | None:
    """숫자 값을 정수 문자열로 변환. 실패 시 None."""
    if v is None:
        return None
    try:
        return str(int(v))
    except (TypeError, ValueError):
        return None


def _extract_numeric_candidates(
    qty, avg, evaluation_amount=None, pnl_amount=None
) -> set[str]:
    """holding 의 개인정보 숫자 값 후보 세트.

    검사 대상 (§7.1):
    - quantity
    - avg_buy_price
    - invested_amount (= avg × qty, 계산 파생)
    - evaluation_amount (= qty × 시장가, holdings enrichment 결과)
    - realized/unrealized pnl_amount (evidence payload 로부터 힌트)
    """
    candidates: set[str] = set()
    for v in (qty, avg, evaluation_amount, pnl_amount):
        s = _to_int_str(v)
        if s is not None:
            candidates.add(s)
    # invested_amount = avg × qty (계산 파생).
    if qty is not None and avg is not None:
        try:
            candidates.add(str(int(float(avg) * float(qty))))
        except (TypeError, ValueError):
            pass
    return candidates


def _hints_by_ticker(evidence_payload) -> dict[str, dict]:
    """evidence_payload.holdings 안의 개인정보 힌트 (evaluation_amount 등) 를
    ticker 기준 dict 로 변환.

    build_holdings_market_evidence 계약 (holdings_market_evidence.py:490 이하):
      holding_out["holding"] = {
          "quantity": ...,
          "avg_buy_price": ...,
          "evaluation_amount": ...,
          "pnl_rate_pct": ...,
      }
    이 값들은 detector 가 leak 여부를 판정하는 근거로만 사용 (본문에는 노출 X).
    """
    if not isinstance(evidence_payload, dict):
        return {}
    out: dict[str, dict] = {}
    for h_out in evidence_payload.get("holdings") or []:
        if not isinstance(h_out, dict):
            continue
        ticker = h_out.get("ticker")
        if not ticker:
            continue
        holding_block = h_out.get("holding") or {}
        if not isinstance(holding_block, dict):
            continue
        out[ticker] = holding_block
    return out


def detect_private_values_exposed(
    holdings_list: "list[Holding]",
    notes: list[str],
    evidence_payload=None,
) -> bool:
    """실제 개인정보 값이 composed notes 에 노출됐는지 boolean.

    검사 대상 (§7.1): quantity · avg_buy_price · invested_amount (avg × qty)
    · evaluation_amount · pnl_amount · account_group. key 이름이 아니라 각
    holding 의 실제 값 substring 검사.

    Args:
        holdings_list: 로드된 Holding 리스트 (quantity/avg_buy_price 원본).
        notes: composed 사용자용 문장 리스트 (스캔 대상 텍스트).
        evidence_payload: (optional) build_holdings_market_evidence 결과 dict.
            각 holding 항목의 `holding.evaluation_amount` 등을 leak 후보로 참조.
            None 이면 evaluation_amount 는 스캔에서 제외 (기존 계약).
    """
    if not notes:
        return False
    text = "\n".join(notes)
    hints = _hints_by_ticker(evidence_payload) if evidence_payload else {}
    for h in holdings_list:
        qty = getattr(h, "quantity", None)
        avg = getattr(h, "avg_buy_price", None)
        acct = getattr(h, "account_group", None)
        hint = hints.get(getattr(h, "ticker", None), {})
        eval_amt = hint.get("evaluation_amount")
        pnl_amt = (
            hint.get("pnl_amount")
            or hint.get("realized_pnl")
            or hint.get("unrealized_pnl")
        )

        for c in _extract_numeric_candidates(qty, avg, eval_amt, pnl_amt):
            if len(c) >= PRIVACY_NUMERIC_MIN_LEN and has_numeric_word(text, c):
                return True
        if acct and isinstance(acct, str) and acct != ACCOUNT_GROUP_DEFAULT_LABEL:
            if has_string_word(text, acct):
                return True
    return False


def detect_raw_identifier_exposed(notes: list[str]) -> bool:
    """내부 reason code · raw source key · raw push_kind 노출 boolean."""
    if not notes:
        return False
    text = "\n".join(notes)
    return any(tok in text for tok in RAW_IDENT_TOKENS)
