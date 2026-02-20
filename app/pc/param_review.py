
import json
import hashlib
from datetime import datetime
from datetime import timezone, timedelta
KST = timezone(timedelta(hours=9))
from pathlib import Path
import shutil

# Config
BASE_DIR = Path(__file__).parent.parent.parent
SEARCH_PATH = BASE_DIR / "reports" / "pc" / "param_search" / "latest" / "param_search_latest.json"
PARAMS_PATH = BASE_DIR / "state" / "strategy_params" / "latest" / "strategy_params_latest.json"
REVIEW_DIR = BASE_DIR / "reports" / "pc" / "param_review" / "latest"
SNAPSHOT_DIR = BASE_DIR / "reports" / "pc" / "param_review" / "snapshots"
OUTPUT_JSON = REVIEW_DIR / "param_review_latest.json"
OUTPUT_MD = REVIEW_DIR / "param_review_latest.md"

def load_json(path):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except: return None
    return None

def analyze_candidate(baseline_p, candidate_p, metrics):
    """
    Generate simple human-readable analysis based on comparisons.
    """
    reasons_good = []
    risks = []
    tags = []
    
    # Compare Volatility Weight
    base_vol_w = baseline_p.get("decision_params", {}).get("weight_volatility", 0.0)
    cand_vol_w = candidate_p.get("weights", {}).get("vol", 0.0) # Search result 'params' structure is flatter: {avg_window, top_k, weights: {mom, vol}} usually
    # Wait, param_search_latest.json 'params' structure might be tailored for search info, 
    # while strategy_params is the full strict schema.
    # Let's map candidate params to meaning.
    
    # Candidate Params (from P135): 
    # { "momentum_window": 20, "vol_window": 10, "top_k": 4, "weights": {"mom": 1.0, "vol": 0.0} } or similar
    
    # Logic:
    if cand_vol_w > base_vol_w:
        reasons_good.append("Higher volatility penalty (defensive).")
        tags.append("DEFENSIVE")
    elif cand_vol_w < base_vol_w:
        risks.append("Lower volatility penalty (aggressive).")
        tags.append("AGGRESSIVE")
        
    # Metrics
    cagr = metrics.get("avg_forward_return", 0) * 100
    hit_rate = metrics.get("hit_rate", 0) * 100
    
    if cagr > 20: 
        reasons_good.append("High projected return (>20%).")
        tags.append("HIGH_RETURN")
    if hit_rate > 60:
        reasons_good.append(f"Strong hit rate ({hit_rate:.0f}%).")
        tags.append("CONSISTENT")
    elif hit_rate < 40:
        risks.append(f"Low hit rate ({hit_rate:.0f}%), relies on big wins.")
        tags.append("VOLATILE_WINS")

    return {
        "why_good": " ".join(reasons_good) or "Balanced profile.",
        "risk_factor": " ".join(risks) or "Standard market risk.",
        "regime_hint": "DEFENSIVE" if "DEFENSIVE" in tags else "AGGRESSIVE" if "AGGRESSIVE" in tags else "NEUTRAL"
    }, tags

def generate_markdown(data):
    lines = []
    lines.append(f"# Param Review Report (As of {data['asof']})")
    lines.append("")
    
    base = data["baseline"]
    lines.append("## 1. Baseline (Current)")
    lines.append(f"- **Fingerprint**: `{base.get('fingerprint')}`")
    lines.append(f"- **Description**: Current strategy parameters.")
    lines.append("")
    
    lines.append("## 2. Top Candidates (Comparisons)")
    for cand in data["candidates"]:
        lines.append(f"### Rank {cand['rank']} (Score: {cand['score']})")
        lines.append(f"- **Tags**: {', '.join(cand['tags'])}")
        lines.append(f"- **Why Good**: {cand['analysis']['why_good']}")
        lines.append(f"- **Risk**: {cand['analysis']['risk_factor']}")
        
        m = cand["metrics"]
        lines.append(f"- **Metrics**: Return {m.get('avg_forward_return',0)*100:.1f}%, Hit {m.get('hit_rate',0)*100:.0f}%")
        lines.append("")
        
    lines.append("## 3. Suggestion Questions (Ask AI)")
    for q in data["questions"]:
        lines.append(f"- {q}")
        
    return "\n".join(lines)

def main():
    print("Generating Param Review Report...")
    
    # 1. Load Inputs
    search_res = load_json(SEARCH_PATH)
    current_params = load_json(PARAMS_PATH)
    
    if not search_res:
        print("[ERROR] No param search results found.")
        return
        
    # 2. Prepare Baseline
    baseline_info = {
        "params": current_params.get("params", {}) if current_params else {},
        "fingerprint": hashlib.sha256(json.dumps(current_params, sort_keys=True).encode()).hexdigest()[:16] if current_params else "UNKNOWN",
        "metrics": {} # We generally don't have simulated metrics for current unless we run backtest. Leave empty/unknown.
    }
    
    # 3. Analyze Candidates
    candidates = []
    raw_results = search_res.get("results", [])
    
    # Sort just in case parameters file isn't sorted
    raw_results.sort(key=lambda x: x.get("score_0_100", 0), reverse=True)
    
    top_candidates = raw_results[:5] # Top 5
    
    for res in top_candidates:
        cand_p = res.get("params", {})
        cand_m = res.get("metrics", {})
        
        analysis, tags = analyze_candidate(baseline_info["params"], cand_p, cand_m)
        
        candidates.append({
            "rank": res.get("rank"),
            "score": res.get("score_0_100"),
            "params": cand_p,
            "metrics": cand_m,
            "analysis": analysis,
            "tags": tags
        })
        
    # 4. Recommendation
    rec = {
        "candidate_rank": candidates[0]["rank"] if candidates else -1,
        "level": "SOFT",
        "reason": "Top scoring candidate based on P135 simulation."
    }
    
    # 5. Questions
    questions = [
        "How does the top candidate's volatility weight compare to the baseline?",
        "Is the hit rate of the top candidate sustainable?",
        "What market regime favors the aggressive candidate?",
        "Why did the baseline score lower (if applicable)?"
    ]
    
    # 6. Assembly
    final_output = {
        "schema": "PARAM_REVIEW_V1",
        "asof": datetime.now(KST).isoformat(),
        "baseline": baseline_info,
        "candidates": candidates,
        "recommendation": rec,
        "questions": questions
    }
    
    # 7. Write
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    
    # JSON
    json_str = json.dumps(final_output, indent=2, ensure_ascii=False)
    OUTPUT_JSON.write_text(json_str, encoding="utf-8")
    
    # Markdown
    md_str = generate_markdown(final_output)
    OUTPUT_MD.write_text(md_str, encoding="utf-8")
    
    # Snapshot
    ts = datetime.now(KST).strftime("%Y%m%d_%H%M%S")
    snap_path = SNAPSHOT_DIR / f"param_review_{ts}.json"
    snap_path.write_text(json_str, encoding="utf-8")
    
    print(f"Report Generated: {OUTPUT_JSON}")
    print(f"Markdown Report: {OUTPUT_MD}")

if __name__ == "__main__":
    main()
