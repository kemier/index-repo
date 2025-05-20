from src.services.mcp_index_service import MCPIndexService

def register_mcp_tools(mcp):
    service = MCPIndexService()

    @mcp.tool()
    async def index_project(project_dir: str) -> str:
        return service.index_project(project_dir)

    @mcp.tool()
    async def get_call_chain(function: str, project: str, direction: str = 'both', depth: int = 5) -> dict:
        return service.get_call_chain(function, project, direction, depth)

    @mcp.tool()
    async def semantic_search(query: str, topk: int = 5) -> list:
        return service.semantic_search(query, topk)

    @mcp.tool()
    async def describe_call_chain(description: str, project: str, direction: str = 'both', depth: int = 5, topk: int = 3) -> list:
        return service.describe_call_chain(description, project, direction, depth, topk) 