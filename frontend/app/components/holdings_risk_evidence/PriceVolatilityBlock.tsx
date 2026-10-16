"use client";
// POC5-16 — 「확인 근거」 종목 상세의 접힌 구역 '가격 흔들림(변동성) 보기'(설계 V1 §5 · 사용자 확정 목업).
// 기본 접힘 · 지금 해당하는 짧은 사유는 접혀 있어도 보임 · 펼치면 최근 · 직전 20구간 값을 같은 폭으로 ·
// 비교 문구 · 기간은 보조 줄 · ? 하나(15 HelpPopover). 색은 중립(수익 색 · 경보 색 없음).
// 새 조회 없음 — 부모가 받은 근거 응답의 선택 필드만.
import { useState } from "react";
import type { PriceVolatilityEvidence } from "@/lib/api";
import HelpPopover from "./HelpPopover";
import {
  COMPARISON_TEXT,
  cellValue,
  hidesValues,
  periodLine,
  volatilityHelp,
  volatilityNote,
} from "./priceVolatility";

export default function PriceVolatilityBlock({
  ev,
  flowDate,
}: {
  ev: PriceVolatilityEvidence | null | undefined;
  flowDate: string | null;
}) {
  const [open, setOpen] = useState(false);
  if (!ev) return null;
  const note = volatilityNote(ev, flowDate);
  return (
    <div className="pvb" data-testid="price-volatility">
      <div className="pvb-head">
        <button
          type="button"
          className="btn-md tc-fold-btn pvb-toggle"
          aria-expanded={open}
          onClick={() => setOpen((v) => !v)}
        >
          {open ? "가격 흔들림(변동성) 접기" : "가격 흔들림(변동성) 보기"}
        </button>
        <HelpPopover label="가격 흔들림" paragraphs={volatilityHelp(ev)} />
      </div>
      {note ? (
        <div className="pvb-note" data-testid="price-volatility-note">
          {note}
        </div>
      ) : null}
      {open && !hidesValues(ev) ? (
        <div className="pvb-body" data-testid="price-volatility-body">
          <div className="wb-detail-grid pvb-grid">
            <div className="wb-detail-cell">
              <span className="svb-k">최근 20구간</span>
              <span className="svb-v">{cellValue(ev.recent, ev.recent_reason)}</span>
            </div>
            <div className="wb-detail-cell">
              <span className="svb-k">직전 20구간</span>
              <span className="svb-v">{cellValue(ev.previous, ev.previous_reason)}</span>
            </div>
          </div>
          {ev.comparison ? (
            <div className="pvb-cmp" data-testid="price-volatility-cmp">
              {COMPARISON_TEXT[ev.comparison]}
            </div>
          ) : null}
          <div className="svb-src">{periodLine(ev)}</div>
        </div>
      ) : null}
    </div>
  );
}
