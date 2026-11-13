"use client";

// POC6-27 — 「지금 확인할 내용」 › 시장 흐름(설계 §3 · PLAN 판정 §2 · Q1 · Q9).
// POC6-29(설계 §2 · PLAN §2-2) — C 「시장 배경」 · 「시장 위험 참고」의 핵심을 이 카드에 합쳤다.
// POC6-29 보완 2차(판정서 V2 §2 · S 판정 Q-S1 · §3 · PLAN §10-1 · §10-2) — 처음 화면 = 아침 요약(직전 국내 거래일
//   마감 기준 · 준비 상태 · 아침 판정 · 기준을 채운 자료) → 오늘 시장 변화(네이버 시세 3칸 · 당일 판정).
// 형수님 결정(2026-11-13): 당일 판정 바로 아래 = 시장 판정 근거 표(KODEX 200 · 아침 · 당일) → 코스피 공식 종가 덩어리
//   (20 · 60 · 6개월 칸 · 바로 아래 차트(사용자 결정 ①) · 코스피 지표). 수급 · VIX · 환율 · 유가 근거 · 사건 전체는
//   [시장 근거와 다른 변화 보기](MarketEvidenceFold) 한 번 열면 읽는다.
// 숫자는 응답 칸에서만 읽는다(새 계산 · 문장 파싱 없음).
import type { MarketTopNResponse, PriceSeriesResponse } from "@/lib/api";
import type { QueryState } from "@/lib/api/queryCache";
import { FLOW_LINK_WARN, type MarketFlowContext } from "@/lib/api/marketFlow";
import type { MorningBasisResponse } from "@/lib/api/morningBasis";
import type { QuickQuotesResponse } from "@/lib/api/quickQuotes";
import type { ShortFlowsResponse } from "@/lib/api/shortFlows";
import { md } from "@/lib/todayMarketLines";
import { regimeSentence } from "@/lib/marketNowText";
import { commonClosedRow, todayBasis } from "@/lib/morningText";
import { storedRowText } from "@/lib/refreshCompare";
import MarketNowBlock from "./MarketNowBlock";
import KospiCloseBlock from "./KospiCloseBlock";
import MorningSummary from "./MorningSummary";
import RegimeBasisTable from "./RegimeBasisTable";
import { failOf, joinStale, staleOf } from "./summaryLines";
import { regimeLabelKo } from "./todayHelpers";

export default function MarketFlowBlock({
  market,
  flow,
  series,
  quick,
  morning,
  short,
  onCopy,
  copyDisabled,
  copyMessage,
  copyFallback,
}: {
  market: QueryState<MarketTopNResponse>;
  flow: QueryState<MarketFlowContext>;
  series: QueryState<PriceSeriesResponse>;
  // 빠른 시세 저장값
  quick: QueryState<QuickQuotesResponse>;
  // 아침 요약 기준 · 수급 5거래일(보완 2차)
  morning: QueryState<MorningBasisResponse>;
  short: QueryState<ShortFlowsResponse>;
  onCopy: () => void;
  copyDisabled: boolean;
  copyMessage: string | null;
  // 복사 실패 때 직접 선택해 복사할 글(성공처럼 보이지 않게 · 판정 §4)
  copyFallback: string | null;
}) {
  const ctx = market.phase === "success" ? (market.data.market_context ?? null) : null;
  const fd = flow.phase === "success" ? flow.data : null;
  // 이 카드가 쓰는 원천 중 이전 값을 보이는 것(다시 읽기 실패) · 첫 조회 실패(검증자 F10 — 아침 기준 · 시장 판정 ·
  // 수급 5거래일도 · 첫 조회 실패는 각 자리에서 이미 '확인 불가 · 불러오지 못했습니다'로 보임).
  const stale = joinStale(
    staleOf("아침 요약 기준", morning),
    staleOf("시장 판정", market),
    staleOf("수급 · 환율 · 유가", flow),
    failOf("수급 · 환율 · 유가", flow),
    staleOf("수급 5거래일", short),
    staleOf("KOSPI 가격 흐름", series),
    failOf("KOSPI 가격 흐름", series),
  );
  const note = fd?.flow_link && FLOW_LINK_WARN.includes(fd.flow_link.state) ? `수급 연결: ${fd.flow_link.text}` : null;
  // 당일 판정(형수님 결정 2026-11-13 · 검증자 F8) — 아침 기준 응답의 today_regime: 판정 값과 그 판정이 쓴 끝 행의 저장
  // 시점이 서버의 같은 한 번 읽기. 그 칸이 없으면 시장 판정 응답의 판정 · 날짜만(저장 시점 확인 필요).
  const tb = todayBasis(morning, ctx, market.phase);
  const todayS = regimeSentence(
    tb.ctx,
    tb.ctx ? regimeLabelKo(tb.ctx.regime_code, tb.ctx.regime_label) : "",
    tb.row ? storedRowText(tb.row) : null,
  );
  // 설계자 V3 D2(형수님 선택 2026-11-13) — 아침 · 당일이 같은 유효 응답의 같은 마감 뒤 저장 행이면 상자는 기준만 짧게
  // (판정 문장은 위 아침 요약 · 아래 표 '아침·당일 공통' 행에 있음).
  const common = commonClosedRow(morning);
  const today = common && tb.ctx
    ? {
        key: "regime" as const,
        text: `당일 판정 — 아침과 같은 ${md(common.date)} 마감 뒤 저장값 기준`,
        basis: `${regimeLabelKo(tb.ctx.regime_code, tb.ctx.regime_label)}${
          tb.ctx.regime_streak?.streak_days != null
            ? `(${tb.ctx.regime_streak.streak_days}거래일째${tb.ctx.regime_streak.at_least ? " 이상" : ""})`
            : ""
        } · 판정 근거는 위 아침 요약 · 아래 표`,
        stale: null,
      }
    : todayS
    ? { ...todayS, text: `당일 판정 — ${todayS.text}` }
    : tb.missing
      ? { key: "regime" as const, text: tb.missing, basis: null, stale: null }
      : null;

  return (
    <section className="tc-card tc-flow" aria-label="시장 흐름" data-testid="tc-market-flow">
      <div className="tc-flow-head">
        <div>
          <h3 className="tc-h3">시장 흐름</h3>
          {/* 형수님 결정(2026-11-13 · 마감 뒤 화면 조절) — 기호식 안내 줄은 뺐다. 각 구역 제목 옆에 기준이 이미 있다
              ('아침 요약 · M/D 마감 기준' · '오늘 시장 변화 M/D … · 네이버 시세 · 마지막 조회 …') · 근거는 접기 제목이 안내. */}
        </div>
        <button type="button" className="btn-md tc-fold-btn" onClick={onCopy} disabled={copyDisabled}>
          AI용 시장 정보 복사
        </button>
      </div>
      {copyMessage ? (
        <p className={copyFallback ? "tc-warn tc-small" : "tc-muted tc-small"} data-testid="tc-copy-message">
          {copyMessage}
        </p>
      ) : null}
      {copyFallback ? (
        <textarea className="tc-copy-fallback" readOnly value={copyFallback} rows={10} aria-label="복사할 시장 정보" />
      ) : null}

      <MorningSummary morning={morning} market={market} flow={flow} short={short} />
      <MarketNowBlock quick={quick} today={today}>
        <RegimeBasisTable market={market} morning={morning} />
        <KospiCloseBlock market={market} flow={flow} morning={morning} />
      </MarketNowBlock>

      {note ? <div className="tc-sum-note">{note}</div> : null}
      {stale ? <div className="tc-sum-stale">{stale}</div> : null}
    </section>
  );
}
