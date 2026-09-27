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

import pytest

from app.market_briefing import flow, krx_store, meta_gate, render
from app.market_briefing.official_csv import EXPECTED_HEADER
from app.runtime_param_store import activate_param_version, create_param_version
from app.three_push_runtime_param import build_manual_seed_param

TODAY_TRADING = "2026-09-18"
PRIOR_TRADING = "2026-09-17"

AXIS = [f"2026-08-{d:02d}" for d in range(3, 32)] + [
    f"2026-09-{d:02d}" for d in (1, 2, 3, 4, 7, 8, 9, 10, 11, 14, 15, 16, 17, 18, 21)
]
TICKERS = ("069500", "102110")
# 운영 resolver 가 고르는 이름 · 17컬럼(POC3-02D-OPS-01 C1).
CSV_NAME = "krx_etf_basic_20260909.csv"


def _seed_active_param() -> None:
    param = build_manual_seed_param()
    version_id, _, _ = create_param_version(param.to_dict())
    activate_param_version(version_id, activated_by="test")


def _csv_lines(rows: list[tuple[str, str, str]]) -> list[str]:
    """`(단축코드, 기초지수명, 한글종목약명)` → 승인 파일과 같은 17컬럼 행."""
    lines = [",".join(EXPECTED_HEADER)]
    for code, index_name, short in rows:
        r = dict.fromkeys(EXPECTED_HEADER, "-")
        r.update(
            {
                "단축코드": code,
                "기초지수명": index_name,
                "지수산출기관": "KRX",
                "기초자산분류": "주식",
                "추적배수": "일반",
                "복제방법": "실물(패시브)",
                "한글종목약명": short,
            }
        )
        lines.append(",".join(r[h] for h in EXPECTED_HEADER))
    return lines


def _official_csv(path: Path) -> Path:
    rows = [("069500", "코스피200", "KODEX 200"), ("102110", "코스피200", "TIGER 200")]
    path.write_bytes(("\n".join(_csv_lines(rows)) + "\n").encode("cp949"))
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
    _official_csv(meta_dir / CSV_NAME)
    # 07:20 이 **오늘 창**으로 남긴 판정(설계자 R2 Q27) — 적재된 창과 같다.
    window = krx_store.resolve_window(db_path=db)
    meta_gate.save_consistency(
        meta_gate.ConsistencyResult(
            status=meta_gate.STATUS_OK,
            api_ticker_count=2,
            csv_ticker_count=2,
            exact_match_count=2,
            join_coverage=1.0,
            api_basis_date=PRIOR_TRADING.replace("-", ""),
            evaluated_api_basis_date=window.latest.replace("-", ""),
            evaluated_window_d20_date=window.d20,
            evaluated_at_kst=f"{today}T07:20:00+09:00",
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


def test_same_day_rerun_is_blocked_by_registry(tmp_path, monkeypatch):
    """같은 거래일 재실행은 막는다. **다만 사유는 내용 동일이 아니라 중복 실행**이다.

    POC3-02B-OPS-03 — 중복 차단은 `registry_key(push_kind, param_id,
    runtime_date_kst)` 가 한다. 콘텐츠 fingerprint 는 막지 않는다.
    """
    runner, sent, state_dir = _install(monkeypatch, tmp_path)
    assert runner.run("market_briefing", "send")["status"] == "sent"
    first = _state(state_dir)

    record = runner.run("market_briefing", "send")
    assert record["status"] == "skipped"
    assert record["reason"] == "duplicate_runtime", record
    assert record["reason"] != flow.REASON_NO_CHANGE
    assert len(sent) == 1, "같은 날 두 번 보냈다"
    assert _state(state_dir) == first


def test_next_trading_day_sends_even_if_content_identical(tmp_path, monkeypatch):
    """**다음 거래일에는 내용이 같아도 보낸다.** 이번 수정의 핵심이다."""
    runner, sent, state_dir = _install(monkeypatch, tmp_path)
    assert runner.run("market_briefing", "send")["status"] == "sent"
    saved = _state(state_dir)

    # 같은 입력 · 날짜만 다음 거래일로.
    monkeypatch.setattr(runner, "kst_today_date", lambda: "2026-09-21")
    record = runner.run("market_briefing", "send")

    assert record["status"] == "sent", record
    assert len(sent) == 2, "다음 거래일인데 보내지 않았다"
    assert sent[1] == sent[0], "같은 내용이어야 한다 (억제만 풀린 것)"
    assert _state(state_dir)["sent_date_kst"] == "2026-09-21"
    assert _state(state_dir)["state_fingerprint"] == saved["state_fingerprint"]


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


# ── POC3-02D-OPS-01 C1 — pending gate: 07:20 판정 → 08:00 소비 ──────────────────
# d20 종가가 없는 신규 상장 ETF 가 API 에만 있어도 기초지수 구역이 살아 있고,
# 후보 수치는 그 ETF 가 없을 때와 **같다**(설계자 Q1 (c) · 수치 영향 0 결속).

PENDING_TICKER = "0227L0"
# CSV 를 20종으로 넓힌다 — 신규 1종이 API 에 더해져도 coverage 20/21 ≈ 0.952.
KOSDAQ = tuple(f"{300000 + i}" for i in range(18))


def _official_csv_wide(path: Path, *, with_pending_row: bool = False) -> Path:
    rows = [("069500", "코스피200", "KODEX 200"), ("102110", "코스피200", "TIGER 200")]
    rows += [(t, "코스닥150", f"ETF{t}") for t in KOSDAQ]
    if with_pending_row:
        # 신규 ETF 가 CSV 에 **있는** 세계 — 코스피200 그룹 후보가 될 수 있는 행.
        rows.append((PENDING_TICKER, "코스피200", "NEWETF"))
    path.write_bytes(("\n".join(_csv_lines(rows)) + "\n").encode("cp949"))
    return path


def _run_0720(
    base: Path,
    *,
    with_pending: bool,
    csv_has_pending: bool = False,
    pending_from: str = "20260915",
) -> dict:
    """07:20 을 실제로 태운다 — 직전 거래일 응답 **하나**로 적재 + 정합성 판정.

    `_install` 과 같은 배치(`three_push/` · `market_meta/` · `krx.sqlite`)를 쓴다.
    `_install` 이 먼저 깐 창은 같은 `(date, ticker)` 로 모두 덮어쓴다.
    """
    from datetime import date

    from app.market_briefing import krx_sync

    meta_dir, state_dir = base / "market_meta", base / "three_push"
    meta_dir.mkdir(parents=True, exist_ok=True)
    state_dir.mkdir(parents=True, exist_ok=True)
    db = base / "krx.sqlite"
    (meta_dir / "krx_trading_days_2026.csv").write_text(
        "date\n" + "\n".join(AXIS) + "\n", encoding="utf-8"
    )
    _official_csv_wide(meta_dir / CSV_NAME, with_pending_row=csv_has_pending)
    days = [d.replace("-", "") for d in AXIS if d <= PRIOR_TRADING]

    def _day_rows(i: int, bas: str) -> list[dict]:
        # 두 그룹 모두 우상향 — 5일·20일 수익률이 양수라 후보 2개가 나온다.
        rows = [
            {
                "ISU_CD": t,
                "BAS_DD": bas,
                "TDD_CLSPRC": str(10000 + 50 * i),
                "IDX_IND_NM": "코스피200",
            }
            for t in TICKERS
        ] + [
            {
                "ISU_CD": t,
                "BAS_DD": bas,
                "TDD_CLSPRC": str(20000 + 30 * i),
                "IDX_IND_NM": "코스닥150",
            }
            for t in KOSDAQ
        ]
        if with_pending and bas >= pending_from:  # 기본 첫 적재 09-15 · d20 없음
            rows.append(
                {
                    "ISU_CD": PENDING_TICKER,
                    "BAS_DD": bas,
                    "TDD_CLSPRC": "5000",
                    "IDX_IND_NM": "코스피200",
                }
            )
        return rows

    for i, bas in enumerate(days[:-1]):
        krx_store.upsert_snapshot(
            krx_store.validate_snapshot(_day_rows(i, bas), expected_date=bas),
            db_path=db,
        )
    env = base / ".env"
    env.write_text("KRX_API_KEY=dummy\n", encoding="utf-8")
    last = days[-1]
    return krx_sync.sync_krx_daily(
        today=date.fromisoformat(TODAY_TRADING),
        meta_dir=meta_dir,
        consistency_path=state_dir / meta_gate.CONSISTENCY_STATE_NAME,
        db_path=db,
        env_path=env,
        fetcher=lambda bas, key: (_day_rows(len(days) - 1, bas) if bas == last else []),
    )


def test_pending_new_listing_keeps_index_block_through_runner(tmp_path, monkeypatch):
    """07:20 이 pending 으로 판정하면 08:00 본문에 '오늘 볼 기초지수' 가 붙는다."""
    runner, sent, state_dir = _install(monkeypatch, tmp_path)
    krx = _run_0720(tmp_path, with_pending=True)
    assert krx["consistency_status"] == meta_gate.STATUS_OK, krx

    record = runner.run("market_briefing", "send")
    assert record["status"] == "sent", record
    assert record["index_status"] == "ok", record["index_status"]
    body = sent[0]
    assert "공식 기준정보 갱신이 필요해" not in body
    assert "오늘 볼 기초지수" in body
    assert f"국내 {PRIOR_TRADING} 종가" in body
    assert PENDING_TICKER not in body
    mc = record["meta_consistency"]
    assert mc["api_only"] == [PENDING_TICKER]
    # 09-15 · 16 · 17 적재 3거래일 — d20 까지 18거래일(R2 Q23 · 5 초과 → due 아님).
    assert mc["api_only_pending"] == [
        {
            "ticker": PENDING_TICKER,
            "first_loaded": "2026-09-15",
            "stored_trading_day_count": 3,
            "remaining_trading_days": 18,
        }
    ]
    assert mc["refresh_due"] is False
    assert render.CSV_REFRESH_NOTICE not in body


def _assemble_0800(base: Path) -> flow.BriefingOutcome:
    return flow.assemble_market_briefing(
        today_kst=TODAY_TRADING,
        runtime_kst=None,
        state_path=base / "three_push" / flow.STATE_NAME,
        consistency_path=base / "three_push" / meta_gate.CONSISTENCY_STATE_NAME,
        meta_dir=base / "market_meta",
        sp500_return_pct=1.24,
        sp500_asof=PRIOR_TRADING,
        sp500_fresh=True,
        calendar_dir=base / "market_meta",
        db_path=base / "krx.sqlite",
    )


def _index_block(base: Path):
    return flow._index_block(
        meta_gate.load_consistency(
            base / "three_push" / meta_gate.CONSISTENCY_STATE_NAME
        ),
        csv_rows=meta_gate.load_official_csv(base / "market_meta" / CSV_NAME),
        db_path=base / "krx.sqlite",
        today_kst=TODAY_TRADING,
        calendar_dir=base / "market_meta",
    )


def test_pending_ticker_has_zero_numeric_impact(tmp_path):
    """pending ETF 가 있는 세계(A) · 없는 세계(B) · **CSV 에 그 행이 있는 세계(C)**
    의 후보가 수치까지 같다.

    A 대 B 만 보면 두 세계 모두 CSV 에 그 ticker 가 없어 늘 같다(검토 지적).
    C 가 결속의 핵심이다 — d20 종가가 없는 ETF 는 CSV 에 행이 생겨도 `n` 에
    들어가지 못한다는 pending gate 의 전제를 실제 계산으로 확인한다.
    """
    with_dir, without_dir = tmp_path / "with", tmp_path / "without"
    in_csv_dir = tmp_path / "in_csv"
    # 첫 적재 09-01 — 이 축에서 d5(09-10) 종가는 **있고** d20(08-24) 종가는 없다.
    # 그래야 C 에서 그 ETF 를 후보에서 빼는 것이 오직 d20 요구다.
    krx_a = _run_0720(with_dir, with_pending=True, pending_from="20260901")
    krx_b = _run_0720(without_dir, with_pending=False)
    krx_c = _run_0720(
        in_csv_dir, with_pending=True, csv_has_pending=True, pending_from="20260901"
    )
    assert krx_a["consistency_status"] == meta_gate.STATUS_OK, krx_a
    assert krx_b["consistency_status"] == meta_gate.STATUS_OK, krx_b
    assert krx_c["consistency_status"] == meta_gate.STATUS_OK, krx_c

    idx_a, idx_b = _index_block(with_dir), _index_block(without_dir)
    idx_c = _index_block(in_csv_dir)
    assert idx_a.status == idx_b.status == idx_c.status == "ok"
    assert len(idx_a.candidates) == 2
    assert idx_a.candidates == idx_b.candidates  # 수익률 · n · 약명까지
    assert (
        idx_a.candidates == idx_c.candidates
    ), "d20 없는 ETF 가 CSV 행으로 n 에 들어갔다"
    assert idx_c.diagnostics["api_only_pending_count"] == 0
    assert idx_a.price_asof == idx_b.price_asof == PRIOR_TRADING
    for k in ("group_count", "candidate_count", "lookback_dates"):
        assert idx_a.diagnostics[k] == idx_b.diagnostics[k], k
    assert idx_a.diagnostics["api_only_pending_count"] == 1
    assert idx_b.diagnostics["api_only_pending_count"] == 0

    out_a, out_b = _assemble_0800(with_dir), _assemble_0800(without_dir)
    assert out_a.should_send and out_b.should_send
    assert out_a.message_text == out_b.message_text
    assert out_a.fingerprint == out_b.fingerprint
    assert (
        out_a.diagnostics["index_candidates"] == out_b.diagnostics["index_candidates"]
    )


# ── POC3-02D-OPS-01 C1 — R2 Q27 판정 창 확인 · Q24 CSV 갱신 안내 ─────────────────
# 08:00 은 07:20 판정이 **오늘 창**의 것일 때만 쓴다. 안내 1줄은 어차피 나가는
# 발송 끝에만 붙고, 주기마다 한 번이며, 발송이 전부 성공한 뒤에만 소진된다.

# 설계자 R2 Q24 확정 문구 — 코드 상수를 믿지 않고 원문을 그대로 박아 둔다.
NOTICE_LINE = "※ 운영 안내: KRX ETF 전종목 기본정보 CSV를 갱신해 주세요."
NOTICE_TAIL = "\n\n" + NOTICE_LINE
STALE_LINE = render.INDEX_NOTICE[meta_gate.STATUS_API_FETCH_FAILED]
CSV_REQUIRED_LINE = render.INDEX_NOTICE[meta_gate.STATUS_CSV_REFRESH_REQUIRED]


def test_refresh_notice_wording_is_pinned():
    assert render.CSV_REFRESH_NOTICE == NOTICE_LINE


def _patch_verdict(state_dir: Path, **fields) -> None:
    p = state_dir / meta_gate.CONSISTENCY_STATE_NAME
    d = json.loads(p.read_text(encoding="utf-8"))
    for k, v in fields.items():
        if v is _DROP:
            d.pop(k, None)
        else:
            d[k] = v
    p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")


_DROP = object()
_DUE = {
    "refresh_due": True,
    "refresh_due_reason": meta_gate.REFRESH_REASON_PENDING,
    "refresh_due_cycle_id": "20260917",
}


@pytest.mark.parametrize(
    "fields,reason",
    [
        ({"evaluated_window_d20_date": "2026-08-12"}, "window_d20_mismatch"),
        ({"evaluated_api_basis_date": "20260916"}, "api_basis_date_mismatch"),
        (
            {
                "evaluated_api_basis_date": _DROP,
                "evaluated_window_d20_date": _DROP,
                "evaluated_at_kst": _DROP,
            },
            "evaluated_window_missing",
        ),
    ],
)
def test_stale_verdict_closes_only_index_block(tmp_path, monkeypatch, fields, reason):
    """전날 `ok`(+ due) 판정을 오늘 쓰지 않는다 — 기초지수 구역만 닫고 안내도 없다."""
    runner, sent, state_dir = _install(monkeypatch, tmp_path)
    _patch_verdict(state_dir, **_DUE, **fields)
    record = runner.run("market_briefing", "send")
    assert record["status"] == "sent", record
    assert record["index_status"] == meta_gate.STATUS_META_GATE_STALE
    assert record["index_diagnostics"]["reason"] == reason
    body = sent[0]
    assert body.startswith(render.HEADER) and render.SENTENCE_UP in body
    assert STALE_LINE in body and "미국 2026-09-17 종가" in body
    assert "오늘 볼 기초지수" not in body and "국내" not in body
    assert render.CSV_REFRESH_NOTICE not in body, "stale 판정의 refresh_due 를 썼다"
    assert "refresh_notice_cycle_id" not in _state(state_dir)


def test_stale_csv_refresh_verdict_is_not_shown_as_csv_refresh(tmp_path, monkeypatch):
    """불필요한 CSV 다운로드 요청을 막는다 — stale 이면 `CSV_REFRESH_REQUIRED` 문구 금지."""
    runner, sent, state_dir = _install(monkeypatch, tmp_path)
    _patch_verdict(
        state_dir,
        status=meta_gate.STATUS_CSV_REFRESH_REQUIRED,
        evaluated_window_d20_date="2026-08-12",
        **_DUE,
    )
    record = runner.run("market_briefing", "send")
    assert record["index_status"] == meta_gate.STATUS_META_GATE_STALE
    assert "공식 기준정보 갱신이 필요해" not in sent[0]
    assert STALE_LINE in sent[0] and render.CSV_REFRESH_NOTICE not in sent[0]


def _break_official_csv(tmp_path: Path) -> None:
    """08:00 에 공식 CSV 를 못 쓰게 만든다 — Excel 등으로 UTF-8 재저장."""
    p = tmp_path / "market_meta" / CSV_NAME
    p.write_bytes(p.read_bytes().decode("cp949").encode("utf-8"))


def test_unusable_csv_at_0800_closes_index_block_as_csv_refresh(tmp_path, monkeypatch):
    """오늘 창의 판정이어도 08:00 에 유효 CSV 가 없으면 `CSV_REFRESH_REQUIRED` 다(R2 Q25)."""
    from app.market_briefing import official_csv as oc

    runner, sent, state_dir = _install(monkeypatch, tmp_path)
    _break_official_csv(tmp_path)
    record = runner.run("market_briefing", "send")
    assert record["status"] == "sent", record
    assert record["index_status"] == meta_gate.STATUS_CSV_REFRESH_REQUIRED
    assert record["index_diagnostics"] == {
        "reason": "official_csv_unavailable",
        "error": oc.ERROR_NO_VALID_FILE,
    }
    assert [r["reason"] for r in record["official_csv"]["rejected"]] == [
        oc.REASON_DECODE
    ]
    body = sent[0]
    assert body.startswith(render.HEADER) and render.SENTENCE_UP in body
    assert CSV_REQUIRED_LINE in body
    assert "국내" not in body and "오늘 볼 기초지수" not in body


def test_stale_verdict_wins_over_unusable_csv(tmp_path, monkeypatch):
    """판정 창 불일치 + 유효 CSV 없음 → `META_GATE_STALE`(창 확인이 먼저다)."""
    runner, sent, state_dir = _install(monkeypatch, tmp_path)
    _patch_verdict(state_dir, evaluated_window_d20_date="2026-08-12")
    _break_official_csv(tmp_path)
    record = runner.run("market_briefing", "send")
    assert record["status"] == "sent", record
    assert record["index_status"] == meta_gate.STATUS_META_GATE_STALE
    assert record["index_diagnostics"]["reason"] == "window_d20_mismatch"
    body = sent[0]
    assert STALE_LINE in body and CSV_REQUIRED_LINE not in body
    assert "국내" not in body


def test_refresh_notice_once_per_cycle_and_body_otherwise_identical(
    tmp_path, monkeypatch
):
    runner, sent, state_dir = _install(monkeypatch, tmp_path)
    _patch_verdict(state_dir, **_DUE)
    r1 = runner.run("market_briefing", "send")
    assert r1["status"] == "sent", r1
    assert sent[0].endswith(NOTICE_TAIL), sent[0]
    assert sent[0].split("\n")[-1] == NOTICE_LINE
    assert "오늘 볼 기초지수" in sent[0]
    s1 = _state(state_dir)
    assert s1["refresh_notice_cycle_id"] == "20260917"
    assert s1["state_fingerprint"] == "UP#KRX|코스피200", "안내가 fingerprint 를 바꿨다"

    # 다음 거래일 — 같은 주기가 이어진다 → 다시 붙이지 않는다 · 나머지는 byte 동일.
    monkeypatch.setattr(runner, "kst_today_date", lambda: "2026-09-21")
    r2 = runner.run("market_briefing", "send")
    assert r2["status"] == "sent", r2
    assert sent[1] == sent[0][: -len(NOTICE_TAIL)]
    assert r2["state_fingerprint"] == r1["state_fingerprint"]
    assert _state(state_dir)["refresh_notice_cycle_id"] == "20260917"


def test_new_cycle_is_notified_and_old_state_file_loads(tmp_path, monkeypatch):
    runner, sent, state_dir = _install(monkeypatch, tmp_path)
    # 필드가 없던 옛 상태 파일.
    (state_dir / flow.STATE_NAME).write_text(
        json.dumps(
            {
                "schema_version": flow.SCHEMA_VERSION,
                "state_fingerprint": "UP#KRX|코스피200",
                "sent_date_kst": PRIOR_TRADING,
            }
        ),
        encoding="utf-8",
    )
    _patch_verdict(state_dir, **_DUE)
    assert runner.run("market_briefing", "send")["status"] == "sent"
    assert sent[0].endswith(NOTICE_TAIL)
    assert _state(state_dir)["refresh_notice_cycle_id"] == "20260917"

    # 이미 알린 주기와 다른 새 주기면 다시 한 번.
    monkeypatch.setattr(runner, "kst_today_date", lambda: "2026-09-21")
    _patch_verdict(state_dir, refresh_due_cycle_id="20260921")
    assert runner.run("market_briefing", "send")["status"] == "sent"
    assert sent[1].endswith(NOTICE_TAIL)
    assert _state(state_dir)["refresh_notice_cycle_id"] == "20260921"


@pytest.mark.parametrize("first_day", ["telegram_failed", "partial", "disabled"])
def test_refresh_notice_waits_for_next_actual_send(tmp_path, monkeypatch, first_day):
    """발송이 전부 성공하지 않은 날은 안내를 소진하지 않는다 → 다음 실제 발송에 붙는다."""
    runner, sent, state_dir = _install(monkeypatch, tmp_path)
    _patch_verdict(state_dir, **_DUE)
    ok_send = runner.telegram_send
    if first_day == "telegram_failed":
        monkeypatch.setattr(
            runner, "telegram_send", lambda t: (False, "HTTP 500", False)
        )
    elif first_day == "partial":
        monkeypatch.setattr(runner, "telegram_send", lambda t: (False, "chunk 2", True))
    else:
        monkeypatch.setenv("PUSH_AUTOSEND_MARKET_BRIEFING_ENABLED", "false")
    assert runner.run("market_briefing", "send")["status"] != "sent"
    assert _state(state_dir) is None

    monkeypatch.setattr(runner, "telegram_send", ok_send)
    monkeypatch.setenv("PUSH_AUTOSEND_MARKET_BRIEFING_ENABLED", "true")
    monkeypatch.setattr(runner, "kst_today_date", lambda: "2026-09-21")
    assert runner.run("market_briefing", "send")["status"] == "sent"
    assert sent[-1].endswith(NOTICE_TAIL)
    assert _state(state_dir)["refresh_notice_cycle_id"] == "20260917"


def _flow_0800(tmp_path: Path, **kw) -> flow.BriefingOutcome:
    base = dict(
        today_kst=TODAY_TRADING,
        runtime_kst=None,
        state_path=tmp_path / "three_push" / flow.STATE_NAME,
        consistency_path=tmp_path / "three_push" / meta_gate.CONSISTENCY_STATE_NAME,
        meta_dir=tmp_path / "market_meta",
        sp500_return_pct=1.24,
        sp500_asof=PRIOR_TRADING,
        sp500_fresh=True,
        calendar_dir=tmp_path / "market_meta",
        db_path=tmp_path / "krx.sqlite",
    )
    base.update(kw)
    return flow.assemble_market_briefing(**base)


def test_refresh_notice_never_changes_send_decision(tmp_path, monkeypatch):
    """안내는 fingerprint · should_send 를 바꾸지 않고, 안내만으로 발송을 만들지 않는다."""
    _, _, state_dir = _install(monkeypatch, tmp_path)
    plain = _flow_0800(tmp_path)
    _patch_verdict(state_dir, **_DUE)
    due = _flow_0800(tmp_path)
    assert due.message_text == plain.message_text + NOTICE_TAIL
    assert due.fingerprint == plain.fingerprint and due.should_send == plain.should_send
    assert (plain.refresh_notice_cycle_id, due.refresh_notice_cycle_id) == (
        None,
        "20260917",
    )
    assert due.diagnostics["official_csv"]["name"] == CSV_NAME

    # 전망 불가 + 후보 없음(CSV 갱신 필요) → 원래 미발송. 안내 때문에 보내지 않는다.
    _patch_verdict(state_dir, status=meta_gate.STATUS_CSV_REFRESH_REQUIRED)
    none = _flow_0800(tmp_path, sp500_return_pct=None, sp500_fresh=False)
    assert not none.should_send and none.message_text == ""
    assert none.skip_reason == flow.REASON_NO_PUBLISHABLE
