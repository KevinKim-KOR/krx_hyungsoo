# Phase 3.3: config/ 분석

**작성일**: 2025-11-28  
**상태**: 분석 완료

---

## 📊 현재 config/ 구조

```
config/
├── backtest_params.json         # 백테스트 파라미터
├── common.yaml                  # 공통 설정
├── config.nas.yaml              # NAS 전용 설정
├── config.template.yaml         # 설정 템플릿
├── config.yaml                  # 메인 설정 ⚠️ 중복
├── crontab.cloud.txt            # Oracle Cloud Cron
├── crontab.nas.fixed.txt        # NAS Cron (수정본) ⚠️ 중복
├── crontab.nas.txt              # NAS Cron ⚠️ 중복
├── crontab_realtime.txt         # 실시간 Cron (레거시) ⚠️ 중복
├── data_sources.yaml            # 데이터 소스 설정
├── env.nas.sample.sh            # NAS 환경 변수 샘플
├── env.nas.sh                   # NAS 환경 변수 ⚠️ 실제 사용
├── env.pc.sh                    # PC 환경 변수
├── regime_params.yaml           # 레짐 파라미터
├── scanner.yaml                 # 스캐너 설정 ⚠️ 중복
├── scanner_config.yaml          # 스캐너 설정 ⚠️ 중복
├── strategies/                  # 전략 설정
├── strategy_params.json         # 전략 파라미터
├── universe.yaml                # 유니버스 설정
├── us_market_indicators.yaml    # 미국 시장 지표
└── web_index.yaml               # Web 인덱스
```

**총 파일 수**: 21개

---

## 🔍 발견된 문제

### 1. Crontab 파일 중복 (4개)

**파일**:
- `crontab.cloud.txt` - Oracle Cloud용 ✅
- `crontab.nas.txt` - NAS용 (기본) ⚠️
- `crontab.nas.fixed.txt` - NAS용 (수정본, 환경 변수 추가) ⚠️
- `crontab_realtime.txt` - 실시간 신호 (레거시) ❌

**문제점**:
- NAS Cron이 2개 (`.txt`, `.fixed.txt`)
- `crontab_realtime.txt`는 레거시 (사용 안 함)
- 어떤 파일이 최신인지 불명확

**제안**:
- `crontab.nas.fixed.txt` → `crontab.nas.txt` (최신본으로 교체)
- `crontab_realtime.txt` → 삭제 (레거시)
- 최종: `crontab.cloud.txt`, `crontab.nas.txt` (2개만 유지)

---

### 2. Scanner 설정 중복 (2개)

**파일**:
- `scanner.yaml` - 베스트에포트 스캐너 설정
- `scanner_config.yaml` - MAPS 전략 스캐너 설정

**차이점**:
- `scanner.yaml`: 단순 스캐너 (절대 변화율 기반)
- `scanner_config.yaml`: 전략 기반 스캐너 (이동평균 기반)

**문제점**:
- 두 파일의 용도가 다름
- 하지만 이름이 유사해서 혼란

**제안**:
- `scanner.yaml` → `scanner_simple.yaml` (명확한 이름)
- `scanner_config.yaml` → `scanner_strategy.yaml` (명확한 이름)
- 또는 하나로 통합 (사용 중인 것만 유지)

---

### 3. Config 파일 중복 (3개)

**파일**:
- `config.yaml` - 메인 설정 (전체)
- `config.nas.yaml` - NAS 전용 설정 (경량)
- `config.template.yaml` - 설정 템플릿

**문제점**:
- `config.yaml`과 `config.nas.yaml`의 관계 불명확
- 템플릿 파일이 별도로 존재

**제안**:
- `config.yaml` - 메인 설정 (유지)
- `config.nas.yaml` - NAS 전용 설정 (유지)
- `config.template.yaml` → `config.example.yaml` (명확한 이름)

---

### 4. 환경 변수 파일 (3개)

**파일**:
- `env.nas.sh` - NAS 환경 변수 (실제 사용) ⚠️ Git 추적 중
- `env.nas.sample.sh` - NAS 환경 변수 샘플 ✅
- `env.pc.sh` - PC 환경 변수 (거의 비어있음)

**문제점**:
- `env.nas.sh`가 Git에 추적되고 있음 (보안 위험)
- `env.pc.sh`는 거의 비어있음

**제안**:
- `env.nas.sh` → `.gitignore`에 추가
- `env.nas.sample.sh` → 유지 (샘플)
- `env.pc.sh` → `env.pc.sample.sh` (샘플로 변경)
- 실제 `env.nas.sh`, `env.pc.sh`는 로컬에만 존재

---

## 📋 정리 계획

### Phase 3.4: 설정 파일 통합

#### Step 1: Crontab 파일 정리

**삭제**:
- `crontab_realtime.txt` (레거시)

**교체**:
- `crontab.nas.fixed.txt` → `crontab.nas.txt` (최신본으로 교체)

**최종**:
- `crontab.cloud.txt` ✅
- `crontab.nas.txt` ✅

---

#### Step 2: Scanner 설정 정리

**옵션 A: 이름 변경** (권장)
- `scanner.yaml` → `scanner_simple.yaml`
- `scanner_config.yaml` → `scanner_strategy.yaml`

**옵션 B: 통합**
- 사용 중인 것만 유지
- 나머지는 삭제 또는 archive/

**선택**: 사용자 확인 필요

---

#### Step 3: Config 파일 정리

**이름 변경**:
- `config.template.yaml` → `config.example.yaml`

**유지**:
- `config.yaml` ✅
- `config.nas.yaml` ✅

---

#### Step 4: 환경 변수 파일 정리

**Git 추적 중지**:
```bash
git rm --cached config/env.nas.sh
echo "config/env.nas.sh" >> .gitignore
echo "config/env.pc.sh" >> .gitignore
```

**이름 변경**:
- `env.pc.sh` → `env.pc.sample.sh`

**최종**:
- `env.nas.sample.sh` ✅ (Git 추적)
- `env.pc.sample.sh` ✅ (Git 추적)
- `env.nas.sh` (로컬만, Git 무시)
- `env.pc.sh` (로컬만, Git 무시)

---

## 📊 정리 후 구조

```
config/
├── backtest_params.json         # 백테스트 파라미터
├── common.yaml                  # 공통 설정
├── config.yaml                  # 메인 설정
├── config.nas.yaml              # NAS 전용 설정
├── config.example.yaml          # 설정 예제 (이름 변경)
├── crontab.cloud.txt            # Oracle Cloud Cron
├── crontab.nas.txt              # NAS Cron (최신)
├── data_sources.yaml            # 데이터 소스 설정
├── env.nas.sample.sh            # NAS 환경 변수 샘플
├── env.pc.sample.sh             # PC 환경 변수 샘플 (이름 변경)
├── regime_params.yaml           # 레짐 파라미터
├── scanner_simple.yaml          # 단순 스캐너 (이름 변경)
├── scanner_strategy.yaml        # 전략 스캐너 (이름 변경)
├── strategies/                  # 전략 설정
├── strategy_params.json         # 전략 파라미터
├── universe.yaml                # 유니버스 설정
├── us_market_indicators.yaml    # 미국 시장 지표
└── web_index.yaml               # Web 인덱스
```

**파일 수**: 18개 (21개 → 18개, 14% 감소)

---

## 🎯 예상 효과

### 파일 수 감소
- **Before**: 21개
- **After**: 18개
- **감소율**: 14%

### 명확성 향상
- ✅ Crontab 파일 명확 (cloud, nas)
- ✅ Scanner 설정 명확 (simple, strategy)
- ✅ 환경 변수 보안 강화 (.gitignore)
- ✅ 예제 파일 명확 (.example, .sample)

---

## ⚠️ 주의사항

### 환경 변수 파일

**중요**: `env.nas.sh`, `env.pc.sh`는 실제 환경 변수를 포함하므로 Git에 추적하면 안 됩니다.

**현재 상태 확인 필요**:
```bash
git ls-files config/env.nas.sh
git ls-files config/env.pc.sh
```

**추적 중이면**:
```bash
git rm --cached config/env.nas.sh
git rm --cached config/env.pc.sh
echo "config/env.nas.sh" >> .gitignore
echo "config/env.pc.sh" >> .gitignore
git commit -m "Stop tracking environment files"
```

---

## 🚀 다음 단계

### 사용자 확인 필요

**질문 1**: Scanner 설정
- 옵션 A: 이름 변경 (`scanner_simple.yaml`, `scanner_strategy.yaml`)
- 옵션 B: 하나만 유지 (어떤 것을 사용 중인가?)

**질문 2**: 환경 변수
- `env.nas.sh`에 실제 환경 변수가 있는가?
- Git 추적 중지 필요한가?

**진행 방식**:
- 확인 후 Phase 3.4 진행
- 안전한 항목부터 정리
- Git commit으로 복원 가능

---

**다음**: 사용자 확인 후 Phase 3.4 진행
