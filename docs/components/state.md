# State Directory (`state/`)

**Last Updated**: 2026-01-01
**Purpose**: 시스템 상태 저장소 (포트폴리오, Gatekeeper 결정 등)

---

## 📊 File Usage Summary

| Path | Status | Used By |
|------|--------|---------|
| `paper_portfolio.json` | ✅ **ACTIVE** | Paper Trading, Dashboard |
| `live/gatekeeper_decision_v3.json` | ✅ **ACTIVE** | Gatekeeper, Dashboard |

---

## 📁 주요 파일/폴더

| Path | Status | Description |
|------|--------|-------------|
| `paper_portfolio.json` | ✅ | Paper Trading 포트폴리오 상태 |
| `live/` | ✅ | Live 상태 파일 |
| `live/gatekeeper_decision_v3.json` | ✅ | Gatekeeper 승인 결정 |

---

## 📋 사용 패턴
- Paper Trading 시스템이 `paper_portfolio.json`을 업데이트
- Gatekeeper가 `gatekeeper_decision_v3.json`을 생성
- Dashboard가 이 파일들을 읽어서 표시

---

## ⚠️ 주의사항
- 상태 파일은 **시스템에 의해서만 수정**
- 수동 수정 시 시스템 불일치 발생 가능
