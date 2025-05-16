import os
from typing import Dict
from langchain.prompts import PromptTemplate
from langchain_deepseek import ChatDeepSeek
from langchain.chains import LLMChain
from dotenv import load_dotenv
import re

class QueryGenerator:
    def __init__(self, deepseek_api_key: str):
        # Load environment variables if not already done (though typically done in main)
        load_dotenv() 
        if not deepseek_api_key:
            # Fallback or error if key is still not found after load_dotenv in main
            print("Warning: DEEPSEEK_API_KEY not found in QueryGenerator. Ensure it is set.")
            # Depending on policy, either raise error or use a placeholder that will fail
            # raise ValueError("DEEPSEEK_API_KEY is essential for QueryGenerator")

        self.llm = ChatDeepSeek(model="deepseek-chat", temperature=0, api_key=deepseek_api_key)
        # Note: input_variables must match keys in dict passed to invoke()
        self.prompt_template = PromptTemplate(
            template="""你是一位Dgraph DQL查询生成专家。
严格按照Dgraph的schema生成查询。

可用Schema:
# Predicates
name: string @index(term, trigram) .
file_path: string @index(term) .
line_number: int .
is_callback: bool @index(bool) .
callback_type: string .
calls: [uid] @reverse .  # 表示函数调用关系：函数A调用了函数B
called_by: [uid] @reverse .  # 表示被调用关系：函数B被函数A调用
in_branch: [uid] @reverse .
branch_node_type: string @index(term) .
condition: string .
contains: [uid] @reverse .

# Types
type Function {{ name file_path line_number is_callback callback_type calls called_by in_branch }}
type Branch {{ branch_node_type condition file_path line_number contains }}

# - 使用 `regexp(predicate, /pattern/i)` 进行不区分大小写的正则表达式搜索 (例如 `@filter(regexp(name, /order|item/i))`)。
# - 使用 `match(predicate, "search term", distance)` 进行模糊搜索 (例如 `@filter(match(name, "order item", 2))`)。
# - 对于递归查询，正确的格式是直接列出字段而不使用 `@recurse` 或 `expand(_all_)`：
#   例如，查询调用链应该这样写:
#   ```
#   calls {{  # 显示此函数调用的函数列表
#     uid
#     name
#     file_path
#     line_number
#     calls {{  # 继续显示下一级被调用的函数
#       uid 
#       name
#       file_path
#       line_number
#     }}
#   }}
#   called_by {{  # 显示调用此函数的函数列表
#     uid
#     name
#     file_path
#     line_number
#   }}
#   ```
#   调用层级深度可以根据需要增加更多嵌套层级

用户的自然语言问题是： {nl_query}

针对此问题，请生成一个名为 '{result_key_placeholder}' 的DQL查询块。 例如，如果 result_key_placeholder 是 "MyFunctions"，并且问题是 "查找所有函数及其调用关系"，你的输出应该是这样的纯DQL字符串：

{{ 
  MyFunctions(func: type(Function)) {{ 
    name 
    file_path
    line_number
    # 这个函数调用了哪些函数
    calls {{
      uid
      name
      file_path
      line_number
    }}
    # 这个函数被哪些函数调用
    called_by {{
      uid
      name
      file_path
      line_number
    }}
  }} 
}}

注意：
1. 一个DQL查询必须只有一组最外层的大括号，且内层的嵌套要对称。
2. 不要使用 `expand(_all_)` 语法，而是直接列出需要的字段。
3. 不要在字段名后使用冒号，例如使用 `calls {{ ... }}` 而不是 `calls: {{ ... }}`。
4. 嵌套查询不要超过3层，避免查询过于复杂。
5. 始终包含调用关系字段（calls和called_by），以帮助用户理解函数之间的关系。

不要包含任何其他解释、说明、JSON封装或Markdown代码块。只返回纯粹的DQL字符串。
确保DQL查询中所有在 `var` 块中定义的变量都在后续的 `var` 块中被使用，或者在最终的查询块中通过 `uid()` 函数被引用。
""",
            input_variables=["nl_query", "result_key_placeholder"]
        )
        self.chain = self.prompt_template | self.llm

    def generate_dql_query(self, nl_query: str, result_key: str) -> str:
        """Generate a Dgraph DQL query from natural language description."""
        response = self.chain.invoke({"nl_query": nl_query, "result_key_placeholder": result_key})
        
        dql_query = ""
        if hasattr(response, 'content'):
            dql_query = response.content
        elif isinstance(response, str):
            dql_query = response
        else:
            print(f"Unexpected LLM response type: {type(response)}. Attempting to str(response).")
            dql_query = str(response) # Fallback, might not be correct DQL

        print(f"LLM Raw Output String: {repr(dql_query)}") # Log the raw string from LLM

        # Clean up common LLM artifacts like markdown code fences
        # Be careful with stripping if the LLM is (correctly) supposed to return a string starting/ending with { }
        temp_query = dql_query.strip()
        fences = [
            "```dgraph\n", "```dql\n", "```json\n", "```graphql\n", "```\n", "```"
        ]
        for fence_start in fences:
            if temp_query.startswith(fence_start):
                temp_query = temp_query[len(fence_start):]
                # If it started with a fence, it likely ends with a fence too
                if temp_query.endswith("\n```"):
                    temp_query = temp_query[:-len("\n```")]
                elif temp_query.endswith("```"):
                    temp_query = temp_query[:-len("```")]
                break # Assume only one set of fences
        
        dql_query = temp_query.strip() # Strip again after fence removal

        # Fix double braces issues {{{{ }}}} -> { } in the query
        dql_query = re.sub(r'\{{2,}', '{', dql_query)
        dql_query = re.sub(r'\}{2,}', '}', dql_query)
        
        # Fix expand syntax - Dgraph doesn't allow aliases with expand()
        dql_query = re.sub(r'(\w+):\s*expand\(_all_\)', r'expand(_all_)', dql_query)
        
        # Remove colons after field names in non-expand contexts
        dql_query = re.sub(r'(\w+):\s*{', r'\1 {', dql_query)
        
        # Specific textual replacements for known/recurring LLM DQL errors
        # These are brittle and ideally the LLM improves, or a proper DQL parser/validator is used.
        dql_query = dql_query.replace("@filter(not has(is_callback)))", "@filter(not has(is_callback))")
        
        # Fix common recurse syntax error (@recurse {})
        dql_query = dql_query.replace("@recurse {}", "expand(_all_)")
        dql_query = dql_query.replace("@recurse()", "expand(_all_)")
        
        dql_query = re.sub(r"(@filter\(uid\([a-zA-Z0-9_]+\)\)\))", r"\1)", dql_query)
        dql_query = dql_query.replace(")))) {", ")) {")

        # Ensure the entire query is wrapped in { } - This is critical as LLM might omit root braces
        # Revised Logic: Always apply our own canonical outer braces after cleaning LLM output.
        final_query_content = dql_query
        if final_query_content.startswith("{") and final_query_content.endswith("}"):
            # If LLM provided its own braces, and content is more than just "{}", strip them for consistency
            if len(final_query_content) > 2:
                final_query_content = final_query_content[1:-1].strip()
            elif final_query_content == "{}": # Handle case where LLM returns exactly "{}"
                final_query_content = "" # Content is empty, will be wrapped below
        
        # Ensure there are no nested outer braces from LLM output
        if final_query_content.startswith("{") and final_query_content.endswith("}"):
            inner_content = final_query_content[1:-1].strip()
            if inner_content.count("{") == inner_content.count("}"):
                final_query_content = inner_content
        
        # Wrap the (potentially stripped) content with our canonical braces.
        # This ensures one level of root braces.
        dql_query = "{\n  " + final_query_content + "\n}"

        print(f"Cleaned DQL Query: {repr(dql_query)}")
        return dql_query

    def get_common_queries(self) -> Dict[str, str]:
        # This method might need to be updated or removed if not used, or if common queries are generated differently
        return {
            "find_all_functions": "{ q(func: type(Function)) { name file_path line_number calls { name file_path line_number } called_by { name file_path line_number } } }",
            "function_call_relationships": """
            {
              call_graph(func: type(Function)) @filter(regexp(file_path, /.*test_repo.*/)) {
                uid
                name
                file_path
                line_number
                
                # 这个函数调用了哪些函数
                calls_functions: calls {
                  uid
                  name
                  file_path
                  line_number
                }
                
                # 这个函数被哪些函数调用
                called_by_functions: called_by {
                  uid
                  name
                  file_path
                  line_number
                }
              }
            }
            """,
            "concise_call_relationships": """
            {
              # 直接查询所有test_repo中的函数，限制为前20个
              unique_functions(func: type(Function), first: 20) @filter(regexp(file_path, /.*test_repo.*/)) {
                uid
                name
                file_path
                line_number
                
                # 这个函数调用了哪些函数
                calls_out: calls {
                  uid
                  name
                  file_path
                  line_number
                }
                
                # 这个函数被哪些函数调用
                calls_in: called_by {
                  uid 
                  name
                  file_path
                  line_number
                }
              }
            }
            """,
            "order_system_relationships": """
            {
              # 查询OrderSystem类的函数
              order_functions(func: type(Function)) @filter(regexp(name, /^OrderSystem::/)) {
                uid
                name
                file_path
                line_number
                
                # 这个函数调用了哪些函数
                calls_functions: calls {
                  uid
                  name
                  file_path
                  line_number
                }
                
                # 这个函数被哪些函数调用
                called_by_functions: called_by {
                  uid
                  name
                  file_path
                  line_number
                }
              }
            }
            """
        } 