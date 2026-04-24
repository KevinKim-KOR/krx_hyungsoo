# MASTER_PLAN

이 프로젝트의 목적은 **AI와 함께 투자 방향을 찾는 것**이다. 운영 전제는 **직장인형 저빈도, K6/EOD 기준, 본업 우선**이며, 새 프로젝트는 Phase 1에서 검증된 자산 중 **독립 ML 모듈, OCI crontab 구조(daily_ops / spike_watch / holding_watch), Telegram 연동**만 살리고 나머지는 화이트리스트 기반으로 다시 시작한다. 성공 기준은 **친구의 긍정적 반응**, **4070s가 실제 ML 작업을 돌리는 상태**, **와이프가 이해할 수 있는 UI**이며, 1차 성과 판정은 **추천 ETF 평균 수익률**과 **같은 기간 KODEX 200 대비 초과 성과**로 본다. 친구 프로젝트 통째 이식, MongoDB 전환, 복잡도 증식은 범위 밖이다. :contentReference[oaicite:1]{index=1} :contentReference[oaicite:2]{index=2} :contentReference[oaicite:3]{index=3}

## 1단계. 데이터 수집 및 추천 초안 생성
K6/EOD 기준으로 시장 데이터를 수집하고, holdings와 결합하여 추천/상태 **초안**을 만든다. 이 단계의 산출물은 실행본이 아니라 **PENDING 상태의 승인 대기안**이다.  
- 연결 Open Question: **Q2, Q3** :contentReference[oaicite:4]{index=4}  
- 관련 Kill Switch: **KS-1, KS-3** :contentReference[oaicite:5]{index=5}  
- 완료 기준: **시장 데이터 1회 수집 → holdings 결합 → PENDING 추천 초안 1건 생성까지 완료되고, 백엔드 데이터와 화면 표시가 일치한다.**

## 2단계. 인간 최종 승인 게이트 구축
추천 초안과 OCI 전달 사이에 **Approve / Reject** 게이트를 둔다. **Approve 전에는 OCI 푸쉬, 후속 실행, 알림 발송이 금지**되며, Reject는 기록만 남기고 종료한다. 시스템은 자동 실행이 아니라 **인간 승인 기반 전진 구조**여야 한다.  
- 연결 Open Question: **Q2, Q3** :contentReference[oaicite:6]{index=6}  
- 관련 Kill Switch: **KS-1, KS-2, KS-3** :contentReference[oaicite:7]{index=7}  
- 완료 기준: **동일한 PENDING 초안에 대해 Approve 시에만 OCI 전달과 알림이 실행되고, Reject 시에는 아무 푸쉬도 발생하지 않음이 확인된다.**

## 3단계. 설명 가능한 판단 UI 구축
사용자가 추천 결과를 보고 승인 여부를 판단할 수 있도록, 입력값·판단 이유·추천 ETF/보유 상태·승인 대기 상태를 한 화면에서 읽히게 만든다. 화면은 전문 용어보다 **이유와 상태**가 먼저 보이도록 단순해야 한다.  
- 연결 Open Question: **Q3** :contentReference[oaicite:8]{index=8}  
- 관련 Kill Switch: **KS-1, KS-2, KS-5** :contentReference[oaicite:9]{index=9}  
- 완료 기준: **한 번의 추천 사이클에서 사용자가 화면만 보고 승인/거절을 결정할 수 있을 정도로 이유, 상태, 다음 액션이 끊기지 않고 이해된다.**

## 4단계. factor/ML 확장 및 4070s 검증
Phase 1에서 살려온 독립 ML 자산을 새 구조에 연결하고, 첫 factor 추가 난이도와 실제 연산 부하를 함께 검증한다. 핵심은 “확장 가능한가”와 “4070s가 실제로 돌아가는가”를 동시에 보는 것이다.  
- 연결 Open Question: **Q1, L-2** :contentReference[oaicite:10]{index=10}  
- 관련 Kill Switch: **KS-3, KS-8, KS-9** :contentReference[oaicite:11]{index=11}  
- 완료 기준: **새 factor 1개를 추가해 비교 가능한 ML 산출물 1세트를 만들고, 4070s에서 실제 배치 실행 로그 또는 사용 증거를 확보한다.**

## 5단계. 저빈도 운영 정착 및 예외 감시 편입
기본 운영은 K6/EOD 저빈도 루프로 유지하되, **급변 상황은 spike_watch / holding_watch로 별도 감시**하여 추가 알림을 허용한다. 이 예외 감시는 기본 승인 구조를 우회하는 자동 매매가 아니라, **추가 관찰·추가 알림 축**으로만 작동해야 한다.  
- 연결 Open Question: **Q2, Q3 최종 판정** :contentReference[oaicite:12]{index=12}  
- 관련 Kill Switch: **KS-4, KS-5, KS-6** :contentReference[oaicite:13]{index=13}  
- 완료 기준: **기본 저빈도 운영과 급변 예외 감시가 함께 동작하면서도 알림 과다와 과잉 교체 없이 성과 판정이 가능하다.**

이 MASTER_PLAN의 목적은 기능을 벌리는 것이 아니라, **데이터 수집 → PENDING 초안 → 인간 승인 → OCI 전달/알림 → factor 확장 → 저빈도 운영 + 예외 감시**의 짧고 검증 가능한 루프를 완성하는 데 있다. Open Question은 질문으로 남겨 관리하고, Kill Switch가 발동하면 토론하지 말고 즉시 멈춘다. :contentReference[oaicite:14]{index=14} :contentReference[oaicite:15]{index=15}