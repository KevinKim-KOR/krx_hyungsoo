"""시세 as-of 결측 → quote 실패.

`tests/test_low_frequency_push_operation.py` (1548줄) 가 KS-10 테스트 임계를
넘어 책임별로 분해한 것이다. **test 본문·docstring·assertion 을 고치지 않았다.**
helper 는 `tests/low_frequency_push/_fixtures.py` 에 있다.
"""

from __future__ import annotations


def test_market_naver_missing_asof_fails_quote(monkeypatch):
    """A+ 재정정: Naver 응답에 localTradedAt 없으면 quote 실패 (missing_asof)."""
    from app import market_naver as mn

    class _FakeResp:
        status_code = 200

        def json(self):
            return {"stockName": "종목X", "closePrice": "1,000"}

    class _FakeClient:
        def __init__(self, *a, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, url, **kw):
            return _FakeResp()

    monkeypatch.setattr(mn.httpx, "Client", _FakeClient)
    results = mn.fetch_many(["000660"], timeout=1.0)
    assert len(results) == 1
    assert results[0].quote is None
    assert results[0].reason == "missing_asof"
