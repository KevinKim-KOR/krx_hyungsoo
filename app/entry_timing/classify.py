"""국내 주식형 세 갈래 판정 — PLAN §2-1 · 판정 Q1(회고 연구에 한해 기본정보 사전 수용).

```text
공식 기본정보 일치   그날 지수명 == 2026-09-27 기본정보 `기초지수명` → 그 지수의 (기초시장분류, 기초자산분류)
명칭으로 추정        기본정보에 없는 지수명 — 아래 순서(처음 맞는 줄) · 이름만 · 가격 미사용
                    1 비주식 자산 낱말 → 아님 · 2 국내 + 해외 시장 낱말 → 미확인(충돌)
                    3 국내 시장 낱말 → 국내 주식형 · 4 해외 시장 낱말 → 아님 · 5 나머지 → 미확인
미확인              후보 · 분모에서 빼고 센다(‘미확인 0’이 아니다)
```
제공사 이름 안의 낱말은 근거로 쓰지 않는다(예: 'FnKorea 50' 의 Korea).
"""

from __future__ import annotations

import csv
from pathlib import Path

from app.entry_timing.protocol import CheckRequired

OFF_DE = "OFFICIAL_DE"
OFF_NOT = "OFFICIAL_NOT"
EST_DE = "ESTIMATED_DE"
EST_NOT = "ESTIMATED_NOT"
UNKNOWN = "UNKNOWN"

ASSET_NOT = (
    "채",
    "Bond",
    "Treasury",
    "CD Index",
    "CD금리",
    "Money Market",
    "크레딧",
    "금리",
    "골드",
    "Gold",
    "금현물",
    "리츠",
    "REIT",
    "부동산",
    "TDF",
    "Target",
    "Lifetime",
    "혼합",
    "Blend",
    "TRF",
    "선물",
    "Futures",
    "달러",
    "USD",
    "원자재",
    "Crude",
    "Oil",
    "Metals",
    "Carbon",
)
FOREIGN = (
    "미국",
    "US ",
    "U.S.",
    "나스닥",
    "NASDAQ",
    "S&P 500",
    "S&P500",
    "글로벌",
    "Global",
    "차이나",
    "China",
    "중국",
    "인도",
    "India",
    "베트남",
    "VN30",
    "일본",
    "TOPIX",
    "대만",
    "TAIEX",
    "Brazil",
    "브라질",
    "독일",
    "Germany",
    "유럽",
    "Euro",
    "싱가포르",
    "Singapore",
    "World",
    "ACWI",
    "BRIC",
    "한·중",
    "Tilted",
)
DOMESTIC = (
    "코스피",
    "코스닥",
    "KOSPI",
    "KOSDAQ",
    "KRX 300",
    "KRX300",
    "KRX 100",
    "코리아",
    "KOREA",
    "Korea",
    "한국",
)
PROVIDER_STRIP = ("FnKorea",)

REASON = {
    "asset": "비주식 자산 낱말",
    "conflict": "충돌(국내 · 해외 낱말 함께)",
    "domestic": "국내 시장 낱말",
    "foreign": "해외 시장 낱말",
    "provider": "제공사 이름만 · 이름만으로 판단 어려움",
    "official": "공식 기본정보 일치",
    "empty": "지수명 없음",
}


def rule_text() -> dict:
    return {
        "order": [
            "공식 기본정보 일치(그날 지수명 = 기초지수명 · 국내 × 주식)",
            "비주식 자산 낱말 → 추정 아님",
            "국내 + 해외 시장 낱말 → 미확인(충돌)",
            "국내 시장 낱말 → 추정 국내 주식형",
            "해외 시장 낱말 → 추정 아님",
            "나머지 → 미확인(제공사 이름만 · 판단 어려움)",
        ],
        "asset_not": list(ASSET_NOT),
        "foreign": list(FOREIGN),
        "domestic": list(DOMESTIC),
        "provider_strip": list(PROVIDER_STRIP),
    }


def load_dictionary(path: Path) -> dict[str, tuple[str, str]]:
    """기본정보 CSV(cp949) → {기초지수명: (기초시장분류, 기초자산분류)}. 한 이름에 분류가 둘이면 CheckRequired."""
    seen: dict[str, set] = {}
    with open(path, encoding="cp949", newline="") as fh:
        for row in csv.DictReader(fh):
            name = (row.get("기초지수명") or "").strip()
            if not name:
                continue
            seen.setdefault(name, set()).add(
                (
                    (row.get("기초시장분류") or "").strip(),
                    (row.get("기초자산분류") or "").strip(),
                )
            )
    multi = sorted(n for n, v in seen.items() if len(v) > 1)
    if multi:
        raise CheckRequired(f"기본정보 지수명에 분류가 둘 이상: {multi[:5]}")
    return {n: next(iter(v)) for n, v in seen.items()}


def estimate(name: str) -> tuple[str, str]:
    """기본정보에 없는 지수명의 명칭 추정(PLAN §2-1 2 · 처음 맞는 줄)."""
    if any(w in name for w in ASSET_NOT):
        return EST_NOT, REASON["asset"]
    text = name
    for p in PROVIDER_STRIP:
        text = text.replace(p, "")
    dom = any(w in text for w in DOMESTIC)
    fgn = any(w in text for w in FOREIGN)
    if dom and fgn:
        return UNKNOWN, REASON["conflict"]
    if dom:
        return EST_DE, REASON["domestic"]
    if fgn:
        return EST_NOT, REASON["foreign"]
    return UNKNOWN, REASON["provider"]


def label(name: str, dictionary: dict[str, tuple[str, str]]) -> tuple[str, str]:
    name = (name or "").strip()
    if not name:
        return UNKNOWN, REASON["empty"]
    if name in dictionary:
        market, asset = dictionary[name]
        de = market == "국내" and asset == "주식"
        return (OFF_DE if de else OFF_NOT), REASON["official"]
    return estimate(name)


def is_domestic_equity(lab: str, variant: str) -> bool:
    """MAIN = 공식 일치 + 명칭 추정 · OFFICIAL = 공식 일치만(§4 ⑦ 대조)."""
    if variant == "MAIN":
        return lab in (OFF_DE, EST_DE)
    if variant == "OFFICIAL":
        return lab == OFF_DE
    raise ValueError(variant)
