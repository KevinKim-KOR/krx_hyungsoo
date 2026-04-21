"""KIS 종목정보파일 기반 국내 ETF 마스터 조회 유틸리티."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from io import BytesIO, StringIO
from zipfile import ZipFile

import pandas as pd
import requests

from config import KIS_KOSDAQ_MASTER_URL, KIS_KOSPI_MASTER_URL
from utils.db_manager import get_db_connection
from utils.logger import get_app_logger

logger = get_app_logger()
_COLLECTION_NAME = "etf_market_master"
_MASTER_ID = "kor_etf_market"

_KOSPI_TAIL_WIDTH = 227
_KOSDAQ_TAIL_WIDTH = 221

_KOSPI_FIELD_SPECS = [
    2,
    1,
    4,
    4,
    4,
    1,
    1,
    1,
    1,
    1,
    1,
    1,
    1,
    1,
    1,
    1,
    1,
    1,
    1,
    1,
    1,
    1,
    1,
    1,
    1,
    1,
    1,
    1,
    1,
    1,
    1,
    9,
    5,
    5,
    1,
    1,
    1,
    2,
    1,
    1,
    1,
    2,
    2,
    2,
    3,
    1,
    3,
    12,
    12,
    8,
    15,
    21,
    2,
    7,
    1,
    1,
    1,
    1,
    1,
    9,
    9,
    9,
    5,
    9,
    8,
    9,
    3,
    1,
    1,
    1,
]

_KOSPI_FIELD_NAMES = [
    "그룹코드",
    "시가총액규모",
    "지수업종대분류",
    "지수업종중분류",
    "지수업종소분류",
    "제조업",
    "저유동성",
    "지배구조지수종목",
    "KOSPI200섹터업종",
    "KOSPI100",
    "KOSPI50",
    "KRX",
    "ETP",
    "ELW발행",
    "KRX100",
    "KRX자동차",
    "KRX반도체",
    "KRX바이오",
    "KRX은행",
    "SPAC",
    "KRX에너지화학",
    "KRX철강",
    "단기과열",
    "KRX미디어통신",
    "KRX건설",
    "Non1",
    "KRX증권",
    "KRX선박",
    "KRX섹터_보험",
    "KRX섹터_운송",
    "SRI",
    "기준가",
    "매매수량단위",
    "시간외수량단위",
    "거래정지",
    "정리매매",
    "관리종목",
    "시장경고",
    "경고예고",
    "불성실공시",
    "우회상장",
    "락구분",
    "액면변경",
    "증자구분",
    "증거금비율",
    "신용가능",
    "신용기간",
    "전일거래량",
    "액면가",
    "상장일자",
    "상장주수",
    "자본금",
    "결산월",
    "공모가",
    "우선주",
    "공매도과열",
    "이상급등",
    "KRX300",
    "KOSPI",
    "매출액",
    "영업이익",
    "경상이익",
    "당기순이익",
    "ROE",
    "기준년월",
    "시가총액",
    "그룹사코드",
    "회사신용한도초과",
    "담보대출가능",
    "대주가능",
]

_KOSDAQ_FIELD_SPECS = [
    2,
    1,
    4,
    4,
    4,
    1,
    1,
    1,
    1,
    1,
    1,
    1,
    1,
    1,
    1,
    1,
    1,
    1,
    1,
    1,
    1,
    1,
    1,
    1,
    1,
    1,
    9,
    5,
    5,
    1,
    1,
    1,
    2,
    1,
    1,
    1,
    2,
    2,
    2,
    3,
    1,
    3,
    12,
    12,
    8,
    15,
    21,
    2,
    7,
    1,
    1,
    1,
    1,
    9,
    9,
    9,
    5,
    9,
    8,
    9,
    3,
    1,
    1,
    1,
]

_KOSDAQ_FIELD_NAMES = [
    "증권그룹구분코드",
    "시가총액규모",
    "지수업종대분류",
    "지수업종중분류",
    "지수업종소분류",
    "벤처기업",
    "저유동성",
    "KRX종목",
    "ETP",
    "KRX100",
    "KRX자동차",
    "KRX반도체",
    "KRX바이오",
    "KRX은행",
    "SPAC",
    "KRX에너지화학",
    "KRX철강",
    "단기과열",
    "KRX미디어통신",
    "KRX건설",
    "투자주의환기",
    "KRX증권",
    "KRX선박",
    "KRX섹터_보험",
    "KRX섹터_운송",
    "KOSDAQ150",
    "기준가",
    "매매수량단위",
    "시간외수량단위",
    "거래정지",
    "정리매매",
    "관리종목",
    "시장경고",
    "경고예고",
    "불성실공시",
    "우회상장",
    "락구분",
    "액면변경",
    "증자구분",
    "증거금비율",
    "신용가능",
    "신용기간",
    "전일거래량",
    "액면가",
    "상장일자",
    "상장주수",
    "자본금",
    "결산월",
    "공모가",
    "우선주",
    "공매도과열",
    "이상급등",
    "KRX300",
    "매출액",
    "영업이익",
    "경상이익",
    "단기순이익",
    "ROE",
    "기준년월",
    "전일기준시가총액",
    "그룹사코드",
    "회사신용한도초과",
    "담보대출가능",
    "대주가능",
]


def _download_master_zip(url: str) -> bytes:
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.content


def _extract_single_file_from_zip(payload: bytes) -> str:
    with ZipFile(BytesIO(payload)) as zip_file:
        names = zip_file.namelist()
        if len(names) != 1:
            raise ValueError(f"KIS 마스터 ZIP 내부 파일 수가 1이 아닙니다: {names}")
        with zip_file.open(names[0]) as handle:
            return handle.read().decode("cp949")


def _parse_master_text(
    raw_text: str,
    *,
    tail_width: int,
    part2_widths: Sequence[int],
    part2_names: Sequence[str],
    market: str,
) -> pd.DataFrame:
    part1_rows: list[dict[str, str]] = []
    part2_lines: list[str] = []

    for raw_line in raw_text.splitlines():
        line = raw_line.rstrip("\r\n")
        if not line:
            continue
        if len(line) <= tail_width:
            raise ValueError(f"{market} 마스터 레코드 길이가 예상보다 짧습니다: {len(line)}")

        prefix = line[:-tail_width]
        suffix = line[-tail_width:]
        part1_rows.append(
            {
                "단축코드": prefix[0:9].rstrip(),
                "표준코드": prefix[9:21].rstrip(),
                "한글종목명": prefix[21:].strip(),
            }
        )
        part2_lines.append(suffix)

    if not part1_rows:
        raise ValueError(f"{market} 마스터 파일이 비어 있습니다.")

    part1 = pd.DataFrame(part1_rows)
    part2 = pd.read_fwf(StringIO("\n".join(part2_lines)), widths=list(part2_widths), names=list(part2_names))
    result = pd.merge(part1, part2, how="outer", left_index=True, right_index=True)
    result["시장"] = market
    return result


def _normalize_listing_date(value: object) -> str:
    text = str(value or "").strip()
    if len(text) != 8 or not text.isdigit():
        return ""
    return f"{text[:4]}-{text[4:6]}-{text[6:8]}"


def _to_float_or_none(value: object) -> float | None:
    text = str(value or "").strip().replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _to_non_negative_float_or_none(value: object) -> float | None:
    parsed = _to_float_or_none(value)
    if parsed is None:
        return None
    if parsed < 0:
        return None
    return parsed


def _is_domestic_etf(row: pd.Series) -> bool:
    group_code = str(row.get("그룹코드") or row.get("증권그룹구분코드") or "").strip().upper()
    name = str(row.get("한글종목명") or "").strip().upper()
    return group_code == "EF" and "ETN" not in name


def load_kis_domestic_etf_master() -> pd.DataFrame:
    """KIS 종목정보파일에서 국내 상장 ETF 목록을 반환합니다."""

    try:
        kospi_zip = _download_master_zip(KIS_KOSPI_MASTER_URL)
        kosdaq_zip = _download_master_zip(KIS_KOSDAQ_MASTER_URL)
    except Exception as exc:
        logger.error("KIS 종목정보파일 다운로드 실패: %s", exc)
        raise RuntimeError(f"KIS 종목정보파일 다운로드 실패: {exc}") from exc

    try:
        kospi_raw = _extract_single_file_from_zip(kospi_zip)
        kosdaq_raw = _extract_single_file_from_zip(kosdaq_zip)
        kospi_df = _parse_master_text(
            kospi_raw,
            tail_width=_KOSPI_TAIL_WIDTH,
            part2_widths=_KOSPI_FIELD_SPECS,
            part2_names=_KOSPI_FIELD_NAMES,
            market="KOSPI",
        )
        kosdaq_df = _parse_master_text(
            kosdaq_raw,
            tail_width=_KOSDAQ_TAIL_WIDTH,
            part2_widths=_KOSDAQ_FIELD_SPECS,
            part2_names=_KOSDAQ_FIELD_NAMES,
            market="KOSDAQ",
        )
    except Exception as exc:
        logger.error("KIS 종목정보파일 파싱 실패: %s", exc)
        raise RuntimeError(f"KIS 종목정보파일 파싱 실패: {exc}") from exc

    combined = pd.concat([kospi_df, kosdaq_df], ignore_index=True)
    etf_df = combined[combined.apply(_is_domestic_etf, axis=1)].copy()
    if etf_df.empty:
        raise RuntimeError("KIS 종목정보파일에서 ETF를 찾지 못했습니다.")

    etf_df["상장일"] = etf_df["상장일자"].apply(_normalize_listing_date)
    etf_df["기준가"] = etf_df["기준가"].apply(_to_float_or_none)
    etf_df["전일거래량"] = etf_df["전일거래량"].apply(_to_non_negative_float_or_none)
    etf_df["시가총액"] = etf_df.get("시가총액", pd.Series(index=etf_df.index)).apply(_to_float_or_none)

    etf_df = etf_df.rename(
        columns={
            "단축코드": "티커",
            "표준코드": "표준코드",
            "한글종목명": "종목명",
        }
    )
    etf_df = etf_df[
        [
            "시장",
            "티커",
            "표준코드",
            "종목명",
            "상장일",
            "기준가",
            "전일거래량",
            "시가총액",
        ]
    ].sort_values(["시장", "종목명", "티커"], ascending=[True, True, True], ignore_index=True)
    return etf_df


def refresh_kis_domestic_etf_master_cache() -> int:
    """KIS 국내 ETF 마스터를 갱신하여 MongoDB 캐시에 저장합니다."""

    db = get_db_connection()
    if db is None:
        raise RuntimeError("MongoDB 연결 실패 — KIS ETF 마스터 캐시에 쓸 수 없습니다.")

    df = load_kis_domestic_etf_master()
    rows = df.to_dict(orient="records")
    now = datetime.now(timezone.utc)

    coll = db[_COLLECTION_NAME]
    coll.replace_one(
        {"master_id": _MASTER_ID},
        {
            "master_id": _MASTER_ID,
            "rows": rows,
            "count": len(rows),
            "updated_at": now,
        },
        upsert=True,
    )
    logger.info("KIS 국내 ETF 마스터 캐시 갱신 완료: %d건", len(rows))
    return len(rows)


def load_cached_kis_domestic_etf_master() -> tuple[pd.DataFrame, datetime | None]:
    """MongoDB에 저장된 KIS 국내 ETF 마스터 캐시를 반환합니다."""

    db = get_db_connection()
    if db is None:
        raise RuntimeError("MongoDB 연결 실패 — KIS ETF 마스터 캐시를 읽을 수 없습니다.")

    coll = db[_COLLECTION_NAME]
    doc = coll.find_one({"master_id": _MASTER_ID}, {"_id": 0})
    if not doc:
        raise RuntimeError("KIS ETF 마스터 캐시가 없습니다. stock_meta_cache_updater를 먼저 실행하세요.")

    rows = doc.get("rows")
    if not isinstance(rows, list) or not rows:
        raise RuntimeError("KIS ETF 마스터 캐시가 비어 있습니다. stock_meta_cache_updater를 다시 실행하세요.")

    updated_at = doc.get("updated_at")
    if isinstance(updated_at, pd.Timestamp):
        updated_at = updated_at.to_pydatetime()

    return pd.DataFrame(rows), updated_at if isinstance(updated_at, datetime) else None
