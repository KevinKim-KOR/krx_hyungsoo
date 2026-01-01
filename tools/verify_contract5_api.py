import requests
import json
import sys

BASE_URL = "http://localhost:8000"

def check_endpoint(name, url):
    print(f"Checking {name} ({url})...")
    try:
        res = requests.get(url)
        if res.status_code != 200:
            print(f"FAIL: Status {res.status_code}")
            return False
        
        data = res.json()
        print(f"SUCCESS: Got JSON with keys: {list(data.keys())}")
        
        # Contract 5 Checks
        if "human" in name.lower():
            if "headline" not in data or "integrity_summary" not in data:
                print("FAIL: Missing Contract 5 Human Report fields (headline, integrity_summary)")
                return False
            print(f"Headline: {data['headline'].get('title_ko')}")
            
        if "ai" in name.lower():
            if "kpi_vector" not in data or "constraints_hint" not in data:
                print("FAIL: Missing Contract 5 AI Report fields (kpi_vector, constraints_hint)")
                return False
            print(f"KPI Vector: {data.get('kpi_vector')}")
            
        return True
    except Exception as e:
        print(f"FAIL: Exception {e}")
        return False

def main():
    h_ok = check_endpoint("Human Report", f"{BASE_URL}/api/report/human")
    a_ok = check_endpoint("AI Report", f"{BASE_URL}/api/report/ai")
    
    if h_ok and a_ok:
        print("\nALL API CHECKS PASSED")
    else:
        print("\nAPI CHECKS FAILED")
        sys.exit(1)

if __name__ == "__main__":
    main()
