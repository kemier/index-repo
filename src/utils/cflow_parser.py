"""
Parser for cflow output format
"""
import re
from typing import List, Dict, Set, Optional, Tuple

from src.models.function_model import Function, CallGraph


def parse_cflow_output(cflow_output: str, source_file: str = "") -> CallGraph:
    """
    Parse cflow output into a call graph
    
    Args:
        cflow_output: String output from cflow
        source_file: Source file path (optional)
        
    Returns:
        CallGraph object representing the function calls
    """
    call_graph = CallGraph()
    
    if not cflow_output:
        return call_graph
    
    # Keep track of the function hierarchy
    function_stack = []
    indent_stack = [-1]
    current_indent = -1
    
    for line in cflow_output.splitlines():
        if not line.strip():
            continue
        
        # Parse the line
        match = re.match(r'^(\s*)(\S.*?)(\s+<.*>)?(\s+\(.*\))?$', line)
        if not match:
            continue
        
        indent, name, location, args = match.groups()
        indent_level = len(indent)
        
        # Clean up function name
        if '(' in name:
            name = name.split('(')[0].strip()
        
        # Get line number if available
        line_number = 0
        if location:
            line_match = re.search(r'<\s*at\s+(\d+)\s*>', location)
            if line_match:
                line_number = int(line_match.group(1))
        
        # Process change in indentation
        if indent_level > current_indent:
            # Going deeper in the call tree
            indent_stack.append(indent_level)
            if function_stack:
                parent_name = function_stack[-1]
            else:
                parent_name = ""
        elif indent_level < current_indent:
            # Coming back up the call tree
            while indent_stack and indent_level <= indent_stack[-1]:
                indent_stack.pop()
                if function_stack:
                    function_stack.pop()
            
            if function_stack:
                parent_name = function_stack[-1]
            else:
                parent_name = ""
        else:
            # Same level, same parent
            if function_stack:
                function_stack.pop()
                if function_stack:
                    parent_name = function_stack[-1]
                else:
                    parent_name = ""
            else:
                parent_name = ""
        
        current_indent = indent_level
        function_stack.append(name)
        
        # Create or update function in call graph
        if name in call_graph.functions:
            function = call_graph.functions[name]
            function.file_path = source_file
            function.line_number = line_number
            
            if parent_name:
                function.add_caller(parent_name)
        else:
            function = Function(
                name=name,
                file_path=source_file,
                line_number=line_number
            )
            
            if parent_name:
                function.add_caller(parent_name)
            
            call_graph.add_function(function)
        
        # Update parent's calls
        if parent_name and parent_name in call_graph.functions:
            parent = call_graph.functions[parent_name]
            parent.add_call(name)
        
    return call_graph 