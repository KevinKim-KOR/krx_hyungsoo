"use client";

// POC2 Step 5D-2 Final — HoldingsClient.tsx 의 시세평가 compact UI 영역 분리.
// 분리 전후 렌더링 결과 / 문구 / 배치 / 상세 펼침 상태 / 데이터 처리 모두 동일.
//
// 분리 목적: KS-10 트리거 (HoldingsClient.tsx 906라인) 해소.
// 분리 대상:
//   EnrichedSection (default export) + 내부 자식 컴포넌트
//     OverallSummaryCard / AccountSummaryCards / AccountSummaryRow /
//     CompactHoldingsTable / CompactRow / DetailRowFields / SummaryItem / KV
//   + 로컬 helpers (Summary / AccountSummary / isPriced / isCalcAvailable /
//                  computeSummaryFor / groupByAccount / rowKey)
//
// 책임 경계:
//   본 파일은 EnrichedHolding 배열을 입력받아 compact 평가 UI 만 그린다.
//   입력 폼 / 시세 갱신 / 저장 / 초안 생성 액션은 HoldingsClient.tsx 에 잔존.

import React, { useCallback, useEffect, useMemo, useState } from "react";

import { type EnrichedHolding } from "@/lib/api";
import {
  fmtMoney,
  fmtPct,
  fmtSignedMoney,
  fmtSignedPct,
  pnlClass,
} from "@/lib/holdings_view";

// ─── 로컬 타입 (EnrichedHolding 기반) ───────────────────────────

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

// ─── 로컬 helpers (EnrichedHolding 기반) ────────────────────────

function isPriced(it: EnrichedHolding): boolean {
  return (
    it.current_price !== null &&
    it.current_price !== undefined &&
    Number.isFinite(it.current_price) &&
    (it.current_price as number) > 0
  );
}

function isCalcAvailable(it: EnrichedHolding): boolean {
  if (!isPriced(it)) return false;
  const ev = it.eval_amount;
  const inv = it.invested_amount;
  return (
    ev !== null &&
    ev !== undefined &&
    Number.isFinite(ev) &&
    ev > 0 &&
    Number.isFinite(inv) &&
    inv > 0
  );
}

function computeSummaryFor(items: EnrichedHolding[]): Summary {
  const total_count = items.length;
  const priced = items.filter(isPriced);
  const calc = priced.filter(isCalcAvailable);

  let total_invested = 0;
  for (const it of items) {
    if (Number.isFinite(it.invested_amount)) total_invested += it.invested_amount;
  }

  let calc_invested = 0;
  let calc_eval = 0;
  for (const it of calc) {
    calc_invested += it.invested_amount;
    calc_eval += it.eval_amount as number;
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

function groupByAccount(items: EnrichedHolding[]): AccountSummary[] {
  // 첫 등장 순서(insertion order) 유지.
  const order: string[] = [];
  const buckets: Record<string, EnrichedHolding[]> = {};
  for (const it of items) {
    const ag = it.account_group ?? "일반";
    if (!(ag in buckets)) {
      buckets[ag] = [];
      order.push(ag);
    }
    buckets[ag].push(it);
  }
  return order.map((ag) => ({
    account_group: ag,
    ...computeSummaryFor(buckets[ag]),
  }));
}

function rowKey(it: EnrichedHolding, fallbackIdx: number): string {
  // 지시문 [UI 식별자 / React Key 정책]:
  // source_index + ticker + account_group + avg_buy_price 조합.
  // source_index 누락(과거 payload) 시 fallbackIdx 사용.
  const si =
    it.source_index !== undefined && it.source_index !== null
      ? it.source_index
      : fallbackIdx;
  const ag = it.account_group ?? "일반";
  return `${si}|${it.ticker}|${ag}|${it.avg_buy_price}`;
}

// ─── 메인 컴포넌트 ────────────────────────────────────────────

interface EnrichedSectionProps {
  items: EnrichedHolding[];
}

export default function EnrichedSection({ items }: EnrichedSectionProps) {
  const summary = useMemo(() => computeSummaryFor(items), [items]);
  const accountSummaries = useMemo(() => groupByAccount(items), [items]);
  const hasAnyPrice = summary.priced_count > 0;
  const expandKeys = useMemo(
    () => items.map((it, idx) => rowKey(it, idx)),
    [items]
  );
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  // items 가 갱신되어도 동일 key 의 펼침 상태는 유지. 키 자체가 사라지면 해당 항목만 정리.
  useEffect(() => {
    setExpanded((prev) => {
      const valid = new Set(expandKeys);
      const next = new Set<string>();
      for (const k of prev) {
        if (valid.has(k)) next.add(k);
      }
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

  return (
    <div style={{ marginTop: 24 }}>
      <h3 style={{ fontSize: 14, margin: "0 0 8px 0" }}>보유 종목 시세 평가</h3>
      <p className="helper" style={{ marginTop: 0 }}>
        {hasAnyPrice
          ? "캐시된 Naver 시세 기준 평가. 갱신은 위의 [시세 갱신] 버튼."
          : "아직 시세가 캐시되지 않았습니다. [시세 갱신] 버튼으로 1회 조회하세요."}
      </p>

      <OverallSummaryCard summary={summary} />
      <AccountSummaryCards summaries={accountSummaries} />
      <CompactHoldingsTable
        items={items}
        expanded={expanded}
        onToggle={toggle}
      />
    </div>
  );
}

// ─── 전체 요약 카드 ─────────────────────────────────────────────

function OverallSummaryCard({ summary }: { summary: Summary }) {
  const { total_count, priced_count, unpriced_count, calc_available_count, calc_missing_count } =
    summary;
  const hasUnpriced = unpriced_count > 0 || calc_missing_count > 0;
  const calcBasis =
    calc_available_count > 0 ? `(평가 계산 ${calc_available_count}개 기준)` : "";

  return (
    <div className="summary-card">
      <div className="summary-card-title">전체 요약</div>
      <div className="summary-grid">
        <SummaryItem label="보유 종목" value={`${total_count}개`} />
        <SummaryItem label="시세 확인" value={`${priced_count}개`} />
        <SummaryItem label="시세 미확인" value={`${unpriced_count}개`} />
        {calc_missing_count > 0 ? (
          <SummaryItem label="계산 정보 부족" value={`${calc_missing_count}개`} />
        ) : null}
        <SummaryItem label="총 매입금액" value={fmtMoney(summary.total_invested) ?? "-"} />
        {calc_available_count > 0 ? (
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

// ─── 계좌별 요약 카드 (compact rows) ───────────────────────────

function AccountSummaryCards({ summaries }: { summaries: AccountSummary[] }) {
  if (summaries.length === 0) return null;
  return (
    <div className="account-summary">
      <div className="summary-card-title">계좌별 요약</div>
      <ul className="account-summary-list">
        {summaries.map((s) => (
          <AccountSummaryRow key={s.account_group} summary={s} />
        ))}
      </ul>
    </div>
  );
}

function AccountSummaryRow({ summary }: { summary: AccountSummary }) {
  const calcBasis =
    summary.calc_available_count > 0
      ? `(평가 계산 ${summary.calc_available_count}개 기준)`
      : "";
  const noCalc = summary.calc_available_count === 0;

  return (
    <li className="account-summary-item">
      <div className="account-summary-header">
        <span className="account-tag">{summary.account_group}</span>
        <span className="account-counts">
          {summary.total_count}개 · 시세 확인 {summary.priced_count}개
          {summary.unpriced_count > 0 ? ` · 미확인 ${summary.unpriced_count}개` : ""}
          {summary.calc_missing_count > 0
            ? ` · 계산 정보 부족 ${summary.calc_missing_count}개`
            : ""}
        </span>
      </div>
      <div className="account-summary-body">
        <KV label="총 매입금액" value={fmtMoney(summary.total_invested) ?? "-"} />
        {noCalc ? (
          <KV label="평가금액/손익/수익률" value="계산 불가" />
        ) : (
          <>
            <KV
              label={`평가금액 ${calcBasis}`}
              value={fmtMoney(summary.priced_eval) ?? "-"}
            />
            <KV
              label={`평가손익 ${calcBasis}`}
              value={fmtSignedMoney(summary.priced_pnl) ?? "-"}
              valueClass={pnlClass(summary.priced_pnl)}
            />
            <KV
              label={`평가수익률 ${calcBasis}`}
              value={fmtSignedPct(summary.priced_pnl_rate_pct) ?? "-"}
              valueClass={pnlClass(summary.priced_pnl_rate_pct)}
            />
          </>
        )}
      </div>
    </li>
  );
}

// ─── compact holdings table ────────────────────────────────────

function CompactHoldingsTable({
  items,
  expanded,
  onToggle,
}: {
  items: EnrichedHolding[];
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
          {items.map((it, idx) => {
            const k = rowKey(it, idx);
            const open = expanded.has(k);
            const ag = it.account_group ?? "일반";
            const nm =
              it.name && it.name !== it.ticker
                ? `${it.name} (${it.ticker})`
                : it.ticker;

            const priced = isPriced(it);
            const calcOK = isCalcAvailable(it);
            const pnlText = fmtSignedMoney(it.pnl_amount);
            const pnlRateText = fmtSignedPct(it.pnl_rate_pct);
            const mwText = fmtPct(it.market_weight_pct);

            let pnlCell: React.ReactNode;
            if (calcOK && pnlText && pnlRateText) {
              pnlCell = (
                <span className={pnlClass(it.pnl_amount)}>
                  {pnlText} / {pnlRateText}
                </span>
              );
            } else if (!priced) {
              pnlCell = <span className="muted">시세 미확인</span>;
            } else {
              pnlCell = <span className="muted">계산 정보 부족</span>;
            }

            const mwCell = mwText ?? <span className="muted">시세 미확인</span>;

            const stateCell = !priced
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
                tagAccount={ag}
                nameLabel={nm}
                pnlCell={pnlCell}
                marketWeightCell={mwCell}
                // POC2 Step2C: 이번 단계 추천 로직 확장 금지 — holdings 평가는 항상 HOLD.
                actionLabel="HOLD"
                stateLabel={stateCell}
                detail={<DetailRowFields it={it} />}
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
        <td>{actionLabel || "-"}</td>
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

function DetailRowFields({ it }: { it: EnrichedHolding }) {
  const lines: Array<[string, string]> = [];
  if (Number.isFinite(it.quantity))
    lines.push(["수량", it.quantity.toLocaleString("ko-KR")]);
  const avg = fmtMoney(it.avg_buy_price);
  if (avg) lines.push(["평균 매입단가", avg]);
  const inv = fmtMoney(it.invested_amount);
  if (inv) lines.push(["매입금액", inv]);
  const bw = fmtPct(it.buy_weight_pct);
  if (bw) lines.push(["매입비중", bw]);
  const cur = fmtMoney(it.current_price);
  if (cur) lines.push(["현재가", cur]);
  const ev = fmtMoney(it.eval_amount);
  if (ev) lines.push(["평가금액", ev]);
  if (it.price_asof) lines.push(["가격 기준시각", it.price_asof]);
  if (it.price_source) lines.push(["데이터 출처", it.price_source]);
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
