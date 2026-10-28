# Software Factory architecture review

This review compares the repository at `codex/factory-hardening` with the intended local-first, ticket-to-PR factory, the supplied architecture sketch, Factory's public Software Factory documentation, and the patterns in Antonio Gulli's *Agentic Design Patterns*.

## What this product is today

The repository is a Python/FastAPI + LangGraph prototype with a React dashboard, YAML policy, agent classes, SQLite checkpoints, optional memory services, and Docker/Podman sandbox managers. It has the right broad lifecycle boundaries, but the code and README describe more complete coverage than is currently implemented. The application code here does not identify or configure Hermes Agent or Nemotron 3 550B: `pyproject.toml`, model configuration, and the agent base class currently describe LangGraph/LangChain and Anthropic/Ollama. If Hermes and Nemotron are the external runtime used to launch this repository, that integration boundary is not represented in this source tree.

## High-risk correctness issues addressed in this branch

- The orchestration graph registered two conditional transitions for the same pre-execution node, ran pre-execution checks before planning, and looped human approval back through the whole graph. It now has one ordered path, one decision per gate, and a checkpoint decision that continues at release only after approval.
- Missing gate handlers previously meant implicit success. Gates now use the gate registry and fail closed when no implementation or result exists.
- Security review and code review previously reported success when no agent result existed. Those paths now fail. Performance checks are explicitly marked unevaluated and non-blocking rather than represented as completed checks.
- The engine marked every normally returned run completed, including states already failed by a gate. It now preserves the graph's failed or cancelled result.
- Gate retry loops were unbounded and reset their counter when a stage reran. Retries now respect the stage's configured retry limit.
- The graph created a hard-coded LangGraph SQLite saver through an unmanaged context manager, while the application already has a durable `CheckpointStore`. This branch uses the existing store as the source of truth and removes the unmanaged saver.
- Validation startup registered only the code reviewer even though QA and security agents exist. The validation stage now runs all three registered agents in sequence so their results are available to gates.
- Checkpoint approval could race with message subscription. The subscriber is installed before the pending checkpoint is exposed in the durable store.

## Architecture assessment

| Area | Assessment | Next improvement |
|---|---|---|
| Intake and triage | Agent exists, but no durable source connector, webhook signature verification, deduplication store, or idempotency key is visible. | Add authenticated, replay-safe source adapters and make source event IDs unique per repository. |
| Planning | Architect and task breakdown exist. The pre-execution gate relies on generated tasks and a local `repo_path`, but there is no consistent repository workspace contract in the API. | Define a run manifest with repo identity, immutable base revision, task dependencies, acceptance criteria, and allowed actions. |
| Execution | Worker pool and sandbox abstractions exist. Governance allow/deny lists are configuration, not a complete enforcement boundary; worker tools can invoke arbitrary commands. | Enforce command policy at the sandbox boundary, scope filesystem/network access, and record every command and artifact. Default network access should be off unless a task needs it. |
| Validation | Code, QA, and security agents are present, but underlying tool implementations are largely model-directed and not independently attested. | Make deterministic test/lint/scanner exit codes the gate evidence; keep model review advisory unless a policy says otherwise. Store evidence and tool versions with each gate result. |
| Human control and release | Checkpoints exist, but the API waits synchronously for up to an hour and does not provide a durable resume endpoint after process restart. The release agent's deployment/merge boundary needs a product policy. | Persist approval state and resume from it; require explicit per-repository policy for creating PRs, merging, deployment, and rollback. Default to opening a PR, never merging or deploying autonomously. |
| State and recovery | SQLite state snapshots exist, but no distributed queue/lease, run deduplication, cancellation, or robust restart reconciliation is implemented. | Make runs idempotent, add lease/heartbeat ownership and cancellation, and resume from durable stage boundaries after restart. |
| Memory | Redis, Chroma, and graph storage are optional-shaped components, but no retention enforcement, provenance model, or tenant/repository isolation contract is apparent. | Start with run-scoped durable state and explicit retention; add retrieval only with source citations, permission filters, and measured value. |
| Observability | Prometheus counters exist, but overview and stage endpoints return placeholders; the overview computes success rate from timestamps rather than terminal statuses. | Derive metrics from persisted run/stage/gate events and label unknown/unavailable separately from zero. Track cost, queue age, retries, gate evidence, and PR outcomes. |
| Product dashboard | Factory-like coverage map is a useful direction, but current UI has a no-op New Run button and reports placeholder health/throughput. | Make setup gaps actionable: integrations connected, repositories covered, required gates configured, most recent run health, and links to automation evidence. |
| Security and operations | CORS is open with credentials, default database credentials are in configuration, and API routes have no visible authentication or authorization layer. | Before exposing beyond loopback, require auth, CSRF-safe browser access, secret management, audit trails, and restrictive CORS. Bind local deployments to loopback by default. |

## Pattern fit from *Agentic Design Patterns*

The repository already names prompt chaining, routing, parallelization, reflection, tool use, planning, and multi-agent collaboration. The reliability patterns need to drive concrete control flow, not just agent prompts:

- **Planning and routing:** persist structured task plans and explicit gate transitions; do not rely on duplicated graph edges or implicit continuation.
- **Reflection:** use bounded, evidence-based repair cycles. The branch adds a retry limit; the next step is to feed exact failed gate evidence to the worker and stop on the configured budget.
- **Tool use and guardrails:** all tool execution should pass a single policy-enforcing sandbox boundary. A prompt instruction or YAML command list alone is not enforcement.
- **Human-in-the-loop:** approval must be an explicit durable event; timeouts and rejection must never become approval. This branch fixes the approval race and graph handoff, but restart-safe resume remains open.
- **Exception handling and evaluation:** missing tools, missing test evidence, and failed security/review should be visible failures. The product needs stage-level outcome and quality evaluation before claiming automation effectiveness.
- **Multi-agent and parallelization:** parallelize only independent tasks with separate worktrees and explicit dependency edges. Current sequential validation avoids concurrent mutation of shared state; future parallel validation should return immutable results for one aggregator to persist.

The supplied 19 MB PDF could not be opened by the browser fetcher because of its size. I used the publisher's book page to verify the pattern coverage and chapter structure; it describes 21 patterns, including guardrails, exception recovery, human-in-the-loop, resource-aware optimization, and evaluation. See [Springer book page](https://link.springer.com/book/10.1007/978-3-032-01402-3).

## Factory product comparison

Factory's published overview describes a coverage view across Triage, Code-gen, Validate, Release, Document, and Monitor, with repository/integration coverage, stage health, setup gaps, time filters, and real automation metrics. Its Triage guide also calls out classification, duplicate reduction, routing, backlog, throughput, and cycle time. This repository has stage names and a dashboard shell, but not yet the operational inventory or truthful metrics needed to provide that product experience. Relevant sources: [Software Factory overview](https://docs.factory.com/software-factory/overview), [Triage](https://docs.factory.com/software-factory/triage), and [Custom Automations](https://docs.factory.com/software-factory/automations).

The supplied sketch's Neon inbox/events/live updates and Vercel board are illustrative. They are not reasons to add Neon, Vercel, Linear, Slack, or GitHub as dependencies. Keep the current local stack; implement equivalent event persistence, status streaming, and coverage data using the repository's existing components and explicit provider interfaces.

## Recommended sequence

1. Finish hardening run/gate behavior and define a regression suite for all graph branches, retries, approval, cancellation, and restart.
2. Build the repository/run manifest, real sandbox policy enforcement, and deterministic validation evidence.
3. Replace placeholder metrics with queries over persisted lifecycle events and expose repository/integration coverage.
4. Implement durable, idempotent intake adapters and PR creation with human-controlled merge/deploy policies.
5. Add restart-safe checkpoints, cancellation, worker leases, and integration-level recovery before claiming always-on operation.
6. Add measurable evaluation datasets for ticket routing, change correctness, test quality, security findings, false positives, cost, and PR acceptance; tune Nemotron/Hermes at the harness boundary once that runtime integration is present in this codebase.
