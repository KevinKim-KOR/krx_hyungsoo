"""POC4-02 공용 봉인 KRX reader (설계자 판정 2026-09-25 §3 · A8 · B4).

02A·02B 가 **수정 없이** import 하는 공통 기반이다. 한쪽에서 변경이 필요하면 임의로 고치지 않고
공통 계약 변경으로 보고한다(판정 §3).

- 봉인 DB 는 `file:<절대경로>?mode=ro&immutable=1` 로만 연다 — 쓰기·DDL 이 불가능하다.
  `app/ml_research_krx_universe.connect` 와 `market_data_store` 는 DDL 을 하므로 쓰지 않는다.
- `verify_sealed_source` — 파일 sha256 · version `SEALED` · content_sha256 재계산
  (`seal_version` 과 같은 식) · member payload hash · row_count · 재수집 충돌 0 · quick_check ·
  integrity_check. 실행 전후 두 번 불러 `assert_same_source` 로 같아야 결과를 쓴다.
- `load_panel` — version member 조인 행만 읽는다(`bas_dd` 로만 고르면 canary·재확인 응답이 섞인다).
- 가격 기준 `KRX_BASEPRICE_CHAIN` (판정 §2) — `r = CMPPREVDD_PRC / (TDD_CLSPRC − CMPPREVDD_PRC)` 를
  `FLUC_RT / 100` 과 허용 오차로 검증한다. 맞지 않는 행은 보정하지 않고 그 행에서 연결 계열을 끊는다
  (새 구간 `segment`). 소비자는 구간을 넘는 창·보유 기간을 제외 사유로 센다.

하지 않는 것 — 봉인 DB 쓰기 · 외부 호출 · 운영 DB 접근 · 보간·이월.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from app.ml_baseline_snapshot import file_sha256

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SEALED_DB = (
    PROJECT_ROOT / "state" / "ml" / "research" / "krx_etf_universe.sqlite"
)
SEALED_VERSION = "krx_etf_universe_v1"
BENCHMARK_CODE = "069500"
PRICE_BASIS = "KRX_BASEPRICE_CHAIN"

# FLUC_RT 는 소수 둘째 자리(%) 반올림이다 — 허용 오차는 그 절반 폭 + 부동소수 여유.
RELATION_TOLERANCE_PCT = 0.005
RELATION_FLOAT_EPS = 1e-9

CLOSE_OK = "OK"
NO_VALID_CLOSE = "NO_VALID_CLOSE"
NON_POSITIVE_CLOSE = "NON_POSITIVE_CLOSE"

_MEMBER_ROWS_SQL = (
    "SELECT m.bas_dd, d.isu_cd, d.row_json FROM krx_dataset_member m "
    "JOIN krx_etf_daily_raw d ON d.response_id = m.response_id "
    "WHERE m.version_id = ? ORDER BY d.isu_cd, m.bas_dd"
)


class SealedSourceError(RuntimeError):
    """봉인 source 계약 위반 — 미봉인 · hash 불일치 · integrity 실패 · 실행 중 변경."""


# --- 연결 --------------------------------------------------------------------


def readonly_uri(db_path: Path) -> str:
    return f"file:{Path(db_path).resolve()}?mode=ro&immutable=1"


def open_readonly(db_path: Path = DEFAULT_SEALED_DB) -> sqlite3.Connection:
    if not Path(db_path).is_file():
        raise SealedSourceError(f"봉인 DB 가 없다: {db_path}")
    return sqlite3.connect(readonly_uri(db_path), uri=True)


# --- 무결성 ------------------------------------------------------------------


def _content_digest(con: sqlite3.Connection, version_id: str) -> tuple[str, list]:
    """`seal_version` 과 같은 식 — member 날짜 순 `bas_dd|payload_sha256` 의 sha256."""
    members = con.execute(
        "SELECT m.bas_dd, r.payload_sha256 FROM krx_dataset_member m JOIN "
        "krx_raw_response r ON r.response_id = m.response_id WHERE m.version_id = ? "
        "ORDER BY m.bas_dd",
        (version_id,),
    ).fetchall()
    digest = hashlib.sha256(
        "".join(f"{d}|{h}\n" for d, h in members).encode("utf-8")
    ).hexdigest()
    return digest, members


def verify_sealed_source(
    db_path: Path = DEFAULT_SEALED_DB,
    *,
    version_id: str = SEALED_VERSION,
    expected_content_sha256: Optional[str] = None,
) -> dict:
    """봉인 source 전체 검증. 하나라도 어긋나면 `SealedSourceError`."""
    path = Path(db_path).resolve()
    size = path.stat().st_size if path.is_file() else None
    sha = file_sha256(path) if path.is_file() else None
    con = open_readonly(path)
    try:
        row = con.execute(
            "SELECT status, content_sha256 FROM krx_dataset_version WHERE version_id = ?",
            (version_id,),
        ).fetchone()
        if row is None:
            raise SealedSourceError(f"version 이 없다: {version_id}")
        status, stored = row
        if status != "SEALED":
            raise SealedSourceError(f"봉인되지 않은 version: {version_id} ({status})")
        digest, members = _content_digest(con, version_id)
        if digest != stored:
            raise SealedSourceError(
                f"content_sha256 불일치: 저장 {stored} · 재계산 {digest}"
            )
        if expected_content_sha256 and digest != expected_content_sha256:
            raise SealedSourceError(
                f"기대한 봉인과 다르다: 기대 {expected_content_sha256} · 실제 {digest}"
            )
        payload_bad = 0
        row_count_bad = 0
        for response_id, payload, payload_sha, row_count, raw_rows in con.execute(
            "SELECT r.response_id, r.payload, r.payload_sha256, r.row_count, "
            "(SELECT COUNT(*) FROM krx_etf_daily_raw d WHERE d.response_id = r.response_id) "
            "FROM krx_dataset_member m JOIN krx_raw_response r "
            "ON r.response_id = m.response_id WHERE m.version_id = ?",
            (version_id,),
        ):
            if hashlib.sha256(payload.encode("utf-8")).hexdigest() != payload_sha:
                payload_bad += 1
            if row_count != raw_rows:
                row_count_bad += 1
        conflicts = con.execute(
            "SELECT COUNT(*) FROM krx_refetch_conflict WHERE version_id = ?",
            (version_id,),
        ).fetchone()[0]
        quick = [r[0] for r in con.execute("PRAGMA quick_check")]
        integrity = [r[0] for r in con.execute("PRAGMA integrity_check")]
    finally:
        con.close()
    if payload_bad or row_count_bad or conflicts:
        raise SealedSourceError(
            f"payload hash 불일치 {payload_bad} · row_count 불일치 {row_count_bad} · "
            f"재수집 충돌 {conflicts}"
        )
    if quick != ["ok"] or integrity != ["ok"]:
        raise SealedSourceError(
            f"integrity 실패: quick={quick[:3]} full={integrity[:3]}"
        )
    dates = [d for d, _ in members]
    return {
        "db_path": str(path),
        "file_size": size,
        "file_sha256": sha,
        "version_id": version_id,
        "status": status,
        "content_sha256": digest,
        "member_dates": len(dates),
        "first_date": dates[0] if dates else None,
        "last_date": dates[-1] if dates else None,
        "payload_hash_mismatch": payload_bad,
        "row_count_mismatch": row_count_bad,
        "refetch_conflicts": conflicts,
        "quick_check": quick[0],
        "integrity_check": integrity[0],
    }


def assert_same_source(before: dict, after: dict) -> None:
    """실행 전후 검증 결과가 모든 필드에서 같아야 한다 — 실행 중 봉인 source 가 바뀌면 실패."""
    if before != after:
        diff = sorted(
            k for k in set(before) | set(after) if before.get(k) != after.get(k)
        )
        raise SealedSourceError(f"실행 중 봉인 source 가 바뀌었다: {diff}")


# --- 행 · 가격 기준 ------------------------------------------------------------


def _num(value) -> Optional[float]:
    if value is None:
        return None
    text = str(value).replace(",", "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def check_relation(
    close: Optional[float], cmpprev: Optional[float], fluc_rt: Optional[float]
) -> tuple[Optional[float], bool]:
    """(일간 수익률, 관계 성립). 판정 §2 — r = CMPPREVDD_PRC / (TDD_CLSPRC − CMPPREVDD_PRC) = FLUC_RT/100.

    previous_reference ≤ 0 · 값 없음 · `|r×100 − FLUC_RT| > 0.005%p` 이면 성립하지 않는다(수익률 None).
    """
    if close is None or cmpprev is None or fluc_rt is None:
        return None, False
    reference = close - cmpprev
    if reference <= 0:
        return None, False
    ret = cmpprev / reference
    if abs(ret * 100.0 - fluc_rt) > RELATION_TOLERANCE_PCT + RELATION_FLOAT_EPS:
        return None, False
    return ret, True


@dataclass
class CodeSeries:
    """한 종목의 v1 행 (날짜 순). 리스트는 모두 같은 길이다."""

    code: str
    dates: list[str] = field(default_factory=list)
    close: list[Optional[float]] = field(default_factory=list)  # TDD_CLSPRC (무조정)
    close_status: list[str] = field(default_factory=list)
    daily_return: list[Optional[float]] = field(default_factory=list)
    relation_ok: list[bool] = field(default_factory=list)
    volume: list[Optional[float]] = field(default_factory=list)  # ACC_TRDVOL
    nav: list[Optional[float]] = field(default_factory=list)
    name: list[str] = field(default_factory=list)  # ISU_NM (그날 이름)
    chain: list[Optional[float]] = field(default_factory=list)  # KRX_BASEPRICE_CHAIN
    segment: list[int] = field(default_factory=list)  # 연결 계열 구간 번호
    index: dict[str, int] = field(default_factory=dict)

    def chain_history(self, upto: Optional[str] = None) -> list[tuple[str, float]]:
        """(날짜, 연결값) — `upto` 이하 · 마지막 행이 속한 구간만 (구간을 넘는 이력을 이어 붙이지 않는다)."""
        end = len(self.dates)
        if upto is not None:
            end = _bisect_right(self.dates, upto)
        if end == 0:
            return []
        last_seg = self.segment[end - 1]
        start = end
        while start > 0 and self.segment[start - 1] == last_seg:
            start -= 1
        return [
            (self.dates[i], self.chain[i])
            for i in range(start, end)
            if self.chain[i] is not None
        ]


def _bisect_right(values: list[str], key: str) -> int:
    lo, hi = 0, len(values)
    while lo < hi:
        mid = (lo + hi) // 2
        if key < values[mid]:
            hi = mid
        else:
            lo = mid + 1
    return lo


def _finish_series(series: CodeSeries) -> None:
    """연결 계열·구간을 만든다. 첫 행과 끊긴 뒤 첫 행은 그날 TDD_CLSPRC 로 시작한다."""
    seg = 0
    for i in range(len(series.dates)):
        ok_close = series.close_status[i] == CLOSE_OK
        if i == 0:
            series.chain.append(series.close[i] if ok_close else None)
            series.segment.append(seg)
            continue
        prev = series.chain[i - 1]
        if ok_close and series.relation_ok[i] and prev is not None:
            series.chain.append(prev * (1.0 + series.daily_return[i]))
            series.segment.append(seg)
            continue
        seg += 1  # 관계 불일치·종가 무효·앞 행 무효 → 새 구간
        series.chain.append(series.close[i] if ok_close else None)
        series.segment.append(seg)
    series.index = {d: i for i, d in enumerate(series.dates)}


@dataclass
class SealedPanel:
    version_id: str
    dates: list[str]  # member 날짜 (YYYY-MM-DD 오름차순) = 거래일 축
    series: dict[str, CodeSeries]
    relation_mismatch_rows: int
    invalid_close_rows: int
    codes_by_date: dict[str, frozenset] = field(default_factory=dict)

    @property
    def final_date(self) -> str:
        return self.dates[-1]

    def present(self, date: str) -> frozenset:
        return self.codes_by_date.get(date, frozenset())

    def benchmark(self) -> CodeSeries:
        if BENCHMARK_CODE not in self.series:
            raise SealedSourceError(f"벤치마크 {BENCHMARK_CODE} 행이 없다")
        return self.series[BENCHMARK_CODE]


def _iso(bas_dd: str) -> str:
    return f"{bas_dd[:4]}-{bas_dd[4:6]}-{bas_dd[6:]}"


def load_panel(
    db_path: Path = DEFAULT_SEALED_DB, *, version_id: str = SEALED_VERSION
) -> SealedPanel:
    """version member 조인 행 → 종목별 시계열. 검증은 `verify_sealed_source` 가 따로 한다."""
    con = open_readonly(db_path)
    try:
        member_dates = [
            r[0]
            for r in con.execute(
                "SELECT bas_dd FROM krx_dataset_member WHERE version_id = ? ORDER BY bas_dd",
                (version_id,),
            )
        ]
        if not member_dates:
            raise SealedSourceError(f"version member 가 없다: {version_id}")
        iso = {d: _iso(d) for d in member_dates}
        names: dict[str, str] = {}
        series: dict[str, CodeSeries] = {}
        by_date: dict[str, set] = {iso[d]: set() for d in member_dates}
        mismatch = invalid = 0
        for bas_dd, isu_cd, row_json in con.execute(_MEMBER_ROWS_SQL, (version_id,)):
            row = json.loads(row_json)
            code = isu_cd or row.get("ISU_CD")
            s = series.get(code)
            if s is None:
                s = series[code] = CodeSeries(code=code)
            close = _num(row.get("TDD_CLSPRC"))
            if close is None:
                status = NO_VALID_CLOSE
            elif close <= 0:
                status = NON_POSITIVE_CLOSE
            else:
                status = CLOSE_OK
            invalid += status != CLOSE_OK
            ret, ok = check_relation(
                close if status == CLOSE_OK else None,
                _num(row.get("CMPPREVDD_PRC")),
                _num(row.get("FLUC_RT")),
            )
            mismatch += not ok and status == CLOSE_OK
            date = iso[bas_dd]
            name = row.get("ISU_NM") or ""
            s.dates.append(date)
            s.close.append(close)
            s.close_status.append(status)
            s.daily_return.append(ret)
            s.relation_ok.append(ok)
            s.volume.append(_num(row.get("ACC_TRDVOL")))
            s.nav.append(_num(row.get("NAV")))
            s.name.append(names.setdefault(name, name))
            by_date[date].add(code)
    finally:
        con.close()
    for s in series.values():
        _finish_series(s)
    return SealedPanel(
        version_id=version_id,
        dates=[iso[d] for d in member_dates],
        series=series,
        relation_mismatch_rows=mismatch,
        invalid_close_rows=invalid,
        codes_by_date={d: frozenset(c) for d, c in by_date.items()},
    )
