/** Overview Page - Factory Dashboard */

import React, { useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  GitBranch, Play, CheckCircle, Box, CheckCircle2, 
  BookOpen, Activity, TrendingUp, Clock, 
  RefreshCw, Plus, ExternalLink
} from 'lucide-react';
import { cn, formatRelativeTime, formatCost, formatTokens, getStatusColor } from '../../lib/utils';
import { useFactoryStore } from '../../store/factoryStore';
import { api, queryKeys } from '../../lib/api';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

const stages = [
  { id: 'triage', name: 'Triage', icon: Play, description: 'Classify & route work', color: 'blue' },
  { id: 'planning', name: 'Planning', icon: CheckCircle, description: 'Technical specification', color: 'purple' },
  { id: 'execution', name: 'Execution', icon: Box, description: 'Implement changes', color: 'indigo' },
  { id: 'validation', name: 'Validation', icon: CheckCircle2, description: 'Review, test, secure', color: 'orange' },
  { id: 'release', name: 'Release', icon: Box, description: 'Deploy & ship', color: 'green' },
  { id: 'document', name: 'Docs', icon: BookOpen, description: 'AutoWiki updates', color: 'cyan' },
  { id: 'monitor', name: 'Monitor', icon: Activity, description: 'Incidents & health', color: 'red' },
];

const stageColors = {
  blue: 'bg-blue-500',
  purple: 'bg-purple-500',
  indigo: 'bg-indigo-500',
  orange: 'bg-orange-500',
  green: 'bg-green-500',
  cyan: 'bg-cyan-500',
  red: 'bg-red-500',
};

export function OverviewPage() {
  const { timeRange, setTimeRange, setOverviewMetrics } = useFactoryStore();
  const queryClient = useQueryClient();
  
  const { data: metrics, isLoading, error, refetch } = useQuery({
    queryKey: queryKeys.overviewMetrics(timeRange),
    queryFn: () => api.getOverviewMetrics(timeRange),
    refetchInterval: 30000,
  });
  
  const { data: runs } = useQuery({
    queryKey: queryKeys.runs(5, 0),
    queryFn: () => api.listRuns(5, 0),
  });
  
  const createRunMutation = useMutation({
    mutationFn: (request: any) => api.createRun(request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.runs(5, 0) });
      queryClient.invalidateQueries({ queryKey: queryKeys.overviewMetrics(timeRange) });
    },
  });
  
  // Update store when metrics load
  useEffect(() => {
    if (metrics) setOverviewMetrics(metrics);
  }, [metrics, setOverviewMetrics]);
  
  const handleCreateRun = () => {
    // Would open a modal
    console.log('Create run clicked');
  };
  
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Software Factory</h1>
          <p className="text-gray-500 mt-1">Autonomous SDLC automation dashboard</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => refetch()}
            disabled={isLoading}
            className="btn-secondary btn-sm"
          >
            <RefreshCw className={cn('w-4 h-4 mr-2', isLoading ? 'animate-spin' : '')} />
            Refresh
          </button>
          <button onClick={handleCreateRun} className="btn-primary">
            <Plus className="w-4 h-4 mr-2" />
            New Run
          </button>
        </div>
      </div>
      
      {/* Key Metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="Total Runs"
          value={metrics?.total_runs ?? 0}
          icon={GitBranch}
          color="blue"
          trend={metrics ? `${Math.round(metrics.success_rate * 100)}% success` : undefined}
        />
        <MetricCard
          title="Completed"
          value={metrics?.completed_runs ?? 0}
          icon={CheckCircle}
          color="green"
          trend={metrics ? `${metrics.completed_runs}/${metrics.total_runs}` : undefined}
        />
        <MetricCard
          title="Success Rate"
          value={metrics ? `${Math.round(metrics.success_rate * 100)}%` : '0%'}
          icon={TrendingUp}
          color="purple"
          trend="vs previous period"
        />
        <MetricCard
          title="Avg Cycle Time"
          value="N/A"
          icon={Clock}
          color="orange"
          trend="calculating..."
        />
      </div>
      
      {/* Stage Health */}
      <div className="card">
        <div className="p-6 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900">SDLC Stage Health</h2>
          <p className="text-sm text-gray-500 mt-1">Automation coverage and health across the software delivery lifecycle</p>
        </div>
        <div className="p-6">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {stages.map((stage) => {
              const stageMetrics = metrics?.stages?.[stage.id];
              const Color = stageColors[stage.color as keyof typeof stageColors];
              const Icon = stage.icon;
              
              return (
                <Link
                  key={stage.id}
                  to={`/stages/${stage.id}`}
                  className="card-hover p-4 border border-gray-200 rounded-lg group"
                >
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-3">
                      <div className={cn('w-10 h-10 rounded-lg flex items-center justify-center', Color)}>
                        <Icon className="w-5 h-5 text-white" />
                      </div>
                      <div>
                        <h3 className="font-medium text-gray-900">{stage.name}</h3>
                        <p className="text-sm text-gray-500">{stage.description}</p>
                      </div>
                    </div>
                    <ExternalLink className="w-4 h-4 text-gray-400 group-hover:text-gray-600 opacity-0 group-hover:opacity-100 transition-opacity" />
                  </div>
                  
                  <div className="mt-4 grid grid-cols-2 gap-4">
                    <div>
                      <p className="text-2xl font-bold text-gray-900">
                        {stageMetrics?.throughput ?? 0}
                      </p>
                      <p className="text-xs text-gray-500">Throughput</p>
                    </div>
                    <div>
                      <p className="text-2xl font-bold text-gray-900">
                        {stageMetrics?.pass_rate ? `${Math.round(stageMetrics.pass_rate * 100)}%` : 'N/A'}
                      </p>
                      <p className="text-xs text-gray-500">Pass Rate</p>
                    </div>
                    {stageMetrics?.backlog !== undefined && (
                      <div className="col-span-2">
                        <p className="text-sm text-gray-500">Backlog: {stageMetrics.backlog}</p>
                      </div>
                    )}
                  </div>
                </Link>
              );
            })}
          </div>
        </div>
      </div>
      
      {/* Recent Runs */}
      <div className="card">
        <div className="p-6 border-b border-gray-200 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">Recent Runs</h2>
          <Link to="/runs" className="text-sm text-factory-600 hover:text-factory-700 font-medium">
            View all →
          </Link>
        </div>
        <div className="divide-y divide-gray-200">
          {runs?.runs?.length === 0 ? (
            <div className="p-12 text-center">
              <GitBranch className="w-12 h-12 mx-auto text-gray-300 mb-4" />
              <h3 className="text-lg font-medium text-gray-900">No runs yet</h3>
              <p className="text-gray-500 mt-1">Create your first factory run to get started</p>
              <button onClick={handleCreateRun} className="btn-primary mt-4">
                <Plus className="w-4 h-4 mr-2" />
                Create Run
              </button>
            </div>
          ) : (
            runs?.runs?.map((run) => (
              <Link
                key={run.run_id}
                to={`/runs/${run.run_id}`}
                className="run-card flex items-center justify-between p-4"
              >
                <div className="flex items-center gap-4">
                  <div className={cn('w-10 h-10 rounded-lg flex items-center justify-center', getStatusColor(run.status))}>
                    <GitBranch className="w-5 h-5 text-white" />
                  </div>
                  <div>
                    <p className="font-medium text-gray-900 truncate max-w-md">{run.work_item.title}</p>
                    <p className="text-sm text-gray-500 flex items-center gap-2">
                      <span>{run.work_item.repository}</span>
                      <span>•</span>
                      <span className={cn('status-badge', getStatusColor(run.status))}>
                        {run.status.replace('_', ' ')}
                      </span>
                      <span>•</span>
                      <span>{formatRelativeTime(run.updated_at)}</span>
                    </p>
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-sm font-medium text-gray-900">{formatCost(run.metrics.total_cost)}</p>
                  <p className="text-xs text-gray-500">{formatTokens(run.metrics.total_tokens)} tokens</p>
                </div>
              </Link>
            ))}
          )}
        </div>
      </div>
    </div>
  );
}

function MetricCard({ 
  title, 
  value, 
  icon: Icon, 
  color, 
  trend 
}: { 
  title: string; 
  value: string | number; 
  icon: React.ComponentType<{ className?: string }>;
  color: keyof typeof stageColors;
  trend?: string;
}) {
  const Color = stageColors[color];
  
  return (
    <div className="card p-6">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-gray-500">{title}</p>
          <p className="text-3xl font-bold text-gray-900 mt-1">{value}</p>
          {trend && <p className="text-xs text-gray-500 mt-1">{trend}</p>}
        </div>
        <div className={cn('w-12 h-12 rounded-lg flex items-center justify-center', Color)}>
          <Icon className="w-6 h-6 text-white" />
        </div>
      </div>
    </div>
  );
}