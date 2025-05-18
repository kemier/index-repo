"""
Visualization utilities for call graphs.
"""
import os
import logging
import tempfile
import subprocess
from pathlib import Path
import networkx as nx
from typing import Dict, List, Set, Optional, Tuple

class CallGraphVisualizer:
    """
    Class to visualize function call graphs using data from Neo4j.
    """
    
    def __init__(self, neo4j_service):
        """
        Initialize the visualizer with Neo4j service.
        
        Args:
            neo4j_service: The Neo4j service to query data from
        """
        self.neo4j_service = neo4j_service
        self.logger = logging.getLogger(__name__)
    
    def generate_call_graph(self, project: str, output_path: str, 
                          depth: int = 2, limit: int = 1000, focus: Optional[str] = None,
                          include_templates: bool = True, include_virtuals: bool = True,
                          color_by_namespace: bool = True) -> str:
        """
        Generate a call graph visualization in PNG format.
        
        Args:
            project: Project name in Neo4j
            output_path: Path to save the output PNG
            depth: Maximum call relationship depth
            limit: Maximum number of functions to include
            focus: Optional function or namespace to focus on
            include_templates: Whether to include template functions
            include_virtuals: Whether to include virtual function relationships
            color_by_namespace: Whether to color nodes by namespace
            
        Returns:
            Path to the generated PNG file
        """
        self.logger.info(f"Generating call graph for project '{project}' (depth={depth}, limit={limit})")
        
        # Fetch data from Neo4j
        relationships = self._fetch_relationships(
            project, depth, limit, focus, include_templates, include_virtuals)
        
        if not relationships:
            self.logger.warning("No relationships found. Check your Neo4j database or parameters.")
            return None
            
        self.logger.info(f"Found {len(relationships)} function call relationships")
        
        # Create graph
        G = self._create_networkx_graph(relationships, color_by_namespace)
        
        # Generate DOT file
        dot_path = self._generate_dot_file(G)
        
        # Convert DOT to PNG
        png_path = self._convert_dot_to_png(dot_path, output_path)
        
        # Clean up temporary file
        if os.path.exists(dot_path):
            os.remove(dot_path)
            
        return png_path
    
    def _fetch_relationships(self, project: str, depth: int, limit: int, 
                           focus: Optional[str], include_templates: bool,
                           include_virtuals: bool) -> List[Dict]:
        """
        Fetch function call relationships from Neo4j.
        
        Args:
            project: Project name
            depth: Maximum call depth
            limit: Maximum number of relationships
            focus: Optional function or namespace to focus on
            include_templates: Whether to include template functions
            include_virtuals: Whether to include virtual relationships
            
        Returns:
            List of relationship dictionaries
        """
        # Handle simple case first - direct relationships (depth=1)
        if depth == 1:
            # Construct a simple direct relationship query
            focus_clause = f"AND (caller.name CONTAINS '{focus}' OR callee.name CONTAINS '{focus}')" if focus else ""
            template_clause = "" if include_templates else "AND NOT caller.name CONTAINS '<' AND NOT callee.name CONTAINS '<'"
            
            relationships_to_match = ["CALLS"]
            if include_virtuals:
                relationships_to_match.extend(["OVERRIDES", "SPECIALIZES"])
            
            rel_type_str = "|".join(f":{rel}" for rel in relationships_to_match)
            
            query = f"""
            MATCH (caller:Function)-[r{rel_type_str}]->(callee:Function)
            WHERE caller.project = '{project}' 
            AND callee.project = '{project}'
            {focus_clause}
            {template_clause}
            RETURN caller.name as caller, callee.name as callee,
                   caller.namespace as caller_namespace, callee.namespace as callee_namespace,
                   type(r) as relationship_type
            LIMIT {limit}
            """
        else:
            # For deeper paths, we'll need to use a different approach
            # This is a simplified version that may not handle all cases correctly
            # but should avoid syntax errors
            focus_clause = f"AND (startNode.name CONTAINS '{focus}' OR endNode.name CONTAINS '{focus}')" if focus else ""
            template_clause = "" if include_templates else "AND NOT startNode.name CONTAINS '<' AND NOT endNode.name CONTAINS '<'"
            
            relationships_to_match = ["CALLS"]
            if include_virtuals:
                relationships_to_match.extend(["OVERRIDES", "SPECIALIZES"])
            
            rel_type_str = "|".join(f":{rel}" for rel in relationships_to_match)
            
            query = f"""
            MATCH path = shortestPath((startNode:Function)-[r{rel_type_str}*1..{depth}]->(endNode:Function))
            WHERE startNode.project = '{project}'
            AND endNode.project = '{project}'
            {focus_clause}
            {template_clause}
            RETURN startNode.name as caller, endNode.name as callee,
                   startNode.namespace as caller_namespace, endNode.namespace as callee_namespace,
                   type(last(relationships(path))) as relationship_type
            LIMIT {limit}
            """
            
        self.logger.debug(f"Executing Neo4j query: {query}")
        
        # Execute the query
        try:
            results = self.neo4j_service.execute_custom_query(query)
            return results
        except Exception as e:
            self.logger.error(f"Error fetching relationships from Neo4j: {e}")
            # Let's add additional info to help debug the query
            self.logger.error(f"Query that failed: {query}")
            return []
    
    def _create_networkx_graph(self, relationships: List[Dict], 
                             color_by_namespace: bool) -> nx.DiGraph:
        """
        Create a NetworkX DiGraph from the relationships.
        
        Args:
            relationships: List of relationship dictionaries
            color_by_namespace: Whether to color nodes by namespace
            
        Returns:
            NetworkX DiGraph
        """
        G = nx.DiGraph()
        
        # Color mapping for namespaces
        namespace_colors = {}
        color_palette = [
            "#66c2a5", "#fc8d62", "#8da0cb", "#e78ac3", "#a6d854",
            "#ffd92f", "#e5c494", "#b3b3b3", "#8dd3c7", "#bebada",
            "#fb8072", "#80b1d3", "#fdb462", "#b3de69", "#fccde5"
        ]
        
        # Add nodes and edges
        for rel in relationships:
            caller = rel.get('caller', '')
            callee = rel.get('callee', '')
            caller_ns = rel.get('caller_namespace', '')
            callee_ns = rel.get('callee_namespace', '')
            rel_type = rel.get('relationship_type', 'CALLS')
            
            # Skip self-calls unless it's a recursive function
            if caller == callee and not caller.endswith('(recursive)'):
                continue
                
            # Add nodes if they don't exist
            if caller not in G:
                G.add_node(caller, namespace=caller_ns)
            if callee not in G:
                G.add_node(callee, namespace=callee_ns)
            
            # Add edge with relationship type
            G.add_edge(caller, callee, relationship=rel_type)
            
            # Add namespace colors
            if color_by_namespace:
                for ns in [caller_ns, callee_ns]:
                    if ns and ns not in namespace_colors:
                        color_idx = len(namespace_colors) % len(color_palette)
                        namespace_colors[ns] = color_palette[color_idx]
        
        # Set node colors based on namespace
        if color_by_namespace:
            for node in G.nodes:
                ns = G.nodes[node].get('namespace', '')
                if ns in namespace_colors:
                    G.nodes[node]['color'] = namespace_colors[ns]
                else:
                    G.nodes[node]['color'] = "#cccccc"  # Default gray
        
        return G
    
    def _generate_dot_file(self, G: nx.DiGraph) -> str:
        """
        Generate a DOT file from the NetworkX graph.
        
        Args:
            G: NetworkX DiGraph
            
        Returns:
            Path to the generated DOT file
        """
        # Create a temporary file for the DOT content
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.dot')
        temp_file.close()
        
        # Write DOT file content
        with open(temp_file.name, 'w') as f:
            f.write('digraph G {\n')
            f.write('  rankdir=LR;\n')  # Left to right layout
            f.write('  node [style=filled, fontname="Arial"];\n')
            f.write('  edge [fontname="Arial"];\n')
            
            # Write node definitions
            for node in G.nodes:
                node_name = node.replace('"', '\\"')  # Escape quotes
                short_name = self._get_short_name(node_name)
                color = G.nodes[node].get('color', '#cccccc')
                
                f.write(f'  "{node_name}" [label="{short_name}", fillcolor="{color}"];\n')
            
            # Write edge definitions
            for u, v, data in G.edges(data=True):
                u_name = u.replace('"', '\\"')
                v_name = v.replace('"', '\\"')
                rel_type = data.get('relationship', 'CALLS')
                
                # Set edge style and color based on relationship type
                if rel_type == 'OVERRIDES':
                    edge_style = 'dashed'
                    edge_color = 'blue'
                elif rel_type == 'SPECIALIZES':
                    edge_style = 'dotted'
                    edge_color = 'green'
                else:  # CALLS
                    edge_style = 'solid'
                    edge_color = 'black'
                
                f.write(f'  "{u_name}" -> "{v_name}" [style={edge_style}, color={edge_color}];\n')
            
            f.write('}\n')
            
        return temp_file.name
    
    def _convert_dot_to_png(self, dot_path: str, output_path: str) -> str:
        """
        Convert the DOT file to PNG using Graphviz.
        
        Args:
            dot_path: Path to the DOT file
            output_path: Desired output PNG path
            
        Returns:
            Path to the generated PNG file
        """
        try:
            # Ensure output directory exists
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            
            # Run the graphviz command
            cmd = ["dot", "-Tpng", dot_path, "-o", output_path]
            self.logger.debug(f"Executing Graphviz command: {' '.join(cmd)}")
            
            result = subprocess.run(cmd, check=True, 
                                  stdout=subprocess.PIPE, 
                                  stderr=subprocess.PIPE)
            
            if not os.path.exists(output_path):
                self.logger.error("PNG file was not created. Graphviz command did not report an error.")
                return None
                
            return output_path
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Error running Graphviz: {e}")
            self.logger.error(f"Stderr: {e.stderr.decode('utf-8') if e.stderr else 'None'}")
            return None
        except Exception as e:
            self.logger.error(f"Error converting DOT to PNG: {e}")
            return None
    
    def _get_short_name(self, full_name: str) -> str:
        """
        Get a shortened version of a function name for display.
        
        Args:
            full_name: Full function name
            
        Returns:
            Shortened name
        """
        # Keep template arguments but trim them for display
        if '<' in full_name and '>' in full_name:
            template_start = full_name.find('<')
            template_end = full_name.rfind('>')
            
            if template_start > 0 and template_end > template_start:
                template_part = full_name[template_start:template_end+1]
                if len(template_part) > 20:  # If template part is too long
                    short_template = '<...>'
                    full_name = full_name[:template_start] + short_template + full_name[template_end+1:]
        
        # If the name includes namespace, consider shortening it
        if '::' in full_name:
            parts = full_name.split('::')
            
            # For long namespace chains, keep only the last 2 components
            if len(parts) > 3:
                short_name = '::'.join(['...'] + parts[-2:])
            else:
                short_name = full_name
        else:
            short_name = full_name
            
        # Limit overall length
        if len(short_name) > 40:
            short_name = short_name[:37] + '...'
            
        return short_name 