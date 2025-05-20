"""
Main module for the code analysis and indexing tool.
"""
import os
import sys
import argparse
from typing import List, Optional

from src.services.clang_analyzer_service import ClangAnalyzerService
from src.services.search_service import SearchService
from src.services.neo4j_service import Neo4jService
from src.config.settings import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Code analysis and indexing tool")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Index command
    index_parser = subparsers.add_parser("index", help="Index code into Neo4j")
    index_parser.add_argument("path", help="Path to file or directory to analyze")
    index_parser.add_argument("--project", required=True, help="Project name for grouping indexed code")
    index_parser.add_argument("--clear", action="store_true", help="Clear existing project data before indexing")
    index_parser.add_argument("--use-clang", action="store_true", help="Use Clang analyzer instead of cflow")
    index_parser.add_argument("--include-dirs", nargs="+", help="Include directories for Clang analysis")
    index_parser.add_argument("--compiler-args", nargs="+", help="Additional compiler arguments for Clang")
    index_parser.add_argument("--parallel", action="store_true", help="Use parallel processing for directory analysis")
    index_parser.add_argument("--workers", type=int, default=4, help="Number of worker processes for parallel analysis")
    index_parser.add_argument("--incremental", action="store_true", help="Use incremental indexing for changed files only")
    index_parser.add_argument("--changed-files", nargs="+", help="List of changed files for incremental indexing")
    
    # Search command
    search_parser = subparsers.add_parser("search", help="Search for functions in Neo4j")
    search_parser.add_argument("query", help="Function name pattern to search for")
    search_parser.add_argument("--project", help="Project name to search within")
    
    # Neighbors command
    neighbors_parser = subparsers.add_parser("neighbors", help="Find function neighbors in the call graph")
    neighbors_parser.add_argument("function", help="Function name to find neighbors for")
    neighbors_parser.add_argument("--project", required=True, help="Project name to search within")
    neighbors_parser.add_argument("--direction", choices=["callers", "callees", "both"], default="both",
                                help="Direction of neighbors to find")
    neighbors_parser.add_argument("--depth", type=int, default=1, help="Depth of neighbors to traverse")
    
    # Natural language query command
    nl_query_parser = subparsers.add_parser("nlquery", help="Query by natural language description")
    nl_query_parser.add_argument("description", help="Natural language description of function to find")
    nl_query_parser.add_argument("--project", required=True, help="Project name to search within")
    nl_query_parser.add_argument("--language", choices=["auto", "zh", "en"], default="auto", 
                              help="Query language (auto, zh: Chinese, en: English)")
    nl_query_parser.add_argument("--limit", type=int, default=10, help="Maximum number of results to return")
    nl_query_parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed match information")
    
    # Embedding index command
    embedding_index_parser = subparsers.add_parser("embedding-index", help="Build embedding-based code index")
    embedding_index_parser.add_argument("--project-dir", required=True, help="Project directory to index")

    embedding_search_parser = subparsers.add_parser("embedding-search", help="Semantic search in code index")
    embedding_search_parser.add_argument("--project-dir", required=True, help="Project directory to search")
    embedding_search_parser.add_argument("--query", required=True, help="Query text")
    
    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()
    
    if not args.command:
        print("Error: No command specified. Use --help for usage information.")
        sys.exit(1)
    
    neo4j_service = Neo4jService(
        uri=NEO4J_URI,
        username=NEO4J_USER,
        password=NEO4J_PASSWORD
    )
    
    if args.command == "index":
        if args.use_clang:
            # Use Clang analyzer
            analyzer = ClangAnalyzerService()
            include_dirs = args.include_dirs if args.include_dirs else []
            compiler_args = args.compiler_args if args.compiler_args else []
            
            if os.path.isdir(args.path):
                call_graph = analyzer.analyze_directory(
                    args.path, 
                    include_dirs=include_dirs, 
                    compiler_args=compiler_args,
                    use_parallel=args.parallel,
                    max_workers=args.workers
                )
            else:
                call_graph = analyzer.analyze_file(args.path, include_dirs=include_dirs, compiler_args=compiler_args)
                
            if args.incremental and args.changed_files:
                neo4j_service.incremental_index(call_graph, args.project, args.changed_files)
            else:
                neo4j_service.index_clang_callgraph(call_graph, args.project, args.clear)
    
    elif args.command == "search":
        search_service = SearchService(neo4j_service)
        results = search_service.search_functions(args.query, args.project)
        
        if not results:
            print("No results found.")
        else:
            print("Found functions:")
            for func in results:
                print(f"  - {func}")
    
    elif args.command == "neighbors":
        search_service = SearchService(neo4j_service)
        
        if args.direction == "callers" or args.direction == "both":
            callers = search_service.find_callers(args.function, args.project, args.depth)
            print(f"Functions that call '{args.function}':")
            if not callers:
                print("  No callers found.")
            else:
                for caller in callers:
                    print(f"  - {caller}")
        
        if args.direction == "callees" or args.direction == "both":
            callees = search_service.find_callees(args.function, args.project, args.depth)
            print(f"Functions called by '{args.function}':")
            if not callees:
                print("  No callees found.")
            else:
                for callee in callees:
                    print(f"  - {callee}")
    
    elif args.command == "nlquery":
        try:
            # Use our new natural language query implementation
            from src.cmd.nlquery import detect_language, main as nlquery_main
            
            # Detect language if set to auto
            language = args.language
            if language == "auto":
                language = detect_language(args.description)
                if language == "zh":
                    print("Detected Chinese query")
                else:
                    print("Detected English query")
                
            # Run the natural language query
            search_service = SearchService(neo4j_service=neo4j_service)
            results = search_service.search_by_description(
                description=args.description,
                project_name=args.project,
                limit=args.limit,
                lang=language
            )
            
            # Display results
            if not results:
                print(f"No functions found matching '{args.description}'")
            else:
                print(f"Found {len(results)} matching functions:")
                for i, result in enumerate(results, 1):
                    print(f"\n{i}. {result['name']}")
                    if 'file_path' in result and result['file_path']:
                        print(f"   File: {result['file_path']}")
                    if 'line_number' in result and result['line_number']:
                        print(f"   Line: {result['line_number']}")
                    
                    # Show additional details if verbose
                    if args.verbose:
                        if 'signature' in result and result['signature']:
                            print(f"   Signature: {result['signature']}")
                        if 'is_template' in result and result['is_template']:
                            print(f"   Template: Yes")
                        if 'is_virtual' in result and result['is_virtual']:
                            print(f"   Virtual: Yes")
                        if 'class_name' in result and result['class_name']:
                            print(f"   Class: {result['class_name']}")
                        if 'namespace' in result and result['namespace']:
                            print(f"   Namespace: {result['namespace']}")
                            
                        # Show relevance details
                        if 'relevance' in result:
                            print(f"   Relevance score: {result['relevance']:.2f}")
                            
                        # Show matched tokens
                        if 'matched_tokens' in result:
                            print(f"   Matched terms: {', '.join(result['matched_tokens'])}")
        except ImportError as e:
            print(f"Error: {e}")
            print("Make sure the required packages are installed.")
            sys.exit(1)
        except Exception as e:
            print(f"Error during natural language query: {e}")
            sys.exit(1)

    elif args.command == "embedding-index":
        from src.services.embedding_index_service import EmbeddingIndexService
        service = EmbeddingIndexService(args.project_dir)
        service.build_index()
        print("Embedding index built.")

    elif args.command == "embedding-search":
        from src.services.embedding_index_service import EmbeddingIndexService
        service = EmbeddingIndexService(args.project_dir)
        service.build_index()
        results = service.search(args.query)
        for meta, score in results:
            print(f"{meta['file']}:{meta['start_line']}-{meta['end_line']} | {meta['name']} | Score: {score}")
            print(meta['code'])
            print('-' * 40)


if __name__ == "__main__":
    main() 