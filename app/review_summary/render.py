"""POC7-02 한 장 HTML(PLAN §3-1) — 표준 라이브러리만 · 실행 묶음에 `review_render.py` 사본으로 들어간다.

같은 입력이면 같은 바이트(시각 · 무작위 없음 · 받은 값만). Windows PC 가 만들고, 맥북 merge 가 '그 묶음에 들어간'
이 코드로 결과에서 다시 만들어 해시를 비교한다(형수님이 연 한 장 = 최초 출력 · AC1).

- 첫 줄(기준일 · 선택한 ETF · 순위)과 끝 줄은 보관 기록에서 가져온다. 네 칸(답이 없으면 세 칸)만 모델 출력이다.
- 칸은 모델 글 그대로(머리 글자만 뗌 · 줄바꿈 유지)이고, 확인 표지 줄도 끝에 그대로 보인다.
- 칸 순서 · 이름이 다르거나, 첫 칸 앞 · 확인 표지 뒤에 글이 있으면 고치지 않고 원문 전체를 그대로 보인다.
- AI 답이 없으면 AI 의견 칸을 그리지 않는다(판정 Q1 · 미측정 안내는 끝 줄).
"""

from __future__ import annotations

import html
from typing import Any, Mapping

try:  # 실행 묶음 안(같은 폴더의 사본)
    import review_judge as judge  # type: ignore[import-not-found]
except ImportError:  # 저장소 안
    from app.review_summary import judge

NO_ANSWER_NOTE = (
    "AI 답 없음 — AI 의견 칸 생략 · 긴 AI 답 대조의 효용은 이번에 재지 않음(미측정)"
)
CSS = """
:root{--bg:#f7f5f0;--fg:#1f2328;--muted:#5b616b;--line:#d9d4c7;--card:#ffffff;--accent:#7a4b12}
@media (prefers-color-scheme: dark){:root{--bg:#1b1c1f;--fg:#e8e6e1;--muted:#a7abb3;
--line:#3a3c42;--card:#24262a;--accent:#e0a45a}}
body{background:var(--bg);color:var(--fg);margin:0;padding:24px 16px;
font:17px/1.7 -apple-system,"Apple SD Gothic Neo","Malgun Gothic",sans-serif}
main{max-width:760px;margin:0 auto}
h1{font-size:19px;line-height:1.5;margin:0 0 16px;color:var(--accent)}
section{background:var(--card);border:1px solid var(--line);border-radius:10px;
padding:14px 16px;margin:0 0 12px}
h2{font-size:15px;margin:0 0 6px;color:var(--muted);letter-spacing:.02em}
p{margin:0;white-space:pre-wrap}
pre{white-space:pre-wrap;word-break:break-word;margin:0;
font:15px/1.6 ui-monospace,Menlo,Consolas,monospace}
footer{color:var(--muted);font-size:13px;margin-top:16px;white-space:pre-wrap}
""".strip()


def _esc(v: Any) -> str:
    return html.escape("" if v is None else str(v), quote=True)


def header_line(meta: Mapping[str, Any]) -> str:
    sel = meta.get("selected") or {}
    return (
        f"주간 ETF 검토 한 장 · 검토 기준일 {meta.get('end_date')} · {meta.get('condition')} · "
        f"선택한 ETF: {sel.get('name')}({sel.get('ticker')}) · {sel.get('rank')}위"
    )


def footer_lines(
    meta: Mapping[str, Any], main: Mapping[str, Any], mark: Any
) -> list[str]:
    digest = str(main.get("model_digest") or "")[:12] or "확인 못 함"
    out = []
    if mark is not None:
        out.append(f"{judge.MARK_LABEL}: {mark}")
    if not meta.get("answer_authors"):
        out.append(NO_ANSWER_NOTE)
    out.append(
        f"로컬 AI({meta.get('model')} · digest {digest}) · 위 원문만 읽고 쓴 요약 · 투자 권유 아님 · "
        f"생성 {main.get('ended_at')} · 결과 구분 {main.get('status')}"
    )
    return out


def render_html(meta: Mapping[str, Any], main: Mapping[str, Any]) -> str:
    """meta = 묶음의 main.meta(보관 기록) · main = 실행기의 본 요약 기록(content · status · 시각 · digest)."""
    content = main.get("content") or ""
    with_ai = bool(meta.get("answer_authors"))
    sections, mark, why = judge.parse_sections(content, with_ai)
    body: list[str] = [f"<h1>{_esc(header_line(meta))}</h1>"]
    if sections is not None:
        for k in judge.expected_heads(with_ai):
            body.append(
                f"<section><h2>{_esc(k)}</h2><p>{_esc(sections[k])}</p></section>"
            )
    else:
        if not content.strip():
            title = "출력이 없음"
        else:
            title = f"형식이 예상과 다름({why}) — 원문 그대로 · 고치지 않음"
        body.append(
            f"<section><h2>{_esc(title)}</h2><pre>{_esc(content)}</pre></section>"
        )
    foot = "\n".join(footer_lines(meta, main, mark))
    body.append(f"<footer>{_esc(foot)}</footer>")
    return (
        '<!doctype html>\n<html lang="ko"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>주간 ETF 검토 한 장</title><style>{CSS}</style></head>"
        f"<body><main>{''.join(body)}</main></body></html>\n"
    )
