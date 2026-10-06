"""POC3-OPS-02B-2 — 시장 흐름 브리핑 본문 렌더 (POC3-02D-OPS-03 부터 08:30).

설계자 §3 확정 형식. **문구 변경이 계산에 영향을 주지 않도록** 렌더를 분리한다.

## 금지 (설계 §3.4)

예상 개장 등락률 숫자 · 매수/매도/교체 지시 · `상승 섹터`·`유망 테마` ·
확률·적중률을 오늘의 확정성처럼 표현 · unavailable 을 `0` 으로 · 기준일이 다른
값을 하나로 · 기존 `확인된 항목 / 별도 확인 필요` 목록 · 기술 식별자·source
key·param ID·경로·secret.

## 기준일

**표시된 값의 실제 기준일만** 쓴다. 미국과 국내가 다르면 **분리 표시**한다.
여러 항목의 기준일이 다르면 단일 날짜로 뭉개지 않는다.
"""

from __future__ import annotations

from typing import Optional, Sequence

from app.market_briefing.evidence import (
    OUTLOOK_DOWN,
    OUTLOOK_FLAT,
    OUTLOOK_UP,
    IndexCandidate,
    Outlook,
    SupportIndex,
)
from app.market_briefing.meta_gate import (
    STATUS_API_FETCH_FAILED,
    STATUS_COVERAGE_BELOW_THRESHOLD,
    STATUS_CSV_REFRESH_REQUIRED,
    STATUS_META_GATE_STALE,
)

# POC3-02D-OPS-03 확정 계약 1 — 시장 브리핑 08:00 → 08:30 (시간 계약 명시 개정).
HEADER = "[시장 흐름 브리핑] 08:30"

# 설계자 §3.2 확정 문장 — `직전 미국 거래일` 로 기간을 명시한다.
SENTENCE_UP = (
    "직전 미국 거래일 S&P500 상승은 오늘 한국 개장에 상승 압력으로 해석됩니다."
)
SENTENCE_DOWN = (
    "직전 미국 거래일 S&P500 하락은 오늘 한국 개장에 하락 압력으로 해석됩니다."
)
SENTENCE_FLAT = "직전 미국 거래일 S&P500이 보합이어서 최근 강한 기초지수만 확인합니다."
SENTENCE_NO_OUTLOOK = (
    "미국시장 방향 근거가 최신성 조건을 충족하지 않아 최근 강한 기초지수만 확인합니다."
)

# 설계자 §8 — 내부 상태와 1:1. 기술 상태명을 본문에 노출하지 않는다.
INDEX_NOTICE = {
    STATUS_CSV_REFRESH_REQUIRED: "기초지수 정보는 공식 기준정보 갱신이 필요해 제외했습니다.",
    STATUS_COVERAGE_BELOW_THRESHOLD: "기초지수 정보는 정합성 조건을 충족하지 않아 제외했습니다.",
    STATUS_API_FETCH_FAILED: "기초지수 정보는 최신 기준을 확인하지 못해 제외했습니다.",
    "stale": "기초지수 정보는 최신성 조건을 충족하지 않아 제외했습니다.",
}
# POC3-02D-OPS-01 R2 Q27 — 저장된 07:20 판정이 오늘 창의 것이 아닐 때. 새 문구를
# 만들지 않고 **기존 승인 문구**(API 조회 실패와 같은 줄)를 쓴다 — 설계자 승인
# (2026-09-27 RESULT 판정): 판정 창을 확인하지 못한 경우에만 쓰고, 정상 0개
# (`STATUS_NO_CANDIDATE_NORMAL`)는 안내 없이 생략한다(`render_market_briefing`).
INDEX_NOTICE[STATUS_META_GATE_STALE] = INDEX_NOTICE[STATUS_API_FETCH_FAILED]

# POC3-02D-OPS-03 확정 계약 6 — 국내 기준일 ≠ 기대 직전 거래일(T-1). 설계자 확정
# 문구(설계서 §2 예시 · PLAN STEP 3-8). T-2 값 · 날짜는 본문 어디에도 쓰지 않는다.
STATUS_PREV_DAY_MISSING = "prev_trading_day_missing"
INDEX_NOTICE[STATUS_PREV_DAY_MISSING] = (
    "국내 기초지수는 직전 거래일 자료를 확인하지 못해 제외했습니다."
)

# POC3-02D-OPS-03 확정 계약 13 · PLAN STEP 7-3 — 뒤 PUSH 판단에 영향을 주는 08:10 배치
# 실패(배치가 안 돈 날) 고지. 하루 최대 1회는 시장 브리핑 일 단위 registry 가 보장한다.
# 문구는 사용자 승인(B3 · 2026-09-30 APPROVED).
# POC3-02D-OPS-04 Q2 a(설계자 2026-10-04): FDR 가격 단계 실패는 발동 입력에서 뺐다 — 보유
# 파생값은 KRX 무조정 계열(ETF 표 · 개별주 표 · 항목 1)에서 오고 FDR 을 쓰지 않는다. 배치가 아예 안 돈 날
# (KRX 도 없음 → 고점 대비 생략)에만 나가는 고지다(`runner_market_briefing.batch_failure_reasons`).
BATCH_FAILURE_NOTICE = (
    "※ 운영 안내: 오늘 아침 보유 종목 시세 갱신이 끝나지 않아 "
    "고점 대비 값이 빠질 수 있습니다."
)

# 설계자 R2 Q24 확정 문구 — `refresh_due` 주기마다 한 번, 본문 **맨 끝** 1줄.
CSV_REFRESH_NOTICE = "※ 운영 안내: KRX ETF 전종목 기본정보 CSV를 갱신해 주세요."

# 정상 산출 결과 후보 0개 — **안내 문구 없이 문단 자체를 생략**한다.
STATUS_NO_CANDIDATE_NORMAL = "no_candidate_normal"


def _pct(v: float) -> str:
    return f"{v:+.1f}%"


def outlook_sentence(outlook: Outlook) -> Optional[str]:
    if outlook.state == OUTLOOK_UP:
        return SENTENCE_UP
    if outlook.state == OUTLOOK_DOWN:
        return SENTENCE_DOWN
    if outlook.state == OUTLOOK_FLAT:
        return SENTENCE_FLAT
    return None


# 추종 ETF 표시 개수 (사용자 확정 2026-09-13). 코스피200 처럼 수십 개인 지수가
# 있어 전부 나열하면 한 줄이 과하게 길어진다. 나머지는 `외 N개` 로 센다.
MAX_SHOWN_PRODUCTS = 3


def render_products(candidate: IndexCandidate) -> str:
    """`추종 ...` 한 줄. 이름은 공식 `한글종목약명` 그대로.

    사용자 요청(2026-09-13) — `추종 ETF 2개` 만으로는 무엇인지 알 수 없다. 다만
    **매수 지시로 읽히지 않도록** 순서는 종목코드 오름차순 고정이고, 추천·선호를
    뜻하는 말을 붙이지 않는다(설계 §3.4 매수/매도 지시 금지).

    약명을 못 찾은 경우에는 개수만 남긴다 — 없는 이름을 만들지 않는다.
    """
    shown = list(candidate.products[:MAX_SHOWN_PRODUCTS])
    if not shown:
        return f"추종 ETF {candidate.ticker_count}개"
    rest = candidate.ticker_count - len(shown)
    tail = f" 외 {rest}개" if rest > 0 else ""
    return "추종 " + ", ".join(shown) + tail


def render_index_block(candidates: Sequence[IndexCandidate]) -> list[str]:
    """`오늘 볼 기초지수`. 표시명은 **공식 기초지수명 그대로**."""
    if not candidates:
        return []
    lines = ["오늘 볼 기초지수"]
    for c in candidates:
        lines.append(
            f"• {c.name}: 5일 {_pct(c.ret_5d_pct)} · 20일 {_pct(c.ret_20d_pct)}"
        )
        lines.append(f"  {render_products(c)}")
    return lines


def render_support_block(indices: Sequence[SupportIndex]) -> list[str]:
    """`근거`. **fresh 한 것만** 들어온다. 없으면 문단을 만들지 않는다."""
    if not indices:
        return []
    return ["근거", " · ".join(f"{i.label} {_pct(i.return_pct)}" for i in indices)]


def render_basis_block(*, us_asof: Optional[str], kr_asof: Optional[str]) -> list[str]:
    """`기준`. **실제 기준일만** 쓰고, 서로 다르면 분리 표시한다."""
    parts = []
    if us_asof:
        parts.append(f"미국 {us_asof} 종가")
    if kr_asof:
        parts.append(f"국내 {kr_asof} 종가")
    return ["기준", " · ".join(parts)] if parts else []


def render_market_briefing(
    *,
    outlook: Outlook,
    index_status: str,
    candidates: Sequence[IndexCandidate] = (),
    support: Sequence[SupportIndex] = (),
    us_asof: Optional[str] = None,
    kr_asof: Optional[str] = None,
    header: str = HEADER,
) -> str:
    """본문. 만들 내용이 없으면 **빈 문자열**을 돌려준다(호출자가 미발송).

    | outlook | index | 결과 |
    |---|---|---|
    | 사용 가능 | 후보 있음 | 전망 + 기초지수 |
    | 사용 가능 | **정상 0개** | **전망만** (문단 생략) |
    | 사용 가능 | 실패 4종 | 전망 + **안내 1줄** |
    | 사용 불가 | 후보 있음 | 기초지수 중심 |
    | 사용 불가 | 후보 없음·실패 | **빈 문자열** |
    """
    sentence = outlook_sentence(outlook)
    has_index = index_status == "ok" and bool(candidates)
    notice = INDEX_NOTICE.get(index_status) if index_status != "ok" else None
    if index_status == STATUS_NO_CANDIDATE_NORMAL:
        notice = None  # 정상 0개는 안내 없이 생략

    if not sentence and not has_index:
        return ""

    lines: list[str] = [header, ""]
    lines.append("오늘 한 문장")
    lines.append(sentence or SENTENCE_NO_OUTLOOK)
    lines.append("")

    if has_index:
        lines.extend(render_index_block(candidates))
        lines.append("")
    elif notice:
        lines.append(notice)
        lines.append("")

    sup = render_support_block(support)
    if sup:
        lines.extend(sup)
        lines.append("")

    basis = render_basis_block(us_asof=us_asof, kr_asof=kr_asof)
    if basis:
        lines.extend(basis)

    return "\n".join(lines).rstrip()


def append_refresh_notice(body: str) -> str:
    """본문 끝에 빈 줄 하나를 두고 CSV 갱신 안내를 붙인다. 빈 본문은 그대로."""
    return f"{body}\n\n{CSV_REFRESH_NOTICE}" if body else body


def append_batch_notice(body: str) -> str:
    """본문 끝에 빈 줄 하나를 두고 배치 실패 고지를 붙인다. 빈 본문은 그대로."""
    return f"{body}\n\n{BATCH_FAILURE_NOTICE}" if body else body


def render_notice_only(header: str = HEADER) -> str:
    """낼 내용이 없는 날의 배치 실패 고지 본문 — 머리 + 고지 한 줄(PLAN STEP 7-3)."""
    return f"{header}\n\n{BATCH_FAILURE_NOTICE}"


__all__ = [
    "BATCH_FAILURE_NOTICE",
    "CSV_REFRESH_NOTICE",
    "HEADER",
    "INDEX_NOTICE",
    "SENTENCE_DOWN",
    "SENTENCE_FLAT",
    "SENTENCE_NO_OUTLOOK",
    "SENTENCE_UP",
    "STATUS_NO_CANDIDATE_NORMAL",
    "STATUS_PREV_DAY_MISSING",
    "append_batch_notice",
    "append_refresh_notice",
    "outlook_sentence",
    "render_basis_block",
    "MAX_SHOWN_PRODUCTS",
    "render_index_block",
    "render_products",
    "render_market_briefing",
    "render_notice_only",
    "render_support_block",
]
