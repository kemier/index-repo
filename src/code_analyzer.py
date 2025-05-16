from typing import List, Dict, Optional
from clang.cindex import Index, Cursor, CursorKind, TranslationUnit, Config, TranslationUnitLoadError, Diagnostic, TypeKind
from pydantic import BaseModel
import os
import traceback

class FunctionInfo(BaseModel):
    name: str
    file_path: str
    line_number: int
    is_callback: bool = False
    callback_type: Optional[str] = None

class BranchInfo(BaseModel):
    branch_node_type: str
    condition: Optional[str] = None
    file_path: str
    line_number: int

class CallRelation(BaseModel):
    caller: FunctionInfo
    callee: FunctionInfo

class CodeAnalyzer:
    def __init__(self):
        # Attempt to find the libclang library
        # Common paths for libclang, adjust if necessary for your system
        # Check environment variable first
        libclang_path = os.getenv('LIBCLANG_PATH')
        if libclang_path and os.path.exists(os.path.join(libclang_path, 'libclang.dll')): # Windows
            Config.set_library_path(libclang_path)
        elif os.path.exists('C:/Program Files/LLVM/bin/libclang.dll'): # Default LLVM install path on Windows
            Config.set_library_path('C:/Program Files/LLVM/bin')
        elif os.path.exists('/usr/lib/llvm-18/lib/libclang.so.1'): # Common on Linux
             Config.set_library_path('/usr/lib/llvm-18/lib')
        # Add more paths as needed for different OS/installations

        try:
            self.index = Index.create()
        except Exception as e:
            print(f"Error creating Clang Index: {e}")
            print("Please ensure libclang is installed and configured correctly.")
            print("You might need to set LIBCLANG_PATH environment variable to the directory containing libclang.dll or libclang.so")
            raise
        self.functions: Dict[str, FunctionInfo] = {}
        self.call_relations: List[CallRelation] = []
        self.callbacks: List[FunctionInfo] = []
        self.branches: List[BranchInfo] = []

    def parse_file(self, file_path: str, compile_args: List[str] = None) -> None:
        print(f"Attempting to parse file: {file_path} with args: {compile_args}")
        tu = None 
        try:
            base_args = [str(arg) for arg in compile_args] if compile_args else []
            msvc_toolset_version = "14.43.34808"
            windows_sdk_version = "10.0.22621.0"
            msvc_include_path = f"C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/VC/Tools/MSVC/{msvc_toolset_version}/include"
            ucrt_include_path = f"C:/Program Files (x86)/Windows Kits/10/Include/{windows_sdk_version}/ucrt"
            shared_include_path = f"C:/Program Files (x86)/Windows Kits/10/Include/{windows_sdk_version}/shared"
            um_include_path = f"C:/Program Files (x86)/Windows Kits/10/Include/{windows_sdk_version}/um"
            winrt_include_path = f"C:/Program Files (x86)/Windows Kits/10/Include/{windows_sdk_version}/winrt"
            system_includes = []
            if os.path.exists(msvc_include_path):
                system_includes.extend(["-isystem", msvc_include_path])
            if os.path.exists(ucrt_include_path):
                system_includes.extend(["-isystem", ucrt_include_path])
            if os.path.exists(shared_include_path):
                system_includes.extend(["-isystem", shared_include_path])
            if os.path.exists(um_include_path):
                system_includes.extend(["-isystem", um_include_path])
            if os.path.exists(winrt_include_path):
                system_includes.extend(["-isystem", winrt_include_path])
            final_args = system_includes + base_args
            if file_path.endswith(".h") or file_path.endswith(".hpp") or file_path.endswith(".hxx"):
                final_args.extend(["-x", "c++-header"])
            elif file_path.endswith(".cpp") or file_path.endswith(".cxx") or file_path.endswith(".cc"):
                final_args.extend(["-x", "c++"])
            print(f"Final clang args for {file_path}: {final_args}")
            tu = self.index.parse(file_path, args=final_args)
            if tu and tu.diagnostics:
                print(f"Diagnostics for {file_path}:")
                for diag in tu.diagnostics:
                    print(f"  Severity: {diag.severity}, Location: {diag.location}, Spelling: {diag.spelling}")
                    if diag.severity >= Diagnostic.Error:
                        print(f"Error parsing {file_path}. Will not process further.")
                        return
            if tu:
              print(f"Successfully parsed {file_path}. Processing TU cursor: {tu.cursor.spelling} (Kind: {tu.cursor.kind})")
              self._process_translation_unit(tu.cursor, file_path) # Pass file_path for context
            else:
              print(f"Translation unit is None for {file_path}, skipping processing.")
        except TranslationUnitLoadError as e:
            print(f"Clang (libclang) TranslationUnitLoadError for {file_path}: {e}")
            if hasattr(e, 'translation_unit') and e.translation_unit and e.translation_unit.diagnostics:
                print(f"Diagnostics from exception object for {file_path}:")
                for diag in e.translation_unit.diagnostics:
                    print(f"  Severity: {diag.severity}, Location: {diag.location}, Spelling: {diag.spelling}")
            else:
                print(f"No detailed diagnostics available in the exception for {file_path}.")
        except Exception as e:
            print(f"Generic error parsing file {file_path}: {e}")
            if tu and tu.diagnostics:
                 print(f"Diagnostics for {file_path} (on generic error):")
                 for diag in tu.diagnostics:
                    print(f"  Severity: {diag.severity}, Location: {diag.location}, Spelling: {diag.spelling}")
            traceback.print_exc()

    def _process_translation_unit(self, cursor: Cursor, current_file_path: str) -> None:
        """Process the translation unit and extract all relevant information, focusing on the current file."""
        # We are only interested in declarations from the file currently being parsed,
        # not from included headers (unless they are part of the project explicitly parsed later).
        print(f"_process_translation_unit for cursor: {cursor.spelling}, Kind: {cursor.kind}, File: {cursor.location.file.name if cursor.location and cursor.location.file else 'N/A'}")
        for node in cursor.get_children():
            # Crucial check: Only process nodes defined in the current file being analyzed.
            # System headers or other includes might bring in many unneeded symbols.
            if node.location and node.location.file and node.location.file.name == current_file_path:
                print(f"  Processing child node: {node.spelling} (Kind: {node.kind}, File: {node.location.file.name})")
                if node.kind == CursorKind.FUNCTION_DECL:
                    self._process_function(node)
                elif node.kind == CursorKind.NAMESPACE:
                    print(f"    Entering NAMESPACE: {node.spelling}")
                    self._process_namespace(node, current_file_path)
                elif node.kind == CursorKind.CLASS_DECL or node.kind == CursorKind.STRUCT_DECL:
                    print(f"    Entering CLASS_DECL/STRUCT_DECL: {node.spelling}")
                    self._process_class_or_struct(node, current_file_path)
                # Potentially add other top-level constructs if needed (e.g., global vars)
            elif node.location and node.location.file:
                # Optional: Log skipped nodes from other files for debugging if necessary
                # print(f"  Skipping child node from other file: {node.spelling} (Kind: {node.kind}, File: {node.location.file.name})")
                pass 
            else:
                 # print(f"  Skipping child node with no location info: {node.spelling} (Kind: {node.kind})")
                 pass # Skip nodes with no location info

    def _process_namespace(self, namespace_cursor: Cursor, current_file_path: str) -> None:
        """Recursively process nodes within a namespace, ensuring they are from the current file."""
        for node in namespace_cursor.get_children():
            if node.location and node.location.file and node.location.file.name == current_file_path:
                print(f"    In NS '{namespace_cursor.spelling}', processing child: {node.spelling} (Kind: {node.kind})")
                if node.kind == CursorKind.FUNCTION_DECL:
                    self._process_function(node)
                elif node.kind == CursorKind.CLASS_DECL or node.kind == CursorKind.STRUCT_DECL:
                    self._process_class_or_struct(node, current_file_path)
                elif node.kind == CursorKind.NAMESPACE: # Nested namespaces
                    self._process_namespace(node, current_file_path) 
            # else: print(f"    In NS '{namespace_cursor.spelling}', skipping child from other file: {node.spelling}")

    def _process_class_or_struct(self, class_cursor: Cursor, current_file_path: str) -> None:
        """Process nodes within a class or struct, including methods and nested types."""
        # Store class/struct definition itself if needed (e.g., as a type node in Dgraph)
        # For now, focusing on its members like methods.
        for node in class_cursor.get_children():
            if node.location and node.location.file and node.location.file.name == current_file_path:
                print(f"      In Class/Struct '{class_cursor.spelling}', processing member: {node.spelling} (Kind: {node.kind})")
                if node.kind == CursorKind.CXX_METHOD:
                    self._process_function(node) # Treat CXX_METHOD like FUNCTION_DECL for storage
                elif node.kind == CursorKind.FIELD_DECL: # For struct callbacks
                    self._process_struct_field(node)
                elif node.kind == CursorKind.CLASS_DECL or node.kind == CursorKind.STRUCT_DECL: # Nested classes/structs
                    self._process_class_or_struct(node, current_file_path)
            # else: print(f"      In Class/Struct '{class_cursor.spelling}', skipping member from other file: {node.spelling}")

    def _process_function(self, cursor: Cursor) -> None:
        """Process a function or method declaration and its body."""
        # Use fully qualified name for functions within classes/namespaces if possible
        # cursor.mangled_name might be too cryptic. cursor.semantic_parent.spelling + "::" + cursor.spelling can work.
        # For simplicity, using cursor.spelling for now, but this can lead to collisions for overloaded functions or methods with same name in different classes.
        # A more robust key for self.functions dict would be needed for that (e.g., mangled name or a composite key).
        
        # Construct a more unique name if it's a method
        func_name = cursor.spelling
        parent = cursor.semantic_parent
        if parent and (parent.kind == CursorKind.CLASS_DECL or parent.kind == CursorKind.STRUCT_DECL or parent.kind == CursorKind.NAMESPACE):
            parent_name = parent.spelling
            # Potentially recurse up for nested namespaces/classes if full qualification is desired
            # For now, one level of qualification.
            if parent_name: # Ensure parent_name is not empty
                 func_name = f"{parent_name}::{func_name}"

        print(f"Processing FUNCTION_DECL/CXX_METHOD: {func_name} (Raw spelling: {cursor.spelling}, Kind: {cursor.kind}, File: {cursor.location.file.name}, Line: {cursor.location.line})")
        
        # Skip if not from a .cpp or .h file (e.g. system headers)
        # This check is now primarily handled by the caller (_process_translation_unit, etc.)
        # but double-checking here for functions might be useful if _process_function is called from other contexts.
        # if not (cursor.location.file.name.endswith('.cpp') or cursor.location.file.name.endswith('.h')):
        #     print(f"  Skipping function {func_name} from non-project file: {cursor.location.file.name}")
        #     return

        func_info = FunctionInfo(
            name=func_name, # Use potentially qualified name
            file_path=cursor.location.file.name,
            line_number=cursor.location.line
        )
        # Using the potentially qualified name as key
        if func_name in self.functions:
            print(f"Warning: Function/Method {func_name} already exists. Overwriting. Location1: {self.functions[func_name].file_path}:{self.functions[func_name].line_number}, Location2: {func_info.file_path}:{func_info.line_number}")
        self.functions[func_name] = func_info
        print(f"  Stored function: {func_name}")

        # Process function body for calls and branches
        # This part needs to be careful about context, especially for `caller`
        for node in cursor.get_children(): # Iterate children of the function/method cursor
            if node.kind == CursorKind.CALL_EXPR:
                # Pass `func_info` (the Pydantic model for the current function) as caller context
                self._process_function_call(func_info, node)
            elif node.kind in (CursorKind.IF_STMT, CursorKind.SWITCH_STMT,
                             CursorKind.WHILE_STMT, CursorKind.FOR_STMT):
                # Pass `func_info` as context for the function containing the branch
                self._process_branch(func_info, node)

    def _process_struct(self, cursor: Cursor) -> None:
        """Process a struct declaration to find callback function pointers."""
        # This needs to be updated to use current_file_path filter similar to _process_class_or_struct
        print(f"_process_struct: {cursor.spelling}, File: {cursor.location.file.name if cursor.location and cursor.location.file else 'N/A'}")
        for node in cursor.get_children():
            # Assuming _process_struct is called from a context where current_file_path is relevant
            # and we only want to process fields if the struct itself is in the current_file_path.
            # The caller (_process_translation_unit, _process_namespace, etc.) should ensure this.
            print(f"  Processing struct field/member: {node.spelling} (Kind: {node.kind})")
            if node.kind == CursorKind.FIELD_DECL:
                self._process_struct_field(node)
            # Can add handling for nested structs/classes if necessary

    def _process_struct_field(self, cursor: Cursor) -> None:
        """Process a struct field to identify callback function pointers."""
        print(f"Processing FIELD_DECL: {cursor.spelling} (Type: {cursor.type.spelling}, Kind: {cursor.type.kind.name})")
        # Check if the type of the field is a pointer (TypeKind.POINTER)
        # and if the type it points to is a function prototype (TypeKind.FUNCTIONPROTO)
        if cursor.type.kind == TypeKind.POINTER and cursor.type.get_pointee().kind == TypeKind.FUNCTIONPROTO:
            print(f"  Found potential callback: {cursor.spelling}, Type: {cursor.type.spelling}")
            callback_info = FunctionInfo(
                name=cursor.spelling, # This is the field name, might need to get function name from type
                file_path=cursor.location.file.name,
                line_number=cursor.location.line,
                is_callback=True,
                callback_type=cursor.type.spelling
            )
            self.callbacks.append(callback_info)
            print(f"    Stored callback field: {cursor.spelling}")

    def _process_function_call(self, caller_info: FunctionInfo, call_expr: Cursor) -> None:
        """Process a function call expression."""
        callee_cursor = call_expr.referenced
        if callee_cursor and callee_cursor.kind == CursorKind.FUNCTION_DECL or callee_cursor.kind == CursorKind.CXX_METHOD:
            
            callee_name = callee_cursor.spelling
            callee_parent = callee_cursor.semantic_parent
            if callee_parent and (callee_parent.kind == CursorKind.CLASS_DECL or callee_parent.kind == CursorKind.STRUCT_DECL or callee_parent.kind == CursorKind.NAMESPACE):
                callee_parent_name = callee_parent.spelling
                if callee_parent_name:
                    callee_name = f"{callee_parent_name}::{callee_name}"

            print(f"  Function Call: {caller_info.name} -> {callee_name} (Raw callee: {callee_cursor.spelling})")
            
            # Ensure callee_info is in self.functions (it might be a call to an unparsed/system function)
            if callee_name in self.functions:
                callee_info = self.functions[callee_name]
                call_relation = CallRelation(
                    caller=caller_info,
                    callee=callee_info
                )
                self.call_relations.append(call_relation)
                print(f"    Stored call relation: {caller_info.name} -> {callee_name}")
            else:
                print(f"    Warning: Callee function/method '{callee_name}' not found in analyzed functions. Skipping call relation from '{caller_info.name}'.")

    def _process_branch(self, containing_func_info: FunctionInfo, branch_node: Cursor) -> None:
        """Process a branch statement (if, switch, while, for)."""
        print(f"  Processing BRANCH: {branch_node.kind.name} in function {containing_func_info.name} (File: {branch_node.location.file.name}, Line: {branch_node.location.line})")
        branch_info = BranchInfo(
            branch_node_type=branch_node.kind.name,
            condition=self._get_branch_condition(branch_node),
            file_path=branch_node.location.file.name,
            line_number=branch_node.location.line
        )
        self.branches.append(branch_info)
        print(f"    Stored branch: {branch_info.branch_node_type} at {branch_info.file_path}:{branch_info.line_number}")

        # Link calls within this branch to the containing_func_info
        # The actual link between the branch_info node and containing_func_info (or calls within it)
        # will primarily be established in Dgraph via queries or schema structure (e.g., Function.in_branch -> Branch.uid)
        # For now, we are collecting call relations originating from containing_func_info that happen to be inside a branch AST node.
        for node in branch_node.get_children():
            if node.kind == CursorKind.CALL_EXPR:
                self._process_function_call(containing_func_info, node) # Calls are attributed to the function, not the branch itself

    def _get_branch_condition(self, branch: Cursor) -> Optional[str]:
        """Extract the condition of a branch statement. Basic version."""
        # Attempt to find the condition part of if, while, for statements.
        # This is a simplified approach; robust condition extraction can be complex.
        condition_str = ""
        # For IF_STMT, WHILE_STMT, the first child is often the condition.
        # For FOR_STMT, the second child is often the condition (after init-statement).
        # SWITCH_STMT condition is its first child.
        children = list(branch.get_children())
        if branch.kind == CursorKind.IF_STMT and len(children) > 0:
            condition_node = children[0]
            condition_str = ' '.join(t.spelling for t in condition_node.get_tokens())
        elif branch.kind == CursorKind.WHILE_STMT and len(children) > 0:
            condition_node = children[0]
            condition_str = ' '.join(t.spelling for t in condition_node.get_tokens())
        elif branch.kind == CursorKind.FOR_STMT and len(children) > 1:
            condition_node = children[1] # Index 1 for condition in for(init; cond; inc)
            condition_str = ' '.join(t.spelling for t in condition_node.get_tokens())
        elif branch.kind == CursorKind.SWITCH_STMT and len(children) > 0:
            condition_node = children[0]
            condition_str = ' '.join(t.spelling for t in condition_node.get_tokens())
        
        # print(f"    Extracted condition for {branch.kind.name}: '{condition_str}'")
        return condition_str if condition_str else None

    def get_analysis_results(self) -> Dict:
        """Return the complete analysis results."""
        return {
            'functions': list(self.functions.values()),
            'call_relations': self.call_relations,
            'callbacks': self.callbacks,
            'branches': self.branches
        } 