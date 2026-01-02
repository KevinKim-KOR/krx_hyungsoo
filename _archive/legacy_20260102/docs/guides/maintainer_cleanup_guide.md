# Cleanup & Organization Suggestions

비즈니스 로직(코드) 외의 데이터, 로그, 테스트, 그리고 목적이 모호한 폴더들에 대한 정리 제안입니다.

## 1. Data & State Folders

### `data/`
*   **성격:** 애플리케이션 실행 중 생성되는 데이터 저장소.
*   **주요 포함 항목:**
    *   DB 파일 (`krx_alertor.db`, `backtest_history.db` 등)
    *   캐시 디렉토리 (`cache/`)
    *   설정/파라미터 파일 (`optimal_params.json`)
    *   **Cleanup Target:**
        *   `data/debugging/`: 디버깅용 임시 출력물로 보임. **[삭제/아카이브]**
        *   `data/tuning_runs/`, `data/tuning_test/`: 최적화 수행 이력. 파일 수가 많으므로 중요 결과만 남기고 **[아카이브]** 권장.
        *   `data/output/`: 리포트 출력물. 주기적 정리 필요.

### `logs/`
*   **성격:** 런타임 로그 파일 저장소.
*   **처리:** `.gitignore`에 포함되어 있는지 확인하고, 오래된 로그는 주기적으로 자동 삭제되도록 설정 권장. 폴더 자체는 **[유지]**.

### `reports/`
*   **성격:** 생성된 HTML/PDF 리포트 저장소로 추정.
*   **처리:** `data/output`과 역할이 중복되는지 확인 필요. 중복이라면 한쪽으로 통합. **[통합/정리]**

## 2. Testing & Quality Assurance

### `tests/`
*   **성격:** `pytest` 기반의 유닛/통합 테스트 코드.
*   **제안:** CI/CD 파이프라인에서 실행되는 필수 코드. **[유지]**.
    *   내부의 `integration`, `tuning` 등 하위 폴더 구조는 적절함.

## 3. Deployment & Environment Variants

### `nas/`
*   **성격:** NAS(Synology 등) 환경에서 실행하기 위한 코드 모음 (`app_nas.py`, `scanner_nas.py` 등).
*   **분석:**
    *   `pc/` (로컬 CLI), `backend/` (서버 API)와 기능적으로 중복될 가능성이 높음.
    *   만약 NAS 환경이 현재 운영되지 않거나, `backend` API로 대체 가능하다면 **[아카이브]** 및 제거 권장.
    *   계속 사용한다면 `extensions/nas_support/` 등으로 이동하여 루트 디렉토리를 정리하는 것을 고려.

### `scripts/dev/`
*   **성격:** 개발 과정에서 작성된 임시 스크립트 모음.
*   **처리:**
    *   현재 사용하지 않는 실험적 코드는 과감히 **[삭제]**하거나 별도 `archive/` 브랜치로 격리.
    *   유용한 유틸리티는 `tools/`로 승격.

## 4. Others

### `.state/`
*   **성격:** 내부 상태 저장용 (혹은 특정 라이브러리가 생성).
*   **처리:** `.gitignore` 포함 여부 확인. 삭제해도 시스템 재기동 시 재생성되는지 확인 후 처리.

### `temp/` or `debug/` (if implies root level)
*   루트 레벨에 `debug` 폴더는 없으나 `data/debugging`이나 스크립트 산출물이 흩어져 있다면 `logs/` 또는 `data/tmp/`로 경로를 일원화하여 루트 오염 방지.

## 종합 정리 계획 (Action Items)

1.  **데이터 정리**: `data/debugging`, `data/tuning_*` 폴더를 백업 후 비우기.
2.  **레거시 청산**: `nas` 폴더가 필수적인지 확인하고, 아니라면 아카이브. `scripts/dev` 내 미사용 파일 삭제.
3.  **구조 단순화**:
    *   `Code`: `core`, `app`(or `backend`), `web`(merge to backend?)
    *   `Utils`: `tools`, `scripts`(ops only), `extensions`
    *   `Data`: `data`, `logs`, `config`, `tests`
    *   **(제거 대상)**: `pc`(CLI를 app으로 통합?), `nas`, `reports`(data로 통합)
