# Phase 9 Specification: Crisis Alpha Strategy

**작성일**: 2025-12-28  
**상태**: **Production Ready** (Gate 3 Passed)  
**버전**: 9.0  

---

## 1. 개요 (Overview)
기존 모멘텀 전략의 약점인 **"횡보장(Choppy Market) 손실"**을 해결하고, **"하락장(Bear Market) 반등"** 수익은 유지하는 **Crisis Alpha** 모델입니다.
2023년 횡보장에서 -20% 손실을 기록했던 기존 모델(Phase 8)을 개선하여, **2023년 수익률 0% (완벽 방어)** 및 **2022년 수익률 +12.6% (알파 유지)**를 달성했습니다.

## 2. 핵심 로직 (Core Logic)

전략은 크게 **Regime Detection (Market Environment)**과 **Signal Generation (Entry/Exit)**으로 나뉩니다.

### 2.1 Market Regime (시장 국면 판단)
벤치마크(`069500` KODEX 200)를 기준으로 다음 3가지 상태를 정의합니다.

1.  **Bull (상승장)**:
    *   조건: `Price >= Long_MA` (120일)
    *   행동: **Risk-On** (적극 매수)
2.  **Bear (하락장)**:
    *   조건: `Price < Long_MA`
    *   행동: **Risk-Off** (전량 현금화)
3.  **Chop (횡보장) [New]**:
    *   조건: `ADX(30) < Threshold(17.5)`
    *   **Prioritized Kill Switch**: 가격이 이평선 위에 있더라도(Bull 신호), ADX가 낮으면 **강제 Risk-Off** 처리.
    *   목적: 추세가 없는 구간에서의 잦은 손절(Whipsaw) 방지.

### 2.2 Golden Cross Override [Phase 8 Legacy]
*   **조건**: `Short_MA(60) > Long_MA(120)`
*   **기능**: Bear Market 상태라 하더라도, 골든크로스가 발생하면 즉시 **Bull**로 전환하여 반등 추세 포착.
*   *Note*: Phase 9에서는 ADX Chop Filter가 이보다 상위 우선순위를 가집니다. (골든크로스여도 ADX 낮으면 진입 금지)

### 2.3 Entry & Exit Logic (RSI Mean Reversion)
Bull Regime일 때만 개별 종목 유니버스에 대해 신호를 생성합니다.

*   **Indicator**: RSI(40)
*   **Buy (Dip Buying)**: `RSI < 50` (상승 추세 중 눌림목 매수)
*   **Sell (Overbought)**: `RSI > 70` (과매수 구간 이익 실현)
*   **Exit (Stop Loss)**: 진입가 대비 `-12%` 하락 시 손절 (System Level Guardrail)

## 3. 파라미터 (Production Config)

| Parameter | Value | Description |
|-----------|-------|-------------|
| `regime_ma_long` | **120** | 레짐 판단용 장기 이평선 |
| `ma_short_period` | **60** | 골든크로스용 단기 이평선 |
| `adx_period` | **30** | 추세 강도(ADX) 계산 기간 |
| `adx_threshold` | **17.5** | 횡보장 판단 기준값 (미만 시 Chop) |
| `rsi_period` | **40** | 개별 종목 매매 타이밍 지표 |
| `stop_loss_pct` | **0.12** | 손실 제한 (12%) |

## 4. 백테스트 성과 (Verification)

### 2022년 (Bear Market Crash)
*   **Return**: +12.62%
*   **MDD**: 12.66%
*   **평가**: 하락장 속 반등 구간을 효과적으로 포착(Alpha).

### 2023년 (Choppy Recovery)
*   **Return**: 0.00%
*   **MDD**: 0.00%
*   **평가**: 지루한 횡보장을 완벽하게 감지하여 거래를 멈춤(Defense).

## 5. 시스템 아키텍처 (Implementation)

*   **Executor**: `core.engine.phase9_executor.Phase9Executor`
*   **Detector**: `core.strategy.market_regime_detector.MarketRegimeDetector` (contains `detect_regime_adx`)
*   **CLI**: `app.cli.alerts` (`--strategy phase9` 옵션)
*   **Config**: `config.production_config.PROD_STRATEGY_CONFIG`

---
**[참고]** 이 문서는 Phase 9 개발 완료 시점에 작성되었습니다. 향후 Phase 10+에서 변경될 수 있습니다.
