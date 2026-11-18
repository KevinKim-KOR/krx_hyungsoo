"""POC6-32 V2 — ETF 공식 기준정보(KRX ETF 기본정보 CSV) 조회 · 두 상품의 지수 상태(PLAN V2 §3-1 R1 · §3-2 D2 · D3 ·
§9 I-6 · I-19 · I-21).

- 값은 CSV 글자 그대로 옮긴다(기초지수명 · 지수산출기관 · 기초시장분류 · 기초자산분류 · 추적배수 · 복제방법 · 총보수 ·
  과세유형 · 상장일). 새 분류 · 추정 값을 만들지 않는다. 파일 선택은 기존 `resolve_official_csv`(최신 유효 파일).
- 종류: CSV 에 있으면 'etf' · CSV 에 없고 ETF 목록(`etf_master`)에도 없으면 'stock'(개별 주식) · CSV 에 없고 ETF 목록에
  있으면 'etf'(공식 기준정보에 없음) · ETF 목록을 읽지 못하면 'unknown'.
- 지수 상태(I-6): 공식 기초지수명이 같으면 '같은 공식 기초지수' · 이름은 다르지만 `index_family.family_of` 계열이 같으면
  '다른 지수 · 같은 계열' · 그 밖 '다른 지수' · 한쪽이라도 공식 기준정보가 없거나 개별 주식이면 '기준 미확인'.
  구조 차이 = 추적배수 · 복제방법 · 총보수 · 과세유형 중 두 쪽 값이 모두 확인됐고(빈 값 아님) 서로 다른 칸(지수 상태와
  따로). 한쪽이라도 비어 있는 칸은 차이가 아니라 '확인 안 된 구조 항목'(`structure_unconfirmed` · 빈 쪽 a · b · both ·
  r1 F2) — '상품 구조 다름'을 만들지 않는다. 빈칸 대신 적힌 자리 표시('-' · '—' · '–' · '－')와 공백뿐인 값도 빈 값과
  같다(`PLACEHOLDERS` · 응답 값 글자는 그대로 둠).
- 읽기 전용 · 외부 호출 0. 같은 프로세스에서 같은 파일(이름 · SHA-256)이면 정리한 표를 다시 쓴다.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional

from app import market_data_store
from app.constituents_pair_exposure_io import read_etf_master
from app.index_family import family_of
from app.market_briefing.official_csv import resolve_official_csv

META_DIR = Path("state/market_meta")

KIND_ETF = "etf"
KIND_STOCK = "stock"
KIND_UNKNOWN = "unknown"

PAIR_SAME = "same"
PAIR_SAME_FAMILY = "same_family"
PAIR_DIFFERENT = "different"
PAIR_UNCONFIRMED = "unconfirmed"
PAIR_LABEL = {
    PAIR_SAME: "같은 공식 기초지수",
    PAIR_SAME_FAMILY: "다른 지수 · 같은 계열",
    PAIR_DIFFERENT: "다른 지수",
    PAIR_UNCONFIRMED: "기준 미확인",
}

WHY_NOT_IN_CSV = "공식 기준정보에 없음"
WHY_STOCK = "개별 주식 · 기초지수 해당 없음"
WHY_CSV_UNREADABLE = "공식 기준정보 파일을 읽지 못함"
WHY_NOT_SELECTED = "고른 상품 없음"

# 응답 칸 → CSV 열(글자 그대로)
_FIELDS = (
    ("name", "한글종목약명"),
    ("index_name", "기초지수명"),
    ("index_provider", "지수산출기관"),
    ("market", "기초시장분류"),
    ("asset", "기초자산분류"),
    ("multiple", "추적배수"),
    ("replication", "복제방법"),
    ("fee_pct", "총보수"),
    ("tax", "과세유형"),
    ("listed", "상장일"),
)
# 상품 구조 비교 칸(D2 · D4 · 화면 이름 = CSV 열 이름)
_STRUCTURE = (
    ("multiple", "추적배수"),
    ("replication", "복제방법"),
    ("fee_pct", "총보수"),
    ("tax", "과세유형"),
)

_CACHE: dict[tuple[Optional[str], Optional[str]], dict[str, dict[str, str]]] = {}


def _rows_of(records: Iterable[Mapping[str, str]]) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for r in records:
        tk = (r.get("단축코드") or "").strip()
        if tk:
            out[tk] = {k: (r.get(col) or "").strip() for k, col in _FIELDS}
    return out


def _cached_rows(
    name: Optional[str], sha: Optional[str], records: Iterable[Mapping[str, str]]
) -> dict[str, dict[str, str]]:
    key = (name, sha)
    if key not in _CACHE:
        _CACHE.clear()  # 파일이 바뀌면 이전 표는 버린다(한 벌만 둠)
        _CACHE[key] = _rows_of(records)
    return _CACHE[key]


def csv_meta(ok: bool, name: Optional[str], asof: Optional[str]) -> dict[str, Any]:
    return {
        "name": name if ok else None,
        "asof": asof if ok else None,
        "ok": ok,
        "error": None if ok else f"{WHY_CSV_UNREADABLE}(유효한 파일 없음)",
    }


def _item(
    ticker: str,
    row: Optional[Mapping[str, str]],
    csv_ok: bool,
    etf_names: Optional[Mapping[str, Optional[str]]],
) -> dict[str, Any]:
    found = row is not None
    if found:
        kind = KIND_ETF
    elif etf_names is None:
        kind = KIND_UNKNOWN
    else:
        kind = KIND_ETF if ticker in etf_names else KIND_STOCK
    out: dict[str, Any] = {"ticker": ticker, "found": found, "kind": kind}
    for key, _ in _FIELDS:
        out[key] = ((row or {}).get(key) or None) if found else None
    if not found and etf_names is not None:
        out["name"] = etf_names.get(ticker)
    if found:
        out["missing_reason"] = None
    elif kind == KIND_STOCK:
        out["missing_reason"] = WHY_STOCK
    elif not csv_ok:
        out["missing_reason"] = WHY_CSV_UNREADABLE
    else:
        out["missing_reason"] = WHY_NOT_IN_CSV
    return out


def build_lookup(
    rows: Mapping[str, Mapping[str, str]],
    csv: Mapping[str, Any],
    tickers: Iterable[str],
    etf_names: Optional[Mapping[str, Optional[str]]],
) -> dict[str, Any]:
    """정리된 CSV 표 → 조회 결과(입력은 모두 인자 · 순수)."""
    items = {}
    for t in dict.fromkeys(x.strip() for x in tickers if x and x.strip()):
        items[t] = _item(t, rows.get(t), bool(csv.get("ok")), etf_names)
    return {"csv": dict(csv), "items": items}


def from_official(
    official: Mapping[str, Mapping[str, str]],
    official_meta: Mapping[str, Any],
    tickers: Iterable[str],
    etf_names: Optional[Mapping[str, Optional[str]]],
) -> dict[str, Any]:
    """이미 읽은 CSV 행(`api_etf_compare._official()` 결과)으로 조회 — 같은 응답 안에서 목록 분류와 같은 파일을 쓴다."""
    ok = official_meta.get("status") == "ok"
    csv = csv_meta(ok, official_meta.get("name"), official_meta.get("csv_asof"))
    return build_lookup(_rows_of(official.values()), csv, tickers, etf_names)


def lookup_official(
    tickers: Iterable[str],
    *,
    meta_dir: Optional[Path] = None,
    db_path: Optional[Path] = None,
    etf_names: Optional[Mapping[str, Optional[str]]] = None,
) -> dict[str, Any]:
    """{csv: {name, asof, ok, error}, items: {코드: {found, kind, name, index_name, …}}} — 읽기 전용."""
    sel = resolve_official_csv(meta_dir if meta_dir is not None else META_DIR)
    rows = _cached_rows(sel.name, sel.sha256, sel.records) if sel.ok else {}
    if etf_names is None:
        # 시장 DB 경로는 부를 때 읽음(모듈 속성 · 시험이 임시 DB 로 바꿔 끼울 수 있게)
        db = db_path if db_path is not None else market_data_store.DEFAULT_DB_PATH
        master = read_etf_master(db)
        etf_names = master[0] if master else None
    return build_lookup(
        rows, csv_meta(sel.ok, sel.name, sel.csv_asof), tickers, etf_names
    )


def _why(it: Optional[Mapping[str, Any]]) -> Optional[str]:
    if it is None:
        return WHY_NOT_SELECTED
    if not it.get("found"):
        if it.get("missing_reason"):
            return str(it["missing_reason"])
        return WHY_STOCK if it.get("kind") == KIND_STOCK else WHY_NOT_IN_CSV
    if not (it.get("index_name") or "").strip():
        return "공식 기초지수명 없음"
    return None


def _same_value(a: Optional[str], b: Optional[str]) -> bool:
    a, b = (a or "").strip(), (b or "").strip()
    if a == b:
        return True
    # 총보수 '0.450000' ↔ '0.45' 처럼 표기만 다른 숫자는 같은 값
    try:
        return Decimal(a) == Decimal(b)
    except (InvalidOperation, ValueError):
        return False


# 빈칸 대신 적힌 자리 표시(하이픈 · 줄표 · 전각 하이픈) = 빈 값과 같이 '확인 안 됨'(앞뒤 공백을 지운 뒤 비교 · r1 G3)
PLACEHOLDERS = frozenset({"-", "—", "–", "－"})


def _confirmed(v: Optional[str]) -> bool:
    s = (v or "").strip()
    return bool(s) and s not in PLACEHOLDERS


def structure_diffs(
    a: Mapping[str, Any], b: Mapping[str, Any]
) -> list[dict[str, Optional[str]]]:
    """두 쪽 모두 공식 기준정보가 있을 때만 · 두 값이 모두 확인됐고(빈 값 아님) 서로 다른 구조 칸(값 그대로 · r1 F2)."""
    if not (a.get("found") and b.get("found")):
        return []
    return [
        {"field": label, "a": a.get(key), "b": b.get(key)}
        for key, label in _STRUCTURE
        if _confirmed(a.get(key))
        and _confirmed(b.get(key))
        and not _same_value(a.get(key), b.get(key))
    ]


def structure_unconfirmed(
    a: Mapping[str, Any], b: Mapping[str, Any]
) -> list[dict[str, str]]:
    """두 쪽 모두 공식 기준정보가 있을 때 값이 비어 있는 구조 칸과 그 쪽(a · b · both) — 차이로 세지 않는다(r1 F2)."""
    if not (a.get("found") and b.get("found")):
        return []
    out = []
    for key, label in _STRUCTURE:
        ea, eb = not _confirmed(a.get(key)), not _confirmed(b.get(key))
        if ea or eb:
            out.append(
                {"field": label, "side": "both" if ea and eb else ("a" if ea else "b")}
            )
    return out


def pair_state(
    a_item: Optional[Mapping[str, Any]], b_item: Optional[Mapping[str, Any]]
) -> dict[str, Any]:
    """두 상품의 지수 상태(D3 · I-6) — 판정 순서: 기준 미확인 → 같은 공식 기초지수 → 같은 계열 → 다른 지수."""
    reasons = [w for w in (_why(a_item), _why(b_item)) if w]
    if reasons or a_item is None or b_item is None:
        return {
            "state": PAIR_UNCONFIRMED,
            "label": PAIR_LABEL[PAIR_UNCONFIRMED],
            "reason": " / ".join(dict.fromkeys(reasons)),
            "structure_diffs": [],
            "structure_unconfirmed": [],
        }
    ia = (a_item.get("index_name") or "").strip()
    ib = (b_item.get("index_name") or "").strip()
    diffs = structure_diffs(a_item, b_item)
    unconfirmed = structure_unconfirmed(a_item, b_item)
    if ia == ib:
        state = PAIR_SAME
        reason = (
            f"두 상품 모두 공식 기초지수 '{ia}'"
            + (" · 상품 구조 다름" if diffs else "")
            + (" · 상품 구조 일부 확인 안 됨" if unconfirmed else "")
        )
    elif family_of(ia) == family_of(ib):
        state = PAIR_SAME_FAMILY
        reason = (
            f"공식 기초지수명이 다름('{ia}' ↔ '{ib}') · 같은 기초지수 계열로 확인됨"
            f"({family_of(ia)})"
        )
    else:
        state = PAIR_DIFFERENT
        reason = f"공식 기초지수가 다름('{ia}' ↔ '{ib}')"
    return {
        "state": state,
        "label": PAIR_LABEL[state],
        "reason": reason,
        "structure_diffs": diffs,
        "structure_unconfirmed": unconfirmed,
    }
