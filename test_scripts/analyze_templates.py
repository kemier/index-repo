"""
分析C++模板元编程特性的脚本。
"""
import os
import sys

# 添加父级目录到Python路径以便导入src模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config.libclang_config import configure_libclang
from src.services.clang_analyzer_service import ClangAnalyzerService
from src.models.function_model import Function, CallGraph

def main():
    """分析test_files目录中的C++模板文件"""
    print("\n=== C++模板元编程特性分析 ===\n")
    
    # 配置libclang
    print("配置libclang...")
    configure_libclang()
    
    # 初始化分析器服务
    print("初始化分析器服务...")
    analyzer = ClangAnalyzerService()
    
    # 获取项目根目录
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # 分析目录中的所有测试文件
    test_dir = os.path.join(root_dir, "test_files")
    test_files = [
        os.path.join(test_dir, f) 
        for f in os.listdir(test_dir) 
        if f.endswith((".cpp", ".cc", ".h", ".hpp"))
    ]
    
    if not test_files:
        print(f"错误: {test_dir} 目录中没有找到C++文件")
        return
    
    print(f"发现 {len(test_files)} 个C++文件:")
    for file_path in test_files:
        print(f"  - {file_path}")
    
    # 为每个文件创建单独的分析
    all_results = {}
    for file_path in test_files:
        print(f"\n分析文件: {file_path}")
        call_graph = analyzer.analyze_file(file_path)
        all_results[file_path] = call_graph
        
        # 打印此文件的结果
        print(f"  发现 {len(call_graph.functions)} 个函数/类:")
        
        # 统计此文件中的特性
        metafunctions = [f for f in call_graph.functions.values() if f.is_metafunction]
        sfinae_functions = [f for f in call_graph.functions.values() if f.has_sfinae]
        variadic_templates = [f for f in call_graph.functions.values() if f.has_variadic_templates]
        
        print(f"  模板元函数: {len(metafunctions)}")
        print(f"  使用SFINAE的函数: {len(sfinae_functions)}")
        print(f"  变参模板: {len(variadic_templates)}")
        
        # 打印函数详情
        for func_name in sorted(call_graph.functions.keys()):
            func = call_graph.functions[func_name]
            print(f"    - {func_name}")
            
            # 打印模板信息
            if func.is_template:
                print(f"      模板: 是")
                if func.template_params:
                    print(f"      模板参数: {', '.join(func.template_params)}")
            
            # 打印元函数信息
            if func.is_metafunction:
                print(f"      元函数: 是 (类型: {func.metafunction_kind})")
            
            # 打印SFINAE信息
            if func.has_sfinae:
                print(f"      SFINAE: 是")
                if func.sfinae_techniques:
                    print(f"      SFINAE技术: {', '.join(func.sfinae_techniques)}")
            
            # 打印变参模板信息
            if func.has_variadic_templates:
                print(f"      变参模板: 是")
                if func.variadic_template_param:
                    print(f"      参数包: {func.variadic_template_param}")
    
    # 打印总结
    total_functions = sum(len(cg.functions) for cg in all_results.values())
    total_metafunctions = sum(len([f for f in cg.functions.values() if f.is_metafunction]) for cg in all_results.values())
    total_sfinae = sum(len([f for f in cg.functions.values() if f.has_sfinae]) for cg in all_results.values())
    total_variadic = sum(len([f for f in cg.functions.values() if f.has_variadic_templates]) for cg in all_results.values())
    
    print("\n=== 总结 ===")
    print(f"总共分析文件: {len(test_files)}")
    print(f"总函数/类数量: {total_functions}")
    print(f"模板元函数总数: {total_metafunctions}")
    print(f"使用SFINAE的函数总数: {total_sfinae}")
    print(f"变参模板总数: {total_variadic}")

if __name__ == "__main__":
    main() 