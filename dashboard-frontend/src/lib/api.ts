/** API Client for Software Factory Dashboard */

import axios, { AxiosInstance, AxiosError } from 'axios';
import type {
  WorkItem,
  FactoryState,
  RunSummary,
  OverviewMetrics,
  StageMetrics,
  CreateRunRequest,
  WebSocketMessage,
} from '../types/api';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const WS_BASE = import.meta.env.VITE_WS_URL || 'ws://localhost:8000';

class ApiClient {
  private client: AxiosInstance;
  private ws: WebSocket | null = null;
  private wsCallbacks: Map<string, (msg: WebSocketMessage) => void> = new Map();
  private reconnectTimeout: ReturnType<typeof setTimeout> | null = null;
  private clientId: string;

  constructor() {
    this.clientId = `client-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    
    this.client = axios.create({
      baseURL: `${API_BASE}/api/v1`,
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Request interceptor
    this.client.interceptors.request.use(
      (config) => config,
      (error) => Promise.reject(error)
    );

    // Response interceptor
    this.client.interceptors.response.use(
      (response) => response,
      (error: AxiosError) => {
        const message = error.response?.data?.detail || error.message;
        return Promise.reject(new Error(message));
      }
    );
  }

  // REST API methods
  async createRun(request: CreateRunRequest): Promise<FactoryState> {
    const response = await this.client.post<FactoryState>('/runs', request);
    return response.data;
  }

  async listRuns(limit = 50, offset = 0, status?: string): Promise<{ runs: RunSummary[] }> {
    const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
    if (status) params.append('status', status);
    const response = await this.client.get<{ runs: RunSummary[] }>(`/runs?${params}`);
    return response.data;
  }

  async getRun(runId: string): Promise<FactoryState> {
    const response = await this.client.get<FactoryState>(`/runs/${runId}`);
    return response.data;
  }

  async getRunHistory(runId: string): Promise<{ history: FactoryState[] }> {
    const response = await this.client.get<{ history: FactoryState[] }>(`/runs/${runId}/history`);
    return response.data;
  }

  async approveCheckpoint(runId: string, checkpointId: string, approver = 'dashboard-user'): Promise<void> {
    await this.client.post(`/runs/${runId}/checkpoint/${checkpointId}/approve`, { approver });
  }

  async rejectCheckpoint(runId: string, checkpointId: string, approver = 'dashboard-user'): Promise<void> {
    await this.client.post(`/runs/${runId}/checkpoint/${checkpointId}/reject`, { approver });
  }

  async getOverviewMetrics(timeRange = '24h'): Promise<OverviewMetrics> {
    const response = await this.client.get<OverviewMetrics>(`/metrics/overview?time_range=${timeRange}`);
    return response.data;
  }

  async getStageMetrics(stageId: string, timeRange = '24h'): Promise<StageMetrics> {
    const response = await this.client.get<StageMetrics>(`/metrics/stage/${stageId}?time_range=${timeRange}`);
    return response.data;
  }

  async healthCheck(): Promise<{ status: string }> {
    const response = await this.client.get<{ status: string }>('/health');
    return response.data;
  }

  async getConfig(): Promise<any> {
    const response = await this.client.get('/config');
    return response.data;
  }

  // WebSocket methods
  connectWebSocket(onMessage: (msg: WebSocketMessage) => void): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.wsCallbacks.set(this.clientId, onMessage);
      return;
    }

    this.wsCallbacks.set(this.clientId, onMessage);

    this.ws = new WebSocket(`${WS_BASE}/api/v1/ws/${this.clientId}`);

    this.ws.onopen = () => {
      console.log('WebSocket connected');
      this.send({ type: 'ping' });
    };

    this.ws.onmessage = (event) => {
      try {
        const message: WebSocketMessage = JSON.parse(event.data);
        this.wsCallbacks.forEach((callback) => callback(message));
      } catch (e) {
        console.error('Failed to parse WS message', e);
      }
    };

    this.ws.onclose = () => {
      console.log('WebSocket disconnected, reconnecting...');
      this.scheduleReconnect(onMessage);
    };

    this.ws.onerror = (error) => {
      console.error('WebSocket error', error);
    };
  }

  disconnectWebSocket(): void {
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.wsCallbacks.clear();
  }

  private scheduleReconnect(onMessage: (msg: WebSocketMessage) => void): void {
    if (this.reconnectTimeout) return;
    
    this.reconnectTimeout = setTimeout(() => {
      this.reconnectTimeout = null;
      this.connectWebSocket(onMessage);
    }, 3000);
  }

  subscribeToRun(runId: string): void {
    this.send({ type: 'subscribe', run_id: runId });
  }

  unsubscribeFromRun(runId: string): void {
    this.send({ type: 'unsubscribe', run_id: runId });
  }

  private send(message: any): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    }
  }
}

// Singleton instance
export const api = new ApiClient();

// React Query keys
export const queryKeys = {
  runs: (limit: number, offset: number, status?: string) => ['runs', limit, offset, status],
  run: (runId: string) => ['run', runId],
  runHistory: (runId: string) => ['runHistory', runId],
  overviewMetrics: (timeRange: string) => ['overviewMetrics', timeRange],
  stageMetrics: (stageId: string, timeRange: string) => ['stageMetrics', stageId, timeRange],
  config: () => ['config'],
};