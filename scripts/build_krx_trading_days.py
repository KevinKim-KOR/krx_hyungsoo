"""KRX 거래일 snapshot CSV 생성기 (`state/market_meta/krx_trading_days_YYYY.csv`).

## 왜 이 파일이 필요한가

08:00 시장 브리핑은 **개장 전**에 돌므로 "오늘이 거래일인가" 를 당일 시세로 알 수
없다. KRX Open API 는 개장 전 당일 조회에 빈 응답을 준다(실측: `20260911` 08:00
`rows=0`). 휴장일 전용 엔드포인트는 전부 404 다. 그래서 **versioned snapshot** 을
둔다.

## 어떻게 날짜를 정했나 — 출처를 CSV 에 같이 적는다

거래일은 **"평일에서 휴장일을 뺀 것"** 으로 정의한다. 주말 휴장은 규칙이 아니라
정의다(KRX 는 토·일에 거래하지 않는다). 따라서 판정이 필요한 것은 **평일 휴장일**
뿐이고, 그 목록의 출처를 둘로 나눠 CSV `source` 컬럼에 남긴다.

| source | 뜻 |
|---|---|
| `MEASURED_KRX_API` | KRX Open API 응답으로 **실측**. 휴장일은 행은 오지만 `TDD_CLSPRC` 가 빈 문자열이다. 거래일은 채워져 있다. |
| `USER_CONFIRMED` | 아직 공시되지 않은 미래 구간. 사용자가 확인해 알려준 휴장일. |

`--verify` 로 실측 구간을 API 로 다시 조회해 `MEASURED_KRX_API` 목록이 맞는지
대조할 수 있다. 추정값·공휴일 라이브러리·주말 외 규칙은 쓰지 않는다.

## 2026 — 규칙으로는 못 맞히는 날이 있었다 (실측 근거)

평일 휴장 11일 중 **5월 1일 근로자의날**은 법정공휴일이 아니지만 KRX 는 휴장한다.
"일반 공휴일" 목록만으로 캘린더를 만들면 이 날 잘못 발송된다. 7월 17일 제헌절은
2026년부터 공휴일로 재지정됐다(사용자 확인).

## 사용

```bash
python scripts/build_krx_trading_days.py 2026            # CSV 생성
python scripts/build_krx_trading_days.py 2026 --verify    # 실측 구간 API 재대조
```
"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

OUT_DIR = Path("state/market_meta")

SRC_MEASURED = "MEASURED_KRX_API"
SRC_USER = "USER_CONFIRMED"

# ── 평일 휴장일 ──────────────────────────────────────────────────────────────
# 실측 구간 — KRX Open API 응답에서 `TDD_CLSPRC` 가 한 건도 채워지지 않은 평일.
# 2026-01-01 ~ 2026-09-11 평일 182일 전수 조회(조회 실패 0건) 결과다.
MEASURED_CLOSED: dict[int, tuple[str, ...]] = {
    2026: (
        "2026-01-01",  # 신정
        "2026-02-16",  # 설날 연휴
        "2026-02-17",  # 설날
        "2026-02-18",  # 설날 연휴
        "2026-03-02",  # 삼일절(3/1 일) 대체공휴일
        "2026-05-01",  # 근로자의날 — 법정공휴일 아님. 규칙으로는 못 맞힌다
        "2026-05-05",  # 어린이날
        "2026-05-25",  # 부처님오신날(5/24 일) 대체공휴일
        "2026-06-03",  # 전국동시지방선거
        "2026-07-17",  # 제헌절 — 2026년부터 공휴일 (사용자 확인)
        "2026-08-17",  # 광복절(8/15 토) 대체공휴일
    )
}

# 실측 구간 경계 — 이 날짜까지는 API 로 판정했다. 이후는 미공시다.
MEASURED_THROUGH: dict[int, str] = {2026: "2026-09-11"}

# 미공시 구간 — 사용자 확인 휴장일 (2026-09-13 확인).
USER_CONFIRMED_CLOSED: dict[int, tuple[str, ...]] = {
    2026: (
        "2026-09-24",  # 추석 연휴
        "2026-09-25",  # 추석
        "2026-09-28",  # 추석 대체공휴일
        "2026-10-05",  # 개천절(10/3 토) 대체공휴일
        "2026-10-09",  # 한글날
        "2026-12-25",  # 성탄절
        "2026-12-31",  # 연말 폐장일
    )
}


def weekdays(year: int) -> list[date]:
    """그 해의 평일 전부. 주말 휴장은 규칙이 아니라 정의다."""
    out, d = [], date(year, 1, 1)
    while d.year == year:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def build(year: int) -> list[tuple[str, str]]:
    """`(date, source)` 목록. 해당 연도 전체를 덮지 못하면 예외."""
    if year not in MEASURED_CLOSED or year not in USER_CONFIRMED_CLOSED:
        raise SystemExit(
            f"{year}년 휴장일 자료가 없다. 연도가 빠진 캘린더를 쓰면 "
            "그 해 전체가 조용히 미발송된다 — 만들지 않는다."
        )
    measured = set(MEASURED_CLOSED[year])
    confirmed = set(USER_CONFIRMED_CLOSED[year])
    overlap = measured & confirmed
    if overlap:
        raise SystemExit(f"실측·확인 구간 중복: {sorted(overlap)}")
    through = MEASURED_THROUGH[year]
    rows: list[tuple[str, str]] = []
    for d in weekdays(year):
        iso = d.isoformat()
        if iso in measured or iso in confirmed:
            continue
        rows.append((iso, SRC_MEASURED if iso <= through else SRC_USER))
    return rows


def verify(year: int, env_path: Optional[Path] = None) -> int:
    """실측 구간을 API 로 다시 조회해 `MEASURED_CLOSED` 와 대조한다."""
    from concurrent.futures import ThreadPoolExecutor

    import httpx

    from app.market_briefing import krx_sync

    key = krx_sync.read_api_key(env_path)
    if not key:
        print("KRX_API_KEY 없음 — 대조 불가")
        return 2
    through = date.fromisoformat(MEASURED_THROUGH[year])
    days = [d for d in weekdays(year) if d <= through]

    def probe(d: date) -> tuple[str, Optional[int]]:
        bas = d.strftime("%Y%m%d")
        try:
            r = httpx.get(
                krx_sync.KRX_ETF_DAILY_URL,
                params={"basDd": bas},
                headers={"AUTH_KEY": key},
                timeout=20.0,
            )
            if r.status_code != 200:
                return d.isoformat(), None
            rows = r.json().get("OutBlock_1") or []
            return d.isoformat(), sum(
                1 for x in rows if (x.get("TDD_CLSPRC") or "").strip()
            )
        except Exception:  # noqa: BLE001
            return d.isoformat(), None

    with ThreadPoolExecutor(max_workers=5) as ex:
        res = list(ex.map(probe, days))

    unknown = [d for d, f in res if f is None]
    closed = sorted(d for d, f in res if f == 0)
    expected = sorted(MEASURED_CLOSED[year])
    print(f"조회 평일 {len(days)}일 · 판정 불가 {len(unknown)}건")
    print(f"실측 휴장 {len(closed)}일 / 기록 {len(expected)}일")
    if unknown:
        print(f"  판정 불가: {unknown[:10]}")
    if closed == expected:
        print("대조 결과: 일치")
        return 0
    print(f"  불일치 — 기록에만: {sorted(set(expected) - set(closed))}")
    print(f"  불일치 — 실측에만: {sorted(set(closed) - set(expected))}")
    return 1


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("year", type=int)
    ap.add_argument("--verify", action="store_true", help="실측 구간 API 재대조")
    ap.add_argument("--out-dir", type=Path, default=None)
    a = ap.parse_args(argv)

    if a.verify:
        return verify(a.year)

    rows = build(a.year)
    out_dir = a.out_dir or OUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"krx_trading_days_{a.year}.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["date", "source"])
        w.writerows(rows)
    measured = sum(1 for _, s in rows if s == SRC_MEASURED)
    print(f"{path} — 거래일 {len(rows)}일")
    print(f"  {SRC_MEASURED} {measured}일 · {SRC_USER} {len(rows) - measured}일")
    print(
        f"  평일 휴장 {len(MEASURED_CLOSED[a.year])}"
        f"+{len(USER_CONFIRMED_CLOSED[a.year])}일 제외"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
