"""화면의 브라우저 동작(연구 서버 화면 · 저장 안 되는 한 장 · 다시 열기 · 목록) — 복사 · AI 답의 질문 출처 · 초안 · 저장.

```text
복사 기록   모든 창이 같이 보는 한 기록(localStorage) {화면 번호 · 질문 지문 · 시각 · 차례 번호} — 앞뒤는 차례 번호로(기기 시계와
            무관) · 이 화면 질문 전체를 실제로 복사했을 때만(클립보드 실패 · 버튼 누름만으로는 아님) · 이 페이지 · 다시 열기 ·
            목록의 다른 글 복사 = 'mixed' · 공유 기록에 쓰지 못한 복사는 그 기록을 지우고(다른 창 = '복사 기록 없음') 이 창에
            '못 씀' 표시를 남겨, 그 뒤 다른 창의 복사가 없으면 이 창에 붙인 답은 'mixed' · 형식이 틀린 기록은 버림
AI 답 출처  칸(GPT · Gemini · Claude)마다 따로 — 답을 붙일(또는 빈 칸에 새로 쓸) 때의 복사 기록 · 그 복사 시각 · 뒤의
            복사나 다른 칸 붙이기로 바뀌지 않음 · 같은 글을 다시 붙여도 지금의 복사 기록 · 이미 쓴 답에 출처가 다른 글을
            덧붙이면 'mixed' · 되돌리기 · 다시 실행으로 바뀐 답은 늘 'mixed'(예전 값의 출처를 기억하지 않음) · 답을 다
            지우면 출처 · 시각 · '판단에 도움' 선택도 지움 · 답이 없는 칸은 '판단에 도움'을 고를 수 없음(PLAN V2 판정 §3)
질문 지문   FNV-1a 32비트(UTF-16 단위) = server.copy_sig — 같은 질문 원문인지 대조
초안        이 창의 저장소(sessionStorage)에만 — 새로 고침 · 서버를 다시 켠 뒤 같은 창에서 되살림 · 다른 창 초안은 가져오지도
            지우지도 않음 · 형식이 맞지 않으면 되살리지 않고 알림 · 빈 초안은 알리지 않음 · 이 창의 다른 ETF 초안은 고르는 길 안내
            · 답 하나짜리 예전 초안 = AI 이름이 세 칸 중 하나면 그 칸으로 · 이름이 없거나 '기타'면 칸에 넣지 않고 읽기 전용
            (그 글을 복사해 붙이면 'mixed')
            · 예전 형식(localStorage) 초안 = 이 창 번호 것만 화면을 열 때 되살림(복사) · 다른 창 번호 · 창 번호 없는 초안은
            되살리지 않고 '예전 화면에 남은 이 ETF 입력'(읽기 전용 목록)에만 보임 · 예전 초안은 지우지 않음 · 이 창에 임시
            저장이 된 뒤에만 '가져옴'을 적음(못 적으면 저장 때 다시 · 그래도 못 적으면 이 창 초안을 '저장 확인'과 함께 남김)
저장 상태   pending(보내는 중 · 결과 모름) · last(마지막으로 저장이 확인된 판단 = 기록 번호 · 입력 지문) — 되살릴 때와 고칠 때
            '이미 저장한 입력' · '저장한 뒤 고친 입력' · '저장됐는지 모름'을 지문 비교로 말함 · 거절(4xx)은 앞선 상태를 지우지 않음
저장        성공 + 보낸 값 = 지금 값 → 초안 지움(위 '가져옴'을 못 적은 경우 말고) · 저장 중 고침 → 초안 남김 ·
            거절(4xx) = 저장 안 됨 · 서버 오류(5xx) · 응답 없음 = 저장됐는지 모름 · '남김' · '새로 고치면 돌아옴' 문구는
            실제 쓰기 결과대로
```
"""

SCRIPT = """
<script>
(function(){
  var BUILD = %(build)s, TICKER = %(ticker)s, END = %(end)s, NAME = %(name)s;
  var PREFIX = "poc7_04_draft_", KEY = PREFIX + TICKER, CLIP = "poc7_04_clip";
  // '가져옴' 표시 이름 = r4 부터 새 이름(r3 판이 초안을 못 쓰고 남긴 옛 표시는 보지 않음)
  var ALONE = "poc7_04_clip_alone", TAKEN = "poc7_04_legacy_taken2";
  var VERDICTS = ["continue", "hold", "unrecorded"];
  var USED = ["rank_flow", "peer", "previous", "weeks", "ai_answer"];
  var $ = function(id){ return document.getElementById(id); };
  var pick = $("pick");
  if (pick) pick.addEventListener("change", function(){
    location.href = "/?ticker=" + encodeURIComponent(pick.value);
  });
  // 뒤로 가기 캐시에서 다시 보이면 새로 고침 — 메모리의 옛 입력이 이 창 초안을 덮지 않게
  // (이 창에 임시 보관이 안 되는 동안은 화면의 입력이 유일한 사본이라 새로 고치지 않음)
  window.addEventListener("pageshow", function(e){
    if (e && e.persisted && kept) location.reload();
  });
  var copyBtn = $("copy"), copyMsg = $("copymsg"), pre = $("copytext");
  var msg = $("savemsg"), saveBtn = $("save"), keepMsg = $("keepmsg");
  // AI 답 세 칸 — 칸마다 붙인 시각 · 질문 출처(복사 기록) · 판단에 도움 선택(PLAN V2 판정 2026-11-26 §3)
  var AIS = [["GPT", "gpt"], ["Gemini", "gemini"], ["Claude", "claude"]], BOXES = [];
  AIS.forEach(function(a){
    var el = $("answer_" + a[1]);
    if (el) BOXES.push({ name: a[0], el: el, help: $("help_" + a[1]), note: $("ainote_" + a[1]),
      from: null, sig: null, copiedAt: null, pastedAt: null, prev: "", pasting: false,
      replaceAll: false });
  });
  function boxOf(name){
    for (var i = 0; i < BOXES.length; i++) if (BOXES[i].name === name) return BOXES[i];
    return null;
  }
  var orphan = null;  // 답 하나짜리 예전 초안의 이름 없는 AI 답(칸에 넣지 않음 · 읽기 전용으로 보임)
  function sig(t){
    var h = 0x811c9dc5;
    for (var i = 0; i < t.length; i++) { h ^= t.charCodeAt(i); h = Math.imul(h, 0x01000193) >>> 0; }
    return ("0000000" + h.toString(16)).slice(-8);
  }
  var SIG = sig(pre.textContent);
  function store(name){ try { return window[name] || null; } catch (e) { return null; } }
  var LS = store("localStorage"), SS = store("sessionStorage");
  function get(s, k){
    if (!s) return null;
    try { return JSON.parse(s.getItem(k) || "null"); } catch (e) { return null; }
  }
  function put(s, k, v){
    if (!s) return false;
    try { s.setItem(k, JSON.stringify(v)); return true; } catch (e) { return false; }
  }
  function del(s, k){
    if (!s) return false;
    try { s.removeItem(k); return true; } catch (e) { return false; }
  }
  function keys(s){
    var out = [];
    if (!s) return out;
    try { for (var i = 0; i < s.length; i++) out.push(s.key(i)); } catch (e) {}
    return out;
  }
  // 복사 기록 — 모든 창이 같이 보는 한 기록(localStorage)뿐 · 앞뒤는 차례 번호(seq)로(기기 시계와 무관)
  // 공유 기록에 쓰지 못한 복사 = 그 기록을 지워 다른 창은 '복사 기록 없음' · 이 창에는 '못 씀' 표시
  // · 화면 번호 · 지문 · 시각은 형식까지 확인(틀린 값은 '복사 기록 없음')
  var ID_RE = /^\\d{8}T\\d{6}Z_[0-9a-f]{8}$/, SIG_RE = /^[0-9a-f]{8}$/;
  // 서버 sane_time 이 받는 것만(시간대 · 1990 ~ 2100 · 있는 날짜 · 24시 아님 · 반박 검토 L1 · 422 로 이어지지 않게)
  var ISO_RE = new RegExp("^(\\\\d{4})-(\\\\d{2})-(\\\\d{2})T(\\\\d{2}):(\\\\d{2})"
    + "(:(\\\\d{2})(\\\\.\\\\d{1,6})?)?(Z|[+-]\\\\d{2}:\\\\d{2})$");
  var aloneMem = null;
  function okFrom(v){
    return v === null || v === "mixed" || (typeof v === "string" && ID_RE.test(v));
  }
  function okSig(v){ return typeof v === "string" && SIG_RE.test(v); }
  function okIso(v){
    var m = typeof v === "string" ? ISO_RE.exec(v) : null;
    if (!m || !isFinite(Date.parse(v))) return false;
    var y = +m[1], mo = +m[2], d = +m[3], day = new Date(Date.UTC(y, mo - 1, d));
    return y >= 1990 && y <= 2100 && day.getUTCMonth() === mo - 1 && day.getUTCDate() === d
      && +m[4] <= 23 && +m[5] <= 59 && (m[7] === undefined || +m[7] <= 59);
  }
  function okTime(v){
    return typeof v === "number" && isFinite(v) && isFinite(new Date(v).getTime());
  }
  function isClip(c){
    if (!c || typeof c !== "object" || Array.isArray(c)) return false;
    return okFrom(c.from === undefined ? null : c.from)
      && (c.sig === null || c.sig === undefined || okSig(c.sig));
  }
  function seqOf(c){ return c && typeof c.seq === "number" && isFinite(c.seq) ? c.seq : 0; }
  function shared(){ var c = get(LS, CLIP); return isClip(c) ? c : null; }
  function setClip(from, s){
    var cur = shared(), rec = { from: from, sig: s, at: Date.now(), seq: seqOf(cur) + 1 };
    if (put(LS, CLIP, rec)) return { alone: false };  // 차례 번호가 올라 예전 '못 씀' 표시보다 뒤가 됨
    var removed = del(LS, CLIP);  // 다른 창이 옛 기록을 이번 복사로 오해하지 않게
    aloneMem = { seq: seqOf(cur), removed: removed }; put(SS, ALONE, aloneMem);
    return { alone: true, removed: removed };
  }
  function clip(){
    var c = shared(), a = aloneMem || get(SS, ALONE);
    if (a && typeof a === "object" && typeof a.seq === "number") {
      // 지웠으면 그 뒤 생긴 공유 기록은 모두 더 나중 것 · 못 지웠으면 차례 번호로 비교
      if (a.removed === true ? !c : seqOf(c) <= a.seq) return { from: "mixed", sig: null };
    }
    return c;
  }
  function copied(){
    var r = setClip(BUILD, SIG);
    copyMsg.textContent = !r.alone ? "복사됨 — 평소 쓰는 AI 채팅에 붙여 넣으세요."
      : "복사됨\\n다만 이 브라우저 저장소에 복사 기록을 남기지 못해, 이 창에 붙인 답의 질문은"
        + " '하나로 정할 수 없음'으로 남습니다." + (r.removed ? ""
        : "\\n다른 창에 붙인 답의 질문도 잘못 기록될 수 있으니 그 창에서 질문을 다시 복사하세요.");
    copyMsg.className = r.alone ? "msg bad" : "msg";
  }
  function selectCopy(){
    $("copybox").open = true;
    var r = document.createRange(); r.selectNodeContents(pre);
    var s = window.getSelection(); s.removeAllRanges(); s.addRange(r);
  }
  function onCopy(e){
    var tg = e && e.target;
    var field = tg && (tg.tagName === "TEXTAREA" || tg.tagName === "INPUT");
    var s = window.getSelection();
    var inPre = !field && s && s.rangeCount && pre.contains(s.anchorNode)
      && pre.contains(s.focusNode);
    if (inPre && String(s).trim() === pre.textContent.trim()) { copied(); return; }
    setClip("mixed", null);  // 이 페이지의 다른 글 — 붙이면 출처를 정할 수 없음
  }
  document.addEventListener("copy", onCopy);
  // 이 페이지의 글(예전 입력의 AI 답 · 다른 칸 답 등)을 끌어 옮기는 것도 '다른 글 복사'와 같음 — 붙이면 출처를
  // 정할 수 없음(반박 검토 F4)
  document.addEventListener("dragstart", function(){ setClip("mixed", null); });
  document.addEventListener("cut", onCopy);
  if (copyBtn) copyBtn.addEventListener("click", function(){
    var fail = function(){
      selectCopy();
      copyMsg.textContent = "복사가 안 됐습니다 — 아래 글이 선택돼 있으니 ⌘C 로 복사하세요"
        + " · 버튼을 다시 눌러도 됩니다.";
      copyMsg.className = "msg bad";
    };
    try {
      navigator.clipboard.writeText(pre.textContent).then(copied, fail);
    } catch (e) { fail(); }
  });
  var pending = null, lastSaved = null, shownSaved = false;
  var imported = null;  // 이 창 번호의 예전 초안에서 가져옴 {key, at, marked} — 초안에 같이 둠(새로 고쳐도 이어짐)
  function fromClip(){
    var c = clip();
    if (!c || c.from === null || c.from === undefined) return { from: null, sig: null, at: null };
    if (c.from === "mixed") return { from: "mixed", sig: null, at: null };
    return { from: c.from, sig: okSig(c.sig) ? c.sig : null,
      at: okTime(c.at) ? new Date(c.at).toISOString() : null };
  }
  function val(id){ return $(id).value; }
  function form(){
    var v = document.querySelector("input[name=verdict]:checked");
    var boxes = document.querySelectorAll("input[name=used]:checked");
    var used = Array.prototype.map.call(boxes, function(x){ return x.value; });
    return { build_id: BUILD, ticker: TICKER, verdict: v ? v.value : "unrecorded",
      reason: val("reason"), next_check: val("next"), used: used,
      ais: BOXES.map(function(b){
        return { name: b.name, answer: b.el.value, helpful: !!(b.help && b.help.checked),
          pasted_at: b.pastedAt, answer_from: b.from, answer_sig: b.sig,
          answer_copied_at: b.copiedAt };
      }),
      ai_excerpt: val("excerpt"), end: END };
  }
  // 칸 아래 안내 · '판단에 도움' 켜고 끔 — 답이 없으면 선택을 지우고 못 고르게
  function hm(iso){
    var t = new Date(iso);
    return (t.getMonth() + 1) + "/" + t.getDate() + " " + ("0" + t.getHours()).slice(-2) + ":"
      + ("0" + t.getMinutes()).slice(-2);
  }
  function refresh(b){
    var has = !!b.el.value.trim();
    if (b.help) { if (!has) b.help.checked = false; b.help.disabled = !has; }
    if (!b.note) return;
    if (!has) { b.note.textContent = "답 미입력"; return; }
    // 붙인 시각 · 질문 출처는 줄을 나눔 · 버튼 이름은 줄 중간에서 꺾이지 않게
    b.note.textContent = "";
    var add = function(n){ b.note.appendChild(n); };
    if (b.pastedAt) {
      add(document.createTextNode("붙인 시각 " + hm(b.pastedAt)));
      add(document.createElement("br"));
    }
    if (b.from === null) {
      add(document.createTextNode("질문 복사 기록 없음 — 먼저 "));
      var k = document.createElement("span"); k.className = "nw"; k.textContent = "[AI 질문 복사]";
      add(k); add(document.createTextNode("를 누르세요"));
      return;
    }
    add(document.createTextNode(b.from === "mixed" ? "질문: 하나로 정할 수 없음"
      : b.from === BUILD ? "질문: 이 화면의 복사문"
      : b.sig && b.sig === SIG ? "질문: 이 화면과 같은 복사문"
      : "질문: 다른 화면의 복사문(저장할 때 서버가 확인)"));
  }
  function showOrphan(){
    var box = $("orphan"), t = $("orphantext");
    if (!box || !t) return;
    box.hidden = !orphan; t.textContent = orphan || "";
  }
  // 입력 지문 — 화면 번호 · 기준일을 뺀 내 입력만(새로 고친 뒤에도 '저장한 그 입력인지' 비교)
  function inputSig(f){
    var x = {};
    for (var k in f) if (k !== "build_id" && k !== "end" && k !== "ticker") x[k] = f[k];
    return sig(JSON.stringify(x));
  }
  // 초안 — 이 창의 저장소(sessionStorage)에만
  var kept = true;
  function keep(){
    var d = form(); d.draft_v = 6; d.at = Date.now(); d.name = NAME;
    if (orphan) d.ai_orphan = orphan;
    d.save = { pending: pending, last: lastSaved }; d.imported = imported;
    kept = put(SS, KEY, d);
    if (keepMsg) keepMsg.hidden = kept;
    return kept;
  }
  function drop(){ del(SS, KEY); if (keepMsg) keepMsg.hidden = true; }
  function keepOrphan(){
    kept = put(SS, KEY, { draft_v: 6, at: Date.now(), name: NAME, end: END, ai_orphan: orphan });
    if (keepMsg) keepMsg.hidden = kept;
  }
  // 저장 뒤 남겨 둔 초안 = 예전 입력의 AI 답만(다른 입력 · 저장 상태 없음)
  function orphanOnly(d){
    var rest = {};
    var base = ["draft_v", "at", "name", "end", "ai_orphan"];
    for (var k in d) if (base.indexOf(k) < 0) rest[k] = d[k];
    return !!(d.ai_orphan || "").trim() && !filled(rest);
  }
  function str(v){ return v === undefined || v === null || typeof v === "string"; }
  function okAi(x){
    return !!x && typeof x === "object" && !Array.isArray(x) && typeof x.name === "string"
      && ["answer", "pasted_at", "answer_from", "answer_sig", "answer_copied_at"].every(function(k){
        return str(x[k]);
      }) && (x.helpful === undefined || typeof x.helpful === "boolean");
  }
  function valid(d){
    if (!d || typeof d !== "object" || Array.isArray(d)) return false;
    if (d.verdict !== undefined && VERDICTS.indexOf(d.verdict) < 0) return false;
    var texts = ["reason", "next_check", "ai_name", "ai_answer", "ai_excerpt", "ai_pasted_at",
      "answer_from", "answer_sig", "answer_copied_at", "end", "name", "ai_orphan"];
    for (var i = 0; i < texts.length; i++) if (!str(d[texts[i]])) return false;
    if (d.ais !== undefined && !(Array.isArray(d.ais) && d.ais.every(okAi))) return false;
    if (d.used !== undefined && !(Array.isArray(d.used)
      && d.used.every(function(u){ return USED.indexOf(u) >= 0; }))) return false;
    return d.save === undefined || d.save === null || typeof d.save === "object";
  }
  function filled(d){
    var texts = ["reason", "next_check", "ai_answer", "ai_excerpt", "ai_name", "ai_orphan"];
    for (var i = 0; i < texts.length; i++) if ((d[texts[i]] || "").trim()) return true;
    if (Array.isArray(d.ais) && d.ais.some(function(x){
      return (x.answer || "").trim() || x.helpful === true;
    })) return true;
    var sv = d.save;  // 새 형식은 저장 상태 칸이 늘 있음 — 실제 상태가 있을 때만 '내용 있음'
    var saved = !!sv && typeof sv === "object" && !!(sv.pending || sv.last || sv.state);
    return (d.verdict && d.verdict !== "unrecorded") || !!(d.used && d.used.length) || saved;
  }
  function box(name, value){
    var els = document.querySelectorAll("input[name=" + name + "]");
    for (var i = 0; i < els.length; i++) if (els[i].value === value) return els[i];
    return null;
  }
  function link(id, text){
    var a = document.createElement("a");
    a.href = "/reviews/" + encodeURIComponent(id); a.textContent = text || "다시 열기";
    return a;
  }
  function say(text, bad){ msg.textContent = text; msg.className = bad ? "msg bad" : "msg"; }
  // 안내는 문장마다 줄을 나눔(메시지 칸은 줄바꿈 유지)
  function note(text){
    var lead = msg.textContent ? "\\n" : "";
    msg.appendChild(document.createTextNode(lead + text.replace(/^\\s+/, "")));
  }
  function savedNote(){
    // 마지막으로 저장한 판단과 지금 입력이 같은지(지문)
    var eq = !!lastSaved.sig && lastSaved.sig === inputSig(form());
    say(eq ? "저장됨 — " : "저장한 뒤 고친 내용은 아직 저장 안 됨 — 다시 저장하면 새 기록으로 남습니다\\n"
      + "저장한 판단: ", !eq);
    msg.appendChild(link(lastSaved.id));
  }
  function restore(d, fromLegacy){
    var r = box("verdict", d.verdict || "unrecorded");
    if (r) r.checked = true;
    $("reason").value = d.reason || ""; $("next").value = d.next_check || "";
    $("excerpt").value = d.ai_excerpt || "";
    // 형식이 틀린 시각 · 화면 번호 · 지문은 버림('복사 기록 없음') — 저장 거절(422)로 이어지지 않게
    // 예전 초안(draft_v 없음)의 화면 번호는 '마지막 복사'라 답의 출처로 쓰지 않음
    function fill(b, x, ver){
      b.el.value = x.answer || "";
      b.pastedAt = okIso(x.pasted_at) ? x.pasted_at : null;
      var af = x.answer_from === undefined ? null : x.answer_from;
      b.from = ver >= 2 && okFrom(af) ? af : null;
      b.sig = ver >= 3 && okSig(x.answer_sig) ? x.answer_sig : null;
      b.copiedAt = ver >= 5 && okIso(x.answer_copied_at) ? x.answer_copied_at : null;
      if (b.help) b.help.checked = x.helpful === true;
    }
    var ver = d.draft_v || 0;
    if (Array.isArray(d.ais)) {
      d.ais.forEach(function(x){ var b = boxOf(x.name); if (b) fill(b, x, ver); });
    } else if ((d.ai_answer || "").trim()) {
      // 답 하나짜리 예전 초안 — 이름이 세 칸 중 하나면 그 칸으로 · 아니면 칸에 넣지 않고 읽기 전용
      var one = boxOf(d.ai_name);
      if (one) {
        fill(one, { answer: d.ai_answer, pasted_at: d.ai_pasted_at, answer_from: d.answer_from,
          answer_sig: d.answer_sig, answer_copied_at: d.answer_copied_at }, ver);
      } else orphan = d.ai_answer;
    }
    if (typeof d.ai_orphan === "string" && d.ai_orphan.trim()) orphan = d.ai_orphan;
    BOXES.forEach(function(b){ b.prev = b.el.value; refresh(b); });
    showOrphan();
    var s = d.save || null;
    if (d.draft_v >= 5 && s) {
      pending = (s.pending === "sending" || s.pending === "unknown") ? s.pending : null;
      // 칸 세 개 이전(v5) 초안의 입력 지문은 지금 입력 모양과 비교할 수 없음 — '그 뒤 고쳤는지 모름'(F6)
      lastSaved = (s.last && typeof s.last.id === "string" && ID_RE.test(s.last.id))
        ? { id: s.last.id, sig: d.draft_v >= 6 && okSig(s.last.sig) ? s.last.sig : null } : null;
    } else if (s && s.state) {
      if (s.state === "sending" || s.state === "unknown") pending = s.state;
      else if (typeof s.id === "string" && ID_RE.test(s.id)) lastSaved = { id: s.id, sig: null };
    }
    (d.used || []).forEach(function(u){ var c = box("used", u); if (c) c.checked = true; });
    var bad = false, where = d.end ? "(기준일 " + d.end + ")" : "";
    if (pending) {
      bad = true;
      say("저장됐는지 모르는 입력을 되살렸습니다.\\n「지난 판단 열기」에서 먼저 확인하고, 없을 때만 다시 저장하세요.");
    } else if (lastSaved) {
      var eq = !!lastSaved.sig && lastSaved.sig === inputSig(form());
      say((eq ? "이미 저장한 판단의 입력입니다.\\n다시 저장하면 같은 내용이 새 기록으로 하나 더 남습니다."
        : lastSaved.sig ? "앞서 저장한 판단 뒤에 고친 입력을 되살렸습니다.\\n다시 저장하면 새 기록으로 남습니다."
        : "앞서 저장한 판단이 있는 입력을 되살렸습니다(그 뒤 고쳤는지는 모름).\\n다시 저장하면 새 기록으로"
          + " 남습니다.") + "\\n");
      msg.appendChild(link(lastSaved.id, "저장한 판단 다시 열기"));
      shownSaved = true;
    } else if (orphanOnly(d)) {
      say("");  // 저장 뒤 남겨 둔 '예전 입력의 AI 답'만 있음 — 아래 안내만
    } else {
      say(fromLegacy ? "이 브라우저에 남아 있던 이 ETF 입력을 되살렸습니다" + where
        + ".\\n다른 창에도 같은 입력이 남아 있을 수 있으니 한 창에서만 저장하세요."
        : "저장하지 않은 입력을 되살렸습니다" + where + ".");
    }
    var got = BOXES.filter(function(b){ return b.el.value.trim(); });
    if (got.length) {
      var same = got.filter(function(b){ return b.sig && b.sig === SIG; });
      var other = got.filter(function(b){ return !(b.sig && b.sig === SIG); });
      var names = function(xs){ return xs.map(function(b){ return b.name; }).join(" · "); };
      if (same.length) note(" 되살린 AI 답(" + names(same) + ")은 이 화면과 같은 질문의 답입니다.");
      if (other.length) {
        note(" 되살린 AI 답(" + names(other) + ")은 이 화면 질문의 답으로 기록되지 않습니다 — 이 화면 질문을"
          + " 복사해 받은 답으로 바꿔 붙이면 이 화면 질문으로 남습니다.");
      }
      if (d.end && d.end !== END) {
        bad = true;
        note(" 기준일이 " + END + " 로 바뀌었으니 AI 답은 새 질문으로 다시 받는 것이 맞습니다.");
      }
    }
    if (orphan) {
      bad = true;
      note(" 예전 입력의 AI 답은 어느 AI 의 답인지 적혀 있지 않아 칸에 넣지 않았습니다 — ③ 의 '예전 입력의"
        + " AI 답'에서 복사해 맞는 칸에 붙이세요(질문은 '하나로 정할 수 없음'으로 남습니다).");
    }
    if (bad) msg.className = "msg bad";
  }
  // 예전 형식(이 브라우저 공용 저장소) 초안 — 새 형식과 같은 규칙: 임시 입력은 그 창의 것
  //  · 이 창 번호(poc7_04_tab) 초안만 화면을 열 때 되살림(복사 · 새로 고친 원래 창 · 그 창에서 연 창)
  //  · 다른 창 번호 · 창 번호 없는 초안은 되살리지도 지우지도 않음 — 아래 읽기 전용 목록에만 보임
  //  · 이 창에 임시 저장이 된 뒤에만 '가져옴'을 이 창에 적음(못 남기면 다음에 다시 가져옴)
  function taken(){ var t = get(SS, TAKEN); return Array.isArray(t) ? t : []; }
  function markTaken(o){ return put(SS, TAKEN, taken().concat([{ key: o.key, at: o.at }])); }
  function ownLegacy(){
    var tab = null;
    try { tab = SS && SS.getItem("poc7_04_tab"); } catch (e) {}
    if (!tab) return null;
    var k = KEY + "__" + tab, d = get(LS, k);
    if (!valid(d) || !filled(d)) return null;
    var at = okTime(d.at) ? d.at : null;
    if (taken().some(function(t){ return t && t.key === k && t.at === at; })) return null;
    return { key: k, d: d, at: at };
  }
  try {
    // 읽을 수 없거나(JSON 아님) 형식이 틀린 초안 = '없음'이 아니라 '되살리지 못함'
    var raw = null, mineDraft = null, broken = false, old = null;
    try { raw = SS ? SS.getItem(KEY) : null; } catch (e) { raw = null; }
    if (raw !== null && raw !== undefined) {
      try { mineDraft = JSON.parse(raw); } catch (e) { broken = true; }
    }
    if (broken || (mineDraft !== null && !valid(mineDraft))) {
      say("이 창에 남아 있던 입력의 형식이 맞지 않아 되살리지 못했습니다 — 새로 쓰면 그 입력은 지워집니다.", true);
    } else {
      var d = (mineDraft && filled(mineDraft)) ? mineDraft : null;
      if (!d) { old = ownLegacy(); d = old && old.d; }
      if (d) {
        if (old) imported = { key: old.key, at: old.at, marked: false };
        else if (d.imported && typeof d.imported.key === "string") {
          imported = { key: d.imported.key, at: okTime(d.imported.at) ? d.imported.at : null,
            marked: d.imported.marked === true };
        }
        restore(d, !!old);
        if (keep()) {
          if (old) { imported.marked = markTaken(imported); keep(); }
        } else {
          note(" 이 창에 임시로 남기지 못했습니다 — 창을 닫기 전에 쓴 내용을 따로 옮겨 두세요.");
          msg.className = "msg bad";
        }
      }
    }
  } catch (e) {
    say("이 창에 남아 있던 입력을 되살리지 못했습니다 — 새로 쓰면 그 입력은 지워집니다.", true);
  }
  // 예전 화면에 남은 이 ETF 입력(이 창 번호 것 말고) — 읽기만 · 화면 칸에 넣거나 저장소에 쓰지 않음
  // (예전 판은 창 번호를 자주 바꿔 그 창 것도 여기로 옴 · 여기서 복사한 글은 '하나로 정할 수 없음')
  (function(){
    var box = $("olddrafts"), body = $("olddraftsbody");
    if (!box || !body) return;
    var tab = null;
    try { tab = SS && SS.getItem("poc7_04_tab"); } catch (e) {}
    var own = tab ? KEY + "__" + tab : null, list = [];
    keys(LS).forEach(function(k){
      if (k === own || (k !== KEY && !(k && k.indexOf(KEY + "__") === 0))) return;
      var d = get(LS, k);
      if (valid(d) && filled(d)) list.push({ d: d, at: okTime(d.at) ? d.at : null });
    });
    if (!list.length) return;
    list.sort(function(a, b){ return (b.at || 0) - (a.at || 0); });
    $("olddraftscount").textContent = String(list.length);
    list.forEach(function(o){
      var item = document.createElement("div"), head = [];
      item.className = "olditem";
      if (o.at !== null) {
        var t = new Date(o.at);
        head.push((t.getMonth() + 1) + "/" + t.getDate() + " " + ("0" + t.getHours()).slice(-2)
          + ":" + ("0" + t.getMinutes()).slice(-2));
      }
      head.push("판단 " + ({ "continue": "검토 계속", hold: "보류" }[o.d.verdict] || "미기록"));
      if ((o.d.reason || "").trim()) head.push("이유: " + o.d.reason.trim());
      if ((o.d.next_check || "").trim()) head.push("다음 확인: " + o.d.next_check.trim());
      var line = document.createElement("div"); line.textContent = head.join(" · ");
      item.appendChild(line);
      if ((o.d.ai_answer || "").trim()) {
        var pre2 = document.createElement("pre"); pre2.textContent = o.d.ai_answer;
        item.appendChild(pre2);
      }
      body.appendChild(item);
    });
    box.hidden = false;
  })();
  // 이 창에 저장하지 않은 다른 ETF 입력 — 고르는 길 안내(다른 창에는 없음)
  (function(){
    var holder = $("otherdrafts");
    if (!holder) return;
    var found = [];
    keys(SS).forEach(function(k){
      if (!k || k.indexOf(PREFIX) !== 0 || k === KEY) return;
      var d = get(SS, k);
      if (valid(d) && filled(d)) found.push({ t: k.slice(PREFIX.length), n: d.name || "" });
    });
    if (!found.length) return;
    holder.appendChild(document.createTextNode("이 창에 저장하지 않은 다른 ETF 입력: "));
    found.forEach(function(f, i){
      if (i) holder.appendChild(document.createTextNode(" · "));
      var a = document.createElement("a");
      a.href = "/?ticker=" + encodeURIComponent(f.t);
      a.textContent = (f.n ? f.n + " " : "") + "(" + f.t + ")";
      holder.appendChild(a);
    });
    holder.hidden = false;
  })();
  function edited(){
    keep();
    if (lastSaved && !pending && shownSaved) savedNote();
  }
  BOXES.forEach(function(b){
    var el = b.el;
    b.prev = el.value; refresh(b);
    el.addEventListener("paste", function(){
      b.pasting = true;
      b.replaceAll = el.selectionStart === 0 && el.selectionEnd === el.value.length;
      setTimeout(function(){ b.pasting = false; b.replaceAll = false; }, 0);
    });
    el.addEventListener("drop", function(){
      b.pasting = true; b.replaceAll = false;
      setTimeout(function(){ b.pasting = false; }, 0);
    });
    el.addEventListener("input", function(e){
      var now = el.value, t = (e && e.inputType) || "";
      var paste = /^insertFrom(Paste|Drop)/.test(t) || (!t && b.pasting);
      var hist = /^history(Undo|Redo)$/.test(t);
      // 되돌리기 · 다시 실행으로 바뀐 답 = 어느 질문의 답인지 정할 수 없음(예전 값의 출처를 기억하지 않음)
      var c = fromClip();
      if (!now.trim()) {
        b.from = null; b.sig = null; b.copiedAt = null; b.pastedAt = null;
      } else if (hist) {
        b.from = "mixed"; b.sig = null; b.copiedAt = null;
      } else if (paste && (!b.prev.trim() || b.replaceAll)) {
        b.from = c.from; b.sig = c.sig; b.copiedAt = c.at;
        b.pastedAt = new Date().toISOString();
      } else if (paste) {
        if (b.from !== c.from) { b.from = "mixed"; b.sig = null; b.copiedAt = null; }
        b.pastedAt = new Date().toISOString();
      } else if (!b.prev.trim()) {
        b.from = c.from; b.sig = c.sig; b.copiedAt = c.at;
      }
      b.pasting = false; b.replaceAll = false; b.prev = now; refresh(b); edited();
    });
  });
  document.querySelectorAll("input, textarea, select").forEach(function(el){
    if (el.id === "pick" || /^answer_/.test(el.id)) return;
    el.addEventListener("input", edited); el.addEventListener("change", edited);
  });
  var UNKNOWN = "저장됐는지 모릅니다 — 「지난 판단 열기」에서 확인하고, 없으면 다시 저장하세요";
  function keptText(){
    return kept ? "\\n쓴 내용은 이 창에 임시로 남아 있습니다."
        + "\\n서버를 다시 켰다면 이 창에서 새로 고치세요 — 새로 열리는 창에는 이 입력이 없으니 이 창을 닫지 마세요."
      : "\\n이 창에 임시로 남기지 못했습니다 — 창을 닫거나 새로 고치기 전에 쓴 내용을 따로 옮겨 두세요.";
  }
  function bad(text){ saveBtn.disabled = false; shownSaved = false; say(text, true); }
  if (saveBtn) saveBtn.addEventListener("click", function(){
    var f = form(), body = JSON.stringify(f), sent = inputSig(f), before = pending;
    pending = "sending"; keep();
    saveBtn.disabled = true; shownSaved = false; say("저장 중…");
    fetch("/api/reviews", { method: "POST", headers: { "Content-Type": "application/json" },
      body: body })
      .then(function(res){
        return res.json().then(function(j){ return { status: res.status, ok: res.ok, j: j }; },
          function(){ return { status: res.status, ok: false, j: {} }; });
      })
      .then(function(x){
        if (x.ok && typeof x.j.review_id === "string") {
          // 보낸 값 = 지금 값일 때만 초안을 지움 — 지우기 전에 '저장 확인'을 먼저 적음(지우기만 실패해도 정확히 알림)
          var same = JSON.stringify(form()) === body;
          pending = null; lastSaved = { id: x.j.review_id, sig: sent };
          saveBtn.disabled = false; shownSaved = true;
          // 가져온 예전 초안의 '가져옴'을 아직 못 적었으면 다시 적음 — 그래도 못 적으면 이 창 초안을 지우지 않고
          // '저장 확인'과 함께 남김(새로 고치면 예전 초안 대신 '이미 저장한 입력'으로 되살림)
          if (imported && !imported.marked) imported.marked = markTaken(imported);
          keep();
          if (same) {
            // 칸에 넣지 않은 예전 입력의 AI 답은 저장 뒤에도 이 창에 남김(그 글만 · F5)
            if (!imported || imported.marked) { if (orphan) keepOrphan(); else drop(); }
            savedNote();
            return;
          }
          say("저장을 누른 때의 내용만 저장됨\\n저장 중에 고친 내용은 아직 저장 안 됨("
            + (kept ? "이 창에 임시로 남김" : "이 창에 임시로 남기지 못함 — 창을 닫기 전에 따로 옮겨 두세요")
            + " · 다시 저장하면 새 기록)\\n", true);
          msg.appendChild(link(x.j.review_id, "저장한 판단 다시 열기"));
          return;
        }
        if (x.status >= 400 && x.status < 500) {
          pending = before; keep();  // 거절 = 이번 시도는 안 됨 · 앞선 '모름' · 저장 기록은 그대로
          if (x.status === 409) {
            bad("저장 안 됨\\n" + (x.j.error || "서버가 이 화면 자료를 갖고 있지 않습니다") + (kept
              ? "\\n이 창을 새로 고치면 쓴 내용이 돌아옵니다(새로 고친 뒤 다시 저장)."
              : "\\n이 창에 임시로 남기지 못했으니 새로 고치기 전에 쓴 내용을 따로 옮겨 두세요."));
          } else if (x.j.fix === "reload") {
            // 화면 자료 쪽 문제 — 같은 화면에서 다시 저장해도 같음(반박 검토 D5)
            bad("저장 안 됨 — 이 화면 자료로는 저장할 수 없습니다\\n" + (x.j.error || "")
              + "\\n이 창을 새로 고쳐 다시 연 뒤 저장해 보세요." + keptText());
          } else {
            bad("저장 안 됨 — 다시 저장\\n" + (x.j.error || "서버가 거절했습니다") + keptText());
          }
          return;
        }
        pending = "unknown"; keep();
        bad(UNKNOWN + (x.j.error ? "\\n" + x.j.error : "") + keptText());
      }, function(){
        pending = "unknown"; keep();
        bad(UNKNOWN + "\\n연구 서버의 응답을 받지 못했습니다(꺼졌을 수 있음)." + keptText());
      });
  });
})();
</script>
"""
