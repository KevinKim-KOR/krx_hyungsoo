"use client";

// POC3-05 DESIGN_V2 — "종목 관리" 화면 (§4.3).
//
// 입력·수정·삭제·저장 전용. 기존 HoldingsClient 의 입력 폼·저장 계약을 그대로 재사용한다
// (Q1-a: 입력부와 평가·시세부 분리). 평가·시장 Evidence 전체 표·초안 생성·시세 갱신은
// 이 화면에 노출하지 않는다(§4.3 금지). 저장 완료 후 "보유 현황 보기" 연결(Q3: 자동 전환
// 없음, 사용자 클릭 이동).
//
// 저장/입력 의미는 기존과 동일 — 새 계산·새 API 없음. 저장 성공 시 Dashboard 읽기 무효화도
// 기존과 동일(HOLDINGS_INVALIDATION_KEYS).

import { useCallback, useEffect, useState } from "react";
import {
  ApiConfigError,
  ApiRequestError,
  fetchHoldings,
  saveHoldings,
  type HoldingItem,
} from "@/lib/api";
import { DEFAULT_GROUP } from "@/lib/holdings_view";
import { invalidateQueries } from "@/lib/api/queryCache";
import { HOLDINGS_INVALIDATION_KEYS } from "@/lib/api/dashboardKeys";
import type { MenuKey } from "./LeftSidebar";

// ─── 입력 폼 row 모델 (기존 HoldingsClient 와 동일) ─────────────────

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
  onNavigate: (key: MenuKey) => void;
}

export default function HoldingsManageView({ onNavigate }: Props) {
  const [rows, setRows] = useState<RowDraft[]>([{ ...EMPTY_ROW }]);
  const [loading, setLoading] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [savedAt, setSavedAt] = useState<string | null>(null);

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

  // 최초 로드: 저장된 holdings 조회 (외부 시세 fetch 없음 — 입력 화면).
  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        const data = await fetchHoldings();
        if (data.holdings.length > 0) {
          setRows(data.holdings.map(holdingToRow));
        }
      } catch (e) {
        handleApiError(e);
      } finally {
        setLoading(false);
      }
    })();
  }, [handleApiError]);

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
      // 저장 성공 시에만 Dashboard 의 보유·Evidence 읽기 무효화 (변경 실패 시
      // catch 로 가서 미호출 — §4.5 "변경 실패 시 무효화 금지").
      for (const k of HOLDINGS_INVALIDATION_KEYS) invalidateQueries(k);
    } catch (e) {
      handleApiError(e);
    } finally {
      setLoading(false);
    }
  }, [rows, handleApiError]);

  const investedList = computeInvested(rows);
  const totalInvested = investedList.reduce((a, b) => a + b, 0);

  return (
    <section aria-labelledby="holdings-manage-h">
      <h1 id="holdings-manage-h">종목 관리</h1>
      <p className="subtitle">
        보유 종목을 입력·수정·삭제하고 저장합니다. 평가·확인 근거는 저장 후
        &lsquo;보유 현황&rsquo;·&lsquo;확인 근거&rsquo; 화면에서 확인합니다.
      </p>

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
          <button className="reject" onClick={addRow} disabled={loading}>
            행 추가
          </button>
          <button onClick={onSave} disabled={loading}>
            {loading ? "처리 중..." : "보유 종목 저장"}
          </button>
        </div>

        {savedAt ? (
          <div className="helper" style={{ marginTop: 8 }}>
            저장 완료 ({savedAt})
            <button
              type="button"
              style={{ marginLeft: 10 }}
              onClick={() => onNavigate("holdings")}
            >
              보유 현황 보기 →
            </button>
          </div>
        ) : null}
      </div>
    </section>
  );
}
