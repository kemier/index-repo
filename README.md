# C/C++代码分析与查询系统

这是一个基于Python的C/C++代码分析系统，具有以下功能：

1. 使用Clang分析C/C++代码，提取函数调用关系
2. 使用Dgraph存储代码关系图，支持高效查询
3. 支持通过自然语言查询代码库中的函数关系
4. 自动提取函数体，显示完整的函数定义
5. 支持命令行接口和API集成

## 系统架构

该系统由以下主要组件组成：

- `CodeAnalyzer`: 使用libclang解析C/C++代码，提取函数调用关系
- `DgraphManager`: 管理与Dgraph数据库的交互，存储和查询代码关系
- `QueryGenerator`: 将自然语言查询转换为Dgraph查询语言(DQL)
- `CodeExtractor`: 从源文件中提取函数体
- `main.py`: 整合以上组件的主系统
- `cli.py`: 提供命令行界面，可分析任意C/C++项目
- `api_example.py`: 展示如何将系统集成到其他工具中

## 环境要求

- Python 3.8+
- libclang
- Docker (用于运行Dgraph)

## 安装

1. 克隆存储库:

```bash
git clone <repository-url>
cd <repository-directory>
```

2. 使用UV创建虚拟环境:

```bash
# 安装UV
curl -LsSf https://astral.sh/uv/install.sh | sh

# 创建虚拟环境
uv venv

# 激活虚拟环境
# Windows
.venv\Scripts\activate
# Linux/Mac
source .venv/bin/activate
```

3. 安装依赖:

```bash
uv pip install -e .
```

4. 启动Dgraph:

```bash
docker run -it -p 5080:5080 -p 6080:6080 -p 8080:8080 -p 9080:9080 -p 8000:8000 dgraph/standalone:latest
```

5. 设置API密钥:

创建一个`.env`文件，并设置DeepSeek API密钥:

```
DEEPSEEK_API_KEY=your_api_key_here
```

## 使用方法

### 命令行工具

系统提供两种命令行工具：

#### 1. 功能查询工具 (query_functions.py)

使用`query_functions.py`脚本进行代码查询:

```bash
# 使用自然语言查询
python query_functions.py -q "查找所有与价格计算相关的函数"

# 使用预定义查询
python query_functions.py -p function_call_relationships

# 分析代码库并查询
python query_functions.py -s test_repo/*.cpp test_repo/*.h -c "-std=c++17" -q "查找回调函数"

# 显示所有函数
python query_functions.py -a

# 将结果保存到文件
python query_functions.py -q "查找递归函数" -o results.json
```

#### 2. 通用C/C++项目分析工具 (cli.py)

新的`cli.py`工具支持更灵活的项目分析:

```bash
# 分析C/C++项目
python cli.py analyze /path/to/project --recursive

# 使用自然语言查询
python cli.py query "Find functions related to error handling"

# 显示特定函数的详细信息
python cli.py function calculate_total_price

# 保存查询结果到文件
python cli.py query "Find callback functions" --output results.json
```

CLI工具选项:

```
analyze  - 分析C/C++项目
  --patterns        文件模式 (默认: *.cpp *.h *.hpp *.c *.cc)
  --compile-args    编译参数 (默认: -std=c++17)
  --recursive       递归搜索文件

query    - 使用自然语言查询函数
  --output          保存结果到文件
  --no-bodies       不提取函数体

function - 显示特定函数的详细信息
  --file            指定源文件路径
```

### 高级分析功能

新的高级分析工具`test_advanced_analysis.py`提供了更深入的代码关系分析:

```bash
# 分析特定函数的关系
python test_advanced_analysis.py calculate_total_price

# 运行默认分析，包括回调函数和复杂流程分析
python test_advanced_analysis.py
```

### API集成示例

使用`api_example.py`学习如何将代码分析系统集成到其他工具中:

```bash
# 分析示例项目
python api_example.py --analyze

# 执行查询
python api_example.py --query "Find functions related to price calculation"

# 获取特定函数的详细信息
python api_example.py --function calculate_total_price

# 显示函数的调用图
python api_example.py --call-graph calculate_total_price

# 列出所有预定义查询
python api_example.py --list-queries

# 以JSON格式输出结果
python api_example.py --function calculate_total_price --output json
```

### 命令行选项 (query_functions.py)

```
options:
  -h, --help            显示此帮助信息
  --query QUERY, -q QUERY
                        自然语言查询字符串
  --predefined PREDEFINED, -p PREDEFINED
                        使用预定义的查询
  --result-key RESULT_KEY, -k RESULT_KEY
                        查询结果在JSON中的键名
  --no-bodies           不提取函数体（更快）
  --no-deduplicate      不去除重复函数
  --source-files SOURCE_FILES [SOURCE_FILES ...], -s SOURCE_FILES [SOURCE_FILES ...]
                        源文件列表（如果需要先分析代码库）
  --compile-args COMPILE_ARGS [COMPILE_ARGS ...], -c COMPILE_ARGS [COMPILE_ARGS ...]
                        编译参数（如果需要先分析代码库）
  --all-functions, -a   显示所有函数
  --output OUTPUT, -o OUTPUT
                        将结果保存到指定文件
```

### 预定义查询

系统提供了以下预定义查询:

- `find_all_functions`: 查找所有函数
- `function_call_relationships`: 显示函数之间的调用关系
- `concise_call_relationships`: 显示精简版的函数调用关系
- `order_system_relationships`: 显示OrderSystem类的函数调用关系

### 编程接口

```python
from src.main import CodeAnalysisSystem

system = CodeAnalysisSystem()

# 分析代码库
source_files = ["file1.cpp", "file2.h"]
compile_args = ["-std=c++17", "-I/path/to/include"]
system.analyze_codebase(source_files, compile_args)

# 使用自然语言查询
results = system.query_by_natural_language(
    "找到所有与用户相关的函数", 
    "UserFunctions",
    extract_function_bodies=True
)

# 使用预定义查询
results = system.query_functions_with_bodies("function_call_relationships")
```

### 使用API封装类

```python
from api_example import CodeAnalysisAPI

api = CodeAnalysisAPI()

# 分析项目
api.analyze_project(
    ["/path/to/source1.cpp", "/path/to/header.h"],
    compile_args=["-std=c++17", "-I/path/to/include"]
)

# 执行自然语言查询
results = api.query_functions("Find functions related to error handling")
print(f"Found {results['count']} functions")

# 获取特定函数的详细信息
function_details = api.get_function_details("calculate_total_price")

# 获取函数调用图
call_graph = api.get_call_graph("main", depth=3)

# 执行预定义查询
available_queries = api.get_available_queries()
api.execute_predefined_query(available_queries["available_queries"][0])
```

## 示例

### 查询函数调用关系

```bash
python query_functions.py -q "查找OrderSystem类中哪些函数调用了validate_order函数"
```

### 分析新代码库

```bash
python query_functions.py -s path/to/src/*.cpp path/to/include/*.h -c "-std=c++17" -I"path/to/include" -q "找到所有回调函数"
```

### 使用CLI工具分析大型项目

```bash
# 分析整个项目
python cli.py analyze /path/to/large/project --recursive

# 查找特定模式的函数
python cli.py query "Find all functions that handle exceptions"

# 查看特定函数的实现
python cli.py function handle_error
```

### 使用API集成到CI/CD流程

```python
from api_example import CodeAnalysisAPI

def analyze_code_changes(changed_files):
    api = CodeAnalysisAPI()
    api.analyze_project(changed_files)
    
    # 检查是否有未处理的错误
    error_results = api.query_functions("Find functions that don't properly handle errors")
    if error_results["count"] > 0:
        print("Warning: Some functions may not properly handle errors!")
        for func in error_results["results"]:
            print(f"Check {func['name']} in {func['file_path']}")
    
    # 返回分析结果
    return error_results
```

## 贡献

欢迎贡献！请提交Pull Request或创建Issue。

## 许可证

本项目采用MIT许可证。 