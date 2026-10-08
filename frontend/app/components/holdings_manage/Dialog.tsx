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
}

export default function Dialog({ title, subtitle, onClose, wide, children, footer }: Props) {
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    const first = box.current?.querySelector<HTMLElement>(
      "input:not([readonly]), select, textarea, button:not(.hmx-x)",
    );
    first?.focus();
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);
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
