#!/usr/bin/env python
"""
Generate a complete call graph visualization for Folly library.
This script analyzes Folly source code, extracts function relationships,
and creates a visual representation of the call graph in PNG format.
"""
import os
import sys
import time
import logging
import argparse
from pathlib import Path

# Add parent directory to path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.clang_analyzer_service import ClangAnalyzerService
from src.services.neo4j_service import Neo4jService
from src.services.compile_commands_service import CompileCommandsService
from src.utils.visualization import CallGraphVisualizer

def setup_logging():
    """Configure logging for the script."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("folly_graph_generation.log")
        ]
    )
    return logging.getLogger(__name__)

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Generate Folly call graph visualization")
    parser.add_argument(
        "--source", 
        required=True,
        help="Path to Folly source directory"
    )
    parser.add_argument(
        "--output",
        default="folly_callgraph.png",
        help="Output PNG filename (default: folly_callgraph.png)"
    )
    parser.add_argument(
        "--project",
        default="folly",
        help="Project name in Neo4j database (default: folly)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=1000,
        help="Maximum number of functions to include (default: 1000)"
    )
    parser.add_argument(
        "--depth",
        type=int,
        default=2,
        help="Maximum call depth to analyze (default: 2)"
    )
    parser.add_argument(
        "--focus",
        help="Focus on a specific function or namespace"
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
        "--skip-analysis",
        action="store_true",
        help="Skip analysis and use existing data in Neo4j"
    )
    return parser.parse_args()

def main():
    """Main function to generate Folly call graph."""
    args = parse_arguments()
    logger = setup_logging()
    
    start_time = time.time()
    logger.info(f"Starting Folly call graph generation for {args.source}")
    
    # Ensure output directory exists
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Connect to Neo4j
    neo4j_service = Neo4jService(
        uri=args.neo4j_uri,
        username=args.neo4j_user,
        password=args.neo4j_password
    )
    
    # Analyze source code if not skipped
    if not args.skip_analysis:
        logger.info("Analyzing Folly source code...")
        
        # Setup compile commands service to detect include paths
        compile_commands_service = CompileCommandsService()
        compile_commands_path = compile_commands_service.find_compile_commands(args.source)
        
        if compile_commands_path:
            logger.info(f"Found compile_commands.json at {compile_commands_path}")
            compile_commands_service.load_compile_commands(compile_commands_path)
        else:
            logger.warning("No compile_commands.json found. Include paths may be incomplete.")
        
        # Initialize analyzer
        analyzer = ClangAnalyzerService()
        
        # Analyze source directory
        logger.info(f"Analyzing directory: {args.source} with {args.workers} workers")
        call_graph = analyzer.analyze_directory(
            directory_path=args.source,
            project_name=args.project,
            clear=True,
            file_extensions=['.cpp', '.cc', '.cxx'],
            max_workers=args.workers
        )
        
        # Store results in Neo4j
        logger.info(f"Storing analysis results in Neo4j ({args.project})...")
        neo4j_service.index_call_graph(call_graph, args.project, clear=True)
        logger.info(f"Indexed {len(call_graph.functions)} functions in Neo4j")
    else:
        logger.info("Skipping analysis, using existing Neo4j data...")
    
    # Generate visualization
    logger.info("Generating call graph visualization...")
    visualizer = CallGraphVisualizer(neo4j_service)
    
    # Set up visualization parameters
    visualization_params = {
        "project": args.project,
        "depth": args.depth,
        "limit": args.limit,
        "output_path": args.output,
        "focus": args.focus,
        "include_templates": True,
        "include_virtuals": True,
        "color_by_namespace": True
    }
    
    try:
        visualizer.generate_call_graph(**visualization_params)
        logger.info(f"Call graph visualization saved to {args.output}")
    except Exception as e:
        logger.error(f"Error generating visualization: {e}")
        # Fallback to simpler visualization if needed
        try:
            logger.info("Attempting simplified visualization...")
            simplified_params = {**visualization_params, "depth": 1, "limit": 500}
            visualizer.generate_call_graph(**simplified_params)
            logger.info(f"Simplified call graph visualization saved to {args.output}")
        except Exception as e2:
            logger.error(f"Simplified visualization also failed: {e2}")
    
    elapsed_time = time.time() - start_time
    logger.info(f"Completed in {elapsed_time:.2f} seconds")

if __name__ == "__main__":
    main() 