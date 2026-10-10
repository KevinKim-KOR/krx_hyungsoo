"use client";

// POC5-06 설계 개정 2 §2 · §10-5 — 재진입 검토 창(History 창 자리를 대신 열고, '← History'로 돌아간다 ·
// 창 위에 창을 겹치지 않는다). 열 때 GET /holdings/trade-history/reentry-review 1회(학습 · 외부 조회 ·
// 쓰기 0). 세 부분: 1 내 거래 · 2 저장된 근거(ReentryEvidence) · 3 ML 검토(ReentryMlPanel · 누를 때만).
// 가격은 '저장 종가 YYYY-MM-DD 기준' · 늦으면 '이 날짜 기준 검토'. [재매수]는 05 매매 창을 연다(ML
// 결과와 연결 없음). 보유가 바뀌어 기간을 찾지 못하면(404) 다시 열라는 문구를 보인다.

import { useEffect, useState } from "react";
import {
  fetchReentryReview,
  type HoldingCycleView,
  type PositionHistory,
  type ReentryReviewResponse,
} from "@/lib/api";
import Dialog from "./Dialog";
import ReentryEvidence from "./ReentryEvidence";
import ReentryMlPanel from "./ReentryMlPanel";
import { apiErrorText, fmtWon, pnlClass } from "./format";
import { dash, pct, savedAt, signedWon } from "./historyText";

interface Props {
  positionId: string;
  cycleId: string;
  onBack: () => void;
  onClose: () => void;
  onNavigate?: (menu: string) => void;
  onTrade?: (position: PositionHistory) => void;
}

function periodOf(c: HoldingCycleView): string {
  const start = c.start_date ?? "매수일 미상";
  return c.status === "OPEN" ? `보유 중 · ${start} ~` : `${start} ~ ${c.end_date ?? "—"}`;
}

function cycleBrief(c: HoldingCycleView) {
  if (c.status === "OPEN") {
    const avg = c.avg_buy_price ? fmtWon(c.avg_buy_price) : "—";
    return <>{`${dash(c.quantity, 6)}주 · 평단 ${avg}`}</>;
  }
  return (
    <>
      실현 <span className={pnlClass(c.realized_pnl)}>{signedWon(c.realized_pnl)}</span> ·{" "}
      <span className={pnlClass(c.realized_rate)}>{pct(c.realized_rate)}</span>
      {c.closed_by === "ADJUSTMENT" ? " · 입력 정정으로 종료" : ""}
    </>
  );
}

function MyTrades({ data }: { data: ReentryReviewResponse }) {
  const { position, selected_cycle_id, previous_cycle_ids, summary, notes } = data.my_trades;
  const cycle = position.cycles.find((c) => c.cycle_id === selected_cycle_id);
  const previous = position.cycles.filter((c) => previous_cycle_ids.includes(c.cycle_id));
  return (
    <section className="hmx-rv-part" aria-labelledby="rv-p1">
      <h4 id="rv-p1">
        <span className="hmx-rv-n">1</span>내 거래
      </h4>
      <dl className="hmx-rv-kv">
        <dt>선택 기간</dt>
        <dd>
          {cycle ? (
            <>
              {periodOf(cycle)} · {cycleBrief(cycle)}
            </>
          ) : (
            "—"
          )}
        </dd>
        <dt>이전 기간</dt>
        <dd>
          {previous.length === 0
            ? "없음"
            : previous.map((c) => (
                <div key={c.cycle_id}>
                  {periodOf(c)} · {cycleBrief(c)}
                </div>
              ))}
        </dd>
        <dt>마지막 실제 매도</dt>
        <dd>{summary.last_actual_sell_date ?? "이 기간에는 없음"}</dd>
        {notes.length > 0 ? (
          <>
            <dt>안내</dt>
            <dd className="muted hmx-small">
              {notes.map((n) => (
                <div key={n}>{n}</div>
              ))}
            </dd>
          </>
        ) : null}
      </dl>
      <p className="muted hmx-small" style={{ margin: "6px 0 0" }}>
        계좌 · 기간별 손익은 합치지 않습니다. 체결단가 기준 · 수수료 · 세금 · 배당 미반영.
      </p>
    </section>
  );
}

export default function ReentryReviewDialog({
  positionId,
  cycleId,
  onBack,
  onClose,
  onNavigate,
  onTrade,
}: Props) {
  const [data, setData] = useState<ReentryReviewResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    fetchReentryReview(positionId, cycleId).then(
      (r) => live && setData(r),
      (e: unknown) => live && setError(apiErrorText(e)),
    );
    return () => {
      live = false;
    };
  }, [positionId, cycleId]);

  const sel = data?.selection;
  const ps = data?.stored_evidence.price_state;
  const sum = data?.my_trades.summary;
  const title = sel
    ? `재진입 검토 — ${sel.name || sel.ticker} · ${sel.account_group} · ${sum?.status === "OPEN" ? "보유 중 기간" : "지난 보유 기간"}`
    : "재진입 검토";
  const basis = ps?.t ? `저장 종가 ${ps.t} 기준` : "저장 종가 기준";
  const footer = data ? (
    <div className="hmx-rv-foot">
      <span className="muted hmx-small">
        이 값은 매수/매도 지시가 아닙니다 · 읽은 기준: 보유 문서 revision {data.read_basis.revision} · 문서
        hash {data.read_basis.doc_sha256.slice(0, 12)}
        {data.read_basis.ledger_synced_at ? ` · 원장 동기화 ${savedAt(data.read_basis.ledger_synced_at)}` : ""}
        {data.read_basis.price_latest ? ` · 가격 ${data.read_basis.price_latest}` : ""}
      </span>
      {onTrade ? (
        <button
          type="button"
          className="hmx-btn-sm hmx-ghost"
          onClick={() => onTrade(data.my_trades.position)}
        >
          {data.my_trades.position.is_open ? "매매(매매 창)" : "재매수(매매 창)"}
        </button>
      ) : null}
    </div>
  ) : null;

  return (
    <Dialog title={title} subtitle={data ? basis : null} onClose={onClose} wide footer={footer}>
      <button type="button" className="hmx-rv-back" onClick={onBack}>
        ← History
      </button>
      {ps?.stale ? (
        <div className="hmx-small" style={{ margin: "2px 0 8px" }}>
          <span className="hmx-tag hmx-tag-warn">{ps.stale_note ?? "이 날짜 기준 검토"}</span>{" "}
          <span className="muted">(기대 완료일 {ps.expected_completed_date})</span>
        </div>
      ) : null}
      {!data && !error ? <p className="muted hmx-small">재진입 검토를 불러오는 중…</p> : null}
      {error ? (
        <div className="hmx-error" role="alert">
          {error}
        </div>
      ) : null}
      {data ? (
        <div className="hmx-rv-body">
          <MyTrades data={data} />
          <ReentryEvidence
            priceState={data.stored_evidence.price_state}
            marketFlow={data.stored_evidence.market_flow}
            ledger={data.stored_evidence.ledger}
            navigation={data.navigation}
            onNavigate={onNavigate}
          />
          <ReentryMlPanel
            positionId={positionId}
            cycleId={cycleId}
            available={data.ml.available}
            targetName={data.ml.target_name}
          />
        </div>
      ) : null}
    </Dialog>
  );
}
