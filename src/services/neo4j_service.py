"""
Neo4j service for managing interactions with the graph database.

This service handles connecting to the Neo4j database, creating nodes and relationships,
and executing queries to analyze code structure.
"""
from typing import List, Dict, Set, Optional, Any, Union
import os
import json
from neo4j import GraphDatabase, Driver, Session, Transaction
from src.models.function_model import Function, CallGraph


class Neo4jService:
    """Service for working with Neo4j graph database"""
    
    def __init__(self, uri: str = "bolt://localhost:7688", 
                 username: str = "neo4j", 
                 password: str = "password"):
        """
        Initialize the Neo4j service with connection parameters.
        
        Args:
            uri: Neo4j connection URI
            username: Database username
            password: Database password
        """
        self.uri = uri
        self.username = username
        self.password = password
        self._driver = None
    
    @property
    def driver(self) -> Driver:
        """Get or create the Neo4j driver instance"""
        if self._driver is None:
            self._driver = GraphDatabase.driver(
                self.uri, auth=(self.username, self.password)
            )
        return self._driver
    
    def close(self) -> None:
        """Close the Neo4j connection"""
        if self._driver is not None:
            self._driver.close()
            self._driver = None
    
    def test_connection(self) -> bool:
        """Test the Neo4j connection and return True if successful"""
        try:
            with self.driver.session() as session:
                result = session.run("RETURN 1 AS test")
                return result.single()["test"] == 1
        except Exception as e:
            print(f"Neo4j connection error: {e}")
            return False
    
    def clear_database(self) -> None:
        """Clear all nodes and relationships from the database"""
        with self.driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
    
    def clear_project(self, project_name: str) -> None:
        """Clear all nodes and relationships for a specific project
        
        Args:
            project_name: Name of the project to clear
        """
        with self.driver.session() as session:
            session.run(
                "MATCH (n:Function {project: $project}) DETACH DELETE n",
                project=project_name
            )
            print(f"Clearing existing data from Neo4j database for project '{project_name}'...")
    
    def clear_files(self, project_name: str, file_paths: List[str]) -> None:
        """Clear all nodes and relationships for specific files
        
        Args:
            project_name: Name of the project
            file_paths: List of file paths to clear
        """
        if not file_paths:
            return
            
        with self.driver.session() as session:
            for file_path in file_paths:
                session.run(
                    """
                    MATCH (f:Function {project: $project, file_path: $file_path})
                    DETACH DELETE f
                    """,
                    project=project_name,
                    file_path=file_path
                )
            print(f"Cleared data for {len(file_paths)} files in project '{project_name}'")
    
    def add_functions_manually(self, functions: List[Dict], project_name: str = "default") -> None:
        """
        Manually add functions to the database without using a CallGraph.
        
        Args:
            functions: List of function dictionaries with name, file_path, etc.
            project_name: Name to identify the project in the database
        """
        with self.driver.session() as session:
            # Create function nodes
            for func in functions:
                self._create_function_node_from_dict(session, func, project_name)
            
            # Create relationships if calls are specified
            for func in functions:
                if "calls" in func and func["calls"]:
                    for called_func in func["calls"]:
                        self._create_call_relationship(session, func["name"], called_func, project_name)
    
    def _create_function_node_from_dict(self, session: Session, func: Dict, project_name: str) -> None:
        """Create a node for a function from a dictionary"""
        cypher = """
        MERGE (f:Function {name: $name, project: $project})
        SET f.file_path = $file_path,
            f.line_number = $line_number,
            f.signature = $signature,
            f.namespace = $namespace,
            f.is_defined = $is_defined,
            f.return_type = $return_type,
            f.description = $description,
            f.is_virtual = $is_virtual,
            f.is_template = $is_template
        """
        session.run(
            cypher,
            name=func.get("name", ""),
            project=project_name,
            file_path=func.get("file_path", ""),
            line_number=func.get("line_number", 0),
            signature=func.get("signature", ""),
            namespace=func.get("namespace", ""),
            is_defined=func.get("is_defined", True),
            return_type=func.get("return_type", ""),
            description=func.get("description", ""),
            is_virtual=func.get("is_virtual", False),
            is_template=func.get("is_template", False)
        )
    
    def index_call_graph(self, call_graph: CallGraph, project_name: str = "default", clear: bool = False) -> None:
        """
        Index a call graph into the Neo4j database.
        
        Creates nodes for each function and relationships for calls between functions.
        
        Args:
            call_graph: The call graph to index
            project_name: Name to identify the project in the database
            clear: Whether to clear existing project data before indexing
        """
        if clear:
            self.clear_project(project_name)
            
        with self.driver.session() as session:
            # First create all function nodes
            for func_name, func in call_graph.functions.items():
                self._create_function_node(session, func, project_name)
            
            # Then create relationships between functions
            for func_name, func in call_graph.functions.items():
                for called_func in func.calls:
                    self._create_call_relationship(session, func_name, called_func, project_name)
                
                # Create template specialization relationships
                if func.is_template and func.specializations:
                    for specialized_func in func.specializations:
                        self._create_specialization_relationship(session, func_name, specialized_func, project_name)
                
                # Create override relationships
                if func.is_virtual and func.overrides:
                    for overridden_func in func.overrides:
                        self._create_override_relationship(session, func_name, overridden_func, project_name)
            
            # Create nodes for missing functions
            for missing_func in call_graph.missing_functions:
                self._create_missing_function_node(session, missing_func, project_name)
    
    def incremental_index(self, call_graph: CallGraph, project_name: str, changed_files: List[str], clear_files: bool = True) -> None:
        """
        Incrementally index a call graph, updating only the changed files.
        
        Args:
            call_graph: The call graph to index
            project_name: Name to identify the project in the database
            changed_files: List of file paths that have changed
            clear_files: Whether to clear existing file data before indexing
        """
        if not changed_files:
            print("No changed files to index")
            return
            
        # Filter functions from changed files
        changed_functions = {}
        for func_name, func in call_graph.functions.items():
            if func.file_path in changed_files:
                changed_functions[func_name] = func
        
        if clear_files:
            self.clear_files(project_name, changed_files)
            
        print(f"Incrementally indexing {len(changed_functions)} functions from {len(changed_files)} changed files")
        
        with self.driver.session() as session:
            # Create function nodes for changed files
            for func_name, func in changed_functions.items():
                self._create_function_node(session, func, project_name)
            
            # Create relationships for changed functions
            for func_name, func in changed_functions.items():
                # Call relationships
                for called_func in func.calls:
                    self._create_call_relationship(session, func_name, called_func, project_name)
                
                # Template specialization relationships
                if func.is_template and func.specializations:
                    for specialized_func in func.specializations:
                        self._create_specialization_relationship(session, func_name, specialized_func, project_name)
                
                # Override relationships
                if func.is_virtual and func.overrides:
                    for overridden_func in func.overrides:
                        self._create_override_relationship(session, func_name, overridden_func, project_name)
            
            # Update relationships for functions that call changed functions
            for func_name, func in call_graph.functions.items():
                if func.file_path not in changed_files:  # Only consider unchanged files
                    for called_func in func.calls:
                        if called_func in changed_functions:
                            # This unchanged function calls a changed function
                            self._create_call_relationship(session, func_name, called_func, project_name)
    
    def _create_function_node(self, session: Session, func: Function, project_name: str) -> None:
        """Create a node for a function"""
        cypher = """
        MERGE (f:Function {name: $name, project: $project})
        SET f.file_path = $file_path,
            f.line_number = $line_number,
            f.signature = $signature,
            f.namespace = $namespace,
            f.is_defined = $is_defined,
            f.return_type = $return_type,
            f.is_virtual = $is_virtual,
            f.is_template = $is_template,
            f.is_member = $is_member,
            f.class_name = $class_name,
            f.is_const = $is_const,
            f.is_static = $is_static,
            f.is_constructor = $is_constructor,
            f.is_destructor = $is_destructor,
            f.is_operator = $is_operator,
            f.operator_kind = $operator_kind,
            f.has_sfinae = $has_sfinae,
            f.sfinae_techniques = $sfinae_techniques,
            f.has_variadic_templates = $has_variadic_templates,
            f.variadic_template_param = $variadic_template_param,
            f.is_metafunction = $is_metafunction,
            f.metafunction_kind = $metafunction_kind,
            f.is_concept = $is_concept,
            f.partial_specialization = $partial_specialization,
            f.primary_template = $primary_template,
            f.indexed_at = timestamp()
        """
        session.run(
            cypher,
            name=func.name,
            project=project_name,
            file_path=func.file_path,
            line_number=func.line_number,
            signature=func.signature,
            namespace=func.namespace,
            is_defined=func.is_defined,
            return_type=func.return_type,
            is_virtual=func.is_virtual,
            is_template=func.is_template,
            is_member=func.is_member,
            class_name=func.class_name,
            is_const=func.is_const,
            is_static=func.is_static,
            is_constructor=func.is_constructor,
            is_destructor=func.is_destructor,
            is_operator=func.is_operator,
            operator_kind=func.operator_kind,
            has_sfinae=func.has_sfinae,
            sfinae_techniques=func.sfinae_techniques,
            has_variadic_templates=func.has_variadic_templates,
            variadic_template_param=func.variadic_template_param,
            is_metafunction=func.is_metafunction,
            metafunction_kind=func.metafunction_kind,
            is_concept=func.is_concept,
            partial_specialization=func.partial_specialization,
            primary_template=func.primary_template
        )
        
        # Store array properties as separate nodes with relationships
        if func.template_params:
            self._store_array_property(session, func.name, project_name, "template_params", func.template_params)
        
        if func.template_specialization_args:
            self._store_array_property(session, func.name, project_name, "template_specialization_args", func.template_specialization_args)
            
        if func.concept_requirements:
            self._store_array_property(session, func.name, project_name, "concept_requirements", func.concept_requirements)
            
        if func.constraint_expressions:
            self._store_array_property(session, func.name, project_name, "constraint_expressions", func.constraint_expressions)
            
        if func.dependent_names:
            self._store_array_property(session, func.name, project_name, "dependent_names", func.dependent_names)
            
        if func.template_template_params:
            self._store_array_property(session, func.name, project_name, "template_template_params", func.template_template_params)
        
        # If there's a function body, add it as a separate TextContent node
        if func.body:
            self._create_function_body_node(session, func.name, func.body, project_name)
    
    def _store_array_property(self, session: Session, func_name: str, project_name: str, 
                            property_name: str, values: List[str]) -> None:
        """Store array properties as separate nodes with relationships to the function.
        
        Args:
            session: Neo4j session
            func_name: Function name
            project_name: Project name
            property_name: Name of the property
            values: List of string values
        """
        # Delete existing property nodes for this function
        session.run(
            f"""
            MATCH (f:Function {{name: $func_name, project: $project}})-[r:HAS_{property_name.upper()}]->(p)
            DELETE r, p
            """,
            func_name=func_name,
            project=project_name
        )
        
        # Create property nodes and relationships
        for value in values:
            session.run(
                f"""
                MATCH (f:Function {{name: $func_name, project: $project}})
                CREATE (p:{property_name.title()} {{value: $value, project: $project}})
                CREATE (f)-[r:HAS_{property_name.upper()}]->(p)
                """,
                func_name=func_name,
                project=project_name,
                value=value
            )
    
    def _create_function_body_node(self, session: Session, func_name: str, body: str, project_name: str) -> None:
        """Create a text content node for a function body"""
        cypher = """
        MATCH (f:Function {name: $func_name, project: $project})
        MERGE (t:TextContent {function_name: $func_name, project: $project})
        SET t.content = $body
        MERGE (f)-[:HAS_CONTENT]->(t)
        """
        session.run(
            cypher,
            func_name=func_name,
            project=project_name,
            body=body
        )
    
    def _create_missing_function_node(self, session: Session, func_name: str, project_name: str) -> None:
        """Create a node for a missing function"""
        cypher = """
        MERGE (f:Function {name: $name, project: $project})
        SET f.is_defined = false,
            f.is_missing = true
        """
        session.run(
            cypher,
            name=func_name,
            project=project_name
        )
    
    def _create_call_relationship(self, session: Session, caller: str, callee: str, project_name: str) -> None:
        """Create a CALLS relationship between functions"""
        # Skip common C++ standard library functions to avoid cluttering the database
        # These are often templated and can cause many missing function nodes
        if (callee.startswith("std::") or 
            callee in ["basic_string", "basic_ostream", "basic_istream", "operator<<", "operator>>"] or
            callee.endswith("::operator=") or callee.endswith("::operator++")):
            return
            
        # Skip calls to the function itself (self-recursion) in Neo4j to reduce noise 
        if caller == callee:
            return
            
        # First ensure both nodes exist
        try:
            # Check if caller exists
            caller_result = session.run(
                "MATCH (f:Function {name: $name, project: $project}) RETURN count(f) as count",
                name=caller, project=project_name
            ).single()
            
            if not caller_result or caller_result["count"] == 0:
                # Create caller node if it doesn't exist
                self._create_missing_function_node(session, caller, project_name)
                
            # Check if callee exists
            callee_result = session.run(
                "MATCH (f:Function {name: $name, project: $project}) RETURN count(f) as count",
                name=callee, project=project_name
            ).single()
            
            if not callee_result or callee_result["count"] == 0:
                # Create callee node if it doesn't exist
                self._create_missing_function_node(session, callee, project_name)
                
            # Now create the relationship
            session.run(
                """
                MATCH (caller:Function {name: $caller, project: $project})
                MATCH (callee:Function {name: $callee, project: $project})
                MERGE (caller)-[r:CALLS {project: $project}]->(callee)
                ON CREATE SET r.count = 1
                ON MATCH SET r.count = r.count + 1
                """,
                caller=caller,
                callee=callee,
                project=project_name
            )
        except Exception as e:
            print(f"Error creating call relationship from {caller} to {callee}: {e}")
    
    def _create_specialization_relationship(self, session: Session, template_func: str, specialization: str, project_name: str) -> None:
        """Create a SPECIALIZES relationship between template function and specialization"""
        cypher = """
        MATCH (template:Function {name: $template, project: $project})
        MATCH (spec:Function {name: $specialization, project: $project})
        MERGE (spec)-[r:SPECIALIZES]->(template)
        """
        try:
            session.run(
                cypher,
                template=template_func,
                specialization=specialization,
                project=project_name
            )
        except Exception as e:
            print(f"Error creating specialization relationship: {e}")
    
    def _create_override_relationship(self, session: Session, method: str, base_method: str, project_name: str) -> None:
        """Create an OVERRIDES relationship between method and base method"""
        cypher = """
        MATCH (derived:Function {name: $method, project: $project})
        MATCH (base:Function {name: $base_method, project: $project})
        MERGE (derived)-[r:OVERRIDES]->(base)
        """
        try:
            session.run(
                cypher,
                method=method,
                base_method=base_method,
                project=project_name
            )
        except Exception as e:
            print(f"Error creating override relationship: {e}")
    
    def find_function(self, name: str, project_name: str = "default") -> Optional[Dict[str, Any]]:
        """
        Find a function by name.
        
        Args:
            name: Function name to find
            project_name: Project to search in
            
        Returns:
            Dictionary with function data if found, None otherwise
        """
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (f:Function {name: $name, project: $project})
                RETURN f
                """,
                name=name,
                project=project_name
            )
            
            record = result.single()
            if record:
                function_node = dict(record["f"])
                
                # Also get function body if available
                content_result = session.run(
                    """
                    MATCH (f:Function {name: $name, project: $project})-[:HAS_CONTENT]->(t:TextContent)
                    RETURN t.content AS body
                    """,
                    name=name,
                    project=project_name
                )
                
                content_record = content_result.single()
                if content_record:
                    function_node["body"] = content_record["body"]
                    
                return function_node
            
            return None
    
    def find_callers(self, function_name: str, project_name: str = "default", depth: int = 1) -> List[Dict[str, Any]]:
        """
        Find functions that call the specified function.
        
        Args:
            function_name: Name of the function to find callers for
            project_name: Project to search in
            depth: Depth of caller relationships to traverse
            
        Returns:
            List of caller function data
        """
        with self.driver.session() as session:
            # For depth 1, use a simple query
            if depth == 1:
                result = session.run(
                    """
                    MATCH (caller:Function)-[:CALLS]->(f:Function {name: $name, project: $project})
                    WHERE caller.project = $project
                    RETURN DISTINCT caller
                    """,
                    name=function_name,
                    project=project_name
                )
            else:
                # For depth > 1, use a simpler approach with single relationships
                callers = set()
                current_functions = [function_name]
                
                # Get callers one level at a time
                for i in range(depth):
                    next_functions = []
                    for func in current_functions:
                        result = session.run(
                            """
                            MATCH (caller:Function)-[:CALLS]->(f:Function {name: $name, project: $project})
                            WHERE caller.project = $project
                            RETURN DISTINCT caller
                            """,
                            name=func,
                            project=project_name
                        )
                        
                        for record in result:
                            caller = dict(record["caller"])
                            caller_name = caller.get("name")
                            if caller_name not in callers and caller_name != function_name:
                                callers.add(caller_name)
                                next_functions.append(caller_name)
                    
                    current_functions = next_functions
                    if not current_functions:
                        break
                
                # Finally get the actual caller node data
                caller_nodes = []
                for caller_name in callers:
                    result = session.run(
                        """
                        MATCH (caller:Function {name: $name, project: $project})
                        RETURN caller
                        """,
                        name=caller_name,
                        project=project_name
                    )
                    record = result.single()
                    if record:
                        caller_nodes.append(dict(record["caller"]))
                
                return caller_nodes
                
            return [dict(record["caller"]) for record in result]
    
    def find_callees(self, function_name: str, project_name: str = "default", depth: int = 1) -> List[Dict[str, Any]]:
        """
        Find functions called by the specified function.
        
        Args:
            function_name: Name of the function to find callees for
            project_name: Project to search in
            depth: Depth of callee relationships to traverse
            
        Returns:
            List of callees
        """
        with self.driver.session() as session:
            # For depth 1, use a simple query
            if depth == 1:
                result = session.run(
                    """
                    MATCH (f:Function {name: $name, project: $project})-[:CALLS]->(callee:Function)
                    WHERE callee.project = $project
                    RETURN DISTINCT callee
                    """,
                    name=function_name,
                    project=project_name
                )
            else:
                # For depth > 1, use a simpler approach with single relationships
                callees = set()
                current_functions = [function_name]
                
                # Get callees one level at a time
                for i in range(depth):
                    next_functions = []
                    for func in current_functions:
                        result = session.run(
                            """
                            MATCH (f:Function {name: $name, project: $project})-[:CALLS]->(callee:Function)
                            WHERE callee.project = $project
                            RETURN DISTINCT callee
                            """,
                            name=func,
                            project=project_name
                        )
                        
                        for record in result:
                            callee = dict(record["callee"])
                            callee_name = callee.get("name")
                            if callee_name not in callees and callee_name != function_name:
                                callees.add(callee_name)
                                next_functions.append(callee_name)
                    
                    current_functions = next_functions
                    if not current_functions:
                        break
                
                # Finally get the actual callee node data
                callee_nodes = []
                for callee_name in callees:
                    result = session.run(
                        """
                        MATCH (callee:Function {name: $name, project: $project})
                        RETURN callee
                        """,
                        name=callee_name,
                        project=project_name
                    )
                    record = result.single()
                    if record:
                        callee_nodes.append(dict(record["callee"]))
                
                return callee_nodes
                
            return [record["callee"] for record in result]
    
    def export_subgraph(self, function_name: str, project_name: str = "default", depth: int = 2) -> Dict[str, Any]:
        """
        Export a subgraph centered on a specific function.
        
        Args:
            function_name: Center function for the subgraph
            project_name: Project to search in
            depth: Depth of relationships to include
            
        Returns:
            Dictionary with nodes and relationships
        """
        with self.driver.session() as session:
            # Query for nodes in both directions up to the specified depth
            result = session.run(
                """
                MATCH (f:Function {name: $name, project: $project})
                OPTIONAL MATCH path1 = (f)-[:CALLS*1..$depth]->(called:Function)
                WHERE called.project = $project
                OPTIONAL MATCH path2 = (caller:Function)-[:CALLS*1..$depth]->(f)
                WHERE caller.project = $project
                WITH f, collect(nodes(path1)) as calls, collect(nodes(path2)) as callers
                RETURN f, calls, callers
                """,
                name=function_name,
                project=project_name,
                depth=depth
            )
            
            record = result.single()
            if not record:
                return {"nodes": [], "relationships": []}
            
            # Process nodes and relationships
            all_nodes = set()
            all_nodes.add(record["f"])
            
            # Add called functions
            for path in record["calls"]:
                for node in path:
                    all_nodes.add(node)
            
            # Add calling functions 
            for path in record["callers"]:
                for node in path:
                    all_nodes.add(node)
            
            # Now get relationships
            rels_result = session.run(
                """
                MATCH (f:Function {name: $name, project: $project})
                OPTIONAL MATCH path1 = (f)-[:CALLS*1..$depth]->(called:Function)
                WHERE called.project = $project
                OPTIONAL MATCH path2 = (caller:Function)-[:CALLS*1..$depth]->(f)
                WHERE caller.project = $project
                WITH f, 
                     collect(relationships(path1)) as call_rels, 
                     collect(relationships(path2)) as caller_rels
                RETURN call_rels, caller_rels
                """,
                name=function_name,
                project=project_name,
                depth=depth
            )
            
            rel_record = rels_result.single()
            relationships = []
            
            if rel_record:
                # Add relationships from calls
                for path_rels in rel_record["call_rels"]:
                    for rel in path_rels:
                        relationships.append({
                            "source": rel.start_node.id,
                            "target": rel.end_node.id,
                            "type": rel.type
                        })
                
                # Add relationships from callers
                for path_rels in rel_record["caller_rels"]:
                    for rel in path_rels:
                        relationships.append({
                            "source": rel.start_node.id,
                            "target": rel.end_node.id,
                            "type": rel.type
                        })
            
            return {
                "nodes": [dict(node) for node in all_nodes],
                "relationships": relationships
            }
    
    def find_missing_functions(self, project_name: str = "default") -> List[str]:
        """
        Find all missing functions in the project.
        
        Args:
            project_name: Project to search in
            
        Returns:
            List of missing function names
        """
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (f:Function {project: $project, is_defined: false})
                RETURN f.name AS name
                """,
                project=project_name
            )
            return [record["name"] for record in result]
    
    def index_clang_callgraph(self, call_graph: CallGraph, project_name: str, clear: bool = False):
        """
        Index a clang call graph into Neo4j.
        
        Args:
            call_graph: CallGraph generated by ClangAnalyzerService
            project_name: Project identifier
            clear: Whether to clear existing data for the project
        """
        if clear:
            self.clear_project(project_name)

        functions = call_graph.functions
        print(f"Indexing {len(functions)} functions in Neo4j...")
        
        with self.driver.session() as session:
            # First create nodes for all functions
            for func_name, func in functions.items():
                # Check if function already exists
                query = (
                    "MATCH (f:Function {name: $name, project: $project}) "
                    "RETURN f"
                )
                result = session.run(query, name=func_name, project=project_name)
                if not result.single():
                    # Create function node
                    query = (
                        "CREATE (f:Function {"
                        "name: $name, "
                        "file_path: $file_path, "
                        "line_number: $line_number, "
                        "signature: $signature, "
                        "project: $project"
                        "}) "
                        "RETURN f"
                    )
                    session.run(
                        query,
                        name=func_name,
                        file_path=func.file_path,
                        line_number=func.line_number if func.line_number else 0,
                        signature=func.signature,
                        project=project_name
                    )
            
            # Create relationships for function calls
            for func_name, func in functions.items():
                # Create 'CALLS' relationships
                for called_name in func.calls:
                    query = (
                        "MATCH (caller:Function {name: $caller_name, project: $project}), "
                        "(callee:Function {name: $callee_name, project: $project}) "
                        "MERGE (caller)-[:CALLS]->(callee)"
                    )
                    try:
                        session.run(
                            query, 
                            caller_name=func_name, 
                            callee_name=called_name, 
                            project=project_name
                        )
                    except Exception as e:
                        # Handle case where called function isn't indexed (e.g., external library)
                        print(f"Warning: Could not create CALLS relationship from {func_name} to {called_name}: {str(e)}")
                        # Create a placeholder node for missing functions
                        query = (
                            "MERGE (f:Function {"
                            "name: $name, "
                            "project: $project, "
                            "is_external: true"
                            "}) "
                        )
                        session.run(query, name=called_name, project=project_name)
                        
                        # Try creating the relationship again
                        query = (
                            "MATCH (caller:Function {name: $caller_name, project: $project}), "
                            "(callee:Function {name: $callee_name, project: $project}) "
                            "MERGE (caller)-[:CALLS]->(callee)"
                        )
                        session.run(
                            query, 
                            caller_name=func_name, 
                            callee_name=called_name, 
                            project=project_name
                        )
        
        print(f"Indexing complete. Indexed {len(functions)} functions in project '{project_name}'.")
    
    def find_template_specializations(self, template_name: str, project_name: str = "default") -> List[Dict[str, Any]]:
        """
        Find template specializations for a given template function.
        
        Args:
            template_name: Name of the template function
            project_name: Project to search in
            
        Returns:
            List of specialization function data
        """
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (template:Function {name: $name, project: $project})
                MATCH (spec:Function)-[:SPECIALIZES]->(template)
                WHERE spec.project = $project
                RETURN spec
                """,
                name=template_name,
                project=project_name
            )
            
            return [dict(record["spec"]) for record in result]
    
    def find_class_methods(self, class_name: str, project_name: str = "default") -> List[Dict[str, Any]]:
        """
        Find all methods belonging to a given class.
        
        Args:
            class_name: Name of the class
            project_name: Project to search in
            
        Returns:
            List of method function data
        """
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (f:Function {project: $project})
                WHERE f.class_name = $class_name OR f.name STARTS WITH $class_prefix
                RETURN f
                """,
                class_name=class_name,
                class_prefix=f"{class_name}::",
                project=project_name
            )
            
            return [dict(record["f"]) for record in result]
    
    def find_overridden_methods(self, method_name: str, project_name: str = "default") -> List[Dict[str, Any]]:
        """
        Find base class methods that are overridden by the given method.
        
        Args:
            method_name: Name of the derived method
            project_name: Project to search in
            
        Returns:
            List of overridden base methods
        """
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (derived:Function {name: $name, project: $project})
                MATCH (derived)-[:OVERRIDES]->(base:Function)
                WHERE base.project = $project
                RETURN base
                """,
                name=method_name,
                project=project_name
            )
            
            return [dict(record["base"]) for record in result]
    
    def find_derived_methods(self, method_name: str, project_name: str = "default") -> List[Dict[str, Any]]:
        """
        Find derived methods that override the given base method.
        
        Args:
            method_name: Name of the base method
            project_name: Project to search in
            
        Returns:
            List of derived methods
        """
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (base:Function {name: $name, project: $project})
                MATCH (derived:Function)-[:OVERRIDES]->(base)
                WHERE derived.project = $project
                RETURN derived
                """,
                name=method_name,
                project=project_name
            )
            
            return [dict(record["derived"]) for record in result]
    
    def find_functions_by_feature(self, project_name: str, 
                                feature_type: str, 
                                value: Any = True) -> List[Dict[str, Any]]:
        """
        Find functions with a specific C++ feature.
        
        Args:
            project_name: Project to search in
            feature_type: Type of feature to search for (is_virtual, is_template, etc.)
            value: Value to match for the feature (default: True)
            
        Returns:
            List of matching function data
        """
        valid_features = [
            'is_virtual', 'is_template', 'is_member', 
            'is_const', 'is_static', 'is_operator',
            'is_constructor', 'is_destructor', 'is_explicit',
            'is_inline', 'has_sfinae'
        ]
        
        if feature_type not in valid_features:
            raise ValueError(f"Invalid feature type. Must be one of: {', '.join(valid_features)}")
            
        with self.driver.session() as session:
            result = session.run(
                f"""
                MATCH (f:Function {{project: $project}})
                WHERE f.{feature_type} = $value
                RETURN f
                """,
                project=project_name,
                value=value
            )
            
            return [dict(record["f"]) for record in result]
    
    def advanced_search(self, project_name: str, 
                       criteria: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Perform an advanced search with multiple criteria.
        
        Args:
            project_name: Project to search in
            criteria: Dictionary of search criteria
            
        Returns:
            List of matching function data
        """
        query_parts = ["MATCH (f:Function {project: $project})"]
        params = {"project": project_name}
        
        # Build WHERE clauses for each criterion
        where_clauses = []
        for i, (key, value) in enumerate(criteria.items()):
            param_name = f"param_{i}"
            
            if key == "name_contains":
                where_clauses.append(f"f.name CONTAINS ${param_name}")
                params[param_name] = value
            elif key == "signature_contains":
                where_clauses.append(f"f.signature CONTAINS ${param_name}")
                params[param_name] = value
            elif key == "file_contains":
                where_clauses.append(f"f.file_path CONTAINS ${param_name}")
                params[param_name] = value
            elif key == "is_in_namespace":
                where_clauses.append(f"f.namespace = ${param_name}")
                params[param_name] = value
            elif key in ["is_virtual", "is_template", "is_member", "is_const", "is_static", 
                        "is_operator", "is_constructor", "is_destructor", "is_explicit", 
                        "is_inline", "has_sfinae"]:
                where_clauses.append(f"f.{key} = ${param_name}")
                params[param_name] = value
            elif key == "calls_function":
                query_parts.append(f"MATCH (f)-[:CALLS]->(called:Function {{name: ${param_name}, project: $project}})")
                params[param_name] = value
            elif key == "called_by_function":
                query_parts.append(f"MATCH (caller:Function {{name: ${param_name}, project: $project}})-[:CALLS]->(f)")
                params[param_name] = value
            elif key == "overrides_function":
                query_parts.append(f"MATCH (f)-[:OVERRIDES]->(base:Function {{name: ${param_name}, project: $project}})")
                params[param_name] = value
            elif key == "specializes_template":
                query_parts.append(f"MATCH (f)-[:SPECIALIZES]->(template:Function {{name: ${param_name}, project: $project}})")
                params[param_name] = value
        
        # Add WHERE clause if any conditions are present
        if where_clauses:
            query_parts.append("WHERE " + " AND ".join(where_clauses))
            
        # Complete the query
        query_parts.append("RETURN f")
        query = "\n".join(query_parts)
        
        # Execute the query
        with self.driver.session() as session:
            result = session.run(query, **params)
            return [dict(record["f"]) for record in result]
        
    def execute_custom_query(self, query: str, params: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Execute a custom Cypher query.
        
        Args:
            query: Cypher query string
            params: Parameters for the query
            
        Returns:
            List of record dictionaries
        """
        if params is None:
            params = {}
            
        with self.driver.session() as session:
            result = session.run(query, **params)
            return [dict(record) for record in result] 