"use client";

// POC6-31 STEP 2(PLAN C10 · C11 · 판정 Q5 (b) · Q20 · §4 M1) — [최신 자료 갱신]의 '보유 구성종목' 결과 줄 · ETF별 보기.
// - 이 화면에서 갱신을 돌렸으면 그 작업 결과(진행 · 완료)를, 아니면 저장 자료로 만든 상태(GET /market/constituents/holdings-status)를 보인다.
// - 번호 없는 별도 줄 · 사라지지 않음(① 줄처럼 3초 뒤 지우지 않음).
// - '기존 자료' · '새로 받음' · '목표일 자료 대기' · '갱신 실패'(받기 실패 · 시간 초과로 조회 안 함 · 저장 잠김 · 원천 기준일 미확인)를 나눠 센다.
import { useState } from "react";
import type { QueryState } from "@/lib/api/queryCache";
import type { RefreshAllConstituentsStep } from "@/lib/api/refreshAll";
import {
  UPDATE_FAILED_RESULTS,
  type ConstituentCounts,
  type ConstituentItem,
  type HoldingsConstituentsStatus,
} from "@/lib/api/constituentsStatus";
import { TARGET_RULE_TEXT, countsText, dateMixText, itemReason, unloggedText } from "@/lib/constituentsText";

export { countsText, dateMixText };
import { md } from "@/lib/etfCompare";
import { kstMdHm } from "@/lib/marketNowText";

function dateCell(it: ConstituentItem): string {
  if (it.source_asof) return md(it.source_asof);
  if (it.kept_asof) return `${md(it.kept_asof)}(마지막 보존${it.kept_confirmed ? "" : " · 원천 기준일 미확인"})`;
  return "없음";
}

function warnOf(counts: ConstituentCounts | null | undefined): boolean {
  const c = counts ?? {};
  return (c.target_wait ?? 0) > 0 || (c.not_checked ?? 0) > 0 || UPDATE_FAILED_RESULTS.some((k) => (c[k] ?? 0) > 0);
}

export default function HoldingsConstituentsResult({
  step,
  status,
}: {
  step: RefreshAllConstituentsStep | null | undefined;
  status: QueryState<HoldingsConstituentsStatus>;
}) {
  const [open, setOpen] = useState(false);
  let line: string | null = null;
  let warn = false;
  let items: ConstituentItem[] = [];
  let detail: string | null = null;
  let target: string | null | undefined = null;
  if (step && step.status !== "pending") {
    target = step.target_date;
    const tgt = target ? `(목표일 ${md(target)})` : "";
    if (step.status === "running") {
      line =
        step.batch_total && step.total
          ? `보유 구성종목 받는 중${tgt} — ${step.batch_index ?? 0}/${step.batch_total} 묶음 · 받을 ETF ${step.total}개 중 ${step.done ?? 0}개 끝`
          : `보유 구성종목 받는 중${tgt}...`;
      items = step.items ?? [];
    } else if (step.status === "done") {
      items = step.items ?? [];
      const unlogged = unloggedText(step.unlogged_logs);
      line = `보유 구성종목${tgt} — ${countsText(step.counts, step.total ?? items.length, {
        calls: step.calls,
        shared: step.shared,
      })}${items.length ? ` · 구성 기준일 ${dateMixText(items)}` : ""}`;
      warn = warnOf(step.counts) || !!step.reason || !!unlogged;
      if (step.reason) line += ` · ${step.reason}`;
      if (unlogged) line += ` · ${unlogged}`;
      detail = step.reason_detail ?? null;
    } else {
      line = `보유 구성종목 — ${step.reason ?? "받지 못했습니다"}`;
      warn = step.status === "failed";
    }
  } else if (status.phase === "success") {
    const s = status.data;
    target = s.target_date;
    if (s.status === "skipped") {
      line = `보유 구성종목 — ${s.reason ?? "확인할 보유 ETF 가 없습니다"}`;
    } else if (s.status === "read_failed") {
      line = `보유 구성종목 — ${s.reason ?? "구성 상태를 읽지 못했습니다"}`;
      warn = true;
    } else {
      items = s.items;
      // 저장 자료로 만든 상태 — '새로 받음'은 생기지 않으므로 '목표일 이상 구성'으로 센다.
      line = `보유 구성종목(목표일 ${md(s.target_date)}) — ${countsText(s.counts, s.total, { statusMode: true })}${
        s.needs_check > 0 ? ` · 다시 확인 필요 ${s.needs_check} — [최신 자료 갱신]에서 받습니다` : ""
      }`;
      warn = s.needs_check > 0;
    }
  } else if (status.phase === "error") {
    line = "보유 구성종목 상태를 읽지 못했습니다 — [요약 다시 읽기]로 다시 읽습니다";
    warn = true;
  }
  if (!line) return null;
  return (
    <div data-testid="tc-constituents-result">
      <p className={warn ? "tc-warn tc-small" : "tc-muted tc-small"}>
        {line}
        {items.length > 0 ? (
          <>
            {" "}
            <button
              type="button"
              className="btn-md tc-fold-btn"
              aria-expanded={open}
              onClick={() => setOpen((v) => !v)}
              data-testid="tc-constituents-toggle"
            >
              {open ? "ETF별 보기 접기" : "ETF별 보기"}
            </button>
          </>
        ) : null}
      </p>
      {detail ? (
        <details className="tc-small">
          <summary>자세히</summary>
          {detail}
        </details>
      ) : null}
      {open && items.length > 0 ? (
        <div className="wb-table-wrap">
          <p className="tc-muted tc-small" data-testid="tc-constituents-rule">
            {target ? `수집 목표일 ${md(target)} · ` : ""}
            {TARGET_RULE_TEXT} · 실제 구성일 = 원천이 준 날짜
          </p>
          <table className="wb-table" data-testid="tc-constituents-table">
            <thead>
              <tr>
                <th>보유 ETF</th>
                <th>결과</th>
                <th>실제 구성일</th>
                <th>확인 시각</th>
                <th>이유</th>
              </tr>
            </thead>
            <tbody>
              {items.map((it) => (
                <tr key={it.ticker}>
                  <td>
                    {it.name ?? it.ticker} <span className="tc-muted">{it.ticker}</span>
                  </td>
                  <td>{it.label}</td>
                  <td>{dateCell(it)}</td>
                  <td>{it.checked_at || it.last_checked_at ? kstMdHm(it.checked_at ?? it.last_checked_at) : "—"}</td>
                  <td>{itemReason(it)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}
