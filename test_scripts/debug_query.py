#!/usr/bin/env python
"""
Debug script for Neo4j queries.
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
    """Main function to debug Neo4j query syntax."""
    logger = setup_logging()
    
    # Neo4j connection parameters
    neo4j_uri = "bolt://localhost:7688"
    neo4j_username = "neo4j"
    neo4j_password = "password"
    
    # Query parameters
    project = "folly"
    focus = "BufferedRandomDevice"
    depth = 1
    limit = 50
    
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
        
        # Try a simpler query first
        logger.info("Executing simple query to check function existence...")
        simple_query = f"""
        MATCH (f:Function)
        WHERE f.project = '{project}' AND f.name CONTAINS '{focus}'
        RETURN f.name as name
        LIMIT 10
        """
        
        simple_results = neo4j_service.execute_custom_query(simple_query)
        if simple_results:
            logger.info(f"Found {len(simple_results)} functions containing '{focus}':")
            for i, result in enumerate(simple_results, 1):
                logger.info(f"  {i}. {result.get('name', 'unknown')}")
        else:
            logger.info(f"No functions found containing '{focus}'")
        
        # Try a different path query
        logger.info("\nExecuting relationship query...")
        relationship_query = f"""
        MATCH (caller:Function)-[r:CALLS]->(callee:Function)
        WHERE caller.project = '{project}' 
        AND callee.project = '{project}'
        AND (caller.name CONTAINS '{focus}' OR callee.name CONTAINS '{focus}')
        RETURN caller.name as caller, callee.name as callee
        LIMIT {limit}
        """
        
        rel_results = neo4j_service.execute_custom_query(relationship_query)
        if rel_results:
            logger.info(f"Found {len(rel_results)} call relationships:")
            for i, result in enumerate(rel_results, 1):
                caller = result.get('caller', 'unknown')
                callee = result.get('callee', 'unknown')
                logger.info(f"  {i}. {caller} -> {callee}")
        else:
            logger.info("No call relationships found")
            
        # Try retrieving more general relationships
        logger.info("\nExecuting general relationship query...")
        general_query = f"""
        MATCH (caller:Function)-[r:CALLS]->(callee:Function)
        WHERE caller.project = '{project}' AND callee.project = '{project}'
        RETURN caller.name as caller, callee.name as callee
        LIMIT 10
        """
        
        general_results = neo4j_service.execute_custom_query(general_query)
        if general_results:
            logger.info(f"Found {len(general_results)} general call relationships:")
            for i, result in enumerate(general_results, 1):
                caller = result.get('caller', 'unknown')
                callee = result.get('callee', 'unknown')
                logger.info(f"  {i}. {caller} -> {callee}")
        else:
            logger.info("No general call relationships found")
            
    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    main() 