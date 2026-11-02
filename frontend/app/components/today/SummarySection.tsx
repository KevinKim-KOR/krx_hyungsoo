"use client";

// POC6-16 — 「오늘의 투자 점검」 맨 위 「지금 확인할 내용」(설계 V1 · PLAN 판정 V1.1 · 사용자 목업 확인 2026-11-02).
//
// 순서: (있을 때만) 「지금 할 일」 → 투자 판단에 볼 것(시장 흐름 · 보유 점검 · 후보 살펴보기)
//   → 자료 · 연구 상태(자료 확인 · 연구 — 투자 판단 신호 아님). 줄 = 영역 · 결론 한 줄 · 기준일 · 이동.
// 버튼: 줄마다 주요 이동 하나만 파란 버튼, 보조 이동은 테두리 버튼(판정 §3). 이동 · 스크롤 · 다시 읽기만 하고
//   갱신 · 계산 명령은 부르지 않는다(시장 자료 갱신은 이동한 화면에서 사용자가 누름).
// 문장 · 숫자는 summaryLines 가 기존 응답 · 함수에서 만든 것을 그대로 그린다.

import type { SummaryAction, SummaryRow, SummaryTask, SummaryTone } from "./summaryLines";

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

function Row({ r, onAction }: { r: SummaryRow; onAction: (a: SummaryAction) => void }) {
  return (
    <div className="tc-sum-row" data-row={r.id}>
      <div className="tc-sum-area">{r.area}</div>
      <div className="tc-sum-cell">
        <div className="tc-sum-main">
          <span className={`tc-sum-badge ${TONE_CLASS[r.tone]}`}>{r.badge}</span>
          <span>{r.text}</span>
        </div>
        {r.sub ? <div className="tc-sum-sub">{r.sub}</div> : null}
        {r.basis ? <div className="tc-sum-basis">{r.basis}</div> : null}
        {r.staleNote ? <div className="tc-sum-stale">{r.staleNote}</div> : null}
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
  tasks,
  judgeRows,
  dataRows,
  onAction,
  reloading,
}: {
  tasks: SummaryTask[];
  judgeRows: SummaryRow[];
  dataRows: SummaryRow[];
  onAction: (a: SummaryAction) => void;
  reloading: boolean;
}) {
  return (
    <section className="tc-card tc-sum" aria-label="지금 확인할 내용">
      <div className="tc-sum-head">
        <h2 className="tc-h2" style={{ margin: 0 }}>
          지금 확인할 내용
        </h2>
        <span className="tc-muted tc-small">요약은 각 화면의 값을 그대로 옮긴 것 · 새 점수 · 등급 없음</span>
      </div>

      {tasks.length > 0 ? (
        <div className="tc-sum-tasks" role="region" aria-label="지금 할 일">
          <div className="tc-sum-tasks-title">지금 할 일</div>
          {tasks.map((t) => (
            <div key={t.id} className="tc-sum-task" data-task={t.id}>
              <div className="tc-sum-task-body">
                <strong>{t.title}</strong>
                <ul className="tc-sum-reasons">
                  {t.reasons.map((x) => (
                    <li key={x}>{x}</li>
                  ))}
                </ul>
                <div className="tc-sum-do">{t.doText}</div>
              </div>
              {t.action ? (
                <div className="tc-sum-go">
                  <ActionButton
                    a={t.action}
                    onAction={onAction}
                    disabled={t.action.target.kind === "reload" && reloading}
                  />
                </div>
              ) : null}
            </div>
          ))}
        </div>
      ) : null}

      <div className="tc-sum-group">투자 판단에 볼 것</div>
      <div role="group" aria-label="투자 판단에 볼 것">
        {judgeRows.map((r) => (
          <Row key={r.id} r={r} onAction={onAction} />
        ))}
      </div>
      <div className="tc-sum-group">
        자료 · 연구 상태 <span className="tc-sum-group-note">(투자 판단 신호가 아닙니다)</span>
      </div>
      <div role="group" aria-label="자료 · 연구 상태">
        {dataRows.map((r) => (
          <Row key={r.id} r={r} onAction={onAction} />
        ))}
      </div>
    </section>
  );
}
