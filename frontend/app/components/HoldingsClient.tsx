"use client";

// POC2 Step 1 — 보유 종목 입력/조회 + 보유 기반 초안 생성.
// 행 단위 추가/삭제. 매입금액(quantity * avg_buy_price) 과 매입금액 기준 비중은
// 클라이언트에서 즉시 계산해서 사용자가 볼 수 있게 한다 (서버 저장 시에도
// 동일 공식으로 draft_payload 에 반영됨).
//
// 종목명은 선택 입력. 미입력 시 ticker 로 표시 (서버 정책과 일치).
//
// 검증 실패는 서버에서 422 로 차단되며 run_id 가 만들어지지 않는다.
// (POC2 Step 1 E항 — 단순 입력 오류로 FAILED run 만들지 않는다.)

import { useCallback, useEffect, useState } from "react";
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

type RowDraft = {
  ticker: string;
  name: string;
  quantity: string;
  avg_buy_price: string;
};

const EMPTY_ROW: RowDraft = {
  ticker: "",
  name: "",
  quantity: "",
  avg_buy_price: "",
};

function holdingToRow(h: HoldingItem): RowDraft {
  return {
    ticker: h.ticker,
    name: h.name ?? "",
    quantity: String(h.quantity),
    avg_buy_price: String(h.avg_buy_price),
  };
}

function rowsToPayload(rows: RowDraft[]): { holdings: HoldingItem[] } {
  return {
    holdings: rows.map((r) => {
      const q = Number(r.quantity);
      const p = Number(r.avg_buy_price);
      const nm = r.name.trim();
      const item: HoldingItem = {
        ticker: r.ticker.trim(),
        quantity: Number.isFinite(q) ? q : 0,
        avg_buy_price: Number.isFinite(p) ? p : 0,
      };
      if (nm) item.name = nm;
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

interface Props {
  onDraftCreated: (run: Run) => void;
}

function formatMoney(value: number | null | undefined): string | null {
  if (value === null || value === undefined || !Number.isFinite(value)) return null;
  return `${value.toLocaleString("ko-KR", { maximumFractionDigits: 2 })}원`;
}

function formatPct(value: number | null | undefined): string | null {
  if (value === null || value === undefined || !Number.isFinite(value)) return null;
  return `${value.toLocaleString("ko-KR", { maximumFractionDigits: 2 })}%`;
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
      // enriched 조회 실패는 비치명적 (입력 화면은 동작 가능). 에러 표시만.
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
        종목코드 / 수량 / 매입단가는 필수. 종목명은 선택 (미입력 시 종목코드로
        표시). 입력 오류는 저장 시점에 서버가 422 로 차단합니다 (잘못된 입력으로
        실패 처리된 초안은 만들어지지 않습니다).
      </p>

      {errorMsg ? <div className="message error">{errorMsg}</div> : null}

      <table className="holdings-table">
        <thead>
          <tr>
            <th>종목코드 *</th>
            <th>종목명</th>
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
            <td colSpan={4} style={{ textAlign: "right", color: "var(--muted)" }}>
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

// ─── POC2 Step 2 — 시세/평가 표시 섹션 ────────────────────────────────

interface EnrichedSectionProps {
  items: EnrichedHolding[];
}

function EnrichedSection({ items }: EnrichedSectionProps) {
  const hasAnyPrice = items.some((it) => it.current_price !== null);
  return (
    <div style={{ marginTop: 20 }}>
      <h3 style={{ fontSize: 14, margin: "0 0 8px 0" }}>
        보유 종목 시세 평가
      </h3>
      <p className="helper" style={{ marginTop: 0 }}>
        {hasAnyPrice
          ? "캐시된 Naver 시세 기준 평가. 갱신은 위의 [시세 갱신] 버튼."
          : "아직 시세가 캐시되지 않았습니다. [시세 갱신] 버튼으로 1회 조회하세요."}
      </p>
      <ul className="holdings-list">
        {items.map((it, idx) => (
          <li className="holdings-item" key={`${it.ticker}-${idx}`}>
            <div className="holdings-item-header">
              {it.name && it.name !== it.ticker
                ? `${idx + 1}. ${it.name} (${it.ticker})`
                : `${idx + 1}. ${it.ticker}`}
            </div>
            <ul className="holdings-item-fields">
              <KV k="수량" v={it.quantity.toLocaleString("ko-KR")} />
              <KV k="평균 매입단가" v={formatMoney(it.avg_buy_price)} />
              <KV k="매입금액" v={formatMoney(it.invested_amount)} />
              <KV k="매입비중" v={formatPct(it.buy_weight_pct)} />
              <KV k="현재가" v={formatMoney(it.current_price)} />
              <KV k="평가금액" v={formatMoney(it.eval_amount)} />
              <KV k="평가손익" v={formatMoney(it.pnl_amount)} />
              <KV k="평가수익률" v={formatPct(it.pnl_rate_pct)} />
              <KV k="시장비중" v={formatPct(it.market_weight_pct)} />
              {it.price_missing ? (
                <li>
                  <span className="k">상태</span>
                  <span className="v" style={{ color: "var(--warn)" }}>
                    [시세 미확인]
                  </span>
                </li>
              ) : null}
              {it.price_asof ? (
                <KV k="시세 기준" v={it.price_asof} />
              ) : null}
            </ul>
          </li>
        ))}
      </ul>
    </div>
  );
}

function KV({ k, v }: { k: string; v: string | null }) {
  if (v === null) return null;
  return (
    <li>
      <span className="k">{k}</span>
      <span className="v">{v}</span>
    </li>
  );
}
