/** Run Detail Page */

import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  GitBranch, Play, CheckCircle, Box, CheckCircle2,
  BookOpen, Activity, ChevronRight, ChevronDown,
  Clock, DollarSign, Database, Zap, MessageSquare,
  Terminal, FileText, Shield, RefreshCw, X,
  ExternalLink, PauseCircle, AlertTriangle
} from 'lucide-react';
import { cn, formatRelativeTime, formatCost, formatTokens, formatDuration, getStatusColor } from '../../lib/utils';
import { api, queryKeys } from '../../lib/api';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useFactoryStore } from '../../store/factoryStore';

const stages = [
  { id: 'triage', name: 'Triage', icon: Play, description: 'Classify & route', color: 'blue' },
  { id: 'planning', name: 'Planning', icon: CheckCircle, description: 'Technical spec', color: 'purple' },
  { id: 'execution', name: 'Execution', icon: Box, description: 'Implement', color: 'indigo' },
  { id: 'validation', name: 'Validation', icon: CheckCircle2, description: 'Review, test, secure', color: 'orange' },
  { id: 'release', name: 'Release', icon: Box, description: 'Deploy & ship', color: 'green' },
  { id: 'document', name: 'Documentation', icon: BookOpen, description: 'AutoWiki', color: 'cyan' },
  { id: 'monitor', name: 'Monitor', icon: Activity, description: 'Incidents & health', color: 'red' },
];

const stageColors = {
  blue: { bg: 'bg-blue-500', light: 'bg-blue-50', text: 'text-blue-700', border: 'border-blue-200' },
  purple: { bg: 'bg-purple-500', light: 'bg-purple-50', text: 'text-purple-700', border: 'border-purple-200' },
  indigo: { bg: 'bg-indigo-500', light: 'bg-indigo-50', text: 'text-indigo-700', border: 'border-indigo-200' },
  orange: { bg: 'bg-orange-500', light: 'bg-orange-50', text: 'text-orange-700', border: 'border-orange-200' },
  green: { bg: 'bg-green-500', light: 'bg-green-50', text: 'text-green-700', border: 'border-green-200' },
  cyan: { bg: 'bg-cyan-500', light: 'bg-cyan-50', text: 'text-cyan-700', border: 'border-cyan-200' },
  red: { bg: 'bg-red-500', light: 'bg-red-50', text: 'text-red-700', border: 'border-red-200' },
};

const stageIcons = {
  triage: Play,
  planning: CheckCircle,
  execution: Box,
  validation: CheckCircle2,
  release: Box,
  document: BookOpen,
  monitor: Activity,
};

export function RunDetailPage() {
  const { runId } = useParams<{ runId: string }>();
  const queryClient = useQueryClient();
  const { setCurrentRun, setSelectedStage } = useFactoryStore();
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);
  const [showThoughts, setShowThoughts] = useState(true);
  
  const { data: run, isLoading, error, refetch } = useQuery({
    queryKey: queryKeys.run(runId!),
    queryFn: () => api.getRun(runId!),
    refetchInterval: (query) => query.state.data?.overall_status === 'running' ? 2000 : false,
    enabled: !!runId,
  });
  
  // Connect WebSocket for real-time updates
  useEffect(() => {
    if (!runId) return;
    
    const handleMessage = (msg: any) => {
      if (msg.run_id === runId) {
        // Invalidate to refetch
        queryClient.invalidateQueries({ queryKey: queryKeys.run(runId) });
      }
    };
    
    api.connectWebSocket(handleMessage);
    api.subscribeToRun(runId);
    
    return () => {
      api.unsubscribeFromRun(runId);
    };
  }, [runId]);
  
  // Update store when run loads
  useEffect(() => {
    if (run) {
      setCurrentRun(run);
    }
  }, [run, setCurrentRun]);
  
  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-center h-64">
          <RefreshCw className="w-10 h-10 text-factory-500 animate-spin" />
        </div>
      </div>
    );
  }
  
  if (error || !run) {
    return (
      <div className="card p-12 text-center">
        <AlertTriangle className="w-12 h-12 mx-auto text-red-500 mb-4" />
        <h2 className="text-xl font-semibold text-gray-900">Run not found</h2>
        <p className="text-gray-500 mt-2">{error?.message || 'Unknown error'}</p>
        <Link to="/runs" className="btn-primary mt-4 inline-block">
          Back to Runs
        </Link>
      </div>
    );
  }
  
  const currentStageIndex = stages.findIndex(s => s.id === run.current_stage);
  
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4">
        <div className="flex-1">
          <div className="flex items-center gap-3 mb-2">
            <Link to="/runs" className="p-2 text-gray-400 hover:text-gray-600 rounded-lg">
              <ChevronDown className="w-5 h-5" />
            </Link>
            <div>
              <h1 className="text-2xl font-bold text-gray-900 truncate">{run.work_item.title}</h1>
              <div className="flex items-center gap-3 mt-1 text-sm text-gray-500">
                <span className="font-mono">{run.run_id.slice(0, 8)}...</span>
                <span>•</span>
                <span>{run.work_item.repository}</span>
                <span>•</span>
                <span className={cn('status-badge', getStatusColor(run.work_item.priority))}>
                  {run.work_item.priority}
                </span>
              </div>
            </div>
          </div>
          
          <div className="flex items-center gap-2 mt-4">
            <span className={cn('status-badge px-3 py-1 text-sm', getStatusColor(run.overall_status))}>
              {run.overall_status.replace('_', ' ')}
            </span>
            {run.current_stage && (
              <>
                <span className="text-gray-400">→</span>
                <span className="text-sm text-gray-500">
                  Current: {stages.find(s => s.id === run.current_stage)?.name || run.current_stage}
                </span>
              </>
            )}
            {run.error && (
              <>
                <span className="text-gray-400">→</span>
                <span className="text-sm text-red-500 flex items-center gap-1">
                  <AlertTriangle className="w-3 h-3" />
                  Error: {truncate(run.error, 50)}
                </span>
              </>
            )}
          </div>
        </div>
        
        <div className="flex flex-wrap gap-2 lg:ml-4">
          <Link to="/runs" className="btn-secondary btn-sm">
            ← Back to Runs
          </Link>
          <button onClick={() => refetch()} disabled={isLoading} className="btn-secondary btn-sm">
            <RefreshCw className={cn('w-4 h-4 mr-2', isLoading ? 'animate-spin' : '')} />
            Refresh
          </button>
        </div>
      </div>
      
      {/* Metrics */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        <MetricStat title="Total Cost" value={formatCost(run.total_cost)} icon={DollarSign} color="green" />
        <MetricStat title="Tokens" value={formatTokens(run.total_tokens)} icon={Database} color="blue" />
        <MetricStat title="Duration" value={run.completed_at ? formatDuration(new Date(run.completed_at).getTime() - new Date(run.started_at).getTime()) : 'Running...'} icon={Clock} color="orange" />
        <MetricStat title="Stages" value={`${Object.values(run.stages).filter(s => s.status === 'completed').length}/${stages.length}`} icon={CheckCircle} color="purple" />
        <MetricStat title="Agents" value={Object.keys(run.agents).length} icon={Zap} color="indigo" />
      </div>
      
      {/* Stage Progress */}
      <div className="card">
        <div className="p-6 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900">Pipeline Progress</h2>
        </div>
        <div className="p-6">
          <div className="relative">
            {/* Progress line */}
            <div className="absolute left-10 right-10 top-6 h-1 bg-gray-200" />
            <div className="absolute left-10 top-6 h-1 bg-factory-500" 
              style={{ width: `${((currentStageIndex + 1) / stages.length) * 100}%` }} 
            />
            
            {/* Stage nodes */}
            <div className="flex items-center justify-between relative z-10">
              {stages.map((stage, index) => {
                const stageData = run.stages[stage.id];
                const isCompleted = stageData?.status === 'completed';
                const isCurrent = run.current_stage === stage.id;
                const isFailed = stageData?.status === 'failed';
                const isWaiting = stageData?.status === 'waiting_human';
                
                let nodeColor = 'bg-gray-300';
                let borderColor = 'border-gray-300';
                let textColor = 'text-gray-500';
                
                if (isCompleted) {
                  nodeColor = 'bg-green-500';
                  borderColor = 'border-green-500';
                  textColor = 'text-green-600';
                } else if (isFailed) {
                  nodeColor = 'bg-red-500';
                  borderColor = 'border-red-500';
                  textColor = 'text-red-600';
                } else if (isWaiting) {
                  nodeColor = 'bg-yellow-500';
                  borderColor = 'border-yellow-500';
                  textColor = 'text-yellow-600';
                } else if (isCurrent) {
                  nodeColor = 'bg-factory-500';
                  borderColor = 'border-factory-500';
                  textColor = 'text-factory-600';
                }
                
                const colors = stageColors[stage.color as keyof typeof stageColors];
                const Icon = stageIcons[stage.id as keyof typeof stageIcons];
                
                return (
                  <Link
                    key={stage.id}
                    to={`/runs/${runId}/stage/${stage.id}`}
                    className="flex flex-col items-center gap-2 flex-1 relative"
                  >
                    <div className={cn(
                      'w-12 h-12 rounded-full flex items-center justify-center border-4 transition-all',
                      nodeColor,
                      borderColor,
                      isCurrent && 'ring-4 ring-factory-500/30 animate-pulse',
                      isCompleted && 'cursor-pointer hover:scale-105',
                    )}>
                      <Icon className={cn('w-6 h-6', isCompleted || isCurrent || isFailed ? 'text-white' : 'text-gray-400')} />
                    </div>
                    <span className={cn('text-xs font-medium text-center w-24', textColor)}>
                      {stage.name}
                    </span>
                    {stageData && (
                      <div className="mt-1 flex items-center gap-1">
                        {isWaiting && <PauseCircle className="w-3 h-3 text-yellow-500" />}
                        {isFailed && <AlertTriangle className="w-3 h-3 text-red-500" />}
                        {isCompleted && <CheckCircle className="w-3 h-3 text-green-500" />}
                      </div>
                    )}
                  </Link>
                );
              })}
            </div>
          </div>
        </div>
      </div>
      
      {/* Main Content Grid */}
      <div className="grid lg:grid-cols-3 gap-6">
        {/* Left: Stage Details & Agent Thoughts */}
        <div className="lg:col-span-2 space-y-6">
          {/* Stage Detail */}
          {run.current_stage && (
            <StageDetailCard 
              run={run} 
              stageId={run.current_stage} 
              onAgentSelect={setSelectedAgent}
              selectedAgent={selectedAgent}
            />
          )}
          
          {/* Agent Thought Stream */}
          {showThoughts && run.agents && Object.keys(run.agents).length > 0 && (
            <AgentThoughtStream 
              agents={run.agents} 
              selectedAgent={selectedAgent}
              onAgentSelect={setSelectedAgent}
            />
          )}
        </div>
        
        {/* Right: Sidebar with details */}
        <div className="space-y-6">
          {/* Work Item Info */}
          <WorkItemCard workItem={run.work_item} />
          
          {/* Gates */}
          {run.gate_results.length > 0 && <GatesCard gates={run.gate_results} />}
          
          {/* Checkpoints */}
          {run.checkpoints.length > 0 && <CheckpointsCard checkpoints={run.checkpoints} />}
          
          {/* Sandboxes */}
          {run.sandboxes && Object.keys(run.sandboxes).length > 0 && (
            <SandboxesCard sandboxes={run.sandboxes} />
          )}
        </div>
      </div>
    </div>
  );
}

function MetricStat({ title, value, icon: Icon, color }: { title: string; value: string; icon: React.ComponentType; color: keyof typeof stageColors }) {
  const colors = stageColors[color];
  return (
    <div className={cn('card p-4', colors.light, colors.border)}>
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-gray-500">{title}</p>
          <p className="text-2xl font-bold text-gray-900 mt-1">{value}</p>
        </div>
        <div className={cn('w-10 h-10 rounded-lg flex items-center justify-center', colors.bg)}>
          <Icon className="w-5 h-5 text-white" />
        </div>
      </div>
    </div>
  );
}

function StageDetailCard({ 
  run, 
  stageId, 
  onAgentSelect,
  selectedAgent,
}: { 
  run: any; 
  stageId: string; 
  onAgentSelect: (agent: string | null) => void;
  selectedAgent: string | null;
}) {
  const stage = stages.find(s => s.id === stageId);
  const stageData = run.stages[stageId];
  const colors = stageColors[stage?.color as keyof typeof stageColors] || stageColors.blue;
  const Icon = stageIcons[stageId as keyof typeof stageIcons];
  
  if (!stageData) return null;
  
  const agents = Object.entries(run.agents).filter(([_, a]: [string, any]) => 
    a.agent_type === stageId || (stageId === 'execution' && a.agent_type === 'worker')
  );
  
  return (
    <div className={cn('card', colors.border)}>
      <div className={cn('p-4 border-b', colors.light)}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className={cn('w-10 h-10 rounded-lg flex items-center justify-center', colors.bg)}>
              <Icon className="w-5 h-5 text-white" />
            </div>
            <div>
              <h3 className="font-semibold text-gray-900">{stage?.name}</h3>
              <p className="text-sm text-gray-500">{stage?.description}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className={cn('status-badge', getStatusColor(stageData.status))}>
              {stageData.status.replace('_', ' ')}
            </span>
            {stageData.started_at && (
              <span className="text-sm text-gray-500">
                Started {formatRelativeTime(stageData.started_at)}
              </span>
            )}
          </div>
        </div>
      </div>
      
      <div className="p-4">
        {/* Output Summary */}
        {stageData.output_data && Object.keys(stageData.output_data).length > 0 && (
          <div className="mb-4">
            <h4 className="text-sm font-medium text-gray-700 mb-2">Output</h4>
            <div className="bg-gray-50 rounded-lg p-3 max-h-40 overflow-auto font-mono text-xs">
              <pre>{JSON.stringify(stageData.output_data, null, 2)}</pre>
            </div>
          </div>
        )}
        
        {/* Agents */}
        {agents.length > 0 && (
          <div>
            <h4 className="text-sm font-medium text-gray-700 mb-2">Agents</h4>
            <div className="space-y-2">
              {agents.map(([id, agent]: [string, any]) => (
                <AgentCard 
                  key={id} 
                  agentId={id} 
                  agent={agent} 
                  selected={selectedAgent === id}
                  onClick={() => onAgentSelect(selectedAgent === id ? null : id)}
                />
              ))}
            </div>
          </div>
        )}
        
        {/* Metrics */}
        {stageData.metrics && Object.keys(stageData.metrics).length > 0 && (
          <div className="mt-4 pt-4 border-t border-gray-200">
            <h4 className="text-sm font-medium text-gray-700 mb-2">Metrics</h4>
            <div className="grid grid-cols-2 gap-2">
              {Object.entries(stageData.metrics).map(([key, value]) => (
                <div key={key} className="bg-gray-50 rounded p-2">
                  <p className="text-xs text-gray-500">{key}</p>
                  <p className="font-mono text-sm">{JSON.stringify(value)}</p>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function AgentCard({ agentId, agent, selected, onClick }: { agentId: string; agent: any; selected: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'w-full p-3 rounded-lg border text-left transition-all',
        selected 
          ? 'border-factory-500 bg-factory-50 ring-2 ring-factory-500/20' 
          : 'border-gray-200 hover:border-gray-300'
      )}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gray-100 flex items-center justify-center">
            <Terminal className="w-4 h-4 text-gray-600" />
          </div>
          <div>
            <p className="font-medium text-gray-900">{agent.agent_name}</p>
            <p className="text-xs text-gray-500">{agent.agent_type}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className={cn('status-badge text-xs', getStatusColor(agent.status))}>
            {agent.status}
          </span>
          <span className="font-mono text-xs text-gray-500">{formatTokens(agent.tokens_used)}</span>
          <span className="font-mono text-xs text-gray-500">{formatCost(agent.cost)}</span>
        </div>
      </div>
      
      {agent.current_thought && (
        <div className="mt-2 p-2 bg-gray-50 rounded text-sm text-gray-600 font-mono">
          💭 {truncate(agent.current_thought, 100)}
        </div>
      )}
      
      {agent.current_action && (
        <div className="mt-1 p-2 bg-factory-50 rounded text-sm text-factory-700 font-mono">
          ⚡ {agent.current_action}
        </div>
      )}
    </button>
  );
}

function AgentThoughtStream({ agents, selectedAgent, onAgentSelect }: { agents: Record<string, any>; selectedAgent: string | null; onAgentSelect: (agent: string | null) => void }) {
  const agentEntries = Object.entries(agents).sort((a, b) => 
    new Date(b[1].started_at).getTime() - new Date(a[1].started_at).getTime()
  );
  
  if (agentEntries.length === 0) return null;
  
  return (
    <div className="card">
      <div className="p-4 border-b border-gray-200 flex items-center justify-between">
        <h3 className="font-semibold text-gray-900 flex items-center gap-2">
          <MessageSquare className="w-5 h-5" />
          Agent Thought Stream
        </h3>
        <select
          value={selectedAgent || 'all'}
          onChange={(e) => onAgentSelect(e.target.value === 'all' ? null : e.target.value)}
          className="input w-auto min-w-[150px]"
        >
          <option value="all">All Agents</option>
          {agentEntries.map(([id, agent]) => (
            <option key={id} value={id}>{agent.agent_name}</option>
          ))}
        </select>
      </div>
      
      <div className="thought-stream">
        {agentEntries
          .filter(([id]) => !selectedAgent || selectedAgent === id)
          .flatMap(([id, agent]) => [
            ...(agent.tool_calls || []).map((tc: any, i: number) => ({
              type: 'tool' as const,
              agentId: id,
              agentName: agent.agent_name,
              content: `🔧 ${tc.name}(${JSON.stringify(tc.args).slice(0, 50)}...)`,
              timestamp: tc.timestamp,
            })),
            ...(agent.observations || []).map((obs: any, i: number) => ({
              type: 'observation' as const,
              agentId: id,
              agentName: agent.agent_name,
              content: `👁 ${obs.tool}: ${obs.result.slice(0, 100)}...`,
              timestamp: obs.timestamp,
            })),
          ])
          .sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())
          .slice(-50)
          .map((item, i) => (
            <div key={i} className="thought-item">
              <span className="thought-agent">{item.agentName}</span>
              <span className="thought-content">{item.content}</span>
              <span className="text-xs text-gray-400 whitespace-nowrap">
                {formatRelativeTime(item.timestamp)}
              </span>
            </div>
          ))}
      </div>
    </div>
  );
}

function WorkItemCard({ workItem }: { workItem: any }) {
  return (
    <div className="card p-4">
      <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
        <FileText className="w-5 h-5" />
        Work Item
      </h3>
      <dl className="space-y-3 text-sm">
        <div className="flex justify-between">
          <dt className="text-gray-500">ID</dt>
          <dd className="font-mono text-gray-900">{workItem.id}</dd>
        </div>
        <div className="flex justify-between">
          <dt className="text-gray-500">Source</dt>
          <dd className="font-medium text-gray-900">{workItem.source} ({workItem.source_id})</dd>
        </div>
        <div className="flex justify-between">
          <dt className="text-gray-500">Repository</dt>
          <dd className="font-medium text-gray-900">{workItem.repository}</dd>
        </div>
        <div className="flex justify-between">
          <dt className="text-gray-500">Branch</dt>
          <dd className="font-mono text-gray-900">{workItem.branch}</dd>
        </div>
        <div className="flex justify-between">
          <dt className="text-gray-500">Priority</dt>
          <dd className={cn('status-badge', getPriorityColor(workItem.priority))}>
            {workItem.priority}
          </dd>
        </div>
        <div className="flex justify-between">
          <dt className="text-gray-500">Labels</dt>
          <dd className="flex flex-wrap gap-1">
            {workItem.labels.map((l: string) => (
              <span key={l} className="badge-gray">{l}</span>
            ))}
          </dd>
        </div>
      </dl>
    </div>
  );
}

function GatesCard({ gates }: { gates: any[] }) {
  return (
    <div className="card p-4">
      <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
        <Shield className="w-5 h-5" />
        Validation Gates
      </h3>
      <div className="space-y-2">
        {gates.map((gate) => (
          <div key={gate.gate_id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
            <div className="flex items-center gap-3">
              <span className={cn('w-2 h-2 rounded-full', gate.passed ? 'bg-green-500' : 'bg-red-500')} />
              <span className="font-medium text-gray-900">{gate.name}</span>
              {gate.score !== undefined && (
                <span className="text-sm text-gray-500">Score: {(gate.score * 100).toFixed(0)}%</span>
              )}
            </div>
            <span className={cn('status-badge', gate.passed ? 'status-completed' : 'status-failed')}>
              {gate.passed ? 'Passed' : 'Failed'}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function CheckpointsCard({ checkpoints }: { checkpoints: any[] }) {
  return (
    <div className="card p-4">
      <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
        <AlertTriangle className="w-5 h-5" />
        Human Checkpoints
      </h3>
      <div className="space-y-2">
        {checkpoints.map((cp) => (
          <div key={cp.id} className="p-3 bg-gray-50 rounded-lg">
            <div className="flex items-center justify-between mb-1">
              <span className="font-medium text-gray-900">{cp.title}</span>
              <span className={cn('status-badge', 
                cp.status === 'approved' ? 'status-completed' : 
                cp.status === 'rejected' ? 'status-failed' : 'status-waiting')}>
                {cp.status}
              </span>
            </div>
            <p className="text-sm text-gray-500">{cp.description}</p>
            {cp.approvers.length > 0 && (
              <p className="text-xs text-gray-500 mt-1">Approved by: {cp.approvers.join(', ')}</p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function SandboxesCard({ sandboxes }: { sandboxes: Record<string, any> }) {
  return (
    <div className="card p-4">
      <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
        <Terminal className="w-5 h-5" />
        Sandboxes
      </h3>
      <div className="space-y-2">
        {Object.entries(sandboxes).map(([id, sb]) => (
          <div key={id} className="p-3 bg-gray-50 rounded-lg">
            <div className="flex items-center justify-between mb-1">
              <span className="font-mono text-sm text-gray-900">{sb.branch}</span>
              <span className={cn('status-badge', getStatusColor(sb.status))}>
                {sb.status}
              </span>
            </div>
            <div className="text-xs text-gray-500 flex gap-4">
              <span>Worktree: {sb.worktree_path?.split('/').pop()}</span>
              <span>Container: {sb.container_id?.slice(0, 12)}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function truncate(str: string, length: number): string {
  if (str.length <= length) return str;
  return str.slice(0, length - 3) + '...';
}