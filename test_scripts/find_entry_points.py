#!/usr/bin/env python
"""
Script to find entry points and example functions in the Folly codebase.
This includes main functions, but also focuses on examples and important
functions that might serve as entry points for visualization.
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
    """Find entry points and examples in the Folly codebase."""
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
            logger.info("No functions named 'main' found")
            
        # Find all functions in example directories
        logger.info("Searching for functions in example directories...")
        example_query = """
        MATCH (f:Function)
        WHERE f.project = 'folly' AND f.file_path CONTAINS '/examples/'
        RETURN f.name as name, f.file_path as file_path, f.line_number as line_number
        ORDER BY f.file_path, f.line_number
        """
        
        example_functions = neo4j_service.execute_custom_query(example_query)
        
        if example_functions:
            logger.info(f"Found {len(example_functions)} functions in example directories:")
            for i, func in enumerate(example_functions, 1):
                name = func.get('name', 'unknown')
                file_path = func.get('file_path', 'unknown')
                line_number = func.get('line_number', 0)
                logger.info(f"  {i}. {name} in {file_path}:{line_number}")
        else:
            logger.info("No functions found in example directories")
            
        # Find important core functions with many outgoing calls
        logger.info("Finding core functions with many outgoing calls...")
        core_query = """
        MATCH (caller:Function)-[r:CALLS]->(callee:Function)
        WHERE caller.project = 'folly' AND callee.project = 'folly'
        AND NOT caller.file_path CONTAINS '/test/'
        AND NOT caller.file_path CONTAINS 'Test'
        WITH caller, count(r) as call_count
        WHERE call_count > 5
        RETURN caller.name as name, caller.file_path as file_path, 
               caller.line_number as line_number, call_count
        ORDER BY call_count DESC
        LIMIT 20
        """
        
        core_functions = neo4j_service.execute_custom_query(core_query)
        
        if core_functions:
            logger.info(f"Found {len(core_functions)} core functions with many outgoing calls:")
            for i, func in enumerate(core_functions, 1):
                name = func.get('name', 'unknown')
                file_path = func.get('file_path', 'unknown')
                line_number = func.get('line_number', 0)
                call_count = func.get('call_count', 0)
                logger.info(f"  {i}. {name} in {file_path}:{line_number} ({call_count} calls)")
        else:
            logger.info("No core functions found with many outgoing calls")
            
        # Find files likely to contain entry points
        logger.info("Finding files likely to contain entry points...")
        file_query = """
        MATCH (f:Function)
        WHERE f.project = 'folly' 
        AND (f.file_path CONTAINS '/example' OR 
             f.file_path CONTAINS '/benchmark' OR 
             f.file_path CONTAINS '/demo' OR
             f.file_path CONTAINS '/tool')
        AND NOT f.file_path CONTAINS '/test/'
        RETURN DISTINCT f.file_path as file_path, count(*) as function_count
        ORDER BY function_count DESC
        LIMIT 20
        """
        
        entry_point_files = neo4j_service.execute_custom_query(file_query)
        
        if entry_point_files:
            logger.info(f"Found {len(entry_point_files)} files likely to contain entry points:")
            for i, result in enumerate(entry_point_files, 1):
                file_path = result.get('file_path', 'unknown')
                count = result.get('function_count', 0)
                logger.info(f"  {i}. {file_path} ({count} functions)")
                
                # For each potential entry point file, get important functions
                file_functions_query = f"""
                MATCH (f:Function)
                WHERE f.project = 'folly' AND f.file_path = '{file_path}'
                RETURN f.name as name, f.line_number as line_number
                ORDER BY f.line_number
                """
                
                file_functions = neo4j_service.execute_custom_query(file_functions_query)
                
                if file_functions:
                    for j, func in enumerate(file_functions, 1):
                        name = func.get('name', 'unknown')
                        line_number = func.get('line_number', 0)
                        logger.info(f"    {j}. {name}:{line_number}")
        else:
            logger.info("No potential entry point files found")
        
        # Combine results for visualization purposes
        entry_points = []
        
        # Add main functions
        for func in main_functions:
            entry_points.append(func)
            
        # Add example functions (first function from each example file)
        example_files = set()
        for func in example_functions:
            file_path = func.get('file_path', '')
            if file_path and file_path not in example_files:
                example_files.add(file_path)
                entry_points.append(func)
                
        # Add core functions
        for func in core_functions:
            entry_points.append(func)
            
        logger.info(f"Total entry points identified: {len(entry_points)}")
        
        return entry_points
                
    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return []

if __name__ == "__main__":
    main() 