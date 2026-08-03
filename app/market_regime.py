"""Market regime 판정 + 후보 excess_return 계산 (POC2 — 2026-05-22).

본 모듈은 시스템이 **1차 시장 국면 판정** 을 한다 — AI 에게 장세 판단을 맡기는
것이 아니라, KODEX200 (필수) / KOSPI (보조) 의 정량 지표로 라벨을 산출한 뒤
AI 는 그 판정을 검토/해석/반론하는 구조로 사용한다 (지시문 §1 / §11).

판정 기준 (지시문 §6):
- KODEX200 20거래일 / 60거래일 수익률, 20일 / 60일 이동평균 대비 위치를 +1/-1/0
  점수로 환산. 총점 +2 이상 상승장, -2 이하 하락장, 그 외 보합장.
- 데이터 부족 시 판정불가.

후보 excess_return (지시문 §8):
- (후보 ETF 1m/3m 수익률) - (KODEX200 / KOSPI 1m/3m 수익률).
- KOSPI 데이터 없으면 vs_kospi_* 는 null.

본 모듈은 수정 데이터 (state) 를 들지 않는다 — pure function. 입력은
benchmark / candidate 의 시계열 dict, 출력은 market_context dict + per-candidate
excess_return dict.
"""

from __future__ import annotations

from typing import Optional, Sequence

# 거래일 기준 lookback (지시문 §6).
LOOKBACK_20D = 20
LOOKBACK_60D = 60
# 1m / 3m 수익률은 거래일 기준 동일 lookback (시장 데이터 운영 단위와 일치).
# 거래일 20 ≈ 1개월, 60 ≈ 3개월 (KRX 영업일 약 21일/월).
LOOKBACK_1M = LOOKBACK_20D
LOOKBACK_3M = LOOKBACK_60D

KODEX200_TICKER = "069500"
KODEX200_NAME = "KODEX 200"
KOSPI_ID = "KOSPI"
KOSPI_NAME = "KOSPI"
KOSPI_FDR_SYMBOL = "KS11"

# 점수 임계값 (지시문 §6).
SCORE_THRESHOLD_20D_PCT = 2.0
SCORE_THRESHOLD_60D_PCT = 5.0
REGIME_BULL_MIN_SCORE = 2
REGIME_BEAR_MAX_SCORE = -2


def _pct_change(latest: float, base: float) -> Optional[float]:
    if base is None or base <= 0:
        return None
    return (latest / base - 1.0) * 100.0


def _simple_ma(closes: Sequence[float], window: int) -> Optional[float]:
    if len(closes) < window or window <= 0:
        return None
    return sum(closes[-window:]) / float(window)


def _return_n_days_back(closes: Sequence[float], n: int) -> Optional[float]:
    """closes 는 date ASC 정렬. 최근 close 와 n 거래일 전 close 의 % 변화."""
    if len(closes) < n + 1:
        return None
    return _pct_change(closes[-1], closes[-(n + 1)])


def _round_pct(v: Optional[float]) -> Optional[float]:
    if v is None:
        return None
    return round(v, 2)


def compute_kodex200_metrics(history: Sequence[tuple[str, float]]) -> dict:
    """KODEX200 시계열 → 20d/60d 수익률 + MA20/MA60 + 현재가 + 위치.

    history 가 부족하면 status='unavailable' + 필요한 필드는 None.
    """
    closes = [c for _, c in history if c is not None and c > 0]
    if len(closes) < LOOKBACK_60D + 1:
        return {"status": "unavailable"}
    latest_close = closes[-1]
    ma20 = _simple_ma(closes, LOOKBACK_20D)
    ma60 = _simple_ma(closes, LOOKBACK_60D)
    # 2026-07-29 POC3-01 — 기준선 대비 거리(%). 기존 저장값의 단순 산술
    # ((close-ma)/ma*100). 신규 지표·산식 아님 (설계자 Q4-a 확정: MA20·MA60
    # 각각 명시 · 백엔드 제공 · 단일 "시장 전환까지 거리" 표기 금지).
    ma20_distance_pct = (
        _round_pct((latest_close / ma20 - 1.0) * 100.0)
        if ma20 is not None and ma20 > 0
        else None
    )
    ma60_distance_pct = (
        _round_pct((latest_close / ma60 - 1.0) * 100.0)
        if ma60 is not None and ma60 > 0
        else None
    )
    return {
        "status": "ok",
        "return_20d_pct": _round_pct(_return_n_days_back(closes, LOOKBACK_20D)),
        "return_60d_pct": _round_pct(_return_n_days_back(closes, LOOKBACK_60D)),
        "return_1m_pct": _round_pct(_return_n_days_back(closes, LOOKBACK_1M)),
        "return_3m_pct": _round_pct(_return_n_days_back(closes, LOOKBACK_3M)),
        "close": latest_close,
        "ma20": round(ma20, 2) if ma20 is not None else None,
        "ma60": round(ma60, 2) if ma60 is not None else None,
        "ma20_position": (
            "above" if ma20 is not None and latest_close > ma20 else "below"
        ),
        "ma60_position": (
            "above" if ma60 is not None and latest_close > ma60 else "below"
        ),
        "ma20_distance_pct": ma20_distance_pct,
        "ma60_distance_pct": ma60_distance_pct,
    }


def compute_kospi_metrics(history: Sequence[tuple[str, float]]) -> dict:
    """KOSPI 시계열 → 20d/60d/1m/3m 수익률 (보조). 부족 시 unavailable."""
    closes = [c for _, c in history if c is not None and c > 0]
    if len(closes) < LOOKBACK_60D + 1:
        return {"status": "unavailable"}
    return {
        "status": "ok",
        "return_20d_pct": _round_pct(_return_n_days_back(closes, LOOKBACK_20D)),
        "return_60d_pct": _round_pct(_return_n_days_back(closes, LOOKBACK_60D)),
        "return_1m_pct": _round_pct(_return_n_days_back(closes, LOOKBACK_1M)),
        "return_3m_pct": _round_pct(_return_n_days_back(closes, LOOKBACK_3M)),
    }


# ── POC3-06 §6.2 — KOSPI 관찰값 확장 (일간·1년·52주 고점 대비) ─────────────
# 설계자 Q1 확정: 값은 공통 composer 에서 1회 계산, 기존 저장 series 단순 산술.
# 신규 source·DB 없음. "고점 대비" 는 음수%(고점이면 0%) 의미로 통일 — 비율(%) 표기 금지.


def _nearest_prior_close_by_date(
    history: Sequence[tuple[str, float]], target_date: str
) -> Optional[float]:
    """history(date ASC) 에서 target_date 이하의 가장 가까운(가장 최근) 유효 close.

    1년 전 날짜에 정확히 거래일이 없을 수 있으므로 '이전 유효 거래일' 을 취한다.
    """
    prior: Optional[float] = None
    for d, c in history:
        if c is None or c <= 0:
            continue
        if d <= target_date:
            prior = c
        else:
            break
    return prior


def _one_year_ago_iso(latest_date: str) -> Optional[str]:
    """YYYY-MM-DD 문자열의 1년 전 날짜. 파싱 실패 시 None."""
    from datetime import date

    try:
        y, m, d = (int(x) for x in latest_date.split("-"))
    except (ValueError, AttributeError):
        return None
    try:
        return date(y - 1, m, d).isoformat()
    except ValueError:
        # 2/29 → 1년 전 없음. 2/28 로 보정.
        try:
            return date(y - 1, m, d - 1).isoformat()
        except ValueError:
            return None


def compute_kospi_position_metrics(history: Sequence[tuple[str, float]]) -> dict:
    """KOSPI 시계열 → 일간 수익률·1년 수익률·최근 1년 고점 대비 (§6.2).

    - daily_return_pct: 최신 유효 close vs 직전 유효 close.
    - return_1y_pct: 최신 close vs '1년 전 날짜에 가장 가까운 이전 유효 거래일' close.
    - high_52w_gap_pct: (현재 close / 최근 1년 최고 close - 1) * 100. 고점이면 0%,
      아래면 음수. 1년 이력 부족 시 None(자료 없음).
    - as_of_date: 최신 유효 거래일.
    각 값은 독립적으로 계산 불가 시 None — 결측을 0 으로 위장하지 않는다(§9.3).
    """
    valid = [(d, c) for d, c in history if c is not None and c > 0]
    if not valid:
        return {
            "as_of_date": None,
            "daily_return_pct": None,
            "return_1y_pct": None,
            "high_52w_gap_pct": None,
        }

    latest_date, latest_close = valid[-1]
    daily = (
        _round_pct(_pct_change(latest_close, valid[-2][1])) if len(valid) >= 2 else None
    )

    # 1년 수익률·52주 고점: 최신 기준일의 1년 전 이후 구간만 사용.
    # **1년 이력 부족 시 계산하지 않는다(§6.2)**: 저장 series 의 최초 유효 거래일이
    # 1년 전 목표일보다 뒤면(= 이력이 1년을 못 채우면) return_1y·high_gap 모두 None.
    # 이 가드가 없으면 23일짜리 데이터로도 "23일 중 최고" 를 52주 고점으로 오인한다.
    one_year_ago = _one_year_ago_iso(latest_date)
    return_1y = None
    high_gap = None
    earliest_date = valid[0][0]
    has_one_year_history = one_year_ago is not None and earliest_date <= one_year_ago
    if has_one_year_history:
        base = _nearest_prior_close_by_date(valid, one_year_ago)
        if base is not None and base > 0:
            return_1y = _round_pct(_pct_change(latest_close, base))
        window = [c for d, c in valid if d >= one_year_ago]
        if window:
            year_high = max(window)
            if year_high > 0:
                # 고점 대비: 고점이면 0%, 아래면 음수.
                high_gap = _round_pct((latest_close / year_high - 1.0) * 100.0)

    return {
        "as_of_date": latest_date,
        "daily_return_pct": daily,
        "return_1y_pct": return_1y,
        "high_52w_gap_pct": high_gap,
    }


# ── POC3-06 §6.2 — 기존 국면 라벨의 지속 거래일 수 (Q4) ──────────────────
# 기존 market_regime 판정 규칙을 과거 KODEX200 시계열에 그대로 재적용. 신규 규칙
# 없음. 각 거래일 시점까지의 데이터만 사용(미래 데이터 금지). 최신 라벨 계산 불가면
# '자료 없음'(None), 저장 이력 시작점까지 같은 라벨이면 at_least=True(N거래일 이상).


def _label_at(closes: Sequence[float], upto: int) -> Optional[str]:
    """closes[:upto+1] 로 기존 국면 규칙을 적용해 regime_code 반환. 부족 시 None."""
    window = closes[: upto + 1]
    if len(window) < LOOKBACK_60D + 1:
        return None
    metrics = compute_kodex200_metrics([("", c) for c in window])
    if metrics.get("status") != "ok":
        return None
    score, _ = _score_kodex200(metrics)
    code, _label = _label_from_score(score)
    return code


def compute_regime_streak(kodex200_history: Sequence[tuple[str, float]]) -> dict:
    """현재 국면 라벨이 며칠째 이어졌는지 (§6.2·Q4).

    반환: {"regime_code": str|None, "streak_days": int|None, "at_least": bool}.
    - 최신 라벨 계산 불가 → regime_code=None·streak_days=None(자료 없음).
    - 저장 이력 시작점까지 같은 라벨이면 at_least=True (N거래일 이상).
    """
    closes = [c for _, c in kodex200_history if c is not None and c > 0]
    last = len(closes) - 1
    latest_code = _label_at(closes, last) if last >= 0 else None
    if latest_code is None:
        return {"regime_code": None, "streak_days": None, "at_least": False}

    streak = 1
    at_least = False
    i = last - 1
    while i >= 0:
        code_i = _label_at(closes, i)
        if code_i is None:
            # 더 과거는 계산 불가(60일 미만) — 이력 시작점 도달로 간주.
            at_least = True
            break
        if code_i == latest_code:
            streak += 1
            i -= 1
        else:
            break
    return {"regime_code": latest_code, "streak_days": streak, "at_least": at_least}


def _score_kodex200(metrics: dict) -> tuple[int, list[str]]:
    """metrics → (점수 합, 사람이 읽을 사유 리스트). status='ok' 가정."""
    score = 0
    reasons: list[str] = []
    r20 = metrics.get("return_20d_pct")
    r60 = metrics.get("return_60d_pct")
    close = metrics.get("close")
    ma20 = metrics.get("ma20")
    ma60 = metrics.get("ma60")

    if r20 is not None:
        if r20 >= SCORE_THRESHOLD_20D_PCT:
            score += 1
        elif r20 <= -SCORE_THRESHOLD_20D_PCT:
            score -= 1
        sign = "+" if r20 > 0 else ""
        reasons.append(f"KODEX200 20거래일 수익률 {sign}{r20:.2f}%")
    if r60 is not None:
        if r60 >= SCORE_THRESHOLD_60D_PCT:
            score += 1
        elif r60 <= -SCORE_THRESHOLD_60D_PCT:
            score -= 1
        sign = "+" if r60 > 0 else ""
        reasons.append(f"KODEX200 60거래일 수익률 {sign}{r60:.2f}%")
    if close is not None and ma20 is not None:
        if close > ma20:
            score += 1
            reasons.append("현재가가 20일 이동평균 위")
        else:
            score -= 1
            reasons.append("현재가가 20일 이동평균 아래")
    if close is not None and ma60 is not None:
        if close > ma60:
            score += 1
            reasons.append("현재가가 60일 이동평균 위")
        else:
            score -= 1
            reasons.append("현재가가 60일 이동평균 아래")
    return score, reasons


def _label_from_score(score: int) -> tuple[str, str]:
    """(regime_code, regime_label_korean)."""
    if score >= REGIME_BULL_MIN_SCORE:
        return "bull", "상승장"
    if score <= REGIME_BEAR_MAX_SCORE:
        return "bear", "하락장"
    return "neutral", "보합장"


def compute_market_context(
    *,
    asof: Optional[str],
    kodex200_history: Sequence[tuple[str, float]],
    kospi_history: Optional[Sequence[tuple[str, float]]] = None,
) -> dict:
    """KODEX200 + KOSPI 시계열 → market_context dict.

    반환 형식은 지시문 §9.1 응답 예시와 일치 (status / asof / primary_benchmark /
    regime_* / kodex200 / kospi / warnings).

    KODEX200 데이터 부족: status=unavailable, regime_label=판정불가.
    KOSPI 데이터 부족: status=partial, KOSPI 보조 항목만 unavailable, KODEX200
    기준 판정은 그대로 수행 (지시문 §4.4).
    """
    warnings: list[str] = []
    kodex_metrics = compute_kodex200_metrics(kodex200_history)
    kospi_metrics = (
        compute_kospi_metrics(kospi_history)
        if kospi_history is not None
        else {"status": "unavailable"}
    )

    if kodex_metrics.get("status") != "ok":
        warnings.append("KODEX200 benchmark data is insufficient.")
        return {
            "status": "unavailable",
            "asof": asof,
            "primary_benchmark": "KODEX200",
            "regime_label": "판정불가",
            "regime_code": "unavailable",
            "regime_score": None,
            "regime_reasons": [],
            "kodex200": kodex_metrics,
            "kospi": kospi_metrics,
            "warnings": warnings,
        }

    score, reasons = _score_kodex200(kodex_metrics)
    code, label = _label_from_score(score)

    if kospi_metrics.get("status") != "ok":
        warnings.append(
            "KOSPI benchmark data unavailable. Market regime uses KODEX200 only."
        )
        status = "partial"
    else:
        status = "ok"

    return {
        "status": status,
        "asof": asof,
        "primary_benchmark": "KODEX200",
        "regime_label": label,
        "regime_code": code,
        "regime_score": score,
        "regime_reasons": reasons,
        "kodex200": kodex_metrics,
        "kospi": kospi_metrics,
        "warnings": warnings,
    }


def compute_candidate_excess_return(
    *,
    candidate_1m_pct: Optional[float],
    candidate_3m_pct: Optional[float],
    kodex200_1m_pct: Optional[float],
    kodex200_3m_pct: Optional[float],
    kospi_1m_pct: Optional[float] = None,
    kospi_3m_pct: Optional[float] = None,
) -> dict:
    """후보 1건의 excess_return dict (지시문 §9.2).

    각 항목은 (후보 수익률 - benchmark 수익률) percentage point. 어느 한 쪽이
    None 이면 해당 항목은 None (null) 로 유지 — fail-loud 방어 (직전 STEP B-1
    정책 동일).
    """

    def _diff_pp(a: Optional[float], b: Optional[float]) -> Optional[float]:
        if a is None or b is None:
            return None
        return round(a - b, 2)

    return {
        "vs_kodex200_1m_pctp": _diff_pp(candidate_1m_pct, kodex200_1m_pct),
        "vs_kodex200_3m_pctp": _diff_pp(candidate_3m_pct, kodex200_3m_pct),
        "vs_kospi_1m_pctp": _diff_pp(candidate_1m_pct, kospi_1m_pct),
        "vs_kospi_3m_pctp": _diff_pp(candidate_3m_pct, kospi_3m_pct),
    }
