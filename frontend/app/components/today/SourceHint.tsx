"use client";

// POC6-29 보완 2차(형수님 결정 2026-11-12 · S 판정 §1) — 상태 옆 작은 [?]: 출처 · 받은 시각 · 비교 시작 · 끝일.
// 표 칸에는 두지 않는다(공간을 쓰지 않음). 누르면 바로 아래에 펼쳐진다(화면 안 상태 · 저장 없음).
// 설계자 V3 D1 — 판정 표 제목 옆 [?](점수 산식)도 같은 부품: 이름(label)과 align="left"(열면 떠 있는 상자 대신 제목 아래로
// 펼침 · 긴 글이 좁은 화면에서 옆으로 넘치지 않게).
export default function SourceHint({
  text,
  testId,
  label = "출처 · 받은 시각 보기",
  align = "right",
}: {
  text: string | null;
  testId?: string;
  label?: string;
  align?: "left" | "right";
}) {
  if (!text) return null;
  return (
    <details className={align === "left" ? "tc-src tc-src-left" : "tc-src"} data-testid={testId}>
      <summary aria-label={label}>?</summary>
      <span className="tc-src-pop">{text}</span>
    </details>
  );
}
