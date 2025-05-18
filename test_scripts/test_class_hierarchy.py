#!/usr/bin/env python
"""
测试类层次结构分析和虚函数解析。
"""
import os
import sys
import json
from pprint import pprint

# 添加父级目录到Python路径以便导入src模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config.libclang_config import configure_libclang
from src.services.clang_analyzer_service import ClangAnalyzerService
from src.services.class_hierarchy_service import ClassHierarchyService
from clang.cindex import Index, TranslationUnit, Config

def test_class_hierarchy(file_path):
    """测试指定文件的类层次结构和虚函数分析。"""
    print(f"\n===== 测试类层次结构和虚函数分析: {file_path} =====\n")
    
    # 配置libclang，确保在创建任何服务之前完成
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
    
    # 分析类层次结构
    print("\n分析类层次结构...")
    class_service = ClassHierarchyService(index)
    class_hierarchy = class_service.analyze_translation_unit(tu)
    
    # 打印类层次结构信息
    print(f"\n发现 {len(class_hierarchy.classes)} 个类:")
    for class_name, class_node in sorted(class_hierarchy.classes.items()):
        print(f"\n类: {class_name}")
        
        # 打印基类信息
        if class_node.base_classes:
            print(f"  基类: {', '.join(sorted(class_node.base_classes))}")
            print(f"  基类访问修饰符: {class_node.base_class_access}")
        
        # 打印派生类信息
        if class_node.derived_classes:
            print(f"  派生类: {', '.join(sorted(class_node.derived_classes))}")
        
        # 打印虚函数信息
        if class_node.virtual_methods:
            print(f"  虚函数: {', '.join(sorted(class_node.virtual_methods))}")
            
            # 打印纯虚函数
            pure_virtuals = class_node.pure_virtual_methods
            if pure_virtuals:
                print(f"  纯虚函数: {', '.join(sorted(pure_virtuals))}")
            
            # 打印重写的方法
            if class_node.overridden_methods:
                print("  重写的方法:")
                for method, bases in sorted(class_node.overridden_methods.items()):
                    print(f"    {method} 重写自: {', '.join(sorted(bases))}")
    
    # 测试虚函数表构建
    print("\n测试虚函数表构建...")
    for class_name in sorted(class_hierarchy.classes.keys()):
        vtable = class_service.get_virtual_method_table(class_name)
        if vtable:
            print(f"\n类 '{class_name}' 的虚函数表:")
            for method, impls in sorted(vtable.items()):
                print(f"  {method}: {', '.join(impls)}")
    
    # 测试虚函数调用解析
    print("\n测试虚函数调用解析...")
    test_virtual_calls = [
        ("Shape", "area"),
        ("Shape", "perimeter"),
        ("Shape", "name"),
        ("Shape", "draw"),
        ("Circle", "area"),
        ("Polygon", "getSides"),
        ("Rectangle", "area"),
        ("Square", "name"),
    ]
    
    for base_class, method in test_virtual_calls:
        impls = class_service.resolve_virtual_call(base_class, method)
        print(f"通过 {base_class} 指针调用 {method}() 可能的实现: {', '.join(impls)}")
    
    # 先检查是否有我们刚刚分析过的测试类
    test_classes = ["Shape", "Circle", "Rectangle", "Square", "Polygon", "ColoredShape", "DrawableShape", "ColoredPolygon"]
    found_test_classes = [cls for cls in test_classes if cls in class_hierarchy.classes]
    
    if found_test_classes:
        print(f"\n找到测试类: {', '.join(found_test_classes)}")
    else:
        print("\n没有找到预期的测试类，跳过函数分析部分")
        return
    
    # 分析整个文件的函数
    print("\n分析文件中的函数...")
    analyzer = ClangAnalyzerService()
    call_graph = analyzer.analyze_file(file_path)
    
    # 丰富函数信息
    print("\n增强函数模型...")
    class_service.enrich_function_model(call_graph.functions)
    
    # 解析虚函数调用
    print("\n解析虚函数调用...")
    class_service.resolve_virtual_calls(call_graph.functions)
    
    # 打印函数信息
    print(f"\n发现 {len(call_graph.functions)} 个函数:")
    for func_name, func in sorted(call_graph.functions.items()):
        if "::" in func_name:  # 只显示类方法
            print(f"\n方法: {func_name}")
            
            # 打印成员信息
            print(f"  类: {func.class_name}")
            
            # 打印虚函数信息
            if func.is_virtual:
                print(f"  虚函数: 是")
                
                # 打印重写信息
                if func.overrides:
                    print(f"  重写: {', '.join(func.overrides)}")
            
            # 打印调用信息
            if func.calls:
                print(f"  调用: {', '.join(func.calls[:5])}{'...' if len(func.calls) > 5 else ''}")
    
    # 导出为JSON
    print("\n将类层次结构导出为JSON...")
    output_dir = os.path.join(os.path.dirname(file_path), "../output")
    os.makedirs(output_dir, exist_ok=True)
    
    output_file = os.path.join(output_dir, "class_hierarchy.json")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(class_hierarchy.to_dict(), f, indent=2)
    print(f"类层次结构已导出到: {output_file}")

def main():
    """主函数"""
    # 获取项目根目录
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # 测试文件路径
    test_file = os.path.join(root_dir, "test_files", "class_hierarchy_test.cpp")
    
    # 执行测试
    test_class_hierarchy(test_file)

if __name__ == "__main__":
    main() 