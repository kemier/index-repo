"""
增量索引C++代码，只处理自上次索引以来已更改的文件。
"""
import os
import sys
import argparse
from datetime import datetime

# 添加父级目录到Python路径以便导入src模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config.libclang_config import configure_libclang
from src.services.clang_analyzer_service import ClangAnalyzerService
from src.services.neo4j_service import Neo4jService
from src.models.function_model import Function, CallGraph
from src.config.settings import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD

def incremental_index(directory_path, project_name, file_extensions=None, max_workers=4):
    """
    增量索引目录中的C++代码文件，只处理自上次索引以来已更改的文件。
    
    Args:
        directory_path: 要索引的目录路径
        project_name: 项目名称（用于Neo4j索引）
        file_extensions: 要索引的文件扩展名列表
        max_workers: 最大并行工作进程数
    """
    # 配置libclang
    print(f"配置libclang...")
    configure_libclang()
    
    # 初始化分析器服务
    print(f"初始化分析器服务...")
    analyzer = ClangAnalyzerService()
    
    # 如果没有指定文件扩展名，使用默认的C/C++扩展名
    if file_extensions is None:
        file_extensions = ['.c', '.cpp', '.cxx', '.cc', '.h', '.hpp', '.hxx', '.hh']
    
    # 初始化Neo4j服务
    print(f"连接到Neo4j数据库...")
    neo4j_service = Neo4jService(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    
    # 增量分析目录
    print(f"开始增量分析目录: {directory_path}")
    start_time = datetime.now()
    
    call_graph, changed_files = analyzer.incremental_analyze_directory(
        directory_path=directory_path,
        project_name=project_name,
        file_extensions=file_extensions,
        max_workers=max_workers
    )
    
    # 计算分析时间
    analysis_time = (datetime.now() - start_time).total_seconds()
    
    # 输出基本统计信息
    print(f"\n增量分析完成! 用时: {analysis_time:.2f} 秒")
    print(f"处理了 {len(changed_files)} 个已更改的文件")
    print(f"发现 {len(call_graph.functions)} 个已更改的函数:")
    
    # 统计高级功能
    metafunctions = [f for f in call_graph.functions.values() if f.is_metafunction]
    sfinae_functions = [f for f in call_graph.functions.values() if f.has_sfinae]
    variadic_templates = [f for f in call_graph.functions.values() if f.has_variadic_templates]
    template_functions = [f for f in call_graph.functions.values() if f.is_template]
    
    print(f"模板函数: {len(template_functions)}")
    print(f"模板元函数: {len(metafunctions)}")
    print(f"使用SFINAE的函数: {len(sfinae_functions)}")
    print(f"变参模板: {len(variadic_templates)}")
    
    # 如果没有更改，则不需要更新Neo4j
    if not changed_files:
        print("没有发现需要更新的文件，不需要更新Neo4j数据库。")
        return call_graph
    
    # 将数据存储到Neo4j
    print(f"\n更新Neo4j数据库...")
    store_start_time = datetime.now()
    
    # 首先从数据库中删除已更改文件中的函数
    for file_path in changed_files:
        neo4j_service.delete_functions_by_file(file_path, project_name)
    
    # 然后存储新的函数数据
    neo4j_service.index_call_graph(call_graph, project_name)
    
    # 计算存储时间
    store_time = (datetime.now() - store_start_time).total_seconds()
    print(f"数据更新完成! 用时: {store_time:.2f} 秒")
    
    return call_graph

def main():
    """主函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='增量索引C++代码，只处理自上次索引以来已更改的文件。')
    parser.add_argument('directory', help='要索引的目录路径')
    parser.add_argument('--project', '-p', default='default', help='项目名称（默认: default）')
    parser.add_argument('--workers', '-w', type=int, default=4, help='最大并行工作进程数（默认: 4）')
    parser.add_argument('--extensions', '-e', nargs='+', help='要索引的文件扩展名列表')
    
    args = parser.parse_args()
    
    # 检查目录是否存在
    if not os.path.isdir(args.directory):
        print(f"错误: 目录 '{args.directory}' 不存在")
        return 1
    
    # 增量索引目录
    call_graph = incremental_index(
        directory_path=args.directory,
        project_name=args.project,
        file_extensions=args.extensions,
        max_workers=args.workers
    )
    
    # 输出索引摘要
    print("\n=== 增量索引摘要 ===")
    print(f"项目名称: {args.project}")
    print(f"更新的函数总数: {len(call_graph.functions)}")
    print(f"新增的缺失函数引用: {len(call_graph.missing_functions)}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 