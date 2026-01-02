# Smoke Test 체크리스트

**Version**: 1.0
**Date**: 2026-01-02

---

## 사전 조건
- [ ] Python 가상환경 활성화
- [ ] 의존성 설치: `pip install -r requirements.txt`

---

## Phase 1: 파일 존재 확인
- [ ] `backend/main.py` 존재
- [ ] `dashboard/index.html` 존재
- [ ] `app/reconcile.py` 존재
- [ ] `app/generate_reports.py` 존재
- [ ] `reports/phase_c/latest/recon_summary.json` 존재
- [ ] `reports/phase_c/latest/recon_daily.jsonl` 존재
- [ ] `reports/phase_c/latest/report_human.json` 존재
- [ ] `reports/phase_c/latest/report_ai.json` 존재

---

## Phase 2: Backend 시작
```bash
cd e:\AI Study\krx_alertor_modular
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

- [ ] 서버 시작 성공 (에러 없음)

---

## Phase 3: API 엔드포인트 확인

| Endpoint | 예상 응답 | 확인 |
|----------|-----------|------|
| `GET /api/recon/summary` | JSON with `status` field | [ ] |
| `GET /api/recon/daily` | JSONL 데이터 | [ ] |
| `GET /api/report/human` | Contract 5 Human Report | [ ] |
| `GET /api/report/ai` | Contract 5 AI Report | [ ] |

```bash
# 테스트 명령
curl http://localhost:8000/api/recon/summary
curl http://localhost:8000/api/report/human
```

---

## Phase 4: Dashboard 확인
- [ ] `http://localhost:8000` 접속
- [ ] Status 탭 렌더링
- [ ] Diagnosis 탭 렌더링

---

## Phase 5: Archive 격리 확인
- [ ] `_archive/**` 경로에서 import 없음 확인

```bash
# 확인 명령 (결과 없어야 함)
grep -r "from _archive" backend/ app/
```

---

## 통과 기준
- [ ] 모든 Phase 체크 완료
- [ ] API 4개 엔드포인트 모두 응답
- [ ] Dashboard 렌더링 성공
