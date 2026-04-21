"""
리포트 및 로그 출력을 위한 포맷팅 유틸리티 함수 모음.
"""

import numbers
import re
from unicodedata import east_asian_width, normalize


def format_kr_money(value: float) -> str:
    """금액을 '억', '만' 단위를 포함한 한글 문자열로 포맷합니다."""
    if value is None or not isinstance(value, numbers.Real):
        return "-"
    val_int = int(round(value))
    if val_int == 0:
        return "0원"

    sign = "-" if val_int < 0 else ""
    val_abs = abs(val_int)

    eok = val_abs // 100000000
    man = (val_abs % 100000000) // 10000
    won = val_abs % 10000

    parts = []
    if eok > 0:
        parts.append(f"{eok}억")
    if man > 0:
        parts.append(f"{man}만")
    if won > 0:
        parts.append(f"{won}원")

    if not parts:
        # 억, 만 단위가 없는 작은 금액
        return f"{sign}{val_abs}원"

    formatted = " ".join(parts)
    if not formatted.endswith("원"):
        formatted += "원"
    return sign + formatted


def format_money(value: float, country: str) -> str:
    """금액을 통화/국가 코드에 맞는 형식으로 포맷합니다."""
    if value is None or not isinstance(value, numbers.Real):
        return "-"

    code = str(country or "").strip().lower()

    if code in ("kor", "kr", "krw"):
        return format_kr_money(value)

    sign = "-" if value < 0 else ""
    val_abs = abs(value)

    if code in ("us", "usa", "usd"):
        return f"{sign}${val_abs:,.2f}"
    elif code in ("aus", "au", "aud"):
        return f"{sign}A${val_abs:,.2f}"
    else:
        return f"{sign}{val_abs:,.2f}"


def render_table_eaw(headers: list[str], rows: list[list[str]], aligns: list[str]) -> list[str]:
    """
    동아시아 문자 너비를 고려하여 리스트 데이터를 ASCII 테이블 문자열로 렌더링합니다.
    """

    ansi_re = re.compile(r"\x1b\[[0-9;]*m")

    def _clean(s: str) -> str:
        if not isinstance(s, str):
            s = str(s)
        s = ansi_re.sub("", s)
        s = normalize("NFKC", s)
        return s

    def _disp_width_eaw(s: str) -> int:
        """동아시아 문자를 포함한 문자열의 실제 터미널 출력 너비를 계산합니다."""
        import unicodedata  # Function scope import to avoid changing module imports if not needed at top level

        s = _clean(s)
        w = 0
        for ch in s:
            # 박스 드로잉 문자
            if "\u2500" <= ch <= "\u257f":
                w += 2
                continue

            # Zero-width characters (Marks, Formatting like VS16)
            # Mn: Mark, Nonspacing
            # Me: Mark, Enclosing
            # Cf: Other, Format (includes VS16 \ufe0f)
            if unicodedata.category(ch) in ("Mn", "Me", "Cf"):
                continue

            eaw = east_asian_width(ch)
            # 'Ambiguous'(A) 문자를 Wide로 처리
            if eaw in ("W", "F", "A"):
                w += 2
            else:
                w += 1
        return w

    def _pad(s: str, width: int, align: str) -> str:
        """주어진 너비와 정렬에 맞게 문자열에 패딩을 추가합니다."""
        s_str = str(s)
        s_clean = _clean(s_str)
        dw = _disp_width_eaw(s_clean)
        if dw >= width:
            return s_str
        pad = width - dw
        if align == "right":
            return " " * pad + s_str
        elif align == "center":
            left = pad // 2
            right = pad - left
            return " " * left + s_str + " " * right
        else:  # 왼쪽 정렬
            return s_str + " " * pad

    widths = [max(_disp_width_eaw(v) for v in [headers[j]] + [r[j] for r in rows]) for j in range(len(headers))]

    def _hline():
        return "+" + "+".join("-" * (w + 2) for w in widths) + "+"

    out = [_hline()]
    header_cells = [
        _pad(headers[j], widths[j], "center" if aligns[j] == "center" else "left") for j in range(len(headers))
    ]
    out.append("| " + " | ".join(header_cells) + " |")
    out.append(_hline())
    for r in rows:
        cells = [_pad(r[j], widths[j], aligns[j]) for j in range(len(headers))]
        out.append("| " + " | ".join(cells) + " |")
    out.append(_hline())
    return out
