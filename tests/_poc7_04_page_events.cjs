// POC7-04 화면 스크립트 시험 대본(jsdom) — 실제 서버가 만든 화면 HTML 을 열고 브라우저 동작을 흉내 낸다.
// 사용: node _poc7_04_page_events.cjs <jsdom 폴더> <시나리오 JSON 파일>
// 시나리오: { pages: [{html, ticker}], seed?: {키: 값}(localStorage), session_seed?: {키: 값}(창 0 sessionStorage),
//            clipboard: "ok" | "fail", storage_fail?(localStorage 쓰기 실패),
//            session_fail?(창 0 sessionStorage 쓰기 실패), session_quota?(창 0 sessionStorage 에 이 길이보다 긴 값은 못 씀),
//            session_fail_keys?(창 0 sessionStorage 에서 이 키들만 못 씀),
//            steps: [...] }
//   창(tab)마다 sessionStorage 를 따로 두고(새로 고침에도 유지), localStorage 는 모든 창이 같이 쓴다.
//   open tab page from? session?  창 tab 에 화면 page 를 연다(from = 그 창에서 연 새 창 · 그 창 sessionStorage 를 복사 ·
//                        session = 그 창 sessionStorage 를 이 값으로 새로 채움)
//   local_set key value  localStorage 값을 바꿈(다른 창이 쓴 것처럼)
//                        처음 단계 전에 창 0 = 화면 0 을 연다
//   storage local? local_delete? session? session_delete? session_fail_keys? tab?  쓰기(지우기) 실패 켜기 · 끄기
//                        — session 은 창 tab 의 것
//   reload tab           같은 창에서 같은 화면을 새로 연다(앞 화면에 pagehide)
//   close tab            창을 닫는다(pagehide)
//   copy                 [AI 질문 복사] 누름(클립보드 결과는 clipboard 값)
//   manual_copy          선택된 글을 직접 복사(⌘C · copy 이벤트)
//   select_part          복사문 일부만 선택
//   copy_answer box?     답 칸 전체를 선택해 복사(copy 이벤트 대상 = 답 칸 · box = gpt(기본) · gemini · claude)
//   cut_answer box?      답 칸 전체를 잘라냄(cut 이벤트 → 값 비움 · deleteByCut)
//   check id             체크 칸을 누름(click · 비활성 칸은 바뀌지 않음)
//   dragstart id         그 요소에서 끌기 시작(dragstart · 이 페이지의 글을 끌어 옮김)
//   field id value how   칸 값 바꿈 — how = type(타자) · paste(끝에 붙여 넣기) · paste_all(전체를 바꿔 붙여 넣기)
//   undo value box?      되돌리기(값 = value · historyUndo)
//   drop value box?      답 칸에 끌어 놓기(drop 이벤트 · value 가 있으면 끝에 붙고 insertFromDrop · 없으면 아무것도 안 들어감)
//   wait ms              시간 흐름(Date.now 를 ms 만큼 옮김 · 음수 = 기기 시계를 뒤로)
//   save                 [저장] 누름(응답은 respond 때까지 대기)
//   respond status json  가장 먼저 보낸 저장 요청에 응답 · network: true 면 응답 없이 실패
// 출력: { posts: [{tab, body}], storage: {키: 값},
//         tabs: [{savemsg, copymsg, reason, answer(= GPT 칸), answers, helps: {칸: [체크됨, 비활성]}, notes, orphan}] }
"use strict";
const fs = require("fs");
const [jsdomDir, scenarioPath] = process.argv.slice(2);
const { JSDOM } = require(jsdomDir);
const sc = JSON.parse(fs.readFileSync(scenarioPath, "utf8"));

class Store {
  constructor(fail) {
    this.m = new Map();
    this.fail = fail;
  }
  get length() {
    return this.m.size;
  }
  key(i) {
    const k = Array.from(this.m.keys())[i];
    return k === undefined ? null : k;
  }
  getItem(k) {
    return this.m.has(String(k)) ? this.m.get(String(k)) : null;
  }
  setItem(k, v) {
    if (this.fail) throw new Error("QuotaExceededError");
    if (this.quota && String(v).length > this.quota) throw new Error("QuotaExceededError");
    if (this.failKeys && this.failKeys.indexOf(String(k)) >= 0) throw new Error("QuotaExceededError");
    this.m.set(String(k), String(v));
  }
  removeItem(k) {
    if (this.failDelete) throw new Error("SecurityError");
    this.m.delete(String(k));
  }
  clear() {
    this.m.clear();
  }
}

let shift = 0; // wait 단계가 앞당긴 시간(ms)
const realNow = Date.now;
Date.now = () => realNow() + shift;
const local = new Store(!!sc.storage_fail);
for (const [k, v] of Object.entries(sc.seed || {})) {
  local.m.set(k, typeof v === "string" ? v : JSON.stringify(v));
}
const posts = [];
const firstSession = new Store(!!sc.session_fail);
firstSession.quota = sc.session_quota || 0;
firstSession.failKeys = sc.session_fail_keys || [];
for (const [k, v] of Object.entries(sc.session_seed || {})) {
  firstSession.m.set(k, typeof v === "string" ? v : JSON.stringify(v));
}
const pending = [];
const tabs = [];

function open(i, page, from, seedSession) {
  const old = tabs[i];
  if (old && !old.closed) hide(old);
  let session = old ? old.session : new Store(false);
  if (from !== undefined) {
    session = new Store(false);
    for (const [k, v] of tabs[from].session.m) session.m.set(k, v);
  }
  if (seedSession) {
    session = new Store(false);
    for (const [k, v] of Object.entries(seedSession)) {
      session.m.set(k, typeof v === "string" ? v : JSON.stringify(v));
    }
  }
  const pg = sc.pages[page];
  const dom = new JSDOM(fs.readFileSync(pg.html, "utf8"), {
    url: "http://127.0.0.1:8770/?ticker=" + pg.ticker,
    runScripts: "dangerously",
    beforeParse(w) {
      Object.defineProperty(w, "localStorage", { configurable: true, get: () => local });
      Object.defineProperty(w, "sessionStorage", { configurable: true, get: () => session });
      w.Date.now = Date.now;
      Object.defineProperty(w.navigator, "clipboard", {
        configurable: true,
        value: {
          writeText: () =>
            sc.clipboard === "ok" ? Promise.resolve() : Promise.reject(new Error("denied")),
        },
      });
      w.fetch = (url, opts) =>
        new Promise((resolve, reject) => {
          posts.push({ tab: i, body: JSON.parse(opts.body) });
          pending.push({ resolve, reject });
        });
    },
  });
  tabs[i] = { dom, session, page };
}

function hide(t) {
  if (!t.dom) return;
  t.dom.window.dispatchEvent(new t.dom.window.Event("pagehide"));
  t.dom.window.close();
  t.closed = true;
}

function input(w, el, inputType) {
  el.dispatchEvent(new w.InputEvent("input", { bubbles: true, inputType }));
}

function setField(w, d, id, value, how) {
  const el = d.getElementById(id);
  if (how === "paste" || how === "paste_all") {
    if (how === "paste_all") el.setSelectionRange(0, el.value.length);
    else el.setSelectionRange(el.value.length, el.value.length);
    el.dispatchEvent(new w.Event("paste", { bubbles: true }));
    el.value = how === "paste_all" ? value : el.value + value;
    input(w, el, "insertFromPaste");
    return;
  }
  const shorter = value.length < el.value.length;
  el.value = value;
  if (el.tagName === "TEXTAREA") input(w, el, shorter ? "deleteContentBackward" : "insertText");
  else el.dispatchEvent(new w.Event("input", { bubbles: true }));
}

const tick = () => new Promise((r) => setTimeout(r, 0));
const BOXES = ["gpt", "gemini", "claude"];

async function run() {
  tabs[0] = { dom: null, session: firstSession, page: 0, closed: true };
  open(0, 0);
  for (const st of sc.steps) {
    const ti = st.tab || 0;
    if (st.do === "open") {
      open(ti, st.page || 0, st.from, st.session);
    } else if (st.do === "local_set") {
      local.m.set(st.key, typeof st.value === "string" ? st.value : JSON.stringify(st.value));
    } else if (st.do === "storage") {
      if (st.local) local.fail = st.local === "fail";
      if (st.session) tabs[ti].session.fail = st.session === "fail";
      if (st.session_delete) tabs[ti].session.failDelete = st.session_delete === "fail";
      if (st.local_delete) local.failDelete = st.local_delete === "fail";
      if (st.session_fail_keys) tabs[ti].session.failKeys = st.session_fail_keys;
    } else if (st.do === "reload") {
      open(ti, tabs[ti].page);
    } else if (st.do === "close") {
      hide(tabs[ti]);
    } else if (st.do === "wait") {
      shift += st.ms;
    } else if (st.do === "respond") {
      const p = pending.shift();
      if (st.network) p.reject(new Error("network"));
      else
        p.resolve({
          ok: st.status >= 200 && st.status < 300,
          status: st.status,
          json: () => Promise.resolve(st.json || {}),
        });
    } else {
      const w = tabs[ti].dom.window;
      const d = w.document;
      const ans = d.getElementById("answer_" + (st.box || "gpt"));
      if (st.do === "copy") {
        d.getElementById("copy").click();
      } else if (st.do === "manual_copy") {
        d.dispatchEvent(new w.Event("copy", { bubbles: true }));
      } else if (st.do === "select_part") {
        const pre = d.getElementById("copytext");
        const r = d.createRange();
        r.setStart(pre.firstChild, 0);
        r.setEnd(pre.firstChild, 5);
        const s = w.getSelection();
        s.removeAllRanges();
        s.addRange(r);
      } else if (st.do === "copy_answer") {
        ans.setSelectionRange(0, ans.value.length);
        ans.dispatchEvent(new w.Event("copy", { bubbles: true }));
      } else if (st.do === "cut_answer") {
        ans.setSelectionRange(0, ans.value.length);
        ans.dispatchEvent(new w.Event("cut", { bubbles: true }));
        ans.value = "";
        input(w, ans, "deleteByCut");
      } else if (st.do === "drop") {
        ans.dispatchEvent(new w.Event("drop", { bubbles: true }));
        if (st.value) {
          ans.value = ans.value + st.value;
          input(w, ans, "insertFromDrop");
        }
      } else if (st.do === "undo") {
        ans.value = st.value;
        input(w, ans, "historyUndo");
      } else if (st.do === "dragstart") {
        d.getElementById(st.id).dispatchEvent(new w.Event("dragstart", { bubbles: true }));
      } else if (st.do === "check") {
        d.getElementById(st.id).click();
      } else if (st.do === "field") {
        setField(w, d, st.id, st.value, st.how || "type");
      } else if (st.do === "save") {
        d.getElementById("save").click();
      } else {
        throw new Error("모르는 단계: " + st.do);
      }
    }
    for (let i = 0; i < 5; i += 1) await tick();
  }
  const out = {
    posts,
    storage: Object.fromEntries(local.m),
    tabs: tabs.map((t) => {
      if (t.closed) return { closed: true, session: Object.fromEntries(t.session.m) };
      const d = t.dom.window.document;
      const text = (id) => (d.getElementById(id) ? d.getElementById(id).textContent : null);
      const value = (id) => (d.getElementById(id) ? d.getElementById(id).value : null);
      const shown = (id) => {
        const el = d.getElementById(id);
        return el && !el.hidden ? el.textContent : null;
      };
      return {
        session: Object.fromEntries(t.session.m),
        keepmsg: shown("keepmsg"),
        otherdrafts: shown("otherdrafts"),
        olddrafts: shown("olddrafts"),
        savemsg: text("savemsg"),
        copymsg: text("copymsg"),
        reason: value("reason"),
        answer: value("answer_gpt"),
        answers: Object.fromEntries(BOXES.map((b) => [b, value("answer_" + b)])),
        helps: Object.fromEntries(
          BOXES.map((b) => {
            const el = d.getElementById("help_" + b);
            return [b, el ? [el.checked, el.disabled] : null];
          })
        ),
        notes: Object.fromEntries(BOXES.map((b) => [b, text("ainote_" + b)])),
        orphan: shown("orphan") === null ? null : text("orphantext"),
      };
    }),
  };
  for (const t of tabs) if (!t.closed && t.dom) t.dom.window.close();
  process.stdout.write(JSON.stringify(out));
  process.exit(0);
}

run().catch((e) => {
  process.stderr.write(String((e && e.stack) || e));
  process.exit(1);
});
