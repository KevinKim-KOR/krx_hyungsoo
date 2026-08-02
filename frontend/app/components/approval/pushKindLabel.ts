// 정보 PUSH 종류(push_kind) → 사람이 읽는 라벨.
//
// 설계 정정(Q1-c·Q2-b): 3종 push_kind 는 모두 정보 PUSH 다. push_kind 가 null/undefined 인
// 과거 run 은 "종류 확인 불가 — 기존 기록" 으로 개발·호환 점검에서만 다룬다(임의 분류 금지).

import type { PushKind } from "@/lib/api";

export function pushKindLabel(kind: PushKind | null | undefined): string {
  switch (kind) {
    case "market_briefing":
      return "시장 흐름";
    case "holdings_briefing":
      return "보유 종목";
    case "spike_or_falling_alert":
      return "급등락";
    default:
      // null/undefined — 종류를 신뢰할 수 없음. 추측 분류하지 않는다.
      return "종류 확인 불가 — 기존 기록";
  }
}

// push_kind 가 신뢰 가능한 정보 PUSH 종류인지(= 미리보기·수동 처리 영역에서 다룰 수 있는지).
// null/undefined 는 개발·호환 점검으로 보낸다.
export function isKnownPushKind(kind: PushKind | null | undefined): boolean {
  return (
    kind === "market_briefing" ||
    kind === "holdings_briefing" ||
    kind === "spike_or_falling_alert"
  );
}
