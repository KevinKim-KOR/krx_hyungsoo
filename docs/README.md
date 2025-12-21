# 📚 KRX Alertor Modular - 문서 인덱스

**최종 업데이트**: 2025-12-21  
**버전**: 3.2 (Phase 2.1 튜닝 엔진 강화)

---

## 🤖 AI 협업 필독

> **AI와 협업 시 반드시 먼저 읽어주세요**

### [📦 AI Context Pack](AI_CONTEXT_PACK.md)

튜닝 시스템의 전체 컨텍스트를 담은 문서입니다:
- ① 목적 (Purpose)
- ② 입력 (Input)
- ③ 처리 로직 (Logic Flow)
- ④ 출력 (Output)
- ⑤ 제약사항 / 규칙 (Constraints & Rules)

**AI 협업 권장 방식**:
1. Plan 수립 → 다른 AI (ChatGPT 등)에게 검토 요청
2. Plan 보완 → Cascade가 세부 사항 추가
3. 실행 → Cascade가 코드 수정
4. 검증 → 사용자가 UI에서 End-to-End 테스트

---

## 📋 목차

1. [빠른 시작](#-빠른-시작)
2. [사용 가이드](#-사용-가이드)
3. [배포 가이드](#-배포-가이드)
4. [설계 문서](#-설계-문서)
5. [참조 문서](#-참조-문서)
6. [완료된 Phase](#-완료된-phase)
7. [아카이브](#-아카이브)

---

## 🚀 빠른 시작

### 처음 시작하는 경우
1. [프로젝트 README](../README.md) - 전체 개요
2. [`design/architecture.md`](design/architecture.md) - 시스템 아키텍처
3. [`guides/backtest.md`](guides/backtest.md) - 백테스트 실행

### NAS 배포하는 경우
1. [`deployment/nas.md`](deployment/nas.md) - NAS 배포 가이드
2. [`guides/nas/`](guides/nas/) - NAS 상세 가이드
3. [`guides/alert-system.md`](guides/alert-system.md) - 알림 설정

### Oracle Cloud 배포하는 경우
1. [`deployment/oracle-cloud.md`](deployment/oracle-cloud.md) - Oracle Cloud 배포
2. [`deployment/troubleshooting.md`](deployment/troubleshooting.md) - 문제 해결

---

## 📖 사용 가이드

### guides/

| 문서 | 설명 |
|------|------|
| [`alert-system.md`](guides/alert-system.md) | 텔레그램 알림 설정 (장중/장시작/EOD) |
| [`backtest.md`](guides/backtest.md) | 백테스트 실행 가이드 |
| [`regime-monitoring.md`](guides/regime-monitoring.md) | 시장 레짐 감지 및 모니터링 |
| [`portfolio-manager.md`](guides/portfolio-manager.md) | 포트폴리오 관리 UI |
| [`optuna.md`](guides/optuna.md) | Optuna 최적화 가이드 |
| [`development.md`](guides/development.md) | 개발 환경 설정 |

### guides/nas/ (NAS 전용)

| 문서 | 설명 |
|------|------|
| [`deployment.md`](guides/nas/deployment.md) | NAS 배포 상세 |
| [`scheduler.md`](guides/nas/scheduler.md) | Cron 스케줄러 설정 |
| [`telegram.md`](guides/nas/telegram.md) | 텔레그램 봇 설정 |
| [`troubleshooting.md`](guides/nas/troubleshooting.md) | NAS 문제 해결 |

---

## 🚀 배포 가이드

### deployment/

| 문서 | 설명 |
|------|------|
| [`oracle-cloud.md`](deployment/oracle-cloud.md) | Oracle Cloud VM 배포 |
| [`nas.md`](deployment/nas.md) | Synology NAS 배포 |
| [`troubleshooting.md`](deployment/troubleshooting.md) | 통합 문제 해결 |

---

## 🎨 설계 문서

### design/

| 문서 | 설명 |
|------|------|
| [`architecture.md`](design/architecture.md) | 시스템 아키텍처 (Clean Architecture) |
| [`adapter_design.md`](design/adapter_design.md) | Jason 어댑터 패턴 설계 |
| [`data_policy.md`](design/data_policy.md) | 데이터 정책 및 캐시 |
| [`defense_system_design.md`](design/defense_system_design.md) | 방어 시스템 설계 |
| [`strategy_spec.md`](design/strategy_spec.md) | 전략 명세 |
| [`jason_code_analysis.md`](design/jason_code_analysis.md) | Jason 코드 분석 |

---

## 📚 참조 문서

### reference/

| 문서 | 설명 |
|------|------|
| [`ACTIVE_SCRIPTS.md`](reference/ACTIVE_SCRIPTS.md) | NAS에서 사용 중인 스크립트 목록 |
| [`AI_PROMPT_FEATURE.md`](reference/AI_PROMPT_FEATURE.md) | AI 프롬프트 기능 |
| [`BACKTEST_AI_PROMPT.md`](reference/BACKTEST_AI_PROMPT.md) | 백테스트 AI 분석 |
| [`notification_comparison.md`](reference/notification_comparison.md) | 알림 비교 |
| [`scheduler_timing_guide.md`](reference/scheduler_timing_guide.md) | 스케줄러 타이밍 |

---

## ✅ 완료된 Phase

### completed/

**Phase 완료 보고서**:
| 문서 | 설명 |
|------|------|
| [`PHASE3_COMPLETE.md`](completed/PHASE3_COMPLETE.md) | Phase 3 완료 (최적화) |
| [`PHASE4_COMPLETE.md`](completed/PHASE4_COMPLETE.md) | Phase 4 완료 (대시보드) |
| [`PHASE4.5_COMPLETE.md`](completed/PHASE4.5_COMPLETE.md) | Phase 4.5 완료 (FastAPI) |
| [`PHASE5_COMPLETE.md`](completed/PHASE5_COMPLETE.md) | Phase 5 완료 (NAS-Oracle 동기화) |
| [`PHASE5-1_COMPLETE.md`](completed/PHASE5-1_COMPLETE.md) | Phase 5-1 완료 |

**Phase 2 상세** (`completed/phase2-hybrid/`):
| 문서 | 설명 |
|------|------|
| [`phase2_complete_summary.md`](completed/phase2-hybrid/phase2_complete_summary.md) | Phase 2 완료 요약 |
| [`week1_jason_integration.md`](completed/phase2-hybrid/week1_jason_integration.md) | Week 1: Jason 통합 |
| [`week2_defense_system.md`](completed/phase2-hybrid/week2_defense_system.md) | Week 2: 방어 시스템 |
| [`week3_hybrid_strategy.md`](completed/phase2-hybrid/week3_hybrid_strategy.md) | Week 3: 하이브리드 전략 |
| [`week4_automation_complete.md`](completed/phase2-hybrid/week4_automation_complete.md) | Week 4: 자동화 |

**계획 문서**:
| 문서 | 설명 |
|------|------|
| [`MASTER_PLAN_2025.md`](completed/MASTER_PLAN_2025.md) | 2025 마스터 플랜 |
| [`WEEK4_AUTOMATION_PLAN.md`](completed/WEEK4_AUTOMATION_PLAN.md) | Week 4 자동화 계획 |
| [`PORTFOLIO_INTEGRATION_PLAN.md`](completed/PORTFOLIO_INTEGRATION_PLAN.md) | 포트폴리오 통합 계획 |

---

## 📦 아카이브

### archive/2025-11/
과거 작업 문서들이 보관되어 있습니다.
- 일일 진행 기록 (2025-11-06 ~ 08)
- 분석 문서 (GAP_ANALYSIS, PORT_ARCHITECTURE 등)
- 정리 계획 문서

### active/backtest-enhancement/
현재 진행 중인 백테스트 개선 작업:
- [`CRITICAL_REVIEW.md`](active/backtest-enhancement/CRITICAL_REVIEW.md) - 비판적 검토
- [`SUMMARY.md`](active/backtest-enhancement/SUMMARY.md) - 요약

---

## 📂 전체 디렉토리 구조

```
docs/
├── README.md                    # 이 파일 (문서 인덱스)
│
├── guides/                      # 📖 사용 가이드
│   ├── alert-system.md          # 알림 시스템
│   ├── backtest.md              # 백테스트
│   ├── regime-monitoring.md     # 레짐 모니터링
│   ├── portfolio-manager.md     # 포트폴리오 관리
│   ├── optuna.md                # Optuna 최적화
│   ├── development.md           # 개발 환경
│   └── nas/                     # NAS 전용 가이드
│       ├── deployment.md
│       ├── scheduler.md
│       ├── telegram.md
│       └── troubleshooting.md
│
├── deployment/                  # 🚀 배포 가이드
│   ├── oracle-cloud.md
│   ├── nas.md
│   └── troubleshooting.md
│
├── design/                      # 🎨 설계 문서
│   ├── architecture.md
│   ├── adapter_design.md
│   ├── data_policy.md
│   ├── defense_system_design.md
│   ├── strategy_spec.md
│   └── jason_code_analysis.md
│
├── reference/                   # 📚 참조 문서
│   ├── ACTIVE_SCRIPTS.md
│   ├── AI_PROMPT_FEATURE.md
│   └── ...
│
├── completed/                   # ✅ 완료된 Phase
│   ├── PHASE*.md
│   ├── phase2-hybrid/
│   ├── phase3-intraday/
│   ├── phase4-dashboard/
│   └── phase5-nas-sync/
│
├── active/                      # 🔄 진행 중
│   └── backtest-enhancement/
│
├── archive/                     # 📦 아카이브
│   └── 2025-11/
│
├── plans/                       # 📋 계획 문서
├── progress/                    # 📊 진행 기록
└── reports/                     # 📈 보고서
```

---

## 🎯 현재 상태 (2025-12-21)

### 완료된 기능
- ✅ **Phase 2**: 하이브리드 전략 (CAGR 27%, Sharpe 1.51)
- ✅ **Phase 3**: 장중 알림 개선
- ✅ **Phase 4**: React 대시보드 + FastAPI 백엔드
- ✅ **Phase 5**: NAS-Oracle 동기화
- ✅ **캐시 업데이트 UI**: 버튼으로 ETF 데이터 갱신
- ✅ **튜닝 시스템**: Optuna 기반 파라미터 최적화
- ✅ **Phase 2.0**: Real Data Gate2 & Force-Gate2 옵션
- ✅ **Phase 2.1**: 멀티룩백 증거 강화 & Real Data Gate0 (Preflight)

### 튜닝 엔진 최종 성과 (Mock 모드, 2025-12-21)
```
Gate1: candidates=7, selected_top_n=3, dedup_removed=0
Gate2: stability=2.68, win_rate=100% (6 windows)
Replay: ✅ PASS (tol=1e-6)

멀티룩백 증거:
  [3M]  lookback_start=2024-03-30
  [6M]  lookback_start=2023-12-30
  [12M] lookback_start=2023-06-30
```

### 운영 환경
- **NAS**: Synology DS220j (Python 3.8)
- **PC**: Windows (Python 3.10+)
- **Cloud**: Oracle Cloud (선택적)

### 주요 스크립트
- `scripts/nas/intraday_alert.py` - 장중 알림
- `scripts/nas/market_open_alert.py` - 장시작 알림
- `scripts/sync/sync_to_oracle.sh` - Oracle 동기화

---

## 📝 문서 작성 규칙

1. **파일명**: kebab-case (예: `alert-system.md`)
2. **날짜**: 최종 업데이트 날짜 명시
3. **상태**: ✅ 완료, ⏳ 진행 중, ❌ 미완료
4. **코드 블록**: 복사-붙여넣기 가능한 명령어
5. **링크**: 상대 경로 사용

---

## 📞 문의

- **GitHub Issues**: 버그 리포트, 기능 요청
- **로그 파일**: `logs/` 디렉토리 첨부

**참고**:
- [프로젝트 README](../README.md)
- [CHANGELOG](../CHANGELOG.md)
