"""비활성 보존 파일 — shadowed 2차 정의 아카이브.

이 파일은 import되지 않습니다.
S5 라우터 분해 시 발견된 중복 라우트의 2차 정의(나중 등록, 매칭 안 됨)를 보존합니다.
향후 v2로 승격이 필요하면 이 파일에서 참조하세요.

각 함수의 원본 위치:
- get_reco_latest_v2: 원본 main.py L3774
- regenerate_reco_v2: 원본 main.py L3820
- upsert_portfolio_api_v2: 원본 main.py L4262
- regenerate_order_plan_api_v2: 원본 main.py L4321
- get_order_plan_latest_api_v2: 원본 main.py L4351
- prepare_execution_api: 원본 main.py L4577
- regenerate_execution_ticket_api: 원본 main.py L4766

현재 live 핸들러는 각 라우터의 v1(1차 정의)입니다.
직접 호출하는 소비자는 없습니다 (HTTP-only).
"""

# 이 파일은 의도적으로 import하지 않습니다.
# 코드 참조 용도로만 보존합니다.

raise ImportError("이 파일은 아카이브입니다. import하지 마세요.")

# ---------------------------------------------------------------------------
# 1. GET /api/reco/latest — shadowed (v1: portfolio.py get_reco_latest_v1)
# ---------------------------------------------------------------------------
#
# def get_reco_latest_v2():
#     """Reco Report Latest (D-P.48) — 확장판: snapshots 포함"""
#     from app.generate_reco_report import load_latest_reco, get_reco_status, list_snapshots
#     report = load_latest_reco()
#     status = get_reco_status()
#     snapshots = list_snapshots()
#     return {
#         "schema": "RECO_REPORT_V1",
#         "asof": ...,
#         "status": "ready" if report else "no_reco_yet",
#         "report": report,
#         "summary": status,
#         "snapshots": snapshots[:5],
#         "error": None if report else {"code": "NO_RECO_YET", ...}
#     }

# ---------------------------------------------------------------------------
# 2. POST /api/reco/regenerate — shadowed (v1: portfolio.py regenerate_reco_v1)
# ---------------------------------------------------------------------------
#
# def regenerate_reco_v2(confirm, force):
#     """Reco Report Regenerate (D-P.48) — confirm 가드 + success 체크"""
#     if not confirm: return BLOCKED
#     result = generate_reco_report(force=force)
#     if result["success"]: return OK with report_id, decision, saved_to
#     else: return FAILED

# ---------------------------------------------------------------------------
# 3. POST /api/portfolio/upsert — shadowed (v1: portfolio.py upsert_portfolio_api_v1)
# ---------------------------------------------------------------------------
#
# async def upsert_portfolio_api_v2(payload: PortfolioUpsertRequest, confirm):
#     """Pydantic 기반 + 외부 모듈(upsert_portfolio) 사용"""
#     from app.generate_portfolio_snapshot import upsert_portfolio
#     holdings_dicts = [h.dict() for h in payload.holdings]
#     result = upsert_portfolio(cash=payload.cash, holdings=holdings_dicts, updated_by="ui")

# ---------------------------------------------------------------------------
# 4. POST /api/order_plan/regenerate — shadowed (v1: portfolio.py regenerate_order_plan_v1)
# ---------------------------------------------------------------------------
#
# async def regenerate_order_plan_api_v2(confirm):
#     """confirm 가드 + generate_order_plan() (force 없음)"""

# ---------------------------------------------------------------------------
# 5. GET /api/order_plan/latest — shadowed (v1: portfolio.py get_order_plan_latest_v1)
# ---------------------------------------------------------------------------
#
# async def get_order_plan_latest_api_v2():
#     """외부 모듈(get_order_plan_latest) 사용, rows/row_count 포맷"""

# ---------------------------------------------------------------------------
# 6. POST /api/execution_prep/prepare — shadowed (v1: manual_execution.py prepare_execution)
# ---------------------------------------------------------------------------
#
# async def prepare_execution_api(payload, confirm):
#     """confirm만, force 없음. PREP_LATEST를 모듈에서 import"""

# ---------------------------------------------------------------------------
# 7. POST /api/manual_execution_ticket/regenerate — shadowed
#    (v1: manual_execution.py regenerate_manual_execution_ticket)
# ---------------------------------------------------------------------------
#
# async def regenerate_execution_ticket_api(confirm):
#     """단순 generate_ticket() + ImportError 시 subprocess fallback"""
