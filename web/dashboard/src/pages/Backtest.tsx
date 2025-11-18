export default function Backtest() {
  return (
    <div className="space-y-6">
      <h2 className="text-3xl font-bold">백테스트 비교</h2>
      <p className="text-muted-foreground">MAPS vs ML 모델 성능 비교</p>
      
      <div className="bg-card rounded-lg border p-6">
        <h3 className="text-xl font-bold mb-4">백테스트 결과 (2022-2024)</h3>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b">
                <th className="text-left p-3">전략</th>
                <th className="text-right p-3">CAGR</th>
                <th className="text-right p-3">Sharpe</th>
                <th className="text-right p-3">MDD</th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-b">
                <td className="p-3 font-medium">MAPS (하이브리드)</td>
                <td className="p-3 text-right">27.05%</td>
                <td className="p-3 text-right">1.51</td>
                <td className="p-3 text-right">-19.92%</td>
              </tr>
              <tr>
                <td className="p-3 font-medium">ML 모델 (XGBoost)</td>
                <td className="p-3 text-right">-</td>
                <td className="p-3 text-right">-</td>
                <td className="p-3 text-right">-</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
