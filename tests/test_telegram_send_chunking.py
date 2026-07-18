"""Telegram sender chunk 분할 focused test (Holdings Controlled Send v1 FIX).

관련 계약:
- 한도 이하: 단일 chunk, header 없음.
- 초과: 줄바꿈 경계 우선 분할, (i/N) header 부착.
- 순수 분할만 수행 (누락/요약/재작성 없음).
- 모든 chunk 성공해야 sent=true.
- 하나라도 실패하면 partial_delivery, 후속 chunk 미호출, 자동 재시도 없음.
- Token/chat_id 비노출 계약 유지.
"""

from __future__ import annotations

from typing import Any

import pytest

from app import three_push_runner_common as trc

# ── _split_message_for_telegram ─────────────────────────────────────────────


def test_split_returns_single_chunk_when_under_limit() -> None:
    text = "A" * 100
    assert trc._split_message_for_telegram(text) == [text]


def test_split_boundary_at_limit_exact() -> None:
    text = "A" * trc._TELEGRAM_MESSAGE_MAX_CHARS
    assert trc._split_message_for_telegram(text) == [text]


def test_split_preserves_content_when_over_limit() -> None:
    lines = [f"line-{i:04d} " + ("x" * 50) for i in range(200)]
    text = "\n".join(lines)
    chunks = trc._split_message_for_telegram(text)
    assert len(chunks) >= 2
    body_lines: list[str] = []
    for c in chunks:
        assert c.startswith("(")
        header, _, body = c.partition("\n")
        assert header.endswith(f"/{len(chunks)})")
        body_lines.extend(body.split("\n"))
    assert body_lines == lines


def test_split_headers_ordered_1_of_N() -> None:
    text = "\n".join("x" * 100 for _ in range(200))
    chunks = trc._split_message_for_telegram(text)
    total = len(chunks)
    for i, c in enumerate(chunks, start=1):
        assert c.startswith(f"({i}/{total})\n")


def test_split_no_chunk_exceeds_limit() -> None:
    text = "\n".join("y" * 200 for _ in range(300))
    chunks = trc._split_message_for_telegram(text)
    for c in chunks:
        assert len(c) <= trc._TELEGRAM_MESSAGE_MAX_CHARS + 16  # header 여유


def test_split_hard_splits_a_single_oversized_line() -> None:
    long_line = "Z" * (trc._TELEGRAM_MESSAGE_MAX_CHARS + 500)
    chunks = trc._split_message_for_telegram(long_line)
    assert len(chunks) >= 2
    rejoined = ""
    for c in chunks:
        _, _, body = c.partition("\n")
        rejoined += body
    assert rejoined == long_line


def test_split_holdings_5506_yields_two_chunks_from_realistic_body() -> None:
    lines: list[str] = []
    lines.append("[보유 종목 관찰 브리핑]\n\n기준 시각: 7월 18일 15:47\n")
    for i in range(70):
        lines.append(
            f"• 종목-{i:02d} (2026-07-03 기준): 현재 Market Discovery TOP-N 미포함 "
            f"· 최근 20거래일 {'-' if i % 2 else '+'}{i * 0.13:.2f}%."
        )
    text = "\n".join(lines)
    assert len(text) > trc._TELEGRAM_MESSAGE_MAX_CHARS
    chunks = trc._split_message_for_telegram(text)
    assert len(chunks) >= 2
    for c in chunks:
        assert len(c) <= trc._TELEGRAM_MESSAGE_MAX_CHARS + 16


# ── telegram_send: HTTP mock ────────────────────────────────────────────────


class _FakeSendRecorder:
    def __init__(self, results: list[tuple[bool, Any]]) -> None:
        self._results = list(results)
        self.calls: list[str] = []

    def __call__(self, token: str, chat_id: str, text: str) -> tuple[bool, Any]:
        self.calls.append(text)
        if not self._results:
            raise AssertionError("send called more times than expected")
        return self._results.pop(0)


@pytest.fixture()
def env_with_valid_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "1234567890:AAAAAAAAAAAAAAAAAAAAAAAAAAAA")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "9999999")


def test_telegram_send_single_chunk_success(
    env_with_valid_token: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    rec = _FakeSendRecorder([(True, None)])
    monkeypatch.setattr(trc, "_telegram_send_one", rec)
    ok, err = trc.telegram_send("short body")
    assert (ok, err) == (True, None)
    assert rec.calls == ["short body"]


def test_telegram_send_short_body_no_header(
    env_with_valid_token: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    rec = _FakeSendRecorder([(True, None)])
    monkeypatch.setattr(trc, "_telegram_send_one", rec)
    text = "line-1\nline-2\nline-3"
    trc.telegram_send(text)
    assert rec.calls == [text]
    assert not rec.calls[0].startswith("(1/1)")


def test_telegram_send_multi_chunk_all_success(
    env_with_valid_token: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    text = "\n".join("x" * 500 for _ in range(20))
    expected_chunks = len(trc._split_message_for_telegram(text))
    assert expected_chunks >= 2
    rec = _FakeSendRecorder([(True, None)] * expected_chunks)
    monkeypatch.setattr(trc, "_telegram_send_one", rec)
    ok, err = trc.telegram_send(text)
    assert (ok, err) == (True, None)
    assert len(rec.calls) == expected_chunks
    for i, c in enumerate(rec.calls, start=1):
        assert c.startswith(f"({i}/{expected_chunks})\n")


def test_telegram_send_first_chunk_fail_stops_and_reports_partial(
    env_with_valid_token: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    rec = _FakeSendRecorder([(False, "other_non_secret_error: HTTP 400")])
    monkeypatch.setattr(trc, "_telegram_send_one", rec)
    text = "\n".join("x" * 500 for _ in range(20))
    ok, err = trc.telegram_send(text)
    assert ok is False
    assert err is not None
    assert err.startswith("partial_delivery_at_chunk_1_of_")
    assert "HTTP 400" in err
    assert len(rec.calls) == 1


def test_telegram_send_second_chunk_fail_stops_before_third(
    env_with_valid_token: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    rec = _FakeSendRecorder([(True, None), (False, "other_non_secret_error: HTTP 500")])
    monkeypatch.setattr(trc, "_telegram_send_one", rec)
    text = "\n".join("x" * 500 for _ in range(30))
    ok, err = trc.telegram_send(text)
    assert ok is False
    assert err is not None
    assert err.startswith("partial_delivery_at_chunk_2_of_")
    assert len(rec.calls) == 2  # 세 번째는 호출되지 않음


def test_telegram_send_single_chunk_failure_keeps_original_error(
    env_with_valid_token: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    rec = _FakeSendRecorder([(False, "other_non_secret_error: HTTP 400")])
    monkeypatch.setattr(trc, "_telegram_send_one", rec)
    ok, err = trc.telegram_send("short body")
    assert ok is False
    assert err == "other_non_secret_error: HTTP 400"


def test_telegram_send_placeholder_token_rejected_before_split(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "TOKEN")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "9999999")
    called: list[Any] = []

    def _boom(*a: Any, **k: Any) -> Any:
        called.append((a, k))
        raise AssertionError("_telegram_send_one must not be called")

    monkeypatch.setattr(trc, "_telegram_send_one", _boom)
    ok, err = trc.telegram_send("body")
    assert ok is False
    assert err is not None
    assert "invalid_or_placeholder_bot_token" in err
    assert called == []


def test_telegram_send_token_in_message_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = "1234567890:AAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", token)
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "9999999")
    monkeypatch.setattr(trc, "_telegram_send_one", lambda *a, **k: (True, None))
    ok, err = trc.telegram_send(f"body contains {token}")
    assert ok is False
    assert err == "message_text 에 token/chat_id 노출 — 발송 차단"
