import faiss
import numpy as np
from src.utils.scanner import scan_files
from src.utils.parser import parse_code_blocks
from src.utils.embedder import CodeEmbedder

class EmbeddingIndexService:
    def __init__(self, project_dir, model_name='microsoft/codebert-base'):
        self.project_dir = project_dir
        self.embedder = CodeEmbedder(model_name)
        self.index = None
        self.meta = []

    def build_index(self):
        files = scan_files(self.project_dir)
        blocks = []
        for file in files:
            code_blocks = parse_code_blocks(file)
            for block in code_blocks:
                embedding = self.embedder.embed_code(block['code'])
                blocks.append((embedding, block))
        if blocks:
            dim = blocks[0][0].shape[0]
            self.index = faiss.IndexFlatL2(dim)
            for emb, meta in blocks:
                self.index.add(np.array([emb]).astype('float32'))
                self.meta.append(meta)

    def search(self, query, topk=5):
        query_vec = self.embedder.embed_code(query)
        D, I = self.index.search(np.array([query_vec]).astype('float32'), topk)
        return [(self.meta[i], float(D[0][idx])) for idx, i in enumerate(I[0])] 