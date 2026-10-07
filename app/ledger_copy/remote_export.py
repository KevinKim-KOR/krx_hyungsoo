"""POC5-03 — OCI 원장 읽기 전용 export(표준 라이브러리만 · PC 가 SSH 표준입력으로 보내 실행).

PLAN `docs/ai_plan/POC5/POC5-03_PC_LEDGER_SYNC_AND_FEEDBACK_PLAN_V1.md` §2-1.

```text
실행    python3 - <원장 경로>   (PC `sync.py` 의 고정 명령 · OCI 저장소에 이 파일을 두지 않는다)
출력    JSONL — header 1줄 → row N줄 → end 1줄 · 원장 파일이 없으면 header(ledger=absent) + end
오류    error 1줄(예외 종류만) · exit 3 — 본문 · 경로 · 메시지는 내보내지 않는다
인코딩  JSON 을 ASCII 로만 낸다(한글은 유니코드 이스케이프) — 원격 locale · U+2028 같은 줄 구분 문자가 줄을 깨지 않는다
읽기    file:<경로>?mode=ro 한 연결 · 읽기 트랜잭션 하나로 5표 스냅샷(쓰기 · DDL · PRAGMA 변경 0)
```

원격 finalize 는 item · delivery INSERT 와 run 갱신을 한 트랜잭션으로 커밋한다. 표마다 따로 읽으면
그 사이 커밋으로 어긋난 스냅샷이 나올 수 있어 한 트랜잭션 안에서 모두 읽는다.
"""

import json
import os
import sqlite3
import sys

FORMAT = "decision_ledger_export.v1"
TABLES = ("evaluation_run", "signal_item", "delivery", "ledger_meta", "price_outcome")
_ORDER = {
    "evaluation_run": "event_id",
    "signal_item": "event_id, item_seq",
    "delivery": "event_id",
    "ledger_meta": "key",
    "price_outcome": "event_id, item_seq, series_id, horizon",
}


def _emit(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=True, separators=(",", ":")) + "\n")


def main(argv):
    path = argv[1]
    if not os.path.exists(path):
        _emit({"kind": "header", "format": FORMAT, "ledger": "absent", "tables": {}})
        _emit({"kind": "end", "counts": {}})
        return 0
    con = sqlite3.connect("file:" + path + "?mode=ro", uri=True, timeout=5.0)
    try:
        con.row_factory = sqlite3.Row
        con.execute("BEGIN")
        names = {
            r[0]
            for r in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        tables = {t: t in names for t in TABLES}
        _emit(
            {"kind": "header", "format": FORMAT, "ledger": "present", "tables": tables}
        )
        counts = {}
        for t in TABLES:
            if not tables[t]:
                continue
            n = 0
            for row in con.execute("SELECT * FROM " + t + " ORDER BY " + _ORDER[t]):
                _emit({"kind": "row", "table": t, "row": dict(row)})
                n += 1
            counts[t] = n
        con.execute("ROLLBACK")
    finally:
        con.close()
    _emit({"kind": "end", "counts": counts})
    return 0


if __name__ == "__main__":
    try:
        code = main(sys.argv)
    except Exception as e:  # noqa: BLE001 — 종류만 내보낸다(본문 · 경로 · 메시지 0)
        _emit({"kind": "error", "error_type": type(e).__name__})
        code = 3
    sys.stdout.flush()
    sys.exit(code)
