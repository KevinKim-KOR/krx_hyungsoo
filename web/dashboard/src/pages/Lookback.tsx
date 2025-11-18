export default function Lookback() {
  return (
    <div className="space-y-6">
      <h2 className="text-3xl font-bold">룩백 분석</h2>
      <p className="text-muted-foreground">워크포워드 분석 결과 (2022-2024)</p>
      
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-card rounded-lg border p-6">
          <h3 className="text-sm font-medium text-muted-foreground">리밸런싱 횟수</h3>
          <p className="text-2xl font-bold mt-2">4회</p>
        </div>
        <div className="bg-card rounded-lg border p-6">
          <h3 className="text-sm font-medium text-muted-foreground">평균 수익률</h3>
          <p className="text-2xl font-bold mt-2">3.71%</p>
        </div>
        <div className="bg-card rounded-lg border p-6">
          <h3 className="text-sm font-medium text-muted-foreground">평균 Sharpe</h3>
          <p className="text-2xl font-bold mt-2">2.47</p>
        </div>
        <div className="bg-card rounded-lg border p-6">
          <h3 className="text-sm font-medium text-muted-foreground">승률</h3>
          <p className="text-2xl font-bold mt-2">75%</p>
        </div>
      </div>

      <div className="bg-card rounded-lg border p-6">
        <h3 className="text-xl font-bold mb-4">리밸런싱 결과</h3>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b">
                <th className="text-left p-3">날짜</th>
                <th className="text-left p-3">최적 비중</th>
                <th className="text-right p-3">수익률</th>
                <th className="text-right p-3">Sharpe</th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-b">
                <td className="p-3">2023-09-25</td>
                <td className="p-3">133690: 100%</td>
                <td className="p-3 text-right text-red-600">-0.46%</td>
                <td className="p-3 text-right">-0.23</td>
              </tr>
              <tr className="border-b">
                <td className="p-3">2024-01-29</td>
                <td className="p-3">091160: 20%, 133690: 80%</td>
                <td className="p-3 text-right text-green-600">2.96%</td>
                <td className="p-3 text-right">1.67</td>
              </tr>
              <tr className="border-b">
                <td className="p-3">2024-06-03</td>
                <td className="p-3">091160: 8%, 133690: 92%</td>
                <td className="p-3 text-right text-green-600">10.09%</td>
                <td className="p-3 text-right">6.31</td>
              </tr>
              <tr>
                <td className="p-3">2024-10-07</td>
                <td className="p-3">133690: 100%</td>
                <td className="p-3 text-right text-green-600">2.23%</td>
                <td className="p-3 text-right">2.15</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
