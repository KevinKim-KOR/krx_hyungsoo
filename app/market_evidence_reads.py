"""POC6-32 V2 — 공통 시장 근거의 읽기 전용 조회 두 가지(PLAN §4-1 · §6 · §9 I-16).

- `investor_sums` — 60거래일 수급(판정 Q10): 시장 흐름 응답(`windows.r60`)이 정한 시작 · 끝 날짜 안의 코스피 저장
  거래일마다 투자자 분류별 순매수를 더한다. 시장 흐름 조립(`supply_fx_oil_context.py`)은 바꾸지 않는다 — 그 조립은
  외국인 · 개인 · 기관계 · 기타법인만 읽고 내국인대우외국인 · 국가는 읽지 않는다. 같은 창 계산과 맞추려고
  있어야 할 날 = 그 구간의 코스피 저장 거래일(종가가 0 보다 큰 행)이고, 그날이 아닌 수급 행은 더하지 않는다.
- `kospi_sources` — 코스피 저장 행의 출처 칸(KRX 공식 · FDR · 네이버)을 날짜별로 읽는다. 기존 저장 모듈의 출처 읽기는
  표를 만들고 저장하는 연결을 쓰므로 조회 경로에서 쓰지 않는다.
- `vix_card` — 기존 VIX 카드 읽기 결과를 칸으로 옮긴다(`market_evidence.py` 줄 수 근접선 때문에 이곳으로 옮김).
- `source_label` — `kospi_sources` 의 그날 출처 칸 → 표시 이름 · KRX 공식 여부(같은 이유로 `market_evidence.py` 에서
  옮김 · 동작 같음 · r1 G4).

조회 둘 다 읽기 전용(`mode=ro`) 연결만 연다 — 표를 만들거나 쓰지 않는다. 파일 · 표가 없으면 None · 빈 결과다.
SQLite 읽기 오류는 그대로 올린다(부르는 쪽이 그 칸만 '확인 불가'로 둔다).
"""

from __future__ import annotations

from contextlib import closing
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from app.market_benchmark_store import KOSPI_ID, KOSPI_SOURCE
from app.market_data_store import DEFAULT_DB_PATH
from app.supply_fx_oil_store import FLOW_MARKET, _has_table, _ro

BENCH_TABLE = "market_benchmark_daily_price"
FLOW_TABLE = "market_investor_flow_daily"
# 코스피 저장 행 출처 칸 → 표시 이름(`source_label`)
SOURCE_LABEL = {
    KOSPI_SOURCE: "KRX 공식",
    "FinanceDataReader/KS11": "FDR",
    "NAVER_FDR": "네이버(FDR 경유)",
}


def investor_sums(
    start: str,
    end: str,
    investors: Sequence[str],
    *,
    db_path: Path = DEFAULT_DB_PATH,
) -> Optional[dict]:
    """{"expected": 구간의 코스피 저장 거래일 수, "investors": {분류: {sum, days, partial}}}.

    `days` = 그 분류의 수급 행이 있는 코스피 저장 거래일 수 · `partial` = days < expected.
    파일 · 표가 없으면 None(확인 불가 — '0'으로 바꾸지 않음).
    """
    con = _ro(db_path)
    if con is None:
        return None
    with closing(con):
        if not (_has_table(con, BENCH_TABLE) and _has_table(con, FLOW_TABLE)):
            return None
        kdates = {
            r[0]
            for r in con.execute(
                f"SELECT date FROM {BENCH_TABLE} WHERE benchmark_id = ? "
                "AND close IS NOT NULL AND close > 0 AND date >= ? AND date <= ?",
                (KOSPI_ID, start, end),
            ).fetchall()
        }
        marks = ", ".join("?" for _ in investors)
        rows = con.execute(
            f"SELECT trade_date, investor, net_value FROM {FLOW_TABLE} "
            f"WHERE market = ? AND trade_date >= ? AND trade_date <= ? "
            f"AND investor IN ({marks})",
            (FLOW_MARKET, start, end, *investors),
        ).fetchall()
    out = {k: {"sum": 0, "days": 0} for k in investors}
    for d, inv, net in rows:
        if d in kdates:
            out[inv]["sum"] += int(net)
            out[inv]["days"] += 1
    n = len(kdates)
    for v in out.values():
        v["partial"] = v["days"] < n
    return {"expected": n, "investors": out}


def kospi_sources(
    dates: Sequence[str], *, db_path: Path = DEFAULT_DB_PATH
) -> dict[str, str]:
    """{날짜: 저장 행의 출처 칸} — 주어진 날짜 중 저장 행이 있는 것만. 파일 · 표 없음 = {}."""
    wanted = sorted({d for d in dates if d})
    if not wanted:
        return {}
    con = _ro(db_path)
    if con is None:
        return {}
    with closing(con):
        if not _has_table(con, BENCH_TABLE):
            return {}
        marks = ", ".join("?" for _ in wanted)
        rows = con.execute(
            f"SELECT date, source FROM {BENCH_TABLE} WHERE benchmark_id = ? "
            f"AND date IN ({marks})",
            (KOSPI_ID, *wanted),
        ).fetchall()
    return {d: s for d, s in rows}


def source_label(
    sources: Optional[Mapping[str, Any]], d: Optional[str]
) -> tuple[str, Optional[bool]]:
    """`kospi_sources` 결과의 그날 출처 → (표시 이름, KRX 공식 여부) — 출처를 읽지 못했거나 그날 행이 없으면
    ('확인 불가', None)."""
    raw = (sources or {}).get(d) if d else None
    if raw is None:
        return "확인 불가", None
    return SOURCE_LABEL.get(raw, "기타 수집 경로"), raw == KOSPI_SOURCE


def vix_card(card: Any) -> dict[str, Any]:
    """기존 VIX 카드 읽기 결과(dataclass) → 칸(최근 시계열은 날짜 오름차순 (날짜, 종가)) · 읽기만 · 계산 없음."""
    return {
        "availability": card.availability,
        "as_of_date": card.as_of_date,
        "close": card.close,
        "change_1d_pct": card.change_1d_pct,
        "change_5d_pct": card.change_5d_pct,
        "series": [(p.date, p.close) for p in (card.recent_20d_series or [])],
    }
