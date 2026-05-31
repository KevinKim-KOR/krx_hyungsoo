"""ETF Constituents Source Diagnosis — POC2 1차 (2026-05-27).

진단 목적 (지시문 §4):
1. pykrx PDF (`get_etf_portfolio_deposit_file`) 의 no_data 가 날짜 문제인지,
   함수 운영 문제인지, ticker coverage 문제인지 격리.
2. Naver Mobile ETF Component API (`m.stock.naver.com/api/etf/<ticker>/component`)
   smoke test — 1차 후보 source 로 사용 가능한지 분류.
3. 결과를 JSON artifact + Markdown 리포트로 영속화.

원칙:
- 외부 API 사용 — Naver 는 비공식. 인증 회피 / 우회성 동작 금지 (단순 GET).
- 결과 데이터 추정 X / source 불명 ok 처리 X.
- 진단은 대표 3 종 ETF × 4 날짜 (= 최대 12 호출). 전체 universe 수집 아님.
- 실측 결과만 기록.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# 진단 대상 (지시문 §5.2 / §6.2).
TICKERS_FOR_DIAGNOSIS = [
    {"ticker": "069500", "label": "대표 시장 (KODEX 200)"},
    {"ticker": "139260", "label": "국내 섹터 (TIGER 200 IT)"},
    {"ticker": "411420", "label": "테마/해외형 (Market Discovery 후보)"},
]

# pykrx 날짜 격리 — 지시문 §5.3.
TEST_DATES = [
    {"date": "2026-05-27", "label": "현재 asof (수)"},
    {"date": "2026-05-26", "label": "직전 영업일 (화)"},
    {"date": "2026-05-15", "label": "과거 확실한 영업일 (금)"},
    {"date": "2026-04-30", "label": "최근 월말 (분기말 인근)"},
    {"date": "2026-03-31", "label": "분기말 (1Q)"},
]

NAVER_API_BASE = "https://m.stock.naver.com/api/etf"
NAVER_TIMEOUT_SEC = 10
PYKRX_SOURCE_LABEL = "pykrx/get_etf_portfolio_deposit_file"
NAVER_SOURCE_LABEL = "naver_mobile_etf_component"

ARTIFACT_JSON_PATH = Path("state/market/constituents_source_diagnosis_latest.json")
ARTIFACT_MD_PATH = Path("docs/handoff/ETF_CONSTITUENTS_SOURCE_DIAGNOSIS.md")


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ─── pykrx PDF 진단 ──────────────────────────────────────────────────


def _pykrx_one_call(ticker: str, yyyymmdd: str) -> dict:
    """pykrx 1회 호출 결과 dict (status / row_count / columns / error)."""
    try:
        from pykrx import stock
    except Exception as e:  # noqa: BLE001
        return {
            "status": "import_failed",
            "row_count": 0,
            "columns": [],
            "error": f"{type(e).__name__}: {e}",
        }
    try:
        df = stock.get_etf_portfolio_deposit_file(yyyymmdd, ticker)
    except Exception as e:  # noqa: BLE001
        return {
            "status": "call_failed",
            "row_count": 0,
            "columns": [],
            "error": f"{type(e).__name__}: {e}",
        }
    if df is None:
        return {"status": "none", "row_count": 0, "columns": [], "error": None}
    try:
        cols = list(df.columns)
    except Exception:  # noqa: BLE001
        cols = []
    return {
        "status": "ok" if len(df) > 0 else "no_data",
        "row_count": int(len(df)),
        "columns": [str(c) for c in cols],
        "error": None,
    }


def diagnose_pykrx() -> dict:
    """대표 3 ETF × 5 날짜 호출 결과 집계."""
    results: list[dict] = []
    for tk in TICKERS_FOR_DIAGNOSIS:
        for dt in TEST_DATES:
            yyyymmdd = dt["date"].replace("-", "")
            out = _pykrx_one_call(tk["ticker"], yyyymmdd)
            results.append(
                {
                    "ticker": tk["ticker"],
                    "ticker_label": tk["label"],
                    "asof": dt["date"],
                    "asof_label": dt["label"],
                    **out,
                }
            )
    # 분류 (지시문 §5.4).
    ok_count = sum(1 for r in results if r["status"] == "ok")
    no_data_count = sum(1 for r in results if r["status"] == "no_data")
    call_failed = sum(1 for r in results if r["status"] == "call_failed")
    import_failed = sum(1 for r in results if r["status"] == "import_failed")

    # 분류 로직 — 결과 기반.
    if import_failed > 0:
        classification = "pykrx_operational_issue"
        pdf_decision = "hold"
    elif ok_count == 0 and no_data_count > 0:
        classification = "pykrx_operational_issue"
        pdf_decision = "hold"
    elif ok_count > 0 and no_data_count > 0:
        # 일부 날짜/ticker 만 성공.
        per_ticker_ok = {
            tk["ticker"]: any(
                r["status"] == "ok" and r["ticker"] == tk["ticker"] for r in results
            )
            for tk in TICKERS_FOR_DIAGNOSIS
        }
        if all(per_ticker_ok.values()):
            classification = "date_issue"
            pdf_decision = "needs_asof_adjustment"
        else:
            classification = "coverage_issue"
            pdf_decision = "needs_asof_adjustment"
    elif call_failed > 0 and ok_count == 0:
        classification = "pykrx_operational_issue"
        pdf_decision = "hold"
    else:
        classification = "inconclusive"
        pdf_decision = "unknown"

    return {
        "source": PYKRX_SOURCE_LABEL,
        "total_calls": len(results),
        "ok_count": ok_count,
        "no_data_count": no_data_count,
        "call_failed_count": call_failed,
        "import_failed_count": import_failed,
        "classification": classification,
        "pdf_decision": pdf_decision,
        "details": results,
    }


# ─── Naver Mobile ETF Component API smoke test ──────────────────────


def _naver_one_call(ticker: str) -> dict:
    """Naver Mobile ETF Component API 1회 호출."""
    url = f"{NAVER_API_BASE}/{ticker}/component"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json,text/plain,*/*",
        "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
    }
    req = urllib.request.Request(url, headers=headers, method="GET")
    out: dict = {
        "url": url,
        "http_status": None,
        "is_json": False,
        "json_keys": [],
        "row_count": 0,
        "sample_item_keys": [],
        "sample_item": None,
        "error": None,
    }
    try:
        with urllib.request.urlopen(req, timeout=NAVER_TIMEOUT_SEC) as resp:
            out["http_status"] = resp.status
            body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        out["http_status"] = e.code
        out["error"] = f"HTTPError: {e}"
        return out
    except Exception as e:  # noqa: BLE001
        out["error"] = f"{type(e).__name__}: {e}"
        return out
    try:
        data = json.loads(body)
    except Exception as e:  # noqa: BLE001
        out["error"] = f"json_parse_failed: {type(e).__name__}: {e}"
        out["sample_item"] = body[:200]
        return out
    out["is_json"] = True
    if isinstance(data, dict):
        out["json_keys"] = sorted(data.keys())
        # 후보 array 키 — componentList / components / data 등.
        arr = None
        for k in ("componentList", "components", "data", "items"):
            if k in data and isinstance(data[k], list):
                arr = data[k]
                out["array_key"] = k
                break
        if arr is None:
            # dict 안에 array 가 있는지 일반 탐색.
            for k, v in data.items():
                if isinstance(v, list) and v and isinstance(v[0], dict):
                    arr = v
                    out["array_key"] = k
                    break
        if arr is not None:
            out["row_count"] = len(arr)
            if arr:
                first = arr[0]
                if isinstance(first, dict):
                    out["sample_item_keys"] = sorted(first.keys())
                    out["sample_item"] = first
    elif isinstance(data, list):
        out["row_count"] = len(data)
        if data and isinstance(data[0], dict):
            out["sample_item_keys"] = sorted(data[0].keys())
            out["sample_item"] = data[0]
    return out


def _detect_field(keys: list[str], candidates: list[str]) -> Optional[str]:
    """후보 키 중 keys 에 실제로 있는 첫 번째 반환."""
    low = {k.lower(): k for k in keys}
    for c in candidates:
        if c.lower() in low:
            return low[c.lower()]
    return None


def diagnose_naver() -> dict:
    """대표 3 ETF 에 대한 smoke test."""
    results: list[dict] = []
    for tk in TICKERS_FOR_DIAGNOSIS:
        out = _naver_one_call(tk["ticker"])
        sample_keys = out.get("sample_item_keys") or []
        # 필드 후보 (지시문 §6.1).
        code_field = _detect_field(
            sample_keys, ["componentItemCode", "itemCode", "code", "symbol", "ticker"]
        )
        name_field = _detect_field(
            sample_keys, ["componentName", "itemName", "name", "stockName"]
        )
        weight_field = _detect_field(
            sample_keys,
            ["componentReute", "weight", "weightRate", "weightPct", "rate"],
        )
        results.append(
            {
                "ticker": tk["ticker"],
                "ticker_label": tk["label"],
                **out,
                "detected_code_field": code_field,
                "detected_name_field": name_field,
                "detected_weight_field": weight_field,
            }
        )

    # 운영 분류 (지시문 §6.4).
    usable = sum(
        1
        for r in results
        if r.get("http_status") == 200
        and r.get("is_json")
        and r.get("row_count", 0) > 0
        and r.get("detected_code_field")
        and r.get("detected_weight_field")
    )
    if usable == len(results):
        operational = "usable"
    elif usable > 0:
        operational = "partial"
    else:
        operational = "unusable"

    # asof 또는 update 필드 탐지 (top-level keys 중).
    asof_field_candidates = ["bizDate", "baseDate", "updateDate", "asof"]
    asof_field_detected: list[str] = []
    for r in results:
        for k in asof_field_candidates:
            if k in (r.get("json_keys") or []):
                asof_field_detected.append(k)
                break

    return {
        "source": NAVER_SOURCE_LABEL,
        "total_calls": len(results),
        "operational_classification": operational,
        "asof_field_candidates_found": list(set(asof_field_detected)),
        "details": results,
    }


# ─── artifact 저장 ──────────────────────────────────────────────────


def save_json_artifact(payload: dict) -> Path:
    ARTIFACT_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_JSON_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    return ARTIFACT_JSON_PATH


def _fmt_pykrx_table(pykrx: dict) -> str:
    lines = [
        "| ticker | asof | status | rows | error |",
        "|---|---|---|---|---|",
    ]
    for r in pykrx["details"]:
        err = (r.get("error") or "")[:60]
        lines.append(
            f"| `{r['ticker']}` ({r['ticker_label']}) | {r['asof']} | "
            f"**{r['status']}** | {r['row_count']} | {err} |"
        )
    return "\n".join(lines)


def _fmt_naver_table(naver: dict) -> str:
    lines = [
        "| ticker | http | json | rows | code field | name field | weight field |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in naver["details"]:
        lines.append(
            f"| `{r['ticker']}` ({r['ticker_label']}) | "
            f"{r.get('http_status', '-')} | "
            f"{'yes' if r.get('is_json') else 'no'} | "
            f"{r.get('row_count', 0)} | "
            f"{r.get('detected_code_field') or '-'} | "
            f"{r.get('detected_name_field') or '-'} | "
            f"{r.get('detected_weight_field') or '-'} |"
        )
    return "\n".join(lines)


def save_md_artifact(payload: dict) -> Path:
    pykrx = payload["pykrx"]
    naver = payload["naver"]
    krx_next = payload["krx_open_api_needed_next"]

    md = [
        "# ETF Constituents Source Diagnosis (POC2 1차)",
        "",
        f"실행 시각 (UTC): `{payload['executed_at']}`",
        "",
        "본 문서는 ETF 구성종목 수집 실패 원인의 단계적 격리 + Naver Mobile API",
        "smoke test 결과 (지시문 §4 / §5 / §6) 의 실측 기록입니다. 결과는 임의",
        "추정 없이 호출 1건당 실제 응답만 남깁니다.",
        "",
        "## 1. pykrx PDF 진단",
        "",
        f"- 분류: **{pykrx['classification']}**",
        f"- PDF 운영 판정: **{pykrx['pdf_decision']}**",
        f"- 총 호출 {pykrx['total_calls']}회 / ok {pykrx['ok_count']} / "
        f"no_data {pykrx['no_data_count']} / call_failed {pykrx['call_failed_count']} / "
        f"import_failed {pykrx['import_failed_count']}",
        "",
        _fmt_pykrx_table(pykrx),
        "",
        "## 2. Naver Mobile ETF Component API smoke test",
        "",
        f"- 운영 분류: **{naver['operational_classification']}**",
        f"- asof/update 후보 필드 (top-level): "
        f"{naver['asof_field_candidates_found'] or '없음'}",
        "",
        _fmt_naver_table(naver),
        "",
        "## 3. KRX Open API / 공식 provider 후속 필요 여부",
        "",
        f"- **{krx_next}**",
        "",
        "조건 (지시문 §8): pykrx 날짜 보정 실패 + 대표 ETF 테스트 실패 + Naver",
        "smoke test 실패 셋이 모두 충족되면 후속 필요.",
        "",
        "## 4. 다음 단계 후보 (지시문 §21)",
        "",
        f"- {payload['next_step_candidate']}",
        "",
        "## 5. JSON artifact",
        "",
        f"- `{ARTIFACT_JSON_PATH.as_posix()}`",
    ]
    ARTIFACT_MD_PATH.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD_PATH.write_text("\n".join(md), encoding="utf-8")
    return ARTIFACT_MD_PATH


def _decide_next_step(pykrx: dict, naver: dict) -> tuple[str, bool]:
    """(다음 STEP 후보 라벨, KRX Open API 후속 필요 여부)."""
    naver_op = naver["operational_classification"]
    pykrx_dec = pykrx["pdf_decision"]
    if naver_op == "usable":
        return ("A. ETF Constituents Naver Source Integration", False)
    if naver_op == "partial":
        return ("B. ETF Constituents Source Fallback Policy", False)
    # naver_op == "unusable"
    if pykrx_dec in ("hold", "unknown"):
        return ("C. KRX Open API / Official Provider Source Design", True)
    if pykrx_dec == "needs_asof_adjustment":
        return ("D. ETF Constituents asof 보정", False)
    return ("inconclusive — 사용자 결정 필요", False)


def run_diagnosis() -> dict:
    pykrx = diagnose_pykrx()
    naver = diagnose_naver()
    next_label, krx_needed = _decide_next_step(pykrx, naver)
    payload = {
        "executed_at": _utcnow_iso(),
        "pykrx": pykrx,
        "naver": naver,
        "krx_open_api_needed_next": krx_needed,
        "next_step_candidate": next_label,
    }
    save_json_artifact(payload)
    save_md_artifact(payload)
    return payload


def _print_summary(payload: dict) -> None:
    pykrx = payload["pykrx"]
    naver = payload["naver"]
    print(f"=== pykrx ===")
    print(f"  classification: {pykrx['classification']}")
    print(f"  pdf_decision: {pykrx['pdf_decision']}")
    print(f"  ok/no_data/call_failed = {pykrx['ok_count']}/"
          f"{pykrx['no_data_count']}/{pykrx['call_failed_count']}")
    print(f"=== Naver ===")
    print(f"  operational: {naver['operational_classification']}")
    print(f"  asof candidates: {naver['asof_field_candidates_found']}")
    print(f"=== Next ===")
    print(f"  step: {payload['next_step_candidate']}")
    print(f"  krx_open_api_needed: {payload['krx_open_api_needed_next']}")
    print(f"=== Artifacts ===")
    print(f"  JSON: {ARTIFACT_JSON_PATH}")
    print(f"  MD:   {ARTIFACT_MD_PATH}")


if __name__ == "__main__":
    p = run_diagnosis()
    _print_summary(p)
    # exit 코드는 항상 0 — 진단은 실패도 정보다.
    sys.exit(0)
