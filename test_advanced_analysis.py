import os
import json
import sys
from src.main import CodeAnalysisSystem

def print_function_with_details(func, indent=""):
    """Print function details with proper indentation"""
    print(f"{indent}Function: {func['name']}")
    print(f"{indent}File: {func['file_path']}:{func['line_number']}")
    
    # Print if function is a callback
    if func.get('is_callback', False):
        print(f"{indent}Callback Type: {func.get('callback_type', 'Unknown')}")
    
    # Print function body (first 5 lines only to prevent excessive output)
    body = func.get('function_body', '')
    if body:
        body_lines = body.split('\n')
        preview = '\n'.join(body_lines[:5])
        if len(body_lines) > 5:
            preview += "\n" + f"{indent}... (truncated, {len(body_lines)} lines total)"
        print(f"{indent}Function Body Preview:")
        print(f"{indent}---------------------------")
        for line in preview.split('\n'):
            print(f"{indent}{line}")
        print(f"{indent}---------------------------")

def analyze_function_relationships(system, function_query, max_depth=2):
    """Analyze and display function relationships with detailed information"""
    print(f"\n=== Analyzing function relationships for: {function_query} ===")
    
    # Query for the specified function
    results = system.query_by_natural_language(
        f"Find all details about the function {function_query} including its call hierarchy",
        "TargetFunction",
        extract_function_bodies=True
    )
    
    target_functions = results.get("TargetFunction", [])
    if not target_functions:
        print(f"No functions found matching '{function_query}'")
        return
    
    # Process each found function
    for func in target_functions:
        print_function_with_details(func)
        
        # Track visited functions to avoid cycles
        visited = set([func.get('name', '')])
        
        # Display functions called by this function (recursively)
        if 'calls_functions' in func and func['calls_functions']:
            print("\nCalls the following functions:")
            _print_call_tree(func['calls_functions'], visited, 1, max_depth)
        else:
            print("\nDoes not call any other functions.")
        
        # Display functions that call this function
        if 'called_by_functions' in func and func['called_by_functions']:
            print("\nCalled by the following functions:")
            for caller in func['called_by_functions']:
                print_function_with_details(caller, indent="  ")
        else:
            print("\nNot called by any other tracked functions.")
        
        # Display branch information if available
        if 'in_branch' in func and func['in_branch']:
            print("\nExists in the following branches:")
            for branch in func['in_branch']:
                print(f"  Branch Type: {branch.get('branch_node_type', 'Unknown')}")
                print(f"  Condition: {branch.get('condition', 'No condition')}")
                if 'contains' in branch and branch['contains']:
                    print("  Contains functions:")
                    for contained_func in branch['contains']:
                        print(f"    - {contained_func.get('name', 'Unknown')}")

def _print_call_tree(functions, visited, level, max_depth):
    """Recursively print the call tree"""
    indent = "  " * level
    if level > max_depth:
        print(f"{indent}... (max depth reached)")
        return
    
    for func in functions:
        func_name = func.get('name', '')
        if func_name in visited:
            print(f"{indent}Function: {func_name} (already shown)")
            continue
        
        visited.add(func_name)
        print_function_with_details(func, indent)
        
        if 'calls_functions' in func and func['calls_functions']:
            print(f"{indent}Calls:")
            _print_call_tree(func['calls_functions'], visited, level + 1, max_depth)

def analyze_callback_registrations(system):
    """Analyze callback function registrations and usage patterns"""
    print("\n=== Analyzing Callback Function Registrations ===")
    
    # Query for all callback functions and their registrations
    results = system.query_by_natural_language(
        "Find all callback functions, their registration points, and execution points",
        "CallbackAnalysis",
        extract_function_bodies=True
    )
    
    callbacks = results.get("CallbackAnalysis", [])
    if not callbacks:
        print("No callback functions found in the codebase.")
        return
    
    # Group callbacks by type
    callback_types = {}
    for callback in callbacks:
        cb_type = callback.get('callback_type', 'Unknown')
        if cb_type not in callback_types:
            callback_types[cb_type] = []
        callback_types[cb_type].append(callback)
    
    # Print callback information grouped by type
    for cb_type, funcs in callback_types.items():
        print(f"\nCallback Type: {cb_type}")
        print(f"Found {len(funcs)} callbacks of this type")
        
        for func in funcs:
            print_function_with_details(func, indent="  ")
            
            # Show where this callback is registered
            if 'called_by_functions' in func and func['called_by_functions']:
                print("  Registered/Called by:")
                for caller in func['called_by_functions']:
                    print(f"    - {caller.get('name', 'Unknown')} in {caller.get('file_path', 'Unknown')}")

def main():
    # Initialize the system
    print("Initializing CodeAnalysisSystem...")
    system = CodeAnalysisSystem()
    
    # Analyze the codebase
    source_files = [
        "test_repo/order_system.h",
        "test_repo/order_system.cpp",
        "test_repo/main.cpp"
    ]
    compile_args = [
        "-std=c++17",
        "-I", os.path.abspath("test_repo")
    ]
    print("Analyzing codebase...")
    system.analyze_codebase(source_files, compile_args)
    print("Codebase analysis completed.")
    
    # Perform specific analyses based on command-line arguments or default
    if len(sys.argv) > 1:
        function_to_analyze = sys.argv[1]
        analyze_function_relationships(system, function_to_analyze)
    else:
        # Default analyses
        analyze_function_relationships(system, "calculate_total_price")
        print("\n" + "="*60 + "\n")
        analyze_callback_registrations(system)
        
        # Demonstrate a complex query looking for price calculation with discount flows
        print("\n=== Complex Flow Analysis: Price Calculation with Discounts ===")
        flow_results = system.query_by_natural_language(
            "Find the complete flow of price calculation including discount application and tax calculation",
            "PriceCalculationFlow",
            extract_function_bodies=True
        )
        
        print(json.dumps(flow_results, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main() 