#!/usr/bin/env python
"""
Script to find main functions and entry points in the Folly codebase, excluding test files.
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
    """Find entry points in the Folly codebase excluding test files."""
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
        
        # Find core Folly functions excluding test files
        logger.info("Searching for core Folly functions excluding test files...")
        
        # Query for core functions (excluding test files)
        core_query = """
        MATCH (f:Function)
        WHERE f.project = 'folly' 
        AND NOT f.file_path CONTAINS '/test/' 
        AND NOT f.file_path CONTAINS '\\test\\' 
        AND NOT f.file_path CONTAINS 'Test' 
        AND NOT f.file_path CONTAINS 'Benchmark'
        RETURN f.name as name, f.file_path as file_path, f.line_number as line_number
        ORDER BY f.file_path, f.line_number
        LIMIT 100
        """
        
        core_functions = neo4j_service.execute_custom_query(core_query)
        
        if core_functions:
            logger.info(f"Found {len(core_functions)} core functions:")
            for i, func in enumerate(core_functions, 1):
                name = func.get('name', 'unknown')
                file_path = func.get('file_path', 'unknown')
                line_number = func.get('line_number', 0)
                logger.info(f"  {i}. {name} in {file_path}:{line_number}")
        else:
            logger.info("No core functions found")
        
        # Find important classes/components
        logger.info("Identifying important Folly components...")
        
        component_query = """
        MATCH (f:Function)
        WHERE f.project = 'folly'
        AND NOT f.file_path CONTAINS '/test/' 
        AND NOT f.file_path CONTAINS '\\test\\' 
        AND NOT f.file_path CONTAINS 'Test' 
        AND NOT f.file_path CONTAINS 'Benchmark'
        RETURN DISTINCT split(f.name, '::')[0] as component, count(*) as count
        ORDER BY count DESC
        LIMIT 20
        """
        
        components = neo4j_service.execute_custom_query(component_query)
        
        if components:
            logger.info(f"Found {len(components)} important components:")
            for i, comp in enumerate(components, 1):
                component = comp.get('component', 'unknown')
                count = comp.get('count', 0)
                logger.info(f"  {i}. {component} ({count} functions)")
                
                # Get sample functions for each component
                sample_query = f"""
                MATCH (f:Function)
                WHERE f.project = 'folly'
                AND f.name STARTS WITH '{component}::'
                AND NOT f.file_path CONTAINS '/test/' 
                AND NOT f.file_path CONTAINS '\\test\\' 
                AND NOT f.file_path CONTAINS 'Test' 
                AND NOT f.file_path CONTAINS 'Benchmark'
                RETURN f.name as name, f.file_path as file_path
                LIMIT 5
                """
                
                samples = neo4j_service.execute_custom_query(sample_query)
                
                if samples:
                    logger.info(f"    Sample functions:")
                    for j, sample in enumerate(samples, 1):
                        name = sample.get('name', 'unknown')
                        file_path = sample.get('file_path', 'unknown')
                        logger.info(f"      {j}. {name} in {file_path}")
        else:
            logger.info("No important components found")
            
        # Find functions with many outgoing calls (likely entry points)
        logger.info("Finding functions with many outgoing calls (potential entry points)...")
        
        entry_point_query = """
        MATCH (caller:Function)-[r:CALLS]->(callee:Function)
        WHERE caller.project = 'folly' AND callee.project = 'folly'
        AND NOT caller.file_path CONTAINS '/test/'
        AND NOT caller.file_path CONTAINS '\\test\\'
        AND NOT caller.file_path CONTAINS 'Test'
        AND NOT caller.file_path CONTAINS 'Benchmark'
        WITH caller, count(r) as call_count
        WHERE call_count > 3
        RETURN caller.name as name, caller.file_path as file_path, 
               caller.line_number as line_number, call_count
        ORDER BY call_count DESC
        LIMIT 20
        """
        
        entry_points = neo4j_service.execute_custom_query(entry_point_query)
        
        if entry_points:
            logger.info(f"Found {len(entry_points)} potential entry points:")
            for i, func in enumerate(entry_points, 1):
                name = func.get('name', 'unknown')
                file_path = func.get('file_path', 'unknown')
                line_number = func.get('line_number', 0)
                call_count = func.get('call_count', 0)
                logger.info(f"  {i}. {name} in {file_path}:{line_number} ({call_count} calls)")
        else:
            logger.info("No potential entry points found")
            
        # Find initialization functions often used as entry points
        logger.info("Finding initialization functions...")
        
        init_query = """
        MATCH (f:Function)
        WHERE f.project = 'folly'
        AND NOT f.file_path CONTAINS '/test/' 
        AND NOT f.file_path CONTAINS '\\test\\' 
        AND NOT f.file_path CONTAINS 'Test' 
        AND NOT f.file_path CONTAINS 'Benchmark'
        AND (f.name CONTAINS 'init' OR 
             f.name CONTAINS 'Init' OR 
             f.name CONTAINS 'start' OR 
             f.name CONTAINS 'Start' OR
             f.name CONTAINS 'create' OR
             f.name CONTAINS 'Create')
        RETURN f.name as name, f.file_path as file_path, f.line_number as line_number
        LIMIT 20
        """
        
        init_functions = neo4j_service.execute_custom_query(init_query)
        
        if init_functions:
            logger.info(f"Found {len(init_functions)} initialization functions:")
            for i, func in enumerate(init_functions, 1):
                name = func.get('name', 'unknown')
                file_path = func.get('file_path', 'unknown')
                line_number = func.get('line_number', 0)
                logger.info(f"  {i}. {name} in {file_path}:{line_number}")
        else:
            logger.info("No initialization functions found")
        
        return core_functions
                
    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return []

if __name__ == "__main__":
    main() 