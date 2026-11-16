"""POC6-31 STEP 4 ~ 5 — 보유와 후보의 구성종목 비교 · 같은 근거로만 미리보기(PLAN C21 ~ C27).

계약 문장 → 시험:
- C21 짝 비중 · 전체 보유 노출(Σ 평가 비중 × 편입 비중 + 직접 보유) · 노출 합계일 = 보유에서 확인된 가장 최근 실제 구성일 ·
  다른 날짜는 참고 · 확인 범위 먼저 · '0(확인)' ↔ '저장 범위에서 미확인' · 계산 입력 자릿수 그대로 · 합계 뒤 한 번 반올림 ·
  근거 지문 · 후보 보유 표시 · 금액 없음(%만).
- C25 미리보기는 화면이 받은 지문과 다시 계산한 지문이 같을 때만(같은 날 수치 · 시세만 바뀌어도 잡음).
- C26 '[구성종목 비교]' 묶음 · 역할별 기준일 3칸.
라이브 DB · 외부 호출 0(임시 DB · 시세 캐시 바꿔 끼움).
"""

from __future__ import annotations

import json
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app import api_decision_draft_preview as api_preview
from app import constituents_pair_exposure as P
from app import constituents_pair_exposure_io as IO
from app import constituents_pair_exposure_text as T
from app.etf_constituents_fetcher import NAVER_STOCK_SOURCE
from app.etf_constituents_status import LOG_OK
from app.etf_constituents_store import ConstituentRow, replace_constituents_snapshot
from tests.test_pc_price_basis import api_client  # noqa: F401 — fixture
from tests.test_poc5_23_decision_preview_bundles import (  # noqa: F401 — fixture
    CAND,
    HELD_ETF,
    HELD_ETF_NO_CONS,
    HELD_ETF_OTHER,
    LIST_PARAMS,
    PREVIEW,
    STOCK,
    seeded,
)

COND = P.condition_of(
    screen="holding_candidate_compare",
    basis="one_month",
    side="top",
    rank=4,
    start_date="2026-10-14",
    end_date="2026-11-13",
    filters={
        "exclude_inverse": True,
        "exclude_leveraged": True,
        "exclude_synthetic": True,
        "exclude_futures": True,
    },
)
PRICE_DATE = {"state": "KNOWN", "min": "2026-11-13", "max": "2026-11-13"}


# ── 단위: 저장 행 · 보유 비중 꾸러미 ──────────────────────────────────────────


def kr(rank, code, name, w):
    """국내 주식 행(칸 순서 = 상태 모듈 ROW_SQL)."""
    return (rank, code, name, w, "E", code, f"KR7{code}003", None, "0")


def us(rank, key, name, w):
    """해외 주식 행."""
    return (rank, None, name, w, "E", key, f"US{key[:3]}0000001", None, "2")


def filler(start, n, w=1.0):
    return [kr(i, f"9{i:05d}", f"채움{i}", w) for i in range(start, start + n)]


def conf(asof, rows, complete=False):
    """원천일 확인된 구성 · complete = 확인 기록 끝 '원천 전체' 표시(수집 작업이 남김 · 검토 지적 backend#0)."""
    return {
        "confirmed": {
            "asof": asof,
            "rows": len(rows),
            "data": rows,
            "complete": complete,
        },
        "latest": None,
    }


def unconf(asof, n):
    return {"confirmed": None, "latest": {"asof": asof, "rows": n}}


def item(t, w, etf=True, name=None):
    return {
        "ticker": t,
        "name": name or f"보유{t}",
        "weight": None if w is None else Decimal(w),
        "etf": etf,
    }


def hw(items, rows=None, priced=None):
    return {
        "items": items,
        "rows": rows if rows is not None else len(items),
        "priced_rows": (
            priced
            if priced is not None
            else sum(1 for i in items if i["weight"] is not None)
        ),
        "denominator": any(i["weight"] is not None for i in items),
    }


LLY = ("LLY.N", "일라이 릴리")
NVO = ("NVO.N", "노보 노디스크 ADR")
SAMSUNG = ("005930", "삼성전자")


def base_snaps():
    return {
        "C": conf(
            "2026-11-13",
            [
                us(1, *LLY, 29.98),
                us(2, *NVO, 20.92),
                kr(3, *SAMSUNG, 6.37),
                (4, None, "원화현금", 1.0, "E", None, "KRD010010001", None, None),
            ],
        ),
        # 30행(요청 깊이) — 그 밖은 '저장 범위에서 미확인'
        "A": conf("2026-11-13", [us(1, *LLY, 3.12), *filler(2, 29)]),
        # 12행 · 원천 전체 표시 — 없는 주식 = '0(확인)'
        "B": conf("2026-11-13", [kr(1, *SAMSUNG, 9.8), *filler(2, 11)], complete=True),
        # 다른 구성일(참고)
        "R": conf("2026-11-12", [us(1, *LLY, 2.10)]),
        # 원천 기준일 미확인(보존 자료)
        "U": unconf("2026-06-22", 10),
        # 예전 10행 — 그 밖 미확인
        "L": conf("2026-11-13", filler(1, 10)),
    }


def base_hw():
    return hw(
        [
            item("A", "12.0000"),
            item("B", "8.5000"),
            item("L", "40.0000"),
            item("R", "3.1000"),
            item("U", "3.2000"),
            item("N", "2.5000"),  # 구성 자료 없음
            item("005930", "6.2000", etf=False, name="삼성전자"),
            item("X", "24.5000"),  # 구성 자료 없음
            item("Q", None),  # 시세 미확인
        ],
        rows=10,
        priced=9,
    )


ETFS = {"C", "A", "B", "R", "U", "N", "L", "X", "Q"}


def build(**kw):
    args = dict(
        candidate="C",
        holding="A",
        condition=COND,
        hw=base_hw(),
        price_date=PRICE_DATE,
        names={"C": "후보C"},
        etf_tickers=ETFS,
        snaps=base_snaps(),
    )
    args.update(kw)
    return P.build(**args)


def stock(body, name):
    return next(s for s in body["stocks"] if s["name"] == name)


@pytest.mark.parametrize(
    "n,complete,want",
    [
        (12, True, P.RANGE_FULL),
        (10, True, P.RANGE_FULL),  # 원천이 10개만 준 것이 확인된 경우
        (1, False, P.RANGE_UNVERIFIED),
        (
            12,
            False,
            P.RANGE_UNVERIFIED,
        ),  # 표시 없는 기록 · 버린 항목 — 행 수만으로 원천 전체라 하지 않음
        (29, False, P.RANGE_UNVERIFIED),
        (10, False, P.RANGE_LEGACY),
        (30, False, P.RANGE_DEPTH),
        (31, False, P.RANGE_DEPTH),
    ],
)
def test_stored_range_needs_source_complete_mark(n, complete, want):
    assert P.stored_range(n, complete) == want


def test_exposure_sum_rounds_once_and_keeps_input_digits():
    b = build()
    assert b["status"] == P.STATUS_OK
    sam = stock(b, "삼성전자")
    # B 8.5% × 9.8% = 0.833 + 직접 보유 6.2% = 7.033 → 7.03(합계 뒤 한 번)
    assert sam["exposure"]["terms"] == [
        {
            "ticker": "B",
            "name": "보유B",
            "holding_weight": "8.5",
            "constituent_weight": "9.8",
            "product": "0.833",
        }
    ]
    assert sam["exposure"]["direct"] == [
        {"ticker": "005930", "name": "삼성전자", "weight": "6.2"}
    ]
    assert (sam["exposure"]["raw"], sam["exposure"]["value"]) == ("7.033", "7.03")
    lly = stock(b, "일라이 릴리")
    assert (lly["exposure"]["raw"], lly["exposure"]["value"]) == ("0.3744", "0.37")


def test_half_up_once_after_sum_not_per_term():
    # 0.0049 + 0.0049 = 0.0098 → 0.01(항마다 반올림하면 0.00 + 0.00 = 0.00)
    snaps = {
        "C": conf("2026-11-13", [kr(1, *SAMSUNG, 10.0)]),
        "A": conf("2026-11-13", [kr(1, *SAMSUNG, 0.049)]),
        "B": conf("2026-11-13", [kr(1, *SAMSUNG, 0.049)]),
    }
    b = P.build(
        candidate="C",
        holding=None,
        condition=COND,
        hw=hw([item("A", "10.0000"), item("B", "10.0000"), item("Z", "80.0000")]),
        price_date=PRICE_DATE,
        names={},
        etf_tickers={"C", "A", "B", "Z"},
        snaps=snaps,
    )
    ex = stock(b, "삼성전자")["exposure"]
    assert (ex["raw"], ex["value"]) == ("0.0098", "0.01")


def test_confirmed_zero_vs_out_of_stored_range():
    b = build()
    nvo = stock(b, "노보 노디스크 ADR")
    # 고른 보유 A = 30행 → 그 밖 미확인(저장 행 합과 함께) · B(12행 원천 전체) = 0(확인) · L(예전 10행) = 미확인
    assert nvo["pair"] == {
        "state": P.PAIR_OUT_OF_RANGE,
        "stored_rows": 30,
        "stored_sum": "32.12",
    }
    assert nvo["exposure"]["zero_confirmed"] == ["B"]
    assert {u["ticker"]: u["range"] for u in nvo["exposure"]["unknown"]} == {
        "A": P.RANGE_DEPTH,
        "L": P.RANGE_LEGACY,
    }
    assert nvo["exposure"]["unknown_weight"] == "52"
    assert nvo["exposure"]["value"] == "0.00"
    lly = stock(b, "일라이 릴리")
    assert lly["pair"] == {"state": P.PAIR_FOUND, "weight": "3.12"}


def test_pair_states_for_unconfirmed_no_data_and_direct_stock():
    assert stock(build(holding="U"), "일라이 릴리")["pair"] == {
        "state": P.PAIR_UNCONFIRMED,
        "asof": "2026-06-22",
    }
    assert stock(build(holding="N"), "일라이 릴리")["pair"] == {"state": P.PAIR_NO_DATA}
    full = build(holding="B")
    assert stock(full, "일라이 릴리")["pair"] == {"state": P.PAIR_ZERO}
    # 고른 보유가 개별 주식 — 그 주식 자체 · 다른 주식은 해당 없음 · 전체 보유에서의 평가 비중은 따로
    st = build(holding="005930")
    assert stock(st, "삼성전자")["pair"] == {"state": P.PAIR_SELF}
    assert stock(st, "일라이 릴리")["pair"] == {"state": P.PAIR_NOT_APPLICABLE}
    assert st["holding"]["kind"] == "stock" and st["holding"]["weight"] == "6.2"
    # 고른 보유 없음(다른 화면) — 짝 칸 없음
    assert stock(build(holding=None), "삼성전자")["pair"] is None


def test_scope_first_sums_to_whole_and_lists_ranges():
    sc = build()["scope"]
    assert sc["included"] == {"count": 3, "weight": "60.5"}  # A · B · L (11/13)
    assert sc["direct"] == {"count": 1, "weight": "6.2"}
    assert sc["other_date"] == {"count": 1, "weight": "3.1", "dates": ["2026-11-12"]}
    assert sc["unconfirmed"] == {"count": 1, "weight": "3.2"}
    assert sc["no_data"] == {"count": 2, "weight": "27"}
    assert sc["no_weight"] == {"count": 1}
    total = sum(
        Decimal(sc[k]["weight"])
        for k in ("included", "direct", "other_date", "unconfirmed", "no_data")
    )
    assert total == Decimal("100")
    assert sc["ranges"] == {
        "depth": 1,
        "legacy": 1,
        "unverified": 0,
        "full": 1,
        "full_min": 12,
        "full_max": 12,
    }
    uses = {e["ticker"]: e["use"] for e in sc["etfs"]}
    assert uses == {
        "A": "sum",
        "B": "sum",
        "L": "sum",
        "R": "other_date",
        "U": "unconfirmed",
        "N": "no_data",
        "X": "no_data",
        "Q": "no_weight",
    }


def test_exposure_date_is_latest_confirmed_and_other_dates_are_reference():
    b = build()
    assert b["dates"] == {
        "candidate": "2026-11-13",
        "holding": "2026-11-13",
        "exposure": "2026-11-13",
    }
    assert stock(b, "일라이 릴리")["reference"] == [
        {
            "ticker": "R",
            "name": "보유R",
            "asof": "2026-11-12",
            "holding_weight": "3.1",
            "constituent_weight": "2.1",
            "product": "0.0651",
        }
    ]
    # 다른 구성일은 합계에 넣지 않는다
    assert all(t["ticker"] != "R" for t in stock(b, "일라이 릴리")["exposure"]["terms"])


def test_no_confirmed_etf_shows_direct_holding_only():
    snaps = {"C": base_snaps()["C"], "U": unconf("2026-06-22", 10)}
    b = P.build(
        candidate="C",
        holding=None,
        condition=COND,
        hw=hw(
            [
                item("U", "50.0000"),
                item("005930", "50.0000", etf=False, name="삼성전자"),
            ]
        ),
        price_date=PRICE_DATE,
        names={},
        etf_tickers={"C", "U"},
        snaps=snaps,
    )
    assert b["dates"]["exposure"] is None
    assert stock(b, "삼성전자")["exposure"]["value"] == "50.00"
    assert stock(b, "일라이 릴리")["exposure"]["value"] == "0.00"
    lines = T.preview_lines(b)
    assert "노출 합계 구성 자료 없음(직접 보유만)" in lines[0]


def test_candidate_top_ten_rows_only_and_non_stock_rows_counted():
    rows = [
        (1, None, "원화현금", 5.0, "E", None, "KRD010010001", None, None),
        *[kr(i, f"1{i:05d}", f"주식{i}", 1.0) for i in range(2, 11)],
        kr(11, *SAMSUNG, 0.5),  # 11행 — 후보 주요 주식(원본 1 ~ 10행) 밖
    ]
    b = build(snaps={**base_snaps(), "C": conf("2026-11-13", rows)})
    assert b["candidate_top_rows"] == 10
    assert b["candidate_non_stock_rows"] == 1
    assert len(b["stocks"]) == 9
    assert all(s["name"] != "삼성전자" for s in b["stocks"])


def test_candidate_held_is_included_and_marked():
    snaps = base_snaps()
    h = base_hw()
    h["items"].append(item("C", "1.0000"))
    b = build(hw=h, snaps=snaps)
    assert b["candidate"]["held"] is True and b["candidate"]["held_use"] == "sum"
    lly = stock(b, "일라이 릴리")
    assert any(t["ticker"] == "C" for t in lly["exposure"]["terms"])
    assert (
        "후보를 이미 보유 중(평가 비중 1.00%) — 그 구성도 노출 합계에 들어 있음"
        in T.preview_lines(b)
    )


def test_no_holdings_and_no_etf_list_show_only_the_reason():
    b = build(hw=hw([]))
    assert b["status"] == P.STATUS_NO_HOLDINGS and b["stocks"] == []
    assert T.preview_lines(b) == [T.NO_HOLDINGS_LINE]
    # ETF 목록을 못 읽으면 보유 ETF 를 직접 보유로 셈하지 않는다(0.00% 로 보이지 않게 · 검토 지적 backend#5)
    b = build(etf_tickers=set())
    assert (
        b["status"] == P.STATUS_NO_ETF_LIST and b["stocks"] == [] and b["scope"] is None
    )
    assert T.preview_lines(b) == [T.NO_ETF_LIST_LINE]


@pytest.mark.parametrize(
    "kw,status,head",
    [
        ({"hw": None}, P.STATUS_HOLDINGS_UNREADABLE, T.HOLDINGS_UNREADABLE_LINE),
        (
            {"hw": hw([item("A", None)], rows=1, priced=0)},
            P.STATUS_NO_WEIGHT_BASIS,
            T.NO_WEIGHT_BASIS_LINE,
        ),
    ],
)
def test_no_weight_basis_keeps_pair_cells_and_hides_only_exposure(kw, status, head):
    # 분모(현금 제외 보유 평가액)가 없어도 후보 · 고른 보유의 편입 비중은 평가액과 무관 — 짝 칸은 보인다(검토 지적 frontend#2)
    b = build(**kw)
    assert b["status"] == status
    lly = stock(b, "일라이 릴리")
    assert lly["pair"] == {"state": P.PAIR_FOUND, "weight": "3.12"}
    assert lly["exposure"] is None and lly["reference"] == []
    lines = T.preview_lines(b)
    assert head in lines
    assert (
        "일라이 릴리: 후보 29.98% · 고른 보유 3.12% · 내 보유 전체 비중 확인 불가"
        in lines
    )
    assert "확인 범위:" not in "".join(lines)


def test_unpriced_newest_etf_does_not_become_exposure_date():
    # 시세 없는 ETF(분모 밖)의 더 늦은 구성일이 합계일이 되면 합산할 ETF 가 없어진다(검토 지적 backend#1)
    snaps = {
        "C": conf("2026-11-13", [kr(1, *SAMSUNG, 25.0)]),
        "A": conf("2026-11-13", [kr(1, *SAMSUNG, 25.0)], complete=True),
        "Q": conf("2026-11-14", [kr(1, *SAMSUNG, 50.0)], complete=True),
    }
    b = P.build(
        candidate="C",
        holding=None,
        condition=COND,
        hw=hw([item("A", "100.0000"), item("Q", None)], rows=2, priced=1),
        price_date=PRICE_DATE,
        names={},
        etf_tickers={"C", "A", "Q"},
        snaps=snaps,
    )
    assert b["dates"]["exposure"] == "2026-11-13"
    assert b["scope"]["included"] == {"count": 1, "weight": "100"}
    assert stock(b, "삼성전자")["exposure"]["value"] == "25.00"
    assert {e["ticker"]: e["use"] for e in b["scope"]["etfs"]} == {
        "A": "sum",
        "Q": "no_weight",
    }


@pytest.mark.parametrize(
    "use,snap,weight,text",
    [
        (
            "sum",
            None,
            "1.0000",
            "후보를 이미 보유 중(평가 비중 1.00%) — 그 구성도 노출 합계에 들어 있음",
        ),
        (
            "other_date",
            "2026-11-10",
            "1.0000",
            "후보를 이미 보유 중(평가 비중 1.00%) — 후보 구성일 2026-11-10이 노출 합계일과 달라 합계 밖(다른 구성일 참고)",
        ),
        (
            "no_weight",
            None,
            None,
            "후보를 이미 보유 중 — 시세 미확인이라 분모 밖 — 합계에 넣지 않음",
        ),
    ],
)
def test_held_candidate_reason_by_use(use, snap, weight, text):
    # 보유 중인 후보가 합계에 들어갔는지 · 빠진 사유를 쓰임별로(날짜 사유를 다른 경우에 쓰지 않음 · 검토 지적 backend#2)
    snaps = base_snaps()
    if snap:
        snaps["C"] = {
            "confirmed": {**snaps["C"]["confirmed"], "asof": snap},
            "latest": None,
        }
    h = base_hw()
    h["items"].append(item("C", weight))
    b = build(hw=h, snaps=snaps)
    assert b["candidate"]["held_use"] == use
    assert text in T.preview_lines(b)


def test_selected_stock_own_weight_is_in_saved_text():
    # 고른 보유가 개별 주식 — '이 주식 자체'와 전체 보유에서 차지하는 평가 비중을 글에도 나눠 적는다(검토 지적 backend#3)
    lines = T.preview_lines(build(holding="005930"))
    assert "고른 보유(삼성전자) 개별 주식 · 전체 보유 평가 비중 6.20%" in lines[0]
    assert any(
        ln.startswith(
            "삼성전자: 후보 6.37% · 고른 보유 이 주식 자체 · 내 보유 전체 7.03%"
        )
        for ln in lines
    )


def test_candidate_without_confirmed_data_is_not_compared():
    for snap, why in (
        (unconf("2026-06-22", 10), "원천 기준일 미확인(2026-06-22 보존 자료)"),
        (None, "구성 자료 없음"),
    ):
        snaps = base_snaps()
        if snap is None:
            snaps.pop("C")
        else:
            snaps["C"] = snap
        b = build(snaps=snaps)
        assert b["status"] == P.STATUS_NO_CANDIDATE_DATA and b["stocks"] == []
        assert (
            T.preview_lines(b)[-1]
            == f"후보 구성: {why} — 비교하지 않음(겹침 없음이라는 뜻 아님)."
        )
        # 확인 범위는 그대로 보인다(수치보다 먼저)
        assert T.preview_lines(b)[1].startswith("확인 범위: 보유 ETF 3개")


def test_dates_differ_is_reference_reading():
    snaps = base_snaps()
    snaps["C"] = {
        "confirmed": {**snaps["C"]["confirmed"], "asof": "2026-11-10"},
        "latest": None,
    }
    line = T.preview_lines(build(snaps=snaps))[0]
    assert "후보 구성 2026-11-10" in line and "노출 합계 2026-11-13" in line
    # 후보 ↔ 노출 합계 · 후보 ↔ 고른 보유(11/13) 둘 다 달라 두 참고 표시(검증자 STEP 4~5 r1 F12)
    assert line.endswith(
        "후보와 보유의 구성일이 달라 나란히 읽는 참고 수치 · "
        "고른 보유 비중은 구성일이 달라 나란히 읽는 참고 수치(구성일 다름 · 참고)"
    )
    # 고른 보유가 없으면 후보 ↔ 노출 합계 표시만
    line2 = T.preview_lines(build(snaps=snaps, holding=None))[0]
    assert line2.endswith("후보와 보유의 구성일이 달라 나란히 읽는 참고 수치")


def test_fingerprint_same_for_same_input_and_changes_on_each_input():
    fp = build()["fingerprint"]
    assert fp == build()["fingerprint"] and len(fp) == 64
    h = base_hw()
    h["items"][0]["weight"] = Decimal("12.0001")  # 같은 날 평가 비중만 0.0001%p
    snaps = base_snaps()
    snaps["B"] = conf("2026-11-13", [kr(1, *SAMSUNG, 9.81), *filler(2, 11)])
    other_cond = {**COND, "rank": 5}
    variants = [
        build(hw=h),
        build(snaps=snaps),  # 같은 날 편입 비중만
        build(condition=other_cond),
        build(holding="B"),
        build(price_date={**PRICE_DATE, "max": "2026-11-14"}),
        build(names={"C": "다른 이름"}),
    ]
    assert all(v["fingerprint"] != fp for v in variants)


def test_holding_weights_aggregate_accounts_and_unpriced_rows():
    class R:
        def __init__(self, t, e, name="n"):
            self.ticker, self.eval_amount, self.name = t, e, name

    out = P.holding_weights(
        [R("A", 100.0), R("A", 100.0), R("B", 100.0), R("C", 50.0), R("C", None)],
        {"A", "B", "C"},
    )
    w = {i["ticker"]: i["weight"] for i in out["items"]}
    # 분모 = 시세 있는 행 합 350(현금 제외) · 같은 종목 계좌 합산 · 한 행이라도 시세 없으면 그 종목 미확인
    assert w == {"A": Decimal("57.1429"), "B": Decimal("28.5714"), "C": None}
    assert (out["rows"], out["priced_rows"], out["denominator"]) == (5, 4, True)
    assert P.holding_weights([R("A", None)], {"A"})["denominator"] is False


def test_preview_lines_text_scope_first_and_no_amount():
    lines = T.preview_lines(build())
    assert lines[0] == (
        "기준일: 후보 구성 2026-11-13 · 고른 보유(보유A) 구성 2026-11-13 · 노출 합계 2026-11-13 · "
        "보유 평가 2026-11-13 · 현금 제외 · 부분 평가액 기준"
    )
    assert lines[1] == (
        "확인 범위: 보유 ETF 3개(평가액의 60.50%) + 직접 보유 1개(6.20%) 계산 · 빠짐 33.30%"
        "(다른 구성일 1개 3.10% · 원천 기준일 미확인 1개 3.20% · 구성 자료 없음 2개 27.00%)"
        " · 시세 미확인 1종목은 분모 밖(부분 평가액 기준)"
    )
    assert (
        "일라이 릴리: 후보 29.98% · 고른 보유 3.12% · 내 보유 전체 0.37%"
        "(저장 범위 밖 미확인 ETF 1개 · 평가액 40.00%)"
    ) in lines
    assert (
        "노보 노디스크 ADR: 후보 20.92% · 고른 보유 저장 범위에서 미확인(30행 · 저장 행 합 32.12%)"
        " · 내 보유 전체 0.00%(저장 범위 밖 미확인 ETF 2개 · 평가액 52.00%)"
    ) in lines
    assert "다른 구성일 참고(합계 밖): 보유R 2026-11-12 — 일라이 릴리 2.10%" in lines
    assert lines[-1] == T.AFTER_ADD_LINE
    assert "원" not in "".join(lines).replace("원천", "").replace("원본", "")


# ── 실제 API: 화면 GET ↔ 미리보기 대조(임시 DB · 시세 캐시 바꿔 끼움) ─────────────────


def _naver(etf, asof, items):
    return [
        ConstituentRow(
            etf_ticker=etf,
            asof=asof,
            source=NAVER_STOCK_SOURCE,
            rank=i + 1,
            constituent_ticker=code,
            constituent_name=name,
            weight_pct=w,
            constituent_key=code,
            constituent_isin=f"KR7{code}003",
            market_type="0",
        )
        for i, (code, name, w) in enumerate(items)
    ]


def _save(etf, asof, items):
    # 원천이 준 전체(원천 항목 수 < 30 · 버린 항목 없음) — 수집 작업과 같은 확인 기록 끝 표시
    replace_constituents_snapshot(
        _naver(etf, asof, items),
        log_status=LOG_OK,
        confirm=True,
        complete=True,
        db_path=api_preview.DEFAULT_DB_PATH,
    )


@pytest.fixture
def priced(seeded: TestClient, monkeypatch: pytest.MonkeyPatch) -> dict:  # noqa: F811
    from app import market_cache
    from app.market_cache import MarketQuote

    prices = {
        HELD_ETF: 100.0,
        HELD_ETF_NO_CONS: 100.0,
        STOCK: 100.0,
        HELD_ETF_OTHER: 100.0,
    }

    def quotes():
        return {
            t: MarketQuote(t, None, p, "2026-11-13T15:40:00+09:00")
            for t, p in prices.items()
        }

    monkeypatch.setattr(market_cache, "get_all", quotes)
    _save(
        CAND,
        "2026-11-13",
        [
            (STOCK, "삼성전자", 25.0),
            ("000660", "SK하이닉스", 5.0),
            ("240810", "원익IPS", 7.0),
        ],
    )
    _save(
        HELD_ETF,
        "2026-11-13",
        [(STOCK, "삼성전자", 20.0), ("000660", "SK하이닉스", 10.0)],
    )
    _save(HELD_ETF_OTHER, "2026-11-12", [(STOCK, "삼성전자", 3.0)])
    return prices


GET = "/market/constituents/pair-exposure"


def _get(client, holding=HELD_ETF, **extra):
    params = {
        "candidate": CAND,
        "basis": LIST_PARAMS["basis"],
        **{
            k: str(LIST_PARAMS[k]).lower()
            for k in (
                "exclude_inverse",
                "exclude_leveraged",
                "exclude_synthetic",
                "exclude_futures",
            )
        },
        **extra,
    }
    if holding:
        params["holding"] = holding
    res = client.get(GET, params=params)
    assert res.status_code == 200
    return res.json()


def _post(client, fp, holding=HELD_ETF):
    body = {"target_kind": "candidate", "ticker": CAND, **LIST_PARAMS}
    if fp is not None:
        body.update(pair_holding=holding, pair_fingerprint=fp)
    return client.post(PREVIEW, json=body).json()


def _pair_section(text):
    return text.split("[구성종목 비교]\n")[1].split("\n\n")[0]


def test_api_values_scope_and_no_amount(
    seeded: TestClient,  # noqa: F811
    priced,
) -> None:
    b = _get(seeded)
    assert b["status"] == "ok"
    # 보유 4종목 각 100원 시세 · 분모 = 현금 제외 보유 평가액(시세 있는 행 합) · 평가 비중 소수 넷째 자리
    sc = b["scope"]
    assert sc["included"] == {"count": 1, "weight": "42.8571"}
    assert sc["direct"] == {"count": 1, "weight": "14.2857"}
    assert sc["other_date"]["dates"] == ["2026-11-12"]
    assert sc["no_data"] == {"count": 1, "weight": "28.5714"}  # 네이버 확인 자료 없음
    sam = next(s for s in b["stocks"] if s["name"] == "삼성전자")
    # 42.8571 × 20 / 100 + 14.2857 = 22.85712 → 22.86
    assert (sam["exposure"]["raw"], sam["exposure"]["value"]) == ("22.85712", "22.86")
    assert sam["pair"] == {"state": "found", "weight": "20"}
    wonik = next(s for s in b["stocks"] if s["name"] == "원익IPS")
    assert wonik["pair"] == {"state": "zero"}  # 고른 보유 2행 = 원천 전체
    assert [r["ticker"] for r in sam["reference"]] == [HELD_ETF_OTHER]
    text = json.dumps(b, ensure_ascii=False)
    # 금액 없음(%만 · POC6-24) — 평가액 · 수량 · 평단 칸이나 금액 값이 없다
    for word in ("amount", "eval", "invested", "quantity", "avg_buy", '"300', '"400'):
        assert word not in text
    # 지문 = 계산 응답(지문 · 서버 글 덧붙임 칸 제외)
    extra = ("fingerprint", "date_line", "pair_dates_differ", "stock_notes")
    assert b["fingerprint"] == P.fingerprint(
        {k: v for k, v in b.items() if k not in extra}
    )
    assert b["date_line"] == T.date_line(b) and b["pair_dates_differ"] is False
    # 주식별 빠진 ETF 사유 글 = 미리보기 원문과 같은 서버 글(F14)
    assert b["stock_notes"] == {
        s["key"]: T.unknown_note(s["exposure"]) for s in b["stocks"]
    }


def test_api_requires_condition_filters(
    seeded: TestClient,  # noqa: F811
) -> None:
    assert seeded.get(GET, params={"candidate": CAND}).status_code == 422


def test_preview_same_fingerprint_builds_same_block_and_role_dates(
    seeded: TestClient,  # noqa: F811
    priced,
) -> None:
    b = _get(seeded)
    res = _post(seeded, b["fingerprint"])
    assert res["status"] == "ok", res
    # 미리보기 묶음 = 화면이 받은 응답으로 만든 줄 그대로(같은 함수 · 같은 입력)
    assert _pair_section(res["preview_text"]) == "\n".join(
        f"- {x}" for x in T.preview_lines(b)
    )
    assert res["evidence_as_of"]["candidate_constituents_asof"] == "2026-11-13"
    assert res["evidence_as_of"]["holding_constituents_asof"] == "2026-11-13"
    assert res["evidence_as_of"]["exposure_asof"] == "2026-11-13"
    assert (
        "삼성전자: 후보 25.00% · 고른 보유 20.00% · 내 보유 전체 22.86%"
        in res["preview_text"]
    )
    assert "보유 ETF 와 구성종목 중복" not in res["preview_text"]


def test_preview_refuses_when_same_day_numbers_changed(
    seeded: TestClient,  # noqa: F811
    priced,
) -> None:
    fp = _get(seeded)["fingerprint"]
    # 같은 날 편입 비중만 바뀜(수집이 그사이 다시 돔)
    _save(
        HELD_ETF,
        "2026-11-13",
        [(STOCK, "삼성전자", 21.0), ("000660", "SK하이닉스", 10.0)],
    )
    res = _post(seeded, fp)
    assert res == {
        **res,
        "status": "error",
        "message": api_preview.PAIR_CHANGED_MESSAGE,
    }
    assert res.get("preview_text") is None
    fp2 = _get(seeded)["fingerprint"]
    assert _post(seeded, fp2)["status"] == "ok"
    # 같은 날 시세만 바뀜 → 평가 비중이 바뀌어 다시 다름
    priced[HELD_ETF] = 101.0
    assert _post(seeded, fp2)["message"] == api_preview.PAIR_CHANGED_MESSAGE


def test_preview_refuses_other_holding_or_tampered_fingerprint(
    seeded: TestClient,  # noqa: F811
    priced,
) -> None:
    fp = _get(seeded)["fingerprint"]
    assert (
        _post(seeded, fp, holding=STOCK)["message"] == api_preview.PAIR_CHANGED_MESSAGE
    )
    assert _post(seeded, "0" * 64)["message"] == api_preview.PAIR_CHANGED_MESSAGE
    assert _post(seeded, "")["message"] == api_preview.PAIR_CHANGED_MESSAGE
    # 고른 보유 = 개별 주식 지문은 그 보유로만 통과
    fp_stock = _get(seeded, holding=STOCK)["fingerprint"]
    ok = _post(seeded, fp_stock, holding=STOCK)
    assert ok["status"] == "ok"
    assert "삼성전자: 후보 25.00% · 고른 보유 이 주식 자체" in ok["preview_text"]
    assert ok["evidence_as_of"]["holding_constituents_asof"] is None


def test_preview_without_fingerprint_has_block_without_pair(
    seeded: TestClient,  # noqa: F811
    priced,
) -> None:
    # 고른 보유가 없는 화면(「후보리스트」 등)의 후보 미리보기 — 대조 없이 묶음만(고른 보유 칸 없음)
    res = _post(seeded, None)
    assert res["status"] == "ok"
    sec = _pair_section(res["preview_text"])
    assert (
        "고른 보유 없음" in sec and "삼성전자: 후보 25.00% · 내 보유 전체 22.86%" in sec
    )
    assert res["evidence_as_of"]["exposure_asof"] == "2026-11-13"


def test_preview_pair_failure_without_fingerprint_keeps_preview(
    seeded: TestClient,  # noqa: F811
    priced,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom(*a, **k):
        raise RuntimeError("x")

    monkeypatch.setattr(IO, "load", boom)
    res = _post(seeded, None)
    assert res["status"] == "ok"
    assert _pair_section(res["preview_text"]) == f"- {T.UNBUILT_LINE}"
    # 지문 대조 요청은 다시 계산을 못 하면 미리보기를 만들지 않는다(일반 실패 · 근거 없이 만들지 않음)
    bad = _post(seeded, "f" * 64)
    assert (
        bad["status"] == "error" and bad["message"] != api_preview.PAIR_CHANGED_MESSAGE
    )


def test_preview_condition_equals_screen_get_condition_field_by_field(
    seeded: TestClient,  # noqa: F811
    priced,
) -> None:
    # 「보유와 후보 비교」가 보내는 칸 그대로(화면 · 쪽 · 순위 · 시작일 · 끝일 · 기간 · 제외 4종) — 미리보기가 같은 조건을
    # 만들어야 지문이 같다(칸 하나라도 빠지면 다른 조건 · 다른 지문).
    extra = {
        "screen": "holding_candidate_compare",
        "side": "top",
        "rank": 4,
        "start_date": "2026-10-14",
        "end_date": "2026-11-13",
    }
    got = _get(seeded, **extra)
    req = api_preview.PreviewRequest(
        target_kind="candidate",
        ticker=CAND,
        **LIST_PARAMS,
        list_source="common_period",
        end_price_state="after_close",
        **extra,
    )
    cond = api_preview._pair_condition(req, api_preview._list_query(req))
    assert cond == got["condition"]
    assert cond["rank"] == 4 and cond["screen"] == "holding_candidate_compare"
    # 순위만 다르면 다른 지문
    assert _get(seeded, **{**extra, "rank": 5})["fingerprint"] != got["fingerprint"]


# ── 원천 전체 표시(검토 지적 backend#0 · 수집기 → 저장 → 상태 읽기 → 짝 비교) ─────────────────────────────


@pytest.mark.parametrize(
    "count,kept,want",
    [
        (12, 12, True),
        (29, 29, True),
        (12, 11, False),  # 비중을 읽을 수 없어 버린 항목 — 저장 행이 원천 전체가 아님
        (30, 30, False),  # 요청 깊이를 다 받음 — 그 밖은 모름
        (None, 5, False),  # 원천 항목 수 모름(다른 수집기)
    ],
)
def test_source_complete_rule(count, kept, want):
    from app.etf_constituents_batch import source_complete
    from app.etf_constituents_fetcher import FetchedConstituent, FetchResult

    cons = [
        FetchedConstituent(
            rank=i + 1,
            constituent_ticker=f"{i:06d}",
            constituent_name="x",
            weight_pct=1.0,
        )
        for i in range(kept)
    ]
    res = FetchResult(
        status="ok", source=NAVER_STOCK_SOURCE, constituents=cons, source_count=count
    )
    assert source_complete(res) is want


def test_naver_fetcher_counts_source_items_including_dropped(monkeypatch):
    from app import etf_constituents_fetcher as F

    items = [
        {
            "componentItemCode": "005930",
            "weight": "32.33",
            "referenceDate": "2026-11-13",
        },
        {"componentItemCode": "000660", "weight": "-", "referenceDate": "2026-11-13"},
        "not-a-dict",
    ]
    monkeypatch.setattr(
        F,
        "_naver_http_get",
        lambda url, timeout=10: (200, json.dumps(items, ensure_ascii=False)),
    )
    res = F.naver_stock_etf_component_fetcher("069500", "2026-11-13", top_k=30)
    assert (res.source_count, len(res.constituents)) == (3, 1)


def test_collector_marks_complete_only_when_nothing_dropped(tmp_path):
    from app.etf_constituents_batch import KIND_CANDIDATES, Collector
    from app.etf_constituents_fetcher import FetchedConstituent, FetchResult
    from app.etf_constituents_status import read_snapshots

    db = tmp_path / "m.sqlite"

    def fetch(ticker, asof, top_k):  # noqa: ARG001
        kept = 11 if ticker == "DROP" else 12
        return FetchResult(
            status="ok",
            source=NAVER_STOCK_SOURCE,
            constituents=[
                FetchedConstituent(
                    rank=i + 1,
                    constituent_ticker=f"{i:06d}",
                    constituent_name=f"주식{i}",
                    weight_pct=10.0 - i * 0.5,
                )
                for i in range(kept)
            ],
            effective_asof="2026-11-13",
            source_count=12,
        )

    Collector().start(
        KIND_CANDIDATES,
        ["FULL", "DROP"],
        target_date="2026-11-13",
        db_path=db,
        fetcher=fetch,
        sleep_fn=lambda s: None,
        mono_fn=lambda: 0.0,
        run_async=False,
    )
    snaps = read_snapshots(["FULL", "DROP"], db_path=db)
    assert snaps["FULL"]["confirmed"]["complete"] is True
    # 하나를 버림 — 원천일은 확인(재사용 · 날짜별 집계에 씀)되지만 원천 전체는 아님
    assert snaps["DROP"]["confirmed"]["complete"] is False
    assert (
        P.stored_range(11, snaps["DROP"]["confirmed"]["complete"]) == P.RANGE_UNVERIFIED
    )


def test_old_confirmation_without_mark_reads_as_not_complete(tmp_path):
    # 이 표시 전에 남긴 확인 기록(지문만)도 원천일 확인은 그대로 · 원천 전체는 모름(보수적으로 '저장 범위에서 미확인')
    from app.etf_constituents_status import confirmation_message, read_snapshots
    from app.etf_constituents_store import log_constituent_refresh, upsert_constituents

    db = tmp_path / "m.sqlite"
    rows = _naver("OLD", "2026-11-13", [(STOCK, "삼성전자", 10.0)])
    upsert_constituents(rows, db_path=db)
    log_constituent_refresh(
        etf_ticker="OLD",
        asof="2026-11-13",
        status=LOG_OK,
        source=NAVER_STOCK_SOURCE,
        message=confirmation_message(rows),
        db_path=db,
    )
    rows2 = _naver("NEW", "2026-11-13", [(STOCK, "삼성전자", 10.0)])
    upsert_constituents(rows2, db_path=db)
    log_constituent_refresh(
        etf_ticker="NEW",
        asof="2026-11-13",
        status=LOG_OK,
        source=NAVER_STOCK_SOURCE,
        message=confirmation_message(rows2, complete=True),
        db_path=db,
    )
    snaps = read_snapshots(["OLD", "NEW"], db_path=db)
    assert snaps["OLD"]["confirmed"]["complete"] is False
    assert snaps["NEW"]["confirmed"]["complete"] is True
    # 표시를 붙여도 지문 대조(원천일 확인)는 그대로 — 분석 읽기도 같은 확인
    from app.etf_constituents_status import read_analysis_rows

    _, rows_by = read_analysis_rows(["OLD", "NEW"], asof=None, db_path=db)
    assert rows_by["OLD"][1] is True and rows_by["NEW"][1] is True


def test_read_etf_master_tells_unreadable_from_list(tmp_path):
    # 못 읽음 · 표 없음 · 빈 표 = None(빈 목록으로 보면 모든 보유 ETF 가 직접 보유로 셈해짐 · 검토 지적 backend#5)
    import sqlite3

    from app.market_data_store import EtfMasterRow, upsert_etf_master

    assert IO.read_etf_master(tmp_path / "none.sqlite") is None
    db = tmp_path / "m.sqlite"
    sqlite3.connect(db).close()
    assert IO.read_etf_master(db) is None  # 표 없음
    with sqlite3.connect(db) as con:
        con.execute("CREATE TABLE etf_master (ticker TEXT, name TEXT)")
    assert IO.read_etf_master(db) is None  # 빈 표
    upsert_etf_master(
        [EtfMasterRow("069500", "KODEX 200", "1", 1.0, 1, 1.0)],
        source="test",
        db_path=tmp_path / "ok.sqlite",
    )
    assert IO.read_etf_master(tmp_path / "ok.sqlite") == (
        {"069500": "KODEX 200"},
        {"069500"},
    )


# ── 검증자 STEP 4~5 r1 정정(F10 ~ F13 · 검증자 재현 장면) ──────────────────────────────


def test_f10_no_confirmed_part_is_unknown_not_zero():
    # 보유 ETF 1종목이 평가액 100% · 원천일 미확인 · 직접 보유 0 — 계산 근거가 없으니 0.00% 가 아니라 확인 불가
    snaps = {
        "C": conf("2026-11-13", [kr(1, *SAMSUNG, 25.0)]),
        "U": unconf("2026-06-22", 10),
    }
    b = P.build(
        candidate="C",
        holding=None,
        condition=COND,
        hw=hw([item("U", "100.0000")]),
        price_date=PRICE_DATE,
        names={},
        etf_tickers={"C", "U"},
        snaps=snaps,
    )
    ex = stock(b, "삼성전자")["exposure"]
    assert (ex["value"], ex["raw"]) == (None, None)
    line = next(ln for ln in T.preview_lines(b) if ln.startswith("삼성전자:"))
    assert (
        line.endswith("내 보유 전체 확인 불가(확인한 구성 없음)")
        and "0.00%" not in line
    )
    # 합산 ETF 가 있어도 그 주식에 대해 전부 미확인(30행)이고 직접 보유가 없으면 확인 불가
    snaps2 = {
        "C": conf("2026-11-13", [us(1, *LLY, 30.0)]),
        "A": conf("2026-11-13", filler(1, 30)),
    }
    b2 = P.build(
        candidate="C",
        holding=None,
        condition=COND,
        hw=hw([item("A", "100.0000")]),
        price_date=PRICE_DATE,
        names={},
        etf_tickers={"C", "A"},
        snaps=snaps2,
    )
    ex2 = stock(b2, "일라이 릴리")["exposure"]
    assert ex2["value"] is None and len(ex2["unknown"]) == 1
    # 원천 전체로 없음이 확인되면 확인된 0
    snaps2["A"] = conf("2026-11-13", filler(1, 12), complete=True)
    b3 = P.build(
        candidate="C",
        holding=None,
        condition=COND,
        hw=hw([item("A", "100.0000")]),
        price_date=PRICE_DATE,
        names={},
        etf_tickers={"C", "A"},
        snaps=snaps2,
    )
    assert stock(b3, "일라이 릴리")["exposure"]["value"] == "0.00"


def test_f10_unreadable_weight_rows_are_unknown_not_zero():
    # 예전에 저장된 NaN 비중 행 — 합계 · 짝 · 참고 · 저장 행 합 어디에도 0 으로 넣지 않는다
    nan = float("nan")
    snaps = base_snaps()
    snaps["A"] = conf("2026-11-13", [us(1, *LLY, nan), *filler(2, 29)])
    snaps["R"] = conf("2026-11-12", [us(1, *LLY, nan)])
    b = build(snaps=snaps)
    lly = stock(b, "일라이 릴리")
    assert lly["pair"] == {"state": P.PAIR_WEIGHT_UNKNOWN}
    assert all(t["ticker"] != "A" for t in lly["exposure"]["terms"])
    assert {u["ticker"]: u["range"] for u in lly["exposure"]["unknown"]}["A"] == (
        P.WEIGHT_UNKNOWN
    )
    assert lly["reference"][0]["constituent_weight"] is None
    assert lly["reference"][0]["product"] is None
    nvo = stock(b, "노보 노디스크 ADR")
    assert nvo["pair"]["stored_sum"] is None  # 저장 행 합 확인 불가
    lines = T.preview_lines(b)
    assert any("고른 보유 편입 · 비중 확인 불가" in ln for ln in lines)
    assert any("저장 행 합 확인 불가" in ln for ln in lines)
    assert any("보유R 2026-11-12 — 일라이 릴리 비중 확인 불가" in ln for ln in lines)


@pytest.mark.parametrize(
    "raw", ["NaN", "nan", "inf", "-Infinity", float("nan"), float("inf")]
)
def test_f10_fetcher_rejects_non_finite_weight(raw):
    from app.etf_constituents_fetcher import _coerce_weight_string

    assert _coerce_weight_string(raw) is None


def test_f10_fetcher_drops_nan_item_so_snapshot_is_not_complete(monkeypatch):
    from app import etf_constituents_fetcher as F
    from app.etf_constituents_batch import source_complete

    items = [
        {
            "componentItemCode": "005930",
            "weight": "32.33",
            "referenceDate": "2026-11-13",
        },
        {"componentItemCode": "000660", "weight": "NaN", "referenceDate": "2026-11-13"},
    ]
    monkeypatch.setattr(
        F,
        "_naver_http_get",
        lambda url, timeout=10: (200, json.dumps(items, ensure_ascii=False)),
    )
    res = F.naver_stock_etf_component_fetcher("069500", "2026-11-13", top_k=30)
    assert (res.source_count, len(res.constituents)) == (2, 1)
    assert source_complete(res) is False


def test_f11_compare_screen_or_selected_holding_needs_fingerprint(
    seeded: TestClient,  # noqa: F811
    priced,
) -> None:
    base = {"target_kind": "candidate", "ticker": CAND, **LIST_PARAMS}
    # 비교 화면 요청인데 지문이 없으면 대조 없이 만들지 않는다
    for extra in (
        {"screen": "holding_candidate_compare", "pair_holding": HELD_ETF},
        {"screen": "holding_candidate_compare"},
        {"pair_holding": HELD_ETF},
    ):
        res = seeded.post(PREVIEW, json={**base, **extra}).json()
        assert res["status"] == "error"
        assert res["message"] == api_preview.PAIR_REQUIRED_MESSAGE
        assert res.get("preview_text") is None
    # 고른 보유가 없는 다른 화면(지문 · 고른 보유 없음)은 그대로 만든다
    assert seeded.post(PREVIEW, json=base).json()["status"] == "ok"
    # 보유 미리보기는 대상 아님
    hold = seeded.post(
        PREVIEW,
        json={"target_kind": "holding", "ticker": HELD_ETF, "pair_holding": HELD_ETF},
    ).json()
    assert hold["status"] == "ok"


def test_f12_pair_dates_differ_marks_reference_in_text_and_get(
    seeded: TestClient,  # noqa: F811
    priced,
) -> None:
    # 후보 구성 · 노출 합계 11/13 · 고른 보유 11/12(시세 있음 · 합계 밖 다른 구성일)
    b = _get(seeded, holding=HELD_ETF_OTHER)
    assert b["dates"] == {
        "candidate": "2026-11-13",
        "holding": "2026-11-12",
        "exposure": "2026-11-13",
    }
    assert b["pair_dates_differ"] is True
    assert b["date_line"].endswith(
        "고른 보유 비중은 구성일이 달라 나란히 읽는 참고 수치(구성일 다름 · 참고)"
    )
    sam = next(ln for ln in T.preview_lines(b) if ln.startswith("삼성전자:"))
    assert "고른 보유 3.00%(구성일 다름 · 참고)" in sam
    # 미리보기 원문에도 같은 글
    res = _post(seeded, b["fingerprint"], holding=HELD_ETF_OTHER)
    assert res["status"] == "ok"
    assert "고른 보유 3.00%(구성일 다름 · 참고)" in res["preview_text"]
    assert b["date_line"] in res["preview_text"]
    # 같은 날짜면 표시 없음
    same = _get(seeded)
    assert same["pair_dates_differ"] is False and "참고)" not in same["date_line"]


def test_f13_holdings_unreadable_keeps_known_dates_in_text():
    b = build(hw=None)
    assert b["status"] == P.STATUS_HOLDINGS_UNREADABLE
    lines = T.preview_lines(b)
    assert lines[0] == (
        "기준일: 후보 구성 2026-11-13 · 고른 보유(A) 구성 2026-11-13 · "
        "노출 합계 확인 불가(보유 목록을 읽지 못함)"
    )
    assert lines[1] == T.HOLDINGS_UNREADABLE_LINE
    snaps = base_snaps()
    snaps["A"] = conf("2026-11-12", [us(1, *LLY, 3.0)])
    b2 = build(hw=None, snaps=snaps)
    assert T.preview_lines(b2)[0].endswith(
        "고른 보유 비중은 구성일이 달라 나란히 읽는 참고 수치(구성일 다름 · 참고)"
    )
    assert any(
        "고른 보유 3.00%(구성일 다름 · 참고)" in ln for ln in T.preview_lines(b2)
    )


# ── 검증자 STEP 4~5 r2 정정(F14 · 검증자 장면) ──────────────────────────────────────


def _f14(etf_rows_a, etf_rows_b, complete_a=True):
    """A = 평가액 40%(원천 전체 · 삼성전자 편입 행) · B = 20%(30행 · 삼성전자 없음) · 직접 보유 삼성전자 40%."""
    snaps = {
        "C": conf("2026-11-13", [kr(1, *SAMSUNG, 25.0)]),
        "A": conf("2026-11-13", etf_rows_a, complete=complete_a),
        "B": conf("2026-11-13", etf_rows_b),
    }
    return P.build(
        candidate="C",
        holding="A",
        condition=COND,
        hw=hw(
            [
                item("A", "40.0000"),
                item("B", "20.0000"),
                item("005930", "40.0000", etf=False, name="삼성전자"),
            ]
        ),
        price_date=PRICE_DATE,
        names={},
        etf_tickers={"C", "A", "B"},
        snaps=snaps,
    )


def test_f14_unknown_reasons_are_told_apart_in_text_and_note():
    nan = float("nan")
    b = _f14([kr(1, *SAMSUNG, nan), *filler(2, 11)], filler(1, 30))
    sam = stock(b, "삼성전자")
    assert sam["pair"] == {"state": P.PAIR_WEIGHT_UNKNOWN}
    assert sam["exposure"]["value"] == "40.00"  # 직접 보유만 확인
    note = T.unknown_note(sam["exposure"])
    assert note == (
        "저장 범위 밖 미확인 ETF 1개 · 평가액 20.00% · 편입 비중 확인 불가 ETF 1개 · 평가액 40.00%"
    )
    line = next(ln for ln in T.preview_lines(b) if ln.startswith("삼성전자:"))
    assert line == (
        "삼성전자: 후보 25.00% · 고른 보유 편입 · 비중 확인 불가 · 내 보유 전체 40.00%"
        f"({note})"
    )
    # 비중 미확인만 있으면 '저장 범위 밖'이라고 적지 않는다
    b2 = _f14([kr(1, *SAMSUNG, nan), *filler(2, 11)], [kr(1, *SAMSUNG, 5.0)])
    only = T.unknown_note(stock(b2, "삼성전자")["exposure"])
    assert only == "편입 비중 확인 불가 ETF 1개 · 평가액 40.00%"
    assert "저장 범위 밖" not in only
    # 저장 범위 밖만 있으면 예전 글 그대로
    b3 = _f14(filler(1, 30), filler(1, 30), complete_a=False)
    assert T.unknown_note(stock(b3, "삼성전자")["exposure"]) == (
        "저장 범위 밖 미확인 ETF 2개 · 평가액 60.00%"
    )
    # 빠진 ETF 가 없으면 글 없음
    b4 = _f14([kr(1, *SAMSUNG, 10.0)], [kr(1, *SAMSUNG, 5.0)])
    assert T.unknown_note(stock(b4, "삼성전자")["exposure"]) is None


def test_f14_get_returns_server_note_for_each_stock(
    seeded: TestClient,  # noqa: F811
    priced,
) -> None:
    # 고른 보유 구성을 다른 내용(행 하나 추가)으로 원천 전체 표시 없이 다시 저장(그 밖 미확인 · 같은 내용이면 앞 기록의
    # 원천 전체 표시가 그대로 적용됨) — 원익IPS 는 그 ETF 에서 '저장 범위 밖 미확인'
    replace_constituents_snapshot(
        _naver(
            HELD_ETF,
            "2026-11-13",
            [
                (STOCK, "삼성전자", 20.0),
                ("000660", "SK하이닉스", 10.0),
                ("042700", "한미반도체", 4.0),
            ],
        ),
        log_status=LOG_OK,
        confirm=True,
        db_path=api_preview.DEFAULT_DB_PATH,
    )
    b = _get(seeded)
    wonik = next(s for s in b["stocks"] if s["name"] == "원익IPS")
    assert (
        b["stock_notes"][wonik["key"]] == "저장 범위 밖 미확인 ETF 1개 · 평가액 42.86%"
    )
    assert b["stock_notes"] == {
        s["key"]: T.unknown_note(s["exposure"]) for s in b["stocks"]
    }
    res = _post(seeded, b["fingerprint"])
    assert "(저장 범위 밖 미확인 ETF 1개 · 평가액 42.86%)" in res["preview_text"]
