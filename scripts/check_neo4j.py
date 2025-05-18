#!/usr/bin/env python
"""
Script to check what data is available in the Neo4j database.
"""
import os
import sys
import logging
from typing import List, Dict, Any

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
    """Main function to check Neo4j database content."""
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
        
        # Get all projects
        logger.info("Checking available projects...")
        projects_query = """
        MATCH (f:Function)
        RETURN DISTINCT f.project AS project, COUNT(f) AS function_count
        """
        projects = neo4j_service.execute_custom_query(projects_query)
        
        if not projects:
            logger.info("No projects found in the database")
            return
            
        logger.info(f"Found {len(projects)} projects in the database:")
        for project in projects:
            project_name = project.get('project', 'unknown')
            function_count = project.get('function_count', 0)
            logger.info(f"  - {project_name}: {function_count} functions")
            
        # Get project with most functions
        if projects:
            main_project = max(projects, key=lambda p: p.get('function_count', 0))
            main_project_name = main_project.get('project', 'unknown')
            
            # Get sample functions
            logger.info(f"\nSample functions from project '{main_project_name}':")
            functions_query = f"""
            MATCH (f:Function {{project: '{main_project_name}'}})
            RETURN f.name AS name, f.namespace AS namespace
            LIMIT 10
            """
            functions = neo4j_service.execute_custom_query(functions_query)
            
            for i, func in enumerate(functions, 1):
                func_name = func.get('name', 'unknown')
                namespace = func.get('namespace', '')
                logger.info(f"  {i}. {func_name}")
                
            # Get function call relationships
            logger.info(f"\nSample call relationships from project '{main_project_name}':")
            relationships_query = f"""
            MATCH (caller:Function {{project: '{main_project_name}'}})-[r:CALLS]->(callee:Function {{project: '{main_project_name}'}})
            RETURN caller.name AS caller, callee.name AS callee
            LIMIT 10
            """
            relationships = neo4j_service.execute_custom_query(relationships_query)
            
            if relationships:
                for i, rel in enumerate(relationships, 1):
                    caller = rel.get('caller', 'unknown')
                    callee = rel.get('callee', 'unknown')
                    logger.info(f"  {i}. {caller} -> {callee}")
            else:
                logger.info("  No call relationships found")
    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    main() 