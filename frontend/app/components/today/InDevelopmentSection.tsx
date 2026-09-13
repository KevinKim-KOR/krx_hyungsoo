"use client";

// POC3-OPS-02B-2-KS10-TRIGGER-FILE-SPLIT (2026-09-13)
// `TodayInvestmentCheckView.tsx` 가 907줄로 KS-10 프론트 임계(>900)를 넘어
// 책임별로 분리했다. **JSX·문구·className·핸들러·호출 조건을 고치지 않았다** —
// 바뀐 것은 파일 배치와 import/export 줄뿐이다.

// ── §4.4 개발 중인 판단 기능 — 빠진 기능 전체 board (사용자 지시 2026-07-29) ───
// 이번 화면에 넣기로 했으나 아직 없는 기능 + 이번 단계에 안 넣기로 한 기능을 모두
// 한곳에 기록해, 앞으로 무엇을 설계·개발해야 하는지 화면에서 직접 보이게 한다.
type DevItem = { name: string; badge: string; desc: string };

const DEV_IN_PROGRESS: DevItem[] = [
  {
    name: "내가 가진 ETF의 위험 신호",
    badge: "개발 중",
    desc: "보유 ETF 중 먼저 점검할 종목과 그 이유를 찾는 기능.",
  },
  {
    name: "시장 흐름 전환까지의 거리",
    badge: "개발 중",
    desc: "현재는 KODEX200 기준선 대비 위치만 참고로 제공합니다.",
  },
  // 2026-08-03 POC3-06: 흐름 지속 거래일 수·최근 고점 대비 위치·일간 등락률·
  // 1년 수익률은 실제값 제공 완료 → 개발 중 목록에서 제거.
];

const DEV_NOT_IN_STEP: DevItem[] = [
  {
    name: "거래량 흐름",
    badge: "이번 단계 미도입",
    desc: "거래량 자료 미저장 — 신규 수집 필요.",
  },
  {
    name: "공격·방어 비중",
    badge: "이번 단계 미도입",
    desc: "매매 비중 판단 표시는 이번 단계 범위 밖.",
  },
  {
    name: "추세 전환선 (SuperTrend)",
    badge: "이번 단계 미도입",
    desc: "신규 추세 전환 지표 — 후속 위험 신호 단계에서 검토.",
  },
];

function DevList({ items }: { items: DevItem[] }) {
  return (
    <ul className="tc-dev-list">
      {items.map((d) => (
        <li key={d.name}>
          {d.name}{" "}
          <span
            className={
              d.badge === "개발 중"
                ? "tc-badge tc-badge-dev"
                : "tc-badge tc-badge-off"
            }
          >
            {d.badge}
          </span>
          <p className="tc-muted tc-small">{d.desc}</p>
        </li>
      ))}
    </ul>
  );
}

export default function InDevelopmentSection() {
  return (
    <section className="tc-card" aria-label="개발 중인 판단 기능">
      <h2 className="tc-h2">개발 중인 판단 기능</h2>
      <p className="tc-muted tc-small" style={{ marginBottom: 12 }}>
        이번 화면에 넣기로 했으나 아직 없는 기능과, 이번 단계에서는 넣지 않기로 한
        기능을 모두 기록합니다. 값이 없어 숨긴 것이 아니라 앞으로 만들 목록입니다.
      </p>
      <div className="tc-label">준비 중 (앞으로 이 화면에 추가)</div>
      <DevList items={DEV_IN_PROGRESS} />
      <div className="tc-label tc-divider" style={{ paddingTop: 12 }}>
        이번 단계 미도입 (후속 단계·별도 설계)
      </div>
      <DevList items={DEV_NOT_IN_STEP} />
    </section>
  );
}
