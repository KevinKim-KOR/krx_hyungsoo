"use client";

// OCI 적용·알림 — 정보 PUSH 운영 방식 안내 카드 (A구간).
//
// 설계 정정(Q1-c·Q3-a·Q4): push_kind 3종(Market/Holdings/Spike)은 모두 정보 PUSH 이며
// OCI 가 자동 발송한다. 본 카드는 "운영 방식 안내" 만 한다:
// - 승인 run 을 담지 않는다. 메시지별 승인이 필요한 것처럼 보이는 문구를 쓰지 않는다.
// - 실행 이력 조회 API 가 없으므로(§1.5) 실제 실행 시각·성공 여부를 표시하지 않는다.
//   `정상`·`운영 중`·`최근 성공` 같은 실측 상태 위장 금지(Q4). "운영 기준(정책 안내)" 만.

interface InfoPushItem {
  key: "market" | "holdings" | "spike";
  title: string;
  operating: string; // 운영 기준(정책) — 실측 상태 아님
}

const INFO_PUSH_ITEMS: InfoPushItem[] = [
  {
    key: "market",
    title: "시장 흐름",
    operating: "정해진 시각에 시장 흐름 정보를 자동 발송합니다.",
  },
  {
    key: "holdings",
    title: "보유 종목",
    operating:
      "하루 중 정해진 슬롯마다 현재 보유 ETF 평가 정보를 자동 발송합니다.",
  },
  {
    key: "spike",
    title: "급등락",
    operating:
      "조건을 평가하고 새 신호가 있을 때만 자동 발송합니다.",
  },
];

export default function InfoPushGuideCards() {
  return (
    <section aria-labelledby="info-push-h" className="card">
      <h2 id="info-push-h">정보 PUSH 운영 기준</h2>
      <p className="helper" style={{ marginBottom: 12 }}>
        아래 세 알림은 OCI 가 <strong>자동으로 발송</strong>합니다. 메시지마다
        사용자가 승인하지 않습니다. 아래는 실시간 실행 상태가 아니라 운영
        기준(정책) 안내입니다.
      </p>
      <div className="info-push-grid">
        {INFO_PUSH_ITEMS.map((it) => (
          <div key={it.key} className="info-push-card">
            <div className="info-push-title">{it.title}</div>
            <div className="info-push-badge">자동 발송 · 메시지별 승인 없음</div>
            <div className="info-push-operating">{it.operating}</div>
          </div>
        ))}
      </div>
    </section>
  );
}
