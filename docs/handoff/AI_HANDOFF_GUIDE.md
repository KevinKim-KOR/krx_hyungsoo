# AI 핸드오프 가이드

> 이 문서는 Claude Code에서 다른 AI 도구로 작업을 이관할 때 참고하는 가이드입니다.
> asof: 2026-03-29

---

## 1. 프로젝트 개요

**KRX Alertor Modular** — 한국 ETF 모멘텀 트레이딩 시스템

| 구성 | 역할 | 포트 |
|---|---|---|
| PC Cockpit | Streamlit UI (파라미터 설정, 백테스트, 튜닝) | 8501 |
| Backend | FastAPI API (읽기 전용 옵저버) | 8000 |
| OCI | Oracle Cloud 운영 서버 | 원격 |

**핵심 흐름**: `Run Tune → SSOT 반영 → Run Full Backtest → 승격 판정`

---

## 2. 9개 철칙 (모든 세션에 적용)

### 커뮤니케이션
1. 모든 대답은 **한국어**
2. 모든 산출물/문서는 **한국어**
3. 코드 문제 발견 시 **즉시 수정 금지** — 보고 → 승인 → 수정

### 작업 절차
4. `znotes/` 폴더는 **명시적 지시 없이 읽지 않음** (개인 메모)
5. **순차 처리** 원칙 (튜닝 병렬만 예외)
6. 리팩토링 시 **Dockerfile/배포 스크립트 영향 확인** 필수

### 코딩 표준
7. **암묵적 fallback/default 금지** — 필수값 누락 시 명시적 에러
8. 코드 수정 후 **black + flake8** 실행 필수
9. **1 파일 1 기능** (단일 책임 원칙)

---

## 3. SSOT (Single Source of Truth)

**파라미터 SSOT**: `state/params/latest/strategy_params_latest.json`

현재 5축 + 유니버스 모드:
- `params.lookbacks.momentum_period`
- `params.lookbacks.volatility_period`
- `params.decision_params.entry_threshold`
- `params.decision_params.exit_threshold` (= stop_loss)
- `params.position_limits.max_positions`
- `universe_mode` (최상위, fixed_current 또는 expanded_candidates)

---

## 4. 현재 진행 상태

### 완료된 단계
| 단계 | 내용 |
|---|---|
| P204 | ML 튜닝 인프라 (Optuna, equal_3way, 목적함수, 승격 판정) |
| P205 구조 정리 | cockpit 분해, main.py 라우터 분해, 문서 거버넌스 |
| P205-STEP1 | 검색 공간 3축→5축 확장 |
| P205-STEP2 | 감도 보정 (두 축 모두 LOW_SENSITIVITY, 기존 범위 유지) |
| P205-STEP3 | Backtest 5축 메타 가드 + 승격 판정 정합성 |
| P205-STEP4 | 유니버스 확장 후보군 도입 (fixed_current + expanded_candidates) |
| P205-STEP5A | 다이나믹 유니버스 스캐너 아키텍처 설계 (3계층 모델, Feature Registry) |
| P205-STEP5B | `dynamic_etf_market` 후보군 생성 및 V1 Feature 엔진 구현 (P205-STEP5B) |

### P205-STEP4 잔여 이슈 (Codex 리뷰 기준)
- 자동 적용 버튼 universe_mode 복사: **코드 수정 완료, 재실행 필요**
- 최신 산출물에 universe_mode 메타: **다음 Run Tune 실행 시 자동 기록**
- 검산 파일(trials_top20.csv) 유니버스 컬럼: **미완료**

### 다음에 할 수 있는 작업
- P205-STEP4 산출물 재생성 (Run Tune + Run Backtest 실행)
- P205-STEP5 이후 (마스터플랜에 따라)
- 일반 lint sweep (backend/routers/ 전체)

---

## 5. 코드 구조 (핵심만)

```
pc_cockpit/
  cockpit.py (78줄) — 부트스트랩 + 탭 라우팅
  views/ — UI 렌더 모듈 7개
  services/ — 공유 서비스 5개

backend/
  main.py (134줄) — 앱 팩토리 + 라우터 등록
  utils.py — 공유 유틸 (logger, safe_read_*, 경로)
  routers/ — API 라우터 16개 모듈

app/
  run_tune.py — Optuna 튜닝 CLI
  run_backtest.py — Full Backtest CLI
  tuning/
    search_space.py — 5축 검색 공간
    universe_config.py — 유니버스 모드 (fixed/expanded)
    promotion_verdict_core.py — 승격 판정 순수 로직
    sensitivity_scan.py — 감도 스캔
  ops_summary/ — ops summary 패키지
  scanner/
    config.py — 스캐너 대상 풀, Feature Registry 및 Churn 룰
    candidate_pool.py — ETF 1차 필터 풀 생성
    feature_provider.py — 지표 계산(Registry 기반) 코어
    snapshot.py — 결정식(deterministic) 스냅샷 생성 / Churn Metrics
    run_scanner.py — 실행 진입점
  utils/param_loader.py — SSOT 파라미터 로더
```

상세 구조: `docs/structure_baseline.md`

---

## 6. 품질 게이트

코드 수정 후 반드시 실행:
```bash
# 1. black 포맷
.venv/Scripts/black --target-version py39 <수정파일>

# 2. 컴파일 체크
python -m py_compile <수정파일>

# 3. flake8 (차단 이슈)
.venv/Scripts/flake8 --select=E999,F821 <수정파일>
```

참고: black 기본 line-length=88, flake8은 `--max-line-length 88`과 호환.

---

## 7. 문서 관리 규칙

`docs/docs_governance.md` 참조.

| 변경 유형 | 갱신 대상 |
|---|---|
| 코드 구조 변경 | `structure_baseline.md` |
| 단계 완료 | `docs/handoff/`에 closeout 문서 |
| UI 구조 변경 | 기존 UI 문서 deprecated 여부 판단 |

분류 체계: Current Truth / Closeout / Reference / Deprecated

---

## 8. 작업 스타일 (사용자 선호)

- **웹 AI(GPT/Gemini)**가 전체 마스터플랜/전략을 설계
- **코드 연결 AI**가 세부 구현 + 검증
- 지시문은 보통 `[P205-STEP??-이름-V?]` 형식으로 옴
- 각 지시문 끝에 **최종 보고 JSON 템플릿**이 있으면 그것만 제출
- Codex(GitHub Copilot)가 사후 리뷰를 하므로, **정직한 보고**가 중요
  - 아직 실행 안 한 산출물을 "있다"고 보고하면 FAIL 받음

---

## 9. 주의사항

### 절대 하면 안 되는 것
- `znotes/` 자발적 접근
- 승인 없이 코드 수정
- 암묵적 fallback/default
- 유니버스/목적함수/체결 모델을 지시 없이 변경

### 자주 실수하는 패턴
- `reports/tuning/` 파일이 `.gitignore`에 걸려있음 → `git add -f` 필요
- `backend/main.py`에서 `BASE_DIR` import → `backend.utils`에서 가져와야 함
- SSOT의 `exit_threshold`가 Tune의 `stop_loss`에 대응 (이름 다름)
- 산출물이 "코드에는 있는데 파일에는 없다" → 재실행이 필요한 것

---

## 10. 참고할 문서 우선순위

1. `docs/structure_baseline.md` — 코드 구조 진실원
2. `docs/docs_governance.md` — 문서 관리 규칙
3. `docs/docs_inventory.md` — 전체 문서 분류표
4. `docs/SSOT/INVARIANTS.md` — 시스템 불변 원칙
5. `docs/handoff/P204_closeout.md` — P204 종료 기록
6. `docs/handoff/P205_structure_closeout.md` — P205 구조 정리 기록
7. `docs/analysis/P204_MASTER_PLAN_vFinal.md` — P204 설계 원칙
