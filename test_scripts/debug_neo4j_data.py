#!/usr/bin/env python
"""
Debug script to examine Neo4j data directly.
"""
import os
import sys
import logging

# Add parent directory to path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.neo4j_service import Neo4jService

def setup_logging():
    """Configure logging for the script."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(__name__)

def main():
    """Main function to debug Neo4j data format."""
    logger = setup_logging()
    
    # Neo4j connection parameters
    neo4j_uri = "bolt://localhost:7688"
    neo4j_username = "neo4j"
    neo4j_password = "password"
    
    try:
        # Connect to Neo4j
        logger.info(f"Connecting to Neo4j at {neo4j_uri}")
        neo4j_service = Neo4jService(
            uri=neo4j_uri,
            username=neo4j_username,
            password=neo4j_password
        )
        
        # Test connection
        if not neo4j_service.test_connection():
            logger.error("Failed to connect to Neo4j. Please check connection settings.")
            return
            
        logger.info("Successfully connected to Neo4j")
        
        # Get all node labels
        logger.info("Getting all node labels...")
        label_query = """
        CALL db.labels() YIELD label
        RETURN label
        """
        labels = neo4j_service.execute_custom_query(label_query)
        if labels:
            logger.info(f"Found {len(labels)} node labels:")
            for label in labels:
                logger.info(f"  - {label.get('label', 'unknown')}")
        else:
            logger.info("No node labels found")
        
        # Get all relationship types
        logger.info("\nGetting all relationship types...")
        rel_query = """
        CALL db.relationshipTypes() YIELD relationshipType
        RETURN relationshipType
        """
        rel_types = neo4j_service.execute_custom_query(rel_query)
        if rel_types:
            logger.info(f"Found {len(rel_types)} relationship types:")
            for rel_type in rel_types:
                logger.info(f"  - {rel_type.get('relationshipType', 'unknown')}")
        else:
            logger.info("No relationship types found")
        
        # Get node count by label
        logger.info("\nGetting node count by label...")
        count_query = """
        MATCH (n)
        RETURN labels(n) as label, count(*) as count
        """
        counts = neo4j_service.execute_custom_query(count_query)
        if counts:
            logger.info(f"Node counts by label:")
            for count in counts:
                logger.info(f"  - {count.get('label', 'unknown')}: {count.get('count', 0)}")
        else:
            logger.info("No nodes found")
        
        # Get relationship count by type
        logger.info("\nGetting relationship count by type...")
        rel_count_query = """
        MATCH ()-[r]->()
        RETURN type(r) as type, count(*) as count
        """
        rel_counts = neo4j_service.execute_custom_query(rel_count_query)
        if rel_counts:
            logger.info(f"Relationship counts by type:")
            for count in rel_counts:
                logger.info(f"  - {count.get('type', 'unknown')}: {count.get('count', 0)}")
        else:
            logger.info("No relationships found")
        
        # Get relationship count by project
        logger.info("\nGetting relationship count by project...")
        project_rel_query = """
        MATCH (caller:Function)-[r]->(callee:Function)
        WHERE caller.project = callee.project
        RETURN caller.project as project, type(r) as type, count(*) as count
        """
        project_rel_counts = neo4j_service.execute_custom_query(project_rel_query)
        if project_rel_counts:
            logger.info(f"Relationship counts by project and type:")
            for count in project_rel_counts:
                project = count.get('project', 'unknown')
                rel_type = count.get('type', 'unknown')
                count_val = count.get('count', 0)
                logger.info(f"  - {project} / {rel_type}: {count_val}")
        else:
            logger.info("No project relationships found")
        
        # Check specific function relationships
        target_function = "BufferedRandomDevice::get"
        logger.info(f"\nChecking relationships for function: {target_function}")
        function_rel_query = f"""
        MATCH (func:Function {{name: '{target_function}', project: 'folly'}})-[r]->(other)
        RETURN type(r) as type, other.name as name
        """
        function_rels = neo4j_service.execute_custom_query(function_rel_query)
        if function_rels:
            logger.info(f"Found {len(function_rels)} outgoing relationships:")
            for rel in function_rels:
                rel_type = rel.get('type', 'unknown')
                name = rel.get('name', 'unknown')
                logger.info(f"  - {rel_type} -> {name}")
        else:
            logger.info(f"No outgoing relationships found for {target_function}")
            
        # Check incoming relationships
        logger.info(f"\nChecking incoming relationships for function: {target_function}")
        function_in_rel_query = f"""
        MATCH (other)-[r]->(func:Function {{name: '{target_function}', project: 'folly'}})
        RETURN type(r) as type, other.name as name
        """
        function_in_rels = neo4j_service.execute_custom_query(function_in_rel_query)
        if function_in_rels:
            logger.info(f"Found {len(function_in_rels)} incoming relationships:")
            for rel in function_in_rels:
                rel_type = rel.get('type', 'unknown')
                name = rel.get('name', 'unknown')
                logger.info(f"  - {name} -{rel_type}-> {target_function}")
        else:
            logger.info(f"No incoming relationships found for {target_function}")
    
    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    main() 