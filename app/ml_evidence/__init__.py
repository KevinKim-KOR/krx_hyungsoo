"""POC6-05 — 지속 시장 자료 수집 · ML 연구 증거 보관 연결.

| 모듈 | 책임 |
|---|---|
| `store` | 내용 해시 object · 완료 묶음 manifest · 재생 가능한 색인 · 잠금 · 검사 · 복구 확인 |
| `daily` | OCI 일일 수집(목록 · 네이버 수신 창 · 기존 표 delta · 수집 기록 · 날짜 축 · 시장 흐름) |
| `daily_naver` | ETF 목록 · 네이버/FDR 수신 창(순차 · 간격 · 멈춤 규칙 · 시간 예산) |
| `research` | 기존 연구(POC6-02 · 03 · 04) 공식 파일 등록 |
| `transfer` | PC ↔ OCI 가져오기 · 연구 업로드 · 업로드 받기 |
| `export` | 기준 시각 이하 공개 판 고르기(연구 입력) |
| `status` | 보관 상태 읽기(목록 · 자료원별 최신일 · 실패 · 연구 연결 · 두 번째 사본) |
| `daily_tables` · `daily_flow` | 기존 표 delta · 수집 기록 / 원/달러 · WTI · 수급 capture |

학습 · 추론 · 성과 계산은 없다. torch · sklearn · 연구 모델 모듈을 불러오지 않는다.
"""
