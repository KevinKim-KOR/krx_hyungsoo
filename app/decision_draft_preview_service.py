"""Decision Draft Preview — 선택 종목 하나의 판단 근거 미리보기 글(저장 없음).

2026-07-03 v1 · POC5-23(2026-10-18) 묶음 개편 — 설계
`docs/ai_design/POC5/POC5-23_SELECTED_ETF_DECISION_EVIDENCE_PREVIEW_DESIGN_V1.md` §3 · 판정
`..._PLAN_DECISION_2026-10-18.md`.

- 저장 없는 preview 전용 — PENDING draft 경로(generate_draft, store.save_run)와 분리.
- LLM / 외부 시세 호출 / 자동 재시도 / 승인·OCI·Telegram 연결 0건.
- 자료는 호출자가 화면 API 응답에서 꺼내 넘긴다(`app/decision_preview_sources.py`). 이 모듈은 그 값을
  묶음별 글로만 옮긴다 — 새 산식 · 점수 · 등급 · 결론 없음. 값이 없으면 줄을 빼거나 0 · 다른 값으로
  채우지 않고 그 묶음 안에 사유를 남긴다.

묶음 순서: [대상] [시장] [가격 흐름 · PC 저장 종가] [KODEX200 동일 기간 비교] [거래량] [가격 흔들림]
[중복 · 자료 상태] [AI에게 요청]. 숫자 표시 정밀도는 화면 규칙과 같다(%·%p 소수 둘째 · 거래량 저장값 그대로 ·
평균 · 배수 소수 둘째 · 하락 구간 판정값 소수 첫째).
"""

from __future__ import annotations

import logging

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from app.decision_preview_lines import (
    AI_REQUEST,
    BASIS_LABEL,
    candidate_flow_lines,
    candidate_overlap_lines,
    daily_check_line,
    fmt_pct,
    holding_flow_lines,
    holding_overlap_lines,
    one_line,
    market_lines,
    nav_line,
    same_period_lines,
    volatility_lines,
    volume_lines,
)
from app.market_data_store import DEFAULT_DB_PATH

logger = logging.getLogger(__name__)

TARGET_KIND_HOLDING = "holding"
TARGET_KIND_CANDIDATE = "candidate"
ALLOWED_TARGET_KINDS = (TARGET_KIND_HOLDING, TARGET_KIND_CANDIDATE)

_FAILURE = "판단 근거 미리보기를 생성하지 못했습니다. 다시 시도하세요."
_KST = timezone(timedelta(hours=9))


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
    generated_at: Optional[str] = None
    message: Optional[str] = None


# ─── 조립 ──────────────────────────────────────────────────────────────


def _section(title: str, lines: list[str]) -> str:
    body = "\n".join(f"- {ln}" for ln in lines) if lines else "- (기록 없음)"
    return f"[{title}]\n{body}"


def _holding_sections(
    ev: dict[str, Any], db_path: Path
) -> tuple[list[str], dict[str, Optional[str]]]:
    bundle = ev.get("bundle") or None
    item = (bundle or {}).get("item") or {}
    ref = (bundle or {}).get("reference_date")
    is_etf = (bundle or {}).get("is_etf")
    kind = "" if bundle is None else ("(ETF)" if is_etf else "(개별 종목)")
    target_asof = (item.get("price_dates") or {}).get("end_date")
    mp = (bundle or {}).get("market_position") or {}
    regime = (
        {
            "label": mp.get("regime_label"),
            "streak_days": mp.get("regime_streak_days"),
            "at_least": mp.get("regime_streak_at_least"),
            # 보유 근거 API 의 판정 날짜(`market_asof`)는 저장 가격 표 전체 최신일일 수 있다
            # (DEF-MARKET-CONTEXT-ASOF-MEANING · PC 시장 화면만 KODEX200 끝으로 정정됨). 국면은
            # KODEX200 이력으로 정하므로 같은 응답의 PC 비교 기준일(KODEX200 최신 저장일)을 적는다.
            "asof": ref,
        }
        if mp.get("available")
        else None
    )
    market, k_asof, v_asof = market_lines(regime, db_path)
    target = [
        f"{one_line(ev.get('name') or ev.get('ticker'))} ({ev.get('ticker')}) · 보유 종목{kind}",
        f"평가비중 {fmt_pct(ev.get('market_weight_pct'), plus_zero=True)} · "
        f"손익률 {fmt_pct(ev.get('pnl_rate_pct'), plus_zero=True)}",
    ]
    if bundle is None:
        no = ["값 없음 — 보유 근거 응답에 이 종목이 없습니다."]
        return (
            [target, market, no, no, no, no, no],
            {"target": None, "kodex200": k_asof, "vix": v_asof},
        )
    status_lines = (
        [
            *holding_overlap_lines(item, bundle.get("constituents_asof")),
            nav_line(item.get("nav_discount")),
        ]
        if is_etf
        else ["구성종목 겹침 · NAV 괴리율: 대상 아님(개별 종목)"]
    )
    return (
        [
            target,
            market,
            holding_flow_lines(item, ref),
            same_period_lines(item.get("same_period_kodex200"), True),
            volume_lines(item.get("stored_volume"), ref),
            volatility_lines(item.get("price_volatility"), ref),
            status_lines,
        ],
        {"target": target_asof, "kodex200": k_asof, "vix": v_asof},
    )


def _candidate_sections(
    ev: dict[str, Any], db_path: Path
) -> tuple[list[str], dict[str, Optional[str]]]:
    cand = ev.get("candidate") or {}
    ref = ev.get("reference_date")
    mc = ev.get("market_context") or {}
    rs = mc.get("regime_streak") or {}
    regime = (
        {
            "label": mc.get("regime_label"),  # PC 시장 응답 = KODEX200 끝 날짜(POC5-11)
            "streak_days": rs.get("streak_days"),
            "at_least": rs.get("at_least"),
            "asof": mc.get("asof"),
        }
        if mc.get("regime_code") not in (None, "unavailable")
        else None
    )
    market, k_asof, v_asof = market_lines(regime, db_path)
    stm = cand.get("short_term_momentum") or {}
    target_asof = stm.get("end_date") or ev.get("end_date")
    basis = BASIS_LABEL.get(ev.get("basis") or "", ev.get("basis") or "")
    rank = cand.get("rank")
    # 낮은 순(asc = 하위 N) 목록이면 순위가 '잘 오른 순'으로 읽히지 않게 적는다.
    order = " · 낮은 순" if ev.get("order") == "asc" else ""
    target = [
        f"{one_line(cand.get('name') or cand.get('ticker'))} ({cand.get('ticker')}) · 후보 ETF"
        + (f" · 현재 목록 {rank}위({basis} 기준{order})" if rank is not None else "")
    ]
    dq = cand.get("data_quality") or {}
    status_lines = candidate_overlap_lines(ev.get("direct_holding"), ev.get("overlap"))
    status_lines.append(nav_line(dq.get("nav_discount")))
    status_lines.append(daily_check_line(dq.get("daily_return_check")))
    return (
        [
            target,
            market,
            candidate_flow_lines(cand),
            same_period_lines(cand.get("same_period_kodex200"), False),
            volume_lines(ev.get("stored_volume"), ref),
            volatility_lines(ev.get("price_volatility"), ref),
            status_lines,
        ],
        {"target": target_asof, "kodex200": k_asof, "vix": v_asof},
    )


def _market_flow_section(db_path: Path, period: str) -> str:
    """POC6-01 — 시장 흐름(수급 · 환율 · 유가) 묶음 = 화면 · AI 복사문과 같은 서버 글(빈 줄 없음)."""
    try:
        from app.supply_fx_oil_context import build_market_flow_context

        return build_market_flow_context(db_path=db_path)["ai_text"][period]
    except Exception:  # noqa: BLE001 — 이 묶음만 실패로 적고 미리보기는 그대로
        logger.exception("market flow section failed")
        return "[시장 흐름 — 수급 · 환율 · 유가]\n- 시장 흐름 자료를 만들지 못했습니다"


def build_preview_text(
    *,
    target_kind: str,
    ticker: str,
    target_evidence: dict[str, Any],
    db_path: Path = DEFAULT_DB_PATH,
    generated_at: Optional[datetime] = None,
    flow_period: str = "6M",
) -> PreviewResult:
    """선택 종목 하나의 preview_text 를 결정적으로 조립(부작용 없음).

    target_evidence: 보유 = {ticker, name, market_weight_pct, pnl_rate_pct, bundle} ·
    후보 = `load_candidate_bundle` 결과(`app/decision_preview_sources.py`).
    """
    if target_kind not in ALLOWED_TARGET_KINDS or not ticker:
        return PreviewResult(status="error", message=_FAILURE)

    gen = (generated_at or datetime.now(_KST)).astimezone(_KST)
    if target_kind == TARGET_KIND_HOLDING:
        bodies, asof = _holding_sections(target_evidence, db_path)
    else:
        bodies, asof = _candidate_sections(target_evidence, db_path)
    bodies[0] = bodies[0] + [
        f"생성 {gen.strftime('%Y-%m-%d %H:%M')} · 가격 기준일 {asof['target'] or '확인 불가'}"
        "(이 종목 마지막 저장 종가) · 생성 시각에 다시 계산한 값이라 화면 목록과 날짜가 다를 수 있습니다."
    ]
    titles = [
        "대상",
        "시장",
        "가격 흐름 · PC 저장 종가",
        "KODEX200 동일 기간 비교",
        "거래량",
        "가격 흔들림",
        "중복 · 자료 상태",
    ]
    sections = [_section(t, b) for t, b in zip(titles, bodies)]
    # POC6-01 — '시장' 바로 다음에 시장 흐름(화면에서 고른 기간 · 서버 공통 글).
    sections.insert(2, _market_flow_section(db_path, flow_period))
    sections.append(_section("AI에게 요청", AI_REQUEST))
    return PreviewResult(
        status="ok",
        target_kind=target_kind,
        ticker=ticker,
        preview_text="\n\n".join(sections),
        evidence_as_of=EvidenceAsOfPayload(
            target_as_of_date=asof["target"],
            kodex200_as_of_date=asof["kodex200"],
            vix_as_of_date=asof["vix"],
        ),
        generated_at=gen.isoformat(timespec="seconds"),
    )
