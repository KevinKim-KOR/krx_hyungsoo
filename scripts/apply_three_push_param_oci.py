"""POC5-27 — OCI 쪽 운영 기준(PARAM) 발행 · 복구 도구.

PC 가 **일시 업로드해 원격 실행**한다(장중 설정 `apply_intraday_config_oci.py` 와 같은 방식 · 실행 뒤
PC 가 지운다). 저장소에도 두므로 OCI pull 뒤에는 상주 명령으로도 쓸 수 있다.

PC 에서 확정 · 사용자가 승인한 PARAM 값을 OCI 로컬에서 **그대로** 검증 · 기록 · 활성화 · 확인한다.
OCI 가 값을 계산 · 선정 · 생성하지 않는다(POC5-27 PLAN 판정 §1). 쓰는 함수는 OCI 에 이미 있는
저장 함수뿐이다(`app.runtime_param_store` · `app.three_push_runtime_param`).

```text
--json <파일>             발행: (--expect-sha256 이 있으면) 파일 내용 = PC 가 보낸 내용 확인
                          → 파일 검증 → 지금 활성값과 유효값 비교(같으면 쓰기 없이 SAME)
                          → 버전 기록(값 그대로) → DB 에서 다시 만든 후보 검사(러너 읽기 함수 ·
                          유효값 = 요청) → 직전 활성 기억 → 활성 전환 → 다시 읽기
                          → 요청과 다르면 직전 활성으로 되돌리고 그 값까지 확인될 때만 FAILED
--list                    읽기만(mode=ro) — 버전 목록 · 지금 활성값과 다른 값 수(복구할 버전 고르기)
--activate-version <id>   복구: 그 버전을 같은 검사 · 전환 · 다시 읽기로 활성화
```

발행 · 복구는 잠금 파일(`state/three_push/params/.param_apply.lock` · git 무시 폴더)로 한 번에
하나만 돈다. 앞 실행이 아직 돌고 있으면(PC 응답이 끊긴 뒤 다시 누른 경우 등) 기다리지 않고
UNCONFIRMED(stage=busy)로 끝낸다 — PC 는 읽기만 다시 해 판정한다.

마지막 줄 = `RESULT {json}`. result = SAME · ACTIVATED · FAILED(전환 안 됨 또는 되돌림까지 확인) ·
UNCONFIRMED(결과 확인 불가 · 단정하지 않음) · LIST. 종료 코드 0 · 0 · 2 · 3 · 0. 버전 ID 는 운영자용
출력(`--list` · 복구)에만 있고 PC 웹 응답 · 화면에는 싣지 않는다(판정 §4).
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any, Iterator, Optional


# **루트를 자기 위치에서 계산하지 않는다.** 원격 임시 경로(`state/three_push/params/`)로 업로드돼
# 실행되므로 스크립트 위치의 부모는 프로젝트 루트가 아니다. 호출자가 `--project-root` 로 알려준다.
def _bootstrap(project_root: str) -> Path:
    root = Path(project_root).resolve()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    return root


# 러너와 같은 파일(cron 은 저장소 루트에서 실행)
DB_RELATIVE = Path("state/runtime/runtime_state.sqlite")
ACTIVATED_BY = "pc_param_apply"
RESTORE_BY = "operator_restore"
EXIT = {"SAME": 0, "ACTIVATED": 0, "LIST": 0, "FAILED": 2, "UNCONFIRMED": 3}
LOCK_NAME = ".param_apply.lock"
_KIND_PREFIX = "enabled_push_kinds["

Effective = tuple[frozenset, dict]


def _emit(result: str, **kw: Any) -> int:
    print("RESULT " + json.dumps({"result": result, **kw}, ensure_ascii=False))
    return EXIT[result]


def _effective(param_dict: dict[str, Any]) -> Effective:
    """러너가 쓰는 유효값(PC ① 비교와 같은 규칙) — 알림 종류는 집합 · 나머지는 (형, 수, 글, 참거짓)."""
    from app.runtime_param_store import _split_value_columns, flatten_param_dict

    kinds: set = set()
    plain: dict[str, tuple] = {}
    for key, vtype, value in flatten_param_dict(param_dict):
        if key.startswith(_KIND_PREFIX):
            kinds.add(value)
        else:
            plain[key] = (vtype, *_split_value_columns(vtype, value))
    return frozenset(kinds), plain


def _diff(a: Effective, b: Effective) -> tuple[int, int]:
    """`(비교한 값 수, 다른 값 수)` — PC `oci_status_rows._compare_values` 와 같은 셈."""
    (kinds_a, plain_a), (kinds_b, plain_b) = a, b
    keys = set(plain_a) | set(plain_b)
    diff = sum(1 for k in keys if plain_a.get(k) != plain_b.get(k))
    return len(keys) + len(kinds_a | kinds_b), diff + len(kinds_a ^ kinds_b)


def _rows(param_dict: dict[str, Any]) -> list[list]:
    """PC ① 캐시와 같은 꼴(`param_values_block` 의 rows) — 키 · 형 · 수 · 글 · 참거짓."""
    from app.runtime_param_store import _split_value_columns, flatten_param_dict

    return [
        [key, vtype, *_split_value_columns(vtype, value)]
        for key, vtype, value in flatten_param_dict(param_dict)
    ]


def _read_active(db: Path) -> dict[str, Any]:
    from app.runtime_param_store import read_active_param_dict

    return read_active_param_dict(db)


def _pointer(db: Path) -> Optional[str]:
    from app.runtime_param_store import get_active_pointer

    ptr = get_active_pointer(db)
    return ptr["active_param_version_id"] if ptr else None


def _check_candidate(db: Path, version_id: str, wanted: Effective) -> Optional[str]:
    """DB 에서 다시 만든 버전이 러너 읽기 함수(`from_dict`)를 통과하고 유효값이 요청과 같은가.

    빈 정책 · 빠진 값은 다시 만들면 키가 없어져 러너가 멈춘다 — 기본값으로 채우지 않고 여기서 거른다.
    """
    from app.runtime_param_store import read_param_version, reconstruct_param_dict
    from app.three_push_runtime_param import from_dict

    row = read_param_version(db, version_id)
    if not row:
        return "candidate_missing"
    rebuilt = reconstruct_param_dict(row)
    try:
        from_dict(rebuilt)
    except Exception as e:  # noqa: BLE001
        return f"candidate_invalid:{type(e).__name__}"
    if _diff(_effective(rebuilt), wanted)[1]:
        return "candidate_values_differ"
    return None


def _lock_path(db: Path) -> Path:
    """잠금 파일 — DB 옆(state/runtime · git 추적 폴더)이 아니라 전달 폴더(state/three_push/params ·
    .gitignore 대상 · PC 가 JSON · 임시 도구를 두는 곳)."""
    return db.parent.parent / "three_push" / "params" / LOCK_NAME


@contextlib.contextmanager
def _writer_lock(db: Path) -> Iterator[bool]:
    """발행 · 복구는 한 번에 하나만 — 잡으면 True, 다른 실행이 잡고 있으면 기다리지 않고 False.

    PC 의 SSH 가 시간 초과로 끊겨도 OCI 의 앞 실행은 끝까지 돌 수 있다. 다시 누른 실행이 같은 DB ·
    같은 전달 파일로 겹쳐 돌지 않게 한다. 잠금은 파일을 닫거나 프로세스가 끝나면 풀린다.
    """
    import fcntl

    path = _lock_path(db)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            yield False
            return
        yield True


def _switch(
    db: Path, version_id: str, wanted: Effective, prior: Effective, activated_by: str
) -> int:
    """직전 활성을 기억 → 전환 → 다시 읽기. 요청과 다르면 되돌리고 **이전 값까지 확인될 때만** FAILED."""
    from app.runtime_param_store import activate_param_version

    before_id = _pointer(db)
    try:
        activate_param_version(version_id, activated_by=activated_by, db_path=db)
    except Exception as e:  # noqa: BLE001
        # 한 문장 upsert — 실패면 보통 그대로다. 단정하지 않고 포인터를 읽어 본다.
        try:
            now = _pointer(db)
        except Exception:  # noqa: BLE001
            return _emit("UNCONFIRMED", stage="activate", error=type(e).__name__)
        if now == before_id and now != version_id:
            # 포인터가 그대로 = 직전 버전 그대로(버전은 바뀌지 않는다). 행은 읽히면 싣는다.
            try:
                rows: Optional[list] = _rows(_read_active(db))
            except Exception:  # noqa: BLE001
                rows = None
            return _emit(
                "FAILED",
                stage="activate",
                previous_kept=True,
                error=type(e).__name__,
                rows=rows,
            )
        if now != version_id:
            return _emit("UNCONFIRMED", stage="activate", error=type(e).__name__)
    try:
        back = _read_active(db)
    except Exception as e:  # noqa: BLE001
        return _emit("UNCONFIRMED", stage="readback", error=type(e).__name__)
    n, d = _diff(_effective(back), wanted)
    if d == 0:
        return _emit("ACTIVATED", n=n, version_id=version_id, rows=_rows(back))
    # 다시 읽은 값이 요청과 다르다 → 직전 활성으로 한 번만 되돌린다(되돌리기 자체는 다시 하지 않는다).
    if before_id is None:
        return _emit("UNCONFIRMED", stage="readback", error="no_previous_version")
    try:
        activate_param_version(
            before_id, activated_by=f"{activated_by}:rollback", db_path=db
        )
        restored = _read_active(db)
    except Exception as e:  # noqa: BLE001
        return _emit("UNCONFIRMED", stage="rollback", error=type(e).__name__)
    if _diff(_effective(restored), prior)[1] == 0:
        return _emit(
            "FAILED", stage="readback", previous_kept=True, rows=_rows(restored)
        )
    return _emit("UNCONFIRMED", stage="rollback", error="previous_not_confirmed")


def apply_file(
    json_path: Path,
    *,
    db: Path,
    activated_by: str = ACTIVATED_BY,
    expect_sha256: Optional[str] = None,
) -> int:
    """PC 가 보낸 PARAM 파일을 그대로 발행한다. 실패하면 활성 포인터를 바꾸지 않는다.

    `expect_sha256`(PC 적용은 늘 준다) = PC 가 보낸 파일 바이트의 SHA-256. 다르면 그 사이 다른
    쓰기 · 다른 경로의 파일이다 — 그 값을 대신 발행하지 않고 쓰기 전에 FAILED(설계 §3-3).
    """
    from app.three_push_runtime_param import from_dict

    if not json_path.exists():
        return _emit(
            "FAILED", stage="validate", previous_kept=True, error="missing_file"
        )
    try:
        raw = json_path.read_bytes()
    except OSError as e:
        return _emit(
            "FAILED", stage="validate", previous_kept=True, error=type(e).__name__
        )
    if expect_sha256 and hashlib.sha256(raw).hexdigest() != expect_sha256:
        return _emit(
            "FAILED", stage="validate", previous_kept=True, error="content_mismatch"
        )
    try:
        data = json.loads(raw.decode("utf-8"))
        # 기존 검증(필수 필드 · 허용값 · 금지 키) — 기본값을 채우지 않는다
        from_dict(data)
        wanted = _effective(data)
    except Exception as e:  # noqa: BLE001
        return _emit(
            "FAILED", stage="validate", previous_kept=True, error=type(e).__name__
        )
    if not db.exists():  # 새 DB 를 만들지 않는다(러너가 읽는 파일이 아니게 된다)
        return _emit("FAILED", stage="precheck", previous_kept=True, error="db_missing")
    with _writer_lock(db) as locked:
        if not locked:
            return _emit("UNCONFIRMED", stage="busy", error="another_apply_running")
        return _publish(data, wanted, db=db, activated_by=activated_by)


def _publish(
    data: dict[str, Any], wanted: Effective, *, db: Path, activated_by: str
) -> int:
    """(잠금 안) 지금 활성값과 비교 → 같으면 SAME · 다르면 기록 → 후보 검사 → 전환."""
    from app.runtime_param_store import create_param_version

    try:
        active = _read_active(db)
    except Exception as e:  # noqa: BLE001
        return _emit(
            "FAILED", stage="precheck", previous_kept=True, error=type(e).__name__
        )
    prior = _effective(active)
    n, d = _diff(prior, wanted)
    if d == 0:
        return _emit("SAME", n=n, rows=_rows(active))
    try:
        version_id, _, _ = create_param_version(data, db_path=db)
    except Exception as e:  # noqa: BLE001
        return _emit(
            "FAILED", stage="create", previous_kept=True, error=type(e).__name__
        )
    problem = _check_candidate(db, version_id, wanted)
    if problem:
        return _emit("FAILED", stage="candidate", previous_kept=True, error=problem)
    return _switch(db, version_id, wanted, prior, activated_by)


def activate_version(
    version_id: str, *, db: Path, activated_by: str = RESTORE_BY
) -> int:
    """복구 — 이미 있는 버전을 같은 검사 · 전환 · 다시 읽기로 활성화한다(새 버전을 만들지 않는다)."""
    if not db.exists():
        return _emit("FAILED", stage="precheck", previous_kept=True, error="db_missing")
    with _writer_lock(db) as locked:
        if not locked:
            return _emit("UNCONFIRMED", stage="busy", error="another_apply_running")
        return _restore(version_id, db=db, activated_by=activated_by)


def _restore(version_id: str, *, db: Path, activated_by: str) -> int:
    from app.runtime_param_store import read_param_version, reconstruct_param_dict

    try:
        prior = _effective(_read_active(db))
        row = read_param_version(db, version_id)
    except Exception as e:  # noqa: BLE001
        return _emit(
            "FAILED", stage="precheck", previous_kept=True, error=type(e).__name__
        )
    if not row:
        return _emit(
            "FAILED", stage="validate", previous_kept=True, error="unknown_version"
        )
    wanted = _effective(reconstruct_param_dict(row))
    problem = _check_candidate(db, version_id, wanted)
    if problem:
        return _emit("FAILED", stage="candidate", previous_kept=True, error=problem)
    n, d = _diff(prior, wanted)
    if d == 0:
        return _emit("SAME", n=n, version_id=version_id)
    return _switch(db, version_id, wanted, prior, activated_by)


def list_versions(db: Path) -> int:
    """읽기만(mode=ro) — 버전마다 만든 때 · 출처 · 지금 활성값과 다른 값 수. `*` = 지금 활성."""
    if not db.exists():
        return _emit("FAILED", stage="precheck", previous_kept=True, error="db_missing")
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        ptr = con.execute(
            "SELECT active_param_version_id, activated_at, activated_by "
            "FROM runtime_param_active WHERE active_scope = ?",
            ("three_push",),
        ).fetchone()
        versions = con.execute(
            "SELECT param_version_id, created_at, param_source "
            "FROM runtime_param_version ORDER BY created_at DESC"
        ).fetchall()

        def effective_of(version_id: str) -> Effective:
            kinds: set = set()
            plain: dict[str, tuple] = {}
            for key, vtype, num, text, boolean in con.execute(
                "SELECT param_key, value_type, numeric_value, text_value, boolean_value "
                "FROM runtime_param_value WHERE param_version_id = ?",
                (version_id,),
            ):
                if key.startswith(_KIND_PREFIX):
                    kinds.add(text)
                else:
                    plain[key] = (vtype, num, text, boolean)
            return frozenset(kinds), plain

        active_id = ptr[0] if ptr else None
        active = effective_of(active_id) if active_id else (frozenset(), {})
        if ptr:
            print(f"지금 활성: {ptr[0]} · 활성화 {ptr[1]} · {ptr[2]}")
        for version_id, created_at, source in versions:
            mark = "*" if version_id == active_id else " "
            d = _diff(effective_of(version_id), active)[1]
            print(
                f"{mark} {version_id} · 만든 때 {created_at} · {source} · 지금 활성값과 다른 값 {d}개"
            )
    finally:
        con.close()
    return _emit("LIST", count=len(versions))


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="POC5-27 OCI PARAM 발행 · 복구 도구")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--json", type=Path, help="발행할 PARAM 파일(PC 가 보낸 값 그대로)"
    )
    mode.add_argument("--list", action="store_true", help="버전 목록(읽기만)")
    mode.add_argument("--activate-version", help="복구: 이 버전 ID 를 활성화")
    ap.add_argument("--activated-by", default=None)
    ap.add_argument(
        "--expect-sha256",
        default=None,
        help="--json 과 함께: PC 가 보낸 파일 바이트의 SHA-256(다르면 쓰기 전에 FAILED)",
    )
    ap.add_argument(
        "--project-root",
        required=True,
        help="`app` 패키지가 있는 디렉터리. 업로드 위치와 무관하게 명시한다",
    )
    a = ap.parse_args(argv)
    root = _bootstrap(a.project_root)
    db = root / DB_RELATIVE
    if a.list:
        return list_versions(db)
    if a.activate_version:
        return activate_version(
            a.activate_version, db=db, activated_by=a.activated_by or RESTORE_BY
        )
    return apply_file(
        a.json,
        db=db,
        activated_by=a.activated_by or ACTIVATED_BY,
        expect_sha256=a.expect_sha256,
    )


if __name__ == "__main__":
    sys.exit(main())
