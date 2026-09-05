"""Runner record 진단 필드 forward 실행 회귀 (FIX r6 검증자 지적 대응).

Cleanup / FIX r7 Round 3B 에서 `tests/test_runtime_evidence_composer.py` 로부터 분리.
"""

from __future__ import annotations

from pathlib import Path

from app.runtime_evidence_composer import (
    RuntimeEvidenceResult,
    SRC_HOLDINGS,
    SRC_MARKET_DISCOVERY,
    SRC_NAV_DISCOUNT,
)


def test_holdings_briefing_runner_record_forwards_all_diagnostics_r6(
    tmp_path: Path, monkeypatch
) -> None:
    """FIX r6: runner 실행 후 record 에 진단 10 필드 실제 전달.

    monkeypatch 로 compose_runtime_evidence + 부수효과 (DB write / Telegram) 를
    차단하고 실제 run() 을 호출해 반환된 record 를 검사.
    """
    from app.three_push_runtime_param import RuntimeParam
    import scripts.run_three_push_runtime_oci as runner_mod

    fake_evidence = RuntimeEvidenceResult(
        available_sources={
            SRC_HOLDINGS: "available",
            SRC_NAV_DISCOUNT: "available",
            SRC_MARKET_DISCOVERY: "available",
        },
        extra_notes=["KODEX 200 (2026-07-11 기준): Market Discovery TOP1."],
        diagnostics={
            "contentful_fact_count": 1,
            "selection_result_count": 1,
            "unavailable_reasons": {},
            "holdings_snapshot_status": "available",
            "holdings_snapshot_reason": "",
            "holdings_loaded_count": 35,
            "holdings_evidence_item_count": 35,
            "holdings_contentful_fact_count": 35,
            "nav_contentful_fact_count": 32,
            "holdings_selection_result_count": 35,
            "rendered_holdings_fact_count": 35,
            "private_fields_exposed": False,
            "raw_identifier_exposed": False,
        },
    )
    fake_param = RuntimeParam(
        param_id="test-p",
        created_at="2026-07-11T00:00:00+00:00",
        approved_at="2026-07-11T00:00:00+00:00",
        approved_by="test",
        param_source="manual",
        enabled_push_kinds=["holdings_briefing"],
        runtime_policy={},
        evidence_policy={},
        safety_policy={},
    )
    # Low-Frequency Telegram Push Operation v1: compose_runtime_evidence 시그니처
    # 에 market_quotes / universe_reevaluate_fn 파라미터 추가됨. mock 도 **kw 수신.
    monkeypatch.setattr(
        runner_mod, "compose_runtime_evidence", lambda pk, **kw: fake_evidence
    )
    # Runner 는 holdings_briefing 시 market_naver.fetch_many 를 호출한다. 실 네트워크
    # 차단.
    import sys
    import types

    fake_naver = types.ModuleType("app.market_naver")
    fake_naver.fetch_many = lambda tickers, timeout=15.0: []
    monkeypatch.setitem(sys.modules, "app.market_naver", fake_naver)
    monkeypatch.setattr(
        runner_mod, "read_active_param_dict", lambda: fake_param.to_dict()
    )
    monkeypatch.setattr(runner_mod, "param_from_dict", lambda d: fake_param)
    monkeypatch.setattr(runner_mod, "insert_status_from_record", lambda r: None)
    monkeypatch.setattr(runner_mod, "_HISTORY_PATH", tmp_path / "history.jsonl")
    monkeypatch.setattr(
        runner_mod, "telegram_send", lambda *a, **kw: (False, "blocked_by_test")
    )
    monkeypatch.setattr(
        runner_mod, "build_runtime_message", lambda **kw: "test body 2026-07-11"
    )
    # Low-Frequency Telegram Push Operation v1 A+ Fail-Closed:
    # holdings_briefing 은 이제 target_tickers 가 파일 존재를 강제한다. 이 test 는
    # composer 자체를 mock 하므로 실 file 없이 진행 · target_tickers 도 stub.
    monkeypatch.setattr(runner_mod, "_collect_target_tickers", lambda pk: ["TEST"])
    # market_naver 가 fetch_many 시 quote (asof 포함) 반환하도록.
    import types as _t

    def _now_kst_iso() -> str:
        from datetime import datetime, timedelta, timezone

        return (
            datetime.now(timezone.utc)
            .astimezone(timezone(timedelta(hours=9)))
            .strftime("%Y-%m-%dT%H:%M:%S+09:00")
        )

    class _R:
        def __init__(self, t):
            self.ticker = t
            from app.market_cache import MarketQuote

            self.quote = MarketQuote(
                ticker=t,
                name=None,
                current_price=100.0,
                # 2026-09-04 POC3-OPS-01A — 비거래일 가드가 `price_asof`
                # 날짜를 본다. 과거 고정일이면 휴장일로 판정돼 skip 된다.
                price_asof=_now_kst_iso(),
                price_source="naver",
            )

    fake2 = _t.ModuleType("app.market_naver")
    fake2.fetch_many = lambda tickers, timeout=15.0: [_R(t) for t in tickers]
    monkeypatch.setitem(sys.modules, "app.market_naver", fake2)
    from app import market_naver as _mn2

    monkeypatch.setattr(_mn2, "fetch_many", fake2.fetch_many)

    # 2026-09-04 POC3-OPS-01A — 선정 경로는 evidence composer 가 아니라
    # `app.holdings.load` 를 직접 읽는다. 35건을 그대로 공급한다.
    from dataclasses import dataclass as _dc

    @_dc
    class _H:
        ticker: str
        name: str
        account_group: str = "일반"

    import app.holdings as _holdings_mod

    monkeypatch.setattr(
        _holdings_mod,
        "load",
        lambda *a, **k: [_H(f"T{i:04d}", f"종목{i:02d}") for i in range(35)],
    )

    # Low-Frequency Telegram Push Operation v1: holdings_briefing 은 slot_id 필수.
    record = runner_mod.run("holdings_briefing", "dry-run", slot_id="OPEN")

    # 2026-09-04 POC3-OPS-01A — 보유 브리핑이 evidence 조립 경로를 타지 않는다.
    # 전량 나열(종목당 2줄) 대신 선정 결과만 렌더하므로 evidence composer 진단
    # (`holdings_snapshot_status` · `nav_contentful_fact_count` ·
    # `rendered_holdings_fact_count`)은 더 이상 생성되지 않는다. 선정 진단이
    # 그 자리를 대신하고, **안전 신호 2개는 그대로 유지**한다.
    assert "holdings_snapshot_status" not in record
    assert record["holdings_loaded_count"] == 35
    assert record["holdings_unique_ticker_count"] == 35
    assert "holdings_selected_count" in record
    assert record["private_fields_exposed"] is False
    assert record["raw_identifier_exposed"] is False
    assert record["telegram_attempted"] is False
    assert record["telegram_sent"] is False
