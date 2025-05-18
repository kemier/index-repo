#!/usr/bin/env python
"""
Script to analyze pure C codebases using ClangAnalyzerService.

This script analyzes function dependencies and relationships in C code.
"""
import os
import sys
import logging
import json
from pathlib import Path
from typing import Dict, List, Set, Any, Optional
from collections import defaultdict

# Add parent directory to path to import project modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.clang_analyzer_service import ClangAnalyzerService

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CCodeAnalyzer:
    """
    Analyzes C codebase structure and function relationships.
    """
    
    def __init__(self, directory_path: str, file_paths: List[str] = None):
        """Initialize the analyzer with directory or specific files to analyze."""
        self.directory_path = directory_path
        self.file_paths = file_paths
        self.analyzer = ClangAnalyzerService()
        self.call_graph = None
        self.results = {}
        
    def analyze(self) -> Dict[str, Any]:
        """
        Perform analysis on C codebase and return results.
        
        Returns:
            Dict containing analysis results
        """
        if self.file_paths:
            logger.info(f"Analyzing {len(self.file_paths)} files in {self.directory_path}")
            # Analyze specific files
            self.call_graph = self._analyze_files(self.file_paths)
        else:
            logger.info(f"Analyzing entire directory: {self.directory_path}")
            # Analyze all C files in directory
            self.call_graph = self._analyze_directory(self.directory_path)
            
        if not self.call_graph or not self.call_graph.functions:
            logger.error("Analysis failed or no functions found")
            return {}
            
        # Extract results
        self.results = {
            "total_functions": len(self.call_graph.functions),
            "function_names": list(self.call_graph.functions.keys()),
            "function_by_file": self._group_functions_by_file(),
            "module_dependencies": self._analyze_module_dependencies(),
            "function_call_relationships": self._analyze_function_calls(),
            "heavily_used_functions": self._find_heavily_used_functions(),
            "call_tree_depths": self._calculate_call_tree_depths(),
            "external_dependencies": self._find_external_dependencies(),
            "missing_functions": list(self.call_graph.missing_functions),
        }
        
        return self.results
    
    def _analyze_files(self, file_paths: List[str]):
        """Analyze a list of C files and return combined call graph."""
        if not file_paths:
            return None
            
        combined_call_graph = None
        
        for file_path in file_paths:
            if not os.path.exists(file_path):
                logger.warning(f"File not found: {file_path}")
                continue
                
            logger.info(f"Analyzing file: {file_path}")
            file_call_graph = self.analyzer.analyze_file(file_path)
            
            if combined_call_graph is None:
                combined_call_graph = file_call_graph
            else:
                # Merge function definitions
                for func_name, func in file_call_graph.functions.items():
                    if func_name in combined_call_graph.functions:
                        # Function already exists, merge calls
                        existing_func = combined_call_graph.functions[func_name]
                        for called in func.calls:
                            if called not in existing_func.calls:
                                existing_func.calls.append(called)
                        for caller in func.called_by:
                            if caller not in existing_func.called_by:
                                existing_func.called_by.append(caller)
                    else:
                        # New function, add to call graph
                        combined_call_graph.add_function(func)
                
                # Merge missing functions
                for missing_func in file_call_graph.missing_functions:
                    combined_call_graph.add_missing_function(missing_func)
                    
        return combined_call_graph
    
    def _analyze_directory(self, directory_path: str):
        """Analyze all C files in a directory recursively."""
        if not os.path.isdir(directory_path):
            logger.error(f"Directory not found: {directory_path}")
            return None
            
        # Find all C files
        c_files = []
        for root, _, files in os.walk(directory_path):
            for file in files:
                if file.endswith(('.c', '.h')):
                    c_files.append(os.path.join(root, file))
                    
        logger.info(f"Found {len(c_files)} C files to analyze")
        
        return self._analyze_files(c_files)
    
    def _group_functions_by_file(self) -> Dict[str, List[str]]:
        """Group functions by their source files."""
        file_functions = defaultdict(list)
        
        for func_name, func in self.call_graph.functions.items():
            if func.file_path:
                # Use relative path if it's in the directory
                rel_path = func.file_path
                if self.directory_path and rel_path.startswith(self.directory_path):
                    rel_path = os.path.relpath(rel_path, self.directory_path)
                file_functions[rel_path].append(func_name)
                
        return dict(file_functions)
    
    def _analyze_module_dependencies(self) -> Dict[str, List[str]]:
        """
        Analyze module dependencies based on function calls between files.
        
        Returns a dictionary mapping from source file to the list of files it depends on.
        """
        module_deps = defaultdict(set)
        
        # For each function call, determine the source and target files
        for func_name, func in self.call_graph.functions.items():
            source_file = func.file_path
            if not source_file:
                continue
                
            # Make paths relative to directory
            source_file_rel = source_file
            if self.directory_path and source_file.startswith(self.directory_path):
                source_file_rel = os.path.relpath(source_file, self.directory_path)
                
            # Check all called functions
            for called_name in func.calls:
                if called_name in self.call_graph.functions:
                    called_func = self.call_graph.functions[called_name]
                    target_file = called_func.file_path
                    
                    if target_file and target_file != source_file:
                        target_file_rel = target_file
                        if self.directory_path and target_file.startswith(self.directory_path):
                            target_file_rel = os.path.relpath(target_file, self.directory_path)
                            
                        module_deps[source_file_rel].add(target_file_rel)
                        
        # Convert set to list for JSON serialization
        return {k: list(v) for k, v in module_deps.items()}
    
    def _analyze_function_calls(self) -> List[Dict[str, str]]:
        """Extract all function call relationships."""
        calls = []
        
        for func_name, func in self.call_graph.functions.items():
            for called_name in func.calls:
                calls.append({
                    "caller": func_name,
                    "callee": called_name,
                    "caller_file": func.file_path,
                    "callee_file": self.call_graph.functions[called_name].file_path if called_name in self.call_graph.functions else "unknown"
                })
                
        return calls
    
    def _find_heavily_used_functions(self, threshold: int = 5) -> List[Dict[str, Any]]:
        """Find functions that are called by many other functions."""
        heavily_used = []
        
        for func_name, func in self.call_graph.functions.items():
            if len(func.called_by) >= threshold:
                heavily_used.append({
                    "name": func_name,
                    "called_by_count": len(func.called_by),
                    "file_path": func.file_path,
                    "callers": func.called_by
                })
                
        # Sort by called_by_count in descending order
        heavily_used.sort(key=lambda x: x["called_by_count"], reverse=True)
        return heavily_used
    
    def _calculate_call_tree_depths(self, max_depth: int = 10) -> Dict[str, int]:
        """
        Calculate the depth of the call tree for each function.
        
        Returns a dictionary mapping function names to their maximum call tree depth.
        """
        depths = {}
        
        def calculate_depth(func_name, visited, current_depth=0):
            if current_depth >= max_depth:
                return current_depth
                
            if func_name in visited:
                return current_depth  # Avoid cycles
                
            if func_name not in self.call_graph.functions:
                return current_depth
                
            visited.add(func_name)
            func = self.call_graph.functions[func_name]
            
            if not func.calls:
                return current_depth
                
            max_call_depth = current_depth
            for called_name in func.calls:
                call_depth = calculate_depth(called_name, visited.copy(), current_depth + 1)
                max_call_depth = max(max_call_depth, call_depth)
                
            return max_call_depth
        
        # Calculate depth for each function
        for func_name in self.call_graph.functions:
            depths[func_name] = calculate_depth(func_name, set())
            
        return depths
    
    def _find_external_dependencies(self) -> List[str]:
        """Identify likely external library dependencies."""
        # Common C library functions and their parent libraries
        c_libs = {
            "printf": "stdio.h", "fprintf": "stdio.h", "sprintf": "stdio.h", 
            "malloc": "stdlib.h", "free": "stdlib.h", "calloc": "stdlib.h", "realloc": "stdlib.h",
            "memcpy": "string.h", "strcpy": "string.h", "strcat": "string.h", "strcmp": "string.h",
            "socket": "sys/socket.h", "connect": "sys/socket.h", "bind": "sys/socket.h",
            "open": "fcntl.h", "read": "unistd.h", "write": "unistd.h", "close": "unistd.h",
            "pthread_create": "pthread.h", "pthread_join": "pthread.h",
            "SSL_new": "openssl/ssl.h", "SSL_connect": "openssl/ssl.h",
        }
        
        external_deps = set()
        
        # Check for calls to known external functions
        for func in self.call_graph.functions.values():
            for called_name in func.calls:
                # Check if it's a missing function (likely external)
                if called_name in self.call_graph.missing_functions:
                    # Check if it's a known C library function
                    if called_name in c_libs:
                        external_deps.add(c_libs[called_name])
                    else:
                        # Otherwise just add the function name
                        external_deps.add(called_name)
                        
        return list(external_deps)
    
    def print_results(self) -> None:
        """Print analysis results in a human-readable format."""
        if not self.results:
            logger.error("No results to print. Run analyze() first.")
            return
            
        print("\n===== C CODE ANALYSIS RESULTS =====\n")
        
        # Print basic statistics
        print(f"Total functions: {self.results['total_functions']}")
        print(f"Missing function references: {len(self.results['missing_functions'])}")
        
        # Print functions by file (top 5 files)
        print("\n=== FILES AND FUNCTION COUNTS ===")
        file_counts = [(file, len(funcs)) for file, funcs in self.results['function_by_file'].items()]
        file_counts.sort(key=lambda x: x[1], reverse=True)
        for file, count in file_counts[:5]:
            print(f"{file}: {count} functions")
        
        # Print module dependencies
        print("\n=== MODULE DEPENDENCIES ===")
        module_deps = self.results['module_dependencies']
        if module_deps:
            for source, targets in list(module_deps.items())[:5]:  # Show top 5
                print(f"{source} depends on: {', '.join(targets[:3])}{'...' if len(targets) > 3 else ''}")
        else:
            print("No module dependencies detected.")
        
        # Print heavily used functions
        print("\n=== HEAVILY USED FUNCTIONS ===")
        heavily_used = self.results['heavily_used_functions']
        if heavily_used:
            for func in heavily_used[:5]:  # Show top 5
                print(f"{func['name']} (from {os.path.basename(func['file_path'])}) - called by {func['called_by_count']} functions")
        else:
            print("No heavily used functions detected.")
        
        # Print deepest call trees
        print("\n=== DEEPEST CALL TREES ===")
        depths = self.results['call_tree_depths']
        sorted_depths = sorted(depths.items(), key=lambda x: x[1], reverse=True)
        for func, depth in sorted_depths[:5]:  # Show top 5
            print(f"{func} - call depth: {depth}")
        
        # Print external dependencies
        print("\n=== EXTERNAL DEPENDENCIES ===")
        external_deps = self.results['external_dependencies']
        if external_deps:
            for dep in sorted(external_deps):
                print(f"- {dep}")
        else:
            print("No external dependencies detected.")
    
    def export_results(self, output_file: str) -> None:
        """Export analysis results to a JSON file."""
        if not self.results:
            logger.error("No results to export. Run analyze() first.")
            return
            
        with open(output_file, 'w') as f:
            json.dump(self.results, f, indent=2)
            
        logger.info(f"Results exported to {output_file}")
        
    def generate_dot_file(self, output_file: str, max_nodes: int = 100) -> None:
        """
        Generate a DOT file for visualization with GraphViz.
        
        Args:
            output_file: Path to save the DOT file
            max_nodes: Maximum number of nodes to include in the graph
        """
        if not self.call_graph:
            logger.error("No call graph to visualize. Run analyze() first.")
            return
            
        # Start DOT file
        dot_content = [
            'digraph "Call Graph" {',
            '  node [shape=box, style=filled, fillcolor=lightblue];',
            '  rankdir=LR;',
            '  concentrate=true;'
        ]
        
        # Get the most important functions (by called_by count)
        important_funcs = []
        for name, func in self.call_graph.functions.items():
            if len(func.called_by) > 0 or len(func.calls) > 0:
                important_funcs.append((name, len(func.called_by) + len(func.calls)))
        
        important_funcs.sort(key=lambda x: x[1], reverse=True)
        important_funcs = [f[0] for f in important_funcs[:max_nodes]]
        
        # Add nodes
        for func_name in important_funcs:
            func = self.call_graph.functions[func_name]
            file_name = os.path.basename(func.file_path) if func.file_path else "unknown"
            label = f"{func_name}\\n({file_name})"
            dot_content.append(f'  "{func_name}" [label="{label}"];')
        
        # Add edges for calls
        added_edges = set()
        for func_name in important_funcs:
            func = self.call_graph.functions[func_name]
            for called_name in func.calls:
                if called_name in important_funcs:
                    edge = f"{func_name}->{called_name}"
                    if edge not in added_edges:
                        dot_content.append(f'  "{func_name}" -> "{called_name}";')
                        added_edges.add(edge)
        
        # Close DOT file
        dot_content.append('}')
        
        # Write to file
        with open(output_file, 'w') as f:
            f.write('\n'.join(dot_content))
            
        logger.info(f"DOT file generated at {output_file}")


def main():
    """Main function to run the C code analyzer."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Analyze C codebase structure and function relationships")
    parser.add_argument("--dir", "-d", required=True, help="Directory containing C code to analyze")
    parser.add_argument("--files", "-f", nargs='+', help="Specific C files to analyze (instead of entire directory)")
    parser.add_argument("--output", "-o", help="Output JSON file for results")
    parser.add_argument("--dot", help="Generate DOT file for visualization")
    
    args = parser.parse_args()
    
    # Validate directory path
    if not os.path.isdir(args.dir):
        logger.error(f"Directory not found: {args.dir}")
        return 1
        
    # Run the analyzer
    analyzer = CCodeAnalyzer(args.dir, args.files)
    analyzer.analyze()
    analyzer.print_results()
    
    # Export results if requested
    if args.output:
        analyzer.export_results(args.output)
    
    # Generate DOT file if requested
    if args.dot:
        analyzer.generate_dot_file(args.dot)
    
    return 0


if __name__ == "__main__":
    sys.exit(main()) 