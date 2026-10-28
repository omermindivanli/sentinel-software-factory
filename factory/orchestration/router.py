"""Model router for intelligent model selection."""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
import time
import structlog

from factory.config.settings import settings, ModelConfig, RouterConfig

logger = structlog.get_logger(__name__)


@dataclass
class ModelMetrics:
    """Runtime metrics for a model."""
    total_requests: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    total_latency_ms: float = 0.0
    errors: int = 0
    last_used: float = 0.0
    
    @property
    def avg_latency_ms(self) -> float:
        return self.total_latency_ms / self.total_requests if self.total_requests > 0 else 0.0
    
    @property
    def avg_cost_per_request(self) -> float:
        return self.total_cost / self.total_requests if self.total_requests > 0 else 0.0


class ModelRouter:
    """Routes tasks to optimal models based on capability, cost, and performance."""
    
    def __init__(self, config: Optional[RouterConfig] = None):
        self.config = config or settings.router
        self.metrics: Dict[str, ModelMetrics] = {}
        self._initialize_metrics()
    
    def _initialize_metrics(self) -> None:
        """Initialize metrics for all configured models."""
        for model in self.config.models:
            self.metrics[model.id] = ModelMetrics()
    
    def get_model(self, capability: str, constraints: Optional[Dict[str, Any]] = None) -> ModelConfig:
        """
        Get the best model for a capability.
        
        Args:
            capability: Required capability (planning, code_generation, review, etc.)
            constraints: Optional constraints like max_cost, max_latency, local_only
            
        Returns:
            Selected ModelConfig
        """
        constraints = constraints or {}
        
        # Get candidate models
        candidates = self._get_candidates(capability, constraints)
        
        if not candidates:
            logger.warning("no_model_for_capability", capability=capability)
            # Return first available as fallback
            return self.config.models[0]
        
        # Score and select best
        selected = self._select_best(candidates, constraints)
        
        logger.info(
            "model_selected",
            capability=capability,
            model=selected.id,
            provider=selected.provider,
            candidates=len(candidates)
        )
        
        return selected
    
    def _get_candidates(
        self, 
        capability: str, 
        constraints: Dict[str, Any]
    ) -> List[ModelConfig]:
        """Get candidate models matching capability and constraints."""
        candidates = []
        
        for model in self.config.models:
            # Check capability
            if capability not in model.capabilities:
                continue
            
            # Check constraints
            if constraints.get("local_only") and not model.local:
                continue
            if constraints.get("provider") and model.provider != constraints["provider"]:
                continue
            if constraints.get("max_cost_per_1k") and model.cost_per_1k_input > constraints["max_cost_per_1k"]:
                continue
            if constraints.get("min_tokens") and model.max_tokens < constraints["min_tokens"]:
                continue
            
            candidates.append(model)
        
        return candidates
    
    def _select_best(
        self, 
        candidates: List[ModelConfig], 
        constraints: Dict[str, Any]
    ) -> ModelConfig:
        """Select best model from candidates using scoring."""
        
        # If explicit routing rule exists, use it
        if capability in self.config.routing_rules:
            rule_model_id = self.config.routing_rules[capability]
            for m in candidates:
                if m.id == rule_model_id:
                    return m
        
        # Score each candidate
        scored = []
        for model in candidates:
            score = self._score_model(model, capability, constraints)
            scored.append((score, model))
        
        # Sort by score (higher is better)
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[0][1]
    
    def _score_model(
        self, 
        model: ModelConfig, 
        capability: str, 
        constraints: Dict[str, Any]
    ) -> float:
        """Score a model for a capability."""
        metrics = self.metrics.get(model.id, ModelMetrics())
        
        score = 0.0
        
        # Capability match bonus
        if capability in model.capabilities:
            score += 10.0
        
        # Cost efficiency (lower cost = higher score)
        if model.cost_per_1k_input > 0:
            cost_score = 100.0 / (model.cost_per_1k_input + model.cost_per_1k_output)
            score += min(cost_score, 20.0)
        else:
            score += 20.0  # Free local models get bonus
        
        # Performance (lower latency = higher score)
        if metrics.total_requests > 10:
            latency_score = 1000.0 / (metrics.avg_latency_ms + 1)
            score += min(latency_score, 15.0)
        else:
            score += 10.0  # Default for untested
        
        # Reliability (lower error rate = higher score)
        if metrics.total_requests > 0:
            error_rate = metrics.errors / metrics.total_requests
            score += (1.0 - error_rate) * 10.0
        else:
            score += 8.0
        
        # Local preference for privacy-sensitive tasks
        if constraints.get("prefer_local") and model.local:
            score += 5.0
        
        # Recency bonus (recently used models are "warm")
        if metrics.last_used > 0:
            age = time.time() - metrics.last_used
            if age < 300:  # 5 minutes
                score += 3.0
        
        return score
    
    def record_request(
        self, 
        model_id: str, 
        tokens: int, 
        cost: float, 
        latency_ms: float, 
        error: bool = False
    ) -> None:
        """Record request metrics for a model."""
        if model_id not in self.metrics:
            self.metrics[model_id] = ModelMetrics()
        
        m = self.metrics[model_id]
        m.total_requests += 1
        m.total_tokens += tokens
        m.total_cost += cost
        m.total_latency_ms += latency_ms
        m.last_used = time.time()
        if error:
            m.errors += 1
    
    def get_model_stats(self, model_id: str) -> Optional[Dict[str, Any]]:
        """Get statistics for a model."""
        if model_id not in self.metrics:
            return None
        
        m = self.metrics[model_id]
        return {
            "model_id": model_id,
            "total_requests": m.total_requests,
            "total_tokens": m.total_tokens,
            "total_cost": m.total_cost,
            "avg_latency_ms": m.avg_latency_ms,
            "avg_cost_per_request": m.avg_cost_per_request,
            "error_rate": m.errors / m.total_requests if m.total_requests > 0 else 0.0,
            "last_used": m.last_used,
        }
    
    def get_all_stats(self) -> Dict[str, Any]:
        """Get statistics for all models."""
        return {mid: self.get_model_stats(mid) for mid in self.metrics}
    
    def reset_metrics(self, model_id: Optional[str] = None) -> None:
        """Reset metrics for a model or all models."""
        if model_id:
            if model_id in self.metrics:
                self.metrics[model_id] = ModelMetrics()
        else:
            self._initialize_metrics()


# Global router instance
router = ModelRouter()


def get_router() -> ModelRouter:
    """Get global router instance."""
    return router