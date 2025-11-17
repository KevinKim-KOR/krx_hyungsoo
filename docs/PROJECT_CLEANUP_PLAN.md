# 프로젝트 정리 계획

**작성일**: 2025-11-17  
**목적**: 미사용 파일/폴더 정리 및 구조 개선

---

## 📋 현재 프로젝트 구조 분석

### 루트 디렉토리 파일 (정리 대상)

#### 삭제 가능 파일
```
COMMIT_MSG.txt                    # 빈 파일
COMMIT_MSG_FINAL.txt              # 빈 파일
git_commit_week3.txt              # 임시 커밋 메시지
git_commit_week4.txt              # 임시 커밋 메시지
fix_corrupted_cache.py            # 일회성 스크립트
test_data_loading.py              # 임시 테스트
test_realtime_signals.py          # 임시 테스트
test_step2_notification.py        # 임시 테스트
test_step3_monitoring.py          # 임시 테스트
quick_phase2_test.py              # 임시 테스트
update_data.py                    # 일회성 스크립트
config.py                         # 중복 (config/ 폴더 사용)
best_params.json                  # 임시 결과
```

#### 정리 가능 문서
```
PHASE2_COMPLETION_REPORT.md       # docs/로 이동
PHASE2_FINAL_SUMMARY.md           # docs/로 이동
PHASE2_GUIDE.md                   # docs/로 이동
PHASE2_ISSUE_REPORT.md            # docs/로 이동
QUICK_TEST.md                     # docs/로 이동
README_PHASE3.md                  # docs/로 이동
```

#### PowerShell 스크립트
```
reorganize_docs.ps1               # 사용 완료 후 삭제
reorganize_docs_fixed.ps1         # 사용 완료 후 삭제
reorganize_docs_simple.ps1        # 사용 완료 후 삭제
```

---

## 📁 주요 폴더 분석

### 1. `app/` vs `backend/` vs `web/` (중복)

**현황**:
- `app/`: FastAPI 앱 (5개 파일)
- `backend/`: 백엔드 코드 (27개 파일)
- `web/`: 웹 관련 (13개 파일)

**정리 방안**:
```
backend/                    # 통합 백엔드 폴더
├── api/                    # FastAPI (app/ 내용 이동)
├── services/               # 비즈니스 로직
├── models/                 # 데이터 모델
└── utils/                  # 유틸리티

web/                        # 프론트엔드 (유지)
├── static/
├── templates/
└── ...

# 삭제: app/ (backend/api/로 통합)
```

### 2. `deprecated/` (삭제 대상)

**현황**: 12개 파일

**정리 방안**: 전체 삭제 (이미 deprecated 표시)

### 3. `momentum-etf/` (외부 프로젝트)

**현황**: 111개 파일

**정리 방안**:
- Jason의 momentum-etf 레포지토리 코드
- 필요한 부분만 `core/engine/jason/`에 통합
- 원본 폴더 삭제 또는 `.gitignore` 추가

### 4. `frontend/` vs `ui/` (중복)

**현황**:
- `frontend/`: 1개 파일
- `ui/`: 1개 파일

**정리 방안**:
```
web/                        # 통합 프론트엔드
├── frontend/               # React 앱 (Phase 5-5)
├── static/                 # 정적 파일
└── templates/              # Jinja2 템플릿

# 삭제: frontend/, ui/ (web/로 통합)
```

### 5. `scripts/` (정리 필요)

**현황**: 159개 파일

**정리 방안**:
```
scripts/
├── phase1/                 # Phase 1 스크립트
├── phase2/                 # Phase 2 스크립트
├── phase3/                 # Phase 3 스크립트
├── phase4/                 # Phase 4 스크립트
├── phase5/                 # Phase 5 스크립트 (신규)
├── sync/                   # 동기화 스크립트 (유지)
├── ops/                    # 운영 스크립트 (유지)
├── linux/                  # Linux 스크립트 (유지)
└── automation/             # 자동화 스크립트 (유지)

# 정리: 중복/임시 스크립트 삭제
```

### 6. `data/` (정리 필요)

**현황**: 754개 파일

**정리 방안**:
```
data/
├── cache/                  # 캐시 (유지, .gitignore)
│   └── ohlcv/
├── sync/                   # 동기화 데이터 (유지)
│   └── ohlcv/
├── output/                 # 결과 (유지)
│   ├── ml/
│   ├── optimization/
│   └── backtest/
└── raw/                    # 원본 데이터 (정리)

# 정리: 오래된 캐시, 중복 파일 삭제
```

### 7. `docs/` (정리 필요)

**현황**: 88개 파일

**정리 방안**:
```
docs/
├── phases/                 # Phase별 문서
│   ├── phase1/
│   ├── phase2/
│   ├── phase3/
│   ├── phase4/
│   └── phase5/
├── guides/                 # 가이드 문서
│   ├── SETUP.md
│   ├── DEPLOYMENT.md
│   └── ...
├── reports/                # 보고서 (완료 보고서)
│   ├── PHASE2_COMPLETE.md
│   ├── PHASE3_COMPLETE.md
│   ├── PHASE4_COMPLETE.md
│   └── PHASE5_COMPLETE.md
└── archive/                # 아카이브 (오래된 문서)

# 정리: 중복 문서, 오래된 문서 아카이브
```

### 8. `reports/` (중복)

**현황**: 72개 파일

**정리 방안**: `docs/reports/`로 통합 후 삭제

### 9. `backtests/` (정리 필요)

**현황**: 3개 파일

**정리 방안**: `data/output/backtest/`로 이동

### 10. `infra/` (유지)

**현황**: 7개 파일 (Docker, 배포 설정)

**정리 방안**: 유지

---

## 🎯 정리 우선순위

### Priority 1: 즉시 삭제 가능

```bash
# 빈 파일
rm COMMIT_MSG.txt COMMIT_MSG_FINAL.txt

# 임시 커밋 메시지
rm git_commit_week3.txt git_commit_week4.txt

# 임시 테스트 스크립트
rm test_*.py quick_phase2_test.py

# 일회성 스크립트
rm fix_corrupted_cache.py update_data.py

# PowerShell 스크립트 (사용 완료)
rm reorganize_docs*.ps1

# Deprecated 폴더
rm -rf deprecated/
```

### Priority 2: 문서 정리

```bash
# 루트 문서 → docs/로 이동
mv PHASE2_*.md docs/phases/phase2/
mv QUICK_TEST.md docs/guides/
mv README_PHASE3.md docs/phases/phase3/

# reports/ → docs/reports/로 통합
mv reports/* docs/reports/
rmdir reports/
```

### Priority 3: 폴더 구조 정리

```bash
# app/ → backend/api/로 통합
mv app/* backend/api/
rmdir app/

# frontend/, ui/ → web/로 통합
mv frontend/* web/frontend/
mv ui/* web/ui/
rmdir frontend/ ui/

# backtests/ → data/output/backtest/로 이동
mv backtests/* data/output/backtest/
rmdir backtests/
```

### Priority 4: 외부 프로젝트 정리

```bash
# momentum-etf/ → .gitignore 추가 또는 삭제
echo "momentum-etf/" >> .gitignore
# 또는
rm -rf momentum-etf/
```

---

## 📊 정리 후 예상 구조

```
krx_alertor_modular/
├── .env.template
├── .gitignore
├── README.md
├── CHANGELOG.md
├── pyproject.toml
├── requirements.txt
├── docker-compose.yml
│
├── backend/                    # 백엔드 (통합)
│   ├── api/                    # FastAPI
│   ├── services/               # 비즈니스 로직
│   ├── models/                 # 데이터 모델
│   └── utils/                  # 유틸리티
│
├── web/                        # 프론트엔드 (통합)
│   ├── frontend/               # React 앱
│   ├── static/                 # 정적 파일
│   └── templates/              # Jinja2 템플릿
│
├── core/                       # 핵심 로직
│   ├── engine/                 # 백테스트 엔진
│   ├── strategy/               # 전략
│   ├── data_loader.py
│   └── ...
│
├── pc/                         # PC 전용 (ML, 최적화)
│   ├── ml/                     # 머신러닝
│   └── optimization/           # 포트폴리오 최적화
│
├── nas/                        # NAS 전용
│   └── ...
│
├── scripts/                    # 스크립트 (정리)
│   ├── phase1/
│   ├── phase2/
│   ├── phase3/
│   ├── phase4/
│   ├── phase5/
│   ├── sync/
│   ├── ops/
│   ├── linux/
│   └── automation/
│
├── data/                       # 데이터 (정리)
│   ├── cache/                  # 캐시
│   ├── sync/                   # 동기화
│   └── output/                 # 결과
│       ├── ml/
│       ├── optimization/
│       └── backtest/
│
├── docs/                       # 문서 (정리)
│   ├── phases/                 # Phase별
│   ├── guides/                 # 가이드
│   ├── reports/                # 보고서
│   └── archive/                # 아카이브
│
├── config/                     # 설정
├── extensions/                 # 확장 기능
├── infra/                      # 인프라
├── logs/                       # 로그
├── tests/                      # 테스트
└── tools/                      # 도구
```

---

## 🚀 실행 계획

### Step 1: 백업

```bash
# 전체 프로젝트 백업
cd "e:/AI Study/"
tar -czf krx_alertor_modular_backup_$(date +%Y%m%d).tar.gz krx_alertor_modular/
```

### Step 2: Priority 1 실행 (즉시 삭제)

```bash
cd "e:/AI Study/krx_alertor_modular"

# 빈 파일 및 임시 파일 삭제
rm COMMIT_MSG.txt COMMIT_MSG_FINAL.txt
rm git_commit_week3.txt git_commit_week4.txt
rm test_*.py quick_phase2_test.py
rm fix_corrupted_cache.py update_data.py
rm reorganize_docs*.ps1

# Deprecated 폴더 삭제
rm -rf deprecated/

# Git commit
git add -A
git commit -m "Cleanup: 임시 파일 및 deprecated 폴더 삭제"
git push
```

### Step 3: Priority 2 실행 (문서 정리)

```bash
# 문서 정리 스크립트 실행 (별도 작성)
python scripts/cleanup/reorganize_docs.py

# Git commit
git add -A
git commit -m "Cleanup: 문서 구조 정리"
git push
```

### Step 4: Priority 3 실행 (폴더 구조 정리)

```bash
# 폴더 구조 정리 스크립트 실행 (별도 작성)
python scripts/cleanup/reorganize_folders.py

# Git commit
git add -A
git commit -m "Cleanup: 폴더 구조 정리"
git push
```

### Step 5: Priority 4 실행 (외부 프로젝트 정리)

```bash
# momentum-etf/ 정리
echo "momentum-etf/" >> .gitignore

# Git commit
git add -A
git commit -m "Cleanup: 외부 프로젝트 .gitignore 추가"
git push
```

---

## ⚠️ 주의사항

1. **백업 필수**: 정리 전 반드시 전체 프로젝트 백업
2. **단계별 실행**: 한 번에 모든 정리 작업을 하지 말고, 단계별로 실행 후 테스트
3. **Git 커밋**: 각 단계마다 Git 커밋하여 롤백 가능하도록 구성
4. **테스트**: 정리 후 주요 기능 테스트 (백테스트, API, ML 모델 등)
5. **문서 업데이트**: 정리 후 README.md 및 관련 문서 업데이트

---

## 📝 체크리스트

- [ ] 백업 완료
- [ ] Priority 1: 즉시 삭제 가능 파일 삭제
- [ ] Priority 2: 문서 정리
- [ ] Priority 3: 폴더 구조 정리
- [ ] Priority 4: 외부 프로젝트 정리
- [ ] 테스트 실행
- [ ] 문서 업데이트
- [ ] Git 커밋 및 푸시

---

**작성**: Cascade AI Assistant  
**최종 수정**: 2025-11-17
