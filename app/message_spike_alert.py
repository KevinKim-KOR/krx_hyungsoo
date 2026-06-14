"""POC2 3-PUSH Message Contract — PUSH-3 급등락 관찰 신호 message_text 빌더 (2026-06-11).

지시문 §4.4 — 현재 수집 대상 universe 에서 급등락이 큰 항목을 관찰 신호로 알림.
**개별 주식 전체 source 도입 금지** (이번 작업 범위 밖). ETF / market universe
기준만 사용. 외부 source 호출 0건.

입력 (모두 read-only, 저장된 artifact / API 결과):
- Market Discovery TopN (compute_topn) — 상위·하위 ETF 수익률.
- universe_momentum_latest.json 의 falling_candidate (기존 PUSH 3 bullet 재사용).
- data_quality flag (Market Discovery Evidence Closeout 1차 결과).

허용 문구 (§4.4): "급등락 관찰 신호", "변동성 확대", "data_quality 확인 필요".
금지 문구: "급등했으니 매수", "급락했으니 매도", "단기 대응 필요", "위험 알림 확정".

길이 정책: MAX_LENGTH_CHARS = 3500. 본 빌더는 ~1500자 이하 안정.
"""

from __future__ import annotations

from typing import Any, Optional

MAX_LENGTH_CHARS = 3500
PUSH_KIND = "spike_or_falling_alert"
TITLE = "⚡ 급등락 관찰 신호"
NEUTRAL_NOTE = (
    "이 신호는 universe 내부 관찰이며, 직접적인 매매 지시나 확정된 위험 신호를 "
    "포함하지 않습니다. 단기 대응 여부는 사용자가 별도로 판단해야 합니다."
)

# 표시 대상으로 선별할 절대 수익률 하한 (% 단위) — 화면/메시지에 무엇을 보여줄지
# 결정하는 표시 제한이며 매매 / 위험 판단 기준이 아니다 (지시문 §12 "위험
# threshold 확정 금지" 와 의미 분리). 설계자 수용 (FIX r2): 변수명에 "threshold"
# 단어를 쓰지 않는다. 본 값은 추후 사용자 설정 가능 옵션으로 외부화 가능.
SPIKE_DISPLAY_RETURN_PCT_MIN = 5.0


def _fmt_pct(value: Any, *, signed: bool = True) -> Optional[str]:
    if not isinstance(value, (int, float)):
        return None
    pct = float(value) * 100.0 if abs(value) < 1.5 else float(value)
    if signed:
        sign = "+" if pct > 0 else ""
        return f"{sign}{pct:.2f}%"
    return f"{pct:.2f}%"


def _topn_spike_section(topn_payload: Optional[dict[str, Any]]) -> list[str]:
    """compute_topn 결과의 상위 / 하위 ETF 중 표시 하한 이상 변동만 표시.

    개별 주식 universe 가 아니라 **기존 ETF universe** (compute_topn 의 items)
    만 사용. 새 source 추가 0건 (§4.4). 표시 하한은 보여줄 항목을 선별하는
    화면 기준이며 매매 / 위험 판단 기준이 아니다.
    """
    if not isinstance(topn_payload, dict):
        return []
    items = topn_payload.get("items")
    if not isinstance(items, list) or len(items) == 0:
        return []

    def _pct(it: dict[str, Any]) -> Optional[float]:
        v = it.get("return_pct") if isinstance(it, dict) else None
        if not isinstance(v, (int, float)):
            return None
        # compute_topn 결과는 % 단위로 들어옴 (e.g. 15.3 = +15.3%). 일관성 위해
        # 절대값이 1.5 미만이면 ratio 로 간주하고 ×100.
        return float(v) * 100.0 if abs(v) < 1.5 else float(v)

    enriched: list[tuple[dict[str, Any], float]] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        p = _pct(it)
        if p is None:
            continue
        enriched.append((it, p))
    if not enriched:
        return []

    enriched.sort(key=lambda x: x[1], reverse=True)
    rises = [pair for pair in enriched if pair[1] >= SPIKE_DISPLAY_RETURN_PCT_MIN][:5]
    falls = [pair for pair in enriched if pair[1] <= -SPIKE_DISPLAY_RETURN_PCT_MIN][
        -5:
    ][::-1]

    if not rises and not falls:
        return []

    basis = topn_payload.get("basis") or "1m"
    asof = topn_payload.get("asof") or "-"
    lines: list[str] = [
        "[ETF universe 변동성 확대 관찰]",
        f"  • 기준일: {asof} / 기준: {basis} / 표시 하한: 절대 수익률 ±{SPIKE_DISPLAY_RETURN_PCT_MIN:.1f}% 이상만",
    ]
    if rises:
        lines.append("  • 상승 관찰:")
        for it, pct in rises:
            name = it.get("name") or it.get("ticker") or "-"
            sign = "+" if pct > 0 else ""
            lines.append(f"    - {name} {sign}{pct:.2f}%")
    if falls:
        lines.append("  • 하락 관찰:")
        for it, pct in falls:
            name = it.get("name") or it.get("ticker") or "-"
            lines.append(f"    - {name} {pct:+.2f}%")
    return lines


def _falling_candidate_section(
    universe_artifact: Optional[dict[str, Any]],
) -> list[str]:
    """universe_momentum_latest.json 의 falling_candidate — 기존 PUSH 3 신호
    재사용. 후보가 없으면 섹션 생략.
    """
    if not isinstance(universe_artifact, dict):
        return []
    summary = universe_artifact.get("summary")
    if not isinstance(summary, dict):
        return []
    falling = summary.get("falling_candidate")
    if not isinstance(falling, dict):
        return []
    threshold_pct = summary.get("falling_threshold_pct")
    score_result = falling.get("score_result") or {}
    score_value = score_result.get("score_value")
    if not isinstance(score_value, (int, float)) or not isinstance(
        threshold_pct, (int, float)
    ):
        return []
    name = falling.get("name") or falling.get("ticker") or "-"
    phb = falling.get("price_history_basis") or {}
    basis_date = (
        (phb.get("latest_date") if isinstance(phb, dict) else None)
        or universe_artifact.get("asof")
        or "-"
    )

    return [
        "[기존 급락 ETF 주의 신호 (PUSH 3 재사용)]",
        f"  • {name} 1개월 수익률 {score_value:+.2f}% — 초기 급락 기준"
        f" {threshold_pct:+.2f}% 이하 (기준일 {basis_date}).",
        "  • 이 값은 매수/매도 지시가 아닙니다.",
    ]


def _data_quality_section(topn_payload: Optional[dict[str, Any]]) -> list[str]:
    """compute_topn 응답에 들어있는 data_quality flag — 변동성 확대가 데이터
    품질 이슈일 가능성을 사용자에게 알리는 보조 안내.
    """
    if not isinstance(topn_payload, dict):
        return []
    items = topn_payload.get("items") or []
    flagged: list[tuple[str, str]] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        flag = it.get("data_quality_flag")
        if not isinstance(flag, str) or not flag.strip():
            continue
        name = it.get("name") or it.get("ticker") or "-"
        flagged.append((name, flag))
    if not flagged:
        return []
    lines = ["[data_quality 확인 필요]"]
    for name, flag in flagged[:5]:
        lines.append(f"  • {name} — {flag}")
    return lines


def _spike_view_section(push_context: Optional[dict[str, Any]]) -> list[str]:
    """3-PUSH Runtime Package PC 검증 (2026-06-13) — push_context.spike_view
    의 items 가 있으면 1줄 요약 추가. universe_artifact 가 직접 falling/top
    candidate 를 만들지 않은 흐름에서도 push_context 만으로 관찰 1줄 노출."""
    if not isinstance(push_context, dict):
        return []
    sv = push_context.get("spike_view")
    if not isinstance(sv, dict):
        return []
    items = sv.get("items") or []
    if not items:
        return []
    lines = ["[universe momentum 관찰 (push_context 기반)]"]
    for it in items[:4]:
        if not isinstance(it, dict):
            continue
        name = it.get("name") or it.get("ticker") or "-"
        sv_val = it.get("score_value")
        direction = it.get("direction") or "-"
        if isinstance(sv_val, (int, float)):
            lines.append(f"  • {name} ({direction}) score={float(sv_val):+.2f}")
    return lines if len(lines) > 1 else []


def build_spike_alert_message(
    *,
    asof_iso: str,
    topn_payload: Optional[dict[str, Any]] = None,
    universe_artifact: Optional[dict[str, Any]] = None,
    push_context: Optional[dict[str, Any]] = None,
) -> str:
    """PUSH-3 급등락 관찰 신호 message_text 생성.

    구조:
      ⚡ 급등락 관찰 신호 (asof)
      [ETF universe 변동성 확대 관찰] — 표시 하한 이상 변동 항목만
      [기존 급락 ETF 주의 신호 (PUSH 3 재사용)]
      [data_quality 확인 필요]
      (중립 안내)

    개별 주식 전체 source 도입 0건. ETF / market universe 기준만.
    """
    header = [TITLE, f"기준일/생성: {asof_iso}", ""]

    body: list[str] = []
    for section in (
        _spike_view_section(push_context),
        _topn_spike_section(topn_payload),
        _falling_candidate_section(universe_artifact),
        _data_quality_section(topn_payload),
    ):
        if section:
            body.extend(section)
            body.append("")

    if not body:
        body = [
            "[ETF universe 변동성 확대 관찰]",
            "  • 현재 표시 하한 이상의 급등락 항목이 universe 내 관찰되지 않습니다.",
            "",
        ]

    footer = [NEUTRAL_NOTE]
    text = "\n".join(header + body + footer).rstrip()
    if len(text) > MAX_LENGTH_CHARS:
        text = (
            text[: MAX_LENGTH_CHARS - 60].rstrip()
            + "\n\n...(메시지 길이 제한으로 일부 생략)"
        )
    return text
