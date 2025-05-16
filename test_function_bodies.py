import os
import json
from src.main import CodeAnalysisSystem

def main():
    # 初始化系统
    print("Initializing CodeAnalysisSystem...")
    system = CodeAnalysisSystem()
    
    # 分析代码库（如果已经分析过，可以注释掉这部分）
    source_files = [
        "test_repo/order_system.h",
        "test_repo/order_system.cpp",
        "test_repo/main.cpp"
    ]
    compile_args = [
        "-std=c++17",
        "-I", os.path.abspath("test_repo")
    ]
    print("Analyzing codebase...")
    system.analyze_codebase(source_files, compile_args)
    print("Codebase analysis completed.")
    
    # 使用预定义查询获取OrderSystem函数及其函数体
    print("\n获取OrderSystem类的函数及其函数体...")
    order_functions = system.query_functions_with_bodies("order_system_relationships")
    
    # 打印函数名和函数体
    print("\n==== OrderSystem类函数及其函数体 ====")
    for func in order_functions.get("order_functions", [])[:5]:  # 只打印前5个函数以避免输出过多
        print(f"\n函数名: {func['name']}")
        print(f"文件路径: {func['file_path']}")
        print(f"行号: {func['line_number']}")
        print(f"函数体:")
        print("----------------------------------")
        print(func.get('function_body', 'No function body found'))
        print("----------------------------------")
        
        # 打印此函数调用的函数列表
        if 'calls_functions' in func and func['calls_functions']:
            print(f"\n函数 {func['name']} 调用的函数:")
            for called_func in func['calls_functions'][:3]:  # 只打印前3个调用的函数
                print(f"  - {called_func['name']} (在 {called_func['file_path']}:{called_func['line_number']})")
        
        # 打印调用此函数的函数列表
        if 'called_by_functions' in func and func['called_by_functions']:
            print(f"\n调用函数 {func['name']} 的函数:")
            for caller_func in func['called_by_functions'][:3]:  # 只打印前3个调用者
                print(f"  - {caller_func['name']} (在 {caller_func['file_path']}:{caller_func['line_number']})")
    
    # 使用自然语言查询获取与计算价格相关的函数
    print("\n\n使用自然语言查询获取与价格计算相关的函数...")
    price_functions = system.query_by_natural_language(
        "找到所有与价格计算相关的函数",
        "PriceFunctions",
        extract_function_bodies=True
    )
    
    # 打印查询结果
    print("\n==== 价格计算相关函数 ====")
    for func in price_functions.get("PriceFunctions", []):
        print(f"\n函数名: {func['name']}")
        print(f"文件路径: {func['file_path']}")
        print(f"行号: {func['line_number']}")
        print(f"函数体:")
        print("----------------------------------")
        print(func.get('function_body', 'No function body found'))
        print("----------------------------------")
    
if __name__ == "__main__":
    main() 