"""POC6-32 — `GET /weekly/etf-check`(「주간 ETF 점검」 · 외부 호출 0) ·
`GET /market/constituents/summary`(한 ETF 구성 요약).

쓰기(r1 F3): 기록 · 구성 · 노출 읽기는 `mode=ro` 연결이고 파일이 없으면 열지 않는다(만들지 않음) · 공통 시장
근거는 시장 DB 파일이 없으면 아무 읽기 없이 '확인 불가'(빌더가 확인) · 있으면 기존 읽기 함수(목록 요약 · 시장 근거)가
표를 확인한다(표가 모두 있으면 바뀌는 것 없음 · 빠진 시장 표만 그 기존 함수가 만듦).

한 응답 = 한 검토 건(판정 §3-1): 화면 · [AI용 주간 검토 복사] · [AI 투자 세션으로 넘기기]가 이 응답 하나를 같이 쓴다.
고른 ETF 를 바꾸거나 다시 읽으면 응답 전체가 바뀐다. V2 에서 경로를 옮겼다(`/today/weekly-review` 없음 · PLAN V2 S3).
- 목록 = 「후보리스트」 기본값과 같은 인자의 공통 기간 요약(`build_summary` · 1개월 · 제외 4종 · 다른 화면 설정과 따로).
- 시장 = 공통 시장 근거(`market_evidence.build_market_evidence` · 일일 복사와 같은 칸 · 같은 `now` · 목록 요약이 ok 일
  때만 읽음) 하나 — 화면 ① · 복사 글의 시장 [근거 n] · 저장 시장 칸이 같은 응답(PLAN V2 S3 · §4-3). 시장 흐름은 그
  안에서 한 번만 읽는다(V1 의 목록 요약 판정 줄 · 두 번째 시장 흐름 읽기 없음).
- 고른 ETF = 상위 30 안 어느 종목이든(묶음 안 ETF 포함 · V2 W7) → ③ 「선택한 후보 검토」(`weekly_candidate_review`):
  공식 기준정보(목록 분류와 같은 CSV 읽기) · 구성 요약(보유와 무관하게 읽음) · 1 · 3개월 · 더 확인할 것 · 보유 겹침.
- 보유 겹침 = 기존 노출 계산(`constituents_pair_exposure.build` · 고른 보유 없음 · 계산 · 지문 변경 없음).
- 고른 후보의 구성 · 원천일 확인 기록 · ETF 목록 · 보유 쪽 구성 = 한 읽기 트랜잭션(`weekly_candidate_reads` · r1 F1) —
  ③ R1 구성 요약 · R4 겹침 · 복사 글 · 넘기기 묶음이 같은 사본에서 나온다(두 번 읽어 섞이지 않음).
- 마지막 기록 = 출처 `today_weekly_review` 기록 중 저장 시각이 가장 최근인 1건(판정 Q8 (a) · 다른 화면 기록과 섞지 않음 ·
  `decision_evidence_readonly` 로 읽음 · 기록 DB 를 만들거나 마이그레이션하지 않음).
- `GET /weekly/etf-check/records/{id}/review` = 저장한 주간 기록 하나의 AI 답 해석(「AI 투자 세션」 '당시 검토' · AC3) —
  저장 원문(질문 · 답)을 지금 해석기로 나눔(PLAN I-14 · 시장 자료 다시 계산 없음 · `decision_evidence_readonly` 로 읽음).
읽기 실패는 그 칸만 '확인 불가'로 두고 다른 칸은 그대로 보인다(알 수 없음을 '없음'으로 바꾸지 않음).
"""

from __future__ import annotations

import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping, Optional

from fastapi import APIRouter, HTTPException, Query

from app import (
    api_etf_compare,
    constituents_pair_exposure,
    decision_evidence_readonly,
    decision_evidence_store,
    etf_constituents_store,
    etf_official_info,
    market_evidence,
    weekly_candidate_reads,
    weekly_candidate_review as wcr,
    weekly_review as wr,
)
from app.pc_etf_compare_summary import build_summary
from app.weekly_review_answers import last_record_view
from app.weekly_review_text import build_copy

KST = timezone(timedelta(hours=9))
router = APIRouter(tags=["today-weekly-review"])


def assemble(
    *,
    summary: Mapping[str, Any],
    selected: Optional[str],
    exposure: Optional[Mapping[str, Any]],
    exposure_error: bool,
    last: Mapping[str, Any],
    generated_at: str,
    official_info: Optional[Mapping[str, Any]] = None,
    constituents: Optional[Mapping[str, Any]] = None,
    market_evidence: Optional[Mapping[str, Any]] = None,
) -> dict[str, Any]:
    """입력은 모두 인자(순수) — 시험은 11/16 고정 자료로 이 함수를 부른다.

    `official_info` = 고른 ETF 의 공식 기준정보 조회(`etf_official_info` 모양 · 없으면 '파일을 읽지 못함') ·
    `constituents` = 고른 ETF 구성 요약(`weekly_candidate_reads.read_candidate` 의 칸 · 없으면 '읽지 못함') ·
    `market_evidence` = 공통 시장 근거(`market_evidence.build_market_evidence` 모양 ·
    없으면 화면 ① · 복사 글 시장 칸 '확인 불가').
    """
    base = {
        "source_screen": wr.SOURCE_SCREEN,
        "generated_at": generated_at,
        "last_record": dict(last),
    }
    if summary.get("status") != "ok":
        return {
            **base,
            "status": summary.get("status") or "invalid",
            "message": summary.get("message") or "목록을 만들 수 없습니다",
        }
    cond = wr.condition_of(summary)
    csv_meta = ((summary.get("sources") or {}).get("official_csv")) or {}
    flows = wr.flows_of(summary["top"], csv_meta.get("status") != "unavailable")
    by_ticker = {r["ticker"]: r for r in summary["top"]}
    sel_row = by_ticker.get(selected) if selected else None
    sel = (
        {"ticker": sel_row["ticker"], "name": sel_row["name"], "rank": sel_row["rank"]}
        if sel_row
        else None
    )
    overlap = wr.overlap_of(sel, exposure, exposure_error) if sel else None
    review = (
        wcr.review_of(
            row=sel_row,
            summary=summary,
            product=wcr.product_of(sel_row["ticker"], official_info),
            constituents=wcr.summary_of(constituents),
            overlap=overlap,
            generated_at=generated_at,
        )
        if sel_row
        else None
    )
    copy = build_copy(
        condition=cond,
        flows=flows,
        selected=sel,
        overlap=overlap,
        summary=summary,
        market_evidence=market_evidence,
        review=review,
    )
    dq = wcr.data_quality_snapshot(
        summary=summary, condition=cond, selected=sel, flows=flows, review=review
    )
    # 근거 목록 = 복사 글의 [근거 n] 그대로(I-13 · I-14)
    dq["evidence_list"] = copy["evidence"]
    return {
        **base,
        "status": "ok",
        "message": None,
        "condition": cond,
        "end_date": summary["end_date"],
        "flows": flows,
        "first_rows": wr.FIRST_ROWS,
        "selected": sel,
        "selected_missing": bool(selected) and sel is None,
        "selected_review": review,
        "overlap": overlap,
        "evidence": copy["evidence"],
        "answer_targets": copy["targets"],
        "copy_text": copy["text"],
        # 공통 시장 근거(일일 글 제외 · 화면 ① · 복사 글의 시장 [근거 n] 과 같은 줄)
        "market_evidence": wr.common_snapshot(market_evidence),
        "candidate_snapshot": wr.candidate_snapshot(summary),
        "market_context_snapshot": wr.market_snapshot(summary, market_evidence),
        # 넘기기 · 저장(기존 자유 칸 · 표 변경 없음 · PLAN V2 §4-3 · I-13)
        "data_quality_snapshot": dq,
        "constituent_snapshot": wcr.constituent_snapshot(review),
    }


def _read_last() -> dict[str, Any]:
    try:
        rec = decision_evidence_readonly.latest_record(
            db_path=decision_evidence_store.DEFAULT_DB_PATH,
            source_screen=wr.SOURCE_SCREEN,
        )
        return last_record_view(rec)
    except (sqlite3.Error, OSError, ValueError, KeyError):
        return {
            "status": "error",
            "message": "기록을 읽지 못했습니다 — 「AI 투자 세션」에서 확인",
        }


@router.get("/weekly/etf-check/records/{record_id}/review")
def get_weekly_record_review(record_id: str) -> dict[str, Any]:
    """저장한 주간 기록 하나의 AI 답 해석(「AI 투자 세션」 '당시 검토' · AC3) — 저장한 질문 원문 · 답 원문을 ④ 마지막
    기록과 같은 해석기(`last_record_view`)로 나눈다(PLAN I-14 · 해석 규칙이 바뀌면 표시도 바뀜). 시장 자료 다시 계산
    없음 · 기록 읽기 = `decision_evidence_readonly`(`mode=ro` · 파일이 없으면 만들지 않고 404 · 옛 스키마도 마이그레이션
    없이). 기록이 없거나 「주간 ETF 점검」 기록이 아니면 404 · 읽기 실패는 503(쉬운 한국어 안내)."""
    try:
        rec = decision_evidence_readonly.get_record(
            record_id, db_path=decision_evidence_store.DEFAULT_DB_PATH
        )
        if rec is None:
            raise HTTPException(status_code=404, detail="기록을 찾을 수 없습니다.")
        if rec.get("source_screen") != wr.SOURCE_SCREEN:
            raise HTTPException(
                status_code=404,
                detail="「주간 ETF 점검」에서 저장한 기록이 아닙니다.",
            )
        return last_record_view(rec)
    except (sqlite3.Error, OSError, ValueError, KeyError):
        raise HTTPException(
            status_code=503, detail="기록을 읽지 못했습니다 — 잠시 뒤 다시 열어 주세요."
        )


@router.get("/weekly/etf-check")
def get_weekly_review(
    selected: Optional[str] = Query(
        None, description="고른 ETF(상위 30 안 어느 종목이든 · 없으면 대조 전)"
    ),
) -> dict[str, Any]:
    official, official_meta = api_etf_compare._official()
    dictionary, dictionary_meta = api_etf_compare._dictionary()
    held, held_status = api_etf_compare._held_tickers()
    summary = build_summary(
        db_path=api_etf_compare.MARKET_DB_PATH,
        basis=wr.BASIS,
        filters=dict(wr.FILTERS),
        official=official,
        official_meta=official_meta,
        dictionary=dictionary,
        dictionary_meta=dictionary_meta,
        held_tickers=held,
        holdings_status=held_status,
    )
    sel = (selected or "").strip() or None
    row = (
        next((r for r in summary.get("top") or [] if r["ticker"] == sel), None)
        if sel
        else None
    )
    exposure, exposure_error = None, False
    official_info = cons = None
    if row is not None:
        cond = constituents_pair_exposure.condition_of(
            screen=wr.SOURCE_SCREEN,
            basis=wr.BASIS,
            side=wr.SIDE,
            rank=row["rank"],
            start_date=row["basis_return"]["start"],
            end_date=row["basis_return"]["end"],
            filters=dict(wr.FILTERS),
        )
        # 구성 · 원천일 확인 기록 · ETF 목록 · 보유 쪽 구성 = 한 읽기(r1 F1 · R1 · R4 · 복사 글 · 넘기기 묶음이 같은 사본)
        got = weekly_candidate_reads.read_candidate(
            sel, db_path=etf_constituents_store.DEFAULT_DB_PATH, condition=cond
        )
        cons, exposure, exposure_error = (
            got["constituents"],
            got["exposure"],
            got["exposure_error"],
        )
        # 목록 분류와 같은 CSV 읽기(`official`)로 고른 ETF 의 공식 기준정보를 낸다(한 응답 = 같은 파일)
        official_info = etf_official_info.from_official(
            official, official_meta, [sel], got["names"]
        )
    now = datetime.now(KST)
    # 공통 시장 근거 — 읽기 실패는 그 칸만 '확인 불가'(빌더가 칸마다 잡음) · 검토일 = 이 응답 생성일 KST(I-24)
    mev = (
        market_evidence.build_market_evidence(now=now)
        if summary.get("status") == "ok"
        else None
    )
    return assemble(
        summary=summary,
        selected=sel,
        exposure=exposure,
        exposure_error=exposure_error,
        last=_read_last(),
        generated_at=now.isoformat(timespec="seconds"),
        official_info=official_info,
        constituents=cons,
        market_evidence=mev,
    )


_TICKER = re.compile(r"^[0-9A-Za-z]{1,12}$")


@router.get("/market/constituents/summary")
def get_constituents_summary(ticker: str = Query(...)) -> dict[str, Any]:
    """한 ETF 구성(「ETF 구성종목」 한 ETF 모드 · PLAN V2 S6) — 주간 ③ 과 같은 구성 요약 + 저장 행 전체 + 집중
    (Top 1 · 3 · 5 · 10 · 기존 정의). 원천일이 확인된 최신 구성 · 없으면 저장 최신 구성 + '원천 기준일 미확인'.
    ETF 목록 · 구성 = 한 읽기(`weekly_candidate_reads` · `mode=ro`) · 시장 DB 파일이 없으면 열지 않고
    'missing'(만들지 않음) · 수집하지 않음(수집은 [구성종목 수집] 때만)."""
    t = ticker.strip()
    if not _TICKER.match(t):
        raise HTTPException(status_code=422, detail="ticker 는 종목 코드 하나입니다.")
    db = etf_constituents_store.DEFAULT_DB_PATH
    if not Path(db).exists():
        return {
            "status": "missing",
            "message": "시장 DB 파일이 없습니다.",
            "ticker": t,
            "name": None,
        }
    got = weekly_candidate_reads.read_candidate(t, db_path=db)
    detail = got["constituents"]
    return {
        "status": "ok" if detail["state"] != wcr.C_ERROR else "error",
        "message": None if detail["state"] != wcr.C_ERROR else detail["line"],
        "ticker": t,
        "name": (got["names"] or {}).get(t),
        **detail,
    }
