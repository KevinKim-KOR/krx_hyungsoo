POC6-29 보완 — 빠른 시세 시험 자료(네이버 공개 응답 사본)

개발자가 2026-11-12 오후 네이버 공개 시세 응답을 받아 아래 칸만 남겨 옮긴 사본이다(값은 손대지 않음).
시험은 이 사본과 가짜 조회 함수만 쓴다 — 네트워크를 부르지 않는다.

- kospi_1536.json   : https://m.stock.naver.com/api/index/KOSPI/basic  (15:36 · 마감)
- kospi_1558.json   : 같은 주소 15:58 다시 받음 — 원천 표기 시각만 바뀌고 값 · 등락 · 장 상태는 같다
- kosdaq_1536.json  : https://m.stock.naver.com/api/index/KOSDAQ/basic (15:36 · 마감)
- kodex200_1535.json: https://m.stock.naver.com/api/stock/069500/basic (15:35:18 · 마감)

남긴 칸: stockName · closePrice · compareToPreviousClosePrice · fluctuationsRatio · localTradedAt ·
marketStatus · itemCode · delayTimeName.
장중(OPEN) · 손상 응답은 시험 안에서 만든 합성 자료이며, 시험 코드에 '합성'으로 표시한다.
