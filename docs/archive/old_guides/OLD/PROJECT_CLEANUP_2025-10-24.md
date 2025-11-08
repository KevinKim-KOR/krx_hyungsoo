# 프로젝트 정리 작업 (2025-10-24)

## 🎯 목표

친구 코드 구조([momentum-etf](https://github.com/jasonisdoing/momentum-etf))를 참고하여 프로젝트를 정리하고 불필요한 파일 제거

---

## 📋 작업 내용

### 1. 루트 디렉토리 정리

**제거된 파일:**
- 중복 Python 파일 (19개): `adaptive.py`, `analyzer.py`, `app.py`, `backtest.py`, `backtest_cli.py`, `cache_store.py`, `calendar_kr.py`, `db.py`, `fetchers.py`, `indicators.py`, `krx_helpers.py`, `notifications.py`, `report_eod_cli.py`, `report_watchlist_cli.py`, `reporting_eod.py`, `scanner.py`, `sector_autotag.py`, `signals_cli.py`, `strategies.py`
- 임시 파일: `commit_message*.txt`, `config_friend.yaml`, `kr_cache_pc.txt`, `sitecustomize.py`, `update_from_git.sh`
- 구 설정 파일: `config.py`, `config.yaml`, `watchlist.yaml`, `sectors_map.csv`, `seed_universe.csv`
- 구 requirements: `requirements*.txt` (5개)

**제거된 디렉토리:**
- `providers/` → `core/providers/`로 이동 완료
- `utils/` → `core/utils/`로 이동 완료
- `ml/` → `pc/ml/`로 이동 완료
- `compat/`, `experimental/`, `ingest/`, `signals/`, `tools/` (미사용)

---

### 2. 새로운 설정 파일 구조

친구 코드의 `data/settings/` 구조를 참고하여 `config/` 재구성:

**생성된 파일:**
- `config/common.yaml`: 공통 설정 (DB, 타임존, 캐시)
- `config/scanner_config.yaml`: 스캐너 전략 설정 (MAPS, RSI, 시장 레짐)
- `config/universe.yaml`: 투자 유니버스 (ETF 리스트)

**기존 유지:**
- `config/data_sources.yaml`: 데이터 소스 우선순위
- `config/scanner.yaml`: 기존 스캐너 설정 (호환성)
- `config/env.nas.sh`, `config/env.pc.sh`: 환경 변수

---

### 3. 문서 업데이트

**README.md 개선:**
- 아키텍처 섹션 명확화 (core/, nas/, pc/ 구조)
- 명령어 가이드 업데이트 (모듈 분리 반영)
- 개발 워크플로우 추가 (PC 테스트 → NAS 배포)
- 설정 파일 섹션 재구성
- 로드맵 업데이트 (현재 상태 반영)

---

## 🏗️ 최종 구조

```
krx_alertor_modular/
├── core/                  # 공통 모듈 (NAS + PC)
│   ├── db.py
│   ├── fetchers.py
│   ├── calendar_kr.py
│   ├── indicators.py
│   ├── providers/
│   │   ├── ohlcv.py
│   │   └── ohlcv_bridge.py
│   └── utils/
│       ├── config.py
│       ├── datasources.py
│       └── trading.py
│
├── nas/                   # NAS 전용 (경량)
│   ├── app_nas.py
│   ├── scanner_nas.py
│   ├── requirements.txt
│   └── README_NAS.md
│
├── pc/                    # PC 전용 (전체 기능)
│   ├── app_pc.py
│   ├── backtest.py
│   ├── scanner.py
│   ├── analyzer.py
│   ├── requirements.txt
│   └── ml/
│
├── config/                # 설정 파일
│   ├── common.yaml        # 공통 설정 (NEW)
│   ├── scanner_config.yaml # 스캐너 설정 (NEW)
│   ├── universe.yaml      # 투자 유니버스 (NEW)
│   ├── data_sources.yaml
│   └── env.nas.sh
│
├── scripts/               # 배치 스크립트
│   └── linux/
│       ├── batch/
│       └── jobs/
│
├── docs/                  # 문서
│   ├── PROJECT_CLEANUP_2025-10-24.md (NEW)
│   ├── MIGRATION_GUIDE.md
│   └── NAS_TEST_GUIDE.md
│
├── data/                  # 데이터
│   ├── cache/
│   └── output/
│
└── README.md              # 업데이트됨
```

---

## 📊 친구 코드에서 배운 점

### 1. 명확한 레이어 분리
- `logic/`: 전략 로직
- `utils/`: 공통 유틸리티
- `scripts/`: 운영 스크립트
- `data/settings/`: 설정 파일

### 2. 설정 중심 구조
- `data/settings/account/*.json`: 계정별 전략 설정
- `data/settings/common.py`: 공통 설정
- 설정 파일 기반으로 모든 동작 제어

### 3. 깔끔한 루트
- CLI 진입점만 루트에 배치 (`app.py`, `recommend.py`, `backtest.py`, `tune.py`)
- 모든 로직은 하위 디렉토리로 분리

### 4. 공통 유틸리티
- `utils/indicators.py`: 중복 제거된 지표 계산
- `utils/report.py`: 통일된 포맷팅
- `utils/data_loader.py`: 데이터 로딩 추상화

---

## ✅ 적용한 개선사항

1. **루트 디렉토리 정리**: 중복 파일 제거, 모듈 분리 완료
2. **설정 파일 재구성**: `config/` 디렉토리에 역할별 YAML 파일
3. **문서 업데이트**: README.md 명확화, 워크플로우 추가
4. **구조 명확화**: core/nas/pc 역할 분리

---

## 🚀 다음 단계

1. **PC에서 테스트**
   ```bash
   python nas/app_nas.py scanner --date 2024-10-23
   ```

2. **DataFrame 에러 수정**
   - `core/providers/ohlcv_bridge.py` 체크 로직 개선
   - PC에서 디버깅 후 NAS 배포

3. **캘린더 로딩 안정화**
   - 폴백 로직 강화
   - 캐시 우선 사용

4. **스캐너 신호 튜닝**
   - 친구 코드의 MAPS 전략 참고
   - RSI, 시장 레짐 필터 추가

---

## 📝 참고

- 친구 프로젝트: https://github.com/jasonisdoing/momentum-etf
- 모듈 분리 가이드: `docs/MIGRATION_GUIDE.md`
- NAS 테스트 가이드: `docs/NAS_TEST_GUIDE.md`
