"""POC2 Cleanup — NAV Discount Source Diagnosis 의 judge / record / markdown
helper 분리 (2026-06-14).

`scripts/diagnose_nav_discount_source.py` 의 KS-10 trigger 해소를 위해 source-
level 판정 + 균일 레코드 빌더 + 리포트 렌더링을 본 모듈로 이관했다. 산식 / 문구 /
판정 기준 변경 0건. 함수 시그니처 그대로.

본 모듈은 진단 1회용 helper 모음 — 운영 backend / API 에서 import 되지 않는다.
"""

from __future__ import annotations

from typing import Optional

# ─── source-level 판정 ────────────────────────────────────────────────


def judge_pykrx_ohlcv(per_ticker_results: dict) -> dict:
    """pykrx ohlcv 결과를 source-level 로 통합 판정."""
    any_ok = False
    any_has_nav = False
    any_has_price = False
    for _ticker, dates in per_ticker_results.items():
        for r in dates.values():
            if r.get("status") == "ok":
                any_ok = True
                if r.get("has_nav"):
                    any_has_nav = True
                if r.get("has_market_price"):
                    any_has_price = True
    if not any_ok:
        return {
            "judgment": "unusable",
            "reason": "모든 ticker × 날짜 조합에서 ok 응답 0건 (empty / call_failed).",
        }
    if any_has_nav and any_has_price:
        return {
            "judgment": "adopt_candidate",
            "reason": (
                "ohlcv 응답에 NAV + 시장가격 동시 제공. 기존 etf_nav_daily schema "
                "(nav / market_price) 와 직접 매핑 가능."
            ),
        }
    if any_has_nav:
        return {
            "judgment": "hold_unstable",
            "reason": "NAV 만 제공되거나 시장가격 키 매핑 실패.",
        }
    return {
        "judgment": "hold_unstable",
        "reason": "ohlcv 응답에 NAV 키 부재.",
    }


def judge_pykrx_deviation(per_ticker_results: dict) -> dict:
    any_ok = False
    any_has_dev = False
    for _ticker, dates in per_ticker_results.items():
        for r in dates.values():
            if r.get("status") == "ok":
                any_ok = True
                if r.get("has_discount_rate"):
                    any_has_dev = True
    if not any_ok:
        return {
            "judgment": "unusable",
            "reason": "모든 ticker × 날짜 조합 empty / call_failed.",
        }
    if any_has_dev:
        return {
            "judgment": "adopt_candidate",
            "reason": "괴리율 직접 제공. 기존 compute_discount_rate_pct 와 충돌 없음.",
        }
    return {
        "judgment": "hold_unstable",
        "reason": "응답은 있으나 괴리율 키 매핑 실패.",
    }


def judge_fdr(per_ticker_results: dict) -> dict:
    ok_count = 0
    price_count = 0
    for r in per_ticker_results.values():
        if r.get("status") == "ok":
            ok_count += 1
            if r.get("has_market_price"):
                price_count += 1
    if ok_count == 0:
        return {
            "judgment": "unusable",
            "reason": "FDR DataReader 응답 0건.",
        }
    if price_count >= 1:
        return {
            "judgment": "hold_unstable",
            "reason": (
                "FDR 은 시장 종가만 제공 — NAV 직접 제공 안 함. NAV source 와 결합 "
                "시 괴리율 계산 후보. 단독 adopt_candidate 아님."
            ),
        }
    return {
        "judgment": "unusable",
        "reason": "FDR 응답은 있으나 시장가격 키 매핑 실패.",
    }


def judge_naver_integration(per_ticker_results: dict) -> dict:
    ok_count = 0
    nav_count = 0
    price_count = 0
    dev_count = 0
    asof_count = 0
    for r in per_ticker_results.values():
        if r.get("status") == "ok":
            ok_count += 1
            if r.get("has_nav"):
                nav_count += 1
            if r.get("has_market_price"):
                price_count += 1
            if r.get("has_discount_rate"):
                dev_count += 1
            if r.get("has_asof"):
                asof_count += 1
    if ok_count == 0:
        return {
            "judgment": "unusable",
            "reason": "Naver integration API 모든 ticker call_failed.",
        }
    if nav_count == ok_count and price_count == ok_count and dev_count == ok_count:
        return {
            "judgment": "hold_unstable",
            "reason": (
                f"NAV / 시장가격 / 괴리율 모두 {ok_count}/{ok_count} 제공 "
                f"(asof={asof_count}/{ok_count}). 비공식 endpoint — schema 변경 / 차단 "
                "위험 + 운영 안정성 별도 검증 권장. 안정성 진단 후 adopt 승격 가능."
            ),
        }
    if nav_count > 0 and price_count > 0:
        return {
            "judgment": "hold_unstable",
            "reason": (
                f"NAV={nav_count}/{ok_count} / 시장가격={price_count}/{ok_count} / "
                f"괴리율={dev_count}/{ok_count} / asof={asof_count}/{ok_count}. "
                "비공식 endpoint — 운영 안정성 별도 검증 권장."
            ),
        }
    return {
        "judgment": "hold_unstable",
        "reason": (
            f"NAV={nav_count}/{ok_count} / 시장가격={price_count}/{ok_count} / "
            f"괴리율={dev_count}/{ok_count} / asof={asof_count}/{ok_count}. 키 매핑 불완전."
        ),
    }


def judge_naver_etf_detail(per_ticker_results: dict) -> dict:
    """ETF dedicated endpoint — 404 가 많으면 unusable / NAV 키 흔적 있으면 hold."""
    any_200 = False
    any_nav_mention = False
    for r in per_ticker_results.values():
        for c in r.get("candidates", []):
            if c.get("http_status") == 200:
                any_200 = True
                if c.get("mentions_nav"):
                    any_nav_mention = True
    if not any_200:
        return {
            "judgment": "unusable",
            "reason": "ETF dedicated endpoint 후보 모두 HTTP 200 응답 0건.",
        }
    if any_nav_mention:
        return {
            "judgment": "hold_unstable",
            "reason": (
                "ETF dedicated endpoint 일부 응답 + NAV / 괴리 단어 흔적. 비공식 "
                "endpoint — schema 검증 + 안정성 추가 진단 필요."
            ),
        }
    return {
        "judgment": "hold_unstable",
        "reason": "응답은 있으나 NAV / 괴리 흔적 부재.",
    }


# ─── 균일 레코드 빌더 (AC-2 필드 계약) ───────────────────────────────


def _record_from(
    source_id: str,
    ticker: str,
    res: dict,
    judgment: str,
    extra: Optional[dict] = None,
) -> dict:
    rec = {
        "source_id": source_id,
        "ticker": ticker,
        "call_status": res.get("status"),
        "http_status": res.get("http_status"),
        "has_nav": bool(res.get("has_nav")),
        "has_market_price": bool(res.get("has_market_price")),
        "has_discount_rate": bool(res.get("has_discount_rate")),
        "has_asof": bool(res.get("has_asof") or res.get("asof") is not None),
        "error_type": res.get("error_type"),
        "judgment": judgment,
    }
    if extra:
        rec.update(extra)
    return rec


def _build_flat_records(
    *,
    pykrx_ohlcv_results: dict,
    pykrx_ohlcv_judgment: dict,
    pykrx_dev_results: dict,
    pykrx_dev_judgment: dict,
    fdr_results: dict,
    fdr_judgment: dict,
    naver_int_results: dict,
    naver_int_judgment: dict,
    naver_etf_results: dict,
    naver_etf_judgment: dict,
) -> list[dict]:
    """source × ticker 단위 균일 레코드 리스트 — AC-2 필드 계약 충족."""
    records: list[dict] = []

    # pykrx ohlcv: ticker 당 마지막 시도 결과 1건 (가장 최근 시도).
    for ticker, dates in pykrx_ohlcv_results.items():
        last_res = None
        last_date = None
        for d, r in dates.items():
            last_res, last_date = r, d
            if r.get("status") == "ok":
                break
        if last_res is not None:
            records.append(
                _record_from(
                    "pykrx_etf_ohlcv",
                    ticker,
                    last_res,
                    pykrx_ohlcv_judgment["judgment"],
                    {"attempted_date": last_date},
                )
            )

    for ticker, dates in pykrx_dev_results.items():
        last_res = None
        last_date = None
        for d, r in dates.items():
            last_res, last_date = r, d
            if r.get("status") == "ok":
                break
        if last_res is not None:
            records.append(
                _record_from(
                    "pykrx_etf_price_deviation",
                    ticker,
                    last_res,
                    pykrx_dev_judgment["judgment"],
                    {"attempted_date": last_date},
                )
            )

    for ticker, res in fdr_results.items():
        records.append(
            _record_from(
                "finance_data_reader",
                ticker,
                res,
                fdr_judgment["judgment"],
            )
        )

    for ticker, res in naver_int_results.items():
        records.append(
            _record_from(
                "naver_mobile_stock_integration",
                ticker,
                res,
                naver_int_judgment["judgment"],
            )
        )

    for ticker, res in naver_etf_results.items():
        candidates = res.get("candidates", []) if isinstance(res, dict) else []
        any_200 = any(c.get("http_status") == 200 for c in candidates)
        any_nav = any(c.get("mentions_nav") for c in candidates)
        any_dev = any(c.get("mentions_deviation") for c in candidates)
        summary = {
            "status": "ok" if any_200 else "call_failed",
            "http_status": next(
                (c.get("http_status") for c in candidates if c.get("http_status")),
                None,
            ),
            "has_nav": any_nav,
            "has_market_price": False,
            "has_discount_rate": any_dev,
            "has_asof": False,
        }
        records.append(
            _record_from(
                "naver_mobile_etf_detail",
                ticker,
                summary,
                naver_etf_judgment["judgment"],
                {"candidates_checked": len(candidates)},
            )
        )

    return records


# ─── 진단 리포트 markdown 렌더 ────────────────────────────────────────


def render_markdown(artifact: dict) -> str:
    lines: list[str] = []
    lines.append("# ETF NAV / Discount Source Diagnosis 1차")
    lines.append("")
    lines.append(f"작성: {artifact['finished_at']}")
    lines.append("성격: 진단 전용 — 운영 fetcher 교체 / source integration 없음.")
    lines.append("")
    lines.append("## 1. 진단 대상 sample ticker")
    lines.append("")
    lines.append("| ticker | name | category | reason |")
    lines.append("| --- | --- | --- | --- |")
    for s in artifact["samples"]:
        lines.append(
            f"| `{s['ticker']}` | {s['name']} | {s['category']} | {s['reason']} |"
        )
    lines.append("")
    lines.append("## 2. source별 판정")
    lines.append("")
    lines.append("| source_id | category | judgment | 핵심 사유 |")
    lines.append("| --- | --- | --- | --- |")
    for sid, src in artifact["sources"].items():
        lines.append(
            f"| `{sid}` | {src['category']} | **{src['judgment']}** | {src['reason']} |"
        )
    lines.append("")
    lines.append("## 3. source별 상세")
    lines.append("")
    for sid, src in artifact["sources"].items():
        lines.append(f"### {sid}")
        lines.append("")
        lines.append(f"- judgment: **{src['judgment']}**")
        lines.append(f"- reason: {src['reason']}")
        lines.append("")
        lines.append("샘플 결과 (ticker × 최초 ok / 최후 시도):")
        lines.append("")
        for ticker, content in src["per_ticker"].items():
            if isinstance(content, dict) and "status" in content:
                lines.append(
                    f"  - `{ticker}`: status={content.get('status')} "
                    f"has_nav={content.get('has_nav')} "
                    f"has_price={content.get('has_market_price')} "
                    f"has_dev={content.get('has_discount_rate')}"
                )
            elif isinstance(content, dict):
                for d, r in content.items():
                    lines.append(
                        f"  - `{ticker}` @ {d}: status={r.get('status')} "
                        f"has_nav={r.get('has_nav')} "
                        f"has_price={r.get('has_market_price')} "
                        f"has_dev={r.get('has_discount_rate')}"
                    )
        lines.append("")
    lines.append("## 4. 기존 schema fit")
    lines.append("")
    lines.append(
        "- `etf_nav_daily` 컬럼: etf_ticker / asof / nav / market_price / "
        "discount_rate_pct / source / status / message."
    )
    lines.append(
        "- pykrx 후보가 `adopt_candidate` 일 경우 시장가격은 ohlcv 종가, NAV 는 "
        "NAV 컬럼, source 라벨은 `pykrx/etf_ohlcv` 권장."
    )
    lines.append(
        "- 괴리율은 source 가 직접 제공하면 그 값을 우선 사용, 그렇지 않으면 기존 "
        "`compute_discount_rate_pct(nav, market_price)` 재사용."
    )
    lines.append("")
    lines.append("## 5. K6 / EOD 방어 가능성")
    lines.append("")
    lines.append(
        "- pykrx 후보: 단일 호출 1초 내외 / 1ticker = 1API call. 10개 후보 + delay 적용 "
        "가능, 30초 budget 안에 들어옴. cache-first / 실패 격리 패턴 적용 가능."
    )
    lines.append(
        "- Naver mobile 후보: 비공식 — 차단 / schema 변경 위험. K6 적용은 채택 결정 후 "
        "별도 운영 안정성 STEP 에서 검증."
    )
    lines.append("")
    lines.append("## 6. 결론 / 다음 STEP 추천")
    lines.append("")
    adopt_sources = [
        sid
        for sid, src in artifact["sources"].items()
        if src["judgment"] == "adopt_candidate"
    ]
    if adopt_sources:
        lines.append(
            f"- adopt_candidate 발견: {', '.join(adopt_sources)}. 다음 STEP 후보: "
            "`NAV_DISCOUNT_SOURCE_INTEGRATION_1` — 본 진단 결과를 입력으로 운영 "
            "fetcher 교체 설계."
        )
    else:
        lines.append(
            "- adopt_candidate 0건. 다음 STEP 후보: 사용자 결정 — 다른 빈자리 (구성종목 "
            "가격 시계열 / 위험 감지 지표 시계열) 로 이동하거나 KRX OPEN API "
            "(auth_required) 확보 검토."
        )
    lines.append("")
    lines.append("## 7. 본 STEP 에서 하지 않은 것")
    lines.append("")
    lines.append("- 운영 NAV fetcher 교체.")
    lines.append("- NAV / 괴리율 source integration.")
    lines.append("- 전체 universe NAV 수집 / 정기 job 추가.")
    lines.append("- 신규 API / 괴리율 threshold 변경 / Telegram 변경.")
    lines.append("")
    return "\n".join(lines)
