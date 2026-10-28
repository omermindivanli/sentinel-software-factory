# Software Factory

A local-first, production-grade software factory that automates the full SDLC using coordinated multi-agent AI loops. Inspired by Factory.com's architecture, built on proven patterns from *Agentic Design Patterns* and Anthropic's latest research.

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         SOFTWARE FACTORY (Local-First)                           │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────┐  │
│  │   INTAKE    │  │  PLANNING   │  │ EXECUTION   │  │ VALIDATION  │  │ RELEASE│  │
│  │  (Triage)   │──│ (Architect) │──│ (Workers)   │──│  (Gates)    │──│ (Ship) │  │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘  └────────┘  │
│        │                │                │                │                │        │
│        └───────────────┼────────────────┼────────────────┼────────────────┘        │
│                        ▼                ▼                ▼                         │
│  ┌─────────────────────────────────────────────────────────────────────────────┐   │
│  │                    ORCHESTRATION ENGINE (LangGraph)                          │   │
│  │  State Machine • Checkpointing • Human Gates • Model Router • Memory Bus    │   │
│  └─────────────────────────────────────────────────────────────────────────────┘   │
│                        │                │                │                         │
│         ┌──────────────┼──────────────┼──────────────┼──────────────┐              │
│         ▼              ▼              ▼              ▼              ▼              │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐      │
│  │  SANDBOX   │ │   TOOLS    │ │   MEMORY   │ │  METRICS   │ │  DASHBOARD │      │
│  │ (Worktrees/│ │  (MCP +    │ │ (Vector +  │ │ (Prometheus│ │  (React +  │      │
│  │ Containers)│ │  Built-in) │ │  Graph +   │ │  + Grafana)│ │  WebSocket)│      │
│  └────────────┘ └────────────┘ └────────────┘ └────────────┘ └────────────┘      │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## ✨ Features

### Six SDLC Stages (Factory.com-aligned)

| Stage | Agent | Description | Key Patterns |
|-------|-------|-------------|--------------|
| **Triage** | Classifier | Classify, deduplicate, route work | Routing, Reflection |
| **Planning** | Architect | Technical spec, task breakdown | Planning, Prompt Chaining |
| **Execution** | Worker Pool | Implement in isolated sandboxes | Multi-Agent, Parallelization, Tool Use |
| **Validation** | Reviewer + QA + Security | Code review, tests, security gates | Guardrails, Human-in-Loop, Reflection |
| **Release** | Release Manager | Deploy, smoke test, track | Prioritization, Monitoring |
| **Document** | AutoWiki | Update docs, changelogs, ADRs | Learning, Exploration |
| **Monitor** | Incident Responder | Correlate incidents, auto-remediate | Learning, Evaluation |

### Core Capabilities

- **🔒 Local-First**: Runs entirely on your machine or self-hosted - no cloud dependency
- **🤖 Multi-Agent Orchestration**: LangGraph-based state machine with checkpointing
- **🏗️ Isolated Sandboxes**: Git worktrees + Docker containers for parallel execution
- **🧠 Tiered Memory**: Working (Redis) → Episodic (ChromaDB) → Semantic (Neo4j) → Procedural (Templates)
- **🔌 MCP Integration**: Progressive tool discovery, programmatic tool calling
- **📊 Real-time Dashboard**: React + WebSocket live agent thoughts, stage metrics, run history
- **🛡️ Governance**: Risk tiers, command allow/deny lists, human approval gates, dual-LLM review
- **📈 Observability**: Prometheus metrics, Grafana dashboards, distributed tracing
- **💰 Cost Tracking**: Per-model, per-agent, per-run token and cost accounting

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- Anthropic API key (for Claude models)
- Optional: Ollama for local models

### 1. Clone and Configure

```bash
git clone <repo>
cd software-factory

# Copy environment template
cp .env.example .env

# Edit .env with your API keys
# ANTHROPIC_API_KEY=your_key_here
```

### 2. Start the Factory

```bash
# Development mode (with hot reload)
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# Production mode
docker-compose up -d
```

### 3. Access the Dashboard

- **Dashboard**: http://localhost:5173
- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Metrics**: http://localhost:9090 (Prometheus)
- **Grafana**: http://localhost:3000 (admin/factory123)

### 4. Create Your First Run

```bash
# Via API
curl -X POST http://localhost:8000/api/v1/runs \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Add user authentication",
    "description": "Implement JWT-based auth with refresh tokens",
    "repository": "myorg/myapp",
    "priority": "high"
  }'

# Or use the Dashboard UI at http://localhost:5173
```

## 📖 Documentation

- [Architecture](docs/architecture.md) - Detailed system architecture
- [Getting Started](docs/getting-started.md) - Step-by-step tutorial
- [Configuration](docs/configuration.md) - All configuration options
- [Agent Guide](docs/agent-guide.md) - Creating custom agents
- [Dashboard Guide](docs/dashboard-guide.md) - Dashboard features

## ⚙️ Configuration

### Models (`factory/config/models.yaml`)

```yaml
router:
  default_provider: anthropic
  fallback_provider: ollama
  models:
    - id: claude-opus-4
      provider: anthropic
      capabilities: [planning, architecture, complex_reasoning]
      api_key_env: ANTHROPIC_API_KEY
    - id: llama-3.1-8b
      provider: ollama
      local: true
      capabilities: [simple_tasks, embeddings]
```

### Stages (`factory/config/stages.yaml`)

```yaml
stages:
  - id: triage
    agent: triage
    parallelism: 1
    human_gate: false
    gates: [pre_execution]
  - id: execution
    agent: worker_pool
    parallelism: 5
    gates: [code_quality, tests, security]
```

### Governance (`factory/config/governance.yaml`)

```yaml
risk_tiers:
  - name: high
    repos: ["payments-*", "auth-*", "prod-*"]
    gates: [code_quality, tests, security, review, performance]
    human_approval: true
    max_autonomy: guided
    require_dual_llm: true
```

## 🤖 Creating Custom Agents

```python
from factory.agents.base import BaseAgent
from langchain_core.tools import tool

@tool
async def my_custom_tool(input: str) -> str:
    """Description of what this tool does."""
    return f"Processed: {input}"

class MyAgent(BaseAgent):
    def __init__(self, **kwargs):
        tools = [my_custom_tool]
        super().__init__(
            name="my-agent",
            agent_type="custom",
            system_prompt="You are a specialized agent...",
            tools=tools,
            **kwargs
        )
    
    async def execute(self, state: FactoryState) -> FactoryState:
        # Your agent logic here
        return await self.run_react_loop(state, "Your task prompt")
```

Register in `factory/agents/__init__.py`:

```python
AGENT_REGISTRY["custom"] = MyAgent
```

## 🔌 MCP Server Integration

Add to `settings.mcp.servers`:

```yaml
mcp:
  servers:
    github:
      command: "npx"
      args: ["-y", "@modelcontextprotocol/server-github"]
      env:
        GITHUB_TOKEN: "${GITHUB_TOKEN}"
    linear:
      command: "npx"
      args: ["-y", "@modelcontextprotocol/server-linear"]
      env:
        LINEAR_API_KEY: "${LINEAR_API_KEY}"
```

## 📊 Monitoring

### Key Metrics

- `factory_runs_total` - Total runs by status/repository
- `factory_stage_throughput_total` - Items processed per stage
- `factory_stage_pass_rate` - Gate pass rates
- `factory_agent_tokens_total` - Token usage by agent/model
- `factory_agent_cost_total` - Cost in USD
- `factory_sandbox_creations_total` - Sandbox lifecycle

### Grafana Dashboards

Pre-built dashboards in `monitoring/grafana/dashboards/`:
- Factory Overview
- Stage Health
- Agent Performance
- Cost Analysis
- Sandbox Utilization

## 🧪 Testing

```bash
# Run unit tests
pytest tests/unit -v

# Run integration tests
pytest tests/integration -v

# Run with coverage
pytest --cov=factory tests/
```

## 📁 Project Structure

```
software-factory/
├── SPEC.md                    # This specification
├── docker-compose.yml         # Production stack
├── docker-compose.dev.yml     # Development overrides
├── pyproject.toml             # Python dependencies
├── factory/
│   ├── config/                # Configuration (models, stages, governance)
│   ├── orchestration/         # LangGraph engine, state, checkpoints
│   ├── agents/                # All agent implementations
│   ├── sandbox/               # Worktree + Docker management
│   ├── tools/                 # Built-in tools + MCP client
│   ├── memory/                # Vector, graph, KV stores
│   ├── validation/            # Quality gates
│   ├── dashboard/             # FastAPI + WebSocket backend
│   └── cli/                   # Typer CLI
├── dashboard-frontend/        # React + TypeScript + Vite
├── monitoring/                # Prometheus + Grafana configs
├── tests/                     # Unit + integration tests
└── docs/                      # Documentation
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `pytest`
5. Submit a PR

## 📄 License

MIT License - see LICENSE file for details.

## 🙏 Acknowledgments

- **Factory.com** - Stage model, metrics, dashboard concepts
- **Agentic Design Patterns (Antonio Gulli)** - 21 patterns implementation
- **Anthropic Research** - Building Effective Agents, Multi-Agent Research System, Think Tool, MCP
- **LangGraph** - Production-grade orchestration
- **MCP Spec** - Progressive discovery, security best practices

## 🆘 Support

- GitHub Issues: Bug reports and feature requests
- Discussions: Architecture questions and community support
- Docs: Comprehensive guides in `/docs`