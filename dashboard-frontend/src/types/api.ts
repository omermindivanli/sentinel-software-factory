/** API Types for Software Factory Dashboard */

export interface WorkItem {
  id: string;
  title: string;
  description: string;
  source: string;
  source_id: string;
  repository: string;
  branch: string;
  priority: 'low' | 'medium' | 'high' | 'critical';
  labels: string[];
  created_at: string;
  updated_at: string;
}

export interface StageExecution {
  stage_id: string;
  status: StageStatus;
  agent_id?: string;
  sandbox_id?: string;
  input_data: Record<string, any>;
  output_data: Record<string, any>;
  metrics: Record<string, any>;
  started_at?: string;
  completed_at?: string;
  error?: string;
  retry_count: number;
  max_retries: number;
}

export type StageStatus = 'pending' | 'running' | 'waiting_human' | 'completed' | 'failed' | 'skipped';

export interface FactoryState {
  run_id: string;
  work_item: WorkItem;
  stages: Record<string, StageExecution>;
  current_stage?: string;
  stage_order: string[];
  sandboxes: Record<string, SandboxExecution>;
  active_sandboxes: string[];
  agents: Record<string, AgentExecution>;
  gate_results: GateResult[];
  checkpoints: HumanCheckpoint[];
  shared_context: Record<string, any>;
  memory_refs: string[];
  total_tokens: number;
  total_cost: number;
  started_at: string;
  updated_at: string;
  completed_at?: string;
  overall_status: 'running' | 'paused' | 'completed' | 'failed' | 'cancelled';
  error?: string;
}

export interface SandboxExecution {
  id: string;
  worktree_path?: string;
  container_id?: string;
  status: SandboxStatus;
  repository: string;
  branch: string;
  base_branch: string;
  resources: Record<string, any>;
  artifacts: string[];
  logs: string[];
  created_at: string;
  started_at?: string;
  completed_at?: string;
}

export type SandboxStatus = 'creating' | 'ready' | 'running' | 'completed' | 'failed' | 'cleaning_up';

export interface AgentExecution {
  id: string;
  agent_type: string;
  agent_name: string;
  status: AgentStatus;
  current_thought?: string;
  current_action?: string;
  tool_calls: ToolCall[];
  observations: Observation[];
  tokens_used: number;
  cost: number;
  started_at: string;
  completed_at?: string;
  error?: string;
}

export type AgentStatus = 'idle' | 'thinking' | 'acting' | 'waiting' | 'completed' | 'error';

export interface ToolCall {
  name: string;
  args: Record<string, any>;
  id: string;
  timestamp: string;
}

export interface Observation {
  tool: string;
  result: string;
  timestamp: string;
}

export interface GateResult {
  gate_id: string;
  name: string;
  passed: boolean;
  score?: number;
  details: Record<string, any>;
  artifacts: string[];
  executed_at: string;
}

export interface HumanCheckpoint {
  id: string;
  stage_id: string;
  title: string;
  description: string;
  required_approvers: number;
  approvers: string[];
  status: 'pending' | 'approved' | 'rejected';
  created_at: string;
  resolved_at?: string;
  comments: Comment[];
}

export interface Comment {
  author: string;
  text: string;
  timestamp: string;
}

export interface RunSummary {
  run_id: string;
  work_item: WorkItem;
  status: string;
  current_stage?: string;
  stages: Record<string, StageExecution>;
  metrics: {
    total_tokens: number;
    total_cost: number;
  };
  created_at: string;
  updated_at: string;
}

export interface OverviewMetrics {
  time_range: string;
  total_runs: number;
  completed_runs: number;
  success_rate: number;
  stages: Record<string, StageMetrics>;
}

export interface StageMetrics {
  throughput: number;
  backlog: number;
  pass_rate?: number;
  avg_time?: number;
  deployments?: number;
  cycle_time?: number;
  updated?: number;
  coverage?: number;
  incidents?: number;
  mttr?: number;
}

export interface WebSocketMessage {
  type: 'run_update' | 'agent_thought' | 'stage_transition' | 'subscribed' | 'pong' | 'error';
  run_id?: string;
  data?: any;
  agent?: string;
  thought?: string;
  action?: string;
  from_stage?: string;
  to_stage?: string;
  timestamp: string;
}

export interface CreateRunRequest {
  title: string;
  description: string;
  source?: string;
  source_id?: string;
  repository: string;
  branch?: string;
  priority?: 'low' | 'medium' | 'high' | 'critical';
  labels?: string[];
}