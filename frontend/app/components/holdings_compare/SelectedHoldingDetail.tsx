"use client";

// 선택 보유 상세 (2026-08-19 사용자 실화면 직접 지시).
//
// 2026-08-16 카드 전환 때 이 영역에서 평가 비중·손익률·20일 KODEX 초과 3줄을
// 뺐다(카드에 같은 값이 보여 중복). 그런데 **대신 채울 것을 넣지 않아** 종목명
// 한 줄만 남았고, 배치 정정으로 전체 폭에 내려오자 빈 영역이 드러났다.
//
// 여기 놓는 값은 전부 이미 응답에 있는 것들이고 **카드에 없는 것만** 고른다.
// 새로 계산하거나 문구를 지어내지 않는다 — `evidence_notes` 는 백엔드가 만든
// 문장을 그대로 나열한다.
//
// 상태 표기는 기존 계약을 따른다: 값이 없으면 채우지 않고 "확인 불가" /
// "확인 전" 으로 구분해 적는다(미포함과 확인 불가는 다른 상태다).

import type { EnrichedHolding, HoldingsMarketEvidenceItem } from "@/lib/api";
import { type AggregatedHolding, DASH, fmtPct, returnColor } from "./helpers";

// topn_match.basis 를 사람이 읽는 말로. 값을 만들지 않고 이름만 붙인다.
const BASIS_LABEL: Record<string, string> = {
  daily: "일간",
  one_month: "1개월",
  three_month: "3개월",
};

function fmtInt(v: number | null | undefined): string {
  if (v === null || v === undefined) return DASH;
  return Math.round(v).toLocaleString("ko-KR");
}

function Row({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="hcd-row">
      <span className="hcd-k">{label}</span>
      <span className="hcd-v">{children}</span>
    </div>
  );
}

function Pct({ v }: { v: number | null | undefined }) {
  return <b style={{ color: returnColor(v) }}>{fmtPct(v)}</b>;
}

export default function SelectedHoldingDetail({
  holding,
  rows,
  evidence,
  evidenceLoaded,
}: {
  holding: AggregatedHolding;
  // 같은 ticker 의 계좌별 원본 행. 수량·평균단가는 계좌마다 다를 수 있다.
  rows: EnrichedHolding[];
  evidence: HoldingsMarketEvidenceItem | undefined;
  evidenceLoaded: boolean;
}) {
  const qty = rows.reduce((acc, r) => acc + r.quantity, 0);
  const accounts = Array.from(
    new Set(rows.map((r) => r.account_group ?? "일반")),
  );
  // 다계좌 평균단가는 대표값을 만들지 않는다 (기존 "계좌별 상이" 계약).
  const avgPrices = Array.from(new Set(rows.map((r) => r.avg_buy_price)));
  const evalCount = rows.filter((r) => r.eval_amount != null).length;

  const tm = evidence?.topn_match;
  const sm = evidence?.short_term_momentum;
  const nav = evidence?.nav_discount;
  const ov = evidence?.constituents_overlap;
  const notes = evidence?.evidence_notes ?? [];

  const topnText = (() => {
    if (!evidenceLoaded) return "확인 전";
    if (!tm) return "확인 불가";
    if (tm.status === "matched_topn_candidate") {
      const basis = tm.basis ? BASIS_LABEL[tm.basis] ?? tm.basis : null;
      const rank = tm.rank != null ? `${tm.rank}위` : "포함";
      return basis ? `현재 후보 ${rank} (${basis} 기준)` : `현재 후보 ${rank}`;
    }
    if (tm.status === "not_in_current_topn") return "현재 후보 목록에 없음";
    return "확인 불가";
  })();

  const smOk = sm?.status === "ok";
  const navOk = nav?.status === "ok" || nav?.status === "warning";

  return (
    <div className="hcd">
      <div className="hcd-head">
        <strong>{holding.name ?? holding.ticker}</strong>
        <code className="hcd-tk">{holding.ticker}</code>
        {accounts.map((a) => (
          <span className="hcd-acc" key={a}>
            {a}
          </span>
        ))}
      </div>

      <div className="hcd-body">
        <Row label="보유 내역">
          {fmtInt(qty)}주
          <span className="hcd-sep">·</span>
          평균단가{" "}
          {avgPrices.length === 1 ? (
            <b>{fmtInt(avgPrices[0])}원</b>
          ) : (
            <span className="hcd-warn">계좌별 상이</span>
          )}
          <span className="hcd-sep">·</span>
          평가금액{" "}
          {holding.eval_amount == null ? (
            <span className="hcd-muted">자료 확인 필요</span>
          ) : (
            <>
              <b>{fmtInt(holding.eval_amount)}원</b>
              {holding.eval_partial_unavail ? (
                <span className="hcd-warn">
                  {" "}
                  ({evalCount}/{rows.length})
                </span>
              ) : null}
            </>
          )}
        </Row>

        <Row label="후보 관계">{topnText}</Row>

        <Row label="단기 흐름">
          {smOk ? (
            <>
              5일 <Pct v={sm?.return_5d_pct} />
              <span className="hcd-sep">·</span>
              10일 <Pct v={sm?.return_10d_pct} />
              <span className="hcd-sep">·</span>
              20일 <Pct v={sm?.return_20d_pct} />
            </>
          ) : (
            <span className="hcd-muted">
              {evidenceLoaded ? "자료 확인 필요" : "확인 전"}
            </span>
          )}
        </Row>

        <Row label="KODEX 대비">
          {smOk ? (
            <>
              5일 <Pct v={sm?.excess_vs_kodex200_5d_pctp} />
              <span className="hcd-sep">·</span>
              10일 <Pct v={sm?.excess_vs_kodex200_10d_pctp} />
              <span className="hcd-sep">·</span>
              20일 <Pct v={sm?.excess_vs_kodex200_20d_pctp} />
            </>
          ) : (
            <span className="hcd-muted">
              {evidenceLoaded ? "자료 확인 필요" : "확인 전"}
            </span>
          )}
        </Row>

        <Row label="NAV 괴리">
          {navOk ? (
            <>
              NAV <b>{fmtInt(nav?.nav)}</b>
              <span className="hcd-sep">/</span>
              시장가 <b>{fmtInt(nav?.market_price)}</b>
              <span className="hcd-sep">→</span>
              <Pct v={nav?.discount_rate_pct} />
              {nav?.asof ? <span className="hcd-asof">{nav.asof}</span> : null}
              {nav?.message ? (
                <span className="hcd-warn"> {nav.message}</span>
              ) : null}
            </>
          ) : (
            <span className="hcd-muted">
              {evidenceLoaded ? "확인 불가" : "확인 전"}
            </span>
          )}
        </Row>

        <Row label="구성종목 겹침">
          {!evidenceLoaded ? (
            <span className="hcd-muted">확인 전</span>
          ) : ov?.status === "ok" ? (
            ov.overlap_with_market_core.length === 0 ? (
              <span className="hcd-muted">겹치는 핵심 종목 없음</span>
            ) : (
              <span className="hcd-chips">
                {ov.overlap_with_market_core.map((o, i) => (
                  <span className="hcd-chip" key={`${o.ticker ?? o.name ?? i}`}>
                    {o.name ?? o.ticker ?? DASH}
                    {o.weight_pct != null ? ` ${o.weight_pct.toFixed(2)}%` : ""}
                  </span>
                ))}
              </span>
            )
          ) : (
            <span className="hcd-muted">확인 불가</span>
          )}
        </Row>

        {notes.length > 0 ? (
          <Row label="확인 근거">
            <ul className="hcd-notes">
              {notes.map((n, i) => (
                <li key={i}>{n}</li>
              ))}
            </ul>
          </Row>
        ) : null}
      </div>
    </div>
  );
}
