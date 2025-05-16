import json
from pydgraph import DgraphClient, DgraphClientStub

# 初始化 Dgraph 客户端
client_stub = DgraphClientStub('localhost:9080')
client = DgraphClient(client_stub)

# 定义 Dgraph schema
schema = """
type Function {
  name: string
  file: string
  line: int
  calls: [Function] @reverse
  branches: [Branch] @reverse
  callbacks: [Callback] @reverse
}

type Branch {
  type: string
  line: int
  calls: [Function] @reverse
  belongsToFunction: Function
}

type Callback {
  name: string
  type: string
  line: int
  belongsToFunction: Function
}
"""

# 设置 schema
client.alter({'schema': schema})

# 准备数据
functions = []
branches = []
callbacks = []
for func_name, info in call_graph.items():
    function_data = {
        'uid': '_:' + func_name,
        'dgraph.type': 'Function',
        'name': func_name,
        'file': info['file'],
        'line': info['line'],
        'calls': [{'uid': '_:' + called_func} for called_func in info['calls']]
    }
    functions.append(function_data)
    
    for branch in info['branches']:
        branch_data = {
            'uid': '_:' + func_name + '_branch_' + str(branch['line']),
            'dgraph.type': 'Branch',
            'type': branch['type'],
            'line': branch['line'],
            'calls': [{'uid': '_:' + called_func} for called_func in branch['calls']],
            'belongsToFunction': {'uid': '_:' + func_name}
        }
        branches.append(branch_data)
    
    for cb in info['callbacks']:
        callback_data = {
            'uid': '_:' + func_name + '_callback_' + cb['name'],
            'dgraph.type': 'Callback',
            'name': cb['name'],
            'type': cb['type'],
            'line': cb['line'],
            'belongsToFunction': {'uid': '_:' + func_name}
        }
        callbacks.append(callback_data)

# 插入数据
with client.txn() as txn:
    txn.mutate(set_obj={'functions': functions, 'branches': branches, 'callbacks': callbacks})
    txn.commit()