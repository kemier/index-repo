"""
查找使用SFINAE技术的函数。
"""
import os
import sys
import argparse

# 添加父级目录到Python路径以便导入src模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.neo4j_service import Neo4jService
from src.config.settings import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD

def find_sfinae_functions(project_name="default", limit=20, technique=None):
    """
    查找使用SFINAE技术的函数。
    
    Args:
        project_name: 项目名称
        limit: 结果限制数
        technique: 特定的SFINAE技术
    """
    # 连接到Neo4j数据库
    print(f"连接到Neo4j数据库...")
    neo4j_service = Neo4jService(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    
    # 构建查询
    if technique:
        # 查询特定SFINAE技术
        print(f"\n查询在项目 '{project_name}' 中使用 '{technique}' 技术的函数:")
        with neo4j_service.driver.session() as session:
            result = session.run(
                """
                MATCH (function:Function {project: $project})
                WHERE function.has_sfinae = true AND $technique IN function.sfinae_techniques
                RETURN function.name AS name, function.signature AS signature, 
                       function.file_path AS file_path, function.sfinae_techniques AS techniques
                LIMIT $limit
                """,
                project=project_name,
                technique=technique,
                limit=limit
            )
            
            functions = list(result)
            if not functions:
                print(f"未找到使用 '{technique}' 技术的函数")
            else:
                for i, record in enumerate(functions):
                    print(f"{i+1}. {record['name']}")
                    print(f"   文件: {record['file_path']}")
                    if record['signature']:
                        print(f"   签名: {record['signature']}")
                    print(f"   SFINAE技术: {', '.join(record['techniques'])}")
                    print()
    else:
        # 查询任何SFINAE技术
        print(f"\n查询在项目 '{project_name}' 中使用SFINAE的函数:")
        with neo4j_service.driver.session() as session:
            result = session.run(
                """
                MATCH (function:Function {project: $project})
                WHERE function.has_sfinae = true
                RETURN function.name AS name, function.signature AS signature, 
                       function.file_path AS file_path, function.sfinae_techniques AS techniques
                LIMIT $limit
                """,
                project=project_name,
                limit=limit
            )
            
            functions = list(result)
            if not functions:
                print(f"未找到使用SFINAE的函数")
            else:
                for i, record in enumerate(functions):
                    print(f"{i+1}. {record['name']}")
                    print(f"   文件: {record['file_path']}")
                    if record['signature']:
                        print(f"   签名: {record['signature']}")
                    if record['techniques']:
                        print(f"   SFINAE技术: {', '.join(record['techniques'])}")
                    print()

def main():
    """主函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='查找使用SFINAE技术的函数。')
    parser.add_argument('--project', '-p', default='default', help='项目名称（默认: default）')
    parser.add_argument('--limit', '-l', type=int, default=20, help='结果限制数（默认: 20）')
    parser.add_argument('--technique', '-t', help='特定的SFINAE技术')
    
    args = parser.parse_args()
    
    # 执行查询
    find_sfinae_functions(
        project_name=args.project,
        limit=args.limit,
        technique=args.technique
    )
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 