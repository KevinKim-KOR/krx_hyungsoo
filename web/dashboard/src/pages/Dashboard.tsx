export default function Dashboard() {
  return (
    <div className="space-y-6">
      <h2 className="text-3xl font-bold">대시보드</h2>
      
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* 요약 카드들 */}
        <div className="p-6 bg-card rounded-lg border">
          <h3 className="text-sm font-medium text-muted-foreground">총 포트폴리오 가치</h3>
          <p className="text-2xl font-bold mt-2">₩10,000,000</p>
          <p className="text-sm text-green-600 mt-1">+5.2%</p>
        </div>

        <div className="p-6 bg-card rounded-lg border">
          <h3 className="text-sm font-medium text-muted-foreground">Sharpe Ratio</h3>
          <p className="text-2xl font-bold mt-2">1.49</p>
          <p className="text-sm text-muted-foreground mt-1">최적화 결과</p>
        </div>

        <div className="p-6 bg-card rounded-lg border">
          <h3 className="text-sm font-medium text-muted-foreground">변동성</h3>
          <p className="text-2xl font-bold mt-2">18.1%</p>
          <p className="text-sm text-muted-foreground mt-1">연율화</p>
        </div>

        <div className="p-6 bg-card rounded-lg border">
          <h3 className="text-sm font-medium text-muted-foreground">기대 수익률</h3>
          <p className="text-2xl font-bold mt-2">29.9%</p>
          <p className="text-sm text-muted-foreground mt-1">연율화</p>
        </div>
      </div>

      {/* 최근 분석 결과 */}
      <div className="bg-card rounded-lg border p-6">
        <h3 className="text-xl font-bold mb-4">최근 분석 결과</h3>
        <div className="space-y-4">
          <div className="flex items-center justify-between p-4 bg-secondary rounded-lg">
            <div>
              <p className="font-medium">포트폴리오 최적화</p>
              <p className="text-sm text-muted-foreground">2025-11-17 23:25</p>
            </div>
            <span className="px-3 py-1 bg-green-100 text-green-800 rounded-full text-sm">완료</span>
          </div>

          <div className="flex items-center justify-between p-4 bg-secondary rounded-lg">
            <div>
              <p className="font-medium">룩백 분석</p>
              <p className="text-sm text-muted-foreground">2025-11-18 00:14</p>
            </div>
            <span className="px-3 py-1 bg-green-100 text-green-800 rounded-full text-sm">완료</span>
          </div>

          <div className="flex items-center justify-between p-4 bg-secondary rounded-lg">
            <div>
              <p className="font-medium">ML 모델 학습</p>
              <p className="text-sm text-muted-foreground">2025-11-17 23:17</p>
            </div>
            <span className="px-3 py-1 bg-green-100 text-green-800 rounded-full text-sm">완료</span>
          </div>
        </div>
      </div>
    </div>
  )
}
