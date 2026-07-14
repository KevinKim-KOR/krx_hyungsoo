"""Runtime Evidence Composer — OCI PARAM Runtime + Diagnosis 공통 evidence 조립.

지시문 §3 · §4:
- 기존 저장소를 read-only 로 조회해 아래 세 결과를 생성한다.
  - available_sources : dict[str, str]  (build_runtime_message 계약 유지, "available"만 available)
  - extra_notes       : list[str]      (사용자 표시 문장, 실제 수치·as-of 포함)
  - diagnostics       : dict[str, object] (내부 진단 · Telegram 본문 비노출)

역할 밖:
- 외부 API 호출 · DB/artifact write · 신규 selection 로직 · 신규 threshold.
- Telegram · scheduler · PARAM 정책.

DI (지시문 Q10):
- market_db_path / holdings_file / holdings_loader / topn_fn / nav_fn / evidence_fn 을
  파라미터로 override 가능 → test 는 tmp path/fixture 사용 가능.
"""

from __future__ import annotations

import json
import re as _re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from app.holdings import (
    HOLDINGS_FILE,
    Holding,
    HoldingsValidationError,
    load as _holdings_load,
)
from app.holdings_market_evidence import (
    build_holdings_market_evidence as _build_holdings_market_evidence,
    get_holdings_file_mtime_iso,
)
from app.market_data_store import DEFAULT_DB_PATH as _MARKET_DB_DEFAULT
from app.market_topn import compute_topn as _compute_topn
from app.etf_nav_store import fetch_latest_nav as _fetch_latest_nav

# ── source key 상수 (PUSH_KIND_DATA_SOURCES 와 동일 · §12 계약 유지) ──────────


SRC_MARKET_DISCOVERY = "market_discovery_snapshot"
SRC_HOLDINGS = "holdings_snapshot"
SRC_NAV_DISCOUNT = "nav_discount_snapshot"
SRC_KR_REALTIME = "kr_realtime_price_snapshot"
SRC_OVERNIGHT_US = "overnight_us_market_snapshot"
SRC_ML_BASELINE = "ml_baseline_v0"
SRC_NEWS = "news_snapshot"
SRC_UNIVERSE_MOMENTUM = "universe_momentum_snapshot"


# reason code — Telegram 본문 노출 금지 (diagnostics 전용).
REASON_EXTERNAL_FETCH_REQUIRED = "unavailable_external_fetch_required"
REASON_NOT_IMPLEMENTED = "unavailable_not_implemented"
REASON_SOURCE_MISSING_HOLDINGS = "holdings_source_missing"
REASON_MARKET_DB_MISSING = "market_db_missing_or_empty"
REASON_NO_CONTENTFUL_FACT = "no_contentful_fact"
REASON_NAV_UNAVAILABLE = "nav_row_unavailable"


# ── 반환 dataclass ────────────────────────────────────────────────────────────


@dataclass
class RuntimeEvidenceResult:
    """Composer 반환 계약 (지시문 §4.2)."""

    available_sources: dict[str, str] = field(default_factory=dict)
    extra_notes: list[str] = field(default_factory=list)
    diagnostics: dict[str, Any] = field(default_factory=dict)


# ── 유틸 ─────────────────────────────────────────────────────────────────────


def _fmt_pct(value: Optional[float]) -> Optional[str]:
    if value is None:
        return None
    return f"{float(value):+.2f}%"


def _fmt_pct_unsigned(value: Optional[float]) -> Optional[str]:
    if value is None:
        return None
    return f"{float(value):.2f}%"


# ── privacy 검사 (FIX r5, 검증자 REJECTED r5 대응) ─────────────────────────────


_RAW_IDENT_TOKENS = (
    "unavailable_external_fetch_required",
    "unavailable_not_implemented",
    "holdings_source_missing",
    "market_db_missing_or_empty",
    "no_contentful_fact",
    "nav_row_unavailable",
    "topn_query_failed",
    "holdings_market_asof_missing",
    "market_briefing",
    "holdings_briefing",
    "spike_or_falling_alert",
    "market_discovery_snapshot",
    "holdings_snapshot",
    "nav_discount_snapshot",
    "kr_realtime_price_snapshot",
    "overnight_us_market_snapshot",
    "ml_baseline_v0",
    "news_snapshot",
    "universe_momentum_snapshot",
)


_PRIVACY_CONTEXT_TOKENS = (
    "수량",
    "평단",
    "평균가",
    "매입가",
    "보유수량",
    "보유주",
    "원금",
    "투자원금",
    "quantity",
    "avg_buy_price",
    "avg_price",
    "invested_amount",
    "invested",
    "account_group",
    "shares",
)


def _has_numeric_word(text: str, value: str) -> bool:
    """숫자 value 가 개인정보 문맥에 노출됐는지 검사.

    실제 운영 evidence 는 20/10/50 같은 소수 정수를 "20거래일", "TOP10",
    "STAR50" 등 정상 문맥에서 사용한다. 개인정보 노출 판정은 다음을 요구:
    1. value 가 non-digit 경계로 감싸진 단어여야 한다 (date/percent 오탐 회피).
    2. value 매칭 위치의 좌·우 32자 내에 _PRIVACY_CONTEXT_TOKENS 하나가 있어야
       실제 leak 로 인정 (예: "보유수량 10주", "avg_buy_price=35000").
    이 조합은 "TOP10" 같은 정상 문맥은 통과하고, 실제 개인정보 필드가
    template 에 우회 노출되는 시나리오는 차단한다.
    """
    if not value or not value.isdigit():
        return False
    pattern = _re.compile(r"(?<!\d)" + _re.escape(value) + r"(?!\d)")
    for m in pattern.finditer(text):
        start = max(0, m.start() - 32)
        window = text[start : m.end() + 32]  # noqa: E203
        if any(tok in window for tok in _PRIVACY_CONTEXT_TOKENS):
            return True
    return False


def _has_string_word(text: str, value: str) -> bool:
    """비숫자 문자열 값 (account_group 등) 검사 — 단순 substring."""
    return bool(value) and value in text


def _detect_private_values_exposed(
    holdings_list: list[Holding], notes: list[str]
) -> bool:
    """실제 개인정보 값이 composed notes 에 노출됐는지 boolean.

    FIX r6 (검증자 REJECTED r6 대응):
    - quantity=10 등 2자 값도 감지 (numeric word boundary 로 date/percent 오탐 회피).
    - 검사 대상: quantity · avg_buy_price · invested_amount (avg × qty) ·
      account_group.
    """
    if not notes:
        return False
    text = "\n".join(notes)
    for h in holdings_list:
        qty = getattr(h, "quantity", None)
        avg = getattr(h, "avg_buy_price", None)
        acct = getattr(h, "account_group", None)

        numeric_candidates: set[str] = set()
        if qty is not None:
            try:
                numeric_candidates.add(str(int(qty)))
            except (TypeError, ValueError):
                pass
        if avg is not None:
            try:
                numeric_candidates.add(str(int(avg)))
            except (TypeError, ValueError):
                pass
            if qty is not None:
                try:
                    numeric_candidates.add(str(int(float(avg) * float(qty))))
                except (TypeError, ValueError):
                    pass
        for c in numeric_candidates:
            if len(c) >= 2 and _has_numeric_word(text, c):
                return True
        if acct and isinstance(acct, str) and acct != "일반":
            if _has_string_word(text, acct):
                return True
    return False


def _detect_raw_identifier_exposed(notes: list[str]) -> bool:
    """내부 reason code · raw source key · raw push_kind 가 노출됐는지 boolean."""
    if not notes:
        return False
    text = "\n".join(notes)
    return any(tok in text for tok in _RAW_IDENT_TOKENS)


# ── market_discovery_snapshot (§5.1 필수 연결) ───────────────────────────────


def _compose_market_discovery(
    topn_fn: Callable[..., dict],
    market_db_path: Path,
) -> tuple[str, list[str], dict[str, Any]]:
    """returns (status, extra_notes lines, diag dict).

    available 조건 (지시문 §5.1):
      - reader 실행 성공 (status == "ok").
      - 실제 asof 존재.
      - 실제 benchmark 또는 후보 수치 존재.
      - 사용자용 evidence 문장 최소 1개 생성 가능.
    """
    payload = topn_fn(db_path=market_db_path)
    status = payload.get("status")
    asof = payload.get("asof")
    diag: dict[str, Any] = {
        "status": None,
        "asof": asof,
        "reader_status": status,
        "candidates_count": 0,
        "contentful_fact_count": 0,
    }
    if status != "ok" or not asof:
        diag["status"] = "unavailable"
        diag["reason"] = REASON_MARKET_DB_MISSING
        return "unavailable", [], diag

    notes: list[str] = []
    fact_count = 0
    market_context = payload.get("market_context") or {}

    # KODEX200 벤치마크.
    kodex = market_context.get("kodex200") or {}
    if kodex.get("status") == "ok":
        pct1m = _fmt_pct(kodex.get("return_1m_pct"))
        pct3m = _fmt_pct(kodex.get("return_3m_pct"))
        if pct1m or pct3m:
            parts = []
            if pct1m:
                parts.append(f"1개월 {pct1m}")
            if pct3m:
                parts.append(f"3개월 {pct3m}")
            notes.append(
                f"KODEX200 최근 수익률 ({asof} 기준): " + " / ".join(parts) + "."
            )
            fact_count += 1

    # KOSPI 벤치마크.
    kospi = market_context.get("kospi") or {}
    if kospi.get("status") == "ok":
        pct1m = _fmt_pct(kospi.get("return_1m_pct"))
        pct3m = _fmt_pct(kospi.get("return_3m_pct"))
        if pct1m or pct3m:
            parts = []
            if pct1m:
                parts.append(f"1개월 {pct1m}")
            if pct3m:
                parts.append(f"3개월 {pct3m}")
            notes.append(f"KOSPI 최근 수익률 ({asof} 기준): " + " / ".join(parts) + ".")
            fact_count += 1

    # Market Discovery TOP 후보 — 실제 as-of 가 있을 때만 preview fact 로 인정.
    candidates = payload.get("candidates") or []
    diag["candidates_count"] = len(candidates)
    if candidates:
        top_preview = candidates[: min(3, len(candidates))]
        preview_pairs: list[str] = []
        for c in top_preview:
            name = c.get("name") or c.get("ticker")
            ret_pct = _fmt_pct(c.get("selected_return_pct"))
            if name and ret_pct:
                preview_pairs.append(f"{name} {ret_pct}")
        if preview_pairs:
            notes.append(
                f"Market Discovery 후보 {len(candidates)}종 상위 ({asof} 기준): "
                + ", ".join(preview_pairs)
                + "."
            )
            fact_count += 1

    if fact_count == 0:
        diag["status"] = "unavailable"
        diag["reason"] = REASON_NO_CONTENTFUL_FACT
        return "unavailable", [], diag

    diag["status"] = "available"
    diag["contentful_fact_count"] = fact_count
    return "available", notes, diag


# ── holdings_snapshot + nav_discount_snapshot (§5.2 · §5.3 조건부) ──────────


def _compose_holdings_and_nav(
    holdings_loader: Callable[[], list[Holding]],
    holdings_file: Path,
    topn_fn: Callable[..., dict],
    market_db_path: Path,
    evidence_fn: Callable[..., dict[str, Any]],
    nav_fn: Callable[..., Any],
) -> tuple[
    tuple[str, list[str], dict[str, Any]],
    tuple[str, list[str], dict[str, Any]],
]:
    """returns ((holdings_status, holdings_notes, holdings_diag),
    (nav_status, nav_notes, nav_diag))."""
    holdings_diag: dict[str, Any] = {
        "status": None,
        "source_present": False,
    }
    nav_diag: dict[str, Any] = {"status": None, "asof": None, "matched_count": 0}

    # FIX r6 (검증자 REJECTED r6 대응): 조기 반환 경로에서도 privacy 진단 필드를
    # 명시적 boolean False 로 채워야 한다 (top-level default 정수 0 로 잘못 대체됨).
    def _set_privacy_defaults(diag: dict[str, Any]) -> None:
        diag["private_fields_exposed"] = False
        diag["raw_identifier_exposed"] = False
        diag.setdefault("holdings_loaded_count", 0)
        diag.setdefault("holdings_evidence_item_count", 0)
        diag.setdefault("holdings_contentful_fact_count", 0)
        diag.setdefault("holdings_selection_result_count", 0)
        diag.setdefault("rendered_holdings_fact_count", 0)

    if not holdings_file.exists():
        holdings_diag["status"] = "unavailable"
        holdings_diag["reason"] = REASON_SOURCE_MISSING_HOLDINGS
        nav_diag["status"] = "unavailable"
        nav_diag["reason"] = REASON_SOURCE_MISSING_HOLDINGS
        _set_privacy_defaults(holdings_diag)
        return ("unavailable", [], holdings_diag), ("unavailable", [], nav_diag)

    holdings_diag["source_present"] = True
    # B-1 정정 r2: 데이터 파일 자체 문제 (JSON 손상 · Holdings validation 실패) 만
    # unavailable 로 격리. `ValueError` 는 프로그래머 오류 (예: dict.get with wrong
    # signature) 로도 발생 가능하므로 catch 하지 않는다. Holdings JSON 파싱은
    # `json.JSONDecodeError` (JSONDecodeError 는 ValueError 상속) 로 잡히지만
    # 우리는 명시적으로 JSONDecodeError 만 캐치하여 다른 ValueError 는 propagate.
    try:
        holdings = holdings_loader()
    except (HoldingsValidationError, json.JSONDecodeError) as e:
        holdings_diag["status"] = "unavailable"
        holdings_diag["reason"] = f"holdings_load_error:{type(e).__name__}"
        nav_diag["status"] = "unavailable"
        nav_diag["reason"] = "holdings_load_error"
        _set_privacy_defaults(holdings_diag)
        return ("unavailable", [], holdings_diag), ("unavailable", [], nav_diag)

    holdings_diag["holdings_count"] = len(holdings)
    if not holdings:
        holdings_diag["status"] = "unavailable"
        holdings_diag["reason"] = "holdings_empty"
        nav_diag["status"] = "unavailable"
        nav_diag["reason"] = "holdings_empty"
        _set_privacy_defaults(holdings_diag)
        return ("unavailable", [], holdings_diag), ("unavailable", [], nav_diag)

    topn_payload = topn_fn(db_path=market_db_path)
    holdings_asof = get_holdings_file_mtime_iso(holdings_file)
    evidence_payload = evidence_fn(
        holdings=holdings,
        topn_payload=topn_payload,
        market_quotes=None,
        db_path=market_db_path,
        holdings_asof=holdings_asof,
    )
    market_asof = evidence_payload.get("market_asof")
    # A-3 정정 r2: source_asof 조립이 통일된 `asof` 키를 읽으므로 diag 에도 `asof`
    # 를 저장 (market_asof 필드도 병기 · 하위 호환).
    holdings_diag["asof"] = market_asof
    holdings_diag["market_asof"] = market_asof

    # A-1 정정 r3: Holdings 시장 evidence 는 market_asof 필수 (§8 "as-of 없으면
    # available X"). NAV 는 아래에서 독립적으로 자체 asof + 값 조건만으로 판정.
    holdings_notes: list[str] = []
    holdings_fact_count = 0
    matched_evidence_count = 0

    # FIX r5 (검증자 REJECTED r5 대응): TOP-N 조회 성공 판정 fail-closed 정정.
    #   builder 는 topn_status != "ok" 여도 topn_payload.asof (입력) 를 그대로 보존
    #   할 수 있으므로 market_asof 존재만으로는 fail-open. 대신 per-holding
    #   topn_match.status 를 검사:
    #     - TOP-N 조회 성공 → 각 holding 의 topn_match.status ∈
    #       {matched_topn_candidate, not_in_current_topn}.
    #     - TOP-N 조회 실패 → 모든 topn_match.status == "unavailable".
    #   holdings 가 존재하는데 모든 topn_match 가 unavailable 이면 TOP-N 실패.
    holdings_evidence_item_count = 0
    holdings_selection_result_count = 0
    holdings_out_list = evidence_payload.get("holdings") or []
    topn_ok_signal_count = sum(
        1
        for h in holdings_out_list
        if (h.get("topn_match") or {}).get("status")
        in ("matched_topn_candidate", "not_in_current_topn")
    )
    # holdings 가 있는데 어떤 holding 도 TOP-N ok 신호 (matched / not_in_topn)
    # 를 못 받았다면 TOP-N reader 실패. holdings 자체가 비어 있으면 이 판정
    # 이 아니라 downstream no_contentful_fact 로 흘려보낸다.
    topn_reader_failed = bool(holdings_out_list) and topn_ok_signal_count == 0

    if not market_asof or topn_reader_failed:
        holdings_diag["status"] = "unavailable"
        holdings_diag["reason"] = (
            "holdings_market_asof_missing" if not market_asof else "topn_query_failed"
        )
    else:
        for h_out in evidence_payload.get("holdings") or []:
            name = h_out.get("name") or h_out.get("ticker")
            line_parts: list[str] = []
            has_evidence_item = False

            returns_payload = h_out.get("returns") or {}
            if returns_payload.get("status") in ("ok", "partial"):
                r1m = _fmt_pct(returns_payload.get("one_month_return_pct"))
                r3m = _fmt_pct(returns_payload.get("three_month_return_pct"))
                frag = []
                if r1m:
                    frag.append(f"1개월 {r1m}")
                if r3m:
                    frag.append(f"3개월 {r3m}")
                if frag:
                    line_parts.append(" / ".join(frag))
                    has_evidence_item = True

            excess_payload = h_out.get("excess_return") or {}
            if excess_payload.get("status") in ("ok", "partial"):
                exc_1m = _fmt_pct(excess_payload.get("vs_kodex200_1m_pctp"))
                exc_3m = _fmt_pct(excess_payload.get("vs_kodex200_3m_pctp"))
                frag2 = []
                if exc_1m:
                    frag2.append(f"1개월 초과 {exc_1m}")
                if exc_3m:
                    frag2.append(f"3개월 초과 {exc_3m}")
                if frag2:
                    line_parts.append("KODEX200 대비 " + " / ".join(frag2))
                    has_evidence_item = True

            topn_match = h_out.get("topn_match") or {}
            match_status = topn_match.get("status")
            if match_status == "matched_topn_candidate":
                rank = topn_match.get("rank")
                if rank is not None:
                    line_parts.append(f"Market Discovery TOP{rank}")
                    has_evidence_item = True
            elif match_status == "not_in_current_topn":
                # FIX r3 (설계자 확정본 Q3): 정상 조회 결과 TOP-N 에 없음도 evidence.
                line_parts.append("현재 Market Discovery TOP-N 미포함")
                has_evidence_item = True

            # 단기 흐름 (builder: STATUS_OK "ok" / STATUS_PARTIAL "partial",
            # 필드 return_20d_pct).
            stm = h_out.get("short_term_momentum") or {}
            if stm.get("status") in ("ok", "partial"):
                stm_20d = _fmt_pct(stm.get("return_20d_pct"))
                if stm_20d:
                    line_parts.append(f"최근 20거래일 {stm_20d}")
                    has_evidence_item = True

            # 구성종목 overlap (builder: status=CONSTITUENTS_OK("ok") ·
            # 필드 overlap_with_market_core = list[dict]).
            constituents = h_out.get("constituents_overlap") or {}
            if constituents.get("status") == "ok":
                overlap_items = constituents.get("overlap_with_market_core") or []
                overlap_names = [
                    (it.get("name") or it.get("ticker"))
                    for it in overlap_items
                    if isinstance(it, dict) and (it.get("name") or it.get("ticker"))
                ]
                if overlap_names:
                    preview = ", ".join(overlap_names[: min(3, len(overlap_names))])
                    line_parts.append(f"구성종목 반복 핵심: {preview}")
                    has_evidence_item = True

            if has_evidence_item:
                holdings_evidence_item_count += 1

            if line_parts and name and has_evidence_item:
                line_text = (
                    f"{name} ({market_asof} 기준): " + " · ".join(line_parts) + "."
                )
                holdings_notes.append(line_text)
                holdings_fact_count += 1
                holdings_selection_result_count += 1
                matched_evidence_count += 1

        if holdings_fact_count == 0:
            holdings_diag["status"] = "unavailable"
            holdings_diag["reason"] = REASON_NO_CONTENTFUL_FACT
        else:
            holdings_diag["status"] = "available"
            holdings_diag["contentful_fact_count"] = holdings_fact_count
            holdings_diag["matched_evidence_count"] = matched_evidence_count

    # FIX r3 (설계자 확정본 Q7): fact attribution 진단 필드 확장.
    holdings_diag["holdings_loaded_count"] = len(holdings)
    holdings_diag["holdings_evidence_item_count"] = holdings_evidence_item_count
    holdings_diag["holdings_contentful_fact_count"] = holdings_fact_count
    holdings_diag["holdings_selection_result_count"] = holdings_selection_result_count
    holdings_diag["rendered_holdings_fact_count"] = holdings_fact_count
    # FIX r5 (검증자 REJECTED r5 대응): Q4 privacy 진단 boolean + 실제 값 검사.
    #   각 holding 의 실제 quantity / avg_buy_price / account_group 값이 composed
    #   notes 안에 substring 으로 나타나는지 검사. 진단 표기는 boolean.
    holdings_diag["private_fields_exposed"] = _detect_private_values_exposed(
        holdings, holdings_notes
    )
    holdings_diag["raw_identifier_exposed"] = _detect_raw_identifier_exposed(
        holdings_notes
    )

    # NAV — 각 보유 ETF 에 대해 fetch_latest_nav 조회 (§5.3 독립 조건).
    nav_notes: list[str] = []
    nav_fact_count = 0
    nav_matched = 0
    nav_asof_latest: Optional[str] = None
    for h in holdings:
        row = nav_fn(etf_ticker=h.ticker, db_path=market_db_path)
        if row is None:
            continue
        # A-1 정정 r4: NAV row 자체의 실제 as-of 필수 (지시문 §5.3 "실제 as-of 존재").
        # asof 부재 시 해당 row 를 available 처리하지 않는다.
        if not row.asof:
            continue
        # 실제 값이 있어야 available (지시문 §5.3).
        has_nav_or_price = (row.nav is not None) or (row.market_price is not None)
        if not has_nav_or_price and row.discount_rate_pct is None:
            continue
        nav_matched += 1
        if nav_asof_latest is None or row.asof > nav_asof_latest:
            nav_asof_latest = row.asof
        parts: list[str] = []
        if row.market_price is not None and row.nav is not None:
            parts.append(f"시장가 {row.market_price:,.0f} / NAV {row.nav:,.0f}")
        elif row.nav is not None:
            parts.append(f"NAV {row.nav:,.0f}")
        elif row.market_price is not None:
            parts.append(f"시장가 {row.market_price:,.0f}")
        disc = _fmt_pct(row.discount_rate_pct)
        if disc:
            parts.append(f"괴리율 {disc}")
        if parts:
            nav_notes.append(
                f"{h.display_name()} NAV ({row.asof} 기준): " + " · ".join(parts) + "."
            )
            nav_fact_count += 1

    nav_diag["matched_count"] = nav_matched
    nav_diag["asof"] = nav_asof_latest
    if nav_fact_count == 0:
        nav_diag["status"] = "unavailable"
        nav_diag["reason"] = REASON_NAV_UNAVAILABLE
        nav_status = "unavailable"
        nav_notes = []
    else:
        nav_diag["status"] = "available"
        nav_diag["contentful_fact_count"] = nav_fact_count
        nav_status = "available"
    # FIX r3 명시적 필드 (설계자 확정본 Q7).
    nav_diag["nav_contentful_fact_count"] = nav_fact_count

    holdings_status = "available" if holdings_fact_count > 0 else "unavailable"
    return (
        (holdings_status, holdings_notes, holdings_diag),
        (nav_status, nav_notes, nav_diag),
    )


# ── 메인 API ─────────────────────────────────────────────────────────────────


def compose_runtime_evidence(
    push_kind: str,
    *,
    market_db_path: Optional[Path] = None,
    holdings_file: Optional[Path] = None,
    holdings_loader: Optional[Callable[[], list[Holding]]] = None,
    topn_fn: Optional[Callable[..., dict]] = None,
    nav_fn: Optional[Callable[..., Any]] = None,
    evidence_fn: Optional[Callable[..., dict[str, Any]]] = None,
) -> RuntimeEvidenceResult:
    """OCI Runtime + Diagnosis 공통 evidence 조립.

    DI (지시문 Q10): 모든 reader 를 파라미터로 override 가능.
    default 는 프로덕션 경로.

    반환:
      - available_sources : {source_key: "available" | "<reason_code>"}
      - extra_notes       : 사용자 문장 (실제 수치 · as-of 포함).
      - diagnostics       : 내부 진단 (본문 비노출).
    """
    market_db = market_db_path or _MARKET_DB_DEFAULT
    hfile = holdings_file or HOLDINGS_FILE
    hload = holdings_loader or _holdings_load
    tfn = topn_fn or _compute_topn
    nfn = nav_fn or _fetch_latest_nav
    efn = evidence_fn or _build_holdings_market_evidence

    result = RuntimeEvidenceResult()
    diag_sources: dict[str, Any] = {}

    # B-6: push_kind 가 실제로 참조하는 source 만 계산 (spike 는 market discovery 불필요).
    _MD_PUSH_KINDS = {"market_briefing"}
    _HOLDINGS_PUSH_KINDS = {"holdings_briefing"}

    if push_kind in _MD_PUSH_KINDS or push_kind in _HOLDINGS_PUSH_KINDS:
        # holdings_briefing 은 evidence 조립 안에서 topn_fn 을 별도로 호출하므로
        # market_briefing 만 여기서 market_discovery 를 별도 계산.
        pass

    md_status = "unavailable"
    md_notes: list[str] = []
    md_diag: dict[str, Any] = {"status": "unavailable"}
    if push_kind in _MD_PUSH_KINDS:
        md_status, md_notes, md_diag = _compose_market_discovery(tfn, market_db)
        diag_sources[SRC_MARKET_DISCOVERY] = md_diag

    # Holdings + NAV — holdings_briefing 만 사용.
    h_status = "unavailable"
    h_notes: list[str] = []
    h_diag: dict[str, Any] = {}
    nav_status = "unavailable"
    nav_notes: list[str] = []
    nav_diag: dict[str, Any] = {}
    if push_kind in _HOLDINGS_PUSH_KINDS:
        (h_status, h_notes, h_diag), (nav_status, nav_notes, nav_diag) = (
            _compose_holdings_and_nav(hload, hfile, tfn, market_db, efn, nfn)
        )
        diag_sources[SRC_HOLDINGS] = h_diag
        diag_sources[SRC_NAV_DISCOUNT] = nav_diag

    # push_kind 별 source 조립 (지시문 Q1 · PUSH_KIND_DATA_SOURCES 계약).
    if push_kind == "market_briefing":
        result.available_sources = {
            SRC_KR_REALTIME: REASON_EXTERNAL_FETCH_REQUIRED,
            SRC_OVERNIGHT_US: REASON_EXTERNAL_FETCH_REQUIRED,
            SRC_MARKET_DISCOVERY: (
                "available"
                if md_status == "available"
                else md_diag.get("reason", "unavailable")
            ),
            SRC_ML_BASELINE: REASON_NOT_IMPLEMENTED,
            SRC_NEWS: REASON_NOT_IMPLEMENTED,
        }
        if md_status == "available":
            result.extra_notes = md_notes
    elif push_kind == "holdings_briefing":
        result.available_sources = {
            SRC_HOLDINGS: (
                "available"
                if h_status == "available"
                else h_diag.get("reason", "unavailable")
            ),
            SRC_KR_REALTIME: REASON_EXTERNAL_FETCH_REQUIRED,
            SRC_NAV_DISCOUNT: (
                "available"
                if nav_status == "available"
                else nav_diag.get("reason", "unavailable")
            ),
            SRC_ML_BASELINE: REASON_NOT_IMPLEMENTED,
        }
        combined_notes: list[str] = []
        if h_status == "available":
            combined_notes.extend(h_notes)
        if nav_status == "available":
            combined_notes.extend(nav_notes)
        result.extra_notes = combined_notes
    elif push_kind == "spike_or_falling_alert":
        result.available_sources = {
            SRC_UNIVERSE_MOMENTUM: REASON_NOT_IMPLEMENTED,
            SRC_KR_REALTIME: REASON_EXTERNAL_FETCH_REQUIRED,
        }
        result.extra_notes = []
    else:
        result.available_sources = {}
        result.extra_notes = []

    # push_kind 별 실제 사용하는 source 만 contentful 합산 (지시문 §6 · A-1 정정).
    if push_kind == "market_briefing":
        contentful_fact_count = (
            (md_diag.get("contentful_fact_count", 0) or 0)
            if md_status == "available"
            else 0
        )
        selection_result_count = (
            md_diag.get("candidates_count", 0) if md_status == "available" else 0
        )
    elif push_kind == "holdings_briefing":
        contentful_fact_count = (
            (h_diag.get("contentful_fact_count", 0) or 0)
            if h_status == "available"
            else 0
        ) + (
            (nav_diag.get("contentful_fact_count", 0) or 0)
            if nav_status == "available"
            else 0
        )
        selection_result_count = (
            h_diag.get("matched_evidence_count", 0) if h_status == "available" else 0
        )
    else:
        contentful_fact_count = 0
        selection_result_count = 0

    # source_statuses: 고정 unavailable source 는 'unavailable' 로 라벨 (검증자 A-1 지적).
    def _status_for(src_key: str, reason_or_status: str) -> str:
        # 실제 계산된 source (diag 존재) 는 그 status 사용.
        if src_key in diag_sources:
            return diag_sources[src_key].get("status") or "unavailable"
        # 고정 unavailable source (외부 API 필요 / not_implemented) 는 'unavailable'.
        return "unavailable"

    unavailable_reasons = {
        src: st for src, st in result.available_sources.items() if st != "available"
    }

    result.diagnostics = {
        "push_kind": push_kind,
        "source_statuses": {
            src: _status_for(src, st) for src, st in result.available_sources.items()
        },
        "source_asof": {
            src: diag_sources.get(src, {}).get("asof")
            for src in diag_sources
            if diag_sources.get(src, {}).get("asof") is not None
        },
        "contentful_fact_count": contentful_fact_count,
        "selection_result_count": selection_result_count,
        "unavailable_reasons": unavailable_reasons,
        "holdings_source_present": diag_sources.get(SRC_HOLDINGS, {}).get(
            "source_present", False
        ),
    }
    # FIX r3 (설계자 확정본 Q7): holdings_briefing 전용 fact attribution 필드.
    if push_kind == "holdings_briefing":
        h_source_diag = diag_sources.get(SRC_HOLDINGS, {})
        nav_source_diag = diag_sources.get(SRC_NAV_DISCOUNT, {})
        result.diagnostics.update(
            {
                "holdings_loaded_count": h_source_diag.get("holdings_loaded_count", 0),
                "holdings_evidence_item_count": h_source_diag.get(
                    "holdings_evidence_item_count", 0
                ),
                "holdings_contentful_fact_count": h_source_diag.get(
                    "holdings_contentful_fact_count", 0
                ),
                "nav_contentful_fact_count": nav_source_diag.get(
                    "nav_contentful_fact_count", 0
                ),
                "holdings_selection_result_count": h_source_diag.get(
                    "holdings_selection_result_count", 0
                ),
                "rendered_holdings_fact_count": h_source_diag.get(
                    "rendered_holdings_fact_count", 0
                ),
                "holdings_snapshot_status": h_source_diag.get("status", "unavailable"),
                "holdings_snapshot_reason": h_source_diag.get("reason") or "",
                "private_fields_exposed": bool(
                    h_source_diag.get("private_fields_exposed", False)
                ),
                "raw_identifier_exposed": bool(
                    h_source_diag.get("raw_identifier_exposed", False)
                ),
            }
        )
        # selection_result_count 를 holdings 전용 값으로 재정의 (설계자 확정본 Q3).
        result.diagnostics["selection_result_count"] = h_source_diag.get(
            "holdings_selection_result_count", 0
        )
    return result
