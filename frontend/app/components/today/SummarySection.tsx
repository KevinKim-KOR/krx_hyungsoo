"use client";

// POC6-16 — 「오늘의 투자 점검」 「지금 확인할 내용」(설계 V1 · PLAN 판정 V1.1 · 사용자 목업 확인 2026-11-02).
// POC6-27 — 개편(설계 §1-4 · §1-5 · PLAN 판정 §2): 시장 흐름(코스피 수치 → 차트 → 외국인 수급 → 최근 큰 변화)
//   → 보유 점검 | 잘 오르는 ETF 두 칸 → 자료 · 연구 상태(자료 확인 · 연구 · 「자료 확인」 펼침 = 기존 정비 목록).
//   「지금 할 일」은 맨 위 「자료 최신화 필요」 카드로 옮겼다(판정 Q2 · 같은 판정 함수 · 버튼은 이 화면 동작).
//   사용자 결정 ④(2026-11-09): 보유 자세히 | 잘 오르는 ETF 자세히(detailBlock)를 자료 · 연구 상태 위로.
// 줄 버튼: 주요 이동 하나만 파란 버튼, 보조 이동은 테두리 버튼. 이동 · 스크롤 · 다시 읽기만 한다.

import type { ReactNode } from "react";
import type { SummaryAction, SummaryRow, SummaryTone } from "./summaryLines";

const TONE_CLASS: Record<SummaryTone, string> = {
  ok: "tc-sum-ok",
  warn: "tc-sum-warn",
  muted: "tc-sum-muted",
  bad: "tc-sum-bad",
  info: "tc-sum-info",
};

function ActionButton({
  a,
  onAction,
  disabled,
}: {
  a: SummaryAction;
  onAction: (a: SummaryAction) => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      className={a.primary ? "btn-md" : "btn-md tc-fold-btn"}
      onClick={() => onAction(a)}
      disabled={disabled}
    >
      {a.label}
    </button>
  );
}

function Row({ r, onAction, extra }: { r: SummaryRow; onAction: (a: SummaryAction) => void; extra?: ReactNode }) {
  return (
    <div className="tc-sum-row" data-row={r.id}>
      <div className="tc-sum-area">{r.area}</div>
      <div className="tc-sum-cell">
        <div className="tc-sum-main">
          <span className={`tc-sum-badge ${TONE_CLASS[r.tone]}`}>{r.badge}</span>
          <span>{r.text}</span>
        </div>
        {r.sub ? <div className="tc-sum-sub">{r.sub}</div> : null}
        {r.note ? <div className="tc-sum-note">{r.note}</div> : null}
        {r.basis ? <div className="tc-sum-basis">{r.basis}</div> : null}
        {r.staleNote ? <div className="tc-sum-stale">{r.staleNote}</div> : null}
        {extra}
      </div>
      <div className="tc-sum-go">
        {r.actions.map((a) => (
          <ActionButton key={a.label} a={a} onAction={onAction} />
        ))}
      </div>
    </div>
  );
}

export default function SummarySection({
  marketBlock,
  holdingsCard,
  candidatesCard,
  dataRows,
  detailBlock,
  dataFold,
  onAction,
}: {
  marketBlock: ReactNode;
  holdingsCard: ReactNode;
  candidatesCard: ReactNode;
  // 보유 자세히 | 잘 오르는 ETF 자세히(두 칸 아래 · 자료 · 연구 상태 위 · 사용자 결정 ④)
  detailBlock: ReactNode;
  dataRows: SummaryRow[];
  // 「자료 확인」 줄 아래 펼침(기존 정비 목록 · 판정 Q2)
  dataFold: ReactNode;
  onAction: (a: SummaryAction) => void;
}) {
  return (
    <section className="tc-sum-wrap" aria-label="지금 확인할 내용">
      <div className="tc-sum-head">
        <h2 className="tc-h2" style={{ margin: 0 }}>
          지금 확인할 내용
        </h2>
        <span className="tc-muted tc-small">요약은 각 화면의 값을 그대로 옮긴 것 · 새 점수 · 등급 없음</span>
      </div>
      {marketBlock}
      <div className="tc-check-grid">
        {holdingsCard}
        {candidatesCard}
      </div>
      {detailBlock}
      <section className="tc-card tc-sum" aria-label="자료 · 연구 상태">
        <div className="tc-sum-group">
          자료 · 연구 상태 <span className="tc-sum-group-note">(투자 판단 신호가 아닙니다)</span>
        </div>
        <div role="group" aria-label="자료 · 연구 상태">
          {dataRows.map((r) => (
            <Row
              key={r.id}
              r={r}
              onAction={onAction}
              extra={
                r.id === "data" ? (
                  <details className="tc-data-fold">
                    <summary>자료 업데이트 목록</summary>
                    {dataFold}
                  </details>
                ) : null
              }
            />
          ))}
        </div>
      </section>
    </section>
  );
}
