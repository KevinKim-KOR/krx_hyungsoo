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
    return this.fetch<any>('/api/v1/parameters/current');
  }

  async updateParameters(params: any): Promise<any> {
    return this.post<any>('/api/v1/parameters/update', params);
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
  async runBacktest(): Promise<any> {
    return this.post<any>('/api/v1/backtest/run');
  }
}

export const apiClient = new ApiClient();
