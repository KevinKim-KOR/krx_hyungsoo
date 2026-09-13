"""POC3-OPS-02B-2 보호 로직 역검증.

각 가드를 **일시 무력화**했을 때 실제로 나쁜 일이 일어나는지 확인한다. 가드가
있을 때 통과하는 것만으로는 "그 가드가 일하고 있다" 를 증명하지 못한다.

실경로를 쓰지 않는다 — 전부 임시 디렉터리·임시 DB·stub fetcher 다.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.market_briefing import calendar as cal  # noqa: E402
from app.market_briefing import evidence as ev  # noqa: E402
from app.market_briefing import flow, krx_store, krx_sync, meta_gate  # noqa: E402

AXIS = [f"2026-08-{d:02d}" for d in range(3, 32)] + [
    f"2026-09-{d:02d}" for d in (1, 2, 3, 4, 7, 8, 9, 10, 11, 14, 15, 16, 17, 18)
]
RESULTS: list[tuple[str, str, str, bool]] = []


def record(guard: str, with_guard: str, without_guard: str, ok: bool) -> None:
    RESULTS.append((guard, with_guard, without_guard, ok))


def area() -> Path:
    return Path(tempfile.mkdtemp())


def setup(tmp: Path, *, through: str, consistency_status: str = meta_gate.STATUS_OK):
    db = tmp / "krx.sqlite"
    days = [d for d in AXIS if d <= through]
    for i, d in enumerate(days):
        bas = d.replace("-", "")
        close = str(10000 + i * 50)  # 우상향 — 5일·20일 수익률이 모두 양수
        rows = [
            {"ISU_CD": t, "BAS_DD": bas, "TDD_CLSPRC": close}
            for t in ("069500", "102110")
        ]
        krx_store.upsert_snapshot(
            krx_store.validate_snapshot(rows, expected_date=bas), db_path=db
        )
    meta_gate.save_consistency(
        meta_gate.ConsistencyResult(
            status=consistency_status,
            api_ticker_count=2,
            csv_ticker_count=2,
            exact_match_count=2 if consistency_status == meta_gate.STATUS_OK else 0,
            join_coverage=1.0 if consistency_status == meta_gate.STATUS_OK else 0.0,
        ),
        tmp / "c.json",
    )
    (tmp / "official.csv").write_bytes(
        (
            "단축코드,기초지수명,지수산출기관,기초자산분류,추적배수,복제방법,"
            "한글종목약명\n"
            "069500,코스피200,KRX,주식,일반,실물(패시브),KODEX 200\n"
            "102110,코스피200,KRX,주식,일반,실물(패시브),TIGER 200\n"
        ).encode("cp949")
    )
    (tmp / "krx_trading_days_2026.csv").write_text(
        "date\n" + "\n".join(AXIS) + "\n", encoding="utf-8"
    )
    return db


def assemble(tmp: Path, db: Path, *, today="2026-09-18", sp500=1.2, fresh=True):
    return flow.assemble_market_briefing(
        today_kst=today,
        runtime_kst=None,
        state_path=tmp / "s.json",
        consistency_path=tmp / "c.json",
        official_csv_path=tmp / "official.csv",
        sp500_return_pct=sp500,
        sp500_asof="2026-09-17",
        sp500_fresh=fresh,
        calendar_dir=tmp,
        db_path=db,
    )


# ── ① 거래일 Gate ────────────────────────────────────────────────────────────
tmp = area()
db = setup(tmp, through="2026-09-17")
with_g = assemble(tmp, db, today="2026-09-19").skip_reason  # 토요일
orig = flow.check_trading_day
flow.check_trading_day = lambda d, directory=None: cal.CalendarVerdict(
    ok=True, reason=None, date_kst=d
)
without = assemble(tmp, db, today="2026-09-19")
flow.check_trading_day = orig
record(
    "① 거래일 Gate (calendar)",
    f"skip_reason={with_g}",
    f"휴장일에 본문 생성 {len(without.message_text or '')}자",
    with_g == "non_trading_day" and bool(without.message_text),
)

# ── ② 창 최신성 Gate ─────────────────────────────────────────────────────────
tmp = area()
db = setup(tmp, through="2026-08-31")  # 12거래일 지연
out = assemble(tmp, db)
_leak = "국내" in (out.message_text or "")
with_g = f"index_status={out.diagnostics['index_status']} · 국내 날짜 노출={_leak}"
orig_lag = flow._window_lag_trading_days
flow._window_lag_trading_days = lambda latest, **kw: 0  # 항상 최신이라고 거짓말
out2 = assemble(tmp, db)
flow._window_lag_trading_days = orig_lag
leaked = [x for x in (out2.message_text or "").splitlines() if "국내" in x]
record(
    "② 창 최신성 Gate",
    with_g,
    f"18일 지난 종가로 후보 생성 · 기준줄={leaked}",
    out.diagnostics["index_status"] == "stale"
    and bool(out2.diagnostics["index_candidates"]),
)

# ── ③ 정합성 Gate (CSV_REFRESH_REQUIRED 면 가격 미사용) ──────────────────────
tmp = area()
db = setup(
    tmp, through="2026-09-17", consistency_status=meta_gate.STATUS_CSV_REFRESH_REQUIRED
)
out = assemble(tmp, db)
with_g = f"index_status={out.diagnostics['index_status']} 후보={out.diagnostics['index_candidates']}"
orig_usable = meta_gate.ConsistencyResult.usable
meta_gate.ConsistencyResult.usable = property(lambda self: True)
out2 = assemble(tmp, db)
meta_gate.ConsistencyResult.usable = orig_usable
record(
    "③ 정합성 Gate",
    with_g,
    f"정합성 깨진 채 후보 생성={out2.diagnostics['index_candidates']}",
    not out.diagnostics["index_candidates"]
    and bool(out2.diagnostics["index_candidates"]),
)

# ── ④ 21거래일 창 요구 ───────────────────────────────────────────────────────
tmp = area()
db = setup(tmp, through="2026-08-14")  # 8거래일만
w = krx_store.resolve_window(db_path=db)
orig_req = krx_store.REQUIRED_TRADING_DAYS
krx_store.REQUIRED_TRADING_DAYS = 2
try:
    w2 = krx_store.resolve_window(db_path=db)
    without4 = f"2일만으로 창 생성 latest={w2.latest if w2 else None}"
    broke4 = w2 is not None
except IndexError as e:
    without4 = f"IndexError: {e}"  # 20일 전 날짜가 없어 그대로 터진다
    broke4 = True
krx_store.REQUIRED_TRADING_DAYS = orig_req
record(
    "④ 21거래일 창 요구",
    f"window={w}",
    without4,
    w is None and broke4,
)

# ── ⑤ 휴장일 응답 판정 (has_traded_prices) ───────────────────────────────────
holiday = [{"ISU_CD": "A", "BAS_DD": "20260817", "TDD_CLSPRC": ""}]
traded = [{"ISU_CD": "A", "BAS_DD": "20260814", "TDD_CLSPRC": "100"}]


def fetch(bas, key):
    return [] if bas == "20260818" else (holiday if bas == "20260817" else traded)


from datetime import date  # noqa: E402

b1, _, _ = krx_sync.resolve_basis_date(
    start=date(2026, 8, 18), key="K", fetcher=fetch, lookback_days=7
)
orig_h = krx_sync.has_traded_prices
krx_sync.has_traded_prices = lambda rows: True  # 무력화
b2, rows2, _ = krx_sync.resolve_basis_date(
    start=date(2026, 8, 18), key="K", fetcher=fetch, lookback_days=7
)
krx_sync.has_traded_prices = orig_h
record(
    "⑤ 휴장일 응답 판정",
    f"기준일={b1} (거래일)",
    f"기준일={b2} (휴장일) · 종가 채워진 행={sum(1 for r in rows2 if (r.get('TDD_CLSPRC') or '').strip())}",
    b1 == "20260816" and b2 == "20260817",
)

# ── ⑥ n≥2 요구 (단일 ETF 지수 배제) ──────────────────────────────────────────
rows = [
    {
        "단축코드": "X1",
        "기초지수명": "단일",
        "지수산출기관": "KRX",
        "기초자산분류": "주식",
        "추적배수": "일반",
        "복제방법": "실물(패시브)",
        "한글종목약명": "ONLY",
    }
]
closes = {"L": {"X1": 11000.0}, "5": {"X1": 10000.0}, "20": {"X1": 9000.0}}
r1 = ev.compute_index_leadership(
    meta_rows=rows, closes=closes, latest="L", d5="5", d20="20"
)
orig_min = ev.MIN_TICKERS_PER_INDEX
ev.MIN_TICKERS_PER_INDEX = 1
r2 = ev.compute_index_leadership(
    meta_rows=rows, closes=closes, latest="L", d5="5", d20="20"
)
ev.MIN_TICKERS_PER_INDEX = orig_min
record(
    "⑥ n≥2 요구",
    f"후보={[c.identifier for c in r1.candidates]}",
    f"단일 ETF 지수가 후보로 승격={[c.identifier for c in r2.candidates]}",
    not r1.candidates and bool(r2.candidates),
)

# ── ⑦ fingerprint 반복 억제 ──────────────────────────────────────────────────
tmp = area()
db = setup(tmp, through="2026-09-17")
first = assemble(tmp, db)
flow.save_state(
    tmp / "s.json",
    fingerprint=first.fingerprint,
    sent_date_kst="2026-09-17",
    runtime_kst=None,
)
again = assemble(tmp, db)
orig_load = flow.load_state
flow.load_state = lambda p: None  # 직전 상태를 못 읽는 것으로 위장
again2 = assemble(tmp, db)
flow.load_state = orig_load
record(
    "⑦ fingerprint 반복 억제",
    f"skip_reason={again.skip_reason}",
    f"같은 상태를 다시 발송 (skip_reason={again2.skip_reason})",
    again.skip_reason == flow.REASON_NO_CHANGE and again2.skip_reason is None,
)

# ── 출력 ─────────────────────────────────────────────────────────────────────
print(f"{'보호 로직':28s} | {'가드 있을 때':44s} | 무력화하면")
print("-" * 130)
allok = True
for g, a, b, ok in RESULTS:
    allok = allok and ok
    mark = "OK " if ok else "!! "
    print(f"{mark}{g:26s} | {a:44s} | {b}")
print("-" * 130)
print(f"역검증 {len(RESULTS)}건 · 전부 '무력화 시 실패' 확인: {allok}")
sys.exit(0 if allok else 1)
