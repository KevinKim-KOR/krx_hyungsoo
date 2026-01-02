import requests
import json
import sys
import os

# Add backend path to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

BASE_URL = "http://localhost:8000/api/v1/ai"

def test_analyze_backtest():
    print("\nTesting /analyze/backtest...")
    data = {
        "metrics": {"cagr": 0.25, "sharpe": 1.5, "mdd": -10.5},
        "trades": [{"date": "2023-01-01", "symbol": "005930", "action": "BUY", "price": 60000}],
        "user_question": "이 전략 어때요?"
    }
    try:
        response = requests.post(f"{BASE_URL}/analyze/backtest", json=data)
        response.raise_for_status()
        result = response.json()
        print("Success!")
        print(f"Prompt length: {len(result['prompt'])}")
        return True
    except Exception as e:
        print(f"Failed: {e}")
        if hasattr(e, 'response') and e.response:
            print(e.response.text)
        return False

def test_analyze_portfolio():
    print("\nTesting /analyze/portfolio...")
    data = {
        "holdings": [{"code": "005930", "name": "Samsung Elec", "weight": 0.5}],
        "market_status": {"regime": "Bull", "trend": "Up"},
        "user_question": "리밸런싱 필요할까요?"
    }
    try:
        response = requests.post(f"{BASE_URL}/analyze/portfolio", json=data)
        response.raise_for_status()
        result = response.json()
        print("Success!")
        print(f"Prompt length: {len(result['prompt'])}")
        return True
    except Exception as e:
        print(f"Failed: {e}")
        return False

def test_analyze_ml_model():
    print("\nTesting /analyze/ml-model...")
    data = {
        "model_info": {
            "train_score": 0.95,
            "test_score": 0.85,
            "feature_importance": [{"feature": "ma_20", "importance": 0.3}]
        },
        "user_question": "과적합인가요?"
    }
    try:
        response = requests.post(f"{BASE_URL}/analyze/ml-model", json=data)
        response.raise_for_status()
        result = response.json()
        print("Success!")
        print(f"Prompt length: {len(result['prompt'])}")
        return True
    except Exception as e:
        print(f"Failed: {e}")
        return False

def test_analyze_lookback():
    print("\nTesting /analyze/lookback...")
    data = {
        "summary": {"total_rebalances": 5, "avg_return": 0.02},
        "results": [{"rebalance_date": "2023-01-01", "return": 0.03, "sharpe_ratio": 1.2}],
        "user_question": "안정적인가요?"
    }
    try:
        response = requests.post(f"{BASE_URL}/analyze/lookback", json=data)
        response.raise_for_status()
        result = response.json()
        print("Success!")
        print(f"Prompt length: {len(result['prompt'])}")
        return True
    except Exception as e:
        print(f"Failed: {e}")
        return False

if __name__ == "__main__":
    print("Starting AI API Verification...")
    results = [
        test_analyze_backtest(),
        test_analyze_portfolio(),
        test_analyze_ml_model(),
        test_analyze_lookback()
    ]
    
    if all(results):
        print("\nAll tests passed!")
        sys.exit(0)
    else:
        print("\nSome tests failed.")
        sys.exit(1)
