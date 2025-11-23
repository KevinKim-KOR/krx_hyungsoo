# 세션 시작 체크리스트

**목적**: 매 세션 시작 시 Cascade AI가 자동으로 읽고 확인하는 파일  
**업데이트**: 작업 완료 시 사용자가 직접 업데이트

---

## 📋 현재 작업 (Current Work)

### Phase: Daily Regime Check 100% 구현
**작업 시작**: 2025-11-23 19:34

### 소단위 작업
1. ✅ **PyKRX 데이터 로딩 수정** (완료 19:50)
   - 파일: `scripts/nas/daily_regime_check.py`
   - 결과: KOSPI 241행 조회 성공
   - 수정: 로거 설정 개선, 상세 로그 추가

2. ✅ **레짐 감지 로직 검증** (완료 19:50)
   - 파일: `core/strategy/market_regime_detector.py`
   - 결과: 상승장 감지 성공 (신뢰도 100%)
   - MA 50/200일 정상 동작

3. ✅ **미국 지표 통합** (완료 19:50)
   - 파일: `core/strategy/us_market_monitor.py`
   - 결과: Nasdaq, S&P 500, VIX 조회 성공
   - 미국 시장 레짐: bearish

4. ✅ **보유 종목 매도 신호** (완료 20:05)
   - 파일: `scripts/nas/daily_regime_check.py`
   - 결과: 29개 종목 확인, 10건 매도 신호 생성
   - 기능: 현재가 조회, 수익률 계산, 손절 판단

5. ✅ **텔레그램 알림** (완료 20:05)
   - 결과: 레짐 변화, 매도 신호 알림 메시지 생성
   - 기능: 이모지, 상세 정보, 권장 조치

### 최종 목표
- ✅ 로컬(PC) 테스트 완료
- ✅ 오류 없이 동작
- ✅ 100% 기능 구현
- ⏳ Oracle Cloud 배포 (다음 단계)

### 현재 상태
- ✅ **Phase 완료**: Daily Regime Check 100% 구현
- ✅ **파라미터 YAML 설정**: 하드코딩 → YAML 변경
- ⏳ **다음**: Oracle Cloud Cron 설정

---

## 🔄 파라미터 동기화 (완료 23:19)

### Git 기반 동기화
- ✅ config/regime_params.yaml 생성
- ✅ MarketRegimeDetector YAML 로드 기능
- ✅ 백테스트 출처 문서화 (Week 3, 2025-11-08)

### 워크플로우
```
PC 백테스트 → regime_params.yaml 업데이트 → Git push
                                              ↓
Oracle Cloud Git pull (08:00) → Daily Regime Check (09:00)
```

### 다음 단계
- ⏳ Oracle Cloud Cron 설정 (Git pull + Daily Check)

---

## 🚨 현재 문제점

### 문제 1: 레짐 감지 실패
**증상**:
```
WARNING: yfinance 사용 불가
WARNING: FinanceDataReader 사용 불가
WARNING: yfinance 사용 불가 - 네이버 금융 폴백 시도: ^KS11
WARNING: 지표 없음, 중립장으로 판단
```

**해결 시도**:
1. ✅ yfinance 선택적 import
2. ✅ PyKRX import 추가
3. ✅ PyKRX 한글 컬럼명 변환
4. ⏳ **다음**: 전체 로그 확인 필요

**필요한 정보**:
- NAS 전체 로그 출력
- `python3 scripts/nas/daily_regime_check.py` 전체 결과

---

## 📝 이전 작업 (Previous Work)

### 2025-11-22 (어제)
**작업**: Holdings 페이지 구현  
**소요 시간**: 10시간  
**결과**: ✅ 완료
- Holdings 페이지 추가
- 매도 신호 API 구현
- 네이버 금융 현재가 조회

---

## 🎯 다음 단계 (Next Steps)

### 즉시 (Immediate)
1. **NAS 전체 로그 확인**
   ```bash
   cd /volume2/homes/Hyungsoo/krx/krx_alertor_modular
   python3 scripts/nas/daily_regime_check.py
   ```
   - 전체 출력 복사
   - 레짐 감지 성공 여부 확인
   - 텔레그램 알림 여부 확인

2. **문제 진단**
   - PyKRX 데이터 조회 성공?
   - 레짐 감지 계산 성공?
   - 미국 지표 필요 여부?

3. **수정 및 테스트**
   - 문제 수정
   - 텔레그램 알림 테스트
   - Cron 설정 확인

### 다음 (Next)
1. **React 파라미터 설정 UI** (3~4시간)
2. **Oracle Cloud 최신 기능 반영** (2~3시간)

---

## 💡 중요 사항 (Important Notes)

### 사용자 요구사항
1. **장중 시장 흐름 파악** ✅
   - Intraday Alert (10:00, 14:00)

2. **장 시작 시 시장 흐름 변화** ❌
   - Daily Regime Check (09:00) - 현재 작업 중

3. **보유 주식 손절/이상 알림** ⚠️
   - Holdings UI 완료
   - Daily Regime Check와 연동 필요

### 환경
- **NAS**: DS220J, Python 3.8
- **PC**: Windows, Python 3.13
- **Oracle Cloud**: 배포 완료, 모바일 접속 가능

### 데이터 소스 우선순위
1. PyKRX (최우선, Python 3.8 호환)
2. FinanceDataReader (폴백)
3. 네이버 금융 (현재가만)
4. yfinance (NAS 사용 불가)

---

## 🔧 개발 원칙

### 코드 수정 전
1. ✅ 기존 코드 확인
2. ✅ 기존 패키지 활용
3. ✅ 변경 최소화
4. ✅ 테스트 먼저

### 문제 해결 시
1. ✅ 에러 메시지 정확히 읽기
2. ✅ 데이터 출력 확인
3. ✅ 근본 원인 파악
4. ✅ 기존 시스템 존중

### 소통 개선
1. ✅ 이 파일 먼저 읽기
2. ✅ PROJECT_STATUS.md 확인
3. ✅ 문서 확인
4. ✅ 기존 구현 확인

---

## 📚 참고 문서

### 필수
- `.cascade/PROJECT_STATUS.md` - 전체 프로젝트 상태
- `docs/README.md` - 문서 목록
- `docs/GAP_ANALYSIS.md` - 계획 vs 구현

### 현재 작업 관련
- `docs/NAS_REGIME_CRON_SETUP.md` - NAS Cron 설정
- `docs/NAS_YFINANCE_FIX.md` - yfinance 문제 해결
- `docs/NAS_DS220J_SETUP.md` - DS220J 최적화

---

## ✅ 세션 시작 시 확인 사항

### Cascade AI가 확인할 것
- [ ] 이 파일 읽기
- [ ] PROJECT_STATUS.md 읽기
- [ ] 현재 작업 파악
- [ ] 문제점 파악
- [ ] 다음 단계 파악

### 사용자에게 물어볼 것
- [ ] "현재 작업 중인 것이 맞나요?"
- [ ] "문제가 해결되었나요?"
- [ ] "다음 단계로 진행할까요?"

---

**이 파일은 사용자가 직접 업데이트합니다.**  
**Cascade AI는 읽기만 합니다.**
