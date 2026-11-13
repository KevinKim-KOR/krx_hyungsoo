"""POC6-29 — 판단 근거 미리보기의 후보를 '공통 기간 목록'에서 찾는다(읽기 전용 · PLAN §3-4 · 판정 Q4-2).

화면(「후보리스트」 · 「섹터요약」 · 「보유와 후보 비교」 · 「보유」)이 본 목록 = 같은 조건의 요약
(`GET /market/etf-compare/summary` 와 같은 입력 읽기 + `build_summary` · 상 · 하위 30). 서버가 지금 다시 계산한
요약에서 그 종목을 찾아 화면이 보낸 쪽(상위/하위) · 선정 순위 · 실제 시작일 · 끝일 · 끝일 가격 시점과 대조한다.
하나라도 다르면(그사이 갱신 등) `ListChanged` — 미리보기를 만들지 않고 다시 읽기 안내.

한 저장 판으로 조립한다(검증자 r1 F1): 이 종목 상세(가격 구간 값 · 끝일 저장 시각 · KODEX 200 · NAV)를 맨 앞과
맨 끝에 한 번씩 읽어 둘이 같을 때만 쓴다. 그 사이의 요약 대조 · 추가 근거 읽기 도중 같은 날 재저장이 있으면
두 상세가 달라진다.

글 줄은 기존 후보 묶음과 같은 함수로 만든다(`decision_draft_preview_service._candidate_sections`). 그 함수가 읽는
후보 칸은 이렇게 채운다(`app/market_topn.py` 무변경):

- 1 · 3개월 수익률 · KODEX 200 동일 기간 = 행 상세 수치(`pc_etf_row_detail.build_etf_detail` · 공통 기간 날짜).
  기간이 다르거나 자료가 없으면 값을 비운다(다른 기간 값으로 채우지 않음).
- 단기 흐름 · 일간 등락 점검 · NAV 괴리율 = 기존 후보 응답과 같은 함수(`enrich_candidates_with_evidence`) —
  공통 기간 목록에 든 종목은 마지막 저장일 = 공통 끝일이라 같은 날짜가 된다.
- 시장 국면 = 같은 요약의 `regime`(069500 · 같은 끝일).
- 거래량 · 가격 흔들림 · 이동평균 · 직접 보유 · 중복 = 기존 후보 경로와 같은 추가 읽기(`selected_extras`).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from app import api_etf_compare
from app.api_market_topn_models import (
    MarketCandidate,
    MarketPeriodReturn,
    MarketReturns,
    SamePeriodKodex200,
    SamePeriodKodex200Item,
)
from app.api_market_topn_service import enrich_candidates_with_evidence
from app.decision_preview_lines import BASIS_LABEL
from app.decision_preview_sources import (
    ALLOWED_BASES,
    CandidateListUnavailable,
    selected_extras,
)
from app.market_data_store import DEFAULT_DB_PATH
from app.pc_etf_compare_periods import (
    CRIT_OK,
    STATE_AFTER_CLOSE,
    STATE_INTRADAY,
    STATE_UNKNOWN,
)
from app.pc_etf_compare_summary import LIST_N
from app.pc_etf_row_detail import build_etf_detail
from app.same_period_kodex200 import (
    REASON_CANDIDATE_PERIOD_UNKNOWN,
    REASON_KODEX200_END_MISSING,
    REASON_KODEX200_START_MISSING,
)

LIST_SOURCE_COMMON = "common_period"
LIST_CHANGED_MESSAGE = "목록이 바뀌었습니다 — 목록을 다시 읽고 다시 고르세요."
SCREEN_LABEL = {
    "candidate_list": "「후보리스트」",
    "sector_summary": "「섹터요약」",
    "holding_candidate_compare": "「보유와 후보 비교」",
    "holdings": "「보유」",
}
SIDE_LABEL = {"top": "상위", "bottom": "하위"}
# 응답 값은 소수 4자리(요약 `round(…, 4)`) — 같은 계산이면 같은 값 · 표현 차이만 허용.
VALUE_TOLERANCE = 1e-6
# 보유 판단 근거 — 이 화면 조건 목록 밖 사유(화면 `outReasonText` 와 같은 낱말).
OUT_TEXT = {
    "stock": "개별 주식 — ETF 비교 목록 대상 아님",
    "filter_excluded": "제외 조건(인버스 · 레버리지 · 합성 · 선물)에 해당해 비교 목록 밖",
    "no_price": "저장 가격 없음",
    "period_differs": "조회 기간과 시작 · 끝 날짜가 달라 비교 목록 밖",
}
PRICE_STATES = (STATE_INTRADAY, STATE_AFTER_CLOSE, STATE_UNKNOWN)
SAME_REASONS = (
    REASON_CANDIDATE_PERIOD_UNKNOWN,
    REASON_KODEX200_START_MISSING,
    REASON_KODEX200_END_MISSING,
)
FILTER_KEYS = (
    "exclude_inverse",
    "exclude_leveraged",
    "exclude_synthetic",
    "exclude_futures",
)


class ListChanged(Exception):
    """화면이 본 목록과 지금 다시 계산한 목록이 다름(그사이 갱신 · 순위 · 날짜 · 가격 시점)."""


@dataclass(frozen=True)
class CommonPeriodPick:
    """화면이 고른 행 — 조건(기간 · 제외) + 그 행에서 본 쪽 · 선정 순위 · 실제 날짜 · 끝일 가격 시점."""

    screen: str
    basis: str
    filters: dict[str, bool]
    side: str
    rank: int
    start_date: str
    end_date: str
    end_price_state: str
    # 화면이 본 선정 기간 수익률(같은 날 장중 재저장으로 가격만 바뀐 경우도 '목록이 바뀜'으로 · 검토 지적).
    # 없으면(예전 화면) 대조하지 않는다.
    basis_value: Optional[float] = None

    def is_valid(self) -> bool:
        return (
            self.screen in SCREEN_LABEL
            and self.basis in ALLOWED_BASES
            and set(self.filters) == set(FILTER_KEYS)
            and self.side in SIDE_LABEL
            and isinstance(self.rank, int)
            and not isinstance(self.rank, bool)
            and 1 <= self.rank <= LIST_N
            and bool(self.start_date)
            and bool(self.end_date)
            and self.end_price_state in PRICE_STATES
        )


def _md(day: str) -> str:
    """'2026-10-12' → '10/12'."""
    _, m, d = day.split("-")
    return f"{int(m)}/{int(d)}"


def list_label(pick: CommonPeriodPick) -> str:
    """[대상] 줄 — 예: 「후보리스트」 1개월 상위 3위 · 공통 기간 10/12 → 11/10."""
    return (
        f"{SCREEN_LABEL[pick.screen]} {BASIS_LABEL[pick.basis]} "
        f"{SIDE_LABEL[pick.side]} {pick.rank}위 · 공통 기간 "
        f"{_md(pick.start_date)} → {_md(pick.end_date)}"
    )


def _matches(row: dict[str, Any], pick: CommonPeriodPick) -> bool:
    br = row.get("basis_return") or {}
    value = br.get("value")
    return (
        row.get("rank") == pick.rank
        and br.get("start") == pick.start_date
        and br.get("end") == pick.end_date
        and (row.get("end_price") or {}).get("state") == pick.end_price_state
        and (
            pick.basis_value is None
            or (
                isinstance(value, (int, float))
                and abs(float(value) - pick.basis_value) <= VALUE_TOLERANCE
            )
        )
    )


def _period_return(p: dict[str, Any]) -> MarketPeriodReturn:
    """행 상세 1 · 3개월 → 후보 수익률 칸(ok 만 값 · 날짜 — 기간 다름 · 자료 없음은 비움)."""
    if p.get("status") != CRIT_OK:
        return MarketPeriodReturn()
    return MarketPeriodReturn(
        return_pct=p["value"],
        basis_start_date=p["start"],
        basis_end_date=p["end"],
        price_start_date=p["start"],
        price_end_date=p["end"],
    )


def _same_item(s: dict[str, Any]) -> SamePeriodKodex200Item:
    """행 상세 동일 기간 → 기존 후보 칸(ok · unavailable + 기존 사유 코드)."""
    if s.get("status") == CRIT_OK:
        return SamePeriodKodex200Item(
            status="ok",
            start_date=s["start"],
            end_date=s["end"],
            candidate_return_pct=s["etf_return_pct"],
            kodex200_return_pct=s["kodex200_return_pct"],
            diff_pctp=s["value"],
        )
    reason = s.get("reason")
    return SamePeriodKodex200Item(
        status="unavailable",
        # 기간 다름 · 자료 없음 = 후보 기간을 공통 기간으로 정할 수 없음(기존 사유 문구 그대로).
        reason=reason if reason in SAME_REASONS else REASON_CANDIDATE_PERIOD_UNKNOWN,
        start_date=s.get("start"),
        end_date=s.get("end"),
    )


def _market_context(regime: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    """요약 `regime`(069500 · 같은 끝일) → 기존 후보 묶음의 시장 칸 모양."""
    if not regime:
        return None
    return {
        "regime_code": regime.get("code"),
        "regime_label": regime.get("label"),
        "asof": regime.get("asof"),
        "regime_streak": {
            "streak_days": regime.get("streak_days"),
            "at_least": regime.get("streak_at_least"),
        },
    }


def load_common_period_bundle(
    ticker: str, pick: CommonPeriodPick, *, db_path: Path = DEFAULT_DB_PATH
) -> dict[str, Any]:
    """공통 기간 목록에서 후보 하나 — 목록이 화면과 다르면 `ListChanged` · 요약 자료 자체가 없으면
    `CandidateListUnavailable`."""
    detail = build_etf_detail(db_path, [ticker])  # 맨 앞 — 맨 끝 다시 읽기와 대조
    summary = api_etf_compare.get_etf_compare_summary(
        basis=pick.basis,  # type: ignore[arg-type]
        **pick.filters,
    )
    status = summary.get("status")
    if status == "no_common_period":
        # 화면은 공통 기간 목록을 봤다 — 지금은 공통 기간이 없다(그사이 갱신).
        raise ListChanged(status)
    if status != "ok":
        raise CandidateListUnavailable(status)
    row = next(
        (r for r in summary.get(pick.side) or [] if r.get("ticker") == ticker), None
    )
    if row is None or not _matches(row, pick):
        raise ListChanged("row")
    same_end = detail.get("end_date") == summary.get("end_date")
    if detail.get("status") != "ok" or not same_end:
        raise ListChanged("detail")  # 두 읽기 사이에 끝일이 바뀜
    item = detail["items"][0]
    cand = MarketCandidate(
        rank=row["rank"],
        ticker=ticker,
        name=row.get("name"),
        tags=list(row.get("tags") or []),
        selected_return_pct=row["basis_return"]["value"],
        selected_basis_start_date=row["basis_return"]["start"],
        selected_basis_end_date=row["basis_return"]["end"],
        returns=MarketReturns(
            one_month=_period_return(item["m1"]),
            three_month=_period_return(item["m3"]),
        ),
        same_period_kodex200=SamePeriodKodex200(
            one_month=_same_item(item["same_kodex"]["one_month"]),
            three_month=_same_item(item["same_kodex"]["three_month"]),
        ),
    )
    cand_dump = enrich_candidates_with_evidence([cand], db_path=db_path)[0].model_dump()
    extras = selected_extras(ticker, cand_dump, db_path=db_path)
    if build_etf_detail(db_path, [ticker]) != detail:
        raise ListChanged("reread")  # 조립하는 사이 이 종목 · KODEX 200 저장 판이 바뀜
    return {
        "candidate": cand_dump,
        "market_context": _market_context(summary.get("regime")),
        "basis": pick.basis,
        "order": "asc" if pick.side == "bottom" else "desc",
        "list_label": list_label(pick),
        **extras,
    }


def _position(link: dict[str, Any]) -> str:
    """보유 한 종목의 목록 위치 — 화면 `candidateLinkText` 와 같은 뜻."""
    br = link.get("basis_return")
    if not link.get("in_population") or not br:
        return OUT_TEXT.get(link.get("out_reason") or "", "비교 목록 밖")
    side, rank, top = link.get("side"), link.get("side_rank"), link.get("top_rank")
    if side == "bottom":
        where = f"하위 {rank}위" + (
            f" · 상위 {top}위(상·하위 공통)" if top is not None else ""
        )
    elif side == "top":
        where = f"상위 {rank}위"
    else:
        where = "상·하위 30 밖"
    return f"{br['value']:+.2f}% · {_md(br['start'])} → {_md(br['end'])} · {where}"


def _exposure_line(link: dict[str, Any]) -> str:
    """하위 목록 ETF 구성종목과의 겹침 — 화면 `exposureText` 와 같은 뜻 · 범위."""
    e = link.get("exposure") or {}
    status = e.get("status")
    if status == "no_constituents":
        return "하위 목록과의 구성종목 노출: 확인 불가 — 이 ETF 구성종목 자료가 없습니다(겹침 없음이라는 뜻 아님)."
    if status == "no_sample":
        return "하위 목록과의 구성종목 노출: 확인 불가 — 하위 ETF 구성 자료가 없습니다."
    lo, hi = e.get("compared_asof_min"), e.get("compared_asof_max")
    asof = f"({_md(lo)}{'' if hi == lo else f' ~ {_md(hi)}'})" if lo and hi else ""
    scope = (
        f"비교 범위 = 하위 ETF 중 구성 자료 있는 {e.get('compared_etf_count')}개{asof}"
        f" · 각 비중 상위 {e.get('top_n')}종목"
    )
    mine = f" · 이 ETF 구성 {_md(e['holding_asof'])}" if e.get("holding_asof") else ""
    if status == "ok":
        names = " · ".join(
            f"{o.get('name') or o.get('key')}({len(o.get('etfs') or [])})"
            for o in e.get("overlaps") or []
        )
        return f"하위 목록과의 구성종목 노출: {names} · {scope}{mine} · 숫자 = 겹친 하위 ETF 수"
    return f"하위 목록과의 구성종목 노출: 겹친 구성종목 0건 · {scope}{mine}"


def holding_list_context(
    ticker: str,
    *,
    screen: str,
    basis: str,
    filters: dict[str, bool],
    db_path: Path = DEFAULT_DB_PATH,
) -> dict[str, Any]:
    """보유 판단 근거 — 이 화면 조건의 공통 기간 목록과 확인된 관계만(판정 Q4-2 둘째 항목).

    예전 '현재 1개월 상위 10 후보' 겹침 · 동일 기간 줄 대신 쓴다. 목록을 못 만들면 관계를 '확인 불가'로
    적고 미리보기는 계속 연다(보유 미리보기는 보유 종목으로 열림). 같은 기간 KODEX 200 = 종목 상세
    수치(행 상세와 같은 응답 · 같은 끝일일 때만). 목록을 상세 두 번 읽기 사이에 읽어, 그사이 이 종목 ·
    KODEX 200 저장 판이 바뀌었으면 섞인 관계를 적지 않는다(검증자 r1 F1 과 같은 뿌리).
    """
    where = f"{SCREEN_LABEL.get(screen, '이 화면')} 조건 {BASIS_LABEL[basis]} 상·하위 {LIST_N}"
    detail = build_etf_detail(db_path, [ticker])
    summary = api_etf_compare.get_etf_compare_summary(
        basis=basis, **filters  # type: ignore[arg-type]
    )
    if summary.get("status") != "ok":
        return {
            "relation_lines": [
                f"후보 목록과의 관계: 확인 불가 — {where} 비교 목록을 만들 수 없습니다."
            ],
            "same_period_kodex200": None,
        }
    if build_etf_detail(db_path, [ticker]) != detail:
        return {
            "relation_lines": [
                f"후보 목록과의 관계: 확인 불가 — {where} 목록을 읽는 동안 저장 자료가 "
                "바뀌었습니다. [다시 생성]으로 다시 확인하세요."
            ],
            "same_period_kodex200": None,
        }
    held = summary.get("holdings") or {}
    link = next((h for h in held.get("items") or [] if h.get("ticker") == ticker), None)
    if held.get("status") != "ok" or link is None:
        lines = [
            f"후보 목록과의 관계: 확인 불가 — {where} 목록 응답에 이 보유 연결이 없습니다."
        ]
    else:
        p = summary["period"]
        lines = [
            f"후보 목록 위치({where} · 공통 기간 {_md(p['start'])} → {_md(p['end'])}): "
            f"{_position(link)}",
            _exposure_line(link),
        ]
    same: Optional[dict[str, Any]] = None
    items = detail.get("items") or []
    if (
        detail.get("status") == "ok"
        and items
        and detail.get("end_date") == summary.get("end_date")
    ):
        sk = items[0].get("same_kodex") or {}
        if sk.get("one_month") and sk.get("three_month"):
            same = SamePeriodKodex200(
                one_month=_same_item(sk["one_month"]),
                three_month=_same_item(sk["three_month"]),
            ).model_dump()
    return {"relation_lines": lines, "same_period_kodex200": same}
