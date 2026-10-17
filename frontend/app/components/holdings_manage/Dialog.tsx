"use client";

// POC5-05 개정 2 — 「종목 관리」 창(매매 입력 · 새 보유 · History) 공용 틀.
// 라이브러리 없이 role="dialog" · aria-modal · Esc 닫기 · 바깥 클릭 닫기 · 첫 입력 칸 포커스.

import { useEffect, useRef } from "react";

interface Props {
  title: string;
  subtitle?: string | null;
  onClose: () => void;
  wide?: boolean;
  children: React.ReactNode;
  footer?: React.ReactNode;
  // 처음 초점을 둘 요소(선택 · 없으면 첫 입력 칸 · 버튼 — 기존 동작 그대로).
  focusSelector?: string;
}

export default function Dialog({
  title,
  subtitle,
  onClose,
  wide,
  children,
  footer,
  focusSelector,
}: Props) {
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      // 창 안의 ? 도움말이 열려 있으면 Esc 는 그 도움말만 닫는다(도움말이 스스로 닫음 · POC5-19).
      if (e.key === "Escape" && !box.current?.querySelector(".help-pop-panel")) onClose();
    };
    document.addEventListener("keydown", onKey);
    // 처음 초점: focusSelector 가 있으면 그 요소, 없거나 맞는 요소가 없으면 첫 입력 칸 · 버튼(기존 동작),
    // 그것도 없으면 닫기(×) — 초점이 창 뒤에 남지 않게.
    const first =
      (focusSelector ? box.current?.querySelector<HTMLElement>(focusSelector) : null) ??
      box.current?.querySelector<HTMLElement>(
        "input:not([readonly]), select, textarea, button:not(.hmx-x)",
      ) ??
      box.current?.querySelector<HTMLElement>(".hmx-x");
    first?.focus();
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose, focusSelector]);
  return (
    <div
      className="hmx-scrim"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        ref={box}
        className={wide ? "hmx-dialog hmx-dialog-wide" : "hmx-dialog"}
        role="dialog"
        aria-modal="true"
        aria-label={title}
      >
        <div className="hmx-dialog-head">
          <div>
            <h3>{title}</h3>
            {subtitle ? <div className="muted hmx-small">{subtitle}</div> : null}
          </div>
          <button type="button" className="hmx-x" aria-label="닫기" onClick={onClose}>
            ×
          </button>
        </div>
        {children}
        {footer ? <div className="hmx-dialog-foot">{footer}</div> : null}
      </div>
    </div>
  );
}
