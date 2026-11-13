"use client";

// POC6-29(PLAN §3-5 · 판정 Q5) — 「후보리스트」 「이 목록으로 할 일」.
// - 지금 고른 쪽(상위 또는 하위)의 최대 30개를 선정 순서로 넘긴다. 버튼 옆과 초안 글 맨 위에 기간 · 실제 날짜 ·
//   제외 조건 · 상하위 · 넘기는 건수를 적는다.
// - 「AI 투자 세션」 · 「ETF 구성종목」의 기존 초안 형식(sessionStorage)을 쓴다. AI 초안의 시장 흐름은 서버 글
//   (기준 기간 · 날짜가 붙은 6개월 글)을 그대로 넣는다. 저장 기록의 출처 값은 기존 계약 그대로(판정 Q16).
// - 저장하지 않은 AI 세션 초안이 있으면 바꾸기 전에 묻는다(판단 근거 카드와 같은 방식).
// - 시장 흐름 글은 누를 때 한 번 읽는다(화면을 열기만 해서는 조회하지 않음 · 못 읽으면 그 사실을 글에 적음).
// - 시장 판정(KODEX 200 국면 · KOSPI 보조 기준)도 누를 때 한 번 읽어 기존 초안 형식 그대로 싣는다
//   (질문 글 [시스템 시장 판정] · 저장 기록의 market_context_snapshot). 못 읽으면 그 사실을 글에 적고 스냅샷은 비운다.

import { useState } from "react";
import { fetchMarketFlowContext } from "@/lib/api/marketFlow";
import { fetchEtfDetail, type DetailSameKodex, type EtfDetailItem } from "@/lib/api/etfDetail";
import type { CompareRow, CompareSummaryOk } from "@/lib/api/etfCompare";
import type { MarketContext } from "@/lib/api";
import { fetchMarketTopnLatest, type MarketCandidate, type SamePeriodKodex200Item } from "@/lib/api/market";
import {
  describeDraftOrigin,
  loadAISessionsDraft,
  saveAISessionsDraft,
  type AISessionsDraft,
} from "@/lib/aiSessionsDraft";
import { buildETFExposureDraftFromMarketDiscovery, saveETFExposureDraft, toMarketContextSnapshot } from "@/lib/etfExposureDraft";
import { appendMarketContextSection } from "@/lib/marketDiscoveryCopyText";
import { BASIS_LABEL, filtersText, md, pct, priceStateLine } from "@/lib/etfCompare";
import { marketFlowCopySection } from "@/lib/marketFlowText";
import type { MenuKey } from "../LeftSidebar";
import CopyListButton from "./CopyListButton";

export const TRANSFER_FLOW_PERIOD = "6M";

export function transferScope(s: CompareSummaryOk, side: "top" | "bottom"): string {
  const rows = side === "top" ? s.top : s.bottom;
  return [
    `${BASIS_LABEL[s.basis]} ${side === "top" ? "상위" : "하위"} ${rows.length}개(선정 순서)`,
    `${md(s.period.start)} → ${md(s.period.end)}`,
    filtersText(s.filters),
    priceStateLine(s.price_state),
  ].join(" · ");
}

function returnOf(r: CompareRow, key: "one_month" | "three_month") {
  const c = r.criteria[key];
  return { return_pct: c.status === "ok" ? c.value : null, basis_start_date: c.start, basis_end_date: c.end, price_start_date: c.start, price_end_date: c.end };
}

// 같은 기간 KODEX 200(공통 기간 행 · 종목 상세 수치) → 예전 후보 칸(ok · 그 밖은 '후보 기간 확인 불가' + 실제 날짜).
function sameItemOf(s: Pick<DetailSameKodex, "status" | "value" | "etf_return_pct" | "kodex200_return_pct" | "start" | "end">): SamePeriodKodex200Item {
  return s.status === "ok"
    ? {
        status: "ok",
        start_date: s.start,
        end_date: s.end,
        candidate_return_pct: s.etf_return_pct,
        kodex200_return_pct: s.kodex200_return_pct,
        diff_pctp: s.value,
      }
    : { status: "unavailable", reason: "candidate_period_unknown", start_date: s.start, end_date: s.end };
}

// 「ETF 구성종목」 초안 · 시장 판정 스냅샷은 예전 후보 모양을 읽는다 — 공통 기간 행에서 같은 칸만 옮긴다(없는 칸은 비움).
// KODEX 200 대비 1개월 = 같은 기간(시작 · 끝 모두 같음)으로 계산된 값만(같지 않으면 비움 · 판정 Q4-1).
// 종목 상세 수치(`details`)가 있으면 같은 기간 KODEX 200 1 · 3개월을 그 값으로(행 상세 · 표와 같은 응답).
export function toMarketCandidates(rows: CompareRow[], details?: ReadonlyMap<string, EtfDetailItem>): MarketCandidate[] {
  return rows.map((r) => {
    const same = r.criteria.same_kodex_1m;
    const d = details?.get(r.ticker);
    return {
      rank: r.rank,
      ticker: r.ticker,
      name: r.name,
      tags: r.tags as MarketCandidate["tags"],
      returns: { one_month: returnOf(r, "one_month"), three_month: returnOf(r, "three_month") },
      excess_return: {
        vs_kodex200_1m_pctp: same.status === "ok" ? same.value : null,
        vs_kodex200_3m_pctp: d?.same_kodex.three_month.status === "ok" ? d.same_kodex.three_month.value : null,
        vs_kospi_1m_pctp: null,
        vs_kospi_3m_pctp: null,
      },
      same_period_kodex200: {
        one_month: sameItemOf(d ? d.same_kodex.one_month : same),
        three_month: d ? sameItemOf(d.same_kodex.three_month) : null,
      },
    } as MarketCandidate;
  });
}

// 넘길 때 한 번 읽는 시장 판정 — 읽기 실패와 '판정 자료 없음'을 구분한다.
export type MarketRead = { ok: true; ctx: MarketContext | null } | { ok: false };

export function marketSection(m: MarketRead): string {
  if (!m.ok) return "[시스템 시장 판정]\n- 시장 판정을 불러오지 못했습니다(넘길 때 읽기 실패 · 이 글에는 싣지 않음)";
  const lines: string[] = [];
  appendMarketContextSection(lines, m.ctx);
  return lines.join("\n");
}

export function transferQuestion(s: CompareSummaryOk, side: "top" | "bottom", flowText: string, market: MarketRead): string {
  const rows = side === "top" ? s.top : s.bottom;
  const lines = [
    `[「후보리스트」 목록 · ${transferScope(s, side)}]`,
    `비교한 ETF ${s.counts.population}개 중 · 기간이 달라 뺀 ${s.counts.period_differs}개 · 넘기는 건수 ${rows.length}개`,
    "",
    "[목록 — 선정 순서]",
    ...rows.map((r) => {
      const one = r.criteria.one_month;
      const three = r.criteria.three_month;
      return (
        `- ${side === "top" ? "상위" : "하위"} ${r.rank}위 ${r.name ?? r.ticker}(${r.ticker}) · 선정 ${BASIS_LABEL[s.basis]} ${pct(
          r.basis_return.value,
        )}` +
        ` · 1개월 ${one.status === "ok" ? pct(one.value) : "값 없음"} · 3개월 ${three.status === "ok" ? pct(three.value) : "값 없음"}`
      );
    }),
    "",
    marketSection(market),
    "",
    flowText,
    "",
    "[요청]",
    "- 위 목록을 ① 함께 보이는 공통점 ② 이름에서 유추한 가설(추정) ③ 더 확인할 자료로 나눠 정리해 주세요.",
    "- 매수 · 매도 결론이나 위험 등급은 만들지 말고, 날짜가 다른 값은 그 차이를 함께 짚어 주세요.",
  ];
  return lines.join("\n");
}

export default function ListTransfer({
  s,
  side,
  onNavigate,
}: {
  s: CompareSummaryOk;
  side: "top" | "bottom";
  onNavigate?: (key: MenuKey) => void;
}) {
  const [pending, setPending] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  // 누를 때 한 번 — 시장 흐름 글 · 시장 판정을 함께 읽는다.
  const readContext = async (): Promise<{ text: string; market: MarketRead }> => {
    const [data, market] = await Promise.all([
      fetchMarketFlowContext().catch(() => null),
      fetchMarketTopnLatest(10)
        .then((r): MarketRead => ({ ok: true, ctx: r.market_context ?? null }))
        .catch((): MarketRead => ({ ok: false })),
    ]);
    return { text: marketFlowCopySection(data, TRANSFER_FLOW_PERIOD), market };
  };
  const rows = side === "top" ? s.top : s.bottom;
  const scope = transferScope(s, side);

  const ctxOf = (m: MarketRead) => (m.ok ? m.ctx : null);
  const aiDraft = (text: string, market: MarketRead): AISessionsDraft => ({
    asof: s.end_date,
    filters: s.filters,
    candidate_snapshot: rows.map((r) => ({
      rank: r.rank,
      ticker: r.ticker,
      name: r.name,
      daily_return_pct: s.basis === "daily" ? r.basis_return.value : null,
      one_month_return_pct: r.criteria.one_month.status === "ok" ? r.criteria.one_month.value : null,
      three_month_return_pct: r.criteria.three_month.status === "ok" ? r.criteria.three_month.value : null,
      tags: r.tags,
    })),
    question_text: transferQuestion(s, side, text, market),
    linked_market_refresh_id: null,
    draft_created_at: new Date().toISOString(),
    // 기존 초안 형식 — AI 세션 저장 때 market_context_snapshot 으로 남는다(공통 기간 목록 응답에 없는 단기 흐름 · 자료 품질은 비움).
    market_context_snapshot: toMarketContextSnapshot(ctxOf(market), toMarketCandidates(rows)),
  });

  const goAi = async (force: boolean) => {
    const old = loadAISessionsDraft();
    if (old && !force) {
      setPending(describeDraftOrigin(old));
      return;
    }
    setBusy(true);
    const { text, market } = await readContext();
    setBusy(false);
    saveAISessionsDraft(aiDraft(text, market));
    setPending(null);
    onNavigate?.("ai_sessions");
  };

  const goExposure = async () => {
    setBusy(true);
    // 같은 기간 KODEX 200 1 · 3개월 = 넘길 때 한 번 읽는 종목 상세 수치(최대 30 · 못 읽으면 1개월만 목록 값).
    const [{ text, market }, detail] = await Promise.all([
      readContext(),
      fetchEtfDetail(rows.map((r) => r.ticker)).catch(() => null),
    ]);
    setBusy(false);
    const details =
      detail && detail.status === "ok" && detail.end_date === s.end_date
        ? new Map(detail.items.map((it) => [it.ticker, it]))
        : undefined;
    const cands = toMarketCandidates(rows, details);
    saveETFExposureDraft(
      buildETFExposureDraftFromMarketDiscovery({
        asof: s.end_date,
        filters: s.filters,
        candidates: cands,
        marketContext: ctxOf(market),
        marketContextSnapshot: toMarketContextSnapshot(ctxOf(market), cands),
        marketFlowText: text,
        // 판정 Q5 — 「ETF 구성종목」 화면 · 그 화면이 만드는 AI 질문 글에도 기간 · 날짜 · 제외 · 상하위 · 건수.
        listScope: `「후보리스트」 ${scope}`,
      }),
    );
    onNavigate?.("etf_exposure");
  };

  return (
    <div className="ec-card wb-card" data-testid="ec-transfer">
      <h2>이 목록으로 할 일</h2>
      <div className="ec-small" data-testid="ec-transfer-scope">
        넘기는 범위: {scope}
      </div>
      <div className="ec-btn-row">
        <button type="button" className="wb-btn btn-md" disabled={rows.length === 0 || busy} onClick={() => void goAi(false)}>
          이 목록을 AI 투자 세션으로 넘기기
        </button>
        <button type="button" className="wb-btn btn-md" disabled={rows.length === 0 || busy} onClick={() => void goExposure()}>
          이 목록을 ETF 구성종목에서 보기
        </button>
      </div>
      {pending && (
        <div className="ddp-replace" role="alert">
          <span>저장하지 않은 AI 세션 초안이 있습니다({pending}). 바꾸면 그 초안은 사라집니다.</span>
          <button type="button" className="btn-md" onClick={() => void goAi(true)}>
            바꾸고 이동
          </button>
          <button type="button" className="btn-md ddp-cancel" onClick={() => setPending(null)}>
            취소
          </button>
        </div>
      )}
      <CopyListButton s={s} side={side} />
      <div className="ec-small">한 종목의 AI 검토는 행을 펼친 뒤 [AI 세션에서 검토] · 목록 전달은 위 버튼입니다.</div>
    </div>
  );
}
