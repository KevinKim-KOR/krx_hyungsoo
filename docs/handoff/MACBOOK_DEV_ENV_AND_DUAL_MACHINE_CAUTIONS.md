# 맥북 개발환경 구성 + 맥/PC 병행 작업 주의사항

작성: 2026-08-12 (개발자)
대상: 맥북과 윈도우 PC 양쪽에서 이 저장소를 작업하는 사용자 / 다음 세션 개발자
성격: 환경 구성 기록 + 병행 작업 시 사고 방지 체크리스트

---

## 1. 맥북에 설치·설정한 것

### 1.1 설치 방식 — Homebrew 대신 홈 디렉터리

Homebrew 는 `/opt/homebrew` (시스템 공용) 에 설치돼 관리자 비밀번호가 필요하다.
비밀번호 프롬프트에서 에이전트 작업이 중단되므로, **sudo 가 필요 없는 홈 디렉터리 설치**로 통일했다.
사용자가 폴더를 직접 관리할 일은 없고 명령어 사용법도 동일하다.

| 도구 | 버전 | 설치 위치 |
|---|---|---|
| uv (Python 버전·패키지 관리자) | 0.12.3 | `~/.local/bin` |
| Python | **3.12.13** (uv 관리, arm64) | uv 내부 + 프로젝트 `.venv` |
| nvm (Node 버전 관리자) | 0.40.1 | `~/.nvm` |
| Node / npm | **v24.19.0** / 11.17.0 | `~/.nvm/versions/node/v24.19.0` |

`~/.zshrc` 에 uv·nvm 로드 줄이 자동 추가됐다. 새 터미널에서 `python`/`node` 가 바로 잡힌다.

시스템 기본 `/usr/bin/python3` (3.9.6) 은 건드리지 않았다.
`requirements.txt` 의 `numpy==2.4.6` / `scikit-learn==1.9.0` 이 3.12 이상을 요구해서 별도 설치가 필요했다.

### 1.2 프로젝트 의존성

- `.venv` — `requirements.txt` 전량 설치. `numpy 2.4.6` / `scikit-learn 1.9.0` 핀 버전 일치 확인.
- `torch 2.13.0` — 맥은 CUDA 가 없어 **CPU/MPS 빌드**. `torch.backends.mps.is_available() == True`.
- `black` / `flake8` — `requirements.txt` 에 없어서 venv 에만 추가 설치 (DEV_RULES §3 자체 검수 도구).
- `frontend/node_modules` — `npm install` 완료 (456MB).

### 1.3 환경변수 파일 (둘 다 gitignored)

- `.env` — `.env.example` 복사 후 채움. `TELEGRAM_*` 는 사용자가 입력. `OCI_SSH_TARGET` / `OCI_REMOTE_INBOX` / `OCI_REMOTE_OUTBOX` 는 저장소 문서에서 찾아 채움. `OCI_BACKEND_URL` / `OCI_OPS_TOKEN` 은 비밀값이라 비어 있음.
- `frontend/.env.local` — `NEXT_PUBLIC_API_BASE=http://127.0.0.1:8000`.

**서버는 `.env` 를 기동 시점에 읽는다. `.env` 를 고치면 반드시 재기동한다.**

### 1.4 기동 스크립트 — `start.sh` / `stop.sh` (신규)

`.bat` 두 개를 맥용으로 옮긴 것. 목적은 같고 수단만 다르다.

| | Windows (`.bat`) | macOS (`.sh`) |
|---|---|---|
| 프로세스 종료 | `netstat` + `taskkill` | `lsof` + `kill` |
| 서버 실행 | 새 cmd 창 2개 | 백그라운드 + 로그 파일 |
| 로그 | 창에 직접 표시 | `/tmp/krx_backend.log` · `/tmp/krx_frontend.log` |
| Python 경로 | `.venv\Scripts\python.exe` | `.venv/bin/python` |

nvm 으로 설치한 node 는 비대화형 셸의 PATH 에 없어서, `start.sh` 안에서 `nvm.sh` 를 명시적으로 로드한다.

### 1.5 시장 데이터

`state/market/market_data.sqlite` 는 gitignored 라 clone 에 포함되지 않는다.
맥에서는 백엔드 기동 후 **`POST /market/refresh`** (UI 의 시장 갱신 버튼과 동일 경로) 로 채웠다.
FinanceDataReader 경유라 PC 도 OCI 도 필요 없다.

- 소요 68초 / ETF **1,163**종 / `etf_daily_price` **92,123**행 / 실패 0건
- **가격 이력 범위: 2026-04-14 ~ 2026-08-12 (약 4개월)**
- 6시간 cooldown 가드가 있어 연속 재실행은 막힌다

### 1.6 git

`user.name = KevinKim-KOR` / `user.email = minandsoo44@gmail.com` (global).

### 1.7 OCI (미완)

`~/.ssh/config` 에 alias 추가 완료 (기존 파일은 `~/.ssh/config.bak` 백업).

```
Host oci-krx
  HostName 152.67.211.223
  User ubuntu
  IdentityFile ~/.ssh/id_ed25519
  IdentitiesOnly yes
```

서버는 살아 있으나(`22` 포트 응답) **맥 공개키가 서버 `authorized_keys` 에 없어 `Permission denied (publickey)`** 상태다.
그 파일을 고치려면 이미 서버에 들어가 있어야 해서, 현재 접속 수단을 가진 PC 등에서 1회 등록이 필요하다.

---

## 2. 맥에서 실행하는 법

```bash
./start.sh          # 백엔드 8000 + 프론트 3000 + 브라우저 열기
./stop.sh           # 둘 다 종료

# 백엔드 검증
.venv/bin/black --check app tests scripts
.venv/bin/flake8 app tests scripts

# 전체 pytest — autosend 플래그 4개를 반드시 앞에 붙인다 (§3.5 참조)
PUSH_AUTOSEND_ENABLED=true PUSH_AUTOSEND_MARKET_BRIEFING_ENABLED=true \
PUSH_AUTOSEND_SPIKE_OR_FALLING_ALERT_ENABLED=true \
PUSH_AUTOSEND_HOLDINGS_BRIEFING_ENABLED=true .venv/bin/python -m pytest tests/ -q

# 프론트 검증 (DEV_RULES §10 — dev 서버 켠 채 npm run build 금지)
cd frontend && npx tsc --noEmit && npm run lint && npx vitest run
```

2026-08-12 기준 실측: black 276 files unchanged · flake8 0 · tsc 0 · eslint 0 · vitest **157 passed** · pytest **1137 passed / 2 failed**.
잔여 2건은 §3.6 참조 (맥 환경 문제 아님).

---

## 3. 맥 ↔ PC 병행 작업 주의사항

### 3.1 git 에 안 들어가는 것 = 양쪽이 서로 다르다

`.env` · `frontend/.env.local` · `.venv` · `frontend/node_modules` · `state/` 전부 gitignored 다.
**`git pull` 로 동기화되지 않는다.** 한쪽에서 환경변수를 추가하면 다른 쪽에 수동 반영해야 한다.
유일한 동기화 통로는 `.env.example` 이므로, 새 환경변수를 도입하면 반드시 거기에 변수명을 추가한다.

### 3.2 ⚠️ 최우선 — 보유(holdings) 데이터 사고 위험

- 정본은 **OCI** 에 있다. PC 와 맥의 `state/holdings/holdings_latest.json` 은 각자의 로컬 사본이다.
- **맥에는 holdings 파일이 아예 없다.** 맥에서 화면을 열면 보유 0건으로 보이는 게 정상이다.
- **맥의 비어 있는/부분적인 holdings 를 OCI 로 올리면 실보유 32종목을 덮어쓴다.** POC3-08 에서 실제로 33건 → 1건으로 덮어쓴 사고가 있었고 OCI 정본에서 복구했다.
- 맥에서 `PUT /holdings` 계열 쓰기를 실행하기 전에, 그 결과가 OCI 로 전파되는 경로인지 반드시 확인한다.

### 3.3 시장 데이터 이력 길이가 다르다

맥은 FDR 로 새로 받은 **약 4개월치**, PC 는 KRX CSV 로 적재한 장기 시계열을 갖고 있을 수 있다
(`scripts/ingest_krx_timeseries.py` 는 수동 다운로드 CSV 를 읽는 도구라 자동 재현이 안 된다).

→ **백테스트·ML 산출물·수치 비교는 한쪽 기준으로만 한다.** 양쪽 수치를 섞어 비교하면 안 된다.
모멘텀 계산은 60거래일 기준이라 맥의 범위로도 동작하지만, 장기 구간이 필요하면 PC/OCI 에서 DB 를 가져와야 한다.

### 3.4 pytest 가 실제 `state/` 경로에 파일을 쓴다

`tests/conftest.py` 는 runs·handoff·holdings·market_cache 는 임시 경로로 격리하지만
**market DB 와 nav refresh 는 격리 대상이 아니다.**
맥에서 pytest 를 처음 돌렸을 때 실제로 아래가 생성됐다.

```
state/market/market_data.sqlite
state/market/nav_discount_refresh_latest.json
state/runs/*.json
```

맥은 원래 데이터가 없어 피해가 없었지만, **PC 에서 full pytest 를 돌리면 실데이터 경로에 쓰기가 발생한다.**

### 3.5 autosend 플래그 때문에 같은 테스트가 양쪽에서 다르게 나온다

`tests/test_runtime_runner_partial_delivery.py` 의 2건과 `tests/test_low_frequency_push_operation.py` 1건은
`PUSH_AUTOSEND_ENABLED` 등을 **테스트가 직접 설정하지 않고 개발자 `.env` 에 켜져 있는 걸 전제**한다.
(같은 파일의 세 번째 테스트는 `monkeypatch.setenv` 로 직접 설정해서 통과한다.)

PC `.env` 에 플래그가 있으면 통과하고, 맥에서는 실패한다. **코드 문제가 아니라 테스트의 환경 의존이다.**

이 4개 플래그는 실제 텔레그램 발송을 여는 스위치라 **맥 `.env` 에는 넣지 않았다.**
테스트 실행 시에만 명령 앞에 붙인다 (§2 참조).
참고로 이 4개는 `.env.example` 과 `docs/KILL_SWITCHES.md` 어디에도 등재돼 있지 않다.

### 3.6 현재 알려진 기존 실패 2건 (양쪽 공통)

`tests/test_factor_signals.py` 2건이 `KeyError: 'message_text'` 로 실패한다.
티커를 `AAA`/`BBB`/`CCC` 로 넣는데 **POC3-08 (A) 의 종목코드 6자리 검증**이 이를 막는다.

```
PUT /holdings status = 422
{'detail': "holdings[0].ticker 형식 오류 — 종목코드는 영숫자 6자리여야 합니다 (received: 'AAA')"}
```

환경 의존이 없는 순수 계약 불일치라 **PC 에서도 동일하게 실패한다.**
POC3-08 때 백엔드는 focused 41건만 돌려서 잡히지 않은 것으로 보인다. 미수정 상태.

### 3.7 torch 빌드가 다르다 — ML 산출물은 PC 에서만

`requirements.txt` 주석대로 PC 는 4070 SUPER + CUDA 12.4 wheel 을 쓴다.
맥은 CPU/MPS 빌드(2.13.0)라 **학습 결과 수치가 재현되지 않을 수 있다.**
`scripts/run_ml_*.py` 계열 산출물 생성은 PC 에서 한다. 맥에서는 코드 수정과 테스트까지만.

### 3.8 `package-lock.json` diff 주의

npm 버전이 다르면 `npm install` 만으로 lockfile 이 바뀐다.
맥에서 실측했을 때 `"peer": true` 키 순서만 12줄 추가 / 20줄 삭제로 바뀌었다(실질 변화 없음).
**의도한 의존성 변경이 아니면 커밋하지 말고 `git checkout -- frontend/package-lock.json` 으로 되돌린다.**

### 3.9 파일명 대소문자 — 맥에서 통과한 게 OCI 에서 깨질 수 있다

맥 기본 파일시스템은 **대소문자를 구분하지 않는다**(실측 확인). 윈도우도 마찬가지다.
**OCI 는 리눅스라 구분한다.** import 경로나 파일명 대소문자 오타는 맥·윈도우에서는 멀쩡히 통과하고 OCI 배포에서만 깨진다.

### 3.10 줄바꿈

`.gitattributes` 가 `.py`/`.md`/`.sh`/`.json` 등은 **LF**, `.bat`/`.ps1` 은 **CRLF** 로 강제한다.
줄 수를 근거로 보고할 때는 항상 그 자리에서 실측한다 (DEV_RULES §11).

### 3.11 기동 스크립트를 이중으로 유지해야 한다

포트·경로·기동 순서를 바꾸면 `start.bat` · `stop.bat` · `start.sh` · `stop.sh` **4개를 함께 고친다.**
한쪽만 고치면 다른 기기에서 조용히 깨진다.

### 3.12 OCI 접속은 현재 PC 에서만 가능

맥의 공개키가 서버에 등록되기 전까지 OCI 정본 확인은 PC 에서만 된다 (§1.7).
OCI 접속은 **읽기 전용**이며 쓰기·발송·재시작은 금지다 (메모리 `project_oci_read_access_policy`).

### 3.13 git 흐름

- 작업 **시작 전 `git pull`**, 작업 **끝나면 커밋 후 push**.
- 한 기기에서 커밋하지 않은 채 다른 기기로 넘어가지 않는다.
- 특히 `docs/STATE_LATEST.md` 와 결과서는 양쪽에서 동시에 고치면 충돌한다. 한 번에 한 기기에서만 편집한다.
- 보고 직전 `git status --short --untracked-files=all` 로 staged = working tree 확인 (DEV_RULES §3-7).

---

## 4. PC 에서 맥으로 가져와야 할 것 (체크리스트)

맥에 없고 git 으로도 오지 않는 것들이다. PC 앞에 앉았을 때 한 번에 처리하면 좋다.

### 4.1 OCI SSH 접속 — 우선순위 1

이것만 뚫리면 4.2·4.3 은 맥에서 알아서 가져올 수 있다. **PC 에서 아래 한 줄을 실행한다.**

```bash
ssh oci-krx "mkdir -p ~/.ssh && chmod 700 ~/.ssh && echo 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIHKwfpC5JTmwWdupWd46ik0u5za0RW3LNNMWLb6DMBZv minandsoo44@gmail.com' >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"
```

맥 쪽 `~/.ssh/config` 의 `oci-krx` alias 는 이미 등록돼 있다 (§1.7). 등록 후 맥에서
`ssh oci-krx "echo ok"` 로 확인한다.

파일을 옮기는 방식(PC 의 `D:\AI\oci_ssh_key\id_rsa` 를 맥으로 복사)도 되지만,
개인키 사본을 늘리지 않는 위 방식이 낫다.

### 4.2 보유(holdings) 파일

맥에 `state/holdings/holdings_latest.json` 이 없어 보유 화면이 0건으로 보인다.
**OCI 정본에서 읽기 전용으로 가져오는 게 맞다** (4.1 완료 후):

```bash
mkdir -p state/holdings
scp oci-krx:/home/ubuntu/krx_hyungsoo/state/holdings/holdings_latest.json state/holdings/
```

PC 의 사본을 복사해도 되지만, 정본은 OCI 다. 가져온 뒤에는 §3.2 를 반드시 읽을 것 —
**오래된 맥 사본을 OCI 로 발행하면 실보유를 덮어쓴다.**

### 4.3 `.env` 나머지 값

`TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` 는 입력 완료. 남은 것:

| 키 | 용도 |
|---|---|
| `OCI_BACKEND_URL` | Phase 1 호환 — `daily_ops.sh` 가 사용 |
| `OCI_OPS_TOKEN` | 같음 |

둘 다 비밀값이라 PC `.env` 에서 옮겨야 한다. **읽기 확인 용도로는 없어도 된다.**

`OCI_SSH_TARGET` / `OCI_REMOTE_INBOX` / `OCI_REMOTE_OUTBOX` 는 저장소 문서에서 찾아 이미 채웠다.

### 4.4 장기 시장 시계열 (선택)

맥의 시장 DB 는 FDR 로 새로 받은 **약 4개월치**다 (§1.5). 장기 백테스트가 필요하면
PC 또는 OCI 의 `state/market/market_data.sqlite` 를 통째로 가져온다. 그전까지는
맥에서 백테스트·ML 산출물을 만들지 않는다 (§3.3 · §3.7).

### 4.5 반대로 — PC 에서 확인해야 할 것

| 항목 | 내용 |
|---|---|
| ETF 비교하기 카드 전환 | 2026-08-12 맥에서 작업. **사용자 실화면 확인 전 · `확인 필요` 탭 미전환.** 결과서 `docs/ai_result/POC3/POC3-WORKBENCH_GRID_CARD_CONVERSION_RESULT.md` |
| `tests/test_factor_signals.py` 2건 | POC3-08 종목코드 6자리 검증과 어긋나 실패. **PC 에서도 동일하게 실패**한다. 수정은 별도 지시 필요 |
| 맥/윈도우 폰트 차이 | §3 서두. 손대면 윈도우 화면도 같이 바뀐다 |
