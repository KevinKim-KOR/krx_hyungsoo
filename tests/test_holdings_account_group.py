"""POC2 Step 5D-2 Cleanup — Step2C account_group.

분리 출처: tests/test_holdings_draft_flow.py (Step 5D-2 이전 단일 파일).
테스트 의미 / 검증 강도 / 동작은 분리 전과 동일.
"""

from __future__ import annotations

import pytest

from app import holdings as holdings_module, store

from tests._helpers import _holding_dict


def test_step2c_account_group_default_when_missing(client):
    """기존 holdings 항목에 account_group 이 없어도 백엔드 로드 단계에서 '일반' 으로
    정상 처리된다 (하위 호환성)."""
    payload = {
        "holdings": [
            _holding_dict("069500", 10, 38500),  # account_group 누락
        ]
    }
    r = client.put("/holdings", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["holdings"][0]["account_group"] == "일반"


def test_step2c_account_group_custom_persisted(client):
    """직접 입력한 account_group 라벨이 저장/조회된다."""
    payload = {
        "holdings": [
            _holding_dict("069500", 10, 38500, account_group="키움-일반"),
            _holding_dict("0013P0", 5, 10050, account_group="ISA"),
        ]
    }
    r = client.put("/holdings", json=payload)
    assert r.status_code == 200

    r2 = client.get("/holdings")
    assert r2.status_code == 200
    items = r2.json()["holdings"]
    groups = [it["account_group"] for it in items]
    assert "키움-일반" in groups
    assert "ISA" in groups


def test_step2c_account_group_blank_normalized_to_general(client):
    """빈 account_group 은 '일반' 으로 정규화된다 (저장 단계)."""
    payload = {
        "holdings": [
            _holding_dict("069500", 10, 38500, account_group="   "),
            _holding_dict("0013P0", 5, 10050, account_group=""),
        ]
    }
    r = client.put("/holdings", json=payload)
    assert r.status_code == 200
    body = r.json()
    for item in body["holdings"]:
        assert item["account_group"] == "일반"


def test_step2c_account_group_over_30_chars_rejected(client):
    """account_group 30자 초과는 422 validation error 로 차단된다 (잘리지 않음)."""
    too_long = "a" * 31
    payload = {
        "holdings": [
            _holding_dict("069500", 10, 38500, account_group=too_long),
        ]
    }
    r = client.put("/holdings", json=payload)
    assert r.status_code == 422
    # 저장 안 됨 확인
    r2 = client.get("/holdings")
    assert r2.json()["holdings"] == []


def test_step2c_account_group_default_label_case_normalized(client):
    """isa / Isa / ISA 는 모두 'ISA' 로 정규화된다.
    일반/연금/오픈뱅킹/기타는 한국어이므로 trim 만 적용."""
    payload = {
        "holdings": [
            _holding_dict("069500", 10, 38500, account_group="isa"),
            _holding_dict("0013P0", 5, 10050, account_group="Isa"),
            _holding_dict("379800", 50, 17303, account_group="ISA"),
        ]
    }
    r = client.put("/holdings", json=payload)
    assert r.status_code == 200
    body = r.json()
    for item in body["holdings"]:
        assert item["account_group"] == "ISA"


def test_step2c_account_group_normalize_helper_unit():
    """단일 helper normalize_account_group 의 직접 단위 테스트.
    저장/draft/load 모든 진입점이 동일 helper 를 거치므로 helper 자체 동작 보장."""
    from app.holdings import (
        ACCOUNT_GROUP_DEFAULT,
        HoldingsValidationError,
        normalize_account_group,
    )

    # 기본값
    assert normalize_account_group(None) == ACCOUNT_GROUP_DEFAULT
    assert normalize_account_group("") == ACCOUNT_GROUP_DEFAULT
    assert normalize_account_group("   ") == ACCOUNT_GROUP_DEFAULT

    # 기본 추천값 정규화
    assert normalize_account_group("isa") == "ISA"
    assert normalize_account_group("Isa") == "ISA"
    assert normalize_account_group("ISA") == "ISA"
    assert normalize_account_group(" 일반 ") == "일반"
    assert normalize_account_group("연금") == "연금"
    assert normalize_account_group("오픈뱅킹") == "오픈뱅킹"
    assert normalize_account_group("기타") == "기타"

    # 사용자 커스텀 라벨은 의미 변경 없이 trim 만
    assert normalize_account_group("키움-ISA") == "키움-ISA"
    assert normalize_account_group("  Kiwoom-ISA  ") == "Kiwoom-ISA"

    # 30자 초과 차단
    with pytest.raises(HoldingsValidationError):
        normalize_account_group("a" * 31)

    # 정확히 30자는 통과
    assert normalize_account_group("a" * 30) == "a" * 30


def test_step2c_holdings_load_legacy_file_without_account_group(tmp_path, monkeypatch):
    """state/holdings/holdings_latest.json 이 account_group 없는 구버전 형식이어도
    load() 가 깨지지 않고 '일반' 으로 정규화한다."""
    import json as _json

    legacy_dir = tmp_path / "holdings_legacy"
    legacy_dir.mkdir()
    legacy_file = legacy_dir / "holdings_latest.json"
    legacy_file.write_text(
        _json.dumps(
            {
                "holdings": [
                    {
                        "ticker": "069500",
                        "quantity": 3.0,
                        "avg_buy_price": 84190.0,
                        "name": "KODEX 200",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(holdings_module, "HOLDINGS_DIR", legacy_dir)
    monkeypatch.setattr(holdings_module, "HOLDINGS_FILE", legacy_file)

    loaded = holdings_module.load()
    assert len(loaded) == 1
    assert loaded[0].account_group == "일반"


def test_step2c_duplicate_policy_allows_split_avg_price(client):
    """동일 ticker + 동일 account_group 이라도 avg_buy_price 가 다르면 허용 (분할매수)."""
    payload = {
        "holdings": [
            _holding_dict("005930", 10, 70000, account_group="일반"),
            _holding_dict("005930", 5, 75000, account_group="일반"),
        ]
    }
    r = client.put("/holdings", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert len(body["holdings"]) == 2


def test_step2c_duplicate_policy_blocks_exact_triple(client):
    """동일 (ticker, account_group, avg_buy_price) 삼중 중복은 차단."""
    payload = {
        "holdings": [
            _holding_dict("005930", 10, 70000, account_group="일반"),
            _holding_dict("005930", 99, 70000, account_group="일반"),
        ]
    }
    r = client.put("/holdings", json=payload)
    assert r.status_code == 422


def test_step2c_new_draft_payload_includes_account_group(client):
    """신규 draft_payload.recommendations[] 에 account_group 이 포함된다."""
    payload = {
        "holdings": [
            _holding_dict("069500", 10, 38500, account_group="ISA"),
            _holding_dict("0013P0", 5, 10050, account_group="키움-일반"),
        ]
    }
    client.put("/holdings", json=payload)
    r = client.post("/runs/generate-from-holdings")
    assert r.status_code == 200
    body = r.json()
    recs = body["draft_payload"]["recommendations"]
    assert len(recs) == 2
    groups = [rec["account_group"] for rec in recs]
    assert groups == ["ISA", "키움-일반"]
    # source_index 도 부여되어야 한다 (UI key 안정성)
    indices = [rec["source_index"] for rec in recs]
    assert indices == [0, 1]


def test_step2c_old_draft_payload_without_account_group_still_loadable():
    """과거 draft_payload.recommendations[] 에 account_group 이 없어도 백엔드 처리가
    KeyError / 예외 없이 동작한다 (compute_summary / build_message_text)."""
    from app import draft_message

    legacy_payload = {
        "title": "보유 종목 기반 초안 (legacy)",
        "asof": "2026-04-01T00:00:00+00:00",
        "note": "이전 버전 draft_payload",
        "recommendations": [
            {
                "ticker": "069500",
                "name": "KODEX 200",
                "quantity": 3,
                "avg_buy_price": 84190,
                "invested_amount": 252570,
                "buy_weight_pct": 100.0,
                "action": "HOLD",
                "reason": "보유 종목 현황 (이번 단계는 추천 판단 없이 HOLD 고정)",
            }
        ],
    }
    # 식별, 요약, 메시지 빌드 모두 KeyError 없이 동작
    assert draft_message.is_holdings_draft(legacy_payload) is True
    summary = draft_message.compute_summary(legacy_payload["recommendations"])
    assert summary["total_count"] == 1
    msg = draft_message.build_message_text("run_legacy", legacy_payload)
    assert "run_legacy" in msg


def test_step2c_old_draft_payload_renders_through_run_endpoint(client, monkeypatch):
    """과거 형식 draft_payload (account_group 없음) 가 store 에 있어도 GET /runs/{id} 가
    안전하게 렌더링된다 (전체 라이프사이클 호환성)."""
    from app.models import Run

    legacy_run = Run(
        run_id="run_legacy_001",
        asof="2026-04-01T00:00:00+00:00",
        status="PENDING_APPROVAL",
        draft_payload={
            "title": "Legacy",
            "asof": "2026-04-01T00:00:00+00:00",
            "note": "legacy",
            "recommendations": [
                {
                    "ticker": "069500",
                    "quantity": 3,
                    "avg_buy_price": 84190,
                    "invested_amount": 252570,
                    "action": "HOLD",
                    "reason": "보유 종목 현황 (이번 단계는 추천 판단 없이 HOLD 고정)",
                    # account_group / source_index 없음
                }
            ],
        },
    )
    store.save(legacy_run)

    r = client.get(f"/runs/{legacy_run.run_id}")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "PENDING_APPROVAL"
    # draft_payload 내용은 변경되지 않고 그대로 (강제 마이그레이션 안 함)
    rec = body["draft_payload"]["recommendations"][0]
    assert "account_group" not in rec  # 강제 추가 금지


def test_step2c_calc_missing_not_zeroed_per_account_group_aggregation():
    """계좌별 PnL 계산 원금이 시세 확인/계산 가능 종목 매입금액 합산분만 사용되는지를
    백엔드 helper 차원에서 보장 (compute_summary 가 calc_invested 만 사용)."""
    from app.draft_message import compute_summary

    recs = [
        # 계산 가능 (priced + eval/invested 유효)
        {
            "ticker": "069500",
            "quantity": 10,
            "avg_buy_price": 38500,
            "invested_amount": 385000,
            "current_price": 40000,
            "eval_amount": 400000,
            "pnl_amount": 15000,
            "pnl_rate_pct": 3.9,
            "action": "HOLD",
            "reason": "x",
            "account_group": "일반",
        },
        # 계산 정보 부족 (current_price 있는데 eval/invested 누락)
        # - invested_amount 누락 → calc_missing 분류
        {
            "ticker": "0013P0",
            "quantity": 5,
            "avg_buy_price": 10050,
            "current_price": 10000,
            "action": "HOLD",
            "reason": "x",
            "account_group": "ISA",
        },
        # 시세 미확인
        {
            "ticker": "0035T0",
            "quantity": 5,
            "avg_buy_price": 14185,
            "invested_amount": 70925,
            "action": "HOLD",
            "reason": "x",
            "account_group": "ISA",
        },
    ]
    s = compute_summary(recs)
    # calc_available 만 PnL 계산용 원금에 들어가야 함
    assert s["calc_available_count"] == 1
    assert s["unpriced_count"] == 1
    assert s["calc_missing_count"] == 1
    # 평가금액/손익은 calc_available 종목 기준
    assert s["priced_eval"] == 400000
    assert s["priced_pnl"] == 15000
    # 계산 정보 부족 종목을 0 으로 취급하지 않는다
    # (1종목만 계산 가능 → 손익률은 그 종목의 invested_amount 385,000 기준만 사용)
    assert abs(s["priced_pnl_rate_pct"] - (15000 / 385000 * 100.0)) < 1e-6
    # 전체 매입금액(표시용)은 invested_amount 가 있는 항목만 합산 (385,000 + 70,925)
    assert s["total_invested"] == 385000 + 70925


# ─── POC2 Step 2D: approval draft preview separation ────────────
