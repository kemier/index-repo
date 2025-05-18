"""
Natural language query for the code index.

This command allows querying the code index using natural language.
"""
import argparse
import re
from typing import List, Dict, Any, Optional

from src.services.search_service import SearchService
from src.services.neo4j_service import Neo4jService
from src.config.settings import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD


def detect_language(query: str) -> str:
    """
    Detect the language of the query.
    
    Args:
        query: The natural language query
        
    Returns:
        Language code: 'zh' for Chinese, 'en' for English or others
    """
    # Check for Chinese characters
    if re.search(r'[\u4e00-\u9fff]', query):
        return 'zh'
    return 'en'


def detect_metaprogramming_features(query: str) -> Dict[str, Any]:
    """
    Detect template metaprogramming features from natural language query.
    
    Args:
        query: The natural language query
        
    Returns:
        Dictionary of detected metaprogramming features
    """
    features = {}
    
    # Map of feature keywords to properties
    metaprogramming_terms = {
        # Variadic templates
        "variadic template": "has_variadic_templates",
        "parameter pack": "has_variadic_templates",
        "template parameter pack": "has_variadic_templates",
        "variadic": "has_variadic_templates",
        
        # SFINAE
        "sfinae": "has_sfinae", 
        "substitution failure": "has_sfinae",
        "enable_if": "sfinae_technique",
        "enable if": "sfinae_technique",  # Match with space
        "void_t": "sfinae_technique", 
        "decltype": "sfinae_technique",
        "detection idiom": "sfinae_technique",
        "tag dispatch": "sfinae_technique",
        
        # Template metafunctions
        "type trait": "is_metafunction",
        "metafunction": "is_metafunction",
        "trait": "is_metafunction",
        "meta function": "is_metafunction",
        "value trait": "metafunction_kind",
        "type trait": "metafunction_kind",
        "transform trait": "metafunction_kind",
        
        # C++20 Concepts
        "concept": "is_concept",
        "requires": "is_concept",
        "constraint": "is_concept",
        
        # Template templates
        "template template": "has_template_template_params",
        
        # Specialization
        "partial specialization": "partial_specialization",
        "template specialization": "is_template"
    }
    
    # Check for matches
    query_lower = query.lower()
    for term, feature in metaprogramming_terms.items():
        if term in query_lower:
            # Special case for kinds
            if feature == "metafunction_kind":
                if "value trait" in query_lower:
                    features["is_metafunction"] = True
                    features["metafunction_kind"] = "value_trait"
                elif "type trait" in query_lower:
                    features["is_metafunction"] = True
                    features["metafunction_kind"] = "type_trait"
                elif "transform" in query_lower:
                    features["is_metafunction"] = True
                    features["metafunction_kind"] = "transform"
            # Special case for SFINAE techniques
            elif feature == "sfinae_technique":
                features["has_sfinae"] = True
                if term == "enable if":
                    features["sfinae_technique"] = "enable_if"
                else:
                    features["sfinae_technique"] = term
            # Standard boolean properties
            else:
                features[feature] = True
    
    return features


def main():
    """Main function for natural language query."""
    parser = argparse.ArgumentParser(
        description="Query the code index using natural language"
    )
    parser.add_argument("query", help="Natural language query")
    parser.add_argument("--project", "-p", default="default", help="Project name")
    parser.add_argument("--limit", "-l", type=int, default=10, help="Maximum number of results")
    parser.add_argument("--lang", choices=['auto', 'en', 'zh'], default='auto', 
                       help="Query language ('auto', 'en' for English, 'zh' for Chinese)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed match information")
    parser.add_argument("--metaprogramming", "-m", action="store_true", 
                       help="Focus search on template metaprogramming features")
    
    args = parser.parse_args()
    
    # Detect language if set to auto
    language = args.lang
    if language == 'auto':
        language = detect_language(args.query)
        if language == 'zh':
            print("Detected Chinese query")
        else:
            print("Detected English query")
    
    # Create Neo4j service first
    neo4j_service = Neo4jService(
        uri=NEO4J_URI,
        username=NEO4J_USER,
        password=NEO4J_PASSWORD
    )
    
    # Create search service with Neo4j service
    search_service = SearchService(neo4j_service=neo4j_service)
    
    try:
        # Check for metaprogramming features in the query
        metaprogramming_features = detect_metaprogramming_features(args.query)
        
        # Process the query with the appropriate language processor
        processed_query = search_service._process_query(args.query, language)
        
        if args.verbose:
            print(f"Processed query tokens: {', '.join(processed_query)}")
            if metaprogramming_features:
                print(f"Detected metaprogramming features: {metaprogramming_features}")
        
        # Decide on search strategy based on detected features
        if args.metaprogramming or metaprogramming_features:
            # Use specialized metaprogramming search
            results = search_service.find_by_metaprogramming_features(
                project_name=args.project,
                **metaprogramming_features
            )
            
            # If no results or few results, fallback to standard search
            if len(results) < 3:
                # Add standard search results and merge
                std_results = search_service.search_by_description(
                    description=args.query,
                    project_name=args.project,
                    limit=args.limit,
                    lang=language
                )
                
                # Merge results, prioritizing metaprogramming matches
                existing_names = {r["name"] for r in results}
                for result in std_results:
                    if result["name"] not in existing_names:
                        results.append(result)
                        if len(results) >= args.limit:
                            break
        else:
            # Use standard semantic search
            results = search_service.search_by_description(
                description=args.query,
                project_name=args.project,
                limit=args.limit,
                lang=language
            )
        
        # Display results
        if not results:
            print(f"No functions found matching '{args.query}'")
        else:
            print(f"Found {len(results)} matching functions:")
            for i, result in enumerate(results, 1):
                print(f"\n{i}. {result['name']}")
                if 'file_path' in result and result['file_path']:
                    print(f"   File: {result['file_path']}")
                if 'line_number' in result and result['line_number']:
                    print(f"   Line: {result['line_number']}")
                    
                # Show template metaprogramming details
                if result.get('is_template', False):
                    print(f"   Template: Yes")
                    if 'template_params' in result:
                        print(f"   Template Parameters: {', '.join(result['template_params'])}")
                
                if result.get('has_variadic_templates', False):
                    print(f"   Variadic Template: Yes")
                    if result.get('variadic_template_param'):
                        print(f"   Parameter Pack: {result['variadic_template_param']}")
                
                if result.get('is_metafunction', False):
                    print(f"   Metafunction: Yes")
                    if result.get('metafunction_kind'):
                        print(f"   Metafunction Kind: {result['metafunction_kind']}")
                
                if result.get('has_sfinae', False):
                    print(f"   SFINAE: Yes")
                    if 'sfinae_techniques' in result:
                        print(f"   SFINAE Techniques: {', '.join(result['sfinae_techniques'])}")
                
                if result.get('is_concept', False):
                    print(f"   Concept: Yes")
                    if 'concept_requirements' in result:
                        print(f"   Concept Requirements: {', '.join(result['concept_requirements'])}")
                    
                # Show additional details if verbose
                if args.verbose:
                    if 'signature' in result and result['signature']:
                        print(f"   Signature: {result['signature']}")
                    if 'is_virtual' in result and result['is_virtual']:
                        print(f"   Virtual: Yes")
                    if 'class_name' in result and result['class_name']:
                        print(f"   Class: {result['class_name']}")
                    if 'namespace' in result and result['namespace']:
                        print(f"   Namespace: {result['namespace']}")
                        
                    # Show relevance details
                    if 'relevance' in result:
                        print(f"   Relevance score: {result['relevance']:.2f}")
                        
                    # Show matched tokens
                    if 'matched_tokens' in result:
                        print(f"   Matched terms: {', '.join(result['matched_tokens'])}")
    except Exception as e:
        print(f"Error executing query: {e}")


if __name__ == "__main__":
    main() 