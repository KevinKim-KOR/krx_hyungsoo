"use client";
// POC6-01 — 「오늘의 투자 점검」 코스피 카드 안 짧은 두 줄(6개월 요약 · 해당하는 최근 큰 변화 · 목업 확인).
// 문장은 서버 응답 그대로(「요즘 잘 오르는 ETF」 시장 흐름 · 복사문과 같은 계산). 카드 밖 새 구역 없음.
// POC6-17 — 기간 비교가 수급 등에 막혔거나 수급 연결에 문제가 있을 때만 서버 설명 한 줄을 더한다.
import { flowBasisNote } from "@/lib/api/marketFlow";
import { useMarketFlowContext } from "./useMarketFlowContext";

export default function TodayFlowLines() {
  const q = useMarketFlowContext();
  if (q.phase === "error") {
    return (
      <div className="tc-muted tc-small tc-divider mf-today" data-testid="tc-market-flow-lines">
        시장 흐름(수급 · 환율 · 유가) 자료를 불러오지 못했습니다.
      </div>
    );
  }
  if (q.phase !== "success") return null;
  const note = flowBasisNote(q.data);
  return (
    <div className="tc-divider mf-today" data-testid="tc-market-flow-lines">
      {q.data.today_lines.map((l, i) => (
        <div key={l} className={i === 0 ? "mf-today-main" : "mf-today-sub"}>
          {l}
        </div>
      ))}
      {note ? (
        <div className="mf-today-sub tc-warn" data-testid="tc-market-flow-basis">
          {note}
        </div>
      ) : null}
      <div className="tc-muted tc-small">자세한 흐름 · 차트는 「요즘 잘 오르는 ETF」 시장 흐름에서 봅니다.</div>
    </div>
  );
}
