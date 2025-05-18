"""
使用自然语言描述查询函数调用链并显示函数体

这个脚本接受自然语言描述作为输入，使用LLM将其转换为Neo4j查询，
然后查询图数据库获取相关函数的调用链，最后显示函数体。
"""
import os
import sys
import argparse
import json
import re
import requests
import jieba
import jieba.analyse
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from neo4j import GraphDatabase

# 修复导入路径问题
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

try:
    from src.services.neo4j_service import Neo4jService
except ImportError:
    print("无法导入Neo4jService，创建简单版本...")
    # 简化版Neo4jService
    class Neo4jService:
        def __init__(self, uri="bolt://localhost:7688", username="neo4j", password="password"):
            self.uri = uri
            self.username = username
            self.password = password
            self.driver = GraphDatabase.driver(uri, auth=(username, password))
        
        def close(self):
            if self.driver:
                self.driver.close()
        
        def find_function(self, function_name, project_name):
            with self.driver.session() as session:
                result = session.run(
                    "MATCH (f:Function {name: $name, project: $project}) RETURN f",
                    name=function_name, project=project_name
                )
                record = result.single()
                if record:
                    return dict(record["f"])
                return None
        
        def find_callers(self, function_name, project_name, depth=1):
            with self.driver.session() as session:
                result = session.run(
                    f"MATCH (caller:Function)-[:CALLS*1..{depth}]->(f:Function {{name: $name, project: $project}}) RETURN DISTINCT caller",
                    name=function_name, project=project_name
                )
                return [dict(record["caller"]) for record in result]
        
        def find_callees(self, function_name, project_name, depth=1):
            with self.driver.session() as session:
                result = session.run(
                    f"MATCH (f:Function {{name: $name, project: $project}})-[:CALLS*1..{depth}]->(callee:Function) RETURN DISTINCT callee",
                    name=function_name, project=project_name
                )
                return [dict(record["callee"]) for record in result]

# 加载环境变量
load_dotenv()

# 使用固定的API密钥，或从环境变量加载
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "sk-96c022f633244358b6cf17f4e5c76a9f")

# 编程领域术语映射表（中英文映射）
programming_term_mapping = {
    "函数": ["function", "method", "procedure", "routine"],
    "调用": ["call", "invoke", "execute"],
    "类": ["class", "struct", "type"],
    "继承": ["inheritance", "extends", "derives", "inherits"],
    "模板": ["template", "generic"],
    "虚函数": ["virtual function", "virtual method", "override"],
    "接口": ["interface", "protocol", "abstract class"],
    "异常": ["exception", "error", "throw", "catch"],
    "线程": ["thread", "concurrency", "parallel"],
    "同步": ["synchronization", "mutex", "lock"],
    "异步": ["asynchronous", "async", "promise", "future"],
    "内存": ["memory", "allocation", "heap", "stack"],
    "指针": ["pointer", "reference", "address"],
    "容器": ["container", "collection", "vector", "list", "map"],
    "算法": ["algorithm", "sort", "search", "find"],
    "字符串": ["string", "text", "char"],
    "网络": ["network", "socket", "http", "request"],
    "文件": ["file", "stream", "io"],
    "数据库": ["database", "query", "sql"],
    "缓存": ["cache", "buffer", "temporary"]
}

def enhance_query_with_context(description: str, language: str = "zh") -> str:
    """
    增强查询，添加代码语境和同义词扩展
    
    Args:
        description: 原始查询描述
        language: 查询语言，'zh'为中文，'en'为英文
        
    Returns:
        增强后的查询
    """
    enhanced_terms = []
    
    # 中文查询处理
    if language == "zh":
        # 使用结巴分词提取关键词
        keywords = jieba.analyse.extract_tags(description, topK=5)
        
        # 查找每个关键词的编程术语映射
        for keyword in keywords:
            if keyword in programming_term_mapping:
                enhanced_terms.extend(programming_term_mapping[keyword])
    
    # 英文查询处理
    else:
        # 查找查询中可能出现的编程术语
        for term, synonyms in programming_term_mapping.items():
            for synonym in synonyms:
                if synonym.lower() in description.lower():
                    # 添加同义词，但避免重复
                    for syn in synonyms:
                        if syn.lower() != synonym.lower() and syn not in enhanced_terms:
                            enhanced_terms.append(syn)
    
    # 提取代码标识符
    code_terms = extract_code_terms(description)
    if code_terms:
        enhanced_terms.extend(code_terms)
    
    # 构建增强查询
    if enhanced_terms:
        if language == "zh":
            enhanced_query = f"{description} {' '.join(enhanced_terms)}"
        else:
            enhanced_query = f"{description} OR {' OR '.join(enhanced_terms)}"
    else:
        enhanced_query = description
        
    return enhanced_query

def extract_code_terms(text: str) -> List[str]:
    """
    从文本中提取可能的代码标识符
    
    Args:
        text: 输入文本
        
    Returns:
        代码标识符列表
    """
    # 匹配驼峰命名法
    camel_case = re.findall(r'[a-z][a-zA-Z0-9]*[A-Z][a-zA-Z0-9]*', text)
    
    # 匹配下划线命名法
    snake_case = re.findall(r'[a-z][a-z0-9]*_[a-z0-9]+(_[a-z0-9]+)*', text)
    
    # 匹配可能的函数调用
    func_calls = re.findall(r'[a-zA-Z][a-zA-Z0-9]*\(\)', text)
    
    # 合并结果并去除重复
    result = list(set(camel_case + snake_case + [f.rstrip('()') for f in func_calls]))
    return result

def generate_query_from_description(description, project_name, language="zh"):
    """
    使用LLM生成基于描述的Neo4j查询
    
    Args:
        description: 自然语言描述
        project_name: 项目名称
        language: 查询语言
    
    Returns:
        生成的Neo4j Cypher查询
    """
    # 增强查询
    enhanced_description = enhance_query_with_context(description, language)
    
    prompt = f"""
    我需要为图数据库Neo4j生成一个Cypher查询，在代码分析中查找特定函数。
    
    数据库结构:
    - 节点标签: Function
    - 节点属性: name, project, file_path, line_number, signature, namespace, is_defined, return_type, is_virtual, is_template
    - 关系: 
      - (Function)-[:CALLS]->(Function) 表示函数调用关系
      - (Function)-[:SPECIALIZES]->(Function) 表示模板特化关系
      - (Function)-[:OVERRIDES]->(Function) 表示方法覆盖关系
      - (Function)-[:HAS_CONTENT]->(TextContent) 连接到函数内容
    
    用户描述: {enhanced_description}
    项目名称: {project_name}
    
    请生成一个Cypher查询，找到与这个描述最相关的函数。考虑函数名称、签名以及其他属性中可能包含的关键词。
    必须返回完整的函数节点，而不仅仅是节点的属性。确保查询最后是RETURN f 而不是返回f的属性。
    
    你的回答应该只包含Cypher查询语句本身，不要有任何解释或其他文本。查询应该以`MATCH`开头并以`;`或不带分号结尾。
    """
    
    try:
        # 调用Deepseek API
        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": "你是一个专业的代码分析助手，精通Neo4j Cypher查询语言。"},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3,
            "max_tokens": 500
        }
        
        response = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers=headers,
            json=payload
        )
        
        # 检查请求是否成功
        response.raise_for_status()
        
        # 解析响应
        result = response.json()
        content = result["choices"][0]["message"]["content"].strip()
        
        # 尝试提取Cypher查询
        cypher_query = extract_cypher_query(content)
        
        # 确保查询是有效的并且返回节点而不是属性
        if not cypher_query or ("RETURN f" not in cypher_query and "return f" not in cypher_query.lower()):
            print("LLM生成的查询可能不返回完整节点，使用备选查询。")
            # 基于语言选择不同的备选查询
            if language == "zh":
                # 中文查询：使用分词和OR条件
                keywords = jieba.analyse.extract_tags(description, topK=3)
                keyword_conditions = " OR ".join([f"f.name CONTAINS '{kw}'" for kw in keywords])
                cypher_query = f"""
                MATCH (f:Function)
                WHERE f.project = '{project_name}' 
                  AND ({keyword_conditions})
                RETURN f
                ORDER BY size((f)--()) DESC
                LIMIT 10
                """
            else:
                # 英文查询：直接使用关键词匹配
                cypher_query = f"""
                MATCH (f:Function)
                WHERE f.project = '{project_name}' 
                  AND (f.name CONTAINS '{description}' OR f.name =~ '(?i).*{description}.*')
                RETURN f
                ORDER BY size((f)--()) DESC
                LIMIT 10
                """
        
        return cypher_query
        
    except Exception as e:
        print(f"生成查询时出错: {e}")
        # 如果API调用失败，使用基本查询模板
        return f"""
        MATCH (f:Function)
        WHERE f.project = '{project_name}' AND f.name CONTAINS '{description}'
        RETURN f
        LIMIT 10
        """

def extract_cypher_query(text):
    """
    从LLM响应文本中提取Cypher查询
    
    Args:
        text: LLM响应文本
    
    Returns:
        提取的Cypher查询或None
    """
    # 方法1：尝试找到代码块
    import re
    code_pattern = re.compile(r'```(?:cypher)?\s*((?:MATCH|match)[\s\S]*?)```')
    code_match = code_pattern.search(text)
    if code_match:
        return code_match.group(1).strip()
    
    # 方法2：尝试找到以MATCH开头的行
    match_pattern = re.compile(r'((?:MATCH|match)[^\n;]*(?:\n[^;]*)*)', re.MULTILINE)
    match_match = match_pattern.search(text)
    if match_match:
        return match_match.group(1).strip()
    
    # 方法3：如果以上方法都失败，尝试使用整个响应
    if text.strip().upper().startswith('MATCH'):
        return text.strip()
    
    return None

def get_function_body(file_path, line_number):
    """
    从文件中提取函数体
    
    Args:
        file_path: 文件路径
        line_number: 函数开始的行号
    
    Returns:
        函数体文本
    """
    if not os.path.exists(file_path):
        return f"文件未找到: {file_path}"
    
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as file:
            lines = file.readlines()
            
        if line_number <= 0:
            # 如果没有准确的行号，尝试搜索整个文件
            return "".join(lines)
            
        # 从行号开始，找到函数的完整定义
        result = []
        brace_count = 0
        found_opening_brace = False
        
        for i in range(line_number - 1, min(line_number + 100, len(lines))):
            if i < 0 or i >= len(lines):
                continue
                
            line = lines[i]
            result.append(line)
            
            # 计算花括号数量，确定函数体的范围
            for char in line:
                if char == '{':
                    found_opening_brace = True
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
            
            # 如果找到了函数的结束花括号，就返回结果
            if found_opening_brace and brace_count == 0:
                break
                
        return "".join(result)
    except Exception as e:
        return f"提取函数体时出错: {e}"

def find_related_functions(neo4j_service, function_name, project_name, direction="both", depth=1):
    """
    寻找与指定函数相关的函数（调用者和被调用者）
    
    Args:
        neo4j_service: Neo4j服务实例
        function_name: 函数名
        project_name: 项目名称
        direction: 关系方向，"callers", "callees"或"both"
        depth: 遍历深度
        
    Returns:
        相关函数的字典，按关系类型分组
    """
    related = {"callers": [], "callees": [], "specializes": [], "specialized_by": [], "overrides": [], "overridden_by": []}
    
    if direction in ["callers", "both"]:
        callers = neo4j_service.find_callers(function_name, project_name, depth)
        related["callers"] = [{"name": f.get("name", ""), "file_path": f.get("file_path", "")} for f in callers]
    
    if direction in ["callees", "both"]:
        callees = neo4j_service.find_callees(function_name, project_name, depth)
        related["callees"] = [{"name": f.get("name", ""), "file_path": f.get("file_path", "")} for f in callees]
    
    # 查找模板特化关系
    with neo4j_service.driver.session() as session:
        # 找出此函数特化的模板
        specializes = session.run("""
        MATCH (f:Function {name: $name, project: $project})-[:SPECIALIZES]->(template:Function)
        RETURN template
        """, name=function_name, project=project_name)
        related["specializes"] = [dict(record["template"]) for record in specializes]
        
        # 找出特化此模板的函数
        if related["specializes"]:
            # 如果这个函数特化了某个模板，它自身就不是模板
            pass
        else:
            # 检查是否有特化此函数的其他函数
            specialized_by = session.run("""
            MATCH (spec:Function)-[:SPECIALIZES]->(f:Function {name: $name, project: $project})
            RETURN spec
            """, name=function_name, project=project_name)
            related["specialized_by"] = [dict(record["spec"]) for record in specialized_by]
        
        # 找出此函数覆盖的基类方法
        overrides = session.run("""
        MATCH (f:Function {name: $name, project: $project})-[:OVERRIDES]->(base:Function)
        RETURN base
        """, name=function_name, project=project_name)
        related["overrides"] = [dict(record["base"]) for record in overrides]
        
        # 找出覆盖此函数的派生类方法
        overridden_by = session.run("""
        MATCH (derived:Function)-[:OVERRIDES]->(f:Function {name: $name, project: $project})
        RETURN derived
        """, name=function_name, project=project_name)
        related["overridden_by"] = [dict(record["derived"]) for record in overridden_by]
    
    return related

def semantic_search(neo4j_service, description, project_name, language="zh", limit=10):
    """
    语义搜索函数
    
    Args:
        neo4j_service: Neo4j服务实例
        description: 查询描述
        project_name: 项目名称
        language: 查询语言
        limit: 结果数量限制
        
    Returns:
        相关函数列表
    """
    # 增强查询
    enhanced_query = enhance_query_with_context(description, language)
    
    # 提取关键词
    if language == "zh":
        keywords = jieba.analyse.extract_tags(enhanced_query, topK=5)
    else:
        # 简单英文分词
        keywords = [w.strip().lower() for w in enhanced_query.split() if len(w.strip()) > 2]
    
    # 构建查询条件
    keyword_conditions = []
    for kw in keywords:
        keyword_conditions.append(f"f.name CONTAINS '{kw}'")
        keyword_conditions.append(f"f.signature CONTAINS '{kw}'")
    
    keyword_query = " OR ".join(keyword_conditions)
    
    # 执行查询
    with neo4j_service.driver.session() as session:
        cypher = f"""
        MATCH (f:Function)
        WHERE f.project = $project AND ({keyword_query})
        WITH f, size((f)--()) as connections
        RETURN f, connections
        ORDER BY connections DESC
        LIMIT {limit}
        """
        
        results = session.run(cypher, project=project_name)
        return [dict(record["f"], relevance=record["connections"]) for record in results]

def analyze_call_chain(description, project_name, neo4j_uri, neo4j_user, neo4j_password, language="zh"):
    """
    基于描述分析函数调用链
    
    Args:
        description: 自然语言描述
        project_name: 项目名称
        neo4j_uri: Neo4j数据库URI
        neo4j_user: Neo4j用户名
        neo4j_password: Neo4j密码
        language: 查询语言，'zh'为中文，'en'为英文
    """
    # 连接到Neo4j
    neo4j_service = Neo4jService(neo4j_uri, neo4j_user, neo4j_password)
    
    # 1. 生成并执行查询
    cypher_query = generate_query_from_description(description, project_name, language)
    print(f"执行查询: {cypher_query}")
    
    # 2. 先尝试LLM生成的查询
    with neo4j_service.driver.session() as session:
        result = session.run(cypher_query)
        records = list(result)
        
        if not records:
            print("未找到匹配函数，尝试语义搜索...")
            # 3. 如果未找到结果，尝试语义搜索
            semantic_results = semantic_search(neo4j_service, description, project_name, language)
            
            if semantic_results:
                print(f"通过语义搜索找到 {len(semantic_results)} 个相关函数:")
                for i, func in enumerate(semantic_results):
                    print(f"{i+1}. {func['name']} (相关度: {func.get('relevance', 0)})")
                    if func.get('file_path'):
                        print(f"   文件: {func['file_path']}, 行号: {func.get('line_number', 0)}")
                    if func.get('signature'):
                        print(f"   签名: {func['signature']}")
                
                if len(semantic_results) > 1:
                    selected = input("请选择要分析的函数编号 (直接回车选择第一个): ")
                    if selected.strip() and selected.isdigit() and 1 <= int(selected) <= len(semantic_results):
                        func = semantic_results[int(selected) - 1]
                    else:
                        func = semantic_results[0]
                else:
                    func = semantic_results[0]
            else:
                print("语义搜索也未找到结果。")
                return
        else:
            func = records[0]["f"]
            print(f"找到函数: {func['name']}")
            if func.get('file_path'):
                print(f"文件: {func['file_path']}, 行号: {func.get('line_number', 0)}")
            if func.get('signature'):
                print(f"签名: {func['signature']}")
    
    # 显示函数的高级C++特性
    if func.get('is_virtual'):
        print("特性: 虚函数")
    if func.get('is_template'):
        print("特性: 模板函数")
    
    # 4. 分析函数关系
    function_name = func["name"]
    print("\n函数关系分析:")
    related = find_related_functions(neo4j_service, function_name, project_name, "both", 1)
    
    # 显示调用关系
    if related["callers"]:
        print("\n调用此函数的函数:")
        for caller in related["callers"]:
            print(f"  - {caller['name']} ({caller.get('file_path', '')})")
    else:
        print("\n无调用此函数的函数")
        
    if related["callees"]:
        print("\n此函数调用的函数:")
        for callee in related["callees"]:
            print(f"  - {callee['name']} ({callee.get('file_path', '')})")
    else:
        print("\n此函数未调用其他函数")
    
    # 显示模板和继承关系
    if related["specializes"]:
        print("\n此函数特化自:")
        for template in related["specializes"]:
            print(f"  - {template['name']} ({template.get('file_path', '')})")
    
    if related["specialized_by"]:
        print("\n此模板函数的特化版本:")
        for spec in related["specialized_by"]:
            print(f"  - {spec['name']} ({spec.get('file_path', '')})")
    
    if related["overrides"]:
        print("\n此函数覆盖的基类方法:")
        for base in related["overrides"]:
            print(f"  - {base['name']} ({base.get('file_path', '')})")
    
    if related["overridden_by"]:
        print("\n覆盖此函数的派生类方法:")
        for derived in related["overridden_by"]:
            print(f"  - {derived['name']} ({derived.get('file_path', '')})")
    
    # 5. 获取并显示函数体
    print("\n函数体:")
    if func.get("file_path") and func.get("line_number"):
        body = get_function_body(func["file_path"], func["line_number"])
        # 查看是否有存储在数据库中的函数体
        func_details = neo4j_service.find_function(function_name, project_name)
        if func_details and "body" in func_details and func_details["body"]:
            db_body = func_details["body"]
            if len(db_body) > len(body):
                body = db_body
                
        print(body)
    else:
        print("无法获取函数体 - 缺少文件路径或行号信息")
    
    # 关闭Neo4j连接
    neo4j_service.close()


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="使用自然语言描述查询代码")
    parser.add_argument("description", help="函数功能描述")
    parser.add_argument("--project", default="default", help="项目名称")
    parser.add_argument("--neo4j-uri", default="bolt://localhost:7688", help="Neo4j URI")
    parser.add_argument("--neo4j-user", default="neo4j", help="Neo4j用户名")
    parser.add_argument("--neo4j-password", default="password", help="Neo4j密码")
    parser.add_argument("--language", choices=["zh", "en"], default="zh", help="查询语言 (zh: 中文, en: 英文)")
    
    args = parser.parse_args()
    
    # 使用环境变量覆盖默认值
    neo4j_uri = os.getenv("NEO4J_URI", args.neo4j_uri)
    neo4j_user = os.getenv("NEO4J_USER", args.neo4j_user)
    neo4j_password = os.getenv("NEO4J_PASSWORD", args.neo4j_password)
    
    analyze_call_chain(
        args.description,
        args.project,
        neo4j_uri,
        neo4j_user,
        neo4j_password,
        args.language
    )


if __name__ == "__main__":
    main() 