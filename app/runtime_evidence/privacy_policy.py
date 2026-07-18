"""개인정보 · raw identifier 노출 탐지 **정책** (지시문 §7).

Cleanup / FIX r7 Round 3 에서 `privacy.py` 로부터 분리. detector 알고리즘과
정책 상수를 분리해 정책 변경 시 detector 영향 없이 관리.

내용:
- RAW_IDENT_TOKENS: 내부 reason code · raw source key · raw push_kind.
- PRIVACY_CONTEXT_TOKENS: 개인정보 문맥 마커 (숫자 값이 이 토큰 주변에 있으면 leak).
- PRIVACY_NUMERIC_MIN_LEN: 숫자 값 감지 최소 길이 (2자, quantity=10 등 포함).
- PRIVACY_CONTEXT_WINDOW: 문맥 검사 window (좌우 32자).

계약:
- 정책 상수는 detector 가 read-only 로 사용.
- 새로운 개인정보 field 추가는 이 파일만 수정하면 됨.
"""

from __future__ import annotations

# ── raw identifier 노출 탐지 (내부 reason code · raw source key · raw push_kind) ──


RAW_IDENT_TOKENS: tuple[str, ...] = (
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
    # Universe artifact 관련 내부 reason code (검증자 REJECTED r2 대응).
    "artifact_refresh_status_failed",
    "artifact_refresh_status_unknown",
    "artifact_mode_mismatch",
    "artifact_asof_missing",
    "artifact_summary_missing",
    "artifact_candidates_missing",
    "artifact_loader_error",
    "artifact_missing_or_invalid_json",
    "universe_no_displayable_candidates",
    "candidate_not_dict",
    "candidate_ticker_missing",
    "candidate_score_result_missing",
    "candidate_is_scored_field_missing",
    "candidate_is_scored_not_bool",
    "candidate_score_value_missing_or_invalid",
    "candidate_score_value_not_finite",
    "artifact_status_scored_inconsistency",
    "artifact_status_ok_but_partial_scored",
    "artifact_status_partial_but_all_scored",
    "artifact_asof_format_invalid",
    "artifact_asof_not_a_real_date",
    "temp_mode_mismatch",
    "temp_owner_mismatch",
    "exec_user_not_expected_owner",
    "current_user_unavailable",
)


# ── 개인정보 문맥 토큰 (숫자 값이 이 토큰 주변에 있을 때만 leak 판정) ──
#
# 검증자 REJECTED r6 대응: quantity=10 등 소수 정수 값도 감지해야 하지만
# 실제 evidence 는 "20거래일", "TOP10", "STAR50", "-0.30%" 같은 정상 문맥에서
# 소수 정수를 자유롭게 사용한다. 문맥 마커가 근처에 있을 때만 leak 판정.


PRIVACY_CONTEXT_TOKENS: tuple[str, ...] = (
    # 한글 개인정보 marker (Round 3 false-negative 보정 시 추가).
    "수량",
    "평단",
    "평균가",
    "매입가",
    "보유수량",
    "보유주",
    "원금",
    "투자원금",
    "매입원금",
    "평가금액",
    "평가액",
    "평가손익",
    "예수금",
    "계좌잔고",
    "계좌평가액",
    # 영문 개인정보 marker.
    "quantity",
    "avg_buy_price",
    "avg_price",
    "invested_amount",
    "invested",
    "account_group",
    "shares",
    "position_size",
    "cost_basis",
    "market_value",
    "unrealized_pnl",
    "realized_pnl",
)


# ── detector 파라미터 ──


# 숫자 값 감지 최소 길이 (2자 미만은 우연 일치 위험 너무 큼).
PRIVACY_NUMERIC_MIN_LEN: int = 2

# 문맥 검사 window (매칭 위치 좌우 N자 안에 PRIVACY_CONTEXT_TOKENS 하나라도 있어야 leak).
PRIVACY_CONTEXT_WINDOW: int = 32


# ── account_group 기본 라벨 (개인정보 아님) ──


ACCOUNT_GROUP_DEFAULT_LABEL: str = "일반"
