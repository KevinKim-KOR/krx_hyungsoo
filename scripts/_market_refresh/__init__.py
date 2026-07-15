"""scripts/_market_refresh — refresh_market_timeseries CLI 서브커맨드 helper.

Cleanup / FIX r7 Round 2 에서 `scripts/refresh_market_timeseries.py` (686줄)
KS-10 trigger 해소를 위해 VIX 서브커맨드를 이 helper 로 분리.

**최소 분리**: 신규 기능·threshold·source 추가 없음. CLI 계약 · 인자 · 출력 유지.
"""
