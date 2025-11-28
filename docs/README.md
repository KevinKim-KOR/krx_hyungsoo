# 📚 문서 인덱스

**최종 업데이트**: 2025-11-27  
**버전**: 2.0 (Phase 2 문서 정리 완료)

---

## 📋 목차

1. [사용 가이드](#사용-가이드)
2. [배포 가이드](#배포-가이드)
3. [개발 문서](#개발-문서)
4. [설계 문서](#설계-문서)
5. [완료된 Phase](#완료된-phase)

---

## 사용 가이드

### 📖 guides/

**알림 시스템**:
- [`alert-system.md`](guides/alert-system.md) - 텔레그램 알림 설정 및 사용법
  - 장중 알림 (새로운 투자 기회)
  - 장시작 알림 (일일 시장 현황)
  - EOD 알림 (매매 신호)

**백테스트**:
- [`backtest.md`](guides/backtest.md) - 백테스트 실행 가이드
  - 전략 테스트
  - 성과 분석
  - 파라미터 최적화

**레짐 모니터링**:
- [`regime-monitoring.md`](guides/regime-monitoring.md) - 시장 레짐 감지 및 모니터링
  - 레짐 감지 원리
  - 실시간 모니터링
  - 알림 설정

**포트폴리오 관리**:
- [`portfolio-manager.md`](guides/portfolio-manager.md) - 포트폴리오 관리 UI
  - 보유 종목 관리
  - 매매 신호
  - 성과 분석

---

## 배포 가이드

### 🚀 deployment/

**Oracle Cloud**:
- [`oracle-cloud.md`](deployment/oracle-cloud.md) - Oracle Cloud 배포 가이드
  - VM 인스턴스 생성
  - 환경 구축
  - Cron 설정
  - 문제 해결

**NAS**:
- [`nas.md`](deployment/nas.md) - Synology NAS 배포 가이드
  - 경량 설치 (yfinance 없이)
  - Python 3.8 호환
  - Cron 설정
  - 문제 해결

**문제 해결**:
- [`troubleshooting.md`](deployment/troubleshooting.md) - 통합 문제 해결 가이드
  - Git 관련
  - 텔레그램 알림
  - Python 환경
  - 데이터 수집
  - 성능 문제

---

## 개발 문서

### 💻 development/

**아키텍처**:
- `architecture.md` - 시스템 아키텍처 (예정)
- `api.md` - API 문서 (예정)

**테스트**:
- `testing.md` - 테스트 가이드 (예정)

---

## 설계 문서

### 🎨 design/

**아키텍처**:
- [`architecture.md`](design/architecture.md) - 전체 시스템 아키텍처
- [`adapter_design.md`](design/adapter_design.md) - 어댑터 패턴 설계
- [`data_policy.md`](design/data_policy.md) - 데이터 정책

**분석**:
- [`jason_code_analysis.md`](design/jason_code_analysis.md) - Jason 코드 분석

---

## 완료된 Phase

### ✅ completed/

**Phase 완료 보고서**:
- `PHASE2_COMPLETE_SUMMARY.md` - Phase 2 완료 (백테스트 시스템)
- `PHASE3_COMPLETE.md` - Phase 3 완료 (최적화)
- `PHASE4_COMPLETE.md` - Phase 4 완료 (자동화)
- `PHASE5_COMPLETE.md` - Phase 5 완료 (UI)

**Week 완료 보고서**:
- `WEEK3_HYBRID_STRATEGY.md` - Week 3 하이브리드 전략
- `WEEK4_AUTOMATION_PLAN.md` - Week 4 자동화 계획

**계획 문서**:
- `MASTER_PLAN_2025.md` - 2025 마스터 플랜
- `PORTFOLIO_INTEGRATION_PLAN.md` - 포트폴리오 통합 계획
- `DOCS_REORGANIZATION_PLAN.md` - 문서 재구성 계획

---

## 📂 디렉토리 구조

```
docs/
├── README.md                          # 이 파일 (문서 인덱스)
│
├── guides/                            # 사용 가이드
│   ├── alert-system.md                # 알림 시스템
│   ├── backtest.md                    # 백테스트
│   ├── regime-monitoring.md           # 레짐 모니터링
│   └── portfolio-manager.md           # 포트폴리오 관리
│
├── deployment/                        # 배포 가이드
│   ├── oracle-cloud.md                # Oracle Cloud
│   ├── nas.md                         # NAS
│   └── troubleshooting.md             # 문제 해결
│
├── development/                       # 개발 문서
│   ├── architecture.md                # 아키텍처 (예정)
│   ├── api.md                         # API 문서 (예정)
│   └── testing.md                     # 테스트 (예정)
│
├── design/                            # 설계 문서
│   ├── architecture.md                # 시스템 아키텍처
│   ├── adapter_design.md              # 어댑터 패턴
│   ├── data_policy.md                 # 데이터 정책
│   └── jason_code_analysis.md         # Jason 코드 분석
│
├── completed/                         # 완료된 Phase 문서
│   ├── PHASE*.md                      # Phase 완료 보고서
│   ├── WEEK*.md                       # Week 완료 보고서
│   └── *_PLAN.md                      # 계획 문서
│
├── CODE_CLEANUP_*.md                  # 코드 정리 문서
├── PHASE1_CLEANUP_COMPLETE.md         # Phase 1 완료
├── GAP_ANALYSIS.md                    # Gap 분석
├── PORT_ARCHITECTURE.md               # 포트 아키텍처
└── US_MARKET_INDICATOR_IMPROVEMENT.md # 미국 시장 지표 개선
```

---

## 🚀 빠른 시작

### 1. 처음 시작하는 경우

**순서**:
1. [`GAP_ANALYSIS.md`](GAP_ANALYSIS.md) - 전체 계획 파악
2. [`PORT_ARCHITECTURE.md`](PORT_ARCHITECTURE.md) - 아키텍처 이해
3. [`guides/backtest.md`](guides/backtest.md) - 백테스트 실행

### 2. NAS 배포하는 경우

**순서**:
1. [`deployment/nas.md`](deployment/nas.md) - NAS 배포 가이드
2. [`guides/regime-monitoring.md`](guides/regime-monitoring.md) - 레짐 모니터링
3. [`guides/alert-system.md`](guides/alert-system.md) - 알림 설정

### 3. Oracle Cloud 배포하는 경우

**순서**:
1. [`deployment/oracle-cloud.md`](deployment/oracle-cloud.md) - Oracle Cloud 배포
2. [`deployment/troubleshooting.md`](deployment/troubleshooting.md) - 문제 해결
3. [`guides/alert-system.md`](guides/alert-system.md) - 알림 설정

---

## 🔍 키워드별 문서 찾기

### 알림 시스템
- [`guides/alert-system.md`](guides/alert-system.md) - 전체 가이드
- [`deployment/troubleshooting.md`](deployment/troubleshooting.md#텔레그램-알림) - 문제 해결

### 배포
- [`deployment/oracle-cloud.md`](deployment/oracle-cloud.md) - Oracle Cloud
- [`deployment/nas.md`](deployment/nas.md) - NAS
- [`deployment/troubleshooting.md`](deployment/troubleshooting.md) - 문제 해결

### 백테스트
- [`guides/backtest.md`](guides/backtest.md) - 백테스트 가이드
- [`completed/PHASE2_COMPLETE_SUMMARY.md`](completed/PHASE2_COMPLETE_SUMMARY.md) - Phase 2 완료

### 레짐 감지
- [`guides/regime-monitoring.md`](guides/regime-monitoring.md) - 레짐 모니터링
- [`US_MARKET_INDICATOR_IMPROVEMENT.md`](US_MARKET_INDICATOR_IMPROVEMENT.md) - 미국 시장 지표

### 포트폴리오
- [`guides/portfolio-manager.md`](guides/portfolio-manager.md) - 포트폴리오 관리
- [`completed/PORTFOLIO_INTEGRATION_PLAN.md`](completed/PORTFOLIO_INTEGRATION_PLAN.md) - 통합 계획

---

## 📝 문서 작성 규칙

1. **제목**: 명확하고 간결하게 (kebab-case)
2. **날짜**: 최종 업데이트 날짜 명시
3. **상태**: ✅ 완료, ⏳ 진행 중, ❌ 미완료
4. **이모지**: 가독성 향상 (적절히 사용)
5. **코드 블록**: 실행 가능한 명령어 제공
6. **링크**: 관련 문서 상호 참조

---

## 🎯 현재 상태 (2025-11-27)

### Phase 2 완료 ✅
- ✅ 중복 문서 통합 (11개 → 3개)
- ✅ 문서 디렉토리 재구성
- ✅ README 업데이트
- ✅ 문제 해결 가이드 추가

### 문서 절감 효과
- **ALERT_SYSTEM**: 3개 → 1개
- **ORACLE_CLOUD**: 4개 → 1개
- **NAS**: 4개 → 1개
- **총 절감**: 11개 → 3개 (73% 감소)

### 다음 작업
- ⏳ Phase 3: 구조 개선
- ⏳ Phase 4: 코드 품질

---

## 📞 문의

**문서 관련 문의**:
- GitHub Issues에 등록
- 로그 파일 첨부 (`logs/`)

**참고**:
- [프로젝트 README](../README.md)
- [CHANGELOG](../CHANGELOG.md)
