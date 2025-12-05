// API 클라이언트

import type {
  PortfolioOptimization,
  BacktestResult,
  MLModelInfo,
  LookbackAnalysis,
  DashboardSummary,
  RecentAnalysis,
} from '../types';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;
  }

  private async fetch<T>(endpoint: string, options?: RequestInit): Promise<T> {
    const response = await fetch(`${this.baseUrl}${endpoint}`, options);
    if (!response.ok) {
      const error = await response.text();
      throw new Error(error || `API Error: ${response.statusText}`);
    }
    return response.json();
  }

  private async post<T>(endpoint: string, data?: any): Promise<T> {
    return this.fetch<T>(endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: data ? JSON.stringify(data) : undefined,
    });
  }

  private async put<T>(endpoint: string, data?: any): Promise<T> {
    return this.fetch<T>(endpoint, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: data ? JSON.stringify(data) : undefined,
    });
  }

  // Dashboard
  async getDashboardSummary(): Promise<DashboardSummary> {
    return this.fetch<DashboardSummary>('/api/v1/dashboard/summary');
  }

  async getRecentAnalyses(): Promise<RecentAnalysis[]> {
    return this.fetch<RecentAnalysis[]>('/api/v1/dashboard/recent');
  }

  // Portfolio
  async getPortfolioOptimization(): Promise<PortfolioOptimization> {
    return this.fetch<PortfolioOptimization>('/api/v1/portfolio/optimization');
  }

  // Backtest
  async getBacktestResults(): Promise<BacktestResult[]> {
    return this.fetch<BacktestResult[]>('/api/v1/backtest/results');
  }

  // ML Model
  async getMLModelInfo(): Promise<MLModelInfo> {
    return this.fetch<MLModelInfo>('/api/v1/ml/model/info');
  }

  // Lookback Analysis
  async getLookbackAnalysis(): Promise<LookbackAnalysis> {
    return this.fetch<LookbackAnalysis>('/api/v1/analysis/lookback');
  }

  // 실행 메서드
  async runPortfolioOptimization(method: string = 'max_sharpe', capital: number = 10000000): Promise<PortfolioOptimization> {
    return this.post<PortfolioOptimization>(`/api/v1/portfolio/optimize?method=${method}&initial_capital=${capital}`);
  }

  async runLookbackAnalysis(method: string = 'portfolio_optimization', lookbackDays: number = 120, rebalanceFreq: number = 30): Promise<LookbackAnalysis> {
    return this.post<LookbackAnalysis>(`/api/v1/analysis/lookback/run?method=${method}&lookback_days=${lookbackDays}&rebalance_frequency=${rebalanceFreq}`);
  }

  async trainMLModel(modelType: string = 'xgboost', task: string = 'regression'): Promise<MLModelInfo> {
    return this.post<MLModelInfo>(`/api/v1/ml/train?model_type=${modelType}&task=${task}`);
  }

  // Parameters
  async getCurrentParameters(): Promise<any> {
    return this.fetch<any>('/api/v1/backtest/parameters');
  }

  async updateParameters(params: any): Promise<any> {
    return this.put<any>('/api/v1/backtest/parameters', params);
  }

  async getParameterPresets(): Promise<any> {
    return this.fetch<any>('/api/v1/parameters/presets');
  }

  async applyPreset(presetName: string): Promise<any> {
    return this.post<any>(`/api/v1/parameters/preset/${presetName}`);
  }

  async resetParameters(): Promise<any> {
    return this.post<any>('/api/v1/parameters/reset');
  }

  // Backtest Run
  async runBacktest(startDate?: string, endDate?: string): Promise<any> {
    const body: any = {};
    if (startDate) body.start_date = startDate;
    if (endDate) body.end_date = endDate;
    return this.post<any>('/api/v1/backtest/run', body);
  }

  // Backtest History
  async getBacktestHistory(): Promise<any[]> {
    return this.fetch<any[]>('/api/v1/backtest/history');
  }

  async saveBacktestHistory(history: any): Promise<any> {
    return this.post<any>('/api/v1/backtest/history/save', history);
  }

  // Train/Val/Test Split Results
  async getSplitResults(): Promise<any> {
    return this.fetch<any>('/api/v1/backtest/split-results');
  }

  // Cache Management
  async getCacheStatus(): Promise<any> {
    return this.fetch<any>('/api/v1/backtest/cache/status');
  }

  async updateCache(): Promise<any> {
    return this.post<any>('/api/v1/backtest/cache/update');
  }

  // ML Parameters
  async getMLParameters(): Promise<any> {
    return this.fetch<any>('/api/v1/ml/parameters/current');
  }

  async updateMLParameters(params: any): Promise<any> {
    return this.post<any>('/api/v1/ml/parameters/update', params);
  }

  async getMLHistory(): Promise<any[]> {
    return this.fetch<any[]>('/api/v1/ml/parameters/history');
  }

  async saveMLHistory(history: any): Promise<any> {
    return this.post<any>('/api/v1/ml/parameters/history/save', history);
  }

  // Lookback Parameters
  async getLookbackParameters(): Promise<any> {
    return this.fetch<any>('/api/v1/lookback/parameters/current');
  }

  async updateLookbackParameters(params: any): Promise<any> {
    return this.post<any>('/api/v1/lookback/parameters/update', params);
  }

  async getLookbackHistory(): Promise<any[]> {
    return this.fetch<any[]>('/api/v1/lookback/parameters/history');
  }

  async saveLookbackHistory(history: any): Promise<any> {
    return this.post<any>('/api/v1/lookback/parameters/history/save', history);
  }

  // AI Analysis
  async analyzeBacktest(metrics: any, trades: any[], userQuestion?: string): Promise<any> {
    return this.post<any>('/api/v1/ai/analyze/backtest', {
      metrics,
      trades,
      user_question: userQuestion
    });
  }

  async analyzePortfolio(holdings: any[], marketStatus: any, userQuestion?: string): Promise<any> {
    return this.post<any>('/api/v1/ai/analyze/portfolio', {
      holdings,
      market_status: marketStatus,
      user_question: userQuestion
    });
  }

  async analyzeMLModel(modelInfo: any, userQuestion?: string): Promise<any> {
    return this.post<any>('/api/v1/ai/analyze/ml-model', {
      model_info: modelInfo,
      user_question: userQuestion
    });
  }

  async analyzeLookback(summary: any, results: any[], userQuestion?: string): Promise<any> {
    return this.post<any>('/api/v1/ai/analyze/lookback', {
      summary,
      results,
      user_question: userQuestion
    });
  }
}

export const apiClient = new ApiClient();
