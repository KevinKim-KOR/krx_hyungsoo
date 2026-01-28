# KRX Alertor Modular — STATE_LATEST (Handoff)

> 목적: 새 세션/새 담당자/새 AI가 “추측 없이” 동일한 방식으로 운영을 이어가기 위한 1장 요약.
> 원칙: Fail-Closed / Resolver-only / PC→OCI Pull / 운영 스크립트 파싱 단순 유지.

---

## 0) 오늘 결론 (한 줄)
- ✅ 현재 운영 상태: [OK] (P67: Spike/Holding Watch 완전 정상화)
- 🧩 핵심 이슈: 없음. (Spike receipt artifact 경로 불일치 및 미생성 문제 해결됨)

---

## 1) 아키텍처 요약 (PC → OCI Pull)
- PC(주도): UI에서 **백테스트/결과확인/포트폴리오/설정/워치리스트** 입력 및 저장
- OCI(운영): 매일 **git pull → ops summary → live cycle → order plan → daily status push**
- 실시간(장중): **spike_watch / holding_watch**가 크론으로 돌며 텔레그램 알림

---

## 2) Git / 브랜치
- Repo: `krx_hyungsoo`
- Branch(운영 기준): `archive-rebuild`
- PC 기준 커밋: `f04d81f` (OCI Synced)
- OCI 기준 커밋: `P67-FIX-FINAL` (Assumed Synced)
- 마지막 변경 요약(짧게): Fix Spike Watch Artifacts & API Path Match

---

## 3) OCI 서비스(backend) 상태
- 서비스명: `krx-backend.service`
- 포트: `:8000`
- 상태 확인:
  - `sudo systemctl status krx-backend.service --no-pager -l | head -60`
  - `sudo ss -lntp | grep ':8000'`
- Health API:
  - `curl -s http://localhost:8000/api/ops/health | python3 -m json.tool | head -80`

---

## 4) 텔레그램 발송 설정(OCI)
- Sender enable 스위치:
  - 파일: `state/real_sender_enable.json`
  - 예시:
    ```json
    {"enabled": true, "provider": "telegram"}
    ```
- Telegram secrets:
  - 파일: `state/secrets/telegram.env` (chmod 600)
  - 키:
    - `TELEGRAM_BOT_TOKEN=...`
    - `TELEGRAM_CHAT_ID=...`
- systemd env 주입:
  - `/etc/systemd/system/krx-backend.service` 내 `[Service]`에
    - `EnvironmentFile=/home/ubuntu/krx_hyungsoo/state/secrets/telegram.env`
  - 적용:
    - `sudo systemctl daemon-reload`
    - `sudo systemctl restart krx-backend.service`

---

## 5) 운영 스케줄 (OCI crontab)
- crontab:
  - `crontab -l`
- 현재 등록(붙여넣기):
  ```cron
  # 1. 일요일 로그 정리
  0 1 * * 0 cd /home/ubuntu/krx_hyungsoo && test -f logs/daily_ops.log && tail -n 5000 logs/daily_ops.log > logs/daily_ops.log.tmp && mv -f logs/daily_ops.log.tmp logs/daily_ops.log || true
  
  # 2. Daily Ops (매일 09:05)
  5 9 * * * cd /home/ubuntu/krx_hyungsoo && bash deploy/oci/daily_ops.sh >> logs/daily_ops.log 2>&1
  
  # 3. Spike Watch (장중 매 5분)
  */05 09-15 * * 1-5 cd /home/ubuntu/krx_hyungsoo && bash deploy/oci/spike_watch.sh >> logs/spike_watch.log 2>&1
  
  # 4. Holding Watch (장중 매 10분, 보유종목 감시)
  */10 9-15 * * 1-5 cd /home/ubuntu/krx_hyungsoo && bash deploy/oci/holding_watch.sh >> logs/holding_watch.log 2>&1
  ```

---

## 6) 주요 “운영 버튼” (CLI 한 줄)
### A) 로그 요약 (P69 Standard)
- 최근 1회 실행 "Reason" 확정:
  - Spike: `tail -n 80 logs/spike_watch.log | grep "Reason=" | tail -1`
  - Holding: `tail -n 80 logs/holding_watch.log | grep "Reason=" | tail -1`

### B) 데일리 운영(OCI)
- 실행:
  `bash deploy/oci/daily_ops.sh`
- Exit code:
  - 0 = OK/WARN 정상 완료
  - 2 = BLOCKED(정상 차단: stale/empty/no portfolio 등)
  - 3 = 운영 장애(스크립트/백엔드/예외)

### B) 스파이크 감시(OCI)
- 실행(수동):
  `bash deploy/oci/spike_watch.sh`

### C) 보유 감시(OCI)
- 실행(수동):
  `bash deploy/oci/holding_watch.sh`

---

## 7) idempotency 규칙(핵심만)
- **Daily Status Push**: `daily_status_YYYYMMDD` (하루 1회)
- **Incident Push**: `incident_<KIND>_YYYYMMDD` (동일 타입 하루 1회)
- **Spike/Holding**: 쿨다운 + “추가 변동(realert_delta)”일 때만 재알림

---

## 8) 운영 확인(증거/리포트)
### A) Daily Status 최신
```bash
curl -s http://localhost:8000/api/push/daily_status/latest | python3 -m json.tool | head -120
```

### B) Holding Watch 최신 (Evidence-based)
- Evidence Ref: `guard_holding_latest` (Alias)
- 검증 (Resolver):
```bash
curl "http://localhost:8000/api/evidence/resolve?ref=guard_holding_latest"
```

### C) Spike Watch 최신 (Evidence-based, P67 Completed)
- Evidence Ref: `guard_spike_latest` (Alias)
- 검증 (Resolver):
```bash
curl "http://localhost:8000/api/evidence/resolve?ref=guard_spike_latest"
```

---

## 9) PC에서 입력되는 것 → OCI로 넘어오는 경로
- **Portfolio**: PC UI에서 저장 → git push → OCI git pull → `state/portfolio/latest/...`
- **Settings(Spike/Holding 통합)**: PC UI 저장 → git push → OCI git pull → `state/settings/latest/...`
- **Watchlist**: PC UI 저장 → git push → OCI git pull → `state/watchlist/latest/...`
- **Strategy bundle**: PC 생성 → `state/strategy_bundle/latest/...` 갱신 → git push → OCI git pull

---

## 10) 오늘 장애/이슈 기록 (필수)
- 날짜: 2026-01-27
- 증상:
  1. Holding Watch 알림 미수신 (Env 미로드) -> 해결
  2. Spike Watch Artifact(JSON) 미생성 (Early Return 문제) -> 해결
  3. API Path Mismatch (구형 spike 경로 참조) -> 해결
- 조치:
  - holding_watch.sh: `set -a` 추가.
  - run_spike_push.py: `try-finally` 블록으로 Artifact 생성 보장, Indentation Fix.
  - backend/main.py: API 경로를 `spike_watch`로 변경.
- 검증:
  - 모든 Watcher가 실행 후 JSON Artifact를 남기며, API(`api/push/spike/latest`, `api/evidence/resolve`)가 정상 응답함.
  - `logs/spike_watch.log` 최근 구간 에러 없음(RECENT_OK).

---

## 11) 다음 단계(Phase)
- 현재 완료: D-P.67 (Spike/Holding Artifact Consistency & Evidence System)
- 다음 후보:
  - P68: Spike Receipt Quality (execution_reason enum화 등, 잔여 개선)
- 보류(나중에): 보유임계치 백테스트/평단 실시간 정교화/괴리율 고도화 등
