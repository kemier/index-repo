"""
C++类层次结构模型，用于表示类的继承关系和虚函数。
"""
from typing import Dict, List, Set, Optional
from dataclasses import dataclass, field


class ClassNode:
    """表示类层次结构中的一个类节点。"""
    
    def __init__(self, name: str):
        """
        初始化类节点。
        
        Args:
            name: 类名
        """
        self.name = name
        self.location = ""  # 类定义的位置（文件:行号）
        
        # 继承关系
        self.base_classes: Set[str] = set()  # 基类集合
        self.derived_classes: Set[str] = set()  # 派生类集合
        self.base_class_access: Dict[str, str] = {}  # 基类到访问说明符的映射
        
        # 虚函数
        self.virtual_methods: Set[str] = set()  # 虚函数集合
        self.pure_virtual_methods: Set[str] = set()  # 纯虚函数集合
        self.overridden_methods: Dict[str, Set[str]] = {}  # 方法名到被重写的基类集合的映射
        
        # 方法签名
        self.method_signatures: Dict[str, Dict] = {}  # 方法名到签名详情的映射
    
    def add_base_class(self, base_class: str) -> None:
        """
        添加基类。
        
        Args:
            base_class: 基类名
        """
        self.base_classes.add(base_class)
    
    def add_derived_class(self, derived_class: str) -> None:
        """
        添加派生类。
        
        Args:
            derived_class: 派生类名
        """
        self.derived_classes.add(derived_class)
    
    def add_virtual_method(self, method_name: str, is_pure: bool = False) -> None:
        """
        添加虚函数。
        
        Args:
            method_name: 方法名
            is_pure: 是否是纯虚函数
        """
        self.virtual_methods.add(method_name)
        if is_pure:
            self.pure_virtual_methods.add(method_name)
    
    def add_overridden_method(self, method_name: str, base_class: str) -> None:
        """
        添加重写的方法。
        
        Args:
            method_name: 方法名
            base_class: 包含被重写方法的基类名
        """
        if method_name not in self.overridden_methods:
            self.overridden_methods[method_name] = set()
        self.overridden_methods[method_name].add(base_class)
    
    def get_methods(self) -> List[object]:
        """
        获取类的所有方法（目前仅用于虚函数检测）。
        
        Returns:
            方法对象列表，每个对象有spelling属性
        """
        class MethodInfo:
            def __init__(self, name):
                self.spelling = name
        
        return [MethodInfo(name) for name in self.method_signatures.keys()]
    
    def to_dict(self) -> Dict:
        """
        将类节点转换为字典表示。
        
        Returns:
            类节点的字典表示
        """
        return {
            "name": self.name,
            "location": self.location,
            "base_classes": list(self.base_classes),
            "derived_classes": list(self.derived_classes),
            "base_class_access": self.base_class_access,
            "virtual_methods": list(self.virtual_methods),
            "pure_virtual_methods": list(self.pure_virtual_methods),
            "overridden_methods": {
                k: list(v) for k, v in self.overridden_methods.items()
            },
            "method_signatures": self.method_signatures
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ClassNode':
        """
        从字典创建类节点。
        
        Args:
            data: 类节点的字典表示
            
        Returns:
            创建的类节点
        """
        node = cls(data["name"])
        node.location = data.get("location", "")
        
        node.base_classes = set(data.get("base_classes", []))
        node.derived_classes = set(data.get("derived_classes", []))
        node.base_class_access = data.get("base_class_access", {})
        
        node.virtual_methods = set(data.get("virtual_methods", []))
        node.pure_virtual_methods = set(data.get("pure_virtual_methods", []))
        
        node.overridden_methods = {
            k: set(v) for k, v in data.get("overridden_methods", {}).items()
        }
        
        node.method_signatures = data.get("method_signatures", {})
        
        return node


class ClassHierarchy:
    """表示整个类层次结构。"""
    
    def __init__(self):
        """初始化类层次结构。"""
        self.classes: Dict[str, ClassNode] = {}
    
    def add_class(self, class_node: ClassNode) -> None:
        """
        添加类到层次结构。
        
        Args:
            class_node: 要添加的类节点
        """
        self.classes[class_node.name] = class_node
    
    def get_class(self, class_name: str) -> Optional[ClassNode]:
        """
        获取类节点。
        
        Args:
            class_name: 类名
            
        Returns:
            类节点，如果不存在则返回None
        """
        return self.classes.get(class_name)
    
    def get_or_create_class(self, class_name: str) -> ClassNode:
        """
        获取类节点，如果不存在则创建一个新的。
        
        Args:
            class_name: 类名
            
        Returns:
            获取或创建的类节点
        """
        if class_name not in self.classes:
            self.classes[class_name] = ClassNode(class_name)
        return self.classes[class_name]
    
    def get_base_classes(self, class_name: str, recursive: bool = False) -> List[str]:
        """
        获取类的基类。
        
        Args:
            class_name: 类名
            recursive: 是否递归获取所有基类
            
        Returns:
            基类列表
        """
        if class_name not in self.classes:
            return []
            
        class_node = self.classes[class_name]
        
        if not recursive:
            return list(class_node.base_classes)
        
        # 递归获取所有基类
        result = []
        visited = set()
        
        def collect_bases(cls_name):
            if cls_name in visited:
                return
            
            visited.add(cls_name)
            
            if cls_name not in self.classes:
                return
                
            node = self.classes[cls_name]
            for base in node.base_classes:
                if base not in result:
                    result.append(base)
                collect_bases(base)
        
        collect_bases(class_name)
        return result
    
    def get_derived_classes(self, class_name: str, recursive: bool = False) -> List[str]:
        """
        获取类的派生类。
        
        Args:
            class_name: 类名
            recursive: 是否递归获取所有派生类
            
        Returns:
            派生类列表
        """
        if class_name not in self.classes:
            return []
            
        class_node = self.classes[class_name]
        
        if not recursive:
            return list(class_node.derived_classes)
        
        # 递归获取所有派生类
        result = []
        visited = set()
        
        def collect_derived(cls_name):
            if cls_name in visited:
                return
            
            visited.add(cls_name)
            
            if cls_name not in self.classes:
                return
                
            node = self.classes[cls_name]
            for derived in node.derived_classes:
                if derived not in result:
                    result.append(derived)
                collect_derived(derived)
        
        collect_derived(class_name)
        return result
    
    def to_dict(self) -> Dict:
        """
        将类层次结构转换为字典表示。
        
        Returns:
            类层次结构的字典表示
        """
        return {
            "classes": {
                name: node.to_dict() for name, node in self.classes.items()
            }
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ClassHierarchy':
        """
        从字典创建类层次结构。
        
        Args:
            data: 类层次结构的字典表示
            
        Returns:
            创建的类层次结构
        """
        hierarchy = cls()
        
        for name, node_data in data.get("classes", {}).items():
            hierarchy.add_class(ClassNode.from_dict(node_data))
        
        return hierarchy 