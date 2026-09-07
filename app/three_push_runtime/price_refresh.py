"""Runtime price refresh helper (Low-Frequency Telegram Push Operation v1 A+).

Runner 로부터 분리한 가격 조회 책임. Runner 는 이 함수의 반환값 (성공 quotes +
진단 dict) 을 받아 Fail-Closed 판정만 수행한다.

Fail-Closed 계약 (사용자 A+ 확정):
- 가격 전건 실패 → Runner 가 failed 종료.
- 가격 일부 실패 → Runner 가 failed 종료 (partial 발송 금지).
- Naver 예외 자체 → Runner 가 failed 종료.
- attempted==0 (Market 등 refresh 불필요) → 정상 진행.

이 함수 자체는 정책 판정을 하지 않고 raw 결과만 반환한다.
"""

from __future__ import annotations

from typing import Any, Optional


def refresh_runtime_quotes(
    push_kind: str,
    collect_target_tickers,  # Callable[[str], list[str]] — Fail-Closed: 예외 propagate
) -> tuple[dict[str, Any], dict[str, Any], Optional[str]]:
    """Runtime price refresh 수행.

    반환:
        (market_quotes, diag, error_str)
        market_quotes: {ticker: MarketQuote} — 조회 성공만.
        diag: {"attempted": n, "success": n, "failed": n,
               "failed_tickers": [...], "target_tickers": [...],
               "success_tickers": [...]}.
              refresh 불필요한 push_kind 는 {"attempted":0,"success":0,"failed":0}.

              ⚠️ `attempted` 는 `collect_target_tickers` 가 돌려준 **행 수**다.
              보유는 같은 종목을 여러 계좌에서 들고 있어 행 수(32)와 고유 ticker
              수(29)가 다르다. **완전성 판정에는 `attempted` 를 쓰지 말고
              `target_tickers` / `success_tickers` 집합을 쓴다** (설계자 확정
              2026-09-05).
        error_str: 예외 발생 시 "TypeName: msg[:200]" · 성공 시 None.
                   Runner 는 error_str is not None 이면 failed 로 종료.
    """
    market_quotes: dict[str, Any] = {}
    diag: dict[str, Any] = {"attempted": 0, "success": 0, "failed": 0}
    if push_kind not in (
        "holdings_briefing",
        "spike_or_falling_alert",
        "holdings_risk_alert",
    ):
        return market_quotes, diag, None
    try:
        tickers = collect_target_tickers(push_kind)
    except Exception as e:  # noqa: BLE001
        return market_quotes, diag, f"{type(e).__name__}: {str(e)[:200]}"
    if not tickers:
        return market_quotes, diag, None
    try:
        from app import market_naver

        results = market_naver.fetch_many(tickers)
    except Exception as e:  # noqa: BLE001
        diag["error"] = f"{type(e).__name__}"
        return market_quotes, diag, f"{type(e).__name__}: {str(e)[:200]}"
    for r in results:
        if r.quote is not None:
            market_quotes[r.ticker] = r.quote
    diag = {
        "attempted": len(tickers),
        "success": sum(1 for r in results if r.quote is not None),
        "failed": sum(1 for r in results if r.quote is None),
        "failed_tickers": sorted({r.ticker for r in results if r.quote is None}),
        # 완전성 판정용 집합 (설계자 확정) — 행 수가 아니라 고유 ticker 다.
        "target_tickers": sorted(set(tickers)),
        "success_tickers": sorted({r.ticker for r in results if r.quote is not None}),
    }
    return market_quotes, diag, None


# 부분 실패를 허용하는 push_kind (설계자 확정 2026-09-05 · OPS-02A PLAN §4.6
# "부분 실패 — 오늘 quote 하나라도 있으면 실패 종목만 표시하고 진행").
# 두 종류 모두 **같은 보유 원장**을 대상으로 하므로 계약이 같다. 여기서 끊으면
# `데이터 확인 필요` 표시가 실제 OCI 경로에서 영영 나오지 않는다.
PARTIAL_TOLERANT_KINDS = ("holdings_briefing", "holdings_risk_alert")


def evaluate_price_refresh(
    diag: dict, *, push_kind: str, logger
) -> Optional[tuple[str, str, str]]:
    """refresh 결과 판정. 차단이면 `(status, reason, detail)`, 진행이면 None.

    Fail-Closed 계약 (사용자 확정):
      attempted == 0 → skip 대상 없음(Market 등) · 정상 진행.
      전건 실패      → failed (runtime_price_all_failed).
      일부 실패      → failed (runtime_price_partial_failed) · 미발송.
                       단 `PARTIAL_TOLERANT_KINDS` 는 진행.
    """
    attempted = diag.get("attempted", 0)
    success = diag.get("success", 0)
    failed = diag.get("failed", 0)
    if attempted <= 0:
        return None
    logger.info(
        "runtime price refresh: attempted=%d success=%d failed=%d",
        attempted,
        success,
        failed,
    )
    if success == 0:
        return (
            "failed",
            "runtime_price_all_failed",
            f"attempted={attempted} failed={failed}",
        )
    if failed > 0:
        if push_kind not in PARTIAL_TOLERANT_KINDS:
            return (
                "failed",
                "runtime_price_partial_failed",
                f"attempted={attempted} success={success} failed={failed}",
            )
        logger.warning(
            "보유 시세 일부 실패 %d건 — 해당 종목만 '데이터 확인 필요' 로 진행",
            failed,
        )
    return None
