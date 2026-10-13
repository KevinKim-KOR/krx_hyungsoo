"use client";

// POC5-09 — 저장 거래량 칸(「확인 근거」 종목 상세 4칸 · 「오늘의 투자 점검」 KODEX200 2 × 2).
// 네 칸은 기존 상세 칸 양식(.wb-detail-grid · .wb-detail-cell)을 쓴다. 새 조회 없음 — 부모가 받은
// 응답의 선택 필드만 표시한다. 자료가 없어도 다른 칸(가격 · NAV · 차트)을 가리지 않는다.
import type { StoredVolumeEvidence } from "@/lib/api";
import {
  NO_VOLUME_TEXT,
  pastVolumeNote,
  volumeCells,
  volumeSourceParts,
} from "@/lib/storedVolume";

export default function StoredVolumeBlock({
  title,
  ev,
  help,
  columns,
  headClassName,
  referenceDate,
}: {
  title: string;
  ev: StoredVolumeEvidence | null | undefined;
  help: string;
  columns: 2 | 4;
  headClassName: string;
  referenceDate?: string | null;
}) {
  const past = ev ? pastVolumeNote(ev, referenceDate) : null;
  const [source, window] = ev ? volumeSourceParts(ev) : ["", ""];
  return (
    <div className="svb" data-testid="stored-volume">
      <div className={headClassName}>
        {title}{" "}
        <span className="tc-info" tabIndex={0} role="note" aria-label={help} title={help}>
          ⓘ
        </span>
        {past ? <span className="hre-status-check svb-past"> {past}</span> : null}
      </div>
      {!ev || ev.status === "no_price_data" ? (
        <p className="helper">{NO_VOLUME_TEXT}</p>
      ) : (
        <>
          <div className={columns === 2 ? "wb-detail-grid svb-2" : "wb-detail-grid"}>
            {volumeCells(ev).map((c) => (
              <div key={c.label} className="wb-detail-cell">
                <span className="svb-k">{c.label}</span>
                <span className="svb-v">{c.value}</span>
              </div>
            ))}
          </div>
          <div className="svb-src">
            {source}
            {columns === 2 ? <br /> : " · "}
            {window}
          </div>
        </>
      )}
    </div>
  );
}
