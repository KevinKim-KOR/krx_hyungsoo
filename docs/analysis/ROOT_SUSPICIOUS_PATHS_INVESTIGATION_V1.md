# Root Suspicious Paths Investigation V1

> 단계: `ROOT-CLEANUP-SUSPICIOUS-PATHS-INVESTIGATION-V1`
> 목적: 의심 root 경로 6건 증거 수집 + 1차 판정. **이번 단계는 삭제/이동/리팩토링 금지**.
> 조사 시각: 2026-04-15
> 제외: `freiends_project/`, `znotes/`

---

## A. 기능/산출물 검증

### A-1. 조사 경로 실체

| # | 경로 | 실체 | 최근 mtime | 대략 용도 (조사 전 추정) |
|---|---|---|---|---|
| 1 | `Remote` | **파일** (43 bytes, 1줄) | 2026-04-15 21:28 | 포트 8001→8000 OCI Backend 메모 |
| 2 | `venv/` | 폴더 (Python 3.14.0 venv) | 2026-04-11 17:27 | `.venv/` 와 중복 의심 |
| 3 | `test_scripts/` | 폴더 (1개 파일: `verify_p191_chain.py`) | - | `tests/` 와 구분 불명 |
| 4 | `dashboard/` | 폴더 (`index.html`, `components_d_p_58.js`) | - | 별도 dashboard 의심 |
| 5 | `local/` | 폴더 (`manual_execution_record_drafts/`, `operator_pack/`) | - | 운영 드래프트/수기 실행 저장 |
| 6 | `_archive/` | 폴더 (`cleanup_20260215/`, `deprecated_code/`, `deprecated_docs/`, `legacy_20260102/`) | - | 과거 아카이브 |

### A-2. 실제 참조 요약

| 경로 | 실행 참조? | 참조 위치 | 참조 유형 |
|---|---|---|---|
| `Remote` | **없음** | — | 텍스트 메모만 (내용: `Local Port 8001 - Port 8000 (OCI Backend)`) |
| `venv/` | **없음** | `.gitignore:136` (ignore 등록만) | 활성 사용 경로는 `.venv/` |
| `test_scripts/` | **없음** | `.gitignore:158` (ignore 등록만) | 저장소 미추적, ad-hoc 스크립트 1개 |
| `dashboard/` | **있음** | [backend/main.py:122-128](../../backend/main.py#L122-L128) + [backend/utils.py:21](../../backend/utils.py#L21) | FastAPI `StaticFiles("/dashboard")` mount |
| `local/` | **있음** | `deploy/pc/*.ps1` (5개 스크립트) | PowerShell 운영자 도구 저장소 |
| `_archive/` | **lint 보호 대상** | [app/lint_active_surface.py:29-51](../../app/lint_active_surface.py#L29-L51) | active code (`backend`, `dashboard`, `config`) 에서 import 금지 lint |

### A-3. 1차 판정

| 경로 | 판정 | 한줄 근거 |
|---|---|---|
| `Remote` | **DELETE_CANDIDATE** | 어떤 실행/배포/테스트 경로에서도 참조 없음. 순수 텍스트 메모 |
| `venv/` | **DELETE_CANDIDATE** | 활성 venv 는 `.venv/`. `venv/` 는 참조 0건 |
| `test_scripts/` | **UNKNOWN** | gitignore 처리 (저장소 외 자산). 사용자 로컬 자산 가능성 — 삭제 위험 배제 불가 |
| `dashboard/` | **KEEP** | `backend/main.py` 에서 StaticFiles mount. 운영 경로 |
| `local/` | **KEEP** | `deploy/pc/*.ps1` 5개 스크립트가 실제 pull/push 타깃으로 사용 |
| `_archive/` | **ARCHIVE** | 보존 목적 명확 + lint 로 active 의존성 이미 차단 |

---

## B. 구현 규칙/구조 품질 검증

### B-1. 각 판정의 근거

#### `Remote` → DELETE_CANDIDATE

- **실체**: `cat Remote` 결과 = `Local Port 8001 - Port 8000 (OCI Backend)` (43 bytes)
- **git 이력**: 최초 commit `21a9901a` (2026-02-17, "Fix P146.9: Sync Deadlock & SSH Tunnel Automation") 에서 1 insert 로 추가. 이후 변경 이력 없음
- **실행 참조 조사**: 전 코드베이스 grep 결과 `./Remote`, `BASE_DIR/Remote`, `open("Remote")` 등 참조 0건
- **대체 경로**: 동일 포트 정책이 [README.md](../../README.md), [start.bat:16-27](../../start.bat#L16-L27), [deploy/pc/connect_oci.bat](../../deploy/pc/connect_oci.bat) 에 이미 문서화되어 있음 → Remote 파일은 **중복 메모**
- **삭제 안전성**: 참조 없음 + 내용이 다른 문서에 중복 존재 → 삭제해도 기능 영향 0

#### `venv/` → DELETE_CANDIDATE

- **실체**: Python 3.14.0 venv (`home=C:\Python314`, `command=...venv E:\...\venv`). `.venv/` 와 동일 Python/동일 생성 패턴
- **실행 참조**: 활성 스크립트는 모두 **`.venv/`** 사용
  - [start.bat:23,30](../../start.bat#L23) — `.\.venv\Scripts\python.exe`
  - `.claude/settings.local.json` 전체 — `.venv/Scripts/python`, `.venv/Scripts/black`, `.venv/Scripts/flake8` 만 사용
- **`venv/` 참조**: `.gitignore:136` (ignore 등록) 외 0건
- **삭제 안전성**: `.venv/` 가 유일한 활성 venv. `venv/` 삭제해도 실행 경로 영향 없음

#### `test_scripts/` → UNKNOWN

- **실체**: `verify_p191_chain.py` 1개 파일만 존재
- **저장소 상태**: [.gitignore:158](../../.gitignore#L158) 으로 저장소 미추적. **사용자 로컬 자산**
- **실행 참조**: pytest 설정 ([pytest.ini](../../pytest.ini)), CI 스크립트, docs 어디에도 test_scripts 언급 없음
- **삭제 위험**: gitignore 된 사용자 로컬 디렉터리 — 삭제 시 사용자 로컬 작업 손실 가능. **사용자 확인 필요** (UNKNOWN 유지)

#### `dashboard/` → KEEP

- **실체**: `index.html` + `components_d_p_58.js` (운영자 대시보드 프론트엔드)
- **실행 참조**:
  - [backend/utils.py:21](../../backend/utils.py#L21) — `DASHBOARD_DIR = BASE_DIR / "dashboard"`
  - [backend/main.py:122-128](../../backend/main.py#L122-L128) — `app.mount("/dashboard", StaticFiles(directory=str(DASHBOARD_DIR)), name="dashboard")`
- **live 모드**: 존재 시 mount (`if DASHBOARD_DIR.exists()`) — 운영 가드 포함
- **`pc_cockpit/` 와 관계**: 중복 아님. `pc_cockpit/` = Streamlit 로컬 UI(port 8501), `dashboard/` = FastAPI 정적 페이지(port 8000/dashboard). 역할 분리
- **추가 확인**: [docker-compose.yml:14](../../docker-compose.yml#L14) 의 `./backend/static:/app/static` mount 는 dashboard 와 다른 경로. 조사 중 발견 — [backend/static](../../backend) 실제 파일 없음 (별도 조사 권고)

#### `local/` → KEEP

- **실체**: `manual_execution_record_drafts/`, `operator_pack/` 서브폴더
- **실행 참조**: `deploy/pc/` PowerShell 스크립트 5개
  - [deploy/pc/pull_operator_pack.ps1:7](../../deploy/pc/pull_operator_pack.ps1#L7) — operator_pack pull 타깃
  - [deploy/pc/generate_record_template.ps1:17](../../deploy/pc/generate_record_template.ps1#L17) — `$DraftDir = "local/manual_execution_record_drafts"`
  - [deploy/pc/push_record_draft.ps1:16,30](../../deploy/pc/push_record_draft.ps1#L30) — draft push source
  - [deploy/pc/daily_operator.ps1:92](../../deploy/pc/daily_operator.ps1#L92) — 운영 안내 문구
  - [deploy/pc/daily_manual_loop.ps1](../../deploy/pc/daily_manual_loop.ps1) — 수동 루프
- **문서 참조**: [docs/runbooks/runbook_live_micro_pilot_v1.md](../runbooks/runbook_live_micro_pilot_v1.md), [docs/contracts/contract_deployment_profile_v1.md](../contracts/contract_deployment_profile_v1.md)

#### `_archive/` → ARCHIVE

- **실체**: 4개 하위 아카이브 (`cleanup_20260215/`, `deprecated_code/`, `deprecated_docs/`, `legacy_20260102/`)
- **보호 장치**: [app/lint_active_surface.py:29-51](../../app/lint_active_surface.py#L29-L51) 의 `check_archive_dependencies()` 가 `backend`, `dashboard`, `config` 내에서 `from _archive`, `import _archive`, `_archive/` + `open()/Path()` 조합을 검출해 차단
- **현존 active 참조**: docstring 주석 내 legacy 경로 언급만 존재 (`app/tuning/telemetry.py:8` 등 4건) — 실제 import 아님
- **보존 근거**: legacy 검증 시 대조용. lint 로 이미 격리

### B-2. 현재 단계에서 건드리면 안 되는 경로

모든 6개 경로 — 이번 단계는 **조사/판정만**. 삭제/이동/rename 금지 원칙을 따라 다음 단계로 이관.

### B-3. 다음 단계 권고

#### 즉시 삭제 후보 (사용자 승인 필요, 단일 PR 가능)

| 경로 | 이유 | 확인 필요 사항 |
|---|---|---|
| `Remote` | 참조 0건 + 내용 중복 | 사용자 개인 메모 목적 여부 (별도 `znotes/` 이동 고려) |
| `venv/` | `.venv/` 가 유일 활성 venv | 사용자 2개 venv 운영 의도 여부 (예: Python 버전 분기 테스트) |

#### 추가 조사 필요

| 경로 | 조사 항목 |
|---|---|
| `test_scripts/` | gitignore 처리 중이므로 **사용자 직접 확인** — (1) 여전히 사용하는 ad-hoc 검증 스크립트인지 (2) 폐기해도 되는지 |
| `backend/static/` (투어링 중 발견) | [docker-compose.yml:14](../../docker-compose.yml#L14) 에서 mount 되지만 실제 폴더 없음. mount 실패 가능성 — 별도 조사 |

#### 인벤토리 문서화 필요

- 이번 조사 6경로 + `backend/static/` 를 포함한 **root 폴더 전체 인벤토리** 문서를 별도 단계에서 작성 권고 (예: `docs/analysis/ROOT_INVENTORY_V1.md`). [REPORTS_INVENTORY.md](REPORTS_INVENTORY.md) 와 동일 패턴 (LIVE/ARCHIVE/DEAD/UNKNOWN 4분류)

#### 보존 확정 (추가 작업 없음)

- `dashboard/` — LIVE, StaticFiles mount
- `local/` — LIVE, PowerShell 운영 스크립트 타깃
- `_archive/` — ARCHIVE, lint 로 격리 완료

---

## 보고 요약 (1줄)

**6 경로 조사 완료: KEEP 2 (dashboard/, local/) / ARCHIVE 1 (_archive/) / DELETE_CANDIDATE 2 (Remote, venv/) / UNKNOWN 1 (test_scripts/). 삭제/이동 미수행.**
