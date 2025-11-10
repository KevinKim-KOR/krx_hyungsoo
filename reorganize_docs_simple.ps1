# 문서 재구성 스크립트 (단순 버전)
# 작성일: 2025-11-08

Write-Host "📁 문서 재구성 시작..." -ForegroundColor Green

# Step 1: 폴더 생성
Write-Host "`n1️⃣ 폴더 생성 중..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path "docs/guides/nas" | Out-Null
New-Item -ItemType Directory -Force -Path "docs/reports/phase2" | Out-Null
New-Item -ItemType Directory -Force -Path "docs/plans" | Out-Null
New-Item -ItemType Directory -Force -Path "docs/design" | Out-Null
New-Item -ItemType Directory -Force -Path "docs/progress" | Out-Null
New-Item -ItemType Directory -Force -Path "docs/archive/old_guides" | Out-Null
New-Item -ItemType Directory -Force -Path "docs/reference/friend_strategy" | Out-Null
Write-Host "✅ 폴더 생성 완료" -ForegroundColor Green

# Step 2: 파일 이동 (Git)
Write-Host "`n2️⃣ 파일 이동 중..." -ForegroundColor Yellow

# guides/
Write-Host "  📘 guides/ 이동 중..." -ForegroundColor Cyan
git mv docs/NAS_DEPLOYMENT_GUIDE.md docs/guides/nas/deployment.md
git mv docs/NAS_SCHEDULER_COMMANDS.md docs/guides/nas/scheduler.md
git mv docs/NAS_TROUBLESHOOTING.md docs/guides/nas/troubleshooting.md
git mv docs/TELEGRAM_SETUP.md docs/guides/nas/telegram.md
git mv docs/NEW/RUNBOOK.md docs/guides/development.md
git mv docs/OPTUNA_GUIDE.md docs/guides/optuna.md

# reports/
Write-Host "  📊 reports/ 이동 중..." -ForegroundColor Cyan
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
Write-Host "  📝 plans/ 이동 중..." -ForegroundColor Cyan
git mv docs/PHASE5_ORACLE_CLOUD_PLAN.md docs/plans/phase5_oracle_cloud_plan.md
git mv docs/PHASE6_ADVANCED_DASHBOARD_PLAN.md docs/plans/phase6_advanced_dashboard_plan.md
git mv docs/PHASE2_RETEST_PLAN.md docs/plans/phase2_retest_plan.md
git mv docs/HYBRID_STRATEGY_PLAN.md docs/plans/hybrid_strategy_plan.md
git mv docs/WEEK4_AUTOMATION_PLAN.md docs/plans/week4_automation_plan.md

# design/
Write-Host "  🏗️ design/ 이동 중..." -ForegroundColor Cyan
git mv docs/adapter_design.md docs/design/adapter_design.md
git mv docs/defense_system_design.md docs/design/defense_system_design.md
git mv docs/jason_code_analysis.md docs/design/jason_code_analysis.md
git mv docs/NEW/ARCHITECTURE.md docs/design/architecture.md
git mv docs/NEW/STRATEGY_SPEC.md docs/design/strategy_spec.md
git mv docs/NEW/DATA_POLICY.md docs/design/data_policy.md

# progress/
Write-Host "  📅 progress/ 이동 중..." -ForegroundColor Cyan
git mv docs/PROGRESS_2025-11-06.md docs/progress/2025-11-06.md
git mv docs/PROGRESS_2025-11-07.md docs/progress/2025-11-07.md
git mv docs/PROGRESS_2025-11-08.md docs/progress/2025-11-08.md
git mv docs/NEW/PROGRESS.md docs/progress/latest.md

# archive/
Write-Host "  🗄️ archive/ 이동 중..." -ForegroundColor Cyan
git mv docs/OLD docs/archive/old_guides
git mv docs/PHASE3_NAS_DEPLOYMENT.md docs/archive/phase3_nas_deployment.md
git mv docs/SESSION_RESUME.md docs/archive/session_resume.md

# reference/
Write-Host "  📚 reference/ 이동 중..." -ForegroundColor Cyan
git mv docs/Friend docs/reference/friend_strategy
git mv docs/NOTIFICATION_COMPARISON.md docs/reference/notification_comparison.md
git mv docs/SCHEDULER_TIMING_GUIDE.md docs/reference/scheduler_timing_guide.md

# NEW 폴더 정리
Write-Host "  🧹 NEW 폴더 정리 중..." -ForegroundColor Cyan
git mv docs/NEW/README.md docs/archive/new_readme.md
Remove-Item -Path "docs/NEW" -Recurse -Force -ErrorAction SilentlyContinue

Write-Host "✅ 파일 이동 완료" -ForegroundColor Green

Write-Host "`n✨ 문서 재구성 완료!" -ForegroundColor Green
Write-Host "`n다음 단계:" -ForegroundColor Yellow
Write-Host "  1. git commit -m docs: 문서 구조 재정리" -ForegroundColor White
Write-Host "  2. git push origin main" -ForegroundColor White
