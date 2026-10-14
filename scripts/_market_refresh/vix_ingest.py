"""VIX 서브커맨드 helper (2026-07-03 Market Risk Reference v1).

Cleanup / FIX r7 Round 2 에서 `scripts/refresh_market_timeseries.py` 로부터
분리. VIX 일별 Close 를 FDR 로 조회해 market_benchmark_daily_price 에 적재.

지시문 §5.1 / §5.2:
- 최초 실행: 2014-04-09 ~ 최신 반환일.
- 이후 실행: SQLite 마지막 저장일 다음 날짜 ~ 최신 반환일.
- 실행당 1회, 자동 재시도 없음.
- KODEX200 호출 X, ETF universe 순회 X, ML 호출 X.
- 지시문 §4.2: 기존 값과 다른 새 값은 자동 덮어쓰지 않는다 (conflict → return 2).
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Optional


def run_vix_ingest(db_path: Path, max_date: Optional[date] = None) -> int:
    """VIX ingestion 실행. 반환값 = CLI exit code (0 ok, 2 error/conflict).

    `max_date`(POC5-11 · PC 수동 갱신만 넘김): 이 날짜보다 뒤 행은 저장하지 않는다(진행 중인
    미국 세션 값이 확정 종가처럼 저장돼 다음 증분에서 다시 고쳐지지 않는 것을 막음).
    None(기본 · CLI · OCI 배치)이면 예전 동작 그대로다.
    """
    import FinanceDataReader as fdr

    from app.market_benchmark_store import (
        fetch_existing_benchmark_close_map,
        latest_benchmark_date,
        upsert_benchmark_prices,
    )

    default_vix_start = date(2014, 4, 9)
    latest = latest_benchmark_date("VIX", db_path=db_path)
    if latest:
        try:
            start = date.fromisoformat(latest) + timedelta(days=1)
        except ValueError:
            # FIX r1 (기존 계약 유지): 기존 latest 파싱 실패는 명확한 실패로 종료.
            # 자동 fallback 시 사용자가 데이터 손상을 감지하지 못한다.
            print(
                f"[vix] existing latest VIX date is unparseable: {latest!r} -- "
                "manual check required. Aborting without fallback.",
                file=sys.stderr,
            )
            return 2
    else:
        start = default_vix_start
    end = date.today()
    if start > end:
        print(f"[vix] already up to date -- latest={latest}")
        return 0
    if max_date is not None and start > max_date:
        print(
            f"[vix] already up to date -- latest={latest} (settled through {max_date})"
        )
        return 0
    if max_date is not None and not any(
        (start + timedelta(days=i)).weekday() < 5
        for i in range((max_date - start).days + 1)
    ):
        # 주말만 남았다(새 미국 거래일 없음) — 조회하면 빈 응답이 실패(rc 2)로 잡힌다.
        # 요일만 본다(거래일 달력 없음 · 미국 평일 휴장은 남는다).
        print(f"[vix] no new weekday through {max_date} -- latest={latest}")
        return 0

    try:
        df = fdr.DataReader("VIX", start, end)
    except Exception as e:  # noqa: BLE001
        print(f"[vix] fetch failed: {type(e).__name__}: {e}", file=sys.stderr)
        return 2

    if df is None or len(df) == 0 or "Close" not in df.columns:
        print("[vix] empty response or missing Close column", file=sys.stderr)
        return 2

    rows: list[tuple[str, Optional[float]]] = []
    for idx, raw in df.iterrows():
        try:
            dt = idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)[:10]
        except Exception:  # noqa: BLE001
            continue
        close_raw = raw["Close"]
        try:
            if close_raw is None:
                continue
            close = float(close_raw)
            if close != close or close <= 0:  # NaN or non-positive
                continue
        except (TypeError, ValueError):
            continue
        rows.append((dt, close))

    if max_date is not None and rows:
        settled = [(dt, close) for dt, close in rows if dt <= max_date.isoformat()]
        if not settled:
            print(
                f"[vix] no settled rows yet (fetched={len(rows)}, settled through {max_date})"
            )
            return 0
        rows = settled

    if not rows:
        print("[vix] no valid rows after filter", file=sys.stderr)
        return 2

    # 지시문 §4.2: 기존 값과 다른 새 값은 자동 덮어쓰지 않는다.
    existing = fetch_existing_benchmark_close_map("VIX", db_path=db_path)
    appendable: list[tuple[str, float]] = []
    conflicts: list[str] = []
    for dt, close in rows:
        prior = existing.get(dt)
        if prior is None or prior <= 0:
            appendable.append((dt, close))
            continue
        if abs(prior - close) <= 1e-9:
            continue  # 동일 값 skip
        conflicts.append(dt)

    if conflicts:
        sample = ",".join(conflicts[:3])
        print(
            f"[vix] conflict with existing prices on {len(conflicts)} dates -- "
            f"aborting without overwrite (e.g. {sample})",
            file=sys.stderr,
        )
        return 2

    if not appendable:
        print(f"[vix] no new rows to write (already up to date, fetched={len(rows)})")
        return 0

    written = upsert_benchmark_prices(
        benchmark_id="VIX",
        benchmark_name="VIX",
        rows=[(dt, close) for dt, close in appendable],
        source="FDR_VIX",
        db_path=db_path,
    )
    new_latest = latest_benchmark_date("VIX", db_path=db_path)
    print(
        f"[vix] source=FDR_VIX written={written} "
        f"range={appendable[0][0]}~{appendable[-1][0]} latest={new_latest}"
    )
    return 0
