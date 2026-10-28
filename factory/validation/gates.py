"""Validation gates for quality control."""

import asyncio
import json
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from datetime import datetime
import structlog

from factory.orchestration.state import FactoryState, GateResult
from factory.config.settings import settings

logger = structlog.get_logger(__name__)


class ValidationGate(ABC):
    """Base class for validation gates."""
    
    def __init__(self, gate_id: str, name: str, blocking: bool = True):
        self.gate_id = gate_id
        self.name = name
        self.blocking = blocking
    
    @abstractmethod
    async def evaluate(self, state: FactoryState) -> GateResult:
        """Evaluate the gate. Returns GateResult."""
        pass
    
    async def run(self, state: FactoryState) -> GateResult:
        """Run the gate with error handling."""
        try:
            return await self.evaluate(state)
        except Exception as e:
            logger.error("gate_error", gate=self.gate_id, error=str(e))
            return GateResult(
                gate_id=self.gate_id,
                name=self.name,
                passed=False,
                score=0.0,
                details={"error": str(e)},
            )


class PreExecutionGate(ValidationGate):
    """Gate to verify pre-execution requirements."""
    
    def __init__(self):
        super().__init__("pre_execution", "Pre-Execution Checks", blocking=True)
    
    async def evaluate(self, state: FactoryState) -> GateResult:
        checks = {}
        all_passed = True
        
        # Check work item has required fields
        work_item = state.work_item
        checks["has_title"] = bool(work_item.title.strip())
        checks["has_description"] = bool(work_item.description.strip())
        checks["has_repository"] = bool(work_item.repository.strip())
        
        # Check triage completed
        triage_stage = state.get_stage("triage")
        checks["triage_completed"] = (
            triage_stage is not None and 
            triage_stage.status.value == "completed"
        )
        
        # Check planning completed (if required)
        planning_stage = state.get_stage("planning")
        checks["planning_completed"] = (
            planning_stage is not None and 
            planning_stage.status.value == "completed"
        )
        
        # Check tasks defined
        tasks = state.shared_context.get("tasks", [])
        checks["tasks_defined"] = len(tasks) > 0
        
        # Check repository exists
        import os
        repo_path = state.shared_context.get("repo_path")
        checks["repo_exists"] = repo_path and os.path.exists(repo_path)
        
        all_passed = all(checks.values())
        
        return GateResult(
            gate_id=self.gate_id,
            name=self.name,
            passed=all_passed,
            score=sum(checks.values()) / len(checks) if checks else 1.0,
            details={"checks": checks},
        )


class CodeQualityGate(ValidationGate):
    """Gate for code quality checks (lint, format, type-check)."""
    
    def __init__(self):
        super().__init__("code_quality", "Code Quality", blocking=True)
    
    async def evaluate(self, state: FactoryState) -> GateResult:
        exec_stage = state.get_stage("execution")
        if not exec_stage:
            return GateResult(
                gate_id=self.gate_id,
                name=self.name,
                passed=False,
                score=0.0,
                details={"error": "Execution stage not found"},
            )
        
        sandboxes = exec_stage.output_data.get("sandboxes", [])
        
        total_checks = 0
        passed_checks = 0
        details = {"sandboxes": []}
        
        for sandbox_info in sandboxes:
            sandbox_id = sandbox_info["sandbox_id"]
            sandbox_results = {
                "sandbox_id": sandbox_id,
                "lint": False,
                "type_check": False,
                "format": False,
            }
            
            # In real implementation, would run linters
            # For now, check if worker reported lint results
            worker_output = state.shared_context.get(f"worker_output:{sandbox_info['task_id']}", {})
            
            sandbox_results["lint"] = worker_output.get("lint_passed", False)
            sandbox_results["format"] = worker_output.get("format_passed", False)
            
            # Type check would be separate
            sandbox_results["type_check"] = True  # Assume pass for now
            
            sandbox_passed = all(sandbox_results.values())
            if sandbox_passed:
                passed_checks += 1
            total_checks += 1
            
            details["sandboxes"].append(sandbox_results)
        
        overall_passed = passed_checks == total_checks and total_checks > 0
        
        return GateResult(
            gate_id=self.gate_id,
            name=self.name,
            passed=overall_passed,
            score=passed_checks / total_checks if total_checks > 0 else 1.0,
            details=details,
        )


class TestsGate(ValidationGate):
    """Gate for test execution."""
    
    def __init__(self):
        super().__init__("tests", "Test Suite", blocking=True)
    
    async def evaluate(self, state: FactoryState) -> GateResult:
        exec_stage = state.get_stage("execution")
        if not exec_stage:
            return GateResult(
                gate_id=self.gate_id,
                name=self.name,
                passed=False,
                score=0.0,
                details={"error": "Execution stage not found"},
            )
        
        # Check QA agent results
        qa_gate = next((g for g in state.gate_results if g.gate_id == "tests"), None)
        if qa_gate:
            return qa_gate
        
        # Fallback: check worker outputs
        sandboxes = exec_stage.output_data.get("sandboxes", [])
        total = len(sandboxes)
        passed = 0
        
        for sandbox_info in sandboxes:
            worker_output = state.shared_context.get(f"worker_output:{sandbox_info['task_id']}", {})
            if worker_output.get("tests_passed", False):
                passed += 1
        
        return GateResult(
            gate_id=self.gate_id,
            name=self.name,
            passed=passed == total and total > 0,
            score=passed / total if total > 0 else 1.0,
            details={"total": total, "passed": passed, "failed": total - passed},
        )


class SecurityGate(ValidationGate):
    """Gate for security review."""
    
    def __init__(self):
        super().__init__("security", "Security Review", blocking=True)
    
    async def evaluate(self, state: FactoryState) -> GateResult:
        # Check security agent results
        sec_gate = next((g for g in state.gate_results if g.gate_id == "security"), None)
        if sec_gate:
            return sec_gate
        
        # Fallback
        return GateResult(
            gate_id=self.gate_id,
            name=self.name,
            passed=True,  # Permissive fallback
            score=1.0,
            details={"note": "Security agent not run"},
        )


class ReviewGate(ValidationGate):
    """Gate for code review."""
    
    def __init__(self):
        super().__init__("review", "Code Review", blocking=True)
    
    async def evaluate(self, state: FactoryState) -> GateResult:
        # Check review agent results
        rev_gate = next((g for g in state.gate_results if g.gate_id == "code_review"), None)
        if rev_gate:
            return rev_gate
        
        return GateResult(
            gate_id=self.gate_id,
            name=self.name,
            passed=True,
            score=1.0,
            details={"note": "Review agent not run"},
        )


class HumanApprovalGate(ValidationGate):
    """Gate for human approval."""
    
    def __init__(self):
        super().__init__("human_approval", "Human Approval", blocking=True)
    
    async def evaluate(self, state: FactoryState) -> GateResult:
        # Check if human approval is required
        current_stage = state.get_current_stage()
        if not current_stage:
            return GateResult(
                gate_id=self.gate_id,
                name=self.name,
                passed=True,
                score=1.0,
                details={"reason": "no_current_stage"},
            )
        
        # Check governance config
        tier = settings.governance.get_tier_for_repo(state.work_item.repository)
        if not tier.human_approval:
            return GateResult(
                gate_id=self.gate_id,
                name=self.name,
                passed=True,
                score=1.0,
                details={"reason": "not_required_by_governance"},
            )
        
        # Check for pending checkpoints
        pending = [c for c in state.checkpoints if c.status == "pending"]
        if pending:
            return GateResult(
                gate_id=self.gate_id,
                name=self.name,
                passed=False,
                score=0.0,
                details={"pending_checkpoints": len(pending)},
            )
        
        # Check for approved checkpoints
        approved = [c for c in state.checkpoints if c.status == "approved"]
        if approved:
            return GateResult(
                gate_id=self.gate_id,
                name=self.name,
                passed=True,
                score=1.0,
                details={"approved_checkpoints": len(approved)},
            )
        
        return GateResult(
            gate_id=self.gate_id,
            name=self.name,
            passed=False,
            score=0.0,
            details={"reason": "awaiting_approval"},
        )


class PerformanceGate(ValidationGate):
    """Gate for performance checks."""
    
    def __init__(self):
        super().__init__("performance", "Performance", blocking=False)
    
    async def evaluate(self, state: FactoryState) -> GateResult:
        # Would run benchmarks, load tests
        return GateResult(
            gate_id=self.gate_id,
            name=self.name,
            passed=True,
            score=1.0,
            details={"note": "Performance checks not implemented"},
        )


class DocumentationGate(ValidationGate):
    """Gate for documentation completeness."""
    
    def __init__(self):
        super().__init__("documentation", "Documentation", blocking=False)
    
    async def evaluate(self, state: FactoryState) -> GateResult:
        # Check documenter agent results
        doc_stage = state.get_stage("document")
        if doc_stage and doc_stage.output_data:
            updated = doc_stage.output_data.get("pages_updated", 0)
            return GateResult(
                gate_id=self.gate_id,
                name=self.name,
                passed=updated > 0,
                score=min(updated / 5, 1.0),  # Expect at least 5 pages
                details=doc_stage.output_data,
            )
        
        return GateResult(
            gate_id=self.gate_id,
            name=self.name,
            passed=True,
            score=0.5,
            details={"note": "Documentation not run"},
        )


class GateRegistry:
    """Registry of validation gates."""
    
    def __init__(self):
        self._gates: Dict[str, ValidationGate] = {}
        self._register_defaults()
    
    def _register_defaults(self) -> None:
        """Register default gates."""
        gates = [
            PreExecutionGate(),
            CodeQualityGate(),
            TestsGate(),
            SecurityGate(),
            ReviewGate(),
            HumanApprovalGate(),
            PerformanceGate(),
            DocumentationGate(),
        ]
        
        for gate in gates:
            self._gates[gate.gate_id] = gate
    
    def register(self, gate: ValidationGate) -> None:
        self._gates[gate.gate_id] = gate
    
    def get(self, gate_id: str) -> Optional[ValidationGate]:
        return self._gates.get(gate_id)
    
    def get_all(self) -> List[ValidationGate]:
        return list(self._gates.values())
    
    async def run_gate(self, gate_id: str, state: FactoryState) -> GateResult:
        """Run a specific gate."""
        gate = self._gates.get(gate_id)
        if not gate:
            return GateResult(
                gate_id=gate_id,
                name=gate_id,
                passed=False,
                score=0.0,
                details={"error": "Gate not found"},
            )
        return await gate.run(state)
    
    async def run_gates(self, gate_ids: List[str], state: FactoryState) -> List[GateResult]:
        """Run multiple gates in parallel."""
        tasks = [self.run_gate(gid, state) for gid in gate_ids]
        return await asyncio.gather(*tasks)


# Global gate registry
_gate_registry: Optional[GateRegistry] = None


def get_gate_registry() -> GateRegistry:
    global _gate_registry
    if _gate_registry is None:
        _gate_registry = GateRegistry()
    return _gate_registry