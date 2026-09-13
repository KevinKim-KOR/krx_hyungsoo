"""POC2 Step 5D Cleanup — 테스트 공유 헬퍼 / 상수.

설계자 결정 (Step 5D 지시문 §4.1):
- conftest.py 는 fixture 만 둔다 (autouse + 명시).
- 헬퍼 함수와 상수는 본 _helpers.py 에 모아 두고 각 테스트 파일에서 명시 import.
- 헬퍼 의미 / 검증 강도 / 동작은 분리 전과 동일 — 위치만 이동.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi.testclient import TestClient

from app import market_cache

# ─── POC1 ────────────────────────────────────────────────────────────


_VALID_INPUT = {
    "title": "테스트 초안",
    "recommendations": [{"ticker": "069500", "score": 0.5, "action": "HOLD"}],
    "note": "테스트 본문",
}


def _generate(client: TestClient, input_data: dict) -> tuple[int, dict]:
    r = client.post("/runs/generate", json={"input_data": input_data})
    try:
        return r.status_code, r.json()
    except ValueError:
        return r.status_code, {}


# Step2 / Step5D-2 분리 시점 — holdings put/get/draft 흐름의 표준 입력 (name 누락 케이스 포함).
_VALID_HOLDINGS = [
    {"ticker": "069500", "name": "KODEX 200", "quantity": 10, "avg_buy_price": 38500},
    {"ticker": "091160", "quantity": 5, "avg_buy_price": 22000},  # name 생략
]


# ─── POC2 Step 2B (draft_message focus 빌더) ────────────────────────


def _make_holding_rec(
    ticker: str,
    *,
    name: Optional[str] = None,
    quantity: float = 10,
    avg_buy_price: float = 10000,
    current_price: Optional[float] = None,
    pnl_rate_pct: Optional[float] = None,
    market_weight_pct: Optional[float] = None,
    action: str = "HOLD",
    reason: Optional[str] = None,
) -> dict[str, object]:
    """Step 2B 테스트용 recommendation dict 빌더.

    current_price=None 이면 시세 키를 통째로 제외 (Step 2 정책 준수).
    pnl_rate_pct/market_weight_pct 도 None 이면 키 제외.
    """
    from app import draft_message

    invested = quantity * avg_buy_price
    rec: dict[str, object] = {
        "ticker": ticker,
        "name": name or ticker,
        "quantity": quantity,
        "avg_buy_price": avg_buy_price,
        "invested_amount": invested,
        "buy_weight_pct": 0,  # 테스트는 비중 정확도까지 보지 않음
        "action": action,
        "reason": reason if reason is not None else draft_message.DEFAULT_HOLD_REASON,
    }
    if current_price is not None:
        rec["current_price"] = current_price
        rec["eval_amount"] = quantity * current_price
        rec["pnl_amount"] = quantity * current_price - invested
    if pnl_rate_pct is not None:
        rec["pnl_rate_pct"] = pnl_rate_pct
    if market_weight_pct is not None:
        rec["market_weight_pct"] = market_weight_pct
    return rec


# ─── POC2 Step 2C (holdings dict 빌더) ──────────────────────────────


def _holding_dict(
    ticker: str,
    quantity: float,
    avg_buy_price: float,
    name: Optional[str] = None,
    account_group: Optional[str] = None,
) -> dict:
    """테스트용 holdings 단건 dict. account_group 미지정 시 키 자체 생략."""
    d: dict = {
        "ticker": ticker,
        "quantity": quantity,
        "avg_buy_price": avg_buy_price,
    }
    if name is not None:
        d["name"] = name
    if account_group is not None:
        d["account_group"] = account_group
    return d


# ─── POC2 Step 2D (holdings 표준 입력) ──────────────────────────────


_VALID_HOLDINGS_FOR_2D = [
    {
        "ticker": "069500",
        "name": "KODEX 200",
        "quantity": 3,
        "avg_buy_price": 84190,
        "account_group": "일반",
    },
    {
        "ticker": "0013P0",
        "name": "RISE 미국은행TOP10",
        "quantity": 5,
        "avg_buy_price": 10050,
        "account_group": "ISA",
    },
]


# ─── POC2 Step 5B (holdings momentum 통합 입력) ─────────────────────


def _put_holdings_for_momentum(client) -> None:
    """Step5B 통합 테스트용 표준 holdings 입력. 동일 ticker 다른 account_group/avg
    포함 — row 매핑 충돌 검증 케이스에서도 그대로 사용."""
    client.put(
        "/holdings",
        json={
            "holdings": [
                {
                    "ticker": "005930",
                    "name": "삼성전자",
                    "quantity": 5,
                    "avg_buy_price": 70000,
                    "account_group": "일반",
                },
                {
                    "ticker": "005930",
                    "name": "삼성전자",
                    "quantity": 10,
                    "avg_buy_price": 75000,
                    "account_group": "일반",
                },
                {
                    "ticker": "069500",
                    "name": "KODEX 200",
                    "quantity": 3,
                    "avg_buy_price": 84190,
                    "account_group": "ISA",
                },
            ]
        },
    )
    market_cache.upsert_many(
        [
            market_cache.MarketQuote(
                ticker="005930",
                name="삼성전자",
                current_price=80000.0,
                price_asof=None,
                price_source="naver",
            ),
            market_cache.MarketQuote(
                ticker="069500",
                name="KODEX 200",
                current_price=100000.0,
                price_asof=None,
                price_source="naver",
            ),
        ]
    )


# ─── POC2 Step 3 (factor signals 단위 테스트용 enriched 빌더) ───────


def _enriched_for_factor(
    rows: list[dict],
):
    """factor 단위 테스트용 EnrichedHolding 리스트 빌더."""
    from app.holdings_enrich import EnrichedHolding

    out: list = []
    for idx, r in enumerate(rows):
        out.append(
            EnrichedHolding(
                ticker=r["ticker"],
                name=r.get("name"),
                quantity=float(r.get("quantity", 1)),
                avg_buy_price=float(r.get("avg_buy_price", 1000)),
                invested_amount=float(r.get("invested_amount", 0)),
                current_price=r.get("current_price"),
                price_asof=r.get("price_asof"),
                price_source=r.get("price_source"),
                eval_amount=r.get("eval_amount"),
                pnl_amount=r.get("pnl_amount"),
                pnl_rate_pct=r.get("pnl_rate_pct"),
                buy_weight_pct=r.get("buy_weight_pct"),
                market_weight_pct=r.get("market_weight_pct"),
                price_missing=r.get("price_missing", False),
                calc_missing=r.get("calc_missing", False),
                account_group=r.get("account_group", "일반"),
                source_index=idx,
            )
        )
    return out


# ─── POC2 Step 5C (universe seed 빌더) ──────────────────────────────


def _write_seed(path: Path, payload: dict) -> None:
    import json as _json

    path.write_text(_json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _seed_payload(asof: str, items: Optional[list] = None) -> dict:
    return {
        "asof": asof,
        "source": "manual_seed",
        "items": (
            items
            if items is not None
            else [
                {
                    "ticker": "379800",
                    "name": "KODEX 미국 S&P500",
                    "universe_group": "미국지수",
                    "sector_or_theme": "S&P500",
                },
                {
                    "ticker": "069500",
                    "name": "KODEX 200",
                    "universe_group": "한국지수",
                    "sector_or_theme": "KOSPI200",
                },
            ]
        ),
    }


def stub_market_briefing_ready(monkeypatch, *, message_text="시장 브리핑 본문"):
    """`market_briefing` 이 발송 가능한 상태로 조립됐다고 둔다.

    POC3-OPS-02B-2 에서 `market_briefing` 에 **국내 거래일 Gate** 와 정합성·
    최신성 Gate 가 붙었다. 그 입력(07:20 결과·가격 창)이 없으면 조립이 미발송으로
    떨어지는 것이 **설계대로의 동작**이다.

    (2026-09-13 정정: 캘린더 부재는 더 이상 차단 사유가 아니다 — 평일이면 통과
    시키는 사용자 운영정책으로 바뀌었다. 여기서 stub 하는 이유는 캘린더가 아니라
    정합성·가격 창 입력이 없기 때문이다.)

    그런데 partial delivery·registry·reeval 계약을 검사하는 기존 테스트들은
    `market_briefing` 을 **본문이 나오는 범용 push_kind** 로 써 왔다. 그 계약들은
    시장 브리핑과 무관하므로, 조립 단계만 통과시키고 **검사 대상은 그대로 둔다.**

    Gate 자체는 `tests/test_market_briefing_contracts.py` 가 따로 고정한다.
    """
    from app.market_briefing import flow
    from app.three_push_runtime import runner_market_briefing as _mb

    def _ready(record, *, push_kind, **kwargs):
        if push_kind != _mb.PUSH_KIND:
            return None
        record["message_text_length"] = len(message_text)
        return flow.BriefingOutcome(message_text=message_text, fingerprint="UP#NONE")

    monkeypatch.setattr(_mb, "assemble", _ready)


def patch_compose_runtime_evidence(monkeypatch, fake):
    """§4 legacy evidence 조립 결과를 `fake` 로 고정한다.

    POC3-OPS-02B-2 KS-10 Cleanup 에서 §4 조립이 러너에서
    `runner_evidence.assemble_legacy_evidence` 로 빠지면서 import 도 함께
    옮겨졌다. helper 가 **호출 시점에** 원천 모듈에서 가져오므로 러너 속성이
    아니라 **원천**을 갈아끼운다.

    검사 대상(입력·본문·status·reason)은 이전과 같다.
    """
    import app.runtime_evidence_composer as _rec

    monkeypatch.setattr(_rec, "compose_runtime_evidence", lambda pk, **kw: fake)
