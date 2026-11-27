"""맥북 내부 주소(127.0.0.1) 전용 작은 연구 서버 — 화면 · 저장 · 다시 열기(PLAN §2-4 · §4 · Q1 = b).

```text
GET  /?ticker=T           한 후보 화면(없으면 1개월 1위) — 화면마다 build_id 와 그때 자료(스냅숏)를 서버 메모리에 둔다
POST /api/reviews         {build_id, 판단 입력} → 그 build_id 의 스냅숏 + 판단을 한 파일로(한 번만 쓰기)
GET  /reviews · /reviews/<id>   저장 목록 · 다시 열기(저장 때 고정한 화면 조각 그대로)
막음  Host 가 127.0.0.1 · localhost(이 포트)가 아니면 403 · POST 는 JSON 만 · Origin 이 있으면 이 서버여야 함 ·
      본문 1MB 넘으면 413 · 판단 근거 DB · 시세 DB 는 읽기만
자료  시세 DB 지문이 바뀌면 다음 화면 요청 때 다시 계산(그 전 화면의 저장은 그 화면 자료로 고정)
```
"""

from __future__ import annotations

import json
from collections import OrderedDict
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Callable, Mapping, Optional
from urllib.parse import parse_qs, urlsplit

from app.candidate_compare import current as CU
from app.entry_timing.protocol import CheckRequired, new_id
from app.weekly_decision import evidence as E
from app.weekly_decision import history as H
from app.weekly_decision import lines as L
from app.weekly_decision import page as PG
from app.weekly_decision import page_live as PL
from app.weekly_decision import page_saved as PS
from app.weekly_decision import store as ST

# 요청 크기 상한 = 입력 칸 상한을 모두 채운 최악의 JSON 크기 + 여유(검증 F23 과 같은 뿌리 — 입력 상한 안이면
# 요청도 받는다). 브라우저 JSON.stringify 는 제어 문자 한 글자를 \\uXXXX(6바이트)로 쓴다 · 다른 글자는 4바이트 이하.
MAX_BODY = (
    6
    * (
        len(ST.AI_BOXES) * ST.LIMITS["ai_answer"]
        + ST.LIMITS["reason"]
        + ST.LIMITS["next_check"]
        + ST.LIMITS["ai_excerpt"]
    )
    + 64 * 1024
)
MAX_BUILDS = 64
SCHEMA_SNAPSHOT = "poc7_04_snapshot_v1"


def copy_sig(text: str) -> str:
    """질문 원문 지문(FNV-1a 32비트 · UTF-16 단위) — 화면 스크립트의 sig() 와 같은 계산(같은 글인지 대조용 · 보안 용도 아님)."""
    h = 0x811C9DC5
    b = text.encode("utf-16-le")
    for i in range(0, len(b), 2):
        h ^= b[i] | (b[i + 1] << 8)
        h = (h * 0x01000193) & 0xFFFFFFFF
    return f"{h:08x}"


class NotCandidate(LookupError):
    """이번 주 후보 목록(조회 조건 · 같은 1개월 기간) 밖의 ETF — 사유를 함께 보인다."""

    def __init__(self, ticker: str, name: Optional[str], why: str) -> None:
        super().__init__(ticker)
        self.ticker, self.name, self.why = ticker, name, why


class App:
    """화면 · 저장 처리(HTTP 와 분리 — 시험이 직접 부른다)."""

    def __init__(
        self,
        *,
        db: Path,
        decision_db: Path,
        root: Path,
        end: Optional[str],
        filters: Mapping[str, bool],
        # (공식 기준정보 · 토큰 사전) — 공식 기준정보를 읽지 못하면 None(peers = '읽지 못함' · 검증 r3 B-6)
        sources: Callable[
            [], tuple[Optional[Mapping[str, Any]], Optional[Mapping[str, Any]]]
        ],
        reader: Optional[Callable[[str, Mapping[str, Any]], Mapping[str, Any]]] = None,
        is_trading: Optional[Callable[[str], bool]] = None,
        now: Callable[[], datetime] = CU.now_kst,
    ) -> None:
        self.db, self.decision_db, self.root = Path(db), Path(decision_db), Path(root)
        self.end, self.filters = end, dict(filters)
        self.sources, self.reader, self.is_trading, self.now = (
            sources,
            reader,
            is_trading,
            now,
        )
        self.ctx: Optional[H.Context] = None
        self.builds: OrderedDict[str, dict[str, Any]] = OrderedDict()

    def context(self) -> H.Context:
        """지금 시세 DB 지문이 같으면 계산한 자료를 다시 쓰고, 바뀌었으면 새로 계산한다."""
        market = CU.read_market(self.db, self.end)
        fp = CU.fingerprint(market)
        if (
            self.ctx is None
            or self.ctx.fingerprint != fp
            or self.ctx.end != market["end"]
        ):
            official, dictionary = self.sources()
            self.ctx = H.load_context(
                self.db,
                self.end,
                filters=self.filters,
                official=official,
                dictionary=dictionary,
                is_trading=self.is_trading,
            )
            if self.ctx.fingerprint != fp:
                # 계산하는 사이 저장이 바뀜 — 이 자료는 쓰지 않는다(한 시점 자료만)
                self.ctx = None
                raise RuntimeError(
                    "자료를 읽는 사이 시세 자료가 바뀌었습니다 — 다시 열어 주세요"
                )
        return self.ctx

    def candidates(self, ctx: H.Context) -> list[dict[str, Any]]:
        return [
            {
                "rank": it["rank"],
                "ticker": it["ticker"],
                "name": it["name"],
                "top30": it["top30"],
            }
            for it in ctx.build.get("items") or []
        ]

    def review(self, ticker: Optional[str]) -> tuple[H.Context, dict[str, Any]]:
        ctx = self.context()
        items = ctx.build.get("items") or []
        if not items:
            raise LookupError("이번 주 후보 목록을 만들 수 없습니다")
        t = ticker or items[0]["ticker"]
        if ctx.item(t) is None:
            common = (ctx.build.get("windows") or {}).get("one_month")
            why = H.exclusion(ctx.market, t, ctx.filters, common)
            raise NotCandidate(t, ctx.market["names"].get(t), L.why(why))
        listing = ST.list_reviews(self.root)
        rv = E.compose(
            ctx,
            t,
            sessions=H.read_sessions(self.decision_db),
            reviews=listing["items"],
            reader=self.reader,
            cutoff=H.cutoff_of(self.end, ctx.end, self.now()),
            reviews_broken=len(listing["broken"]),
        )
        return ctx, rv

    def page(self, ticker: Optional[str]) -> str:
        ctx, rv = self.review(ticker)
        bid = new_id(self.now())
        self.builds[bid] = {
            "schema": SCHEMA_SNAPSHOT,
            "build_id": bid,
            "built_at": self.now().isoformat(timespec="seconds"),
            "ticker": rv["ticker"],
            "name": rv["name"],
            "end": rv["end"],
            "filters": dict(rv["filters"]),
            "fingerprints": ctx.fingerprints(),
            "review": rv,
            "copy": rv["copy"],
            "screen": PG.screen_parts(rv),
        }
        while len(self.builds) > MAX_BUILDS:
            self.builds.popitem(last=False)
        # 지난 판단 목록 = compose 가 검토 시점 필터를 거친 것(근거와 같은 필터 · 따로 거르지 않음)
        return PL.render_live(
            rv, build_id=bid, candidates=self.candidates(ctx), reviews=rv["past"]
        )

    def list_page(self) -> str:
        """저장 목록 — 끝일을 지정한 서버면 검토 시점 이후에 저장한(또는 더 뒤 기준일) 판단에 표시."""
        listing = ST.list_reviews(self.root)
        if self.end is None:
            return PS.render_list(listing)
        ctx = self.context()
        cut = H.cutoff_of(self.end, ctx.end, self.now())
        later = {
            r["review_id"]
            for r in listing["items"]
            if r["end"] > ctx.end or not H.known(r["saved_at"], cut)
        }
        return PS.render_list(listing, later=later, end=ctx.end)

    def asked(
        self,
        src: Optional[str],
        snap: Mapping[str, Any],
        has_answer: bool,
        sig: Optional[str] = None,
    ) -> dict[str, Any]:
        """AI 답이 어느 화면의 질문으로 받은 것인지 — 서버가 가진 화면 자료로만 판정(브라우저 글을 근거로 쓰지 않음).

        src = 브라우저가 '답을 붙일 때 마지막으로 복사한 화면 번호'로 보낸 값(뒤의 복사로 바뀌지 않음)
        sig = 그 질문 원문의 지문 — 서버가 그 화면 자료를 더 갖고 있지 않을 때만 이 화면 원문과 대조."""
        if not has_answer:
            return {"state": "no_answer"}
        if src is None:
            return {"state": "no_copy_record"}
        if src == ST.MIXED:
            return {"state": "mixed"}
        if src == snap["build_id"]:
            return {"state": "this_screen"}
        other = self.builds.get(src)
        if other is None:
            if sig is not None and sig == copy_sig(snap["copy"]):
                return {"state": "same_copy", "build_id": src, "by": "copy_sig"}
            return {"state": "unknown_screen", "build_id": src}
        if other["copy"] == snap["copy"]:
            # 다시 연 같은 화면 — 화면 번호만 다르고 질문 원문이 같다
            return {"state": "same_copy", "build_id": src}
        return {
            "state": "other_screen",
            "build_id": src,
            "ticker": other["ticker"],
            "end": other["end"],
            "copy": other["copy"],
        }

    def save(self, body: Any) -> tuple[int, dict[str, Any]]:
        """저장 — 화면 번호의 스냅숏과 판단 입력만으로(브라우저가 보낸 근거 값은 쓰지 않음)."""
        if not isinstance(body, dict):
            return 400, {"error": "요청 형식이 올바르지 않습니다"}
        snap = self.builds.get(str(body.get("build_id") or ""))
        if snap is None:
            return 409, {
                "error": "이 화면의 자료를 서버가 갖고 있지 않습니다(서버를 다시 켰거나 오래된 화면) — "
                "이 창을 새로 고쳐 다시 여세요"
            }
        if body.get("ticker") != snap["ticker"]:
            return 400, {"error": "화면의 ETF 와 저장 요청의 ETF 가 다릅니다"}
        try:
            decision = ST.clean_decision(body)
        except ST.InputError as e:
            return 422, {"error": str(e)}
        for ai in decision[
            "ais"
        ]:  # 칸마다 질문 출처(서버가 가진 화면 자료로만 · PLAN V2 판정 §3-3)
            ai["asked"] = self.asked(
                ai.pop("answer_from"), snap, bool(ai["answer"]), ai.pop("answer_sig")
            )
        try:
            # 다시 열기 화면까지 만들어 보고 통과한 것만 씀(검증 F23)
            got = ST.save(self.root, self.now(), snap, decision, reopen=PS.render_saved)
        # 기록할 수 없는 수(NaN · inf) — 저장할 글을 만들기 전 거절 · 파일 0건(반박 검토 D1)
        # 화면 자료 쪽 문제라 같은 화면에서 다시 저장해도 같음 — 화면은 '새로 고쳐 다시 열기'로 안내(반박 검토 D5)
        except ST.Unrecordable as e:
            return 422, {
                "error": f"저장하지 않았습니다 — {e} · 아무것도 쓰지 않았습니다",
                "fix": "reload",
            }
        # 저장 폴더 확인에서 거절(연구 폴더 밖 · 실제 폴더가 아님 등) — 값 문제와 따로 안내(검증 F21)
        except CheckRequired as e:
            return 500, {"error": f"저장 폴더에 쓰지 못했습니다 — {e}"}
        except (
            OSError
        ) as e:  # 쓰기는 임시 파일 → 이름 붙이기라 실패하면 판단 기록은 생기지 않음
            return 500, {"error": f"저장 폴더에 쓰지 못했습니다 — {os_why(e)}"}
        return 200, {"review_id": got["review_id"], "sha256": got["sha256"]}


def os_why(e: OSError) -> str:
    """파일 쓰기 실패 사유(반박 검토 D6 — FileExistsError 를 '이미 저장됨'으로 읽히지 않게)."""
    name = Path(e.filename).name if e.filename else ""
    why = {
        FileExistsError: "같은 이름의 파일이 이미 있음",
        NotADirectoryError: "경로 중간에 폴더가 아닌 것이 있음",
        PermissionError: "쓰기 권한이 없음",
        IsADirectoryError: "파일 자리에 폴더가 있음",
    }.get(type(e), f"파일 시스템 오류({type(e).__name__})")
    return f"{why}({name})" if name else why


def make_handler(app: App, port: int) -> type[BaseHTTPRequestHandler]:
    hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
    origins = {f"http://{h}" for h in hosts}

    class Handler(BaseHTTPRequestHandler):
        server_version = "poc7-04"

        def log_message(
            self, fmt: str, *args: Any
        ) -> None:  # 요청 줄을 터미널에 남기지 않음(입력 노출 방지)
            return

        def _send(self, code: int, body: str, ctype: str) -> None:
            data = body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.end_headers()
            self.wfile.write(data)

        def _html(self, code: int, body: str) -> None:
            self._send(code, body, "text/html; charset=utf-8")

        def _json(self, code: int, obj: Mapping[str, Any]) -> None:
            self._send(
                code,
                json.dumps(obj, ensure_ascii=False),
                "application/json; charset=utf-8",
            )

        def _host_ok(self) -> bool:
            return self.headers.get("Host", "") in hosts

        def do_GET(self) -> None:  # noqa: N802
            if not self._host_ok():
                self._html(
                    403,
                    PS.render_error(
                        "막힘", "이 연구 화면은 맥북 내부 주소에서만 엽니다."
                    ),
                )
                return
            url = urlsplit(self.path)
            try:
                if url.path == "/":
                    q = parse_qs(url.query)
                    t = (q.get("ticker") or [None])[0]
                    try:
                        self._html(200, app.page(t))
                    except NotCandidate as e:
                        who = f"{e.name}({e.ticker})" if e.name else str(e.ticker)
                        self._html(
                            404,
                            PS.render_error(
                                "후보 목록 밖",
                                f"{who} 는 이번 주 후보 목록(「주간 ETF 점검」 조회 조건 · 같은 "
                                f"1개월 기간) 밖입니다 — 사유: {e.why}.",
                            ),
                        )
                    return
                if url.path == "/reviews":
                    self._html(200, app.list_page())
                    return
                if url.path.startswith("/reviews/"):
                    rid = url.path.removeprefix("/reviews/")
                    try:
                        doc = ST.load(app.root, rid)
                        # 화면 만들기 실패도 그 기록만(반박 검토 D7)
                        page = PS.render_saved(doc)
                    # 손상된 파일 하나 — 그 기록만 열지 못함
                    except Exception:
                        self._html(
                            404,
                            PS.render_error(
                                "저장 기록 없음",
                                "이 저장 기록을 찾거나 읽지 못했습니다.",
                            ),
                        )
                        return
                    self._html(200, page)
                    return
                self._html(
                    404, PS.render_error("없는 주소", "검토 화면으로 돌아가세요.")
                )
            except Exception as e:  # 화면 하나가 실패해도 서버는 계속(사유만 보임)
                self._html(
                    500,
                    PS.render_error(
                        "화면을 만들지 못함", f"{type(e).__name__}: {e}"[:300]
                    ),
                )

        def do_POST(self) -> None:  # noqa: N802
            if not self._host_ok():
                self._json(403, {"error": "맥북 내부 주소에서만 저장합니다"})
                return
            origin = self.headers.get("Origin")
            if origin is not None and origin not in origins:
                self._json(403, {"error": "다른 곳에서 온 저장 요청은 받지 않습니다"})
                return
            if urlsplit(self.path).path != "/api/reviews":
                self._json(404, {"error": "없는 주소"})
                return
            if not (self.headers.get("Content-Type") or "").startswith(
                "application/json"
            ):
                self._json(415, {"error": "JSON 요청만 받습니다"})
                return
            try:
                n = int(self.headers.get("Content-Length") or "0")
            except ValueError:
                n = -1
            if n < 0 or n > MAX_BODY:
                self._json(413, {"error": "요청이 너무 큽니다"})
                return
            try:
                body = json.loads(self.rfile.read(n).decode("utf-8"))
            # 글자 · JSON · 너무 큰 정수 · 깊은 중첩(반박 검토 D4)
            except (ValueError, RecursionError):
                self._json(400, {"error": "JSON 을 읽지 못했습니다"})
                return
            try:
                code, out = app.save(body)
            # 마지막 관문 — 응답 없이 끊지 않음 · 결과를 단정하지 않음
            except Exception as e:
                code, out = 500, {
                    "error": f"저장 중 예상하지 못한 오류({type(e).__name__}) — 저장됐는지 모릅니다 · "
                    "[지난 판단 열기]에서 확인하세요"
                }
            self._json(code, out)

    return Handler


def serve(app: App, port: int) -> HTTPServer:
    return HTTPServer(("127.0.0.1", port), make_handler(app, port))
