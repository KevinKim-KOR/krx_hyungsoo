"""POC5-06 — 상태 · 화면 문구 · 응답 모양(설계 개정 2 §2 · §4 · §5 · §10-5).

문구는 이 파일 한 곳에서만 정한다 — '하락 위험 예측' · '지금' · '재진입 적기' 같은 말은 쓰지
않는다(설계 §2 · §5-1). 이 값은 연구 추정이며 매수/매도 지시가 아니다.
"""

from __future__ import annotations

SCHEMA = "reentry_review_v1"

# ── 상태 ─────────────────────────────────────────────────────────────────────

OK = "OK"
DATA_SHORT = "DATA_SHORT"
PRICE_BASIS_UNCONFIRMED = "PRICE_BASIS_UNCONFIRMED"
NOT_ETF = "NOT_ETF"
NO_PRICE = "NO_PRICE"
AXIS_UNCERTAIN = "AXIS_UNCERTAIN"
READ_FAILED = "READ_FAILED"
NO_COPY = "NO_COPY"

STATUS_TEXT = {
    OK: "계산 완료",
    DATA_SHORT: "자료 부족 — 추정값을 만들지 않음",
    PRICE_BASIS_UNCONFIRMED: "가격 기준 확인 불가 — 현재 추정값을 만들지 않음",
    NOT_ETF: "ML 대상 아님(ETF 만)",
    NO_PRICE: "저장 가격 없음",
    AXIS_UNCERTAIN: "연구 축 불확실 — 추정값을 만들지 않음",
    READ_FAILED: "읽기 실패",
    NO_COPY: "원장 사본 없음",
}

# 검증 비교(전체 MAE · 화면 소수 2자리 기준)
IMPROVED = "IMPROVED"
NO_DIFFERENCE = "NO_DIFFERENCE"
WORSE = "WORSE"
VERDICT_TEXT = {
    IMPROVED: "단순 기준보다 검증 오차 작음",
    NO_DIFFERENCE: "단순 기준과 검증 오차 같음",
    WORSE: "단순 기준보다 검증 오차 큼",
}

# ── 이름 · 고정 문구 ──────────────────────────────────────────────────────────

TARGET_NAME = "이후 20거래일 최저 종가 변화(연구 추정)"
RESEARCH_NOTE = "연구 추정 · 투자 유효성 미확정"
NOT_ADVICE = "이 값은 매수/매도 지시가 아닙니다."
STALE_NOTE = "이 날짜 기준 검토"

NOTES = (
    "가격은 PC 에 저장된 종가입니다(현재 체결 가능 가격이 아님).",
    "D20 = 기준일 종가 대비 이후 20거래일 중 가장 낮았던 종가의 변화(모두 높으면 0) — "
    "최대낙폭(MDD) · 장중 최대손실 · 손실 확률이 아닙니다.",
    "수수료 · 세금을 반영하지 않은 저장 종가 변화입니다 — 가격 의미는 '저장 종가(네이버 계열 · "
    "분배락 조정 흔적 · 총수익 여부 미확정)'입니다.",
    "겹치는 20일 창을 독립 표본으로 보지 않으므로 신뢰구간 · 성공률 · 확률을 표시하지 않습니다.",
    "이미 살펴본 과거 자료로 다시 계산한 연구이며 새로운 확증 시험이 아닙니다.",
    "알림이 도움이 됐는지 · 특정 거래가 적절했는지를 판정하지 않습니다.",
    RESEARCH_NOTE,
    NOT_ADVICE,
)

LINK_SUBJECT = "SUBJECT"
LINK_SECTOR_REPRESENTATIVE = "SECTOR_REPRESENTATIVE"
LINK_INDEX_GROUP_MEMBER = "INDEX_GROUP_MEMBER"
LINK_TEXT = {
    LINK_SUBJECT: "이 종목 알림",
    LINK_SECTOR_REPRESENTATIVE: "연관 근거 — 사업군 신호의 대표 ETF 로 기록됨",
    LINK_INDEX_GROUP_MEMBER: "연관 근거 — 기초지수 묶음 구성 ETF 로 기록됨",
}

VIEW_DELIVERED = "DELIVERED"
VIEW_PARTIAL = "PARTIAL"
VIEW_NOT_DELIVERED = "NOT_DELIVERED"
VIEW_OBSERVED = "OBSERVED"
VIEW_TEXT = {
    VIEW_DELIVERED: "전달됨",
    VIEW_PARTIAL: "일부 전달(partial)",
    VIEW_NOT_DELIVERED: "본문에 실렸으나 전달 안 됨",
    VIEW_OBSERVED: "관측만(본문에 안 실림)",
}

FEEDBACK_SCOPE_TEXT = "이 알림 전체에 대한 평가(종목별 평가 아님)"

NAVIGATION = (
    {
        "menu": "market_discovery",
        "label": "요즘 잘 오르는 ETF — [최신 시장 데이터 갱신]",
        "note": "전체 ETF(약 1,200종목)의 최근 120일을 받습니다 · 약 1.5 ~ 2.5분 · 6시간 간격",
    },
    {
        "menu": "alert_records",
        "label": "받은 알림 기록 — [원장 새로고침]",
        "note": "OCI 원장 사본을 받습니다(시세는 갱신하지 않음)",
    },
)
