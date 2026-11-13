"use client";

// POC6-29(PLAN §2-4 · 판정 Q1 · Q11 · 2026-11-12) — 「ETF보유 및 후보 선정 › 섹터요약」.
// POC6-28 「후보」 [섹터 요약] 탭을 독립 메뉴로 옮겼다. 이 화면의 조건(기간 · 제외 · 기본 저장)으로 같은 요약 응답을
// 읽고, 공통 기간의 상 · 하위 30을 업종 · 테마 · 보유 접점으로 묶어 보인다(같은 조건 · 자료 시점이면 후보리스트와 같은 목록).
// 묶음 안 ETF 줄을 누르면 후보리스트와 같은 행 상세(상세 수치 · 판단 근거)가 열린다.

import { useState } from "react";
import type { MenuKey } from "./LeftSidebar";
import {
  BasisSaveRow,
  CompareLines,
  ConditionPanel,
  SummaryStatus,
  okSummary,
  useEtfCompareSummary,
} from "./workbench/CompareHead";
import SectorSummary from "./workbench/SectorSummary";
import { invalidateQueries } from "@/lib/api/queryCache";
import { ETF_DETAIL_KEY_PREFIX, PRICE_SERIES_KEY_PREFIX } from "@/lib/api/dashboardKeys";

interface Props {
  onNavigate: (key: MenuKey) => void;
}

export default function SectorSummaryView({ onNavigate }: Props) {
  const { cond, q } = useEtfCompareSummary("sector");
  const [panel, setPanel] = useState(false);
  const [nonce, setNonce] = useState(0);
  const s = okSummary(q);
  const stale = q.phase === "success" && q.stale;

  return (
    <section aria-labelledby="sec-h" className="wb-root ec-root">
      <div className="ec-head">
        <h1 id="sec-h">섹터요약</h1>
        <button type="button" className="wb-btn btn-md" aria-expanded={panel} onClick={() => setPanel(!panel)}>
          조회 기준
        </button>
        <button
          type="button"
          className="wb-btn btn-md"
          onClick={() => {
            invalidateQueries(PRICE_SERIES_KEY_PREFIX);
            invalidateQueries(ETF_DETAIL_KEY_PREFIX);
            setNonce((n) => n + 1);
            q.reload();
          }}
        >
          다시 불러오기
        </button>
      </div>

      {panel && (
        <ConditionPanel
          screen="sector"
          cond={cond}
          onClose={() => setPanel(false)}
          applies="「섹터요약」 업종 · 테마 묶음 · 보유 접점"
        />
      )}
      <BasisSaveRow screen="sector" basis={cond.basis} />

      <SummaryStatus q={q} />
      {s && (
        <>
          <CompareLines s={s} stale={stale} showRegime />
          <SectorSummary key={`s${nonce}`} s={s} onNavigate={onNavigate} />
        </>
      )}
    </section>
  );
}
