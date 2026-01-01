# Logs Directory (`logs/`)

**Last Updated**: 2026-01-01
**Purpose**: 시스템 로그 저장소

---

## 📊 Log File Usage Summary

| Pattern | Status | Used By |
|---------|--------|---------|
| `daily_YYYYMMDD.log` | ✅ **ACTIVE** | Backend `/api/status` 파싱 |
| `app.log` | ✅ **ACTIVE** | 애플리케이션 로깅 |
| `backend.log` | ✅ **ACTIVE** | 백엔드 서버 로깅 |
| `archive/` | ⚠️ **ARCHIVE** | 과거 로그 보관 |

---

## 📄 주요 로그 파일

| File | Status | Description |
|------|--------|-------------|
| `daily_YYYYMMDD.log` | ✅ | 일별 실행 로그 (크론 배치) |
| `app.log` | ✅ | 애플리케이션 로그 |
| `backend.log` | ✅ | 백엔드 서버 로그 |

---

## 📋 로그 파싱
Backend API (`/api/status`)는 `daily_YYYYMMDD.log` 파일을 파싱하여 시스템 상태를 판단합니다.

### 주요 키워드
- `[OK]`: 성공
- `[ERROR]`: 오류
- `[COMPLETED]`: 완료
- `[SKIP]`: 스킵 (멱등성)

---

## ⚠️ 주의사항
- 로그 파일은 **읽기 전용**으로 취급
- 인코딩 문제 시 `safe_read_text_advanced()` 사용
