from typing import Any, Dict, Optional
from helixdb import HelixDB

class HelixDBService:
    """Service for working with HelixDB graph-vector database."""

    def __init__(self, host: str = "localhost", port: int = 6969) -> None:
        """
        Initialize the HelixDB client.

        Args:
            host: Hostname for HelixDB server.
            port: Port for HelixDB server.
        """
        self.client = HelixDB(host=host, port=port)

    def add_node(self, label: str, properties: Dict[str, Any]) -> Any:
        """
        Add a node with a label and properties.

        Args:
            label: The label/type of the node (e.g., 'Function', 'Class').
            properties: Dictionary of node properties.
        Returns:
            Result of the HelixDB query.
        """
        return self.client.query(f"ADD {label}({properties})")

    def add_relationship(self, from_id: str, to_id: str, rel_type: str, properties: Optional[Dict[str, Any]] = None) -> Any:
        """
        Add a relationship between two nodes.

        Args:
            from_id: ID or unique property of the source node.
            to_id: ID or unique property of the target node.
            rel_type: Relationship type (e.g., 'INVOKES', 'HAVE').
            properties: Optional dictionary of relationship properties.
        Returns:
            Result of the HelixDB query.
        """
        return self.client.query(f"ADD_REL {from_id} -[{rel_type}]-> {to_id} {properties or {}}")

    def query(self, query: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """
        Run a custom HelixDB query.

        Args:
            query: The query string.
            params: Optional parameters for the query.
        Returns:
            Query result.
        """
        return self.client.query(query, params or {}) 