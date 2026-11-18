"use client";

// POC6-16 — 「오늘의 투자 점검」 「지금 확인할 내용」(설계 V1 · PLAN 판정 V1.1 · 사용자 목업 확인 2026-11-02).
// POC6-27 — 개편(설계 §1-4 · §1-5 · PLAN 판정 §2): 시장 흐름(코스피 수치 → 차트 → 외국인 수급 → 최근 큰 변화)
//   → 보유 점검 | 잘 오르는 ETF 두 칸 → 자료 · 연구 상태(자료 확인 · 연구 · 「자료 확인」 펼침 = 기존 정비 목록).
//   「지금 할 일」은 맨 위 「자료 최신화 필요」 카드로 옮겼다(판정 Q2 · 같은 판정 함수 · 버튼은 이 화면 동작).
//   사용자 결정 ④(2026-11-09): 보유 자세히 | 잘 오르는 ETF 자세히(detailBlock)를 자료 · 연구 상태 위로.
// POC6-32(판정 Q1 (a)) — 「잘 오르는 ETF」 칸 자리에 「ETF 주간 검토」(weeklyCard · 표가 있어 보유 점검 아래 전체 폭).
// POC6-32 V2(PLAN §2 S2) — 그 자리 = 「주간 ETF 점검」 한 줄([주간 ETF 점검 열기 →] = 메뉴 「주간 ETF 점검」으로 이동).
//   주간 자료는 이 화면에서 읽지 않는다(주간 화면이 열 때 읽음). 이 화면 글자에는 '후보'를 쓰지 않는다(AC-7 · 메뉴 이름 제외).
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

// POC6-32 V2(PLAN §2 S2 · 목업 ①) — 주간 화면으로 가는 한 줄(보조 버튼 · 이동만).
const OPEN_WEEKLY: SummaryAction = {
  label: "주간 ETF 점검 열기 →",
  target: { kind: "menu", key: "weekly_etf_check" },
  primary: false,
};

function WeeklyLink({ onAction }: { onAction: (a: SummaryAction) => void }) {
  return (
    <section className="tc-card tc-weekly-link" aria-label="주간 ETF 점검" data-testid="tc-weekly-link">
      <div className="tc-weekly-link-head">
        <h3 className="tc-h3" style={{ margin: 0 }}>
          주간 ETF 점검
        </h3>
        <ActionButton a={OPEN_WEEKLY} onAction={onAction} />
      </div>
      <div className="tc-muted tc-small">
        ETF 고르기 · 보유와 겹침 · AI 의견 · 검토 기록은 주간 화면에서 봅니다(이 화면은 주간 자료를 읽지 않음).
      </div>
    </section>
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
  dataRows,
  detailBlock,
  dataFold,
  onAction,
}: {
  marketBlock: ReactNode;
  holdingsCard: ReactNode;
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
      {holdingsCard}
      <WeeklyLink onAction={onAction} />
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
