"""Decision Draft Preview v1 — 선택 ETF 임시 판단 근거 미리보기 서비스.

지시문 §3 / §4 원칙:
- 저장 없는 preview 전용 — 기존 PENDING draft 경로 (generate_draft, store.save_run)
  와 완전 분리.
- LLM / 외부 시세 호출 / 자동 재시도 / 승인·OCI·Telegram 연결 0건.
- 서버가 결정적으로 조립한 텍스트 (사용자가 복사해 외부 AI 웹에 입력하는 용도).

구성 (지시문 §7 / 설계자 Q3 확정):
1. 대상과 검토 맥락
2. 확인된 근거
3. 시장 참고
4. 주의·미확인 사항
5. AI에게 추가로 물어볼 질문 (사용자가 별도 AI 웹사이트에 붙여넣어 추가
   해석을 요청할 수 있는 형태)

부작용 없음. DB write / 파일 write / 외부 호출 0건.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from app.market_data_store import DEFAULT_DB_PATH
from app.market_risk_reference_service import build_market_risk_reference

TARGET_KIND_HOLDING = "holding"
TARGET_KIND_CANDIDATE = "candidate"
ALLOWED_TARGET_KINDS = (TARGET_KIND_HOLDING, TARGET_KIND_CANDIDATE)


@dataclass
class EvidenceAsOfPayload:
    target_as_of_date: Optional[str] = None
    kodex200_as_of_date: Optional[str] = None
    vix_as_of_date: Optional[str] = None


@dataclass
class PreviewResult:
    status: str  # ok / error
    target_kind: Optional[str] = None
    ticker: Optional[str] = None
    preview_text: Optional[str] = None
    evidence_as_of: Optional[EvidenceAsOfPayload] = None
    message: Optional[str] = None


def _fmt_pct(value: Optional[float]) -> str:
    if value is None:
        return "미확인"
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.2f}%"


def _fmt_num(value: Optional[float], digits: int = 2) -> str:
    if value is None:
        return "미확인"
    return f"{value:,.{digits}f}"


def _find_holding(
    holdings: list[dict[str, Any]], ticker: str
) -> Optional[dict[str, Any]]:
    for h in holdings:
        if str(h.get("ticker") or "") == ticker:
            return h
    return None


def _find_candidate(
    candidates: list[dict[str, Any]], ticker: str
) -> Optional[dict[str, Any]]:
    for c in candidates:
        if str(c.get("ticker") or "") == ticker:
            return c
    return None


def _section(title: str, lines: list[str]) -> str:
    body = "\n".join(f"- {ln}" for ln in lines) if lines else "- (기록 없음)"
    return f"[{title}]\n{body}"


def _build_holding_evidence_lines(
    holding: dict[str, Any],
) -> tuple[list[str], list[str], Optional[str]]:
    """(확인된 근거, 주의·미확인, target_as_of_date) 조립.

    holding 은 build_holdings_market_evidence 응답 items 중 한 건 (dict).
    """
    confirmed: list[str] = []
    warnings: list[str] = []
    target_asof: Optional[str] = None

    name = holding.get("name") or holding.get("ticker") or "보유 ETF"
    confirmed.append(f"대상: {name} ({holding.get('ticker') or '미확인'}) — 보유 ETF")
    weight = holding.get("market_weight_pct")
    pnl = holding.get("pnl_rate_pct")
    confirmed.append(f"평가비중: {_fmt_pct(weight)}")
    confirmed.append(f"손익률: {_fmt_pct(pnl)}")

    stm = holding.get("short_term_momentum") or {}
    ex_20 = stm.get("excess_vs_kodex200_20d_pctp")
    if ex_20 is not None:
        confirmed.append(f"KODEX200 대비 20거래일 초과: {_fmt_pct(ex_20)}")
    else:
        warnings.append("KODEX200 대비 20거래일 초과 수치는 확인되지 않았습니다.")
    stm_end = stm.get("end_date")
    if stm_end:
        target_asof = stm_end

    dq = holding.get("data_quality") or {}
    dq_status = dq.get("status")
    if dq_status == "warning":
        warnings.append("보유 ETF 데이터 품질 경고 — 확인 필요.")
    elif dq_status == "unavailable" or dq_status is None:
        warnings.append("보유 ETF 데이터 품질은 확인되지 않았습니다.")

    overlap = holding.get("overlap") or {}
    overlap_status = overlap.get("status")
    if overlap_status == "not_loaded" or overlap_status is None:
        warnings.append("직접 보유·구성종목 중복은 아직 확인되지 않았습니다.")
    elif overlap_status == "unavailable":
        warnings.append("구성종목 중복 확인이 불가능했습니다.")
    return confirmed, warnings, target_asof


def _build_candidate_evidence_lines(
    candidate: dict[str, Any],
) -> tuple[list[str], list[str], Optional[str]]:
    confirmed: list[str] = []
    warnings: list[str] = []
    target_asof: Optional[str] = None

    name = candidate.get("name") or candidate.get("ticker") or "후보 ETF"
    confirmed.append(f"대상: {name} ({candidate.get('ticker') or '미확인'}) — 후보 ETF")
    score = candidate.get("relative_upside_score")
    if score is not None:
        confirmed.append(f"상대상승 참고점수: {score:.1f}")
    else:
        warnings.append("상대상승 참고점수는 확인되지 않았습니다.")

    stm = candidate.get("short_term_momentum") or {}
    ex_20 = stm.get("excess_vs_kodex200_20d_pctp")
    if ex_20 is not None:
        confirmed.append(f"KODEX200 대비 20거래일 초과: {_fmt_pct(ex_20)}")
    else:
        warnings.append("KODEX200 대비 20거래일 초과 수치는 확인되지 않았습니다.")
    stm_end = stm.get("end_date")
    if stm_end:
        target_asof = stm_end

    dd = candidate.get("drawdown_20d")
    if dd is not None:
        confirmed.append(f"20거래일 고점 대비: {_fmt_pct(dd * 100)}")
    else:
        warnings.append("20거래일 고점 대비 수치는 확인되지 않았습니다.")

    dq = candidate.get("data_quality") or {}
    dq_status = dq.get("status")
    if dq_status == "warning":
        warnings.append("후보 ETF 데이터 품질 경고 — 확인 필요.")
    elif dq_status == "unavailable" or dq_status is None:
        warnings.append("후보 ETF 데이터 품질은 확인되지 않았습니다.")
    return confirmed, warnings, target_asof


def _build_market_reference_lines(
    db_path: Path,
) -> tuple[list[str], list[str], Optional[str], Optional[str]]:
    """(시장 참고 lines, 주의사항 lines, kodex_asof, vix_asof)."""
    evidence = build_market_risk_reference(db_path=db_path)
    lines: list[str] = []
    warnings: list[str] = []

    if evidence.kodex200.availability == "available":
        lines.append(
            f"KODEX200 기준일: {evidence.kodex200.as_of_date or '미확인'} — "
            f"전일 대비: {_fmt_pct(evidence.kodex200.change_1d_pct)}"
        )
    else:
        lines.append("KODEX200: 미확인")
        warnings.append("KODEX200 evidence 가 아직 확인되지 않았습니다.")

    if evidence.vix.availability == "available":
        lines.append(
            f"VIX 기준일: {evidence.vix.as_of_date or '미확인'} — "
            f"전일 대비: {_fmt_pct(evidence.vix.change_1d_pct)} / "
            f"5거래일 변화: {_fmt_pct(evidence.vix.change_5d_pct)}"
        )
    else:
        lines.append("VIX: 미확인")
        warnings.append("VIX evidence 가 아직 확인되지 않았습니다.")

    k_asof = evidence.kodex200.as_of_date
    v_asof = evidence.vix.as_of_date
    if k_asof and v_asof and k_asof != v_asof:
        lines.append(
            "국내·미국 시장의 마지막 확인 거래일은 다를 수 있습니다. "
            "각 시장의 실제 기준일을 표시합니다."
        )

    return lines, warnings, k_asof, v_asof


def _build_ai_followup_questions(target_kind: str) -> list[str]:
    """지시문 Q3 확정 — 사용자가 AI 웹사이트에 그대로 붙여넣을 수 있는 형태.

    자동 매수·매도·유지 지시 / 시장 예측 / 위험 등급 요청 문구는 만들지 않는다.
    """
    if target_kind == TARGET_KIND_HOLDING:
        return [
            "위 evidence 만 놓고 볼 때, 이 보유 ETF 의 현재 상황을 어떻게 요약할 수 있을까요?",
            "확인되지 않은 항목 (구성종목 중복 등) 이 판단에 얼마나 중요한 변수라고 보시나요?",
            "국내·미국 시장 기준일 차이가 이 evidence 해석에 어떤 영향을 줄 수 있나요?",
        ]
    return [
        "위 evidence 만 놓고 볼 때, 이 후보 ETF 의 현재 상황을 어떻게 요약할 수 있을까요?",
        "보유 ETF 와의 중복 상태가 확인되지 않은 점이 이 evidence 해석에 어떤 영향을 줄 수 있나요?",
        "고점 대비 / KODEX200 대비 수치를 함께 놓고 볼 때, 이 evidence 는 어떤 관점을 시사하나요?",
    ]


def build_preview_text(
    *,
    target_kind: str,
    ticker: str,
    target_evidence: dict[str, Any],
    db_path: Path = DEFAULT_DB_PATH,
) -> PreviewResult:
    """선택 ETF 하나에 대한 preview_text 를 결정적으로 조립.

    target_evidence 는 호출자가 미리 구성한 dict (보유 또는 후보 evidence 한 건).
    본 함수는 부작용 없이 텍스트만 생성.
    """
    if target_kind not in ALLOWED_TARGET_KINDS:
        return PreviewResult(
            status="error",
            message="판단 근거 미리보기를 생성하지 못했습니다. 다시 시도하세요.",
        )
    if not ticker:
        return PreviewResult(
            status="error",
            message="판단 근거 미리보기를 생성하지 못했습니다. 다시 시도하세요.",
        )

    if target_kind == TARGET_KIND_HOLDING:
        confirmed_lines, warning_lines, target_asof = _build_holding_evidence_lines(
            target_evidence
        )
        context_line = "보유 ETF 하나에 대해 유지·조정 판단 근거를 정리합니다."
    else:
        confirmed_lines, warning_lines, target_asof = _build_candidate_evidence_lines(
            target_evidence
        )
        context_line = "후보 ETF 하나에 대해 매수 검토 근거를 정리합니다."

    market_lines, market_warnings, k_asof, v_asof = _build_market_reference_lines(
        db_path=db_path
    )
    warning_lines.extend(market_warnings)
    questions = _build_ai_followup_questions(target_kind)

    sections = [
        _section(
            "1. 대상과 검토 맥락",
            [
                context_line,
                (
                    f"선택 ETF 기준일: {target_asof or '미확인'} / "
                    f"KODEX200 기준일: {k_asof or '미확인'} / "
                    f"VIX 기준일: {v_asof or '미확인'}"
                ),
            ],
        ),
        _section("2. 확인된 근거", confirmed_lines),
        _section("3. 시장 참고", market_lines),
        _section("4. 주의·미확인 사항", warning_lines),
        _section("5. AI에게 추가로 물어볼 질문", questions),
    ]
    preview_text = "\n\n".join(sections)

    return PreviewResult(
        status="ok",
        target_kind=target_kind,
        ticker=ticker,
        preview_text=preview_text,
        evidence_as_of=EvidenceAsOfPayload(
            target_as_of_date=target_asof,
            kodex200_as_of_date=k_asof,
            vix_as_of_date=v_asof,
        ),
    )
