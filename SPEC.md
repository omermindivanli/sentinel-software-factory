# Software Factory - Technical Specification

## Vision
A local-first, production-grade software factory that automates the full SDLC using coordinated multi-agent AI loops. Inspired by Factory.com's architecture, built on proven patterns from *Agentic Design Patterns* and Anthropic's latest research.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                         SOFTWARE FACTORY (Local-First)                               │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌──────────┐  │
│  │  INTAKE     │  │  PLANNING   │  │  EXECUTION  │  │  VALIDATION │  │ RELEASE  │  │
│  │  (Triage)   │──│  (Architect)│──│  (Workers)  │──│  (Gates)    │──│  (Ship)  │  │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘  └──────────┘  │
│        │               │               │               │               │             │
│        └───────────────┼───────────────┼───────────────┼───────────────┘             │
│                        ▼               ▼               ▼                             │
│  ┌─────────────────────────────────────────────────────────────────────────────┐   │
│  │                    ORCHESTRATION ENGINE (LangGraph)                          │   │
│  │  State Machine • Checkpointing • Human Gates • Model Router • Memory Bus    │   │
│  └─────────────────────────────────────────────────────────────────────────────┘   │
│                        │               │               │                             │
│         ┌──────────────┼──────────────┼──────────────┼──────────────┐              │
│         ▼              ▼              ▼              ▼              ▼              │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐      │
│  │  SANDBOX   │ │   TOOLS    │ │   MEMORY   │ │  METRICS   │ │  DASHBOARD │      │
│  │ (Worktrees/│ │  (MCP +    │ │ (Vector +  │ │ (Prometheus│ │  (React +  │      │
│  │ Containers)│ │  Built-in) │ │  Graph +   │ │  + Grafana)│ │  WebSocket)│      │
│  └────────────┘ └────────────┘ └────────────┘ └────────────┘ └────────────┘      │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Core Components

### 1. Orchestration Engine (LangGraph-based)
- **State Machine**: Explicit states for each SDLC stage
- **Checkpointing**: Full state persistence at every step
- **Human Gates**: Approval checkpoints for critical transitions
- **Model Router**: Route tasks to optimal model (Opus/Sonnet/Haiku/local)
- **Memory Bus**: Shared context across all agents

### 2. Six SDLC Stages (Factory.com-aligned)

| Stage | Agent Role | Key Patterns | Output |
|-------|------------|--------------|--------|
| **Triage** | Classifier | Routing, Reflection | Classified, deduplicated work items |
| **Planning** | Architect | Planning, Prompt Chaining | Technical spec, task breakdown |
| **Execution** | Worker Pool | Multi-Agent, Parallelization, Tool Use | Code changes in isolated sandboxes |
| **Validation** | Reviewer + QA + Security | Guardrails, Human-in-Loop, Reflection | Pass/fail with detailed reports |
| **Release** | Release Manager | Prioritization, Monitoring | Deployed artifacts, release notes |
| **Monitor** | Incident Responder | Learning, Exploration | Root cause, auto-fix, wiki updates |

### 3. Sandbox Execution Environment
- **Git Worktrees**: Parallel, isolated branches per task
- **Docker Containers**: Full isolation for builds/tests
- **Resource Limits**: CPU, memory, network, time bounds
- **Artifact Persistence**: Build outputs, test results, logs

### 4. Tool Ecosystem (MCP + Built-in)
- **MCP Servers**: GitHub, Linear, Slack, Filesystem, Database, Browser
- **Built-in Tools**: Code search, AST parsing, test runner, linter, type checker
- **Progressive Discovery**: Load tool defs on-demand (1-5% context threshold)

### 5. Memory System (4-Tier)
| Tier | Storage | TTL | Purpose |
|------|---------|-----|---------|
| Working | In-context | Session | Active task state |
| Episodic | Vector DB (Chroma) | 30 days | Conversation history, decisions |
| Semantic | Knowledge Graph (Neo4j) | Permanent | Architecture decisions, patterns |
| Procedural | Prompt Templates | Versioned | Skills, workflows, best practices |

### 6. Observability Dashboard (Real-time)
- **Live Agent View**: WebSocket stream of agent thoughts/actions
- **Stage Metrics**: Throughput, pass rate, queue depth, cycle time
- **Health & Coverage**: Per-repo, per-stage automation status
- **Token/Cost Tracking**: Per-model, per-stage, cumulative

---

## Agent Workflow (The Loop)

```
┌────────────────────────────────────────────────────────────────┐
│                     AGENT EXECUTION LOOP                        │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐    │
│   │ GATHER  │───▶│ THINK   │───▶│  ACT    │───▶│ CHECK   │    │
│   │ CONTEXT │    │ (Think  │    │ (Tools) │    │ RESULTS │    │
│   │         │    │  Tool)  │    │         │    │         │    │
│   └─────────┘    └─────────┘    └─────────┘    └────┬────┘    │
│                                                      │         │
│         ┌────────────────────────────────────────────┘         │
│         ▼                                                      │
│   ┌─────────────┐                                              │
│   │  CONDITION  │──▶ Continue? ──▶ GATHER CONTEXT              │
│   │  MET?       │                                              │
│   └─────────────┘                                              │
│        │                                                       │
│        No                                                      │
│        ▼                                                       │
│   ┌─────────────┐                                              │
│   │  RETURN     │                                              │
│   │  RESULT     │                                              │
│   └─────────────┘                                              │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

---

## Multi-Agent Coordination Patterns

### Supervisor-Worker (Primary)
```
Supervisor (Architect)
    │
    ├──▶ Worker 1 (Backend) ──▶ Sandbox 1
    ├──▶ Worker 2 (Frontend) ──▶ Sandbox 2
    ├──▶ Worker 3 (Tests) ─────▶ Sandbox 3
    └──▶ Worker 4 (Docs) ──────▶ Sandbox 4
         │
         ▼
    Aggregator ──▶ Validation Gates
```

### Parallel Fan-Out (for independent tasks)
```
Task ──▶ [Agent₁, Agent₂, Agent₃, Agent₄, Agent₅] (parallel)
         │
         ▼
    Aggregator (merge results)
```

### Hierarchical (for complex features)
```
Feature Lead
    ├──▶ Backend Lead ──▶ [API Dev, DB Dev, Auth Dev]
    ├──▶ Frontend Lead ──▶ [UI Dev, State Dev, Test Dev]
    └──▶ DevOps Lead ──▶ [CI Dev, Deploy Dev, Monitor Dev]
```

---

## Model Routing Strategy

| Task Type | Model | Rationale |
|-----------|-------|-----------|
| Planning/Architecture | Claude Opus 4 / Sonnet 4 | Complex reasoning, large context |
| Code Generation | Claude Sonnet 4 / 3.5 Sonnet | Best code quality/speed balance |
| Code Review | Claude Sonnet 4 | Nuanced judgment |
| Test Generation | Claude 3.5 Sonnet / Haiku | Fast, repetitive |
| Documentation | Haiku / Local (Llama) | Cost-effective |
| Classification/Triage | Haiku / Local | High volume, low complexity |
| Think Tool Reasoning | Sonnet 4 (with think tool) | Sequential decisions |

---

## Validation Gates (Must Pass to Proceed)

| Gate | Checks | Blocking? |
|------|--------|-----------|
| **Pre-Execution** | Spec completeness, dependency check | Yes |
| **Code Quality** | Lint, type-check, format, complexity | Yes |
| **Tests** | Unit, integration, e2e, coverage ≥ 80% | Yes |
| **Security** | SAST, dependency scan, secrets, STRIDE | Yes |
| **Review** | AI code review + human approval (configurable) | Configurable |
| **Performance** | Benchmarks, load test (if applicable) | Warning |
| **Documentation** | AutoWiki updated, API docs current | Warning |

---

## Dashboard Requirements

### Real-Time Views
1. **Factory Overview**: All stages health, active agents, queue depth
2. **Stage Detail**: Per-stage metrics, repository coverage, recent runs
3. **Agent Live View**: Streaming thoughts, tool calls, sandbox status
4. **Repository View**: Coverage map, recent PRs, open issues
5. **Analytics**: Trends, token costs, model usage, MTTR

### Key Metrics (Factory.com-aligned)
- **Tickets Triaged** (Queue burn)
- **PR Validations** (Merge gate)
- **PRs Merged** (Ship rate)
- **Incidents Processed** (Reliability)
- **Stage Throughput** / **Pass Rate** / **Cycle Time**
- **Token Efficiency** (tokens per merged PR)

---

## Technology Stack

| Layer | Technology | Rationale |
|-------|------------|-----------|
| Orchestration | LangGraph (Python) | Production-grade, stateful, checkpointing |
| API Layer | FastAPI | Async, OpenAPI, WebSocket support |
| Dashboard | React + TypeScript + Vite | Modern, fast, typed |
| Real-time | WebSocket (native) | Low latency, bidirectional |
| Metrics | Prometheus + Grafana | Industry standard, queryable |
| Vector DB | ChromaDB | Local, persistent, easy |
| Graph DB | Neo4j (or Kuzu for embedded) | Relationships, architecture decisions |
| Sandboxing | Git worktrees + Docker | Isolation, reproducibility |
| MCP | Official SDK + custom servers | Standard, extensible |
| Models | Anthropic SDK + Ollama (local) | Multi-provider routing |

---

## Project Structure

```
software-factory/
├── SPEC.md                    # This file
├── docker-compose.yml         # Full stack
├── pyproject.toml             # Python deps
├── factory/
│   ├── __init__.py
│   ├── config/
│   │   ├── settings.py        # Pydantic settings
│   │   ├── models.yaml        # Model routing config
│   │   ├── stages.yaml        # Stage definitions
│   │   └── governance.yaml    # Allow/deny, risk tiers
│   ├── orchestration/
│   │   ├── __init__.py
│   │   ├── engine.py          # LangGraph engine
│   │   ├── state.py           # State schema
│   │   ├── checkpoints.py     # Persistence
│   │   ├── router.py          # Model router
│   │   └── memory_bus.py      # Shared context
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── base.py            # BaseAgent with Think tool
│   │   ├── triage.py          # TriageAgent
│   │   ├── architect.py       # PlanningAgent
│   │   ├── worker.py          # WorkerAgent (parametrized)
│   │   ├── reviewer.py        # CodeReviewAgent
│   │   ├── qa.py              # QAAgent
│   │   ├── security.py        # SecurityAgent
│   │   ├── release.py         # ReleaseAgent
│   │   ├── documenter.py      # AutoWikiAgent
│   │   └── monitor.py         # IncidentAgent
│   ├── sandbox/
│   │   ├── __init__.py
│   │   ├── manager.py         # SandboxManager
│   │   ├── worktree.py        # Git worktree ops
│   │   ├── container.py       # Docker ops
│   │   └── resources.py       # Limits, quotas
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── registry.py        # Tool registry
│   │   ├── mcp_client.py      # MCP client
│   │   ├── builtin/
│   │   │   ├── __init__.py
│   │   │   ├── code_search.py
│   │   │   ├── ast_tools.py
│   │   │   ├── test_runner.py
│   │   │   ├── linter.py
│   │   │   └── type_checker.py
│   │   └── progressive.py     # Progressive discovery
│   ├── memory/
│   │   ├── __init__.py
│   │   ├── vector_store.py    # Chroma wrapper
│   │   ├── graph_store.py     # Neo4j/Kuzu wrapper
│   │   ├── kv_store.py        # Redis/SQLite
│   │   └── tiered.py          # TieredMemory facade
│   ├── validation/
│   │   ├── __init__.py
│   │   ├── gates.py           # Gate definitions
│   │   ├── lint.py
│   │   ├── test.py
│   │   ├── security.py
│   │   └── review.py
│   ├── dashboard/
│   │   ├── __init__.py
│   │   ├── api/
│   │   │   ├── routes.py      # FastAPI routes
│   │   │   ├── websocket.py   # WS handlers
│   │   │   └── metrics.py     # Prometheus metrics
│   │   └── frontend/          # React app (separate build)
│   ├── integrations/
│   │   ├── __init__.py
│   │   ├── github.py
│   │   ├── linear.py
│   │   ├── slack.py
│   │   └── jira.py
│   └── cli/
│       ├── __init__.py
│       └── main.py            # Typer CLI
├── dashboard-frontend/        # React app
│   ├── package.json
│   ├── src/
│   │   ├── components/
│   │   ├── hooks/
│   │   ├── pages/
│   │   ├── services/
│   │   └── types/
│   └── vite.config.ts
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
├── docs/
│   ├── architecture.md
│   ├── getting-started.md
│   ├── configuration.md
│   ├── agent-guide.md
│   └── dashboard-guide.md
└── scripts/
    ├── setup.sh
    ├── dev.sh
    └── deploy.sh
```

---

## Implementation Phases

### Phase 1: Foundation (Week 1)
- [ ] Project scaffolding, config system
- [ ] LangGraph orchestration engine with checkpointing
- [ ] Model router with cost/latency tracking
- [ ] Tiered memory system (vector + graph + KV)
- [ ] Sandbox manager (worktrees + Docker)

### Phase 2: Core Agents (Week 2)
- [ ] BaseAgent with Think tool integration
- [ ] TriageAgent (Routing + Reflection)
- [ ] ArchitectAgent (Planning + Prompt Chaining)
- [ ] WorkerAgent pool (Multi-Agent + Parallelization)
- [ ] Tool registry + MCP client + progressive discovery

### Phase 3: Validation & Gates (Week 3)
- [ ] CodeReviewAgent (Guardrails + Reflection)
- [ ] QAAgent (Test generation + execution)
- [ ] SecurityAgent (SAST + STRIDE + dependencies)
- [ ] Validation gate engine with human checkpoints
- [ ] ReleaseAgent with deployment tracking

### Phase 4: Monitoring & Docs (Week 4)
- [ ] AutoWikiAgent (Document)
- [ ] IncidentAgent (Monitor + Learning)
- [ ] Prometheus metrics + Grafana dashboards
- [ ] WebSocket real-time streaming

### Phase 5: Dashboard (Week 5)
- [ ] React dashboard with all views
- [ ] Live agent view with thought streaming
- [ ] Stage health & coverage maps
- [ ] Repository coverage matrix

### Phase 6: Polish & Docs (Week 6)
- [ ] CLI with full command set
- [ ] Comprehensive documentation
- [ ] Example recipes (12+ starter automations)
- [ ] Integration tests, CI/CD

---

## Configuration Examples

### models.yaml
```yaml
router:
  default_provider: anthropic
  fallback_provider: ollama
  
models:
  - id: claude-opus-4
    provider: anthropic
    max_tokens: 8192
    cost_per_1k_input: 0.015
    cost_per_1k_output: 0.075
    capabilities: [planning, architecture, complex_reasoning]
    
  - id: claude-sonnet-4
    provider: anthropic
    max_tokens: 8192
    cost_per_1k_input: 0.003
    cost_per_1k_output: 0.015
    capabilities: [code_generation, review, think_tool]
    
  - id: claude-3-5-haiku
    provider: anthropic
    max_tokens: 8192
    cost_per_1k_input: 0.00025
    cost_per_1k_output: 0.00125
    capabilities: [classification, triage, docs]
    
  - id: llama-3.1-8b
    provider: ollama
    local: true
    capabilities: [simple_tasks, embeddings]
```

### stages.yaml
```yaml
stages:
  - id: triage
    name: "Triage"
    agent: triage
    description: "Classify and route inbound work"
    metrics:
      - throughput
      - backlog_depth
      - deduplication_rate
    gates:
      - pre_execution
    integrations: [github, linear, slack]
    
  - id: planning
    name: "Planning"
    agent: architect
    description: "Technical specification and task breakdown"
    metrics:
      - spec_completeness
      - task_breakdown_quality
    gates:
      - pre_execution
    human_gate: true  # Require approval for complex features
    
  - id: execution
    name: "Code Generation"
    agent: worker_pool
    description: "Implement changes in isolated sandboxes"
    parallelism: 5
    metrics:
      - lines_changed
      - files_touched
      - sandbox_success_rate
    gates:
      - code_quality
      - tests
      - security
      
  - id: validation
    name: "Validation"
    agents: [reviewer, qa, security]
    description: "Automated review, QA, and security gates"
    metrics:
      - pass_rate
      - review_volume
      - findings_by_severity
    gates:
      - review
      - human_approval  # Configurable
      
  - id: release
    name: "Release"
    agent: release
    description: "Deployment gates and shipping"
    metrics:
      - deployments
      - cycle_time
      - rollback_rate
    gates:
      - performance
      - documentation
      
  - id: document
    name: "Documentation"
    agent: documenter
    description: "AutoWiki and knowledge maintenance"
    schedule: "on_merge"
    metrics:
      - docs_updated
      - repository_coverage
      
  - id: monitor
    name: "Monitor"
    agent: incident
    description: "Incident response and agent effectiveness"
    schedule: "continuous"
    metrics:
      - incidents_processed
      - mttr
      - token_efficiency
```

### governance.yaml
```yaml
risk_tiers:
  - name: low
    repos: ["*-internal", "docs-*", "tools-*"]
    gates: [code_quality, tests]
    human_approval: false
    max_autonomy: full
    
  - name: medium
    repos: ["core-*", "api-*", "services-*"]
    gates: [code_quality, tests, security, review]
    human_approval: true
    max_autonomy: supervised
    
  - name: high
    repos: ["payments-*", "auth-*", "infra-*", "prod-*"]
    gates: [code_quality, tests, security, review, performance, human_approval]
    human_approval: true
    max_autonomy: guided
    require_dual_llm: true

command_allowlist:
  - git
  - npm
  - pip
  - poetry
  - docker
  - kubectl
  - terraform
  - pytest
  - mypy
  - ruff
  - eslint

command_denylist:
  - rm -rf
  - sudo
  - chmod 777
  - curl | bash
  - npm publish
  - git push --force

secrets_policy:
  never_in_context: true
  use_env_vars: true
  vault_integration: optional
```

---

## Success Criteria

1. **Autonomy**: Agents complete multi-step tasks without human intervention (configurable)
2. **Reliability**: ≥ 95% gate pass rate on validated PRs
3. **Speed**: < 10 min median cycle time from triage to merge for low-risk changes
4. **Observability**: Real-time visibility into every agent action
5. **Governance**: Full audit trail, least-privilege, secrets never in context
6. **Extensibility**: New stages/agents/tools added via configuration
7. **Local-First**: Runs entirely on developer machine or self-hosted

---

## Influences & References

- **Factory.com Software Factory**: Stage model, metrics, dashboard concepts
- **Agentic Design Patterns (Gulli)**: 21 patterns, all implemented
- **Anthropic Research**: 
  - Building Effective Agents (workflows vs agents)
  - Multi-Agent Research System (orchestrator-worker, parallelization)
  - Code Execution with MCP (programmatic tool calling)
  - Think Tool (sequential reasoning)
  - Effective Context Engineering (just-in-time loading)
- **MCP Spec**: Progressive discovery, security best practices
- **Frameworks**: LangGraph (orchestration), CrewAI (role patterns), AutoGen (messaging)

---

## Next Steps

1. Approve `best-agent` skill in Hermes UI (`/skills pending`)
2. Initialize project structure
3. Begin Phase 1 implementation
4. Iterate with real tasks to validate architecture