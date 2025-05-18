#!/usr/bin/env python
"""
Test script to analyze class hierarchy and virtual method override detection.
"""
import os
import sys
import logging
from pathlib import Path

# Add parent directory to path to import project modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.clang_analyzer_service import ClangAnalyzerService
from src.services.neo4j_service import Neo4jService

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    """Test class hierarchy and virtual method analysis."""
    # Path to the test file
    test_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                             "test_files", "test_virtual_methods.cpp")
    
    if not os.path.exists(test_file):
        logger.error(f"Test file not found: {test_file}")
        return
    
    # Initialize analyzer
    logger.info(f"Initializing analyzer for file: {test_file}")
    analyzer = ClangAnalyzerService()
    
    # Analyze the file with focus on tracking virtual methods
    logger.info("Analyzing file...")
    call_graph = analyzer.analyze_file(test_file, analyze_templates=True, track_virtual_methods=True)
    
    # Report overall results
    logger.info(f"Found {len(call_graph.functions)} functions and methods")
    
    # Identify all classes
    classes = set()
    for name, func in call_graph.functions.items():
        if func.is_member and func.class_name:
            classes.add(func.class_name)
    
    logger.info(f"Found {len(classes)} classes: {', '.join(classes)}")
    
    # Analyze class hierarchy
    class_hierarchy = {}
    for name, func in call_graph.functions.items():
        if func.is_member and func.class_hierarchy:
            if func.class_name not in class_hierarchy:
                class_hierarchy[func.class_name] = set()
            for base in func.class_hierarchy:
                class_hierarchy[func.class_name].add(base)
    
    # Print class hierarchy
    logger.info("\n=== Class Hierarchy ===")
    for derived, bases in class_hierarchy.items():
        logger.info(f"{derived} derives from: {', '.join(bases)}")
    
    # Find all virtual methods
    logger.info("\n=== Virtual Methods ===")
    virtual_methods = {}
    for name, func in call_graph.functions.items():
        if func.is_virtual:
            if func.class_name not in virtual_methods:
                virtual_methods[func.class_name] = []
            virtual_methods[func.class_name].append(name)
    
    for class_name, methods in virtual_methods.items():
        logger.info(f"Class {class_name} has {len(methods)} virtual methods:")
        for method in methods:
            logger.info(f"  - {method}")
    
    # Find override relationships
    logger.info("\n=== Method Overrides ===")
    for name, func in call_graph.functions.items():
        if func.is_virtual and func.overrides:
            logger.info(f"{name} overrides: {', '.join(func.overrides)}")
    
    # Check for multiple inheritance
    logger.info("\n=== Multiple Inheritance ===")
    multiple_inheritance = []
    for class_name, bases in class_hierarchy.items():
        if len(bases) > 1:
            multiple_inheritance.append((class_name, bases))
    
    if multiple_inheritance:
        for class_name, bases in multiple_inheritance:
            logger.info(f"{class_name} has multiple base classes: {', '.join(bases)}")
    else:
        logger.info("No multiple inheritance detected.")
    
    # Check for polymorphic function calls
    logger.info("\n=== Polymorphic Function Calls ===")
    polymorphic_calls = []
    
    # Look at calls to makeSound method through different paths
    for name, func in call_graph.functions.items():
        if "makeSound" in name:
            for caller in func.called_by:
                if not caller.endswith("::makeSound"):
                    # This is likely a polymorphic call
                    polymorphic_calls.append((caller, name))
    
    if polymorphic_calls:
        for caller, callee in polymorphic_calls:
            logger.info(f"Polymorphic call: {caller} calls {callee}")
    else:
        logger.info("No polymorphic calls detected.")
    
    # Optional: Store in Neo4j for further analysis
    store_in_neo4j = False
    if store_in_neo4j:
        logger.info("\n=== Storing in Neo4j ===")
        try:
            neo4j = Neo4jService(uri="bolt://localhost:7688", 
                                 username="neo4j", 
                                 password="password")
            
            # Test connection
            if neo4j.test_connection():
                logger.info("Connected to Neo4j")
                
                # Clear existing project data
                neo4j.clear_project("virtual_test")
                
                # Index the call graph
                neo4j.index_call_graph(call_graph, "virtual_test", clear=False)
                logger.info("Successfully indexed in Neo4j")
            else:
                logger.error("Failed to connect to Neo4j")
        except Exception as e:
            logger.error(f"Error with Neo4j: {e}")

if __name__ == "__main__":
    main() 