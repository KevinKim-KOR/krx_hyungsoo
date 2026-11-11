"use client";

// POC6-28 — [이 목록 전체를 AI 질문용으로 복사](판정 §3 · PLAN §3-3).
// PC 클립보드 복사로 끝난다(저장 · 전송 없음). 복사가 막히면 글을 보여 주고 직접 선택하게 한다(오늘 점검과 같은 방식).

import { useState } from "react";
import type { CompareSummaryOk } from "@/lib/api/etfCompare";
import { aiCopyText } from "@/lib/etfCompare";

export default function CopyListButton({ s, side }: { s: CompareSummaryOk; side: "top" | "bottom" }) {
  const [msg, setMsg] = useState<{ text: string; fallback: string | null } | null>(null);
  const doCopy = () => {
    const text = aiCopyText(s, side);
    const fail = () => setMsg({ text: "복사하지 못했습니다 — 아래 글을 직접 선택해 복사하세요.", fallback: text });
    try {
      const p = navigator.clipboard?.writeText(text);
      if (!p) {
        fail();
        return;
      }
      p.then(() => setMsg({ text: "목록 전체를 AI 질문용으로 복사했습니다.", fallback: null })).catch(fail);
    } catch {
      fail();
    }
  };
  const rows = side === "top" ? s.top : s.bottom;
  const noCons = rows.filter((r) => !r.constituents).length;
  return (
    <div className="ec-copy" data-testid={`ec-copy-${side}`}>
      <button type="button" className="wb-btn btn-md" onClick={doCopy}>
        이 목록 전체를 AI 질문용으로 복사
      </button>
      <span className="ec-small">
        {side === "top" ? "상위" : "하위"} {rows.length}개 · 기초지수 · 지역 · 자산 · 수익률과 날짜 · 확인된 구성종목과
        비중 · 구성 자료 없음 {noCons}개 · 질문 = 반복된 근거 / 이름에서 유추한 가설(추정) / 부족한 자료 · AI 답은
        추정입니다
      </span>
      {msg && (
        <div className="ec-small" role="status">
          {msg.text}
          {msg.fallback && <textarea className="ec-fallback" readOnly value={msg.fallback} rows={6} />}
        </div>
      )}
    </div>
  );
}
