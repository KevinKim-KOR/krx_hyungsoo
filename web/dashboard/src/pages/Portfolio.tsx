export default function Portfolio() {
  return (
    <div className="space-y-6">
      <h2 className="text-3xl font-bold">포트폴리오 최적화</h2>
      
      <div className="bg-card rounded-lg border p-6">
        <h3 className="text-xl font-bold mb-4">최적 비중 (Sharpe Ratio 최대화)</h3>
        <div className="space-y-2">
          <div className="flex justify-between items-center p-3 bg-secondary rounded">
            <span className="font-medium">069500 (KODEX 200)</span>
            <span className="text-lg font-bold">40%</span>
          </div>
          <div className="flex justify-between items-center p-3 bg-secondary rounded">
            <span className="font-medium">091160 (KODEX 반도체)</span>
            <span className="text-lg font-bold">20%</span>
          </div>
          <div className="flex justify-between items-center p-3 bg-secondary rounded">
            <span className="font-medium">133690 (KOSEF 국고채)</span>
            <span className="text-lg font-bold">40%</span>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-card rounded-lg border p-6">
          <h4 className="text-sm font-medium text-muted-foreground">기대 수익률</h4>
          <p className="text-2xl font-bold mt-2">29.9%</p>
        </div>
        <div className="bg-card rounded-lg border p-6">
          <h4 className="text-sm font-medium text-muted-foreground">변동성</h4>
          <p className="text-2xl font-bold mt-2">18.1%</p>
        </div>
        <div className="bg-card rounded-lg border p-6">
          <h4 className="text-sm font-medium text-muted-foreground">Sharpe Ratio</h4>
          <p className="text-2xl font-bold mt-2">1.49</p>
        </div>
      </div>

      <div className="bg-card rounded-lg border p-6">
        <h3 className="text-xl font-bold mb-4">이산 배분 (1천만원 기준)</h3>
        <div className="space-y-2">
          <div className="flex justify-between items-center p-3 bg-secondary rounded">
            <span>069500</span>
            <span className="font-bold">120주</span>
          </div>
          <div className="flex justify-between items-center p-3 bg-secondary rounded">
            <span>091160</span>
            <span className="font-bold">63주</span>
          </div>
          <div className="flex justify-between items-center p-3 bg-secondary rounded">
            <span>133690</span>
            <span className="font-bold">33주</span>
          </div>
          <div className="flex justify-between items-center p-3 bg-primary/10 rounded mt-4">
            <span className="font-medium">잔액</span>
            <span className="font-bold">₩21,441</span>
          </div>
        </div>
      </div>
    </div>
  )
}
