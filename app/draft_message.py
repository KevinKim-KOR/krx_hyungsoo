"""POC2 Step 1A + Step 2B + Step 3 — holdings 기반 draft_payload → 사람이 읽는 message_text.

설계자 결정 (Step 1A):
- handoff artifact 에 top-level `message_text` 키 추가
- 메시지 문자열 생성 책임은 로컬 백엔드(여기). OCI bash 는 JSON 파싱하지 않음
- raw JSON 노출 금지. 존재하는 필드만 줄 단위로 표시
- 데이터 새로 만들지 않음 (현재가/평가손익/score 추가 금지)
- 없는 필드는 생략. undefined/null 노출 금지

설계자 결정 (Step 3 — First Factor Signal Integration):
- draft_payload.factor_signals 에서 scope='portfolio' signal 1개를 찾아 [판단 사유]
  섹션 1줄을 헤더 직후에 삽입한다.
- 종목 기준 언급은 평가 계산 가능 row 중 max_weight_row 1개로 고정 (signal 빌더 책임).
- 모든 holdings row 의 factor 사유를 메시지에 나열하지 않는다 (Top N 정책 금지).
- factor 계산 불가 시 portfolio signal 의 fallback_text 1줄을 그대로 사용한다.
- 길이 방어 정책(MAX_LENGTH_CHARS=3500) 그대로 유지.

설계자 결정 (Step 5B — Minimal Momentum Engine Execution):
- draft_payload.momentum_result.summary 에서 1줄을 만들어 기존 [판단 사유] 섹션의
  bullet 으로 추가한다 (별도 [모멘텀 점검] 헤더 신설 금지 — 헤더 중복 방지).
- top_candidate 가 있으면 그 reason_text 를, 없으면 summary_reason_text 를 사용한다.
- 전체 후보 순위 / Top N 정책 / BUY·SELL / 리밸런싱 표현 금지.
- placeholder 산식 성격이 드러나도록 "이 값은 최종 투자 판단 산식이 아닙니다" 문구를
  유지한다 (summary 빌더가 책임).

설계자 결정 (Step 2B — Telegram Message Compaction):
- Telegram 메시지는 "전체 상세 보고서" 가 아니라 "승인 결과 요약 + 주목 종목 일부" 다.
- 보유 종목 18+ 에서도 message_text 가 안전 한도(MAX_LENGTH_CHARS=3500) 이하로 생성된다.
- 기본 HOLD 종목(action=HOLD + 기본 reason)은 요약 계산에는 포함되지만 상세 목록에는 빠진다.
- Top N 선별 시 누락/None/NaN/비숫자 값은 정렬 대상에서 제외 (price_missing 종목을 손익률 0% 로 취급 금지).
- 전체 요약은 시세 확인/미확인 종목 수를 구분하고, 평가금액/손익/수익률은 "시세 확인 종목 기준" 임을 명시.
- snapshot/history/전일 대비 변화 감지 일체 도입하지 않는다 (이번 단계 외).
- message split 안 함 — 한 메시지로 발송하되 길이 안전 한도 초과 시 주목 종목을 더 줄이고,
  최후에는 잘라낸 뒤 잘림 안내 문구를 포함한다.

대상은 holdings 기반 draft 만 명확히 식별한다 (recommendations 항목에
quantity/avg_buy_price 등 holdings 필드가 들어있는 형태). 식별 불가 / 누락 시는
빈 문자열을 반환하여 호출자가 적절히 처리하게 한다.
"""

from __future__ import annotations

from typing import Any, Optional

# Step 5D-2 Final — leaf format / 항목 식별 helpers 는 message_helpers.py 로 분리.
# 본 모듈은 helpers 를 재공개(re-export) 하여 기존 import 경로
# (`from app.draft_message import ...` / `draft_message.DEFAULT_HOLD_REASON`) 호환 유지.
from app.message_helpers import (
    DEFAULT_HOLD_REASON,
    _format_money,
    _format_pct,
    _format_signed_money,
    _format_signed_pct,
    _is_calc_available,
    _is_priced,
    _item_label,
    _to_finite_float,
)

__all__ = [
    "MAX_LENGTH_CHARS",
    "TOP_N_PRICE_MISSING",
    "TOP_N_BOTTOM_PNL_RATE",
    "TOP_N_TOP_MARKET_WEIGHT",
    "TOP_N_TOP_PNL_RATE",
    "DEFAULT_HOLD_REASON",
    "TRUNCATION_NOTICE",
    "JUDGMENT_SECTION_HEADER",
    "MOMENTUM_BULLET_LABEL",
    "is_holdings_draft",
    "compute_summary",
    "select_focus_items",
    "build_message_text",
]

# Step 2B 정책 상수 — 이번 단계에서는 설정 파일로 빼지 않는다 (BACKLOG).
MAX_LENGTH_CHARS = 3500
TOP_N_PRICE_MISSING = 3
TOP_N_BOTTOM_PNL_RATE = 3
TOP_N_TOP_MARKET_WEIGHT = 3
TOP_N_TOP_PNL_RATE = 3

TRUNCATION_NOTICE = (
    "...(메시지 길이 제한으로 일부 생략됨. 전체 상세는 웹 화면에서 확인하세요.)"
)

# Step 3: 판단 사유 섹션의 라벨. portfolio scope signal 1줄만 표시.
JUDGMENT_SECTION_HEADER = "[판단 사유]"

# Step 5B: 모멘텀 점검 bullet 라벨. [판단 사유] 섹션 안의 두 번째 bullet 으로 추가.
MOMENTUM_BULLET_LABEL = "모멘텀 점검"


def is_holdings_draft(payload: Any) -> bool:
    """draft_payload 가 holdings 기반 형태인지 식별.

    기준: recommendations 가 list 이고 첫 항목에 quantity 또는 avg_buy_price 가 있으면
    holdings 기반으로 본다 (POC2 Step 1 운영 흐름).
    """
    if not isinstance(payload, dict):
        return False
    recs = payload.get("recommendations")
    if not isinstance(recs, list) or len(recs) == 0:
        return False
    head = recs[0]
    if not isinstance(head, dict):
        return False
    return ("quantity" in head) or ("avg_buy_price" in head)


# ─── Step 2B 핵심 — 요약 계산 ─────────────────────────────────────────


def compute_summary(recs: list[dict[str, Any]]) -> dict[str, Any]:
    """전체 보유종목 요약. 시세 확인/미확인 + 계산 가능 여부를 분리.

    카운트 정의:
    - total_count          : 전체 종목 수
    - priced_count         : 시세 확인 종목 수 (current_price 유효)
    - unpriced_count       : 시세 미확인 종목 수
    - calc_available_count : 평가 계산 가능 종목 수 (current_price + eval_amount + invested_amount 모두 유효 양수)
    - calc_missing_count   : 시세는 있는데 평가 계산 불가능 종목 수 (priced - calc_available)

    집계 정의:
    - total_invested  : 전체 종목 invested_amount 합계 (있는 것만)
    - priced_eval     : 평가 계산 가능 종목 기준 eval_amount 합계 (계산 정보 부족 종목은 0 으로 취급하지 않음)
    - priced_pnl      : 같은 종목 기준 손익 합계
    - priced_pnl_rate_pct : 같은 종목 기준 수익률

    "평가금액/평가손익/평가수익률" 은 평가 계산 가능 종목 기준만 사용.
    계산 정보 부족 종목은 0 으로 취급하지 않고 별도 카운트로 노출한다.
    """
    total_count = len(recs)
    priced_items = [it for it in recs if isinstance(it, dict) and _is_priced(it)]
    calc_items = [it for it in priced_items if _is_calc_available(it)]
    unpriced_count = total_count - len(priced_items)
    calc_missing_count = len(priced_items) - len(calc_items)

    total_invested = 0.0
    for it in recs:
        if not isinstance(it, dict):
            continue
        n = _to_finite_float(it.get("invested_amount"))
        if n is not None:
            total_invested += n

    calc_invested = 0.0
    calc_eval = 0.0
    for it in calc_items:
        inv = _to_finite_float(it.get("invested_amount"))
        ev = _to_finite_float(it.get("eval_amount"))
        # _is_calc_available 통과한 종목이라 두 값 모두 유효 양수 보장.
        calc_invested += inv  # type: ignore[operator]
        calc_eval += ev  # type: ignore[operator]

    calc_pnl = calc_eval - calc_invested if calc_items else None
    calc_pnl_rate = (
        (calc_pnl / calc_invested * 100.0)
        if calc_items and calc_invested > 0 and calc_pnl is not None
        else None
    )

    return {
        "total_count": total_count,
        "priced_count": len(priced_items),
        "unpriced_count": unpriced_count,
        "calc_available_count": len(calc_items),
        "calc_missing_count": calc_missing_count,
        "total_invested": total_invested,
        "priced_eval": calc_eval if calc_items else None,
        "priced_pnl": calc_pnl,
        "priced_pnl_rate_pct": calc_pnl_rate,
    }


def _render_summary_lines(summary: dict[str, Any]) -> list[str]:
    """요약 dict → 사람이 읽는 줄 묶음.

    평가 라벨은 "시세 확인" 이 아니라 "평가 계산 N개 기준" 으로 표기 — current_price
    는 있지만 eval_amount 가 누락된 종목이 0 원으로 취급되지 않도록 명시 분리.
    """
    lines: list[str] = ["", "전체 요약:"]
    lines.append(f"   - 보유 종목: {summary['total_count']}개")
    lines.append(
        f"   - 시세 확인: {summary['priced_count']}개 / "
        f"미확인: {summary['unpriced_count']}개"
    )
    if summary.get("calc_missing_count", 0) > 0:
        lines.append(
            f"   - 평가 계산 가능: {summary['calc_available_count']}개 / "
            f"계산 정보 부족: {summary['calc_missing_count']}개"
        )

    total_inv = _format_money(summary.get("total_invested"))
    if total_inv is not None:
        lines.append(f"   - 총 매입금액: {total_inv}")

    calc_count = summary.get("calc_available_count", 0)
    if calc_count > 0:
        basis = f"(평가 계산 {calc_count}개 기준)"
        ev = _format_money(summary.get("priced_eval"))
        if ev is not None:
            lines.append(f"   - 평가금액: {ev} {basis}")
        pnl = _format_signed_money(summary.get("priced_pnl"))
        if pnl is not None:
            lines.append(f"   - 평가손익: {pnl} {basis}")
        pnl_rate = _format_signed_pct(summary.get("priced_pnl_rate_pct"))
        if pnl_rate is not None:
            lines.append(f"   - 평가수익률: {pnl_rate} {basis}")

    if summary["unpriced_count"] > 0 or summary.get("calc_missing_count", 0) > 0:
        # 시세 미확인 또는 계산 정보 부족 종목이 있으면 전체 포트폴리오 손익으로
        # 오해되지 않게 명시. 평가 집계가 0 원으로 보이는 오해 차단.
        lines.append(
            "   - ⚠ 일부 종목 시세 미확인 또는 계산 정보 부족 — "
            "평가금액/손익/수익률은 평가 계산 가능 종목 기준입니다."
        )

    return lines


# ─── Step 2B 핵심 — 주목 종목 선별 ─────────────────────────────────────


def select_focus_items(
    recs: list[dict[str, Any]],
) -> list[tuple[str, dict[str, Any]]]:
    """주목 종목 선별. (category_label, item) 튜플 리스트 반환.

    우선순위 (지시문):
      1. price_missing — 가격 미확인 (최대 TOP_N_PRICE_MISSING)
      2. calc_missing  — 시세는 있는데 평가 계산 정보 부족 (최대 TOP_N_PRICE_MISSING)
      3. bottom_pnl_rate — 평가수익률 하위 (최대 TOP_N_BOTTOM_PNL_RATE)
      4. top_market_weight — 시장비중 상위 (최대 TOP_N_TOP_MARKET_WEIGHT)
      5. top_pnl_rate — 평가수익률 상위 (최대 TOP_N_TOP_PNL_RATE)

    중복 종목은 한 번만 (앞 카테고리 우선). 정렬 대상은 _to_finite_float 통과한 항목만.
    누락/None/NaN 은 정렬 대상에서 제외 — 0 으로 취급 금지.
    계산 정보 부족 종목은 손익률/시장비중 정렬 대상에서도 자연 제외 (해당 키가 없음).
    """
    valid_items = [it for it in recs if isinstance(it, dict)]
    selected: list[tuple[str, dict[str, Any]]] = []
    seen_tickers: set[str] = set()

    def _add(category: str, item: dict[str, Any]) -> None:
        ticker = item.get("ticker") or _item_label(item)
        if ticker in seen_tickers:
            return
        seen_tickers.add(str(ticker))
        selected.append((category, item))

    # 1. 가격 미확인
    price_missing = [it for it in valid_items if not _is_priced(it)]
    for it in price_missing[:TOP_N_PRICE_MISSING]:
        _add("price_missing", it)

    # 2. 계산 정보 부족 — 시세는 있는데 eval/invested 가 누락된 종목 (0 원 취급 차단)
    calc_missing = [
        it for it in valid_items if _is_priced(it) and not _is_calc_available(it)
    ]
    for it in calc_missing[:TOP_N_PRICE_MISSING]:
        _add("calc_missing", it)

    # 3. 평가수익률 하위 — 유효한 pnl_rate_pct 가진 종목만 정렬 대상
    pnl_rate_valid = [
        (it, _to_finite_float(it.get("pnl_rate_pct"))) for it in valid_items
    ]
    pnl_rate_sortable = [(it, n) for it, n in pnl_rate_valid if n is not None]

    bottom_sorted = sorted(pnl_rate_sortable, key=lambda x: x[1])
    for it, _ in bottom_sorted[:TOP_N_BOTTOM_PNL_RATE]:
        _add("bottom_pnl_rate", it)

    # 4. 시장비중 상위 — 유효한 market_weight_pct 가진 종목만
    market_weight_sortable = [
        (it, n)
        for it in valid_items
        for n in [_to_finite_float(it.get("market_weight_pct"))]
        if n is not None
    ]
    top_market_sorted = sorted(market_weight_sortable, key=lambda x: x[1], reverse=True)
    for it, _ in top_market_sorted[:TOP_N_TOP_MARKET_WEIGHT]:
        _add("top_market_weight", it)

    # 5. 평가수익률 상위
    top_pnl_sorted = sorted(pnl_rate_sortable, key=lambda x: x[1], reverse=True)
    for it, _ in top_pnl_sorted[:TOP_N_TOP_PNL_RATE]:
        _add("top_pnl_rate", it)

    return selected


def _render_focus_item(item: dict[str, Any]) -> str:
    """주목 종목 1건 → 사람이 읽는 줄 묶음.

    Step 2B 표시 정책: 최소 필드만 — 평가수익률 / 판단 / 사유 + 옵션(평가손익 / 시장비중).
    수량/평균매입단가/매입금액/매입비중/현재가/평가금액 은 기본 제외 (UI 에서 확인).
    """
    label = _item_label(item)
    lines: list[str] = [f"   • {label}"]

    pnl_rate = _format_signed_pct(item.get("pnl_rate_pct"))
    if pnl_rate is not None:
        lines.append(f"     - 평가수익률: {pnl_rate}")

    pnl_amount = _format_signed_money(item.get("pnl_amount"))
    if pnl_amount is not None:
        lines.append(f"     - 평가손익: {pnl_amount}")

    market_weight = _format_pct(item.get("market_weight_pct"))
    if market_weight is not None:
        lines.append(f"     - 시장비중: {market_weight}")

    if not _is_priced(item):
        lines.append("     - [시세 미확인]")
    elif not _is_calc_available(item):
        # 시세는 있는데 평가 계산 불가능 (eval/invested 누락) — 0 원으로 취급 금지.
        lines.append("     - [계산 정보 부족]")

    action = item.get("action")
    if isinstance(action, str) and action:
        lines.append(f"     - 판단: {action}")

    reason = item.get("reason")
    if isinstance(reason, str) and reason:
        lines.append(f"     - 사유: {reason}")

    return "\n".join(lines)


_CATEGORY_HEADERS = {
    "price_missing": "🔍 시세 미확인 종목",
    "calc_missing": "⚙ 계산 정보 부족 종목",
    "bottom_pnl_rate": "📉 평가수익률 하위",
    "top_market_weight": "📊 시장비중 상위",
    "top_pnl_rate": "📈 평가수익률 상위",
}


def _render_focus_section(
    focus: list[tuple[str, dict[str, Any]]],
) -> list[str]:
    """주목 종목 섹션. 카테고리별로 묶어 표시. 비어있으면 빈 리스트."""
    if not focus:
        return []

    by_category: dict[str, list[dict[str, Any]]] = {}
    order: list[str] = []
    for category, item in focus:
        if category not in by_category:
            by_category[category] = []
            order.append(category)
        by_category[category].append(item)

    lines: list[str] = ["", "주목 종목:"]
    for category in order:
        items = by_category[category]
        if not items:
            continue
        header = _CATEGORY_HEADERS.get(category, category)
        lines.append(f"  {header}")
        for it in items:
            lines.append(_render_focus_item(it))

    return lines


# ─── Step 2B 핵심 — 길이 제한 방어 ─────────────────────────────────────


def _enforce_length_limit(text: str) -> str:
    """안전 한도(MAX_LENGTH_CHARS) 이하로 보장. 초과 시 잘라내고 안내 문구 추가.

    호출자(build_message_text) 가 1차로 주목 종목 수를 줄여 본다. 그래도 초과하면
    여기서 잘라내되, 잘린 결과 자체도 한도 이하임을 보장한다.
    """
    if len(text) <= MAX_LENGTH_CHARS:
        return text

    # 잘림 안내 포함 후에도 한도 이하여야 함
    notice_with_break = "\n\n" + TRUNCATION_NOTICE
    keep_chars = MAX_LENGTH_CHARS - len(notice_with_break)
    if keep_chars < 0:
        keep_chars = 0
    return text[:keep_chars] + notice_with_break


def _factor_bullet(payload: dict[str, Any]) -> Optional[str]:
    """factor_signals 의 portfolio scope signal 1줄 → bullet 본문. 없으면 None."""
    factor_signals = payload.get("factor_signals")
    if not isinstance(factor_signals, list):
        return None
    portfolio_sig: Optional[dict[str, Any]] = None
    for sig in factor_signals:
        if isinstance(sig, dict) and sig.get("scope") == "portfolio":
            portfolio_sig = sig
            break
    if portfolio_sig is None:
        return None

    factor_name = portfolio_sig.get("factor_name") or "보유 비중 영향"
    if portfolio_sig.get("is_available"):
        text = portfolio_sig.get("reason_text")
    else:
        text = portfolio_sig.get("fallback_text")
    if not isinstance(text, str) or not text.strip():
        return None
    return f"- {factor_name}: {text}"


def _momentum_bullet(payload: dict[str, Any]) -> Optional[str]:
    """Step 5B — momentum_result.summary 1줄 → bullet 본문. 없으면 None.

    top_candidate 가 있으면 그 reason_text 를, 없으면 summary_reason_text 를 사용.
    별도 [모멘텀 점검] 헤더 신설 금지 — 본 함수는 bullet 본문만 반환한다.
    """
    momentum = payload.get("momentum_result")
    if not isinstance(momentum, dict):
        return None
    summary = momentum.get("summary")
    if not isinstance(summary, dict):
        return None

    top = summary.get("top_candidate")
    if isinstance(top, dict):
        text = top.get("reason_text")
    else:
        text = summary.get("summary_reason_text")
    if not isinstance(text, str) or not text.strip():
        return None
    return f"- {MOMENTUM_BULLET_LABEL}: {text}"


def _render_judgment_lines(payload: dict[str, Any]) -> list[str]:
    """[판단 사유] 섹션 — Step 3 의 factor bullet 과 Step 5B 의 momentum bullet 을
    한 헤더 아래에 모은다.

    헤더 중복 금지: bullet 이 1개라도 있으면 헤더 1번 + bullets. 둘 다 없으면 빈 리스트.
    종목별 / 후보별 항목은 메시지에 나열하지 않는다 (Top N 정책 금지).
    """
    bullets: list[str] = []
    fb = _factor_bullet(payload)
    if fb is not None:
        bullets.append(fb)
    mb = _momentum_bullet(payload)
    if mb is not None:
        bullets.append(mb)
    if not bullets:
        return []
    return ["", JUDGMENT_SECTION_HEADER, *bullets]


def _build_with_focus_limit(
    run_id: str,
    payload: dict[str, Any],
    summary: dict[str, Any],
    focus_full: list[tuple[str, dict[str, Any]]],
    focus_limit: Optional[int],
) -> str:
    """focus_limit 개수만큼만 주목 종목을 표시한 message_text 조립."""
    title = payload.get("title") or "보유 종목 기반 초안"
    note = payload.get("note") or ""

    header_lines = [
        "✅ POC2 holdings 승인 처리",
        f"run_id: {run_id}",
        f"title: {title}",
    ]
    if note:
        header_lines.append("")
        header_lines.append(note)

    judgment_lines = _render_judgment_lines(payload)
    summary_lines = _render_summary_lines(summary)

    if focus_limit is None:
        focus_subset = focus_full
    else:
        focus_subset = focus_full[:focus_limit]
    focus_lines = _render_focus_section(focus_subset)

    footer_lines = ["", "전체 보유 상세는 웹 화면에서 확인하세요."]

    return "\n".join(
        header_lines + judgment_lines + summary_lines + focus_lines + footer_lines
    )


def build_message_text(run_id: str, payload: dict[str, Any]) -> str:
    """holdings draft_payload → Telegram 본문 (Step 2B 요약형).

    호출자는 is_holdings_draft 로 사전 검증해야 한다. 그렇지 않으면 빈 문자열 반환.

    길이 방어 흐름:
    1. 전체 요약 + 주목 종목 전부(최대 4 카테고리 × N) 로 1차 조립
    2. MAX_LENGTH_CHARS 초과 시 주목 종목 수를 단계적으로 축소 (전체 → 절반 → 0)
    3. 그래도 초과면 _enforce_length_limit 에서 잘라내고 안내 문구 추가
    4. 메시지 split 사용 안 함 (이번 단계 정책)
    """
    if not is_holdings_draft(payload):
        return ""

    recs = payload.get("recommendations") or []
    summary = compute_summary(recs)
    focus_full = select_focus_items(recs)

    # 1차: 전체 주목 종목
    text = _build_with_focus_limit(run_id, payload, summary, focus_full, None)
    if len(text) <= MAX_LENGTH_CHARS:
        return text

    # 2차: 주목 종목 절반으로 축소
    if focus_full:
        half = max(1, len(focus_full) // 2)
        text = _build_with_focus_limit(run_id, payload, summary, focus_full, half)
        if len(text) <= MAX_LENGTH_CHARS:
            return text

    # 3차: 주목 종목 0건 (요약만)
    text = _build_with_focus_limit(run_id, payload, summary, [], 0)
    if len(text) <= MAX_LENGTH_CHARS:
        return text

    # 4차: 그래도 초과 — 잘라내고 안내
    return _enforce_length_limit(text)
