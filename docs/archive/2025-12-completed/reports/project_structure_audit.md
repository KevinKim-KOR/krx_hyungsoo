# 프로젝트 구조 점검 보고서

**작성일**: 2025-11-08  
**목적**: Phase 2 완료 후 프로젝트 일관성 및 구조 점검  
**점검자**: Cascade AI

---

## 📋 점검 요약

### ✅ 양호한 부분
1. **기본 구조 유지**: `core/`, `nas/`, `pc/` 모듈 분리 원칙 준수
2. **문서화**: README.md, nas/README_NAS.md 등 기본 가이드 존재
3. **스크립트 조직화**: `scripts/linux/batch/`, `scripts/linux/jobs/` 구조 유지

### ⚠️ 개선 필요 부분
1. **scripts/phase2 폴더**: 테스트 스크립트와 운영 스크립트 혼재
2. **scripts/automation 폴더**: Week 4에서 새로 생성, 기존 구조와 중복
3. **scripts/nas 폴더**: 기존 NAS 스크립트와 새 automation 스크립트 분리
4. **문서 일관성**: 여러 NAS 배포 가이드 존재 (통합 필요)

---

## 🗂️ 현재 프로젝트 구조

### 1. 핵심 모듈 (✅ 양호)

```
krx_alertor_modular/
├── core/              # 공통 모듈 (NAS + PC)
│   ├── db.py
│   ├── fetchers.py
│   ├── providers/
│   ├── strategy/      # Week 3에서 추가
│   └── engine/        # Week 1에서 추가
│
├── nas/               # NAS 전용 (경량)
│   ├── app_nas.py
│   ├── scanner_nas.py
│   └── README_NAS.md
│
├── pc/                # PC 전용 (전체 기능)
│   ├── app_pc.py
│   ├── backtest.py
│   └── ml/
│
└── infra/             # 인프라 (데이터 로더 등)
    └── data/
```

**평가**: ✅ **원칙 준수** - 모듈 분리 원칙이 잘 지켜지고 있음

---

### 2. 스크립트 구조 (⚠️ 정리 필요)

#### 현재 상태:

```
scripts/
├── linux/             # 기존 NAS 운영 스크립트 (✅ 양호)
│   ├── batch/         # 27개 스크립트
│   └── jobs/          # 29개 스크립트
│
├── nas/               # NAS 알림 스크립트 (✅ 양호)
│   ├── daily_realtime_signals.sh
│   ├── rising_etf_alert.py
│   └── weekly_report.py
│
├── automation/        # Week 4 신규 (⚠️ 중복 가능성)
│   ├── daily_alert.sh
│   ├── weekly_alert.sh
│   ├── run_daily_report.py
│   └── run_weekly_report.py
│
└── phase2/            # Phase 2 백테스트 (⚠️ 테스트 전용?)
    ├── run_backtest_hybrid.py
    ├── run_backtest_defense.py
    └── prepare_data.py
```

#### 문제점:

1. **scripts/automation vs scripts/nas 중복**
   - `scripts/automation/daily_alert.sh` ≈ `scripts/nas/daily_realtime_signals.sh`
   - `scripts/automation/weekly_alert.sh` ≈ `scripts/nas/weekly_report.py`
   - 역할이 유사하지만 별도로 존재

2. **scripts/phase2 용도 불명확**
   - 백테스트 스크립트들이 모여 있음
   - 테스트용인지 운영용인지 불분명
   - `scripts/bt/`와 역할 중복 가능성

---

### 3. 문서 구조 (⚠️ 통합 필요)

#### NAS 배포 관련 문서:

```
docs/
├── NAS_DEPLOYMENT_GUIDE.md          # Week 4 신규 (최신)
├── PHASE3_NAS_DEPLOYMENT.md         # Phase 3 버전
├── NAS_SCHEDULER_COMMANDS.md        # 스케줄러 명령어
├── NAS_TROUBLESHOOTING.md           # 문제 해결
├── TELEGRAM_SETUP.md                # 텔레그램 설정
│
├── OLD/
│   ├── NAS_SETUP_GUIDE.md           # 구버전
│   ├── NAS_TEST_GUIDE.md            # 테스트 가이드
│   └── ACTION_PLAN_MODULE_SEPARATION.md  # 모듈 분리 계획
│
└── NEW/
    └── RUNBOOK.md                   # 운영 매뉴얼
```

#### 문제점:

- **NAS 배포 가이드가 4개 이상 존재**
- 어느 것이 최신이고 정확한지 불명확
- 사용자가 혼란스러울 수 있음

---

## 🔍 상세 분석

### 1. scripts/phase2 폴더 분석

**파일 목록**:
- `run_backtest_hybrid.py` - 하이브리드 전략 백테스트
- `run_backtest_defense.py` - 방어 시스템 백테스트
- `run_backtest_crash_detection.py` - 급락 감지 백테스트
- `run_backtest_volatility.py` - 변동성 관리 백테스트
- `prepare_data.py` - 데이터 준비
- `debug_regime.py` - 레짐 디버깅

**평가**:
- ✅ **테스트/개발 전용으로 판단됨**
- ⚠️ **운영 스크립트와 분리 필요**
- 💡 **제안**: `scripts/phase2/` → `scripts/tests/phase2/` 또는 `scripts/dev/phase2/`로 이동

---

### 2. scripts/automation vs scripts/nas 비교

| 항목 | scripts/automation | scripts/nas |
|------|-------------------|-------------|
| **생성 시기** | Week 4 (2025-11-08) | Phase 3 이전 |
| **목적** | Week 4 자동화 시스템 | 기존 NAS 알림 시스템 |
| **일일 리포트** | `daily_alert.sh` | `daily_realtime_signals.sh` |
| **주간 리포트** | `weekly_alert.sh` | `weekly_report.py` |
| **텔레그램** | `TelegramNotifier` 클래스 | 직접 API 호출 |
| **레짐 감지** | `RegimeMonitor` 클래스 | `regime_change_alert.py` |

**문제점**:
- 기능이 중복됨
- 어느 것을 사용해야 할지 불명확

**해결 방안**:
1. **Option A**: `scripts/automation`을 메인으로 사용, `scripts/nas`는 레거시로 표시
2. **Option B**: 두 시스템을 통합하여 하나로 정리
3. **Option C**: 역할을 명확히 구분 (automation=새 시스템, nas=기존 시스템)

---

### 3. 기존 가이드 문서 vs 새 가이드 비교

#### 기존 가이드 (ACTION_PLAN_MODULE_SEPARATION.md)

**핵심 원칙**:
```
1. core/ - 공통 모듈 (NAS + PC)
2. nas/ - NAS 전용 (경량, Python 3.8)
3. pc/ - PC 전용 (전체 기능)
4. scripts/linux/ - NAS 운영 스크립트
5. config/ - 설정 파일 (env.nas.sh, env.pc.sh)
```

#### Week 4 가이드 (NAS_DEPLOYMENT_GUIDE.md)

**새로운 구조**:
```
1. extensions/automation/ - 자동화 모듈
2. extensions/ui/ - UI 모듈
3. scripts/automation/ - 자동화 스크립트
4. .env - 환경 변수 (새로운 방식)
```

**차이점**:
- 기존: `config/env.nas.sh` → 새: `.env`
- 기존: `scripts/linux/` → 새: `scripts/automation/`
- 기존: `nas/app_nas.py` → 새: `extensions/automation/`

**평가**:
- ⚠️ **일관성 부족** - 두 가이드가 다른 구조를 제안
- 💡 **통합 필요** - 하나의 명확한 가이드로 정리

---

## 💡 권장 사항

### 1. 스크립트 구조 정리

#### 제안 A: 명확한 역할 분리

```
scripts/
├── linux/             # NAS 운영 (기존 유지)
│   ├── batch/         # 일반 배치 작업
│   └── jobs/          # Cron 작업
│
├── automation/        # Week 4 자동화 (신규, 메인)
│   ├── daily_alert.sh
│   ├── weekly_alert.sh
│   └── README.md      # "이것이 최신 시스템입니다" 명시
│
├── nas/               # 레거시 (보존, 참고용)
│   └── README_LEGACY.md  # "automation/ 사용 권장" 명시
│
└── dev/               # 개발/테스트 전용
    ├── phase2/        # Phase 2 백테스트 테스트
    └── tests/
```

#### 제안 B: 통합

```
scripts/
├── linux/             # NAS 운영 (통합)
│   ├── batch/
│   ├── jobs/
│   └── automation/    # Week 4 스크립트 이동
│
└── dev/               # 개발/테스트
    └── phase2/
```

**추천**: **제안 A** - 기존 시스템을 건드리지 않고 새 시스템을 명확히 구분

---

### 2. 문서 정리

#### 제안: 단일 마스터 가이드 생성

```
docs/
├── NAS_DEPLOYMENT_MASTER.md  # 최종 통합 가이드
│   ├── 1. 기본 설정 (기존 가이드 기반)
│   ├── 2. Week 4 자동화 시스템 (신규)
│   ├── 3. 텔레그램 설정
│   ├── 4. 스케줄러 설정
│   └── 5. 문제 해결
│
├── LEGACY/            # 구버전 보관
│   ├── NAS_DEPLOYMENT_GUIDE.md
│   ├── PHASE3_NAS_DEPLOYMENT.md
│   └── ...
│
└── QUICK_START.md     # 빠른 시작 가이드 (1페이지)
```

---

### 3. 환경 설정 통합

#### 현재:
- `config/env.nas.sh` (기존)
- `.env` (Week 4 신규)
- `config/config.yaml` (공통)

#### 제안:
```bash
# .env (메인)
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
DATA_DIR=...
LOG_DIR=...

# config/env.nas.sh (레거시, .env로 리다이렉트)
source .env
export TELEGRAM_BOT_TOKEN
export TELEGRAM_CHAT_ID
```

---

## 📊 우선순위별 작업 계획

### 🔴 High Priority (즉시)

1. **scripts/phase2 이동**
   ```bash
   mkdir -p scripts/dev
   mv scripts/phase2 scripts/dev/
   ```

2. **README 업데이트**
   - `scripts/automation/README.md` 생성
   - "이것이 Week 4 최신 시스템입니다" 명시

3. **scripts/nas에 LEGACY 표시**
   - `scripts/nas/README_LEGACY.md` 생성
   - "automation/ 사용 권장" 명시

### 🟡 Medium Priority (1주일 내)

4. **문서 통합**
   - `docs/NAS_DEPLOYMENT_MASTER.md` 생성
   - 기존 가이드들을 `docs/LEGACY/`로 이동

5. **환경 변수 통합**
   - `.env` 를 메인으로 사용
   - `config/env.nas.sh`는 `.env`를 source

### 🟢 Low Priority (필요 시)

6. **scripts/automation과 scripts/nas 통합**
   - 기능 중복 제거
   - 하나의 시스템으로 통합

---

## ✅ 즉시 적용 가능한 조치

### 1. scripts/phase2 이동

```bash
# PC에서 실행
cd "e:/AI Study/krx_alertor_modular"

# dev 폴더 생성
mkdir -p scripts/dev

# phase2 이동
git mv scripts/phase2 scripts/dev/

# 커밋
git add -A
git commit -m "refactor: scripts/phase2를 scripts/dev/로 이동 (테스트 전용)"
```

### 2. README 생성

**scripts/automation/README.md**:
```markdown
# Week 4 자동화 시스템

**상태**: ✅ 최신 (2025-11-08)  
**용도**: 운영 환경 (NAS)

## 이 폴더는?
Week 4에서 구현한 최신 자동화 시스템입니다.

## 사용 방법
`docs/NAS_DEPLOYMENT_GUIDE.md` 참조

## 기존 시스템과의 차이
- `scripts/nas/`: 레거시 (Phase 3 이전)
- `scripts/automation/`: 최신 (Week 4)

**권장**: `scripts/automation/` 사용
```

**scripts/nas/README_LEGACY.md**:
```markdown
# NAS 알림 시스템 (레거시)

**상태**: ⚠️ 레거시  
**최신 시스템**: `scripts/automation/`

이 폴더는 Phase 3 이전에 사용하던 시스템입니다.
새로운 배포는 `scripts/automation/`을 사용하세요.

## 마이그레이션
`docs/NAS_DEPLOYMENT_GUIDE.md` 참조
```

### 3. 프로젝트 루트 README 업데이트

`README.md`에 명확한 안내 추가:

```markdown
## 🚀 최신 업데이트 (2025-11-08)

### Week 4: 자동화 시스템 완성 ✅
- **위치**: `extensions/automation/`, `scripts/automation/`
- **가이드**: `docs/NAS_DEPLOYMENT_GUIDE.md`
- **상태**: 운영 준비 완료

### 폴더 구조
- `scripts/automation/` - ✅ 최신 자동화 시스템 (Week 4)
- `scripts/nas/` - ⚠️ 레거시 (Phase 3 이전)
- `scripts/linux/` - ✅ 기존 NAS 운영 스크립트 (유지)
- `scripts/dev/` - 🧪 개발/테스트 전용
```

---

## 📝 결론

### 현재 상태
- ✅ **핵심 모듈 구조**: 양호 (core/, nas/, pc/ 분리 원칙 준수)
- ⚠️ **스크립트 구조**: 정리 필요 (중복 및 용도 불명확)
- ⚠️ **문서**: 통합 필요 (여러 가이드 존재)

### 권장 조치
1. **즉시**: scripts/phase2 이동, README 생성
2. **1주일 내**: 문서 통합, 환경 변수 정리
3. **필요 시**: 스크립트 통합

### 다음 단계
1. 위 조치 사항 적용
2. NAS 배포 테스트
3. 실전 운영 시작

---

**작성자**: Cascade AI  
**검토 필요**: 사용자 확인 및 승인
