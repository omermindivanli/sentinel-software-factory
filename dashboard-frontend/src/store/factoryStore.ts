/** Global state store using Zustand */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { FactoryState, RunSummary, OverviewMetrics, WebSocketMessage } from '../types/api';

interface FactoryStore {
  // Current run being viewed
  currentRun: FactoryState | null;
  setCurrentRun: (run: FactoryState | null) => void;
  
  // Run list
  runs: RunSummary[];
  runsLoading: boolean;
  runsError: string | null;
  setRuns: (runs: RunSummary[]) => void;
  setRunsLoading: (loading: boolean) => void;
  setRunsError: (error: string | null) => void;
  addRun: (run: RunSummary) => void;
  updateRun: (runId: string, updates: Partial<RunSummary>) => void;
  
  // Overview metrics
  overviewMetrics: OverviewMetrics | null;
  setOverviewMetrics: (metrics: OverviewMetrics) => void;
  
  // WebSocket
  wsConnected: boolean;
  setWsConnected: (connected: boolean) => void;
  wsMessages: WebSocketMessage[];
  addWsMessage: (msg: WebSocketMessage) => void;
  clearWsMessages: () => void;
  
  // UI state
  sidebarOpen: boolean;
  toggleSidebar: () => void;
  setSidebarOpen: (open: boolean) => void;
  
  timeRange: '1h' | '24h' | '7d' | '30d';
  setTimeRange: (range: '1h' | '24h' | '7d' | '30d') => void;
  
  // Selected stage for detail view
  selectedStage: string | null;
  setSelectedStage: (stage: string | null) => void;
  
  // Notifications
  notifications: Notification[];
  addNotification: (notification: Omit<Notification, 'id'>) => void;
  removeNotification: (id: string) => void;
}

interface Notification {
  id: string;
  type: 'success' | 'error' | 'warning' | 'info';
  title: string;
  message?: string;
  duration?: number;
}

export const useFactoryStore = create<FactoryStore>()(
  persist(
    (set, get) => ({
      // Current run
      currentRun: null,
      setCurrentRun: (run) => set({ currentRun: run }),
      
      // Runs
      runs: [],
      runsLoading: false,
      runsError: null,
      setRuns: (runs) => set({ runs }),
      setRunsLoading: (loading) => set({ runsLoading: loading }),
      setRunsError: (error) => set({ runsError: error }),
      addRun: (run) => set((state) => ({ runs: [run, ...state.runs] })),
      updateRun: (runId, updates) => set((state) => ({
        runs: state.runs.map((r) => r.run_id === runId ? { ...r, ...updates } : r),
        currentRun: state.currentRun?.run_id === runId ? { ...state.currentRun, ...updates } : state.currentRun,
      })),
      
      // Overview metrics
      overviewMetrics: null,
      setOverviewMetrics: (metrics) => set({ overviewMetrics: metrics }),
      
      // WebSocket
      wsConnected: false,
      setWsConnected: (connected) => set({ wsConnected: connected }),
      wsMessages: [],
      addWsMessage: (msg) => set((state) => ({ 
        wsMessages: [msg, ...state.wsMessages].slice(0, 100) 
      })),
      clearWsMessages: () => set({ wsMessages: [] }),
      
      // UI
      sidebarOpen: true,
      toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
      setSidebarOpen: (open) => set({ sidebarOpen: open }),
      
      timeRange: '24h',
      setTimeRange: (range) => set({ timeRange: range }),
      
      selectedStage: null,
      setSelectedStage: (stage) => set({ selectedStage: stage }),
      
      // Notifications
      notifications: [],
      addNotification: (notification) => {
        const id = `notif-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
        const newNotif = { ...notification, id };
        set((state) => ({ notifications: [...state.notifications, newNotif] }));
        
        // Auto-remove
        setTimeout(() => {
          get().removeNotification(id);
        }, notification.duration ?? 5000);
      },
      removeNotification: (id) => set((state) => ({
        notifications: state.notifications.filter((n) => n.id !== id)
      })),
    }),
    {
      name: 'factory-store',
      partialize: (state) => ({
        sidebarOpen: state.sidebarOpen,
        timeRange: state.timeRange,
      }),
    }
  )
);

// Selectors for performance
export const useCurrentRun = () => useFactoryStore((s) => s.currentRun);
export const useRuns = () => useFactoryStore((s) => s.runs);
export const useRunsLoading = () => useFactoryStore((s) => s.runsLoading);
export const useOverviewMetrics = () => useFactoryStore((s) => s.overviewMetrics);
export const useWsConnected = () => useFactoryStore((s) => s.wsConnected);
export const useSidebarOpen = () => useFactoryStore((s) => s.sidebarOpen);
export const useTimeRange = () => useFactoryStore((s) => s.timeRange);
export const useNotifications = () => useFactoryStore((s) => s.notifications);
export const useSelectedStage = () => useFactoryStore((s) => s.selectedStage);