"""POC2 3-PUSH Message Contract — PUSH-1 시장 흐름 브리핑 message_text 빌더 (2026-06-11).

지시문 §4.2 — 어제까지의 시장 흐름과 현재 시장 내부 신호 요약. 외부 source 호출
0건 (저장된 artifact / read-only 정규화 evidence 만 사용). 매수/매도 / 상승장
확정 / 조정장 확정 / 현금비중 조절 / 위험 알림 확정 문구 0건.

3-PUSH Runtime Package PC 검증 (2026-06-13) — 입력 흐름 정렬:
  pc_evidence + runtime_snapshot → push_context → 본 builder → message_text.
push_context 가 주입되면 본 builder 가 그 안의 market_view.observations 를
참고해 [밤사이 미국 시장] 1줄 섹션을 추가한다 (runtime probe 결과 반영).

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

MAX_LENGTH_CHARS = 3500
PUSH_KIND = "market_briefing"
TITLE = "📊 시장 흐름 브리핑"
NEUTRAL_NOTE = (
    "이 브리핑은 시장 내부 신호의 요약이며, 직접적인 매매 지시를 포함하지 "
    "않습니다. 외부 변수 (CNN Fear & Greed / 환율 / 원유 / 미국장 / 지정학) "
    "는 별도 확인 필요합니다."
)


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
    parts: list[str] = ["[위험 패턴 참고]"]
    if high10 and low10 and isinstance(eval_days, int):
        parts.append(
            f"  • 과거 {eval_days}거래일 룩백 — high-risk bucket 의 이후 10d "
            f"drawdown {high10} vs low-risk {low10}."
        )
    parts.append("  • 본 항목은 baseline 참고이며 현재 시장의 확정 판정이 아닙니다.")
    return parts


def _market_internal_section(topn_payload: Optional[dict[str, Any]]) -> list[str]:
    """Market Discovery TopN 의 상위 / 하위 ETF 흐름 요약. 외부 source 호출 X.

    topn_payload 가 비정상이면 섹션 생략. items 가 비어있어도 생략.
    """
    if not isinstance(topn_payload, dict):
        return []
    items = topn_payload.get("items")
    if not isinstance(items, list) or len(items) == 0:
        return []
    basis = topn_payload.get("basis") or "1m"
    asof = topn_payload.get("asof") or "-"

    def _key(it: dict[str, Any]) -> Optional[float]:
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
        "[시장 내부 신호]",
        f"  • 기준일: {asof} / 비교 기준: {basis}",
        "  • 상위 ETF 흐름:",
    ]
    for it, _ in top3:
        name = it.get("name") or it.get("ticker") or "-"
        pct = _fmt_pct(it.get("return_pct"))
        if pct:
            lines.append(f"    - {name} {pct}")
    lines.append("  • 하위 ETF 흐름:")
    for it, _ in bottom3:
        name = it.get("name") or it.get("ticker") or "-"
        pct = _fmt_pct(it.get("return_pct"))
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
    lines = ["[추가 확인 필요 외부 변수]"]
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
) -> str:
    """PUSH-1 시장 흐름 브리핑 message_text 생성.

    입력 흐름 (2026-06-13 정렬): pc_evidence + runtime_snapshot → push_context
    → 본 builder → message_text. push_context 가 주입되면 그 안의 market_view
    .observations (overnight_us) 를 참고해 [밤사이 미국 시장] 1줄 섹션 추가.

    구조:
      ✅ 시장 흐름 브리핑 (asof)
      [밤사이 미국 시장 (runtime probe)] — push_context 기반, 조회 성공 시
      [시장 내부 신호]
        • 상위 / 하위 ETF (TopN read-only)
      [위험 패턴 참고]
        • ML baseline 룩백 high vs low drawdown (사용 가능 시)
      [추가 확인 필요 외부 변수]
        • CNN Fear & Greed / VIX / 환율 등 checklist
      (중립 안내)

    뉴스 source 가 없으면 뉴스 섹션 자체 생략. "unavailable" 보여주기 X.
    """
    from app.push_context import overnight_us_lines

    header = [TITLE, f"기준일/생성: {asof_iso}", ""]

    sections: list[list[str]] = [
        overnight_us_lines(push_context),
        _market_internal_section(topn_payload),
        _evidence_section(ml_baseline_snapshot),
        _external_context_section(ml_baseline_snapshot),
    ]
    body: list[str] = []
    for s in sections:
        if s:
            body.extend(s)
            body.append("")

    if not body:
        body = [
            "[전일 기준 시장 흐름]",
            "  • 현재 사용 가능한 시장 내부 신호 / 위험 패턴 evidence 가 없습니다.",
            "",
        ]

    footer = [NEUTRAL_NOTE]
    text = "\n".join(header + body + footer).rstrip()
    if len(text) > MAX_LENGTH_CHARS:
        # 길이 초과는 외부 checklist 섹션부터 축소 (가장 적게 잃는 순서).
        text = (
            text[: MAX_LENGTH_CHARS - 60].rstrip()
            + "\n\n...(메시지 길이 제한으로 일부 생략)"
        )
    return text
