"""
Function model for representing function data and relationships.

This module defines the data models for representing functions and their
relationships in a call graph structure.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set, Any


@dataclass
class Function:
    """
    Represents a function in source code.
    
    Stores information about a function, including its name, definition,
    calling relationships, and other metadata.
    
    Attributes:
        name: The function name.
        signature: The function signature including parameters.
        file_path: The path to the file containing the function.
        body: The function body code.
        line_number: The line number where the function is defined.
        calls: List of function names this function calls.
        called_by: List of function names that call this function.
        namespace: The namespace containing this function.
        is_defined: Whether the function is defined or just declared.
        parameters: List of parameter names for this function.
        return_type: The function's return type.
        is_virtual: Whether the function is virtual.
        overrides: List of base class methods this function overrides.
        is_template: Whether the function is a template.
        template_params: List of template parameters.
        specializations: List of template specializations.
        class_hierarchy: List representing the class inheritance hierarchy.
        is_member: Whether the function is a class member.
        class_name: The name of the class if it's a member function.
        access_specifier: The access specifier (public, protected, private).
        is_const: Whether the method is const.
        is_static: Whether the method is static.
        is_operator: Whether the function is an operator overload.
        operator_kind: The kind of operator if is_operator is true.
        is_constructor: Whether the function is a constructor.
        is_destructor: Whether the function is a destructor.
        is_explicit: Whether the constructor is explicit.
        is_inline: Whether the function is inline.
        has_sfinae: Whether SFINAE techniques are applied.
        template_specialization_args: Specialized template arguments.
        has_variadic_templates: Whether the function uses variadic templates.
        variadic_template_param: The name of the parameter pack.
        sfinae_techniques: List of specific SFINAE techniques used.
        is_metafunction: Whether the function is a template metafunction.
        metafunction_kind: The kind of metafunction (type trait, etc).
        is_concept: Whether the function uses C++20 concepts.
        concept_requirements: List of concept requirements.
        partial_specialization: Whether this is a partial template specialization.
        primary_template: The name of the primary template for specializations.
        dependent_names: List of dependent names used in the template.
        template_template_params: List of template template parameters.
        constraint_expressions: List of constraint expressions for concepts or requires.
    """
    name: str
    signature: str = ""
    file_path: str = ""
    body: str = ""
    line_number: int = 0
    calls: List[str] = field(default_factory=list)
    called_by: List[str] = field(default_factory=list)
    namespace: str = ""
    is_defined: bool = True
    parameters: List[str] = field(default_factory=list)
    return_type: str = ""
    # Advanced C++ features
    is_virtual: bool = False
    overrides: List[str] = field(default_factory=list)
    is_template: bool = False
    template_params: List[str] = field(default_factory=list)
    specializations: List[str] = field(default_factory=list)
    class_hierarchy: List[str] = field(default_factory=list)
    # Enhanced C++ features (new fields)
    is_member: bool = False
    class_name: str = ""
    access_specifier: str = "public"  # public, protected, private
    is_const: bool = False
    is_static: bool = False
    is_operator: bool = False
    operator_kind: str = ""
    is_constructor: bool = False
    is_destructor: bool = False
    is_explicit: bool = False
    is_inline: bool = False
    has_sfinae: bool = False
    template_specialization_args: List[str] = field(default_factory=list)
    # Advanced template metaprogramming fields (new)
    has_variadic_templates: bool = False
    variadic_template_param: str = ""
    sfinae_techniques: List[str] = field(default_factory=list)  # enable_if, void_t, decltype, etc.
    is_metafunction: bool = False
    metafunction_kind: str = ""  # type_trait, value_trait, transform, etc.
    is_concept: bool = False
    concept_requirements: List[str] = field(default_factory=list)
    partial_specialization: bool = False
    primary_template: str = ""
    dependent_names: List[str] = field(default_factory=list)
    template_template_params: List[str] = field(default_factory=list)
    constraint_expressions: List[str] = field(default_factory=list)
    
    def add_call(self, function_name: str) -> None:
        """
        Add a function call to this function.
        
        Args:
            function_name: The name of the function being called.
        """
        if function_name not in self.calls:
            self.calls.append(function_name)
    
    def add_caller(self, function_name: str) -> None:
        """
        Add a function that calls this function.
        
        Args:
            function_name: The name of the function that calls this one.
        """
        if function_name not in self.called_by:
            self.called_by.append(function_name)

    def add_specialization(self, specialized_name: str) -> None:
        """
        Add a template specialization for this template function.
        
        Args:
            specialized_name: The name of the specialized function.
        """
        if specialized_name not in self.specializations:
            self.specializations.append(specialized_name)
    
    def add_override(self, base_method: str) -> None:
        """
        Add a base class method that this method overrides.
        
        Args:
            base_method: The name of the base class method.
        """
        if base_method not in self.overrides:
            self.overrides.append(base_method)
    
    def add_sfinae_technique(self, technique: str) -> None:
        """
        Add a SFINAE technique used in this template function.
        
        Args:
            technique: The SFINAE technique name (e.g., 'enable_if', 'void_t').
        """
        if technique not in self.sfinae_techniques:
            self.sfinae_techniques.append(technique)
            self.has_sfinae = True
    
    def add_concept_requirement(self, requirement: str) -> None:
        """
        Add a concept requirement for this template function.
        
        Args:
            requirement: The concept requirement expression.
        """
        if requirement not in self.concept_requirements:
            self.concept_requirements.append(requirement)
    
    def add_constraint_expression(self, constraint: str) -> None:
        """
        Add a constraint expression for this template function.
        
        Args:
            constraint: The constraint expression.
        """
        if constraint not in self.constraint_expressions:
            self.constraint_expressions.append(constraint)


@dataclass
class CallGraph:
    """
    Represents a call graph of functions.
    
    Stores a collection of Function objects and their relationships,
    as well as tracking missing function references.
    
    Attributes:
        functions: Dictionary mapping function names to Function objects.
        missing_functions: Set of function names that are called but not defined.
    """
    functions: Dict[str, Function] = field(default_factory=dict)
    missing_functions: Set[str] = field(default_factory=set)
    
    def add_function(self, function: Function) -> None:
        """
        Add a function to the call graph.
        
        Args:
            function: The Function object to add.
        """
        self.functions[function.name] = function
    
    def add_missing_function(self, function_name: str) -> None:
        """
        Add a missing function to the call graph.
        
        Args:
            function_name: The name of the missing function.
        """
        self.missing_functions.add(function_name)
    
    def get_function(self, function_name: str) -> Optional[Function]:
        """
        Get a function from the call graph.
        
        Args:
            function_name: The name of the function to retrieve.
            
        Returns:
            The Function object if found, None otherwise.
        """
        return self.functions.get(function_name) 