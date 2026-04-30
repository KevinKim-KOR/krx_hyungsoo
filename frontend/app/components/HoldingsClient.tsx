"use client";

// POC2 Step 1 → Step 2C — 보유 종목 입력/조회 + 시세평가 + compact UI.
//
// Step 2C 변경:
// - 입력 폼: account_group 컬럼 추가 (HTML <datalist> — 추천값 5개 + 직접입력).
// - 시세평가 섹션: 긴 카드 나열 → 전체 요약 → 계좌별 요약 → compact table → 상세 펼침
//   (지시문 "[UI 설계 방향]" 1·2·3·4 단계).
// - React key / 펼침 상태 key: source_index + ticker + account_group + avg_buy_price.
// - 상세 펼침은 기본 접힘. 사용자가 펼친 상태는 fetchEnrichedHoldings 호출 (저장 후 등) 직후에도
//   동일 항목 단위로 유지된다 (폼/표시 분리, 펼침 state 는 별도 Set 으로 관리).
//
// 정책 유지 (Step 2B):
// - "시세 확인" ≠ "평가 계산 가능" 분리. PnL 집계 원금은 평가 계산 가능 종목 매입금액 합산분만.
// - 시세 미확인 / 계산 정보 부족 종목을 0 원으로 취급 금지. undefined/null/NaN 비노출.
// - 외부 fetch 는 [시세 갱신] 버튼에서만. page load / polling 에서 호출 금지.

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ApiConfigError,
  ApiRequestError,
  fetchEnrichedHoldings,
  fetchHoldings,
  generateDraftFromHoldings,
  refreshMarket,
  saveHoldings,
  type EnrichedHolding,
  type HoldingItem,
  type Run,
} from "@/lib/api";

// ─── 입력 폼 row 모델 ───────────────────────────────────────────

type RowDraft = {
  ticker: string;
  name: string;
  quantity: string;
  avg_buy_price: string;
  account_group: string;
};

const DEFAULT_GROUP = "일반";

const RECOMMENDED_GROUPS: ReadonlyArray<string> = [
  "일반",
  "ISA",
  "연금",
  "오픈뱅킹",
  "기타",
];

const ACCOUNT_GROUP_MAX_LEN = 30;

const EMPTY_ROW: RowDraft = {
  ticker: "",
  name: "",
  quantity: "",
  avg_buy_price: "",
  account_group: "",
};

function holdingToRow(h: HoldingItem): RowDraft {
  return {
    ticker: h.ticker,
    name: h.name ?? "",
    quantity: String(h.quantity),
    avg_buy_price: String(h.avg_buy_price),
    account_group: h.account_group ?? DEFAULT_GROUP,
  };
}

function rowsToPayload(rows: RowDraft[]): { holdings: HoldingItem[] } {
  return {
    holdings: rows.map((r) => {
      const q = Number(r.quantity);
      const p = Number(r.avg_buy_price);
      const nm = r.name.trim();
      const ag = r.account_group.trim();
      const item: HoldingItem = {
        ticker: r.ticker.trim(),
        quantity: Number.isFinite(q) ? q : 0,
        avg_buy_price: Number.isFinite(p) ? p : 0,
      };
      if (nm) item.name = nm;
      // 빈 문자열은 백엔드에서 "일반" 으로 정규화. 명시 입력만 전송.
      if (ag) item.account_group = ag;
      return item;
    }),
  };
}

function computeInvested(rows: RowDraft[]): number[] {
  return rows.map((r) => {
    const q = Number(r.quantity);
    const p = Number(r.avg_buy_price);
    return Number.isFinite(q) && Number.isFinite(p) ? q * p : 0;
  });
}

function formatNumber(n: number): string {
  if (!Number.isFinite(n)) return "-";
  return n.toLocaleString("ko-KR", {
    maximumFractionDigits: 2,
  });
}

function fmtMoney(value: number | null | undefined): string | null {
  if (value === null || value === undefined || !Number.isFinite(value)) return null;
  return `${value.toLocaleString("ko-KR", { maximumFractionDigits: 2 })}원`;
}

function fmtSignedMoney(value: number | null | undefined): string | null {
  if (value === null || value === undefined || !Number.isFinite(value)) return null;
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toLocaleString("ko-KR", { maximumFractionDigits: 2 })}원`;
}

function fmtPct(value: number | null | undefined): string | null {
  if (value === null || value === undefined || !Number.isFinite(value)) return null;
  return `${value.toLocaleString("ko-KR", { maximumFractionDigits: 2 })}%`;
}

function fmtSignedPct(value: number | null | undefined): string | null {
  if (value === null || value === undefined || !Number.isFinite(value)) return null;
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toLocaleString("ko-KR", { maximumFractionDigits: 2 })}%`;
}

function pnlClass(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "";
  if (value > 0) return "pnl-pos";
  if (value < 0) return "pnl-neg";
  return "";
}

interface Props {
  onDraftCreated: (run: Run) => void;
}

export default function HoldingsClient({ onDraftCreated }: Props) {
  const [rows, setRows] = useState<RowDraft[]>([{ ...EMPTY_ROW }]);
  const [loading, setLoading] = useState<boolean>(false);
  const [refreshing, setRefreshing] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [savedAt, setSavedAt] = useState<string | null>(null);
  const [enriched, setEnriched] = useState<EnrichedHolding[]>([]);
  const [refreshSummary, setRefreshSummary] = useState<string | null>(null);

  const handleApiError = useCallback((e: unknown) => {
    if (e instanceof ApiConfigError) {
      setErrorMsg(`구성 오류: ${e.message}`);
      return;
    }
    if (e instanceof ApiRequestError) {
      const detail =
        typeof e.body === "string"
          ? e.body
          : e.body && typeof e.body === "object" && "detail" in e.body
            ? String((e.body as Record<string, unknown>).detail)
            : JSON.stringify(e.body);
      setErrorMsg(`요청 실패(HTTP ${e.httpStatus}): ${detail}`);
      return;
    }
    setErrorMsg(`알 수 없는 오류: ${(e as Error).message}`);
  }, []);

  // 캐시에서 enriched 조회 (외부 fetch 트리거 안 함 — 로드/저장 후 표시 갱신용)
  const loadEnriched = useCallback(async () => {
    try {
      const data = await fetchEnrichedHoldings();
      setEnriched(data.items);
    } catch (e) {
      handleApiError(e);
    }
  }, [handleApiError]);

  // 최초 로드: 저장된 holdings 조회 + enriched (캐시) 조회
  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        const data = await fetchHoldings();
        if (data.holdings.length > 0) {
          setRows(data.holdings.map(holdingToRow));
          await loadEnriched();
        }
      } catch (e) {
        handleApiError(e);
      } finally {
        setLoading(false);
      }
    })();
  }, [handleApiError, loadEnriched]);

  const updateRow = (idx: number, key: keyof RowDraft, value: string) => {
    setRows((prev) =>
      prev.map((r, i) => (i === idx ? { ...r, [key]: value } : r))
    );
  };

  const addRow = () => setRows((prev) => [...prev, { ...EMPTY_ROW }]);
  const removeRow = (idx: number) =>
    setRows((prev) => (prev.length <= 1 ? prev : prev.filter((_, i) => i !== idx)));

  const onSave = useCallback(async () => {
    setLoading(true);
    setErrorMsg(null);
    setSavedAt(null);
    try {
      const payload = rowsToPayload(rows);
      const saved = await saveHoldings(payload);
      setRows(saved.holdings.map(holdingToRow));
      setSavedAt(new Date().toLocaleTimeString("ko-KR"));
      // 저장 후 enriched 표시도 갱신 (시세는 캐시에 있을 때만 반영, fetch 트리거 X).
      await loadEnriched();
    } catch (e) {
      handleApiError(e);
    } finally {
      setLoading(false);
    }
  }, [rows, handleApiError, loadEnriched]);

  const onGenerate = useCallback(async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const run = await generateDraftFromHoldings();
      onDraftCreated(run);
    } catch (e) {
      handleApiError(e);
    } finally {
      setLoading(false);
    }
  }, [handleApiError, onDraftCreated]);

  // POC2 Step 2 — 사용자 명시적 액션. page load / polling 에서 호출 금지.
  const onRefreshMarket = useCallback(async () => {
    setRefreshing(true);
    setErrorMsg(null);
    setRefreshSummary(null);
    try {
      const result = await refreshMarket();
      const failNote =
        result.fail_count > 0
          ? ` / 실패 ${result.fail_count}건: ${result.failures
              .map((f) => `${f.ticker}(${f.reason})`)
              .join(", ")}`
          : "";
      setRefreshSummary(
        `Naver 시세 갱신 완료 — 성공 ${result.ok_count}건${failNote} (${new Date().toLocaleTimeString(
          "ko-KR"
        )})`
      );
      await loadEnriched();
    } catch (e) {
      handleApiError(e);
    } finally {
      setRefreshing(false);
    }
  }, [handleApiError, loadEnriched]);

  const investedList = computeInvested(rows);
  const totalInvested = investedList.reduce((a, b) => a + b, 0);

  return (
    <div className="card">
      <h2>1. 보유 종목 입력</h2>
      <p className="helper">
        종목코드 / 수량 / 매입단가는 필수. 종목명·계좌는 선택 (계좌 미입력 시 “일반”).
        계좌 라벨은 표시/그룹용이며 실제 계좌번호 / 증권사 / 세금 판정값이 아닙니다.
      </p>

      {errorMsg ? <div className="message error">{errorMsg}</div> : null}

      <datalist id="account-group-options">
        {RECOMMENDED_GROUPS.map((g) => (
          <option value={g} key={g} />
        ))}
      </datalist>

      <table className="holdings-table">
        <thead>
          <tr>
            <th>종목코드 *</th>
            <th>종목명</th>
            <th>계좌</th>
            <th>수량 *</th>
            <th>매입단가 *</th>
            <th>매입금액</th>
            <th>매입비중</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, idx) => {
            const invested = investedList[idx];
            const weight =
              totalInvested > 0 ? (invested / totalInvested) * 100 : 0;
            return (
              <tr key={idx}>
                <td>
                  <input
                    type="text"
                    value={r.ticker}
                    onChange={(e) => updateRow(idx, "ticker", e.target.value)}
                    placeholder="069500"
                    disabled={loading}
                  />
                </td>
                <td>
                  <input
                    type="text"
                    value={r.name}
                    onChange={(e) => updateRow(idx, "name", e.target.value)}
                    placeholder="(선택)"
                    disabled={loading}
                  />
                </td>
                <td>
                  <input
                    type="text"
                    list="account-group-options"
                    value={r.account_group}
                    onChange={(e) =>
                      updateRow(idx, "account_group", e.target.value)
                    }
                    placeholder="일반"
                    maxLength={ACCOUNT_GROUP_MAX_LEN}
                    disabled={loading}
                  />
                </td>
                <td>
                  <input
                    type="number"
                    value={r.quantity}
                    onChange={(e) => updateRow(idx, "quantity", e.target.value)}
                    placeholder="10"
                    min="0"
                    step="any"
                    disabled={loading}
                  />
                </td>
                <td>
                  <input
                    type="number"
                    value={r.avg_buy_price}
                    onChange={(e) =>
                      updateRow(idx, "avg_buy_price", e.target.value)
                    }
                    placeholder="38500"
                    min="0"
                    step="any"
                    disabled={loading}
                  />
                </td>
                <td className="num">{formatNumber(invested)}</td>
                <td className="num">
                  {totalInvested > 0 ? `${weight.toFixed(2)}%` : "-"}
                </td>
                <td>
                  <button
                    className="reject"
                    onClick={() => removeRow(idx)}
                    disabled={loading || rows.length <= 1}
                    title="이 행 삭제"
                  >
                    ×
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
        <tfoot>
          <tr>
            <td colSpan={5} style={{ textAlign: "right", color: "var(--muted)" }}>
              합계
            </td>
            <td className="num">
              <strong>{formatNumber(totalInvested)}</strong>
            </td>
            <td className="num">100%</td>
            <td></td>
          </tr>
        </tfoot>
      </table>

      <div className="btn-row" style={{ marginTop: 12 }}>
        <button className="reject" onClick={addRow} disabled={loading || refreshing}>
          행 추가
        </button>
        <button onClick={onSave} disabled={loading || refreshing}>
          {loading ? "처리 중..." : "보유 종목 저장"}
        </button>
        <button onClick={onGenerate} disabled={loading || refreshing} type="button">
          저장된 보유 종목으로 초안 만들기
        </button>
        <button
          onClick={onRefreshMarket}
          disabled={loading || refreshing}
          type="button"
          title="저장된 보유 종목의 현재가를 Naver 에서 1회 조회하여 캐시에 반영"
        >
          {refreshing ? "시세 조회 중..." : "시세 갱신 (Naver)"}
        </button>
      </div>

      {savedAt ? (
        <div className="helper" style={{ marginTop: 8 }}>
          저장 완료 ({savedAt})
        </div>
      ) : null}
      {refreshSummary ? (
        <div className="helper" style={{ marginTop: 4 }}>
          {refreshSummary}
        </div>
      ) : null}

      {enriched.length > 0 ? <EnrichedSection items={enriched} /> : null}
    </div>
  );
}

// ─── Step 2C — 시세평가 compact UI ────────────────────────────────

interface EnrichedSectionProps {
  items: EnrichedHolding[];
}

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

function EnrichedSection({ items }: EnrichedSectionProps) {
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
