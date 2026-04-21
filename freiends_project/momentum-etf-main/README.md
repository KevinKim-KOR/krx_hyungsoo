# 📈 Momentum ETF

> **"추세에 순응하되, 위험은 철저히 관리한다."**
>
> 데이터 기반의 ETF 순위 분석 시스템

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Code Style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

## 🚀 소개 (Introduction)

**Momentum ETF**는 계좌 설정을 기반으로 동작하는 **ETF 순위 분석 시스템**입니다.
현재 운영 모델은 다음과 같습니다.
* 계좌(`zaccounts/*`): 등록된 전체 종목을 직접 관리하고 비중 조절로 운용

감정이나 직관에 의존하는 투자를 지양하고, **이동평균(MA)**과 **RSI** 등 기술적 지표를 활용하여 **"현재 계좌 종목의 상대 추세 강도를 비교하는"** 데이터 기반의 의사결정을 지원합니다.

## ✨ 주요 기능 (Key Features)

*   **📊 계좌별 순위 화면**: 종목풀별 `MA_RULES` 기본값을 불러오고, 화면에서 `추세1`과 `추세2`를 각각 바꿔가며 점수와 규칙별 추세를 즉시 확인합니다.
*   **🟩 실보유 강조 표시**: 실제 보유 종목은 순위 테이블에서 녹색 행으로 즉시 구분합니다.
*   **🛡️ 데이터 안정성 (Robust Caching)**: **Apache Parquet** 포맷을 캐시 엔진으로 도입하여 라이브러리 버전 mismatch로부터 자유롭고 안정적인 데이터 로딩을 보장합니다.
*   **🛠️ 종목 관리**: 계좌별 종목 추가/수정/삭제 및 삭제 종목 복원을 지원합니다.

## 📚 문서 (Documentation)

더 자세한 내용은 `docs/` 폴더의 문서를 참고하세요.

*   **[프로젝트 개요 (Project Overview)](docs/project_overview.md)**: 프로젝트의 철학, 상세 기능, 시스템 구조
*   **[사용자 가이드 (User Guide)](docs/user_guide.md)**: 설치, 설정, 실행 방법, 결과 해석
*   **[전략 로직 (Strategy Logic)](docs/strategy_logic.md)**: 이동평균 점수 계산 규칙과 정렬 기준
*   **[개발자 가이드 (Developer Guide)](docs/developer_guide.md)**: 시스템 아키텍처, 데이터 파이프라인, 화면 구성

## ⚡️ 빠른 시작 (Quick Start)

### 1. 설치

```bash
# 저장소 클론
git clone https://github.com/your-username/momentum-etf.git
cd momentum-etf

# 가상환경 생성 및 활성화 (권장)
python -m venv venv
source venv/bin/activate  # Mac/Linux
# venv\Scripts\activate  # Windows

# 의존성 설치
pip install -r requirements.txt
```

### 2. 설정
`config.py` 및 `zaccounts/<account>/config.json` 파일을 환경에 맞게 수정합니다. (상세 내용은 [사용자 가이드](docs/user_guide.md) 참고)

### 3. 실행

**1. 웹 실행**
```bash
cd web
npm run dev
```

웹에서 다음 기능을 사용합니다.
* `http://localhost:3000/`
* Home
* 자산 관리 / 스냅샷 / 주별
* 종목 관리 / ETF 마켓 / 계좌 메모 / AI용 요약 / 정보

현재 기본 계좌 식별자는 다음과 같습니다.
* 계좌: `kor_account`, `isa_account`, `pension_account`, `core_account`, `aus_account`

## ⚠️ 면책 조항 (Disclaimer)

이 소프트웨어는 투자를 돕기 위한 보조 도구입니다. **최종적인 투자 결정과 그에 따른 책임은 전적으로 사용자에게 있습니다.** 개발자는 이 프로그램을 사용하여 발생한 금전적 손실에 대해 책임지지 않습니다.
