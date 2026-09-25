"""POC4-02 공용 봉인 KRX reader — 고정 fixture 테스트 (설계자 판정 2026-09-25 §3 · 구현 순서 2).

모두 tmp_path 의 KRX 스키마 DB 만 쓴다. 봉인 DB·라이브 DB 는 열지 않는다.
"""

from __future__ import annotations

import sqlite3

import pytest

from app import krx_sealed_reader as reader
from app.ml_baseline_snapshot import file_sha256
from tests._krx_fixture import (
    build_sealed_db,
    krx_row,
    rows_by_date,
    series_rows,
    trading_dates,
)


def _small_db(tmp_path, *, seal=True, extra=None):
    days = trading_dates(6)
    a = series_rows("069500", days, [100, 101, 99, 102, 103, 104], name="KODEX 200")
    b = series_rows("111111", days[:4], [50, 51, 52, 50], name="TEST ETF")  # 폐지
    c = series_rows("222222", days[2:], [10, 11, 12, 13], name="TEST NEW")  # 신규 상장
    path = tmp_path / "krx.sqlite"
    sha = build_sealed_db(
        path, rows_by_date(a, b, c), seal=seal, extra_unattached=extra
    )
    return path, sha, days


def test_verify_sealed_source_ok(tmp_path):
    path, sha, days = _small_db(tmp_path)
    got = reader.verify_sealed_source(path, expected_content_sha256=sha)
    assert got["status"] == "SEALED"
    assert got["content_sha256"] == sha
    assert got["member_dates"] == 6
    assert (got["first_date"], got["last_date"]) == (days[0], days[-1])
    assert got["payload_hash_mismatch"] == 0 and got["row_count_mismatch"] == 0
    assert got["quick_check"] == "ok" and got["integrity_check"] == "ok"
    assert got["file_sha256"] == file_sha256(path)


def test_open_version_is_refused(tmp_path):
    path, _sha, _ = _small_db(tmp_path, seal=False)
    with pytest.raises(reader.SealedSourceError, match="봉인되지 않은"):
        reader.verify_sealed_source(path)


def test_expected_seal_mismatch_fails(tmp_path):
    path, _sha, _ = _small_db(tmp_path)
    with pytest.raises(reader.SealedSourceError, match="기대한 봉인"):
        reader.verify_sealed_source(path, expected_content_sha256="0" * 64)


def test_tampered_payload_fails(tmp_path):
    path, _sha, _ = _small_db(tmp_path)
    con = sqlite3.connect(path)
    con.execute(
        "UPDATE krx_raw_response SET payload = payload || ' ' WHERE response_id = 1"
    )
    con.commit()
    con.close()
    with pytest.raises(reader.SealedSourceError, match="payload hash 불일치 1"):
        reader.verify_sealed_source(path)


def test_tampered_member_hash_breaks_seal(tmp_path):
    path, _sha, _ = _small_db(tmp_path)
    con = sqlite3.connect(path)
    con.execute(
        "UPDATE krx_raw_response SET payload_sha256 = 'x' WHERE response_id = 2"
    )
    con.commit()
    con.close()
    with pytest.raises(reader.SealedSourceError, match="content_sha256 불일치"):
        reader.verify_sealed_source(path)


def test_assert_same_source_detects_change(tmp_path):
    path, _sha, _ = _small_db(tmp_path)
    before = reader.verify_sealed_source(path)
    reader.assert_same_source(before, reader.verify_sealed_source(path))
    changed = dict(before, file_sha256="different")
    with pytest.raises(reader.SealedSourceError, match="file_sha256"):
        reader.assert_same_source(before, changed)


def test_reader_is_read_only(tmp_path):
    path, _sha, _ = _small_db(tmp_path)
    before = file_sha256(path)
    reader.verify_sealed_source(path)
    reader.load_panel(path)
    con = reader.open_readonly(path)
    with pytest.raises(sqlite3.OperationalError):
        con.execute("CREATE TABLE x (a)")
    con.close()
    assert file_sha256(path) == before


def test_load_panel_uses_member_rows_only(tmp_path):
    days = trading_dates(6)
    canary = {days[1]: [krx_row("999999", days[1], 7, None, name="CANARY ONLY")]}
    path, _sha, _ = _small_db(tmp_path, extra=canary)
    panel = reader.load_panel(path)
    assert "999999" not in panel.series
    assert panel.dates == [f"{d[:4]}-{d[4:6]}-{d[6:]}" for d in days]
    assert panel.final_date == panel.dates[-1]
    assert panel.present(panel.dates[0]) == frozenset({"069500", "111111"})
    assert panel.present(panel.dates[-1]) == frozenset({"069500", "222222"})
    assert panel.benchmark().name[0] == "KODEX 200"


def test_relation_tolerance_boundary():
    # r = 1 / 100 = 1% · FLUC_RT 표기 1.00
    assert reader.check_relation(101.0, 1.0, 1.00) == pytest.approx((0.01, True))
    assert reader.check_relation(101.0, 1.0, 1.005)[1] is True  # 차이 0.005 — 허용
    assert reader.check_relation(101.0, 1.0, 1.0051)[1] is False  # 0.0051 — 불일치
    assert reader.check_relation(100.0, 100.0, 0.0) == (None, False)  # 기준가 0
    assert reader.check_relation(None, 1.0, 1.0) == (None, False)


def test_chain_follows_official_daily_return(tmp_path):
    days = trading_dates(5)
    # 분배락 흉내: 종가 차이(−3)와 공식 대비(−1)가 다르다 — 연결 계열은 공식 대비를 따른다.
    rows = {
        days[0]: [krx_row("069500", days[0], 100, None)],
        days[1]: [krx_row("069500", days[1], 102, 100)],
        days[2]: [krx_row("069500", days[2], 99, 102, cmpprev=-1)],
        days[3]: [krx_row("069500", days[3], 100, 99)],
        days[4]: [krx_row("069500", days[4], 101, 100)],
    }
    path = tmp_path / "krx.sqlite"
    build_sealed_db(path, rows)
    s = reader.load_panel(path).benchmark()
    expected = [100.0]
    for close, cp in ((102, 2), (99, -1), (100, 1), (101, 1)):
        expected.append(expected[-1] * (1 + cp / (close - cp)))
    assert s.chain == pytest.approx(expected)
    assert s.segment == [0, 0, 0, 0, 0]
    assert all(s.relation_ok)


def test_relation_mismatch_starts_new_segment(tmp_path):
    days = trading_dates(5)
    rows = {
        days[0]: [krx_row("111111", days[0], 100, None)],
        days[1]: [krx_row("111111", days[1], 101, 100)],
        # 셋째 날 FLUC_RT 가 공식 대비와 맞지 않는다
        days[2]: [krx_row("111111", days[2], 103, 101, fluc=9.99)],
        days[3]: [krx_row("111111", days[3], 104, 103)],
        days[4]: [krx_row("111111", days[4], 105, 104)],
    }
    path = tmp_path / "krx.sqlite"
    build_sealed_db(path, rows)
    panel = reader.load_panel(path)
    s = panel.series["111111"]
    assert panel.relation_mismatch_rows == 1
    assert s.relation_ok == [True, True, False, True, True]
    assert s.segment == [0, 0, 1, 1, 1]
    assert s.chain[2] == pytest.approx(103.0)  # 보정하지 않고 그날 종가로 새로 시작
    iso = [f"{d[:4]}-{d[4:6]}-{d[6:]}" for d in days]
    # 구간을 넘는 이력은 붙이지 않는다
    assert [d for d, _ in s.chain_history()] == iso[2:]
    assert [d for d, _ in s.chain_history(iso[1])] == iso[:2]


def test_invalid_close_is_flagged(tmp_path):
    days = trading_dates(3)
    bad = krx_row("111111", days[1], 100, 100)
    bad["TDD_CLSPRC"] = ""
    rows = {
        days[0]: [krx_row("111111", days[0], 100, None)],
        days[1]: [bad],
        days[2]: [krx_row("111111", days[2], 101, 100)],
    }
    path = tmp_path / "krx.sqlite"
    build_sealed_db(path, rows)
    panel = reader.load_panel(path)
    s = panel.series["111111"]
    assert panel.invalid_close_rows == 1
    assert s.close_status == [reader.CLOSE_OK, reader.NO_VALID_CLOSE, reader.CLOSE_OK]
    assert s.chain[1] is None and s.segment == [0, 1, 2]
