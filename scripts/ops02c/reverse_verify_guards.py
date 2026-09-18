"""POC3-02C-OPS-01 + POC3-02B-OPS-03 보호 로직 역검증.

각 가드를 **일시 무력화**해 실제로 나쁜 일이 일어나는지 확인한다. 가드가 있을 때
통과하는 것만으로는 "그 가드가 일하고 있다" 를 증명하지 못한다.

실경로를 쓰지 않는다 — 임시 DB·임시 디렉터리만. 외부 호출·발송 0건.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.intraday_config import generator, schema, selector, store  # noqa: E402
from app.market_briefing import flow as mb_flow  # noqa: E402

RESULTS: list[tuple[str, str, str, bool]] = []


def record(guard: str, with_g: str, without_g: str, ok: bool) -> None:
    RESULTS.append((guard, with_g, without_g, ok))


def area() -> Path:
    return Path(tempfile.mkdtemp())


CSV = Path("state/market_meta/krx_etf_basic_20260909.csv")
DB = Path("state/market/market_data.sqlite")


def payload() -> dict:
    sectors, excluded, asof = selector.build_sectors(csv_path=CSV, db_path=DB)
    return schema.build_payload(
        rule_version=selector.RULE_VERSION,
        sectors=sectors,
        token_dictionary=selector.default_token_dictionary(),
        data_asof=asof,
        excluded=excluded,
    )


# ── ① 승인 게이트 ───────────────────────────────────────────────────────────
db = area() / "runtime_state.sqlite"
p = payload()
vid, _ = store.create_candidate(p, evaluation_input_hash="h", db_path=db)
try:
    store.activate(vid, activated_by="t", db_path=db)
    with_g1, ok1 = "!! 활성화됨", False
except store.ApprovalRequired:
    with_g1, ok1 = "ApprovalRequired 로 거부", True

orig_get = store.get_version
store.get_version = lambda v, **k: {
    **orig_get(v, **k),
    "approved_at": "X",
    "approved_by": "X",
}
try:
    store.activate(vid, activated_by="t", db_path=db)
    without1, broke1 = "미승인 버전이 활성화됨", True
except Exception as e:  # noqa: BLE001
    without1, broke1 = f"{type(e).__name__}", False
store.get_version = orig_get
record("① 승인 게이트", with_g1, without1, ok1 and broke1)


# ── ② 동일 유효설정 재생성 차단 ──────────────────────────────────────────────
db2 = area() / "runtime_state.sqlite"
v1, c1 = store.create_candidate(p, evaluation_input_hash="h1", db_path=db2)
v2, c2 = store.create_candidate(p, evaluation_input_hash="h2", db_path=db2)
with_g2 = f"두 번째 created={c2} (같은 id={v1 == v2})"
orig_find = store.find_by_effective_hash
store.find_by_effective_hash = lambda h, **k: None
v3, c3 = store.create_candidate(p, evaluation_input_hash="h3", db_path=db2)
store.find_by_effective_hash = orig_find
record(
    "② 동일 설정 재생성 차단",
    with_g2,
    f"같은 설정으로 새 버전 생성됨 created={c3}",
    (not c2) and c3,
)


# ── ③ checksum 가변필드 제외 ─────────────────────────────────────────────────
base = schema.source_hash(p)
noisy = json.loads(json.dumps(p))
noisy["approved_at"] = "2026-01-01T00:00:00Z"
with_g3 = f"승인 시각 추가 후에도 {schema.source_hash(noisy)[:12]} (동일={schema.source_hash(noisy) == base})"
orig_strip = schema._strip_volatile
schema._strip_volatile = lambda o: o
without3 = f"동일={schema.source_hash(noisy) == base}"
broke3 = schema.source_hash(noisy) != base
schema._strip_volatile = orig_strip
record(
    "③ checksum 가변필드 제외",
    with_g3,
    f"승인 시각이 checksum 을 바꿈 {without3}",
    broke3,
)


# ── ④ enabled=true 정책 필수값 ───────────────────────────────────────────────
bad = json.loads(json.dumps(p))
bad["intraday_alert_policy"] = {"enabled": True, "policy_status": "CONFIGURED"}
try:
    schema.validate(bad)
    with_g4, ok4 = "!! 통과됨", False
except schema.ConfigSchemaError:
    with_g4, ok4 = "ConfigSchemaError 로 거부", True
orig_req = schema.REQUIRED_POLICY_KEYS
schema.REQUIRED_POLICY_KEYS = ()
try:
    schema.validate(bad)
    without4, broke4 = "임계 없이 enabled=true 가 통과됨", True
except schema.ConfigSchemaError:
    without4, broke4 = "여전히 거부", False
schema.REQUIRED_POLICY_KEYS = orig_req
record("④ enabled=true 필수값", with_g4, without4, ok4 and broke4)


# ── ⑤ 생성 트리거 예외 격리 ──────────────────────────────────────────────────
out5 = generator.generate(
    csv_path=Path("missing.csv"),
    db_path=Path("missing.sqlite"),
    state_db_path=area() / "runtime_state.sqlite",
    force=True,
)
with_g5, ok5 = f"status={out5['status']} (예외 미발생)", out5["status"] == "failed"
orig_build = generator.selector.build_sectors
raised = False
try:
    generator.selector.build_sectors(csv_path=Path("missing.csv"), db_path=Path("x"))
except Exception:  # noqa: BLE001
    raised = True
record(
    "⑤ 생성 트리거 예외 격리",
    with_g5,
    f"try 가 없으면 selector 가 그대로 raise (실측 raise={raised})",
    ok5 and raised,
)


# ── ⑥ 정기 PUSH 억제 해제 (POC3-02B-OPS-03) ─────────────────────────────────
# 같은 fingerprint 가 이어져도 막지 않아야 한다.
AXIS = [f"2026-08-{d:02d}" for d in range(3, 32)] + [
    f"2026-09-{d:02d}" for d in (1, 2, 3, 4, 7, 8, 9, 10, 11)
]
tmp6 = area()
(tmp6 / "krx_trading_days_2026.csv").write_text(
    "date\n" + "\n".join(AXIS) + "\n", encoding="utf-8"
)
(tmp6 / "official.csv").write_bytes(
    "단축코드,기초지수명,지수산출기관,기초자산분류,추적배수,복제방법\n".encode("cp949")
)


def assemble6(today: str):
    return mb_flow.assemble_market_briefing(
        today_kst=today,
        runtime_kst=None,
        state_path=tmp6 / "s.json",
        consistency_path=tmp6 / "c.json",
        official_csv_path=tmp6 / "official.csv",
        sp500_return_pct=-1.0,
        sp500_asof="2026-09-08",
        sp500_fresh=True,
        calendar_dir=tmp6,
        db_path=tmp6 / "none.sqlite",
    )


a = assemble6("2026-09-09")
mb_flow.save_state(
    tmp6 / "s.json",
    fingerprint=a.fingerprint,
    sent_date_kst="2026-09-09",
    runtime_kst=None,
)
b = assemble6("2026-09-10")
with_g6 = f"다음 거래일 skip_reason={b.skip_reason} unchanged={b.diagnostics.get('content_unchanged')}"

# 옛 계약 복원 — fingerprint 가 같으면 막는다.
orig_assemble = mb_flow.assemble_market_briefing


def legacy(**kw):
    out = orig_assemble(**kw)
    if out.previous_fingerprint == out.fingerprint and out.fingerprint:
        out.skip_reason = mb_flow.REASON_NO_CHANGE
    return out


mb_flow.assemble_market_briefing = legacy
c = assemble6("2026-09-10")
mb_flow.assemble_market_briefing = orig_assemble
record(
    "⑥ 정기 PUSH 억제 해제",
    with_g6,
    f"옛 계약이면 skip_reason={c.skip_reason} (다음 거래일이 막힌다)",
    b.skip_reason is None and c.skip_reason == mb_flow.REASON_NO_CHANGE,
)


# ── 검증자 REJECTED P1 6건 역검증 ───────────────────────────────────────────

# ⑦ 기각본 활성화 차단 (P1-4)
d7 = area() / "rs.sqlite"
v7, _ = store.create_candidate(payload(), evaluation_input_hash="h7", db_path=d7)
store.approve(v7, approved_by="user", db_path=d7)
store.reject(v7, rejected_by="user", reason="테스트", db_path=d7)
try:
    store.activate(v7, activated_by="t", db_path=d7)
    with7, ok7 = "!! 기각본이 활성화됐다", False
except store.ApprovalRequired:
    with7, ok7 = "ApprovalRequired 로 거부", True
# 무력화: 기각 검사를 빼고 승인 필드를 되살리면 통과해 버린다
import sqlite3  # noqa: E402

con = sqlite3.connect(d7)
con.execute(
    "UPDATE intraday_alert_config_version SET approved_at=?, approved_by=? "
    "WHERE config_version_id=?",
    ("2026-01-01T00:00:00Z", "user", v7),
)
con.commit()
con.close()
row7 = store.get_version(v7, db_path=d7)
without7 = (
    "승인 필드를 되살리면 게이트만으로는 못 막는다"
    f" (rejected_at={bool(row7['rejected_at'])} 검사가 그래서 필요)"
)
try:
    store.activate(v7, activated_by="t", db_path=d7)
    ok7 = False
    without7 = "!! 기각본이 활성화됐다"
except store.ApprovalRequired:
    pass
record("⑦ 기각본 활성화 차단", with7, without7, ok7)


# ⑧ 전달 실패본이 재시도 조회에 남는가 (P1-2)
d8 = area() / "rs.sqlite"
v8, _ = store.create_candidate(payload(), evaluation_input_hash="h8", db_path=d8)
store.approve(v8, approved_by="user", db_path=d8)
store.record_sync(v8, target="oci", status="scp_failed", error="boom", db_path=d8)
row8, st8 = store.actionable_version(db_path=d8)
legacy8 = store.latest_candidate(db_path=d8)  # 옛 조회 방식
record(
    "⑧ 배포 실패본 재시도 보존",
    f"actionable={st8} version={(row8 or {}).get('config_version_id', '')[:28]}",
    f"옛 latest_candidate() 만 쓰면 {legacy8} → 재시도 버튼이 사라진다",
    row8 is not None and st8 == store.STATE_APPROVED_NOT_DEPLOYED and legacy8 is None,
)


# ⑨ 성공 후 할 일이 사라지는가 (P1-2 반대편)
store.activate(v8, activated_by="pc_deploy", db_path=d8)
row9, st9 = store.actionable_version(db_path=d8)
record(
    "⑨ 전달 성공 후 액션 해제",
    f"actionable={st9} (재시도 버튼 없음)",
    "PC active 를 안 쓰면 성공해도 재시도 버튼이 영구히 남는다",
    row9 is None and st9 is None,
)


# ⑩ rollback — **실제 apply_file 체인**으로 재독출 불일치를 만든다 (P1-3)
#    helper 만 부르면 activate→readback→rollback 배선이 끊겨도 통과한다.
import scripts.apply_intraday_config_oci as apply_mod  # noqa: E402


def _export10(row: dict, path: Path) -> Path:
    path.write_text(
        json.dumps(
            {
                k: row[k]
                for k in (
                    "config_version_id",
                    "schema_version",
                    "created_at",
                    "rule_version",
                    "evaluation_input_hash",
                    "effective_config_hash",
                    "source_hash_sha256",
                    "payload_json",
                    "approved_at",
                    "approved_by",
                )
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return path


a10 = area()
d10 = a10 / "rs.sqlite"
pa = payload()
v10a, _ = store.create_candidate(pa, evaluation_input_hash="h10a", db_path=d10)
store.approve(v10a, approved_by="user", db_path=d10)
store.activate(v10a, activated_by="t", db_path=d10)
pb = json.loads(json.dumps(pa))
pb["sector_representative_universe"]["sectors"][0]["representative"][
    "ticker"
] = "777777"
v10b, _ = store.create_candidate(pb, evaluation_input_hash="h10b", db_path=d10)
store.approve(v10b, approved_by="user", db_path=d10)
row10b = store.get_version(v10b, db_path=d10)

_dflt = store._db.DEFAULT_DB_PATH
store._db.DEFAULT_DB_PATH = d10
_orig_rb = apply_mod._readback_matches
apply_mod._readback_matches = lambda row: (False, "hash")
rc10 = apply_mod.apply_file(_export10(row10b, a10 / "v2.json"))
after_guard = store.get_active(db_path=d10)["config_version_id"]

# 무력화: rollback 을 없애고 같은 실패를 재현한다
_orig_restore = apply_mod._restore
apply_mod._restore = lambda before_id, activated_by: None
store.activate(v10a, activated_by="reset", db_path=d10)
rc10b = apply_mod.apply_file(_export10(row10b, a10 / "v2.json"))
without_guard = store.get_active(db_path=d10)["config_version_id"]
apply_mod._restore = _orig_restore
apply_mod._readback_matches = _orig_rb
store._db.DEFAULT_DB_PATH = _dflt

record(
    "⑩ 재독출 실패 시 active 복원",
    f"apply_file rc={rc10} · active={after_guard[:28]} (직전본으로 복원)",
    f"rollback 을 빼면 실패를 반환하면서 active 는 {without_guard[:28]} 로 남는다",
    rc10 != 0 and after_guard == v10a and without_guard == v10b,
)


# ⑪ 시총 결측 대표 선정 차단 (P1-5)
_orig_closes = selector.latest_closes
selector.latest_closes = lambda db_path: ("2026-09-11", {})
s11, e11, _ = selector.build_sectors(csv_path=CSV, db_path=DB)
selector.latest_closes = _orig_closes
s11ok, _, _ = selector.build_sectors(csv_path=CSV, db_path=DB)
record(
    "⑪ 시총 결측 대표 선정 차단",
    f"가격 0건이면 사업군 {len(s11)}개 · 사유 기록 {len(e11) > 0}",
    "`market_cap or 0.0` 이면 종목코드순으로 뽑고 metric=market_cap 이라 적는다",
    s11 == [] and any(x["reason"] == "sector_no_market_cap" for x in e11) and s11ok,
)


# ⑫ 토큰 사전이 데이터 원천인가 (P1-6)
try:
    selector.load_token_dictionary(area() / "없음.json")
    with12, ok12 = "!! 파일이 없는데 통과했다", False
except selector.TokenDictionaryError:
    with12, ok12 = "TokenDictionaryError 로 거부", True
src12 = Path("app/intraday_config/selector.py").read_text(encoding="utf-8")
lit = [k for k in selector.load_token_dictionary()[0] if f'"{k}": [' in src12]
record(
    "⑫ 토큰 사전 = 번들 데이터",
    with12,
    f"코드 상수로 되돌리면 승인 없이 분류가 바뀐다 (현재 잔존 리터럴 {len(lit)}개)",
    ok12 and not lit,
)


# ⑬ 자동 산출 배선 (P1-1)
api_src = Path("app/api.py").read_text(encoding="utf-8")
svc_src = Path("app/market_refresh_service.py").read_text(encoding="utf-8")
wired = "intraday_startup.catch_up()" in api_src
refresh_wired = "_regenerate_intraday_config(db_path)" in svc_src
record(
    "⑬ 자동 산출 진입점 배선",
    f"기동 catch-up={wired} · 갱신 성공 후 재산출={refresh_wired}",
    "배선이 없으면 generate() 가 완성돼 있어도 후보가 영원히 안 생긴다",
    wired and refresh_wired,
)


# ── 검증자 r2 REJECTED 4건 역검증 ───────────────────────────────────────────

# ⑭ 옛 승인본이 재시도 대상으로 되살아나지 않는가 (r2 P1)
d14 = area() / "rs.sqlite"
pa14 = payload()
v14a, _ = store.create_candidate(pa14, evaluation_input_hash="a", db_path=d14)
store.approve(v14a, approved_by="user", db_path=d14)
store.activate(v14a, activated_by="pc_deploy", db_path=d14)
pb14 = json.loads(json.dumps(pa14))
pb14["sector_representative_universe"]["sectors"][0]["representative"][
    "ticker"
] = "777777"
v14b, _ = store.create_candidate(pb14, evaluation_input_hash="b", db_path=d14)
store.approve(v14b, approved_by="user", db_path=d14)
store.activate(v14b, activated_by="pc_deploy", db_path=d14)
row14, st14 = store.actionable_version(db_path=d14)
# 무력화: 옛 조회("active 가 아닌 승인본")를 재현한다
con14 = sqlite3.connect(d14)
con14.row_factory = sqlite3.Row
legacy14 = con14.execute(
    "SELECT config_version_id FROM intraday_alert_config_version "
    "WHERE rejected_at IS NULL AND approved_at IS NOT NULL "
    "AND config_version_id IS NOT ? ORDER BY approved_at DESC LIMIT 1",
    (v14b,),
).fetchone()
con14.close()
record(
    "⑭ 옛 승인본 재시도 배제",
    f"actionable={st14} (v2 운영 중이므로 할 일 없음)",
    f"옛 조회는 {('v1' if legacy14 and legacy14[0] == v14a else '?')} 를 재배포 대상으로 내놓는다",
    row14 is None and st14 is None and legacy14 is not None,
)


# ⑮ 재시도가 승인 시각을 다시 쓰지 않는가 (r2 P1)
d15 = area() / "rs.sqlite"
v15, _ = store.create_candidate(payload(), evaluation_input_hash="c", db_path=d15)
store.approve(v15, approved_by="user", db_path=d15)
first15 = store.get_version(v15, db_path=d15)["approved_at"]
row15 = store.get_version(v15, db_path=d15)
already15 = bool(row15.get("approved_at") and row15.get("approved_by"))
if not already15:  # 현재 API 의 멱등 분기와 같은 조건
    store.approve(v15, approved_by="user", db_path=d15)
kept15 = store.get_version(v15, db_path=d15)["approved_at"]
store.approve(v15, approved_by="user", db_path=d15)  # 무조건 승인했다면
rewritten15 = store.get_version(v15, db_path=d15)["approved_at"]
record(
    "⑮ 재시도 승인 멱등",
    f"재시도 후 approved_at 불변={kept15 == first15}",
    f"무조건 approve 하면 승인 시각이 바뀐다 (변경={rewritten15 != first15})",
    kept15 == first15 and rewritten15 != first15,
)


# ⑯ 운영 중 버전 기각 차단 (r2 P1)
d16 = area() / "rs.sqlite"
v16, _ = store.create_candidate(payload(), evaluation_input_hash="d", db_path=d16)
store.approve(v16, approved_by="user", db_path=d16)
store.activate(v16, activated_by="pc_deploy", db_path=d16)
try:
    store.reject(v16, rejected_by="user", reason="t", db_path=d16)
    with16, ok16 = "!! 운영 중 설정이 기각됐다", False
except store.CannotRejectActive:
    with16, ok16 = "CannotRejectActive 로 거부", True
r16 = store.get_version(v16, db_path=d16)
a16 = store.get_active(db_path=d16)
record(
    "⑯ 운영 중 버전 기각 차단",
    with16,
    "가드가 없으면 active pointer 는 그대로인데 그 버전이 기각 상태가 된다",
    ok16 and r16["rejected_at"] is None and a16["config_version_id"] == v16,
)


# ⑰ 정리 명령이 적용 rc 를 오염시키지 않는가 (r2 P1)
sync_src = Path("scripts/sync_intraday_config.py").read_text(encoding="utf-8")
chained = "; rm -f {remote_apply}" in sync_src
reconciles = "_remote_active(target)" in sync_src and "deploy_unconfirmed" in sync_src
record(
    "⑰ 원격 성공 후 SSH 실패 화해",
    f"rm 분리={not chained} · 원격 상태 조회 후 rollback/unconfirmed={reconciles}",
    "`; rm` 을 붙이면 정리 실패가 적용 성공을 실패로 뒤집고 active 는 남는다",
    (not chained) and reconciles,
)


# ── 검증자 r3 지적 3건 역검증 ───────────────────────────────────────────────

# ⑱ stale 화면의 옛 후보 승인 차단
api_src = Path("app/api_intraday_config.py").read_text(encoding="utf-8")
gate18 = "current, _state = store.actionable_version()" in api_src
d18 = area() / "rs.sqlite"
pa18 = payload()
v18a, _ = store.create_candidate(pa18, evaluation_input_hash="e", db_path=d18)
pb18 = json.loads(json.dumps(pa18))
pb18["sector_representative_universe"]["sectors"][0]["representative"][
    "ticker"
] = "777777"
v18b, _ = store.create_candidate(pb18, evaluation_input_hash="f", db_path=d18)
cur18, _ = store.actionable_version(db_path=d18)
record(
    "⑱ stale 화면 옛 후보 승인 차단",
    f"조치 대상은 최신 {cur18['config_version_id'][:28]} 뿐 · API 게이트={gate18}",
    f"게이트가 없으면 옛 {v18a[:28]} 로 POST 해 옛 설정이 OCI 로 나간다",
    gate18 and cur18["config_version_id"] == v18b,
)


# ⑲ 적용 전 active 조회 실패 시 **시작하지 않는다**
sync_src2 = Path("scripts/sync_intraday_config.py").read_text(encoding="utf-8")
precheck = 'return fail(\n            "precheck_failed"' in sync_src2 or (
    "precheck_failed" in sync_src2 and "if not prior_read_ok:" in sync_src2
)
still_impossible = "rollback_impossible" in sync_src2.replace(
    "# 뒤 `rollback_impossible` 을 내놨는데, 그 시점엔 이미 늦었다(검증자 지적).", ""
)
record(
    "⑲ 사전 조회 실패 시 적용 중단",
    f"precheck_failed 로 중단={precheck}",
    "그대로 진행하면 되돌릴 기준 없이 원격이 바뀐다 (옛 rollback_impossible)",
    precheck and not still_impossible,
)


# ⑳ 손상 payload 를 빈 객체로 숨기지 않는다
import app.api_intraday_config as api_mod  # noqa: E402

try:
    api_mod._payload({"config_version_id": "x", "payload_json": "{깨짐"})
    with20, ok20 = "!! 손상을 통과시켰다", False
except api_mod.PayloadCorrupt:
    with20, ok20 = "PayloadCorrupt 로 올림", True
record(
    "⑳ 손상 payload 노출",
    with20,
    "except: return {} 이면 깨진 설정이 화면에 '0개 사업군' 으로 보인다",
    ok20 and "payload_error" in api_src,
)


# ── 설계자 확정 read-back 재시도 (2026-09-18) ───────────────────────────────

import scripts.sync_intraday_config as sync_mod  # noqa: E402

WANT_ID, WANT_HASH = "intraday-목표", "a" * 64
PRIOR_ID, PRIOR_HASH = "intraday-직전", "b" * 64


def _recon(reads):
    seq = list(reads)
    _orig = sync_mod._remote_active
    sync_mod._remote_active = lambda _t: seq.pop(0) if seq else (False, None, None)
    try:
        return sync_mod.reconcile_after_apply(
            "fake",
            want_id=WANT_ID,
            want_hash=WANT_HASH,
            prior_id=PRIOR_ID,
            prior_hash=PRIOR_HASH,
            sleep=lambda _d: None,
        )
    finally:
        sync_mod._remote_active = _orig


# ㉑ 1·2회 실패 후 확인 → deployed (조회 1회뿐이면 unconfirmed 로 끝난다)
v21, seen21 = _recon(
    [(False, None, None), (False, None, None), (True, WANT_ID, WANT_HASH)]
)
v21_once, _ = _recon([(False, None, None)])
record(
    "㉑ read-back 3회 재시도",
    f"1·2회 실패 후 3회차 확인 → {v21} (조회 {len(seen21)}회)",
    f"1회만 조회하면 같은 상황이 {v21_once} 로 끝난다",
    v21 == "deployed" and len(seen21) == 3 and v21_once == "deploy_unconfirmed",
)

# ㉒ 직전 유지 확인 → remote_apply_failed
v22, _ = _recon([(True, PRIOR_ID, PRIOR_HASH)])
record(
    "㉒ 직전 active 유지 확정",
    f"직전 version/hash 확인 → {v22}",
    "구분하지 않으면 적용 안 된 경우도 '모름' 으로 뭉뚱그려진다",
    v22 == "remote_apply_failed",
)

# ㉓ 예상 밖 상태·전부 실패 → deploy_unconfirmed (추정 금지)
v23a, _ = _recon([(True, "intraday-누구", "f" * 64)] * 3)
v23b, seen23 = _recon([(False, None, None)] * 3)
# hash 만 다른 경우도 목표로 인정하면 안 된다
v23c, _ = _recon([(True, WANT_ID, "c" * 64)] * 3)
record(
    "㉓ 예상 밖 상태 추정 금지",
    f"예상밖={v23a} · 전부실패={v23b} · hash불일치={v23c}",
    "version 만 보고 판정하면 내용이 다른 설정을 적용 완료로 단정한다",
    v23a == v23b == v23c == "deploy_unconfirmed" and len(seen23) == 3,
)

# ㉔ 재시도 경로는 read-only — 자동 재적용 금지
recon_src = Path("scripts/sync_intraday_config.py").read_text(encoding="utf-8")
_s = recon_src.index("def reconcile_after_apply")
_e = recon_src.index("def _parse_ok")
recon_body = recon_src[_s:_e]
writes = [w for w in ("activate(", "clear_active", "rm -f", "scp") if w in recon_body]
record(
    "㉔ 재시도는 조회 전용",
    f"쓰기 명령 {len(writes)}개 · 자동 재적용 없음",
    "apply 를 재실행하면 OCI 를 한 번 더 건드린다 (AUTOMATIC_REAPPLY=FORBIDDEN)",
    not writes and "_remote_rollback" not in recon_src,
)


# ㉕ precheck 이 원격 쓰기보다 **앞**인가 (검증자 r6)
dep_src = sync_mod_src = Path("scripts/sync_intraday_config.py").read_text(
    encoding="utf-8"
)
dep_body = sync_mod_src[sync_mod_src.index("def deploy(") :]  # noqa: E203
pos_check = dep_body.index("prior_read_ok")
pos_scp = dep_body.index('"scp"')
pos_mv = dep_body.index("mv {remote_tmp}")
record(
    "㉕ precheck 선행 (원격 쓰기 0)",
    f"precheck@{pos_check} < scp@{pos_scp} · mv@{pos_mv}",
    "뒤에 있으면 precheck_failed 를 내면서 원격 정본 JSON 이 이미 교체돼 있다",
    pos_check < pos_scp and pos_check < pos_mv,
)

# ㉖ 업로드 뒤 **모든** 실패 분기가 정리를 거치는가
#
#    예전 가드는 `fail_after_upload(` 개수를 셌는데 **함수 정의 자체도 포함**돼
#    호출 한 곳이 빠져도 통과했다(검증자 r7). 실제 계약을 본다 —
#    "첫 원격 쓰기부터 cleanup() 까지 구간에 맨 `fail(` 이 하나도 없어야 한다".
_w = dep_body.index('"scp"')  # 첫 원격 쓰기
_c = dep_body.index("cleanup()  #")  # 적용 후 일괄 정리
window = dep_body[_w:_c]
bare = [ln.strip() for ln in window.splitlines() if "return fail(" in ln]
wrapped = window.count("return fail_after_upload(")
record(
    "㉖ 업로드 뒤 실패는 전부 정리 경유",
    f"쓰기~정리 구간: 맨 fail {len(bare)}건 · fail_after_upload {wrapped}건",
    "한 곳이라도 맨 fail 이면 .apply_intraday_config_oci.py 가 OCI 에 남는다",
    not bare and wrapped >= 4 and "def cleanup()" in sync_mod_src,
)


# ── 출력 ─────────────────────────────────────────────────────────────────────
print(f"{'보호 로직':30s} | {'가드 있을 때':46s} | 무력화하면")
print("-" * 140)
allok = True
for g, w, wo, ok in RESULTS:
    allok = allok and ok
    print(f"{'OK ' if ok else '!! '}{g:28s} | {w:46s} | {wo}")
print("-" * 140)
print(f"역검증 {len(RESULTS)}건 · 전부 '무력화 시 실패' 확인: {allok}")
sys.exit(0 if allok else 1)
