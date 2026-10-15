"use client";
// POC5-15 — 요약마다 하나인 '?' 도움말(PLAN 판정 §5). 클릭 · 키보드(버튼)로 열고, 다시 누름 ·
// Escape · 바깥 클릭 · 초점이 창 밖으로 나감(Tab)으로 닫는다. 마우스를 올리기만 해서는 열리지 않는다.
// 받은 자료로 만든 문장만 보인다(조회 · 저장 · 발송 없음). 저장소의 기존 ⓘ 표시는 title 툴팁이라
// 클릭 창을 새로 둔다.
import { useCallback, useEffect, useId, useLayoutEffect, useRef, useState } from "react";

const EDGE = 8; // 보이는 화면 가장자리 여백(px)

export default function HelpPopover({
  label,
  paragraphs,
}: {
  label: string;
  paragraphs: string[];
}) {
  const [open, setOpen] = useState(false);
  const [shift, setShift] = useState(0);
  const shiftRef = useRef(0);
  const boxRef = useRef<HTMLSpanElement>(null);
  const btnRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLSpanElement>(null);
  const panelId = useId();
  const textKey = paragraphs.join("\n");

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setOpen(false);
        btnRef.current?.focus();
      }
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  // 보이는 폭(스크롤바 제외 · clientWidth) 안으로 좌우를 옮긴다(판정 §5 '화면 밖으로 잘리지 않게').
  // 지금 적용된 이동량을 빼고 원래 자리에서 다시 잰다.
  const measure = useCallback(() => {
    const el = panelRef.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    const left = r.left - shiftRef.current;
    const right = r.right - shiftRef.current;
    const vw = document.documentElement.clientWidth || window.innerWidth;
    let next = 0;
    if (right > vw - EDGE) next = vw - EDGE - right;
    if (left + next < EDGE) next = EDGE - left;
    if (next !== shiftRef.current) {
      shiftRef.current = next;
      setShift(next);
    }
  }, []);

  // 열 때 · 문장이 바뀔 때 다시 잰다.
  useLayoutEffect(() => {
    if (!open) {
      shiftRef.current = 0;
      setShift(0);
      return;
    }
    measure();
  }, [open, textKey, measure]);

  // 열린 동안 창 크기가 바뀌면 다시 잰다.
  useEffect(() => {
    if (!open) return;
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, [open, measure]);

  return (
    <span
      className="help-pop"
      ref={boxRef}
      onBlur={(e) => {
        // Tab 등으로 초점이 창 밖의 다른 요소로 옮겨 가면 닫는다(열린 창이 다음 버튼을 가리지 않게).
        // 창 안 글자를 누른 경우(옮겨 간 초점 없음)는 바깥 클릭 처리에 맡긴다.
        const to = e.relatedTarget as Node | null;
        if (open && to && !boxRef.current?.contains(to)) setOpen(false);
      }}
    >
      <button
        ref={btnRef}
        type="button"
        className="help-pop-btn"
        aria-expanded={open}
        aria-controls={open ? panelId : undefined}
        aria-label={`${label} 도움말`}
        onClick={() => setOpen((v) => !v)}
      >
        {/* POC5-UI-01 아이콘 버튼 = 40 × 40 누르는 자리 · 보이는 표시는 작은 원 */}
        <span className="help-pop-dot" aria-hidden="true">
          ?
        </span>
      </button>
      {open ? (
        <span
          ref={panelRef}
          id={panelId}
          className="help-pop-panel"
          role="dialog"
          aria-label={`${label} 도움말`}
          style={shift ? { transform: `translateX(${shift}px)` } : undefined}
        >
          {paragraphs.map((p) => (
            <span key={p} className="help-pop-p">
              {p}
            </span>
          ))}
        </span>
      ) : null}
    </span>
  );
}
