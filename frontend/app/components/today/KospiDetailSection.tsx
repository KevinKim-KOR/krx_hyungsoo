"use client";

// POC3-OPS-02B-2-KS10-TRIGGER-FILE-SPLIT (2026-09-13)
// `TodayInvestmentCheckView.tsx` 가 907줄로 KS-10 프론트 임계(>900)를 넘어
// 책임별로 분리했다. **JSX·문구·className·핸들러·호출 조건을 고치지 않았다** —
// 바뀐 것은 파일 배치와 import/export 줄뿐이다.

import type { QueryState } from "@/lib/api/queryCache";
import type { MarketTopNResponse } from "@/lib/api";

type BlockedMetric = { name: string; badge: string; reason: string };

// 이번 Step 에서 코스피 영역에 "안 되는 것" 을 모두 기록 (사용자 지시 2026-07-29).
// 두 부류로 구분: (A) 기능 개발 중 (향후 저장값 파생) (B) 이번 단계 미도입
// (설계서 §11 금지 · 신규 산식/수집 필요 → 후속 Step). 숨기지 않고 board 로 노출.
// 2026-08-03 POC3-06 §3.2 — 흐름 지속 거래일 수·최근 고점 대비 위치·일간 등락률·
// 1년 수익률은 실제값으로 교체 완료(위 KospiHeadline). 개발 중 board 에서 제거.
const KOSPI_IN_DEV: BlockedMetric[] = [];

const KOSPI_NOT_IN_STEP: BlockedMetric[] = [
  {
    name: "거래량 흐름",
    badge: "이번 단계 미도입",
    reason: "현재 거래량 자료를 저장하지 않아 표시할 수 없습니다. 신규 수집이 필요해 이번 단계에서는 넣지 않습니다.",
  },
  {
    name: "공격·방어 비중",
    badge: "이번 단계 미도입",
    reason: "공격·방어 비중은 이번 화면 개편 단계의 범위가 아닙니다 (매매 비중 판단 표시 안 함).",
  },
  {
    name: "추세 전환선 (SuperTrend)",
    badge: "이번 단계 미도입",
    reason: "SuperTrend 등 신규 추세 전환 지표는 이번 단계에 도입하지 않습니다. 후속 위험 신호 단계에서 검토합니다.",
  },
];

function BlockedRow({ m }: { m: BlockedMetric }) {
  const dev = m.badge === "개발 중";
  return (
    <span>
      {m.name}{" "}
      <span className={dev ? "tc-badge tc-badge-dev" : "tc-badge tc-badge-off"}>
        {m.badge}
      </span>
      <span
        className="tc-info"
        tabIndex={0}
        role="note"
        aria-label={m.reason}
        title={m.reason}
      >
        {" "}
        ⓘ
      </span>
    </span>
  );
}

// ── §4.1 코스피 상세 — 이번 Step 에 아직/안 넣는 항목 board (정직 노출). ───────
export default function KospiDetailSection({
  market,
}: {
  market: QueryState<MarketTopNResponse>;
}) {
  void market; // 현재는 모두 미제공 — 향후 시계열 파생 시 market 사용.
  return (
    <section className="tc-card" aria-label="코스피 상세 (개발 중)">
      <h2 className="tc-h2">코스피 상세 지표</h2>
      <p className="tc-muted tc-small" style={{ marginBottom: 10 }}>
        아래 항목은 값이 없어 숨긴 것이 아니라, 아직 제공하지 않는 상태를 그대로
        표시한 것입니다.
      </p>
      <div className="tc-dev-row">
        {KOSPI_IN_DEV.map((m) => (
          <BlockedRow key={m.name} m={m} />
        ))}
        {KOSPI_NOT_IN_STEP.map((m) => (
          <BlockedRow key={m.name} m={m} />
        ))}
      </div>
    </section>
  );
}
