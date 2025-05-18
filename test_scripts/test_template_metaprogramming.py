#!/usr/bin/env python3
"""
Test script for advanced template metaprogramming analysis.

This script runs the analyzer on a sample C++ file with various template metaprogramming
techniques and verifies that the features are correctly detected.
"""
import os
import sys
import traceback
from pathlib import Path

# Add parent directory to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

# Test file path
TEST_FILE = os.path.join(current_dir, "template_metaprogramming_test.cpp")
PROJECT_NAME = "template_metaprogramming_test"

def test_analyzer():
    """Test the analyzer on the template metaprogramming test file."""
    print("\n=== Testing Analyzer on Template Metaprogramming Features ===\n")
    
    try:
        # Configure libclang first
        print("Configuring libclang...")
        try:
            from src.config.libclang_config import configure_libclang
            configure_libclang()
            
            # Test libclang compatibility
            print("Testing libclang compatibility...")
            from clang.cindex import Index, Config
            try:
                index = Index.create()
                print("Successfully created Index - libclang is working correctly")
            except Exception as e:
                print(f"ERROR: Could not create clang Index: {e}")
                print("Detailed error information:")
                traceback.print_exc()
                print("\nPlease check your libclang installation and version compatibility.")
                return
        except Exception as e:
            print(f"ERROR: Could not configure libclang: {e}")
            print("Detailed error information:")
            traceback.print_exc()
            return
        
        # Import required modules
        print("Importing required modules...")
        from src.services.clang_analyzer_service import ClangAnalyzerService
        from src.models.function_model import Function, CallGraph
        
        # Initialize analyzer
        print("Initializing analyzer service...")
        try:
            analyzer = ClangAnalyzerService()
        except Exception as e:
            print(f"ERROR: Could not initialize ClangAnalyzerService: {e}")
            print("Detailed error information:")
            traceback.print_exc()
            return
        
        # Analyze the test file directly (without Neo4j)
        print(f"Analyzing file: {TEST_FILE}")
        try:
            call_graph = analyzer.analyze_file(TEST_FILE)
        except Exception as e:
            print(f"ERROR: Failed to analyze file: {e}")
            print("Detailed error information:")
            traceback.print_exc()
            return
        
        # Print functions found
        print(f"\nFound {len(call_graph.functions)} functions/classes:")
        for name in sorted(call_graph.functions.keys()):
            print(f"  - {name}")
        
        # Test feature detection - focus on SFINAE first
        print("\n--- Testing SFINAE Detection in Detail ---")
        test_sfinae_detection(call_graph)
        
        # Also test other features
        test_metafunction_detection(call_graph)
        test_variadic_template_detection(call_graph)
        test_template_template_detection(call_graph)
        test_partial_specialization_detection(call_graph)
        
        # Optional: Try Neo4j operations if requested
        if "--use-neo4j" in sys.argv:
            try_neo4j_operations(call_graph)
        
    except ImportError as e:
        print(f"ERROR: Import error - {e}")
        print("Make sure you're running this script from the project root directory.")
        traceback.print_exc()
    except Exception as e:
        print(f"ERROR: {e}")
        traceback.print_exc()

def try_neo4j_operations(call_graph):
    """Try to connect to Neo4j and index the call graph if possible."""
    try:
        from src.services.neo4j_service import Neo4jService
        from src.services.search_service import SearchService
        from src.config.settings import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
        
        # Initialize services
        print("\nInitializing Neo4j service...")
        neo4j = Neo4jService(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
        
        # Test Neo4j connection
        if not neo4j.test_connection():
            print("ERROR: Could not connect to Neo4j. Please make sure Neo4j is running.")
            return
        
        search = SearchService(neo4j_service=neo4j)
        
        # Clear any existing data for this test project
        print(f"Clearing existing data for project: {PROJECT_NAME}")
        neo4j.clear_project(PROJECT_NAME)
        
        # Index the results in Neo4j
        print("\nIndexing in Neo4j...")
        neo4j.index_call_graph(call_graph, PROJECT_NAME)
        
        # Test natural language queries for SFINAE
        print("\n--- Testing SFINAE-specific Queries ---")
        test_sfinae_queries(search)
    except Exception as e:
        print(f"ERROR with Neo4j operations: {e}")
        traceback.print_exc()

def test_sfinae_detection(call_graph):
    """Test that SFINAE techniques are correctly detected."""
    print("\nTesting SFINAE techniques detection:")
    
    # List of functions using various SFINAE techniques
    sfinae_functions = [
        ("is_even", ["enable_if"]),
        ("get_size", ["decltype"]),
        ("has_resize_method", ["tag_dispatch"]),
        ("has_value_type", ["void_t"]),
        ("has_ostream_operator", ["expression_sfinae"]),
        ("detector", ["void_t"]),
    ]
    
    for name, expected_techniques in sfinae_functions:
        print(f"\nChecking SFINAE in function: {name}")
        
        if name in call_graph.functions:
            func = call_graph.functions[name]
            print(f"  Function details:")
            print(f"  - is_template: {func.is_template}")
            print(f"  - has_sfinae: {func.has_sfinae}")
            print(f"  - sfinae_techniques: {func.sfinae_techniques}")
            
            # Validate has_sfinae flag
            if func.has_sfinae:
                print(f"  ✅ Correctly detected SFINAE usage")
            else:
                print(f"  ❌ Failed to detect SFINAE usage")
            
            # Validate detected techniques
            if not func.sfinae_techniques:
                print(f"  ❌ No SFINAE techniques detected")
            else:
                found_any = False
                for technique in expected_techniques:
                    if any(t.lower() == technique.lower() for t in func.sfinae_techniques):
                        print(f"  ✅ Correctly detected {technique} technique")
                        found_any = True
                    else:
                        print(f"  ❓ Did not detect {technique} technique")
                
                if not found_any:
                    print(f"  ❌ None of the expected techniques were detected")
        else:
            print(f"  ❌ Function not found in analyzed code")
    
    # Print overall statistics
    sfinae_count = sum(1 for func in call_graph.functions.values() if func.has_sfinae)
    print(f"\nFound {sfinae_count} functions using SFINAE techniques out of {len(call_graph.functions)} total functions")

def test_metafunction_detection(call_graph):
    """Test that metafunctions are correctly detected."""
    print("\n--- Testing Metafunction Detection ---")
    
    # Check specific type trait metafunctions
    metafunctions = [
        ("is_void_like", "value_trait"),
        ("add_const_ref", "type_trait"),
    ]
    
    for name, kind in metafunctions:
        if name in call_graph.functions:
            func = call_graph.functions[name]
            print(f"Found metafunction {name}: is_metafunction={func.is_metafunction}, kind={func.metafunction_kind}")
            
            if func.is_template:
                print(f"✅ Correctly detected {name} as a template")
            else:
                print(f"❌ Failed to detect {name} as a template")
                
            if func.is_metafunction:
                print(f"✅ Correctly detected {name} as a metafunction")
            else:
                print(f"❌ Failed to detect {name} as a metafunction")
            
            if func.metafunction_kind == kind:
                print(f"✅ Correctly detected {name} as {kind}")
            else:
                print(f"❌ Failed to detect correct metafunction kind for {name} (found {func.metafunction_kind}, expected {kind})")
        else:
            print(f"❌ Failed to find metafunction {name}")

def test_variadic_template_detection(call_graph):
    """Test that variadic templates are correctly detected."""
    print("\n--- Testing Variadic Template Detection ---")
    
    variadic_tests = [
        "pack_size",
        "print_all"
    ]
    
    for name in variadic_tests:
        if name in call_graph.functions:
            func = call_graph.functions[name]
            print(f"Found variadic template {name}: has_variadic_templates={func.has_variadic_templates}")
            
            if func.is_template:
                print(f"✅ Correctly detected {name} as a template")
            else:
                print(f"❌ Failed to detect {name} as a template")
                
            if func.has_variadic_templates:
                print(f"✅ Correctly detected {name} as variadic template")
            else:
                print(f"❌ Failed to detect {name} as variadic template")
        else:
            print(f"❌ Failed to find variadic template {name}")

def test_template_template_detection(call_graph):
    """Test that template template parameters are correctly detected."""
    print("\n--- Testing Template Template Parameter Detection ---")
    
    if "apply_trait" in call_graph.functions:
        func = call_graph.functions["apply_trait"]
        print(f"Found template template function: template_template_params={func.template_template_params}")
        
        if func.is_template:
            print(f"✅ Correctly detected apply_trait as a template")
        else:
            print(f"❌ Failed to detect apply_trait as a template")
            
        if func.template_template_params:
            print(f"✅ Correctly detected template template parameters")
        else:
            print(f"❌ Failed to detect template template parameters")
    else:
        print(f"❌ Failed to find template template function apply_trait")

def test_partial_specialization_detection(call_graph):
    """Test that partial specialization is correctly detected."""
    print("\n--- Testing Partial Specialization Detection ---")
    
    # The specialization of is_same<T, T> should be detected
    # Find the specialized version by looking for matching names
    specialized_name = None
    for name in call_graph.functions:
        if "is_same" in name and "<" in name:
            specialized_name = name
            break
    
    if specialized_name:
        func = call_graph.functions[specialized_name]
        print(f"Found specialization: {specialized_name}")
        print(f"  partial_specialization={func.partial_specialization}")
        
        if func.partial_specialization:
            print(f"✅ Correctly detected partial specialization")
        else:
            print(f"❌ Failed to detect partial specialization")
    else:
        print(f"❌ Failed to find partial specialization function for is_same")

def test_sfinae_queries(search):
    """Test natural language queries for SFINAE features."""
    print("\nTesting SFINAE-specific natural language queries:")
    
    # Import the detect_metaprogramming_features function
    try:
        from src.cmd.nlquery import detect_metaprogramming_features
        
        # SFINAE-specific queries
        sfinae_queries = [
            "functions using SFINAE",
            "enable_if examples",
            "find template functions with decltype",
            "show me code using substitution failure",
            "tag dispatch pattern"
        ]
        
        for query in sfinae_queries:
            print(f"\nQuery: '{query}'")
            
            # Check if the query is detected as SFINAE-related
            features = detect_metaprogramming_features(query)
            print(f"Detected features: {features}")
            
            # Verify that SFINAE is detected
            if "has_sfinae" in features and features["has_sfinae"]:
                print(f"✅ Correctly identified as SFINAE-related query")
            else:
                print(f"❌ Failed to identify as SFINAE-related query")
            
            # If a specific technique is mentioned, check for it
            if "sfinae_technique" in features:
                print(f"✅ Correctly identified specific technique: {features['sfinae_technique']}")
            
            # Perform search
            if features:
                results = search.find_by_metaprogramming_features(
                    project_name=PROJECT_NAME,
                    **features
                )
                
                print(f"Found {len(results)} matching functions:")
                for i, result in enumerate(results[:3], 1):
                    print(f"  {i}. {result.get('name', 'Unknown')}")
    except Exception as e:
        print(f"Error in SFINAE queries test: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    test_analyzer() 