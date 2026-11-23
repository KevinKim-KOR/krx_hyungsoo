"""POC7-02 합성 점검 입력(PLAN §2-2) — 실제 값 · 이름이 없는 같은 형식의 복사문 · AI 답 두 개.

같은 `.bat` 안에서 본 요약보다 먼저 돈다. 길이는 본 사례 입력 이상(최소 2.2만 자) — 합성 점검이 문맥 · 메모리에
들어가면 본 사례도 들어간다. 같은 목표 길이면 같은 글(무작위 없음). 이름은 모두 '합성 ETF ○' · 코드 'T0000n'.
"""

from __future__ import annotations

from typing import Any

MIN_CHARS = 22000
SELECTED = {"ticker": "T00001", "name": "합성 ETF 가", "rank": 1}

_HEAD = """[최신 공개 자료 확인] (합성 점검 글 — 실제 시장 값이 아님) 판단에 쓰는 항목의 최신 공개 자료를 확인해 주세요.

[주간 ETF 점검 · 1개월 상위 30개(선정 순서) · 합성 10/01 → 10/31]

[시장 — 공통 시장 근거 · 자료마다 기준일]
[근거 1] [시장 판정 · 아침] 미확인 — 합성 기준 ETF 10/31 마감 가격 미확인
[근거 2] [시장 판정 · 당일] 합성 기준 ETF 하락장 · 12거래일째 · 판정 가격 10/30 · 20거래일 -4.10%
[근거 3] [코스피 공식 종가] 3,100.00 · 10/29 · 10/28 대비 -12.00pt(-0.39%) · 기대 거래일 10/31 종가 확인 불가
[근거 4] [외국인 20거래일] 직전 순매도 9.0조원(일평균 4,500억원) → 최근 순매도 6.0조원(일평균 3,000억원)
[자료 상태] 합성 · 코스피 10/29까지(기대 10/31 · 2거래일 늦음) · 외국인 수급 10/29까지(기대 10/31 · 2거래일 늦음)

[주간 목록 — 조건 · 같은 기간 기준]
[근거 5] [목록 조건] 1개월 상위 30개 · 합성 10/01 → 10/31 · 인버스 · 레버리지 제외
[근거 6] [같은 기간 기준 ETF] 1개월 -3.20%(10/01 → 10/31)
"""

_SELECTED = """
[고른 ETF — 어떤 상품인가 · 실제로 올랐나]
[근거 {a}] 고른 ETF 합성 ETF 가(T00001) · 1위 · 합성 기초지수 · 총보수 0.10%
[근거 {b}] [실제로 올랐나] 1개월 -1.10%(10/01 → 10/31) · 기준 ETF 보다 +2.10%p(덜 내림) · 3개월 기간 다름
[근거 {c}] [보유 겹침] 구성 10종목 중 6종목 확인(확인 범위 비중 58%) · 금액 · 보유 종목 이름 없음
"""

_ANSWER = """최신 확인: {state}
- 항목: 코스피 종가 · 값: {value} · 기준일: 10/31 · 출처: {source} · 확인 시각: {at} · 달라지는 해석: 없음
대상 ETF: T00001
[ETF T00001]
상태: {etf_state}
인용 근거: 2, 3, {b}
이유: {reason}
다음 확인: {next}
"""


def _flow(i: int) -> str:
    return (
        f"[근거 {i}] [흐름 {i - 6}] 합성 ETF {i:03d}(T{i:05d}) · 합성 기초지수 {i % 7} 계열 · "
        f"1개월 +{(i * 37) % 900 / 100:.2f}% · 3개월 +{(i * 53) % 1500 / 100:.2f}% · 거래대금 합성 {i * 11}억원"
    )


def build(target_chars: int) -> dict[str, Any]:
    """{meta, copy_text, answers} — 복사문 + 두 답의 길이 합이 max(target, MIN_CHARS) 이상."""
    target = max(int(target_chars), MIN_CHARS)
    gpt = _ANSWER.format(
        state="새 값 있음",
        value="3,090.00",
        source="https://example.invalid/합성",
        at="10/31 18:00",
        etf_state="추가 확인",
        b="{b}",
        reason="외국인 순매도가 이어져 방향 확인이 더 필요하다(합성).",
        next="10/31 이후 외국인 수급",
    )
    claude = _ANSWER.format(
        state="확인 불가",
        value="",
        source="",
        at="",
        etf_state="근거 확인",
        b="{b}",
        reason="하루 평균 매도 규모가 줄었고 기준보다 덜 내렸다(합성).",
        next="합성 기초지수 구성 변화",
    )
    flows: list[str] = []
    i = 7
    while True:
        a, b, c = i, i + 1, i + 2
        text = _HEAD + "\n[먼저 볼 ETF 흐름]\n" + "\n".join(flows)
        text += _SELECTED.format(a=a, b=b, c=c)
        answers = [
            {"author": "GPT", "text": gpt.replace("{b}", str(b))},
            {"author": "Claude", "text": claude.replace("{b}", str(b))},
        ]
        if len(text) + sum(len(x["text"]) for x in answers) >= target:
            break
        flows.append(_flow(i))
        i += 1
    meta = {
        "end_date": "합성 10/31",
        "condition": "1개월 상위 30개 · 합성",
        "selected": dict(SELECTED),
        "answer_authors": ["GPT", "Claude"],
        "synthetic": True,
    }
    return {"meta": meta, "copy_text": text, "answers": answers}
