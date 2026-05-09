"use client";

// POC2 Step 5D-2 Cleanup — RunPanel.tsx 의 근거 데이터 영역 책임 분리.
// 분리 전후 렌더링 결과 / 문구 / 배치 / 동작 / 접힘 기본 상태 / message_text 모두 동일.
//
// 정책 (Step2C/2D/5B 누적):
// - <details> 기본 접힘은 부모(ApprovalDraftBody)가 결정한다 (defaultOpen prop).
// - 본 영역에는 계좌별 요약 + 보유 종목 compact table + (있을 경우) 모멘텀 후보 상세가
//   순서대로 표시된다.
// - 종목별 상세 펼침은 컴포넌트 메모리 단위(Set)로 유지되며 polling 시 키 보존 정리만.

import { useCallback, useEffect, useMemo, useState } from "react";

import MomentumCandidatesSection, {
  pickMomentumCandidates,
} from "./MomentumCandidatesSection";
import {
  computeSummaryFor,
  fmtMoney,
  fmtPct,
  fmtSignedMoney,
  fmtSignedPct,
  isCalcAvailable,
  isPriced,
  pnlClass,
  rowKey,
  type AccountSummary,
  type NormRec,
} from "./RunPanel";


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

export default EvidenceDetails;
