#!/usr/bin/env python3
"""
Validate all the enhanced template metaprogramming features.

This script tests all the template metaprogramming enhancements we've implemented
by analyzing our test files and checking for specific features.
"""
import os
import sys
import time
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config.libclang_config import configure_libclang
from src.services.clang_analyzer_service import ClangAnalyzerService
from src.models.function_model import Function, CallGraph

# Define test files
TEST_FILES = [
    "test_scripts/template_metaprogramming_test.cpp",
    "test_files/template_test.cpp"
]

# Define expected features
EXPECTED_FEATURES = {
    # Feature name: minimum expected count across all test files
    "templates": 10,
    "metafunctions": 5,
    "sfinae": 3,
    "variadic_templates": 1,
    "partial_specialization": 1
}

def validate_features():
    """Validate all template metaprogramming features."""
    print("\n=== Template Metaprogramming Features Validation ===\n")
    
    # Configure libclang
    print("Configuring libclang...")
    configure_libclang()
    
    # Initialize analyzer
    print("Initializing analyzer...")
    analyzer = ClangAnalyzerService()
    
    # Track overall feature counts
    total_features = {
        "templates": 0,
        "metafunctions": 0,
        "sfinae": 0,
        "variadic_templates": 0,
        "template_template_params": 0,
        "partial_specialization": 0,
        "concepts": 0
    }
    
    # Track function lists by feature
    functions_by_feature = {
        "templates": [],
        "metafunctions": [],
        "sfinae": [],
        "variadic_templates": [],
        "template_template_params": [],
        "partial_specialization": [],
        "concepts": []
    }
    
    # Analyze each test file
    for test_file in TEST_FILES:
        if not os.path.exists(test_file):
            print(f"WARNING: Test file {test_file} not found. Skipping.")
            continue
            
        print(f"\nAnalyzing file: {test_file}")
        call_graph = analyzer.analyze_file(test_file)
        
        # Count features
        templates = [f for f in call_graph.functions.values() if f.is_template]
        metafunctions = [f for f in call_graph.functions.values() if f.is_metafunction]
        sfinae_functions = [f for f in call_graph.functions.values() if f.has_sfinae]
        variadic_templates = [f for f in call_graph.functions.values() if f.has_variadic_templates]
        template_templates = [f for f in call_graph.functions.values() if f.template_template_params]
        partial_specializations = [f for f in call_graph.functions.values() if f.partial_specialization]
        concept_functions = [f for f in call_graph.functions.values() if f.is_concept]
        
        # Update total counts
        total_features["templates"] += len(templates)
        total_features["metafunctions"] += len(metafunctions)
        total_features["sfinae"] += len(sfinae_functions)
        total_features["variadic_templates"] += len(variadic_templates)
        total_features["template_template_params"] += len(template_templates)
        total_features["partial_specialization"] += len(partial_specializations)
        total_features["concepts"] += len(concept_functions)
        
        # Add to function lists
        functions_by_feature["templates"].extend(templates)
        functions_by_feature["metafunctions"].extend(metafunctions)
        functions_by_feature["sfinae"].extend(sfinae_functions)
        functions_by_feature["variadic_templates"].extend(variadic_templates)
        functions_by_feature["template_template_params"].extend(template_templates)
        functions_by_feature["partial_specialization"].extend(partial_specializations)
        functions_by_feature["concepts"].extend(concept_functions)
        
        # Print file-specific results
        print(f"  Templates: {len(templates)}")
        print(f"  Metafunctions: {len(metafunctions)}")
        print(f"  SFINAE functions: {len(sfinae_functions)}")
        print(f"  Variadic templates: {len(variadic_templates)}")
        print(f"  Template template parameters: {len(template_templates)}")
        print(f"  Partial specializations: {len(partial_specializations)}")
        print(f"  Concept-enabled functions: {len(concept_functions)}")
    
    # Print validation results
    print("\n=== Validation Results ===")
    all_passed = True
    
    for feature, min_count in EXPECTED_FEATURES.items():
        actual_count = total_features[feature]
        if actual_count >= min_count:
            status = "✅ PASS"
        else:
            status = "❌ FAIL"
            all_passed = False
            
        print(f"{status} - {feature}: Expected at least {min_count}, found {actual_count}")
    
    # Print summary
    print("\n=== Feature Examples ===")
    
    # Show examples of each feature type
    for feature, functions in functions_by_feature.items():
        if functions:
            print(f"\n{feature.title()} Examples:")
            for i, func in enumerate(functions[:3]):  # Show up to 3 examples
                print(f"  {i+1}. {func.name}")
                if hasattr(func, "signature") and func.signature:
                    print(f"     Signature: {func.signature}")
                if feature == "sfinae" and hasattr(func, "sfinae_techniques") and func.sfinae_techniques:
                    print(f"     SFINAE techniques: {', '.join(func.sfinae_techniques)}")
                if feature == "metafunctions" and hasattr(func, "metafunction_kind") and func.metafunction_kind:
                    print(f"     Metafunction kind: {func.metafunction_kind}")
    
    # Print overall status
    print("\n=== Overall Status ===")
    if all_passed:
        print("✅ All template metaprogramming features validated successfully!")
    else:
        print("❌ Some template metaprogramming features failed validation.")
    
    return all_passed

if __name__ == "__main__":
    success = validate_features()
    sys.exit(0 if success else 1) 