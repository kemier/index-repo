"""
解析compile_commands.json文件并处理包含路径的服务。
"""
import os
import json
import re
import platform
from typing import List, Dict, Set, Optional, Tuple
import logging

class CompileCommandsService:
    """用于解析compile_commands.json文件并提取编译选项的服务。"""
    
    def __init__(self, compile_commands_path: Optional[str] = None):
        """
        初始化服务。
        
        Args:
            compile_commands_path: compile_commands.json文件的路径，如果为None则尝试自动查找
        """
        self.compile_commands_path = compile_commands_path
        self.compile_commands = []
        self.file_to_command = {}  # 文件路径到编译命令的映射
        
        if compile_commands_path and os.path.exists(compile_commands_path):
            self.load_compile_commands(compile_commands_path)
    
    def load_compile_commands(self, path: str) -> bool:
        """
        加载compile_commands.json文件。
        
        Args:
            path: 文件路径
            
        Returns:
            加载是否成功
        """
        try:
            with open(path, 'r', encoding='utf-8') as f:
                self.compile_commands = json.load(f)
                
            # 构建文件到命令的映射
            for cmd in self.compile_commands:
                file_path = cmd.get('file')
                if file_path:
                    # 规范化路径
                    norm_path = os.path.normpath(file_path)
                    self.file_to_command[norm_path] = cmd
            
            return True
        except Exception as e:
            logging.error(f"Error loading compile_commands.json: {e}")
            return False
    
    def find_compile_commands(self, start_dir: str) -> Optional[str]:
        """
        从指定目录开始向上递归查找compile_commands.json文件。
        
        Args:
            start_dir: 开始查找的目录
            
        Returns:
            找到的文件路径，如果未找到则返回None
        """
        current_dir = os.path.abspath(start_dir)
        while True:
            compile_commands_path = os.path.join(current_dir, 'compile_commands.json')
            if os.path.exists(compile_commands_path):
                return compile_commands_path
            
            parent_dir = os.path.dirname(current_dir)
            if parent_dir == current_dir:  # 已经到达根目录
                break
            current_dir = parent_dir
        
        # 在build子目录中查找
        build_dirs = ['build', 'Build', 'BUILD', 'out', 'Out', 'OUT']
        for build_dir in build_dirs:
            compile_commands_path = os.path.join(start_dir, build_dir, 'compile_commands.json')
            if os.path.exists(compile_commands_path):
                return compile_commands_path
        
        return None
    
    def get_compile_command(self, file_path: str) -> Optional[Dict]:
        """
        获取指定文件的编译命令。
        
        Args:
            file_path: 文件路径
            
        Returns:
            编译命令字典，如果未找到则返回None
        """
        norm_path = os.path.normpath(file_path)
        return self.file_to_command.get(norm_path)
    
    def get_include_paths(self, file_path: str) -> List[str]:
        """
        从编译命令中提取包含路径。
        
        Args:
            file_path: 文件路径
            
        Returns:
            包含路径列表
        """
        cmd = self.get_compile_command(file_path)
        if not cmd:
            return []
        
        command_line = cmd.get('command', '')
        if not command_line and 'arguments' in cmd:
            # 某些compile_commands.json使用arguments数组而不是command字符串
            command_line = ' '.join(cmd['arguments'])
        
        include_paths = []
        
        # 提取-I选项
        include_pattern = r'-I\s*([^\s]+)'
        include_matches = re.finditer(include_pattern, command_line)
        for match in include_matches:
            path = match.group(1)
            # 处理相对路径
            if not os.path.isabs(path):
                path = os.path.normpath(os.path.join(cmd.get('directory', ''), path))
            include_paths.append(path)
        
        # 提取-isystem选项
        system_include_pattern = r'-isystem\s*([^\s]+)'
        system_include_matches = re.finditer(system_include_pattern, command_line)
        for match in system_include_matches:
            path = match.group(1)
            if not os.path.isabs(path):
                path = os.path.normpath(os.path.join(cmd.get('directory', ''), path))
            include_paths.append(path)
        
        return include_paths
    
    def get_compiler_options(self, file_path: str) -> List[str]:
        """
        从编译命令中提取编译器选项。
        
        Args:
            file_path: 文件路径
            
        Returns:
            编译器选项列表
        """
        cmd = self.get_compile_command(file_path)
        if not cmd:
            return []
        
        # 提取命令行参数
        if 'arguments' in cmd:
            args = cmd['arguments']
        else:
            command = cmd.get('command', '')
            # 简单分割，不考虑引号等复杂情况
            args = command.split()
        
        # 过滤出编译器选项，排除输入文件和输出文件
        options = []
        skip_next = False
        for i, arg in enumerate(args):
            if skip_next:
                skip_next = False
                continue
                
            # 跳过编译器路径
            if i == 0:
                continue
                
            # 跳过输入文件和输出文件选项
            if arg == file_path or arg.endswith(os.path.basename(file_path)):
                continue
                
            if arg in ['-o', '-c']:
                skip_next = True
                continue
                
            if arg.startswith('-o') or arg.startswith('-c'):
                continue
                
            options.append(arg)
        
        return options
    
    def get_clang_args(self, file_path: str) -> List[str]:
        """
        获取适用于libclang的编译参数。
        
        Args:
            file_path: 文件路径
            
        Returns:
            编译参数列表
        """
        options = self.get_compiler_options(file_path)
        
        # 过滤掉一些不兼容的选项
        filtered_options = []
        skip_next = False
        for i, opt in enumerate(options):
            if skip_next:
                skip_next = False
                continue
                
            # 跳过一些libclang不支持的选项
            if opt in ['-fcolor-diagnostics', '-fdiagnostics-color', '-Werror']:
                continue
                
            # 跳过有参数的不支持选项
            if opt in ['-arch', '-target']:
                skip_next = True
                continue
                
            filtered_options.append(opt)
        
        # 添加文件类型
        if file_path.endswith('.cpp') or file_path.endswith('.cc') or file_path.endswith('.cxx'):
            filtered_options.append('-xc++')
        elif file_path.endswith('.c'):
            filtered_options.append('-xc')
        
        return filtered_options
    
    def infer_include_paths(self, file_content: str, base_dir: str) -> List[str]:
        """
        从文件内容中推断可能的包含目录。
        
        Args:
            file_content: 文件内容
            base_dir: 基础目录
            
        Returns:
            推断的包含目录列表
        """
        include_paths = set()
        
        # 查找#include语句
        include_pattern = r'#include\s+["<]([^">]+)[">]'
        include_matches = re.finditer(include_pattern, file_content)
        
        for match in include_matches:
            include_file = match.group(1)
            
            # 跳过系统头文件
            if match.group(0).startswith('#include <') and '/' not in include_file:
                continue
                
            # 对于相对路径，尝试在基础目录和父目录中查找
            if match.group(0).startswith('#include "'):
                path_parts = include_file.split('/')
                
                # 尝试各种可能的包含路径
                current_dir = base_dir
                for _ in range(len(path_parts)):
                    if os.path.exists(os.path.join(current_dir, *path_parts)):
                        include_paths.add(current_dir)
                        break
                    
                    # 向上移动一级目录
                    current_dir = os.path.dirname(current_dir)
                    if current_dir == os.path.dirname(current_dir):  # 已经到达根目录
                        break
        
        return list(include_paths)
    
    def normalize_path(self, path: str) -> str:
        """
        根据当前操作系统规范化路径。
        
        Args:
            path: 原始路径
            
        Returns:
            规范化的路径
        """
        norm_path = os.path.normpath(path)
        
        # 在Windows上统一路径分隔符
        if platform.system() == 'Windows':
            norm_path = norm_path.replace('\\', '/')
            
            # 处理盘符
            match = re.match(r'^([A-Za-z]):(.*)$', norm_path)
            if match:
                drive, rest = match.groups()
                norm_path = f"/{drive.lower()}{rest}"
        
        return norm_path
    
    def create_compile_commands(self, directory: str, files: List[str], 
                              compiler: str = 'g++', options: List[str] = None) -> bool:
        """
        为指定目录创建compile_commands.json文件。
        
        Args:
            directory: 目标目录
            files: 需要包含的文件列表
            compiler: 使用的编译器
            options: 编译选项
            
        Returns:
            是否成功创建
        """
        if options is None:
            options = ['-std=c++17']
            
        commands = []
        for file in files:
            abs_path = os.path.abspath(file)
            rel_path = os.path.relpath(abs_path, directory)
            
            command = {
                'directory': directory,
                'file': abs_path,
                'arguments': [compiler, *options, '-c', rel_path]
            }
            commands.append(command)
            
        try:
            output_path = os.path.join(directory, 'compile_commands.json')
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(commands, f, indent=2)
            return True
        except Exception as e:
            logging.error(f"Error creating compile_commands.json: {e}")
            return False 