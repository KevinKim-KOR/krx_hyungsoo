"use client";

// POC3-05 DESIGN_V2 — "확인 근거" 화면 (§4.4).
//
// 오늘 먼저 볼 보유 ETF와 실제 수치 근거를 하나의 읽기 흐름으로 보여준다.
// 본체는 기존 HoldingsRiskEvidenceSection 재사용(읽기 전용 표 + 선택 상세). 기존 시장
// Evidence 카드(HoldingsMarketEvidenceCard)는 별도 대형 패널로 두지 않고(Q2·AC-8), 그
// 고유 정보(NAV·괴리율·구성종목·중복률)는 선택 상세로 통합한다(HoldingsRiskEvidenceSection
// 내부에서 처리). unavailable 사유 확인은 "데이터 상태"로 이동(§7).

import HoldingsRiskEvidenceSection from "./HoldingsRiskEvidenceSection";
import type { MenuKey } from "./LeftSidebar";

interface Props {
  onNavigate: (key: MenuKey) => void;
}

export default function HoldingsEvidenceView({ onNavigate }: Props) {
  return (
    <section aria-labelledby="holdings-evidence-h">
      <h1 id="holdings-evidence-h">확인 근거</h1>
      <p className="subtitle">
        오늘 먼저 확인할 보유 ETF와 그 수치 근거입니다. 값을 수정하거나 저장하지 않는
        읽기 전용 화면입니다.
      </p>

      <HoldingsRiskEvidenceSection onNavigate={onNavigate} />
    </section>
  );
}
