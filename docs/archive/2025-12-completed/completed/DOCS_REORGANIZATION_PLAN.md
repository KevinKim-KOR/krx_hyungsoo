# 문서 재구성 계획

**작성일**: 2025-11-08  
**목적**: docs 폴더 체계적 정리

---

## 📋 현재 문제점

1. ❌ 루트에 30개 이상의 파일 혼재
2. ❌ OLD, NEW, Friend 폴더의 용도 불명확
3. ❌ 가이드/진행/설계 문서 구분 없음
4. ❌ 중복 문서 존재 (NAS 가이드 3개 이상)

---

## 🎯 새로운 구조

```
docs/
├── guides/              # 📘 운영 가이드 (실전 사용)
│   ├── nas/
│   │   ├── deployment.md
│   │   ├── scheduler.md
│   │   ├── troubleshooting.md
│   │   └── telegram.md
│   ├── development.md
│   └── optuna.md
│
├── reports/             # 📊 완료 보고서 (Phase/Week)
│   ├── phase2/
│   │   ├── week1_jason_integration.md
│   │   ├── week2_defense_system.md
│   │   ├── week3_hybrid_strategy.md
│   │   ├── week4_automation_complete.md
│   │   └── phase2_complete_summary.md
│   ├── phase3_completion_report.md
│   └── project_structure_audit.md
│
├── plans/               # 📝 계획서 (미래 작업)
│   ├── phase5_oracle_cloud_plan.md
│   ├── phase6_advanced_dashboard_plan.md
│   ├── phase2_retest_plan.md
│   └── hybrid_strategy_plan.md
│
├── design/              # 🏗️ 설계 문서
│   ├── adapter_design.md
│   ├── defense_system_design.md
│   └── jason_code_analysis.md
│
├── progress/            # 📅 일일 진행 기록
│   ├── 2025-11-06.md
│   ├── 2025-11-07.md
│   └── 2025-11-08.md
│
├── archive/             # 🗄️ 구버전 (참고용)
│   ├── old_guides/
│   ├── old_progress/
│   └── migration_history/
│
├── reference/           # 📚 참고 자료
│   ├── friend_strategy/
│   ├── notification_comparison.md
│   └── development_rules.md
│
└── README.md            # 문서 인덱스
```

---

## 📁 파일 분류

### 1. guides/ (운영 가이드)
**목적**: 실전 사용 가이드

- `guides/nas/deployment.md` ← NAS_DEPLOYMENT_GUIDE.md (최신)
- `guides/nas/scheduler.md` ← NAS_SCHEDULER_COMMANDS.md
- `guides/nas/troubleshooting.md` ← NAS_TROUBLESHOOTING.md
- `guides/nas/telegram.md` ← TELEGRAM_SETUP.md
- `guides/development.md` ← NEW/RUNBOOK.md
- `guides/optuna.md` ← OPTUNA_GUIDE.md

### 2. reports/ (완료 보고서)
**목적**: Phase/Week 완료 기록

- `reports/phase2/week1_jason_integration.md` ← WEEK1_JASON_INTEGRATION.md
- `reports/phase2/week2_defense_system.md` ← WEEK2_DEFENSE_SYSTEM.md
- `reports/phase2/week3_hybrid_strategy.md` ← WEEK3_HYBRID_STRATEGY.md
- `reports/phase2/week4_automation_complete.md` ← WEEK4_AUTOMATION_COMPLETE.md
- `reports/phase2/phase2_complete_summary.md` ← PHASE2_COMPLETE_SUMMARY.md
- `reports/phase2/phase2_week3_summary.md` ← PHASE2_WEEK3_SUMMARY.md
- `reports/phase3_completion_report.md` ← PHASE3_COMPLETION_REPORT.md
- `reports/project_structure_audit.md` ← PROJECT_STRUCTURE_AUDIT.md
- `reports/project_structure_cleanup.md` ← PROJECT_STRUCTURE_CLEANUP_SUMMARY.md

### 3. plans/ (계획서)
**목적**: 미래 작업 계획

- `plans/phase5_oracle_cloud_plan.md` ← PHASE5_ORACLE_CLOUD_PLAN.md
- `plans/phase6_advanced_dashboard_plan.md` ← PHASE6_ADVANCED_DASHBOARD_PLAN.md
- `plans/phase2_retest_plan.md` ← PHASE2_RETEST_PLAN.md
- `plans/hybrid_strategy_plan.md` ← HYBRID_STRATEGY_PLAN.md
- `plans/week4_automation_plan.md` ← WEEK4_AUTOMATION_PLAN.md

### 4. design/ (설계 문서)
**목적**: 아키텍처 및 설계

- `design/adapter_design.md` ← adapter_design.md
- `design/defense_system_design.md` ← defense_system_design.md
- `design/jason_code_analysis.md` ← jason_code_analysis.md
- `design/architecture.md` ← NEW/ARCHITECTURE.md
- `design/strategy_spec.md` ← NEW/STRATEGY_SPEC.md
- `design/data_policy.md` ← NEW/DATA_POLICY.md

### 5. progress/ (일일 진행)
**목적**: 날짜별 작업 기록

- `progress/2025-11-06.md` ← PROGRESS_2025-11-06.md
- `progress/2025-11-07.md` ← PROGRESS_2025-11-07.md
- `progress/2025-11-08.md` ← PROGRESS_2025-11-08.md
- `progress/latest.md` ← NEW/PROGRESS.md

### 6. archive/ (구버전)
**목적**: 참고용 보관

- `archive/old_guides/` ← OLD/ 폴더 전체
- `archive/phase3_nas_deployment.md` ← PHASE3_NAS_DEPLOYMENT.md (구버전)
- `archive/session_resume.md` ← SESSION_RESUME.md

### 7. reference/ (참고 자료)
**목적**: 외부 참고 자료

- `reference/friend_strategy/` ← Friend/ 폴더 전체
- `reference/notification_comparison.md` ← NOTIFICATION_COMPARISON.md
- `reference/development_rules.md` ← Friend/development-rules.md

---

## 🚀 실행 계획

### Step 1: 폴더 생성
```bash
mkdir -p docs/guides/nas
mkdir -p docs/reports/phase2
mkdir -p docs/plans
mkdir -p docs/design
mkdir -p docs/progress
mkdir -p docs/archive/old_guides
mkdir -p docs/reference/friend_strategy
```

### Step 2: 파일 이동 (Git)
```bash
# guides/
git mv docs/NAS_DEPLOYMENT_GUIDE.md docs/guides/nas/deployment.md
git mv docs/NAS_SCHEDULER_COMMANDS.md docs/guides/nas/scheduler.md
git mv docs/NAS_TROUBLESHOOTING.md docs/guides/nas/troubleshooting.md
git mv docs/TELEGRAM_SETUP.md docs/guides/nas/telegram.md
git mv docs/NEW/RUNBOOK.md docs/guides/development.md
git mv docs/OPTUNA_GUIDE.md docs/guides/optuna.md

# reports/
git mv docs/WEEK1_JASON_INTEGRATION.md docs/reports/phase2/week1_jason_integration.md
git mv docs/WEEK2_DEFENSE_SYSTEM.md docs/reports/phase2/week2_defense_system.md
git mv docs/WEEK3_HYBRID_STRATEGY.md docs/reports/phase2/week3_hybrid_strategy.md
git mv docs/WEEK4_AUTOMATION_COMPLETE.md docs/reports/phase2/week4_automation_complete.md
git mv docs/PHASE2_COMPLETE_SUMMARY.md docs/reports/phase2/phase2_complete_summary.md
git mv docs/PHASE2_WEEK3_SUMMARY.md docs/reports/phase2/phase2_week3_summary.md
git mv docs/PHASE3_COMPLETION_REPORT.md docs/reports/phase3_completion_report.md
git mv docs/PROJECT_STRUCTURE_AUDIT.md docs/reports/project_structure_audit.md
git mv docs/PROJECT_STRUCTURE_CLEANUP_SUMMARY.md docs/reports/project_structure_cleanup.md

# plans/
git mv docs/PHASE5_ORACLE_CLOUD_PLAN.md docs/plans/phase5_oracle_cloud_plan.md
git mv docs/PHASE6_ADVANCED_DASHBOARD_PLAN.md docs/plans/phase6_advanced_dashboard_plan.md
git mv docs/PHASE2_RETEST_PLAN.md docs/plans/phase2_retest_plan.md
git mv docs/HYBRID_STRATEGY_PLAN.md docs/plans/hybrid_strategy_plan.md
git mv docs/WEEK4_AUTOMATION_PLAN.md docs/plans/week4_automation_plan.md

# design/
git mv docs/adapter_design.md docs/design/adapter_design.md
git mv docs/defense_system_design.md docs/design/defense_system_design.md
git mv docs/jason_code_analysis.md docs/design/jason_code_analysis.md
git mv docs/NEW/ARCHITECTURE.md docs/design/architecture.md
git mv docs/NEW/STRATEGY_SPEC.md docs/design/strategy_spec.md
git mv docs/NEW/DATA_POLICY.md docs/design/data_policy.md

# progress/
git mv docs/PROGRESS_2025-11-06.md docs/progress/2025-11-06.md
git mv docs/PROGRESS_2025-11-07.md docs/progress/2025-11-07.md
git mv docs/PROGRESS_2025-11-08.md docs/progress/2025-11-08.md
git mv docs/NEW/PROGRESS.md docs/progress/latest.md

# archive/
git mv docs/OLD docs/archive/old_guides
git mv docs/PHASE3_NAS_DEPLOYMENT.md docs/archive/phase3_nas_deployment.md
git mv docs/SESSION_RESUME.md docs/archive/session_resume.md

# reference/
git mv docs/Friend docs/reference/friend_strategy
git mv docs/NOTIFICATION_COMPARISON.md docs/reference/notification_comparison.md
git mv docs/SCHEDULER_TIMING_GUIDE.md docs/reference/scheduler_timing_guide.md

# NEW 폴더 정리
git mv docs/NEW/README.md docs/archive/new_readme.md
rmdir docs/NEW
```

### Step 3: README 생성
```bash
# docs/README.md 생성
```

### Step 4: 커밋
```bash
git commit -m "docs: 문서 구조 재정리

- 업무별 폴더 구조로 재구성
- guides/ (운영 가이드)
- reports/ (완료 보고서)
- plans/ (계획서)
- design/ (설계 문서)
- progress/ (일일 진행)
- archive/ (구버전)
- reference/ (참고 자료)
"
```

---

## ✅ 기대 효과

1. **명확한 분류**: 가이드/보고서/계획서 구분
2. **쉬운 탐색**: 업무별 폴더로 빠른 검색
3. **유지보수 용이**: 새 문서 추가 시 위치 명확
4. **구버전 관리**: archive/로 깔끔하게 보관

---

**작성자**: Cascade AI  
**실행**: 사용자 승인 후 진행
