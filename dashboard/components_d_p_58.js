function PortfolioView({ data, onRefresh }) {
    const [cash, setCash] = useState(0);
    const [holdings, setHoldings] = useState([]);
    const [isSaving, setIsSaving] = useState(false);
    const [showForm, setShowForm] = useState(false);

    // Init from data
    useEffect(() => {
        if (data && data.rows && data.rows[0]) {
            const row = data.rows[0];
            setCash(row.cash || 0);
            setHoldings(row.holdings || []);
        }
    }, [data]);

    const handleAddRow = () => {
        setHoldings([...holdings, { ticker: "", name: "", quantity: 0, avg_price: 0 }]);
    };

    const handleRemoveRow = (idx) => {
        const newHoldings = [...holdings];
        newHoldings.splice(idx, 1);
        setHoldings(newHoldings);
    };

    const handleChange = (idx, field, val) => {
        const newHoldings = [...holdings];
        newHoldings[idx][field] = val;
        setHoldings(newHoldings);
    };

    const handleSave = async () => {
        if (!confirm("포트폴리오를 저장하시겠습니까?")) return;
        setIsSaving(true);
        try {
            const payload = {
                cash: Number(cash),
                holdings: holdings.map(h => ({
                    ticker: h.ticker,
                    name: h.name,
                    quantity: Number(h.quantity),
                    avg_price: Number(h.avg_price)
                }))
            };

            const res = await fetch(`${API_BASE}/api/portfolio/upsert?confirm=true`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (res.ok) {
                alert("저장되었습니다.");
                onRefresh();
                setShowForm(false);
            } else {
                const err = await res.json();
                alert(`저장 실패: ${err.detail?.reason || err.detail?.message || "Unknown"}`);
            }
        } catch (e) {
            alert(`오류 발생: ${e.message}`);
        } finally {
            setIsSaving(false);
        }
    };

    // Formatters
    const fmt = (n) => new Intl.NumberFormat('ko-KR').format(n);

    if (!showForm && data && data.rows && data.rows[0]) {
        const row = data.rows[0];
        return (
            <div className="bg-slate-800 border border-slate-700 rounded-2xl p-6">
                <div className="flex justify-between items-center mb-6">
                    <h2 className="text-xl font-bold text-white flex items-center gap-2">
                        <span className="w-1 h-5 bg-blue-500 rounded"></span> Portfolio
                        <span className="text-xs font-mono text-slate-500">{row.asof?.slice(0, 16)}</span>
                    </h2>
                    <button onClick={() => setShowForm(true)} className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg font-bold transition">
                        ✏️ Edit
                    </button>
                </div>

                <div className="grid grid-cols-3 gap-4 mb-6">
                    <div className="bg-slate-900/50 p-4 rounded-xl border border-slate-700/50">
                        <div className="text-sm text-slate-500 mb-1">Total Value</div>
                        <div className="text-2xl font-bold text-white font-mono">{fmt(row.total_value)} 원</div>
                    </div>
                    <div className="bg-slate-900/50 p-4 rounded-xl border border-slate-700/50">
                        <div className="text-sm text-slate-500 mb-1">Cash</div>
                        <div className="text-2xl font-bold text-emerald-400 font-mono">{fmt(row.cash)} 원</div>
                        <div className="text-xs text-emerald-500/50 mt-1">{row.cash_ratio_pct}%</div>
                    </div>
                    <div className="bg-slate-900/50 p-4 rounded-xl border border-slate-700/50">
                        <div className="text-sm text-slate-500 mb-1">Holdings</div>
                        <div className="text-2xl font-bold text-blue-400 font-mono">{row.holdings?.length || 0} 종목</div>
                    </div>
                </div>

                <table className="w-full text-sm text-left text-slate-400">
                    <thead className="text-slate-500 uppercase bg-slate-900/50">
                        <tr>
                            <th className="px-4 py-3 rounded-l-lg">Ticker</th>
                            <th className="px-4 py-3">Quantitiy</th>
                            <th className="px-4 py-3">Avg Price</th>
                            <th className="px-4 py-3 text-right rounded-r-lg">Market Value</th>
                        </tr>
                    </thead>
                    <tbody>
                        {row.holdings.map((h, i) => (
                            <tr key={i} className="border-b border-slate-700 hover:bg-slate-700/30">
                                <td className="px-4 py-3">
                                    <div className="font-bold text-white">{h.name}</div>
                                    <div className="font-mono text-xs text-slate-500">{h.ticker}</div>
                                </td>
                                <td className="px-4 py-3 font-mono">{fmt(h.quantity)}</td>
                                <td className="px-4 py-3 font-mono">{fmt(h.avg_price)}</td>
                                <td className="px-4 py-3 font-mono text-right text-white">{fmt(h.market_value)}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        );
    }

    return (
        <div className="bg-slate-800 border border-slate-700 rounded-2xl p-6">
            <h2 className="text-xl font-bold text-white mb-6 flex items-center gap-2">
                <span className="w-1 h-5 bg-blue-500 rounded"></span> Edit Portfolio
            </h2>

            <div className="mb-6">
                <label className="block text-sm font-medium text-slate-400 mb-1">Cash (KRW)</label>
                <input
                    type="number"
                    value={cash}
                    onChange={(e) => setCash(Number(e.target.value))}
                    className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-2 text-white font-mono"
                />
            </div>

            <div className="space-y-2 mb-6">
                {holdings.map((h, i) => (
                    <div key={i} className="flex gap-2 items-center bg-slate-900/50 p-2 rounded-lg border border-slate-700/50">
                        <input placeholder="Ticker" value={h.ticker} onChange={e => handleChange(i, 'ticker', e.target.value)} className="w-24 bg-slate-800 border-none rounded px-2 py-1 text-white font-mono text-sm" />
                        <input placeholder="Name" value={h.name} onChange={e => handleChange(i, 'name', e.target.value)} className="flex-1 bg-slate-800 border-none rounded px-2 py-1 text-white text-sm" />
                        <input placeholder="Qty" type="number" value={h.quantity} onChange={e => handleChange(i, 'quantity', Number(e.target.value))} className="w-20 bg-slate-800 border-none rounded px-2 py-1 text-white font-mono text-sm text-right" />
                        <input placeholder="AvgPrice" type="number" value={h.avg_price} onChange={e => handleChange(i, 'avg_price', Number(e.target.value))} className="w-24 bg-slate-800 border-none rounded px-2 py-1 text-white font-mono text-sm text-right" />
                        <button onClick={() => handleRemoveRow(i)} className="text-red-500 hover:text-red-400 px-2">✕</button>
                    </div>
                ))}
                <button onClick={handleAddRow} className="w-full py-2 border border-dashed border-slate-600 rounded-lg text-slate-400 hover:text-white hover:bg-slate-700/50 text-sm transition">
                    + Add Holding
                </button>
            </div>

            <div className="flex gap-4">
                <button onClick={handleSave} disabled={isSaving} className="flex-1 py-3 bg-blue-600 hover:bg-blue-500 text-white font-bold rounded-lg transition">
                    {isSaving ? "Saving..." : "Save Portfolio"}
                </button>
                <button onClick={() => setShowForm(false)} className="px-6 py-3 bg-slate-700 hover:bg-slate-600 text-white font-bold rounded-lg transition">
                    Cancel
                </button>
            </div>
        </div>
    );
}

function OrderPlanView({ data, onRegenerate }) {
    const [isGenerating, setIsGenerating] = useState(false);

    const handleGen = async () => {
        if (!confirm("주문안을 재생성하시겠습니까?")) return;
        setIsGenerating(true);
        try {
            const res = await fetch(`${API_BASE}/api/order_plan/regenerate?confirm=true`, { method: 'POST' });
            if (res.ok) {
                onRegenerate();
            } else {
                alert("재생성 실패");
            }
        } catch (e) {
            alert("Error: " + e.message);
        } finally {
            setIsGenerating(false);
        }
    };

    const fmt = (n) => new Intl.NumberFormat('ko-KR').format(n);

    if (!data || !data.rows || !data.rows[0]) {
        return (
            <div className="bg-slate-800 border border-slate-700 rounded-2xl p-8 text-center">
                <div className="text-4xl mb-4">🧾</div>
                <h3 className="text-xl font-bold text-white mb-2">No Order Plan</h3>
                <p className="text-slate-500 mb-6">아직 생성된 주문안이 없습니다.</p>
                <button onClick={handleGen} disabled={isGenerating} className="px-6 py-2 bg-indigo-600 hover:bg-indigo-500 text-white font-bold rounded-lg">
                    {isGenerating ? "Generating..." : "Generate Plan"}
                </button>
            </div>
        );
    }

    const plan = data.rows[0];
    const decisionColor = plan.decision === 'GENERATED' ? 'text-emerald-400' : 'text-amber-400';

    return (
        <div className="space-y-6">
            <div className="bg-slate-800 border border-slate-700 rounded-2xl p-6">
                <div className="flex justify-between items-center mb-6">
                    <h2 className="text-xl font-bold text-white flex items-center gap-2">
                        <span className="w-1 h-5 bg-indigo-500 rounded"></span> Order Plan
                        <span className={`px-2 py-0.5 rounded text-xs border bg-slate-900 ${decisionColor} border-current`}>{plan.decision}</span>
                    </h2>
                    <button onClick={handleGen} disabled={isGenerating} className="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg text-sm font-bold">
                        {isGenerating ? "..." : "🔄 Regenerate"}
                    </button>
                </div>

                {plan.reason && <div className="bg-slate-900/50 p-3 rounded-lg text-slate-400 text-sm mb-6 border border-slate-700/50">Reason: {plan.reason}</div>}

                {plan.summary && (
                    <div className="grid grid-cols-4 gap-4 mb-6">
                        <div className="bg-emerald-900/20 p-3 rounded-lg border border-emerald-900/30 text-center">
                            <div className="text-xs text-emerald-500 mb-1">Buy Amount</div>
                            <div className="text-lg font-bold text-emerald-400">{fmt(plan.summary.total_buy_amount)}</div>
                        </div>
                        <div className="bg-blue-900/20 p-3 rounded-lg border border-blue-900/30 text-center">
                            <div className="text-xs text-blue-500 mb-1">Sell Amount</div>
                            <div className="text-lg font-bold text-blue-400">{fmt(plan.summary.total_sell_amount)}</div>
                        </div>
                        <div className="bg-slate-700/30 p-3 rounded-lg border border-slate-600/30 text-center">
                            <div className="text-xs text-slate-400 mb-1">Net Cash Change</div>
                            <div className="text-lg font-bold text-white">{fmt(plan.summary.net_cash_change)}</div>
                        </div>
                        <div className="bg-slate-700/30 p-3 rounded-lg border border-slate-600/30 text-center">
                            <div className="text-xs text-slate-400 mb-1">Est. Cash Ratio</div>
                            <div className="text-lg font-bold text-white">{plan.summary.estimated_cash_ratio_pct}%</div>
                        </div>
                    </div>
                )}

                {plan.orders && plan.orders.length > 0 ? (
                    <table className="w-full text-sm text-left text-slate-400">
                        <thead className="text-slate-500 uppercase bg-slate-900/50">
                            <tr>
                                <th className="px-4 py-3 rounded-l-lg">Action</th>
                                <th className="px-4 py-3">Ticker</th>
                                <th className="px-4 py-3 text-right">Qty</th>
                                <th className="px-4 py-3 text-right rounded-r-lg">Amount</th>
                            </tr>
                        </thead>
                        <tbody>
                            {plan.orders.map((o, i) => (
                                <tr key={i} className="border-b border-slate-700 hover:bg-slate-700/30">
                                    <td className="px-4 py-3">
                                        <span className={`px-2 py-0.5 rounded text-xs font-bold ${o.action === 'BUY' ? 'bg-red-500/20 text-red-400' : 'bg-blue-500/20 text-blue-400'}`}>
                                            {o.action}
                                        </span>
                                    </td>
                                    <td className="px-4 py-3">
                                        <div className="text-white font-bold">{o.name}</div>
                                        <div className="text-xs font-mono">{o.ticker}</div>
                                    </td>
                                    <td className="px-4 py-3 text-right font-mono">{fmt(o.estimated_quantity)}</td>
                                    <td className="px-4 py-3 text-right font-mono text-white">{fmt(o.order_amount)}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                ) : (
                    <div className="text-center py-8 text-slate-500">No Orders Generated</div>
                )}
            </div>
        </div>
    );
}
