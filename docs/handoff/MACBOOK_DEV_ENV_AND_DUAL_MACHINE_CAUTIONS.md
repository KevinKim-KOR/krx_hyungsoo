# 맥북 개발환경 구성 + 맥/PC 병행 작업 주의사항

작성: 2026-08-12 · 갱신: 2026-08-13 (OCI SSH 연결·보유 파일·시장 DB 정본 반영) (개발자)
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

- `.env` — 2026-08-13 사용자가 **PC `.env` 를 통째로 붙여넣어** 현재는 PC 현행과 같은 키 구성이다. 단 발송 스위치 4개는 맥에서 `false` 로 되돌렸다 (§3.5 의 경고를 반드시 읽을 것).
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

> **⚠ 2026-08-16 — 다른 프로젝트를 죽이던 문제 수정.** 3000(Next/React/Express) 과
> 8000(FastAPI/Django) 은 가장 흔한 개발 포트라, **포트 번호만 보고 종료하면 다른 프로젝트의
> 서버가 죽는다.** `./start.sh` 도 내부에서 stop 을 부르므로 기동만 해도 남의 것이 죽었다.
> 실제로 다른 프로젝트가 이쪽 백엔드(8000)를 종료시킨 사례가 발생했다.
>
> 이제 두 스크립트 모두 **주인 확인 후에만 종료**한다.
> - `stop.sh` — `lsof -a -p <pid> -d cwd` 로 작업 디렉터리가 이 프로젝트 밑인지 확인.
>   **확인 불가 시 죽이지 않는다.** 가짜 외부 프로세스로 실측 검증 완료.
> - `stop.bat` — (1) `start.bat` 이 붙인 창 제목(`POC1 Backend`/`POC1 Frontend`)으로 `taskkill /T`
>   (2) 남은 포트만 `ExecutablePath` 가 프로젝트 밑인지 검사. **PC 실행 검증 미완.**
>
> 반대로 **다른 프로젝트가 이쪽을 죽이는 것은 막을 수 없다.** 서버가 조용히 죽어 있으면
> 포트 점유를 먼저 확인한다:
> `lsof -i :3000 -i :8000 -sTCP:LISTEN -P -n`

### 1.5 시장 데이터 — 현재 OCI 정본 (2026-08-13 교체)

`state/market/market_data.sqlite` 는 gitignored 라 clone 에 포함되지 않는다. 두 가지 방법이 있고,
**현재 맥에는 OCI 정본이 들어가 있다.**

**(현행) OCI 정본 복사** — PC·OCI 와 같은 기준이 되므로 이쪽을 쓴다.

```bash
./stop.sh                       # 백엔드가 파일을 잡고 있으므로 먼저 내린다
scp oci-krx:/home/ubuntu/krx_hyungsoo/state/market/market_data.sqlite state/market/
./start.sh
```

| 항목 | 실측 (2026-08-13) |
|---|---|
| 파일 크기 | 131MB (복사 23초) |
| `etf_daily_price` | **1,344,177행** |
| 가격 기간 | **2014-04-09 ~ 2026-08-12 (약 12년)** |
| `etf_master` | 1,146 |
| 벤치마크 | 6,079행 (2014-04-08 ~ 2026-07-03) |

**(대안) FDR 로 새로 적재** — OCI 접속이 없을 때. 백엔드 기동 후 `POST /market/refresh`
(UI 의 시장 갱신 버튼과 같은 경로). 소요 68초 / ETF 1,163종 / `etf_daily_price` 92,123행 /
실패 0건. 단 **가격 이력이 약 4개월(2026-04-14~)뿐**이라 장기 계산에는 쓸 수 없다.
6시간 cooldown 가드가 있어 연속 재실행은 막힌다.

> 이력이 짧으면 1M·3M·6M·1Y 수익률이 **전부 같은 값**이 된다. 조회 시작일이 데이터 시작일로
> 눌리기 때문이다. 신규 상장 종목은 정본에서도 같은 현상이 나므로, 값이 같다고 바로
> 버그로 보지 말고 응답의 `basis_start_date` 를 먼저 확인한다.

### 1.6 git

`user.name = KevinKim-KOR` / `user.email = minandsoo44@gmail.com` (global).

### 1.7 OCI — 연결 완료 (2026-08-13)

`~/.ssh/config` 에 alias 추가 완료 (기존 파일은 `~/.ssh/config.bak` 백업).

```
Host oci-krx
  HostName 152.67.211.223
  User ubuntu
  IdentityFile ~/.ssh/id_ed25519
  IdentitiesOnly yes
```

맥 공개키(`SHA256:GxdOTPIYacMJS1CA2wdwZrSNWz19VbiAbP6FzEZGbAA`)를 PC 에서 서버
`authorized_keys` 에 등록해 **`ssh oci-krx` 접속 성공**.

키 판별 주의 — 맥 키는 `ssh-ed25519`, PC 키는 파일명이 `id_rsa` 라 `ssh-rsa` 계열이다.
주석은 양쪽 다 같은 이메일일 수 있으므로 **지문이나 키 종류로 구분**한다.
등록 확인은 `ssh oci-krx "ssh-keygen -lf ~/.ssh/authorized_keys"`.

**접속은 읽기 전용으로만 쓴다** — `ls` / `cat` / `scp` 받기까지. 쓰기·발송·재시작 금지
(메모리 `project_oci_read_access_policy`).

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

실측 (2026-08-16 · 시장 DB 를 OCI 정본으로 교체한 뒤 측정):
tsc 0 · eslint 0 · vitest **160 passed (14 files)** · pytest **1139 passed · 실패 0건**.
black/flake8 은 2026-08-12 기준 276 files unchanged · 0.

> **상시 실패 0건이 정상 상태다.** 하나라도 빨간불이 뜨면 그 자리에서 원인을 본다
> (§3.6 — 이전에 2건이 상시 실패로 방치돼 새 실패를 가릴 뻔했다).

---

## 3. 맥 ↔ PC 병행 작업 주의사항

### 3.1 git 에 안 들어가는 것 = 양쪽이 서로 다르다

`.env` · `frontend/.env.local` · `.venv` · `frontend/node_modules` · `state/` 전부 gitignored 다.
**`git pull` 로 동기화되지 않는다.** 한쪽에서 환경변수를 추가하면 다른 쪽에 수동 반영해야 한다.
유일한 동기화 통로는 `.env.example` 이므로, 새 환경변수를 도입하면 반드시 거기에 변수명을 추가한다.

### 3.2 ⚠️ 최우선 — 보유(holdings) 데이터 사고 위험

- 정본은 **OCI** 에 있다. PC 와 맥의 `state/holdings/holdings_latest.json` 은 각자의 로컬 사본이다.
- 맥에는 2026-08-13 에 OCI 정본을 복사해 넣었다 (**32종목** — 일반 12 / ISA 13 / 오픈뱅킹 7).
  **이 사본은 시간이 지나면 낡는다.** 맥에서 발행하기 전에 정본이 그 사이 바뀌지 않았는지 먼저 확인한다.

```bash
scp oci-krx:/home/ubuntu/krx_hyungsoo/state/holdings/holdings_latest.json state/holdings/
```
- **맥의 비어 있는/부분적인 holdings 를 OCI 로 올리면 실보유 32종목을 덮어쓴다.** POC3-08 에서 실제로 33건 → 1건으로 덮어쓴 사고가 있었고 OCI 정본에서 복구했다.
- 맥에서 `PUT /holdings` 계열 쓰기를 실행하기 전에, 그 결과가 OCI 로 전파되는 경로인지 반드시 확인한다.

### 3.3 시장 데이터 이력 길이 — 2026-08-13 정본으로 통일됨 (재발 주의)

맥의 DB 를 OCI 정본으로 교체해(§1.5) 현재는 **양쪽이 같은 기준**이다. 백테스트·ML 수치를
섞어 봐도 된다.

다만 **맥에서 `POST /market/refresh` 를 누르면 이 상태가 깨질 수 있다.** 그 경로는 FDR 로
최근 구간만 갱신하므로, 정본 DB 위에 덮어쓰는 게 아니라면 문제없지만 새 DB 를 만드는
상황(파일 삭제 후 재생성 등)에서는 다시 4개월치로 돌아간다.

→ 수치를 비교하기 전에 **양쪽 DB 의 기간이 같은지 먼저 확인한다.**

```bash
.venv/bin/python -c "import sqlite3;c=sqlite3.connect('state/market/market_data.sqlite');print(c.execute('select min(date),max(date),count(*) from etf_daily_price').fetchone())"
```

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

이 4개 플래그는 실제 텔레그램 발송을 여는 스위치다. 테스트 실행 시에만 명령 앞에 붙인다 (§2 참조).
참고로 이 4개는 `.env.example` 과 `docs/KILL_SWITCHES.md` 어디에도 등재돼 있지 않다.

> **⚠ 2026-08-13 사고 근접 사례** — PC `.env` 를 맥에 통째로 붙여넣으면서 이 4개가
> `true` 로 들어왔다. 토큰도 함께 채워져 있어, 그 상태로 `scripts/run_three_push_*_oci.py` 를
> 실행했다면 **맥의 데이터로 실제 텔레그램이 발송될 뻔했다.** 사용자 지시로 맥은 전부
> `false` 로 되돌렸다.
>
> **`.env` 를 기기 간에 통째로 복사하지 말 것.** 필요한 키만 옮기고, 옮긴 뒤에는
> `grep -E "^PUSH_AUTOSEND" .env` 로 발송 스위치 상태를 반드시 확인한다.
> **PC 는 `true` 가 정상**(실제 운영 주체)이고 **맥은 `false` 가 정상**이다.
>
> 같은 복사로 `OCI_REMOTE_INBOX` / `OCI_REMOTE_OUTBOX` / `OCI_BACKEND_URL` /
> `OCI_OPS_TOKEN` 이 사라지고 `THREE_PUSH_REMOTE_PACKAGE_DIR` 이 들어왔다.
> PC 도 그 4개 없이 운영 중이라 PC 현행에 맞춰 그대로 두었다.

### 3.6 기존 실패 2건 (양쪽 공통) — 2026-08-16 해소

`tests/test_factor_signals.py` 2건이 `KeyError: 'message_text'` 로 실패한다.
티커를 `AAA`/`BBB`/`CCC` 로 넣는데 **POC3-08 (A) 의 종목코드 6자리 검증**이 이를 막는다.

```
PUT /holdings status = 422
{'detail': "holdings[0].ticker 형식 오류 — 종목코드는 영숫자 6자리여야 합니다 (received: 'AAA')"}
```

환경 의존이 없는 순수 계약 불일치라 **PC 에서도 동일하게 실패한다.**
POC3-08 때 백엔드는 focused 41건만 돌려서 잡히지 않은 것으로 보인다.

**2026-08-16 해소** — 검증을 그대로 둔 채 fixture 티커를 실제 형식(`069500`/`360750`/
`379810`, 시세 미확인 fallback 테스트는 `999999`)으로 교체했다. 백엔드 전체
**1139 passed · 실패 0건**. 상시 실패가 없어야 새 실패가 즉시 드러난다.

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

## 4. 기기 간에 옮겨야 하는 것 (체크리스트)

git 으로 오지 않는 것들이다. **2026-08-13 기준 1~4 는 모두 해소**됐고, 아래는
재설치·재구성 때 다시 쓰기 위한 절차로 남긴다.

### 4.1 OCI SSH 접속 — 우선순위 1 ✅ 완료

이것만 뚫리면 4.2·4.4 는 맥에서 알아서 가져올 수 있다. **PC 에서 아래 한 줄을 실행한다.**

```bash
ssh oci-krx "mkdir -p ~/.ssh && chmod 700 ~/.ssh && echo '<맥 공개키 한 줄>' >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"
```

- `>>` 는 반드시 두 개. `>` 하나로 쓰면 PC 키가 지워져 **PC 에서도 접속이 끊긴다.**
- 맥 공개키는 `cat ~/.ssh/id_ed25519.pub` 로 얻는다.
- 확인: `ssh oci-krx "ssh-keygen -lf ~/.ssh/authorized_keys"` 에 맥 키 지문이 보이면 성공.
- 개인키 파일을 옮기는 방식보다 이쪽이 낫다 (사본을 늘리지 않는다).

### 4.2 보유(holdings) 파일 ✅ 완료 (32종목)

정본은 OCI 다. PC 사본을 복사하지 말고 OCI 에서 직접 받는다.

```bash
mkdir -p state/holdings
scp oci-krx:/home/ubuntu/krx_hyungsoo/state/holdings/holdings_latest.json state/holdings/
```

가져온 뒤 §3.2 를 반드시 읽을 것 — **낡은 사본을 OCI 로 발행하면 실보유를 덮어쓴다.**

### 4.3 `.env` ✅ 완료 (단 §3.5 경고 참조)

**통째로 복사하지 말 것.** 필요한 키만 옮기고, 옮긴 뒤 발송 스위치 상태를 확인한다.

```bash
grep -E "^PUSH_AUTOSEND" .env      # 맥은 전부 false 가 정상
```

### 4.4 시장 시계열 ✅ 완료 (OCI 정본 12년)

절차와 실측값은 §1.5 참조. 백엔드를 내리고 복사한 뒤 다시 올린다.

### 4.5 반대로 — PC 에서 확인해야 할 것

| 항목 | 내용 |
|---|---|
| ETF 비교하기 카드 전환 | 2026-08-12~13 맥에서 작업. 1차 화면 확인 후 지적 4건 반영 완료. **`확인 필요` 탭 미전환 · 보유 탭 배지 정리 미결.** 결과서 `docs/ai_result/POC3/POC3-WORKBENCH_GRID_CARD_CONVERSION_RESULT.md` |
| **`stop.bat` 주인 확인 가드** | 2026-08-16 추가. **맥에서 작성해 PC 실행 검증을 못 했다.** PC 에서 `stop.bat` 1회 실행해 백엔드·프론트가 정상 종료되는지 확인 필요. 프론트가 안 죽으면 알려줄 것 |
| 확인 근거 카드 전환 | 2026-08-16 완료·실화면 확인 완료. 결과서 `docs/ai_result/POC3/POC3-EVIDENCE_GRID_AND_STOP_GUARD_RESULT.md` |
| PC `.env` 발송 스위치 | 맥은 `false` 로 되돌렸다. **PC 는 `true` 가 정상**이므로 실수로 따라 끄지 말 것 (§3.5) |
| `tests/test_factor_signals.py` 2건 | POC3-08 종목코드 6자리 검증과 어긋나 실패. **PC 에서도 동일하게 실패**한다. 수정은 별도 지시 필요 |
| 맥/윈도우 폰트 차이 | §3 서두. 손대면 윈도우 화면도 같이 바뀐다 |
