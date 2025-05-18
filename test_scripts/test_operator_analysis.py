#!/usr/bin/env python
"""
测试C++运算符重载和隐式转换分析。
"""
import os
import sys
import json
from pprint import pprint

# 添加父级目录到Python路径以便导入src模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config.libclang_config import configure_libclang
from src.services.clang_analyzer_service import ClangAnalyzerService
from clang.cindex import Index, TranslationUnit, Config, CursorKind, TypeKind

def detect_operator_overloads(cursor):
    """
    递归检测指定游标下的运算符重载。
    
    Args:
        cursor: 开始检测的游标
        
    Returns:
        运算符重载信息的列表
    """
    operators = []
    
    def process_cursor(c):
        # 检查是否是运算符重载函数
        if c.kind == CursorKind.CXX_METHOD and "operator" in c.spelling:
            operators.append({
                "name": c.spelling,
                "location": f"{c.location.file.name}:{c.location.line}" if c.location.file else "",
                "return_type": c.result_type.spelling,
                "parameters": [param.type.spelling for param in c.get_arguments()],
                "is_member": True,
                "class_name": c.semantic_parent.spelling if c.semantic_parent else "",
                "is_const": c.is_const_method() if hasattr(c, 'is_const_method') else False,
                "is_static": c.is_static_method() if hasattr(c, 'is_static_method') else False
            })
        elif c.kind == CursorKind.FUNCTION_DECL and "operator" in c.spelling:
            operators.append({
                "name": c.spelling,
                "location": f"{c.location.file.name}:{c.location.line}" if c.location.file else "",
                "return_type": c.result_type.spelling,
                "parameters": [param.type.spelling for param in c.get_arguments()],
                "is_member": False,
                "is_friend": c.is_friend_declaration() if hasattr(c, 'is_friend_declaration') else False
            })
            
        # 递归处理所有子节点
        for child in c.get_children():
            process_cursor(child)
    
    process_cursor(cursor)
    return operators

def detect_conversion_operators(cursor):
    """
    递归检测指定游标下的类型转换运算符。
    
    Args:
        cursor: 开始检测的游标
        
    Returns:
        类型转换运算符信息的列表
    """
    conversions = []
    
    def process_cursor(c):
        # 检查是否是转换运算符或转换构造函数
        
        # 检测转换运算符 (operator TypeName())
        if c.kind == CursorKind.CXX_METHOD and c.spelling.startswith("operator "):
            # 排除其他运算符重载
            operator_type = c.spelling.replace("operator ", "")
            if not any(op in operator_type for op in ["+", "-", "*", "/", "%", "&", "|", "^", "~", "!", "=", "<", ">", "[]", "()", "->", ">>", "<<"]):
                is_explicit = any(token.spelling == "explicit" for token in c.get_tokens())
                conversions.append({
                    "name": c.spelling,
                    "location": f"{c.location.file.name}:{c.location.line}" if c.location.file else "",
                    "class_name": c.semantic_parent.spelling if c.semantic_parent else "",
                    "target_type": operator_type,
                    "is_explicit": is_explicit,
                    "type": "operator"
                })
        
        # 检测转换构造函数 (单参数非explicit构造函数)
        elif c.kind == CursorKind.CONSTRUCTOR:
            args = list(c.get_arguments())
            if len(args) == 1 and args[0].type.spelling != "void":
                is_explicit = any(token.spelling == "explicit" for token in c.get_tokens())
                if not is_explicit:
                    conversions.append({
                        "name": c.spelling,
                        "location": f"{c.location.file.name}:{c.location.line}" if c.location.file else "",
                        "class_name": c.semantic_parent.spelling if c.semantic_parent else "",
                        "source_type": args[0].type.spelling,
                        "is_explicit": False,
                        "type": "constructor"
                    })
            
        # 递归处理所有子节点
        for child in c.get_children():
            process_cursor(child)
    
    process_cursor(cursor)
    return conversions

def test_operator_analysis(file_path):
    """测试对指定C++文件的运算符重载和隐式转换检测。"""
    print(f"\n===== 测试运算符重载和隐式转换分析: {file_path} =====\n")
    
    # 配置libclang
    print("配置libclang...")
    libclang_path = configure_libclang()
    
    # 初始化Clang
    print("初始化Clang...")
    index = Index.create()
    
    # 解析文件
    print(f"解析文件: {file_path}")
    try:
        tu = index.parse(file_path, args=['-std=c++17', '-xc++'])
        if not tu:
            print(f"错误: 无法解析文件 {file_path}")
            return
    except Exception as e:
        print(f"解析错误: {e}")
        return
    
    # 打印解析的AST结构（用于调试）
    print("\n调试: 打印AST结构...")
    
    def print_ast(cursor, level=0):
        if cursor.location.file and cursor.location.file.name == file_path:
            indent = '  ' * level
            print(f"{indent}{cursor.kind}: {cursor.spelling} ({cursor.location.line if cursor.location.line else 'unknown'})")
            for child in cursor.get_children():
                print_ast(child, level + 1)
    
    print_ast(tu.cursor)
    
    # 检测运算符重载
    print("\n检测运算符重载...")
    operator_overloads = detect_operator_overloads(tu.cursor)
    
    # 输出运算符重载信息
    print(f"\n找到 {len(operator_overloads)} 个运算符重载:")
    for op in operator_overloads:
        if op["is_member"]:
            print(f"\n成员运算符: {op['class_name']}::{op['name']}")
            if op.get("is_const"):
                print("  const: 是")
            if op.get("is_static"):
                print("  static: 是")
        else:
            print(f"\n非成员运算符: {op['name']}")
            if op.get("is_friend"):
                print("  friend: 是")
        
        print(f"  位置: {op['location']}")
        print(f"  返回类型: {op['return_type']}")
        print(f"  参数类型: {', '.join(op['parameters'])}")
    
    # 检测类型转换
    print("\n检测类型转换运算符和隐式转换...")
    conversion_operators = detect_conversion_operators(tu.cursor)
    
    # 输出类型转换信息
    print(f"\n找到 {len(conversion_operators)} 个类型转换:")
    for conv in conversion_operators:
        if conv["type"] == "operator":
            print(f"\n转换运算符: {conv['class_name']}::{conv['name']}")
            print(f"  目标类型: {conv['target_type']}")
        else:
            print(f"\n转换构造函数: {conv['class_name']}::{conv['name']}")
            print(f"  源类型: {conv['source_type']}")
        
        print(f"  位置: {conv['location']}")
        print(f"  explicit: {'是' if conv['is_explicit'] else '否'}")
    
    # 导出为JSON
    print("\n将分析结果导出为JSON...")
    output_dir = os.path.join(os.path.dirname(file_path), "../output")
    os.makedirs(output_dir, exist_ok=True)
    
    output_file = os.path.join(output_dir, "operator_analysis.json")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            "operator_overloads": operator_overloads,
            "conversion_operators": conversion_operators
        }, f, indent=2)
    print(f"分析结果已导出到: {output_file}")

def main():
    """主函数"""
    # 获取项目根目录
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # 测试文件路径
    test_file = os.path.join(root_dir, "test_files", "operator_overload_test.cpp")
    
    # 执行测试
    test_operator_analysis(test_file)

if __name__ == "__main__":
    main() 