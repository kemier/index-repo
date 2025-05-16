from langchain.llms import OpenAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain

# 初始化模型
llm = OpenAI(temperature=0)

# 定义提示词
prompt_template = """你是一位资深的软件工程师，熟悉C/C++代码库。
以下是一个自然语言描述的业务需求，请你根据这个描述生成一个Dgraph查询，以找到相关的函数及其调用关系，包括逻辑分支和回调函数。

业务需求：{business_need}

查询要点：
1. 考虑函数名、文件路径、行号等信息。
2. 考虑函数的调用关系。
3. 考虑逻辑分支中的调用。
4. 考虑通过struct注册的回调函数。
5. 以Dgraph查询语言（GraphQL）格式输出。

Dgraph查询：
"""

# 创建 LLMChain
prompt = PromptTemplate(template=prompt_template, input_variables=["business_need"])
llm_chain = LLMChain(prompt=prompt, llm=llm)

# 执行查询
business_need = "找到计算用户订单总价的函数及其调用关系，包括逻辑分支和回调函数"
dgraph_query = llm_chain.run(business_need)
print(dgraph_query)