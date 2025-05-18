"""
Simple test script to analyze template metaprogramming features.
"""
import os
import sys
from src.config.libclang_config import configure_libclang
from src.services.clang_analyzer_service import ClangAnalyzerService
from src.services.neo4j_service import Neo4jService
from src.models.function_model import Function, CallGraph
from src.config.settings import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD

def main():
    """Run the test."""
    print("\n=== Testing Template Metaprogramming Features ===\n")
    
    # Configure libclang
    print("Configuring libclang...")
    configure_libclang()
    
    # Initialize analyzer service
    print("Initializing analyzer service...")
    analyzer = ClangAnalyzerService()
    
    # Get test file path
    test_file = os.path.join("tests", "template_metaprogramming_test.cpp")
    if not os.path.exists(test_file):
        print(f"Error: Test file {test_file} not found")
        return
    
    # Analyze the file
    print(f"Analyzing file: {test_file}")
    call_graph = analyzer.analyze_file(test_file)
    
    # Print results
    print(f"\nFound {len(call_graph.functions)} functions/classes:")
    for func_name in sorted(call_graph.functions.keys()):
        func = call_graph.functions[func_name]
        print(f"  - {func_name}")
        
        # Print template info
        if func.is_template:
            print(f"    Template: Yes")
            if func.template_params:
                print(f"    Template parameters: {', '.join(func.template_params)}")
        
        # Print metafunction info
        if func.is_metafunction:
            print(f"    Metafunction: Yes (kind: {func.metafunction_kind})")
        
        # Print SFINAE info
        if func.has_sfinae:
            print(f"    SFINAE: Yes")
            if func.sfinae_techniques:
                print(f"    SFINAE techniques: {', '.join(func.sfinae_techniques)}")
        
        # Print variadic template info
        if func.has_variadic_templates:
            print(f"    Variadic template: Yes")
            if func.variadic_template_param:
                print(f"    Parameter pack: {func.variadic_template_param}")
    
    # Print summary
    print("\n=== Summary ===")
    metafunctions = [f for f in call_graph.functions.values() if f.is_metafunction]
    sfinae_functions = [f for f in call_graph.functions.values() if f.has_sfinae]
    variadic_templates = [f for f in call_graph.functions.values() if f.has_variadic_templates]
    
    print(f"Total functions/classes: {len(call_graph.functions)}")
    print(f"Template metafunctions: {len(metafunctions)}")
    print(f"Functions using SFINAE: {len(sfinae_functions)}")
    print(f"Variadic templates: {len(variadic_templates)}")

if __name__ == "__main__":
    main() 