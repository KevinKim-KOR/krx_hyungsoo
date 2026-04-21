# MongoDB 운영 가이드 (Atlas → VM 자체 호스팅)

> 2026-04-10, Atlas 무료 티어에서 오라클 VM 자체 호스팅으로 이전했습니다.
> 이 문서는 **이전 방식과 달라진 점**과 **일상 작업에서 해야 할 것**을 정리합니다.

---

## 0. 한눈에 보는 변화

| 항목 | 이전 (Atlas 무료티어) | 이후 (VM 자체 호스팅) |
|---|---|---|
| 호스팅 | MongoDB Atlas 클라우드 | 오라클 VM (134.185.109.82) docker 컨테이너 |
| 연결 방식 | `mongodb+srv://...@cluster.m3jtdwa.mongodb.net` 직접 | 로컬은 **SSH 터널** 경유 (`localhost:27017`) |
| 환경변수 | `MONGO_DB_CONNECTION_STRING` 단일 값 | `MONGO_DB_USER/PASSWORD/HOST/NAME` 부품 조립 |
| VM 내부 앱 | - | `fastapi_app`/`node_app` → `mongodb:27017` (docker network) |
| 외부 포트 노출 | Atlas 네트워크(IP whitelist) | **없음** — 27017 은 VM 내부 `127.0.0.1` 만 바인딩 |
| 인증 | Atlas 계정 | 로컬 admin + app 전용 유저 `jasonisdoing` |
| 운영 비용 | 무료(512MB 한도, 일시 차단 발생) | VM 비용에 포함 (디스크는 VM 용량) |

---

## 1. 아키텍처

```
[로컬 맥북]
  ├─ .env: MONGO_DB_HOST=localhost:27017
  ├─ python/node 앱 → localhost:27017
  │          │
  │          ↓ (SSH 터널: autossh -L 27017:localhost:27017)
  ▼
[오라클 VM 134.185.109.82]
  ├─ ssh :22 (인증: ~/DEV/ssh-key-2025-10-09.key)
  │
  └─ docker compose (프로젝트 경로: /home/ubuntu/apps/momentum-etf)
      ├─ mongodb:7.0
      │     포트 바인딩: 127.0.0.1:27017  (VM 외부 차단)
      │     볼륨:        ./mongo-data:/data/db
      │     init:        ./infra/mongo-init/01-create-app-user.sh
      ├─ fastapi_app  →  mongodb:27017 (docker network)
      ├─ node_app     →  mongodb:27017 (docker network)
      └─ hybrid_proxy / nginx-proxy / acme
```

**핵심**:
- **27017 포트는 VM 외부에 노출되지 않음**. 오라클 시큐리티리스트 변경 불필요.
- 로컬 접속은 오직 **SSH 터널**로만 가능. SSH 키가 있어야 DB 에 접근 가능 → 2중 보안.

---

## 2. 환경변수 (`.env`) 변경

### 이전
```bash
MONGO_DB_CONNECTION_STRING="mongodb+srv://jasonisdoing:xxxx@cluster.m3jtdwa.mongodb.net/?retryWrites=true&w=majority&appName=Cluster"
```

### 이후 (부품 조립 방식)
```bash
# (롤백용 보존, 주석 처리)
# [migrated to VM mongodb via SSH tunnel] MONGO_DB_CONNECTION_STRING="mongodb+srv://..."

# --- MongoDB (VM 자체 호스팅) ---
MONGO_DB_USER=jasonisdoing
MONGO_DB_PASSWORD=RExDR4cyIAsmtz
MONGO_DB_HOST=localhost:27017      # 로컬 .env 값
# MONGO_DB_HOST=mongodb:27017      # VM .env 값 (docker network 내부)
MONGO_DB_NAME=momentum_etf_db

# (VM .env 에만) admin 계정 — mongodb 컨테이너 최초 기동 시만 사용
MONGO_DB_ROOT_USER=root
MONGO_DB_ROOT_PASSWORD=<랜덤 32자>
```

### 코드 로직 (하위호환)
`utils/db_manager.py` 와 `web/lib/mongo.ts` 는 아래 순서로 접속 문자열을 결정합니다:

1. `MONGO_DB_CONNECTION_STRING` 이 설정되어 있으면 **그대로 사용** (롤백 용이)
2. 없으면 `MONGO_DB_USER` / `MONGO_DB_PASSWORD` / `MONGO_DB_HOST` 로 조립
3. 호스트가 `*.mongodb.net` 으로 끝나면 자동으로 `mongodb+srv://`, 아니면 `mongodb://`
4. 옵션은 `MONGO_DB_OPTIONS` 로 덮어쓸 수 있음. 기본값:
   - Atlas: `retryWrites=true&w=majority`
   - VM: `authSource=admin&retryWrites=true&w=majority`

---

## 3. 일상 작업에서 해야 하는 것

### A. 처음 셋업 (한 번만)

```bash
brew install autossh
```

### B. 매 부팅/개발 시작 시 (한 번씩)

**SSH 터널을 먼저 띄운다.**

```bash
autossh -M 0 -N -i ~/DEV/ssh-key-2025-10-09.key \
  -o "ServerAliveInterval=30" -o "ServerAliveCountMax=3" \
  -L 27017:localhost:27017 ubuntu@134.185.109.82
```

- `-f` : 백그라운드 실행 (터미널 닫아도 유지)
- `-N` : 명령 실행 없이 터널만
- `ServerAlive*` : 네트워크 일시 단절 시 자동 감지 및 재연결

**확인**:
```bash
pgrep -lf autossh                       # 실행 중인 프로세스 확인
nc -zv localhost 27017 2>&1 | head -1   # 포트 응답 확인
```

**종료**:
```bash
pkill -f "autossh.*27017"
```

> 대체 방안: `scripts/mongo-tunnel.sh` (autossh 없이 일반 ssh, 포그라운드 실행)

### C. 평소처럼 앱/스크립트 실행

터널만 열려 있으면 **이전과 완전히 동일**합니다.

```bash
cd ~/DEV/momentum-etf

# 스크립트
python scripts/stock_meta_cache_updater.py
python scripts/stock_price_cache_updater.py

# FastAPI
uvicorn fastapi_app.main:app --reload

# Next.js
cd web && npm run dev
```

### D. 터널이 죽었을 때 증상

앱/스크립트에서 아래와 같은 에러가 나오면 터널이 끊어진 것:
```
MongoServerSelectionError: connect ECONNREFUSED 127.0.0.1:27017
ServerSelectionTimeoutError: localhost:27017: [Errno 61] Connection refused
```

→ 위 `autossh` 명령을 다시 실행.

---

## 4. VM 내부 운영 (SSH 로 VM 에 직접 들어갔을 때)

```bash
ssh -i ~/DEV/ssh-key-2025-10-09.key ubuntu@134.185.109.82
cd /home/ubuntu/apps/momentum-etf
```

### 컨테이너 상태 확인
```bash
docker compose ps
docker compose logs -f mongodb       # MongoDB 로그
docker compose logs -f fastapi_app   # 앱 로그
```

### MongoDB 재시작 (설정 변경 후)
```bash
docker compose restart mongodb
# ⚠️ 재시작 후 로컬 SSH 터널도 끊어질 수 있으니 터널 재연결 확인
```

### 앱 재빌드/재기동 (코드/compose 변경 후)
```bash
docker compose up -d --build fastapi_app node_app
```

### MongoDB 데이터 위치
- **호스트**: `/home/ubuntu/apps/momentum-etf/mongo-data/` (바인드 마운트)
- 이 디렉토리를 삭제하면 DB 가 **초기화**됨 (주의!)
- 백업: `tar czf mongo-data-$(date +%F).tar.gz mongo-data/` (컨테이너 정지 후 권장)

### mongosh 접속 (VM 내부에서)
```bash
docker compose exec mongodb mongosh \
  -u root -p "<MONGO_DB_ROOT_PASSWORD>" --authenticationDatabase admin
```

또는 앱 유저로:
```bash
docker compose exec mongodb mongosh \
  -u jasonisdoing -p "<MONGO_DB_PASSWORD>" --authenticationDatabase admin momentum_etf_db
```

---

## 5. 백업 / 복원

### 현재 보유 백업
- **Atlas 최종 스냅샷**: `.backups/atlas_20260410_140758/` (로컬, gzip BSON, 약 18MB)
- 36개 컬렉션 / 1,464 문서 무결성 검증 완료

### 특정 컬렉션만 복원 (로컬에서, SSH 터널 필요)
```bash
mongorestore \
  --uri='mongodb://jasonisdoing:RExDR4cyIAsmtz@localhost:27017/?authSource=admin' \
  --nsInclude='momentum_etf_db.<컬렉션명>' \
  --gzip .backups/atlas_20260410_140758
```

예:
```bash
--nsInclude='momentum_etf_db.portfolio_master'
--nsInclude='momentum_etf_db.account_targets'
--nsInclude='momentum_etf_db.stock_meta'
```

### 복원한 핵심 컬렉션 (2026-04-10)
| 컬렉션 | 건수 | 용도 |
|---|---|---|
| portfolio_master | 1 | 계좌 보유 종목 마스터 |
| account_targets | 46 | 계좌별 목표 비중 |
| account_notes | 5 | 계좌 메모 |
| stock_meta | 242 | 종목 메타 (이름/버킷) |
| system_config | 1 | 시스템 설정 |
| daily_snapshots | 26 | 일일 스냅샷 |

### 전체 백업 (수동)
VM 에서 현재 DB 를 통째로 덤프:
```bash
docker compose exec -T mongodb mongodump \
  --uri="mongodb://root:${MONGO_DB_ROOT_PASSWORD}@localhost:27017/?authSource=admin" \
  --db=momentum_etf_db --gzip --archive > backup-$(date +%F).archive.gz
```

복원:
```bash
docker compose exec -T mongodb mongorestore \
  --uri="mongodb://root:${MONGO_DB_ROOT_PASSWORD}@localhost:27017/?authSource=admin" \
  --gzip --archive < backup-YYYY-MM-DD.archive.gz
```

---

## 6. 롤백 (Atlas 로 되돌리기)

만약 VM MongoDB 에 문제가 생겨 즉시 Atlas 로 돌려야 할 경우:

1. 로컬/VM `.env` 에서 아래 줄의 주석 `#` 을 제거:
   ```
   # [migrated ...] MONGO_DB_CONNECTION_STRING="mongodb+srv://..."
   ```
2. 새 부품 변수(`MONGO_DB_USER/PASSWORD/HOST`) 는 주석 처리하거나 삭제
   - (남겨 둬도 무방 — 코드가 `CONNECTION_STRING` 을 우선 사용)
3. 앱 재시작
   ```bash
   # 로컬
   # (그냥 재실행)
   # VM
   docker compose restart fastapi_app node_app
   ```

Atlas 는 유지 중이며 데이터는 마지막 dump 시점 그대로 있습니다.

---

## 7. 자주 생기는 문제

### (1) "connect ECONNREFUSED 127.0.0.1:27017"
- SSH 터널이 끊어졌거나 안 띄운 상태.
- `pgrep -lf autossh` 확인 → 없으면 섹션 3-B 의 autossh 명령 재실행.

### (2) "Authentication failed"
- 비밀번호 오타 또는 `authSource=admin` 누락.
- VM mongodb 컨테이너를 완전히 재생성했는데 기존 `mongo-data/` 가 남아있으면,
  init 스크립트는 실행되지 않고 예전 유저가 그대로 유지됨.

### (3) 로컬 27017 포트 충돌
```
bind: Address already in use
```
- 다른 mongodb 인스턴스나 이전 터널이 떠 있음.
- `lsof -iTCP:27017 -sTCP:LISTEN` 로 확인 후 kill.

### (4) VM mongo-data 가 날아갔을 때
- 컨테이너가 `mongo-data/` 디렉토리를 초기 생성하면 **init 스크립트가 다시 실행되어 admin/app 유저도 재생성**됨.
- `.env` 에 있는 `MONGO_DB_ROOT_PASSWORD`, `MONGO_DB_PASSWORD` 가 변경되지 않았다면 복구 후 바로 사용 가능.
- 데이터는 마지막 백업(`.backups/atlas_20260410_140758/`) 또는 직전 수동 백업에서 복원 필요.

### (5) 컨테이너 재생성 후 `init` 이 실행 안 됨
- `docker-entrypoint-initdb.d` 의 스크립트는 **`mongo-data/` 가 비어있을 때만** 실행됩니다.
- 기존 데이터가 있으면 스크립트는 스킵되고 기존 유저/권한이 그대로 유지됩니다.
- 유저를 다시 만들려면 mongosh 로 직접 `db.createUser(...)` 실행.

---

## 8. 관련 파일

| 경로 | 설명 |
|---|---|
| `utils/db_manager.py` | Python MongoDB 연결 (부품 조립 로직) |
| `web/lib/mongo.ts` | Next.js MongoDB 연결 (부품 조립 로직) |
| `docker-compose.yml` | mongodb 서비스 정의, 포트/볼륨/init |
| `infra/mongo-init/01-create-app-user.sh` | 최초 기동 시 app 유저 자동 생성 |
| `scripts/mongo-tunnel.sh` | SSH 터널 헬퍼 (autossh 대체용) |
| `.backups/atlas_20260410_140758/` | Atlas 최종 백업 (gzip BSON) |
| `.env` | 로컬 환경변수 (HOST=localhost:27017) |
| `.env` (VM) | VM 환경변수 (HOST=mongodb:27017 + ROOT 계정) |
| `mongo-data/` | VM 에만 존재. MongoDB 실 데이터 디렉토리 (gitignore) |

---

## 9. 보안 체크리스트

- [x] 27017 포트는 VM 외부에 노출되지 않음 (127.0.0.1 바인딩)
- [x] MongoDB 인증 활성화 (root + app 유저 분리)
- [x] SSH 키 기반 접근 (비밀번호 로그인 불가)
- [x] `mongo-data/`, `.backups/`, `.env*` 모두 `.gitignore` 처리
- [x] Atlas URI 는 주석 처리하여 평문 저장 (롤백용, 별도 파일 아님)
- [ ] **주기적 백업 자동화** — TODO: cron 등으로 주 1회 mongodump 권장
- [ ] **VM 디스크 모니터링** — TODO: `mongo-data/` 크기 추적

---

## 10. 컬렉션 복원 현황 (2026-04-10 기준)

Atlas 백업에는 **37개** 컬렉션이 있었고, VM 으로는 **지연 복원(lazy restore)** 방식으로 필요한 것만 가져왔습니다. 이 섹션은 "무엇을 복원했고, 무엇을 안 했으며, 왜 그런지"를 기록합니다.

복원 원본: `.backups/atlas_20260410_140758/momentum_etf_db/`

### 10.1. 복원한 컬렉션 (15개, 앱에서 실제 사용)

| 컬렉션 | 문서 수 | 용도 |
|---|---|---|
| `account_notes` | 5 | 계정별 메모 |
| `account_targets` | 46 | 계정 목표/설정 |
| `backtest_configs` | 8 | 백테스트 설정 |
| `cache_aus_stocks` | 90 | 호주 종목 캐시 |
| `cache_fx_stocks` | 1 | 환율 캐시 |
| `cache_kor_kr_stocks` | 79 | 한국 종목 캐시 |
| `cache_kor_us_stocks` | 73 | 미국 종목 캐시 |
| `cache_refresh_status` | 3 | 캐시 갱신 상태 |
| `daily_snapshots` | 26 | 일일 스냅샷 |
| `etf_market_master` | 1 | ETF 마스터 |
| `portfolio_master` | 1 | 포트폴리오 마스터 |
| `stock_cache_meta` | 152 | 종목 캐시 메타 |
| `stock_meta` | 242 | 종목 메타데이터 |
| `system_config` | 1 | 시스템 설정 |
| `weekly_fund_data` | 76 | 주간 펀드 데이터 |

> 복원 명령 예시 (반드시 `--drop` 포함):
> ```bash
> mongorestore \
>   --uri="mongodb://jasonisdoing:${MONGO_DB_PASSWORD}@localhost:27017/?authSource=admin" \
>   --gzip --drop \
>   --nsInclude="momentum_etf_db.<컬렉션명>" \
>   .backups/atlas_20260410_140758
> ```
> `--drop` 없이 복원하면 기존 문서 위에 덧씌워져 **중복**이 생깁니다. (실제로 `weekly_fund_data` 에서 이번 주 데이터가 두 개 생겨 재복원한 사례 있음)

### 10.2. 복원하지 않은 컬렉션 (22개)

#### (A) 명시적 백업 스냅샷 — 복원 불필요 (7개)

과거 수동 백업 시점의 복사본. 운영 데이터가 아니므로 복원하지 않습니다.

- `daily_snapshots_backup`
- `daily_snapshots_backup_20260404_094122`
- `daily_snapshots_backup_20260404_094303`
- `daily_snapshots_backup_non_trading_20260404_122831`
- `portfolio_master_backup`
- `weekly_fund_data_backup_20260329_195900`
- `weekly_fund_data_backup_20260331_150958`

#### (B) 런타임에 자동 재생성되는 캐시 (9개)

캐시 워커/스크립트가 실행되면 다시 채워집니다. Atlas 에서의 스냅샷을 굳이 옮길 필요 없음.

- `cache_aus_account_stocks`
- `cache_core_account_stocks`
- `cache_isa_account_stocks`
- `cache_kor_account_stocks`
- `cache_pension_account_stocks`
- `cache_kor_etf_stocks`
- `cache_kor_isa_stocks`
- `cache_kor_pension_stocks`
- `cache_us_stocks`

#### (C) 테스트/디버그용 (2개)

- `cache_test_stocks`
- `cache_tmp_debug_stocks`

#### (D) 구버전 잔재 — 현재 코드에서 **전혀 참조되지 않음** (4개)

프로젝트 전체(Python + TypeScript + 스크립트)를 grep 했을 때 참조 0건. 리팩토링 과정에서 제거되었지만 Atlas 에는 남아있던 컬렉션입니다. 복원 불필요.

- `balance_stats` — 잔고 통계 (미사용)
- `pool_rankings` — 종목풀 순위 스냅샷 (미사용)
- `stock_recommendations` — 종목 추천 (미사용)

> 참고: 이 네 개는 **앞으로 정리 대상**입니다. 백업에만 존재하고 VM 에는 복원되지 않았으므로, 다음 Atlas 백업을 보관하지 않기로 하면 자연스럽게 사라집니다.

### 10.3. 추가 복원이 필요해질 때

특정 페이지/스크립트에서 "컬렉션이 없다"는 에러가 나면 그때만 복원합니다. 절차:

1. 에러 로그에서 컬렉션 이름 확인
2. `ls .backups/atlas_20260410_140758/momentum_etf_db/ | grep <이름>` 으로 백업 존재 확인
3. 위 10.1 의 `mongorestore` 예시 명령으로 `--drop` 포함 복원
4. 이 문서 10.1 표에 한 줄 추가
