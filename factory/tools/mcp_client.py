"""MCP (Model Context Protocol) client for external tool integration."""

import asyncio
import json
from typing import Any, Dict, List, Optional
from datetime import datetime
from uuid import uuid4
import structlog

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from factory.config.settings import settings

logger = structlog.get_logger(__name__)


class MCPServerConnection:
    """Connection to a single MCP server."""
    
    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config
        self.session: Optional[ClientSession] = None
        self._tools: List[Dict[str, Any]] = []
        self._connected = False
    
    async def connect(self) -> bool:
        """Connect to MCP server."""
        try:
            # Parse server config
            command = self.config.get("command")
            args = self.config.get("args", [])
            env = self.config.get("env", {})
            
            if not command:
                logger.error("mcp_no_command", server=self.name)
                return False
            
            server_params = StdioServerParameters(
                command=command,
                args=args,
                env=env,
            )
            
            # Create client session
            read, write = await stdio_client(server_params).__aenter__()
            self.session = ClientSession(read, write)
            await self.session.__aenter__()
            
            # Initialize
            await self.session.initialize()
            
            # List tools
            tools_result = await self.session.list_tools()
            self._tools = [
                {
                    "name": f"{self.name}.{t.name}",
                    "description": t.description,
                    "input_schema": t.inputSchema,
                    "server": self.name,
                }
                for t in tools_result.tools
            ]
            
            self._connected = True
            logger.info("mcp_connected", server=self.name, tools=len(self._tools))
            return True
            
        except Exception as e:
            logger.error("mcp_connection_failed", server=self.name, error=str(e))
            self._connected = False
            return False
    
    async def disconnect(self) -> None:
        """Disconnect from MCP server."""
        if self.session:
            try:
                await self.session.__aexit__(None, None, None)
            except Exception:
                pass
            self.session = None
        self._connected = False
        logger.info("mcp_disconnected", server=self.name)
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Call a tool on the MCP server."""
        if not self._connected or not self.session:
            raise RuntimeError(f"MCP server {self.name} not connected")
        
        # Remove server prefix if present
        if tool_name.startswith(f"{self.name}."):
            tool_name = tool_name[len(self.name) + 1:]
        
        result = await self.session.call_tool(tool_name, arguments)
        
        # Convert result to JSON-serializable
        if hasattr(result, 'content'):
            return [{"type": c.type, "text": c.text} for c in result.content]
        return result
    
    def get_tools(self) -> List[Dict[str, Any]]:
        """Get available tools."""
        return self._tools
    
    @property
    def is_connected(self) -> bool:
        return self._connected


class MCPClient:
    """Manages connections to multiple MCP servers."""
    
    def __init__(self):
        self.servers: Dict[str, MCPServerConnection] = {}
        self._tool_index: Dict[str, MCPServerConnection] = {}
    
    async def connect_server(self, name: str, config: Dict[str, Any]) -> bool:
        """Connect to an MCP server."""
        if name in self.servers:
            await self.servers[name].disconnect()
        
        conn = MCPServerConnection(name, config)
        success = await conn.connect()
        
        if success:
            self.servers[name] = conn
            # Index tools
            for tool in conn.get_tools():
                self._tool_index[tool["name"]] = conn
            return True
        return False
    
    async def disconnect_server(self, name: str) -> None:
        """Disconnect from an MCP server."""
        if name in self.servers:
            await self.servers[name].disconnect()
            # Remove from index
            for tool in self.servers[name].get_tools():
                self._tool_index.pop(tool["name"], None)
            del self.servers[name]
    
    async def disconnect_all(self) -> None:
        """Disconnect all servers."""
        for name in list(self.servers.keys()):
            await self.disconnect_server(name)
    
    def get_all_tools(self) -> List[Dict[str, Any]]:
        """Get all tools from all connected servers."""
        tools = []
        for conn in self.servers.values():
            tools.extend(conn.get_tools())
        return tools
    
    def get_server_for_tool(self, tool_name: str) -> Optional[MCPServerConnection]:
        """Get server that provides a tool."""
        return self._tool_index.get(tool_name)
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Call a tool on the appropriate server."""
        server = self.get_server_for_tool(tool_name)
        if not server:
            raise ValueError(f"Tool not found: {tool_name}")
        return await server.call_tool(tool_name, arguments)
    
    def get_connected_servers(self) -> List[str]:
        """Get list of connected server names."""
        return [name for name, conn in self.servers.items() if conn.is_connected]
    
    async def reload_server(self, name: str) -> bool:
        """Reload a server (disconnect and reconnect)."""
        config = self.servers[name].config if name in self.servers else None
        await self.disconnect_server(name)
        if config:
            return await self.connect_server(name, config)
        return False


# Global MCP client
_mcp_client: Optional[MCPClient] = None


def get_mcp_client() -> MCPClient:
    global _mcp_client
    if _mcp_client is None:
        _mcp_client = MCPClient()
    return _mcp_client


async def initialize_mcp_client() -> MCPClient:
    """Initialize MCP client and connect configured servers."""
    client = get_mcp_client()
    
    # Connect configured servers
    for name, config in settings.mcp.servers.items():
        await client.connect_server(name, config)
    
    return client