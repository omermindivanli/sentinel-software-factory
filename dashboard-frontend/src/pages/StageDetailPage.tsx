/** Stage Detail Page */

import React, { useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  Play, CheckCircle, Box, CheckCircle2, BookOpen, Activity,
  ArrowLeft, RefreshCw, TrendingUp, Clock, Users,
  Filter, Search, ChevronDown, Download, ExternalLink
} from 'lucide-react';
import { cn, formatRelativeTime, formatCost, formatTokens, formatDuration, getStatusColor } from '../../lib/utils';
import { api, queryKeys } from '../../lib/api';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useFactoryStore } from '../../store/factoryStore';

const stageInfo: Record<string, any> = {
  triage: { name: 'Triage', icon: Play, description: 'Classify and route inbound work', color: 'blue', longDesc: 'The Triage stage classifies incoming work items (issues, PRs, Slack messages), removes duplicates, assigns priority, and routes to the appropriate next stage.' },
  planning: { name: 'Planning', icon: CheckCircle, description: 'Technical specification and task breakdown', color: 'purple', longDesc: 'The Planning stage creates detailed technical specifications, breaks down work into executable tasks, estimates effort, and identifies dependencies.' },
  execution: { name: 'Execution', icon: Box, description: 'Implement changes in isolated sandboxes', color: 'indigo', longDesc: 'The Execution stage runs worker agents in isolated git worktrees and Docker containers to implement the planned changes.' },
  validation: { name: 'Validation', icon: CheckCircle2, description: 'Automated review, QA, and security gates', color: 'orange', longDesc: 'The Validation stage runs code review, test suites, security scans, and human approval gates before allowing changes to proceed.' },
  release: { name: 'Release', icon: Box, description: 'Deployment gates and shipping', color: 'green', longDesc: 'The Release stage manages deployment to staging/production, runs smoke tests, and tracks deployment health.' },
  document: { name: 'Documentation', icon: BookOpen, description: 'AutoWiki and knowledge maintenance', color: 'cyan', longDesc: 'The Documentation stage automatically updates API docs, READMEs, changelogs, and architecture decision records.' },
  monitor: { name: 'Monitor', icon: Activity, description: 'Incident response and agent effectiveness', color: 'red', longDesc: 'The Monitor stage tracks deployed services, correlates incidents with recent changes, and feeds learnings back to the factory.' },
};

const stageColors = {
  blue: { bg: 'bg-blue-500', light: 'bg-blue-50', text: 'text-blue-700', border: 'border-blue-200' },
  purple: { bg: 'bg-purple-500', light: 'bg-purple-50', text: 'text-purple-700', border: 'border-purple-200' },
  indigo: { bg: 'bg-indigo-500', light: 'bg-indigo-50', text: 'text-indigo-700', border: 'border-indigo-200' },
  orange: { bg: 'bg-orange-500', light: 'bg-orange-50', text: 'text-orange-700', border: 'border-orange-200' },
  green: { bg: 'bg-green-500', light: 'bg-green-50', text: 'text-green-700', border: 'border-green-200' },
  cyan: { bg: 'bg-cyan-500', light: 'bg-cyan-50', text: 'text-cyan-700', border: 'border-cyan-200' },
  red: { bg: 'bg-red-500', light: 'bg-red-50', text: 'text-red-700', border: 'border-red-200' },
};

export function StageDetailPage() {
  const { stageId } = useParams<{ stageId: string }>();
  const { timeRange, setTimeRange, setSelectedStage } = useFactoryStore();
  const queryClient = useQueryClient();
  const [sortBy, setSortBy] = React.useState<'updated' | 'cost' | 'duration'>('updated');
  
  const stage = stageInfo[stageId || ''];
  
  if (!stage) {
    return (
      <div className="card p-12 text-center">
        <h1 className="text-2xl font-bold text-gray-900 mb-2">Stage Not Found</h1>
        <p className="text-gray-500">Unknown stage: {stageId}</p>
        <Link to="/" className="btn-primary mt-4 inline-block">Back to Overview</Link>
      </div>
    );
  }
  
  const colors = stageColors[stage.color as keyof typeof stageColors];
  const Icon = stage.icon;
  
  const { data: runs, isLoading, refetch } = useQuery({
    queryKey: [...queryKeys.runs(100, 0), stageId],
    queryFn: async () => {
      const result = await api.listRuns(100, 0);
      // Filter runs that have this stage
      return result.runs.filter((run: any) => run.stages?.[stageId]);
    },
    refetchInterval: 30000,
  });
  
  const { data: metrics, isLoading: metricsLoading } = useQuery({
    queryKey: queryKeys.stageMetrics(stageId!, timeRange),
    queryFn: () => api.getStageMetrics(stageId!, timeRange),
  });
  
  useEffect(() => {
    setSelectedStage(stageId!);
  }, [stageId, setSelectedStage]);
  
  const sortedRuns = React.useMemo(() => {
    if (!runs) return [];
    return [...runs].sort((a, b) => {
      const aVal = new Date(a.updated_at).getTime();
      const bVal = new Date(b.updated_at).getTime();
      return bVal - aVal;
    });
  }, [runs, sortBy]);
  
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        <div className="flex items-center gap-4">
          <Link to="/" className="p-2 text-gray-400 hover:text-gray-600 rounded-lg">
            <ArrowLeft className="w-5 h-5" />
          </Link>
          <div className={cn('w-14 h-14 rounded-xl flex items-center justify-center', colors.bg)}>
            <Icon className="w-7 h-7 text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">{stage.name}</h1>
            <p className="text-gray-500 mt-1">{stage.description}</p>
          </div>
        </div>
        
        <div className="flex flex-wrap gap-3">
          <select
            value={timeRange}
            onChange={(e) => setTimeRange(e.target.value as any)}
            className="input w-auto"
          >
            <option value="1h">Last hour</option>
            <option value="24h">Last 24 hours</option>
            <option value="7d">Last 7 days</option>
            <option value="30d">Last 30 days</option>
          </select>
          <button onClick={() => refetch()} disabled={isLoading} className="btn-secondary btn-sm">
            <RefreshCw className={cn('w-4 h-4 mr-2', isLoading ? 'animate-spin' : '')} />
            Refresh
          </button>
        </div>
      </div>
      
      {/* Description */}
      <div className={cn('card p-6', colors.light, colors.border)}>
        <p className="text-gray-700">{stage.longDesc}</p>
      </div>
      
      {/* Metrics */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        <StageMetricCard 
          title="Throughput" 
          value={metrics?.throughput ?? 0} 
          icon={TrendingUp} 
          color={stage.color}
          subtitle="Items processed"
        />
        <StageMetricCard 
          title="Pass Rate" 
          value={metrics?.pass_rate ? `${Math.round(metrics.pass_rate * 100)}%` : 'N/A'} 
          icon={CheckCircle} 
          color={stage.color}
          subtitle="Gate success rate"
        />
        <StageMetricCard 
          title="Avg Cycle Time" 
          value={metrics?.avg_cycle_time ? `${metrics.avg_cycle_time.toFixed(1)}m` : 'N/A'} 
          icon={Clock} 
          color={stage.color}
          subtitle="Stage duration"
        />
        <StageMetricCard 
          title="Queue Depth" 
          value={metrics?.queue_depth ?? 0} 
          icon={Users} 
          color={stage.color}
          subtitle="Pending items"
        />
        <StageMetricCard 
          title="Health" 
          value={metrics?.health || 'Unknown'} 
          icon={Activity} 
          color={stage.color}
          subtitle="Stage status"
        />
      </div>
      
      {/* Recent Runs in this Stage */}
      <div className="card">
        <div className="p-6 border-b border-gray-200 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <h2 className="text-lg font-semibold text-gray-900">Recent Runs in {stage.name}</h2>
          <div className="flex items-center gap-4">
            <input
              type="text"
              placeholder="Filter runs..."
              className="input w-64"
              onChange={(e) => setSearch(e.target.value)}
            />
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as any)}
              className="input w-auto"
            >
              <option value="updated">Sort: Updated</option>
              <option value="cost">Sort: Cost</option>
              <option value="duration">Sort: Duration</option>
            </select>
          </div>
        </div>
        
        {isLoading ? (
          <div className="p-8 text-center">
            <RefreshCw className="w-8 h-8 mx-auto text-factory-500 animate-spin mb-4" />
            <p className="text-gray-500">Loading runs...</p>
          </div>
        ) : sortedRuns.length === 0 ? (
          <div className="p-12 text-center">
            <Icon className="w-12 h-12 mx-auto text-gray-300 mb-4" />
            <h3 className="text-lg font-medium text-gray-900">No runs in this stage</h3>
            <p className="text-gray-500 mt-1">Runs will appear here when they reach the {stage.name} stage</p>
          </div>
        ) : (
          <div className="divide-y divide-gray-200">
            {sortedRuns.map((run) => (
              <StageRunRow key={run.run_id} run={run} stageId={stageId!} colors={colors} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
  
  // Local state for search
  const [search, setSearch] = React.useState('');
  
  const filteredRuns = React.useMemo(() => {
    if (!runs) return [];
    return runs.filter((run) => {
      if (!search) return true;
      const s = search.toLowerCase();
      return (
        run.work_item.title.toLowerCase().includes(s) ||
        run.work_item.repository.toLowerCase().includes(s)
      );
    });
  }, [runs, search]);
  
  const sortedRuns = React.useMemo(() => {
    return [...filteredRuns].sort((a, b) => {
      if (sortBy === 'updated') {
        return new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime();
      }
      if (sortBy === 'cost') {
        return b.metrics.total_cost - a.metrics.total_cost;
      }
      if (sortBy === 'duration') {
        const aDur = a.completed_at ? new Date(a.completed_at).getTime() - new Date(a.started_at).getTime() : 0;
        const bDur = b.completed_at ? new Date(b.completed_at).getTime() - new Date(b.started_at).getTime() : 0;
        return bDur - aDur;
      }
      return 0;
    });
  }, [filteredRuns, sortBy]);
}

function StageMetricCard({ title, value, icon: Icon, color, subtitle }: { 
  title: string; 
  value: string | number; 
  icon: React.ComponentType;
  color: keyof typeof stageColors;
  subtitle: string;
}) {
  const colors = stageColors[color];
  return (
    <div className={cn('card p-4', colors.light, colors.border)}>
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-gray-500">{title}</p>
          <p className="text-2xl font-bold text-gray-900 mt-1">{value}</p>
          <p className="text-xs text-gray-500">{subtitle}</p>
        </div>
        <div className={cn('w-10 h-10 rounded-lg flex items-center justify-center', colors.bg)}>
          <Icon className="w-5 h-5 text-white" />
        </div>
      </div>
    </div>
  );
}

function StageRunRow({ run, stageId, colors }: { run: any; stageId: string; colors: any }) {
  const stageData = run.stages[stageId];
  
  return (
    <Link
      to={`/runs/${run.run_id}`}
      className="run-card flex items-center justify-between p-4 hover:bg-gray-50 transition-colors"
    >
      <div className="flex items-center gap-4 flex-1 min-w-0">
        <div className={cn('w-10 h-10 rounded-lg flex items-center justify-center', colors.bg)}>
          <CheckCircle className="w-5 h-5 text-white" />
        </div>
        <div className="min-w-0">
          <Link to={`/runs/${run.run_id}`} className="font-medium text-gray-900 hover:text-factory-600 truncate block">
            {run.work_item.title}
          </Link>
          <p className="text-sm text-gray-500 truncate">{run.work_item.repository}</p>
        </div>
      </div>
      
      <div className="flex items-center gap-4 flex-wrap">
        {stageData && (
          <>
            <span className={cn('status-badge', getStatusColor(stageData.status))}>
              {stageData.status.replace('_', ' ')}
            </span>
            {stageData.started_at && (
              <span className="text-sm text-gray-500">
                Started {formatRelativeTime(stageData.started_at)}
              </span>
            )}
            {stageData.completed_at && stageData.started_at && (
              <span className="text-sm text-gray-500 font-mono">
                {formatDuration(new Date(stageData.completed_at).getTime() - new Date(stageData.started_at).getTime())}
              </span>
            )}
          </>
        )}
        
        <div className="text-right ml-auto">
          <p className="text-sm font-medium text-gray-900">{formatCost(run.metrics.total_cost)}</p>
          <p className="text-xs text-gray-500">{formatTokens(run.metrics.total_tokens)} tokens</p>
        </div>
      </div>
    </Link>
  );
}

// Need to import formatDuration and getStatusColor
import { formatDuration, getStatusColor } from '../../lib/utils';