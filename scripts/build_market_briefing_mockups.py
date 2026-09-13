"""POC3-OPS-02B-2 — 사용자 목업 Gate 7종 생성 (설계서 §9).

① 상승+지수2 ② 하락+지수1 ③ 전망만(정상 0개) ④ 전망 불가+지수만
⑤ `CSV_REFRESH_REQUIRED` ⑥ 전체 stale ⑦ 동일 fingerprint 미발송

**손으로 쓴 본문이 아니다.** 운영과 같은 `flow.assemble_market_briefing()` 을
그대로 호출해 나온 본문을 찍는다. 각 목업에 실제 글자 수 · 분할 수 · 사용 기준일
· 발송/미발송 사유 · 저장 상태 변경 여부를 함께 낸다.

## 격리

라이브 state·DB·`.env` 를 건드리지 않는다. 모든 경로가 `tempfile` 아래다. 외부
조회 0건(07:20 결과를 소비하는 구조라 조립 단계에 네트워크가 없다). Telegram
sender 는 호출하지 않는다 — 본문만 만든다.

```bash
python scripts/build_market_briefing_mockups.py            # 콘솔 출력
python scripts/build_market_briefing_mockups.py --md OUT   # 마크다운 저장
```
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from app.market_briefing import flow, krx_store, meta_gate  # noqa: E402

# Telegram 한 메시지 상한. 분할 수 계산에만 쓴다 — 임의 길이 기준을 만들지 않는다.
TELEGRAM_LIMIT = 4096

TODAY = "2026-09-18"  # 거래일 (2026 캘린더 실측 기준 금요일)
RUNTIME = "2026-09-18T08:00:00+09:00"
US_ASOF = "2026-09-17"

CSV_HEADER = (
    "단축코드,기초지수명,지수산출기관,기초자산분류,추적배수,복제방법,한글종목약명\n"
)


@dataclass
class Mock:
    no: str
    title: str
    outcome: Any
    state_saved: bool
    state_note: str


def _official_csv(path: Path, rows: list[tuple[str, str, str]]) -> Path:
    body = CSV_HEADER + "".join(
        f"{code},{index},KRX,주식,일반,실물(패시브),{short}\n"
        for code, index, short in rows
    )
    path.write_bytes(body.encode("cp949"))
    return path


def _calendar(dirpath: Path) -> Path:
    """목업용 거래일 캘린더. 운영 파일을 읽지 않는다."""
    (dirpath / "krx_trading_days_2026.csv").write_text(
        "date\n" + "\n".join(MOCK_TRADING_DAYS) + "\n", encoding="utf-8"
    )
    return dirpath


# 목업 거래일 축 — 실행일 2026-09-18 의 **직전 거래일이 2026-09-17** 이 되게 한다.
# 예전 fixture 는 08-30 까지만 채워 본문 기준 줄이 "국내 2026-08-30" 으로 나왔다.
# 그건 운영 모습이 아니었다(사용자 지적 2026-09-13).
MOCK_TRADING_DAYS = (
    [f"2026-08-{d:02d}" for d in (3, 4, 5, 6, 7, 10, 11, 12, 13, 14)]
    + [f"2026-08-{d:02d}" for d in (18, 19, 20, 21, 24, 25, 26, 27, 28, 31)]
    + [f"2026-09-{d:02d}" for d in (1, 2, 3, 4, 7, 8, 9, 10, 11, 14, 15, 16, 17, 18)]
)


def _seed_prices(
    db: Path, tickers: list[str], *, latest: float, d5: float, d20: float
) -> None:
    """직전 거래일까지 채운다. 창이 성립하고 **최신성 Gate도 통과**해야 한다."""
    days = [d for d in MOCK_TRADING_DAYS if d < "2026-09-18"]
    for i, day in enumerate(days):
        # 창은 최신일 기준 21개다. -20 위치에 d20, -5 위치에 d5 를 둔다.
        if i == len(days) - 21:
            price = d20
        elif i == len(days) - 6:
            price = d5
        else:
            price = latest
        rows = [
            {"ISU_CD": t, "BAS_DD": day.replace("-", ""), "TDD_CLSPRC": str(price)}
            for t in tickers
        ]
        snap = krx_store.validate_snapshot(rows, expected_date=day.replace("-", ""))
        krx_store.upsert_snapshot(snap, db_path=db)


def _consistency(n: int, *, status: str = meta_gate.STATUS_OK) -> Any:
    return meta_gate.ConsistencyResult(
        status=status,
        api_ticker_count=n,
        csv_ticker_count=n,
        exact_match_count=n if status == meta_gate.STATUS_OK else 0,
        join_coverage=1.0 if status == meta_gate.STATUS_OK else 0.0,
        api_basis_date="20260917",
        csv_asof_date="2026-09-09",
    )


def _run(
    tmp: Path,
    *,
    sp500: Optional[float],
    fresh: bool,
    csv_rows: list[tuple[str, str]],
    consistency: Any,
    seed: Optional[dict] = None,
    prev_fingerprint: Optional[str] = None,
) -> Any:
    state = tmp / "state.json"
    cpath = tmp / "consistency.json"
    if consistency is not None:
        meta_gate.save_consistency(consistency, cpath)
    db = tmp / "krx.sqlite"
    if seed:
        _seed_prices(db, **seed)
    if prev_fingerprint:
        flow.save_state(
            state,
            fingerprint=prev_fingerprint,
            sent_date_kst="2026-09-17",
            runtime_kst=None,
        )
    return flow.assemble_market_briefing(
        today_kst=TODAY,
        runtime_kst=RUNTIME,
        state_path=state,
        consistency_path=cpath,
        official_csv_path=_official_csv(tmp / "official.csv", csv_rows),
        sp500_return_pct=sp500,
        sp500_asof=US_ASOF,
        sp500_fresh=fresh,
        calendar_dir=_calendar(tmp),
        db_path=db,
    )


def build() -> list[Mock]:
    out: list[Mock] = []
    root = Path(tempfile.mkdtemp(prefix="mb_mock_"))

    def area(name: str) -> Path:
        p = root / name
        p.mkdir(parents=True, exist_ok=True)
        return p

    # ① 상승 + 기초지수 2개
    two = [
        ("069500", "코스피200", "KODEX 200"),
        ("102110", "코스피200", "TIGER 200"),
        ("091160", "반도체", "KODEX 반도체"),
        ("091230", "반도체", "TIGER 반도체"),
    ]
    two_tickers = ["069500", "102110", "091160", "091230"]
    out.append(
        Mock(
            "①",
            "상승 + 기초지수 2개",
            _run(
                area("m1"),
                sp500=1.24,
                fresh=True,
                csv_rows=two,
                consistency=_consistency(4),
                seed={
                    "tickers": two_tickers,
                    "latest": 11000.0,
                    "d5": 10500.0,
                    "d20": 10000.0,
                },
            ),
            True,
            "발송 성공 후 fingerprint 저장",
        )
    )

    # ② 하락 + 기초지수 1개 (후보 1개만 통과)
    one = [
        ("069500", "코스피200", "KODEX 200"),
        ("102110", "코스피200", "TIGER 200"),
        ("272910", "단일지수", "KODEX 단일"),
    ]
    out.append(
        Mock(
            "②",
            "하락 + 기초지수 1개",
            _run(
                area("m2"),
                sp500=-0.93,
                fresh=True,
                csv_rows=one,
                consistency=_consistency(3),
                seed={
                    "tickers": ["069500", "102110", "272910"],
                    "latest": 11000.0,
                    "d5": 10500.0,
                    "d20": 10000.0,
                },
            ),
            True,
            "발송 성공 후 fingerprint 저장",
        )
    )

    # ③ 전망만 — 기초지수 정상 0개 (안내 없이 문단 생략)
    out.append(
        Mock(
            "③",
            "전망만 · 기초지수 정상 0개",
            _run(
                area("m3"),
                sp500=0.41,
                fresh=True,
                csv_rows=[
                    ("069500", "코스피200", "KODEX 200"),
                    ("102110", "코스피200", "TIGER 200"),
                ],
                consistency=_consistency(2),
                seed={
                    "tickers": ["069500", "102110"],
                    "latest": 9000.0,  # 5일·20일 음수 → 후보 0개
                    "d5": 10500.0,
                    "d20": 10000.0,
                },
            ),
            True,
            "발송 성공 후 fingerprint 저장",
        )
    )

    # ④ 전망 불가 + 기초지수만
    out.append(
        Mock(
            "④",
            "전망 불가 + 기초지수만",
            _run(
                area("m4"),
                sp500=None,
                fresh=False,
                csv_rows=two,
                consistency=_consistency(4),
                seed={
                    "tickers": two_tickers,
                    "latest": 11000.0,
                    "d5": 10500.0,
                    "d20": 10000.0,
                },
            ),
            True,
            "발송 성공 후 fingerprint 저장",
        )
    )

    # ⑤ CSV_REFRESH_REQUIRED — 정합성 실패 시 가격을 쓰지 않는다
    out.append(
        Mock(
            "⑤",
            "CSV_REFRESH_REQUIRED",
            _run(
                area("m5"),
                sp500=0.77,
                fresh=True,
                csv_rows=two,
                consistency=_consistency(
                    4, status=meta_gate.STATUS_CSV_REFRESH_REQUIRED
                ),
                seed={
                    "tickers": two_tickers,
                    "latest": 11000.0,
                    "d5": 10500.0,
                    "d20": 10000.0,
                },
            ),
            True,
            "발송 성공 후 fingerprint 저장",
        )
    )

    # ⑥ 전체 stale — 전망 불가 + 가격 창 미성립
    out.append(
        Mock(
            "⑥",
            "전체 stale (미발송)",
            _run(
                area("m6"),
                sp500=None,
                fresh=False,
                csv_rows=two,
                consistency=_consistency(4),
                seed=None,  # 거래일 21개 미만 → 창 미성립
            ),
            False,
            "미발송 — 상태 저장 없음",
        )
    )

    # ⑦ 동일 fingerprint — 반복 억제.
    # 손으로 fingerprint 를 적지 않는다. ① 과 같은 입력으로 **한 번 조립해 발송
    # 성공 상태를 저장**한 뒤 **다시 조립**한다 — 운영에서 실제로 벌어지는 순서다.
    m7 = area("m7")
    seed7 = {
        "tickers": two_tickers,
        "latest": 11000.0,
        "d5": 10500.0,
        "d20": 10000.0,
    }
    first = _run(
        m7,
        sp500=1.24,
        fresh=True,
        csv_rows=two,
        consistency=_consistency(4),
        seed=seed7,
    )
    flow.save_state(
        m7 / "state.json",
        fingerprint=first.fingerprint,
        sent_date_kst="2026-09-17",
        runtime_kst=None,
    )
    out.append(
        Mock(
            "⑦",
            "동일 fingerprint (미발송)",
            _run(
                m7,
                sp500=1.24,
                fresh=True,
                csv_rows=two,
                consistency=_consistency(4),
                seed=None,  # 이미 적재돼 있다
            ),
            False,
            "미발송 — 상태 저장 없음 (직전과 동일)",
        )
    )
    return out


def report(mocks: list[Mock]) -> str:
    lines: list[str] = []
    lines.append(f"실행일(KST) = {TODAY} · runtime = {RUNTIME}")
    lines.append(f"미국 기준일 = {US_ASOF} · Telegram 1건 상한 = {TELEGRAM_LIMIT}자")
    lines.append("")
    for m in mocks:
        o = m.outcome
        body = o.message_text or ""
        n = len(body)
        parts = 1 if n == 0 else (n + TELEGRAM_LIMIT - 1) // TELEGRAM_LIMIT
        sent = not (o.skip_reason or o.fail)
        cal = (o.diagnostics or {}).get("calendar") or {}
        lines.append(f"## {m.no} {m.title}")
        lines.append("")
        lines.append("```text")
        lines.append(f"발송          = {'예' if sent else '아니오'}")
        lines.append(f"사유          = {o.skip_reason or o.fail or '-'}")
        lines.append(f"글자 수       = {n}")
        lines.append(f"분할 수       = {parts if sent else 0}")
        idx_diag = (o.diagnostics or {}).get("index_diagnostics") or {}
        kr_asof = idx_diag.get("price_asof") or cal.get("date_kst") or "-"
        lines.append(f"국내 기준일    = {kr_asof}")
        lines.append(f"미국 기준일    = {US_ASOF}")
        lines.append(
            f"전망 상태      = {(o.diagnostics or {}).get('outlook_state') or '-'}"
        )
        lines.append(
            f"지수 상태      = {(o.diagnostics or {}).get('index_status') or '-'}"
        )
        lines.append(
            f"지수 후보      = {(o.diagnostics or {}).get('index_candidates') or []}"
        )
        lines.append(f"fingerprint   = {o.fingerprint or '-'}")
        lines.append(f"직전 fp       = {o.previous_fingerprint or '-'}")
        lines.append(
            f"상태 저장      = {'예' if m.state_saved and sent else '아니오'} ({m.state_note})"
        )
        lines.append("```")
        lines.append("")
        if body:
            lines.append("실제 본문:")
            lines.append("")
            lines.append("```text")
            lines.append(body)
            lines.append("```")
        else:
            lines.append("본문 없음 (미발송).")
        lines.append("")
    return "\n".join(lines)


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--md", type=Path, default=None, help="마크다운 저장 경로")
    a = ap.parse_args(argv)
    text = report(build())
    if a.md:
        a.md.parent.mkdir(parents=True, exist_ok=True)
        a.md.write_text(text, encoding="utf-8")
        print(f"저장: {a.md}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
