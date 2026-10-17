"use client";
// POC5-19 개정(2026-10-17 §2) — 종목 상세 머리의 [세부 흐름 보기] 하나 → 공통 세부 흐름 창(기존 대화창 틀 재사용 ·
// Esc · 바깥 클릭 · × 로 닫음 · 닫으면 이 버튼으로 초점이 돌아옴). 아래쪽 펼침 영역은 두지 않는다.
// 종목을 바꾸면 창 · 고른 날짜를 이어받지 않는다(부모 key).
import { useCallback, useRef, useState } from "react";
import type { HoldingsMarketEvidenceItem, PriceBasis } from "@/lib/api";
import Dialog from "../holdings_manage/Dialog";
import DetailFlowsBody from "./DetailFlowsBody";
import type { RiskEvidenceRow } from "./helpers";

export default function DetailFlows({
  row,
  item,
  basis,
}: {
  row: RiskEvidenceRow;
  item: HoldingsMarketEvidenceItem | null;
  basis: PriceBasis | null;
}) {
  const [open, setOpen] = useState(false);
  const btn = useRef<HTMLButtonElement>(null);
  const close = useCallback(() => {
    setOpen(false);
    btn.current?.focus();
  }, []);
  return (
    <>
      <button
        ref={btn}
        type="button"
        className="btn-md tc-fold-btn"
        aria-haspopup="dialog"
        onClick={() => setOpen(true)}
        data-testid="detail-flows"
      >
        세부 흐름 보기
      </button>
      {open ? (
        <Dialog
          title={`${row.name ?? row.ticker} 세부 흐름`}
          subtitle={`${row.ticker} · PC 저장 종가 · 저장 거래량`}
          onClose={close}
          wide
          focusSelector=".rc-plot"
        >
          <DetailFlowsBody row={row} item={item} basis={basis} />
        </Dialog>
      ) : null}
    </>
  );
}
