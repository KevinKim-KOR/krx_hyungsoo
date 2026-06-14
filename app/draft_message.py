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
from app.message_helpers import (  # noqa: F401
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

# POC2 Cleanup (2026-06-14) — focus / summary 렌더링 책임을 draft_message_focus.py
# 로 분리 (KS-10 near 해소). 본 파일은 re-export 로 기존 import 경로 호환 유지.
from app.draft_message_focus import (  # noqa: F401
    TOP_N_BOTTOM_PNL_RATE,
    TOP_N_PRICE_MISSING,
    TOP_N_TOP_MARKET_WEIGHT,
    TOP_N_TOP_PNL_RATE,
    _render_focus_item,
    _render_focus_section,
    _render_summary_lines,
    compute_summary,
    select_focus_items,
)

# Step 7B (2026-05-12) — PUSH 1 "보유 종목 상태 브리핑" bullet 빌더는
# app.message_holdings_briefing 으로 분리 (draft_message.py KS-10 trigger 해소).
# 라벨 상수는 본 파일에서도 re-export 하여 기존 import 경로 호환을 유지한다.
from app.message_holdings_briefing import (  # noqa: F401
    HOLDINGS_STATUS_BRIEFING_LABEL,
    HOLDINGS_STATUS_BRIEFING_NEUTRAL_NOTE,
)
from app.message_holdings_briefing import (
    build_holdings_status_briefing_bullet as _holdings_status_briefing_bullet,
)

# Step 7C (2026-05-12) — PUSH 3 "급락 ETF 주의 신호" bullet picker 는 동일 패턴으로
# app.message_falling_etf_bullet 로 분리 (draft_message.py KS-10 near 해소).
from app.message_falling_etf_bullet import (  # noqa: F401
    FALLING_ETF_CAUTION_BULLET_LABEL,
)
from app.message_falling_etf_bullet import (
    extract_falling_etf_bullet as _falling_etf_caution_bullet,
)

# POC2 Holdings × Market Discovery Evidence 1차 (2026-06-03) — [판단 사유] 의
# "보유 vs 시장" bullet 1줄 picker. helper 는 신규 모듈로 분리 (KS-10 부담 분리).
from app.message_holdings_market_evidence_bullet import (
    render_holdings_market_evidence_bullet,
)

# POC2 — ML Baseline Evidence Draft Integration (2026-06-11). 저장된 baseline
# 룩백 report 가 GenerateDraft 시점에 snapshot 으로 박혀 있고, 본 helper 가
# [판단 사유] 의 "ML baseline 룩백 evidence" 1줄을 추출한다. unavailable / error
# 도 1줄로 노출 (조용히 빠지지 않음 — 지시문 §4.7).
from app.ml_baseline_evidence import render_ml_baseline_evidence_bullet

# Step 6 Fix 라운드: external_universe_bullet 빌더는 본 파일 안에 직접 둔다
# (factor_signals universe scope signal 에서 추출 — message_universe_bullet 의
# build_universe_signal_texts 가 reason_text/fallback_text 만 만드는 책임으로 단순화).

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
    "EXTERNAL_UNIVERSE_BULLET_LABEL",
    "EXTERNAL_UNIVERSE_FACTOR_ID",
    "is_holdings_draft",
    "compute_summary",
    "select_focus_items",
    "build_message_text",
]

# Step 2B 정책 상수 — 이번 단계에서는 설정 파일로 빼지 않는다 (BACKLOG).
# TOP_N_* 은 draft_message_focus 모듈에 정의되어 본 모듈에서 re-export.
MAX_LENGTH_CHARS = 3500

TRUNCATION_NOTICE = (
    "...(메시지 길이 제한으로 일부 생략됨. 전체 상세는 웹 화면에서 확인하세요.)"
)

# Step 3: 판단 사유 섹션의 라벨. portfolio scope signal 1줄만 표시.
JUDGMENT_SECTION_HEADER = "[판단 사유]"

# Step 5B: 모멘텀 점검 bullet 라벨 — Step 7B (2026-05-12) 이후 [판단 사유] 별도 bullet
# 으로 노출되지 않는다. holdings momentum 정보는 "보유 종목 상태 브리핑" bullet 안에
# portfolio 비중 정보와 함께 통합 표시된다. 라벨 상수는 호환 / 테스트 참조 목적으로 유지.
MOMENTUM_BULLET_LABEL = "모멘텀 점검"

# Step 6 + Step 7A 명칭 정렬 (2026-05-11):
# Step 6 시점 "외부 후보 점검" 사용자 노출 명칭을 공식 PUSH 2 명칭 "신규 ETF 관찰 후보"
# 로 정렬한다. factor_id (universe_one_month_return) / 내부 함수명 / 파일명은 변경하지
# 않는다 — 사용자 노출 문구만 정렬.
EXTERNAL_UNIVERSE_BULLET_LABEL = "신규 ETF 관찰 후보"
EXTERNAL_UNIVERSE_FACTOR_ID = "universe_one_month_return"

# Step 7C 라벨 / 식별자는 app.message_falling_etf_bullet 에 정의됨 (단일 출처).
FALLING_ETF_CAUTION_FACTOR_ID = "universe_falling_one_month_return"


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


# ─── Step 2B 핵심 — 요약 / 주목 종목 / focus 렌더링 ───────────────────
# 본 helper 들은 app.draft_message_focus 로 분리되어 본 파일 상단에서 re-export.


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


# Step 7B 통합 후 _factor_bullet / _momentum_bullet 별도 함수는 _render_judgment_lines
# 에서 더 이상 호출되지 않으며 외부 import 도 없음 — 본 파일에서 함수 정의 제거.
# 라벨 상수 (MOMENTUM_BULLET_LABEL 등) 는 호환 목적으로 유지.


def _external_universe_bullet(payload: dict[str, Any]) -> Optional[str]:
    """Step 6 Fix — factor_signals 의 scope="universe" signal → bullet 본문.

    universe signal 은 draft.py 가 universe_momentum_latest.json 에서 만든 factor signal
    (factor_id="universe_one_month_return", scope="universe"). 신규 draft_payload 키가
    아니라 factor_signals 5번째 키 안의 새 entry — BACKLOG 가드 준수.

    is_available=True 면 reason_text 를, False 면 fallback_text 를 사용한다. 둘 다 빈
    문자열이거나 signal 자체가 없으면 None 반환.
    """
    factor_signals = payload.get("factor_signals")
    if not isinstance(factor_signals, list):
        return None
    universe_sig: Optional[dict[str, Any]] = None
    for sig in factor_signals:
        if isinstance(sig, dict) and sig.get("scope") == "universe":
            universe_sig = sig
            break
    if universe_sig is None:
        return None

    factor_name = universe_sig.get("factor_name") or EXTERNAL_UNIVERSE_BULLET_LABEL
    if universe_sig.get("is_available"):
        text = universe_sig.get("reason_text")
    else:
        text = universe_sig.get("fallback_text")
    if not isinstance(text, str) or not text.strip():
        return None
    return f"- {factor_name}: {text}"


def _render_judgment_lines(payload: dict[str, Any]) -> list[str]:
    """[판단 사유] 섹션 — Step 7C 이후 구조:
      1. 보유 종목 상태 브리핑 (portfolio 비중 + holdings momentum 통합 1줄)
      2. 신규 ETF 관찰 후보 (Step 7A — universe scope signal 1줄)
      3. 급락 ETF 주의 신호 (Step 7C — universe_falling scope signal 1줄, optional)

    헤더 중복 금지: bullet 이 1개라도 있으면 헤더 1번 + bullets. 모두 없으면 빈 리스트.
    종목별 / 후보별 / Top N 항목은 메시지에 나열하지 않는다.

    Step 7C: 급락 후보 없을 때는 falling bullet 자체가 생성되지 않으므로 자연 생략.
    Telegram 에 "신호 없음" 같은 매번 메시지를 추가하지 않는다 (KS-5 알림 과다 방지).

    Step 5B 의 _factor_bullet / _momentum_bullet 은 본 함수에서 더 이상 호출하지
    않는다 — 두 정보가 _holdings_status_briefing_bullet 에 통합 흡수됨.
    """
    bullets: list[str] = []
    briefing = _holdings_status_briefing_bullet(payload)
    if briefing is not None:
        bullets.append(briefing)
    # POC2 Holdings × Market Discovery Evidence 1차 (2026-06-03) — 보유 기준
    # evidence 가 외부 후보 흐름보다 먼저 읽히도록 briefing 직후 배치. helper 는
    # 신규 모듈로 분리 (KS-10 부담 분리).
    market_evidence = render_holdings_market_evidence_bullet(payload)
    if market_evidence is not None:
        bullets.append(market_evidence)
    ml_evidence = render_ml_baseline_evidence_bullet(payload)
    if ml_evidence is not None:
        bullets.append(ml_evidence)
    eu = _external_universe_bullet(payload)
    if eu is not None:
        bullets.append(eu)
    falling = _falling_etf_caution_bullet(payload)
    if falling is not None:
        bullets.append(falling)
    if not bullets:
        return []
    return ["", JUDGMENT_SECTION_HEADER, *bullets]


def _runtime_evidence_lines(payload: dict[str, Any]) -> list[str]:
    """PUSH-2 holdings draft 의 runtime_package.push_context 기반 [보유 종목 관찰
    포인트] + [시장 흐름 연결] 섹션 (3-PUSH Message Text Runtime Evidence,
    2026-06-14, AC-3 / AC-4).

    payload 의 runtime_package 안 push_context 가 의미 있는 관찰을 갖고 있을
    때만 노출. 없으면 빈 리스트 → 기존 흐름(보유 종목 상태 브리핑 bullet 등)
    만으로 진행.
    """
    rp = payload.get("runtime_package")
    if not isinstance(rp, dict):
        return []
    push_context = rp.get("push_context")
    if not isinstance(push_context, dict) or not push_context:
        return []
    # 동적 import — draft_message 가 push_context 모듈을 top-level 로 의존하지
    # 않게 (circular 방지).
    from app.push_context import holdings_observation_lines

    lines = holdings_observation_lines(push_context)
    if not lines:
        return []
    return ["", *lines]


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
    runtime_lines = _runtime_evidence_lines(payload)
    summary_lines = _render_summary_lines(summary)

    if focus_limit is None:
        focus_subset = focus_full
    else:
        focus_subset = focus_full[:focus_limit]
    focus_lines = _render_focus_section(focus_subset)

    footer_lines = ["", "전체 보유 상세는 웹 화면에서 확인하세요."]

    return "\n".join(
        header_lines
        + judgment_lines
        + runtime_lines
        + summary_lines
        + focus_lines
        + footer_lines
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
