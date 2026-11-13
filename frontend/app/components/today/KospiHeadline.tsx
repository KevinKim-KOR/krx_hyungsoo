"use client";

// POC3-OPS-02B-2-KS10-TRIGGER-FILE-SPLIT (2026-09-13)
// `TodayInvestmentCheckView.tsx` 가 907줄로 KS-10 프론트 임계(>900)를 넘어
// 책임별로 분리했다. 분리 때는 JSX·문구·className·핸들러·호출 조건을 고치지 않았다
// (파일 배치와 import/export 줄만). 그 뒤 화면은 POC5-09 · POC5-UI-03 에서 바뀌었다.

import { useState } from "react";
import type { QueryState } from "@/lib/api/queryCache";
import type { MarketTopNResponse, StoredVolumeEvidence } from "@/lib/api";
import type { KospiDetail, KospiWindow, MorningBasisResponse } from "@/lib/api/morningBasis";
import { KOSPI_SOURCE_LINE } from "@/lib/kospiStatus";
import { md } from "@/lib/todayMarketLines";
import StoredVolumeBlock from "../StoredVolumeBlock";
import { KODEX200_VOLUME_HELP, NO_VOLUME_TEXT, volumeCells } from "@/lib/storedVolume";
import { fmtPct } from "./todayHelpers";

// ── §4.1 코스피 대표 (헤드라인) — 첫 화면 필수 요소만 compact ────────────────
// 코스피 차트 + [별도] KODEX200 기준선 대비 위치. 코스피와 KODEX200 을 하나로 묶지 않는다
// (§3.1 강제 분리 · FAIL 조건).
// POC5-UI-03 — 오른쪽 열은 코스피 일간 변화 · KODEX200 기준선(MA20 · MA60 · 기준일)만 둔다(일간 변화 칸은 2026-11-14 뺌 · 아래).
// 코스피 20 · 60거래일(2026-11-14 전 이름 '1개월 · 3개월') · 1년 · 고점 대비 · 기존 시장 판정 · KODEX200 거래량은 카드 아래
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
  morning,
  startOpen = false,
}: {
  market: QueryState<MarketTopNResponse>;
  // 설계자 지시 · 형수님 결정(2026-11-14 · POC6-29-1 결과서 §5) — 코스피 수익률 · 위치는 아침 기준 응답의 kospi_detail
  // (저장 종가 끝 행 기준 · 20 · 60거래일 실제 시작일 · 주말 · 장 시작 전에도 저장값이 있으면 보임).
  morning: QueryState<MorningBasisResponse>;
  embedded?: boolean;
  // POC6-29 보완 2차 — 오늘 점검에서는 처음부터 펼친다(두 번째 접기 정리 · 판정서 V2 §2 · 지금 자리는 KospiCloseBlock).
  startOpen?: boolean;
}) {
  const [open, setOpen] = useState(startOpen);
  const vol = market.phase === "success" ? market.data.kodex200_stored_volume ?? null : null;
  const kd = morning.phase === "success" ? (morning.data.kospi_detail ?? null) : null;
  const foldNotes = foldedMarketNotes(market, morning, kd, vol);

  return (
    <section className="tc-headline tc-headline-embedded" aria-label="KOSPI 현재 위치">
      <div className="tc-headline-grid tc-headline-grid-embedded">
        <div className="tc-headline-stats">
          {/* 형수님 결정(2026-11-14 · POC6-29-1 결과서 §4-2): '코스피 일간 변화' 칸은 뺐다 — 바로 위 코스피 공식 종가 머리 줄
              ('−32.63pt (−0.61%) 11/11 대비' · 시장 흐름 응답 obs.d1)이 같은 일간 변화를 비교 날짜와 함께 보이는데, 이 칸은
              KOSPI 기준일이 기대 직전 거래일이 아니면(주말 · KRX 공개 전) 같은 값을 사유 문장으로 막아 앞뒤가 달랐다. */}
          {/* 설계자 RESULT STEP 4-2 — 공식 자료원 표시(KRX 약관 제10조③). 기준일은 머리 줄 한 곳(2026-11-14 · 반복 정리). */}
          <div className="tc-muted tc-small tc-divider" style={{ paddingTop: 12 }} data-testid="tc-kospi-source">
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
          {/* 코스피 수익률·위치 — 저장 KOSPI 공식 종가 끝 행 기준(kospi_detail). 최신성 배지 · 기준일 · 지연은 머리 줄 한 곳,
              수집 · 지연 사유는 아침 요약 [자료 상태 보기] · 자료 최신화에서(설계자 지시 2026-11-14 · 반복 정리). */}
          <div className="tc-stat-block" data-testid="tc-kospi-detail">
            <div className="tc-label">
              코스피 수익률·위치
              {kd?.status === "ok" && kd.as_of_date ? (
                <span className="tc-muted tc-small"> · {md(kd.as_of_date)} 종가 기준</span>
              ) : null}
            </div>
            <KospiDetailBody morning={morning} kd={kd} />
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

// 20 · 60거래일 = 실제 계산 시작일(끝 = 제목의 종가 기준일) · 1년 · 최근 1년 고점 대비 = 같은 끝 행. 값이 없으면 그 칸만
// '자료 부족 · 자료 없음'(더 오래된 값 · 0 으로 대신하지 않음).
function KospiDetailBody({
  morning,
  kd,
}: {
  morning: QueryState<MorningBasisResponse>;
  kd: KospiDetail | null;
}) {
  if (morning.phase === "loading" || morning.phase === "idle") {
    return <div className="kospi-status-loading">확인 중</div>;
  }
  if (morning.phase === "error") {
    return <div className="tc-muted tc-small">코스피 수익률을 불러오지 못했습니다</div>;
  }
  if (!kd) return <div className="tc-muted tc-small">코스피 수익률 확인 불가</div>;
  if (kd.status !== "ok") {
    return <div className="tc-muted tc-small">코스피 수익률 확인 불가 — {kd.reason ?? "저장 종가 확인 불가"}</div>;
  }
  // 서버 사유(그날 KODEX 200 저장 가격이 없어 20 · 60거래일을 계산하지 못함)가 있으면 빈 칸은 '계산 불가' + 그 사유 한 줄 ·
  // 사유 없이 빈 칸이면 이력 부족(독립 검토 2026-11-14).
  const win = (label: string, w: KospiWindow | null) =>
    w ? `${label} ${fmtPct(w.pct)} (${md(w.start_date)}부터)` : `${label} ${kd.reason ? "계산 불가" : "자료 부족"}`;
  return (
    <ul className="tc-list-plain">
      <li>{win("20거래일", kd.r20)}</li>
      <li>{win("60거래일", kd.r60)}</li>
      <li>1년 {kd.return_1y_pct != null ? fmtPct(kd.return_1y_pct) : "자료 없음"}</li>
      <li>최근 1년 고점 대비 {kd.high_52w_gap_pct != null ? fmtPct(kd.high_52w_gap_pct) : "자료 없음"}</li>
      {kd.reason ? (
        <li className="tc-muted tc-small" data-testid="tc-kospi-detail-reason">
          {kd.reason}
        </li>
      ) : null}
    </ul>
  );
}

// UI-03 설계 §3 · 판정 Q3 — 접힌 칸 안의 자료 없음 · 부족 · 계산 불가 · 확인 불가를 기존 문구로 모은다.
// 서로 다른 사유는 따로 둔다. 값이 비어 있다는 것만으로 위험 · 하락 신호를 만들지 않는다.
function foldedMarketNotes(
  market: QueryState<MarketTopNResponse>,
  morning: QueryState<MorningBasisResponse>,
  kd: KospiDetail | null,
  vol: StoredVolumeEvidence | null,
): string[] {
  const notes: string[] = [];
  // 코스피 수익률 칸은 상세가 계산됐을 때(ok)만 빈 칸을 센다 — 아니면 칸 자리에 사유가 이미 보인다.
  if (morning.phase === "success" && kd?.status === "ok") {
    const miss = kd.reason ? "계산 불가" : "자료 부족";
    if (!kd.r20) notes.push(`코스피 20거래일 ${miss}`);
    if (!kd.r60) notes.push(`코스피 60거래일 ${miss}`);
    if (kd.return_1y_pct == null) notes.push("코스피 1년 자료 없음");
    if (kd.high_52w_gap_pct == null) notes.push("코스피 최근 1년 고점 대비 자료 없음");
  }
  if (market.phase !== "success") return notes;
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
