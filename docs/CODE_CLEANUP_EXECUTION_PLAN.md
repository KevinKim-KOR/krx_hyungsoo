# 코드 정리 실행 계획 및 테스트

**작성일**: 2025-11-26  
**방식**: 단계별 진행 + 테스트 검증  
**예상 시간**: 3시간

---

## 🎯 Phase 1: 안전한 삭제 (30분)

### 1.1 Deprecated & Legacy 삭제

#### 삭제 대상
```
scripts/_deprecated_2025-11-13/
├── daily_realtime_signals.sh
├── run_weekly_report.py
├── weekly_alert.sh
└── weekly_report.py

scripts/legacy/2025-10-05/
└── (10개 항목)
```

#### 테스트 시나리오 1: 의존성 확인
```bash
# 1. 삭제 전: 다른 파일에서 참조하는지 확인
grep -r "_deprecated_2025-11-13" --include="*.py" --include="*.sh" --include="*.md"
grep -r "legacy/2025-10-05" --include="*.py" --include="*.sh" --include="*.md"

# 2. Import 확인
grep -r "from scripts._deprecated" --include="*.py"
grep -r "from scripts.legacy" --include="*.py"

# 예상 결과: 참조 없음 (0건)
```

#### 테스트 시나리오 2: 기능 테스트
```bash
# 삭제 후 주요 스크립트 실행 확인
python scripts/nas/daily_regime_check.py --help
python -m core.strategy.us_market_monitor

# 예상 결과: 정상 실행
```

#### 실행 명령
```bash
# Git으로 삭제 (이력 유지)
git rm -r scripts/_deprecated_2025-11-13/
git rm -r scripts/legacy/2025-10-05/
git commit -m "Phase 1.1: Deprecated & Legacy 삭제"
```

---

### 1.2 빈 디렉토리 삭제

#### 삭제 대상
```
pending/
logs/
.locks/
.state/
```

#### 테스트 시나리오 3: 디렉토리 사용 확인
```bash
# 1. 실제로 비어있는지 확인
ls -la pending/
ls -la logs/
ls -la .locks/
ls -la .state/

# 2. 코드에서 참조하는지 확인
grep -r "pending/" --include="*.py" --include="*.sh"
grep -r "logs/" --include="*.py" --include="*.sh" | grep -v ".gitignore"
grep -r ".locks/" --include="*.py" --include="*.sh"
grep -r ".state/" --include="*.py" --include="*.sh"

# 3. .gitignore 확인
cat .gitignore | grep -E "logs|locks|state"

# 예상 결과: 
# - pending/: 참조 없음
# - logs/, .locks/, .state/: .gitignore에 있음
```

#### 테스트 시나리오 4: 런타임 생성 확인
```bash
# 삭제 후 스크립트 실행 시 자동 생성되는지 확인
rm -rf logs/ .locks/ .state/
python scripts/nas/daily_regime_check.py --dry-run

# 예상 결과: logs/ 자동 생성됨
```

#### 실행 명령
```bash
# Git에서 추적 중지
git rm -r pending/
git rm -r logs/ --cached  # 파일은 유지, Git 추적만 중지
git rm -r .locks/ --cached
git rm -r .state/ --cached

# .gitignore 확인 및 추가 (이미 있으면 skip)
echo "logs/" >> .gitignore
echo ".locks/" >> .gitignore
echo ".state/" >> .gitignore

git commit -m "Phase 1.2: 빈 디렉토리 및 런타임 디렉토리 정리"
```

---

### 1.3 Archive 디렉토리 삭제

#### 삭제 대상
```
docs/archive/
├── new_readme.md
├── old_guides/ (12개 항목)
├── phase3_nas_deployment.md
└── session_resume.md (0 bytes)

scripts/nas/archive/
└── (확인 필요)
```

#### 테스트 시나리오 5: Archive 내용 확인
```bash
# 1. Archive 내용 확인
ls -la docs/archive/
ls -la scripts/nas/archive/

# 2. 다른 문서에서 참조하는지 확인
grep -r "docs/archive" --include="*.md"
grep -r "scripts/nas/archive" --include="*.py" --include="*.sh"

# 3. Git 이력 확인
git log --oneline -- docs/archive/
git log --oneline -- scripts/nas/archive/

# 예상 결과: Git 이력에 모두 있음
```

#### 테스트 시나리오 6: 문서 링크 확인
```bash
# 삭제 후 문서 링크 깨지는지 확인
grep -r "\[.*\](.*archive" docs/*.md

# 예상 결과: 링크 없음 또는 외부 링크만
```

#### 실행 명령
```bash
git rm -r docs/archive/
git rm -r scripts/nas/archive/
git commit -m "Phase 1.3: Archive 디렉토리 삭제 (Git 이력에 보존)"
```

---

### 1.4 외부 레포 삭제

#### 삭제 대상
```
momentum-etf/  # Jason의 레포
```

#### 테스트 시나리오 7: 외부 레포 사용 확인
```bash
# 1. .gitignore 확인
cat .gitignore | grep momentum-etf

# 2. 코드에서 참조하는지 확인
grep -r "momentum-etf" --include="*.py" --include="*.sh"

# 3. Import 확인
grep -r "from momentum-etf" --include="*.py"
grep -r "import momentum-etf" --include="*.py"

# 예상 결과: .gitignore에 있음, 참조 없음
```

#### 테스트 시나리오 8: 백테스트 실행
```bash
# 삭제 후 백테스트 정상 작동 확인
python -m core.engine.jason_adapter --help

# 예상 결과: 정상 실행 (어댑터가 독립적으로 구현됨)
```

#### 실행 명령
```bash
# 디렉토리 삭제 (Git 추적 안 됨)
rm -rf momentum-etf/

# .gitignore 확인
cat .gitignore | grep momentum-etf

# 예상: 이미 .gitignore에 있으므로 Git commit 불필요
```

---

### 1.5 미구현 UI 삭제

#### 삭제 대상
```
frontend/  # README만 있음
ui/portfolio_manager.py  # 단일 파일
```

#### 테스트 시나리오 9: UI 사용 확인
```bash
# 1. frontend/ 내용 확인
ls -la frontend/
cat frontend/README.md

# 2. ui/portfolio_manager.py 사용 확인
grep -r "ui.portfolio_manager" --include="*.py"
grep -r "from ui import" --include="*.py"

# 3. 실제 UI 확인
ls -la web/dashboard/

# 예상 결과:
# - frontend/: README만, 미구현
# - ui/portfolio_manager.py: 참조 없음
# - web/dashboard/: 실제 React UI
```

#### 테스트 시나리오 10: React UI 실행
```bash
# 삭제 후 React UI 정상 작동 확인
cd web/dashboard
npm run dev

# 예상 결과: 정상 실행 (http://localhost:5173)
```

#### 실행 명령
```bash
# frontend/ 삭제
git rm -r frontend/

# ui/portfolio_manager.py 이동
mkdir -p extensions/ui_archive/standalone
git mv ui/portfolio_manager.py extensions/ui_archive/standalone/
git rm -r ui/

git commit -m "Phase 1.5: 미구현 UI 삭제 및 단일 파일 이동"
```

---

### Phase 1 종합 테스트

#### 테스트 시나리오 11: 전체 기능 검증
```bash
# 1. 미국 시장 지표
python -m core.strategy.us_market_monitor

# 2. Daily Regime Check
python scripts/nas/daily_regime_check.py --dry-run

# 3. 백엔드 API
cd backend
uvicorn app.main:app --reload &
curl http://localhost:8000/health

# 4. 프론트엔드
cd web/dashboard
npm run dev &
curl http://localhost:5173

# 5. Git 상태 확인
git status
git log --oneline -5

# 예상 결과: 모두 정상 작동
```

#### 체크리스트
- [ ] Deprecated & Legacy 삭제 완료
- [ ] 빈 디렉토리 정리 완료
- [ ] Archive 삭제 완료
- [ ] 외부 레포 삭제 완료
- [ ] 미구현 UI 삭제 완료
- [ ] 모든 테스트 통과
- [ ] Git commit 완료

---

## 📊 Phase 1 완료 후 상태

### 삭제된 항목
- `scripts/_deprecated_2025-11-13/` (4개 파일)
- `scripts/legacy/2025-10-05/` (10개 항목)
- `pending/` (빈 디렉토리)
- `docs/archive/` (4개 항목)
- `scripts/nas/archive/`
- `momentum-etf/` (외부 레포)
- `frontend/` (미구현)
- `ui/` (단일 파일 이동)

### 예상 절감
- **파일 수**: 약 50-70개
- **디스크 용량**: 약 10-20MB
- **디렉토리**: 8개

### Git Commits
1. Phase 1.1: Deprecated & Legacy 삭제
2. Phase 1.2: 빈 디렉토리 정리
3. Phase 1.3: Archive 삭제
4. Phase 1.4: (commit 불필요)
5. Phase 1.5: 미구현 UI 삭제

---

## ⏭️ 다음 단계

**Phase 1 완료 후**:
- [ ] 모든 테스트 통과 확인
- [ ] Git push
- [ ] Phase 2 시작 승인 요청

**Phase 2 미리보기**:
- 문서 통합 (ALERT_SYSTEM_*.md, ORACLE_CLOUD_*.md, NAS_*.md)
- 문서 재구성 (deployment/, guides/, development/)
- README 업데이트

---

**Phase 1 시작 준비 완료!** 🚀

**진행 방법**:
1. 각 테스트 시나리오 실행
2. 결과 확인
3. 문제 없으면 삭제 실행
4. 다음 단계로 진행

**시작할까요?** ✅
