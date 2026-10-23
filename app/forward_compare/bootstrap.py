"""POC6-06 — 초기 장기 가격 1회 조회 · 초기 회고 예제(설계 §3-1 · PLAN §2 · 승인 뒤 실행).

```text
조회   cohort 24종 · 종목당 1회 · 재시도 없음 · 요청 시간 제한 = 기존 `fdr_request_timeout()`
       기존 `market_data_fdr` 읽기 부분만(`_default_price_fetcher` · `_dataframe_to_price_rows`)
       라이브 DB 쓰기 0
       구간 = 연구 축 첫날(05 KOSPI 저장일 object 첫날) ~ 오늘 KST · 오늘 KST 이상 행 = 진행 중 봉으로 뺌
저장   bootstrap/<id>/prices.json(종목별 한 수신 판) → fetch.json(로그 · prices 해시) · 이미 있으면 조회 거절
예제   한 수신 판의 종가를 06 `AxisSeries` 로 축에 맞춤 · 창 [i-60, i+20] 통과
       목표 끝 axis[i+20] < 첫 예측 D
       252 이상 = initial_trainable · 미달 = DATA_SHORT(분모 유지 · 교체 없음)
```

같은 응답에서 계산한 change 와의 일치는 가격 조정의 정확성 증거가 아니다(설계 §3-1). 오래된 운영 가격 ·
05 120일 창 · KRX 무조정 가격을 이어 붙이거나 대체하지 않는다.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable, Optional

from app import market_data_fdr as fdr_mod
from app.forward_compare import protocol as P
from app.ml_evidence import store
from app.reentry_review import model as m06
from app.reentry_review import prices as px
from app.three_push_runtime.market_data_batch import fdr_request_timeout

ORIGIN = "BOOTSTRAP_RETROSPECTIVE"
LIBS = ("finance-datareader", "pandas", "requests")


class BootstrapRefused(Exception):
    """승인 범위 밖 조회 거절(이미 초기 자료가 있음 · cohort 없음) — 조회 0."""


def folders(root: Path) -> list[Path]:
    base = root / "bootstrap"
    if not base.is_dir():
        return []
    return sorted(
        p for p in base.iterdir() if p.is_dir() and (p / "fetch.json").is_file()
    )


@P.exclusive
def fetch(
    root: Path,
    cohort: dict[str, Any],
    *,
    start: str,
    clock: Callable[[], datetime],
    fetcher: Optional[Callable] = None,
) -> tuple[str, dict]:
    """한 묶음 조회 — 종목마다 한 번. 실패는 그 종목 기록으로 남기고 다음 종목으로(재시도 0)."""
    base = root / "bootstrap"
    if base.exists() and any(base.iterdir()):
        raise BootstrapRefused(
            "초기 자료 폴더가 이미 있음 — 다시 조회하지 않음(승인 = 1회)"
        )
    get = fetcher or fdr_mod._default_price_fetcher
    started = clock()
    today = P.kst_day(started)
    log, tickers = [], {}
    for t in cohort["tickers"]:
        entry: dict[str, Any] = {
            "ticker": t,
            "requested": [start, today],
            "status": None,
        }
        entry["started_at"] = store.iso(clock())
        try:
            with fdr_request_timeout():
                df = get(t, date.fromisoformat(start), date.fromisoformat(today))
            got = fdr_mod._dataframe_to_price_rows(t, df)
        except Exception as e:  # noqa: BLE001 — 종목 단위 실패 기록(재시도 없음)
            entry.update(
                status="FAILED",
                error=f"{type(e).__name__}: {e}"[:200],
                timeout=fdr_mod._is_request_timeout(e),
                finished_at=store.iso(clock()),
            )
            log.append(entry)
            continue
        observed = store.iso(clock())
        kept = [r for r in got if r.date < today]
        entry.update(
            finished_at=observed,
            rows=len(kept),
            dropped_in_progress=len(got) - len(kept),
            returned_first=kept[0].date if kept else None,
            returned_last=kept[-1].date if kept else None,
            status="OK" if kept else "NO_DATA",
        )
        log.append(entry)
        if kept:
            tickers[t] = {
                "observed_at": observed,
                "rows": [
                    [r.date, r.open, r.high, r.low, r.close, r.volume, r.change]
                    for r in kept
                ],
            }
    bid = P.new_id(started)
    folder = root / "bootstrap" / bid
    prices = P.doc(
        "bootstrap_prices",
        id=bid,
        source=P.SOURCE,
        row_format=["date", "open", "high", "low", "close", "volume", "change"],
        tickers=tickers,
    )
    prices_sha = P.write_once(folder / "prices.json", P.dumps(prices, compact=True))
    counts = {
        s: sum(1 for e in log if e["status"] == s) for s in ("OK", "NO_DATA", "FAILED")
    }
    meta = P.doc(
        "bootstrap_fetch",
        id=bid,
        cohort_id=cohort["cohort_id"],
        started_at=store.iso(started),
        finished_at=store.iso(clock()),
        today_kst=today,
        requested_range=[start, today],
        requests=len(log),
        counts=counts,
        retries=0,
        libraries=_libs(),
        prices_sha256=prices_sha,
        log=log,
        semantics=(
            "FinanceDataReader 네이버 일봉 한 수신 판 · change = 같은 응답 종가로 계산(독립 품질 근거 아님)"
            " · 당시 가용(PIT) 자료 아님 · 오늘 KST 이상 행 제외"
        ),
    )
    P.write_once(folder / "fetch.json", P.dumps(meta))
    status = (
        "OK" if counts["OK"] == len(log) else ("PARTIAL" if counts["OK"] else "FAILED")
    )
    return status, meta


def _libs() -> dict[str, Optional[str]]:
    from importlib import metadata

    out: dict[str, Optional[str]] = {}
    for lib in LIBS:
        try:
            out[lib] = metadata.version(lib)
        except metadata.PackageNotFoundError:
            out[lib] = None
    return out


def load(root: Path) -> tuple[Path, dict, dict]:
    """유일한 초기 자료(fetch.json 의 prices 해시가 맞아야 함)."""
    found = folders(root)
    if len(found) != 1:
        raise store.EvidenceError(f"초기 자료 폴더 수 {len(found)}(1이어야 함)")
    meta = P.read_json(found[0] / "fetch.json")
    data = (found[0] / "prices.json").read_bytes()
    if store.sha256_bytes(data) != meta["prices_sha256"]:
        raise store.EvidenceError("초기 가격 파일 해시가 기록과 다름")
    return found[0], meta, json.loads(data)


def build_examples(
    prices: dict, meta: dict, axis: dict, D: str, trainable_from: Optional[list] = None
) -> dict[str, Any]:
    """초기 회고 예제 — 축 끝 = D · 목표 끝 axis[i+20] < D(첫 예측 기준일보다 이름)."""
    dates = axis["dates"]
    rows: list[list] = []
    per: dict[str, dict] = {}
    for t, body in sorted(prices["tickers"].items()):
        series = px.AxisSeries(
            dates,
            [
                px.PriceRow(r[0], r[4], P.SOURCE, body["observed_at"], r[6])
                for r in body["rows"]
            ],
        )
        excluded: dict[str, int] = {}
        n = 0
        for i in range(m06.LB, len(dates) - m06.H):
            if dates[i + m06.H] >= D:
                break
            reason = series.window_reason(i - m06.LB, i + m06.H)
            if reason:
                excluded[reason] = excluded.get(reason, 0) + 1
                continue
            x = m06.features_at(series.closes, i)
            y = m06.target_at(series.closes, i)
            rows.append(
                [t, dates[i], ORIGIN, x, y, dates[i + m06.H], body["observed_at"]]
            )
            n += 1
        per[t] = {"examples": n, "excluded_by_reason": excluded}
    missing = [t for t in P.EXPECTED_COHORT if t not in prices["tickers"]]
    for t in missing:
        per[t] = {"examples": 0, "excluded_by_reason": {}, "reason": "초기 자료 미확보"}
    trainable = [t for t in P.EXPECTED_COHORT if per[t]["examples"] >= P.MIN_EXAMPLES]
    return {
        "rows": rows,
        "per_ticker": per,
        "initial_trainable": trainable,
        "data_short": [t for t in P.EXPECTED_COHORT if t not in trainable],
        "bootstrap": {"id": meta["id"], "prices_sha256": meta["prices_sha256"]},
        "boundary_D": D,
        "available_at": meta["finished_at"],
    }
