"""POC3-02D-OPS-01 C1 — 운영 공식 CSV resolver (07:20 · 08:00 공유).

설계자 판정 Q1 · Q2 · C1 필수 보완(2026-09-26) · R2 Q25(2026-09-27):

```text
운영 07:20 · 08:00
  → krx_etf_basic_YYYYMMDD.csv 중
     파일명 날짜가 가장 늦고 검증을 통과한 파일을 결정적으로 선택

02B-1 재현 · 장중 설정
  → 승인된 20260909 파일에 계속 고정 (이 모듈을 쓰지 않는다 · Q3)
```

앞으로 CSV 교체는 **데이터 파일만 추가**하는 작업이다. 코드 상수를 바꾸지 않는다.

## 검사 (fail-loud · 거부한 파일은 이름 · 원본 SHA-256 · 사유를 남기고 경고)

- 파일명: 정확히 `krx_etf_basic_YYYYMMDD.csv` · 실제 달력 날짜. `krx_etf_basic_`
  뒤 8자리 날짜를 못 읽으면 `date_parse`, 날짜는 읽히나 이름이 엄격 패턴이 아니면
  `name_pattern`.
- 같은 날짜 파일이 둘 이상(사본 · 접미사 붙은 파일 포함)이면 **그 날짜 묶음 전체**를
  `duplicate_date` 로 무효 처리한다(R2 Q25).
- 내용: CP949 디코딩 · 승인 파일(`20260909`)과 같은 17컬럼(헤더 · 모든 행) · 단축코드
  빈 값 · 중복 없음 · 빈 기초지수명 없음 · 데이터 행 1개 이상.

## 선택

검사를 통과한 파일 중 파일명 날짜가 가장 늦은 것. 최신 파일이 실패하면 직전의 최신
유효 파일로 내려간다(R2 Q25 (a)). **유효 파일이 하나도 없을 때만** 선택 없음 +
`ERROR_NO_VALID_FILE` — 호출자가 `CSV_REFRESH_REQUIRED` 로 fail-closed 한다.

같은 폴더 내용이면 같은 결과다(이름 정렬 · 파일 시각을 보지 않는다).
"""

from __future__ import annotations

import csv
import hashlib
import io
import logging
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Optional

FILE_GLOB = "krx_etf_basic_*.csv"
_STRICT_NAME = re.compile(r"^krx_etf_basic_(\d{8})\.csv$")
# `krx_etf_basic_` 바로 뒤 8자리 — 9자리 이상 숫자는 날짜가 아니다.
_DATE_AFTER_PREFIX = re.compile(r"^krx_etf_basic_(\d{8})(?!\d)")

# 승인 파일 `krx_etf_basic_20260909.csv` 헤더 그대로(2026-09-27 실측 · 17컬럼).
EXPECTED_HEADER: tuple[str, ...] = (
    "표준코드",
    "단축코드",
    "한글종목명",
    "한글종목약명",
    "영문종목명",
    "상장일",
    "기초지수명",
    "지수산출기관",
    "추적배수",
    "복제방법",
    "기초시장분류",
    "기초자산분류",
    "상장좌수",
    "운용사",
    "CU수량",
    "총보수",
    "과세유형",
)

REASON_DATE_PARSE = "date_parse"
REASON_NAME_PATTERN = "name_pattern"
REASON_DUPLICATE_DATE = "duplicate_date"
REASON_READ = "read_error"
REASON_DECODE = "cp949_decode"
REASON_CSV_PARSE = "csv_parse"
REASON_COLUMNS = "columns"
REASON_NO_ROWS = "no_rows"
REASON_EMPTY_TICKER = "empty_ticker"
REASON_DUPLICATE_TICKER = "duplicate_ticker"
REASON_EMPTY_INDEX_NAME = "empty_index_name"

ERROR_NO_VALID_FILE = "official_csv_resolver:no_valid_file"

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class RejectedCsv:
    """검사에 걸린 후보. 원본 SHA-256 은 읽을 수 없었으면 `None`."""

    name: str
    sha256: Optional[str]
    reason: str
    detail: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "sha256": self.sha256,
            "reason": self.reason,
            "detail": self.detail,
        }


@dataclass
class FileCheck:
    """파일 하나의 내용 검사 결과. `records` 가 `None` 이면 실패다."""

    name: str
    sha256: Optional[str]
    records: Optional[list[dict[str, str]]]
    reason: Optional[str] = None
    detail: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.records is not None


@dataclass
class CsvSelection:
    """resolver 결과. `records` 는 **검사를 통과한 그 byte** 를 읽은 행이다."""

    path: Optional[Path] = None
    name: Optional[str] = None
    sha256: Optional[str] = None
    csv_asof: Optional[str] = None
    rows: Optional[int] = None
    records: list[dict[str, str]] = field(default_factory=list)
    rejected: list[RejectedCsv] = field(default_factory=list)
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.path is not None

    def csv_meta(self) -> dict[str, Any]:
        """`meta_gate.evaluate_consistency(csv_meta=...)` 입력."""
        return {"asof_date": self.csv_asof, "sha256": self.sha256, "rows": self.rows}

    def to_dict(self) -> dict[str, Any]:
        """진단 · 기록용. 행 내용은 담지 않는다."""
        return {
            "name": self.name,
            "sha256": self.sha256,
            "csv_asof": self.csv_asof,
            "rows": self.rows,
            "rejected": [r.to_dict() for r in self.rejected],
            "error": self.error,
        }


def _iso(yyyymmdd: str) -> Optional[str]:
    try:
        return date(
            int(yyyymmdd[:4]), int(yyyymmdd[4:6]), int(yyyymmdd[6:])
        ).isoformat()
    except ValueError:
        return None


def parse_name(name: str) -> tuple[Optional[str], Optional[str]]:
    """파일명 → `(ISO 날짜, 거부 사유)`. 날짜를 못 읽으면 `(None, date_parse)`.

    엄격 패턴이면 `(날짜, None)`, 날짜는 읽히나 엄격 패턴이 아니면
    `(날짜, name_pattern)` — 같은 날짜 묶음 판정에는 들어간다.
    """
    m = _DATE_AFTER_PREFIX.match(name)
    day = _iso(m.group(1)) if m else None
    if day is None:
        return None, REASON_DATE_PARSE
    return day, (None if _STRICT_NAME.match(name) else REASON_NAME_PATTERN)


def check_bytes(name: str, raw: bytes) -> FileCheck:
    """CP949 · 17컬럼 · 단축코드 · 기초지수명 검사. **읽기만 한다.**"""
    sha = hashlib.sha256(raw).hexdigest()

    def _fail(reason: str, detail: Optional[str] = None) -> FileCheck:
        return FileCheck(name, sha, None, reason, detail)

    try:
        text = raw.decode("cp949")
    except UnicodeDecodeError as e:
        return _fail(REASON_DECODE, f"byte {e.start}")
    try:
        table = [row for row in csv.reader(io.StringIO(text)) if row]
    except csv.Error as e:
        return _fail(REASON_CSV_PARSE, str(e))
    if not table or tuple(table[0]) != EXPECTED_HEADER:
        return _fail(REASON_COLUMNS, f"header={len(table[0]) if table else 0}")
    body = table[1:]
    for i, row in enumerate(body, start=2):
        if len(row) != len(EXPECTED_HEADER):
            return _fail(REASON_COLUMNS, f"line {i}: {len(row)}")
    if not body:
        return _fail(REASON_NO_ROWS)

    records = [dict(zip(EXPECTED_HEADER, row)) for row in body]
    codes = [(r["단축코드"] or "").strip() for r in records]
    if "" in codes:
        return _fail(REASON_EMPTY_TICKER, f"line {codes.index('') + 2}")
    seen: set[str] = set()
    dups: set[str] = set()
    for c in codes:
        if c in seen:
            dups.add(c)
        seen.add(c)
    if dups:
        return _fail(REASON_DUPLICATE_TICKER, ",".join(sorted(dups)[:5]))
    empty = [c for c, r in zip(codes, records) if not (r["기초지수명"] or "").strip()]
    if empty:
        return _fail(REASON_EMPTY_INDEX_NAME, ",".join(empty[:5]))
    return FileCheck(name, sha, records)


def check_file(path: Path) -> FileCheck:
    try:
        raw = path.read_bytes()
    except OSError as e:
        return FileCheck(path.name, None, None, REASON_READ, type(e).__name__)
    return check_bytes(path.name, raw)


def _raw_sha(path: Path) -> Optional[str]:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def resolve_official_csv(meta_dir: Path, *, logger: Any = None) -> CsvSelection:
    """`meta_dir` 의 `krx_etf_basic_*.csv` 중 **최신 유효 파일**을 고른다.

    예외를 올리지 않는다. 거부한 파일마다 경고 1줄을 남긴다.
    """
    log = logger if logger is not None else _log
    try:
        paths = sorted(
            (p for p in Path(meta_dir).glob(FILE_GLOB) if p.is_file()),
            key=lambda p: p.name,
        )
    except OSError:
        paths = []

    rejected: list[RejectedCsv] = []
    groups: dict[str, list[tuple[Path, Optional[str]]]] = {}
    for p in paths:
        day, name_reason = parse_name(p.name)
        if day is None:
            rejected.append(RejectedCsv(p.name, _raw_sha(p), REASON_DATE_PARSE))
        else:
            groups.setdefault(day, []).append((p, name_reason))

    # 날짜가 늦은 묶음부터. 선택이 끝난 뒤의 옛 파일도 **검사는 한다**(fail-loud).
    selection = CsvSelection()
    for day in sorted(groups, reverse=True):
        members = groups[day]
        if len(members) > 1:
            detail = f"{day}:{len(members)}"
            rejected += [
                RejectedCsv(p.name, _raw_sha(p), REASON_DUPLICATE_DATE, detail)
                for p, _ in members
            ]
            continue
        p, name_reason = members[0]
        if name_reason is not None:
            rejected.append(RejectedCsv(p.name, _raw_sha(p), name_reason))
            continue
        chk = check_file(p)
        if not chk.ok:
            rejected.append(
                RejectedCsv(p.name, chk.sha256, chk.reason or "", chk.detail)
            )
        elif not selection.ok:
            selection = CsvSelection(
                path=p,
                name=p.name,
                sha256=chk.sha256,
                csv_asof=day,
                rows=len(chk.records or []),
                records=chk.records or [],
            )

    selection.rejected = sorted(rejected, key=lambda r: r.name)
    for r in selection.rejected:
        log.warning(
            "공식 CSV 후보 거부: %s reason=%s detail=%s sha256=%s",
            r.name,
            r.reason,
            r.detail,
            r.sha256,
        )
    if not selection.ok:
        selection.error = ERROR_NO_VALID_FILE
    return selection


__all__ = [
    "ERROR_NO_VALID_FILE",
    "EXPECTED_HEADER",
    "FILE_GLOB",
    "REASON_COLUMNS",
    "REASON_CSV_PARSE",
    "REASON_DATE_PARSE",
    "REASON_DECODE",
    "REASON_DUPLICATE_DATE",
    "REASON_DUPLICATE_TICKER",
    "REASON_EMPTY_INDEX_NAME",
    "REASON_EMPTY_TICKER",
    "REASON_NAME_PATTERN",
    "REASON_NO_ROWS",
    "REASON_READ",
    "CsvSelection",
    "FileCheck",
    "RejectedCsv",
    "check_bytes",
    "check_file",
    "parse_name",
    "resolve_official_csv",
]
