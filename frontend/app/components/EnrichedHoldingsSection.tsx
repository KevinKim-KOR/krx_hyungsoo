"use client";

// POC2 Step 5D-2 — HoldingsClient.tsx 의 시세평가 UI 영역 분리(default export
//   EnrichedSection). 입력 폼/시세 갱신/저장/초안 액션은 HoldingsView·HoldingsManageView.
//
// POC3-08 증권사 스타일 개편: 기존 요약 카드 + compact 표를 다음으로 교체.
//   - HoldingsHero: 상단 큰 평가 배너(총 평가금액·평가손익). 기존 summary 재사용.
//   - AccountSection: 계좌순이면 계좌 소계 헤더로 묶고, 종목명/코드순이면 단일 섹션.
//   - HoldingRow: 종목 행 2단×2열(좌상 종목명+판단 · 우상 손익 · 좌하 티커/수량/비중 ·
//                 우하 매입가→현재가). 클릭 시 DetailRowFields 상세 펼침.
//   평가·계산·요약·정렬 로직은 무변경(sortHoldings/computeSummaryFor 그대로) — 표시만 교체.
//   손익 색은 앱 실제 pnlClass(수익=--ok 초록 / 손실=--danger 빨강) 재사용.
//   ※ 기존 .summary-card/.compact-table CSS 는 EvidenceDetails.tsx 가 여전히 사용.

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

// ─── POC3-08 정렬 (보유 현황 조회 순서) ──────────────────────────
//   기본·최우선 = 계좌순(증권사 계좌조회 순서). 표시 순서만 바꾼다(평가·계산 무변경).

export type HoldingsSortKey = "account" | "name" | "ticker";

// 계좌 그룹 표시 우선순위(사용자 확정: 증권사 계좌조회 순서).
//   목록에 없는 계좌(사용자 커스텀)는 뒤에 이름 가나다순.
const ACCOUNT_ORDER: ReadonlyArray<string> = [
  "일반",
  "ISA",
  "연금",
  "오픈뱅킹",
  "기타",
];

// 계좌 라벨 정규화 — 누락/빈 값은 "일반"(백엔드 normalize_account_group 과 동일 계약).
function normAccount(ag: string | null | undefined): string {
  const t = (ag ?? "").trim();
  return t === "" ? "일반" : t;
}

function accountRank(ag: string): number {
  const i = ACCOUNT_ORDER.indexOf(ag);
  // 목록에 없으면 뒤로(같은 큰 값), 그 안에서는 이름 비교로 안정 정렬.
  return i === -1 ? ACCOUNT_ORDER.length : i;
}

// 종목명 표시 라벨(정렬 키). 이름 없으면 ticker 로 대체(가나다에서 자연스럽게).
function nameKey(it: EnrichedHolding): string {
  return (it.name && it.name.trim() !== "" ? it.name : it.ticker).trim();
}

// ko 로케일 비교(가나다/영문 혼재 안정). 동률은 ticker 로 tie-break.
function compareByName(a: EnrichedHolding, b: EnrichedHolding): number {
  const c = nameKey(a).localeCompare(nameKey(b), "ko");
  return c !== 0 ? c : a.ticker.localeCompare(b.ticker);
}

function compareByTicker(a: EnrichedHolding, b: EnrichedHolding): number {
  return a.ticker.localeCompare(b.ticker);
}

// 정렬은 표시용 새 배열만 만든다(원본 items 불변 — expand key/평가 계약 보존).
export function sortHoldings(
  items: EnrichedHolding[],
  key: HoldingsSortKey
): EnrichedHolding[] {
  const arr = [...items];
  if (key === "ticker") {
    arr.sort(compareByTicker);
  } else if (key === "name") {
    arr.sort(compareByName);
  } else {
    // account: 계좌 우선순위 → 같은 계좌 안은 종목명 가나다.
    arr.sort((a, b) => {
      const ag = normAccount(a.account_group);
      const bg = normAccount(b.account_group);
      const ra = accountRank(ag);
      const rb = accountRank(bg);
      if (ra !== rb) return ra - rb;
      // 같은 우선순위(둘 다 커스텀 계좌 포함)면 계좌명 자체로 안정화.
      if (ag !== bg) return ag.localeCompare(bg, "ko");
      return compareByName(a, b);
    });
  }
  return arr;
}

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

// POC3-08: 계좌 태그에 계좌별 색(종목 관리 화면과 동일 체계).
//   알려진 계좌만 색 매핑(임의 입력이 클래스명 되는 것 방지).
const KNOWN_ACCOUNTS = new Set(["ISA", "오픈뱅킹", "연금"]);
function accountTagClass(ag: string): string {
  return KNOWN_ACCOUNTS.has(ag)
    ? `account-tag account-tag-${ag}`
    : "account-tag";
}

// POC3-08: 구성 막대용 계좌 색(태그 색 계열과 맞춤). 미매핑 계좌는 회청 계열.
const ACCOUNT_BAR_COLOR: Record<string, string> = {
  일반: "#94a3b8",
  ISA: "#4ba46e",
  연금: "#9b7ec8",
  오픈뱅킹: "#d99a4e",
  기타: "#b0b6bf",
};
function accountBarColor(ag: string): string {
  return ACCOUNT_BAR_COLOR[ag] ?? "#b0b6bf";
}

// 계좌 표시 우선순위(구성 막대 세그먼트 순서 = 계좌순 정렬과 동일).
const ACCOUNT_BAR_ORDER: ReadonlyArray<string> = [
  "일반",
  "ISA",
  "연금",
  "오픈뱅킹",
  "기타",
];
function accountBarRank(ag: string): number {
  const i = ACCOUNT_BAR_ORDER.indexOf(ag);
  return i === -1 ? ACCOUNT_BAR_ORDER.length : i;
}

// ─── 메인 컴포넌트 ────────────────────────────────────────────

interface EnrichedSectionProps {
  items: EnrichedHolding[];
}

export default function EnrichedSection({ items }: EnrichedSectionProps) {
  const summary = useMemo(() => computeSummaryFor(items), [items]);
  const accountSummaries = useMemo(() => groupByAccount(items), [items]);
  const hasAnyPrice = summary.priced_count > 0;

  // POC3-08: 정렬(조회 순서). 기본 = 계좌순. 표시 순서만 바꾼다.
  const [sortKey, setSortKey] = useState<HoldingsSortKey>("account");
  const sortedItems = useMemo(
    () => sortHoldings(items, sortKey),
    [items, sortKey]
  );

  // expand key 는 source_index 기반이라 표시 순서와 무관(정렬해도 펼침 유지).
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

  // POC3-08 증권사 스타일: 계좌순이면 계좌 섹션(소계 헤더)으로 묶고, 종목명/코드순이면
  //   계좌 헤더 없이 한 섹션으로(앞서 확정한 정렬 정책과 동일).
  const sections = useMemo<Section[]>(() => {
    if (sortKey !== "account") {
      return [{ account_group: null, items: sortedItems }];
    }
    // 이미 계좌순 정렬됐으므로 인접 그룹으로 자른다(계좌 우선순위 순서 유지).
    const out: Section[] = [];
    for (const it of sortedItems) {
      const ag = (it.account_group ?? "일반").trim() || "일반";
      const last = out[out.length - 1];
      if (last && last.account_group === ag) last.items.push(it);
      else out.push({ account_group: ag, items: [it] });
    }
    return out;
  }, [sortedItems, sortKey]);

  const accountSubtotal = useMemo(() => {
    const m: Record<string, AccountSummary> = {};
    for (const s of accountSummaries) m[s.account_group] = s;
    return m;
  }, [accountSummaries]);

  return (
    <div style={{ marginTop: 24 }}>
      <HoldingsHero summary={summary} accounts={accountSummaries} />

      <p className="helper" style={{ margin: "0 0 12px" }}>
        {hasAnyPrice
          ? "캐시된 Naver 시세 기준 평가. 갱신은 위의 [시세 갱신] 버튼."
          : "아직 시세가 캐시되지 않았습니다. [시세 갱신] 버튼으로 1회 조회하세요."}
      </p>

      {/* POC3-08: 정렬 컨트롤. 기본 계좌순(증권사 계좌조회 순서). */}
      <div className="holdings-sortbar">
        <span className="holdings-sortbar-label">정렬</span>
        <div className="holdings-sort-seg" role="group" aria-label="보유 종목 정렬 기준">
          {(
            [
              ["account", "계좌순"],
              ["name", "종목명순"],
              ["ticker", "종목코드순"],
            ] as ReadonlyArray<[HoldingsSortKey, string]>
          ).map(([key, label]) => (
            <button
              key={key}
              type="button"
              className={sortKey === key ? "on" : ""}
              aria-pressed={sortKey === key}
              onClick={() => setSortKey(key)}
            >
              {label}
            </button>
          ))}
        </div>
        {sortKey === "account" ? (
          <span className="holdings-sortbar-hint">
            계좌 순서: 일반 · ISA · 연금 · 오픈뱅킹 · 기타 (계좌 안은 종목명순)
          </span>
        ) : null}
      </div>

      {sections.map((sec, si) => (
        <AccountSection
          key={sec.account_group ?? `flat-${si}`}
          section={sec}
          subtotal={
            sec.account_group ? accountSubtotal[sec.account_group] : undefined
          }
          expanded={expanded}
          onToggle={toggle}
        />
      ))}
    </div>
  );
}

// ─── 증권사 스타일 상단 평가 배너 (POC3-08) ─────────────────────
//   전체 평가금액·손익을 큰 숫자로. 기존 summary 재사용(신규 계산 없음).

function HoldingsHero({
  summary,
  accounts,
}: {
  summary: Summary;
  accounts: AccountSummary[];
}) {
  const {
    total_count,
    priced_count,
    unpriced_count,
    calc_missing_count,
    priced_eval,
    priced_pnl,
    priced_pnl_rate_pct,
  } = summary;
  const hasUnpriced = unpriced_count > 0 || calc_missing_count > 0;

  return (
    <div className="hld-hero">
      <div className="hld-hero-top">
        <div className="hld-hero-eval">
          <div className="hld-hero-lbl">총 평가금액</div>
          <div className="hld-hero-amt">
            {priced_eval !== null ? (fmtMoney(priced_eval) ?? "-") : "계산 불가"}
          </div>
        </div>
        <div className="hld-hero-pnl">
          <div className="hld-hero-lbl">평가손익</div>
          <div className={`hld-hero-pamt ${pnlClass(priced_pnl)}`}>
            {priced_pnl !== null ? (fmtSignedMoney(priced_pnl) ?? "-") : "-"}
            {priced_pnl_rate_pct !== null ? (
              <span className="hld-hero-rate">
                {fmtSignedPct(priced_pnl_rate_pct)}
              </span>
            ) : null}
          </div>
        </div>
      </div>
      <div className="hld-hero-sub">
        <div className="hld-kv">
          <div className="k">총 매입금액</div>
          <div className="v">{fmtMoney(summary.total_invested) ?? "-"}</div>
        </div>
        <div className="hld-kv">
          <div className="k">보유 종목</div>
          <div className="v">{total_count}개</div>
        </div>
        <div className="hld-kv">
          <div className="k">시세 확인</div>
          <div className="v">{priced_count}개</div>
        </div>
      </div>

      <CompositionBar accounts={accounts} totalEval={priced_eval} />

      {hasUnpriced ? (
        <div className="hld-hero-warn">
          ⚠ 시세 미확인 또는 계산 정보 부족 종목이 있습니다 — 평가금액·손익·구성은
          평가 계산 가능 종목 기준입니다.
        </div>
      ) : null}
    </div>
  );
}

// ─── 계좌별 구성 막대 (POC3-08) ─────────────────────────────────
//   계좌별 평가금액(priced_eval) 비율을 가로 누적 막대로. 계좌순 세그먼트.
//   비율 기준 = 평가금액(개별 행 시장비중과 동일 기준). 계산 불가 계좌는 제외.

function CompositionBar({
  accounts,
  totalEval,
}: {
  accounts: AccountSummary[];
  totalEval: number | null;
}) {
  // 평가금액이 있는 계좌만, 계좌순으로.
  const segs = accounts
    .filter((a) => a.priced_eval !== null && (a.priced_eval as number) > 0)
    .map((a) => ({
      account_group: a.account_group,
      eval: a.priced_eval as number,
    }))
    .sort((x, y) => accountBarRank(x.account_group) - accountBarRank(y.account_group));

  const total =
    totalEval !== null && totalEval > 0
      ? totalEval
      : segs.reduce((s, x) => s + x.eval, 0);
  if (segs.length === 0 || total <= 0) return null;

  return (
    <div className="hld-comp">
      <div className="hld-comp-lbl">
        <span>계좌별 구성 (평가금액 기준)</span>
      </div>
      <div className="hld-comp-bar">
        {segs.map((s) => {
          const pct = (s.eval / total) * 100;
          return (
            <div
              key={s.account_group}
              className="hld-comp-seg"
              style={{
                width: `${pct}%`,
                background: accountBarColor(s.account_group),
              }}
              title={`${s.account_group} · ${pct.toLocaleString("ko-KR", {
                maximumFractionDigits: 1,
              })}%`}
            />
          );
        })}
      </div>
      <div className="hld-comp-legend">
        {segs.map((s) => {
          const pct = (s.eval / total) * 100;
          return (
            <span className="lg" key={s.account_group}>
              <span
                className="sw"
                style={{ background: accountBarColor(s.account_group) }}
              />
              {s.account_group}{" "}
              {pct.toLocaleString("ko-KR", { maximumFractionDigits: 1 })}%
            </span>
          );
        })}
      </div>
    </div>
  );
}

// ─── 계좌 섹션 (증권사 스타일, POC3-08) ─────────────────────────

type Section = { account_group: string | null; items: EnrichedHolding[] };

function AccountSection({
  section,
  subtotal,
  expanded,
  onToggle,
}: {
  section: Section;
  subtotal: AccountSummary | undefined;
  expanded: Set<string>;
  onToggle: (k: string) => void;
}) {
  return (
    <div className="hld-acct">
      {section.account_group ? (
        <div className="hld-acct-head">
          <span className={accountTagClass(section.account_group)}>
            {section.account_group}
          </span>
          <span className="hld-acct-cnt">{section.items.length}종목</span>
          {subtotal ? <AccountSubtotal summary={subtotal} /> : null}
        </div>
      ) : null}
      {section.items.map((it, idx) => (
        <HoldingRow
          key={rowKey(it, idx)}
          it={it}
          rk={rowKey(it, idx)}
          open={expanded.has(rowKey(it, idx))}
          onToggle={onToggle}
        />
      ))}
    </div>
  );
}

function AccountSubtotal({ summary }: { summary: AccountSummary }) {
  if (summary.calc_available_count === 0) {
    return <span className="hld-acct-sub muted">일부 시세 미확인</span>;
  }
  return (
    <span className="hld-acct-sub">
      평가손익{" "}
      <span className={`amt ${pnlClass(summary.priced_pnl)}`}>
        {fmtSignedMoney(summary.priced_pnl) ?? "-"}
      </span>{" "}
      <span className={pnlClass(summary.priced_pnl_rate_pct)}>
        ({fmtSignedPct(summary.priced_pnl_rate_pct) ?? "-"})
      </span>
    </span>
  );
}

// ─── 종목 행: 2단(상/하) × 2열(좌/우), 클릭 시 상세 펼침 (POC3-08) ──
//   좌상 종목명+판단 · 우상 손익 · 좌하 티커/수량/비중 · 우하 매입가→현재가.

function HoldingRow({
  it,
  rk,
  open,
  onToggle,
}: {
  it: EnrichedHolding;
  rk: string;
  open: boolean;
  onToggle: (k: string) => void;
}) {
  const priced = isPriced(it);
  const calcOK = isCalcAvailable(it);
  const pnlText = fmtSignedMoney(it.pnl_amount);
  const pnlRateText = fmtSignedPct(it.pnl_rate_pct);
  // 비중은 숫자로만(막대는 상단 계좌별 구성 막대로 통합 — 개별 행 막대 제거).
  const mwText = fmtPct(it.market_weight_pct);
  const avgText = fmtMoney(it.avg_buy_price);
  const curText = fmtMoney(it.current_price);
  const qtyText = Number.isFinite(it.quantity)
    ? it.quantity.toLocaleString("ko-KR")
    : "-";
  const nm = it.name && it.name !== it.ticker ? it.name : it.ticker;

  return (
    <>
      <div
        className="hld-row"
        role="button"
        tabIndex={0}
        aria-expanded={open}
        onClick={() => onToggle(rk)}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            onToggle(rk);
          }
        }}
      >
        {/* 상단: 좌 종목명+판단 / 우 손익 */}
        <div className="hld-row-top">
          <div className="hld-row-name">
            {nm}
            <span className="hld-badges">
              <span className="hld-b-hold">보유</span>
              {!priced ? (
                <span className="hld-b-warn">시세 미확인</span>
              ) : !calcOK ? (
                <span className="hld-b-warn">계산 정보 부족</span>
              ) : null}
            </span>
          </div>
          <div className="hld-row-pnl">
            {calcOK && pnlText && pnlRateText ? (
              <>
                <span className={`amt ${pnlClass(it.pnl_amount)}`}>{pnlText}</span>
                <span className={`rate ${pnlClass(it.pnl_amount)}`}>
                  {pnlRateText}
                </span>
              </>
            ) : (
              <span className="amt muted">—</span>
            )}
          </div>
        </div>
        {/* 하단: 좌 티커/수량/비중 / 우 매입가→현재가 */}
        <div className="hld-row-bot">
          <div className="hld-row-facts">
            <span className="tk">{it.ticker}</span>
            <span className="sep">/</span>
            <span>{qtyText}주</span>
            <span className="sep">/</span>
            {mwText ? (
              <span>
                비중 <span className="hld-wv">{mwText}</span>
              </span>
            ) : (
              <span className="muted">비중 계산 불가</span>
            )}
          </div>
          <div className="hld-row-price">
            {avgText ? (
              <>
                매입 <b>{avgText}</b>
                <span className="arw">→</span>
                {curText ? (
                  <>
                    현재 <b>{curText}</b>
                  </>
                ) : (
                  <span className="muted">현재 확인 불가</span>
                )}
              </>
            ) : (
              <span className="muted">매입가 없음</span>
            )}
          </div>
        </div>
      </div>
      {open ? (
        <div className="hld-row-detail">
          <DetailRowFields it={it} />
        </div>
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
