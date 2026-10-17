"""POC5-20 — 입력 사본 읽기 · 입력 식별 · 리포트 산출(설계 §5 · PLAN §2 · §5).

```text
입력   보유 파일(종목 코드만 · 다계좌 중복 1회) · 시장 DB(`mode=ro` · 하나의 읽기 트랜잭션 · `--end` 이하)
       · 2026 거래일 캘린더(`market_briefing.calendar.load_calendar`) — 이 셋을 입력 사본으로 확정하고
       계산 · 입력 식별 · 산출물이 같은 사본을 쓴다
대상   `etf_master` 에 있는 보유 종목(ETF) · 없는 종목(개별주)은 '대상 밖' 건수만
기준일 2026 캘린더 중 2026-02-19 ~ `--end`
산출   state/ml/research/poc5_20/<종료일>_<생성시각>/ report.md · report.json · input_snapshot.json
       (임시 폴더에 다 쓴 뒤 이름 바꾸기 · DB · 보유 · 원장 쓰기 0)
식별   입력 사본의 정렬 해시(`input_hash`) · 생성 시각을 뺀 본문 해시(`body_hash`) — 같은 입력이면 같은 수치
```

계좌 · 수량 · 평단 · 개인 손익 · 메모는 읽지도 쓰지도 않는다.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from app.evidence_combo.observations import (
    REASONS,
    RawRow,
    Record,
    TickerSeries,
    classify_pair,
)
from app.evidence_combo.render import render_md
from app.evidence_combo.tables import band_table, split_halves
from app.holdings import HOLDINGS_FILE
from app.market_briefing.calendar import CALENDAR_DIR, load_calendar
from app.market_data_store import DEFAULT_DB_PATH
from app.reentry_review.prices import canonical_hash

RESEARCH_ROOT = Path(
    "state/ml/research/poc5_20"
)  # 호출 때 읽는다(시험이 tmp 로 바꾼다)
SCHEMA = "evidence_combo.v1"
START_DATE = "2026-02-19"
CALENDAR_YEAR = 2026
KST = timezone(timedelta(hours=9))
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

QUESTION = (
    "같은 가격 하락 구간 안에서 거래량(직전 20개 저장일 평균 대비)과 가격 흔들림(최근 · 직전 20구간)의 "
    "차이가 이후 20거래일 가격 경로의 차이와 함께 나타났는가"
)
DEFINITIONS: dict[str, str] = {
    "version": "poc5_20.v1",
    "decline": "PC 최근 20저장일 변화 — 종가 유효 저장 행 21개 · `_window_return_pct` · "
    "`classify_decline(normalize_pct(...))`(소수 첫째 자리 · 10% 이상 / 8~10% / 5~8% 하락 · 구간 미해당)",
    "volume": "그날 거래량 ÷ 그날을 뺀 직전 20개 저장일 평균(POC5-09 규칙 · 0 유효 · 결측 · 평균 분모 규칙 그대로) · "
    "**거래량은 표시 반올림 전 배수 기준** — 1 보다 크면 평균 초과, 1 이하면 평균 이하",
    "volatility": "POC5-16 최근 · 직전 20구간 모집단 표준편차(41개 종가 · 공유 경계 종가 · 비정상 행 · 가격 기준 경계 규칙) · "
    "**흔들림은 소수 둘째 자리 표시값 비교** — higher = 커짐 · lower · same = 커지지 않음",
    "outcome": "2026 거래일 캘린더의 t 다음 20거래일 저장 종가 · 끝점 변화 = C(t+20)/C(t) − 1 · "
    "기간 중 최저 종가 변화 = min(0, min_h C(t+h)/C(t) − 1)(h = 1..20) · 저장 결측은 더 먼 날로 채우지 않음 · "
    "연결은 POC5-16 판정(유효 종가 · 허용 출처 · change 연결)",
    "sample": "세 관측이 모두 계산되고 이후 20거래일 결과가 완결된 종목 × 기준일 — 가격 구간 표와 네 조합 표가 같은 표본을 쓴다 · "
    "빠진 건은 정해진 순서에서 처음 걸린 사유 하나로 센다",
    "stats": "중앙값 · 25 / 75 분위 = 기존 `ml_score_validity_metrics.percentile`(선형보간) · "
    "날짜별 중앙값의 중앙값 = 기준일마다 중앙값을 구한 뒤 그 중앙값(보조값)",
}
NOTES: tuple[str, ...] = (
    "현재 보유 ETF 의 저장 가격을 다시 계산한 표본입니다 — 과거 실제 보유 · 과거 알림 · 당시 전체 ETF 시장을 복원한 것이 아닙니다(현재 보유 선택의 편향).",
    "저장 자료는 수집 뒤 고쳐질 수 있습니다. 상품 구조 · 구성 종목이 다른 영향을 조합의 효과로 단정하지 않습니다.",
    "같은 종목의 겹친 20일 경로는 서로 독립이 아닙니다 — 성공률 · 유의확률을 만들지 않았고, 작은 표본도 실제 건수 그대로 보입니다.",
    "끝점 · 최저 종가 변화는 저장 종가 비교입니다 — 장중 저가 · 배당 포함 총수익률 · 개인 손익이 아닙니다.",
    "change 가 없는 NAVER_FDR 구간은 가격 기준 변화를 감지할 수 없어 연결 확인이 부분적입니다(POC5-06 · 16 한계 그대로).",
    "위험 등급 · 점수 · 최적 기준 · 매매 신호 · 운영 채택이 아닙니다. Q6 운영 계약은 OPEN 그대로입니다.",
)


class EndDateError(ValueError):
    """`--end` 형식 · 범위가 맞지 않음."""


@dataclass(frozen=True)
class InputCopy:
    end: str
    held_tickers: tuple[str, ...]
    etf_targets: tuple[str, ...]
    non_etf: tuple[str, ...]
    series: dict[str, TickerSeries]
    calendar: tuple[str, ...]  # 2026 거래일(오름차순)
    calendar_source: str
    db_latest: str  # 대상 종목의 실제 시장 DB 최신 저장일(종료일로 자르지 않음 · 같은 트랜잭션 · `--end` 이상)

    @property
    def base_dates(self) -> list[str]:
        return [d for d in self.calendar if START_DATE <= d <= self.end]


def _calendar_2026(calendar_dir: Optional[Path]) -> tuple[tuple[str, ...], str]:
    cal = load_calendar(calendar_dir or CALENDAR_DIR)
    if cal is None or not cal.covers(CALENDAR_YEAR):
        raise EndDateError(
            "2026 거래일 캘린더(krx_trading_days_*.csv)를 읽을 수 없습니다"
        )
    days = tuple(sorted(d for d in cal.days if d.startswith(f"{CALENDAR_YEAR}-")))
    return days, cal.source_path


def check_end(end: str, calendar: tuple[str, ...]) -> str:
    """`--end YYYY-MM-DD` — 2026-02-19 이상 · 2026 캘린더 마지막 날 이하."""
    if not isinstance(end, str) or not _DATE.match(end):
        raise EndDateError("--end 는 YYYY-MM-DD 형식이어야 합니다")
    try:
        date.fromisoformat(end)
    except ValueError as e:
        raise EndDateError("--end 날짜를 읽을 수 없습니다") from e
    if end < START_DATE:
        raise EndDateError(f"--end 는 {START_DATE} 이후여야 합니다")
    if end > calendar[-1]:
        raise EndDateError(
            f"--end 는 2026 거래일 캘린더 마지막 날({calendar[-1]}) 이하여야 합니다"
        )
    return end


def _held_tickers(holdings_path: Path) -> tuple[str, ...]:
    """보유 파일에서 종목 코드만(다계좌 중복 1회 · 다른 칸은 읽지 않음)."""
    data = json.loads(Path(holdings_path).read_text(encoding="utf-8"))
    rows = data.get("holdings", []) if isinstance(data, dict) else data
    return tuple(
        sorted(
            {str(r["ticker"]) for r in rows if isinstance(r, dict) and r.get("ticker")}
        )
    )


def load_inputs(
    end: str,
    *,
    db_path: Path = DEFAULT_DB_PATH,
    holdings_path: Path = HOLDINGS_FILE,
    calendar_dir: Optional[Path] = None,
) -> InputCopy:
    """입력 사본 확정 — 시장 DB 는 `mode=ro` 하나의 읽기 트랜잭션에서 읽는다."""
    calendar, cal_source = _calendar_2026(calendar_dir)
    end = check_end(end, calendar)
    held = _held_tickers(holdings_path)
    con = sqlite3.connect(
        f"{Path(db_path).resolve().as_uri()}?mode=ro", uri=True, timeout=5.0
    )
    con.isolation_level = None
    try:
        con.execute("BEGIN")
        marks = ",".join("?" * len(held)) or "NULL"
        etfs = {
            r[0]
            for r in con.execute(
                f"SELECT ticker FROM etf_master WHERE ticker IN ({marks})", held
            )
        }
        series: dict[str, TickerSeries] = {}
        for t in sorted(etfs):
            raw = con.execute(
                "SELECT date, close, volume, source, fetched_at, change FROM etf_daily_price "
                "WHERE ticker = ? AND date <= ? ORDER BY date ASC",
                (t, end),
            ).fetchall()
            valid = con.execute(
                "SELECT date, close, volume, source, fetched_at, change FROM etf_daily_price "
                "WHERE ticker = ? AND date <= ? AND close IS NOT NULL AND close > 0 "
                "ORDER BY date ASC",
                (t, end),
            ).fetchall()
            series[t] = TickerSeries(
                ticker=t,
                raw=tuple(RawRow(*r) for r in raw),
                valid=tuple(RawRow(*r) for r in valid),
            )
        # 검증 r1 P2 — 최신 저장일은 종료일로 자르지 않은 실제 값(같은 트랜잭션 · 대상 종목 전체 행).
        # 종료일까지 자른 행으로 구하면, 종료일 행 하나만 빠져도 정상 종료일을 거절하고 실제보다 이른 날을 적는다.
        marks_t = ",".join("?" * len(etfs)) or "NULL"
        latest = con.execute(
            f"SELECT MAX(date) FROM etf_daily_price WHERE ticker IN ({marks_t})",
            tuple(sorted(etfs)),
        ).fetchone()[0]
        con.execute("COMMIT")
    finally:
        con.close()
    # 검토 L2 — DB 최신 저장일 뒤의 날은 '아직 저장되지 않은 날'이다. 받으면 그 기준일 · 경로가 미도래가 아니라
    # 종가 없음 · 저장 결측으로 잘못 분류된다 → 실행하지 않는다.
    if latest is None or end > latest:
        raise EndDateError(
            f"--end 는 대상 종목의 시장 DB 최신 저장일({latest or '없음'}) 이하여야 합니다"
        )
    return InputCopy(
        end=end,
        held_tickers=held,
        etf_targets=tuple(sorted(etfs)),
        non_etf=tuple(t for t in held if t not in etfs),
        series=series,
        calendar=calendar,
        calendar_source=cal_source,
        db_latest=latest,
    )


def input_snapshot(inp: InputCopy) -> dict[str, Any]:
    """입력 식별에 쓰는 사본 — 종목 · 기간 · 종가 · 거래량 · 출처 · change · 캘린더 · 정의."""
    return {
        "schema": SCHEMA,
        "end": inp.end,
        "start": START_DATE,
        "held_tickers": list(inp.held_tickers),
        "db_latest": inp.db_latest,
        "etf_targets": list(inp.etf_targets),
        "non_etf_excluded": list(inp.non_etf),
        "calendar_days": list(inp.calendar),
        "definitions": DEFINITIONS,
        "rows": {
            t: [
                [r.date, r.close, r.volume, r.source, r.fetched_at, r.change]
                for r in s.raw
            ]
            for t, s in sorted(inp.series.items())
        },
        "valid_dates": {
            t: [r.date for r in s.valid] for t, s in sorted(inp.series.items())
        },
    }


def _span(days: list[str]) -> dict[str, Any]:
    return (
        {"first": days[0], "last": days[-1], "days": len(days)} if days else {"days": 0}
    )


def _dump(body: dict[str, Any]) -> str:
    return json.dumps(body, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def build_report(
    inp: InputCopy, *, input_hash: str, generated_at: str
) -> dict[str, Any]:
    base = inp.base_dates
    calendar = list(inp.calendar)
    counts: Counter[str] = Counter()
    records: list[Record] = []
    for t in inp.etf_targets:
        s = inp.series[t]
        for d in base:
            reason, rec = classify_pair(s, d, calendar, inp.end)
            if rec is not None:
                records.append(rec)
            else:
                counts[str(reason)] += 1
    front, back = split_halves(base)
    front_set, back_set = set(front), set(back)
    sample_dates = sorted({r.date for r in records})  # 검토 L3 — 실제 자료 기간
    body: dict[str, Any] = {
        "schema": SCHEMA,
        "step": "POC5-20",
        "question": QUESTION,
        "end": inp.end,
        "start": START_DATE,
        "input_hash": input_hash,
        "definitions": DEFINITIONS,
        "universe": {
            "held_tickers": len(inp.held_tickers),
            "etf_targets": list(inp.etf_targets),
            "non_etf_excluded": list(inp.non_etf),
            "base_dates": _span(base),
            "pairs": len(inp.etf_targets) * len(base),
            "front": _span(front),
            "back": _span(back),
            "common_sample_dates": _span(sample_dates),
            "front_sample_dates": _span([d for d in sample_dates if d in front_set]),
            "back_sample_dates": _span([d for d in sample_dates if d in back_set]),
            "db_latest": inp.db_latest,
            "calendar_source": inp.calendar_source,
        },
        "exclusions": [
            {"code": c, "label": lab, "count": counts.get(c, 0)} for c, lab in REASONS
        ],
        "common_sample": len(records),
        "tables": {
            "all": band_table(records),
            "front": band_table([r for r in records if r.date in front_set]),
            "back": band_table([r for r in records if r.date in back_set]),
        },
        "notes": list(NOTES),
    }
    return {**body, "generated_at": generated_at, "body_hash": canonical_hash(body)}


def _write(folder: Path, files: dict[str, str]) -> None:
    staging = (
        folder.parent / f".{folder.name}.partial"
    )  # 다 쓴 뒤에만 보이는 이름으로 바꾼다
    folder.parent.mkdir(parents=True, exist_ok=True)
    staging.mkdir(exist_ok=False)
    try:
        for name, text in files.items():
            (staging / name).write_text(text, encoding="utf-8")
        os.rename(staging, folder)
    except OSError:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def run(
    end: str,
    *,
    db_path: Path = DEFAULT_DB_PATH,
    holdings_path: Path = HOLDINGS_FILE,
    calendar_dir: Optional[Path] = None,
    root: Optional[Path] = None,
    now: Optional[datetime] = None,
) -> Path:
    """한 번 실행 → 새 산출 폴더 경로."""
    inp = load_inputs(
        end, db_path=db_path, holdings_path=holdings_path, calendar_dir=calendar_dir
    )
    snapshot = input_snapshot(inp)
    input_hash = canonical_hash(snapshot)
    stamp = (now or datetime.now(KST)).astimezone(KST)
    report = build_report(inp, input_hash=input_hash, generated_at=stamp.isoformat())
    folder = (
        Path(root or RESEARCH_ROOT) / f"{inp.end}_{stamp.strftime('%Y%m%dT%H%M%S%f')}"
    )
    _write(
        folder,
        {
            "report.md": render_md(report),
            "report.json": _dump(report),
            "input_snapshot.json": _dump({**snapshot, "input_hash": input_hash}),
        },
    )
    return folder
