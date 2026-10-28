"""Graph store for semantic memory using Neo4j or Kuzu."""

import asyncio
import json
from typing import Any, Dict, List, Optional
from datetime import datetime
from pathlib import Path
import structlog

from factory.config.settings import settings

logger = structlog.get_logger(__name__)


class GraphStore:
    """Neo4j-backed graph store for semantic memory (architecture decisions, patterns)."""
    
    def __init__(
        self,
        uri: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
    ):
        self.uri = uri or settings.memory.neo4j_uri
        self.user = user or settings.memory.neo4j_user
        self.password = password or settings.memory.neo4j_password
        self._driver = None
        self._use_kuzu = False
        self._kuzu_db = None
    
    async def initialize(self) -> None:
        """Initialize database connection."""
        # Try Neo4j first
        try:
            from neo4j import AsyncGraphDatabase
            self._driver = AsyncGraphDatabase.driver(
                self.uri,
                auth=(self.user, self.password),
            )
            await self._driver.verify_connectivity()
            logger.info("neo4j_connected", uri=self.uri)
            return
        except Exception as e:
            logger.warning("neo4j_connection_failed", error=str(e))
        
        # Fallback to Kuzu (embedded)
        try:
            import kuzu
            db_path = settings.data_dir / "kuzu_db"
            db_path.mkdir(parents=True, exist_ok=True)
            self._kuzu_db = kuzu.Database(str(db_path))
            self._use_kuzu = True
            logger.info("kuzu_initialized", path=str(db_path))
            await self._init_kuzu_schema()
            return
        except Exception as e:
            logger.warning("kuzu_initialization_failed", error=str(e))
        
        logger.warning("no_graph_store_available")
    
    async def _init_kuzu_schema(self) -> None:
        """Initialize Kuzu schema."""
        if not self._kuzu_db:
            return
        
        conn = self._kuzu_db.connection()
        
        # Node tables
        schemas = [
            "CREATE NODE TABLE IF NOT EXISTS Decision (id STRING, title STRING, description STRING, context STRING, status STRING, created_at TIMESTAMP, PRIMARY KEY (id))",
            "CREATE NODE TABLE IF NOT EXISTS Pattern (id STRING, name STRING, description STRING, category STRING, code_example STRING, created_at TIMESTAMP, PRIMARY KEY (id))",
            "CREATE NODE TABLE IF NOT EXISTS Component (id STRING, name STRING, type STRING, repository STRING, description STRING, created_at TIMESTAMP, PRIMARY KEY (id))",
            "CREATE NODE TABLE IF NOT EXISTS WorkItem (id STRING, title STRING, description STRING, repository STRING, status STRING, created_at TIMESTAMP, PRIMARY KEY (id))",
            "CREATE REL TABLE IF NOT EXISTS RELATES_TO (FROM Decision TO Decision, strength DOUBLE)",
            "CREATE REL TABLE IF NOT EXISTS USES_PATTERN (FROM Decision TO Pattern)",
            "CREATE REL TABLE IF NOT EXISTS IMPLEMENTS (FROM WorkItem TO Component)",
            "CREATE REL TABLE IF NOT EXISTS DEPENDS_ON (FROM Component TO Component)",
        ]
        
        for schema in schemas:
            try:
                conn.execute(schema)
            except Exception:
                pass  # May already exist
    
    async def add_decision(
        self,
        decision_id: str,
        title: str,
        description: str,
        context: str,
        status: str = "proposed",
        related_decisions: Optional[List[str]] = None,
    ) -> None:
        """Add an architecture decision record (ADR)."""
        if self._use_kuzu:
            await self._kuzu_add_decision(decision_id, title, description, context, status, related_decisions)
        elif self._driver:
            await self._neo4j_add_decision(decision_id, title, description, context, status, related_decisions)
    
    async def _kuzu_add_decision(
        self,
        decision_id: str,
        title: str,
        description: str,
        context: str,
        status: str,
        related_decisions: Optional[List[str]] = None,
    ) -> None:
        conn = self._kuzu_db.connection()
        
        conn.execute("""
            CREATE (d:Decision {
                id: $id, title: $title, description: $desc,
                context: $context, status: $status, created_at: $created
            })
        """, {
            "id": decision_id,
            "title": title,
            "desc": description,
            "context": context,
            "status": status,
            "created": datetime.utcnow().timestamp(),
        })
        
        if related_decisions:
            for rel_id in related_decisions:
                conn.execute("""
                    MATCH (d1:Decision {id: $id1}), (d2:Decision {id: $id2})
                    CREATE (d1)-[:RELATES_TO {strength: 1.0}]->(d2)
                """, {"id1": decision_id, "id2": rel_id})
    
    async def _neo4j_add_decision(
        self,
        decision_id: str,
        title: str,
        description: str,
        context: str,
        status: str,
        related_decisions: Optional[List[str]] = None,
    ) -> None:
        async with self._driver.session() as session:
            await session.run("""
                CREATE (d:Decision {
                    id: $id, title: $title, description: $desc,
                    context: $context, status: $status, created_at: datetime()
                })
            """, id=decision_id, title=title, desc=description, context=context, status=status)
            
            if related_decisions:
                for rel_id in related_decisions:
                    await session.run("""
                        MATCH (d1:Decision {id: $id1}), (d2:Decision {id: $id2})
                        CREATE (d1)-[:RELATES_TO {strength: 1.0}]->(d2)
                    """, id1=decision_id, id2=rel_id)
    
    async def add_pattern(
        self,
        pattern_id: str,
        name: str,
        description: str,
        category: str,
        code_example: str = "",
    ) -> None:
        """Add a reusable pattern."""
        if self._use_kuzu:
            conn = self._kuzu_db.connection()
            conn.execute("""
                CREATE (p:Pattern {
                    id: $id, name: $name, description: $desc,
                    category: $cat, code_example: $code, created_at: $created
                })
            """, {
                "id": pattern_id,
                "name": name,
                "desc": description,
                "cat": category,
                "code": code_example,
                "created": datetime.utcnow().timestamp(),
            })
        elif self._driver:
            async with self._driver.session() as session:
                await session.run("""
                    CREATE (p:Pattern {
                        id: $id, name: $name, description: $desc,
                        category: $cat, code_example: $code, created_at: datetime()
                    })
                """, id=pattern_id, name=name, desc=description, cat=category, code=code_example)
    
    async def add_component(
        self,
        component_id: str,
        name: str,
        type: str,
        repository: str,
        description: str = "",
        dependencies: Optional[List[str]] = None,
    ) -> None:
        """Add a system component."""
        if self._use_kuzu:
            conn = self._kuzu_db.connection()
            conn.execute("""
                CREATE (c:Component {
                    id: $id, name: $name, type: $type,
                    repository: $repo, description: $desc, created_at: $created
                })
            """, {
                "id": component_id,
                "name": name,
                "type": type,
                "repo": repository,
                "desc": description,
                "created": datetime.utcnow().timestamp(),
            })
            
            if dependencies:
                for dep_id in dependencies:
                    conn.execute("""
                        MATCH (c1:Component {id: $id1}), (c2:Component {id: $id2})
                        CREATE (c1)-[:DEPENDS_ON]->(c2)
                    """, {"id1": component_id, "id2": dep_id})
        elif self._driver:
            async with self._driver.session() as session:
                await session.run("""
                    CREATE (c:Component {
                        id: $id, name: $name, type: $type,
                        repository: $repo, description: $desc, created_at: datetime()
                    })
                """, id=component_id, name=name, type=type, repo=repository, desc=description)
                
                if dependencies:
                    for dep_id in dependencies:
                        await session.run("""
                            MATCH (c1:Component {id: $id1}), (c2:Component {id: $id2})
                            CREATE (c1)-[:DEPENDS_ON]->(c2)
                        """, id1=component_id, id2=dep_id)
    
    async def query_decisions(
        self,
        query: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Query architecture decisions."""
        if self._use_kuzu:
            conn = self._kuzu_db.connection()
            # Kuzu doesn't support full-text search easily, use simple match
            result = conn.execute(f"""
                MATCH (d:Decision)
                WHERE d.title CONTAINS $query OR d.description CONTAINS $query
                RETURN d.id, d.title, d.description, d.context, d.status, d.created_at
                LIMIT {limit}
            """, {"query": query})
            
            return [dict(row) for row in result.get_as_pl()]
        elif self._driver:
            async with self._driver.session() as session:
                result = await session.run("""
                    MATCH (d:Decision)
                    WHERE d.title CONTAINS $query OR d.description CONTAINS $query
                    RETURN d
                    LIMIT $limit
                """, query=query, limit=limit)
                
                return [dict(record["d"]) for record in result]
        
        return []
    
    async def query_patterns(
        self,
        category: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Query reusable patterns."""
        if self._use_kuzu:
            conn = self._kuzu_db.connection()
            if category:
                result = conn.execute(f"""
                    MATCH (p:Pattern {{category: $cat}})
                    RETURN p.id, p.name, p.description, p.category, p.code_example, p.created_at
                    LIMIT {limit}
                """, {"cat": category})
            else:
                result = conn.execute(f"""
                    MATCH (p:Pattern)
                    RETURN p.id, p.name, p.description, p.category, p.code_example, p.created_at
                    LIMIT {limit}
                """)
            
            return [dict(row) for row in result.get_as_pl()]
        elif self._driver:
            async with self._driver.session() as session:
                if category:
                    result = await session.run("""
                        MATCH (p:Pattern {category: $cat})
                        RETURN p
                        LIMIT $limit
                    """, cat=category, limit=limit)
                else:
                    result = await session.run("""
                        MATCH (p:Pattern)
                        RETURN p
                        LIMIT $limit
                    """, limit=limit)
                
                return [dict(record["p"]) for record in result]
        
        return []
    
    async def get_component_graph(
        self,
        repository: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get component dependency graph."""
        if self._use_kuzu:
            conn = self._kuzu_db.connection()
            if repository:
                result = conn.execute("""
                    MATCH (c:Component {repository: $repo})
                    OPTIONAL MATCH (c)-[:DEPENDS_ON]->(d:Component)
                    RETURN c, collect(d) as dependencies
                """, {"repo": repository})
            else:
                result = conn.execute("""
                    MATCH (c:Component)
                    OPTIONAL MATCH (c)-[:DEPENDS_ON]->(d:Component)
                    RETURN c, collect(d) as dependencies
                """)
            
            nodes = []
            edges = []
            for row in result.get_as_pl():
                c = dict(row[0])
                nodes.append(c)
                for d in row[1]:
                    edges.append({"from": c["id"], "to": dict(d)["id"]})
            
            return {"nodes": nodes, "edges": edges}
        elif self._driver:
            async with self._driver.session() as session:
                if repository:
                    result = await session.run("""
                        MATCH (c:Component {repository: $repo})
                        OPTIONAL MATCH (c)-[:DEPENDS_ON]->(d:Component)
                        RETURN c, collect(d) as dependencies
                    """, repo=repository)
                else:
                    result = await session.run("""
                        MATCH (c:Component)
                        OPTIONAL MATCH (c)-[:DEPENDS_ON]->(d:Component)
                        RETURN c, collect(d) as dependencies
                    """)
                
                nodes = []
                edges = []
                for record in result:
                    c = dict(record["c"])
                    nodes.append(c)
                    for d in record["dependencies"]:
                        edges.append({"from": c["id"], "to": dict(d)["id"]})
                
                return {"nodes": nodes, "edges": edges}
        
        return {"nodes": [], "edges": []}
    
    async def close(self) -> None:
        """Close connections."""
        if self._driver:
            await self._driver.close()
        if self._kuzu_db:
            self._kuzu_db.close()


# Global graph store
_graph_store: Optional[GraphStore] = None


def get_graph_store() -> GraphStore:
    global _graph_store
    if _graph_store is None:
        _graph_store = GraphStore()
    return _graph_store


async def initialize_graph_store() -> GraphStore:
    """Initialize global graph store."""
    store = get_graph_store()
    await store.initialize()
    return store