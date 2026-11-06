"""POC6-24 — 보유 판단의 자금 기준(현금 C · 추가 투입 한도 A · 확인일) 저장 · 계산 · 미리보기.

통합설계 V1.1(`docs/ai_design/POC6/POC6_24_..._PLAN_DECISION_2026-11-06.md` B) AC1 ~ AC8 의 백엔드 부분.
모든 금액은 가상 값 · 파일은 conftest 가 바꿔 끼운 tmp `holdings.HOLDINGS_DIR` 아래(라이브 state 0).
"""

from __future__ import annotations

import json
import re
from datetime import timedelta
from pathlib import Path
from typing import Optional

import pytest
from fastapi.testclient import TestClient

from app import api_decision_draft_preview, api_decision_sessions
from app import decision_evidence_store
from app import holdings as holdings_module
from app import holdings_capital as cap
from app.api import app
from app.decision_draft_preview_service import build_preview_text
from app.decision_preview_lines import AI_REQUEST
from app.decision_selected_preview import SELECTED_PREVIEW_SOURCE_SCREEN
from app.holdings import Holding
from app.market_cache import MarketQuote

DAY = "2026-11-05"
ASOF = f"{DAY}T16:10:16+09:00"
SECTION = "[보유 · 자금 기준]"


def _quote(ticker: str, price: Optional[float], asof: Optional[str] = ASOF):
    return MarketQuote(
        ticker=ticker,
        name=f"시험 {ticker}",
        current_price=price,
        price_asof=asof,
        price_source="TEST",
    )


def _seed(monkeypatch: pytest.MonkeyPatch, rows: list[Holding], quotes: dict) -> None:
    holdings_module.save(rows)
    from app import market_cache

    monkeypatch.setattr(market_cache, "get_all", lambda: quotes, raising=True)


def _ac2(monkeypatch: pytest.MonkeyPatch, asof: str = ASOF) -> None:
    """설계 AC2 — 보유 60만(이 종목 12만 · 다른 종목 48만)."""
    _seed(
        monkeypatch,
        [
            Holding("069500", 10, 11000.0, "시험 069500", "일반"),
            Holding("360750", 20, 20000.0, "시험 360750", "일반"),
        ],
        {
            "069500": _quote("069500", 12000.0, asof),
            "360750": _quote("360750", 24000.0, asof),
        },
    )


def _two_accounts(
    monkeypatch: pytest.MonkeyPatch, second_price: Optional[float] = 40000.0
) -> None:
    """같은 종목 두 계좌(3 × 40,000 + 1 × 40,000 = 16만) + 다른 종목 44만 = 60만."""
    quotes = {"360750": _quote("360750", 22000.0)}
    if second_price is not None:
        quotes["069500"] = _quote("069500", second_price)
    _seed(
        monkeypatch,
        [
            Holding("069500", 3, 38000.0, "시험 069500", "일반"),
            Holding("069500", 1, 39000.0, "시험 069500", "연금저축"),
            Holding("360750", 20, 20000.0, "시험 360750", "일반"),
        ],
        quotes,
    )


def _file() -> Path:
    return holdings_module.HOLDINGS_DIR / "capital_context.json"


# ── AC1 저장 · 복원 · 거부 ────────────────────────────────────────────────


def test_initial_state_is_not_entered_and_path_follows_holdings_dir() -> None:
    assert cap.path() == holdings_module.HOLDINGS_DIR / "capital_context.json"
    assert cap.path().resolve() != Path("state/holdings/capital_context.json").resolve()
    assert not _file().exists()
    st = cap.read()
    assert st == {
        "status": "NOT_ENTERED",
        "cash_krw": None,
        "limit_krw": None,
        "confirmed_on": None,
        "saved_at": None,
    }


def test_save_positive_zero_modify_clear_round_trip() -> None:
    st = cap.save(400000, 100000, DAY)
    assert st["status"] == "ENTERED"
    assert (st["cash_krw"], st["limit_krw"], st["confirmed_on"]) == (
        400000,
        100000,
        DAY,
    )
    doc = json.loads(_file().read_text(encoding="utf-8"))
    assert set(doc) == {
        "schema_version",
        "cash_krw",
        "limit_krw",
        "confirmed_on",
        "saved_at",
    }
    assert doc["schema_version"] == 1 and doc["saved_at"] == st["saved_at"]
    assert cap.read() == st

    # 명시적 0원 = 입력한 값(미입력 아님) · 한도 비움 = 미정
    st = cap.save(0, None, DAY)
    assert cap.read()["status"] == "ENTERED"
    assert (st["cash_krw"], st["limit_krw"]) == (0, None)

    # 수정
    cap.save(250000, 250000, "2026-11-01")
    assert cap.read()["cash_krw"] == 250000 and cap.read()["limit_krw"] == 250000

    # 비우기 = 세 칸 null 저장(파일은 남음)
    st = cap.save(None, None, None)
    assert st["status"] == "NOT_ENTERED"
    assert _file().exists()
    doc = json.loads(_file().read_text(encoding="utf-8"))
    assert (doc["cash_krw"], doc["limit_krw"], doc["confirmed_on"]) == (
        None,
        None,
        None,
    )
    assert cap.read()["status"] == "NOT_ENTERED"
    assert not list(_file().parent.glob(".capital-*.tmp"))


def test_upper_bound_is_inclusive() -> None:
    st = cap.save(cap.MAX_KRW, cap.MAX_KRW, DAY)
    assert st["cash_krw"] == 2**53 - 1


def _future() -> str:
    return (cap.today_kst() + timedelta(days=1)).isoformat()


REJECT = [
    ("한도 > 현금", lambda: (100, 101, DAY)),
    ("음수 현금", lambda: (-1, None, DAY)),
    ("음수 한도", lambda: (100, -1, DAY)),
    ("소수 현금", lambda: (100.5, None, DAY)),
    ("정수 모양 소수", lambda: (100.0, None, DAY)),
    ("불", lambda: (True, None, DAY)),
    ("문자열 금액", lambda: ("100", None, DAY)),
    ("NaN", lambda: (float("nan"), None, DAY)),
    ("무한", lambda: (float("inf"), None, DAY)),
    ("상한 초과", lambda: (2**53, None, DAY)),
    ("현금 없이 한도", lambda: (None, 100, DAY)),
    ("현금 있는데 확인일 없음", lambda: (100, None, None)),
    ("미래 확인일", lambda: (100, None, _future())),
    ("현금 없는데 확인일", lambda: (None, None, DAY)),
    ("날짜 형식", lambda: (100, None, "2026-1-5")),
    ("없는 날짜", lambda: (100, None, "2026-02-30")),
    ("날짜 숫자", lambda: (100, None, 20261105)),
    ("날짜 시각 포함", lambda: (100, None, "2026-11-05T00:00:00")),
]


@pytest.mark.parametrize("label,args", REJECT, ids=[r[0] for r in REJECT])
def test_rejected_inputs_leave_file_unchanged(label: str, args) -> None:
    cap.save(300000, None, DAY)
    before = _file().read_bytes()
    with pytest.raises(cap.CapitalInputError):
        cap.save(*args())
    assert _file().read_bytes() == before


CORRUPT = [
    ("JSON 아님", "{not json"),
    ("목록", "[]"),
    (
        "형식 버전",
        json.dumps(
            {
                "schema_version": 2,
                "cash_krw": 1,
                "limit_krw": None,
                "confirmed_on": DAY,
                "saved_at": None,
            }
        ),
    ),
    ("칸 빠짐", json.dumps({"schema_version": 1, "cash_krw": 1, "confirmed_on": DAY})),
    (
        "소수 금액",
        json.dumps(
            {
                "schema_version": 1,
                "cash_krw": 1.5,
                "limit_krw": None,
                "confirmed_on": DAY,
                "saved_at": None,
            }
        ),
    ),
    (
        "한도 > 현금",
        json.dumps(
            {
                "schema_version": 1,
                "cash_krw": 1,
                "limit_krw": 2,
                "confirmed_on": DAY,
                "saved_at": None,
            }
        ),
    ),
    (
        "확인일 없음",
        json.dumps(
            {
                "schema_version": 1,
                "cash_krw": 1,
                "limit_krw": None,
                "confirmed_on": None,
                "saved_at": None,
            }
        ),
    ),
    (
        "저장 시각 형",
        json.dumps(
            {
                "schema_version": 1,
                "cash_krw": None,
                "limit_krw": None,
                "confirmed_on": None,
                "saved_at": 5,
            }
        ),
    ),
    ("깊은 중첩(RecursionError)", "[" * 200000),
    (
        "형식 버전 true",
        json.dumps(
            {
                "schema_version": True,
                "cash_krw": 1,
                "limit_krw": None,
                "confirmed_on": DAY,
                "saved_at": None,
            }
        ),
    ),
    (
        "형식 버전 1.0",
        json.dumps(
            {
                "schema_version": 1.0,
                "cash_krw": 1,
                "limit_krw": None,
                "confirmed_on": DAY,
                "saved_at": None,
            }
        ),
    ),
]


@pytest.mark.parametrize("label,body", CORRUPT, ids=[c[0] for c in CORRUPT])
def test_corrupt_file_is_read_failed_and_never_overwritten(
    label: str, body: str
) -> None:
    _file().parent.mkdir(parents=True, exist_ok=True)
    _file().write_text(body, encoding="utf-8")
    with pytest.raises(cap.CapitalCorrupt):
        cap.read()
    st = cap.load_status()
    assert st["status"] == "READ_FAILED"
    assert (
        st["cash_krw"] is None and st["limit_krw"] is None
    )  # 0원 · 미입력으로 바꾸지 않음
    with pytest.raises(cap.CapitalCorrupt):
        cap.save(100, None, DAY)
    with pytest.raises(cap.CapitalCorrupt):
        cap.save(None, None, None)  # 비우기도 손상 파일을 덮어쓰지 않음
    assert _file().read_text(encoding="utf-8") == body


def test_failed_replace_keeps_old_file_and_removes_temp(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cap.save(300000, None, DAY)
    before = _file().read_bytes()

    def boom(src, dst):
        raise OSError("디스크 오류(시험)")

    monkeypatch.setattr(cap.os, "replace", boom)
    with pytest.raises(OSError):
        cap.save(500000, 1, DAY)
    assert _file().read_bytes() == before
    assert not list(_file().parent.glob(".capital-*.tmp"))


# ── AC2 · AC3 계산 ────────────────────────────────────────────────────────


def test_ac2_numbers_and_existing_fields_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ac2(monkeypatch)
    client = TestClient(app)
    before = client.get("/holdings/enriched").json()
    assert before["capital"]["status"] == "NOT_ENTERED"
    assert before["capital"]["total_krw"] is None
    assert before["capital"]["total_reason"] == "NO_CASH"
    assert all(i["cash_inclusive_weight_pct"] is None for i in before["items"])

    res = client.put(
        "/holdings/capital-context",
        json={"cash_krw": 400000, "limit_krw": 100000, "confirmed_on": DAY},
    )
    assert res.status_code == 200, res.text
    after = client.get("/holdings/enriched").json()
    c = after["capital"]
    assert c["holdings_value"] == 600000.0
    assert c["total_krw"] == 1000000.0  # 한도 10만은 더하지 않음
    assert c["holdings_share_pct"] == 60.0 and c["cash_share_pct"] == 40.0
    assert c["complete"] is True and c["priced_rows"] == 2 == c["holdings_rows"]
    assert c["price_date"] == {"state": "KNOWN", "min": DAY, "max": DAY}
    assert c["same_day"] is True
    row = next(i for i in after["items"] if i["ticker"] == "069500")
    assert row["market_weight_pct"] == 20.0  # 보유 내(현금 제외)
    assert row["cash_inclusive_weight_pct"] == 12.0
    # 기존 칸(매입 비중 · 손익 · 시장 비중)은 자금 저장 전과 같다.
    strip = [
        {k: v for k, v in i.items() if k != "cash_inclusive_weight_pct"}
        for i in after["items"]
    ]
    assert strip == [
        {k: v for k, v in i.items() if k != "cash_inclusive_weight_pct"}
        for i in before["items"]
    ]


def _rows(evals: list[Optional[float]], asofs: Optional[list[Optional[str]]] = None):
    class R:
        def __init__(self, e, a):
            self.eval_amount = e
            self.price_asof = a

    asofs = asofs or [ASOF] * len(evals)
    return [R(e, a) for e, a in zip(evals, asofs)]


def _entered(cash: Optional[int], limit: Optional[int] = None, day: str = DAY) -> dict:
    return {
        "status": "ENTERED",
        "cash_krw": cash,
        "limit_krw": limit,
        "confirmed_on": day,
        "saved_at": None,
    }


NOT_ENTERED = {
    "status": "NOT_ENTERED",
    "cash_krw": None,
    "limit_krw": None,
    "confirmed_on": None,
    "saved_at": None,
}
READ_FAILED = {**NOT_ENTERED, "status": "READ_FAILED"}


def test_partial_valuation_does_not_compute_total_but_keeps_cash() -> None:
    cv = cap.view(_rows([120000.0, None]), _entered(400000, 100000))
    assert cv["complete"] is False and cv["total_krw"] is None
    assert cv["total_reason"] == "PARTIAL"
    assert cv["holdings_share_pct"] is None and cv["cash_share_pct"] is None
    assert cv["cash_krw"] == 400000 and cv["limit_krw"] == 100000
    assert cap.with_cash_pct(120000.0, cv) is None
    lines = cap.preview_lines(cv, None)
    assert "부분 합계 1/2종목" in lines[0]
    assert "보유 + 입력 현금 합계 계산 안 함(보유 일부 시세 미확인)" in lines


def test_cash_not_entered_vs_zero_vs_total_zero() -> None:
    rows = _rows([600000.0])
    ne = cap.view(rows, NOT_ENTERED)
    assert ne["total_krw"] is None and ne["total_reason"] == "NO_CASH"
    zero = cap.view(rows, _entered(0))
    assert zero["total_krw"] == 600000.0
    assert zero["holdings_share_pct"] == 100.0 and zero["cash_share_pct"] == 0.0
    # 보유 없음 · 현금 0 → 합계 0원은 알려진 금액 · 구성만 계산 불가
    t0 = cap.view([], _entered(0))
    assert t0["total_krw"] == 0 and t0["total_reason"] is None
    assert t0["holdings_share_pct"] is None and t0["cash_share_pct"] is None
    assert t0["price_date"]["state"] == "NO_HOLDINGS"
    lines = cap.preview_lines(t0, {"kind": "candidate", "held": False})
    assert any(ln.startswith("보유 + 입력 현금 합계 0원(") for ln in lines)
    assert any("보유 · 현금 구성 계산 불가(합계 0원)" in ln for ln in lines)
    assert "가격 기준일 대상 없음" in lines[0]


def test_no_holdings_with_cash_is_all_cash() -> None:
    cv = cap.view([], _entered(400000))
    assert cv["total_krw"] == 400000 and cv["cash_share_pct"] == 100.0
    assert cv["holdings_share_pct"] == 0.0


def test_read_failed_never_becomes_zero() -> None:
    cv = cap.view(_rows([600000.0]), READ_FAILED)
    assert cv["total_krw"] is None and cv["total_reason"] == "READ_FAILED"
    lines = cap.preview_lines(cv, None)
    assert (
        "자금 기준 읽기 실패" in lines[1] and "0원 · 무제한으로 보지 않음" in lines[1]
    )
    assert not any(ln.startswith("보유 + 입력 현금 합계") for ln in lines)


PRICE_DATES = [
    ("모두 확인일과 같음", [ASOF, ASOF], DAY, "KNOWN", True),
    (
        "범위 안에 확인일 · 같다고 보지 않음",
        ["2026-11-04T15:00:00+09:00", "2026-11-06T15:00:00+09:00"],
        DAY,
        "KNOWN",
        False,
    ),
    ("모두 같은 날 · 확인일과 다름", [ASOF, ASOF], "2026-11-06", "KNOWN", False),
    ("날짜를 못 읽은 행", [ASOF, None], DAY, "UNKNOWN", None),
    ("날짜 모양 아님", [ASOF, "어제"], DAY, "UNKNOWN", None),
]


@pytest.mark.parametrize(
    "label,asofs,day,state,same", PRICE_DATES, ids=[p[0] for p in PRICE_DATES]
)
def test_price_date_rule(label, asofs, day, state, same) -> None:
    if day > cap.today_kst().isoformat():
        pytest.skip("시험 기계 날짜가 확인일보다 이름")
    cv = cap.view(_rows([100.0, 200.0], asofs), _entered(100, None, day))
    assert cv["price_date"]["state"] == state
    assert cv["same_day"] is same
    text = " ".join(cap.preview_lines(cv, None))
    if same is True:
        assert "가격 기준일과 현금 확인일이 같은 합계" in text
    elif same is False:
        assert "가격 기준일과 현금 확인일이 다른 참고 합계" in text
        assert "같은 합계" not in text
    else:
        assert "가격 기준일 확인 불가" in text and "같은 합계" not in text.replace(
            "같은 기준일 합계로 보지 않음", ""
        )
    if label.startswith("범위"):
        assert cv["price_date"] == {
            "state": "KNOWN",
            "min": "2026-11-04",
            "max": "2026-11-06",
        }
        assert "가격 기준일 2026-11-04 ~ 2026-11-06" in text


def test_none_priced_holdings() -> None:
    cv = cap.view(_rows([None, None]), _entered(100))
    assert cv["price_date"]["state"] == "NONE_PRICED" and cv["total_krw"] is None
    first = cap.preview_lines(cv, None)[0]
    assert first.startswith("보유 평가액 확인 불가 · 부분 합계 0/2종목")  # '0원' 아님
    assert "0원" not in first


# ── API 경계 ────────────────────────────────────────────────────────────


def test_put_errors_422_and_500_keep_file(monkeypatch: pytest.MonkeyPatch) -> None:
    _ac2(monkeypatch)
    client = TestClient(app)
    ok = client.put(
        "/holdings/capital-context",
        json={"cash_krw": 400000, "limit_krw": None, "confirmed_on": DAY},
    )
    assert ok.status_code == 200 and ok.json()["limit_krw"] is None
    before = _file().read_bytes()
    bad = client.put(
        "/holdings/capital-context",
        json={"cash_krw": 100, "limit_krw": 200, "confirmed_on": DAY},
    )
    assert bad.status_code == 422
    assert (
        bad.json()["detail"]
        == "추가 투입 한도가 검토에 포함할 현금보다 클 수 없습니다."
    )
    # 빠진 칸은 '비움'으로 보지 않는다.
    missing = client.put("/holdings/capital-context", json={"cash_krw": 100})
    assert missing.status_code == 422
    assert _file().read_bytes() == before

    _file().write_text("{broken", encoding="utf-8")
    res = client.put(
        "/holdings/capital-context",
        json={"cash_krw": None, "limit_krw": None, "confirmed_on": None},
    )
    # 문구 머리 = 화면의 '쓰기 전 거절' 판정 근거(CapitalContextPanel.refusedBeforeWrite)
    assert res.status_code == 500 and res.json()["detail"].startswith(
        "자금 기준 파일 손상"
    )
    assert _file().read_text(encoding="utf-8") == "{broken"
    # 자금 읽기 실패여도 보유 조회는 200 · 보유 칸 그대로
    body = client.get("/holdings/enriched").json()
    assert body["capital"]["status"] == "READ_FAILED"
    assert body["capital"]["cash_krw"] is None and body["capital"]["total_krw"] is None
    assert len(body["items"]) == 2 and body["items"][0]["market_weight_pct"] is not None


def test_capital_save_never_touches_holdings_document(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC8 — 자금 저장 뒤 holdings_latest.json(「보유 OCI 반영」 대상)에 자금 값이 없다."""
    _ac2(monkeypatch)
    before = holdings_module.HOLDINGS_FILE.read_bytes()
    client = TestClient(app)
    for body in (
        {"cash_krw": 400000, "limit_krw": 100000, "confirmed_on": DAY},
        {"cash_krw": None, "limit_krw": None, "confirmed_on": None},
    ):
        assert client.put("/holdings/capital-context", json=body).status_code == 200
    assert holdings_module.HOLDINGS_FILE.read_bytes() == before
    text = holdings_module.HOLDINGS_FILE.read_text(encoding="utf-8")
    assert "cash_krw" not in text and "limit_krw" not in text
    assert _file().parent == holdings_module.HOLDINGS_FILE.parent


def test_gitignore_names_the_exact_private_file() -> None:
    lines = Path(".gitignore").read_text(encoding="utf-8").splitlines()
    assert "state/holdings/capital_context.json" in lines
    assert "state/holdings/.capital-*.tmp" in lines  # 저장 중 임시 파일(개인 금액)


# ── AC3 · AC5 미리보기 [보유 · 자금 기준] ───────────────────────────────


def test_holding_lines_ac2_exact(monkeypatch: pytest.MonkeyPatch) -> None:
    _ac2(monkeypatch)
    cap.save(400000, 100000, DAY)
    lines = api_decision_draft_preview._load_capital_lines("069500", "holding")
    assert lines == [
        f"보유 평가액 600,000원 · 2/2종목 전체 · 가격 기준일 {DAY} · 현금 제외 · 모든 계좌 합산",
        f"검토에 포함할 현금 400,000원 · 이번 검토의 추가 투입 한도 100,000원 · 확인일 {DAY} · "
        "직접 입력한 확인일 기준 값 · 거래/입출금 후 자동 반영되지 않음",
        "보유 + 입력 현금 합계 1,000,000원(이 보유 목록과 입력 현금의 평가 합계 · 투자 총예산 · 전체 재산 아님 · "
        "한도는 더하지 않음) · 보유 60.00% · 현금 40.00% · 가격 기준일과 현금 확인일이 같은 합계",
        "이 종목 비중(같은 종목 모든 계좌 합산): 보유 내 20.00%(현금 제외) · 입력 현금 포함 12.00%",
    ]


def test_limit_undecided_and_not_entered_lines(monkeypatch: pytest.MonkeyPatch) -> None:
    _ac2(monkeypatch)
    ne = api_decision_draft_preview._load_capital_lines("069500", "holding")
    assert ne[1] == (
        "검토에 포함할 현금 미입력(0원 아님) · 추가 투입 한도 미입력 — 합계 · 현금 포함 비중 계산 안 함"
    )
    assert (
        ne[2]
        == "이 종목 비중(같은 종목 모든 계좌 합산): 보유 내 20.00%(현금 제외) · 입력 현금 포함 계산 안 함"
    )
    cap.save(400000, None, DAY)
    lines = api_decision_draft_preview._load_capital_lines("069500", "holding")
    assert "이번 검토의 추가 투입 한도 미정(현금 전액을 한도로 보지 않음)" in lines[1]


def test_multi_account_rows_vs_ticker_aggregate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _two_accounts(monkeypatch)
    cap.save(400000, None, DAY)
    items = TestClient(app).get("/holdings/enriched").json()["items"]
    rows = sorted(
        (i["account_group"], i["cash_inclusive_weight_pct"])
        for i in items
        if i["ticker"] == "069500"
    )
    assert rows == [("연금저축", 4.0), ("일반", 12.0)]  # 화면 = 계좌 행 단위
    lines = api_decision_draft_preview._load_capital_lines("069500", "holding")
    assert lines[-1] == (
        "이 종목 비중(같은 종목 모든 계좌 합산): 보유 내 26.67%(현금 제외) · 입력 현금 포함 16.00%"
    )
    # 원문에 계좌 이름 · 개별 종목 평가금액 · 수량 · 평단 없음
    text = "\n".join(lines)
    for leak in (
        "연금저축",
        "일반",
        "160,000",
        "120,000",
        "40,000",
        "38,000",
        "39,000",
        "3주",
    ):
        assert leak not in text


def test_candidate_held_unpriced_and_not_held(monkeypatch: pytest.MonkeyPatch) -> None:
    _two_accounts(monkeypatch)
    cap.save(400000, None, DAY)
    held = api_decision_draft_preview._load_capital_lines("069500", "candidate")
    assert held[-1] == (
        "이 종목: 후보 · 현재 보유 중 — 같은 종목 모든 계좌 합산: "
        "보유 내 26.67%(현금 제외) · 입력 현금 포함 16.00%"
    )
    other = api_decision_draft_preview._load_capital_lines("379800", "candidate")
    assert other[-1] == "이 종목: 후보 · 현재 보유 아님 — 보유 비중 없음"


def test_held_candidate_with_unpriced_row_stays_held(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _two_accounts(monkeypatch, second_price=None)  # 069500 두 계좌 모두 시세 없음
    cap.save(400000, None, DAY)
    lines = api_decision_draft_preview._load_capital_lines("069500", "candidate")
    assert lines[-1] == (
        "이 종목: 후보 · 현재 보유 중 — 같은 종목 모든 계좌 합산: 보유 내 미확인 · 입력 현금 포함 미확인"
        "(같은 종목 일부 계좌 행 시세 미확인)"
    )
    assert "부분 합계 1/3종목" in lines[0]
    assert lines[2] == "보유 + 입력 현금 합계 계산 안 함(보유 일부 시세 미확인)"
    # 이 종목은 평가됐지만 다른 종목이 미평가 → 보유 내 비중은 부분 평가액 기준이라고 적는다.
    other = api_decision_draft_preview._load_capital_lines("360750", "holding")
    assert other[-1] == (
        "이 종목 비중(같은 종목 모든 계좌 합산): 보유 내 100.00%(현금 제외 · 부분 평가액 기준) · "
        "입력 현금 포함 계산 안 함"
    )


def test_holdings_unreadable_gives_one_unknown_line(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    holdings_module.HOLDINGS_DIR.mkdir(parents=True, exist_ok=True)
    holdings_module.HOLDINGS_FILE.write_text("{broken", encoding="utf-8")
    lines = api_decision_draft_preview._load_capital_lines("379800", "candidate")
    assert lines == [
        "보유 · 자금 기준 확인 불가 — 보유 자료를 읽지 못했습니다(0원으로 보지 않음)."
    ]


@pytest.mark.parametrize("kind", ["깨진 UTF-8", "같은 이름 폴더"])
def test_holdings_read_errors_like_candidate_path(kind: str) -> None:
    """후보 경로(decision_preview_sources)가 잡는 OSError · ValueError 를 같이 잡는다."""
    holdings_module.HOLDINGS_DIR.mkdir(parents=True, exist_ok=True)
    if kind == "깨진 UTF-8":
        holdings_module.HOLDINGS_FILE.write_bytes(b"\xff\xfe\x00broken")
    else:
        holdings_module.HOLDINGS_FILE.mkdir()
    lines = api_decision_draft_preview._load_capital_lines("379800", "candidate")
    assert lines == [
        "보유 · 자금 기준 확인 불가 — 보유 자료를 읽지 못했습니다(0원으로 보지 않음)."
    ]


def test_unexpected_capital_failure_marks_only_this_section(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ac2(monkeypatch)
    from app import market_cache

    def boom():
        raise RuntimeError("시세 캐시 시험 오류")

    monkeypatch.setattr(market_cache, "get_all", boom)
    lines = api_decision_draft_preview._load_capital_lines("069500", "holding")
    assert lines == [cap.UNBUILT_LINE]
    assert "0원으로 보지 않음" in cap.UNBUILT_LINE


WEIGHT_NOTES = [
    ("같은 기준일", [ASOF, ASOF], DAY, ""),
    (
        "기준일 다름",
        [ASOF, ASOF],
        "2026-11-06",
        "(기준일이 다른 참고 비중)",
    ),
    (
        "가격 기준일 확인 불가",
        [ASOF, None],
        DAY,
        "(가격 기준일 확인 불가 — 같은 기준일 비중으로 보지 않음)",
    ),
]


@pytest.mark.parametrize(
    "label,asofs,day,note", WEIGHT_NOTES, ids=[w[0] for w in WEIGHT_NOTES]
)
def test_cash_weight_carries_same_date_note(label, asofs, day, note) -> None:
    """설계 B-3 — 기준일이 다르면 합계뿐 아니라 '입력 현금 포함' 비중도 참고 값으로 적는다."""
    if day > cap.today_kst().isoformat():
        pytest.skip("시험 기계 날짜가 확인일보다 이름")
    cv = cap.view(_rows([100.0, 300.0], asofs), _entered(100, None, day))
    target = {
        "kind": "holding",
        "held": True,
        "weight_in": 25.0,
        "weight_with_cash": cap.with_cash_pct(100.0, cv),
        "unknown": False,
        "partial": False,
    }
    last = cap.preview_lines(cv, target)[-1]
    assert last == (
        "이 종목 비중(같은 종목 모든 계좌 합산): 보유 내 25.00%(현금 제외) · "
        f"입력 현금 포함 20.00%{note}"
    )
    # 비중을 계산하지 않으면 표시도 붙이지 않음
    ne = cap.view(_rows([100.0, 300.0], asofs), NOT_ENTERED)
    t2 = {**target, "weight_with_cash": None}
    assert cap.preview_lines(ne, t2)[-1].endswith("입력 현금 포함 계산 안 함")


def test_candidate_preview_survives_unreadable_holdings(
    preview_client: TestClient,
) -> None:
    holdings_module.HOLDINGS_DIR.mkdir(parents=True, exist_ok=True)
    holdings_module.HOLDINGS_FILE.write_bytes(b"\xff\xfe\x00broken")
    body = preview_client.post(
        "/decision-draft/preview", json={"target_kind": "candidate", "ticker": "379800"}
    ).json()
    assert body["status"] == "ok"
    assert _section(body["preview_text"], SECTION) == (
        f"{SECTION}\n- 보유 · 자금 기준 확인 불가 — 보유 자료를 읽지 못했습니다(0원으로 보지 않음)."
    )


def test_ai_request_has_capital_premise_line() -> None:
    assert AI_REQUEST[-1] == (
        "현금 보유를 추가 매수 승인으로 해석하지 말고, [보유 · 자금 기준]의 추가 투입 한도 · 확인일 · "
        "포함 범위를 전제로 검토해 주세요(한도가 미정 · 미입력이면 그 상태 그대로)."
    )


@pytest.fixture
def tmp_db(tmp_path: Path) -> Path:
    from app.market_data_store import init_db

    db = tmp_path / "market_data.sqlite"
    init_db(db)
    return db


@pytest.fixture
def preview_client(
    monkeypatch: pytest.MonkeyPatch, tmp_db: Path, tmp_path: Path
) -> TestClient:
    """근거 묶음 로더만 가짜(시장 참고는 빈 tmp DB) · 자금 줄은 실제 `_load_capital_lines`."""
    monkeypatch.setattr(api_decision_draft_preview, "DEFAULT_DB_PATH", tmp_db)
    monkeypatch.setattr(
        api_decision_draft_preview,
        "_load_holdings_evidence",
        lambda t: {
            "ticker": t,
            "name": "시험 069500",
            "market_weight_pct": 20.0,
            "pnl_rate_pct": 9.09,
            "bundle": None,
        },
    )
    monkeypatch.setattr(
        api_decision_draft_preview,
        "_load_candidate_evidence",
        lambda t, q: {
            "candidate": {"ticker": t, "name": "시험 후보", "rank": 1},
            "basis": "1m",
        },
    )
    fake = tmp_path / "decision_evidence.sqlite"
    monkeypatch.setattr(decision_evidence_store, "DEFAULT_DB_PATH", fake)
    monkeypatch.setattr(api_decision_sessions, "DEFAULT_DB_PATH", fake)
    return TestClient(app)


def _titles(text: str) -> list[str]:
    return [sec.split("\n", 1)[0] for sec in text.split("\n\n")]


def _section(text: str, title: str) -> str:
    return next(s for s in text.split("\n\n") if s.startswith(title))


def test_preview_order_target_line_and_only_four_amounts(
    monkeypatch: pytest.MonkeyPatch, preview_client: TestClient
) -> None:
    _ac2(monkeypatch)
    cap.save(400000, 100000, DAY)
    for kind, ticker in (
        ("holding", "069500"),
        ("candidate", "069500"),
        ("candidate", "379800"),
    ):
        body = preview_client.post(
            "/decision-draft/preview", json={"target_kind": kind, "ticker": ticker}
        ).json()
        assert body["status"] == "ok", body
        text = body["preview_text"]
        titles = _titles(text)
        assert titles[:3] == ["[대상]", SECTION, "[시장]"]
        assert titles[3].startswith("[시장 흐름")
        assert titles[-2:] == ["[AI에게 요청]", "[검토 질문]"]
        assert "평가비중" not in text
        sec = _section(text, SECTION)
        amounts = set(re.findall(r"([\d,]+)원", sec))
        assert amounts == {
            "600,000",
            "400,000",
            "100,000",
            "1,000,000",
        }  # V · C · A · T 만
        # 다른 묶음에는 원 단위 금액이 없다.
        assert not re.findall(r"[\d,]+원", text.replace(sec, ""))
        assert AI_REQUEST[-1] in text
    hold = preview_client.post(
        "/decision-draft/preview", json={"target_kind": "holding", "ticker": "069500"}
    ).json()["preview_text"]
    assert (
        _section(hold, "[대상]").split("\n")[2]
        == "- 손익률 +9.09% · 비중은 [보유 · 자금 기준]에 적음"
    )


def test_preview_survives_capital_read_failure(
    monkeypatch: pytest.MonkeyPatch, preview_client: TestClient
) -> None:
    _ac2(monkeypatch)
    _file().write_text("{broken", encoding="utf-8")
    body = preview_client.post(
        "/decision-draft/preview", json={"target_kind": "holding", "ticker": "069500"}
    ).json()
    assert body["status"] == "ok"
    sec = _section(body["preview_text"], SECTION)
    assert "자금 기준 읽기 실패" in sec and "보유 + 입력 현금 합계" not in sec
    assert _file().read_text(encoding="utf-8") == "{broken"


def test_saved_session_keeps_text_generated_before_capital_edit(
    monkeypatch: pytest.MonkeyPatch, preview_client: TestClient
) -> None:
    """AC6 — 생성 당시 값이 원문에 고정 · 자금 수정 뒤 저장 세션 · 옛 원문은 그대로 · 새 생성만 새 값."""
    _ac2(monkeypatch)
    cap.save(400000, 100000, DAY)
    first = preview_client.post(
        "/decision-draft/preview", json={"target_kind": "holding", "ticker": "069500"}
    ).json()
    text = first["preview_text"]
    sp = {
        "target_kind": "holding",
        "generated_at": first["generated_at"],
        "evidence_as_of": first["evidence_as_of"],
        "preview_text": text,
    }
    payload = dict(
        # 세션 기준일 = 가격 기준일(없으면 생성 시각의 KST 날짜) — POC5-24 규칙
        asof=first["evidence_as_of"]["target_as_of_date"] or first["generated_at"][:10],
        source_screen=SELECTED_PREVIEW_SOURCE_SCREEN,
        filters={
            "exclude_inverse": True,
            "exclude_leveraged": False,
            "exclude_synthetic": True,
            "exclude_futures": True,
        },
        candidate_snapshot=[
            {
                "rank": None,
                "ticker": "069500",
                "name": "시험 069500",
                "tags": [],
                "selected_preview": sp,
            }
        ],
        question_text=text,
        gpt_answer_text="시험 답변",
        user_memo="",
        user_verdict="hold",
        next_checks=[],
    )
    res = preview_client.post("/decision/sessions", json=payload)
    assert res.status_code == 200, res.text
    rid = res.json()["id"]

    cap.save(900000, 50000, DAY)
    rec = preview_client.get(f"/decision/sessions/{rid}").json()["record"]
    assert rec["question_text"] == text
    assert rec["candidate_snapshot"][0]["selected_preview"]["preview_text"] == text
    assert "400,000원" in rec["question_text"]
    again = preview_client.post(
        "/decision-draft/preview", json={"target_kind": "holding", "ticker": "069500"}
    ).json()["preview_text"]
    assert "900,000원" in again and "400,000원" not in again


def test_build_preview_text_without_capital_lines_keeps_section() -> None:
    from app.market_data_store import init_db

    db = holdings_module.HOLDINGS_DIR.parent / "m.sqlite"
    init_db(db)
    res = build_preview_text(
        target_kind="holding",
        ticker="069500",
        target_evidence={
            "ticker": "069500",
            "name": "시험",
            "pnl_rate_pct": 1.0,
            "bundle": None,
        },
        db_path=db,
    )
    sec = _section(res.preview_text or "", SECTION)
    assert (
        sec
        == f"{SECTION}\n- 보유 · 자금 기준 확인 불가 — 보유 자료를 읽지 못했습니다(0원으로 보지 않음)."
    )
