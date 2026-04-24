"""POC 1단계 Streamlit UI (Step 2 에서 Next.js 로 교체 예정).

백엔드 API 의 status 값을 그대로 표시한다. UI 가 임의로 상태를 합치거나
가공하지 않는다 (KS-1 준수).

환경변수 POC_API_BASE 는 필수. 누락 시 즉시 명확한 에러로 기동 거부
(암묵적 localhost fallback 금지).

사용법:
    set POC_API_BASE=http://127.0.0.1:8000
    uvicorn app.api:app --host 127.0.0.1 --port 8000
    streamlit run ui_app.py
"""

from __future__ import annotations

import json
import os

import requests
import streamlit as st

HTTP_TIMEOUT_SEC = 5


class UIConfigError(Exception):
    pass


def _require_api_base() -> str:
    value = os.environ.get("POC_API_BASE")
    if not value:
        raise UIConfigError(
            "환경변수 POC_API_BASE 가 설정되어야 합니다. 예: http://127.0.0.1:8000"
        )
    return value


try:
    API_BASE = _require_api_base()
except UIConfigError as e:
    st.set_page_config(page_title="POC 1단계 승인 루프", layout="wide")
    st.error(str(e))
    st.stop()


st.set_page_config(page_title="POC 1단계 승인 루프", layout="wide")
st.title("POC 1단계 승인 루프")
st.caption(f"API: {API_BASE}")


def _get_json(path: str) -> tuple[int, object]:
    try:
        r = requests.get(f"{API_BASE}{path}", timeout=HTTP_TIMEOUT_SEC)
        return r.status_code, (r.json() if r.ok else r.text)
    except requests.RequestException as e:
        return 0, f"GET {path} 요청 실패: {e}"


def _post_json(path: str, json_body: dict | None = None) -> tuple[int, object]:
    try:
        r = requests.post(
            f"{API_BASE}{path}",
            json=json_body if json_body is not None else {},
            timeout=HTTP_TIMEOUT_SEC,
        )
        return r.status_code, (r.json() if r.ok else r.text)
    except requests.RequestException as e:
        return 0, f"POST {path} 요청 실패: {e}"


# --- 새 초안 생성 ---
st.subheader("1. 새 초안 생성")
st.caption(
    "draft payload 에 들어갈 입력값을 직접 입력하세요. "
    "필수 키(title / recommendations / note) 누락 시 FAILED run 으로 저장됩니다."
)
with st.form("generate_form"):
    title_in = st.text_input("title", value="", placeholder="예: ETF 모멘텀 추천 초안")
    note_in = st.text_area("note", value="", placeholder="사람이 읽고 판단할 본문")
    recs_in = st.text_area(
        "recommendations (JSON 배열)",
        value="",
        placeholder='[{"ticker": "069500", "score": 0.75, "action": "HOLD"}]',
        height=120,
    )
    submitted = st.form_submit_button("GenerateDraft")

if submitted:
    input_data: dict = {}
    if title_in.strip():
        input_data["title"] = title_in.strip()
    if note_in.strip():
        input_data["note"] = note_in.strip()
    if recs_in.strip():
        try:
            input_data["recommendations"] = json.loads(recs_in)
        except json.JSONDecodeError as e:
            st.error(
                f"recommendations JSON 파싱 실패: {e}. 입력 그대로 서버에 보내지 않습니다."
            )
            st.stop()

    status, body = _post_json("/runs/generate", {"input_data": input_data})
    if status == 200 and isinstance(body, dict):
        st.session_state["current_run_id"] = body["run_id"]
        if body["status"] == "PENDING_APPROVAL":
            st.success(f"생성됨: {body['run_id']} (status={body['status']})")
        else:
            st.warning(f"생성됨: {body['run_id']} (status={body['status']})")
    else:
        st.error(f"생성 실패 (HTTP {status}): {body}")

# --- run 목록 ---
st.subheader("2. run 목록")
status, body = _get_json("/runs")
if status == 200 and isinstance(body, list):
    runs = body
else:
    runs = []
    st.error(f"run 목록 조회 실패 (HTTP {status}): {body}")

if runs:
    run_ids = [x["run_id"] for x in runs]
    default_idx = 0
    if st.session_state.get("current_run_id") in run_ids:
        default_idx = run_ids.index(st.session_state["current_run_id"])
    selected_id = st.selectbox("run_id 선택", options=run_ids, index=default_idx)
    st.session_state["current_run_id"] = selected_id
else:
    st.info("저장된 run 이 없습니다. 상단에서 GenerateDraft 를 실행하세요.")
    selected_id = None

# --- 현재 run 상세 ---
if selected_id:
    status, body = _get_json(f"/runs/{selected_id}")
    if status != 200 or not isinstance(body, dict):
        st.warning(f"run_id={selected_id} 조회 실패 (HTTP {status}): {body}")
    else:
        run = body
        st.subheader(f"3. 현재 run: {run['run_id']}")
        c1, c2, c3 = st.columns(3)
        c1.metric("status", run["status"])
        c2.metric("asof", run["asof"])
        c3.metric("draft_payload", "있음" if run["draft_payload"] else "없음")

        st.markdown("**draft_payload**")
        st.json(run["draft_payload"] or {})

        if run["status"] == "PENDING_APPROVAL":
            btn_a, btn_r = st.columns(2)
            if btn_a.button("Approve", type="primary", key="btn_approve"):
                s2, b2 = _post_json(f"/runs/{selected_id}/approve")
                if s2 == 200 and isinstance(b2, dict):
                    st.success(f"Approve 처리됨. status={b2['status']}")
                    st.rerun()
                else:
                    st.error(f"Approve 실패 (HTTP {s2}): {b2}")
            if btn_r.button("Reject", key="btn_reject"):
                s2, b2 = _post_json(f"/runs/{selected_id}/reject")
                if s2 == 200 and isinstance(b2, dict):
                    st.info(f"Reject 처리됨. status={b2['status']}")
                    st.rerun()
                else:
                    st.error(f"Reject 실패 (HTTP {s2}): {b2}")
        else:
            st.caption(
                f"현재 상태 '{run['status']}' 에서는 Approve/Reject 불가. "
                "terminal 상태(REJECTED/FAILED/COMPLETED) 는 재시도 금지이며 "
                "새 시도는 GenerateDraft 로 새 run_id 를 생성해야 합니다."
            )
