// API 응답 타입 정의

export interface PortfolioOptimization {
  timestamp: string;
  method: string;
  expected_return: number;
  volatility: number;
  sharpe_ratio: number;
  weights: Record<string, number>;
  discrete_allocation?: {
    allocation: Record<string, number>;
    leftover: number;
    total_value: number;
  };
}

export interface BacktestResult {
  strategy: string;
  start_date: string;
  end_date: string;
  total_return: number;
  cagr: number;
  sharpe_ratio: number;
  max_drawdown: number;
  calmar_ratio?: number;
  volatility?: number;
  win_rate?: number;
  trade_win_rate?: number;
  total_trades?: number;
  sell_trades?: number;
  total_realized_pnl?: number;
  avg_win?: number;
  avg_loss?: number;
  total_costs?: number;
  cost_ratio?: number;
  calendar_days?: number;
  trading_days?: number;
  years?: number;
}

export interface MLModelInfo {
  model_type: string;
  timestamp: string;
  train_score: number;
  test_score: number;
  n_features: number;
  feature_importance: Array<{
    feature: string;
    importance: number;
  }>;
}

export interface LookbackResult {
  rebalance_date: string;
  holding_period_days: number;
  return: number;
  volatility: number;
  sharpe_ratio: number;
  weights: Record<string, number>;
}

export interface LookbackAnalysis {
  timestamp: string;
  method: string;
  results: LookbackResult[];
  summary: {
    total_rebalances: number;
    avg_return: number;
    avg_sharpe: number;
    win_rate: number;
  };
}

export interface DashboardSummary {
  portfolio_value: number;
  portfolio_change: number;
  sharpe_ratio: number;
  volatility: number;
  expected_return: number;
  last_updated: string;
}

export interface RecentAnalysis {
  type: 'portfolio' | 'backtest' | 'ml' | 'lookback';
  title: string;
  timestamp: string;
  summary: string;
}
