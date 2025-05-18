#!/usr/bin/env python
"""
Basic test script for analyzing C/C++ code and storing in Neo4j.
This version doesn't require libclang to work.
"""
import os
import re
import sys
import argparse
from src.models.function_model import Function, CallGraph
from src.services.neo4j_service import Neo4jService
from src.config.settings import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Basic C/C++ analyzer")
    parser.add_argument("file", help="File to analyze")
    parser.add_argument("--project", default="test_basic", help="Project name for Neo4j")
    parser.add_argument("--clear", action="store_true", help="Clear existing Neo4j data for project")
    return parser.parse_args()

def basic_analyze_file(file_path):
    """
    A very basic function analyzer for C/C++ that doesn't rely on libclang.
    Uses regex pattern matching instead.
    
    Args:
        file_path: Path to the C/C++ file
        
    Returns:
        CallGraph with identified functions and relationships
    """
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return CallGraph()
        
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Define patterns for different function declaration types
    patterns = [
        # Regular functions: return_type function_name(...) { ... }
        r'(\w+(?:\s*\*)?)\s+(\w+)\s*\([^)]*\)\s*{',
        # Class methods: type Class::method(...) { ... }
        r'(\w+(?:\s*\*)?)\s+(\w+)::\w+\s*\([^)]*\)\s*{',
        # Constructors/destructors: Class::Class(...) { ... }
        r'(\w+)::(\w+)\s*\([^)]*\)\s*{'
    ]
    
    call_graph = CallGraph()
    
    # Find functions
    functions = {}
    for pattern in patterns:
        for match in re.finditer(pattern, content):
            if len(match.groups()) >= 2:
                func_name = match.group(2)
                
                # Create function if it doesn't exist
                if func_name not in functions:
                    func = Function(
                        name=func_name,
                        file_path=file_path,
                        line_number=content[:match.start()].count('\n') + 1
                    )
                    functions[func_name] = func
    
    # Find function calls
    for func_name, func in functions.items():
        # Extract function body
        func_pattern = f"{func_name}\\s*\\([^)]*\\)\\s*{{(.*?)}}"
        body_match = re.search(func_pattern, content, re.DOTALL)
        
        if body_match:
            body = body_match.group(1)
            func.body = body
            
            # Find calls to other functions
            for other_func_name in functions:
                if other_func_name == func_name:
                    continue  # Skip self
                    
                # Simple pattern for function calls: function_name(...)
                call_pattern = f"{other_func_name}\\s*\\("
                if re.search(call_pattern, body):
                    func.add_call(other_func_name)
                    functions[other_func_name].add_caller(func_name)
    
    # Add functions to call graph
    for func in functions.values():
        call_graph.add_function(func)
        
    return call_graph

def main():
    """Main function."""
    args = parse_args()
    
    print(f"Analyzing file: {args.file}")
    call_graph = basic_analyze_file(args.file)
    
    print(f"Found {len(call_graph.functions)} functions:")
    for name, func in call_graph.functions.items():
        print(f"- {name} (line {func.line_number})")
        if func.calls:
            print(f"  Calls: {', '.join(func.calls)}")
        if func.called_by:
            print(f"  Called by: {', '.join(func.called_by)}")
    
    # Index in Neo4j
    try:
        neo4j_service = Neo4jService(
            uri=NEO4J_URI,
            username=NEO4J_USER,
            password=NEO4J_PASSWORD
        )
        
        # Test connection
        connected = neo4j_service.test_connection()
        if not connected:
            print("Error: Could not connect to Neo4j database.")
            sys.exit(1)
            
        print(f"Indexing functions in Neo4j (project: {args.project})...")
        if args.clear:
            neo4j_service.clear_project(args.project)
            
        # First create all function nodes
        for name, func in call_graph.functions.items():
            with neo4j_service.driver.session() as session:
                session.run("""
                MERGE (f:Function {name: $name, project: $project})
                SET f.file_path = $file_path,
                    f.line_number = $line_number,
                    f.signature = $signature
                """, 
                name=name,
                project=args.project,
                file_path=func.file_path,
                line_number=func.line_number,
                signature=func.signature or ""
                )
        
        # Then create all CALLS relationships
        for name, func in call_graph.functions.items():
            for callee in func.calls:
                with neo4j_service.driver.session() as session:
                    session.run("""
                    MATCH (caller:Function {name: $caller_name, project: $project})
                    MATCH (callee:Function {name: $callee_name, project: $project})
                    MERGE (caller)-[:CALLS]->(callee)
                    """,
                    caller_name=name,
                    callee_name=callee,
                    project=args.project
                    )
            
        print("Indexing complete.")
        
    except Exception as e:
        print(f"Error during Neo4j indexing: {e}")

if __name__ == "__main__":
    main() 