"""KRX ETF 전종목 기본정보 CSV 검사 (POC3-02D-OPS-01 C1 · PC 전용).

07:20 · 08:00 이 쓰는 **공용 resolver**(`app.market_briefing.official_csv`)와 같은
검사를 돌려, 새 원본을 `state/market_meta/krx_etf_basic_YYYYMMDD.csv` 로 추가해도
되는지 먼저 본다. 설계자 C1 필수 보완 — 이 스크립트와 C1 집중 테스트가 통과하면
코드 변경이 없는 데이터 갱신은 전체 검증자를 다시 거치지 않는다(commit · push ·
OCI pull 승인은 그대로).

**읽기만 한다.** 파일을 쓰거나 옮기지 않고, 외부 호출이 없다.

```bash
python scripts/check_krx_etf_basic_csv.py                         # 폴더 · 선택 결과
python scripts/check_krx_etf_basic_csv.py ~/Downloads/new.csv     # 원본 내용 검사
python scripts/check_krx_etf_basic_csv.py NEW.csv \
    --compare state/market_meta/krx_etf_basic_20260909.csv          # 추가·삭제 ticker
python scripts/check_krx_etf_basic_csv.py --meta-dir /tmp/meta    # 다른 폴더
```

종료 코드: resolver 가 폴더에서 유효 파일을 고르고, 선택 날짜 이상이거나 파일명
날짜를 읽을 수 없는 거부 후보가 없고(새 파일이 조용히 안 쓰이는 경우), 넘긴 파일이
모두 내용 검사를 통과하면(비교 파일 포함) 0. 아니면 1.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional, Sequence

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from app.market_briefing import official_csv  # noqa: E402

DEFAULT_META_DIR = _PROJECT_ROOT / "state" / "market_meta"
# 비교 결과 목록은 이만큼만 찍는다(개수는 전부 센다).
MAX_LISTED = 30


class _Quiet:
    """resolver 경고는 아래에서 `거부:` 줄로 한 번만 찍는다."""

    def warning(self, msg: str, *args: object) -> None:
        pass


def _names(records: Sequence[dict[str, str]]) -> dict[str, str]:
    return {r["단축코드"].strip(): r["기초지수명"].strip() for r in records}


def _listed(codes: list[str]) -> str:
    tail = f" 외 {len(codes) - MAX_LISTED}개" if len(codes) > MAX_LISTED else ""
    return ", ".join(codes[:MAX_LISTED]) + tail


def _check_given(path: Path) -> official_csv.FileCheck:
    chk = official_csv.check_file(path)
    print(f"[파일] {path}")
    print(f"  sha256={chk.sha256}")
    if chk.ok:
        print(f"  내용 검사 통과 · 행 {len(chk.records or [])}")
    else:
        print(f"  내용 검사 실패 · reason={chk.reason} detail={chk.detail}")
    day, name_reason = official_csv.parse_name(path.name)
    if day is not None and name_reason is None:
        print(f"  파일명 그대로 resolver 후보(csv_asof={day})")
    else:
        print(
            "  파일명이 resolver 후보가 아니다 — "
            "`krx_etf_basic_YYYYMMDD.csv` 로 추가해야 선택된다"
        )
    return chk


def _unused_newer(sel: official_csv.CsvSelection) -> list[str]:
    """거부 후보 중 선택 날짜 **이상**이거나 날짜를 못 읽는 파일명.

    이런 파일이 있으면 새로 넣은 CSV 가 조용히 쓰이지 않는 것이다. 선택보다
    오래된 거부 후보는 운영에 영향이 없다. 날짜는 resolver 와 같은
    `official_csv.parse_name` 으로 읽는다.
    """
    out = []
    for r in sel.rejected:
        day, _ = official_csv.parse_name(r.name)
        if day is None or day >= (sel.csv_asof or ""):
            out.append(r.name)
    return out


def _off_pattern(meta_dir: Path) -> list[str]:
    """resolver 후보(`FILE_GLOB`)에 걸리지 않는 **비슷한 이름**의 파일.

    대소문자 · 밑줄 · 확장자가 조금만 달라도 resolver 는 그 파일을 보지 않는다
    (거부 목록에도 없다). 새로 넣은 CSV 가 조용히 쓰이지 않는 또 다른 경우라
    폴더 검사에서 함께 실패로 본다.
    """
    try:
        entries = sorted(p for p in Path(meta_dir).iterdir() if p.is_file())
    except OSError:
        return []
    listed = {p.name for p in Path(meta_dir).glob(official_csv.FILE_GLOB)}
    return [
        p.name
        for p in entries
        if p.name.lower().startswith("krx_etf_basic") and p.name not in listed
    ]


def _compare(new: official_csv.FileCheck, old: official_csv.FileCheck) -> None:
    a, b = _names(new.records or []), _names(old.records or [])
    added = sorted(set(a) - set(b))
    removed = sorted(set(b) - set(a))
    renamed = sorted(t for t in set(a) & set(b) if a[t] != b[t])
    print(f"[비교] {new.name} 대 {old.name}")
    print(f"  추가 ticker {len(added)}: {_listed(added)}")
    print(f"  삭제 ticker {len(removed)}: {_listed(removed)}")
    print(f"  기초지수명 변경 {len(renamed)}: {_listed(renamed)}")


def main(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(description="KRX ETF 기본정보 CSV 검사 (읽기 전용)")
    p.add_argument("paths", nargs="*", type=Path, help="검사할 CSV 원본(선택)")
    p.add_argument("--meta-dir", type=Path, default=DEFAULT_META_DIR)
    p.add_argument("--compare", type=Path, help="추가·삭제 ticker 를 비교할 CSV")
    args = p.parse_args(argv)

    ok = True
    print(f"[폴더] {args.meta_dir}")
    sel = official_csv.resolve_official_csv(args.meta_dir, logger=_Quiet())
    for r in sel.rejected:
        print(f"  거부: {r.name} reason={r.reason} detail={r.detail} sha256={r.sha256}")
    if sel.ok:
        print(
            f"  resolver 선택: {sel.name} · csv_asof={sel.csv_asof} · 행 {sel.rows}"
            f" · sha256={sel.sha256}"
        )
        unused = _unused_newer(sel)
        for name in unused:
            print(
                f"  새 파일이 쓰이지 않는다: {name} — 선택 파일({sel.csv_asof})보다"
                " 새롭거나 같은 날짜이거나, 파일명 날짜를 읽을 수 없다"
            )
        ok = not unused
    else:
        print(f"  resolver 선택 없음: {sel.error}")
        ok = False
    off = _off_pattern(args.meta_dir)
    for name in off:
        print(
            f"  파일명이 resolver 후보가 아니다: {name} — "
            "`krx_etf_basic_YYYYMMDD.csv`(소문자 · .csv)로 넣어야 선택된다"
        )
    if off:
        ok = False

    checks = [_check_given(path) for path in args.paths]
    ok = ok and all(c.ok for c in checks)

    if args.compare is not None:
        old = _check_given(args.compare)
        new: Optional[official_csv.FileCheck] = checks[0] if checks else None
        if new is None and sel.ok and sel.path is not None:
            new = official_csv.check_file(sel.path)
        if new is None or not new.ok or not old.ok:
            print("[비교] 비교할 두 파일이 모두 내용 검사를 통과해야 한다")
            ok = False
        else:
            _compare(new, old)

    print("결과: 통과" if ok else "결과: 실패")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
