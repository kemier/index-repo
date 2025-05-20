import ast

def parse_code_blocks(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        source = f.read()
    tree = ast.parse(source, filename=file_path)
    code_blocks = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            start = node.lineno
            end = getattr(node, 'end_lineno', start)
            code = '\n'.join(source.splitlines()[start-1:end])
            code_blocks.append({
                'type': type(node).__name__,
                'name': getattr(node, 'name', None),
                'start_line': start,
                'end_line': end,
                'code': code,
                'file': file_path
            })
    return code_blocks 