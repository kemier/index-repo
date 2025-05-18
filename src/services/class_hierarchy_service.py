"""
类层次结构分析服务，用于处理C++类继承和虚函数解析。
"""
import os
from typing import Dict, List, Set, Tuple, Optional
from clang.cindex import Index, CursorKind, TranslationUnit, Cursor

from src.models.function_model import Function
from src.models.class_model import ClassHierarchy, ClassNode

class ClassHierarchyService:
    """用于分析和处理C++类继承结构和虚函数关系的服务。"""
    
    def __init__(self, index: Index = None):
        """
        初始化类层次结构分析服务。
        
        Args:
            index: 可选的Clang索引实例，如果不提供则创建新实例
        """
        self.index = index if index else Index.create()
        self.class_hierarchy = ClassHierarchy()
        self._vtable_cache = {}  # 缓存已计算的虚函数表，避免重复计算
    
    def analyze_translation_unit(self, tu: TranslationUnit) -> ClassHierarchy:
        """
        分析翻译单元中的类层次结构。
        
        Args:
            tu: 要分析的翻译单元
            
        Returns:
            构建的类层次结构
        """
        self.class_hierarchy = ClassHierarchy()
        self._vtable_cache = {}  # 重置缓存
        self._process_cursor(tu.cursor)
        self._resolve_virtual_methods()
        return self.class_hierarchy
    
    def _process_cursor(self, cursor: Cursor) -> None:
        """
        递归处理游标以构建类层次结构。
        
        Args:
            cursor: 当前处理的游标
        """
        # 检查是否是类或结构体定义
        if cursor.kind in [CursorKind.CLASS_DECL, CursorKind.STRUCT_DECL, 
                           CursorKind.CLASS_TEMPLATE]:
            self._process_class_decl(cursor)
        
        # 递归处理子节点
        for child in cursor.get_children():
            self._process_cursor(child)
    
    def _process_class_decl(self, cursor: Cursor) -> None:
        """
        处理类声明，提取继承关系和虚函数。
        
        Args:
            cursor: 类声明的游标
        """
        class_name = cursor.spelling
        if not class_name:
            return  # 跳过匿名类
            
        # 创建或获取类节点
        class_node = self.class_hierarchy.get_or_create_class(class_name)
        class_node.location = f"{cursor.location.file.name}:{cursor.location.line}" if cursor.location.file else ""
        
        # 处理基类
        for child in cursor.get_children():
            if child.kind == CursorKind.CXX_BASE_SPECIFIER:
                base_class = child.get_definition()
                if base_class:
                    base_name = base_class.spelling
                    base_node = self.class_hierarchy.get_or_create_class(base_name)
                    
                    # 添加继承关系
                    class_node.add_base_class(base_name)
                    base_node.add_derived_class(class_name)
                    
                    # 检查访问说明符
                    access_specifier = child.access_specifier
                    class_node.base_class_access[base_name] = str(access_specifier)
        
        # 处理类方法
        for child in cursor.get_children():
            if child.kind == CursorKind.CXX_METHOD:
                method_name = child.spelling
                qualified_name = f"{class_name}::{method_name}"
                
                # 检查是否是虚函数
                is_virtual = child.is_virtual_method()
                is_pure_virtual = child.is_pure_virtual_method() if hasattr(child, 'is_pure_virtual_method') else False
                
                if is_virtual:
                    class_node.add_virtual_method(method_name, is_pure_virtual)
                    
                    # 记录方法信息，包括参数类型，用于后续重写匹配
                    param_types = []
                    for param in child.get_arguments():
                        param_type = param.type.spelling
                        param_types.append(param_type)
                    
                    class_node.method_signatures[method_name] = {
                        'return_type': child.result_type.spelling,
                        'param_types': param_types,
                        'is_const': child.is_const_method(),
                        'access': str(child.access_specifier)
                    }
    
    def _resolve_virtual_methods(self) -> None:
        """解析虚函数重写关系，完善虚函数表。"""
        # 对于每个类
        for class_name, class_node in self.class_hierarchy.classes.items():
            # 对于每个基类
            for base_name in class_node.base_classes:
                if base_name in self.class_hierarchy.classes:
                    base_node = self.class_hierarchy.classes[base_name]
                    
                    # 检查基类的虚方法是否在派生类中被重写
                    for v_method in base_node.virtual_methods:
                        # 在派生类中查找同名方法
                        for child in class_node.get_methods():
                            if child.spelling == v_method:
                                # 检查签名兼容性
                                if self._is_override_compatible(base_node, class_node, v_method):
                                    # 记录重写关系
                                    class_node.add_overridden_method(v_method, base_name)
                                    # 将基类虚方法添加到派生类的虚方法列表
                                    if v_method not in class_node.virtual_methods:
                                        class_node.add_virtual_method(v_method, False)
    
    def _is_override_compatible(self, base_node: ClassNode, derived_node: ClassNode, 
                              method_name: str) -> bool:
        """
        检查派生类方法是否与基类虚方法兼容（可以重写）。
        
        Args:
            base_node: 基类节点
            derived_node: 派生类节点
            method_name: 方法名
            
        Returns:
            如果方法签名兼容，返回True
        """
        # 简单检查 - 将来可以实现更复杂的兼容性检查
        if method_name in base_node.method_signatures and method_name in derived_node.method_signatures:
            base_sig = base_node.method_signatures[method_name]
            derived_sig = derived_node.method_signatures[method_name]
            
            # 检查返回类型、参数数量和类型
            # 注意：C++允许协变返回类型，这里简化处理
            if len(base_sig['param_types']) == len(derived_sig['param_types']):
                # 对于covariant返回类型，这里仅做简单检查
                return True
        
        return False
    
    def get_virtual_method_table(self, class_name: str, visited: Set[str] = None) -> Dict[str, List[str]]:
        """
        获取指定类的虚函数表。
        
        Args:
            class_name: 类名
            visited: 已访问过的类集合，用于检测循环继承
            
        Returns:
            虚函数名到实现它们的类列表的映射
        """
        # 检查缓存
        if class_name in self._vtable_cache:
            return self._vtable_cache[class_name]
            
        # 初始化结果
        vtable = {}
        
        # 初始化已访问类集合（如果没有提供）
        if visited is None:
            visited = set()
            
        # 检测循环引用
        if class_name in visited:
            return vtable  # 发现循环，返回空表
            
        # 将当前类标记为已访问
        visited.add(class_name)
        
        # 检查类是否存在
        if class_name not in self.class_hierarchy.classes:
            return vtable
            
        class_node = self.class_hierarchy.classes[class_name]
        
        # 首先添加基类的虚函数
        for base_name in class_node.base_classes:
            if base_name in self.class_hierarchy.classes:
                # 递归调用，传递已访问类集合
                base_vtable = self.get_virtual_method_table(base_name, visited.copy())
                
                # 合并基类的虚函数表
                for method, implementations in base_vtable.items():
                    if method not in vtable:
                        vtable[method] = implementations.copy()
                    else:
                        # 如果多个基类有相同名称的虚函数，合并它们的实现
                        for impl in implementations:
                            if impl not in vtable[method]:
                                vtable[method].append(impl)
        
        # 添加或更新当前类的虚函数
        for vmethod in class_node.virtual_methods:
            # 检查这个虚函数是否重写了基类方法
            overridden = False
            for base_name in class_node.base_classes:
                if vmethod in class_node.overridden_methods and base_name in class_node.overridden_methods[vmethod]:
                    overridden = True
                    break
            
            if overridden:
                # 这是一个重写 - 更新实现类
                if vmethod in vtable:
                    # 替换基类实现为当前类实现
                    vtable[vmethod] = [class_name]
            else:
                # 这是一个新的虚函数
                vtable[vmethod] = [class_name]
        
        # 缓存结果以便重用
        self._vtable_cache[class_name] = vtable
                
        return vtable
    
    def resolve_virtual_call(self, base_class: str, method_name: str) -> List[str]:
        """
        解析虚函数调用可能调用的实际实现。
        
        Args:
            base_class: 基类名称（通过其指针/引用调用虚函数）
            method_name: 虚函数名称
            
        Returns:
            可能实现此调用的函数列表（类名::方法名格式）
        """
        possible_implementations = []
        
        # 检查基类是否存在
        if base_class not in self.class_hierarchy.classes:
            return [f"{base_class}::{method_name}"]  # 默认实现
            
        base_node = self.class_hierarchy.classes[base_class]
        
        # 检查此方法是否为虚方法
        if method_name not in base_node.virtual_methods:
            return [f"{base_class}::{method_name}"]  # 非虚函数，只有一个实现
        
        # 获取所有派生类
        all_classes = self._get_class_hierarchy(base_class)
        
        # 对于层次结构中的每个类，检查它是否实现/重写了该方法
        for cls in all_classes:
            if cls in self.class_hierarchy.classes:
                class_node = self.class_hierarchy.classes[cls]
                
                # 检查该方法是否在此类中被重写
                if method_name in class_node.virtual_methods:
                    # 对于Pure Virtual函数，只有在非抽象类中才添加实现
                    if not (method_name in class_node.pure_virtual_methods and 
                            cls == base_class):
                        possible_implementations.append(f"{cls}::{method_name}")
        
        return possible_implementations if possible_implementations else [f"{base_class}::{method_name}"]
    
    def _get_class_hierarchy(self, base_class: str) -> List[str]:
        """
        获取从基类开始的完整类层次结构（包括所有派生类）。
        
        Args:
            base_class: 基类名称
            
        Returns:
            类层次结构中的类列表，从基类开始
        """
        result = [base_class]
        visited = set([base_class])
        
        # 广度优先搜索获取所有派生类
        queue = [base_class]
        while queue:
            current = queue.pop(0)
            
            if current in self.class_hierarchy.classes:
                derived_classes = self.class_hierarchy.classes[current].derived_classes
                
                for derived in derived_classes:
                    if derived not in visited:
                        visited.add(derived)
                        result.append(derived)
                        queue.append(derived)
        
        return result
    
    def enrich_function_model(self, functions: Dict[str, Function]) -> None:
        """
        利用类层次结构信息丰富函数模型。
        
        Args:
            functions: 函数字典，键为函数名，值为Function对象
        """
        # 对每个类方法，添加类层次结构信息
        for func_name, func in functions.items():
            if "::" in func_name:  # 类方法
                parts = func_name.split("::")
                class_name = "::".join(parts[:-1])  # 处理嵌套命名空间
                method_name = parts[-1]
                
                # 设置类名
                func.class_name = class_name
                func.is_member = True
                
                # 查找此类在层次结构中的信息
                if class_name in self.class_hierarchy.classes:
                    class_node = self.class_hierarchy.classes[class_name]
                    
                    # 添加类层次结构信息
                    func.class_hierarchy = list(class_node.base_classes)
                    
                    # 检查是否是虚函数以及是否重写了基类方法
                    if method_name in class_node.virtual_methods:
                        func.is_virtual = True
                        
                        # 检查重写关系
                        if method_name in class_node.overridden_methods:
                            for base_class in class_node.overridden_methods[method_name]:
                                func.add_override(f"{base_class}::{method_name}")
                        
                        # 检查是否是纯虚函数
                        if method_name in class_node.pure_virtual_methods:
                            func.is_pure_virtual = True
    
    def resolve_virtual_calls(self, functions: Dict[str, Function]) -> None:
        """
        解析函数调用中的虚函数调用。
        
        Args:
            functions: 函数字典，键为函数名，值为Function对象
        """
        for func_name, func in functions.items():
            # 处理此函数的调用
            new_calls = []
            
            for called_func in func.calls:
                if "::" in called_func:  # 可能是类方法调用
                    parts = called_func.split("::")
                    class_name = "::".join(parts[:-1])
                    method_name = parts[-1]
                    
                    # 检查是否是虚函数调用
                    if class_name in self.class_hierarchy.classes:
                        class_node = self.class_hierarchy.classes[class_name]
                        
                        if method_name in class_node.virtual_methods:
                            # 这是一个虚函数调用，解析可能的实际实现
                            possible_impls = self.resolve_virtual_call(class_name, method_name)
                            
                            # 替换原始调用为所有可能的实现
                            for impl in possible_impls:
                                if impl != called_func and impl not in new_calls:
                                    new_calls.append(impl)
                            
                            # 保留原始调用
                            if called_func not in new_calls:
                                new_calls.append(called_func)
                        else:
                            # 非虚函数调用，保持不变
                            if called_func not in new_calls:
                                new_calls.append(called_func)
                    else:
                        # 未知类，保持调用不变
                        if called_func not in new_calls:
                            new_calls.append(called_func)
                else:
                    # 非类方法调用，保持不变
                    if called_func not in new_calls:
                        new_calls.append(called_func)
            
            # 更新函数的调用列表
            func.calls = new_calls 