"use client";

// 「진단·상태 › 미사용 기능」 — 2026-11-12 POC6-29 보완(보완 PLAN 판정 Q-R5 · RESULT 판정 §4 · PLAN §9-4 · 목업 R4).
//
// 일상 메뉴에서 뺀 기능을 기능마다 하위 메뉴 하나(메뉴 key 하나)로 둔다. 페이지는 기능마다 같은 틀이다:
//   머리(이름 · 「미사용 기능」 배지) → 세 줄(어떤 기능이었는지 · 왜 빠졌는지 · 지금 어디서) → 실행 → 이동 → 「자세히」(접힘).
// 세 줄 · 실행 · 이동은 펼치지 않고 읽는다. 기능을 더 옮길 때는 FEATURES 에 한 항목 + 메뉴 key 하나를 더한다.
//
// 첫 기능 = 「신규 ETF 관찰 점검」(`unused_universe_watch`): 「요즘 잘 오르는 ETF」에 있던 [신규 ETF 관찰 후보 갱신].
//   실행 패널(UniverseRefreshPanel)은 그대로 쓴다 — 화면을 열 때 요청 0 · 버튼을 누를 때만 외부(pykrx) 조회 ·
//   PC 파일 덮어쓰기(기존 동작). 결과는 「개발·실험용」 › 미리보기 · 수동 전달 점검의 PUSH-2 보유 관찰 브리핑 초안
//   ([저장된 보유 종목으로 초안 만들기]) · PUSH-3 급등락 관찰 신호 초안이 읽는다.
//   「자세히」 = 없앤 「요즘 잘 오르는 ETF」의 기능별 옮긴 곳(보관 README 표 요약 · 파일 경로는 이 안에만).

import type { ComponentType } from "react";
import UniverseRefreshPanel from "./UniverseRefreshPanel";
import type { MenuKey } from "./LeftSidebar";

export type UnusedFeatureId = "universe_watch";

// 「자세히」의 한 줄 = 옛 기능 → 지금 있는 곳(+ 그 메뉴로 가는 버튼 · 메뉴가 하나로 정해지지 않으면 버튼 없음).
interface MoveRow {
  was: string;
  now: string;
  to?: { key: MenuKey; label: string };
}

interface UnusedFeature {
  title: string;
  was: string;
  why: string;
  where: string;
  Run: ComponentType;
  back: { key: MenuKey; label: string };
  details?: { summary: string; intro: string; rows: MoveRow[]; archive: string };
}

const TO_TODAY = { key: "today_check" as const, label: "「오늘의 투자 점검」으로" };
const TO_LIST = { key: "workbench" as const, label: "「후보리스트」로" };
const TO_COMPARE = { key: "holding_candidate_compare" as const, label: "「보유와 후보 비교」로" };

const FEATURES: Record<UnusedFeatureId, UnusedFeature> = {
  universe_watch: {
    title: "신규 ETF 관찰 점검",
    was: "기존 후보군에서 pykrx 1개월 수익률이 가장 높은 ETF 한 종목을 수동으로 찾습니다. 두 실험용 초안이 그 결과를 읽습니다.",
    why: "일상 ETF 탐색을 「후보리스트」로 통합했습니다. 이 기능은 실험용 수동 초안에서 쓰기 때문에 별도 메뉴로 옮겼습니다.",
    where:
      "이 페이지에서 실행합니다. 결과를 읽는 곳 = 「개발·실험용」 › 미리보기 · 수동 전달 점검의 'PUSH-2 보유 관찰 브리핑 초안' · 'PUSH-3 급등락 관찰 신호 초안'.",
    Run: UniverseRefreshPanel,
    back: { key: "diagnostics", label: "「개발·실험용」으로" },
    details: {
      summary: "자세히 · 없앤 「요즘 잘 오르는 ETF」의 기능별 옮긴 곳",
      intro: "「요즘 잘 오르는 ETF」 메뉴는 없앴고, 그 화면이 하던 일은 아래 화면으로 옮겼습니다.",
      rows: [
        { was: "후보 카드 · 표 · 순위 수치", now: "「후보리스트」 [목록 | 표] · 줄을 펼친 상세", to: TO_LIST },
        {
          was: "보유와 비교 · 판단 근거 미리보기 · [AI 세션에서 검토]",
          now: "「보유와 후보 비교」(「보유」 · 「후보리스트」 줄 상세에서도 봄)",
          to: TO_COMPARE,
        },
        {
          was: "시장 배경 · 시장 위험 참고 · 시장 흐름 상세 · [VIX 다시 받기]",
          now: "「오늘의 투자 점검」 시장 흐름 · [시장 근거와 다른 변화 보기]",
          to: TO_TODAY,
        },
        { was: "[최신 시장 데이터 갱신]", now: "「오늘의 투자 점검」 [최신 자료 갱신]", to: TO_TODAY },
        {
          was: "「오늘의 투자 점검」의 판단 대기 목록(이 화면으로 이어지던 목록)",
          now: "「오늘의 투자 점검」 「보유 점검」 · 「잘 오르는 ETF」 카드",
          to: TO_TODAY,
        },
        {
          was: "목록 넘기기(AI 투자 세션 · ETF 구성종목으로)",
          now: "「후보리스트」 「이 목록으로 할 일」",
          to: TO_LIST,
        },
        { was: "기본 조회 기간 저장", now: "화면마다 [이 기준을 기본으로](화면별로 따로 저장)" },
        { was: "[신규 ETF 관찰 후보 갱신]", now: "이 페이지" },
      ],
      archive:
        "옛 화면 파일의 원래 경로와 대신하는 곳: archive/poc6_29_market_discovery/README.md (저장소 맨 위 · 화면에서 쓰지 않는 보관 폴더)",
    },
  },
};

interface Props {
  feature: UnusedFeatureId;
  onNavigate: (key: MenuKey) => void;
}

export default function UnusedFeatureView({ feature, onNavigate }: Props) {
  const f = FEATURES[feature];
  const { Run } = f;
  return (
    <section aria-labelledby="unused-feature-h">
      <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 8 }}>
        <h1 id="unused-feature-h" style={{ margin: 0 }}>
          {f.title}
        </h1>
        <span className="tc-badge tc-badge-dev">미사용 기능</span>
      </div>

      <div className="card" style={{ marginTop: 12 }}>
        <dl className="ec-lines" data-testid="unused-lines">
          <dt>어떤 기능이었는지</dt>
          <dd>{f.was}</dd>
          <dt>왜 빠졌는지</dt>
          <dd>{f.why}</dd>
          <dt>지금 어디서</dt>
          <dd>{f.where}</dd>
        </dl>
      </div>

      <Run />

      <div className="btn-row" style={{ marginTop: 12 }}>
        <button type="button" className="wb-btn btn-md" onClick={() => onNavigate(f.back.key)}>
          {f.back.label}
        </button>
      </div>

      {f.details ? (
        <details className="card" style={{ marginTop: 16 }} data-testid="unused-details">
          <summary style={{ cursor: "pointer", fontWeight: 600 }}>{f.details.summary}</summary>
          <div style={{ marginTop: 12, display: "grid", gap: 10 }}>
            <p className="helper" style={{ margin: 0 }}>
              {f.details.intro}
            </p>
            <dl className="ec-lines">
              {f.details.rows.map((r) => (
                <MoveLine key={r.was} row={r} onNavigate={onNavigate} />
              ))}
            </dl>
            <p className="helper" style={{ margin: 0 }}>
              {f.details.archive}
            </p>
          </div>
        </details>
      ) : null}
    </section>
  );
}

function MoveLine({ row, onNavigate }: { row: MoveRow; onNavigate: (key: MenuKey) => void }) {
  const { to } = row;
  return (
    <>
      <dt>{row.was}</dt>
      <dd>
        {row.now}
        {to ? (
          <button type="button" className="wb-btn btn-md ec-inline" onClick={() => onNavigate(to.key)}>
            {to.label}
          </button>
        ) : null}
      </dd>
    </>
  );
}
