"use client";

// POC3-05 DESIGN_V2 — "보유 현황" 화면 (§4.2).
//
// 평가 현황과 시세 갱신 (읽기 중심, 입력 폼 없음). 기존 HoldingsClient 의 평가·시세부만
// 분리 재사용한다(Q1-a). 보유 종목 입력·저장은 "종목 관리", 확인 근거·시장 Evidence 표는
// "확인 근거" 화면으로 분리(§4.2 금지: 입력 폼·긴 시장 Evidence 표·초안 생성 노출 금지).
//
// - 전체/계좌별/ticker별 평가 = EnrichedSection 재사용 (신규 계산 없음).
// - 시세 갱신(Naver) = 기존 refreshMarket 계약 그대로. 사용자 액션에서만 호출.
// - enriched 조회는 캐시에서 표시 (page load 시 저장분 1회 조회, 외부 시세 fetch 는
//   [시세 갱신] 버튼에서만).

import { useCallback, useEffect, useState } from "react";
import {
  ApiConfigError,
  ApiRequestError,
  fetchEnrichedHoldings,
  refreshMarket,
  type EnrichedHolding,
} from "@/lib/api";
import EnrichedSection from "./EnrichedHoldingsSection";
import type { MenuKey } from "./LeftSidebar";

interface Props {
  onNavigate: (key: MenuKey) => void;
}

export default function HoldingsView({ onNavigate }: Props) {
  const [enriched, setEnriched] = useState<EnrichedHolding[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [refreshing, setRefreshing] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
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

  // 캐시에서 enriched 조회 (외부 fetch 트리거 안 함 — 표시 갱신용).
  const loadEnriched = useCallback(async () => {
    try {
      const data = await fetchEnrichedHoldings();
      setEnriched(data.items);
    } catch (e) {
      handleApiError(e);
    }
  }, [handleApiError]);

  // 최초 로드: 저장된 enriched(캐시) 조회.
  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        await loadEnriched();
      } finally {
        setLoading(false);
      }
    })();
  }, [loadEnriched]);

  // 사용자 명시적 액션. page load / polling 에서 호출 금지.
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

  return (
    <section aria-labelledby="holdings-h">
      <h1 id="holdings-h">보유 현황</h1>
      <p className="subtitle">
        저장된 보유 종목의 평가 현황입니다. 종목 입력·수정은 &lsquo;종목 관리&rsquo;,
        오늘 먼저 볼 ETF와 근거는 &lsquo;확인 근거&rsquo; 화면에서 확인합니다.
      </p>

      <div className="card">
        <div className="btn-row">
          <button
            onClick={onRefreshMarket}
            disabled={refreshing}
            type="button"
            title="저장된 보유 종목의 현재가를 Naver 에서 1회 조회하여 캐시에 반영"
          >
            {refreshing ? "시세 조회 중..." : "시세 갱신 (Naver)"}
          </button>
          <button type="button" onClick={() => onNavigate("holdings_manage")}>
            종목 관리 →
          </button>
          <button type="button" onClick={() => onNavigate("holdings_evidence")}>
            확인 근거 보기 →
          </button>
        </div>

        {errorMsg ? (
          <div className="message error" style={{ marginTop: 8 }}>
            {errorMsg}
          </div>
        ) : null}
        {refreshSummary ? (
          <div className="helper" style={{ marginTop: 8 }}>
            {refreshSummary}
          </div>
        ) : null}

        {loading ? (
          <div className="message info" style={{ marginTop: 8 }}>
            불러오는 중...
          </div>
        ) : enriched.length > 0 ? (
          <EnrichedSection items={enriched} />
        ) : (
          <div className="message info" style={{ marginTop: 8 }}>
            저장된 보유 종목이 없습니다. &lsquo;종목 관리&rsquo;에서 보유 종목을 입력·저장하세요.
          </div>
        )}
      </div>
    </section>
  );
}
