export default function MLModel() {
  return (
    <div className="space-y-6">
      <h2 className="text-3xl font-bold">ML 모델</h2>
      <p className="text-muted-foreground">XGBoost 기반 ETF 랭킹 예측 모델</p>
      
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-card rounded-lg border p-6">
          <h3 className="text-lg font-bold mb-2">학습 결과</h3>
          <div className="space-y-2">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Train R²</span>
              <span className="font-bold">0.9986</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Test R²</span>
              <span className="font-bold">-0.3973</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">특징 수</span>
              <span className="font-bold">46개</span>
            </div>
          </div>
        </div>

        <div className="bg-card rounded-lg border p-6">
          <h3 className="text-lg font-bold mb-2">Top 5 중요 특징</h3>
          <div className="space-y-2">
            <div className="flex justify-between">
              <span>volatility_60</span>
              <span className="font-bold">0.0629</span>
            </div>
            <div className="flex justify-between">
              <span>ma_100</span>
              <span className="font-bold">0.0609</span>
            </div>
            <div className="flex justify-between">
              <span>roc_60</span>
              <span className="font-bold">0.0592</span>
            </div>
            <div className="flex justify-between">
              <span>macd_signal</span>
              <span className="font-bold">0.0536</span>
            </div>
            <div className="flex justify-between">
              <span>williams_r</span>
              <span className="font-bold">0.0513</span>
            </div>
          </div>
        </div>
      </div>

      <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
        <p className="text-sm text-yellow-800">
          ⚠️ Test R²가 음수인 것은 과적합 신호입니다. 실제 운영 시 더 많은 데이터와 하이퍼파라미터 튜닝이 필요합니다.
        </p>
      </div>
    </div>
  )
}
