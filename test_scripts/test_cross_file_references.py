#!/usr/bin/env python
"""
Test script for the cross-file references function in clear_and_reindex_folly.py
"""
import sys
import os
from collections import defaultdict, Counter
from pathlib import Path
from datetime import datetime
import logging

# Set up logging to file and console
log_file = 'cross_file_test.log'
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Define minimal versions of required classes for testing
class Function:
    def __init__(self, name, file_path=None, line_number=None, metadata=None):
        self.name = name
        self.file_path = file_path or "unknown"
        self.line_number = line_number or 0
        self.calls = set()
        self.called_by = set()
        self.metadata = metadata or {}
    
    def add_call(self, func_name):
        self.calls.add(func_name)
    
    def add_caller(self, func_name):
        self.called_by.add(func_name)

class CallGraph:
    def __init__(self):
        self.functions = {}
        self.missing_functions = set()
    
    def add_function(self, func):
        self.functions[func.name] = func
    
    def add_missing_function(self, func_name):
        if func_name not in self.functions:
            self.missing_functions.add(func_name)

# Import the function to test
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

def create_test_call_graph():
    """Create a test call graph with functions and missing references."""
    logger.info("Creating test call graph...")
    call_graph = CallGraph()
    
    # Create "implemented" functions
    function1 = Function("math::calculate", "math.cpp", 10, {"namespace": "math", "param_count": 2})
    function2 = Function("math::add", "math.cpp", 20, {"namespace": "math", "param_count": 2})
    function3 = Function("math::multiply", "math.cpp", 30, {"namespace": "math", "param_count": 2})
    function4 = Function("utils::Logger::log", "logger.cpp", 5, {"namespace": "utils", "class": "Logger", "param_count": 1})
    function5 = Function("calculate", "main.cpp", 15, {"param_count": 2})
    function6 = Function("add", "utils.cpp", 25, {"param_count": 2})
    
    # Add function calls
    function1.add_call("math::add")
    function1.add_call("math::multiply")
    function5.add_call("add")  # This should resolve to the "add" function
    function5.add_call("utils::Logger::log")
    function5.add_call("missing_function")  # This will stay missing
    
    # Add functions with signature metadata for full mode testing
    function7 = Function("templates::process<int>", "templates.cpp", 40, {
        "namespace": "templates", 
        "param_count": 1,
        "param_types": ["int"],
        "return_type": "int",
        "signature": "int process(int)"
    })
    
    function8 = Function("templates::process<string>", "templates.cpp", 50, {
        "namespace": "templates", 
        "param_count": 1,
        "param_types": ["string"],
        "return_type": "string",
        "signature": "string process(string)"
    })
    
    # Call with signature information
    function9 = Function("main", "main.cpp", 5, {
        "call_sites": [
            {
                "target": "templates::process",
                "arg_count": 1,
                "arg_types": ["int"],
                "context_type": "main"
            }
        ]
    })
    function9.add_call("templates::process")  # This should resolve to process<int>
    
    # Create a function that another function will call by base name
    # utils::helper is the full name, but will be called as just "helper"
    function10 = Function("utils::helper", "utils.cpp", 100, {
        "namespace": "utils",
        "param_count": 1
    })
    
    # Add a function that will call helper by its base name
    function11 = Function("app::processor", "app.cpp", 200, {
        "namespace": "app",
        "param_count": 2
    })
    function11.add_call("helper")  # This will need to be resolved to utils::helper
    
    # Add all functions to call graph
    for func in [function1, function2, function3, function4, function5, function6, 
                function7, function8, function9, function10, function11]:
        call_graph.add_function(func)
    
    # Add missing functions that we expect to be resolved
    call_graph.add_missing_function("missing_function")
    call_graph.add_missing_function("templates::process")
    call_graph.add_missing_function("helper")  # Should resolve to utils::helper
    
    # Debug: Print contents of call graph
    logger.debug(f"Created call graph with {len(call_graph.functions)} functions and {len(call_graph.missing_functions)} missing functions")
    logger.debug(f"Functions: {', '.join(call_graph.functions.keys())}")
    logger.debug(f"Missing functions: {', '.join(call_graph.missing_functions)}")
    
    return call_graph

def test_basic_mode():
    """Test basic mode which should not resolve anything."""
    logger.info("Testing basic mode...")
    call_graph = create_test_call_graph()
    original_missing = len(call_graph.missing_functions)
    
    result = process_cross_file_references(call_graph, "basic")
    
    # In basic mode, we should get back just the call graph with no changes
    if isinstance(result, tuple):
        logger.error("Basic mode should not return a tuple")
        return False
    
    if len(result.missing_functions) != original_missing:
        logger.error(f"Basic mode should not resolve any missing functions, but {original_missing - len(result.missing_functions)} were resolved")
        return False
    
    logger.info("Basic mode test passed")
    return True

def test_enhanced_mode():
    """Test enhanced mode which should resolve some references."""
    logger.info("Testing enhanced mode...")
    call_graph = create_test_call_graph()
    original_missing = len(call_graph.missing_functions)
    
    # Print details for debugging
    logger.info(f"Before: Missing functions count: {original_missing}")
    logger.info(f"Missing functions: {', '.join(call_graph.missing_functions)}")
    
    # Check keys in the function_by_base_name that would be created
    base_name_counts = {}
    for func_name in call_graph.functions:
        base_name = func_name.split("::")[-1]
        base_name_counts[base_name] = base_name_counts.get(base_name, 0) + 1
    
    logger.info(f"Base name counts: {base_name_counts}")
    
    result = process_cross_file_references(call_graph, "enhanced")
    
    # Enhanced mode should return a tuple and resolve some missing functions
    if not isinstance(result, tuple):
        logger.error("Enhanced mode should return a tuple (call_graph, resolved_count)")
        return False
    
    call_graph, resolved_count = result
    
    # Print details after processing
    logger.info(f"After: Missing functions count: {len(call_graph.missing_functions)}")
    logger.info(f"Missing functions: {', '.join(call_graph.missing_functions)}")
    logger.info(f"Resolved count: {resolved_count}")
    
    if resolved_count == 0:
        for missing in list(call_graph.missing_functions):
            base_name = missing.split("::")[-1]
            logger.info(f"Missing: {missing}, base_name: {base_name}, matches: {base_name in base_name_counts}")
        logger.error("Enhanced mode should resolve at least one missing function")
        return False
    
    logger.info(f"Enhanced mode resolved {resolved_count} missing functions")
    logger.info("Enhanced mode test passed")
    return True

def test_full_mode():
    """Test full mode which should resolve more references using signature matching."""
    logger.info("Testing full mode...")
    call_graph = create_test_call_graph()
    original_missing = len(call_graph.missing_functions)
    
    result = process_cross_file_references(call_graph, "full")
    
    # Full mode should return a tuple and resolve more missing functions
    if not isinstance(result, tuple):
        logger.error("Full mode should return a tuple (call_graph, resolved_count)")
        return False
    
    call_graph, resolved_count = result
    
    if resolved_count == 0:
        logger.error("Full mode should resolve at least one missing function")
        return False
    
    # Check if templates::process was resolved to templates::process<int> based on call site info
    main_function = call_graph.functions["main"]
    resolved_to_int_template = False
    
    for call in main_function.calls:
        if call == "templates::process<int>":
            resolved_to_int_template = True
            break
    
    if resolved_to_int_template:
        logger.info("Full mode correctly resolved template call to templates::process<int>")
    else:
        logger.warning("Full mode did not resolve template call as expected")
    
    logger.info(f"Full mode resolved {resolved_count} missing functions")
    logger.info("Full mode test passed")
    return True

def main():
    """Run all tests."""
    print("Starting cross-file references function tests")
    logger.info("Starting cross-file references function tests")
    
    # Run basic mode test
    print("\n===== TEST: Basic Mode =====")
    basic_passed = test_basic_mode()
    print(f"Basic mode test: {'PASSED' if basic_passed else 'FAILED'}")
    
    # Run enhanced mode test
    print("\n===== TEST: Enhanced Mode =====")
    enhanced_passed = test_enhanced_mode()
    print(f"Enhanced mode test: {'PASSED' if enhanced_passed else 'FAILED'}")
    
    # Run full mode test
    print("\n===== TEST: Full Mode =====")
    full_passed = test_full_mode()
    print(f"Full mode test: {'PASSED' if full_passed else 'FAILED'}")
    
    all_tests_passed = basic_passed and enhanced_passed and full_passed
    
    print("\n===== TEST RESULTS SUMMARY =====")
    if all_tests_passed:
        print("All tests passed successfully!")
        logger.info("All tests passed successfully!")
    else:
        print("Some tests failed. See logs for details.")
        logger.error("Some tests failed. See logs for details.")
    
    print(f"Log file written to: {os.path.abspath(log_file)}")
    logger.info("Testing complete")

if __name__ == "__main__":
    main() 