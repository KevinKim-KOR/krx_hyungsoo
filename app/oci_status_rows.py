"""「OCI 운영·적용」 ① 표의 '장중 대표 ETF' · '운영 기준 활성' 행 — POC3-02D-OPS-04 항목 3 · 6.

`oci_startup_status.refresh_snapshot` 의 기동 시 SSH 읽기 1회에 붙는 원격 블록 2개(읽기 전용)와
그 출력으로 행을 만드는 순수 함수다. I/O 는 `param_active_job` 의 PC 운영 기준 JSON 읽기뿐이다.

```text
대표 ETF  같은 날이면 09:20 기록 · 아니면 08:10 기록 · 지난 기록도 기준일과 함께(설계자 Q3 a/a)
          못 읽으면 숫자를 보이지 않는다(0 · 정상 아님)
활성      OCI 러너가 쓰는 유효값과 PC 운영 기준을 같은 펼침 규칙으로 비교(Q7 b) — 버전 ID 가
          달라도 값이 같으면 일치 · `param_id` 는 꺼내지 않는다 · DB 는 mode=ro(Q8 a)
```
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:  # 순환 import 없이 타입만
    from app.oci_startup_status import OciJobStatus

_KST = timezone(timedelta(hours=9))


def _job(job: str, status: str, detail: str) -> "OciJobStatus":
    from app.oci_startup_status import OciJobStatus

    return OciJobStatus(job=job, status=status, detail=detail)


# ── 원격 블록 ────────────────────────
# 원격 블록은 heredoc 으로 넘긴다(셸 따옴표 · `$` 해석을 피한다). 블록이 실패해도 `{}` 를
# 찍고 0 으로 끝난다 — 마지막 명령의 종료 코드가 SSH 읽기 전체의 성패라서다.

_REPS_FILES = (
    (
        "batch",
        "state/market/oci_market_data_batch_state.json",
        "refresh_date_kst",
        "refresh_completed_at",
    ),
    (
        "reinforce",
        "state/market/oci_krx_reinforcement_state.json",
        "date_kst",
        "finished_at",
    ),
)


def representatives_block(home: str) -> str:
    """08:10 · 09:20 KRX 기록에서 날짜 · 기록 시각 · 대표 커버리지만 꺼내 JSON 1줄."""
    files = ", ".join(
        f"({name!r}, {home + '/' + path!r}, {dkey!r}, {tkey!r})"
        for name, path, dkey, tkey in _REPS_FILES
    )
    return (
        "python3 - <<'PY' 2>/dev/null || echo '{}'\n"
        "import json\n"
        "out = {}\n"
        f"for name, path, dkey, tkey in ({files},):\n"
        "    try:\n"
        "        d = json.load(open(path, encoding='utf-8'))\n"
        "        out[name] = {'date': d.get(dkey), 'at': d.get(tkey),\n"
        "                     'reps': d.get('krx_representatives')}\n"
        "    except Exception:\n"
        "        out[name] = None\n"
        "print(json.dumps(out))\n"
        "PY"
    )


def param_values_block(home: str) -> str:
    """OCI 러너가 읽는 활성 PARAM 값(포인터 → 버전 행 → 값 행). `mode=ro` · 버전 ID 는 꺼내지 않는다."""
    uri = f"file:{home}/state/runtime/runtime_state.sqlite?mode=ro"
    return (
        "python3 - <<'PY' 2>/dev/null || echo '{}'\n"
        "import json, sqlite3\n"
        "try:\n"
        f"    con = sqlite3.connect({uri!r}, uri=True)\n"
        "    rows = con.execute(\n"
        "        'SELECT v.param_key, v.value_type, v.numeric_value, v.text_value, '\n"
        "        'v.boolean_value FROM runtime_param_active a '\n"
        "        'JOIN runtime_param_version p '\n"
        "        'ON p.param_version_id = a.active_param_version_id '\n"
        "        'JOIN runtime_param_value v ON v.param_version_id = p.param_version_id '\n"
        "        'WHERE a.active_scope = ?', ('three_push',)).fetchall()\n"
        "    print(json.dumps({'rows': rows}))\n"
        "except Exception as e:\n"
        "    print(json.dumps({'error': type(e).__name__}))\n"
        "PY"
    )


def _md(iso_day: Any) -> Optional[str]:
    try:
        d = date.fromisoformat(str(iso_day)[:10])
    except ValueError:
        return None
    return f"{d.month}/{d.day}"


def _kst_stamp(iso: Any) -> Optional[str]:
    """ISO 시각 → KST `M/D HH:MM`. 못 읽으면 None."""
    try:
        dt = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    k = dt.astimezone(_KST)
    return f"{k.month}/{k.day} {k:%H:%M}"


def representatives_job(raw: str) -> "OciJobStatus":
    """'장중 대표 ETF' 행(설계자 Q3 a/a). 같은 날이면 09:20 기록 · 아니면 08:10 기록.

    못 읽으면 숫자를 보이지 않는다(0 · 정상으로 보이지 않는다) — `not_evaluated` 는
    `missing = []` 라 그대로 세면 '27/27' 이 되므로 셈하지 않는다.
    """
    unknown = _job("intraday_representatives", "UNKNOWN", "기록을 읽지 못함")
    try:
        data = json.loads(raw.strip() or "{}")
    except ValueError:
        return unknown
    if not isinstance(data, dict):
        return unknown
    batch, rein = data.get("batch"), data.get("reinforce")
    rec = batch
    if (
        isinstance(rein, dict)
        and isinstance(rein.get("reps"), dict)
        and rein.get("date")
        and (not isinstance(batch, dict) or rein.get("date") == batch.get("date"))
    ):
        rec = rein
    reps = rec.get("reps") if isinstance(rec, dict) else None
    if not isinstance(reps, dict):
        return unknown
    status = reps.get("status")
    if status == "intraday_config_unavailable":
        return _job("intraday_representatives", "UNKNOWN", "활성 설정을 읽지 못함")
    count, missing = reps.get("count"), reps.get("missing")
    basis = _md(reps.get("expected_previous_trading_day"))
    if (
        status not in ("ok", "representative_missing")
        or not isinstance(count, int)
        or isinstance(count, bool)
        or count <= 0
        or not isinstance(missing, list)
        or len(missing) > count
        or basis is None
    ):
        return unknown
    when = _kst_stamp(rec.get("at"))
    tail = f" ({when} 확인)" if when else ""
    head = f"기준일 {basis} · {count - len(missing)}/{count} 준비됨"
    if status == "ok" and not missing:
        return _job("intraday_representatives", "SUCCESS", head + tail)
    return _job(
        "intraday_representatives", "STALE", f"{head} · {len(missing)}종 빠짐{tail}"
    )


_ENABLED_KEY = re.compile(r"^enabled_push_kinds\[\d+\]$")


def _compare_values(pc: dict[str, tuple], oci: dict[str, tuple]) -> tuple[int, int]:
    """`(비교한 값 수, 다른 값 수)`. `enabled_push_kinds[i]` 는 집합으로 본다 — 러너는 포함
    여부만 본다(순서만 다르면 같다 · 빠지거나 더해진 종류마다 1개 다름)."""
    kinds = [
        {v for k, v in vals.items() if _ENABLED_KEY.match(k)} for vals in (pc, oci)
    ]
    plain = [
        {k: v for k, v in vals.items() if not _ENABLED_KEY.match(k)}
        for vals in (pc, oci)
    ]
    keys = set(plain[0]) | set(plain[1])
    diff = sum(1 for k in keys if plain[0].get(k) != plain[1].get(k))
    return len(keys) + len(kinds[0] | kinds[1]), diff + len(kinds[0] ^ kinds[1])


def parse_param_values(raw: str) -> Optional[dict[str, tuple]]:
    """활성 PARAM 값 블록(`param_values_block`) JSON → 값 사전. 못 읽으면 None.

    `{param_key: (value_type, numeric, text, boolean)}`.
    """
    try:
        data = json.loads(raw.strip() or "{}")
        rows = data.get("rows") if isinstance(data, dict) else None
        if not isinstance(rows, list) or not rows:
            return None
        out: dict[str, tuple] = {}
        for key, vtype, num, text, boolean in rows:
            out[str(key)] = (
                str(vtype),
                None if num is None else float(num),
                None if text is None else str(text),
                None if boolean is None else int(boolean),
            )
        return out
    except (ValueError, TypeError):
        return None


def param_active_job(
    oci_values: Optional[dict[str, tuple]],
    pc_json_path: Path,
    last_sync_ok: Optional[bool],
) -> "OciJobStatus":
    """'운영 기준 활성' 행(설계자 Q7 b) — 러너가 실제로 쓰는 유효값으로 비교한다.

    PC 운영 기준 JSON 을 PARAM 버전을 만들 때와 같은 규칙(`flatten_param_dict` ·
    `_split_value_columns`)으로 펼쳐 OCI 활성값과 비교한다. 버전 ID 가 달라도 값이 같으면
    일치다. '전달만 되고 활성화되지 않음' 은 마지막 전달이 성공했을 때만 붙인다(전달 실패
    날에는 사실이 아니다).
    """
    from app.runtime_param_store import _split_value_columns, flatten_param_dict

    if not oci_values:
        return _job("param_active", "UNKNOWN", "OCI 에서 쓰는 값을 읽지 못함")
    try:
        data = json.loads(pc_json_path.read_text(encoding="utf-8"))
        pc = {
            k: (vt, *_split_value_columns(vt, v))
            for k, vt, v in flatten_param_dict(data)
        }
    except Exception:  # noqa: BLE001 - 파일 없음 · 손상 · 표현 불가 → 이 행만 확인 불가
        return _job("param_active", "UNKNOWN", "전달한 운영 기준을 읽지 못함")
    n, diff = _compare_values(pc, oci_values)
    if not diff:
        return _job(
            "param_active",
            "SUCCESS",
            f"전달한 운영 기준이 OCI 에서 쓰는 값과 같음 ({n}/{n})",
        )
    tail = " — 전달만 되고 활성화되지 않음" if last_sync_ok else ""
    return _job(
        "param_active",
        "STALE",
        f"OCI 는 다른 값으로 동작 중 ({n}개 중 {diff}개 다름){tail}",
    )


__all__ = [
    "param_active_job",
    "param_values_block",
    "parse_param_values",
    "representatives_block",
    "representatives_job",
]
