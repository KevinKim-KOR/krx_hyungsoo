"use client";

// 현재 run 의 status / draft_payload 표시 + Approve / Reject + 느린 polling.
// 부모(MainPanel) 가 run state 를 controlled 로 관리한다 (run / setRun prop).
//
// Step 2C 변경:
// - draft_payload.recommendations 가 holdings 형태이면 compact UI 로 렌더 (전체 요약 +
//   계좌별 요약 + compact table + 상세 펼침). 기존 카드 나열 형식 폐지.
// - account_group / source_index 는 신규 draft_payload 에는 항상 포함되지만 과거 run
//   에는 없을 수 있다 → 누락 시 "일반" / 행 인덱스 fallback. KeyError 발생 안 함.
// - 상세 펼침 상태는 항목 식별자(source_index|ticker|account_group|avg_buy_price) 단위로
//   유지된다. polling 으로 동일 run 의 동일 항목이 다시 패치되어도 펼친 상태 유지.
// - 새 run 으로 전환되면 펼침 상태 초기화.

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ApiConfigError,
  ApiRequestError,
  approveRun,
  fetchRun,
  isTerminal,
  rejectRun,
  type Run,
  type RunStatus,
} from "@/lib/api";

const POLL_INTERVAL_MS = 12000;
const MAX_POLL_TICKS = 30;
const DEFAULT_GROUP = "일반";

function humanLabel(status: RunStatus): string {
  switch (status) {
    case "PENDING_APPROVAL":
      return "승인 대기";
    case "DELIVERING":
      return "전달 중";
    case "COMPLETED":
      return "전달 완료";
    case "REJECTED":
      return "거절됨";
    case "FAILED":
      return "실패";
  }
}

function describeApiError(e: unknown): string {
  if (e instanceof ApiConfigError) return `구성 오류: ${e.message}`;
  if (e instanceof ApiRequestError) {
    const detail =
      typeof e.body === "string"
        ? e.body
        : e.body && typeof e.body === "object" && "detail" in e.body
          ? String((e.body as Record<string, unknown>).detail)
          : JSON.stringify(e.body);
    return `요청 실패(HTTP ${e.httpStatus}): ${detail}`;
  }
  return `알 수 없는 오류: ${(e as Error).message}`;
}

function isHoldingsRec(r: Record<string, unknown>): boolean {
  return "quantity" in r || "avg_buy_price" in r;
}

function toFiniteNumber(v: unknown): number | null {
  const n = typeof v === "number" ? v : Number(v);
  return Number.isFinite(n) ? n : null;
}

function fmtMoney(v: unknown): string | null {
  const n = toFiniteNumber(v);
  if (n === null) return null;
  return `${n.toLocaleString("ko-KR", { maximumFractionDigits: 2 })}원`;
}

function fmtSignedMoney(v: unknown): string | null {
  const n = toFiniteNumber(v);
  if (n === null) return null;
  const sign = n > 0 ? "+" : "";
  return `${sign}${n.toLocaleString("ko-KR", { maximumFractionDigits: 2 })}원`;
}

function fmtPct(v: unknown): string | null {
  const n = toFiniteNumber(v);
  if (n === null) return null;
  return `${n.toLocaleString("ko-KR", { maximumFractionDigits: 2 })}%`;
}

function fmtSignedPct(v: unknown): string | null {
  const n = toFiniteNumber(v);
  if (n === null) return null;
  const sign = n > 0 ? "+" : "";
  return `${sign}${n.toLocaleString("ko-KR", { maximumFractionDigits: 2 })}%`;
}

function pnlClass(v: unknown): string {
  const n = toFiniteNumber(v);
  if (n === null) return "";
  if (n > 0) return "pnl-pos";
  if (n < 0) return "pnl-neg";
  return "";
}

// ─── recommendations 정규화 ─────────────────────────────────────

type NormRec = {
  ticker: string;
  name: string;
  account_group: string;
  source_index: number;
  quantity: number | null;
  avg_buy_price: number | null;
  invested_amount: number | null;
  current_price: number | null;
  eval_amount: number | null;
  pnl_amount: number | null;
  pnl_rate_pct: number | null;
  buy_weight_pct: number | null;
  market_weight_pct: number | null;
  price_asof: string | null;
  price_source: string | null;
  action: string;
  reason: string;
};

function normalizeRec(r: Record<string, unknown>, idx: number): NormRec {
  const ag = typeof r.account_group === "string" && r.account_group.trim()
    ? r.account_group
    : DEFAULT_GROUP;
  const si =
    typeof r.source_index === "number" && Number.isFinite(r.source_index)
      ? r.source_index
      : idx;
  const ticker = typeof r.ticker === "string" ? r.ticker : "";
  const name = typeof r.name === "string" ? r.name : "";
  const action = typeof r.action === "string" ? r.action : "";
  const reason = typeof r.reason === "string" ? r.reason : "";
  return {
    ticker,
    name,
    account_group: ag,
    source_index: si,
    quantity: toFiniteNumber(r.quantity),
    avg_buy_price: toFiniteNumber(r.avg_buy_price),
    invested_amount: toFiniteNumber(r.invested_amount),
    current_price: toFiniteNumber(r.current_price),
    eval_amount: toFiniteNumber(r.eval_amount),
    pnl_amount: toFiniteNumber(r.pnl_amount),
    pnl_rate_pct: toFiniteNumber(r.pnl_rate_pct),
    buy_weight_pct: toFiniteNumber(r.buy_weight_pct),
    market_weight_pct: toFiniteNumber(r.market_weight_pct),
    price_asof: typeof r.price_asof === "string" ? r.price_asof : null,
    price_source: typeof r.price_source === "string" ? r.price_source : null,
    action,
    reason,
  };
}

function isPriced(rec: NormRec): boolean {
  return rec.current_price !== null && rec.current_price > 0;
}

function isCalcAvailable(rec: NormRec): boolean {
  return (
    isPriced(rec) &&
    rec.eval_amount !== null &&
    rec.eval_amount > 0 &&
    rec.invested_amount !== null &&
    rec.invested_amount > 0
  );
}

function rowKey(rec: NormRec): string {
  // 지시문: source_index + ticker + account_group + avg_buy_price.
  // avg_buy_price 누락 시 "?" 토큰으로 대체 (동일 종목 다중 행 충돌 방지).
  const avg =
    rec.avg_buy_price !== null && rec.avg_buy_price !== undefined
      ? rec.avg_buy_price
      : "?";
  return `${rec.source_index}|${rec.ticker}|${rec.account_group}|${avg}`;
}

// ─── 요약 계산 ────────────────────────────────────────────────

type Summary = {
  total_count: number;
  priced_count: number;
  unpriced_count: number;
  calc_available_count: number;
  calc_missing_count: number;
  total_invested: number;
  priced_invested: number;
  priced_eval: number | null;
  priced_pnl: number | null;
  priced_pnl_rate_pct: number | null;
};

type AccountSummary = Summary & { account_group: string };

function computeSummaryFor(recs: NormRec[]): Summary {
  const total_count = recs.length;
  const priced = recs.filter(isPriced);
  const calc = priced.filter(isCalcAvailable);

  let total_invested = 0;
  for (const r of recs) {
    if (r.invested_amount !== null) total_invested += r.invested_amount;
  }

  let calc_invested = 0;
  let calc_eval = 0;
  for (const r of calc) {
    calc_invested += r.invested_amount as number;
    calc_eval += r.eval_amount as number;
  }

  const priced_pnl = calc.length > 0 ? calc_eval - calc_invested : null;
  const priced_pnl_rate_pct =
    calc.length > 0 && calc_invested > 0 && priced_pnl !== null
      ? (priced_pnl / calc_invested) * 100.0
      : null;

  return {
    total_count,
    priced_count: priced.length,
    unpriced_count: total_count - priced.length,
    calc_available_count: calc.length,
    calc_missing_count: priced.length - calc.length,
    total_invested,
    priced_invested: calc_invested,
    priced_eval: calc.length > 0 ? calc_eval : null,
    priced_pnl,
    priced_pnl_rate_pct,
  };
}

function groupByAccount(recs: NormRec[]): AccountSummary[] {
  const order: string[] = [];
  const buckets: Record<string, NormRec[]> = {};
  for (const r of recs) {
    if (!(r.account_group in buckets)) {
      buckets[r.account_group] = [];
      order.push(r.account_group);
    }
    buckets[r.account_group].push(r);
  }
  return order.map((ag) => ({
    account_group: ag,
    ...computeSummaryFor(buckets[ag]),
  }));
}

// ─── compact 렌더링 컴포넌트 ────────────────────────────────────

function OverallSummaryCard({ summary }: { summary: Summary }) {
  const calcBasis =
    summary.calc_available_count > 0
      ? `(평가 계산 ${summary.calc_available_count}개 기준)`
      : "";
  const hasUnpriced =
    summary.unpriced_count > 0 || summary.calc_missing_count > 0;

  return (
    <div className="summary-card">
      <div className="summary-card-title">전체 요약</div>
      <div className="summary-grid">
        <SummaryItem label="보유 종목" value={`${summary.total_count}개`} />
        <SummaryItem label="시세 확인" value={`${summary.priced_count}개`} />
        <SummaryItem label="시세 미확인" value={`${summary.unpriced_count}개`} />
        {summary.calc_missing_count > 0 ? (
          <SummaryItem
            label="계산 정보 부족"
            value={`${summary.calc_missing_count}개`}
          />
        ) : null}
        <SummaryItem
          label="총 매입금액"
          value={fmtMoney(summary.total_invested) ?? "-"}
        />
        {summary.calc_available_count > 0 ? (
          <>
            <SummaryItem
              label={`평가금액 ${calcBasis}`}
              value={fmtMoney(summary.priced_eval) ?? "-"}
            />
            <SummaryItem
              label={`평가손익 ${calcBasis}`}
              value={fmtSignedMoney(summary.priced_pnl) ?? "-"}
              valueClass={pnlClass(summary.priced_pnl)}
            />
            <SummaryItem
              label={`평가수익률 ${calcBasis}`}
              value={fmtSignedPct(summary.priced_pnl_rate_pct) ?? "-"}
              valueClass={pnlClass(summary.priced_pnl_rate_pct)}
            />
          </>
        ) : (
          <SummaryItem label="평가금액/손익/수익률" value="계산 불가" />
        )}
      </div>
      {hasUnpriced ? (
        <div className="summary-warning">
          ⚠ 시세 미확인 또는 계산 정보 부족 종목이 있습니다 — 평가금액/손익/수익률은 평가
          계산 가능 종목 기준입니다.
        </div>
      ) : null}
    </div>
  );
}

function AccountSummaryCards({ summaries }: { summaries: AccountSummary[] }) {
  if (summaries.length === 0) return null;
  return (
    <div className="account-summary">
      <div className="summary-card-title">계좌별 요약</div>
      <ul className="account-summary-list">
        {summaries.map((s) => {
          const calcBasis =
            s.calc_available_count > 0
              ? `(평가 계산 ${s.calc_available_count}개 기준)`
              : "";
          const noCalc = s.calc_available_count === 0;
          return (
            <li className="account-summary-item" key={s.account_group}>
              <div className="account-summary-header">
                <span className="account-tag">{s.account_group}</span>
                <span className="account-counts">
                  {s.total_count}개 · 시세 확인 {s.priced_count}개
                  {s.unpriced_count > 0 ? ` · 미확인 ${s.unpriced_count}개` : ""}
                  {s.calc_missing_count > 0
                    ? ` · 계산 정보 부족 ${s.calc_missing_count}개`
                    : ""}
                </span>
              </div>
              <div className="account-summary-body">
                <KV label="총 매입금액" value={fmtMoney(s.total_invested) ?? "-"} />
                {noCalc ? (
                  <KV label="평가금액/손익/수익률" value="계산 불가" />
                ) : (
                  <>
                    <KV
                      label={`평가금액 ${calcBasis}`}
                      value={fmtMoney(s.priced_eval) ?? "-"}
                    />
                    <KV
                      label={`평가손익 ${calcBasis}`}
                      value={fmtSignedMoney(s.priced_pnl) ?? "-"}
                      valueClass={pnlClass(s.priced_pnl)}
                    />
                    <KV
                      label={`평가수익률 ${calcBasis}`}
                      value={fmtSignedPct(s.priced_pnl_rate_pct) ?? "-"}
                      valueClass={pnlClass(s.priced_pnl_rate_pct)}
                    />
                  </>
                )}
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function CompactHoldingsTable({
  recs,
  expanded,
  onToggle,
}: {
  recs: NormRec[];
  expanded: Set<string>;
  onToggle: (k: string) => void;
}) {
  return (
    <div className="compact-table-wrapper">
      <table className="compact-table">
        <thead>
          <tr>
            <th></th>
            <th>계좌</th>
            <th>종목</th>
            <th>손익</th>
            <th>시장비중</th>
            <th>판단</th>
            <th>상태</th>
          </tr>
        </thead>
        <tbody>
          {recs.map((rec) => {
            const k = rowKey(rec);
            const open = expanded.has(k);
            const nm =
              rec.name && rec.name !== rec.ticker
                ? `${rec.name} (${rec.ticker})`
                : rec.ticker || "(종목 미상)";
            const priced = isPriced(rec);
            const calcOK = isCalcAvailable(rec);
            const pnlText = fmtSignedMoney(rec.pnl_amount);
            const pnlRateText = fmtSignedPct(rec.pnl_rate_pct);
            const mwText = fmtPct(rec.market_weight_pct);

            let pnlCell: React.ReactNode;
            if (calcOK && pnlText && pnlRateText) {
              pnlCell = (
                <span className={pnlClass(rec.pnl_amount)}>
                  {pnlText} / {pnlRateText}
                </span>
              );
            } else if (!priced) {
              pnlCell = <span className="muted">시세 미확인</span>;
            } else {
              pnlCell = <span className="muted">계산 정보 부족</span>;
            }

            const mwCell = mwText ?? <span className="muted">시세 미확인</span>;

            const stateLabel = !priced
              ? "[시세 미확인]"
              : !calcOK
                ? "[계산 정보 부족]"
                : "정상";

            return (
              <CompactRow
                key={k}
                rowKey={k}
                open={open}
                onToggle={onToggle}
                tagAccount={rec.account_group}
                nameLabel={nm}
                pnlCell={pnlCell}
                marketWeightCell={mwCell}
                actionLabel={rec.action || "-"}
                stateLabel={stateLabel}
                detail={<DetailRowFields rec={rec} />}
              />
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function CompactRow({
  rowKey: k,
  open,
  onToggle,
  tagAccount,
  nameLabel,
  pnlCell,
  marketWeightCell,
  actionLabel,
  stateLabel,
  detail,
}: {
  rowKey: string;
  open: boolean;
  onToggle: (k: string) => void;
  tagAccount: string;
  nameLabel: string;
  pnlCell: React.ReactNode;
  marketWeightCell: React.ReactNode;
  actionLabel: string;
  stateLabel: string;
  detail: React.ReactNode;
}) {
  const handleToggle = () => onToggle(k);
  return (
    <>
      <tr className="compact-row" onClick={handleToggle}>
        <td className="toggle-cell">
          <button
            type="button"
            className="toggle-btn"
            aria-expanded={open}
            aria-label={open ? "상세 접기" : "상세 펼치기"}
            onClick={(e) => {
              e.stopPropagation();
              handleToggle();
            }}
          >
            {open ? "▼" : "▶"}
          </button>
        </td>
        <td>
          <span className="account-tag">{tagAccount}</span>
        </td>
        <td className="ticker-cell">{nameLabel}</td>
        <td className="num">{pnlCell}</td>
        <td className="num">{marketWeightCell}</td>
        <td>{actionLabel}</td>
        <td className={stateLabel === "정상" ? "muted" : ""}>{stateLabel}</td>
      </tr>
      {open ? (
        <tr className="compact-row-detail">
          <td></td>
          <td colSpan={6}>{detail}</td>
        </tr>
      ) : null}
    </>
  );
}

function DetailRowFields({ rec }: { rec: NormRec }) {
  const lines: Array<[string, string]> = [];
  if (rec.quantity !== null)
    lines.push(["수량", rec.quantity.toLocaleString("ko-KR")]);
  const avg = fmtMoney(rec.avg_buy_price);
  if (avg) lines.push(["평균 매입단가", avg]);
  const inv = fmtMoney(rec.invested_amount);
  if (inv) lines.push(["매입금액", inv]);
  const bw = fmtPct(rec.buy_weight_pct);
  if (bw) lines.push(["매입비중", bw]);
  const cur = fmtMoney(rec.current_price);
  if (cur) lines.push(["현재가", cur]);
  const ev = fmtMoney(rec.eval_amount);
  if (ev) lines.push(["평가금액", ev]);
  if (rec.price_asof) lines.push(["가격 기준시각", rec.price_asof]);
  if (rec.price_source) lines.push(["데이터 출처", rec.price_source]);
  if (rec.reason) lines.push(["사유", rec.reason]);
  return (
    <ul className="detail-fields">
      {lines.map(([k, v]) => (
        <li key={k}>
          <span className="k">{k}</span>
          <span className="v">{v}</span>
        </li>
      ))}
    </ul>
  );
}

// ─── 작은 표시 컴포넌트 ─────────────────────────────────────────

function SummaryItem({
  label,
  value,
  valueClass,
}: {
  label: string;
  value: string;
  valueClass?: string;
}) {
  return (
    <div className="summary-item">
      <div className="summary-item-label">{label}</div>
      <div className={`summary-item-value ${valueClass ?? ""}`}>{value}</div>
    </div>
  );
}

function KV({
  label,
  value,
  valueClass,
}: {
  label: string;
  value: string;
  valueClass?: string;
}) {
  return (
    <div className="kv-row">
      <span className="k">{label}</span>
      <span className={`v ${valueClass ?? ""}`}>{value}</span>
    </div>
  );
}

// ─── Step 2D — 승인 초안 영역 (preview 우선 + 전체 요약 기본 + 근거 데이터 접힘) ───
//
// 표시 정책:
// 1. 최신 run + message_text 있음 → preview block + 전체 요약(기본) + 근거 데이터(접힘)
// 2. 과거 run + message_text 없음 + holdings draft → 정적 안내 문구 + 전체 요약(기본) + 근거 데이터(펼침)
// 3. 비-holdings(샘플) draft → 기존처럼 raw recommendations 한 줄 표시 (preview 없음)
// 4. 빈 payload → "초안 본문이 없습니다" 안내
//
// 프론트엔드는 message_text 를 절대 조립/파싱하지 않는다. 백엔드가 내려준 원본만 그대로 렌더링.

const LEGACY_FALLBACK_NOTICE =
  "이 과거 초안은 전송 메시지 미리보기를 지원하지 않습니다. " +
  "아래 근거 데이터에서 초안 내용을 확인하세요.";

function MessagePreview({ messageText }: { messageText: string }) {
  return (
    <div className="preview-block">
      <div className="preview-header">전송 메시지 미리보기</div>
      <pre className="preview-body">{messageText}</pre>
    </div>
  );
}

function LegacyFallback() {
  return <div className="message info">{LEGACY_FALLBACK_NOTICE}</div>;
}

function EvidenceDetails({
  recs,
  defaultOpen,
  momentumBundle,
}: {
  recs: NormRec[];
  defaultOpen: boolean;
  momentumBundle?: ReturnType<typeof pickMomentumCandidates>;
}) {
  return (
    <details className="evidence-details" open={defaultOpen}>
      <summary>근거 데이터 펼쳐보기 (계좌별 요약 + 보유 종목 표 + 모멘텀 후보 상세)</summary>
      <div className="evidence-body">
        <AccountSummaryCards summaries={groupByAccount(recs)} />
        <CompactHoldingsTableStandalone recs={recs} />
        {momentumBundle ? <MomentumCandidatesSection bundle={momentumBundle} /> : null}
      </div>
    </details>
  );
}

// CompactHoldingsTable 은 기존에 expanded/onToggle 을 prop 으로 받음.
// 근거 데이터 펼침 안에서 행별 상세 펼침 상태를 별도로 보존하려면 자기 상태를 가져야 하므로
// wrapper 를 둔다 (기존 컴포넌트 재사용).
function CompactHoldingsTableStandalone({ recs }: { recs: NormRec[] }) {
  const expandKeys = useMemo(() => recs.map((r) => rowKey(r)), [recs]);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  useEffect(() => {
    setExpanded((prev) => {
      const valid = new Set(expandKeys);
      const next = new Set<string>();
      for (const k of prev) if (valid.has(k)) next.add(k);
      return next;
    });
  }, [expandKeys]);

  const toggle = useCallback((k: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(k)) next.delete(k);
      else next.add(k);
      return next;
    });
  }, []);

  return <CompactHoldingsTable recs={recs} expanded={expanded} onToggle={toggle} />;
}

// Step 3: draft_payload.factor_signals 에서 portfolio scope 1개 추출.
// 종목별 signal 은 기본 영역에 표시하지 않는다 (Top N 정책 금지).
function pickPortfolioFactorSignal(
  payload: Record<string, unknown>,
): {
  factor_name: string;
  is_available: boolean;
  reason_text: string | null;
  fallback_text: string | null;
} | null {
  const fs = payload.factor_signals;
  if (!Array.isArray(fs)) return null;
  for (const sig of fs) {
    if (
      sig &&
      typeof sig === "object" &&
      (sig as Record<string, unknown>).scope === "portfolio"
    ) {
      const s = sig as Record<string, unknown>;
      return {
        factor_name:
          typeof s.factor_name === "string" ? s.factor_name : "보유 비중 영향",
        is_available: Boolean(s.is_available),
        reason_text: typeof s.reason_text === "string" ? s.reason_text : null,
        fallback_text:
          typeof s.fallback_text === "string" ? s.fallback_text : null,
      };
    }
  }
  return null;
}

// Step 5B: draft_payload.momentum_result.summary 에서 1줄 추출.
// 전체 후보 순위는 기본 영역에 표시하지 않는다 (Top N 정책 금지). 후보 상세는
// EvidenceDetails 안에 별도 섹션으로 두고 기본 접힘.
function pickMomentumBullet(
  payload: Record<string, unknown>,
): { label: string; text: string } | null {
  const mr = payload.momentum_result;
  if (!mr || typeof mr !== "object") return null;
  const summary = (mr as Record<string, unknown>).summary;
  if (!summary || typeof summary !== "object") return null;
  const s = summary as Record<string, unknown>;
  const top = s.top_candidate;
  let text: unknown;
  if (top && typeof top === "object") {
    text = (top as Record<string, unknown>).reason_text;
  }
  if (typeof text !== "string" || text.length === 0) {
    text = s.summary_reason_text;
  }
  if (typeof text !== "string" || text.length === 0) return null;
  return { label: "모멘텀 점검", text };
}

function pickMomentumCandidates(
  payload: Record<string, unknown>,
): { items: Array<Record<string, unknown>>; mode: string; engine: string } | null {
  const mr = payload.momentum_result;
  if (!mr || typeof mr !== "object") return null;
  const m = mr as Record<string, unknown>;
  const cands = m.candidates;
  if (!Array.isArray(cands) || cands.length === 0) return null;
  return {
    items: cands as Array<Record<string, unknown>>,
    mode: typeof m.mode === "string" ? m.mode : "holdings",
    engine: typeof m.engine_id === "string" ? m.engine_id : "",
  };
}

function JudgmentReasonSection({
  signal,
  momentumBullet,
}: {
  signal: ReturnType<typeof pickPortfolioFactorSignal>;
  momentumBullet: ReturnType<typeof pickMomentumBullet>;
}) {
  // 두 bullet 중 하나라도 있어야 섹션을 그린다 (헤더 중복 방지 — 백엔드와 동일 정책).
  const factorText = signal
    ? signal.is_available
      ? signal.reason_text
      : signal.fallback_text
    : null;
  const hasFactor = signal !== null && typeof factorText === "string" && factorText.length > 0;
  const hasMomentum = momentumBullet !== null;
  if (!hasFactor && !hasMomentum) return null;

  return (
    <div className="reason-section">
      <div className="reason-section-title">판단 사유</div>
      <ul className="reason-list">
        {hasFactor && signal ? (
          <li>
            <span className="reason-name">{signal.factor_name}</span>
            <span className="reason-text">{factorText as string}</span>
          </li>
        ) : null}
        {hasMomentum && momentumBullet ? (
          <li>
            <span className="reason-name">{momentumBullet.label}</span>
            <span className="reason-text">{momentumBullet.text}</span>
          </li>
        ) : null}
      </ul>
    </div>
  );
}

function MomentumCandidatesSection({
  bundle,
}: {
  bundle: ReturnType<typeof pickMomentumCandidates>;
}) {
  if (bundle === null) return null;
  const { items, mode } = bundle;
  return (
    <div className="momentum-candidates" style={{ marginTop: 12 }}>
      <div className="reason-section-title">
        모멘텀 점검 후보 상세 (mode: {mode}, placeholder 산식 — 최종 투자 판단 산식이 아님)
      </div>
      <ul className="reason-list">
        {items.map((c) => {
          const ticker = typeof c.ticker === "string" ? c.ticker : "";
          const name = typeof c.name === "string" ? c.name : ticker;
          const ag = typeof c.account_group === "string" ? c.account_group : "";
          const rank = typeof c.rank === "number" ? c.rank : null;
          const sr = (c.score_result as Record<string, unknown>) ?? {};
          const isScored = Boolean(sr.is_scored);
          const score = typeof sr.score_value === "number" ? sr.score_value : null;
          const unit = typeof sr.score_unit === "string" ? sr.score_unit : "";
          const reason =
            typeof c.reason_text === "string"
              ? c.reason_text
              : typeof c.exclusion_reason === "string"
                ? c.exclusion_reason
                : "";
          const headParts: string[] = [];
          if (rank !== null) headParts.push(`#${rank}`);
          if (ag) headParts.push(`[${ag}]`);
          headParts.push(name);
          if (ticker && ticker !== name) headParts.push(`(${ticker})`);
          const head = headParts.join(" ");
          const valueText = isScored && score !== null ? `${score}${unit}` : "—";
          return (
            <li key={String(c.candidate_id ?? `${ticker}-${ag}`)}>
              <span className="reason-name">{head}</span>
              <span className="reason-text">
                {valueText}
                {reason ? ` · ${reason}` : ""}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function ApprovalDraftBody({ run }: { run: Run }) {
  const payload = run.draft_payload ?? {};
  const recs = (payload as Record<string, unknown>).recommendations;
  const note = (payload as Record<string, unknown>).note;
  const messageText =
    typeof run.message_text === "string" && run.message_text.length > 0
      ? run.message_text
      : null;
  const portfolioSignal = pickPortfolioFactorSignal(payload as Record<string, unknown>);
  const momentumBullet = pickMomentumBullet(payload as Record<string, unknown>);
  const momentumBundle = pickMomentumCandidates(payload as Record<string, unknown>);

  const hasRecs = Array.isArray(recs) && recs.length > 0;
  const hasNote = typeof note === "string" && note.length > 0;
  const recsList = hasRecs
    ? (recs as Array<Record<string, unknown>>)
    : ([] as Array<Record<string, unknown>>);
  const isHoldings =
    recsList.length > 0 &&
    typeof recsList[0] === "object" &&
    recsList[0] !== null &&
    isHoldingsRec(recsList[0]);

  // 빈 payload — 안내만
  if (!hasRecs && !hasNote && !messageText) {
    return <div className="message info">초안 본문이 없습니다.</div>;
  }

  // 비-holdings 샘플 초안 — preview 미지원. raw 는 기본 접힘 details 안으로만 노출.
  // Step 2D AC13: raw JSON 은 기본 노출되지 않는다.
  if (hasRecs && !isHoldings) {
    return (
      <div>
        <LegacyFallback />
        {hasNote ? (
          <div className="summary-text" style={{ marginTop: 10 }}>
            {note as string}
          </div>
        ) : null}
        <details className="evidence-details" style={{ marginTop: 12 }}>
          <summary>근거 데이터 펼쳐보기 (샘플 recommendations 원본)</summary>
          <ul className="reco-list" style={{ marginTop: 10 }}>
            {recsList.map((r, idx) => (
              <li key={idx}>
                <code>{JSON.stringify(r)}</code>
              </li>
            ))}
          </ul>
        </details>
      </div>
    );
  }

  // holdings draft — preview / 정적 안내 + 전체 요약 + 판단 사유 + 근거 데이터(접힘/펼침)
  const normRecs = recsList.map((r, idx) => normalizeRec(r, idx));
  const summary = computeSummaryFor(normRecs);
  const evidenceDefaultOpen = messageText === null;

  return (
    <div>
      {messageText !== null ? (
        <MessagePreview messageText={messageText} />
      ) : (
        <LegacyFallback />
      )}
      {hasNote ? (
        <div className="summary-text" style={{ marginTop: 10 }}>
          {note as string}
        </div>
      ) : null}
      <div style={{ marginTop: 12 }}>
        <OverallSummaryCard summary={summary} />
      </div>
      <JudgmentReasonSection signal={portfolioSignal} momentumBullet={momentumBullet} />
      <EvidenceDetails
        recs={normRecs}
        defaultOpen={evidenceDefaultOpen}
        momentumBundle={momentumBundle}
      />
    </div>
  );
}

interface Props {
  run: Run;
  setRun: (run: Run | null) => void;
  loading: boolean;
  setLoading: (b: boolean) => void;
  errorMsg: string | null;
  setErrorMsg: (s: string | null) => void;
}

export default function RunPanel({
  run,
  setRun,
  loading,
  setLoading,
  errorMsg,
  setErrorMsg,
}: Props) {
  const pollTickRef = useRef<number>(0);

  // DELIVERING 만 polling. terminal 도달 시 즉시 중단.
  useEffect(() => {
    if (run.status !== "DELIVERING") {
      pollTickRef.current = 0;
      return;
    }
    const id = window.setInterval(async () => {
      pollTickRef.current += 1;
      if (pollTickRef.current > MAX_POLL_TICKS) {
        window.clearInterval(id);
        setErrorMsg(
          "DELIVERING 상태가 너무 오래 지속됩니다. '상태 새로고침' 을 눌러 확인해 주세요."
        );
        return;
      }
      try {
        const latest = await fetchRun(run.run_id);
        setRun(latest);
      } catch (e) {
        setErrorMsg(describeApiError(e));
      }
    }, POLL_INTERVAL_MS);
    return () => window.clearInterval(id);
  }, [run, setRun, setErrorMsg]);

  const onApprove = useCallback(async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const next = await approveRun(run.run_id);
      setRun(next);
    } catch (e) {
      setErrorMsg(describeApiError(e));
    } finally {
      setLoading(false);
    }
  }, [run, setRun, setLoading, setErrorMsg]);

  const onReject = useCallback(async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const next = await rejectRun(run.run_id);
      setRun(next);
    } catch (e) {
      setErrorMsg(describeApiError(e));
    } finally {
      setLoading(false);
    }
  }, [run, setRun, setLoading, setErrorMsg]);

  const onRefresh = useCallback(async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const latest = await fetchRun(run.run_id);
      setRun(latest);
    } catch (e) {
      setErrorMsg(describeApiError(e));
    } finally {
      setLoading(false);
    }
  }, [run, setRun, setLoading, setErrorMsg]);

  const onReset = useCallback(() => {
    setRun(null);
    setErrorMsg(null);
    pollTickRef.current = 0;
  }, [setRun, setErrorMsg]);

  const canApproveOrReject = run.status === "PENDING_APPROVAL";
  const showTerminalReset = isTerminal(run.status);

  return (
    <>
      {errorMsg ? <div className="message error">{errorMsg}</div> : null}

      <div className="card">
        <h2>2. 현재 진행 상황</h2>
        <div className="status-row">
          <span className={`status-badge status-${run.status}`}>
            {humanLabel(run.status)}
          </span>
          <span className="kv">
            <span className="k">run_id</span>
            <span className="v">
              <code>{run.run_id}</code>
            </span>
          </span>
          <span className="kv">
            <span className="k">asof</span>
            <span className="v">{run.asof}</span>
          </span>
        </div>
        <div className="helper">
          백엔드 status: <code>{run.status}</code>
          {run.status === "DELIVERING" ? " (자동 상태 확인 중, 약 12초 간격)" : ""}
        </div>
      </div>

      <div className="card">
        <h2>3. 승인 초안 (전송 메시지 미리보기)</h2>
        <ApprovalDraftBody run={run} />
      </div>

      <div className="card">
        <h2>4. 다음 행동</h2>
        {canApproveOrReject ? (
          <div className="btn-row">
            <button onClick={onApprove} disabled={loading} type="button">
              승인 (Approve)
            </button>
            <button
              className="reject"
              onClick={onReject}
              disabled={loading}
              type="button"
            >
              거절 (Reject)
            </button>
          </div>
        ) : (
          <div className="message info">
            {run.status === "DELIVERING"
              ? "외부 전달이 진행 중입니다. 잠시 후 상태가 자동으로 갱신됩니다."
              : "이 run 은 종결 상태입니다. 새 시도는 새 run_id 로만 가능합니다."}
          </div>
        )}
        <div
          className="btn-row"
          style={{ marginTop: canApproveOrReject ? 12 : 0 }}
        >
          <button
            className="reject"
            onClick={onRefresh}
            disabled={loading}
            type="button"
          >
            상태 새로고침
          </button>
          {showTerminalReset ? (
            <button onClick={onReset} disabled={loading} type="button">
              새 초안 시작
            </button>
          ) : null}
        </div>
      </div>
    </>
  );
}
