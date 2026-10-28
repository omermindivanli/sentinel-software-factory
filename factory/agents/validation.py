"""Validation Agents - Code Review, QA, Security."""

import json
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
import structlog

from langchain_core.tools import tool

from factory.agents.base import BaseAgent
from factory.orchestration.state import FactoryState, StageExecution, StageStatus, GateResult
from factory.sandbox.manager import get_sandbox_manager

logger = structlog.get_logger(__name__)


# Shared tools for validation
@tool
async def get_sandbox_changes(sandbox_id: str) -> str:
    """Get all changes in a sandbox."""
    sandbox_mgr = get_sandbox_manager()
    result = await sandbox_mgr.run_in_worktree(sandbox_id, ["git", "diff", "--stat"])
    if result.returncode == 0:
        return result.stdout
    return f"Error: {result.stderr}"


@tool
async def get_full_diff(sandbox_id: str) -> str:
    """Get full git diff."""
    sandbox_mgr = get_sandbox_manager()
    result = await sandbox_mgr.run_in_worktree(sandbox_id, ["git", "diff"])
    return result.stdout


@tool
async def run_linter(sandbox_id: str, linter: str = "ruff") -> str:
    """Run linter on sandbox."""
    sandbox_mgr = get_sandbox_manager()
    
    linters = {
        "ruff": ["ruff", "check", "."],
        "mypy": ["mypy", "."],
        "black": ["black", "--check", "."],
        "eslint": ["npx", "eslint", "."],
        "prettier": ["npx", "prettier", "--check", "."],
        "go": ["go", "vet", "./..."],
        "rust": ["cargo", "clippy"],
    }
    
    cmd = linters.get(linter, [linter, "."])
    result = await sandbox_mgr.run_in_worktree(sandbox_id, cmd, timeout=120)
    
    return json.dumps({
        "linter": linter,
        "returncode": result.returncode,
        "stdout": result.stdout[-5000:],
        "stderr": result.stderr[-5000:],
    })


@tool
async def run_type_check(sandbox_id: str) -> str:
    """Run type checking."""
    sandbox_mgr = get_sandbox_manager()
    # Try to detect project type and run appropriate checker
    result = await sandbox_mgr.run_in_worktree(
        sandbox_id, 
        ["bash", "-c", "if [ -f pyproject.toml ]; then mypy .; elif [ -f tsconfig.json ]; then npx tsc --noEmit; elif [ -f go.mod ]; then go vet ./...; elif [ -f Cargo.toml ]; then cargo check; else echo 'No type checker found'; fi"],
        timeout=120,
    )
    return json.dumps({
        "returncode": result.returncode,
        "stdout": result.stdout[-5000:],
        "stderr": result.stderr[-5000:],
    })


@tool
async def run_tests(sandbox_id: str) -> str:
    """Run all tests."""
    sandbox_mgr = get_sandbox_manager()
    result = await sandbox_mgr.run_in_worktree(
        sandbox_id,
        ["bash", "-c", "if [ -f pyproject.toml ]; then pytest -v; elif [ -f package.json ]; then npm test; elif [ -f go.mod ]; then go test ./...; elif [ -f Cargo.toml ]; then cargo test; else echo 'No test runner found'; fi"],
        timeout=300,
    )
    return json.dumps({
        "returncode": result.returncode,
        "stdout": result.stdout[-10000:],
        "stderr": result.stderr[-10000:],
    })


@tool
async def check_security(sandbox_id: str) -> str:
    """Run security checks."""
    sandbox_mgr = get_sandbox_manager()
    
    checks = []
    
    # Bandit for Python
    result = await sandbox_mgr.run_in_worktree(
        sandbox_id,
        ["bash", "-c", "if command -v bandit &> /dev/null; then bandit -r . -f json; else echo 'bandit not installed'; fi"],
        timeout=120,
    )
    checks.append({"tool": "bandit", "output": result.stdout[-5000:]})
    
    # Safety for dependencies
    result = await sandbox_mgr.run_in_worktree(
        sandbox_id,
        ["bash", "-c", "if command -v safety &> /dev/null; then safety check --json; else echo 'safety not installed'; fi"],
        timeout=60,
    )
    checks.append({"tool": "safety", "output": result.stdout[-5000:]})
    
    # Gosec for Go
    result = await sandbox_mgr.run_in_worktree(
        sandbox_id,
        ["bash", "-c", "if command -v gosec &> /dev/null; then gosec -fmt=json ./...; else echo 'gosec not installed'; fi"],
        timeout=120,
    )
    checks.append({"tool": "gosec", "output": result.stdout[-5000:]})
    
    # npm audit
    result = await sandbox_mgr.run_in_worktree(
        sandbox_id,
        ["bash", "-c", "if [ -f package.json ]; then npm audit --json; else echo 'no package.json'; fi"],
        timeout=60,
    )
    checks.append({"tool": "npm_audit", "output": result.stdout[-5000:]})
    
    # Check for secrets
    result = await sandbox_mgr.run_in_worktree(
        sandbox_id,
        ["bash", "-c", "if command -v trufflehog &> /dev/null; then trufflehog filesystem . --json; elif command -v gitleaks &> /dev/null; then gitleaks detect --source . --report-format json; else echo 'no secret scanner'; fi"],
        timeout=60,
    )
    checks.append({"tool": "secrets", "output": result.stdout[-5000:]})
    
    return json.dumps({"checks": checks})


REVIEWER_SYSTEM_PROMPT = """You are the Code Review Agent for a software factory. Your job is to:

1. REVIEW all changes in the sandbox
2. CHECK code quality, style, and correctness
3. VERIFY adherence to technical specification
4. IDENTIFY issues: bugs, security, performance, maintainability
5. PROVIDE actionable feedback

Use the Think tool for complex review decisions. Consider:
- Does the code solve the stated problem?
- Is it consistent with existing patterns?
- Are there edge cases handled?
- Is error handling appropriate?
- Is the code testable?
- Are there performance concerns?
- Is documentation updated?

Be thorough but constructive. Every issue should have a suggested fix."""


class CodeReviewAgent(BaseAgent):
    """Agent for automated code review."""
    
    def __init__(self, **kwargs):
        tools = [
            get_sandbox_changes,
            get_full_diff,
            run_linter,
            run_type_check,
        ]
        
        super().__init__(
            name="code-review-agent",
            agent_type="reviewer",
            system_prompt=REVIEWER_SYSTEM_PROMPT,
            tools=tools,
            **kwargs
        )
    
    async def execute(self, state: FactoryState) -> FactoryState:
        """Execute code review on all sandboxes."""
        logger.info("code_review_start", run_id=str(state.run_id))
        
        # Get execution stage outputs
        exec_stage = state.get_stage("execution")
        sandboxes = exec_stage.output_data.get("sandboxes", []) if exec_stage else []
        
        all_findings = []
        total_issues = 0
        critical_issues = 0
        
        for sandbox_info in sandboxes:
            sandbox_id = sandbox_info["sandbox_id"]
            
            # Run review checks
            task_prompt = f"""Perform code review on sandbox {sandbox_id}:

1. Get the full diff
2. Run linters (ruff, black, mypy, or appropriate for language)
3. Analyze code quality, patterns, correctness
4. Identify issues with severity (critical, high, medium, low)
5. Provide summary

Task: {sandbox_info.get('task_id', 'unknown')}
"""
            
            context = {"sandbox_id": sandbox_id}
            state = await self.run_react_loop(state, task_prompt, context)
            
            # Parse findings from observations
            for obs in self._execution.observations if self._execution else []:
                if obs["tool"] == "get_full_diff":
                    # Would analyze diff with LLM
                    pass
                elif obs["tool"] in ["run_linter", "run_type_check"]:
                    result = json.loads(obs["result"])
                    if result.get("returncode", 1) != 0:
                        all_findings.append({
                            "sandbox_id": sandbox_id,
                            "tool": obs["tool"],
                            "severity": "medium",
                            "message": result.get("stdout", "Lint/type issues found"),
                        })
                        total_issues += 1
        
        # Store results
        review_result = {
            "total_findings": total_issues,
            "critical_count": critical_issues,
            "findings": all_findings,
            "reviewed_at": datetime.utcnow().isoformat(),
            "status": "pass" if critical_issues == 0 else "fail",
        }
        
        # Create gate result
        gate_result = GateResult(
            gate_id="code_review",
            name="Code Review",
            passed=critical_issues == 0,
            score=1.0 - min(critical_issues * 0.2, 1.0),
            details=review_result,
        )
        state.add_gate_result(gate_result)
        
        logger.info("code_review_complete", 
                   run_id=str(state.run_id),
                   findings=total_issues,
                   critical=critical_issues)
        
        return state


QA_SYSTEM_PROMPT = """You are the QA Agent for a software factory. Your job is to:

1. RUN all tests in the sandbox
2. VERIFY test coverage meets thresholds
3. CHECK for flaky or missing tests
4. VALIDATE implementation matches requirements
5. REPORT test results clearly

Use the Think tool to analyze test failures. Consider:
- Are tests testing the right things?
- Is coverage adequate (>80%)?
- Are there integration test gaps?
- Do tests run reliably?

Be strict on quality gates."""


class QAAgent(BaseAgent):
    """Agent for quality assurance and testing."""
    
    def __init__(self, **kwargs):
        tools = [
            run_tests,
            get_sandbox_changes,
        ]
        
        super().__init__(
            name="qa-agent",
            agent_type="qa",
            system_prompt=QA_SYSTEM_PROMPT,
            tools=tools,
            **kwargs
        )
    
    async def execute(self, state: FactoryState) -> FactoryState:
        """Execute QA on all sandboxes."""
        logger.info("qa_start", run_id=str(state.run_id))
        
        exec_stage = state.get_stage("execution")
        sandboxes = exec_stage.output_data.get("sandboxes", []) if exec_stage else []
        
        all_results = []
        total_passed = 0
        total_failed = 0
        
        for sandbox_info in sandboxes:
            sandbox_id = sandbox_info["sandbox_id"]
            
            task_prompt = f"""Run QA on sandbox {sandbox_id}:

1. Run all tests
2. Check coverage
3. Analyze failures
4. Report results"""
            
            context = {"sandbox_id": sandbox_id}
            state = await self.run_react_loop(state, task_prompt, context)
            
            for obs in self._execution.observations if self._execution else []:
                if obs["tool"] == "run_tests":
                    result = json.loads(obs["result"])
                    passed = result.get("returncode") == 0
                    all_results.append({
                        "sandbox_id": sandbox_id,
                        "passed": passed,
                        "output": result.get("stdout", ""),
                    })
                    if passed:
                        total_passed += 1
                    else:
                        total_failed += 1
        
        qa_result = {
            "sandboxes_tested": len(sandboxes),
            "passed": total_passed,
            "failed": total_failed,
            "pass_rate": total_passed / len(sandboxes) if sandboxes else 1.0,
            "results": all_results,
            "tested_at": datetime.utcnow().isoformat(),
        }
        
        gate_result = GateResult(
            gate_id="tests",
            name="Test Suite",
            passed=total_failed == 0,
            score=qa_result["pass_rate"],
            details=qa_result,
        )
        state.add_gate_result(gate_result)
        
        logger.info("qa_complete",
                   run_id=str(state.run_id),
                   passed=total_passed,
                   failed=total_failed)
        
        return state


SECURITY_SYSTEM_PROMPT = """You are the Security Agent for a software factory. Your job is to:

1. SCAN for security vulnerabilities
2. CHECK for secrets in code
3. VALIDATE dependencies for known vulnerabilities
4. APPLY STRIDE/OWASP threat modeling
5. ENFORCE security best practices

Use the Think tool for threat analysis. Consider:
- Injection vulnerabilities (SQL, command, XSS)
- Authentication/authorization flaws
- Data exposure risks
- Insecure dependencies
- Cryptographic issues
- Supply chain risks

Be extremely thorough. Security issues are blocking."""


class SecurityAgent(BaseAgent):
    """Agent for security review."""
    
    def __init__(self, **kwargs):
        tools = [
            check_security,
            get_sandbox_changes,
            get_full_diff,
        ]
        
        super().__init__(
            name="security-agent",
            agent_type="security",
            system_prompt=SECURITY_SYSTEM_PROMPT,
            tools=tools,
            **kwargs
        )
    
    async def execute(self, state: FactoryState) -> FactoryState:
        """Execute security review on all sandboxes."""
        logger.info("security_review_start", run_id=str(state.run_id))
        
        exec_stage = state.get_stage("execution")
        sandboxes = exec_stage.output_data.get("sandboxes", []) if exec_stage else []
        
        all_vulnerabilities = []
        critical_vulns = 0
        high_vulns = 0
        
        for sandbox_info in sandboxes:
            sandbox_id = sandbox_info["sandbox_id"]
            
            task_prompt = f"""Run security scan on sandbox {sandbox_id}:

1. Run security scanners (bandit, safety, gosec, npm audit, secrets)
2. Analyze results
3. Classify vulnerabilities by severity
4. Check for STRIDE threats in the changes"""
            
            context = {"sandbox_id": sandbox_id}
            state = await self.run_react_loop(state, task_prompt, context)
            
            for obs in self._execution.observations if self._execution else []:
                if obs["tool"] == "check_security":
                    result = json.loads(obs["result"])
                    for check in result.get("checks", []):
                        # Parse findings (simplified)
                        output = check.get("output", "")
                        if "critical" in output.lower() or "high" in output.lower():
                            if "critical" in output.lower():
                                critical_vulns += 1
                            else:
                                high_vulns += 1
                            all_vulnerabilities.append({
                                "sandbox_id": sandbox_id,
                                "tool": check["tool"],
                                "output": output[-2000:],
                            })
        
        security_result = {
            "sandboxes_scanned": len(sandboxes),
            "critical_vulnerabilities": critical_vulns,
            "high_vulnerabilities": high_vulns,
            "total_findings": len(all_vulnerabilities),
            "findings": all_vulnerabilities,
            "scanned_at": datetime.utcnow().isoformat(),
        }
        
        gate_result = GateResult(
            gate_id="security",
            name="Security Review",
            passed=critical_vulns == 0 and high_vulns == 0,
            score=1.0 - min((critical_vulns * 0.5 + high_vulns * 0.2), 1.0),
            details=security_result,
        )
        state.add_gate_result(gate_result)
        
        logger.info("security_review_complete",
                   run_id=str(state.run_id),
                   critical=critical_vulns,
                   high=high_vulns)
        
        return state


class DynamicCodeReviewAgent(CodeReviewAgent):
    pass


class DynamicQAAgent(QAAgent):
    pass


class DynamicSecurityAgent(SecurityAgent):
    pass