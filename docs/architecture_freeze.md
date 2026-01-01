# Architecture Freeze: Engine & UI Separation Principles

**Status**: FROZEN (Since Phase 12 completion)
**Purpose**: To ensure the stability of the trading engine while allowing safe UI development.

---

## 5 Core Immutable Principles (5대 불변 원칙)

UI 개발 시 다음 5가지 원칙을 절대적으로 준수해야 합니다.

### 1. Single Log Source (로그 중심 관제)
*   **Rule**: 실행 결과와 상태 확인은 오직 **로그 파일 파싱**을 통해서만 수행한다.
*   **Source**: `logs/daily_YYYYMMDD.log`
*   **Constraint**: 엔진 내부의 메모리 상태나 변수에 직접 접근하지 않는다.

### 2. Idempotency Respect (중복 실행 방지 존중)
*   **Rule**: UI에서 "실행" 버튼을 눌러도, 엔진 내부의 **중복 방지 로직(`SKIP`)을 그대로 수용**한다.
*   **Constraint**: UI에서는 절대 `--force` 옵션을 노출하거나 사용하지 않는다. (수동 복구 시에만 터미널에서 사용)

### 3. Close-On-Close (일별 확정 데이터)
*   **Rule**: UI는 장중 실시간 시세나 호가 데이터를 다루지 않는다.
*   **Constraint**: 오직 **장 마감 후 확정된 데이터(Daily Close)**와 그에 따른 시그널/잔고만을 표시한다. 실시간 변동성은 UI의 관심사가 아니다.

### 4. Config Immutable (설정 불변)
*   **Rule**: `config/production_config.py` (V1) is **Immutable**. Upgrades use `production_config_v2.py`. UI treats them as **Read-Only**.
*   **Constraint**: UI에서 슬라이더나 폼을 통해 파라미터를 변경하고 저장하는 기능을 구현하지 않는다. 파라미터 변경은 코드 수정 배포로 간주한다.

### 5. File-Based Coupling (파일 기반 느슨한 결합)
*   **Rule**: UI 코드는 엔진 코드를 절대 `import` 하지 않는다.
*   **Constraint**: 오직 엔진이 산출하는 **Contract 5 Reports**와 로그만을 소비한다.
    *   `reports/phase_c/report_human_v1.json` (Dashboard UI)
    *   `reports/phase_c/report_ai_v1.json` (AI Agent Context)
    *   `reports/phase_c/recon_daily.jsonl` (Detailed Tables)

---

**"UI는 엔진을 바라보는 창문일 뿐, 엔진을 조작하는 핸들이 아니다."**
