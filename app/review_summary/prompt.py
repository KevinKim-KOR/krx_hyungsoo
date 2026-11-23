"""POC7-02 지시문 · 모델 · 설정(PLAN §2-2 · §3-2 · 판정 Q3 · §3) — 판 번호와 해시로 고정.

지시문은 판(`PROMPT_VERSION`)을 바꾸지 않고 고치지 않는다(본 실행 뒤 바꾸지 않음 · PLAN §2-2).
입력 = 맨 앞 표지 · 복사문 · AI 답(작성자) · 맨 뒤 표지. 표지는 묶음마다 무작위(같은 앞머리 캐시 재사용도 막는다).
"""

from __future__ import annotations

import hashlib
from typing import Any, Mapping, Sequence

from app.review_summary.judge import LABELS, MARK_LABEL

PROMPT_VERSION = "poc7-02-prompt-v1"
MODEL = "qwen3.5:9b-q4_K_M"  # 판정 Q3 — 모델 교체 · 추가 다운로드는 별도 결정
AUTHORS = ("GPT", "Claude", "Gemini")
# 모델 카드 생각 모드 권장값 + seed 고정(판정 Q3 · 합성 시험의 시작 설정)
OPTIONS: dict[str, Any] = {
    "temperature": 1.0,
    "top_p": 0.95,
    "top_k": 20,
    "min_p": 0.0,
    "presence_penalty": 1.5,
    "repeat_penalty": 1.0,
    "seed": 20261123,
    "num_ctx": 49152,
    "num_predict": 24576,
}
MAX_CTX = 262144  # qwen3.5:9b-q4_K_M 문맥 256K(PLAN §2-2 모델 표)
LENGTH_KEYS = ("num_ctx", "num_predict")  # 합성 시험으로 조정할 수 있는 칸(판정 Q3)
THINK = True
NO_ANSWER_LINE = "[AI 답 없음 — AI 의견 칸은 쓰지 않는다]"

SYSTEM = """너는 한국어로 「주간 ETF 검토 한 장」을 쓰는 도우미다. 아래 규칙을 모두 지킨다.

[읽는 범위]
1. 사용자가 준 원문(「주간 ETF 점검」 복사문과, 있으면 AI 답)만 읽는다. 인터넷을 볼 수 없다. 원문에 없는 값 · 날짜 · 사실을 만들지 않는다.
2. 복사문 첫머리의 '최신 공개 자료를 확인해 달라'는 요청은 웹 AI 에게 한 요청이다. 너는 확인할 수 없다. AI 답에 적힌 확인 보고만 정리한다.

[칸 — 이 순서로, 칸마다 한두 문장]
3. 시장: 시장 판정(아침 · 당일) · 코스피 · 외국인 수급의 기준일을 각자 쓴다. [자료 상태] 의 늦은 자료와 확인 불가 가운데 이번 검토에 영향을 주는 것을 쓴다.
4. 선택한 ETF: '고른 ETF' 근거로, 원문 기간에 실제로 올랐는지 · 시장(KODEX 200)보다 덜 내렸는지를 구별해 쓴다.
   - %(변화율)와 %p(차이)를 구별한다. %가 음수이고 %p가 양수면 '시장보다 덜 내렸다'로 쓴다.
   - 보유 겹침에는 확인 범위를 붙인다.
5. AI 의견: 고른 ETF 와 시장에 대한 의견만 쓴다(AI 답은 다른 ETF 도 다룬다).
   - 답이 둘 이상이면 판단에 영향을 주는 공통점과 차이를 작성자와 함께 쓴다. 상태 선택이 다르면 상태와 작성자를 적는다.
   - 강조점이 다른 것(예: 한쪽은 방향, 한쪽은 속도)은 이견이 아니다. 서로 상충하는 주장만 이견으로 쓴다. 한쪽만 다룬 항목은 '(GPT 만)'처럼 적는다.
   - 답이 하나면 그 의견만 쓴다. AI 답이 없으면 이 칸을 쓰지 않는다.
6. 최신 자료와 다음 확인:
   - AI 답에 값 · 기준일 · 출처 · 확인 시각이 모두 있는 확인만 그 AI 의 보고로 쓴다.
     확인 주체 · 값 · 기준일 · 출처 · 확인 시각(답에 적힌 그대로)을 함께 쓰고, 그 값은 저장값과 구별한다.
   - 하나라도 빠졌거나 링크만 있으면 '최신 공개 자료 확인 불가'와 저장 자료의 기준일을 쓴다. 확인 시각은 답에 적힌 값만 쓴다.
   - 더 확인할 것은 가장 중요한 한 가지만 쓴다.

[인용과 표현]
7. 수치 · 판단마다 〔근거 n〕처럼 복사문의 근거 번호를 붙인다. 번호가 없는 줄은 원문 항목명과 기준일을 쓴다. AI 답은 〔GPT 이유〕처럼 작성자와 칸을 쓴다.
8. 순매도 규모가 줄어든 것을 순매수로 쓰지 않는다. 오름 · 내림 · 덜 내림을 바꿔 쓰지 않는다.
9. 매수 · 매도 · 보유 같은 매매 결론, 추천, 'AI 들이 동의했다' 같은 합의 단정을 쓰지 않는다.

[출력 형식 — 아래 머리 그대로, 다른 글 없이]
시장: …
선택한 ETF: …
AI 의견: …
최신 자료와 다음 확인: …
확인 표지: (입력 맨 앞 표지) · (입력 맨 뒤 표지)
(AI 답이 없으면 'AI 의견:' 줄을 쓰지 않는다.)"""


def prompt_sha() -> str:
    """지시문 · 판 · 모델 · 설정 · 칸 이름의 해시(묶음 · 결과에 기록 · 바뀌면 다른 판)."""
    blob = "\n".join(
        [
            PROMPT_VERSION,
            MODEL,
            SYSTEM,
            repr(sorted(OPTIONS.items())),
            repr(LABELS),
            MARK_LABEL,
            NO_ANSWER_LINE,
        ]
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def options(overrides: Mapping[str, int] | None = None) -> dict[str, Any]:
    """설정 한 벌 — 길이 칸(`num_ctx` · `num_predict`)만 바꿀 수 있다(판정 Q3)."""
    out = dict(OPTIONS)
    for k, v in (overrides or {}).items():
        if k not in LENGTH_KEYS:
            raise ValueError(f"바꿀 수 없는 설정: {k}")
        if not isinstance(v, int) or isinstance(v, bool) or v <= 0:
            raise ValueError(f"길이 설정은 양의 정수: {k}={v!r}")
        # 모델 문맥 256K(PLAN §2-2 모델 표) — 넘으면 적재 실패 · 되돌릴 수 없는 길이
        if v > MAX_CTX:
            raise ValueError(f"길이 설정은 모델 문맥 {MAX_CTX} 이하: {k}={v!r}")
        out[k] = v
    if out["num_predict"] >= out["num_ctx"]:
        raise ValueError("num_predict 는 num_ctx 보다 작아야 함")
    return out


def build_messages(
    *,
    copy_text: str,
    archived_at: str,
    answers: Sequence[Mapping[str, str]],
    start_mark: str,
    end_mark: str,
) -> list[dict[str, str]]:
    """대화 두 개(system · user). 표지는 system 맨 앞과 user 맨 앞 · 맨 뒤(잘림 · 캐시 확인용)."""
    parts = [
        f"[입력 맨 앞 표지: {start_mark}]",
        f"[원문 1 · 「주간 ETF 점검」 복사문 · 보관 {archived_at}]",
        copy_text,
    ]
    if answers:
        for i, a in enumerate(answers, start=2):
            parts += ["", f"[원문 {i} · {a['author']} 답]", a["text"]]
    else:
        parts += ["", NO_ANSWER_LINE]
    parts += ["", f"[입력 맨 뒤 표지: {end_mark}]"]
    return [
        {"role": "system", "content": f"[실행 표지 {start_mark}]\n{SYSTEM}"},
        {"role": "user", "content": "\n".join(parts)},
    ]


def input_chars(messages: Sequence[Mapping[str, str]]) -> int:
    return sum(len(m["content"]) for m in messages)
