"""
Controller for coordinating analysis operations
"""
import os
import sys
import argparse
from typing import List, Dict, Set, Optional, Tuple

from src.models.function_model import CallGraph
from src.services.analyzer_service import AnalyzerService
from src.services.search_service import SearchService
from src.services.neo4j_service import Neo4jService
from src.utils.file_utils import ensure_dir
from src.config.settings import (
    DEFAULT_FILE_PATTERNS, 
    CFLOW_PATH, 
    ANALYSIS_DIR, 
    STUBS_DIR,
    NEOJ4_URI,
    NEO4J_USERNAME,
    NEO4J_PASSWORD,
    NEO4J_DEFAULT_PROJECT
)


class AnalysisController:
    """Controller for analysis operations"""
    
    def __init__(self, cflow_path: str = CFLOW_PATH):
        """Initialize the analysis controller"""
        self.analyzer_service = AnalyzerService(cflow_path)
        self.search_service = SearchService()
        self.neo4j_service = Neo4jService(
            uri=NEOJ4_URI,
            username=NEO4J_USERNAME,
            password=NEO4J_PASSWORD
        )
        
    def run(self, args: List[str] = None) -> None:
        """Run the analysis controller with command line arguments"""
        parser = self._create_argument_parser()
        parsed_args = parser.parse_args(args if args is not None else sys.argv[1:])
        
        if parsed_args.command == "analyze":
            self._handle_analyze_command(parsed_args)
        elif parsed_args.command == "search":
            self._handle_search_command(parsed_args)
        elif parsed_args.command == "fix":
            self._handle_fix_command(parsed_args)
        elif parsed_args.command == "index":
            self._handle_index_command(parsed_args)
        elif parsed_args.command == "query":
            self._handle_query_command(parsed_args)
        else:
            parser.print_help()
    
    def _create_argument_parser(self) -> argparse.ArgumentParser:
        """Create the argument parser for the controller"""
        parser = argparse.ArgumentParser(description="Code analysis and function search tool")
        subparsers = parser.add_subparsers(dest="command", help="Command to execute")
        
        # Analyze command
        analyze_parser = subparsers.add_parser("analyze", help="Analyze code to find function calls")
        analyze_parser.add_argument("path", help="Path to file or directory to analyze")
        analyze_parser.add_argument("--output", "-o", help="Output file for analysis results")
        analyze_parser.add_argument("--pattern", "-p", default=DEFAULT_FILE_PATTERNS, 
                                   help="File pattern to analyze (comma-separated)")
        
        # Search command
        search_parser = subparsers.add_parser("search", help="Search for functions in codebase")
        search_parser.add_argument("functions", help="Comma-separated list of functions to search for")
        search_parser.add_argument("path", help="Path to search in")
        search_parser.add_argument("--pattern", "-p", default=DEFAULT_FILE_PATTERNS,
                                  help="File pattern to search (comma-separated)")
        
        # Fix command
        fix_parser = subparsers.add_parser("fix", help="Generate stubs for missing functions")
        fix_parser.add_argument("missing_file", help="File with list of missing functions")
        fix_parser.add_argument("output_file", help="Output file for generated stubs")
        
        # Index command (new)
        index_parser = subparsers.add_parser("index", help="Index code in Neo4j graph database")
        index_parser.add_argument("path", help="Path to file or directory to analyze and index")
        index_parser.add_argument("--project", "-p", default=NEO4J_DEFAULT_PROJECT,
                                help="Project name to use in the database")
        index_parser.add_argument("--pattern", default=DEFAULT_FILE_PATTERNS,
                                help="File pattern to analyze (comma-separated)")
        index_parser.add_argument("--clear", "-c", action="store_true",
                                help="Clear existing data before indexing")
        
        # Query command (new)
        query_parser = subparsers.add_parser("query", help="Query the Neo4j graph database")
        query_subparsers = query_parser.add_subparsers(dest="query_type", help="Type of query")
        
        # Function query
        function_parser = query_subparsers.add_parser("function", help="Query information about a function")
        function_parser.add_argument("name", help="Function name to query")
        function_parser.add_argument("--project", "-p", default=NEO4J_DEFAULT_PROJECT,
                                   help="Project name to query")
        
        # Callers query
        callers_parser = query_subparsers.add_parser("callers", help="Find functions that call a given function")
        callers_parser.add_argument("name", help="Function name to find callers for")
        callers_parser.add_argument("--project", "-p", default=NEO4J_DEFAULT_PROJECT,
                                  help="Project name to query")
        callers_parser.add_argument("--depth", "-d", type=int, default=1,
                                  help="Depth of caller relationships to traverse")
        
        # Callees query
        callees_parser = query_subparsers.add_parser("callees", help="Find functions called by a given function")
        callees_parser.add_argument("name", help="Function name to find callees for")
        callees_parser.add_argument("--project", "-p", default=NEO4J_DEFAULT_PROJECT,
                                  help="Project name to query")
        callees_parser.add_argument("--depth", "-d", type=int, default=1,
                                  help="Depth of callee relationships to traverse")
        
        # Missing functions query
        missing_parser = query_subparsers.add_parser("missing", help="Find missing functions")
        missing_parser.add_argument("--project", "-p", default=NEO4J_DEFAULT_PROJECT,
                                  help="Project name to query")
        
        return parser
    
    def _handle_analyze_command(self, args) -> None:
        """Handle the analyze command"""
        path = args.path
        
        if os.path.isfile(path):
            call_graph = self.analyzer_service.analyze_file(path)
        elif os.path.isdir(path):
            call_graph = self.analyzer_service.analyze_directory(path, args.pattern)
        else:
            print(f"Error: Path {path} not found")
            return
        
        missing_functions = self.analyzer_service.find_missing_functions(call_graph)
        
        print(f"Analysis complete. Found {len(call_graph.functions)} functions and {len(missing_functions)} missing functions.")
        
        if args.output:
            output_file = args.output
        else:
            # Use default output location
            output_name = os.path.basename(path).split('.')[0] + "_analysis.txt"
            output_file = os.path.join(ANALYSIS_DIR, output_name)
            
        self._save_analysis_results(call_graph, missing_functions, output_file)
    
    def _handle_search_command(self, args) -> None:
        """Handle the search command"""
        functions = [f.strip() for f in args.functions.split(",")]
        path = args.path
        
        results = self.search_service.search_functions(functions, path, args.pattern)
        
        for func_name, locations in results.items():
            if locations:
                print(f"Function '{func_name}' found in {len(locations)} locations:")
                for location in locations:
                    print(f"  - {location}")
            else:
                print(f"Function '{func_name}' not found")
    
    def _handle_fix_command(self, args) -> None:
        """Handle the fix command"""
        if not os.path.exists(args.missing_file):
            print(f"Error: Missing functions file {args.missing_file} not found")
            return
        
        with open(args.missing_file, 'r') as f:
            missing_functions = [line.strip() for line in f if line.strip()]
        
        if not missing_functions:
            print("No missing functions found in the file")
            return
        
        stubs = self.search_service.generate_function_stubs(missing_functions)
        
        # Use provided output file or default
        if args.output_file:
            output_file = args.output_file
        else:
            output_file = os.path.join(STUBS_DIR, "missing_functions.h")
            
        ensure_dir(os.path.dirname(output_file))
        with open(output_file, 'w') as f:
            f.write(stubs)
        
        print(f"Generated stubs for {len(missing_functions)} functions in {output_file}")
    
    def _handle_index_command(self, args) -> None:
        """Handle the index command"""
        # First check Neo4j connection
        if not self.neo4j_service.test_connection():
            print("Error: Unable to connect to Neo4j database. Please make sure Neo4j is running.")
            return
        
        # Clear database if requested
        if args.clear:
            print("Clearing existing data from Neo4j database...")
            self.neo4j_service.clear_database()
        
        # Analyze the code
        path = args.path
        print(f"Analyzing code at {path}...")
        
        if os.path.isfile(path):
            call_graph = self.analyzer_service.analyze_file(path)
        elif os.path.isdir(path):
            call_graph = self.analyzer_service.analyze_directory(path, args.pattern)
        else:
            print(f"Error: Path {path} not found")
            return
        
        # Index the call graph in Neo4j
        print(f"Indexing {len(call_graph.functions)} functions in Neo4j...")
        self.neo4j_service.index_call_graph(call_graph, args.project)
        
        print(f"Indexing complete. Indexed {len(call_graph.functions)} functions in project '{args.project}'.")
    
    def _handle_query_command(self, args) -> None:
        """Handle the query command"""
        # Check Neo4j connection
        if not self.neo4j_service.test_connection():
            print("Error: Unable to connect to Neo4j database. Please make sure Neo4j is running.")
            return
        
        if args.query_type == "function":
            # Query function information
            function = self.neo4j_service.find_function(args.name, args.project)
            if function:
                print(f"Function: {args.name}")
                print(f"Project: {args.project}")
                print(f"File: {function.get('file_path', 'Unknown')}")
                print(f"Line: {function.get('line_number', 'Unknown')}")
                print(f"Defined: {function.get('is_defined', False)}")
            else:
                print(f"Function '{args.name}' not found in project '{args.project}'")
        
        elif args.query_type == "callers":
            # Query function callers
            callers = self.neo4j_service.find_callers(args.name, args.project, args.depth)
            if callers:
                print(f"Functions that call '{args.name}' (depth {args.depth}):")
                for i, caller in enumerate(callers, 1):
                    print(f"  {i}. {caller.get('name')} in {caller.get('file_path', 'Unknown')}")
            else:
                print(f"No callers found for function '{args.name}' in project '{args.project}'")
        
        elif args.query_type == "callees":
            # Query function callees
            callees = self.neo4j_service.find_callees(args.name, args.project, args.depth)
            if callees:
                print(f"Functions called by '{args.name}' (depth {args.depth}):")
                for i, callee in enumerate(callees, 1):
                    print(f"  {i}. {callee.get('name')} in {callee.get('file_path', 'Unknown')}")
            else:
                print(f"No callees found for function '{args.name}' in project '{args.project}'")
        
        elif args.query_type == "missing":
            # Query missing functions
            missing = self.neo4j_service.find_missing_functions(args.project)
            if missing:
                print(f"Missing functions in project '{args.project}':")
                for i, func_name in enumerate(missing, 1):
                    print(f"  {i}. {func_name}")
            else:
                print(f"No missing functions found in project '{args.project}'")
        
        else:
            print("Error: Invalid query type. Use 'function', 'callers', 'callees', or 'missing'.")
    
    def _save_analysis_results(self, call_graph: CallGraph, missing_functions: Set[str], output_file: str) -> None:
        """Save analysis results to a file"""
        ensure_dir(os.path.dirname(output_file))
        
        with open(output_file, 'w') as f:
            f.write("Analysis Results\n")
            f.write("===============\n\n")
            
            f.write(f"Total functions found: {len(call_graph.functions)}\n")
            f.write(f"Missing functions: {len(missing_functions)}\n\n")
            
            f.write("Function Call Graph:\n")
            for func_name, func in call_graph.functions.items():
                f.write(f"\n{func_name} [{func.file_path}:{func.line_number}]\n")
                if func.calls:
                    f.write("  Calls:\n")
                    for call in func.calls:
                        f.write(f"    - {call}\n")
                if func.called_by:
                    f.write("  Called by:\n")
                    for caller in func.called_by:
                        f.write(f"    - {caller}\n")
            
            f.write("\nMissing Functions:\n")
            for missing in sorted(missing_functions):
                f.write(f"  - {missing}\n")
        
        print(f"Results saved to {output_file}") 