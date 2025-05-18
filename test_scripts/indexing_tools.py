#!/usr/bin/env python3
"""
Consolidated indexing tools for code analysis.
This module combines functionality from:
- clear_and_reindex_folly.py
- index_directory.py
- incremental_index.py
"""

import os
import sys
import argparse
import logging
import time
from pathlib import Path
from datetime import datetime
import json
import platform
import hashlib
from typing import Dict, List, Set, Tuple, Optional, Any, Union
import concurrent.futures
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
import shutil

# Try to import Neo4j and Clang libraries
try:
    from py2neo import Graph, Node, Relationship, NodeMatcher
    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False
    print("Warning: py2neo not installed. Neo4j functionality disabled.")

try:
    import clang.cindex
    from clang.cindex import Index, Cursor, CursorKind, TokenKind
    CLANG_AVAILABLE = True
except ImportError:
    CLANG_AVAILABLE = False
    print("Warning: clang not installed. C++ analysis functionality disabled.")

# Try to import project-specific modules
try:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from src.services.neo4j_service import Neo4jService
    from src.services.clang_analyzer_service import ClangAnalyzerService
    from src.services.compile_commands_service import CompileCommandsService
    from src.models.call_graph import CallGraph
    PROJECT_MODULES_AVAILABLE = True
except ImportError:
    PROJECT_MODULES_AVAILABLE = False
    print("Warning: Project modules not found. Some functionality may be limited.")
    
    # Define minimal CallGraph class for standalone usage
    class CallGraph:
        """Minimal implementation of CallGraph for standalone usage."""
        def __init__(self):
            self.functions = {}
            self.files = set()
            self.function_count = 0
            self.relationship_count = 0
            
        def add_function(self, name, file_path=None, line_number=None, metadata=None):
            """Add a function to the call graph."""
            if name not in self.functions:
                self.functions[name] = {
                    'name': name,
                    'file_path': file_path,
                    'line_number': line_number,
                    'metadata': metadata or {},
                    'calls': set(),
                    'called_by': set()
                }
                self.function_count += 1
                if file_path:
                    self.files.add(file_path)
            return self.functions[name]
            
        def add_call(self, caller, callee):
            """Add a call relationship between two functions."""
            if caller in self.functions and callee in self.functions:
                self.functions[caller]['calls'].add(callee)
                self.functions[callee]['called_by'].add(caller)
                self.relationship_count += 1
                return True
            return False
            
        def merge(self, other_graph):
            """Merge another call graph into this one."""
            for func_name, func_data in other_graph.functions.items():
                if func_name not in self.functions:
                    self.add_function(func_name, func_data['file_path'], 
                                     func_data['line_number'], func_data['metadata'])
                
            # Add relationships after all functions are added
            for func_name, func_data in other_graph.functions.items():
                for callee in func_data['calls']:
                    self.add_call(func_name, callee)
            
            return self

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Default Neo4j connection parameters
DEFAULT_NEO4J_URI = "bolt://localhost:7688"
DEFAULT_NEO4J_USER = "neo4j"
DEFAULT_NEO4J_PASSWORD = "password"
DEFAULT_PROJECT = "folly"

class IndexingManager:
    """Class for managing code indexing operations."""
    
    def __init__(self, 
                 uri: str = DEFAULT_NEO4J_URI, 
                 user: str = DEFAULT_NEO4J_USER, 
                 password: str = DEFAULT_NEO4J_PASSWORD,
                 project: str = DEFAULT_PROJECT):
        """
        Initialize the indexing manager.
        
        Args:
            uri: Neo4j connection URI
            user: Neo4j username
            password: Neo4j password
            project: Project name in Neo4j
        """
        self.uri = uri
        self.user = user
        self.password = password
        self.project = project
        self.neo4j_graph = None
        self.analyzer = None
        self.clang_available = CLANG_AVAILABLE
        self.neo4j_available = NEO4J_AVAILABLE
        
        # Initialize Neo4j connection if available
        if NEO4J_AVAILABLE:
            try:
                self.neo4j_graph = Graph(uri, auth=(user, password))
                logger.info(f"Connected to Neo4j at {uri}")
            except Exception as e:
                logger.error(f"Error connecting to Neo4j: {e}")
                self.neo4j_graph = None
        
        # Initialize analyzer if available
        if PROJECT_MODULES_AVAILABLE and CLANG_AVAILABLE:
            self.analyzer = ClangAnalyzerService()
            logger.info("Clang analyzer service initialized")
    
    def clear_project_data(self, project_name: Optional[str] = None) -> bool:
        """
        Clear all data for a specific project in Neo4j.
        
        Args:
            project_name: Name of the project to clear (defaults to self.project)
            
        Returns:
            bool: Success status
        """
        if not NEO4J_AVAILABLE or not self.neo4j_graph:
            logger.error("Neo4j connection not available")
            return False
            
        project = project_name or self.project
        
        try:
            # Delete all function nodes and relationships for the project
            self.neo4j_graph.run(f"""
                MATCH (n:Function {{project: $project}})
                DETACH DELETE n
            """, project=project)
            
            logger.info(f"Cleared all data for project: {project}")
            return True
        except Exception as e:
            logger.error(f"Error clearing project data: {e}")
            return False
    
    def detect_system_include_paths(self) -> List[str]:
        """
        Detect system include paths based on platform.
        
        Returns:
            List[str]: List of detected system include paths
        """
        system_includes = []
        
        if platform.system() == "Windows":
            # Windows - check common paths
            possible_paths = [
                "C:/Program Files/LLVM/include",
                "C:/Program Files (x86)/Microsoft Visual Studio/2019/Community/VC/Tools/MSVC/14.29.30133/include",
                "C:/Program Files (x86)/Windows Kits/10/Include/10.0.19041.0/ucrt",
            ]
            for path in possible_paths:
                if os.path.exists(path):
                    system_includes.append(path)
        
        elif platform.system() == "Darwin":
            # macOS - check common paths
            possible_paths = [
                "/usr/include",
                "/usr/local/include",
                "/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk/usr/include",
                "/Applications/Xcode.app/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs/MacOSX.sdk/usr/include",
            ]
            for path in possible_paths:
                if os.path.exists(path):
                    system_includes.append(path)
        
        else:
            # Linux - check common paths
            possible_paths = [
                "/usr/include",
                "/usr/local/include",
                "/usr/include/c++/9",  # Adjust version as needed
                "/usr/include/x86_64-linux-gnu",
            ]
            for path in possible_paths:
                if os.path.exists(path):
                    system_includes.append(path)
        
        return system_includes
    
    def heuristic_include_path_detection(self, folder_path: str) -> List[str]:
        """
        Detect potential include paths using heuristics.
        
        Args:
            folder_path: Path to the folder to scan
            
        Returns:
            List[str]: List of detected include paths
        """
        include_paths = []
        
        # Check for common include directory names
        common_include_dirs = ["include", "inc", "headers", "third-party"]
        for root, dirs, _ in os.walk(folder_path):
            for dir_name in dirs:
                if dir_name.lower() in common_include_dirs:
                    include_paths.append(os.path.join(root, dir_name))
        
        # Check for large concentrations of header files
        header_concentrations = {}
        for root, _, files in os.walk(folder_path):
            header_count = sum(1 for f in files if f.endswith(('.h', '.hpp', '.hxx')))
            if header_count > 5:  # Threshold for considering a directory as an include path
                header_concentrations[root] = header_count
        
        # Add directories with many header files
        for path, count in sorted(header_concentrations.items(), key=lambda x: x[1], reverse=True)[:5]:
            if path not in include_paths:
                include_paths.append(path)
        
        return include_paths
    
    def process_file(self, 
                    file_path: str, 
                    include_dirs: List[str] = None, 
                    compiler_args: List[str] = None,
                    analyze_templates: bool = False,
                    track_virtual: bool = False,
                    cross_file_mode: str = "basic") -> Optional[CallGraph]:
        """
        Process a C/C++ file using Clang.
        
        Args:
            file_path: Path to the file to analyze
            include_dirs: List of include directories
            compiler_args: List of compiler arguments
            analyze_templates: Whether to analyze templates
            track_virtual: Whether to track virtual methods
            cross_file_mode: Cross-file analysis mode
            
        Returns:
            CallGraph: Call graph for the file, or None on failure
        """
        if not self.clang_available or not self.analyzer:
            logger.error("Clang analyzer not available")
            return None
        
        try:
            # Set default include dirs if not provided
            if include_dirs is None:
                include_dirs = self.detect_system_include_paths()
                # Add heuristic include paths
                include_dirs.extend(self.heuristic_include_path_detection(os.path.dirname(file_path)))
            
            # Set default compiler args if not provided
            if compiler_args is None:
                compiler_args = ["-std=c++17"]
            
            # Process the file
            call_graph = self.analyzer.analyze_file(
                file_path=file_path,
                include_dirs=include_dirs,
                compiler_args=compiler_args,
                analyze_templates=analyze_templates,
                track_virtual_methods=track_virtual
            )
            
            # Process cross-file references if needed
            if cross_file_mode != "basic" and hasattr(self.analyzer, "process_cross_file_references"):
                call_graph = self.analyzer.process_cross_file_references(call_graph, mode=cross_file_mode)
            
            logger.info(f"Processed file: {file_path} - Found {len(call_graph.functions)} functions")
            return call_graph
        
        except Exception as e:
            logger.error(f"Error processing file {file_path}: {e}")
            return None
    
    def process_directory(self, 
                         directory_path: str, 
                         include_dirs: List[str] = None,
                         compiler_args: List[str] = None,
                         file_extensions: List[str] = None,
                         analyze_templates: bool = False,
                         track_virtual: bool = False,
                         cross_file_mode: str = "basic",
                         parallel: bool = False,
                         max_workers: int = 4,
                         skip_patterns: List[str] = None) -> CallGraph:
        """
        Process a directory of C/C++ files.
        
        Args:
            directory_path: Path to the directory to analyze
            include_dirs: List of include directories
            compiler_args: List of compiler arguments
            file_extensions: List of file extensions to process
            analyze_templates: Whether to analyze templates
            track_virtual: Whether to track virtual methods
            cross_file_mode: Cross-file analysis mode
            parallel: Whether to use parallel processing
            max_workers: Maximum number of parallel workers
            skip_patterns: List of patterns to skip
            
        Returns:
            CallGraph: Combined call graph for all files
        """
        if not self.clang_available or not self.analyzer:
            logger.error("Clang analyzer not available")
            return CallGraph()
        
        # Set default file extensions if not provided
        if file_extensions is None:
            file_extensions = [".cpp", ".cc", ".cxx", ".c++", ".c"]
        
        # Set default skip patterns if not provided
        if skip_patterns is None:
            skip_patterns = ["test", "tests", "example", "examples"]
        
        # Find all matching files
        all_files = []
        for ext in file_extensions:
            for file_path in Path(directory_path).glob(f"**/*{ext}"):
                # Skip files matching skip patterns
                if any(pattern in str(file_path) for pattern in skip_patterns):
                    continue
                all_files.append(str(file_path))
        
        logger.info(f"Found {len(all_files)} files to process in {directory_path}")
        
        # Set default include dirs if not provided
        if include_dirs is None:
            include_dirs = self.detect_system_include_paths()
            # Add heuristic include paths from the directory
            include_dirs.extend(self.heuristic_include_path_detection(directory_path))
        
        # Set default compiler args if not provided
        if compiler_args is None:
            compiler_args = ["-std=c++17"]
        
        # Process files
        call_graphs = []
        
        if parallel and len(all_files) > 1:
            # Use parallel processing
            logger.info(f"Using parallel processing with {max_workers} workers")
            with ProcessPoolExecutor(max_workers=max_workers) as executor:
                future_to_file = {
                    executor.submit(
                        self.process_file, 
                        file_path, 
                        include_dirs, 
                        compiler_args,
                        analyze_templates,
                        track_virtual,
                        cross_file_mode
                    ): file_path for file_path in all_files
                }
                
                for future in concurrent.futures.as_completed(future_to_file):
                    file_path = future_to_file[future]
                    try:
                        call_graph = future.result()
                        if call_graph:
                            call_graphs.append(call_graph)
                    except Exception as e:
                        logger.error(f"Error processing {file_path}: {e}")
        else:
            # Use sequential processing
            logger.info("Using sequential processing")
            for file_path in all_files:
                call_graph = self.process_file(
                    file_path, 
                    include_dirs, 
                    compiler_args,
                    analyze_templates,
                    track_virtual,
                    cross_file_mode
                )
                if call_graph:
                    call_graphs.append(call_graph)
        
        # Merge all call graphs
        combined_graph = CallGraph()
        for graph in call_graphs:
            combined_graph.merge(graph)
        
        logger.info(f"Processed {len(all_files)} files - Found {len(combined_graph.functions)} functions")
        return combined_graph
    
    def store_call_graph(self, 
                        call_graph: CallGraph, 
                        project_name: Optional[str] = None,
                        clear: bool = False) -> bool:
        """
        Store a call graph in Neo4j.
        
        Args:
            call_graph: Call graph to store
            project_name: Name of the project (defaults to self.project)
            clear: Whether to clear existing data for the project
            
        Returns:
            bool: Success status
        """
        if not NEO4J_AVAILABLE or not self.neo4j_graph:
            logger.error("Neo4j connection not available")
            return False
        
        project = project_name or self.project
        
        try:
            # Clear existing data if requested
            if clear:
                self.clear_project_data(project)
            
            # Use Neo4jService if available, otherwise use direct Neo4j operations
            if PROJECT_MODULES_AVAILABLE:
                # Use project's Neo4jService
                neo4j_service = Neo4jService(self.uri, self.user, self.password)
                neo4j_service.index_call_graph(call_graph, project, clear=False)  # already cleared if needed
            else:
                # Direct Neo4j operations
                for func_name, func in call_graph.functions.items():
                    # Create function node
                    func_node = Node("Function", 
                                    name=func_name,
                                    project=project,
                                    file=func.file_path,
                                    line=func.line_number,
                                    is_declaration=func.is_declaration)
                    
                    # Add any additional properties
                    for key, value in func.metadata.items():
                        if isinstance(value, (str, int, float, bool)) or value is None:
                            func_node[key] = value
                    
                    # Create or merge node
                    self.neo4j_graph.merge(func_node, "Function", "name")
                
                # Create call relationships
                matcher = NodeMatcher(self.neo4j_graph)
                
                for func_name, func in call_graph.functions.items():
                    caller_node = matcher.match("Function", name=func_name, project=project).first()
                    
                    if caller_node:
                        for callee_name in func.calls:
                            callee_node = matcher.match("Function", name=callee_name, project=project).first()
                            
                            if callee_node:
                                # Create CALLS relationship
                                rel = Relationship(caller_node, "CALLS", callee_node)
                                self.neo4j_graph.create(rel)
            
            logger.info(f"Stored call graph with {len(call_graph.functions)} functions in Neo4j for project: {project}")
            return True
        
        except Exception as e:
            logger.error(f"Error storing call graph in Neo4j: {e}")
            return False
    
    def incremental_index(self, 
                         directory_path: str,
                         project_name: Optional[str] = None,
                         include_dirs: List[str] = None,
                         compiler_args: List[str] = None,
                         file_extensions: List[str] = None,
                         analyze_templates: bool = False,
                         track_virtual: bool = False,
                         cross_file_mode: str = "basic",
                         parallel: bool = False,
                         max_workers: int = 4) -> bool:
        """
        Incrementally index a directory, only processing changed files.
        
        Args:
            directory_path: Path to the directory to analyze
            project_name: Name of the project (defaults to self.project)
            include_dirs: List of include directories
            compiler_args: List of compiler arguments
            file_extensions: List of file extensions to process
            analyze_templates: Whether to analyze templates
            track_virtual: Whether to track virtual methods
            cross_file_mode: Cross-file analysis mode
            parallel: Whether to use parallel processing
            max_workers: Maximum number of parallel workers
            
        Returns:
            bool: Success status
        """
        if not self.clang_available or not self.analyzer:
            logger.error("Clang analyzer not available")
            return False
        
        if not NEO4J_AVAILABLE or not self.neo4j_graph:
            logger.error("Neo4j connection not available")
            return False
        
        project = project_name or self.project
        
        # Set default file extensions if not provided
        if file_extensions is None:
            file_extensions = [".cpp", ".cc", ".cxx", ".c++", ".c"]
        
        # Find all matching files
        all_files = []
        for ext in file_extensions:
            for file_path in Path(directory_path).glob(f"**/*{ext}"):
                all_files.append(str(file_path))
        
        logger.info(f"Found {len(all_files)} files to check in {directory_path}")
        
        # Find existing files in database
        existing_files = {}
        result = self.neo4j_graph.run("""
            MATCH (f:Function {project: $project})
            RETURN f.file as file, f.hash as hash
        """, project=project)
        
        for record in result:
            file_path = record["file"]
            file_hash = record["hash"]
            if file_path:
                existing_files[file_path] = file_hash
        
        logger.info(f"Found {len(existing_files)} existing files in database")
        
        # Find files that need to be processed
        files_to_process = []
        
        for file_path in all_files:
            # Calculate file hash
            file_hash = self._calculate_file_hash(file_path)
            
            # Check if file exists in database with same hash
            if file_path in existing_files and existing_files[file_path] == file_hash:
                continue  # File hasn't changed
            
            # Add file to processing list
            files_to_process.append(file_path)
        
        logger.info(f"Found {len(files_to_process)} files that need to be processed")
        
        # Process changed files
        if files_to_process:
            # Set default include dirs if not provided
            if include_dirs is None:
                include_dirs = self.detect_system_include_paths()
                # Add heuristic include paths from the directory
                include_dirs.extend(self.heuristic_include_path_detection(directory_path))
            
            # Set default compiler args if not provided
            if compiler_args is None:
                compiler_args = ["-std=c++17"]
            
            # Process files
            call_graphs = []
            
            if parallel and len(files_to_process) > 1:
                # Use parallel processing
                logger.info(f"Using parallel processing with {max_workers} workers")
                with ProcessPoolExecutor(max_workers=max_workers) as executor:
                    future_to_file = {
                        executor.submit(
                            self.process_file, 
                            file_path, 
                            include_dirs, 
                            compiler_args,
                            analyze_templates,
                            track_virtual,
                            cross_file_mode
                        ): file_path for file_path in files_to_process
                    }
                    
                    for future in concurrent.futures.as_completed(future_to_file):
                        file_path = future_to_file[future]
                        try:
                            call_graph = future.result()
                            if call_graph:
                                # Add file hash to function metadata
                                file_hash = self._calculate_file_hash(file_path)
                                for func in call_graph.functions.values():
                                    if func.file_path == file_path:
                                        func.metadata["hash"] = file_hash
                                
                                call_graphs.append(call_graph)
                        except Exception as e:
                            logger.error(f"Error processing {file_path}: {e}")
            else:
                # Use sequential processing
                logger.info("Using sequential processing")
                for file_path in files_to_process:
                    call_graph = self.process_file(
                        file_path, 
                        include_dirs, 
                        compiler_args,
                        analyze_templates,
                        track_virtual,
                        cross_file_mode
                    )
                    if call_graph:
                        # Add file hash to function metadata
                        file_hash = self._calculate_file_hash(file_path)
                        for func in call_graph.functions.values():
                            if func.file_path == file_path:
                                func.metadata["hash"] = file_hash
                        
                        call_graphs.append(call_graph)
            
            # Merge all call graphs
            combined_graph = CallGraph()
            for graph in call_graphs:
                combined_graph.merge(graph)
            
            logger.info(f"Processed {len(files_to_process)} files - Found {len(combined_graph.functions)} functions")
            
            # Store call graph
            self.store_call_graph(combined_graph, project, clear=False)
            
            return True
        else:
            logger.info("No files need to be processed")
            return True
    
    def index_folly(self,
                   folly_path: str,
                   project_name: Optional[str] = None,
                   clear: bool = True,
                   parallel: bool = True,
                   max_workers: int = 4,
                   analyze_templates: bool = True,
                   track_virtual: bool = True,
                   cross_file_mode: str = "enhanced") -> bool:
        """
        Index the Folly codebase.
        
        Args:
            folly_path: Path to the Folly codebase
            project_name: Name of the project (defaults to "folly")
            clear: Whether to clear existing data
            parallel: Whether to use parallel processing
            max_workers: Maximum number of parallel workers
            analyze_templates: Whether to analyze templates
            track_virtual: Whether to track virtual methods
            cross_file_mode: Cross-file analysis mode
            
        Returns:
            bool: Success status
        """
        project = project_name or "folly"
        
        # Check if Folly path exists
        if not os.path.exists(folly_path):
            logger.error(f"Folly path does not exist: {folly_path}")
            return False
        
        # Check for folly directory structure
        folly_core_path = os.path.join(folly_path, "folly")
        if not os.path.exists(folly_core_path):
            logger.warning(f"Could not find core folly directory at {folly_core_path}")
            # Try to find it in subfolders
            for root, dirs, _ in os.walk(folly_path):
                if "folly" in dirs:
                    folly_core_path = os.path.join(root, "folly")
                    logger.info(f"Found folly core directory at {folly_core_path}")
                    break
        
        # Detect include paths
        include_dirs = [
            folly_path,
            folly_core_path,
            os.path.join(folly_path, ".."),  # Parent directory
        ]
        
        # Add system include paths
        include_dirs.extend(self.detect_system_include_paths())
        
        # Use heuristic detection to find more include paths
        include_dirs.extend(self.heuristic_include_path_detection(folly_path))
        
        # Set compiler arguments
        compiler_args = ["-std=c++17", "-DFOLLY_NO_CONFIG"]
        
        # Define file extensions
        file_extensions = [".cpp", ".cc", ".cxx", ".c++"]
        
        # Define skip patterns
        skip_patterns = ["test", "tests", "example", "examples", "benchmark", "benchmarks"]
        
        logger.info(f"Starting indexing of Folly codebase at {folly_path}")
        
        # Process the directory
        call_graph = self.process_directory(
            directory_path=folly_core_path,
            include_dirs=include_dirs,
            compiler_args=compiler_args,
            file_extensions=file_extensions,
            analyze_templates=analyze_templates,
            track_virtual=track_virtual,
            cross_file_mode=cross_file_mode,
            parallel=parallel,
            max_workers=max_workers,
            skip_patterns=skip_patterns
        )
        
        # Store call graph
        success = self.store_call_graph(call_graph, project, clear=clear)
        
        return success
    
    def _calculate_file_hash(self, file_path: str) -> str:
        """
        Calculate a hash for a file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            str: Hash of the file content
        """
        hash_md5 = hashlib.md5()
        
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception as e:
            logger.error(f"Error calculating file hash for {file_path}: {e}")
            return ""

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Code Indexing Tools")
    
    # Main commands
    parser.add_argument("command", choices=["index", "index-incremental", "index-folly", "clear"],
                        help="Command to execute")
    
    # Source/target parameters
    parser.add_argument("--source", "-s", type=str, 
                        help="Source directory or file to index")
    
    # Project parameters
    parser.add_argument("--project", "-p", type=str, default=DEFAULT_PROJECT,
                        help=f"Project name in Neo4j (default: {DEFAULT_PROJECT})")
    parser.add_argument("--clear", action="store_true",
                        help="Clear existing data for the project")
    
    # Neo4j connection parameters
    parser.add_argument("--neo4j-uri", type=str, default=DEFAULT_NEO4J_URI,
                        help=f"Neo4j connection URI (default: {DEFAULT_NEO4J_URI})")
    parser.add_argument("--neo4j-user", type=str, default=DEFAULT_NEO4J_USER,
                        help=f"Neo4j username (default: {DEFAULT_NEO4J_USER})")
    parser.add_argument("--neo4j-password", type=str, default=DEFAULT_NEO4J_PASSWORD,
                        help=f"Neo4j password (default: {DEFAULT_NEO4J_PASSWORD})")
    
    # Processing options
    parser.add_argument("--parallel", action="store_true",
                        help="Use parallel processing")
    parser.add_argument("--workers", type=int, default=4,
                        help="Maximum number of parallel workers")
    parser.add_argument("--extensions", type=str, nargs="+", default=None,
                        help="File extensions to process")
    parser.add_argument("--include-dirs", type=str, nargs="+", default=None,
                        help="Include directories")
    parser.add_argument("--compiler-args", type=str, nargs="+", default=None,
                        help="Compiler arguments")
    
    # Analysis options
    parser.add_argument("--analyze-templates", action="store_true",
                        help="Analyze templates")
    parser.add_argument("--track-virtual", action="store_true",
                        help="Track virtual methods")
    parser.add_argument("--cross-file-mode", choices=["basic", "enhanced", "full"], default="basic",
                        help="Cross-file analysis mode")
    
    # Other options
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Enable verbose logging")
    
    return parser.parse_args()

def main():
    """Main function."""
    args = parse_args()
    
    # Set logging level
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    # Check if Neo4j is available
    if not NEO4J_AVAILABLE:
        logger.error("Neo4j library (py2neo) not available. Please install it.")
        if args.command != "clear":
            return 1
    
    # Check if Clang is available for indexing
    if not CLANG_AVAILABLE and args.command in ["index", "index-incremental", "index-folly"]:
        logger.error("Clang library not available. Please install it.")
        return 1
    
    # Create indexing manager
    indexer = IndexingManager(
        uri=args.neo4j_uri,
        user=args.neo4j_user,
        password=args.neo4j_password,
        project=args.project
    )
    
    # Track time
    start_time = time.time()
    
    # Process command
    if args.command == "clear":
        # Clear project data
        logger.info(f"Clearing data for project: {args.project}")
        success = indexer.clear_project_data(args.project)
    
    elif args.command == "index":
        # Check for source parameter
        if not args.source:
            logger.error("Source parameter is required for indexing")
            return 1
        
        logger.info(f"Indexing source: {args.source}")
        
        # Check if source is a file or directory
        if os.path.isfile(args.source):
            # Process single file
            call_graph = indexer.process_file(
                file_path=args.source,
                include_dirs=args.include_dirs,
                compiler_args=args.compiler_args,
                analyze_templates=args.analyze_templates,
                track_virtual=args.track_virtual,
                cross_file_mode=args.cross_file_mode
            )
            
            if call_graph:
                # Store call graph
                success = indexer.store_call_graph(call_graph, args.project, clear=args.clear)
            else:
                logger.error("Failed to process file")
                success = False
        
        elif os.path.isdir(args.source):
            # Process directory
            call_graph = indexer.process_directory(
                directory_path=args.source,
                include_dirs=args.include_dirs,
                compiler_args=args.compiler_args,
                file_extensions=args.extensions,
                analyze_templates=args.analyze_templates,
                track_virtual=args.track_virtual,
                cross_file_mode=args.cross_file_mode,
                parallel=args.parallel,
                max_workers=args.workers
            )
            
            # Store call graph
            success = indexer.store_call_graph(call_graph, args.project, clear=args.clear)
        
        else:
            logger.error(f"Source does not exist: {args.source}")
            success = False
    
    elif args.command == "index-incremental":
        # Check for source parameter
        if not args.source:
            logger.error("Source parameter is required for incremental indexing")
            return 1
        
        if not os.path.isdir(args.source):
            logger.error(f"Source must be a directory for incremental indexing: {args.source}")
            return 1
        
        logger.info(f"Incremental indexing of source: {args.source}")
        
        # Perform incremental indexing
        success = indexer.incremental_index(
            directory_path=args.source,
            project_name=args.project,
            include_dirs=args.include_dirs,
            compiler_args=args.compiler_args,
            file_extensions=args.extensions,
            analyze_templates=args.analyze_templates,
            track_virtual=args.track_virtual,
            cross_file_mode=args.cross_file_mode,
            parallel=args.parallel,
            max_workers=args.workers
        )
    
    elif args.command == "index-folly":
        # Check for source parameter
        if not args.source:
            logger.error("Source parameter is required for Folly indexing")
            return 1
        
        if not os.path.isdir(args.source):
            logger.error(f"Source must be a directory for Folly indexing: {args.source}")
            return 1
        
        logger.info(f"Indexing Folly codebase at: {args.source}")
        
        # Index Folly codebase
        success = indexer.index_folly(
            folly_path=args.source,
            project_name=args.project,
            clear=args.clear,
            parallel=args.parallel,
            max_workers=args.workers,
            analyze_templates=args.analyze_templates or True,  # Default to True for Folly
            track_virtual=args.track_virtual or True,  # Default to True for Folly
            cross_file_mode=args.cross_file_mode or "enhanced"  # Default to enhanced for Folly
        )
    
    else:
        logger.error(f"Unknown command: {args.command}")
        success = False
    
    # Report time
    elapsed_time = time.time() - start_time
    logger.info(f"Command '{args.command}' completed in {elapsed_time:.2f} seconds")
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main()) 