"""
Search service for finding functions in codebase
"""
import os
import re
from typing import List, Dict, Set, Optional, Tuple, Any

from src.services.neo4j_service import Neo4jService
from src.config.settings import DEFAULT_FILE_PATTERNS


class SearchService:
    """Service for searching functions in codebase"""
    
    def __init__(self, neo4j_service=None, neo4j_uri=None, neo4j_user=None, neo4j_password=None):
        """
        Initialize the search service.
        
        Args:
            neo4j_service: Neo4jService instance to use (optional)
            neo4j_uri: Neo4j URI (only used if neo4j_service is not provided)
            neo4j_user: Neo4j username (only used if neo4j_service is not provided)
            neo4j_password: Neo4j password (only used if neo4j_service is not provided)
        """
        # Initialize with an existing service or create a new one
        if neo4j_service:
            self.neo4j_service = neo4j_service
        else:
            from src.services.neo4j_service import Neo4jService
            self.neo4j_service = Neo4jService(
                uri=neo4j_uri,
                username=neo4j_user,
                password=neo4j_password
            )
    
    def search_functions(self, function_names: List[str], search_path: str, pattern: str = DEFAULT_FILE_PATTERNS) -> Dict[str, List[str]]:
        """
        Search for functions in a codebase
        
        Args:
            function_names: List of function names to search for
            search_path: Path to search in
            pattern: File pattern to search (comma-separated)
            
        Returns:
            Dict mapping function names to lists of file locations
        """
        if not os.path.exists(search_path):
            raise FileNotFoundError(f"Path {search_path} not found")
        
        results = {func: [] for func in function_names}
        file_patterns = pattern.split(',')
        
        # Compile regex patterns for each function
        function_patterns = {}
        for func in function_names:
            # Match function definitions and declarations
            # This handles various styles:
            # - type func(params) { ... }
            # - type func(params);
            # - type* func(params)
            # - type (*func)(params)
            pattern = rf'(^|\s|\*|\()({re.escape(func)})\s*\('
            function_patterns[func] = re.compile(pattern)
        
        if os.path.isfile(search_path):
            self._search_file(search_path, function_patterns, results)
        else:
            for root, _, files in os.walk(search_path):
                for file in files:
                    if any(self._matches_pattern(file, p) for p in file_patterns):
                        file_path = os.path.join(root, file)
                        self._search_file(file_path, function_patterns, results)
                        
        return results
    
    def find_callers(self, function_name: str, project_name: str, depth: int = 1) -> List[str]:
        """Find functions that call the specified function.
        
        Args:
            function_name: Name of the function to find callers for
            project_name: Project to search in
            depth: Depth of caller relationships to traverse
            
        Returns:
            List of caller function names
        """
        callers = self.neo4j_service.find_callers(function_name, project_name, depth)
        return [caller.get("name", "") for caller in callers]
    
    def find_callees(self, function_name: str, project_name: str, depth: int = 1) -> List[str]:
        """Find functions called by the specified function.
        
        Args:
            function_name: Name of the function to find callees for
            project_name: Project to search in
            depth: Depth of callee relationships to traverse
            
        Returns:
            List of callee function names
        """
        callees = self.neo4j_service.find_callees(function_name, project_name, depth)
        return [callee.get("name", "") for callee in callees]
    
    def generate_function_stubs(self, function_names: List[str]) -> str:
        """
        Generate stubs for missing functions
        
        Args:
            function_names: List of function names to generate stubs for
            
        Returns:
            String containing C/C++ code with stub implementations
        """
        header = """/**
 * Auto-generated stubs for missing functions
 */

#ifndef MISSING_FUNCTIONS_H
#define MISSING_FUNCTIONS_H

#ifdef __cplusplus
extern "C" {
#endif

"""
        
        footer = """
#ifdef __cplusplus
}
#endif

#endif /* MISSING_FUNCTIONS_H */
"""
        
        stubs = []
        for func in function_names:
            # Create a basic stub that returns 0 or void
            stubs.append(f"""
/**
 * Stub implementation for missing function: {func}
 */
int {func}(void) {{
    // TODO: Implement this function
    return 0;
}}""")
        
        return header + "\n".join(stubs) + footer
    
    def _search_file(self, file_path: str, patterns: Dict[str, re.Pattern], results: Dict[str, List[str]]) -> None:
        """
        Search for function patterns in a file
        
        Args:
            file_path: Path to file to search
            patterns: Dictionary mapping function names to regex patterns
            results: Dictionary to update with search results
        """
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
            for func, pattern in patterns.items():
                matches = pattern.finditer(content)
                for match in matches:
                    # Get line number of match
                    line_num = content[:match.start()].count('\n') + 1
                    results[func].append(f"{file_path}:{line_num}")
        except Exception as e:
            print(f"Error searching file {file_path}: {e}")
    
    def _matches_pattern(self, filename: str, pattern: str) -> bool:
        """Check if a filename matches a glob pattern"""
        pattern = pattern.replace("*", ".*").replace(".", "\\.")
        pattern = f"^{pattern}$"
        return bool(re.match(pattern, filename))
    
    def _process_query(self, query: str, lang: str = "en") -> List[str]:
        """
        Process a natural language query into keywords.
        
        Args:
            query: The natural language query
            lang: Language of the query ('en' for English, 'zh' for Chinese)
            
        Returns:
            List of processed keywords
        """
        # Convert to lowercase
        query = query.lower()
        
        # Process based on language
        if lang == "zh":
            # Chinese text segmentation using jieba
            try:
                import jieba
                
                # Add programming domain terms to jieba dictionary
                self._add_programming_terms_to_jieba()
                
                # Perform segmentation
                words = list(jieba.cut(query))
                
                # Filter stopwords
                stopwords = self._get_chinese_stopwords()
                words = [w for w in words if w.strip() and w not in stopwords]
                
                # Map common Chinese programming terms to English
                words = self._map_chinese_to_english_terms(words)
                
                return words
            except ImportError:
                print("Warning: jieba package not found. Using basic character splitting for Chinese.")
                # Basic fallback: split by common punctuation
                for char in "，。！？；：""''（）【】《》":
                    query = query.replace(char, " ")
                words = query.split()
                return words
        else:
            # English processing
            # Remove punctuation
            for char in ",.!?;:\"'()[]{}":
                query = query.replace(char, " ")
            
            # Split into words
            words = query.split()
            
            # Filter stopwords
            stopwords = self._get_english_stopwords()
            words = [w for w in words if w.strip() and w not in stopwords]
            
            # Map programming domain synonyms
            words = self._map_programming_synonyms(words)
            
            return words
    
    def _add_programming_terms_to_jieba(self):
        """Add programming domain terms to jieba dictionary."""
        try:
            import jieba
            
            # Common programming terms in Chinese
            terms = [
                ("函数调用", 10000),
                ("类继承", 10000),
                ("模板特化", 10000),
                ("虚函数", 10000),
                ("接口", 10000),
                ("实现", 10000),
                ("编译", 10000),
                ("构造函数", 10000),
                ("析构函数", 10000),
                ("命名空间", 10000),
                ("模板参数", 10000),
                ("异步", 10000),
                ("同步", 10000),
                ("并发", 10000),
                ("线程安全", 10000),
                ("内存管理", 10000),
                ("智能指针", 10000),
                ("容器", 10000),
                ("算法", 10000),
                ("迭代器", 10000),
                ("错误处理", 10000),
                ("异常", 10000),
                ("调试", 10000),
                ("性能优化", 10000),
                ("代码复用", 10000),
                ("设计模式", 10000),
                # Add more terms as needed
            ]
            
            for term, weight in terms:
                jieba.add_word(term, weight)
                
        except ImportError:
            pass
    
    def _get_chinese_stopwords(self) -> Set[str]:
        """Get Chinese stopwords."""
        return {
            "的", "了", "和", "是", "就", "都", "而", "及", "与", "这", "那", "有", "在",
            "中", "为", "对", "或", "所", "因", "于", "由", "上", "下", "之", "以", "到",
            "从", "但", "却", "并", "等", "做", "来", "去", "把", "将", "能", "要", "会",
            "我", "你", "他", "她", "它", "们", "个", "某", "该"
        }
    
    def _get_english_stopwords(self) -> Set[str]:
        """Get English stopwords."""
        return {
            "a", "an", "the", "and", "or", "but", "if", "then", "else", "when",
            "of", "to", "in", "for", "with", "on", "at", "from", "by", "about",
            "as", "into", "like", "through", "after", "over", "between", "out",
            "against", "during", "without", "before", "under", "around", "among",
            "is", "are", "was", "were", "be", "been", "being", "have", "has", "had",
            "do", "does", "did", "will", "would", "shall", "should", "can", "could",
            "may", "might", "must", "that", "which", "who", "whom", "whose", "what",
            "where", "when", "why", "how", "all", "any", "both", "each", "few", "more",
            "most", "other", "some", "such", "no", "nor", "not", "only", "own", "same",
            "so", "than", "too", "very", "s", "t", "can", "will", "just", "don", "don't",
            "should", "now", "I", "you", "he", "she", "we", "they", "it", "this", "these",
            "those", "their", "I'm", "you're", "he's", "she's", "we're", "they're", "I've",
            "you've", "we've", "they've", "I'd", "you'd", "he'd", "she'd", "we'd", "they'd",
            "I'll", "you'll", "he'll", "she'll", "we'll", "they'll"
        }
    
    def _map_chinese_to_english_terms(self, words: List[str]) -> List[str]:
        """Map Chinese programming terms to English equivalents."""
        term_mapping = {
            "函数": "function",
            "调用": "call",
            "类": "class",
            "继承": "inheritance",
            "模板": "template",
            "特化": "specialization",
            "虚函数": "virtual function",
            "接口": "interface",
            "实现": "implementation",
            "编译": "compile",
            "构造函数": "constructor",
            "析构函数": "destructor",
            "命名空间": "namespace",
            "参数": "parameter",
            "异步": "asynchronous",
            "同步": "synchronous",
            "并发": "concurrent",
            "线程安全": "thread safe",
            "内存管理": "memory management",
            "智能指针": "smart pointer",
            "容器": "container",
            "算法": "algorithm",
            "迭代器": "iterator",
            "错误处理": "error handling",
            "异常": "exception",
            "调试": "debug",
            "性能优化": "performance optimization",
            "代码复用": "code reuse",
            "设计模式": "design pattern",
            "指针": "pointer",
            "引用": "reference",
            "内存": "memory",
            "线程": "thread",
            "进程": "process",
            "互斥": "mutex",
            "锁": "lock",
            "队列": "queue",
            "栈": "stack",
            "堆": "heap",
            "字符串": "string",
            "数组": "array",
            "向量": "vector",
            "映射": "map",
            "集合": "set",
            "列表": "list",
            "树": "tree",
            "图": "graph",
            "文件": "file",
            "输入": "input",
            "输出": "output",
            "网络": "network",
            "套接字": "socket",
            "协议": "protocol",
            "服务器": "server",
            "客户端": "client",
            "数据库": "database",
            "查询": "query",
            "事务": "transaction",
            "索引": "index",
            "缓存": "cache",
            "算法": "algorithm",
            "排序": "sort",
            "搜索": "search",
            "递归": "recursion",
            "迭代": "iteration",
            "回调": "callback",
            "事件": "event",
            "监听器": "listener",
            "消息": "message",
            "队列": "queue"
        }
        
        result = []
        for word in words:
            if word in term_mapping:
                result.append(term_mapping[word])
            else:
                result.append(word)
        
        return result
    
    def _map_programming_synonyms(self, words: List[str]) -> List[str]:
        """Map programming domain synonyms to canonical terms."""
        # Map common programming synonyms
        synonym_mapping = {
            "invoke": "call",
            "calling": "call",
            "calls": "call",
            "called": "call",
            "invokes": "call",
            "invoked": "call",
            "invoke": "call",
            "executed": "execute",
            "executes": "execute",
            "run": "execute",
            "runs": "execute",
            "running": "execute",
            "ran": "execute",
            "instantiates": "instantiate",
            "instantiated": "instantiate",
            "creates": "create",
            "created": "create",
            "initializes": "initialize",
            "initialized": "initialize",
            "terminates": "terminate",
            "terminated": "terminate",
            "destroys": "destroy",
            "destroyed": "destroy",
            "implementing": "implement",
            "implements": "implement",
            "implemented": "implement",
            "extends": "inherit",
            "inherits": "inherit",
            "inherited": "inherit",
            "derives": "inherit",
            "derived": "inherit",
            "subclasses": "inherit",
            "subclassed": "inherit",
            "specializes": "specialize",
            "specialized": "specialize",
            "overrides": "override",
            "overridden": "override",
            "overloads": "overload",
            "overloaded": "overload",
            "processes": "process",
            "processed": "process",
            "handles": "handle",
            "handled": "handle",
            "managing": "manage",
            "manages": "manage",
            "managed": "manage",
            "allocates": "allocate",
            "allocated": "allocate",
            "deallocates": "deallocate",
            "deallocated": "deallocate",
            "frees": "free",
            "freed": "free",
            "releases": "release",
            "released": "release",
            "locks": "lock",
            "locked": "lock",
            "unlocks": "unlock",
            "unlocked": "unlock",
            "synchronizes": "synchronize",
            "synchronized": "synchronize",
            "reads": "read",
            "reading": "read",
            "writes": "write",
            "writing": "write",
            "wrote": "write",
            "renders": "render",
            "rendered": "render",
            "draws": "draw",
            "drawing": "draw",
            "drew": "draw",
            "drawn": "draw",
            "computes": "compute",
            "computed": "compute",
            "calculates": "calculate",
            "calculated": "calculate",
            "validates": "validate",
            "validated": "validate",
            "verifies": "verify",
            "verified": "verify",
            "checks": "check",
            "checked": "check",
            "transforms": "transform",
            "transformed": "transform",
            "converts": "convert",
            "converted": "convert",
            "formats": "format",
            "formatted": "format",
            "parses": "parse",
            "parsed": "parse",
            "serializes": "serialize",
            "serialized": "serialize",
            "deserializes": "deserialize",
            "deserialized": "deserialize",
            "encodes": "encode",
            "encoded": "encode",
            "decodes": "decode",
            "decoded": "decode",
            "encrypts": "encrypt",
            "encrypted": "encrypt",
            "decrypts": "decrypt",
            "decrypted": "decrypt",
            "compresses": "compress",
            "compressed": "compress",
            "decompresses": "decompress",
            "decompressed": "decompress",
            "loads": "load",
            "loaded": "load",
            "saves": "save",
            "saved": "save",
            "stores": "store",
            "stored": "store",
            "retrieves": "retrieve",
            "retrieved": "retrieve",
            "fetches": "fetch",
            "fetched": "fetch",
            "queries": "query",
            "queried": "query",
            "searches": "search",
            "searched": "search",
            "finds": "find",
            "found": "find",
            "filters": "filter",
            "filtered": "filter",
            "sorts": "sort",
            "sorted": "sort",
            "merges": "merge",
            "merged": "merge",
            "splits": "split",
            "splitted": "split",
            "joins": "join",
            "joined": "join",
            "concatenates": "concatenate",
            "concatenated": "concatenate",
            "appends": "append",
            "appended": "append",
            "inserts": "insert",
            "inserted": "insert",
            "removes": "remove",
            "removed": "remove",
            "deletes": "delete",
            "deleted": "delete",
            "updates": "update",
            "updated": "update",
            "modifies": "modify",
            "modified": "modify",
            "changes": "change",
            "changed": "change",
            "sends": "send",
            "sent": "send",
            "receives": "receive",
            "received": "receive",
            "transmits": "transmit",
            "transmitted": "transmit",
            "broadcasts": "broadcast",
            "broadcasted": "broadcast",
            "publishes": "publish",
            "published": "publish",
            "subscribes": "subscribe",
            "subscribed": "subscribe",
            "notifies": "notify",
            "notified": "notify",
            "signals": "signal",
            "signalled": "signal",
            "triggers": "trigger",
            "triggered": "trigger",
            "logs": "log",
            "logged": "log",
            "prints": "print",
            "printed": "print",
            "displays": "display",
            "displayed": "display",
            "shows": "show",
            "shown": "show",
            "hides": "hide",
            "hidden": "hide",
            "enables": "enable",
            "enabled": "enable",
            "disables": "disable",
            "disabled": "disable",
            "activates": "activate",
            "activated": "activate",
            "deactivates": "deactivate",
            "deactivated": "deactivate",
            "starts": "start",
            "started": "start",
            "stops": "stop",
            "stopped": "stop",
            "resumes": "resume",
            "resumed": "resume",
            "pauses": "pause",
            "paused": "pause",
            "cancels": "cancel",
            "cancelled": "cancel",
            "aborts": "abort",
            "aborted": "abort",
            "retries": "retry",
            "retried": "retry",
            "skips": "skip",
            "skipped": "skip",
            "schedules": "schedule",
            "scheduled": "schedule",
            "dispatches": "dispatch",
            "dispatched": "dispatch",
            "delegates": "delegate",
            "delegated": "delegate",
            "registers": "register",
            "registered": "register",
            "unregisters": "unregister",
            "unregistered": "unregister",
            "commits": "commit",
            "committed": "commit",
            "rollbacks": "rollback",
            "rolled back": "rollback",
            "opens": "open",
            "opened": "open",
            "closes": "close",
            "closed": "close",
            "connects": "connect",
            "connected": "connect",
            "disconnects": "disconnect",
            "disconnected": "disconnect",
            "attaches": "attach",
            "attached": "attach",
            "detaches": "detach",
            "detached": "detach",
            "mounts": "mount",
            "mounted": "mount",
            "unmounts": "unmount",
            "unmounted": "unmount",
            "binds": "bind",
            "bound": "bind",
            "unbinds": "unbind",
            "unbound": "unbind"
        }
        
        result = []
        for word in words:
            if word in synonym_mapping:
                result.append(synonym_mapping[word])
            else:
                result.append(word)
        
        return result
    
    def search_by_description(self, description: str, project_name: str = "default", 
                           limit: int = 10, lang: str = "en") -> List[Dict[str, Any]]:
        """
        Search for functions matching a natural language description.
        
        Args:
            description: Natural language description of the function
            project_name: Project to search in
            limit: Maximum number of results to return
            lang: Language of the description ('en' for English, 'zh' for Chinese)
            
        Returns:
            List of matching function data with relevance scores
        """
        # Process the description into keywords
        keywords = self._process_query(description, lang)
        
        if not keywords:
            return []
            
        with self.neo4j_service.driver.session() as session:
            # Build a Cypher query to search for functions matching any of the keywords
            keyword_conditions = []
            for keyword in keywords:
                # Escape special characters for regex pattern
                escaped_keyword = re.escape(keyword)
                # For each keyword, check several fields
                keyword_conditions.append(f"f.name =~ '(?i).*{escaped_keyword}.*'")
                keyword_conditions.append(f"f.signature =~ '(?i).*{escaped_keyword}.*'")
                keyword_conditions.append(f"f.namespace =~ '(?i).*{escaped_keyword}.*'")
                keyword_conditions.append(f"exists(tc.content) AND tc.content =~ '(?i).*{escaped_keyword}.*'")
            
            # Join conditions with OR
            combined_condition = " OR ".join(keyword_conditions)
            
            # Build and execute the query
            query = f"""
            MATCH (f:Function {{project: $project}})
            OPTIONAL MATCH (f)-[:HAS_CONTENT]->(tc:TextContent)
            WHERE {combined_condition}
            RETURN DISTINCT f, tc.content as body
            LIMIT $limit
            """
            
            result = session.run(query, project=project_name, limit=limit)
            
            # Process results
            functions = []
            for record in result:
                function = dict(record["f"])
                if record["body"]:
                    function["body"] = record["body"]
                functions.append(function)
            
            # Score and rank results
            scored_functions = []
            for function in functions:
                # Calculate relevance score
                score = 0
                matched_tokens = []
                
                for keyword in keywords:
                    # Check name (highest weight)
                    if keyword in function["name"].lower():
                        score += 10
                        matched_tokens.append(keyword)
                    
                    # Check signature
                    if "signature" in function and function["signature"] and keyword in function["signature"].lower():
                        score += 5
                        if keyword not in matched_tokens:
                            matched_tokens.append(keyword)
                    
                    # Check namespace
                    if "namespace" in function and function["namespace"] and keyword in function["namespace"].lower():
                        score += 3
                        if keyword not in matched_tokens:
                            matched_tokens.append(keyword)
                    
                    # Check function body (lowest weight but still important)
                    if "body" in function and function["body"] and keyword in function["body"].lower():
                        score += 2
                        if keyword not in matched_tokens:
                            matched_tokens.append(keyword)
                
                # Add score and matched tokens to function data
                function["relevance"] = score
                function["matched_tokens"] = matched_tokens
                scored_functions.append(function)
            
            # Sort by relevance score (highest first)
            scored_functions.sort(key=lambda x: x["relevance"], reverse=True)
            
            # Return top results
            return scored_functions[:limit]
    
    def find_by_metaprogramming_features(self, project_name: str, **kwargs) -> List[Dict[str, Any]]:
        """
        Find functions by specific template metaprogramming features.
        
        Args:
            project_name: Project name to search in
            **kwargs: Key-value pairs of features to search for, possible keys include:
                - has_variadic_templates (bool): Whether the function uses variadic templates
                - is_metafunction (bool): Whether the function is a metafunction
                - metafunction_kind (str): Kind of metafunction ('type_trait', 'value_trait', etc)
                - has_sfinae (bool): Whether SFINAE techniques are used
                - sfinae_technique (str): Specific SFINAE technique
                - is_concept (bool): Whether the function uses concepts
                - has_template_template_params (bool): Whether the function has template template parameters
                - partial_specialization (bool): Whether the function is a partial specialization
            
        Returns:
            List of matching functions
        """
        query_parts = ["MATCH (f:Function {project: $project})"]
        match_clauses = []
        params = {"project": project_name}
        
        # Process simple boolean properties
        boolean_props = [
            "has_variadic_templates", "is_metafunction", 
            "has_sfinae", "is_concept", "partial_specialization"
        ]
        
        for prop in boolean_props:
            if prop in kwargs:
                match_clauses.append(f"f.{prop} = ${prop}")
                params[prop] = kwargs[prop]
        
        # Process string properties with exact match
        string_props = ["metafunction_kind", "variadic_template_param", "primary_template"]
        
        for prop in string_props:
            if prop in kwargs:
                match_clauses.append(f"f.{prop} = ${prop}")
                params[prop] = kwargs[prop]
        
        # Handle special case: sfinae_technique (search in array)
        if "sfinae_technique" in kwargs:
            query_parts.append(f"MATCH (f)-[:HAS_SFINAE_TECHNIQUES]->(t:SfaineTechnique {{value: $sfinae_technique}})")
            params["sfinae_technique"] = kwargs["sfinae_technique"]
        
        # Handle template_template_param search
        if "has_template_template_params" in kwargs and kwargs["has_template_template_params"]:
            query_parts.append("MATCH (f)-[:HAS_TEMPLATE_TEMPLATE_PARAMS]->(p)")
        
        # Handle specific template param search
        if "template_param" in kwargs:
            query_parts.append(f"MATCH (f)-[:HAS_TEMPLATE_PARAMS]->(p:TemplateParams {{value: $template_param}})")
            params["template_param"] = kwargs["template_param"]
        
        # Add WHERE clause if we have match conditions
        if match_clauses:
            query_parts.append("WHERE " + " AND ".join(match_clauses))
        
        # Finalize query
        query_parts.append("RETURN DISTINCT f")
        query = "\n".join(query_parts)
        
        # Execute query
        with self.neo4j_service.driver.session() as session:
            result = session.run(query, **params)
            functions = [dict(record["f"]) for record in result]
            
            # For each function, get the array properties
            for func in functions:
                # Fetch template params
                self._fetch_array_property(session, func, "template_params", project_name)
                
                # Fetch other relevant array properties based on function features
                if func.get("has_variadic_templates", False):
                    self._fetch_array_property(session, func, "template_template_params", project_name)
                
                if func.get("is_concept", False):
                    self._fetch_array_property(session, func, "concept_requirements", project_name)
                    self._fetch_array_property(session, func, "constraint_expressions", project_name)
                
                if func.get("has_sfinae", False):
                    self._fetch_array_property(session, func, "sfinae_techniques", project_name)
            
            return functions
    
    def _fetch_array_property(self, session, func: Dict[str, Any], property_name: str, project_name: str) -> None:
        """
        Fetch array property values for a function.
        
        Args:
            session: Neo4j session
            func: Function dictionary to update
            property_name: Property name to fetch
            project_name: Project name
        """
        query = f"""
        MATCH (f:Function {{name: $name, project: $project}})-[:HAS_{property_name.upper()}]->(p)
        RETURN p.value as value
        """
        
        result = session.run(query, name=func["name"], project=project_name)
        values = [record["value"] for record in result]
        
        if values:
            func[property_name] = values 