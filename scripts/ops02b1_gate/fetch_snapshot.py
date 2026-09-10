"""OPS-02B-1 Gate — KRX Open API 에서 069500 평가 행만 추출.

설계자 정정 §1 확정:
  OPEN_GAP_t = KRX t일 무조정 시가 / KRX 직전 거래일 무조정 종가 - 1
  source = KRX_OPEN_API · price_basis = UNADJUSTED_TRADED_PRICE

- **일별 응답 전체를 적재하지 않는다.** `069500` 행만 추출한다.
- 운영 DB(`etf_daily_price`)를 **읽지도 쓰지도 않는다.**
- 재실행 가능(이미 받은 날짜는 건너뜀).
"""

import csv
import hashlib
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "state" / "ops02b1_gate" / "krx_069500_snapshot.csv"
TICKER = "069500"
URL = "https://data-dbg.krx.co.kr/svc/apis/etp/etf_bydd_trd"


def _num(v):
    return (v or "").replace(",", "")


def read_api_key() -> str:
    """`.env` 의 `KRX_API_KEY`. 키는 출력하지 않는다."""
    for line in open(ROOT / ".env", encoding="utf-8"):
        if line.startswith("KRX_API_KEY="):
            return line.strip().split("=", 1)[1].strip()
    raise SystemExit(".env 에 KRX_API_KEY 가 없다")


key = read_api_key()

# 한국 거래일 축 — FDR 069500 거래일 (평가 축과 동일)
sys.path.insert(0, str(ROOT))
import FinanceDataReader as fdr  # noqa: E402

kr = fdr.DataReader(TICKER, "2015-01-01", "2026-09-09")
days = [d.strftime("%Y%m%d") for d in kr.index]
print(f"대상 거래일 {len(days)}  {days[0]} ~ {days[-1]}", flush=True)

done = {}
if OUT.exists():
    with open(OUT, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            done[r["bas_dd"]] = r
    print(f"기존 {len(done)}일 재사용", flush=True)

FIELDS = [
    "bas_dd",
    "isu_cd",
    "open",
    "high",
    "low",
    "close",
    "acc_trdvol",
    "acc_trdval",
    "idx_ind_nm",
]
new = 0
miss = []
t0 = time.time()
with httpx.Client(timeout=40.0, headers={"AUTH_KEY": key}) as cli:
    for i, d in enumerate(days):
        if d in done:
            continue
        try:
            r = cli.get(URL, params={"basDd": d})
            rows = r.json().get("OutBlock_1") or []
        except Exception as e:
            miss.append((d, f"{type(e).__name__}"))
            continue
        row = next((x for x in rows if x["ISU_CD"] == TICKER), None)
        if row is None:
            miss.append((d, "no_row"))
            continue
        done[d] = {
            "bas_dd": d,
            "isu_cd": TICKER,
            "open": _num(row["TDD_OPNPRC"]),
            "high": _num(row["TDD_HGPRC"]),
            "low": _num(row["TDD_LWPRC"]),
            "close": _num(row["TDD_CLSPRC"]),
            "acc_trdvol": _num(row["ACC_TRDVOL"]),
            "acc_trdval": _num(row["ACC_TRDVAL"]),
            "idx_ind_nm": row.get("IDX_IND_NM", ""),
        }
        new += 1
        if new % 200 == 0:
            el = time.time() - t0
            print(f"  {new}건 ({i+1}/{len(days)}) {el:.0f}s", flush=True)
            with open(OUT, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, FIELDS)
                w.writeheader()
                for k in sorted(done):
                    w.writerow(done[k])

with open(OUT, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, FIELDS)
    w.writeheader()
    for k in sorted(done):
        w.writerow(done[k])

h = hashlib.sha256(OUT.read_bytes()).hexdigest()
print(f"\n완료: {len(done)}일 (신규 {new})  누락 {len(miss)}")
if miss:
    print("  누락 샘플:", miss[:8])
print(f"파일: {OUT}")
print(f"sha256: {h}")
print(f"소요: {time.time()-t0:.0f}s")
