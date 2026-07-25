# OCI Low-Frequency Telegram Push Operation v1 — Crontab 초안 + 실측 명령셋

작성일: 2026-07-25
Step: `LOW_FREQUENCY_TELEGRAM_PUSH_OPERATION_V1`
상태: **DRAFT (사용자 실측 대기)** — crontab 미적용 · commit/push 미승인
선행 문서: [`OCI_THREE_PUSH_CRONTAB_TEMPLATE.md`](OCI_THREE_PUSH_CRONTAB_TEMPLATE.md)

---

## 0. 목적과 범위

이 문서는 **Low-Frequency Telegram Push Operation v1** 의 최종 crontab 초안과
사용자가 OCI 에서 한 번에 실행할 실측 명령셋을 제시한다.

- 기존 3-PUSH 하루 3회 (Market 1 / Holdings 1 / Spike 1) 배선을 대체한다.
- 신규 배선: **Market 1회 + Holdings 3슬롯 + Spike 7회 (총 11 tick/일)**.
- Holdings 는 슬롯별 (OPEN/MIDDAY/CLOSE) 로 registry key 가 분리되어 하루 3회 발송 허용.
- Spike 는 signal fingerprint (`ticker#trigger#direction`) 기준으로 중복 차단. Registry key 는 `date` 를 접두 (`{date}#{ticker}#{trigger}#{direction}`) — fingerprint 본문 자체에는 date 없음.
- Runtime 가격은 `market_naver.fetch_many` 로 조회하며 `holdings_latest.json` 은 수정하지 않는다.

**이 문서만으로 crontab 을 적용하지 않는다.** 검증자 검증자 판정 이후 사용자
승인하에 §3 실측 명령셋을 실행한다.

---

## 1. 전제 조건

`OCI_THREE_PUSH_CRONTAB_TEMPLATE.md §1` 과 동일한 PARAM/venv 조건에 추가로:

- `state/holdings/holdings_latest.json` 존재 (Holdings 슬롯).
- `state/universe/universe_momentum_latest.json` 존재 + `price_history_basis.base_close` 실측치 포함 (Spike 재평가).
- Naver 조회 가능 (외부 네트워크). **가격 조회 실패는 no_signal 이 아니라 `failed` 로 종료되며 미발송·registry 미기록** — §5 계약 준수.

---

## 2. 신규 crontab (초안 · 미적용)

`crontab -e` 로 편집할 최종 형태. UTC 시각은 KST 기준을 UTC 로 환산한 값이다.
OCI 서버는 UTC 로 가정한다 (`date +%Z` 로 확인 필요).

```crontab
# ─── Low-Frequency Telegram Push Operation v1 (KST 기준, UTC 로 환산) ────
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

# ── PUSH-1: Market 브리핑 — 평일 08:00 KST = 전날 23:00 UTC (요일 0-4 UTC = 일~목)
00 23 * * 0-4 cd /home/ubuntu/krx_hyungsoo && venv/bin/python scripts/run_three_push_runtime_oci.py --push-kind market_briefing --mode send >> logs/low_freq_push_cron.log 2>&1

# ── PUSH-2: Holdings 브리핑 3 슬롯 (평일 KST) ─────────────────────────────
# OPEN   09:15 KST = 00:15 UTC (요일 1-5 UTC = 월~금)
15 00 * * 1-5 cd /home/ubuntu/krx_hyungsoo && venv/bin/python scripts/run_three_push_runtime_oci.py --push-kind holdings_briefing --mode send --slot-id OPEN   >> logs/low_freq_push_cron.log 2>&1
# MIDDAY 12:30 KST = 03:30 UTC
30 03 * * 1-5 cd /home/ubuntu/krx_hyungsoo && venv/bin/python scripts/run_three_push_runtime_oci.py --push-kind holdings_briefing --mode send --slot-id MIDDAY >> logs/low_freq_push_cron.log 2>&1
# CLOSE  15:40 KST = 06:40 UTC
40 06 * * 1-5 cd /home/ubuntu/krx_hyungsoo && venv/bin/python scripts/run_three_push_runtime_oci.py --push-kind holdings_briefing --mode send --slot-id CLOSE  >> logs/low_freq_push_cron.log 2>&1

# ── PUSH-3: Spike/Falling 알림 7 tick (평일 KST) ─────────────────────────
# 09:30 KST = 00:30 UTC
30 00 * * 1-5 cd /home/ubuntu/krx_hyungsoo && venv/bin/python scripts/run_three_push_runtime_oci.py --push-kind spike_or_falling_alert --mode send >> logs/low_freq_push_cron.log 2>&1
# 10:30 KST = 01:30 UTC
30 01 * * 1-5 cd /home/ubuntu/krx_hyungsoo && venv/bin/python scripts/run_three_push_runtime_oci.py --push-kind spike_or_falling_alert --mode send >> logs/low_freq_push_cron.log 2>&1
# 11:30 KST = 02:30 UTC
30 02 * * 1-5 cd /home/ubuntu/krx_hyungsoo && venv/bin/python scripts/run_three_push_runtime_oci.py --push-kind spike_or_falling_alert --mode send >> logs/low_freq_push_cron.log 2>&1
# 12:30 KST = 03:30 UTC  (Holdings MIDDAY 와 동시 tick — 각각 독립 실행)
30 03 * * 1-5 cd /home/ubuntu/krx_hyungsoo && venv/bin/python scripts/run_three_push_runtime_oci.py --push-kind spike_or_falling_alert --mode send >> logs/low_freq_push_cron.log 2>&1
# 13:30 KST = 04:30 UTC
30 04 * * 1-5 cd /home/ubuntu/krx_hyungsoo && venv/bin/python scripts/run_three_push_runtime_oci.py --push-kind spike_or_falling_alert --mode send >> logs/low_freq_push_cron.log 2>&1
# 14:30 KST = 05:30 UTC
30 05 * * 1-5 cd /home/ubuntu/krx_hyungsoo && venv/bin/python scripts/run_three_push_runtime_oci.py --push-kind spike_or_falling_alert --mode send >> logs/low_freq_push_cron.log 2>&1
# 15:20 KST = 06:20 UTC
20 06 * * 1-5 cd /home/ubuntu/krx_hyungsoo && venv/bin/python scripts/run_three_push_runtime_oci.py --push-kind spike_or_falling_alert --mode send >> logs/low_freq_push_cron.log 2>&1
```

주요 규칙:
- **PATH 보강**: crontab 은 로그인 shell PATH 를 상속하지 않는다.
- **secret**: `.env` 자동 로드 (기존 규칙 유지). token/chat_id 를 crontab 에 inline 금지.
- **로그**: `logs/low_freq_push_cron.log` 단일 파일. 기존 `three_push_runtime_cron.log` 와 분리하여 이번 Step 관측 용이.
- **param_id 미고정**: `--push-kind` 만 지정. latest PARAM snapshot 을 사용한다.
- **Holdings MIDDAY 와 Spike 12:30**: 같은 UTC 03:30 tick. cron 은 두 job 을 **동시에 fork** 하며 실행 순서를 보장하지 않는다. 두 프로세스는 서로 다른 registry key 를 사용하므로 상호 독립적으로 완료된다.
- **Spike 12:30**: 원 지시문 및 보완 지시문 모두에 7 tick (09:30/10:30/11:30/12:30/13:30/14:30/15:20) 로 명시되어 있어 그대로 반영. Holdings MIDDAY 와 동시각이나 두 job 은 다른 registry key 를 사용해 독립적으로 완료된다.

---

## 3. 사용자 실측 명령셋 (OCI · SSH 접속 후 순서대로 실행)

**⚠️ 이 명령셋은 검증자 판정 이후 사용자 승인 시에만 실행한다. 사전 검토 단계에서는 참조만.**

### 3.1 OCI 최신 코드 pull

```bash
cd /home/ubuntu/krx_hyungsoo
git fetch origin main
git log --oneline -5 origin/main
# 예상: 최상단에 Low-Frequency Telegram Push Operation v1 구현 commit
git checkout main
git pull --ff-only origin main
```

### 3.2 기존 crontab 백업

```bash
# 반드시 백업. 롤백 시 이 파일로 복구한다.
crontab -l > ~/crontab_before_low_frequency_push.txt
ls -la ~/crontab_before_low_frequency_push.txt
```

### 3.3 dry-run 사전 검증 (Telegram 미발송)

이 단계는 **송신 없음**. status/history 만 기록. 각 명령이 `status=dry_run_success` 를 반환해야 다음 단계 진행 가능.

```bash
cd /home/ubuntu/krx_hyungsoo

# Market
venv/bin/python scripts/run_three_push_runtime_oci.py --push-kind market_briefing --mode dry-run

# Holdings — 3 슬롯 각각
venv/bin/python scripts/run_three_push_runtime_oci.py --push-kind holdings_briefing --mode dry-run --slot-id OPEN
venv/bin/python scripts/run_three_push_runtime_oci.py --push-kind holdings_briefing --mode dry-run --slot-id MIDDAY
venv/bin/python scripts/run_three_push_runtime_oci.py --push-kind holdings_briefing --mode dry-run --slot-id CLOSE

# Spike (1 tick 만)
venv/bin/python scripts/run_three_push_runtime_oci.py --push-kind spike_or_falling_alert --mode dry-run
```

기대 결과:
- Market/Holdings 3슬롯: `status=dry_run_success` + `contentful_fact_count>=1`.
- Spike: `status=dry_run_success` (Runner 는 dry-run 이면 no-signal guard 이전 §5 에서 종료하므로 dry-run 결과는 항상 `dry_run_success`. 실제 발송 시점의 no-signal / duplicate 판정은 send 모드에서만 확인).

### 3.4 신규 crontab 등록

**§3.3 dry-run 이 모두 성공한 뒤에만 진행한다.**

**append-only 안전 방식** (기존 crontab 전체 대체 방지):

```bash
# 1) 기존 crontab 에서 이번 Step 관련 라인만 제거 (기존 job 은 그대로 보존).
grep -v "run_three_push_runtime_oci" ~/crontab_before_low_frequency_push.txt \
  | grep -v "Low-Frequency Telegram Push Operation v1" \
  > ~/crontab_kept.txt

# 2) 기존 유지분 + 신규 블록을 하나로 합쳐 등록.
cat ~/crontab_kept.txt > ~/crontab_new_low_freq.txt
cat >> ~/crontab_new_low_freq.txt <<'EOF'
# ─── Low-Frequency Telegram Push Operation v1 (KST 기준, UTC 로 환산) ────
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

# ── PUSH-1: Market 브리핑 — 평일 08:00 KST = 전날 23:00 UTC (요일 0-4 UTC = 일~목)
00 23 * * 0-4 cd /home/ubuntu/krx_hyungsoo && venv/bin/python scripts/run_three_push_runtime_oci.py --push-kind market_briefing --mode send >> logs/low_freq_push_cron.log 2>&1

# ── PUSH-2: Holdings 브리핑 3 슬롯 (평일 KST)
# OPEN   09:15 KST = 00:15 UTC
15 00 * * 1-5 cd /home/ubuntu/krx_hyungsoo && venv/bin/python scripts/run_three_push_runtime_oci.py --push-kind holdings_briefing --mode send --slot-id OPEN   >> logs/low_freq_push_cron.log 2>&1
# MIDDAY 12:30 KST = 03:30 UTC
30 03 * * 1-5 cd /home/ubuntu/krx_hyungsoo && venv/bin/python scripts/run_three_push_runtime_oci.py --push-kind holdings_briefing --mode send --slot-id MIDDAY >> logs/low_freq_push_cron.log 2>&1
# CLOSE  15:40 KST = 06:40 UTC
40 06 * * 1-5 cd /home/ubuntu/krx_hyungsoo && venv/bin/python scripts/run_three_push_runtime_oci.py --push-kind holdings_briefing --mode send --slot-id CLOSE  >> logs/low_freq_push_cron.log 2>&1

# ── PUSH-3: Spike/Falling 알림 7 tick (평일 KST)
30 00 * * 1-5 cd /home/ubuntu/krx_hyungsoo && venv/bin/python scripts/run_three_push_runtime_oci.py --push-kind spike_or_falling_alert --mode send >> logs/low_freq_push_cron.log 2>&1
30 01 * * 1-5 cd /home/ubuntu/krx_hyungsoo && venv/bin/python scripts/run_three_push_runtime_oci.py --push-kind spike_or_falling_alert --mode send >> logs/low_freq_push_cron.log 2>&1
30 02 * * 1-5 cd /home/ubuntu/krx_hyungsoo && venv/bin/python scripts/run_three_push_runtime_oci.py --push-kind spike_or_falling_alert --mode send >> logs/low_freq_push_cron.log 2>&1
30 03 * * 1-5 cd /home/ubuntu/krx_hyungsoo && venv/bin/python scripts/run_three_push_runtime_oci.py --push-kind spike_or_falling_alert --mode send >> logs/low_freq_push_cron.log 2>&1
30 04 * * 1-5 cd /home/ubuntu/krx_hyungsoo && venv/bin/python scripts/run_three_push_runtime_oci.py --push-kind spike_or_falling_alert --mode send >> logs/low_freq_push_cron.log 2>&1
30 05 * * 1-5 cd /home/ubuntu/krx_hyungsoo && venv/bin/python scripts/run_three_push_runtime_oci.py --push-kind spike_or_falling_alert --mode send >> logs/low_freq_push_cron.log 2>&1
20 06 * * 1-5 cd /home/ubuntu/krx_hyungsoo && venv/bin/python scripts/run_three_push_runtime_oci.py --push-kind spike_or_falling_alert --mode send >> logs/low_freq_push_cron.log 2>&1
EOF

# 3) 등록.
crontab ~/crontab.new_low_freq.txt

# 4) 등록 확인.
crontab -l | grep -E "run_three_push_runtime_oci|Low-Frequency"
diff ~/crontab.current.txt <(crontab -l)  # 예상: 신규 블록 추가만
```

### 3.5 수동 send 실측 (사용자가 회신할 결과)

각 send 명령을 **1회씩만** 실행. 두 번째 실행은 registry key 중복으로 자동 차단됨.

```bash
cd /home/ubuntu/krx_hyungsoo

# Market 1회
venv/bin/python scripts/run_three_push_runtime_oci.py --push-kind market_briefing --mode send

# Holdings OPEN
venv/bin/python scripts/run_three_push_runtime_oci.py --push-kind holdings_briefing --mode send --slot-id OPEN

# Holdings MIDDAY
venv/bin/python scripts/run_three_push_runtime_oci.py --push-kind holdings_briefing --mode send --slot-id MIDDAY

# Holdings CLOSE
venv/bin/python scripts/run_three_push_runtime_oci.py --push-kind holdings_briefing --mode send --slot-id CLOSE

# Spike 1회
venv/bin/python scripts/run_three_push_runtime_oci.py --push-kind spike_or_falling_alert --mode send
```

### 3.6 결과 회신 항목

사용자가 대화창으로 회신할 항목:

1. **각 명령의 stdout JSON** (`status`, `telegram_sent`, `contentful_fact_count`, `spike_signal_fingerprint`(있으면), `unavailable_reasons`).
2. **Telegram 실 수신 여부** (5건 — Market 1 · Holdings 3 · Spike 0 또는 1).
3. **crontab -l 출력**.
4. **로그**: `tail -n 200 logs/low_freq_push_cron.log` (아직 cron 자동 발송 대기 상태이므로 수동 실행 로그만 있을 수 있음).

---

## 4. 롤백 방법 (문제 발생 시)

```bash
# 이전 crontab 복구
crontab ~/crontab_before_low_frequency_push.txt
crontab -l
```

`state/three_push/params/latest_runtime_param.json` 및 SQLite 는 롤백 대상이 아니다 (PARAM/registry 는 상위 호환).

---

## 5. 실패 · 부분 · no_signal 계약 (A+ 재정정 · Fail-Closed)

Runtime 가격 조회 · Published Evidence 재평가 결과에 따라 Runner 는 다음 상태를 **엄격히 구분**한다. `partial` 은 별도 발송 상태가 아니라 **failed 의 한 종류**이다 (미발송·registry 미기록).

### 5.1 `failed` (미발송 · registry 미기록)

Runner 가 status=`failed` 로 종료하며 Telegram 을 호출하지 않고 sent registry 에도 기록하지 않는다.

- Naver 가격 조회 **전건 실패**: reason=`runtime_price_all_failed`.
- Naver 가격 조회 **일부 실패** (attempted>0 · failed>0): reason=`runtime_price_partial_failed`.
- Naver 조회 **예외** / ticker loader 예외: reason=`runtime_price_refresh_error`.
- Spike Published Evidence 필수 필드 (`spike_trigger_type` / `spike_direction` / `falling_threshold_pct` / `evidence_as_of`) 누락: reason=`reevaluate_missing_published_evidence`.
- Spike 재평가 결과 status=`partial` (일부 candidate 의 `base_close`/`base_date` 누락 또는 일부 ticker quote 누락): reason=`reevaluate_partial`.
- Runtime evidence/message 조립 예외 (재평가 예외 포함): reason=`runtime_evidence_error` / `reevaluate_missing_published_evidence` (fake failed 로 신호).
- Registry DB 접근 실패, Telegram 발송 실패: 각 reason.

### 5.2 `sent` (정상 발송)

Runner 가 status=`sent` 로 종료. Naver 100% 성공 + Spike 재평가 status=`ok` + 신규 fingerprint 존재.

`telegram_partial_delivery=True` 필드는 오직 Telegram chunk 전송 부분 성공만 의미한다 (데이터 품질 partial 과 무관).

### 5.3 `skipped/no_signal` (미발송 · 정상)

- Universe candidate 자체가 0건 (`no_signal=True`) → reason=`no_signal`.
- Spike 재평가 status=`ok` **이면서** signals=0 → reason=`no_signal`.
- 신규 fingerprint 0 (모두 이미 발송) → reason=`duplicate_runtime`.

**가격 조회 실패 / reeval partial 상황은 절대 no_signal 로 처리하지 않는다** (§5.1 로 분기).

### 5.4 실측 시 판정 체크리스트

```text
status=failed  → reason 확인 · Telegram 미수신 · registry 미기록 확정
status=sent    → telegram_partial_delivery(chunk 전송) 만 확인
                 데이터 품질 partial 은 절대 sent 로 오지 않음 (Fail-Closed)
status=skipped → reason ∈ {no_signal, duplicate_runtime, autosend_disabled, push_kind_*}
```

---

## 6. 미결/주의 사항

- **`state/holdings/holdings_latest.json` 부재**: A+ 재정정 (Fail-Closed) 에 의해 `_collect_target_tickers` 가 즉시 `RuntimeError("holdings source missing")` 을 raise 한다. Runner 는 `runtime_price_refresh_error/failed` 로 종료 · Telegram 미호출 · registry 미기록. 실측 전 OCI 에 파일 존재 확인 필수.
- **Universe artifact `price_history_basis.base_close` 실측치 부재**: 해당 candidate 는 `candidate_missing_fields` 진단 후 skip → partial. artifact 전체가 오래되어 필드 누락되어 있으면 back-fill 필요.
- **`spike_trigger_type` / `spike_direction` / `evidence_as_of`**: A+ 재작업에서 producer 가 새로 publish 하므로 배포 후 최초 실행 전 OCI 의 `universe_momentum_latest.json` 을 최신 producer 로 재생성해야 한다. 기존 stale artifact 에는 이 필드가 없어 Spike 가 `failed/reevaluate_missing_published_evidence` 로 종료된다.
- **OCI timezone**: 반드시 `date +%Z` 로 UTC 확인. KST 이면 crontab 시각 재환산 필요.

---

## 7. 이 문서의 상태

- crontab 미적용
- git commit 미완료
- 검증자 사전 검증 대기
- 사용자 OCI 실측 대기

검증자 검증자 판정 이후 다음 순서로 진행한다:

```text
구현 commit·push (사용자 승인 후)
→ 사용자 OCI 실측 (§3)
→ 실측 결과 회신
→ Unit 7 문서 closeout (MASTER_PLAN·STATE·handoff·BACKLOG·conclusion)
→ 검증자 최종 Closeout 검증
→ 최종 문서 commit/push
```
