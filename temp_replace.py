import codecs

path = 'pc_cockpit/cockpit.py'
content = codecs.open(path, 'r', 'utf-8').read()

# 1. 1-Click Sync
content = content.replace(
    'st.error(f"LIVE 승인 없음(또는 REVOKED) → Approve LIVE 후 Sync 하세요. ({msg})")\n            st.stop()',
    'st.error(f"LIVE 승인 없음(또는 REVOKED) → Approve LIVE 후 Sync 하세요. ({msg})")\n            st.session_state["last_block_reason"] = f"1-Click Sync 차단: {msg}"\n            return'
)
content = content.replace(
    'st.warning("OCI 토큰이 필요합니다. 위 입력란에 토큰을 넣고 다시 시도하세요.")\n            st.stop()',
    'st.warning("OCI 토큰이 필요합니다. 위 입력란에 토큰을 넣고 다시 시도하세요.")\n            st.session_state["last_block_reason"] = "1-Click Sync 차단: Token 없음"\n            return'
)

# 2. Workflow Header
wf_header = 'st.header("🧭 운영 워크플로우 허브 (P170-UI)")'
wf_header_new = wf_header + '\n    if "last_block_reason" in st.session_state and st.session_state["last_block_reason"]:\n        st.warning(f"⚠️ 최근 차단 사유: {st.session_state[\'last_block_reason\']}")'
content = content.replace(wf_header, wf_header_new)

# 3. Daily Ops Backend
content = content.replace(
    'st.error(f"🛑 Backend Connection Failed: {error_msg}")\n        st.stop() # Stop rendering if backend is dead',
    'st.error(f"🛑 Backend Connection Failed: {error_msg}")\n        st.session_state["last_block_reason"] = f"Backend 죽음: {error_msg}"\n        return'
)

# 4. Daily Ops PULL
pull_old = '''        if pull_clicked:
            if not st.session_state.get("ops_token", ""):
                st.warning("워크플로우(P170) 탭에서 운영 토큰을 먼저 입력해 주세요.")
                st.stop()
            with st.spinner(f"Pulling..."):'''
pull_new = '''        if pull_clicked:
            do_pull = True
            if not st.session_state.get("ops_token", ""):
                st.warning("워크플로우(P170) 탭에서 운영 토큰을 먼저 입력해 주세요.")
                st.session_state["last_block_reason"] = "PULL 차단: Token 없음"
                do_pull = False
            
            if do_pull:
                with st.spinner(f"Pulling..."):'''
content = content.replace(pull_old, pull_new)

# 5. Auto Ops Cycle
content = content.replace(
    'st.error(f"워크플로우에서 승인 → 1-Click Sync 완료 후 실행 ({msg})")\n                 st.stop()',
    'st.error(f"워크플로우에서 승인 → 1-Click Sync 완료 후 실행 ({msg})")\n                 st.session_state["last_block_reason"] = f"Auto Ops 차단: {msg}"\n                 return'
)
content = content.replace(
    'st.warning("워크플로우(P170) 탭에서 운영 토큰을 먼저 입력해 주세요.")\n                 st.stop()',
    'st.warning("워크플로우(P170) 탭에서 운영 토큰을 먼저 입력해 주세요.")\n                 st.session_state["last_block_reason"] = "Auto Ops 차단: Token 없음"\n                 return'
)
content = content.replace(
    'st.error(f"Step 1 실패: 번들 생성에 실패했습니다.\\n{result.stderr}")\n                     st.stop()',
    'st.error(f"Step 1 실패: 번들 생성에 실패했습니다.\\n{result.stderr}")\n                     st.session_state["last_block_reason"] = "Auto Ops 차단: Step 1 Bundle 생성 실패"\n                     return'
)
content = content.replace(
    'st.error("Step 2 실패: 최신 Export 파일에서 confirm_token을 찾을 수 없습니다. Order Plan Export를 먼저 생성해주세요.")\n                     st.stop()',
    'st.error("Step 2 실패: 최신 Export 파일에서 confirm_token을 찾을 수 없습니다. Order Plan Export를 먼저 생성해주세요.")\n                     st.session_state["last_block_reason"] = "Auto Ops 차단: Step 2 Token 추출 실패"\n                     return'
)
content = content.replace(
    'st.error(f"Step 2 실패: OCI 동기화에 실패했습니다.\\n{sync_resp.text}")\n                     st.stop()',
    'st.error(f"Step 2 실패: OCI 동기화에 실패했습니다.\\n{sync_resp.text}")\n                     st.session_state["last_block_reason"] = f"Auto Ops 차단: Step 2 Push 실패"\n                     return'
)

codecs.open(path, 'w', 'utf-8').write(content)
print("Replace complete.")
