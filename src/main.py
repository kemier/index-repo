import os
from typing import List, Dict
from dotenv import load_dotenv
print("Importing CodeAnalyzer...")
from .code_analyzer import CodeAnalyzer
print("Importing DgraphManager...")
from .dgraph_client import DgraphManager
print("Importing QueryGenerator...")
from .query_generator import QueryGenerator
print("Importing CodeExtractor...")
from .code_extractor import CodeExtractor
print("Imports in main.py successful.")

# Load environment variables from .env file
print("Loading .env file...")
if load_dotenv():
    print(".env file loaded (if present).")
else:
    print(".env file not found or not loaded.")

def deduplicate_function_results(results: Dict) -> Dict:
    """
    对查询结果中的函数列表进行去重
    
    Args:
        results: 原始查询结果
        
    Returns:
        去重后的结果
    """
    deduped_results = {}
    
    for key, func_list in results.items():
        if not isinstance(func_list, list):
            deduped_results[key] = func_list
            continue
        
        # 用于存储已处理过的函数签名
        seen_functions = set()
        # 去重后的函数列表
        unique_functions = []
        
        for func in func_list:
            if not isinstance(func, dict) or 'name' not in func or 'file_path' not in func:
                unique_functions.append(func)
                continue
                
            # 创建唯一签名：函数名_文件路径
            signature = f"{func['name']}_{func['file_path']}"
            
            if signature not in seen_functions:
                seen_functions.add(signature)
                unique_functions.append(func)
        
        deduped_results[key] = unique_functions
    
    return deduped_results

class CodeAnalysisSystem:
    def __init__(self):
        print("CodeAnalysisSystem.__init__ started.")
        deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
        if not deepseek_api_key:
            print("DEEPSEEK_API_KEY not found in environment variables!")
            raise ValueError("DEEPSEEK_API_KEY not set")

        print("Initializing CodeAnalyzer...")
        self.analyzer = CodeAnalyzer()
        print("CodeAnalyzer initialized.")
        
        print("Initializing DgraphManager...")
        self.dgraph = DgraphManager()
        print("DgraphManager initialized.")
        
        print("Initializing QueryGenerator...")
        self.query_generator = QueryGenerator(deepseek_api_key=deepseek_api_key)
        print("QueryGenerator initialized.")
        print("CodeAnalysisSystem.__init__ finished.")
        
        # 保存项目根路径，用于函数体提取
        self.project_root = os.getcwd()

    def analyze_codebase(self, source_files: List[str], compile_args: List[str] = None) -> None:
        """Analyze a codebase and store results in Dgraph."""
        for file_path in source_files:
            self.analyzer.parse_file(file_path, compile_args)
        
        analysis_data = {
            "functions": list(self.analyzer.functions.values()),
            "branches": self.analyzer.branches,
            "callbacks": self.analyzer.callbacks
        }
        uids = self.dgraph.store_analysis_results(analysis_data)
        print(f"Analysis results stored. UIDs: {uids}")

    def query_by_natural_language(self, business_need: str, result_key: str, extract_function_bodies: bool = False, deduplicate: bool = True) -> Dict:
        """Convert natural language business need to Dgraph query and execute."""
        print(f"Generating DQL query for: {business_need} (expected key: {result_key})")
        dgraph_query = self.query_generator.generate_dql_query(business_need, result_key)
        print(f"Generated DQL query (raw from generator):\n{dgraph_query}")
        print(f"Generated DQL query (repr for Dgraph):\n{repr(dgraph_query)}")
        
        # 执行查询
        result = self.dgraph.query_data(dgraph_query)
        
        # 对结果进行去重
        if deduplicate:
            result = deduplicate_function_results(result)
        
        # 如果需要，提取函数体
        if extract_function_bodies:
            print(f"Extracting function bodies for query results...")
            result = CodeExtractor.extract_functions_from_query_result(result, self.project_root)
            print(f"Function bodies extracted.")
        
        return result
    
    def query_functions_with_bodies(self, query_name: str, deduplicate: bool = True) -> Dict:
        """使用预定义查询并提取函数体"""
        if query_name not in self.query_generator.get_common_queries():
            raise ValueError(f"Unknown query name: {query_name}")
        
        query = self.query_generator.get_common_queries()[query_name]
        print(f"Executing predefined query: {query_name}")
        result = self.dgraph.query_data(query)
        
        # 对结果进行去重
        if deduplicate:
            result = deduplicate_function_results(result)
        
        print(f"Extracting function bodies...")
        result = CodeExtractor.extract_functions_from_query_result(result, self.project_root)
        print(f"Function bodies extracted.")
        
        return result

    def get_common_dql_queries(self) -> Dict[str, str]:
        """Get common query templates."""
        return self.query_generator.get_common_queries()

def main():
    # Example usage
    system = CodeAnalysisSystem()
    
    # Analyze codebase
    source_files = [
        "path/to/your/source/file1.cpp",
        "path/to/your/source/file2.cpp"
    ]
    compile_args = ["-std=c++17", "-I/path/to/include"]
    system.analyze_codebase(source_files, compile_args)
    
    # Query using natural language
    business_need = "找到计算用户订单总价的函数及其调用关系，包括逻辑分支和回调函数"
    results = system.query_by_natural_language(business_need, "expected_key")
    print(results)

if __name__ == "__main__":
    main() 