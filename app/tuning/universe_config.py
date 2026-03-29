"""유니버스 모드 설정 (P205-STEP4).

fixed_current: 기존 고정 유니버스 (SSOT 원본)
expanded_candidates: 확장 후보군 (기존 포함 + 추가 ETF)
"""

from typing import Dict, List, Any

# 기존 고정 유니버스 (현재 SSOT 기준)
FIXED_CURRENT_UNIVERSE = [
    "069500",  # KODEX 200
    "229200",  # KODEX 코스닥150
    "360750",  # TIGER MSCI Korea TR
    "379810",  # KODEX 은행
    "314250",  # TIGER 경기방어
    "381170",  # KODEX 자동차
    "458730",  # KODEX 퀄리티밸류
    "441680",  # KB STAR 배당성장
    "148070",  # TIGER 글로벌채권
    "305080",  # KODEX 안심배당플러스
    "411060",  # TIGER 이머징채권
    "138230",  # KRX 채권종합TR
    "130730",  # KODEX 단기채권
]

# 확장 후보군: 기존 + 추가 KRX ETF (유동성/대표성 중심)
EXPANDED_CANDIDATES_ADDITIONS = [
    "102110",  # TIGER 200
    "252670",  # KODEX 200선물인버스2X
    "114800",  # KODEX 인버스
    "226490",  # KODEX 코스피100
    "091160",  # KODEX 반도체
    "091170",  # KODEX 은행
    "143850",  # TIGER 미국S&P500
    "195930",  # TIGER 유로스톡스50
    "261240",  # TIGER 미국채10년
    "182490",  # TIGER 단기통안채
    "192090",  # TIGER 차이나CSI300
    "371460",  # TIGER 차이나전기차SOLACTIVE
    "364690",  # KODEX 혁신기술테마
    "277630",  # TIGER 우량가치
    "277640",  # TIGER 미국나스닥100
    "133690",  # TIGER 미국채10년선물
    "117460",  # KODEX 에너지화학
    "091180",  # KODEX 자동차
    "266360",  # KODEX 2차전지산업
    "305720",  # KODEX 2차전지테마
]

EXPANDED_CANDIDATES_UNIVERSE = sorted(
    list(set(FIXED_CURRENT_UNIVERSE + EXPANDED_CANDIDATES_ADDITIONS))
)

VALID_UNIVERSE_MODES = ["fixed_current", "expanded_candidates"]
DEFAULT_UNIVERSE_MODE = "fixed_current"


def get_universe_list(mode: str) -> List[str]:
    """유니버스 모드에 따른 종목 리스트 반환."""
    if mode == "expanded_candidates":
        return list(EXPANDED_CANDIDATES_UNIVERSE)
    return list(FIXED_CURRENT_UNIVERSE)


def get_universe_meta(mode: str) -> Dict[str, Any]:
    """유니버스 메타데이터 반환."""
    universe = get_universe_list(mode)
    return {
        "universe_mode": mode,
        "universe_size": len(universe),
        "universe_list": universe,
        "universe_source": "app.tuning.universe_config",
    }
