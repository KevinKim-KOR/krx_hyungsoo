"""POC5-23 — 선택 ETF 판단 근거 미리보기 통합(설계 V1 · PLAN 판정 2026-10-18).

연결 검사: tmp 시장 DB · tmp 보유 파일로 화면 API(`/holdings/market-evidence/latest` ·
`/market/topn/latest`) 응답을 받고, 같은 자료로 만든 미리보기 글이 그 응답 값을 그대로 옮기는지 본다.
라이브 DB · 보유 파일은 열지 않는다(`api_client` 고정 자료 · conftest 격리).
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import json
import random
import shutil
import struct
import subprocess

import pytest
from fastapi.testclient import TestClient

from app import api_decision_draft_preview, api_market_topn, decision_preview_sources
from app.decision_preview_lines import (
    HOLDING_OVERLAP_LIMIT,
    HOLDING_OVERLAP_SCOPE,
    OVERLAP_LIMIT,
    SAME_PERIOD_LIMIT,
    SHORT_NOTE_CANDIDATE,
    SHORT_NOTE_HOLDING,
)
from app.etf_constituents_store import ConstituentRow, upsert_constituents
from app.etf_nav_store import NavDailyRow, upsert_nav_rows
from app.market_data_store import (
    EtfDailyPriceRow,
    EtfMasterRow,
    upsert_daily_prices,
    upsert_etf_master,
)
from app.pc_price_basis import load_recent_price_rows
from app.pc_price_volatility import build_price_volatility
from app.preview_number_format import (
    fmt_exact,
    intl_fixed,
    math_round_grouped,
    to_fixed,
)
from app.stored_volume_evidence import build_stored_volume_evidence
from tests.test_pc_price_basis import api_client  # noqa: F401 — fixture

END = date(2026, 10, 14)
START = date(2026, 5, 1)
HELD_ETF = "111111"  # 보유 ETF · 구성종목 있음(06-22)
HELD_ETF_NO_CONS = "222222"  # 보유 ETF · 구성종목 없음
CAND = "333333"  # 후보 · 구성종목 있음(10-02)
CAND_NO_CONS = "444444"  # 후보 · 구성종목 없음
CAND_LATE = "555555"  # 후보 · 마지막 저장일이 KODEX200 보다 이름(10-10)
HELD_ETF_OTHER = "666666"  # 보유 ETF · 구성종목 있음(06-19) · 후보와 공통 종목 없음
STOCK = "005930"  # 보유 개별 종목(etf_master 에 없음)
KODEX = "069500"
PREVIEW = "/decision-draft/preview"
LIST_PARAMS = {
    "n": 10,
    "basis": "one_month",
    "order": "desc",
    "exclude_inverse": True,
    "exclude_leveraged": True,
    "exclude_synthetic": True,
    "exclude_futures": True,
}


def _series(
    ticker: str, base: float, drift: float, vol0: int = 1000, end: date = END
) -> list[EtfDailyPriceRow]:
    out: list[EtfDailyPriceRow] = []
    prev = None
    d = START
    i = 0
    while d <= end:
        c = round(base * (1 + drift * i) + (i % 5) * 0.37, 4)
        change = (c / prev - 1.0) if prev else 0.0
        # 종목마다 거래량 모양이 다르다(마지막 날 급증 = vol0 의 3배) — 다른 종목 행을 쓰면 값이 달라진다.
        vol = vol0 + 13 * i + (2 * vol0 if d == end else 0)
        out.append(EtfDailyPriceRow(ticker, d.isoformat(), c, c, c, c, vol, change))
        prev = c
        d += timedelta(days=1)
        i += 1
    return out


# 종목별 가격 모양(기준가 · 추세 · 거래량 기본값 · 마지막 저장일).
SERIES_SPEC = {
    KODEX: (100.0, -0.0006, 9000, END),
    HELD_ETF: (50.0, 0.0004, 2000, END),
    HELD_ETF_NO_CONS: (70.0, 0.0002, 3000, END),
    CAND: (30.0, 0.004, 500, END),
    CAND_NO_CONS: (40.0, 0.003, 700, END),
    CAND_LATE: (35.0, 0.0035, 800, date(2026, 10, 10)),
    HELD_ETF_OTHER: (45.0, 0.0001, 1500, END),
    # 개별 종목은 KODEX200 보다 하루 늦게까지 저장 — 저장 가격 표 전체 최신일 ≠ KODEX200 최신일.
    STOCK: (60.0, -0.001, 4000, date(2026, 10, 15)),
}


def _series_for(ticker: str) -> list[EtfDailyPriceRow]:
    base, drift, vol0, end = SERIES_SPEC[ticker]
    return _series(ticker, base, drift, vol0, end)


def _cons(
    etf: str, asof: str, items: list[tuple[str, str, float]]
) -> list[ConstituentRow]:
    return [
        ConstituentRow(
            etf_ticker=etf,
            asof=asof,
            source="src",
            rank=i + 1,
            constituent_ticker=tk,
            constituent_name=nm,
            weight_pct=w,
        )
        for i, (tk, nm, w) in enumerate(items)
    ]


@pytest.fixture
def seeded(
    api_client: TestClient,  # noqa: F811 — tests.test_pc_price_basis 의 fixture
    monkeypatch: pytest.MonkeyPatch,
) -> TestClient:
    db: Path = api_market_topn.DEFAULT_DB_PATH
    monkeypatch.setattr(api_decision_draft_preview, "DEFAULT_DB_PATH", db)
    upsert_etf_master(
        [
            EtfMasterRow(KODEX, "KODEX 200", "1", 100.0, 1, 1.0),
            EtfMasterRow(HELD_ETF, "보유 반도체 ETF", "1", 100.0, 1, 1.0),
            EtfMasterRow(HELD_ETF_NO_CONS, "보유 배당 ETF", "1", 100.0, 1, 1.0),
            EtfMasterRow(CAND, "후보 장비 ETF", "1", 100.0, 1, 1.0),
            EtfMasterRow(CAND_NO_CONS, "후보 소재 ETF", "1", 100.0, 1, 1.0),
            EtfMasterRow(CAND_LATE, "후보 늦은 ETF", "1", 100.0, 1, 1.0),
            EtfMasterRow(HELD_ETF_OTHER, "보유 해외 ETF", "1", 100.0, 1, 1.0),
        ],
        source="Test",
        db_path=db,
    )
    for tk in SERIES_SPEC:
        upsert_daily_prices(_series_for(tk), source="FinanceDataReader", db_path=db)
    upsert_constituents(
        _cons(
            HELD_ETF,
            "2026-06-22",
            [
                ("005930", "삼성전자", 20.0),
                ("000660", "SK하이닉스", 10.0),
                ("042700", "한미반도체", 4.0),
            ],
        ),
        db_path=db,
    )
    upsert_constituents(
        _cons(
            CAND,
            "2026-10-02",
            [
                ("005930", "삼성전자", 25.0),
                ("000660", "SK하이닉스", 5.0),
                ("240810", "원익IPS", 7.0),
            ],
        ),
        db_path=db,
    )
    upsert_constituents(
        _cons(
            HELD_ETF_OTHER,
            "2026-06-19",
            [("AAPL", "애플", 12.0), ("MSFT", "마이크로소프트", 11.0)],
        ),
        db_path=db,
    )
    # NAV — 보유 ETF 는 정상(괴리 3% 이상 경고 코드) · 후보는 부분 자료(값 있음 · 이전 자료 재사용).
    upsert_nav_rows(
        [
            NavDailyRow(HELD_ETF, "2026-10-14", 100.0, 103.5, 3.5, "naver", "ok", None),
            NavDailyRow(
                CAND,
                "2026-10-13",
                50.0,
                49.8,
                -0.4,
                "naver",
                "partial",
                "이전 자료 사용",
            ),
        ],
        db_path=db,
    )
    payload = [
        {
            "ticker": HELD_ETF,
            "name": "보유 반도체 ETF",
            "quantity": 3,
            "avg_buy_price": 50,
        },
        {
            "ticker": HELD_ETF_NO_CONS,
            "name": "보유 배당 ETF",
            "quantity": 2,
            "avg_buy_price": 70,
        },
        {"ticker": STOCK, "name": "삼성전자", "quantity": 1, "avg_buy_price": 60},
        {
            "ticker": HELD_ETF_OTHER,
            "name": "보유 해외 ETF",
            "quantity": 1,
            "avg_buy_price": 45,
        },
    ]
    assert api_client.put("/holdings", json={"holdings": payload}).status_code == 200
    return api_client


def _preview(client: TestClient, kind: str, ticker: str, **q) -> dict:
    body = client.post(
        PREVIEW, json={"target_kind": kind, "ticker": ticker, **q}
    ).json()
    return body


def _pct(v: float, unit: str = "%") -> str:
    # 화면 `samePeriodKodex.fmtSigned` 와 같은 규칙(부호는 0 초과만 · toFixed(2)).
    return f"{'+' if v > 0 else ''}{to_fixed(v, 2)}{unit}"


# ── 보유 ──────────────────────────────────────────────────────────────────


def test_holding_preview_carries_screen_response_values(seeded: TestClient) -> None:
    ev = seeded.get("/holdings/market-evidence/latest").json()
    item = next(h for h in ev["holdings"] if h["ticker"] == HELD_ETF)
    body = _preview(seeded, "holding", HELD_ETF)
    assert body["status"] == "ok"
    text = body["preview_text"]
    stm, pd_ = item["short_term_momentum"], item["price_dates"]
    assert stm["status"] == "ok"
    # 가격 흐름 = 화면(PC 근거 사본) 값 그대로 · 단기 문구 계약(판정 §3).
    for n in (5, 10, 20):
        assert f"{n}저장일 {_pct(stm[f'return_{n}d_pct'])}" in text
        assert f"{n}저장일 {_pct(stm[f'excess_vs_kodex200_{n}d_pctp'], '%p')}" in text
    assert f"({pd_['start_date_20d']} → {pd_['end_date']})" in text
    assert "단기 KODEX200 차이(저장일 수 기준)" in text and SHORT_NOTE_HOLDING in text
    assert "같은 저장일 구간" not in text
    band = item["decline_band"]
    assert band["judgeable"] is True and band["state"] is None
    assert (
        f"PC 20저장일 하락 구간: 해당 없음 (20저장일 {band['return_20d_pct_1dp']:.1f}%)"
        in text
    )
    # 거래량 · 흔들림 = 화면 값 그대로.
    sv, pv = item["stored_volume"], item["price_volatility"]
    assert f"평균 대비 {intl_fixed(sv['ratio'], 2)}배" in text
    assert f"직전 20개 저장일 평균 {intl_fixed(sv['avg_prev20'], 2)}주" in text
    assert pv["status"] == "ok"
    assert f"최근 20구간 {pv['recent']['value_pct']:.2f}%" in text
    assert f"직전 20구간 {pv['previous']['value_pct']:.2f}%" in text
    # 키 연결(BACKLOG 기록 누락 해소) — 겹침의 실제 비교 대상 · 항목 · 구성종목 저장일 그대로.
    assert item["constituents_overlap"]["status"] == "ok"
    assert (
        f"{HOLDING_OVERLAP_SCOPE}: "
        "삼성전자 20.00%(후보 2개에 반복), SK하이닉스 10.00%(후보 2개에 반복) · 이 ETF 구성종목 2026-06-22"
    ) in text
    # 비교 범위 · Top 10 한계(내 보유 ETF 사이 중복 아님)를 함께 적는다(검토 r1 · 판정 §2).
    assert HOLDING_OVERLAP_LIMIT in text
    assert "데이터 품질은 확인되지 않았습니다" not in text
    assert "아직 확인되지 않았습니다" not in text
    # 동일 기간: 이 보유 종목은 상위 후보와 연결 → 그 객체 값 그대로.
    sp = item["same_period_kodex200"]["one_month"]
    assert sp["status"] == "ok"
    assert (
        f"1개월 {_pct(sp['diff_pctp'], '%p')} (후보 {_pct(sp['candidate_return_pct'])} · "
        f"KODEX200 {_pct(sp['kodex200_return_pct'])} · 사용 종가 {sp['start_date']} → {sp['end_date']})"
    ) in text
    # 날짜 · 생성 시각.
    assert body["evidence_as_of"]["target_as_of_date"] == pd_["end_date"]
    assert body["generated_at"]
    assert "보유 종목(ETF)" in text


def test_holding_stock_marks_etf_only_bundles_as_not_applicable(
    seeded: TestClient,
) -> None:
    text = _preview(seeded, "holding", STOCK)["preview_text"]
    assert "보유 종목(개별 종목)" in text
    # 상위 후보와 연결되지 않은 보유 → 동일 기간은 사유(다른 값 · 0 으로 채우지 않음).
    assert (
        "1개월 · 3개월: 값 없음 — 동일 기간 비교는 현재 1개월 상위 10 후보에 든 보유 종목만 제공합니다."
        in text
    )
    assert "구성종목 겹침 · NAV 괴리율: 대상 아님(개별 종목)" in text
    assert "구성종목 자료가 저장돼 있지 않습니다" not in text


def test_holding_without_constituents_is_unconfirmed_not_none(
    seeded: TestClient,
) -> None:
    text = _preview(seeded, "holding", HELD_ETF_NO_CONS)["preview_text"]
    assert (
        "구성종목 겹침: 확인 불가 — 이 ETF 의 구성종목 자료가 저장돼 있지 않습니다(겹침 없음이라는 뜻 아님)."
        in text
    )
    assert "겹치는 반복 종목 없음" not in text
    # 한 묶음이 없어도 나머지 묶음은 그대로.
    assert "[거래량]" in text and "평균 대비" in text


# ── 후보 ──────────────────────────────────────────────────────────────────


def test_candidate_preview_carries_market_response_and_one_ticker_reads(
    seeded: TestClient,
) -> None:
    market = seeded.get("/market/topn/latest", params=LIST_PARAMS).json()
    cand = next(c for c in market["candidates"] if c["ticker"] == CAND)
    body = _preview(seeded, "candidate", CAND, **LIST_PARAMS)
    assert body["status"] == "ok"
    text = body["preview_text"]
    stm = cand["short_term_momentum"]
    for n in (5, 10, 20):
        assert f"{n}저장일 {_pct(stm[f'return_{n}d_pct'])}" in text
    assert SHORT_NOTE_CANDIDATE in text
    one = cand["returns"]["one_month"]
    assert (
        f"1개월 {_pct(one['return_pct'])} ({one['price_start_date']} → {one['price_end_date']})"
        in text
    )
    sp = cand["same_period_kodex200"]["one_month"]
    assert sp["status"] == "ok"
    assert (
        f"1개월 {_pct(sp['diff_pctp'], '%p')} (후보 {_pct(sp['candidate_return_pct'])}"
        in text
    )
    assert SAME_PERIOD_LIMIT in text
    assert f"현재 목록 {cand['rank']}위(1개월 기준)" in text
    # 선택 1종목 추가 읽기 = POC5-09 · 16 함수 그대로.
    db = api_market_topn.DEFAULT_DB_PATH
    sv = build_stored_volume_evidence(CAND, db_path=db)
    rows = load_recent_price_rows([CAND], db_path=db)
    pv = build_price_volatility(
        [{"ticker": CAND, "price_dates": {"end_date": rows[CAND][0][0]}}],
        reference_date=rows[KODEX][0][0],
        db_path=db,
    )[CAND]
    assert sv.asof_date == "2026-10-14" and sv.volume is not None
    assert f"2026-10-14 거래량 {sv.volume:,}주" in text
    assert f"평균 대비 {intl_fixed(sv.ratio, 2)}배" in text
    assert pv.status == "ok"
    assert f"최근 20구간 {pv.recent.value_pct:.2f}%" in text
    # REJECT 된 참고점수 · 폐기 스냅샷 고점 대비는 넣지 않는다(판정 Q4 (a)).
    assert "참고점수" not in text and "고점 대비" not in text


def test_candidate_overlap_compares_real_etf_constituents(seeded: TestClient) -> None:
    text = _preview(seeded, "candidate", CAND, **LIST_PARAMS)["preview_text"]
    assert "직접 보유: 없음" in text
    # 보유 ETF 3개(개별 종목 제외) 중 구성종목 있는 2개만 비교 · 기준일 양쪽.
    assert (
        "보유 ETF 와 구성종목 중복(Top 10 기준): 비교 가능 2/3개 · 후보 구성종목 2026-10-02"
        in text
    )
    # 공통 = 삼성전자 · SK하이닉스 → min(25,20) + min(5,10) = 25.00%.
    assert (
        f"보유 반도체 ETF({HELD_ETF} · 2026-06-22): 공통 2종목 · 비중 중복률 25.00%"
        in text
    )
    # 공통 종목이 없는 쌍은 그 쌍의 결과로만 적는다(전체 '중복 없음' 아님 · 0% 로 쓰지 않음).
    assert "상위 10 공통 종목이 없는 쌍: 1개(그 쌍만의 결과)" in text
    assert "보유 해외 ETF(" not in text
    assert "구성종목 자료가 없는 보유 ETF 1개는 비교하지 않음" in text
    assert OVERLAP_LIMIT in text
    assert "중복 없음" not in text


def test_candidate_without_constituents_is_not_compared(seeded: TestClient) -> None:
    text = _preview(seeded, "candidate", CAND_NO_CONS, **LIST_PARAMS)["preview_text"]
    assert (
        "보유 ETF 와 구성종목 중복: 비교하지 않음 — 이 후보의 구성종목 자료가 저장돼 있지 않습니다(중복 없음이라는 뜻 아님)."
        in text
    )
    assert "비교 가능" not in text


def test_candidate_directly_held_is_separate_from_overlap(seeded: TestClient) -> None:
    market = seeded.get("/market/topn/latest", params=LIST_PARAMS).json()
    assert HELD_ETF in [c["ticker"] for c in market["candidates"]]
    text = _preview(seeded, "candidate", HELD_ETF, **LIST_PARAMS)["preview_text"]
    assert "직접 보유: 있음(이미 보유 중)" in text
    # 자기 자신과는 비교하지 않는다 → 나머지 보유 ETF 2개(구성종목 없음 1 · 공통 없음 1).
    assert "보유 ETF 와 구성종목 중복(Top 10 기준): 비교 가능 1/2개" in text
    assert "상위 10 공통 종목이 없는 쌍: 1개(그 쌍만의 결과)" in text


def test_candidate_late_last_date_hides_volatility_and_keeps_own_volume_date(
    seeded: TestClient,
) -> None:
    """마지막 저장일이 PC 기준일(KODEX200)과 다른 후보 — 흔들림은 값 숨김(POC5-16 판정 그대로) ·
    거래량은 자기 날짜를 과거 저장 자료로 구분한다(POC5-09)."""
    text = _preview(seeded, "candidate", CAND_LATE, **LIST_PARAMS)["preview_text"]
    assert (
        "값 숨김 — 이 종목의 마지막 유효 가격일(2026-10-10)이 PC 가격 흐름 기준일(2026-10-14)과 다릅니다."
        in text
    )
    assert "최근 20구간" not in text
    assert "2026-10-10 거래량" in text
    assert "과거 저장 자료 · PC 비교 기준일은 2026-10-14" in text


def test_candidate_list_conditions_follow_the_screen(seeded: TestClient) -> None:
    # 화면 조건(개수 1)에서 1위가 아닌 종목 → 사유 · 다른 조건 값으로 채우지 않음.
    market = seeded.get("/market/topn/latest", params={**LIST_PARAMS, "n": 1}).json()
    top = market["candidates"][0]["ticker"]
    other = CAND_NO_CONS if top != CAND_NO_CONS else CAND
    body = _preview(seeded, "candidate", other, **{**LIST_PARAMS, "n": 1})
    assert body["status"] == "error"
    assert (
        body["message"]
        == "현재 목록 조건에서 이 후보를 찾지 못했습니다. 목록을 다시 불러온 뒤 시도하세요."
    )
    assert body.get("preview_text") is None
    ok = _preview(seeded, "candidate", top, **{**LIST_PARAMS, "n": 1})
    assert ok["status"] == "ok"
    # 3개월 기준 요청은 3개월 목록에서 찾는다.
    m3 = seeded.get(
        "/market/topn/latest", params={**LIST_PARAMS, "basis": "three_month"}
    ).json()
    c3 = m3["candidates"][0]
    b3 = _preview(
        seeded, "candidate", c3["ticker"], **{**LIST_PARAMS, "basis": "three_month"}
    )
    assert f"현재 목록 {c3['rank']}위(3개월 기준)" in b3["preview_text"]
    # 이전 요청 모양(조건 없음) = 기존 기본 조건.
    old = _preview(seeded, "candidate", CAND)
    assert old["status"] == "ok" and "(1개월 기준)" in old["preview_text"]
    # 잘못된 조건 → 짧은 실패(목록을 계산하지 않음).
    bad = _preview(seeded, "candidate", CAND, basis="weekly")
    assert bad["status"] == "error"
    assert (
        bad["message"] == "판단 근거 미리보기를 생성하지 못했습니다. 다시 시도하세요."
    )


def test_preview_has_no_side_effects(
    seeded: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    import FinanceDataReader as fdr

    from app import holdings as holdings_mod
    from app import store

    calls: list = []
    monkeypatch.setattr(fdr, "DataReader", lambda *a, **k: calls.append(a))
    monkeypatch.setattr(store, "save", lambda *a, **k: calls.append(a))
    before = holdings_mod.HOLDINGS_FILE.read_bytes()
    for kind, tk in (("holding", HELD_ETF), ("candidate", CAND)):
        assert (
            _preview(seeded, kind, tk, **(LIST_PARAMS if kind == "candidate" else {}))[
                "status"
            ]
            == "ok"
        )
    assert calls == []
    assert holdings_mod.HOLDINGS_FILE.read_bytes() == before


def test_sources_read_only_one_candidate_window(
    seeded: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """후보 추가 읽기는 선택 종목 하나(+ KODEX200) 뿐이다(판정 Q2 (a))."""
    seen: list[list[str]] = []
    real = decision_preview_sources.load_recent_price_rows

    def spy(tickers, **kw):
        seen.append(list(tickers))
        return real(tickers, **kw)

    monkeypatch.setattr(decision_preview_sources, "load_recent_price_rows", spy)
    assert _preview(seeded, "candidate", CAND, **LIST_PARAMS)["status"] == "ok"
    assert seen == [[CAND]]


# ── 검토 r1 보강: NAV 값 · 국면 줄 · 묶음 수 · 정렬 방향 · 목록 실패 ─────────────────


def _sections(text: str) -> list[str]:
    secs = text.split("\n\n")
    assert all(sec.startswith("[") for sec in secs)
    return [sec.split("\n", 1)[0] for sec in secs]


def test_real_previews_have_eight_bundles_and_regime_from_each_screen(
    seeded: TestClient,
) -> None:
    ev = seeded.get("/holdings/market-evidence/latest").json()
    market = seeded.get("/market/topn/latest", params=LIST_PARAMS).json()
    titles = [
        "[대상]",
        "[시장]",
        "[가격 흐름 · PC 저장 종가]",
        "[KODEX200 동일 기간 비교]",
        "[거래량]",
        "[가격 흔들림]",
        "[중복 · 자료 상태]",
        "[AI에게 요청]",
    ]
    h = _preview(seeded, "holding", HELD_ETF)["preview_text"]
    c = _preview(seeded, "candidate", CAND, **LIST_PARAMS)["preview_text"]
    assert _sections(h) == titles and _sections(c) == titles
    # 국면 = 각 화면 응답 그대로 · 날짜 = KODEX200 최신 저장일(보유 = PC 비교 기준일).
    mp = ev["judgment_summary"]["market_position"]
    ref = ev["price_basis"]["reference_date"]
    more = " 이상" if mp["regime_streak_at_least"] else ""
    assert mp["available"] is True
    assert (
        f"시장 국면: {mp['regime_label']} · {mp['regime_streak_days']}거래일째{more} "
        f"(KODEX200 {ref} 기준)"
    ) in h
    mc = market["market_context"]
    rs = mc["regime_streak"]
    more_c = " 이상" if rs["at_least"] else ""
    assert (
        f"시장 국면: {mc['regime_label']} · {rs['streak_days']}거래일째{more_c} "
        f"(KODEX200 {mc['asof']} 기준)"
    ) in c
    assert mc["asof"] == ref


def test_nav_values_ok_and_partial_with_korean_flag(seeded: TestClient) -> None:
    ev = seeded.get("/holdings/market-evidence/latest").json()
    nav = next(h for h in ev["holdings"] if h["ticker"] == HELD_ETF)["nav_discount"]
    assert nav["status"] == "ok" and nav["flag"] == "discount_check_needed"
    h = _preview(seeded, "holding", HELD_ETF)["preview_text"]
    assert (
        "NAV 괴리율 +3.50% (NAV 100 · 시장가 104 · 2026-10-14) "
        "— 괴리율 절대값 3% 이상 · 확인 필요"
    ) in h
    c = _preview(seeded, "candidate", CAND, **LIST_PARAMS)["preview_text"]
    # 부분 자료도 값은 보이되 '부분 자료'를 숨기지 않는다(「확인 근거」와 같은 규칙).
    assert (
        "NAV 괴리율 -0.40% (NAV 50 · 시장가 50 · 2026-10-13) — 부분 자료 · 이전 자료 사용"
    ) in c
    for code in (
        "discount_check_needed",
        "discount_warning",
        "daily_surge",
        "daily_drop",
    ):
        assert code not in h and code not in c


def test_ascending_list_rank_says_low_order(seeded: TestClient) -> None:
    asc = {**LIST_PARAMS, "order": "asc"}
    market = seeded.get("/market/topn/latest", params=asc).json()
    first = market["candidates"][0]
    text = _preview(seeded, "candidate", first["ticker"], **asc)["preview_text"]
    assert f"현재 목록 {first['rank']}위(1개월 기준 · 낮은 순)" in text


def test_market_list_failure_is_not_reported_as_not_in_list(
    seeded: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = decision_preview_sources.get_market_topn_latest

    def broken(**kw):
        resp = real(**kw)
        return resp.model_copy(update={"status": "missing", "candidates": []})

    monkeypatch.setattr(decision_preview_sources, "get_market_topn_latest", broken)
    body = _preview(seeded, "candidate", CAND, **LIST_PARAMS)
    assert body["status"] == "error"
    assert (
        body["message"] == "판단 근거 미리보기를 생성하지 못했습니다. 다시 시도하세요."
    )


def test_holding_regime_date_is_kodex200_not_table_max(seeded: TestClient) -> None:
    """보유 근거 API 의 판정 날짜(`market_asof`)는 저장 가격 표 전체 최신일(개별 종목 10-15)일 수 있다 —
    미리보기는 KODEX200 최신 저장일(PC 비교 기준일 10-14)을 적는다(검토 r1)."""
    ev = seeded.get("/holdings/market-evidence/latest").json()
    assert ev["judgment_summary"]["market_position"]["market_asof"] == "2026-10-15"
    assert ev["price_basis"]["reference_date"] == "2026-10-14"
    text = _preview(seeded, "holding", HELD_ETF)["preview_text"]
    assert "(KODEX200 2026-10-14 기준)" in text
    assert "2026-10-15 기준" not in text


def test_holding_overlap_zero_match_is_scoped_not_none(seeded: TestClient) -> None:
    """구성종목은 있지만 반복 종목과 일치 0건 — '없음'이 아니라 비교 범위 한정으로 적는다(검토 r1)."""
    ev = seeded.get("/holdings/market-evidence/latest").json()
    ov = next(h for h in ev["holdings"] if h["ticker"] == HELD_ETF_OTHER)[
        "constituents_overlap"
    ]
    assert ov == {"status": "ok", "overlap_with_market_core": []}
    text = _preview(seeded, "holding", HELD_ETF_OTHER)["preview_text"]
    assert (
        f"{HOLDING_OVERLAP_SCOPE}: 일치 0건(비교 범위 한정 · 겹침이 없다는 뜻 아님) "
        "· 이 ETF 구성종목 2026-06-19"
    ) in text
    assert HOLDING_OVERLAP_LIMIT in text
    assert "없음" not in text.split("[중복 · 자료 상태]")[1].split("[AI에게 요청]")[
        0
    ].replace("겹침이 없다는 뜻 아님", "").replace("NAV 괴리율: 자료 없음", "")


# ── 검증자 r1 P2 정정: 숫자 글 = 화면(JS) 규칙 ─────────────────────────────────


@pytest.mark.parametrize(
    "fn, value, expected",
    [
        # chartScale.fmtExact — 2026-10-18 node 실측(저장 거래량 · 줄이지 않음).
        (fmt_exact, 0.0000001, "0.0000001"),
        (fmt_exact, 3e-7, "0.0000003"),
        (fmt_exact, 0.4, "0.4"),
        (fmt_exact, 0, "0"),
        (fmt_exact, 4655670, "4,655,670"),
        (fmt_exact, 1234567.1234565, "1,234,567.123457"),
        (fmt_exact, 0.1234565, "0.123457"),
        (fmt_exact, 0.000123456789, "0.000123457"),
        (fmt_exact, 0.9999999, "1"),
        (fmt_exact, 12.5, "12.5"),
        (fmt_exact, 5.0000005, "5.000001"),
        (fmt_exact, 2.0000025, "2.000003"),
        # toLocaleString("ko-KR", 소수 둘째 고정) — 거래량 평균 · 배수.
        (lambda v: intl_fixed(v, 2), 1.125, "1.13"),
        (lambda v: intl_fixed(v, 2), 2.675, "2.68"),
        (lambda v: intl_fixed(v, 2), 1.005, "1.01"),
        (lambda v: intl_fixed(v, 2), 3463997.8, "3,463,997.80"),
        (lambda v: intl_fixed(v, 2), 1234.565, "1,234.57"),
        # toFixed — %, %p · 흔들림 · 비중 · 하락 구간(실제 이진값 기준).
        (lambda v: to_fixed(v, 2), 0.125, "0.13"),
        (lambda v: to_fixed(v, 2), -1.125, "-1.13"),
        (lambda v: to_fixed(v, 2), 2.675, "2.67"),
        (lambda v: to_fixed(v, 2), 1.005, "1.00"),
        (lambda v: to_fixed(v, 2), -0.001, "-0.00"),
        (lambda v: to_fixed(v, 2), 32.1304, "32.13"),
        (lambda v: to_fixed(v, 1), 0.25, "0.3"),
        (lambda v: to_fixed(v, 1), 1.15, "1.1"),
        # Math.round(v).toLocaleString("ko-KR") — NAV · 시장가.
        (math_round_grouped, 102.5, "103"),
        (math_round_grouped, 35036.5, "35,037"),
        (math_round_grouped, 0.49999999999999994, "0"),
        (math_round_grouped, 1234567.5, "1,234,568"),
        # 검증자 r2 — 극단값(2026-10-18 node 실측): 큰 값 · 음수 0 · 숫자 아님 · 무한대.
        (fmt_exact, 1e22, "10,000,000,000,000,000,000,000"),
        (fmt_exact, 123456789012345678901234, "123,456,789,012,345,690,000,000"),
        (fmt_exact, -0.0, "-0"),
        (fmt_exact, -0.0000001, "-0.0000001"),
        (fmt_exact, float("nan"), "NaN"),
        (fmt_exact, float("inf"), "∞"),
        (lambda v: intl_fixed(v, 2), 1e22, "10,000,000,000,000,000,000,000.00"),
        (lambda v: intl_fixed(v, 2), -0.0, "-0.00"),
        (lambda v: intl_fixed(v, 2), -0.004, "-0.00"),
        (lambda v: intl_fixed(v, 2), float("-inf"), "-∞"),
        (lambda v: to_fixed(v, 2), 1e21, "1e+21"),
        (lambda v: to_fixed(v, 2), 1.5e21, "1.5e+21"),
        (lambda v: to_fixed(v, 2), 9.99e20, "999000000000000000000.00"),
        (lambda v: to_fixed(v, 2), 123456789012345678901, "123456789012345683968.00"),
        (lambda v: to_fixed(v, 2), -0.0, "0.00"),
        (lambda v: to_fixed(v, 1), -0.0, "0.0"),
        (lambda v: to_fixed(v, 1), -0.001, "-0.0"),
        (lambda v: to_fixed(v, 2), float("nan"), "NaN"),
        (lambda v: to_fixed(v, 2), float("-inf"), "-Infinity"),
        (math_round_grouped, -0.4, "-0"),
        (math_round_grouped, -0.5, "-0"),
        (math_round_grouped, -0.6, "-1"),
        (math_round_grouped, 1e22, "10,000,000,000,000,000,000,000"),
        (math_round_grouped, float("inf"), "∞"),
        # 검증자 r3 — 반올림한 double 을 Intl 처럼(가장 짧은 십진 표현) · 2026-10-18 node 실측.
        (math_round_grouped, 1e23, "100,000,000,000,000,000,000,000"),
        (math_round_grouped, 2**60, "1,152,921,504,606,847,000"),
        (math_round_grouped, 12345678901234567890, "12,345,678,901,234,567,000"),
        (math_round_grouped, 123456789012345678, "123,456,789,012,345,680"),
        (math_round_grouped, 2**53 + 1, "9,007,199,254,740,992"),
    ],
)
def test_number_text_follows_screen_js_rules(fn, value, expected) -> None:
    assert fn(value) == expected


def _set_last_volume(db: Path, ticker: str, volume: float) -> None:
    rows = [r for r in _series_for(ticker) if r.date == "2026-10-14"]
    assert len(rows) == 1
    r = rows[0]
    upsert_daily_prices(
        [
            EtfDailyPriceRow(
                r.ticker, r.date, r.open, r.high, r.low, r.close, volume, r.change
            )
        ],
        source="FinanceDataReader",
        db_path=db,
    )


def test_tiny_stored_volume_is_not_shown_as_zero(seeded: TestClient) -> None:
    """검증자 r1 P2 재현 — 유효한 작은 양수 거래량(0.0000001)은 화면처럼 그대로(0 과 구분)."""
    db = api_market_topn.DEFAULT_DB_PATH
    for tk, vol in (
        (HELD_ETF_OTHER, 0.0000001),
        (CAND_NO_CONS, 0.0000001),
        (HELD_ETF_NO_CONS, 0),
    ):
        _set_last_volume(db, tk, vol)
    h = _preview(seeded, "holding", HELD_ETF_OTHER)["preview_text"]
    c = _preview(seeded, "candidate", CAND_NO_CONS, **LIST_PARAMS)["preview_text"]
    z = _preview(seeded, "holding", HELD_ETF_NO_CONS)["preview_text"]
    assert "2026-10-14 거래량 0.0000001주" in h
    assert "2026-10-14 거래량 0.0000001주" in c
    assert "2026-10-14 거래량 0주" in z
    assert "거래량 0주" not in h and "거래량 0주" not in c


def test_zero_sign_follows_the_screen_where_the_value_appears() -> None:
    """0 의 부호 — 「보유와 비교」 · 「확인 근거」 값은 '+0.00%', 동일 기간 · 시장 위험 참고는 '0.00%'."""
    from app.decision_preview_lines import fmt_pct

    assert fmt_pct(0.0, plus_zero=True) == "+0.00%"
    assert fmt_pct(0.0, "%p", plus_zero=True) == "+0.00%p"
    assert fmt_pct(0.0) == "0.00%"
    assert (
        fmt_pct(-0.001, plus_zero=True) == "-0.00%"
    )  # JS: v >= 0 거짓 · toFixed '-0.00'
    assert fmt_pct(0.125) == "+0.13%"
    assert fmt_pct(None) == "미확인"


def test_extreme_number_text_lengths_match_screen() -> None:
    """double 의 끝 값도 정밀도 부족 없이 글로(node 실측 글 길이 · 1e300 = 401자 · 5e-324 = 326자)."""
    assert len(fmt_exact(1e300)) == 401 and fmt_exact(1e300).startswith("1,000,000")
    s = fmt_exact(5e-324)
    assert len(s) == 326 and s.startswith("0.000") and s.endswith("0005")
    assert to_fixed(1e300, 2) == "1e+300"


def test_huge_stored_volume_keeps_the_preview(seeded: TestClient) -> None:
    """검증자 r2 P2 재현 — 저장 거래량 1e22(유효 · 유한)에서도 보유 · 후보 미리보기 전체가 나온다."""
    db = api_market_topn.DEFAULT_DB_PATH
    for tk in (HELD_ETF_OTHER, CAND_NO_CONS):
        _set_last_volume(db, tk, 1e22)
    h = seeded.post(PREVIEW, json={"target_kind": "holding", "ticker": HELD_ETF_OTHER})
    c = seeded.post(
        PREVIEW,
        json={"target_kind": "candidate", "ticker": CAND_NO_CONS, **LIST_PARAMS},
    )
    for res in (h, c):
        assert res.status_code == 200
        body = res.json()
        assert body["status"] == "ok"
        assert (
            "2026-10-14 거래량 10,000,000,000,000,000,000,000주" in body["preview_text"]
        )
        assert len(body["preview_text"].split("\n\n")) == 8


def test_negative_zero_decline_value_matches_screen() -> None:
    """검증자 r2 P3 — 정규화된 20저장일 -0.0 은 화면(toFixed)처럼 '0.0%'."""
    from app.decision_preview_lines import holding_flow_lines

    item = {
        "price_dates": {
            "end_date": "2026-10-14",
            "start_date_20d": "2026-09-10",
            "comparison": "ok",
        },
        "short_term_momentum": {
            "status": "ok",
            "return_5d_pct": -0.004,
            "return_10d_pct": 0.0,
            "return_20d_pct": -0.01,
            "excess_vs_kodex200_5d_pctp": -0.0,
            "excess_vs_kodex200_10d_pctp": None,
            "excess_vs_kodex200_20d_pctp": 0.2,
        },
        "decline_band": {
            "judgeable": True,
            "state": None,
            "label": None,
            "return_20d_pct_1dp": -0.0,
            "unjudged_reason": None,
        },
    }
    lines = holding_flow_lines(item, "2026-10-14")
    assert "PC 20저장일 하락 구간: 해당 없음 (20저장일 0.0%)" in lines
    # 「보유와 비교」 상세 규칙(v >= 0 → '+') · toFixed: -0.004 → '-0.00' · -0.0 → '+0.00'.
    assert lines[0].startswith(
        "변화율 5저장일 -0.00% · 10저장일 +0.00% · 20저장일 -0.01%"
    )
    assert "5저장일 +0.00%p · 10저장일 시작일 달라 비움 · 20저장일 +0.20%p" in lines[1]


def test_text_build_error_returns_short_failure_not_500(
    seeded: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """검증자 r2 — 글 조립 단계 예외도 로더와 같은 짧은 실패 응답(HTTP 200 · 내부 정보 없음)."""

    def boom(**kw):
        raise ArithmeticError("simulated format failure")

    monkeypatch.setattr(api_decision_draft_preview, "build_preview_text", boom)
    res = seeded.post(PREVIEW, json={"target_kind": "holding", "ticker": HELD_ETF})
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "error"
    assert (
        body["message"] == "판단 근거 미리보기를 생성하지 못했습니다. 다시 시도하세요."
    )
    assert "simulated" not in str(body)


def test_huge_nav_is_written_like_the_screen(seeded: TestClient) -> None:
    """검증자 r3 재현 — NAV · 시장가 1e23 은 화면처럼 '100,000,000,000,000,000,000,000'(보유 · 후보)."""
    db = api_market_topn.DEFAULT_DB_PATH
    upsert_nav_rows(
        [
            NavDailyRow(
                HELD_ETF_OTHER, "2026-10-14", 1e23, 1e23, 0.0, "naver", "ok", None
            ),
            NavDailyRow(
                CAND_NO_CONS, "2026-10-14", 1e23, 1e23, 0.0, "naver", "ok", None
            ),
        ],
        db_path=db,
    )
    big = "100,000,000,000,000,000,000,000"
    h = _preview(seeded, "holding", HELD_ETF_OTHER)["preview_text"]
    c = _preview(seeded, "candidate", CAND_NO_CONS, **LIST_PARAMS)["preview_text"]
    for text in (h, c):
        assert f"NAV 괴리율 +0.00% (NAV {big} · 시장가 {big} · 2026-10-14)" in text
        assert "99,999,999,999,999,991,611,392" not in text


_JS_RULES = r"""
const fs = require("fs");
const vals = JSON.parse(fs.readFileSync(process.argv[1])).map(Number);
function fmtExact(v){
  if (v!==0 && Math.abs(v)<1) return v.toLocaleString("ko-KR",{maximumSignificantDigits:6});
  return v.toLocaleString("ko-KR",{minimumFractionDigits:0, maximumFractionDigits:6}); }
const TWO={minimumFractionDigits:2,maximumFractionDigits:2};
process.stdout.write(JSON.stringify(vals.map(v => [v.toFixed(2), v.toFixed(1),
  v.toLocaleString("ko-KR",TWO), fmtExact(v), Math.round(v).toLocaleString("ko-KR")])));
"""


@pytest.mark.skipif(
    shutil.which("node") is None, reason="화면 JS 대조에는 node 가 필요하다"
)
def test_number_rules_match_browser_js_on_random_doubles(tmp_path: Path) -> None:
    """화면 helper 와 같은 JS 식(chartScale.fmtExact · storedVolume · toFixed · Math.round)을 node 로 실행해
    무작위 double(크기 · 반올림 경계 · 큰 정수 · 임의 비트 패턴)에서 글이 모두 같은지 본다(검증자 r1 ~ r3)."""
    rnd = random.Random(523)
    vals: list[float] = [0.0, -0.0, 5e-324, 1.7976931348623157e308, 1e23, 2.675, 1.005]
    for _ in range(1500):
        v = rnd.random() * 10 ** rnd.randint(-30, 30)
        vals.append(-v if rnd.random() < 0.3 else v)
    for _ in range(800):
        vals.append((rnd.randint(-(10**6), 10**6) + 0.5) / 10 ** rnd.randint(1, 7))
    for _ in range(500):
        n = float(rnd.randint(1, 9) * 2 ** rnd.randint(0, 70))
        vals += [n, n + 0.5, -n - 0.5]
    for _ in range(500):
        v = struct.unpack("d", struct.pack("Q", rnd.getrandbits(64)))[0]
        if v == v and abs(v) != float("inf"):
            vals.append(v)
    src = tmp_path / "vals.json"
    src.write_text(json.dumps([repr(v) for v in vals]))
    out = subprocess.run(
        ["node", "-e", _JS_RULES, str(src)], capture_output=True, text=True, check=True
    ).stdout
    expected = json.loads(out)
    mismatch = [
        (repr(v), mine, js)
        for v, row in zip(vals, expected)
        for mine, js in zip(
            [
                to_fixed(v, 2),
                to_fixed(v, 1),
                intl_fixed(v, 2),
                fmt_exact(v),
                math_round_grouped(v),
            ],
            row,
        )
        if mine != js
    ]
    assert len(expected) == len(vals)
    assert mismatch == []
