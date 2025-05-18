"""
查询存储在Neo4j数据库中的函数调用关系。
"""
import os
import sys
import argparse
from datetime import datetime

# 添加父级目录到Python路径以便导入src模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.neo4j_service import Neo4jService
from src.config.settings import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD

def query_function_calls(function_name=None, project_name="default", 
                         limit=10, show_callers=True, show_called=True, 
                         most_called=False, most_callers=False):
    """
    查询函数调用关系。
    
    Args:
        function_name: 要查询的函数名称（可选，如果不提供则根据其他参数查询）
        project_name: 项目名称
        limit: 结果限制数
        show_callers: 是否显示调用者
        show_called: 是否显示被调用的函数
        most_called: 是否查询最常被调用的函数
        most_callers: 是否查询调用最多函数的函数
    """
    # 连接到Neo4j数据库
    print(f"连接到Neo4j数据库...")
    neo4j_service = Neo4jService(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    
    # 查询最常被调用的函数
    if most_called:
        print(f"\n查询在项目 '{project_name}' 中最常被调用的函数（Top {limit}）:")
        with neo4j_service.driver.session() as session:
            result = session.run(
                """
                MATCH (caller:Function {project: $project})-[r:CALLS]->(function:Function {project: $project})
                WITH function, count(r) AS call_count
                ORDER BY call_count DESC
                LIMIT $limit
                RETURN function.name AS name, function.signature AS signature, 
                       function.file_path AS file_path, call_count
                """,
                project=project_name,
                limit=limit
            )
            
            for i, record in enumerate(result):
                print(f"{i+1}. {record['name']} - 被调用 {record['call_count']} 次")
                print(f"   文件: {record['file_path']}")
                if record['signature']:
                    print(f"   签名: {record['signature']}")
                print()
    
    # 查询调用最多函数的函数
    if most_callers:
        print(f"\n查询在项目 '{project_name}' 中调用最多函数的函数（Top {limit}）:")
        with neo4j_service.driver.session() as session:
            result = session.run(
                """
                MATCH (function:Function {project: $project})-[r:CALLS]->(called:Function {project: $project})
                WITH function, count(r) AS calls_count
                ORDER BY calls_count DESC
                LIMIT $limit
                RETURN function.name AS name, function.signature AS signature, 
                       function.file_path AS file_path, calls_count
                """,
                project=project_name,
                limit=limit
            )
            
            for i, record in enumerate(result):
                print(f"{i+1}. {record['name']} - 调用了 {record['calls_count']} 个函数")
                print(f"   文件: {record['file_path']}")
                if record['signature']:
                    print(f"   签名: {record['signature']}")
                print()
    
    # 查询特定函数的调用关系
    if function_name:
        # 查找函数的基本信息
        with neo4j_service.driver.session() as session:
            result = session.run(
                """
                MATCH (function:Function {name: $name, project: $project})
                RETURN function.name AS name, function.signature AS signature, 
                       function.file_path AS file_path, function.is_template AS is_template,
                       function.has_sfinae AS has_sfinae, function.is_metafunction AS is_metafunction,
                       function.has_variadic_templates AS has_variadic
                """,
                name=function_name,
                project=project_name
            )
            
            record = result.single()
            if not record:
                print(f"错误: 未找到函数 '{function_name}' 在项目 '{project_name}' 中")
                return
            
            print(f"\n函数信息: {record['name']}")
            print(f"文件: {record['file_path']}")
            if record['signature']:
                print(f"签名: {record['signature']}")
            
            # 显示模板信息
            if record['is_template']:
                print("模板: 是")
            if record['is_metafunction']:
                print("元函数: 是")
            if record['has_sfinae']:
                print("使用SFINAE: 是")
            if record['has_variadic']:
                print("变参模板: 是")
            
        # 查询调用此函数的函数（调用者）
        if show_callers:
            print(f"\n调用 '{function_name}' 的函数 (限制 {limit}):")
            with neo4j_service.driver.session() as session:
                result = session.run(
                    """
                    MATCH (caller:Function {project: $project})-[:CALLS]->(function:Function {name: $name, project: $project})
                    RETURN caller.name AS name, caller.file_path AS file_path
                    LIMIT $limit
                    """,
                    name=function_name,
                    project=project_name,
                    limit=limit
                )
                
                callers = list(result)
                if not callers:
                    print("  没有找到调用者")
                else:
                    for i, record in enumerate(callers):
                        print(f"  {i+1}. {record['name']} - {record['file_path']}")
        
        # 查询此函数调用的函数（被调用者）
        if show_called:
            print(f"\n'{function_name}' 调用的函数 (限制 {limit}):")
            with neo4j_service.driver.session() as session:
                result = session.run(
                    """
                    MATCH (function:Function {name: $name, project: $project})-[:CALLS]->(called:Function {project: $project})
                    RETURN called.name AS name, called.file_path AS file_path
                    LIMIT $limit
                    """,
                    name=function_name,
                    project=project_name,
                    limit=limit
                )
                
                called_funcs = list(result)
                if not called_funcs:
                    print("  没有找到被调用的函数")
                else:
                    for i, record in enumerate(called_funcs):
                        print(f"  {i+1}. {record['name']} - {record['file_path']}")

def main():
    """主函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='查询存储在Neo4j数据库中的函数调用关系。')
    parser.add_argument('--function', '-f', help='要查询的函数名称')
    parser.add_argument('--project', '-p', default='default', help='项目名称（默认: default）')
    parser.add_argument('--limit', '-l', type=int, default=10, help='结果限制数（默认: 10）')
    parser.add_argument('--callers', '-c', action='store_true', help='仅显示调用者')
    parser.add_argument('--called', '-d', action='store_true', help='仅显示被调用的函数')
    parser.add_argument('--most-called', '-m', action='store_true', help='查询最常被调用的函数')
    parser.add_argument('--most-callers', '-M', action='store_true', help='查询调用最多函数的函数')
    
    args = parser.parse_args()
    
    # 如果没有指定任何参数，则默认显示两者
    show_callers = args.callers or not (args.callers or args.called)
    show_called = args.called or not (args.callers or args.called)
    
    # 执行查询
    query_function_calls(
        function_name=args.function,
        project_name=args.project,
        limit=args.limit,
        show_callers=show_callers,
        show_called=show_called,
        most_called=args.most_called,
        most_callers=args.most_callers
    )
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 