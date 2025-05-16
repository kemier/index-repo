import os
import re

class CodeExtractor:
    """工具类，用于从源文件中提取完整的函数体"""
    
    @staticmethod
    def extract_function_body(file_path: str, function_name: str, line_number: int) -> str:
        """
        从源文件中提取函数体
        
        Args:
            file_path: 源文件路径
            function_name: 函数名（可能包含类名，如"OrderSystem::create_order"）
            line_number: 函数声明或定义的行号
            
        Returns:
            函数体文本，如果无法提取则返回空字符串
        """
        if not os.path.exists(file_path):
            return f"ERROR: File not found: {file_path}"
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                
            # 确保行号在文件范围内
            if line_number > len(lines):
                return f"ERROR: Line {line_number} exceeds file length"
            
            # 检查文件类型
            is_header = file_path.endswith('.h') or file_path.endswith('.hpp')
            
            # 如果是头文件，尝试找到对应的实现文件
            if is_header:
                # 查找可能的实现文件路径
                possible_impl_paths = []
                base_path = os.path.dirname(file_path)
                file_name = os.path.basename(file_path)
                file_name_without_ext = os.path.splitext(file_name)[0]
                
                # 常见的实现文件扩展名
                for ext in ['.cpp', '.cc', '.cxx']:
                    impl_path = os.path.join(base_path, file_name_without_ext + ext)
                    if os.path.exists(impl_path):
                        possible_impl_paths.append(impl_path)
                
                # 如果找到了实现文件，从实现文件中提取函数体
                function_short_name = function_name.split('::')[-1] if '::' in function_name else function_name
                class_prefix = function_name.rsplit('::', 1)[0] + '::' if '::' in function_name else ''
                
                for impl_path in possible_impl_paths:
                    # 在实现文件中搜索函数定义
                    with open(impl_path, 'r', encoding='utf-8') as f:
                        impl_lines = f.readlines()
                    
                    # 匹配函数定义的行
                    func_def_line = -1
                    for i, line in enumerate(impl_lines):
                        # 查找形如 "ReturnType ClassName::functionName(" 的模式
                        if f"{class_prefix}{function_short_name}(" in line or f"{class_prefix}{function_short_name} (" in line:
                            func_def_line = i + 1  # 行号从1开始
                            break
                    
                    if func_def_line != -1:
                        # 找到函数定义，提取函数体
                        return CodeExtractor._extract_function_body_from_lines(impl_lines, func_def_line, function_name)
                
                # 如果没有找到实现文件或函数定义，则从头文件中尝试提取
                # 这通常只适用于模板函数或内联函数
                return CodeExtractor._extract_function_body_from_lines(lines, line_number, function_name)
            else:
                # 如果是实现文件，直接提取函数体
                return CodeExtractor._extract_function_body_from_lines(lines, line_number, function_name)
                
        except Exception as e:
            return f"ERROR: Failed to extract function body: {str(e)}"
    
    @staticmethod
    def _extract_function_body_from_lines(lines: list, line_number: int, function_name: str) -> str:
        """
        从给定的文件行中提取函数体
        
        Args:
            lines: 文件内容的行列表
            line_number: 函数声明或定义的行号（从1开始）
            function_name: 函数名
            
        Returns:
            函数体文本
        """
        # 检查行号范围
        if line_number <= 0 or line_number > len(lines):
            return f"ERROR: Line {line_number} out of range"
        
        # 首先在当前行或其附近寻找函数定义的起始点
        body_start = -1
        # 查找函数定义行（包含函数名和(开始的参数列表）
        function_def_line = -1
        for i in range(max(0, line_number - 1), min(line_number + 30, len(lines))):
            if function_name.split('::')[-1] + '(' in lines[i]:
                function_def_line = i
                break
        
        # 如果没找到函数定义行，尝试使用行号指定的行
        if function_def_line == -1:
            function_def_line = line_number - 1
            
        # 从函数定义行开始，寻找函数体开始的{
        for i in range(function_def_line, min(function_def_line + 10, len(lines))):
            if '{' in lines[i]:
                body_start = i
                break
        
        if body_start == -1:
            # 如果没有找到函数体的起始，先检查这是否是只有声明的情况
            for i in range(max(0, line_number - 1), min(line_number + 10, len(lines))):
                if ';' in lines[i] and '{' not in lines[i]:
                    # 这可能是声明而不是定义
                    return f"NOTE: Line {line_number} appears to contain a function declaration, not a definition. The function body should be in the implementation file."
            
            # 否则报告错误
            return f"ERROR: Could not find function body start for {function_name}"
        
        # 从body_start开始向后扫描，寻找匹配的}来确定函数体的结束
        brace_count = 0
        body_lines = []
        
        # 仅包含一次函数签名（函数定义开始到函数体开始）
        # 跳过行号指定的行（通常是声明而不是定义）
        if function_def_line != line_number - 1:
            for i in range(function_def_line, body_start + 1):
                body_lines.append(lines[i])
        else:
            # 如果行号确实指向的是定义行，则直接从定义行开始
            for i in range(function_def_line, body_start + 1):
                body_lines.append(lines[i])
        
        # 从函数体起始处向后扫描到函数体结束
        for i in range(body_start, len(lines)):
            line = lines[i]
            if i != body_start or line not in body_lines:  # 避免重复添加body_start行
                body_lines.append(line)
            
            # 计算花括号的嵌套级别
            brace_count += line.count('{')
            brace_count -= line.count('}')
            
            # 当花括号计数归零时，我们找到了函数体的结束
            if brace_count == 0 and i > body_start:
                break
        
        return ''.join(body_lines)
    
    @staticmethod
    def extract_functions_from_query_result(query_result: dict, base_path: str = "") -> dict:
        """
        处理查询结果，为每个函数添加函数体
        
        Args:
            query_result: Dgraph查询结果
            base_path: 源文件的基础路径，如果函数路径是相对路径，将添加此前缀
            
        Returns:
            添加了函数体的查询结果
        """
        result = query_result.copy()
        
        # 遍历所有结果键
        for key in result:
            if isinstance(result[key], list):
                for func in result[key]:
                    # 检查是否是函数对象（具有name和file_path属性）
                    if isinstance(func, dict) and 'name' in func and 'file_path' in func and 'line_number' in func:
                        file_path = func['file_path']
                        if base_path and not os.path.isabs(file_path):
                            file_path = os.path.join(base_path, file_path)
                        
                        # 提取函数体并添加到结果中
                        func['function_body'] = CodeExtractor.extract_function_body(
                            file_path, 
                            func['name'], 
                            func['line_number']
                        )
                        
                        # 递归处理调用关系
                        if 'calls' in func and isinstance(func['calls'], list):
                            for called_func in func['calls']:
                                if isinstance(called_func, dict) and 'name' in called_func and 'file_path' in called_func and 'line_number' in called_func:
                                    called_file_path = called_func['file_path']
                                    if base_path and not os.path.isabs(called_file_path):
                                        called_file_path = os.path.join(base_path, called_file_path)
                                    
                                    called_func['function_body'] = CodeExtractor.extract_function_body(
                                        called_file_path,
                                        called_func['name'],
                                        called_func['line_number']
                                    )
                        
                        # 递归处理被调用关系
                        if 'called_by' in func and isinstance(func['called_by'], list):
                            for caller_func in func['called_by']:
                                if isinstance(caller_func, dict) and 'name' in caller_func and 'file_path' in caller_func and 'line_number' in caller_func:
                                    caller_file_path = caller_func['file_path']
                                    if base_path and not os.path.isabs(caller_file_path):
                                        caller_file_path = os.path.join(base_path, caller_file_path)
                                    
                                    caller_func['function_body'] = CodeExtractor.extract_function_body(
                                        caller_file_path,
                                        caller_func['name'],
                                        caller_func['line_number']
                                    )
                        
                        # 同样处理calls_functions和called_by_functions（如果存在）
                        if 'calls_functions' in func and isinstance(func['calls_functions'], list):
                            for called_func in func['calls_functions']:
                                if isinstance(called_func, dict) and 'name' in called_func and 'file_path' in called_func and 'line_number' in called_func:
                                    called_file_path = called_func['file_path']
                                    if base_path and not os.path.isabs(called_file_path):
                                        called_file_path = os.path.join(base_path, called_file_path)
                                    
                                    called_func['function_body'] = CodeExtractor.extract_function_body(
                                        called_file_path,
                                        called_func['name'],
                                        called_func['line_number']
                                    )
                        
                        if 'called_by_functions' in func and isinstance(func['called_by_functions'], list):
                            for caller_func in func['called_by_functions']:
                                if isinstance(caller_func, dict) and 'name' in caller_func and 'file_path' in caller_func and 'line_number' in caller_func:
                                    caller_file_path = caller_func['file_path']
                                    if base_path and not os.path.isabs(caller_file_path):
                                        caller_file_path = os.path.join(base_path, caller_file_path)
                                    
                                    caller_func['function_body'] = CodeExtractor.extract_function_body(
                                        caller_file_path,
                                        caller_func['name'],
                                        caller_func['line_number']
                                    )
        
        return result 