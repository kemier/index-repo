#!/usr/bin/env python
"""
测试C++20概念(concepts)分析。
"""
import os
import sys
import json
import re
from pprint import pprint

# 添加父级目录到Python路径以便导入src模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config.libclang_config import configure_libclang
from src.services.clang_analyzer_service import ClangAnalyzerService
from clang.cindex import Index, TranslationUnit, Config, CursorKind, TypeKind

def detect_concepts(cursor):
    """
    递归检测指定游标下的C++20概念定义和使用。
    
    Args:
        cursor: 开始检测的游标
        
    Returns:
        概念定义和使用的信息列表
    """
    concepts = []
    concept_usages = []
    
    def process_cursor(c):
        # 调试输出
        if False and c.location.file and "concepts_test.cpp" in c.location.file.name:
            print(f"Cursor: {c.kind} - {c.spelling}")
        
        # Clang可能不直接支持CONCEPT_DECL，我们使用字符串匹配
        if c.kind == CursorKind.UNEXPOSED_DECL or c.kind == CursorKind.VAR_DECL:
            # 检查是否是概念定义
            source_text = get_source_text(c)
            if source_text and "concept" in source_text:
                concept_match = re.search(r'concept\s+(\w+)\s*=', source_text)
                if concept_match:
                    concept_name = concept_match.group(1)
                    concepts.append({
                        "name": concept_name,
                        "location": f"{c.location.file.name}:{c.location.line}" if c.location.file else "",
                        "type": "concept_definition",
                        "source": source_text
                    })
        
        # 检查模板参数是否使用概念约束
        if c.kind == CursorKind.FUNCTION_TEMPLATE:
            source_text = get_source_text(c)
            
            # 检查函数模板是否有requires子句
            if source_text and "requires" in source_text:
                requires_match = re.search(r'requires\s+([^{]+)', source_text)
                if requires_match:
                    concept_usages.append({
                        "location": f"{c.location.file.name}:{c.location.line}" if c.location.file else "",
                        "type": "requires_clause",
                        "source": requires_match.group(0),
                        "function_name": c.spelling
                    })
            
            # 检查函数参数是否使用概念约束 (如 ConceptName auto param)
            for child in c.get_children():
                if child.kind == CursorKind.PARM_DECL:
                    param_source = get_source_text(child)
                    if param_source and "auto" in param_source:
                        for concept in concepts:
                            if concept["name"] in param_source:
                                concept_usages.append({
                                    "location": f"{child.location.file.name}:{child.location.line}" if child.location.file else "",
                                    "type": "auto_parameter_constraint",
                                    "source": param_source,
                                    "function_name": c.spelling
                                })
                                break
        
        # 检查模板类声明和特化
        if c.kind == CursorKind.CLASS_TEMPLATE:
            source_text = get_source_text(c)
            if source_text:
                template_parts = re.search(r'template\s*<([^>]+)>', source_text)
                if template_parts:
                    template_params = template_parts.group(1)
                    for concept in concepts:
                        if concept["name"] in template_params:
                            concept_usages.append({
                                "location": f"{c.location.file.name}:{c.location.line}" if c.location.file else "",
                                "type": "template_parameter_constraint",
                                "source": template_params,
                                "class_name": c.spelling
                            })
        
        # 使用clang_getTemplateCursorKind(c)获取更多元信息 (不可行，因为Python绑定不完整)
        # 而改为解析源码识别其他用法
        source_text = get_source_text(c)
        if source_text and c.location.file:
            # 识别类似 Number auto func() 形式的概念用法
            for concept in concepts:
                pattern = r'{}(?:\s+auto)'.format(concept["name"])
                if re.search(pattern, source_text):
                    concept_usages.append({
                        "location": f"{c.location.file.name}:{c.location.line}" if c.location.file else "",
                        "type": "auto_concept_constraint",
                        "source": source_text,
                        "concept_name": concept["name"]
                    })
            
            # 识别partial specialization with concepts
            if "template" in source_text and "struct" in source_text and any(concept["name"] in source_text for concept in concepts):
                for concept in concepts:
                    if concept["name"] in source_text:
                        concept_usages.append({
                            "location": f"{c.location.file.name}:{c.location.line}" if c.location.file else "",
                            "type": "template_specialization",
                            "source": source_text,
                            "concept_name": concept["name"]
                        })
            
        # 递归处理所有子节点
        for child in c.get_children():
            process_cursor(child)
    
    def get_source_text(cursor):
        """获取游标的源代码文本"""
        if not cursor.extent.start.file:
            return None
            
        if cursor.extent.start.file.name != cursor.extent.end.file.name:
            return None
            
        try:
            with open(cursor.extent.start.file.name, 'r', encoding='utf-8') as f:
                source_code = f.read()
                
            # 获取行列信息
            start_line = cursor.extent.start.line - 1  # 0-based
            start_col = cursor.extent.start.column - 1
            end_line = cursor.extent.end.line - 1
            end_col = cursor.extent.end.column - 1
            
            # 提取源代码
            lines = source_code.splitlines()
            if start_line == end_line:
                return lines[start_line][start_col:end_col]
            else:
                result = [lines[start_line][start_col:]]
                for line in range(start_line + 1, end_line):
                    result.append(lines[line])
                result.append(lines[end_line][:end_col])
                return '\n'.join(result)
        except Exception as e:
            print(f"Error extracting source code: {e}")
            return None
    
    # 预先扫描文件以识别概念定义
    def prescan_concepts(source_file):
        """预先扫描文件识别所有概念定义"""
        try:
            with open(source_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # 使用正则表达式匹配所有概念定义
            concept_matches = re.finditer(r'template\s*<[^>]+>\s*concept\s+(\w+)\s*=', content)
            for match in concept_matches:
                concept_name = match.group(1)
                line_number = content[:match.start()].count('\n') + 1
                concepts.append({
                    "name": concept_name,
                    "location": f"{source_file}:{line_number}",
                    "type": "concept_definition_scan",
                    "source": content[match.start():match.end()]
                })
                print(f"找到概念定义: {concept_name} 在行 {line_number}")
        except Exception as e:
            print(f"Error scanning file: {e}")
    
    # 首先预扫描概念定义
    if cursor.translation_unit and cursor.translation_unit.cursor.location.file:
        prescan_concepts(cursor.translation_unit.cursor.location.file.name)
    
    # 然后处理整个AST
    process_cursor(cursor)
    return concepts, concept_usages

def test_concepts_analysis(file_path):
    """测试对指定C++文件的C++20概念分析。"""
    print(f"\n===== 测试C++20概念分析: {file_path} =====\n")
    
    # 配置libclang
    print("配置libclang...")
    libclang_path = configure_libclang()
    
    # 初始化Clang
    print("初始化Clang...")
    try:
        from clang.cindex import Index, Config
        index = Index.create()
    except Exception as e:
        # 处理特定兼容性错误
        print(f"警告: 检测到libclang兼容性问题: {e}")
        print("尝试使用兼容性模式...")
        try:
            # 尝试设置兼容性检查为False
            Config.compatibility_check = False
            index = Index.create()
            print("成功在兼容性模式下创建Index")
        except Exception as fallback_error:
            print(f"错误: 无法在兼容性模式下创建Index: {fallback_error}")
            print("将使用有限功能")
            return
    
    # 解析文件
    print(f"解析文件: {file_path}")
    try:
        # 使用C++20标准
        tu = index.parse(file_path, args=['-std=c++20', '-xc++'])
        if not tu:
            print(f"错误: 无法解析文件 {file_path}")
            return
    except Exception as e:
        print(f"解析错误: {e}")
        return
    
    # 检测C++20概念
    print("\n检测C++20概念定义和使用...")
    concepts, concept_usages = detect_concepts(tu.cursor)
    
    # 输出概念定义信息
    print(f"\n找到 {len(concepts)} 个概念定义:")
    for concept in concepts:
        print(f"\n概念定义: {concept['name']}")
        print(f"  位置: {concept['location']}")
        print(f"  类型: {concept['type']}")
        if concept.get('source'):
            print(f"  源代码: {concept['source']}")
    
    # 输出概念使用信息
    print(f"\n找到 {len(concept_usages)} 个概念使用:")
    for usage in concept_usages:
        print(f"\n概念使用位置: {usage['location']}")
        print(f"  类型: {usage['type']}")
        if usage.get('function_name'):
            print(f"  函数: {usage['function_name']}")
        if usage.get('parent_name'):
            print(f"  父节点: {usage['parent_name']}")
        if usage.get('class_name'):
            print(f"  类: {usage['class_name']}")
        if usage.get('concept_name'):
            print(f"  概念名: {usage['concept_name']}")
        if usage.get('source'):
            print(f"  源代码: {usage['source']}")
    
    # 导出为JSON
    print("\n将分析结果导出为JSON...")
    output_dir = os.path.join(os.path.dirname(file_path), "../output")
    os.makedirs(output_dir, exist_ok=True)
    
    output_file = os.path.join(output_dir, "concepts_analysis.json")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            "concepts": concepts,
            "concept_usages": concept_usages
        }, f, indent=2)
    print(f"分析结果已导出到: {output_file}")

def main():
    """主函数"""
    # 获取项目根目录
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # 测试文件路径
    test_file = os.path.join(root_dir, "test_files", "concepts_test.cpp")
    
    # 执行测试
    test_concepts_analysis(test_file)

if __name__ == "__main__":
    main() 