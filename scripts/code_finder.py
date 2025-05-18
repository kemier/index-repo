#!/usr/bin/env python
"""
代码查找工具 - 在实现新功能前检查代码库中是否已有类似实现
"""
import os
import re
import sys
import argparse
from typing import List, Dict, Tuple, Any, Set, Optional
try:
    from py2neo import Graph, Node, Relationship
    HAS_NEO4J = True
except ImportError:
    HAS_NEO4J = False
    # 定义一个替代类型用于类型注解
    class Graph:
        pass
    class Node:
        pass
    class Relationship:
        pass

def extract_keywords(description: str) -> List[str]:
    """从功能描述中提取关键词"""
    # 先按空格分割
    words = description.lower().split()
    
    # 删除常见的停用词
    stop_words = {"a", "an", "the", "and", "or", "but", "if", "of", "for", "in", "to", "with"}
    keywords = [word for word in words if word not in stop_words and len(word) > 2]
    
    # 对于中文描述，尝试提取2-3个字的词汇
    chinese_pattern = re.compile(r'[\u4e00-\u9fff]{2,3}')
    chinese_keywords = chinese_pattern.findall(description)
    
    # 合并结果
    all_keywords = list(set(keywords + chinese_keywords))
    
    # 如果关键词太少，使用原始词
    if len(all_keywords) < 2:
        return words
        
    return all_keywords

def search_code_files(directory: str, extensions: List[str], keywords: List[str], 
                     max_results: int = 10) -> List[Dict[str, Any]]:
    """
    在代码文件中搜索关键词
    
    Args:
        directory: 要搜索的目录
        extensions: 文件扩展名列表 (.c, .h, .py等)
        keywords: 要搜索的关键词
        max_results: 最大结果数量
        
    Returns:
        匹配的函数列表
    """
    results = []
    
    # 编译正则表达式来识别函数定义
    func_patterns = [
        # C/C++风格函数
        re.compile(r'((?:[a-zA-Z0-9_*]+\s+)+)([a-zA-Z0-9_]+)\s*\([^)]*\)\s*(?:const)?\s*(?:noexcept)?\s*{'),
        # Python风格函数
        re.compile(r'def\s+([a-zA-Z0-9_]+)\s*\([^)]*\)(?:\s*->.*?)?\s*:'),
        # JavaScript/TypeScript风格函数
        re.compile(r'(?:function|const|let|var)\s+([a-zA-Z0-9_]+)\s*(?:=\s*(?:async\s*)?\([^)]*\)|=>\s*{|\([^)]*\)\s*{)')
    ]
    
    # 遍历目录
    for root, _, files in os.walk(directory):
        for file in files:
            # 检查文件扩展名
            if not any(file.endswith(ext) for ext in extensions):
                continue
                
            file_path = os.path.join(root, file)
            
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                # 检查文件内容是否包含任何关键词
                has_keywords = any(keyword.lower() in content.lower() for keyword in keywords)
                if not has_keywords:
                    continue
                
                # 提取文件中的所有函数
                functions = extract_functions(content, func_patterns, file_path)
                
                # 为每个函数计算相关性分数
                for func in functions:
                    relevance = calculate_relevance(func, keywords)
                    if relevance > 0:
                        func["relevance"] = relevance
                        results.append(func)
                        
            except Exception as e:
                print(f"错误处理文件 {file_path}: {e}", file=sys.stderr)
    
    # 按相关性排序并限制结果数量
    results.sort(key=lambda x: x.get("relevance", 0), reverse=True)
    return results[:max_results]

def extract_functions(content: str, patterns: List[re.Pattern], file_path: str) -> List[Dict[str, Any]]:
    """从文件内容中提取函数"""
    functions = []
    lines = content.split('\n')
    
    for pattern in patterns:
        for match in pattern.finditer(content):
            # 找到函数的起始位置
            start_pos = match.start()
            line_no = content[:start_pos].count('\n') + 1
            
            # 提取函数名
            if 'def ' in match.group(0):  # Python风格
                func_name = match.group(1)
            elif 'function ' in match.group(0) or '=' in match.group(0):  # JavaScript风格
                func_name = match.group(1)
            else:  # C/C++风格
                func_name = match.group(2)
            
            # 尝试提取函数体
            body = extract_function_body(content, start_pos, '{', '}')
            
            # 如果找不到C风格函数体，尝试Python风格缩进
            if not body:
                body = extract_python_function_body(lines, line_no)
            
            # 如果成功提取了函数体
            if body:
                function_info = {
                    "name": func_name,
                    "file_path": file_path,
                    "line_number": line_no,
                    "body": body
                }
                functions.append(function_info)
    
    return functions

def extract_function_body(content: str, start_pos: int, open_char: str, close_char: str) -> str:
    """提取使用括号界定的函数体（C/C++, JavaScript等）"""
    body_start = content.find(open_char, start_pos)
    
    if body_start == -1:
        return ""
        
    # 跟踪嵌套括号
    bracket_count = 1
    body_end = body_start + 1
    
    while bracket_count > 0 and body_end < len(content):
        if content[body_end] == open_char:
            bracket_count += 1
        elif content[body_end] == close_char:
            bracket_count -= 1
        body_end += 1
    
    if bracket_count == 0:
        # 包括函数签名
        signature_start = max(0, content.rfind('\n', 0, start_pos) + 1)
        return content[signature_start:body_end]
        
    return ""

def extract_python_function_body(lines: List[str], start_line: int) -> str:
    """提取基于缩进的函数体（Python）"""
    if start_line > len(lines):
        return ""
        
    # 获取函数定义行的缩进级别
    def_line = lines[start_line - 1]
    if not def_line.strip().startswith("def "):
        return ""
        
    indent_level = len(def_line) - len(def_line.lstrip())
    
    # 收集函数体
    body_lines = [def_line]
    
    for i in range(start_line, len(lines)):
        line = lines[i]
        
        # 空行或注释行
        if not line.strip() or line.strip().startswith("#"):
            body_lines.append(line)
            continue
            
        current_indent = len(line) - len(line.lstrip())
        
        # 如果缩进减少，那么我们已经离开了函数
        if current_indent <= indent_level:
            break
            
        body_lines.append(line)
        
    return "\n".join(body_lines)

def calculate_relevance(function: Dict[str, Any], keywords: List[str]) -> int:
    """计算函数与关键词的相关性分数"""
    score = 0
    
    # 在函数名中检查关键词
    for keyword in keywords:
        if keyword.lower() in function["name"].lower():
            score += 10
            
    # 在函数体中检查关键词
    if "body" in function:
        for keyword in keywords:
            matches = re.findall(keyword.lower(), function["body"].lower())
            score += len(matches) * 3
            
    return score

def find_function_calls(directory: str, extensions: List[str], function_name: str, 
                       max_results: int = 10) -> List[Dict[str, Any]]:
    """
    在代码文件中查找调用特定函数的地方
    
    Args:
        directory: 要搜索的目录
        extensions: 文件扩展名列表 (.c, .h, .py等)
        function_name: 要查找的函数名
        max_results: 最大结果数量
        
    Returns:
        匹配的函数列表
    """
    results = []
    
    # 编译正则表达式来识别函数定义
    func_patterns = [
        # C/C++风格函数
        re.compile(r'((?:[a-zA-Z0-9_*]+\s+)+)([a-zA-Z0-9_]+)\s*\([^)]*\)\s*(?:const)?\s*(?:noexcept)?\s*{'),
        # Python风格函数
        re.compile(r'def\s+([a-zA-Z0-9_]+)\s*\([^)]*\)(?:\s*->.*?)?\s*:'),
        # JavaScript/TypeScript风格函数
        re.compile(r'(?:function|const|let|var)\s+([a-zA-Z0-9_]+)\s*(?:=\s*(?:async\s*)?\([^)]*\)|=>\s*{|\([^)]*\)\s*{)')
    ]
    
    # 编译函数调用的正则表达式
    call_pattern = re.compile(r'[^a-zA-Z0-9_]' + re.escape(function_name) + r'\s*\(')
    
    # 遍历目录
    for root, _, files in os.walk(directory):
        for file in files:
            # 检查文件扩展名
            if not any(file.endswith(ext) for ext in extensions):
                continue
                
            file_path = os.path.join(root, file)
            
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                # 检查文件内容是否包含函数调用
                if not call_pattern.search(content):
                    continue
                
                # 提取文件中的所有函数
                functions = extract_functions(content, func_patterns, file_path)
                
                # 检查每个函数是否调用了目标函数
                for func in functions:
                    if "body" in func and call_pattern.search(func["body"]):
                        # 计算调用次数
                        calls = len(call_pattern.findall(func["body"]))
                        func["relevance"] = calls * 10  # 根据调用次数设置相关性分数
                        func["calls"] = calls
                        results.append(func)
                        
            except Exception as e:
                print(f"错误处理文件 {file_path}: {e}", file=sys.stderr)
    
    # 按相关性排序并限制结果数量
    results.sort(key=lambda x: x.get("relevance", 0), reverse=True)
    return results[:max_results]

def connect_to_graph_db(uri: str, user: str, password: str) -> 'Graph':
    """
    连接到图数据库
    
    Args:
        uri: 图数据库的URI
        user: 用户名
        password: 密码
        
    Returns:
        图数据库连接
    """
    if not HAS_NEO4J:
        raise ImportError("请先安装py2neo: pip install py2neo")
    
    return Graph(uri, auth=(user, password))

def get_function_call_chain_from_graph(graph: 'Graph', function_names: List[str], 
                                      max_depth: int = 5) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
    """
    从图数据库中获取函数调用链
    
    Args:
        graph: 图数据库连接
        function_names: 函数名列表
        max_depth: 最大调用深度
        
    Returns:
        调用链信息
    """
    result = {}
    
    for function_name in function_names:
        # 查询调用当前函数的函数
        callers_query = """
        MATCH (caller:Function)-[:CALLS]->(callee:Function {name: $function_name})
        RETURN caller.name as caller_name, caller.file_path as file_path, caller.line_number as line_number
        LIMIT 100
        """
        callers = graph.run(callers_query, function_name=function_name).data()
        
        # 查询当前函数调用的函数
        callees_query = """
        MATCH (caller:Function {name: $function_name})-[:CALLS]->(callee:Function)
        RETURN callee.name as callee_name, callee.file_path as file_path, callee.line_number as line_number
        LIMIT 100
        """
        callees = graph.run(callees_query, function_name=function_name).data()
        
        result[function_name] = {
            "callers": callers,
            "callees": callees
        }
    
    return result

def find_function_in_codebase(directory: str, extensions: List[str], function_name: str) -> Optional[Dict[str, Any]]:
    """
    在代码库中查找指定函数的定义
    
    Args:
        directory: 要搜索的目录
        extensions: 文件扩展名列表 (.c, .h, .py等)
        function_name: 函数名
        
    Returns:
        函数定义信息
    """
    func_patterns = [
        # C/C++风格函数
        re.compile(r'((?:[a-zA-Z0-9_*]+\s+)+)([a-zA-Z0-9_]+)\s*\([^)]*\)\s*(?:const)?\s*(?:noexcept)?\s*{'),
        # Python风格函数
        re.compile(r'def\s+([a-zA-Z0-9_]+)\s*\([^)]*\)(?:\s*->.*?)?\s*:'),
        # JavaScript/TypeScript风格函数
        re.compile(r'(?:function|const|let|var)\s+([a-zA-Z0-9_]+)\s*(?:=\s*(?:async\s*)?\([^)]*\)|=>\s*{|\([^)]*\)\s*{)')
    ]
    
    # 遍历目录
    for root, _, files in os.walk(directory):
        for file in files:
            # 检查文件扩展名
            if not any(file.endswith(ext) for ext in extensions):
                continue
                
            file_path = os.path.join(root, file)
            
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                # 提取文件中的所有函数
                functions = extract_functions(content, func_patterns, file_path)
                
                # 查找指定函数
                for func in functions:
                    if func["name"] == function_name:
                        return func
                        
            except Exception as e:
                print(f"错误处理文件 {file_path}: {e}", file=sys.stderr)
    
    return None

def find_function_call_chain(directory: str, extensions: List[str], function_names: List[str], 
                           max_depth: int = 3) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
    """
    在代码库中手动查找函数调用链(不使用图数据库)
    
    Args:
        directory: 要搜索的目录
        extensions: 文件扩展名列表 (.c, .h, .py等)
        function_names: 函数名列表
        max_depth: 最大调用深度
        
    Returns:
        调用链信息
    """
    result = {}
    
    # 存储已访问的函数，避免循环调用
    visited = set()
    
    def find_callers_and_callees(func_name: str, depth: int) -> Dict[str, List[Dict[str, Any]]]:
        if depth > max_depth or func_name in visited:
            return {"callers": [], "callees": []}
        
        visited.add(func_name)
        
        # 查找调用当前函数的函数
        callers = find_function_calls(directory, extensions, func_name)
        
        # 查找当前函数的定义
        func_def = find_function_in_codebase(directory, extensions, func_name)
        
        # 如果找到函数定义，查找它调用的函数
        callees = []
        if func_def and "body" in func_def:
            # 提取函数调用
            body = func_def["body"]
            # 简单的函数调用模式匹配
            call_pattern = re.compile(r'[^a-zA-Z0-9_]([a-zA-Z0-9_]+)\s*\(')
            for match in call_pattern.finditer(body):
                callee_name = match.group(1)
                # 跳过内置函数
                if callee_name in ["print", "len", "int", "str", "float", "list", "dict", "set", "tuple"]:
                    continue
                    
                callee_def = find_function_in_codebase(directory, extensions, callee_name)
                if callee_def:
                    callees.append(callee_def)
        
        result = {
            "callers": callers,
            "callees": callees
        }
        
        # 递归查找调用者的调用者
        if depth < max_depth - 1:
            for caller in callers:
                caller_name = caller["name"]
                if caller_name not in visited:
                    caller_chain = find_callers_and_callees(caller_name, depth + 1)
                    caller["callers"] = caller_chain["callers"]
        
        # 递归查找被调用者的被调用者
        if depth < max_depth - 1:
            for callee in callees:
                callee_name = callee["name"]
                if callee_name not in visited:
                    callee_chain = find_callers_and_callees(callee_name, depth + 1)
                    callee["callees"] = callee_chain["callees"]
        
        return result
    
    # 查找每个函数的调用链
    for function_name in function_names:
        visited.clear()
        # 先查找函数是否存在
        func_def = find_function_in_codebase(directory, extensions, function_name)
        if func_def:
            result[function_name] = find_callers_and_callees(function_name, 0)
        else:
            print(f"警告: 未找到函数定义 '{function_name}'")
            result[function_name] = {"callers": [], "callees": []}
    
    return result

def display_function(function: Dict[str, Any], show_relevance: bool = True):
    """显示函数信息"""
    print("\n" + "="*80)
    print(f"函数: {function.get('name', '未知')}")
    print("="*80)
    
    print(f"文件: {function.get('file_path', '未知')}")
    print(f"行号: {function.get('line_number', '未知')}")
    
    if show_relevance and 'relevance' in function:
        print(f"相关度: {function['relevance']}")
    
    if 'calls' in function:
        print(f"调用次数: {function['calls']}")
    
    print("\n源代码:")
    print("-"*80)
    print(function.get('body', '无法获取函数体'))
    print("-"*80)

def display_call_chain(chain: Dict[str, List[Dict[str, Any]]], function_name: str, indent: int = 0):
    """
    显示调用链信息
    
    Args:
        chain: 调用链信息
        function_name: 当前函数名
        indent: 缩进层级
    """
    indentation = "  " * indent
    print(f"{indentation}函数: {function_name}")
    
    callers = chain.get("callers", [])
    callees = chain.get("callees", [])
    
    if callers:
        print(f"{indentation}被调用者 ({len(callers)}):")
        for caller in callers:
            caller_name = caller.get("name", "未知")
            file_path = caller.get("file_path", "未知")
            line_number = caller.get("line_number", "未知")
            print(f"{indentation}  - {caller_name} (在 {file_path}:{line_number})")
            
            # 递归显示调用者的调用者
            if "callers" in caller:
                display_call_chain({"callers": caller["callers"], "callees": []}, caller_name, indent + 2)
    
    if callees:
        print(f"{indentation}调用者 ({len(callees)}):")
        for callee in callees:
            callee_name = callee.get("name", "未知")
            file_path = callee.get("file_path", "未知")
            line_number = callee.get("line_number", "未知")
            print(f"{indentation}  - {callee_name} (在 {file_path}:{line_number})")
            
            # 递归显示被调用者的被调用者
            if "callees" in callee:
                display_call_chain({"callers": [], "callees": callee["callees"]}, callee_name, indent + 2)

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="代码查找工具 - 检查代码库中是否存在特定功能的实现")
    parser.add_argument("description", help="功能描述或函数名", nargs='?')
    parser.add_argument("--dir", "-d", default=".", help="要搜索的目录（默认：当前目录）")
    parser.add_argument("--extensions", "-e", default=".c,.h,.cpp,.hpp,.py,.js,.ts,.java", 
                      help="文件扩展名，以逗号分隔（默认：.c,.h,.cpp,.hpp,.py,.js,.ts,.java）")
    parser.add_argument("--limit", "-l", type=int, default=5, help="最大结果数量（默认：5）")
    parser.add_argument("--find-calls", "-f", help="查找调用指定函数名的所有函数")
    parser.add_argument("--call-chain", "-c", help="查找函数调用链（可以是多个函数名，用逗号分隔）")
    parser.add_argument("--max-depth", "-m", type=int, default=3, help="调用链最大深度（默认：3）")
    parser.add_argument("--use-graph-db", "-g", action="store_true", help="是否使用图数据库")
    parser.add_argument("--graph-uri", default="bolt://localhost:7687", help="图数据库URI（默认：bolt://localhost:7687）")
    parser.add_argument("--graph-user", default="neo4j", help="图数据库用户名（默认：neo4j）")
    parser.add_argument("--graph-password", default="password", help="图数据库密码（默认：password）")
    parser.add_argument("--export", "-o", help="导出完整调用链到指定文件")
    parser.add_argument("--export-format", choices=["txt", "md", "json"], default="md", 
                      help="导出格式（默认：md）")
    parser.add_argument("--full-chain", action="store_true", 
                      help="是否导出完整调用链（包括所有上下游函数）")
    parser.add_argument("--build-graph", action="store_true", 
                      help="构建函数调用关系图数据库")
    parser.add_argument("--clear-graph", action="store_true", 
                      help="清除图数据库中的现有数据")
    
    args = parser.parse_args()
    
    # 将扩展名字符串分割为列表
    extensions = args.extensions.split(',')

    # 构建图数据库
    if args.build_graph:
        if not HAS_NEO4J:
            print("错误: 请先安装py2neo库以使用图数据库功能")
            print("      pip install py2neo")
            return
            
        try:
            print(f"开始构建函数调用关系图数据库，分析目录: {args.dir}")
            graph = build_graph_database(
                args.dir, 
                extensions, 
                args.graph_uri, 
                args.graph_user, 
                args.graph_password, 
                args.clear_graph
            )
            print("图数据库构建完成!")
            return
        except Exception as e:
            print(f"构建图数据库时出错: {e}")
            return

    # 查找函数调用链
    if args.call_chain:
        function_names = [name.strip() for name in args.call_chain.split(',')]
        print(f"查找函数 {', '.join(function_names)} 的调用链...")
        
        # 使用图数据库查询调用链
        if args.use_graph_db:
            if not HAS_NEO4J:
                print("错误: 请先安装py2neo库以使用图数据库功能")
                print("      pip install py2neo")
                return
                
            try:
                # 连接到图数据库
                graph = connect_to_graph_db(args.graph_uri, args.graph_user, args.graph_password)
                
                # 获取高级调用链信息
                chains = get_advanced_call_chain(graph, function_names, args.max_depth)
                
                # 存储所有相关函数
                all_functions = {}
                function_ids = []
                
                # 收集所有函数ID
                for function_name, chain in chains.items():
                    for func in chain["all_related_functions"]:
                        if "id" in func:
                            function_ids.append(func["id"])
                
                # 检索函数源代码
                sources = retrieve_function_source(graph, function_ids, args.dir)
                
                # 构建用于导出的函数信息
                for function_name, chain in chains.items():
                    print(f"\n\n函数 {function_name} 的调用链:")
                    
                    # 显示上游路径
                    if chain["upstream_paths"]:
                        print(f"上游调用链 (共 {len(chain['upstream_paths'])} 条):")
                        for i, path_info in enumerate(chain["upstream_paths"], 1):
                            print(f"  路径 {i}:")
                            # 在这里可以遍历路径并显示详细信息
                    
                    # 显示下游路径
                    if chain["downstream_paths"]:
                        print(f"下游调用链 (共 {len(chain['downstream_paths'])} 条):")
                        for i, path_info in enumerate(chain["downstream_paths"], 1):
                            print(f"  路径 {i}:")
                            # 在这里可以遍历路径并显示详细信息
                    
                    # 收集相关函数的信息
                    for func in chain["all_related_functions"]:
                        func_id = func.get("id")
                        if func_id and func_id in sources:
                            func["body"] = sources[func_id]
                            all_functions[func_id] = func
                
                # 导出所有收集到的函数
                if args.export:
                    if not all_functions:
                        print(f"警告: 未找到任何函数定义，无法导出")
                    else:
                        export_functions(all_functions, args.export, args.export_format)
                        print(f"\n已导出 {len(all_functions)} 个函数到文件 {args.export}")
                
                return
            except Exception as e:
                print(f"连接图数据库时出错: {e}")
                print("请确保Neo4j服务正在运行且可以访问")
                return
        else:
            print("错误: 您必须使用 --use-graph-db 参数来查询函数调用链")
            print("提示: 先使用 --build-graph 构建图数据库，然后使用 --use-graph-db 查询")
            return
    
    # 必须提供description参数用于搜索
    if not args.description and not args.find_calls:
        parser.error("未提供搜索描述或函数名")
    
    # 查找函数调用
    if args.find_calls:
        function_name = args.find_calls
        print(f"在 {args.dir} 中搜索调用 '{function_name}' 的函数...")
        results = find_function_calls(args.dir, extensions, function_name, args.limit)
        
        if not results:
            print(f"\n未找到调用 '{function_name}' 的函数。")
            return
        
        print(f"\n找到 {len(results)} 个调用 '{function_name}' 的函数:")
    # 常规搜索功能
    else:
        # 提取关键词
        keywords = extract_keywords(args.description)
        print(f"搜索关键词: {', '.join(keywords)}")
        
        print(f"在 {args.dir} 中搜索匹配 '{args.description}' 的函数...")
        results = search_code_files(args.dir, extensions, keywords, args.limit)
        
        if not results:
            print("\n未找到匹配的函数。可能需要实现该功能。")
            return
        
        print(f"\n找到 {len(results)} 个可能相关的函数:")
    
    # 显示结果
    for i, function in enumerate(results, 1):
        print(f"\n[结果 {i}/{len(results)}]")
        display_function(function)
        
        # 如果不是最后一个结果，等待用户确认
        if i < len(results):
            input("按回车键查看下一个结果...")

def crawl_callers(directory: str, extensions: List[str], callers: List[Dict[str, Any]], 
                 all_functions: Dict[str, Dict[str, Any]], visited: Set[str], max_depth: int = 3):
    """
    递归查找更多的调用者
    
    Args:
        directory: 要搜索的目录
        extensions: 文件扩展名列表
        callers: 当前的调用者列表
        all_functions: 所有收集到的函数
        visited: 已访问的函数名集合，避免循环
        max_depth: 最大查找深度
    """
    if max_depth <= 0:
        return
    
    for caller in callers:
        caller_name = caller.get("name", "")
        
        if not caller_name or caller_name in visited:
            continue
            
        visited.add(caller_name)
        all_functions[caller_name] = caller
        
        # 查找调用当前函数的函数
        higher_callers = find_function_calls(directory, extensions, caller_name)
        
        # 递归查找上层调用者
        crawl_callers(directory, extensions, higher_callers, all_functions, visited, max_depth - 1)

def crawl_callees(directory: str, extensions: List[str], callees: List[Dict[str, Any]], 
                 all_functions: Dict[str, Dict[str, Any]], visited: Set[str], max_depth: int = 3):
    """
    递归查找更多的被调用者
    
    Args:
        directory: 要搜索的目录
        extensions: 文件扩展名列表
        callees: 当前的被调用者列表
        all_functions: 所有收集到的函数
        visited: 已访问的函数名集合，避免循环
        max_depth: 最大查找深度
    """
    if max_depth <= 0:
        return
    
    for callee in callees:
        callee_name = callee.get("name", "")
        
        if not callee_name or callee_name in visited:
            continue
            
        visited.add(callee_name)
        all_functions[callee_name] = callee
        
        # 查找当前函数调用的函数
        func_def = find_function_in_codebase(directory, extensions, callee_name)
        if not func_def or "body" not in func_def:
            continue
            
        # 提取函数调用
        body = func_def["body"]
        
        # 简单的函数调用模式匹配
        call_pattern = re.compile(r'[^a-zA-Z0-9_]([a-zA-Z0-9_]+)\s*\(')
        lower_callees = []
        
        for match in call_pattern.finditer(body):
            lower_callee_name = match.group(1)
            # 跳过内置函数
            if lower_callee_name in ["print", "len", "int", "str", "float", "list", "dict", "set", "tuple"]:
                continue
                
            lower_callee_def = find_function_in_codebase(directory, extensions, lower_callee_name)
            if lower_callee_def:
                lower_callees.append(lower_callee_def)
        
        # 递归查找下层被调用者
        crawl_callees(directory, extensions, lower_callees, all_functions, visited, max_depth - 1)

def export_functions(functions: Dict[str, Dict[str, Any]], filename: str, format: str = "md"):
    """
    导出函数到文件
    
    Args:
        functions: 函数字典
        filename: 导出文件名
        format: 导出格式 (txt, md, json)
    """
    if format == "json":
        # 导出为JSON格式
        import json
        
        # 将复杂对象转换为可序列化的形式
        serializable_funcs = {}
        for name, func in functions.items():
            serializable_func = {
                "name": func.get("name", "未知"),
                "file_path": func.get("file_path", "未知"),
                "line_number": func.get("line_number", "未知"),
                "body": func.get("body", ""),
                "relevance": func.get("relevance", 0),
                "calls": func.get("calls", 0)
            }
            serializable_funcs[name] = serializable_func
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(serializable_funcs, f, ensure_ascii=False, indent=2)
            
    elif format == "md":
        # 导出为Markdown格式
        with open(filename, 'w', encoding='utf-8') as f:
            f.write("# 函数调用链分析\n\n")
            
            # 按文件路径对函数进行分组
            funcs_by_file = {}
            for func in functions.values():
                file_path = func.get("file_path", "未知")
                if file_path not in funcs_by_file:
                    funcs_by_file[file_path] = []
                funcs_by_file[file_path].append(func)
            
            # 按文件输出
            for file_path, funcs in funcs_by_file.items():
                f.write(f"## 文件: {file_path}\n\n")
                
                # 排序函数，按行号排序
                funcs.sort(key=lambda x: x.get("line_number", 0))
                
                for func in funcs:
                    name = func.get("name", "未知")
                    line_number = func.get("line_number", "未知")
                    body = func.get("body", "")
                    
                    f.write(f"### 函数: {name} (行号: {line_number})\n\n")
                    f.write("```\n")
                    f.write(body)
                    f.write("\n```\n\n")
    else:
        # 导出为纯文本格式
        with open(filename, 'w', encoding='utf-8') as f:
            f.write("函数调用链分析\n\n")
            
            for func in functions.values():
                name = func.get("name", "未知")
                file_path = func.get("file_path", "未知")
                line_number = func.get("line_number", "未知")
                body = func.get("body", "")
                
                f.write(f"函数: {name}\n")
                f.write(f"文件: {file_path}\n")
                f.write(f"行号: {line_number}\n")
                f.write("\n源代码:\n")
                f.write("-"*80 + "\n")
                f.write(body)
                f.write("\n" + "-"*80 + "\n\n")

def build_graph_database(directory: str, extensions: List[str], graph_uri: str, 
                        graph_user: str, graph_password: str, clear_existing: bool = False) -> 'Graph':
    """
    分析代码库并构建函数调用关系图数据库
    
    Args:
        directory: 要分析的目录
        extensions: 文件扩展名列表
        graph_uri: 图数据库连接URI
        graph_user: 图数据库用户名
        graph_password: 图数据库密码
        clear_existing: 是否清除现有数据
        
    Returns:
        图数据库连接
    """
    if not HAS_NEO4J:
        raise ImportError("请先安装py2neo库: pip install py2neo")
    
    # 连接到图数据库
    graph = connect_to_graph_db(graph_uri, graph_user, graph_password)
    
    # 清除现有数据
    if clear_existing:
        graph.run("MATCH (n) DETACH DELETE n")
    
    # 编译正则表达式来识别函数定义
    func_patterns = [
        # C/C++风格函数定义
        re.compile(r'((?:[a-zA-Z0-9_*]+\s+)+)([a-zA-Z0-9_]+)\s*\([^)]*\)\s*(?:const)?\s*(?:noexcept)?\s*{'),
        # C/C++风格函数声明
        re.compile(r'((?:[a-zA-Z0-9_*]+\s+)+)([a-zA-Z0-9_]+)\s*\([^)]*\)\s*(?:const)?\s*(?:noexcept)?\s*;'),
        # Python风格函数
        re.compile(r'def\s+([a-zA-Z0-9_]+)\s*\([^)]*\)(?:\s*->.*?)?\s*:'),
        # JavaScript/TypeScript风格函数
        re.compile(r'(?:function|const|let|var)\s+([a-zA-Z0-9_]+)\s*(?:=\s*(?:async\s*)?\([^)]*\)|=>\s*{|\([^)]*\)\s*{)')
    ]
    
    # 编译函数调用的正则表达式
    call_pattern = re.compile(r'[^a-zA-Z0-9_]([a-zA-Z0-9_]+)\s*\(')
    
    # 存储所有函数的字典
    all_functions = {}
    
    # 第一遍遍历：找到所有函数定义
    print("第一步: 提取所有函数定义...")
    for root, _, files in os.walk(directory):
        for file in files:
            if not any(file.endswith(ext) for ext in extensions):
                continue
                
            file_path = os.path.join(root, file)
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                # 提取文件中的所有函数
                for pattern in func_patterns:
                    for match in pattern.finditer(content):
                        # 找到函数的起始位置
                        start_pos = match.start()
                        line_no = content[:start_pos].count('\n') + 1
                        
                        # 提取函数名
                        if 'def ' in match.group(0):  # Python风格
                            func_name = match.group(1)
                        elif 'function ' in match.group(0) or '=' in match.group(0):  # JavaScript风格
                            func_name = match.group(1)
                        else:  # C/C++风格
                            func_name = match.group(2)
                        
                        # 提取函数体(只有函数定义才有函数体，声明没有)
                        body = ""
                        if '{' in match.group(0) or ':' in match.group(0):
                            body = extract_function_body(content, start_pos, '{', '}')
                            if not body:
                                body = extract_python_function_body(content.split('\n'), line_no)
                        
                        # 构建函数的唯一ID
                        func_id = f"{func_name}_{file_path}_{line_no}"
                        
                        # 存储函数信息
                        all_functions[func_id] = {
                            "name": func_name,
                            "file_path": file_path,
                            "line_number": line_no,
                            "body": body
                        }
            except Exception as e:
                print(f"错误处理文件 {file_path}: {e}", file=sys.stderr)
    
    # 创建函数节点
    print(f"第二步: 在图数据库中创建 {len(all_functions)} 个函数节点...")
    func_nodes = {}
    tx = graph.begin()
    batch_size = 100
    count = 0
    
    for func_id, func_info in all_functions.items():
        # 创建函数节点
        node = Node("Function", 
                   id=func_id,
                   name=func_info["name"], 
                   file_path=func_info["file_path"],
                   line_number=func_info["line_number"])
        func_nodes[func_id] = node
        tx.create(node)
        
        count += 1
        if count % batch_size == 0:
            tx.commit()
            tx = graph.begin()
            print(f"  已处理 {count}/{len(all_functions)} 个函数节点")
    
    tx.commit()
    
    # 第二遍遍历：分析函数调用关系
    print("第三步: 分析函数调用关系...")
    tx = graph.begin()
    count = 0
    relationship_count = 0
    
    for func_id, func_info in all_functions.items():
        body = func_info.get("body", "")
        if not body:
            continue
        
        # 查找函数调用
        for match in call_pattern.finditer(body):
            callee_name = match.group(1)
            
            # 跳过内置函数和关键字
            if callee_name in ["if", "for", "while", "switch", "print", "len", 
                              "int", "str", "float", "list", "dict", "set", "tuple"]:
                continue
            
            # 查找被调用的函数
            for callee_id, callee_info in all_functions.items():
                if callee_info["name"] == callee_name:
                    # 创建调用关系
                    caller_node = func_nodes[func_id]
                    callee_node = func_nodes[callee_id]
                    relationship = Relationship(caller_node, "CALLS", callee_node)
                    tx.create(relationship)
                    relationship_count += 1
                    
                    if relationship_count % batch_size == 0:
                        tx.commit()
                        tx = graph.begin()
                        print(f"  已创建 {relationship_count} 个调用关系")
        
        count += 1
        if count % batch_size == 0:
            print(f"  已分析 {count}/{len(all_functions)} 个函数的调用关系")
    
    tx.commit()
    print(f"完成! 总共创建了 {relationship_count} 个函数调用关系")
    
    # 创建索引以加快查询速度
    print("创建索引...")
    graph.run("CREATE INDEX ON :Function(name)")
    graph.run("CREATE INDEX ON :Function(id)")
    
    return graph

def get_complete_function_call_chain(graph: 'Graph', function_name: str) -> Dict[str, Any]:
    """
    使用图数据库获取完整的函数调用链
    
    Args:
        graph: 图数据库连接
        function_name: 函数名
        
    Returns:
        包含上下游调用关系的完整函数信息
    """
    # 查找调用当前函数的所有函数(上游)
    upstream_query = """
    MATCH (caller:Function)-[:CALLS]->(callee:Function {name: $function_name})
    RETURN caller.name as name, caller.file_path as file_path, caller.line_number as line_number, caller.id as id
    ORDER BY caller.name
    """
    upstream = graph.run(upstream_query, function_name=function_name).data()
    
    # 查找当前函数调用的所有函数(下游)
    downstream_query = """
    MATCH (caller:Function {name: $function_name})-[:CALLS]->(callee:Function)
    RETURN callee.name as name, callee.file_path as file_path, callee.line_number as line_number, callee.id as id
    ORDER BY callee.name
    """
    downstream = graph.run(downstream_query, function_name=function_name).data()
    
    # 获取函数自身的信息
    self_query = """
    MATCH (func:Function {name: $function_name})
    RETURN func.name as name, func.file_path as file_path, func.line_number as line_number, func.id as id
    LIMIT 1
    """
    self_info = graph.run(self_query, function_name=function_name).data()
    
    # 构建结果
    return {
        "function": self_info[0] if self_info else {"name": function_name, "not_found": True},
        "upstream": upstream,
        "downstream": downstream
    }

def get_advanced_call_chain(graph: 'Graph', function_names: List[str], max_depth: int = 3) -> Dict[str, Any]:
    """
    使用图数据库的路径查询功能获取更复杂的调用链
    
    Args:
        graph: 图数据库连接
        function_names: 函数名列表
        max_depth: 最大调用深度
        
    Returns:
        完整的调用链信息
    """
    result = {}
    
    for function_name in function_names:
        # 向上查找最长的调用链路径
        upstream_query = f"""
        MATCH path = (caller:Function)-[:CALLS*1..{max_depth}]->(callee:Function {{name: $function_name}})
        RETURN path, length(path) as depth
        ORDER BY depth DESC
        LIMIT 10
        """
        upstream_paths = graph.run(upstream_query, function_name=function_name).data()
        
        # 向下查找最长的调用链路径
        downstream_query = f"""
        MATCH path = (caller:Function {{name: $function_name}})-[:CALLS*1..{max_depth}]->(callee:Function)
        RETURN path, length(path) as depth
        ORDER BY depth DESC
        LIMIT 10
        """
        downstream_paths = graph.run(downstream_query, function_name=function_name).data()
        
        # 获取所有相关的函数节点
        all_functions_query = f"""
        MATCH (start:Function)-[:CALLS*0..{max_depth}]-(related:Function)
        WHERE start.name = $function_name
        RETURN DISTINCT related.name as name, related.file_path as file_path, 
               related.line_number as line_number, related.id as id
        """
        all_related = graph.run(all_functions_query, function_name=function_name).data()
        
        result[function_name] = {
            "upstream_paths": upstream_paths,
            "downstream_paths": downstream_paths,
            "all_related_functions": all_related
        }
    
    return result

def retrieve_function_source(graph: 'Graph', function_ids: List[str], directory: str) -> Dict[str, str]:
    """
    获取函数的源代码
    
    Args:
        graph: 图数据库连接
        function_ids: 函数ID列表
        directory: 代码目录
        
    Returns:
        函数ID到源代码的映射
    """
    result = {}
    
    for func_id in function_ids:
        # 从图数据库获取函数信息
        query = """
        MATCH (func:Function {id: $func_id})
        RETURN func.name as name, func.file_path as file_path, func.line_number as line_number
        """
        func_info = graph.run(query, func_id=func_id).data()
        
        if not func_info:
            continue
            
        func_info = func_info[0]
        file_path = func_info["file_path"]
        line_number = func_info["line_number"]
        
        # 读取文件并提取函数体
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
            # 定位到函数定义
            lines = content.split('\n')
            line_index = line_number - 1
            
            # 获取函数体
            func_body = extract_function_at_line(lines, line_index)
            if func_body:
                result[func_id] = func_body
        except Exception as e:
            print(f"错误获取函数源码 {func_id}: {e}", file=sys.stderr)
    
    return result

def extract_function_at_line(lines: List[str], line_index: int) -> str:
    """
    从给定行提取函数体
    
    Args:
        lines: 文件的所有行
        line_index: 函数定义所在的行索引
        
    Returns:
        函数体字符串
    """
    if line_index >= len(lines):
        return ""
        
    # 检查是否为函数定义行
    line = lines[line_index]
    is_c_style = '{' in line
    is_python_style = 'def ' in line and ':' in line
    
    if is_c_style:
        # C/C++风格函数
        return extract_c_function_body(lines, line_index)
    elif is_python_style:
        # Python风格函数
        return extract_python_function_body(lines, line_index + 1)
    
    return ""

def extract_c_function_body(lines: List[str], start_line: int) -> str:
    """提取C/C++风格函数体"""
    body_lines = []
    open_braces = 0
    found_opening = False
    
    for i in range(start_line, len(lines)):
        line = lines[i]
        body_lines.append(line)
        
        # 计算大括号数量
        for char in line:
            if char == '{':
                open_braces += 1
                found_opening = True
            elif char == '}':
                open_braces -= 1
        
        # 如果已经找到了开始的大括号，且大括号数量平衡，说明函数结束
        if found_opening and open_braces == 0:
            break
    
    return '\n'.join(body_lines)

if __name__ == "__main__":
    main() 