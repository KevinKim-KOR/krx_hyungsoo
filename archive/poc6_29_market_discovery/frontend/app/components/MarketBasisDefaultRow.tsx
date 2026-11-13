"use client";
// POC5-26 — 「요즘 잘 오르는 ETF」 목록 카드 맨 위 '기본 조회 기준' 한 줄(카드 · 표 보기 공통 · 설계 §2 · §3 ·
// PLAN 판정 Q1 (a)). 기준을 바꾸는 곳은 지금처럼 표 보기 머리뿐이다(카드 보기에 선택 버튼을 두지 않음).
// - 저장 기본은 화면 상태 초기값에서 한 번 읽는다 → 첫 시장 조회부터 그 기준(1개월을 먼저 부르지 않음).
// - [이 기준을 기본으로] = 지금 보는 기준을 저장만 한다(시장 GET · 재계산 없음). 성공 뒤에만 기본 표시를 바꾼다.
// - 지금 보는 기준(조회 · 표시 · 「보유와 비교」 조건 · 복사 · 전달)은 화면 상태 · 응답 그대로다.
import { useCallback, useEffect, useState } from "react";
import type { MarketBasis } from "@/lib/api";
import { PERIOD_LABEL } from "@/lib/returnPeriod";
import {
  MARKET_BASIS_PREF_KEY,
  readMarketBasisPref,
  writeMarketBasisPref,
  type MarketBasisPref,
} from "@/lib/marketBasisPreference";

// 같은 자리의 짧은 안내(PLAN §2 · 판정 §2 · §3).
export const BASIS_READ_NOTICE: Partial<Record<MarketBasisPref["status"], string>> = {
  read_failed: "저장된 기본을 읽지 못해 1개월로 시작했습니다",
  invalid: "저장된 기본 값을 쓸 수 없어 1개월로 시작했습니다",
};
export const BASIS_SAVE_FAILED = "기본값 저장을 확인하지 못했습니다. 현재 조회는 유지됩니다.";

// 표시용 기본 상태. 저장값이 허용 밖(invalid)이면 1개월은 대신 쓴 값일 뿐 저장된 기본이 아니다
// (confirmed = false) → 1개월을 보고 있어도 명시 저장으로 바로잡을 수 있다.
function prefView(p: MarketBasisPref) {
  return {
    saved: p.basis,
    confirmed: p.status !== "invalid",
    notice: BASIS_READ_NOTICE[p.status] ?? null,
  };
}

export interface MarketBasisDefault {
  initial: MarketBasisPref;
  saved: MarketBasis;
  confirmed: boolean;
  notice: string | null;
  save: (basis: MarketBasis) => boolean;
}

export function useMarketBasisDefault(): MarketBasisDefault {
  const [initial] = useState<MarketBasisPref>(readMarketBasisPref);
  const [view, setView] = useState(() => prefView(initial));
  const save = useCallback((basis: MarketBasis) => {
    if (!writeMarketBasisPref(basis)) return false;
    setView({ saved: basis, confirmed: true, notice: null });
    return true;
  }, []);
  // 같은 브라우저의 다른 탭에서 기본을 바꾸면 '기본' 표시만 다시 읽는다(지금 조회 · 시장 GET · 저장값은 그대로).
  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      if (e.key !== null && e.key !== MARKET_BASIS_PREF_KEY) return;
      setView(prefView(readMarketBasisPref()));
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);
  return { initial, ...view, save };
}

// 저장 실패 안내는 이 줄에만 둔다. 기준을 바꾸거나 다시 읽으면 화면이 '불러오는 중'으로 바뀌며 함께 사라지고,
// 저장할 것이 없어지면(다른 탭 저장 등) 보이지 않는다.
export default function MarketBasisDefaultRow({
  current,
  pref,
}: {
  current: MarketBasis;
  pref: MarketBasisDefault;
}) {
  const [failed, setFailed] = useState(false);
  const differs = current !== pref.saved;
  const canSave = differs || !pref.confirmed;
  return (
    <div className="mbd-row" data-testid="market-basis-default">
      <span className="mbd-k">기본 조회 기준</span>
      <span className="mbd-v">{PERIOD_LABEL[pref.saved]}</span>
      {differs ? <span className="mbd-now">· 지금 보는 기준 {PERIOD_LABEL[current]}</span> : null}
      {pref.notice ? <span className="mbd-note">· {pref.notice}</span> : null}
      <button
        type="button"
        className="btn-md"
        disabled={!canSave}
        onClick={() => setFailed(!pref.save(current))}
      >
        {canSave ? "이 기준을 기본으로" : "이미 기본"}
      </button>
      {failed && canSave ? (
        <span className="mbd-err" role="alert">
          {BASIS_SAVE_FAILED}
        </span>
      ) : null}
    </div>
  );
}
