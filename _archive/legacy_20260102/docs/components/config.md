# Config Module (`config/`)

**Last Updated**: 2026-01-01
**Purpose**: 시스템 설정 파일 모음 (YAML, Python, JSON)

---

## � File Usage Summary

| File | Status | Used By |
|------|--------|---------|
| `production_config.py` | ✅ **FROZEN** | 레거시 참조 (수정 금지) |
| `production_config_v2.py` | ✅ **ACTIVE** | Phase9Executor, CLI |
| `production_config.yaml` | 🔶 **LEGACY** | 일부 스크립트 |
| `backtest.yaml` | ✅ **ACTIVE** | 백테스트 엔진 |
| `config.yaml` | ✅ **ACTIVE** | 전체 시스템 |
| `universe.yaml` | ✅ **ACTIVE** | 스캐너, 백테스트 |
| `data_sources.yaml` | ✅ **ACTIVE** | data_loader |
| `regime_params.yaml` | ✅ **ACTIVE** | RegimeDetector |
| `rsi_profiles.yaml` | ✅ **ACTIVE** | LiveSignalGenerator |
| `crontab.nas.txt` | ✅ **ACTIVE** | NAS 배포 |
| 기타 | ⚠️ | 개별 확인 필요 |

---

## �📁 주요 파일

### Production Config (전략 파라미터)
| File | Status | Description |
|------|--------|-------------|
| `production_config.py` | ✅ FROZEN | V1 Production Config (수정 금지) |
| `production_config_v2.py` | ✅ ACTIVE | V2 Production Config (RSI Thresholds) |
| `production_config.yaml` | 🔶 LEGACY | YAML 버전 (마이그레이션 권장) |

### Backtest Config
| File | Status | Description |
|------|--------|-------------|
| `backtest.yaml` | ✅ ACTIVE | 백테스트 설정 |
| `backtest_config.yaml` | ⚠️ LOW | 백테스트 파라미터 (중복 확인) |
| `backtest_params.json` | ⚠️ LOW | JSON 파라미터 (중복 확인) |

### Strategy Config
| File | Status | Description |
|------|--------|-------------|
| `regime_params.yaml` | ✅ ACTIVE | Market Regime 파라미터 |
| `rsi_profiles.yaml` | ✅ ACTIVE | RSI 프로파일 설정 |
| `strategy_params.json` | ⚠️ LOW | 전략 파라미터 JSON |
| `universe.yaml` | ✅ ACTIVE | 유니버스 종목 설정 |

### Infrastructure Config
| File | Status | Description |
|------|--------|-------------|
| `config.yaml` | ✅ ACTIVE | 메인 설정 |
| `config.nas.yaml` | ✅ ACTIVE | NAS 배포 설정 |
| `data_sources.yaml` | ✅ ACTIVE | 데이터 소스 우선순위 |
| `us_market_indicators.yaml` | ⚠️ LOW | 미국 시장 지표 설정 |
| `crontab.nas.txt` | ✅ ACTIVE | NAS 크론탭 |

### 환경 설정
| File | Status | Description |
|------|--------|-------------|
| `env.nas.sh` | ✅ ACTIVE | NAS 환경 변수 |
| `env.pc.sample.sh` | ⚠️ SAMPLE | PC 환경 변수 샘플 |

---

## ⚠️ Immutability Policy
- `production_config.py` (V1)는 **절대 수정 금지**
- 파라미터 변경 시 **V2 파일**을 사용하거나 신규 버전 생성

---

## 🧹 정리 권장 사항
1. 🔶 `production_config.yaml`: `.py` 버전으로 통합 검토
2. ⚠️ `backtest_config.yaml`, `backtest_params.json`: 중복 확인 후 통합
3. ⚠️ `strategy_params.json`: 사용 여부 확인
