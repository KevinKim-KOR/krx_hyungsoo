"use client";

// POC2 Step 6 + Fix 라운드 + Step 7A — 신규 ETF 관찰 후보 (PUSH 2) refresh 버튼 + 상태 패널.
//
// 정책 (Step7A 명칭 정렬, 2026-05-11):
// - 사용자 노출 명칭은 공식 PUSH 2 "신규 ETF 관찰 후보" 로 통일 (기존 "외부 후보 점검"
//   사용자 노출 문구 전면 정렬). 내부 함수명 / 컴포넌트명은 유지.
// - seed 파일이 없으면 백엔드가 starter seed 를 생성 후 refresh 실행 (Step7A §4.2).
//   응답의 summary.source === "starter_seed" 면 "기본 후보군 사용" 안내 표시.
//
// 정책 (Fix 라운드 2026-05-11):
// - 신규 endpoint 추가 금지 (GET /universe/momentum/latest 미도입).
// - mount 시 fetch 미수행. POST refresh 응답을 frontend state 로 보관해 상태 패널 표시.
// - 페이지 reload 시 state 비워짐 → 안내 문구만 표시 (사용자가 갱신 버튼 한 번 더 누르면 채워짐).
//
// Step6 §12 정책 유지:
// - 갱신 버튼 / 상태 패널은 승인 초안 내부가 아니라 별도 영역.
// - 버튼 클릭은 Telegram / Approve / GenerateDraft 자동 실행 안 함.
// - 요청 중 버튼 disabled.
// - 후보 전체 리스트는 표시하지 않음 (§12.2 / AC-28).
// - 기준일 우선순위: top_candidate.price_history_basis.latest_date → momentum_result.asof
//   → "기준일 확인 불가".

import { useCallback, useState } from "react";

import {
  ApiConfigError,
  ApiRequestError,
  refreshUniverseMomentum,
  type UniverseRefreshResponse,
} from "@/lib/api";

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

function basisDate(res: UniverseRefreshResponse | null): string {
  if (!res) return "기준일 확인 불가";
  const top = res.momentum_result.summary.top_candidate;
  if (top && top.price_history_basis && top.price_history_basis.latest_date) {
    return top.price_history_basis.latest_date;
  }
  const asof = res.momentum_result.asof;
  if (asof) return asof;
  return "기준일 확인 불가";
}

function refreshStatusLabel(
  status: "ok" | "partial" | "failed" | undefined,
): string {
  if (status === "ok") return "성공";
  if (status === "partial") return "부분 성공";
  if (status === "failed") return "실패";
  return "—";
}

export default function UniverseRefreshPanel() {
  const [latest, setLatest] = useState<UniverseRefreshResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [statusNote, setStatusNote] = useState<string | null>(null);

  const onRefresh = useCallback(async () => {
    setLoading(true);
    setErrorMsg(null);
    setStatusNote(null);
    try {
      const res = await refreshUniverseMomentum();
      setLatest(res);
      const summary = res.momentum_result.summary;
      const ts = new Date().toLocaleTimeString("ko-KR");
      setStatusNote(
        `신규 ETF 관찰 후보 갱신 ${refreshStatusLabel(summary.refresh_status)} ` +
          `— 계산 가능 ${summary.scored_candidates}/${summary.total_candidates}개 (${ts})`,
      );
    } catch (e) {
      setErrorMsg(describeApiError(e));
    } finally {
      setLoading(false);
    }
  }, []);

  const summary = latest?.momentum_result.summary;
  const status = summary?.refresh_status;
  const top = summary?.top_candidate;
  const computedBasisDate = basisDate(latest);

  const usingStarterSeed = summary?.source === "starter_seed";

  return (
    <div className="card" style={{ marginTop: 16 }}>
      <h2 style={{ fontSize: 16 }}>신규 ETF 관찰 후보 (PUSH 2)</h2>
      <p className="helper" style={{ marginTop: 0 }}>
        후보군에 pykrx 1개월 수익률을 적용해 가장 높은 관찰 후보 1건을 보여줍니다.
        본 점검값은 매수 추천이 아닙니다. 갱신은 아래 버튼으로 수동 실행합니다.
        (페이지 새로 고침 시 결과는 사라지며, 갱신을 한 번 더 눌러야 다시 표시됩니다.)
      </p>

      {errorMsg ? <div className="message error">{errorMsg}</div> : null}

      <div className="btn-row" style={{ marginBottom: 8 }}>
        <button
          onClick={onRefresh}
          disabled={loading}
          type="button"
          title="universe seed 의 모든 ticker 에 대해 pykrx 1개월 수익률을 1회 조회 (seed 파일 부재 시 기본 후보군 자동 생성)"
        >
          {loading
            ? "신규 ETF 관찰 후보 갱신 중..."
            : "신규 ETF 관찰 후보 갱신"}
        </button>
      </div>

      {statusNote ? (
        <div className="helper" style={{ marginTop: 4 }}>
          {statusNote}
        </div>
      ) : null}

      {usingStarterSeed ? (
        <div className="helper" style={{ marginTop: 4 }}>
          ⓘ 사용자 seed 파일이 없어 기본 후보군 (starter seed) 으로 동작 중입니다.
          이 기본 후보군은 투자전략 확정값이 아니며, 신규 ETF 관찰 후보 기능 작동
          확인용입니다.
        </div>
      ) : null}

      {!latest ? (
        <div className="helper" style={{ marginTop: 8 }}>
          아직 신규 ETF 관찰 후보 결과가 없습니다. 위 버튼을 눌러 1회 갱신해 주세요.
        </div>
      ) : (
        <div className="summary-card" style={{ marginTop: 8 }}>
          <div className="summary-card-title">
            마지막 갱신: asof {latest.momentum_result.asof} / 기준일{" "}
            {computedBasisDate}
          </div>
          <div className="summary-grid">
            <div className="summary-item">
              <div className="summary-item-label">refresh 상태</div>
              <div className="summary-item-value">
                {refreshStatusLabel(status)}
              </div>
            </div>
            <div className="summary-item">
              <div className="summary-item-label">계산 가능 / 전체</div>
              <div className="summary-item-value">
                {summary?.scored_candidates ?? "—"}/
                {summary?.total_candidates ?? "—"}개
              </div>
            </div>
            <div className="summary-item">
              <div className="summary-item-label">seed freshness</div>
              <div className="summary-item-value">
                {summary?.source_freshness ?? "—"}
              </div>
            </div>
          </div>

          {status !== "failed" && top ? (
            <div className="account-summary" style={{ marginTop: 12 }}>
              <div className="summary-card-title">최상위 후보</div>
              <div className="account-summary-body">
                <div className="kv-row">
                  <span className="k">종목</span>
                  <span className="v">
                    {top.name} ({top.ticker})
                  </span>
                </div>
                <div className="kv-row">
                  <span className="k">1개월 수익률</span>
                  <span className="v">
                    {typeof top.score_result?.score_value === "number"
                      ? `${top.score_result.score_value}%`
                      : "—"}
                  </span>
                </div>
                {top.price_history_basis ? (
                  <div className="kv-row">
                    <span className="k">계산 기준일</span>
                    <span className="v">
                      {top.price_history_basis.base_date} →{" "}
                      {top.price_history_basis.latest_date}
                    </span>
                  </div>
                ) : null}
              </div>
            </div>
          ) : null}

          {status === "failed" && summary?.summary_reason_text ? (
            <div className="summary-warning" style={{ marginTop: 12 }}>
              ⚠ {summary.summary_reason_text}
            </div>
          ) : null}

          {/* Step7C 급락 ETF 주의 신호 상태 표시 (UI 대개편 아님, 최소 표시). */}
          {status !== "failed" ? (
            summary?.falling_candidate ? (
              <div className="summary-warning" style={{ marginTop: 12 }}>
                ⚠ 급락 ETF 주의 신호: {summary.falling_candidate.name} (
                {summary.falling_candidate.ticker}){" "}
                {typeof summary.falling_candidate.score_result?.score_value ===
                "number"
                  ? `${summary.falling_candidate.score_result.score_value}%`
                  : "—"}{" "}
                — 초기 급락 기준{" "}
                {typeof summary.falling_threshold_pct === "number"
                  ? `${summary.falling_threshold_pct}%`
                  : "—"}{" "}
                이하 (확정값 아님 / 매수/매도 지시 아님)
              </div>
            ) : (
              <div className="helper" style={{ marginTop: 12 }}>
                급락 주의 신호 없음 (초기 급락 기준{" "}
                {typeof summary?.falling_threshold_pct === "number"
                  ? `${summary.falling_threshold_pct}%`
                  : "—"}
                )
              </div>
            )
          ) : null}
        </div>
      )}
    </div>
  );
}
