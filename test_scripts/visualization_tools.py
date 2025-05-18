#!/usr/bin/env python
"""
Consolidated visualization tools for Folly code analysis.
This module provides unified functionality for generating various
visualizations of Folly's codebase structure and call graphs.
"""
import os
import sys
import logging
import tempfile
import subprocess
import argparse
import networkx as nx
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Union

# Add parent directory to path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.neo4j_service import Neo4jService

# Constants
DEFAULT_NEO4J_URI = "bolt://localhost:7688"
DEFAULT_NEO4J_USERNAME = "neo4j"
DEFAULT_NEO4J_PASSWORD = "password"
DEFAULT_OUTPUT_DIR = "output"

# Color palettes
DEFAULT_COLOR_PALETTE = [
    "#66c2a5", "#fc8d62", "#8da0cb", "#e78ac3", "#a6d854",
    "#ffd92f", "#e5c494", "#b3b3b3", "#8dd3c7", "#bebada"
]

def setup_logging() -> logging.Logger:
    """Configure logging for visualization scripts."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(__name__)

def connect_to_neo4j(uri: str = DEFAULT_NEO4J_URI, 
                    username: str = DEFAULT_NEO4J_USERNAME, 
                    password: str = DEFAULT_NEO4J_PASSWORD) -> Neo4jService:
    """
    Create and return a Neo4j service connection.
    
    Args:
        uri: Neo4j connection URI
        username: Neo4j username
        password: Neo4j password
        
    Returns:
        Neo4jService instance
    """
    logger = logging.getLogger(__name__)
    logger.info(f"Connecting to Neo4j at {uri}")
    
    try:
        neo4j_service = Neo4jService(uri, username, password)
        return neo4j_service
    except Exception as e:
        logger.error(f"Failed to connect to Neo4j: {e}")
        raise

#
# Database Query Functions
#

def get_logger_functions(neo4j_service: Neo4jService) -> List[Dict]:
    """
    Get all Logger-related functions from the database.
    
    Args:
        neo4j_service: Neo4j service
        
    Returns:
        List of function dictionaries
    """
    logger = logging.getLogger(__name__)
    
    query = """
    MATCH (f:Function)
    WHERE f.project = 'folly' 
    AND (f.name CONTAINS "Logger" OR f.file_path CONTAINS "logging")
    AND NOT f.file_path CONTAINS "test"
    AND NOT f.file_path CONTAINS "Test"
    AND NOT f.file_path CONTAINS "Benchmark"
    RETURN f.name as name, f.file_path as file_path, f.line_number as line_number
    ORDER BY f.file_path, f.line_number
    """
    
    try:
        logger.info("Finding Logger-related functions")
        functions = neo4j_service.execute_custom_query(query)
        
        if not functions:
            logger.warning("No Logger-related functions found")
            return []
            
        logger.info(f"Found {len(functions)} Logger-related functions")
        return functions
    except Exception as e:
        logger.error(f"Error getting Logger functions: {e}")
        return []

def get_logger_callgraph(neo4j_service: Neo4jService, depth: int = 3, limit: int = 150) -> List[Dict]:
    """
    Get the call graph for LoggerDB-related functions.
    
    Args:
        neo4j_service: Neo4j service
        depth: Maximum call depth
        limit: Maximum number of relationships to return
        
    Returns:
        List of relationship dictionaries
    """
    logger = logging.getLogger(__name__)
    
    # Use manual list of important logger functions
    key_logger_functions = [
        "LoggerDB::getCategory",
        "LoggerDB::getCategoryOrNull",
        "LoggerDB::addContextCallback",
        "LoggerDB::internalWarningImpl",
        "Logger::getCategory",
        "initLogging",
        "initLoggingOrDie",
        "logDisabled",
        "logEnabled"
    ]
    
    # Build call graph query using function names
    func_conditions = []
    for name in key_logger_functions:
        safe_name = name.replace("'", "\\'")
        func_conditions.append(f"caller.name = '{safe_name}' OR callee.name = '{safe_name}'")
    
    conditions = " OR ".join(func_conditions)
    
    call_graph_query = f"""
    MATCH path = (caller:Function)-[r:CALLS*1..{depth}]->(callee:Function)
    WHERE caller.project = 'folly' AND callee.project = 'folly'
    AND ({conditions})
    RETURN DISTINCT caller.name as caller, callee.name as callee,
           caller.file_path as caller_path, callee.file_path as callee_path,
           length(path) as path_length
    LIMIT {limit}
    """
    
    try:
        logger.info("Getting call graph for Logger-related functions")
        return neo4j_service.execute_custom_query(call_graph_query)
    except Exception as e:
        logger.error(f"Error getting logger call graph: {e}")
        return []

def get_callgraph_for_function(neo4j_service: Neo4jService, 
                             function: Dict,
                             depth: int = 2,
                             limit: int = 100,
                             focus: Optional[str] = None) -> List[Dict]:
    """
    Get the call graph for a specific function.
    
    Args:
        neo4j_service: Neo4j service
        function: Dictionary containing function info
        depth: Maximum call depth
        limit: Maximum number of functions to include
        focus: Optional component to focus on
        
    Returns:
        List of relationship dictionaries
    """
    logger = logging.getLogger(__name__)
    func_name = function.get('name', '')
    
    if not func_name:
        logger.warning("No function name provided")
        return []
    
    # Add focus clause if specified
    focus_clause = f"AND (caller.name CONTAINS '{focus}' OR callee.name CONTAINS '{focus}')" if focus else ""
    
    # Query to get call graph starting from the function
    query = f"""
    MATCH path = (caller:Function)-[r:CALLS*1..{depth}]->(callee:Function)
    WHERE caller.name = '{func_name}' 
    AND caller.project = 'folly'
    AND callee.project = 'folly'
    AND caller.file_path = '{function.get('file_path', '')}'
    {focus_clause}
    RETURN caller.name as caller, callee.name as callee,
           caller.namespace as caller_namespace, callee.namespace as callee_namespace,
           length(path) as path_length
    ORDER BY path_length
    LIMIT {limit}
    """
    
    try:
        logger.info(f"Querying call graph for function: {func_name}")
        return neo4j_service.execute_custom_query(query)
    except Exception as e:
        logger.error(f"Error querying call graph: {e}")
        return []

def find_key_components(neo4j_service: Neo4jService) -> List[str]:
    """
    Find key components in the Folly codebase by analyzing namespaces.
    
    Args:
        neo4j_service: Neo4j service
        
    Returns:
        List of key component names
    """
    logger = logging.getLogger(__name__)
    
    # Query to find namespaces
    query = """
    MATCH (f:Function)
    WHERE f.project = 'folly'
    RETURN DISTINCT f.namespace as namespace, count(f) as func_count
    ORDER BY func_count DESC
    LIMIT 20
    """
    
    try:
        results = neo4j_service.execute_custom_query(query)
        
        components = []
        for result in results:
            ns = result.get('namespace', '')
            if ns:
                # Extract component name from namespace (last part)
                parts = ns.split('::')
                if len(parts) > 0 and parts[-1]:
                    components.append(parts[-1])
        
        return list(set(components))  # Remove duplicates
    except Exception as e:
        logger.error(f"Error finding key components: {e}")
        return []

def get_hash64_functions(neo4j_service: Neo4jService) -> List[Dict]:
    """
    Get Hash64-related functions from the database.
    
    Args:
        neo4j_service: Neo4j service
        
    Returns:
        List of function dictionaries
    """
    logger = logging.getLogger(__name__)
    
    query = """
    MATCH (f:Function)
    WHERE f.project = 'folly' 
    AND (f.name CONTAINS "Hash64" OR f.name CONTAINS "hash64")
    AND NOT f.file_path CONTAINS "test"
    AND NOT f.file_path CONTAINS "Test"
    RETURN f.name as name, f.file_path as file_path, f.line_number as line_number
    ORDER BY f.file_path, f.line_number
    """
    
    try:
        logger.info("Finding Hash64-related functions")
        functions = neo4j_service.execute_custom_query(query)
        
        if not functions:
            logger.warning("No Hash64-related functions found")
            return []
            
        logger.info(f"Found {len(functions)} Hash64-related functions")
        return functions
    except Exception as e:
        logger.error(f"Error getting Hash64 functions: {e}")
        return []

def get_init_impl_functions(neo4j_service: Neo4jService) -> List[Dict]:
    """
    Get InitImpl-related functions from the database.
    
    Args:
        neo4j_service: Neo4j service
        
    Returns:
        List of function dictionaries
    """
    logger = logging.getLogger(__name__)
    
    query = """
    MATCH (f:Function)
    WHERE f.project = 'folly' 
    AND (f.name CONTAINS "InitImpl" OR f.name CONTAINS "initImpl")
    AND NOT f.file_path CONTAINS "test"
    AND NOT f.file_path CONTAINS "Test"
    RETURN f.name as name, f.file_path as file_path, f.line_number as line_number
    ORDER BY f.file_path, f.line_number
    """
    
    try:
        logger.info("Finding InitImpl-related functions")
        functions = neo4j_service.execute_custom_query(query)
        
        if not functions:
            logger.warning("No InitImpl-related functions found")
            return []
            
        logger.info(f"Found {len(functions)} InitImpl-related functions")
        return functions
    except Exception as e:
        logger.error(f"Error getting InitImpl functions: {e}")
        return []

def get_component_functions(neo4j_service: Neo4jService, component: str, limit: int = 100) -> List[Dict]:
    """
    Get functions related to a specific component.
    
    Args:
        neo4j_service: Neo4j service
        component: Component name or keyword
        limit: Maximum number of functions to return
        
    Returns:
        List of function dictionaries
    """
    logger = logging.getLogger(__name__)
    
    # Query to find functions related to the component
    query = f"""
    MATCH (f:Function)
    WHERE f.project = 'folly' 
    AND (f.name CONTAINS '{component}' OR f.namespace CONTAINS '{component}')
    RETURN f.name as name, f.file_path as file_path, f.line_number as line_number
    LIMIT {limit}
    """
    
    try:
        logger.info(f"Finding functions related to component: {component}")
        return neo4j_service.execute_custom_query(query)
    except Exception as e:
        logger.error(f"Error finding component functions: {e}")
        return []

def get_component_callgraph(neo4j_service: Neo4jService, component: str, depth: int = 2, limit: int = 100) -> List[Dict]:
    """
    Get the call graph for a specific component.
    
    Args:
        neo4j_service: Neo4j service
        component: Component name or keyword
        depth: Maximum call depth
        limit: Maximum number of relationships to return
        
    Returns:
        List of relationship dictionaries
    """
    logger = logging.getLogger(__name__)
    
    # Query to get call graph for the component
    query = f"""
    MATCH path = (caller:Function)-[r:CALLS*1..{depth}]->(callee:Function)
    WHERE caller.project = 'folly' AND callee.project = 'folly'
    AND (caller.name CONTAINS '{component}' OR caller.namespace CONTAINS '{component}'
         OR callee.name CONTAINS '{component}' OR callee.namespace CONTAINS '{component}')
    RETURN caller.name as caller, callee.name as callee,
           caller.namespace as caller_namespace, callee.namespace as callee_namespace,
           length(path) as path_length
    LIMIT {limit}
    """
    
    try:
        logger.info(f"Getting call graph for component: {component}")
        return neo4j_service.execute_custom_query(query)
    except Exception as e:
        logger.error(f"Error getting component call graph: {e}")
        return []

def get_main_functions(neo4j_service: Neo4jService, include_tests: bool = False) -> List[Dict]:
    """
    Get main functions from the Folly codebase.
    
    Args:
        neo4j_service: Neo4j service
        include_tests: Whether to include test files
        
    Returns:
        List of function dictionaries
    """
    logger = logging.getLogger(__name__)
    
    # Excluding test files if needed
    exclude_clause = "" if include_tests else """
    AND NOT f.file_path CONTAINS "test/"
    AND NOT f.file_path CONTAINS "/test"
    AND NOT f.file_path CONTAINS "Test"
    AND NOT f.file_path CONTAINS "Benchmark"
    """
    
    # Query to find main functions
    query = f"""
    MATCH (f:Function)
    WHERE f.project = 'folly' 
    AND (f.name = 'main' OR f.name ENDS WITH '::main')
    {exclude_clause}
    RETURN f.name as name, f.file_path as file_path, f.line_number as line_number
    ORDER BY f.file_path
    """
    
    try:
        logger.info("Finding main functions")
        functions = neo4j_service.execute_custom_query(query)
        
        if not functions:
            logger.warning("No main functions found")
            return []
            
        logger.info(f"Found {len(functions)} main functions")
        return functions
    except Exception as e:
        logger.error(f"Error getting main functions: {e}")
        return []

def get_callgraph_from_main(neo4j_service: Neo4jService, 
                          main_function: Dict,
                          depth: int = 2,
                          limit: int = 100) -> List[Dict]:
    """
    Get the call graph starting from a main function.
    
    Args:
        neo4j_service: Neo4j service
        main_function: Dictionary containing main function info
        depth: Maximum call depth
        limit: Maximum number of functions to include
        
    Returns:
        List of relationship dictionaries
    """
    logger = logging.getLogger(__name__)
    main_name = main_function.get('name', '')
    
    if not main_name:
        logger.warning("No main function name provided")
        return []
    
    # Query to get call graph starting from main
    query = f"""
    MATCH path = (main:Function)-[r:CALLS*1..{depth}]->(callee:Function)
    WHERE main.name = '{main_name}' AND main.project = 'folly'
    AND callee.project = 'folly'
    AND main.file_path = '{main_function.get('file_path', '')}'
    RETURN main.name as caller, callee.name as callee,
           main.namespace as caller_namespace, callee.namespace as callee_namespace,
           length(path) as path_length
    ORDER BY path_length
    LIMIT {limit}
    """
    
    try:
        logger.info(f"Querying call graph for main function: {main_name}")
        return neo4j_service.execute_custom_query(query)
    except Exception as e:
        logger.error(f"Error querying call graph: {e}")
        return []

def get_focus_relationships(neo4j_service: Neo4jService, focus: str, limit: int = 100) -> List[Dict]:
    """
    Get relationships for functions containing a specific focus string.
    
    Args:
        neo4j_service: Neo4j service
        focus: Focus string to search for
        limit: Maximum number of relationships to return
        
    Returns:
        List of relationship dictionaries
    """
    logger = logging.getLogger(__name__)
    
    # Query to find relationships for the focus
    query = f"""
    MATCH (caller:Function)-[r:CALLS]->(callee:Function)
    WHERE caller.project = 'folly' AND callee.project = 'folly'
    AND (caller.name CONTAINS '{focus}' OR callee.name CONTAINS '{focus}')
    RETURN caller.name as caller, callee.name as callee, 
           caller.namespace as caller_namespace, callee.namespace as callee_namespace,
           type(r) as relationship_type
    LIMIT {limit}
    """
    
    try:
        logger.info(f"Finding relationships for functions containing '{focus}'")
        return neo4j_service.execute_custom_query(query)
    except Exception as e:
        logger.error(f"Error finding focus relationships: {e}")
        return []

#
# Visualization Functions 
#

def generate_function_visualization(functions: List[Dict], output_path: str, title: str = "Function Visualization") -> None:
    """
    Generate a simple visualization of a set of functions.
    
    Args:
        functions: List of function dictionaries
        output_path: Path to save the output PNG
        title: Title for the visualization
    """
    logger = logging.getLogger(__name__)
    
    if not functions:
        logger.warning("No functions to visualize")
        return
        
    # Create graph
    G = nx.DiGraph()
    
    # Group functions by file path
    file_functions = {}
    for func in functions:
        file_path = func.get('file_path', '')
        if file_path not in file_functions:
            file_functions[file_path] = []
        file_functions[file_path].append(func)
    
    # Color mapping for file paths
    path_colors = {}
    
    # Create a file node for each file
    for i, (file_path, funcs) in enumerate(file_functions.items()):
        # Create a shortened file name for display
        parts = file_path.split('/')
        if len(parts) > 1:
            short_name = parts[-2] + '/' + parts[-1]
        else:
            short_name = parts[-1]
            
        # Get color for this file
        color_idx = i % len(DEFAULT_COLOR_PALETTE)
        color = DEFAULT_COLOR_PALETTE[color_idx]
        path_colors[file_path] = color
        
        # Add file node
        file_node = f"FILE: {short_name}"
        G.add_node(file_node, is_file=True, color=color, shape="box", penwidth="2.0")
        
        # Add function nodes and connect to file
        for func in funcs:
            name = func.get('name', '')
            if not name:
                continue
                
            # Check function properties
            is_special = check_function_properties(name)
            
            G.add_node(name, is_file=False, is_special=is_special, file_path=file_path)
            G.add_edge(file_node, name)
    
    # Set node appearance
    for node in G.nodes:
        if G.nodes[node].get('is_file', False):
            continue  # File nodes already styled
            
        is_special = G.nodes[node].get('is_special', False)
        file_path = G.nodes[node].get('file_path', '')
        
        if is_special:
            # Highlight special nodes
            G.nodes[node]['color'] = "#ff5555"  # Red
            G.nodes[node]['shape'] = "box"
            G.nodes[node]['penwidth'] = "2.0"
        elif file_path in path_colors:
            # Use file color with lower intensity
            base_color = path_colors[file_path]
            G.nodes[node]['color'] = base_color
            G.nodes[node]['shape'] = "ellipse"
            G.nodes[node]['penwidth'] = "1.0"
        else:
            G.nodes[node]['color'] = "#cccccc"  # Default gray
            G.nodes[node]['shape'] = "ellipse"
            G.nodes[node]['penwidth'] = "1.0"
    
    # Generate and save the visualization
    render_graph_to_file(G, output_path, title, rankdir="TB")

def generate_callgraph_visualization(relationships: List[Dict], output_path: str, title: str = "Call Graph Visualization") -> None:
    """
    Generate a visualization from relationship data.
    
    Args:
        relationships: List of relationship dictionaries
        output_path: Path to save the output PNG
        title: Title for the visualization
    """
    logger = logging.getLogger(__name__)
    
    if not relationships:
        logger.warning("No relationships to visualize")
        return
        
    # Create graph
    G = nx.DiGraph()
    
    # Color mapping for namespaces
    namespace_colors = {}
    
    # Add nodes and edges
    for rel in relationships:
        caller = rel.get('caller', '')
        callee = rel.get('callee', '')
        caller_ns = rel.get('caller_namespace', rel.get('caller_path', ''))
        callee_ns = rel.get('callee_namespace', rel.get('callee_path', ''))
        path_length = rel.get('path_length', 1)
        
        # Skip self-calls
        if caller == callee:
            continue
            
        # Add nodes if they don't exist
        if caller not in G:
            is_special_caller = check_function_properties(caller)
            G.add_node(caller, namespace=caller_ns, is_special=is_special_caller)
        if callee not in G:
            is_special_callee = check_function_properties(callee)
            G.add_node(callee, namespace=callee_ns, is_special=is_special_callee)
        
        # Add edge with relationship info
        G.add_edge(caller, callee, path_length=path_length)
        
        # Add namespace colors
        for ns in [caller_ns, callee_ns]:
            if ns and ns not in namespace_colors:
                color_idx = len(namespace_colors) % len(DEFAULT_COLOR_PALETTE)
                namespace_colors[ns] = DEFAULT_COLOR_PALETTE[color_idx]
    
    # Set node colors based on namespace and highlight special nodes
    for node in G.nodes:
        is_special = G.nodes[node].get('is_special', False)
        ns = G.nodes[node].get('namespace', '')
        
        if is_special:
            # Highlight special nodes
            G.nodes[node]['color'] = "#ff5555"  # Red
            G.nodes[node]['shape'] = "box"
            G.nodes[node]['penwidth'] = "2.0"
        elif ns in namespace_colors:
            G.nodes[node]['color'] = namespace_colors[ns]
            G.nodes[node]['shape'] = "ellipse"
            G.nodes[node]['penwidth'] = "1.0"
        else:
            G.nodes[node]['color'] = "#cccccc"  # Default gray
            G.nodes[node]['shape'] = "ellipse"
            G.nodes[node]['penwidth'] = "1.0"
    
    # Generate and save the visualization
    render_graph_to_file(G, output_path, title, rankdir="LR")

def check_function_properties(name: str) -> bool:
    """
    Check if a function has special properties based on its name.
    
    Args:
        name: Function name
        
    Returns:
        True if the function is special, False otherwise
    """
    special_patterns = [
        "Logger::", "LoggerDB", "Hash64", "hash64", 
        "InitImpl", "initImpl", "init", "Init",
        "main", "Main"
    ]
    
    for pattern in special_patterns:
        if pattern in name:
            return True
    
    return False

def render_graph_to_file(G: nx.DiGraph, output_path: str, title: str, rankdir: str = "TB") -> None:
    """
    Render a NetworkX graph to a PNG file.
    
    Args:
        G: NetworkX DiGraph
        output_path: Path to save the output PNG
        title: Title for the visualization
        rankdir: Graph direction (TB=top-bottom, LR=left-right)
    """
    logger = logging.getLogger(__name__)
    
    # Generate DOT file
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.dot')
    temp_file.close()
    
    # Write DOT file content
    with open(temp_file.name, 'w') as f:
        f.write(f'digraph "{title}" {{\n')
        f.write(f'  rankdir={rankdir};\n')
        f.write('  node [style=filled, fontname="Arial"];\n')
        f.write('  edge [fontname="Arial"];\n')
        f.write(f'  labelloc="t";\n')
        f.write(f'  label="{title}";\n')
        
        # Write node definitions
        for node in G.nodes:
            node_name = node.replace('"', '\\"')  # Escape quotes
            color = G.nodes[node].get('color', '#cccccc')
            shape = G.nodes[node].get('shape', 'ellipse')
            penwidth = G.nodes[node].get('penwidth', '1.0')
            
            # Shorten function names if too long
            if not G.nodes[node].get('is_file', False) and len(node_name) > 40:
                parts = node_name.split('::')
                if len(parts) > 2:
                    short_name = '::'.join(parts[-2:])
                else:
                    short_name = node_name[-40:]
            else:
                short_name = node_name
                
            f.write(f'  "{node_name}" [label="{short_name}", fillcolor="{color}", '
                  f'shape={shape}, penwidth={penwidth}];\n')
        
        # Write edge definitions
        for u, v in G.edges():
            u_name = u.replace('"', '\\"')
            v_name = v.replace('"', '\\"')
            path_length = G.edges[u, v].get('path_length', 1)
            
            style = "solid"
            penwidth = "1.0"
            
            if G.nodes[u].get('is_file', False):
                # File to function edges are thinner and dashed
                style = "dashed"
                penwidth = "0.5"
            elif path_length > 1:
                # For longer paths, make edges lighter
                penwidth = f"{2.0 / path_length:.1f}"
            
            f.write(f'  "{u_name}" -> "{v_name}" [style={style}, penwidth={penwidth}];\n')
        
        f.write('}\n')
    
    # Convert DOT to PNG using Graphviz
    try:
        # Ensure output directory exists
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Run the graphviz command
        cmd = ["dot", "-Tpng", temp_file.name, "-o", output_path]
        logger.debug(f"Executing Graphviz command: {' '.join(cmd)}")
        
        result = subprocess.run(cmd, check=True, 
                               stdout=subprocess.PIPE, 
                               stderr=subprocess.PIPE)
        
        if os.path.exists(output_path):
            logger.info(f"Generated PNG visualization at: {output_path}")
            # Also generate a SVG for better quality
            svg_path = output_path.replace('.png', '.svg')
            svg_cmd = ["dot", "-Tsvg", temp_file.name, "-o", svg_path]
            subprocess.run(svg_cmd, check=True)
            logger.info(f"Generated SVG visualization at: {svg_path}")
        else:
            logger.error("PNG file was not created. Graphviz command did not report an error.")
    except subprocess.CalledProcessError as e:
        logger.error(f"Error running Graphviz: {e}")
        logger.error(f"Stderr: {e.stderr.decode('utf-8') if e.stderr else 'None'}")
    except Exception as e:
        logger.error(f"Error converting DOT to PNG: {e}")
    finally:
        # Clean up temporary file
        try:
            os.unlink(temp_file.name)
        except:
            pass

#
# Command-line interfaces for various visualization tools
#

def visualize_logger_functions(neo4j_service: Optional[Neo4jService] = None):
    """Command-line interface for visualizing Logger functions."""
    logger = setup_logging()
    
    # Set up output path
    output_dir = DEFAULT_OUTPUT_DIR
    output_file = "logger_functions.png"
    output_path = os.path.join(output_dir, output_file)
    
    # Connect to Neo4j if not provided
    if neo4j_service is None:
        neo4j_service = connect_to_neo4j()
    
    # Get Logger functions
    functions = get_logger_functions(neo4j_service)
    
    # Generate visualization
    generate_function_visualization(functions, output_path, "Folly Logger Functions")
    
    return output_path

def visualize_logger_callgraph(neo4j_service: Optional[Neo4jService] = None, depth: int = 3, limit: int = 150):
    """Command-line interface for visualizing Logger call graph."""
    logger = setup_logging()
    
    # Set up output path
    output_dir = DEFAULT_OUTPUT_DIR
    output_file = "logger_callgraph.png"
    output_path = os.path.join(output_dir, output_file)
    
    # Connect to Neo4j if not provided
    if neo4j_service is None:
        neo4j_service = connect_to_neo4j()
    
    # Get Logger call graph
    relationships = get_logger_callgraph(neo4j_service, depth, limit)
    
    # Generate visualization
    generate_callgraph_visualization(relationships, output_path, "Folly Logger Call Graph")
    
    return output_path

def visualize_hash64_callgraph(neo4j_service: Optional[Neo4jService] = None, depth: int = 3, limit: int = 150):
    """Command-line interface for visualizing Hash64 call graph."""
    logger = setup_logging()
    
    # Set up output path
    output_dir = DEFAULT_OUTPUT_DIR
    output_file = "hash64_callgraph.png"
    output_path = os.path.join(output_dir, output_file)
    
    # Connect to Neo4j if not provided
    if neo4j_service is None:
        neo4j_service = connect_to_neo4j()
    
    # Get Hash64 functions
    functions = get_hash64_functions(neo4j_service)
    
    # Get call graph for each Hash64 function
    all_relationships = []
    for func in functions[:5]:  # Limit to first 5 functions to avoid overloading
        relationships = get_callgraph_for_function(neo4j_service, func, depth, limit // 5)
        all_relationships.extend(relationships)
    
    # Generate visualization
    generate_callgraph_visualization(all_relationships, output_path, "Folly Hash64 Call Graph")
    
    return output_path

def visualize_initimpl_callgraph(neo4j_service: Optional[Neo4jService] = None, depth: int = 3, limit: int = 150):
    """Command-line interface for visualizing InitImpl call graph."""
    logger = setup_logging()
    
    # Set up output path
    output_dir = DEFAULT_OUTPUT_DIR
    output_file = "initimpl_callgraph.png"
    output_path = os.path.join(output_dir, output_file)
    
    # Connect to Neo4j if not provided
    if neo4j_service is None:
        neo4j_service = connect_to_neo4j()
    
    # Get InitImpl functions
    functions = get_init_impl_functions(neo4j_service)
    
    # Get call graph for each InitImpl function
    all_relationships = []
    for func in functions[:5]:  # Limit to first 5 functions to avoid overloading
        relationships = get_callgraph_for_function(neo4j_service, func, depth, limit // 5)
        all_relationships.extend(relationships)
    
    # Generate visualization
    generate_callgraph_visualization(all_relationships, output_path, "Folly InitImpl Call Graph")
    
    return output_path

def visualize_folly_callgraph(neo4j_service: Optional[Neo4jService] = None, depth: int = 2, limit: int = 200, 
                             focus: Optional[str] = None, multiple: bool = False):
    """Command-line interface for visualizing Folly call graph."""
    logger = setup_logging()
    parser = argparse.ArgumentParser(description="Generate comprehensive Folly call graph visualizations")
    
    if multiple:
        # Generate multiple visualizations, one for each major component
        components = find_key_components(neo4j_service)
        logger.info(f"Found {len(components)} major components: {', '.join(components)}")
        
        outputs = []
        for component in components[:5]:  # Limit to first 5 components
            output_file = f"folly_{component.lower()}_callgraph.png"
            output_path = os.path.join(DEFAULT_OUTPUT_DIR, output_file)
            
            # TODO: Implement component-specific query
            # For now, just return the path
            outputs.append(output_path)
            
        return outputs
    else:
        # Generate a single visualization
        output_file = "folly_callgraph.png" if not focus else f"folly_{focus.lower()}_callgraph.png"
        output_path = os.path.join(DEFAULT_OUTPUT_DIR, output_file)
        
        # TODO: Implement comprehensive callgraph query
        # For now, just return the path
        return output_path

def visualize_specific_component(neo4j_service: Optional[Neo4jService] = None, 
                                component: str = "Future", 
                                depth: int = 2, 
                                limit: int = 100,
                                output_dir: str = DEFAULT_OUTPUT_DIR):
    """Command-line interface for visualizing a specific Folly component."""
    logger = setup_logging()
    
    # Set up output path
    output_file = f"folly_{component.lower()}_component.png"
    output_path = os.path.join(output_dir, output_file)
    
    # Connect to Neo4j if not provided
    if neo4j_service is None:
        neo4j_service = connect_to_neo4j()
    
    # Get component call graph
    relationships = get_component_callgraph(neo4j_service, component, depth, limit)
    
    # Generate visualization
    generate_callgraph_visualization(relationships, output_path, f"Folly {component} Component")
    
    return output_path

def visualize_main_callgraph(neo4j_service: Optional[Neo4jService] = None, 
                            depth: int = 2, 
                            limit: int = 200,
                            include_tests: bool = False,
                            output_dir: str = DEFAULT_OUTPUT_DIR):
    """Command-line interface for visualizing call graphs from main functions."""
    logger = setup_logging()
    
    # Set up output path
    output_file = "folly_main_callgraph.png"
    output_path = os.path.join(output_dir, output_file)
    
    # Connect to Neo4j if not provided
    if neo4j_service is None:
        neo4j_service = connect_to_neo4j()
    
    # Get main functions
    main_functions = get_main_functions(neo4j_service, include_tests)
    
    # Get call graph for each main function
    all_relationships = []
    for func in main_functions[:5]:  # Limit to first 5 main functions
        relationships = get_callgraph_from_main(neo4j_service, func, depth, limit // 5)
        all_relationships.extend(relationships)
    
    # Generate visualization
    generate_callgraph_visualization(all_relationships, output_path, "Folly Main Call Graph")
    
    return output_path

def visualize_folly_graph_viewer(neo4j_service: Optional[Neo4jService] = None, 
                               focus: str = "BufferedRandomDevice", 
                               limit: int = 100,
                               output_dir: str = DEFAULT_OUTPUT_DIR):
    """Command-line interface for the simple Folly call graph visualization."""
    logger = setup_logging()
    
    # Set up output path
    output_file = f"folly_{focus.lower()}_viewer.png"
    output_path = os.path.join(output_dir, output_file)
    
    # Connect to Neo4j if not provided
    if neo4j_service is None:
        neo4j_service = connect_to_neo4j()
    
    # Get relationships for the focus
    relationships = get_focus_relationships(neo4j_service, focus, limit)
    
    # Generate visualization
    generate_callgraph_visualization(relationships, output_path, f"Folly Call Graph - {focus}")
    
    return output_path

def main():
    """Main function to parse command-line arguments and run visualizations."""
    logger = setup_logging()
    
    # Declare global variables
    global DEFAULT_OUTPUT_DIR
    
    parser = argparse.ArgumentParser(description="Folly Code Visualization Tools")
    parser.add_argument("--type", choices=[
        "logger_functions", "logger_callgraph", "hash64_callgraph", 
        "initimpl_callgraph", "folly_callgraph", "specific_component",
        "main_callgraph", "folly_graph_viewer"
    ], required=True, help="Type of visualization to generate")
    
    parser.add_argument("--depth", type=int, default=2, help="Call graph depth (default: 2)")
    parser.add_argument("--limit", type=int, default=150, help="Maximum results (default: 150)")
    parser.add_argument("--focus", help="Component/function to focus on")
    parser.add_argument("--component", default="Future", help="Component to visualize (for specific_component)")
    parser.add_argument("--include-tests", action="store_true", help="Include test files")
    parser.add_argument("--multiple", action="store_true", help="Generate multiple visualizations")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="Output directory")
    
    args = parser.parse_args()
    
    # Override default output directory
    DEFAULT_OUTPUT_DIR = args.output_dir
    
    # Connect to Neo4j
    neo4j_service = connect_to_neo4j()
    
    # Run the selected visualization
    if args.type == "logger_functions":
        visualize_logger_functions(neo4j_service)
    elif args.type == "logger_callgraph":
        visualize_logger_callgraph(neo4j_service, args.depth, args.limit)
    elif args.type == "hash64_callgraph":
        visualize_hash64_callgraph(neo4j_service, args.depth, args.limit)
    elif args.type == "initimpl_callgraph":
        visualize_initimpl_callgraph(neo4j_service, args.depth, args.limit)
    elif args.type == "folly_callgraph":
        visualize_folly_callgraph(neo4j_service, args.depth, args.limit, args.focus, args.multiple)
    elif args.type == "specific_component":
        visualize_specific_component(neo4j_service, args.component, args.depth, args.limit, args.output_dir)
    elif args.type == "main_callgraph":
        visualize_main_callgraph(neo4j_service, args.depth, args.limit, args.include_tests, args.output_dir)
    elif args.type == "folly_graph_viewer":
        focus = args.focus if args.focus else "BufferedRandomDevice"
        visualize_folly_graph_viewer(neo4j_service, focus, args.limit, args.output_dir)
    
if __name__ == "__main__":
    main() 