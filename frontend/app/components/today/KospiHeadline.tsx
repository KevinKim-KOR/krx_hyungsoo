"use client";

// POC3-OPS-02B-2-KS10-TRIGGER-FILE-SPLIT (2026-09-13)
// `TodayInvestmentCheckView.tsx` 가 907줄로 KS-10 프론트 임계(>900)를 넘어
// 책임별로 분리했다. 분리 때는 JSX·문구·className·핸들러·호출 조건을 고치지 않았다
// (파일 배치와 import/export 줄만). 그 뒤 화면은 POC5-09 · POC5-UI-03 에서 바뀌었다.

import { useState } from "react";
import type { QueryState } from "@/lib/api/queryCache";
import type {
  MarketContextKospi,
  MarketTopNResponse,
  StoredVolumeEvidence,
} from "@/lib/api";
import { KOSPI_SOURCE_LINE, kospiStatusView, kospiValuesUsable } from "@/lib/kospiStatus";
import StoredVolumeBlock from "../StoredVolumeBlock";
import { KODEX200_VOLUME_HELP, NO_VOLUME_TEXT, volumeCells } from "@/lib/storedVolume";
import { KospiStatusBadges, KospiStatusLines } from "../KospiStatusNote";
import {
  fmtKstDate,
  fmtPct,
} from "./todayHelpers";

// ── §4.1 코스피 대표 (헤드라인) — 첫 화면 필수 요소만 compact ────────────────
// 코스피 차트 + [별도] KODEX200 기준선 대비 위치. 코스피와 KODEX200 을 하나로 묶지 않는다
// (§3.1 강제 분리 · FAIL 조건).
// POC5-UI-03 — 오른쪽 열은 코스피 일간 변화 · KODEX200 기준선(MA20 · MA60 · 기준일)만 둔다.
// 코스피 1개월 · 3개월 · 1년 · 고점 대비 · 기존 시장 판정 · KODEX200 거래량은 카드 아래
// '시장 수치와 거래량'에서 펼쳐 본다(기본 접힘 · 화면 안 상태만). 접힌 칸의 자료 없음 · 부족 ·
// 계산 불가는 펼치기 전후 모두 버튼 옆 '확인 필요: …'로 보인다(설계 §3 · 판정 Q3).
// POC6-27 — 차트는 「시장 흐름」 안 코스피 수치 바로 아래로 옮겼고(사용자 결정 ①) · 흐름 두 줄은 시장 흐름
// 구역이 대신한다. 이 부품은 코스피 공식 종가 덩어리(POC6-29 · 형수님 결정 2026-11-13 · 「오늘 시장 변화」 당일 판정 아래 ·
// KospiCloseBlock) 안에서 나머지 지표(일간 변화 · KODEX200 기준선 · '시장 수치와 거래량')만 문구 그대로 보인다(판정 Q1 (a)).
// embedded 는 그 자리 표시(카드 테두리 · 제목 없음).
// 설계자 RESULT 재판정 V3(2026-11-13): D3 — 'KODEX200 기준선 대비 위치'(MA20 · MA60 거리 · ⓘ 이 값의 한계)는 판정 표의
//   '20일선 87,415원 · 3.63% 아래'와 겹쳐 뺐다(한계 문장은 판정 표 제목 옆 [?]). D4 — 「시장 수치와 거래량」 안
//   '기존 시장 판정 참고'(국면 · 지속일 · KODEX200 기준일)는 당일 판정 · 판정 표와 겹쳐 뺐다. 그 둘에 딸린 접힌 칸 안내
//   ('시장 판정 확인 불가' · '기존 시장 판정 지속일 자료 없음')도 함께 뺐다.
export default function KospiHeadline({
  market,
  startOpen = false,
}: {
  market: QueryState<MarketTopNResponse>;
  embedded?: boolean;
  // POC6-29 보완 2차 — 오늘 점검에서는 처음부터 펼친다(두 번째 접기 정리 · 판정서 V2 §2 · 지금 자리는 KospiCloseBlock).
  startOpen?: boolean;
}) {
  const ctx =
    market.phase === "success" ? market.data.market_context ?? null : null;
  const kospi = ctx?.kospi;
  // 설계자 RESULT STEP 4-3 — '마지막 자료 기준일' 은 KOSPI 기준일이다(KODEX200 날짜 아님).
  // KOSPI 기준일이 없으면 날짜를 내지 않는다(다른 날짜로 대신하지 않는다).
  const kospiAsOf = kospi?.as_of_date ?? null;
  const [open, setOpen] = useState(startOpen);
  // UI-03 — 일간 값은 화면 판정(정상 · 휴장)일 때만. 아니면 상태 사유 문장만 둔다
  // (배지 · 기준 줄은 같은 카드 차트 아래와 접힌 '코스피 수익률·위치'에 그대로 있다).
  const kv = kospiStatusView(kospi, market.phase);
  const vol = market.phase === "success" ? market.data.kodex200_stored_volume ?? null : null;
  const foldNotes = foldedMarketNotes(market, kospi, vol);

  return (
    <section className="tc-headline tc-headline-embedded" aria-label="KOSPI 현재 위치">
      <div className="tc-headline-grid tc-headline-grid-embedded">
        <div className="tc-headline-stats">
          <div className="tc-stat-block" data-testid="tc-kospi-daily">
            <div className="tc-label">코스피 일간 변화</div>
            {kospiValuesUsable(kospi) && kospi ? (
              <div className="tc-big-value">
                {kospi.daily_return_pct != null ? fmtPct(kospi.daily_return_pct) : "자료 없음"}
              </div>
            ) : kv.loading ? (
              <div className="kospi-status-loading">확인 중</div>
            ) : (
              <div className="kospi-status-reason">{kv.reason ?? "자료 없음"}</div>
            )}
          </div>

          {/* 설계자 RESULT STEP 4-2 — 공식 자료원 표시(KRX 약관 제10조③). 차트 · 수익률을
              합친 이 카드에 한 줄(기준일과 같은 줄). */}
          <div className="tc-muted tc-small tc-divider" style={{ paddingTop: 12 }}>
            {kospiAsOf ? `마지막 자료 기준일 ${fmtKstDate(kospiAsOf)} · ` : null}
            {KOSPI_SOURCE_LINE}
          </div>
        </div>
      </div>

      <div className="tc-fold-row tc-divider">
        <button
          type="button"
          className="btn-md tc-fold-btn"
          aria-expanded={open}
          onClick={() => setOpen((v) => !v)}
        >
          {open ? "시장 수치와 거래량 접기" : "시장 수치와 거래량 펼치기"}
        </button>
        {foldNotes.length > 0 ? (
          <span className="tc-warn tc-small" data-testid="tc-market-fold-notes">
            확인 필요: {foldNotes.join(" · ")}
          </span>
        ) : null}
      </div>

      {open ? (
        <div className="tc-market-detail" data-testid="tc-market-detail">
          {/* 코스피 수익률·위치 (저장 KOSPI 시계열 기반 · POC3-06 §6.2 실제값). 최신성 상태 배지 ·
              기준 줄 · 사유 줄은 「요즘 잘 오르는 ETF」 시장 배경 카드와 같은 생성기(KospiStatusNote). */}
          <div className="tc-stat-block">
            <div className="tc-label">
              코스피 수익률·위치{" "}
              <KospiStatusBadges kospi={kospi} phase={market.phase} />
            </div>
            {kospi && kospi.status === "ok" ? (
              <ul className="tc-list-plain">
                <li>1개월 {fmtPct(kospi.return_1m_pct)}</li>
                <li>3개월 {fmtPct(kospi.return_3m_pct)}</li>
                <li>
                  1년{" "}
                  {kospi.return_1y_pct != null
                    ? fmtPct(kospi.return_1y_pct)
                    : "자료 없음"}
                </li>
                <li>
                  최근 1년 고점 대비{" "}
                  {kospi.high_52w_gap_pct != null
                    ? fmtPct(kospi.high_52w_gap_pct)
                    : "자료 없음"}
                </li>
              </ul>
            ) : null}
            <KospiStatusLines kospi={kospi} phase={market.phase} />
          </div>

          {/* POC5-09 — KODEX200 한 종목의 저장 거래량(KOSPI 지수 거래량 아님 · 자기 기준일). */}
          {market.phase === "success" ? (
            <div className="tc-stat-block">
              <StoredVolumeBlock
                title="KODEX200 거래량"
                ev={market.data.kodex200_stored_volume}
                help={KODEX200_VOLUME_HELP}
                columns={2}
                headClassName="tc-label"
              />
            </div>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

// UI-03 설계 §3 · 판정 Q3 — 접힌 칸 안의 자료 없음 · 부족 · 계산 불가 · 확인 불가를 기존 문구로 모은다.
// 서로 다른 사유는 따로 둔다. 값이 비어 있다는 것만으로 위험 · 하락 신호를 만들지 않는다.
function foldedMarketNotes(
  market: QueryState<MarketTopNResponse>,
  kospi: MarketContextKospi | null | undefined,
  vol: StoredVolumeEvidence | null,
): string[] {
  const notes: string[] = [];
  if (market.phase !== "success") return notes;
  // 코스피 수익률 칸은 값을 보일 때(운영 판정 ok)만 빈 값을 센다 — 아니면 상태 사유가 이미 보인다.
  if (kospi && kospi.status === "ok") {
    // 펼친 칸에서 '자료 없음'으로 그리는 두 값만(1개월 · 3개월은 운영 판정 ok 면 늘 산출 · 표시는 '-').
    const kospiCells: [string, number | null | undefined][] = [
      ["1년", kospi.return_1y_pct],
      ["최근 1년 고점 대비", kospi.high_52w_gap_pct],
    ];
    for (const [label, v] of kospiCells) {
      if (v == null) notes.push(`코스피 ${label} 자료 없음`);
    }
  }
  if (!vol || vol.status === "no_price_data") {
    notes.push(`KODEX200 ${NO_VOLUME_TEXT}`);
  } else {
    for (const c of volumeCells(vol)) {
      // 평균 대비는 앞 칸(거래량 · 평균)의 사유에서 나온 값이라 '계산 불가'(평균 0)일 때만 따로 센다.
      if (c.label === "평균 대비" && vol.ratio_status !== "avg_zero") continue;
      if (/자료 없음|자료 부족|계산 불가/.test(c.value)) {
        // '거래량' 칸은 이름이 겹치므로 'KODEX200 거래량 자료 없음'.
        notes.push(c.label === "거래량" ? `KODEX200 거래량 ${c.value}` : `KODEX200 거래량 ${c.label} ${c.value}`);
      }
    }
  }
  return notes;
}

// 미제공 지표 1건 — 이름 + 상태 + 사유(hover 툴팁). 임시 숫자 없이 정직 표시.
