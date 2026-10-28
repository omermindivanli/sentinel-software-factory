"""Factory CLI - Command line interface for the Software Factory."""

import asyncio
import json
from pathlib import Path
from typing import Optional
import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.syntax import Syntax

from factory.config.settings import settings
from factory.orchestration.engine import initialize_engine, get_engine
from factory.orchestration.state import WorkItem, TaskPriority
from factory.memory.tiered import initialize_tiered_memory
from factory.tools.mcp_client import initialize_mcp_client

app = typer.Typer(
    name="factory",
    help="Software Factory CLI - Local-first SDLC automation",
    add_completion=False,
)

console = Console()


@app.callback()
def callback():
    """Software Factory - Local-first SDLC automation with multi-agent orchestration."""
    pass


@app.command()
def init(
    project_path: Path = typer.Argument(Path.cwd(), help="Project directory"),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing config"),
):
    """Initialize a new factory project."""
    console.print(Panel.fit("🏭 Initializing Software Factory", style="bold blue"))
    
    config_dir = project_path / "factory" / "config"
    if config_dir.exists() and not force:
        console.print("[yellow]Config already exists. Use --force to overwrite.[/yellow]")
        raise typer.Exit(1)
    
    config_dir.mkdir(parents=True, exist_ok=True)
    
    # Copy default configs
    import shutil
    source_config = Path(__file__).parent / "config"
    if source_config.exists():
        for config_file in source_config.glob("*.yaml"):
            shutil.copy2(config_file, config_dir / config_file.name)
    
    console.print(f"[green]✓[/green] Initialized factory in {project_path}")


@app.command()
def run(
    title: str = typer.Argument(..., help="Work item title"),
    description: str = typer.Argument(..., help="Work item description"),
    repository: str = typer.Option(..., "--repo", "-r", help="Repository name"),
    branch: str = typer.Option("main", "--branch", "-b", help="Base branch"),
    priority: str = typer.Option("medium", "--priority", "-p", help="Priority (low/medium/high/critical)"),
    source: str = typer.Option("cli", "--source", "-s", help="Source identifier"),
    watch: bool = typer.Option(True, "--watch/--no-watch", help="Watch progress in real-time"),
):
    """Execute a factory run."""
    
    async def _run():
        # Initialize systems
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Initializing factory...", total=None)
            
            await initialize_tiered_memory()
            await initialize_mcp_client()
            engine = await initialize_engine()
            
            progress.update(task, description="Creating work item...")
            
            work_item = WorkItem(
                title=title,
                description=description,
                source="cli",
                source_id=f"cli-{description[:20]}",
                repository=repository,
                branch=branch,
                priority=TaskPriority(priority.lower()),
            )
            
            progress.update(task, description="Executing factory run...")
            
            state = await engine.run(work_item)
            
            progress.update(task, description="Complete!", completed=True)
        
        # Display results
        _display_run_results(state)
        
        if watch and state.overall_status == "running":
            console.print("[yellow]Run still in progress. Use 'factory status <run_id>' to check.[/yellow]")
    
    asyncio.run(_run())


@app.command()
def status(
    run_id: str = typer.Argument(..., help="Run ID"),
    watch: bool = typer.Option(False, "--watch", "-w", help="Watch for updates"),
):
    """Check status of a factory run."""
    
    async def _status():
        engine = get_engine()
        state = await engine.get_state(run_id)
        
        if not state:
            console.print(f"[red]Run {run_id} not found[/red]")
            raise typer.Exit(1)
        
        _display_run_results(state)
        
        if watch and state.overall_status == "running":
            console.print("[yellow]Watching for updates... (Ctrl+C to stop)[/yellow]")
            # Would implement real-time updates here
    
    asyncio.run(_status())


@app.command()
def list(
    limit: int = typer.Option(20, "--limit", "-l", help="Number of runs to show"),
    status_filter: Optional[str] = typer.Option(None, "--status", "-s", help="Filter by status"),
):
    """List recent factory runs."""
    
    async def _list():
        engine = get_engine()
        runs = await engine.list_runs(limit=limit)
        
        if status_filter:
            runs = [r for r in runs if r.get("overall_status") == status_filter]
        
        table = Table(title=f"Recent Factory Runs (limit: {limit})")
        table.add_column("Run ID", style="cyan", no_wrap=True)
        table.add_column("Title", style="white")
        table.add_column("Repository", style="green")
        table.add_column("Status", style="yellow")
        table.add_column("Cost", style="magenta")
        table.add_column("Updated", style="blue")
        
        for run in runs:
            run_id = run.get("run_id", "")[:8]
            title = run.get("work_item", {}).get("title", "Unknown")[:50]
            repo = run.get("work_item", {}).get("repository", "Unknown")
            status = run.get("overall_status", "unknown")
            cost = run.get("metrics", {}).get("total_cost", 0)
            updated = run.get("updated_at", "")[:19].replace("T", " ")
            
            status_style = {
                "completed": "green",
                "running": "yellow",
                "failed": "red",
                "paused": "blue",
            }.get(status, "white")
            
            table.add_row(
                run_id,
                title,
                repo,
                f"[{status_style}]{status}[/{status_style}]",
                f"${cost:.4f}",
                updated,
            )
        
        console.print(table)
    
    asyncio.run(_list())


@app.command()
def approve(
    run_id: str = typer.Argument(..., help="Run ID"),
    checkpoint_id: str = typer.Argument(..., help="Checkpoint ID"),
    approver: str = typer.Option("cli-user", "--approver", "-a", help="Approver name"),
):
    """Approve a human checkpoint."""
    
    async def _approve():
        engine = get_engine()
        await engine.approve_checkpoint(checkpoint_id, approver)
        console.print(f"[green]✓[/green] Checkpoint {checkpoint_id} approved for run {run_id}")
    
    asyncio.run(_approve())


@app.command()
def reject(
    run_id: str = typer.Argument(..., help="Run ID"),
    checkpoint_id: str = typer.Argument(..., help="Checkpoint ID"),
    approver: str = typer.Option("cli-user", "--approver", "-a", help="Approver name"),
):
    """Reject a human checkpoint."""
    
    async def _reject():
        engine = get_engine()
        await engine.reject_checkpoint(checkpoint_id, approver)
        console.print(f"[red]✗[/red] Checkpoint {checkpoint_id} rejected for run {run_id}")
    
    asyncio.run(_reject())


@app.command()
def config(
    show: bool = typer.Option(False, "--show", help="Show current configuration"),
    validate: bool = typer.Option(False, "--validate", help="Validate configuration"),
):
    """Manage factory configuration."""
    
    if show:
        console.print(Panel("Factory Configuration", style="bold blue"))
        
        # Models
        table = Table(title="Models")
        table.add_column("ID")
        table.add_column("Provider")
        table.add_column("Capabilities")
        table.add_column("Local")
        
        for model in settings.router.models:
            table.add_row(
                model.id,
                model.provider,
                ", ".join(model.capabilities),
                "✓" if model.local else "✗",
            )
        console.print(table)
        
        # Stages
        table = Table(title="Stages")
        table.add_column("ID")
        table.add_column("Name")
        table.add_column("Agent")
        table.add_column("Parallelism")
        table.add_column("Human Gate")
        
        for stage in settings.stages:
            table.add_row(
                stage.id,
                stage.name,
                stage.agent,
                str(stage.parallelism),
                "✓" if stage.human_gate else "✗",
            )
        console.print(table)
        
        # Governance
        table = Table(title="Risk Tiers")
        table.add_column("Name")
        table.add_column("Patterns")
        table.add_column("Gates")
        table.add_column("Human Approval")
        table.add_column("Max Autonomy")
        
        for tier in settings.governance.risk_tiers:
            table.add_row(
                tier.name,
                ", ".join(tier.repos),
                ", ".join(tier.gates),
                "✓" if tier.human_approval else "✗",
                tier.max_autonomy,
            )
        console.print(table)
    
    if validate:
        console.print("[green]✓[/green] Configuration valid")


@app.command()
def dashboard(
    port: int = typer.Option(5173, "--port", "-p", help="Dashboard port"),
    host: str = typer.Option("0.0.0.0", "--host", "-h", help="Dashboard host"),
):
    """Start the dashboard server."""
    import uvicorn
    console.print(f"[green]Starting dashboard on http://{host}:{port}[/green]")
    uvicorn.run(
        "factory.dashboard.api.routes:app",
        host=host,
        port=port,
        reload=True,
    )


@app.command()
def test(
    path: str = typer.Option("tests", "--path", help="Test path"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
):
    """Run tests."""
    import pytest
    args = [path]
    if verbose:
        args.append("-v")
    pytest.main(args)


def _display_run_results(state):
    """Display run results in a nice format."""
    console.print(Panel.fit(
        f"Run: {state.run_id}\n"
        f"Work Item: {state.work_item.title}\n"
        f"Repository: {state.work_item.repository}\n"
        f"Status: [bold]{state.overall_status}[/bold]\n"
        f"Total Cost: ${state.total_cost:.4f}\n"
        f"Total Tokens: {state.total_tokens:,}",
        title="Factory Run Results",
        style="green" if state.overall_status == "completed" else "yellow" if state.overall_status == "running" else "red",
    ))
    
    # Stages table
    table = Table(title="Stage Execution")
    table.add_column("Stage", style="cyan")
    table.add_column("Status", style="yellow")
    table.add_column("Started")
    table.add_column("Completed")
    table.add_column("Duration")
    
    for stage_id, stage in state.stages.items():
        started = stage.started_at[:19].replace("T", " ") if stage.started_at else "-"
        completed = stage.completed_at[:19].replace("T", " ") if stage.completed_at else "-"
        
        duration = "-"
        if stage.started_at and stage.completed_at:
            from datetime import datetime
            dur = datetime.fromisoformat(stage.completed_at) - datetime.fromisoformat(stage.started_at)
            duration = str(dur).split(".")[0]
        
        status_style = {
            "completed": "green",
            "running": "yellow",
            "failed": "red",
            "waiting_human": "blue",
            "pending": "white",
        }.get(stage.status.value, "white")
        
        table.add_row(
            stage_id,
            f"[{status_style}]{stage.status.value}[/{status_style}]",
            started,
            completed,
            duration,
        )
    
    console.print(table)
    
    # Gates
    if state.gate_results:
        table = Table(title="Validation Gates")
        table.add_column("Gate")
        table.add_column("Status")
        table.add_column("Score")
        
        for gate in state.gate_results:
            table.add_row(
                gate.name,
                "✓ Passed" if gate.passed else "✗ Failed",
                f"{gate.score:.1%}" if gate.score else "N/A",
            )
        console.print(table)
    
    # Checkpoints
    if state.checkpoints:
        table = Table(title="Human Checkpoints")
        table.add_column("Stage")
        table.add_column("Title")
        table.add_column("Status")
        table.add_column("Approvers")
        
        for cp in state.checkpoints:
            table.add_row(
                cp.stage_id,
                cp.title,
                cp.status,
                ", ".join(cp.approvers) if cp.approvers else "pending",
            )
        console.print(table)


if __name__ == "__main__":
    app()