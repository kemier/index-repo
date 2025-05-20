from src.utils.scanner import scan_files
from src.utils.parser import parse_code_blocks
from src.utils.embedder import CodeEmbedder
import faiss
import numpy as np
import ast

class MCPIndexer:
    def __init__(self, project_dir):
        self.project_dir = project_dir
        self.functions = {}  # {func_name: {meta}}
        self.call_graph = {} # {func_name: {"callers": [], "callees": []}}
        self.embedder = CodeEmbedder()
        self.index = None
        self.meta = []

    def build_all(self):
        files = scan_files(self.project_dir)
        blocks = []
        for file in files:
            code_blocks = parse_code_blocks(file)
            for block in code_blocks:
                # 记录函数元数据
                if block['type'] in ('FunctionDef', 'AsyncFunctionDef'):
                    func_name = block['name']
                    self.functions[func_name] = {
                        "file": block['file'],
                        "start_line": block['start_line'],
                        "end_line": block['end_line'],
                        "signature": self._get_signature(block['code']),
                        "code": block['code']
                    }
        # 构建调用关系
        self._build_call_graph(files)
        # 构建嵌入索引
        self._build_embedding_index()

    def _get_signature(self, code):
        try:
            node = ast.parse(code).body[0]
            args = [a.arg for a in node.args.args]
            return f"{node.name}({', '.join(args)})"
        except Exception:
            return None

    def _build_call_graph(self, files):
        for file in files:
            code_blocks = parse_code_blocks(file)
            for block in code_blocks:
                if block['type'] in ('FunctionDef', 'AsyncFunctionDef'):
                    func_name = block['name']
                    callees = []
                    try:
                        node = ast.parse(block['code']).body[0]
                        for n in ast.walk(node):
                            if isinstance(n, ast.Call) and hasattr(n.func, 'id'):
                                callees.append(n.func.id)
                    except Exception:
                        pass
                    self.call_graph.setdefault(func_name, {"callers": [], "callees": []})
                    self.call_graph[func_name]["callees"].extend(callees)
                    for callee in callees:
                        self.call_graph.setdefault(callee, {"callers": [], "callees": []})
                        self.call_graph[callee]["callers"].append(func_name)

    def _build_embedding_index(self):
        blocks = []
        for func, meta in self.functions.items():
            embedding = self.embedder.embed_code(meta['code'])
            blocks.append((embedding, {**meta, "function": func}))
        if blocks:
            dim = blocks[0][0].shape[0]
            self.index = faiss.IndexFlatL2(dim)
            for emb, meta in blocks:
                self.index.add(np.array([emb]).astype('float32'))
                self.meta.append(meta)

    def get_call_chain(self, function):
        meta = self.functions.get(function)
        if not meta:
            return {}
        callers = [{"function": c, **self.functions.get(c, {})} for c in self.call_graph.get(function, {}).get("callers", [])]
        callees = [{"function": c, **self.functions.get(c, {})} for c in self.call_graph.get(function, {}).get("callees", [])]
        return {
            "function": function,
            "file": meta["file"],
            "start_line": meta["start_line"],
            "end_line": meta["end_line"],
            "signature": meta["signature"],
            "callers": callers,
            "callees": callees
        }

    def semantic_search(self, query, topk=5):
        if not self.index:
            return []
        query_vec = self.embedder.embed_code(query)
        D, I = self.index.search(np.array([query_vec]).astype('float32'), topk)
        results = []
        for idx, i in enumerate(I[0]):
            m = self.meta[i]
            results.append({
                "file": m["file"],
                "start_line": m["start_line"],
                "end_line": m["end_line"],
                "code": m["code"],
                "score": float(D[0][idx]),
                "function": m["function"]
            })
        return results 