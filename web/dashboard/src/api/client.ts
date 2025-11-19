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

  private async fetch<T>(endpoint: string): Promise<T> {
    const response = await fetch(`${this.baseUrl}${endpoint}`);
    if (!response.ok) {
      throw new Error(`API Error: ${response.statusText}`);
    }
    return response.json();
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
}

export const apiClient = new ApiClient();
