#!/usr/bin/env python
"""
Script to find all main functions in the Folly codebase using Neo4j.
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
    """Find all main functions in the Folly codebase."""
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
        
        # Find all main functions in the folly project
        logger.info("Searching for main functions in the folly project...")
        
        # Search for functions named exactly "main"
        main_query = """
        MATCH (f:Function)
        WHERE f.project = 'folly' AND f.name = 'main'
        RETURN f.name as name, f.file_path as file_path, f.line_number as line_number
        """
        
        main_functions = neo4j_service.execute_custom_query(main_query)
        
        if main_functions:
            logger.info(f"Found {len(main_functions)} main functions:")
            for i, func in enumerate(main_functions, 1):
                name = func.get('name', 'unknown')
                file_path = func.get('file_path', 'unknown')
                line_number = func.get('line_number', 0)
                logger.info(f"  {i}. {name} in {file_path}:{line_number}")
        else:
            logger.info("No functions named 'main' found, trying alternative search...")
            
            # Search for functions containing "main" in the name
            alt_query = """
            MATCH (f:Function)
            WHERE f.project = 'folly' AND f.name CONTAINS 'main'
            RETURN f.name as name, f.file_path as file_path, f.line_number as line_number
            """
            
            alt_functions = neo4j_service.execute_custom_query(alt_query)
            
            if alt_functions:
                logger.info(f"Found {len(alt_functions)} functions containing 'main':")
                for i, func in enumerate(alt_functions, 1):
                    name = func.get('name', 'unknown')
                    file_path = func.get('file_path', 'unknown')
                    line_number = func.get('line_number', 0)
                    logger.info(f"  {i}. {name} in {file_path}:{line_number}")
            else:
                # Check if there might be main functions with int return type
                logger.info("No functions with 'main' in name found, checking for int return type functions...")
                
                int_main_query = """
                MATCH (f:Function)
                WHERE f.project = 'folly' AND f.return_type = 'int' AND f.name = 'main'
                RETURN f.name as name, f.file_path as file_path, f.line_number as line_number
                """
                
                int_main_functions = neo4j_service.execute_custom_query(int_main_query)
                
                if int_main_functions:
                    logger.info(f"Found {len(int_main_functions)} main functions with int return type:")
                    for i, func in enumerate(int_main_functions, 1):
                        name = func.get('name', 'unknown')
                        file_path = func.get('file_path', 'unknown')
                        line_number = func.get('line_number', 0)
                        logger.info(f"  {i}. {name} in {file_path}:{line_number}")
                else:
                    logger.info("No main functions found in the database.")
                    
                    # Search for file paths containing "main" or "example"
                    file_query = """
                    MATCH (f:Function)
                    WHERE f.project = 'folly' AND 
                          (f.file_path CONTAINS '/main' OR f.file_path CONTAINS '/example')
                    RETURN DISTINCT f.file_path as file_path, count(*) as function_count
                    ORDER BY function_count DESC
                    LIMIT 20
                    """
                    
                    file_results = neo4j_service.execute_custom_query(file_query)
                    
                    if file_results:
                        logger.info(f"Found {len(file_results)} files potentially containing main functions:")
                        for i, result in enumerate(file_results, 1):
                            file_path = result.get('file_path', 'unknown')
                            count = result.get('function_count', 0)
                            logger.info(f"  {i}. {file_path} ({count} functions)")
                    else:
                        logger.info("No relevant files found.")
        
        return main_functions
                
    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None

if __name__ == "__main__":
    main() 