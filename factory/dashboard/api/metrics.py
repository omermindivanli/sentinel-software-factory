"""Prometheus metrics for the factory."""

from prometheus_client import Counter, Histogram, Gauge, Summary, CollectorRegistry
from typing import Optional

# Create custom registry
registry = CollectorRegistry()

# Run metrics
runs_total = Counter(
    'factory_runs_total',
    'Total number of factory runs',
    ['status', 'repository'],
    registry=registry
)

run_duration = Histogram(
    'factory_run_duration_seconds',
    'Factory run duration in seconds',
    ['repository', 'stage'],
    registry=registry
)

# Stage metrics
stage_throughput = Counter(
    'factory_stage_throughput_total',
    'Number of items processed by stage',
    ['stage', 'status'],
    registry=registry
)

stage_pass_rate = Gauge(
    'factory_stage_pass_rate',
    'Pass rate for stage',
    ['stage'],
    registry=registry
)

stage_cycle_time = Histogram(
    'factory_stage_cycle_time_seconds',
    'Cycle time for stage',
    ['stage'],
    registry=registry
)

stage_queue_depth = Gauge(
    'factory_stage_queue_depth',
    'Current queue depth for stage',
    ['stage'],
    registry=registry
)

# Agent metrics
agent_executions = Counter(
    'factory_agent_executions_total',
    'Total agent executions',
    ['agent_type', 'status'],
    registry=registry
)

agent_tokens = Counter(
    'factory_agent_tokens_total',
    'Total tokens used by agents',
    ['agent_type', 'model'],
    registry=registry
)

agent_cost = Counter(
    'factory_agent_cost_total',
    'Total cost by agents',
    ['agent_type', 'model'],
    registry=registry
)

agent_latency = Histogram(
    'factory_agent_latency_seconds',
    'Agent execution latency',
    ['agent_type'],
    registry=registry
)

# Sandbox metrics
sandbox_creations = Counter(
    'factory_sandbox_creations_total',
    'Total sandboxes created',
    ['repository'],
    registry=registry
)

sandbox_duration = Histogram(
    'factory_sandbox_duration_seconds',
    'Sandbox lifetime',
    ['repository'],
    registry=registry
)

sandbox_failures = Counter(
    'factory_sandbox_failures_total',
    'Sandbox creation/execution failures',
    ['repository', 'error_type'],
    registry=registry
)

# Gate metrics
gate_evaluations = Counter(
    'factory_gate_evaluations_total',
    'Total gate evaluations',
    ['gate', 'result'],
    registry=registry
)

gate_latency = Histogram(
    'factory_gate_latency_seconds',
    'Gate evaluation latency',
    ['gate'],
    registry=registry
)

# Memory metrics
memory_operations = Counter(
    'factory_memory_operations_total',
    'Memory operations',
    ['tier', 'operation'],
    registry=registry
)

memory_size = Gauge(
    'factory_memory_size_bytes',
    'Memory store size',
    ['tier'],
    registry=registry
)

# Model metrics
model_requests = Counter(
    'factory_model_requests_total',
    'Model requests',
    ['model', 'provider', 'status'],
    registry=registry
)

model_tokens = Counter(
    'factory_model_tokens_total',
    'Model tokens',
    ['model', 'provider', 'type'],  # input/output
    registry=registry
)

model_latency = Histogram(
    'factory_model_latency_seconds',
    'Model request latency',
    ['model', 'provider'],
    registry=registry
)

model_cost = Counter(
    'factory_model_cost_total',
    'Model cost in USD',
    ['model', 'provider'],
    registry=registry
)

# WebSocket metrics
ws_connections = Gauge(
    'factory_websocket_connections',
    'Active WebSocket connections',
    registry=registry
)

ws_messages = Counter(
    'factory_websocket_messages_total',
    'WebSocket messages',
    ['direction', 'type'],
    registry=registry
)

# System metrics
factory_info = Gauge(
    'factory_info',
    'Factory information',
    ['version', 'environment'],
    registry=registry
)

# Helper functions
def record_run_start(repository: str):
    runs_total.labels(status="started", repository=repository).inc()


def record_run_complete(repository: str, status: str, duration: float):
    runs_total.labels(status=status, repository=repository).inc()
    run_duration.labels(repository=repository, stage="total").observe(duration)


def record_stage_complete(stage: str, status: str, duration: float):
    stage_throughput.labels(stage=stage, status=status).inc()
    stage_cycle_time.labels(stage=stage).observe(duration)


def record_agent_execution(agent_type: str, status: str, tokens: int, cost: float, latency: float, model: str):
    agent_executions.labels(agent_type=agent_type, status=status).inc()
    agent_tokens.labels(agent_type=agent_type, model=model).inc(tokens)
    agent_cost.labels(agent_type=agent_type, model=model).inc(cost)
    agent_latency.labels(agent_type=agent_type).observe(latency)


def record_gate_evaluation(gate: str, passed: bool, latency: float):
    gate_evaluations.labels(gate=gate, result="pass" if passed else "fail").inc()
    gate_latency.labels(gate=gate).observe(latency)


def record_model_request(model: str, provider: str, success: bool, input_tokens: int, output_tokens: int, cost: float, latency: float):
    model_requests.labels(model=model, provider=provider, status="success" if success else "error").inc()
    model_tokens.labels(model=model, provider=provider, type="input").inc(input_tokens)
    model_tokens.labels(model=model, provider=provider, type="output").inc(output_tokens)
    model_cost.labels(model=model, provider=provider).inc(cost)
    model_latency.labels(model=model, provider=provider).observe(latency)


def set_factory_info(version: str, environment: str):
    factory_info.labels(version=version, environment=environment).set(1)