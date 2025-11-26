# Standalone UI Archive

이 디렉토리는 독립적으로 실행되는 단일 파일 UI를 보관합니다.

## 파일 목록

### portfolio_manager.py
- **설명**: Streamlit 기반 포트폴리오 매니저
- **기능**: 포트폴리오 관리 및 시각화
- **상태**: 독립 실행 가능
- **이동 이유**: 
  - 루트 `ui/` 디렉토리에 단일 파일만 존재
  - React 기반 통합 UI (`web/dashboard/`)로 대체됨
  - 필요 시 독립적으로 실행 가능하도록 보존

## 실행 방법

```bash
# Streamlit 설치
pip install streamlit

# 실행
streamlit run extensions/ui_archive/standalone/portfolio_manager.py
```

## 참고

- **현재 UI**: `web/dashboard/` (React + TypeScript + Vite)
- **Archive UI**: `extensions/ui_archive/streamlit/` (Streamlit 전체 UI)
- **Standalone UI**: 이 디렉토리 (단일 파일 UI)

## 복원 방법

필요 시 다시 사용하려면:

```bash
# 루트로 복사
cp extensions/ui_archive/standalone/portfolio_manager.py ui/

# 또는 직접 실행
streamlit run extensions/ui_archive/standalone/portfolio_manager.py
```

---

**보관일**: 2025-11-26  
**이유**: 프로젝트 구조 정리, React UI로 통합
