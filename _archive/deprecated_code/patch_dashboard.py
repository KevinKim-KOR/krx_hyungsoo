import os

DASHBOARD_PATH = "dashboard/index.html"
NEW_CODE = r"""        function DiagnosisView({ data }) {
            const [expandedDay, setExpandedDay] = useState(null);

            if (!data || !data.years) {
                return (
                    <div className="flex flex-col items-center justify-center py-20 border border-dashed border-slate-700 rounded-lg opacity-70">
                        <div className="text-4xl mb-4">🩺</div>
                        <h3 className="text-xl font-bold text-slate-400">진단 리포트 준비 중 (Contract-1 Strict)</h3>
                        <p className="text-sm text-slate-500 mt-2">{data ? data.message : "Data Loading..."}</p>
                    </div>
                );
            }

            const COLORS = ['#8884d8', '#82ca9d', '#ffc658', '#ff8042', '#ef4444', '#f472b6'];

            return (
                <div className="space-y-12">
                    {['2024', '2025'].map(year => {
                        const yData = data.years[year];
                        if (!yData) return null;

                        const kpis = yData.kpis;
                        const breakdown = yData.reason_breakdown;

                        const chartData = Object.entries(breakdown || {})
                            .map(([name, value]) => ({ name, value }))
                            .sort((a, b) => b.value - a.value);

                        // Contract 1: Array is named 'daily'
                        const daily = yData.daily || [];

                        return (
                            <section key={year} className="bg-slate-800 border border-slate-700 rounded-2xl p-6 md:p-8">
                                <h2 className="text-2xl font-bold text-white mb-6 border-b border-slate-700 pb-4 flex items-center gap-2">
                                    <span className="w-1 h-6 bg-cyan-500 rounded"></span> {year} (V3 Strict)
                                </h2>

                                {/* KPI Cards Contract 3 Order */}
                                <div className="grid grid-cols-1 md:grid-cols-5 gap-4 mb-8">
                                    <KPICard label="Gate Open Days" value={kpis.gate_open_days} sub="Bullish/Neutral" />
                                    <KPICard label="Chop Blocked" value={kpis.chop_blocked_days} color={kpis.chop_blocked_days > 0 ? "text-yellow-400" : "text-slate-400"} />
                                    <KPICard label="Bear Blocked" value={kpis.bear_blocked_days} color={kpis.bear_blocked_days > 0 ? "text-red-400" : "text-slate-400"} />
                                    <KPICard label="Executed Days" value={kpis.executed_days} color={kpis.executed_days > 0 ? "text-emerald-400" : "text-slate-500"} />
                                    <KPICard label="Integrity Anomaly" value={kpis.integrity_anomaly_days} color={kpis.integrity_anomaly_days > 0 ? "text-red-600 font-bold animate-pulse" : "text-slate-700"} />
                                </div>

                                {/* Chart & Table */}
                                <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                                    <div className="lg:col-span-1">
                                         <h3 className="text-sm font-bold text-slate-400 uppercase tracking-widest mb-4">Reason Breakdown</h3>
                                         <div className="h-48 bg-slate-900/50 rounded-lg p-2 border border-slate-800">
                                            <ResponsiveContainer width="100%" height="100%">
                                                <BarChart data={chartData} layout="vertical" margin={{ left: 10 }}>
                                                    <XAxis type="number" hide />
                                                    <YAxis type="category" dataKey="name" width={110} tick={{ fontSize: 9, fill: '#64748b' }} />
                                                    <Tooltip contentStyle={{ backgroundColor: '#1e293b' }} />
                                                    <Bar dataKey="value" fill="#3b82f6" radius={[0,4,4,0]} barSize={15} />
                                                </BarChart>
                                            </ResponsiveContainer>
                                         </div>
                                    </div>
                                    
                                    <div className="lg:col-span-2">
                                        <h3 className="text-sm font-bold text-slate-400 uppercase tracking-widest mb-4">Daily Evidence Details</h3>
                                        <div className="overflow-x-auto bg-slate-900/50 rounded-lg border border-slate-800 max-h-[400px]">
                                            <table className="w-full text-xs text-left">
                                                <thead className="text-slate-500 bg-slate-900 sticky top-0 uppercase font-mono">
                                                    <tr>
                                                        <th className="p-3">DATE</th>
                                                        <th className="p-3">REGIME</th>
                                                        <th className="p-3">REASON</th>
                                                        <th className="p-3 text-center">EXEC</th>
                                                        <th className="p-3 text-right">TRADES</th>
                                                        <th className="p-3">ADX</th>
                                                        <th className="p-3">MA</th>
                                                        <th className="p-3">CONF</th>
                                                    </tr>
                                                </thead>
                                                <tbody className="divide-y divide-slate-800">
                                                    {daily.slice(0, 100).map((d, i) => { 
                                                        const isAnomaly = d.integrity && d.integrity.anomaly;
                                                        return (
                                                            <tr key={i} className={`hover:bg-slate-800/80 transition-colors ${isAnomaly ? "outline outline-1 outline-red-500 bg-red-900/20" : ""}`}>
                                                                <td className="p-3 font-mono text-slate-400">{d.date}</td>
                                                                <td className="p-3">{d.market.regime}</td>
                                                                <td className="p-3 text-xs">{d.decision.block_reason}</td>
                                                                <td className="p-3 text-center text-lg">{d.execution.executed ? "✅" : ""}</td>
                                                                <td className="p-3 text-right font-mono">{d.execution.trade_count > 0 ? d.execution.trade_count : "-"}</td>
                                                                <td className="p-3 font-mono text-slate-400">{d.evidence.adx.value.toFixed(1)}</td>
                                                                <td className="p-3 font-mono text-slate-500 text-[10px]">{d.evidence.ma.relation}</td>
                                                                <td className="p-3">{d.evidence.confidence.level}</td>
                                                            </tr>
                                                        )
                                                    })}
                                                </tbody>
                                            </table>
                                        </div>
                                    </div>
                                </div>
                            </section>
                        );
                    })}
                </div>
            )
        }
"""

with open(DASHBOARD_PATH, "r", encoding="utf-8") as f:
    content = f.read()

start_marker = "function DiagnosisView({ data })"
end_marker = "function GatekeeperView({ data })"

start_idx = content.find(start_marker)
end_idx = content.find(end_marker)

if start_idx == -1 or end_idx == -1:
    print(f"Error: Markers not found. Start: {start_idx}, End: {end_idx}")
    exit(1)

# Replace
new_content = content[:start_idx] + NEW_CODE + "\n\n" + content[end_idx:]

with open(DASHBOARD_PATH, "w", encoding="utf-8") as f:
    f.write(new_content)

print("Success: Patched DiagnosisView")
