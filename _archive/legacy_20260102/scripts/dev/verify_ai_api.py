# scripts/dev/verify_ai_api.py
import sys
import os
import asyncio
from datetime import date

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../backend')))

from backend.app.api.v1.ai import analyze_backtest, BacktestAnalysisRequest, analyze_portfolio, PortfolioAnalysisRequest

async def verify_backtest_analysis():
    print("1. Verifying Backtest Analysis...")
    request = BacktestAnalysisRequest(
        metrics={
            "total_return": 15.5,
            "mdd": -10.2,
            "sharpe": 1.2
        },
        trades=[
            {"date": "2024-01-01", "code": "005930", "action": "BUY", "price": 70000},
            {"date": "2024-02-01", "code": "005930", "action": "SELL", "price": 75000}
        ],
        user_question="이 전략 안전한가요?"
    )
    
    response = await analyze_backtest(request)
    print("   System Message:", response['system_message'])
    print("   Prompt Length:", len(response['prompt']))
    if "이 전략 안전한가요?" in response['prompt']:
        print("   ✅ User question included.")
    else:
        print("   ❌ User question missing.")

async def verify_portfolio_analysis():
    print("\n2. Verifying Portfolio Analysis...")
    request = PortfolioAnalysisRequest(
        holdings=[
            {"code": "005930", "name": "Samsung Elec", "weight": 0.5},
            {"code": "000660", "name": "SK Hynix", "weight": 0.3}
        ],
        market_status={
            "regime": "Bull",
            "trend": "Upward"
        }
    )
    
    response = await analyze_portfolio(request)
    print("   System Message:", response['system_message'])
    print("   Prompt Length:", len(response['prompt']))
    if "Samsung Elec" in response['prompt']:
        print("   ✅ Holdings included.")
    else:
        print("   ❌ Holdings missing.")

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(verify_backtest_analysis())
    loop.run_until_complete(verify_portfolio_analysis())
    loop.close()
