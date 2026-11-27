"""서버 없이 여는 한 장 · 다시 열기 · 저장 목록의 작은 화면 스크립트 — page_script 에서 나눔(줄 수).

```text
SCRIPT_STATIC  저장 안 되는 한 장(page) — [AI 질문 복사]만(복사 기록 · 초안 · 저장 없음)
SCRIPT_MARK    다시 열기 · 목록 — 이 화면의 글을 복사하면 모든 창의 복사 기록을 '하나로 정할 수 없음'으로
               (옛 질문 원문을 복사해 새 답의 질문으로 오해하지 않게 · page_script 의 복사 기록과 같은 키 · 차례 번호)
```
"""

SCRIPT_STATIC = """
<script>
(function(){
  var $ = function(id){ return document.getElementById(id); };
  var b = $("copy"), m = $("copymsg"), pre = $("copytext");
  if (!b) return;
  b.addEventListener("click", function(){
    var fail = function(){
      $("copybox").open = true;
      var r = document.createRange(); r.selectNodeContents(pre);
      var s = window.getSelection(); s.removeAllRanges(); s.addRange(r);
      m.textContent = "복사가 안 됐습니다 — 아래 글이 선택돼 있으니 ⌘C 로 복사하세요.";
    };
    try {
      navigator.clipboard.writeText(pre.textContent).then(function(){
        m.textContent = "복사됨 — 평소 쓰는 AI 채팅에 붙여 넣으세요.";
      }, fail);
    } catch (e) { fail(); }
  });
})();
</script>
"""


# 다시 열기 · 목록 화면 — 이 화면의 글을 복사하면 모든 창의 복사 기록을 '하나로 정할 수 없음'으로(옛 질문 원문 복사 대비)
SCRIPT_MARK = """
<script>
(function(){
  function mark(){
    try {
      var cur = JSON.parse(localStorage.getItem("poc7_04_clip") || "null");
      var seq = cur && typeof cur.seq === "number" && isFinite(cur.seq) ? cur.seq : 0;
      var c = { from: "mixed", sig: null, at: Date.now(), seq: seq + 1 };
      localStorage.setItem("poc7_04_clip", JSON.stringify(c));
    } catch (e) {
      // 못 쓰면 옛 기록을 지움 — 다른 창이 옛 기록을 이번 복사로 오해하지 않게
      try { localStorage.removeItem("poc7_04_clip"); } catch (e2) {}
    }
  }
  document.addEventListener("copy", mark);
  document.addEventListener("cut", mark);
})();
</script>
"""
