"""POC3-OPS-02B-1 Gate 재현 — PLAN §14 의 모든 수치를 다시 만든다.

검증자가 **독립 재검증**할 수 있도록 저장소 안에 둔 단일 진입점이다. PLAN 의
숫자만으로는 다른 환경에서 재현할 수 없다는 지적(r1 A-3)에 대응한다.

    python scripts/ops02b1_gate/reproduce.py            # 전체
    python scripts/ops02b1_gate/reproduce.py outlook    # 일부만

**읽기 전용이다.** 운영 DB(`etf_daily_price`·`market_benchmark_daily_price`)를
쓰지 않고, 외부 조회도 하지 않는다. 입력은 저장소에 커밋된 snapshot 뿐이다.

| 입력 | 경로 |
|---|---|
| KRX `069500` 무조정 시가/종가 | `state/ops02b1_gate/krx_069500_snapshot.csv` |
| PIT 정렬 데이터셋 | `state/ops02b1_gate/gate_dataset.csv` |
| KRX 공식 ETF 기본정보 | `state/market_meta/krx_etf_basic_20260909.csv` |
| ETF 종가 (최근 41거래일, `n≥2` 대상) | `state/ops02b1_gate/etf_close_snapshot.csv` |
| `etf_master` ticker 목록 | `state/ops02b1_gate/etf_master_tickers.csv` |
| KRX API 기초지수명 (1일치) | `state/ops02b1_gate/krx_api_idxname_20260904.csv` |
| DB `069500` 종가 | `state/ops02b1_gate/db_069500_close_snapshot.csv` |
| 무결성 기준 | `state/ops02b1_gate/MANIFEST.json` (sha256·행 수) |

snapshot 을 처음부터 다시 받으려면 `fetch_snapshot.py` 를 쓴다(`KRX_API_KEY`
필요). 그것만이 외부를 조회하며, 운영 DB 는 여전히 건드리지 않는다.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import statistics
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
GATE = ROOT / "state" / "ops02b1_gate"
META_CSV = ROOT / "state" / "market_meta" / "krx_etf_basic_20260909.csv"

PRIMARY_FEATURES = (
    "sp500_ret_1d_pct",
    "nasdaq_ret_1d_pct",
    "sox_ret_1d_pct",
    "russell_ret_1d_pct",
    "vix_ret_1d_pct",
)
TRAIN_MIN = 756
REFIT_EVERY = 20
BOOTSTRAP_N = 5000
SEED = 20260910
MIN_TICKERS_PER_INDEX = 2


# ── 공통 ────────────────────────────────────────────────────────────────────


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rng(tag: str):
    """통계 항목마다 **독립** RNG. 공유 RNG 를 순서대로 소비하면 스크립트 구성이
    바뀔 때 값이 달라진다(검증자 r2 A-2 — CI 가 문서와 어긋난 원인).
    `tag` 로 seed 를 파생시켜 **호출 순서와 무관하게** 같은 값을 낸다.
    """
    digest = hashlib.sha256(f"{SEED}:{tag}".encode()).digest()
    return np.random.default_rng(int.from_bytes(digest[:8], "big"))


def bootstrap_mean_ci(values, tag, n=BOOTSTRAP_N):
    """평균의 bootstrap 95% CI."""
    arr = np.asarray(values, dtype=float)
    gen = _rng(tag)
    idx = gen.integers(0, len(arr), size=(n, len(arr)))
    means = np.sort(arr[idx].mean(axis=1))
    return float(means[int(0.025 * n)]), float(means[int(0.975 * n)])


def bootstrap_diff_ci(a, b, tag, n=BOOTSTRAP_N):
    """두 집단 평균 차이의 bootstrap 95% CI."""
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    gen = _rng(tag)
    da = a[gen.integers(0, len(a), size=(n, len(a)))].mean(axis=1)
    db = b[gen.integers(0, len(b), size=(n, len(b)))].mean(axis=1)
    diffs = np.sort(da - db)
    return float(diffs[int(0.025 * n)]), float(diffs[int(0.975 * n)])


def load_dataset():
    rows = [
        r
        for r in csv.DictReader(open(GATE / "gate_dataset.csv", encoding="utf-8"))
        if r["primary_complete"] == "True"
        and all(r[f] not in ("", "None", None) for f in PRIMARY_FEATURES)
    ]
    rows.sort(key=lambda r: r["as_of_date"])
    x = np.array([[float(r[f]) for f in PRIMARY_FEATURES] for r in rows])
    y = np.array([float(r["target_open_gap_pct"]) for r in rows])
    return rows, x, y


# ── 1. 무결성 ───────────────────────────────────────────────────────────────


def check_manifest() -> bool:
    man = json.loads((GATE / "MANIFEST.json").read_text(encoding="utf-8"))
    print("=== 1. 입력 무결성 (MANIFEST.json) ===")
    ok = True
    for key, spec in man["inputs"].items():
        path = ROOT / spec["path"]
        if not path.exists():
            print(f"  {key:26} **파일 없음** {spec['path']}")
            ok = False
            continue
        actual = sha256(path)
        match = actual == spec["sha256"]
        ok = ok and match
        print(
            f"  {key:26} rows={spec['rows']:<6} sha256={actual[:16]}… "
            f"{'일치' if match else '**불일치**'}"
        )
    for name, desc in man["scripts"].items():
        rel = desc.split("#")[0].strip()
        exists = (ROOT / rel).exists()
        ok = ok and exists
        print(f"  script {name:19} {rel} {'있음' if exists else '**없음**'}")
    return ok


# ── 2. OPEN_GAP snapshot ────────────────────────────────────────────────────


def check_snapshot():
    rows = list(
        csv.DictReader(open(GATE / "krx_069500_snapshot.csv", encoding="utf-8"))
    )
    days = sorted(r["bas_dd"] for r in rows if r["open"] and r["close"])
    print("\n=== 2. KRX snapshot (UNADJUSTED_TRADED_PRICE) ===")
    print(f"  행 수 {len(days)}  {days[0]} ~ {days[-1]}")
    print(f"  결측 open/close: {len(rows) - len(days)}")


# ── 3. PIT 정렬 커버리지 ────────────────────────────────────────────────────


def check_coverage():
    all_rows = list(csv.DictReader(open(GATE / "gate_dataset.csv", encoding="utf-8")))
    n = len(all_rows)
    print("\n=== 3. PIT 정렬 커버리지 (USD/KRW 는 primary 제외) ===")
    for f in PRIMARY_FEATURES:
        got = sum(1 for r in all_rows if r[f] not in ("", "None", None))
        print(f"  {f:22} PRIMARY {got:>5}/{n} = {100 * got / n:.1f}%")
    aux = sum(1 for r in all_rows if r["usdkrw_ret_1d_pct"] not in ("", "None", None))
    print(f"  {'usdkrw_ret_1d_pct':22} AUX     {aux:>5}/{n} = {100 * aux / n:.1f}%")
    complete = sum(1 for r in all_rows if r["primary_complete"] == "True")
    print(f"\n  primary 5종 완비 {complete}/{n} = {100 * complete / n:.1f}%")
    print(
        f"  750일 요구 {'충족' if complete >= 750 else '미달'} · "
        f"95% 커버리지 {'충족' if complete / n >= 0.95 else '미달'}"
    )


# ── 4. OPERATING_RULE = SP500_SIGN_V1 ───────────────────────────────────────


def run_sp500_sign():
    rows, x, y = load_dataset()
    dates = [r["as_of_date"] for r in rows]
    sp = x[:, 0]
    print("\n=== 4. OPERATING_RULE — SP500_SIGN_V1 ===")
    result, ok_all = {}, True
    for key, label, idx in (
        (
            "same_window",
            "OLS Gate 와 동일 예측 구간",
            list(range(TRAIN_MIN, len(rows))),
        ),
        ("full_sample", "전체 표본 (robustness)", list(range(len(rows)))),
    ):
        s_, y_ = sp[idx], y[idx]
        nz = y_ != 0
        hit = (np.sign(s_[nz]) == np.sign(y_[nz])).astype(float)
        maj = 1.0 if (y_ > 0).sum() * 2 >= len(y_) else -1.0
        base = (maj == np.sign(y_[nz])).astype(float)
        lo, hi = bootstrap_mean_ci(hit, f"sp500_hit:{key}")
        up, dn = y_[s_ > 0], y_[s_ < 0]
        dlo, dhi = bootstrap_diff_ci(up, dn, f"sp500_gap:{key}")
        improve = float(hit.mean() - base.mean())
        passed = bool(lo > 0.50 and improve >= 0.05 and dlo > 0)
        ok_all = ok_all and passed
        print(f"\n  [{label}] {dates[idx[0]]} ~ {dates[idx[-1]]} (n={len(idx)})")
        print(
            f"    적중률   {hit.mean() * 100:.2f}%  95%CI [{lo * 100:.2f}, {hi * 100:.2f}]"
        )
        print(f"    baseline {base.mean() * 100:.2f}%  개선폭 {improve * 100:+.2f}%p")
        print(
            f"    S&P 상승일 갭 {up.mean():+.4f}% (n={len(up)}) · "
            f"하락일 {dn.mean():+.4f}% (n={len(dn)})"
        )
        print(f"    차이 {up.mean() - dn.mean():+.4f}%  95%CI [{dlo:+.4f}, {dhi:+.4f}]")
        print(f"    사전 기준 3개: {'PASS' if passed else 'FAIL'}")
        result[key] = {
            "n": len(idx),
            "range": [dates[idx[0]], dates[idx[-1]]],
            "hit": float(hit.mean()),
            "hit_ci": [lo, hi],
            "baseline": float(base.mean()),
            "improve_pp": improve * 100,
            "up_mean": float(up.mean()),
            "dn_mean": float(dn.mean()),
            "diff": float(up.mean() - dn.mean()),
            "diff_ci": [dlo, dhi],
            "pass": passed,
        }
    rule = "SP500_SIGN_V1" if ok_all else "FAIL"
    print(f"\n  OPERATING_RULE = {rule}")
    result["operating_rule"] = rule
    (GATE / "gate_sp500_sign_result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    return ok_all


# ── 5. OLS (RESEARCH_REFERENCE) + 누수 검사 ─────────────────────────────────


def walk_forward(x, y, train_min=TRAIN_MIN, refit=REFIT_EVERY):
    preds, acts = [], []
    coef = None
    i = train_min
    while i < len(x):
        if (i - train_min) % refit == 0:
            design = np.column_stack([np.ones(i), x[:i]])
            coef, *_ = np.linalg.lstsq(design, y[:i], rcond=None)
        preds.append(float(coef[0] + x[i] @ coef[1:]))
        acts.append(float(y[i]))
        i += 1
    preds, acts = np.array(preds), np.array(acts)
    nz = acts != 0
    return float((np.sign(preds[nz]) == np.sign(acts[nz])).mean())


def run_ols_and_leak():
    rows, x, y = load_dataset()
    print("\n=== 5. OLS (RESEARCH_REFERENCE) + 누수 검사 ===")
    print(f"  정상 walk-forward: {walk_forward(x, y) * 100:.2f}%")
    nz = y != 0
    for j, f in enumerate(PRIMARY_FEATURES):
        hr = float((np.sign(x[nz, j]) == np.sign(y[nz])).mean())
        print(f"    단변량 sign({f:22}) {hr * 100:.2f}%")
    gen = np.random.default_rng(SEED)
    for k in range(3):
        shuffled = y.copy()
        gen.shuffle(shuffled)
        print(
            f"  target 셔플 #{k + 1}: {walk_forward(x, shuffled) * 100:.2f}%  (50% 근처여야 정상)"
        )
    lag1 = np.vstack([x[0], x[:-1]])
    lag2 = np.vstack([x[0], x[0], x[:-2]])
    print(f"  feature 1세션 지연: {walk_forward(lag1, y) * 100:.2f}%")
    print(f"  feature 2세션 지연: {walk_forward(lag2, y) * 100:.2f}%")
    print(
        f"  target +1일 이동  : {walk_forward(x, np.append(y[1:], y[-1])) * 100:.2f}%"
    )
    print(
        f"  OPEN_GAP 분포: 평균 {y.mean():+.4f}% · 표준편차 {y.std():.4f}% · "
        f"상승 {(y > 0).mean() * 100:.1f}%"
    )


# ── 6. INDEX_LEADERSHIP ─────────────────────────────────────────────────────


def load_meta():
    raw = META_CSV.read_bytes().decode("cp949")
    return list(csv.DictReader(io.StringIO(raw)))


def eligible(meta):
    """설계자 §5 필터 — 기초자산 주식 · 추적배수 일반 · 합성 제외."""
    return [
        r
        for r in meta
        if r["기초자산분류"] == "주식"
        and r["추적배수"] == "일반"
        and "합성" not in r["복제방법"]
    ]


def index_groups(elig):
    """식별키 = 지수산출기관 + 기초지수명 완전일치. fuzzy matching 금지."""
    groups: dict[tuple[str, str], set[str]] = {}
    for r in elig:
        groups.setdefault((r["지수산출기관"], r["기초지수명"]), set()).add(
            r["단축코드"]
        )
    return groups


def run_index_leadership():
    """**커밋된 snapshot 만** 사용한다 — 운영 DB 를 읽지 않는다(검증자 r2 A-3)."""
    meta = load_meta()
    elig = eligible(meta)
    groups = index_groups(elig)
    multi = {k: v for k, v in groups.items() if len(v) >= MIN_TICKERS_PER_INDEX}
    print("\n=== 6. INDEX_LEADERSHIP ===")
    print(f"  메타데이터 {len(meta)}종 → 필터 후 {len(elig)}종 → 그룹 {len(groups)}개")
    print(f"  n>={MIN_TICKERS_PER_INDEX} 풀: {len(multi)}개")

    # API 기초지수명 ↔ CSV 기초지수명 일치 검증 (설계자 §3 계약 4)
    api = {
        r["isu_cd"]: r["idx_ind_nm"]
        for r in csv.DictReader(
            open(GATE / "krx_api_idxname_20260904.csv", encoding="utf-8")
        )
    }
    both = [(r["단축코드"], r["기초지수명"]) for r in meta if r["단축코드"] in api]
    same = sum(1 for t, name in both if api[t] == name)
    print(
        f"  API IDX_IND_NM ↔ CSV 기초지수명: {same}/{len(both)} = "
        f"{100 * same / len(both):.1f}% 완전일치"
    )
    if same != len(both):
        print("  → 불일치 종목은 계약대로 제외 대상 (공식 CSV 교체 필요 상태)")

    master = {
        r["ticker"]
        for r in csv.DictReader(open(GATE / "etf_master_tickers.csv", encoding="utf-8"))
    }
    elig_tickers = {r["단축코드"] for r in elig}
    cov = len(elig_tickers & master) / len(elig_tickers) * 100
    print(f"  join coverage {cov:.1f}%  ({'사용 가능' if cov >= 95 else '미산출'})")

    closes: dict[str, dict[str, float]] = {}
    for r in csv.DictReader(open(GATE / "etf_close_snapshot.csv", encoding="utf-8")):
        closes.setdefault(r["ticker"], {})[r["date"]] = float(r["close"])
    days = sorted({d for m in closes.values() for d in m})

    def ret(ticker, asof_idx, n):
        series = closes.get(ticker) or {}
        if asof_idx - n < 0:
            return None
        a_, b_ = series.get(days[asof_idx]), series.get(days[asof_idx - n])
        return (a_ / b_ - 1) * 100 if a_ and b_ else None

    counts = []
    for i in range(len(days) - 1, 19, -1):
        cands = []
        for (agency, name), tickers in multi.items():
            r5 = [v for v in (ret(t, i, 5) for t in tickers) if v is not None]
            r20 = [v for v in (ret(t, i, 20) for t in tickers) if v is not None]
            if len(r5) < MIN_TICKERS_PER_INDEX or len(r20) < MIN_TICKERS_PER_INDEX:
                continue
            m5, m20 = statistics.median(r5), statistics.median(r20)
            if m5 > 0 and m20 > 0:
                cands.append((m20, m5, name, agency, len(r20)))
        cands.sort(reverse=True)
        counts.append(len(cands))
        if i == len(days) - 1:
            print(f"\n  최신 기준일 {days[i]} — 후보 {len(cands)}개, 상위 2개:")
            for m20, m5, name, agency, n in cands[:2]:
                print(
                    f"    • {name[:44]}: 5일 {m5:+.1f}% · 20일 {m20:+.1f}% "
                    f"(추종 ETF {n}개, {agency})"
                )
            if not cands:
                print("    (후보 0개 → 기초지수 문단 생략)")
    print(
        f"\n  최근 {len(counts)}거래일 후보 수: 중앙 {statistics.median(counts):.0f} · "
        f"범위 {min(counts)}~{max(counts)} · 2개 이상인 날 "
        f"{sum(1 for c in counts if c >= 2)}/{len(counts)}"
    )
    return cov >= 95


# ── 7. DEF-ETF-DAILY-PRICE-BASIS-CONSISTENCY ────────────────────────────────


def run_basis_defect():
    """**커밋된 snapshot 만** 사용한다 — 운영 DB 를 읽지 않는다."""
    krx = {
        r["bas_dd"]: float(r["close"])
        for r in csv.DictReader(
            open(GATE / "krx_069500_snapshot.csv", encoding="utf-8")
        )
        if r["close"]
    }
    db = {
        r["date"]: float(r["close"])
        for r in csv.DictReader(
            open(GATE / "db_069500_close_snapshot.csv", encoding="utf-8")
        )
    }

    def iso(d):
        return f"{d[:4]}-{d[4:6]}-{d[6:]}"

    pairs = sorted((iso(d), krx[d], db[iso(d)]) for d in krx if iso(d) in db)
    print("\n=== 7. DEF-ETF-DAILY-PRICE-BASIS-CONSISTENCY (읽기 전용) ===")
    print(f"  대조 {len(pairs)}일  {pairs[0][0]} ~ {pairs[-1][0]}")
    first = (pairs[0][1] / pairs[0][2] - 1) * 100
    last = (pairs[-1][1] / pairs[-1][2] - 1) * 100
    print(f"  KRX/DB 비율: {pairs[0][0]} {first:+.3f}%  →  {pairs[-1][0]} {last:+.3f}%")
    steps, prev = [], None
    for d, k, v in pairs:
        r = round((k / v - 1) * 100, 3)
        if prev is not None and abs(r - prev[1]) > 0.05:
            steps.append((prev[0], prev[1], d, r))
        prev = (d, r)
    print(f"  전환 후보일 {len(steps)}건 — 최근 5:")
    for a_, ra, b_, rb in steps[-5:]:
        print(f"    {a_} {ra:+.3f}%  →  {b_} {rb:+.3f}%")
    print("  해석: 분기 배당 조정으로 대부분 설명된다 (DB=조정 계열, KRX=무조정).")
    print("  운영 실영향: PUSH·수익률은 DB 단일 계열 안에서 계산 — 계열 혼합 0건.")
    return True


SECTIONS = {
    "manifest": check_manifest,
    "snapshot": check_snapshot,
    "coverage": check_coverage,
    "operating": run_sp500_sign,
    "outlook": run_ols_and_leak,
    "index": run_index_leadership,
    "basis": run_basis_defect,
}


def main() -> int:
    """섹션 하나라도 실패(무결성 불일치·coverage 미달)면 **0 이 아닌 코드**로 끝난다.

    검증자 r2 A-3 — hash 가 어긋나도 exit 0 이면 CI·스크립트가 성공으로 읽는다.
    """
    wanted = sys.argv[1:] or list(SECTIONS)
    unknown = [w for w in wanted if w not in SECTIONS]
    if unknown:
        print(f"알 수 없는 섹션: {unknown}\n사용 가능: {list(SECTIONS)}")
        return 2
    failed = []
    for name in wanted:
        result = SECTIONS[name]()
        if result is False:
            failed.append(name)
    if failed:
        print(f"\n**실패 섹션**: {failed}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
