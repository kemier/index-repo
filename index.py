import os
from clang.cindex import Index, CursorKind, TypeKind

def extract_call_graph_with_callbacks(file_path):
    """提取 C/C++ 文件的调用关系，包括逻辑分支和回调函数"""
    index = Index.create()
    tu = index.parse(file_path)
    call_graph = {}

    def process_cursor(cursor, parent=None):
        if cursor.kind == CursorKind.FUNCTION_DECL:
            function_name = cursor.spelling
            call_graph[function_name] = {
                'file': file_path,
                'line': cursor.location.line,
                'calls': [],
                'branches': [],
                'callbacks': []
            }
            for child in cursor.get_children():
                if child.kind == CursorKind.CALL_EXPR:
                    called_function = child.referenced
                    if called_function and called_function.kind == CursorKind.FUNCTION_DECL:
                        call_graph[function_name]['calls'].append(called_function.spelling)
                elif child.kind in (CursorKind.IF_STMT, CursorKind.SWITCH_STMT, CursorKind.WHILE_STMT, CursorKind.FOR_STMT):
                    call_graph[function_name]['branches'].append({
                        'type': str(child.kind),
                        'line': child.location.line,
                        'calls': []
                    })
                    for branch_child in child.get_children():
                        if branch_child.kind == CursorKind.CALL_EXPR:
                            called_function = branch_child.referenced
                            if called_function and called_function.kind == CursorKind.FUNCTION_DECL:
                                call_graph[function_name]['branches'][-1]['calls'].append(called_function.spelling)
                elif child.kind == CursorKind.VAR_DECL:
                    if child.type.kind == TypeKind.POINTER and child.type.get_pointee().kind == TypeKind.FUNCTION:
                        call_graph[function_name]['callbacks'].append({
                            'name': child.spelling,
                            'type': str(child.type),
                            'line': child.location.line
                        })
                process_cursor(child, function_name)

    process_cursor(tu.cursor)
    return call_graph

repo_path = "/path/to/your/repo"
call_graph = {}

for root, dirs, files in os.walk(repo_path):
    for file in files:
        if file.endswith(('.c', '.cpp', '.h')):
            file_path = os.path.join(root, file)
            call_graph.update(extract_call_graph_with_callbacks(file_path))