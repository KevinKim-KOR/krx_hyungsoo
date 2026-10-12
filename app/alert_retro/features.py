"""POC5-08 — ML 입력 허용 목록 · 단위 · 대상 범위(PLAN §1-2 · §2-6 · 설계 §5).

```text
라벨        +5 MATURED return_raw(소수 비율)
범위        보유 브리핑 · 장중 의 ticker · sector 중 price_basis 의 '|' 앞이 KRX_ETF_UNADJUSTED ·
            KRX_STOCK_UNADJUSTED 와 정확히 같은 행 · 계약 버전 *.v1 — 시장 · 기초지수는 원시 결과만
숫자 2개    20거래일 변화 · 당일 변화 — values_json 의 % 값(8.8 = +8.8%) ÷ 100 = 비율 · 없으면 None
            (구조적 결측 포함 · 새로 계산하지 않음) · 개인 손익률(profit_loss_pct) · 다른 키는 읽지 않는다
범주 6개    push_kind · subject_kind · state · event_type · exposure · held — NULL = 'NONE'
```
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any, Optional

ML_HORIZON = 5
ML_PUSH_KINDS = ("holdings_briefing", "holdings_risk_alert")
ML_SUBJECT_KINDS = ("ticker", "sector")
ML_PRICE_BASES = ("KRX_ETF_UNADJUSTED", "KRX_STOCK_UNADJUSTED")
SUPPORTED_CONTRACTS = ("holdings_briefing.v1", "holdings_risk_alert.v1")

NUMERIC = ("return_20d", "day_return")
CATEGORICAL = ("push_kind", "subject_kind", "state", "event_type", "exposure", "held")
NONE = "NONE"

# (push_kind, subject_kind) → {feature: values_json 키(% 단위)} — 판정에 실제 쓴 값만(PLAN §1-2).
NUMERIC_KEYS: dict[tuple[str, str], dict[str, str]] = {
    ("holdings_briefing", "ticker"): {"return_20d": "return_20d_pct"},
    ("holdings_risk_alert", "ticker"): {"day_return": "day_return_pct"},
    ("holdings_risk_alert", "sector"): {
        "return_20d": "return_20d_pct",
        "day_return": "day_return_pct",
    },
}

# ML 칸 사유 코드 → 화면 문구.
REASON_TEXT = {
    "OUT_OF_SCOPE": "이번 ML 범위 밖(시장 · 기초지수 그룹은 원시 결과만)",
    "UNSUPPORTED_CONTRACT": "지원 안 되는 계약 버전",
    "UNSUPPORTED_PRICE_BASIS": "지원 안 되는 가격 기준",
    "NOT_MATURED": "+5 미성숙",
    "NO_LABEL": "+5 결과 없음(결측 상태)",
    "OUTSIDE_TEST": "시험 구간 밖",
    "DATA_SHORT": "자료 부족(그 시험 구간)",
}


def price_base(basis: Optional[str]) -> Optional[str]:
    """`KRX_ETF_UNADJUSTED|ETF` → `KRX_ETF_UNADJUSTED`(접미는 snapshot 에 그대로 남긴다)."""
    if basis is None:
        return None
    return str(basis).split("|", 1)[0]


def scope_reason(item: dict[str, Any]) -> Optional[str]:
    """item 이 ML 범위 밖이면 사유 코드 · 안이면 None(가격 기준 · 성숙은 행마다 따로 본다)."""
    if (
        item["push_kind"] not in ML_PUSH_KINDS
        or item["subject_kind"] not in ML_SUBJECT_KINDS
    ):
        return "OUT_OF_SCOPE"
    if item.get("contract_version") not in SUPPORTED_CONTRACTS:
        return "UNSUPPORTED_CONTRACT"
    return None


def _ratio(value: Any) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not math.isfinite(float(value)):
        return None
    return float(value) / 100.0


def numeric(
    values: dict[str, Any], push_kind: str, subject_kind: str
) -> dict[str, Optional[float]]:
    keys = NUMERIC_KEYS.get((push_kind, subject_kind), {})
    return {
        name: (_ratio(values.get(keys[name])) if name in keys else None)
        for name in NUMERIC
    }


def categories(item: dict[str, Any]) -> dict[str, str]:
    out = {}
    for name in CATEGORICAL:
        value = item.get(name)
        out[name] = NONE if value is None else str(value)
    return out


def aware_time(value: Any) -> Optional[datetime]:
    """시간대가 붙은 ISO 시각만 읽는다 — 읽을 수 없거나 시간대가 없으면 None(대체 시각을 만들지 않음).

    `runtime_kst` · `computed_at` 은 이 규칙으로 `population.check_copy` 가 먼저 막는다."""
    if not isinstance(value, str):
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    return dt if dt.tzinfo is not None else None


def observations(items: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict]:
    """+5 슬롯마다 ML 관측(라벨 있는 행) 또는 사유 코드.

    반환 = (관측 목록, {(event_id, item_seq, 슬롯 순번): 사유 코드})."""
    obs: list[dict[str, Any]] = []
    reasons: dict[tuple[str, int, int], str] = {}
    for item in items:
        scope = scope_reason(item)
        for n, slot in enumerate(item["slots"]):
            if slot["horizon"] != ML_HORIZON:
                continue
            key = (item["event_id"], item["item_seq"], n)
            if scope is not None:
                reasons[key] = scope
            elif slot["status"] in ("PENDING_NOT_DUE", "PENDING_DUE"):
                reasons[key] = "NOT_MATURED"
            elif (
                slot["status"] != "MATURED"
                or slot["return_raw"] is None
                or not slot["eval_date"]
            ):
                reasons[key] = "NO_LABEL"
            elif price_base(slot["price_basis"]) not in ML_PRICE_BASES:
                reasons[key] = "UNSUPPORTED_PRICE_BASIS"
            else:
                runtime = aware_time(item["runtime_kst"])
                computed = aware_time(slot["computed_at"])
                if (
                    runtime is None or computed is None
                ):  # check_copy 를 거치지 않은 입력
                    raise ValueError("시각 형식 손상(runtime_kst · computed_at)")
                obs.append(
                    {
                        "event_id": item["event_id"],
                        "item_seq": item["item_seq"],
                        "slot": n,
                        "series_id": slot["series_id"],
                        "signal_date": item["signal_date"],
                        "runtime": runtime,
                        "eval_date": slot["eval_date"],
                        "computed": computed,
                        "y": float(slot["return_raw"]),
                        "num": item["numeric"],
                        "cat": categories(item),
                        "group": f"{item['push_kind']}/{item['subject_kind']}",
                    }
                )
    obs.sort(
        key=lambda o: (o["signal_date"], o["event_id"], o["item_seq"], o["series_id"])
    )
    return obs, reasons
