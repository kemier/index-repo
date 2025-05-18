#!/usr/bin/env python
"""
测试compile_commands.json解析和包含路径处理。
"""
import os
import sys
import json
import logging
from pprint import pprint

# 添加父级目录到Python路径以便导入src模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.compile_commands_service import CompileCommandsService

def test_compile_commands_generation():
    """测试生成compile_commands.json文件。"""
    print("\n===== 测试生成compile_commands.json文件 =====")
    
    # 获取项目根目录
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # 查找测试文件
    test_files_dir = os.path.join(root_dir, 'test_files')
    test_files = [
        os.path.join(test_files_dir, f) 
        for f in os.listdir(test_files_dir) 
        if f.endswith('.cpp') or f.endswith('.c')
    ]
    
    if not test_files:
        print("没有找到测试文件")
        return
    
    print(f"找到 {len(test_files)} 个测试文件")
    
    # 创建输出目录
    output_dir = os.path.join(root_dir, 'output')
    os.makedirs(output_dir, exist_ok=True)
    
    # 创建服务
    service = CompileCommandsService()
    
    # 生成compile_commands.json
    compiler = 'g++' if sys.platform != 'win32' else 'cl.exe'
    options = ['-std=c++17', '-I./include', '-Wall', '-Wextra']
    
    success = service.create_compile_commands(output_dir, test_files, compiler, options)
    
    if success:
        print(f"成功创建compile_commands.json文件：{os.path.join(output_dir, 'compile_commands.json')}")
        
        # 读取并打印生成的文件
        with open(os.path.join(output_dir, 'compile_commands.json'), 'r', encoding='utf-8') as f:
            commands = json.load(f)
            print(f"\n生成的compile_commands.json包含 {len(commands)} 个条目：")
            for i, cmd in enumerate(commands):
                print(f"\n条目 {i+1}:")
                print(f"  文件: {cmd['file']}")
                print(f"  目录: {cmd['directory']}")
                print(f"  参数: {' '.join(cmd['arguments'])}")
    else:
        print("创建compile_commands.json文件失败")

def test_compile_commands_parsing():
    """测试解析compile_commands.json文件。"""
    print("\n===== 测试解析compile_commands.json文件 =====")
    
    # 获取项目根目录
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # 寻找compile_commands.json文件
    compile_commands_path = os.path.join(root_dir, 'output', 'compile_commands.json')
    if not os.path.exists(compile_commands_path):
        print(f"找不到文件: {compile_commands_path}")
        return
    
    # 创建服务
    service = CompileCommandsService(compile_commands_path)
    
    # 获取测试文件
    test_files_dir = os.path.join(root_dir, 'test_files')
    test_files = [
        os.path.join(test_files_dir, f) 
        for f in os.listdir(test_files_dir) 
        if f.endswith('.cpp') or f.endswith('.c')
    ]
    
    if not test_files:
        print("没有找到测试文件")
        return
    
    # 测试每个文件的编译命令解析
    for test_file in test_files:
        print(f"\n测试文件: {os.path.basename(test_file)}")
        
        # 获取编译命令
        cmd = service.get_compile_command(test_file)
        if cmd:
            print("找到编译命令")
        else:
            print("未找到编译命令")
            continue
        
        # 获取包含路径
        include_paths = service.get_include_paths(test_file)
        print(f"找到 {len(include_paths)} 个包含路径:")
        for path in include_paths:
            print(f"  {path}")
        
        # 获取编译器选项
        options = service.get_compiler_options(test_file)
        print(f"找到 {len(options)} 个编译器选项:")
        for opt in options:
            print(f"  {opt}")
        
        # 获取适用于libclang的参数
        clang_args = service.get_clang_args(test_file)
        print(f"适用于libclang的参数:")
        for arg in clang_args:
            print(f"  {arg}")

def test_include_path_inference():
    """测试从文件内容推断包含路径。"""
    print("\n===== 测试从文件内容推断包含路径 =====")
    
    # 获取项目根目录
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # 测试文件
    test_files_dir = os.path.join(root_dir, 'test_files')
    test_files = [
        os.path.join(test_files_dir, f) 
        for f in os.listdir(test_files_dir) 
        if f.endswith('.cpp') or f.endswith('.c')
    ]
    
    if not test_files:
        print("没有找到测试文件")
        return
    
    # 创建服务
    service = CompileCommandsService()
    
    # 测试每个文件的包含路径推断
    for test_file in test_files:
        print(f"\n测试文件: {os.path.basename(test_file)}")
        
        # 读取文件内容
        try:
            with open(test_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # 推断包含路径
            include_paths = service.infer_include_paths(content, os.path.dirname(test_file))
            print(f"推断出 {len(include_paths)} 个包含路径:")
            for path in include_paths:
                print(f"  {path}")
        except Exception as e:
            print(f"读取文件失败: {e}")

def test_path_normalization():
    """测试路径规范化。"""
    print("\n===== 测试路径规范化 =====")
    
    # 测试路径
    test_paths = [
        "C:\\Program Files\\LLVM\\include",
        "c:/users/username/project/include",
        "../include",
        "/usr/local/include",
        "D:\\project\\include\\..\\src",
    ]
    
    # 创建服务
    service = CompileCommandsService()
    
    # 测试每个路径的规范化
    for path in test_paths:
        print(f"原始路径: {path}")
        norm_path = service.normalize_path(path)
        print(f"规范化路径: {norm_path}")
        print()

def main():
    """主函数"""
    # 配置日志
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # 执行测试
    test_compile_commands_generation()
    test_compile_commands_parsing()
    test_include_path_inference()
    test_path_normalization()

if __name__ == "__main__":
    main() 