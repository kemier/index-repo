import argparse
import os
import json
from src.main import CodeAnalysisSystem

def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='使用自然语言查询代码分析系统')
    parser.add_argument('--query', '-q', type=str, help='自然语言查询字符串')
    parser.add_argument('--predefined', '-p', type=str, help='使用预定义的查询（如"function_call_relationships", "order_system_relationships"等）')
    parser.add_argument('--result-key', '-k', type=str, default='QueryResults', help='查询结果在JSON中的键名')
    parser.add_argument('--no-bodies', action='store_true', help='不提取函数体（更快）')
    parser.add_argument('--no-deduplicate', action='store_true', help='不去除重复函数')
    parser.add_argument('--source-files', '-s', nargs='+', help='源文件列表（如果需要先分析代码库）')
    parser.add_argument('--compile-args', '-c', nargs='+', help='编译参数（如果需要先分析代码库）')
    parser.add_argument('--all-functions', '-a', action='store_true', help='显示所有函数')
    parser.add_argument('--output', '-o', type=str, help='将结果保存到指定文件')
    
    args = parser.parse_args()
    
    # 初始化系统
    print("初始化代码分析系统...")
    system = CodeAnalysisSystem()
    
    # 如果提供了源文件，则先分析代码库
    if args.source_files:
        print(f"正在分析源文件: {', '.join(args.source_files)}")
        system.analyze_codebase(args.source_files, args.compile_args)
        print("代码库分析完成。")
    
    # 确定是否需要提取函数体
    extract_bodies = not args.no_bodies
    deduplicate = not args.no_deduplicate
    
    # 执行查询
    results = None
    
    if args.all_functions:
        # 显示所有函数
        if args.predefined:
            print(f"警告: --all-functions 会覆盖 --predefined 参数")
        
        print("获取所有函数...")
        results = system.query_functions_with_bodies("find_all_functions", deduplicate)
    elif args.predefined:
        # 使用预定义查询
        print(f"使用预定义查询: {args.predefined}")
        try:
            results = system.query_functions_with_bodies(args.predefined, deduplicate)
        except ValueError as e:
            print(f"错误: {str(e)}")
            available_queries = system.get_common_dql_queries().keys()
            print(f"可用的预定义查询: {', '.join(available_queries)}")
            return
    elif args.query:
        # 使用自然语言查询
        print(f"执行自然语言查询: {args.query}")
        results = system.query_by_natural_language(
            args.query, 
            args.result_key,
            extract_function_bodies=extract_bodies,
            deduplicate=deduplicate
        )
    else:
        print("错误: 必须提供 --query, --predefined 或 --all-functions 参数")
        return
    
    # 显示结果
    if not results:
        print("查询没有返回任何结果。")
        return
    
    # 将结果保存到文件
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"结果已保存到文件: {args.output}")
    
    # 打印结果
    for key in results:
        if isinstance(results[key], list):
            functions = results[key]
            print(f"\n找到 {len(functions)} 个函数:")
            
            for i, func in enumerate(functions, 1):
                print(f"\n{i}. 函数名: {func.get('name', 'Unknown')}")
                print(f"   文件路径: {func.get('file_path', 'Unknown')}")
                print(f"   行号: {func.get('line_number', 'Unknown')}")
                
                # 打印函数调用关系
                if 'calls' in func and func['calls']:
                    print(f"   调用其他函数:")
                    for called in func['calls'][:3]:  # 只显示前3个
                        print(f"     - {called.get('name', 'Unknown')} (在 {called.get('file_path', 'Unknown')}:{called.get('line_number', 'Unknown')})")
                    if len(func['calls']) > 3:
                        print(f"     ... 以及其他 {len(func['calls']) - 3} 个函数")
                    
                if 'called_by' in func and func['called_by']:
                    print(f"   被其他函数调用:")
                    for caller in func['called_by'][:3]:  # 只显示前3个
                        print(f"     - {caller.get('name', 'Unknown')} (在 {caller.get('file_path', 'Unknown')}:{caller.get('line_number', 'Unknown')})")
                    if len(func['called_by']) > 3:
                        print(f"     ... 以及其他 {len(func['called_by']) - 3} 个函数")
                
                # 打印函数调用关系（使用calls_functions和called_by_functions字段）
                if 'calls_functions' in func and func['calls_functions']:
                    print(f"   调用其他函数:")
                    for called in func['calls_functions'][:3]:  # 只显示前3个
                        print(f"     - {called.get('name', 'Unknown')} (在 {called.get('file_path', 'Unknown')}:{called.get('line_number', 'Unknown')})")
                    if len(func['calls_functions']) > 3:
                        print(f"     ... 以及其他 {len(func['calls_functions']) - 3} 个函数")
                    
                if 'called_by_functions' in func and func['called_by_functions']:
                    print(f"   被其他函数调用:")
                    for caller in func['called_by_functions'][:3]:  # 只显示前3个
                        print(f"     - {caller.get('name', 'Unknown')} (在 {caller.get('file_path', 'Unknown')}:{caller.get('line_number', 'Unknown')})")
                    if len(func['called_by_functions']) > 3:
                        print(f"     ... 以及其他 {len(func['called_by_functions']) - 3} 个函数")
                
                # 打印函数体
                if 'function_body' in func:
                    print(f"   函数体:")
                    print("   " + "="*50)
                    body_lines = func['function_body'].split('\n')
                    for line in body_lines:
                        print(f"   {line}")
                    print("   " + "="*50)
                
                # 如果有很多函数，在每10个后暂停
                if i % 10 == 0 and i < len(functions):
                    input(f"\n已显示 {i}/{len(functions)} 个函数。按回车继续...")
        else:
            print(f"\n{key}:")
            print(json.dumps(results[key], ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main() 