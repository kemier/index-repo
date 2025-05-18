#!/usr/bin/env python
"""
Script to clear existing Folly data from Neo4j and re-index the Folly repository.
Enhanced with improved C++ feature handling, include path detection, cross-file analysis,
and performance metrics collection.
"""
import os
import sys
import logging
import argparse
import time
import platform
import json
import psutil
from pathlib import Path
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor, as_completed
from collections import defaultdict, Counter

# Add parent directory to path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.neo4j_service import Neo4jService
from src.services.clang_analyzer_service import ClangAnalyzerService
from src.services.compile_commands_service import CompileCommandsService
from src.models.call_graph import CallGraph

def setup_logging(log_file=None):
    """Configure logging for the script."""
    log_format = '%(asctime)s - %(levelname)s - %(message)s'
    if log_file:
        logging.basicConfig(
            level=logging.INFO,
            format=log_format,
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
    else:
        logging.basicConfig(
            level=logging.INFO,
            format=log_format
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
    parser.add_argument(
        "--output-metrics",
        action="store_true",
        help="Output detailed metrics to a JSON file"
    )
    parser.add_argument(
        "--enhanced-template-handling",
        action="store_true",
        help="Enable enhanced template handling (might increase analysis time)"
    )
    parser.add_argument(
        "--track-virtual-methods",
        action="store_true",
        help="Enable tracking of virtual method overrides"
    )
    parser.add_argument(
        "--fallback-include-dirs",
        type=str,
        nargs="+",
        help="Fallback include directories if compile_commands.json is not found"
    )
    parser.add_argument(
        "--cross-file-mode",
        choices=["basic", "enhanced", "full"],
        default="basic",
        help="Cross-file analysis mode: basic (faster), enhanced (balanced), full (slower)"
    )
    return parser.parse_args()

def detect_system_include_paths():
    """Detect system include paths based on platform."""
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

def heuristic_include_path_detection(folder_path):
    """Detect potential include paths using heuristics."""
    include_paths = []
    
    # Check for common include directory names
    common_include_dirs = ["include", "inc", "headers", "third-party"]
    for root, dirs, _ in os.walk(folder_path):
        for dir_name in dirs:
            if dir_name.lower() in common_include_dirs:
                include_paths.append(os.path.join(root, dir_name))
    
    # Check for large concentrations of header files
    header_concentrations = defaultdict(int)
    for root, _, files in os.walk(folder_path):
        header_count = sum(1 for f in files if f.endswith(('.h', '.hpp', '.hxx')))
        if header_count > 5:  # Threshold for considering a directory as an include path
            header_concentrations[root] = header_count
    
    # Add directories with many header files
    for path, count in sorted(header_concentrations.items(), key=lambda x: x[1], reverse=True)[:5]:
        if path not in include_paths:
            include_paths.append(path)
    
    return include_paths

def measure_memory_usage():
    """Get current memory usage."""
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / 1024 / 1024  # Convert to MB

def collect_metrics(start_time, files_analyzed, functions_found, call_relationships, file_metrics):
    """Collect analysis metrics."""
    end_time = time.time()
    
    metrics = {
        "start_time": datetime.fromtimestamp(start_time).isoformat(),
        "end_time": datetime.fromtimestamp(end_time).isoformat(),
        "total_duration_seconds": end_time - start_time,
        "files_analyzed": files_analyzed,
        "functions_found": functions_found,
        "call_relationships": call_relationships,
        "memory_usage_mb": measure_memory_usage(),
        "file_metrics": file_metrics,
        "system_info": {
            "platform": platform.system(),
            "processor": platform.processor(),
            "python_version": platform.python_version()
        }
    }
    
    return metrics

def analyze_file(analyzer, file_path, include_dirs, compiler_args, analyze_templates=False, track_virtual=False):
    """Analyze a single file with metrics."""
    start_time = time.time()
    memory_before = measure_memory_usage()
    
    # Set additional parameters for enhanced features
    analyzer_options = {
        "analyze_templates": analyze_templates,
        "track_virtual_methods": track_virtual
    }
    
    # Analyze the file
    file_call_graph = analyzer.analyze_file(
        file_path, include_dirs, compiler_args, **analyzer_options
    )
    
    end_time = time.time()
    memory_after = measure_memory_usage()
    
    # Collect file-specific metrics
    c_features = {
        "templates": 0,
        "virtual_methods": 0,
        "namespaces": set(),
        "classes": set()
    }
    
    # Count features in functions
    for func_name, func in file_call_graph.functions.items():
        if "template" in func.metadata:
            c_features["templates"] += 1
        if "virtual" in func.metadata and func.metadata["virtual"]:
            c_features["virtual_methods"] += 1
        if "class" in func.metadata:
            c_features["classes"].add(func.metadata["class"])
        if "namespace" in func.metadata:
            c_features["namespaces"].add(func.metadata["namespace"])
    
    # Convert sets to counts
    c_features["namespaces"] = len(c_features["namespaces"])
    c_features["classes"] = len(c_features["classes"])
    
    metrics = {
        "file_path": str(file_path),
        "analysis_time": end_time - start_time,
        "memory_delta_mb": memory_after - memory_before,
        "functions_count": len(file_call_graph.functions),
        "missing_functions_count": len(file_call_graph.missing_functions),
        "call_relationships": sum(len(func.calls) for func in file_call_graph.functions.values()),
        "cpp_features": c_features
    }
    
    return file_call_graph, metrics

def process_cross_file_references(call_graph, mode="basic"):
    """
    Process cross-file references to improve call graph accuracy.
    
    Args:
        call_graph: The call graph containing functions and their relationships
        mode: Analysis mode - "basic", "enhanced", or "full"
        
    Returns:
        Tuple of (updated call graph, number of resolved references)
    """
    if mode == "basic":
        # Basic mode - only resolve direct function calls
        return call_graph
    
    # Enhanced and full modes - try to match missing functions to defined functions
    resolved_count = 0
    
    # Create lookup maps for faster processing
    function_map = {}
    function_by_base_name = defaultdict(list)
    function_by_signature = defaultdict(list)
    
    for func_name, func in call_graph.functions.items():
        # Create normalized name without namespace qualifiers for fuzzy matching
        base_name = func_name.split("::")[-1]
        
        # Store by fully qualified name
        function_map[func_name] = func
        
        # Store by base name for fuzzy matching
        function_by_base_name[base_name].append(func)
        
        # For full mode, prepare signature-based lookup
        if mode == "full" and "signature" in func.metadata:
            # Get parameter count and types for matching
            param_count = func.metadata.get("param_count", 0)
            param_types = func.metadata.get("param_types", [])
            return_type = func.metadata.get("return_type", "void")
            
            # Create signature keys of varying specificity
            # 1. Just parameter count
            function_by_signature[f"params:{param_count}"].append(func)
            
            # 2. Parameter count and return type
            function_by_signature[f"return:{return_type}|params:{param_count}"].append(func)
            
            # 3. Full signature with types (most specific)
            if param_types:
                param_type_str = "|".join(param_types)
                function_by_signature[f"return:{return_type}|params:{param_type_str}"].append(func)
    
    # Try to resolve missing functions
    resolved_missing = set()
    for missing in call_graph.missing_functions:
        # Case 1: Try exact match first
        if missing in function_map:
            resolved_missing.add(missing)
            resolved_count += 1
            continue
            
        # Case 2: Try base name match (for both enhanced and full modes)
        base_name = missing.split("::")[-1]
        if base_name in function_by_base_name:
            candidates = function_by_base_name[base_name]
            
            # If only one candidate, use it directly
            if len(candidates) == 1:
                # Find all callers of this missing function
                for func_name, func in call_graph.functions.items():
                    if missing in func.calls:
                        # Replace missing call with resolved function
                        func.calls.remove(missing)
                        func.add_call(candidates[0].name)
                        candidates[0].add_caller(func_name)
                
                resolved_missing.add(missing)
                resolved_count += 1
                continue
            
            # If multiple candidates but not in full mode, use namespace hints if available
            if mode != "full" and len(candidates) > 1:
                # Try to use namespace hints from context
                best_candidate = None
                for func_name, func in call_graph.functions.items():
                    if missing in func.calls and "namespace" in func.metadata:
                        caller_namespace = func.metadata["namespace"]
                        # Find candidate in same namespace
                        for candidate in candidates:
                            if "namespace" in candidate.metadata and candidate.metadata["namespace"] == caller_namespace:
                                best_candidate = candidate
                                break
                
                if best_candidate:
                    # Find all callers and update relationships
                    for func_name, func in call_graph.functions.items():
                        if missing in func.calls:
                            func.calls.remove(missing)
                            func.add_call(best_candidate.name)
                            best_candidate.add_caller(func_name)
                    
                    resolved_missing.add(missing)
                    resolved_count += 1
                    continue
    
    # Full mode - sophisticated matching based on signatures
    if mode == "full":
        # For each remaining missing function, try signature-based matching
        for missing in set(call_graph.missing_functions) - resolved_missing:
            # Skip already resolved
            if missing in resolved_missing:
                continue
                
            # Extract information from missing function name and context
            base_name = missing.split("::")[-1]
            
            # Collect signature information from callers
            param_count_candidates = []
            return_type_candidates = []
            context_clues = defaultdict(int)  # For weighted voting
            
            # Analyze callers for clues
            for func_name, func in call_graph.functions.items():
                if missing in func.calls:
                    # Check for call site information in metadata
                    for call_info in func.metadata.get("call_sites", []):
                        if call_info.get("target") == missing:
                            # Found call site info for this missing function
                            if "arg_count" in call_info:
                                param_count_candidates.append(call_info["arg_count"])
                            
                            if "arg_types" in call_info:
                                arg_type_str = "|".join(call_info["arg_types"])
                                context_clues[f"params:{arg_type_str}"] += 2  # Higher weight
                            
                            if "context_type" in call_info:
                                context_clues[f"context:{call_info['context_type']}"] += 1
            
            # Determine most likely parameter count
            most_common_param_count = None
            if param_count_candidates:
                counter = Counter(param_count_candidates)
                most_common_param_count = counter.most_common(1)[0][0]
            
            # Search for matching functions using derived signature information
            potential_matches = []
            
            # First try parameter count match
            if most_common_param_count is not None:
                signature_key = f"params:{most_common_param_count}"
                if signature_key in function_by_signature:
                    potential_matches.extend(function_by_signature[signature_key])
            
            # Filter to those matching the base name
            name_matches = [f for f in potential_matches if f.name.split("::")[-1] == base_name]
            if name_matches:
                potential_matches = name_matches
            
            # If we have potential matches, score them by context clues
            if potential_matches:
                best_match = None
                best_score = -1
                
                for candidate in potential_matches:
                    score = 0
                    
                    # Base score: matching name is good
                    if candidate.name.split("::")[-1] == base_name:
                        score += 5
                    
                    # Parameter count match
                    if most_common_param_count is not None and "param_count" in candidate.metadata:
                        if candidate.metadata["param_count"] == most_common_param_count:
                            score += 3
                    
                    # Context clues matching
                    for clue, weight in context_clues.items():
                        if clue.startswith("params:") and "param_types" in candidate.metadata:
                            param_types = "|".join(candidate.metadata["param_types"])
                            clue_params = clue.split("params:")[1]
                            if param_types == clue_params:
                                score += weight * 2
                        
                        if clue.startswith("context:") and "class" in candidate.metadata:
                            context_type = clue.split("context:")[1]
                            if candidate.metadata["class"] == context_type:
                                score += weight * 3
                    
                    # Namespace matching with callers
                    if "namespace" in candidate.metadata:
                        for func_name, func in call_graph.functions.items():
                            if missing in func.calls and "namespace" in func.metadata:
                                if func.metadata["namespace"] == candidate.metadata["namespace"]:
                                    score += 4  # Same namespace is a strong signal
                    
                    if score > best_score:
                        best_score = score
                        best_match = candidate
                
                # If we found a good match, update the call graph
                if best_match and best_score > 2:  # Threshold to avoid weak matches
                    # Update all callers to point to the resolved function
                    for func_name, func in call_graph.functions.items():
                        if missing in func.calls:
                            func.calls.remove(missing)
                            func.add_call(best_match.name)
                            best_match.add_caller(func_name)
                    
                    resolved_missing.add(missing)
                    resolved_count += 1
    
    # Remove resolved missing functions
    for missing in resolved_missing:
        if missing in call_graph.missing_functions:  # Check in case set changed during iteration
            call_graph.missing_functions.remove(missing)
    
    return call_graph, resolved_count

def main():
    """Clear Neo4j data and re-index Folly repository."""
    args = parse_arguments()
    
    # Setup logging with timestamp in filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = f"folly_indexing_{timestamp}.log"
    logger = setup_logging(log_file)
    
    # Track overall start time
    overall_start_time = time.time()
    
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
    
    # Store all include directories for reference and fallback
    include_directories = []
    
    if compile_commands_path:
        logger.info(f"Found compile_commands.json at {compile_commands_path}")
        compile_commands_service.load_compile_commands(compile_commands_path)
    else:
        logger.warning("No compile_commands.json found. Using heuristic include path detection.")
        
        # Try heuristic approaches to detect include paths
        if args.fallback_include_dirs:
            logger.info(f"Using provided fallback include directories: {args.fallback_include_dirs}")
            include_directories.extend(args.fallback_include_dirs)
        else:
            # Try to detect include paths using heuristics
            logger.info("Performing heuristic include path detection...")
            heuristic_includes = heuristic_include_path_detection(folly_path)
            include_directories.extend(heuristic_includes)
            logger.info(f"Detected {len(heuristic_includes)} potential include paths")
            
            # Add system include paths
            logger.info("Detecting system include paths...")
            system_includes = detect_system_include_paths()
            include_directories.extend(system_includes)
            logger.info(f"Added {len(system_includes)} system include paths")
    
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
    
    # Store file-specific metrics
    file_metrics = []
    
    # Use ThreadPoolExecutor for parallel processing
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        # Submit file analysis tasks
        file_tasks = []
        for file_path in files_to_analyze:
            file_include_dirs = []
            compiler_args = []
            
            # Get include paths and compiler args from compile_commands.json if available
            if compile_commands_path:
                file_include_dirs = compile_commands_service.get_include_paths(file_path)
                compiler_args = compile_commands_service.get_compiler_options(file_path)
            else:
                # Use detected include directories as fallback
                file_include_dirs = include_directories
            
            # Submit analysis task
            file_tasks.append(
                executor.submit(
                    analyze_file, 
                    analyzer, 
                    file_path, 
                    file_include_dirs, 
                    compiler_args,
                    args.enhanced_template_handling,
                    args.track_virtual_methods
                )
            )
        
        # Process completed tasks as they complete
        total_files = len(files_to_analyze)
        processed_files = 0
        
        for future in as_completed(file_tasks):
            processed_files += 1
            
            try:
                result = future.result()
                if result:
                    file_call_graph, file_metric = result
                    
                    # Store metrics
                    file_metrics.append(file_metric)
                    
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
                                
                            # Merge metadata
                            for key, value in func.metadata.items():
                                if key not in existing_func.metadata:
                                    existing_func.metadata[key] = value
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
    
    # Process cross-file references
    if args.cross_file_mode != "basic":
        logger.info(f"Processing cross-file references (mode: {args.cross_file_mode})...")
        result = process_cross_file_references(call_graph, args.cross_file_mode)
        if isinstance(result, tuple):  # Check if we got a tuple (call_graph, resolved_count)
            call_graph, resolved_count = result
            logger.info(f"Resolved {resolved_count} cross-file references")
        else:  # Otherwise just the call_graph was returned
            call_graph = result
            logger.info("Processed cross-file references")
    
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
    
    # Collect and save metrics if requested
    if args.output_metrics:
        metrics = collect_metrics(
            overall_start_time,
            len(files_to_analyze),
            len(call_graph.functions),
            sum(len(func.calls) for func in call_graph.functions.values()),
            file_metrics
        )
        
        # Save metrics to JSON file
        metrics_file = f"folly_indexing_metrics_{timestamp}.json"
        with open(metrics_file, 'w') as f:
            json.dump(metrics, f, indent=2)
        
        logger.info(f"Saved metrics to {metrics_file}")
    
    logger.info("Re-indexing complete")
    logger.info(f"Total execution time: {time.time() - overall_start_time:.2f} seconds")

if __name__ == "__main__":
    main() 