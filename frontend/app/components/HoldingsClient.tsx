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
import { DEFAULT_GROUP } from "@/lib/holdings_view";
import EnrichedSection from "./EnrichedHoldingsSection";
// POC2 Holdings × Market Discovery Evidence 1차 (2026-06-03) — 보유 ETF 가
// Market Discovery 후보 / 시장 국면 / 단기 흐름 / 구성종목 / NAV 와 어떻게
// 연결되는지의 raw evidence 카드. 사용자 액션에서만 호출 (page load auto X).
import HoldingsMarketEvidenceCard from "./HoldingsMarketEvidenceCard";

// ─── 입력 폼 row 모델 ───────────────────────────────────────────

type RowDraft = {
  ticker: string;
  name: string;
  quantity: string;
  avg_buy_price: string;
  account_group: string;
};

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

      <HoldingsMarketEvidenceCard />
    </div>
  );
}

