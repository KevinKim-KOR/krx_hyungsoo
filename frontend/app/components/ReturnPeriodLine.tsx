"use client";
// POC5-21 — 후보 목록 위 '수익률 계산 기간' 한 줄(선택 기간) + 'KODEX200 대비' 한 줄.
// 양쪽 실제 시작~끝과 계산 정의는 기존 클릭형 ? 안에. 날짜는 표시 후보의 응답 값에서만 만든다.
import type { MarketCandidate, MarketContextKodex200 } from "@/lib/api";
import {
  PERIOD_KEYS,
  PERIOD_LABEL,
  cmpGroup,
  cmpLabel,
  fmtRange,
  groupLine,
  groupSummary,
  kodexRange,
  periodGroup,
  type CmpKey,
  type PeriodKey,
} from "@/lib/returnPeriod";
import HelpPopover from "./holdings_risk_evidence/HelpPopover";

// 값 아래 · 이름 옆 짧은 표시. 날짜(YYYY-MM-DD)는 중간에서 줄을 바꾸지 않는다.
export function PeriodNote({ text }: { text: string | null }) {
  if (!text) return null;
  const parts = text.split(/(\d{4}-\d{2}-\d{2})/);
  return (
    <span className="rp-note">
      {parts.map((p, i) =>
        /^\d{4}-\d{2}-\d{2}$/.test(p) ? (
          <span key={i} className="rp-date">
            {p}
          </span>
        ) : (
          p
        ),
      )}
    </span>
  );
}

export default function ReturnPeriodLine({
  candidates,
  selected,
  marketAsof,
  kodex,
}: {
  candidates: MarketCandidate[];
  selected: PeriodKey;
  marketAsof: string | null | undefined;
  kodex: MarketContextKodex200 | null | undefined;
}) {
  if (candidates.length === 0) return null;
  const g = periodGroup(candidates, selected);
  const byPeriod = PERIOD_KEYS.map(
    (k) => `· ${PERIOD_LABEL[k]} ${groupSummary(periodGroup(candidates, k))}`,
  );
  const c1 = cmpGroup(candidates, "1m", kodex);
  const c3 = cmpGroup(candidates, "3m", kodex);
  const l1 = cmpLabel(c1);
  const l3 = cmpLabel(c3);
  const cmpText = l1 === l3 ? `${l1} (%p)` : `1M ${l1} · 3M ${l3} (%p)`;
  const kd = (key: CmpKey) => {
    const r = kodexRange(kodex, key);
    return r ? fmtRange(r.start, r.end) : "확인 불가";
  };
  return (
    <div className="rp-box" data-testid="return-period-line">
      <div className="rp-line">
        <span className="rp-k">{PERIOD_LABEL[selected]} 수익률 계산 기간</span>
        <span className="rp-v">{groupLine(g)}</span>
        <HelpPopover
          label="수익률 계산 기간"
          paragraphs={[
            "수익률 = 끝 종가 ÷ 시작 종가 − 1. 끝 종가는 그 종목의 마지막 저장 종가입니다.",
            "시작 종가 — 일간: 직전 저장일 종가. 1개월 · 3개월 · 6개월 · 12개월 · 3년: 시장 저장 최신일에서 30 · 90 · 180 · 365 · 1,095일 전 날짜 또는 그 뒤 첫 저장 종가.",
            "저장 자료가 그보다 짧은 종목은 첫 저장일 종가부터 계산합니다. 이때 값은 그 기간 전체의 수익률이 아닙니다. 실제 시작일은 아래 기간별 날짜에 있고, 종목마다 시작일이 다르면 값 아래에도 표시합니다.",
            `시장 저장 최신일 ${marketAsof ?? "-"} = 저장된 전체 종목 가격 중 가장 늦은 저장일. 끝일이 이와 다른 후보는 이름 옆에 '수익률 끝일'을 표시합니다.`,
            `표시 후보 ${candidates.length}개의 기간별 사용 종가 날짜`,
            ...byPeriod,
          ]}
        />
      </div>
      <div className="rp-line">
        <span className="rp-k">KODEX200 대비 1M · 3M</span>
        <span className="rp-v">{cmpText}</span>
        <HelpPopover
          label="KODEX200 대비 기간"
          paragraphs={[
            "KODEX200 대비 값 = 후보 수익률 − KODEX200 수익률(두 수익률의 차이 · 단위 %p).",
            "후보 1개월 · 3개월은 시장 저장 최신일에서 30 · 90일 전 날짜 또는 그 뒤 첫 저장 종가부터, KODEX200 1M · 3M 은 KODEX200 마지막 저장일에서 20 · 60 저장일 앞 종가부터 계산합니다.",
            "두 기간이 다르면 같은 기간의 초과수익이나 시장 대비 우위를 확인한 값이 아닙니다.",
            `· 1M — 후보 ${groupSummary(periodGroup(candidates, "one_month"))} · KODEX200 ${kd("1m")}`,
            `· 3M — 후보 ${groupSummary(periodGroup(candidates, "three_month"))} · KODEX200 ${kd("3m")}`,
          ]}
        />
      </div>
    </div>
  );
}
