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
  applyHoldingsToOci,
  fetchHoldingsApplyStatus,
  type HoldingItem,
  type HoldingsApplyResult,
  type HoldingsApplyStatusRecord,
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
    // 저장된 숫자를 불러올 때도 콤마 표시(요구 3).
    quantity: formatWithCommas(String(h.quantity)),
    avg_buy_price: formatWithCommas(String(h.avg_buy_price)),
    account_group: h.account_group ?? DEFAULT_GROUP,
  };
}

function rowsToPayload(rows: RowDraft[]): { holdings: HoldingItem[] } {
  return {
    holdings: rows.map((r) => {
      // 입력칸에 콤마가 있을 수 있으므로 제거 후 숫자로.
      const q = Number(stripCommas(r.quantity));
      const p = Number(stripCommas(r.avg_buy_price));
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
    const q = Number(stripCommas(r.quantity));
    const p = Number(stripCommas(r.avg_buy_price));
    return Number.isFinite(q) && Number.isFinite(p) ? q * p : 0;
  });
}

function formatNumber(n: number): string {
  if (!Number.isFinite(n)) return "-";
  return n.toLocaleString("ko-KR", {
    maximumFractionDigits: 2,
  });
}

// 입력칸용 콤마 포맷 — 입력 중에도 천단위 콤마를 보여준다(요구 3).
//   저장 시에는 stripCommas 로 콤마를 제거해 숫자로 전송한다.
//   소수점·입력 중 상태(예: "1," "1.")를 깨지 않도록 정수부만 콤마 처리.
export function formatWithCommas(raw: string): string {
  if (raw === "") return "";
  // 숫자·소수점·콤마만 남기고 나머지 제거.
  const cleaned = raw.replace(/[^\d.]/g, "");
  const negative = raw.trim().startsWith("-");
  const [intPart, ...decParts] = cleaned.split(".");
  const grouped = intPart.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  // 소수점이 입력된 경우(끝에 "." 포함)를 보존.
  const hasDot = cleaned.includes(".");
  const dec = decParts.join("");
  const body = hasDot ? `${grouped}.${dec}` : grouped;
  return negative ? `-${body}` : body;
}

// 콤마 제거 — 저장/계산 전 순수 숫자 문자열로.
export function stripCommas(s: string): string {
  return s.replace(/,/g, "");
}

interface Props {
  onNavigate: (key: MenuKey) => void;
}

export default function HoldingsManageView({ onNavigate }: Props) {
  const [rows, setRows] = useState<RowDraft[]>([{ ...EMPTY_ROW }]);
  const [loading, setLoading] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [savedAt, setSavedAt] = useState<string | null>(null);
  // POC3-07: OCI 적용은 저장과 별도 동작(설계자 Q3). 명시적 클릭에서만 실행.
  const [applying, setApplying] = useState<boolean>(false);
  const [applyResult, setApplyResult] = useState<HoldingsApplyResult | null>(
    null
  );
  // POC3-08: 마지막 OCI 적용 이력(지속 표시). null = 이력 없음.
  const [lastApply, setLastApply] = useState<HoldingsApplyStatusRecord | null>(
    null
  );

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
    // 수량·매입단가는 입력 중에도 천단위 콤마로 보여준다(요구 3).
    const next =
      key === "quantity" || key === "avg_buy_price"
        ? formatWithCommas(value)
        : value;
    setRows((prev) =>
      prev.map((r, i) => (i === idx ? { ...r, [key]: next } : r))
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

  // POC3-08: 마지막 OCI 적용 이력(지속 표시). 마운트 시 1회 조회.
  const loadApplyStatus = useCallback(async () => {
    try {
      const rec = await fetchHoldingsApplyStatus();
      setLastApply(rec.has_record ? rec : null);
    } catch {
      // 이력 조회 실패는 조용히 무시(부가 정보). 적용 자체와 무관.
    }
  }, []);

  useEffect(() => {
    loadApplyStatus();
  }, [loadApplyStatus]);

  // OCI 적용 — 저장된 Holdings 를 OCI 에 명시적으로 전송·검증·적용(Q3·Q4·Q11).
  //   저장과 별도 동작. 자동 실행 아님. 실패해도 기존 OCI active 는 보존된다.
  const onApplyToOci = useCallback(async () => {
    setApplying(true);
    setApplyResult(null);
    try {
      const result = await applyHoldingsToOci();
      setApplyResult(result);
      // 적용 후 지속 이력도 갱신(화면 재진입해도 남게).
      await loadApplyStatus();
    } catch (e) {
      handleApiError(e);
    } finally {
      setApplying(false);
    }
  }, [handleApiError, loadApplyStatus]);

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

        {/* POC3-08: 입력 편의 우선 카드행 그리드. 각 종목이 넉넉한 간격의 행 카드.
            수량·매입단가는 콤마 표시(입력 중에도) · 계좌 색 pill · 비중 막대. */}
        <div className="hm-grid">
          <div className="hm-chead" role="row">
            <span>종목코드 *</span>
            <span>종목명</span>
            <span>계좌</span>
            <span className="num">수량 *</span>
            <span className="num">매입단가 *</span>
            <span className="num">매입금액</span>
            <span className="num">매입비중</span>
            <span></span>
          </div>

          {rows.map((r, idx) => {
            const invested = investedList[idx];
            const weight =
              totalInvested > 0 ? (invested / totalInvested) * 100 : 0;
            // 입력칸 자체에 계좌 색을 입힌다(별도 pill 없이 — 중복 방지).
            //   알려진 계좌만 색 매핑(임의 입력이 클래스명 되는 것 방지).
            const knownAcct = new Set(["ISA", "오픈뱅킹", "연금"]);
            const acctInpClass = knownAcct.has(r.account_group)
              ? `hm-inp hm-inp-acct hm-inp-acct-${r.account_group}`
              : "hm-inp hm-inp-acct";
            return (
              <div className="hm-rowcard" key={idx}>
                <input
                  className="hm-inp"
                  type="text"
                  value={r.ticker}
                  onChange={(e) => updateRow(idx, "ticker", e.target.value)}
                  placeholder="069500"
                  aria-label="종목코드"
                  disabled={loading}
                />
                <input
                  className="hm-inp"
                  type="text"
                  value={r.name}
                  onChange={(e) => updateRow(idx, "name", e.target.value)}
                  placeholder="(선택)"
                  aria-label="종목명"
                  disabled={loading}
                />
                <input
                  className={acctInpClass}
                  type="text"
                  list="account-group-options"
                  value={r.account_group}
                  onChange={(e) =>
                    updateRow(idx, "account_group", e.target.value)
                  }
                  placeholder="일반"
                  maxLength={ACCOUNT_GROUP_MAX_LEN}
                  aria-label="계좌"
                  disabled={loading}
                />
                <input
                  className="hm-inp num"
                  type="text"
                  inputMode="decimal"
                  value={r.quantity}
                  onChange={(e) => updateRow(idx, "quantity", e.target.value)}
                  placeholder="10"
                  aria-label="수량"
                  disabled={loading}
                />
                <input
                  className="hm-inp num"
                  type="text"
                  inputMode="numeric"
                  value={r.avg_buy_price}
                  onChange={(e) =>
                    updateRow(idx, "avg_buy_price", e.target.value)
                  }
                  placeholder="38,500"
                  aria-label="매입단가"
                  disabled={loading}
                />
                <span className="hm-num">{formatNumber(invested)}</span>
                <span className={weight >= 8 ? "hm-num hm-w-big" : "hm-num"}>
                  {totalInvested > 0 ? `${weight.toFixed(2)}%` : "-"}
                </span>
                <button
                  className="hm-del"
                  onClick={() => removeRow(idx)}
                  disabled={loading || rows.length <= 1}
                  title="이 행 삭제"
                  aria-label="이 행 삭제"
                >
                  ×
                </button>
              </div>
            );
          })}

          <div className="hm-foot">
            <span className="hm-foot-label">합계 · {rows.length}종목</span>
            <span className="hm-num">
              <strong>{formatNumber(totalInvested)}</strong>
            </span>
            <span className="hm-num">100%</span>
          </div>
        </div>

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

      {/* POC3-07 §6: OCI 적용 — 저장과 별도 동작. 명시적 클릭에서만 실행한다.
          저장 성공을 OCI 적용 성공으로 위장하지 않는다(§6.4). */}
      <div className="card" style={{ marginTop: 16 }}>
        <h2>OCI 적용</h2>
        <p className="helper" style={{ marginBottom: 8 }}>
          저장한 보유 종목을 OCI 운영 환경에 적용합니다. <strong>저장과는 별도</strong>{" "}
          동작이며, 이 버튼을 눌러야만 전송됩니다. 실패해도 기존 OCI 적용 상태는
          유지됩니다.
        </p>
        {lastApply && lastApply.applied_at ? (
          <div className="helper" style={{ marginBottom: 8 }}>
            마지막 OCI 적용:{" "}
            {new Date(lastApply.applied_at).toLocaleString("ko-KR")} ·{" "}
            {lastApply.status === "OCI_APPLIED"
              ? "성공"
              : `${lastApply.status}`}
          </div>
        ) : (
          <div className="helper" style={{ marginBottom: 8 }}>
            아직 OCI 에 적용한 기록이 없습니다.
          </div>
        )}
        <button type="button" onClick={onApplyToOci} disabled={applying || loading}>
          {applying ? "적용 중..." : "저장한 보유 종목 OCI 적용"}
        </button>
        {applyResult ? (
          <div
            className={
              applyResult.status === "OCI_APPLIED" ? "message" : "message error"
            }
            style={{ marginTop: 8 }}
          >
            [{applyResult.status}] {applyResult.message}
            {applyResult.applied_at ? (
              <div className="helper" style={{ marginTop: 4 }}>
                적용 시각: {new Date(applyResult.applied_at).toLocaleString()}
              </div>
            ) : null}
          </div>
        ) : null}
      </div>
    </section>
  );
}
