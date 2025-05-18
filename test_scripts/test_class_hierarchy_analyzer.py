#!/usr/bin/env python
"""
Enhanced test script for analyzing class hierarchies and virtual methods.

This script analyzes C++ class hierarchies, virtual method overrides, 
and polymorphic function calls using the ClangAnalyzerService.
"""
import os
import sys
import logging
import json
from pathlib import Path
from typing import Dict, List, Set, Any, Optional

# Add parent directory to path to import project modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.clang_analyzer_service import ClangAnalyzerService
from src.services.neo4j_service import Neo4jService

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ClassHierarchyAnalyzer:
    """
    Analyzes C++ class hierarchies and virtual method relationships.
    
    This class provides functionality to analyze class hierarchies, virtual method
    overrides, and polymorphic function calls in C++ code using ClangAnalyzerService.
    """
    
    def __init__(self, file_path: str):
        """Initialize the analyzer with the file to analyze."""
        self.file_path = file_path
        self.analyzer = ClangAnalyzerService()
        self.call_graph = None
        self.results = {}
        
    def analyze(self) -> Dict[str, Any]:
        """
        Perform analysis on the C++ file and return results.
        
        Returns:
            Dict containing analysis results
        """
        logger.info(f"Analyzing file: {self.file_path}")
        
        # Analyze the file with enhanced template and virtual method tracking
        self.call_graph = self.analyzer.analyze_file(
            self.file_path, 
            analyze_templates=True, 
            track_virtual_methods=True,
            cross_file_mode="enhanced"
        )
        
        if not self.call_graph or not self.call_graph.functions:
            logger.error("Analysis failed or no functions found")
            return {}
        
        # Extract the various analysis results
        self.results = {
            "file_path": self.file_path,
            "total_functions": len(self.call_graph.functions),
            "function_names": list(self.call_graph.functions.keys()),
            "class_hierarchy": self._get_class_hierarchy(),
            "virtual_methods": self._get_virtual_methods(),
            "override_relationships": self._get_override_relationships(),
            "polymorphic_calls": self._get_polymorphic_calls(),
            "virtual_method_metrics": self._calculate_virtual_method_metrics(),
            "override_chains": self._get_override_chains(),
            "multiple_inheritance": self._get_multiple_inheritance(),
        }
        
        return self.results
    
    def _get_class_hierarchy(self) -> Dict[str, List[str]]:
        """Extract the class hierarchy."""
        hierarchy = {}
        for func in self.call_graph.functions.values():
            if func.is_member and func.class_name and func.class_hierarchy:
                if func.class_name not in hierarchy:
                    hierarchy[func.class_name] = func.class_hierarchy
        return hierarchy
    
    def _get_virtual_methods(self) -> Dict[str, List[str]]:
        """Get all virtual methods organized by class."""
        virtual_methods = {}
        for name, func in self.call_graph.functions.items():
            if func.is_virtual:
                if func.class_name not in virtual_methods:
                    virtual_methods[func.class_name] = []
                virtual_methods[func.class_name].append(name)
        return virtual_methods
    
    def _get_override_relationships(self) -> List[Dict[str, str]]:
        """Get all override relationships between methods."""
        relationships = []
        for name, func in self.call_graph.functions.items():
            if func.is_virtual and func.overrides:
                for base_method in func.overrides:
                    relationships.append({
                        "derived": name,
                        "base": base_method
                    })
        return relationships
    
    def _get_polymorphic_calls(self) -> List[Dict[str, str]]:
        """Identify likely polymorphic function calls."""
        polymorphic_calls = []
        
        # Look for virtual methods
        for func_name, func in self.call_graph.functions.items():
            if func.is_virtual:
                for caller in func.called_by:
                    if caller in self.call_graph.functions:
                        caller_func = self.call_graph.functions[caller]
                        # Skip calls from methods in the same class (non-polymorphic)
                        if caller_func.is_member and caller_func.class_name == func.class_name:
                            continue
                            
                        # Any other call to a virtual method is potentially polymorphic
                        polymorphic_calls.append({
                            "caller": caller,
                            "callee": func_name,
                            "caller_type": "method" if caller_func.is_member else "function",
                            "callee_class": func.class_name
                        })
        
        return polymorphic_calls
    
    def _calculate_virtual_method_metrics(self) -> Dict[str, Any]:
        """Calculate metrics related to virtual methods and class hierarchies."""
        # Get count of virtual methods
        virtual_methods = [f for f in self.call_graph.functions.values() if f.is_virtual]
        class_hierarchy = self._get_class_hierarchy()
        all_classes = set(f.class_name for f in self.call_graph.functions.values() if f.is_member)
        
        # Calculate metrics
        metrics = {
            "total_virtual_methods": len(virtual_methods),
            "total_classes": len(all_classes),
            "classes_with_virtual_methods": len(set(f.class_name for f in virtual_methods)),
            "average_virtual_methods_per_class": len(virtual_methods) / max(1, len(all_classes)),
            "max_inheritance_depth": max((len(bases) for bases in class_hierarchy.values()), default=0),
            "classes_with_multiple_inheritance": sum(1 for bases in class_hierarchy.values() if len(bases) > 1),
            "total_override_relationships": sum(len(f.overrides) for f in self.call_graph.functions.values()),
        }
        
        return metrics
    
    def _get_override_chains(self) -> Dict[str, List[List[str]]]:
        """Find chains of method overrides across inheritance hierarchies."""
        if not self.call_graph:
            return {}
            
        # Get virtual methods grouped by method name (not qualified)
        method_name_groups = {}
        for func in self.call_graph.functions.values():
            if func.is_virtual:
                method_name = self._get_method_name(func.name)
                if method_name not in method_name_groups:
                    method_name_groups[method_name] = []
                method_name_groups[method_name].append(func.name)
        
        # For each group, establish override relationships
        override_chains = {}
        for method_name, qualified_names in method_name_groups.items():
            chains = []
            base_methods = []
            
            # Find methods that don't override anything (base methods)
            for qualified_name in qualified_names:
                if not self.call_graph.functions[qualified_name].overrides:
                    base_methods.append(qualified_name)
                    
            # For each base method, build chains
            for base_method in base_methods:
                chain = [base_method]
                self._build_override_chain(base_method, chain, chains)
                
            if chains:
                override_chains[method_name] = chains
                
        return override_chains
    
    def _build_override_chain(self, method_name: str, current_chain: List[str], all_chains: List[List[str]]) -> None:
        """
        Recursively build a chain of method overrides.
        
        Args:
            method_name: Current method in the chain.
            current_chain: Current override chain being built.
            all_chains: List to store complete chains.
        """
        # Find methods that override this one
        overriders = []
        for name, func in self.call_graph.functions.items():
            if func.overrides and method_name in func.overrides:
                overriders.append(name)
                
        if not overriders:
            # End of chain, make a copy to store
            all_chains.append(list(current_chain))
        else:
            # For each overrider, continue the chain
            for overrider in overriders:
                # Avoid cycles in the override chain
                if overrider not in current_chain:
                    current_chain.append(overrider)
                    self._build_override_chain(overrider, current_chain, all_chains)
                    current_chain.pop()  # Backtrack
    
    def _get_method_name(self, qualified_name: str) -> str:
        """Extract the method name from a qualified name."""
        if "::" in qualified_name:
            return qualified_name.split("::")[-1]
        return qualified_name
    
    def _get_multiple_inheritance(self) -> List[Dict[str, Any]]:
        """Identify classes that use multiple inheritance."""
        multiple_inheritance = []
        class_hierarchy = self._get_class_hierarchy()
        
        for class_name, bases in class_hierarchy.items():
            if len(bases) > 1:
                multiple_inheritance.append({
                    "class": class_name,
                    "base_classes": bases
                })
                
        return multiple_inheritance
    
    def print_results(self) -> None:
        """Print analysis results in a human-readable format."""
        if not self.results:
            logger.error("No results to print. Run analyze() first.")
            return
            
        print("\n===== CLASS HIERARCHY ANALYSIS RESULTS =====\n")
        
        # Print class hierarchy
        print("\n=== CLASS HIERARCHY ===")
        hierarchy = self.results.get("class_hierarchy", {})
        if hierarchy:
            for derived, bases in hierarchy.items():
                print(f"{derived} derives from: {', '.join(bases)}")
        else:
            print("No class hierarchies detected.")
        
        # Print virtual methods
        print("\n=== VIRTUAL METHODS ===")
        virtual_methods = self.results.get("virtual_methods", {})
        if virtual_methods:
            for class_name, methods in virtual_methods.items():
                print(f"Class {class_name} has {len(methods)} virtual methods:")
                for method in methods:
                    print(f"  - {method}")
        else:
            print("No virtual methods detected.")
        
        # Print override relationships
        print("\n=== METHOD OVERRIDES ===")
        overrides = self.results.get("override_relationships", [])
        if overrides:
            for override in overrides:
                print(f"{override['derived']} overrides {override['base']}")
        else:
            print("No override relationships detected.")
        
        # Print multiple inheritance
        print("\n=== MULTIPLE INHERITANCE ===")
        multiple_inheritance = self.results.get("multiple_inheritance", [])
        if multiple_inheritance:
            for item in multiple_inheritance:
                print(f"{item['class']} inherits from multiple base classes: {', '.join(item['base_classes'])}")
        else:
            print("No multiple inheritance detected.")
        
        # Print polymorphic calls
        print("\n=== POLYMORPHIC FUNCTION CALLS ===")
        polymorphic_calls = self.results.get("polymorphic_calls", [])
        if polymorphic_calls:
            for call in polymorphic_calls:
                print(f"Polymorphic call: {call['caller']} calls {call['callee']}")
        else:
            print("No polymorphic calls detected.")
        
        # Print override chains
        print("\n=== OVERRIDE CHAINS ===")
        override_chains = self.results.get("override_chains", {})
        if override_chains:
            for method_name, chains in override_chains.items():
                print(f"Method '{method_name}' override chains:")
                for i, chain in enumerate(chains, 1):
                    print(f"  Chain {i}: {' -> '.join(chain)}")
        else:
            print("No override chains detected.")
        
        # Print metrics
        print("\n=== VIRTUAL METHOD METRICS ===")
        metrics = self.results.get("virtual_method_metrics", {})
        if metrics:
            for metric, value in metrics.items():
                print(f"{metric}: {value}")
        else:
            print("No metrics calculated.")
    
    def export_results(self, output_file: str) -> None:
        """Export analysis results to a JSON file."""
        if not self.results:
            logger.error("No results to export. Run analyze() first.")
            return
            
        with open(output_file, 'w') as f:
            json.dump(self.results, f, indent=2)
            
        logger.info(f"Results exported to {output_file}")
    
    def index_in_neo4j(self, project_name: str = "class_hierarchy_test", 
                     uri: str = "bolt://localhost:7688",
                     username: str = "neo4j",
                     password: str = "password") -> bool:
        """Index analysis results in Neo4j for visualization."""
        if not self.call_graph:
            logger.error("No call graph to index. Run analyze() first.")
            return False
            
        try:
            logger.info("Connecting to Neo4j...")
            neo4j = Neo4jService(uri=uri, username=username, password=password)
            
            # Test connection
            if not neo4j.test_connection():
                logger.error("Failed to connect to Neo4j.")
                return False
                
            logger.info("Connected to Neo4j. Clearing existing project data...")
            neo4j.clear_project(project_name)
            
            logger.info("Indexing call graph...")
            neo4j.index_call_graph(self.call_graph, project_name, clear=False)
            
            logger.info("Successfully indexed in Neo4j")
            return True
            
        except Exception as e:
            logger.error(f"Error indexing in Neo4j: {e}")
            return False


def main():
    """Main function to run the class hierarchy analyzer."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Analyze C++ class hierarchies and virtual methods")
    parser.add_argument("--file", "-f", required=True, help="C++ file to analyze")
    parser.add_argument("--output", "-o", help="Output JSON file for results")
    parser.add_argument("--neo4j", action="store_true", help="Index results in Neo4j")
    parser.add_argument("--project", default="class_hierarchy_test", help="Neo4j project name")
    
    args = parser.parse_args()
    
    # Validate file path
    if not os.path.exists(args.file):
        logger.error(f"File not found: {args.file}")
        return 1
        
    # Run the analyzer
    analyzer = ClassHierarchyAnalyzer(args.file)
    analyzer.analyze()
    analyzer.print_results()
    
    # Export results if requested
    if args.output:
        analyzer.export_results(args.output)
    
    # Index in Neo4j if requested
    if args.neo4j:
        analyzer.index_in_neo4j(project_name=args.project)
    
    return 0


if __name__ == "__main__":
    sys.exit(main()) 