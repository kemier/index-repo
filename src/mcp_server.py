from mcp.server.fastmcp import FastMCP
from src.controllers.mcp_controller import register_mcp_tools

mcp = FastMCP("code-indexer")
register_mcp_tools(mcp)

if __name__ == "__main__":
    mcp.run(transport="stdio") 