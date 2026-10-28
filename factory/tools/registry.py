"""Tool registry and built-in tools for the factory."""

import asyncio
import json
import subprocess
import ast
import os
from typing import Any, Dict, List, Optional, Callable, Awaitable
from pathlib import Path
import structlog

from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)


class ToolRegistry:
    """Registry for managing available tools."""
    
    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
        self._tool_schemas: Dict[str, Dict[str, Any]] = {}
        self._categories: Dict[str, List[str]] = {}
    
    def register(
        self,
        tool: BaseTool,
        category: str = "general",
        schema: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Register a tool."""
        self._tools[tool.name] = tool
        self._tool_schemas[tool.name] = schema or self._extract_schema(tool)
        
        if category not in self._categories:
            self._categories[category] = []
        self._categories[category].append(tool.name)
        
        logger.debug("tool_registered", name=tool.name, category=category)
    
    def _extract_schema(self, tool: BaseTool) -> Dict[str, Any]:
        """Extract schema from tool."""
        return {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.args_schema.model_json_schema() if tool.args_schema else {},
        }
    
    def get(self, name: str) -> Optional[BaseTool]:
        """Get tool by name."""
        return self._tools.get(name)
    
    def get_schema(self, name: str) -> Optional[Dict[str, Any]]:
        """Get tool schema."""
        return self._tool_schemas.get(name)
    
    def list_tools(self, category: Optional[str] = None) -> List[str]:
        """List available tools."""
        if category:
            return self._categories.get(category, [])
        return list(self._tools.keys())
    
    def get_schemas(self, names: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Get schemas for tools."""
        if names is None:
            names = list(self._tools.keys())
        return [self._tool_schemas[n] for n in names if n in self._tool_schemas]
    
    def get_tools(self, names: Optional[List[str]] = None) -> List[BaseTool]:
        """Get tool instances."""
        if names is None:
            return list(self._tools.values())
        return [self._tools[n] for n in names if n in self._tools]


# Global tool registry
_tool_registry: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
    global _tool_registry
    if _tool_registry is None:
        _tool_registry = ToolRegistry()
        _register_builtin_tools(_tool_registry)
    return _tool_registry


def _register_builtin_tools(registry: ToolRegistry) -> None:
    """Register all built-in tools."""
    # Code search tools
    registry.register(search_code_tool, category="code")
    registry.register(read_file_tool, category="code")
    registry.register(write_file_tool, category="code")
    registry.register(edit_file_tool, category="code")
    registry.register(list_files_tool, category="code")
    
    # Execution tools
    registry.register(run_command_tool, category="execution")
    registry.register(run_tests_tool, category="execution")
    registry.register(run_linter_tool, category="execution")
    registry.register(run_type_check_tool, category="execution")
    
    # Git tools
    registry.register(git_diff_tool, category="git")
    registry.register(git_status_tool, category="git")
    registry.register(git_log_tool, category="git")
    
    # Analysis tools
    registry.register(analyze_complexity_tool, category="analysis")
    registry.register(find_todos_tool, category="analysis")


# ==================== Built-in Tools ====================

# Code Search Tools
class SearchCodeInput(BaseModel):
    query: str = Field(description="Search query (regex supported)")
    path: str = Field(default=".", description="Directory to search in")
    pattern: str = Field(default="*.py", description="File pattern (glob)")
    max_results: int = Field(default=50, description="Maximum results")


@tool("search_code", args_schema=SearchCodeInput)
async def search_code_tool(query: str, path: str = ".", pattern: str = "*.py", max_results: int = 50) -> str:
    """Search code using ripgrep."""
    try:
        import pathspec
        
        # Build command
        cmd = ["rg", "--json", "--max-count", str(max_results)]
        if pattern != "*.py":
            cmd.extend(["-g", pattern])
        cmd.extend([query, path])
        
        result = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        )
        
        if result.returncode not in [0, 1]:
            return f"Error: {result.stderr}"
        
        # Parse JSON output
        matches = []
        for line in result.stdout.strip().split("\n"):
            if line:
                try:
                    data = json.loads(line)
                    if data.get("type") == "match":
                        match_data = data["data"]
                        matches.append({
                            "file": match_data["path"]["text"],
                            "line": match_data["line_number"],
                            "column": match_data.get("column_number"),
                            "text": match_data["lines"]["text"].strip(),
                        })
                except json.JSONDecodeError:
                    pass
        
        return json.dumps({"matches": matches[:max_results], "count": len(matches)})
    except FileNotFoundError:
        return "Error: ripgrep (rg) not installed"
    except Exception as e:
        return f"Error: {str(e)}"


class ReadFileInput(BaseModel):
    path: str = Field(description="File path to read")
    offset: int = Field(default=0, description="Line offset (0-indexed)")
    limit: int = Field(default=200, description="Maximum lines to read")


@tool("read_file", args_schema=ReadFileInput)
async def read_file_tool(path: str, offset: int = 0, limit: int = 200) -> str:
    """Read a file with pagination."""
    try:
        file_path = Path(path)
        if not file_path.exists():
            return f"Error: File not found: {path}"
        
        content = file_path.read_text()
        lines = content.splitlines()
        
        start = offset
        end = min(offset + limit, len(lines))
        
        return json.dumps({
            "path": path,
            "total_lines": len(lines),
            "offset": offset,
            "limit": limit,
            "content": "\n".join(lines[start:end]),
        })
    except Exception as e:
        return f"Error: {str(e)}"


class WriteFileInput(BaseModel):
    path: str = Field(description="File path to write")
    content: str = Field(description="Content to write")
    create_dirs: bool = Field(default=True, description="Create parent directories")


@tool("write_file", args_schema=WriteFileInput)
async def write_file_tool(path: str, content: str, create_dirs: bool = True) -> str:
    """Write content to a file."""
    try:
        file_path = Path(path)
        if create_dirs:
            file_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_path.write_text(content)
        return json.dumps({"success": True, "path": path, "bytes": len(content)})
    except Exception as e:
        return f"Error: {str(e)}"


class EditFileInput(BaseModel):
    path: str = Field(description="File path to edit")
    old_string: str = Field(description="String to replace")
    new_string: str = Field(description="New string")
    replace_all: bool = Field(default=False, description="Replace all occurrences")


@tool("edit_file", args_schema=EditFileInput)
async def edit_file_tool(path: str, old_string: str, new_string: str, replace_all: bool = False) -> str:
    """Edit a file by replacing text."""
    try:
        file_path = Path(path)
        if not file_path.exists():
            return f"Error: File not found: {path}"
        
        content = file_path.read_text()
        
        if old_string not in content:
            return f"Error: old_string not found in file"
        
        if replace_all:
            new_content = content.replace(old_string, new_string)
            count = content.count(old_string)
        else:
            new_content = content.replace(old_string, new_string, 1)
            count = 1
        
        file_path.write_text(new_content)
        return json.dumps({"success": True, "replacements": count})
    except Exception as e:
        return f"Error: {str(e)}"


class ListFilesInput(BaseModel):
    path: str = Field(default=".", description="Directory to list")
    pattern: str = Field(default="**/*", description="Glob pattern")
    max_depth: int = Field(default=3, description="Maximum directory depth")


@tool("list_files", args_schema=ListFilesInput)
async def list_files_tool(path: str = ".", pattern: str = "**/*", max_depth: int = 3) -> str:
    """List files matching pattern."""
    try:
        base = Path(path)
        files = []
        
        for file_path in base.rglob(pattern):
            if file_path.is_file():
                # Check depth
                rel = file_path.relative_to(base)
                if len(rel.parts) <= max_depth:
                    files.append({
                        "path": str(file_path.relative_to(base)),
                        "size": file_path.stat().st_size,
                        "modified": file_path.stat().st_mtime,
                    })
        
        return json.dumps({"files": files, "count": len(files)})
    except Exception as e:
        return f"Error: {str(e)}"


# Execution Tools
class RunCommandInput(BaseModel):
    command: List[str] = Field(description="Command and arguments")
    workdir: str = Field(default=".", description="Working directory")
    timeout: int = Field(default=120, description="Timeout in seconds")
    env: Optional[Dict[str, str]] = Field(default=None, description="Environment variables")


@tool("run_command", args_schema=RunCommandInput)
async def run_command_tool(command: List[str], workdir: str = ".", timeout: int = 120, env: Optional[Dict[str, str]] = None) -> str:
    """Run a shell command."""
    try:
        merged_env = {**os.environ}
        if env:
            merged_env.update(env)
        
        def _run():
            return subprocess.run(
                command,
                cwd=workdir,
                capture_output=True,
                text=True,
                env=merged_env,
                timeout=timeout,
            )
        
        result = await asyncio.get_event_loop().run_in_executor(None, _run)
        
        return json.dumps({
            "command": command,
            "returncode": result.returncode,
            "stdout": result.stdout[-10000:],
            "stderr": result.stderr[-10000:],
        })
    except subprocess.TimeoutExpired:
        return json.dumps({"error": f"Command timed out after {timeout}s"})
    except Exception as e:
        return f"Error: {str(e)}"


class RunTestsInput(BaseModel):
    workdir: str = Field(default=".", description="Working directory")
    test_command: Optional[str] = Field(default=None, description="Override test command")
    timeout: int = Field(default=300, description="Timeout in seconds")


@tool("run_tests", args_schema=RunTestsInput)
async def run_tests_tool(workdir: str = ".", test_command: Optional[str] = None, timeout: int = 300) -> str:
    """Run tests in the project."""
    try:
        if test_command:
            cmd = test_command.split()
        else:
            # Auto-detect
            if Path(workdir, "pyproject.toml").exists() or Path(workdir, "pytest.ini").exists():
                cmd = ["pytest", "-v", "--tb=short"]
            elif Path(workdir, "package.json").exists():
                cmd = ["npm", "test"]
            elif Path(workdir, "go.mod").exists():
                cmd = ["go", "test", "./..."]
            elif Path(workdir, "Cargo.toml").exists():
                cmd = ["cargo", "test"]
            else:
                return "Error: No test configuration found"
        
        def _run():
            return subprocess.run(
                cmd,
                cwd=workdir,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        
        result = await asyncio.get_event_loop().run_in_executor(None, _run)
        
        return json.dumps({
            "command": cmd,
            "returncode": result.returncode,
            "stdout": result.stdout[-20000:],
            "stderr": result.stderr[-20000:],
        })
    except subprocess.TimeoutExpired:
        return json.dumps({"error": f"Tests timed out after {timeout}s"})
    except Exception as e:
        return f"Error: {str(e)}"


class RunLinterInput(BaseModel):
    workdir: str = Field(default=".", description="Working directory")
    linter: str = Field(default="auto", description="Linter to use (auto, ruff, eslint, etc.)")
    fix: bool = Field(default=False, description="Auto-fix issues")


@tool("run_linter", args_schema=RunLinterInput)
async def run_linter_tool(workdir: str = ".", linter: str = "auto", fix: bool = False) -> str:
    """Run code linter."""
    try:
        if linter == "auto":
            # Auto-detect
            if Path(workdir, "pyproject.toml").exists():
                linter = "ruff"
            elif Path(workdir, "package.json").exists():
                linter = "eslint"
            elif Path(workdir, "go.mod").exists():
                linter = "go"
            elif Path(workdir, "Cargo.toml").exists():
                linter = "rust"
            else:
                return "Error: Could not detect linter"
        
        linters = {
            "ruff": ["ruff", "check"] + (["--fix"] if fix else []) + ["."],
            "black": ["black"] + (["."] if not fix else ["--check", "."]),
            "eslint": ["npx", "eslint"] + (["--fix"] if fix else []) + ["."],
            "prettier": ["npx", "prettier"] + (["--write", "."] if fix else ["--check", "."]),
            "go": ["go", "vet", "./..."],
            "rust": ["cargo", "clippy"] + (["--fix"] if fix else []),
        }
        
        if linter not in linters:
            return f"Error: Unknown linter: {linter}"
        
        cmd = linters[linter]
        
        def _run():
            return subprocess.run(cmd, cwd=workdir, capture_output=True, text=True, timeout=120)
        
        result = await asyncio.get_event_loop().run_in_executor(None, _run)
        
        return json.dumps({
            "linter": linter,
            "returncode": result.returncode,
            "stdout": result.stdout[-10000:],
            "stderr": result.stderr[-10000:],
        })
    except Exception as e:
        return f"Error: {str(e)}"


class RunTypeCheckInput(BaseModel):
    workdir: str = Field(default=".", description="Working directory")


@tool("run_type_check", args_schema=RunTypeCheckInput)
async def run_type_check_tool(workdir: str = ".") -> str:
    """Run type checker."""
    try:
        # Auto-detect
        if Path(workdir, "pyproject.toml").exists():
            cmd = ["mypy", "."]
        elif Path(workdir, "tsconfig.json").exists():
            cmd = ["npx", "tsc", "--noEmit"]
        elif Path(workdir, "go.mod").exists():
            cmd = ["go", "vet", "./..."]
        elif Path(workdir, "Cargo.toml").exists():
            cmd = ["cargo", "check"]
        else:
            return "Error: No type checker configuration found"
        
        def _run():
            return subprocess.run(cmd, cwd=workdir, capture_output=True, text=True, timeout=120)
        
        result = await asyncio.get_event_loop().run_in_executor(None, _run)
        
        return json.dumps({
            "command": cmd,
            "returncode": result.returncode,
            "stdout": result.stdout[-10000:],
            "stderr": result.stderr[-10000:],
        })
    except Exception as e:
        return f"Error: {str(e)}"


# Git Tools
@tool("git_diff")
async def git_diff_tool(path: str = ".", staged: bool = False) -> str:
    """Get git diff."""
    try:
        cmd = ["git", "diff"]
        if staged:
            cmd.append("--cached")
        
        def _run():
            return subprocess.run(cmd, cwd=path, capture_output=True, text=True)
        
        result = await asyncio.get_event_loop().run_in_executor(None, _run)
        return result.stdout
    except Exception as e:
        return f"Error: {str(e)}"


@tool("git_status")
async def git_status_tool(path: str = ".") -> str:
    """Get git status."""
    try:
        def _run():
            return subprocess.run(["git", "status", "--porcelain"], cwd=path, capture_output=True, text=True)
        
        result = await asyncio.get_event_loop().run_in_executor(None, _run)
        return result.stdout
    except Exception as e:
        return f"Error: {str(e)}"


@tool("git_log")
async def git_log_tool(path: str = ".", limit: int = 20) -> str:
    """Get git log."""
    try:
        def _run():
            return subprocess.run(
                ["git", "log", f"-{limit}", "--oneline", "--decorate"],
                cwd=path, capture_output=True, text=True
            )
        
        result = await asyncio.get_event_loop().run_in_executor(None, _run)
        return result.stdout
    except Exception as e:
        return f"Error: {str(e)}"


# Analysis Tools
@tool("analyze_complexity")
async def analyze_complexity_tool(path: str = ".", language: str = "python") -> str:
    """Analyze code complexity."""
    try:
        if language == "python":
            # Use radon if available
            def _run():
                return subprocess.run(
                    ["radon", "cc", "-s", "-a", path],
                    capture_output=True, text=True
                )
            
            result = await asyncio.get_event_loop().run_in_executor(None, _run)
            return result.stdout
        else:
            return f"Complexity analysis not implemented for {language}"
    except FileNotFoundError:
        return "Error: radon not installed"
    except Exception as e:
        return f"Error: {str(e)}"


@tool("find_todos")
async def find_todos_tool(path: str = ".", pattern: str = "TODO|FIXME|HACK|BUG") -> str:
    """Find TODO/FIXME comments."""
    try:
        def _run():
            return subprocess.run(
                ["rg", "-n", pattern, path],
                capture_output=True, text=True
            )
        
        result = await asyncio.get_event_loop().run_in_executor(None, _run)
        
        if result.returncode in [0, 1]:
            return result.stdout
        return f"Error: {result.stderr}"
    except Exception as e:
        return f"Error: {str(e)}"


# Progressive Discovery
class ProgressiveToolDiscovery:
    """Implements progressive tool discovery for MCP."""
    
    def __init__(self, registry: ToolRegistry, context_threshold: float = 0.03):
        self.registry = registry
        self.context_threshold = context_threshold
        self._loaded_tools: set = set()
        self._search_tool = self._create_search_tool()
    
    def _create_search_tool(self) -> BaseTool:
        @tool("search_tools")
        async def search_tools(query: str) -> str:
            """Search for available tools by keyword."""
            all_tools = self.registry.list_tools()
            # Simple keyword matching
            matches = [t for t in all_tools if query.lower() in t.lower()]
            schemas = self.registry.get_schemas(matches)
            return json.dumps({"tools": schemas})
        
        return search_tools
    
    def should_load_all(self, estimated_tokens: int, context_window: int = 128000) -> bool:
        """Check if we should load all tool definitions."""
        return (estimated_tokens / context_window) < self.context_threshold
    
    def get_available_tools(self, force_all: bool = False) -> List[BaseTool]:
        """Get tools to load into context."""
        if force_all or self.should_load_all(len(self._loaded_tools) * 500):
            return list(self.registry._tools.values())
        else:
            # Return search tool + already loaded
            tools = [self._search_tool]
            tools.extend(self.registry.get_tools(list(self._loaded_tools)))
            return tools
    
    def mark_loaded(self, tool_names: List[str]) -> None:
        """Mark tools as loaded."""
        self._loaded_tools.update(tool_names)


# Global progressive discovery
_progressive_discovery: Optional[ProgressiveToolDiscovery] = None


def get_progressive_discovery() -> ProgressiveToolDiscovery:
    global _progressive_discovery
    if _progressive_discovery is None:
        _progressive_discovery = ProgressiveToolDiscovery(get_tool_registry())
    return _progressive_discovery