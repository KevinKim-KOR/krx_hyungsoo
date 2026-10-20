"""POC6-01 — 키움 REST `ka10051`(업종별투자자순매수) 코스피 종합 행 읽기(인증 · 이 조회만).

사용자 승인 범위(2026-10-20): 접근토큰 발급(`au10001`) + `ka10051`(코스피 `mrkt_tp=0` · 금액 `amt_qty_tp=0` ·
KRX `stex_tp=1`)뿐이다. 주문 · 잔고 · 다른 TR · SDK 없음. 앱키는 PC `.env`(`KIWOOM_APP_KEY` ·
`KIWOOM_APP_SECRET`)에서만 읽고, 키 · 토큰은 로그 · 예외 문구 · 응답에 싣지 않는다. 토큰은 이 프로세스
메모리에서만 재사용한다(만료 5분 전 다시 발급 · 디스크 저장 없음).

응답 사실(PLAN §9-8 표본): 코스피 종합 행 = `inds_cd "001"` · `inds_nm "종합(KOSPI)"` · 순매수 필드 =
억원 정수(부호 문자열 · `"-0"` 가능). 기관계(`orgn_netprps`) = 기관 세부 합 — 함께 더하지 않는다. 매수 ·
매도 · 거래대금은 없다. 값을 못 읽으면 0 으로 바꾸지 않고 실패다. 행의 지수값(`cur_prc` ÷ 100)은
저장 코스피 종가와 같아야 한다(표본 4개 날짜 일치 · 다르면 범위 · 날짜가 섞인 것 → 그 날짜 실패).
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

import requests

HOST = "https://api.kiwoom.com"
TOKEN_PATH = "/oauth2/token"
SECT_PATH = "/api/dostk/sect"
REQUEST_TIMEOUT_S = 15
KOSPI_ROW = "001"
EOK_TO_WON = 100_000_000

# 원천 필드 → 저장 분류(app.supply_fx_oil_store.INVESTORS)
FIELD_TO_INVESTOR: dict[str, str] = {
    "ind_netprps": "individual",
    "frgnr_netprps": "foreign",
    "orgn_netprps": "institution",
    "etc_corp_netprps": "other_corp",
    "native_trmt_frgnr_netprps": "native_foreign",
    "natn_netprps": "nation",
    "sc_netprps": "inst_securities",
    "insrnc_netprps": "inst_insurance",
    "invtrt_netprps": "inst_trust",
    "bank_netprps": "inst_bank",
    "jnsinkm_netprps": "inst_other_finance",
    "endw_netprps": "inst_pension",
    "samo_fund_netprps": "inst_private_fund",
}
_SIGNED_INT = re.compile(r"^[+-]?\d+$")
_default_post = requests.post  # 시험은 이 속성을 막는다(실제 키움 호출 금지)


class KiwoomFlowError(Exception):
    """인증 · 조회 · 응답 형식 실패(키 · 토큰은 문구에 넣지 않는다)."""


class KiwoomAuthError(KiwoomFlowError):
    """토큰 발급 실패(등록 IP · 앱키 · 서비스 상태) — 이번 갱신의 수급 조회를 바로 멈춘다."""


def _reason(r, body: dict) -> str:
    return f"HTTP {r.status_code} · 코드 {body.get('return_code')} · {body.get('return_msg')}"


def parse_eok(raw: object) -> int:
    """`"+8475"` · `"-0"` → 정수 원. 비어 있음 · 수 아님 = 실패(0 으로 바꾸지 않는다)."""
    if not isinstance(raw, str) or not _SIGNED_INT.match(raw.strip()):
        raise KiwoomFlowError(f"순매수 값을 읽을 수 없음: {raw!r}")
    return int(raw.strip()) * EOK_TO_WON


class KiwoomClient:
    def __init__(
        self,
        app_key: str,
        app_secret: str,
        *,
        http_post: Optional[Callable] = None,
        now: Optional[Callable[[], datetime]] = None,
    ):
        self._key, self._secret = app_key, app_secret
        self._post = http_post or _default_post
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._token: Optional[str] = None
        self._expires: Optional[datetime] = None

    def _token_value(self) -> str:
        if (
            self._token
            and self._expires
            and self._now() < self._expires - timedelta(minutes=5)
        ):
            return self._token
        r = self._post(
            HOST + TOKEN_PATH,
            json={
                "grant_type": "client_credentials",
                "appkey": self._key,
                "secretkey": self._secret,
            },
            headers={"Content-Type": "application/json;charset=UTF-8"},
            timeout=REQUEST_TIMEOUT_S,
        )
        try:
            body = r.json()
        except ValueError as e:
            raise KiwoomAuthError(f"토큰 응답 형식 오류(HTTP {r.status_code})") from e
        token, exp = body.get("token"), body.get("expires_dt")
        if r.status_code != 200 or body.get("return_code") != 0 or not token or not exp:
            raise KiwoomAuthError(f"토큰 발급 실패({_reason(r, body)})")
        # expires_dt = 한국 시각 YYYYMMDDHHMMSS
        kst = timezone(timedelta(hours=9))
        self._expires = datetime.strptime(str(exp), "%Y%m%d%H%M%S").replace(tzinfo=kst)
        self._token = token
        return token

    def kospi_net_by_investor(self, base_date: str) -> tuple[dict[str, int], float]:
        """그날(YYYY-MM-DD) 코스피 종합 행 투자자별 순매수(정수 원)와 그 행의 지수값.

        지수값 = `cur_prc`(지수 × 100 · 부호 = 등락 방향) → 호출자가 저장 코스피 종가와 대조한다.
        """
        r = self._post(
            HOST + SECT_PATH,
            json={
                "mrkt_tp": "0",
                "amt_qty_tp": "0",
                "base_dt": base_date.replace("-", ""),
                "stex_tp": "1",
            },
            headers={
                "Content-Type": "application/json;charset=UTF-8",
                "authorization": f"Bearer {self._token_value()}",
                "api-id": "ka10051",
            },
            timeout=REQUEST_TIMEOUT_S,
        )
        try:
            body = r.json()
        except ValueError as e:
            raise KiwoomFlowError(
                f"{base_date} 응답 형식 오류(HTTP {r.status_code})"
            ) from e
        if r.status_code != 200 or body.get("return_code") != 0:
            raise KiwoomFlowError(f"{base_date} 조회 실패({_reason(r, body)})")
        row = next(
            (
                x
                for x in body.get("inds_netprps") or []
                if x.get("inds_cd") == KOSPI_ROW
            ),
            None,
        )
        if row is None:
            raise KiwoomFlowError(f"{base_date} 코스피 종합 행(001) 없음")
        nets = {
            inv: parse_eok(row.get(field)) for field, inv in FIELD_TO_INVESTOR.items()
        }
        price = row.get("cur_prc")
        if not isinstance(price, str) or not _SIGNED_INT.match(price.strip()):
            raise KiwoomFlowError(f"{base_date} 지수값을 읽을 수 없음: {price!r}")
        return nets, abs(int(price.strip())) / 100
