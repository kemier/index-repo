from src.mcp_indexer import MCPIndexer
from src.services.neo4j_service import Neo4jService

class MCPIndexService:
    def __init__(self):
        self.indexer = None
        self.neo4j = Neo4jService(...)

    def index_project(self, project_dir):
        self.indexer = MCPIndexer(project_dir)
        self.indexer.build_all()
        return f"Indexed {len(self.indexer.functions)} functions in {project_dir}"

    def get_call_chain(self, function, project, direction, depth):
        return self.neo4j.query_call_chain(function, project, direction, depth)

    def semantic_search(self, query, topk):
        if not self.indexer:
            return []
        return self.indexer.semantic_search(query, topk)

    def describe_call_chain(self, description, project, direction, depth, topk):
        candidates = self.semantic_search(description, topk)
        results = []
        for func in candidates:
            func_name = func['function']
            chain = self.get_call_chain(func_name, project, direction, depth)
            results.append({
                "entry_function": func,
                "call_chain": chain
            })
        return results 