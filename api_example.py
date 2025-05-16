import os
import json
import argparse
from src.main import CodeAnalysisSystem

class CodeAnalysisAPI:
    """
    API wrapper for the code analysis system, making it easy to integrate with other tools.
    """
    
    def __init__(self):
        """Initialize the code analysis system."""
        self.system = CodeAnalysisSystem()
        self.project_root = os.getcwd()
        self.is_analyzed = False
    
    def analyze_project(self, source_files, compile_args=None):
        """
        Analyze a C/C++ project and store the results in the database.
        
        Args:
            source_files: List of source files to analyze
            compile_args: Optional compilation arguments
        
        Returns:
            Success status
        """
        if not compile_args:
            compile_args = ["-std=c++17"]
            
        try:
            self.system.analyze_codebase(source_files, compile_args)
            self.is_analyzed = True
            return {"status": "success", "message": f"Successfully analyzed {len(source_files)} files"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def query_functions(self, query_text, extract_bodies=True):
        """
        Query functions using natural language.
        
        Args:
            query_text: Natural language query
            extract_bodies: Whether to extract function bodies
        
        Returns:
            Query results
        """
        if not self.is_analyzed:
            return {"status": "error", "message": "No project analyzed yet. Call analyze_project first."}
        
        try:
            result_key = "QueryResults"
            results = self.system.query_by_natural_language(
                query_text, 
                result_key, 
                extract_function_bodies=extract_bodies
            )
            
            # Convert results to a more API-friendly format
            return {
                "status": "success",
                "query": query_text,
                "results": results.get(result_key, []),
                "count": len(results.get(result_key, []))
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def get_function_details(self, function_name, file_path=None):
        """
        Get detailed information about a specific function.
        
        Args:
            function_name: Name of the function
            file_path: Optional file path to narrow search
        
        Returns:
            Function details
        """
        if not self.is_analyzed:
            return {"status": "error", "message": "No project analyzed yet. Call analyze_project first."}
        
        query = f"Find details about the function named {function_name}"
        if file_path:
            query += f" in file {file_path}"
        
        try:
            results = self.system.query_by_natural_language(
                query,
                "FunctionDetails",
                extract_function_bodies=True
            )
            
            functions = results.get("FunctionDetails", [])
            if not functions:
                return {
                    "status": "warning",
                    "message": f"No function named '{function_name}' found",
                    "results": []
                }
            
            return {
                "status": "success",
                "count": len(functions),
                "results": functions
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def get_call_graph(self, function_name, depth=2):
        """
        Get the call graph for a specific function.
        
        Args:
            function_name: Name of the function
            depth: How many levels of calls to include
        
        Returns:
            Call graph
        """
        if not self.is_analyzed:
            return {"status": "error", "message": "No project analyzed yet. Call analyze_project first."}
        
        query = f"Find the call graph for function {function_name} with depth {depth}"
        
        try:
            results = self.system.query_by_natural_language(
                query,
                "CallGraph",
                extract_function_bodies=True
            )
            
            return {
                "status": "success",
                "function": function_name,
                "depth": depth,
                "call_graph": results.get("CallGraph", [])
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def get_available_queries(self):
        """
        Get a list of predefined queries available in the system.
        
        Returns:
            List of available queries
        """
        return {
            "status": "success",
            "available_queries": list(self.system.get_common_dql_queries().keys())
        }
    
    def execute_predefined_query(self, query_name):
        """
        Execute a predefined query by name.
        
        Args:
            query_name: Name of the predefined query
        
        Returns:
            Query results
        """
        if not self.is_analyzed:
            return {"status": "error", "message": "No project analyzed yet. Call analyze_project first."}
        
        try:
            results = self.system.query_functions_with_bodies(query_name)
            
            # The result key depends on the query, so we need to get it from the results
            if not results:
                return {"status": "warning", "message": f"No results for query '{query_name}'"}
            
            result_key = list(results.keys())[0]
            
            return {
                "status": "success",
                "query_name": query_name,
                "result_key": result_key,
                "results": results.get(result_key, []),
                "count": len(results.get(result_key, []))
            }
        except ValueError as e:
            return {"status": "error", "message": str(e)}
        except Exception as e:
            return {"status": "error", "message": f"Error executing query: {str(e)}"}

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Code Analysis API Example")
    parser.add_argument('--analyze', action='store_true', help='Analyze the example project')
    parser.add_argument('--query', type=str, help='Execute a natural language query')
    parser.add_argument('--function', type=str, help='Get details about a specific function')
    parser.add_argument('--call-graph', type=str, help='Get call graph for a function')
    parser.add_argument('--list-queries', action='store_true', help='List available predefined queries')
    parser.add_argument('--predefined-query', type=str, help='Execute a predefined query by name')
    parser.add_argument('--output', type=str, choices=['pretty', 'json'], default='pretty', 
                      help='Output format (pretty or json)')
    return parser.parse_args()

def main():
    """Main function for the API example"""
    args = parse_args()
    api = CodeAnalysisAPI()
    
    # Define the output function based on the format chosen
    if args.output == 'json':
        def output(data):
            print(json.dumps(data, indent=2))
    else:
        def output(data):
            if data.get('status') == 'error':
                print(f"ERROR: {data.get('message')}")
                return
                
            print(f"Status: {data.get('status')}")
            
            if 'message' in data:
                print(f"Message: {data.get('message')}")
                
            if 'count' in data:
                print(f"Result count: {data.get('count')}")
                
            if 'results' in data and isinstance(data['results'], list):
                print("\nResults:")
                for idx, item in enumerate(data['results'], 1):
                    print(f"\n--- Result {idx} ---")
                    for key, value in item.items():
                        if key == 'function_body' and value:
                            print(f"Function body: (first 5 lines)")
                            lines = value.split('\n')
                            for line in lines[:5]:
                                print(f"  {line}")
                            if len(lines) > 5:
                                print(f"  ... ({len(lines)} lines total)")
                        elif key not in ['calls_functions', 'called_by_functions']:
                            print(f"{key}: {value}")
    
    # Process the arguments
    if args.analyze:
        # Analyze the example project
        source_files = [
            "test_repo/order_system.h",
            "test_repo/order_system.cpp",
            "test_repo/main.cpp"
        ]
        compile_args = [
            "-std=c++17",
            "-I", os.path.abspath("test_repo")
        ]
        result = api.analyze_project(source_files, compile_args)
        output(result)
    
    elif args.query:
        # Execute a natural language query
        result = api.query_functions(args.query)
        output(result)
    
    elif args.function:
        # Get details about a specific function
        result = api.get_function_details(args.function)
        output(result)
    
    elif args.call_graph:
        # Get call graph for a function
        result = api.get_call_graph(args.call_graph)
        output(result)
    
    elif args.list_queries:
        # List available predefined queries
        result = api.get_available_queries()
        output(result)
    
    elif args.predefined_query:
        # Execute a predefined query
        result = api.execute_predefined_query(args.predefined_query)
        output(result)
    
    else:
        # No arguments provided, show help
        print("Use one of the following arguments:")
        print("  --analyze               Analyze the example project")
        print("  --query TEXT            Execute a natural language query")
        print("  --function NAME         Get details about a specific function")
        print("  --call-graph NAME       Get call graph for a function")
        print("  --list-queries          List available predefined queries")
        print("  --predefined-query NAME Execute a predefined query by name")
        print("  --output FORMAT         Output format (pretty or json)")
        print("\nExample: python api_example.py --analyze")
        print("Example: python api_example.py --query 'Find functions related to price calculation'")
        print("Example: python api_example.py --function calculate_total_price --output json")

if __name__ == "__main__":
    main() 