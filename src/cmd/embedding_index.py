import argparse
from src.services.embedding_index_service import EmbeddingIndexService

def main():
    parser = argparse.ArgumentParser(description="Embedding-based code index/search")
    parser.add_argument("command", choices=["index", "search"])
    parser.add_argument("--project-dir", required=True)
    parser.add_argument("--query", help="Query text for search")
    args = parser.parse_args()

    service = EmbeddingIndexService(args.project_dir)
    if args.command == "index":
        service.build_index()
        print("Index built.")
    elif args.command == "search":
        if not args.query:
            print("Please provide --query for search.")
            return
        service.build_index()  # 简单起见，每次都重建，可优化为持久化
        results = service.search(args.query)
        for meta, score in results:
            print(f"{meta['file']}:{meta['start_line']}-{meta['end_line']} | {meta['name']} | Score: {score}")
            print(meta['code'])
            print('-' * 40)

if __name__ == "__main__":
    main() 