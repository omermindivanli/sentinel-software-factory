"""Factory configuration system using Pydantic Settings."""

from pathlib import Path
from typing import Any, Dict, List, Optional, Literal
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import yaml


class ModelConfig(BaseSettings):
    """Configuration for a single model."""
    
    id: str
    provider: Literal["anthropic", "openai", "ollama", "google", "azure"] = "anthropic"
    max_tokens: int = 8192
    temperature: float = 0.0
    cost_per_1k_input: float = 0.0
    cost_per_1k_output: float = 0.0
    capabilities: List[str] = Field(default_factory=list)
    local: bool = False
    base_url: Optional[str] = None
    api_key_env: Optional[str] = None  # Env var name for API key
    
    def get_api_key(self) -> Optional[str]:
        """Get API key from environment."""
        if self.api_key_env:
            import os
            return os.getenv(self.api_key_env)
        return None


class RouterConfig(BaseSettings):
    """Model router configuration."""
    
    default_provider: str = "anthropic"
    fallback_provider: str = "ollama"
    models: List[ModelConfig] = Field(default_factory=list)
    routing_rules: Dict[str, str] = Field(default_factory=dict)  # capability -> model_id
    
    def get_model_for_capability(self, capability: str) -> Optional[ModelConfig]:
        """Get best model for a capability."""
        # Check explicit routing rule first
        if capability in self.routing_rules:
            model_id = self.routing_rules[capability]
            for m in self.models:
                if m.id == model_id:
                    return m
        
        # Find first model with capability
        for m in self.models:
            if capability in m.capabilities:
                return m
        
        # Fallback to default
        for m in self.models:
            if m.provider == self.default_provider:
                return m
        
        # Last resort: first model
        return self.models[0] if self.models else None


class StageConfig(BaseSettings):
    """Configuration for a single SDLC stage."""
    
    id: str
    name: str
    agent: str  # Agent class name
    description: str = ""
    parallelism: int = 1
    schedule: Optional[str] = None  # cron expression or "on_merge", "continuous"
    metrics: List[str] = Field(default_factory=list)
    gates: List[str] = Field(default_factory=list)
    human_gate: bool = False
    integrations: List[str] = Field(default_factory=list)


class RiskTierConfig(BaseSettings):
    """Risk tier for governance."""
    
    name: str
    repos: List[str] = Field(default_factory=list)  # Glob patterns
    gates: List[str] = Field(default_factory=list)
    human_approval: bool = False
    max_autonomy: Literal["full", "supervised", "guided"] = "supervised"
    require_dual_llm: bool = False


class GovernanceConfig(BaseSettings):
    """Governance and security configuration."""
    
    risk_tiers: List[RiskTierConfig] = Field(default_factory=list)
    command_allowlist: List[str] = Field(default_factory=list)
    command_denylist: List[str] = Field(default_factory=list)
    secrets_policy: Dict[str, Any] = Field(default_factory=dict)
    
    def get_tier_for_repo(self, repo: str) -> RiskTierConfig:
        """Get risk tier for a repository."""
        import fnmatch
        for tier in self.risk_tiers:
            for pattern in tier.repos:
                if fnmatch.fnmatch(repo, pattern):
                    return tier
        # Default to medium
        for tier in self.risk_tiers:
            if tier.name == "medium":
                return tier
        return self.risk_tiers[0] if self.risk_tiers else RiskTierConfig(
            name="default",
            gates=["code_quality", "tests"],
            human_approval=False,
            max_autonomy="supervised"
        )


class SandboxConfig(BaseSettings):
    """Sandbox execution configuration."""
    
    worktree_base: Path = Path(".factory/worktrees")
    container_base_image: str = "python:3.11-slim"
    default_cpu_limit: float = 2.0
    default_memory_limit: str = "4g"
    default_timeout: int = 600  # seconds
    network_enabled: bool = True
    gpu_enabled: bool = False
    artifact_retention_days: int = 30
    
    # Container runtime: "docker" or "podman"
    container_runtime: Literal["docker", "podman"] = "podman"


class MemoryConfig(BaseSettings):
    """Memory system configuration."""
    
    # Vector store (Chroma)
    chroma_host: str = "localhost"
    chroma_port: int = 8000
    chroma_collection_prefix: str = "factory"
    
    # Graph store (Neo4j)
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "factory123"
    
    # KV store (Redis)
    redis_url: str = "redis://localhost:6379/0"
    
    # Tier TTLs (seconds)
    working_ttl: int = 3600  # 1 hour
    episodic_ttl: int = 2592000  # 30 days
    semantic_ttl: int = 0  # Permanent (0 = no expiry)
    procedural_ttl: int = 0  # Versioned, no auto-expiry


class MCPConfig(BaseSettings):
    """MCP configuration."""
    
    servers: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    progressive_discovery: bool = True
    context_threshold: float = 0.03  # 3% of context window
    tool_search_enabled: bool = True
    
    
class Settings(BaseSettings):
    """Main factory settings."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
    
    # Environment
    env: Literal["development", "staging", "production"] = "development"
    debug: bool = True
    log_level: str = "INFO"
    
    # Paths
    data_dir: Path = Path(".factory/data")
    work_dir: Path = Path(".factory/work")
    log_dir: Path = Path(".factory/logs")
    
    # Sub-configurations
    router: RouterConfig = Field(default_factory=RouterConfig)
    stages: List[StageConfig] = Field(default_factory=list)
    governance: GovernanceConfig = Field(default_factory=GovernanceConfig)
    sandbox: SandboxConfig = Field(default_factory=SandboxConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    mcp: MCPConfig = Field(default_factory=MCPConfig)
    
    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    ws_heartbeat_interval: int = 30
    
    # Dashboard
    dashboard_port: int = 5173
    
    # Metrics
    metrics_enabled: bool = True
    metrics_port: int = 9090
    
    @field_validator("data_dir", "work_dir", "log_dir", mode="before")
    @classmethod
    def expand_path(cls, v: Any) -> Path:
        if isinstance(v, str):
            return Path(v).expanduser().resolve()
        return v
    
    def load_from_yaml(self, path: Path) -> "Settings":
        """Load configuration from YAML files."""
        with open(path) as f:
            data = yaml.safe_load(f)
        return self.model_validate(data)


def load_settings() -> Settings:
    """Load settings from config files and environment."""
    settings = Settings()
    
    # Load from YAML configs if they exist
    config_dir = Path("factory/config")
    if config_dir.exists():
        for config_file in ["models.yaml", "stages.yaml", "governance.yaml"]:
            path = config_dir / config_file
            if path.exists():
                with open(path) as f:
                    data = yaml.safe_load(f)
                    if data:
                        # Update relevant section
                        if config_file == "models.yaml" and "router" in data:
                            settings.router = RouterConfig(**data["router"])
                        elif config_file == "stages.yaml" and "stages" in data:
                            settings.stages = [StageConfig(**s) for s in data["stages"]]
                        elif config_file == "governance.yaml":
                            settings.governance = GovernanceConfig(**data)
    
    return settings


# Global settings instance
settings = load_settings()