# OCI 3-PUSH Crontab Runner — 등록 Template

작성일: 2026-06-15
Step: OCI_THREE_PUSH_CRONTAB_RUNNER_AUTOSEND

---

## 1. 전제 조건

OCI 에서 실행 전 확인 사항:

```bash
# package sync 완료 여부 확인 (PC 에서 sync 후)
ls ~/krx_hyungsoo/state/three_push/packages/
# 기대: manifest.json + latest_market_briefing.json + latest_holdings_briefing.json + latest_spike_or_falling_alert.json

# runner 동작 확인
python scripts/run_three_push_oci.py --push-kind market_briefing --mode dry-run
```

---

## 2. 필수 환경변수

OCI `~/.bashrc` 또는 `~/.profile` 에 추가:

```bash
# Telegram
export TELEGRAM_BOT_TOKEN="..."
export TELEGRAM_CHAT_ID="..."

# 전체 자동 발송 ON/OFF
export PUSH_AUTOSEND_ENABLED=true

# push_kind 별 ON/OFF
export PUSH_AUTOSEND_MARKET_BRIEFING_ENABLED=true
export PUSH_AUTOSEND_HOLDINGS_BRIEFING_ENABLED=true
export PUSH_AUTOSEND_SPIKE_OR_FALLING_ALERT_ENABLED=true

# package 경로 (기본값: /home/ubuntu/krx_hyungsoo/state/three_push/packages)
# export THREE_PUSH_PACKAGE_DIR=/home/ubuntu/krx_hyungsoo/state/three_push/packages

# stale 판정 기준 시간 (기본값: 36시간)
# export THREE_PUSH_MAX_PACKAGE_AGE_HOURS=36
```

crontab 은 로그인 shell 환경변수를 상속하지 않으므로 crontab 내 직접 설정 권장:

```text
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
PUSH_AUTOSEND_ENABLED=true
PUSH_AUTOSEND_MARKET_BRIEFING_ENABLED=true
PUSH_AUTOSEND_HOLDINGS_BRIEFING_ENABLED=true
PUSH_AUTOSEND_SPIKE_OR_FALLING_ALERT_ENABLED=true
```

---

## 3. Crontab Template

`crontab -e` 로 편집:

```crontab
# ─── 3-PUSH 자동 발송 (한국 KST = UTC+9) ─────────────────────────────────────
# 발송 시간은 운영 전 사용자가 조정 가능. 아래는 참고용 기본값.
# 주의: crontab 시간은 OCI 서버 timezone 기준 (확인: date +%Z)

TELEGRAM_BOT_TOKEN=your_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
PUSH_AUTOSEND_ENABLED=true
PUSH_AUTOSEND_MARKET_BRIEFING_ENABLED=true
PUSH_AUTOSEND_HOLDINGS_BRIEFING_ENABLED=true
PUSH_AUTOSEND_SPIKE_OR_FALLING_ALERT_ENABLED=true

# PUSH-1: 시장 흐름 브리핑 — 평일 오전 8시 (KST) / UTC 기준 23:00 전날
# 한국 평일 주식 시장 개장 전 발송
00 23 * * 0-4 cd /home/ubuntu/krx_hyungsoo && python scripts/run_three_push_oci.py --push-kind market_briefing --mode send >> logs/three_push_cron.log 2>&1

# PUSH-2: 보유 종목 관찰 브리핑 — 평일 오후 12시 30분 (KST) / UTC 03:30
# 점심 시간 장중 관찰
30 03 * * 1-5 cd /home/ubuntu/krx_hyungsoo && python scripts/run_three_push_oci.py --push-kind holdings_briefing --mode send >> logs/three_push_cron.log 2>&1

# PUSH-3: 급등락/상승 관찰 신호 — 평일 오후 3시 30분 (KST) / UTC 06:30
# 장 마감 30분 전 관찰
30 06 * * 1-5 cd /home/ubuntu/krx_hyungsoo && python scripts/run_three_push_oci.py --push-kind spike_or_falling_alert --mode send >> logs/three_push_cron.log 2>&1
```

---

## 4. 시간 조정 가이드

| PUSH | 발송 시점 (KST) | UTC | 용도 |
|---|---|---|---|
| PUSH-1 market_briefing | 평일 08:00 | 23:00 (전날) | 장 개장 전 시장 흐름 확인 |
| PUSH-2 holdings_briefing | 평일 12:30 | 03:30 | 점심 장중 보유 관찰 |
| PUSH-3 spike_or_falling_alert | 평일 15:30 | 06:30 | 장 마감 전 급등락 신호 확인 |

발송 시간을 바꾸려면 crontab 의 `분 시` 부분만 수정한다.

OCI 서버 timezone 확인:

```bash
date +%Z
# UTC 이면 위 표의 UTC 컬럼 값 사용
# KST 이면 KST 컬럼 값 직접 사용
```

---

## 5. dry-run 먼저 확인

발송 전 반드시 dry-run 으로 각 push_kind 검증:

```bash
python scripts/run_three_push_oci.py --push-kind market_briefing --mode dry-run
python scripts/run_three_push_oci.py --push-kind holdings_briefing --mode dry-run
python scripts/run_three_push_oci.py --push-kind spike_or_falling_alert --mode dry-run
```

`status=dry_run_success` 3건 확인 후 crontab 등록.

---

## 6. 실행 결과 확인

```bash
# 최신 실행 결과
cat state/three_push/oci_runner_status_latest.json

# 실행 이력 (jsonl)
tail -20 state/three_push/oci_runner_history.jsonl

# 로그
tail -50 logs/three_push_cron.log

# 발송 registry (중복 방지)
cat state/three_push/oci_sent_registry.json
```

---

## 7. package 갱신 (PC → OCI sync)

runner 는 PC 에서 sync 한 package 를 읽는다. package 를 갱신하려면 PC 에서:

```bash
python scripts/sync_three_push_packages.py
```

실행 후 `sync_status_latest.json` 에서 `status=success` 확인.

stale 차단 기준(기본 36시간)을 넘기 전에 PC sync 를 주기적으로 실행해야 발송이 정상 동작한다.

---

## 8. 중단 방법

전체 발송 중단:

```bash
# crontab 의 PUSH_AUTOSEND_ENABLED 를 false 로 변경
crontab -e
# PUSH_AUTOSEND_ENABLED=false
```

push_kind 별 중단:

```bash
# 해당 push_kind 의 flag 만 false 로 변경
# PUSH_AUTOSEND_MARKET_BRIEFING_ENABLED=false
```

---

## 9. 주의사항

- TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID 는 로그/status 파일에 기록되지 않는다.
- 같은 package_id 는 1회만 발송된다 (oci_sent_registry.json 관리).
- generation_status=failed 인 package 는 발송하지 않는다.
- stale package (기본 36시간 초과) 는 발송하지 않는다.
- 금지 문구(매수/매도/비중조절/조정장 확정 등) 가 포함된 message_text 는 발송하지 않는다.
