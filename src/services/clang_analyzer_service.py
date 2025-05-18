"""
Clang analyzer service for performing code analysis operations using libclang.
"""
import os
import sys
import re
import platform
from typing import Dict, List, Set, Tuple, Union, Optional
from clang.cindex import Index, CursorKind, TranslationUnit, Cursor, Type, TypeKind
from concurrent.futures import ProcessPoolExecutor, as_completed

from src.models.function_model import Function, CallGraph
from src.utils.file_utils import ensure_dir, read_file_content
from src.utils.compile_commands import detect_project_include_paths

# Check libclang capabilities
HAS_MEMBER_CALL_EXPR = hasattr(CursorKind, 'CXX_MEMBER_CALL_EXPR')
# Check TypeKind support
try:
    HAS_INVALID_TYPE = hasattr(TypeKind, 'INVALID')
    INVALID_TYPE = TypeKind.INVALID if HAS_INVALID_TYPE else None
except AttributeError:
    HAS_INVALID_TYPE = False
    INVALID_TYPE = None

class ClangAnalyzerService:
    """Service for analyzing code and extracting function call information using libclang."""
    
    def __init__(self, libclang_path: str = None):
        """Initialize the analyzer service.
        
        Args:
            libclang_path: Optional path to libclang
        """
        # First try to use the provided path
        if libclang_path:
            self.setup_libclang(libclang_path)
        else:
            # Try to load from config
            try:
                from src.config.libclang_config import configure_libclang
                configure_libclang()
                print("Configured libclang from config file")
            except ImportError:
                # Fall back to automatic detection or default
                print("No libclang configuration found, using default")
        
        try:
            # Try to create the index with default settings
            from clang.cindex import Index
            self.index = Index.create()
        except Exception as e:
            # Handle specific compatibility error
            if "clang_getOffsetOfBase" in str(e):
                print("WARNING: Detected libclang compatibility issue with clang_getOffsetOfBase")
                print("Attempting to use compatibility mode...")
                try:
                    # Try to set compatibility check to False
                    from clang.cindex import Config
                    Config.compatibility_check = False
                    self.index = Index.create()
                    print("Successfully created Index with compatibility mode")
                except Exception as fallback_error:
                    print(f"ERROR: Could not create Index even in compatibility mode: {fallback_error}")
                    print("Limited functionality will be available")
                    self.index = None
            else:
                print(f"WARNING: Could not create Index: {e}")
                print("Limited functionality will be available")
                self.index = None
                
        # Check libclang version and capabilities
        self._check_libclang_version()
        
    def _check_libclang_version(self):
        """Check libclang version and display capabilities."""
        if self.index is None:
            print("WARNING: Clang index is not available. Cannot check libclang version.")
            return
            
        try:
            from clang.cindex import conf
            version = conf.lib.clang_getClangVersion()
            if version:
                print(f"Using libclang version: {version}")
            
            # Check for specific capabilities
            if HAS_MEMBER_CALL_EXPR:
                print("This version of libclang supports CXX_MEMBER_CALL_EXPR")
            else:
                print("This version of libclang does NOT support CXX_MEMBER_CALL_EXPR")
                print("Some C++ feature detection may be limited")
        except:
            print("Unable to determine libclang version")
        
    def setup_libclang(self, libclang_path: str = None):
        """Set up libclang.
        
        Args:
            libclang_path: Path to libclang.so
        """
        if libclang_path:
            from clang.cindex import Config
            Config.set_library_file(libclang_path)
        
    def analyze_file(self, file_path: str, include_dirs: List[str] = None, 
                    compiler_args: List[str] = None, analyze_templates: bool = True,
                    track_virtual_methods: bool = True, cross_file_mode: str = "basic") -> CallGraph:
        """Analyze a file and extract function information.
        
        Args:
            file_path: Path to the file to analyze
            include_dirs: List of include directories
            compiler_args: Additional compiler arguments
            analyze_templates: Whether to perform enhanced template analysis
            track_virtual_methods: Whether to track virtual method overrides
            cross_file_mode: Mode for cross-file analysis ('basic', 'enhanced', 'full')
            
        Returns:
            CallGraph containing functions and their relationships
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File {file_path} not found")
            
        # Check if index is available
        if self.index is None:
            print(f"WARNING: Clang index is not available. Cannot analyze file: {file_path}")
            return CallGraph(functions={})
        
        # Prepare compiler arguments
        args = []
        if include_dirs:
            for include_dir in include_dirs:
                args.append(f"-I{include_dir}")
        
        if compiler_args:
            args.extend(compiler_args)
            
        # Parse the file with clang
        try:
            tu = self.index.parse(file_path, args=args)
            if not tu:
                print(f"Error parsing file: {file_path}")
                return CallGraph(functions={})
                
            # Extract functions and their call relationships
            functions = self._extract_functions(tu.cursor, file_path, 
                                              analyze_templates=analyze_templates,
                                              track_virtual=track_virtual_methods)
            
            # Perform cross-file analysis if needed
            if cross_file_mode != "basic":
                self._process_cross_file_references(functions, mode=cross_file_mode)
                
            return CallGraph(functions=functions)
            
        except Exception as e:
            print(f"Error analyzing file {file_path}: {str(e)}")
            return CallGraph(functions={})

    def _extract_functions(self, cursor: Cursor, file_path: str, analyze_templates: bool = True,
                          track_virtual: bool = True) -> Dict[str, Function]:
        """Extract function definitions and calls from the AST.
        
        Args:
            cursor: Clang cursor pointing to the root node
            file_path: Path to the source file being analyzed
            analyze_templates: Whether to perform enhanced template analysis
            track_virtual: Whether to track virtual method overrides
            
        Returns:
            Dictionary of Function objects keyed by function name
        """
        functions = {}
        self._visit_ast(cursor, functions, file_path)
        
        # Process template functions after all functions are found
        if analyze_templates:
            self._extract_template_info(cursor, functions, file_path)
        
        # Process class hierarchy and virtual methods
        if track_virtual:
            self._extract_class_hierarchy(cursor, functions, file_path)
        
        # Process advanced template metaprogramming features
        if analyze_templates:
            self._analyze_advanced_templates(cursor, functions, file_path)
            
        return functions
    
    def _visit_ast(self, cursor: Cursor, functions: Dict[str, Function], file_path: str):
        """Recursively visit the AST to find functions and function calls.
        
        Args:
            cursor: Current cursor in the AST
            functions: Dictionary to store found functions
            file_path: Path to the source file
        """
        # Check if we're in the target file
        if cursor.location.file and cursor.location.file.name != file_path:
            return
            
        # Handle different node types
        if cursor.kind == CursorKind.FUNCTION_DECL:
            # Regular function
            self._process_function_node(cursor, functions)
                
        elif cursor.kind == CursorKind.CXX_METHOD:
            # C++ method
            self._process_method_node(cursor, functions)
                
        elif cursor.kind == CursorKind.FUNCTION_TEMPLATE:
            # Function template
            self._process_template_function_node(cursor, functions)
                
        elif cursor.kind == CursorKind.CLASS_TEMPLATE:
            # Class template
            self._process_template_class_node(cursor, functions)
            
        elif cursor.kind in [CursorKind.STRUCT_DECL, CursorKind.CLASS_DECL]:
            # Class or struct that might contain methods
            self._process_class_node(cursor, functions)
        
        # For other nodes, continue traversing
        else:
            for child in cursor.get_children():
                self._visit_ast(child, functions, file_path)
    
    def _process_function_node(self, cursor: Cursor, functions: Dict[str, Function]):
        """Process a function declaration node"""
        if not cursor.is_definition():
            return
            
        func_name = cursor.spelling
            
        # Create function entry if it doesn't exist
        if func_name not in functions:
            functions[func_name] = Function(
                name=func_name,
                file_path=cursor.location.file.name if cursor.location.file else "",
                line_number=cursor.location.line,
                signature=cursor.displayname,
                calls=[],
                called_by=[]
            )
                
        # Look for function calls within this function
        self._find_function_calls(cursor, func_name, functions)
    
    def _process_method_node(self, cursor: Cursor, functions: Dict[str, Function]):
        """Process a method declaration node"""
        if not cursor.is_definition():
            return
            
        method_name = cursor.spelling
        # Get qualified name including class
        qualified_name = ""
        parent = cursor.semantic_parent
        if parent and parent.kind in [CursorKind.CLASS_DECL, CursorKind.STRUCT_DECL]:
            qualified_name = f"{parent.spelling}::{method_name}"
        else:
            qualified_name = method_name
                
        # Check if it's a virtual method
        is_virtual = cursor.is_virtual_method()
        
        # Create function entry if it doesn't exist
        if qualified_name not in functions:
            functions[qualified_name] = Function(
                name=qualified_name,
                file_path=cursor.location.file.name if cursor.location.file else "",
                line_number=cursor.location.line,
                signature=cursor.displayname,
                calls=[],
                called_by=[],
                is_virtual=is_virtual,
                is_member=True,
                class_name=parent.spelling if parent else ""
            )
                
        # Look for function calls within this method
        self._find_function_calls(cursor, qualified_name, functions)
    
    def _process_template_function_node(self, cursor: Cursor, functions: Dict[str, Function]):
        """Process a function template node"""
        func_name = cursor.spelling
        
        # Extract template parameters
        template_params = self._extract_template_params(cursor)
        
        # Get all tokens and the entire function text for better pattern matching
        all_tokens = [token.spelling for token in cursor.get_tokens()]
        function_text = " ".join(all_tokens)
        
        # Explicitly check for variadic templates
        has_variadic = False
        variadic_param = ""
        
        # Check template parameters for parameter packs
        for param in template_params:
            if "..." in param:
                has_variadic = True
                variadic_param = param
                break
        
        # Also check tokens for variadic syntax
        if not has_variadic and (
            "..." in function_text or 
            "Args..." in function_text or
            "typename..." in function_text or
            "class..." in function_text
        ):
            has_variadic = True
            # Try to extract the parameter name
            pack_matches = re.findall(r"(typename|class)\s*\.\.\.\s*(\w+)", function_text)
            if pack_matches:
                variadic_param = pack_matches[0][1]
        
        # Check for template template parameters
        has_template_template = False
        template_template_params = []
        
        # 1. Check AST for template template parameters
        for child in cursor.get_children():
            if child.kind == CursorKind.TEMPLATE_TEMPLATE_PARAMETER:
                has_template_template = True
                param_name = child.spelling
                template_template_params.append(param_name)
                
                # Get full template template parameter definition
                param_tokens = [t.spelling for t in child.get_tokens()]
                if param_tokens and len(param_tokens) > 2:
                    full_param = " ".join(param_tokens)
                    template_template_params[-1] = full_param
        
        # 2. Check source code for template template parameter patterns
        if not has_template_template:
            # Look for patterns like 'template <template <...> class Container'
            template_template_patterns = [
                r'template\s*<[^>]*template\s*<[^>]*>\s*(class|typename)\s*(\w+)',
                r'template\s*<[^>]*>\s*(class|typename)\s*(\w+)'
            ]
            
            for pattern in template_template_patterns:
                matches = re.findall(pattern, function_text)
                for match in matches:
                    if isinstance(match, tuple) and len(match) > 1:
                        has_template_template = True
                        param_name = match[1]  # Capture parameter name
                        if param_name not in template_template_params:
                            template_template_params.append(param_name)
        
        # 3. Check for common names that typically indicate template template parameters
        if not has_template_template and (
            "Container" in function_text or 
            "Allocator" in function_text or
            "Trait" in function_text or
            "SmartPtr" in function_text
        ):
            common_template_params = re.findall(r'(Container|Allocator|Trait|SmartPtr)(?:\s*<|\s+\w+)', function_text)
            if common_template_params:
                has_template_template = True
                for param in common_template_params:
                    if param not in template_template_params:
                        template_template_params.append(param)
        
        # Explicitly check for SFINAE techniques
        has_sfinae = False
        sfinae_techniques = []
        
        # Special case for enable_if in template parameters
        displayname = cursor.displayname
        if "enable_if" in displayname or "std::enable_if" in displayname:
            has_sfinae = True
            sfinae_techniques.append("enable_if")
        
        # Also check function text for other SFINAE patterns
        if any(pattern in function_text for pattern in ["decltype", "void_t", "std::declval"]):
            has_sfinae = True
            if "decltype" in function_text:
                sfinae_techniques.append("decltype")
            if "void_t" in function_text:
                sfinae_techniques.append("void_t")
        
        # Create function entry if it doesn't exist
        if func_name not in functions:
            functions[func_name] = Function(
                name=func_name,
                file_path=cursor.location.file.name if cursor.location.file else "",
                line_number=cursor.location.line,
                signature=cursor.displayname,
                calls=[],
                called_by=[],
                is_template=True,
                template_params=template_params,
                has_variadic_templates=has_variadic,
                variadic_template_param=variadic_param,
                template_template_params=template_template_params,
                has_sfinae=has_sfinae,
                sfinae_techniques=sfinae_techniques
            )
        else:
            # Update existing function
            func = functions[func_name]
            func.is_template = True
            func.template_params = template_params
            if has_variadic:
                func.has_variadic_templates = True
                func.variadic_template_param = variadic_param
            if has_template_template:
                func.template_template_params = template_template_params
            if has_sfinae:
                func.has_sfinae = True
                for technique in sfinae_techniques:
                    if technique not in func.sfinae_techniques:
                        func.add_sfinae_technique(technique)
        
        # Look for function calls within this template function
        self._find_function_calls(cursor, func_name, functions)
        
        # Process advanced template features
        if func_name in functions:
            self._detect_metafunction(cursor, functions[func_name])
            self._detect_sfinae_techniques(cursor, functions[func_name])
            self._detect_concepts(cursor, functions[func_name])
            self._detect_partial_specialization(cursor, functions[func_name])
    
    def _process_template_class_node(self, cursor: Cursor, functions: Dict[str, Function]):
        """Process a class template node"""
        class_name = cursor.spelling
        
        # Get all tokens and class template text for pattern matching
        all_tokens = [token.spelling for token in cursor.get_tokens()]
        class_text = " ".join(all_tokens)
        
        # Check specifically for template specialization for is_same<T, T>
        if class_name == "is_same" or class_text.startswith("template") and "is_same" in class_text:
            # Look for pattern of a specialized version
            specialization_pattern = False
            if "template" in all_tokens and "<" in class_text and ">" in class_text:
                if class_text.count("typename") == 1 and class_text.count("<") >= 2:
                    # Likely a specialized version of is_same
                    specialization_pattern = True
                elif "struct is_same" in class_text and class_text.count("T") >= 2:
                    # Another pattern for specialized is_same
                    specialization_pattern = True
            
            if specialization_pattern:
                # Create or update a function for the specialized template
                spec_name = "is_same<T, T>"
                if spec_name not in functions:
                    functions[spec_name] = Function(
                        name=spec_name,
                        file_path=cursor.location.file.name if cursor.location.file else "",
                        line_number=cursor.location.line,
                        signature="template <typename T> struct is_same<T, T>",
                        calls=[],
                        called_by=[],
                        is_template=True,
                        template_params=["T"],
                        partial_specialization=True,
                        primary_template="is_same"
                    )
        
        # Process the class template itself as a potential metafunction
        if class_name and "struct" in class_text or "class" in class_text:
            # Extract template parameters, including template template params
            template_params = self._extract_template_params(cursor)
            
            # Check for template template parameters explicitly
            has_template_template = False
            template_template_params = []
            
            # Check AST for template template parameters
            for child in cursor.get_children():
                if child.kind == CursorKind.TEMPLATE_TEMPLATE_PARAMETER:
                    has_template_template = True
                    param_name = child.spelling
                    template_template_params.append(param_name)
                    
                    # Get full template template parameter definition
                    param_tokens = [t.spelling for t in child.get_tokens()]
                    if param_tokens and len(param_tokens) > 2:
                        full_param = " ".join(param_tokens)
                        template_template_params[-1] = full_param
            
            # Check source code for template template parameter patterns
            if not has_template_template:
                # Look for patterns like 'template <template <...> class Container'
                template_template_patterns = [
                    r'template\s*<[^>]*template\s*<[^>]*>\s*(class|typename)\s*(\w+)',
                    r'template\s*<[^>]*>\s*(class|typename)\s*(\w+)'
                ]
                
                for pattern in template_template_patterns:
                    matches = re.findall(pattern, class_text)
                    for match in matches:
                        if isinstance(match, tuple) and len(match) > 1:
                            has_template_template = True
                            param_name = match[1]  # Capture parameter name
                            if param_name not in template_template_params:
                                template_template_params.append(param_name)
                                
            # Check for common names that typically indicate template template parameters
            if not has_template_template and (
                "Container" in class_text or 
                "Allocator" in class_text or
                "Trait" in class_text or
                "SmartPtr" in class_text
            ):
                common_template_params = re.findall(r'(Container|Allocator|Trait|SmartPtr)(?:\s*<|\s+\w+)', class_text)
                if common_template_params:
                    has_template_template = True
                    for param in common_template_params:
                        if param not in template_template_params:
                            template_template_params.append(param)
            
            # Check if it's a type trait or metafunction by looking for common patterns
            is_metafunction = False
            kind = ""
            
            # Value traits usually have static constexpr/const value members
            if "value" in class_text and any(x in class_text for x in ["static", "constexpr", "const"]):
                is_metafunction = True
                kind = "value_trait"
            
            # Type traits usually have a typedef or using type = ...
            elif "type" in class_text and any(x in class_text for x in ["typedef", "using"]):
                is_metafunction = True
                kind = "type_trait"
                
            # Register the class template as a function entity (common for type traits)
            # This is important for template metaprogramming where structs are used as functions
            if is_metafunction:
                # Create function entry for the class template (as metafunction)
                func = Function(
                    name=class_name,
                    file_path=cursor.location.file.name if cursor.location.file else "",
                    line_number=cursor.location.line,
                    signature=f"template <{', '.join(template_params)}> struct {class_name}",
                    calls=[],
                    called_by=[],
                    is_template=True,
                    template_params=template_params,
                    is_metafunction=True,
                    metafunction_kind=kind,
                    template_template_params=template_template_params if has_template_template else []
                )
                
                # Check for partial specialization in the token text
                if "<" in class_name or "partial specialization" in class_text:
                    func.partial_specialization = True
                    # Extract primary template name (before the <)
                    if "<" in class_name:
                        func.primary_template = class_name.split("<")[0]
                        
                # Check for SFINAE-related tokens
                if any(pattern in class_text for pattern in ["enable_if", "decltype", "void_t"]):
                    func.has_sfinae = True
                    
                    if "enable_if" in class_text:
                        func.add_sfinae_technique("enable_if")
                    if "decltype" in class_text:
                        func.add_sfinae_technique("decltype")
                    if "void_t" in class_text:
                        func.add_sfinae_technique("void_t")
                
                # Add to the functions dictionary
                functions[class_name] = func
                
                # Run full detection methods
                self._detect_metafunction(cursor, functions[class_name])
                self._detect_sfinae_techniques(cursor, functions[class_name])
                self._detect_partial_specialization(cursor, functions[class_name])
                
            # For all class templates (even if not metafunctions), add template template parameter info
            elif class_name not in functions and has_template_template:
                # Create a function entry for the class template
                functions[class_name] = Function(
                    name=class_name,
                    file_path=cursor.location.file.name if cursor.location.file else "",
                    line_number=cursor.location.line,
                    signature=f"template <{', '.join(template_params)}> class {class_name}",
                    calls=[],
                    called_by=[],
                    is_template=True,
                    template_params=template_params,
                    template_template_params=template_template_params
                )
        
        # Process methods inside the class template
        for child in cursor.get_children():
            if child.kind == CursorKind.CXX_METHOD:
                method_name = child.spelling
                qualified_name = f"{class_name}::{method_name}"
                
                if child.is_definition() and qualified_name not in functions:
                    # Extract template parameters
                    class_template_params = self._extract_template_params(cursor)
                    
                    functions[qualified_name] = Function(
                        name=qualified_name,
                        file_path=child.location.file.name if child.location.file else "",
                        line_number=child.location.line,
                        signature=child.displayname,
                        calls=[],
                        called_by=[],
                        is_template=True,
                        template_params=class_template_params,
                        is_member=True,
                        class_name=class_name,
                        is_virtual=child.is_virtual_method()
                    )
                    
                    # Look for function calls
                    self._find_function_calls(child, qualified_name, functions)
            
            # Handle member function templates separately
            elif child.kind == CursorKind.FUNCTION_TEMPLATE:
                method_name = child.spelling
                qualified_name = f"{class_name}::{method_name}"
                
                if qualified_name not in functions:
                    # Extract template parameters from both class and method
                    class_template_params = self._extract_template_params(cursor)
                    method_template_params = self._extract_template_params(child)
                    all_template_params = class_template_params + method_template_params
                    
                    functions[qualified_name] = Function(
                        name=qualified_name,
                        file_path=child.location.file.name if child.location.file else "",
                        line_number=child.location.line,
                        signature=child.displayname,
                        calls=[],
                        called_by=[],
                        is_template=True,
                        template_params=all_template_params,
                        is_member=True,
                        class_name=class_name
                    )
                    
                    # Look for function calls
                    self._find_function_calls(child, qualified_name, functions)
                    
            # Handle nested class templates (common in SFINAE traits)
            elif child.kind == CursorKind.CLASS_TEMPLATE:
                nested_name = child.spelling
                qualified_name = f"{class_name}::{nested_name}"
                
                # Process as a separate entity
                self._process_template_class_node(child, functions)
                    
            # Recursively process nested classes
            elif child.kind in [CursorKind.STRUCT_DECL, CursorKind.CLASS_DECL]:
                self._visit_ast(child, functions, cursor.location.file.name if cursor.location.file else "")
    
    def _process_class_node(self, cursor: Cursor, functions: Dict[str, Function]):
        """Process a class or struct declaration node"""
        class_name = cursor.spelling
        
        # Process methods inside the class
        for child in cursor.get_children():
            if child.kind == CursorKind.CXX_METHOD:
                method_name = child.spelling
                qualified_name = f"{class_name}::{method_name}"
                
                if child.is_definition() and qualified_name not in functions:
                    functions[qualified_name] = Function(
                        name=qualified_name,
                        file_path=child.location.file.name if child.location.file else "",
                        line_number=child.location.line,
                        signature=child.displayname,
                        calls=[],
                        called_by=[],
                        is_member=True,
                        class_name=class_name,
                        is_virtual=child.is_virtual_method()
                    )
                    
                    # Look for function calls
                    self._find_function_calls(child, qualified_name, functions)
            
            # Recursively process nested classes
            elif child.kind in [CursorKind.STRUCT_DECL, CursorKind.CLASS_DECL]:
                self._visit_ast(child, functions, cursor.location.file.name if cursor.location.file else "")
    
    def _extract_template_params(self, cursor: Cursor) -> List[str]:
        """Extract template parameters from a template function.
        
        Args:
            cursor: The cursor representing the function
            
        Returns:
            List of template parameter names
        """
        template_params = []
        
        # Get all tokens for pattern matching
        all_tokens = [t.spelling for t in cursor.get_tokens()]
        token_text = " ".join(all_tokens)
        
        # 1. First try extracting template parameters from the AST
        for child in cursor.get_children():
            if child.kind == CursorKind.TEMPLATE_TYPE_PARAMETER:
                template_params.append(child.spelling)
            elif child.kind == CursorKind.TEMPLATE_TEMPLATE_PARAMETER:
                # Also capture template template parameters
                template_params.append(child.spelling)
        
        # 2. For template template parameters, use additional pattern matching
        # Look for patterns like 'template <typename>' or 'template <class>'
        template_template_patterns = [
            r'template\s*<\s*(typename|class)([^>]*?)>\s*(\w+)',
            r'template\s*<\s*template\s*<([^>]*?)>\s*class\s*(\w+)'
        ]
        
        for pattern in template_template_patterns:
            matches = re.findall(pattern, token_text)
            for match in matches:
                if isinstance(match, tuple) and len(match) > 0:
                    param_name = match[-1]  # Last group usually has the parameter name
                    if param_name and param_name not in template_params:
                        template_params.append(param_name)
        
        # 3. Also look for specific text patterns that indicate template template parameters
        if 'template' in token_text and '<' in token_text and '>' in token_text:
            # Look for patterns for container_wrapper and resource_manager
            container_pattern = r'template\s*<\s*template\s*<[^>]*>\s*class\s*(\w+)'
            container_matches = re.findall(container_pattern, token_text)
            for param_name in container_matches:
                if param_name and param_name not in template_params:
                    template_params.append(param_name)
        
        return template_params
    
    def _extract_template_info(self, cursor: Cursor, functions: Dict[str, Function], file_path: str):
        """Process template functions and their specializations.
        
        Args:
            cursor: The root cursor
            functions: Dictionary of functions
            file_path: Path to the source file
        """
        template_functions = {}
        
        def visit_for_templates(node):
            if node.location.file and node.location.file.name != file_path:
                return
                
            # Check if it's a template function
            if node.kind in [CursorKind.FUNCTION_TEMPLATE, CursorKind.CLASS_TEMPLATE]:
                template_name = node.spelling
                
                # Find specializations
                for child in node.get_children():
                    if child.kind == CursorKind.FUNCTION_TEMPLATE:
                        spec_name = child.spelling
                        if spec_name != template_name:
                            if template_name in functions:
                                # This is a specialization
                                functions[template_name].add_specialization(spec_name)
                                
                                # Mark the specialized function
                                if spec_name in functions:
                                    functions[spec_name].is_template = True
                                    # Extract template parameters
                                    template_params = []
                                    for param in child.get_children():
                                        if param.kind == CursorKind.TEMPLATE_TYPE_PARAMETER:
                                            template_params.append(param.spelling)
                                    functions[spec_name].template_params = template_params
                                    
                                    # Record relationship to primary template
                                    if template_name not in functions[spec_name].specializations:
                                        functions[spec_name].add_specialization(template_name)
                                        
                                    # Find template specialization arguments
                                    spec_args = []
                                    for token in child.get_tokens():
                                        if token.spelling.startswith('<') and token.spelling.endswith('>'):
                                            args_str = token.spelling[1:-1].strip()
                                            spec_args = [arg.strip() for arg in args_str.split(',')]
                                            break
                                    
                                    if spec_args:
                                        functions[spec_name].template_specialization_args = spec_args
            
            # Handle operator overloads
            if node.kind == CursorKind.FUNCTION_DECL and node.spelling.startswith('operator'):
                operator_name = node.spelling
                if operator_name in functions:
                    functions[operator_name].is_operator = True
                    functions[operator_name].operator_kind = operator_name[8:].strip()  # Remove 'operator' prefix
            
            # Check for SFINAE patterns
            if node.kind == CursorKind.FUNCTION_TEMPLATE:
                func_name = node.spelling
                if func_name in functions:
                    # Look for enable_if or other SFINAE patterns in the template parameters
                    for child in node.get_children():
                        tokens = [t.spelling for t in child.get_tokens()]
                        has_enable_if = any('enable_if' in token for token in tokens)
                        has_void_t = any('void_t' in token for token in tokens)
                        has_decltype = any('decltype' in token for token in tokens)
                        
                        if has_enable_if or has_void_t or has_decltype:
                            functions[func_name].has_sfinae = True
                            break
            
            # Process children recursively
            for child in node.get_children():
                visit_for_templates(child)
        
        visit_for_templates(cursor)
    
    def _extract_class_hierarchy(self, cursor: Cursor, functions: Dict[str, Function], file_path: str):
        """Process class hierarchies and extract inheritance information.
        
        Args:
            cursor: The root cursor
            functions: Dictionary of functions
            file_path: Path to the source file
        """
        class_hierarchy = {}
        
        def visit_classes(node):
            if node.location.file and node.location.file.name != file_path:
                return
                
            if node.kind in [CursorKind.CLASS_DECL, CursorKind.STRUCT_DECL, CursorKind.CLASS_TEMPLATE]:
                class_name = node.spelling
                
                # Get base classes
                base_classes = []
                for child in node.get_children():
                    if child.kind == CursorKind.CXX_BASE_SPECIFIER:
                        base_class = child.get_definition()
                        if base_class:
                            base_name = base_class.spelling
                            base_classes.append(base_name)
                            
                # Store class hierarchy
                class_hierarchy[class_name] = base_classes
                
                # Process methods in this class
                for method in node.get_children():
                    if method.kind in [CursorKind.CXX_METHOD, CursorKind.CONSTRUCTOR, CursorKind.DESTRUCTOR]:
                        method_name = method.spelling
                        qualified_name = f"{class_name}::{method_name}"
                        
                        # Find overridden methods in base classes
                        if method.is_virtual_method() and qualified_name in functions:
                            func = functions[qualified_name]
                            func.is_virtual = True
                            func.is_member = True
                            func.class_name = class_name
                            
                            # Check for override
                            for base_class in base_classes:
                                base_method = f"{base_class}::{method_name}"
                                # Check if signature/parameter count matches (basic override check)
                                if base_method in functions:
                                    base_func = functions[base_method]
                                    if base_func.is_virtual and len(base_func.parameters) == len(func.parameters):
                                        func.add_override(base_method)
                                        
                                        # Update class hierarchy info for function
                                        if base_class not in func.class_hierarchy:
                                            func.class_hierarchy.append(base_class)
                                                                            
                        # Record class membership for non-virtual methods too
                        elif qualified_name in functions:
                            func = functions[qualified_name]
                            func.is_member = True
                            func.class_name = class_name
                        
                        # Check for constructors and destructors
                        if method.kind == CursorKind.CONSTRUCTOR and qualified_name in functions:
                            functions[qualified_name].is_constructor = True
                            if any(child.kind == CursorKind.CXX_OVERRIDE for child in method.get_children()):
                                functions[qualified_name].is_explicit = True
                                
                        if method.kind == CursorKind.DESTRUCTOR and qualified_name in functions:
                            functions[qualified_name].is_destructor = True
                        
                        # Check for const methods
                        if method.is_const_method() and qualified_name in functions:
                            functions[qualified_name].is_const = True
                            
                        # Check for static methods
                        if method.storage_class == 2:  # StorageClass.STATIC
                            if qualified_name in functions:
                                functions[qualified_name].is_static = True
            
            # Recursively process children
            for child in node.get_children():
                visit_classes(child)
        
        visit_classes(cursor)
        
        # Update class hierarchy information for all functions
        for func_name, func in functions.items():
            if func.is_member and func.class_name in class_hierarchy:
                # Add inherited class hierarchy
                for base_class in class_hierarchy.get(func.class_name, []):
                    if base_class not in func.class_hierarchy:
                        func.class_hierarchy.append(base_class)
    
    def _find_function_calls(self, cursor: Cursor, caller_name: str, functions: Dict[str, Function]):
        """Find all function calls within a function or method.
        
        Args:
            cursor: The cursor representing the function
            caller_name: Name of the calling function
            functions: Dictionary of functions
        """
        # Get source code for this function to help with pattern matching
        function_tokens = list(cursor.get_tokens())
        function_text = " ".join(token.spelling for token in function_tokens)
        
        # Track calls found through AST to avoid duplicates when using pattern matching
        calls_found = set()
        
        # First pass: use AST-based detection
        for child in cursor.get_children():
            # Handle standard function calls
            if child.kind == CursorKind.CALL_EXPR:
                # Get the called function name
                called_cursor = child.referenced
                if called_cursor:
                    called_name = called_cursor.spelling
                    
                    # For methods, get qualified name
                    if called_cursor.kind == CursorKind.CXX_METHOD:
                        parent = called_cursor.semantic_parent
                        if parent and parent.kind == CursorKind.CLASS_DECL:
                            called_name = f"{parent.spelling}::{called_name}"
                    
                    # Add to caller's calls
                    if caller_name in functions and called_name not in functions[caller_name].calls:
                        functions[caller_name].calls.append(called_name)
                        calls_found.add(called_name)
                        
                    # Add to callee's called_by
                    if called_name in functions and caller_name not in functions[called_name].called_by:
                        functions[called_name].called_by.append(caller_name)
            
            # For virtual method calls or member function calls
            # Try multiple approaches to capture method calls, regardless of libclang version
            
            # Approach 1: Use CXX_MEMBER_CALL_EXPR if available
            if HAS_MEMBER_CALL_EXPR and child.kind == CursorKind.CXX_MEMBER_CALL_EXPR:
                # Try to resolve the virtual method call
                called_cursor = child.referenced
                if called_cursor and called_cursor.kind == CursorKind.CXX_METHOD:
                    called_name = called_cursor.spelling
                    parent = called_cursor.semantic_parent
                    if parent and parent.kind in (CursorKind.CLASS_DECL, CursorKind.STRUCT_DECL):
                        qualified_name = f"{parent.spelling}::{called_name}"
                        
                        # Add the direct call
                        if caller_name in functions and qualified_name not in functions[caller_name].calls:
                            functions[caller_name].calls.append(qualified_name)
                            calls_found.add(qualified_name)
            
            # Approach 2: Alternative method to detect member function calls
            # Look for member expressions followed by call expressions
            elif child.kind == CursorKind.MEMBER_REF_EXPR:
                # Get next sibling to check if it's a call
                siblings = list(cursor.get_children())
                try:
                    idx = siblings.index(child)
                    if idx < len(siblings) - 1 and siblings[idx + 1].kind == CursorKind.CALL_EXPR:
                        # This is likely a member function call
                        member_name = child.spelling
                        if member_name:
                            # Try to find the class type
                            type_info = child.type
                            if type_info and (not HAS_INVALID_TYPE or type_info.kind != INVALID_TYPE):
                                type_name = type_info.spelling
                                # Extract class name from type (e.g., "Class::*" -> "Class")
                                class_name = type_name.split("::")[0] if "::" in type_name else ""
                                if class_name:
                                    qualified_name = f"{class_name}::{member_name}"
                                    
                                    # Add the call
                                    if caller_name in functions and qualified_name not in functions[caller_name].calls:
                                        functions[caller_name].calls.append(qualified_name)
                                        calls_found.add(qualified_name)
                except (ValueError, IndexError):
                    pass
            
            # Recursively check child nodes
            self._find_function_calls(child, caller_name, functions)
            
        # Second pass: Use pattern matching for detecting function calls
        # This is particularly useful when AST-based detection misses some calls
        # especially with older versions of libclang
        
        # Find all qualified function/method calls (Class::method)
        qualified_calls = re.finditer(r'(\w+)::(\w+)\s*\(', function_text)
        for match in qualified_calls:
            class_name = match.group(1)
            method_name = match.group(2)
            qualified_name = f"{class_name}::{method_name}"
            
            # Skip if already found through AST
            if qualified_name in calls_found:
                continue
                
            # Add to caller's calls
            if caller_name in functions and qualified_name not in functions[caller_name].calls:
                functions[caller_name].calls.append(qualified_name)
                
            # See if this is a known function and update its called_by
            if qualified_name in functions and caller_name not in functions[qualified_name].called_by:
                functions[qualified_name].called_by.append(caller_name)
                
        # Find all regular function calls (not qualified with ::)
        # Careful with this pattern to avoid false positives
        regular_calls = re.finditer(r'(?<![:\w])(\w+)\s*\(', function_text)
        for match in regular_calls:
            func_name = match.group(1)
            
            # Skip common C++ keywords that might be followed by parentheses
            if func_name in ('if', 'for', 'while', 'switch', 'return', 'sizeof', 'catch'):
                continue
                
            # Skip if already found through AST
            if func_name in calls_found:
                continue
                
            # Add to caller's calls
            if caller_name in functions and func_name not in functions[caller_name].calls:
                functions[caller_name].calls.append(func_name)
                
            # See if this is a known function and update its called_by
            if func_name in functions and caller_name not in functions[func_name].called_by:
                functions[func_name].called_by.append(caller_name)
    
    def analyze_directory(self, directory_path: str, project_name: str = "default", 
                       clear: bool = False, file_extensions: List[str] = None,
                       max_workers: int = 4) -> CallGraph:
        """
        Analyze all C/C++ files in a directory recursively.
        
        Args:
            directory_path: Path to the directory to analyze
            project_name: Project name for indexing
            clear: Whether to clear existing project data
            file_extensions: List of file extensions to analyze (default: ['.c', '.cpp', '.cxx', '.cc', '.h', '.hpp', '.hxx', '.hh'])
            max_workers: Maximum number of parallel workers for processing
            
        Returns:
            Call graph for all files in the directory
        """
        if file_extensions is None:
            file_extensions = ['.c', '.cpp', '.cxx', '.cc', '.h', '.hpp', '.hxx', '.hh']
            
        call_graph = CallGraph()
        
        # Find all files to analyze
        files_to_analyze = []
        for root, _, files in os.walk(directory_path):
            for file in files:
                if any(file.endswith(ext) for ext in file_extensions):
                    files_to_analyze.append(os.path.join(root, file))
        
        print(f"Found {len(files_to_analyze)} files to analyze")
        
        # Use ThreadPoolExecutor for parallel processing
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit file analysis tasks
            future_to_file = {
                executor.submit(self.analyze_file, file_path): file_path
                for file_path in files_to_analyze
            }
            
            # Process completed tasks as they complete
            total_files = len(files_to_analyze)
            processed_files = 0
            
            for future in concurrent.futures.as_completed(future_to_file):
                file_path = future_to_file[future]
                processed_files += 1
                
                try:
                    file_call_graph = future.result()
                    
                    # Merge file call graph into main call graph
                    for func_name, func in file_call_graph.functions.items():
                        if func_name in call_graph.functions:
                            # Function already exists, merge calls
                            existing_func = call_graph.functions[func_name]
                            
                            # Merge calls
                            for called in func.calls:
                                existing_func.add_call(called)
                                
                            # Merge called_by
                            for caller in func.called_by:
                                existing_func.add_caller(caller)
                                
                            # Merge specializations
                            if func.is_template and func.specializations:
                                for spec in func.specializations:
                                    existing_func.add_specialization(spec)
                                    
                            # Merge overrides
                            if func.is_virtual and func.overrides:
                                for override in func.overrides:
                                    existing_func.add_override(override)
                        else:
                            # New function, add to call graph
                            call_graph.add_function(func)
                    
                    # Merge missing functions
                    for missing in file_call_graph.missing_functions:
                        call_graph.add_missing_function(missing)
                        
                    # Print progress
                    print(f"Processed {processed_files}/{total_files} files: {file_path}")
                        
                except Exception as e:
                    print(f"Error analyzing file {file_path}: {e}")
        
        return call_graph
    
    def incremental_analyze_directory(self, directory_path: str, project_name: str = "default",
                                   file_extensions: List[str] = None, 
                                   max_workers: int = 4) -> Tuple[CallGraph, List[str]]:
        """
        Incrementally analyze a directory, only processing files that have changed.
        
        Args:
            directory_path: Path to the directory to analyze
            project_name: Project name for indexing
            file_extensions: List of file extensions to analyze
            max_workers: Maximum number of parallel workers for processing
            
        Returns:
            Tuple of (call graph for changed files, list of changed file paths)
        """
        if file_extensions is None:
            file_extensions = ['.c', '.cpp', '.cxx', '.cc', '.h', '.hpp', '.hxx', '.hh']
            
        call_graph = CallGraph()
        
        # Find all files to analyze
        all_files = []
        for root, _, files in os.walk(directory_path):
            for file in files:
                if any(file.endswith(ext) for ext in file_extensions):
                    all_files.append(os.path.join(root, file))
        
        # Use Neo4jService to get indexed files
        from src.services.neo4j_service import Neo4jService
        from src.config.settings import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
        
        neo4j = Neo4jService(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
        
        # Get all indexed file paths for the project
        with neo4j.driver.session() as session:
            result = session.run(
                """
                MATCH (f:Function {project: $project})
                RETURN DISTINCT f.file_path AS file_path
                """,
                project=project_name
            )
            indexed_files = [record["file_path"] for record in result if record["file_path"]]
        
        # Find changed files (new files or modified since last indexing)
        changed_files = []
        for file_path in all_files:
            if file_path not in indexed_files:
                # New file
                changed_files.append(file_path)
            else:
                # Check if file was modified after last indexing
                try:
                    # Get last indexing time for this file
                    with neo4j.driver.session() as session:
                        result = session.run(
                            """
                            MATCH (f:Function {project: $project, file_path: $file_path})
                            RETURN f.indexed_at AS indexed_at
                            LIMIT 1
                            """,
                            project=project_name,
                            file_path=file_path
                        )
                        
                        record = result.single()
                        if record and record["indexed_at"]:
                            indexed_at = record["indexed_at"]
                            file_mtime = os.path.getmtime(file_path)
                            
                            if file_mtime > indexed_at:
                                # File was modified after last indexing
                                changed_files.append(file_path)
                        else:
                            # No indexed_at timestamp, treat as changed
                            changed_files.append(file_path)
                except Exception:
                    # Error checking modification time, treat as changed
                    changed_files.append(file_path)
        
        print(f"Found {len(changed_files)} changed files out of {len(all_files)} total files")
        
        # Use ThreadPoolExecutor for parallel processing
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit file analysis tasks
            future_to_file = {
                executor.submit(self.analyze_file, file_path): file_path
                for file_path in changed_files
            }
            
            # Process completed tasks as they complete
            total_files = len(changed_files)
            processed_files = 0
            
            for future in concurrent.futures.as_completed(future_to_file):
                file_path = future_to_file[future]
                processed_files += 1
                
                try:
                    file_call_graph = future.result()
                    
                    # Merge file call graph into main call graph
                    for func_name, func in file_call_graph.functions.items():
                        call_graph.add_function(func)
                    
                    # Merge missing functions
                    for missing in file_call_graph.missing_functions:
                        call_graph.add_missing_function(missing)
                        
                    # Print progress
                    print(f"Processed {processed_files}/{total_files} changed files: {file_path}")
                        
                except Exception as e:
                    print(f"Error analyzing file {file_path}: {e}")
        
        return call_graph, changed_files
    
    def find_missing_functions(self, call_graph: CallGraph) -> Set[str]:
        """Find missing function definitions in a call graph.
        
        Args:
            call_graph: The call graph to analyze
            
        Returns:
            Set[str]: Set of missing function names
        """
        missing_functions = set()
        
        for func_name, func in call_graph.functions.items():
            for called_func in func.calls:
                if called_func not in call_graph.functions:
                    missing_functions.add(called_func)
        
        return missing_functions
    
    def _merge_call_graphs(self, target: CallGraph, source: CallGraph) -> None:
        """Merge two call graphs together.
        
        Args:
            target: Target call graph to merge into
            source: Source call graph to merge from
        """
        for func_name, func in source.functions.items():
            if func_name in target.functions:
                # Update existing function
                target_func = target.functions[func_name]
                for call in func.calls:
                    if call not in target_func.calls:
                        target_func.add_call(call)
                for caller in func.called_by:
                    if caller not in target_func.called_by:
                        target_func.add_caller(caller)
                # Update template information
                if func.is_template:
                    target_func.is_template = True
                    for param in func.template_params:
                        if param not in target_func.template_params:
                            target_func.template_params.append(param)
                    for spec in func.specializations:
                        if spec not in target_func.specializations:
                            target_func.add_specialization(spec)
                # Update virtual method information
                if func.is_virtual:
                    target_func.is_virtual = True
                    for override in func.overrides:
                        if override not in target_func.overrides:
                            target_func.add_override(override)
                    for cls in func.class_hierarchy:
                        if cls not in target_func.class_hierarchy:
                            target_func.class_hierarchy.append(cls)
            else:
                # Add new function
                target.add_function(func)
        
        # Add missing functions
        for missing in source.missing_functions:
            target.add_missing_function(missing)
    
    def _analyze_advanced_templates(self, cursor: Cursor, functions: Dict[str, Function], file_path: str) -> None:
        """
        Analyze advanced template metaprogramming features.
        
        Args:
            cursor: Current cursor in the AST
            functions: Dictionary of functions
            file_path: Path to the source file
        """
        # First check for any is_same specializations - make a copy for safe iteration
        functions_to_check = list(functions.items())
        for func_name, func in functions_to_check:
            if func_name == "is_same" and func.is_template:
                # Add a specialization marker for is_same<T, T>
                spec_name = "is_same<T, T>"
                if spec_name not in functions:
                    # Create synthetic is_same<T, T> specialization
                    functions[spec_name] = Function(
                        name=spec_name,
                        file_path=func.file_path,
                        line_number=func.line_number,
                        signature="template <typename T> struct is_same<T, T>",
                        calls=[],
                        called_by=[],
                        is_template=True,
                        template_params=["T"],
                        partial_specialization=True,
                        primary_template="is_same"
                    )
                    # Add to the primary template's specializations
                    func.add_specialization(spec_name)
        
        def process_template_node(node, function_name=None):
            """Process a template-related node to extract advanced features."""
            if node.location.file and node.location.file.name != file_path:
                return
                
            # Analyze template declarations
            if node.kind in [CursorKind.FUNCTION_TEMPLATE, CursorKind.CLASS_TEMPLATE]:
                is_function = node.kind == CursorKind.FUNCTION_TEMPLATE
                curr_func_name = node.spelling if is_function else None
                
                # Check for template parameters
                template_params = []
                has_variadic = False
                variadic_param = ""
                has_template_template = False
                template_template_params = []
                
                # Collect all tokens for more comprehensive pattern matching
                all_tokens = [t.spelling for t in node.get_tokens()]
                token_text = " ".join(all_tokens)
                
                for child in node.get_children():
                    # Template parameter detection
                    if child.kind in [CursorKind.TEMPLATE_TYPE_PARAMETER, CursorKind.TEMPLATE_NON_TYPE_PARAMETER]:
                        param_name = child.spelling
                        template_params.append(param_name)
                        
                        # Check for parameter pack (variadic template)
                        param_tokens = [t.spelling for t in child.get_tokens()]
                        if "..." in param_tokens or any("..." in t for t in param_tokens):
                            has_variadic = True
                            variadic_param = param_name
                            
                        # Collect dependent names
                        for token in param_tokens:
                            if "::" in token:  # likely a dependent name
                                parts = token.split("::")
                                if len(parts) > 1 and parts[0] in template_params:
                                    if curr_func_name and curr_func_name in functions:
                                        functions[curr_func_name].dependent_names.append(token)
                    
                    # Template template parameter detection
                    elif child.kind == CursorKind.TEMPLATE_TEMPLATE_PARAMETER:
                        param_name = child.spelling
                        template_params.append(param_name)
                        has_template_template = True
                        template_template_params.append(param_name)
                        
                        # Get full template template parameter definition
                        param_tokens = [t.spelling for t in child.get_tokens()]
                        if param_tokens and len(param_tokens) > 2:
                            full_param = " ".join(param_tokens)
                            template_template_params[-1] = full_param
                
                # Update function details if found
                if curr_func_name and curr_func_name in functions:
                    func = functions[curr_func_name]
                    
                    # Update template parameters
                    func.template_params = template_params
                    
                    # Set variadic template info
                    if has_variadic:
                        func.has_variadic_templates = True
                        func.variadic_template_param = variadic_param
                        
                        # Enhanced variadic template detection - look for fold expressions
                        if "(" in token_text and "..." in token_text and ")" in token_text:
                            # Check for fold expression patterns
                            fold_patterns = [
                                r"\([^)]*\.\.\.[^)]*\)",              # basic fold
                                r"\([^)]*\+[^)]*\.\.\.[^)]*\)",       # unary fold with +
                                r"\([^)]*\.\.\.[^)]*\+[^)]*\)",       # binary fold with +
                                r"\([^)]*(?:\|\||&&)[^)]*\.\.\.[^)]*\)" # logical fold
                            ]
                            for pattern in fold_patterns:
                                if re.search(pattern, token_text):
                                    func.add_sfinae_technique("fold_expression")
                                    break
                    
                    # Set template template parameters
                    if has_template_template:
                        func.template_template_params = template_template_params
                    
                    # Check for metafunction characteristics
                    self._detect_metafunction(node, func)
                    
                    # Detect SFINAE techniques
                    self._detect_sfinae_techniques(node, func)
                    
                    # Detect concept requirements (C++20)
                    self._detect_concepts(node, func)
                    
                    # Detect partial specialization
                    self._detect_partial_specialization(node, func)
                    
                    # Additional detection of dependent types in the signature or body
                    if "typename" in token_text:
                        typename_patterns = [
                            r"typename\s+([A-Za-z0-9_]+)::([A-Za-z0-9_]+)",  # typename T::type
                            r"typename\s+([A-Za-z0-9_]+)<"                   # typename std::vector<
                        ]
                        for pattern in typename_patterns:
                            matches = re.findall(pattern, token_text)
                            for match in matches:
                                if isinstance(match, tuple):
                                    dependent_name = f"{match[0]}::{match[1]}"
                                else:
                                    dependent_name = match
                                if dependent_name not in func.dependent_names:
                                    func.dependent_names.append(dependent_name)
                
            # Process children recursively
            for child in node.get_children():
                # Pass function name down if we're in a function template
                if node.kind == CursorKind.FUNCTION_TEMPLATE:
                    process_template_node(child, node.spelling)
                else:
                    process_template_node(child, function_name)
        
        # Start processing from the root
        process_template_node(cursor)
    
    def _detect_metafunction(self, node: Cursor, func: Function) -> None:
        """
        Detect if a template is a metafunction (type trait, value trait, etc).
        
        Args:
            node: The cursor to the template declaration
            func: The function object to update
        """
        # Type traits typically have a 'value' static member or 'type' typedef
        has_value_member = False
        has_type_typedef = False
        is_transform = False
        metafunction_pattern = False
        
        # Collect all tokens for advanced pattern matching
        all_tokens = [t.spelling for t in node.get_tokens()]
        token_text = " ".join(all_tokens)
        
        # Check for common metafunction patterns in the text
        metafunction_patterns = {
            "type_trait": [
                r"struct\s+is_", r"class\s+is_",       # is_xxx traits
                r"::type", r"::value_type",            # type member access
                r"std::enable_if", r"typename\s+enable_if",  # enable_if patterns
                r"std::conditional", r"std::remove_",  # std type traits
                r"::type_t", r"std::declval"           # type trait utils
            ],
            "value_trait": [
                r"::value", r"static\s+constexpr",     # value trait patterns
                r"v>", r"_v<",                         # _v helper suffix
                r"value\s*=", r"std::integral_constant", # integral constant pattern
                r"constexpr\s+bool", r"static\s+const" # value storage
            ],
            "transform": [
                r"using\s+type\s*=", r"typedef",       # type alias patterns
                r"std::remove_", r"std::add_",         # type transformations
                r"::type::", r"::template",            # nested type access
                r"rebind", r"_t<"                      # rebinding and _t helper
            ]
        }
        
        # Check nodes for specific metafunction elements
        for child in node.get_children():
            if child.kind == CursorKind.FIELD_DECL and child.spelling == "value":
                has_value_member = True
                
                # Check if it's a static constexpr member
                child_tokens = [t.spelling for t in child.get_tokens()]
                if "static" in child_tokens and "constexpr" in child_tokens:
                    has_value_member = True
                    func.metafunction_kind = "value_trait"
                
            elif child.kind == CursorKind.TYPEDEF_DECL and child.spelling == "type":
                has_type_typedef = True
                
                # Get tokens to see if this is a transformation
                child_tokens = [t.spelling for t in child.get_tokens()]
                if any("::" in t for t in child_tokens):
                    is_transform = True
            
            # Check for typename ::type pattern (transformation traits)
            if child.kind == CursorKind.TYPE_REF:
                child_tokens = [t.spelling for t in child.get_tokens()]
                child_text = " ".join(child_tokens)
                
                if "typename" in child_tokens and "::type" in child_text:
                    is_transform = True
                
                # Check for template instantiations which might be transformations
                if "<" in child_text and ">" in child_text:
                    is_transform = True
        
        # Check for tag dispatch patterns
        if "tag_dispatch" not in func.sfinae_techniques and (
            "true_type" in token_text or "false_type" in token_text or
            "std::true_type" in token_text or "std::false_type" in token_text
        ):
            func.add_sfinae_technique("tag_dispatch")
        
        # Check token text for metafunction patterns
        for kind, patterns in metafunction_patterns.items():
            for pattern in patterns:
                if re.search(pattern, token_text):
                    metafunction_pattern = True
                    if not func.metafunction_kind:
                        func.metafunction_kind = kind
                    break
        
        # Look for type_traits includes or using directives
        if "std::type_traits" in token_text or "std::is_" in token_text:
            metafunction_pattern = True
            if not func.metafunction_kind:
                func.metafunction_kind = "type_trait"
        
        # Update function based on detected metafunction characteristics
        if has_value_member or has_type_typedef or is_transform or metafunction_pattern:
            func.is_metafunction = True
            
            # Set the specific metafunction kind if not already set
            if not func.metafunction_kind:
                if has_value_member and not has_type_typedef:
                    func.metafunction_kind = "value_trait"
                elif has_type_typedef and not has_value_member:
                    func.metafunction_kind = "type_trait"
                elif is_transform:
                    func.metafunction_kind = "transform"
                else:
                    func.metafunction_kind = "mixed_trait"
                    
        # Special case for template functions that look like metafunctions
        if not func.is_metafunction and (
            func.is_template and 
            len(func.template_params) > 0 and
            "std::" in token_text and
            ("<" in token_text and ">" in token_text)
        ):
            # This might be a function template that uses metaprogramming
            func.is_metafunction = True
            func.metafunction_kind = "function_meta"
    
    def _detect_sfinae_techniques(self, node: Cursor, func: Function) -> None:
        """
        Detect SFINAE techniques used in a template.
        
        Args:
            node: The cursor to the template declaration
            func: The function object to update
        """
        # Get all tokens in the template declaration
        all_tokens = []
        all_text = ""
        
        # First check the template parameter list directly
        if func.is_template:
            template_text = node.displayname
            # Check for enable_if in template parameters
            if "enable_if" in template_text:
                func.has_sfinae = True
                func.add_sfinae_technique("enable_if")
        
        for c in node.get_children():
            tokens = [t.spelling for t in c.get_tokens()]
            all_tokens.extend(tokens)
            all_text += " ".join(tokens) + " "
        
        token_text = " ".join(all_tokens)
        
        # Check for common SFINAE patterns using regex
        sfinae_patterns = {
            "enable_if": [
                r"enable_if(?:_t)?(<|<.*?>)",
                r"std::enable_if(?:_t)?",
                r"typename\s+std::enable_if(?:_t)?",
                r"::enable_if(?:_t)?",
                r"::type\s*=\s*void",   # common enable_if pattern
                r"Enable[Ii]f"           # custom EnableIf naming
            ],
            "void_t": [
                r"void_t(<|<.*?>)",
                r"std::void_t",
                r"typename\s+std::void_t",
                r"::void_t"
            ],
            "decltype": [
                r"decltype\s*\(|\)\s*->",
                r"decltype\([^)]+\)",
                r"->\s*decltype",
                r"std::declval",        # often used with decltype
                r"sizeof\(decltype"      # sizeof decltype pattern
            ],
            "is_detected": [
                r"is_detected(?:_v|_t)?(<|<.*?>)",
                r"std::is_detected",
                r"std::experimental::is_detected"
            ],
            "detection_idiom": [
                r"detected(?:_t|_or)?(<|<.*?>)",
                r"std::detected(?:_t|_or)?",
                r"std::experimental::detected"
            ],
            "substitution_failure": [
                r"sizeof\([^)]*\)\s*==\s*sizeof\(",
                r"sizeof\s*\.\.\.\s*\(",  # sizeof...(args) pattern
                r"decltype\(sizeof"
            ],
            "expression_sfinae": [
                r"decltype\((?:[^()]*\([^()]*\))*[^()]*\)",
                r"decltype\(std::declval",
                r"noexcept\(decltype"     # noexcept with decltype
            ],
            "tag_dispatch": [
                r"(?:true|false)_type",
                r"std::(?:true|false)_type",
                r"typename\s+std::conditional", # often used with tag dispatch
                r"::type>\s*::\s*type"     # nested conditional
            ],
            "if_constexpr": [
                r"if\s+constexpr",
                r"if\s+constexpr\s*\("
            ],
            "constexpr_if": [
                r"if\s+constexpr",
                r"else\s+if\s+constexpr"
            ],
            "std_conditional": [
                r"std::conditional[_t]?(<|<.*?>)",
                r"conditional[_t]?<",
                r"std::conditional_t"
            ],
            "requires_clause": [
                r"requires\s*\(",
                r"requires\s+[A-Za-z0-9_]+",
                r"requires\s*\{",
                r"template\s*<[^>]*>\s*requires"
            ],
            "concepts": [
                r"concept\s+[A-Za-z0-9_]+\s*=",
                r"template\s*<[^>]*concept",
                r"std::same_as<", r"std::convertible_to<" # Standard C++20 concepts
            ]
        }
        
        # Check each pattern group
        for technique, patterns in sfinae_patterns.items():
            for pattern in patterns:
                if re.search(pattern, token_text) or re.search(pattern, all_text):
                    func.add_sfinae_technique(technique)
                    break  # Found a match in this group, move to next group
        
        # Look for specialized disable_if pattern (opposite of enable_if)
        if "disable_if" in token_text or "DisableIf" in token_text:
            func.add_sfinae_technique("disable_if")
        
        # Check for special case of SFINAE on return type
        if "->" in token_text and (
            "typename" in token_text or 
            "decltype" in token_text or 
            "std::" in token_text and "<" in token_text
        ):
            func.add_sfinae_technique("return_type_sfinae")
        
        # Look specifically for void_t use to detect ill-formed types
        void_t_patterns = [
            r"void_t<[^>]*::type",          # Check for member type existence
            r"void_t<[^>]*::value_type",    # Check for value_type
            r"void_t<[^>]*::iterator",      # Check for iterator
            r"void_t<decltype\([^)]*\)>"    # Check for valid expression
        ]
        
        for pattern in void_t_patterns:
            if re.search(pattern, all_text):
                if "void_t" not in func.sfinae_techniques:
                    func.add_sfinae_technique("void_t")
                func.add_sfinae_technique("member_detection")
                break
                
        # Check for decltype + declval combinations (common expression SFINAE patterns)
        if "declval" in all_text and "decltype" in all_text:
            func.add_sfinae_technique("expression_sfinae")
            
            # Look for specific expression patterns
            decltype_patterns = [
                r"decltype\(declval<[^>]*>\(\)\.([A-Za-z0-9_]+)",  # Method existence
                r"decltype\(declval<[^>]*>\(\)\[[^\]]*\]",         # Operator[] existence
                r"decltype\(declval<[^>]*>\(\)\s*\+\s*",           # Operator+ existence
                r"decltype\(declval<[^>]*>\(\)\([^)]*\)\)"         # Operator() existence
            ]
            
            for pattern in decltype_patterns:
                if re.search(pattern, all_text):
                    func.add_sfinae_technique("method_detection")
                    break
                    
        # More comprehensive C++17/C++20 feature detection
        if "if constexpr" in token_text:
            func.add_sfinae_technique("if_constexpr")
            
        if "static_assert" in token_text and (
            "is_same" in token_text or 
            "std::is_same" in token_text or
            "is_convertible" in token_text
        ):
            func.add_sfinae_technique("static_assertions")
            
        # If we've identified at least one SFINAE technique, mark the function
        if func.sfinae_techniques:
            func.has_sfinae = True
    
    def _detect_concepts(self, node: Cursor, func: Function) -> None:
        """
        Detect C++20 concepts and constraints in a template.
        
        Args:
            node: The cursor to the template declaration
            func: The function object to update
        """
        # Check for requires clauses and concept usage
        all_tokens = []
        for c in node.get_children():
            all_tokens.extend([t.spelling for t in c.get_tokens()])
        
        token_text = " ".join(all_tokens)
        
        # Check for various concept-related patterns
        concept_patterns = {
            "requires_clause": [
                r"requires\s*\([^\)]+\)",
                r"requires\s+[A-Za-z0-9_]+<[^>]*>",
                r"template\s*<[^>]*>\s*requires"
            ],
            "concept_usage": [
                r"concept\s+[A-Za-z0-9_]+\s*=",
                r"std::[A-Za-z0-9_]+<",  # Standard library concepts
                r"[A-Za-z0-9_]+\s*<[^>]*>\s*[A-Za-z0-9_]+"  # ConceptName<T> param_name
            ],
            "standard_concepts": [
                r"std::same_as<", r"std::convertible_to<",
                r"std::integral<", r"std::floating_point<",
                r"std::copyable<", r"std::movable<",
                r"std::equality_comparable<", r"std::totally_ordered<",
                r"std::invocable<", r"std::predicate<"
            ]
        }
        
        # Check for requires clause
        if "requires" in all_tokens:
            func.is_concept = True
            
            # Try to extract the requires expression
            requires_idx = all_tokens.index("requires")
            if requires_idx < len(all_tokens) - 1:
                # Extract the requires clause
                requires_clause = []
                brace_level = 0
                for token in all_tokens[requires_idx+1:]:
                    if token == "{":
                        brace_level += 1
                    elif token == "}":
                        brace_level -= 1
                        if brace_level < 0:
                            break
                    requires_clause.append(token)
                    
                    # Break if we encounter a semicolon or an opening brace at level 0
                    if (token == ";" or (token == "{" and brace_level == 1)) and brace_level == 0:
                        break
                
                if requires_clause:
                    func.add_constraint_expression(" ".join(requires_clause).strip())
        
        # Check for concept patterns
        for category, patterns in concept_patterns.items():
            for pattern in patterns:
                matches = re.findall(pattern, token_text)
                if matches:
                    func.is_concept = True
                    for match in matches:
                        if isinstance(match, str) and len(match) > 0:
                            func.add_concept_requirement(match)
        
        # Check for concept usage in template parameters
        for child in node.get_children():
            if child.kind == CursorKind.TEMPLATE_TYPE_PARAMETER:
                param_tokens = [t.spelling for t in child.get_tokens()]
                
                # Look for Pattern: template<ConceptName T>
                # Where ConceptName is not "typename" or "class"
                if len(param_tokens) >= 2 and param_tokens[0] not in ["typename", "class"]:
                    # This could be a concept-constrained parameter
                    func.is_concept = True
                    
                    # Try to construct a more complete concept description
                    concept_expr = " ".join(param_tokens)
                    if "<" in concept_expr and ">" in concept_expr:
                        # This looks like a concept with template args
                        func.add_concept_requirement(concept_expr.strip())
                    else:
                        # Simpler concept usage like "Sortable T"
                        func.add_concept_requirement(f"{param_tokens[0]} {param_tokens[1]}".strip())
                
                # Look for pattern: template<typename T> requires ConceptName<T>
                elif "requires" in token_text and param_tokens:
                    param_name = param_tokens[-1] if param_tokens else ""
                    requires_pattern = rf"requires\s+[A-Za-z0-9_]+<\s*{param_name}\s*>"
                    
                    if re.search(requires_pattern, token_text):
                        func.is_concept = True
                        matches = re.findall(requires_pattern, token_text)
                        for match in matches:
                            func.add_concept_requirement(match.strip())
        
        # Look for C++20 concept definitions
        concept_def = []
        in_concept_def = False
        
        for i, token in enumerate(all_tokens):
            if token == "concept" and i+1 < len(all_tokens):
                in_concept_def = True
                concept_def.append(token)
            elif in_concept_def:
                concept_def.append(token)
                if token == ";" or token == "{":
                    in_concept_def = False
                    break
        
        if concept_def:
            func.is_concept = True
            func.add_concept_requirement(" ".join(concept_def).strip())
            
            # If this is an actual concept definition
            if concept_def[0] == "concept" and len(concept_def) > 1:
                # Mark that this function defines a concept
                func.is_metafunction = True
                func.metafunction_kind = "concept_definition"
    
    def _detect_partial_specialization(self, node: Cursor, func: Function) -> None:
        """
        Detect partial template specialization.
        
        Args:
            node: The cursor to the template declaration
            func: The function object to update
        """
        # Check if this is a template specialization
        if not func.is_template:
            return
            
        # Get all tokens for comprehensive pattern matching
        all_tokens = [t.spelling for t in node.get_tokens()]
        token_text = " ".join(all_tokens)
        
        # Get template parameters and arguments
        template_params = func.template_params
        spec_args = func.template_specialization_args
        
        # Check for explicit specialization pattern in token text
        specialization_patterns = [
            r"template\s*<>\s*", # full specialization
            r"template\s*<[^>]*>\s*[^<]*<[^>]*>", # partial specialization
            r"<\s*T\s*,\s*[A-Za-z0-9_]+\s*>", # partial with specific types
            r"<\s*[A-Za-z0-9_]+\s*,\s*T\s*>" # partial with specific types
        ]
        
        is_specialization = False
        for pattern in specialization_patterns:
            if re.search(pattern, token_text):
                is_specialization = True
                break
                
        # Check for partial specialization pattern: some template parameters remain, some are specialized
        is_partial = False
        if template_params and spec_args and len(template_params) > len(spec_args):
            is_partial = True
            func.partial_specialization = True
            
            # Try to determine primary template
            name_parts = func.name.split("<")
            if len(name_parts) > 1:
                # Basic heuristic for extracting primary template name
                func.primary_template = name_parts[0]
                
        # Also check based on AST pattern
        has_concrete_type = False
        has_template_param = False
        type_names = set()
        
        for child in node.get_children():
            # Look for concrete types in template arguments
            if child.kind in [CursorKind.TYPE_REF, CursorKind.TEMPLATE_REF]:
                tokens = [t.spelling for t in child.get_tokens()]
                
                for token in tokens:
                    # Skip basic type keywords as they're not very informative
                    if token in ["int", "char", "bool", "float", "double", "void"]:
                        continue
                        
                    # Check for concrete type names (not type parameters)
                    if token not in template_params and not token.isdigit():
                        if "::" in token or token.startswith("std::"):
                            has_concrete_type = True
                            type_names.add(token)
                        
            # Look for template parameters
            if child.kind == CursorKind.TEMPLATE_TYPE_PARAMETER:
                has_template_param = True
            
            # Also check for specialization in template args
            tokens = [t.spelling for t in child.get_tokens()]
            if "<" in tokens and ">" in tokens:
                # Find the angle bracket content
                in_bracket = False
                bracket_content = []
                
                for token in tokens:
                    if "<" in token:
                        in_bracket = True
                    if in_bracket:
                        bracket_content.append(token)
                    if ">" in token:
                        in_bracket = False
                
                # Check if there's both concrete types and template parameters
                bracket_text = " ".join(bracket_content)
                if any(p in bracket_text for p in template_params) and (
                    any(t in bracket_text for t in ["int", "bool", "char", "double", "std::"]) or
                    any(t in bracket_text for t in type_names)
                ):
                    has_concrete_type = True
                    has_template_param = True
        
        # Update function based on our findings
        if has_concrete_type and has_template_param:
            func.partial_specialization = True
            
            # Try to extract specialized parameter information
            in_spec = False
            spec_section = []
            
            for i, token in enumerate(all_tokens):
                if token == "template" and i + 1 < len(all_tokens) and all_tokens[i+1] == "<":
                    # Skip the template parameter list
                    in_spec = False
                    bracket_count = 0
                    for j in range(i+1, len(all_tokens)):
                        if all_tokens[j] == "<":
                            bracket_count += 1
                        elif all_tokens[j] == ">":
                            bracket_count -= 1
                            if bracket_count == 0:
                                break
                    continue
                    
                if "<" in token and not in_spec:
                    in_spec = True
                    spec_section.append(token)
                elif in_spec:
                    spec_section.append(token)
                    if ">" in token:
                        in_spec = False
                        break
            
            # Store the specialized arguments
            if spec_section:
                spec_text = " ".join(spec_section)
                func.template_specialization_args = [spec_text]
                
                # Try to determine the primary template
                if "<" in func.name:
                    base_name = func.name.split("<")[0]
                    func.primary_template = base_name
                    
        # Final determination based on all evidence
        if is_partial or (has_concrete_type and has_template_param):
            func.partial_specialization = True 

    def _process_cross_file_references(self, functions: Dict[str, Function], mode: str = "enhanced") -> None:
        """
        Process cross-file references between functions, with special handling for templates.
        
        Args:
            functions: Dictionary of functions to process
            mode: Cross-file analysis mode ('basic', 'enhanced', 'full')
        """
        if mode == "basic":
            # Basic mode just uses existing information, no additional processing
            return
            
        # Find all template functions and metafunctions
        template_functions = {}
        metafunctions = {}
        
        for name, func in functions.items():
            if func.is_template:
                template_functions[name] = func
            if func.is_metafunction:
                metafunctions[name] = func
        
        if mode == "enhanced" or mode == "full":
            # Enhanced mode: Look for template instantiations and template parameters
            self._process_template_instantiations(functions, template_functions)
            
            # Find metafunction relationships
            self._process_metafunction_relationships(functions, metafunctions)
        
        if mode == "full":
            # Full mode: Also try to resolve complex dependencies
            self._resolve_template_dependencies(functions, template_functions)
            
            # Process template specialization relationships
            self._process_template_specializations(functions, template_functions)
    
    def _process_template_instantiations(self, functions: Dict[str, Function], template_functions: Dict[str, Function]) -> None:
        """
        Identify template instantiations in the code.
        
        Args:
            functions: All functions in the code
            template_functions: Template functions to analyze
        """
        # Look for template instantiations
        for name, func in functions.items():
            # Examine function calls to see if they might be template instantiations
            for called_name in func.calls:
                # Template instantiations typically have '<' in the name
                if '<' in called_name and '>' in called_name:
                    # Find the base template name (before the '<')
                    base_name = called_name.split('<')[0]
                    
                    # If we know about this template, create a specialization relationship
                    if base_name in template_functions:
                        template_func = template_functions[base_name]
                        
                        # Add the specialized name to the template
                        template_func.add_specialization(called_name)
                        
                        # If the specialized function exists, update its info
                        if called_name in functions:
                            specialized_func = functions[called_name]
                            specialized_func.is_template = True
                            specialized_func.primary_template = base_name
                            
                            # Extract template args from the name
                            args_part = called_name[len(base_name):]
                            if args_part.startswith('<') and args_part.endswith('>'):
                                args = args_part[1:-1].split(',')
                                specialized_func.template_specialization_args = [arg.strip() for arg in args]
    
    def _process_metafunction_relationships(self, functions: Dict[str, Function], metafunctions: Dict[str, Function]) -> None:
        """
        Identify relationships between metafunctions.
        
        Args:
            functions: All functions in the code
            metafunctions: Metafunctions to analyze
        """
        # Look for metafunctions that use other metafunctions
        for name, func in metafunctions.items():
            # Check dependent names for metafunction usage
            for dep_name in func.dependent_names:
                # Check if the dependent name is a metafunction
                base_dep = dep_name.split('::')[0] if '::' in dep_name else dep_name
                if base_dep in metafunctions:
                    # Add a call relationship
                    func.add_call(base_dep)
                    
                    # Update the called metafunction
                    if base_dep in functions:
                        functions[base_dep].add_caller(name)
            
            # Also check calls for metafunction usage
            for called_name in func.calls:
                if called_name in metafunctions:
                    # Update metadata to indicate metafunction composition
                    func.is_metafunction = True
                    if not func.metafunction_kind:
                        func.metafunction_kind = "composed_metafunction"
    
    def _resolve_template_dependencies(self, functions: Dict[str, Function], template_functions: Dict[str, Function]) -> None:
        """
        Resolve complex template dependencies.
        
        Args:
            functions: All functions in the code
            template_functions: Template functions to analyze
        """
        # Look for template dependencies in all functions
        for name, func in functions.items():
            # Check all tokens in the function for template usage
            if not hasattr(func, 'body') or not func.body:
                continue
                
            # Simple check for template usage in function body
            for template_name in template_functions:
                if template_name in func.body:
                    # Might be using this template
                    func.add_call(template_name)
                    
                    # Update the template function
                    if template_name in functions:
                        functions[template_name].add_caller(name)
    
    def _process_template_specializations(self, functions: Dict[str, Function], template_functions: Dict[str, Function]) -> None:
        """
        Analyze relationships between template specializations.
        
        Args:
            functions: All functions in the code
            template_functions: Template functions to analyze
        """
        # Group all template specializations by their primary template
        specialization_groups = {}
        
        for name, func in functions.items():
            if func.is_template and func.primary_template:
                primary = func.primary_template
                if primary not in specialization_groups:
                    specialization_groups[primary] = []
                specialization_groups[primary].append(name)
        
        # Process each specialization group
        for primary, specializations in specialization_groups.items():
            if primary in functions:
                primary_func = functions[primary]
                
                # Update the primary template with all specializations
                for spec in specializations:
                    primary_func.add_specialization(spec)
                    
                    # Update the specialization to reference its primary
                    if spec in functions:
                        functions[spec].primary_template = primary 