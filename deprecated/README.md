# Deprecated Files

이 폴더는 Phase 4.5 FastAPI + React 전환 과정에서 더 이상 사용하지 않는 파일들을 보관합니다.

## 📁 **폴더 구조**

### **dashboard_streamlit/**
- 기존 Streamlit 대시보드 (Phase 4.5 이전)
- 9개 페이지 (home, portfolio, signals, performance, regime, alerts, backtest, stop_loss)
- 보관 이유: 로직 참고용
- 삭제 가능 시점: Phase 4.5 완료 후 (Day 10 이후)

---

## ⚠️ **주의사항**

### **삭제하지 말 것**
```
이 폴더의 파일들은 당장 삭제하지 마세요.
Phase 4.5 개발 중 로직 참고가 필요할 수 있습니다.
```

### **삭제 가능 시점**
```
✅ Phase 4.5 완료 (Day 10)
✅ FastAPI + React 정상 작동 확인
✅ Oracle Cloud 배포 완료
✅ 모든 기능 이전 완료

→ 위 조건 모두 충족 시 삭제 가능
```

---

## 📝 **삭제 전 체크리스트**

### **확인 사항**
```
□ FastAPI 백엔드 정상 작동
□ React 프론트엔드 정상 작동
□ 6개 페이지 모두 구현 완료
□ Oracle Cloud 배포 완료
□ 로컬 테스트 완료
□ 프로덕션 테스트 완료
```

### **삭제 명령어**
```bash
# 모든 확인 완료 후
rm -rf deprecated/
```

---

**보관 날짜:** 2025-11-16  
**보관 이유:** FastAPI + React 전환  
**삭제 예정:** Phase 4.5 완료 후
