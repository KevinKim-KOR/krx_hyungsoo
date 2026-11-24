"""POC7-03 고정 설정(recipe) · 잠금 기대값 · 코드 해시 대상 — PLAN V1 §2 ~ §4 · 판정 2026-11-24.

```text
입력   봉인 KRX krx_etf_universe_v1(파일 · 내용 해시 = POC7-01 고정값 그대로)
설정   1개월(끝 − 30일 이후 069500 첫 거래일) · 주 마감 5번(네 구간) · 세 자리 · 편입 D+1 시가
       · 편입일 = 0일 · 20거래일 뒤 공통 시가 · 편입 · 청산 각 20bp(참고 40bp)
       본 구간 2021-01-01 ~ 2026-08-21(294주 · 회고) · 보조 2014-01-01 ~ 2020-12-31(방향만)
판정   PLAN §4 · 판정 Q5 숫자 — 결과를 보고 바꾸지 않는다
기대값 PLAN §1-4 분모(선정 뒤 가격을 보기 전 수) — 다르면 CheckRequired
```
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from app.entry_timing import protocol as EP
from app.ml_evidence import store

CheckRequired = EP.CheckRequired  # 같은 예외(입력 · 잠금이 고정과 다름)
PROTOCOL_ID = "poc7-03-v1"
SCHEMA = {
    "lock": "poc7_03_lock_v1",
    "run": "poc7_03_run_v1",
    "report": "poc7_03_report_v1",
    "verify": "poc7_03_verify_v1",
    "week": "poc7_03_week_v1",
    "cross_check": "poc7_03_cross_check_v1",
}
REPO = EP.REPO
ROOT = REPO / "state" / "ml" / "research" / "poc7_03"
BENCH = EP.BENCH

LOOKBACK_1M, LOOKBACK_3M = 30, 90
N_PICK = 3
N_INTERVALS = 4  # 네 구간 = 주 마감 5번
HOLD_DAYS = 20  # 편입일 = 0일 · 20거래일 뒤 공통 시가
COST, ALT_COST = 0.002, 0.004
UP_EPS = 1e-9  # 비율 차이 이 값 이하 = 변화 없음(오름 아님)
SPANS = {"main": ("2021-01-01", "2026-08-21"), "aux": ("2014-01-01", "2020-12-31")}
SUBS = (
    ("2021-01-01", "2022-12-31"),
    ("2023-01-01", "2024-12-31"),
    ("2025-01-01", "2026-08-21"),
)
VALID_WEEKS_MIN = 236  # 294 × 80% = 235.2
UNCONFIRMED_SHARE_MAX = 0.05
GAIN_MIN = 0.002  # 0.20%p(한 번 20거래일 보유)
SUB_WINS_MIN = 2
MDD_WORSE_MAX = 0.01  # 1.0%p
TURN_MORE_MAX = 0.5
DIFF_WEEKS_MIN = 26
TOP_EXCLUDE = 5
AVAILABILITY = "공개 일정상 D+1 08:00 · 과거 실제 수신 시각 미확인"
PRICE_NOTE = (
    "비용 후 가격 모의 결과 — 봉인 KRX 기준가 연결 가격(분배금 미반영) · 실제 계좌 성과 아님 · "
    "회고 자료(2021 ~ 2026 은 다른 연구에서 이미 쓴 기간) · 운영 채택 아님"
)
RECORD_KIND = "뒤에 복원한 목록(봉인 KRX · 그날 이름)"

# PLAN §1-4 실측(2026-11-24 · 선정 뒤 가격을 보기 전). prepare 가 다시 세어 다르면 멈춘다.
EXPECTED: dict[str, dict[str, int]] = {
    "main": {"weeks": 294, "common_missing": 0},
    "aux": {"weeks": 360, "common_missing": 1},
}

# 이 연구의 코드(잠금 · 실행 · 검산이 대조) + 불러 쓰는 POC7-01 · 운영 순수 함수 파일
CODE_FILES = (
    "app/candidate_compare/__init__.py",
    "app/candidate_compare/protocol.py",
    "app/candidate_compare/rules.py",
    "app/candidate_compare/population.py",
    "app/candidate_compare/study.py",
    "app/candidate_compare/flow.py",
    "app/candidate_compare/verify.py",
    "app/candidate_compare/report.py",
    "scripts/run_candidate_compare.py",
    "app/krx_sealed_reader.py",
    "app/entry_timing/data.py",
    "app/entry_timing/protocol.py",
    "app/entry_timing/study.py",
    "app/entry_timing/weekly.py",
)
ENV_LIBS = ("numpy",)


@dataclass(frozen=True)
class Config:
    """경로 · 고정값 묶음. 시험은 tmp 경로와 자기 기대값을 넣는다(라이브 DB 를 열지 않는다)."""

    db: Path = EP.DB
    version: str = EP.VERSION
    file_sha: Optional[str] = EP.FILE_SHA
    content_sha: Optional[str] = EP.CONTENT_SHA
    root: Path = ROOT
    repo: Path = REPO
    spans: dict = field(default_factory=lambda: dict(SPANS))
    subs: tuple = SUBS
    expected: Optional[dict] = field(default_factory=lambda: EXPECTED)
    valid_weeks_min: int = VALID_WEEKS_MIN

    def entry_timing(self) -> EP.Config:
        """봉인 읽기(POC7-01 `data.load`)에 넘길 설정 — 봉인 경로 · 해시만 쓴다."""
        return EP.Config(
            db=self.db,
            version=self.version,
            file_sha=self.file_sha,
            content_sha=self.content_sha,
            root=self.root,
            repo=self.repo,
            expected=None,
            cross_check_poc6=False,
        )


def recipe(cfg: Config) -> dict[str, Any]:
    """결과 전 잠금 설정(PLAN §2 ~ §4) — 실행 · 검산이 같은 값을 쓴다."""
    return {
        "window_1m": f"끝 − {LOOKBACK_1M}일 이후 {BENCH} 첫 거래일 ~ 신호일(운영 1개월 규칙)",
        "name_filter": "그날 이름에 인버스 · 레버리지 · 2X · 2배 · 합성 · 선물(운영 규칙)",
        "weekly": f"주 마감 {N_INTERVALS + 1}번(W-4 ~ W0 = 신호일 · ISO 주 마지막 거래일) · "
        "같은 가격 구간 · 끝 값 > 시작 값 = 오름 · 변화 없음(비율 차이 ≤ 1e-9) = 오름 아님 · 값 없음 = 미확인",
        "rule_a": "공통 후보군 1개월 내림차순 · 같으면 종목코드 오름차순 · 위 3",
        "rule_b": "공통 후보군 중 1개월 > 0 → 오른 주 수 내림차순 → 1개월 순위 · 위 3 · 모자라면 1개월 순위로 채움",
        "n_pick": N_PICK,
        "entry": "신호 다음 거래일 합성 시가(O*)",
        "exit": f"편입일 = 0일 · {HOLD_DAYS}거래일 뒤 공통 합성 시가",
        "availability": AVAILABILITY,
        "costs": {"base": COST, "reference": ALT_COST, "legs": "편입 · 청산 각각"},
        "slots": "세 자리 · 원금 3분의 1씩 · 편입 불가 확인(행 있음 · 거래량 ≤ 0) = 현금 0%",
        "missing_base": "편입 미확인 · 청산 미확인 자리가 하나라도 있으면 그 주 두 묶음 함께 평가 불가",
        "missing_alt": "편입 미확인 = 현금 · 청산 미확인 = 같은 구간 평가일까지 마지막 유효 종가(참고 평가액 · 청산 비용)",
        "spans": cfg.spans,
        "subs": [list(s) for s in cfg.subs],
        "bootstrap": {
            "block_weeks": EP.BLOCK_WEEKS,
            "draws": EP.DRAWS,
            "seed": EP.SEED,
            "function": "app.entry_timing.study.bootstrap(POC7-01 과 같음)",
        },
        "criteria": {
            "valid_weeks_min": cfg.valid_weeks_min,
            "unconfirmed_share_max": UNCONFIRMED_SHARE_MAX,
            "gain_min": GAIN_MIN,
            "sub_wins_min": SUB_WINS_MIN,
            "mdd_worse_max": MDD_WORSE_MAX,
            "turn_more_max": TURN_MORE_MAX,
            "diff_weeks_min": DIFF_WEEKS_MIN,
            "order": "판정 불가 → 미달 → 연구 후보(① ~ ⑦) → 효용 미확인",
        },
        "top_exclude": TOP_EXCLUDE,
    }


def code_hashes(repo: Path) -> dict[str, str]:
    return {rel: store.sha256_file(Path(repo) / rel) for rel in CODE_FILES}


def env() -> dict[str, Any]:
    import importlib.metadata
    import sys

    out: dict[str, Any] = {"python": sys.version.split()[0]}
    for lib in ENV_LIBS:
        try:
            out[lib] = importlib.metadata.version(lib)
        except importlib.metadata.PackageNotFoundError:
            out[lib] = None
    return out
