"use client";

// 현재 run 의 status / draft_payload 표시 + Approve / Reject + 느린 polling.
// 부모(MainPanel) 가 run state 를 controlled 로 관리한다 (run / setRun prop).
//
// Step 2C 변경:
// - draft_payload.recommendations 가 holdings 형태이면 compact UI 로 렌더 (전체 요약 +
//   계좌별 요약 + compact table + 상세 펼침). 기존 카드 나열 형식 폐지.
// - account_group / source_index 는 신규 draft_payload 에는 항상 포함되지만 과거 run
//   에는 없을 수 있다 → 누락 시 "일반" / 행 인덱스 fallback. KeyError 발생 안 함.
// - 상세 펼침 상태는 항목 식별자(source_index|ticker|account_group|avg_buy_price) 단위로
//   유지된다. polling 으로 동일 run 의 동일 항목이 다시 패치되어도 펼친 상태 유지.
// - 새 run 으로 전환되면 펼침 상태 초기화.

import { useCallback, useEffect, useRef } from "react";
import {
  ApiConfigError,
  ApiRequestError,
  approveRun,
  fetchRun,
  isTerminal,
  rejectRun,
  type Run,
  type RunStatus,
} from "@/lib/api";
import {
  computeSummaryFor,
  fmtMoney,
  fmtSignedMoney,
  fmtSignedPct,
  normalizeRec,
  pnlClass,
  type Summary,
} from "@/lib/holdings_view";
import EvidenceDetails from "./EvidenceDetails";
import JudgmentReasonSection from "./JudgmentReasonSection";
import { pickMomentumCandidates } from "./MomentumCandidatesSection";

const POLL_INTERVAL_MS = 12000;
const MAX_POLL_TICKS = 30;

function humanLabel(status: RunStatus): string {
  switch (status) {
    case "PENDING_APPROVAL":
      return "승인 대기";
    case "DELIVERING":
      return "전달 중";
    case "COMPLETED":
      return "전달 완료";
    case "REJECTED":
      return "거절됨";
    case "FAILED":
      return "실패";
  }
}

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

function isHoldingsRec(r: Record<string, unknown>): boolean {
  return "quantity" in r || "avg_buy_price" in r;
}




// ─── compact 렌더링 컴포넌트 ────────────────────────────────────

export function OverallSummaryCard({ summary }: { summary: Summary }) {
  const calcBasis =
    summary.calc_available_count > 0
      ? `(평가 계산 ${summary.calc_available_count}개 기준)`
      : "";
  const hasUnpriced =
    summary.unpriced_count > 0 || summary.calc_missing_count > 0;

  return (
    <div className="summary-card">
      <div className="summary-card-title">전체 요약</div>
      <div className="summary-grid">
        <SummaryItem label="보유 종목" value={`${summary.total_count}개`} />
        <SummaryItem label="시세 확인" value={`${summary.priced_count}개`} />
        <SummaryItem label="시세 미확인" value={`${summary.unpriced_count}개`} />
        {summary.calc_missing_count > 0 ? (
          <SummaryItem
            label="계산 정보 부족"
            value={`${summary.calc_missing_count}개`}
          />
        ) : null}
        <SummaryItem
          label="총 매입금액"
          value={fmtMoney(summary.total_invested) ?? "-"}
        />
        {summary.calc_available_count > 0 ? (
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




// ─── Step 2D — 승인 초안 영역 (preview 우선 + 전체 요약 기본 + 근거 데이터 접힘) ───
//
// 표시 정책:
// 1. 최신 run + message_text 있음 → preview block + 전체 요약(기본) + 근거 데이터(접힘)
// 2. 과거 run + message_text 없음 + holdings draft → 정적 안내 문구 + 전체 요약(기본) + 근거 데이터(펼침)
// 3. 비-holdings(샘플) draft → 기존처럼 raw recommendations 한 줄 표시 (preview 없음)
// 4. 빈 payload → "초안 본문이 없습니다" 안내
//
// 프론트엔드는 message_text 를 절대 조립/파싱하지 않는다. 백엔드가 내려준 원본만 그대로 렌더링.

const LEGACY_FALLBACK_NOTICE =
  "이 과거 초안은 전송 메시지 미리보기를 지원하지 않습니다. " +
  "아래 근거 데이터에서 초안 내용을 확인하세요.";

function MessagePreview({ messageText }: { messageText: string }) {
  return (
    <div className="preview-block">
      <div className="preview-header">전송 메시지 미리보기</div>
      <pre className="preview-body">{messageText}</pre>
    </div>
  );
}

function LegacyFallback() {
  return <div className="message info">{LEGACY_FALLBACK_NOTICE}</div>;
}


// CompactHoldingsTable 은 기존에 expanded/onToggle 을 prop 으로 받음.
// 근거 데이터 펼침 안에서 행별 상세 펼침 상태를 별도로 보존하려면 자기 상태를 가져야 하므로
// wrapper 를 둔다 (기존 컴포넌트 재사용).

// Step 5D Cleanup: pickPortfolioFactorSignal / pickMomentumBullet / JudgmentReasonSection /
// pickMomentumCandidates / MomentumCandidatesSection 은 별도 컴포넌트로 분리되었다:
// - frontend/app/components/JudgmentReasonSection.tsx
// - frontend/app/components/MomentumCandidatesSection.tsx
// 분리 전후 렌더링 / 문구 / 배치 / 동작 동일.

function ApprovalDraftBody({ run }: { run: Run }) {
  const payload = run.draft_payload ?? {};
  const recs = (payload as Record<string, unknown>).recommendations;
  const note = (payload as Record<string, unknown>).note;
  const messageText =
    typeof run.message_text === "string" && run.message_text.length > 0
      ? run.message_text
      : null;
  const momentumBundle = pickMomentumCandidates(payload as Record<string, unknown>);

  const hasRecs = Array.isArray(recs) && recs.length > 0;
  const hasNote = typeof note === "string" && note.length > 0;
  const recsList = hasRecs
    ? (recs as Array<Record<string, unknown>>)
    : ([] as Array<Record<string, unknown>>);
  const isHoldings =
    recsList.length > 0 &&
    typeof recsList[0] === "object" &&
    recsList[0] !== null &&
    isHoldingsRec(recsList[0]);

  // 빈 payload — 안내만
  if (!hasRecs && !hasNote && !messageText) {
    return <div className="message info">초안 본문이 없습니다.</div>;
  }

  // 비-holdings 샘플 초안 — preview 미지원. raw 는 기본 접힘 details 안으로만 노출.
  // Step 2D AC13: raw JSON 은 기본 노출되지 않는다.
  if (hasRecs && !isHoldings) {
    return (
      <div>
        <LegacyFallback />
        {hasNote ? (
          <div className="summary-text" style={{ marginTop: 10 }}>
            {note as string}
          </div>
        ) : null}
        <details className="evidence-details" style={{ marginTop: 12 }}>
          <summary>근거 데이터 펼쳐보기 (샘플 recommendations 원본)</summary>
          <ul className="reco-list" style={{ marginTop: 10 }}>
            {recsList.map((r, idx) => (
              <li key={idx}>
                <code>{JSON.stringify(r)}</code>
              </li>
            ))}
          </ul>
        </details>
      </div>
    );
  }

  // holdings draft — preview / 정적 안내 + 전체 요약 + 판단 사유 + 근거 데이터(접힘/펼침)
  const normRecs = recsList.map((r, idx) => normalizeRec(r, idx));
  const summary = computeSummaryFor(normRecs);
  const evidenceDefaultOpen = messageText === null;

  return (
    <div>
      {messageText !== null ? (
        <MessagePreview messageText={messageText} />
      ) : (
        <LegacyFallback />
      )}
      {hasNote ? (
        <div className="summary-text" style={{ marginTop: 10 }}>
          {note as string}
        </div>
      ) : null}
      <div style={{ marginTop: 12 }}>
        <OverallSummaryCard summary={summary} />
      </div>
      <JudgmentReasonSection run={run} />
      <EvidenceDetails
        recs={normRecs}
        defaultOpen={evidenceDefaultOpen}
        momentumBundle={momentumBundle}
      />
    </div>
  );
}

interface Props {
  run: Run;
  setRun: (run: Run | null) => void;
  loading: boolean;
  setLoading: (b: boolean) => void;
  errorMsg: string | null;
  setErrorMsg: (s: string | null) => void;
}

export default function RunPanel({
  run,
  setRun,
  loading,
  setLoading,
  errorMsg,
  setErrorMsg,
}: Props) {
  const pollTickRef = useRef<number>(0);

  // DELIVERING 만 polling. terminal 도달 시 즉시 중단.
  useEffect(() => {
    if (run.status !== "DELIVERING") {
      pollTickRef.current = 0;
      return;
    }
    const id = window.setInterval(async () => {
      pollTickRef.current += 1;
      if (pollTickRef.current > MAX_POLL_TICKS) {
        window.clearInterval(id);
        setErrorMsg(
          "DELIVERING 상태가 너무 오래 지속됩니다. '상태 새로고침' 을 눌러 확인해 주세요."
        );
        return;
      }
      try {
        const latest = await fetchRun(run.run_id);
        setRun(latest);
      } catch (e) {
        setErrorMsg(describeApiError(e));
      }
    }, POLL_INTERVAL_MS);
    return () => window.clearInterval(id);
  }, [run, setRun, setErrorMsg]);

  const onApprove = useCallback(async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const next = await approveRun(run.run_id);
      setRun(next);
    } catch (e) {
      setErrorMsg(describeApiError(e));
    } finally {
      setLoading(false);
    }
  }, [run, setRun, setLoading, setErrorMsg]);

  const onReject = useCallback(async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const next = await rejectRun(run.run_id);
      setRun(next);
    } catch (e) {
      setErrorMsg(describeApiError(e));
    } finally {
      setLoading(false);
    }
  }, [run, setRun, setLoading, setErrorMsg]);

  const onRefresh = useCallback(async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const latest = await fetchRun(run.run_id);
      setRun(latest);
    } catch (e) {
      setErrorMsg(describeApiError(e));
    } finally {
      setLoading(false);
    }
  }, [run, setRun, setLoading, setErrorMsg]);

  const onReset = useCallback(() => {
    setRun(null);
    setErrorMsg(null);
    pollTickRef.current = 0;
  }, [setRun, setErrorMsg]);

  const canApproveOrReject = run.status === "PENDING_APPROVAL";
  const showTerminalReset = isTerminal(run.status);

  return (
    <>
      {errorMsg ? <div className="message error">{errorMsg}</div> : null}

      <div className="card">
        <h2>2. 현재 진행 상황</h2>
        <div className="status-row">
          <span className={`status-badge status-${run.status}`}>
            {humanLabel(run.status)}
          </span>
          <span className="kv">
            <span className="k">run_id</span>
            <span className="v">
              <code>{run.run_id}</code>
            </span>
          </span>
          <span className="kv">
            <span className="k">asof</span>
            <span className="v">{run.asof}</span>
          </span>
        </div>
        <div className="helper">
          백엔드 status: <code>{run.status}</code>
          {run.status === "DELIVERING" ? " (자동 상태 확인 중, 약 12초 간격)" : ""}
        </div>
      </div>

      <div className="card">
        <h2>3. 승인 초안 (전송 메시지 미리보기)</h2>
        <ApprovalDraftBody run={run} />
      </div>

      <div className="card">
        <h2>4. 다음 행동</h2>
        {canApproveOrReject ? (
          <div className="btn-row">
            <button onClick={onApprove} disabled={loading} type="button">
              승인 (Approve)
            </button>
            <button
              className="reject"
              onClick={onReject}
              disabled={loading}
              type="button"
            >
              거절 (Reject)
            </button>
          </div>
        ) : (
          <div className="message info">
            {run.status === "DELIVERING"
              ? "외부 전달이 진행 중입니다. 잠시 후 상태가 자동으로 갱신됩니다."
              : "이 run 은 종결 상태입니다. 새 시도는 새 run_id 로만 가능합니다."}
          </div>
        )}
        <div
          className="btn-row"
          style={{ marginTop: canApproveOrReject ? 12 : 0 }}
        >
          <button
            className="reject"
            onClick={onRefresh}
            disabled={loading}
            type="button"
          >
            상태 새로고침
          </button>
          {showTerminalReset ? (
            <button onClick={onReset} disabled={loading} type="button">
              새 초안 시작
            </button>
          ) : null}
        </div>
      </div>
    </>
  );
}
