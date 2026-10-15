"""POC5-13 — PC 근거 응답 사본의 20저장일 하락 구간(`decline_band`).

판정: docs/ai_design/POC5/
  POC5-13_HOLDINGS_AND_MARKET_RISK_EVIDENCE_INTEGRATION_PLAN_DECISION_2026-10-14.md
  (PLAN §7 Q1 (b) PC 이름 · Q2 (b) 자기 값으로 판정)
순수 사본 처리 + 실제 GET /holdings/market-evidence/latest(tmp DB · 격리 보유).
라이브 DB · 라이브 보유 파일을 열지 않는다.
"""

from __future__ import annotations

import copy
import math

import pytest
from fastapi.testclient import TestClient

from app import api_market_topn
from app import holdings as holdings_module
from app.holdings_market_evidence import build_holdings_market_evidence
from app.market_topn import DEFAULT_BASIS, DEFAULT_N, DEFAULT_ORDER, compute_topn
from app.pc_price_basis import (
    COMPARISON_DATE_MISMATCH,
    COMPARISON_OK,
    COMPARISON_UNAVAILABLE,
    COMPARISON_WINDOW_MISMATCH,
    PC_DECLINE_LABEL,
    _decline_band,
    apply_pc_price_basis,
)
from app.runtime_evidence.holdings_selection import (
    DECLINE_STATE_LABEL,
    classify_decline,
    normalize_pct,
)
from tests.test_pc_price_basis import (  # noqa: F401 — api_client 는 fixture
    REF,
    _closes,
    _evidence,
    _item,
    _rows,
    _seed,
    api_client,
)

OLD = "2026-09-30"


def _stm(value, status: str = "ok") -> dict:
    return {"status": status, "return_20d_pct": value}


# ── 구간 = OCI 보유 알림 함수(반올림 포함) ─────────────────────────────────────
@pytest.mark.parametrize(
    "value, state",
    [
        (-4.94, None),
        (-4.95, "D5_8"),  # 소수 첫째 자리 반올림(−5.0) 뒤 경계
        (-5.0, "D5_8"),
        (-7.95, "D8_10"),
        (-7.96, "D8_10"),
        (-8.0, "D8_10"),
        (-9.95, "D8_10"),
        (-9.96, "D10_PLUS"),
        (-10.0, "D10_PLUS"),
        (-12.3, "D10_PLUS"),
        (0.0, None),
        (3.1, None),
    ],
)
@pytest.mark.parametrize("comparison", [COMPARISON_OK, COMPARISON_WINDOW_MISMATCH])
def test_band_equals_oci_function_at_boundaries(value, state, comparison) -> None:
    band = _decline_band(_stm(value), comparison)
    assert band["state"] == state == classify_decline(normalize_pct(value))
    assert band["judgeable"] is True
    assert band["unjudged_reason"] is None
    assert band["return_20d_pct_1dp"] == normalize_pct(value)
    assert band["label"] == (PC_DECLINE_LABEL[state] if state else None)


def test_pc_labels_and_shared_oci_labels_unchanged() -> None:
    assert PC_DECLINE_LABEL == {
        "D10_PLUS": "PC 20저장일 하락 10% 이상",
        "D8_10": "PC 20저장일 하락 8~10%",
        "D5_8": "PC 20저장일 하락 5~8%",
    }
    # 공유 이름(OCI 보유 알림)은 그대로.
    assert DECLINE_STATE_LABEL == {
        "D10_PLUS": "20거래일 하락 10% 이상",
        "D8_10": "20거래일 하락 8~10%",
        "D5_8": "20거래일 하락 5~8%",
    }


# ── 판정 안 함 = 이유 코드(‘구간 밖’과 다름) ─────────────────────────────────
@pytest.mark.parametrize(
    "stm, comparison, reason",
    [
        # 판정 순서: 종료일 → 이력 → 값. 기준일이 다르면 값이 있어도 date_mismatch.
        (_stm(-12.0), COMPARISON_DATE_MISMATCH, "date_mismatch"),
        (_stm(None, "unavailable"), COMPARISON_DATE_MISMATCH, "date_mismatch"),
        (_stm(None, "unavailable"), COMPARISON_UNAVAILABLE, "insufficient_history"),
        (_stm(-12.0, "unavailable"), COMPARISON_OK, "insufficient_history"),
        (_stm(None), COMPARISON_OK, "invalid_value"),
        (_stm(math.nan), COMPARISON_OK, "invalid_value"),
        (_stm(-math.inf), COMPARISON_OK, "invalid_value"),
        (_stm(True), COMPARISON_OK, "invalid_value"),
        (_stm("-12.0"), COMPARISON_OK, "invalid_value"),
        ({}, COMPARISON_OK, "insufficient_history"),
    ],
)
def test_unjudged_reasons_and_order(stm, comparison, reason) -> None:
    band = _decline_band(stm, comparison)
    assert band == {
        "judgeable": False,
        "state": None,
        "label": None,
        "return_20d_pct_1dp": None,
        "unjudged_reason": reason,
    }


# ── 사본 적용(같은 읽기의 20저장일 값) ────────────────────────────────────────
def test_copy_gets_band_per_item_and_input_not_mutated() -> None:
    rows = {
        "069500": _rows(REF),
        "111111": _rows(REF, r=-12.0),
        "222222": _rows(REF, r=-6.0),
        "333333": _rows(REF, r=-3.0),
        "444444": _rows(OLD, r=-12.0),  # 기준일 다름
        "555555": _rows(REF, r=-12.0, n=15),  # 이력 부족
        "666666": _rows(REF, r=-9.0, skip=(12,)),  # 20일 시작일만 다름
    }
    ev = _evidence(
        [
            _item("111111", -12.0),
            _item("222222", -6.0),
            _item("333333", -3.0),
            _item("444444", -12.0),
            _item("555555", None, status="unavailable"),
            _item("666666", -9.0),
        ]
    )
    before = copy.deepcopy(ev)
    out = apply_pc_price_basis(ev, rows)
    assert ev == before  # 원본(공유 builder 결과)에는 붙이지 않는다
    assert all("decline_band" not in it for it in ev["holdings"])
    by = {it["ticker"]: it for it in out["holdings"]}
    got = {
        t: (b["judgeable"], b["state"], b["unjudged_reason"])
        for t, b in ((t, it["decline_band"]) for t, it in by.items())
    }
    assert got == {
        "111111": (True, "D10_PLUS", None),
        "222222": (True, "D5_8", None),
        "333333": (True, None, None),
        "444444": (False, None, "date_mismatch"),
        "555555": (False, None, "insufficient_history"),
        "666666": (True, "D8_10", None),
    }
    # 판정 값 = 이 사본의 20저장일 값(같은 읽기)을 소수 첫째 자리로.
    for it in out["holdings"]:
        b = it["decline_band"]
        if b["judgeable"]:
            r20 = it["short_term_momentum"]["return_20d_pct"]
            assert b["return_20d_pct_1dp"] == normalize_pct(r20)
            assert b["state"] == classify_decline(normalize_pct(r20))
    # 20일 시작일만 다른 종목: 자기 값으로 판정하고, 상대 비교는 기존대로 비움.
    wm = by["666666"]
    assert wm["price_dates"]["comparison"] == COMPARISON_WINDOW_MISMATCH
    assert wm["short_term_momentum"]["excess_vs_kodex200_20d_pctp"] is None
    assert wm["decline_band"]["label"] == "PC 20저장일 하락 8~10%"


def test_same_ticker_two_accounts_get_the_same_band() -> None:
    rows = {"069500": _rows(REF), "111111": _rows(REF, r=-8.5)}
    ev = _evidence(
        [_item("111111", -8.5, account="일반"), _item("111111", -8.5, account="ISA")]
    )
    a, b = apply_pc_price_basis(ev, rows)["holdings"]
    assert a["decline_band"] == b["decline_band"]
    assert a["decline_band"]["state"] == "D8_10"


# ── 실제 GET 응답(tmp DB) ─────────────────────────────────────────────────────
def test_endpoint_returns_band_and_shared_builder_has_none(
    api_client: TestClient,  # noqa: F811
) -> None:
    db = api_market_topn.DEFAULT_DB_PATH
    _seed(db, "069500", REF, _closes(0.0))
    _seed(db, "111111", REF, _closes(-10.0))
    _seed(db, "222222", REF, _closes(-2.0))
    _seed(db, "333333", "2026-08-12", _closes(-20.0))
    _seed(db, "444444", REF, _closes(-7.0)[-12:])  # 12행 → 이력 부족
    payload = [
        {"ticker": t, "name": t + "명", "quantity": 1, "avg_buy_price": 100}
        for t in ("111111", "222222", "333333", "444444")
    ]
    assert api_client.put("/holdings", json={"holdings": payload}).status_code == 200

    body = api_client.get("/holdings/market-evidence/latest").json()
    by = {h["ticker"]: h["decline_band"] for h in body["holdings"]}
    assert by["111111"] == {
        "judgeable": True,
        "state": "D10_PLUS",
        "label": "PC 20저장일 하락 10% 이상",
        "return_20d_pct_1dp": -10.0,
        "unjudged_reason": None,
    }
    assert (by["222222"]["judgeable"], by["222222"]["state"]) == (True, None)
    assert by["222222"]["return_20d_pct_1dp"] == -2.0
    assert by["333333"]["unjudged_reason"] == "date_mismatch"
    assert by["444444"]["unjudged_reason"] == "insufficient_history"

    # 공유 builder(PUSH · 초안 경로)는 이 필드를 만들지 않는다.
    shared = build_holdings_market_evidence(
        holdings=holdings_module.load(),
        topn_payload=compute_topn(
            n=DEFAULT_N, db_path=db, basis=DEFAULT_BASIS, order=DEFAULT_ORDER
        ),
        market_quotes={},
        db_path=db,
        holdings_asof=None,
    )
    assert all("decline_band" not in h for h in shared["holdings"])
