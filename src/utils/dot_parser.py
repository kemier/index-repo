"""
Parser for DOT graph format
"""
import re
from typing import List, Dict, Set, Optional, Tuple

from src.models.function_model import Function, CallGraph


def parse_dot_file(dot_content: str) -> CallGraph:
    """
    Parse a DOT file into a call graph
    
    Args:
        dot_content: String content of DOT file
        
    Returns:
        CallGraph object representing the function calls
    """
    call_graph = CallGraph()
    
    # Extract node definitions
    node_pattern = re.compile(r'"([^"]+)"\s*\[([^\]]+)\]')
    for match in node_pattern.finditer(dot_content):
        name, attrs = match.groups()
        
        # Skip if not a function
        if 'shape=box' not in attrs:
            continue
        
        # Extract file and line info if available
        file_path = ""
        line_number = 0
        
        label_match = re.search(r'label="([^"]+)"', attrs)
        if label_match:
            label = label_match.group(1)
            file_match = re.search(r'\\n(.*?):', label)
            if file_match:
                file_path = file_match.group(1)
            
            line_match = re.search(r':(\\n)?(\d+)', label)
            if line_match:
                line_number = int(line_match.group(2))
        
        # Create function object
        function = Function(
            name=name,
            file_path=file_path,
            line_number=line_number
        )
        
        call_graph.add_function(function)
    
    # Extract edges (function calls)
    edge_pattern = re.compile(r'"([^"]+)"\s*->\s*"([^"]+)"')
    for match in edge_pattern.finditer(dot_content):
        caller, callee = match.groups()
        
        if caller in call_graph.functions:
            call_graph.functions[caller].add_call(callee)
        
        if callee in call_graph.functions:
            call_graph.functions[callee].add_caller(caller)
        else:
            # Add to missing functions
            call_graph.add_missing_function(callee)
    
    return call_graph 