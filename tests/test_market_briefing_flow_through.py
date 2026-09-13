"""POC3-OPS-02B-2 — 시장 브리핑 **러너 flow-through**.

계약 단위 테스트(`test_market_briefing_contracts.py`)는 조립 함수를 직접 부른다.
여기서는 **러너 `run()` 을 실제로 태워** §3-e 조립 → flag guard → §6-c 판정 →
발송 → §8 상태 저장까지 한 줄로 이어지는지 본다. 단위로 통과해도 배선이 틀리면
운영에서 안 돈다.

## 여기서만 잡히는 것

| 검증 | 왜 단위로는 못 잡나 |
|---|---|
| flag guard **뒤에서** 판정 | 앞에서 부르면 `non_trading_day` 가
  `push_kind_disabled` 를 가로챈다 |
| Telegram **전체 성공 뒤에만** 상태 저장 | `save_state_after_send` 호출 위치는 러너에만 있다 |
| 미발송 시 상태 미저장 | 조립 결과만 봐서는 저장 여부를 알 수 없다 |
| 라이브 경로 미접근 | `STATE_DIR` 해석이 러너 런타임에서 일어난다 |

## 격리

`conftest` autouse 가드가 라이브 state·DB·KRX API·OCI 를 이미 막는다. 여기서는
Telegram sender 를 stub 해 **발송 0건**으로 둔다.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.market_briefing import flow, krx_store, meta_gate
from app.runtime_param_store import activate_param_version, create_param_version
from app.three_push_runtime_param import build_manual_seed_param

TODAY_TRADING = "2026-09-18"
PRIOR_TRADING = "2026-09-17"

AXIS = [f"2026-08-{d:02d}" for d in range(3, 32)] + [
    f"2026-09-{d:02d}" for d in (1, 2, 3, 4, 7, 8, 9, 10, 11, 14, 15, 16, 17, 18)
]
TICKERS = ("069500", "102110")


def _seed_active_param() -> None:
    param = build_manual_seed_param()
    version_id, _, _ = create_param_version(param.to_dict())
    activate_param_version(version_id, activated_by="test")


def _official_csv(path: Path) -> Path:
    path.write_bytes(
        (
            "단축코드,기초지수명,지수산출기관,기초자산분류,추적배수,복제방법,"
            "한글종목약명\n"
            "069500,코스피200,KRX,주식,일반,실물(패시브),KODEX 200\n"
            "102110,코스피200,KRX,주식,일반,실물(패시브),TIGER 200\n"
        ).encode("cp949")
    )
    return path


def _seed_window(db: Path, *, through: str = PRIOR_TRADING) -> None:
    """직전 거래일까지 적재한다 — 최신성 Gate 를 통과해야 후보가 나온다."""
    days = [d for d in AXIS if d <= through]
    for i, day in enumerate(days):
        bas = day.replace("-", "")
        close = "11000" if i >= len(days) - 5 else "10000"
        rows = [{"ISU_CD": t, "BAS_DD": bas, "TDD_CLSPRC": close} for t in TICKERS]
        krx_store.upsert_snapshot(
            krx_store.validate_snapshot(rows, expected_date=bas), db_path=db
        )


def _install(
    monkeypatch,
    tmp_path: Path,
    *,
    kind_enabled: bool = True,
    today: str = TODAY_TRADING,
    window_through: str = PRIOR_TRADING,
    sp500: tuple[float | None, str | None, bool] = (1.24, "2026-09-17", True),
):
    """러너를 태우기 위한 최소 배선. 라이브 경로는 하나도 쓰지 않는다."""
    from app.three_push_runtime import runner_market_briefing as mb
    from scripts import run_three_push_runtime_oci as runner

    _seed_active_param()

    state_dir = tmp_path / "three_push"
    state_dir.mkdir(parents=True, exist_ok=True)
    meta_dir = tmp_path / "market_meta"
    meta_dir.mkdir(parents=True, exist_ok=True)
    db = tmp_path / "krx.sqlite"
    _seed_window(db, through=window_through)

    (meta_dir / "krx_trading_days_2026.csv").write_text(
        "date\n" + "\n".join(AXIS) + "\n", encoding="utf-8"
    )
    _official_csv(meta_dir / mb.OFFICIAL_ETF_CSV)
    meta_gate.save_consistency(
        meta_gate.ConsistencyResult(
            status=meta_gate.STATUS_OK,
            api_ticker_count=2,
            csv_ticker_count=2,
            exact_match_count=2,
            join_coverage=1.0,
            api_basis_date=PRIOR_TRADING.replace("-", ""),
        ),
        state_dir / meta_gate.CONSISTENCY_STATE_NAME,
    )

    monkeypatch.setattr(mb, "STATE_DIR", state_dir)
    monkeypatch.setattr(mb, "MARKET_META_DIR", meta_dir)
    monkeypatch.setattr(mb, "_sp500_input", lambda _today: sp500)

    # 캘린더·가격 DB 경로를 조립에 주입한다 (라이브 미접근).
    real_assemble = mb.assemble

    def _assemble(record, **kw):
        kw.setdefault("state_dir", state_dir)
        kw.setdefault("meta_dir", meta_dir)
        kw.setdefault("db_path", db)
        return real_assemble(record, **kw)

    monkeypatch.setattr(mb, "assemble", _assemble)

    real_flow = flow.assemble_market_briefing

    def _flow(**kw):
        kw.setdefault("calendar_dir", meta_dir)
        return real_flow(**kw)

    monkeypatch.setattr(flow, "assemble_market_briefing", _flow)

    monkeypatch.setattr(runner, "_HISTORY_PATH", tmp_path / "history.jsonl")
    monkeypatch.setattr(runner, "kst_today_date", lambda: today)

    sent: list[str] = []

    def _send(text: str):
        sent.append(text)
        return (True, None, False)

    monkeypatch.setattr(runner, "telegram_send", _send)
    monkeypatch.setenv("PUSH_AUTOSEND_ENABLED", "true")
    monkeypatch.setenv(
        "PUSH_AUTOSEND_MARKET_BRIEFING_ENABLED", "true" if kind_enabled else "false"
    )
    return runner, sent, state_dir


def _state(state_dir: Path) -> dict | None:
    p = state_dir / flow.STATE_NAME
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


# ── 발송 경로 ────────────────────────────────────────────────────────────────


def test_flow_through_sends_and_saves_state(tmp_path, monkeypatch):
    """§3-e → §6-c → 발송 → §8 저장까지 한 줄로 이어진다."""
    runner, sent, state_dir = _install(monkeypatch, tmp_path)
    record = runner.run("market_briefing", "send")

    assert record["status"] == "sent", record
    assert len(sent) == 1, sent
    body = sent[0]
    assert body.startswith("[시장 흐름 브리핑]")
    assert "오늘 볼 기초지수" in body
    assert "KODEX 200" in body  # 추종 ETF 약명 (사용자 확정 2026-09-13)
    assert f"국내 {PRIOR_TRADING} 종가" in body

    saved = _state(state_dir)
    assert saved is not None, "발송 성공했는데 상태가 저장되지 않았다"
    assert saved["state_fingerprint"] == "UP#KRX|코스피200"
    assert saved["sent_date_kst"] == TODAY_TRADING
    assert record.get("market_briefing_state_saved") is True


def test_flow_through_repeat_is_suppressed_and_state_untouched(tmp_path, monkeypatch):
    """같은 상태가 이어지면 **두 번째는 안 보낸다**. 상태도 그대로."""
    runner, sent, state_dir = _install(monkeypatch, tmp_path)
    assert runner.run("market_briefing", "send")["status"] == "sent"
    first = _state(state_dir)

    record = runner.run("market_briefing", "send")
    assert record["status"] == "skipped"
    assert record["reason"] == flow.REASON_NO_CHANGE
    assert len(sent) == 1, "억제되어야 하는데 다시 보냈다"
    assert _state(state_dir) == first


# ── 보호 분기 ────────────────────────────────────────────────────────────────


def test_flag_guard_wins_over_non_trading_day(tmp_path, monkeypatch):
    """flag 가 꺼져 있으면 **휴장일이어도** `push_kind_disabled` 다.

    판정을 flag guard 앞에서 하면 `non_trading_day` 가 기존 계약을 가로챈다.
    러너 §6-c 순서를 고정하는 테스트다.
    """
    runner, sent, state_dir = _install(
        monkeypatch, tmp_path, kind_enabled=False, today="2026-09-19"  # 토요일
    )
    record = runner.run("market_briefing", "send")
    assert record["status"] == "skipped"
    assert record["reason"] == "push_kind_disabled", record
    assert sent == []
    assert _state(state_dir) is None


def test_non_trading_day_skips_without_send_or_state(tmp_path, monkeypatch):
    runner, sent, state_dir = _install(monkeypatch, tmp_path, today="2026-09-19")
    record = runner.run("market_briefing", "send")
    assert record["status"] == "skipped"
    assert record["reason"] == "non_trading_day"
    assert sent == []
    assert _state(state_dir) is None


def test_stale_window_does_not_send_kr_basis(tmp_path, monkeypatch):
    """창이 오래되면 국내 기준일을 본문에 적지 않는다 (사용자 지적 2026-09-13)."""
    runner, sent, state_dir = _install(
        monkeypatch, tmp_path, window_through="2026-08-31"
    )
    record = runner.run("market_briefing", "send")
    assert record["status"] == "sent", record  # 전망은 살아 있다
    body = sent[0]
    assert "국내" not in body, body
    assert "오늘 볼 기초지수" not in body


def test_telegram_failure_does_not_save_state(tmp_path, monkeypatch):
    """발송 실패면 상태를 저장하지 않는다 — 다음 실행이 다시 시도해야 한다."""
    runner, sent, state_dir = _install(monkeypatch, tmp_path)
    monkeypatch.setattr(
        runner, "telegram_send", lambda text: (False, "boom: HTTP 500", False)
    )
    record = runner.run("market_briefing", "send")
    assert record["status"] == "failed"
    assert _state(state_dir) is None, "발송 실패인데 상태가 저장됐다"


def test_partial_delivery_does_not_save_state(tmp_path, monkeypatch):
    """부분 전송도 성공이 아니다. 상태 저장 금지."""
    runner, sent, state_dir = _install(monkeypatch, tmp_path)
    monkeypatch.setattr(
        runner,
        "telegram_send",
        lambda text: (False, "partial_delivery_at_chunk_1_of_2: HTTP 500", True),
    )
    record = runner.run("market_briefing", "send")
    assert record["partial_delivery"] is True
    assert _state(state_dir) is None


def test_dry_run_sends_nothing_and_saves_nothing(tmp_path, monkeypatch):
    runner, sent, state_dir = _install(monkeypatch, tmp_path)
    record = runner.run("market_briefing", "dry-run")
    assert record["telegram_sent"] is False
    assert sent == []
    assert _state(state_dir) is None


def test_repo_state_file_is_not_touched(tmp_path, monkeypatch):
    """러너가 **저장소 실경로** `state/three_push` 를 건드리지 않는다.

    `conftest` 가 이미 `STATE_DIR` 를 격리하므로 모듈 상수를 읽으면 임시 경로가
    나온다. 그러면 "라이브를 안 건드렸다" 를 증명하지 못한다 — 그래서 저장소
    경로를 **파일 위치에서 직접** 계산해 비교한다.
    """
    repo_live = (
        Path(__file__).resolve().parents[1] / "state" / "three_push" / flow.STATE_NAME
    )
    before = repo_live.read_bytes() if repo_live.exists() else None
    runner, _, state_dir = _install(monkeypatch, tmp_path)
    runner.run("market_briefing", "send")
    after = repo_live.read_bytes() if repo_live.exists() else None
    assert before == after, f"저장소 상태 파일이 바뀌었다: {repo_live}"
    assert _state(state_dir) is not None  # 격리 경로에는 저장됐다
