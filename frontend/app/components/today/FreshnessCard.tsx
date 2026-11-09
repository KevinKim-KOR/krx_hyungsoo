"use client";

// POC6-27 — 상단 「자료 최신화 필요」(설계 §1-2 · §2 · 사용자 결정 ② · PLAN 판정 §2 · Q2).
//
// - 늦은 자료 · 기준 확인이 필요한 자료(자료별 최신성) + 기존 「지금 할 일」 판정(summaryTasks)이 알린
//   바로 조치할 일이 있을 때만 보인다. 기본 접힘(화면 안 상태만 · 저장 없음 · 다시 들어오면 접힘).
// - 접힌 줄: 제목 · 요약('2건 · 1거래일 늦음' 또는 '늦음 N건 · 기준 확인 필요 M건' · 할 일 수) · [펼치기].
// - 펼치면 자료별 마지막 날짜 · 기대일과 기준 · 사유, 할 일의 사유 · 안내, 그리고 이 화면의 같은 작업 버튼
//   (최신 시장 데이터 갱신 · 보유 현재가 업데이트 · 요약 다시 읽기). 갱신 · 계산은 버튼을 누를 때만.
// - 사용자 결정 ⑤(2026-11-09): 옆 「OCI 운영 스케줄 확인」과 함께 펼치고 접는다 — 부모가 open · onToggle 을 주면 그 상태를 쓴다.
import { useState } from "react";
import { freshnessLine, freshnessSummary, type FreshAction, type FreshRow } from "@/lib/todayFreshness";
import type { SummaryAction, SummaryTask } from "./summaryLines";

const ACTION_LABEL: Record<Exclude<FreshAction, null>, string> = {
  market: "최신 시장 데이터 갱신",
  holdings: "보유 현재가 업데이트",
  reload: "요약 다시 읽기",
};

export default function FreshnessCard({
  rows,
  tasks,
  onAction,
  busy,
  open: openProp,
  onToggle,
}: {
  rows: FreshRow[];
  tasks: SummaryTask[];
  onAction: (a: SummaryAction) => void;
  busy: { market: boolean; holdings: boolean; reload: boolean };
  open?: boolean;
  onToggle?: () => void;
}) {
  const [openSelf, setOpenSelf] = useState(false);
  const open = openProp ?? openSelf;
  if (rows.length === 0 && tasks.length === 0) return null;
  const summary = [freshnessSummary(rows), tasks.length ? `할 일 ${tasks.length}건` : null]
    .filter(Boolean)
    .join(" · ");
  // 이 카드의 버튼은 작업 종류마다 한 번(할 일 · 자료 줄이 같은 작업을 가리켜도 한 버튼 · 상단 버튼과 같은 작업).
  const kinds = new Set<Exclude<FreshAction, null>>();
  for (const r of rows) if (r.action) kinds.add(r.action);
  for (const t of tasks) {
    const k = t.action?.target.kind;
    if (k === "market_refresh") kinds.add("market");
    else if (k === "holdings_refresh") kinds.add("holdings");
    else if (k === "reload") kinds.add("reload");
  }
  const order: Exclude<FreshAction, null>[] = ["market", "holdings", "reload"];
  const actions = order.filter((k) => kinds.has(k));
  const toAction = (a: Exclude<FreshAction, null>): SummaryAction => ({
    label: ACTION_LABEL[a],
    target: a === "market" ? { kind: "market_refresh" } : a === "holdings" ? { kind: "holdings_refresh" } : { kind: "reload" },
    primary: false,
  });
  const disabledOf = (t: SummaryAction["target"]) =>
    t.kind === "market_refresh" ? busy.market : t.kind === "holdings_refresh" ? busy.holdings : t.kind === "reload" ? busy.reload : false;

  return (
    <section className="tc-card tc-fold-card tc-fold-warn" aria-label="자료 최신화 필요" data-testid="tc-fresh-card">
      <div className="tc-fold-card-head">
        <h2 className="tc-h2 tc-fold-card-title">자료 최신화 필요</h2>
        <span className="tc-chip tc-chip-warn" data-testid="tc-fresh-summary">
          {summary}
        </span>
        <button
          type="button"
          className="btn-md tc-fold-btn tc-fold-card-btn"
          aria-expanded={open}
          aria-label={open ? "자료 최신화 필요 접기" : "자료 최신화 필요 펼치기"}
          onClick={() => (onToggle ? onToggle() : setOpenSelf((v) => !v))}
        >
          {open ? "접기" : "펼치기"}
        </button>
      </div>
      {open ? (
        <div className="tc-fold-card-body" data-testid="tc-fresh-body">
          {rows.length > 0 ? (
            <ul className="tc-fresh-list">
              {rows.map((r) => (
                <li key={r.key} className="tc-fresh-row" data-fresh={r.key}>
                  <span className="tc-fresh-label">{r.label}</span>
                  <span className="tc-fresh-line">{freshnessLine(r)}</span>
                </li>
              ))}
            </ul>
          ) : null}
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
            </div>
          ))}
          {actions.length > 0 ? (
            <div className="tc-btn-row">
              {actions.map((a) => {
                const act = toAction(a);
                return (
                  <button
                    key={a}
                    type="button"
                    className="btn-md tc-fold-btn"
                    disabled={disabledOf(act.target)}
                    onClick={() => onAction(act)}
                  >
                    {act.label}
                  </button>
                );
              })}
            </div>
          ) : null}
          <p className="tc-muted tc-small">
            기대 기준일은 서버가 정한 국내 직전 거래일입니다. 지연 원인은 이 화면에서 확인하지 않습니다.
          </p>
        </div>
      ) : null}
    </section>
  );
}
