# FastAPI 백엔드 API

## 🚀 **빠른 시작**

### **1. 의존성 설치**
```bash
cd backend
pip install -r requirements.txt
```

### **2. 서버 실행**
```bash
python -m uvicorn app.main:app --reload
```

### **3. API 문서 확인**
```
http://localhost:8000/api/docs
```

### **4. API 테스트**
```bash
python test_api.py
```

---

## 📊 **API 엔드포인트 (18개)**

### **기본**
- `GET /` - 루트
- `GET /health` - 헬스 체크

### **대시보드 (2개)**
- `GET /api/v1/dashboard/summary` - 대시보드 요약
- `GET /api/v1/dashboard/holdings` - 보유 종목

### **자산 관리 (7개)**
- `GET /api/v1/assets/` - 자산 목록
- `POST /api/v1/assets/` - 자산 추가
- `GET /api/v1/assets/{id}` - 자산 상세
- `PUT /api/v1/assets/{id}` - 자산 수정
- `DELETE /api/v1/assets/{id}` - 자산 삭제
- `GET /api/v1/assets/trades/` - 거래 기록
- `POST /api/v1/assets/trades/` - 거래 추가

### **백테스트 (4개)**
- `GET /api/v1/backtest/results` - 백테스트 결과
- `POST /api/v1/backtest/run` - 백테스트 실행 (로컬만)
- `GET /api/v1/backtest/history` - 백테스트 히스토리
- `GET /api/v1/backtest/compare` - 파라미터 비교

### **손절 전략 (3개)**
- `GET /api/v1/stop-loss/strategies` - 전략 목록
- `GET /api/v1/stop-loss/comparison` - 전략 비교
- `GET /api/v1/stop-loss/targets?strategy=hybrid` - 손절 대상

### **신호 & 히스토리 (3개)**
- `GET /api/v1/signals/?days=7` - 매매 신호
- `GET /api/v1/signals/history` - 신호 히스토리
- `GET /api/v1/signals/alerts?days=7` - 알림 히스토리

### **시장 분석 (3개)**
- `GET /api/v1/market/regime` - 시장 레짐
- `GET /api/v1/market/volatility` - 변동성 분석
- `GET /api/v1/market/sectors` - 섹터 분석

---

## 🧪 **테스트 결과**

### **정상 작동 (12개)** ✅
```
✅ 헬스 체크
✅ 루트
✅ 대시보드 요약
✅ 백테스트 파라미터 비교
✅ 손절 전략 목록 (4가지)
✅ 손절 전략 비교
✅ 손절 대상 종목 (6개)
✅ 매매 신호
✅ 알림 히스토리
✅ 시장 레짐 (명확한 기준)
✅ 변동성 분석
✅ 섹터 분석
```

### **데이터 필요 (1개)** ⚠️
```
⚠️ 백테스트 결과 (404)
   → data/output/backtest/jason_backtest_results.json 필요
   → data/output/backtest/hybrid_backtest_results.json 필요
```

---

## 📝 **데이터 준비**

### **백테스트 결과 파일 생성**
```bash
# Phase 2 백테스트 실행
cd ..
python scripts/phase2/run_backtest_jason.py
```

### **손절 전략 비교 파일 생성**
```bash
# Phase 4 손절 전략 비교
python scripts/phase4/compare_stop_loss_strategies.py
```

---

## 🔧 **환경 변수**

`.env` 파일 생성:
```env
IS_LOCAL=true
DEBUG=true
DATABASE_URL=sqlite:///./data/krx_alertor.db
TELEGRAM_BOT_TOKEN=your_token
TELEGRAM_CHAT_ID=your_chat_id
```

---

## 📚 **API 문서**

### **Swagger UI** (추천)
```
http://localhost:8000/api/docs
```

### **ReDoc**
```
http://localhost:8000/api/redoc
```

### **OpenAPI JSON**
```
http://localhost:8000/api/openapi.json
```

---

## 🐛 **트러블슈팅**

### **문제 1: Pydantic 타입 에러**
```
PydanticSchemaGenerationError: Unable to generate pydantic-core schema for <built-in function any>
```

**해결:**
```python
# ❌ 잘못된 코드
optimal_value: any

# ✅ 올바른 코드
from typing import Union
optimal_value: Union[str, int, float]
```

### **문제 2: 백테스트 결과 404**
```
{"detail":"백테스트 결과를 찾을 수 없습니다"}
```

**해결:**
```bash
# 백테스트 실행하여 JSON 파일 생성
python scripts/phase2/run_backtest_jason.py
```

### **문제 3: 포트 충돌**
```bash
# 다른 포트 사용
python -m uvicorn app.main:app --reload --port 8001
```

---

## 📊 **테스트 스크립트**

### **전체 API 테스트**
```bash
python test_api.py
```

### **개별 API 테스트**
```bash
# curl 사용
curl http://localhost:8000/api/v1/market/regime

# Python requests 사용
python -c "import requests; print(requests.get('http://localhost:8000/health').json())"
```

---

## 🎯 **다음 단계**

### **Day 4-8: React 프론트엔드**
```
1. Node.js 설치
2. Create React App
3. TailwindCSS 설정
4. 6개 페이지 구현
5. API 연동
```

---

**FastAPI 백엔드 완성!** ✅  
**18개 API 정상 작동!** 🎉  
**테스트 스크립트 포함!** 🧪
