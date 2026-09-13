"""POC3-OPS-02B-2 — 08:00 시장 흐름 브리핑.

| 모듈 | 책임 |
|---|---|
| `krx_store` | KRX 무조정 가격 **별도 계열** 저장소 |
| `meta_gate` | 07:20 정합성 결과 **소비 경계** · API↔CSV 판정 |
| `calendar` | 국내 거래일 snapshot 로더 · 거래일 Gate |
| `evidence` | `SP500_SIGN_V1` 방향 + 기초지수 산출 |
| `render` | 본문 · 부분 산출 · 안내 문구 |
| `flow` | 조립 흐름 · fingerprint · 억제 · 상태 |
"""
