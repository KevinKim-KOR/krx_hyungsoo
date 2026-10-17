"use client";
// POC5-21 — 후보 목록 위 '수익률 계산 기간' 한 줄(선택 기간). 날짜는 표시 후보의 응답 값에서만 만든다.
// POC5-22 — 둘째 줄 = '동일 기간 KODEX200 대비 1M · 3M'(후보와 같은 시작 · 끝 날짜의 KODEX200 종가로 뺀 차이).
// 기간별 KODEX200 수익률 · 뺄셈 뜻 · 한계(가격 조정 기준 연속성 미검사)는 기존 클릭형 ? 안에.
import type { MarketCandidate } from "@/lib/api";
import {
  PERIOD_KEYS,
  PERIOD_LABEL,
  groupLine,
  groupSummary,
  periodGroup,
  type PeriodKey,
} from "@/lib/returnPeriod";
import { SAME_PERIOD_LIMIT, sameGroups, sameSummary } from "@/lib/samePeriodKodex";
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
}: {
  candidates: MarketCandidate[];
  selected: PeriodKey;
  marketAsof: string | null | undefined;
}) {
  if (candidates.length === 0) return null;
  const g = periodGroup(candidates, selected);
  const byPeriod = PERIOD_KEYS.map(
    (k) => `· ${PERIOD_LABEL[k]} ${groupSummary(periodGroup(candidates, k))}`,
  );
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
        <span className="rp-k">동일 기간 KODEX200 대비 1M · 3M</span>
        <span className="rp-v">{sameSummary(candidates)}</span>
        <HelpPopover
          label="동일 기간 KODEX200 대비"
          paragraphs={[
            "차이(%p) = 후보 수익률 − KODEX200 수익률. 두 수익률 모두 후보가 실제로 쓴 시작 · 끝 날짜의 저장 종가로 계산합니다(KODEX200 도 같은 날짜 · 전후 날짜나 보간 없음).",
            "예: 같은 기간 후보 +10% · KODEX200 +5% → +5%p.",
            ...sameGroups(candidates, "1m"),
            ...sameGroups(candidates, "3m"),
            `뜻: 그 저장 가격 기간에 KODEX200 보다 몇 %p 높거나 낮았는가. 배당 포함 총수익 · 개인 손익 · 앞으로의 우위가 아닙니다. ${SAME_PERIOD_LIMIT}`,
          ]}
        />
      </div>
    </div>
  );
}
