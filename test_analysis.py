import os
import unittest # Import unittest
import traceback
import json # For pretty printing
from src.main import CodeAnalysisSystem

class TestCodeAnalysis(unittest.TestCase): # Create a class that inherits from unittest.TestCase
    def setUp(self):
        """Set up for each test method."""
        print("\nSetting up TestCodeAnalysis...")
        self.system = CodeAnalysisSystem()
        
        # Analyze test codebase (common for all tests that need analyzed data)
        source_files = [
            "test_repo/order_system.h",
            "test_repo/order_system.cpp",
            "test_repo/main.cpp"
        ]
        compile_args = [
            "-std=c++17",
            "-I", os.path.abspath("test_repo")
        ]
        print("开始分析代码库 (setUp)...")
        self.system.analyze_codebase(source_files, compile_args)
        print("代码库分析完成 (setUp).")

    def test_01_hardcoded_minimal_query(self):
        """Test a hardcoded minimal Dgraph query."""
        print("\nTesting hardcoded minimal Dgraph query...")
        try:
            minimal_query = "{ q(func: uid(0x1)) { uid } }" # Compacted slightly
            print(f"Minimal DQL: {repr(minimal_query)}")
            minimal_results = self.system.dgraph.query_data(minimal_query)
            print(f"Minimal query results: {minimal_results}")
            self.assertIn('q', minimal_results, "Minimal query should return 'q' key")
            self.assertTrue(len(minimal_results.get('q', [])) > 0, "Minimal query for uid(0x1) should find a node.")
            self.assertEqual(minimal_results['q'][0]['uid'], '0x1', "UID should be 0x1")
        except Exception as e:
            print(f"Error during minimal query: {e}")
            traceback.print_exc()
            self.fail(f"Minimal Dgraph query failed: {e}")

    def test_02_dump_project_function_data(self):
        """Dump and verify project-specific Function data from Dgraph."""
        print("\nDumping project-specific Function data from Dgraph...")
        try:
            # Filter by file_path containing 'test_repo'
            dump_query = """
            {
              all_functions(func: type(Function)) @filter(regexp(file_path, /.*test_repo.*/)) {
                uid
                name
                file_path
                line_number
                is_callback
                callback_type
                calls { uid name }
                called_by { uid name }
                in_branch {
                    uid
                    branch_node_type
                    condition
                    contains { uid name }
                }
              }
            }
            """
            print(f"Dump DQL: {dump_query}")
            dump_results = self.system.dgraph.query_data(dump_query)
            print("Project-specific Function data dump:")
            print(json.dumps(dump_results, indent=2, ensure_ascii=False))
            
            # Basic assertion: Check if any functions from test_repo were found
            project_functions = dump_results.get('all_functions', [])
            self.assertTrue(len(project_functions) > 0, 
                            "Data dump should find at least one function from 'test_repo'")
            
            # Example of a more specific check (optional, can be expanded)
            # found_main = any(func.get('name') == 'main' and 'test_repo/main.cpp' in func.get('file_path', '') for func in project_functions)
            # self.assertTrue(found_main, "Function 'main' from 'test_repo/main.cpp' should be in the dump.")

        except Exception as e:
            print(f"Error during data dump query: {e}")
            traceback.print_exc()
            self.fail(f"Data dump query failed: {e}")

    def test_03_natural_language_queries(self):
        """Test natural language queries."""
        test_queries = [
            ("Find functions related to order, price, or total", "FunctionsRelatedToOrderPriceTotal"),
            ("查找所有回调函数的定义和注册位置", "CallbackFunctions"), # Find all callback function definitions and registration locations
            ("查找订单创建和更新相关的函数调用链", "CallChainQuery"), # Find function call chains related to order creation and update
            ("展示所有函数之间的调用关系，包括谁调用谁", "FunctionCallRelationships") # Show call relationships between all functions, including who calls whom
        ]
        
        print("\n执行自然语言查询测试...")
        for nl_query, result_key in test_queries:
            print(f"\nNL Query: {nl_query}")
            try:
                results = self.system.query_by_natural_language(nl_query, result_key, extract_function_bodies=True)
                print(f"Query results for '{result_key}':")
                print(json.dumps(results, indent=2, ensure_ascii=False))
                # We expect a key in the results, and its value should be a list (possibly empty)
                self.assertIn(result_key, results, f"Results for '{nl_query}' should contain key '{result_key}'")
                self.assertIsInstance(results.get(result_key), list, f"Results for '{result_key}' should be a list.")
                # We don't assert non-empty here yet, as data population is the next focus
            except Exception as e:
                print(f"Error during NL query '{nl_query}': {e}")
                traceback.print_exc()
                self.fail(f"NL Query '{nl_query}' failed: {e}")

if __name__ == '__main__':
    unittest.main() 