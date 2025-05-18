#!/usr/bin/env python
"""
Script to clear existing Folly data from Neo4j and re-index the Folly repository.
"""
import os
import sys
import logging
import argparse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add parent directory to path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.neo4j_service import Neo4jService
from src.services.clang_analyzer_service import ClangAnalyzerService
from src.services.compile_commands_service import CompileCommandsService
from src.models.function_model import CallGraph

def setup_logging():
    """Configure logging for the script."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(__name__)

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Clear Neo4j and re-index Folly")
    parser.add_argument(
        "--folly-path", 
        required=True,
        help="Path to Folly source directory"
    )
    parser.add_argument(
        "--project",
        default="folly",
        help="Project name in Neo4j database (default: folly)"
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Number of parallel workers (default: 4)"
    )
    parser.add_argument(
        "--neo4j-uri",
        default="bolt://localhost:7688",
        help="Neo4j connection URI (default: bolt://localhost:7688)"
    )
    parser.add_argument(
        "--neo4j-user",
        default="neo4j",
        help="Neo4j username (default: neo4j)"
    )
    parser.add_argument(
        "--neo4j-password",
        default="password",
        help="Neo4j password (default: password)"
    )
    parser.add_argument(
        "--clear-all",
        action="store_true",
        help="Clear all Neo4j data, not just the specified project"
    )
    return parser.parse_args()

def main():
    """Clear Neo4j data and re-index Folly repository."""
    args = parse_arguments()
    logger = setup_logging()
    
    folly_path = Path(args.folly_path)
    if not folly_path.exists():
        logger.error(f"Folly path does not exist: {folly_path}")
        return
    
    # Connect to Neo4j
    logger.info(f"Connecting to Neo4j at {args.neo4j_uri}")
    neo4j_service = Neo4jService(
        uri=args.neo4j_uri,
        username=args.neo4j_user,
        password=args.neo4j_password
    )
    
    # Test connection
    if not neo4j_service.test_connection():
        logger.error("Failed to connect to Neo4j. Please check connection settings.")
        return
    
    logger.info("Successfully connected to Neo4j")
    
    # Clear data
    if args.clear_all:
        logger.info("Clearing all data from Neo4j database...")
        neo4j_service.clear_database()
    else:
        logger.info(f"Clearing existing data for project '{args.project}' from Neo4j database...")
        neo4j_service.clear_project(args.project)
    
    # Setup compile commands service to detect include paths
    logger.info("Setting up compile commands service...")
    compile_commands_service = CompileCommandsService()
    compile_commands_path = compile_commands_service.find_compile_commands(folly_path)
    
    if compile_commands_path:
        logger.info(f"Found compile_commands.json at {compile_commands_path}")
        compile_commands_service.load_compile_commands(compile_commands_path)
    else:
        logger.warning("No compile_commands.json found. Include paths may be incomplete.")
    
    # Initialize analyzer
    logger.info("Initializing Clang analyzer...")
    analyzer = ClangAnalyzerService()
    
    # Filter out test, benchmark, and example files
    excluded_patterns = ['test', 'benchmark', 'example']
    logger.info(f"Will exclude files with patterns: {excluded_patterns}")
    
    # Find all C++ files to analyze
    file_extensions = ['.cpp', '.cc', '.cxx', '.h', '.hpp']
    files_to_analyze = []
    for root, _, files in os.walk(folly_path):
        for file in files:
            if any(file.endswith(ext) for ext in file_extensions):
                file_path = os.path.join(root, file)
                # Skip files in test, benchmark, or example directories
                if not any(pattern in file_path.lower() for pattern in excluded_patterns):
                    files_to_analyze.append(file_path)
    
    logger.info(f"Found {len(files_to_analyze)} files to analyze (after filtering)")
    
    # Analyze source directory
    logger.info(f"Analyzing with {args.workers} workers")
    call_graph = CallGraph()
    
    # Use ThreadPoolExecutor for parallel processing
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        # Submit file analysis tasks
        file_tasks = []
        for file_path in files_to_analyze:
            include_dirs = []
            compiler_args = []
            
            # Get include paths and compiler args from compile_commands.json if available
            if compile_commands_path:
                include_dirs = compile_commands_service.get_include_paths(file_path)
                compiler_args = compile_commands_service.get_compiler_options(file_path)
            
            # Submit analysis task
            file_tasks.append(
                executor.submit(analyzer.analyze_file, file_path, include_dirs, compiler_args)
            )
        
        # Process completed tasks as they complete
        total_files = len(files_to_analyze)
        processed_files = 0
        
        for future in as_completed(file_tasks):
            processed_files += 1
            
            try:
                file_call_graph = future.result()
                
                # Merge file call graph into main call graph
                for func_name, func in file_call_graph.functions.items():
                    if func_name in call_graph.functions:
                        # Function already exists, merge calls
                        existing_func = call_graph.functions[func_name]
                        
                        # Merge calls
                        for called in func.calls:
                            existing_func.add_call(called)
                            
                        # Merge called_by
                        for caller in func.called_by:
                            existing_func.add_caller(caller)
                    else:
                        # New function, add to call graph
                        call_graph.add_function(func)
                
                # Merge missing functions
                for missing in file_call_graph.missing_functions:
                    call_graph.add_missing_function(missing)
                    
                # Print progress
                if processed_files % 10 == 0 or processed_files == total_files:
                    logger.info(f"Processed {processed_files}/{total_files} files")
                    
            except Exception as e:
                logger.error(f"Error analyzing file: {e}")
    
    logger.info(f"Analysis complete. Found {len(call_graph.functions)} functions")
    
    # Store results in Neo4j
    logger.info(f"Storing analysis results in Neo4j ({args.project})...")
    neo4j_service.index_call_graph(call_graph, args.project, clear=False)
    logger.info(f"Indexed {len(call_graph.functions)} functions and {len(call_graph.missing_functions)} missing functions")
    
    # Show relationship counts
    with neo4j_service.driver.session() as session:
        result = session.run(
            """
            MATCH ()-[r:CALLS]->() WHERE r.project = $project
            RETURN count(r) as call_count
            """,
            project=args.project
        )
        record = result.single()
        if record:
            call_count = record["call_count"]
            logger.info(f"Created {call_count} CALLS relationships")
    
    logger.info("Re-indexing complete")

if __name__ == "__main__":
    main() 