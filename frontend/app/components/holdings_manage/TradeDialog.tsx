"use client";

// POC5-05 개정 2 — 보유 줄의 매매 입력 창(추가매수 · 분할매도 · 전량매도) · 거래 오기 정정.
// 설계 §2 · §3 · §6 · PLAN §2-8 · 사용자 확인 목업:
//   폼 = 같은 폭 3열 두 줄(거래일 · 거래 시각 · 종류 / 체결단가 · 수량 · 계산 금액) + 전체 폭 메모.
//   미리보기는 화면 안내용 근사값이다 — 저장 결과는 늘 서버 계산(Decimal)을 따른다.
//   record_id = 저장 동작마다 새 UUID · 직전 저장이 실패했고 보낼 내용이 같으면 같은 ID
//   (응답 유실 재시도). 내용 비교 범위는 서버의 재시도 비교와 같다(record_id · base_revision 제외).

import { useCallback, useId, useRef, useState } from "react";
import {
  ApiRequestError,
  putTradeCommand,
  type HoldingItem,
  type TradeCommand,
  type TradeCommandResult,
} from "@/lib/api";
import { DEFAULT_GROUP } from "@/lib/holdings_view";
import Dialog from "./Dialog";
import {
  KIND_LABEL,
  apiErrorText,
  fmtNum,
  fmtSignedMoney,
  fmtSignedPct,
  fmtWon,
  newSaveId,
  parseInput,
  pnlClass,
  previewTrade,
  toDecimalText,
  todayKst,
  type TradeKind,
  type TradePreview,
} from "./format";

// ─── 저장 공용(매매 입력 창 · 새 보유 창) ──────────────────────────────

export type SaveCommand = Omit<TradeCommand, "record_id">;

// 409 = 오래된 화면 · 충돌 — 창을 닫으면 부모가 최신 보유로 다시 읽는다.
export function saveErrorText(e: unknown): string {
  const text = apiErrorText(e);
  if (e instanceof ApiRequestError && e.httpStatus === 409) {
    return `${text} 창을 닫으면 최신 보유로 새로고침됩니다.`;
  }
  return text;
}

export function useTradeSave(onSaved: (result: TradeCommandResult) => void) {
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const failed = useRef<{ key: string; id: string } | null>(null);
  const busy = useRef(false);
  const save = useCallback(
    async (cmd: SaveCommand) => {
      if (busy.current) return;
      busy.current = true;
      // 서버는 같은 record_id 의 재시도를 revision 확인보다 먼저, 명령 내용만으로 비교한다.
      const key = JSON.stringify({ ...cmd, base_revision: null });
      const id = failed.current && failed.current.key === key ? failed.current.id : newSaveId();
      setSaving(true);
      setError(null);
      try {
        const result = await putTradeCommand({ record_id: id, ...cmd });
        failed.current = null;
        busy.current = false;
        setSaving(false);
        onSaved(result);
      } catch (e) {
        failed.current = { key, id };
        busy.current = false;
        setSaving(false);
        setError(saveErrorText(e));
      }
    },
    [onSaved],
  );
  return { saving, error, save };
}

// ─── 매매 입력 창 ───────────────────────────────────────────────────

export interface TradeCorrection {
  recordId: string;
  kind: "BUY" | "SELL";
  tradeDate: string;
  tradeTime: string | null;
  price: string;
  quantity: string;
  memo: string | null;
}

interface Props {
  holding: HoldingItem;
  revision: number;
  initialKind?: TradeKind;
  eventDates?: string[];
  // 서버가 계산한 정확한 잔량(십진 문자열 · History 의 현재 기간 수량). 전량매도는 이 값을
  // 보낸다 — 화면의 float 수량은 기존 기준잔고 정밀도를 잃을 수 있다(서버는 정확히 비교).
  exactQuantity?: string | null;
  correct?: TradeCorrection | null;
  onClose: () => void;
  onSaved: (result: TradeCommandResult) => void;
}

const KIND_OPTIONS: { kind: TradeKind; label: string }[] = [
  { kind: "buy", label: "추가매수" },
  { kind: "sell", label: "분할매도" },
  { kind: "sell_all", label: "전량매도" },
];

export default function TradeDialog({
  holding,
  revision,
  initialKind = "buy",
  eventDates,
  exactQuantity = null,
  correct = null,
  onClose,
  onSaved,
}: Props) {
  const uid = useId();
  const [today] = useState(todayKst);
  const [kind, setKind] = useState<TradeKind>(
    correct ? (correct.kind === "BUY" ? "buy" : "sell") : initialKind,
  );
  const [date, setDate] = useState(correct?.tradeDate ?? today);
  const [time, setTime] = useState(correct?.tradeTime ?? "");
  const [price, setPrice] = useState(correct?.price ?? "");
  const [qty, setQty] = useState(correct?.quantity ?? "");
  const [memo, setMemo] = useState(correct?.memo ?? "");
  const [sameDay, setSameDay] = useState<"after" | "before">("after");
  const { saving, error, save } = useTradeSave(onSaved);

  const name = holding.name?.trim() || holding.ticker;
  const account = holding.account_group?.trim() || DEFAULT_GROUP;
  const q = holding.quantity;
  const cost = q * holding.avg_buy_price;
  const sellAll = !correct && kind === "sell_all";
  const qtyText = sellAll ? (exactQuantity ?? String(q)) : qty;
  const priceNum = parseInput(price);
  const qtyNum = parseInput(qtyText);
  const amount =
    priceNum !== null && qtyNum !== null && priceNum > 0 && qtyNum > 0 ? priceNum * qtyNum : null;
  const pv = correct ? null : previewTrade(q, cost, kind, priceNum, qtyNum);
  // 정정에서 날짜를 그대로 두면 서버가 원래 순서를 유지한다 — 앞/뒤 선택이 필요 없다.
  const showSameDay =
    (eventDates ?? []).includes(date) && !(correct && date === correct.tradeDate);
  const canSave = !saving && date !== "" && amount !== null && !pv?.oversell;

  const submit = () => {
    if (!canSave) return;
    const trade = {
      trade_date: date,
      trade_time: time || null,
      price: toDecimalText(price),
      quantity: toDecimalText(qtyText),
      memo: memo.trim() || null,
    };
    const cmd: SaveCommand = correct
      ? {
          base_revision: revision,
          action: "correct",
          position_id: holding.position_id ?? null,
          supersedes_id: correct.recordId,
          trade,
        }
      : { base_revision: revision, action: kind, position_id: holding.position_id ?? null, trade };
    if (showSameDay) cmd.same_day = sameDay;
    void save(cmd);
  };

  const title = correct ? "매매 기록 정정" : `${name} · ${account} 매매 입력`;
  const subtitle = correct
    ? `${name} · ${account} — ${correct.tradeDate} ${KIND_LABEL[correct.kind]} 기록을 고칩니다`
    : `지금 ${fmtNum(q, 6)}주 · 평단 ${fmtWon(holding.avg_buy_price)} · 원가 ${fmtWon(cost)}`;

  return (
    <Dialog
      title={title}
      subtitle={subtitle}
      onClose={onClose}
      footer={
        <>
          <button type="button" className="hmx-ghost" onClick={onClose} disabled={saving}>
            취소
          </button>
          <button type="button" onClick={submit} disabled={!canSave}>
            {saving ? "저장 중…" : correct ? "정정 저장" : "매매 저장"}
          </button>
        </>
      }
    >
      <form className="hmx-form" onSubmit={(e) => e.preventDefault()}>
        <div className="hmx-field">
          <label htmlFor={`${uid}-date`}>거래일</label>
          <input
            id={`${uid}-date`}
            type="date"
            value={date}
            max={today}
            onChange={(e) => setDate(e.target.value)}
          />
        </div>
        <div className="hmx-field">
          <label htmlFor={`${uid}-time`}>거래 시각 (선택)</label>
          <input
            id={`${uid}-time`}
            type="time"
            value={time}
            onChange={(e) => setTime(e.target.value)}
          />
        </div>
        <div className="hmx-field">
          <span className="hmx-lbl" id={`${uid}-kind`}>
            종류
          </span>
          {correct ? (
            <output className="hmx-out" aria-labelledby={`${uid}-kind`}>
              {KIND_LABEL[correct.kind]}
            </output>
          ) : (
            <div className="hmx-seg" role="group" aria-labelledby={`${uid}-kind`}>
              {KIND_OPTIONS.map((o) => (
                <button
                  key={o.kind}
                  type="button"
                  aria-pressed={kind === o.kind}
                  onClick={() => setKind(o.kind)}
                >
                  {o.label}
                </button>
              ))}
            </div>
          )}
        </div>
        <div className="hmx-field">
          <label htmlFor={`${uid}-price`}>체결단가 (원)</label>
          <input
            id={`${uid}-price`}
            className="hmx-num"
            inputMode="decimal"
            autoComplete="off"
            value={price}
            onChange={(e) => setPrice(e.target.value)}
          />
        </div>
        <div className="hmx-field">
          <label htmlFor={`${uid}-qty`}>수량</label>
          <input
            id={`${uid}-qty`}
            className="hmx-num"
            inputMode="decimal"
            autoComplete="off"
            value={qtyText}
            readOnly={sellAll}
            onChange={(e) => setQty(e.target.value)}
          />
        </div>
        <div className="hmx-field">
          <span className="hmx-lbl" id={`${uid}-amt`}>
            계산 금액 (원)
          </span>
          <output className="hmx-out hmx-right" aria-labelledby={`${uid}-amt`}>
            {amount === null ? "—" : fmtNum(amount)}
          </output>
        </div>
        {showSameDay ? (
          <div className="hmx-field">
            <span className="hmx-lbl" id={`${uid}-same`}>
              같은 날 기존 기록의 뒤 / 앞
            </span>
            <div className="hmx-seg" role="group" aria-labelledby={`${uid}-same`}>
              <button
                type="button"
                aria-pressed={sameDay === "after"}
                onClick={() => setSameDay("after")}
              >
                뒤 (기본)
              </button>
              <button
                type="button"
                aria-pressed={sameDay === "before"}
                onClick={() => setSameDay("before")}
              >
                앞
              </button>
            </div>
          </div>
        ) : null}
        <div className="hmx-field hmx-field-wide">
          <label htmlFor={`${uid}-memo`}>메모 (선택)</label>
          <input
            id={`${uid}-memo`}
            maxLength={200}
            placeholder="예: 실적 발표 뒤 분할매수"
            value={memo}
            onChange={(e) => setMemo(e.target.value)}
          />
        </div>
      </form>
      <p className="hmx-note">
        시각을 모르면 비워 두세요(날짜 단위로 기록). 휴장일 날짜도 기록할 수 있습니다.
        {eventDates && eventDates.length > 0
          ? " 같은 날 기록이 이미 있으면 '앞 / 뒤'를 고르는 칸이 나타납니다."
          : ""}
      </p>
      {correct ? (
        <div className="hmx-info">저장하면 이 기간을 다시 계산합니다.</div>
      ) : (
        <PreviewBox kind={kind} pv={pv} />
      )}
      {error ? (
        <div className="hmx-error" role="alert">
          {error}
        </div>
      ) : null}
    </Dialog>
  );
}

function PreviewBox({ kind, pv }: { kind: TradeKind; pv: TradePreview | null }) {
  let qtyV = "—";
  let avgV = "—";
  let pnlV = kind === "buy" ? "— (매수)" : "—";
  let qtyCls = "";
  let pnlCls = "";
  if (pv?.oversell) {
    qtyV = "잔량 초과 — 저장할 수 없음";
    qtyCls = "pnl-neg";
  } else if (pv) {
    const closed = pv.quantity === 0;
    qtyV = `${fmtNum(pv.quantity, 6)}주${closed ? " (보유 종료)" : ""}`;
    if (kind === "buy") {
      avgV = fmtWon(pv.avg);
    } else {
      avgV = closed ? "—" : `${fmtWon(pv.avg)} (유지)`;
      const money = fmtSignedMoney(pv.realized);
      const pct = fmtSignedPct(pv.rate);
      pnlV = [money, pct].filter(Boolean).join(" · ") || "—";
      pnlCls = pnlClass(pv.realized);
    }
  }
  return (
    <div className="hmx-preview" aria-live="polite">
      <div>
        <span className="hmx-k">저장 후 수량</span>
        <span className={`hmx-v ${qtyCls}`}>{qtyV}</span>
      </div>
      <div>
        <span className="hmx-k">저장 후 평단</span>
        <span className="hmx-v">{avgV}</span>
      </div>
      <div>
        <span className="hmx-k">이번 실현손익</span>
        <span className={`hmx-v ${pnlCls}`}>{pnlV}</span>
      </div>
    </div>
  );
}
