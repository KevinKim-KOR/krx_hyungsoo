# PC·OCI 운영 구조 방향 점검 기록

작성일: 2026-06-20
성격: 아키텍처 방향 앵커
상태: 결정 기록 — 신규 활성 Open Question 아님

본 문서는 PC·OCI 운영 평면 분리 결정의 **원본 기록**이다. 본 결정의 요약 반영은:

- `docs/PROJECT_ORIGIN_INTENT.md` §7 운영 원칙 — OCI 장기 역할 추가
- `docs/ASSUMPTIONS.md` §3 이미 답이 나온 것 — A-6 PC 분석 평면 / OCI 운영·조회 평면 분리
- `docs/MASTER_PLAN.md` — OCI read model foundation 확장 단계로 기록
- `docs/STATE_LATEST.md` §7 Index — 본 문서 포인터

---

## 1. 결정 배경

현재 프로젝트는 PC에서 ETF universe, 시장 데이터, 후보 해석, ML 작업을 수행하고 OCI에서 일 3회 Telegram PUSH를 수행한다.

PARAM handoff와 OCI runtime PUSH까지는 확보됐다.

다만 장기적으로 OCI는 Telegram 발송만 하는 서버에 머물지 않는다. 사용자가 PC를 켜지 않아도 외부 또는 모바일에서 마지막 발행 데이터와 운영 상태를 조회할 수 있는 read-only 환경으로 확장한다.

## 2. 확정 방향

### PC 역할

PC는 분석·판단 평면이다.

* 시장 데이터 SQLite 관리
* ETF universe 갱신
* 후보 ETF 검토
* ML 학습·백테스트·feature 실험
* AI 투자세션
* 사용자 승인
* approved PARAM과 published data snapshot 생성

PC는 24시간 상시 실행을 전제로 하지 않는다.

### OCI 역할

OCI는 상시 운영·조회 평면이다.

* latest approved PARAM 보관
* 일 3회 3-PUSH 실행
* Telegram 발송
* 이후 외부·모바일 조회 메뉴 제공
* 마지막 published data snapshot 조회 제공
* 기준 시각과 데이터 신선도 표시

OCI는 ML 학습을 수행하지 않는다.

## 3. 데이터 원칙

시장 데이터의 PC 작업용 기준 저장소는 기존 SQLite를 유지한다.

OCI 전환은 PC SQLite를 즉시 폐기하거나 PC ML이 OCI DB를 직접 원격으로 읽는 구조가 아니다.

장기적으로 PC는 승인 또는 발행 시점에 OCI로 read-only published snapshot을 전달한다.

초기 OCI read model 후보:

* 선택된 시장 snapshot
* 보유 현황 snapshot
* 후보 ETF 비교 결과
* 승인 PARAM
* ML 결과 요약
* 데이터 기준 시각
* 신선도 상태

구체 형식은 OCI 조회 메뉴 구현 직전에 결정한다.

가능 후보:

* versioned SQLite snapshot
* read-only JSON artifact
* 제한된 조회용 SQLite copy

현재 단계에서 신규 DB나 full DB migration은 하지 않는다.

## 4. UI 방향

친구 프로젝트의 화면은 기능 복제 대상이 아니라 UI·운영 구조 참고다.

가져갈 요소:

* 한 화면에서 빠르게 읽히는 카드/표
* 기준 시각과 갱신 상태
* 현재값·변동률·비교값
* 데스크톱과 모바일에서 같은 read model 조회
* 판단에 필요한 정보 밀도

가져가지 않을 요소:

* 10초 폴링을 현재 운영 기본값으로 채택
* Hyperliquid 데이터 source 즉시 도입
* 친구의 점수·버킷·threshold 그대로 복제
* 친구 프로젝트 구조 전체 이식

## 4-1. 외부 참고 화면에서 확정한 방향 (2026-06-24 추가)

친구 프로젝트의 화면은 기능 복제 대상이 아니라, 향후 PC 판단 화면과 위험
evidence 표현의 참고 자료로만 사용한다.

### 나중에 참고할 패턴

* 시장 국면은 단일 상승·하락 라벨만으로 끝내지 않는다.
* 향후 위험 evidence에서는 현재 위치, 전고점 대비 거리, 국면 경계까지의
  거리를 함께 보여줄 수 있다.
* 이 거리는 "향후 하락 예측"이나 매매 지시가 아니라, 현재 계산 기준에서의
  위치 정보로 표현한다.
* 후보 비교 화면은 `요약 → 비교 표 → 선택 항목 상세 근거` 흐름을 유지한다.
* 장기 시계열과 실제 포트 기록이 충분해진 뒤에는 MDD, 변동성, 수익 주
  비율 등 성과·백테스트 지표를 검토한다.

### 가져오지 않는 것

* 자동 매수·매도
* 공격·방어 자산 자동 전환
* 매수컷·매도컷 기반 자동 추천
* 현금 비중 자동 조절
* 시스템이 보유 종목을 확정하는 기능

### 보류 원칙

국면 경계 거리, 추세 강도, 전고점 대비를 어떤 산식·기간·기준으로 계산할지는
지금 확정하지 않는다.

재검토 시점은 Cleanup 완료 후, 시계열 데이터 상태와 위험 축2의 단일 목표를
확정하는 Step이다.

## 5. 현재 순서 유지

현재 PUSH 문구와 PARAM UI Step을 먼저 닫는다.

그 다음 순서는 아래로 유지한다.

1. 상승 후보 점수화 ML 1차
2. 위험 감지용 시계열 빈자리 하나 채우기
3. 점수·위험·보유 비교가 모이는 PC 판단 화면
4. OCI read model foundation
5. 외부·모바일 조회 메뉴
6. BACKLOG 통합 정리

## 6. 문서 반영

PROJECT_ORIGIN_INTENT.md:

* 운영 원칙에 “OCI 장기 역할: 외부 read-only 조회 평면”을 추가한다.
* 단, 현재 단계의 모바일 UI 후순위 원칙은 유지한다.

ASSUMPTIONS.md:

* 활성 Open Question은 추가하지 않는다.
* 이미 답이 나온 항목에 “PC 분석 평면 / OCI 운영·조회 평면 분리”를 기록한다.
* DB 형식 선택은 OCI read model 구현 직전의 별도 결정으로 남긴다.

MASTER_PLAN.md:

* 기존 단계 순서는 바꾸지 않는다.
* OCI read model foundation은 PC 판단 화면과 ML 1차 결과가 확보된 뒤의 확장 단계로 기록한다.
