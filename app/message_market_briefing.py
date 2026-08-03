"""POC2 3-PUSH Message Contract — PUSH-1 시장 흐름 브리핑 message_text 빌더 (2026-06-11).

지시문 §4.2 — 어제까지의 시장 흐름과 현재 시장 내부 신호 요약. 외부 source 호출
0건 (저장된 artifact / read-only 정규화 evidence 만 사용). 매수/매도 / 상승장
확정 / 조정장 확정 / 현금비중 조절 / 위험 알림 확정 문구 0건.

3-PUSH Runtime Package PC 검증 (2026-06-13) — 입력 흐름 정렬:
  pc_evidence + runtime_snapshot → push_context → 본 builder → message_text.
push_context 가 주입되면 본 builder 가 그 안의 market_view.observations 를
참고해 [밤사이 미국 시장] 1줄 섹션을 추가한다 (runtime probe 결과 반영).

3-PUSH Message Text Runtime Evidence 반영 (2026-06-14) — AC-1 / AC-2:
- push_context.market_view 의 overnight_us 관찰에서 실제 close / change_pct +
  섹터 해석 hint 를 노출.
- push_context.market_view 의 market_trend / risk_pattern 관찰 텍스트도 그대로
  message_text 에 1~2줄로 반영.
- 단순 "조회 가능 지수" 노출 금지.

입력 (모두 read-only, 저장된 artifact / 정규화 evidence):
- ML baseline evidence snapshot (위험 패턴 참고).
- Market Discovery TopN (시장 내부 신호 — 상위 / 하위 N개 ETF).

본 모듈은 "뉴스 수집 실패" / "뉴스 unavailable" 등 보여주기식 문구를 만들지
않는다 (§4.2). 뉴스 section 자체를 생략한다.

길이 정책: 기존 message_text 와 동일 — MAX_LENGTH_CHARS = 3500. 본 빌더는
~1800자 이하로 안정 (3-4 섹션, raw JSON 0건).
"""

from __future__ import annotations

from typing import Any, Iterable, Optional

from app.push_user_copy import (
    NEUTRAL_NOTES,
    PUSH_KIND_HEADERS,
    build_all_unavailable_message,
    render_unavailable_block,
)

MAX_LENGTH_CHARS = 3500
PUSH_KIND = "market_briefing"
TITLE = PUSH_KIND_HEADERS["market_briefing"]
NEUTRAL_NOTE = NEUTRAL_NOTES["market_briefing"]


def _fmt_pct(value: Any, *, signed: bool = True) -> Optional[str]:
    if not isinstance(value, (int, float)):
        return None
    pct = float(value) * 100.0 if abs(value) < 1.5 else float(value)
    if signed:
        sign = "+" if pct > 0 else ""
        return f"{sign}{pct:.2f}%"
    return f"{pct:.2f}%"


def _evidence_section(ml_baseline_snapshot: Optional[dict[str, Any]]) -> list[str]:
    """ML baseline 룩백 evidence 의 위험 패턴 1줄 요약. evidence 가 없거나 사용
    불가능하면 섹션 자체 생략 (보여주기식 'unavailable' 문구 금지).
    """
    if not isinstance(ml_baseline_snapshot, dict):
        return []
    status = ml_baseline_snapshot.get("status")
    if status in (None, "unavailable", "error"):
        return []
    risk = ml_baseline_snapshot.get("risk_summary")
    if not isinstance(risk, dict):
        return []
    high_dd = risk.get("high_risk_group_future_drawdown") or {}
    low_dd = risk.get("low_risk_group_future_drawdown") or {}
    high10 = _fmt_pct(high_dd.get("10d"))
    low10 = _fmt_pct(low_dd.get("10d"))
    eval_days = risk.get("evaluated_days")
    parts: list[str] = ["[위험 참고 데이터]"]
    if high10 and low10 and isinstance(eval_days, int):
        parts.append(
            f"  • 과거 {eval_days}거래일 기준 — 위험 높은 그룹의 이후 10일 하락 "
            f"{high10}, 위험 낮은 그룹 {low10}."
        )
    parts.append("  • 이 항목은 참고 데이터이며 현재 시장의 확정 판정이 아닙니다.")
    return parts


def _market_position_section(topn_payload: Optional[dict[str, Any]]) -> list[str]:
    """POC3-06 §7.2 — 시장 위치 요약 (KOSPI 관찰값 + 기존 국면 + 지속 거래일 수).

    Dashboard 와 동일한 market_context(같은 저장값 read 산출)를 표시한다. PUSH 가
    별도 계산하지 않는다(§6.1·AC-14). market_context 부재/미확정 시 섹션 생략.
    KOSPI(사용자 대표 지수)와 KODEX200 기준 국면을 섞지 않는다(§4.2).
    """
    if not isinstance(topn_payload, dict):
        return []
    mc = topn_payload.get("market_context")
    if not isinstance(mc, dict) or mc.get("status") == "unavailable":
        return []
    kospi = mc.get("kospi") if isinstance(mc.get("kospi"), dict) else {}
    streak = (
        mc.get("regime_streak") if isinstance(mc.get("regime_streak"), dict) else {}
    )

    lines: list[str] = ["[시장 위치]"]
    if kospi and kospi.get("status") == "ok":
        daily = _fmt_pct(kospi.get("daily_return_pct"))
        y1 = _fmt_pct(kospi.get("return_1y_pct"))
        gap = _fmt_pct(kospi.get("high_52w_gap_pct"))
        asof = kospi.get("as_of_date") or mc.get("asof") or "-"
        parts = []
        if daily:
            parts.append(f"일간 {daily}")
        if y1:
            parts.append(f"1년 {y1}")
        if gap:
            parts.append(f"최근 1년 고점 대비 {gap}")
        if parts:
            lines.append(f"  • KOSPI {' / '.join(parts)} (기준일 {asof})")
    # 기존 시장 국면 (KODEX200 기준) + 지속 거래일 수.
    regime_label = mc.get("regime_label")
    if isinstance(regime_label, str) and regime_label:
        streak_txt = ""
        sd = streak.get("streak_days")
        if isinstance(sd, int):
            streak_txt = f" · {sd}거래일째" + (
                " 이상" if streak.get("at_least") else ""
            )
        lines.append(f"  • 기존 시장 국면(KODEX200 기준): {regime_label}{streak_txt}")
    # 헤더만 있고 내용 없으면 생략.
    return lines if len(lines) > 1 else []


def _market_internal_section(topn_payload: Optional[dict[str, Any]]) -> list[str]:
    """Market Discovery TopN 의 상위 / 하위 ETF 흐름 요약. 외부 source 호출 X.

    topn_payload 가 비정상이면 섹션 생략. candidates / items 비어있어도 생략.
    compute_topn 응답은 candidates 키를 갖는다 — 호환을 위해 items 도 fallback.
    """
    if not isinstance(topn_payload, dict):
        return []
    items = topn_payload.get("candidates")
    if not isinstance(items, list) or len(items) == 0:
        items = topn_payload.get("items")
    if not isinstance(items, list) or len(items) == 0:
        return []
    basis = topn_payload.get("basis") or "1m"
    asof = topn_payload.get("asof") or "-"

    def _key(it: dict[str, Any]) -> Optional[float]:
        v = it.get("selected_return_pct") if isinstance(it, dict) else None
        if not isinstance(v, (int, float)):
            v = it.get("return_pct") if isinstance(it, dict) else None
        return v if isinstance(v, (int, float)) else None

    sortable = [(it, _key(it)) for it in items if isinstance(it, dict)]
    sortable = [(it, k) for it, k in sortable if k is not None]
    if not sortable:
        return []
    sortable.sort(key=lambda x: x[1], reverse=True)
    top3 = sortable[:3]
    bottom3 = sortable[-3:][::-1]  # 가장 낮은 것부터 표시.

    lines: list[str] = [
        "[ETF 후보 흐름]",
        f"  • 기준일: {asof} / 비교 기준: {basis}",
        "  • 상위 ETF 흐름:",
    ]
    for it, _ in top3:
        name = it.get("name") or it.get("ticker") or "-"
        v = it.get("selected_return_pct")
        if not isinstance(v, (int, float)):
            v = it.get("return_pct")
        pct = _fmt_pct(v)
        if pct:
            lines.append(f"    - {name} {pct}")
    lines.append("  • 하위 ETF 흐름:")
    for it, _ in bottom3:
        name = it.get("name") or it.get("ticker") or "-"
        v = it.get("selected_return_pct")
        if not isinstance(v, (int, float)):
            v = it.get("return_pct")
        pct = _fmt_pct(v)
        if pct:
            lines.append(f"    - {name} {pct}")
    return lines


def _external_context_section(
    ml_baseline_snapshot: Optional[dict[str, Any]],
) -> list[str]:
    """ML baseline evidence 의 external_context_checklist 가 있으면 그대로 노출.
    체크리스트는 사용자 / AI 가 추가로 확인할 외부 변수 목록 (지시문 §4.2 허용).
    """
    if not isinstance(ml_baseline_snapshot, dict):
        return []
    checklist = ml_baseline_snapshot.get("external_context_checklist")
    if not isinstance(checklist, Iterable):
        return []
    items = [s for s in checklist if isinstance(s, str) and s.strip()]
    if not items:
        return []
    lines = ["[별도 확인 필요 외부 변수]"]
    # 최대 7개로 제한 (길이 안전 + 정규화 checklist 크기와 일치).
    for s in items[:7]:
        lines.append(f"  • {s}")
    return lines


def build_market_briefing_message(
    *,
    asof_iso: str,
    ml_baseline_snapshot: Optional[dict[str, Any]] = None,
    topn_payload: Optional[dict[str, Any]] = None,
    push_context: Optional[dict[str, Any]] = None,
    unavailable_source_keys: Optional[list[str]] = None,
) -> str:
    """PUSH-1 시장 흐름 브리핑 message_text 생성.

    입력 흐름 (2026-06-13 정렬): pc_evidence + runtime_snapshot → push_context
    → 본 builder → message_text.

    3-PUSH Message Text Runtime Evidence 반영 (2026-06-14): push_context 가
    주입되면 그 안의 market_view.observations 가 우선이며 (AC-1 / AC-2):
      • overnight_us — 실제 close / change_pct + 섹터 해석 hint 노출.
      • market_trend — Market Discovery 후보 흐름 1줄 (push_context 우선,
        없으면 fallback 으로 기존 topn 섹션).
      • risk_pattern — ML baseline 룩백 1줄 (push_context 우선).

    구조:
      ✅ 시장 흐름 브리핑 (asof)
      [밤사이 미국 시장 (runtime probe)] — push_context 기반, 조회 성공 시
      [국내 시장 내부 신호 (Market Discovery)] — push_context.market_view 기반
      [시장 내부 신호] — topn_payload 기반 상세 (상위/하위 ETF 목록)
      [위험 패턴 참고 (ML baseline 룩백)] — push_context 기반 1줄
      [위험 패턴 참고] — ML baseline snapshot 기반 상세
      [추가 확인 필요 외부 변수]
      (중립 안내)

    뉴스 source 가 없으면 뉴스 섹션 자체 생략. "unavailable" 보여주기 X.
    """
    from app.push_context import (
        market_trend_lines,
        overnight_us_lines,
        risk_pattern_lines,
    )

    sections: list[list[str]] = [
        # POC3-06 §7.2 — 시장 위치 요약을 가장 먼저(§7.2 "먼저 길게 나오지 않게").
        _market_position_section(topn_payload),
        overnight_us_lines(push_context),
        market_trend_lines(push_context),
        _market_internal_section(topn_payload),
        risk_pattern_lines(push_context),
        _evidence_section(ml_baseline_snapshot),
        _external_context_section(ml_baseline_snapshot),
    ]
    body: list[str] = []
    for s in sections:
        if s:
            body.extend(s)
            body.append("")

    # 모든 섹션이 비어있으면 사용자 중심 unavailable 메시지 (지시문 §4.3).
    if not body:
        return build_all_unavailable_message(
            push_kind=PUSH_KIND,
            asof_iso=asof_iso,
            unavailable_source_keys=list(unavailable_source_keys or []),
        )

    # 일부 available — 별도 확인 필요 블록 추가 (지시문 §4.4).
    header = [TITLE, f"기준일/생성: {asof_iso}", ""]
    unavail_block = render_unavailable_block(list(unavailable_source_keys or []))
    if unavail_block:
        body.extend(unavail_block)
        body.append("")

    footer = [NEUTRAL_NOTE]
    text = "\n".join(header + body + footer).rstrip()
    if len(text) > MAX_LENGTH_CHARS:
        # 길이 초과는 외부 checklist 섹션부터 축소 (가장 적게 잃는 순서).
        text = (
            text[: MAX_LENGTH_CHARS - 60].rstrip()
            + "\n\n...(메시지 길이 제한으로 일부 생략)"
        )
    return text
